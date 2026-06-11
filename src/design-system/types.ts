/**
 * UNMATCHED Design System - TypeScript Types
 *
 * Полная система типов для дизайн-системы
 */

// ============================================================
// CARD TYPES - Типы карт
// ============================================================

export type CardType = 'attack' | 'defense' | 'versatile' | 'scheme';

export type CardSize = 'small' | 'medium' | 'large';

export type CardState = 'idle' | 'playable' | 'selected' | 'disabled' | 'boosted' | 'preview';

export interface CardStyleProps {
  type?: CardType;
  size?: CardSize;
  state?: CardState;
  isFaceDown?: boolean;
  showValue?: boolean;
}

// ============================================================
// COLOR TYPES - Типы цветов
// ============================================================

export type ColorName =
  | 'primary'
  | 'secondary'
  | 'accent'
  | 'success'
  | 'warning'
  | 'error'
  | 'info'
  | 'white'
  | 'black'
  | 'gray-50'
  | 'gray-100'
  | 'gray-200'
  | 'gray-300'
  | 'gray-400'
  | 'gray-500'
  | 'gray-600'
  | 'gray-700'
  | 'gray-800'
  | 'gray-900';

export type ZoneColor = 'blue' | 'green' | 'yellow' | 'red' | 'purple';

export type GradientName =
  | 'dark'
  | 'darker'
  | 'card-attack'
  | 'card-defense'
  | 'card-versatile'
  | 'card-scheme';

// ============================================================
// TYPOGRAPHY TYPES - Типы типографики
// ============================================================

export type FontSize =
  | 'xs'
  | 'sm'
  | 'md'
  | 'lg'
  | 'xl'
  | '2xl'
  | '3xl'
  | '4xl'
  | '5xl';

export type FontWeight =
  | 'light'
  | 'normal'
  | 'medium'
  | 'semibold'
  | 'bold'
  | 'extrabold';

export type LineHeight =
  | 'tight'
  | 'snug'
  | 'normal'
  | 'relaxed'
  | 'loose';

export type LetterSpacing =
  | 'tight'
  | 'normal'
  | 'wide'
  | 'wider'
  | 'widest';

export interface TextStyleProps {
  size?: FontSize;
  weight?: FontWeight;
  lineHeight?: LineHeight;
  letterSpacing?: LetterSpacing;
  align?: 'left' | 'center' | 'right';
  transform?: 'uppercase' | 'lowercase' | 'capitalize';
  color?: ColorName;
}

// ============================================================
// SPACING TYPES - Типы отступов
// ============================================================

export type SpacingValue =
  | 0
  | 1
  | 2
  | 3
  | 4
  | 5
  | 6
  | 8
  | 10
  | 12
  | 16
  | 20
  | 24;

export type SpacingProps = {
  m?: SpacingValue;
  mx?: SpacingValue;
  my?: SpacingValue;
  mt?: SpacingValue;
  mb?: SpacingValue;
  ml?: SpacingValue;
  mr?: SpacingValue;
  p?: SpacingValue;
  px?: SpacingValue;
  py?: SpacingValue;
  pt?: SpacingValue;
  pb?: SpacingValue;
  pl?: SpacingValue;
  pr?: SpacingValue;
};

// ============================================================
// BORDER RADIUS TYPES - Типы скругления
// ============================================================

export type BorderRadius =
  | 'none'
  | 'sm'
  | 'md'
  | 'lg'
  | 'xl'
  | '2xl'
  | '3xl'
  | 'full';

// ============================================================
// SHADOW TYPES - Типы теней
// ============================================================

export type Shadow =
  | 'none'
  | 'sm'
  | 'md'
  | 'lg'
  | 'xl'
  | '2xl'
  | 'inner'
  | 'attack'
  | 'defense'
  | 'versatile'
  | 'scheme'
  | 'glow';

// ============================================================
// BUTTON TYPES - Типы кнопок
// ============================================================

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'success' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  icon?: boolean;
  active?: boolean;
}

