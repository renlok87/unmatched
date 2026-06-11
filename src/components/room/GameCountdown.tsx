import React, { useEffect, useState } from 'react';
import './GameCountdown.css';

interface GameCountdownProps {
  seconds: number;
  onComplete: () => void;
  message?: string;
}

export const GameCountdown: React.FC<GameCountdownProps> = ({
  seconds,
  onComplete,
  message = 'Игра начнется через',
}) => {
  const [count, setCount] = useState(seconds);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (count <= 0) {
      setIsVisible(false);
      onComplete();
      return;
    }

    const timer = setTimeout(() => {
      setCount(count - 1);
    }, 1000);

    return () => clearTimeout(timer);
  }, [count, onComplete]);

  if (!isVisible) return null;

  return (
    <div className="game-countdown">
      <div className="game-countdown__backdrop" />
      <div className="game-countdown__content">
        <div className="game-countdown__message">{message}</div>
        <div className={`game-countdown__number game-countdown__number--${count}`}>
          {count}
        </div>
        <div className="game-countdown__progress">
          <div
            className="game-countdown__progress-bar"
            style={{ width: `${(count / seconds) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export default GameCountdown;