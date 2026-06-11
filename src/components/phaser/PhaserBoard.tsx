// ============================================================
// PHASER BOARD - Компонент игрового поля на Phaser
// ============================================================

import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { PhaserGame } from '@/phaser';
import { useGameStore } from '@/store/gameStore';
import type { PhaserGameEvent } from '@/phaser/types';
import './PhaserBoard.css';

interface PhaserBoardProps {
  /** Дополнительный CSS класс */
  className?: string;
}

export const PhaserBoard: React.FC<PhaserBoardProps> = ({ className = '' }) => {
  const { gameId } = useParams<{ gameId: string }>();
  const gameState = useGameStore(state => state.gameState);

  const [phaserReady, setPhaserReady] = useState(false);

  /**
   * Обрабатывает события из Phaser
   */
  const handleGameEvent = useCallback(
    (event: PhaserGameEvent) => {
      console.log('PhaserBoard: событие из Phaser', event);

      switch (event.type) {
        case 'PHASER_READY':
          setPhaserReady(true);
          break;

        case 'FIGHTER_CLICKED':
          useGameStore.getState().selectFighter(event.fighterId);
          break;

        case 'SPACE_CLICKED':
          // Обработка клика по клетке
          const selectedFighterId = useGameStore.getState().selectedFighterId;
          if (selectedFighterId) {
            useGameStore.getState().moveFighter(selectedFighterId, event.position);
          }
          break;

        case 'CARD_CLICKED':
          useGameStore.getState().selectCard(event.cardId);
          break;

        case 'ATTACK_CLICKED':
          useGameStore.getState().attack(event.attackerId, '', event.targetId);
          break;

        default:
          break;
      }
    },
    []
  );

  /**
   * Подсвечивает валидные_move_ при выборе бойца
   */
  useEffect(() => {
    if (!phaserReady) return;

    const selectedFighterId = useGameStore.getState().selectedFighterId;
    if (selectedFighterId) {
      const validMoves = useGameStore.getState().getValidMoves(selectedFighterId);

      // Отправляем событие в Phaser для подсветки
      const gameContainer = document.querySelector('.phaser-game-container');
      if (gameContainer && (gameContainer as any).phaserGame) {
        (gameContainer as any).phaserGame.sendEvent({
          type: 'HIGHLIGHT_SPACES',
          spaces: validMoves,
        });
      }
    }
  }, [phaserReady, gameState?.currentTurn.currentPlayerId]);

  if (!gameId) {
    return (
      <div className="phaser-board phaser-board--error">
        <p>Игра не найдена</p>
      </div>
    );
  }

  return (
    <div className={`phaser-board ${className}`}>
      {!phaserReady && (
        <div className="phaser-board__loading">
          <div className="phaser-board__spinner" />
          <p>Загрузка игрового поля...</p>
        </div>
      )}

      <PhaserGame
        gameId={gameId}
        gameState={gameState || undefined}
        onGameEvent={handleGameEvent}
        width={800}
        height={600}
        className="phaser-board__canvas"
      />

      {/* Отладочная информация */}
      {import.meta.env.DEV && (
        <div className="phaser-board__debug">
          <p>Game ID: {gameId}</p>
          <p>State: {gameState ? 'Загружен' : 'Не загружен'}</p>
          <p>Phaser: {phaserReady ? 'Готов' : 'Загрузка...'}</p>
        </div>
      )}
    </div>
  );
};

export default PhaserBoard;
