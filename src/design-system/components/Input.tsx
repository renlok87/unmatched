/**
 * UNMATCHED Design System - Input Component
 *
 * Компонент поля ввода
 */

import React from 'react';
import type { InputProps } from '../types';

export const Input: React.FC<InputProps & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'>> = ({
  type = 'text',
  size = 'md',
  disabled = false,
  error,
  placeholder,
  label,
  className = '',
  ...props
}) => {
  const inputClasses = [
    'input',
    `input-${size}`,
    error && 'input-error',
    disabled && 'disabled',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="input-group">
      {label && (
        <label className="input-label">
          {label}
        </label>
      )}
      <input
        type={type}
        className={inputClasses}
        disabled={disabled}
        placeholder={placeholder}
        aria-invalid={!!error}
        {...props}
      />
      {error && (
        <span className="input-error">
          {error}
        </span>
      )}
    </div>
  );
};

export default Input;
