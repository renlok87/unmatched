import type { BoardDefinition, BoardState, Position, Zone, BoardSpace, Fighter } from './types';

/**
 * Board class - represents the game board with zones
 */
export class BoardModel {
  /**
   * Create a board state from a definition
   */
  static createBoard(definition: BoardDefinition): BoardState {
    return {
      definition,
      fighters: new Map(),
    };
  }

  /**
   * Get a space at a specific position
   */
  static getSpaceAt(board: BoardState, position: Position): BoardSpace | undefined {
    return board.definition.spaces.find(
      s => s.position.x === position.x && s.position.y === position.y
    );
  }

  /**
   * Check if a position is valid (exists on the board)
   */
  static isValidPosition(board: BoardState, position: Position): boolean {
    return (
      position.x >= 0 &&
      position.x < board.definition.width &&
      position.y >= 0 &&
      position.y < board.definition.height
    );
  }

  /**
   * Get zones at a specific position
   */
  static getZonesAt(board: BoardState, position: Position): Zone[] {
    const space = this.getSpaceAt(board, position);
    return space?.zones || [];
  }

  /**
   * Check if two positions share at least one zone
   */
  static sharesZone(board: BoardState, pos1: Position, pos2: Position): boolean {
    const zones1 = this.getZonesAt(board, pos1);
    const zones2 = this.getZonesAt(board, pos2);

    return zones1.some(z => zones2.includes(z));
  }

  /**
   * Get all spaces that share at least one zone with the given position
   */
  static getConnectedSpaces(board: BoardState, position: Position): BoardSpace[] {
    const zones = this.getZonesAt(board, position);

    return board.definition.spaces.filter(space =>
      space.position.x !== position.x ||
      space.position.y !== position.y ||
      space.zones.some(z => zones.includes(z))
    );
  }

  /**
   * Get adjacent spaces (sharing at least one zone)
   */
  static getAdjacentSpaces(board: BoardState, position: Position): BoardSpace[] {
    const zones = this.getZonesAt(board, position);

    return board.definition.spaces.filter(space => {
      if (space.position.x === position.x && space.position.y === position.y) {
        return false; // Same space
      }
      return space.zones.some(z => zones.includes(z));
    });
  }

  /**
   * Get the position of a fighter
   */
  static getFighterPosition(board: BoardState, fighterId: string): Position | undefined {
    return board.fighters.get(fighterId);
  }

  /**
   * Set the position of a fighter
   */
  static setFighterPosition(board: BoardState, fighterId: string, position: Position): BoardState {
    const newFighters = new Map(board.fighters);
    newFighters.set(fighterId, { ...position });

    return {
      ...board,
      fighters: newFighters,
    };
  }

  /**
   * Remove a fighter from the board
   */
  static removeFighter(board: BoardState, fighterId: string): BoardState {
    const newFighters = new Map(board.fighters);
    newFighters.delete(fighterId);

    return {
      ...board,
      fighters: newFighters,
    };
  }

  /**
   * Get all fighters at a specific position
   */
  static getFightersAt(board: BoardState, position: Position, allFighters: Fighter[]): Fighter[] {
    const fighterIds = Array.from(board.fighters.entries())
      .filter(([_, pos]) => pos.x === position.x && pos.y === position.y)
      .map(([id]) => id);

    return allFighters.filter(f => fighterIds.includes(f.id));
  }

  /**
   * Check if a space has an obstacle
   */
  static isObstacle(board: BoardState, position: Position): boolean {
    const space = this.getSpaceAt(board, position);
    return space?.isObstacle ?? false;
  }

  /**
   * Calculate distance between two positions (for range calculations)
   * In Unmatched, range is determined by zone connectivity, not Euclidean distance
   */
  static getDistance(board: BoardState, from: Position, to: Position): number {
    if (from.x === to.x && from.y === to.y) {
      return 0;
    }

    // BFS to find shortest path through zones
    const visited = new Set<string>();
    const queue: Array<{ pos: Position; dist: number }> = [{ pos: from, dist: 0 }];

    visited.add(`${from.x},${from.y}`);

    while (queue.length > 0) {
      const current = queue.shift()!;

      if (current.pos.x === to.x && current.pos.y === to.y) {
        return current.dist;
      }

      const adjacent = this.getAdjacentSpaces(board, current.pos);

      for (const space of adjacent) {
        const key = `${space.position.x},${space.position.y}`;
        if (!visited.has(key)) {
          visited.add(key);
          queue.push({ pos: space.position, dist: current.dist + 1 });
        }
      }
    }

    return Infinity; // No path found
  }

  /**
   * Clone a board state
   */
  static clone(board: BoardState): BoardState {
    return {
      ...board,
      fighters: new Map(board.fighters),
    };
  }

  /**
   * Check if two positions are equal
   */
  static positionsEqual(a: Position, b: Position): boolean {
    return a.x === b.x && a.y === b.y;
  }

  /**
   * Create a position key for Map/Set operations
   */
  static positionKey(position: Position): string {
    return `${position.x},${position.y}`;
  }
}
