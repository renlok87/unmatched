/**
 * GameStatusGuard
 *
 * Проверяет, что игра находится в нужном статусе.
 * Используется для защиты мутаций, которые доступны только во время игры.
 */

import { Injectable, CanActivate, ExecutionContext, ForbiddenException } from '@nestjs/common';
import { GameStatus } from '../dto';
import { PrismaService } from '../../database/prisma.service';

/**
 * Декоратор для указания требуемых статусов игры
 */
export const RequiredGameStatus =
  (...statuses: GameStatus[]) =>
  (target: any, propertyKey: string, descriptor: PropertyDescriptor) => {
    Reflect.defineMetadata('requiredGameStatus', statuses, descriptor.value);
  };

@Injectable()
export class GameStatusGuard implements CanActivate {
  constructor(private readonly prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    // Получаем gameId из аргументов мутации
    const args = context.getArgByIndex(1);
    const input = args?.input || args;

    const gameId = input?.gameId || args?.gameId;
    if (!gameId) {
      return false;
    }

    // Получаем requiredStatus из метаданных или используем дефолтный
    const requiredStatuses = this.getRequiredStatuses(context);

    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      select: { status: true },
    });

    if (!game) {
      throw new ForbiddenException(`Game ${gameId} not found`);
    }

    if (!requiredStatuses.includes(game.status as GameStatus)) {
      throw new ForbiddenException(
        `Game status is ${game.status}. Required: ${requiredStatuses.join(' or ')}`,
      );
    }

    return true;
  }

  /**
   * Получить требуемые статусы из метаданных или использовать дефолтные
   */
  protected getRequiredStatuses(context: ExecutionContext): GameStatus[] {
    const handler = context.getHandler();
    const metadata = Reflect.getMetadata('requiredGameStatus', handler);

    if (metadata && Array.isArray(metadata)) {
      return metadata as GameStatus[];
    }

    // Дефолтный список - только активные игры
    return [GameStatus.IN_PROGRESS];
  }
}

/**
 * Упрощённая версия guard с предустановленными статусами
 */
@Injectable()
export class GameInProgressGuard implements CanActivate {
  constructor(private readonly prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const args = context.getArgByIndex(1);
    const input = args?.input || args;

    const gameId = input?.gameId || args?.gameId;
    if (!gameId) {
      return false;
    }

    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      select: { status: true },
    });

    if (!game) {
      throw new ForbiddenException(`Game ${gameId} not found`);
    }

    if (game.status !== GameStatus.IN_PROGRESS) {
      throw new ForbiddenException(`Game status is ${game.status}. Required: IN_PROGRESS`);
    }

    return true;
  }
}
