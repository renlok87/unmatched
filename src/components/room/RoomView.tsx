import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRoomStore } from '@/store/roomStore';
import { PlayerSlots } from './PlayerSlots';
import { ReadyStatus } from './ReadyStatus';
import { RoomChat } from './RoomChat';
import { InviteLink } from './InviteLink';
import { FighterPlacement, type Fighter, type SpawnZone } from './FighterPlacement';
import { GameCountdown } from './GameCountdown';
import { Button } from '@/design-system/components/Button';
import { Modal } from '@/design-system/components/Modal';
import './RoomView.css';

export const RoomView: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const {
    game,
    isHost,
    allReady,
    loading,
    error,
    mount,
    unmount,
    loadRoom,
    setReady,
    leaveRoom,
    startGame,
    clearError,
  } = useRoomStore();

  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [showCountdown, setShowCountdown] = useState(false);
  const [placedFighters, setPlacedFighters] = useState<Record<string, string>>({});

  useEffect(() => {
    mount();

    if (gameId) {
      loadRoom(gameId);

      const interval = setInterval(() => {
        loadRoom(gameId);
      }, 3000);

      return () => {
        clearInterval(interval);
        unmount();
      };
    }
  }, [gameId]);

  const handleLeaveRoom = async () => {
    if (!gameId) return;

    try {
      await leaveRoom(gameId);
      navigate('/lobby');
    } catch (err) {
      console.error('Failed to leave room:', err);
    }
  };

  const handleStartGame = async () => {
    if (!gameId || !allReady) return;

    setShowCountdown(true);
  };

  const handleCountdownComplete = async () => {
    if (!gameId) return;

    try {
      await startGame(gameId);
      navigate(`/game/${gameId}`);
    } catch (err) {
      console.error('Failed to start game:', err);
      setShowCountdown(false);
    }
  };

  const handlePlaceFighter = (fighterId: string, zoneId: string) => {
    setPlacedFighters((prev) => ({ ...prev, [fighterId]: zoneId }));
  };

  const handleRemoveFighter = (fighterId: string) => {
    setPlacedFighters((prev) => {
      const next = { ...prev };
      delete next[fighterId];
      return next;
    });
  };

  const mockFighters: Fighter[] = [
    { id: '1', name: 'Алиса', type: 'hero', health: 5, maxHealth: 5 },
    { id: '2', name: 'Белый Кролик', type: 'sidekick', health: 2, maxHealth: 2 },
  ];

  const mockSpawnZones: SpawnZone[] = [
    { id: 'zone1', x: 10, y: 40, width: 20, height: 20, color: 'blue', label: 'Зона 1' },
    { id: 'zone2', x: 40, y: 40, width: 20, height: 20, color: 'green', label: 'Зона 2' },
    { id: 'zone3', x: 70, y: 40, width: 20, height: 20, color: 'yellow', label: 'Зона 3' },
  ];

  const allFightersPlaced = mockFighters.every((f) => placedFighters[f.id]);

  if (loading && !game) {
    return (
      <div className="room-view room-view--loading">
        <div className="loading-spinner" />
        <p>Загрузка комнаты...</p>
      </div>
    );
  }

  if (!game) {
    return (
      <div className="room-view room-view--error">
        <p>Комната не найдена</p>
        <Button onClick={() => navigate('/lobby')}>Вернуться в лобби</Button>
      </div>
    );
  }

  const currentUserId = localStorage.getItem('userId');
  const currentPlayer = game.players.find((p) => p.userId === currentUserId);
  const isReady = currentPlayer?.isReady || false;

  return (
    <div className="room-view">
      <div className="room-view__header">
        <h1 className="room-view__title">Комната {game.code || `#${game.id.slice(0, 8)}`}</h1>
        <div className="room-view__actions">
          {isHost && (
            <Button
              variant="success"
              onClick={handleStartGame}
              disabled={!allReady}
            >
              Начать игру
            </Button>
          )}
          <Button variant="danger" onClick={() => setShowLeaveModal(true)}>
            Покинуть комнату
          </Button>
        </div>
      </div>

      {error && (
        <div className="room-view__error">
          <span>⚠️</span>
          <span>{error}</span>
          <button onClick={clearError}>✕</button>
        </div>
      )}

      <div className="room-view__content">
        <div className="room-view__main">
          <PlayerSlots
            players={game.players}
            mode={game.mode}
            currentUserId={currentUserId}
          />
          <ReadyStatus
            isReady={isReady}
            onToggle={() => setReady(gameId!)}
            disabled={loading}
            allReady={allReady}
          />
          <FighterPlacement
            fighters={mockFighters}
            spawnZones={mockSpawnZones}
            placedFighters={placedFighters}
            onPlaceFighter={handlePlaceFighter}
            onRemoveFighter={handleRemoveFighter}
            onConfirm={() => {
              if (allFightersPlaced) {
                handleStartGame();
              }
            }}
            isConfirmEnabled={allFightersPlaced}
            isConfirming={loading}
          />
          <InviteLink gameCode={game.code} />
        </div>

        <div className="room-view__sidebar">
          <RoomChat />
        </div>
      </div>

      <Modal
        isOpen={showLeaveModal}
        onClose={() => setShowLeaveModal(false)}
        title="Покинуть комнату"
      >
        <div className="leave-modal">
          <p>Вы уверены, что хотите покинуть комнату?</p>
          <div className="leave-modal__actions">
            <Button variant="ghost" onClick={() => setShowLeaveModal(false)}>
              Отмена
            </Button>
            <Button variant="danger" onClick={handleLeaveRoom}>
              Покинуть
            </Button>
          </div>
        </div>
      </Modal>

      {showCountdown && (
        <GameCountdown seconds={3} onComplete={handleCountdownComplete} />
      )}
    </div>
  );
};

export default RoomView;