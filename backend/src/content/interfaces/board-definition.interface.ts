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
 * Color zones on the board.
 *
 * Базовые цвета зон Unmatched. Scraped-data (maps.json) содержит варианты
 * оттенков ("blue-dark", "green-light"), синоним "violet" и опечатки
 * ("biege", "brown-ligt") — все они нормализуются к этим базовым цветам
 * в ContentMapper.normalizeZone (неизвестное отбрасывается).
 */
export enum Zone {
  BLUE = 'blue',
  GREEN = 'green',
  YELLOW = 'yellow',
  RED = 'red',
  PURPLE = 'purple',
  BROWN = 'brown',
  GRAY = 'gray',
  ORANGE = 'orange',
  PINK = 'pink',
  WHITE = 'white',
  GOLD = 'gold',
  BEIGE = 'beige',
}

/**
 * Zone Type for type checking
 * Use this type when you need the union type instead of the enum
 */
export type ZoneType =
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
