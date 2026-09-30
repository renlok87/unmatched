/**
 * Adjacency Service
 *
 * Определяет соседние клетки и достижимость на доске.
 * Используется для перемещения и поиска путей.
 */

import { Injectable, Logger } from '@nestjs/common';
import type { BoardState, Position } from '../models';
import { getCellZones } from '../models';
import * as topology from './board-topology';

export interface AdjacentCell {
  readonly position: Position;
  readonly direction: Direction;
  readonly cost: number;
  readonly isBlocked: boolean;
}

export enum Direction {
  NORTH = 'north',
  SOUTH = 'south',
  EAST = 'east',
  WEST = 'west',
  NORTHEAST = 'northeast',
  NORTHWEST = 'northwest',
  SOUTHEAST = 'southeast',
  SOUTHWEST = 'southwest',
}

@Injectable()
export class AdjacencyService {
  private readonly logger = new Logger(AdjacencyService.name);

  // Смещения для соседних клеток (ортогональные)
  private readonly orthogonalOffsets: readonly { dx: number; dy: number; direction: Direction }[] =
    [
      { dx: 0, dy: -1, direction: Direction.NORTH },
      { dx: 0, dy: 1, direction: Direction.SOUTH },
      { dx: 1, dy: 0, direction: Direction.EAST },
      { dx: -1, dy: 0, direction: Direction.WEST },
    ];

  // Смещения для диагональных соседей
  private readonly diagonalOffsets: readonly { dx: number; dy: number; direction: Direction }[] = [
    { dx: 1, dy: -1, direction: Direction.NORTHEAST },
    { dx: -1, dy: -1, direction: Direction.NORTHWEST },
    { dx: 1, dy: 1, direction: Direction.SOUTHEAST },
    { dx: -1, dy: 1, direction: Direction.SOUTHWEST },
  ];

  /**
   * Получить соседние клетки для позиции.
   *
   * Топологическая доска (engine/board-topology): соседи — РОВНО связанные
   * линией клетки (links), includeDiagonal игнорируется, стоимость шага 1.
   * Сеточная доска — прежние ортогональные (и опц. диагональные) соседи.
   */
  getAdjacentCells(
    boardState: BoardState,
    position: Position,
    options: { includeDiagonal?: boolean; ignoreBlocking?: boolean } = {},
  ): readonly AdjacentCell[] {
    const { includeDiagonal = false, ignoreBlocking = false } = options;

    if (topology.hasTopology(boardState)) {
      return topology
        .neighbours(boardState, position)
        .map((adjacentPos) => {
          const cell = this.getCell(boardState, adjacentPos);
          if (!cell) {
            return null;
          }
          return {
            position: adjacentPos,
            direction: this.directionBetween(position, adjacentPos),
            cost: 1,
            isBlocked: !ignoreBlocking && this.isCellBlocked(cell),
          };
        })
        .filter((c): c is AdjacentCell => c !== null);
    }

    const offsets = includeDiagonal
      ? [...this.orthogonalOffsets, ...this.diagonalOffsets]
      : this.orthogonalOffsets;

    return offsets
      .map(({ dx, dy, direction }) => {
        const adjacentPos: Position = { x: position.x + dx, y: position.y + dy };
        const cell = this.getCell(boardState, adjacentPos);

        if (!cell) {
          return null;
        }

        const isBlocked = !ignoreBlocking && this.isCellBlocked(cell);
        const cost = includeDiagonal && dx !== 0 && dy !== 0 ? 1.5 : 1;

        return {
          position: adjacentPos,
          direction,
          cost,
          isBlocked,
        };
      })
      .filter((c): c is AdjacentCell => c !== null);
  }

  /**
   * Получить достижимые клетки (BFS)
   */
  getReachableCells(
    boardState: BoardState,
    start: Position,
    maxCost: number,
    options: {
      includeDiagonal?: boolean;
      // Дополнительно заблокированные позиции (ключ `x:y`) — напр. занятые бойцами клетки
      blockedPositions?: ReadonlySet<string>;
    } = {},
  ): Map<string, { position: Position; cost: number }> {
    const reachable = new Map<string, { position: Position; cost: number }>();
    const visited = new Set<string>();
    const queue: Array<{ position: Position; cost: number }> = [{ position: start, cost: 0 }];

    visited.add(this.posKey(start));

    while (queue.length > 0) {
      const current = queue.shift()!;

      if (current.cost > 0) {
        reachable.set(this.posKey(current.position), {
          position: current.position,
          cost: current.cost,
        });
      }

      if (current.cost >= maxCost) {
        continue;
      }

      const adjacent = this.getAdjacentCells(boardState, current.position, options);

      for (const cell of adjacent) {
        if (cell.isBlocked || options.blockedPositions?.has(this.posKey(cell.position))) {
          continue;
        }

        const key = this.posKey(cell.position);
        if (visited.has(key)) {
          continue;
        }

        visited.add(key);
        queue.push({
          position: cell.position,
          cost: current.cost + cell.cost,
        });
      }
    }

    return reachable;
  }

