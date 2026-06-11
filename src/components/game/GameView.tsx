import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useGameSync } from '@/hooks/useGameSync';
import { GameHeader } from './GameHeader';
import { TurnIndicator } from './TurnIndicator';
import { ActionButtons } from './ActionButtons';
import { OpponentHandView } from './OpponentHandView';
import { BoardView } from '@/components/board/BoardView';
import { PhaserBoard } from '@/components/phaser';
import { HandView } from '@/components/cards/HandView';
import { GameControls } from '@/components/controls/GameControls';
import { GameErrorBoundary } from './GameErrorBoundary';
import { GameChat } from '@/components/chat';
import { VictoryScreen, useVictoryScreen } from './VictoryScreen';
import { Modal } from '@/design-system/components/Modal';
import { Button } from '@/design-system/components/Button';
import './GameView.css';

// Флаг для использования Phaser вместо CSS BoardView
// TODO: Вынести в фич-тoggles или настройки пользователя
const USE_PHASER = import.meta.env.VITE_USE_PHASER === 'true' || false;

export const GameView = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const { isConnecting, hasError, error, connectionStatus } = useGameSync(gameId || '');

  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  // Hook для управления экраном победы
  const { result: victoryResult, visible: victoryVisible, show: _showVictory, hide: hideVictory } = useVictoryScreen();

  const handleLeave = () => {
    setShowLeaveModal(true);
  };

  const confirmLeave = () => {
    navigate('/lobby');
  };

  const handleSettings = () => {
    setShowSettingsModal(true);
  };

  const handleEndTurn = () => {
    console.log('End turn mutation will be called here');
  };

  const handlePass = () => {
    console.log('Pass mutation will be called here');
  };

  if (isConnecting) {
    return (
      <div className="game-view game-view--loading">
        <div className="game-view__loading-spinner" />
        <p>Подключение к игре...</p>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="game-view game-view--error">
        <div className="game-view__error-content">
          <div className="game-view__error-icon">⚠️</div>
          <h2>Ошибка подключения</h2>
          <p>{error}</p>
          <Button variant="primary" onClick={() => window.location.reload()}>
            Перезагрузить страницу
          </Button>
          <Button variant="ghost" onClick={() => navigate('/lobby')}>
            Вернуться в лобби
          </Button>
        </div>
      </div>
    );
  }

  const mockTurnNumber = 1;
  const mockRoundNumber = 1;

  return (
    <GameErrorBoundary>
      <div className="game-view">
        <GameHeader
          turnNumber={mockTurnNumber}
          roundNumber={mockRoundNumber}
          isConnected={connectionStatus === 'connected'}
          onSettings={handleSettings}
          onLeave={handleLeave}
        />

        <div className="game-view__content">
          <div className="game-view__top">
            <OpponentHandView cardCount={5} />
            <TurnIndicator
              currentPlayer={{
                id: '1',
                userId: 'user1',
                username: 'Игрок 1',
              }}
              isYourTurn={true}
              timeRemaining={60}
            />
          </div>

          <div className="game-view__middle">
            {USE_PHASER ? (
              <PhaserBoard />
            ) : (
              <BoardView interactive={true} />
            )}
          </div>

          <div className="game-view__bottom">
            <div className="game-view__hand-section">
              <HandView />
            </div>

            <div className="game-view__actions-section">
              <ActionButtons
                canEndTurn={true}
                canPass={true}
                onEndTurn={handleEndTurn}
                onPass={handlePass}
              />
            </div>
          </div>

          <div className="game-view__controls">
            <GameControls />
          </div>

          <div className="game-view__chat">
            {gameId && <GameChat gameId={gameId} />}
          </div>
        </div>

        <Modal
          isOpen={showLeaveModal}
          onClose={() => setShowLeaveModal(false)}
          title="Покинуть игру"
        >
          <div className="game-view__modal-content">
            <p>Вы уверены, что хотите покинуть игру?</p>
            <div className="game-view__modal-actions">
              <Button variant="ghost" onClick={() => setShowLeaveModal(false)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={confirmLeave}>
                Покинуть
              </Button>
            </div>
          </div>
        </Modal>

        <Modal
          isOpen={showSettingsModal}
          onClose={() => setShowSettingsModal(false)}
          title="Настройки"
        >
          <div className="game-view__modal-content">
            <p>Настройки игры</p>
          </div>
        </Modal>

        {/* Экран победы/поражения */}
        <VictoryScreen
          result={victoryResult}
          visible={victoryVisible}
          playerName="You"
          opponentName="Opponent"
          onPlayAgain={() => {
            hideVictory();
            navigate('/matchmaking');
          }}
          onReturnToLobby={() => {
            hideVictory();
            navigate('/lobby');
          }}
        />
      </div>
    </GameErrorBoundary>
  );
};

export default GameView;