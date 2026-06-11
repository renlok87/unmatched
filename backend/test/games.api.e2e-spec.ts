import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/database/prisma.service';
import { RedisService } from '../src/redis/redis.service';

describe('Games API (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let redis: RedisService;

  let authToken: string;
  let authToken2: string;
  let testUserId: string;
  let testUserId2: string;
  let testGameId: string;

  const generateTestData = (suffix: string) => ({
    email: `game-${suffix}-${Date.now()}@example.com`,
    username: `game-${suffix}-${Date.now()}`,
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

  describe('Mutation: createGame', () => {
    const CREATE_GAME_MUTATION = `
      mutation CreateGame($input: CreateGameDto!) {
        createGame(input: $input) {
          id
          name
          mode
          status
          maxPlayers
          currentPlayers
          createdBy {
            id
            username
          }
          createdAt
        }
      }
    `;

    it('успешное создание игры в режиме RANKED', async () => {
      const response = await gqlRequest(
        CREATE_GAME_MUTATION,
        {
          input: {
            name: 'Test Ranked Game',
            mode: 'RANKED',
            maxPlayers: 2,
          },
        },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.createGame).toBeDefined();

      const { createGame } = response.body.data;
      expect(createGame.id).toBeDefined();
      expect(createGame.name).toBe('Test Ranked Game');
      expect(createGame.mode).toBe('RANKED');
      expect(createGame.status).toBe('WAITING');
      expect(createGame.maxPlayers).toBe(2);
      expect(createGame.createdBy.id).toBe(testUserId);

      testGameId = createGame.id;
    });

    it('успешное создание игры в режиме CASUAL', async () => {
      const response = await gqlRequest(
        CREATE_GAME_MUTATION,
        {
          input: {
            name: 'Test Casual Game',
            mode: 'CASUAL',
            maxPlayers: 4,
          },
        },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.createGame.mode).toBe('CASUAL');
    });

    it('rate limiting - ограничение 10 запросов в минуту', async () => {
      const requests = [];
      for (let i = 0; i < 12; i++) {
        requests.push(
          gqlRequest(
            CREATE_GAME_MUTATION,
            {
              input: {
                name: `Game ${i}`,
                mode: 'CASUAL',
                maxPlayers: 2,
              },
            },
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

  describe('Query: game', () => {
    const GAME_QUERY = `
      query Game($id: ID!) {
        game(id: $id) {
          id
          name
          mode
          status
          maxPlayers
          currentPlayers
          players {
            id
            username
            isReady
            heroId
          }
          createdBy {
            id
            username
          }
        }
      }
    `;

    beforeAll(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const response = await gqlRequest(
        CREATE_GAME_MUTATION,
        {
          input: {
            name: 'Test Game for Query',
            mode: 'CASUAL',
            maxPlayers: 2,
          },
        },
        authToken,
      );

      testGameId = response.body.data.createGame.id;
    });

    it('успешное получение игры по ID', async () => {
      const response = await gqlRequest(GAME_QUERY, { id: testGameId }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.game).toBeDefined();

      const { game } = response.body.data;
      expect(game.id).toBe(testGameId);
      expect(game.players).toBeDefined();
      expect(Array.isArray(game.players)).toBe(true);
    });

    it('ошибка при запросе без токена для активной игры', async () => {
      const response = await gqlRequest(GAME_QUERY, { id: testGameId }).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });

    it('ошибка при запросе несуществующей игры', async () => {
      const response = await gqlRequest(GAME_QUERY, { id: 'nonexistent-id' }, authToken).expect(200);

      expect(response.body.data.game).toBeNull();
    });
  });

  describe('Query: myGames', () => {
    const MY_GAMES_QUERY = `
      query MyGames($filters: GameFiltersDto) {
        myGames(filters: $filters) {
          id
          name
          mode
          status
          currentPlayers
          maxPlayers
        }
      }
    `;

    beforeAll(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
            status
          }
        }
      `;

      await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'My Game 1', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'My Game 2', mode: 'RANKED', maxPlayers: 2 } },
        authToken,
      );
    });

    it('успешное получение всех игр пользователя', async () => {
      const response = await gqlRequest(MY_GAMES_QUERY, {}, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.myGames).toBeDefined();
      expect(Array.isArray(response.body.data.myGames)).toBe(true);
      expect(response.body.data.myGames.length).toBeGreaterThan(0);
    });

    it('фильтрация по статусу', async () => {
      const response = await gqlRequest(MY_GAMES_QUERY, { filters: { status: 'WAITING' } }, authToken).expect(200);

      expect(response.body.data.myGames).toBeDefined();
      response.body.data.myGames.forEach((game: any) => {
        expect(game.status).toBe('WAITING');
      });
    });

    it('фильтрация по режиму игры', async () => {
      const response = await gqlRequest(MY_GAMES_QUERY, { filters: { mode: 'RANKED' } }, authToken).expect(200);

      expect(response.body.data.myGames).toBeDefined();
      response.body.data.myGames.forEach((game: any) => {
        expect(game.mode).toBe('RANKED');
      });
    });
  });

  describe('Query: availableGames', () => {
    const AVAILABLE_GAMES_QUERY = `
      query AvailableGames($mode: GameMode, $limit: Int) {
        availableGames(mode: $mode, limit: $limit) {
          id
          name
          mode
          status
          currentPlayers
          maxPlayers
        }
      }
    `;

    it('успешное получение доступных игр', async () => {
      const response = await gqlRequest(AVAILABLE_GAMES_QUERY, {}).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.availableGames).toBeDefined();
      expect(Array.isArray(response.body.data.availableGames)).toBe(true);
    });

    it('фильтрация по режиму игры', async () => {
      const response = await gqlRequest(AVAILABLE_GAMES_QUERY, { mode: 'RANKED' }).expect(200);

      expect(response.body.data.availableGames).toBeDefined();
      response.body.data.availableGames.forEach((game: any) => {
        expect(game.mode).toBe('RANKED');
      });
    });

    it('ограничение количества результатов', async () => {
      const response = await gqlRequest(AVAILABLE_GAMES_QUERY, { limit: 5 }).expect(200);

      expect(response.body.data.availableGames.length).toBeLessThanOrEqual(5);
    });
  });

  describe('Mutation: joinGame', () => {
    const JOIN_GAME_MUTATION = `
      mutation JoinGame($input: JoinGameDto!) {
        joinGame(input: $input) {
          id
          currentPlayers
          players {
            id
            username
            isReady
          }
        }
      }
    `;

    let gameId: string;

    beforeEach(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const response = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Game to Join', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      gameId = response.body.data.createGame.id;
    });

    it('успешное присоединение к игре', async () => {
      const response = await gqlRequest(
        JOIN_GAME_MUTATION,
        { input: { gameId } },
        authToken2,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.joinGame).toBeDefined();

      const { joinGame } = response.body.data;
      expect(joinGame.currentPlayers).toBeGreaterThan(0);
      expect(joinGame.players.length).toBeGreaterThan(0);
    });

    it('присоединение с выбором героя', async () => {
      const response = await gqlRequest(
        JOIN_GAME_MUTATION,
        { input: { gameId, heroId: 'daredevil' } },
        authToken2,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();

      const player = response.body.data.joinGame.players.find((p: any) => p.id === testUserId2);
      expect(player.heroId).toBe('daredevil');
    });

    it('ошибка при попытке присоединиться к полной игре', async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const gameResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Full Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      const fullGameId = gameResponse.body.data.createGame.id;

      await gqlRequest(JOIN_GAME_MUTATION, { input: { gameId: fullGameId } }, authToken2);

      const thirdUser = await createAuthenticatedUser('third');
      const thirdToken = thirdUser.accessToken;

      const response = await gqlRequest(JOIN_GAME_MUTATION, { input: { gameId: fullGameId } }, thirdToken).expect(200);

      expect(response.body.errors).toBeDefined();
    });

    it('rate limiting - ограничение 15 запросов в минуту', async () => {
      const requests = [];
      for (let i = 0; i < 17; i++) {
        requests.push(gqlRequest(JOIN_GAME_MUTATION, { input: { gameId } }, authToken2));
      }

      const responses = await Promise.all(requests);
      const throttled = responses.filter(
        (r: any) => r.body.errors?.[0]?.extensions?.code === 'TOO_MANY_REQUESTS',
      );

      expect(throttled.length).toBeGreaterThan(0);
    });
  });

  describe('Mutation: leaveGame', () => {
    const LEAVE_GAME_MUTATION = `
      mutation LeaveGame($gameId: ID!) {
        leaveGame(gameId: $gameId)
      }
    `;

    let gameId: string;

    beforeEach(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Game to Leave', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      gameId = createResponse.body.data.createGame.id;

      const JOIN_GAME_MUTATION = `
        mutation JoinGame($input: JoinGameDto!) {
          joinGame(input: $input) {
            id
          }
        }
      `;

      await gqlRequest(JOIN_GAME_MUTATION, { input: { gameId } }, authToken2);
    });

    it('успешный выход из игры', async () => {
      const response = await gqlRequest(LEAVE_GAME_MUTATION, { gameId }, authToken2).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.leaveGame).toBe(true);
    });

    it('ошибка при выходе из игры, в которой не участвуешь', async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Other Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      const otherGameId = createResponse.body.data.createGame.id;

      const response = await gqlRequest(LEAVE_GAME_MUTATION, { gameId: otherGameId }, authToken2).expect(200);

      expect(response.body.errors).toBeDefined();
    });

    it('хост может покинуть игру - opponent становится новым хостом', async () => {
      const GAME_QUERY = `
        query Game($id: ID!) {
          game(id: $id) {
            id
            hostId
            opponentId
          }
        }
      `;

      // Получаем начальное состояние
      const beforeLeave = await gqlRequest(GAME_QUERY, { id: gameId }, authToken);
      const originalHostId = beforeLeave.body.data.game.hostId;
      const originalOpponentId = beforeLeave.body.data.game.opponentId;

      // Хост покидает игру
      const leaveResponse = await gqlRequest(LEAVE_GAME_MUTATION, { gameId }, authToken).expect(200);
      expect(leaveResponse.body.errors).toBeUndefined();
      expect(leaveResponse.body.data.leaveGame).toBe(true);

      // Проверяем, что opponent стал новым хостом
      const afterLeave = await gqlRequest(GAME_QUERY, { id: gameId }, authToken2);
      expect(afterLeave.body.data.game.hostId).toBe(originalOpponentId);
      expect(afterLeave.body.data.game.opponentId).toBeNull();
    });

    it('хост может покинуть игру без opponent - игра удаляется', async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Solo Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      const soloGameId = createResponse.body.data.createGame.id;

      // Хост покидает игру без opponent
      const leaveResponse = await gqlRequest(LEAVE_GAME_MUTATION, { gameId: soloGameId }, authToken).expect(200);
      expect(leaveResponse.body.errors).toBeUndefined();
      expect(leaveResponse.body.data.leaveGame).toBe(true);

      // Проверяем, что игра удалена
      const GAME_QUERY = `
        query Game($id: ID!) {
          game(id: $id) {
            id
          }
        }
      `;

      const afterLeave = await gqlRequest(GAME_QUERY, { id: soloGameId }, authToken);
      expect(afterLeave.body.data.game).toBeNull();
    });
  });

  describe('Mutation: toggleReady', () => {
    const TOGGLE_READY_MUTATION = `
      mutation ToggleReady($gameId: ID!) {
        toggleReady(gameId: $gameId) {
          id
          players {
            id
            username
            isReady
          }
        }
      }
    `;

    let gameId: string;

    beforeEach(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Ready Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      gameId = createResponse.body.data.createGame.id;

      const JOIN_GAME_MUTATION = `
        mutation JoinGame($input: JoinGameDto!) {
          joinGame(input: $input) {
            id
          }
        }
      `;

      await gqlRequest(JOIN_GAME_MUTATION, { input: { gameId } }, authToken2);
    });

    it('успешное переключение готовности', async () => {
      const response = await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();

      const player = response.body.data.toggleReady.players.find((p: any) => p.id === testUserId);
      expect(player.isReady).toBe(true);
    });

    it('toggle готовности изменяет состояние', async () => {
      const firstToggle = await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken);
      const player1 = firstToggle.body.data.toggleReady.players.find((p: any) => p.id === testUserId);
      expect(player1.isReady).toBe(true);

      const secondToggle = await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken);
      const player2 = secondToggle.body.data.toggleReady.players.find((p: any) => p.id === testUserId);
      expect(player2.isReady).toBe(false);
    });

    it('rate limiting - ограничение 20 запросов в минуту', async () => {
      const requests = [];
      for (let i = 0; i < 22; i++) {
        requests.push(gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken));
      }

      const responses = await Promise.all(requests);
      const throttled = responses.filter(
        (r: any) => r.body.errors?.[0]?.extensions?.code === 'TOO_MANY_REQUESTS',
      );

      expect(throttled.length).toBeGreaterThan(0);
    });
  });

  describe('Mutation: selectHero', () => {
    const SELECT_HERO_MUTATION = `
      mutation SelectHero($gameId: ID!, $heroId: String!) {
        selectHero(gameId: $gameId, heroId: $heroId) {
          id
          players {
            id
            heroId
          }
        }
      }
    `;

    let gameId: string;

    beforeEach(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Hero Selection Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      gameId = createResponse.body.data.createGame.id;
    });

    it('успешный выбор героя', async () => {
      const response = await gqlRequest(SELECT_HERO_MUTATION, { gameId, heroId: 'daredevil' }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();

      const player = response.body.data.selectHero.players.find((p: any) => p.id === testUserId);
      expect(player.heroId).toBe('daredevil');
    });

    it('ошибка при выборе несуществующего героя', async () => {
      const response = await gqlRequest(
        SELECT_HERO_MUTATION,
        { gameId, heroId: 'nonexistent-hero' },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeDefined();
    });

    it('rate limiting - ограничение 10 запросов в минуту', async () => {
      const requests = [];
      for (let i = 0; i < 12; i++) {
        requests.push(gqlRequest(SELECT_HERO_MUTATION, { gameId, heroId: 'daredevil' }, authToken));
      }

      const responses = await Promise.all(requests);
      const throttled = responses.filter(
        (r: any) => r.body.errors?.[0]?.extensions?.code === 'TOO_MANY_REQUESTS',
      );

      expect(throttled.length).toBeGreaterThan(0);
    });
  });

  describe('Query: gameState', () => {
    const GAME_STATE_QUERY = `
      query GameState($gameId: ID!) {
        gameState(gameId: $gameId) {
          id
          gameId
          sequenceNumber
          currentTurnPlayerId
          phase
          turnCount
          state
          updatedAt
        }
      }
    `;

    let gameId: string;

    beforeAll(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'State Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      gameId = createResponse.body.data.createGame.id;
    });

    it('успешное получение состояния игры', async () => {
      const response = await gqlRequest(GAME_STATE_QUERY, { gameId }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.gameState).toBeDefined();

      const { gameState } = response.body.data;
      expect(gameState.gameId).toBe(gameId);
      expect(gameState.sequenceNumber).toBeDefined();
      expect(gameState.phase).toBeDefined();
      expect(gameState.turnCount).toBeDefined();
    });

    it('состояние содержит валидный JSON', async () => {
      const response = await gqlRequest(GAME_STATE_QUERY, { gameId }, authToken).expect(200);

      const { gameState } = response.body.data;

      expect(() => {
        JSON.parse(gameState.state);
      }).not.toThrow();
    });

    it('sequenceNumber увеличивается при действиях', async () => {
      const firstState = await gqlRequest(GAME_STATE_QUERY, { gameId }, authToken);
      const firstSequence = firstState.body.data.gameState.sequenceNumber;

      await new Promise((resolve) => setTimeout(resolve, 100));

      const secondState = await gqlRequest(GAME_STATE_QUERY, { gameId }, authToken);
      const secondSequence = secondState.body.data.gameState.sequenceNumber;

      expect(secondSequence).toBeGreaterThanOrEqual(firstSequence);
    });

    it('ошибка при запросе состояния неучастником', async () => {
      const thirdUser = await createAuthenticatedUser('third-state');
      const thirdToken = thirdUser.accessToken;

      const response = await gqlRequest(GAME_STATE_QUERY, { gameId }, thirdToken).expect(200);

      expect(response.body.errors).toBeDefined();
    });
  });

  describe('Query: gameSequence', () => {
    const GAME_SEQUENCE_QUERY = `
      query GameSequence($gameId: ID!) {
        gameSequence(gameId: $gameId)
      }
    `;

    let gameId: string;

    beforeAll(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Sequence Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      gameId = createResponse.body.data.createGame.id;
    });

    it('успешное получение sequence number', async () => {
      const response = await gqlRequest(GAME_SEQUENCE_QUERY, { gameId }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.gameSequence).toBeDefined();
      expect(typeof response.body.data.gameSequence).toBe('number');
    });

    it('sequence number является неотрицательным', async () => {
      const response = await gqlRequest(GAME_SEQUENCE_QUERY, { gameId }, authToken).expect(200);

      expect(response.body.data.gameSequence).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Query: eventsSince', () => {
    const EVENTS_SINCE_QUERY = `
      query EventsSince($gameId: ID!, $sinceSequence: Float!) {
        eventsSince(gameId: $gameId, sinceSequence: $sinceSequence) {
          gameId
          events
          lastSequence
          hasMore
        }
      }
    `;

    let gameId: string;

    beforeAll(async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Events Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      gameId = createResponse.body.data.createGame.id;
    });

    it('успешное получение событий с указанного sequence', async () => {
      const response = await gqlRequest(EVENTS_SINCE_QUERY, { gameId, sinceSequence: 0 }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.eventsSince).toBeDefined();

      const { eventsSince } = response.body.data;
      expect(eventsSince.gameId).toBe(gameId);
      expect(eventsSince.lastSequence).toBeDefined();
      expect(typeof eventsSince.hasMore).toBe('boolean');
    });

    it('возвращает пустой список если нет новых событий', async () => {
      const GAME_SEQUENCE_QUERY = `
        query GameSequence($gameId: ID!) {
          gameSequence(gameId: $gameId)
        }
      `;

      const sequenceResponse = await gqlRequest(GAME_SEQUENCE_QUERY, { gameId }, authToken);
      const currentSequence = sequenceResponse.body.data.gameSequence;

      const response = await gqlRequest(
        EVENTS_SINCE_QUERY,
        { gameId, sinceSequence: currentSequence },
        authToken,
      ).expect(200);

      expect(response.body.data.eventsSince.events.length).toBe(0);
    });

    it('ошибка при запросе неучастником', async () => {
      const thirdUser = await createAuthenticatedUser('third-events');
      const thirdToken = thirdUser.accessToken;

      const response = await gqlRequest(EVENTS_SINCE_QUERY, { gameId, sinceSequence: 0 }, thirdToken).expect(200);

      expect(response.body.errors).toBeDefined();
    });
  });

  describe('Интеграционные сценарии', () => {
    it('полный жизненный цикл игры: создание -> присоединение -> готовность -> начало', async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
            status
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Full Cycle Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      const gameId = createResponse.body.data.createGame.id;
      expect(createResponse.body.data.createGame.status).toBe('WAITING');

      const JOIN_GAME_MUTATION = `
        mutation JoinGame($input: JoinGameDto!) {
          joinGame(input: $input) {
            id
            currentPlayers
          }
        }
      `;

      const joinResponse = await gqlRequest(JOIN_GAME_MUTATION, { input: { gameId } }, authToken2);
      expect(joinResponse.body.data.joinGame.currentPlayers).toBe(2);

      const TOGGLE_READY_MUTATION = `
        mutation ToggleReady($gameId: ID!) {
          toggleReady(gameId: $gameId) {
            id
            players {
              id
              isReady
            }
          }
        }
      `;

      await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken);
      await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken2);

      const GAME_QUERY = `
        query Game($id: ID!) {
          game(id: $id) {
            id
            players {
              id
              isReady
            }
          }
        }
      `;

      const gameResponse = await gqlRequest(GAME_QUERY, { id: gameId }, authToken);
      const allReady = gameResponse.body.data.game.players.every((p: any) => p.isReady);
      expect(allReady).toBe(true);
    });

    it('множественные переключения готовности корректно обновляют состояние', async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Toggle Test Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      const gameId = createResponse.body.data.createGame.id;

      const TOGGLE_READY_MUTATION = `
        mutation ToggleReady($gameId: ID!) {
          toggleReady(gameId: $gameId) {
            players {
              id
              isReady
            }
          }
        }
      `;

      await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken);
      await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken);
      await gqlRequest(TOGGLE_READY_MUTATION, { gameId }, authToken);

      const GAME_QUERY = `
        query Game($id: ID!) {
          game(id: $id) {
            players {
              id
              isReady
            }
          }
        }
      `;

      const response = await gqlRequest(GAME_QUERY, { id: gameId }, authToken);
      const player = response.body.data.game.players.find((p: any) => p.id === testUserId);
      expect(player.isReady).toBe(true);
    });
  });

  describe('Кеширование', () => {
    it('состояние игры кешируется в Redis', async () => {
      const CREATE_GAME_MUTATION = `
        mutation CreateGame($input: CreateGameDto!) {
          createGame(input: $input) {
            id
          }
        }
      `;

      const createResponse = await gqlRequest(
        CREATE_GAME_MUTATION,
        { input: { name: 'Cache Test Game', mode: 'CASUAL', maxPlayers: 2 } },
        authToken,
      );

      const gameId = createResponse.body.data.createGame.id;

      const GAME_STATE_QUERY = `
        query GameState($gameId: ID!) {
          gameState(gameId: $gameId) {
            id
          }
        }
      `;

      await gqlRequest(GAME_STATE_QUERY, { gameId }, authToken);

      const cached = await redis.get(`game:state:${gameId}`);
      expect(cached).toBeDefined();
    });

    it('список игр кешируется в Redis', async () => {
      const MY_GAMES_QUERY = `
        query MyGames {
          myGames {
            id
          }
        }
      `;

      await gqlRequest(MY_GAMES_QUERY, {}, authToken);

      const cached = await redis.get(`games:user:${testUserId}`);
      expect(cached).toBeDefined();
    });
  });
});