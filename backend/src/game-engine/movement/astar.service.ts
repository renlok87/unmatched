/**
 * A* Pathfinding Service
 *
 * A* алгоритм для поиска пути между двумя точками.
 * Используется вместо BFS когда нужна проверка достижимости
 * конкретной клетки, а не всех возможных путей.
 *
 * Преимущества A* над BFS:
 * - Находит конкретный путь быстрее
 * - Использует эвристику для направленного поиска
 * - Меньше памяти для больших расстояний
 */

import { Injectable, Logger } from '@nestjs/common';
import { Position, positionEqual } from '../models';
import type { BoardState } from '../models';
import { distanceField, neighbours, ORTHOGONAL_NESW } from '../engine/board-topology';
import { isCellPassable, isFreeEndpoint, isInBoardBounds, isTraversable } from './traversal';

/**
 * Результат A* поиска
 */
export interface AStarResult {
  readonly path: readonly Position[];
  readonly cost: number;
  readonly exists: boolean;
}

/**
 * Узел в A* алгоритме
 */
interface AStarNode {
  pos: Position;
  g: number; // Стоимость от старта
  h: number; // Эвристика до цели
  f: number; // g + h
  parent?: Position;
}

@Injectable()
export class AStarService {
  private readonly logger = new Logger(AStarService.name);

  /**
   * Найти путь от start до end
   *
   * @param state Состояние игры (для проверки проходимости)
   * @param fighterId ID бойца (для проверки проходимости)
   * @param start Начальная позиция
   * @param end Конечная позиция
   * @param maxCost Максимальная стоимость (дистанция)
   * @returns Результат поиска
   */
  findPath(
    state: any,
    fighterId: string,
    start: Position,
    end: Position,
    maxCost: number,
  ): AStarResult {
    // Старт и цель: целочисленные клетки в границах реальной доски
    if (!isInBoardBounds(state?.boardState, start) || !isInBoardBounds(state?.boardState, end)) {
      return { path: [], cost: 0, exists: false };
    }
    if (!isCellPassable(state?.boardState?.cells?.[start.y]?.[start.x])) {
      return { path: [], cost: 0, exists: false };
    }
    // Цель проходима и свободна от живых бойцов
    if (!isCellPassable(state?.boardState?.cells?.[end.y]?.[end.x])) {
      return { path: [], cost: 0, exists: false };
    }
    if (!isFreeEndpoint(state, fighterId, end)) {
      return { path: [], cost: 0, exists: false };
    }

    const openSet: AStarNode[] = [];
    const closedSet = new Set<string>();
    const cameFrom = new Map<string, Position>();

    // Эвристика: сетка — манхэттен; топологическая доска — статическая
    // graph distance до цели (связь может перекрывать >1 шага решётки, поэтому
    // манхэттен там недопустим). Недостижимая по графу цель — пути нет.
    const heuristic = distanceField(this.boardOf(state), end);
    const startH = heuristic(start);
    if (!Number.isFinite(startH)) {
      return { path: [], cost: 0, exists: false };
    }

    // Начальная нода
    const startNode: AStarNode = {
      pos: start,
      g: 0,
      h: startH,
      f: startH,
    };

    openSet.push(startNode);

    while (openSet.length > 0) {
      // Сортируем по f (приоритетная очередь)
      openSet.sort((a, b) => a.f - b.f);
      const current = openSet.shift()!;

      // Проверяем лимит стоимости
      if (current.g > maxCost) {
        continue;
      }

      // Достигли цели?
      if (positionEqual(current.pos, end)) {
        return {
          path: this.reconstructPath(cameFrom, current.pos),
          cost: current.g,
          exists: true,
        };
      }

      const currentKey = this.posKey(current.pos);
      closedSet.add(currentKey);

      // Проверяем соседей
      for (const neighbor of this.getNeighbors(state, fighterId, current.pos)) {
        const neighborKey = this.posKey(neighbor);

        if (closedSet.has(neighborKey)) {
          continue;
        }

        const tentativeG = current.g + 1; // Стоимость перемещения = 1

        // Проверяем, есть ли сосед в openSet с меньшей стоимостью
        const existingNode = openSet.find((n) => positionEqual(n.pos, neighbor));

        if (!existingNode) {
          // Новая нода
          const h = heuristic(neighbor);
          const newNode: AStarNode = {
            pos: neighbor,
            g: tentativeG,
            h,
            f: tentativeG + h,
            parent: current.pos,
          };

          openSet.push(newNode);
          cameFrom.set(neighborKey, current.pos);
        } else if (tentativeG < existingNode.g) {
          // Нашли лучший путь к существующей ноде
          existingNode.g = tentativeG;
          existingNode.f = tentativeG + existingNode.h;
          existingNode.parent = current.pos;
          cameFrom.set(neighborKey, current.pos);
        }
      }
    }

    // Путь не найден
    return {
      path: [],
      cost: 0,
      exists: false,
    };
  }

  /**
   * Проверить, достижима ли позиция
   * (оптимизированная версия без восстановления пути)
   *
   * @param state Состояние игры
   * @param fighterId ID бойца
   * @param from Начальная позиция
   * @param to Конечная позиция
   * @param maxDistance Максимальная дистанция
   */
  isReachable(
    state: any,
    fighterId: string,
    from: Position,
    to: Position,
    maxDistance: number,
  ): boolean {
    const result = this.findPath(state, fighterId, from, to, maxDistance);
    return result.exists;
  }

  /**
   * Получить соседние клетки (board-topology: связи топологической доски
   * либо 4 ортогональных соседа сетки в порядке N, E, S, W): границы
   * реальной доски, стены/закрытые двери и живые враги блокируют шаг;
   * живые союзники проходимы (GD-015)
   */
  private getNeighbors(state: any, fighterId: string, pos: Position): Position[] {
    const neighbors: Position[] = [];

    for (const newPos of neighbours(this.boardOf(state), pos, ORTHOGONAL_NESW)) {
      if (!isInBoardBounds(state?.boardState, newPos)) {
        continue;
      }
      if (!isCellPassable(state?.boardState?.cells?.[newPos.y]?.[newPos.x])) {
        continue;
      }
      if (!isTraversable(state, fighterId, newPos)) {
        continue;
      }
      neighbors.push(newPos);
    }

    return neighbors;
  }

  /** Доска из нетипизированного state (легаси-сигнатура findPath(state: any)) */
  private boardOf(state: unknown): BoardState | undefined {
    return (state as { boardState?: BoardState } | null | undefined)?.boardState;
  }

  /**
   * Восстановить путь из cameFrom map
   */
  private reconstructPath(cameFrom: Map<string, Position>, current: Position): Position[] {
    const path: Position[] = [current];
    let currentKey = this.posKey(current);

    while (cameFrom.has(currentKey)) {
      current = cameFrom.get(currentKey)!;
      path.unshift(current);
      currentKey = this.posKey(current);
    }

    return path;
  }

  /**
   * Создать ключ для позиции
   */
  private posKey(pos: Position): string {
    return `${pos.x}:${pos.y}`;
  }
}
