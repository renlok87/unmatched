import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../database/prisma.service';
import { LeaderboardService } from './leaderboard.service';
import { AuditService } from '../../audit/audit.service';
import { AuditEventType } from '../models/audit.model';

@Injectable()
export class StatsAggregatorService {
  private readonly logger = new Logger(StatsAggregatorService.name);
  private readonly K_FACTOR = 32;

  constructor(
    private readonly prisma: PrismaService,
    private readonly leaderboard: LeaderboardService,
    private readonly audit: AuditService,
  ) {}

  async updateEloRatings(gameId: string, winnerId: string, loserId: string): Promise<void> {
    try {
      const [winnerStats, loserStats] = await Promise.all([
        this.getUserStats(winnerId),
        this.getUserStats(loserId),
      ]);

      const winnerElo = winnerStats?.currentElo || 1200;
      const loserElo = loserStats?.currentElo || 1200;

      const newWinnerElo = this.calculateNewElo(winnerElo, loserElo, true);
      const newLoserElo = this.calculateNewElo(loserElo, winnerElo, false);

      await this.prisma.$transaction([
        this.prisma.userStats.upsert({
          where: { userId: winnerId },
          update: {
            currentElo: newWinnerElo,
            gamesWon: { increment: 1 },
            gamesPlayed: { increment: 1 },
            peakElo: Math.max(winnerStats?.peakElo || 1200, newWinnerElo),
            winRate: {
              set: ((winnerStats?.gamesWon || 0) + 1) / ((winnerStats?.gamesPlayed || 0) + 1),
            },
            lastPlayedAt: new Date(),
          },
          create: {
            userId: winnerId,
            currentElo: newWinnerElo,
            peakElo: newWinnerElo,
            gamesWon: 1,
            gamesPlayed: 1,
            winRate: 1,
            lastPlayedAt: new Date(),
          },
        }),
        this.prisma.userStats.upsert({
          where: { userId: loserId },
          update: {
            currentElo: newLoserElo,
            gamesLost: { increment: 1 },
            gamesPlayed: { increment: 1 },
            lastPlayedAt: new Date(),
          },
          create: {
            userId: loserId,
            currentElo: newLoserElo,
            peakElo: newLoserElo,
            gamesLost: 1,
            gamesPlayed: 1,
            lastPlayedAt: new Date(),
          },
        }),
      ]);

      await Promise.all([
        this.leaderboard.updatePlayerStats({
          userId: winnerId,
          currentElo: newWinnerElo,
        }),
        this.leaderboard.updatePlayerStats({
          userId: loserId,
          currentElo: newLoserElo,
        }),
      ]);

      this.logger.log(
        `Updated ELO for game ${gameId}: ${winnerId} (${winnerElo} -> ${newWinnerElo}), ${loserId} (${loserElo} -> ${newLoserElo})`,
      );
    } catch (error) {
      this.logger.error(`Failed to update ELO ratings: ${error.message}`);
      throw error;
    }
  }

  async applyQueuePenalty(userId: string, penalty: number): Promise<void> {
    try {
      const stats = await this.getUserStats(userId);
      const currentElo = stats?.currentElo || 1200;
      const newElo = Math.max(0, currentElo + penalty);

      await this.prisma.userStats.upsert({
        where: { userId },
        update: {
          currentElo: newElo,
        },
        create: {
          userId,
          currentElo: newElo,
          peakElo: newElo,
        },
      });

      await this.leaderboard.updatePlayerStats({
        userId,
        currentElo: newElo,
      });

      await this.audit.logEvent({
        type: AuditEventType.SUSPICIOUS_ACTIVITY,
        userId,
        metadata: {
          penalty,
          reason: 'queue_decline',
          previousElo: currentElo,
          newElo,
        },
        success: true,
      });

      this.logger.log(`Applied queue penalty to ${userId}: ${currentElo} -> ${newElo}`);
    } catch (error) {
      this.logger.error(`Failed to apply queue penalty: ${error.message}`);
      throw error;
    }
  }

