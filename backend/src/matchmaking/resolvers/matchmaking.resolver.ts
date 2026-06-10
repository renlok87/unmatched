/**
 * Matchmaking Resolver
 *
 * GraphQL API для матчмейкинга.
 *
 * ФАЗА 8D: Matchmaking API
 */

import { Resolver, Mutation, Query, Args, Context } from '@nestjs/graphql';
import { UseGuards, ForbiddenException, NotFoundException, Logger } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { QueueManagerService } from '../services/queue-manager.service';
import { MatchConfirmationService } from '../services/match-confirmation.service';
import { PenaltyService } from '../services/penalty.service';
import { GameSanityService } from '../services/game-sanity.service';
import { MatchmakingMetricsService } from '../services/matchmaking-metrics.service';
import { MatchmakingGuard } from '../guards/matchmaking.guard';
import { JoinQueueDto } from '../dto';
import { GameMode } from '../../games/dto/create-game.dto';
import { QueueStatusResponse, PenaltyInfoDto } from '../dto';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { PrismaService } from '../../database/prisma.service';
import { GameStatus } from '@prisma/client';
import type { UserPayload } from '../models/user-payload.model';

@Resolver()
export class MatchmakingResolver {
  private readonly logger = new Logger(MatchmakingResolver.name);

  constructor(
    private readonly queueManager: QueueManagerService,
    private readonly confirmationService: MatchConfirmationService,
    private readonly penaltyService: PenaltyService,
    private readonly gameSanity: GameSanityService,
    private readonly distributedLock: DistributedLockService,
    private readonly prisma: PrismaService,
    private readonly metricsService: MatchmakingMetricsService,
  ) {}

  /**
   * Войти в очередь
   */
  @Mutation(() => QueueStatusResponse)
  @UseGuards(MatchmakingGuard)
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async joinQueue(
    @Args('input') input: JoinQueueDto,
    @CurrentUser() user: UserPayload,
  ): Promise<QueueStatusResponse> {
    const lockKey = `mm:join:${user.userId}`;
    const lockTTL = 5000;

    return await this.distributedLock.withLockOptions(
      lockKey,
      async () => {
        const rating = await this.getUserRating(user.userId);

        const alreadyInQueue = await this.queueManager.isInQueue(user.userId, input.mode);
        if (alreadyInQueue) {
          await this.queueManager.removeFromQueue(user.userId, input.mode);
        }

        const result = await this.queueManager.addToQueue(
          user.userId,
          rating,
          input.mode,
          input.heroPref,
        );

        this.metricsService.recordJoin(input.mode);

        const positionInfo = await this.queueManager.getPositionInfo(user.userId, input.mode);

        return {
          inQueue: true,
          mode: input.mode,
          position: result.position,
          totalPlayers: await this.queueManager.getQueueSize(input.mode),
          estimatedWaitTime: positionInfo?.estimatedWaitTime || 0,
          joinedAt: new Date(),
        };
      },
      { ttl: lockTTL, retryCount: 0, retryDelay: 0 },
    );
  }

  /**
   * Выйти из очереди
   */
@Mutation(() => Boolean)
  @UseGuards(MatchmakingGuard)
  async leaveQueue(
    @Args('mode', { type: () => String }) mode: GameMode,
    @CurrentUser() user: UserPayload,
  ): Promise<boolean> {
    const lockKey = `mm:leave:${user.userId}`;
    const lockTTL = 3000;

    return await this.distributedLock.withLockOptions(
      lockKey,
      async () => {
        const removed = await this.queueManager.removeFromQueue(user.userId, mode);
        if (removed) {
          this.metricsService.recordLeave(mode);
        }
        return removed;
      },
      { ttl: lockTTL, retryCount: 0, retryDelay: 0 },
    );
  }

  /**
   * Выйти из всех очередей
   */
  @Mutation(() => Boolean)
  @UseGuards(MatchmakingGuard)
  async leaveAllQueues(@CurrentUser() user: UserPayload): Promise<boolean> {
    const lockKey = `mm:leaveAll:${user.userId}`;
    const lockTTL = 3000;

    return await this.distributedLock.withLockOptions(
      lockKey,
      async () => {
        const modes = await this.queueManager.removeFromAllQueues(user.userId);
        return modes.length > 0;
      },
      { ttl: lockTTL, retryCount: 0, retryDelay: 0 },
    );
  }

