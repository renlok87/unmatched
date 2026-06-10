/**
 * Queue Manager Service
 *
 * Управление очередью матчмейкинга с использованием Redis ZSets.
 * O(log N) для добавления, удаления и поиска.
 *
 * ФАЗА 8A: Matchmaking Queue Manager
 */

import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';
import { GameMode } from '@prisma/client';
import { QueueEntry, QueueEntryWithRank, QueuePositionInfo, getEloRange } from '../models';

const QUEUE_PREFIX = 'mm:queue:';
const QUEUE_DATA_PREFIX = 'mm:queue:data:';
const QUEUE_TTL_SECONDS = 300;
const QUEUE_DATA_TTL_SECONDS = 900;
const ENTRY_TTL_SECONDS = 600;

interface RedisQueueEntry {
  userId: string;
  rating: number;
  mode: string;
  heroPref?: string;
  joinedAt: number;
}

@Injectable()
export class QueueManagerService implements OnModuleInit {
  private readonly logger = new Logger(QueueManagerService.name);

  constructor(
    private readonly redis: RedisService,
    private readonly prisma: PrismaService,
  ) {}

  async onModuleInit() {
    this.logger.log('QueueManagerService initialized');
  }

  /**
   * Получить ключ очереди для режима
   */
  private getQueueKey(mode: string): string {
    return `${QUEUE_PREFIX}${mode}`;
  }

  /**
   * Добавить игрока в очередь
   * O(log N) - ZADD
   *
   * @param userId ID пользователя
   * @param rating ELO рейтинг
   * @param mode Игровой режим
   * @param heroPref Предпочтительный герой
   * @returns true если добавлен, false если уже был в очереди (обновлён)
   */
  async addToQueue(
    userId: string,
    rating: number,
    mode: string,
    heroPref?: string,
  ): Promise<{ added: boolean; position: number }> {
    const queueKey = this.getQueueKey(mode);
    const dataKey = `${QUEUE_DATA_PREFIX}${userId}`;
    const now = Date.now();

    await this.redis.hset(dataKey, {
      userId,
      rating: String(rating),
      mode,
      heroPref: heroPref ?? '',
      joinedAt: String(now),
    });
    await this.redis.expire(dataKey, QUEUE_DATA_TTL_SECONDS);

    const result = await this.redis.zadd(queueKey, rating, userId);
    await this.redis.expire(queueKey, QUEUE_TTL_SECONDS);

    await this.saveToPostgres(userId, rating, mode, heroPref);

    const position = await this.getUserPosition(userId, mode);

    this.logger.debug(`User ${userId} added to ${mode} queue at position ${position}`);

    return {
      added: result > 0,
      position,
    };
  }

  /**
   * Удалить игрока из очереди
   * O(log N) - ZREM
   *
   * @param userId ID пользователя
   * @param mode Игровой режим
   */
  async removeFromQueue(userId: string, mode: string): Promise<boolean> {
    const queueKey = this.getQueueKey(mode);
    const dataKey = `${QUEUE_DATA_PREFIX}${userId}`;

    const result = await this.redis.zrem(queueKey, userId);

    await this.redis.del(dataKey);

    await this.removeFromPostgres(userId);

    if (result > 0) {
      this.logger.debug(`User ${userId} removed from ${mode} queue`);
    }

    return result > 0;
  }

  /**
   * Удалить из всех очередей
   */
  async removeFromAllQueues(userId: string): Promise<string[]> {
    const modes = ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI'];
    const removedFrom: string[] = [];

    for (const mode of modes) {
      if (await this.removeFromQueue(userId, mode)) {
        removedFrom.push(mode);
      }
    }

    return removedFrom;
  }

