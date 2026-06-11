import React from 'react';
import './MatchHistory.css';

export interface GameSummary {
  id: string;
  mode: string;
  result: 'win' | 'loss' | 'draw';
  heroes: Array<{
    id: string;
    name: string;
    thumbnailUrl?: string;
  }>;
  playedAt: string;
  ratingChange: number;
}

interface MatchHistoryProps {
  games: GameSummary[];
  onLoadMore: () => void;
  onGameClick: (gameId: string) => void;
  hasMore?: boolean;
  isLoading?: boolean;
}

export const MatchHistory: React.FC<MatchHistoryProps> = ({
  games,
  onLoadMore,
  onGameClick,
  hasMore = false,
  isLoading = false,
}) => {
  const getResultIcon = (result: string) => {
    switch (result) {
      case 'win':
        return '🏆';
      case 'loss':
        return '💔';
      case 'draw':
        return '🤝';
      default:
        return '❓';
    }
  };

  const getResultClass = (result: string) => {
    switch (result) {
      case 'win':
        return 'match-history__item--win';
      case 'loss':
        return 'match-history__item--loss';
      case 'draw':
        return 'match-history__item--draw';
      default:
        return '';
    }
  };

  const getRatingChangeClass = (change: number) => {
    if (change > 0) return 'match-history__rating-change--positive';
    if (change < 0) return 'match-history__rating-change--negative';
    return 'match-history__rating-change--neutral';
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  if (games.length === 0) {
    return (
      <div className="match-history match-history--empty">
        <div className="match-history__empty-icon">🎮</div>
        <p className="match-history__empty-text">История игр пуста</p>
      </div>
    );
  }

  return (
    <div className="match-history">
      <h2 className="match-history__title">История матчей</h2>
      <div className="match-history__list">
        {games.map((game) => (
          <div
            key={game.id}
            className={`match-history__item ${getResultClass(game.result)}`}
            onClick={() => onGameClick(game.id)}
          >
            <div className="match-history__result">
              <span className="match-history__result-icon">{getResultIcon(game.result)}</span>
            </div>
            <div className="match-history__content">
              <div className="match-history__mode">{game.mode}</div>
              <div className="match-history__heroes">
                {game.heroes.map((hero) => (
                  <div key={hero.id} className="match-history__hero">
                    {hero.thumbnailUrl ? (
                      <img src={hero.thumbnailUrl} alt={hero.name} />
                    ) : (
                      <span>{hero.name[0]}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="match-history__meta">
              <div className="match-history__date">{formatDate(game.playedAt)}</div>
              <div className={`match-history__rating-change ${getRatingChangeClass(game.ratingChange)}`}>
                {game.ratingChange > 0 ? '+' : ''}{game.ratingChange}
              </div>
            </div>
          </div>
        ))}
      </div>
      {hasMore && (
        <div className="match-history__load-more">
          <button
            type="button"
            className="match-history__load-more-button"
            onClick={onLoadMore}
            disabled={isLoading}
          >
            {isLoading ? 'Загрузка...' : 'Загрузить ещё'}
          </button>
        </div>
      )}
    </div>
  );
};