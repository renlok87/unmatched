import { Injectable, Logger, Optional, Inject, forwardRef } from '@nestjs/common';
import { PrismaService } from '../../database/prisma.service';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { GameStateService } from '../game-state.service';
import { GameSubscriptionService } from '../game-subscription.service';
import {
  GameActionExecutorService,
  ActionContext,
} from '../../game-engine/services/game-action-executor.service';
import { AiDecisionService, AiAction } from '../../game-engine/services/ai-decision.service';
import { GamePhase } from '../../game-engine/models';
import type { GameState, PendingEffect } from '../../game-engine/models';
import { isCellPassable, isLivingFighter } from '../../game-engine/movement/traversal';
import { CombatTimeoutService } from './combat-timeout.service';
import { journalActionType } from '../models/game-action.model';
import {
  executeGameCommand,
  makeCommand,
  type GameCommand,
  type GameCommandKind,
} from '../../game-engine/services/game-command';
import { commitDecision } from './commit-decision';

/**
 * Оркестрация ходов ИИ-оппонента (VS_AI). Вызывается fire-and-forget из
 * game-actions.resolver.executeMutation ПОСЛЕ хода человека. Если игра VS_AI и
 * боту есть что делать (его ход / защита / отложенный эффект / резолв боя) —
 * крутит шаги: load → decide → executor.execute* → save → publish, под локом
 * на каждый шаг (оптимистик-лок saveState, как у человека). Реалтайм-апдейты
 * человек видит без F5.
 */
/**
 * AiAction → входная команда движка (DET-2): тот же kind и DTO, что у
 * человеческой мутации того же действия, и то же имя события журнала.
 */
export function aiActionCommand(
  action: AiAction,
  gameId: string,
): { kind: GameCommandKind; input: Record<string, unknown>; eventType: string } {
  switch (action.kind) {
    case 'attack':
      return {
        kind: 'attack',
        input: { gameId, attackerId: action.attackerId, targetId: action.targetId, cardId: action.cardId },
        eventType: 'ATTACK_INITIATED',
      };
    case 'defense':
      return { kind: 'playDefense', input: { gameId, cardId: action.cardId }, eventType: 'DEFENSE_PLAYED' };
    case 'resolveCombat':
      return { kind: 'resolveCombat', input: { gameId }, eventType: 'COMBAT_RESOLVED' };
    case 'maneuver':
      return {
        kind: 'maneuver',
        input: { gameId, maneuverId: action.maneuverId, moves: action.moves, boostCardId: action.boostCardId },
        eventType: 'MANEUVER',
      };
    case 'beginManeuver':
      return {
        kind: 'beginManeuver',
        input: { gameId, expectedSequenceNumber: action.expectedSequenceNumber },
        eventType: 'MANEUVER',
      };
    case 'discardToLimit':
      return {
        kind: 'discardToLimit',
        input: { gameId, pendingId: action.pendingId, cardIds: action.cardIds },
        eventType: 'CARD_DISCARDED',
      };
    case 'resolveChoose':
      return {
        kind: 'resolvePendingEffect',
        input: { gameId, effectId: action.effectId, optionIndex: action.optionIndex },
        eventType: 'CARD_PLAYED',
      };
    case 'resolveMove':
      return {
        kind: 'resolvePendingEffect',
        input: { gameId, effectId: action.effectId, fighterId: action.fighterId, x: action.x, y: action.y },
        eventType: 'CARD_PLAYED',
      };
    case 'resolveTarget':
      return {
        kind: 'resolvePendingEffect',
        input: { gameId, effectId: action.effectId, fighterId: action.fighterId },
        eventType: 'CARD_PLAYED',
      };
    case 'resolveDiscard':
      return {
        kind: 'resolvePendingEffect',
        input: { gameId, effectId: action.effectId, cardIds: action.cardIds },
        eventType: 'CARD_DISCARDED',
      };
    case 'resolveBoost':
      // BOOST_CHOICE (S05): карта-буст уходит в сброс, значение — в бой
      return {
        kind: 'resolvePendingEffect',
        input: { gameId, effectId: action.effectId, cardIds: action.cardIds },
        eventType: 'CARD_DISCARDED',
      };
    case 'resolveSpace':
      // CHOOSE_SPACE (S06, Restless Spirits): клетка без бойца
      return {
        kind: 'resolvePendingEffect',
        input: { gameId, effectId: action.effectId, x: action.x, y: action.y },
        eventType: 'CARD_PLAYED',
      };
    case 'resolveDeckPick':
      // DECK_TOP_PICK (S06, Prophecy): PICK 2 в руку / ORDER порядок возврата
      return {
        kind: 'resolvePendingEffect',
        input: { gameId, effectId: action.effectId, cardIds: action.cardIds },
        eventType: 'CARD_PLAYED',
      };
    case 'declinePending':
      return { kind: 'declinePendingEffect', input: { gameId, effectId: action.effectId }, eventType: 'CARD_PLAYED' };
    case 'endTurn':
      // TURN_ENDED — как у человека в game-actions.resolver.endTurn и как
      // GameActionType в журнале; TURN_CHANGED не входит в enum → запись
      // бот-endTurn молча выпадала из eventsSince-catchup (и GAME_ENDED при
      // терминальном endTurn вместе с ней).
      // Подписка turnChanged принимает оба имени (TURN_ENDED|TURN_CHANGED).
      return { kind: 'endTurn', input: { gameId }, eventType: 'TURN_ENDED' };
  }
}

