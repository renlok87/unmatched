import React from 'react';
import { Button } from '@/design-system/components/Button';
import './GameHeader.css';

interface GameHeaderProps {
  turnNumber: number;
  roundNumber: number;
  isConnected: boolean;
  onSettings: () => void;
  onLeave: () => void;
}

export const GameHeader: React.FC<GameHeaderProps> = ({
  turnNumber,
  roundNumber,
  isConnected,
  onSettings,
  onLeave,
}) => {
  return (
    <header className="game-header">
      <div className="game-header__info">
        <div className="game-header__turn">
          <span className="game-header__label">Ход:</span>
          <span className="game-header__value">{turnNumber}</span>
        </div>
        <div className="game-header__round">
          <span className="game-header__label">Раунд:</span>
          <span className="game-header__value">{roundNumber}</span>
        </div>
      </div>

      <div className="game-header__connection">
        <div
          className={`game-header__status game-header__status--${
            isConnected ? 'connected' : 'disconnected'
          }`}
        >
          <span className="game-header__status-dot" />
          <span className="game-header__status-text">
            {isConnected ? 'Онлайн' : 'Переподключение...'}
          </span>
        </div>
      </div>

      <div className="game-header__actions">
        <Button variant="ghost" onClick={onSettings} icon>
          ⚙️
        </Button>
        <Button variant="ghost" onClick={onLeave} icon>
          🚪
        </Button>
      </div>
    </header>
  );
};

export default GameHeader;