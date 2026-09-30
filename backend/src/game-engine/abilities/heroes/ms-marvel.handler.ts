/**
 * Ms. Marvel Hero Ability Handler
 *
 * Обработчик способности Ms. Marvel: "Stretchy"
 * 1. В начале хода: может переместиться на 1 клетку
 * 2. Может атаковать с расстояния до 2 клеток (игнорируя зоны)
 */

import { Injectable, Logger } from '@nestjs/common';
import type { GameState } from '../../models/game-state.model';
import type { Fighter, Position } from '../../models/fighter.model';
import { positionEqual } from '../../models/fighter.model';
import {
  boardDistance,
  hasTopology,
  neighbours,
  orthogonalPositions,
  ORTHOGONAL_WENS,
} from '../../engine/board-topology';
import { isCellPassable } from '../../movement/traversal';
import {
  IHeroAbilityHandler,
  ExtendedCombatContext,
  AbilityChecker,
} from '../hero-ability.interface';

/**
 * Расширенный радиус атаки Ms. Marvel
 */
const MS_MARVEL_EXTENDED_RANGE = 2;

/**
 * Базовый радиус атаки в Unmatched
 */
const DEFAULT_ATTACK_RANGE = 1;

/**
 * Дополнительное перемещение в начале хода
 */
const TURN_START_MOVE_BONUS = 1;

/**
 * Результат перемещения в начале хода
 */
export interface TurnStartMoveResult {
  readonly success: boolean;
  readonly fighterId: string;
  readonly fromPosition: Position;
  readonly toPosition: Position;
  readonly path: readonly Position[];
}

/**
 * Обработчик способности Ms. Marvel
 */
@Injectable()
export class MsMarvelHandler implements IHeroAbilityHandler, AbilityChecker {
  private readonly logger = new Logger(MsMarvelHandler.name);

  readonly heroId = 'ms-marvel';
  readonly abilityName = 'Stretchy';
  readonly abilityDescription =
    'В начале хода: может переместиться на 1 клетку. Может атаковать с расстояния до 2 клеток (игнорируя зоны).';

  /**
   * Получить расширенный радиус атаки
   * @returns Максимальное расстояние атаки
   */
  getAttackRange(): number {
    return MS_MARVEL_EXTENDED_RANGE;
  }

  /**
   * Проверить, может ли Ms. Marvel атаковать на указанной дистанции
   * @param attackerId ID атакующего бойца
   * @param defenderId ID защищающегося бойца
   * @param range Расстояние между бойцами
   * @returns true, если атака возможна
   */
  canAttackAtRange(attackerId: string, defenderId: string, range: number): boolean {
    // Ms. Marvel может атаковать на расстоянии до 2 клеток
    // Проверка героя происходит на более высоком уровне
    return range <= MS_MARVEL_EXTENDED_RANGE;
  }

  /**
   * Проверить, может ли быть активирована способность
   * @param state Состояние игры
   * @param playerId ID игрока
   * @param context Опциональный контекст
   * @returns true, если условие выполнено
   */
  canTrigger(state: GameState, playerId: string, context?: unknown): boolean {
    const player = state.players.find((p) => p.userId === playerId);
    if (!player || player.heroId !== this.heroId) {
      return false;
    }

    // Проверяем, что герой жив
    if (!player.isAlive) {
      return false;
    }

    // Находим бойца Ms. Marvel
    const fighter = state.fighters.find((f) => f.ownerId === playerId && f.heroId === this.heroId);
    if (!fighter) {
      return false;
    }

    return true;
  }

  /**
   * Проверить, может ли Ms. Marvel атаковать конкретную цель
   * @param state Состояние игры
   * @param attackerId ID атакующего
   * @param defenderId ID цели
   * @returns true, если атака возможна
   */
  canAttackTarget(state: GameState, attackerId: string, defenderId: string): boolean {
    const attacker = state.fighters.find((f) => f.id === attackerId);
    const defender = state.fighters.find((f) => f.id === defenderId);

    if (!attacker || !defender) {
      return false;
    }

    // Проверяем, что атакующий - Ms. Marvel
    if (attacker.heroId !== this.heroId) {
      return false;
    }

    // Дистанция в пространствах: сетка — манхэттен, топология — по линиям
    const distance = boardDistance(state.boardState, attacker.position, defender.position);
    return this.canAttackAtRange(attackerId, defenderId, distance);
  }

