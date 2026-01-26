import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { RatingService } from './rating.service';
import { UserStatsResponse, LeaderboardEntryResponse, LeaderboardOptionsDto, TimeFrame } from './dto';

interface LeaderboardQueryOptions {
  heroId?: string;
  timeFrame?: TimeFrame;
  limit?: number;
}

@Injectable()
export class UserStatsService {
  constructor(
    private prisma: PrismaService,
    private ratingService: RatingService,
  ) {}

  /**
   * Получить статистику пользователя
   */
  async getStats(userId: string): Promise<UserStatsResponse> {
    const stats = await this.prisma.userStats.findUnique({
      where: { userId },
    });

    if (!stats) {
      // Создаем статистику если её нет
      const newStats = await this.prisma.userStats.create({
        data: { userId },
      });

      return this.mapToStatsResponse(newStats);
    }

    return this.mapToStatsResponse(stats);
  }

  /**
   * Обновить статистику после игры
   */
  async updateStatsAfterGame(gameId: string, winnerId: string, loserId: string): Promise<void> {
    // Получаем текущую статистику обоих игроков
    const [winnerStats, loserStats] = await Promise.all([
      this.prisma.userStats.findUnique({ where: { userId: winnerId } }),
      this.prisma.userStats.findUnique({ where: { userId: loserId } }),
    ]);

    if (!winnerStats || !loserStats) {
      throw new NotFoundException('Статистика одного из игроков не найдена');
    }

    // Рассчитываем новые ELO рейтинги
    const newRatings = this.ratingService.calculateNewRatings(
      winnerStats.currentElo,
      loserStats.currentElo,
    );

    // Обновляем статистику в транзакции
    await this.prisma.$transaction([
      // Победитель
      this.prisma.userStats.update({
        where: { userId: winnerId },
        data: {
          gamesPlayed: winnerStats.gamesPlayed + 1,
          gamesWon: winnerStats.gamesWon + 1,
          winRate: this.calculateWinRate(winnerStats.gamesWon + 1, winnerStats.gamesPlayed + 1),
          currentElo: newRatings.winner,
          peakElo: Math.max(winnerStats.peakElo, newRatings.winner),
          lastPlayedAt: new Date(),
        },
      }),
      // Проигравший
      this.prisma.userStats.update({
        where: { userId: loserId },
        data: {
          gamesPlayed: loserStats.gamesPlayed + 1,
          gamesLost: loserStats.gamesLost + 1,
          winRate: this.calculateWinRate(loserStats.gamesWon, loserStats.gamesPlayed + 1),
          currentElo: newRatings.loser,
          lastPlayedAt: new Date(),
        },
      }),
    ]);
  }

  /**
   * Обновить статистику для конкретного героя
   * Использует атомарное обновление для избежания race conditions
   */
  async updateHeroStats(
    userId: string,
    heroId: string,
    didWin: boolean,
    playTime: number,
  ): Promise<void> {
    // Проверяем существование статистики
    const stats = await this.prisma.userStats.findUnique({
      where: { userId },
    });

    if (!stats) {
      throw new NotFoundException('Статистика пользователя не найдена');
    }

    // Используем PostgreSQL JSONB операции для атомарного обновления
    // Это предотвращает race conditions при одновременных запросах
    const winIncrement = didWin ? 1 : 0;
    const loseIncrement = didWin ? 0 : 1;

    await this.prisma.$executeRawUnsafe(`
      UPDATE "UserStats"
      SET
        "heroStats" = COALESCE("heroStats", '{}'::jsonb) ||
          jsonb_build_object(
            $1,
            jsonb_build_object(
              'gamesPlayed', COALESCE(("heroStats"->>$1)::int, 0) + 1,
              'gamesWon', COALESCE(("heroStats"->>$1)->>'gamesWon', '0')::int + $2,
              'gamesLost', COALESCE(("heroStats"->>$1)->>'gamesLost', '0')::int + $3,
              'totalPlayTime', COALESCE(("heroStats"->>$1)->>'totalPlayTime', '0')::int + $4,
              'elo', COALESCE(("heroStats"->>$1)->>'elo', '1200')::int,
              'peakElo', GREATEST(COALESCE(("heroStats"->>$1)->>'peakElo', '1200')::int, COALESCE(("heroStats"->>$1)->>'elo', '1200')::int),
              'winRate', ROUND(
                (COALESCE(("heroStats"->>$1)->>'gamesWon', '0')::int + $2)::numeric /
                NULLIF((COALESCE(("heroStats"->>$1)::int, 0) + 1), 0) * 100,
                2
              )
            )
          ),
        "totalPlayTime" = "totalPlayTime" + $4
      WHERE "userId" = $5
    `, heroId, winIncrement, loseIncrement, playTime, userId);
  }

