/**
 * Game Sanity Service
 *
 * Обработка edge cases и recovery механизмов.
 *
 * ФАЗА 8E: Edge Cases & Recovery
 */

import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { QueueManagerService } from './queue-manager.service';
import { MatchConfirmationService } from './match-confirmation.service';
import { PenaltyService } from './penalty.service';
import { PrismaService } from '../../database/prisma.service';
import { GameStatus } from '@prisma/client';

const ZOMBIE_GAME_THRESHOLD_MINUTES = 5;
const STUCK_CONFIRMATION_THRESHOLD_MINUTES = 2;

@Injectable()
export class GameSanityService {
  private readonly logger = new Logger(GameSanityService.name);

  constructor(
    private readonly queueManager: QueueManagerService,
    private readonly confirmationService: MatchConfirmationService,
    private readonly penaltyService: PenaltyService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Ежеминутная проверка застрявших игр
   */
  @Cron(CronExpression.EVERY_MINUTE)
  async cleanupZombieGames(): Promise<void> {
    try {
      const threshold = new Date(Date.now() - ZOMBIE_GAME_THRESHOLD_MINUTES * 60 * 1000);

      // Находим игры в статусе PENDING, которые давно не обновлялись
      const zombieGames = await this.prisma.game.findMany({
        where: {
          status: GameStatus.PENDING,
          createdAt: {
            lt: threshold,
          },
        },
        take: 50,
      });

      for (const game of zombieGames) {
        await this.handleZombieGame(game.id);
      }

      if (zombieGames.length > 0) {
        this.logger.warn(`Cleaned up ${zombieGames.length} zombie games`);
      }
    } catch (error) {
      this.logger.error(`Zombie game cleanup failed: ${error}`);
    }
  }

  /**
   * Обработка zombie игры
   */
  private async handleZombieGame(gameId: string): Promise<void> {
    try {
      // Проверяем, есть ли подтверждение
      const confirmation = await this.confirmationService.getConfirmation(gameId);

      if (confirmation) {
        // Подтверждение есть - проверяем не истекло ли
        if (confirmation.expiresAt < new Date()) {
          // Удаляем подтверждение
          await this.forceCancelConfirmation(gameId);
        }
      } else {
        // Подтверждения нет - отменяем игру
        await this.prisma.game.update({
          where: { id: gameId },
          data: { status: GameStatus.ABORTED },
        });
      }

      this.logger.debug(`Handled zombie game ${gameId}`);
    } catch (error) {
      this.logger.error(`Failed to handle zombie game ${gameId}: ${error}`);
    }
  }

  /**
   * Принудительно отменить подтверждение
   */
  async forceCancelConfirmation(gameId: string): Promise<void> {
    try {
      // Получаем игру
      const game = await this.prisma.game.findUnique({
        where: { id: gameId },
      });

      if (!game) {
        return;
      }

      // Применяем penalty к обоим игрокам (так как неизвестно кто виноват)
      if (game.hostId) {
        await this.penaltyService.recordTimeout(game.hostId);
      }
      if (game.opponentId) {
        await this.penaltyService.recordTimeout(game.opponentId);
      }

      // Отменяем игру
      await this.prisma.game.update({
        where: { id: gameId },
        data: { status: GameStatus.ABORTED },
      });

      this.logger.warn(`Force cancelled confirmation for game ${gameId}`);
    } catch (error) {
      this.logger.error(`Failed to force cancel confirmation: ${error}`);
    }
  }

  /**
   * Очистка игроков, которые застряли в очереди
   */
  async cleanupStuckQueueEntries(): Promise<void> {
    try {
      const entries = await this.queueManager.getPostgresEntries();
      const now = Date.now();
      const STUCK_THRESHOLD_MS = 30 * 60 * 1000; // 30 минут

      let cleaned = 0;

      for (const entry of entries) {
        const ageMs = now - entry.joinedAt.getTime();

        if (ageMs > STUCK_THRESHOLD_MS) {
          // Игрок застрял - удаляем
          await this.queueManager.removeFromQueue(entry.userId, entry.mode);
          cleaned++;
        }
      }

      if (cleaned > 0) {
        this.logger.warn(`Cleaned up ${cleaned} stuck queue entries`);
      }
    } catch (error) {
      this.logger.error(`Stuck queue entry cleanup failed: ${error}`);
    }
  }

  /**
   * Проверка целостности: убедиться, что все в PENDING играх имеют подтверждения
   */
  async verifyPendingGames(): Promise<void> {
    try {
      const pendingGames = await this.prisma.game.findMany({
        where: {
          status: GameStatus.PENDING,
        },
        select: {
          id: true,
          hostId: true,
          opponentId: true,
        },
      });

      let issues = 0;

      for (const game of pendingGames) {
        const confirmation = await this.confirmationService.getConfirmation(game.id);

        if (!confirmation) {
          // Игра без подтверждения - либо timeout, либо ошибка
          this.logger.warn(`Game ${game.id} is PENDING but has no confirmation`);

          // Проверяем, не застряла ли игра
          const gameAge = Date.now() - new Date().getTime();
          if (gameAge > STUCK_CONFIRMATION_THRESHOLD_MINUTES * 60 * 1000) {
            await this.handleZombieGame(game.id);
            issues++;
          }
        }
      }

      if (issues > 0) {
        this.logger.warn(`Found and fixed ${issues} pending game issues`);
      }
    } catch (error) {
      this.logger.error(`Pending games verification failed: ${error}`);
    }
  }

  /**
   * Проверка: убедиться, что игроки с подтверждениями не в очереди
   */
  async verifyQueueConsistency(): Promise<void> {
    try {
      const pendingGames = await this.prisma.game.findMany({
        where: {
          status: GameStatus.PENDING,
        },
        select: {
          id: true,
          hostId: true,
          opponentId: true,
        },
      });

      let fixed = 0;

      for (const game of pendingGames) {
        // Проверяем host
        if (game.hostId) {
          for (const mode of ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI']) {
            if (await this.queueManager.isInQueue(game.hostId, mode)) {
              await this.queueManager.removeFromQueue(game.hostId, mode);
              fixed++;
              this.logger.debug(`Removed ${game.hostId} from queue (in game ${game.id})`);
            }
          }
        }

        // Проверяем opponent
        if (game.opponentId) {
          for (const mode of ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI']) {
            if (await this.queueManager.isInQueue(game.opponentId, mode)) {
              await this.queueManager.removeFromQueue(game.opponentId, mode);
              fixed++;
              this.logger.debug(`Removed ${game.opponentId} from queue (in game ${game.id})`);
            }
          }
        }
      }

      if (fixed > 0) {
        this.logger.warn(`Fixed ${fixed} queue consistency issues`);
      }
    } catch (error) {
      this.logger.error(`Queue consistency check failed: ${error}`);
    }
  }

  /**
   * Ручной запуск всех проверок
   */
  async runAllChecks(): Promise<{
    zombieGames: number;
    stuckEntries: number;
    pendingIssues: number;
    queueIssues: number;
  }> {
    const results = {
      zombieGames: 0,
      stuckEntries: 0,
      pendingIssues: 0,
      queueIssues: 0,
    };

    // Cleanup zombie games
    try {
      const threshold = new Date(Date.now() - ZOMBIE_GAME_THRESHOLD_MINUTES * 60 * 1000);
      const zombieGames = await this.prisma.game.findMany({
        where: {
          status: GameStatus.PENDING,
          createdAt: { lt: threshold },
        },
        take: 50,
      });

      for (const game of zombieGames) {
        await this.handleZombieGame(game.id);
      }

      results.zombieGames = zombieGames.length;
    } catch {
      // Игнорируем
    }

    // Cleanup stuck entries
    try {
      const entries = await this.queueManager.getPostgresEntries();
      const now = Date.now();
      const STUCK_THRESHOLD_MS = 30 * 60 * 1000;

      for (const entry of entries) {
        if (now - entry.joinedAt.getTime() > STUCK_THRESHOLD_MS) {
          await this.queueManager.removeFromQueue(entry.userId, entry.mode);
          results.stuckEntries++;
        }
      }
    } catch {
      // Игнорируем
    }

    // Verify pending games
    try {
      await this.verifyPendingGames();
    } catch {
      // Игнорируем
    }

    // Verify queue consistency
    try {
      await this.verifyQueueConsistency();
    } catch {
      // Игнорируем
    }

    return results;
  }

  /**
   * Получить статус здоровья системы
   */
  async getHealthStatus(): Promise<{
    healthy: boolean;
    queueStats: Record<string, number>;
    pendingGames: number;
    issues: string[];
  }> {
    const issues: string[] = [];

    // Проверяем очереди
    const queueStats = await this.queueManager.getAllQueueStats();
    const totalInQueue = Object.values(queueStats).reduce((a, b) => a + b, 0);

    // Проверяем pending игры
    const pendingGames = await this.prisma.game.count({
      where: { status: GameStatus.PENDING },
    });

    // Если pending игр больше чем игроков в очереди, что-то не так
    if (pendingGames > totalInQueue * 2) {
      issues.push(
        `More pending games (${pendingGames}) than expected for queue size (${totalInQueue})`,
      );
    }

    // Проверяем старые pending игры
    const oldPendingGames = await this.prisma.game.count({
      where: {
        status: GameStatus.PENDING,
        createdAt: {
          lt: new Date(Date.now() - ZOMBIE_GAME_THRESHOLD_MINUTES * 60 * 1000),
        },
      },
    });

    if (oldPendingGames > 0) {
      issues.push(`${oldPendingGames} old pending games detected`);
    }

    return {
      healthy: issues.length === 0,
      queueStats,
      pendingGames,
      issues,
    };
  }

  /**
   * Восстановление после crash
   * Вызывается при startup
   */
  async recoverFromCrash(): Promise<void> {
    this.logger.log('Starting crash recovery...');

    try {
      // 1. Синхронизируем очередь из PostgreSQL
      // (это делается в QueueSyncService)

      // 2. Проверяем целостность pending игр
      await this.verifyPendingGames();

      // 3. Проверяем целостность очереди
      await this.verifyQueueConsistency();

      // 4. Очищаем zombie игры
      await this.cleanupZombieGames();

      this.logger.log('Crash recovery completed');
    } catch (error) {
      this.logger.error(`Crash recovery failed: ${error}`);
    }
  }
}
