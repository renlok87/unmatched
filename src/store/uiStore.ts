import { create } from 'zustand';
import type { CardInstance } from '../core/models/types';

interface GameLogEntry {
  id: string;
  timestamp: number;
  type: 'combat' | 'movement' | 'card_play' | 'effect' | 'system' | 'turn';
  message: string;
  details?: unknown;
}

interface UIStoreState {
  // Modal states
  showCombatModal: boolean;
  showCardPreview: boolean;
  showGameLog: boolean;
  showHeroSelect: boolean;

  // Card preview
  previewCard: CardInstance | null;

  // Game log
  gameLog: GameLogEntry[];

  // Loading states
  isProcessing: boolean;

  // Actions
  openCombatModal: () => void;
  closeCombatModal: () => void;
  setCardPreview: (card: CardInstance | null) => void;
  toggleGameLog: () => void;
  addLogEntry: (entry: Omit<GameLogEntry, 'id' | 'timestamp'>) => void;
  clearLog: () => void;
  setProcessing: (processing: boolean) => void;
  openHeroSelect: () => void;
  closeHeroSelect: () => void;
}

export const useUIStore = create<UIStoreState>((set) => ({
  showCombatModal: false,
  showCardPreview: false,
  showGameLog: false,
  showHeroSelect: false,
  previewCard: null,
  gameLog: [],
  isProcessing: false,

  openCombatModal: () => set({ showCombatModal: true }),
  closeCombatModal: () => set({ showCombatModal: false }),

  setCardPreview: (card) => set({
    previewCard: card,
    showCardPreview: !!card,
  }),

  toggleGameLog: () => set((state) => ({ showGameLog: !state.showGameLog })),

  addLogEntry: (entry) => set((state) => ({
    gameLog: [
      ...state.gameLog,
      {
        id: `log_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        timestamp: Date.now(),
        ...entry,
      },
    ],
  })),

  clearLog: () => set({ gameLog: [] }),

  setProcessing: (processing) => set({ isProcessing: processing }),

  openHeroSelect: () => set({ showHeroSelect: true }),
  closeHeroSelect: () => set({ showHeroSelect: false }),
}));
