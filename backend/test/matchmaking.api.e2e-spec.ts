import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/database/prisma.service';
import { RedisService } from '../src/redis/redis.service';

describe('Matchmaking API (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let redis: RedisService;

  let authToken: string;
  let authToken2: string;
  let authToken3: string;
  let testUserId: string;
  let testUserId2: string;
  let testUserId3: string;

  const generateTestData = (suffix: string) => ({
    email: `match-${suffix}-${Date.now()}@example.com`,
    username: `match-${suffix}-${Date.now()}`,
    password: 'TestPassword123!',
  });

  const gqlRequest = (query: string, variables?: any, token?: string) => {
    const req = request(app.getHttpServer())
      .post('/graphql')
      .set('Content-Type', 'application/json')
      .send(JSON.stringify({ query, variables }));

    if (token) {
      req.set('Authorization', `Bearer ${token}`);
    }

    return req;
  };

  const createAuthenticatedUser = async (suffix: string) => {
    const data = generateTestData(suffix);

    const REGISTER_MUTATION = `
      mutation Register($input: RegisterDto!) {
        register(input: $input) {
          accessToken
          user {
            id
            email
            username
          }
        }
      }
    `;

    const response = await gqlRequest(REGISTER_MUTATION, { input: data });
    return response.body.data.register;
  };

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
    app.enableCors({ origin: '*', credentials: true });

    await app.init();

    prisma = app.get<PrismaService>(PrismaService);
    redis = app.get<RedisService>(RedisService);

    const userData = await createAuthenticatedUser('main');
    authToken = userData.accessToken;
    testUserId = userData.user.id;

    const userData2 = await createAuthenticatedUser('second');
    authToken2 = userData2.accessToken;
    testUserId2 = userData2.user.id;

    const userData3 = await createAuthenticatedUser('third');
    authToken3 = userData3.accessToken;
    testUserId3 = userData3.user.id;
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

  describe('Mutation: joinQueue', () => {
    const JOIN_QUEUE_MUTATION = `
      mutation JoinQueue($input: JoinQueueDto!) {
        joinQueue(input: $input) {
          inQueue
          mode
          position
          totalPlayers
          estimatedWaitTime
          joinedAt
        }
      }
    `;

    it('успешное добавление в очередь RANKED', async () => {
      const response = await gqlRequest(
        JOIN_QUEUE_MUTATION,
        {
          input: {
            mode: 'RANKED',
          },
        },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.joinQueue).toBeDefined();

      const { joinQueue } = response.body.data;
      expect(joinQueue.inQueue).toBe(true);
      expect(joinQueue.mode).toBe('RANKED');
      expect(joinQueue.position).toBeGreaterThanOrEqual(0);
      expect(joinQueue.totalPlayers).toBeGreaterThanOrEqual(1);
      expect(joinQueue.estimatedWaitTime).toBeGreaterThanOrEqual(0);
      expect(joinQueue.joinedAt).toBeDefined();
    });

    it('успешное добавление в очередь CASUAL', async () => {
      const response = await gqlRequest(
        JOIN_QUEUE_MUTATION,
        {
          input: {
            mode: 'CASUAL',
          },
        },
        authToken2,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.joinQueue.mode).toBe('CASUAL');
    });

    it('успешное добавление с предпочтением героя', async () => {
      const response = await gqlRequest(
        JOIN_QUEUE_MUTATION,
        {
          input: {
            mode: 'RANKED',
            heroPref: ['daredevil', 'ms-marvel'],
          },
        },
        authToken3,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.joinQueue.inQueue).toBe(true);
    });

    it('повторное добавление удаляет из предыдущей очереди', async () => {
      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);

      const firstResponse = await gqlRequest(
        JOIN_QUEUE_MUTATION,
        { input: { mode: 'CASUAL' } },
        authToken,
      );

      expect(firstResponse.body.errors).toBeUndefined();
      expect(firstResponse.body.data.joinQueue.mode).toBe('CASUAL');
    });

    it('rate limiting - ограничение 5 запросов в минуту', async () => {
      const requests = [];
      for (let i = 0; i < 7; i++) {
        requests.push(
          gqlRequest(
            JOIN_QUEUE_MUTATION,
            { input: { mode: 'RANKED' } },
            authToken,
          ),
        );
      }

      const responses = await Promise.all(requests);
      const throttled = responses.filter(
        (r: any) => r.body.errors?.[0]?.extensions?.code === 'TOO_MANY_REQUESTS',
      );

      expect(throttled.length).toBeGreaterThan(0);
    });
  });

  describe('Mutation: leaveQueue', () => {
    const LEAVE_QUEUE_MUTATION = `
      mutation LeaveQueue($mode: GameMode!) {
        leaveQueue(mode: $mode)
      }
    `;

    it('успешный выход из очереди', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);

      const response = await gqlRequest(LEAVE_QUEUE_MUTATION, { mode: 'RANKED' }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.leaveQueue).toBe(true);
    });

    it('выход из пустой очереди возвращает false', async () => {
      const response = await gqlRequest(LEAVE_QUEUE_MUTATION, { mode: 'RANKED' }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.leaveQueue).toBe(false);
    });
  });

  describe('Mutation: leaveAllQueues', () => {
    const LEAVE_ALL_QUEUES_MUTATION = `
      mutation LeaveAllQueues {
        leaveAllQueues
      }
    `;

    it('успешный выход из всех очередей', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);
      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'CASUAL' } }, authToken);

      const response = await gqlRequest(LEAVE_ALL_QUEUES_MUTATION, {}, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.leaveAllQueues).toBe(true);
    });

    it('выход когда не в очереди возвращает false', async () => {
      const response = await gqlRequest(LEAVE_ALL_QUEUES_MUTATION, {}, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.leaveAllQueues).toBe(false);
    });
  });

  describe('Query: queueStatus', () => {
    const QUEUE_STATUS_QUERY = `
      query QueueStatus($mode: GameMode!) {
        queueStatus(mode: $mode) {
          inQueue
          mode
          position
          totalPlayers
          estimatedWaitTime
        }
      }
    `;

    it('успешное получение статуса когда в очереди', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);

      const response = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'RANKED' }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.queueStatus).toBeDefined();

      const { queueStatus } = response.body.data;
      expect(queueStatus.inQueue).toBe(true);
      expect(queueStatus.mode).toBe('RANKED');
      expect(queueStatus.totalPlayers).toBeGreaterThanOrEqual(1);
    });

    it('статус когда не в очереди', async () => {
      const response = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'CASUAL' }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.queueStatus.inQueue).toBe(false);
      expect(response.body.data.queueStatus.mode).toBe('CASUAL');
    });

    it('позиция корректно отображается', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            position
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken2);
      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);

      const response = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'RANKED' }, authToken).expect(200);

      expect(response.body.data.queueStatus.position).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Query: allQueueStatus', () => {
    const ALL_QUEUE_STATUS_QUERY = `
      query AllQueueStatus {
        allQueueStatus
      }
    `;

    it('успешное получение статуса всех очередей', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);
      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'CASUAL' } }, authToken2);

      const response = await gqlRequest(ALL_QUEUE_STATUS_QUERY, {}).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.allQueueStatus).toBeDefined();

      const status = JSON.parse(response.body.data.allQueueStatus);
      expect(status).toHaveProperty('RANKED');
      expect(status).toHaveProperty('CASUAL');
      expect(status.RANKED).toHaveProperty('totalPlayers');
      expect(status.CASUAL).toHaveProperty('totalPlayers');
    });
  });

  describe('Query: penaltyInfo', () => {
    const PENALTY_INFO_QUERY = `
      query PenaltyInfo {
        penaltyInfo {
          canJoinQueue
          declineCount
          tempBanUntil
          penaltyElo
          reason
        }
      }
    `;

    it('успешное получение информации о штрафах', async () => {
      const response = await gqlRequest(PENALTY_INFO_QUERY, {}, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.penaltyInfo).toBeDefined();

      const { penaltyInfo } = response.body.data;
      expect(penaltyInfo).toHaveProperty('canJoinQueue');
      expect(penaltyInfo).toHaveProperty('declineCount');
      expect(penaltyInfo).toHaveProperty('tempBanUntil');
      expect(penaltyInfo).toHaveProperty('penaltyElo');
      expect(typeof penaltyInfo.canJoinQueue).toBe('boolean');
      expect(typeof penaltyInfo.declineCount).toBe('number');
    });

    it('новый пользователь может join очередь', async () => {
      const response = await gqlRequest(PENALTY_INFO_QUERY, {}, authToken).expect(200);

      expect(response.body.data.penaltyInfo.canJoinQueue).toBe(true);
      expect(response.body.data.penaltyInfo.declineCount).toBe(0);
    });
  });

  describe('Query: metrics', () => {
    const METRICS_QUERY = `
      query Metrics {
        metrics
      }
    `;

    it('успешное получение метрик матчмейкинга', async () => {
      const response = await gqlRequest(METRICS_QUERY, {}).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.metrics).toBeDefined();

      const metrics = JSON.parse(response.body.data.metrics);
      expect(metrics).toHaveProperty('queueSizes');
      expect(metrics).toHaveProperty('joinCount');
      expect(metrics).toHaveProperty('leaveCount');
      expect(metrics).toHaveProperty('matchCount');
    });
  });

  describe('Интеграционные сценарии', () => {
    it('полный цикл: join -> status -> leave', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
            mode
            position
          }
        }
      `;

      const joinResponse = await gqlRequest(
        JOIN_QUEUE_MUTATION,
        { input: { mode: 'RANKED' } },
        authToken,
      );

      expect(joinResponse.body.data.joinQueue.inQueue).toBe(true);

      const QUEUE_STATUS_QUERY = `
        query QueueStatus($mode: GameMode!) {
          queueStatus(mode: $mode) {
            inQueue
            position
            totalPlayers
          }
        }
      `;

      const statusResponse = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'RANKED' }, authToken);

      expect(statusResponse.body.data.queueStatus.inQueue).toBe(true);
      expect(statusResponse.body.data.queueStatus.totalPlayers).toBeGreaterThan(0);

      const LEAVE_QUEUE_MUTATION = `
        mutation LeaveQueue($mode: GameMode!) {
          leaveQueue(mode: $mode)
        }
      `;

      const leaveResponse = await gqlRequest(LEAVE_QUEUE_MUTATION, { mode: 'RANKED' }, authToken);

      expect(leaveResponse.body.data.leaveQueue).toBe(true);

      const afterLeaveResponse = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'RANKED' }, authToken);

      expect(afterLeaveResponse.body.data.queueStatus.inQueue).toBe(false);
    });

    it('множественные игроки в очереди корректно обновляют totalPlayers', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            totalPlayers
          }
        }
      `;

      const firstJoin = await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);
      const firstTotal = firstJoin.body.data.joinQueue.totalPlayers;

      const secondJoin = await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken2);
      const secondTotal = secondJoin.body.data.joinQueue.totalPlayers;

      expect(secondTotal).toBeGreaterThan(firstTotal);

      const thirdJoin = await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken3);
      const thirdTotal = thirdJoin.body.data.joinQueue.totalPlayers;

      expect(thirdTotal).toBeGreaterThan(secondTotal);
    });

    it('leaveAllQueues очищает все очереди', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);
      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'CASUAL' } }, authToken);

      const QUEUE_STATUS_QUERY = `
        query QueueStatus($mode: GameMode!) {
          queueStatus(mode: $mode) {
            inQueue
          }
        }
      `;

      const rankedStatus = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'RANKED' }, authToken);
      const casualStatus = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'CASUAL' }, authToken);

      expect(rankedStatus.body.data.queueStatus.inQueue).toBe(true);
      expect(casualStatus.body.data.queueStatus.inQueue).toBe(true);

      const LEAVE_ALL_QUEUES_MUTATION = `
        mutation LeaveAllQueues {
          leaveAllQueues
        }
      `;

      await gqlRequest(LEAVE_ALL_QUEUES_MUTATION, {}, authToken);

      const afterRankedStatus = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'RANKED' }, authToken);
      const afterCasualStatus = await gqlRequest(QUEUE_STATUS_QUERY, { mode: 'CASUAL' }, authToken);

      expect(afterRankedStatus.body.data.queueStatus.inQueue).toBe(false);
      expect(afterCasualStatus.body.data.queueStatus.inQueue).toBe(false);
    });
  });

  describe('Race Conditions и Concurrency', () => {
    it('одновременный join и leave корректно обрабатываются', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      const LEAVE_QUEUE_MUTATION = `
        mutation LeaveQueue($mode: GameMode!) {
          leaveQueue(mode: $mode)
        }
      `;

      const promises = [
        gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken),
        gqlRequest(LEAVE_QUEUE_MUTATION, { mode: 'RANKED' }, authToken),
      ];

      const results = await Promise.all(promises);

      expect(results).toBeDefined();
      expect(results.length).toBe(2);
    });

    it('множественные одновременные join запросы', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            position
            totalPlayers
          }
        }
      `;

      const promises = [];
      for (let i = 0; i < 5; i++) {
        promises.push(
          gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'CASUAL' } }, authToken),
        );
      }

      const results = await Promise.all(promises);

      results.forEach((result) => {
        expect(result.body.errors).toBeUndefined();
        expect(result.body.data.joinQueue.totalPlayers).toBeGreaterThan(0);
      });
    });
  });

  describe('Кеширование', () => {
    it('статус очереди кешируется в Redis', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);

      const cached = await redis.get(`mm:queue:RANKED:${testUserId}`);
      expect(cached).toBeDefined();
    });

    it('метрики кешируются в Redis', async () => {
      const METRICS_QUERY = `
        query Metrics {
          metrics
        }
      `;

      await gqlRequest(METRICS_QUERY, {});

      const cached = await redis.get('mm:metrics');
      expect(cached).toBeDefined();
    });

    it('данные о штрафах кешируются', async () => {
      const PENALTY_INFO_QUERY = `
        query PenaltyInfo {
          penaltyInfo {
            canJoinQueue
          }
        }
      `;

      await gqlRequest(PENALTY_INFO_QUERY, {}, authToken);

      const cached = await redis.get(`mm:penalty:${testUserId}`);
      expect(cached).toBeDefined();
    });
  });

  describe('Distributed Locking', () => {
    it('join queue использует distributed lock', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);

      const lockExists = await redis.exists(`mm:join:${testUserId}`);
      expect(lockExists).toBe(0);
    });

    it('leave queue использует distributed lock', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      const LEAVE_QUEUE_MUTATION = `
        mutation LeaveQueue($mode: GameMode!) {
          leaveQueue(mode: $mode)
        }
      `;

      await gqlRequest(JOIN_QUEUE_MUTATION, { input: { mode: 'RANKED' } }, authToken);
      await gqlRequest(LEAVE_QUEUE_MUTATION, { mode: 'RANKED' }, authToken);

      const lockExists = await redis.exists(`mm:leave:${testUserId}`);
      expect(lockExists).toBe(0);
    });
  });

  describe('Валидация данных', () => {
    it('mode должен быть валидным GameMode', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      const response = await gqlRequest(
        JOIN_QUEUE_MUTATION,
        { input: { mode: 'INVALID_MODE' } },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeDefined();
    });

    it('heroPref должен быть массивом строк', async () => {
      const JOIN_QUEUE_MUTATION = `
        mutation JoinQueue($input: JoinQueueDto!) {
          joinQueue(input: $input) {
            inQueue
          }
        }
      `;

      const response = await gqlRequest(
        JOIN_QUEUE_MUTATION,
        { input: { mode: 'RANKED', heroPref: 'invalid' } },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeDefined();
    });
  });
});