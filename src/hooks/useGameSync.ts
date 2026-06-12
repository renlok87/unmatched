import { useEffect, useRef, useCallback, useState } from 'react';
import { apolloClient } from '@/lib/apolloClient';
import * as gql from '@/gql/graphql';
import { useRemoteGameStore } from '@/store/remoteGameStore';

interface UseGameSyncOptions {
  /**
   * Автоматически переподключаться при потере соединения
   */
  autoReconnect?: boolean;

  /**
   * Задержка перед попыткой переподключения (ms)
   */
  reconnectDelay?: number;

  /**
   * Максимальное количество попыток переподключения
   */
  maxReconnectAttempts?: number;

  /**
   * Callback при успешном подключении
   */
  onConnected?: (gameId: string) => void;

  /**
   * Callback при потере соединения
   */
  onDisconnected?: () => void;

  /**
   * Callback при ошибке
   */
  onError?: (error: Error) => void;
}

/**
 * Hook для синхронизации gameState с сервером через WebSocket подписку
 *
 * @example
 * ```tsx
 * function GamePage() {
 *   const { isConnected, isSyncing, error } = useGameSync('game-123');
 *
 *   if (!isConnected) return <Loading />;
 *   if (error) return <Error message={error} />;
 *
 *   return <GameBoard />;
 * }
 * ```
 */
