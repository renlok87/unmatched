/**
 * MS-AT-03 (MS-T-14): the public movement trail `metadata.lastMovement`
 * (docs/game-design/move-selection/04-technical-design.md §4.3, MS-R-47).
 *
 *  - executeManeuver writes it (several fighters, order, seq, BOOST, moves: []),
 *    the turn may pass in the same seq (MS-E-45), the next maneuver replaces
 *    it (MS-E-72), beginManeuver keeps it (MS-E-103);
 *  - a resolved MOVE effect writes the server's canonical path, PLACE writes
 *    kind PLACE with the target only; the golden fixtures of MS-T-02 pin both;
 *  - it survives saveState -> cache drop -> loadState (deserialize, key `lm`),
 *    a save without `lm` reads as "no trail" (MS-E-108);
 *  - the opponent's projection carries it and no hidden card id; the BOOST
 *    instance id is already public in the discard pile (MS-Q-05);
 *  - MS-Q-06: while a maneuver is open no other mutation of either player
 *    (and no bot step) can change the state.
 */
import type { GameState, LastMovement, Position } from '../models';
import { GamePhase } from '../models';
import { AdjacencyService } from '../engine/adjacency.service';
import { canonicalPath, computeReach } from '../movement/canonical-path';
import { AiDecisionService } from './ai-decision.service';
import { GameStateService } from '../../games/game-state.service';
import { GameSubscriptionService } from '../../games/game-subscription.service';
import { GameStatus } from '../../games/dto/create-game.dto';
import type { ManeuverDto } from '../../games/dto/gameplay.dto';
import type { RedisService } from '../../redis/redis.service';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import {
  MOVE_FIXTURE_SCHEMA,
  buildMoveFixtureState,
  commandMovesOf,
  evaluateFixtureDraft,
  fixtureActor,
  loadMoveFixtures,
  type MoveFixture,
} from '../../test/fixtures/move-fixture-state';

const engine = s03Engine();
const executor = engine.executor;

/** 5×3 grid: p1 hero (0,0) and sidekick (0,2), p2 hero (4,1); p1 holds three BOOST cards */
function fixture(name: string, over: Partial<MoveFixture> = {}): MoveFixture {
  return {
    schema: MOVE_FIXTURE_SCHEMA,
    name,
    expectSource: 'manual',
    board: { key: 'last-movement-grid', lattice: { width: 5, height: 3 } },
    fighters: [
      { id: 'hero', ownerId: 'p1', position: { x: 0, y: 0 }, type: 'HERO', movement: 2 },
      { id: 'side', ownerId: 'p1', position: { x: 0, y: 2 }, type: 'MINION', movement: 2 },
      { id: 'enemy', ownerId: 'p2', position: { x: 4, y: 1 }, type: 'HERO', movement: 2 },
    ],
    hand: [
      { id: 'b-4', boostValue: 4 },
      { id: 'b-2', boostValue: 2 },
      { id: 'b-none', boostValue: null },
    ],
    draft: { moves: [] },
    expect: { layer: 'executor', server: 'ok' },
    ...over,
  };
}

const xy = (x: number, y: number): Position => ({ x, y });
type Command = { fighterId: string; path: Position[] };

async function maneuver(
  state: GameState,
  moves: Command[],
  boostCardId?: string,
  userId = 'p1',
): Promise<GameState> {
  const maneuverId = state.metadata.pendingManeuver!.id;
  const r = await executor.executeManeuver(
    { gameId: state.gameId, maneuverId, moves, ...(boostCardId ? { boostCardId } : {}) } as ManeuverDto,
    { gameId: state.gameId, userId, currentState: state },
  );
  expect(r.error).toBeUndefined();
  expect(r.success).toBe(true);
  return r.gameState!;
}

async function resolve(state: GameState, fighterId: string, target: Position, userId = 'p1'): Promise<GameState> {
  const effectId = state.metadata.pendingEffects![0].id;
  const r = await executor.executeResolvePendingEffect(
    { gameId: state.gameId, effectId, fighterId, x: target.x, y: target.y },
    { gameId: state.gameId, userId, currentState: state },
  );
  expect(r.error).toBeUndefined();
  expect(r.success).toBe(true);
  return r.gameState!;
}

