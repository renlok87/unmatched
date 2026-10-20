/**
 * DET-2: replay of a game from its start snapshot and its command journal
 * (replay/replay-format.ts). Every command runs through executeGameCommand —
 * the same entry the live path used — on the state of the previous step after
 * a storage round-trip (serialize → deserialize, as a load from Postgres), and
 * the canonical hash of each result is compared with the hash the live path
 * wrote. The first difference stops the replay and names the sequence number.
 */
import type { GameState } from '../../game-engine/models';
import type { GameActionExecutorService } from '../../game-engine/services/game-action-executor.service';
import { executeGameCommand, type GameCommand } from '../../game-engine/services/game-command';
import { deserializeGameState, serializeGameState, type SerializedGameState } from '../game-state.service';
import { canonicalStateHash, engineVersion, type EngineVersion, type StartSnapshot } from './replay-format';

/** A GameAction row as Prisma returns it (only the fields the replay reads). */
export interface JournalRow {
  readonly sequenceNumber: number;
  readonly type: string;
  readonly payload: unknown;
}

export interface ReplayCommandRow {
  readonly seq: number;
  readonly command: GameCommand;
  readonly hash?: string;
}

export interface ReplayDivergence {
  readonly seq: number;
  readonly reason: 'gap' | 'rejected' | 'seq' | 'hash';
  readonly detail: string;
}

export interface ReplayResult {
  readonly state: GameState;
  /** Commands applied before the divergence (all of them when none) */
  readonly applied: number;
  readonly divergence?: ReplayDivergence;
  /** Engine of the snapshot differs from this build: a divergence is expected, not a bug */
  readonly engineChanged?: { readonly snapshot: EngineVersion; readonly current: EngineVersion };
}

/** Command rows of a journal in sequence order; GAME_ENDED and lobby rows carry no cmd. */
export function commandRows(rows: readonly JournalRow[]): ReplayCommandRow[] {
  return rows
    .filter((r) => !!(r.payload as { cmd?: unknown } | null)?.cmd)
    .map((r) => {
      const payload = r.payload as { cmd: GameCommand; hash?: string };
      return { seq: r.sequenceNumber, command: payload.cmd, hash: payload.hash };
    })
    .sort((a, b) => a.seq - b.seq);
}

const roundTrip = (state: GameState): GameState =>
  deserializeGameState(JSON.parse(JSON.stringify(serializeGameState(state))) as SerializedGameState);

export function stateHash(state: GameState): string {
  return canonicalStateHash(serializeGameState(state));
}

export async function replayGame(
  executor: GameActionExecutorService,
  start: StartSnapshot,
  rows: readonly ReplayCommandRow[],
): Promise<ReplayResult> {
  const current = engineVersion();
  const snap = start.engine;
  const engineChanged =
    snap.parserVersion !== current.parserVersion || snap.abilityConfigs !== current.abilityConfigs
      ? { snapshot: snap, current }
      : undefined;

  let state = deserializeGameState(JSON.parse(JSON.stringify(start.state)) as SerializedGameState);
  let applied = 0;
  const stop = (divergence: ReplayDivergence): ReplayResult => ({ state, applied, divergence, engineChanged });

  for (const row of rows) {
    if (row.seq !== state.sequenceNumber + 1) {
      return stop({ seq: row.seq, reason: 'gap', detail: `state is at seq ${state.sequenceNumber}` });
    }
    const result = await executeGameCommand(executor, row.command, state);
    if (!result.success || !result.gameState) {
      return stop({ seq: row.seq, reason: 'rejected', detail: `${row.command.kind}: ${result.error ?? 'no state'}` });
    }
    if (result.gameState.sequenceNumber !== row.seq) {
      return stop({ seq: row.seq, reason: 'seq', detail: `${row.command.kind} produced seq ${result.gameState.sequenceNumber}` });
    }
    const next = roundTrip(result.gameState);
    if (row.hash !== undefined) {
      const hash = stateHash(next);
      if (hash !== row.hash) {
        state = next;
        return stop({ seq: row.seq, reason: 'hash', detail: `${row.command.kind}: ${hash} != journal ${row.hash}` });
      }
    }
    state = next;
    applied++;
  }
  return { state, applied, engineChanged };
}

/** Minimal Prisma surface the loader reads (PrismaService or a transaction client). */
export interface ReplaySource {
  readonly gameStateSnapshot: {
    findFirst(args: { where: { gameId: string }; orderBy: { sequence: 'asc' } }): Promise<{ fullState: unknown } | null>;
  };
  readonly gameAction: {
    findMany(args: {
      where: { gameId: string };
      orderBy: Array<Record<string, 'asc'>>;
      select: { sequenceNumber: true; type: true; payload: true };
    }): Promise<JournalRow[]>;
  };
}

/** Start snapshot and command rows of a stored game; null when it has no snapshot (game before DET-2). */
export async function loadReplay(
  source: ReplaySource,
  gameId: string,
): Promise<{ start: StartSnapshot; rows: ReplayCommandRow[] } | null> {
  const snapshot = await source.gameStateSnapshot.findFirst({ where: { gameId }, orderBy: { sequence: 'asc' } });
  if (!snapshot) return null;
  const journal = await source.gameAction.findMany({
    where: { gameId },
    orderBy: [{ sequenceNumber: 'asc' }, { timestamp: 'asc' }],
    select: { sequenceNumber: true, type: true, payload: true },
  });
  return { start: snapshot.fullState as StartSnapshot, rows: commandRows(journal) };
}
