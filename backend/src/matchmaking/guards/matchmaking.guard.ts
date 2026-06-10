import { Injectable, CanActivate, ExecutionContext, ForbiddenException } from '@nestjs/common';
import { PrismaService } from '../../database/prisma.service';
import { PenaltyService } from '../services/penalty.service';
import { GameStatus } from '@prisma/client';

@Injectable()
export class MatchmakingGuard implements CanActivate {
  constructor(
    private readonly prisma: PrismaService,
    private readonly penaltyService: PenaltyService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const user = request.user;

    if (!user || !user.userId) {
      throw new ForbiddenException('Not authenticated');
    }

    const penaltyInfo = await this.penaltyService.getPenaltyInfo(user.userId);
    if (!penaltyInfo.canJoinQueue) {
      throw new ForbiddenException(
        `You are temporarily banned from matchmaking until ${penaltyInfo.tempBanUntil}`,
      );
    }

    const activeGame = await this.prisma.game.findFirst({
      where: {
        OR: [
          {
            hostId: user.userId,
            status: { in: [GameStatus.PENDING, GameStatus.LOBBY, GameStatus.IN_PROGRESS] },
          },
          {
            opponentId: user.userId,
            status: { in: [GameStatus.PENDING, GameStatus.LOBBY, GameStatus.IN_PROGRESS] },
          },
        ],
      },
    });

    if (activeGame) {
      throw new ForbiddenException(
        `You are already in game ${activeGame.id}. Finish or leave it first.`,
      );
    }

    return true;
  }
}
