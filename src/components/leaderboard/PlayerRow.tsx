import React from 'react';
import './PlayerRow.css';

export type LeaderboardEntry = {
  rank: number;
  user: {
    id: string;
    username: string;
    avatar?: string;
    country?: string;
  };
  rating: number;
  gamesPlayed: number;
  wins: number;
  winRate: number;
  streak: number;
}

interface PlayerRowProps {
  player: LeaderboardEntry;
  isCurrentUser: boolean;
  onClick: (playerId: string) => void;
}

export const PlayerRow: React.FC<PlayerRowProps> = ({ player, isCurrentUser, onClick }) => {
  const getRankIcon = (rank: number) => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return rank;
  };

  const getStreakIcon = (streak: number) => {
    if (streak > 0) return `🔥 +${streak}`;
    if (streak < 0) return `❄️ ${streak}`;
    return '-';
  };

  const getCountryFlag = (country?: string) => {
    const flags: Record<string, string> = {
      ru: '🇷🇺',
      us: '🇺🇸',
      gb: '🇬🇧',
      de: '🇩🇪',
      fr: '🇫🇷',
      es: '🇪🇸',
      it: '🇮🇹',
      jp: '🇯🇵',
      cn: '🇨🇳',
      br: '🇧🇷',
    };
    return country ? flags[country.toLowerCase()] || '' : '';
  };

  return (
    <tr
      className={`player-row ${isCurrentUser ? 'player-row--current' : ''}`}
      onClick={() => onClick(player.user.id)}
    >
      <td className="player-row__rank">
        <span className="player-row__rank-icon">{getRankIcon(player.rank)}</span>
      </td>
      <td className="player-row__player">
        <div className="player-row__player-info">
          {player.user.avatar ? (
            <img
              src={player.user.avatar}
              alt={player.user.username}
              className="player-row__avatar"
            />
          ) : (
            <div className="player-row__avatar-placeholder">
              {player.user.username[0].toUpperCase()}
            </div>
          )}
          <div className="player-row__player-details">
            <div className="player-row__username">
              {player.user.username}
              {getCountryFlag(player.user.country) && (
                <span className="player-row__country">
                  {getCountryFlag(player.user.country)}
                </span>
              )}
            </div>
            {isCurrentUser && <span className="player-row__badge">Вы</span>}
          </div>
        </div>
      </td>
      <td className="player-row__rating">
        <span className="player-row__rating-value">{player.rating}</span>
      </td>
      <td className="player-row__win-rate">
        <div className="player-row__win-rate-bar">
          <div
            className="player-row__win-rate-fill"
            style={{ width: `${player.winRate}%` }}
          />
        </div>
        <span className="player-row__win-rate-text">{player.winRate}%</span>
      </td>
      <td className="player-row__games">{player.gamesPlayed}</td>
      <td className="player-row__streak">
        <span
          className={`player-row__streak-value ${
            player.streak > 0
              ? 'player-row__streak-value--positive'
              : player.streak < 0
                ? 'player-row__streak-value--negative'
                : ''
          }`}
        >
          {getStreakIcon(player.streak)}
        </span>
      </td>
    </tr>
  );
};