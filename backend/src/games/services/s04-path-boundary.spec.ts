import { AStarService } from '../../game-engine/movement/astar.service';
import { PathCacheService } from '../../game-engine/movement';
import { MovementService } from '../../game-engine/engine/movement.service';
import { GameRulesValidator } from '../../game-engine/validators/game-rules.validator';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { s03Engine, s03Fixture } from '../../test/fixtures/s03-engine.fixture';

describe('GD-015 independent path boundary review', () => {
  const astar = new AStarService();
  it('does not treat missing cells inside the bounding rectangle as playable', () => {
    const base = s03Fixture();
    const state = { ...base, boardState: { ...base.boardState,
      cells: base.boardState.cells.map(row => row.map(c => c.x === 1 ? undefined : c)) } };
    expect(astar.findPath(state, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 10).exists).toBe(false);
  });
  it('rejects fractional coordinates even when start equals end', () => {
    expect(astar.findPath(s03Fixture(), 'a', { x: 0.5, y: 0 }, { x: 0.5, y: 0 }, 1).exists).toBe(false);
  });
  it('rejects a start outside the board instead of stepping into the board', () => {
    expect(astar.findPath(s03Fixture(), 'a', { x: -1, y: 0 }, { x: 0, y: 0 }, 1).exists).toBe(false);
  });
  it('does not invent a board when BoardState is missing', () => {
    const state = { ...s03Fixture(), boardState: undefined };
    expect(astar.findPath(state, 'a', { x: 0, y: 0 }, { x: 1, y: 0 }, 1).exists).toBe(false);
  });
  it('direct path execution rejects teleporting without mutating the input', async () => {
    const state = s03Fixture();
    const service = new MovementService(astar, new PathCacheService());
    const result = await service.executeMovement(state, 'a', [{ x: 3, y: 0 }]);
    expect(result.success).toBe(false);
    expect(state.fighters[0].position).toEqual({ x: 0, y: 0 });
  });
  it('both explicit maneuver and direct execution reject a closed door', async () => {
    const base = s03Fixture();
    const state = { ...base, boardState: { ...base.boardState,
      cells: base.boardState.cells.map(row => row.map(c => c.x === 1 && c.y === 0
        ? { ...c, type: 'door' as const, isOpen: false } : c)) } };
    const path = [{ x: 1, y: 0 }, { x: 2, y: 0 }];
    const validator = new GameRulesValidator(new AdjacencyService());
    expect(validator.validateManeuver(state, 'a', undefined, path, 'a').valid).toBe(false);
    const service = new MovementService(astar, new PathCacheService());
    expect((await service.executeMovement(state, 'a', path)).success).toBe(false);
  });
  it.each([['a', true], ['b', false]])('pending MOVE applies the same path rule through owner %s', async (ownerId, success) => {
    const base = s03Fixture();
    const state = { ...base,
      fighters: base.fighters.map(f => f.id === 'helper'
        ? { ...f, ownerId: ownerId as string, position: { x: 1, y: 0 } } : f),
      metadata: { ...base.metadata, pendingEffects: [{ id: 'move', type: 'MOVE' as const,
        playerId: 'a', value: 2 }] } };
    const result = await s03Engine().executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'move', fighterId: 'a', x: 2, y: 0 },
      { gameId: state.gameId, userId: 'a', currentState: state });
    expect(result.success).toBe(success);
    expect(state.fighters[0].position).toEqual({ x: 0, y: 0 });
    if (success) expect(result.gameState!.fighters[0].position).toEqual({ x: 2, y: 0 });
    else expect(state.metadata.pendingEffects).toHaveLength(1);
  });
});
