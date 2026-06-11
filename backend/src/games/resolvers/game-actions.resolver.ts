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
import { GamePhase } from '../dto';
import {
  ManeuverDto,
  MoveFighterDto,
  AttackDto,
  PlayDefenseDto,
  ResolveCombatDto,
  EndTurnDto,
  PassDto,
  ToggleDoorDto,
  GameMutationResult,
} from '../dto/gameplay.dto';
import { BadRequestException, ConflictException } from '@nestjs/common';
import {
  GameInProgressGuard,
  GamePlayerGuard,
  ManeuverPhaseGuard,
  AttackPhaseGuard,
  CombatPhaseGuard,
  DefensePlayGuard,
  CombatResolveGuard,
} from '../guards';
import { GameActionExecutorService, ActionContext } from '../../game-engine/services/game-action-executor.service';

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
  ) {}

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
    return this.distributedLockService.withLockOptions(
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

          // Запланировать auto-resolve если требуется (для атаки)
          if (scheduleAutoResolve) {
            await this.combatTimeoutService.scheduleAutoResolve(
              dto.gameId,
              30,
              result.gameState!.sequenceNumber,
            );
          } else if (eventType === 'DEFENSE_PLAYED' || eventType === 'COMBAT_RESOLVED') {
            // Отменяем scheduled auto-resolve для защиты и разрешения боя
            await this.combatTimeoutService.cancelAutoResolve(dto.gameId);
          }

          // Публикуем обновление
          await this.gameSubscriptionService.publishGameUpdate(
            dto.gameId,
            eventType,
            result.gameState!,
          );

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
  }

  // ============================================
  // MANEUVER - Перемещение + розыгрыш карты
  // ============================================

  /**
   * Выполнить манёвр - переместить бойца по пути и сыграть карту эффектов
   * Доступно в фазе ACTION_MANEUVER только текущему игроку
   */
  @Mutation(() => GameMutationResult, { name: 'maneuver', description: 'Переместить бойца и сыграть карту эффектов' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ManeuverPhaseGuard)
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

  // ============================================
  // MOVE FIGHTER - Простое перемещение
  // ============================================

  /**
   * Переместить бойца на указанную клетку без игры карты
   * Доступно в фазе ACTION_MANEUVER только текущему игроку
   */
  @Mutation(() => GameMutationResult, { name: 'moveFighter', description: 'Переместить бойца на указанную клетку' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ManeuverPhaseGuard)
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
   * Доступно в фазе ACTION_ATTACK только текущему игроку
   * После атаки запускается 30-секундный таймер auto-resolve
   */
  @Mutation(() => GameMutationResult, { name: 'attack', description: 'Объявить атаку на соседнего бойца' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, AttackPhaseGuard)
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
   * Доступно в фазе ACTION_MANEUVER только текущему игроку
   */
  @Mutation(() => GameMutationResult, { name: 'endTurn', description: 'Завершить текущий ход' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ManeuverPhaseGuard)
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
   * Доступно в фазе ACTION_MANEUVER только текущему игроку
   */
  @Mutation(() => GameMutationResult, { name: 'pass', description: 'Сбросить карту и получить дополнительное действие' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ManeuverPhaseGuard)
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
   * Доступно в фазе ACTION_MANEUVER только текущему игроку
   * Специальная способность героя (например, Bjorn)
   */
  @Mutation(() => GameMutationResult, { name: 'toggleDoor', description: 'Открыть или закрыть дверь' })
  @UseGuards(GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, ManeuverPhaseGuard)
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
}
