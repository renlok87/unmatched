import type {
  GameState,
  GameSetup,
  Position,
} from '../models/types';
import { GamePhase } from '../models/types';
import { Card } from '../models/Card';
import { Deck } from '../models/Deck';
import { FighterModel } from '../models/Fighter';
import { BoardModel } from '../models/Board';
import { GameStateManager } from '../models/GameState';
import { MovementSystem } from './MovementSystem';
import { TurnManager } from './TurnManager';
import { CombatResolver } from './CombatResolver';
import { getHeroDefinition } from '../data/heroes';
import { getBoardDefinition } from '../data/boards';

/**
 * GameEngine - main controller for the Unmatched game
 * Orchestrates all game systems and enforces rules
 */
export class GameEngine {
  private movement: MovementSystem;
  private turns: TurnManager;
  private combat: CombatResolver;

  constructor() {
    this.movement = new MovementSystem();
    this.turns = new TurnManager();
    this.combat = new CombatResolver();
  }

  /**
   * Initialize a new game with the given setup
   */
  initializeGame(setup: GameSetup): GameState {
    const boardDef = getBoardDefinition(setup.boardId);
    const board = BoardModel.createBoard(boardDef);

    const players = setup.players.map((playerSetup, index) => {
      return this.createPlayer(playerSetup.id, playerSetup.name, playerSetup.heroId, board, index);
    });

    const gameState: GameState = {
      id: this.generateGameId(),
      players,
      board,
      currentTurn: {
        currentPlayerId: players[0].id,
        action1: undefined,
        action2: undefined,
        cardsDrawnThisTurn: 0,
      },
      phase: GamePhase.START_OF_TURN,
      combatState: null,
      winner: null,
      turnCount: 1,
    };

    // Start first player's turn
    return this.turns.startTurn(gameState);
  }

  /**
   * Create a player with hero, sidekicks, and deck
   */
  private createPlayer(
    id: string,
    name: string,
    heroId: string,
    board: any,
    playerIndex: number
  ) {
    const heroDef = getHeroDefinition(heroId);

    // Get starting position from board
    const startPosition = this.getStartingPosition(board, playerIndex);

    // Create hero fighter
    const hero = FighterModel.createHero(heroDef, id, startPosition);

    // Create sidekicks if applicable
    const sidekicks = FighterModel.createSidekicks(heroDef, id, startPosition);
    const fighters = [hero, ...sidekicks];

    // Create deck
    const deckCards = Card.createDeck(heroDef.deckCards, id);
    const shuffledDeck = Deck.create(deckCards);

    // Place fighters on board
    board.fighters.set(hero.id, startPosition);
    sidekicks.forEach(sk => {
      board.fighters.set(sk.id, startPosition);
    });

    // Draw starting hand (5 cards)
    const { drawn: hand, remaining: deck } = Deck.draw(shuffledDeck, 5);

    return {
      id,
      name,
      fighters,
      hand,
      discardPile: [],
      deck,
      actionsRemaining: 2,
      hasPassed: false,
      handLimit: 7,
    };
  }

  /**
   * Get starting position for a player
   */
  private getStartingPosition(board: any, playerIndex: number): Position {
    // Default starting positions - should be defined per board
    const defaults: Position[] = [
      { x: 0, y: 0 },
      { x: board.definition.width - 1, y: board.definition.height - 1 },
    ];
    return defaults[playerIndex] || { x: 0, y: 0 };
  }

  /**
   * Execute a Maneuver action: draw card and move
   */
  maneuver(state: GameState, fighterId: string): GameState {
    let newState = this.turns.maneuver(state, fighterId);
    return GameStateManager.setPhase(newState, GamePhase.MOVEMENT);
  }

  /**
   * Move a fighter to a new position
   */
  moveFighter(state: GameState, fighterId: string, position: Position): GameState {
    if (!this.movement.isValidMove(state, fighterId, position)) {
      throw new Error('Invalid move');
    }

    const fighter = GameStateManager.findFighter(state, fighterId);
    if (!fighter) return state;

    // Update fighter position
    const newFighter = FighterModel.move(fighter, position);
    let newState = GameStateManager.updateFighter(state, fighterId, {
      position: newFighter.position,
    });

    // Update board state
    const newBoard = BoardModel.setFighterPosition(newState.board, fighterId, position);
    newState = { ...newState, board: newBoard };

    // Return to action selection unless movement was from maneuver
    if (newState.phase === GamePhase.MOVEMENT) {
      newState = GameStateManager.setPhase(newState, GamePhase.ACTION_SELECTION);
    }

    return newState;
  }

  /**
   * Play a scheme card
   */
  playScheme(state: GameState, cardId: string): GameState {
    return this.turns.scheme(state, cardId);
  }

  /**
   * Initiate an attack
   */
  attack(state: GameState, attackerId: string, cardId: string, targetId: string): GameState {
    const currentPlayer = GameStateManager.getCurrentPlayer(state);
    if (!currentPlayer) return state;

    // Verify card is in hand
    const card = GameStateManager.findCardInHand(state, currentPlayer.id, cardId);
    if (!card || !Card.canAttack(card)) {
      throw new Error('Card cannot be used to attack');
    }

    // Verify target is valid
    if (!this.movement.canAttack(state, attackerId, targetId)) {
      throw new Error('Invalid attack target');
    }

    let newState = this.turns.attack(state, cardId, targetId);
    return this.combat.initiateAttack(newState, attackerId, cardId, targetId);
  }

  /**
   * Play a defense card during combat
   */
  defend(state: GameState, cardId: string): GameState {
    return this.combat.playDefense(state, cardId);
  }

  /**
   * Resolve the current combat
   */
  resolveCombat(state: GameState): GameState {
    return this.combat.resolve(state);
  }

  /**
   * End the current turn
   */
  endTurn(state: GameState): GameState {
    return this.turns.endTurn(state);
  }

  /**
   * Pass the turn without taking more actions
   */
  pass(state: GameState): GameState {
    return this.turns.pass(state);
  }

  // ============ Query Methods ============

  /**
   * Get valid moves for a fighter
   */
  getValidMoves(state: GameState, fighterId: string): Position[] {
    return this.movement.getValidMoves(state, fighterId);
  }

  /**
   * Get valid attack targets for a fighter
   */
  getValidTargets(state: GameState, attackerId: string): string[] {
    const attacker = GameStateManager.findFighter(state, attackerId);
    if (!attacker || attacker.isDefeated) return [];

    const validTargets: string[] = [];
    const allFighters = state.players.flatMap(p => p.fighters);

    for (const fighter of allFighters) {
      if (fighter.ownerId === attacker.ownerId) continue;
      if (fighter.isDefeated) continue;

      if (this.movement.canAttack(state, attackerId, fighter.id)) {
        validTargets.push(fighter.id);
      }
    }

    return validTargets;
  }

  /**
   * Check if an action is legal
   */
  isLegalAction(state: GameState, _action: string): boolean {
    return this.turns.canTakeAction(state);
  }

  /**
   * Get remaining actions for current turn
   */
  getRemainingActions(state: GameState): number {
    return this.turns.getRemainingActions(state);
  }

  /**
   * Generate unique game ID
   */
  private generateGameId(): string {
    return `game_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Get the MovementSystem instance (for UI interactions)
   */
  getMovementSystem(): MovementSystem {
    return this.movement;
  }

  /**
   * Get the CombatResolver instance (for UI interactions)
   */
  getCombatResolver(): CombatResolver {
    return this.combat;
  }
}
