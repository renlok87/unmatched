import React, { useEffect, useState } from 'react';
import { Button } from '@/design-system/components/Button';
import { type Fighter } from './AttackerView';
import './CombatResolution.css';

interface CombatResolutionProps {
  attacker: Fighter;
  defender: Fighter;
  damageToAttacker: number;
  damageToDefender: number;
  onComplete: () => void;
}

export const CombatResolution: React.FC<CombatResolutionProps> = ({
  attacker,
  defender,
  damageToAttacker,
  damageToDefender,
  onComplete,
}) => {
  const [step, setStep] = useState(0);
  const [showDamage, setShowDamage] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setStep(1);
      setShowDamage(true);
    }, 1000);

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (step === 1) {
      const timer = setTimeout(() => {
        setStep(2);
      }, 2000);

      return () => clearTimeout(timer);
    }
  }, [step]);

  const handleContinue = () => {
    onComplete();
  };

  const getHealthColor = (current: number, max: number) => {
    const percentage = (current / max) * 100;
    if (percentage > 50) return 'var(--color-success)';
    if (percentage > 25) return 'var(--color-warning)';
    return 'var(--color-error)';
  };

  return (
    <div className="combat-resolution">
      <div className="combat-resolution__content">
        <h2 className="combat-resolution__title">Расчёт боя</h2>

        <div className="combat-resolution__fighters">
          <div className="combat-resolution__fighter">
            <div className="combat-resolution__fighter-name">
              {attacker.name}
            </div>
            <div className="combat-resolution__fighter-health">
              <div className="combat-resolution__health-bar">
                <div
                  className="combat-resolution__health-fill"
                  style={{
                    width: `${(attacker.health / attacker.maxHealth) * 100}%`,
                    backgroundColor: getHealthColor(attacker.health, attacker.maxHealth),
                  }}
                />
              </div>
              <div className="combat-resolution__health-text">
                {attacker.health}/{attacker.maxHealth}
              </div>
            </div>
            {showDamage && damageToAttacker > 0 && (
              <div className="combat-resolution__damage combat-resolution__damage--attacker">
                -{damageToAttacker}
              </div>
            )}
          </div>

          <div className="combat-resolution__vs">VS</div>

          <div className="combat-resolution__fighter">
            <div className="combat-resolution__fighter-name">
              {defender.name}
            </div>
            <div className="combat-resolution__fighter-health">
              <div className="combat-resolution__health-bar">
                <div
                  className="combat-resolution__health-fill"
                  style={{
                    width: `${(defender.health / defender.maxHealth) * 100}%`,
                    backgroundColor: getHealthColor(defender.health, defender.maxHealth),
                  }}
                />
              </div>
              <div className="combat-resolution__health-text">
                {defender.health}/{defender.maxHealth}
              </div>
            </div>
            {showDamage && damageToDefender > 0 && (
              <div className="combat-resolution__damage combat-resolution__damage--defender">
                -{damageToDefender}
              </div>
            )}
          </div>
        </div>

        {step === 2 && (
          <div className="combat-resolution__summary">
            <div className="combat-resolution__summary-item">
              <span>Урон атакующему:</span>
              <span className="combat-resolution__summary-value">
                {damageToAttacker > 0 ? `-${damageToAttacker}` : '0'}
              </span>
            </div>
            <div className="combat-resolution__summary-item">
              <span>Урон защищающемуся:</span>
              <span className="combat-resolution__summary-value">
                {damageToDefender > 0 ? `-${damageToDefender}` : '0'}
              </span>
            </div>
          </div>
        )}

        <div className="combat-resolution__actions">
          {step === 2 && (
            <Button variant="primary" onClick={handleContinue}>
              Продолжить
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default CombatResolution;