/**
 * UNMATCHED Design System - Badge Component
 *
 * Компонент бейджа для отображения статусов и меток
 */

import React from 'react';
import type { BadgeProps } from '../types';

export const Badge: React.FC<BadgeProps & React.HTMLAttributes<HTMLSpanElement>> = ({
  variant = 'primary',
  size = 'md',
  dot = false,
  pill = false,
  children,
  className = '',
  ...props
}) => {
  const classes = [
    'badge',
    `badge-${variant}`,
    `badge-${size}`,
    dot && 'badge-dot',
    pill && 'badge-pill',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes} {...props}>
      {children}
    </span>
  );
};

export default Badge;
