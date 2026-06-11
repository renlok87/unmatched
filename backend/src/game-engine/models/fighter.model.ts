/**
 * Fighter Model
 *
 * Типы для бойцов (героев, миньонов, huge)
 */

/**
 * Тип бойца
 */
export enum FighterType {
  HERO = 'HERO',
  MINION = 'MINION',
  HUGE = 'HUGE',
}

/**
 * Позиция на доске
 */
export interface Position {
  readonly x: number;
  readonly y: number;
}

/**
 * Эффект на бойце
 */
export interface FighterEffect {
  readonly type: string;
  readonly value?: number;
  readonly duration?: 'permanent' | 'turn' | 'round';
  readonly expiresAt?: number;
  readonly source?: string;
}

/**
 * Боец на доске
 */
export interface Fighter {
  readonly id: string;
  readonly ownerId: string;
  readonly heroId: string;
  readonly name: string;
  readonly type: FighterType;
  readonly health: number;
  readonly maxHealth: number;
  readonly position: Position;
  readonly effects: readonly FighterEffect[];
  readonly hasSidekick: boolean;
  readonly sidekickIds?: readonly string[];
  readonly isDefeated?: boolean;
}

/**
 * Создаёт глубокую копию бойца с обновлёнными полями
 */
export function updateFighter<T extends Partial<Fighter>>(fighter: Fighter, updates: T): Fighter {
  return {
    ...fighter,
    ...updates,
    effects: updates.effects !== undefined ? [...updates.effects] : [...fighter.effects],
  };
}

/**
 * Создаёт новую позицию
 */
export function createPosition(x: number, y: number): Position {
  return { x, y };
}

/**
 * Проверяет, равны ли две позиции
 */
export function positionEqual(a: Position, b: Position): boolean {
  return a.x === b.x && a.y === b.y;
}

/**
 * Вычисляет расстояние между двумя позициями (Manhattan distance)
 */
export function positionDistance(a: Position, b: Position): number {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}
