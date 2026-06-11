import React from 'react';
import type { Hero } from '@/types/hero';

interface HeroCardProps {
  hero: Hero;
  selected: boolean;
  disabled: boolean;
  onClick: () => void;
  onHover?: () => void;
}

export const HeroCard: React.FC<HeroCardProps> = ({
  hero,
  selected,
  disabled,
  onClick,
  onHover,
}) => {
  return (
    <div
      className={`hero-card ${selected ? 'hero-card--selected' : ''} ${
        disabled ? 'hero-card--disabled' : ''
      }`}
      onClick={!disabled ? onClick : undefined}
      onMouseEnter={onHover}
      role="button"
      tabIndex={!disabled ? 0 : undefined}
      onKeyDown={(e) => {
        if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="hero-card__image">
        {hero.imageUrl ? (
          <img src={hero.imageUrl} alt={hero.name} />
        ) : (
          <div className="hero-card__placeholder">{hero.name[0]}</div>
        )}
      </div>

      <div className="hero-card__stats">
        <div className="hero-card__stat hero-card__stat--hp">
          <span className="hero-card__stat-icon">❤️</span>
          <span className="hero-card__stat-value">{hero.health}</span>
        </div>
        <div className="hero-card__stat hero-card__stat--movement">
          <span className="hero-card__stat-icon">👟</span>
          <span className="hero-card__stat-value">{hero.movement}</span>
        </div>
      </div>

      <div className="hero-card__info">
        <h3 className="hero-card__name">{hero.name}</h3>
        <span className="hero-card__set">{hero.set}</span>
      </div>

      {disabled && (
        <div className="hero-card__overlay">
          <span className="hero-card__locked-icon">🔒</span>
        </div>
      )}

      {selected && (
        <div className="hero-card__selected-badge">
          <span>✓</span>
        </div>
      )}
    </div>
  );
};

export default HeroCard;