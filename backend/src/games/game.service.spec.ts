/** S09 P2: терминальный read авторитетен, даже если инвалидация кеша игры
 *  не прошла (сбой Redis при saveState FINISHED) — getGame сверяет живой
 *  cached-статус с БД (конвенция getCachedState), терминальный кеш
 *  иммутабелен и отдаётся напрямую. */
import { Test, TestingModule } from '@nestjs/testing';
import { NotFoundException } from '@nestjs/common';
import { GameService } from './game.service';
import { GameStatus } from './dto';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { GameInitializationService } from './services/game-initialization.service';
import { GameActionService } from './services/game-action.service';
import { GameSubscriptionService } from './game-subscription.service';
import { AiTurnService } from './services/ai-turn.service';
import type { GameResponse } from './models';

const fullRow = (overrides: Record<string, unknown> = {}) => ({
  id: 'g1',
  code: 'ABCDEF',
  status: 'FINISHED',
  mode: 'ONE_V_ONE',
  hostId: 'host',
  host: { id: 'host', username: 'Host', avatar: null },
  opponentId: 'opp',
  opponent: { id: 'opp', username: 'Opp', avatar: null },
  boardId: 'board1',
  boardState: null,
  createdAt: new Date('2026-01-01T00:00:00Z'),
  updatedAt: new Date('2026-01-02T00:00:00Z'),
  startedAt: new Date('2026-01-01T01:00:00Z'),
  endedAt: new Date('2026-01-02T00:00:00Z'),
  winnerId: 'host',
  version: 10,
  players: [
    { id: 'p1', userId: 'host', user: { id: 'host', username: 'Host', avatar: null }, heroId: 'h1', isReady: true, hasPassed: false, seatOrder: 0 },
    { id: 'p2', userId: 'opp', user: { id: 'opp', username: 'Opp', avatar: null }, heroId: 'h2', isReady: true, hasPassed: false, seatOrder: 1 },
  ],
  state: null,
  ...overrides,
});

const staleCache = (overrides: Record<string, unknown> = {}): GameResponse => ({
  id: 'g1',
  code: 'ABCDEF',
  status: 'IN_PROGRESS',
  mode: 'ONE_V_ONE',
  hostId: 'host',
  host: { id: 'host', userId: 'host', username: 'Host', avatar: null, isReady: true, hasPassed: false, seatOrder: 0, heroId: 'h1' },
  opponentId: 'opp',
  opponent: { id: 'opp', userId: 'opp', username: 'Opp', avatar: null, isReady: true, hasPassed: false, seatOrder: 1, heroId: 'h2' },
  boardId: 'board1',
  boardState: null,
  createdAt: new Date('2026-01-01T00:00:00Z'),
  updatedAt: new Date('2026-01-01T12:00:00Z'),
  startedAt: new Date('2026-01-01T01:00:00Z'),
  endedAt: null,
  winnerId: null,
  version: 9,
  players: [],
  phase: null,
  currentTurn: null,
  ...overrides,
}) as GameResponse;

describe('GameService getGame: терминальный read авторитетен при живом кеше', () => {
  let service: GameService;
  let prisma: PrismaService;
  let redis: RedisService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameService,
        {
          provide: PrismaService,
          useValue: {
            game: { findUnique: jest.fn(), findMany: jest.fn() },
            gamePlayer: { findUnique: jest.fn() },
            $transaction: jest.fn(),
          },
        },
        {
          provide: RedisService,
          useValue: { getJson: jest.fn(), setJsonex: jest.fn(), del: jest.fn() },
        },
        { provide: GameInitializationService, useValue: {} },
        { provide: GameActionService, useValue: { recordAction: jest.fn() } },
        { provide: GameSubscriptionService, useValue: { publishLobbyEvent: jest.fn() } },
      ],
    }).compile();

    service = module.get<GameService>(GameService);
    prisma = module.get(PrismaService);
    redis = module.get(RedisService);
  });

  it('stale IN_PROGRESS-кеш после FINISHED → ответ из БД и перезапись кеша', async () => {
    // инвалидация saveState не прошла: в кеше живой IN_PROGRESS (version 9),
    // строка уже FINISHED (version 10)
    (redis.getJson as jest.Mock).mockResolvedValue(staleCache());
    (prisma.game.findUnique as jest.Mock)
      .mockResolvedValueOnce({ status: 'FINISHED', version: 10 })
      .mockResolvedValueOnce(fullRow());

    const result = await service.getGame('g1');

    expect(result.status).toBe('FINISHED');
    expect(result.winnerId).toBe('host');
    expect(result.endedAt).toBeInstanceOf(Date);
    expect(prisma.game.findUnique).toHaveBeenCalledTimes(2);
    // просроченная запись перезаписана терминальным ответом
    expect(redis.setJsonex).toHaveBeenCalledWith('game:g1', 300, expect.objectContaining({ status: 'FINISHED' }));
  });

  it('терминальный FINISHED-кеш отдаётся без похода в БД (иммутабелен)', async () => {
    (redis.getJson as jest.Mock).mockResolvedValue(staleCache({ status: 'FINISHED', winnerId: 'host', endedAt: new Date() }));

    const result = await service.getGame('g1');

    expect(result.status).toBe('FINISHED');
    expect(prisma.game.findUnique).not.toHaveBeenCalled();
    expect(redis.setJsonex).not.toHaveBeenCalled();
  });

  it('живой IN_PROGRESS-кеш с совпадающим статусом/version отдаётся из кеша', async () => {
    (redis.getJson as jest.Mock).mockResolvedValue(staleCache());
    (prisma.game.findUnique as jest.Mock).mockResolvedValue({ status: 'IN_PROGRESS', version: 9 });

    const result = await service.getGame('g1');

    expect(result.status).toBe('IN_PROGRESS');
    // только сверка статуса, без полного include-read
    expect(prisma.game.findUnique).toHaveBeenCalledTimes(1);
    expect(redis.setJsonex).not.toHaveBeenCalled();
  });

  it('кеш живого статуса при удалённой строке → NotFound, а не призрак игры', async () => {
    (redis.getJson as jest.Mock).mockResolvedValue(staleCache());
    (prisma.game.findUnique as jest.Mock).mockResolvedValue(null);

    await expect(service.getGame('g1')).rejects.toThrow(NotFoundException);
  });
});

