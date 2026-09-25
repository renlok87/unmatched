import { GameState } from '../models';
import { s03Fixture } from '../../test/fixtures/s03-engine.fixture';
import { AStarService } from './astar.service';
import { MovementService } from '../engine/movement.service';
import { PathCacheService } from './index';
import { AdjacencyService } from '../engine/adjacency.service';
import { GameRulesValidator } from '../validators/game-rules.validator';

type Patch = (f: GameState['fighters'][number]) => GameState['fighters'][number];

function fixture(fighters?: Record<string, Patch>, cells?: (x: number, y: number, cell: GameState['boardState']['cells'][number][number]) => GameState['boardState']['cells'][number][number]): GameState {
  let state: GameState = s03Fixture(0);
  if (fighters) state = { ...state, fighters: state.fighters.map(f => (fighters[f.id] ? fighters[f.id](f) : f)) };
  if (cells) state = { ...state, boardState: { ...state.boardState, cells: state.boardState.cells.map((row, y) => row.map((cell, x) => cells(x, y, cell))) } };
  return state;
}

describe('GD-015: AStarService pathfinding rules', () => {
  const astar = new AStarService();

  it('uses real board bounds instead of hardcoded 12x8', () => {
    const state = fixture();
    // доска 8x2: (0,5) за границей — недостижимо
    expect(astar.findPath(state, 'a', { x: 0, y: 0 }, { x: 0, y: 5 }, 10).exists).toBe(false);
    expect(astar.findPath(state, 'a', { x: 0, y: 0 }, { x: 11, y: 0 }, 10).exists).toBe(false);
    expect(astar.findPath(state, 'a', { x: 0, y: 0 }, { x: 7, y: 1 }, 10).exists).toBe(true);
  });

  it('respects walls and closed doors', () => {
    const walled = fixture(undefined, (x, y, cell) =>
      x === 1 && y === 0 ? { ...cell, type: 'wall' as const } : x === 1 && y === 1 ? { ...cell, type: 'door' as const, isOpen: false } : cell);
    expect(astar.findPath(walled, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 10).exists).toBe(false);
    const opened = fixture(undefined, (x, y, cell) =>
      x === 1 && y === 0 ? { ...cell, type: 'wall' as const } : x === 1 && y === 1 ? { ...cell, type: 'door' as const, isOpen: true } : cell);
    const r = astar.findPath(opened, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 10);
    expect(r.exists).toBe(true);
    expect(r.cost).toBe(4);
  });

  it('may traverse living allies but not living enemies', () => {
    const ally = fixture({ helper: f => ({ ...f, position: { x: 1, y: 0 } }) });
    expect(astar.findPath(ally, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 10).exists).toBe(true);
    const enemy = fixture({ b: f => ({ ...f, position: { x: 1, y: 0 } }) });
    expect(astar.findPath(enemy, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 2).exists).toBe(false);
  });

  it('defeated fighters never block', () => {
    const dead = fixture({ b: f => ({ ...f, health: 0, isDefeated: true, position: { x: 1, y: 0 } }) });
    expect(astar.findPath(dead, 'a', { x: 0, y: 0 }, { x: 1, y: 0 }, 2).exists).toBe(true);
  });

  it('may not end on any living fighter', () => {
    const enemy = fixture({ b: f => ({ ...f, position: { x: 2, y: 0 } }) });
    expect(astar.findPath(enemy, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 10).exists).toBe(false);
    const ally = fixture({ helper: f => ({ ...f, position: { x: 2, y: 0 } }) });
    expect(astar.findPath(ally, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 10).exists).toBe(false);
  });

  it('returned path includes the start cell (documented convention)', () => {
    const state = fixture();
    const r = astar.findPath(state, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, 10);
    expect(r.path).toEqual([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }]);
  });
});

