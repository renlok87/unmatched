import React from 'react';
import { Button } from '@/design-system/components/Button';
import { Avatar } from '@/design-system/components/Avatar';
import { Badge } from '@/design-system/components/Badge';
import type { GameResponse, GameStatus, GameMode } from '@/gql';

interface GameCardProps {
  game: GameResponse;
  onJoin: (gameId: string) => void;
  onView?: (gameId: string) => void;
}

const statusLabels: Record<GameStatus, string> = {
  LOBBY: 'В лобби',
  IN_PROGRESS: 'В процессе',
  FINISHED: 'Завершена',
  PAUSED: 'Пауза',
  ABORTED: 'Отменена',
  PENDING: 'Ожидание',
};

const statusColors: Record<GameStatus, string> = {
  LOBBY: 'bg-green-500',
  IN_PROGRESS: 'bg-blue-500',
  FINISHED: 'bg-gray-500',
  PAUSED: 'bg-yellow-500',
  ABORTED: 'bg-red-500',
  PENDING: 'bg-gray-400',
};

const modeLabels: Record<GameMode, string> = {
  ONE_V_ONE: '1 на 1',
  TWO_V_TWO: '2 на 2',
  FREE_FOR_ALL: 'Free for All',
  VS_AI: 'Против ИИ',
};

export const GameCard: React.FC<GameCardProps> = ({ game, onJoin, onView }) => {
  const host = game.players.find(p => p.userId === game.hostId);
  const opponent = game.players.find(p => p.userId !== game.hostId);
  const isJoinable = game.status === 'LOBBY' && game.players.length < 2;

  return (
    <div className="game-card">
      <div className="game-card-header">
        <div className="game-card-title">
          <h3>Игра #{game.id.slice(-6)}</h3>
          <Badge className={statusColors[game.status]}>{statusLabels[game.status]}</Badge>
        </div>
        <div className="game-card-mode">
          {modeLabels[game.mode]}
        </div>
      </div>

      <div className="game-card-players">
        <div className="player-info">
          <div className="player-avatar">
            <Avatar 
              src={host?.avatar || undefined}
              alt={host?.username || 'Host'} 
              size="sm" 
              fallback={host?.username?.charAt(0)}
            />
          </div>
          <div className="player-details">
            <span className="player-name">{host?.username || 'Host'}</span>
            <span className="player-status">Хост</span>
          </div>
          {host?.heroId && (
            <span className="hero-indicator">🦸</span>
          )}
        </div>

        {opponent ? (
          <div className="player-info">
            <div className="player-avatar">
              <Avatar 
                src={opponent.avatar || undefined}
                alt={opponent.username} 
                size="sm"
                fallback={opponent.username.charAt(0)}
              />
            </div>
            <div className="player-details">
              <span className="player-name">{opponent.username}</span>
              <span className="player-status">Оппонент</span>
            </div>
            {opponent.heroId && (
              <span className="hero-indicator">🦸</span>
            )}
          </div>
        ) : (
          <div className="player-info player-empty">
            <div className="player-avatar">
              <div className="avatar-placeholder">?</div>
            </div>
            <div className="player-details">
              <span className="player-name">Ожидание игрока...</span>
            </div>
          </div>
        )}
      </div>

      <div className="game-card-footer">
        <span className="game-time">
          {new Date(game.createdAt).toLocaleDateString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>

        <div className="game-card-actions">
          {onView && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onView(game.id)}
            >
              Просмотр
            </Button>
          )}
          
          {isJoinable && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => onJoin(game.id)}
            >
              Присоединиться
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default GameCard;