import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/database/prisma.service';
import { RedisService } from '../src/redis/redis.service';

/**
 * E2E тесты для GraphQL Admin API
 *
 * Тестируют все admin queries и mutations через GraphQL endpoint
 */
describe('Admin API (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let redis: RedisService;

  // Токены для тестов
  let adminToken: string;
  let userToken: string;
  let moderatorToken: string;

  // Тестовые данные
  let testHeroId: string;
  let testCardId: string;
  let testBoardId: string;
  let testUserId: string;

  // Генератор уникальных данных для тестов
  const generateTestData = (suffix: string) => {
    const timestamp = Date.now().toString().slice(-6);
    const safeSuffix = suffix.replace(/[^a-zA-Z0-9]/g, '');
    return {
      email: `admin${safeSuffix}${timestamp}@example.com`,
      username: `admin${safeSuffix}${timestamp}`,
      password: 'AdminPassword123!',
    };
  };

  // GraphQL query helper
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

    app.enableCors({
      origin: '*',
      credentials: true,
    });

    await app.init();

    prisma = app.get<PrismaService>(PrismaService);
    redis = app.get<RedisService>(RedisService);
  });

  afterAll(async () => {
    // Очистка тестовых данных
    await prisma.card.deleteMany({
      where: { hero: { name: { contains: 'Test' } } },
    });
    await prisma.hero.deleteMany({
      where: { name: { contains: 'Test' } },
    });
    await prisma.board.deleteMany({
      where: { name: { contains: 'Test' } },
    });
    await prisma.refreshToken.deleteMany({
      where: { user: { email: { contains: '@example.com' } } },
    });
    await prisma.user.deleteMany({
      where: { email: { contains: '@example.com' } },
    });

    await app.close();
  });

  afterEach(async () => {
    await redis.flushDb();
  });

  describe('Setup: Создание пользователей с разными ролями', () => {
    const REGISTER_MUTATION = `
      mutation Register($input: RegisterDto!) {
        register(input: $input) {
          accessToken
          user {
            id
            role
          }
        }
      }
    `;

    const UPDATE_ROLE_MUTATION = `
      mutation UpdateUserRole($id: String!, $role: UserRole!) {
        updateUserRole(id: $id, role: $role) {
          id
          role
        }
      }
    `;

    it('создаёт admin пользователя', async () => {
      const data = generateTestData('admin');

      const response = await gqlRequest(REGISTER_MUTATION, { input: data });
      expect(response.body.errors).toBeUndefined();

      const adminId = response.body.data.register.user.id;

      // Обновляем роль на ADMIN (требует прямого доступа к БД для тестов)
      await prisma.user.update({
        where: { id: adminId },
        data: { role: 'ADMIN' },
      });

      // Логинимся снова чтобы получить токен с новой ролью
      const LOGIN_MUTATION = `
        mutation Login($input: LoginDto!) {
          login(input: $input) {
            accessToken
          }
        }
      `;

      const loginResponse = await gqlRequest(LOGIN_MUTATION, {
        input: { email: data.email, password: data.password },
      });
      expect(loginResponse.body.errors).toBeUndefined();

      adminToken = loginResponse.body.data.login.accessToken;
    });

    it('создаёт moderator пользователя', async () => {
      const data = generateTestData('mod');

      const response = await gqlRequest(REGISTER_MUTATION, { input: data });
      expect(response.body.errors).toBeUndefined();

      const modId = response.body.data.register.user.id;

      await prisma.user.update({
        where: { id: modId },
        data: { role: 'MODERATOR' },
      });

      // Логинимся снова чтобы получить токен с новой ролью
      const LOGIN_MUTATION = `
        mutation Login($input: LoginDto!) {
          login(input: $input) {
            accessToken
          }
        }
      `;

      const loginResponse = await gqlRequest(LOGIN_MUTATION, {
        input: { email: data.email, password: data.password },
      });
      expect(loginResponse.body.errors).toBeUndefined();

      moderatorToken = loginResponse.body.data.login.accessToken;
    });

    it('создаёт обычного пользователя', async () => {
      const data = generateTestData('user');

      const response = await gqlRequest(REGISTER_MUTATION, { input: data });
      expect(response.body.errors).toBeUndefined();

      userToken = response.body.data.register.accessToken;
      testUserId = response.body.data.register.user.id;
    });
  });

  describe('Query: adminStats', () => {
    const STATS_QUERY = `
      query GetAdminStats {
        adminStats {
          totalUsers
          totalHeroes
          totalCards
          totalBoards
          totalGames
        }
      }
    `;

    it('возвращает статистику для admin', async () => {
      const response = await gqlRequest(STATS_QUERY, {}, adminToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.adminStats).toBeDefined();

      const stats = response.body.data.adminStats;
      expect(stats.totalUsers).toBeGreaterThanOrEqual(0);
      expect(stats.totalHeroes).toBeGreaterThanOrEqual(0);
      expect(stats.totalCards).toBeGreaterThanOrEqual(0);
      expect(stats.totalBoards).toBeGreaterThanOrEqual(0);
      expect(stats.totalGames).toBeGreaterThanOrEqual(0);
    });

    it('возвращает ошибку для обычного пользователя', async () => {
      const response = await gqlRequest(STATS_QUERY, {}, userToken).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('FORBIDDEN');
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(STATS_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Query: adminHero / heroesList', () => {
    const HEROES_LIST_QUERY = `
      query GetHeroesList($page: Int, $limit: Int) {
        heroList(page: $page, limit: $limit) {
          items {
            id
            name
            nameEn
            nameRu
            set
            health
            fighterType
            createdAt
          }
          total
          page
          limit
          totalPages
        }
      }
    `;

    const HERO_QUERY = `
      query GetHero($id: String!) {
        adminHero(id: $id) {
          id
          name
          nameEn
          nameRu
          set
          health
          fighterType
          ability
          deckCards
          properties
          imageUrl
          avatarUrl
          createdAt
          updatedAt
        }
      }
    `;

    it('возвращает список героев для авторизованного пользователя', async () => {
      const response = await gqlRequest(HEROES_LIST_QUERY, { page: 1, limit: 10 }, userToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.heroList).toBeDefined();

      const list = response.body.data.heroList;
      expect(Array.isArray(list.items)).toBe(true);
      expect(typeof list.total).toBe('number');
      expect(list.page).toBe(1);
      expect(list.limit).toBe(10);
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(HEROES_LIST_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Mutation: createHero, updateHero, deleteHero', () => {
    const CREATE_HERO_MUTATION = `
      mutation CreateHero($input: CreateHeroInput!) {
        createHero(input: $input) {
          id
          name
          nameEn
          nameRu
          set
          health
          fighterType
        }
      }
    `;

    const UPDATE_HERO_MUTATION = `
      mutation UpdateHero($id: String!, $input: UpdateHeroInput!) {
        updateHero(id: $id, input: $input) {
          id
          name
          health
        }
      }
    `;

    const DELETE_HERO_MUTATION = `
      mutation DeleteHero($id: String!) {
        deleteHero(id: $id)
      }
    `;

    it('полный CRUD цикл для героя', async () => {
      // 1. Создаём
      const createInput = {
        name: `Test Hero ${Date.now()}`,
        nameEn: 'Test Hero En',
        nameRu: 'Тестовый Герой',
        set: 'test-set',
        health: 10,
        fighterType: 'MELEE',
        ability: JSON.stringify({ name: 'Test ability', description: 'Test' }),
        deckCards: JSON.stringify([]),
        properties: JSON.stringify({ test: true }),
      };

      const createResponse = await gqlRequest(CREATE_HERO_MUTATION, { input: createInput }, adminToken).expect(200);
      expect(createResponse.body.errors).toBeUndefined();
      expect(createResponse.body.data.createHero).toBeDefined();

      const hero = createResponse.body.data.createHero;
      expect(hero.id).toBeDefined();
      expect(hero.name).toBe(createInput.name);
      expect(hero.health).toBe(createInput.health);

      const heroId = hero.id;

      // 2. Обновляем
      const updateInput = {
        name: `Updated Hero ${Date.now()}`,
        health: 15,
      };

      const updateResponse = await gqlRequest(
        UPDATE_HERO_MUTATION,
        { id: heroId, input: updateInput },
        adminToken,
      ).expect(200);

      expect(updateResponse.body.errors).toBeUndefined();
      expect(updateResponse.body.data.updateHero).toBeDefined();

      const updatedHero = updateResponse.body.data.updateHero;
      expect(updatedHero.id).toBe(heroId);
      expect(updatedHero.health).toBe(15);

      // 3. Удаляем
      const deleteResponse = await gqlRequest(DELETE_HERO_MUTATION, { id: heroId }, adminToken).expect(200);
      expect(deleteResponse.body.errors).toBeUndefined();
      expect(deleteResponse.body.data.deleteHero).toBe(true);

      // 4. Проверяем удаление из БД
      const deletedHero = await prisma.hero.findUnique({ where: { id: heroId } });
      expect(deletedHero).toBeNull();
    });

    it('не даёт создать героя обычному пользователю', async () => {
      const input = {
        name: `Unauthorized Hero ${Date.now()}`,
        nameEn: 'Unauthorized',
        nameRu: 'Неавторизованный',
        set: 'test',
        health: 5,
        fighterType: 'RANGED',
      };

      const response = await gqlRequest(CREATE_HERO_MUTATION, { input }, userToken).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('FORBIDDEN');
    });
  });

  describe('Query: adminCard / cardsList', () => {
    const CARDS_LIST_QUERY = `
      query GetCardsList($page: Int, $limit: Int, $heroId: String) {
        cardList(page: $page, limit: $limit, heroId: $heroId) {
          items {
            id
            name
            nameEn
            nameRu
            cardType
            subType
            attackValue
            defenseValue
            boostValue
            count
            heroId
            createdAt
          }
          total
          page
          limit
          totalPages
        }
      }
    `;

    const CARD_QUERY = `
      query GetCard($id: String!) {
        adminCard(id: $id) {
          id
          name
          nameEn
          nameRu
          cardType
          subType
          attackValue
          defenseValue
          boostValue
          effects
          text
          textEn
          textRu
          heroId
          count
          createdAt
          updatedAt
        }
      }
    `;

    it('возвращает список карт для авторизованного пользователя', async () => {
      const response = await gqlRequest(CARDS_LIST_QUERY, { page: 1, limit: 10 }, userToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.cardList).toBeDefined();

      const list = response.body.data.cardList;
      expect(Array.isArray(list.items)).toBe(true);
      expect(typeof list.total).toBe('number');
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(CARDS_LIST_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Mutation: createCard, updateCard, deleteCard', () => {
    // Сначала создаём героя для карт (будет использоваться во всех тестах)
    let cardHeroId: string;

    beforeAll(async () => {
      const hero = await prisma.hero.create({
        data: {
          name: `Test Hero for Cards ${Date.now()}`,
          nameEn: 'Test Hero',
          nameRu: 'Тестовый Герой',
          set: 'test-set',
          health: 10,
          fighterType: 'MELEE',
          ability: 'Test',
          deckCards: '[]',
          properties: '{}',
        },
      });
      cardHeroId = hero.id;
    });

    const CREATE_CARD_MUTATION = `
      mutation CreateCard($input: CreateCardInput!) {
        createCard(input: $input) {
          id
          name
          nameEn
          nameRu
          cardType
          attackValue
          defenseValue
          heroId
          count
        }
      }
    `;

    const UPDATE_CARD_MUTATION = `
      mutation UpdateCard($id: String!, $input: UpdateCardInput!) {
        updateCard(id: $id, input: $input) {
          id
          name
          attackValue
          count
        }
      }
    `;

    const DELETE_CARD_MUTATION = `
      mutation DeleteCard($id: String!) {
        deleteCard(id: $id)
      }
    `;

    it('полный CRUD цикл для карты', async () => {
      // 1. Создаём
      const createInput = {
        name: `Test Card ${Date.now()}`,
        nameEn: 'Test Card En',
        nameRu: 'Тестовая Карта',
        heroId: cardHeroId,
        cardType: 'ATTACK',
        subType: 'MELEE',
        attackValue: 5,
        defenseValue: 3,
        boostValue: 1,
        effects: JSON.stringify({ test: true }),
        text: 'Test text',
        textEn: 'Test text En',
        textRu: 'Тестовый текст',
        count: 2,
      };

      const createResponse = await gqlRequest(CREATE_CARD_MUTATION, { input: createInput }, adminToken).expect(200);
      expect(createResponse.body.errors).toBeUndefined();
      expect(createResponse.body.data.createCard).toBeDefined();

      const card = createResponse.body.data.createCard;
      expect(card.id).toBeDefined();
      expect(card.name).toBe(createInput.name);
      expect(card.cardType).toBe(createInput.cardType);
      expect(card.attackValue).toBe(createInput.attackValue);

      const cardId = card.id;

      // 2. Обновляем
      const updateInput = {
        name: `Updated Card ${Date.now()}`,
        attackValue: 7,
        count: 3,
      };

      const updateResponse = await gqlRequest(
        UPDATE_CARD_MUTATION,
        { id: cardId, input: updateInput },
        adminToken,
      ).expect(200);

      expect(updateResponse.body.errors).toBeUndefined();
      expect(updateResponse.body.data.updateCard).toBeDefined();

      const updatedCard = updateResponse.body.data.updateCard;
      expect(updatedCard.id).toBe(cardId);
      expect(updatedCard.attackValue).toBe(7);
      expect(updatedCard.count).toBe(3);

      // 3. Удаляем
      const deleteResponse = await gqlRequest(DELETE_CARD_MUTATION, { id: cardId }, adminToken).expect(200);
      expect(deleteResponse.body.errors).toBeUndefined();
      expect(deleteResponse.body.data.deleteCard).toBe(true);

      // 4. Проверяем удаление из БД
      const deletedCard = await prisma.card.findUnique({ where: { id: cardId } });
      expect(deletedCard).toBeNull();
    });

    it('не даёт создать карту обычному пользователю', async () => {
      const input = {
        name: `Unauthorized Card ${Date.now()}`,
        nameEn: 'Unauthorized',
        nameRu: 'Неавторизованная',
        heroId: cardHeroId,
        cardType: 'DEFENSE',
        count: 1,
      };

      const response = await gqlRequest(CREATE_CARD_MUTATION, { input }, userToken).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('FORBIDDEN');
    });
  });

  describe('Query: adminBoard / boardsList', () => {
    const BOARDS_LIST_QUERY = `
      query GetBoardsList($page: Int, $limit: Int) {
        boardList(page: $page, limit: $limit) {
          items {
            id
            name
            nameEn
            nameRu
            set
            width
            height
            imageUrl
            createdAt
          }
          total
          page
          limit
          totalPages
        }
      }
    `;

    const BOARD_QUERY = `
      query GetBoard($id: String!) {
        adminBoard(id: $id) {
          id
          name
          nameEn
          nameRu
          set
          width
          height
          cells
          features
          imageUrl
          imageUrlDark
          createdAt
          updatedAt
        }
      }
    `;

    it('возвращает список полей для авторизованного пользователя', async () => {
      const response = await gqlRequest(BOARDS_LIST_QUERY, { page: 1, limit: 10 }, userToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.boardList).toBeDefined();

      const list = response.body.data.boardList;
      expect(Array.isArray(list.items)).toBe(true);
      expect(typeof list.total).toBe('number');
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(BOARDS_LIST_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Mutation: createBoard, updateBoard, deleteBoard', () => {
    const CREATE_BOARD_MUTATION = `
      mutation CreateBoard($input: CreateBoardInput!) {
        createBoard(input: $input) {
          id
          name
          nameEn
          nameRu
          set
          width
          height
        }
      }
    `;

    const UPDATE_BOARD_MUTATION = `
      mutation UpdateBoard($id: String!, $input: UpdateBoardInput!) {
        updateBoard(id: $id, input: $input) {
          id
          name
          width
          height
        }
      }
    `;

    const DELETE_BOARD_MUTATION = `
      mutation DeleteBoard($id: String!) {
        deleteBoard(id: $id)
      }
    `;

    it('полный CRUD цикл для поля', async () => {
      // 1. Создаём
      const createInput = {
        name: `Test Board ${Date.now()}`,
        nameEn: 'Test Board En',
        nameRu: 'Тестовое Поле',
        set: 'test-set',
        width: 6,
        height: 6,
        // Валидная геометрия (createBoard теперь прогоняет validateBoardGeometry):
        // 2x2 решётка с реципрокными связями, зоны из канона.
        cells: JSON.stringify([
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: ['right', 'down'] },
          { x: 1, y: 0, type: 'normal', zone: 'blue', connections: ['left', 'down'] },
          { x: 0, y: 1, type: 'normal', zone: 'blue', connections: ['up', 'right'] },
          { x: 1, y: 1, type: 'normal', zone: 'blue', connections: ['up', 'left'] },
        ]),
        features: JSON.stringify({ doors: [], secretPassages: [], highGround: [] }),
      };

      const createResponse = await gqlRequest(CREATE_BOARD_MUTATION, { input: createInput }, adminToken).expect(200);
      expect(createResponse.body.errors).toBeUndefined();
      expect(createResponse.body.data.createBoard).toBeDefined();

      const board = createResponse.body.data.createBoard;
      expect(board.id).toBeDefined();
      expect(board.name).toBe(createInput.name);
      expect(board.width).toBe(createInput.width);
      expect(board.height).toBe(createInput.height);

      const boardId = board.id;

      // 2. Обновляем
      const updateInput = {
        name: `Updated Board ${Date.now()}`,
        width: 8,
        height: 8,
      };

      const updateResponse = await gqlRequest(
        UPDATE_BOARD_MUTATION,
        { id: boardId, input: updateInput },
        adminToken,
      ).expect(200);

      expect(updateResponse.body.errors).toBeUndefined();
      expect(updateResponse.body.data.updateBoard).toBeDefined();

      const updatedBoard = updateResponse.body.data.updateBoard;
      expect(updatedBoard.id).toBe(boardId);
      expect(updatedBoard.width).toBe(8);
      expect(updatedBoard.height).toBe(8);

      // 3. Удаляем
      const deleteResponse = await gqlRequest(DELETE_BOARD_MUTATION, { id: boardId }, adminToken).expect(200);
      expect(deleteResponse.body.errors).toBeUndefined();
      expect(deleteResponse.body.data.deleteBoard).toBe(true);

      // 4. Проверяем удаление из БД
      const deletedBoard = await prisma.board.findUnique({ where: { id: boardId } });
      expect(deletedBoard).toBeNull();
    });

    it('не даёт создать поле обычному пользователю', async () => {
      const input = {
        name: `Unauthorized Board ${Date.now()}`,
        nameEn: 'Unauthorized',
        nameRu: 'Неавторизованное',
        set: 'test',
        width: 4,
        height: 4,
        cells: '{}',
      };

      const response = await gqlRequest(CREATE_BOARD_MUTATION, { input }, userToken).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('FORBIDDEN');
    });
  });

  describe('Query: user / usersList', () => {
    const USERS_LIST_QUERY = `
      query GetUsersList($page: Int, $limit: Int, $search: String) {
        userList(page: $page, limit: $limit, search: $search) {
          users {
            id
            username
            email
            avatar
            role
            createdAt
            emailVerified
            stats {
              gamesPlayed
              gamesWon
              currentElo
            }
          }
          total
          page
          limit
          totalPages
        }
      }
    `;

    const USER_QUERY = `
      query GetUser($id: String!) {
        user(id: $id) {
          id
          username
          email
          avatar
          role
          createdAt
          emailVerified
          stats {
            gamesPlayed
            gamesWon
            currentElo
          }
        }
      }
    `;

    it('возвращает список пользователей для авторизованного пользователя', async () => {
      const response = await gqlRequest(USERS_LIST_QUERY, { page: 1, limit: 10 }, userToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.userList).toBeDefined();

      const list = response.body.data.userList;
      expect(Array.isArray(list.users)).toBe(true);
      expect(typeof list.total).toBe('number');
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(USERS_LIST_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });

    it('позволяет искать пользователей', async () => {
      const response = await gqlRequest(
        USERS_LIST_QUERY,
        { page: 1, limit: 10, search: 'admin' },
        adminToken,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.userList).toBeDefined();
    });
  });

  describe('Mutation: updateUser, banUser, unbanUser', () => {
    const UPDATE_USER_MUTATION = `
      mutation UpdateUser($id: String!, $input: UpdateUserInput!) {
        updateUser(id: $id, input: $input) {
          id
          username
          avatar
          role
        }
      }
    `;

    const BAN_USER_MUTATION = `
      mutation BanUser($id: String!) {
        banUser(id: $id)
      }
    `;

    const UNBAN_USER_MUTATION = `
      mutation UnbanUser($id: String!) {
        unbanUser(id: $id)
      }
    `;

    it('обновляет пользователя как admin', async () => {
      const input = {
        username: `UpdatedUser${Date.now()}`,
        avatar: 'https://example.com/new-avatar.png',
      };

      const response = await gqlRequest(
        UPDATE_USER_MUTATION,
        { id: testUserId, input },
        adminToken,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.updateUser).toBeDefined();

      const user = response.body.data.updateUser;
      expect(user.id).toBe(testUserId);
      expect(user.username).toBe(input.username);
    });

    it('не даёт обновить пользователя обычному пользователю', async () => {
      const response = await gqlRequest(
        UPDATE_USER_MUTATION,
        { id: testUserId, input: { username: 'Hacked' } },
        userToken,
      ).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('FORBIDDEN');
    });

    it('банит пользователя как admin', async () => {
      const response = await gqlRequest(BAN_USER_MUTATION, { id: testUserId }, adminToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.banUser).toBe(true);
    });

    it('проверяет что пользователь забанен в БД', async () => {
      const user = await prisma.user.findUnique({ where: { id: testUserId } });
      expect(user?.deletedAt).not.toBeNull();
    });

    it('разбанивает пользователя как admin', async () => {
      const response = await gqlRequest(UNBAN_USER_MUTATION, { id: testUserId }, adminToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.unbanUser).toBe(true);
    });

    it('проверяет что пользователь разбанен в БД', async () => {
      const user = await prisma.user.findUnique({ where: { id: testUserId } });
      expect(user?.deletedAt).toBeNull();
    });
  });

  describe('Query: gamesList', () => {
    const GAMES_LIST_QUERY = `
      query GetGamesList($page: Int, $limit: Int) {
        gameList(page: $page, limit: $limit) {
          items {
            id
            status
            createdAt
            boardId
            boardName
            gamePlayers {
              id
              playerId
              heroId
              status
              username
              avatar
            }
          }
          total
          page
          limit
          totalPages
        }
      }
    `;

    it('возвращает список игр для авторизованного пользователя', async () => {
      const response = await gqlRequest(GAMES_LIST_QUERY, { page: 1, limit: 10 }, userToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.gameList).toBeDefined();

      const list = response.body.data.gameList;
      expect(Array.isArray(list.items)).toBe(true);
      expect(typeof list.total).toBe('number');
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(GAMES_LIST_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Query: matchmakingQueue', () => {
    const QUEUE_QUERY = `
      query GetMatchmakingQueue {
        matchmakingQueue {
          items {
            id
            userId
            username
            avatar
            mode
            elo
            joinedAt
            position
          }
          total
          activeQueues
        }
      }
    `;

    it('возвращает очередь для авторизованного пользователя', async () => {
      const response = await gqlRequest(QUEUE_QUERY, {}, userToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.matchmakingQueue).toBeDefined();

      const queue = response.body.data.matchmakingQueue;
      expect(Array.isArray(queue.items)).toBe(true);
      expect(typeof queue.total).toBe('number');
      expect(typeof queue.activeQueues).toBe('number');
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(QUEUE_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Query: auditLogs (только для moderator)', () => {
    const AUDIT_LOGS_QUERY = `
      query GetAuditLogs($page: Int, $limit: Int, $userId: String) {
        auditLogs(page: $page, limit: $limit, userId: $userId) {
          items {
            id
            action
            userId
            ipAddress
            userAgent
            success
            errorMessage
            timestamp
            metadata
          }
          total
        }
      }
    `;

    it('возвращает логи для moderator', async () => {
      const response = await gqlRequest(AUDIT_LOGS_QUERY, { page: 1, limit: 10 }, moderatorToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.auditLogs).toBeDefined();

      const logs = response.body.data.auditLogs;
      expect(Array.isArray(logs.items)).toBe(true);
      expect(typeof logs.total).toBe('number');
    });

    it('возвращает логи для admin', async () => {
      const response = await gqlRequest(AUDIT_LOGS_QUERY, { page: 1, limit: 10 }, adminToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.auditLogs).toBeDefined();
    });

    it('возвращает ошибку для обычного пользователя', async () => {
      const response = await gqlRequest(AUDIT_LOGS_QUERY, {}, userToken).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('FORBIDDEN');
    });

    it('возвращает ошибку без авторизации', async () => {
      const response = await gqlRequest(AUDIT_LOGS_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Валидация входных данных', () => {
    const CREATE_HERO_MUTATION = `
      mutation CreateHero($input: CreateHeroInput!) {
        createHero(input: $input) {
          id
          name
        }
      }
    `;

    it('отклоняет создание героя с невалидными данными', async () => {
      const input = {
        name: '', // пустое имя
        nameEn: '',
        nameRu: '',
        set: '',
        health: -1, // отрицательное здоровье
        fighterType: '',
      };

      const response = await gqlRequest(CREATE_HERO_MUTATION, { input }, adminToken).expect(200);

      expect(response.body.errors).toBeDefined();
    });

    it('отклоняет создание карты без heroId', async () => {
      const CREATE_CARD_MUTATION = `
        mutation CreateCard($input: CreateCardInput!) {
          createCard(input: $input) {
            id
          }
        }
      `;

      const input = {
        name: 'Test Card',
        nameEn: 'Test',
        nameRu: 'Тест',
        heroId: '', // пустой heroId
        cardType: 'ATTACK',
        count: 1,
      };

      const response = await gqlRequest(CREATE_CARD_MUTATION, { input }, adminToken).expect(200);

      expect(response.body.errors).toBeDefined();
    });
  });

  describe('Пагинация', () => {
    const HEROES_LIST_QUERY = `
      query GetHeroesList($page: Int, $limit: Int) {
        heroList(page: $page, limit: $limit) {
          items {
            id
          }
          total
          page
          limit
          totalPages
        }
      }
    `;

    it('корректно работает пагинация', async () => {
      const response1 = await gqlRequest(HEROES_LIST_QUERY, { page: 1, limit: 5 }, adminToken).expect(200);
      const response2 = await gqlRequest(HEROES_LIST_QUERY, { page: 2, limit: 5 }, adminToken).expect(200);

      expect(response1.body.errors).toBeUndefined();
      expect(response2.body.errors).toBeUndefined();

      const list1 = response1.body.data.heroList;
      const list2 = response2.body.data.heroList;

      expect(list1.page).toBe(1);
      expect(list2.page).toBe(2);
      expect(list1.total).toBe(list2.total);
      expect(list1.totalPages).toBe(list2.totalPages);
    });
  });

  describe('GraphQL Schema валидация', () => {
    const INTROSPECTION_QUERY = `
      query Introspection {
        __schema {
          queryType {
            fields {
              name
            }
          }
          mutationType {
            fields {
              name
            }
          }
        }
      }
    `;

    it('содержит все необходимые admin queries', async () => {
      const response = await gqlRequest(INTROSPECTION_QUERY).expect(200);

      expect(response.body.errors).toBeUndefined();

      const queries = response.body.data.__schema.queryType.fields.map((f: any) => f.name);
      const mutations = response.body.data.__schema.mutationType.fields.map((f: any) => f.name);

      // Проверяем admin queries
      expect(queries).toContain('adminStats');
      expect(queries).toContain('adminHero');
      expect(queries).toContain('adminCard');
      expect(queries).toContain('adminBoard');
      expect(queries).toContain('user');
      expect(queries).toContain('userList');
      expect(queries).toContain('heroList');
      expect(queries).toContain('cardList');
      expect(queries).toContain('boardList');
      expect(queries).toContain('gameList');
      expect(queries).toContain('matchmakingQueue');
      expect(queries).toContain('auditLogs');

      // Проверяем admin mutations
      expect(mutations).toContain('createHero');
      expect(mutations).toContain('updateHero');
      expect(mutations).toContain('deleteHero');
      expect(mutations).toContain('createCard');
      expect(mutations).toContain('updateCard');
      expect(mutations).toContain('deleteCard');
      expect(mutations).toContain('createBoard');
      expect(mutations).toContain('updateBoard');
      expect(mutations).toContain('deleteBoard');
      expect(mutations).toContain('updateUser');
      expect(mutations).toContain('banUser');
      expect(mutations).toContain('unbanUser');
    });
  });
});
