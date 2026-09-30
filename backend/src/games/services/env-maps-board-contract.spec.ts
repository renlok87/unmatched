/**
 * ENV-MAPS B2: runtime contract of the ORIGINAL maps of Battle of Legends Vol. 1
 * (Marmoreal, Sarpedon) for Medusa (+3 Harpy) vs King Arthur (+Merlin).
 *
 * Source of truth: backend/prisma/fixtures/boards/<map>.topology.json (built by
 * tools/art/board_topology.py, pinned here by sha256) and, independently, the
 * committed research evidence docs/game-design/evidence/ENV-MAPS/2026-09-30-research.
 * The Board row is exactly what prisma/seed-env-map-boards.ts writes; board
 * construction, starts, sidekick placement, movement, attacks and the AI are
 * production code - only persistence and the hero catalog are substituted
 * (pattern of s04-board-contract.spec.ts).
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { GameInitializationService } from './game-initialization.service';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { graphDistance, hasTopology, isAdjacent } from '../../game-engine/engine/board-topology';
import { AiDecisionService } from '../../game-engine/services/ai-decision.service';
import { getCellZones } from '../../game-engine/models';
import type { BoardState, Fighter, GameState, Position } from '../../game-engine/models';
import type { AttackDto, ManeuverDto } from '../dto/gameplay.dto';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import { ContentMapper } from '../../content/mappers/content.mapper';
import { Zone } from '../../content/interfaces';
import {
  fixtureFiles,
  loadTopologyFixture,
  topologyBoardId,
  topologyBoardRow,
  validateTopologyFixture,
  type TopologyFixture,
} from '../../../prisma/seed-env-map-boards';

const root = resolve(__dirname, '../../../..');
const evidenceDir = 'docs/game-design/evidence/ENV-MAPS/2026-09-30-research';
const load = (path: string) => JSON.parse(readFileSync(resolve(root, path), 'utf8'));
const key = (p: Position) => `${p.x}:${p.y}`;

/**
 * Pinned fixtures: sha256 of the committed LF bytes (fixtures/boards/.gitattributes
 * keeps them LF). A regenerated topology must update this contract on purpose.
 */
const MAPS = {
  marmoreal: {
    sha256: '425bebf254a98724c8192ab11d692eceb0ab2e31b7238dab3057b52ac9e5d38f',
    boardId: 'c121b47f8d6eb28daccb76d05',
    spaces: 31,
    edges: 42,
    lattice: [7, 6],
    starts: { 1: 'M13', 2: 'M31', 3: 'M03', 4: 'M11' },
    longLink: ['M25', 'M26'],
    /** lattice neighbours that are NOT linked by a line */
    unlinkedLatticeStep: ['M26', 'M30'],
    /** ranged via the THIRD zone of a triple-zone space (purple of M17), not linked */
    rangedViaSharedZone: { from: 'M17', to: 'M29', zone: 'purple' },
    /** violet != purple: violet-only M23 vs purple+brown M29, not linked */
    rangedNoSharedZone: { from: 'M23', to: 'M29' },
    image: '07d4a8eb350c7db43e9c5e7699196173101eb5eff981d7befe3d30e5c35631a0',
  },
  sarpedon: {
    sha256: 'd1a7221454e3b6f61a08468f9ea5469071c1683604da8287e7d74c2354978b37',
    boardId: 'c7fa64a26c29a0835f2383e63',
    spaces: 38,
    edges: 61,
    lattice: [9, 6],
    starts: { 1: 'S20', 2: 'S32', 3: 'S03', 4: 'S14' },
    longLink: ['S21', 'S31'],
    unlinkedLatticeStep: ['S32', 'S35'],
    rangedViaSharedZone: { from: 'S22', to: 'S30', zone: 'purple' },
    rangedNoSharedZone: { from: 'S19', to: 'S30' },
    image: '9015b9cf102bbcc48de1958acb5468c838a588013a6ada2f74ce2f5c57effa84',
  },
} as const;
type MapKey = keyof typeof MAPS;

