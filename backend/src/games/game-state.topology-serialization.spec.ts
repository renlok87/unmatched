/**
 * ENV-MAPS B2: the topology of an original map (Cell.links / layout / start /
 * spaceId) survives every storage and transport hop of the game state:
 *   - DB: serialize -> Json column (JSON) -> deserialize (saveState / loadState);
 *   - Redis: cacheState -> JSON string -> getCachedState;
 *   - wire: filterPrivateData -> JSON.stringify (query gameState / mutations)
 *     and the subscription's separate boardState JSON field.
 * The engine must see the same graph after each hop (neighbours = links).
 */
import { GameStateService, type GameState } from './game-state.service';
import { GameInitializationService } from './services/game-initialization.service';
import { GameStatus } from './dto/create-game.dto';
import { hasTopology, isAdjacent, neighbours } from '../game-engine/engine/board-topology';
import type { BoardState, Cell } from '../game-engine/models';
import {
  fixtureFiles,
  loadTopologyFixture,
  topologyBoardRow,
} from '../../prisma/seed-env-map-boards';

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

async function initialState(map: string): Promise<GameState> {
  const file = fixtureFiles().find((f) => f.endsWith(`${map}.topology.json`))!;
  const { fixture, sha256 } = loadTopologyFixture(file);
  const board = JSON.parse(JSON.stringify(topologyBoardRow(fixture, sha256, file)));
  const prisma = {
    game: { findUnique: async () => ({ boardId: board.id }) },
    board: { findUnique: async () => board },
    gamePlayer: {
      findMany: async () =>
        ['medusa', 'arthur'].map((heroId, seatOrder) => ({
          heroId,
          seatOrder,
          userId: `seat-${seatOrder}`,
        })),
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
  const service = new GameInitializationService(
    prisma as any,
    { saveState: async () => undefined } as any,
  );
  return service.initializeGameState(`env-${map}`);
}

function fakeRedis() {
  const store = new Map<string, string>();
  return {
    store,
    setJsonex: async (key: string, _ttl: number, value: unknown) => {
      store.set(key, JSON.stringify(value));
      return 'OK' as const;
    },
    getJson: async (key: string) => (store.has(key) ? JSON.parse(store.get(key)!) : null),
    del: async (key: string) => (store.delete(key) ? 1 : 0),
  };
}

/** Topology fields of every space cell, keyed by position */
function topologyOf(board: BoardState) {
  return board.cells
    .flat()
    .filter((c) => c.spaceId)
    .map((c: Cell) => ({
      x: c.x,
      y: c.y,
      type: c.type,
      spaceId: c.spaceId,
      layout: c.layout,
      start: c.start,
      links: c.links,
      zones: c.zones,
    }));
}

function expectSameGraph(after: BoardState, before: BoardState) {
  expect(after).toEqual(before);
  expect(topologyOf(after)).toEqual(topologyOf(before));
  expect(hasTopology(after)).toBe(true);
  for (const cell of before.cells.flat()) {
    expect(neighbours(after, cell)).toEqual(neighbours(before, cell));
  }
}

describe.each(['marmoreal', 'sarpedon'])('ENV-MAPS %s: topology survives serialization', (map) => {
  let state: GameState;
  let service: GameStateService;
  let redis: ReturnType<typeof fakeRedis>;
  beforeAll(async () => {
    state = await initialState(map);
    redis = fakeRedis();
    const prisma = {
      game: {
        findUnique: async () => ({ status: GameStatus.IN_PROGRESS, version: state.sequenceNumber }),
      },
    };
    service = new GameStateService(prisma as any, redis as any);
  });

  it('the initial state carries the graph (sanity)', () => {
    const spaces = topologyOf(state.boardState);
    expect(spaces.length).toBe(map === 'marmoreal' ? 31 : 38);
    expect(spaces.every((s) => Array.isArray(s.links) && s.links.length >= 2 && s.layout)).toBe(
      true,
    );
    expect(
      spaces
        .filter((s) => s.start)
        .map((s) => s.start)
        .sort(),
    ).toEqual([1, 2, 3, 4]);
  });

  it('DB: serialize -> Json column -> deserialize', () => {
    const column = JSON.parse(JSON.stringify(service.serialize(state)));
    expect(column.b.cells).toEqual(state.boardState.cells);
    const back = service.deserialize(column);
    expectSameGraph(back.boardState, state.boardState);
    expect([back.boardState.width, back.boardState.height]).toEqual([
      state.boardState.width,
      state.boardState.height,
    ]);
    expect(back.fighters.map((f) => f.position)).toEqual(state.fighters.map((f) => f.position));
  });

  it('Redis: cacheState -> getCachedState', async () => {
    await service.cacheState(state.gameId, state);
    expect(redis.store.get(`gamestate:${state.gameId}`)).toContain('"links"');
    const cached = await service.getCachedState(state.gameId);
    expect(cached).not.toBeNull();
    expectSameGraph(cached!.boardState, state.boardState);
  });

  it('wire: filtered query/mutation state and the subscription boardState field', () => {
    for (const viewer of ['seat-0', 'seat-1', 'spectator']) {
      const filtered = service.filterPrivateData(state, viewer);
      const query = JSON.parse(JSON.stringify(filtered)) as GameState;
      expectSameGraph(query.boardState, state.boardState);
      const subscriptionField = JSON.parse(JSON.stringify(filtered.boardState)) as BoardState;
      expectSameGraph(subscriptionField, state.boardState);
    }
  });

  it('a lattice neighbour without a line stays non-adjacent after the round trip', () => {
    const back = service.deserialize(JSON.parse(JSON.stringify(service.serialize(state))));
    const cells = back.boardState.cells.flat();
    const byId = new Map(cells.filter((c) => c.spaceId).map((c) => [c.spaceId!, c]));
    const [a, b] = map === 'marmoreal' ? ['M13', 'M14'] : ['S19', 'S24'];
    const pa = byId.get(a)!;
    const pb = byId.get(b)!;
    expect(Math.abs(pa.x - pb.x) + Math.abs(pa.y - pb.y)).toBe(1);
    expect(isAdjacent(back.boardState, pa, pb)).toBe(false);
  });
});
