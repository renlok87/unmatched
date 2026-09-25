import { ExecutionContext, Injectable } from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';
import { ThrottlerGuard } from '@nestjs/throttler';

/** Минимальный структурный вид GQL-контекста, из которого throttler берёт req/res. */
type GqlContext = {
  req?: Record<string, unknown>;
  res?: Record<string, unknown>;
};

/** Поля Express-запроса, участвующие в вычислении трекера. */
type GqlThrottlerRequest = {
  user?: { id?: string };
  ip?: string;
  headers?: Record<string, string | undefined>;
};

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
    const ctx = GqlExecutionContext.create(context).getContext<GqlContext>();
    const req = (ctx?.req as Record<string, any> | undefined) ?? (ctx as Record<string, any>);
    const res = (ctx?.res as Record<string, any> | undefined) ?? (ctx as Record<string, any>);
    return { req, res };
  }

  protected getTracker(req: Record<string, any>): Promise<string> {
    const gqlReq = req as GqlThrottlerRequest;
    return Promise.resolve(
      gqlReq?.user?.id ?? gqlReq?.ip ?? gqlReq?.headers?.['x-forwarded-for'] ?? 'anonymous',
    );
  }
}
