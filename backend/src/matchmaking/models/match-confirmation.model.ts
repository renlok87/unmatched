/**
 * Match Confirmation Model
 *
 * Двухфазное подтверждение матча.
 */

export enum ConfirmationStatus {
  PENDING = 'PENDING',
  ACCEPTED = 'ACCEPTED',
  DECLINED = 'DECLINED',
  TIMEOUT = 'TIMEOUT',
  COMPLETED = 'COMPLETED',
}

export interface MatchConfirmation {
  gameId: string;
  player1Id: string;
  player2Id: string;
  player1Status: ConfirmationStatus;
  player2Status: ConfirmationStatus;
  expiresAt: Date;
  createdAt: Date;
}

export interface ConfirmationResult {
  success: boolean;
  bothAccepted: boolean;
  status: ConfirmationStatus;
  timeoutUserId?: string; // игрок, который не принял
}

export const CONFIRMATION_TTL_SECONDS = 35;
export const CONFIRMATION_TIMEOUT_SECONDS = 30;
