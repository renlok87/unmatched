import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/database/prisma.service';
import { RedisService } from '../src/redis/redis.service';

describe('Users API (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let redis: RedisService;

  let authToken: string;
  let testUserId: string;
  let testUsername: string;
  let testEmail: string;

  const generateTestData = (suffix: string) => ({
    email: `user-${suffix}-${Date.now()}@example.com`,
    username: `user-${suffix}-${Date.now()}`,
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
    testUsername = userData.user.username;
    testEmail = userData.user.email;
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

  describe('Query: me', () => {
    const ME_QUERY = `
      query Me {
        me {
          id
          email
          username
          avatar
          createdAt
          settings {
            theme
            soundEnabled
            musicEnabled
            language
            profileVisible
          }
        }
      }
    `;

    it('успешное получение данных текущего пользователя', async () => {
      const response = await gqlRequest(ME_QUERY, {}, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.me).toBeDefined();

      const { me } = response.body.data;
      expect(me.id).toBe(testUserId);
      expect(me.email).toBe(testEmail);
      expect(me.username).toBe(testUsername);
      expect(me.settings).toBeDefined();
      expect(me.settings.theme).toBeDefined();
    });

    it('ошибка при запросе без токена', async () => {
      const response = await gqlRequest(ME_QUERY).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].extensions?.code).toBe('UNAUTHENTICATED');
    });
  });

  describe('Query: user', () => {
    const USER_QUERY = `
      query User($id: ID!) {
        user(id: $id) {
          id
          username
          avatar
          createdAt
        }
      }
    `;

    it('успешное получение публичного профиля', async () => {
      const response = await gqlRequest(USER_QUERY, { id: testUserId }).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.user).toBeDefined();

      const { user } = response.body.data;
      expect(user.id).toBe(testUserId);
      expect(user.username).toBe(testUsername);
      expect(user.email).toBeUndefined();
    });

    it('профиль скрыт если настройка profileVisible = false', async () => {
      const UPDATE_SETTINGS_MUTATION = `
        mutation UpdateSettings($input: SettingsDto!) {
          updateSettings(input: $input) {
            profileVisible
          }
        }
      `;

      await gqlRequest(UPDATE_SETTINGS_MUTATION, { input: { profileVisible: false } }, authToken);

      const response = await gqlRequest(USER_QUERY, { id: testUserId }).expect(200);

      expect(response.body.data.user.username).toBe('Hidden');
    });

    it('владелец видит свой профиль даже если скрыт', async () => {
      const response = await gqlRequest(USER_QUERY, { id: testUserId }, authToken).expect(200);

      expect(response.body.data.user.username).toBe(testUsername);
    });
  });

  describe('Query: userByUsername', () => {
    const USER_BY_USERNAME_QUERY = `
      query UserByUsername($username: String!) {
        userByUsername(username: $username) {
          id
          username
          avatar
          createdAt
        }
      }
    `;

    it('успешный поиск пользователя по username', async () => {
      const response = await gqlRequest(USER_BY_USERNAME_QUERY, { username: testUsername }).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.userByUsername).toBeDefined();
      expect(response.body.data.userByUsername.id).toBe(testUserId);
    });

    it('ошибка при несуществующем username', async () => {
      const response = await gqlRequest(USER_BY_USERNAME_QUERY, { username: 'nonexistent' }).expect(200);

      expect(response.body.data.userByUsername).toBeNull();
    });
  });

  describe('Query: myStats', () => {
    const MY_STATS_QUERY = `
      query MyStats {
        myStats {
          totalGames
          wins
          losses
          draws
          winRate
          currentElo
          peakElo
          longestWinStreak
          longestLoseStreak
        }
      }
    `;

    it('успешное получение статистики', async () => {
      const response = await gqlRequest(MY_STATS_QUERY, {}, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.myStats).toBeDefined();

      const stats = response.body.data.myStats;
      expect(stats.totalGames).toBeGreaterThanOrEqual(0);
      expect(stats.currentElo).toBeGreaterThanOrEqual(0);
      expect(typeof stats.winRate).toBe('number');
    });

    it('статистика содержит все поля', async () => {
      const response = await gqlRequest(MY_STATS_QUERY, {}, authToken).expect(200);

      const stats = response.body.data.myStats;
      const requiredFields = [
        'totalGames',
        'wins',
        'losses',
        'draws',
        'winRate',
        'currentElo',
        'peakElo',
        'longestWinStreak',
        'longestLoseStreak',
      ];

      requiredFields.forEach((field) => {
        expect(stats).toHaveProperty(field);
      });
    });
  });

  describe('Query: stats', () => {
    const STATS_QUERY = `
      query Stats($userId: ID!) {
        stats(userId: $userId) {
          totalGames
          wins
          losses
          currentElo
        }
      }
    `;

    it('успешное получение публичной статистики', async () => {
      const response = await gqlRequest(STATS_QUERY, { userId: testUserId }).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.stats).toBeDefined();
    });
  });

  describe('Query: mySettings', () => {
    const MY_SETTINGS_QUERY = `
      query MySettings {
        mySettings {
          theme
          soundEnabled
          musicEnabled
          language
          profileVisible
        }
      }
    `;

    it('успешное получение настроек', async () => {
      const response = await gqlRequest(MY_SETTINGS_QUERY, {}, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.mySettings).toBeDefined();

      const settings = response.body.data.mySettings;
      expect(settings).toHaveProperty('theme');
      expect(settings).toHaveProperty('soundEnabled');
      expect(settings).toHaveProperty('musicEnabled');
      expect(settings).toHaveProperty('language');
      expect(settings).toHaveProperty('profileVisible');
    });
  });

  describe('Mutation: updateProfile', () => {
    const UPDATE_PROFILE_MUTATION = `
      mutation UpdateProfile($input: UpdateProfileDto!) {
        updateProfile(input: $input) {
          id
          username
          avatar
        }
      }
    `;

    it('успешное обновление username', async () => {
      const newUsername = `updated-${Date.now()}`;

      const response = await gqlRequest(
        UPDATE_PROFILE_MUTATION,
        { input: { username: newUsername } },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.updateProfile.username).toBe(newUsername);
    });

    it('ошибка при дубликате username', async () => {
      const otherUser = await createAuthenticatedUser('other');

      const response = await gqlRequest(
        UPDATE_PROFILE_MUTATION,
        { input: { username: otherUser.user.username } },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeDefined();
      expect(response.body.errors[0].message).toContain('уже существует');
    });

    it('rate limiting - ограничение 5 запросов в минуту', async () => {
      const requests = [];
      for (let i = 0; i < 7; i++) {
        requests.push(
          gqlRequest(UPDATE_PROFILE_MUTATION, { input: { username: `test${i}-${Date.now()}` } }, authToken),
        );
      }

      const responses = await Promise.all(requests);
      const throttled = responses.filter(
        (r: any) => r.body.errors?.[0]?.message?.includes('Too Many Requests') || r.body.errors?.[0]?.extensions?.code === 'TOO_MANY_REQUESTS',
      );

      expect(throttled.length).toBeGreaterThan(0);
    });
  });

  describe('Mutation: updateSettings', () => {
    const UPDATE_SETTINGS_MUTATION = `
      mutation UpdateSettings($input: SettingsDto!) {
        updateSettings(input: $input) {
          theme
          soundEnabled
          musicEnabled
          language
          profileVisible
        }
      }
    `;

    it('успешное обновление всех настроек', async () => {
      const settings = {
        theme: 'dark',
        soundEnabled: false,
        musicEnabled: true,
        language: 'ru',
        profileVisible: true,
      };

      const response = await gqlRequest(UPDATE_SETTINGS_MUTATION, { input: settings }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.updateSettings).toMatchObject(settings);
    });

    it('частичное обновление настроек', async () => {
      const response = await gqlRequest(
        UPDATE_SETTINGS_MUTATION,
        { input: { theme: 'light' } },
        authToken,
      ).expect(200);

      expect(response.body.data.updateSettings.theme).toBe('light');
    });
  });

  describe('Mutation: changePassword', () => {
    const CHANGE_PASSWORD_MUTATION = `
      mutation ChangePassword($input: ChangePasswordDto!) {
        changePassword(input: $input)
      }
    `;

    it('успешная смена пароля', async () => {
      const newPassword = `NewPassword${Date.now()}!`;

      const response = await gqlRequest(
        CHANGE_PASSWORD_MUTATION,
        { input: { currentPassword: 'TestPassword123!', newPassword } },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.changePassword).toBe(true);

      const LOGIN_MUTATION = `
        mutation Login($input: LoginDto!) {
          login(input: $input) {
            accessToken
          }
        }
      `;

      const loginResponse = await gqlRequest(LOGIN_MUTATION, {
        input: { email: testEmail, password: newPassword },
      }).expect(200);

      expect(loginResponse.body.errors).toBeUndefined();
      expect(loginResponse.body.data.login.accessToken).toBeDefined();

      authToken = loginResponse.body.data.login.accessToken;
    });

    it('ошибка при неверном текущем пароле', async () => {
      const response = await gqlRequest(
        CHANGE_PASSWORD_MUTATION,
        { input: { currentPassword: 'WrongPassword123!', newPassword: 'NewPassword123!' } },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeDefined();
    });

    it('rate limiting - ограничение 3 запроса в минуту', async () => {
      const requests = [];
      for (let i = 0; i < 5; i++) {
        requests.push(
          gqlRequest(
            CHANGE_PASSWORD_MUTATION,
            { input: { currentPassword: 'TestPassword123!', newPassword: `New${i}!` } },
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

  describe('Mutation: uploadAvatar', () => {
    const UPLOAD_AVATAR_MUTATION = `
      mutation UploadAvatar($fileUrl: String!) {
        uploadAvatar(fileUrl: $fileUrl)
      }
    `;

    it('успешная загрузка аватара', async () => {
      const fileUrl = `https://example.com/avatar-${Date.now()}.jpg`;

      const response = await gqlRequest(UPLOAD_AVATAR_MUTATION, { fileUrl }, authToken).expect(200);

      expect(response.body.errors).toBeUndefined();
      expect(response.body.data.uploadAvatar).toBe(fileUrl);

      const ME_QUERY = `
        query Me {
          me {
            avatar
          }
        }
      `;

      const meResponse = await gqlRequest(ME_QUERY, {}, authToken).expect(200);
      expect(meResponse.body.data.me.avatar).toBe(fileUrl);
    });
  });

  describe('Mutation: removeAvatar', () => {
    const REMOVE_AVATAR_MUTATION = `
      mutation RemoveAvatar {
        removeAvatar
      }
    `;

    it('успешное удаление аватара', async () => {
      await gqlRequest(REMOVE_AVATAR_MUTATION, {}, authToken).expect(200);

      const ME_QUERY = `
        query Me {
          me {
            avatar
          }
        }
      `;

      const response = await gqlRequest(ME_QUERY, {}, authToken).expect(200);
      expect(response.body.data.me.avatar).toBeNull();
    });
  });

  describe('Интеграционные тесты', () => {
    it('аватар обновляется при updateProfile', async () => {
      const fileUrl = `https://example.com/avatar-${Date.now()}.jpg`;

      await gqlRequest(
        `
        mutation UploadAvatar($fileUrl: String!) {
          uploadAvatar(fileUrl: $fileUrl)
        }
      `,
        { fileUrl },
        authToken,
      );

      const ME_QUERY = `
        query Me {
          me {
            avatar
          }
        }
      `;

      const response = await gqlRequest(ME_QUERY, {}, authToken).expect(200);
      expect(response.body.data.me.avatar).toBe(fileUrl);
    });

    it('настройки приватности влияют на публичный профиль', async () => {
      const UPDATE_SETTINGS_MUTATION = `
        mutation UpdateSettings($input: SettingsDto!) {
          updateSettings(input: $input) {
            profileVisible
          }
        }
      `;

      await gqlRequest(UPDATE_SETTINGS_MUTATION, { input: { profileVisible: true } }, authToken);

      const USER_QUERY = `
        query User($id: ID!) {
          user(id: $id) {
            username
          }
        }
      `;

      const response = await gqlRequest(USER_QUERY, { id: testUserId }).expect(200);
      expect(response.body.data.user.username).not.toBe('Hidden');
    });
  });

  describe('Валидация данных', () => {
    it('username не может быть пустым', async () => {
      const UPDATE_PROFILE_MUTATION = `
        mutation UpdateProfile($input: UpdateProfileDto!) {
          updateProfile(input: $input) {
            id
          }
        }
      `;

      const response = await gqlRequest(UPDATE_PROFILE_MUTATION, { input: { username: '' } }, authToken).expect(200);

      expect(response.body.errors).toBeDefined();
    });

    it('пароль должен соответствовать требованиям сложности', async () => {
      const CHANGE_PASSWORD_MUTATION = `
        mutation ChangePassword($input: ChangePasswordDto!) {
          changePassword(input: $input)
        }
      `;

      const response = await gqlRequest(
        CHANGE_PASSWORD_MUTATION,
        { input: { currentPassword: 'TestPassword123!', newPassword: 'simple' } },
        authToken,
      ).expect(200);

      expect(response.body.errors).toBeDefined();
    });
  });

  describe('Кеширование', () => {
    it('профиль кешируется в Redis', async () => {
      const ME_QUERY = `
        query Me {
          me {
            id
            username
          }
        }
      `;

      await gqlRequest(ME_QUERY, {}, authToken).expect(200);

      const cached = await redis.getUserFromCache(`user:${testUserId}`);
      expect(cached).toBeDefined();
    });

    it('кешируется статистика пользователя', async () => {
      const MY_STATS_QUERY = `
        query MyStats {
          myStats {
            totalGames
            currentElo
          }
        }
      `;

      await gqlRequest(MY_STATS_QUERY, {}, authToken).expect(200);

      const cached = await redis.getUserFromCache(`stats:${testUserId}`);
      expect(cached).toBeDefined();
    });
  });
});