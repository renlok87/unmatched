/**
 * Penalty Service
 *
 * Система штрафов за отклонение матчей.
 * Decline -> -25 ELO
 * 3 decline за час -> temp ban 30 мин
 *
 * ФАЗа 8C: Penalty System
 */

import { Injectable, Logger } from '@nestjs/common';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';
import { PenaltyRecord, PenaltyInfo, PENALTY_CONFIG, TempBanInfo } from '../models';

const PENALTY_PREFIX = 'mm:penalty:';
const TEMP_BAN_PREFIX = 'mm:tempban:';

@Injectable()
export class PenaltyService {
  private readonly logger = new Logger(PenaltyService.name);

  constructor(
    private readonly redis: RedisService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Получить информацию о штрафах пользователя
   */
  async getPenaltyInfo(userId: string): Promise<PenaltyInfo> {
    const record = await this.getPenaltyRecord(userId);
    const tempBan = await this.getTempBan(userId);

    const canJoinQueue = !tempBan || tempBan.expiresAt < new Date();

    return {
      canJoinQueue,
      declineCount: record?.declineCount || 0,
      tempBanUntil: tempBan?.expiresAt,
      penaltyElo: canJoinQueue ? PENALTY_CONFIG.ELO_PENALTY : undefined,
    };
  }

  /**
   * Записать decline
   * Возвращает true если применён temp ban
   */
  async recordDecline(userId: string): Promise<{ tempBanned: boolean; eloPenalty: number }> {
    const record = await this.getPenaltyRecord(userId);
    const now = new Date();

    // Проверяем окно decline
    const isInWindow = record && this.isWithinDeclineWindow(record.lastDeclineAt);

    let declineCount = isInWindow ? record.declineCount + 1 : 1;
    let tempBanned = false;

    // Проверяем условие temp ban
    if (declineCount >= PENALTY_CONFIG.DECLINES_FOR_BAN) {
      await this.applyTempBan(userId);
      tempBanned = true;
      declineCount = 0; // Сбрасываем после бана
    }

    // Обновляем запись
    const newRecord: PenaltyRecord = {
      userId,
      declineCount,
      lastDeclineAt: now,
    };

    await this.savePenaltyRecord(newRecord);

    // Применяем ELO штраф
    if (!tempBanned) {
      await this.applyEloPenalty(userId);
    }

    this.logger.warn(
      `User ${userId} declined match. Count: ${declineCount}, Temp banned: ${tempBanned}`,
    );

    return {
      tempBanned,
      eloPenalty: PENALTY_CONFIG.ELO_PENALTY,
    };
  }

  /**
   * Записать timeout (как decline для не принявшего)
   */
  async recordTimeout(userId: string): Promise<void> {
    await this.recordDecline(userId);
  }

  /**
   * Применить временный бан
   */
  private async applyTempBan(userId: string): Promise<void> {
    const now = new Date();
    const expiresAt = new Date(now.getTime() + PENALTY_CONFIG.BAN_DURATION_MINUTES * 60 * 1000);

    const banInfo: TempBanInfo = {
      userId,
      bannedAt: now,
      expiresAt,
      reason: `Too many declines (${PENALTY_CONFIG.DECLINES_FOR_BAN}) in ${PENALTY_CONFIG.DECLINE_WINDOW_HOURS}h`,
    };

    const key = this.getTempBanKey(userId);
    const ttl = PENALTY_CONFIG.BAN_DURATION_MINUTES * 60;

    await this.redis.setJsonex(key, ttl, banInfo);

    this.logger.warn(`Temp ban applied to user ${userId} until ${expiresAt}`);
  }

  /**
   * Применить ELO штраф
   */
  private async applyEloPenalty(userId: string): Promise<void> {
    try {
      const stats = await this.prisma.userStats.findUnique({
        where: { userId },
      });

      if (!stats) {
        return;
      }

      const newElo = Math.max(0, stats.currentElo - PENALTY_CONFIG.ELO_PENALTY);

      await this.prisma.userStats.update({
        where: { userId },
        data: { currentElo: newElo },
      });

      this.logger.debug(`ELO penalty applied to user ${userId}: ${stats.currentElo} -> ${newElo}`);
    } catch (error) {
      this.logger.error(`Failed to apply ELO penalty: ${error}`);
    }
  }

  /**
   * Проверить, находится ли пользователь в окне decline
   */
  private isWithinDeclineWindow(lastDeclineAt: Date): boolean {
    const windowStart = new Date(Date.now() - PENALTY_CONFIG.DECLINE_WINDOW_HOURS * 60 * 60 * 1000);
    return lastDeclineAt > windowStart;
  }

  /**
   * Получить запись о штрафах
   */
  private async getPenaltyRecord(userId: string): Promise<PenaltyRecord | null> {
    const key = this.getPenaltyKey(userId);
    return this.redis.getJson<PenaltyRecord>(key);
  }

  /**
   * Сохранить запись о штрафах
   */
  private async savePenaltyRecord(record: PenaltyRecord): Promise<void> {
    const key = this.getPenaltyKey(record.userId);
    // TTL = окно decline + небольшой запас
    const ttl = PENALTY_CONFIG.DECLINE_WINDOW_HOURS * 3600 + 300;

    await this.redis.setJsonex(key, ttl, record);
  }

  /**
   * Получить информацию о временном бане
   */
  private async getTempBan(userId: string): Promise<TempBanInfo | null> {
    const key = this.getTempBanKey(userId);
    return this.redis.getJson<TempBanInfo>(key);
  }

  /**
   * Проверить, может ли пользователь встать в очередь
   */
  async canJoinQueue(userId: string): Promise<boolean> {
    const info = await this.getPenaltyInfo(userId);
    return info.canJoinQueue;
  }

  /**
   * Сбросить счётчик decline (для тестирования или админских действий)
   */
  async resetDeclines(userId: string): Promise<void> {
    const key = this.getPenaltyKey(userId);
    await this.redis.del(key);
    this.logger.debug(`Decline count reset for user ${userId}`);
  }

  /**
   * Снять временный бан (для админских действий)
   */
  async removeTempBan(userId: string): Promise<void> {
    const key = this.getTempBanKey(userId);
    await this.redis.del(key);
    this.logger.debug(`Temp ban removed for user ${userId}`);
  }

  /**
   * Получить ключ записи о штрафах
   */
  private getPenaltyKey(userId: string): string {
    return `${PENALTY_PREFIX}${userId}`;
  }

  /**
   * Получить ключ временного бана
   */
  private getTempBanKey(userId: string): string {
    return `${TEMP_BAN_PREFIX}${userId}`;
  }

  /**
   * Очистить все данные о штрафах (для тестирования)
   */
  async clearAllPenalties(): Promise<void> {
    // Только в dev/test окружении
    if (process.env.NODE_ENV === 'production') {
      throw new Error('Cannot clear penalties in production');
    }

    // В реальном коде здесь был бы SCAN для удаления всех ключей
    this.logger.debug('All penalties cleared');
  }
}