export function useGameSync(
  gameId: string | null,
  options: UseGameSyncOptions = {}
) {
  const {
    autoReconnect = true,
    reconnectDelay = 1000,
    maxReconnectAttempts = 5,
    onConnected,
    onDisconnected,
    onError,
  } = options;

  const subscriptionRef = useRef<{ unsubscribe: () => void } | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);

  const {
    connectToGame,
    disconnect,
    handleSubscriptionState,
    setConnectionStatus,
    connectionStatus,
    syncError,
  } = useRemoteGameStore();

  /**
   * Очистка ресурсов
   */
  const cleanup = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.unsubscribe();
      subscriptionRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  /**
   * Подписка на gameState updates
   */
  const subscribe = useCallback(() => {
    if (!gameId || !isMountedRef.current) return;

    cleanup();

    // НЕ сбрасываем статус в 'connecting': initial load уже завершился
    // ('connected' от connectToGame), а первое событие подписки придёт
    // только при чьём-то ходе — UI висел бы в вечном спиннере

    try {
      const observable = apolloClient.subscribe<{
        gameStateUpdated: Parameters<typeof handleSubscriptionState>[0];
      }>({
        query: gql.GameStateUpdatedDocument,
        variables: {
          gameId,
          // ВАЖНО: бэк сравнивает since с sequenceNumber (НЕ timestamp!) —
          // Date.now()/1000 отфильтровывал ВСЕ события, подписка молчала.
          // При reconnect lastSequenceNumber отсечёт уже принятые снапшоты.
          since: useRemoteGameStore.getState().lastSequenceNumber || undefined,
        },
      });

      subscriptionRef.current = observable.subscribe({
        next: (data: any) => {
          // Check if component is still mounted
          if (!isMountedRef.current) {
            console.warn('[useGameSync] Component unmounted, ignoring event');
            return;
          }

          if (!data?.gameStateUpdated) return;

          // Обновляем статус соединения (через getState — connectionStatus
          // в deps subscribe вызывал пересоздание подписки и цикл
          // connectToGame → ре-маунт Phaser)
          if (useRemoteGameStore.getState().connectionStatus !== 'connected') {
            setConnectionStatus('connected');
            reconnectAttemptsRef.current = 0;
            onConnected?.(gameId);
          }

          // Полный wire-снапшот → applyWireState (guard по seq внутри)
          handleSubscriptionState(data.gameStateUpdated);
        },
        error: (error: unknown) => {
          // Check if component is still mounted
          if (!isMountedRef.current) {
            console.warn('[useGameSync] Component unmounted, ignoring error');
            return;
          }

          console.error('[useGameSync] Subscription error:', error);

          setConnectionStatus('error');

          const errorObj = error instanceof Error ? error : new Error(String(error));
          onError?.(errorObj);

          // Пытаемся переподключиться
          if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts && isMountedRef.current) {
            reconnectTimeoutRef.current = setTimeout(() => {
              if (!isMountedRef.current) return;

              reconnectAttemptsRef.current++;
              console.log(`[useGameSync] Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
              setConnectionStatus('reconnecting');
              subscribe();
            }, reconnectDelay * reconnectAttemptsRef.current); // Экспоненциальная задержка
          } else {
            onDisconnected?.();
          }
        },
        complete: () => {
          // Check if component is still mounted
          if (!isMountedRef.current) {
            console.warn('[useGameSync] Component unmounted, subscription completed');
            return;
          }

          console.warn('[useGameSync] Subscription completed (connection closed)');
          setConnectionStatus('disconnected');
          onDisconnected?.();

          // Пытаемся переподключиться
          if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts && isMountedRef.current) {
            reconnectTimeoutRef.current = setTimeout(() => {
              if (!isMountedRef.current) return;

              reconnectAttemptsRef.current++;
              setConnectionStatus('reconnecting');
              subscribe();
            }, reconnectDelay);
          }
        },
      });
    } catch (error) {
      console.error('[useGameSync] Failed to create subscription:', error);
      setConnectionStatus('error');

      const errorObj = error instanceof Error ? error : new Error(String(error));
      onError?.(errorObj);
    }
    // ВАЖНО: НЕ добавлять connectionStatus в deps — пересоздание subscribe
    // перезапускало главный effect (connectToGame) по кругу
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    gameId,
    cleanup,
    setConnectionStatus,
    handleSubscriptionState,
    onConnected,
    onDisconnected,
    onError,
    autoReconnect,
    maxReconnectAttempts,
    reconnectDelay,
  ]);

  /**
   * Подключение к игре при монтировании или изменении gameId
   */
  useEffect(() => {
    isMountedRef.current = true;

    if (!gameId) {
      cleanup();
      disconnect();
      return;
    }

    // Сначала загружаем начальное состояние
    connectToGame(gameId)
      .then(() => {
        // Проверяем, что компонент всё ещё смонтирован
        if (!isMountedRef.current) {
          console.warn('[useGameSync] Component unmounted during connectToGame');
          return;
        }

        // Затем подписываемся на обновления
        subscribe();
      })
      .catch((error) => {
        // Проверяем, что компонент всё ещё смонтирован
        if (!isMountedRef.current) {
          console.warn('[useGameSync] Component unmounted during connectToGame error');
          return;
        }

        console.error('[useGameSync] Failed to connect to game:', error);
        setConnectionStatus('error');
        onError?.(error);
      });

    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, [gameId, connectToGame, disconnect, subscribe, cleanup, setConnectionStatus, onError]);

  return {
    isConnected: connectionStatus === 'connected' || connectionStatus === 'reconnecting',
    isConnecting: connectionStatus === 'connecting',
    isReconnecting: connectionStatus === 'reconnecting',
    hasError: connectionStatus === 'error',
    error: syncError,
    connectionStatus,
  };
}

/**
 * Hook для подписки на специфические игровые события
 *
 * @example
 * ```tsx
 * function CombatLog() {
 *   const events = useGameEvents('game-123', ['ATTACK', 'DEFEND']);
 *
 *   return (
 *     <ul>
 *       {events.map((event) => (
 *         <li key={event.sequenceNumber}>{event.type}</li>
 *       ))}
 *     </ul>
 *   );
 * }
 * ```
 */
export interface GameEvent {
  type: string;
  gameId: string;
  sequenceNumber: number;
  timestamp: number;
  payload: unknown;
}

export function useGameEvents(
  gameId: string | null,
  eventTypes: string[] = []
): GameEvent[] {
  const [events, setEvents] = useState<GameEvent[]>([]);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;

    if (!gameId) return;

    const observable = apolloClient.subscribe<{
      gameStateUpdated: GameEvent;
    }>({
      query: gql.GameStateUpdatedDocument,
      variables: { gameId },
    });

    const subscription = observable.subscribe({
      next: (data: any) => {
        // Check if component is still mounted
        if (!isMountedRef.current) {
          console.warn('[useGameEvents] Component unmounted, ignoring event');
          return;
        }

        if (!data?.gameStateUpdated) return;

        const event = data.gameStateUpdated;

        // Фильтруем по типу событий
        if (eventTypes.length === 0 || eventTypes.includes(event.type)) {
          setEvents((prev) => [...prev, event]);
        }
      },
    });

    return () => {
      isMountedRef.current = false;
      subscription.unsubscribe();
    };
  }, [gameId, eventTypes]);

  return events;
}
