import { Injectable, Logger } from '@nestjs/common';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';
import {
  LeaderboardEntry,
  LeaderboardResponse,
  LeaderboardRank,
  LeaderboardOptions,
  PlayerStatsUpdate,
  UserMetadata,
} from '../models/leaderboard.model';

@Injectable()
export class LeaderboardService {
  private readonly logger = new Logger(LeaderboardService.name);
  private readonly METADATA_TTL = 3600; // 1 hour

  constructor(
    private readonly redis: RedisService,
    private readonly prisma: PrismaService,
  ) {}

  async getLeaderboard(options: LeaderboardOptions = {}): Promise<LeaderboardResponse> {
    const { heroId, timeFrame = 'all', page = 0, pageSize = 50 } = options;

    const key = this.getLeaderboardKey(heroId, timeFrame);
    const start = page * pageSize;
    const end = start + pageSize - 1;

    try {
      const entries = await this.redis.zrevrange(key, start, end, true);

      const totalCount = await this.redis.zcard(key);
      const leaderboardEntries: LeaderboardEntry[] = [];

      for (let i = 0; i < entries.length; i += 2) {
        const userId = entries[i];
        const elo = parseInt(entries[i + 1], 10);
        const rank = start + i / 2 + 1;

        try {
          const metadata = await this.getUserMetadata(userId);
          leaderboardEntries.push({
            rank,
            userId,
            username: metadata.username,
            avatarUrl: metadata.avatarUrl,
            elo,
            gamesWon: metadata.gamesWon,
            gamesPlayed: metadata.gamesPlayed,
            winRate:
              metadata.gamesPlayed > 0 ? (metadata.gamesWon / metadata.gamesPlayed) * 100 : 0,
          });
        } catch (error) {
          this.logger.warn(`Failed to get metadata for user ${userId}`);
          leaderboardEntries.push({
            rank,
            userId,
            username: 'Unknown',
            elo,
            gamesWon: 0,
            gamesPlayed: 0,
            winRate: 0,
          });
        }
      }

      return {
        entries: leaderboardEntries,
        totalCount,
        page,
        pageSize,
      };
    } catch (error) {
      this.logger.error(`Redis error, falling back to PostgreSQL: ${error.message}`);
      return this.getLeaderboardFromPostgres(options);
    }
  }

  async getPlayerRank(
    userId: string,
    heroId?: string,
    timeFrame: 'all' | 'weekly' | 'monthly' = 'all',
  ): Promise<LeaderboardRank> {
    const key = this.getLeaderboardKey(heroId, timeFrame);

    try {
      const score = await this.redis.zscore(key, userId);

      if (score === null) {
        throw new Error('User not found in leaderboard');
      }

      const rank = await this.redis.zrevrank(key, userId);

      if (rank === null) {
        throw new Error('Failed to get rank');
      }

      return {
        rank: rank + 1,
        userId,
        elo: Math.floor(score),
        heroId,
        timeFrame: timeFrame as 'all' | 'weekly' | 'monthly',
      };
    } catch (error) {
      this.logger.error(`Redis error, falling back to PostgreSQL: ${error.message}`);
      return this.getPlayerRankFromPostgres(
        userId,
        heroId,
        timeFrame as 'all' | 'weekly' | 'monthly',
      );
    }
  }

  async updatePlayerStats(update: PlayerStatsUpdate): Promise<void> {
    const { userId, currentElo, weeklyElo, gamesWon, gamesPlayed } = update;

    try {
      const multi = this.redis.multi();
      if (!multi) {
        this.logger.warn('Redis not connected, skipping leaderboard update');
        return;
      }

      multi.zadd('leaderboard:overall', currentElo.toString(), userId);

      if (weeklyElo !== undefined) {
        multi.zadd('leaderboard:weekly', weeklyElo.toString(), userId);
      }

      await multi.exec();

      const metadata = await this.getUserMetadataFromPostgres(userId);
      await this.cacheUserMetadata(userId, {
        ...metadata,
        gamesWon: gamesWon ?? metadata.gamesWon,
        gamesPlayed: gamesPlayed ?? metadata.gamesPlayed,
      });

      this.logger.debug(`Updated leaderboard stats for user ${userId}`);
    } catch (error) {
      this.logger.error(`Failed to update leaderboard stats: ${error.message}`);
    }
  }

  async removePlayer(userId: string): Promise<void> {
    try {
      const multi = this.redis.multi();
      if (!multi) {
        this.logger.warn('Redis not connected, skipping leaderboard removal');
        return;
      }

      multi.zrem('leaderboard:overall', userId);
      multi.zrem('leaderboard:weekly', userId);
      multi.del(`leaderboard:meta:${userId}`);

      await multi.exec();

      this.logger.debug(`Removed user ${userId} from leaderboards`);
    } catch (error) {
      this.logger.error(`Failed to remove user from leaderboard: ${error.message}`);
    }
  }

