import { create } from 'zustand';
import { apolloClient } from '@/lib/apolloClient';
import { gql } from '@apollo/client';

export interface GamePlayer {
  id: string;
  userId: string;
  username: string;
  avatar: string | null;
  heroId: string | null;
  isReady: boolean;
  seatOrder: number;
}

export interface GameInfo {
  id: string;
  code: string | null;
  status: string;
  mode: string;
  hostId: string;
  boardId: string | null;
  phase: string;
  createdAt: string;
  players: GamePlayer[];
}

interface RoomState {
  game: GameInfo | null;
  isHost: boolean;
  allReady: boolean;
  loading: boolean;
  error: string | null;

  _isMounted: boolean;
  _abortController: AbortController | null;

  mount: () => void;
  unmount: () => void;
  loadRoom: (gameId: string) => Promise<void>;
  setReady: (gameId: string) => Promise<void>;
  leaveRoom: (gameId: string) => Promise<void>;
  startGame: (gameId: string) => Promise<void>;
  clearError: () => void;
}

export const useRoomStore = create<RoomState>((set, get) => ({
  game: null,
  isHost: false,
  allReady: false,
  loading: false,
  error: null,

  _isMounted: false,
  _abortController: null,

  mount: () => {
    set({ _isMounted: true });
  },

  unmount: () => {
    const controller = get()._abortController;
    if (controller) {
      controller.abort();
    }
    set({ _isMounted: false, _abortController: null });
  },

  loadRoom: async (gameId: string) => {
    const state = get();

    if (!state._isMounted) return;

    if (state._abortController) {
      state._abortController.abort();
    }

    const controller = new AbortController();
    set({ _abortController: controller, loading: true, error: null });

    try {
      const { data, errors } = await apolloClient.query<{
        game: GameInfo;
      }>({
        query: gql`
          query RoomInfo($id: String!) {
            game(id: $id) {
              id
              code
              status
              mode
              hostId
              boardId
              phase
              createdAt
              players {
                id
                userId
                username
                avatar
                heroId
                isReady
                seatOrder
              }
            }
          }
        `,
        variables: { id: gameId },
        fetchPolicy: 'network-only',
        context: {
          fetchOptions: {
            signal: controller.signal,
          },
        },
      });

      if (!get()._isMounted) return;

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      if (!data?.game) {
        throw new Error('Failed to load room');
      }

      const currentUserId = localStorage.getItem('userId');
      const isHost = data.game.hostId === currentUserId;
      const allReady = data.game.players.every((p) => p.isReady);

      set({
        game: data.game,
        isHost,
        allReady,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      if (!get()._isMounted) return;

      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to load room';
      set({
        error: message,
        loading: false,
        _abortController: null,
      });
    }
  },

  setReady: async (gameId: string) => {
    const state = get();

    if (!state._isMounted) return;

    if (state._abortController) {
      state._abortController.abort();
    }

    const controller = new AbortController();
    const idempotencyKey = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    set({ _abortController: controller, loading: true, error: null });

    try {
      const { data, errors } = await apolloClient.mutate({
        mutation: gql`
          mutation ToggleReady($gameId: String!) {
            toggleReady(gameId: $gameId) {
              id
              players {
                userId
                isReady
              }
            }
          }
        `,
        variables: { gameId },
        context: {
          headers: {
            'X-Idempotency-Key': idempotencyKey,
          },
          fetchOptions: {
            signal: controller.signal,
          },
        },
      });

      if (!get()._isMounted) return;

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      if (!data?.toggleReady) {
        throw new Error('Failed to toggle ready');
      }

      await get().loadRoom(gameId);
    } catch (error) {
      if (!get()._isMounted) return;

      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to toggle ready';
      set({
        error: message,
        loading: false,
        _abortController: null,
      });
      throw error;
    }
  },

  leaveRoom: async (gameId: string) => {
    const state = get();

    if (!state._isMounted) return;

    if (state._abortController) {
      state._abortController.abort();
    }

    const controller = new AbortController();

    set({ _abortController: controller, loading: true, error: null });

    try {
      const { errors } = await apolloClient.mutate({
        mutation: gql`
          mutation LeaveGame($gameId: String!) {
            leaveGame(gameId: $gameId)
          }
        `,
        variables: { gameId },
        context: {
          fetchOptions: {
            signal: controller.signal,
          },
        },
      });

      if (!get()._isMounted) return;

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      set({
        game: null,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      if (!get()._isMounted) return;

      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to leave room';
      set({
        error: message,
        loading: false,
        _abortController: null,
      });
      throw error;
    }
  },

  startGame: async (gameId: string) => {
    const state = get();

    if (!state._isMounted) return;

    if (state._abortController) {
      state._abortController.abort();
    }

    const controller = new AbortController();
    const idempotencyKey = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    set({ _abortController: controller, loading: true, error: null });

    try {
      const { data, errors } = await apolloClient.mutate({
        mutation: gql`
          mutation StartGame($gameId: String!) {
            startGame(gameId: $gameId) {
              id
              status
              phase
              players {
                userId
                heroId
              }
            }
          }
        `,
        variables: { gameId },
        context: {
          headers: {
            'X-Idempotency-Key': idempotencyKey,
          },
          fetchOptions: {
            signal: controller.signal,
          },
        },
      });

      if (!get()._isMounted) return;

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      if (!data?.startGame) {
        throw new Error('Failed to start game');
      }

      set({
        game: { ...get().game!, ...data.startGame } as GameInfo,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      if (!get()._isMounted) return;

      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to start game';
      set({
        error: message,
        loading: false,
        _abortController: null,
      });
      throw error;
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));