/**
 * CombatTimeoutService
 *
 * Сервис для автоматического разрешения боя при timeout защиты.
 * Использует BullMQ для отложенных задач.
 */

import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { GameStateService, GameState } from '../game-state.service';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { GamePhase } from '../dto';

/**
 * Конфигурация timeout'а для боя
 */
export interface CombatTimeoutConfig {
  /**
   * Время в секундах на ответ защитой (дефолт 30)
   */
  defenseTimeoutSeconds?: number;

  /**
   * Время в секундах на подтверждение разрешения (дефолт 10)
   */
  resolveTimeoutSeconds?: number;
}

/**
 * Данные для задачи auto-resolve
 */
interface AutoResolveJobData {
  gameId: string;
  attackSequenceNumber: number;
}

/**
 * Результат auto-resolve
 */
interface AutoResolveResult {
  success: boolean;
  resolvedSequenceNumber: number;
  reason: string;
}

@Injectable()
export class CombatTimeoutService implements OnModuleDestroy {
  private readonly logger = new Logger(CombatTimeoutService.name);

  /**
   * Имя очереди для задач timeout'а боя
   */
  private static readonly QUEUE_NAME = 'combat-timeout';

  /**
   * Дефолтное время на защиту (30 секунд)
   */
  private static readonly DEFAULT_DEFENSE_TIMEOUT = 30;

  /**
   * Дефолтное время на разрешение (10 секунд)
   */
  private static readonly DEFAULT_RESOLVE_TIMEOUT = 10;

  /**
   * Префикс для ключей scheduled задач в Redis
   */
  private readonly SCHEDULED_JOB_PREFIX = 'combat:scheduled:';

  constructor(
    @InjectQueue(CombatTimeoutService.QUEUE_NAME)
    private readonly combatTimeoutQueue: Queue<AutoResolveJobData>,
    private readonly gameStateService: GameStateService,
    private readonly distributedLockService: DistributedLockService,
  ) {}

  async onModuleDestroy(): Promise<void> {
    // Очистка при завершении модуля
    await this.combatTimeoutQueue.close();
  }

  /**
   * Запланировать auto-resolve через N секунд
   *
   * @param gameId - ID игры
   * @param delaySeconds - Задержка в секундах (дефолт 30)
   * @param attackSequenceNumber - Sequence number атаки для проверки актуальности
   */
  async scheduleAutoResolve(
    gameId: string,
    delaySeconds: number = CombatTimeoutService.DEFAULT_DEFENSE_TIMEOUT,
    attackSequenceNumber?: number,
  ): Promise<void> {
    // Проверяем, нет ли уже scheduled задачи
    const existingJobId = `${this.SCHEDULED_JOB_PREFIX}${gameId}`;

    // Удаляем старую задачу если есть
    try {
      const existingJob = await this.combatTimeoutQueue.getJob(existingJobId);
      if (existingJob) {
        await existingJob.remove();
        this.logger.debug(`Removed existing auto-resolve job for game ${gameId}`);
      }
    } catch {
      // Job не существует, игнорируем
    }

    // Добавляем задачу с задержкой
    const jobData: AutoResolveJobData = {
      gameId,
      attackSequenceNumber: attackSequenceNumber || Date.now(),
    };

    await this.combatTimeoutQueue.add('auto-resolve', jobData, {
      jobId: existingJobId,
      delay: delaySeconds * 1000, // BullMQ использует миллисекунды
      attempts: 1,
      removeOnComplete: {
        count: 10, // Хранить последние 10 завершённых задач
      },
      removeOnFail: {
        count: 50, // Хранить последние 50 failed задач
      },
    });

    this.logger.debug(`Scheduled auto-resolve for game ${gameId} in ${delaySeconds}s`);
  }

  /**
   * Отменить scheduled auto-resolve
   *
   * @param gameId - ID игры
   */
  async cancelAutoResolve(gameId: string): Promise<void> {
    const jobId = `${this.SCHEDULED_JOB_PREFIX}${gameId}`;

    try {
      const job = await this.combatTimeoutQueue.getJob(jobId);
      if (job) {
        await job.remove();
        this.logger.debug(`Cancelled auto-resolve for game ${gameId}`);
      }
    } catch {
      // Job не существует, игнорируем
    }
  }

  /**
   * Проверить, есть ли scheduled auto-resolve для игры
   *
   * @param gameId - ID игры
   */
  async hasScheduledAutoResolve(gameId: string): Promise<boolean> {
    const jobId = `${this.SCHEDULED_JOB_PREFIX}${gameId}`;

    try {
      const job = await this.combatTimeoutQueue.getJob(jobId);
      return job !== null;
    } catch {
      return false;
    }
  }

