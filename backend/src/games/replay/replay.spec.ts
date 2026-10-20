/**
 * DET-2 end to end: a game played through the LIVE server paths — the
 * GraphQL mutation resolver (random legal policy for both seats), the VS_AI
 * drain (AiTurnService) and the server combat timeout (CombatTimeoutService)
 * — on a real map, persisted by the real GameStateService into an in-memory
 * Postgres double, replays from the stored start snapshot and the stored
 * GameAction rows with a fresh executor, hash for hash, to the stored final
 * state. The live path reads states back from the Redis double (raw states),
 * the replay from the serialized rows: the hash check also proves both
 * storage paths give the same game.
 */
import { GameStateService } from '../game-state.service';
import type { GameState } from '../game-state.service';
import { GameInitializationService } from '../services/game-initialization.service';
import { GameActionsResolver } from '../resolvers/game-actions.resolver';
import { AiTurnService } from '../services/ai-turn.service';
import { CombatTimeoutService } from '../services/combat-timeout.service';
import { AiDecisionService } from '../../game-engine/services/ai-decision.service';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { GamePhase } from '../../game-engine/models';
import { rngFromSeed } from '../../game-engine/engine/rng';
import { s03Engine } from '../../test/fixtures/s03-engine.fixture';
import {
  Dice,
  boardRowOf,
  candidatesFor,
  heroes,
  weightedOrder,
  type SelfPlayBoard,
} from '../../test/selfplay/selfplay';
import { loadReplay, replayGame, stateHash } from './replay';

function memoryDb(gameId: string, board: SelfPlayBoard) {
  const boardRow = boardRowOf(board);
  const rows = heroes();
  const game = { id: gameId, hostId: 'u1', opponentId: 'u2', boardId: boardRow.id, mode: 'VS_AI', status: 'IN_PROGRESS', version: 0 };
  const players = [
    { userId: 'u1', heroId: rows.medusa.id, seatOrder: 0 },
    { userId: 'u2', heroId: rows.arthur.id, seatOrder: 1 },
  ];
  const states = new Map<string, any>();
  const snapshots: any[] = [];
  const actions: any[] = [];
  const stats = (userId: string) => ({ userId, gamesPlayed: 0, gamesWon: 0, gamesLost: 0, currentElo: 1000, peakElo: 1000 });
  const prisma: any = {
    game: {
      findUnique: async ({ where }: any) => (where.id === gameId ? { ...game } : null),
      updateMany: async ({ where, data }: any) => {
        if (where.id !== gameId || game.status !== where.status) return { count: 0 };
        Object.assign(game, data);
        return { count: 1 };
      },
    },
    gamePlayer: { findMany: async () => players },
    hero: { findUnique: async ({ where }: any) => Object.values(rows).find((h) => h.id === where.id) ?? null },
    board: { findUnique: async () => boardRow },
    gameState: {
      findUnique: async ({ where }: any) => states.get(where.gameId) ?? null,
      findMany: async () => [],
      upsert: async ({ where, create, update }: any) => {
        const row = JSON.parse(JSON.stringify(states.has(where.gameId) ? { ...states.get(where.gameId), ...update } : create));
        states.set(where.gameId, row);
        return row;
      },
    },
    gameStateSnapshot: {
      create: async ({ data }: any) => { snapshots.push(JSON.parse(JSON.stringify(data))); return data; },
      findFirst: async ({ where }: any) =>
        snapshots.filter((s) => s.gameId === where.gameId).sort((a, b) => a.sequence - b.sequence)[0] ?? null,
    },
    gameAction: {
      createMany: async ({ data }: any) => {
        actions.push(...data.map((d: any) => JSON.parse(JSON.stringify({ ...d, timestamp: new Date() }))));
        return { count: data.length };
      },
      findMany: async ({ where }: any) =>
        actions.filter((a) => a.gameId === where.gameId).sort((a, b) => a.sequenceNumber - b.sequenceNumber),
    },
    userStats: { createMany: async () => ({ count: 2 }), update: async () => ({}) },
    $queryRaw: async () => [stats('u1'), stats('u2')],
    $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
  };
  const cache = new Map<string, string>();
  const redis: any = {
    getJson: async (key: string) => (cache.has(key) ? JSON.parse(cache.get(key)!) : null),
    setJsonex: async (key: string, _ttl: number, value: unknown) => { cache.set(key, JSON.stringify(value)); return 'OK'; },
    del: async (key: string) => { cache.delete(key); return 1; },
  };
  return { prisma, redis, game, states, snapshots, actions };
}

