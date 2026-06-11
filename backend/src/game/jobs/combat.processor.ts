/**
 * Combat Processor
 *
 * Обрабатывает задачи разрешения боя из очереди.
 */

import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import type { CombatJobData } from './game-jobs.service';

@Processor('combat-resolution')
export class CombatProcessor extends WorkerHost {
  private readonly logger = new Logger(CombatProcessor.name);

  async process(job: Job<CombatJobData>): Promise<void> {
    const { gameId, attackerId, defenderId, attackCardId, defenseCardId } = job.data;

    this.logger.debug(
      `Processing combat: game=${gameId}, attacker=${attackerId}, defender=${defenderId}`,
    );

    try {
      // TODO: Реализовать разрешение боя
      // 1. Загрузить состояние игры
      // 2. Применить модификаторы от способностей
      // 3. Вычислить урон
      // 4. Применить урон к бойцам
      // 5. Сохранить обновлённое состояние
      // 6. Отправить уведомление через WebSocket

      await new Promise((resolve) => setTimeout(resolve, 100));

      this.logger.debug(`Combat resolved for game ${gameId}`);
    } catch (error) {
      this.logger.error(`Error processing combat for game ${gameId}:`, error);
      throw error;
    }
  }
}
