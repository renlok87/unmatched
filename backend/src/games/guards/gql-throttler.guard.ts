import { ExecutionContext, Injectable } from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';
import { ThrottlerGuard } from '@nestjs/throttler';

/**
 * GraphQL-aware ThrottlerGuard.
 *
 * Базовый ThrottlerGuard достаёт req/res через switchToHttp — для GraphQL
 * ExecutionContext это заглушка (req === undefined), поэтому @Throttle на
 * резолвере без этого guard'а не просто не работает, а упал бы с TypeError.
 * Здесь запрос берётся из GQL-контекста, трекер — per-user (JWT), чтобы
 * клиенты за одним NAT/localhost не блокировали друг друга.
 */
@Injectable()
export class GqlThrottlerGuard extends ThrottlerGuard {
  protected getRequestResponse(context: ExecutionContext): {
    req: Record<string, any>;
    res: Record<string, any>;
  } {
    const ctx = GqlExecutionContext.create(context).getContext();
    return { req: ctx?.req ?? ctx, res: ctx?.res ?? ctx };
  }

  protected async getTracker(req: Record<string, any>): Promise<string> {
    return (
      req?.user?.id ?? req?.ip ?? req?.headers?.['x-forwarded-for'] ?? 'anonymous'
    );
  }
}
