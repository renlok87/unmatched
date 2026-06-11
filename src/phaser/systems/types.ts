// ============================================================
// VICTORY CONDITIONS TYPES
// ============================================================

/**
 * Результат проверки условий победы
 */
export enum VictoryResult {
  NONE = 'none',
  VICTORY = 'victory',
  DEFEAT = 'defeat',
  DRAW = 'draw',
}

/**
 * Результат проверки условий победы/поражения
 */
export interface VictoryCheckResult {
  result: VictoryResult;
  winnerId: string | null;
  reason: string;
  defeatedFighters: string[];
}
