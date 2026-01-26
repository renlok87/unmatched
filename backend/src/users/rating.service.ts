import { Injectable } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';

export interface RatingResult {
  winner: number;
  loser: number;
}

export interface RatingChange {
  oldRating: number;
  newRating: number;
  change: number;
}

@Injectable()
export class RatingService {
  // K-factor для ELO рейтинга
  private readonly K_FACTOR = 32;

  constructor(private prisma: PrismaService) {}

  /**
   * Рассчитать новые ELO рейтинги после игры
   * ELO формула:
   * Ea = 1 / (1 + 10^((Rb - Ra) / 400))
   * Ra' = Ra + K * (Sa - Ea)
   *
   * где:
   * - Ra, Rb - текущие рейтинги игроков A и B
   * - Ea - ожидаемый счёт для игрока A
   * - Sa - фактический результат (1 для победы, 0 для поражения)
   * - K - коэффициент (обычно 32)
   */
  calculateNewRatings(winnerElo: number, loserElo: number): RatingResult {
    // Ожидаемый счёт для победителя
    const winnerExpectedScore = this.calculateExpectedScore(winnerElo, loserElo);

    // Ожидаемый счёт для проигравшего
    const loserExpectedScore = this.calculateExpectedScore(loserElo, winnerElo);

    // Фактический результат: победитель - 1, проигравший - 0
    const winnerActualScore = 1;
    const loserActualScore = 0;

    // Новые рейтинги
    const newWinnerElo = Math.round(
      winnerElo + this.K_FACTOR * (winnerActualScore - winnerExpectedScore),
    );

    const newLoserElo = Math.round(
      loserElo + this.K_FACTOR * (loserActualScore - loserExpectedScore),
    );

    return {
      winner: newWinnerElo,
      loser: newLoserElo,
    };
  }

  /**
   * Рассчитать ожидаемый счёт
   * Ea = 1 / (1 + 10^((Rb - Ra) / 400))
   */
  private calculateExpectedScore(playerRating: number, opponentRating: number): number {
    const power = (opponentRating - playerRating) / 400;
    return 1 / (1 + Math.pow(10, power));
  }

  /**
   * Получить рейтинг игрока
   * Если указан heroId, возвращает рейтинг для конкретного героя
   */
  async getPlayerRating(userId: string, heroId?: string): Promise<number> {
    if (heroId) {
      // Получаем рейтинг для конкретного героя из heroStats
      const stats = await this.prisma.userStats.findUnique({
        where: { userId },
      });

      if (!stats) {
        return 1200; // Базовый рейтинг
      }

      const heroStats = stats.heroStats as Record<string, any> | null;
      if (heroStats && heroStats[heroId]) {
        return heroStats[heroId].elo || 1200;
      }

      return 1200; // Базовый рейтинг если нет статистики по герою
    }

    // Общий рейтинг игрока
    const stats = await this.prisma.userStats.findUnique({
      where: { userId },
    });

    return stats?.currentElo || 1200;
  }

  /**
   * Обновить рейтинг игрока после игры
   */
  async updatePlayerRating(
    userId: string,
    newRating: number,
    heroId?: string,
  ): Promise<void> {
    const stats = await this.prisma.userStats.findUnique({
      where: { userId },
    });

    if (!stats) {
      throw new Error('Stats not found for user');
    }

    const newPeakElo = Math.max(stats.peakElo, newRating);

    if (heroId) {
      // Обновляем рейтинг для конкретного героя
      const heroStats = (stats.heroStats as Record<string, any>) || {};

      if (!heroStats[heroId]) {
        heroStats[heroId] = {
          gamesPlayed: 0,
          gamesWon: 0,
          elo: 1200,
        };
      }

      const oldHeroElo = heroStats[heroId].elo;
      heroStats[heroId].elo = newRating;
      heroStats[heroId].peakElo = Math.max(heroStats[heroId].peakElo || 1200, newRating);

      await this.prisma.userStats.update({
        where: { userId },
        data: {
          heroStats,
        },
      });
    } else {
      // Обновляем общий рейтинг
      await this.prisma.userStats.update({
        where: { userId },
        data: {
          currentElo: newRating,
          peakElo: newPeakElo,
        },
      });
    }
  }

  /**
   * Рассчитать изменение рейтинга с детализацией
   */
  calculateRatingChange(
    playerRating: number,
    opponentRating: number,
    didWin: boolean,
  ): RatingChange {
    const expectedScore = this.calculateExpectedScore(playerRating, opponentRating);
    const actualScore = didWin ? 1 : 0;
    const newRating = Math.round(
      playerRating + this.K_FACTOR * (actualScore - expectedScore),
    );

    return {
      oldRating: playerRating,
      newRating,
      change: newRating - playerRating,
    };
  }

  /**
   * Получить K-factor (для возможной кастомизации в будущем)
   */
  getKFactor(): number {
    return this.K_FACTOR;
  }
}
