/**
 * Turn Management Service
 *
 * Управление прогрессией ходов, экономикой действий и фазами в Unmatched.
 * Отвечает за:
 * - Начало и конец хода игрока
 * - Отслеживание действий (actions)
 * - Пас и дополнительные действия
 * - Переход хода к следующему живому игроку
 * - Проверку условий окончания игры
 */

import { Injectable, Logger } from '@nestjs/common';
import { ContentService } from '../../content/content.service';
import type { HeroDefinition, AbilityTrigger } from '../../content/interfaces';
import type { GameState, GameStatePlayer, Fighter } from '../models';
import { GamePhase } from '../models';
import { HeroAbilityRegistry } from '../abilities/hero-ability-registry';
import type { GameEvent } from '../abilities/hero-ability-registry';

/**
 * Количество действий по умолчанию за ход
 */
const DEFAULT_ACTIONS_PER_TURN = 2;

/**
 * Метаданные хода игрока
 */
interface PlayerTurnMetadata {
  readonly actionsTaken: number;
  readonly hasPassed: boolean;
  readonly additionalActions?: number;
}

/**
 * Ключи для метаданных хода в GameState.metadata
 */
interface TurnMetadataKeys {
  ACTIONS: string;
  PASSED: string;
  ADDITIONAL: string;
}

const META_KEYS: TurnMetadataKeys = {
  ACTIONS: 'turn_actions',
  PASSED: 'turn_passed',
  ADDITIONAL: 'turn_additional',
};

/**
 * Результат начала хода
 */
export interface TurnStartResult {
  readonly state: GameState;
  readonly events: readonly GameEvent[];
  readonly cardsDrawn?: number;
}

/**
 * Результат конца хода
 */
export interface TurnEndResult {
  readonly state: GameState;
  readonly events: readonly GameEvent[];
  readonly gameOver?: boolean;
  readonly winnerId?: string;
}

/**
 * Результат паса
 */
export interface PassResult {
  readonly state: GameState;
  readonly discardedCard?: string;
  readonly additionalAction?: boolean;
}

@Injectable()
export class TurnManagementService {
  private readonly logger = new Logger(TurnManagementService.name);

  constructor(
    private readonly contentService: ContentService,
    private readonly abilityRegistry: HeroAbilityRegistry,
  ) {}

  /**
   * Начать ход игрока
   *
   * Устанавливает текущего игрока, переходит к фазе TURN_START,
   * применяет способности триггера start_of_turn, сбрасывает счётчики действий
   */
  async startTurn(state: GameState, playerId: string): Promise<TurnStartResult> {
    this.logger.debug(`Starting turn for player ${playerId} in game ${state.gameId}`);

    const player = state.players.find((p) => p.userId === playerId);
    if (!player) {
      throw new Error(`Player ${playerId} not found in game state`);
    }

    if (!player.isAlive) {
      throw new Error(`Player ${playerId} is not alive`);
    }

    const events: GameEvent[] = [];
    let cardsDrawn = 0;

    // Получаем определение героя для проверки способностей
    let heroDef: HeroDefinition | null = null;
    try {
      heroDef = await this.contentService.getHeroById(player.heroId);
    } catch {
      this.logger.warn(`Hero definition not found for ${player.heroId}`);
    }

    // Проверяем способность рисовать карту в начале хода
    if (heroDef && this.shouldDrawCardAtTurnStart(heroDef)) {
      // TODO: Реализовать вытягивание карты из колоды
      // const drawResult = await this.drawCard(state, playerId);
      // state = drawResult.state;
      // cardsDrawn = drawResult.count;
      this.logger.debug(`Player ${playerId} draws a card at turn start`);
      events.push({
        type: 'CARD_DRAWN',
        description: `${player.heroId} draws a card at turn start`,
        sourceId: playerId,
      });
    }

    // Применяем способности триггера start_of_turn
    const playerFighters = state.fighters.filter((f) => f.ownerId === playerId);
    for (const fighter of playerFighters) {
      const abilityEvents = this.abilityRegistry.triggerOnTurnStart(fighter.heroId, fighter);
      events.push(...abilityEvents);
    }

    // Создаём обновлённое состояние
    const newState: GameState = {
      ...state,
      phase: GamePhase.TURN_START,
      currentTurnPlayerId: playerId,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
        lastActionBy: playerId,
        // Сбрасываем счётчики действий для нового хода
        [META_KEYS.ACTIONS]: 0,
        [META_KEYS.PASSED]: false,
        [META_KEYS.ADDITIONAL]: 0,
      },
    };

