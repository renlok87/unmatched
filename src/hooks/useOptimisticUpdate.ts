import { useCallback, useRef, useEffect } from 'react';
import { ApolloError, useApolloClient } from '@apollo/client';
import type { DocumentNode } from 'graphql';
import { useGameStore } from '@/store/gameStore';
import { useRemoteGameStore } from '@/store/remoteGameStore';
import type { GameState } from '@/core/models/types';

/**
 * Результат мутации с optimistic response
 */
interface MutationResult<T> {
  data?: T;
  success: boolean;
  error?: ApolloError;
}

/**
 * Опции для optimistic обновления
 */
interface OptimisticUpdateOptions<TData, TVariables> {
  /**
   * Мутация GraphQL
   */
  mutation: DocumentNode;

  /**
   * Функция для предсказания локального состояния
   * Вызывается немедленно для показа результата пользователю
   */
  predictState: (currentState: GameState | null, variables: TVariables) => GameState | null;

  /**
   * Функция для rollback в случае ошибки
   * Восстанавливает состояние до мутации
   */
  rollbackState?: (previousState: GameState | null) => void;

  /**
   * Callback при успешном выполнении мутации
   */
  onSuccess?: (data: TData) => void;

  /**
   * Callback при ошибке мутации
   */
  onError?: (error: ApolloError) => void;
}

/**
 * State для отката изменений
 */
interface RollbackState {
  previousState: GameState | null;
  restore: () => void;
}

/**
 * Hook для выполнения мутаций с optimistic updates
 *
 * Позволяет мгновенно показывать результат действия пользователю,
 * а затем подтверждать или отката изменения после ответа сервера.
 *
 * @example
 * ```tsx
 * function GameBoard() {
 *   const { execute: maneuver, isLoading } = useOptimisticUpdate({
 *     mutation: ManeuverDocument,
 *     predictState: (state, { fighterId }) => {
 *       // Предсказываем состояние после манёвра
 *       const engine = new GameEngine();
 *       return engine.maneuver(state, fighterId);
 *     },
 *     onSuccess: (data) => {
 *       console.log('Maneuver successful!', data);
 *     },
 *   });
 *
 *   return <button onClick={() => maneuver({ fighterId: 'hero-1' })}>Maneuver</button>;
 * }
 * ```
 */
export function useOptimisticUpdate<TData = unknown, TVariables = Record<string, unknown>>(
  options: OptimisticUpdateOptions<TData, TVariables>
) {
  const { mutation, predictState, rollbackState, onSuccess, onError } = options;
  const client = useApolloClient();

  const { gameState: localGameState } = useGameStore();
  const { serverGameState } = useRemoteGameStore();

  // Храним состояние для отката
  const rollbackRef = useRef<RollbackState | null>(null);
  const isMutatingRef = useRef(false);
  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;

      // Cancel any pending mutations
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Rollback any pending changes
      if (rollbackRef.current) {
        rollbackRef.current.restore();
        rollbackRef.current = null;
      }
    };
  }, []);

  /**
   * Выполнение мутации с optimistic update
   */
  const execute = useCallback(
    async (variables: TVariables): Promise<MutationResult<TData>> => {
      // Check if component is mounted
      if (!isMountedRef.current) {
        console.warn('[useOptimisticUpdate] Component unmounted, skipping mutation');
        return { success: false };
      }

      if (isMutatingRef.current) {
        console.warn('[useOptimisticUpdate] Mutation already in progress, ignoring');
        return { success: false };
      }

      // Cancel any pending mutations
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Create new abort controller
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      isMutatingRef.current = true;

      // Сохраняем текущее состояние для возможного отката
      const previousState = localGameState || null;
      const currentState = serverGameState
        ? convertServerStateToLocal(serverGameState)
        : localGameState;

      void serverGameState; // помечаем как использованное для будущего использования в optimistic update

      if (!currentState) {
        isMutatingRef.current = false;
        abortControllerRef.current = null;
        return { success: false, error: new ApolloError({ errorMessage: 'No game state available' }) };
      }

      // Предсказываем результат (optimistic update)
      const predictedState = predictState(currentState, variables);

      if (predictedState) {
        // Применяем предсказанное состояние немедленно
        useGameStore.setState({ gameState: predictedState });

        // Сохраняем функцию отката
        rollbackRef.current = {
          previousState,
          restore: () => {
            if (isMountedRef.current) {
              useGameStore.setState({ gameState: previousState });
            }
          },
        };
      }

      try {
        // Выполняем мутацию на сервере
        const { data, errors } = await client.mutate<TData>({
          mutation,
          variables: variables as Record<string, unknown>,
          context: {
            fetchOptions: {
              signal: abortController.signal,
            },
          },
          // optimisticResponse будет использоваться Apollo для кэша
          optimisticResponse: predictedState
            ? ({
                __typename: 'Mutation',
                // @ts-ignore - dynamic response shape
                result: predictedState,
              } as any)
            : undefined,
        });

        // Check if component is still mounted
        if (!isMountedRef.current) {
          console.warn('[useOptimisticUpdate] Component unmounted after mutation');
          return { success: false };
        }

        if (errors?.length) {
          throw new ApolloError({ graphQLErrors: errors });
        }

        // Успех — очищаем rollback
        rollbackRef.current = null;
        abortControllerRef.current = null;

        onSuccess?.(data as TData);

        return { data: data as TData, success: true };
      } catch (error) {
        // Check if error was due to abort
        if (error instanceof Error && error.name === 'AbortError') {
          console.log('[useOptimisticUpdate] Mutation aborted');
          return { success: false };
        }

        // Check if component is still mounted
        if (!isMountedRef.current) {
          console.warn('[useOptimisticUpdate] Component unmounted during error');
          return { success: false };
        }

        const apolloError = error instanceof ApolloError ? error : new ApolloError({ errorMessage: String(error) });

        // Ошибка — откатываем состояние
        if (rollbackRef.current) {
          rollbackRef.current.restore();
          rollbackRef.current = null;
        } else if (rollbackState) {
          rollbackState(previousState);
        }

        onError?.(apolloError);

        return { success: false, error: apolloError };
      } finally {
        isMutatingRef.current = false;
        abortControllerRef.current = null;
      }
    },
    [mutation, predictState, rollbackState, onSuccess, onError, localGameState, serverGameState, client]
  );

  /**
   * Ручной откат последней мутации
   */
  const rollback = useCallback(() => {
    if (rollbackRef.current && isMountedRef.current) {
      rollbackRef.current.restore();
      rollbackRef.current = null;
    }
  }, []);

  /**
   * Отмена текущей мутации
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // Rollback if needed
    if (rollbackRef.current && isMountedRef.current) {
      rollbackRef.current.restore();
      rollbackRef.current = null;
    }

    isMutatingRef.current = false;
  }, []);

  return {
    execute,
    rollback,
    cancel,
    isMutating: isMutatingRef.current,
  };
}

/**
 * Вспомогательная функция для конвертации серверного состояния в локальное
 * TODO: Реализовать полную конвертацию когда будут готовы типы
 */
