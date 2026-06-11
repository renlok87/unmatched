import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLobbyStore } from '@/store/lobbyStore';
import { useAuthStore } from '@/store/authStore';
import { GameList } from './GameList';
import { CreateGameDialog } from './CreateGameDialog';
import { Button } from '@/design-system/components/Button';
import { GameMode, GameStatus } from '@/gql';

export const LobbyView: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    joinGame,
    error,
    clearError,
    setFilter,
    startPolling,
    stopPolling,
    mount,
    unmount,
  } = useLobbyStore();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [modeFilter, setModeFilter] = useState<GameMode | undefined>();
  const [statusFilter, setStatusFilter] = useState<GameStatus>(GameStatus.Lobby);

  useEffect(() => {
    // Mark component as mounted
    mount();

    // Start polling for games
    startPolling(30000); // 30 seconds

    // Cleanup when component unmounts
    return () => {
      stopPolling();
      unmount();
    };
  }, [mount, unmount, startPolling, stopPolling]);

  useEffect(() => {
    // Update store filter when local filter changes
    setFilter({ mode: modeFilter, status: statusFilter });
  }, [modeFilter, statusFilter, setFilter]);

  useEffect(() => {
    clearError();
  }, [clearError]);

  const handleCreateGame = (gameId: string) => {
    navigate(`/room/${gameId}`);
  };

  const handleJoinGame = async (gameId: string) => {
    try {
      await joinGame(gameId);
      navigate(`/room/${gameId}`);
    } catch (error) {
      console.error('Failed to join game:', error);
    }
  };

  const handleMatchmaking = () => {
    navigate('/matchmaking');
  };

  if (!user) {
    return (
      <div className="lobby-view lobby-view-loading">
        <div className="loading-spinner" />
        <p>Загрузка...</p>
      </div>
    );
  }

  return (
    <div className="lobby-view">
      <header className="lobby-header">
        <div className="lobby-title">
          <h1>⚔️ Unmatched - Лобби</h1>
          <p className="lobby-subtitle">Добро пожаловать, {user.username}!</p>
        </div>

        <div className="lobby-actions">
          <Button variant="primary" onClick={() => setIsCreateDialogOpen(true)}>
            + Создать игру
          </Button>
          <Button variant="secondary" onClick={handleMatchmaking}>
            🔍 Найти игру
          </Button>
        </div>
      </header>

      <div className="lobby-filters">
        <div className="filter-group">
          <label htmlFor="mode-filter">Режим:</label>
          <select
            id="mode-filter"
            value={modeFilter || ''}
            onChange={(e) => setModeFilter(e.target.value as GameMode || undefined)}
            className="form-select"
          >
            <option value="">Все режимы</option>
            <option value={GameMode.OneVOne}>1 на 1</option>
            <option value={GameMode.TwoVTwo}>2 на 2</option>
            <option value={GameMode.FreeForAll}>Free for All</option>
            <option value={GameMode.VsAi}>Против ИИ</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="status-filter">Статус:</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as GameStatus)}
            className="form-select"
          >
            <option value={GameStatus.Lobby}>В лобби</option>
            <option value={GameStatus.InProgress}>В процессе</option>
            <option value={GameStatus.Finished}>Завершены</option>
          </select>
        </div>
      </div>

      <main className="lobby-content">
        {error && (
          <div className="error-banner">
            <span>⚠️</span>
            <p>{error}</p>
            <button onClick={clearError} className="close-banner">×</button>
          </div>
        )}

        <GameList
          modeFilter={modeFilter}
          statusFilter={statusFilter}
          onJoinGame={handleJoinGame}
        />
      </main>

      <CreateGameDialog
        isOpen={isCreateDialogOpen}
        onClose={() => setIsCreateDialogOpen(false)}
        onSuccess={handleCreateGame}
      />
    </div>
  );
};

export default LobbyView;