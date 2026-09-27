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
import { GamePhase, DEFENSE_TIMEOUT_SECONDS, RESOLVE_TIMEOUT_SECONDS } from '../../game-engine/models';
import { CombatTimeoutService } from './combat-timeout.service';
import { GameActionService } from './game-action.service';
import { GameActionType } from '../models/game-action.model';

/**
 * Оркестрация ходов ИИ-оппонента (VS_AI). Вызывается fire-and-forget из
 * game-actions.resolver.executeMutation ПОСЛЕ хода человека. Если игра VS_AI и
 * боту есть что делать (его ход / защита / отложенный эффект / резолв боя) —
 * крутит шаги: load → decide → executor.execute* → save → publish, под локом
 * на каждый шаг (оптимистик-лок saveState, как у человека). Реалтайм-апдейты
 * человек видит без F5.
 */
/**
 * Диспетчер AiAction → production-executor (тот же путь, что у человека
 * через resolver'ы). Выделен из AiTurnService для переиспользования
 * тест-харнессами полного матча (человеческий сид на той же механике).
 */
export async function dispatchAiAction(
  executor: GameActionExecutorService,
  action: AiAction,
  ctx: ActionContext,
): Promise<{ result: { success: boolean; gameState?: any; error?: string }; eventType: string }> {
  const gameId = ctx.gameId;
  switch (action.kind) {
    case 'attack':
      return {
        result: await executor.executeAttack(
          { gameId, attackerId: action.attackerId, targetId: action.targetId, cardId: action.cardId },
          ctx,
        ),
        eventType: 'ATTACK_INITIATED',
      };
    case 'defense':
      return {
        result: await executor.executePlayDefense({ gameId, cardId: action.cardId }, ctx),
        eventType: 'DEFENSE_PLAYED',
      };
    case 'resolveCombat':
      return {
        result: await executor.executeResolveCombat({ gameId }, ctx),
        eventType: 'COMBAT_RESOLVED',
      };
    case 'maneuver':
      return {
        result: await executor.executeManeuver(
          { gameId, maneuverId: action.maneuverId, moves: action.moves, boostCardId: action.boostCardId },
          ctx,
        ),
        eventType: 'MANEUVER',
      };
    case 'beginManeuver':
      return {
        result: await executor.executeBeginManeuver(
          { gameId, expectedSequenceNumber: action.expectedSequenceNumber }, ctx,
        ),
        eventType: 'MANEUVER',
      };
    case 'discardToLimit':
      return {
        result: await executor.executeDiscardToLimit(
          { gameId, pendingId: action.pendingId, cardIds: action.cardIds }, ctx,
        ),
        eventType: 'CARD_DISCARDED',
      };
    case 'resolveChoose':
      return {
        result: await executor.executeResolvePendingEffect(
          { gameId, effectId: action.effectId, optionIndex: action.optionIndex },
          ctx,
        ),
        eventType: 'CARD_PLAYED',
      };
    case 'resolveMove':
      return {
        result: await executor.executeResolvePendingEffect(
          { gameId, effectId: action.effectId, fighterId: action.fighterId, x: action.x, y: action.y },
          ctx,
        ),
        eventType: 'CARD_PLAYED',
      };
    case 'resolveTarget':
      return {
        result: await executor.executeResolvePendingEffect(
          { gameId, effectId: action.effectId, fighterId: action.fighterId },
          ctx,
        ),
        eventType: 'CARD_PLAYED',
      };
    case 'resolveDiscard':
      return {
        result: await executor.executeResolvePendingEffect(
          { gameId, effectId: action.effectId, cardIds: action.cardIds },
          ctx,
        ),
        eventType: 'CARD_DISCARDED',
      };
    case 'resolveBoost':
      // BOOST_CHOICE (S05): карта-буст уходит в сброс, значение — в бой
      return {
        result: await executor.executeResolvePendingEffect(
          { gameId, effectId: action.effectId, cardIds: action.cardIds },
          ctx,
        ),
        eventType: 'CARD_DISCARDED',
      };
    case 'resolveSpace':
      // CHOOSE_SPACE (S06, Restless Spirits): клетка без бойца
      return {
        result: await executor.executeResolvePendingEffect(
          { gameId, effectId: action.effectId, x: action.x, y: action.y },
          ctx,
        ),
        eventType: 'CARD_PLAYED',
      };
    case 'resolveDeckPick':
      // DECK_TOP_PICK (S06, Prophecy): PICK 2 в руку / ORDER порядок возврата
      return {
        result: await executor.executeResolvePendingEffect(
          { gameId, effectId: action.effectId, cardIds: action.cardIds },
          ctx,
        ),
        eventType: 'CARD_PLAYED',
      };
    case 'declinePending':
      return {
        result: await executor.executeDeclinePendingEffect(
          { gameId, effectId: action.effectId }, ctx,
        ),
        eventType: 'CARD_PLAYED',
      };
    case 'endTurn':
      // TURN_ENDED — как у человека в game-actions.resolver.endTurn и как
      // GameActionType в журнале; TURN_CHANGED не входит в enum → запись
      // бот-endTurn молча выпадала из eventsSince-catchup (и GAME_ENDED при
      // терминальном endTurn вместе с ней — ранний return в recordJournal).
      // Подписка turnChanged принимает оба имени (TURN_ENDED|TURN_CHANGED).
      return {
        result: await executor.executeEndTurn({ gameId } as any, ctx),
        eventType: 'TURN_ENDED',
      };
  }
}

