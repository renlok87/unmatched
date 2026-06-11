import React, { useEffect } from 'react';
import './DamageIndicator.css';

export interface ValueModifier {
  type: 'boost' | 'ignoreDefense' | 'doubleDamage' | 'shield';
  value: number;
  description: string;
}

interface DamageIndicatorProps {
  damage: number;
  target: 'attacker' | 'defender';
  onAnimationComplete?: () => void;
}

export const DamageIndicator: React.FC<DamageIndicatorProps> = ({
  damage,
  target,
  onAnimationComplete,
}) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onAnimationComplete?.();
    }, 1000);

    return () => clearTimeout(timer);
  }, [onAnimationComplete]);

  if (damage <= 0) return null;

  return (
    <div className={`damage-indicator damage-indicator--${target}`}>
      <div className="damage-indicator__value">
        {damage > 0 ? `-${damage}` : `+${Math.abs(damage)}`}
      </div>
      <div className="damage-indicator__icon">
        {damage > 0 ? '💥' : '💚'}
      </div>
    </div>
  );
};

export default DamageIndicator;