async function playLiveGame(board: SelfPlayBoard, seed: number) {
  const gameId = `replay-${board}-${seed}`;
  const db = memoryDb(gameId, board);
  const states = new GameStateService(db.prisma, db.redis);
  const { executor } = s03Engine({ abilities: true });
  const lock: any = { withLockOptions: async (_key: string, run: () => Promise<unknown>) => run() };
  const subscription: any = { publishGameUpdate: async () => undefined };
  const timeoutQueue: any = { getJob: async () => null, getJobs: async () => [], add: async () => ({}), close: async () => undefined };
  const timeout = new CombatTimeoutService(timeoutQueue, states, lock, db.prisma, executor, subscription);
  const scheduler: any = { scheduleAutoResolve: async () => undefined, cancelAutoResolve: async () => undefined };
  const ai = new AiTurnService(db.prisma, lock, states, subscription, executor, new AiDecisionService(new AdjacencyService()), scheduler);
  const resolver = new GameActionsResolver(states, subscription, lock, scheduler, executor, { maybeRunAiTurns: async () => undefined } as any);

  const init = new GameInitializationService(db.prisma, states);
  init.rngSeed = () => rngFromSeed(seed);
  await init.initializeGameState(gameId);

  const dice = new Dice(rngFromSeed(`live:${seed}`));
  const used = { resolver: 0, ai: 0, timeout: 0 };
  for (let step = 0; step < 4000; step++) {
    const state: GameState = await states.loadState(gameId);
    if (state.phase === GamePhase.GAME_OVER) break;
    const before = state.sequenceNumber;

    // the server timeout finishes a combat whose deadline has passed
    if (state.metadata.combatInfo && dice.chance(0.15)) {
      timeout.now = () => new Date(Date.now() + 120_000);
      const result = await timeout.processAutoResolve({ gameId, attackSequenceNumber: before, stage: state.phase === GamePhase.COMBAT ? 'DEFENSE' : 'RESOLVE' });
      if (result.success) { used.timeout++; continue; }
    }
    // the bot (u2) plays its own decisions through the VS_AI drain
    if (dice.chance(0.5)) {
      await ai.maybeRunAiTurns(gameId);
      if ((await states.loadState(gameId)).sequenceNumber !== before) { used.ai++; continue; }
    }
    // a client sends a GraphQL mutation (random legal policy, either seat)
    let progressed = false;
    for (const cand of weightedOrder(await candidatesFor(state, dice, executor, Date.now()), dice)) {
      if (cand.system) continue; // only the timeout service resolves as the system
      try {
        await (resolver as any)[cand.kind](cand.input, { req: { user: { id: cand.userId } } }, null);
        progressed = true;
        used.resolver++;
        break;
      } catch {
        // rejected: the next candidate
      }
    }
    if (!progressed) throw new Error(`live game ${gameId} stalled at seq ${before} (${state.phase})`);
  }
  return { gameId, db, final: await states.loadState(gameId), used };
}

describe('DET-2: a live game replays from its start snapshot and command journal', () => {
  it.each([
    ['marmoreal', 101],
    ['sarpedon', 202],
  ] as const)('%s seed %d: resolver + AI + timeout game, stored rows replay hash for hash', async (board, seed) => {
    const live = await playLiveGame(board, seed);
    expect(live.final.phase).toBe(GamePhase.GAME_OVER);
    expect(live.used.resolver).toBeGreaterThan(0);
    expect(live.used.ai).toBeGreaterThan(0);
    expect(live.used.timeout).toBeGreaterThan(0);
    if (process.env.SELFPLAY_REPORT) console.log(board, seed, live.used, live.db.actions.map((a: any) => a.payload.action).join(' '));

    // exactly one start snapshot, at the deal
    expect(live.db.snapshots).toHaveLength(1);
    expect(live.db.snapshots[0].sequence).toBe(1);
    expect(live.db.snapshots[0].fullState.engine.parserVersion).toBeGreaterThan(0);

    // one command row for every saved seq 2..final, no gap, terminal pair last
    const commandSeqs = live.db.actions.filter((a) => a.payload.cmd).map((a) => a.sequenceNumber);
    expect(commandSeqs).toEqual(Array.from({ length: live.final.sequenceNumber - 1 }, (_, i) => i + 2));
    const last = live.db.actions[live.db.actions.length - 1];
    expect(last.type).toBe('GAME_ENDED');
    expect(last.payload.winnerId).toBe(live.final.metadata.winnerId ?? null);

    const stored = await loadReplay(live.db.prisma, live.gameId);
    const replay = await replayGame(s03Engine({ abilities: true }).executor, stored!.start, stored!.rows);
    expect(replay.divergence).toBeUndefined();
    expect(replay.engineChanged).toBeUndefined();
    expect(replay.applied).toBe(commandSeqs.length);
    expect(stateHash(replay.state)).toBe(stateHash(live.final));
    expect(replay.state.metadata.winnerId).toBe(live.final.metadata.winnerId);
  }, 120_000);

  it('a tampered journal stops the replay at the first diverging seq', async () => {
    const live = await playLiveGame('marmoreal', 303);
    const stored = await loadReplay(live.db.prisma, live.gameId);
    const rows = stored!.rows.map((r, i) => (i === 5 ? { ...r, hash: '0'.repeat(64) } : r));
    const replay = await replayGame(s03Engine({ abilities: true }).executor, stored!.start, rows);
    expect(replay.divergence).toMatchObject({ seq: rows[5].seq, reason: 'hash' });
    expect(replay.applied).toBe(5);

    const gap = await replayGame(s03Engine({ abilities: true }).executor, stored!.start, stored!.rows.filter((_, i) => i !== 3));
    expect(gap.divergence).toMatchObject({ seq: stored!.rows[4].seq, reason: 'gap' });
  }, 120_000);
});
