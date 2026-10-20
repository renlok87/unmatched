/**
 * DET-1 (docs/research/de-reverse-2026-10-20/VERDICT.md §3 P1.1): the only
 * source of randomness of the rules. A seeded sfc32 generator whose whole
 * state — four uint32 — lives in GameState.metadata.rng and goes through
 * serialize/deserialize, so a game is reproduced by (start snapshot, input
 * commands). Better than the original (seed only, the RNG state is not saved)
 * and DuelEngine (System.Random cannot be serialized).
 *
 * Every function is pure: it takes a state and returns the value together
 * with the advanced state. The RNG state reveals every future shuffle, so
 * GameStateService.filterPrivateData removes it from every projection.
 */
import { randomBytes } from 'node:crypto';
import type { GameState } from '../models/game-state.model';

/** sfc32 state: four uint32 words a, b, c, d (d is the counter). */
export type RngState = readonly [number, number, number, number];

/** Rounds discarded after seeding: decorrelates close seeds (sfc32 reference value). */
const WARMUP_ROUNDS = 12;

function sfc32Step(s: RngState): [number, RngState] {
  let [a, b, c, d] = s;
  const t = (((a + b) | 0) + d) | 0;
  d = (d + 1) | 0;
  a = b ^ (b >>> 9);
  b = (c + (c << 3)) | 0;
  c = (c << 21) | (c >>> 11);
  c = (c + t) | 0;
  return [t >>> 0, [a >>> 0, b >>> 0, c >>> 0, d >>> 0]];
}

function warmUp(s: RngState): RngState {
  let state = s;
  for (let i = 0; i < WARMUP_ROUNDS; i++) state = sfc32Step(state)[1];
  return state;
}

/** splitmix32: expands one 32-bit seed into well-mixed words. */
function splitmix32(seed: number): () => number {
  let x = seed >>> 0;
  return () => {
    x = (x + 0x9e3779b9) >>> 0;
    let z = x;
    z = Math.imul(z ^ (z >>> 16), 0x85ebca6b) >>> 0;
    z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35) >>> 0;
    return (z ^ (z >>> 16)) >>> 0;
  };
}

/** Deterministic state from a number or a string (tests, self-play, repro of a fuzz seed). */
export function rngFromSeed(seed: number | string): RngState {
  let n: number;
  if (typeof seed === 'number') {
    n = seed >>> 0;
  } else {
    // FNV-1a 32 over UTF-16 code units
    n = 0x811c9dc5;
    for (let i = 0; i < seed.length; i++) {
      n = Math.imul(n ^ seed.charCodeAt(i), 0x01000193) >>> 0;
    }
  }
  const next = splitmix32(n);
  return warmUp([next(), next(), next(), next()]);
}

/** Fresh state from crypto: the seed of every new game. */
export function randomRngState(): RngState {
  const bytes = randomBytes(16);
  return warmUp([bytes.readUInt32LE(0), bytes.readUInt32LE(4), bytes.readUInt32LE(8), bytes.readUInt32LE(12)]);
}

/** A structurally valid state (four uint32); anything else is not a saved RNG. */
export function isRngState(value: unknown): value is RngState {
  return (
    Array.isArray(value) &&
    value.length === 4 &&
    value.every((w) => Number.isInteger(w) && w >= 0 && w <= 0xffffffff)
  );
}

/** Uniform float in [0, 1). */
export function rngNext(s: RngState): [number, RngState] {
  const [word, next] = sfc32Step(s);
  return [word / 4294967296, next];
}

/** Uniform integer in [0, n), n >= 1. */
export function rngInt(s: RngState, n: number): [number, RngState] {
  if (!Number.isInteger(n) || n < 1) throw new RangeError(`rngInt: n must be a positive integer, got ${n}`);
  const [r, next] = rngNext(s);
  return [Math.floor(r * n), next];
}

/** Fisher-Yates, the same loop the engine used with Math.random. */
export function rngShuffle<T>(s: RngState, items: readonly T[]): [T[], RngState] {
  const result = [...items];
  let state = s;
  for (let i = result.length - 1; i > 0; i--) {
    let j: number;
    [j, state] = rngInt(state, i + 1);
    [result[i], result[j]] = [result[j], result[i]];
  }
  return [result, state];
}

// ---------------------------------------------------------------------------
// GameState wrappers: read metadata.rng, return the advanced state with it.
// A state without rng (a save from before DET-1) gets a fresh crypto state on
// its first random step; from then on the game is reproducible.
// ---------------------------------------------------------------------------

function rngOf(state: GameState): RngState {
  const saved = state.metadata.rng;
  return isRngState(saved) ? saved : randomRngState();
}

function withRng(state: GameState, rng: RngState): GameState {
  return { ...state, metadata: { ...state.metadata, rng } };
}

/** Uniform integer in [0, n) drawn from the game RNG. */
export function stateRandomInt(state: GameState, n: number): { value: number; state: GameState } {
  const [value, rng] = rngInt(rngOf(state), n);
  return { value, state: withRng(state, rng) };
}

/** Shuffle drawn from the game RNG. */
export function stateShuffle<T>(state: GameState, items: readonly T[]): { items: T[]; state: GameState } {
  const [shuffled, rng] = rngShuffle(rngOf(state), items);
  return { items: shuffled, state: withRng(state, rng) };
}
