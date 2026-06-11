import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../database/prisma.service';
import { GameActionService } from './game-action.service';
import { ReplayCompressorService } from './replay-compressor.service';
import { ReplayData, ReplaySummary, ReplayMetadata, ReplayAction } from '../models/replay.model';

@Injectable()
export class ReplayService {
  private readonly logger = new Logger(ReplayService.name);
  private readonly DEFAULT_TTL_DAYS = 30;

  constructor(
    private readonly prisma: PrismaService,
    private readonly gameActionService: GameActionService,
    private readonly compressor: ReplayCompressorService,
  ) {}

  async buildReplay(gameId: string): Promise<ReplayData> {
    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      include: {
        players: true,
      },
    });

    if (!game) {
      throw new Error(`Game ${gameId} not found`);
    }

    const actions = await this.gameActionService.getActionsByGame(gameId);
    const replayActions = actions.map(
      (action): ReplayAction => ({
        sequenceNumber: action.sequenceNumber,
        type: action.type,
        playerId: action.playerId || undefined,
        timestamp: action.timestamp.getTime(),
        data: action.metadata,
      }),
    );

    const metadata: ReplayMetadata = {
      boardId: game.boardId,
      hostId: game.hostId,
      opponentId: game.opponentId || '',
      hostHero: game.players.find((p) => p.userId === game.hostId)?.heroId || undefined,
      opponentHero: game.players.find((p) => p.userId === game.opponentId)?.heroId || undefined,
      gameMode: game.mode,
      startedAt: game.startedAt?.toISOString() || new Date().toISOString(),
      endedAt: game.endedAt?.toISOString() || new Date().toISOString(),
    };

    const duration = game.startedAt && game.endedAt
      ? game.endedAt.getTime() - game.startedAt.getTime()
      : 0;

    return {
      version: 1,
      gameId,
      duration,
      turnCount: replayActions.length,
      winnerId: game.winnerId || undefined,
      actions: replayActions,
      metadata,
    };
  }

  async saveReplay(
    gameId: string,
    replayData: ReplayData,
    isFavorite = false,
    ttlDays?: number,
  ): Promise<string> {
    const compressedData = await this.compressor.compress(JSON.stringify(replayData));

    const expiresAt = isFavorite
      ? null
      : new Date(Date.now() + (ttlDays || this.DEFAULT_TTL_DAYS) * 24 * 60 * 60 * 1000);

    const replay = await this.prisma.gameReplay.create({
      data: {
        gameId,
        data: Buffer.from(compressedData),
        duration: replayData.duration,
        turnCount: replayData.turnCount,
        winnerId: replayData.winnerId,
        isFavorite,
        expiresAt,
      },
    });

    this.logger.log(`Saved replay for game ${gameId}: ${replay.id}`);
    return replay.id;
  }

  async getReplay(gameId: string): Promise<ReplayData> {
    const replay = await this.prisma.gameReplay.findUnique({
      where: { gameId },
    });

    if (!replay) {
      throw new Error(`Replay for game ${gameId} not found`);
    }

    try {
      const decompressed = await this.compressor.decompress(Buffer.from(replay.data));
      const replayData = JSON.parse(decompressed);
      return replayData as ReplayData;
    } catch (error) {
      this.logger.error(`Failed to decompress replay ${replay.id}: ${error.message}`);
      throw new Error('Failed to load replay');
    }
  }

  async getReplayByReplayId(replayId: string): Promise<ReplayData> {
    const replay = await this.prisma.gameReplay.findUnique({
      where: { id: replayId },
    });

    if (!replay) {
      throw new Error(`Replay ${replayId} not found`);
    }

    try {
      const decompressed = await this.compressor.decompress(Buffer.from(replay.data));
      const replayData = JSON.parse(decompressed);
      return replayData as ReplayData;
    } catch (error) {
      this.logger.error(`Failed to decompress replay ${replayId}: ${error.message}`);
      throw new Error('Failed to load replay');
    }
  }

  async listReplays(
    userId?: string,
    isFavorite?: boolean,
    limit: number = 20,
    offset: number = 0,
  ): Promise<{ replays: ReplaySummary[]; total: number }> {
    const where: any = {};

    if (userId) {
      where.OR = [{ game: { hostId: userId } }, { game: { opponentId: userId } }];
    }

    if (isFavorite !== undefined) {
      where.isFavorite = isFavorite;
    }

    const [replays, total] = await Promise.all([
      this.prisma.gameReplay.findMany({
        where,
        include: {
          game: {
            select: {
              hostId: true,
              opponentId: true,
              createdAt: true,
            },
          },
        },
        orderBy: { createdAt: 'desc' },
        take: limit,
        skip: offset,
      }),
      this.prisma.gameReplay.count({ where }),
    ]);

    const summaries: ReplaySummary[] = replays.map((r) => ({
      id: r.id,
      gameId: r.gameId,
      duration: r.duration,
      turnCount: r.turnCount,
      winnerId: r.winnerId || undefined,
      createdAt: r.createdAt,
      isFavorite: r.isFavorite,
    }));

    return { replays: summaries, total };
  }

  async deleteReplay(replayId: string): Promise<void> {
    await this.prisma.gameReplay.delete({
      where: { id: replayId },
    });

    this.logger.log(`Deleted replay ${replayId}`);
  }

  async markAsFavorite(replayId: string, isFavorite: boolean): Promise<void> {
    await this.prisma.gameReplay.update({
      where: { id: replayId },
      data: {
        isFavorite,
        expiresAt: isFavorite ? null : new Date(Date.now() + this.DEFAULT_TTL_DAYS * 24 * 60 * 60 * 1000),
      },
    });

    this.logger.log(`Marked replay ${replayId} as favorite: ${isFavorite}`);
  }

  async cleanupExpiredReplays(): Promise<number> {
    const result = await this.prisma.gameReplay.deleteMany({
      where: {
        expiresAt: {
          lte: new Date(),
        },
        isFavorite: false,
      },
    });

    this.logger.log(`Cleaned up ${result.count} expired replays`);
    return result.count;
  }
}