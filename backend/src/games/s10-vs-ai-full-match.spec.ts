/** GD-039 Sol6: полный матч VS_AI на ЖИВОЙ изолированной S10-инфраструктуре.
 *  Настоящий Postgres (S10_TEST_DB_URL, порт 55435) + настоящий Redis
 *  (S10_TEST_REDIS_PORT, по умолчанию 6382), ПРОДАКШН-колоды King Arthur /
 *  Medusa (по 30 карт из сидов, развёрнутые по count), ЕДИНЫЙ bot-identity
 *  на оба матча. Оба сидa играют детерминированной greedy-политикой через
 *  РЕАЛЬНЫЕ executor/saveState/loadState/lock/pubsub — без моков игровой
 *  логики. Харнесс не дропает и не сбрасывает ничего: создаются и удаляются
 *  только собственные строки (users → game каскадом GamePlayer/GameState/
 *  GameAction/UserStats).
 *
 *  Известный зазор слайса: BullMQ-воркер combat-timeout в live-прогон не
 *  поднимается (упрощение харнесса): дедлайны боя бот планирует только в
 *  юнит-прогоне (ai-turn/s07 specs). Здесь бот-атака не ждёт 30с окно
 *  защиты — человек-политика отвечает немедленно. */
import { PrismaClient } from '@prisma/client';
import { randomUUID } from 'node:crypto';
import { GameStateService } from './game-state.service';
import { GameSubscriptionService } from './game-subscription.service';
import { RedisService } from '../redis/redis.service';
import { DistributedLockService } from '../common/services/distributed-lock.service';
import { GameInitializationService } from './services/game-initialization.service';
import { GameActionService } from './services/game-action.service';
import { AiTurnService, dispatchAiAction } from './services/ai-turn.service';
import { AiDecisionService } from '../game-engine/services/ai-decision.service';
import { GameActionExecutorService } from '../game-engine/services/game-action-executor.service';
import { CardEffectExecutorService } from '../game-engine/effects/card-effect-executor.service';
import { DeckManagementService } from '../game-engine/services/deck-management.service';
import { GameRulesValidator } from '../game-engine/validators/game-rules.validator';
import { CombatResolverService } from '../game-engine/engine/combat-resolver.service';
import { AdjacencyService } from '../game-engine/engine/adjacency.service';
import { ValueModifierService } from '../game-engine/engine/value-modifier.service';
import { HeroAbilityRegistry } from '../game-engine/abilities/hero-ability-registry';
import { GamePhase } from '../game-engine/models';
import { GameActionType } from './models/game-action.model';
import type { GameState } from './game-state.service';

const dbUrl = process.env.S10_TEST_DB_URL;
const redisPort = Number(process.env.S10_TEST_REDIS_PORT ?? 6382);
const describeLive = dbUrl ? describe : describe.skip;

/** Максимальный seq — страховка от бесконечного матча; реальный матч
 *  Arthur/Medusa на greedy закрывается далеко раньше (exhaustion + урон). */
const SEQ_HARD_CAP = 2000;

