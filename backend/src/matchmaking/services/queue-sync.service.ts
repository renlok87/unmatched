/**
 * Queue Sync Service
 *
 * Синхронизация очереди между Redis и PostgreSQL.
 * Recovery после Redis restart, очистка истёкших записей.
 *
 * ФАЗА 8A: QueueSyncService
 */

import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { QueueManagerService } from './queue-manager.service';

const SYNC_INTERVAL_MINUTES = 10;
const ENTRY_TTL_SECONDS = 600; // 10 минут

@Injectable()
export class QueueSyncService implements OnModuleInit {
  private readonly logger = new Logger(QueueSyncService.name);
  private isSyncing = false;

  constructor(private readonly queueManager: QueueManagerService) {}

  async onModuleInit() {
    // Выполняем синхронизацию при запуске
    await this.syncFromPostgreSQL();
  }

  /**
   * Синхронизация из PostgreSQL при запуске
   * Восстанавливает очередь после Redis restart
   */
  async syncFromPostgreSQL(): Promise<void> {
    if (this.isSyncing) {
      this.logger.warn('Sync already in progress, skipping');
      return;
    }

    this.isSyncing = true;
    this.logger.log('Starting queue sync from PostgreSQL...');

    try {
      const entries = await this.queueManager.getPostgresEntries();

      if (entries.length === 0) {
        this.logger.log('No entries to sync from PostgreSQL');
        return;
      }

      let restored = 0;
      let skipped = 0;

      for (const entry of entries) {
        // Проверяем, не истёк ли TTL
        const ageSeconds = Math.floor((Date.now() - entry.joinedAt.getTime()) / 1000);

        if (ageSeconds > ENTRY_TTL_SECONDS) {
          skipped++;
          continue;
        }

        // Проверяем, есть ли уже запись в Redis
        const alreadyInQueue = await this.queueManager.isInQueue(entry.userId, entry.mode);

        if (!alreadyInQueue) {
          await this.queueManager.addToQueue(
            entry.userId,
            entry.rating,
            entry.mode,
            entry.heroPref,
          );
          restored++;
        } else {
          skipped++;
        }
      }

      this.logger.log(`Queue sync completed: ${restored} restored, ${skipped} skipped`);
    } catch (error) {
      this.logger.error(`Queue sync failed: ${error}`);
    } finally {
      this.isSyncing = false;
    }
  }

  /**
   * Очистка истёкших записей
   * Выполняется каждые 10 минут
   */
  @Cron(CronExpression.EVERY_10_MINUTES)
  async cleanupExpiredEntries(): Promise<void> {
    this.logger.log('Starting cleanup of expired queue entries...');

    try {
      const entries = await this.queueManager.getPostgresEntries();
      let removed = 0;

      for (const entry of entries) {
        const ageSeconds = Math.floor((Date.now() - entry.joinedAt.getTime()) / 1000);

        if (ageSeconds > ENTRY_TTL_SECONDS) {
          await this.queueManager.removeFromQueue(entry.userId, entry.mode);
          removed++;
        }
      }

      this.logger.log(`Cleanup completed: ${removed} expired entries removed`);
    } catch (error) {
      this.logger.error(`Cleanup failed: ${error}`);
    }
  }

  /**
   * Ручной запуск синхронизации
   */
  async triggerSync(): Promise<{ restored: number; skipped: number }> {
    await this.syncFromPostgreSQL();

    const stats = await this.queueManager.getAllQueueStats();
    const totalPlayers = Object.values(stats).reduce((a, b) => a + b, 0);

    return {
      restored: totalPlayers,
      skipped: 0,
    };
  }

  /**
   * Получить статус синхронизации
   */
  getSyncStatus(): { syncing: boolean } {
    return { syncing: this.isSyncing };
  }
}
