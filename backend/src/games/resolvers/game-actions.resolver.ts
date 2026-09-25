/**
 * GameActionsResolver
 *
 * GraphQL Resolver для игровых мутаций в Unmatched.
 * Все мутации следуют единому паттерну:
 * 1. GqlAuthGuard → userId из JWT
 * 2. GameStatusGuard → game.status == IN_PROGRESS
 * 3. GamePlayerGuard → userId ∈ game.players
 * 4. PhaseGuard → проверка фазы игры
 * 5. DistributedLockService.withLock() → предотвращение race conditions
 * 6. GameActionExecutorService.executeAction() → выполнение действия
 * 7. GameStateService.saveState() → сохранение состояния
 * 8. GameSubscriptionService.publishUpdate() → уведомление подписчиков
 * 9. Return filtered state with metadata → возврат отфильтрованного состояния
 */

import { Resolver, Mutation, Args, Context } from '@nestjs/graphql';
import { UseGuards, Logger } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { GameStateService, GameState } from '../game-state.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { CombatTimeoutService } from '../services/combat-timeout.service';
import { GameActionService } from '../services/game-action.service';
import { GameActionType } from '../models/game-action.model';
import { GamePhase } from '../dto';
import {
  BeginManeuverDto,
  ManeuverDto,
  DiscardToLimitDto,
  MoveFighterDto,
  AttackDto,
  PlayDefenseDto,
  PlaySchemeDto,
  ResolvePendingEffectDto,
  DeclinePendingEffectDto,
  ResolveCombatDto,
  EndTurnDto,
  PassDto,
  ToggleDoorDto,
  SetStanceDto,
  GameMutationResult,
} from '../dto/gameplay.dto';
import { BadRequestException, ConflictException } from '@nestjs/common';
import {
  GameInProgressGuard,
  GamePlayerGuard,
  ActionPhaseGuard,
  CombatPhaseGuard,
  DefensePlayGuard,
  CombatResolveGuard,
} from '../guards';
import { GameActionExecutorService, ActionContext } from '../../game-engine/services/game-action-executor.service';
import { DEFENSE_TIMEOUT_SECONDS, RESOLVE_TIMEOUT_SECONDS } from '../../game-engine/models';
import { AiTurnService } from '../services/ai-turn.service';

/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-assignment */

/**
 * Помощник для получения userId из контекста
 */
function getUserId(context: any): string {
  const userId = context?.req?.user?.id || context?.user?.id;
  if (!userId) {
    throw new BadRequestException('User not authenticated');
  }
  return userId;
}

/**
 * Создаёт GameMutationResult из состояния
 */
function createMutationResult(state: GameState, sequenceNumber?: number): GameMutationResult {
  return {
    state: JSON.stringify(state),
    sequenceNumber: sequenceNumber ?? state.sequenceNumber,
    timestamp: new Date(),
    phase: state.phase,
    currentTurnPlayerId: state.currentTurnPlayerId,
    turnCount: state.turnCount,
  };
}

@Resolver(() => GameMutationResult)
export class GameActionsResolver {
  private readonly logger = new Logger(GameActionsResolver.name);

  constructor(
    private readonly gameStateService: GameStateService,
    private readonly gameSubscriptionService: GameSubscriptionService,
    private readonly distributedLockService: DistributedLockService,
    private readonly combatTimeoutService: CombatTimeoutService,
    private readonly actionExecutor: GameActionExecutorService,
    private readonly gameActionService: GameActionService,
    private readonly aiTurnService: AiTurnService,
  ) {}

  /**
   * Записать игровое действие в журнал GameAction (через BullMQ-очередь).
   * Запись best-effort: ошибка журнала НЕ должна ронять мутацию.
   */
  private async recordGameAction(
    gameId: string,
    userId: string,
    eventType: string,
    sequenceNumber: number,
    actionName: string,
    input: unknown,
  ): Promise<void> {
    const type = GameActionType[eventType as keyof typeof GameActionType];
    if (!type) {
      this.logger.warn(`No GameActionType for event ${eventType}, skip log`);
      return;
    }
    try {
      await this.gameActionService.recordAction({
        gameId,
        sequenceNumber,
        type,
        playerId: userId,
        metadata: { action: actionName, input: JSON.parse(JSON.stringify(input ?? {})) },
      });
    } catch (e) {
      this.logger.warn(`Failed to record game action ${eventType} for ${gameId}: ${e}`);
    }
  }

  /**
   * Обработка ошибок выполнения действия с логированием
   */
  private handleActionResult(result: { success: boolean; error?: string }, actionName: string): void {
    if (!result.success) {
      this.logger.warn(`${actionName} failed: ${result.error}`);
      throw new BadRequestException(result.error || `${actionName} failed`);
    }
  }

