/** GD-029: S08 lobby contract — safe code→gameId resolution and duplicate
 * create idempotency, exercised over the real GameResolver/GameService with
 * a JSON fixture database (same harness style as s04-lobby-transport.spec).
 * Covers:
 *  - gameByCode returns ONLY joinable LOBBY rooms with a free slot;
 *    full/started/unknown codes are indistinguishable (null);
 *  - gameByCode response feeds joinGame (the UE grey flow's entry);
 *  - createGame with the same idempotency key never creates a second room. */
import 'reflect-metadata';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { ThrottlerModule } from '@nestjs/throttler';
import { GameResolver } from '../game.resolver';
import { GameService } from '../game.service';
import { GameStateService } from '../game-state.service';
import { GameInitializationService } from '../services/game-initialization.service';
import { PrismaService } from '../../database/prisma.service';
import { RedisService } from '../../redis/redis.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { GameActionService } from '../services/game-action.service';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';
import { GqlThrottlerGuard } from '../guards/gql-throttler.guard';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const boardSource = JSON.parse(readFileSync(
  resolve(__dirname, '../../../../docs/game-design/evidence/S01/content-board.json'), 'utf8'),
).adminBoard;

const gameFields = 'id code status mode hostId boardId opponentId '
  + 'players { userId username heroId isReady seatOrder }';

const operations = {
  createGame: `mutation Create($input: CreateGameDto!, $key: String) { createGame(input: $input, idempotencyKey: $key) { ${gameFields} } }`,
  gameByCode: `query ByCode($code: String!) { gameByCode(code: $code) { ${gameFields} } }`,
  joinGame: `mutation Join($input: JoinGameDto!) { joinGame(input: $input) { ${gameFields} } }`,
  selectHero: `mutation Select($gameId: String!, $heroId: String!) { selectHero(gameId: $gameId, heroId: $heroId) { ${gameFields} } }`,
  toggleReady: `mutation Ready($gameId: String!) { toggleReady(gameId: $gameId) { ${gameFields} } }`,
  startGame: `mutation Start($gameId: String!) { startGame(gameId: $gameId) { ${gameFields} } }`,
};