/** S09: myGames всегда читает авторитетный Postgres — list-кеш не читается и
 *  не пишется. Сверка ЭЛЕМЕНТОВ кеша с БД не видит появления новых членов:
 *  закешированный [] по фильтру FINISHED выглядел бы «свежим» и скрывал новый
 *  завершённый матч, если терминальный del в saveState не прошёл. Сходным
 *  образом конкурентный read, стартовавший до коммита, не должен иметь шанса
 *  репопулировать кеш. Legacy-инвалидация ключей games:list:* остаётся. */
describe('GameService myGames: авторитетный Postgres, list-кеш выключен', () => {
  let service: GameService;
  let prisma: PrismaService;
  let redis: RedisService;

  const liveRow = (overrides: Record<string, unknown> = {}) =>
    fullRow({ status: 'IN_PROGRESS', endedAt: null, winnerId: null, version: 9, ...overrides });

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameService,
        {
          provide: PrismaService,
          useValue: {
            game: { findUnique: jest.fn(), findMany: jest.fn() },
            gamePlayer: { findUnique: jest.fn() },
            $transaction: jest.fn(),
          },
        },
        {
          provide: RedisService,
          useValue: { getJson: jest.fn(), setJsonex: jest.fn(), del: jest.fn() },
        },
        { provide: GameInitializationService, useValue: {} },
        { provide: GameActionService, useValue: { recordAction: jest.fn() } },
        { provide: GameSubscriptionService, useValue: { publishLobbyEvent: jest.fn() } },
      ],
    }).compile();

    service = module.get<GameService>(GameService);
    prisma = module.get(PrismaService);
    redis = module.get(RedisService);
  });

  it('failed eviction: stale кеш [] по фильтру FINISHED игнорируется → новый завершённый матч возвращается', async () => {
    // до конца дуэли кеш по фильтру FINISHED был []; saveState закоммитил
    // FINISHED, но терминальный del Redis не прошёл — ключ живёт 60с
    (redis.getJson as jest.Mock).mockResolvedValue([]);
    (prisma.game.findMany as jest.Mock).mockResolvedValue([fullRow()]);

    const result = await service.myGames('host', { status: GameStatus.FINISHED });

    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('FINISHED');
    expect(result[0].winnerId).toBe('host');
    expect(redis.getJson).not.toHaveBeenCalled();
    expect(prisma.game.findMany).toHaveBeenCalledTimes(1);
  });

  it('фильтрованный IN_PROGRESS-список отражает терминальный коммит (игра покинула фильтр)', async () => {
    (prisma.game.findMany as jest.Mock).mockResolvedValue([]);

    const result = await service.myGames('host', { status: GameStatus.IN_PROGRESS });

    expect(result).toEqual([]);
    expect(prisma.game.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          status: GameStatus.IN_PROGRESS,
          OR: [{ hostId: 'host' }, { opponentId: 'host' }],
        }),
      }),
    );
  });

  it('нефильтрованный список отражает терминальный коммит FINISHED', async () => {
    (prisma.game.findMany as jest.Mock).mockResolvedValue([fullRow()]);

    const result = await service.myGames('host');

    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('FINISHED');
    expect(result[0].endedAt).toBeInstanceOf(Date);
  });

  it('limit пробрасывается в запрос (семантика фильтров сохранена)', async () => {
    (prisma.game.findMany as jest.Mock).mockResolvedValue([]);

    await service.myGames('host', { limit: 5 });

    expect(prisma.game.findMany).toHaveBeenCalledWith(
      expect.objectContaining({ take: 5 }),
    );
  });

  it('конкурентный read не может репопулировать list-кеш: ни getJson, ни setJsonex', async () => {
    // read стартовал до терминального коммита и вернул живую игру —
    // устаревший ответ уходит только вызывающему, в кеш не попадает
    (redis.getJson as jest.Mock).mockResolvedValue(null);
    (prisma.game.findMany as jest.Mock).mockResolvedValue([liveRow()]);

    const result = await service.myGames('host');

    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('IN_PROGRESS');
    expect(redis.getJson).not.toHaveBeenCalled();
    expect(redis.setJsonex).not.toHaveBeenCalled();
  });
});

