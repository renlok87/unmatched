import React from 'react';
import { useGameStore } from '../../store/gameStore';
import type { Position } from '../../core/models/types';
import './BoardView.css';

interface BoardViewProps {
  interactive?: boolean;
}

export const BoardView: React.FC<BoardViewProps> = ({ interactive = true }) => {
  const { gameState, highlightedSpaces } = useGameStore();

  if (!gameState) {
    return (
      <div className="board-container">
        <div className="board-placeholder">
          <p>Игра не инициализирована</p>
          <button onClick={() => useGameStore.getState().initializeGame()}>
            Начать игру
          </button>
        </div>
      </div>
    );
  }

  const { definition: board } = gameState.board;

  const handleSpaceClick = (position: Position) => {
    if (!interactive) return;

    const { selectedFighterId, moveFighter } = useGameStore.getState();

    if (selectedFighterId) {
      const isValid = highlightedSpaces.some(
        p => p.x === position.x && p.y === position.y
      );
      if (isValid) {
        moveFighter(selectedFighterId, position);
      }
    }
  };

  const isHighlighted = (position: Position): boolean => {
    return highlightedSpaces.some(
      p => p.x === position.x && p.y === position.y
    );
  };

  const getFighterAt = (position: Position) => {
    return gameState.players
      .flatMap(p => p.fighters)
      .find(f =>
        !f.isDefeated &&
        f.position.x === position.x &&
        f.position.y === position.y
      );
  };

  const getZoneColor = (zones: string[]) => {
    const zoneColors: Record<string, string> = {
      blue: '#3b82f6',
      green: '#22c55e',
      yellow: '#eab308',
      red: '#ef4444',
      purple: '#a855f7',
    };

    if (zones.length === 1) {
      return zoneColors[zones[0]] || '#6b7280';
    }

    // Mixed zones - create gradient
    const colors = zones.map(z => zoneColors[z]).filter(Boolean);
    return `linear-gradient(135deg, ${colors[0]} 50%, ${colors[1] || colors[0]} 50%)`;
  };

  return (
    <div className="board-container">
      <div className="board-header">
        <h2>{board.name}</h2>
      </div>
      <div
        className="board-grid"
        style={{
          gridTemplateColumns: `repeat(${board.width}, 1fr)`,
          gridTemplateRows: `repeat(${board.height}, 1fr)`,
        }}
      >
        {board.spaces.map((space) => {
          const fighter = getFighterAt(space.position);
          const highlighted = isHighlighted(space.position);

          return (
            <div
              key={`${space.position.x}-${space.position.y}`}
              className={`board-space ${highlighted ? 'highlighted' : ''} ${fighter ? 'occupied' : ''}`}
              style={{
                backgroundColor: space.zones.length === 1 ? getZoneColor(space.zones) : undefined,
                background: space.zones.length > 1 ? getZoneColor(space.zones) : undefined,
              }}
              onClick={() => handleSpaceClick(space.position)}
            >
              <div className="space-coords">
                {space.position.x},{space.position.y}
              </div>
              {space.zones.length > 1 && (
                <div className="space-zones">
                  {space.zones.map(z => (
                    <span key={z} className="zone-indicator">{z[0]}</span>
                  ))}
                </div>
              )}
              {fighter && (
                <div className={`fighter-token ${fighter.type}`}>
                  <div className="fighter-name">
                    {fighter.type === 'hero' ? 'H' : 'S'}
                  </div>
                  <div className="fighter-health">
                    {fighter.health}/{fighter.maxHealth}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="board-legend">
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#3b82f6' }}></span>
          <span>Blue</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#22c55e' }}></span>
          <span>Green</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#eab308' }}></span>
          <span>Yellow</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#ef4444' }}></span>
          <span>Red</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#a855f7' }}></span>
          <span>Purple</span>
        </div>
      </div>
    </div>
  );
};
