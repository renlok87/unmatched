import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRoomStore } from '@/store/roomStore';
import { useHeroSelectionStore } from '@/store/heroSelectionStore';
import { PlayerSlots } from './PlayerSlots';
import { ReadyStatus } from './ReadyStatus';
import { RoomChat } from './RoomChat';
import { InviteLink } from './InviteLink';
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
  const [selectingHeroId, setSelectingHeroId] = useState<string | null>(null);

  const {
    heroes,
    loadHeroes,
    selectHeroOnServer,
  } = useHeroSelectionStore();

  useEffect(() => {
    mount();
    loadHeroes();

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

  // Автопереход в игру: хост уходит сам после startGame, не-хост — по
  // поллингу статуса (бэк ставит IN_PROGRESS после startGame)
  useEffect(() => {
    if (game?.status === 'IN_PROGRESS' && gameId) {
      navigate(`/game/${gameId}`);
    }
  }, [game?.status, gameId]);

  const handleSelectHero = async (heroId: string) => {
    if (!gameId) return;
    setSelectingHeroId(heroId);
    try {
      await selectHeroOnServer(gameId, heroId);
      await loadRoom(gameId);
    } catch (err) {
      console.error('Failed to select hero:', err);
    } finally {
      setSelectingHeroId(null);
    }
  };

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
  const myHeroId = currentPlayer?.heroId ?? null;
  const heroName = (heroId: string | null) =>
    heroId ? heroes.find((h) => h.id === heroId)?.name ?? heroId : null;

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
          {/* Выбор героя: серверная мутация selectHero; расстановка бойцов
              серверная (GameInitializationService при startGame) */}
          <div className="room-view__hero-select">
            <h3>
              {myHeroId
                ? `Ваш герой: ${heroName(myHeroId)}`
                : 'Выберите героя'}
            </h3>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                gap: 8,
                maxHeight: 260,
                overflowY: 'auto',
              }}
            >
              {heroes.map((hero) => {
                const takenByOther = game.players.some(
                  (p) => p.heroId === hero.id && p.userId !== currentUserId,
                );
                return (
                  <Button
                    key={hero.id}
                    variant={myHeroId === hero.id ? 'success' : 'ghost'}
                    disabled={takenByOther || selectingHeroId !== null || isReady}
                    onClick={() => handleSelectHero(hero.id)}
                  >
                    {selectingHeroId === hero.id ? '…' : hero.name}
                  </Button>
                );
              })}
            </div>
            <p style={{ opacity: 0.7, marginTop: 8 }}>
              {game.players
                .map((p) => `${p.username}: ${heroName(p.heroId) ?? '—'}${p.isReady ? ' ✓' : ''}`)
                .join('  ·  ')}
            </p>
          </div>
          <ReadyStatus
            isReady={isReady}
            onToggle={() => setReady(gameId!)}
            disabled={loading || !myHeroId}
            allReady={allReady}
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