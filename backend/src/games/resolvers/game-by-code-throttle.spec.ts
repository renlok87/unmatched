/** GD-029 security: gameByCode rate limiting — production-wired regression.
 *
 * @Throttle alone enforces nothing: the base ThrottlerGuard reads req/res via
 * switchToHttp, which is a dummy for GraphQL contexts. The resolver is now
 * guarded by GqlThrottlerGuard (per-user tracker from the JWT context).
 *
 * This spec does NOT re-declare its own throttler config: the exact options
 * object is extracted from the real AppModule's ThrottlerModule.forRoot
 * registration and the limit from the real @Throttle decorator on
 * GameResolver.gameByCode, then the actual 16th HTTP request is fired through
 * the booted Apollo stack. A wiring regression (guard unregistered, decorator
 * dropped, setHeaders flipping back on and breaking the GQL context) fails
 * the assertions below, not a copy of the implementation. */
import 'reflect-metadata';
import { ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { ThrottlerModule, getOptionsToken } from '@nestjs/throttler';
import { AppModule } from '../../app.module';
import { GameResolver } from '../game.resolver';
import { GameService } from '../game.service';
import { GameStateService } from '../game-state.service';
import { GameInitializationService } from '../services/game-initialization.service';
import { PrismaService } from '../../database/prisma.service';
import { RedisService } from '../../redis/redis.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { GameActionService } from '../services/game-action.service';
import { GamesModule } from '../games.module';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';
import { GqlThrottlerGuard } from '../guards/gql-throttler.guard';

/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-unsafe-assignment */

const query =
  'query ByCode($code: String!) { gameByCode(code: $code) { id code status } }';

/** The literal provider token ThrottlerModule.forRoot registers. */
const THROTTLER_MODULE_OPTIONS_TOKEN = getOptionsToken();

function productionThrottlerOptions(): any {
  const imports: any[] = Reflect.getMetadata('imports', AppModule) ?? [];
  for (const imported of imports) {
    for (const provider of imported?.providers ?? []) {
      if (provider?.provide === THROTTLER_MODULE_OPTIONS_TOKEN && provider?.useValue) {
        return provider.useValue;
      }
    }
  }
  throw new Error('AppModule no longer registers ThrottlerModule.forRoot');
}

function productionByCodeThrottle(): { limit: number; ttl: number } {
  const method = GameResolver.prototype.gameByCode;
  const limit = Reflect.getMetadata('THROTTLER:LIMITdefault', method);
  const ttl = Reflect.getMetadata('THROTTLER:TTLdefault', method);
  if (typeof limit !== 'number' || typeof ttl !== 'number') {
    throw new Error('gameByCode lost its @Throttle({ default: { limit, ttl } }) decorator');
  }
  return { limit, ttl };
}

describe('S08 GD-029: gameByCode throttle production wiring', () => {
  it('AppModule registers the GraphQL-safe ThrottlerModule (setHeaders: false)', () => {
    const options = productionThrottlerOptions();
    expect(options.setHeaders).toBe(false); // GQL contexts carry no express res
    expect(Array.isArray(options.throttlers)).toBe(true);
    expect(options.throttlers.length).toBeGreaterThan(0);
  });

  it('gameByCode is guarded by GqlAuthGuard + GqlThrottlerGuard and declares its cap', () => {
    const guards: any[] = Reflect.getMetadata('__guards__', GameResolver.prototype.gameByCode);
    expect(guards).toContain(GqlAuthGuard);
    expect(guards).toContain(GqlThrottlerGuard);

    const { limit, ttl } = productionByCodeThrottle();
    expect(limit).toBeGreaterThan(0);
    expect(ttl).toBeGreaterThan(0);
    expect(limit).toBeLessThanOrEqual(15); // anti room-enumeration cap
  });

  it('GamesModule registers GqlThrottlerGuard as a provider', () => {
    const providers: any[] = Reflect.getMetadata('providers', GamesModule) ?? [];
    const names = new Set(
      providers.map((p) => (typeof p === 'function' ? p : p?.provide)),
    );
    expect(names.has(GqlThrottlerGuard)).toBe(true);
  });
});

describe('S08 GD-029: gameByCode excessive-lookup throttle (production config)', () => {
  let app: import('@nestjs/common').INestApplication;
  let url: string;
  let limit: number;

  beforeAll(async () => {
    // The production ThrottlerModule options object feeds the test app - the
    // behavioral request loop below therefore runs against the real config.
    limit = productionByCodeThrottle().limit;
    const room = {
      id: 'g1', code: 'THROTTLE', status: 'LOBBY', mode: 'ONE_V_ONE',
      hostId: 'a', opponentId: null, boardId: 'b1', createdAt: new Date(),
      updatedAt: new Date(), version: 0, boardState: null, startedAt: null,
      endedAt: null, winnerId: null,
    };
    const prisma = {
      game: {
        findUnique: async ({ where }: any) =>
          where.code === 'THROTTLE'
            ? { ...room, host: { id: 'a', username: 'user-a', avatar: null },
                opponent: null, players: [], state: null }
            : null,
        findFirst: async () => null,
        count: async () => 0,
      },
      $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
      $queryRaw: async () => [],
    };
    const redis = {
      getJson: async () => null,
      setJsonex: async () => 'OK',
      del: async () => 1,
      subscribe: () => {},
      publish: async () => 1,
    };
    const module = await Test.createTestingModule({
      imports: [
        GraphQLModule.forRoot<ApolloDriverConfig>({
          driver: ApolloDriver, autoSchemaFile: true, csrfPrevention: false,
        }),
        ThrottlerModule.forRoot(productionThrottlerOptions()),
      ],
      providers: [GameResolver, GameService, GameInitializationService,
        GameStateService, GqlThrottlerGuard,
        { provide: PrismaService, useValue: prisma },
        { provide: RedisService, useValue: redis },
        { provide: GameActionService, useValue: { recordAction: async () => 'id' } },
        { provide: GameSubscriptionService, useValue: { publishLobbyEvent: async () => ({}),
          publishGameUpdate: async () => ({}) } },
      ],
    }).overrideGuard(GqlAuthGuard).useValue({ canActivate: (context: any) => {
      const req = context.getArgByIndex(2).req;
      const userId = req.headers['x-fixture-user'];
      if (!['a', 'b'].includes(userId)) return false;
      req.user = { id: userId };
      return true;
    } }).compile();
    app = module.createNestApplication();
    app.useLogger(false);
    app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
    await app.listen(0, '127.0.0.1');
    url = await app.getUrl();
  }, 15000);

  afterAll(async () => { await app?.close(); });

  async function byCode(viewer: string, code: string): Promise<any> {
    const response = await fetch(`${url}/graphql`, { method: 'POST', headers: {
      'content-type': 'application/json', 'x-fixture-user': viewer,
    }, body: JSON.stringify({ query, variables: { code } }) });
    return await response.json() as any;
  }

  it('the limit+1-th rapid lookup from one user is throttled, another user is unaffected', async () => {
    // User 'b' burns exactly the PRODUCTION-declared limit (from the
    // @Throttle decorator, not a local copy).
    for (let i = 0; i < limit; i++) {
      const ok = await byCode('b', 'THROTTLE');
      expect(ok.errors).toBeUndefined();
      expect(ok.data.gameByCode.id).toBe('g1');
    }

    const blocked = await byCode('b', 'THROTTLE');
    expect(blocked.errors).toBeDefined();
    expect(String(blocked.errors[0]?.message)).toMatch(/Throttler|Too Many Requests|429/i);

    // Per-USER tracker: the same endpoint from another user still works.
    const other = await byCode('a', 'THROTTLE');
    expect(other.errors).toBeUndefined();
    expect(other.data.gameByCode.id).toBe('g1');
  });
});