@Injectable()
export class AiTurnService {
  private readonly logger = new Logger(AiTurnService.name);
  private static readonly MAX_STEPS = 40;

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
    @Optional() private readonly gameActionService?: GameActionService,
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

        const action = this.decision.decide(state, aiUserId);
        if (!action) return false;

        const ctx: ActionContext = { userId: aiUserId, gameId, currentState: state };
        const { result, eventType } = await this.dispatch(action, ctx);

        if (!result.success || !result.gameState) {
          this.logger.warn(`AI шаг «${action.kind}» не выполнен: ${result.error}`);
          return false;
        }
        // Страховка от зацикливания: каждый шаг должен двигать seq
        if (result.gameState.sequenceNumber <= state.sequenceNumber) {
          this.logger.warn(`AI шаг «${action.kind}» без прогресса seq — стоп`);
          return false;
        }

        await this.stateService.saveState(gameId, result.gameState);
        await this.scheduleCombatDeadline(gameId, eventType, result.gameState);
        await this.recordJournal(gameId, aiUserId, eventType, action, result.gameState);
        // Named-CUE публикация — best-effort ПОСЛЕ коммита: транзитный отказ
        // Redis/PubSub не должен прерывать дрейн (иначе VS_AI-матч виснет),
        // закоммиченный seq — источник истины; подписчики догонят eventsSince.
        // Отказ saveState наверху глотать НЕЛЬЗЯ — потеря персистентности.
        // Терминальный GAME_ENDED — ОТДЕЛЬНАЯ попытка: отказ публикации
        // самого действия не должен глотать терминальное событие.
        try {
          await this.subscription.publishGameUpdate(gameId, eventType, result.gameState);
        } catch (publishError) {
          this.logger.warn(
            `AI publish «${eventType}» для ${gameId} не доставлен (состояние закоммичено, seq=${result.gameState.sequenceNumber}): ${publishError}`,
          );
        }
        if (result.gameState.phase === GamePhase.GAME_OVER) {
          try {
            await this.subscription.publishGameUpdate(gameId, 'GAME_ENDED', result.gameState);
          } catch (publishError) {
            this.logger.warn(
              `AI publish «GAME_ENDED» для ${gameId} не доставлен (состояние закоммичено, seq=${result.gameState.sequenceNumber}): ${publishError}`,
            );
          }
        }

