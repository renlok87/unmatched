import React from 'react';
import './CombatTimer.css';

interface CombatTimerProps {
  timeRemaining: number;
  totalTime: number;
}

export const CombatTimer: React.FC<CombatTimerProps> = ({
  timeRemaining,
  totalTime,
}) => {
  const percentage = (timeRemaining / totalTime) * 100;
  const isLowTime = timeRemaining <= 10;
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div
      className={`combat-timer ${isLowTime ? 'combat-timer--low' : ''}`}
    >
      <svg className="combat-timer__svg" viewBox="0 0 100 100">
        <circle
          className="combat-timer__background"
          cx="50"
          cy="50"
          r="45"
          fill="none"
          strokeWidth="8"
        />
        <circle
          className={`combat-timer__progress ${
            isLowTime ? 'combat-timer__progress--low' : ''
          }`}
          cx="50"
          cy="50"
          r="45"
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div className="combat-timer__value">{timeRemaining}</div>
    </div>
  );
};

export default CombatTimer;