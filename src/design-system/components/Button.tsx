/**
 * UNMATCHED Design System - Button Component
 *
 * Универсальный компонент кнопки с вариантами стилей
 */

import React from 'react';
import type { ButtonProps } from '../types';

export const Button: React.FC<ButtonProps & React.ButtonHTMLAttributes<HTMLButtonElement>> = ({
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  icon = false,
  active = false,
  children,
  className = '',
  ...props
}) => {
  const classes = [
    'btn',
    `btn-${variant}`,
    size && `btn-${size}`,
    icon && 'btn-icon',
    active && 'btn-active',
    loading && 'loading',
    disabled && 'disabled',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      className={classes}
      disabled={disabled || loading}
      {...props}
    >
      {children}
    </button>
  );
};

export default Button;