/** Wire form of a player's snapshot: filterPrivateData -> JSON (the GraphQL `state: String`) */
function wire(service: GameStateService, state: GameState, viewer: string) {
  return JSON.parse(JSON.stringify(service.filterPrivateData(state, viewer))) as GameState;
}

/** In-memory Game / GameState rows and Redis for GameStateService.saveState / loadState */
function fakeStorage() {
  let row: { state: unknown; sequenceNumber: number } | null = null;
  let version = 0;
  const cache = new Map<string, string>();
  const tx = {
    game: {
      updateMany: async ({ data }: { data: { version: number } }) => {
        version = data.version;
        return { count: 1 };
      },
    },
    gameState: {
      findUnique: async () => row,
      upsert: async (args: { create: { state: unknown; sequenceNumber: number } }) => {
        // the Json column stores plain JSON
        row = {
          state: JSON.parse(JSON.stringify(args.create.state)),
          sequenceNumber: args.create.sequenceNumber,
        };
        return row;
      },
    },
  };
  const prisma = {
    $transaction: async (cb: (t: typeof tx) => Promise<unknown>) => cb(tx),
    game: { findUnique: async () => ({ status: GameStatus.IN_PROGRESS, version }) },
    gameState: { findUnique: async () => row },
  };
  const redis = {
    setJsonex: async (key: string, _ttl: number, value: unknown) => {
      cache.set(key, JSON.stringify(value));
      return 'OK' as const;
    },
    getJson: async (key: string) => (cache.has(key) ? JSON.parse(cache.get(key)!) : null),
    del: async (key: string) => (cache.delete(key) ? 1 : 0),
  };
  return {
    service: new GameStateService(prisma as never, redis as never),
    stored: () => row!.state as { m: Record<string, unknown> },
    setStored: (state: unknown, sequenceNumber: number) => {
      row = { state, sequenceNumber };
      version = sequenceNumber;
    },
    cache,
  };
}

