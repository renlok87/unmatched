import React from 'react';
import type { GamePlayer } from '@/store/roomStore';

interface PlayerSlotsProps {
  players: GamePlayer[];
  mode: string;
  currentUserId: string | null;
}

export const PlayerSlots: React.FC<PlayerSlotsProps> = ({
  players,
  mode,
  currentUserId,
}) => {
  const maxPlayers = mode === 'ONE_V_ONE' ? 2 : 4;

  const renderPlayerSlot = (player: GamePlayer | null, index: number) => {
    const isEmpty = !player;
    const isCurrentUser = player?.userId === currentUserId;

    return (
      <div
        key={index}
        className={`player-slot ${isEmpty ? 'player-slot--empty' : ''} ${
          isCurrentUser ? 'player-slot--current' : ''
        }`}
      >
        {isEmpty ? (
          <div className="player-slot__empty">
            <span className="player-slot__empty-icon">⌛</span>
            <span className="player-slot__empty-text">Ожидание игрока...</span>
          </div>
        ) : (
          <div className="player-slot__player">
            <div className="player-slot__avatar">
              {player.avatar ? (
                <img src={player.avatar} alt={player.username} />
              ) : (
                <span className="player-slot__avatar-placeholder">
                  {player.username.charAt(0).toUpperCase()}
                </span>
              )}
            </div>
            <div className="player-slot__info">
              <h4 className="player-slot__name">{player.username}</h4>
              {player.heroId && (
                <span className="player-slot__hero">Герой выбран</span>
              )}
            </div>
            <div
              className={`player-slot__status ${
                player.isReady ? 'player-slot__status--ready' : ''
              }`}
            >
              {player.isReady ? '✓ Готов' : '⏳ Не готов'}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="player-slots">
      <h3 className="player-slots__title">Игроки</h3>
      <div className="player-slots__grid">
        {Array.from({ length: maxPlayers }).map((_, index) =>
          renderPlayerSlot(players[index] || null, index),
        )}
      </div>
    </div>
  );
};

export default PlayerSlots;