describe('S08 GD-029: code resolution and duplicate-create guard', () => {
  let app: INestApplication;
  let url: string;
  let prisma: any;

  beforeAll(async () => {
    const games = new Map<string, any>();
    const players = new Map<string, any>();
    const states = new Map<string, any>();
    const users = new Map<string, any>([
      ['a', { id: 'a', username: 'user-a', avatar: null }],
      ['b', { id: 'b', username: 'user-b', avatar: null }],
    ]);
    let nextId = 0;
    let nextCode = 0;
    const user = (id: string) => users.get(id);
    const gameRow = (id: string) => {
      const game = games.get(id);
      if (!game) return null;
      const roster = [...players.values()].filter((p) => p.gameId === id)
        .sort((x, y) => x.seatOrder - y.seatOrder);
      return {
        ...game,
        host: user(game.hostId),
        opponent: game.opponentId ? user(game.opponentId) : null,
        players: roster.map((p) => ({ ...p, user: user(p.userId) })),
        state: states.get(id) ?? null,
      };
    };
    prisma = {
      game: {
        findUnique: async ({ where }: any) => {
          if (where.id) return gameRow(where.id);
          const byCode = [...games.values()].find((g) => g.code === where.code);
          return byCode ? gameRow(byCode.id) : null;
        },
        findFirst: async ({ where }: any) =>
          [...games.values()].find((g) => g.idempotencyKey === where.idempotencyKey
            && g.hostId === where.hostId) ?? null,
        count: async () => 0,
        create: async ({ data }: any) => {
          const id = `g${++nextId}`;
          const code = `C${++nextCode}DEFG`;
          games.set(id, { createdAt: new Date(), updatedAt: new Date(), version: 0,
            boardState: null, startedAt: null, endedAt: null, winnerId: null, ...data, id, code });
          return games.get(id);
        },
        update: async ({ where, data }: any) => {
          const game = games.get(where.id);
          games.set(where.id, { ...game, ...data, updatedAt: new Date() });
          return games.get(where.id);
        },
        updateMany: async ({ where, data }: any) => {
          const game = games.get(where.id);
          if (!game || (where.status && !(typeof where.status === 'string'
            ? game.status === where.status : where.status.in?.includes(game.status)))) return { count: 0 };
          games.set(where.id, { ...game, ...data, updatedAt: new Date() });
          return { count: 1 };
        },
      },
      gamePlayer: {
        findUnique: async ({ where }: any) =>
          players.get(`${where.gameId_userId.gameId}:${where.gameId_userId.userId}`) ?? null,
        findFirst: async ({ where }: any) =>
          [...players.values()].find((p) => p.gameId === where.gameId && p.userId === where.userId) ?? null,
        findMany: async ({ where }: any) =>
          [...players.values()].filter((p) => p.gameId === where.gameId)
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
      hero: { findUnique: async ({ where }: any) => ({ id: where.id, name: where.id, health: 10,
        movement: 2, properties: { attackType: 'melee' }, sidekicks: [],
        cards: [{ id: `${where.id}-card`, name: 'Fixture', cardType: 'VERSATILE', count: 30, effects: [] }] }) },
      board: { findUnique: async ({ where }: any) => (where.id === boardSource.id ? boardSource : null),
        findFirst: async () => boardSource },
      user: { findUnique: async ({ where }: any) => users.get(where.id) ?? null },
      gameState: {
        findUnique: async ({ where }: any) => states.get(where.gameId) ?? null,
        upsert: async ({ where, create }: any) => {
          states.set(where.gameId, create);
          return create;
        },
      },
      $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
      $queryRaw: async () => [],
    };
    const cache = new Map<string, any>();
    const redis = {
      getJson: async (key: string) => (cache.has(key) ? JSON.parse(JSON.stringify(cache.get(key))) : null),
      setJsonex: async (key: string, _ttl: number, value: unknown) => { cache.set(key, value); return 'OK'; },
      del: async (key: string) => { cache.delete(key); },
      subscribe: () => {}, publish: async () => 1,
    };
    const module = await Test.createTestingModule({
      imports: [GraphQLModule.forRoot<ApolloDriverConfig>({
        driver: ApolloDriver, autoSchemaFile: true, csrfPrevention: false,
      }), ThrottlerModule.forRoot({
        throttlers: [{ ttl: 60000, limit: 15 }], setHeaders: false,
      })],
      providers: [GameResolver, GameService, GameInitializationService, GameStateService,
        GqlThrottlerGuard,
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

  afterAll(async () => { await app?.close(); });

  async function http(viewer: string, operation: keyof typeof operations, variables: any) {
    const response = await fetch(`${url}/graphql`, { method: 'POST', headers: {
      'content-type': 'application/json', 'x-fixture-user': viewer,
    }, body: JSON.stringify({ query: operations[operation], variables }) });
    return await response.json() as any;
  }

  it('duplicate createGame with the same idempotency key returns the same room', async () => {
    const first = await http('a', 'createGame', { input: { mode: 'ONE_V_ONE' }, key: 'stable-key-1' });
    expect(first.errors).toBeUndefined();
    const second = await http('a', 'createGame', { input: { mode: 'ONE_V_ONE' }, key: 'stable-key-1' });
    expect(second.errors).toBeUndefined();
    expect(second.data.createGame.id).toBe(first.data.createGame.id);
    expect(second.data.createGame.code).toBe(first.data.createGame.code);
  });

  it('gameByCode resolves only joinable LOBBY rooms with a free slot', async () => {
    const created = await http('a', 'createGame', { input: { mode: 'ONE_V_ONE' } });
    const code = created.data.createGame.code;
    const gameId = created.data.createGame.id;

    const resolved = await http('b', 'gameByCode', { code });
    expect(resolved.errors).toBeUndefined();
    expect(resolved.data.gameByCode.id).toBe(gameId);
    expect(resolved.data.gameByCode.status).toBe('LOBBY');
    expect(resolved.data.gameByCode.opponentId).toBeNull();

    // unknown code is indistinguishable from any non-joinable state
    const unknown = await http('b', 'gameByCode', { code: 'ZZZZZZ' });
    expect(unknown.errors).toBeUndefined();
    expect(unknown.data.gameByCode).toBeNull();
  });

  it('full room resolves to null; the resolution feeds joinGame', async () => {
    const created = await http('a', 'createGame', { input: { mode: 'ONE_V_ONE' } });
    const code = created.data.createGame.code;

    const joined = await http('b', 'joinGame', { input: { gameId: created.data.createGame.id } });
    expect(joined.errors).toBeUndefined();
    expect(joined.data.joinGame.players).toHaveLength(2);

    const full = await http('b', 'gameByCode', { code });
    expect(full.errors).toBeUndefined();
    expect(full.data.gameByCode).toBeNull(); // occupied: no room disclosure
  });

  it('started room no longer resolves by code', async () => {
    const created = await http('a', 'createGame', { input: { mode: 'ONE_V_ONE' } });
    const gameId = created.data.createGame.id;
    const code = created.data.createGame.code;
    await http('b', 'joinGame', { input: { gameId } });
    await http('a', 'selectHero', { gameId, heroId: 'medusa' });
    await http('b', 'selectHero', { gameId, heroId: 'arthur' });
    await http('a', 'toggleReady', { gameId });
    await http('b', 'toggleReady', { gameId });
    const started = await http('a', 'startGame', { gameId });
    expect(started.errors).toBeUndefined();
    expect(started.data.startGame.status).toBe('IN_PROGRESS');

    const after = await http('b', 'gameByCode', { code });
    expect(after.errors).toBeUndefined();
    expect(after.data.gameByCode).toBeNull();
  });
});
