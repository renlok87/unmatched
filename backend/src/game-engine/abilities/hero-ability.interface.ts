/**
 * Hero Ability Interface
 *
 * Базовый интерфейс для обработчиков способностей героев.
 * Определяет контракт реализации уникальных способностей героев Unmatched.
 */

import type { GameState } from '../models/game-state.model';
import type { Fighter, Position } from '../models/fighter.model';
import type { Card } from '../models/card.model';
import type { CombatState, CombatModifier } from './hero-ability-registry';

/**
 * Контекст боя (расширенный)
 * Содержит информацию о текущем боевом столкновении
 */
export interface ExtendedCombatContext extends CombatState {
  readonly isBlindBoostAvailable?: boolean; // Для способности Daredevil
}

/**
 * Результат применения способности
 */
export interface AbilityResult {
  readonly success: boolean;
  readonly events: readonly AbilityEvent[];
  readonly modifiedState?: GameState;
}

/**
 * Событие способности
 */
export interface AbilityEvent {
  readonly type: AbilityEventType;
  readonly description: string;
  readonly sourceId: string;
  readonly playerId: string;
  readonly data?: Record<string, unknown>;
}

/**
 * Тип события способности
 */
export enum AbilityEventType {
  TURN_START_MOVE = 'TURN_START_MOVE',
  BLIND_BOOST = 'BLIND_BOOST',
  RANGE_ATTACK = 'RANGE_ATTACK',
  MODIFIER_APPLIED = 'MODIFIER_APPLIED',
}

/**
 * Базовый интерфейс обработчика способности героя (новый формат)
 * Все новые герои должны реализовывать этот интерфейс
 */
export interface IHeroAbilityHandler {
  /** ID героя (например, 'daredevil', 'ms-marvel') */
  readonly heroId: string;

  /** Название способности */
  readonly abilityName: string;

  /** Описание способности */
  readonly abilityDescription: string;

  /**
   * Вызывается в начале хода игрока
   * @param state Текущее состояние игры
   * @param playerId ID игрока, начинающего ход
   * @returns Обновлённое состояние игры
   */
  onTurnStart?(state: GameState, playerId: string): Promise<GameState>;

  /**
   * Вызывается в конце хода игрока
   * @param state Текущее состояние игры
   * @param playerId ID игрока, завершающего ход
   * @returns Обновлённое состояние игры
   */
  onTurnEnd?(state: GameState, playerId: string): Promise<GameState>;

  /**
   * Вызывается во время боя
   * Позволяет модифицировать боевые значения или применять специальные эффекты
   * @param state Текущее состояние игры
   * @param context Контекст боя
   * @returns Обновлённое состояние игры
   */
  onCombat?(state: GameState, context: ExtendedCombatContext): Promise<GameState>;

  /**
   * Проверяет, может ли боец атаковать на определённой дистанции
   * Используется для героев с расширенным радиусом атаки (например, Ms. Marvel)
   * @param attackerId ID атакующего бойца
   * @param defenderId ID защищающегося бойца
   * @param range Расстояние между бойцами
   * @returns true, если атака возможна на этой дистанции
   */
  canAttackAtRange?(attackerId: string, defenderId: string, range: number): boolean;

  /**
   * Получить модификаторы боя от способности героя
   * @param context Контекст боя
   * @param fighter Боец, к которому применяется модификатор
   * @param role Роль в бою (attacker/defender)
   * @returns Массив модификаторов
   */
  getCombatModifiers?(
    context: ExtendedCombatContext,
    fighter: Fighter,
    role: 'attacker' | 'defender',
  ): readonly CombatModifier[];
}

/**
 * Расширенный интерфейс для проверки условий способностей
 */
export interface AbilityChecker {
  /**
   * Проверить, может ли способность быть активирована
   * @param state Текущее состояние игры
   * @param playerId ID игрока
   * @param context Контекст (опционально)
   */
  canTrigger(state: GameState, playerId: string, context?: ExtendedCombatContext): boolean;
}
