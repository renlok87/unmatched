/** GD-016: hero-selection composition and server-owned legal setup.
 * Production GameService + GameInitializationService with fixture storage;
 * the pinned S01 Cobble City capture is the board source. */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { BadRequestException } from '@nestjs/common';
import { GameService } from '../game.service';
import { GameInitializationService } from './game-initialization.service';
import { GameStateService, GameState } from '../game-state.service';
import { getCellZones } from '../../game-engine/models';

const root = resolve(__dirname, '../../../..');
const source = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-board.json'), 'utf8'),
).adminBoard;
const captured = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/duel-start-p1.json'), 'utf8'),
);

const heroes: Record<string, any> = {
  medusa: { id: 'medusa', name: 'Medusa', health: 16, movement: 3,
    properties: { attackType: 'ranged' }, sidekicks: [{ name: 'Harpy', count: 3, health: 1 }] },
  arthur: { id: 'arthur', name: 'King Arthur', health: 18, movement: 2,
    sidekicks: [{ name: 'Merlin', health: 7, attackType: 'ranged' }] },
};
for (const hero of Object.values(heroes)) {
  hero.cards = [{ id: `${hero.id}-fixture`, name: 'Fixture', cardType: 'VERSATILE', count: 30, effects: [] }];
}

function makeDb() {
  const games = new Map<string, any>();
  const players = new Map<string, any>();
  const states = new Map<string, any>();
  const user = (id: string) => ({ id, username: `user-${id}`, avatar: null });
  const gameRow = (id: string) => {
    const game = games.get(id);
    if (!game) return null;
    const roster = [...players.values()].filter(p => p.gameId === id).sort((a, b) => a.seatOrder - b.seatOrder);
    return {
      ...game,
      host: user(game.hostId),
      opponent: game.opponentId ? user(game.opponentId) : null,
      players: roster.map(p => ({ ...p, user: user(p.userId) })),
      state: states.get(id) ?? null,
    };
  };
  let txTail = Promise.resolve();
  const release = { resolve: () => {} };
  const serializeTx = (run: (tx: unknown) => unknown) => {
    const previous = txTail;
    let done!: () => void;
    txTail = new Promise<void>(yes => { done = yes; });
    return previous.then(() => Promise.resolve(run(prisma))).finally(() => done());
  };
  const prisma: any = {
    game: {
      findUnique: async ({ where }: any) => (where.id ? gameRow(where.id) : games.get(where.code) ?? null),
      findFirst: async () => null,
      count: async () => 0,
      update: async ({ where, data }: any) => {
        const game = games.get(where.id);
        games.set(where.id, { ...game, ...data });
        return games.get(where.id);
      },
      create: async ({ data }: any) => { games.set(data.id ?? 'g1', data); return data; },
    },
    gamePlayer: {
      findUnique: async ({ where }: any) =>
        players.get(`${where.gameId_userId.gameId}:${where.gameId_userId.userId}`) ?? null,
      findFirst: async ({ where }: any) =>
        [...players.values()].find(p => p.gameId === where.gameId && p.userId === where.userId) ?? null,
      findMany: async ({ where, orderBy }: any) =>
        [...players.values()]
          .filter(p => p.gameId === where.gameId)
          .sort((a, b) => (orderBy?.seatOrder === 'asc' ? a.seatOrder - b.seatOrder : 0)),
      create: async ({ data }: any) => { players.set(`${data.gameId}:${data.userId}`, data); return data; },
      update: async ({ where, data }: any) => {
        const key = where.id ? [...players.entries()].find(([, p]) => p.id === where.id)?.[0]
          : `${where.gameId_userId.gameId}:${where.gameId_userId.userId}`;
        const player = players.get(key!);
        players.set(key!, { ...player, ...data });
        return players.get(key!);
      },
      updateMany: async () => ({}),
      deleteMany: async () => ({ count: 0 }),
    },
    hero: { findUnique: async ({ where }: any) => heroes[where.id] ?? null },
    board: { findUnique: async ({ where }: any) => (where.id === source.id ? source : null) },
    gameState: {
      findUnique: async ({ where }: any) => states.get(where.gameId) ?? null,
      upsert: async ({ where, create }: any) => { states.set(where.gameId, create); return create; },
    },
    $transaction: serializeTx,
    $queryRaw: async () => [],
  };
  const redis = { getJson: async () => null, setJsonex: async () => 'OK', del: async () => 1 };
  return { prisma, redis, games, players, states, gameRow };
}

function makeService(db = makeDb()) {
  const saveState = jest.fn(async (_gameId: string, _state: GameState) => undefined);
  const service = new GameService(
    db.prisma,
    db.redis as any,
    new GameInitializationService(db.prisma, { saveState } as any),
    { recordAction: async () => 'id' } as any,
    { publishLobbyEvent: async () => ({}) } as any,
  );
  return { service, saveState, db };
}

