/**
 * Queue Status Model
 */

export interface QueueStatus {
  mode: string;
  totalPlayers: number;
  estimatedWaitTime: number;
}

export interface UserQueueStatus extends QueueStatus {
  inQueue: boolean;
  position?: number;
  joinedAt?: Date;
}

export enum QueueErrorCode {
  NOT_IN_QUEUE = 'NOT_IN_QUEUE',
  ALREADY_IN_QUEUE = 'ALREADY_IN_QUEUE',
  TEMP_BANNED = 'TEMP_BANNED',
  QUEUE_UNAVAILABLE = 'QUEUE_UNAVAILABLE',
  INVALID_MODE = 'INVALID_MODE',
}
