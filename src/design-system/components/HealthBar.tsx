/**
 * UNMATCHED Design System - HealthBar Component
 *
 * Компонент индикатора здоровья для бойцов
 */

import React from 'react';
import type { HealthBarProps } from '../types';

export const HealthBar: React.FC<HealthBarProps> = ({
  value,
  max,
  size = 'md',
  showLabel = true,
  warningThreshold = 0.3,
}) => {
  const percentage = Math.max(0, Math.min(100, (value / max) * 100));
  const isLow = percentage <= warningThreshold * 100;

  const classes = [
    'health-bar',
    `health-bar-${size}`,
    isLow && 'low',
  ].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      <div
        className="health-bar-fill"
        style={{ width: `${percentage}%` }}
      />
      {showLabel && (
        <span className="health-bar-label">
          {value}/{max}
        </span>
      )}
    </div>
  );
};

export default HealthBar;
