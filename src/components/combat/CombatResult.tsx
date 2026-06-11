import React from 'react';
import { Button } from '@/design-system/components/Button';
import { type Fighter } from './AttackerView';
import './CombatResult.css';

interface CombatResultProps {
  winner: 'attacker' | 'defender' | 'draw' | null;
  attacker: Fighter;
  defender: Fighter;
  damageToAttacker: number;
  damageToDefender: number;
  onContinue: () => void;
}

export const CombatResult: React.FC<CombatResultProps> = ({
  winner,
  attacker,
  defender,
  damageToAttacker,
  damageToDefender,
  onContinue,
}) => {
  const getResultMessage = () => {
    switch (winner) {
      case 'attacker':
        return `${attacker.name} побеждает!`;
      case 'defender':
        return `${defender.name} побеждает!`;
      case 'draw':
        return 'Ничья!';
      default:
        return 'Бой завершён';
    }
  };

  const getResultIcon = () => {
    switch (winner) {
      case 'attacker':
        return '⚔️';
      case 'defender':
        return '🛡️';
      case 'draw':
        return '🤝';
      default:
        return '✓';
    }
  };

  const isDefeated = (fighter: Fighter) => fighter.health <= 0;

  return (
    <div className="combat-result">
      <div className="combat-result__content">
        <div className="combat-result__icon">{getResultIcon()}</div>
        <h2 className="combat-result__title">{getResultMessage()}</h2>

        <div className="combat-result__fighters">
          <div
            className={`combat-result__fighter ${
              isDefeated(attacker) ? 'combat-result__fighter--defeated' : ''
            } ${winner === 'attacker' ? 'combat-result__fighter--winner' : ''}`}
          >
            <div className="combat-result__fighter-name">
              {attacker.name}
            </div>
            <div className="combat-result__fighter-health">
              <div className="combat-result__health-bar">
                <div
                  className="combat-result__health-fill"
                  style={{
                    width: `${Math.max(0, (attacker.health / attacker.maxHealth) * 100)}%`,
                  }}
                />
              </div>
              <div className="combat-result__health-text">
                {Math.max(0, attacker.health)}/{attacker.maxHealth}
              </div>
            </div>
            {isDefeated(attacker) && (
              <div className="combat-result__defeated">Побеждён</div>
            )}
          </div>

          <div className="combat-result__vs">VS</div>

          <div
            className={`combat-result__fighter ${
              isDefeated(defender) ? 'combat-result__fighter--defeated' : ''
            } ${winner === 'defender' ? 'combat-result__fighter--winner' : ''}`}
          >
            <div className="combat-result__fighter-name">
              {defender.name}
            </div>
            <div className="combat-result__fighter-health">
              <div className="combat-result__health-bar">
                <div
                  className="combat-result__health-fill"
                  style={{
                    width: `${Math.max(0, (defender.health / defender.maxHealth) * 100)}%`,
                  }}
                />
              </div>
              <div className="combat-result__health-text">
                {Math.max(0, defender.health)}/{defender.maxHealth}
              </div>
            </div>
            {isDefeated(defender) && (
              <div className="combat-result__defeated">Побеждён</div>
            )}
          </div>
        </div>

        <div className="combat-result__summary">
          <div className="combat-result__summary-item">
            <span>Урон атакующему:</span>
            <span className="combat-result__summary-value">
              {damageToAttacker > 0 ? `-${damageToAttacker}` : '0'}
            </span>
          </div>
          <div className="combat-result__summary-item">
            <span>Урон защищающемуся:</span>
            <span className="combat-result__summary-value">
              {damageToDefender > 0 ? `-${damageToDefender}` : '0'}
            </span>
          </div>
        </div>

        <div className="combat-result__actions">
          <Button variant="primary" onClick={onContinue}>
            Продолжить
          </Button>
        </div>
      </div>
    </div>
  );
};

export default CombatResult;