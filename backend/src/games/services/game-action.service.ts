import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { v4 as uuidv4 } from 'uuid';
import { PrismaService } from '../../database/prisma.service';
import { GameAction, GameActionType, CreateGameActionDto } from '../models/game-action.model';

@Injectable()
export class GameActionService {
  private readonly logger = new Logger(GameActionService.name);
  private readonly QUEUE_NAME = 'game-action';

  constructor(
    @InjectQueue('game-action') private readonly gameActionQueue: Queue,
    private readonly prisma: PrismaService,
  ) {}

  async recordAction(dto: CreateGameActionDto): Promise<string> {
    const actionId = uuidv4();

    try {
      await this.gameActionQueue.add(
        'record-action',
        {
          id: actionId,
          ...dto,
          timestamp: new Date(),
        },
        {
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
      );

      return actionId;
    } catch (error) {
      this.logger.error(`Failed to add game action to queue: ${error.message}`);
      throw error;
    }
  }

  async recordActionBatch(actions: CreateGameActionDto[]): Promise<string[]> {
    const actionIds = actions.map(() => uuidv4());

    try {
      const jobs = actions.map((action, index) => ({
        name: 'record-action',
        data: {
          id: actionIds[index],
          ...action,
          timestamp: new Date(),
        },
        opts: {
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
      }));

      await this.gameActionQueue.addBulk(jobs);

      return actionIds;
    } catch (error) {
      this.logger.error(`Failed to add game actions to queue: ${error.message}`);
      throw error;
    }
  }

  async getActionsByGame(
    gameId: string,
    fromSequence?: number,
    toSequence?: number,
  ): Promise<GameAction[]> {
    const where: any = { gameId };

    if (fromSequence !== undefined || toSequence !== undefined) {
      where.sequenceNumber = {};
      if (fromSequence !== undefined) {
        where.sequenceNumber.gte = fromSequence;
      }
      if (toSequence !== undefined) {
        where.sequenceNumber.lte = toSequence;
      }
    }

    const actions = await this.prisma.gameAction.findMany({
      where,
      orderBy: { sequenceNumber: 'asc' },
    });

    return actions.map(this.mapToGameAction);
  }

  async getActionsByPlayer(playerId: string, gameId?: string): Promise<GameAction[]> {
    const where: any = { playerId };

    if (gameId) {
      where.gameId = gameId;
    }

    const actions = await this.prisma.gameAction.findMany({
      where,
      orderBy: { timestamp: 'desc' },
      take: 100,
    });

    return actions.map(this.mapToGameAction);
  }

  async getActionCount(gameId: string): Promise<number> {
    return this.prisma.gameAction.count({ where: { gameId } });
  }

  async cleanupOldActions(olderThanDays: number = 30): Promise<number> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - olderThanDays);

    const result = await this.prisma.gameAction.deleteMany({
      where: {
        timestamp: {
          lt: cutoffDate,
        },
      },
    });

    this.logger.log(`Cleaned up ${result.count} old game actions`);
    return result.count;
  }

  private mapToGameAction(prismaAction: any): GameAction {
    return {
      id: prismaAction.id,
      gameId: prismaAction.gameId,
      sequenceNumber: prismaAction.sequenceNumber,
      type: prismaAction.type as GameActionType,
      playerId: prismaAction.playerId,
      timestamp: prismaAction.timestamp,
      metadata: prismaAction.payload as Record<string, any>,
    };
  }
}
