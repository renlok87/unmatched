/** GD-018: real localhost HTTP GraphQL + graphql-ws pending-choice chain.
 * Production resolvers, executor, serializer, subscription filtering; seeded
 * two-choice queue (mandatory MOVE + optional MOVE) with a persisted deferred
 * turn transfer. Synthetic identities/JSON storage/local lock — not a deployed
 * Postgres/Redis/JWT or UE test. */
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
import { GqlThrottlerGuard } from '../guards/gql-throttler.guard';
import { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { GameState } from '../../game-engine/models';
import { s03Fixture, s03Engine } from '../../test/fixtures/s03-engine.fixture';

const WebSocket = require('ws');
const json = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const fields = 'state sequenceNumber phase currentTurnPlayerId turnCount';
const operations = {
  attack: `mutation Attack($input: AttackDto!) { attack(input: $input) { ${fields} } }`,
  endTurn: `mutation End($input: EndTurnDto!) { endTurn(input: $input) { ${fields} } }`,
  resolvePendingEffect: `mutation Resolve($input: ResolvePendingEffectDto!) { resolvePendingEffect(input: $input) { ${fields} } }`,
  declinePendingEffect: `mutation Decline($input: DeclinePendingEffectDto!) { declinePendingEffect(input: $input) { ${fields} } }`,
  gameState: `query Snapshot($gameId: String!) { gameState(gameId: $gameId) { ${fields} } }`,
};
const subscriptionQuery = `subscription Updates($gameId: String!, $since: Float) {
  gameStateUpdated(gameId: $gameId, since: $since) {
    gameId sequenceNumber phase currentTurnPlayerId turnCount metadata
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

describe('S04 real HTTP/WS pending-choice chain', () => {
  let app: INestApplication;
  let url: string;
  let states: GameStateService;
  let subscriptions: GameSubscriptionService;
  const rows = new Map<string, any>();
  const games = new Map<string, { status: string; version: number }>();
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
    const prisma = {
      gameState: {
        findUnique: async ({ where }: any) => rows.has(where.gameId) ? json(rows.get(where.gameId)) : null,
        upsert: async ({ where, create, update }: any) => {
          const row = json(rows.has(where.gameId) ? { ...rows.get(where.gameId), ...update } : create);
          rows.set(where.gameId, row);
          return row;
        },
      },
      game: {
        findUnique: async ({ where }: any) => games.get(where.id) ?? null,
        updateMany: async ({ where, data }: any) => {
          const game = games.get(where.id);
          if (!game || (where.status && !(typeof where.status === 'string'
            ? game.status === where.status : where.status.in?.includes(game.status)))) return { count: 0 };
          games.set(where.id, { ...game, ...data });
          return { count: 1 };
        },
        update: async () => ({}),
      },
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
    } })
      // Harness-only: ThrottlerModule is absent from this fixture module, so the
      // resolver-level GqlThrottlerGuard would fail on missing THROTTLER:MODULE_OPTIONS.
      .overrideGuard(GqlThrottlerGuard).useValue({ canActivate: () => true })
      .compile();
    app = module.createNestApplication();
    app.useLogger(false);
    app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
    states = app.get(GameStateService);
    subscriptions = app.get(GameSubscriptionService);
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
    if (process.env.S04_PENDING_REPORT && evidence.checks.length === 1) {
      writeFileSync(process.env.S04_PENDING_REPORT, JSON.stringify({
        scope: 'Real localhost HTTP GraphQL and graphql-ws; production action resolvers/executor/serializer/subscriptions; seeded sequential pending queue with deferred turn transfer; synthetic auth, in-memory JSON database/cache, local lock, no AI/UE.',
        ...evidence,
      }, null, 2) + '\n');
    }
  });

  function seed(gameId: string): GameState {
    const base = s03Fixture(0, 0);
    const state = { ...base, gameId,
      metadata: { ...base.metadata,
        pendingEffects: [
          { id: 'pe1', type: 'MOVE' as const, playerId: 'a', value: 2,
            optional: false, text: 'Move up to 2 spaces' },
          { id: 'pe2', type: 'MOVE' as const, playerId: 'a', value: 1,
            optional: true, text: 'You may move 1 space' },
        ],
        pendingTurnEnd: { playerId: 'a', endEffectsApplied: false },
      } };
    rows.set(gameId, { gameId, sequenceNumber: state.sequenceNumber, state: json(states.serialize(state)) });
    games.set(gameId, { status: 'IN_PROGRESS', version: state.sequenceNumber });
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
        return { ...state, metadata: JSON.parse(state.metadata) };
      },
      close: async () => { stop(); await client.dispose(); clients.delete(client); },
    };
  }

  it('drains the seeded chain over HTTP/WS with strict order and one transfer', async () => {
    const gameId = 's04-pending-transport';
    const initial = seed(gameId);
    const owner = await watch('a', gameId);
    const other = await watch('b', gameId);
    try {
      const input = { gameId };
      // Gates: no second action, no turn end, while the queue is open.
      const attack = await http('attack-gated', 'a', 'attack', { input: {
        ...input, attackerId: 'a', targetId: 'b', cardId: 'none' } });
      expect(attack.errors).toBeDefined();
      const end = await http('end-gated', 'a', 'endTurn', { input });
      expect(end.errors).toBeDefined();
      // Strict order + ownership + optional-only decline.
      const tailFirst = await http('tail-first', 'a', 'resolvePendingEffect', { input: {
        ...input, effectId: 'pe2', fighterId: 'a', x: 1, y: 0 } });
      expect(tailFirst.errors).toBeDefined();
      const foreign = await http('foreign-head', 'b', 'resolvePendingEffect', { input: {
        ...input, effectId: 'pe1', fighterId: 'b', x: 6, y: 0 } });
      expect(foreign.errors).toBeDefined();
      const mandatoryDecline = await http('mandatory-decline', 'a', 'declinePendingEffect', { input: {
        ...input, effectId: 'pe1' } });
      expect(mandatoryDecline.errors).toBeDefined();

      const resolved = await http('resolve-head', 'a', 'resolvePendingEffect', { input: {
        ...input, effectId: 'pe1', fighterId: 'a', x: 2, y: 0 } });
      expect(resolved.errors).toBeUndefined();
      const resolvedState = JSON.parse(resolved.data.resolvePendingEffect.state) as GameState;
      expect(resolvedState.sequenceNumber).toBe(11);
      expect(resolvedState.fighters.find(f => f.id === 'a')!.position).toEqual({ x: 2, y: 0 });
      expect(resolvedState.currentTurnPlayerId).toBe('a'); // очередь не пуста — передачи нет
      const updates1 = await Promise.all([owner.next(), other.next()]);
      for (const update of updates1) expect(update.sequenceNumber).toBe(11);

      // Cache-evict + reload mid-chain restores the queue and the deferral.
      await states.invalidateStateCache(gameId);
      const restored = await snapshot('db-snapshot-mid-chain', 'a', gameId);
      expect(restored.metadata.pendingEffects!.map((p: any) => [p.id, p.optional]))
        .toEqual([['pe2', true]]);
      expect(restored.metadata.pendingTurnEnd).toEqual({ playerId: 'a', endEffectsApplied: false });

      const declined = await http('decline-optional', 'a', 'declinePendingEffect', { input: {
        ...input, effectId: 'pe2' } });
      expect(declined.errors).toBeUndefined();
      const finalState = JSON.parse(declined.data.declinePendingEffect.state) as GameState;
      expect(finalState.sequenceNumber).toBe(12);
      expect(finalState.currentTurnPlayerId).toBe('b');
      expect(finalState.metadata.actionsRemaining).toBe(2);
      expect(finalState.metadata.pendingTurnEnd).toBeUndefined();
      expect(finalState.metadata.pendingEffects ?? []).toHaveLength(0);
      const updates2 = await Promise.all([owner.next(), other.next()]);
      for (const update of updates2) expect(update.sequenceNumber).toBe(12);

      const replay = await http('decline-replay', 'a', 'declinePendingEffect', { input: {
        ...input, effectId: 'pe2' } });
      expect(replay.errors).toBeDefined();
      expect((await snapshot('after-replay', 'a', gameId)).sequenceNumber).toBe(12);
      expect(initial.sequenceNumber).toBe(10);
      evidence.checks.push('HTTP/WS sequential chain: gates, head/owner/optional-only rules, mid-chain reload, single deferred transfer, replay rejection');
    } finally { await owner.close(); await other.close(); }
  });
});
