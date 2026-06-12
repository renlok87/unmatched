/**
 * Daredevil Handler Unit Tests
 *
 * Тесты для обработчика способности Daredevil - Blind Boost
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { DaredevilHandler, BlindBoostResult } from './daredevil.handler';
import type { GameState } from '../../models/game-state.model';
import type { Card } from '../../models/card.model';
import { GamePhase } from '../../models/game-state.model';
import { CardType } from '../../models/card.model';
import { createEmptyBoardState } from '../../models/board.model';

describe('DaredevilHandler', () => {
  let handler: DaredevilHandler;
  let mockState: GameState;
  const playerId = 'player-daredevil';

  const createMockCard = (id: string, name: string, boost: number): Card => ({
    id,
    cardId: id,
    name,
    nameEn: name,
    nameRu: name,
    cardType: CardType.ATTACK,
    attackValue: 3,
    boostValue: boost,
  });

  beforeEach(() => {
    handler = new DaredevilHandler();

    // Создаём mock состояние игры
    mockState = {
      gameId: 'test-game',
      sequenceNumber: 1,
      phase: GamePhase.COMBAT,
      turnCount: 1,
      currentTurnPlayerId: playerId,
      players: [
        {
          userId: playerId,
          heroId: 'daredevil',
          health: 17,
          maxHealth: 17,
          fighterIds: ['fighter-daredevil'],
          isAlive: true,
        },
      ],
      fighters: [],
      decks: {
        [playerId]: {
          cards: [],
          drawPile: [
            createMockCard('card-1', 'Billy Club', 2),
            createMockCard('card-2', 'Radar Sense', 1),
          ],
          topCard: createMockCard('card-1', 'Billy Club', 2),
        },
      },
      discardPiles: {
        [playerId]: [],
      },
      handZones: {
        [playerId]: {
          cards: [],
          maxSize: 5,
        },
      },
      boardState: createEmptyBoardState(),
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: playerId,
        version: 1,
      },
    } as GameState;
  });

  describe('Свойства обработчика', () => {
    it('должен иметь правильный heroId', () => {
      expect(handler.heroId).toBe('daredevil');
    });

    it('должен иметь правильное название способности', () => {
      expect(handler.abilityName).toBe('Blind Boost');
    });

    it('должен иметь описание способности', () => {
      expect(handler.abilityDescription).toContain('BOOST');
      expect(handler.abilityDescription).toContain('BOOST');
    });
  });

  describe('canTrigger', () => {
    it('должен возвращать true когда в руке 2 карты и в колоде есть карты', () => {
      const handZone = {
        cards: [
          { ...createMockCard('hand-1', 'Card 1', 0), isVisible: true },
          { ...createMockCard('hand-2', 'Card 2', 0), isVisible: true },
        ],
        maxSize: 5,
      };

      const newState = {
        ...mockState,
        handZones: { ...mockState.handZones, [playerId]: handZone },
      };

      const context = {
        attackerId: 'fighter-daredevil',
        defenderId: 'fighter-enemy',
        isBlindBoostAvailable: true,
      };

      expect(handler.canTrigger(newState, playerId, context)).toBe(true);
    });

    it('должен возвращать true когда в руке 1 карта и в колоде есть карты', () => {
      const handZone = {
        cards: [{ ...createMockCard('hand-1', 'Card 1', 0), isVisible: true }],
        maxSize: 5,
      };

      const newState = {
        ...mockState,
        handZones: { ...mockState.handZones, [playerId]: handZone },
      };

      const context = {
        attackerId: 'fighter-daredevil',
        defenderId: 'fighter-enemy',
        isBlindBoostAvailable: true,
      };

      expect(handler.canTrigger(newState, playerId, context)).toBe(true);
    });

    it('должен возвращать false когда в руке 3 карты', () => {
      const handZone = {
        cards: [
          { ...createMockCard('hand-1', 'Card 1', 0), isVisible: true },
          { ...createMockCard('hand-2', 'Card 2', 0), isVisible: true },
          { ...createMockCard('hand-3', 'Card 3', 0), isVisible: true },
        ],
        maxSize: 5,
      };

      const newState = {
        ...mockState,
        handZones: { ...mockState.handZones, [playerId]: handZone },
      };

      const context = {
        attackerId: 'fighter-daredevil',
        defenderId: 'fighter-enemy',
        isBlindBoostAvailable: true,
      };

      expect(handler.canTrigger(newState, playerId, context)).toBe(false);
    });

    it('должен возвращать false когда колода пуста', () => {
      const handZone = {
        cards: [{ ...createMockCard('hand-1', 'Card 1', 0), isVisible: true }],
        maxSize: 5,
      };

      const deck = {
        cards: [],
        drawPile: [],
      };

      const newState = {
        ...mockState,
        handZones: { ...mockState.handZones, [playerId]: handZone },
        decks: { ...mockState.decks, [playerId]: deck },
      };

      const context = {
        attackerId: 'fighter-daredevil',
        defenderId: 'fighter-enemy',
        isBlindBoostAvailable: true,
      };

      expect(handler.canTrigger(newState, playerId, context)).toBe(false);
    });

    it('работает и без контекста (багфикс A8: раньше безусловное false)', () => {
      expect(handler.canTrigger(mockState, playerId)).toBe(true);
    });
  });

  describe('getBoostValue', () => {
    it('должен возвращать BOOST значение верхней карты', () => {
      expect(handler.getBoostValue(mockState, playerId)).toBe(2);
    });

    it('должен возвращать 0 когда колода пуста', () => {
      const deck = {
        cards: [],
        drawPile: [],
      };

      const newState = {
        ...mockState,
        decks: { ...mockState.decks, [playerId]: deck },
      };

      expect(handler.getBoostValue(newState, playerId)).toBe(0);
    });
  });

  describe('peekTopCard', () => {
    it('должен возвращать верхнюю карту колоды', () => {
      const topCard = handler.peekTopCard(mockState, playerId);
      expect(topCard).toBeDefined();
      expect(topCard?.cardId).toBe('card-1');
    });

    it('должен возвращать undefined когда колода пуста', () => {
      const deck = {
        cards: [],
        drawPile: [],
      };

      const newState = {
        ...mockState,
        decks: { ...mockState.decks, [playerId]: deck },
      };

      expect(handler.peekTopCard(newState, playerId)).toBeUndefined();
    });
  });

  describe('executeBlindBoost', () => {
    it('должен успешно выполнить Blind Boost для атаки', () => {
      const result = handler.executeBlindBoost(mockState, playerId, true);

      expect(result.success).toBe(true);
      expect(result.boostValue).toBe(2);
      expect(result.discardedCard).toBeDefined();
      expect(result.discardedCard?.cardId).toBe('card-1');
      expect(result.remainingDeck.length).toBe(1);
    });

    it('должен успешно выполнить Blind Boost для защиты', () => {
      const result = handler.executeBlindBoost(mockState, playerId, false);

      expect(result.success).toBe(true);
      expect(result.boostValue).toBe(2);
    });

    it('должен возвращать failure когда условие не выполнено', () => {
      // Меняем руку на 3 карты
      const handZone = {
        cards: [
          { ...createMockCard('hand-1', 'Card 1', 0), isVisible: true },
          { ...createMockCard('hand-2', 'Card 2', 0), isVisible: true },
          { ...createMockCard('hand-3', 'Card 3', 0), isVisible: true },
        ],
        maxSize: 5,
      };

      const newState = {
        ...mockState,
        handZones: { ...mockState.handZones, [playerId]: handZone },
      };

      const result = handler.executeBlindBoost(newState, playerId, true);

      expect(result.success).toBe(false);
      expect(result.boostValue).toBe(0);
      expect(result.discardedCard).toBeUndefined();
    });

    it('должен уменьшать колоду на 1 карту после Blind Boost', () => {
      const initialDeckSize = mockState.decks[playerId].drawPile.length;

      const result = handler.executeBlindBoost(mockState, playerId, true);

      expect(result.success).toBe(true);
      expect(result.remainingDeck.length).toBe(initialDeckSize - 1);
    });
  });

  describe('createBlindBoostModifier', () => {
    it('должен создавать модификатор для атаки', () => {
      const modifier = handler.createBlindBoostModifier(3, true);

      expect(modifier.type).toBe('add');
      expect(modifier.value).toBe(3);
      expect(modifier.source).toContain('daredevil');
      expect(modifier.appliesTo).toBe('attack');
    });

    it('должен создавать модификатор для защиты', () => {
      const modifier = handler.createBlindBoostModifier(2, false);

      expect(modifier.type).toBe('add');
      expect(modifier.value).toBe(2);
      expect(modifier.appliesTo).toBe('defense');
    });
  });

  describe('getConditionDescription', () => {
    it('должен возвращать описание условия', () => {
      const description = handler.getConditionDescription();
      expect(description).toContain('2');
      expect(description).toContain('карт');
    });
  });

  describe('canTriggerInCombat', () => {
    it('должен возвращать true когда isBlindBoostAvailable = true', () => {
      const context = {
        attackerId: 'fighter-daredevil',
        defenderId: 'fighter-enemy',
        isBlindBoostAvailable: true,
      };

      expect(handler.canTriggerInCombat(context)).toBe(true);
    });

    it('должен возвращать false когда isBlindBoostAvailable = false', () => {
      const context = {
        attackerId: 'fighter-daredevil',
        defenderId: 'fighter-enemy',
        isBlindBoostAvailable: false,
      };

      expect(handler.canTriggerInCombat(context)).toBe(false);
    });
  });
});
