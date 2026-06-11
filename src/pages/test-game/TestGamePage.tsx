import React, { useEffect, useState } from 'react';
import { useTestGameStore } from '@/store/testGameStore';
import { BoardView } from '@/components/board/BoardView';
import { PlayerArea } from './PlayerArea';
import { TestGameControls } from './TestGameControls';
import { TestGameLanding } from './TestGameLanding';
import './TestGamePage.css';

export const TestGamePage: React.FC = () => {
  const {
    gameState,
    isLoading,
    error,
    allHeroes,
    loadHeroes,
    loadBoards,
    selectCard,
    selectFighter,
    selectedCardId,
    selectedFighterId,
    highlightedSpaces,
  } = useTestGameStore();

  const [showDebugBoard, setShowDebugBoard] = useState(true);

  useEffect(() => {
    console.log('TestGamePage mounted');
    loadHeroes();
    loadBoards();
  }, []);

  // Debug logging
  useEffect(() => {
    console.log('TestGamePage state:', { isLoading, error, gameState: !!gameState, allHeroesLength: allHeroes?.length });
  }, [isLoading, error, gameState, allHeroes]);

  const handleCardClick = (cardId: string) => {
    if (selectedCardId === cardId) {
      selectCard(null);
    } else {
      selectCard(cardId);
    }
  };

  const handleFighterSelect = (fighterId: string) => {
    selectFighter(fighterId);
  };

  const handleSpaceClick = (position: { x: number; y: number }) => {
    if (selectedFighterId && highlightedSpaces.some((s) => s.x === position.x && s.y === position.y)) {
      useTestGameStore.getState().moveFighter(selectedFighterId, position);
    }
  };

  // Debug: show what's happening
  if (error) {
    return (
      <div className="test-game-page" style={{ padding: '20px', color: 'white' }}>
        <h2>Ошибка: {error}</h2>
        <button onClick={loadHeroes}>Попробовать снова</button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="test-game-page" style={{ padding: '20px', color: 'white' }}>
        <p>Загрузка данных о героях...</p>
      </div>
    );
  }

  if (!gameState) {
    return <TestGameLanding />;
  }

  const [player1, player2] = gameState.players;
  const currentPlayerId = gameState.currentTurn.currentPlayerId;
  const player1IsCurrent = player1.id === currentPlayerId;
  const player2IsCurrent = player2.id === currentPlayerId;

  return (
    <div className="test-game-page">
      <header className="test-game-header">
        <div className="header-content">
          <h1 className="page-title">🎮 Тестовая игра Unmatched</h1>
          <div className="header-actions">
            <button
              onClick={() => setShowDebugBoard(!showDebugBoard)}
              className="btn btn-ghost btn-sm"
            >
              {showDebugBoard ? 'Скрыть' : 'Показать'} доску
            </button>
          </div>
        </div>
      </header>

      <div className="test-game__main">
        <div className="test-game__board-section">
          {showDebugBoard && (
            <div className="board-wrapper">
              <BoardView
                interactive={true}
                gameState={gameState}
                highlightedSpaces={highlightedSpaces}
                onFighterSelect={handleFighterSelect}
                onSpaceClick={handleSpaceClick}
              />
            </div>
          )}
        </div>

        <div className="test-game__players-section">
          <div className="players-container">
            <PlayerArea
              player={player1}
              isCurrent={player1IsCurrent}
              showCards={true}
              onCardClick={handleCardClick}
              selectedCardId={selectedCardId}
            />
            <div className="vs-divider">
              <span className="vs-text">VS</span>
            </div>
            <PlayerArea
              player={player2}
              isCurrent={player2IsCurrent}
              showCards={true}
              onCardClick={handleCardClick}
              selectedCardId={selectedCardId}
            />
          </div>
        </div>

        <div className="test-game__controls-section">
          <TestGameControls />
        </div>
      </div>

      <footer className="test-game-footer">
        <span className="footer-text">
          Тестовая страница для отладки игрового интерфейса
        </span>
      </footer>
    </div>
  );
};

export default TestGamePage;
