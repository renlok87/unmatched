export enum AuditEventType {
  // Auth events
  USER_REGISTERED = 'USER_REGISTERED',
  USER_LOGIN = 'USER_LOGIN',
  USER_LOGOUT = 'USER_LOGOUT',
  LOGIN_FAILED = 'LOGIN_FAILED',
  PASSWORD_CHANGED = 'PASSWORD_CHANGED',
  PASSWORD_RESET_REQUESTED = 'PASSWORD_RESET_REQUESTED',

  // Game events
  GAME_CREATED = 'GAME_CREATED',
  GAME_JOINED = 'GAME_JOINED',
  GAME_STARTED = 'GAME_STARTED',
  GAME_ABORTED = 'GAME_ABORTED',
  GAME_COMPLETED = 'GAME_COMPLETED',
  PLAYER_KICKED = 'PLAYER_KICKED',

  // Admin events
  ADMIN_USER_BANNED = 'ADMIN_USER_BANNED',
  ADMIN_USER_UNBANNED = 'ADMIN_USER_UNBANNED',
  ADMIN_CONTENT_UPDATED = 'ADMIN_CONTENT_UPDATED',
  ADMIN_SETTINGS_CHANGED = 'ADMIN_SETTINGS_CHANGED',

  // Security events
  SUSPICIOUS_ACTIVITY = 'SUSPICIOUS_ACTIVITY',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  UNAUTHORIZED_ACCESS = 'UNAUTHORIZED_ACCESS',
  TOKEN_REVOKED = 'TOKEN_REVOKED',
}

export interface AuditEvent {
  id: string;
  type: AuditEventType;
  userId?: string;
  ipAddress?: string;
  userAgent?: string;
  metadata: Record<string, any>;
  timestamp: Date;
  success: boolean;
  errorMessage?: string;
}

export interface CreateAuditEventDto {
  type: AuditEventType;
  userId?: string;
  ipAddress?: string;
  userAgent?: string;
  metadata: Record<string, any>;
  success?: boolean;
  errorMessage?: string;
}

export interface SuspiciousActivity {
  userId?: string;
  ipAddress: string;
  eventCount: number;
  lastEventAt: Date;
  eventTypes: AuditEventType[];
}

export interface AuditFilter {
  userId?: string;
  startDate?: Date;
  endDate?: Date;
  eventType?: AuditEventType;
  success?: boolean;
  ipAddress?: string;
}