describe('MS-AT-03 lastMovement after a maneuver', () => {
  it('records every fighter in the order applied, with its start, the sent path, seq and BOOST', async () => {
    const before = buildMoveFixtureState(fixture('lm-two-fighters'));
    // the sidekick ends on the hero's start: legal only after the hero's move
    const after = await maneuver(
      before,
      [
        { fighterId: 'hero', path: [xy(1, 0)] },
        { fighterId: 'side', path: [xy(0, 1), xy(0, 0)] },
      ],
      'b-4',
    );
    expect(after.sequenceNumber).toBe(before.sequenceNumber + 1);
    const card = before.handZones.p1.cards.find((c) => c.id === 'b-4')!;
    expect(after.metadata.lastMovement).toEqual<LastMovement>({
      seq: after.sequenceNumber,
      playerId: 'p1',
      source: 'MANEUVER',
      sourceRef: before.metadata.pendingManeuver!.id,
      boost: { cardId: 'b-4', catalogId: card.cardId, name: card.name, value: 4 },
      moves: [
        { order: 0, fighterId: 'hero', kind: 'MOVE', from: xy(0, 0), path: [xy(1, 0)] },
        { order: 1, fighterId: 'side', kind: 'MOVE', from: xy(0, 2), path: [xy(0, 1), xy(0, 0)] },
      ],
    });
    // the trail matches the positions of the snapshot it belongs to
    for (const mv of after.metadata.lastMovement!.moves) {
      expect(after.fighters.find((f) => f.id === mv.fighterId)!.position).toEqual(mv.path[mv.path.length - 1]);
    }
    expect(before.metadata.lastMovement).toBeUndefined();
  });

  it('a maneuver without movement records moves: [] (with and without BOOST)', async () => {
    const boosted = await maneuver(buildMoveFixtureState(fixture('lm-boost-only')), [], 'b-2');
    expect(boosted.metadata.lastMovement).toMatchObject({
      seq: boosted.sequenceNumber,
      source: 'MANEUVER',
      boost: { cardId: 'b-2', value: 2 },
      moves: [],
    });
    const plain = await maneuver(buildMoveFixtureState(fixture('lm-plain')), []);
    expect(plain.metadata.lastMovement).toMatchObject({ seq: plain.sequenceNumber, boost: null, moves: [] });
  });

  it('a BOOST card without a printed BOOST is recorded with value null', async () => {
    const before = buildMoveFixtureState(fixture('lm-boost-null'));
    const card = before.handZones.p1.cards.find((c) => c.id === 'b-none')!;
    const after = await maneuver(before, [{ fighterId: 'hero', path: [xy(1, 0)] }], 'b-none');
    expect(after.metadata.lastMovement!.boost).toEqual({ cardId: 'b-none', catalogId: card.cardId, name: card.name, value: null });
  });

  it('the last action passes the turn in the same seq; the trail keeps that seq (MS-E-45)', async () => {
    const base = buildMoveFixtureState(fixture('lm-last-action'));
    const before: GameState = { ...base, metadata: { ...base.metadata, actionsRemaining: 0 } };
    const after = await maneuver(before, [{ fighterId: 'hero', path: [xy(1, 0), xy(2, 0)] }]);
    expect(after.currentTurnPlayerId).toBe('p2');
    expect(after.sequenceNumber).toBe(before.sequenceNumber + 1);
    expect(after.metadata.lastMovement).toMatchObject({ seq: after.sequenceNumber, playerId: 'p1' });
  });

  it('beginManeuver keeps the trail (MS-E-103); the next maneuver replaces it (MS-E-72)', async () => {
    const first = await maneuver(buildMoveFixtureState(fixture('lm-two-maneuvers')), [
      { fighterId: 'hero', path: [xy(1, 0)] },
    ]);
    const trail1 = first.metadata.lastMovement!;

    const begun = await executor.executeBeginManeuver(
      { gameId: first.gameId, expectedSequenceNumber: first.sequenceNumber },
      { gameId: first.gameId, userId: 'p1', currentState: first },
    );
    expect(begun.success).toBe(true);
    const open = begun.gameState!;
    expect(open.sequenceNumber).toBe(first.sequenceNumber + 1);
    expect(open.metadata.lastMovement).toEqual(trail1); // older seq: the client does not animate it again

    const second = await maneuver(open, [{ fighterId: 'hero', path: [xy(2, 0)] }]);
    expect(second.currentTurnPlayerId).toBe('p2'); // two actions spent
    expect(second.metadata.lastMovement).toEqual<LastMovement>({
      seq: second.sequenceNumber,
      playerId: 'p1',
      source: 'MANEUVER',
      sourceRef: open.metadata.pendingManeuver!.id,
      boost: null,
      moves: [{ order: 0, fighterId: 'hero', kind: 'MOVE', from: xy(1, 0), path: [xy(2, 0)] }],
    });
    expect(second.metadata.lastMovement!.sourceRef).not.toBe(trail1.sourceRef);
  });
});