        return result.gameState.phase !== GamePhase.GAME_OVER;
      },
      { ttl: 10000, retryCount: 2, retryDelay: 150 },
    );
  }

  /**
   * GD-039 Sol6: боевые дедлайны для бота-инициатора — тот же контракт, что у
   * человека в game-actions.resolver. Атака бота → 30с окно защиты человека
   * (человек может отключиться: сервер финализирует бой CombatTimeoutService);
   * защита бота → окно ручного резолва; резолв → отмена расписаний.
   * Best-effort: дедлайн персистен в combatInfo.timeoutAt, transient-отказ
   * очереди чинится periodic recovery sweep — дрейн не прерываем.
   */
  private async scheduleCombatDeadline(gameId: string, eventType: string, state: any): Promise<void> {
    if (!this.combatTimeout) return;
    try {
      if (eventType === 'ATTACK_INITIATED') {
        const ci = state.metadata.combatInfo;
        const delayMs = ci?.timeoutAt
          ? Math.max(0, new Date(ci.timeoutAt).getTime() - Date.now())
          : DEFENSE_TIMEOUT_SECONDS * 1000;
        await this.combatTimeout.scheduleAutoResolve(
          gameId,
          Math.max(1, Math.ceil(delayMs / 1000)),
          state.sequenceNumber,
          'DEFENSE',
        );
      } else if (eventType === 'DEFENSE_PLAYED') {
        await this.combatTimeout.scheduleAutoResolve(
          gameId,
          RESOLVE_TIMEOUT_SECONDS,
          state.sequenceNumber,
          'RESOLVE',
        );
      } else if (eventType === 'COMBAT_RESOLVED') {
        await this.combatTimeout.cancelAutoResolve(gameId);
      }
    } catch (e) {
      this.logger.warn(`AI combat deadline для ${gameId} (${eventType}) не запланирован: ${e}`);
    }
  }

  /**
   * GD-039 Sol6: журнал действий бота для eventsSince-catchup человека —
   * без записей ход бота невидим реконнекту. Форма как у ручного пути
   * (game-actions.resolver.recordGameAction): metadata.input с instance-id
   * карт приватен боту — getEventsSince отдаёт input только владельцу
   * действия (playerId), человек получает только action. Лучший-усилие:
   * отказ журнала не роняет дрейн. GAME_ENDED — отдельной записью с
   * победителем, тем же seq (зеркало ручного пути), ОТДЕЛЬНОЙ best-effort
   * попыткой: отказ записи самого действия не должен глотать терминал.
   */
  private async recordJournal(
    gameId: string,
    aiUserId: string,
    eventType: string,
    action: AiAction,
    state: any,
  ): Promise<void> {
    if (!this.gameActionService) return;
    const type = GameActionType[eventType as keyof typeof GameActionType];
    if (!type) return; // unmapped named-CUE (STATE_UPDATED) не журналим — как у человека
    try {
      await this.gameActionService.recordAction({
        gameId,
        sequenceNumber: state.sequenceNumber,
        type,
        playerId: aiUserId,
        metadata: { action: `ai:${action.kind}`, input: JSON.parse(JSON.stringify(action)) },
      });
    } catch (e) {
      this.logger.warn(`AI journal для ${gameId} (${eventType}) не записан: ${e}`);
    }
    if (state.phase === GamePhase.GAME_OVER) {
      try {
        await this.gameActionService.recordAction({
          gameId,
          sequenceNumber: state.sequenceNumber,
          type: GameActionType.GAME_ENDED,
          playerId: aiUserId,
          metadata: { action: `ai:${action.kind}`, winnerId: state.metadata?.winnerId },
        });
      } catch (e) {
        this.logger.warn(`AI journal GAME_ENDED для ${gameId} не записан: ${e}`);
      }
    }
  }

  private async dispatch(
    action: AiAction,
    ctx: ActionContext,
  ): Promise<{ result: { success: boolean; gameState?: any; error?: string }; eventType: string }> {
    return dispatchAiAction(this.executor, action, ctx);
  }
}
