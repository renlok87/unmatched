/**
 * MS-T-02 — generator of the GENERATED golden move fixtures
 * (backend/prisma/fixtures/movement/*.move-fixture.json, format
 * unmatched.move-fixture/1 — docs/game-design/move-selection/04-technical-design.md §4.8).
 *
 * A scenario below is the fixture input (board, fighters, hand, draft or
 * pending, layer). The generator fills `expect` from the code under test:
 * reach / paths / status / requiredBoost from movement/canonical-path.ts and
 * `server` by running the layer (dto / validator / executor / resolvePending).
 * For these fixtures MS-AT-01/02 are therefore REGRESSION checks; the
 * independent expectations live in the manual fixtures (expectSource
 * "manual"), which this script never writes.
 *
 * Topology maps are pinned by the sha256 of backend/prisma/fixtures/boards/
 * <map>.topology.json (MS-R-67): after a topology change run --write, review
 * the diff and re-check the manual fixtures of that map by hand.
 *
 * Usage (from backend/):
 *   node node_modules/ts-node/dist/bin.js --transpile-only scripts/gen-move-fixtures.ts --check
 *   node node_modules/ts-node/dist/bin.js --transpile-only scripts/gen-move-fixtures.ts --write
 * --check (default) exits 1 when a generated file is missing or differs.
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import {
  computeFixtureExpect,
  currentTopologySha256,
  loadMoveFixtures,
  MOVE_FIXTURE_DIR,
  MOVE_FIXTURE_SCHEMA,
  MOVE_FIXTURE_SUFFIX,
  runFixtureLayer,
  topologyFile,
  type MoveFixture,
  type MoveFixtureBoard,
  type MoveFixtureDraft,
  type MoveFixtureExpect,
  type MoveFixtureFighter,
  type MoveFixtureHandCard,
  type MoveFixtureLayer,
  type MoveFixturePending,
  type XY,
} from '../src/test/fixtures/move-fixture-state';

// ---------------------------------------------------------------------------
// Boards and helpers
// ---------------------------------------------------------------------------

export type BoardRef = 'cobble' | 'grid20' | 'marmoreal' | 'sarpedon';

function boardOf(ref: BoardRef): MoveFixtureBoard {
  if (ref === 'cobble') return { key: 'cobble-5x6', lattice: { width: 5, height: 6 } };
  if (ref === 'grid20') return { key: 'grid-20x20', lattice: { width: 20, height: 20 } };
  return { key: ref, topologySha256: currentTopologySha256({ key: ref }) };
}

const spaceCache = new Map<string, Map<string, XY>>();
/** Position of a space id (M01..M31, S01..S38) on its map */
function at(id: string): XY {
  const map = id.startsWith('M') ? 'marmoreal' : 'sarpedon';
  let spaces = spaceCache.get(map);
  if (!spaces) {
    const fx = JSON.parse(readFileSync(topologyFile(map), 'utf8')) as {
      spaces: { id: string; x: number; y: number }[];
    };
    spaces = new Map(fx.spaces.map((s) => [s.id, { x: s.x, y: s.y }]));
    spaceCache.set(map, spaces);
  }
  const p = spaces.get(id);
  if (!p) throw new Error(`unknown space ${id}`);
  return p;
}

const xy = (x: number, y: number): XY => ({ x, y });
const pos = (p: string | XY): XY => (typeof p === 'string' ? at(p) : p);

function fighter(
  id: string,
  ownerId: string,
  where: string | XY,
  extra: Partial<MoveFixtureFighter> = {},
): MoveFixtureFighter {
  return { id, ownerId, position: pos(where), ...extra };
}
const medusa = (where: string | XY, extra: Partial<MoveFixtureFighter> = {}) =>
  fighter('medusa', 'p1', where, {
    name: 'Medusa',
    type: 'HERO',
    health: 16,
    movement: 3,
    ...extra,
  });
const harpy = (n: number, where: string | XY, extra: Partial<MoveFixtureFighter> = {}) =>
  fighter(`harpy-${n}`, 'p1', where, {
    name: `Harpy ${n}`,
    type: 'MINION',
    health: 1,
    movement: 3,
    ...extra,
  });
