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

import { Injectable, Logger, OnModuleDestroy, OnModuleInit, Optional, Inject, forwardRef } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Job, Queue } from 'bullmq';
import { PrismaService } from '../../database/prisma.service';
import { GameStateService, GameState } from '../game-state.service';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { GamePhase, DEFENSE_TIMEOUT_SECONDS, RESOLVE_TIMEOUT_SECONDS } from '../../game-engine/models';
import { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { GameActionService } from './game-action.service';
import { GameActionType } from '../models/game-action.model';
import { AiTurnService } from './ai-turn.service';

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
  // BullMQ forbids ':' in custom job ids ('Custom Id cannot contain :'),
  // which made every attack fail at scheduleAutoResolve against a live
  // queue (S07 specs ran on a mocked queue and missed it). cuid gameIds and
  // the stage token contain no '-', so the id stays unambiguous.
  private readonly SCHEDULED_JOB_PREFIX = 'combat-scheduled-';
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
    // forwardRef: AiTurnService планирует боевые дедлайны бота через нас,
    // а мы после авто-резолва дёргаем его дрейн — иначе circular DI
    @Optional()
    @Inject(forwardRef(() => AiTurnService))
    private readonly aiTurnService?: AiTurnService,
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
      const stage = state.phase === GamePhase.COMBAT ? 'DEFENSE' : 'RESOLVE';
      if (remainingMs <= 0) {
        const result = await this.processAutoResolve({
          gameId: row.gameId,
          attackSequenceNumber: state.sequenceNumber,
          stage,
        });
        if (result.success) recovered++;
      } else if (!(await this.hasCurrentScheduledWork(row.gameId, stage, state.sequenceNumber))) {
        await this.scheduleAutoResolve(
          row.gameId,
          Math.ceil(remainingMs / 1000),
          state.sequenceNumber,
          stage,
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
   * JobId — stage-специфичный (`combat-scheduled-<gameId>-<stage>`).
   * Общий id на обе стадии создавал race: remove() АКТИВНОЙ джобы
   * предыдущей стадии бросает, а BullMQ add с существующим jobId молча
   * возвращает старую джобу — RESOLVE-дедлайн оказывался не запланирован.
   * Теперь: защита планирует `-RESOLVE` независимо от `-DEFENSE`; устаревшая
   * джоба своей стадии (waiting/delayed) снимается перед перепланированием;
   * если старую активную джобу снять нельзя, текущая атака получает отдельный
   * id с sequenceNumber.
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

    const options = {
      jobId,
      delay: delaySeconds * 1000,
      attempts: 3,
      backoff: { type: 'exponential', delay: 1000 },
      removeOnComplete: { count: 10 },
      removeOnFail: { count: 50 },
    };
    const scheduled = await this.combatTimeoutQueue.add('auto-resolve', jobData, options);

    // BullMQ silently returns the old job when its id is still occupied (most
    // notably by an active job, which remove() cannot remove). Give this
    // attack its own id so a previous attack cannot swallow the new deadline.
    if (!(await this.isCurrentPendingJob(scheduled, gameId, stage, jobData.attackSequenceNumber))) {
      const sequenceJobId = this.sequenceJobIdFor(gameId, stage, jobData.attackSequenceNumber);
      const previous = await this.combatTimeoutQueue.getJob(sequenceJobId);
      if (previous) {
        if (await this.isCurrentPendingJob(previous, gameId, stage, jobData.attackSequenceNumber)) return;
        await previous.remove();
      }
      const fallback = await this.combatTimeoutQueue.add('auto-resolve', jobData, { ...options, jobId: sequenceJobId });
      if (!(await this.isCurrentPendingJob(fallback, gameId, stage, jobData.attackSequenceNumber))) {
        throw new Error(`Could not schedule current ${stage} timeout for ${gameId}`);
      }
    }

    this.logger.debug(`Scheduled auto-resolve (${stage}) for game ${gameId} in ${delaySeconds}s`);
  }

  async cancelAutoResolve(gameId: string): Promise<void> {
    // The current timeout may have a sequence id when an older active job
    // occupies the base id. Query pending jobs so cancellation also finds
    // that fallback after a service restart; active jobs are left to finish.
    let jobs: Job<AutoResolveJobData>[];
    try {
      jobs = await this.pendingScheduledJobs(gameId);
    } catch (e) {
      this.logger.warn(`Could not list scheduled jobs for ${gameId}: ${e}`);
      return;
    }
    for (const job of jobs) {
      try {
        await job.remove();
        this.logger.debug(`Cancelled auto-resolve (${job.data.stage}) for game ${gameId}`);
      } catch {
        // The worker may have activated it between listing and removal.
      }
    }
  }

  async hasScheduledAutoResolve(gameId: string): Promise<boolean> {
    try {
      if ((await this.pendingScheduledJobs(gameId)).length > 0) return true;
      // An active job counts only if it belongs to the current combat. An
      // active job from an earlier attack may remain after cancellation.
      const state = await this.gameStateService.loadState(gameId);
      if (!state.metadata.combatInfo) return false;
      if (state.phase !== GamePhase.COMBAT && state.phase !== GamePhase.COMBAT_RESOLVE) return false;
      const stage = state.phase === GamePhase.COMBAT ? 'DEFENSE' : 'RESOLVE';
      return await this.hasCurrentScheduledWork(gameId, stage, state.sequenceNumber);
    } catch {
      // Queue or state unavailable; recovery uses the persisted state directly.
      return false;
    }
  }

  async getTimeUntilResolve(gameId: string): Promise<number | null> {
    let best: number | null = null;
    try {
      for (const job of await this.pendingScheduledJobs(gameId)) {
        const delay = job.delay;
        if (!delay) continue;
        const processedOn = job.processedOn || job.timestamp;
        const remaining = Math.max(0, processedOn + delay - Date.now());
        if (best === null || remaining < best) best = remaining;
      }
    } catch {
      // очередь недоступна
    }
    return best;
  }

  private jobIdFor(gameId: string, stage: 'DEFENSE' | 'RESOLVE'): string {
    return `${this.SCHEDULED_JOB_PREFIX}${gameId}-${stage}`;
  }

  private sequenceJobIdFor(gameId: string, stage: 'DEFENSE' | 'RESOLVE', sequence: number): string {
    return `${this.jobIdFor(gameId, stage)}-${sequence}`;
  }

  private isScheduledJobForGame(job: Job<AutoResolveJobData>, gameId: string): boolean {
    const stage = job.data?.stage;
    if (job.data?.gameId !== gameId || (stage !== 'DEFENSE' && stage !== 'RESOLVE')) return false;
    const baseId = this.jobIdFor(gameId, stage);
    if (job.id === baseId) return true;
    const prefix = `${baseId}-`;
    return job.id?.startsWith(prefix) === true &&
      job.id.slice(prefix.length) === String(job.data.attackSequenceNumber);
  }

  private async pendingScheduledJobs(gameId: string): Promise<Job<AutoResolveJobData>[]> {
    const jobs = await this.combatTimeoutQueue.getJobs(['waiting', 'delayed']);
    const matching: Job<AutoResolveJobData>[] = [];
    for (const job of jobs) {
      if (!this.isScheduledJobForGame(job, gameId)) continue;
      const status = await job.getState();
      if (status === 'waiting' || status === 'delayed') matching.push(job);
    }
    return matching;
  }

  private async isCurrentPendingJob(
    job: Job<AutoResolveJobData> | null | undefined,
    gameId: string,
    stage: 'DEFENSE' | 'RESOLVE',
    sequence: number,
  ): Promise<boolean> {
    if (
      !job || job.data.gameId !== gameId || job.data.stage !== stage ||
      job.data.attackSequenceNumber !== sequence
    ) return false;
    const status = await job.getState();
    return status === 'waiting' || status === 'delayed' || status === 'active';
  }

  private async hasCurrentScheduledWork(
    gameId: string,
    stage: 'DEFENSE' | 'RESOLVE',
    sequence: number,
  ): Promise<boolean> {
    for (const jobId of [this.jobIdFor(gameId, stage), this.sequenceJobIdFor(gameId, stage, sequence)]) {
      const job = await this.combatTimeoutQueue.getJob(jobId);
      if (await this.isCurrentPendingJob(job, gameId, stage, sequence)) return true;
    }
    return false;
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
    const result = await this.distributedLockService.withLockOptions(`game:${gameId}`, async () => {
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
          await this.publishCue(gameId, 'STATE_UPDATED', current);
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

      await this.publishCue(gameId, 'COMBAT_RESOLVED', current);
      await this.recordAudit(gameId, combatInfo.defenderId, current.sequenceNumber, reason);
      if (current.phase === GamePhase.GAME_OVER) {
        // Финальный удар нанесён таймаутом: saveState уже закоммитил FINISHED —
        // авторитетный исход несут gameStateUpdated-барьер и HTTP query,
        // а не gameEnded: это lossy named-CUE (16-network-contract §4). CUE и
        // аудиты — best-effort и независимы: отказ COMBAT_RESOLVED не отменяет
        // попытку GAME_ENDED и не проваливает закоммиченный результат.
        await this.publishCue(gameId, 'GAME_ENDED', current);
        await this.recordAudit(gameId, combatInfo.defenderId, current.sequenceNumber, reason, GameActionType.GAME_ENDED, {
          winnerId: current.metadata.winnerId,
        });
      }

      this.logger.log(`Auto-resolved combat for game ${gameId} (${reason}), seq=${current.sequenceNumber}`);

      return { success: true, resolvedSequenceNumber: current.sequenceNumber, reason };
    });

    // GD-039 (ACC-019): таймаут финализировал бой, но ход атакующего VS_AI
    // продолжается (остались действия/выборы). Без триггера матч виснет:
    // человек в чужой фазе легальных мутаций не имеет, а executeMutation
    // дергает дрейн только после СВОЕЙ успешной мутации. Лок уже снят.
    if (result.success) {
      await this.aiTurnService?.maybeRunAiTurns(gameId);
    }
    return result;
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
      await this.publishCue(gameId, 'STATE_UPDATED', state);
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

  /** Named-CUE после коммита saveState — best-effort и независимы. Redis
   * publish может бросить уже после локального deliver: закоммиченный
   * результат не репортится как провал джобы, последующие CUE/аудиты
   * всё равно попытаны (COMBAT_RESOLVED упал → GAME_ENDED не теряется). */
  private async publishCue(gameId: string, eventType: string, state: GameState): Promise<void> {
    if (!this.gameSubscriptionService) return;
    try {
      await this.gameSubscriptionService.publishGameUpdate(gameId, eventType, state);
    } catch (e) {
      this.logger.warn(`Failed to publish ${eventType} for game ${gameId}: ${e}`);
    }
  }

  /** Журнал исхода таймаута — best-effort, тем же типом что ручной резолв. */
  private async recordAudit(
    gameId: string,
    playerId: string,
    sequenceNumber: number,
    reason: string,
    type: GameActionType = GameActionType.COMBAT_RESOLVED,
    extraMetadata: Record<string, unknown> = {},
  ): Promise<void> {
    if (!this.gameActionService) return;
    try {
      await this.gameActionService.recordAction({
        gameId,
        sequenceNumber,
        type,
        playerId,
        metadata: { action: 'autoResolve', reason, ...extraMetadata },
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
