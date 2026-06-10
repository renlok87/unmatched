/**
 * Penalty Model
 *
 * Система штрафов за отклонение матчей.
 */

export interface PenaltyRecord {
  userId: string;
  declineCount: number;
  lastDeclineAt: Date;
  tempBanUntil?: Date;
}

export interface PenaltyInfo {
  canJoinQueue: boolean;
  declineCount: number;
  tempBanUntil?: Date;
  penaltyElo?: number; // сколько ELO будет вычтено при следующем decline
}

export const PENALTY_CONFIG = {
  ELO_PENALTY: 25, // ELO штраф за decline
  DECLINES_FOR_BAN: 3, // количество decline для temp ban
  BAN_DURATION_MINUTES: 30, // длительность temp ban
  DECLINE_WINDOW_HOURS: 1, // окно для подсчёта decline
} as const;

export interface TempBanInfo {
  userId: string;
  bannedAt: Date;
  expiresAt: Date;
  reason: string;
}
