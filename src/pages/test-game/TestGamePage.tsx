import React, { useEffect, useMemo, useState } from 'react';
import { PhaserGame } from '@/phaser';
import type { PhaserGameEvent } from '@/phaser/types';
import { GameEngine } from '@/core/engine/GameEngine';
import { getDefaultBoardId } from '@/core/data/boards';
import { useTestGameStore } from '@/store/testGameStore';
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

  const [showGameScene, setShowGameScene] = useState(true);
  const demoGameState = useMemo(() => {
    const engine = new GameEngine();
    return engine.initializeGame({
      players: [
        { id: 'player1', name: 'Ms. Marvel', heroId: 'ms-marvel' },
        { id: 'player2', name: 'Daredevil', heroId: 'daredevil' },
      ],
      boardId: getDefaultBoardId(),
    });
  }, []);

  useEffect(() => {
    loadHeroes();
    loadBoards();
  }, [loadHeroes, loadBoards]);

  useEffect(() => {
    console.log('TestGamePage state:', {
      isLoading,
      error,
      gameState: Boolean(gameState),
      allHeroesLength: allHeroes?.length,
    });
  }, [isLoading, error, gameState, allHeroes]);

  const handleCardClick = (cardId: string) => {
    selectCard(selectedCardId === cardId ? null : cardId);
  };

  const handleFighterSelect = (fighterId: string) => {
    selectFighter(fighterId);
  };

  const handleSpaceClick = (position: { x: number; y: number }) => {
    if (selectedFighterId && highlightedSpaces.some(space => space.x === position.x && space.y === position.y)) {
      useTestGameStore.getState().moveFighter(selectedFighterId, position);
    }
  };

  const handlePhaserEvent = (event: PhaserGameEvent) => {
    switch (event.type) {
      case 'FIGHTER_CLICKED':
        handleFighterSelect(event.fighterId);
        break;
      case 'SPACE_CLICKED':
        handleSpaceClick(event.position);
        break;
      case 'CARD_CLICKED':
        handleCardClick(event.cardId);
        break;
      default:
        break;
    }
  };

  if (error) {
    return (
      <div className="test-game-page">
        <header className="test-game-header">
          <div className="header-content">
            <h1 className="page-title">Test Game</h1>
            <button onClick={loadHeroes} className="btn btn-ghost btn-sm">Retry API</button>
          </div>
        </header>

        <div className="test-game__fallback">
          <p className="error-text">API unavailable: {error}. Showing local Phaser demo.</p>
          <div className="board-wrapper">
            <PhaserGame
              gameId={demoGameState.id}
              gameState={demoGameState}
              selectedFighterId={selectedFighterId}
              selectedCardId={selectedCardId}
              highlightedSpaces={highlightedSpaces}
              onGameEvent={handlePhaserEvent}
              width={800}
              height={600}
              className="test-game__phaser-scene"
            />
          </div>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="test-game-page" style={{ padding: '20px', color: 'white' }}>
        <p>Loading hero data...</p>
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
          <h1 className="page-title">Test Game</h1>
          <div className="header-actions">
            <button
              onClick={() => setShowGameScene(!showGameScene)}
              className="btn btn-ghost btn-sm"
            >
              {showGameScene ? 'Hide' : 'Show'} Phaser
            </button>
          </div>
        </div>
      </header>

      <div className="test-game__main">
        <div className="test-game__board-section">
          {showGameScene && (
            <div className="board-wrapper">
              <PhaserGame
                gameId={gameState.id}
                gameState={gameState}
                selectedFighterId={selectedFighterId}
                selectedCardId={selectedCardId}
                highlightedSpaces={highlightedSpaces}
                onGameEvent={handlePhaserEvent}
                width={800}
                height={600}
                className="test-game__phaser-scene"
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
        <span className="footer-text">Test page for the Phaser game scene.</span>
      </footer>
    </div>
  );
};

export default TestGamePage;
