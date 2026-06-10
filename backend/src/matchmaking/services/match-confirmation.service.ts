/**
 * Match Confirmation Service
 *
 * Двухфазное подтверждение матча с использованием Redis и BullMQ.
 *
 * ФАЗА 8C: Match Confirmation
 */

import { Injectable, Logger, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue, Worker, Job } from 'bullmq';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';
import {
  MatchConfirmation,
  ConfirmationResult,
  ConfirmationStatus,
  CONFIRMATION_TTL_SECONDS,
  CONFIRMATION_TIMEOUT_SECONDS,
} from '../models';
import { GameStatus } from '@prisma/client';

const CONFIRMATION_QUEUE_NAME = 'match-confirmation';
const CONFIRMATION_PREFIX = 'mm:confirm:';

interface ConfirmationTimeoutJobData {
  gameId: string;
  player1Id: string;
  player2Id: string;
}

@Injectable()
export class MatchConfirmationService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(MatchConfirmationService.name);
  private worker: Worker<ConfirmationTimeoutJobData> | null = null;

  constructor(
    @InjectQueue(CONFIRMATION_QUEUE_NAME)
    private readonly confirmationQueue: Queue<ConfirmationTimeoutJobData>,
    private readonly redis: RedisService,
    private readonly prisma: PrismaService,
  ) {}

  async onModuleInit() {
    await this.startWorker();
  }

  async onModuleDestroy() {
    await this.stopWorker();
  }

  /**
   * Запуск worker для обработки timeout
   */
  async startWorker(): Promise<void> {
    this.worker = new Worker<ConfirmationTimeoutJobData>(
      CONFIRMATION_QUEUE_NAME,
      async (job: Job<ConfirmationTimeoutJobData>) => {
        await this.handleConfirmationTimeout(job.data);
      },
      {
        connection: {
          host: process.env.REDIS_HOST || 'localhost',
          port: parseInt(process.env.REDIS_PORT || '6379', 10),
          password: process.env.REDIS_PASSWORD,
        },
        concurrency: 5,
      },
    );

    this.worker.on('completed', (job) => {
      this.logger.debug(`Confirmation timeout job ${job.id} completed`);
    });

    this.worker.on('failed', (job, error) => {
      this.logger.error(`Confirmation timeout job ${job?.id} failed: ${error}`);
    });

    this.logger.log('Match confirmation worker started');
  }

  /**
   * Остановка worker
   */
  async stopWorker(): Promise<void> {
    if (this.worker) {
      await this.worker.close();
      this.worker = null;
    }
  }

  /**
   * Создать подтверждение матча
   */
  async createConfirmation(gameId: string, player1Id: string, player2Id: string): Promise<void> {
    const key = this.getConfirmationKey(gameId);
    const now = new Date();
    const expiresAt = new Date(now.getTime() + CONFIRMATION_TTL_SECONDS * 1000);

    const confirmation: MatchConfirmation = {
      gameId,
      player1Id,
      player2Id,
      player1Status: ConfirmationStatus.PENDING,
      player2Status: ConfirmationStatus.PENDING,
      expiresAt,
      createdAt: now,
    };

    // Сохраняем в Redis с TTL
    await this.redis.setJsonex(key, CONFIRMATION_TTL_SECONDS, confirmation);

    // Создаём delayed job для timeout
    await this.confirmationQueue.add(
      'timeout',
      { gameId, player1Id, player2Id },
      {
        jobId: `timeout:${gameId}`,
        delay: CONFIRMATION_TIMEOUT_SECONDS * 1000,
      },
    );

    this.logger.debug(`Created confirmation for game ${gameId}`);
  }

  /**
   * Принять матч
   */
  async acceptMatch(gameId: string, userId: string): Promise<ConfirmationResult> {
    const key = this.getConfirmationKey(gameId);
    const confirmation = await this.redis.getJson<MatchConfirmation>(key);

    if (!confirmation) {
      return {
        success: false,
        bothAccepted: false,
        status: ConfirmationStatus.TIMEOUT,
      };
    }

    // Проверяем, является ли пользователь участником
    if (confirmation.player1Id !== userId && confirmation.player2Id !== userId) {
      throw new Error('User is not a participant in this match');
    }

    // Проверяем статус
    const isPlayer1 = confirmation.player1Id === userId;
    const currentStatus = isPlayer1 ? confirmation.player1Status : confirmation.player2Status;

    if (currentStatus === ConfirmationStatus.ACCEPTED) {
      // Двойной accept - ок, просто возвращаем success
      return {
        success: true,
        bothAccepted: this.checkBothAccepted(confirmation),
        status: ConfirmationStatus.ACCEPTED,
      };
    }

    if (currentStatus !== ConfirmationStatus.PENDING) {
      // Уже decline или timeout
      return {
        success: false,
        bothAccepted: false,
        status: currentStatus,
      };
    }

    // Обновляем статус
    if (isPlayer1) {
      confirmation.player1Status = ConfirmationStatus.ACCEPTED;
    } else {
      confirmation.player2Status = ConfirmationStatus.ACCEPTED;
    }

    await this.redis.setJsonex(key, CONFIRMATION_TTL_SECONDS, confirmation);

    // Проверяем, оба ли приняли
    const bothAccepted = this.checkBothAccepted(confirmation);

    if (bothAccepted) {
      confirmation.player1Status = ConfirmationStatus.COMPLETED;
      confirmation.player2Status = ConfirmationStatus.COMPLETED;

      // Обновляем игру
      await this.startGame(gameId);

      // Удаляем подтверждение
      await this.redis.del(key);

      // Отменяем timeout job
      await this.cancelTimeoutJob(gameId);

      this.logger.log(`Both players accepted game ${gameId}`);
    }

    return {
      success: true,
      bothAccepted,
      status: bothAccepted ? ConfirmationStatus.COMPLETED : ConfirmationStatus.ACCEPTED,
    };
  }

  /**
   * Отклонить матч
   */
  async declineMatch(gameId: string, userId: string): Promise<ConfirmationResult> {
    const key = this.getConfirmationKey(gameId);
    const confirmation = await this.redis.getJson<MatchConfirmation>(key);

    if (!confirmation) {
      return {
        success: false,
        bothAccepted: false,
        status: ConfirmationStatus.TIMEOUT,
      };
    }

    // Проверяем, является ли пользователь участником
    if (confirmation.player1Id !== userId && confirmation.player2Id !== userId) {
      throw new Error('User is not a participant in this match');
    }

    // Обновляем статусы
    confirmation.player1Status = ConfirmationStatus.DECLINED;
    confirmation.player2Status = ConfirmationStatus.DECLINED;

    // Удаляем из Redis
    await this.redis.del(key);

    // Отменяем timeout job
    await this.cancelTimeoutJob(gameId);

    // Отменяем игру
    await this.cancelGame(gameId);

    // Удаляем подтверждение
    await this.redis.del(key);

    this.logger.log(`Player ${userId} declined game ${gameId}`);

    return {
      success: true,
      bothAccepted: false,
      status: ConfirmationStatus.DECLINED,
    };
  }

  /**
   * Обработка timeout подтверждения
   */
  private async handleConfirmationTimeout(data: ConfirmationTimeoutJobData): Promise<void> {
    const { gameId, player1Id, player2Id } = data;
    const key = this.getConfirmationKey(gameId);
    const confirmation = await this.redis.getJson<MatchConfirmation>(key);

    if (!confirmation) {
      // Уже обработано
      return;
    }

    // Определяем, кто не принял
    let timeoutUserId: string | undefined;

    if (
      confirmation.player1Status === ConfirmationStatus.PENDING &&
      confirmation.player2Status === ConfirmationStatus.ACCEPTED
    ) {
      timeoutUserId = player1Id;
    } else if (
      confirmation.player2Status === ConfirmationStatus.PENDING &&
      confirmation.player1Status === ConfirmationStatus.ACCEPTED
    ) {
      timeoutUserId = player2Id;
    }

    // Удаляем подтверждение
    await this.redis.del(key);

    // Отменяем игру
    await this.cancelGame(gameId);

    this.logger.log(
      `Confirmation timeout for game ${gameId}. Timeout user: ${timeoutUserId || 'both'}`,
    );
  }

  /**
   * Проверить, оба ли игрока приняли
   */
  private checkBothAccepted(confirmation: MatchConfirmation): boolean {
    return (
      confirmation.player1Status === ConfirmationStatus.ACCEPTED &&
      confirmation.player2Status === ConfirmationStatus.ACCEPTED
    );
  }

  /**
   * Запустить игру
   */
  private async startGame(gameId: string): Promise<void> {
    await this.prisma.game.update({
      where: { id: gameId },
      data: {
        status: GameStatus.LOBBY,
        startedAt: new Date(),
      },
    });

    this.logger.log(`Game ${gameId} started`);
  }

  /**
   * Отменить игру
   */
  private async cancelGame(gameId: string): Promise<void> {
    await this.prisma.game.update({
      where: { id: gameId },
      data: {
        status: GameStatus.ABORTED,
      },
    });

    this.logger.log(`Game ${gameId} cancelled`);
  }

  /**
   * Отменить timeout job
   */
  private async cancelTimeoutJob(gameId: string): Promise<void> {
    const job = await this.confirmationQueue.getJob(`timeout:${gameId}`);
    if (job) {
      await job.remove();
    }
  }

  /**
   * Получить подтверждение
   */
  async getConfirmation(gameId: string): Promise<MatchConfirmation | null> {
    const key = this.getConfirmationKey(gameId);
    return this.redis.getJson<MatchConfirmation>(key);
  }

  /**
   * Получить ключ подтверждения
   */
  private getConfirmationKey(gameId: string): string {
    return `${CONFIRMATION_PREFIX}${gameId}`;
  }

  /**
   * Проверить статус подтверждения для пользователя
   */
  async getUserConfirmationStatus(
    gameId: string,
    userId: string,
  ): Promise<{ canAccept: boolean; status: ConfirmationStatus }> {
    const confirmation = await this.getConfirmation(gameId);

    if (!confirmation) {
      return {
        canAccept: false,
        status: ConfirmationStatus.TIMEOUT,
      };
    }

    const isPlayer1 = confirmation.player1Id === userId;
    const userStatus = isPlayer1 ? confirmation.player1Status : confirmation.player2Status;

    return {
      canAccept: userStatus === ConfirmationStatus.PENDING,
      status: userStatus,
    };
  }
}