  /**
   * Получить таблицу лидеров
   */
  async getLeaderboard(options: LeaderboardQueryOptions): Promise<LeaderboardEntryResponse[]> {
    const limit = options.limit || 50;
    const timeFrame = options.timeFrame || TimeFrame.ALL;

    // Фильтрация по временному периоду
    let startDate: Date | undefined;
    if (timeFrame === TimeFrame.WEEK) {
      startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    } else if (timeFrame === TimeFrame.MONTH) {
      startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    }

    // Получаем записи из таблицы leaderboard
    const leaderboardEntries = await this.prisma.leaderboardEntry.findMany({
      where: {
        heroId: options.heroId || null,
        timeFrame,
      },
      orderBy: {
        elo: 'desc',
      },
      take: limit,
    });

    // Если записей нет или они устарели, создаем их на основе UserStats
    if (leaderboardEntries.length === 0) {
      return await this.generateLeaderboard(options);
    }

    // Загружаем данные пользователей
    const userIds = leaderboardEntries.map((e) => e.userId);
    const users = await this.prisma.user.findMany({
      where: { id: { in: userIds } },
      select: {
        id: true,
        username: true,
        avatar: true,
      },
    });

    const userMap = new Map(users.map((u) => [u.id, u]));

    return leaderboardEntries.map((entry) => ({
      rank: entry.rank,
      user: userMap.get(entry.userId) || {
        id: entry.userId,
        username: 'Unknown',
        avatar: null,
      },
      elo: entry.elo,
      gamesWon: entry.gamesWon,
      gamesPlayed: entry.gamesPlayed,
    }));
  }

  /**
   * Сгенерировать таблицу лидеров из UserStats
   */
  private async generateLeaderboard(
    options: LeaderboardQueryOptions,
  ): Promise<LeaderboardEntryResponse[]> {
    const limit = options.limit || 50;

    // Получаем статистику всех игроков
    // Примечание: Фильтрация по heroId делается на уровне приложения,
    // так как JSON фильтрация в Prisma для PostgreSQL имеет ограничения
    let stats = await this.prisma.userStats.findMany({
      orderBy: {
        currentElo: 'desc',
      },
      take: limit * 2, // Берем больше записей для фильтрации
    });

    // Фильтруем по heroId если нужно
    if (options.heroId) {
      stats = stats.filter((stat) => {
        const heroStats = stat.heroStats as Record<string, any> | null;
        return heroStats && heroStats[options.heroId!];
      });
    }

    stats = stats.slice(0, limit);

    // Получаем данные пользователей
    const userIds = stats.map((s) => s.userId);
    const users = await this.prisma.user.findMany({
      where: { id: { in: userIds } },
      select: {
        id: true,
        username: true,
        avatar: true,
      },
    });

    const userMap = new Map(users.map((u) => [u.id, u]));

    return stats.map((stat, index) => ({
      rank: index + 1,
      user: userMap.get(stat.userId) || {
        id: stat.userId,
        username: 'Unknown',
        avatar: null,
      },
      elo: stat.currentElo,
      gamesWon: stat.gamesWon,
      gamesPlayed: stat.gamesPlayed,
    }));
  }

  /**
   * Рассчитать процент побед
   */
  private calculateWinRate(wins: number, total: number): number {
    if (total === 0) return 0;
    return Math.round((wins / total) * 100 * 100) / 100; // Округление до 2 знаков
  }

  /**
   * Преобразовать в ответ для API
   */
  private mapToStatsResponse(stats: any): UserStatsResponse {
    // Определяем любимого героя
    let favoriteHero = null;
    const heroStats = stats.heroStats as Record<string, any> | null;

    if (heroStats && Object.keys(heroStats).length > 0) {
      const heroEntries = Object.entries(heroStats);
      const sorted = heroEntries.sort((a, b) => b[1].gamesPlayed - a[1].gamesPlayed);
      const [topHeroId, topHeroData] = sorted[0];

      favoriteHero = {
        id: topHeroId,
        name: topHeroData.name || topHeroId,
        nameEn: topHeroData.nameEn || topHeroId,
        nameRu: topHeroData.nameRu || topHeroId,
      };
    }

    return {
      userId: stats.userId,
      gamesPlayed: stats.gamesPlayed,
      gamesWon: stats.gamesWon,
      gamesLost: stats.gamesLost,
      winRate: stats.winRate,
      currentElo: stats.currentElo,
      peakElo: stats.peakElo,
      lastPlayedAt: stats.lastPlayedAt,
      totalPlayTime: stats.totalPlayTime,
      favoriteHero,
    };
  }

  /**
   * Обновить таблицу лидеров (для cron jobs)
   */
  async refreshLeaderboard(heroId: string | null = null): Promise<void> {
    const timeFrames = [TimeFrame.ALL, TimeFrame.WEEK, TimeFrame.MONTH];

    for (const timeFrame of timeFrames) {
      // Получаем топ-100 игроков
      const stats = await this.prisma.userStats.findMany({
        orderBy: { currentElo: 'desc' },
        take: 100,
      });

      // Удаляем старые записи
      await this.prisma.leaderboardEntry.deleteMany({
        where: {
          heroId: heroId || null,
          timeFrame,
        },
      });

      // Создаем новые записи
      const entries = stats.map((stat, index) => ({
        userId: stat.userId,
        heroId: heroId || null,
        timeFrame,
        rank: index + 1,
        elo: stat.currentElo,
        gamesWon: stat.gamesWon,
        gamesPlayed: stat.gamesPlayed,
      }));

      await this.prisma.leaderboardEntry.createMany({
        data: entries,
      });
    }
  }
}