const heroes: Record<string, any> = {
  medusa: {
    id: 'medusa',
    name: 'Medusa',
    health: 16,
    movement: 3,
    properties: { attackType: 'ranged' },
    sidekicks: [{ name: 'Harpy', count: 3, health: 1 }],
  },
  arthur: {
    id: 'arthur',
    name: 'King Arthur',
    health: 18,
    movement: 2,
    sidekicks: [{ name: 'Merlin', health: 7, attackType: 'ranged' }],
  },
};

function fixtureOf(map: MapKey) {
  const file = fixtureFiles().find((f) => f.endsWith(`${map}.topology.json`))!;
  const { fixture, sha256 } = loadTopologyFixture(file);
  // what Prisma hands back from the Json column after seed-env-map-boards.ts
  const row = JSON.parse(JSON.stringify(topologyBoardRow(fixture, sha256, file)));
  return { fixture, sha256, row };
}

async function initialize(board: unknown, order: string[]): Promise<GameState> {
  const prisma = {
    game: { findUnique: async () => ({ boardId: (board as { id: string }).id }) },
    board: { findUnique: async () => board },
    gamePlayer: {
      findMany: async () =>
        order.map((heroId, seatOrder) => ({ heroId, seatOrder, userId: `seat-${seatOrder}` })),
    },
    hero: {
      findUnique: async ({ where }: any) => ({
        ...heroes[where.id],
        cards: [
          {
            id: `${where.id}-fixture`,
            name: 'Fixture',
            cardType: 'VERSATILE',
            count: 30,
            effects: [],
          },
        ],
      }),
    },
  };
  const saveState = jest.fn(async () => undefined);
  const service = new GameInitializationService(prisma as any, { saveState } as any);
  const state = await service.initializeGameState('env-maps');
  expect(saveState).toHaveBeenCalledWith('env-maps', state);
  return state;
}

/** Independent oracle from the fixture's spaces/edges (ids, not engine cells) */
function oracle(fixture: TopologyFixture) {
  const byId = new Map(fixture.spaces.map((s) => [s.id, s]));
  const adj = new Map<string, Set<string>>(fixture.spaces.map((s) => [s.id, new Set<string>()]));
  for (const [a, b] of fixture.edges) {
    adj.get(a)!.add(b);
    adj.get(b)!.add(a);
  }
  const at = (id: string): Position => ({ x: byId.get(id)!.x, y: byId.get(id)!.y });
  const idAt = (p: Position) =>
    fixture.spaces.find((s) => s.x === p.x && s.y === p.y)?.id ?? `#${key(p)}`;
  const bfs = (from: string) => {
    const dist = new Map([[from, 0]]);
    const queue = [from];
    for (let i = 0; i < queue.length; i++) {
      for (const n of [...adj.get(queue[i])!].sort()) {
        if (!dist.has(n)) {
          dist.set(n, dist.get(queue[i])! + 1);
          queue.push(n);
        }
      }
    }
    return dist;
  };
  /** Rules: separate free space in any of the hero's zones; BFS from the hero, ties by id */
  const sidekickSpaces = (heroId: string, count: number, blocked: Set<string>): string[] => {
    const zones = new Set(byId.get(heroId)!.zones);
    const dist = bfs(heroId);
    const out: string[] = [];
    for (let i = 0; i < count; i++) {
      const pick = fixture.spaces
        .filter((s) => !blocked.has(s.id) && s.zones.some((z) => zones.has(z)))
        .sort(
          (a, b) => (dist.get(a.id) ?? 1e9) - (dist.get(b.id) ?? 1e9) || (a.id < b.id ? -1 : 1),
        )[0];
      out.push(pick.id);
      blocked.add(pick.id);
    }
    return out;
  };
  return { byId, adj, at, idAt, sidekickSpaces };
}

