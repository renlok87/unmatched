// ============================================================
// PHASER GAME WITH BACKEND INTEGRATION
// ============================================================
//
// Пример компонента для интеграции Phaser с бэкендом
//
// Использование:
// ```tsx
// import { PhaserGameWithBackend } from '@/phaser/components/PhaserGameWithBackend';
//
// <PhaserGameWithBackend
//   gameId={gameId}
//   width={800}
//   height={600}
//   onStateUpdate={(state) => console.log('State updated:', state)}
//   onError={(error) => console.error('Game error:', error)}
// />
// ```

import { useEffect, useRef, useState } from 'react';
import Phaser from 'phaser';
import { apolloClient } from '@/lib/apolloClient';
import { GameActions, SubscriptionHandler } from '../network';
import { GameStateBridge } from '../state';
import { BootScene } from '../scenes/BootScene';
import type { GameStateUpdate, GameEvent } from '../network';

// ------------------------------------------------------------
// Типы пропсов
// ------------------------------------------------------------

export interface PhaserGameWithBackendProps {
  /** ID игры */
  gameId: string;

  /** Ширина игрового поля */
  width?: number;

  /** Высота игрового поля */
  height?: number;

  /** CSS класс контейнера */
  className?: string;

  /** Callback при обновлении состояния */
  onStateUpdate?: (update: GameStateUpdate) => void;

  /** Callback при игровом событии */
  onGameEvent?: (event: GameEvent) => void;

  /** Callback при ошибке */
  onError?: (error: string) => void;

  /** Показывать отладочную информацию */
  debug?: boolean;
}

// ------------------------------------------------------------
// Компонент
// ------------------------------------------------------------

/**
 * PhaserGameWithBackend - компонент для запуска Phaser игры
 * с полной интеграцией с GraphQL бэкендом
 *
 * Функционал:
 * - Создаёт Phaser инстанс
 * - Настраивает WebSocket подписки
 * - Управляет синхронизацией состояния
 * - Обрабатывает игровые действия
 */
