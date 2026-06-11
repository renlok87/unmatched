/**
 * Player Fixture
 *
 * Мульти-ролевая фикстура для тестирования сценариев с несколькими игроками.
 * Адаптировано из паттерна alix1912/e2e.
 *
 * Позволяет создавать несколько браузеров с разными авторизованными пользователями
 * для тестирования мультиплеерных сценариев.
 */

import { test as base, BrowserContext, Page, Browser } from '@playwright/test';
import { resolve } from 'path';
import { URLS, STORAGE_STATES, TEST_USERS, HEROES } from './data';

// ============================================================
// Types
// ============================================================

interface MultiplayerContext {
  gameId: string;
  player1Context: BrowserContext;
  player2Context: BrowserContext;
  player1Page: Page;
  player2Page: Page;
  player1Id: string;
  player2Id: string;
}

type PlayerFixtures = {
  /**
   * Создаёт мультиплеерную игру с двумя авторизованными игроками
   */
  createMultiplayerGame: () => Promise<MultiplayerContext>;

  /**
   * Создаёт три контекста для 3-х игроков
   */
  createThreePlayerGame: () => Promise<{
    gameId: string;
    contexts: BrowserContext[];
    pages: Page[];
    userIds: string[];
  }>;

  /**
   * Создаёт браузерный контекст с конкретным storage state
   */
  createContextWithRole: (
    browser: Browser,
    role: 'player1' | 'player2' | 'player3',
  ) => Promise<BrowserContext>;

  /**
   * Создаёт страницу с конкретным storage state
   */
  createPageWithRole: (
    browser: Browser,
    role: 'player1' | 'player2' | 'player3',
  ) => Promise<Page>;
};

// ============================================================
// Player Fixtures
// ============================================================

export const playerFixtures = {
  // --------------------------------------------------------
  // createMultiplayerGame
  // --------------------------------------------------------
  createMultiplayerGame: async ({ browser }, use) => {
    const contexts: BrowserContext[] = [];

    await use(async () => {
      // Создаём контексты для двух игроков
      const player1Context = await createContextForRole(browser, 'player1');
      const player2Context = await createContextForRole(browser, 'player2');

      contexts.push(player1Context, player2Context);

      // Создаём страницы
      const player1Page = await player1Context.newPage();
      const player2Page = await player2Context.newPage();

      // Оба игрока переходят на главную страницу
      await player1Page.goto(URLS.BASE);
      await player2Page.goto(URLS.BASE);

      // Получаем userId из localStorage
      const player1Id = await player1Page.evaluate(() => {
        const userStr = localStorage.getItem('user');
        if (userStr) {
          return JSON.parse(userStr).id;
        }
        return '';
      });

      const player2Id = await player2Page.evaluate(() => {
        const userStr = localStorage.getItem('user');
        if (userStr) {
          return JSON.parse(userStr).id;
        }
        return '';
      });

      // Генерируем ID игры
      const gameId = `test-game-${Date.now()}`;

      return {
        gameId,
        player1Context,
        player2Context,
        player1Page,
        player2Page,
        player1Id,
        player2Id,
      };
    });

    // Cleanup
    for (const context of contexts) {
      await context.close();
    }
  },

  // --------------------------------------------------------
  // createThreePlayerGame
  // --------------------------------------------------------
  createThreePlayerGame: async ({ browser }, use) => {
    const contexts: BrowserContext[] = [];

    await use(async () => {
      // Создаём контексты для трёх игроков
      const context1 = await createContextForRole(browser, 'player1');
      const context2 = await createContextForRole(browser, 'player2');
      const context3 = await createContextForRole(browser, 'player3');

      contexts.push(context1, context2, context3);

      // Создаём страницы
      const page1 = await context1.newPage();
      const page2 = await context2.newPage();
      const page3 = await context3.newPage();

      // Все игроки переходят на главную страницу
      await Promise.all([
        page1.goto(URLS.BASE),
        page2.goto(URLS.BASE),
        page3.goto(URLS.BASE),
      ]);

      // Получаем userId
      const userIds = await Promise.all([
        page1.evaluate(() => {
          const userStr = localStorage.getItem('user');
          return userStr ? JSON.parse(userStr).id : '';
        }),
        page2.evaluate(() => {
          const userStr = localStorage.getItem('user');
          return userStr ? JSON.parse(userStr).id : '';
        }),
        page3.evaluate(() => {
          const userStr = localStorage.getItem('user');
          return userStr ? JSON.parse(userStr).id : '';
        }),
      ]);

      const gameId = `test-game-${Date.now()}`;

      return {
        gameId,
        contexts: [context1, context2, context3],
        pages: [page1, page2, page3],
        userIds,
      };
    });

    // Cleanup
    for (const context of contexts) {
      await context.close();
    }
  },

  // --------------------------------------------------------
  // createContextWithRole
  // --------------------------------------------------------
  createContextWithRole: async ({ browser }, use) => {
    await use(async (role: 'player1' | 'player2' | 'player3') => {
      return await createContextForRole(browser, role);
    });
  },

  // --------------------------------------------------------
  // createPageWithRole
  // --------------------------------------------------------
  createPageWithRole: async ({ browser }, use) => {
    const contexts: BrowserContext[] = [];

    await use(async (role: 'player1' | 'player2' | 'player3') => {
      const context = await createContextForRole(browser, role);
      contexts.push(context);

      const page = await context.newPage();
      await page.goto(URLS.BASE);

      return page;
    });

    // Cleanup
    for (const context of contexts) {
      await context.close();
    }
  },
};

// ============================================================
// Helper Functions
// ============================================================

/**
 * Создаёт контекст браузера с storage state для роли
 */
async function createContextForRole(
  browser: Browser,
  role: 'player1' | 'player2' | 'player3',
): Promise<BrowserContext> {
  const storagePath = resolve(__dirname, STORAGE_STATES[role.toUpperCase() as keyof typeof STORAGE_STATES]);

  return await browser.newContext({
    storageStatePath: storagePath,
  });
}

// Экспортируем расширенный test
export const test = base.extend<PlayerFixtures>(playerFixtures);
