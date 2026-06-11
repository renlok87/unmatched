import React from 'react';
import { Button } from '@/design-system/components/Button';
import { Modal } from '@/design-system/components/Modal';
import './DiscardPileView.css';

export interface Card {
  id: string;
  name: string;
  type: 'attack' | 'defense' | 'versatile' | 'scheme';
  value: number;
  playerId?: string;
  playerName?: string;
}

interface DiscardPileViewProps {
  topCard: Card | null;
  discardCount: number;
  onExpand: () => void;
}

export const DiscardPileView: React.FC<DiscardPileViewProps> = ({
  topCard,
  discardCount,
  onExpand,
}) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [selectedPlayer, setSelectedPlayer] = React.useState<string | 'all'>('all');

  const handleExpand = () => {
    setIsExpanded(true);
    onExpand();
  };

  const handleCloseModal = () => {
    setIsExpanded(false);
  };

  return (
    <>
      <div className="discard-pile-view">
        <div className="discard-pile-view__pile">
          {topCard ? (
            <div
              className={`discard-pile-view__top-card discard-pile-view__top-card--${topCard.type}`}
              onClick={discardCount > 1 ? handleExpand : undefined}
              style={{ cursor: discardCount > 1 ? 'pointer' : 'default' }}
            >
              <div className="discard-pile-view__card-value">
                {topCard.value}
              </div>
              <div className="discard-pile-view__card-name">
                {topCard.name}
              </div>
              {discardCount > 1 && (
                <div className="discard-pile-view__card-count">
                  +{discardCount - 1}
                </div>
              )}
            </div>
          ) : (
            <div className="discard-pile-view__empty">
              <span className="discard-pile-view__empty-icon">📚</span>
              <span className="discard-pile-view__empty-text">Пусто</span>
            </div>
          )}
        </div>

        {discardCount > 1 && (
          <Button
            variant="ghost"
            onClick={handleExpand}
            className="discard-pile-view__expand-btn"
          >
            Показать все ({discardCount})
          </Button>
        )}
      </div>

      <Modal
        isOpen={isExpanded}
        onClose={handleCloseModal}
        title="Сброс"
        size="lg"
      >
        <div className="discard-pile-view__modal">
          <div className="discard-pile-view__modal-filters">
            <Button
              variant={selectedPlayer === 'all' ? 'primary' : 'ghost'}
              onClick={() => setSelectedPlayer('all')}
              size="sm"
            >
              Все
            </Button>
          </div>
          <div className="discard-pile-view__modal-content">
            <div className="discard-pile-view__modal-message">
              Список сброшенных карт будет загружен из игрового состояния
            </div>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default DiscardPileView;