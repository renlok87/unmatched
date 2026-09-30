/**
 * Board Model
 *
 * Типы для состояния доски
 */

import { Position } from './fighter.model';

/**
 * Состояние доски
 */
export interface BoardState {
  readonly width: number;
  readonly height: number;
  readonly cells: readonly (readonly Cell[])[];
  readonly doors: Readonly<Record<string, boolean>>; // ID двери -> открыта/закрыта
  readonly fog: Readonly<Record<string, boolean>>; // ID клетки -> туман/нет
  readonly tokens: Readonly<Record<string, any>>; // ID клетки -> жетоны
}

/**
 * Клетка доски
 */
export interface Cell {
  readonly type: 'normal' | 'wall' | 'obstacle' | 'door' | 'zone-line';
  readonly x: number;
  readonly y: number;
  /** @deprecated Первая зона — legacy-сейвы; полный список в zones */
  readonly zone?: string;
  /** Все зоны клетки (в Unmatched клетка может быть в 1–2 зонах;
   *  ranged-атаки и зонные эффекты работают по ПЕРЕСЕЧЕНИЮ зон) */
  readonly zones?: readonly string[];
  readonly isOpen?: boolean; // Для дверей
  readonly isHighGround?: boolean;
  /**
   * Топология оригинальной карты (граф клеток со связями). Доска «имеет
   * топологию», если хотя бы одна её клетка несёт массив links; тогда соседи
   * клетки — РОВНО её links (симметрично), а не ортогональная сетка.
   * Единственная точка чтения — engine/board-topology.ts.
   */
  readonly links?: readonly Position[];
  /** Центр пространства в пикселях иллюстрации карты (1337x866) — для клиента */
  readonly layout?: { readonly x: number; readonly y: number };
  /** Номер стартового пространства (1..4) оригинальной карты */
  readonly start?: number;
  /** Id пространства оригинальной карты (M01..M31, S01..S38) */
  readonly spaceId?: string;
}

/**
 * Все зоны клетки: zones, либо legacy-zone, либо пусто.
 * Единственная точка чтения зон — мультизонность через неё.
 */
export function getCellZones(cell: Cell | undefined): readonly string[] {
  if (!cell) return [];
  if (cell.zones && cell.zones.length > 0) return cell.zones;
  return cell.zone != null ? [cell.zone] : [];
}

/**
 * Характеристики клетки доски
 */
export interface CellFeature {
  readonly type: CellType;
  readonly zone?: string;
  readonly connections?: readonly string[]; // ID соединённых клеток
  readonly isHighGround?: boolean;
  readonly hasSecretPassage?: boolean;
  readonly doorId?: string;
}

/**
 * Тип клетки
 */
export enum CellType {
  NORMAL = 'NORMAL',
  OBSTACLE = 'OBSTACLE',
  ZONE_LINE = 'ZONE_LINE',
  STARTING_ZONE = 'STARTING_ZONE',
}

/**
 * Дверь на доске
 */
export interface Door {
  readonly id: string;
  readonly isOpen: boolean;
  readonly position: Position;
  readonly connects: readonly string[]; // ID клеток
}

/**
 * Создаёт пустое состояние доски
 */
export function createEmptyBoardState(width: number = 20, height: number = 20): BoardState {
  // Создаём сетку клеток
  const cells: Cell[][] = [];
  for (let y = 0; y < height; y++) {
    const row: Cell[] = [];
    for (let x = 0; x < width; x++) {
      row.push({
        type: 'normal',
        x,
        y,
      });
    }
    cells.push(row);
  }

  return {
    width,
    height,
    cells,
    doors: {},
    fog: {},
    tokens: {},
  };
}

/**
 * Создаёт ключ для клетки
 */
export function cellKey(x: number, y: number): string {
  return `${x}:${y}`;
}

/**
 * Парсит ключ клетки
 */
export function parseCellKey(key: string): Position {
  const [x, y] = key.split(':').map(Number);
  return { x, y };
}