  async resetWeeklyLeaderboard(): Promise<number> {
    try {
      const count = await this.redis.del('leaderboard:weekly');
      this.logger.log(`Reset weekly leaderboard, removed ${count} entries`);
      return count;
    } catch (error) {
      this.logger.error(`Failed to reset weekly leaderboard: ${error.message}`);
      return 0;
    }
  }

  async getTopPlayers(limit: number = 10, timeFrame: 'all' | 'weekly' | 'monthly' = 'all'): Promise<LeaderboardEntry[]> {
    const result = await this.getLeaderboard({
      timeFrame,
      page: 0,
      pageSize: limit,
    });

    return result.entries;
  }

  private getLeaderboardKey(heroId?: string, timeFrame: string = 'all'): string {
    if (heroId) {
      return `leaderboard:hero:${heroId}:${timeFrame}`;
    }
    return `leaderboard:${timeFrame}`;
  }

  private async getUserMetadata(userId: string): Promise<UserMetadata> {
    const cacheKey = `leaderboard:meta:${userId}`;

    try {
      const cached = await this.redis.hgetall(cacheKey);

      if (Object.keys(cached).length > 0) {
        return {
          username: cached.username,
          avatarUrl: cached.avatarUrl as string | undefined,
          gamesWon: parseInt(cached.gamesWon, 10),
          gamesPlayed: parseInt(cached.gamesPlayed, 10),
        };
      }
    } catch (error) {
      this.logger.debug(`Cache miss for user ${userId}`);
    }

    const metadata = await this.getUserMetadataFromPostgres(userId);
    await this.cacheUserMetadata(userId, metadata);

    return metadata;
  }

  private async cacheUserMetadata(userId: string, metadata: UserMetadata): Promise<void> {
    const cacheKey = `leaderboard:meta:${userId}`;

    try {
      const multi = this.redis.multi();
      if (!multi) {
        this.logger.warn('Redis not connected, skipping metadata cache');
        return;
      }

      multi.hset(cacheKey, {
        username: metadata.username,
        avatarUrl: metadata.avatarUrl || '',
        gamesWon: metadata.gamesWon.toString(),
        gamesPlayed: metadata.gamesPlayed.toString(),
      });
      multi.expire(cacheKey, this.METADATA_TTL);
      await multi.exec();
    } catch (error) {
      this.logger.warn(`Failed to cache metadata for user ${userId}`);
    }
  }

  private async getUserMetadataFromPostgres(userId: string): Promise<UserMetadata> {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      include: {
        stats: true,
      },
    });

    if (!user) {
      throw new Error(`User ${userId} not found`);
    }

    return {
      username: user.username,
      avatarUrl: user.avatar || undefined,
      gamesWon: user.stats?.gamesWon || 0,
      gamesPlayed: user.stats?.gamesPlayed || 0,
    };
  }

  private async getLeaderboardFromPostgres(
    options: LeaderboardOptions,
  ): Promise<LeaderboardResponse> {
    const { heroId, page = 0, pageSize = 50 } = options;

    const skip = page * pageSize;

    const [users, totalCount] = await Promise.all([
      this.prisma.user.findMany({
        where: {
          deletedAt: null,
        },
        include: {
          stats: true,
        },
        orderBy: {
          stats: {
            currentElo: 'desc',
          },
        },
        skip,
        take: pageSize,
      }),
      this.prisma.user.count({
        where: {
          deletedAt: null,
        },
      }),
    ]);

    const entries: LeaderboardEntry[] = users.map((user: any, index: number) => ({
      rank: skip + index + 1,
      userId: user.id,
      username: user.username,
      avatarUrl: user.avatar || undefined,
      elo: user.stats?.currentElo || 1200,
      gamesWon: user.stats?.gamesWon || 0,
      gamesPlayed: user.stats?.gamesPlayed || 0,
      winRate:
        user.stats && user.stats.gamesPlayed > 0
          ? (user.stats.gamesWon / user.stats.gamesPlayed) * 100
          : 0,
    }));

    return {
      entries,
      totalCount,
      page,
      pageSize,
    };
  }

  private async getPlayerRankFromPostgres(
    userId: string,
    heroId: string | undefined,
    timeFrame: string,
  ): Promise<LeaderboardRank> {
    const userStats = await this.prisma.userStats.findUnique({
      where: { userId },
    });

    if (!userStats) {
      throw new Error('User stats not found');
    }

    const rank = await this.prisma.userStats.count({
      where: {
        currentElo: {
          gt: userStats.currentElo,
        },
      },
    });

    return {
      rank: rank + 1,
      userId,
      elo: userStats.currentElo,
      heroId,
      timeFrame,
    };
  }
}