describe.each(Object.keys(MAPS) as MapKey[])('ENV-MAPS original map %s', (map) => {
  const expected = MAPS[map];
  const { fixture, sha256, row } = fixtureOf(map);
  const o = oracle(fixture);
  const evidence = load(`${evidenceDir}/${map}.topology.json`);

  it('pins the fixture bytes, the deterministic id and the map image hash', () => {
    expect(sha256).toBe(expected.sha256);
    expect(fixture.boardId).toBe(expected.boardId);
    expect(topologyBoardId(map)).toBe(expected.boardId);
    expect(fixture.source.sha256).toBe(expected.image);
    expect(evidence.source.sha256).toBe(expected.image);
    expect(validateTopologyFixture(fixture, map)).toEqual([]);
    expect(row).toMatchObject({
      id: expected.boardId,
      width: expected.lattice[0],
      height: expected.lattice[1],
      imageUrl: null,
      features: { topology: true, fixtureSha256: sha256 },
    });
  });

  it('matches the independent research evidence: spaces, zones, edges, starts', () => {
    expect(fixture.spaces).toHaveLength(expected.spaces);
    expect(fixture.edges).toHaveLength(expected.edges);
    expect(fixture.spaces.map((s) => s.id)).toEqual(evidence.spaces.map((s: any) => s.id));
    for (const s of evidence.spaces) {
      expect(o.byId.get(s.id)!.zones).toEqual(s.zones);
      expect(o.byId.get(s.id)!.start).toBe(s.start);
    }
    const norm = (edges: string[][]) => edges.map((e) => [...e].sort().join('-')).sort();
    expect(norm(fixture.edges)).toEqual(norm(evidence.edges));
    const starts = Object.fromEntries(
      fixture.spaces.filter((s) => s.start).map((s) => [s.start, s.id]),
    );
    expect(starts).toEqual(expected.starts);
  });

  describe('board state built from the seeded Board row', () => {
    let state: GameState;
    let board: BoardState;
    beforeAll(async () => {
      state = await initialize(row, ['medusa', 'arthur']);
      board = state.boardState;
    });

    it('every lattice position is explicit: spaces carry the copied topology, holes are obstacles', () => {
      expect([board.width, board.height]).toEqual(expected.lattice);
      expect(hasTopology(board)).toBe(true);
      const cells = board.cells.flat();
      expect(cells).toHaveLength(expected.lattice[0] * expected.lattice[1]);
      for (const cell of cells) {
        const space = fixture.spaces.find((s) => s.x === cell.x && s.y === cell.y);
        if (!space) {
          expect(cell).toEqual({ type: 'obstacle', x: cell.x, y: cell.y });
          continue;
        }
        const source = fixture.cells.find((c) => c.x === cell.x && c.y === cell.y)!;
        expect(cell.type).toBe('normal');
        expect(cell.spaceId).toBe(space.id);
        expect(cell.layout).toEqual(space.layout);
        expect(cell.start).toBe(space.start ?? undefined);
        expect(cell.links).toEqual(source.links);
        expect(getCellZones(cell)).toEqual(space.zones);
      }
      expect(cells.filter((c) => c.type === 'normal')).toHaveLength(expected.spaces);
    });

    it('every edge is adjacent through the engine; nothing else is (incl. unlinked lattice neighbours)', async () => {
      const adjacency = new AdjacencyService();
      let adjacentPairs = 0;
      for (const a of fixture.spaces) {
        for (const b of fixture.spaces) {
          if (a.id >= b.id) continue;
          const linked = o.adj.get(a.id)!.has(b.id);
          expect([a.id, b.id, isAdjacent(board, o.at(a.id), o.at(b.id))]).toEqual([
            a.id,
            b.id,
            linked,
          ]);
          expect(await adjacency.isAdjacent(state, o.at(b.id), o.at(a.id))).toBe(linked);
          if (linked) adjacentPairs++;
        }
      }
      expect(adjacentPairs).toBe(expected.edges);
      // Lattice neighbours without a line are NOT adjacent (recomputed, then the fixture list)
      const latticeOnly = fixture.spaces.flatMap((a) =>
        fixture.spaces
          .filter(
            (b) =>
              a.id < b.id &&
              Math.abs(a.x - b.x) + Math.abs(a.y - b.y) === 1 &&
              !o.adj.get(a.id)!.has(b.id),
          )
          .map((b) => [a.id, b.id]),
      );
      expect(latticeOnly).toEqual((fixture.summary as any).latticeNeighboursNotLinked);
      expect(latticeOnly.length).toBeGreaterThan(0);
      for (const [a, b] of latticeOnly) expect(isAdjacent(board, o.at(a), o.at(b))).toBe(false);
      // Obstacles have no neighbours at all
      for (const hole of board.cells.flat().filter((c) => c.type === 'obstacle')) {
        expect(adjacency.getAdjacentCells(board, hole)).toEqual([]);
      }
    });

    if (map === 'marmoreal') {
      it('M22-M29 / M22-M30 cross M25-M26 WITHOUT a junction: no node, no shortcut', () => {
        expect(fixture.crossings).toEqual([
          {
            edges: [
              ['M22', 'M29'],
              ['M25', 'M26'],
            ],
            junction: false,
          },
          {
            edges: [
              ['M22', 'M30'],
              ['M25', 'M26'],
            ],
            junction: false,
          },
        ]);
        // the crossing point lies on the lattice hole between M25 (2,4) and M26 (4,4)
        expect(board.cells[4][3]).toEqual({ type: 'obstacle', x: 3, y: 4 });
        expect(isAdjacent(board, o.at('M25'), o.at('M26'))).toBe(true);
        expect(isAdjacent(board, o.at('M22'), o.at('M29'))).toBe(true);
        expect(isAdjacent(board, o.at('M22'), o.at('M30'))).toBe(true);
        for (const a of ['M22', 'M29', 'M30']) {
          for (const b of ['M25', 'M26']) expect(isAdjacent(board, o.at(a), o.at(b))).toBe(false);
        }
        // with a junction these would be 2 steps; along the real lines they are 5
        expect(graphDistance(board, o.at('M22'), o.at('M25'))).toBe(5);
        expect(graphDistance(board, o.at('M25'), o.at('M29'))).toBe(5);
      });
    }

    it('zones are the map zones; multi-zone spaces are in all of them', () => {
      const zoneKeys = fixture.zones.map((z) => z.key);
      const counts: Record<string, number> = {};
      for (const cell of board.cells.flat()) {
        for (const z of getCellZones(cell)) {
          expect(zoneKeys).toContain(z);
          counts[z] = (counts[z] ?? 0) + 1;
        }
      }
      expect(counts).toEqual((fixture.summary as any).zoneSpaceCounts);
      const adjacency = new AdjacencyService();
      const { from, to, zone } = expected.rangedViaSharedZone;
      expect(o.byId.get(from)!.zones.indexOf(zone)).toBeGreaterThan(0); // 2nd/3rd zone
      expect(adjacency.isInSameZone(state, o.at(from), o.at(to))).toBe(true);
      expect(
        adjacency.isInSameZone(
          state,
          o.at(expected.rangedNoSharedZone.from),
          o.at(expected.rangedNoSharedZone.to),
        ),
      ).toBe(false);
    });

    it('content API zones: violet stays a zone of its own (not merged into purple)', () => {
      const definition = new ContentMapper().prismaBoardToBoardDefinition(row);
      const zonesOf = (id: string) =>
        definition.spaces.find((s) => key(s.position) === key(o.at(id)))!.zones;
      for (const s of fixture.spaces) expect(zonesOf(s.id)).toEqual(s.zones);
      if (map === 'marmoreal') {
        expect(zonesOf('M16')).toEqual([Zone.BLUE, Zone.VIOLET]);
        expect(zonesOf('M17')).toEqual([Zone.GREEN, Zone.BLUE, Zone.PURPLE]);
        const violet = fixture.spaces
          .filter((s) => zonesOf(s.id).includes(Zone.VIOLET))
          .map((s) => s.id);
        const purple = fixture.spaces
          .filter((s) => zonesOf(s.id).includes(Zone.PURPLE))
          .map((s) => s.id);
        expect(violet).toEqual(['M16', 'M23', 'M24', 'M31']);
        expect(purple).toEqual(['M17', 'M18', 'M22', 'M29', 'M30']);
      }
    });
  });

  describe.each([
    ['medusa', 'arthur'],
    ['arthur', 'medusa'],
  ])('setup %s (seat 0, first) vs %s (seat 1)', (first, second) => {
    let state: GameState;
    beforeAll(async () => {
      state = await initialize(row, [first, second]);
    });
    const pos = (id: string) => state.fighters.find((f) => f.id === id)!.position;

    it('heroes stand on start 1 (host, first turn) and start 2', () => {
      expect(state.currentTurnPlayerId).toBe('seat-0');
      expect(state.metadata.firstPlayerId).toBe('seat-0');
      expect(o.idAt(pos('f-0-hero'))).toBe(expected.starts[1]);
      expect(o.idAt(pos('f-1-hero'))).toBe(expected.starts[2]);
      expect(state.fighters.find((f) => f.id === 'f-0-hero')!.name).toBe(heroes[first].name);
    });

    it('sidekicks: separate spaces inside their hero zones, BFS from the hero, ties by space id', () => {
      const blocked = new Set([expected.starts[1], expected.starts[2]]);
      const counts: Record<string, number> = { medusa: 3, arthur: 1 };
      for (const [seat, hero] of [
        [0, first],
        [1, second],
      ] as const) {
        const heroSpace = o.idAt(pos(`f-${seat}-hero`));
        const sidekicks = state.fighters.filter((f) => f.id.startsWith(`f-${seat}-sk`));
        expect(sidekicks).toHaveLength(counts[hero]);
        const want = o.sidekickSpaces(heroSpace, counts[hero], blocked);
        expect(sidekicks.map((f) => o.idAt(f.position))).toEqual(want);
        const heroZones = o.byId.get(heroSpace)!.zones;
        for (const f of sidekicks) {
          expect(o.byId.get(o.idAt(f.position))!.zones.some((z) => heroZones.includes(z))).toBe(
            true,
          );
        }
      }
      const spaces = state.fighters.map((f) => o.idAt(f.position));
      expect(new Set(spaces).size).toBe(6);
      for (const id of spaces) expect(o.byId.has(id)).toBe(true); // never on a hole
    });

    if (map === 'marmoreal') {
      it('documents the Marmoreal placement', () => {
        const ids = Object.fromEntries(state.fighters.map((f) => [f.id, o.idAt(f.position)]));
        expect(ids).toEqual(
          first === 'medusa'
            ? {
                'f-0-hero': 'M13',
                'f-0-sk0': 'M07',
                'f-0-sk1': 'M20',
                'f-0-sk2': 'M01',
                'f-1-hero': 'M31',
                'f-1-sk0': 'M23',
              }
            : {
                'f-0-hero': 'M13',
                'f-0-sk0': 'M07',
                'f-1-hero': 'M31',
                'f-1-sk0': 'M23',
                'f-1-sk1': 'M30',
                'f-1-sk2': 'M24',
              },
        );
      });
    }
  });

  describe('play on the graph (production executor and AI)', () => {
    let base: GameState;
    beforeAll(async () => {
      base = await initialize(row, ['medusa', 'arthur']);
    });
    /** base state with the named fighters moved; every other fighter keeps its space */
    const place = (spots: Record<string, string>): GameState => {
      const taken = new Set(Object.values(spots));
      const fighters: Fighter[] = base.fighters
        .filter((f) => f.id in spots || !taken.has(o.idAt(f.position)))
        .map((f) => (f.id in spots ? { ...f, position: o.at(spots[f.id]) } : f));
      return { ...base, fighters };
    };
    const context = (state: GameState, userId = 'seat-0') => ({
      gameId: state.gameId,
      userId,
      currentState: state,
    });

    async function maneuver(state: GameState, fighterId: string, path: Position[]) {
      const { executor } = s03Engine();
      const begun = await executor.executeBeginManeuver(
        { gameId: state.gameId, expectedSequenceNumber: state.sequenceNumber },
        context(state),
      );
      expect(begun.success).toBe(true);
      const dto: ManeuverDto = {
        gameId: state.gameId,
        maneuverId: begun.gameState.metadata.pendingManeuver!.id,
        moves: [{ fighterId, path }],
      };
      return executor.executeManeuver(dto, context(begun.gameState));
    }

    it('moves along a long link spanning two lattice steps; an unlinked lattice step is rejected', async () => {
      const [a, b] = expected.longLink;
      const pa = o.at(a);
      const pb = o.at(b);
      expect(Math.abs(pa.x - pb.x) + Math.abs(pa.y - pb.y)).toBe(2);
      expect(graphDistance(base.boardState, pa, pb)).toBe(1);
      const ok = await maneuver(place({ 'f-0-hero': a }), 'f-0-hero', [pb]);
      expect(ok.success).toBe(true);
      expect(ok.gameState!.fighters.find((f) => f.id === 'f-0-hero')!.position).toEqual(pb);
      const [from, to] = expected.unlinkedLatticeStep;
      const step = o.at(to);
      expect(Math.abs(step.x - o.at(from).x) + Math.abs(step.y - o.at(from).y)).toBe(1);
      expect(o.adj.get(from)!.has(to)).toBe(false);
      const bad = await maneuver(place({ 'f-0-hero': from }), 'f-0-hero', [step]);
      expect(bad.success).toBe(false);
    });

    it('ranged attacks through a shared 2nd/3rd zone; melee needs a line; violet is not purple', async () => {
      const attack = async (
        attackerId: string,
        targetId: string,
        spots: Record<string, string>,
      ) => {
        const state = place(spots);
        const cardId = state.handZones['seat-0'].cards[0].id;
        const dto: AttackDto = { gameId: state.gameId, attackerId, targetId, cardId };
        return s03Engine().executor.executeAttack(dto, context(state));
      };
      const { from, to } = expected.rangedViaSharedZone;
      expect(o.adj.get(from)!.has(to)).toBe(false);
      // Medusa (ranged, seat 0) - shared zone, no line
      expect(
        (await attack('f-0-hero', 'f-1-hero', { 'f-0-hero': from, 'f-1-hero': to })).success,
      ).toBe(true);
      // a Harpy (melee) from the same space - no line, no attack
      expect(
        (await attack('f-0-sk0', 'f-1-hero', { 'f-0-sk0': from, 'f-1-hero': to })).success,
      ).toBe(false);
      // Medusa without a shared zone and without a line
      const none = expected.rangedNoSharedZone;
      expect(o.adj.get(none.from)!.has(none.to)).toBe(false);
      expect(
        (await attack('f-0-hero', 'f-1-hero', { 'f-0-hero': none.from, 'f-1-hero': none.to }))
          .success,
      ).toBe(false);
      // melee across the long link (adjacent by the line)
      const [a, b] = expected.longLink;
      expect((await attack('f-0-sk0', 'f-1-hero', { 'f-0-sk0': a, 'f-1-hero': b })).success).toBe(
        true,
      );
    });

    it('the AI moves along lines only, and the executor accepts its maneuver', async () => {
      const { executor } = s03Engine();
      const begun = await executor.executeBeginManeuver(
        { gameId: base.gameId, expectedSequenceNumber: base.sequenceNumber },
        context(base),
      );
      expect(begun.success).toBe(true);
      const action = new AiDecisionService(new AdjacencyService()).decide(
        begun.gameState,
        'seat-0',
      );
      expect(action).toMatchObject({ kind: 'maneuver' });
      if (action?.kind !== 'maneuver') throw new Error('no maneuver');
      expect(action.moves.length).toBeGreaterThan(0);
      for (const move of action.moves) {
        let at = begun.gameState.fighters.find((f) => f.id === move.fighterId)!.position;
        expect(move.path.length).toBeGreaterThan(0);
        for (const step of move.path) {
          expect([o.idAt(at), o.idAt(step), o.adj.get(o.idAt(at))?.has(o.idAt(step))]).toEqual([
            o.idAt(at),
            o.idAt(step),
            true,
          ]);
          at = step;
        }
      }
      const done = await executor.executeManeuver(
        { gameId: base.gameId, maneuverId: action.maneuverId, moves: action.moves } as ManeuverDto,
        context(begun.gameState),
      );
      expect(done.success).toBe(true);
    });
  });
});

