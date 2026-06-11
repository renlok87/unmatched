import React from 'react';
import { PlayerRow, type LeaderboardEntry } from './PlayerRow';
import { Button } from '@/design-system/components/Button';
import './LeaderboardTable.css';

interface LeaderboardTableProps {
  players: LeaderboardEntry[];
  currentUserRank?: {
    rank: number;
    rating: number;
  };
  currentUserId?: string;
  isLoading?: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void;
  onPlayerClick: (playerId: string) => void;
}

export const LeaderboardTable: React.FC<LeaderboardTableProps> = ({
  players,
  currentUserRank,
  currentUserId,
  isLoading = false,
  hasMore = false,
  onLoadMore,
  onPlayerClick,
}) => {
  if (isLoading && players.length === 0) {
    return (
      <div className="leaderboard-table leaderboard-table--loading">
        {[...Array(10)].map((_, i) => (
          <div key={i} className="leaderboard-table__skeleton">
            <div className="leaderboard-table__skeleton-cell" />
            <div className="leaderboard-table__skeleton-cell leaderboard-table__skeleton-cell--player" />
            <div className="leaderboard-table__skeleton-cell" />
            <div className="leaderboard-table__skeleton-cell" />
            <div className="leaderboard-table__skeleton-cell" />
            <div className="leaderboard-table__skeleton-cell" />
          </div>
        ))}
      </div>
    );
  }

  if (players.length === 0) {
    return (
      <div className="leaderboard-table leaderboard-table--empty">
        <div className="leaderboard-table__empty-icon">🏆</div>
        <p className="leaderboard-table__empty-text">
          Нет данных для отображения
        </p>
      </div>
    );
  }

  return (
    <div className="leaderboard-table">
      <table className="leaderboard-table__table">
        <thead>
          <tr>
            <th className="leaderboard-table__header leaderboard-table__header--rank">
              Ранг
            </th>
            <th className="leaderboard-table__header leaderboard-table__header--player">
              Игрок
            </th>
            <th className="leaderboard-table__header leaderboard-table__header--rating">
              Рейтинг
            </th>
            <th className="leaderboard-table__header leaderboard-table__header--win-rate">
              Win Rate
            </th>
            <th className="leaderboard-table__header leaderboard-table__header--games">
              Игры
            </th>
            <th className="leaderboard-table__header leaderboard-table__header--streak">
              Серия
            </th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => (
            <PlayerRow
              key={player.user.id}
              player={player}
              isCurrentUser={player.user.id === currentUserId}
              onClick={onPlayerClick}
            />
          ))}
        </tbody>
      </table>

      {currentUserRank && (
        <div className="leaderboard-table__current-user">
          <div className="leaderboard-table__current-user-label">Ваш ранг:</div>
          <div className="leaderboard-table__current-user-rank">
            #{currentUserRank.rank}
          </div>
          <div className="leaderboard-table__current-user-rating">
            {currentUserRank.rating} ELO
          </div>
        </div>
      )}

      {hasMore && onLoadMore && (
        <div className="leaderboard-table__load-more">
          <Button
            variant="ghost"
            onClick={onLoadMore}
            disabled={isLoading}
          >
            {isLoading ? 'Загрузка...' : 'Загрузить ещё'}
          </Button>
        </div>
      )}
    </div>
  );
};