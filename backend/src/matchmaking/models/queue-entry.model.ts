/**
 * Queue Entry Model
 *
 * Представляет игрока в очереди матчмейкинга.
 */

export interface QueueEntry {
  userId: string;
  rating: number;
  mode: string;
  heroPref?: string;
  joinedAt: Date;
}

export interface QueueEntryWithRank extends QueueEntry {
  rank: number;
}

export interface QueuePositionInfo {
  position: number;
  estimatedWaitTime: number; // в секундах
  totalPlayers: number;
}

/**
 * Expanding window параметры
 */
export interface ExpandingWindowConfig {
  // [seconds, +/- ELO]
  windows: readonly [number, number][];
}

export const DEFAULT_EXPANDING_WINDOW: ExpandingWindowConfig = {
  windows: [
    [30, 100], // 0-30 сек: +/-100 ELO
    [60, 200], // 30-60 сек: +/-200 ELO
    [120, 400], // 60-120 сек: +/-400 ELO
    [Infinity, Infinity], // 120+ сек: без ограничений
  ] as const,
};

/**
 * Получить диапазон ELO на основе времени ожидания
 */
export function getEloRange(
  waitTimeSeconds: number,
  config: ExpandingWindowConfig = DEFAULT_EXPANDING_WINDOW,
): [number, number] {
  for (const [seconds, delta] of config.windows) {
    if (waitTimeSeconds <= seconds) {
      return [-delta, delta];
    }
  }
  return [-Infinity, Infinity];
}
