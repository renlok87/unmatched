// ============================================================
// PHASER GAME - React компонент обёртка для Phaser
// ============================================================

import { useEffect, useRef, useCallback } from 'react';
import Phaser from 'phaser';
import type { GameState } from '../core/models/types';
import type { PhaserGameEvent, ReactToPhaserEvent, PhaserGameState } from './types';
import { GameScene } from './scenes/GameScene';
import { BootScene } from './scenes/BootScene';
import { UIScene } from './scenes/UIScene';

interface PhaserGameProps {
  /** ID игры */
  gameId: string;

  /** Состояние игры из backend/engine */
  gameState?: GameState | null;

  /** Callback для отправки событий в React */
  onGameEvent?: (event: PhaserGameEvent) => void;

  /** CSS класс для контейнера */
  className?: string;

  /** Ширина канваса */
  width?: number;

  /** Высота канваса */
  height?: number;
}

export const PhaserGame: React.FC<PhaserGameProps> = ({
  gameId,
  gameState,
  onGameEvent,
  className = '',
  width = 800,
  height = 600,
}) => {
  const gameRef = useRef<Phaser.Game | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  /**
   * Обрабатывает события из Phaser и отправляет в React
   */
  const handleGameEvent = useCallback(
    (event: PhaserGameEvent) => {
      console.log('PhaserGame: событие из Phaser', event);
      onGameEvent?.(event);
    },
    [onGameEvent]
  );

  /**
   * Инициализирует Phaser при монтировании компонента
   */
  useEffect(() => {
    if (!containerRef.current || gameRef.current) {
      return;
    }

    console.log('PhaserGame: инициализация');

    // Создаём конфигурацию Phaser
    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width,
      height,
      parent: containerRef.current,
      backgroundColor: '#1a1a2e',
      scene: [BootScene, () => new GameScene(handleGameEvent), UIScene],
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
      physics: {
        default: null, // Не используем физику для карточной игры
      },
      render: {
        pixelArt: false,
        antialias: true,
      },
      dom: {
        createContainer: true,
      },
    };

    // Создаём экземпляр игры
    gameRef.current = new Phaser.Game(config);

    // Очищаем при размонтировании
    return () => {
      console.log('PhaserGame: уничтожение');
      if (gameRef.current) {
        gameRef.current.destroy(true);
        gameRef.current = null;
      }
    };
  }, [width, height, handleGameEvent]);

  /**
   * Отправляет события из React в Phaser
   */
  const sendEventToPhaser = useCallback((event: ReactToPhaserEvent) => {
    if (!gameRef.current) return;

    console.log('PhaserGame: отправка события в Phaser', event);
    gameRef.current.events.emit('react-to-phaser', event);
  }, []);

  /**
   * Обновляет состояние игры в Phaser при изменении пропсов
   */
  useEffect(() => {
    if (!gameRef.current || !gameState) return;

    sendEventToPhaser({
      type: 'UPDATE_STATE',
      state: gameState,
    });
  }, [gameState, sendEventToPhaser]);

  /**
   * Предоставляет API для управления игрой извне
   */
  useEffect(() => {
    // Привязываем API к DOM элементу для внешнего доступа
    if (containerRef.current) {
      (containerRef.current as any).phaserGame = {
        sendEvent: sendEventToPhaser,
        getGame: () => gameRef.current,
      };
    }
  }, [sendEventToPhaser]);

  return (
    <div
      ref={containerRef}
      className={`phaser-game-container ${className}`}
      style={{
        width: `${width}px`,
        height: `${height}px`,
        position: 'relative',
      }}
      data-game-id={gameId}
    />
  );
};

export default PhaserGame;
