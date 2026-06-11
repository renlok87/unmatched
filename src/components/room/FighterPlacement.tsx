import React from 'react';
import { Button } from '@/design-system/components/Button';
import './FighterPlacement.css';

export interface Fighter {
  id: string;
  name: string;
  type: 'hero' | 'sidekick';
  health: number;
  maxHealth: number;
}

export interface SpawnZone {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  label: string;
}

interface FighterPlacementProps {
  fighters: Fighter[];
  spawnZones: SpawnZone[];
  placedFighters: Record<string, string>;
  onPlaceFighter: (fighterId: string, zoneId: string) => void;
  onRemoveFighter: (fighterId: string) => void;
  onConfirm: () => void;
  isConfirmEnabled: boolean;
  isConfirming?: boolean;
}

export const FighterPlacement: React.FC<FighterPlacementProps> = ({
  fighters,
  spawnZones,
  placedFighters,
  onPlaceFighter,
  onRemoveFighter,
  onConfirm,
  isConfirmEnabled,
  isConfirming = false,
}) => {
  const [selectedFighter, setSelectedFighter] = React.useState<string | null>(null);

  const handleZoneClick = (zoneId: string) => {
    if (!selectedFighter) return;

    const existingFighterInZone = Object.entries(placedFighters).find(
      ([_, z]) => z === zoneId
    );

    if (existingFighterInZone) {
      onRemoveFighter(existingFighterInZone[0]);
    }

    onPlaceFighter(selectedFighter, zoneId);
    setSelectedFighter(null);
  };

  const handleFighterClick = (fighterId: string) => {
    if (placedFighters[fighterId]) {
      onRemoveFighter(fighterId);
    } else {
      setSelectedFighter(selectedFighter === fighterId ? null : fighterId);
    }
  };

  const getZoneFighter = (zoneId: string) => {
    return Object.entries(placedFighters).find(([_, z]) => z === zoneId);
  };

  return (
    <div className="fighter-placement">
      <div className="fighter-placement__header">
        <h3 className="fighter-placement__title">Размещение бойцов</h3>
        <p className="fighter-placement__subtitle">
          Выберите бойца и кликните на зону для размещения
        </p>
      </div>

      <div className="fighter-placement__content">
        <div className="fighter-placement__fighters">
          <h4 className="fighter-placement__section-title">Ваи бойцы</h4>
          <div className="fighter-placement__fighter-list">
            {fighters.map((fighter) => {
              const isPlaced = !!placedFighters[fighter.id];
              const isSelected = selectedFighter === fighter.id;

              return (
                <button
                  key={fighter.id}
                  className={`fighter-placement__fighter-card ${
                    isPlaced ? 'fighter-placement__fighter-card--placed' : ''
                  } ${isSelected ? 'fighter-placement__fighter-card--selected' : ''}`}
                  onClick={() => handleFighterClick(fighter.id)}
                  disabled={isConfirming}
                >
                  <div className="fighter-placement__fighter-type">
                    {fighter.type === 'hero' ? '🦸' : '🦸‍♂️'}
                  </div>
                  <div className="fighter-placement__fighter-info">
                    <div className="fighter-placement__fighter-name">
                      {fighter.name}
                    </div>
                    <div className="fighter-placement__fighter-health">
                      ❤️ {fighter.health}/{fighter.maxHealth}
                    </div>
                  </div>
                  {isPlaced && (
                    <div className="fighter-placement__fighter-status">
                      ✓ Размещен
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="fighter-placement__board">
          <h4 className="fighter-placement__section-title">Игровое поле</h4>
          <div className="fighter-placement__board-grid">
            {spawnZones.map((zone) => {
              const zoneFighter = getZoneFighter(zone.id);
              const isHovered = selectedFighter !== null;

              return (
                <button
                  key={zone.id}
                  className={`fighter-placement__zone fighter-placement__zone--${zone.color} ${
                    zoneFighter ? 'fighter-placement__zone--occupied' : ''
                  } ${isHovered && !zoneFighter ? 'fighter-placement__zone--available' : ''}`}
                  style={{
                    left: `${zone.x}%`,
                    top: `${zone.y}%`,
                    width: `${zone.width}%`,
                    height: `${zone.height}%`,
                  }}
                  onClick={() => handleZoneClick(zone.id)}
                  disabled={isConfirming}
                >
                  {zoneFighter ? (
                    <div className="fighter-placement__zone-fighter">
                      {fighters.find((f) => f.id === zoneFighter[0])?.name}
                      <button
                        className="fighter-placement__zone-remove"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveFighter(zoneFighter[0]);
                        }}
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <div className="fighter-placement__zone-label">
                      {zone.label}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="fighter-placement__actions">
        <Button
          variant="success"
          onClick={onConfirm}
          disabled={!isConfirmEnabled || isConfirming}
          loading={isConfirming}
        >
          {isConfirming ? 'Подтверждение...' : 'Подтвердить размещение'}
        </Button>
      </div>
    </div>
  );
};

export default FighterPlacement;