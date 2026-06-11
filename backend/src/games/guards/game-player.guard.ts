/**
 * GamePlayerGuard
 *
 * Проверяет, что пользователь является участником игры.
 * Используется для защиты мутаций, доступных только игрокам.
 */

import { Injectable, CanActivate, ExecutionContext, ForbiddenException } from '@nestjs/common';
import { PrismaService } from '../../database/prisma.service';

@Injectable()
export class GamePlayerGuard implements CanActivate {
  constructor(private readonly prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const ctx = context.getArgByIndex<{
      req?: { user?: { id?: string } };
    }>(2);

    const userId = ctx?.req?.user?.id;
    if (!userId) {
      return false;
    }

    // Получаем gameId из аргументов мутации
    const args = context.getArgByIndex(1);
    const input = args?.input || args;

    // gameId может быть на первом уровне или вложен в input
    const gameId = input?.gameId || args?.gameId;
    if (!gameId) {
      return false;
    }

    // Проверяем, что пользователь участвует в игре
    const player = await this.prisma.gamePlayer.findUnique({
      where: {
        gameId_userId: {
          gameId,
          userId,
        },
      },
    });

    if (!player) {
      throw new ForbiddenException(`You are not a participant in game ${gameId}`);
    }

    return true;
  }
}