    this.logger.debug(
      `Turn started for player ${playerId}, phase: ${GamePhase.TURN_START}, actions reset`,
    );

    return {
      state: newState,
      events,
      cardsDrawn,
    };
  }

  /**
   * Завершить ход игрока
   *
   * Проверяет условия окончания игры, находит следующего живого игрока,
   * применяет способности триггера end_of_turn, очищает временные модификаторы
   */
  async endTurn(state: GameState, playerId: string): Promise<TurnEndResult> {
    this.logger.debug(`Ending turn for player ${playerId} in game ${state.gameId}`);

    const player = state.players.find((p) => p.userId === playerId);
    if (!player) {
      throw new Error(`Player ${playerId} not found in game state`);
    }

    const events: GameEvent[] = [];

    // Проверяем условия окончания игры (все враги повержены)
    const enemies = state.players.filter((p) => p.isAlive && p.userId !== playerId);
    const playerFightersAlive = state.fighters.filter((f) => f.ownerId === playerId && f.health > 0);
    const enemyFightersAlive = state.fighters.filter(
      (f) => f.ownerId !== playerId && f.health > 0,
    );

    let gameOver = false;
    let winnerId: string | undefined;

    // Если все бойцы противника повержены
    if (enemyFightersAlive.length === 0 && playerFightersAlive.length > 0) {
      gameOver = true;
      winnerId = playerId;
      this.logger.debug(`Game over! Player ${playerId} wins!`);

      const finalState: GameState = {
        ...state,
        phase: GamePhase.TURN_END,
        sequenceNumber: state.sequenceNumber + 1,
        metadata: {
          ...state.metadata,
          lastActionAt: new Date(),
          lastActionBy: playerId,
        } as typeof state.metadata & Record<string, any>,
      };
      // Сохраняем gameOver и winnerId в metadata
      (finalState.metadata as Record<string, any>).gameOver = true;
      (finalState.metadata as Record<string, any>).winnerId = winnerId;

      return {
        state: finalState,
        events,
        gameOver: true,
        winnerId,
      };
    }

    // Если все бойцы текущего игрока повержены
    if (playerFightersAlive.length === 0) {
      // Проверяем, есть ли живые союзники (для режимов 2v2, FFA)
      const allies = state.players.filter(
        (p) => p.isAlive && p.userId !== playerId && p.userId !== enemies[0]?.userId,
      );

      if (allies.length === 0) {
        // Текущий игрок и его союзники повержены
        gameOver = true;
        winnerId = enemies[0]?.userId;
        this.logger.debug(`Game over! Player ${winnerId} wins!`);

        const finalState: GameState = {
          ...state,
          phase: GamePhase.TURN_END,
          sequenceNumber: state.sequenceNumber + 1,
          metadata: {
            ...state.metadata,
            lastActionAt: new Date(),
            lastActionBy: playerId,
          } as typeof state.metadata & Record<string, any>,
        };
        // Сохраняем gameOver и winnerId в metadata
        (finalState.metadata as Record<string, any>).gameOver = true;
        (finalState.metadata as Record<string, any>).winnerId = winnerId;

        return {
          state: finalState,
          events,
          gameOver: true,
          winnerId,
        };
      }
    }

    // Применяем способности триггера end_of_turn
    for (const fighter of playerFightersAlive) {
      const abilityEvents = this.abilityRegistry.triggerOnTurnEnd(fighter.heroId, fighter);
      events.push(...abilityEvents);
    }

    // Находим следующего игрока
    const nextPlayerId = this.getNextPlayer(state, playerId);

    // Очищаем временные модификаторы (истекшие в конце хода)
    const cleanedFighters = this.clearExpiredModifiers(state.fighters, 'turn');

    const newState: GameState = {
      ...state,
      phase: GamePhase.TURN_END,
      currentTurnPlayerId: nextPlayerId,
      fighters: cleanedFighters,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
        lastActionBy: playerId,
      },
    };

    this.logger.debug(`Turn ended. Next player: ${nextPlayerId}`);

    return {
      state: newState,
      events,
      gameOver: false,
    };
  }

  /**
   * Проверить, может ли игрок совершить действие
   *
   * Проверяет лимит действий за ход и флаг hasPassed
   */
  canTakeAction(state: GameState, playerId: string): boolean {
    // Проверяем, что это ход игрока
    if (state.currentTurnPlayerId !== playerId) {
      return false;
    }

    const metadata = state.metadata as Record<string, any>;
    const actionsTaken = (metadata[META_KEYS.ACTIONS] as number) || 0;
    const hasPassed = (metadata[META_KEYS.PASSED] as boolean) || false;
    const additionalActions = (metadata[META_KEYS.ADDITIONAL] as number) || 0;

    // Если игрок пасовал, больше не может действовать
    if (hasPassed) {
      return false;
    }

    // Проверяем лимит действий (базовый + дополнительные)
    const maxActions = DEFAULT_ACTIONS_PER_TURN + additionalActions;
    return actionsTaken < maxActions;
  }

  /**
   * Потратить действие
   *
   * Увеличивает счётчик actionsTaken и возвращает обновлённое состояние
   */
  async spendAction(state: GameState, playerId: string): Promise<GameState> {
    if (!this.canTakeAction(state, playerId)) {
      throw new Error(`Player ${playerId} cannot take action`);
    }

    const metadata = state.metadata as Record<string, any>;
    const actionsTaken = ((metadata[META_KEYS.ACTIONS] as number) || 0) + 1;

    this.logger.debug(
      `Player ${playerId} spends action (${actionsTaken}/${DEFAULT_ACTIONS_PER_TURN})`,
    );

    return {
      ...state,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
        lastActionBy: playerId,
        [META_KEYS.ACTIONS]: actionsTaken,
      },
    };
  }

  /**
   * Пас (отказ от дальнейших действий)
   *
   * Устанавливает hasPassed в true.
   * Опционально сбрасывает случайную карту для получения дополнительного действия.
   */
  async pass(state: GameState, playerId: string): Promise<PassResult> {
    if (state.currentTurnPlayerId !== playerId) {
      throw new Error(`Not ${playerId}'s turn`);
    }

    const metadata = state.metadata as Record<string, any>;
    const hasPassed = (metadata[META_KEYS.PASSED] as boolean) || false;

    if (hasPassed) {
      throw new Error(`Player ${playerId} has already passed`);
    }

    this.logger.debug(`Player ${playerId} passes`);

    let discardedCard: string | undefined;
    let additionalAction = false;

    // TODO: Реализовать сброс случайной карты для дополнительного действия
    // В Unmatched можно сбросить карту для получения дополнительного действия

    const newState: GameState = {
      ...state,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
        lastActionBy: playerId,
        [META_KEYS.PASSED]: true,
        ...(additionalAction
          ? {
              [META_KEYS.ADDITIONAL]:
                ((metadata[META_KEYS.ADDITIONAL] as number) || 0) + 1,
            }
          : {}),
      },
    };

    return {
      state: newState,
      discardedCard,
      additionalAction,
    };
  }

  /**
   * Получить текущего игрока
   *
   * Возвращает ID игрока, чей сейчас ход
   */
  getCurrentPlayer(state: GameState): string | null {
    return state.currentTurnPlayerId || null;
  }

  /**
   * Получить следующего игрока
   *
   * Находит следующего живого игрока в порядке хода
   */
  getNextPlayer(state: GameState, currentPlayerId?: string): string {
    const currentId = currentPlayerId || state.currentTurnPlayerId;
    const alivePlayers = state.players.filter((p) => p.isAlive);

    if (alivePlayers.length === 0) {
      throw new Error('No alive players in game');
    }

    const currentIndex = alivePlayers.findIndex((p) => p.userId === currentId);

    // Если текущий игрок не найден, возвращаем первого живого
    if (currentIndex === -1) {
      return alivePlayers[0].userId;
    }

    // Находим следующего живого игрока (циклически)
    const nextIndex = (currentIndex + 1) % alivePlayers.length;
    return alivePlayers[nextIndex].userId;
  }

  /**
   * Получить метаданные хода игрока
   *
   * Извлекает информацию о действиях и пасе из метаданных состояния
   */
  getPlayerTurnMetadata(state: GameState, playerId: string): PlayerTurnMetadata {
    const metadata = state.metadata as Record<string, any>;
    return {
      actionsTaken: (metadata[META_KEYS.ACTIONS] as number) || 0,
      hasPassed: (metadata[META_KEYS.PASSED] as boolean) || false,
      additionalActions: (metadata[META_KEYS.ADDITIONAL] as number) || 0,
    };
  }

  /**
   * Получить оставшееся количество действий
   */
  getRemainingActions(state: GameState, playerId: string): number {
    const turnMeta = this.getPlayerTurnMetadata(state, playerId);
    const maxActions = DEFAULT_ACTIONS_PER_TURN + (turnMeta.additionalActions || 0);
    return Math.max(0, maxActions - turnMeta.actionsTaken);
  }

  /**
   * Сбросить истекшие модификаторы у бойцов
   *
   * Очищает эффекты с указанной длительностью (turn, round)
   */
  private clearExpiredModifiers(
    fighters: readonly Fighter[],
    duration: 'turn' | 'round',
  ): Fighter[] {
    return fighters.map((fighter) => {
      if (!fighter.effects || fighter.effects.length === 0) {
        return fighter;
      }

      const currentSequence = Date.now(); // Используем timestamp как упрощение

      const validEffects = fighter.effects.filter(
        (effect) =>
          effect.duration !== duration ||
          (effect.expiresAt && effect.expiresAt > currentSequence),
      );

      if (validEffects.length === fighter.effects.length) {
        return fighter;
      }

      return {
        ...fighter,
        effects: validEffects,
      };
    });
  }

  /**
   * Проверить, должен ли герой вытянуть карту в начале хода
   *
   * Проверяет наличие способности с триггером START_OF_TURN
   */
  private shouldDrawCardAtTurnStart(hero: HeroDefinition): boolean {
    return hero.abilities.some(
      (ability) => ability.trigger === ('start_of_turn' as AbilityTrigger),
    );
  }

  /**
   * Перейти к фазе манёвра
   *
   * Вызывается после завершения фазы TURN_START
   */
  transitionToManeuver(state: GameState): GameState {
    return {
      ...state,
      phase: GamePhase.ACTION_MANEUVER,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
      },
    };
  }

  /**
   * Перейти к фазе атаки
   *
   * Вызывается когда игрок начинает атаку
   */
  transitionToAttack(state: GameState): GameState {
    return {
      ...state,
      phase: GamePhase.ACTION_ATTACK,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
      },
    };
  }

  /**
   * Перейти к фазе боя
   *
   * Вызывается когда атака инициирована и ожидается защита
   */
  transitionToCombat(state: GameState): GameState {
    return {
      ...state,
      phase: GamePhase.COMBAT,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
      },
    };
  }

  /**
   * Перейти к фазе разрешения боя
   *
   * Вызывается когда защита сыграна или таймаут истёк
   */
  transitionToCombatResolve(state: GameState): GameState {
    return {
      ...state,
      phase: GamePhase.COMBAT_RESOLVE,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
      },
    };
  }

  /**
   * Проверить окончена ли игра
   */
  isGameOver(state: GameState): boolean {
    const metadata = state.metadata as Record<string, any>;
    return (metadata.gameOver as boolean) || false;
  }

  /**
   * Получить победителя
   */
  getWinner(state: GameState): string | undefined {
    const metadata = state.metadata as Record<string, any>;
    return metadata.winnerId as string | undefined;
  }
}