// ============================================================
// BADGE TYPES - Типы бейджей
// ============================================================

export type BadgeVariant = 'primary' | 'secondary' | 'accent' | 'success' | 'warning' | 'error' | 'ghost';
export type BadgeSize = 'sm' | 'md' | 'lg';

export interface BadgeProps {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  pill?: boolean;
}

// ============================================================
// TOKEN TYPES - Типы токенов
// ============================================================

export type TokenType = 'fighter' | 'boost' | 'damage' | 'action';
export type FighterType = 'hero' | 'sidekick';

export interface TokenProps {
  type?: TokenType;
  fighterType?: FighterType;
  value?: number;
  active?: boolean;
}

// ============================================================
// ZONE TYPES - Типы зон
// ============================================================

export type ZoneType = 'blue' | 'green' | 'yellow' | 'red' | 'purple';

export interface ZoneProps {
  type: ZoneType;
  showLabel?: boolean;
  showDot?: boolean;
}

// ============================================================
// HEALTH BAR TYPES - Типы индикатора здоровья
// ============================================================

export type HealthBarSize = 'sm' | 'md' | 'lg';

export interface HealthBarProps {
  value: number;
  max: number;
  size?: HealthBarSize;
  showLabel?: boolean;
  warningThreshold?: number;
}

// ============================================================
// AVATAR TYPES - Типы аватаров
// ============================================================

export type AvatarSize = 'sm' | 'md' | 'lg' | 'xl';
export type AvatarVariant = 'hero' | 'villain' | 'default';

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string;
  alt?: string;
  size?: AvatarSize;
  variant?: AvatarVariant;
  fallback?: string;
}

// ============================================================
// MODAL TYPES - Типы модальных окон
// ============================================================

export type ModalSize = 'sm' | 'md' | 'lg' | 'full';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: ModalSize;
  closable?: boolean;
  children?: React.ReactNode;
}

// ============================================================
// TOOLTIP TYPES - Типы всплывающих подсказок
// ============================================================

export type TooltipPlacement = 'top' | 'bottom' | 'left' | 'right';

export interface TooltipProps {
  content: string;
  placement?: TooltipPlacement;
  delay?: number;
}

// ============================================================
// TOAST TYPES - Типы уведомлений
// ============================================================

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';
export type ToastPosition = 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top' | 'bottom';

export interface ToastProps {
  variant?: ToastVariant;
  title?: string;
  message: string;
  duration?: number;
  closable?: boolean;
}

export interface ToastOptions {
  id?: string;
  variant?: ToastVariant;
  title?: string;
  message: string;
  duration?: number;
  closable?: boolean;
}

// ============================================================
// INPUT TYPES - Типы полей ввода
// ============================================================

export type InputSize = 'sm' | 'md' | 'lg';

export interface InputProps {
  type?: 'text' | 'email' | 'password' | 'number';
  size?: InputSize;
  disabled?: boolean;
  error?: string;
  placeholder?: string;
  label?: string;
}

// ============================================================
// ANIMATION TYPES - Типы анимации
// ============================================================

export type AnimationType =
  | 'fade-in'
  | 'fade-out'
  | 'slide-up'
  | 'slide-down'
  | 'slide-left'
  | 'slide-right'
  | 'scale-in'
  | 'scale-out'
  | 'bounce'
  | 'pulse'
  | 'spin'
  | 'shake';

export interface AnimationProps {
  type?: AnimationType;
  duration?: number;
  delay?: number;
  infinite?: boolean;
}

// ============================================================
// GAME SPECIFIC TYPES - Специфичные для игры типы
// ============================================================

export type GamePhase =
  | 'setup'
  | 'start_of_turn'
  | 'action_selection'
  | 'card_play'
  | 'movement'
  | 'combat'
  | 'combat_defense'
  | 'resolution'
  | 'end_of_turn'
  | 'game_over';

export type ActionType = 'maneuver' | 'scheme' | 'attack';

