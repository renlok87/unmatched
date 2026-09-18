/**
 * Deck Management Service Tests
 *
 * Юниты drawCards/discardCard/discardRandomCard/recycleDeck.
 * Колоды — фикстурные (initializeDeck удалён в A8: реальные колоды
 * раздаёт GameInitializationService из карт героя в БД).
 */

import { Test, TestingModule } from '@nestjs/testing';
import { DeckManagementService } from './deck-management.service';
import { GamePhase } from '../models/game-state.model';
import { CardType, createEmptyBoardState } from '../models';
import type { Card, GameState } from '../models';

const fixtureCard = (i: number): Card => ({
  id: `card-${i}`,
  cardId: `card-${i}`,
  name: `Card ${i}`,
  nameEn: `Card ${i}`,
  nameRu: `Карта ${i}`,
  cardType: CardType.ATTACK,
  attackValue: i,
  boostValue: 1,
});

/** Фикстурная колода n карт + пустая рука maxSize 5 */
const withDeck = (state: GameState, playerId: string, n: number): GameState => {
  const cards = Array.from({ length: n }, (_, i) => fixtureCard(i));
  return {
    ...state,
    decks: {
      ...state.decks,
      [playerId]: { cards, drawPile: [...cards], topCard: cards[0] },
    },
    discardPiles: { ...state.discardPiles, [playerId]: [] },
    handZones: { ...state.handZones, [playerId]: { cards: [], maxSize: 5 } },
  };
};

