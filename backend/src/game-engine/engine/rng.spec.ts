import {
  isRngState,
  randomRngState,
  rngFromSeed,
  rngInt,
  rngNext,
  rngShuffle,
  stateRandomInt,
  stateShuffle,
  type RngState,
} from './rng';
import type { GameState } from '../models';

const draw = (s: RngState, n: number): number[] => {
  const out: number[] = [];
  let state = s;
  for (let i = 0; i < n; i++) {
    let v: number;
    [v, state] = rngNext(state);
    out.push(v);
  }
  return out;
};

describe('DET-1 game RNG (sfc32, state in GameState.metadata.rng)', () => {
  it('is a pure function of its state: the same seed gives the same stream, another seed another', () => {
    expect(draw(rngFromSeed(42), 50)).toEqual(draw(rngFromSeed(42), 50));
    expect(draw(rngFromSeed('game-1'), 50)).toEqual(draw(rngFromSeed('game-1'), 50));
    expect(draw(rngFromSeed(42), 50)).not.toEqual(draw(rngFromSeed(43), 50));
    for (const v of draw(rngFromSeed(7), 1000)) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it('keeps its whole state in four uint32 that survive JSON', () => {
    const s = rngFromSeed(9000);
    expect(isRngState(s)).toBe(true);
    const restored = JSON.parse(JSON.stringify(s));
    expect(draw(restored, 20)).toEqual(draw(s, 20));
    expect(isRngState(randomRngState())).toBe(true);
    for (const bad of [undefined, null, [1, 2, 3], [1, 2, 3, -1], [1, 2, 3, 2 ** 32], ['1', 2, 3, 4], { a: 1 }]) {
      expect(isRngState(bad)).toBe(false);
    }
  });

  it('crypto seeds differ between games', () => {
    expect(randomRngState()).not.toEqual(randomRngState());
  });

  it('rngInt is uniform enough over a die', () => {
    const counts = Array<number>(6).fill(0);
    let s = rngFromSeed(1);
    for (let i = 0; i < 60_000; i++) {
      let v: number;
      [v, s] = rngInt(s, 6);
      counts[v]++;
    }
    for (const c of counts) expect(Math.abs(c - 10_000)).toBeLessThan(500);
    expect(() => rngInt(s, 0)).toThrow(RangeError);
  });

  it('rngShuffle is a deterministic permutation and advances the state', () => {
    const items = Array.from({ length: 30 }, (_, i) => `card::${i}`);
    const s = rngFromSeed(5);
    const [a, afterA] = rngShuffle(s, items);
    const [b] = rngShuffle(s, items);
    expect(a).toEqual(b);
    expect([...a].sort()).toEqual([...items].sort());
    expect(a).not.toEqual(items);
    expect(afterA).not.toEqual(s);
    expect(items[0]).toBe('card::0'); // the input is not mutated
  });

  it('state wrappers store the advanced state; a save without rng gets a fresh one', () => {
    const base = { metadata: { lastActionAt: new Date(0), lastActionBy: 'a', version: 1 } } as unknown as GameState;
    const seeded = { ...base, metadata: { ...base.metadata, rng: rngFromSeed(3) } } as GameState;
    const one = stateShuffle(seeded, [1, 2, 3, 4, 5]);
    const two = stateShuffle(seeded, [1, 2, 3, 4, 5]);
    expect(one.items).toEqual(two.items);
    expect(one.state.metadata.rng).toEqual(two.state.metadata.rng);
    expect(one.state.metadata.rng).not.toEqual(seeded.metadata.rng);
    const next = stateRandomInt(one.state, 10);
    expect(next.value).toBeGreaterThanOrEqual(0);
    expect(next.value).toBeLessThan(10);
    expect(next.state.metadata.rng).not.toEqual(one.state.metadata.rng);

    const legacy = stateRandomInt(base, 4);
    expect(isRngState(legacy.state.metadata.rng)).toBe(true);
  });
});