/**
 * Диспетчер AiAction → production-executor (тот же путь, что у человека
 * через resolver'ы: executeGameCommand). Выделен из AiTurnService для
 * переиспользования тест-харнессами полного матча (человеческий сид на той
 * же механике). Часы — ctx.now (или сейчас); команда возвращается для журнала.
 */
export async function dispatchAiAction(
  executor: GameActionExecutorService,
  action: AiAction,
  ctx: ActionContext,
): Promise<{ result: { success: boolean; gameState?: any; error?: string }; eventType: string; command: GameCommand }> {
  const { kind, input, eventType } = aiActionCommand(action, ctx.gameId);
  const command = makeCommand(kind, ctx.userId, input, ctx.now ?? new Date(), ctx.systemInitiator);
  return { result: await executeGameCommand(executor, command, ctx.currentState), eventType, command };
}

type AiStep = {
  action: AiAction;
  result: { success: boolean; gameState?: GameState; error?: string };
  eventType: string;
  /** DET-2: the input command of the accepted step, for the journal */
  command: GameCommand;
};

/** DTO системного фолбэка (buildSystemPendingFallback) → ход бота того же типа выбора. */
function pendingAnswer(
  head: PendingEffect,
  dto: { fighterId?: string; x?: number; y?: number; optionIndex?: number; cardIds?: string[] },
): AiAction | null {
  const effectId = head.id;
  switch (head.type) {
    case 'CHOOSE_ONE':
      return dto.optionIndex === undefined ? null : { kind: 'resolveChoose', effectId, optionIndex: dto.optionIndex };
    case 'MOVE':
    case 'PLACE':
      return dto.fighterId && dto.x !== undefined && dto.y !== undefined
        ? { kind: 'resolveMove', effectId, fighterId: dto.fighterId, x: dto.x, y: dto.y }
        : null;
    case 'TARGET_FIGHTER':
      return dto.fighterId ? { kind: 'resolveTarget', effectId, fighterId: dto.fighterId } : null;
    case 'DISCARD_CARDS':
      return dto.cardIds ? { kind: 'resolveDiscard', effectId, cardIds: dto.cardIds } : null;
    case 'BOOST_CHOICE':
      return dto.cardIds ? { kind: 'resolveBoost', effectId, cardIds: dto.cardIds } : null;
    case 'CHOOSE_SPACE':
      return dto.x !== undefined && dto.y !== undefined ? { kind: 'resolveSpace', effectId, x: dto.x, y: dto.y } : null;
    case 'DECK_TOP_PICK':
      return dto.cardIds ? { kind: 'resolveDeckPick', effectId, cardIds: dto.cardIds } : null;
    default:
      return null;
  }
}

