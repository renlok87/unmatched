/**
 * MS-AT-01 (MS-R-41): computeReach / canonicalPath / evaluateDraft on
 * hand-made boards and on every golden fixture of
 * backend/prisma/fixtures/movement. Manual fixtures hold expectations written
 * by hand from the rules; generated ones are regression data
 * (backend/scripts/gen-move-fixtures.ts).
 */
import type { BoardState, Cell, Fighter, Position } from '../models';
import { FighterType } from '../models';
import {
  canonicalKey,
  canonicalPath,
  compareCanonical,
  computeReach,
  evaluateDraft,
  isEndpoint,
  reachableEndpoints,
  reachTiers,
} from './canonical-path';
import {
  computeFixtureExpect,
  loadMoveFixtures,
  topologyStaleness,
  type Cell2,
  type MoveFixture,
} from '../../test/fixtures/move-fixture-state';

const p = (x: number, y: number): Position => ({ x, y });

function grid(width: number, height: number, walls: Position[] = []): BoardState {
  const cells: Cell[][] = [];
  for (let y = 0; y < height; y++) {
    const row: Cell[] = [];
    for (let x = 0; x < width; x++) {
      row.push({ x, y, type: walls.some((w) => w.x === x && w.y === y) ? 'wall' : 'normal' });
    }
    cells.push(row);
  }
  return { width, height, cells, doors: {}, fog: {}, tokens: {} };
}

function fighter(
  id: string,
  ownerId: string,
  pos: Position,
  extra: Partial<Fighter> = {},
): Fighter {
  return {
    id,
    ownerId,
    heroId: ownerId,
    name: id,
    type: FighterType.HERO,
    health: 10,
    maxHealth: 10,
    position: pos,
    effects: [],
    hasSidekick: false,
    movement: 2,
    ...extra,
  };
}

/**
 * Graph board 4x2 (letters are spaceIds; (2,0) is an obstacle hole):
 *   y=0   D -- E ====#==== C       E-C: one long link over the hole
 *   y=1   A -- B -- F ---- G
 * Links: D-E, E-C, D-A, A-B, B-F, F-G, G-C, E-B.
 * From D: D-E-C-G is the only shortest way to G (3); F has two (D-E-B-F, D-A-B-F).
 * The tie at B is decided by the spaceId part of K alone: A (0,1) < E (1,0),
 * while (y, x) would prefer E.
 */
function graphBoard(order: 'declared' | 'reversed' = 'declared'): BoardState {
  const ids: Record<string, Position> = {
    D: p(0, 0),
    E: p(1, 0),
    C: p(3, 0),
    A: p(0, 1),
    B: p(1, 1),
    F: p(2, 1),
    G: p(3, 1),
  };
  const edges: [string, string][] = [
    ['D', 'E'],
    ['E', 'C'],
    ['D', 'A'],
    ['A', 'B'],
    ['B', 'F'],
    ['F', 'G'],
    ['G', 'C'],
    ['E', 'B'],
  ];
  const links = new Map<string, Position[]>();
  for (const [u, v] of edges) {
    links.set(u, [...(links.get(u) ?? []), ids[v]]);
    links.set(v, [...(links.get(v) ?? []), ids[u]]);
  }
  const cells: Cell[][] = [0, 1].map((y) =>
    [0, 1, 2, 3].map((x) => {
      const id = Object.keys(ids).find((k) => ids[k].x === x && ids[k].y === y);
      if (!id) return { x, y, type: 'obstacle' } as Cell;
      const l = links.get(id) ?? [];
      return {
        x,
        y,
        type: 'normal',
        spaceId: id,
        links: order === 'declared' ? l : [...l].reverse(),
      } as Cell;
    }),
  );
  return { width: 4, height: 2, cells, doors: {}, fog: {}, tokens: {} };
}

