# Playwright E2E Tests for Unmatched

E2E тесты для Unmatched с использованием Playwright. Архитектура адаптирована из паттернов проекта `alix1912/e2e`.

## Структура

```
test/playwright/
├── playwright.config.ts      # Конфигурация Playwright
├── tsconfig.json              # TypeScript конфигурация
├── fixtures/                  # Фикстуры для тестов
│   ├── fixtures.ts           # Главный экспорт фикстур
│   ├── auth.fixture.ts       # Авторизация + storage state
│   ├── player.fixture.ts     # Multi-role (несколько игроков)
│   ├── game.fixture.ts       # Создание игр
│   └── data.ts               # Константы, селекторы, мутации
├── src/
│   ├── services/
│   │   └── api.service.ts    # GraphQL API wrapper
│   ├── generators/
│   │   └── game.generator.ts # Генерация тестовых данных
│   └── utils/
│       └── global-setup.ts   # Storage state кэширование
├── e2e/                       # E2E тесты
│   ├── full-game-cycle.spec.ts
│   ├── victory-screen.spec.ts
│   └── multiplayer.spec.ts
├── storage-states/            # Кэшированные сессии
│   ├── player1.json
│   ├── player2.json
│   └── player3.json
└── playwright-artifacts/      # Артефакты (screenshot, trace, video)
```

## Ключевые паттерны

### 1. Storage State Caching

Для быстрой авторизации используются кэшированные storage states. Они генерируются автоматически через `global-setup.ts` перед запуском тестов.

```typescript
test('my test', async ({ page, loginAs }) => {
  await loginAs('player1'); // Быстрый логин из кэша
  // ...
});
```

### 2. Multi-Role Fixtures

Для тестирования мультиплеера можно создавать несколько браузеров с разными авторизованными пользователями:

```typescript
test('multiplayer test', async ({ createMultiplayerGame }) => {
  const { player1Page, player2Page, gameId } = await createMultiplayerGame();

  // Player 1 видит свой ход
  await expect(player1Page.locator('.turn-indicator')).toContainText('Your Turn');

  // Player 2 видит ход оппонента
  await expect(player2Page.locator('.turn-indicator')).toContainText("Opponent's Turn");
});
```

### 3. Test Tags

Тесты группируются тегами для запуска определённых наборов:

```typescript
test.describe('Critical Tests', { tag: ['@smoke', '@critical'] }, () => {
  test('login works', async ({ page }) => { ... });
});
```

## Запуск тестов

### Все тесты
```bash
npm run test:e2e:ui
```

### Только smoke тесты
```bash
npm run test:e2e:ui:smoke
```

### Только мультиплеер тесты
```bash
npm run test:e2e:ui:multiplayer
```

### С headed режимом (видно браузеры)
```bash
npm run test:e2e:ui:headed
```

### Debug режим
```bash
npm run test:e2e:ui:debug
```

### HTML отчет
```bash
npm run test:e2e:ui:report
```

## Написание тестов

### Базовый тест

```typescript
import { test, expect } from '../fixtures/fixtures';

test('basic test', async ({ page, loginAs, createGame }) => {
  await loginAs('player1');
  const gameId = await createGame();
  await page.goto(`http://localhost:5174/game/${gameId}`);

  await expect(page.locator('.game-board')).toBeVisible();
});
```

### Мультиплеерный тест

```typescript
import { test, expect } from '../fixtures/fixtures';

test('turn sync', async ({ createMultiplayerGame }) => {
  const { player1Page, player2Page, gameId } = await createMultiplayerGame();

  await player1Page.goto(`http://localhost:5174/game/${gameId}`);
  await player2Page.goto(`http://localhost:5174/game/${gameId}`);

  // Player 1 завершает ход
  await player1Page.click('[data-action="end-turn"]');

  // Player 2 видит изменение
  await expect(player2Page.locator('.turn-indicator')).toContainText('Your Turn');
});
```

### Тест с API вызовами

```typescript
test('API integration', async ({ api, createGame }) => {
  const gameId = await createGame();

  // Выполняем действия через API
  await api.maneuver({
    gameId,
    fighterId: 'fighter1',
    cardId: 'card1',
    path: [{ x: 5, y: 5 }, { x: 6, y: 5 }],
  });

  await api.endTurn({ gameId });
});
```

## Доступные фикстуры

### Auth Fixtures
- `createUser(userData)` - создание нового пользователя
- `createRandomUser()` - создание пользователя со случайными данными
- `loginAs(role)` - быстрый логин через storage state
- `loginWithCredentials(email, password)` - логин через форму
- `authenticatedPage` - страница с готовой авторизацией
- `api` - API клиент с токеном

### Player Fixtures
- `createMultiplayerGame()` - создание игры с 2 игроками
- `createThreePlayerGame()` - создание игры с 3 игроками
- `createContextWithRole(browser, role)` - контекст для роли
- `createPageWithRole(browser, role)` - страница для роли

### Game Fixtures
- `createGame(options)` - создание новой игры
- `joinGame(gameId, heroId)` - присоединение к игре
- `executeManeuver(...)` - выполнение манёвра
- `executeAttack(...)` - выполнение атаки
- `executeDefense(...)` - выполнение защиты
- `executeResolveCombat(gameId)` - разрешение боя
- `executeEndTurn(gameId)` - завершение хода
- `setup1v1Game(hero1, hero2)` - быстрое создание 1v1 игры

## Storage States

Storage states генерируются автоматически перед запуском тестов. Для регенерации:

```bash
# Удалить существующие
rm -rf test/playwright/storage-states/*.json

# Запустить тесты - создадутся новые
npm run test:e2e:ui
```

## CI/CD

При запуске в CI:
1. Установите SKIP_STORAGE_SETUP=false для генерации storage states
2. Тесты запускаются параллельно (workers: 1 в CI для стабильности)
3. Артефакты сохраняются в `playwright-artifacts/`

## Устранение проблем

### "Storage state not found"
Запустите глобальный сетап:
```bash
SKIP_STORAGE_SETUP=false npm run test:e2e:ui
```

### "Backend not running"
Убедитесь, что backend запущен на `http://localhost:3000`:
```bash
cd backend && npm run start:dev
```

### "Frontend not running"
Frontend запускается автоматически через `webServer` в playwright.config.ts.

### Медленные тесты
- Увеличьте `workers` в playwright.config.ts для локального запуска
- Используйте `test.step()` для группировки действий
- Используйте storage states вместо логина через UI
