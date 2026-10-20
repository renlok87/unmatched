/**
 * S09 → DET-3 self-play fuzz (docs/research/de-reverse-2026-10-20/VERDICT.md
 * §3 P1.3). Origin: capture-pending-fixtures saw 'A Momentary Glance ::1'
 * twice in one hand (2026-09-27); the S09 harness checked card instance
 * invariants after every mutation of 60 seeded scripted duels on Cobble City.
 *
 * Now: random legal self-play (test/selfplay/selfplay.ts) on the real maps,
 * Marmoreal and Sarpedon, Medusa and King Arthur with their production
 * abilities, the game RNG seeded per game. After every accepted command the
 * harness checks every invariant (cards, HP, seq, defeated hero ⇒ GAME_OVER,
 * winner, round-trip, projections, no input mutation), probes an out-of-turn
 * command and fails on a stalled game; after GAME_OVER nothing is accepted.
 * Every game then replays from its start snapshot and command journal with a
 * fresh executor, hash for hash.
 *
 * CI runs SELFPLAY_SEEDS games (default 24). Long run, opt-in:
 *   SELFPLAY_SEEDS=1000 npx jest src/games/services/s09-card-instance-dup.spec.ts
 * A failing case prints its seed; the same seed replays the same game.
 */
import { GameInitializationService } from './game-initialization.service';
import { GameState, GameStateService } from '../game-state.service';
import { GamePhase } from '../../game-engine/models';
import { marmorealBoardRow } from '../../test/fixtures/real-board';
import {
  replaySelfPlay,
  runSelfPlay,
  type SelfPlayBoard,
  type SelfPlayHero,
  type SelfPlayOptions,
} from '../../test/selfplay/selfplay';
import { stateHash } from '../replay/replay';

const SEEDS = Math.max(1, Number(process.env.SELFPLAY_SEEDS ?? 24));
const PAIRS: ReadonlyArray<readonly [SelfPlayHero, SelfPlayHero]> = [
  ['medusa', 'arthur'], ['arthur', 'medusa'], ['medusa', 'medusa'], ['arthur', 'arthur'],
];
const cases: SelfPlayOptions[] = Array.from({ length: SEEDS }, (_, i) => ({
  seed: 9000 + i,
  board: (i % 2 ? 'sarpedon' : 'marmoreal') as SelfPlayBoard,
  heroes: PAIRS[Math.floor(i / 2) % PAIRS.length],
  first: (i % 3 ? 'u1' : 'u2') as 'u1' | 'u2',
}));

const coverage: Record<string, { accepted: number; rejected: number }> = {};
let finished = 0;
let played = 0;

