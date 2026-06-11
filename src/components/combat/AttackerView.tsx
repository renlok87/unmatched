import React from 'react';
import { Avatar } from '@/design-system/components/Avatar';
import { AttackCardDisplay } from './AttackCardDisplay';
import { DamageIndicator, type ValueModifier } from './DamageIndicator';
import './AttackerView.css';

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

interface AttackerViewProps {
  fighter: Fighter;
  attackCard: Card;
  attackValue: number;
  modifiers: ValueModifier[];
  showDamage?: number;
}

export const AttackerView: React.FC<AttackerViewProps> = ({
  fighter,
  attackCard,
  attackValue,
  modifiers,
  showDamage,
}) => {
  const healthPercentage = (fighter.health / fighter.maxHealth) * 100;
  const healthColor = healthPercentage > 50 ? 'var(--color-success)' : healthPercentage > 25 ? 'var(--color-warning)' : 'var(--color-error)';

  return (
    <div className="attacker-view">
      <div className="attacker-view__fighter">
        <div className="attacker-view__avatar">
          <Avatar
            src={fighter.avatar}
            alt={fighter.name}
            size="lg"
            variant="hero"
            fallback={fighter.name[0].toUpperCase()}
          />
          <div className="attacker-view__fighter-type">
            {fighter.type === 'hero' ? '🦸' : '🦸‍♂️'}
          </div>
        </div>

        <div className="attacker-view__info">
          <div className="attacker-view__name">{fighter.name}</div>
          <div className="attacker-view__health">
            <div className="attacker-view__health-bar">
              <div
                className="attacker-view__health-fill"
                style={{
                  width: `${healthPercentage}%`,
                  backgroundColor: healthColor,
                }}
              />
            </div>
            <div className="attacker-view__health-text">
              {fighter.health}/{fighter.maxHealth}
            </div>
          </div>
        </div>
      </div>

      <AttackCardDisplay card={attackCard} attackValue={attackValue} />

      {modifiers.length > 0 && (
        <div className="attacker-view__modifiers">
          {modifiers.map((mod, index) => (
            <div
              key={index}
              className="attacker-view__modifier attacker-view__modifier--${mod.type}"
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

      {showDamage !== undefined && showDamage > 0 && (
        <div className="attacker-view__damage-indicator">
          <DamageIndicator damage={showDamage} target="attacker" />
        </div>
      )}
    </div>
  );
};

export default AttackerView;