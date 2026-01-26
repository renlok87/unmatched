import type {
  GameState,
  GameSetup,
  Player,
  Fighter,
  GamePhase,
  CardInstance,
} from './types';
import { BoardModel } from './Board';
import { FighterModel } from './Fighter';

/**
 * GameState class - manages immutable game state
 */
export class GameStateManager {
  /**
   * Create a new game state from setup
   */
  static createGame(setup: GameSetup): GameState {
    return {
      id: this.generateGameId(),
      players: [], // Will be populated by initializeGame
      board: {
        definition: {} as any,
        fighters: new Map(),
      },
      currentTurn: {
        currentPlayerId: setup.players[0]?.id || '',
        action1: undefined,
        action2: undefined,
        cardsDrawnThisTurn: 0,
      },
      phase: 'setup' as GamePhase,
      combatState: null,
      winner: null,
      turnCount: 1,
    };
  }

  /**
   * Create a player from hero definition
   */
  static createPlayer(
    id: string,
    name: string,
    fighters: Fighter[],
    deck: CardInstance[],
    handLimit: number = 7
  ): Player {
    // Draw starting hand (typically 5 cards)
    const { drawn: hand, remaining: deckCards } = this.drawStartingHand(deck, 5);

    return {
      id,
      name,
      fighters,
      hand,
      discardPile: [],
      deck: deckCards,
      actionsRemaining: 2,
      hasPassed: false,
      handLimit,
    };
  }

  /**
   * Draw starting hand from deck
   */
  static drawStartingHand(deck: CardInstance[], count: number): {
    drawn: CardInstance[];
    remaining: CardInstance[];
  } {
    const drawn = deck.slice(0, count);
    const remaining = deck.slice(count);

    return { drawn, remaining };
  }

  /**
   * Get the current player
   */
  static getCurrentPlayer(state: GameState): Player | undefined {
    return state.players.find(
      p => p.id === state.currentTurn.currentPlayerId
    );
  }

  /**
   * Get the opponent player
   */
  static getOpponent(state: GameState, playerId: string): Player | undefined {
    return state.players.find(p => p.id !== playerId);
  }

  /**
   * Get all alive fighters for a player
   */
  static getAliveFighters(state: GameState, playerId: string): Fighter[] {
    const player = state.players.find(p => p.id === playerId);
    if (!player) return [];

    return FighterModel.getAliveFighters(player.fighters);
  }

  /**
   * Check if a player has lost (all fighters defeated)
   */
  static isPlayerDefeated(state: GameState, playerId: string): boolean {
    const player = state.players.find(p => p.id === playerId);
    if (!player) return true;

    return FighterModel.isAllDefeated(player.fighters);
  }

  /**
   * Check for game over condition
   */
  static checkGameOver(state: GameState): string | null {
    // Check if only one player has alive fighters
    const alivePlayers = state.players.filter(p =>
      !FighterModel.isAllDefeated(p.fighters)
    );

    if (alivePlayers.length <= 1) {
      return alivePlayers[0]?.id || null;
    }

    return null;
  }

  /**
   * Advance to next turn
   */
  static nextTurn(state: GameState): GameState {
    const currentPlayerIndex = state.players.findIndex(
      p => p.id === state.currentTurn.currentPlayerId
    );

    const nextPlayerIndex = (currentPlayerIndex + 1) % state.players.length;
    const nextPlayerId = state.players[nextPlayerIndex].id;

    const newTurnCount =
      nextPlayerIndex === 0 ? state.turnCount + 1 : state.turnCount;

    return {
      ...state,
      currentTurn: {
        currentPlayerId: nextPlayerId,
        action1: undefined,
        action2: undefined,
        cardsDrawnThisTurn: 0,
        selectedCard: undefined,
        selectedTarget: undefined,
      },
      turnCount: newTurnCount,
      phase: 'start_of_turn' as GamePhase,
    };
  }

  /**
   * Clone game state (deep clone)
   */
  static clone(state: GameState): GameState {
    return {
      ...state,
      players: state.players.map(p => ({
        ...p,
        hand: p.hand.map(c => ({ ...c })),
        discardPile: p.discardPile.map(c => ({ ...c })),
        deck: p.deck.map(c => ({ ...c })),
        fighters: p.fighters.map(f => ({
          ...f,
          position: { ...f.position },
        })),
      })),
      board: BoardModel.clone(state.board),
      currentTurn: { ...state.currentTurn },
      combatState: state.combatState ? {
        ...state.combatState,
        attacker: { ...state.combatState.attacker, position: { ...state.combatState.attacker.position } },
        defender: { ...state.combatState.defender, position: { ...state.combatState.defender.position } },
        attackCard: { ...state.combatState.attackCard },
        defenseCard: state.combatState.defenseCard ? { ...state.combatState.defenseCard } : undefined,
      } : null,
    };
  }

  /**
   * Find a fighter by ID across all players
   */
  static findFighter(state: GameState, fighterId: string): Fighter | undefined {
    for (const player of state.players) {
      const fighter = player.fighters.find(f => f.id === fighterId);
      if (fighter) return fighter;
    }
    return undefined;
  }

  /**
   * Find a card by ID in a player's hand
   */
  static findCardInHand(state: GameState, playerId: string, cardId: string): CardInstance | undefined {
    const player = state.players.find(p => p.id === playerId);
    return player?.hand.find(c => c.id === cardId);
  }

  /**
   * Update a player in the state
   */
  static updatePlayer(state: GameState, playerId: string, updates: Partial<Player>): GameState {
    return {
      ...state,
      players: state.players.map(p =>
        p.id === playerId ? { ...p, ...updates } : p
      ),
    };
  }

  /**
   * Update a fighter in the state
   */
  static updateFighter(state: GameState, fighterId: string, updates: Partial<Fighter>): GameState {
    return {
      ...state,
      players: state.players.map(p => ({
        ...p,
        fighters: p.fighters.map(f =>
          f.id === fighterId ? { ...f, ...updates } : f
        ),
      })),
    };
  }

  /**
   * Generate a unique game ID
   */
  private static generateGameId(): string {
    return `game_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Check if a fighter can perform an action
   */
  static canPerformAction(state: GameState): boolean {
    return state.currentTurn.action1 === undefined ||
           state.currentTurn.action2 === undefined;
  }

  /**
   * Get remaining actions for current turn
   */
  static getRemainingActions(state: GameState): number {
    let count = 0;
    if (state.currentTurn.action1 === undefined) count++;
    if (state.currentTurn.action2 === undefined) count++;
    return count;
  }

  /**
   * Set the game phase
   */
  static setPhase(state: GameState, phase: GamePhase): GameState {
    return { ...state, phase };
  }

  /**
   * Set the winner
   */
  static setWinner(state: GameState, winnerId: string | null): GameState {
    return {
      ...state,
      winner: winnerId,
      phase: winnerId ? ('game_over' as GamePhase) : state.phase,
    };
  }
}
