import React from 'react';
import { Avatar } from '@/design-system/components/Avatar';
import { DefenseCardDisplay } from './DefenseCardDisplay';
import { DamageIndicator, type ValueModifier } from './DamageIndicator';
import './DefenderView.css';

export interface Fighter {
  id: string;
  name: string;
  type: 'hero' | 'sidekick';
  health: number;
  maxHealth: number;
  avatar?: string;
}

export interface Card {
  id: string;
  name: string;
  type: 'attack' | 'defense' | 'versatile' | 'scheme';
  value: number;
}

interface DefenderViewProps {
  fighter: Fighter;
  defenseCard: Card | null;
  defenseValue: number;
  modifiers: ValueModifier[];
  isHidden: boolean;
  showDamage?: number;
}

export const DefenderView: React.FC<DefenderViewProps> = ({
  fighter,
  defenseCard,
  defenseValue,
  modifiers,
  isHidden,
  showDamage,
}) => {
  const healthPercentage = (fighter.health / fighter.maxHealth) * 100;
  const healthColor = healthPercentage > 50 ? 'var(--color-success)' : healthPercentage > 25 ? 'var(--color-warning)' : 'var(--color-error)';

  return (
    <div className="defender-view">
      <div className="defender-view__fighter">
        <div className="defender-view__avatar">
          <Avatar
            src={fighter.avatar}
            alt={fighter.name}
            size="lg"
            variant="hero"
            fallback={fighter.name[0].toUpperCase()}
          />
          <div className="defender-view__fighter-type">
            {fighter.type === 'hero' ? '🦸' : '🦸‍♂️'}
          </div>
        </div>

        <div className="defender-view__info">
          <div className="defender-view__name">{fighter.name}</div>
          <div className="defender-view__health">
            <div className="defender-view__health-bar">
              <div
                className="defender-view__health-fill"
                style={{
                  width: `${healthPercentage}%`,
                  backgroundColor: healthColor,
                }}
              />
            </div>
            <div className="defender-view__health-text">
              {fighter.health}/{fighter.maxHealth}
            </div>
          </div>
        </div>
      </div>

      <DefenseCardDisplay
        card={defenseCard}
        defenseValue={defenseValue}
        isHidden={isHidden}
      />

      {modifiers.length > 0 && !isHidden && (
        <div className="defender-view__modifiers">
          {modifiers.map((mod, index) => (
            <div
              key={index}
              className={`defender-view__modifier defender-view__modifier--${mod.type}`}
              title={mod.description}
            >
              {mod.type === 'boost' && '⚡'}
              {mod.type === 'ignoreDefense' && '🛡️'}
              {mod.type === 'doubleDamage' && '💥'}
              {mod.type === 'shield' && '🔵'}
              {mod.value > 0 && <span>+{mod.value}</span>}
            </div>
          ))}
        </div>
      )}

      {showDamage !== undefined && showDamage > 0 && !isHidden && (
        <div className="defender-view__damage-indicator">
          <DamageIndicator damage={showDamage} target="defender" />
        </div>
      )}
    </div>
  );
};

export default DefenderView;