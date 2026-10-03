import { GameInitializationService } from './game-initialization.service';
import { DeckManagementService } from '../../game-engine/services/deck-management.service';
import { GameStateService } from '../game-state.service';
import { marmorealBoardRow } from '../../test/fixtures/real-board';

describe('physical card instance identity', () => {
  it('keeps repeated cards unique across mirror decks, initial hands, draws and private views', async () => {
    const catalogCard = {
      id: 'catalog-scheme', name: 'Repeated Scheme', nameEn: 'Repeated Scheme',
      nameRu: 'Repeated Scheme', cardType: 'SCHEME', count: 6, effects: [],
    };
    const prisma = {
      // НД-2: the game starts on a real board (the default one), never on an empty 20x20 grid
      game: { findUnique: jest.fn().mockResolvedValue({ boardId: marmorealBoardRow().id }) },
      board: { findUnique: jest.fn().mockResolvedValue(marmorealBoardRow()) },
      gamePlayer: { findMany: jest.fn().mockResolvedValue([
        { userId: 'first', heroId: 'shared-hero', seatOrder: 0 },
        { userId: 'second', heroId: 'shared-hero', seatOrder: 1 },
      ]) },
      hero: { findUnique: jest.fn().mockResolvedValue({
        id: 'shared-hero', name: 'Mirror Hero', health: 10, movement: 2,
        sidekicks: [], cards: [catalogCard],
      }) },
    };
    const saveState = jest.fn();
    const initializer = new GameInitializationService(prisma as any, { saveState } as any);
    const projection = new GameStateService({} as any, {} as any, {} as any);
    const deck = new DeckManagementService();
    const initial = await initializer.initializeGameState('mirror-game');
    expect(saveState).toHaveBeenCalledWith('mirror-game', initial);

    const physicalCards = (state: typeof initial) =>
      ['first', 'second'].flatMap((owner) => [
        ...state.handZones[owner].cards,
        ...state.decks[owner].drawPile,
      ]);
    const initialIds = physicalCards(initial).map((card) => card.id);
    expect(initialIds).toHaveLength(12);
    expect(new Set(initialIds).size).toBe(initialIds.length);
    expect(physicalCards(initial).every((card) => card.cardId === catalogCard.id)).toBe(true);
    expect(initial.decks.first.cards.map((card) => card.id).sort()).toEqual(
      physicalCards(initial).slice(0, 6).map((card) => card.id).sort(),
    );

    let drawn = await deck.drawCards(initial, 'first', 1);
    drawn = await deck.drawCards(drawn, 'second', 1);
    expect(drawn.decks.first.drawPile).toHaveLength(0);
    expect(drawn.decks.second.drawPile).toHaveLength(0);
    expect(physicalCards(drawn).map((card) => card.id).sort()).toEqual([...initialIds].sort());
    expect(new Set(physicalCards(drawn).map((card) => card.id)).size).toBe(12);

    for (const [viewer, opponent] of [['first', 'second'], ['second', 'first']]) {
      const view = projection.filterPrivateData(drawn, viewer);
      expect(view.handZones[viewer].cards.map((card) => card.id)).toEqual(
        drawn.handZones[viewer].cards.map((card) => card.id),
      );
      expect(view.handZones[opponent].cards).toHaveLength(6);
      expect(view.handZones[opponent].cards.every((card) => card.cardId === 'hidden')).toBe(true);
      expect(view.decks[opponent].cards.every((card) => card.cardId === 'hidden')).toBe(true);
      for (const card of drawn.handZones[opponent].cards) {
        expect(view.handZones[opponent].cards.some((projected) => projected.id === card.id)).toBe(false);
      }
    }
  });
});
