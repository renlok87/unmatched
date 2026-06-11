// ============================================================
// USE GAME STATE - React hook для игрового состояния
// ============================================================

import { useEffect, useState, useCallback, useRef } from 'react';
import { ApolloClient } from '@apollo/client';
import * as gql from '@/gql';
import type { GameStateUpdate, GameEvent, TurnUpdate } from '../network/SubscriptionHandler';

// ------------------------------------------------------------
// Типы для хука
// ------------------------------------------------------------

/**
 * Статус синхронизации
 */
export type SyncStatus = 'disconnected' | 'connecting' | 'synced' | 'error';

/**
 * Состояние игры от сервера (упрощённое)
 */
export interface ServerGameState {
  gameId: string;
  sequenceNumber: number;
  phase: string;
  turnCount: number;
  currentTurnPlayerId: string;
  lastUpdate: Date;
}

/**
 * Опции хука useGameState
 */
export interface UseGameStateOptions {
  /**
   * gameId для подписки
   */
  gameId: string | null;

  /**
   * Apollo клиент для запросов
   */
  client: ApolloClient<object>;

  /**
   * Автоматическое переподключение
   */
  autoReconnect?: boolean;

  /**
   * Задержка между попытками переподключения (мс)
   */
  reconnectDelay?: number;
}

/**
 * Возвращаемое значение хука
 */
export interface UseGameStateReturn {
  // Состояние
  gameState: ServerGameState | null;
  syncStatus: SyncStatus;
  error: Error | null;

  // Действия
  connect: () => Promise<void>;
  disconnect: () => void;
  refetch: () => Promise<void>;

  // Подписки (управляются автоматически)
  subscriptions: {
    gameState: ZenObservable.Subscription | null;
    events: Map<string, ZenObservable.Subscription>;
  };
}

// ------------------------------------------------------------
// Hook implementation
// ------------------------------------------------------------

/**
 * useGameState - хук для синхронизации игрового состояния с сервером
 *
 * Функционал:
 * - Подписка на gameStateUpdated
 * - Подписка на игровые события
 * - Автоматическое переподключение
 * - Кэширование последнего состояния
 * - Обработка sequence gaps
 *
 * @example
 * ```tsx
 * const { gameState, syncStatus, error } = useGameState({
 *   gameId: currentGame?.id,
 *   client: apolloClient,
 * });
 * ```
 */