  /**
   * Общая логика выполнения мутации
   */
  private async executeMutation<T extends { gameId: string }>(
    dto: T,
    userId: string,
    actionName: string,
    executor: (context: ActionContext) => Promise<{ success: boolean; gameState?: GameState; error?: string }>,
    eventType: string,
    scheduleAutoResolve?: boolean,
  ): Promise<GameMutationResult> {
    const mutationResult = await this.distributedLockService.withLockOptions(
      `game:${dto.gameId}`,
      async () => {
        try {
          // Загружаем состояние
          const state = await this.gameStateService.loadState(dto.gameId);

          // Создаём контекст выполнения
          const actionContext: ActionContext = {
            userId,
            gameId: dto.gameId,
            currentState: state,
          };

          // Выполняем действие через GameActionExecutorService
          const result = await executor(actionContext);

          if (!result.success) {
            this.handleActionResult(result, actionName);
          }

          // Сохраняем состояние
          await this.gameStateService.saveState(dto.gameId, result.gameState!);

          // GD-026: планирование серверных дедлайнов боя.
          if (scheduleAutoResolve) {
            // Атака: дедлайн окна защиты персистен в combatInfo.timeoutAt —
            // джоба дёргается ровно к нему (не process-local таймер).
            const ci = result.gameState!.metadata.combatInfo;
            const delayMs = ci?.timeoutAt
              ? Math.max(0, new Date(ci.timeoutAt).getTime() - Date.now())
              : DEFENSE_TIMEOUT_SECONDS * 1000;
            await this.combatTimeoutService.scheduleAutoResolve(
              dto.gameId,
              Math.max(1, Math.ceil(delayMs / 1000)),
              result.gameState!.sequenceNumber,
              'DEFENSE',
            );
          } else if (eventType === 'DEFENSE_PLAYED') {
            // Защита сыграна: окно ручного резолва. Оба клиента могут
            // отключиться — сервер всё равно завершит бой (тот же
            // idempotent-путь executeResolveCombat).
            await this.combatTimeoutService.scheduleAutoResolve(
              dto.gameId,
              RESOLVE_TIMEOUT_SECONDS,
              result.gameState!.sequenceNumber,
              'RESOLVE',
            );
          } else if (eventType === 'COMBAT_RESOLVED') {
            // Бой разрешён вручную — отмена scheduled auto-resolve
            await this.combatTimeoutService.cancelAutoResolve(dto.gameId);
          }

          // Публикуем обновление
          await this.gameSubscriptionService.publishGameUpdate(
            dto.gameId,
            eventType,
            result.gameState!,
          );

          // Записываем действие в журнал GameAction (для eventsSince/catch-up)
          await this.recordGameAction(
            dto.gameId,
            userId,
            eventType,
            result.gameState!.sequenceNumber,
            actionName,
            dto,
          );
          if (result.gameState!.phase === GamePhase.GAME_OVER) {
            // Публикуем GAME_ENDED для подписки gameEnded (никто иначе не публикует)
            await this.gameSubscriptionService.publishGameUpdate(
              dto.gameId,
              'GAME_ENDED',
              result.gameState!,
            );
            await this.recordGameAction(
              dto.gameId,
              userId,
              'GAME_ENDED',
              result.gameState!.sequenceNumber,
              actionName,
              {
                winnerId:
                  (result.gameState! as any).winnerId ??
                  (result.gameState! as any).metadata?.winnerId,
              },
            );
          }

          // Фильтруем приватные данные
          const filteredState = this.gameStateService.filterPrivateData(result.gameState!, userId);

          this.logger.debug(`${actionName} succeeded for game ${dto.gameId} by user ${userId}`);

          return createMutationResult(filteredState);
        } catch (error) {
          if (error instanceof BadRequestException || error instanceof ConflictException) {
            throw error;
          }
          this.logger.error(`Unexpected error in ${actionName}: ${error}`);
          throw new BadRequestException(`Unexpected error during ${actionName}`);
        }
      },
      { ttl: 10000, retryCount: 1, retryDelay: 100 },
    );

    // VS_AI: после хода человека дать боту отыграть свои действия (fire-and-forget;
    // realtime-апдейты доходят через подписку). No-op для не-VS_AI и когда боту
    // нечего делать.
    void this.aiTurnService
      .maybeRunAiTurns(dto.gameId)
      .catch((e) => this.logger.warn(`AI turn error (${dto.gameId}): ${e}`));

    return mutationResult;
  }

  // ============================================
  // MANEUVER - Обязательный добор, затем выбор BOOST и движения
  // ============================================

