import type { CardInstance, CardDefinition } from './types';

/**
 * Card class - represents a single card in the game
 * Cards can be in hand, deck, discard pile, or in play (combat)
 */
export class Card {
  /**
   * Create a card instance from a definition
   */
  static createInstance(
    definition: CardDefinition,
    ownerId: string,
    instanceIndex: number
  ): CardInstance {
    return {
      id: `${definition.id}_${instanceIndex}`,
      definition,
      ownerId,
      instanceIndex,
      isBoosted: false,
      isFaceDown: false,
    };
  }

  /**
   * Create multiple instances for deck construction
   */
  static createDeck(
    definitions: CardDefinition[],
    ownerId: string
  ): CardInstance[] {
    const instances: CardInstance[] = [];
    let globalIndex = 0;

    for (const def of definitions) {
      for (let i = 0; i < def.quantity; i++) {
        instances.push(this.createInstance(def, ownerId, globalIndex++));
      }
    }

    return instances;
  }

  /**
   * Get the total value of a card including boosts
   */
  static getValue(card: CardInstance): number {
    const base = card.definition.value;
    const boost = card.boostValue || 0;
    return card.isBoosted ? base + boost : base;
  }

  /**
   * Check if a card can be used as an attack
   */
  static canAttack(card: CardInstance): boolean {
    return card.definition.type === 'attack' ||
           card.definition.type === 'versatile';
  }

  /**
   * Check if a card can be used as defense
   */
  static canDefend(card: CardInstance): boolean {
    return card.definition.type === 'defense' ||
           card.definition.type === 'versatile';
  }

  /**
   * Check if a card is a scheme card
   */
  static isScheme(card: CardInstance): boolean {
    return card.definition.type === 'scheme';
  }

  /**
   * Clone a card instance (for immutable state)
   */
  static clone(card: CardInstance): CardInstance {
    return { ...card };
  }

  /**
   * Create a face-down version of a card for combat
   */
  static playFaceDown(card: CardInstance): CardInstance {
    return {
      ...this.clone(card),
      isFaceDown: true,
    };
  }

  /**
   * Reveal a face-down card
   */
  static reveal(card: CardInstance): CardInstance {
    return {
      ...this.clone(card),
      isFaceDown: false,
    };
  }

  /**
   * Apply boost to a card
   */
  static boost(card: CardInstance, boostValue: number): CardInstance {
    return {
      ...this.clone(card),
      boostValue,
      isBoosted: true,
    };
  }

  /**
   * Reset card to base state
   */
  static reset(card: CardInstance): CardInstance {
    return {
      ...this.clone(card),
      boostValue: undefined,
      isBoosted: false,
      isFaceDown: false,
    };
  }
}