/**
 * Перебор там, где системного фолбэка нет или он слишком узок: опции
 * CHOOSE_ONE, любая проходимая клетка CHOOSE_SPACE (по правилу «any space»
 * занятая тоже легальна), живые цели TARGET_FIGHTER, карта руки для
 * BOOST_CHOICE (бот выбирает за себя — серверу за человека это запрещено).
 */
function simplePendingAnswers(
  head: PendingEffect,
  state: GameState,
  hand: readonly { id: string }[],
): AiAction[] {
  const effectId = head.id;
  switch (head.type) {
    case 'CHOOSE_ONE':
      return (head.options ?? []).map((o): AiAction => ({ kind: 'resolveChoose', effectId, optionIndex: o.index }));
    case 'CHOOSE_SPACE': {
      const out: AiAction[] = [];
      for (let y = 0; y < state.boardState.height; y++) {
        for (let x = 0; x < state.boardState.width; x++) {
          if (isCellPassable(state.boardState.cells[y]?.[x])) out.push({ kind: 'resolveSpace', effectId, x, y });
        }
      }
      return out;
    }
    case 'TARGET_FIGHTER':
      return state.fighters
        .filter((f) => isLivingFighter(f) && (!head.targetFighterIds || head.targetFighterIds.includes(f.id)))
        .map((f): AiAction => ({ kind: 'resolveTarget', effectId, fighterId: f.id }));
    case 'BOOST_CHOICE':
      return hand.map((c): AiAction => ({ kind: 'resolveBoost', effectId, cardIds: [c.id] }));
    default:
      return [];
  }
}

@Injectable()
export class AiTurnService {
  private readonly logger = new Logger(AiTurnService.name);
  private static readonly MAX_STEPS = 40;
  /** Потолок перебора запасных ответов за шаг (клетки доски, карты руки). */
  private static readonly MAX_FALLBACK_CANDIDATES = 64;

  constructor(
    private readonly prisma: PrismaService,
    private readonly lock: DistributedLockService,
    private readonly stateService: GameStateService,
    private readonly subscription: GameSubscriptionService,
    private readonly executor: GameActionExecutorService,
    private readonly decision: AiDecisionService,
    // forwardRef: CombatTimeoutService сам зависит от AiTurnService (таймаут
    // финализировал бой → продолжить ход атакующего VS_AI) — иначе circular DI
    @Optional()
    @Inject(forwardRef(() => CombatTimeoutService))
    private readonly combatTimeout?: CombatTimeoutService,
  ) {}

  /** Прогоняет ходы бота, если это VS_AI и боту есть что делать. Не бросает. */
  async maybeRunAiTurns(gameId: string): Promise<void> {
    try {
      const game = await this.prisma.game.findUnique({
        where: { id: gameId },
        select: { mode: true, opponentId: true, status: true },
      });
      if (!game || game.mode !== 'VS_AI' || !game.opponentId || game.status !== 'IN_PROGRESS') {
        return;
      }
      const aiUserId = game.opponentId;
      for (let step = 0; step < AiTurnService.MAX_STEPS; step++) {
        const progressed = await this.runOneStep(gameId, aiUserId);
        if (!progressed) break;
      }
    } catch (e) {
      this.logger.warn(`maybeRunAiTurns(${gameId}) прервано: ${(e as Error).message}`);
    }
  }