/** GD-039: старт VS_AI обязан дать боту отыграть, если ход (или выбор) его —
 *  иначе при боте-первом матч виснет до действия человека, а человек в чужой
 *  фазе легальных мутаций не имеет. Триггер — fire-and-forget drain. */
describe('GameService startGame: VS_AI триггерит дрейн бота', () => {
  const lobbyRow = (mode: string) => ({
    id: 'g1',
    code: 'ABCDEF',
    status: 'LOBBY',
    mode,
    hostId: 'host',
    opponentId: mode === 'VS_AI' ? 'ai' : 'opp',
    boardId: 'board1',
    players: [
      { id: 'p1', userId: 'host', heroId: 'h1', isReady: true, seatOrder: 0 },
      { id: 'p2', userId: mode === 'VS_AI' ? 'ai' : 'opp', heroId: 'h2', isReady: true, seatOrder: 1 },
    ],
  });

  async function buildService() {
    const aiTurn = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameService,
        {
          provide: PrismaService,
          useValue: {
            game: {
              findUnique: jest.fn(),
              update: jest.fn(),
              updateMany: jest.fn().mockResolvedValue({ count: 0 }),
            },
            gamePlayer: { findUnique: jest.fn(), findMany: jest.fn() },
            $transaction: jest.fn(),
            $queryRaw: jest.fn().mockResolvedValue([]),
          },
        },
        {
          provide: RedisService,
          useValue: { getJson: jest.fn().mockResolvedValue(null), setJsonex: jest.fn(), del: jest.fn() },
        },
        { provide: GameInitializationService, useValue: { initializeGameState: jest.fn().mockResolvedValue(undefined) } },
        { provide: GameActionService, useValue: { recordAction: jest.fn().mockResolvedValue('id') } },
        { provide: GameSubscriptionService, useValue: { publishLobbyEvent: jest.fn() } },
        { provide: AiTurnService, useValue: aiTurn },
      ],
    }).compile();
    return { service: module.get(GameService), aiTurn, prisma: module.get(PrismaService), redis: module.get(RedisService) };
  }

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('успешный старт VS_AI → maybeRunAiTurns(g1) вызван', async () => {
    const { service, aiTurn, prisma } = await buildService();
    (prisma.game.findUnique as jest.Mock)
      // 1: начальный include-read (лобби, все готовы); статус внутри транзакции
      //    читается через tx (см. $transaction-мок ниже)
      .mockResolvedValueOnce(lobbyRow('VS_AI'))
      // 2: getGame после старта — полный include-read
      .mockResolvedValueOnce(fullRow({ status: 'IN_PROGRESS', endedAt: null, winnerId: null, mode: 'VS_AI' }));
    (prisma.$transaction as jest.Mock).mockImplementation(async (run: (tx: unknown) => unknown) =>
      run({
        $queryRaw: async () => [],
        game: { findUnique: async () => ({ status: 'LOBBY' }), update: async () => ({}) },
        gamePlayer: { findMany: async () => lobbyRow('VS_AI').players },
      }),
    );
    (prisma.gamePlayer.findMany as jest.Mock).mockResolvedValue(lobbyRow('VS_AI').players);

    const result = await service.startGame('g1', 'host');

    expect(result.status).toBe('IN_PROGRESS');
    expect(aiTurn.maybeRunAiTurns).toHaveBeenCalledWith('g1');
  });

  it('обычный ONE_V_ONE старт → дрейн бота НЕ вызван', async () => {
    const { service, aiTurn, prisma } = await buildService();
    (prisma.game.findUnique as jest.Mock)
      .mockResolvedValueOnce(lobbyRow('ONE_V_ONE'))
      .mockResolvedValueOnce(fullRow());
    (prisma.$transaction as jest.Mock).mockImplementation(async (run: (tx: unknown) => unknown) =>
      run({
        $queryRaw: async () => [],
        game: { findUnique: async () => ({ status: 'LOBBY' }), update: async () => ({}) },
        gamePlayer: { findMany: async () => lobbyRow('ONE_V_ONE').players },
      }),
    );
    (prisma.gamePlayer.findMany as jest.Mock).mockResolvedValue(lobbyRow('ONE_V_ONE').players);

    await service.startGame('g1', 'host');

    expect(aiTurn.maybeRunAiTurns).not.toHaveBeenCalled();
  });
});
