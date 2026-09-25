/**
 * Movement Service
 *
 * Обрабатывает перемещения бойцов по доске.
 * Проверяет валидность перемещений и обновляет состояние.
 */

import { Injectable, Logger } from '@nestjs/common';
import type { GameState, Fighter, Position } from '../models';
import { AStarService, PathCacheService } from '../movement';
import { isCellPassable, isFreeEndpoint, isTraversable } from '../movement/traversal';

export interface MovementResult {
  readonly success: boolean;
  readonly path?: readonly Position[];
  readonly nextState?: GameState;
  readonly error?: string;
}

export interface MovementOptions {
  readonly allowDiagonal?: boolean;
  readonly ignoreEnemies?: boolean;
  readonly maxCost?: number;
}

@Injectable()
export class MovementService {
  private readonly logger = new Logger(MovementService.name);

  constructor(
    private readonly astar: AStarService,
    private readonly pathCache: PathCacheService,
  ) {}

  /**
   * Переместить бойца в новую позицию
   */
  async moveFighter(
    state: GameState,
    fighterId: string,
    targetPosition: Position,
    options: MovementOptions = {},
  ): Promise<MovementResult> {
    const fighter = state.fighters.find((f) => f.id === fighterId);

    if (!fighter) {
      return { success: false, error: 'Fighter not found' };
    }

    // Проверяем валидность целевой позиции
    if (!this.isValidPosition(state, targetPosition)) {
      return { success: false, error: 'Invalid target position' };
    }

    // Находим путь
    const pathResult = await this.findPath(
      state,
      fighterId,
      fighter.position,
      targetPosition,
      options,
    );

    if (!pathResult.path || pathResult.path.length === 0) {
      return { success: false, error: pathResult.error || 'No path found' };
    }

    // Проверяем стоимость перемещения
    const maxCost = options.maxCost ?? fighter.health;
    if (pathResult.cost > maxCost) {
      return {
        success: false,
        error: `Path cost ${pathResult.cost} exceeds maximum ${maxCost}`,
      };
    }

    // TODO: Применить перемещение к состоянию
    const nextState = state;

    this.logger.debug(
      `Moved fighter ${fighter.name} to (${targetPosition.x}, ${targetPosition.y})`,
    );

    return {
      success: true,
      path: pathResult.path,
      nextState,
    };
  }

  /**
   * Найти путь между двумя позициями.
   * Путь A* включает стартовую клетку; правила прохождения — см. traversal.ts
   */
  async findPath(
    state: GameState,
    fighterId: string,
    start: Position,
    end: Position,
    options: MovementOptions = {},
  ): Promise<{ path?: readonly Position[]; cost: number; error?: string }> {
    const maxDistance = options.maxCost ?? 10;
    return this.astar.findPath(state, fighterId, start, end, maxDistance);
  }

  /**
   * Получить допустимые позиции для перемещения (BFS, 4-связно).
   * Живые враги блокируют прохождение, живые союзники проходимы, но ни на
   * какого живого бойца нельзя закончить путь; побеждённые не блокируют.
   */
  getValidMoveTargets(state: GameState, fighterId: string, maxCost: number): readonly Position[] {
    const fighter = state.fighters.find((f) => f.id === fighterId);

    if (!fighter || maxCost < 1) {
      return [];
    }

    const targets: Position[] = [];
    const visited = new Set<string>([this.posKey(fighter.position)]);
    const queue: Array<{ position: Position; cost: number }> = [
      { position: fighter.position, cost: 0 },
    ];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (current.cost >= maxCost) {
        continue;
      }

      for (const neighbor of this.orthogonalNeighbors(current.position)) {
        const key = this.posKey(neighbor);
        if (visited.has(key)) {
          continue;
        }
        const cell = state.boardState.cells[neighbor.y]?.[neighbor.x];
        if (!cell || !isCellPassable(cell)) {
          continue;
        }
        if (!isTraversable(state, fighterId, neighbor)) {
          continue;
        }
        visited.add(key);
        queue.push({ position: neighbor, cost: current.cost + 1 });
        if (isFreeEndpoint(state, fighterId, neighbor)) {
          targets.push(neighbor);
        }
      }
    }