  /** Один шаг бота под локом. true — действие выполнено (есть прогресс). */
  private async runOneStep(gameId: string, aiUserId: string): Promise<boolean> {
    return this.lock.withLockOptions(
      `game:${gameId}`,
      async () => {
        const state = await this.stateService.loadState(gameId);
        if (state.phase === GamePhase.GAME_OVER) return false;

        // DET-2: one clock for the step; every candidate runs as a command at it
        const ctx: ActionContext = { userId: aiUserId, gameId, currentState: state, now: new Date() };
        const decided = this.decision.decide(state, aiUserId);
        const step =
          (decided ? await this.attempt(decided, ctx, state, false) : null) ??
          (await this.fallback(ctx, state, aiUserId, decided));
        if (!step) return false;

        // SEL-07: общий коммит с ручным путём. Отказ saveState пробрасывается
        // (потеря персистентности глотать НЕЛЬЗЯ); дедлайн боя и named-CUE
        // после коммита — best-effort: транзитный отказ Redis/PubSub не
        // прерывает дрейн (иначе VS_AI-матч виснет), закоммиченный seq —
        // источник истины, подписчики догонят eventsSince.
        // GD-039 Sol6 + DET-2: журнал хода бота для eventsSince-catchup человека
        // пишется в транзакции состояния. input с instance-id карт приватен боту:
        // getEventsSince отдаёт input только владельцу действия (playerId).
        // GAME_ENDED того же seq добавляет saveState.
        const committed = step.result.gameState!;
        await commitDecision(
          {
            stateService: this.stateService,
            subscription: this.subscription,
            combatTimeout: this.combatTimeout,
            logger: this.logger,
          },
          {
            gameId,
            state: committed,
            eventType: step.eventType,
            journal: [{
              type: journalActionType(step.eventType),
              playerId: aiUserId,
              payload: { action: `ai:${step.action.kind}`, input: JSON.parse(JSON.stringify(step.action)) },
              command: step.command,
            }],
          },
        );

        return committed.phase !== GamePhase.GAME_OVER;
      },
      { ttl: 10000, retryCount: 2, retryDelay: 150 },
    );
  }

  /**
   * Исполнить ход бота production-executor'ом. null — executor отверг ход
   * (или бросил), либо ход не сдвинул seq (страховка от зацикливания).
   * quiet — перебор запасных кандидатов: отказ каждого не логируется.
   */
  private async attempt(
    action: AiAction,
    ctx: ActionContext,
    state: GameState,
    quiet: boolean,
  ): Promise<AiStep | null> {
    let dispatched: { result: AiStep['result']; eventType: string; command: GameCommand };
    try {
      dispatched = await this.dispatch(action, ctx);
    } catch (e) {
      if (!quiet) this.logger.warn(`AI шаг «${action.kind}» упал: ${(e as Error).message}`);
      return null;
    }
    const { result, eventType, command } = dispatched;
    if (!result.success || !result.gameState) {
      if (!quiet) this.logger.warn(`AI шаг «${action.kind}» не выполнен: ${result.error}`);
      return null;
    }
    // Страховка от зацикливания: каждый шаг должен двигать seq
    if (result.gameState.sequenceNumber <= state.sequenceNumber) {
      if (!quiet) this.logger.warn(`AI шаг «${action.kind}» без прогресса seq — стоп`);
      return null;
    }
    return { action, result, eventType, command };
  }

