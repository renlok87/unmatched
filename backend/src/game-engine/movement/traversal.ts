/**
 * Общие pure-правила проходимости пути (GD-015).
 *
 * Единая семантика для validateManeuver/validateMovement,
 * MovementService.executeMovement/getValidMoveTargets, AStar и AI:
 * - живой СОЮЗНИК на промежуточной клетке — путь разрешён;
 * - живой ВРАГ на промежуточной клетке — путь запрещён;
 * - КОНЕЧНАЯ клетка не может содержать никакого другого живого бойца;
 * - побеждённые бойцы никого не блокируют.
 */

import type { BoardState, Cell, Fighter, Position } from '../models';

/** Минимальный срез GameState, нужный правилам пути */
export interface TraversalState {
  readonly fighters: readonly Fighter[];
}

export function isLivingFighter(f: Fighter): boolean {
  return f.health > 0 && !f.isDefeated;
}

/**
 * Клетка проходима для шага: стены/препятствия/закрытые двери блокируют.
 * Отсутствующая клетка (undefined внутри ограничивающего прямоугольника)
 * непроходима — дыры в cells не являются играбельным пространством.
 */
export function isCellPassable(cell: Cell | undefined): boolean {
  if (!cell) return false;
  return !(cell.type === 'wall' || cell.type === 'obstacle' || (cell.type === 'door' && !cell.isOpen));
}

/**
 * Позиция — целочисленная клетка внутри границ доски.
 * Без boardState доски нет: пути не существуют (никаких придуманных сеток).
 */
export function isInBoardBounds(boardState: BoardState | undefined, pos: Position): boolean {
  if (!Number.isInteger(pos.x) || !Number.isInteger(pos.y)) return false;
  if (!boardState) return false;
  return pos.x >= 0 && pos.x < boardState.width && pos.y >= 0 && pos.y < boardState.height;
}

/**
 * Промежуточный шаг пути разрешён: клетка свободна от живых бойцов либо
 * занята живым союзником (совпадает ownerId). Живой враг блокирует проход.
 */
export function isTraversable(state: TraversalState, moverId: string, pos: Position): boolean {
  const blocker = state.fighters.find(
    (f) =>
      f.id !== moverId &&
      isLivingFighter(f) &&
      f.position.x === pos.x &&
      f.position.y === pos.y,
  );
  if (!blocker) return true;
  const mover = state.fighters.find((f) => f.id === moverId);
  return mover != null && blocker.ownerId === mover.ownerId;
}

/** Конечная клетка пути свободна: на ней нет НИ одного другого живого бойца */
export function isFreeEndpoint(state: TraversalState, moverId: string, pos: Position): boolean {
  return !state.fighters.some(
    (f) =>
      f.id !== moverId &&
      isLivingFighter(f) &&
      f.position.x === pos.x &&
      f.position.y === pos.y,
  );
}
