/**
 * UNMATCHED Design System - Token Component
 *
 * Компонент игрового токена
 */

import React from 'react';
import type { TokenProps } from '../types';

export const Token: React.FC<TokenProps & React.HTMLAttributes<HTMLDivElement>> = ({
  type = 'fighter',
  fighterType,
  value,
  active = false,
  children,
  className = '',
  ...props
}) => {
  const classes = [
    'token',
    type === 'fighter' && `token-fighter ${fighterType || ''}`,
    type === 'boost' && 'token-boost',
    type === 'damage' && 'token-damage',
    type === 'action' && 'token-action',
    active && 'active',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} {...props}>
      {children !== undefined ? children : value}
    </div>
  );
};

export default Token;
