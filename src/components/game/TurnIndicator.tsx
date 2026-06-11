import React from 'react';
import { Avatar } from '@/design-system/components/Avatar';
import './TurnIndicator.css';

export interface Player {
  id: string;
  userId: string;
  username: string;
  avatar?: string;
}

interface TurnIndicatorProps {
  currentPlayer: Player;
  isYourTurn: boolean;
  timeRemaining?: number;
}

export const TurnIndicator: React.FC<TurnIndicatorProps> = ({
  currentPlayer,
  isYourTurn,
  timeRemaining,
}) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      className={`turn-indicator ${
        isYourTurn ? 'turn-indicator--your-turn' : ''
      }`}
    >
      <div className="turn-indicator__avatar">
        <Avatar
          src={currentPlayer.avatar}
          alt={currentPlayer.username}
          size="md"
          variant="hero"
          fallback={currentPlayer.username[0].toUpperCase()}
        />
      </div>

      <div className="turn-indicator__info">
        <div className="turn-indicator__label">
          {isYourTurn ? 'Ваш ход' : 'Ход соперника'}
        </div>
        <div className="turn-indicator__player-name">
          {currentPlayer.username}
        </div>
      </div>

      {timeRemaining !== undefined && (
        <div className="turn-indicator__timer">
          <div className="turn-indicator__timer-value">
            {formatTime(timeRemaining)}
          </div>
          <div
            className="turn-indicator__timer-bar"
            style={{
              width: `${Math.max(0, timeRemaining / 60) * 100}%`,
            }}
          />
        </div>
      )}
    </div>
  );
};

export default TurnIndicator;