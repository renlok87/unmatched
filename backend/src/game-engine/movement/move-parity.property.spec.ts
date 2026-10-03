/**
 * MS-AT-06 (MS-R-42): property test over 500 seeded random states on Cobble
 * 5x6, Marmoreal, Sarpedon and walled 7x7 grids.
 *
 * For every state (random fighters of two owners, living / defeated / dirty
 * "isDefeated with health > 0", random raw movement and boost card):
 *  1. computeReach equals the legacy AdjacencyService.getReachableCells +
 *     blockedPositions call that resolvePendingEffect / validateMovement used
 *     before MS-T-02 (with and without passThroughEnemies);
 *  2. every canonical path is a shortest simple path along links and
 *     GameRulesValidator.validateManeuver accepts it (client not softer);
 *  3. ALL simple paths of length 1..allowance from the start (DFS over the
 *     neighbour graph, walls included) are enumerated: any path the
 *     validator accepts ends on a reach endpoint no farther than its length,
 *     i.e. every space outside the reach is rejected on every simple path
 *     (client not stricter);
 *  4. dist and canonical paths do not change when every cell's links are
 *     shuffled (on a grid: the same graph given as shuffled explicit links).
 */
import type { BoardState, Cell, GameState, Position } from '../models';
import { getFighterMovement } from '../models';
import { neighbours, posKey } from '../engine/board-topology';
import { AdjacencyService } from '../engine/adjacency.service';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { isLivingFighter } from './traversal';
import {
  canonicalPath,
  computeReach,
  isPassableSpace,
  reachableEndpoints,
  reachDistance,
} from './canonical-path';
import {
  boardStateFor,
  buildMoveFixtureState,
  currentTopologySha256,
  type MoveFixture,
  type MoveFixtureBoard,
  type MoveFixtureFighter,
} from '../../test/fixtures/move-fixture-state';

const SEED = 0x5eed0302;
const STATES = 500;

/** mulberry32 — small deterministic PRNG */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const adjacency = new AdjacencyService();
const validator = new GameRulesValidator(adjacency);

function walledGrids(random: () => number): MoveFixtureBoard[] {
  return [0, 1, 2, 3].map((n) => {
    const walls: [number, number][] = [];
    for (let y = 0; y < 7; y++) for (let x = 0; x < 7; x++) if (random() < 0.2) walls.push([x, y]);
    return { key: `walls-7x7-${n}`, lattice: { width: 7, height: 7, walls } };
  });
}

const pick = <T>(random: () => number, items: readonly T[]): T =>
  items[Math.floor(random() * items.length)];

