// ============================================================
// CORE TYPES FOR UNMATCHED DIGITAL GAME
// ============================================================

// ------------------------------------------------------------
// Card Types
// ------------------------------------------------------------

export enum CardType {
  ATTACK = 'attack',
  DEFENSE = 'defense',
  VERSATILE = 'versatile',
  SCHEME = 'scheme',
}

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

// ------------------------------------------------------------
// Card Interfaces
// ------------------------------------------------------------

export interface CardDefinition {
  id: string;
  title: string;
  type: CardType;
  value: number;        // 0-6 base value
  boost: number;        // 0-3 boost value
  quantity: number;     // Number of copies in deck
  effects: CardEffect[];
  characterName: string;
  imageUrl?: string;    // URL изображения карты
  imageUrlRu?: string; // URL изображения карты (русская версия)
}

export interface CardEffect {
  id: string;
  timing: EffectTiming;
  text: string;         // Human-readable description
}

export interface CardInstance {
  id: string;
  definition: CardDefinition;
  ownerId: string;      // Player/fighter ID
  instanceIndex: number;
  boostValue?: number;  // When blind boosted
  isBoosted?: boolean;  // Track if boost was applied
  isFaceDown?: boolean; // For attack cards
}

// ------------------------------------------------------------
// Fighter Types
// ------------------------------------------------------------

export enum FighterType {
  HERO = 'hero',
  SIDEKICK = 'sidekick',
}

export interface HeroDefinition {
  id: string;
  name: string;
  health: number;
  movement: number;
  abilities: SpecialAbility[];
  deckCards: CardDefinition[];
  sidekickCount?: number;
  sidekickHealth?: number;
  set: string;          // Which expansion set
  imageUrl?: string;     // URL изображения героя (card back)
  avatarUrl?: string;    // URL аватара героя (mini)
}

export interface SpecialAbility {
  id: string;
  name: string;
  text: string;
  trigger: AbilityTrigger;
}

export enum AbilityTrigger {
  START_OF_TURN = 'start_of_turn',
  DURING_COMBAT = 'during_combat',
  PASSIVE = 'passive',
  WHEN_ATTACKED = 'when_attacked',
  WHEN_DEFENDING = 'when_defending',
  END_OF_TURN = 'end_of_turn',
}

export interface Fighter {
  id: string;
  definitionId: string;  // Reference to HeroDefinition
  type: FighterType;
  health: number;
  maxHealth: number;
  position: Position;
  ownerId: string;       // Player ID
  isDefeated: boolean;
  avatarUrl?: string;    // URL изображения бойца (mini)
}

export interface FighterModifier {
  type: 'damage_boost' | 'damage_reduction' | 'movement_bonus' | 'range_bonus';
  value: number;
  duration: 'permanent' | 'turn' | 'combat' | 'until_start_of_next_turn';
  expiresAtTurn?: number;
}

// ------------------------------------------------------------
// Board Types
// ------------------------------------------------------------

export interface Position {
  x: number;
  y: number;
}

export interface BoardSpace {
  position: Position;
  zones: Zone[];         // Color zones (typically 1-2 per space)
  isObstacle?: boolean;
  startingPositions?: Record<string, Position>; // player ID -> position
}

export type Zone =
  | 'blue'
  | 'green'
  | 'yellow'
  | 'red'
  | 'purple'
  | 'brown'
  | 'gray'
  | 'orange'
  | 'pink'
  | 'white'
  | 'gold'
  | 'beige';

export interface BoardDefinition {
  id: string;
  name: string;
  width: number;
  height: number;
  spaces: BoardSpace[];
  recommendedPlayers: number;
  imageUrl?: string;     // URL изображения доски
}

export interface BoardState {
  definition: BoardDefinition;
  fighters: Map<string, Position>;  // fighterId -> position
}

// ------------------------------------------------------------
// Game State Types
// ------------------------------------------------------------

export enum GamePhase {
  SETUP = 'setup',
  START_OF_TURN = 'start_of_turn',
  ACTION_SELECTION = 'action_selection',
  CARD_PLAY = 'card_play',
  MOVEMENT = 'movement',
  COMBAT = 'combat',
  COMBAT_DEFENSE = 'combat_defense',
  RESOLUTION = 'resolution',
  END_OF_TURN = 'end_of_turn',
  GAME_OVER = 'game_over',
}

export type ActionType = 'maneuver' | 'scheme' | 'attack';

export interface GameState {
  id: string;
  players: Player[];
  board: BoardState;
  currentTurn: TurnState;
  phase: GamePhase;
  combatState: CombatState | null;
  winner: string | null;
  turnCount: number;
}

export interface Player {
  id: string;
  name: string;
  fighters: Fighter[];  // Hero + sidekicks
  hand: CardInstance[];
  discardPile: CardInstance[];
  deck: CardInstance[];
  actionsRemaining: number;
  hasPassed: boolean;
  handLimit: number;
}

export interface TurnState {
  currentPlayerId: string;
  action1?: ActionType;
  action2?: ActionType;
  cardsDrawnThisTurn: number;
  selectedCard?: CardInstance;
  selectedTarget?: string;
}

// ------------------------------------------------------------
// Combat Types
// ------------------------------------------------------------

export interface CombatState {
  attacker: Fighter;
  defender: Fighter;
  attackCard: CardInstance;
  defenseCard?: CardInstance;
  attackValue: number;
  defenseValue: number;
  attackBoosts: number;
  defenseBoosts: number;
  effectsToProcess: CardEffect[];
  resolutionComplete: boolean;
}

// ------------------------------------------------------------
// Setup Types
// ------------------------------------------------------------

export interface GameSetup {
  players: Array<{
    id: string;
    name: string;
    heroId: string;
  }>;
  boardId: string;
  startingHandSize?: number;
}

// ------------------------------------------------------------
// Utility Types
// ------------------------------------------------------------

export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export type Immutable<T> = Readonly<{
  [P in keyof T]: T[P] extends object ? Immutable<T[P]> : T[P];
}>;
