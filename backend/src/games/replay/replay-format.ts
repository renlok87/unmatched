/**
 * DET-2 / DET-5 (docs/research/de-reverse-2026-10-20/VERDICT.md §3 P1.2):
 * the persisted form of a replayable game.
 *
 * - The start snapshot: one GameStateSnapshot row (sequence = the start seq)
 *   whose fullState is { format, engine, state } — the serialized start state
 *   and the engine version it was dealt by.
 * - The command journal: GameAction rows written in the saveState transaction.
 *   A row with payload.cmd is an input command (GameCommand) that produced the
 *   state of its sequenceNumber, and payload.hash is the canonical hash of that
 *   state. Rows without cmd (GAME_ENDED, lobby events) are not commands.
 *
 * The canonical hash is sha256 of a key-sorted JSON of serialize(state) without
 * the clock fields: lastActionAt and the combat startedAt/timeoutAt. Two runs
 * that agree on the rules agree on the hash, whatever the wall clock was.
 */
import { createHash } from 'node:crypto';
import { PARSER_VERSION } from '../../game-engine/effects/effect-text-parser';
import { ABILITY_CONFIGS } from '../../game-engine/abilities/ability-config';
import type { GameCommand } from '../../game-engine/services/game-command';
import type { SerializedGameState } from '../game-state.service';

/** Bump when the snapshot/journal layout changes. */
export const REPLAY_FORMAT_VERSION = 1;

export interface EngineVersion {
  readonly replayFormat: number;
  /** effect-text-parser version that turned card texts into effects */
  readonly parserVersion: number;
  /** sha256 of ABILITY_CONFIGS: a changed hero ability makes old journals diverge */
  readonly abilityConfigs: string;
  /** Build commit when the deployment provides one */
  readonly commit?: string;
}

export interface StartSnapshot {
  readonly format: number;
  readonly engine: EngineVersion;
  readonly state: SerializedGameState;
}

/** payload of a command row of the GameAction journal */
export interface CommandJournalPayload {
  /** eventsSince fields (unchanged: action name and the actor's own input) */
  readonly action: string;
  readonly input?: unknown;
  /** The input command that produced this row's state */
  readonly cmd: GameCommand;
  /** canonicalStateHash of that state */
  readonly hash: string;
}

let cachedAbilityHash: string | undefined;

export function engineVersion(): EngineVersion {
  cachedAbilityHash ??= sha256(stableStringify(ABILITY_CONFIGS));
  const commit = process.env.GIT_COMMIT || process.env.SOURCE_COMMIT || undefined;
  return {
    replayFormat: REPLAY_FORMAT_VERSION,
    parserVersion: PARSER_VERSION,
    abilityConfigs: cachedAbilityHash,
    ...(commit ? { commit } : {}),
  };
}

/** Keys of serialize(state).m and .m.ci that hold wall-clock time. */
const CLOCK_KEYS_META = ['la'] as const;
const CLOCK_KEYS_COMBAT = ['sa', 'ta'] as const;

/** sha256 of serialize(state) without clock fields; stable across key order. */
export function canonicalStateHash(serialized: SerializedGameState): string {
  const m: Record<string, unknown> = { ...serialized.m };
  for (const k of CLOCK_KEYS_META) delete m[k];
  if (m.ci && typeof m.ci === 'object') {
    const ci: Record<string, unknown> = { ...(m.ci as Record<string, unknown>) };
    for (const k of CLOCK_KEYS_COMBAT) delete ci[k];
    m.ci = ci;
  }
  return sha256(stableStringify({ ...serialized, m }));
}

/** JSON with object keys sorted; undefined members dropped, as JSON.stringify does. */
export function stableStringify(value: unknown): string {
  return JSON.stringify(sortKeys(value));
}

function sortKeys(value: unknown): unknown {
  if (value === null || typeof value !== 'object') return value;
  if (value instanceof Date) return value.toISOString();
  if (Array.isArray(value)) return value.map((v) => (v === undefined ? null : sortKeys(v)));
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(value as Record<string, unknown>).sort()) {
    const v = (value as Record<string, unknown>)[key];
    if (v !== undefined) out[key] = sortKeys(v);
  }
  return out;
}

function sha256(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}
