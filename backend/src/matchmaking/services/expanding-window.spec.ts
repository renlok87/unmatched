/**
 * Expanding Window Logic Tests
 *
 * ФАЗА 8F: Expanding Window Tests
 */

import { getEloRange, DEFAULT_EXPANDING_WINDOW } from '../models';

describe('Expanding Window Logic', () => {
  describe('getEloRange', () => {
    it('should return +/-100 ELO for wait time <= 30 seconds', () => {
      const [min, max] = getEloRange(20);
      expect(min).toBe(-100);
      expect(max).toBe(100);
    });

    it('should return +/-200 ELO for wait time 30-60 seconds', () => {
      const [min, max] = getEloRange(45);
      expect(min).toBe(-200);
      expect(max).toBe(200);
    });

    it('should return +/-400 ELO for wait time 60-120 seconds', () => {
      const [min, max] = getEloRange(90);
      expect(min).toBe(-400);
      expect(max).toBe(400);
    });

    it('should return unlimited range for wait time > 120 seconds', () => {
      const [min, max] = getEloRange(150);
      expect(min).toBe(-Infinity);
      expect(max).toBe(Infinity);
    });

    it('should handle edge case at exactly 30 seconds', () => {
      const [min, max] = getEloRange(30);
      expect(min).toBe(-100);
      expect(max).toBe(100);
    });

    it('should handle edge case at exactly 60 seconds', () => {
      const [min, max] = getEloRange(60);
      expect(min).toBe(-200);
      expect(max).toBe(200);
    });

    it('should handle edge case at exactly 120 seconds', () => {
      const [min, max] = getEloRange(120);
      expect(min).toBe(-400);
      expect(max).toBe(400);
    });
  });

  describe('Match eligibility with expanding window', () => {
    const testCases = [
      { waitTime: 0, eloDiff: 50, shouldMatch: true },
      { waitTime: 0, eloDiff: 150, shouldMatch: false },
      { waitTime: 30, eloDiff: 100, shouldMatch: true },
      { waitTime: 30, eloDiff: 250, shouldMatch: false },
      { waitTime: 60, eloDiff: 200, shouldMatch: true },
      { waitTime: 60, eloDiff: 500, shouldMatch: false },
      { waitTime: 120, eloDiff: 400, shouldMatch: true },
      { waitTime: 120, eloDiff: 1000, shouldMatch: false },
      { waitTime: 121, eloDiff: 1000, shouldMatch: true },
      { waitTime: 121, eloDiff: 10000, shouldMatch: true },
    ];

    testCases.forEach(({ waitTime, eloDiff, shouldMatch }) => {
      it(`waitTime=${waitTime}s, eloDiff=${eloDiff} -> ${shouldMatch ? 'match' : 'no match'}`, () => {
        const [minDelta, maxDelta] = getEloRange(waitTime);
        // minDelta отрицательное, maxDelta положительное
        // eloDiff - это абсолютная разница рейтингов
        const isMatch = Math.abs(eloDiff) <= maxDelta || maxDelta === Infinity;
        expect(isMatch).toBe(shouldMatch);
      });
    });
  });
});
