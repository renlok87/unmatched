import React, { useEffect } from 'react';
import { useLobbyStore } from '@/store/lobbyStore';
import { GameCard } from './GameCard';
import type { GameMode, GameStatus } from '@/gql';

interface GameListProps {
  modeFilter?: GameMode;
  statusFilter?: GameStatus;
  onJoinGame?: (gameId: string) => void;
  onViewGame?: (gameId: string) => void;
}

export const GameList: React.FC<GameListProps> = ({
  modeFilter,
  statusFilter,
  onJoinGame,
  onViewGame,
}) => {
  const { games, loading, error, fetchGames, setFilter } = useLobbyStore();

  useEffect(() => {
    const filters: { mode?: GameMode; status?: GameStatus } = {};
    if (modeFilter) filters.mode = modeFilter;
    if (statusFilter) filters.status = statusFilter;
    setFilter(filters);
  }, [modeFilter, statusFilter, setFilter]);

  useEffect(() => {
    fetchGames();
    const interval = setInterval(fetchGames, 30000);
    return () => clearInterval(interval);
  }, [fetchGames]);

  const handleJoin = (gameId: string) => {
    if (onJoinGame) {
      onJoinGame(gameId);
    }
  };

  const handleView = (gameId: string) => {
    if (onViewGame) {
      onViewGame(gameId);
    }
  };

  if (loading && games.length === 0) {
    return (
      <div className="game-list game-list-loading">
        <div className="loading-spinner" />
        <p>Загрузка игр...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="game-list game-list-error">
        <div className="error-message">
          <span>⚠️</span>
          <p>{error}</p>
        </div>
        <button onClick={fetchGames} className="retry-button">
          Повторить
        </button>
      </div>
    );
  }

  if (games.length === 0) {
    return (
      <div className="game-list game-list-empty">
        <div className="empty-state">
          <span>🎮</span>
          <h3>Нет доступных игр</h3>
          <p>Создайте новую игру или подождите других игроков</p>
        </div>
      </div>
    );
  }

  return (
    <div className="game-list">
      <div className="game-list-header">
        <h2>Доступные игры ({games.length})</h2>
      </div>
      <div className="game-list-grid">
        {games.map((game) => (
          <GameCard
            key={game.id}
            game={game}
            onJoin={handleJoin}
            onView={handleView}
          />
        ))}
      </div>
    </div>
  );
};

export default GameList;