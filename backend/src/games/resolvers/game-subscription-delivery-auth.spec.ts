/** S08 security regression: subscription membership must be re-authorized at
 * DELIVERY time, not only at subscribe time.
 *
 * The @Subscription filter previously matched only gameId/eventType/since: a
 * player who subscribed and THEN left the lobby kept receiving every later
 * gameStateUpdated event (including state published after a replacement
 * joined and the game started). This spec boots the REAL Apollo wiring
 * (decorator metadata -> resolvers-explorer -> subscriptionWithFilter ->
 * filterFn.call(instance, payload, variables, context), exactly what the
 * graphql-ws server executes) and drives it with graphql-js subscribe() —
 * no websocket needed, but no re-implemented filter either. */
import 'reflect-metadata';
import { Test } from '@nestjs/testing';
import { Query, Resolver } from '@nestjs/graphql';
import { GraphQLModule, GraphQLSchemaHost } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { parse, subscribe } from 'graphql';
import { GameSubscriptionResolver } from './game-subscription.resolver';
import { GameSubscriptionService, GamePubSubEvent } from '../game-subscription.service';
import { GameStateService } from '../game-state.service';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';

/** Schema needs a Query root; the resolver under test only subscribes. */
@Resolver()
class PingResolver {
  @Query(() => String)
  ping(): string {
    return 'pong';
  }
}

/* eslint-disable @typescript-eslint/no-explicit-any */

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Push-queue async iterator standing in for the PubSub stream. */
class FakeUpstream implements AsyncIterableIterator<GamePubSubEvent> {
  private queue: GamePubSubEvent[] = [];
  private waiters: ((r: IteratorResult<GamePubSubEvent>) => void)[] = [];

  push(event: GamePubSubEvent): void {
    const waiter = this.waiters.shift();
    if (waiter) waiter({ done: false, value: event });
    else this.queue.push(event);
  }

  next(): Promise<IteratorResult<GamePubSubEvent>> {
    if (this.queue.length > 0) {
      return Promise.resolve({ done: false, value: this.queue.shift()! });
    }
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  async return(): Promise<IteratorResult<GamePubSubEvent>> {
    return { done: true, value: undefined };
  }

  [Symbol.asyncIterator](): AsyncIterableIterator<GamePubSubEvent> {
    return this;
  }
}

const stateAt = (sequenceNumber: number) =>
  ({
    sequenceNumber,
    phase: 'ACTION_MANEUVER',
    turnCount: 1,
    currentTurnPlayerId: 'u1',
    players: [],
    fighters: [],
    handZones: {},
    discardPiles: {},
    boardState: {},
    metadata: {},
  }) as any;

const eventAt = (sequenceNumber: number): GamePubSubEvent =>
  ({
    gameId: 'g1',
    sequenceNumber,
    timestamp: Date.now(),
    eventType: 'STATE_UPDATED',
    payload: stateAt(sequenceNumber),
  }) as any;

const SUB_DOC = parse(
  `subscription ($gameId: String!) {
     gameStateUpdated(gameId: $gameId) { gameId sequenceNumber phase }
   }`,
);

describe('gameStateUpdated delivery-time membership recheck (S08)', () => {
  let app: import('@nestjs/common').INestApplication;
  let upstream: FakeUpstream;
  let participant: boolean;
  let schema: import('graphql').GraphQLSchema;

  beforeAll(async () => {
    upstream = new FakeUpstream();
    participant = true;
    const moduleRef = await Test.createTestingModule({
      imports: [
        GraphQLModule.forRoot<ApolloDriverConfig>({
          driver: ApolloDriver,
          autoSchemaFile: true,
          csrfPrevention: false,
        }),
      ],
      providers: [
        GameSubscriptionResolver,
        PingResolver,
        { provide: GameSubscriptionService, useValue: { asyncIteratorForGame: () => upstream } },
        {
          provide: GameStateService,
          useValue: {
            loadState: async () => stateAt(5),
            isParticipant: async () => participant,
            filterPrivateData: (payload: any) => payload,
          },
        },
      ],
    })
      .overrideGuard(GqlAuthGuard)
      .useValue({
        canActivate: (context: any) => {
          const ctx = context.getArgByIndex(2);
          const req = ctx?.req ?? ctx;
          if (!req.user) req.user = { id: 'u1' };
          return true;
        },
      })
      .compile();
    app = moduleRef.createNestApplication();
    app.useLogger(false);
    await app.init();
    schema = app.get(GraphQLSchemaHost).schema;
  });

  afterAll(async () => {
    await app?.close();
  });

  async function openStream(): Promise<
    AsyncIterableIterator<{ data?: any; errors?: any[] }>
  > {
    const result = (await subscribe({
      schema,
      document: SUB_DOC,
      variableValues: { gameId: 'g1' },
      contextValue: { req: { user: { id: 'u1' } } },
    })) as any;
    // Nest's async-iterator util may expose iterall's $$asyncIterator instead
    // of the native symbol - duck-type instead of symbol-checking.
    if (typeof result?.next !== 'function') {
      const why = (result?.errors ?? []).map(
        (e: any) => `${e?.message ?? '?'} ${JSON.stringify(e?.extensions ?? {})}`,
      );
      throw new Error(`subscribe failed: ${why.join(' | ') || JSON.stringify(result)}`);
    }
    return result;
  }

  it('leaver receives nothing after leave, replacement/start events included', async () => {
    const stream = await openStream();

    // Barrier snapshot was earned while still a participant. graphql-js
    // subscribe() = createSourceEventStream: the iterator yields the raw
    // resolver payloads (the filter chain runs before them; per-event
    // resolve belongs to the server's execution pipeline, covered elsewhere).
    const barrier = await stream.next();
    expect(barrier.done).toBe(false);
    expect((barrier.value as any)?.data?.gameStateUpdated?.sequenceNumber).toBe(5);

    // Player leaves the lobby AFTER subscribing.
    participant = false;

    // Replacement joins and the game starts: fresh state is published...
    const pending = stream.next();
    upstream.push(eventAt(6)); // replacement joined / room state advanced
    upstream.push(eventAt(7)); // startGame state
    const leaked = await Promise.race([
      pending.then((r) => r),
      delay(400).then(() => 'NO_DELIVERY' as const),
    ]);
    expect(leaked).toBe('NO_DELIVERY');

    // Control: the stream itself is alive — restoring membership (e.g. the
    // same user re-joining) resumes delivery. This proves the leaver filter,
    // not a dead iterator, blocked the events above. The SAME pending next()
    // is awaited: calling next() on an async iterator with an unresolved
    // prior next() would race two upstream reads.
    participant = true;
    upstream.push(eventAt(8));
    const resumed = await Promise.race([
      pending,
      delay(1500).then(() => 'TIMEOUT' as const),
    ]);
    expect(resumed).not.toBe('TIMEOUT');
    expect((resumed as any).value?.data?.gameStateUpdated?.sequenceNumber).toBe(8);

    await stream.return!();
  });

  it('non-participant is rejected at subscribe time (subscribe gate intact)', async () => {
    participant = false;
    const result = (await subscribe({
      schema,
      document: SUB_DOC,
      variableValues: { gameId: 'g1' },
      contextValue: { req: { user: { id: 'u1' } } },
    })) as any;
    expect(typeof result?.next).not.toBe('function');
    expect(String(result?.errors?.[0]?.message)).toMatch(/participant/i);
    participant = true;
  });
});