function seedLobby(db: ReturnType<typeof makeDb>, opts: { ready?: boolean; heroIds?: Record<string, string | null> } = {}) {
  db.games.set('g1', { id: 'g1', hostId: 'u1', opponentId: 'u2', boardId: source.id,
    mode: 'ONE_V_ONE', status: 'LOBBY', code: 'AAAAAA', version: 0 });
  db.players.set('g1:u1', { id: 'p1', gameId: 'g1', userId: 'u1', seatOrder: 0,
    heroId: opts.heroIds?.u1 ?? null, isReady: opts.ready ?? false });
  db.players.set('g1:u2', { id: 'p2', gameId: 'g1', userId: 'u2', seatOrder: 1,
    heroId: opts.heroIds?.u2 ?? null, isReady: opts.ready ?? false });
}

describe('GD-016: selection composition', () => {
  it('rejects a hero already taken by the other lobby player', async () => {
    const { service, db } = makeService();
    seedLobby(db, { heroIds: { u1: 'medusa', u2: null } });
    await expect(service.selectHero('g1', 'u2', 'medusa')).rejects.toThrow(BadRequestException);
    await expect(service.selectHero('g1', 'u2', 'arthur')).resolves.toBeTruthy();
    await expect(service.selectHero('g1', 'u1', 'medusa')).resolves.toBeTruthy();
  });

  it('lets only one of two concurrent selections of the same hero through', async () => {
    const { service, db } = makeService();
    seedLobby(db);
    const results = await Promise.allSettled([
      service.selectHero('g1', 'u1', 'medusa'),
      service.selectHero('g1', 'u2', 'medusa'),
    ]);
    const rejected = results.filter(r => r.status === 'rejected');
    expect(rejected).toHaveLength(1);
    const roster = await db.prisma.gamePlayer.findMany({ where: { gameId: 'g1' } });
    expect(new Set(roster.map(p => p.heroId)).size).toBe(2);
    expect(roster.filter(p => p.heroId === 'medusa')).toHaveLength(1);
  });

  it('refuses to start a duplicated hero composition and stays in LOBBY', async () => {
    const { service, db, saveState } = makeService();
    seedLobby(db, { ready: true, heroIds: { u1: 'medusa', u2: 'medusa' } });
    await expect(service.startGame('g1', 'u1')).rejects.toThrow(BadRequestException);
    expect(db.games.get('g1').status).toBe('LOBBY');
    expect(saveState).not.toHaveBeenCalled();
  });
});

describe('GD-016: legal server-owned setup for the starter pair', () => {
  it.each([
    ['medusa-first', 'medusa', 'arthur'],
    ['arthur-first', 'arthur', 'medusa'],
  ])('%s orientation places sidekicks legally and exposes the first player', async (_name, seat0, seat1) => {
    const { service, saveState, db } = makeService();
    seedLobby(db, { ready: true, heroIds: { u1: seat0, u2: seat1 } });
    await service.startGame('g1', 'u1');
    expect(saveState).toHaveBeenCalledTimes(1);
    const state = saveState.mock.calls[0][1] as GameState;
    expect(state.phase).toBe('ACTION_MANEUVER');
    expect(state.boardState).toEqual(captured.boardState);
    // Explicit first player: persisted and driving the opening turn.
    expect(state.metadata.firstPlayerId).toBe('u1');
    expect(state.currentTurnPlayerId).toBe('u1');
    expect(state.metadata.actionsRemaining).toBe(2);
    // Distinct cells for all six fighters, every cell on the pinned board.
    const keys = state.fighters.map(f => `${f.position.x}:${f.position.y}`);
    expect(new Set(keys).size).toBe(6);
    for (const fighter of state.fighters) {
      const cell = state.boardState.cells[fighter.position.y]?.[fighter.position.x];
      expect(cell).toBeTruthy();
    }
    // Each sidekick on a distinct free space sharing a zone with its hero.
    for (const owner of ['u1', 'u2']) {
      const hero = state.fighters.find(f => f.ownerId === owner && f.type === 'HERO')!;
      const heroZones = new Set(getCellZones(state.boardState.cells[hero.position.y]?.[hero.position.x]));
      const sidekicks = state.fighters.filter(f => f.ownerId === owner && f.type !== 'HERO');
      expect(sidekicks.length).toBeGreaterThan(0);
      for (const sk of sidekicks) {
        const zones = getCellZones(state.boardState.cells[sk.position.y]?.[sk.position.x]);
        // sidekick must share at least one zone with its hero
        expect(zones.filter(z => heroZones.has(z))).not.toHaveLength(0);
      }
    }
  });

  it('keeps firstPlayerId and positions through compact state serialization', async () => {
    const { service, saveState, db } = makeService();
    seedLobby(db, { ready: true, heroIds: { u1: 'medusa', u2: 'arthur' } });
    await service.startGame('g1', 'u1');
    const state = saveState.mock.calls[0][1] as GameState;
    const serializer = new GameStateService(db.prisma, db.redis as any);
    const roundtrip = serializer.deserialize(JSON.parse(JSON.stringify(serializer.serialize(state))));
    expect(roundtrip.metadata.firstPlayerId).toBe('u1');
    expect(roundtrip.fighters.map(f => f.position)).toEqual(state.fighters.map(f => f.position));
  });
});