  /**
   * Найти матч для игрока
   * O(log N + M) где M - количество кандидатов в диапазоне
   *
   * Использует expanding window - чем дольше ждёшь, тем шире диапазон
   *
   * @param userId ID пользователя (исключается из поиска)
   * @param mode Игровой режим
   * @returns Найденный кандидат или null
   */
  async findMatch(userId: string, mode: string): Promise<QueueEntry | null> {
    const queueKey = this.getQueueKey(mode);

    // Получаем информацию о текущем игроке
    const userEntry = await this.getEntryByUserId(userId, mode);
    if (!userEntry) {
      return null;
    }

    const waitTimeSeconds = Math.floor((Date.now() - userEntry.joinedAt.getTime()) / 1000);
    const [minDelta, maxDelta] = getEloRange(waitTimeSeconds);

    const minRating = userEntry.rating - minDelta;
    const maxRating = userEntry.rating + maxDelta;

    // Получаем кандидатов в диапазоне ELO
    const candidates = await this.getCandidatesInRange(mode, minRating, maxRating);

    // Исключаем самого себя и уже найденные матчи
    const validCandidates = candidates.filter((c) => c.userId !== userId);

    if (validCandidates.length === 0) {
      return null;
    }

    // Сортируем по близости рейтинга
    validCandidates.sort((a, b) => {
      const diffA = Math.abs(a.rating - userEntry.rating);
      const diffB = Math.abs(b.rating - userEntry.rating);
      return diffA - diffB;
    });

    // Берём лучшего кандидата
    const match = validCandidates[0];

    this.logger.debug(
      `Match found for ${userId}: ${match.userId} (rating diff: ${Math.abs(match.rating - userEntry.rating)})`,
    );

    return match;
  }

  /**
   * Найти несколько пар для массового матчмейкинга
   *
   * @param mode Игровой режим
   * @param maxMatches Максимальное количество пар
   * @returns Массив пар игроков
   */
  async findMultipleMatches(
    mode: string,
    maxMatches = 10,
  ): Promise<Array<[QueueEntry, QueueEntry]>> {
    const entries = await this.getAllEntries(mode);

    if (entries.length < 2) {
      return [];
    }

    const matches: Array<[QueueEntry, QueueEntry]> = [];
    const matched = new Set<string>();

    // Сортируем по времени ожидания
    const sorted = [...entries].sort((a, b) => a.joinedAt.getTime() - b.joinedAt.getTime());

    for (const entry of sorted) {
      if (matched.has(entry.userId)) {
        continue;
      }

      const waitTimeSeconds = Math.floor((Date.now() - entry.joinedAt.getTime()) / 1000);
      const [minDelta, maxDelta] = getEloRange(waitTimeSeconds);

      const minRating = entry.rating - minDelta;
      const maxRating = entry.rating + maxDelta;

      // Ищем партнёра
      for (const candidate of sorted) {
        if (matched.has(candidate.userId) || candidate.userId === entry.userId) {
          continue;
        }

        if (candidate.rating >= minRating && candidate.rating <= maxRating) {
          matches.push([entry, candidate]);
          matched.add(entry.userId);
          matched.add(candidate.userId);

          if (matches.length >= maxMatches) {
            break;
          }
          break;
        }
      }

      if (matches.length >= maxMatches) {
        break;
      }
    }

    return matches;
  }

  /**
   * Получить размер очереди
   * O(1) - ZCARD
   */
  async getQueueSize(mode: string): Promise<number> {
    const queueKey = this.getQueueKey(mode);
    return this.redis.zcard(queueKey);
  }

  /**
   * Получить позицию игрока в очереди
   * O(log N) - ZRANK
   */
  async getUserPosition(userId: string, mode: string): Promise<number> {
    const queueKey = this.getQueueKey(mode);
    const entries = await this.getAllEntries(mode);

    // Сортируем по рейтингу
    const sorted = [...entries].sort((a, b) => a.rating - b.rating);
    const index = sorted.findIndex((e) => e.userId === userId);

    return index >= 0 ? index + 1 : 0;
  }

  /**
   * Получить информацию о позиции
   */
  async getPositionInfo(userId: string, mode: string): Promise<QueuePositionInfo | null> {
    const entry = await this.getEntryByUserId(userId, mode);
    if (!entry) {
      return null;
    }

    const position = await this.getUserPosition(userId, mode);
    const totalPlayers = await this.getQueueSize(mode);

    // Оценка времени ожидания: ~5 секунд на позицию
    const estimatedWaitTime = position * 5;

    return {
      position,
      estimatedWaitTime,
      totalPlayers,
    };
  }

  /**
   * Получить все записи в очереди
   */
  async getAllEntries(mode: string): Promise<QueueEntry[]> {
    const queueKey = this.getQueueKey(mode);

    const userIds = await this.redis.zrange(queueKey, 0, -1, true);

    const entries: QueueEntry[] = [];
    const zombieUserIds: string[] = [];

    for (let i = 0; i < userIds.length; i += 2) {
      const userId = userIds[i];
      const rating = parseInt(userIds[i + 1], 10);
      const dataKey = `${QUEUE_DATA_PREFIX}${userId}`;
      const data = await this.redis.hgetall(dataKey);

      if (data.userId) {
        entries.push({
          userId: data.userId,
          rating,
          mode: data.mode,
          heroPref: data.heroPref || undefined,
          joinedAt: new Date(parseInt(data.joinedAt, 10)),
        });
      } else {
        zombieUserIds.push(userId);
      }
    }

    if (zombieUserIds.length > 0) {
      await this.redis.zremMany(queueKey, ...zombieUserIds);
      this.logger.warn(
        `Removed ${zombieUserIds.length} zombie entries: ${zombieUserIds.join(', ')}`,
      );
    }

    return entries;
  }