describe('MS-AT-03 lastMovement after a MOVE / PLACE effect', () => {
  const pendingFx = (name: string, pending: MoveFixture['pending']) =>
    fixture(name, { draft: undefined, pending, expect: { layer: 'resolvePending', server: 'ok' } });

  it('MOVE writes the canonical path of the server, not just any shortest path', async () => {
    const before = buildMoveFixtureState(
      pendingFx('lm-effect-move', { type: 'MOVE', fighterId: 'hero', ownerId: 'p1', value: 2, target: xy(1, 1) }),
    );
    const after = await resolve(before, 'hero', xy(1, 1));
    // two shortest paths: via (1,0) and via (0,1); K = (y, x) picks (1,0)
    const expected = canonicalPath(computeReach(before, 'hero', 2), before, xy(1, 1));
    expect(expected).toEqual([xy(1, 0), xy(1, 1)]);
    expect(after.sequenceNumber).toBe(before.sequenceNumber + 1);
    expect(after.metadata.lastMovement).toEqual<LastMovement>({
      seq: after.sequenceNumber,
      playerId: 'p1',
      source: 'EFFECT',
      sourceRef: before.metadata.pendingEffects![0].id,
      boost: null,
      moves: [{ order: 0, fighterId: 'hero', kind: 'MOVE', from: xy(0, 0), path: expected! }],
    });
  });

  it('a MOVE that drains a deferred turn end keeps the final seq (the turn passes in the same seq)', async () => {
    const base = buildMoveFixtureState(
      pendingFx('lm-effect-deferred-turn', { type: 'MOVE', fighterId: 'hero', ownerId: 'p1', value: 1, target: xy(1, 0) }),
    );
    const before: GameState = {
      ...base,
      metadata: { ...base.metadata, actionsRemaining: 0, pendingTurnEnd: { playerId: 'p1', endEffectsApplied: true } },
    };
    const after = await resolve(before, 'hero', xy(1, 0));
    expect(after.currentTurnPlayerId).toBe('p2');
    expect(after.metadata.pendingTurnEnd).toBeUndefined();
    expect(after.sequenceNumber).toBe(before.sequenceNumber + 1);
    expect(after.metadata.lastMovement).toMatchObject({
      seq: after.sequenceNumber,
      playerId: 'p1',
      moves: [{ fighterId: 'hero', kind: 'MOVE', from: xy(0, 0), path: [xy(1, 0)] }],
    });
  });

  it('MOVE resolved as "stay" records moves: []', async () => {
    const before = buildMoveFixtureState(
      pendingFx('lm-effect-stay', { type: 'MOVE', fighterId: 'hero', ownerId: 'p1', value: 2, target: xy(0, 0) }),
    );
    const after = await resolve(before, 'hero', xy(0, 0));
    expect(after.metadata.lastMovement).toMatchObject({ seq: after.sequenceNumber, source: 'EFFECT', moves: [] });
  });

  it('PLACE records kind PLACE with the target as the only path cell', async () => {
    const before = buildMoveFixtureState(
      pendingFx('lm-effect-place', { type: 'PLACE', fighterId: 'side', ownerId: 'p1', target: xy(3, 2) }),
    );
    const after = await resolve(before, 'side', xy(3, 2));
    expect(after.metadata.lastMovement).toMatchObject({
      seq: after.sequenceNumber,
      source: 'EFFECT',
      boost: null,
      moves: [{ order: 0, fighterId: 'side', kind: 'PLACE', from: xy(0, 2), path: [xy(3, 2)] }],
    });
  });
});

describe('MS-AT-03 trail on the golden fixtures of MS-T-02', () => {
  const accepted = loadMoveFixtures().filter(
    (fx) => fx.expect.server === 'ok' && (fx.expect.layer === 'executor' || fx.expect.layer === 'resolvePending'),
  );

  it('covers accepted maneuvers and effects on grid and topology boards', () => {
    expect(accepted.filter((fx) => fx.expect.layer === 'executor').length).toBeGreaterThanOrEqual(30);
    expect(accepted.filter((fx) => fx.pending?.type === 'MOVE').length).toBeGreaterThanOrEqual(5);
    expect(accepted.some((fx) => fx.pending?.type === 'PLACE')).toBe(true);
    const boards = new Set(accepted.map((fx) => (fx.board.lattice ? 'grid' : fx.board.key)));
    expect([...boards].sort()).toEqual(['grid', 'marmoreal', 'sarpedon']);
  });

  it.each(accepted.map((fx) => [fx.name, fx] as const))('%s', async (_name, fx) => {
    const state = buildMoveFixtureState(fx);
    const actor = fixtureActor(fx);
    const startOf = new Map(state.fighters.map((f) => [f.id, xy(f.position.x, f.position.y)]));
    let after: GameState;
    let expectedMoves: LastMovement['moves'];
    if (fx.expect.layer === 'executor') {
      const moves = commandMovesOf(fx, evaluateFixtureDraft(fx, state));
      after = await maneuver(state, moves, fx.draft!.boostCardId ?? undefined, actor);
      expectedMoves = moves.map((m, order) => {
        const from = startOf.get(m.fighterId)!;
        startOf.set(m.fighterId, m.path[m.path.length - 1]);
        return { order, fighterId: m.fighterId, kind: 'MOVE' as const, from, path: m.path };
      });
      expect(after.metadata.lastMovement!.boost?.cardId ?? null).toBe(fx.draft!.boostCardId ?? null);
    } else {
      const p = fx.pending!;
      after = await resolve(state, p.fighterId, p.target, actor);
      const from = startOf.get(p.fighterId)!;
      const stays = from.x === p.target.x && from.y === p.target.y;
      const path =
        p.type === 'MOVE'
          ? fx.expect.paths![p.fighterId]!.map(([x, y]) => xy(x, y)) // golden canonical path
          : stays ? [] : [xy(p.target.x, p.target.y)];
      expectedMoves = path.length ? [{ order: 0, fighterId: p.fighterId, kind: p.type, from, path }] : [];
    }
    expect(after.metadata.lastMovement).toMatchObject({
      seq: after.sequenceNumber,
      playerId: actor,
      source: fx.expect.layer === 'executor' ? 'MANEUVER' : 'EFFECT',
      moves: expectedMoves,
    });
  });
});