function shuffled<T>(random: () => number, items: readonly T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** The same graph with every cell's links listed in a random order (grids get explicit links). */
function withShuffledLinks(board: BoardState, random: () => number): BoardState {
  const cells: Cell[][] = board.cells.map((row) =>
    row.map((cell) => ({
      ...cell,
      links: shuffled(random, neighbours(board, { x: cell.x, y: cell.y })),
    })),
  );
  return { ...board, cells };
}

interface RandomState {
  state: GameState;
  moverId: string;
  ownerId: string;
  boostCardId?: string;
  allowance: number;
  passThrough: boolean;
}

function randomState(random: () => number, board: MoveFixtureBoard, index: number): RandomState {
  const engineBoard = boardStateFor(board);
  const spaces: Position[] = [];
  for (const row of engineBoard.cells)
    for (const c of row) if (isPassableSpace(engineBoard, c)) spaces.push({ x: c.x, y: c.y });
  const cells = shuffled(random, spaces);
  const count = 2 + Math.floor(random() * 6);
  const fighters: MoveFixtureFighter[] = [];
  for (let i = 0; i < count && i < cells.length; i++) {
    const ownerId = i === 0 ? 'p1' : random() < 0.5 ? 'p1' : 'p2';
    const roll = random();
    const health = i > 0 && roll < 0.15 ? 0 : 1 + Math.floor(random() * 10);
    const isDefeated = health === 0 || (i > 0 && roll > 0.9);
    // B33: a defeated fighter may lie under a living one
    const position = isDefeated && i > 1 && random() < 0.3 ? fighters[1].position : cells[i];
    fighters.push({
      id: `f${i}`,
      ownerId,
      position,
      type: 'MINION',
      health,
      isDefeated,
      movement: pick(random, [1, 2, 3, undefined, 0, 2.5, '3', 3]),
    });
  }
  // the mover: f0 (p1, alive); sometimes dirty isDefeated with health > 0 (MS-E-77)
  fighters[0].isDefeated = random() < 0.1;
  const boost = pick(random, [undefined, null, 0, 1, 2, 3, 4, 6]);
  const hand = boost === undefined ? [] : [{ id: 'boost', boostValue: boost }];
  const fx: MoveFixture = {
    schema: 'unmatched.move-fixture/1',
    name: `property-${index}`,
    expectSource: 'generated',
    board,
    fighters,
    hand,
    expect: { layer: 'validator', server: '' },
  };
  const state = buildMoveFixtureState(fx);
  const mover = state.fighters[0];
  let allowance = getFighterMovement(mover) + (typeof boost === 'number' ? boost : 0);
  if (board.lattice && board.lattice.width * board.lattice.height > 40)
    allowance = Math.min(allowance, 7);
  return {
    state,
    moverId: mover.id,
    ownerId: mover.ownerId,
    boostCardId: boost === undefined ? undefined : 'boost',
    allowance,
    passThrough: random() < 0.3,
  };
}

/** Legacy call of resolvePendingEffect / validateMovement before MS-T-02 */
function legacyReach(rs: RandomState, passThrough: boolean): Map<string, number> {
  const { state, moverId, ownerId, allowance } = rs;
  const mover = state.fighters.find((f) => f.id === moverId);
  const blockedPositions = passThrough
    ? new Set<string>()
    : new Set(
        state.fighters
          .filter((f) => f.id !== moverId && isLivingFighter(f) && f.ownerId !== ownerId)
          .map((f) => `${f.position.x}:${f.position.y}`),
      );
  const legacy = adjacency.getReachableCells(state.boardState, mover.position, allowance, {
    blockedPositions,
  });
  return new Map([...legacy.entries()].map(([k, v]) => [k, v.cost]));
}

const sortedEntries = (m: ReadonlyMap<string, number>) =>
  [...m.entries()].sort(([a], [b]) => (a < b ? -1 : 1));

function* simplePaths(board: BoardState, start: Position, maxLen: number): Generator<Position[]> {
  const path: Position[] = [];
  const seen = new Set<string>([posKey(start)]);
  function* walk(from: Position): Generator<Position[]> {
    if (path.length === maxLen) return;
    for (const next of neighbours(board, from)) {
      const k = posKey(next);
      if (seen.has(k)) continue;
      seen.add(k);
      path.push(next);
      yield [...path];
      yield* walk(next);
      path.pop();
      seen.delete(k);
    }
  }
  yield* walk(start);
}

const random = rng(SEED);
const BOARDS: MoveFixtureBoard[] = [
  { key: 'cobble-5x6', lattice: { width: 5, height: 6 } },
  { key: 'marmoreal', topologySha256: currentTopologySha256({ key: 'marmoreal' }) },
  { key: 'sarpedon', topologySha256: currentTopologySha256({ key: 'sarpedon' }) },
  ...walledGrids(random),
];

describe(`MS-AT-06 property: ${STATES} random states, seed 0x${SEED.toString(16)}`, () => {
  const stats = { states: 0, canonical: 0, simplePaths: 0, accepted: 0 };

  it('canonical paths are accepted, every out-of-reach space is rejected on every simple path, legacy BFS agrees', () => {
    for (let i = 0; i < STATES; i++) {
      // a quarter per map (Cobble, Marmoreal, Sarpedon), the last quarter over the walled grids
      const board =
        i % 4 < 3 ? BOARDS[i % 4] : BOARDS[3 + (Math.floor(i / 4) % (BOARDS.length - 3))];
      const rs = randomState(random, board, i);
      const { state, moverId, ownerId, boostCardId, allowance } = rs;
      const where = `state ${i} on ${board.key} (allowance ${allowance})`;
      stats.states++;

      // 1. the canonical BFS is the legacy BFS, with and without passThroughEnemies
      for (const passThrough of [false, rs.passThrough]) {
        const reach = computeReach(state, moverId, allowance, { passThroughEnemies: passThrough });
        const dist = new Map(reach.dist);
        dist.delete(posKey(reach.start));
        expect({ where, passThrough, dist: sortedEntries(dist) }).toEqual({
          where,
          passThrough,
          dist: sortedEntries(legacyReach(rs, passThrough)),
        });
      }

      // 2. client not softer: canonical paths are shortest, simple, linked and accepted
      const reach = computeReach(state, moverId, allowance);
      const endpoints = reachableEndpoints(state, reach);
      for (const end of endpoints) {
        const path = canonicalPath(reach, state, end);
        stats.canonical++;
        expect({ where, end, len: path.length }).toEqual({
          where,
          end,
          len: reachDistance(reach, end),
        });
        expect(new Set([reach.start, ...path].map(posKey)).size).toBe(path.length + 1);
        const verdict = validator.validateManeuver(state, moverId, boostCardId, path, ownerId);
        expect({ where, end, path, verdict }).toEqual({
          where,
          end,
          path,
          verdict: { valid: true },
        });
      }

      // 3. client not stricter: anything the validator accepts ends inside the reach
      const endKeys = new Set(endpoints.map(posKey));
      for (const path of simplePaths(state.boardState, reach.start, allowance)) {
        stats.simplePaths++;
        if (!validator.validateManeuver(state, moverId, boostCardId, path, ownerId).valid) continue;
        stats.accepted++;
        const end = path[path.length - 1];
        const d = reachDistance(reach, end);
        expect({
          where,
          path,
          inReach: endKeys.has(posKey(end)) && d !== undefined && d <= path.length,
        }).toEqual({
          where,
          path,
          inReach: true,
        });
      }

      // 4. independent of the order of links
      const shuffledState = { ...state, boardState: withShuffledLinks(state.boardState, random) };
      const reach2 = computeReach(shuffledState, moverId, allowance);
      expect(sortedEntries(reach2.dist)).toEqual(sortedEntries(reach.dist));
      for (const end of endpoints) {
        expect(canonicalPath(reach2, shuffledState, end)).toEqual(canonicalPath(reach, state, end));
      }
    }
    // the generator really produced work on every axis
    expect(stats.states).toBe(STATES);
    expect(stats.canonical).toBeGreaterThan(STATES);
    expect(stats.accepted).toBeGreaterThan(stats.canonical);
    expect(stats.simplePaths).toBeGreaterThan(stats.accepted);
  }, 240_000);
});
