/**
 * Auth Fixture
 *
 * Фикстура для авторизации в тестах.
 * Адаптировано из паттерна alix1912/e2e с storage state кэшированием.
 *
 * Предоставляет:
 * - createUser: создание нового пользователя
 * - loginAs: быстрый логин через storage state
 * - createAuthenticatedPage: создание страницы с готовой авторизацией
 */

import { test as base, Page } from '@playwright/test';
import { resolve } from 'path';
import { URLS, TEST_USERS, STORAGE_STATES } from './data';
import { ApiService, RegisterDto } from '../src/services/api.service';

// ============================================================
// Types
// ============================================================

type AuthFixtures = {
  /**
   * Создаёт нового пользователя через API
   */
  createUser: (userData: { email: string; username: string; password: string }) => Promise<{
    id: string;
    email: string;
    username: string;
    token: string;
  }>;

  /**
   * Создаёт пользователя со случайными данными
   */
  createRandomUser: () => Promise<{
    id: string;
    email: string;
    username: string;
    password: string;
    token: string;
  }>;

  /**
   * Логинит пользователя через storage state (быстро)
   */
  loginAs: (role: 'player1' | 'player2' | 'player3') => Promise<void>;

  /**
   * Логинит пользователя через email/password
   */
  loginWithCredentials: (email: string, password: string) => Promise<void>;

  /**
   * Создаёт страницу с готовой авторизацией (используя storage state)
   */
  authenticatedPage: Page;

  /**
   * API клиент с токеном авторизации
   */
  api: ApiService;
};

// ============================================================
// Helper Functions
// ============================================================

/**
 * Проверяет существование storage state файла
 */
function storageStateExists(role: string): boolean {
  const fs = require('fs');
  const storagePath = resolve(__dirname, `storage-states/${role}.json`);
  return fs.existsSync(storagePath);
}

/**
 * Загружает storage state из файла
 */
function loadStorageState(role: string): object | null {
  const fs = require('fs');
  const storagePath = resolve(__dirname, `storage-states/${role}.json`);

  if (!fs.existsSync(storagePath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(storagePath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

// ============================================================
// Auth Fixtures
// ============================================================

export const authFixtures = {
  // --------------------------------------------------------
  // createUser
  // --------------------------------------------------------
  createUser: async ({}, use) => {
    const users: Array<{
      id: string;
      email: string;
      username: string;
      token: string;
    }> = [];

    await use(async (userData: { email: string; username: string; password: string }) => {
      const api = new ApiService();

      try {
        // Пробуем зарегистрировать
        const response = await api.register(userData as RegisterDto);
        const user = {
          id: response.user.id,
          email: response.user.email,
          username: response.user.username,
          token: response.accessToken,
        };
        users.push(user);
        return user;
      } catch (error) {
        // Если пользователь уже существует, логинимся
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (errorMessage.includes('already exists') || errorMessage.includes('exists')) {
          const response = await api.login({
            email: userData.email,
            password: userData.password,
          });
          const user = {
            id: response.user.id,
            email: response.user.email,
            username: response.user.username,
            token: response.accessToken,
          };
          users.push(user);
          return user;
        }
        throw error;
      }
    });

    // Cleanup: удаляем созданных пользователей (опционально)
    // В реальном проекте можно добавить API для удаления тестовых пользователей
  },

  // --------------------------------------------------------
  // createRandomUser
  // --------------------------------------------------------
  createRandomUser: async ({ createUser }, use) => {
    await use(async () => {
      const suffix = Math.random().toString(36).substring(7);
      const userData = {
        email: `e2e-${suffix}@example.com`,
        username: `e2e-${suffix}`,
        password: 'TestPassword123!',
      };

      const user = await createUser(userData);
      return {
        ...user,
        password: userData.password,
      };
    });
  },

  // --------------------------------------------------------
  // loginAs (storage state кэширование)
  // --------------------------------------------------------
  loginAs: async ({ page }, use) => {
    await use(async (role: 'player1' | 'player2' | 'player3') => {
      const storageState = loadStorageState(role);

      if (!storageState) {
        throw new Error(
          `Storage state for ${role} not found. Run global-setup first or set SKIP_STORAGE_SETUP=false.`,
        );
      }

      // Загружаем storage state в контекст
      await page.goto(URLS.BASE);

      // Применяем localStorage и cookies
      const url = new URL(URLS.BASE);

      // Cookies
      if ('cookies' in storageState) {
        const cookies = (storageState as any).cookies || [];
        for (const cookie of cookies) {
          await page.context().addCookies([
            {
              ...cookie,
              domain: cookie.domain || url.hostname,
            },
          ]);
        }
      }

      // localStorage
      if ('origins' in storageState) {
        const origins = (storageState as any).origins || [];
        for (const origin of origins) {
          if (origin.origin === URLS.BASE || origin.origin === `${URLS.BASE}/`) {
            for (const item of origin.localStorage || []) {
              await page.evaluate(
                (data) => {
                  localStorage.setItem(data.name, data.value);
                },
                { name: item.name, value: item.value },
              );
            }
          }
        }
      }

      // Перезагружаем страницу для применения изменений
      await page.reload();
    });
  },

  // --------------------------------------------------------
  // loginWithCredentials
  // --------------------------------------------------------
  loginWithCredentials: async ({ page }, use) => {
    await use(async (email: string, password: string) => {
      await page.goto(URLS.LOGIN);

      // Заполняем форму логина
      await page.fill('[name="email"]', email);
      await page.fill('[name="password"]', password);
      await page.click('button[type="submit"]');

      // Ждём перенаправления на главную страницу
      await page.waitForURL(URLS.BASE, { timeout: 10000 });
    });
  },

  // --------------------------------------------------------
  // authenticatedPage (страница с готовой авторизацией)
  // --------------------------------------------------------
  authenticatedPage: async ({ browser }, use) => {
    // Создаём контекст с storage state для player1
    const storagePath = resolve(__dirname, STORAGE_STATES.PLAYER1);

    const context = await browser.newContext({
      storageStatePath: storagePath,
    });

    const page = await context.newPage();
    await use(page);

    // Cleanup
    await context.close();
  },

  // --------------------------------------------------------
  // api (API клиент с токеном)
  // --------------------------------------------------------
  api: async ({ authenticatedPage }, use) => {
    // Получаем токен из localStorage
    const token = await authenticatedPage.evaluate(() => {
      return localStorage.getItem('auth_token') || localStorage.getItem('token') || '';
    });

    const api = new ApiService(token);
    await use(api);
  },
};

// Экспортируем расширенный test
export const test = base.extend<AuthFixtures>(authFixtures);
