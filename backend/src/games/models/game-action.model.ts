export enum GameActionType {
  GAME_CREATED = 'GAME_CREATED',
  GAME_JOINED = 'GAME_JOINED',
  GAME_STARTED = 'GAME_STARTED',
  GAME_ENDED = 'GAME_ENDED',
  GAME_ABORTED = 'GAME_ABORTED',
  TURN_STARTED = 'TURN_STARTED',
  TURN_ENDED = 'TURN_ENDED',
  PASSED = 'PASSED',
  CARD_PLAYED = 'CARD_PLAYED',
  CARD_DISCARDED = 'CARD_DISCARDED',
  // Полное зеркало Prisma-enum GameActionType (schema.prisma)
  FIGHTER_MOVED = 'FIGHTER_MOVED',
  MANEUVER = 'MANEUVER',
  PLACED = 'PLACED',
  ATTACK_INITIATED = 'ATTACK_INITIATED',
  DEFENSE_PLAYED = 'DEFENSE_PLAYED',
  COMBAT_RESOLVED = 'COMBAT_RESOLVED',
  EFFECT_APPLIED = 'EFFECT_APPLIED',
  SPECIAL_ABILITY = 'SPECIAL_ABILITY',
  DOOR_TOGGLED = 'DOOR_TOGGLED',
}

export interface GameAction {
  id: string;
  gameId: string;
  sequenceNumber: number;
  type: GameActionType;
  playerId: string;
  timestamp: Date;
  metadata: Record<string, any>;
}

export interface GameActionMetadata {
  cardId?: string;
  targetId?: string;
  fromPosition?: { row: number; col: number };
  toPosition?: { row: number; col: number };
  damage?: number;
  value?: number;
  reason?: string;
}

export interface CreateGameActionDto {
  gameId: string;
  sequenceNumber: number;
  type: GameActionType;
  playerId: string;
  metadata: GameActionMetadata & Record<string, unknown>;
}
