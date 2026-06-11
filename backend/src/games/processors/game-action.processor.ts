import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Job } from 'bullmq';
import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../database/prisma.service';
import { GameActionType } from '../models/game-action.model';

interface GameActionJobData {
  id: string;
  gameId: string;
  sequenceNumber: number;
  type: GameActionType;
  playerId: string;
  timestamp: Date;
  metadata: Record<string, any>;
}

@Injectable()
@Processor('game-action')
export class GameActionProcessor extends WorkerHost {
  private readonly logger = new Logger(GameActionProcessor.name);

  constructor(private readonly prisma: PrismaService) {
    super();
  }

  async process(job: Job<GameActionJobData>): Promise<void> {
    const { id, gameId, sequenceNumber, type, playerId, timestamp, metadata } = job.data;

    try {
      await this.prisma.gameAction.upsert({
        where: {
          id,
        },
        update: {},
        create: {
          id,
          gameId,
          sequenceNumber,
          type: type as any,
          playerId,
          timestamp,
          payload: metadata as any,
        },
      });

      this.logger.debug(
        `Recorded game action ${id} for game ${gameId}, sequence ${sequenceNumber}`,
      );
    } catch (error) {
      this.logger.error(`Failed to record game action ${id}: ${error.message}`, error.stack);
      throw error;
    }
  }
}
