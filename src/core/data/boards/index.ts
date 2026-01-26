import type { BoardDefinition } from '../../models/types';
import { cobbleCity } from './cobble-city';

/**
 * Board Registry
 * All available game boards
 */
export const BOARD_REGISTRY: Record<string, BoardDefinition> = {
  'cobble-city': cobbleCity,
};

/**
 * Get a board definition by ID
 */
export function getBoardDefinition(boardId: string): BoardDefinition {
  const board = BOARD_REGISTRY[boardId];
  if (!board) {
    throw new Error(`Board not found: ${boardId}`);
  }
  return board;
}

/**
 * Get all available boards
 */
export function getAllBoards(): BoardDefinition[] {
  return Object.values(BOARD_REGISTRY);
}

/**
 * Get default board ID
 */
export function getDefaultBoardId(): string {
  return 'cobble-city';
}
