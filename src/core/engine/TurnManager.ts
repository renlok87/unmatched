import type { GameState, ActionType } from '../models/types';
import { GamePhase } from '../models/types';
import { GameStateManager } from '../models/GameState';
import { Deck } from '../models/Deck';

/**
 * TurnManager - manages turn phases and actions
 * In Unmatched, each turn consists of 2 actions chosen from:
 * - Maneuver: Draw a card and move
 * - Scheme: Play a scheme card
 * - Attack: Play an attack card
 */
export class TurnManager {
  /**
   * Start a new turn for the current player
   */
  startTurn(state: GameState): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    let newState = state;

    // Process start-of-turn abilities
    newState = this.processStartOfTurnAbilities(newState);

    // Set phase to action selection
    newState = GameStateManager.setPhase(newState, GamePhase.ACTION_SELECTION);

    return newState;
  }

  /**
   * Record an action being taken
   */
  takeAction(state: GameState, action: ActionType): GameState {
    const turn = { ...state.currentTurn };

    if (turn.action1 === undefined) {
      turn.action1 = action;
    } else if (turn.action2 === undefined) {
      turn.action2 = action;
    } else {
      throw new Error('No actions remaining this turn');
    }

    return {
      ...state,
      currentTurn: turn,
    };
  }

  /**
   * Perform a Maneuver action: draw a card and optionally move
   */
  maneuver(state: GameState, fighterId?: string): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    // Draw a card
    let newState = this.drawCard(state);

    // Record the action
    newState = this.takeAction(newState, 'maneuver');

    // If fighter specified, enter movement phase
    if (fighterId) {
      newState = {
        ...newState,
        phase: 'movement' as GamePhase,
      };
    }

    return newState;
  }

  /**
   * Perform a Scheme action: play a scheme card
   */
  scheme(state: GameState, _cardId: string): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    // Record the action
    let newState = this.takeAction(state, 'scheme');

    // Process the scheme card
    // TODO: Implement scheme card processing

    return newState;
  }

  /**
   * Perform an Attack action: play an attack card
   */
  attack(state: GameState, _cardId: string, _targetId: string): GameState {
    // Record the action
    let newState = this.takeAction(state, 'attack');

    // Enter combat phase
    newState = GameStateManager.setPhase(newState, GamePhase.COMBAT);

    // TODO: Set up combat state

    return newState;
  }

  /**
   * Draw a card for the current player
   */
  drawCard(state: GameState): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    if (currentPlayer.deck.length === 0) {
      // Deck exhausted - recycle discard pile
      return this.recycleDeck(state);
    }

    const { card, remaining } = Deck.drawOne(currentPlayer.deck);

    if (!card) {
      return state; // No card available
    }

    const newHand = [...currentPlayer.hand, card];

    return GameStateManager.updatePlayer(state, currentPlayer.id, {
      deck: remaining,
      hand: newHand,
    });
  }

  /**
   * Recycle discard pile into deck
   */
  recycleDeck(state: GameState): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    if (currentPlayer.discardPile.length === 0) {
      // No cards to recycle - player takes exhaustion damage
      return this.applyExhaustionDamage(state);
    }

    const newDeck = Deck.shuffle([...currentPlayer.discardPile]);
    return GameStateManager.updatePlayer(state, currentPlayer.id, {
      deck: newDeck,
      discardPile: [],
    });
  }

  /**
   * Apply damage when deck is exhausted
   */
  applyExhaustionDamage(state: GameState): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    // Deal 1 damage to the hero
    const hero = currentPlayer.fighters.find(f => f.type === 'hero');
    if (!hero) return state;

    // TODO: Implement damage application
    return state;
  }

  /**
   * End the current turn
   */
  endTurn(state: GameState): GameState {
    let newState = state;

    // Process end-of-turn abilities
    newState = this.processEndOfTurnAbilities(newState);

    // Discard down to hand limit
    newState = this.discardToHandLimit(newState);

    // Move to next player
    newState = GameStateManager.nextTurn(newState);

    // Start the new turn
    newState = this.startTurn(newState);

    return newState;
  }

  /**
   * Discard cards down to hand limit
   */
  discardToHandLimit(state: GameState): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    if (currentPlayer.hand.length <= currentPlayer.handLimit) {
      return state;
    }

    // TODO: Implement card selection for discarding
    // For now, discard from the end
    const newHand = currentPlayer.hand.slice(0, currentPlayer.handLimit);
    const newDiscard = [
      ...currentPlayer.discardPile,
      ...currentPlayer.hand.slice(currentPlayer.handLimit),
    ];

    return GameStateManager.updatePlayer(state, currentPlayer.id, {
      hand: newHand,
      discardPile: newDiscard,
    });
  }

  /**
   * Pass the turn (take no further actions)
   */
  pass(state: GameState): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    const newPlayer = { ...currentPlayer, hasPassed: true };
    const newState = GameStateManager.updatePlayer(state, currentPlayer.id, newPlayer);

    // Check if all players have passed
    const allPassed = newState.players.every(p => p.hasPassed);

    if (allPassed) {
      // End the round
      return this.endTurn(newState);
    }

    return newState;
  }

  /**
   * Process start-of-turn abilities
   */
  private processStartOfTurnAbilities(state: GameState): GameState {
    // TODO: Implement ability processing
    // Ms. Marvel: Move 1 space at start of turn
    return state;
  }

  /**
   * Process end-of-turn abilities
   */
  private processEndOfTurnAbilities(state: GameState): GameState {
    // TODO: Implement ability processing
    return state;
  }

  /**
   * Check if player can take an action
   */
  canTakeAction(state: GameState): boolean {
    return GameStateManager.canPerformAction(state);
  }

  /**
   * Get remaining actions for current turn
   */
  getRemainingActions(state: GameState): number {
    return GameStateManager.getRemainingActions(state);
  }
}
