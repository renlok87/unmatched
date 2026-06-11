import { create } from 'zustand';
import { apolloClient } from '@/lib/apolloClient';
import * as gql from '@/gql';

/**
 * Статус соединения с сервером
 */
export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error';

/**
 * Игровое событие от сервера
 */
export interface GameEvent {
  type: string;
  gameId: string;
  sequenceNumber: number;
  timestamp: number;
  payload: unknown;
}

/**
 * Состояние игры с сервера (упрощённое для фронтенда)
 */
export interface ServerGameState {
  gameId: string;
  sequenceNumber: number;
  phase: string;
  turnCount: number;
  currentTurnPlayerId: string;
  players: ServerGamePlayer[];
  fighters: ServerFighter[];
  handZones: Record<string, ServerHandZone>;
  boardState: ServerBoardState;
  metadata: {
    lastUpdatedAt: number;
  };
}

export interface ServerGamePlayer {
  id: string;
  userId: string;
  username: string;
  heroId: string;
  health: number;
  hasPassed: boolean;
}

export interface ServerFighter {
  id: string;
  definitionId: string;
  type: 'hero' | 'sidekick';
  health: number;
  maxHealth: number;
  position: { x: number; y: number };
  ownerId: string;
}

export interface ServerHandZone {
  ownerId: string;
  cards: Array<{
    id: string;
    definitionId: string;
    isFaceDown?: boolean;
  }>;
}

export interface ServerBoardState {
  width: number;
  height: number;
  spaces: Array<{
    position: { x: number; y: number };
    zones: string[];
  }>;
}

/**
 * Remote Game Store
 *
 * Управляет синхронизацией игрового состояния с сервером.
 * Отслеживает sequence numbers для обнаружения пропущенных событий.
 */
interface RemoteGameState {
  // Server state
  currentGameId: string | null;
  serverGameState: ServerGameState | null;
  lastSequenceNumber: number;
  connectionStatus: ConnectionStatus;
  syncError: string | null;
  isSyncing: boolean;

  // Actions
  connectToGame: (gameId: string) => Promise<void>;
  disconnect: () => void;
  handleGameEvent: (event: GameEvent) => void;
  checkSequenceGaps: () => Promise<void>;
  fetchGameState: (gameId: string) => Promise<void>;
  setConnectionStatus: (status: ConnectionStatus) => void;
  clearError: () => void;
}

export const useRemoteGameStore = create<RemoteGameState>((set, get) => ({
  // Initial state
  currentGameId: null,
  serverGameState: null,
  lastSequenceNumber: 0,
  connectionStatus: 'disconnected',
  syncError: null,
  isSyncing: false,

  /**
   * Подключение к игре
   * Загружает начальное состояние игры
   */
  connectToGame: async (gameId: string) => {
    set({ connectionStatus: 'connecting', syncError: null, isSyncing: true });

    try {
      await get().fetchGameState(gameId);
      set({
        currentGameId: gameId,
        connectionStatus: 'connected',
        isSyncing: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to connect to game';
      set({
        connectionStatus: 'error',
        syncError: message,
        isSyncing: false,
      });
      throw error;
    }
  },

  /**
   * Отключение от игры
   */
  disconnect: () => {
    set({
      currentGameId: null,
      serverGameState: null,
      lastSequenceNumber: 0,
      connectionStatus: 'disconnected',
      syncError: null,
    });
  },

  /**
   * Обработка игрового события от WebSocket подписки
   *
   * Проверяет sequence number и обнаруживает gaps.
   */
  handleGameEvent: (event: GameEvent) => {
    const state = get();
    const expectedSeq = state.lastSequenceNumber + 1;
    const actualSeq = event.sequenceNumber;

    // Пропускаем устаревшие события
    if (actualSeq <= state.lastSequenceNumber) {
      console.warn(`[RemoteGameStore] Skipping old event: ${actualSeq} <= ${state.lastSequenceNumber}`);
      return;
    }

    // Обнаружен gap — нужно запросить пропущенные события
    if (actualSeq > expectedSeq) {
      console.warn(`[RemoteGameStore] Sequence gap detected: expected ${expectedSeq}, got ${actualSeq}`);

      // Запускаем асинхронную загрузку пропущенных событий
      get().checkSequenceGaps().catch((error) => {
        console.error('[RemoteGameStore] Failed to fetch missed events:', error);
        set({
          syncError: `Не удалось загрузить пропущенные события (${expectedSeq}-${actualSeq - 1})`,
        });
      });
    }

    // Применяем событие (здесь должна быть логика применения разных типов событий)
    set({
      lastSequenceNumber: actualSeq,
    });

    // TODO: Применить конкретные изменения в зависимости от типа события
    // switch (event.type) {
    //   case 'MANEUVER':
    //   case 'MOVE':
    //   case 'ATTACK':
    //   case 'DEFEND':
    //     ...
    // }
  },

  /**
   * Проверка на пропущенные события и их загрузка
   */
  checkSequenceGaps: async () => {
    const state = get();
    if (!state.currentGameId) return;

    void (state.lastSequenceNumber + 1); // ожидаемая последовательность для будущего использования

    set({ isSyncing: true });

    try {
      // TODO: Добавить мутацию/запрос eventsSince на бэкенде
      // const { data } = await apolloClient.query({
      //   query: EventsSinceDocument,
      //   variables: {
      //     gameId: state.currentGameId,
      //     afterSequence: expectedSeq,
      //   },
      // });

      // Временно: перезагружаем полное состояние игры
      await get().fetchGameState(state.currentGameId);

      set({ isSyncing: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch missed events';
      set({
        syncError: message,
        isSyncing: false,
      });
      throw error;
    }
  },

  /**
   * Загрузка текущего состояния игры с сервера
   */
  fetchGameState: async (gameId: string) => {
    set({ isSyncing: true });

    try {
      const { data, errors } = await apolloClient.query<{
        gameState: ServerGameState;
      }>({
        query: gql.GetGameStateDocument,
        variables: { gameId },
        fetchPolicy: 'network-only',
      });

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      if (!data?.gameState) {
        throw new Error('Game state not found');
      }

      set({
        serverGameState: data.gameState,
        lastSequenceNumber: data.gameState.sequenceNumber,
        isSyncing: false,
      });
    } catch (error) {
      set({ isSyncing: false });
      throw error;
    }
  },

  /**
   * Установить статус соединения (для использования в hooks)
   */
  setConnectionStatus: (status: ConnectionStatus) => {
    set({ connectionStatus: status });
  },

  /**
   * Очистить ошибку синхронизации
   */
  clearError: () => {
    set({ syncError: null });
  },
}));

/**
 * Selector хуки для оптимизации ререндеров
 */
export const useCurrentGameId = () => useRemoteGameStore((state) => state.currentGameId);
export const useServerGameState = () => useRemoteGameStore((state) => state.serverGameState);
export const useConnectionStatus = () => useRemoteGameStore((state) => state.connectionStatus);
export const useIsGameSyncing = () => useRemoteGameStore((state) => state.isSyncing);
export const useGameSyncError = () => useRemoteGameStore((state) => state.syncError);