describe('MS-AT-03 storage and transport (key lm)', () => {
  async function trailState(): Promise<GameState> {
    return maneuver(
      buildMoveFixtureState(fixture('lm-storage')),
      [
        { fighterId: 'hero', path: [xy(1, 0), xy(2, 0)] },
        { fighterId: 'side', path: [xy(1, 2)] },
      ],
      'b-4',
    );
  }

  it('saveState -> cache dropped -> loadState (deserialize) keeps the trail; the cache path too', async () => {
    const state = await trailState();
    const storage = fakeStorage();
    await storage.service.saveState(state.gameId, state);
    expect(storage.stored().m.lm).toEqual(state.metadata.lastMovement);

    await storage.service.invalidateStateCache(state.gameId);
    expect(storage.cache.size).toBe(0);
    const fromDb = await storage.service.loadState(state.gameId);
    expect(fromDb.metadata.lastMovement).toEqual(state.metadata.lastMovement);

    // loadState re-cached the DB state: the Redis path returns the same trail
    const fromCache = await storage.service.getCachedState(state.gameId);
    expect(fromCache!.metadata.lastMovement).toEqual(state.metadata.lastMovement);
  });

  it('a save without lm (before MS-T-14) reads as "no trail" and the game goes on (MS-E-108)', async () => {
    const state = await trailState();
    const storage = fakeStorage();
    const legacyDoc = JSON.parse(JSON.stringify(storage.service.serialize(state)));
    delete legacyDoc.m.lm;
    storage.setStored(legacyDoc, state.sequenceNumber);

    const legacy = await storage.service.loadState(state.gameId);
    expect(legacy.metadata.lastMovement).toBeUndefined();
    // everything else reads exactly as the same document with lm
    const modern = storage.service.deserialize(JSON.parse(JSON.stringify(storage.service.serialize(state))));
    expect(modern.metadata.lastMovement).toEqual(state.metadata.lastMovement);
    expect(legacy).toEqual({ ...modern, metadata: { ...modern.metadata, lastMovement: undefined } });

    // the wire snapshot of an old save has no lastMovement key at all (unchanged
    // for the S09/S10 parsers); a new one only adds metadata.lastMovement
    const oldWire = wire(storage.service, legacy, 'p2');
    const newWire = wire(storage.service, state, 'p2');
    expect(Object.prototype.hasOwnProperty.call(oldWire.metadata, 'lastMovement')).toBe(false);
    expect(Object.keys(newWire).sort()).toEqual(Object.keys(oldWire).sort());
    expect(Object.keys(newWire.metadata).filter((k) => !(k in oldWire.metadata))).toEqual(['lastMovement']);

    // a serialized legacy state round-trips without inventing the key
    expect(Object.prototype.hasOwnProperty.call(
      JSON.parse(JSON.stringify(storage.service.serialize(legacy))).m, 'lm')).toBe(false);
  });

  it('the opponent projection carries the trail and no hidden card id; the BOOST id is in the public discard (MS-Q-05)', async () => {
    const state = await trailState();
    const service = fakeStorage().service;
    const view = wire(service, state, 'p2');
    expect(view.metadata.lastMovement).toEqual(state.metadata.lastMovement);

    // hidden from p2: p1's hand and both decks (order and identity)
    const hidden = [
      ...state.handZones.p1.cards.map((c) => c.id),
      ...Object.values(state.decks).flatMap((d) => [...d.cards, ...d.drawPile].map((c) => c.id)),
    ];
    expect(hidden.length).toBeGreaterThan(0);
    const text = JSON.stringify(view);
    for (const id of hidden) expect(text).not.toContain(`"${id}"`);

    // MS-Q-05: the BOOST instance id is public anyway — the discard pile shows it
    const boostId = view.metadata.lastMovement!.boost!.cardId;
    expect(view.discardPiles.p1.map((c) => c.id)).toContain(boostId);
    expect(view.handZones.p1.cards.map((c) => c.id)).not.toContain(boostId);
  });

  it('the subscription event keeps the trail for the per-player projection', async () => {
    const state = await trailState();
    const publish = jest.fn().mockResolvedValue(1);
    const subscriptions = new GameSubscriptionService({ publish } as unknown as RedisService);
    await subscriptions.publishGameUpdate(state.gameId, 'MANEUVER', state);
    const event = JSON.parse(publish.mock.calls[0][1]);
    expect(event.gameState.metadata.lastMovement).toEqual(state.metadata.lastMovement);
  });
});

