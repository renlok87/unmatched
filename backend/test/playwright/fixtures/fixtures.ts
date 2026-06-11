/**
 * Main Fixtures
 *
 * Композиция всех фикстур для E2E тестов.
 * Адаптировано из паттерна alix1912/e2e.
 *
 * Использование:
 *
 * ```typescript
 * import { test, expect } from './fixtures/fixtures';
 *
 * test('my test', async ({ page, loginAs, createGame }) => {
 *   await loginAs('player1');
 *   const gameId = await createGame();
 *   // ...
 * });
 * ```
 */

import { test as base } from '@playwright/test';
import { authFixtures, AuthFixtures } from './auth.fixture';
import { playerFixtures, PlayerFixtures } from './player.fixture';
import { gameFixtures, GameFixtures } from './game.fixture';

// ============================================================
// Composed Fixtures Type
// ============================================================

export type Fixtures = AuthFixtures & PlayerFixtures & GameFixtures;

// ============================================================
// Composed Test
// ============================================================

/**
 * Главный test объект со всеми фикстурами
 *
 * Доступные фикстуры:
 *
 * **Auth:**
 * - createUser: создание нового пользователя
 * - createRandomUser: создание пользователя со случайными данными
 * - loginAs: быстрый логин через storage state
 * - loginWithCredentials: логин через email/password
 * - authenticatedPage: страница с готовой авторизацией
 * - api: API клиент с токеном
 *
 * **Player:**
 * - createMultiplayerGame: создание игры с двумя игроками
 * - createThreePlayerGame: создание игры с тремя игроками
 * - createContextWithRole: контекст для конкретной роли
 * - createPageWithRole: страница для конкретной роли
 *
 * **Game:**
 * - createGame: создание новой игры
 * - joinGame: присоединение к игре
 * - createAndWaitForOpponent: создание игры и ожидание оппонента
 * - executeManeuver: выполнение манёвра
 * - executeAttack: выполнение атаки
 * - executeDefense: выполнение защиты
 * - executeResolveCombat: разрешение боя
 * - executeEndTurn: завершение хода
 * - mockGameState: mock состояние игры
 * - setup1v1Game: быстрое создание 1v1 игры
 */
export const test = base
  .extend<AuthFixtures>(authFixtures)
  .extend<PlayerFixtures>(playerFixtures)
  .extend<GameFixtures>(gameFixtures);

// ============================================================
// Re-export expect
// ============================================================

export const expect = base.expect;

// ============================================================
// Test Tags (для организации тестов)
// ============================================================

/**
 * Теги для группировки тестов
 *
 * Использование:
 * ```typescript
 * test.describe('Auth', { tag: ['@smoke', '@auth'] }, () => {
 *   test('login works', async ({ page }) => { ... });
 * });
 * ```
 */
export const TAGS = {
  SMOKE: '@smoke',
  CRITICAL: '@critical',
  REGRESSION: '@regression',

  AUTH: '@auth',
  GAME: '@game',
  UI: '@ui',

  SINGLEPLAYER: '@singleplayer',
  MULTIPLAYER: '@multiplayer',

  FAST: '@fast',
  SLOW: '@slow',
} as const;
