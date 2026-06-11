/**
 * Game Action Executor Service
 *
 * Единая точка входа для выполнения всех игровых действий в Unmatched.
 * Инкапсулирует логику выполнения действий с валидацией и изменением состояния.
 *
 * Все действия следуют единому паттерну:
 * 1. Валидация через GameRulesValidator
 * 2. Выполнение через соответствующий engine service
 * 3. Возврат результата с обновлённым состоянием
 */

import { Injectable, Logger, BadRequestException } from '@nestjs/common';
import { MetricsService } from '../../metrics/metrics.service';
import type { GameState } from '../../games/game-state.service';
import { GamePhase } from '../../games/dto';
import { createEmptyBoardState } from '../models';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { MovementService } from '../engine/movement.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import {
  ManeuverDto,
  MoveFighterDto,
  AttackDto,
  PlayDefenseDto,
  ResolveCombatDto,
  EndTurnDto,
  PassDto,
  ToggleDoorDto,
} from '../../games/dto/gameplay.dto';

/**
 * Результат выполнения игрового действия
 */
export interface ActionResult {
  readonly success: boolean;
  readonly gameState?: GameState;
  readonly error?: string;
  readonly metadata?: {
    readonly action: string;
    readonly performedAt: Date;
    readonly performedBy: string;
    readonly sequenceNumber: number;
  };
}

/**
 * Контекст выполнения действия
 */
export interface ActionContext {
  readonly userId: string;
  readonly gameId: string;
  readonly currentState: GameState;
}

/**
 * Параметры создания начального состояния игры
 */
export interface InitialGameStateParams {
  readonly gameId: string;
  readonly players: readonly {
    readonly userId: string;
    readonly heroId: string;
    readonly health: number;
    readonly maxHealth: number;
  }[];
  readonly boardId: string;
}

/**
 * Карта состояния боя
 */
interface CombatState {
  readonly attackerId: string;
  readonly defenderId: string;
  readonly attackerCardId: string;
  readonly defenderCardId?: string;
  readonly attackValue: number;
  readonly defenseValue: number;
  readonly startedAt: Date;
  readonly timeoutAt?: Date;
}

@Injectable()
export class GameActionExecutorService {
  private readonly logger = new Logger(GameActionExecutorService.name);

  constructor(
    private readonly rulesValidator: GameRulesValidator,
    private readonly combatResolver: CombatResolverService,
    private readonly movementService: MovementService,
    private readonly valueModifier: ValueModifierService,
    private readonly adjacencyService: AdjacencyService,
    private readonly metrics: MetricsService,
  ) {}

  /**
   * Создаёт начальное состояние игры
   */
  async createInitialState(params: InitialGameStateParams): Promise<GameState> {
    const { gameId, players, boardId } = params;

    // Создаём начальное состояние
    const state: GameState = {
      gameId,
      sequenceNumber: 0,
      phase: GamePhase.TURN_START,
      turnCount: 1,
      currentTurnPlayerId: players[0].userId,

      // Игроки
      players: players.map((p) => ({
        userId: p.userId,
        heroId: p.heroId,
        health: p.health,
        maxHealth: p.maxHealth,
        fighterIds: [], // Заполняется при размещении бойцов
        isAlive: true,
      })),

      // Бойцы (пока нет)
      fighters: [],

      // Колоды
      decks: {},
      discardPiles: {},

      // Зоны ручек
      handZones: {},

      // Состояние доски - используем вспомогательную функцию
      boardState: createEmptyBoardState(20, 20),

      // Метаданные
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: 'system',
        version: 1,
      },
    };

