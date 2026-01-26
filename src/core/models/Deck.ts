import type { CardInstance } from './types';

/**
 * Deck class - manages a deck of cards
 */
export class Deck {
  /**
   * Shuffle an array of cards using Fisher-Yates algorithm
   */
  static shuffle(cards: CardInstance[]): CardInstance[] {
    const shuffled = [...cards];
    let currentIndex = shuffled.length;
    let randomIndex: number;

    // While there remain elements to shuffle
    while (currentIndex !== 0) {
      // Pick a remaining element
      randomIndex = Math.floor(Math.random() * currentIndex);
      currentIndex--;

      // Swap with current element
      [shuffled[currentIndex], shuffled[randomIndex]] = [
        shuffled[randomIndex],
        shuffled[currentIndex],
      ];
    }

    return shuffled;
  }

  /**
   * Draw cards from the deck
   * Returns { drawn, remaining }
   */
  static draw(deck: CardInstance[], count: number): {
    drawn: CardInstance[];
    remaining: CardInstance[];
  } {
    if (count <= 0) {
      return { drawn: [], remaining: deck };
    }

    const drawn = deck.slice(0, count);
    const remaining = deck.slice(count);

    return { drawn, remaining };
  }

  /**
   * Draw a single card
   */
  static drawOne(deck: CardInstance[]): {
    card: CardInstance | null;
    remaining: CardInstance[];
  } {
    if (deck.length === 0) {
      return { card: null, remaining: deck };
    }

    const [card, ...remaining] = deck;
    return { card, remaining };
  }

  /**
   * Add cards to the bottom of the deck
   */
  static addToBottom(deck: CardInstance[], cards: CardInstance[]): CardInstance[] {
    return [...deck, ...cards];
  }

  /**
   * Add cards to the top of the deck
   */
  static addToTop(deck: CardInstance[], cards: CardInstance[]): CardInstance[] {
    return [...cards, ...deck];
  }

  /**
   * Move a card from hand to discard pile
   */
  static discard(hand: CardInstance[], cardId: string): {
    hand: CardInstance[];
    discarded: CardInstance;
  } {
    const cardIndex = hand.findIndex(c => c.id === cardId);

    if (cardIndex === -1) {
      throw new Error(`Card ${cardId} not found in hand`);
    }

    const card = hand[cardIndex];
    const newHand = hand.filter((_, i) => i !== cardIndex);

    return { hand: newHand, discarded: card };
  }

  /**
   * Discard multiple cards
   */
  static discardMultiple(
    hand: CardInstance[],
    cardIds: string[]
  ): { hand: CardInstance[]; discarded: CardInstance[] } {
    const toDiscard = new Set(cardIds);
    const discarded: CardInstance[] = [];
    const newHand: CardInstance[] = [];

    for (const card of hand) {
      if (toDiscard.has(card.id)) {
        discarded.push(card);
      } else {
        newHand.push(card);
      }
    }

    return { hand: newHand, discarded };
  }

  /**
   * Shuffle discard pile into deck
   */
  static recycleDiscard(
    deck: CardInstance[],
    discard: CardInstance[]
  ): CardInstance[] {
    if (discard.length === 0) {
      return deck;
    }

    return this.shuffle([...deck, ...discard]);
  }

  /**
   * Count cards by type
   */
  static countByType(
    cards: CardInstance[],
    type: string
  ): number {
    return cards.filter(c => c.definition.type === type).length;
  }

  /**
   * Get total value of all cards in hand/deck
   */
  static getTotalValue(cards: CardInstance[]): number {
    return cards.reduce((sum, card) => sum + card.definition.value, 0);
  }

  /**
   * Find a card by ID
   */
  static findById(cards: CardInstance[], cardId: string): CardInstance | undefined {
    return cards.find(c => c.id === cardId);
  }

  /**
   * Check if deck is empty
   */
  static isEmpty(deck: CardInstance[]): boolean {
    return deck.length === 0;
  }

  /**
   * Create a deck from card definitions
   */
  static create(cards: CardInstance[]): CardInstance[] {
    return this.shuffle(cards);
  }
}
