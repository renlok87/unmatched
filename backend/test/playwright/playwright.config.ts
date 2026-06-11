/**
 * Playwright E2E Test Configuration for Unmatched
 *
 * Адаптировано из архитектуры alix1912/e2e:
 * - Storage state кэширование для быстрой авторизации
 * - Multi-role fixtures для мультиплеера
 * - Test tags для группировки тестов
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // Директория с тестами
  testDir: './e2e',

  // Артефакты тестов (screenshot, trace, video)
  outputDir: './playwright-artifacts',

  // Global setup для создания storage states
  // Отключено т.к. storage states уже созданы вручную:
  // globalSetup: './src/utils/global-setup.ts',

  // Параллельный запуск
  fullyParallel: true,

  // Запрещаем .only в CI
  forbidOnly: !!process.env.CI,

  // Retry при ошибках
  retries: process.env.TEST_RETRIES ? parseInt(process.env.TEST_RETRIES, 10) : 2,

  // Количество воркеров
  workers: process.env.CI ? 1 : 4,

  // Таймаут для тестов
  timeout: 60 * 1000,

  // Настройки для каждого теста
  use: {
    // Screenshot только при ошибках
    screenshot: 'only-on-failure',

    // Video только при ошибках
    video: 'retain-on-failure',

    // Trace с первой retry
    trace: 'on-first-retry',

    // Разрешаем service workers для WebSocket subscriptions
    serviceWorkers: 'allow',

    // Базовый URL для тестов
    baseURL: 'http://localhost:5174',

    // Таймаут для навигации
    navigationTimeout: 30 * 1000,

    // Таймаут для действий
    actionTimeout: 10 * 1000,
  },

  // Reporter конфигурация
  reporter: [
    ['html', { outputFolder: './playwright-report/html-report' }],
    ['json', { outputFile: './playwright-report/results.json' }],
    ['junit', { outputFile: './playwright-report/junit.xml' }],
    ['list'],
  ],

  // WebServer для автозапуска frontend при тестах
  webServer: {
    command: 'cd ../.. && npm run dev -- --host',
    url: 'http://localhost:5174',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },

  // Проекты для разных конфигураций
  projects: [
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'desktop-firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'desktop-safari',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],

  // Metadata для тестов
  metadata: {
    project: 'Unmatched',
    suite: 'E2E',
  },
});
