import { CanActivate, ExecutionContext, Injectable } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { UserRole } from '@prisma/client';
import { GqlExecutionContext } from '@nestjs/graphql';

/**
 * Guard для защиты эндпоинтов, доступных только администраторам
 */
@Injectable()
export class AdminGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    // Проверяем, является ли это GraphQL запрос
    const gqlContext = GqlExecutionContext.create(context);
    const request = gqlContext.getContext()?.req;

    // Если это GraphQL, берем user из контекста
    let user;
    if (request) {
      user = request.user;
    } else {
      // Пробуем через HTTP context (для REST)
      const httpContext = context.switchToHttp();
      const httpRequest = httpContext.getRequest();
      user = httpRequest?.user;
    }

    if (!user) {
      return false;
    }

    // Администраторы имеют полный доступ
    if (user.role === UserRole.ADMIN) {
      return true;
    }

    return false;
  }
}

/**
 * Guard для защиты эндпоинтов, доступных администраторам и модераторам
 */
@Injectable()
export class ModeratorGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    // Проверяем, является ли это GraphQL запрос
    const gqlContext = GqlExecutionContext.create(context);
    const request = gqlContext.getContext()?.req;

    // Если это GraphQL, берем user из контекста
    let user;
    if (request) {
      user = request.user;
    } else {
      // Пробуем через HTTP context (для REST)
      const httpContext = context.switchToHttp();
      const httpRequest = httpContext.getRequest();
      user = httpRequest?.user;
    }

    if (!user) {
      return false;
    }

    // Администраторы и модераторы имеют доступ
    if (user.role === UserRole.ADMIN || user.role === UserRole.MODERATOR) {
      return true;
    }

    return false;
  }
}
