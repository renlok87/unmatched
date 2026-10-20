/**
 * ability-rules — запросы к ABILITY_CONFIGS вне реестра (разбор DE 2026-10-20):
 * неотменяемость карт (RULE-01), смена стойки (RULE-03), размер руки (D5).
 */

import { handSizeLimitsFor, isCardUncancellable, toggleHeroStance } from './ability-rules';
import { FighterType, GamePhase } from '../models';
import type { Fighter, GameState } from '../models';

const fighter = (id: string, ownerId: string, name: string, heroSlug: string, type = FighterType.HERO): Fighter => ({
  id, ownerId, heroId: heroSlug, heroSlug, name, type,
  health: 10, maxHealth: 10, position: { x: 0, y: 0 }, effects: [], hasSidekick: false,
});

const state = (fighters: Fighter[], heroStances?: Record<string, string>): GameState =>
  ({
    gameId: 'g', sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER, turnCount: 1,
    currentTurnPlayerId: 'p1', players: [], fighters,
    decks: {}, discardPiles: {}, handZones: {},
    boardState: { width: 5, height: 5, cells: [], doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(), lastActionBy: 'p1', version: 1, ...(heroStances ? { heroStances } : {}) },
  }) as unknown as GameState;

describe('ability-rules', () => {
  describe('isCardUncancellable (RULE-01)', () => {
    const holmes = state([
      fighter('h', 'p1', 'Sherlock Holmes', 'sherlock-holmes'),
      fighter('w', 'p1', 'Dr. Watson', 'sherlock-holmes', FighterType.MINION),
    ]);

    it('Holmes: банер героя и помощника защищён, Any — нет', () => {
      expect(isCardUncancellable(holmes, { bannerName: 'Holmes' }, 'h')).toBe(true);
      expect(isCardUncancellable(holmes, { bannerName: 'Dr. Watson' }, 'w')).toBe(true);
      expect(isCardUncancellable(holmes, { bannerName: 'Any' }, 'h')).toBe(false);
    });

    it("печатное «This card's effects cannot be canceled» — у любого героя", () => {
      const plain = state([fighter('a', 'p1', 'King Arthur', 'king-arthur')]);
      expect(isCardUncancellable(plain, { bannerName: 'Any', text: "This card's effects cannot be canceled." }, 'a')).toBe(true);
      expect(isCardUncancellable(plain, { bannerName: 'Arthur', text: 'Draw 1 card.' }, 'a')).toBe(false);
      expect(isCardUncancellable(plain, null, 'a')).toBe(false);
    });
  });

  describe('toggleHeroStance (CHANGE_SIZE)', () => {
    it('Alice: по умолчанию BIG → SMALL → BIG', () => {
      const alice = state([fighter('a', 'p1', 'Alice', 'alice')]);
      const small = toggleHeroStance(alice, 'p1');
      expect(small.metadata.heroStances).toEqual({ p1: 'small' });
      expect(toggleHeroStance(small, 'p1').metadata.heroStances).toEqual({ p1: 'big' });
    });

    it('герой без стоек — тот же объект state', () => {
      const plain = state([fighter('a', 'p1', 'King Arthur', 'king-arthur')]);
      expect(toggleHeroStance(plain, 'p1')).toBe(plain);
    });
  });

  it('handSizeLimitsFor: Michelangelo 3/3, остальные — общие 5/7', () => {
    const defaults = { starting: 5, max: 7 };
    expect(handSizeLimitsFor('michelangelo', defaults)).toEqual({ starting: 3, max: 3 });
    expect(handSizeLimitsFor('medusa', defaults)).toEqual(defaults);
    expect(handSizeLimitsFor(undefined, defaults)).toEqual(defaults);
  });
});
