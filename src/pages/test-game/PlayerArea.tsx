import React from 'react';
import { Card } from '@/components/cards/Card';
import type { Player } from '@/core/models/types';
import './PlayerArea.css';

interface PlayerAreaProps {
  player: Player;
  isCurrent: boolean;
  showCards: boolean;
  onCardClick?: (cardId: string) => void;
  selectedCardId?: string | null;
}

export const PlayerArea: React.FC<PlayerAreaProps> = ({
  player,
  isCurrent,
  showCards,
  onCardClick,
  selectedCardId,
}) => {
  const hero = player.fighters.find((f) => f.type === 'hero');
  const sidekicks = player.fighters.filter((f) => f.type === 'sidekick');

  return (
    <div className={`player-area ${isCurrent ? 'current' : ''}`}>
      <div className="player-header">
        <h3 className="player-name">{player.name}</h3>
        <div className="player-turn-indicator">
          {isCurrent && <span className="turn-badge">Текущий ход</span>}
        </div>
      </div>

      <div className="player-fighters">
        {hero && (
          <div className="fighter-status hero">
            <span className="fighter-icon" title="Герой">
              🦸
            </span>
            <div className="fighter-info">
              <span className="fighter-name">Герой</span>
              <div className="health-bar-container">
                <div className="health-bar">
                  <div
                    className="health-fill"
                    style={{
                      width: `${(hero.health / hero.maxHealth) * 100}%`,
                      backgroundColor: getHealthColor(hero.health, hero.maxHealth),
                    }}
                  />
                </div>
                <span className="health-text">
                  {hero.health}/{hero.maxHealth}
                </span>
              </div>
              <div className="fighter-position">
                Позиция: ({hero.position.x}, {hero.position.y})
              </div>
            </div>
          </div>
        )}

        {sidekicks.map((sidekick) => (
          <div key={sidekick.id} className="fighter-status sidekick">
            <span className="fighter-icon" title="Помощник">
              🧑‍🤝‍🧑
            </span>
            <div className="fighter-info">
              <span className="fighter-name">Помощник</span>
              <div className="health-bar-container">
                <div className="health-bar">
                  <div
                    className="health-fill"
                    style={{
                      width: `${(sidekick.health / sidekick.maxHealth) * 100}%`,
                      backgroundColor: getHealthColor(sidekick.health, sidekick.maxHealth),
                    }}
                  />
                </div>
                <span className="health-text">
                  {sidekick.health}/{sidekick.maxHealth}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {showCards && (
        <div className="player-hand">
          <div className="hand-header">
            <span className="hand-title">Рука ({player.hand.length})</span>
            <div className="hand-stats">
              <span className="deck-count">📥 Колодa: {player.deck.length}</span>
              <span className="discard-count">🗑️ Сброс: {player.discardPile.length}</span>
            </div>
          </div>

          <div className="hand-cards">
            {player.hand.length === 0 ? (
              <div className="empty-hand">Нет карт</div>
            ) : (
              player.hand.map((card) => (
                <Card
                  key={card.id}
                  card={card}
                  isPlayable={isCurrent}
                  isSelected={selectedCardId === card.id}
                  onClick={() => isCurrent && onCardClick?.(card.id)}
                />
              ))
            )}
          </div>

          <div className="player-actions">
            <div className="actions-remaining">
              Очки действий: {player.actionsRemaining}
            </div>
            {player.hasPassed && (
              <div className="passed-badge">Пас</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

function getHealthColor(current: number, max: number): string {
  const percentage = (current / max) * 100;

  if (percentage > 60) {
    return 'var(--color-success)';
  } else if (percentage > 30) {
    return 'var(--color-warning)';
  } else {
    return 'var(--color-error)';
  }
}
