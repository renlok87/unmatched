/** Real localhost HTTP GraphQL + graphql-ws transport with production resolvers,
 * executor, subscription filtering and compact state serialization.
 * Synthetic identities, JSON-backed database/cache and a local lock adapter replace
 * external infrastructure; this is not a deployed JWT/Postgres/Redis or UE test. */
import 'reflect-metadata';
import { writeFileSync } from 'node:fs';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { createClient, Client } from 'graphql-ws';
import { GameActionsResolver } from './game-actions.resolver';
import { GameSubscriptionResolver } from './game-subscription.resolver';
import { GameResolver } from '../game.resolver';
import { GameService } from '../game.service';
import { GameStateService } from '../game-state.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { PrismaService } from '../../database/prisma.service';
import { RedisService } from '../../redis/redis.service';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { CombatTimeoutService } from '../services/combat-timeout.service';
import { GameActionService } from '../services/game-action.service';
import { AiTurnService } from '../services/ai-turn.service';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';
import { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { GameState, GamePhase } from '../../game-engine/models';
import { s03Fixture, s03Engine } from '../../test/fixtures/s03-engine.fixture';

const WebSocket = require('ws');
const json = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const fields = 'state sequenceNumber phase currentTurnPlayerId turnCount';
const operations = {
  beginManeuver: `mutation Begin($input: BeginManeuverDto!) { beginManeuver(input: $input) { ${fields} } }`,
  maneuver: `mutation Complete($input: ManeuverDto!) { maneuver(input: $input) { ${fields} } }`,
  discardToLimit: `mutation Discard($input: DiscardToLimitDto!) { discardToLimit(input: $input) { ${fields} } }`,
  gameState: `query Snapshot($gameId: String!) { gameState(gameId: $gameId) { ${fields} } }`,
};
const subscriptionQuery = `subscription Updates($gameId: String!, $since: Float) {
  gameStateUpdated(gameId: $gameId, since: $since) {
    gameId sequenceNumber phase currentTurnPlayerId turnCount handZones fighters metadata
  }
}`;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function bounded<T>(promise: Promise<T>, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`Timed out: ${label}`)), 5000);
    promise.then(value => { clearTimeout(timeout); resolve(value); },
      error => { clearTimeout(timeout); reject(error); });
  });
}

