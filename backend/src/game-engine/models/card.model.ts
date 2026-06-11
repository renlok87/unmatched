/**
 * Card Model
 *
 * Типы для карт в игре Unmatched
 */

/**
 * Тип карты
 */
export enum CardType {
  ATTACK = 'ATTACK',
  DEFENSE = 'DEFENSE',
  SCHEME = 'SCHEME',
  UNIVERSAL = 'UNIVERSAL',
}

/**
 * Базовый интерфейс карты
 */
export interface Card {
  readonly id: string;
  readonly cardId: string;
  readonly name: string;
  readonly nameEn: string;
  readonly nameRu: string;
  readonly cardType: CardType;
  readonly attackValue?: number;
  readonly defenseValue?: number;
  readonly boostValue?: number;
  readonly effects?: readonly CardEffect[];
}

/**
 * Эффект карты
 */
export interface CardEffect {
  readonly id: string;
  readonly type: EffectType;
  readonly timing: EffectTiming;
  readonly target?: EffectTarget;
  readonly value?: number;
  readonly condition?: string;
}

/**
 * Тип эффекта
 */
export enum EffectType {
  MODIFY_ATTACK = 'MODIFY_ATTACK',
  MODIFY_DEFENSE = 'MODIFY_DEFENSE',
  DAMAGE = 'DAMAGE',
  HEAL = 'HEAL',
  MOVE = 'MOVE',
  PLACE = 'PLACE',
  DRAW_CARD = 'DRAW_CARD',
  DISCARD = 'DISCARD',
}

/**
 * Время применения эффекта
 */
export enum EffectTiming {
  BEFORE_COMBAT = 'BEFORE_COMBAT',
  DURING_COMBAT = 'DURING_COMBAT',
  AFTER_COMBAT = 'AFTER_COMBAT',
  ON_PLAY = 'ON_PLAY',
  ON_DISCARD = 'ON_DISCARD',
  TURN_START = 'TURN_START',
  TURN_END = 'TURN_END',
}

/**
 * Цель эффекта
 */
export enum EffectTarget {
  ATTACKER = 'ATTACKER',
  DEFENDER = 'DEFENDER',
  SELF = 'SELF',
  ALL_ENEMIES = 'ALL_ENEMIES',
  ALL_ALLIES = 'ALL_ALLIES',
}

/**
 * Карта в руке (с видимостью)
 */
export interface HandCard extends Card {
  readonly isVisible: boolean;
}

/**
 * Состояние колоды
 */
export interface DeckState {
  readonly cards: readonly Card[];
  readonly drawPile: readonly Card[];
  readonly topCard?: Card;
}

/**
 * Зона руки
 */
export interface HandZone {
  readonly cards: readonly HandCard[];
  readonly maxSize: number;
}
