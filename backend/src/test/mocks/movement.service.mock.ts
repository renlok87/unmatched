/**
 * Mock Movement Service
 *
 * Используется для тестирования без реальной логики перемещения
 */

import { Position } from '../../game-engine/models';

export interface IMovementService {
  canMove(state: any, fighterId: string, from: Position, to: Position): boolean;
  getValidMoves(state: any, fighterId: string): readonly Position[];
}

/**
 * Mock реализация MovementService
 */
export class MockMovementService implements IMovementService {
  private canMoveResult = true;
  private validMoves: Position[] = [];

  canMove(): boolean {
    return this.canMoveResult;
  }

  getValidMoves(): readonly Position[] {
    return this.validMoves;
  }

  // Методы для настройки поведения в тестах

  setCanMoveResult(value: boolean): void {
    this.canMoveResult = value;
  }

  setValidMoves(positions: Position[]): void {
    this.validMoves = positions;
  }

  reset(): void {
    this.canMoveResult = true;
    this.validMoves = [];
  }
}
