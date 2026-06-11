export interface ReplayData {
  version: number;
  gameId: string;
  duration: number;
  turnCount: number;
  winnerId?: string;
  actions: ReplayAction[];
  metadata: ReplayMetadata;
}

export interface ReplayAction {
  sequenceNumber: number;
  type: string;
  playerId?: string;
  timestamp: number;
  data: Record<string, any>;
}

export interface ReplayMetadata {
  boardId: string;
  hostId: string;
  opponentId: string;
  hostHero?: string;
  opponentHero?: string;
  gameMode: string;
  startedAt: string;
  endedAt: string;
}

export interface ReplaySummary {
  id: string;
  gameId: string;
  duration: number;
  turnCount: number;
  winnerId?: string;
  createdAt: Date;
  isFavorite: boolean;
}
