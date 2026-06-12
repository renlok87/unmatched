/**
 * Deck Management Service
 *
 * Управление всеми операциями с картами:
 * - Вытягивание карт
 * - Сброс карт
 * - Перетасовка колоды
 * - Проверка лимитов руки
 */

import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { GameState } from '../models/game-state.model';
import { Card, HandCard, DeckState, HandZone } from '../models/card.model';

/**
 * Результат операции с колодой
 */
export interface DeckOperationResult {
  readonly success: boolean;
  readonly gameState: GameState;
  readonly drawnCards?: readonly Card[];
  readonly discardedCard?: Card;
  readonly error?: string;
}

/**
 * Fisher-Yates алгоритм перетасовки
 */
function shuffle<T>(array: readonly T[]): T[] {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

@Injectable()
export class DeckManagementService {
  private readonly logger = new Logger(DeckManagementService.name);

  // initializeDeck/createHeroCards удалены (A8): были заглушками с
  // hardcoded-картами; реальные колоды раздаёт GameInitializationService
  // из карт героя в БД (hero.cards × count)

  /**
   * Вытягивание указанного количества карт
   * @param state Текущее состояние
   * @param userId ID пользователя
   * @param count Количество карт для вытягивания
   * @returns Обновленное состояние
   */
  async drawCards(
    state: GameState,
    userId: string,
    count: number,
  ): Promise<GameState> {
    this.logger.debug(`Drawing ${count} cards for user ${userId}`);

    let deck = state.decks[userId];
    const handZone = state.handZones[userId];

    if (!deck || !handZone) {
      throw new NotFoundException(`Deck or hand zone not found for user ${userId}`);
    }

    let currentDrawPile = [...deck.drawPile];
    let currentHand = [...handZone.cards];
    let deckState = { ...deck };
    const drawnCards: Card[] = [];

    for (let i = 0; i < count; i++) {
      // Проверяем лимит руки
      if (currentHand.length >= handZone.maxSize) {
        this.logger.debug(`Hand is full (${currentHand.length}/${handZone.maxSize})`);
        break;
      }

      // Проверяем, нужно ли перетасовать сброс в колоду
      if (currentDrawPile.length === 0) {
        this.logger.debug('Draw pile empty, recycling discard pile');
        const recycleResult = await this.recycleDeck(state, userId);
        state = recycleResult;
        deck = state.decks[userId];
        currentDrawPile = [...deck.drawPile];

        if (currentDrawPile.length === 0) {
          this.logger.debug('No cards to draw after recycling');
          break;
        }
      }

      // Вытягиваем карту
      const card = currentDrawPile.shift()!;
      drawnCards.push(card);

      // Добавляем в руку (видимая для владельца)
      currentHand.push({
        ...card,
        isVisible: true,
      } as HandCard);
    }

    // Обновляем состояние колоды
    deckState = {
      ...deckState,
      drawPile: currentDrawPile,
      topCard: currentDrawPile[0],
    };

    // Обновляем зону руки
    const newHandZone: HandZone = {
      ...handZone,
      cards: currentHand,
    };

    return {
      ...state,
      decks: {
        ...state.decks,
        [userId]: deckState,
      },
      handZones: {
        ...state.handZones,
        [userId]: newHandZone,
      },
    };
  }

  /**
   * Сброс конкретной карты
   * @param state Текущее состояние
   * @param userId ID пользователя
   * @param cardInstanceId ID экземпляра карты
   * @returns Обновленное состояние
   */
  async discardCard(
    state: GameState,
    userId: string,
    cardInstanceId: string,
  ): Promise<GameState> {
    this.logger.debug(`Discarding card ${cardInstanceId} for user ${userId}`);

    const handZone = state.handZones[userId];
    if (!handZone) {
      throw new NotFoundException(`Hand zone not found for user ${userId}`);
    }

    // Находим карту в руке
    const cardIndex = handZone.cards.findIndex(c => c.id === cardInstanceId);
    if (cardIndex === -1) {
      throw new NotFoundException(`Card ${cardInstanceId} not found in hand`);
    }

    const card = handZone.cards[cardIndex];
    const newHand = handZone.cards.filter(c => c.id !== cardInstanceId);

    // Добавляем в сброс (скрыта от противника)
    const currentDiscard = state.discardPiles[userId] || [];
    const newDiscard = [
      ...currentDiscard,
      { ...card, isVisible: false },
    ];

    return {
      ...state,
      handZones: {
        ...state.handZones,
        [userId]: {
          ...handZone,
          cards: newHand,
        },
      },
      discardPiles: {
        ...state.discardPiles,
        [userId]: newDiscard,
      },
    };
  }

  /**
   * Сброс случайной карты (для действия Pass)
   * @param state Текущее состояние
   * @param userId ID пользователя
   * @returns Обновленное состояние с информацией о сброшенной карте
   */
  async discardRandomCard(
    state: GameState,
    userId: string,
  ): Promise<{ gameState: GameState; discardedCard: Card }> {
    this.logger.debug(`Discarding random card for user ${userId}`);

    const handZone = state.handZones[userId];
    if (!handZone || handZone.cards.length === 0) {
      throw new NotFoundException(`No cards in hand for user ${userId}`);
    }

    // Выбираем случайную карту
    const randomIndex = Math.floor(Math.random() * handZone.cards.length);
    const card = handZone.cards[randomIndex];

    const newState = await this.discardCard(state, userId, card.id);

    return {
      gameState: newState,
      discardedCard: card,
    };
  }

  /**
   * Перетасовка сброса в колоду
   * @param state Текущее состояние
   * @param userId ID пользователя
   * @returns Обновленное состояние
   */
  async recycleDeck(
    state: GameState,
    userId: string,
  ): Promise<GameState> {
    this.logger.debug(`Recycling deck for user ${userId}`);

    const discardPile = state.discardPiles[userId] || [];
    const deck = state.decks[userId];

    if (!deck) {
      throw new NotFoundException(`Deck not found for user ${userId}`);
    }

    if (discardPile.length === 0) {
      this.logger.debug('Discard pile is empty, nothing to recycle');
      return state;
    }

    // Перетасовываем сброс
    const shuffledDiscard = shuffle(discardPile);

    // Добавляем к текущей колоде
    const newDrawPile = [...shuffledDiscard, ...deck.drawPile];

    const newDeckState: DeckState = {
      ...deck,
      drawPile: newDrawPile,
      topCard: newDrawPile[0],
    };

    return {
      ...state,
      decks: {
        ...state.decks,
        [userId]: newDeckState,
      },
      discardPiles: {
        ...state.discardPiles,
        [userId]: [],
      },
    };
  }

  /**
   * Проверка необходимости перетасовки
   * @param state Текущее состояние
   * @param userId ID пользователя
   * @returns true, если колода пуста
   */
  shouldRecycleDeck(state: GameState, userId: string): boolean {
    const deck = state.decks[userId];
    return deck ? deck.drawPile.length === 0 : false;
  }

  /**
   * Получение количества карт в руке
   */
  getHandSize(state: GameState, userId: string): number {
    const handZone = state.handZones[userId];
    return handZone ? handZone.cards.length : 0;
  }

  /**
   * Проверка, может ли игрок вытянуть ещё карту
   */
  canDrawCard(state: GameState, userId: string): boolean {
    const handZone = state.handZones[userId];
    if (!handZone) return false;
    return handZone.cards.length < handZone.maxSize;
  }

}