function buildStack(prisma: unknown, redis: RedisService) {
  const metrics = {
    measureServiceDuration: async (_a: string, _b: string, run: () => unknown) => run(),
    measureValidation: async (_a: string, run: () => unknown) => run(),
    incrementGameAction: () => {},
    incrementError: () => {},
  } as any;
  const adjacency = new AdjacencyService();
  const values = new ValueModifierService();
  const decks = new DeckManagementService();
  const registry = new HeroAbilityRegistry();
  const executor = new GameActionExecutorService(
    new GameRulesValidator(adjacency),
    new CombatResolverService(registry, metrics),
    undefined as any,
    values,
    adjacency,
    metrics,
    decks,
    new CardEffectExecutorService(values, metrics, adjacency, decks),
    registry,
  );
  const subscription = new GameSubscriptionService(redis);
  const stateService = new GameStateService(prisma as any, redis, subscription as any);
  const lock = new DistributedLockService(redis);
  // Журнал — та же BullMQ-форма записи (id/попытки), но persistence напрямую
  // в Prisma (мимикрия GameActionProcessor): recordAction остаётся async.
  const gameActionService = new GameActionService(
    {
      add: async (_name: string, data: any) => {
        await (prisma as PrismaClient).gameAction.create({
          data: {
            id: data.id,
            gameId: data.gameId,
            sequenceNumber: data.sequenceNumber,
            type: data.type,
            playerId: data.playerId,
            timestamp: data.timestamp,
            payload: data.metadata,
          },
        });
        return {} as any;
      },
    } as any,
    prisma as any,
  );
  const decision = new AiDecisionService(adjacency);
  const aiTurn = new AiTurnService(
    prisma as any,
    lock,
    stateService,
    subscription as any,
    executor,
    decision,
    undefined,
    gameActionService,
  );
  return { executor, subscription, stateService, lock, gameActionService, decision, aiTurn };
}

