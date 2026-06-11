import React, { useEffect, useState } from 'react';
import { Button } from '@/design-system/components/Button';
import { AttackerView } from './AttackerView';
import { DefenderView } from './DefenderView';
import { CombatTimer } from './CombatTimer';
import { type ValueModifier } from './DamageIndicator';
import './CombatPanel.css';

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

export interface CombatState {
  attackerId: string;
  defenderId: string;
  attacker: Fighter;
  defender: Fighter;
  attackCard: Card;
  defenseCard: Card | null;
  attackValue: number;
  defenseValue: number;
  attackModifiers: ValueModifier[];
  defenseModifiers: ValueModifier[];
  startedAt: number;
  timeRemaining: number;
  status: 'pending' | 'in_progress' | 'resolving' | 'complete';
}

interface CombatPanelProps {
  combat: CombatState;
  isAttacker: boolean;
  isDefender: boolean;
  onResolveCombat: () => void;
}

export const CombatPanel: React.FC<CombatPanelProps> = ({
  combat,
  isAttacker,
  isDefender,
  onResolveCombat,
}) => {
  const [timeLeft, setTimeLeft] = useState(combat.timeRemaining);

  useEffect(() => {
    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 0) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [combat]);

  const handleResolve = () => {
    onResolveCombat();
  };

  return (
    <div className="combat-panel">
      <div className="combat-panel__header">
        <h2 className="combat-panel__title">Бой</h2>
        <CombatTimer timeRemaining={timeLeft} totalTime={30} />
      </div>

      <div className="combat-panel__arena">
        <AttackerView
          fighter={combat.attacker}
          attackCard={combat.attackCard}
          attackValue={combat.attackValue}
          modifiers={combat.attackModifiers}
        />

        <div className="combat-panel__vs">
          <div className="combat-panel__vs-text">VS</div>
          <div className="combat-panel__scores">
            <div className="combat-panel__score combat-panel__score--attack">
              {combat.attackValue}
            </div>
            <div className="combat-panel__score combat-panel__score--defense">
              {combat.defenseValue || 0}
            </div>
          </div>
        </div>

        <DefenderView
          fighter={combat.defender}
          defenseCard={combat.defenseCard}
          defenseValue={combat.defenseValue}
          modifiers={combat.defenseModifiers}
          isHidden={!isDefender && combat.status === 'pending'}
        />
      </div>

      <div className="combat-panel__footer">
        {isAttacker && combat.status === 'pending' && (
          <Button variant="primary" onClick={handleResolve}>
            Разрешить бой
          </Button>
        )}
        {isDefender && combat.status === 'pending' && (
          <div className="combat-panel__instruction">
            Выберите карту защиты
          </div>
        )}
        {combat.status === 'resolving' && (
          <div className="combat-panel__status">
            Расчёт урона...
          </div>
        )}
        {combat.status === 'complete' && (
          <div className="combat-panel__status">
            Бой завершён
          </div>
        )}
      </div>
    </div>
  );
};

export default CombatPanel;