  /**
   * Начать манёвр: добрать карту и зарезервировать одно действие.
   * Возвращённый pendingManeuver.id нужен для завершения после выбора движения.
   */
  @Mutation(() => GameMutationResult, { name: 'beginManeuver', description: 'Начать манёвр: добрать карту и потратить одно действие' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async beginManeuver(
    @Args('input') dto: BeginManeuverDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(dto, userId, 'beginManeuver',
      (ctx) => this.actionExecutor.executeBeginManeuver(dto, ctx), 'MANEUVER');
  }

  /** Завершить начатый манёвр; moves: [] оставляет всех бойцов на месте. */
  @Mutation(() => GameMutationResult, { name: 'maneuver', description: 'Завершить начатый манёвр: необязательные BOOST и перемещения без повторного добора' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async maneuver(
    @Args('input') dto: ManeuverDto,
    @Context() context: any,
    @CurrentUser() user: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'maneuver',
      (ctx) => this.actionExecutor.executeManeuver(dto, ctx),
      'MANEUVER',
    );
  }

  /** TURN_END belongs to the ending player until the exact excess is discarded. */
  @Mutation(() => GameMutationResult, { name: 'discardToLimit', description: 'Выбрать лишние карты для сброса в конце хода' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async discardToLimit(
    @Args('input') dto: DiscardToLimitDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(dto, userId, 'discardToLimit',
      (ctx) => this.actionExecutor.executeDiscardToLimit(dto, ctx), 'CARD_DISCARDED');
  }

  // ============================================
  // MOVE FIGHTER - Простое перемещение
  // ============================================

  /**
   * Совместимый endpoint отклоняет перемещение, обходящее обязательный добор.
   * Движение выполняется при завершении начатого манёвра.
   */
  @Mutation(() => GameMutationResult, { name: 'moveFighter', description: 'Прямое перемещение без манёвра запрещено', deprecationReason: 'Используйте beginManeuver, затем maneuver' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async moveFighter(
    @Args('input') dto: MoveFighterDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'moveFighter',
      (ctx) => this.actionExecutor.executeMoveFighter(dto, ctx),
      'FIGHTER_MOVED',
    );
  }

  // ============================================
  // ATTACK - Объявление атаки
  // ============================================

  /**
   * Объявить атаку на соседнего бойца с указанной картой
   * Доступно в любой action-фазе текущему игроку — атака может быть и первым
   * действием, и дважды за ход (экономика «2 действия за ход»)
   * После атаки запускается 30-секундный таймер auto-resolve
   */
  @Mutation(() => GameMutationResult, { name: 'attack', description: 'Объявить атаку на соседнего бойца (тратит 1 действие)' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 20, ttl: 60000 } })
  async attack(
    @Args('input') dto: AttackDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'attack',
      (ctx) => this.actionExecutor.executeAttack(dto, ctx),
      'ATTACK_INITIATED',
      true, // scheduleAutoResolve
    );
  }

  // ============================================
  // PLAY DEFENSE - Игра защиты
  // ============================================

  /**
   * Сыграть карту защиты в ответ на атаку
   * Доступно только защищающемуся игроку в фазе COMBAT
   * Отменяет auto-resolve таймер
   */
  @Mutation(() => GameMutationResult, { name: 'playDefense', description: 'Сыграть карту защиты в ответ на атаку' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, DefensePlayGuard)
  @Throttle({ default: { limit: 20, ttl: 60000 } })
  async playDefense(
    @Args('input') dto: PlayDefenseDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'playDefense',
      (ctx) => this.actionExecutor.executePlayDefense(dto, ctx),
      'DEFENSE_PLAYED',
    );
  }

  // ============================================
  // PLAY SCHEME - Розыгрыш scheme-карты
  // ============================================

  /**
   * Разыграть scheme-карту из руки текущего игрока
   * Доступно в любой action-фазе текущему игроку (экономика «2 действия за ход»)
   * Авто-эффекты применяются best-effort, карта всегда уходит в сброс
   */
  @Mutation(() => GameMutationResult, { name: 'playScheme', description: 'Разыграть scheme-карту из руки (тратит 1 действие)' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 20, ttl: 60000 } })
  async playScheme(
    @Args('input') dto: PlaySchemeDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'playScheme',
      (ctx) => this.actionExecutor.executePlayScheme(dto, ctx),
      'CARD_PLAYED',
    );
  }

  /**
   * Резолв отложенного эффекта карты (C2): выбор бойца/клетки для
   * MOVE/PLACE из metadata.pendingEffects. Действие не тратится.
   */
  @Mutation(() => GameMutationResult, {
    name: 'resolvePendingEffect',
    description: 'Выбор бойца/клетки для отложенного эффекта карты (MOVE/PLACE)',
  })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async resolvePendingEffect(
    @Args('input') dto: ResolvePendingEffectDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'resolvePendingEffect',
      (ctx) => this.actionExecutor.executeResolvePendingEffect(dto, ctx),
      'CARD_PLAYED',
    );
  }

  /**
   * GD-018 (ACC-008): отказ от OPTIONAL-выбора («You may …»). Только голова
   * очереди, только владелец, только optional — mandatory отклонить нельзя.
   */
  @Mutation(() => GameMutationResult, {
    name: 'declinePendingEffect',
    description: 'Отказаться от optional-выбора (только «You may …», только голова очереди)',
  })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async declinePendingEffect(
    @Args('input') dto: DeclinePendingEffectDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'declinePendingEffect',
      (ctx) => this.actionExecutor.executeDeclinePendingEffect(dto, ctx),
      'CARD_PLAYED',
    );
  }

