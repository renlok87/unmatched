export enum PresenceStatus {
  OFFLINE = 'offline',
  ONLINE = 'online',
  INGAME = 'ingame',
  INQUEUE = 'inqueue',
}

export interface PresenceData {
  userId: string;
  status: PresenceStatus;
  currentGameId?: string;
  lastSeenAt: number;
}