describe('canonical-path: computeReach', () => {
  it('BFS within maxSteps on a grid; start has 0; walls are not entered', () => {
    const board = grid(4, 3, [p(1, 0)]);
    const state = { boardState: board, fighters: [fighter('a', 'p1', p(0, 0))] };
    const reach = computeReach(state, 'a', 2);
    expect(Object.fromEntries(reach.dist)).toEqual({ '0:0': 0, '0:1': 1, '1:1': 2, '0:2': 2 });
    expect(reach.start).toEqual(p(0, 0));
    expect(reach.ownerId).toBe('p1');
  });

  it('living enemies block, allies and defeated fighters do not; passThroughEnemies lifts the block', () => {
    const board = grid(5, 1);
    const fighters = [
      fighter('a', 'p1', p(0, 0)),
      fighter('ally', 'p1', p(1, 0)),
      fighter('dead', 'p2', p(2, 0), { health: 0 }),
      fighter('dirty', 'p2', p(3, 0), { isDefeated: true }),
      fighter('enemy', 'p2', p(4, 0)),
    ];
    const state = { boardState: board, fighters };
    expect([...computeReach(state, 'a', 9).dist.keys()]).toEqual(['0:0', '1:0', '2:0', '3:0']);
    expect([...computeReach(state, 'a', 9, { passThroughEnemies: true }).dist.keys()]).toHaveLength(
      5,
    );
  });

  it('enemies are relative to the MOVED fighter (an effect moving the opponent)', () => {
    const board = grid(3, 1);
    const fighters = [fighter('mine', 'p1', p(1, 0)), fighter('theirs', 'p2', p(0, 0))];
    const reach = computeReach({ boardState: board, fighters }, 'theirs', 5);
    expect([...reach.dist.keys()]).toEqual(['0:0']);
  });

  it('maxSteps 0 reaches only the start; Infinity is unbounded; no board → only the start', () => {
    const board = grid(3, 3);
    const fighters = [fighter('a', 'p1', p(1, 1))];
    expect(computeReach({ boardState: board, fighters }, 'a', 0).dist.size).toBe(1);
    expect(computeReach({ boardState: board, fighters }, 'a', Infinity).dist.size).toBe(9);
    expect(computeReach({ boardState: undefined, fighters }, 'a', 5).dist.size).toBe(1);
  });

  it('throws for an unknown mover', () => {
    expect(() => computeReach({ boardState: grid(2, 2), fighters: [] }, 'x', 1)).toThrow(
      /not on the board/,
    );
  });

  it('on a graph board only links are steps; a long link is one step', () => {
    const state = { boardState: graphBoard(), fighters: [fighter('a', 'p1', p(0, 0))] };
    const reach = computeReach(state, 'a', 2);
    expect(Object.fromEntries(reach.dist)).toEqual({
      '0:0': 0, // D
      '1:0': 1, // E
      '0:1': 1, // A
      '3:0': 2, // C over the hole
      '1:1': 2, // B
    });
  });
});

describe('canonical-path: canonicalPath and K', () => {
  it('K is (y, x) on a grid and (spaceId, y, x) on a graph board', () => {
    expect(canonicalKey(grid(2, 2), p(1, 0))).toEqual(['', 0, 1]);
    expect(canonicalKey(graphBoard(), p(3, 1))).toEqual(['G', 1, 3]);
    expect(compareCanonical(grid(3, 3), p(2, 0), p(0, 1))).toBeLessThan(0);
    // ordinal: 'B' (1,1) < 'C' (3,0) although C has the smaller y
    expect(compareCanonical(graphBoard(), p(1, 1), p(3, 0))).toBeLessThan(0);
  });

  it('[] for the start, null for unreached or occupied ends, no start cell in the path', () => {
    const board = grid(4, 1);
    const fighters = [fighter('a', 'p1', p(0, 0)), fighter('ally', 'p1', p(1, 0))];
    const state = { boardState: board, fighters };
    const reach = computeReach(state, 'a', 2);
    expect(canonicalPath(reach, state, p(0, 0))).toEqual([]);
    expect(canonicalPath(reach, state, p(1, 0))).toBeNull(); // ally: passable, not an end
    expect(canonicalPath(reach, state, p(2, 0))).toEqual([p(1, 0), p(2, 0)]);
    expect(canonicalPath(reach, state, p(3, 0))).toBeNull(); // 3 steps > 2
    expect(isEndpoint(state, reach, p(1, 0))).toBe(false);
    expect(isEndpoint(state, reach, p(0, 0))).toBe(true);
  });

  it('ties go to the predecessor with the smallest K (grid: lower row first)', () => {
    const state = { boardState: grid(3, 3), fighters: [fighter('a', 'p1', p(0, 0))] };
    const reach = computeReach(state, 'a', 4);
    expect(canonicalPath(reach, state, p(2, 2))).toEqual([p(1, 0), p(2, 0), p(2, 1), p(2, 2)]);
    expect(canonicalPath(reach, state, p(1, 1))).toEqual([p(1, 0), p(1, 1)]);
  });

  it('graph tie: D to F has D-E-B-F and D-A-B-F; spaceId decides: A (0,1) beats E (1,0)', () => {
    const state = { boardState: graphBoard(), fighters: [fighter('a', 'p1', p(0, 0))] };
    const reach = computeReach(state, 'a', 3);
    // (y, x) first would give E: [(1,0), (1,1), (2,1)]
    expect(canonicalPath(reach, state, p(2, 1))).toEqual([p(0, 1), p(1, 1), p(2, 1)]);
    // G: D-E-C-G (3) is the only shortest; F-G would be 4
    expect(canonicalPath(reach, state, p(3, 1))).toEqual([p(1, 0), p(3, 0), p(3, 1)]);
  });

  it('does not depend on the order of links', () => {
    const fighters = [fighter('a', 'p1', p(0, 0))];
    const s1 = { boardState: graphBoard('declared'), fighters };
    const s2 = { boardState: graphBoard('reversed'), fighters };
    const r1 = computeReach(s1, 'a', 9);
    const r2 = computeReach(s2, 'a', 9);
    expect(new Map(r1.dist)).toEqual(new Map(r2.dist));
    for (const e of reachableEndpoints(s1, r1)) {
      expect(canonicalPath(r2, s2, e)).toEqual(canonicalPath(r1, s1, e));
    }
  });

  it('passThroughEnemies routes through an enemy but never ends on one', () => {
    const board = grid(3, 1);
    const fighters = [fighter('a', 'p1', p(0, 0)), fighter('e', 'p2', p(1, 0))];
    const state = { boardState: board, fighters };
    const reach = computeReach(state, 'a', 2, { passThroughEnemies: true });
    expect(canonicalPath(reach, state, p(2, 0))).toEqual([p(1, 0), p(2, 0)]);
    expect(canonicalPath(reach, state, p(1, 0))).toBeNull();
  });
});