export function useGameState(options: UseGameStateOptions): UseGameStateReturn {
  const { gameId, client, autoReconnect = true, reconnectDelay = 3000 } = options;

  // Состояние
  const [gameState, setGameState] = useState<ServerGameState | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('disconnected');
  const [error, setError] = useState<Error | null>(null);

  // Refs для подписок
  const subscriptionsRef = useRef<{
    gameState: ZenObservable.Subscription | null;
    events: Map<string, ZenObservable.Subscription>;
  }>({
    gameState: null,
    events: new Map(),
  });

  const lastSequenceRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Очистить все подписки
   */
  const cleanup = useCallback(() => {
    console.log('[useGameState] Очистка подписок');

    // Очищаем таймер переподключения
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Отписываемся от gameState
    if (subscriptionsRef.current.gameState) {
      subscriptionsRef.current.gameState.unsubscribe();
      subscriptionsRef.current.gameState = null;
    }

    // Отписываемся от всех событий
    subscriptionsRef.current.events.forEach(sub => sub.unsubscribe());
    subscriptionsRef.current.events.clear();
  }, []);

  /**
   * Подписаться на gameState
   */
  const subscribeToGameState = useCallback((currentGameId: string) => {
    console.log('[useGameState] Подписка на gameState:', currentGameId);

    const observable = client.subscribe<{
      gameStateUpdated: gql.GameState;
    }>({
      query: gql.GameStateUpdatedDocument,
      variables: {
        gameId: currentGameId,
        since: lastSequenceRef.current || undefined,
      },
    });

    const subscription = observable.subscribe({
      next: ({ data, errors }) => {
        if (errors?.length) {
          setError(new Error(errors[0].message));
          setSyncStatus('error');
          return;
        }

        if (data?.gameStateUpdated) {
          const update = data.gameStateUpdated;

          // Проверяем sequence number
          if (update.sequenceNumber <= lastSequenceRef.current) {
            console.warn('[useGameState] Пропуск устаревшего состояния');
            return;
          }

          // Проверяем gaps
          const expectedSeq = lastSequenceRef.current + 1;
          if (update.sequenceNumber > expectedSeq) {
            console.warn('[useGameState] Обнаружен gap:', expectedSeq, update.sequenceNumber);
            // TODO: Запросить пропущенные события
          }

          lastSequenceRef.current = update.sequenceNumber;

          setGameState({
            gameId: update.gameId,
            sequenceNumber: update.sequenceNumber,
            phase: update.phase,
            turnCount: update.turnCount,
            currentTurnPlayerId: update.currentTurnPlayerId,
            lastUpdate: new Date(),
          });

          setSyncStatus('synced');
          setError(null);
        }
      },
      error: (err) => {
        console.error('[useGameState] Ошибка подписки gameState:', err);
        setError(err);
        setSyncStatus('error');

        // Пытаемся переподключиться
        if (autoReconnect && gameId) {
          reconnectTimeoutRef.current = setTimeout(() => {
            setSyncStatus('connecting');
            subscribeToGameState(gameId);
          }, reconnectDelay);
        }
      },
      complete: () => {
        console.warn('[useGameState] GameState подписка закрыта');
        setSyncStatus('disconnected');
      },
    });

    subscriptionsRef.current.gameState = subscription;
  }, [client, autoReconnect, reconnectDelay, gameId]);

  /**
   * Подписаться на игровые события
   */
  const subscribeToEvents = useCallback((currentGameId: string) => {
    const events = [
      { key: 'attackInitiated', query: gql.AttackInitiatedDocument },
      { key: 'defensePlayed', query: gql.DefensePlayedDocument },
      { key: 'combatResolved', query: gql.CombatResolvedDocument },
      { key: 'playerJoined', query: gql.PlayerJoinedDocument },
      { key: 'playerLeft', query: gql.PlayerLeftDocument },
      { key: 'gameEnded', query: gql.GameEndedDocument },
    ];

    events.forEach(({ key, query }) => {
      const observable = client.subscribe({
        query,
        variables: { gameId: currentGameId },
      });

      const subscription = observable.subscribe({
        next: ({ data, errors }) => {
          if (errors?.length) {
            console.error(`[useGameState] Ошибка события ${key}:`, errors[0].message);
            return;
          }

          const eventData = data?.[key];
          if (eventData) {
            console.log(`[useGameState] Событие ${key}:`, eventData);
            // TODO: Диспатчить события в store
          }
        },
        error: (err) => {
          console.error(`[useGameState] Ошибка подписки ${key}:`, err);
        },
      });

      subscriptionsRef.current.events.set(key, subscription);
    });

    // Отдельно подписываемся на turnChanged (другой формат ответа)
    const turnObservable = client.subscribe<{
      turnChanged: gql.TurnState;
    }>({
      query: gql.TurnChangedDocument,
      variables: { gameId: currentGameId },
    });

    const turnSub = turnObservable.subscribe({
      next: ({ data, errors }) => {
        if (errors?.length) {
          console.error('[useGameState] Ошибка turnChanged:', errors[0].message);
          return;
        }

        if (data?.turnChanged) {
          console.log('[useGameState] Turn changed:', data.turnChanged);
          // TODO: Обновить состояние при смене хода
        }
      },
      error: (err) => {
        console.error('[useGameState] Ошибка подписки turnChanged:', err);
      },
    });

    subscriptionsRef.current.events.set('turnChanged', turnSub);
  }, [client]);

  /**
   * Подключиться к игре
   */
  const connect = useCallback(async () => {
    if (!gameId) {
      console.warn('[useGameState] Нет gameId для подключения');
      return;
    }

    console.log('[useGameState] Подключение к игре:', gameId);
    setSyncStatus('connecting');
    setError(null);

    try {
      // Сначала загружаем начальное состояние
      const { data, errors } = await client.query<{
        gameState: gql.GameStateResponse;
      }>({
        query: gql.GetGameStateDocument,
        variables: { gameId },
        fetchPolicy: 'network-only',
      });

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      if (!data?.gameState) {
        throw new Error('Не удалось загрузить состояние игры');
      }

      // Парсим состояние
      const stateData = typeof data.gameState.state === 'string'
        ? JSON.parse(data.gameState.state)
        : data.gameState.state;

      lastSequenceRef.current = data.gameState.sequenceNumber;

      setGameState({
        gameId,
        sequenceNumber: data.gameState.sequenceNumber,
        phase: data.gameState.phase,
        turnCount: data.gameState.turnCount,
        currentTurnPlayerId: data.gameState.currentTurnPlayerId ?? '',
        lastUpdate: new Date(),
      });

      // Подписываемся на обновления
      subscribeToGameState(gameId);
      subscribeToEvents(gameId);

      setSyncStatus('synced');
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Неизвестная ошибка');
      setError(error);
      setSyncStatus('error');

      // Пытаемся переподключиться
      if (autoReconnect) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectDelay);
      }
    }
  }, [gameId, client, autoReconnect, reconnectDelay, subscribeToGameState, subscribeToEvents]);

  /**
   * Отключиться от игры
   */
  const disconnect = useCallback(() => {
    console.log('[useGameState] Отключение от игры');
    cleanup();
    setSyncStatus('disconnected');
    setGameState(null);
    setError(null);
  }, [cleanup]);

  /**
   * Перзагрузить состояние
   */
  const refetch = useCallback(async () => {
    if (!gameId) return;

    console.log('[useGameState] Перзагрузка состояния');
    cleanup();
    await connect();
  }, [gameId, cleanup, connect]);

  // Автоматическое подключение/отключение при изменении gameId
  useEffect(() => {
    if (gameId) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      cleanup();
    };
  }, [gameId]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    gameState,
    syncStatus,
    error,
    connect,
    disconnect,
    refetch,
    subscriptions: {
      gameState: subscriptionsRef.current.gameState,
      events: subscriptionsRef.current.events,
    },
  };
}

// ------------------------------------------------------------
// Типы для ZenObservable
// ------------------------------------------------------------

declare namespace ZenObservable {
  interface Observer<T> {
    next?(value: T): void;
    error?(error: any): void;
    complete?(): void;
  }

  interface Subscription {
    unsubscribe(): void;
  }

  interface Observable<T> {
    subscribe(observer: Observer<T>): Subscription;
    subscribe(
      onNext?: (value: T) => void,
      onError?: (error: any) => void,
      onComplete?: () => void
    ): Subscription;
  }
}