  /**
   * Проверить, заблокирована ли клетка
   */
  isCellBlocked(cell: BoardState['cells'][number][number]): boolean {
    return (
      cell.type === 'wall' || cell.type === 'obstacle' || (cell.type === 'door' && !cell.isOpen)
    );
  }

  /**
   * Получить клетку по позиции
   */
  private getCell(
    boardState: BoardState,
    position: Position,
  ): BoardState['cells'][number][number] | null {
    if (
      position.x < 0 ||
      position.x >= boardState.width ||
      position.y < 0 ||
      position.y >= boardState.height
    ) {
      return null;
    }

    return boardState.cells[position.y]?.[position.x];
  }

  /**
   * Создать ключ для позиции
   */
  private posKey(pos: Position): string {
    return topology.posKey(pos);
  }

  /**
   * Грубое направление связи (для топологических связей, которые могут
   * перекрывать несколько шагов решётки) — по знакам dx/dy.
   */
  private directionBetween(from: Position, to: Position): Direction {
    const sx = Math.sign(to.x - from.x);
    const sy = Math.sign(to.y - from.y);
    if (sx === 0) return sy < 0 ? Direction.NORTH : Direction.SOUTH;
    if (sy === 0) return sx > 0 ? Direction.EAST : Direction.WEST;
    if (sy < 0) return sx > 0 ? Direction.NORTHEAST : Direction.NORTHWEST;
    return sx > 0 ? Direction.SOUTHEAST : Direction.SOUTHWEST;
  }

  /**
   * Вычислить Manhattan расстояние (метрика СЕТКИ, без учёта доски).
   * Тонкая обёртка над board-topology.manhattanDistance; для дальности на
   * произвольной доске используйте boardDistance.
   */
  manhattanDistance(a: Position, b: Position): number {
    return topology.manhattanDistance(a, b);
  }

  /**
   * «Сколько пространств между» с учётом доски: топология — graph distance
   * по линиям; сетка — манхэттен (как раньше).
   */
  boardDistance(
    state: { boardState?: BoardState } | null | undefined,
    a: Position,
    b: Position,
  ): number {
    return topology.boardDistance(state?.boardState, a, b);
  }

  /**
   * Синхронная смежность с учётом доски (см. isAdjacent).
   */
  isAdjacentOnBoard(
    state: { boardState?: BoardState } | null | undefined,
    a: Position,
    b: Position,
  ): boolean {
    return topology.isAdjacent(state?.boardState, a, b);
  }

  /**
   * Вычислить Евклидово расстояние
   */
  euclideanDistance(a: Position, b: Position): number {
    return Math.sqrt(Math.pow(a.x - b.x, 2) + Math.pow(a.y - b.y, 2));
  }

  /**
   * Проверить, являются ли две позиции смежными
   * Используется для проверки возможности атаки
   *
   * Топологическая доска (state.boardState с links): смежны ⟺ соединены
   * линией; иначе (сетка или нет доски) — манхэттен === 1, как раньше.
   *
   * @param state - Состояние игры
   * @param a - Первая позиция
   * @param b - Вторая позиция
   * @returns true если позиции смежные
   */
  async isAdjacent(state: any, a: Position, b: Position): Promise<boolean> {
    return this.isAdjacentOnBoard(state as { boardState?: BoardState } | null | undefined, a, b);
  }

  /**
   * Проверить, пересекаются ли зоны двух клеток доски.
   * Используется для ranged-атак: цель в пересекающейся зоне ИЛИ смежная.
   *
   * Мультизонность: клетка может состоять в 1–2 зонах (Cell.zones) —
   * сравнение ПО ПЕРЕСЕЧЕНИЮ списков; legacy-сейвы с одиночным Cell.zone
   * покрываются fallback'ом внутри getCellZones. На доске без зон
   * (все zones пусты) возвращается false — ranged работает только по adjacency.
   */
  isInSameZone(state: { boardState: BoardState }, a: Position, b: Position): boolean {
    const zonesA = getCellZones(state.boardState.cells[a.y]?.[a.x]);
    const zonesB = getCellZones(state.boardState.cells[b.y]?.[b.x]);
    return zonesA.length > 0 && zonesA.some((z) => zonesB.includes(z));
  }
}
