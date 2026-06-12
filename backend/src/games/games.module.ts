import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';

// Resolvers
import { GameResolver } from './game.resolver';
import { GameActionsResolver } from './resolvers/game-actions.resolver';
import { GameSubscriptionResolver } from './resolvers/game-subscription.resolver';

// Services
import { GameService } from './game.service';
import { GameStateService } from './game-state.service';
import { GameSubscriptionService } from './game-subscription.service';
import { CombatTimeoutService } from './services/combat-timeout.service';
import { GameActionService } from './services/game-action.service';
import { GameInitializationService } from './services/game-initialization.service';
import { ReplayService } from './services/replay.service';
import { ReplayCompressorService } from './services/replay-compressor.service';
import { LeaderboardService } from './services/leaderboard.service';
import { StatsAggregatorService } from './services/stats-aggregator.service';

// Processors
import { CombatTimeoutProcessor } from './processors/combat-timeout.processor';
import { GameActionProcessor } from './processors/game-action.processor';

// DTO
import { ReplayData } from './models/replay.model';

// Validators
import { GameRulesValidator } from '../game-engine/validators/game-rules.validator';

// Guards
import {
  GameStatusGuard,
  GameInProgressGuard,
  GamePlayerGuard,
  GameTurnGuard,
  AttackPhaseGuard,
  ManeuverPhaseGuard,
  ActionPhaseGuard,
  CombatPhaseGuard,
  DefensePlayGuard,
  CombatResolveGuard,
} from './guards';

// Modules
import { PrismaModule } from '../database/prisma.module';
import { RedisModule } from '../redis/redis.module';
import { CommonModule } from '../common/common.module';
import { AuditModule } from '../audit/audit.module';
import { GameEngineModule } from '../game-engine/game-engine.module';
import { GameActionType } from './models/game-action.model';

/**
 * GamesModule
 *
 * Модуль управления играми в Unmatched.
 * Содержит resolvers, services и validators для игровой логики.
 */
@Module({
  imports: [
    PrismaModule,
    RedisModule,
    CommonModule, // Глобальный модуль для общих сервисов
    AuditModule, // Audit модуль для логирования действий
    GameEngineModule, // Game Engine для игровой логики
    // BullQueue для CombatTimeoutService
    BullModule.registerQueue({
      name: 'combat-timeout',
      defaultJobOptions: {
        attempts: 1,
        removeOnComplete: {
          count: 10,
        },
        removeOnFail: {
          count: 50,
        },
      },
    }),
    // BullQueue для GameActionService
    BullModule.registerQueue({
      name: 'game-action',
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
          age: 86400,
        },
      },
    }),
  ],
  providers: [
    // Resolvers
    GameResolver,
    GameActionsResolver,
    GameSubscriptionResolver,

    // Services
    GameService,
    GameStateService,
    GameSubscriptionService,
    CombatTimeoutService,
    GameActionService,
    GameInitializationService,
    ReplayService,
    ReplayCompressorService,
    LeaderboardService,
    StatsAggregatorService,

    // Processors
    CombatTimeoutProcessor,
    GameActionProcessor,

    // Validators
    GameRulesValidator,

    // Guards
    GameStatusGuard,
    GameInProgressGuard,
    GamePlayerGuard,
    GameTurnGuard,
    AttackPhaseGuard,
    ManeuverPhaseGuard,
    ActionPhaseGuard,
    CombatPhaseGuard,
    DefensePlayGuard,
    CombatResolveGuard,
  ],
  exports: [
    GameService,
    GameStateService,
    GameSubscriptionService,
    CombatTimeoutService,
    GameActionService,
    ReplayService,
    LeaderboardService,
    StatsAggregatorService,
    GameRulesValidator,
  ],
})
export class GamesModule {}
