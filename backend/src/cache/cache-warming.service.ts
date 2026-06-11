/**
 * Cache Warming Service
 *
 * Предотвращает cache stampede через прогрев кэша.
 * Использует @nestjs/schedule для cron задач.
 */

import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { RedisService } from '../redis/redis.service';

@Injectable()
export class CacheWarmingService {
  private readonly logger = new Logger(CacheWarmingService.name);

  constructor(private readonly redis: RedisService) {}

  /**
   * Прогрев кэша активных игр каждые 5 минут
   */
  @Cron(CronExpression.EVERY_5_MINUTES)
  async warmActiveGames(): Promise<void> {
    try {
      // TODO: Получить список активных игр из БД
      const activeGameIds: string[] = [];

      for (const gameId of activeGameIds) {
        await this.warmGameCache(gameId);
      }

      if (activeGameIds.length > 0) {
        this.logger.debug(`Warmed cache for ${activeGameIds.length} active games`);
      }
    } catch (error) {
      this.logger.error('Error warming cache:', error);
    }
  }

  /**
   * Прогрев кэша для конкретной игры
   */
  async warmGameCache(gameId: string): Promise<void> {
    const cacheKey = `game:${gameId}:state`;

    // Используем getOrSet с distributed lock
    await this.redis.getOrSet(
      cacheKey,
      async () => {
        // TODO: Загрузить состояние игры из БД
        return null;
      },
      300, // 5 минут TTL
    );
  }

  /**
   * Ручной прогрев кэша для игры
   */
  async warmGameManually(gameId: string): Promise<void> {
    await this.warmGameCache(gameId);
    this.logger.log(`Manually warmed cache for game ${gameId}`);
  }
}