function convertServerStateToLocal(_serverState: unknown): GameState | null {
  // Временная заглушка — в реальности нужна полная конвертация
  // ServerGameState -> GameState
  return null;
}

/**
 * Hook для выполнения нескольких мутаций с optimistic updates batch
 *
 * Полезно для комбо действий (например, манёвр + атака)
 */
export function useOptimisticBatch() {
  const batchRef = useRef<Array<() => void>>([]);
  const isExecutingRef = useRef(false);
  const isMountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      batchRef.current = [];
      isExecutingRef.current = false;
    };
  }, []);

  const add = useCallback((mutation: () => void) => {
    if (isMountedRef.current) {
      batchRef.current.push(mutation);
    }
  }, []);

  const execute = useCallback(async () => {
    if (!isMountedRef.current) {
      console.warn('[useOptimisticBatch] Component unmounted');
      return { success: false };
    }

    if (isExecutingRef.current || batchRef.current.length === 0) {
      return { success: false };
    }

    isExecutingRef.current = true;
    const mutations = [...batchRef.current];
    batchRef.current = [];

    try {
      // Выполняем все мутации параллельно
      await Promise.all(mutations.map((m) => m()));

      if (isMountedRef.current) {
        isExecutingRef.current = false;
      }

      return { success: true };
    } catch (error) {
      if (isMountedRef.current) {
        isExecutingRef.current = false;
      }
      return { success: false, error };
    }
  }, []);

  const clear = useCallback(() => {
    batchRef.current = [];
  }, []);

  return {
    add,
    execute,
    clear,
    size: batchRef.current.length,
  };
}

/**
 * Hook для optimistic обновления с debounce
 *
 * Полезно для часто повторяющихся действий (например, перемещение фигуры)
 */
export function useOptimisticDebounce<TVariables>(
  options: OptimisticUpdateOptions<unknown, TVariables>,
  delay: number = 300
) {
  const { execute, cancel: cancelMutation } = useOptimisticUpdate(options);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestVarsRef = useRef<TVariables | null>(null);
  const isMountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;

      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const executeDebounced = useCallback(
    (variables: TVariables) => {
      if (!isMountedRef.current) {
        console.warn('[useOptimisticDebounce] Component unmounted, skipping');
        return;
      }

      latestVarsRef.current = variables;

      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        if (latestVarsRef.current && isMountedRef.current) {
          execute(latestVarsRef.current);
        }
      }, delay);
    },
    [execute, delay]
  );

  const cancel = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    cancelMutation();
  }, [cancelMutation]);

  return {
    execute: executeDebounced,
    cancel,
  };
}
