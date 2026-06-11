/**
 * Game Action Performance Tests
 *
 * Performance тесты для игровых действий в Unmatched.
 * Измеряют время выполнения критических операций:
 * - Выполнение игровых действий
 * - Сохранение состояния
 * - Публикация подписок
 * - Валидация правил
 *
 * Целевые метрики (p95):
 * - Простое действие (pass): < 50ms
 * - Сложное действие (attack): < 100ms
 * - Сохранение состояния: < 30ms
 * - Публикация события: < 20ms
 */

import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import { AppModule } from '../../src/app.module';
import { PrismaService } from '../../src/database/prisma.service';
import { RedisService } from '../../src/redis/redis.service';
import { GameActionExecutorService } from '../../src/game-engine/services/game-action-executor.service';
import { GameStateService } from '../../src/games/game-state.service';
import { GameSubscriptionService } from '../../src/games/game-subscription.service';
import { GamePhase } from '../../src/games/dto';
import type { GameState } from '../../src/game-engine/models';

/**
 * Вспомогательная функция для измерения времени выполнения
 */
const measureTime = async <T>(fn: () => Promise<T>): Promise<{ result: T; duration: number }> => {
  const start = performance.now();
  const result = await fn();
  const duration = performance.now() - start;
  return { result, duration };
};

/**
 * Создаёт тестовое состояние игры
 */
const createTestGameState = (gameId: string, playerId: string): GameState => ({
  gameId,
  sequenceNumber: 0,
  phase: GamePhase.ACTION_MANEUVER,
  turnCount: 1,
  currentTurnPlayerId: playerId,
  players: [
    {
      userId: playerId,
      heroId: 'test-hero',
      health: 10,
      maxHealth: 10,
      fighterIds: ['fighter-1'],
      isAlive: true,
    },
    {
      userId: 'opponent-id',
      heroId: 'opponent-hero',
      health: 10,
      maxHealth: 10,
      fighterIds: ['fighter-2'],
      isAlive: true,
    },
  ],
  fighters: [
    {
      id: 'fighter-1',
      ownerId: playerId,
      heroId: 'test-hero',
      name: 'Test Fighter',
      type: 'hero',
      health: 10,
      maxHealth: 10,
      position: { x: 5, y: 5 },
      effects: [],
      hasSidekick: false,
    },
    {
      id: 'fighter-2',
      ownerId: 'opponent-id',
      heroId: 'opponent-hero',
      name: 'Opponent Fighter',
      type: 'hero',
      health: 10,
      maxHealth: 10,
      position: { x: 10, y: 10 },
      effects: [],
      hasSidekick: false,
    },
  ],
  decks: {},
  discardPiles: {},
  handZones: {},
  boardState: {
    boardId: 'test-board',
    width: 20,
    height: 20,
    doors: {},
    obstacles: [],
    fog: {},
  },
  metadata: {
    lastActionAt: new Date(),
    lastActionBy: 'system',
    version: 1,
  },
});

