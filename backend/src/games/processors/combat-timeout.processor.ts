/**
 * CombatTimeoutProcessor
 *
 * BullMQ Processor для обработки задач auto-resolve combat.
 * Запускается автоматически при старте приложения.
 */

import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { CombatTimeoutService } from '../services/combat-timeout.service';

/**
 * Данные для задачи auto-resolve
 */
export interface AutoResolveJobData {
  gameId: string;
  attackSequenceNumber: number;
}

/**
 * Результат auto-resolve
 */
export interface AutoResolveResult {
  success: boolean;
  resolvedSequenceNumber: number;
  reason: string;
}

/**
 * Processor для очереди combat-timeout
 * Обрабатывает задачи автоматического разрешения боя
 */
@Processor('combat-timeout')
export class CombatTimeoutProcessor extends WorkerHost {
  private readonly logger = new Logger(CombatTimeoutProcessor.name);

  constructor(private readonly combatTimeoutService: CombatTimeoutService) {
    super();
  }

  /**
   * Обработчик задачи auto-resolve
   */
  async process(job: Job<AutoResolveJobData>): Promise<AutoResolveResult> {
    const { gameId, attackSequenceNumber } = job.data;

    this.logger.debug(`Processing auto-resolve for game ${gameId}`);

    try {
      const result = await this.combatTimeoutService.processAutoResolve({
        gameId,
        attackSequenceNumber,
      });

      this.logger.debug(`Auto-resolve completed for game ${gameId}: ${result.reason}`);

      return result;
    } catch (error) {
      this.logger.error(`Error processing auto-resolve for game ${gameId}:`, error);

      throw error; // Перебрасываем ошибку для retry
    }
  }
}