  /**
   * Получить кандидатов в диапазоне ELO
   */
  async getCandidatesInRange(
    mode: string,
    minRating: number,
    maxRating: number,
  ): Promise<QueueEntry[]> {
    const queueKey = this.getQueueKey(mode);

    const userIdsWithScores = await this.redis.zrangebyscore(queueKey, minRating, maxRating, true);

    const entries: QueueEntry[] = [];

    for (let i = 0; i < userIdsWithScores.length; i += 2) {
      const userId = userIdsWithScores[i];
      const rating = parseInt(userIdsWithScores[i + 1], 10);
      const dataKey = `${QUEUE_DATA_PREFIX}${userId}`;
      const data = await this.redis.hgetall(dataKey);

      if (data.userId) {
        entries.push({
          userId: data.userId,
          rating,
          mode: data.mode,
          heroPref: data.heroPref || undefined,
          joinedAt: new Date(parseInt(data.joinedAt, 10)),
        });
      }
    }

    return entries;
  }

  /**
   * Получить запись пользователя
   */
  async getEntryByUserId(userId: string, mode: string): Promise<QueueEntry | null> {
    const entries = await this.getAllEntries(mode);
    return entries.find((e) => e.userId === userId) || null;
  }

  /**
   * Проверить, находится ли пользователь в очереди
   */
  async isInQueue(userId: string, mode: string): Promise<boolean> {
    return (await this.getEntryByUserId(userId, mode)) !== null;
  }

  /**
   * Очистить очередь
   */
  async clearQueue(mode: string): Promise<void> {
    const queueKey = this.getQueueKey(mode);
    await this.redis.del(queueKey);
    this.logger.debug(`Cleared ${mode} queue`);
  }

  /**
   * Очистить все очереди
   */
  async clearAllQueues(): Promise<void> {
    const modes = ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI'];
    for (const mode of modes) {
      await this.clearQueue(mode);
    }
  }

  async cleanupUserData(userId: string): Promise<void> {
    const modes = ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI'];

    for (const mode of modes) {
      await this.removeFromQueue(userId, mode);
    }

    const dataKey = `${QUEUE_DATA_PREFIX}${userId}`;
    await this.redis.del(dataKey);
  }

  /**
   * Сохранить запись в PostgreSQL как backup
   */
  private async saveToPostgres(
    userId: string,
    rating: number,
    mode: string,
    heroPref?: string,
  ): Promise<void> {
    try {
      await this.prisma.matchmakingQueueEntry.upsert({
        where: { userId },
        create: {
          userId,
          mode: mode as GameMode,
          rating,
          heroPref,
        },
        update: {
          mode: mode as GameMode,
          rating,
          heroPref,
          joinedAt: new Date(),
        },
      });
    } catch (error) {
      this.logger.error(`Failed to save queue entry to PostgreSQL: ${error}`);
    }
  }

  /**
   * Удалить запись из PostgreSQL
   */
  private async removeFromPostgres(userId: string): Promise<void> {
    try {
      await this.prisma.matchmakingQueueEntry.delete({
        where: { userId },
      });
    } catch {
      // Игнорируем, если запись не существует
    }
  }

  /**
   * Получить все записи из PostgreSQL (для recovery)
   */
  async getPostgresEntries(): Promise<QueueEntry[]> {
    const entries = await this.prisma.matchmakingQueueEntry.findMany({
      where: {
        joinedAt: {
          gte: new Date(Date.now() - ENTRY_TTL_SECONDS * 1000),
        },
      },
    });

    return entries.map((e) => ({
      userId: e.userId,
      rating: e.rating,
      mode: e.mode,
      heroPref: e.heroPref ?? undefined,
      joinedAt: e.joinedAt,
    }));
  }

  /**
   * Получить статистику всех очередей
   */
  async getAllQueueStats(): Promise<Record<string, number>> {
    const modes = ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI'];
    const stats: Record<string, number> = {};

    for (const mode of modes) {
      stats[mode] = await this.getQueueSize(mode);
    }

    return stats;
  }
}
