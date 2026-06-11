import React, { useState, useEffect } from 'react';
import { Modal } from '@/design-system/components/Modal';
import { Button } from '@/design-system/components/Button';
import { useLobbyStore } from '@/store/lobbyStore';
import { apolloClient } from '@/lib/apolloClient';
import { gql } from '@apollo/client';
import { GameMode } from '@/gql';
import type { Board } from '@/gql';

const BOARDS_QUERY = gql`
  query Boards {
    boards {
      id
      name
      width
      height
      recommendedPlayers
    }
  }
`;

interface CreateGameDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (gameId: string) => void;
}

export const CreateGameDialog: React.FC<CreateGameDialogProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { createGame, loading: creatingGame } = useLobbyStore();
  const [mode, setMode] = useState<GameMode>(GameMode.OneVOne);
  const [boardId, setBoardId] = useState<string>('');
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBoards = async () => {
      if (!isOpen) return;
      
      setLoading(true);
      setError(null);
      try {
        const result = await apolloClient.query<{ boards: Board[] }>({
          query: BOARDS_QUERY,
          fetchPolicy: 'network-only',
        });
        setBoards(result.data?.boards || []);
        if (result.data?.boards?.[0]) {
          setBoardId(result.data.boards[0].id);
        }
      } catch (err) {
        setError('Не удалось загрузить доски');
      } finally {
        setLoading(false);
      }
    };

    fetchBoards();
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      const game = await createGame({ mode, boardId });
      onSuccess(game.id);
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать игру');
    }
  };

  const handleClose = () => {
    setMode(GameMode.OneVOne);
    setBoardId('');
    setError(null);
    onClose();
  };

  const modeOptions: { value: GameMode; label: string }[] = [
    { value: GameMode.OneVOne, label: '1 на 1' },
    { value: GameMode.TwoVTwo, label: '2 на 2' },
    { value: GameMode.FreeForAll, label: 'Free for All' },
    { value: GameMode.VsAi, label: 'Против ИИ' },
  ];

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Создать игру">
      <div className="modal-body">
        {loading ? (
          <div className="loading-state">
            <div className="loading-spinner" />
            <p>Загрузка...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && (
              <div className="error-message">
                <span>⚠️</span>
                <p>{error}</p>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="mode">Режим игры</label>
              <select
                id="mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as GameMode)}
                className="form-select"
              >
                {modeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="board">Доска</label>
              <select
                id="board"
                value={boardId}
                onChange={(e) => setBoardId(e.target.value)}
                className="form-select"
                disabled={boards.length === 0}
              >
                {boards.map((board) => (
                  <option key={board.id} value={board.id}>
                    {board.name} ({board.width}x{board.height})
                  </option>
                ))}
              </select>
            </div>

            <div className="dialog-actions">
              <Button variant="ghost" type="button" onClick={handleClose}>
                Отмена
              </Button>
              <Button variant="primary" type="submit" loading={creatingGame}>
                Создать
              </Button>
            </div>
          </form>
        )}
      </div>
    </Modal>
  );
};

export default CreateGameDialog;