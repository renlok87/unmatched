/** GD-016: real localhost HTTP GraphQL lobby flow — create/join/selectHero/
 * toggleReady/startGame with the production GameService, GameInitializationService,
 * GameStateService and resolvers. Fixture JSON database/cache/identities replace
 * Postgres/Redis/JWT; this is not a deployed-stack or UE test. */
import 'reflect-metadata';
import { writeFileSync } from 'node:fs';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { GameResolver } from '../game.resolver';
import { GameService } from '../game.service';
import { GameStateService } from '../game-state.service';
import { GameInitializationService } from '../services/game-initialization.service';
import { PrismaService } from '../../database/prisma.service';
import { RedisService } from '../../redis/redis.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { GameActionService } from '../services/game-action.service';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';
import { getCellZones } from '../../game-engine/models';

const root = resolve(__dirname, '../../../..');
const source = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-board.json'), 'utf8'),
).adminBoard;

const heroes: Record<string, any> = {
  medusa: { id: 'medusa', name: 'Medusa', health: 16, movement: 3,
    properties: { attackType: 'ranged' }, sidekicks: [{ name: 'Harpy', count: 3, health: 1 }] },
  arthur: { id: 'arthur', name: 'King Arthur', health: 18, movement: 2,
    sidekicks: [{ name: 'Merlin', health: 7, attackType: 'ranged' }] },
};
for (const hero of Object.values(heroes)) {
  hero.cards = [{ id: `${hero.id}-fixture`, name: 'Fixture', cardType: 'VERSATILE', count: 30, effects: [] }];
}

const gameFields = 'id status mode boardId version opponentId '
  + 'players { userId username heroId isReady seatOrder }';
const operations = {
  createGame: `mutation Create($input: CreateGameDto!) { createGame(input: $input) { ${gameFields} } }`,
  joinGame: `mutation Join($input: JoinGameDto!) { joinGame(input: $input) { ${gameFields} } }`,
  selectHero: `mutation Select($gameId: String!, $heroId: String!) { selectHero(gameId: $gameId, heroId: $heroId) { ${gameFields} } }`,
  toggleReady: `mutation Ready($gameId: String!) { toggleReady(gameId: $gameId) { ${gameFields} } }`,
  startGame: `mutation Start($gameId: String!) { startGame(gameId: $gameId) { ${gameFields} } }`,
  gameState: `query State($gameId: String!) { gameState(gameId: $gameId) { state sequenceNumber currentTurnPlayerId phase } }`,
};

