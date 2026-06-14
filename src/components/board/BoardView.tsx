import React from 'react';
import { useGameStore } from '../../store/gameStore';
import type { Position, GameState } from '../../core/models/types';
import './BoardView.css';

interface BoardViewProps {
  interactive?: boolean;
  gameState?: GameState | null;
  highlightedSpaces?: Position[];
  onFighterSelect?: (fighterId: string) => void;
  onSpaceClick?: (position: Position) => void;
}

export const BoardView: React.FC<BoardViewProps> = ({
  interactive = true,
  gameState: propsGameState,
  highlightedSpaces: propsHighlightedSpaces,
  onFighterSelect,
  onSpaceClick,
}) => {
  const { gameState: storeGameState, highlightedSpaces: storeHighlightedSpaces, selectedFighterId } = useGameStore();

  // Use props if provided, otherwise fall back to store
  const gameState = propsGameState ?? storeGameState;
  const highlightedSpaces = propsHighlightedSpaces ?? storeHighlightedSpaces;

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

    // Use custom handler if provided
    if (onSpaceClick) {
      onSpaceClick(position);
      return;
    }

    // Otherwise use store handler
    const { moveFighter } = useGameStore.getState();

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
      brown: '#92400e',
      gray: '#6b7280',
      orange: '#f97316',
      pink: '#ec4899',
      white: '#e5e7eb',
      gold: '#d4af37',
      beige: '#d6c8a8',
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
          backgroundImage: board.imageUrl ? `url(${board.imageUrl})` : undefined,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
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
                backgroundColor: !board.imageUrl && space.zones.length === 1 ? getZoneColor(space.zones) : undefined,
                background: !board.imageUrl && space.zones.length > 1 ? getZoneColor(space.zones) : undefined,
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
                <div
                  className={`fighter-token ${fighter.type}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onFighterSelect) {
                      onFighterSelect(fighter.id);
                    }
                  }}
                >
                  {fighter.avatarUrl ? (
                    <img
                      src={fighter.avatarUrl}
                      alt={fighter.type}
                      className="fighter-avatar"
                    />
                  ) : (
                    <div className="fighter-name">
                      {fighter.type === 'hero' ? 'H' : 'S'}
                    </div>
                  )}
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
