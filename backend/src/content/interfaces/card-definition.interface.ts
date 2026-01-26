/**
 * Card Definition Interface
 * Defines a playable card in the game
 */
export interface CardDefinition {
  id: string;
  title: string;
  type: CardType;
  value: number;
  boost: number;
  quantity: number;
  characterName: string;
  effects: CardEffect[];
}

/**
 * Card Effect Interface
 * Defines a card's special effects
 */
export interface CardEffect {
  id: string;
  timing: EffectTiming;
  text: string;
}

/**
 * Card Type Enum
 */
export enum CardType {
  ATTACK = 'attack',
  DEFENSE = 'defense',
  VERSATILE = 'versatile',
  SCHEME = 'scheme',
}

/**
 * Effect Timing Enum
 * Defines when an effect activates
 */
export enum EffectTiming {
  IMMEDIATELY = 'immediately',
  DURING_COMBAT = 'during_combat',
  AFTER_COMBAT = 'after_combat',
  START_OF_TURN = 'start_of_turn',
  END_OF_TURN = 'end_of_turn',
  WHEN_PLAYED = 'when_played',
  WHEN_ATTACKED = 'when_attacked',
  WHEN_DEFENDING = 'when_defending',
}
