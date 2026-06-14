/**
 * UNMATCHED Design System - DesignSystemProvider
 *
 * Провайдер дизайн-системы для управления темой и токенами
 */

import React, { createContext, useContext, useMemo, useEffect } from 'react';
import type { ThemeTokens, ThemeContextValue, DesignSystemProviderProps } from './types';

const defaultTheme: ThemeTokens = {
  colors: {
    primary: '#dc2626',
    secondary: '#2563eb',
    accent: '#a855f7',
    success: '#22c55e',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6',
    white: '#ffffff',
    black: '#000000',
    'gray-50': '#f9fafb',
    'gray-100': '#f3f4f6',
    'gray-200': '#e5e7eb',
    'gray-300': '#d1d5db',
    'gray-400': '#9ca3af',
    'gray-500': '#6b7280',
    'gray-600': '#4b5563',
    'gray-700': '#374151',
    'gray-800': '#1f2937',
    'gray-900': '#111827',
  },
  zoneColors: {
    blue: '#3b82f6',
    green: '#22c55e',
    yellow: '#eab308',
    red: '#ef4444',
    purple: '#a855f7',
    brown: '#92400e',
    gray: '#6b7280',
    orange: '#f97316',
    pink: '#ec4899',
    white: '#e5e7eb',
    gold: '#d4af37',
    beige: '#d6c8a8',
  },
  gradients: {
    dark: 'linear-gradient(135deg, #1f2937 0%, #111827 100%)',
    darker: 'linear-gradient(135deg, #374151 0%, #1f2937 100%)',
    'card-attack': 'linear-gradient(135deg, #7f1d1d 0%, #450a0a 100%)',
    'card-defense': 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)',
    'card-versatile': 'linear-gradient(135deg, #581c87 0%, #6b21a8 100%)',
    'card-scheme': 'linear-gradient(135deg, #713f12 0%, #78350f 100%)',
  },
  fontSizes: {
    xs: '0.75rem',
    sm: '0.875rem',
    md: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
    '2xl': '1.5rem',
    '3xl': '1.875rem',
    '4xl': '2.25rem',
    '5xl': '3rem',
  },
  fontWeights: {
    light: 300,
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
  },
  lineHeights: {
    tight: 1.25,
    snug: 1.375,
    normal: 1.5,
    relaxed: 1.625,
    loose: 2,
  },
  letterSpacings: {
    tight: '-0.025em',
    normal: '0',
    wide: '0.025em',
    wider: '0.05em',
    widest: '0.1em',
  },
  spacing: {
    0: '0',
    1: '0.25rem',
    2: '0.5rem',
    3: '0.75rem',
    4: '1rem',
    5: '1.25rem',
    6: '1.5rem',
    8: '2rem',
    10: '2.5rem',
    12: '3rem',
    16: '4rem',
    20: '5rem',
    24: '6rem',
  },
  borderRadius: {
    none: '0',
    sm: '0.125rem',
    md: '0.375rem',
    lg: '0.5rem',
    xl: '0.75rem',
    '2xl': '1rem',
    '3xl': '1.5rem',
    full: '9999px',
  },
  shadows: {
    none: 'none',
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)',
    attack: '0 8px 20px rgba(220, 38, 38, 0.4)',
    defense: '0 8px 20px rgba(37, 99, 235, 0.4)',
    versatile: '0 8px 20px rgba(168, 85, 247, 0.4)',
    scheme: '0 8px 20px rgba(202, 138, 4, 0.4)',
    glow: '0 0 20px rgba(251, 191, 36, 0.5)',
  },
  transitions: {
    fast: '150ms ease-in-out',
    base: '200ms ease-in-out',
    slow: '300ms ease-in-out',
    slower: '500ms ease-in-out',
  },
};

const DesignSystemContext = createContext<ThemeContextValue | undefined>(undefined);

export const useDesignSystem = (): ThemeContextValue => {
  const context = useContext(DesignSystemContext);
  if (!context) {
    throw new Error('useDesignSystem must be used within DesignSystemProvider');
  }
  return context;
};

export const DesignSystemProvider: React.FC<DesignSystemProviderProps> = ({
  children,
  theme: customTheme,
  defaultColorMode = 'dark',
}) => {
  const [isDark, setIsDark] = React.useState(defaultColorMode === 'dark');

  // Apply CSS custom properties to document
  useEffect(() => {
    const root = document.documentElement;

    // Apply color mode
    if (isDark) {
      root.setAttribute('data-color-mode', 'dark');
    } else {
      root.setAttribute('data-color-mode', 'light');
    }
  }, [isDark]);

  // Merge custom theme with default
  const theme = useMemo(() => {
    if (!customTheme) return defaultTheme;

    return {
      colors: { ...defaultTheme.colors, ...customTheme.colors },
      zoneColors: { ...defaultTheme.zoneColors, ...customTheme.zoneColors },
      gradients: { ...defaultTheme.gradients, ...customTheme.gradients },
      fontSizes: { ...defaultTheme.fontSizes, ...customTheme.fontSizes },
      fontWeights: { ...defaultTheme.fontWeights, ...customTheme.fontWeights },
      lineHeights: { ...defaultTheme.lineHeights, ...customTheme.lineHeights },
      letterSpacings: { ...defaultTheme.letterSpacings, ...customTheme.letterSpacings },
      spacing: { ...defaultTheme.spacing, ...customTheme.spacing },
      borderRadius: { ...defaultTheme.borderRadius, ...customTheme.borderRadius },
      shadows: { ...defaultTheme.shadows, ...customTheme.shadows },
      transitions: { ...defaultTheme.transitions, ...customTheme.transitions },
    };
  }, [customTheme]);

  const toggleTheme = () => setIsDark((prev) => !prev);

  const contextValue: ThemeContextValue = useMemo(
    () => ({
      theme,
      toggleTheme,
      isDark,
    }),
    [theme, isDark]
  );

  return (
    <DesignSystemContext.Provider value={contextValue}>
      {children}
    </DesignSystemContext.Provider>
  );
};

export default DesignSystemProvider;
