/**
 * Movement Service
 *
 * Обрабатывает перемещения бойцов по доске.
 * Проверяет валидность перемещений и обновляет состояние.
 */

import { Injectable, Logger } from '@nestjs/common';
import type { GameState, Fighter, Position } from '../models';
import { AStarService, PathCacheService } from '../movement';

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
   * Найти путь между двумя позициями
   */
  async findPath(
    state: GameState,
    fighterId: string,
    start: Position,
    end: Position,
    options: MovementOptions = {},
  ): Promise<{ path?: readonly Position[]; cost: number; error?: string }> {
    // Проверяем кэш достижимых позиций
    const maxDistance = options.maxCost ?? 10;
    const cachedPositions = this.pathCache.get(fighterId, start, maxDistance);

    // Если есть кэш, проверяем достижима ли конечная точка
    if (cachedPositions) {
      const isReachable = cachedPositions.some((p) => p.x === end.x && p.y === end.y);
      if (isReachable) {
        // TODO: Построить путь из кешированных позиций
        return { path: [start, end], cost: maxDistance };
      }
    }

    // Используем A* для поиска пути
    const result = this.astar.findPath(state, fighterId, start, end, maxDistance);

    // Кешируем достижимые позиции из start
    if (cachedPositions === null) {
      // TODO: Вычислить и закешировать достижимые позиции
      this.pathCache.set(fighterId, start, maxDistance, result.path ?? []);
    }

    return result;
  }

  /**
   * Получить допустимые позиции для перемещения
   */
  getValidMoveTargets(state: GameState, fighterId: string, maxCost: number): readonly Position[] {
    const fighter = state.fighters.find((f) => f.id === fighterId);

    if (!fighter) {
      return [];
    }

    // TODO: Реализовать BFS для поиска всех достижимых позиций
    return [];
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

    // Проверяем препятствия
    const cell = state.boardState.cells[pos.y]?.[pos.x];
    if (!cell || cell.type === 'wall' || cell.type === 'obstacle') {
      return false;
    }

    return true;
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

    // Проверяем валидность каждой позиции в пути
    for (const pos of path) {
      if (!this.isValidPosition(state, pos)) {
        return { success: false, error: `Invalid position in path: (${pos.x}, ${pos.y})` };
      }

      // Проверяем что целевая позиция не занята (кроме стартовой)
      if (pos.x !== fighter.position.x || pos.y !== fighter.position.y) {
        const occupied = state.fighters.some(
          (f) => f.id !== fighterId && f.position.x === pos.x && f.position.y === pos.y && f.health > 0,
        );
        if (occupied) {
          return { success: false, error: `Position occupied: (${pos.x}, ${pos.y})` };
        }
      }
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
