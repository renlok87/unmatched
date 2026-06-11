import React from 'react';
import type { CardInstance } from '../../core/models/types';
import { CardType } from '../../core/models/types';
import './Card.css';

interface CardProps {
  card: CardInstance;
  onClick?: () => void;
  isPlayable?: boolean;
  isSelected?: boolean;
  isFaceDown?: boolean;
  showValue?: boolean;
}

export const Card: React.FC<CardProps> = ({
  card,
  onClick,
  isPlayable = true,
  isSelected = false,
  isFaceDown = false,
  showValue = true,
}) => {
  const { definition } = card;

  if (isFaceDown) {
    return (
      <div
        className={`card card-face-down ${isPlayable ? 'playable' : ''}`}
        onClick={isPlayable ? onClick : undefined}
      >
        <div className="card-back">
          <span className="card-back-icon">?</span>
        </div>
      </div>
    );
  }

  const getCardTypeLabel = (type: CardType) => {
    const labels: Record<CardType, string> = {
      [CardType.ATTACK]: 'ATK',
      [CardType.DEFENSE]: 'DEF',
      [CardType.VERSATILE]: 'VER',
      [CardType.SCHEME]: 'SCH',
    };
    return labels[type];
  };

  const cardImage = definition.imageUrl || definition.imageUrlRu;

  return (
    <div
      className={`card ${definition.type.toLowerCase()} ${isPlayable ? 'playable' : ''} ${isSelected ? 'selected' : ''}`}
      onClick={isPlayable ? onClick : undefined}
    >
      {cardImage && (
        <div className="card-image">
          <img src={cardImage} alt={definition.title} />
        </div>
      )}

      <div className="card-header">
        <span className="card-title">{definition.title}</span>
        {showValue && <span className="card-value">{definition.value}</span>}
      </div>

      <div className="card-type">{getCardTypeLabel(definition.type)}</div>

      {definition.effects.length > 0 && (
        <div className="card-effects">
          {definition.effects.map((effect) => (
            <div key={effect.id} className="card-effect">
              <span className="effect-timing">{effect.timing}</span>
              <span className="effect-text">{effect.text}</span>
            </div>
          ))}
        </div>
      )}

      {definition.boost > 0 && (
        <div className="card-boost">+{definition.boost}</div>
      )}

      <div className="card-character">{definition.characterName}</div>
    </div>
  );
};

export default Card;
