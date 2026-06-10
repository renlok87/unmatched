/**
 * Matchmaking Module
 *
 * Модуль матчмейкинга с автоматическим поиском матчей,
 * двухфазным подтверждением и системой штрафов.
 *
 * ФАЗЫ 8A-8E: Queue Manager, Scheduler, Confirmation, API, Edge Cases
 */

import { Module, OnModuleInit } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { ScheduleModule } from '@nestjs/schedule';
import { QueueManagerService } from './services/queue-manager.service';
import { QueueSyncService } from './services/queue-sync.service';
import { MatchmakingSchedulerService } from './services/matchmaking-scheduler.service';
import { MatchConfirmationService } from './services/match-confirmation.service';
import { PenaltyService } from './services/penalty.service';
import { GameSanityService } from './services/game-sanity.service';
import { MatchmakingMetricsService } from './services/matchmaking-metrics.service';
import { MatchmakingResolver } from './resolvers/matchmaking.resolver';
import {
  MatchmakingSubscriptionResolver,
  MatchmakingPubSubService,
} from './resolvers/matchmaking.subscription';
import { MatchmakingGuard } from './guards/matchmaking.guard';
import { RedisModule } from '../redis/redis.module';
import { PrismaModule } from '../database/prisma.module';

@Module({
  imports: [
    // BullMQ queues для scheduler и confirmation timeout
    BullModule.registerQueue(
      {
        name: 'matchmaking-scheduler',
        defaultJobOptions: {
          attempts: 1,
          removeOnComplete: { age: 3600 },
          removeOnFail: { age: 7200 },
        },
      },
      {
        name: 'match-confirmation',
        defaultJobOptions: {
          attempts: 1,
          removeOnComplete: { age: 3600 },
          removeOnFail: { age: 7200 },
        },
      },
    ),
    // Scheduler для cron задач
    ScheduleModule.forRoot(),
    // Redis для distributed lock и pub/sub
    RedisModule,
    // Prisma для PostgreSQL
    PrismaModule,
  ],
  providers: [
    // Services
    QueueManagerService,
    QueueSyncService,
    MatchmakingSchedulerService,
    MatchConfirmationService,
    PenaltyService,
    GameSanityService,
    MatchmakingPubSubService,
    MatchmakingMetricsService,
    // Resolvers
    MatchmakingResolver,
    MatchmakingSubscriptionResolver,
    // Guards
    MatchmakingGuard,
  ],
  exports: [
    QueueManagerService,
    QueueSyncService,
    MatchmakingSchedulerService,
    MatchConfirmationService,
    PenaltyService,
    GameSanityService,
    MatchmakingPubSubService,
  ],
})
export class MatchmakingModule implements OnModuleInit {
  constructor(
    private readonly queueSync: QueueSyncService,
    private readonly gameSanity: GameSanityService,
    private readonly matchmakingScheduler: MatchmakingSchedulerService,
  ) {}

  async onModuleInit() {
    // Запускаем recovery при старте
    await this.gameSanity.recoverFromCrash();

    // Scheduler запускается автоматически в onModuleInit
  }
}