describe('canonical-path: tiers and evaluateDraft (04 §3.2)', () => {
  const board = grid(8, 1);

  it('reachTiers splits base and boost by distance, ends only', () => {
    const fighters = [fighter('a', 'p1', p(0, 0)), fighter('ally', 'p1', p(2, 0))];
    const state = { boardState: board, fighters };
    const reach = computeReach(state, 'a', 5);
    expect(reachTiers(state, reach, 3, 5)).toEqual({
      base: [p(1, 0), p(3, 0)],
      boost: [p(4, 0), p(5, 0)],
    });
  });

  it('required boost is absolute from the base; a small card leaves NeedBoost(3) (MS-E-78)', () => {
    const fighters = [fighter('a', 'p1', p(0, 0), { movement: 3 })];
    const hand = [
      { id: 'c2', boostValue: 2 },
      { id: 'c4', boostValue: 4 },
      { id: 'cn', boostValue: null },
    ];
    const ev = evaluateDraft(
      { boardState: board, fighters },
      { moves: [{ fighterId: 'a', dest: p(6, 0) }], boostCardId: 'c2' },
      hand,
    );
    expect(ev.selectedBoost).toBe(2);
    expect(ev.maxBoost).toBe(4);
    expect(ev.moves[0]).toMatchObject({ status: 'needBoost', requiredBoost: 3, base: 3 });
    expect(ev.moves[0].path).toHaveLength(6);
    expect(ev.moves[0].reach.base.map((c) => c.x)).toEqual([1, 2, 3, 4, 5]);
    expect(ev.moves[0].reach.boost.map((c) => c.x)).toEqual([6, 7]);
  });

  it('a null BOOST counts as 0 and does not raise the boost tier (MS-E-07)', () => {
    const fighters = [fighter('a', 'p1', p(0, 0), { movement: 1 })];
    const ev = evaluateDraft(
      { boardState: board, fighters },
      { moves: [{ fighterId: 'a', dest: p(2, 0) }], boostCardId: 'cn' },
      [{ id: 'cn', boostValue: null }],
    );
    expect(ev).toMatchObject({ selectedBoost: 0, maxBoost: 0 });
    expect(ev.moves[0]).toMatchObject({ status: 'conflict', conflict: 'no-path' });
  });

  it('moves see the positions after the previous moves (MS-E-33/34)', () => {
    const fighters = [fighter('a', 'p1', p(1, 0)), fighter('b', 'p1', p(0, 0))];
    const state = { boardState: board, fighters };
    const aThenB = evaluateDraft(
      state,
      {
        moves: [
          { fighterId: 'a', dest: p(2, 0) },
          { fighterId: 'b', dest: p(1, 0) },
        ],
      },
      [],
    );
    expect(aThenB.moves.map((m) => m.status)).toEqual(['ok', 'ok']);
    expect(aThenB.fighters.find((f) => f.id === 'b').position).toEqual(p(1, 0));
    const bThenA = evaluateDraft(
      state,
      {
        moves: [
          { fighterId: 'b', dest: p(1, 0) },
          { fighterId: 'a', dest: p(2, 0) },
        ],
      },
      [],
    );
    expect(bThenA.moves.map((m) => m.status)).toEqual(['conflict', 'ok']);
  });

  it('mover gates: immobilized, health 0, another owner, duplicate, missing; isDefeated with health > 0 moves (MS-E-77)', () => {
    const fighters = [
      fighter('imm', 'p1', p(0, 0), { effects: [{ type: 'immobilized' }] }),
      fighter('dead', 'p1', p(2, 0), { health: 0 }),
      fighter('dirty', 'p1', p(4, 0), { isDefeated: true }),
      fighter('foe', 'p2', p(7, 0)),
    ];
    const ev = evaluateDraft(
      { boardState: board, fighters },
      {
        moves: [
          { fighterId: 'imm', dest: p(1, 0) },
          { fighterId: 'dead', dest: p(3, 0) },
          { fighterId: 'dirty', dest: p(5, 0) },
          { fighterId: 'foe', dest: p(6, 0) },
          { fighterId: 'dirty', dest: p(6, 0) },
          { fighterId: 'ghost', dest: p(6, 0) },
        ],
      },
      [],
      'p1',
    );
    expect(ev.moves.map((m) => m.conflict ?? m.status)).toEqual([
      'immobilized',
      'defeated',
      'ok',
      'not-yours',
      'duplicate',
      'missing',
    ]);
  });

  it('getFighterMovement on the raw value decides the base (MS-E-04, MS-E-107)', () => {
    const base = (movement: unknown) =>
      evaluateDraft(
        {
          boardState: board,
          fighters: [fighter('a', 'p1', p(0, 0), { movement: movement as number })],
        },
        { moves: [{ fighterId: 'a', dest: p(1, 0) }] },
        [],
      ).moves[0].base;
    expect([0, null, undefined, 2.5, 3.5, '3', '3.5', 3].map(base)).toEqual([
      2, 2, 2, 2, 2, 3, 2, 3,
    ]);
  });
});