describe('S03 real HTTP/WS resource lifecycle', () => {
  let app: INestApplication;
  let url: string;
  let states: GameStateService;
  let subscriptions: GameSubscriptionService;
  const rows = new Map<string, any>();
  const cache = new Map<string, any>();
  const evidence: { http: any[]; ws: any[]; checks: string[] } = { http: [], ws: [], checks: [] };
  const clients = new Set<Client>();
  let registration: ReturnType<typeof deferred<void>> | undefined;

  beforeAll(async () => {
    const redis = {
      getJson: async (key: string) => cache.has(key) ? json(cache.get(key)) : null,
      setJsonex: async (key: string, _ttl: number, value: unknown) => { cache.set(key, json(value)); return 'OK'; },
      del: async (key: string) => { cache.delete(key); },
      subscribe: () => {}, publish: async () => 1,
    };
    const gameStateTable = {
      findUnique: async ({ where }: any) => rows.has(where.gameId) ? json(rows.get(where.gameId)) : null,
      upsert: async ({ where, create, update }: any) => {
        const row = json(rows.has(where.gameId) ? { ...rows.get(where.gameId), ...update } : create);
        rows.set(where.gameId, row);
        return row;
      },
    };
    const prisma = {
      gameState: gameStateTable,
      game: { findUnique: async ({ where }: any) => rows.has(where.id) ? { status: 'IN_PROGRESS' } : null,
        update: async () => ({}) },
      gamePlayer: { findUnique: async ({ where }: any) =>
        rows.has(where.gameId_userId.gameId) && ['a', 'b'].includes(where.gameId_userId.userId) ? {} : null },
      $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
    };
    let lockTail = Promise.resolve();
    const localLock = { withLockOptions: async (_key: string, run: () => Promise<any>) => {
      const previous = lockTail;
      const release = deferred<void>();
      lockTail = release.promise;
      await previous;
      try { return await run(); } finally { release.resolve(); }
    } };
    const module = await Test.createTestingModule({
      imports: [GraphQLModule.forRoot<ApolloDriverConfig>({
        driver: ApolloDriver, autoSchemaFile: true, csrfPrevention: false,
        subscriptions: { 'graphql-ws': true },
        context: (ctx: any) => ({ req: ctx.req ?? { headers: { 'x-fixture-user': ctx.connectionParams?.fixtureUser } } }),
        includeStacktraceInErrorResponses: false,
      })],
      providers: [GameActionsResolver, GameSubscriptionResolver, GameResolver, GameStateService, GameSubscriptionService,
        { provide: GameActionExecutorService, useValue: s03Engine().executor },
        { provide: PrismaService, useValue: prisma }, { provide: RedisService, useValue: redis },
        { provide: DistributedLockService, useValue: localLock },
        { provide: CombatTimeoutService, useValue: { scheduleAutoResolve: async () => {}, cancelAutoResolve: async () => {} } },
        { provide: GameActionService, useValue: { recordAction: async () => {} } },
        { provide: AiTurnService, useValue: { maybeRunAiTurns: async () => {} } },
        { provide: GameService, useValue: { requireParticipation: async (gameId: string, userId: string) => {
          if (!rows.has(gameId) || !['a', 'b'].includes(userId)) throw new Error('Unknown fixture participant');
        } } },
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
    states = app.get(GameStateService);
    subscriptions = app.get(GameSubscriptionService);
    // Observe the real iterator's first pull, so requests never race subscription setup.
    const originalIterator = subscriptions.asyncIteratorForGame.bind(subscriptions);
    jest.spyOn(subscriptions, 'asyncIteratorForGame').mockImplementation(gameId => {
      const iterator = originalIterator(gameId);
      const originalNext = iterator.next.bind(iterator);
      iterator.next = (...args: any[]) => {
        const pending = originalNext(...args);
        if (registration) {
          const ready = registration;
          registration = undefined;
          setImmediate(() => ready.resolve());
        }
        return pending;
      };
      return iterator;
    });
    await app.listen(0, '127.0.0.1');
    url = await app.getUrl();
  }, 15000);

  afterAll(async () => {
    await Promise.all([...clients].map(client => client.dispose()));
    await app?.close();
    if (process.env.S03_TRANSPORT_REPORT && evidence.checks.length === 3) {
      writeFileSync(process.env.S03_TRANSPORT_REPORT, JSON.stringify({
        scope: 'Real localhost HTTP GraphQL and graphql-ws; production resolvers/executor/state serializer/filter/subscriptions; synthetic auth, in-memory JSON database/cache, local lock, no AI/queue/UE.',
        ...evidence,
      }, null, 2) + '\n');
    }
  });

  function seed(gameId: string, hand = 0, actions = 2) {
    const base = s03Fixture(hand, actions);
    const state = { ...base, gameId, decks: { ...base.decks,
      a: { ...base.decks.a, drawPile: base.decks.a.drawPile.map((card, i) => i === 0
        ? { ...card, cardId: 'secret-drawn-definition', bannerName: 'secret-drawn-banner', text: 'secret-drawn-text' } : card) } } };
    rows.set(gameId, { gameId, sequenceNumber: state.sequenceNumber, state: json(states.serialize(state)) });
    cache.delete(`gamestate:${gameId}`);
    return state;
  }

  async function http(stage: string, viewer: string, operation: keyof typeof operations, variables: any) {
    const response = await fetch(`${url}/graphql`, { method: 'POST', headers: {
      'content-type': 'application/json', 'x-fixture-user': viewer,
    }, body: JSON.stringify({ query: operations[operation], variables }) });
    const body: any = await response.json();
    evidence.http.push({ stage, viewer, request: { operation, variables }, status: response.status, response: body });
    return body;
  }

  async function snapshot(stage: string, viewer: string, gameId: string): Promise<GameState> {
    const response = await http(stage, viewer, 'gameState', { gameId });
    expect(response.errors).toBeUndefined();
    return JSON.parse(response.data.gameState.state);
  }

  async function watch(viewer: string, gameId: string, since = 10) {
    const ready = deferred<void>();
    registration = ready;
    const queue: any[] = [];
    let waiting: ReturnType<typeof deferred<any>> | undefined;
    const client = createClient({ url: url.replace('http', 'ws') + '/graphql', webSocketImpl: WebSocket,
      connectionParams: { fixtureUser: viewer }, retryAttempts: 0 });
    clients.add(client);
    const stop = client.subscribe({ query: subscriptionQuery, variables: { gameId, since } }, {
      next: payload => {
        evidence.ws.push({ viewer, gameId, payload });
        if (waiting) { waiting.resolve(payload); waiting = undefined; } else queue.push(payload);
      },
      error: error => { ready.reject(error); waiting?.reject(error); }, complete: () => {},
    });
    await bounded(ready.promise, `subscription ${viewer}/${gameId}`);
    return {
      next: async () => {
        const payload = queue.length ? queue.shift() : await bounded((waiting = deferred<any>()).promise, `WS update ${viewer}/${gameId}`);
        expect(payload.errors).toBeUndefined();
        const state = payload.data.gameStateUpdated;
        return { ...state, handZones: JSON.parse(state.handZones), metadata: JSON.parse(state.metadata), fighters: JSON.parse(state.fighters) };
      },
      close: async () => { stop(); await client.dispose(); clients.delete(client); },
    };
  }

  async function mutate(stage: string, operation: 'beginManeuver' | 'maneuver' | 'discardToLimit', input: any,
    beforeSequence: number, observers: Awaited<ReturnType<typeof watch>>[]) {
    const response = await http(stage, 'a', operation, { input });
    expect(response.errors).toBeUndefined();
    const state = JSON.parse(response.data[operation].state) as GameState;
    expect(state.sequenceNumber).toBe(beforeSequence + 1);
    const updates = await Promise.all(observers.map(observer => observer.next()));
    for (const update of updates) expect(update.sequenceNumber).toBe(state.sequenceNumber);
    return { state, updates };
  }

  it('draw-only maneuver survives HTTP snapshot + WS reconnect and rejects both replays', async () => {
    const initial = seed('s03-transport-reconnect');
    let owner = await watch('a', initial.gameId);
    const other = await watch('b', initial.gameId);
    try {
      const request = { gameId: initial.gameId, expectedSequenceNumber: initial.sequenceNumber };
      const begun = await mutate('begin-draw-only', 'beginManeuver', request, 10, [owner, other]);
      expect(begun.updates[0].handZones.a.cards[0]).toMatchObject({ id: 'a-new', name: 'a-new', boostValue: 3 });
      expect(begun.updates[1].handZones.a.cards[0]).toMatchObject({ name: '???', isVisible: false });
      expect(begun.updates[1].handZones.a.cards[0].boostValue).toBeUndefined();
      for (const forbidden of ['a-new', 'secret-drawn-definition', 'secret-drawn-banner', 'secret-drawn-text', 'VERSATILE', 'boostValue']) {
        expect(JSON.stringify(begun.updates[1].handZones.a)).not.toContain(forbidden);
        const otherPayload = evidence.ws.filter(event => event.viewer === 'b' && event.gameId === initial.gameId).at(-1);
        expect(JSON.stringify(otherPayload.payload)).not.toContain(forbidden);
      }
      for (const viewer of ['a', 'b']) {
        const view = await snapshot('begin-view', viewer, initial.gameId);
        expect(view.decks.a.topCard).toBeUndefined();
        expect(view.decks.b.topCard).toBeUndefined();
        expect(JSON.stringify(view.decks)).not.toContain('a-next');
        expect(JSON.stringify(view.decks)).not.toContain('b-new');
        if (viewer === 'b') {
          const rawHttp = evidence.http.at(-1).response;
          for (const forbidden of ['a-new', 'secret-drawn-definition', 'secret-drawn-banner', 'secret-drawn-text', 'VERSATILE', 'boostValue']) {
            expect(JSON.stringify(rawHttp)).not.toContain(forbidden);
          }
        }
      }
      await owner.close();
      await states.invalidateStateCache(initial.gameId);
      owner = await watch('a', initial.gameId, 11);
      const restored = await snapshot('reconnect-db-snapshot', 'a', initial.gameId);
      expect(restored.metadata.pendingManeuver).toEqual(begun.state.metadata.pendingManeuver);
      expect(restored.sequenceNumber).toBe(11);
      expect(restored.handZones.a.cards).toHaveLength(1);
      expect(restored.decks.a.drawPile).toHaveLength(1);
      const restoredOther = await snapshot('reconnect-other-snapshot', 'b', initial.gameId);
      expect(restoredOther.metadata.pendingManeuver).toEqual(restored.metadata.pendingManeuver);
      expect(restoredOther.handZones.a.cards[0]).toMatchObject({ id: 'hidden-0', isVisible: false });
      const prematureReplay = await http('pending-begin-replay', 'a', 'beginManeuver', { input: request });
      expect(prematureReplay.errors).toBeDefined();
      const finish = { gameId: initial.gameId, maneuverId: restored.metadata.pendingManeuver!.id, moves: [] };
      const completed = await mutate('complete-draw-only', 'maneuver', finish, 11, [owner, other]);
      expect(completed.state.handZones.a.cards).toHaveLength(1);
      expect(completed.state.metadata.actionsRemaining).toBe(1);
      expect(completed.state.metadata.pendingManeuver).toBeUndefined();
      expect((await http('completed-replay', 'a', 'maneuver', { input: finish })).errors).toBeDefined();
      expect((await http('stale-begin-replay', 'a', 'beginManeuver', { input: request })).errors).toBeDefined();
      expect((await snapshot('after-replays', 'a', initial.gameId)).sequenceNumber).toBe(12);
      evidence.checks.push('HTTP/WS draw-only, both viewers, cache eviction, reconnect and replay rejection');
    } finally { await owner.close(); await other.close(); }
  });

  it('allows the card received over HTTP/WS to boost the same maneuver', async () => {
    const initial = seed('s03-transport-boost');
    const owner = await watch('a', initial.gameId);
    const other = await watch('b', initial.gameId);
    try {
      const begun = await mutate('begin-boost', 'beginManeuver', { gameId: initial.gameId, expectedSequenceNumber: 10 }, 10, [owner, other]);
      const cardId = begun.state.handZones.a.cards[0].id;
      const completed = await mutate('complete-new-card-boost', 'maneuver', { gameId: initial.gameId,
        maneuverId: begun.state.metadata.pendingManeuver!.id, boostCardId: cardId,
        moves: [{ fighterId: 'a', path: [1, 2, 3, 4, 5].map(x => ({ x, y: 0 })) }] }, 11, [owner, other]);
      expect(completed.state.fighters[0].position).toEqual({ x: 5, y: 0 });
      expect(completed.state.handZones.a.cards).toHaveLength(0);
      expect(completed.state.discardPiles.a.map(card => card.id)).toEqual([cardId]);
      expect(completed.state.decks.a.drawPile).toHaveLength(1);
      expect(completed.state.metadata.actionsRemaining).toBe(1);
      evidence.checks.push('HTTP/WS newly drawn BOOST, one draw and one action');
    } finally { await owner.close(); await other.close(); }
  });

  it('keeps TURN_END with its owner until a persisted excess-card selection completes', async () => {
    const initial = seed('s03-transport-discard', 7, 1);
    const owner = await watch('a', initial.gameId);
    const other = await watch('b', initial.gameId);
    try {
      const begun = await mutate('begin-eight-card-hand', 'beginManeuver', { gameId: initial.gameId, expectedSequenceNumber: 10 }, 10, [owner, other]);
      expect(begun.state.handZones.a.cards).toHaveLength(8);
      const completed = await mutate('await-end-turn-discard', 'maneuver', { gameId: initial.gameId,
        maneuverId: begun.state.metadata.pendingManeuver!.id, moves: [] }, 11, [owner, other]);
      expect(completed.state.phase).toBe(GamePhase.TURN_END);
      expect(completed.state.currentTurnPlayerId).toBe('a');
      expect(completed.updates[1].metadata.pendingHandDiscard).toMatchObject({ playerId: 'a', count: 1 });
      await states.invalidateStateCache(initial.gameId);
      const restored = await snapshot('discard-db-snapshot', 'a', initial.gameId);
      const otherSnapshot = await snapshot('discard-other-snapshot', 'b', initial.gameId);
      expect(otherSnapshot.metadata.pendingHandDiscard).toEqual(restored.metadata.pendingHandDiscard);
      expect(otherSnapshot.handZones.a.cards).toHaveLength(8);
      const input = { gameId: initial.gameId, pendingId: restored.metadata.pendingHandDiscard!.id, cardIds: ['h2'] };
      expect((await http('foreign-discard-rejected', 'b', 'discardToLimit', { input })).errors).toBeDefined();
      expect((await http('catalog-discard-rejected', 'a', 'discardToLimit', { input: { ...input, cardIds: ['definition'] } })).errors).toBeDefined();
      const discarded = await mutate('owner-selects-discard', 'discardToLimit', input, 12, [owner, other]);
      expect(discarded.state.handZones.a.cards).toHaveLength(7);
      expect(discarded.state.discardPiles.a.map(card => card.id)).toEqual(['h2']);
      expect(discarded.state.currentTurnPlayerId).toBe('b');
      expect(discarded.state.handZones.b.cards).toHaveLength(0);
      expect(discarded.state.decks.b.drawPile).toHaveLength(2);
      expect(discarded.state.metadata.pendingHandDiscard).toBeUndefined();
      expect((await http('discard-replay-rejected', 'a', 'discardToLimit', { input })).errors).toBeDefined();
      evidence.checks.push('HTTP/WS end-turn discard, DB reload, owner/exact-instance validation and replay rejection');
    } finally { await owner.close(); await other.close(); }
  });
});
