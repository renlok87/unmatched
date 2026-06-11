import React, { useEffect, useState, useRef } from 'react';
import { Button } from '@/design-system/components/Button';
import { Badge } from '@/design-system/components/Badge';
import { Avatar } from '@/design-system/components/Avatar';
import type { MatchFoundResponse } from '@/gql';

interface MatchFoundProps {
  match: MatchFoundResponse | null;
  onAccept: () => void;
  onDecline: () => void;
  autoAcceptDelay?: number;
}

export const MatchFound: React.FC<MatchFoundProps> = ({
  match,
  onAccept,
  onDecline,
  autoAcceptDelay = 5000,
}) => {
  const [countdown, setCountdown] = useState(autoAcceptDelay / 1000);
  const [hasAutoAccepted, setHasAutoAccepted] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    if (!match || hasAutoAccepted) return;

    isMountedRef.current = true;
    setCountdown(autoAcceptDelay / 1000);

    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          // Only call onAccept if component is still mounted
          if (isMountedRef.current && !hasAutoAccepted) {
            setHasAutoAccepted(true);
            onAccept();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      clearInterval(interval);
      isMountedRef.current = false;
    };
  }, [match, autoAcceptDelay, hasAutoAccepted, onAccept]);

  if (!match) {
    return null;
  }

  const handleAccept = () => {
    if (!hasAutoAccepted && isMountedRef.current) {
      setHasAutoAccepted(true);
      onAccept();
    }
  };

  const handleDecline = () => {
    if (isMountedRef.current) {
      onDecline();
    }
  };

  const expiresAt = new Date(match.expiresAt);
  const timeRemaining = Math.max(0, Math.ceil((expiresAt.getTime() - Date.now()) / 1000));

  return (
    <div className="match-found-overlay">
      <div className="match-found-modal">
        <div className="match-found-header">
          <div className="match-found-icon">🎮</div>
          <h2 className="match-found-title">Игра найдена!</h2>
          <p className="match-found-subtitle">Подготовьтесь к битве</p>
        </div>

        <div className="match-found-content">
          <div className="match-info">
            <div className="match-mode">
              <Badge>{match.mode === 'ONE_V_ONE' ? '1 на 1' : match.mode}</Badge>
            </div>
            <div className="match-countdown">
              <span className="countdown-label">Автоподтверждение через:</span>
              <span className="countdown-value">{countdown} сек</span>
            </div>
          </div>

          <div className="match-vs-container">
            <div className="player-card player-you">
              <div className="player-card-header">
                <span className="player-label">Вы</span>
              </div>
              <div className="player-avatar-large">
                <Avatar
                  alt="Вы"
                  size="xl"
                  fallback="В"
                />
              </div>
              <div className="player-rating">
                <span className="rating-label">Ваш рейтинг:</span>
                <span className="rating-value">--</span>
              </div>
            </div>

            <div className="vs-badge">
              <span>VS</span>
            </div>

            <div className="player-card player-opponent">
              <div className="player-card-header">
                <span className="player-label">Оппонент</span>
              </div>
              <div className="player-avatar-large">
                <Avatar
                  src={undefined}
                  alt={match.opponentUsername}
                  size="xl"
                  fallback={match.opponentUsername.charAt(0)}
                />
              </div>
              <div className="player-name">
                {match.opponentUsername}
              </div>
              <div className="player-rating">
                <span className="rating-label">Рейтинг:</span>
                <span className="rating-value">{match.opponentRating}</span>
              </div>
            </div>
          </div>

          <div className="match-found-footer">
            <div className="time-warning">
              <span>⏰</span>
              <span>Время подтверждения: {timeRemaining} сек</span>
            </div>

            <div className="match-actions">
              <Button
                variant="danger"
                onClick={handleDecline}
                disabled={hasAutoAccepted}
              >
                Отклонить
              </Button>
              <Button
                variant="primary"
                onClick={handleAccept}
                disabled={hasAutoAccepted}
                loading={hasAutoAccepted}
              >
                {hasAutoAccepted ? 'Принято!' : 'Принять'}
              </Button>
            </div>
          </div>
        </div>

        <div className="match-found-decoration">
          <div className="decoration-circle decoration-circle-1" />
          <div className="decoration-circle decoration-circle-2" />
          <div className="decoration-circle decoration-circle-3" />
        </div>
      </div>
    </div>
  );
};

export default MatchFound;