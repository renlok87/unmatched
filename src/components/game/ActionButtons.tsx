import React from 'react';
import { Button } from '@/design-system/components/Button';
import { Modal } from '@/design-system/components/Modal';
import './ActionButtons.css';

interface ActionButtonsProps {
  canEndTurn: boolean;
  canPass: boolean;
  onEndTurn: () => void;
  onPass: () => void;
}

export const ActionButtons: React.FC<ActionButtonsProps> = ({
  canEndTurn,
  canPass,
  onEndTurn,
  onPass,
}) => {
  const [showEndTurnModal, setShowEndTurnModal] = React.useState(false);
  const [showPassModal, setShowPassModal] = React.useState(false);

  const handleEndTurn = () => {
    setShowEndTurnModal(true);
  };

  const confirmEndTurn = () => {
    setShowEndTurnModal(false);
    onEndTurn();
  };

  const handlePass = () => {
    setShowPassModal(true);
  };

  const confirmPass = () => {
    setShowPassModal(false);
    onPass();
  };

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && canEndTurn) {
        e.preventDefault();
        handleEndTurn();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [canEndTurn]);

  return (
    <>
      <div className="action-buttons">
        <Button
          variant="primary"
          onClick={handleEndTurn}
          disabled={!canEndTurn}
          className="action-buttons__end-turn"
        >
          Конец хода
          <span className="action-buttons__hotkey">Space</span>
        </Button>

        <Button
          variant="secondary"
          onClick={handlePass}
          disabled={!canPass}
          className="action-buttons__pass"
        >
          Пас
        </Button>
      </div>

      <Modal
        isOpen={showEndTurnModal}
        onClose={() => setShowEndTurnModal(false)}
        title="Завершить ход"
      >
        <div className="action-buttons__modal">
          <p className="action-buttons__modal-text">
            Вы уверены, что хотите завершить ход?
          </p>
          <div className="action-buttons__modal-actions">
            <Button variant="ghost" onClick={() => setShowEndTurnModal(false)}>
              Отмена
            </Button>
            <Button variant="primary" onClick={confirmEndTurn}>
              Завершить
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showPassModal}
        onClose={() => setShowPassModal(false)}
        title="Пас"
      >
        <div className="action-buttons__modal">
          <p className="action-buttons__modal-text">
            Вы уверены, что хотите пасануть? Это сбросит текущую карту.
          </p>
          <div className="action-buttons__modal-actions">
            <Button variant="ghost" onClick={() => setShowPassModal(false)}>
              Отмена
            </Button>
            <Button variant="secondary" onClick={confirmPass}>
              Пасануть
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default ActionButtons;