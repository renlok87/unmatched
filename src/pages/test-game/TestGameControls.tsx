import React from 'react';
import { useTestGameStore } from '@/store/testGameStore';
import './TestGameControls.css';

export const TestGameControls: React.FC = () => {
  const {
    gameState,
    selectedCardId,
    selectedFighterId,
    resetGame,
    endTurn,
    initializeRandomGame,
    selectCard,
    playCard,
  } = useTestGameStore();

  const currentPlayer = useTestGameStore((state) => state.getCurrentPlayer());

  const handleNewGame = async () => {
    resetGame();
    await initializeRandomGame();
  };

  const handlePlayCard = () => {
    if (selectedCardId) {
      playCard(selectedCardId);
    }
  };

  const handleDeselect = () => {
    selectCard(null);
  };

  return (
    <div className="test-game-controls">
      <div className="controls-section">
        <h3 className="controls-title">Управление игрой</h3>

        <div className="controls-buttons">
          <button onClick={handleNewGame} className="btn btn-primary">
            🔄 Новая игра (рандом)
          </button>
          <button onClick={endTurn} className="btn btn-secondary" disabled={!gameState}>
            ⏭️ Конец хода
          </button>
        </div>
      </div>

      {gameState && (
        <div className="controls-section">
          <h3 className="controls-title">Состояние игры</h3>

          <div className="game-stats">
            <div className="stat-item">
              <span className="stat-label">Ход:</span>
              <span className="stat-value">{gameState.turnCount}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Фаза:</span>
              <span className="stat-value">{formatPhase(gameState.phase)}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Текущий игрок:</span>
              <span className="stat-value">{currentPlayer?.name || '-'}</span>
            </div>
          </div>
        </div>
      )}

      {selectedCardId && (
        <div className="controls-section selection-info">
          <h3 className="controls-title">Выбрано</h3>
          <div className="selected-card-info">
            <span className="selected-card-id">Карта: {selectedCardId}</span>
            <button onClick={handlePlayCard} className="btn btn-success btn-sm">
              Играть карту
            </button>
            <button onClick={handleDeselect} className="btn btn-ghost btn-sm">
              Отмена
            </button>
          </div>
        </div>
      )}

      {selectedFighterId && currentPlayer && (
        <div className="controls-section selection-info">
          <h3 className="controls-title">Выбран боец</h3>
          <div className="selected-fighter-info">
            <span className="selected-fighter-id">
              {currentPlayer.fighters.find((f) => f.id === selectedFighterId)?.type === 'hero'
                ? '🦸 Герой'
                : '🧑‍🤝‍🧑 Помощник'}
            </span>
            <span className="selected-fighter-pos">
              {currentPlayer.fighters.find((f) => f.id === selectedFighterId)?.position &&
                `(${currentPlayer.fighters.find((f) => f.id === selectedFighterId)!.position.x}, ${currentPlayer.fighters.find((f) => f.id === selectedFighterId)!.position.y})`
              }
            </span>
          </div>
        </div>
      )}

      {gameState && (
        <div className="controls-section debug-info">
          <details>
            <summary className="debug-summary">Debug (JSON)</summary>
            <pre className="debug-json">
              {JSON.stringify(
                {
                  players: gameState.players.map((p) => ({
                    id: p.id,
                    name: p.name,
                    handSize: p.hand.length,
                    deckSize: p.deck.length,
                    fighters: p.fighters.map((f) => ({
                      id: f.id,
                      type: f.type,
                      health: f.health,
                      maxHealth: f.maxHealth,
                      position: f.position,
                    })),
                  })),
                  turn: gameState.turnCount,
                  phase: gameState.phase,
                },
                null,
                2
              )}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
};

function formatPhase(phase: string): string {
  const phaseNames: Record<string, string> = {
    setup: 'Настройка',
    start_of_turn: 'Начало хода',
    action_selection: 'Выбор действия',
    card_play: 'Игрок карт',
    movement: 'Перемещение',
    combat: 'Бой',
    combat_defense: 'Защита',
    resolution: 'Разрешение',
    end_of_turn: 'Конец хода',
    game_over: 'Игра окончена',
  };
  return phaseNames[phase] || phase;
}
