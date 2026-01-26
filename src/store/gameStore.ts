import { create } from 'zustand';
import type {
  GameState,
  GameSetup,
  Position,
  GamePhase,
} from '../core/models/types';
import { GameEngine } from '../core/engine/GameEngine';
import { getDefaultBoardId } from '../core/data/boards';

interface GameStoreState {
  // Core game state
  gameState: GameState | null;

  // UI selection state
  selectedFighterId: string | null;
  selectedCardId: string | null;
  highlightedSpaces: Position[];

  // Actions
  initializeGame: (setup?: GameSetup) => void;
  selectFighter: (fighterId: string | null) => void;
  selectCard: (cardId: string | null) => void;
  maneuver: (fighterId: string) => void;
  moveFighter: (fighterId: string, position: Position) => void;
  attack: (attackerId: string, cardId: string, targetId: string) => void;
  defend: (cardId: string) => void;
  resolveCombat: () => void;
  endTurn: () => void;
  pass: () => void;

  // Getters (derived state)
  getCurrentPlayer: () => ReturnType<typeof getCurrentPlayer>;
  getCurrentPhase: () => GamePhase;
  getValidMoves: (fighterId: string) => Position[];
  getValidTargets: (attackerId: string) => string[];
  getRemainingActions: () => number;
  canPlayCard: (cardId: string) => boolean;
}

const engine = new GameEngine();

const getCurrentPlayer = (state: GameState | null) => {
  if (!state) return undefined;
  return state.players.find(p => p.id === state.currentTurn.currentPlayerId);
};

export const useGameStore = create<GameStoreState>((set, get) => ({
  gameState: null,
  selectedFighterId: null,
  selectedCardId: null,
  highlightedSpaces: [],

  initializeGame: (setup) => {
    const defaultSetup: GameSetup = setup || {
      players: [
        { id: 'player1', name: 'Player 1', heroId: 'ms-marvel' },
        { id: 'player2', name: 'Player 2', heroId: 'daredevil' },
      ],
      boardId: getDefaultBoardId(),
    };

    const newState = engine.initializeGame(defaultSetup);
    set({
      gameState: newState,
      selectedFighterId: null,
      selectedCardId: null,
      highlightedSpaces: [],
    });
  },

  selectFighter: (fighterId) => {
    const { gameState } = get();
    if (!gameState) return;

    set({ selectedFighterId: fighterId });

    // Highlight valid moves if fighter selected
    if (fighterId) {
      const moves = engine.getValidMoves(gameState, fighterId);
      set({ highlightedSpaces: moves });
    } else {
      set({ highlightedSpaces: [] });
    }
  },

  selectCard: (cardId) => {
    set({ selectedCardId: cardId });
  },

  maneuver: (fighterId) => {
    const { gameState } = get();
    if (!gameState) return;

    try {
      const newState = engine.maneuver(gameState, fighterId);
      set({ gameState: newState, selectedFighterId: fighterId });
    } catch (error) {
      console.error('Maneuver failed:', error);
    }
  },

  moveFighter: (fighterId, position) => {
    const { gameState } = get();
    if (!gameState) return;

    try {
      const newState = engine.moveFighter(gameState, fighterId, position);
      set({ gameState: newState, highlightedSpaces: [] });
    } catch (error) {
      console.error('Move failed:', error);
    }
  },

  attack: (attackerId, cardId, targetId) => {
    const { gameState } = get();
    if (!gameState) return;

    try {
      const newState = engine.attack(gameState, attackerId, cardId, targetId);
      set({ gameState: newState, selectedCardId: null });
    } catch (error) {
      console.error('Attack failed:', error);
    }
  },

  defend: (cardId) => {
    const { gameState } = get();
    if (!gameState) return;

    try {
      const newState = engine.defend(gameState, cardId);
      set({ gameState: newState });
    } catch (error) {
      console.error('Defend failed:', error);
    }
  },

  resolveCombat: () => {
    const { gameState } = get();
    if (!gameState) return;

    try {
      const newState = engine.resolveCombat(gameState);
      set({
        gameState: newState,
        selectedCardId: null,
        selectedFighterId: null,
      });
    } catch (error) {
      console.error('Resolve combat failed:', error);
    }
  },

  endTurn: () => {
    const { gameState } = get();
    if (!gameState) return;

    try {
      const newState = engine.endTurn(gameState);
      set({
        gameState: newState,
        selectedCardId: null,
        selectedFighterId: null,
        highlightedSpaces: [],
      });
    } catch (error) {
      console.error('End turn failed:', error);
    }
  },

  pass: () => {
    const { gameState } = get();
    if (!gameState) return;

    try {
      const newState = engine.pass(gameState);
      set({ gameState: newState });
    } catch (error) {
      console.error('Pass failed:', error);
    }
  },

  getCurrentPlayer: () => {
    return getCurrentPlayer(get().gameState);
  },

  getCurrentPhase: () => {
    return get().gameState?.phase || 'setup' as GamePhase;
  },

  getValidMoves: (fighterId) => {
    const { gameState } = get();
    if (!gameState) return [];
    return engine.getValidMoves(gameState, fighterId);
  },

  getValidTargets: (attackerId) => {
    const { gameState } = get();
    if (!gameState) return [];
    return engine.getValidTargets(gameState, attackerId);
  },

  canPlayCard: (cardId) => {
    const { gameState } = get();
    if (!gameState) return false;
    const player = getCurrentPlayer(gameState);
    if (!player) return false;
    return player.hand.some(c => c.id === cardId);
  },

  getRemainingActions: () => {
    const { gameState } = get();
    if (!gameState) return 0;
    let count = 0;
    if (!gameState.currentTurn.action1) count++;
    if (!gameState.currentTurn.action2) count++;
    return count;
  },
}));