  /**
   * AI-03 / SEL-04: запасной легальный ответ (аналог DefaultRandomChoice
   * оригинала). Вне боя у VS_AI нет дедлайна: если decide вернул null на
   * собственном обязательстве бота или executor отверг его ход, бот молча
   * вставал, а у человека в чужой фазе легальных мутаций нет. Кандидатов
   * проверяет production-executor, первый принятый — ход бота. Нет
   * кандидатов — боту действительно нечего делать (ход за человеком).
   */
  private async fallback(
    ctx: ActionContext,
    state: GameState,
    aiUserId: string,
    failed: AiAction | null,
  ): Promise<AiStep | null> {
    const failedKey = failed ? JSON.stringify(failed) : '';
    const candidates = (await this.fallbackCandidates(state, aiUserId))
      .filter((c) => JSON.stringify(c) !== failedKey)
      .slice(0, AiTurnService.MAX_FALLBACK_CANDIDATES);
    const reason = failed ? `rejected:${failed.kind}` : 'no-decision';
    const head = state.metadata.pendingEffects?.[0];
    const where = head && head.playerId === aiUserId ? ` head=${head.type}/${head.id}` : '';
    if (candidates.length === 0) {
      if (failed) {
        this.logger.error(
          `AI_FALLBACK game=${ctx.gameId} seq=${state.sequenceNumber} reason=${reason}${where}: запасного ответа нет — бот стоит`,
        );
      }
      return null;
    }
    for (let i = 0; i < candidates.length; i++) {
      const step = await this.attempt(candidates[i], ctx, state, true);
      if (step) {
        this.logger.warn(
          `AI_FALLBACK game=${ctx.gameId} seq=${state.sequenceNumber} reason=${reason}${where} -> ${step.action.kind} (кандидат ${i + 1}/${candidates.length})`,
        );
        return step;
      }
    }
    this.logger.error(
      `AI_FALLBACK game=${ctx.gameId} seq=${state.sequenceNumber} reason=${reason}${where}: executor отверг все ${candidates.length} запасных ответа — бот стоит`,
    );
    return null;
  }

  /**
   * Кандидаты по обязательству бота, от безопасного к перебору: системный
   * фолбэк таймаута (buildSystemPendingFallback), перебор опций / клеток /
   * целей / карт руки, decline для optional. Чужое обязательство или чужой
   * ход — пустой список.
   */
  private async fallbackCandidates(state: GameState, aiUserId: string): Promise<AiAction[]> {
    const out: AiAction[] = [];
    const hand = state.handZones[aiUserId]?.cards ?? [];
    const discard = state.metadata.pendingHandDiscard;
    if (discard) {
      if (discard.playerId === aiUserId) {
        out.push({ kind: 'discardToLimit', pendingId: discard.id, cardIds: hand.slice(0, discard.count).map((c) => c.id) });
        out.push({ kind: 'discardToLimit', pendingId: discard.id, cardIds: hand.slice(-discard.count).map((c) => c.id) });
      }
      return out;
    }
    const maneuver = state.metadata.pendingManeuver;
    if (maneuver) {
      if (maneuver.playerId === aiUserId) out.push({ kind: 'maneuver', maneuverId: maneuver.id, moves: [] });
      return out;
    }
    const head = state.metadata.pendingEffects?.[0];
    if (head) {
      if (head.playerId !== aiUserId) return out;
      const system = await this.executor.buildSystemPendingFallback(head, state);
      const systemAnswer = system ? pendingAnswer(head, system) : null;
      if (systemAnswer) out.push(systemAnswer);
      out.push(...simplePendingAnswers(head, state, hand));
      if (head.optional) out.push({ kind: 'declinePending', effectId: head.id });
      return out;
    }
    if (state.phase === GamePhase.COMBAT_RESOLVE) {
      out.push({ kind: 'resolveCombat' });
      return out;
    }
    if (state.phase === GamePhase.COMBAT) {
      // бот-защитник: бой без карты защиты
      if (state.metadata.combatInfo?.defenderId === aiUserId) out.push({ kind: 'resolveCombat' });
      return out;
    }
    if (
      state.currentTurnPlayerId === aiUserId &&
      (state.phase === GamePhase.ACTION_MANEUVER || state.phase === GamePhase.ACTION_ATTACK)
    ) {
      out.push({ kind: 'beginManeuver', expectedSequenceNumber: state.sequenceNumber });
      out.push({ kind: 'endTurn' });
    }
    return out;
  }

  private async dispatch(
    action: AiAction,
    ctx: ActionContext,
  ): Promise<{ result: { success: boolean; gameState?: any; error?: string }; eventType: string; command: GameCommand }> {
    return dispatchAiAction(this.executor, action, ctx);
  }
}