describe('DeckManagementService', () => {
  let service: DeckManagementService;
  let mockState: GameState;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [DeckManagementService],
    }).compile();

    service = module.get<DeckManagementService>(DeckManagementService);

    mockState = {
      gameId: 'test-game-1',
      sequenceNumber: 0,
      phase: GamePhase.SETUP,
      turnCount: 0,
      currentTurnPlayerId: 'player-1',
      players: [
        {
          userId: 'player-1',
          heroId: 'daredevil',
          health: 10,
          maxHealth: 10,
          fighterIds: ['fighter-1'],
          isAlive: true,
        },
        {
          userId: 'player-2',
          heroId: 'ms-marvel',
          health: 10,
          maxHealth: 10,
          fighterIds: ['fighter-2'],
          isAlive: true,
        },
      ],
      fighters: [],
      decks: {},
      discardPiles: {},
      handZones: {},
      boardState: createEmptyBoardState(5, 5),
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: 'system',
        version: 1,
      },
    };
  });

  describe('drawCards', () => {
    beforeEach(() => {
      mockState = withDeck(mockState, 'player-1', 15);
    });

    it('should draw the specified number of cards', async () => {
      const result = await service.drawCards(mockState, 'player-1', 3);

      expect(result.handZones['player-1'].cards.length).toBe(3);
      expect(result.decks['player-1'].drawPile.length).toBe(
        mockState.decks['player-1'].drawPile.length - 3,
      );
    });

    it('should allow draws beyond the end-of-turn hand size limit', async () => {
      const result = await service.drawCards(mockState, 'player-1', 10);

      expect(result.handZones['player-1'].cards.length).toBe(10);
      expect(result.decks['player-1'].drawPile.length).toBe(5);
    });

    it('should mark drawn cards as visible', async () => {
      const result = await service.drawCards(mockState, 'player-1', 2);

      result.handZones['player-1'].cards.forEach((card) => {
        expect(card.isVisible).toBe(true);
      });
    });

    it('should signal recycle when draw pile is empty', async () => {
      let state = withDeck(mockState, 'player-1', 3);
      state = await service.drawCards(state, 'player-1', 3);
      for (const card of [...state.handZones['player-1'].cards]) {
        state = await service.discardCard(state, 'player-1', card.id);
      }

      expect(service.shouldRecycleDeck(state, 'player-1')).toBe(true);
    });
  });

  describe('discardCard', () => {
    beforeEach(async () => {
      mockState = withDeck(mockState, 'player-1', 15);
      mockState = await service.drawCards(mockState, 'player-1', 3);
    });

    it('should remove card from hand', async () => {
      const cardToDiscard = mockState.handZones['player-1'].cards[0];
      const result = await service.discardCard(mockState, 'player-1', cardToDiscard.id);

      expect(result.handZones['player-1'].cards.length).toBe(2);
      expect(
        result.handZones['player-1'].cards.find((c) => c.id === cardToDiscard.id),
      ).toBeUndefined();
    });

    it('should add card to discard pile', async () => {
      const cardToDiscard = mockState.handZones['player-1'].cards[0];
      const result = await service.discardCard(mockState, 'player-1', cardToDiscard.id);

      expect(result.discardPiles['player-1']).toBeDefined();
      expect(result.discardPiles['player-1'].length).toBe(1);
      expect(result.discardPiles['player-1'][0].id).toBe(cardToDiscard.id);
    });

    it('should mark discarded card as not visible', async () => {
      const cardToDiscard = mockState.handZones['player-1'].cards[0];
      const result = await service.discardCard(mockState, 'player-1', cardToDiscard.id);

      expect((result.discardPiles['player-1'][0] as { isVisible?: boolean }).isVisible).toBe(
        false,
      );
    });
  });

  describe('discardRandomCard', () => {
    beforeEach(async () => {
      mockState = withDeck(mockState, 'player-1', 15);
      mockState = await service.drawCards(mockState, 'player-1', 3);
    });

    it('should discard a random card from hand', async () => {
      const initialHandSize = mockState.handZones['player-1'].cards.length;
      const result = await service.discardRandomCard(mockState, 'player-1');

      expect(result.gameState.handZones['player-1'].cards.length).toBe(initialHandSize - 1);
      expect(result.discardedCard).toBeDefined();
    });

    it('should throw if hand is empty', async () => {
      const emptyState = {
        ...mockState,
        handZones: {
          ...mockState.handZones,
          'player-1': { ...mockState.handZones['player-1'], cards: [] },
        },
      };

      await expect(service.discardRandomCard(emptyState, 'player-1')).rejects.toThrow();
    });
  });

  describe('recycleDeck', () => {
    beforeEach(async () => {
      mockState = withDeck(mockState, 'player-1', 15);
      mockState = await service.drawCards(mockState, 'player-1', 3);
      const cardToDiscard = mockState.handZones['player-1'].cards[0];
      mockState = await service.discardCard(mockState, 'player-1', cardToDiscard.id);
    });

    it('should shuffle discard pile into draw pile', async () => {
      const result = await service.recycleDeck(mockState, 'player-1');

      expect(result.discardPiles['player-1'].length).toBe(0);
      expect(result.decks['player-1'].drawPile.length).toBeGreaterThan(
        mockState.decks['player-1'].drawPile.length,
      );
    });

    it('should clear discard pile after recycling', async () => {
      const result = await service.recycleDeck(mockState, 'player-1');

      expect(result.discardPiles['player-1']).toEqual([]);
    });
  });

  describe('shouldRecycleDeck', () => {
    it('should return true when draw pile is empty', () => {
      mockState = withDeck(mockState, 'player-1', 5);
      mockState = {
        ...mockState,
        decks: {
          ...mockState.decks,
          'player-1': { ...mockState.decks['player-1'], drawPile: [] },
        },
      };

      expect(service.shouldRecycleDeck(mockState, 'player-1')).toBe(true);
    });

    it('should return false when draw pile has cards', () => {
      mockState = withDeck(mockState, 'player-1', 5);

      expect(service.shouldRecycleDeck(mockState, 'player-1')).toBe(false);
    });
  });

  describe('getHandSize', () => {
    it('should return the number of cards in hand', async () => {
      mockState = withDeck(mockState, 'player-1', 15);
      mockState = await service.drawCards(mockState, 'player-1', 3);

      expect(service.getHandSize(mockState, 'player-1')).toBe(3);
    });

    it('should return 0 for non-existent hand', () => {
      expect(service.getHandSize(mockState, 'unknown-player')).toBe(0);
    });
  });

  describe('canDrawCard', () => {
    beforeEach(() => {
      mockState = withDeck(mockState, 'player-1', 15);
    });

    it('should return true when hand is not full', async () => {
      mockState = await service.drawCards(mockState, 'player-1', 3);

      expect(service.canDrawCard(mockState, 'player-1')).toBe(true);
    });

    it('should permit a required draw when hand is full', async () => {
      mockState = await service.drawCards(mockState, 'player-1', 5);

      expect(service.canDrawCard(mockState, 'player-1')).toBe(true);
    });

    it('should return false for non-existent hand', () => {
      expect(service.canDrawCard(mockState, 'unknown-player')).toBe(false);
    });
  });
});
