/**
 * Matchmaking Scheduler Service
 *
 * Фоновый процесс поиска матчей с использованием BullMQ.
 * Распредёлённая блокировка для multi-instance deployments.
 *
 * ФАЗА 8B: Matchmaking Scheduler
 */

import { Injectable, Logger, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue, Worker, Job } from 'bullmq';
import { QueueManagerService } from './queue-manager.service';
import { MatchConfirmationService } from './match-confirmation.service';
import { MatchmakingPubSubService } from '../resolvers/matchmaking.subscription';
import { MatchmakingMetricsService } from './matchmaking-metrics.service';
import { PrismaService } from '../../database/prisma.service';
import { RedisService } from '../../redis/redis.service';
import { boardCellsHaveTopology } from '../../content/mappers/content.mapper';
import { GameStatus, GameMode } from '@prisma/client';
import { MatchResult } from '../models';
import { CONFIRMATION_TTL_SECONDS } from '../models/match-confirmation.model';

const SCHEDULER_QUEUE_NAME = 'matchmaking-scheduler';
const LOCK_KEY = 'matchmaking:scheduler:lock';
const LOCK_TTL_MS = 15000; // 15 секунд - больше интервала
const SCHEDULER_INTERVAL_MS = 5000; // 5 секунд
const MATCH_FIND_BATCH_SIZE = 20; // Максимальное количество пар за одну итерацию

interface SchedulerJobData {
  timestamp: number;
}