  async updateHeroStats(
    userId: string,
    heroId: string,
    won: boolean,
    playTime: number,
  ): Promise<void> {
    try {
      const stats = await this.getUserStats(userId);

      if (!stats) {
        this.logger.warn(`User stats not found for ${userId}, skipping hero stats update`);
        return;
      }

      const heroStats = stats.heroStats || {};
      const heroData = heroStats[heroId] || {
        gamesPlayed: 0,
        gamesWon: 0,
        gamesLost: 0,
        winRate: 0,
        totalPlayTime: 0,
      };

      heroData.gamesPlayed += 1;
      heroData.totalPlayTime += playTime;

      if (won) {
        heroData.gamesWon += 1;
      } else {
        heroData.gamesLost += 1;
      }

      heroData.winRate = heroData.gamesWon / heroData.gamesPlayed;

      heroStats[heroId] = heroData;

      await this.prisma.userStats.update({
        where: { userId },
        data: {
          heroStats: heroStats,
          totalPlayTime: { increment: playTime },
        },
      });

      this.logger.debug(`Updated hero stats for ${userId} with ${heroId}`);
    } catch (error) {
      this.logger.error(`Failed to update hero stats: ${error.message}`);
    }
  }

  async getPlayerStats(userId: string): Promise<any> {
    try {
      const stats = await this.getUserStats(userId);

      if (!stats) {
        return this.getDefaultStats(userId);
      }

      const rank = await this.leaderboard.getPlayerRank(userId);

      return {
        userId: stats.userId,
        currentElo: stats.currentElo,
        peakElo: stats.peakElo,
        gamesPlayed: stats.gamesPlayed,
        gamesWon: stats.gamesWon,
        gamesLost: stats.gamesLost,
        winRate: stats.winRate,
        totalPlayTime: stats.totalPlayTime,
        lastPlayedAt: stats.lastPlayedAt,
        rank: rank.rank,
        heroStats: stats.heroStats || {},
      };
    } catch (error) {
      this.logger.error(`Failed to get player stats: ${error.message}`);
      return this.getDefaultStats(userId);
    }
  }

  async getTopPlayers(limit: number = 10): Promise<any[]> {
    const leaderboardEntries = await this.leaderboard.getTopPlayers(limit);

    return Promise.all(
      leaderboardEntries.map(async (entry: any) => {
        const stats = await this.getUserStats(entry.userId);

        return {
          ...entry,
          peakElo: stats?.peakElo || entry.elo,
          totalPlayTime: stats?.totalPlayTime || 0,
        };
      }),
    );
  }

  async resetWeeklyStats(): Promise<number> {
    try {
      await this.leaderboard.resetWeeklyLeaderboard();

      this.logger.log(`Reset weekly leaderboard`);
      return 0;
    } catch (error) {
      this.logger.error(`Failed to reset weekly stats: ${error.message}`);
      return 0;
    }
  }

  private calculateNewElo(playerElo: number, opponentElo: number, won: boolean): number {
    const expectedScore = 1 / (1 + Math.pow(10, (opponentElo - playerElo) / 400));
    const actualScore = won ? 1 : 0;
    const newElo = Math.round(playerElo + this.K_FACTOR * (actualScore - expectedScore));

    return Math.max(0, newElo);
  }

  private async getUserStats(userId: string): Promise<any> {
    return this.prisma.userStats.findUnique({
      where: { userId },
    });
  }

  private getDefaultStats(userId: string): any {
    return {
      userId,
      currentElo: 1200,
      peakElo: 1200,
      gamesPlayed: 0,
      gamesWon: 0,
      gamesLost: 0,
      winRate: 0,
      totalPlayTime: 0,
      lastPlayedAt: null,
      rank: null,
      heroStats: {},
    };
  }
}
