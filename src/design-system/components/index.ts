/**
 * UNMATCHED Design System - Components Index
 *
 * Главный файл экспорта компонентов дизайн-системы
 */

export { Button } from './Button';
export { Badge } from './Badge';
export { HealthBar } from './HealthBar';
export { Token } from './Token';
export { ZoneIndicator, ZoneDot } from './ZoneIndicator';
export { Avatar } from './Avatar';
export { Modal, ModalWithFooter } from './Modal';
export {
  Toast,
  ToastProvider,
  useToast,
  toast
} from './Toast';
export { Input } from './Input';

// Re-export types
export type {
  CardType,
  CardSize,
  CardState,
  CardStyleProps,
  ColorName,
  ZoneColor,
  GradientName,
  FontSize,
  FontWeight,
  LineHeight,
  LetterSpacing,
  TextStyleProps,
  SpacingValue,
  SpacingProps,
  BorderRadius,
  Shadow,
  ButtonProps,
  ButtonVariant,
  ButtonSize,
  BadgeProps,
  BadgeVariant,
  BadgeSize,
  TokenProps,
  TokenType,
  FighterType,
  ZoneProps,
  HealthBarProps,
  HealthBarSize,
  AvatarProps,
  ModalProps,
  ModalSize,
  ToastProps,
  ToastVariant,
  ToastPosition,
  ToastOptions,
  InputProps,
  InputSize,
  AnimationType,
  AnimationProps,
  GamePhase,
  ActionType,
  GameStatus,
  ThemeTokens,
  ThemeContextValue,
  DesignSystemProviderProps,
} from '../types';
