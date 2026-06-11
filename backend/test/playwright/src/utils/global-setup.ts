/**
 * Global Setup для Playwright E2E тестов
 *
 * Создаёт storage states для тестовых пользователей.
 * Адаптировано из паттерна alix1912/e2e для быстрой авторизации в тестах.
 *
 * Storage state позволяет кэшировать авторизованные сессии,
 * чтобы не логиниться перед каждым тестом.
 */

import { FullConfig, chromium } from '@playwright/test';
import { mkdirSync, existsSync, writeFileSync } from 'fs';
import { resolve } from 'path';
import { URLS, TEST_USERS, STORAGE_STATES } from '../../fixtures/data';
import type { RegisterDto, LoginDto } from '../services/api.service';

// ============================================================
// Storage State Generation
// ============================================================

interface StorageState {
  cookies: Array<{
    name: string;
    value: string;
    domain: string;
    path: string;
    expires: number;
    httpOnly: boolean;
    secure: boolean;
    sameSite: 'Strict' | 'Lax' | 'None';
  }>;
  origins: Array<{
    origin: string;
    localStorage: Array<{ name: string; value: string }>;
  }>;
}

/**
 * Создаёт директорию для storage states если не существует
 */
function ensureStorageDir(): void {
  const storageDir = resolve(__dirname, '../../storage-states');
  if (!existsSync(storageDir)) {
    mkdirSync(storageDir, { recursive: true });
  }
}

/**
 * Регистрирует нового пользователя через GraphQL
 */
async function registerUser(userData: { email: string; username: string; password: string }): Promise<string> {
  const response = await fetch(URLS.GRAPHQL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: `mutation Register($input: RegisterDto!) {
        register(input: $input) {
          accessToken
          refreshToken
          user {
            id
            email
            username
          }
        }
      }`,
      variables: {
        input: {
          email: userData.email,
          username: userData.username,
          password: userData.password,
        } as RegisterDto,
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to register user: ${response.status}`);
  }

  const result = await response.json();

  if (result.errors) {
    // Если пользователь уже существует, пробуем логин
    if (result.errors[0]?.message?.includes('already exists')) {
      return await loginUser(userData);
    }
    throw new Error(`Registration failed: ${result.errors[0].message}`);
  }

  return result.data.register.accessToken;
}

/**
 * Логинит пользователя через GraphQL
 */
async function loginUser(userData: { email: string; password: string }): Promise<string> {
  const response = await fetch(URLS.GRAPHQL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: `mutation Login($input: LoginDto!) {
        login(input: $input) {
          accessToken
          refreshToken
          user {
            id
            email
            username
          }
        }
      }`,
      variables: {
        input: {
          email: userData.email,
          password: userData.password,
        } as LoginDto,
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to login user: ${response.status}`);
  }

  const result = await response.json();

  if (result.errors) {
    throw new Error(`Login failed: ${result.errors[0].message}`);
  }

  return result.data.login.accessToken;
}

/**
 * Создаёт storage state для пользователя с помощью браузера
 *
 * Это более надёжный способ чем ручная генерация JSON,
 * т.к. браузер сам сохранит все нужные данные.
 */
async function createStorageStateForUser(
  username: string,
  userData: { email: string; username: string; password: string },
  filename: string,
): Promise<void> {
  console.log(`Creating storage state for ${username}...`);

  // Получаем токен через API
  let token: string;
  try {
    token = await registerUser(userData);
  } catch (error) {
    console.warn(`Registration failed for ${username}, trying login...`);
    token = await loginUser({ email: userData.email, password: userData.password });
  }

  // Запускаем браузер для создания storage state
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Переходим на фронтенд
    await page.goto(URLS.BASE);

    // Устанавливаем токен в localStorage
    await page.evaluate((accessToken) => {
      localStorage.setItem('auth_token', accessToken);
      localStorage.setItem('token', accessToken);
    }, token);

    // Также можно установить через cookie
    const url = new URL(URLS.BASE);
    await context.addCookies([
      {
        name: 'auth_token',
        value: token,
        domain: url.hostname,
        path: '/',
        expires: Date.now() / 1000 + 365 * 24 * 60 * 60, // 1 год
        httpOnly: false,
        secure: false,
        sameSite: 'Lax',
      },
    ]);

    // Сохраняем storage state
    const storageDir = resolve(__dirname, '../../storage-states');
    const storagePath = resolve(storageDir, filename);

    await page.context().storageState({ path: storagePath });

    console.log(`✓ Storage state saved: ${filename}`);
  } finally {
    await browser.close();
  }
}

/**
 * Альтернативный метод - создаёт storage state напрямую через GraphQL
 * Без запуска браузера (быстрее, но менее надёжно для сложных случаев)
 */
async function createStorageStateDirect(
  username: string,
  userData: { email: string; username: string; password: string },
  filename: string,
): Promise<void> {
  console.log(`Creating storage state (direct) for ${username}...`);

  // Получаем токен через API
  let token: string;
  try {
    token = await registerUser(userData);
  } catch (error) {
    console.warn(`Registration failed for ${username}, trying login...`);
    token = await loginUser({ email: userData.email, password: userData.password });
  }

  // Создаём storage state вручную
  const url = new URL(URLS.BASE);
  const storageState: StorageState = {
    cookies: [
      {
        name: 'auth_token',
        value: token,
        domain: url.hostname,
        path: '/',
        expires: Date.now() / 1000 + 365 * 24 * 60 * 60,
        httpOnly: false,
        secure: url.protocol === 'https:',
        sameSite: 'Lax',
      },
    ],
    origins: [
      {
        origin: URLS.BASE,
        localStorage: [
          { name: 'auth_token', value: token },
          { name: 'token', value: token },
        ],
      },
    ],
  };

  // Сохраняем в файл
  const storageDir = resolve(__dirname, '../../storage-states');
  const storagePath = resolve(storageDir, filename);
  writeFileSync(storagePath, JSON.stringify(storageState, null, 2));

  console.log(`✓ Storage state saved: ${filename}`);
}

// ============================================================
// Main Setup Function
// ============================================================

async function createStorageStates(): Promise<void> {
  ensureStorageDir();

  console.log('='.repeat(60));
  console.log('Creating storage states for E2E tests...');
  console.log('='.repeat(60));

  // Используем прямой метод для скорости
  await createStorageStateDirect('player1', TEST_USERS.PLAYER1, 'player1.json');
  await createStorageStateDirect('player2', TEST_USERS.PLAYER2, 'player2.json');
  await createStorageStateDirect('player3', TEST_USERS.PLAYER3, 'player3.json');

  console.log('='.repeat(60));
  console.log('✓ All storage states created successfully!');
  console.log('='.repeat(60));
}

// ============================================================
// Export для Playwright
// ============================================================

export default async function globalSetup(config: FullConfig): Promise<void> {
  // Пропускаем если backend не запущен (для локальной разработки)
  const skipSetup = process.env.SKIP_STORAGE_SETUP === 'true';

  if (skipSetup) {
    console.log('Skipping storage state creation (SKIP_STORAGE_SETUP=true)');
    return;
  }

  try {
    await createStorageStates();
  } catch (error) {
    console.error('Failed to create storage states:', error);
    // Не выбрасываем ошибку, чтобы тесты могли запуститься
    // с альтернативным методом авторизации
  }
}
