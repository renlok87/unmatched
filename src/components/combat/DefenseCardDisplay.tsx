import React from 'react';
import './DefenseCardDisplay.css';

export interface Card {
  id: string;
  name: string;
  type: 'attack' | 'defense' | 'versatile' | 'scheme';
  value: number;
}

interface DefenseCardDisplayProps {
  card: Card | null;
  defenseValue: number;
  isHidden: boolean;
}

export const DefenseCardDisplay: React.FC<DefenseCardDisplayProps> = ({
  card,
  defenseValue,
  isHidden,
}) => {
  if (isHidden && !card) {
    return (
      <div className="defense-card-display defense-card-display--hidden">
        <div className="defense-card-display__placeholder">
          <span className="defense-card-display__placeholder-icon">🛡️</span>
          <span className="defense-card-display__placeholder-text">
            Ожидание защиты...
          </span>
        </div>
      </div>
    );
  }

  if (!card) {
    return (
      <div className="defense-card-display defense-card-display--no-defense">
        <span className="defense-card-display__no-defense-icon">❌</span>
        <span className="defense-card-display__no-defense-text">
          Нет защиты
        </span>
      </div>
    );
  }

  return (
    <div
      className={`defense-card-display defense-card-display--${card.type}`}
    >
      <div className="defense-card-display__value">{defenseValue}</div>
      <div className="defense-card-display__name">{card.name}</div>
      <div className="defense-card-display__type">
        {card.type === 'attack' && '⚔️'}
        {card.type === 'defense' && '🛡️'}
        {card.type === 'versatile' && '⚡'}
        {card.type === 'scheme' && '🎯'}
      </div>
      {defenseValue > card.value && (
        <div className="defense-card-display__boost">
          +{defenseValue - card.value}
        </div>
      )}
    </div>
  );
};

export default DefenseCardDisplay;