const arthur = (where: string | XY, extra: Partial<MoveFixtureFighter> = {}) =>
  fighter('arthur', 'p2', where, {
    name: 'King Arthur',
    type: 'HERO',
    health: 18,
    movement: 2,
    ...extra,
  });
const merlin = (where: string | XY, extra: Partial<MoveFixtureFighter> = {}) =>
  fighter('merlin', 'p2', where, {
    name: 'Merlin',
    type: 'MINION',
    health: 7,
    movement: 2,
    ...extra,
  });

const card = (id: string, boostValue: number | null): MoveFixtureHandCard => ({ id, boostValue });
const to = (fighterId: string, dest: string | XY) => ({ fighterId, dest: pos(dest) });
const forced = (fighterId: string, ...path: (string | XY)[]) => ({
  fighterId,
  path: path.map(pos),
});

export interface Scenario {
  name: string;
  description: string;
  cases: string[];
  board: BoardRef;
  layer: MoveFixtureLayer;
  actor?: string;
  fighters: MoveFixtureFighter[];
  hand?: MoveFixtureHandCard[];
  draft?: MoveFixtureDraft;
  pending?: MoveFixturePending;
  pendingRuleChange?: MoveFixtureExpect['pendingRuleChange'];
}

// ---------------------------------------------------------------------------
// Scenarios (06 §6.1 groups); manual fixtures cover the remaining rows
// ---------------------------------------------------------------------------

const MARMOREAL_UNLINKED: [string, string][] = [
  ['M02', 'M08'],
  ['M03', 'M09'],
  ['M05', 'M10'],
  ['M06', 'M11'],
  ['M13', 'M14'],
  ['M14', 'M21'],
  ['M15', 'M22'],
  ['M17', 'M21'],
  ['M17', 'M25'],
  ['M18', 'M23'],
  ['M18', 'M26'],
  ['M19', 'M23'],
  ['M25', 'M28'],
  ['M26', 'M30'],
];
const SARPEDON_UNLINKED: [string, string][] = [
  ['S14', 'S15'],
  ['S19', 'S24'],
  ['S19', 'S29'],
  ['S26', 'S27'],
  ['S32', 'S35'],
];

const unlinkedScenarios = (pairs: [string, string][], enemyAt: string): Scenario[] =>
  pairs.map(([a, b]) => ({
    name: `topology-${a.startsWith('M') ? 'marmoreal' : 'sarpedon'}-unlinked-${a}-${b}`,
    description: `${a} and ${b} are lattice neighbours without a line: not a step (forced one-step path is INVALID_STEP)`,
    cases: ['MS-E-25'],
    board: a.startsWith('M') ? 'marmoreal' : 'sarpedon',
    layer: 'executor',
    fighters: [medusa(a, { movement: 1 }), arthur(enemyAt)],
    draft: { moves: [forced('medusa', b)] },
  }));

const DATA_MOVEMENT: [string, unknown][] = [
  ['zero', 0],
  ['null', null],
  ['fraction-2-5', 2.5],
  ['fraction-3-5', 3.5],
  ['string-3', '3'],
  ['string-3-5', '3.5'],
];

