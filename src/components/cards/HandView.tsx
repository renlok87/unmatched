import React from 'react';
import { useGameStore } from '../../store/gameStore';
import Card from './Card';
import './HandView.css';

export const HandView: React.FC = () => {
  const { gameState, selectedCardId, selectCard } = useGameStore();

  if (!gameState) {
    return (
      <div className="hand-container">
        <div className="hand-placeholder">
          <p>Рука игрока</p>
        </div>
      </div>
    );
  }

  const currentPlayer = gameState.players.find(
    p => p.id === gameState.currentTurn.currentPlayerId
  );

  if (!currentPlayer) {
    return (
      <div className="hand-container">
        <div className="hand-placeholder">
          <p>Нет активного игрока</p>
        </div>
      </div>
    );
  }

  const handleCardClick = (cardId: string) => {
    if (selectedCardId === cardId) {
      selectCard(null); // Deselect
    } else {
      selectCard(cardId);
    }
  };

  const canPlayCard = (cardId: string) => {
    // Current player can only play their own cards
    return currentPlayer.hand.some(c => c.id === cardId);
  };

  return (
    <div className="hand-container">
      <div className="hand-header">
        <h3>{currentPlayer.name}</h3>
        <div className="hand-info">
          <span>Рука: {currentPlayer.hand.length}</span>
          <span>Колода: {currentPlayer.deck.length}</span>
          <span>Сброс: {currentPlayer.discardPile.length}</span>
        </div>
      </div>

      {currentPlayer.fighters.filter(f => !f.isDefeated).map(fighter => (
        <div key={fighter.id} className="fighter-status">
          <span className="fighter-name">
            {fighter.type === 'hero' ? '🦸' : '🧑‍✈️'} {fighter.type}
          </span>
          <div className="health-bar">
            <div
              className="health-fill"
              style={{
                width: `${(fighter.health / fighter.maxHealth) * 100}%`,
                backgroundColor: fighter.health <= fighter.maxHealth * 0.3 ? '#ef4444' : '#10b981',
              }}
            />
          </div>
          <span className="health-text">{fighter.health}/{fighter.maxHealth}</span>
        </div>
      ))}

      <div className="hand-cards">
        {currentPlayer.hand.length === 0 ? (
          <div className="empty-hand">Нет карт</div>
        ) : (
          currentPlayer.hand.map((card) => (
            <Card
              key={card.id}
              card={card}
              onClick={() => handleCardClick(card.id)}
              isPlayable={canPlayCard(card.id)}
              isSelected={selectedCardId === card.id}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default HandView;
