import React from 'react';
import './OpponentHandView.css';

export interface Card {
  id: string;
  name: string;
  type: 'attack' | 'defense' | 'versatile' | 'scheme';
  value: number;
}

interface OpponentHandViewProps {
  cardCount: number;
  lastDiscarded?: Card;
}

export const OpponentHandView: React.FC<OpponentHandViewProps> = ({
  cardCount,
  lastDiscarded,
}) => {
  const maxVisibleCards = 7;
  const visibleCount = Math.min(cardCount, maxVisibleCards);
  const remainingCount = Math.max(0, cardCount - maxVisibleCards);

  return (
    <div className="opponent-hand-view">
      <div className="opponent-hand-view__cards">
        {Array.from({ length: visibleCount }).map((_, index) => (
          <div
            key={index}
            className="opponent-hand-view__card"
            style={{
              transform: `translateX(-${index * 8}px)`,
              zIndex: visibleCount - index,
            }}
          >
            <div className="opponent-hand-view__card-back">
              <div className="opponent-hand-view__card-pattern" />
            </div>
          </div>
        ))}

        {remainingCount > 0 && (
          <div className="opponent-hand-view__more">
            +{remainingCount}
          </div>
        )}
      </div>

      {lastDiscarded && (
        <div className="opponent-hand-view__last-discarded">
          <span className="opponent-hand-view__label">Последний сброс:</span>
          <div className={`opponent-hand-view__card-preview opponent-hand-view__card-preview--${lastDiscarded.type}`}>
            <span className="opponent-hand-view__card-value">
              {lastDiscarded.value}
            </span>
            <span className="opponent-hand-view__card-name">
              {lastDiscarded.name}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default OpponentHandView;