export type GameStatus = 'waiting' | 'in_progress' | 'paused' | 'finished';

export interface GameStateIndicatorProps {
  phase: GamePhase;
  currentTurn: number;
  currentPlayer: string;
}

// ============================================================
// THEME CONTEXT TYPES - Типы для темы
// ============================================================

export interface ThemeTokens {
  // Colors
  colors: Record<ColorName, string>;
  zoneColors: Record<ZoneColor, string>;
  gradients: Record<GradientName, string>;

  // Typography
  fontSizes: Record<FontSize, string>;
  fontWeights: Record<FontWeight, number>;
  lineHeights: Record<LineHeight, number>;
  letterSpacings: Record<LetterSpacing, string>;

  // Spacing
  spacing: Record<SpacingValue, string>;

  // Border Radius
  borderRadius: Record<BorderRadius, string>;

  // Shadows
  shadows: Record<Shadow, string>;

  // Transitions
  transitions: {
    fast: string;
    base: string;
    slow: string;
    slower: string;
  };
}

export interface ThemeContextValue {
  theme: ThemeTokens;
  toggleTheme?: () => void;
  isDark?: boolean;
}

// ============================================================
// DESIGN SYSTEM PROVIDER TYPES - Типы провайдера
// ============================================================

export interface DesignSystemProviderProps {
  children: React.ReactNode;
  theme?: Partial<ThemeTokens>;
  defaultColorMode?: 'light' | 'dark';
}

// ============================================================
// UTILITY TYPE HELPERS - Вспомогательные типы
// ============================================================

export type PolymorphicComponentProps<T, P = {}> = P & {
  as?: React.ElementType;
} & Omit<React.ComponentPropsWithoutRef<T extends keyof JSX.IntrinsicElements ? T : 'div'>, keyof P>;

export type WithChildren<T = {}> = T & { children?: React.ReactNode };

export type MakeOptional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export type MakeRequired<T, K extends keyof T> = Omit<T, K> & Required<Pick<T, K>>;

// ============================================================
// COMPONENT VARIANT PROP HELPERS - Хелперы для вариантов компонентов
// ============================================================

export type VariantProps<T extends Record<string, any>> = T[keyof T];

export type SizeProps = 'sm' | 'md' | 'lg';

// ============================================================
// CSS VARIABLES TYPE - Типы CSS переменных
// ============================================================

export type CSSVariableValue = string | number;

export interface CSSVariables {
  // Colors
  '--color-primary'?: CSSVariableValue;
  '--color-secondary'?: CSSVariableValue;
  '--color-accent'?: CSSVariableValue;
  '--color-success'?: CSSVariableValue;
  '--color-warning'?: CSSVariableValue;
  '--color-error'?: CSSVariableValue;
  '--color-info'?: CSSVariableValue;
  '--color-white'?: CSSVariableValue;
  '--color-black'?: CSSVariableValue;

  // Spacing
  '--spacing-1'?: CSSVariableValue;
  '--spacing-2'?: CSSVariableValue;
  '--spacing-3'?: CSSVariableValue;
  '--spacing-4'?: CSSVariableValue;
  '--spacing-5'?: CSSVariableValue;
  '--spacing-6'?: CSSVariableValue;

  // Typography
  '--font-size-xs'?: CSSVariableValue;
  '--font-size-sm'?: CSSVariableValue;
  '--font-size-md'?: CSSVariableValue;
  '--font-size-lg'?: CSSVariableValue;
  '--font-size-xl'?: CSSVariableValue;
  '--font-size-2xl'?: CSSVariableValue;

  // Border Radius
  '--radius-sm'?: CSSVariableValue;
  '--radius-md'?: CSSVariableValue;
  '--radius-lg'?: CSSVariableValue;
  '--radius-xl'?: CSSVariableValue;
  '--radius-full'?: CSSVariableValue;

  // Transitions
  '--transition-fast'?: CSSVariableValue;
  '--transition-base'?: CSSVariableValue;
  '--transition-slow'?: CSSVariableValue;
}
