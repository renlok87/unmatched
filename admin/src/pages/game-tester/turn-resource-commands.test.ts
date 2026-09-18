import { describe, expect, it } from 'vitest';
import { parseManeuverCompletion } from './turn-resource-commands';

describe('S03 Game Tester staged maneuver syntax', () => {
  it('allows zero movement without a boost', () => {
    expect(parseManeuverCompletion('-')).toEqual({ boostRef: null, moves: [] });
  });
  it('parses newly drawn boost and ordered paths of multiple fighters', () => {
    expect(parseManeuverCompletion('c7 f0 1,1 1,2 ; f2 2,2')).toEqual({
      boostRef: 'c7', moves: [
        { fighterRef: 'f0', path: [{ x: 1, y: 1 }, { x: 1, y: 2 }] },
        { fighterRef: 'f2', path: [{ x: 2, y: 2 }] },
      ],
    });
  });
  it.each(['- f0', '- f0 1,2,3', '- f0 1.5,2', '- f0 1,', ''])('rejects malformed completion %s', input => {
    expect(() => parseManeuverCompletion(input)).toThrow();
  });
});