describe('DET-3: self-play fuzz on Marmoreal and Sarpedon with invariants after every command', () => {
  it.each(cases)(
    'seed $seed $board $heroes first=$first: invariants hold, the journal replays hash for hash',
    async (opts) => {
      const game = await runSelfPlay(opts);
      played++;
      if (game.finished) finished++;
      for (const [label, row] of Object.entries(game.coverage)) {
        const total = (coverage[label] ??= { accepted: 0, rejected: 0 });
        total.accepted += row.accepted;
        total.rejected += row.rejected;
      }
      expect(game.journal.length).toBeGreaterThan(0);

      const replay = await replaySelfPlay(game);
      expect(replay.divergence).toBeUndefined();
      expect(replay.applied).toBe(game.journal.length);
      expect(stateHash(replay.state)).toBe(game.journal[game.journal.length - 1].hash);
      expect(replay.state.phase).toBe(game.state.phase);
    },
    120_000,
  );

  it('the random policy reaches the branches the AI policy never plays, and games end', () => {
    expect(played).toBe(cases.length);
    const accepted = (prefix: string) =>
      Object.entries(coverage).filter(([l]) => l.startsWith(prefix)).reduce((n, [, r]) => n + r.accepted, 0);
    const attempted = (prefix: string) =>
      Object.entries(coverage).filter(([l]) => l.startsWith(prefix)).reduce((n, [, r]) => n + r.accepted + r.rejected, 0);
    // schemes and system timeouts are played for real
    expect(accepted('scheme')).toBeGreaterThan(0);
    expect(accepted('resolve:system')).toBeGreaterThan(0);
    expect(accepted('fallback:')).toBeGreaterThan(0);
    expect(accepted('maneuver:boost')).toBeGreaterThan(0);
    // stances and doors are tried: Medusa and Arthur have no stance and the
    // real maps have no door, so every such command must be rejected
    expect(attempted('stance')).toBeGreaterThan(0);
    expect(accepted('stance')).toBe(0);
    expect(attempted('door')).toBeGreaterThan(0);
    expect(accepted('door')).toBe(0);
    expect(accepted('pass')).toBe(0);
    // most random games reach GAME_OVER within the command cap
    expect(finished / played).toBeGreaterThanOrEqual(0.8);
    if (process.env.SELFPLAY_REPORT) console.log(JSON.stringify({ played, finished, coverage }, null, 1));
  });

  // Hypothesis under test (capture-pending-fixtures comment + operator notes):
  // "the live state can hold the SAME instance id on two hand entries"
  // ('A Momentary Glance ::1' twice in one hand, allegedly stable). The
  // GraphQL gameState response = loadState (DB deserialize or Redis) →
  // filterPrivateData → JSON.stringify. This test walks the exact same
  // layers with both Glance copies in one hand and after every storage
  // round-trip: the serialized → deserialized → projected → serialized →
  // deserialized hand must keep exactly the two DISTINCT instance ids.
  it('serialize/deserialize/projection round-trips never duplicate instance ids in a projected hand', async () => {
    const glanceCard = {
      id: 'glance', name: 'A Momentary Glance', nameEn: 'A Momentary Glance',
      nameRu: 'A Momentary Glance', cardType: 'SCHEME', count: 2, effects: [],
    };
    const prisma = {
      // НД-2: the game starts on a real board (the default one), never on an empty 20x20 grid
      game: { findUnique: jest.fn().mockResolvedValue({ boardId: marmorealBoardRow().id }) },
      board: { findUnique: jest.fn().mockResolvedValue(marmorealBoardRow()) },
      gamePlayer: { findMany: jest.fn().mockResolvedValue([
        { userId: 'first', heroId: 'glance-hero', seatOrder: 0 },
        { userId: 'second', heroId: 'other-hero', seatOrder: 1 },
      ]) },
      hero: { findUnique: jest.fn()
        .mockResolvedValueOnce({ id: 'glance-hero', name: 'Glance Hero', health: 10, movement: 2, sidekicks: [], cards: [glanceCard] })
        .mockResolvedValueOnce({ id: 'other-hero', name: 'Other Hero', health: 10, movement: 2, sidekicks: [], cards: [{ ...glanceCard, id: 'filler' }] }) },
    };
    const saveState = jest.fn();
    const initializer = new GameInitializationService(prisma as any, { saveState } as any);
    const initial = await initializer.initializeGameState('round-trip');
    // Force both Glance copies into one hand deterministically.
    const handIds = initial.decks.first.cards.filter((c) => c.cardId === 'glance').map((c) => c.id);
    expect(handIds).toHaveLength(2);
    expect(new Set(handIds).size).toBe(2);
    const forced: GameState = {
      ...initial,
      handZones: {
        first: { cards: initial.decks.first.cards.filter((c) => c.cardId === 'glance').map((c) => ({ ...c, isVisible: true })), maxSize: 7 },
        second: initial.handZones.second,
      },
      decks: {
        first: { ...initial.decks.first, drawPile: [], topCard: undefined },
        second: initial.decks.second,
      },
    };

    const svc = new GameStateService({} as any, {} as any, {} as any);
    let current = forced;
    for (let hop = 0; hop < 3; hop++) {
      const persisted = svc.serialize(current);           // DB column shape (compact keys)
      current = svc.deserialize(JSON.parse(JSON.stringify(persisted))); // transport round-trip
      for (const viewer of ['first', 'second']) {
        const projected = svc.filterPrivateData(current, viewer);
        const ownHand = projected.handZones[viewer].cards.map((c) => c.id).sort();
        if (viewer === 'first') {
          expect(ownHand).toEqual([...handIds].sort());
          expect(new Set(ownHand).size).toBe(2);
        } else {
          expect(projected.handZones.first.cards.map((c) => c.id)).toHaveLength(2);
          expect(new Set(projected.handZones.first.cards.map((c) => c.id)).size).toBe(2);
        }
      }
    }
    expect(current.phase).not.toBe(GamePhase.GAME_OVER);
  });
});