describe('ENV-MAPS setup rules on a synthetic topology board', () => {
  /**
   *   A(start 1, red) -- B(start 2, red) -- C(red) -- D(blue)
   *   (3,0) is a lattice hole WITHOUT a cell in the data -> must become an obstacle
   */
  const cells = [
    { x: 0, y: 0, spaceId: 'A', zones: ['red'], start: 1, links: [{ x: 1, y: 0 }] },
    {
      x: 1,
      y: 0,
      spaceId: 'B',
      zones: ['red'],
      start: 2,
      links: [
        { x: 0, y: 0 },
        { x: 2, y: 0 },
      ],
    },
    {
      x: 2,
      y: 0,
      spaceId: 'C',
      zones: ['red'],
      links: [
        { x: 1, y: 0 },
        { x: 2, y: 1 },
      ],
    },
    { x: 2, y: 1, spaceId: 'D', zones: ['blue'], links: [{ x: 2, y: 0 }] },
    { x: 0, y: 1, isObstacle: true },
    { x: 1, y: 1, isObstacle: true },
    { x: 3, y: 1, isObstacle: true },
  ];
  const board = { id: 'synthetic', name: 'Synthetic', cells };
  const idAt = (p: Position) =>
    cells.find((c) => c.x === p.x && c.y === p.y)?.spaceId ?? `#${key(p)}`;

  it('holes missing from the data become obstacles (never normal) on a topology board', async () => {
    heroes.solo = { id: 'solo', name: 'Solo', health: 10, movement: 2, sidekicks: [] };
    const state = await initialize(board, ['solo', 'solo']);
    expect(state.boardState.cells[0][3]).toEqual({ type: 'obstacle', x: 3, y: 0 });
    expect(state.fighters.map((f) => idAt(f.position))).toEqual(['A', 'B']);
  });

  it("a sidekick never takes a later seat's start space; no free zone space -> nearest free space", async () => {
    heroes.duo = {
      id: 'duo',
      name: 'Duo',
      health: 10,
      movement: 2,
      sidekicks: [{ name: 'Pal', count: 2 }],
    };
    const state = await initialize(board, ['duo', 'solo']);
    // B (start 2, red, adjacent) is reserved for seat 1: first Pal goes to C (red, distance 2),
    // the red zone is then full -> second Pal falls back to the nearest free space D (blue)
    expect(state.fighters.map((f) => [f.id, idAt(f.position)])).toEqual([
      ['f-0-hero', 'A'],
      ['f-0-sk0', 'C'],
      ['f-0-sk1', 'D'],
      ['f-1-hero', 'B'],
    ]);
  });
});

describe('ENV-MAPS: grid boards are untouched (Cobble City)', () => {
  it('the S01 Cobble capture is rebuilt byte-for-byte (no topology keys, holes still normal)', async () => {
    const source = load('docs/game-design/evidence/S01/content-board.json').adminBoard;
    const captured = load('docs/game-design/evidence/S01/duel-start-p1.json');
    const state = await initialize(source, ['medusa', 'arthur']);
    expect(hasTopology(state.boardState)).toBe(false);
    expect(JSON.stringify(state.boardState)).toBe(JSON.stringify(captured.boardState));
    for (const cell of state.boardState.cells.flat()) {
      expect(
        Object.keys(cell).filter((k) => ['links', 'layout', 'start', 'spaceId'].includes(k)),
      ).toEqual([]);
    }
    // a grid board with a hole in the data still fills it as 'normal' (pre-topology behaviour)
    const holed = {
      ...source,
      cells: source.cells.filter((c: Position) => !(c.x === 2 && c.y === 2)),
    };
    const rebuilt = await initialize(holed, ['medusa', 'arthur']);
    expect(rebuilt.boardState.cells[2][2]).toEqual({ type: 'normal', x: 2, y: 2 });
  });
});