describe('MS-Q-06: nothing but the maneuver itself changes the state while it is open', () => {
  it('every other mutation of either player is refused; the bot waits', async () => {
    const state = buildMoveFixtureState(fixture('lm-open-maneuver'));
    expect(state.metadata.pendingManeuver).toBeDefined();
    const g = state.gameId;
    const snapshot = JSON.stringify(state);
    // the refusal must come from the open maneuver, not from a malformed input
    const GUARD = 'Resolve the pending resource choice first';
    type Result = { success: boolean; error?: string };
    const calls: Array<[string, (userId: string) => string, (userId: string) => Promise<Result>]> = [
      ['beginManeuver', (u) => (u === 'p1' ? 'Cannot begin maneuver in current state' : 'Not your turn'),
        (u) => executor.executeBeginManeuver({ gameId: g, expectedSequenceNumber: state.sequenceNumber }, ctx(u))],
      ['attack', () => GUARD,
        (u) => executor.executeAttack({ gameId: g, attackerId: 'hero', targetId: 'enemy', cardId: 'b-4' } as never, ctx(u))],
      ['playDefense', () => GUARD, (u) => executor.executePlayDefense({ gameId: g, cardId: 'b-4' } as never, ctx(u))],
      ['playScheme', () => GUARD, (u) => executor.executePlayScheme({ gameId: g, cardId: 'b-4' } as never, ctx(u))],
      ['resolveCombat', () => GUARD, (u) => executor.executeResolveCombat({ gameId: g } as never, ctx(u))],
      ['endTurn', () => GUARD, (u) => executor.executeEndTurn({ gameId: g } as never, ctx(u))],
      ['toggleDoor', () => GUARD, (u) => executor.executeToggleDoor({ gameId: g, x: 1, y: 1 } as never, ctx(u))],
      ['setStance', () => GUARD, (u) => executor.executeSetStance({ gameId: g, stanceId: 'any' }, ctx(u))],
      ['resolvePendingEffect', () => GUARD,
        (u) => executor.executeResolvePendingEffect({ gameId: g, effectId: 'any' } as never, ctx(u))],
      ['declinePendingEffect', () => GUARD,
        (u) => executor.executeDeclinePendingEffect({ gameId: g, effectId: 'any' }, ctx(u))],
      // these three never apply here whatever the input
      ['pass', () => 'Passing is not a legal action; use maneuver even without movement',
        (u) => executor.executePass({ gameId: g } as never, ctx(u))],
      ['moveFighter', () => 'Use beginManeuver and maneuver to move fighters',
        (u) => executor.executeMoveFighter({ gameId: g, fighterId: 'hero' } as never, ctx(u))],
      ['discardToLimit', () => 'No matching discard choice for this player',
        (u) => executor.executeDiscardToLimit({ gameId: g, pendingId: 'any', cardIds: [] }, ctx(u))],
    ];
    function ctx(userId: string) {
      return { gameId: g, userId, currentState: state };
    }
    for (const userId of ['p1', 'p2']) {
      for (const [name, expected, call] of calls) {
        const r = await call(userId);
        expect({ name, userId, success: r.success, error: r.error }).toEqual({
          name,
          userId,
          success: false,
          error: expected(userId),
        });
      }
    }
    // the opponent cannot complete someone else's maneuver either
    const foreign = await executor.executeManeuver(
      { gameId: g, maneuverId: state.metadata.pendingManeuver!.id, moves: [] } as ManeuverDto,
      ctx('p2'),
    );
    expect(foreign.success).toBe(false);
    // a VS_AI bot (p2) takes no step on a foreign open maneuver
    expect(new AiDecisionService(new AdjacencyService()).decide(state, 'p2')).toBeNull();
    expect(JSON.stringify(state)).toBe(snapshot);
    expect(state.phase).toBe(GamePhase.ACTION_MANEUVER);
  });
});
