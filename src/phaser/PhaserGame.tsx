// ============================================================
// PHASER GAME - React компонент обёртка для Phaser
// ============================================================

import { useEffect, useRef, useCallback, useState } from 'react';
import Phaser from 'phaser';
import type { GameState } from '../core/models/types';
import type { PhaserGameEvent, ReactToPhaserEvent } from './types';
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

  /** Selected fighter id from React UI */
  selectedFighterId?: string | null;

  /** Selected card id from React UI */
  selectedCardId?: string | null;

  /** Spaces highlighted by React/game logic */
  highlightedSpaces?: Array<{ x: number; y: number }>;

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
  selectedFighterId = null,
  selectedCardId = null,
  highlightedSpaces = [],
  className = '',
  width = 800,
  height = 600,
}) => {
  const gameRef = useRef<Phaser.Game | null>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [renderScale, setRenderScale] = useState(1);
  const latestGameStateRef = useRef<GameState | null>(gameState ?? null);
  const latestSelectedFighterRef = useRef<string | null>(selectedFighterId);
  const latestSelectedCardRef = useRef<string | null>(selectedCardId);
  const latestHighlightedSpacesRef = useRef(highlightedSpaces);

  /**
   * Отправляет события из React в Phaser
   */
  const sendEventToPhaser = useCallback((event: ReactToPhaserEvent) => {
    if (!gameRef.current) return;

    console.log('PhaserGame: отправка события в Phaser', event);
    gameRef.current.events.emit('react-to-phaser', event);
  }, []);

  /**
   * Обрабатывает события из Phaser и отправляет в React
   */
  const handleGameEvent = useCallback(
    (event: PhaserGameEvent) => {
      console.log('PhaserGame: событие из Phaser', event);
      if (event.type === 'PHASER_READY') {
        const latestState = latestGameStateRef.current;
        if (latestState) {
          sendEventToPhaser({ type: 'UPDATE_STATE', state: latestState });
        }

        sendEventToPhaser({
          type: 'SELECT_FIGHTER',
          fighterId: latestSelectedFighterRef.current,
        });

        sendEventToPhaser({
          type: 'SELECT_CARD',
          cardId: latestSelectedCardRef.current,
        });

        sendEventToPhaser({
          type: 'HIGHLIGHT_SPACES',
          spaces: latestHighlightedSpacesRef.current,
        });
      }
      onGameEvent?.(event);
    },
    [onGameEvent, sendEventToPhaser]
  );

  /**
   * Инициализирует Phaser при монтировании компонента
   */
  useEffect(() => {
    if (!containerRef.current || gameRef.current) {
      return;
    }

    console.log('PhaserGame: инициализация');

    const gameScene = new GameScene(handleGameEvent);

    // Создаём конфигурацию Phaser
    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width,
      height,
      parent: containerRef.current,
      backgroundColor: '#1a1a2e',
      scene: [BootScene, gameScene, UIScene],
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
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

  useEffect(() => {
    const updateScale = () => {
      const parentWidth = shellRef.current?.parentElement?.clientWidth ?? width;
      const viewportWidth =
        typeof window !== 'undefined' ? Math.max(window.innerWidth - 32, 1) : width;
      const availableWidth = Math.min(parentWidth, viewportWidth);
      const nextScale = Math.min(1, availableWidth / width);
      setRenderScale(Number.isFinite(nextScale) && nextScale > 0 ? nextScale : 1);
    };

    updateScale();

    const parent = shellRef.current?.parentElement;
    const resizeObserver =
      typeof ResizeObserver !== 'undefined' && parent
        ? new ResizeObserver(updateScale)
        : null;

    if (resizeObserver && parent) {
      resizeObserver.observe(parent);
    } else {
      window.addEventListener('resize', updateScale);
    }

    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener('resize', updateScale);
    };
  }, [width]);

  /**
   * Обновляет состояние игры в Phaser при изменении пропсов
   */
  useEffect(() => {
    latestGameStateRef.current = gameState ?? null;
    if (!gameRef.current || !gameState) return;

    sendEventToPhaser({
      type: 'UPDATE_STATE',
      state: gameState,
    });
  }, [gameState, sendEventToPhaser]);

  useEffect(() => {
    latestSelectedFighterRef.current = selectedFighterId;
    if (!gameRef.current) return;

    sendEventToPhaser({
      type: 'SELECT_FIGHTER',
      fighterId: selectedFighterId,
    });
  }, [selectedFighterId, sendEventToPhaser]);

  useEffect(() => {
    latestSelectedCardRef.current = selectedCardId;
    if (!gameRef.current) return;

    sendEventToPhaser({
      type: 'SELECT_CARD',
      cardId: selectedCardId,
    });
  }, [selectedCardId, sendEventToPhaser]);

  useEffect(() => {
    latestHighlightedSpacesRef.current = highlightedSpaces;
    if (!gameRef.current) return;

    sendEventToPhaser({
      type: 'HIGHLIGHT_SPACES',
      spaces: highlightedSpaces,
    });
  }, [highlightedSpaces, sendEventToPhaser]);

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
      ref={shellRef}
      className={`phaser-game-shell ${className}`}
      style={{
        width: `${width * renderScale}px`,
        maxWidth: '100%',
        height: `${height * renderScale}px`,
        position: 'relative',
      }}
      data-game-id={gameId}
    >
      <div
        ref={containerRef}
        className="phaser-game-container"
        style={{
          width: `${width}px`,
          height: `${height}px`,
          transform: `scale(${renderScale})`,
          transformOrigin: 'top left',
          position: 'absolute',
          inset: 0,
        }}
        data-game-id={gameId}
      />
    </div>
  );
};

export default PhaserGame;
