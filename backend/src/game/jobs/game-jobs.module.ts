/**
 * Game Jobs Module
 *
 * Фоновые задачи для обработки игровых событий.
 * Использует BullMQ для асинхронной обработки.
 */

import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { GameJobsService } from './game-jobs.service';
import { CombatProcessor } from './combat.processor';
import { GameStatePersistProcessor } from './game-state-persist.processor';
import { RedisModule } from '../../redis/redis.module';

@Module({
  imports: [
    BullModule.registerQueue(
      {
        name: 'combat-resolution',
        defaultJobOptions: {
          attempts: 3,
          backoff: {
            type: 'exponential',
            delay: 1000,
          },
          removeOnComplete: {
            age: 3600,
          },
          removeOnFail: {
            age: 7200,
          },
        },
      },
      {
        name: 'game-state-persist',
        defaultJobOptions: {
          attempts: 5,
          backoff: {
            type: 'exponential',
            delay: 2000,
          },
          removeOnComplete: {
            age: 3600,
          },
          removeOnFail: {
            age: 7200,
          },
        },
      },
    ),
    RedisModule,
  ],
  providers: [GameJobsService, CombatProcessor, GameStatePersistProcessor],
  exports: [GameJobsService],
})
export class GameJobsModule {}
