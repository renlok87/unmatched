import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMatchmakingStore } from '@/store/matchmakingStore';
import { QueueStatus } from '@/components/matchmaking/QueueStatus';
import { MatchFound } from '@/components/matchmaking/MatchFound';
import { Button } from '@/design-system/components/Button';
import type { GameMode } from '@/gql';

export const MatchmakingView: React.FC = () => {
  const navigate = useNavigate();
  const {
    inQueue,
    matchFound,
    loading,
    error,
    joinQueue,
    leaveQueue,
    subscribeToMatchFound,
    unsubscribeFromMatchFound,
    clearMatchFound,
    clearError,
    mount,
    unmount,
  } = useMatchmakingStore();

  useEffect(() => {
    // Mark component as mounted
    mount();

    // Subscribe to match found when component mounts
    // TODO: Get actual userId from auth context or store
    const userId = 'current-user-id';
    subscribeToMatchFound(userId);

    // Cleanup when component unmounts
    return () => {
      unsubscribeFromMatchFound();
      unmount();
    };
  }, [mount, unmount, subscribeToMatchFound, unsubscribeFromMatchFound]);

  const handleJoinQueue = async () => {
    try {
      await joinQueue('ONE_V_ONE' as GameMode);
    } catch (err) {
      console.error('Failed to join queue:', err);
    }
  };

  const handleLeaveQueue = async () => {
    try {
      await leaveQueue();
    } catch (err) {
      console.error('Failed to leave queue:', err);
    }
  };

  const handleAcceptMatch = () => {
    // Navigate to room when match is accepted
    if (matchFound) {
      navigate(`/room/${matchFound.gameId}`);
    }
    clearMatchFound();
  };

  const handleDeclineMatch = () => {
    // Leave queue and reset match state
    leaveQueue();
    clearMatchFound();
  };

  const handleClearError = () => {
    clearError();
  };

  return (
    <div className="matchmaking-view">
      <div className="matchmaking-header">
        <h1>Поиск игры</h1>
        <p className="matchmaking-subtitle">
          Найдите соперника для соревновательной игры
        </p>
      </div>

      {error && (
        <div className="error-message">
          <span>⚠️</span>
          <span>{error}</span>
          <button onClick={handleClearError} className="error-close">×</button>
        </div>
      )}

      {matchFound ? (
        <MatchFound
          match={matchFound}
          onAccept={handleAcceptMatch}
          onDecline={handleDeclineMatch}
          autoAcceptDelay={5000}
        />
      ) : (
        <div className="matchmaking-content">
          {!inQueue ? (
            <div className="join-queue-section">
              <div className="join-queue-info">
                <h2>Готовы к игре?</h2>
                <p>
                  Нажмите кнопку ниже, чтобы встать в очередь и найти соперника.
                  Система подберет вам противника с похожим уровнем навыков.
                </p>
              </div>
              <Button
                variant="primary"
                size="lg"
                onClick={handleJoinQueue}
                disabled={loading}
              >
                {loading ? 'Вступление...' : 'Встать в очередь'}
              </Button>
            </div>
          ) : (
            <>
              <QueueStatus />
              <div className="leave-queue-section">
                <Button
                  variant="danger"
                  size="md"
                  onClick={handleLeaveQueue}
                  disabled={loading}
                >
                  Покинуть очередь
                </Button>
              </div>
            </>
          )}

          <div className="matchmaking-tips">
            <h3>Советы по поиску:</h3>
            <ul>
              <li>⏱️ Среднее время ожидания: ~2-5 минут</li>
              <li>🎯 Вы будете подобраны с соперником вашего уровня</li>
              <li>🚫 Если вы выйдете из очереди, получите штраф</li>
              <li>✅ Вы можете отменить поиск в любой момент</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default MatchmakingView;