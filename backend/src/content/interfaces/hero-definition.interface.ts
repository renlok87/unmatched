import type { CardDefinition } from './card-definition.interface';

/**
 * Hero URLs Interface
 * Image URLs from scraped data
 */
export interface HeroUrls {
  avatar: string;
  mini: string;
  cardCover: string;
}

/**
 * Hero Definition Interface
 * Defines a playable hero character in the game
 */
export interface HeroDefinition {
  id: string;
  name: string;
  nameEn?: string;
  nameRu?: string;
  health: number;
  movement: number;
  set: string;
  abilities: SpecialAbility[];
  deckCards: CardDefinition[];
  fighterType?: FighterType;
  sidekickCount?: number;
  sidekickHealth?: number;
  // Image URLs from scraped data
  urls?: HeroUrls;
}

/**
 * Special Ability Interface
 * Defines a hero's unique ability
 */
export interface SpecialAbility {
  id: string;
  name: string;
  text: string;
  trigger: AbilityTrigger;
}

/**
 * Ability Trigger Enum
 * Defines when an ability activates
 */
export enum AbilityTrigger {
  START_OF_TURN = 'start_of_turn',
  DURING_COMBAT = 'during_combat',
  PASSIVE = 'passive',
  WHEN_ATTACKED = 'when_attacked',
  WHEN_DEFENDING = 'when_defending',
  END_OF_TURN = 'end_of_turn',
}

/**
 * Fighter Type Enum
 */
export enum FighterType {
  HERO = 'hero',
  SIDEKICK = 'sidekick',
}
