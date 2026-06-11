import React from 'react';
import './AttackCardDisplay.css';

export interface Card {
  id: string;
  name: string;
  type: 'attack' | 'defense' | 'versatile' | 'scheme';
  value: number;
}

interface AttackCardDisplayProps {
  card: Card;
  attackValue: number;
}

export const AttackCardDisplay: React.FC<AttackCardDisplayProps> = ({
  card,
  attackValue,
}) => {
  return (
    <div
      className={`attack-card-display attack-card-display--${card.type}`}
    >
      <div className="attack-card-display__value">{attackValue}</div>
      <div className="attack-card-display__name">{card.name}</div>
      <div className="attack-card-display__type">
        {card.type === 'attack' && '⚔️'}
        {card.type === 'defense' && '🛡️'}
        {card.type === 'versatile' && '⚡'}
        {card.type === 'scheme' && '🎯'}
      </div>
      {attackValue > card.value && (
        <div className="attack-card-display__boost">
          +{attackValue - card.value}
        </div>
      )}
    </div>
  );
};

export default AttackCardDisplay;