describeLive('S10 GD-039: полный матч VS_AI на живых Postgres+Redis', () => {
  let prisma: PrismaClient;
  let redis: RedisService;
  let stack: ReturnType<typeof buildStack>;
  let botId: string;
  let humanId: string;
  let boardId: string;
  const gameIds: string[] = [];

  beforeAll(async () => {
    prisma = new PrismaClient({ datasources: { db: { url: dbUrl! } } });
    redis = new RedisService({
      get: (key: string) =>
        key === 'REDIS_HOST' ? '127.0.0.1' : key === 'REDIS_PORT' ? String(redisPort) : undefined,
    } as any);
    await redis.onModuleInit();
    await (redis as any).client.ping();
    stack = buildStack(prisma, redis);
    await stack.subscription.onModuleInit();

    // единый bot-identity + один human-identity на весь прогон
    const suffix = randomUUID().slice(0, 8);
    botId = `s10-bot-${suffix}`;
    humanId = `s10-human-${suffix}`;
    await prisma.user.createMany({
      data: [
        { id: botId, email: `${botId}@test.invalid`, username: botId, password: 'test' },
        { id: humanId, email: `${humanId}@test.invalid`, username: humanId, password: 'test' },
      ],
    });
    const board = await prisma.board.findFirst({ orderBy: { createdAt: 'asc' } });
    if (!board) throw new Error('S10 test DB: нет досок — сиды не прогнаны');
    boardId = board.id;
  }, 60_000);

  afterAll(async () => {
    try {
      await prisma.game.deleteMany({ where: { id: { in: gameIds } } });
      await prisma.user.deleteMany({ where: { id: { in: [botId, humanId] } } });
    } finally {
      await stack?.subscription.onModuleDestroy();
      await redis?.onModuleDestroy();
      await prisma?.$disconnect();
    }
  }, 60_000);

  const createVsAiGame = async (
    humanHeroName: string,
    botHeroName: string,
    botSeat: 0 | 1 = 1,
  ): Promise<string> => {
    const [humanHero, botHero] = await Promise.all([
      prisma.hero.findFirst({ where: { name: humanHeroName } }),
      prisma.hero.findFirst({ where: { name: botHeroName } }),
    ]);
    if (!humanHero || !botHero) throw new Error(`S10 test DB: нет героев ${humanHeroName}/${botHeroName}`);
    const gameId = `s10-match-${randomUUID().slice(0, 8)}`;
    gameIds.push(gameId);
    await prisma.game.create({
      data: {
        id: gameId, hostId: humanId, opponentId: botId, boardId,
        mode: 'VS_AI', status: 'IN_PROGRESS', version: 1,
      },
    });
    // первым ходит seatOrder 0 (GD-016); бот-first матч → бот на seat 0
    await prisma.gamePlayer.createMany({
      data: [
        { gameId, userId: botId, heroId: botHero.id, isReady: true, seatOrder: botSeat },
        { gameId, userId: humanId, heroId: humanHero.id, isReady: true, seatOrder: (1 - botSeat) as 0 | 1 },
      ],
    });
    const init = new GameInitializationService(prisma as any, stack.stateService);
    await init.initializeGameState(gameId);
    return gameId;
  };

  /** Матч: бот — дрейном AiTurnService (реальный prisma/lock/save), человек —
   *  той же greedy-политикой через dispatchAiAction + реальный saveState. */
  const playMatch = async (gameId: string): Promise<GameState> => {
    let lastSeq = 0;
    for (let round = 0; round < SEQ_HARD_CAP; round++) {
      let state = await stack.stateService.loadState(gameId);
      if (state.sequenceNumber <= lastSeq && round > 0) {
        throw new Error(`seq не растёт (round ${round}, seq ${state.sequenceNumber}) — зависание`);
      }
      lastSeq = state.sequenceNumber;

      await stack.aiTurn.maybeRunAiTurns(gameId);
      state = await stack.stateService.loadState(gameId);
      if (state.phase === GamePhase.GAME_OVER) return state;

      const action = stack.decision.decide(state, humanId);
      if (action) {
        const { result, eventType } = await dispatchAiAction(stack.executor, action, {
          userId: humanId, gameId, currentState: state,
        });
        if (!result.success || !result.gameState) {
          throw new Error(`human ${action.kind} отклонён: ${result.error}`);
        }
        if (result.gameState.sequenceNumber <= state.sequenceNumber) {
          throw new Error(`human ${action.kind} без прогресса seq`);
        }
        await stack.stateService.saveState(gameId, result.gameState);
        const type = GameActionType[eventType as keyof typeof GameActionType];
        if (type) {
          await stack.gameActionService.recordAction({
            gameId, sequenceNumber: result.gameState.sequenceNumber, type,
            playerId: humanId, metadata: { action: `human:${action.kind}`, input: action },
          });
        }
        if (result.gameState.phase === GamePhase.GAME_OVER) {
          // зеркало game-actions.resolver: терминал журналируется отдельно
          await stack.gameActionService.recordAction({
            gameId, sequenceNumber: result.gameState.sequenceNumber,
            type: GameActionType.GAME_ENDED, playerId: humanId,
            metadata: { action: `human:${action.kind}`, winnerId: result.gameState.metadata.winnerId },
          });
        }
      }
      // action===null → ход бота/бой на стороне бота: следующий круг дрейна
    }
    throw new Error(`матч не завершился за ${SEQ_HARD_CAP} шагов`);
  };

  const assertMatchInvariants = async (gameId: string, final: GameState) => {
    // терминальное состояние реально в БД (не только в памяти)
    const row = await prisma.gameState.findUnique({ where: { gameId } });
    expect(row!.phase).toBe(GamePhase.GAME_OVER);
    expect(row!.sequenceNumber).toBe(final.sequenceNumber);
    const game = await prisma.game.findUnique({ where: { id: gameId } });
    expect(game!.status).toBe('FINISHED');
    expect(game!.winnerId).toBeDefined();
    expect([botId, humanId]).toContain(final.metadata.winnerId);
    expect(final.metadata.pendingEffects ?? []).toHaveLength(0);

    // консервация карт: 30 инстансов на сид (рука+колода+сброс), без дублей
    const seen = new Set<string>();
    for (const uid of [botId, humanId]) {
      const hand = final.handZones[uid]?.cards ?? [];
      const draw = final.decks[uid]?.drawPile ?? [];
      const discard = final.discardPiles[uid] ?? [];
      expect(hand.length + draw.length + discard.length).toBe(30);
      for (const c of [...hand, ...draw, ...discard]) {
        expect(seen.has(c.id)).toBe(false);
        seen.add(c.id);
      }
    }

    // журнал: ходы бота записаны, терминал есть, input бота приватен
    const actions = await prisma.gameAction.findMany({
      where: { gameId }, orderBy: { sequenceNumber: 'asc' },
    });
    const botActions = actions.filter((a) => a.playerId === botId);
    expect(botActions.length).toBeGreaterThan(5);
    expect(actions.some((a) => a.type === 'GAME_ENDED')).toBe(true);

    const humanView = await stack.stateService.getEventsSince(gameId, 0, humanId);
    const botView = await stack.stateService.getEventsSince(gameId, 0, botId);
    const humanBySeq = new Map(humanView.map((e) => [e.sequenceNumber, JSON.parse(e.payload)]));
    const botInputSeqs: number[] = [];
    for (const e of botView) {
      const payload = JSON.parse(e.payload);
      if (payload.input !== undefined && e.playerId === botId) botInputSeqs.push(e.sequenceNumber);
    }
    expect(botInputSeqs.length).toBeGreaterThan(0); // бот видит свой input
    for (const seq of botInputSeqs) {
      // человек на той же записи видит только action — без карт/секретов
      expect(humanBySeq.get(seq)).toBeDefined();
      expect(humanBySeq.get(seq)!.input).toBeUndefined();
      expect(humanBySeq.get(seq)!.action).toMatch(/^ai:/);
    }

    // GD-039/S10 catch-up живого матча: клиентский цикл eventsSince/hasMore
    // доставляет ВЕСЬ журнал ровно один раз (терминальная пара одного seq —
    // обе строки), терминал последним, приватность на каждой странице.
    // Число записей живого матча НЕ гарантировано >100 — это доказательство
    // end-to-end ДОСТАВКИ, а не multi-page/boundary-разреза. Доказательство
    // пагинации по границе — синтетическая 151-строчная регрессия в
    // s10-journal-pagination.spec.ts.
    // Residual: журнал пишется асинхронно ПОСЛЕ коммита состояния — запись
    // может закоммититься позже продвижения клиентского курсора. Журнал —
    // НЕ replay (16-network-contract.md §3): snapshot авторитетен, CUE
    // записей с seq <= применённого клиентом не проигрывается.
    const dbCount = await prisma.gameAction.count({ where: { gameId } });
    const PAGE = 100;
    const catchUp: Awaited<ReturnType<typeof stack.stateService.getEventsSince>> = [];
    let since = 0;
    for (let hop = 0; hop < 40; hop++) {
      const page = await stack.stateService.getEventsSince(gameId, since, humanId);
      catchUp.push(...page);
      if (page.length < PAGE) break;
      since = page[page.length - 1].sequenceNumber;
    }
    expect(catchUp).toHaveLength(dbCount); // весь журнал доставлен
    expect(new Set(catchUp.map((e) => `${e.sequenceNumber}:${e.type}`)).size).toBe(dbCount); // без дублей
    expect(catchUp[catchUp.length - 1].type).toBe('GAME_ENDED'); // терминал последним
    for (const e of catchUp) {
      // приватность на каждой странице: input бота не утекает человеку
      if (e.playerId === botId) expect(JSON.parse(e.payload).input).toBeUndefined();
    }
  };

  it('бот=Medusa vs человек=King Arthur: полный матч до GAME_OVER на реальной персистентности', async () => {
    const gameId = await createVsAiGame('King Arthur', 'Medusa');
    const final = await playMatch(gameId);
    await assertMatchInvariants(gameId, final);
  }, 240_000);

  it('бот=King Arthur vs человек=Medusa (обратные сиды, бот — seat 0 ходит первым, тот же bot-identity): полный матч', async () => {
    const gameId = await createVsAiGame('Medusa', 'King Arthur', 0);
    // bot-first стартап: инициализация отдала первый ход сиду 0 — боту
    const start = await stack.stateService.loadState(gameId);
    expect(start.currentTurnPlayerId).toBe(botId);
    const final = await playMatch(gameId);
    await assertMatchInvariants(gameId, final);
  }, 240_000);
});
