/**
 * Smoke Tests
 *
 * Базовые тесты для проверки работоспособности приложения.
 * Не требуют авторизации.
 */

import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', { tag: ['@smoke'] }, () => {
  test('page loads successfully', async ({ page }) => {
    await page.goto('http://localhost:5174');

    // Проверяем, что страница загрузилась
    await expect(page).toHaveTitle(/Unmatched/i);
  });

  test('basic UI elements are visible', async ({ page }) => {
    await page.goto('http://localhost:5174');

    // Проверяем наличие базовых элементов
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
