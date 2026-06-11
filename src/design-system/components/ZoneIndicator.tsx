/**
 * UNMATCHED Design System - ZoneIndicator Component
 *
 * Компонент индикатора зоны игрового поля
 */

import React from 'react';
import type { ZoneProps } from '../types';

export const ZoneIndicator: React.FC<ZoneProps & React.HTMLAttributes<HTMLDivElement>> = ({
  type,
  showLabel = true,
  showDot = true,
  className = '',
  ...props
}) => {
  const zoneNames: Record<string, string> = {
    blue: 'BLUE',
    green: 'GREEN',
    yellow: 'YELLOW',
    red: 'RED',
    purple: 'PURPLE',
  };

  const classes = [
    'zone',
    `zone-${type}`,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} {...props}>
      {showDot && <div className={`zone-dot ${type}`} />}
      {showLabel && <span>{zoneNames[type]}</span>}
    </div>
  );
};

export const ZoneDot: React.FC<{ type: ZoneProps['type'] } & React.HTMLAttributes<HTMLDivElement>> = ({
  type,
  className = '',
  ...props
}) => {
  const classes = ['zone-dot', type, className].filter(Boolean).join(' ');

  return <div className={classes} {...props} />;
};

export default ZoneIndicator;
