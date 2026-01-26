import type { GameState, Position, Fighter } from '../models/types';
import { BoardModel } from '../models/Board';
import { FighterModel } from '../models/Fighter';

/**
 * MovementSystem - handles fighter movement on the board
 * Movement in Unmatched is zone-based: fighters can move to spaces
 * that share at least one zone with their current position
 */
export class MovementSystem {
  /**
   * Get all valid moves for a fighter based on their movement stat
   * Uses BFS to find all reachable spaces within movement range
   */
  getValidMoves(gameState: GameState, fighterId: string): Position[] {
    const fighter = this.findFighter(gameState, fighterId);
    if (!fighter || fighter.isDefeated) {
      return [];
    }

    const player = gameState.players.find(p => p.id === fighter.ownerId);
    if (!player) return [];

    const movement = this.getEffectiveMovement(fighter, player);
    const currentPosition = fighter.position;

    const validPositions: Position[] = [];
    const visited = new Set<string>();
    const queue: Array<{ pos: Position; remaining: number }> = [
      { pos: currentPosition, remaining: movement }
    ];

    visited.add(BoardModel.positionKey(currentPosition));

    while (queue.length > 0) {
      const { pos, remaining } = queue.shift()!;

      // Add position to valid moves (except starting position)
      if (remaining < movement) {
        validPositions.push(pos);
      }

      if (remaining <= 0) continue;

      // Get adjacent spaces that share zones
      const adjacent = BoardModel.getAdjacentSpaces(gameState.board, pos);

      for (const space of adjacent) {
        const key = BoardModel.positionKey(space.position);
        if (!visited.has(key) && this.canEnter(gameState, space.position, fighterId)) {
          visited.add(key);
          queue.push({ pos: space.position, remaining: remaining - 1 });
        }
      }
    }

    return validPositions;
  }

  /**
   * Check if a move is valid
   */
  isValidMove(gameState: GameState, fighterId: string, position: Position): boolean {
    const validMoves = this.getValidMoves(gameState, fighterId);
    return validMoves.some(p => BoardModel.positionsEqual(p, position));
  }

  /**
   * Check if a fighter can enter a specific space
   * - Space must not be an obstacle
   * - Space must not contain an enemy fighter (unless special ability)
   */
  canEnter(gameState: GameState, position: Position, fighterId: string): boolean {
    // Check if space exists
    if (!BoardModel.isValidPosition(gameState.board, position)) {
      return false;
    }

    // Check for obstacles
    if (BoardModel.isObstacle(gameState.board, position)) {
      return false;
    }

    // Check for other fighters
    const occupants = this.getFightersAt(gameState, position);
    const enemyOccupant = occupants.find(f => f.ownerId !==
      this.findFighter(gameState, fighterId)?.ownerId);

    if (enemyOccupant) {
      // Some heroes can move through enemies (e.g., Ms. Marvel's Stretchy)
      return this.canMoveThroughEnemies(gameState, fighterId);
    }

    // Cannot enter space occupied by own fighter (unless sidekick with hero)
    const allyOccupant = occupants.find(f => f.ownerId ===
      this.findFighter(gameState, fighterId)?.ownerId);

    if (allyOccupant && allyOccupant.id !== fighterId) {
      // Allow sidekicks to stack with hero
      const fighter = this.findFighter(gameState, fighterId);
      const ally = this.findFighter(gameState, allyOccupant.id);

      if (fighter && ally) {
        return (FighterModel.isHero(fighter) && FighterModel.isSidekick(ally)) ||
               (FighterModel.isSidekick(fighter) && FighterModel.isHero(ally));
      }
      return false;
    }

    return true;
  }

  /**
   * Check if fighter can move through enemies (special abilities)
   */
  canMoveThroughEnemies(_gameState: GameState, _fighterId: string): boolean {
    // TODO: Implement special ability checks
    // Ms. Marvel's Stretchy allows extended movement
    return false;
  }

  /**
   * Get the effective movement stat for a fighter
   * May be modified by abilities, card effects, etc.
   */
  getEffectiveMovement(_fighter: Fighter, _player: any): number {
    // TODO: Apply movement modifiers from cards, abilities
    // For now, return base movement from hero definition
    return 2;
  }

  /**
   * Get all fighters at a specific position
   */
  getFightersAt(gameState: GameState, position: Position): Fighter[] {
    const allFighters = gameState.players.flatMap(p => p.fighters);
    return BoardModel.getFightersAt(gameState.board, position, allFighters);
  }

  /**
   * Find a fighter by ID
   */
  findFighter(gameState: GameState, fighterId: string): Fighter | undefined {
    return gameState.players
      .flatMap(p => p.fighters)
      .find(f => f.id === fighterId);
  }

  /**
   * Check if two positions are in melee range (adjacent with shared zone)
   */
  isInRange(gameState: GameState, from: Position, to: Position, range: number = 1): boolean {
    if (range === 0) {
      return BoardModel.positionsEqual(from, to);
    }

    if (range === 1) {
      // Melee range - adjacent spaces sharing a zone
      return BoardModel.getAdjacentSpaces(gameState.board, from)
        .some(s => BoardModel.positionsEqual(s.position, to));
    }

    // For range > 1, calculate distance
    return BoardModel.getDistance(gameState.board, from, to) <= range;
  }

  /**
   * Check if attacker can attack defender based on position and range
   * Most heroes can only attack adjacent fighters
   * Some heroes have extended range (ranged attacks)
   */
  canAttack(
    gameState: GameState,
    attackerId: string,
    defenderId: string,
    cardRange: number = 1
  ): boolean {
    const attacker = this.findFighter(gameState, attackerId);
    const defender = this.findFighter(gameState, defenderId);

    if (!attacker || !defender) return false;
    if (attacker.isDefeated || defender.isDefeated) return false;

    // Check if defender is in range
    const effectiveRange = this.getAttackRange(gameState, attackerId, cardRange);
    return this.isInRange(gameState, attacker.position, defender.position, effectiveRange);
  }

  /**
   * Get attack range for a fighter
   * May be modified by abilities (e.g., Ms. Marvel's Stretchy gives range 2)
   */
  getAttackRange(_gameState: GameState, _fighterId: string, baseRange: number): number {
    // TODO: Implement special ability checks
    // Ms. Marvel can attack from 2 spaces away
    return baseRange;
  }

  /**
   * Check if two fighters share any zones
   */
  sharesZones(gameState: GameState, fighter1Id: string, fighter2Id: string): boolean {
    const f1 = this.findFighter(gameState, fighter1Id);
    const f2 = this.findFighter(gameState, fighter2Id);

    if (!f1 || !f2) return false;

    return BoardModel.sharesZone(gameState.board, f1.position, f2.position);
  }
}