describe('GD-016: lobby hero selection over real HTTP transport', () => {
  let app: INestApplication;
  let url: string;
  let prisma: any;
  const evidence: { http: any[]; checks: string[] } = { http: [], checks: [] };

  beforeAll(async () => {
    const games = new Map<string, any>();
    const players = new Map<string, any>();
    const states = new Map<string, any>();
    const users = new Map<string, any>([
      ['a', { id: 'a', username: 'user-a', avatar: null }],
      ['b', { id: 'b', username: 'user-b', avatar: null }],
    ]);
    let nextId = 0;
    const user = (id: string) => users.get(id);
    const gameRow = (id: string) => {
      const game = games.get(id);
      if (!game) return null;
      const roster = [...players.values()].filter(p => p.gameId === id)
        .sort((x, y) => x.seatOrder - y.seatOrder);
      return {
        ...game,
        host: user(game.hostId),
        opponent: game.opponentId ? user(game.opponentId) : null,
        players: roster.map(p => ({ ...p, user: user(p.userId) })),
        state: states.get(id) ?? null,
      };
    };
    // Serialized transactions: fixture storage is single-node, the tail chain
    // stands in for production isolation between two concurrent selections.
    let txTail = Promise.resolve();
    const serializeTx = (run: (tx: unknown) => unknown) => {
      const previous = txTail;
      let done!: () => void;
      txTail = new Promise<void>(yes => { done = yes; });
      return previous.then(() => Promise.resolve(run(prisma))).finally(() => done());
    };
    const cache = new Map<string, any>();
    const json = <T>(value: T): T => JSON.parse(JSON.stringify(value));
    prisma = {
      game: {
        findUnique: async ({ where }: any) =>
          where.id ? gameRow(where.id) : (games.get(where.code) ?? null),
        findFirst: async ({ where }: any) =>
          [...games.values()].find(g => g.idempotencyKey === where.idempotencyKey) ?? null,
        count: async () => 0,
        create: async ({ data }: any) => {
          const id = `g${++nextId}`;
          games.set(id, { createdAt: new Date(), updatedAt: new Date(), version: 0, ...data, id });
          return games.get(id);
        },
        update: async ({ where, data }: any) => {
          const game = games.get(where.id);
          games.set(where.id, { ...game, ...data, updatedAt: new Date() });
          return games.get(where.id);
        },
      },
      gamePlayer: {
        findUnique: async ({ where }: any) =>
          players.get(`${where.gameId_userId.gameId}:${where.gameId_userId.userId}`) ?? null,
        findFirst: async ({ where }: any) =>
          [...players.values()].find(p => p.gameId === where.gameId && p.userId === where.userId) ?? null,
        findMany: async ({ where }: any) =>
          [...players.values()].filter(p => p.gameId === where.gameId)
            .sort((x, y) => x.seatOrder - y.seatOrder),
        create: async ({ data }: any) => {
          const id = `p${++nextId}`;
          players.set(`${data.gameId}:${data.userId}`, { hasPassed: false, isReady: false, ...data, id });
          return players.get(`${data.gameId}:${data.userId}`);
        },
        update: async ({ where, data }: any) => {
          const key = where.id
            ? [...players.entries()].find(([, p]) => p.id === where.id)?.[0]
            : `${where.gameId_userId.gameId}:${where.gameId_userId.userId}`;
          const player = players.get(key!);
          players.set(key!, { ...player, ...data });
          return players.get(key!);
        },
      },
      hero: { findUnique: async ({ where }: any) => heroes[where.id] ?? null },
      board: { findUnique: async ({ where }: any) => (where.id === source.id ? source : null),
        findFirst: async () => source },
      user: { findUnique: async ({ where }: any) => users.get(where.id) ?? null },
      gameState: {
        findUnique: async ({ where }: any) => states.get(where.gameId) ?? null,
        upsert: async ({ where, create, update }: any) => {
          const row = states.has(where.gameId)
            ? { ...states.get(where.gameId), ...update }
            : create;
          states.set(where.gameId, row);
          return row;
        },
      },
      $transaction: serializeTx,
      $queryRaw: async () => [],
    };
    const redis = {
      getJson: async (key: string) => (cache.has(key) ? json(cache.get(key)) : null),
      setJsonex: async (key: string, _ttl: number, value: unknown) => { cache.set(key, json(value)); return 'OK'; },
      del: async (key: string) => { cache.delete(key); },
      subscribe: () => {}, publish: async () => 1,
    };
    const module = await Test.createTestingModule({
      imports: [GraphQLModule.forRoot<ApolloDriverConfig>({
        driver: ApolloDriver, autoSchemaFile: true, csrfPrevention: false,
      })],
      providers: [GameResolver, GameService, GameInitializationService, GameStateService,
        { provide: PrismaService, useValue: prisma }, { provide: RedisService, useValue: redis },
        { provide: GameActionService, useValue: { recordAction: async () => 'id' } },
        { provide: GameSubscriptionService, useValue: { publishLobbyEvent: async () => ({}),
          publishGameUpdate: async () => ({}) } },
      ],
    }).overrideGuard(GqlAuthGuard).useValue({ canActivate: (context: any) => {
      const req = context.getArgByIndex(2).req;
      const userId = req.headers['x-fixture-user'];
      if (!['a', 'b'].includes(userId)) return false;
      req.user = { id: userId };
      return true;
    } }).compile();
    app = module.createNestApplication();
    app.useLogger(false);
    app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
    await app.listen(0, '127.0.0.1');
    url = await app.getUrl();
  }, 15000);

  afterAll(async () => {
    await app?.close();
    if (process.env.S04_LOBBY_REPORT && evidence.checks.length === 2) {
      writeFileSync(process.env.S04_LOBBY_REPORT, JSON.stringify({
        scope: 'Real localhost HTTP GraphQL; production lobby resolvers/GameService/GameInitializationService/GameStateService; synthetic identities, JSON database/cache, no deployed Postgres/Redis/JWT/UE.',
        ...evidence,
      }, null, 2) + '\n');
    }
  });

  async function http(stage: string, viewer: string, operation: keyof typeof operations, variables: any) {
    const response = await fetch(`${url}/graphql`, { method: 'POST', headers: {
      'content-type': 'application/json', 'x-fixture-user': viewer,
    }, body: JSON.stringify({ query: operations[operation], variables }) });
    const body: any = await response.json();
    evidence.http.push({ stage, viewer, request: { operation, variables }, status: response.status, response: body });
    return body;
  }

  async function startLobby(selects: Array<[string, string]> = [['a', 'medusa'], ['b', 'arthur']]) {
    const created = await http('create', 'a', 'createGame', { input: { mode: 'ONE_V_ONE', boardId: source.id } });
    expect(created.errors).toBeUndefined();
    const gameId = created.data.createGame.id;
    const joined = await http('join', 'b', 'joinGame', { input: { gameId } });
    expect(joined.errors).toBeUndefined();
    expect(joined.data.joinGame.players).toHaveLength(2);
    for (const [viewer, heroId] of selects) {
      const selected = await http(`select-${heroId}`, viewer, 'selectHero', { gameId, heroId });
      expect(selected.errors).toBeUndefined();
    }
    return gameId;
  }

  it('runs create/join/select/ready/start through HTTP and exposes the legal server setup', async () => {
    const created = await http('create', 'a', 'createGame', { input: { mode: 'ONE_V_ONE', boardId: source.id } });
    expect(created.errors).toBeUndefined();
    const gameId = created.data.createGame.id;
    expect(created.data.createGame.status).toBe('LOBBY');
    expect(created.data.createGame.players).toHaveLength(1);

    const joined = await http('join', 'b', 'joinGame', { input: { gameId } });
    expect(joined.errors).toBeUndefined();
    expect(joined.data.joinGame.players).toHaveLength(2);
    expect(joined.data.joinGame.opponentId).toBe('b');

    expect((await http('select-medusa-a', 'a', 'selectHero', { gameId, heroId: 'medusa' })).errors).toBeUndefined();
    const duplicate = await http('select-medusa-b-duplicate', 'b', 'selectHero', { gameId, heroId: 'medusa' });
    expect(duplicate.errors).toBeDefined();
    const rosterAfter = await http('game-after-duplicate', 'a', 'gameState', { gameId });
    expect(rosterAfter.errors).toBeDefined(); // no state yet — the game is still a lobby

    const switched = await http('select-arthur-b', 'b', 'selectHero', { gameId, heroId: 'arthur' });
    expect(switched.errors).toBeUndefined();
    const heroIds = switched.data.selectHero.players
      .sort((p: any, q: any) => p.seatOrder - q.seatOrder).map((p: any) => p.heroId);
    expect(heroIds).toEqual(['medusa', 'arthur']);

    const premature = await http('start-not-ready', 'a', 'startGame', { gameId });
    expect(premature.errors).toBeDefined();

    expect((await http('ready-a', 'a', 'toggleReady', { gameId })).errors).toBeUndefined();
    const bothReady = await http('ready-b', 'b', 'toggleReady', { gameId });
    expect(bothReady.errors).toBeUndefined();
    expect(bothReady.data.toggleReady.players.every((p: any) => p.isReady)).toBe(true);

    const started = await http('start', 'a', 'startGame', { gameId });
    expect(started.errors).toBeUndefined();
    expect(started.data.startGame.status).toBe('IN_PROGRESS');

    for (const viewer of ['a', 'b']) {
      const snapshot = await http(`state-${viewer}`, viewer, 'gameState', { gameId });
      expect(snapshot.errors).toBeUndefined();
      const state = JSON.parse(snapshot.data.gameState.state);
      expect(snapshot.data.gameState.sequenceNumber).toBe(1);
      expect(snapshot.data.gameState.currentTurnPlayerId).toBe('a');
      expect(state.phase).toBe('ACTION_MANEUVER');
      expect(state.metadata.firstPlayerId).toBe('a');
      expect(state.metadata.actionsRemaining).toBe(2);
      expect(new Set(state.fighters.map((f: any) => `${f.position.x}:${f.position.y}`)).size).toBe(6);
      for (const owner of ['a', 'b']) {
        const hero = state.fighters.find((f: any) => f.ownerId === owner && f.type === 'HERO');
        const heroZones = new Set(getCellZones(state.boardState.cells[hero.position.y]?.[hero.position.x]));
        const sidekicks = state.fighters.filter((f: any) => f.ownerId === owner && f.type !== 'HERO');
        expect(sidekicks.length).toBeGreaterThan(0);
        for (const sk of sidekicks) {
          expect(getCellZones(state.boardState.cells[sk.position.y]?.[sk.position.x])
            .filter((z: string) => heroZones.has(z))).not.toHaveLength(0);
        }
      }
      if (viewer === 'b') {
        expect(state.handZones.a.cards.every((c: any) => c.isVisible === false)).toBe(true);
      }
    }
    evidence.checks.push('HTTP create/join/select/ready/start; duplicate hero rejected; premature start rejected; legal setup + explicit first player exposed to both participants');
  });

  it('serializes two racing HTTP selections of one hero into a single winner', async () => {
    const gameId = await startLobby([]);
    const [first, second] = await Promise.all([
      http('race-a', 'a', 'selectHero', { gameId, heroId: 'medusa' }),
      http('race-b', 'b', 'selectHero', { gameId, heroId: 'medusa' }),
    ]);
    const failures = [first, second].filter(r => r.errors);
    expect(failures).toHaveLength(1);
    const winner = first.errors ? second : first;
    const roster = winner.data.selectHero.players;
    expect(roster.filter((p: any) => p.heroId === 'medusa')).toHaveLength(1);
    evidence.checks.push('Two concurrent HTTP selectHero of one hero: exactly one rejected, roster keeps a single instance');
  });
});