  // ============================================
  // RESOLVE COMBAT - Разрешение боя
  // ============================================

  /**
   * Разрешить бой и нанести урон
   * Доступно в фазах COMBAT и COMBAT_RESOLVE участникам боя
   * Отменяет auto-resolve таймер
   */
  @Mutation(() => GameMutationResult, { name: 'resolveCombat', description: 'Разрешить бой и нанести урон' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, CombatResolveGuard)
  @Throttle({ default: { limit: 20, ttl: 60000 } })
  async resolveCombat(
    @Args('input') dto: ResolveCombatDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'resolveCombat',
      (ctx) => this.actionExecutor.executeResolveCombat(dto, ctx),
      'COMBAT_RESOLVED',
    );
  }

  // ============================================
  // END TURN - Конец хода
  // ============================================

  /**
   * Завершить текущий ход и передать управление следующему игроку
   * Доступно в фазах ACTION_MANEUVER и ACTION_ATTACK только текущему игроку
   * (можно завершить ход после манёвра, не объявляя атаку)
   */
  @Mutation(() => GameMutationResult, { name: 'endTurn', description: 'Завершить текущий ход' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async endTurn(
    @Args('input') dto: EndTurnDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'endTurn',
      (ctx) => this.actionExecutor.executeEndTurn(dto, ctx),
      'TURN_ENDED',
    );
  }

  // ============================================
  // PASS - Сброс карты + дополнительное действие
  // ============================================

  /**
   * Сбросить верхнюю карту колоды и выполнить дополнительное действие
   * Доступно в фазах ACTION_MANEUVER и ACTION_ATTACK только текущему игроку
   */
  @Mutation(() => GameMutationResult, { name: 'pass', description: 'Свободный пропуск действия запрещён правилами', deprecationReason: 'Выполните maneuver, attack или playScheme' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 20, ttl: 60000 } })
  async pass(@Args('input') dto: PassDto, @Context() context: any): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'pass',
      (ctx) => this.actionExecutor.executePass(dto, ctx),
      'CARD_PLAYED',
    );
  }

  // ============================================
  // TOGGLE DOOR - Открыть/закрыть дверь
  // ============================================

  /**
   * Открыть или закрыть дверь на указанной клетке
   * Доступно в фазах ACTION_MANEUVER и ACTION_ATTACK только текущему игроку
   * Специальная способность героя (например, Bjorn)
   */
  @Mutation(() => GameMutationResult, { name: 'toggleDoor', description: 'Открыть или закрыть дверь' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async toggleDoor(
    @Args('input') dto: ToggleDoorDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'toggleDoor',
      (ctx) => this.actionExecutor.executeToggleDoor(dto, ctx),
      'DOOR_TOGGLED',
    );
  }

  // ============================================
  // SET STANCE - Сменить стойку героя (STANCE)
  // ============================================

  /**
   * Сменить стойку героя (Alice big/small, Muhammad Ali float/sting и т.п.).
   * Доступно в action-фазах текущему игроку (выбор при размещении / начале хода
   * / «Change size»-карты). НЕ тратит действие (выбор стойки бесплатен).
   */
  @Mutation(() => GameMutationResult, {
    name: 'setStance',
    description: 'Сменить стойку героя (STANCE: Alice big/small, Muhammad Ali float/sting)',
  })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ActionPhaseGuard)
  @Throttle({ default: { limit: 30, ttl: 60000 } })
  async setStance(
    @Args('input') dto: SetStanceDto,
    @Context() context: any,
  ): Promise<GameMutationResult> {
    const userId = getUserId(context);
    return this.executeMutation(
      dto,
      userId,
      'setStance',
      (ctx) => this.actionExecutor.executeSetStance(dto, ctx),
      'SPECIAL_ABILITY',
    );
  }
}