// ---------------------------------------------------------------------------
// Golden fixtures
// ---------------------------------------------------------------------------

const FIXTURES = loadMoveFixtures();
const sortCells = (cells: readonly Cell2[]): Cell2[] =>
  [...cells].sort((a, b) => a[1] - b[1] || a[0] - b[0]);

describe('canonical-path: golden fixture set', () => {
  it('has at least 40 fixtures, 15 manual, on Cobble, Marmoreal and Sarpedon', () => {
    expect(FIXTURES.length).toBeGreaterThanOrEqual(40);
    expect(FIXTURES.filter((f) => f.expectSource === 'manual').length).toBeGreaterThanOrEqual(15);
    const boards = new Set(FIXTURES.map((f) => f.board.key));
    for (const key of ['cobble-5x6', 'marmoreal', 'sarpedon']) expect(boards).toContain(key);
  });
});

describe.each(
  FIXTURES.filter((f) => f.draft || f.pending?.type === 'MOVE').map((f) => [f.name, f] as const),
)('MS-AT-01 %s', (_name: string, fx: MoveFixture) => {
  it(`${fx.expectSource}: reach, path, status and required boost match`, () => {
    expect(topologyStaleness(fx)).toBeNull();
    const got = computeFixtureExpect(fx);
    const want = fx.expect;
    if (want.reach) {
      const norm = (r: Record<string, { base: Cell2[]; boost: Cell2[] }>) =>
        Object.fromEntries(
          Object.entries(r).map(([id, t]) => [
            id,
            { base: sortCells(t.base), boost: sortCells(t.boost) },
          ]),
        );
      expect(norm(got.reach)).toEqual(norm(want.reach));
    }
    if (want.paths) expect(got.paths).toEqual(want.paths);
    if (want.status) expect(got.status).toEqual(want.status);
    if (want.requiredBoost) expect(got.requiredBoost).toEqual(want.requiredBoost);
  });
});