export function PhaserGameWithBackend({
  gameId,
  width = 800,
  height = 600,
  className = '',
  onStateUpdate,
  onGameEvent,
  onError,
  debug = false,
}: PhaserGameWithBackendProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const phaserRef = useRef<Phaser.Game | null>(null);
  const subscriptionHandlerRef = useRef<SubscriptionHandler | null>(null);
  const stateBridgeRef = useRef<GameStateBridge | null>(null);
  const gameActionsRef = useRef<GameActions | null>(null);

  const [isReady, setIsReady] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const [currentPhase, setCurrentPhase] = useState<string>('-');
  const [turnCount, setTurnCount] = useState<number>(0);

  // Инициализация Phaser
  useEffect(() => {
    if (!containerRef.current) return;

    console.log('[PhaserGameWithBackend] Инициализация Phaser для игры:', gameId);

    // Создаём инстанс Phaser
    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width,
      height,
      parent: containerRef.current,
      backgroundColor: '#1a1a2e',
      scene: [BootScene],
      physics: {
        default: 'arcade',
        arcade: {
          gravity: { x: 0, y: 0 },
          debug: false,
        },
      },
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
    };

    const game = new Phaser.Game(config);
    phaserRef.current = game;

    // Создаём компоненты интеграции
    gameActionsRef.current = new GameActions();

    // Ожидаем готовности сцены
    const handleReady = () => {
      console.log('[PhaserGameWithBackend] Phaser готов');
      setIsReady(true);

      // После готовности создаём обработчик подписки
      if (game.scene.keys['GameScene']) {
        const gameScene = game.scene.keys['GameScene'] as any;

        stateBridgeRef.current = new GameStateBridge(
          gameScene,
          gameActionsRef.current,
          gameId,
          {
            enableOptimisticUpdates: true,
            rollbackOnError: true,
          }
        );

        subscriptionHandlerRef.current = new SubscriptionHandler(
          gameScene,
          gameId,
          apolloClient,
          {
            onStateUpdate: (update) => {
              console.log('[PhaserGameWithBackend] State update:', update);
              setCurrentPhase(update.phase);
              setTurnCount(update.turnCount);
              onStateUpdate?.(update);
            },
            onGameEvent: (event) => {
              console.log('[PhaserGameWithBackend] Game event:', event.type);
              onGameEvent?.(event);
            },
            onTurnChanged: (turn) => {
              console.log('[PhaserGameWithBackend] Turn changed:', turn);
              setTurnCount(turn.turnCount);
            },
            onError: (error) => {
              console.error('[PhaserGameWithBackend] Subscription error:', error);
              setConnectionStatus('error');
              onError?.(error.message);
            },
            onConnecting: () => {
              console.log('[PhaserGameWithBackend] Connecting...');
              setConnectionStatus('connecting');
            },
            onConnected: () => {
              console.log('[PhaserGameWithBackend] Connected!');
              setConnectionStatus('connected');
            },
            onDisconnected: () => {
              console.log('[PhaserGameWithBackend] Disconnected');
              setConnectionStatus('disconnected');
            },
            onReconnecting: () => {
              console.log('[PhaserGameWithBackend] Reconnecting...');
              setConnectionStatus('connecting');
            },
          }
        );

        // Подписываемся на события игры
        subscriptionHandlerRef.current.subscribe();
      }
    };

    // Слушаем событие готовности от Phaser
    game.events.on('ready', handleReady);

    // Очистка при размонтировании
    return () => {
      console.log('[PhaserGameWithBackend] Очистка');

      // Отписываемся от событий
      if (subscriptionHandlerRef.current) {
        subscriptionHandlerRef.current.unsubscribe();
      }

      // Уничтожаем Phaser
      game.destroy(true);
      phaserRef.current = null;
    };
  }, [gameId, width, height]); // eslint-disable-line react-hooks/exhaustive-deps

  // Отображение статуса соединения
  const getStatusBadge = () => {
    const colors = {
      disconnected: 'bg-gray-500',
      connecting: 'bg-yellow-500',
      connected: 'bg-green-500',
      error: 'bg-red-500',
    };

    const labels = {
      disconnected: 'Отключено',
      connecting: 'Подключение...',
      connected: 'Подключено',
      error: 'Ошибка',
    };

    return (
      <span className={`inline-flex items-center px-2 py-1 rounded text-xs text-white ${colors[connectionStatus]}`}>
        {labels[connectionStatus]}
      </span>
    );
  };

  return (
    <div className={`relative ${className}`}>
      {/* Отладочная информация */}
      {debug && (
        <div className="absolute top-0 left-0 right-0 bg-black/80 text-white p-2 z-10 flex justify-between items-center text-sm">
          <div className="flex gap-4">
            <span>Игра: {gameId.substring(0, 8)}...</span>
            <span>Фаза: {currentPhase}</span>
            <span>Ход: {turnCount}</span>
          </div>
          {getStatusBadge()}
        </div>
      )}

      {/* Контейнер для Phaser */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Индикатор загрузки */}
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
          <div className="text-white text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4" />
            <p>Загрузка игры...</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Хук для использования внутри компонентов
// ------------------------------------------------------------

/**
 * usePhaserGameActions - хук для выполнения действий в Phaser игре
 *
 * Возвращает методы для выполнения всех игровых действий.
 */
export function usePhaserGameActions(gameId: string | null) {
  const [isPending, setIsPending] = useState(false);

  const maneuver = async (params: {
    fighterId: string;
    cardId: string;
    path: { x: number; y: number }[];
  }) => {
    if (!gameId) return { success: false, error: 'Нет активной игры' };

    setIsPending(true);
    try {
      const { data, errors } = await apolloClient.mutate({
        mutation: (await import('@/gql')).ManeuverDocument,
        variables: {
          input: {
            gameId,
            fighterId: params.fighterId,
            cardId: params.cardId,
            path: params.path,
          },
        },
      });

      if (errors?.length) {
        return { success: false, error: errors[0].message };
      }

      return { success: true, data };
    } finally {
      setIsPending(false);
    }
  };

  const attack = async (params: {
    attackerId: string;
    targetId: string;
    cardId: string;
  }) => {
    if (!gameId) return { success: false, error: 'Нет активной игры' };

    setIsPending(true);
    try {
      const { data, errors } = await apolloClient.mutate({
        mutation: (await import('@/gql')).AttackDocument,
        variables: {
          input: {
            gameId,
            attackerId: params.attackerId,
            targetId: params.targetId,
            cardId: params.cardId,
          },
        },
      });

      if (errors?.length) {
        return { success: false, error: errors[0].message };
      }

      return { success: true, data };
    } finally {
      setIsPending(false);
    }
  };

  const endTurn = async () => {
    if (!gameId) return { success: false, error: 'Нет активной игры' };

    setIsPending(true);
    try {
      const { data, errors } = await apolloClient.mutate({
        mutation: (await import('@/gql')).EndTurnDocument,
        variables: { input: { gameId } },
      });

      if (errors?.length) {
        return { success: false, error: errors[0].message };
      }

      return { success: true, data };
    } finally {
      setIsPending(false);
    }
  };

  return {
    maneuver,
    attack,
    endTurn,
    isPending,
  };
}

export default PhaserGameWithBackend;
