import React from 'react';
import type { Hero } from '@/types/hero';
import { HeroCard } from './HeroCard';

interface HeroGridProps {
  heroes: Hero[];
  selectedHero: Hero | null;
  takenHeroIds: string[];
  loading: boolean;
  onHeroClick: (hero: Hero) => void;
  onHeroHover?: (hero: Hero) => void;
  emptyMessage?: string;
}

export const HeroGrid: React.FC<HeroGridProps> = ({
  heroes,
  selectedHero,
  takenHeroIds,
  loading,
  onHeroClick,
  onHeroHover,
  emptyMessage = 'Нет доступных героев',
}) => {
  if (loading) {
    return (
      <div className="hero-grid hero-grid--loading">
        <div className="hero-grid__loading">
          <div className="loading-spinner" />
          <p>Загрузка героев...</p>
        </div>
      </div>
    );
  }

  if (heroes.length === 0) {
    return (
      <div className="hero-grid hero-grid--empty">
        <p className="hero-grid__empty-message">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="hero-grid">
      {heroes.map((hero) => {
        const isSelected = selectedHero?.id === hero.id;
        const isTaken = takenHeroIds.includes(hero.id);

        return (
          <HeroCard
            key={hero.id}
            hero={hero}
            selected={isSelected}
            disabled={isTaken}
            onClick={() => onHeroClick(hero)}
            onHover={() => onHeroHover?.(hero)}
          />
        );
      })}
    </div>
  );
};

export default HeroGrid;