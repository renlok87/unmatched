/**
 * Fighter Model
 *
 * Типы для бойцов (героев, миньонов, huge)
 */

// Только чистая функция; board-topology импортирует из models лишь типы —
// рантайм-цикла модулей нет
import { manhattanDistance as latticeManhattan } from '../engine/board-topology';

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
  /** Очки движения за одно перемещение (опционально — легаси-сейвы без поля) */
  readonly movement?: number;
  /** Тип атаки бойца: melee — только смежные цели, ranged — та же зона или смежная
   *  (опционально — легаси-сейвы без поля → melee через getFighterAttackType) */
  readonly attackType?: 'melee' | 'ranged';
  /** Слаг героя для HeroAbilityRegistry (handlers регистрируются по слагам
   *  'daredevil'/'ms-marvel', а heroId — Prisma cuid). Optional — легаси-сейвы
   *  без поля: способности у них не срабатывают (как и раньше). */
  readonly heroSlug?: string;
}

/**
 * Дефолтные очки движения (Hero.movement в Prisma default 2)
 */
export const DEFAULT_FIGHTER_MOVEMENT = 2;

/**
 * Очки движения бойца. Единственная точка дефолта:
 * легаси-сейвы/мусорные значения (0, null, NaN, строка) → DEFAULT_FIGHTER_MOVEMENT.
 */
export function getFighterMovement(f: Fighter): number {
  const m = Number(f.movement);
  return Number.isInteger(m) && m >= 1 ? m : DEFAULT_FIGHTER_MOVEMENT;
}

/**
 * Слаг героя для реестра способностей: 'Ms. Marvel' → 'ms-marvel',
 * 'King Arthur' → 'king-arthur'. Единственная точка нормализации имени.
 */
export function slugifyHeroName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * Канонический тип атаки в движке
 */
export type AttackType = 'melee' | 'ranged';

/**
 * Единый нормализатор типа атаки: данные БД/скрейпа хранят 'range',
 * движок использует 'ranged'; любой мусор (null, melee_range, число) → 'melee'.
 */
export function normalizeAttackType(v: unknown): AttackType {
  return v === 'ranged' || v === 'range' ? 'ranged' : 'melee';
}

/**
 * Тип атаки бойца. Единственная точка дефолта:
 * легаси-сейвы/отсутствие поля → 'melee' (поведение как до фикса).
 */
export function getFighterAttackType(f: Fighter): AttackType {
  return normalizeAttackType(f.attackType);
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
 * Вычисляет расстояние между двумя позициями (Manhattan distance решётки,
 * БЕЗ учёта доски). Не годится для смежности/дальности на топологических
 * досках — там используйте engine/board-topology (isAdjacent/boardDistance).
 */
export function positionDistance(a: Position, b: Position): number {
  return latticeManhattan(a, b);
}
