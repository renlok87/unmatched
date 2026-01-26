import React from 'react';
import { useGameStore } from '../../store/gameStore';
import { GamePhase } from '../../core/models/types';
import './GameControls.css';

export const GameControls: React.FC = () => {
  const {
    gameState,
    selectedCardId,
    selectedFighterId,
    endTurn,
    getCurrentPhase,
    getRemainingActions,
  } = useGameStore();

  if (!gameState) {
    return null;
  }

  const currentPhase = getCurrentPhase();
  const remainingActions = getRemainingActions();
  const currentPlayer = gameState.players.find(
    p => p.id === gameState.currentTurn.currentPlayerId
  );

  const getPhaseLabel = (phase: GamePhase): string => {
    const labels: Record<GamePhase, string> = {
      [GamePhase.SETUP]: 'Настройка',
      [GamePhase.START_OF_TURN]: 'Начало хода',
      [GamePhase.ACTION_SELECTION]: 'Выбор действия',
      [GamePhase.CARD_PLAY]: 'Играть карту',
      [GamePhase.MOVEMENT]: 'Перемещение',
      [GamePhase.COMBAT]: 'Бой',
      [GamePhase.COMBAT_DEFENSE]: 'Защита',
      [GamePhase.RESOLUTION]: 'Разрешение',
      [GamePhase.END_OF_TURN]: 'Конец хода',
      [GamePhase.GAME_OVER]: 'Игра окончена',
    };
    return labels[phase];
  };

  const getPhaseColor = (phase: GamePhase): string => {
    const colors: Record<GamePhase, string> = {
      [GamePhase.SETUP]: '#6b7280',
      [GamePhase.START_OF_TURN]: '#3b82f6',
      [GamePhase.ACTION_SELECTION]: '#22c55e',
      [GamePhase.CARD_PLAY]: '#a855f7',
      [GamePhase.MOVEMENT]: '#f59e0b',
      [GamePhase.COMBAT]: '#ef4444',
      [GamePhase.COMBAT_DEFENSE]: '#ef4444',
      [GamePhase.RESOLUTION]: '#eab308',
      [GamePhase.END_OF_TURN]: '#6b7280',
      [GamePhase.GAME_OVER]: '#ec4899',
    };
    return colors[phase];
  };

  const canEndTurn = currentPhase === GamePhase.ACTION_SELECTION &&
    (remainingActions === 0 || currentPlayer?.hasPassed);

  return (
    <div className="game-controls">
      <div className="phase-indicator" style={{ borderColor: getPhaseColor(currentPhase) }}>
        <span className="phase-label">Фаза:</span>
        <span className="phase-name" style={{ color: getPhaseColor(currentPhase) }}>
          {getPhaseLabel(currentPhase)}
        </span>
      </div>

      <div className="turn-info">
        <div className="turn-count">Ход: {gameState.turnCount}</div>
        <div className="current-player">{currentPlayer?.name}</div>
        <div className="actions-remaining">
          Действий: {remainingActions}/2
        </div>
      </div>

      {selectedCardId && (
        <div className="selection-info">
          Выбрана карта: {selectedCardId}
        </div>
      )}

      {selectedFighterId && (
        <div className="selection-info">
          Выбран боец: {selectedFighterId}
        </div>
      )}

      <div className="control-buttons">
        {gameState.winner ? (
          <div className="winner-announcement">
            🏆 Победитель: {gameState.players.find(p => p.id === gameState.winner)?.name}
          </div>
        ) : (
          <>
            {currentPhase === GamePhase.COMBAT && (
              <button
                className="btn btn-primary"
                onClick={() => useGameStore.getState().resolveCombat()}
              >
                Разрешить бой
              </button>
            )}

            {canEndTurn && (
              <button className="btn btn-success" onClick={endTurn}>
                Завершить ход
              </button>
            )}

            {!gameState.winner && currentPhase === GamePhase.ACTION_SELECTION && remainingActions > 0 && (
              <button
                className="btn btn-secondary"
                onClick={() => useGameStore.getState().pass()}
              >
                Пас
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default GameControls;