    return targets;
  }

  private orthogonalNeighbors(pos: Position): Position[] {
    return [
      { x: pos.x, y: pos.y - 1 },
      { x: pos.x + 1, y: pos.y },
      { x: pos.x, y: pos.y + 1 },
      { x: pos.x - 1, y: pos.y },
    ];
  }

  private posKey(pos: Position): string {
    return `${pos.x}:${pos.y}`;
  }

  /**
   * Проверить валидность позиции
   */
  private isValidPosition(state: GameState, pos: Position): boolean {
    // Проверяем границы доски
    if (pos.x < 0 || pos.x >= state.boardState.width) {
      return false;
    }
    if (pos.y < 0 || pos.y >= state.boardState.height) {
      return false;
    }

    // Проверяем препятствия: стены, закрытые двери, отсутствующие клетки
    const cell = state.boardState.cells[pos.y]?.[pos.x];
    return isCellPassable(cell);
  }

  /**
   * Создать ключ для кэша путей
   */
  private getPathCacheKey(
    state: GameState,
    fighterId: string,
    start: Position,
    end: Position,
  ): string {
    return `path:${state.gameId}:${fighterId}:${start.x}:${start.y}-${end.x}:${end.y}`;
  }

  /**
   * Выполнить перемещение по пути
   * Используется в GameActionExecutorService
   */
  async executeMovement(
    state: GameState,
    fighterId: string,
    path: readonly Position[],
  ): Promise<MovementResult> {
    const fighter = state.fighters.find((f) => f.id === fighterId);

    if (!fighter) {
      return { success: false, error: 'Fighter not found' };
    }

    if (!path || path.length === 0) {
      return { success: false, error: 'Path is empty' };
    }

    // Проверяем валидность каждой позиции в пути. Путь без телепортов:
    // каждый шаг — на соседнюю клетку (manhattan === 1). Путь в конвенции
    // AStar может начинаться со стартовой клетки бойца — её пропускаем.
    let prev = fighter.position;
    for (let i = 0; i < path.length; i++) {
      const pos = path[i];
      if (!this.isValidPosition(state, pos)) {
        return { success: false, error: `Invalid position in path: (${pos.x}, ${pos.y})` };
      }

      if (i === 0 && pos.x === fighter.position.x && pos.y === fighter.position.y) {
        prev = pos;
        continue;
      }

      if (Math.abs(pos.x - prev.x) + Math.abs(pos.y - prev.y) !== 1) {
        return {
          success: false,
          error: `Step (${prev.x},${prev.y})→(${pos.x},${pos.y}) is not a move to an adjacent cell`,
        };
      }

      const isLast = i === path.length - 1;
      if (isLast) {
        // Конечная клетка не может содержать никакого живого бойца
        if (!isFreeEndpoint(state, fighterId, pos)) {
          return { success: false, error: `Position occupied: (${pos.x}, ${pos.y})` };
        }
      } else if (!isTraversable(state, fighterId, pos)) {
        // Промежуточная клетка: живой враг блокирует проход (союзник — нет)
        return {
          success: false,
          error: `Path blocked by enemy fighter at: (${pos.x}, ${pos.y})`,
        };
      }

      prev = pos;
    }

    // Создаём обновлённое состояние
    const lastPosition = path[path.length - 1];
    const updatedFighters = state.fighters.map((f) =>
      f.id === fighterId
        ? { ...f, position: { x: lastPosition.x, y: lastPosition.y } }
        : f,
    );

    const nextState: GameState = {
      ...state,
      fighters: updatedFighters,
      sequenceNumber: state.sequenceNumber + 1,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
        lastActionBy: fighter.ownerId,
      },
    };

    this.logger.debug(
      `Executed movement for fighter ${fighter.name} to (${lastPosition.x}, ${lastPosition.y})`,
    );

    return {
      success: true,
      path,
      nextState,
    };
  }
}