  /**
   * Выполнить перемещение в начале хода
   * @param state Текущее состояние игры
   * @param playerId ID игрока
   * @param targetPosition Целевая позиция
   * @returns Обновлённое состояние игры
   */
  async executeTurnStartMove(
    state: GameState,
    playerId: string,
    targetPosition: Position,
  ): Promise<GameState> {
    if (!this.canTrigger(state, playerId)) {
      this.logger.warn(`Ms. Marvel turn start move cannot be triggered for player ${playerId}`);
      return state;
    }

    // Находим бойца Ms. Marvel
    const fighter = state.fighters.find((f) => f.ownerId === playerId && f.heroId === this.heroId);
    if (!fighter) {
      this.logger.warn(`Ms. Marvel fighter not found for player ${playerId}`);
      return state;
    }

    // Проверяем дистанцию (только 1 клетка; сетка — манхэттен, топология — по линиям)
    const distance = boardDistance(state.boardState, fighter.position, targetPosition);
    if (distance > TURN_START_MOVE_BONUS) {
      this.logger.warn(
        `Ms. Marvel can only move ${TURN_START_MOVE_BONUS} space at turn start, requested ${distance}`,
      );
      return state;
    }

    // Создаём обновлённого бойца с новой позицией
    const updatedFighter = {
      ...fighter,
      position: targetPosition,
    };

    // Создаём обновлённое состояние
    const updatedFighters = state.fighters.map((f) =>
      f.id === fighter.id ? updatedFighter : f,
    );

    const newState: GameState = {
      ...state,
      fighters: updatedFighters,
    };

    this.logger.log(
      `Ms. Marvel (${playerId}) moved from ${fighter.position.x},${fighter.position.y} ` +
        `to ${targetPosition.x},${targetPosition.y} at turn start`,
    );

    return newState;
  }

  /**
   * Получить доступные позиции для перемещения в начале хода
   * @param state Состояние игры
   * @param playerId ID игрока
   * @returns Массив доступных позиций
   */
  getAvailableTurnStartPositions(state: GameState, playerId: string): Position[] {
    const fighter = state.fighters.find((f) => f.ownerId === playerId && f.heroId === this.heroId);
    if (!fighter) {
      return [];
    }

    const positions: Position[] = [];

    // Топологическая доска: соседи — связанные линией пространства;
    // проходимые и свободные от бойцов
    if (hasTopology(state.boardState)) {
      return neighbours(state.boardState, fighter.position).filter(
        (pos) =>
          isCellPassable(state.boardState.cells[pos.y]?.[pos.x]) &&
          !state.fighters.some((f) => positionEqual(f.position, pos)),
      );
    }

    // 4 соседние клетки (без диагоналей для Unmatched)
    const adjacentPositions: Position[] = orthogonalPositions(fighter.position, ORTHOGONAL_WENS);

    // Фильтруем позиции с учётом границ доски и препятствий
    // (здесь упрощённая версия - полная проверка должна учитывать состояние доски)
    for (const pos of adjacentPositions) {
      if (this.isValidPosition(state, pos)) {
        positions.push(pos);
      }
    }

    return positions;
  }

  /**
   * Проверить, является ли позиция валидной
   * @param state Состояние игры
   * @param position Позиция для проверки
   * @returns true, если позиция валидна
   */
  private isValidPosition(state: GameState, position: Position): boolean {
    // Проверка границ (предполагаем стандартную доску 6x6)
    const BOARD_SIZE = 6;
    if (position.x < 0 || position.x >= BOARD_SIZE || position.y < 0 || position.y >= BOARD_SIZE) {
      return false;
    }

    // Проверка на наличие других бойцов
    const occupied = state.fighters.some((f) => positionEqual(f.position, position));
    if (occupied) {
      return false;
    }

    // TODO: Добавить проверку препятствий и закрытых дверей
    // Это требует интеграции с BoardState

    return true;
  }

  /**
   * Вызывается в начале хода игрока
   * Ms. Marvel может переместиться на 1 клетку
   * @param state Состояние игры
   * @param playerId ID игрока
   * @returns Обновлённое состояние (или текущее, если перемещение не выполнено)
   */
  async onTurnStart(state: GameState, playerId: string): Promise<GameState> {
    // Способность активируется через отдельный mutation
    // Этот метод зарезервирован для автоматического применения
    return state;
  }

  /**
   * Вызывается во время боя
   * Ms. Marvel игнорирует зоны при атаке
   * @param state Состояние игры
   * @param context Контекст боя
   * @returns Обновлённое состояние
   */
  async onCombat(state: GameState, context: ExtendedCombatContext): Promise<GameState> {
    // Радиус атаки проверяется в canAttackAtRange
    return state;
  }

  /**
   * Получить описание способности
   * @returns Описание способности
   */
  getAbilityDescription(): string {
    return this.abilityDescription;
  }

  /**
   * Получить подробное описание механики атаки
   * @returns Описание механики атаки
   */
  getAttackMechanicsDescription(): string {
    return `Ms. Marvel может атаковать бойцов на расстоянии до ${MS_MARVEL_EXTENDED_RANGE} клеток, ` +
      `игнорируя правила зон. Обычные герои могут атаковать только соседнюю клетку.`;
  }
}

/**
 * Экспорт обработчика как singleton для использования в registry
 */
export const msMarvelHandler = new MsMarvelHandler();
