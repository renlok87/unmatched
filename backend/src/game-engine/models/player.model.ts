/**
 * Player Model
 *
 * Типы для игроков в игре
 */

/**
 * Игрок в лобби
 */
export interface LobbyPlayer {
  readonly userId: string;
  readonly username: string;
  readonly avatar?: string;
  readonly heroId?: string;
  readonly isReady: boolean;
  readonly seatOrder: number;
}

/**
 * Статистика игрока
 */
export interface PlayerStats {
  readonly gamesPlayed: number;
  readonly gamesWon: number;
  readonly gamesLost: number;
  readonly winRate: number;
  readonly currentElo: number;
  readonly peakElo: number;
}
