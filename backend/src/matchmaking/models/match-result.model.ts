/**
 * Match Result Model
 *
 * Результат поиска матча.
 */

export interface MatchResult {
  gameId: string;
  player1Id: string;
  player2Id: string;
  player1Rating: number;
  player2Rating: number;
  mode: string;
  matchedAt: Date;
}

export interface MatchCandidate {
  userId: string;
  rating: number;
  waitTime: number; // секунды
  heroPref?: string;
}
