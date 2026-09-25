/**
 * CombatTimeoutService
 *
 * GD-026 (ACC-010): серверная финализация боя по таймауту.
 * - Дедлайн персистится в combatInfo.timeoutAt ( executor пишет при атаке
 *   и при защите) — BullMQ-джоба лишь дёргает processAutoResolve к сроку.
 * - processAutoResolve проходит через ТОТ ЖЕ executeResolveCombat, что и
 *   ручная защита/резолв: ровно один исход и один инкремент sequenceNumber.
 * - Восстановление после рестарта: BullMQ-джобы живут в Redis, но при
 *   утерянной джобе/чистом Redis onModuleInit пересканирует активные бои
 *   и перепланирует/дофинализирует их по персистентному дедлайну.
 */

import { Injectable, Logger, OnModuleDestroy, OnModuleInit, Optional } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { PrismaService } from '../../database/prisma.service';
import { GameStateService, GameState } from '../game-state.service';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { GamePhase, DEFENSE_TIMEOUT_SECONDS, RESOLVE_TIMEOUT_SECONDS } from '../../game-engine/models';
import { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { GameActionService } from './game-action.service';
import { GameActionType } from '../models/game-action.model';

/**
 * Конфигурация timeout'а для боя
 */
export interface CombatTimeoutConfig {
  defenseTimeoutSeconds?: number;
  resolveTimeoutSeconds?: number;
}

/**
 * Данные для задачи auto-resolve
 */
export interface AutoResolveJobData {
  gameId: string;
  attackSequenceNumber: number;
  /** Стадия, на которой джоба была запланирована (для аудита причины) */
  stage: 'DEFENSE' | 'RESOLVE';
}

/**
 * Результат auto-resolve
 */
export interface AutoResolveResult {
  success: boolean;
  resolvedSequenceNumber: number;
  reason: string;
}

@Injectable()
export class CombatTimeoutService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(CombatTimeoutService.name);

  private static readonly QUEUE_NAME = 'combat-timeout';
  private static readonly DEFAULT_DEFENSE_TIMEOUT = DEFENSE_TIMEOUT_SECONDS;
  private static readonly DEFAULT_RESOLVE_TIMEOUT = RESOLVE_TIMEOUT_SECONDS;
  private static readonly RECOVERY_SWEEP_INTERVAL_MS = 60_000;
  private readonly SCHEDULED_JOB_PREFIX = 'combat:scheduled:';
  private recoveryTimer: ReturnType<typeof setInterval> | null = null;

  /** Часы сервиса. Публичное поле для clock-injectable тестов (GD-026):
   *  детерминированный now() вместо sleep-петель и fake timers. */
  now: () => Date = () => new Date();

  constructor(
    @InjectQueue(CombatTimeoutService.QUEUE_NAME)
    private readonly combatTimeoutQueue: Queue<AutoResolveJobData>,
    private readonly gameStateService: GameStateService,
    private readonly distributedLockService: DistributedLockService,
    private readonly prisma: PrismaService,
    private readonly actionExecutor: GameActionExecutorService,
    @Optional() private readonly gameSubscriptionService?: GameSubscriptionService,
    @Optional() private readonly gameActionService?: GameActionService,
  ) {}

  async onModuleInit(): Promise<void> {
    // Не блокируем старт приложения восстановлением: бои дедлайнами
    // персистентны, догоним асинхронно.
    void this.recoverScheduledWork().catch((e) =>
      this.logger.error(`Combat timeout recovery failed: ${e}`),
    );
    // Periodic recovery sweep: transient-отказ очереди (enqueue-failure при
    // атаке/защите), исчерпание round-cap дрейна и утерянные джобы чинятся
    // БЕЗ рестарта процесса — sweep перепланирует по персистентному дедлайну.
    this.recoveryTimer = setInterval(
      () =>
        void this.recoverScheduledWork().catch((e) =>
          this.logger.error(`Combat timeout recovery sweep failed: ${e}`),
        ),
      CombatTimeoutService.RECOVERY_SWEEP_INTERVAL_MS,
    );
    this.recoveryTimer.unref?.();
  }

  async onModuleDestroy(): Promise<void> {
    if (this.recoveryTimer) clearInterval(this.recoveryTimer);
    this.recoveryTimer = null;
    await this.combatTimeoutQueue.close();
  }

  /**
   * GD-026: восстановление запланированных работ после рестарта.
   * Джобы BullMQ переживают рестарт в Redis; здесь закрываются потери:
   * - истёкший дедлайн → немедленная финализация;
   * - будущий дедлайн без джобы → перепланирование.
   * Идемпотентно: processAutoResolve сам отбрасывает неактуальные фазы.
   */
  async recoverScheduledWork(): Promise<{ recovered: number; rescheduled: number }> {
    const rows = await this.prisma.gameState.findMany({
      where: { game: { status: 'IN_PROGRESS' } },
      select: { gameId: true, state: true, sequenceNumber: true },
    });

    let recovered = 0;
    let rescheduled = 0;
    for (const row of rows) {
      let state: GameState;
      try {
        state = this.gameStateService.deserialize(row.state as any);
      } catch {
        continue;
      }
      const combatInfo = state.metadata.combatInfo;
      if (
        !combatInfo ||
        (state.phase !== GamePhase.COMBAT && state.phase !== GamePhase.COMBAT_RESOLVE)
      ) {
        continue;
      }
      const deadline = this.deadlineOf(state);
      const remainingMs = deadline - this.now().getTime();
      if (remainingMs <= 0) {
        const result = await this.processAutoResolve({
          gameId: row.gameId,
          attackSequenceNumber: state.sequenceNumber,
          stage: state.phase === GamePhase.COMBAT ? 'DEFENSE' : 'RESOLVE',
        });
        if (result.success) recovered++;
      } else if (!(await this.hasScheduledAutoResolve(row.gameId))) {
        await this.scheduleAutoResolve(
          row.gameId,
          Math.ceil(remainingMs / 1000),
          state.sequenceNumber,
          state.phase === GamePhase.COMBAT ? 'DEFENSE' : 'RESOLVE',
        );
        rescheduled++;
      }
    }
    if (recovered || rescheduled) {
      this.logger.log(`Timeout recovery: ${recovered} finalized, ${rescheduled} rescheduled`);
    }
    return { recovered, rescheduled };
  }

  /** Дедлайн текущей стадии боя. Легаси-сейвы без timeoutAt — от startedAt. */
  private deadlineOf(state: GameState): number {
    const ci = state.metadata.combatInfo!;
    if (ci.timeoutAt) return new Date(ci.timeoutAt).getTime();
    const fallbackSeconds =
      state.phase === GamePhase.COMBAT
        ? CombatTimeoutService.DEFAULT_DEFENSE_TIMEOUT
        : CombatTimeoutService.DEFAULT_RESOLVE_TIMEOUT;
    return new Date(ci.startedAt).getTime() + fallbackSeconds * 1000;
  }

  /**
   * Запланировать auto-resolve через N секунд
   *
   * JobId — stage-специфичный (`combat:scheduled:<gameId>:<stage>`).
   * Общий id на обе стадии создавал race: remove() АКТИВНОЙ джобы
   * предыдущей стадии бросает, а BullMQ add с существующим jobId молча
   * возвращает старую джобу — RESOLVE-дедлайн оказывался не запланирован.
   * Теперь: защита планирует `:RESOLVE` независимо от `:DEFENSE`; устаревшая
   * джоба своей стадии (waiting/delayed) снимается перед перепланированием;
   * remove() активной джобы СВОЕЙ стадии безвреден — она уже исполняется и
   * прочитает персистентный deadline из состояния, а не свой delay.
   */
  async scheduleAutoResolve(
    gameId: string,
    delaySeconds: number = CombatTimeoutService.DEFAULT_DEFENSE_TIMEOUT,
    attackSequenceNumber?: number,
    stage: 'DEFENSE' | 'RESOLVE' = 'DEFENSE',
  ): Promise<void> {
    const jobId = this.jobIdFor(gameId, stage);

    try {
      const existingJob = await this.combatTimeoutQueue.getJob(jobId);
      if (existingJob) {
        await existingJob.remove();
      }
    } catch (e) {
      // Активную джобу снять нельзя — она сама no-op-нется по персистентному
      // дедлайну. Ошибки add ниже НЕ глотаются: потеря расписания видна
      // вызывающему и чинится recoverScheduledWork.
      this.logger.warn(`Could not remove stale ${stage} job for ${gameId}: ${e}`);
    }

    const jobData: AutoResolveJobData = {
      gameId,
      attackSequenceNumber: attackSequenceNumber || 0,
      stage,
    };

    await this.combatTimeoutQueue.add('auto-resolve', jobData, {
      jobId,
      delay: delaySeconds * 1000,
      attempts: 3,
      backoff: { type: 'exponential', delay: 1000 },
      removeOnComplete: { count: 10 },
      removeOnFail: { count: 50 },
    });

    this.logger.debug(`Scheduled auto-resolve (${stage}) for game ${gameId} in ${delaySeconds}s`);
  }

  async cancelAutoResolve(gameId: string): Promise<void> {
    for (const stage of ['DEFENSE', 'RESOLVE'] as const) {
      const jobId = this.jobIdFor(gameId, stage);
      try {
        const job = await this.combatTimeoutQueue.getJob(jobId);
        if (job) {
          await job.remove();
          this.logger.debug(`Cancelled auto-resolve (${stage}) for game ${gameId}`);
        }
      } catch {
        // Активную джобу снять нельзя — она no-op-нется по фазе/дедлайну
      }
    }
  }

  async hasScheduledAutoResolve(gameId: string): Promise<boolean> {
    for (const stage of ['DEFENSE', 'RESOLVE'] as const) {
      try {
        const job = await this.combatTimeoutQueue.getJob(this.jobIdFor(gameId, stage));
        if (job) return true;
      } catch {
        // очередь недоступна — считаем незапланированным (recovery перепланирует)
      }
    }
    return false;
  }

  async getTimeUntilResolve(gameId: string): Promise<number | null> {
    let best: number | null = null;
    for (const stage of ['DEFENSE', 'RESOLVE'] as const) {
      try {
        const job = await this.combatTimeoutQueue.getJob(this.jobIdFor(gameId, stage));
        if (!job) continue;
        const delay = job.delay;
        if (!delay) continue;
        const processedOn = job.processedOn || job.timestamp;
        const remaining = Math.max(0, processedOn + delay - Date.now());
        if (best === null || remaining < best) best = remaining;
      } catch {
        // ignore
      }
    }
    return best;
  }

  private jobIdFor(gameId: string, stage: 'DEFENSE' | 'RESOLVE'): string {
    return `${this.SCHEDULED_JOB_PREFIX}${gameId}:${stage}`;
  }

  /**
   * Processor для auto-resolve: вызывается BullMQ при наступлении таймаута.
   * Финализирует бой ТЕМ ЖЕ путём, что и ручной resolveCombat — через
   * GameActionExecutorService.executeResolveCombat с systemInitiator.
   */
  async processAutoResolve(data: AutoResolveJobData): Promise<AutoResolveResult> {
    const { gameId } = data;

    // Тот же ключ блокировки, что и у executeMutation (withLockOptions сам
    // НЕ добавляет префикс, а withLock добавляет — раньше получался
    // game:game:<id> и таймаут не сериализовался с мутациями).
    return await this.distributedLockService.withLockOptions(`game:${gameId}`, async () => {
      let state: GameState;
      try {
        state = await this.gameStateService.loadState(gameId);
      } catch (error) {
        this.logger.warn(`Auto-resolve: state unavailable for ${gameId}: ${error}`);
        return { success: false, resolvedSequenceNumber: 0, reason: 'State unavailable' };
      }

      // Поздняя/неактуальная джоба: бой уже разрешён или фаза ушла — no-op.
      const combatInfo = state.metadata.combatInfo;
      if (
        !combatInfo ||
        (state.phase !== GamePhase.COMBAT && state.phase !== GamePhase.COMBAT_RESOLVE)
      ) {
        return { success: false, resolvedSequenceNumber: state.sequenceNumber, reason: 'No combat in progress' };
      }

      const deadline = this.deadlineOf(state);
      if (deadline > this.now().getTime()) {
        return { success: false, resolvedSequenceNumber: state.sequenceNumber, reason: 'Deadline not reached' };
      }

      const reason =
        state.phase === GamePhase.COMBAT ? 'defense-timeout' : 'resolve-timeout';

      // GD-026: истёкший дедлайн при непустой очереди выборов (бой запаузен
      // на BOOST/mandatory-эффекте, оба клиента офлайн) — серверная
      // прогрессия через ПРОИЗВОДСТВЕННЫЕ резолверы выборов. Каждый шаг
      // легален, детерминирован, +1 seq, аудит и публикация. executeResolveCombat
      // может запаузить бой на новом выборе — цикл дренирует и его.
      let current = state;
      for (let round = 0; round < 8; round++) {
        const drained = await this.drainTimedOutPendingChoices(gameId, current, reason);
        if (drained.ok !== true) {
          this.logger.error(
            `Auto-resolve blocked by pending choice for game ${gameId}: ${drained.blocker}`,
          );
          return {
            success: false,
            resolvedSequenceNumber: current.sequenceNumber,
            reason: `Cannot auto-resolve pending choice: ${drained.blocker}`,
          };
        }
        current = drained.state;

        if (
          current.phase !== GamePhase.COMBAT &&
          current.phase !== GamePhase.COMBAT_RESOLVE
        ) {
          break; // дрейн сам довёл бой до конца (resume/выбросили игру в GAME_OVER)
        }

        // Легаси-сейвы без timeoutAt: executor требует явный дедлайн для
        // системного резолва — восстанавливаем его из startedAt (deadlineOf).
        const stateForExecutor: GameState = current.metadata.combatInfo?.timeoutAt
          ? current
          : {
              ...current,
              metadata: {
                ...current.metadata,
                combatInfo: {
                  ...current.metadata.combatInfo!,
                  timeoutAt: new Date(deadline),
                },
              },
            };

        // Системный резолв: userId — защитник (его окно истекло / его защита
        // уже сыграна); executor сам проверит дедлайн и применит один исход.
        const result = await this.actionExecutor.executeResolveCombat(
          { gameId },
          {
            userId: combatInfo.defenderId,
            gameId,
            currentState: stateForExecutor,
            systemInitiator: true,
          },
        );

        if (!result.success) {
          this.logger.warn(`Auto-resolve rejected for game ${gameId}: ${result.error}`);
          return { success: false, resolvedSequenceNumber: current.sequenceNumber, reason: result.error || 'Executor rejected' };
        }
        current = result.gameState!;
        await this.gameStateService.saveState(gameId, current);

        // Пауза на новом выборе (COMBAT_RESOLVE + очередь): публикуем
        // промежуточное состояние, следующий круг дренирует. Иначе бой
        // завершён — финальная публикация COMBAT_RESOLVED ниже.
        if (
          current.phase === GamePhase.COMBAT_RESOLVE &&
          (current.metadata.pendingEffects?.length ?? 0) > 0
        ) {
          await this.gameSubscriptionService?.publishGameUpdate(gameId, 'STATE_UPDATED', current);
          continue;
        }
        break;
      }

      // Honest open gate (GD-026): потолок раундов исчерпан, а бой ещё
      // запаузен на выборе — НЕ публикуем COMBAT_RESOLVED и не репортим
      // success: фальшивая финализация запрещена. Каждый пройденный шаг
      // легален и засейвлен; periodic recovery sweep (60 c) снова входит в
      // processAutoResolve по персистентному дедлайну и дренирует дальше.
      if (
        current.phase === GamePhase.COMBAT_RESOLVE &&
        (current.metadata.pendingEffects?.length ?? 0) > 0
      ) {
        this.logger.warn(
          `Auto-resolve round cap reached for game ${gameId} with pending choices — left open for recovery sweep`,
        );
        return {
          success: false,
          resolvedSequenceNumber: current.sequenceNumber,
          reason: 'Auto-resolve round cap reached with pending choices; combat left open for recovery sweep',
        };
      }

      await this.gameSubscriptionService?.publishGameUpdate(gameId, 'COMBAT_RESOLVED', current);
      await this.recordAudit(gameId, combatInfo.defenderId, current.sequenceNumber, reason);

      this.logger.log(`Auto-resolved combat for game ${gameId} (${reason}), seq=${current.sequenceNumber}`);

      return { success: true, resolvedSequenceNumber: current.sequenceNumber, reason };
    });
  }

  /**
   * GD-026: серверная прогрессия выборов по истёкшему дедлайну стадии.
   * Владелец офлайн → optional-выбор авто-отклоняется, mandatory получает
   * детерминированный легальный фолбэк (см.
   * GameActionExecutorService.buildSystemPendingFallback). Применение —
   * ТОЛЬКО production-резолверами (executeDeclinePendingEffect /
   * executeResolvePendingEffect): собственные эффекты не изобретаются,
   * очередь не чистится вручную. Каждый шаг: +1 seq, save, публикация
   * STATE_UPDATED, аудит без приватных данных (без id карт).
   * Блокер → очередь остаётся нетронутой с последнего валидного состояния.
   */
  private async drainTimedOutPendingChoices(
    gameId: string,
    start: GameState,
    reason: string,
  ): Promise<{ ok: true; state: GameState } | { ok: false; blocker: string }> {
    let state = start;
    // Каждый шаг обязан сдвинуть голову очереди; потолок страхует от
    // патологических цепочек эффектов, порождающих новые выборы.
    for (let step = 0; step < 32; step++) {
      if (state.phase === GamePhase.GAME_OVER) return { ok: true, state };
      const queue = state.metadata.pendingEffects ?? [];
      if (queue.length === 0) return { ok: true, state };
      const head = queue[0]!;
      const actor = head.playerId;

      let result: { success: boolean; gameState?: GameState; error?: string };
      if (head.optional) {
        result = await this.actionExecutor.executeDeclinePendingEffect(
          { gameId, effectId: head.id },
          { userId: actor, gameId, currentState: state },
        );
      } else {
        const fallback = await this.actionExecutor.buildSystemPendingFallback(head, state);
        if (!fallback) {
          return {
            ok: false,
            blocker: `mandatory ${head.type} (${head.id}) has no safe deterministic fallback`,
          };
        }
        result = await this.actionExecutor.executeResolvePendingEffect(
          { gameId, effectId: head.id, ...fallback },
          { userId: actor, gameId, currentState: state },
        );
      }
      if (!result.success || !result.gameState) {
        return { ok: false, blocker: result.error ?? `pending ${head.type} (${head.id}) rejected` };
      }
      const nextQueue = result.gameState.metadata.pendingEffects ?? [];
      // Прогресс шага = голова очереди сменилась (снята/замещена вложенным
      // выбором) ИЛИ multi-step pending продвинулся ПРИ СОХРАНЁННОМ id:
      // resolveChooseOne (chooseCount>1) снимает опцию за шаг, CHOOSE_SPACE
      // stage 1→2 заменяет голову на stage 2 — id и длина очереди не меняются,
      // продвижение видно по chooseCount/options/stage/mode/revealedCards.
      // Полное отсутствие изменений той же головы = no-op резолвера → блокер.
      const nextHead = nextQueue[0];
      if (
        nextHead?.id === head.id &&
        (nextHead.chooseCount ?? 1) === (head.chooseCount ?? 1) &&
        (nextHead.options?.length ?? 0) === (head.options?.length ?? 0) &&
        nextHead.stage === head.stage &&
        nextHead.mode === head.mode &&
        (nextHead.revealedCards?.length ?? 0) === (head.revealedCards?.length ?? 0)
      ) {
        return {
          ok: false,
          blocker: `pending ${head.type} (${head.id}) did not advance the queue`,
        };
      }
      state = result.gameState;
      await this.gameStateService.saveState(gameId, state);
      await this.gameSubscriptionService?.publishGameUpdate(gameId, 'STATE_UPDATED', state);
      await this.recordChoiceAudit(gameId, actor, state.sequenceNumber, reason, head);
    }
    return { ok: false, blocker: 'pending choice chain exceeded 32 steps' };
  }

  /** Аудит системного авто-выбора; без id карт — приватность руки/колоды. */
  private async recordChoiceAudit(
    gameId: string,
    playerId: string,
    sequenceNumber: number,
    reason: string,
    pending: { id: string; type: string; optional?: boolean },
  ): Promise<void> {
    if (!this.gameActionService) return;
    try {
      await this.gameActionService.recordAction({
        gameId,
        sequenceNumber,
        type: GameActionType.CARD_PLAYED,
        playerId,
        metadata: {
          action: 'autoResolveChoice',
          reason,
          pendingType: pending.type,
          effectId: pending.id,
          method: pending.optional ? 'decline' : 'deterministic-fallback',
        },
      });
    } catch (e) {
      this.logger.warn(`Failed to record auto-choice audit for ${gameId}: ${e}`);
    }
  }

  /** Журнал исхода таймаута — best-effort, тем же типом что ручной резолв. */
  private async recordAudit(
    gameId: string,
    playerId: string,
    sequenceNumber: number,
    reason: string,
  ): Promise<void> {
    if (!this.gameActionService) return;
    try {
      await this.gameActionService.recordAction({
        gameId,
        sequenceNumber,
        type: GameActionType.COMBAT_RESOLVED,
        playerId,
        metadata: { action: 'autoResolve', reason },
      });
    } catch (e) {
      this.logger.warn(`Failed to record auto-resolve audit for ${gameId}: ${e}`);
    }
  }

  async getQueueStats(): Promise<{
    active: number;
    waiting: number;
    completed: number;
    failed: number;
  }> {
    const [active, waiting, completed, failed] = await Promise.all([
      this.combatTimeoutQueue.getActiveCount(),
      this.combatTimeoutQueue.getWaitingCount(),
      this.combatTimeoutQueue.getCompletedCount(),
      this.combatTimeoutQueue.getFailedCount(),
    ]);

    return { active, waiting, completed, failed };
  }

  async cleanCompletedJobs(): Promise<void> {
    await this.combatTimeoutQueue.clean(0, 100, 'completed');
    await this.combatTimeoutQueue.clean(0, 100, 'failed');
  }
}
