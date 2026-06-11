/**
 * Результат валидации игрового действия
 */

/**
 * Статус валидации
 */
export enum ValidationStatus {
  VALID = 'VALID',
  INVALID = 'INVALID',
  PARTIAL = 'PARTIAL', // Частично валидно (нужен выбор игрока)
}

/**
 * Результат валидации
 */
export interface ValidationResult {
  valid: boolean;
  status: ValidationStatus;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  metadata?: Record<string, any>;
}

/**
 * Ошибка валидации
 */
export interface ValidationError {
  code: string;
  message: string;
  field?: string;
  value?: any;
}

/**
 * Предупреждение валидации
 */
export interface ValidationWarning {
  code: string;
  message: string;
  field?: string;
  value?: any;
}

/**
 * Коды ошибок валидации
 */
export enum ValidationErrorCode {
  // Общие ошибки
  INVALID_STATE = 'INVALID_STATE',
  INVALID_PHASE = 'INVALID_PHASE',
  NOT_YOUR_TURN = 'NOT_YOUR_TURN',
  PLAYER_NOT_FOUND = 'PLAYER_NOT_FOUND',
  FIGHTER_NOT_FOUND = 'FIGHTER_NOT_FOUND',

  // Очки действия
  INSUFFICIENT_ACTION_POINTS = 'INSUFFICIENT_ACTION_POINTS',
  NO_ACTION_POINTS = 'NO_ACTION_POINTS',

  // Карты
  CARD_NOT_IN_HAND = 'CARD_NOT_IN_HAND',
  CARD_ALREADY_PLAYED = 'CARD_ALREADY_PLAYED',
  INVALID_CARD_TYPE = 'INVALID_CARD_TYPE',
  CANNOT_PLAY_AS_ATTACK = 'CANNOT_PLAY_AS_ATTACK',
  CANNOT_PLAY_AS_DEFENSE = 'CANNOT_PLAY_AS_DEFENSE',

  // Перемещение
  INVALID_MOVE_TARGET = 'INVALID_MOVE_TARGET',
  MOVE_DISTANCE_EXCEEDED = 'MOVE_DISTANCE_EXCEEDED',
  PATH_BLOCKED = 'PATH_BLOCKED',
  TARGET_POSITION_OCCUPIED = 'TARGET_POSITION_OCCUPIED',

  // Атака
  NOT_ADJACENT = 'NOT_ADJACENT',
  INVALID_ATTACK_TARGET = 'INVALID_ATTACK_TARGET',
  ATTACKER_STUNNED = 'ATTACKER_STUNNED',
  TARGET_INVULNERABLE = 'TARGET_INVULNERABLE',

  // Защита
  ALREADY_DEFENDED = 'ALREADY_DEFENDED',
  DEFENSE_NOT_ALLOWED = 'DEFENSE_NOT_ALLOWED',

  // Размещение
  INVALID_PLACEMENT_ZONE = 'INVALID_PLACEMENT_ZONE',
  ZONE_FULL = 'ZONE_FULL',
  FIGHTER_ALREADY_PLACED = 'FIGHTER_ALREADY_PLACED',

  // Maneuver
  MANEUVER_ALREADY_EXECUTED = 'MANEUVER_ALREADY_EXECUTED',
  INVALID_MANEUVER_TARGET = 'INVALID_MANEUVER_TARGET',
}

/**
 * Создать валидный результат
 */
export function validResult(metadata?: Record<string, any>): ValidationResult {
  return {
    valid: true,
    status: ValidationStatus.VALID,
    errors: [],
    warnings: [],
    metadata,
  };
}

/**
 * Создать невалидный результат
 */
export function invalidResult(
  errors: ValidationError[],
  warnings: ValidationWarning[] = [],
): ValidationResult {
  return {
    valid: false,
    status: ValidationStatus.INVALID,
    errors,
    warnings,
  };
}

/**
 * Создать ошибку валидации
 */
export function createError(
  code: ValidationErrorCode,
  message: string,
  field?: string,
  value?: any,
): ValidationError {
  return { code, message, field, value };
}

/**
 * Создать предупреждение валидации
 */
export function createWarning(
  code: string,
  message: string,
  field?: string,
  value?: any,
): ValidationWarning {
  return { code, message, field, value };
}

/**
 * Объединить результаты валидации
 */
export function mergeResults(...results: ValidationResult[]): ValidationResult {
  const allErrors = results.flatMap((r) => r.errors);
  const allWarnings = results.flatMap((r) => r.warnings);

  return {
    valid: allErrors.length === 0,
    status: allErrors.length === 0 ? ValidationStatus.VALID : ValidationStatus.INVALID,
    errors: allErrors,
    warnings: allWarnings,
  };
}
