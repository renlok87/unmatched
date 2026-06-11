/**
 * Game State Persist Processor
 *
 * Обрабатывает задачи сохранения состояния игры.
 */

import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import type { GameStatePersistJobData } from './game-jobs.service';

@Processor('game-state-persist')
export class GameStatePersistProcessor extends WorkerHost {
  private readonly logger = new Logger(GameStatePersistProcessor.name);

  async process(job: Job<GameStatePersistJobData>): Promise<void> {
    const { gameId, sequenceNumber, state } = job.data;

    this.logger.debug(`Persisting state: game=${gameId}, seq=${sequenceNumber}`);

    try {
      // TODO: Реализовать сохранение состояния
      // 1. Сохранить снепшот в БД (для истории/отмены)
      // 2. Обновить текущее состояние в Redis
      // 3. Обновить sequenceNumber

      await new Promise((resolve) => setTimeout(resolve, 50));

      this.logger.debug(`State persisted for game ${gameId}, seq ${sequenceNumber}`);
    } catch (error) {
      this.logger.error(`Error persisting state for game ${gameId}:`, error);
      throw error;
    }
  }
}
