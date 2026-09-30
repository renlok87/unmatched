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
 * оттенков ("blue-dark", "green-light") и опечатки ("biege", "brown-ligt") —
 * они нормализуются к этим базовым цветам в ContentMapper.normalizeZone
 * (неизвестное отбрасывается).
 *
 * VIOLET (ENV-MAPS, 2026-09-30) — САМОСТОЯТЕЛЬНАЯ зона, не синоним PURPLE:
 * на Marmoreal, Globe Theatre и Azuchi Castle violet и purple — две разные
 * зоны одной карты (Marmoreal M16 blue+violet, M17 green+blue+purple).
 */
export enum Zone {
  BLUE = 'blue',
  GREEN = 'green',
  YELLOW = 'yellow',
  RED = 'red',
  PURPLE = 'purple',
  VIOLET = 'violet',
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
  | 'violet'
  | 'brown'
  | 'gray'
  | 'orange'
  | 'pink'
  | 'white'
  | 'gold'
  | 'beige';
