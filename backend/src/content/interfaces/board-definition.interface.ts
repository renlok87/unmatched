/**
 * Board Definition Interface
 * Defines a game board with its spaces and zones
 */
export interface BoardDefinition {
  id: string;
  name: string;
  width: number;
  height: number;
  recommendedPlayers: number;
  spaces: BoardSpace[];
  imageUrl?: string;
}

/**
 * Board Space Interface
 * Defines a single space on the board
 */
export interface BoardSpace {
  position: Position;
  zones: Zone[];
  isObstacle?: boolean;
  startingPositions?: Record<string, Position>;
}

/**
 * Position Interface
 */
export interface Position {
  x: number;
  y: number;
}

/**
 * Zone Enum
 * Color zones on the board
 */
export enum Zone {
  BLUE = 'blue',
  GREEN = 'green',
  YELLOW = 'yellow',
  RED = 'red',
  PURPLE = 'purple',
}

/**
 * Zone Type for type checking
 * Use this type when you need the union type instead of the enum
 */
export type ZoneType = 'blue' | 'green' | 'yellow' | 'red' | 'purple';