    this.logger.debug(`Создано начальное состояние для игры ${gameId}`);
    return state;
  }

  /**
   * Выполнить манёвр (перемещение + розыгрыш карты)
   */
  async executeManeuver(
    dto: ManeuverDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    return this.metrics.measureServiceDuration('executeManeuver', 'GameActionExecutor', async () => {
      try {
        const { userId, currentState, gameId } = context;

        // Валидация с замером времени
        const validation = await this.metrics.measureValidation('maneuver', () =>
          this.rulesValidator.validateManeuver(
            currentState as any,
            dto.fighterId,
            dto.cardId,
            dto.path,
            userId,
          ),
        );

        if (!validation.valid) {
          this.metrics.incrementGameAction('maneuver', undefined, 'error');
          return {
            success: false,
            error: validation.error || 'Maneuver validation failed',
          };
        }

        // Выполняем перемещение
        const movementResult = await this.movementService.executeMovement(
          currentState as any,
          dto.fighterId,
          dto.path,
        );

        if (!movementResult.success) {
          this.metrics.incrementGameAction('maneuver', undefined, 'error');
          return {
            success: false,
            error: movementResult.error || 'Movement failed',
          };
        }

        // Применяем эффекты карты
        let newState = movementResult.nextState ?? currentState;
        newState = await this.valueModifier.applyCardEffects(
          newState as any,
          dto.cardId,
          dto.fighterId,
        ) as any;

        // Переход в фазу ACTION_ATTACK если ещё не там
        const nextPhase =
          newState.phase === GamePhase.ACTION_MANEUVER ? GamePhase.ACTION_ATTACK : newState.phase;

        newState = {
          ...newState,
          phase: nextPhase,
          sequenceNumber: newState.sequenceNumber + 1,
          metadata: {
            ...newState.metadata,
            lastActionAt: new Date(),
            lastActionBy: userId,
          },
        } as any;

        this.metrics.incrementGameAction('maneuver', undefined, 'success');

        return {
          success: true,
          gameState: newState as any,
          metadata: {
            action: 'maneuver',
            performedAt: new Date(),
            performedBy: userId,
            sequenceNumber: newState.sequenceNumber,
          },
        };
      } catch (error) {
        this.logger.error(
          `Ошибка при выполнении манёвра [gameId=${context.gameId}]: ${error}`,
          { gameId: context.gameId, userId: context.userId, dto },
        );
        this.metrics.incrementError('GameActionExecutor', 'executeManeuver', error instanceof Error ? error.name : 'unknown');
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });
  }

  /**
   * Выполнить простое перемещение бойца
   */
  async executeMoveFighter(
    dto: MoveFighterDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    try {
      const { userId, currentState } = context;

      // Валидация
      const validation = this.rulesValidator.validateMovement(
        currentState as any,
        dto.fighterId,
        { x: dto.x, y: dto.y },
        userId,
      );

      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'Movement validation failed',
        };
      }

      // Выполняем перемещение
      const path = [{ x: dto.x, y: dto.y }];
      const result = await this.movementService.executeMovement(
        currentState as any,
        dto.fighterId,
        path,
      );

      if (!result.success) {
        return {
          success: false,
          error: result.error || 'Movement failed',
        };
      }

      const newState = {
        ...result.nextState!,
        sequenceNumber: result.nextState!.sequenceNumber + 1,
        metadata: {
          ...result.nextState!.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
        },
      } as any;

      return {
        success: true,
        gameState: newState as any,
        metadata: {
          action: 'moveFighter',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при перемещении бойца: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Выполнить атаку
   */
  async executeAttack(
    dto: AttackDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    return this.metrics.measureServiceDuration('executeAttack', 'GameActionExecutor', async () => {
      try {
        const { userId, currentState, gameId } = context;

        // Валидация с замером времени
        const validation = await this.metrics.measureValidation('attack', () =>
          this.rulesValidator.validateAttackWithParams(
            currentState as any,
            dto.attackerId,
            dto.targetId,
            dto.cardId,
            userId,
          ),
        );

        if (!validation.valid) {
          this.metrics.incrementGameAction('attack', undefined, 'error');
          return {
            success: false,
            error: validation.error || 'Attack validation failed',
          };
        }

        // Проверяем смежность позиций
        const attacker = currentState.fighters.find((f) => f.id === dto.attackerId);
        const target = currentState.fighters.find((f) => f.id === dto.targetId);

        if (!attacker || !target) {
          this.metrics.incrementGameAction('attack', undefined, 'error');
          return { success: false, error: 'Attacker or target not found' };
        }

        const isAdjacent = await this.adjacencyService.isAdjacent(
          currentState as any,
          attacker.position,
          target.position,
        );

        if (!isAdjacent) {
          this.metrics.incrementGameAction('attack', undefined, 'error');
          return { success: false, error: 'Target is not adjacent to attacker' };
        }

        // Сохраняем состояние боя в metadata
        const combatState: CombatState = {
          attackerId: dto.attackerId,
          defenderId: target.ownerId,
          attackerCardId: dto.cardId,
          attackValue: this.getCardValue(currentState, dto.cardId),
          defenseValue: 0,
          startedAt: new Date(),
        };

        const newState: any = {
          ...currentState,
          phase: GamePhase.COMBAT,
          sequenceNumber: currentState.sequenceNumber + 1,
          metadata: {
            ...currentState.metadata,
            lastActionAt: new Date(),
            lastActionBy: userId,
            combatInfo: combatState,
          },
        };

        this.metrics.incrementGameAction('attack', undefined, 'success');

        return {
          success: true,
          gameState: newState,
          metadata: {
            action: 'attack',
            performedAt: new Date(),
            performedBy: userId,
            sequenceNumber: newState.sequenceNumber,
          },
        };
      } catch (error) {
        this.logger.error(
          `Ошибка при выполнении атаки [gameId=${context.gameId}]: ${error}`,
          { gameId: context.gameId, userId: context.userId, dto },
        );
        this.metrics.incrementError('GameActionExecutor', 'executeAttack', error instanceof Error ? error.name : 'unknown');
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });
  }

  /**
   * Выполнить защиту
   */
  async executePlayDefense(
    dto: PlayDefenseDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    try {
      const { userId, currentState } = context;

      // Проверяем фазу
      if (currentState.phase !== GamePhase.COMBAT) {
        return { success: false, error: 'Not in combat phase' };
      }

      // Проверяем, что пользователь - защищающийся
      const combatInfo = (currentState.metadata as any).combatInfo as CombatState | undefined;
      if (!combatInfo) {
        return { success: false, error: 'No combat in progress' };
      }

      if (combatInfo.defenderId !== userId) {
        return { success: false, error: 'Only defender can play defense' };
      }

      // Валидация карты защиты
      const validation = this.rulesValidator.validateDefense(
        currentState as any,
        dto.cardId,
        userId,
      );

      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'Defense validation failed',
        };
      }

      // Обновляем состояние боя
      const updatedCombatInfo: CombatState = {
        ...combatInfo,
        defenderCardId: dto.cardId,
        defenseValue: this.getCardValue(currentState, dto.cardId),
      };

      const newState: GameState = {
        ...currentState,
        phase: 'COMBAT_RESOLVE' as GamePhase,
        sequenceNumber: currentState.sequenceNumber + 1,
        metadata: {
          ...currentState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
          combatInfo: updatedCombatInfo,
        } as any,
      };

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'playDefense',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при игре защиты: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Разрешить бой
   */
  async executeResolveCombat(
    dto: ResolveCombatDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    return this.metrics.measureServiceDuration('executeResolveCombat', 'GameActionExecutor', async () => {
      try {
        const { userId, currentState, gameId } = context;

        // Проверяем фазу
        if (currentState.phase !== GamePhase.COMBAT && currentState.phase !== GamePhase.COMBAT_RESOLVE) {
          this.metrics.incrementGameAction('resolveCombat', undefined, 'error');
          return { success: false, error: 'Not in combat phase' };
        }

        const combatInfo = (currentState.metadata as any).combatInfo as CombatState | undefined;
        if (!combatInfo) {
          this.metrics.incrementGameAction('resolveCombat', undefined, 'error');
          return { success: false, error: 'No combat in progress' };
        }

        // Вычисляем урон
        const attacker = currentState.fighters.find((f) => f.id === combatInfo.attackerId);
        const defenderFighter = currentState.fighters.find((f) => f.ownerId === combatInfo.defenderId);

        if (!attacker || !defenderFighter) {
          this.metrics.incrementGameAction('resolveCombat', undefined, 'error');
          return { success: false, error: 'Combat participants not found' };
        }

        // Разрешаем бой через CombatResolverService с метриками
        const combatResult = await this.metrics.measureCombat(
          attacker.heroId,
          defenderFighter.heroId,
          () => this.combatResolver.resolveCombat(
            currentState as any,
            combatInfo.attackerId,
            defenderFighter.id,
            combatInfo.attackerCardId,
            combatInfo.defenderCardId,
          ),
        );

        // Получаем урон из результата
        const attackerDamage = (combatResult as any).attackerDamage ?? 0;
        const defenderDamage = (combatResult as any).defenderDamage ?? 0;

        // Применяем урон
        let updatedFighters = [...currentState.fighters];
        updatedFighters = updatedFighters.map((f) => {
          if (f.id === combatInfo.attackerId && attackerDamage > 0) {
            return { ...f, health: Math.max(0, f.health - attackerDamage) };
          }
          if (f.id === defenderFighter.id && defenderDamage > 0) {
            return { ...f, health: Math.max(0, f.health - defenderDamage) };
          }
          return f;
        });

        // Проверяем условия победы/поражения
        const updatedPlayers = currentState.players.map((p) => {
          const playerFighters = updatedFighters.filter((f) => f.ownerId === p.userId);
          const hasAliveFighters = playerFighters.some((f) => f.health > 0);
          return {
            ...p,
            isAlive: hasAliveFighters,
          };
        });

        const alivePlayers = updatedPlayers.filter((p) => p.isAlive);
        const gameEnded = alivePlayers.length <= 1;

        let nextPhase = GamePhase.ACTION_MANEUVER;
        if (gameEnded) {
          nextPhase = GamePhase.GAME_OVER;
        }

        const newState: any = {
          ...currentState,
          phase: nextPhase,
          sequenceNumber: currentState.sequenceNumber + 1,
          fighters: updatedFighters,
          players: updatedPlayers,
          metadata: {
            ...currentState.metadata,
            lastActionAt: new Date(),
            lastActionBy: userId,
            combatInfo: undefined,
            ...(gameEnded ? { winnerId: alivePlayers[0]?.userId } : {}),
          } as any,
        };

        this.metrics.incrementGameAction('resolveCombat', undefined, 'success');

        return {
          success: true,
          gameState: newState,
          metadata: {
            action: 'resolveCombat',
            performedAt: new Date(),
            performedBy: userId,
            sequenceNumber: newState.sequenceNumber,
          },
        };
      } catch (error) {
        this.logger.error(
          `Ошибка при разрешении боя [gameId=${context.gameId}]: ${error}`,
          { gameId: context.gameId, userId: context.userId, dto },
        );
        this.metrics.incrementError('GameActionExecutor', 'executeResolveCombat', error instanceof Error ? error.name : 'unknown');
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });
  }

  /**
   * Завершить ход
   */
  async executeEndTurn(
    dto: EndTurnDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    try {
      const { userId, currentState } = context;

      // Валидация
      const validation = this.rulesValidator.validateEndTurn(currentState as any, userId);
      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'End turn validation failed',
        };
      }

      // Находим следующего живого игрока
      const currentPlayerIndex = currentState.players.findIndex(
        (p) => p.userId === currentState.currentTurnPlayerId,
      );

      let nextPlayerIndex = (currentPlayerIndex + 1) % currentState.players.length;
      let attempts = 0;

      while (!currentState.players[nextPlayerIndex].isAlive && attempts < currentState.players.length) {
        nextPlayerIndex = (nextPlayerIndex + 1) % currentState.players.length;
        attempts++;
      }

      const nextPlayerId = currentState.players[nextPlayerIndex].userId;
      const isSamePlayer = nextPlayerId === currentState.currentTurnPlayerId;

      const newState: any = {
        ...currentState,
        phase: GamePhase.TURN_START,
        currentTurnPlayerId: nextPlayerId,
        turnCount: isSamePlayer ? currentState.turnCount : currentState.turnCount + 1,
        sequenceNumber: currentState.sequenceNumber + 1,
        metadata: {
          ...currentState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
        },
      };

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'endTurn',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при завершении хода: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Выполнить pass (сброс карты + дополнительное действие)
   */
  async executePass(
    dto: PassDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    try {
      const { userId, currentState } = context;

      // Валидация
      const validation = this.rulesValidator.validatePass(currentState as any, userId);
      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'Pass validation failed',
        };
      }

      // Сбрасываем верхнюю карту колоды (упрощённо - без реальной логики колоды)
      // TODO: Интегрировать с реальной логикой колоды

      const newState: GameState = {
        ...currentState,
        sequenceNumber: currentState.sequenceNumber + 1,
        metadata: {
          ...currentState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
          passCount: ((currentState.metadata as any).passCount || 0) + 1,
        } as any,
      };

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'pass',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при выполнении pass: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Переключить дверь (специальная способность Bjorn)
   */
  async executeToggleDoor(
    dto: ToggleDoorDto,
    context: ActionContext,
  ): Promise<ActionResult> {
    try {
      const { userId, currentState } = context;

      // Валидация
      const validation = this.rulesValidator.validateToggleDoor(
        currentState as any,
        dto.x,
        dto.y,
        userId,
      );

      if (!validation.valid) {
        return {
          success: false,
          error: validation.error || 'Toggle door validation failed',
        };
      }

      const doorKey = `${dto.x}:${dto.y}`;
      const currentOpen = currentState.boardState.doors?.[doorKey] ?? false;

      const newState: GameState = {
        ...currentState,
        sequenceNumber: currentState.sequenceNumber + 1,
        boardState: {
          ...currentState.boardState,
          doors: {
            ...currentState.boardState.doors,
            [doorKey]: !currentOpen,
          },
        },
        metadata: {
          ...currentState.metadata,
          lastActionAt: new Date(),
          lastActionBy: userId,
        },
      };

      return {
        success: true,
        gameState: newState,
        metadata: {
          action: 'toggleDoor',
          performedAt: new Date(),
          performedBy: userId,
          sequenceNumber: newState.sequenceNumber,
        },
      };
    } catch (error) {
      this.logger.error(`Ошибка при переключении двери: ${error}`);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Получить значение карты из состояния
   * TODO: Интегрировать с реальной логикой карт
   */
  private getCardValue(state: GameState, cardId: string): number {
    // Заглушка - в будущем получать из состояния
    return 3;
  }
}
