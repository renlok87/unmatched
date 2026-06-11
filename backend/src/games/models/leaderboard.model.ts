export interface LeaderboardEntry {
  rank: number;
  userId: string;
  username: string;
  avatarUrl?: string;
  elo: number;
  gamesWon: number;
  gamesPlayed: number;
  winRate: number;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  totalCount: number;
  page: number;
  pageSize: number;
}

export interface LeaderboardRank {
  rank: number;
  userId: string;
  elo: number;
  heroId?: string;
  timeFrame: string;
}

export interface LeaderboardOptions {
  heroId?: string;
  timeFrame?: 'all' | 'weekly' | 'monthly';
  page?: number;
  pageSize?: number;
}

export interface PlayerStatsUpdate {
  userId: string;
  currentElo: number;
  weeklyElo?: number;
  gamesWon?: number;
  gamesPlayed?: number;
}

export interface UserMetadata {
  username: string;
  avatarUrl?: string;
  gamesWon: number;
  gamesPlayed: number;
}