  /**
   * Принять матч
   */
@Mutation(() => Boolean)
  async acceptMatch(
    @Args('gameId', { type: () => String }) gameId: string,
    @CurrentUser() user: UserPayload,
  ): Promise<boolean> {
    const lockKey = `mm:accept:${gameId}:${user.userId}`;
    const lockTTL = 5000;

    return await this.distributedLock.withLockOptions(
      lockKey,
      async () => {
        const canJoin = await this.penaltyService.canJoinQueue(user.userId);

        if (!canJoin) {
          throw new ForbiddenException('You are temporarily banned from matchmaking');
        }

        const result = await this.confirmationService.acceptMatch(gameId, user.userId);

        if (!result.success) {
          if (result.status === 'TIMEOUT') {
            throw new NotFoundException('Match confirmation has expired');
          }
          throw new ForbiddenException('Cannot accept match');
        }

        if (result.success) {
          this.metricsService.recordMatchAccepted(gameId);
        }

        return result.bothAccepted;
      },
      { ttl: lockTTL, retryCount: 0, retryDelay: 0 },
    );
  }

  /**
   * Отклонить матч
   */
@Mutation(() => Boolean)
  async declineMatch(
    @Args('gameId', { type: () => String }) gameId: string,
    @CurrentUser() user: UserPayload,
  ): Promise<boolean> {
    // Проверяем статус
    const status = await this.confirmationService.getUserConfirmationStatus(gameId, user.userId);

    if (status.status === 'TIMEOUT') {
      throw new NotFoundException('Match confirmation has expired');
    }

    if (!status.canAccept) {
      throw new ForbiddenException('Cannot decline match');
    }

    const result = await this.confirmationService.declineMatch(gameId, user.userId);
    await this.penaltyService.recordDecline(user.userId);

    if (result.success) {
      this.metricsService.recordMatchDeclined(gameId);
    }

    return result.success;
  }

  /**
   * Получить статус очереди
   */
@Query(() => QueueStatusResponse)
  async queueStatus(
    @Args('mode', { type: () => String }) mode: GameMode,
    @CurrentUser() user: UserPayload,
  ): Promise<QueueStatusResponse> {
    const inQueue = await this.queueManager.isInQueue(user.userId, mode);

    if (!inQueue) {
      return {
        inQueue: false,
        mode,
        totalPlayers: await this.queueManager.getQueueSize(mode),
        estimatedWaitTime: 0,
      };
    }

    const positionInfo = await this.queueManager.getPositionInfo(user.userId, mode);

    return {
      inQueue: true,
      mode,
      position: positionInfo?.position,
      totalPlayers: await this.queueManager.getQueueSize(mode),
      estimatedWaitTime: positionInfo?.estimatedWaitTime || 0,
    };
  }

  /**
   * Получить статус всех очередей
   */
  @Query(() => String)
  async allQueueStatus(): Promise<string> {
    const stats = await this.queueManager.getAllQueueStats();
    return JSON.stringify(stats, null, 2);
  }

  /**
   * Получить информацию о штрафах
   */
  @Query(() => PenaltyInfoDto)
  async penaltyInfo(@CurrentUser() user: UserPayload): Promise<PenaltyInfoDto> {
    const info = await this.penaltyService.getPenaltyInfo(user.userId);

    return {
      canJoinQueue: info.canJoinQueue,
      declineCount: info.declineCount,
      tempBanUntil: info.tempBanUntil,
      penaltyElo: info.penaltyElo,
      reason: info.tempBanUntil
        ? `Too many declines. Ban expires at ${info.tempBanUntil}`
        : undefined,
    };
  }

  @Query(() => String)
  async metrics(): Promise<string> {
    const queueStats = await this.queueManager.getAllQueueStats();
    this.metricsService.updateQueueSizes(queueStats);
    return JSON.stringify(this.metricsService.getMetrics(), null, 2);
  }

  /**
   * Получить рейтинг пользователя
   */
  private async getUserRating(userId: string): Promise<number> {
    try {
      const stats = await this.prisma.userStats.findUnique({
        where: { userId },
        select: { currentElo: true },
      });

      return stats?.currentElo ?? 1200;
    } catch (error) {
      this.logger.error(`Failed to get user rating: ${error}`);
      return 1200;
    }
  }
}
