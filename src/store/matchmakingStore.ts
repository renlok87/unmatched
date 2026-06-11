import { create } from 'zustand';
import { apolloClient } from '@/lib/apolloClient';
import { gql } from '@apollo/client';
import type { GameMode, MatchFoundResponse, QueueStatusResponse, PenaltyInfoDto } from '@/gql';

const JOIN_QUEUE_MUTATION = gql`
  mutation JoinQueue($input: JoinQueueDto!, $idempotencyKey: String!) {
    joinQueue(input: $input, idempotencyKey: $idempotencyKey) {
      inQueue
      mode
      position
      totalPlayers
      estimatedWaitTime
      joinedAt
    }
  }
`;

const LEAVE_QUEUE_MUTATION = gql`
  mutation LeaveQueue($mode: String!, $idempotencyKey: String!) {
    leaveQueue(mode: $mode, idempotencyKey: $idempotencyKey)
  }
`;

const LEAVE_ALL_QUEUES_MUTATION = gql`
  mutation LeaveAllQueues($idempotencyKey: String!) {
    leaveAllQueues(idempotencyKey: $idempotencyKey)
  }
`;

const QUEUE_STATUS_QUERY = gql`
  query QueueStatus($mode: String!) {
    queueStatus(mode: $mode) {
      inQueue
      mode
      position
      totalPlayers
      estimatedWaitTime
      joinedAt
    }
  }
`;

const PENALTY_INFO_QUERY = gql`
  query PenaltyInfo {
    penaltyInfo {
      canJoinQueue
      declineCount
      tempBanUntil
      penaltyElo
      reason
    }
  }
`;

const MATCH_FOUND_SUBSCRIPTION = gql`
  subscription MatchFound($userId: ID!) {
    matchFound(userId: $userId) {
      gameId
      opponentId
      opponentUsername
      opponentRating
      mode
      expiresAt
    }
  }
`;

type SubscriptionCleanup = () => void;

export interface MatchmakingState {
  inQueue: boolean;
  mode: GameMode | null;
  position: number | null;
  estimatedWaitTime: number | null;
  totalPlayers: number;
  joinedAt: Date | null;
  matchFound: MatchFoundResponse | null;
  penaltyInfo: PenaltyInfoDto | null;
  loading: boolean;
  error: string | null;

  // Internal state for cleanup
  _isMounted: boolean;
  _subscriptionCleanup: SubscriptionCleanup | null;
  _abortController: AbortController | null;
  _lastOperationId: string | null;

  joinQueue: (mode: GameMode, heroPref?: string) => Promise<void>;
  leaveQueue: () => Promise<void>;
  leaveAllQueues: () => Promise<void>;
  fetchQueueStatus: () => Promise<void>;
  fetchPenaltyInfo: () => Promise<void>;
  subscribeToMatchFound: (userId: string) => void;
  unsubscribeFromMatchFound: () => void;
  clearMatchFound: () => void;
  clearError: () => void;
  mount: () => void;
  unmount: () => void;
}

const generateIdempotencyKey = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