  /**
   * Получить время до auto-resolve в миллисекундах
   *
   * @param gameId - ID игры
   * @returns Время в мс или null если нет scheduled задачи
   */
  async getTimeUntilResolve(gameId: string): Promise<number | null> {
    const jobId = `${this.SCHEDULED_JOB_PREFIX}${gameId}`;

    try {
      const job = await this.combatTimeoutQueue.getJob(jobId);

      if (!job) {
        return null;
      }

      const delay = job.delay;
      if (!delay) {
        return null;
      }

      const processedOn = job.processedOn || job.timestamp;
      const remaining = processedOn + delay - Date.now();

      return Math.max(0, remaining);
    } catch {
      return null;
    }
  }

  /**
   * Processor для auto-resolve
   * Вызывается BullMQ когда наступает время timeout'а
   */
  async processAutoResolve(data: AutoResolveJobData): Promise<AutoResolveResult> {
    const { gameId, attackSequenceNumber } = data;

    this.logger.debug(`Processing auto-resolve for game ${gameId}`);

    try {
      // Получаем distributed lock для безопасности
      return await this.distributedLockService.withLock(`game:${gameId}`, async () => {
        const state = await this.gameStateService.loadState(gameId);

        // Проверяем, что всё еще в combat phase
        if (state.phase !== GamePhase.COMBAT) {
          this.logger.debug(`Game ${gameId} no longer in combat phase, skipping auto-resolve`);
          return {
            success: false,
            resolvedSequenceNumber: state.sequenceNumber,
            reason: 'Not in combat phase',
          };
        }

        // Проверяем sequence number если указан
        if (attackSequenceNumber && state.sequenceNumber > attackSequenceNumber) {
          this.logger.debug(`Game ${gameId} state changed, skipping auto-resolve`);
          return {
            success: false,
            resolvedSequenceNumber: state.sequenceNumber,
            reason: 'State changed',
          };
        }

        // Выполняем auto-resolve с defense = null
        const resolvedState = await this.performAutoResolve(state);

        // Сохраняем состояние
        await this.gameStateService.saveState(gameId, resolvedState);

        this.logger.debug(`Auto-resolved combat for game ${gameId}`);

        return {
          success: true,
          resolvedSequenceNumber: resolvedState.sequenceNumber,
          reason: 'Defense timeout',
        };
      });
    } catch (error) {
      this.logger.error(`Error processing auto-resolve for game ${gameId}:`, error);

      return {
        success: false,
        resolvedSequenceNumber: 0,
        reason: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Выполнить auto-resolve с defense = null
   *
   * @param state - Текущее состояние игры
   * @returns Новое состояние после разрешения боя
   */
  private async performAutoResolve(state: GameState): Promise<GameState> {
    // Создаём новое состояние
    const newState: GameState = {
      ...state,
      sequenceNumber: state.sequenceNumber + 1,
      phase: GamePhase.COMBAT_RESOLVE,
      metadata: {
        ...state.metadata,
        lastActionAt: new Date(),
        lastActionBy: state.currentTurnPlayerId,
      },
    };

    // TODO: Интегрировать с CombatResolverService для реального разрешения боя
    // Сейчас просто переходим к фазе разрешения
    // В полной реализации нужно:
    // 1. Применить урон от атаки
    // 2. Проверить defeat conditions
    // 3. Проверить win/loss conditions
    // 4. Обновить состояние бойцов

    return newState;
  }

  /**
   * Получить статистику очереди
   */
  async getQueueStats(): Promise<{
    active: number;
    waiting: number;
    completed: number;
    failed: number;
  }> {
    const [active, waiting, completed, failed] = await Promise.all([
      this.combatTimeoutQueue.getActiveCount(),
      this.combatTimeoutQueue.getWaitingCount(),
      this.combatTimeoutQueue.getCompletedCount(),
      this.combatTimeoutQueue.getFailedCount(),
    ]);

    return { active, waiting, completed, failed };
  }

  /**
   * Очистить завершённые задачи
   */
  async cleanCompletedJobs(): Promise<void> {
    await this.combatTimeoutQueue.clean(0, 100, 'completed');
    await this.combatTimeoutQueue.clean(0, 100, 'failed');
  }
}

/**
 * Worker для обработки задач auto-resolve
 * Регистрируется отдельно для обработки фоновой очереди
 */
export class CombatTimeoutWorker {
  private readonly logger = new Logger(CombatTimeoutWorker.name);
  private worker?: any;

  constructor(private readonly combatTimeoutService: CombatTimeoutService) {}

  /**
   * Запустить worker
   */
  async run(): Promise<void> {
    // В продакшене worker запускается как отдельный процесс
    // Для разработки можно использовать inline worker
    this.logger.log('CombatTimeoutWorker started');
  }

  /**
   * Остановить worker
   */
  async stop(): Promise<void> {
    if (this.worker) {
      await this.worker.close();
      this.logger.log('CombatTimeoutWorker stopped');
    }
  }
}