export const SCENARIOS: Scenario[] = [
  // --- basic-* (MS-E-01..03) ---
  {
    name: 'basic-cobble-move2',
    description: 'movement 2 on Cobble 5x6: base plates and a 2-step move',
    cases: ['MS-E-01'],
    board: 'cobble',
    layer: 'executor',
    fighters: [medusa(xy(2, 2), { movement: 2 }), arthur(xy(4, 5))],
    draft: { moves: [to('medusa', xy(3, 3))] },
  },
  {
    name: 'basic-cobble-move3-edge',
    description: 'movement 3 from the corner of Cobble 5x6: plates clipped by the board edge',
    cases: ['MS-E-01'],
    board: 'cobble',
    layer: 'executor',
    fighters: [medusa(xy(4, 5)), arthur(xy(0, 0))],
    draft: { moves: [to('medusa', xy(2, 4))] },
  },
  {
    name: 'basic-grid20-edge',
    description: 'movement 2 from the corner (0,0) of a 20x20 grid',
    cases: ['MS-E-01'],
    board: 'grid20',
    layer: 'executor',
    fighters: [medusa(xy(0, 0), { movement: 2 }), arthur(xy(19, 19))],
    draft: { moves: [to('medusa', xy(1, 1))] },
  },
  {
    name: 'basic-grid20-allowance7',
    description: 'usual maximum allowance 3 + 4 = 7 on a 20x20 grid',
    cases: ['MS-E-02'],
    board: 'grid20',
    layer: 'executor',
    fighters: [medusa(xy(10, 10)), arthur(xy(0, 0))],
    hand: [card('c4', 4)],
    draft: { moves: [to('medusa', xy(14, 13))], boostCardId: 'c4' },
  },
  {
    name: 'basic-grid20-allowance9',
    description: 'suspicious BOOST 6 (allowance 9) on a 20x20 grid: no hard cap',
    cases: ['MS-E-03'],
    board: 'grid20',
    layer: 'executor',
    fighters: [medusa(xy(10, 10)), arthur(xy(0, 0))],
    hand: [card('c6', 6)],
    draft: { moves: [to('medusa', xy(15, 14))], boostCardId: 'c6' },
  },

  // --- blockers-* (MS-E-20..23) ---
  {
    name: 'blockers-marmoreal-enemy-path',
    description:
      'the only short way M13-M07-M08 runs through Arthur on M07: no path in 3, forced path blocked',
    cases: ['MS-E-20'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M07')],
    draft: { moves: [forced('medusa', 'M07', 'M08')] },
  },
  {
    name: 'blockers-sarpedon-enemy-detour',
    description: 'Arthur on S21 blocks S20-S21-S12; the move detours S20-S10-S11-S12',
    cases: ['MS-E-20'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S20'), arthur('S21')],
    draft: { moves: [to('medusa', 'S12')] },
  },
  {
    name: 'blockers-sarpedon-ally-path',
    description: 'a Harpy on S21 is passable: S20-S21-S12',
    cases: ['MS-E-20'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S20', { movement: 2 }), harpy(1, 'S21'), arthur('S36')],
    draft: { moves: [to('medusa', 'S12')] },
  },
  {
    name: 'blockers-sarpedon-enemy-target',
    description: 'Arthur on the target S21: not an end, server answers PATH_BLOCKED_BY_ENEMY',
    cases: ['MS-E-21'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S20'), arthur('S21')],
    draft: { moves: [forced('medusa', 'S21')] },
  },
  {
    name: 'blockers-sarpedon-ally-target',
    description: 'a Harpy on the target S24: passable but not an end, POSITION_OCCUPIED',
    cases: ['MS-E-22'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S20'), harpy(1, 'S24'), arthur('S36')],
    draft: { moves: [forced('medusa', 'S24')] },
  },
  {
    name: 'blockers-marmoreal-ally-target',
    description: 'a Harpy on the target M07: POSITION_OCCUPIED',
    cases: ['MS-E-22'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), harpy(1, 'M07'), arthur('M31')],
    draft: { moves: [forced('medusa', 'M07')] },
  },
  {
    name: 'blockers-marmoreal-defeated',
    description: 'a defeated Merlin (health 0) on M07 blocks nothing: M13-M07-M01',
    cases: ['MS-E-23'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M31'), merlin('M07', { health: 0, isDefeated: true })],
    draft: { moves: [to('medusa', 'M01')] },
  },

  // --- topology-* (MS-E-25..28) ---
  ...unlinkedScenarios(MARMOREAL_UNLINKED, 'M31'),
  ...unlinkedScenarios(SARPEDON_UNLINKED, 'S07'),
  {
    name: 'topology-marmoreal-crossing-from-M22',
    description:
      'from M22 the edges M22-M29/M22-M30 cross M25-M26 without a junction: M22-M30-M31-M23',
    cases: ['MS-E-27'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M22'), arthur('M01')],
    draft: { moves: [to('medusa', 'M23')] },
  },
  {
    name: 'topology-sarpedon-degree5-S11',
    description: 'degree-5 vertex S11 (and S21): S11-S21-S24',
    cases: ['MS-E-28'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S11', { movement: 2 }), arthur('S38')],
    draft: { moves: [to('medusa', 'S24')] },
  },

  // --- tiebreak-* (MS-E-32) ---
  {
    name: 'tiebreak-sarpedon-S20-S11',
    description: 'two shortest paths S20-S10-S11 and S20-S21-S11: K picks S10',
    cases: ['MS-E-32'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S20', { movement: 2 }), arthur('S38')],
    draft: { moves: [to('medusa', 'S11')] },
  },
  {
    name: 'tiebreak-marmoreal-M08-M17',
    description: 'two shortest paths M08-M09-M17 and M08-M14-M17: K picks M09',
    cases: ['MS-E-32'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M08', { movement: 2 }), arthur('M31')],
    draft: { moves: [to('medusa', 'M17')] },
  },
  {
    name: 'tiebreak-cobble-boosted',
    description: 'many shortest paths over 7 steps on Cobble: K = (y, x) walks the low rows first',
    cases: ['MS-E-32', 'MS-E-02'],
    board: 'cobble',
    layer: 'executor',
    fighters: [medusa(xy(0, 0)), arthur(xy(4, 5))],
    hand: [card('c4', 4)],
    draft: { moves: [to('medusa', xy(4, 3))], boostCardId: 'c4' },
  },

  // --- multi-* (MS-E-05, 33..37) ---
  {
    name: 'multi-cobble-free-then-occupy',
    description: 'A leaves (2,2) first, then B ends there: legal in this order',
    cases: ['MS-E-33'],
    board: 'cobble',
    layer: 'executor',
    fighters: [medusa(xy(2, 2)), harpy(1, xy(2, 1)), arthur(xy(4, 5))],
    draft: { moves: [to('medusa', xy(2, 3)), to('harpy-1', xy(2, 2))] },
  },
  {
    name: 'multi-cobble-occupy-before-free',
    description: 'B ends on (2,2) before A leaves it: Conflict, POSITION_OCCUPIED',
    cases: ['MS-E-34'],
    board: 'cobble',
    layer: 'executor',
    fighters: [medusa(xy(2, 2)), harpy(1, xy(2, 1)), arthur(xy(4, 5))],
    draft: { moves: [forced('harpy-1', xy(2, 2)), to('medusa', xy(2, 3))] },
  },
  {
    name: 'multi-sarpedon-swap',
    description: 'two allies cannot swap S20 and S21 in any order',
    cases: ['MS-E-35'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S20'), harpy(1, 'S21'), arthur('S38')],
    draft: { moves: [forced('harpy-1', 'S20'), forced('medusa', 'S21')] },
  },
  {
    name: 'multi-sarpedon-same-target',
    description: 'two moves to S24: the second is a Conflict',
    cases: ['MS-E-36'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S20'), harpy(1, 'S30'), arthur('S38')],
    draft: { moves: [to('medusa', 'S24'), forced('harpy-1', 'S24')] },
  },
  {
    name: 'multi-sarpedon-through-moved',
    description: 'A steps S19-S20, then B goes S23-S19-S20-S10 through A',
    cases: ['MS-E-37'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [medusa('S19'), harpy(1, 'S23'), arthur('S38')],
    draft: { moves: [to('medusa', 'S20'), to('harpy-1', 'S10')] },
  },
  {
    name: 'multi-cobble-duplicate-fighter',
    description:
      'the same fighter twice in moves[]: the executor rejects the maneuver (the client overwrites instead)',
    cases: ['MS-E-38'],
    board: 'cobble',
    layer: 'executor',
    fighters: [medusa(xy(2, 2)), arthur(xy(4, 5))],
    draft: { moves: [forced('medusa', xy(2, 3)), forced('medusa', xy(2, 3), xy(2, 4))] },
  },
  {
    name: 'multi-cobble-leshen-1-3',
    description: 'hero movement 1 and sidekick movement 3 (Ancient Leshen / Wolves), +2 to each',
    cases: ['MS-E-05', 'MS-E-01'],
    board: 'cobble',
    layer: 'executor',
    fighters: [
      fighter('leshen', 'p1', xy(0, 0), { name: 'Ancient Leshen', type: 'HERO', movement: 1 }),
      fighter('wolf-1', 'p1', xy(0, 5), { name: 'Wolf 1', type: 'MINION', movement: 3 }),
      arthur(xy(4, 5)),
    ],
    hand: [card('c2', 2)],
    draft: { moves: [to('leshen', xy(2, 1)), to('wolf-1', xy(3, 3))], boostCardId: 'c2' },
  },
  {
    name: 'multi-sarpedon-leshen-1-3',
    description:
      'Leshen 1 / Wolves 3 on Sarpedon without boost: a wolf goes 3, the hero 1 onto its space',
    cases: ['MS-E-05', 'MS-E-33'],
    board: 'sarpedon',
    layer: 'executor',
    fighters: [
      fighter('leshen', 'p1', at('S20'), { name: 'Ancient Leshen', type: 'HERO', movement: 1 }),
      fighter('wolf-1', 'p1', at('S24'), { name: 'Wolf 1', type: 'MINION', movement: 3 }),
      fighter('wolf-2', 'p1', at('S30'), { name: 'Wolf 2', type: 'MINION', movement: 3 }),
      arthur('S38'),
    ],
    draft: { moves: [to('wolf-1', 'S05'), to('leshen', 'S24'), to('wolf-2', 'S19')] },
  },
  {
    name: 'multi-marmoreal-three-fighters-boost',
    description: 'Medusa and two Harpies with one +2 boost card (live acceptance shape of M1)',
    cases: ['MS-E-05', 'MS-E-33'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), harpy(1, 'M20'), harpy(2, 'M07'), arthur('M31'), merlin('M30')],
    hand: [card('c2', 2), card('c3', 3)],
    draft: {
      moves: [to('harpy-2', 'M09'), to('medusa', 'M08'), to('harpy-1', 'M23')],
      boostCardId: 'c2',
    },
  },

  // --- boost-* (MS-E-07..09, 13, 78, 79, 81) ---
  {
    name: 'boost-marmoreal-null-with-move',
    description: 'boost with a card without printed BOOST: server takes +0 today',
    cases: ['MS-E-07'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M31')],
    hand: [card('c-null', null)],
    draft: { moves: [to('medusa', 'M02')], boostCardId: 'c-null' },
    pendingRuleChange: {
      task: 'MS-T-20',
      rule: 'RL-07 / MS-E-07 (R6 S6)',
      server: 'BOOST_NO_VALUE',
    },
  },
  {
    name: 'boost-marmoreal-zero-small',
    description: 'BOOST 0 adds nothing: a 4-step target needs +1, server NOT_ENOUGH_MOVEMENT',
    cases: ['MS-E-08', 'MS-E-13', 'MS-E-19'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M31')],
    hand: [card('c0', 0), card('c3', 3)],
    draft: { moves: [to('medusa', 'M15')], boostCardId: 'c0' },
  },
  {
    name: 'boost-marmoreal-four',
    description: 'BOOST 4: a 7-step target with movement 3 is Ok',
    cases: ['MS-E-02'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M01')],
    hand: [card('c4', 4)],
    draft: { moves: [to('medusa', 'M12')], boostCardId: 'c4' },
  },
  {
    name: 'boost-marmoreal-six',
    description: 'suspicious BOOST 6 (allowance 9): no cap; M16 is 7 steps away and needs +4',
    cases: ['MS-E-03'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M01')],
    hand: [card('c6', 6)],
    draft: { moves: [to('medusa', 'M16')], boostCardId: 'c6' },
  },
  {
    name: 'boost-marmoreal-no-move',
    description: 'boost without movement: moves [] + boostCardId, the card is discarded',
    cases: ['MS-E-09'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M31')],
    hand: [card('c4', 4)],
    draft: { moves: [], boostCardId: 'c4' },
  },
  {
    name: 'boost-marmoreal-removed',
    description: 'boost removed after drawing: the 6-step move becomes NeedBoost(3), not Conflict',
    cases: ['MS-E-13', 'MS-E-14', 'MS-E-19'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), arthur('M31')],
    hand: [card('c4', 4)],
    draft: { moves: [to('medusa', 'M05')] },
  },
  {
    name: 'boost-marmoreal-two-moves-selected4',
    description: 'moves needing +2 and +4 with the +4 card selected: both Ok',
    cases: ['MS-E-79'],
    board: 'marmoreal',
    layer: 'executor',
    fighters: [medusa('M13'), harpy(1, 'M27'), arthur('M06')],
    hand: [card('c2', 2), card('c4', 4)],
    draft: { moves: [to('medusa', 'M04'), to('harpy-1', 'M12')], boostCardId: 'c4' },
  },

  // --- data-* (MS-E-04, 24, 40, 77, 107) ---
  ...DATA_MOVEMENT.map(
    ([label, movement]): Scenario => ({
      name: `data-cobble-movement-${label}`,
      description: `raw movement ${JSON.stringify(movement)}: getFighterMovement decides the base`,
      cases: ['MS-E-04', 'MS-E-107'],
      board: 'cobble',
      layer: 'executor',
      fighters: [medusa(xy(2, 2), { movement }), arthur(xy(4, 5))],
      hand: [card('c1', 1)],
      draft: { moves: [to('medusa', xy(2, 5))] },
    }),
  ),
  {
    name: 'data-cobble-movement-missing',
    description: 'no movement field (legacy save): base 2',
    cases: ['MS-E-04'],
    board: 'cobble',
    layer: 'executor',
    fighters: [
      fighter('medusa', 'p1', xy(2, 2), { name: 'Medusa', type: 'HERO', health: 16 }),
      arthur(xy(4, 5)),
    ],
    hand: [card('c1', 1)],
    draft: { moves: [to('medusa', xy(2, 5))] },
  },
  {
    name: 'data-cobble-dirty-defeated-blocker',
    description: 'Merlin with isDefeated true and health 5 is not alive: a free end (dirty data)',
    cases: ['MS-E-24'],
    board: 'cobble',
    layer: 'executor',
    fighters: [
      medusa(xy(2, 2)),
      merlin(xy(2, 3), { health: 5, isDefeated: true }),
      arthur(xy(4, 5)),
    ],
    draft: { moves: [to('medusa', xy(2, 3))] },
  },
  {
    name: 'data-cobble-dirty-defeated-mover',
    description:
      'a Harpy with isDefeated true and health 1 still moves (validator checks health only)',
    cases: ['MS-E-77'],
    board: 'cobble',
    layer: 'executor',
    fighters: [medusa(xy(0, 0)), harpy(1, xy(2, 2), { isDefeated: true }), arthur(xy(4, 5))],
    draft: { moves: [to('harpy-1', xy(3, 3))] },
  },
  {
    name: 'data-cobble-immobilized-forced',
    description: 'one of three fighters is immobilized; forcing its move fails the maneuver',
    cases: ['MS-E-40'],
    board: 'cobble',
    layer: 'executor',
    fighters: [
      medusa(xy(2, 2)),
      harpy(1, xy(1, 1)),
      harpy(2, xy(3, 1), { effects: ['immobilized'] }),
      arthur(xy(4, 5)),
    ],
    draft: {
      moves: [to('medusa', xy(2, 4)), to('harpy-1', xy(0, 0)), forced('harpy-2', xy(4, 1))],
    },
  },
  {
    name: 'data-cobble-immobilized-stays',
    description: 'the immobilized Harpy stays; the other two fighters move',
    cases: ['MS-E-40'],
    board: 'cobble',
    layer: 'executor',
    fighters: [
      medusa(xy(2, 2)),
      harpy(1, xy(1, 1)),
      harpy(2, xy(3, 1), { effects: ['immobilized'] }),
      arthur(xy(4, 5)),
    ],
    draft: { moves: [to('medusa', xy(2, 4)), to('harpy-1', xy(0, 0))] },
  },

  // --- server-* (MS-E-31) ---
  {
    name: 'server-cobble-dto-coord19',
    description: 'coordinate 19 is the DTO maximum: accepted by class-validator',
    cases: ['MS-E-31'],
    board: 'cobble',
    layer: 'dto',
    fighters: [medusa(xy(2, 2)), arthur(xy(4, 5))],
    draft: { moves: [forced('medusa', xy(19, 2))] },
  },

  // --- pending-* (MS-E-57..60, 63, 76) ---
  {
    name: 'pending-marmoreal-move-value3',
    description: 'pending MOVE up to 3 for a Harpy: M27-M28-M29-M22',
    cases: ['MS-E-57'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M13'), harpy(1, 'M27'), arthur('M31')],
    pending: {
      type: 'MOVE',
      fighterId: 'harpy-1',
      ownerId: 'p1',
      value: 3,
      optional: true,
      target: at('M22'),
    },
  },
  {
    name: 'pending-marmoreal-move-stay-value0',
    description: 'value 0: staying on the own space is the only legal answer',
    cases: ['MS-E-76', 'MS-E-58'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M13'), harpy(1, 'M14'), arthur('M31')],
    pending: {
      type: 'MOVE',
      fighterId: 'harpy-1',
      ownerId: 'p1',
      value: 0,
      optional: true,
      target: at('M14'),
    },
  },
  {
    name: 'pending-marmoreal-move-opponent-blocked',
    description: 'p1 moves Arthur (p2): p1 fighters are walls for him, M07 is out of 2 steps',
    cases: ['MS-E-59'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M08'), arthur('M14'), harpy(1, 'M31')],
    pending: {
      type: 'MOVE',
      fighterId: 'arthur',
      ownerId: 'p1',
      value: 2,
      targetsOpponent: true,
      optional: true,
      target: at('M07'),
    },
  },
  {
    name: 'pending-marmoreal-move-opponent-ok',
    description: 'p1 moves Arthur (p2) M14-M09-M15',
    cases: ['MS-E-59'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M08'), arthur('M14'), harpy(1, 'M31')],
    pending: {
      type: 'MOVE',
      fighterId: 'arthur',
      ownerId: 'p1',
      value: 2,
      targetsOpponent: true,
      optional: true,
      target: at('M15'),
    },
  },
  {
    name: 'pending-marmoreal-move-through-enemies',
    description: 'Winged Frenzy (canPassThroughEnemies): M13-M07-M08 through Arthur',
    cases: ['MS-E-60'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M31'), harpy(1, 'M13'), arthur('M07')],
    pending: {
      type: 'MOVE',
      fighterId: 'harpy-1',
      ownerId: 'p1',
      value: 3,
      canPassThroughEnemies: true,
      optional: true,
      target: at('M08'),
    },
  },
  {
    name: 'pending-marmoreal-move-enemies-block',
    description:
      'the same move without canPassThroughEnemies: Arthur on M07 blocks, NOT_ENOUGH_MOVEMENT',
    cases: ['MS-E-60', 'MS-E-20'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M31'), harpy(1, 'M13'), arthur('M07')],
    pending: {
      type: 'MOVE',
      fighterId: 'harpy-1',
      ownerId: 'p1',
      value: 3,
      optional: true,
      target: at('M08'),
    },
  },
  {
    name: 'pending-marmoreal-place-in-zone',
    description: "PLACE in Medusa's zone (M13 red/yellow → M20 red/yellow)",
    cases: ['MS-E-62'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M13'), harpy(1, 'M29'), arthur('M31')],
    pending: {
      type: 'PLACE',
      fighterId: 'harpy-1',
      ownerId: 'p1',
      zoneFighterName: 'Medusa',
      optional: false,
      target: at('M20'),
    },
  },
  {
    name: 'pending-marmoreal-move-immobilized',
    description: 'MOVE effect on an immobilized Harpy: the server allows it today',
    cases: ['MS-E-63'],
    board: 'marmoreal',
    layer: 'resolvePending',
    fighters: [medusa('M13'), harpy(1, 'M14', { effects: ['immobilized'] }), arthur('M31')],
    pending: {
      type: 'MOVE',
      fighterId: 'harpy-1',
      ownerId: 'p1',
      value: 2,
      optional: true,
      target: at('M09'),
    },
    pendingRuleChange: {
      task: 'MS-T-19',
      rule: 'RL-10 / MS-E-63 (R6 O-15)',
      server: 'FIGHTER_IMMOBILIZED',
    },
  },
];

// ---------------------------------------------------------------------------
// Build, format, write / check
// ---------------------------------------------------------------------------

export async function buildFixture(sc: Scenario): Promise<MoveFixture> {
  const fx: MoveFixture = {
    schema: MOVE_FIXTURE_SCHEMA,
    name: sc.name,
    expectSource: 'generated',
    description: sc.description,
    cases: sc.cases,
    ...(sc.actor ? { actor: sc.actor } : {}),
    board: boardOf(sc.board),
    fighters: sc.fighters,
    ...(sc.hand ? { hand: sc.hand } : {}),
    ...(sc.draft ? { draft: sc.draft } : {}),
    ...(sc.pending ? { pending: sc.pending } : {}),
    expect: { layer: sc.layer, server: '' },
  };
  const computed = computeFixtureExpect(fx);
  const outcome = await runFixtureLayer(fx);
  if (/^(UNMAPPED|NO_CODE)/.test(outcome.server)) {
    throw new Error(`${sc.name}: server answer has no 02 §1.1 code: ${outcome.server}`);
  }
  const nonEmpty = <T extends object>(o: T) => (Object.keys(o).length > 0 ? o : undefined);
  fx.expect = {
    layer: sc.layer,
    ...(nonEmpty(computed.reach) ? { reach: computed.reach } : {}),
    ...(nonEmpty(computed.paths) ? { paths: computed.paths } : {}),
    ...(nonEmpty(computed.status) ? { status: computed.status } : {}),
    ...(nonEmpty(computed.requiredBoost) ? { requiredBoost: computed.requiredBoost } : {}),
    server: outcome.server,
    ...(sc.layer === 'dto' && outcome.error ? { serverDetail: outcome.error } : {}),
    ...(sc.pendingRuleChange ? { pendingRuleChange: sc.pendingRuleChange } : {}),
  };
  return fx;
}

/** JSON with 2-space indent; flat objects and arrays of numbers/pairs stay on one line */
export function formatFixture(value: unknown, indent = ''): string {
  const inner = indent + '  ';
  const isFlat = (v: unknown): boolean =>
    v === null ||
    typeof v !== 'object' ||
    (Array.isArray(v) && v.every((e) => e === null || typeof e !== 'object'));
  if (Array.isArray(value)) {
    if (value.every(isFlat)) {
      return `[${value.map((e) => (Array.isArray(e) ? `[${e.map((n) => JSON.stringify(n)).join(', ')}]` : JSON.stringify(e))).join(', ')}]`;
    }
    return `[\n${value.map((e) => inner + formatFixture(e, inner)).join(',\n')}\n${indent}]`;
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).filter(([, v]) => v !== undefined);
    if (entries.every(([, v]) => v === null || typeof v !== 'object') && entries.length <= 4) {
      return `{ ${entries.map(([k, v]) => `${JSON.stringify(k)}: ${JSON.stringify(v)}`).join(', ')} }`;
    }
    return `{\n${entries.map(([k, v]) => `${inner}${JSON.stringify(k)}: ${formatFixture(v, inner)}`).join(',\n')}\n${indent}}`;
  }
  return JSON.stringify(value);
}

async function main(): Promise<void> {
  const mode = process.argv.includes('--write') ? 'write' : 'check';
  const manual = new Set(
    loadMoveFixtures()
      .filter((f) => f.expectSource === 'manual')
      .map((f) => f.name),
  );
  const names = new Set<string>();
  let drift = 0;
  for (const sc of SCENARIOS) {
    if (names.has(sc.name)) throw new Error(`duplicate scenario ${sc.name}`);
    names.add(sc.name);
    if (manual.has(sc.name))
      throw new Error(`${sc.name} is a manual fixture — the generator never writes it`);
    const text = formatFixture(await buildFixture(sc)) + '\n';
    const file = join(MOVE_FIXTURE_DIR, `${sc.name}${MOVE_FIXTURE_SUFFIX}`);
    const old = existsSync(file) ? readFileSync(file, 'utf8').replace(/\r\n/g, '\n') : null;
    if (old === text) continue;
    if (mode === 'write') {
      writeFileSync(file, text, 'utf8');
      console.log(`${old === null ? 'created' : 'updated'} ${basename(file)}`);
    } else {
      drift++;
      console.log(`${old === null ? 'missing' : 'differs'} ${basename(file)}`);
    }
  }
  const stale = loadMoveFixtures().filter(
    (f) => f.expectSource === 'generated' && !names.has(f.name),
  );
  for (const f of stale) console.log(`stale generated fixture without a scenario: ${f.name}`);
  console.log(
    `${mode}: ${SCENARIOS.length} generated scenarios, ${manual.size} manual fixtures, ` +
      `${mode === 'check' ? `${drift} drifted` : 'written'}, ${stale.length} stale`,
  );
  if (mode === 'check' && (drift > 0 || stale.length > 0)) process.exitCode = 1;
}

if (require.main === module) {
  main().catch((error) => {
    console.error(
      'GEN_MOVE_FIXTURES_FAILED:',
      error instanceof Error ? error.message : String(error),
    );
    process.exitCode = 1;
  });
}