@Injectable()
export class MatchmakingSchedulerService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(MatchmakingSchedulerService.name);
  private worker: Worker<SchedulerJobData> | null = null;
  private isRunning = false;

  constructor(
    @InjectQueue(SCHEDULER_QUEUE_NAME)
    private readonly schedulerQueue: Queue<SchedulerJobData>,
    private readonly queueManager: QueueManagerService,
    private readonly confirmationService: MatchConfirmationService,
    private readonly matchmakingPubSub: MatchmakingPubSubService,
    private readonly metricsService: MatchmakingMetricsService,
    private readonly prisma: PrismaService,
    private readonly redis: RedisService,
  ) {}

  async onModuleInit() {
    await this.startScheduler();
  }

  async onModuleDestroy() {
    await this.stopScheduler();
  }

  /**
   * Запуск планировщика
   */
  async startScheduler(): Promise<void> {
    if (this.isRunning) {
      this.logger.warn('Scheduler already running');
      return;
    }

    this.logger.log('Starting matchmaking scheduler...');

    // Создаём repeating job
    await this.schedulerQueue.add(
      'find-matches',
      { timestamp: Date.now() },
      {
        repeat: {
          every: SCHEDULER_INTERVAL_MS,
        },
        jobId: 'recurring-find-matches',
      },
    );

    // Создаём worker для обработки задач
    this.worker = new Worker<SchedulerJobData>(
      SCHEDULER_QUEUE_NAME,
      async (job: Job<SchedulerJobData>) => {
        await this.processMatchmaking(job);
      },
      {
        connection: {
          host: process.env.REDIS_HOST || 'localhost',
          port: parseInt(process.env.REDIS_PORT || '6379', 10),
          password: process.env.REDIS_PASSWORD,
        },
        concurrency: 1,
      },
    );

    this.worker.on('completed', (job) => {
      this.logger.debug(`Scheduler job ${job.id} completed`);
    });

    this.worker.on('failed', (job, error) => {
      this.logger.error(`Scheduler job ${job?.id} failed: ${error}`);
    });

    this.isRunning = true;
    this.logger.log('Matchmaking scheduler started');
  }

  /**
   * Остановка планировщика
   */
  async stopScheduler(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    this.logger.log('Stopping matchmaking scheduler...');

    // Удаляем repeating job
    const repeatableJobs = await this.schedulerQueue.getRepeatableJobs();
    for (const job of repeatableJobs) {
      if (job.name === 'find-matches') {
        await this.schedulerQueue.removeRepeatableByKey(job.key);
      }
    }

    // Останавливаем worker
    if (this.worker) {
      await this.worker.close();
      this.worker = null;
    }

    this.isRunning = false;
    this.logger.log('Matchmaking scheduler stopped');
  }

  /**
   * Обработка матчмейкинга
   * Использует distributed lock для multi-instance safety
   */
  private async processMatchmaking(job: Job<SchedulerJobData>): Promise<void> {
    // Пытаемся получить distributed lock
    const lock = await this.redis.acquireLock(LOCK_KEY, LOCK_TTL_MS);

    if (!lock) {
      this.logger.debug('Could not acquire scheduler lock, skipping this iteration');
      return;
    }

    try {
      this.logger.debug('Processing matchmaking...');

      // Обрабатываем каждый режим отдельно
      const modes: GameMode[] = ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI'];

      for (const mode of modes) {
        await this.processMode(mode);
      }

      this.logger.debug('Matchmaking processing completed');
    } catch (error) {
      this.logger.error(`Matchmaking processing error: ${error}`);
    } finally {
      await this.redis.releaseLock(lock);
    }
  }

  /**
   * Обработка конкретного режима игры
   */
  private async processMode(mode: GameMode): Promise<void> {
    const queueSize = await this.queueManager.getQueueSize(mode);

    if (queueSize < 2) {
      return;
    }

    // Находим пары
    const matches = await this.queueManager.findMultipleMatches(mode, MATCH_FIND_BATCH_SIZE);

    this.logger.debug(`Found ${matches.length} matches for ${mode}`);

    // Создаём игры для каждой пары
    for (const [player1, player2] of matches) {
      await this.createMatch(player1, player2);
    }
  }

  /**
   * Создать матч для двух игроков
   */
  private async createMatch(
    player1: { userId: string; rating: number; heroPref?: string },
    player2: { userId: string; rating: number; heroPref?: string },
  ): Promise<void> {
    try {
      const mode = await this.getPlayerMode(player1.userId);

      if (!mode) {
        this.logger.warn(`Player ${player1.userId} not in queue, skipping match`);
        return;
      }

      const game = await this.prisma.game.create({
        data: {
          status: GameStatus.PENDING,
          mode: mode as GameMode,
          hostId: player1.userId,
          opponentId: player2.userId,
          boardId: await this.getDefaultBoardId(),
        },
      });

      await this.confirmationService.createConfirmation(game.id, player1.userId, player2.userId);

      await this.queueManager.removeFromQueue(player1.userId, mode);
      await this.queueManager.removeFromQueue(player2.userId, mode);

      await this.matchmakingPubSub.publishMatchFound(
        game.id,
        player1.userId,
        player2.userId,
        mode,
        new Date(Date.now() + CONFIRMATION_TTL_SECONDS * 1000),
      );

      this.metricsService.recordMatchCreated(mode, 0);

      this.logger.log(`Match created: ${game.id} between ${player1.userId} and ${player2.userId}`);
    } catch (error) {
      this.logger.error(`Failed to create match: ${error}`);
    }
  }

  /**
   * Получить режим игры игрока
   */
  private async getPlayerMode(userId: string): Promise<string | null> {
    // Проверяем все очереди
    for (const mode of ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI']) {
      if (await this.queueManager.isInQueue(userId, mode)) {
        return mode;
      }
    }
    return null;
  }

  /**
   * Получить ID доски по умолчанию: та же доска, что у GameService.createGame
   * (самая старая по createdAt). Доски с топологией оригинальной карты
   * (ENV-MAPS, cells с links) играются только UE-клиентом — дефолтом матчмейкинга
   * они не становятся (web-клиент такую игру не отрисует).
   */
  private async getDefaultBoardId(): Promise<string> {
    const boards = await this.prisma.board.findMany({
      orderBy: { createdAt: 'asc' },
      select: { id: true, cells: true },
    });
    const board = boards.find((b) => !boardCellsHaveTopology(b.cells));
    return board?.id || 'default-board';
  }

  /**
   * Ручной запуск поиска матчей
   */
  async triggerMatchmaking(): Promise<MatchResult[]> {
    // Пытаемся получить lock
    const lock = await this.redis.acquireLock(LOCK_KEY, LOCK_TTL_MS);

    if (!lock) {
      throw new Error('Could not acquire lock - another instance is processing');
    }

    try {
      const results: MatchResult[] = [];
      const modes: GameMode[] = ['ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI'];

      for (const mode of modes) {
        const matches = await this.queueManager.findMultipleMatches(mode, 10);

        for (const [player1, player2] of matches) {
          await this.createMatch(player1, player2);

          results.push({
            gameId: 'pending',
            player1Id: player1.userId,
            player2Id: player2.userId,
            player1Rating: player1.rating,
            player2Rating: player2.rating,
            mode,
            matchedAt: new Date(),
          });
        }
      }

      return results;
    } finally {
      await this.redis.releaseLock(lock);
    }
  }

  /**
   * Получить статус планировщика
   */
  getStatus(): { running: boolean; locked: boolean } {
    return {
      running: this.isRunning,
      locked: false, // Можно проверить lock через Redis
    };
  }
}
