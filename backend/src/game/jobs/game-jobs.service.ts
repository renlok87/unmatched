/**
 * Game Jobs Service
 *
 * Сервис для постановки задач в очередь.
 */

import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';

export interface CombatJobData {
  readonly gameId: string;
  readonly attackerId: string;
  readonly defenderId: string;
  readonly attackCardId: string;
  readonly defenseCardId?: string;
}

export interface GameStatePersistJobData {
  readonly gameId: string;
  readonly sequenceNumber: number;
  readonly state: unknown;
}

@Injectable()
export class GameJobsService {
  private readonly logger = new Logger(GameJobsService.name);

  constructor(
    @InjectQueue('combat-resolution')
    private readonly combatQueue: Queue<CombatJobData>,
    @InjectQueue('game-state-persist')
    private readonly persistQueue: Queue<GameStatePersistJobData>,
  ) {}

  /**
   * Поставить задачу разрешения боя в очередь
   */
  async queueCombatResolution(data: CombatJobData): Promise<void> {
    const jobId = 'combat:' + data.gameId + ':' + data.attackerId + ':' + String(Date.now());
    await this.combatQueue.add('resolve', data, { jobId });

    this.logger.debug('Queued combat resolution for game ' + data.gameId);
  }

  /**
   * Поставить задачу сохранения состояния в очередь
   */
  async queueStatePersist(data: GameStatePersistJobData): Promise<void> {
    const jobId = 'persist:' + data.gameId + ':' + String(data.sequenceNumber);
    await this.persistQueue.add('persist', data, { jobId });

    this.logger.debug(
      'Queued state persist for game ' + data.gameId + ', seq ' + String(data.sequenceNumber),
    );
  }

  /**
   * Получить статистику очередей
   */
  async getQueueStats(): Promise<{
    combat: { waiting: number; active: number; completed: number; failed: number };
    persist: { waiting: number; active: number; completed: number; failed: number };
  }> {
    const [combatCounts, persistCounts] = await Promise.all([
      this.combatQueue.getJobCounts('waiting', 'active', 'completed', 'failed'),
      this.persistQueue.getJobCounts('waiting', 'active', 'completed', 'failed'),
    ]);

    return {
      combat: {
        waiting: combatCounts.waiting ?? 0,
        active: combatCounts.active ?? 0,
        completed: combatCounts.completed ?? 0,
        failed: combatCounts.failed ?? 0,
      },
      persist: {
        waiting: persistCounts.waiting ?? 0,
        active: persistCounts.active ?? 0,
        completed: persistCounts.completed ?? 0,
        failed: persistCounts.failed ?? 0,
      },
    };
  }
}
