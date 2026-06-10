/**
 * Matchmaking Subscription Resolver
 *
 * GraphQL подписки для событий матчмейкинга.
 *
 * ФАЗА 8D: Matchmaking Subscriptions
 */

import { Resolver, Args, Subscription } from '@nestjs/graphql';
import { Injectable, Logger } from '@nestjs/common';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';
import { MatchFoundResponse } from '../dto';

// Создаём простой PubSub для локальных подписок
class PubSub {
  private readonly eventMap = new Map<string, Set<Function>>();
  private readonly queueMap = new Map<string, Array<(value: any) => void>>();

  publish(eventName: string, payload: any): void {
    const subscriptions = this.eventMap.get(eventName);
    if (subscriptions) {
      subscriptions.forEach((callback) => callback(payload));
    }
  }

  asyncIterator<T>(eventName: string): AsyncIterator<T> {
    if (!this.eventMap.has(eventName)) {
      this.eventMap.set(eventName, new Set());
    }
    if (!this.queueMap.has(eventName)) {
      this.queueMap.set(eventName, []);
    }

    const eventSet = this.eventMap.get(eventName)!;
    const queue = this.queueMap.get(eventName)!;

    const pullQueue: Array<(value: IteratorResult<T>) => void> = [];
    let pushValue: T | null = null;
    let done = false;

    const callback = (payload: T) => {
      if (pullQueue.length > 0) {
        const resolve = pullQueue.shift()!;
        resolve({ value: payload, done: false });
      } else {
        pushValue = payload;
      }
    };

    eventSet.add(callback);

    return {
      next(): Promise<IteratorResult<T>> {
        return new Promise((resolve) => {
          if (done) {
            resolve({ value: undefined, done: true });
            return;
          }

          if (pushValue !== null) {
            const value = pushValue;
            pushValue = null;
            resolve({ value, done: false });
          } else {
            pullQueue.push(resolve);
          }
        });
      },
      return(): Promise<IteratorResult<T>> {
        done = true;
        eventSet.delete(callback);
        // Очищаем очередь ожидания
        while (pullQueue.length > 0) {
          const resolve = pullQueue.shift()!;
          resolve({ value: undefined, done: true });
        }
        return Promise.resolve({ value: undefined, done: true });
      },
      throw(error?: any): Promise<IteratorResult<T>> {
        done = true;
        eventSet.delete(callback);
        return Promise.reject(error);
      },
    };
  }
}

const MATCH_FOUND_EVENT = 'matchFound';
const MATCH_TIMEOUT_EVENT = 'matchTimeout';
const QUEUE_UPDATED_EVENT = 'queueUpdated';

export interface MatchFoundPayload {
  gameId: string;
  player1Id: string;
  player2Id: string;
  player1Username: string;
  player2Username: string;
  player1Rating: number;
  player2Rating: number;
  mode: string;
  expiresAt: Date;
}

export interface MatchTimeoutPayload {
  gameId: string;
  userId: string;
  reason: 'timeout' | 'declined' | 'cancelled';
}

export interface QueueUpdatedPayload {
  mode: string;
  totalPlayers: number;
  estimatedWaitTime: number;
}

@Injectable()
export class MatchmakingPubSubService {
  private readonly logger = new Logger(MatchmakingPubSubService.name);
  private readonly pubSub = new PubSub();

  constructor(private readonly prisma: PrismaService) {}

  async publishMatchFound(
    gameId: string,
    player1Id: string,
    player2Id: string,
    mode: string,
    expiresAt: Date,
  ): Promise<void> {
    try {
      const [player1, player2] = await Promise.all([
        this.prisma.user.findUnique({
          where: { id: player1Id },
          select: { username: true },
        }),
        this.prisma.user.findUnique({
          where: { id: player2Id },
          select: { username: true },
        }),
      ]);

      if (!player1 || !player2) {
        this.logger.warn(`Cannot publish match found - users not found`);
        return;
      }

      const [stats1, stats2] = await Promise.all([
        this.prisma.userStats.findUnique({
          where: { userId: player1Id },
          select: { currentElo: true },
        }),
        this.prisma.userStats.findUnique({
          where: { userId: player2Id },
          select: { currentElo: true },
        }),
      ]);

      const payload: MatchFoundPayload = {
        gameId,
        player1Id,
        player2Id,
        player1Username: player1.username,
        player2Username: player2.username,
        player1Rating: stats1?.currentElo || 1200,
        player2Rating: stats2?.currentElo || 1200,
        mode,
        expiresAt,
      };

      this.pubSub.publish(MATCH_FOUND_EVENT, payload);
      this.logger.debug(`Published match found for game ${gameId}`);
    } catch (error) {
      this.logger.error(`Failed to publish match found: ${error}`);
    }
  }

  async publishMatchTimeout(
    gameId: string,
    userId: string,
    reason: 'timeout' | 'declined' | 'cancelled',
  ): Promise<void> {
    const payload: MatchTimeoutPayload = {
      gameId,
      userId,
      reason,
    };

    this.pubSub.publish(MATCH_TIMEOUT_EVENT, payload);
    this.logger.debug(
      `Published match timeout for game ${gameId}, user ${userId}, reason: ${reason}`,
    );
  }

  async publishQueueUpdated(
    mode: string,
    totalPlayers: number,
    estimatedWaitTime: number,
  ): Promise<void> {
    const payload: QueueUpdatedPayload = {
      mode,
      totalPlayers,
      estimatedWaitTime,
    };

    this.pubSub.publish(QUEUE_UPDATED_EVENT, payload);
  }

  asyncIterator(eventName: string): AsyncIterator<any> {
    return this.pubSub.asyncIterator(eventName as any);
  }
}

@Resolver(() => MatchFoundResponse)
export class MatchmakingSubscriptionResolver {
  constructor(private readonly matchmakingPubSub: MatchmakingPubSubService) {}

  @Subscription(() => MatchFoundResponse, {
    name: 'matchFound',
    filter: (payload: MatchFoundPayload, variables: { userId: string }) => {
      return payload.player1Id === variables.userId || payload.player2Id === variables.userId;
    },
    resolve: (payload: MatchFoundPayload, variables: { userId: string }) => {
      const isPlayer1 = payload.player1Id === variables.userId;

      return {
        gameId: payload.gameId,
        opponentId: isPlayer1 ? payload.player2Id : payload.player1Id,
        opponentUsername: isPlayer1 ? payload.player2Username : payload.player1Username,
        opponentRating: isPlayer1 ? payload.player2Rating : payload.player1Rating,
        mode: payload.mode,
        expiresAt: payload.expiresAt,
      };
    },
  })
  matchFound(@Args('userId') userId: string) {
    return this.matchmakingPubSub.asyncIterator('matchFound');
  }
}
