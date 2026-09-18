import { Injectable, Logger } from '@nestjs/common';
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

/**
 * Оркестрация ходов ИИ-оппонента (VS_AI). Вызывается fire-and-forget из
 * game-actions.resolver.executeMutation ПОСЛЕ хода человека. Если игра VS_AI и
 * боту есть что делать (его ход / защита / отложенный эффект / резолв боя) —
 * крутит шаги: load → decide → executor.execute* → save → publish, под локом
 * на каждый шаг (оптимистик-лок saveState, как у человека). Реалтайм-апдейты
 * человек видит без F5.
 */
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
        await this.subscription.publishGameUpdate(gameId, eventType, result.gameState);

        if (result.gameState.phase === GamePhase.GAME_OVER) {
          await this.subscription.publishGameUpdate(gameId, 'GAME_ENDED', result.gameState);
          return false;
        }
        return true;
      },
      { ttl: 10000, retryCount: 2, retryDelay: 150 },
    );
  }

  private async dispatch(
    action: AiAction,
    ctx: ActionContext,
  ): Promise<{ result: { success: boolean; gameState?: any; error?: string }; eventType: string }> {
    const gameId = ctx.gameId;
    switch (action.kind) {
      case 'attack':
        return {
          result: await this.executor.executeAttack(
            { gameId, attackerId: action.attackerId, targetId: action.targetId, cardId: action.cardId },
            ctx,
          ),
          eventType: 'ATTACK_INITIATED',
        };
      case 'defense':
        return {
          result: await this.executor.executePlayDefense({ gameId, cardId: action.cardId }, ctx),
          eventType: 'DEFENSE_PLAYED',
        };
      case 'resolveCombat':
        return {
          result: await this.executor.executeResolveCombat({ gameId }, ctx),
          eventType: 'COMBAT_RESOLVED',
        };
      case 'maneuver':
        return {
          result: await this.executor.executeManeuver(
            { gameId, maneuverId: action.maneuverId, moves: action.moves, boostCardId: action.boostCardId },
            ctx,
          ),
          eventType: 'MANEUVER',
        };
      case 'beginManeuver':
        return {
          result: await this.executor.executeBeginManeuver(
            { gameId, expectedSequenceNumber: action.expectedSequenceNumber }, ctx,
          ),
          eventType: 'MANEUVER',
        };
      case 'discardToLimit':
        return {
          result: await this.executor.executeDiscardToLimit(
            { gameId, pendingId: action.pendingId, cardIds: action.cardIds }, ctx,
          ),
          eventType: 'CARD_DISCARDED',
        };
      case 'resolveChoose':
        return {
          result: await this.executor.executeResolvePendingEffect(
            { gameId, effectId: action.effectId, optionIndex: action.optionIndex },
            ctx,
          ),
          eventType: 'CARD_PLAYED',
        };
      case 'resolveMove':
        return {
          result: await this.executor.executeResolvePendingEffect(
            { gameId, effectId: action.effectId, fighterId: action.fighterId, x: action.x, y: action.y },
            ctx,
          ),
          eventType: 'CARD_PLAYED',
        };
      case 'endTurn':
        return {
          result: await this.executor.executeEndTurn({ gameId } as any, ctx),
          eventType: 'TURN_CHANGED',
        };
    }
  }
}
