/** GD-027/ACC-011: connection barrier — focused live-stream regression.
 *
 * withSnapshotBarrier registers the PubSub subscription (upstream.next())
 * BEFORE building the HTTP snapshot; when the barrier snapshot is returned,
 * that pending read MUST still be handed to the client later. The old code
 * dropped the resolved promise after returning the barrier, so the next
 * next() called upstream.next() AGAIN — the one event published between
 * subscribe and snapshot was swallowed and the iterator stalled until a
 * SECOND mutation arrived. These tests pin exactly-one-event delivery. */
import 'reflect-metadata';
import { NotFoundException } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { GameSubscriptionResolver } from './game-subscription.resolver';
import { GameSubscriptionService, GamePubSubEvent } from '../game-subscription.service';
import { GameStateService } from '../game-state.service';

/* eslint-disable @typescript-eslint/no-explicit-any */

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Push-queue async iterator standing in for the PubSub stream. */
class FakeUpstream implements AsyncIterableIterator<GamePubSubEvent> {
  private queue: GamePubSubEvent[] = [];
  private waiters: ((r: IteratorResult<GamePubSubEvent>) => void)[] = [];
  public nextCalls = 0;

  push(event: GamePubSubEvent): void {
    const waiter = this.waiters.shift();
    if (waiter) waiter({ done: false, value: event });
    else this.queue.push(event);
  }

  next(): Promise<IteratorResult<GamePubSubEvent>> {
    this.nextCalls += 1;
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
    phase: 'MANEUVER',
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

async function buildResolver(upstream: FakeUpstream, loadStateImpl: () => Promise<any>) {
  const module = await Test.createTestingModule({
    providers: [
      GameSubscriptionResolver,
      {
        provide: GameSubscriptionService,
        useValue: { asyncIteratorForGame: () => upstream },
      },
      {
        provide: GameStateService,
        useValue: {
          loadState: loadStateImpl,
          isParticipant: async () => true,
          filterPrivateData: (payload: any) => payload,
        },
      },
    ],
  }).compile();
  return module.get(GameSubscriptionResolver);
}

describe('gameStateUpdated connection barrier (GD-027)', () => {
  it('delivers the ONE event published while the barrier snapshot was loading', async () => {
    const upstream = new FakeUpstream();
    let loadCount = 0;
    const resolver = await buildResolver(upstream, async () => {
      loadCount += 1;
      await delay(40); // event lands while the snapshot is in flight
      return stateAt(5);
    });

    const stream = await resolver.gameStateUpdated('g1', 0, undefined, { req: { user: { id: 'u1' } } } as any);

    const firstPromise = stream.next();
    await delay(10); // first upstream.next() registered, loadState started
    upstream.push(eventAt(6)); // the event that used to be swallowed

    const barrier = await firstPromise;
    expect(barrier.done).toBe(false);
    expect(barrier.value.sequenceNumber).toBe(5); // barrier snapshot first
    expect(upstream.nextCalls).toBe(1); // no second registration yet

    // The live event must arrive on the NEXT next() without any further
    // publication — the pending read from before the barrier is consumed.
    const live = await Promise.race([
      stream.next(),
      delay(1500).then(() => 'TIMEOUT' as const),
    ]);
    expect(live).not.toBe('TIMEOUT');
    expect((live as IteratorResult<GamePubSubEvent>).value.sequenceNumber).toBe(6);

    await stream.return!();
  });

  it('delivers an event published after the barrier was returned (pending read retained)', async () => {
    const upstream = new FakeUpstream();
    const resolver = await buildResolver(upstream, async () => stateAt(5));

    const stream = await resolver.gameStateUpdated('g1', 0, undefined, { req: { user: { id: 'u1' } } } as any);

    const barrier = await stream.next();
    expect(barrier.value?.sequenceNumber).toBe(5);

    upstream.push(eventAt(7)); // arrives after the barrier value, before next()

    const live = await Promise.race([
      stream.next(),
      delay(1500).then(() => 'TIMEOUT' as const),
    ]);
    expect(live).not.toBe('TIMEOUT');
    expect((live as IteratorResult<GamePubSubEvent>).value.sequenceNumber).toBe(7);
    expect(upstream.nextCalls).toBe(1); // served from the retained first read

    await stream.return!();
  });

  it('lobby phase (no state yet) passes live events straight through', async () => {
    const upstream = new FakeUpstream();
    const resolver = await buildResolver(upstream, async () => {
      throw new NotFoundException('no state');
    });

    const stream = await resolver.gameStateUpdated('g1', 0, undefined, { req: { user: { id: 'u1' } } } as any);

    const pending = stream.next();
    upstream.push(eventAt(1));
    const first = await pending;
    expect(first.value?.sequenceNumber).toBe(1);

    upstream.push(eventAt(2));
    const second = await stream.next();
    expect(second.value?.sequenceNumber).toBe(2);

    await stream.return!();
  });
});