describe('Game Action Performance', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let redis: RedisService;
  let actionExecutor: GameActionExecutorService;
  let gameStateService: GameStateService;
  let gameSubscriptionService: GameSubscriptionService;

  let authToken: string;
  let testUserId: string;
  let testGameId: string;

  // Результаты измерений
  const measurements: Record<string, number[]> = {};

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        forbidNonWhitelisted: true,
        transform: true,
      }),
    );
    await app.init();

    prisma = app.get<PrismaService>(PrismaService);
    redis = app.get<RedisService>(RedisService);
    actionExecutor = app.get<GameActionExecutorService>(GameActionExecutorService);
    gameStateService = app.get<GameStateService>(GameStateService);
    gameSubscriptionService = app.get<GameSubscriptionService>(GameSubscriptionService);

    // Создаём тестового пользователя
    const registerMutation = `
      mutation Register($input: RegisterDto!) {
        register(input: $input) {
          accessToken
          user {
            id
          }
        }
      }
    `;

    const response = await request(app.getHttpServer())
      .post('/graphql')
      .send({
        query: registerMutation,
        variables: {
          input: {
            email: `perf-${Date.now()}@example.com`,
            username: `perf-${Date.now()}`,
            password: 'TestPassword123!',
          },
        },
      });

    authToken = response.body.data.register.accessToken;
    testUserId = response.body.data.register.user.id;
    testGameId = `perf-game-${Date.now()}`;
  });

  afterAll(async () => {
    await prisma.user.deleteMany({
      where: { email: { contains: '@example.com' } },
    });
    await app.close();
  });

  afterEach(async () => {
    await redis.flushDb();
  });

  describe('Выполнение игровых действий', () => {
    it('pass действие выполняется < 50ms (p95)', async () => {
      const durations: number[] = [];
      const iterations = 20;

      for (let i = 0; i < iterations; i++) {
        const state = createTestGameState(testGameId, testUserId);

        const { duration } = await measureTime(async () => {
          return actionExecutor.executePass(
            { gameId: testGameId },
            { userId: testUserId, gameId: testGameId, currentState: state },
          );
        });

        durations.push(duration);
      }

      // Сортируем и находим p95
      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['pass'] = durations;

      console.log(`Pass performance (p95): ${p95.toFixed(2)}ms`);
      console.log(`Pass min: ${durations[0].toFixed(2)}ms, max: ${durations[durations.length - 1].toFixed(2)}ms`);

      // p95 должен быть < 50ms
      expect(p95).toBeLessThan(50);
    });

    it('endTurn действие выполняется < 50ms (p95)', async () => {
      const durations: number[] = [];
      const iterations = 20;

      for (let i = 0; i < iterations; i++) {
        const state = createTestGameState(testGameId, testUserId);

        const { duration } = await measureTime(async () => {
          return actionExecutor.executeEndTurn(
            { gameId: testGameId },
            { userId: testUserId, gameId: testGameId, currentState: state },
          );
        });

        durations.push(duration);
      }

      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['endTurn'] = durations;

      console.log(`EndTurn performance (p95): ${p95.toFixed(2)}ms`);

      expect(p95).toBeLessThan(50);
    });

    it('moveFighter действие выполняется < 100ms (p95)', async () => {
      const durations: number[] = [];
      const iterations = 20;

      for (let i = 0; i < iterations; i++) {
        const state = createTestGameState(testGameId, testUserId);

        const { duration } = await measureTime(async () => {
          return actionExecutor.executeMoveFighter(
            { gameId: testGameId, fighterId: 'fighter-1', x: 6, y: 5 },
            { userId: testUserId, gameId: testGameId, currentState: state },
          );
        });

        durations.push(duration);
      }

      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['moveFighter'] = durations;

      console.log(`MoveFighter performance (p95): ${p95.toFixed(2)}ms`);

      expect(p95).toBeLessThan(100);
    });

    it('toggleDoor действие выполняется < 50ms (p95)', async () => {
      const durations: number[] = [];
      const iterations = 20;

      for (let i = 0; i < iterations; i++) {
        const state = createTestGameState(testGameId, testUserId);

        const { duration } = await measureTime(async () => {
          return actionExecutor.executeToggleDoor(
            { gameId: testGameId, x: 5, y: 5 },
            { userId: testUserId, gameId: testGameId, currentState: state },
          );
        });

        durations.push(duration);
      }

      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['toggleDoor'] = durations;

      console.log(`ToggleDoor performance (p95): ${p95.toFixed(2)}ms`);

      expect(p95).toBeLessThan(50);
    });
  });

  describe('Сохранение состояния', () => {
    it('сохранение состояния в Redis выполняется < 30ms (p95)', async () => {
      const durations: number[] = [];
      const iterations = 30;

      for (let i = 0; i < iterations; i++) {
        const state = createTestGameState(`${testGameId}-${i}`, testUserId);

        const { duration } = await measureTime(async () => {
          await gameStateService.saveState(state.gameId, state);
        });

        durations.push(duration);
      }

      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['saveState'] = durations;

      console.log(`SaveState performance (p95): ${p95.toFixed(2)}ms`);

      expect(p95).toBeLessThan(30);
    });

    it('загрузка состояния из Redis выполняется < 20ms (p95)', async () => {
      // Предварительно сохраняем состояние
      const state = createTestGameState(testGameId, testUserId);
      await gameStateService.saveState(testGameId, state);

      const durations: number[] = [];
      const iterations = 30;

      for (let i = 0; i < iterations; i++) {
        const { duration } = await measureTime(async () => {
          await gameStateService.loadState(testGameId);
        });

        durations.push(duration);
      }

      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['loadState'] = durations;

      console.log(`LoadState performance (p95): ${p95.toFixed(2)}ms`);

      expect(p95).toBeLessThan(20);
    });
  });

  describe('Публикация событий', () => {
    it('публикация события выполняется < 20ms (p95)', async () => {
      const state = createTestGameState(testGameId, testUserId);

      const durations: number[] = [];
      const iterations = 30;

      for (let i = 0; i < iterations; i++) {
        const { duration } = await measureTime(async () => {
          await gameSubscriptionService.publishGameUpdate(testGameId, 'TEST_EVENT', state);
        });

        durations.push(duration);
      }

      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['publishUpdate'] = durations;

      console.log(`PublishUpdate performance (p95): ${p95.toFixed(2)}ms`);

      expect(p95).toBeLessThan(20);
    });
  });

  describe('Распределённые блокировки', () => {
    it('приобретение и освобождение блокировки выполняется < 30ms (p95)', async () => {
      const DistributedLockService = (await import('../../src/common/services/distributed-lock.service')).DistributedLockService;
      const lockService = app.get<DistributedLockService>(DistributedLockService);

      const durations: number[] = [];
      const iterations = 20;

      for (let i = 0; i < iterations; i++) {
        const { duration } = await measureTime(async () => {
          await lockService.withLockOptions(`test-lock:${i}`, async () => {
            // Простая операция
            return true;
          }, { ttl: 5000, retryCount: 0 });
        });

        durations.push(duration);
      }

      durations.sort((a, b) => a - b);
      const p95Index = Math.floor(durations.length * 0.95);
      const p95 = durations[p95Index];

      measurements['distributedLock'] = durations;

      console.log(`DistributedLock performance (p95): ${p95.toFixed(2)}ms`);

      expect(p95).toBeLessThan(30);
    });
  });

  describe('Нагрузочное тестирование', () => {
    it('обработка 100 последовательных действий без задержек', async () => {
      const state = createTestGameState(testGameId, testUserId);
      await gameStateService.saveState(testGameId, state);

      const durations: number[] = [];

      for (let i = 0; i < 100; i++) {
        const { duration } = await measureTime(async () => {
          await actionExecutor.executePass(
            { gameId: testGameId },
            { userId: testUserId, gameId: testGameId, currentState: state },
          );
        });

        durations.push(duration);
      }

      const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length;
      const max = Math.max(...durations);

      console.log(`100 sequential passes - avg: ${avg.toFixed(2)}ms, max: ${max.toFixed(2)}ms`);

      // Среднее время должно быть < 30ms
      expect(avg).toBeLessThan(30);
      // Максимальное время должно быть < 100ms
      expect(max).toBeLessThan(100);
    });

    it('конкурентные действия корректно обрабатываются', async () => {
      const state = createTestGameState(testGameId, testUserId);
      await gameStateService.saveState(testGameId, state);

      const concurrentActions = 10;
      const startTime = performance.now();

      const promises = Array.from({ length: concurrentActions }, (_, i) =>
        measureTime(async () => {
          try {
            return await actionExecutor.executePass(
              { gameId: testGameId },
              { userId: testUserId, gameId: testGameId, currentState: state },
            );
          } catch (e) {
            // Некоторые действия могут завершиться с ошибкой из-за race conditions
            return null;
          }
        }),
      );

      const results = await Promise.all(promises);
      const totalDuration = performance.now() - startTime;

      const successful = results.filter((r) => r.result?.success).length;

      console.log(
        `Concurrent actions: ${concurrentActions}, Successful: ${successful}, Total time: ${totalDuration.toFixed(2)}ms`,
      );

      // Хотя бы половина должна выполниться успешно
      expect(successful).toBeGreaterThan(concurrentActions / 2);
      // Общее время должно быть пропорционально concurrency
      expect(totalDuration).toBeLessThan(concurrentActions * 50);
    });
  });

  describe('Отчёт о производительности', () => {
    it('генерирует отчёт по всем измерениям', () => {
      console.log('\n=== Performance Report ===');

      const report = Object.entries(measurements).map(([name, durations]) => {
        durations.sort((a, b) => a - b);
        const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length;
        const p50 = durations[Math.floor(durations.length * 0.5)];
        const p95 = durations[Math.floor(durations.length * 0.95)];
        const p99 = durations[Math.floor(durations.length * 0.99)];
        const min = durations[0];
        const max = durations[durations.length - 1];

        return { name, avg, min, max, p50, p95, p99 };
      });

      console.table(report);

      // Проверяем, что все p95 метрики в допустимых пределах
      report.forEach((metric) => {
        const limit = metric.name === 'moveFighter' ? 100 : 50;
        expect(metric.p95).toBeLessThan(limit);
      });
    });
  });
});