describe('GD-015: MovementService rules', () => {
  let movement: MovementService;
  beforeEach(() => { movement = new MovementService(new AStarService(), new PathCacheService()); });

  it('executeMovement passes through a living ally', async () => {
    const state = fixture({ helper: f => ({ ...f, position: { x: 1, y: 0 } }) });
    const r = await movement.executeMovement(state, 'a', [{ x: 1, y: 0 }, { x: 2, y: 0 }]);
    expect(r.success).toBe(true);
    expect(r.nextState!.fighters[0].position).toEqual({ x: 2, y: 0 });
  });

  it('executeMovement refuses to traverse a living enemy or end on any living fighter', async () => {
    const enemyMid = fixture({ b: f => ({ ...f, position: { x: 1, y: 0 } }) });
    expect((await movement.executeMovement(enemyMid, 'a', [{ x: 1, y: 0 }, { x: 2, y: 0 }])).success).toBe(false);
    const enemyEnd = fixture({ b: f => ({ ...f, position: { x: 2, y: 0 } }) });
    expect((await movement.executeMovement(enemyEnd, 'a', [{ x: 1, y: 0 }, { x: 2, y: 0 }])).success).toBe(false);
    const allyEnd = fixture({ helper: f => ({ ...f, position: { x: 2, y: 0 } }) });
    expect((await movement.executeMovement(allyEnd, 'a', [{ x: 1, y: 0 }, { x: 2, y: 0 }])).success).toBe(false);
  });

  it('executeMovement treats defeated fighters as passable', async () => {
    const state = fixture({ helper: f => ({ ...f, health: 0, isDefeated: true, position: { x: 1, y: 0 } }) });
    expect((await movement.executeMovement(state, 'a', [{ x: 1, y: 0 }, { x: 2, y: 0 }])).success).toBe(true);
  });

  it('findPath returns honest path cost without fake cache shortcuts', async () => {
    const state = fixture();
    const first = await movement.findPath(state, 'a', { x: 0, y: 0 }, { x: 2, y: 0 }, { maxCost: 10 });
    expect(first.cost).toBe(2);
    const second = await movement.findPath(state, 'a', { x: 0, y: 0 }, { x: 1, y: 0 }, { maxCost: 10 });
    expect(second.cost).toBe(1);
    expect(second.path).toEqual([{ x: 0, y: 0 }, { x: 1, y: 0 }]);
  });

  it('getValidMoveTargets excludes occupied endpoints but allows paths through allies', () => {
    const state = fixture({
      helper: f => ({ ...f, position: { x: 1, y: 0 } }),
      b: f => ({ ...f, position: { x: 3, y: 0 } }),
    });
    const targets = movement.getValidMoveTargets(state, 'a', 2)
      .map(p => `${p.x}:${p.y}`).sort();
    expect(targets).toEqual(['0:1', '1:1', '2:0']);
  });
});

describe('GD-015: validator movement rules', () => {
  const validator = new GameRulesValidator(new AdjacencyService());

  it('validateMovement traverses allies, blocks enemies and occupied endpoints', () => {
    const ally = fixture({ helper: f => ({ ...f, position: { x: 1, y: 0 } }) });
    expect(validator.validateMovement(ally, 'a', { x: 2, y: 0 }, 'a')).toEqual({ valid: true });
    expect(validator.validateMovement(ally, 'a', { x: 1, y: 0 }, 'a').valid).toBe(false);
    const enemy = fixture({ b: f => ({ ...f, position: { x: 1, y: 0 } }) });
    expect(validator.validateMovement(enemy, 'a', { x: 2, y: 0 }, 'a').valid).toBe(false);
  });

  it('validateManeuver blocks enemy traversal and occupied endpoints', () => {
    const enemy = fixture({ b: f => ({ ...f, position: { x: 1, y: 0 } }) });
    const through = validator.validateManeuver(enemy, 'a', undefined, [{ x: 1, y: 0 }, { x: 2, y: 0 }], 'a');
    expect(through.valid).toBe(false);
    expect(through.code).toBe('PATH_BLOCKED_BY_ENEMY');
    const allyEnd = fixture({ helper: f => ({ ...f, position: { x: 2, y: 0 } }) });
    const onto = validator.validateManeuver(allyEnd, 'a', undefined, [{ x: 1, y: 0 }, { x: 2, y: 0 }], 'a');
    expect(onto.valid).toBe(false);
    expect(onto.code).toBe('POSITION_OCCUPIED');
    const allyMid = fixture({ helper: f => ({ ...f, position: { x: 1, y: 0 } }) });
    expect(validator.validateManeuver(allyMid, 'a', undefined, [{ x: 1, y: 0 }, { x: 2, y: 0 }], 'a')).toEqual({ valid: true });
  });
});

describe('GD-015: AdjacencyService.isInSameZone uses zones[] with legacy fallback', () => {
  const adjacency = new AdjacencyService();
  const board = (a: any, b: any) => {
    const cells: any[][] = Array.from({ length: 2 }, (_r, y) => Array.from({ length: 8 }, (_c, x) => ({ x, y, type: 'normal' })));
    cells[0][0] = { ...cells[0][0], ...a };
    cells[0][5] = { ...cells[0][5], ...b };
    return { boardState: { width: 8, height: 2, cells, doors: {}, fog: {}, tokens: {} } } as any;
  };

  it('matches via secondary zone intersection', () => {
    expect(adjacency.isInSameZone(board({ zones: ['z1', 'z2'] }, { zones: ['z2', 'z3'] }), { x: 0, y: 0 }, { x: 5, y: 0 })).toBe(true);
  });

  it('matches via legacy zone field', () => {
    expect(adjacency.isInSameZone(board({ zone: 'legacy' }, { zone: 'legacy' }), { x: 0, y: 0 }, { x: 5, y: 0 })).toBe(true);
  });

  it('false for disjoint zones and zoneless cells', () => {
    expect(adjacency.isInSameZone(board({ zones: ['z1'] }, { zones: ['z9'] }), { x: 0, y: 0 }, { x: 5, y: 0 })).toBe(false);
    expect(adjacency.isInSameZone(board({}, {}), { x: 0, y: 0 }, { x: 5, y: 0 })).toBe(false);
  });
});
