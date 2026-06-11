import React from 'react';
import { Card } from './AttackCardDisplay';
import { Button } from '@/design-system/components/Button';
import './DefenseCardSelector.css';

interface DefenseCardSelectorProps {
  hand: Card[];
  onSelect: (cardId: string) => void;
  onPass: () => void;
  timeRemaining: number;
}

export const DefenseCardSelector: React.FC<DefenseCardSelectorProps> = ({
  hand,
  onSelect,
  onPass,
  timeRemaining,
}) => {
  const defenseCards = hand.filter(
    (card) => card.type === 'defense' || card.type === 'versatile'
  );

  const handleCardClick = (cardId: string) => {
    onSelect(cardId);
  };

  return (
    <div className="defense-card-selector">
      <div className="defense-card-selector__header">
        <h3 className="defense-card-selector__title">Выберите защиту</h3>
        <div className="defense-card-selector__timer">
          <span className="defense-card-selector__timer-icon">⏱️</span>
          <span className="defense-card-selector__timer-value">
            {timeRemaining}с
          </span>
        </div>
      </div>

      <div className="defense-card-selector__cards">
        {defenseCards.length === 0 ? (
          <div className="defense-card-selector__empty">
            <span className="defense-card-selector__empty-icon">🛡️</span>
            <span className="defense-card-selector__empty-text">
              Нет доступных карт защиты
            </span>
          </div>
        ) : (
          defenseCards.map((card) => (
            <button
              key={card.id}
              className={`defense-card-selector__card defense-card-selector__card--${card.type}`}
              onClick={() => handleCardClick(card.id)}
            >
              <div className="defense-card-selector__card-value">
                {card.value}
              </div>
              <div className="defense-card-selector__card-name">
                {card.name}
              </div>
              <div className="defense-card-selector__card-type">
                {card.type === 'defense' && '🛡️'}
                {card.type === 'versatile' && '⚡'}
              </div>
            </button>
          ))
        )}
      </div>

      <div className="defense-card-selector__actions">
        <Button variant="ghost" onClick={onPass}>
          Пропустить
        </Button>
      </div>
    </div>
  );
};

export default DefenseCardSelector;