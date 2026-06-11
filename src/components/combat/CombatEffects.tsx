import React from 'react';
import { type ValueModifier } from './DamageIndicator';
import './CombatEffects.css';

interface CombatEffectsProps {
  effects: ValueModifier[];
}

export const CombatEffects: React.FC<CombatEffectsProps> = ({ effects }) => {
  if (effects.length === 0) return null;

  const getEffectIcon = (type: ValueModifier['type']) => {
    switch (type) {
      case 'boost':
        return '⚡';
      case 'ignoreDefense':
        return '🛡️';
      case 'doubleDamage':
        return '💥';
      case 'shield':
        return '🔵';
      default:
        return '✨';
    }
  };

  const getEffectLabel = (type: ValueModifier['type']) => {
    switch (type) {
      case 'boost':
        return 'Усиление';
      case 'ignoreDefense':
        return 'Игнор защиты';
      case 'doubleDamage':
        return 'Двойной урон';
      case 'shield':
        return 'Щит';
      default:
        return 'Эффект';
    }
  };

  return (
    <div className="combat-effects">
      <h4 className="combat-effects__title">Активные эффекты</h4>
      <div className="combat-effects__list">
        {effects.map((effect, index) => (
          <div
            key={index}
            className={`combat-effects__item combat-effects__item--${effect.type}`}
            title={effect.description}
          >
            <span className="combat-effects__icon">
              {getEffectIcon(effect.type)}
            </span>
            <span className="combat-effects__label">
              {getEffectLabel(effect.type)}
            </span>
            {effect.value > 0 && (
              <span className="combat-effects__value">+{effect.value}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default CombatEffects;