export const useMatchmakingStore = create<MatchmakingState>((set, get) => ({
  inQueue: false,
  mode: null,
  position: null,
  estimatedWaitTime: null,
  totalPlayers: 0,
  joinedAt: null,
  matchFound: null,
  penaltyInfo: null,
  loading: false,
  error: null,

  // Internal state
  _isMounted: false,
  _subscriptionCleanup: null,
  _abortController: null,
  _lastOperationId: null,

  joinQueue: async (mode, heroPref) => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[MatchmakingStore] Component unmounted, skipping joinQueue');
      return;
    }

    // Cancel any pending operations
    if (state._abortController) {
      state._abortController.abort();
    }

    // Create new abort controller for this operation
    const abortController = new AbortController();
    set({ _abortController: abortController });

    // Generate idempotency key
    const idempotencyKey = generateIdempotencyKey();
    set({ _lastOperationId: idempotencyKey, loading: true, error: null });

    try {
      const result = await apolloClient.mutate<{ joinQueue: QueueStatusResponse }>({
        mutation: JOIN_QUEUE_MUTATION,
        variables: { input: { mode, heroPref }, idempotencyKey },
        context: {
          fetchOptions: {
            signal: abortController.signal,
          },
        },
      });

      // Check if component is still mounted and operation is still current
      const currentState = get();
      if (!currentState._isMounted || currentState._lastOperationId !== idempotencyKey) {
        console.warn('[MatchmakingStore] Operation cancelled or stale');
        return;
      }

      if (!result.data?.joinQueue) {
        throw new Error('Failed to join queue');
      }

      const status = result.data.joinQueue;
      set({
        inQueue: status.inQueue,
        mode: status.mode as GameMode,
        position: status.position ?? null,
        estimatedWaitTime: status.estimatedWaitTime ?? null,
        totalPlayers: status.totalPlayers,
        joinedAt: status.joinedAt ?? null,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      // Check if error was due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[MatchmakingStore] Join queue operation aborted');
        return;
      }

      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[MatchmakingStore] Component unmounted during joinQueue');
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to join queue';
      set({ error: message, loading: false, _abortController: null });
      throw error;
    }
  },

  leaveQueue: async () => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[MatchmakingStore] Component unmounted, skipping leaveQueue');
      return;
    }

    const { mode } = state;
    if (!mode) return;

    // Cancel any pending operations
    if (state._abortController) {
      state._abortController.abort();
    }

    // Create new abort controller for this operation
    const abortController = new AbortController();
    set({ _abortController: abortController });

    // Generate idempotency key
    const idempotencyKey = generateIdempotencyKey();
    set({ _lastOperationId: idempotencyKey, loading: true, error: null });

    try {
      await apolloClient.mutate({
        mutation: LEAVE_QUEUE_MUTATION,
        variables: { mode, idempotencyKey },
        context: {
          fetchOptions: {
            signal: abortController.signal,
          },
        },
      });

      // Check if component is still mounted and operation is still current
      const currentState = get();
      if (!currentState._isMounted || currentState._lastOperationId !== idempotencyKey) {
        console.warn('[MatchmakingStore] Operation cancelled or stale');
        return;
      }

      set({
        inQueue: false,
        mode: null,
        position: null,
        estimatedWaitTime: null,
        totalPlayers: 0,
        joinedAt: null,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      // Check if error was due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[MatchmakingStore] Leave queue operation aborted');
        return;
      }

      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[MatchmakingStore] Component unmounted during leaveQueue');
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to leave queue';
      set({ error: message, loading: false, _abortController: null });
      throw error;
    }
  },

  leaveAllQueues: async () => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[MatchmakingStore] Component unmounted, skipping leaveAllQueues');
      return;
    }

    // Cancel any pending operations
    if (state._abortController) {
      state._abortController.abort();
    }

    // Create new abort controller for this operation
    const abortController = new AbortController();
    set({ _abortController: abortController });

    // Generate idempotency key
    const idempotencyKey = generateIdempotencyKey();
    set({ _lastOperationId: idempotencyKey, loading: true, error: null });

    try {
      await apolloClient.mutate({
        mutation: LEAVE_ALL_QUEUES_MUTATION,
        variables: { idempotencyKey },
        context: {
          fetchOptions: {
            signal: abortController.signal,
          },
        },
      });

      // Check if component is still mounted and operation is still current
      const currentState = get();
      if (!currentState._isMounted || currentState._lastOperationId !== idempotencyKey) {
        console.warn('[MatchmakingStore] Operation cancelled or stale');
        return;
      }

      set({
        inQueue: false,
        mode: null,
        position: null,
        estimatedWaitTime: null,
        totalPlayers: 0,
        joinedAt: null,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      // Check if error was due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[MatchmakingStore] Leave all queues operation aborted');
        return;
      }

      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[MatchmakingStore] Component unmounted during leaveAllQueues');
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to leave queues';
      set({ error: message, loading: false, _abortController: null });
      throw error;
    }
  },

  fetchQueueStatus: async () => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[MatchmakingStore] Component unmounted, skipping fetchQueueStatus');
      return;
    }

    const { mode } = state;
    if (!mode) return;

    // Cancel any pending operations
    if (state._abortController) {
      state._abortController.abort();
    }

    // Create new abort controller for this operation
    const abortController = new AbortController();
    set({ _abortController: abortController, loading: true, error: null });

    try {
      const result = await apolloClient.query<{ queueStatus: QueueStatusResponse }>({
        query: QUEUE_STATUS_QUERY,
        variables: { mode },
        fetchPolicy: 'network-only',
        context: {
          fetchOptions: {
            signal: abortController.signal,
          },
        },
      });

      // Check if component is still mounted
      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[MatchmakingStore] Component unmounted during fetchQueueStatus');
        return;
      }

      const status = result.data?.queueStatus;
      if (status) {
        set({
          inQueue: status.inQueue,
          mode: status.mode as GameMode,
          position: status.position ?? null,
          estimatedWaitTime: status.estimatedWaitTime ?? null,
          totalPlayers: status.totalPlayers,
          joinedAt: status.joinedAt ?? null,
          loading: false,
          _abortController: null,
        });
      } else {
        set({
          inQueue: false,
          mode: null,
          loading: false,
          _abortController: null,
        });
      }
    } catch (error) {
      // Check if error was due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[MatchmakingStore] Fetch queue status operation aborted');
        return;
      }

      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[MatchmakingStore] Component unmounted during fetchQueueStatus');
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to fetch queue status';
      set({ error: message, loading: false, _abortController: null });
    }
  },

  fetchPenaltyInfo: async () => {
    const state = get();

    // Check if component is mounted
    if (!state._isMounted) {
      console.warn('[MatchmakingStore] Component unmounted, skipping fetchPenaltyInfo');
      return;
    }

    try {
      const result = await apolloClient.query<{ penaltyInfo: PenaltyInfoDto }>({
        query: PENALTY_INFO_QUERY,
        fetchPolicy: 'network-only',
      });

      // Check if component is still mounted
      const currentState = get();
      if (!currentState._isMounted) {
        console.warn('[MatchmakingStore] Component unmounted during fetchPenaltyInfo');
        return;
      }

      set({ penaltyInfo: result.data?.penaltyInfo ?? null });
    } catch (error) {
      console.error('Failed to fetch penalty info:', error);
    }
  },

  subscribeToMatchFound: (userId) => {
    const state = get();

    // Clean up existing subscription if any
    if (state._subscriptionCleanup) {
      state._subscriptionCleanup();
    }

    const subscription = apolloClient.subscribe<{ matchFound: MatchFoundResponse }>({
      query: MATCH_FOUND_SUBSCRIPTION,
      variables: { userId },
    });

    const observable = subscription.subscribe({
      next: ({ data }) => {
        // Check if component is still mounted before updating state
        const currentState = get();
        if (!currentState._isMounted) {
          console.warn('[MatchmakingStore] Component unmounted, ignoring match found event');
          return;
        }

        if (data?.matchFound) {
          set({ matchFound: data.matchFound });
        }
      },
      error: (error) => {
        // Check if component is still mounted before updating state
        const currentState = get();
        if (!currentState._isMounted) {
          console.warn('[MatchmakingStore] Component unmounted, ignoring subscription error');
          return;
        }

        console.error('Match found subscription error:', error);
        set({ error: 'Match finding error' });
      },
    });

    const cleanup = () => {
      observable.unsubscribe();
      console.log('[MatchmakingStore] Match found subscription cleaned up');
    };

    set({ _subscriptionCleanup: cleanup });
  },

  unsubscribeFromMatchFound: () => {
    const state = get();

    if (state._subscriptionCleanup) {
      state._subscriptionCleanup();
      set({ _subscriptionCleanup: null });
    }
  },

  clearMatchFound: () => {
    set({ matchFound: null });
  },

  clearError: () => set({ error: null }),

  mount: () => {
    console.log('[MatchmakingStore] Component mounted');
    set({ _isMounted: true });
  },

  unmount: () => {
    console.log('[MatchmakingStore] Component unmounting');

    // Cancel any pending operations
    const state = get();
    if (state._abortController) {
      state._abortController.abort();
    }

    // Clean up subscription
    if (state._subscriptionCleanup) {
      state._subscriptionCleanup();
    }

    set({
      _isMounted: false,
      _subscriptionCleanup: null,
      _abortController: null,
    });
  },
}));