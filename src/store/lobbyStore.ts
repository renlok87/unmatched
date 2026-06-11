import { create } from 'zustand';
import { apolloClient } from '@/lib/apolloClient';
import { gql } from '@apollo/client';
import type { GameResponse, GameMode, GameStatus } from '@/gql';

const AVAILABLE_GAMES_QUERY = gql`
  query AvailableGames($mode: String) {
    availableGames(mode: $mode) {
      id
      mode
      status
      hostId
      boardId
      createdAt
      players {
        userId
        username
        avatar
        heroId
      }
    }
  }
`;

const CREATE_GAME_MUTATION = gql`
  mutation CreateGame($input: CreateGameDto!, $idempotencyKey: String!) {
    createGame(input: $input, idempotencyKey: $idempotencyKey) {
      id
      mode
      status
      hostId
      boardId
    }
  }
`;

const JOIN_GAME_MUTATION = gql`
  mutation JoinGame($input: JoinGameDto!, $idempotencyKey: String!) {
    joinGame(input: $input, idempotencyKey: $idempotencyKey) {
      id
      status
      phase
    }
  }
`;

export interface LobbyState {
  games: GameResponse[];
  loading: boolean;
  error: string | null;
  filter: {
    mode?: GameMode;
    status?: GameStatus;
  };

  // Internal state for cleanup
  _isMounted: boolean;
  _abortController: AbortController | null;
  _lastOperationId: string | null;
  _pollInterval: NodeJS.Timeout | null;

  fetchGames: () => Promise<void>;
  setFilter: (filter: { mode?: GameMode; status?: GameStatus }) => void;
  createGame: (input: { mode?: GameMode; boardId?: string }) => Promise<GameResponse>;
  joinGame: (gameId: string) => Promise<void>;
  clearError: () => void;
  startPolling: (intervalMs?: number) => void;
  stopPolling: () => void;
  mount: () => void;
  unmount: () => void;
}

const generateIdempotencyKey = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

export const useLobbyStore = create<LobbyState>((set, get) => ({
  games: [],
  loading: false,
  error: null,
  filter: {},

  // Internal state
  _isMounted: false,
  _abortController: null,
  _lastOperationId: null,
  _pollInterval: null,

  fetchGames: async () => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[LobbyStore] Component unmounted, skipping fetchGames');
      return;
    }

    // Cancel any pending operations
    if (state._abortController) {
      state._abortController.abort();
    }

    // Create new abort controller for this operation
    const abortController = new AbortController();
    set({ _abortController: abortController, loading: true, error: null });

    try {
      const { filter } = state;
      const result = await apolloClient.query({
        query: AVAILABLE_GAMES_QUERY,
        variables: filter.mode ? { mode: filter.mode } : {},
        fetchPolicy: 'cache-first',
        context: {
          fetchOptions: {
            signal: abortController.signal,
          },
        },
      });

      // Check if component is still mounted
      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[LobbyStore] Component unmounted during fetchGames');
        return;
      }

      set({ games: result.data?.availableGames || [], loading: false, _abortController: null });
    } catch (error) {
      // Check if error was due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[LobbyStore] Fetch games operation aborted');
        return;
      }

      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[LobbyStore] Component unmounted during fetchGames');
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to fetch games';
      set({ error: message, loading: false, games: [], _abortController: null });
    }
  },

  setFilter: (filter) => {
    set({ filter });
    // Не вызываем fetchGames — polling обновляет данные автоматически
  },

  createGame: async (input) => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[LobbyStore] Component unmounted, skipping createGame');
      throw new Error('Component unmounted');
    }

    // Cancel any pending operations
    if (state._abortController) {
      state._abortController.abort();
    }

    // Create new abort controller for this operation
    const abortController = new AbortController();
    const idempotencyKey = generateIdempotencyKey();
    set({ _abortController: abortController, _lastOperationId: idempotencyKey, loading: true, error: null });

    try {
      const result = await apolloClient.mutate({
        mutation: CREATE_GAME_MUTATION,
        variables: { input, idempotencyKey },
        context: {
          fetchOptions: {
            signal: abortController.signal,
          },
        },
      });

      // Check if component is still mounted and operation is still current
      const currentState = get();
      if (!currentState._isMounted || currentState._lastOperationId !== idempotencyKey) {
        console.warn('[LobbyStore] Operation cancelled or stale');
        throw new Error('Operation cancelled');
      }

      if (!result.data?.createGame) {
        throw new Error('Failed to create game');
      }

      set({ loading: false, _abortController: null });
      return result.data.createGame;
    } catch (error) {
      // Check if error was due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[LobbyStore] Create game operation aborted');
        throw error;
      }

      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[LobbyStore] Component unmounted during createGame');
        throw new Error('Component unmounted');
      }

      const message = error instanceof Error ? error.message : 'Failed to create game';
      set({ error: message, loading: false, _abortController: null });
      throw error;
    }
  },

  joinGame: async (gameId) => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[LobbyStore] Component unmounted, skipping joinGame');
      throw new Error('Component unmounted');
    }

    // Cancel any pending operations
    if (state._abortController) {
      state._abortController.abort();
    }

    // Create new abort controller for this operation
    const abortController = new AbortController();
    const idempotencyKey = generateIdempotencyKey();
    set({ _abortController: abortController, _lastOperationId: idempotencyKey, loading: true, error: null });

    try {
      await apolloClient.mutate({
        mutation: JOIN_GAME_MUTATION,
        variables: { input: { gameId, asOpponent: true }, idempotencyKey },
        context: {
          fetchOptions: {
            signal: abortController.signal,
          },
        },
      });

      // Check if component is still mounted and operation is still current
      const currentState = get();
      if (!currentState._isMounted || currentState._lastOperationId !== idempotencyKey) {
        console.warn('[LobbyStore] Operation cancelled or stale');
        throw new Error('Operation cancelled');
      }

      set({ loading: false, _abortController: null });
    } catch (error) {
      // Check if error was due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[LobbyStore] Join game operation aborted');
        throw error;
      }

      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[LobbyStore] Component unmounted during joinGame');
        throw new Error('Component unmounted');
      }

      const message = error instanceof Error ? error.message : 'Failed to join game';
      set({ error: message, loading: false, _abortController: null });
      throw error;
    }
  },

  clearError: () => set({ error: null }),

  startPolling: (intervalMs = 30000) => {
    const state = get();

    // Clear existing interval if any
    if (state._pollInterval) {
      clearInterval(state._pollInterval);
    }

    // Initial fetch
    state.fetchGames();

    // Set up polling
    const interval = setInterval(() => {
      const currentState = get();
      if (currentState._isMounted) {
        currentState.fetchGames();
      }
    }, intervalMs);

    set({ _pollInterval: interval });
    console.log(`[LobbyStore] Polling started with interval ${intervalMs}ms`);
  },

  stopPolling: () => {
    const state = get();

    if (state._pollInterval) {
      clearInterval(state._pollInterval);
      set({ _pollInterval: null });
      console.log('[LobbyStore] Polling stopped');
    }
  },

  mount: () => {
    console.log('[LobbyStore] Component mounted');
    set({ _isMounted: true });
  },

  unmount: () => {
    console.log('[LobbyStore] Component unmounting');

    // Cancel any pending operations
    const state = get();
    if (state._abortController) {
      state._abortController.abort();
    }

    // Stop polling
    state.stopPolling();

    set({
      _isMounted: false,
      _abortController: null,
      _pollInterval: null,
    });
  },
}));