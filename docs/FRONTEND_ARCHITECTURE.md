# Frontend Architecture — Unmatched Digital

> Версия: 1.0.0
> Обновлено: 2025-01-31

---

## Оглавление

1. [Обзор](#обзор)
2. [Технологический стек](#технологический-стек)
3. [Структура проекта](#структура-проекта)
4. [Архитектура State Management](#архитектура-state-management)
5. [Apollo Client & GraphQL](#apollo-client--graphql)
6. [Аутентификация](#аутентификация)
7. [Игровая синхронизация](#игровая-синхронизация)
8. [Оптимистичные обновления](#оптимистичные-обновления)
9. [Routing](#routing)
10. [Компоненты](#компоненты)
11. [Стилизация](#стилизация)
12. [Обработка ошибок](#обработка-ошибок)
13. [Performance](#performance)
14. [Testing](#testing)

---

## Обзор

Фронтенд **Unmatched Digital** — это React-приложение для реального времени с GraphQL API. Приложение поддерживает:

- **Real-time мультиплеер** через WebSocket подписки
- **Offline-first** подход с локальным игровым движком
- **Optimistic UI** с мгновенным откликом
- **JWT аутентификацию** с автоматическим refresh

---

## Технологический стек

| Категория | Технология | Версия |
|-----------|------------|--------|
| **Framework** | React | 18.3.1 |
| **Runtime** | TypeScript | 5.x |
| **Build** | Vite | 5.x |
| **State** | Zustand | 5.0.2 |
| **GraphQL** | Apollo Client | 3.14.0 |
| **WebSocket** | graphql-ws | — |
| **Codegen** | GraphQL Codegen | — |
| **Testing** | Vitest | — |
| **E2E** | Playwright | — |

---

## Структура проекта

```
src/
├── components/          # React компоненты
│   ├── auth/           # Auth UI (LoginForm, RegisterForm, AuthGuard)
│   ├── board/          # Игровое поле
│   ├── cards/          # Карточные компоненты
│   └── controls/       # UI контролы
├── core/               # Игровой движок (бизнес-логика)
│   ├── engine/         # GameEngine, TurnManager, CombatResolver
│   ├── models/         # Типы и модели
│   └── data/           # Данные героев, карт, досок
├── store/              # Zustand stores
│   ├── authStore.ts    # Аутентификация
│   ├── gameStore.ts    # Локальное игровое состояние
│   ├── remoteGameStore.ts # Синхронизация с сервером
│   └── uiStore.ts      # UI состояние
├── lib/                # Утилиты и конфигурация
│   ├── apolloClient.ts # Apollo Client с link chain
│   ├── auth-link.ts    # Auth link для токенов
│   ├── error-link.ts   # Error link с 401 handling
│   ├── retry-link.ts   # Retry link с backoff
│   └── token-storage.ts # Хранение токенов
├── hooks/              # Custom React hooks
│   ├── useGameSync.ts      # WebSocket подписки
│   ├── useOptimisticUpdate.ts # Optimistic updates
│   └── useAuth.ts          # Auth действия
├── graphql/            # GraphQL операции (.graphql файлы)
│   ├── queries/        # Query операции
│   ├── mutations/      # Mutation операции
│   └── subscriptions/  # Subscription операции
├── gql/                # Сгенерированные типы (codegen)
└── main.tsx            # Entry point
```

---

## Архитектура State Management

### Zustand Stores

Приложение использует **Zustand** для управления состоянием. Каждый store отвечает за свою область:

```typescript
┌─────────────────────────────────────────────────────────────┐
│                        Application State                     │
├─────────────────────────────────────────────────────────────┤
│  authStore          │  gameStore        │  remoteGameStore  │
│  - user             │  - gameState      │  - serverState    │
│  - accessToken      │  - selectedFighter│  - sequenceNumber │
│  - isAuthenticated  │  - highlightedPos │  - connectionStatus│
│                      │                   │                   │
│  login()            │  maneuver()       │  connectToGame()  │
│  register()         │  attack()         │  handleGameEvent()│
│  refreshTokens()    │  endTurn()        │  checkGaps()      │
│  logout()           │                   │                   │
├─────────────────────────────────────────────────────────────┤
│  uiStore                                                      │
│  - modals (combat, cardPreview, heroSelect)                  │
│  - gameLog                                                   │
│  - isProcessing                                              │
└─────────────────────────────────────────────────────────────┘
```

### authStore

Управляет аутентификацией и токенами:

```typescript
interface AuthState {
  // State
  user: User | null;
  isAuthenticated: boolean;
  isAuthLoading: boolean;

  // Actions
  login(email, password): Promise<void>
  register(email, username, password): Promise<void>
  logout(): Promise<void>
  refreshTokens(): Promise<void>
}
```

**Особенности:**
- Инициализируется из `localStorage` при старте
- Автоматически обновляет токен при 401 ошибке
- Single-flight refresh (только один refresh одновременно)

### gameStore

Локальный игровой движок для offline режима и optimistic updates:

```typescript
interface GameStoreState {
  gameState: GameState | null;
  selectedFighterId: string | null;
  highlightedSpaces: Position[];

  initializeGame(setup?): void
  maneuver(fighterId): void
  moveFighter(fighterId, position): void
  attack(attackerId, cardId, targetId): void
  endTurn(): void
}
```

### remoteGameStore

Синхронизация с сервером через WebSocket:

```typescript
interface RemoteGameState {
  serverGameState: ServerGameState | null;
  lastSequenceNumber: number;
  connectionStatus: ConnectionStatus;

  connectToGame(gameId): Promise<void>
  handleGameEvent(event): void
  checkSequenceGaps(): Promise<void>
}
```

**Sequence Numbers:**
- Каждый серверный事件 имеет `sequenceNumber`
- Client отслеживает `lastSequenceNumber`
- Gap detection: если `actualSeq > expectedSeq + 1` → запрашиваем пропущенные события

---

## Apollo Client & GraphQL

### Link Chain

Apollo использует цепочку middleware-links для обработки запросов:

```
┌─────────────────────────────────────────────────────────────┐
│                    Apollo Link Chain                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. retryLink    → Повторяет неудачные запросы              │
│  2. authLink     → Добавляет Authorization header            │
│  3. errorLink    → Обрабатывает 401 → refresh token          │
│  4. splitLink    → HTTP для queries/mutations                │
│                    WebSocket для subscriptions               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### retryLink

```typescript
const retryLink = new RetryLink({
  delay: { initial: 300, max: 10000, jitter: true },
  attempts: {
    max: 3,
    retryIf: (error) => isNetworkError(error) || isRetryableError(error)
  }
});
```

### authLink

```typescript
const authLink = setContext((operation, { headers }) => {
  const token = useAuthStore.getState().accessToken;
  return {
    headers: { ...headers, authorization: token ? `Bearer ${token}` : '' }
  };
});
```

### errorLink

```typescript
const errorLink = onError(({ graphQLErrors, operation, forward }) => {
  if (isAuthError(graphQLErrors)) {
    return fromPromise(
      useAuthStore.getState().refreshTokens()
    ).flatMap(() => forward(operation));
  }
});
```

---

## Аутентификация

### Flow

```
┌─────────────┐      login(email, password)      ┌─────────────┐
│   Client    │ ─────────────────────────────────▶│   Backend   │
│             │                                     │             │
│             │ ◀─────────────────────────────────│             │
│             │     { accessToken, refreshToken }  │             │
└─────────────┘                                     └─────────────┘
       │                                                    │
       │ Save to localStorage                               │
       │ Set user in authStore                              │
       │                                                    │
       ▼                                                    ▼
```

### Token Refresh

```
┌─────────────┐     401 Error               ┌─────────────┐
│   Client    │ ────────────────────────────▶│   Apollo    │
│             │                              │             │
│             │                              │             │
│             │ ◀─────────────────────────────│             │
│             │      UNAUTHENTICATED          │             │
└─────────────┘                              └─────────────┘
       │
       │ errorLink перехватывает
       │
       ▼
┌─────────────────────────────────────┐
│  1. Проверить refreshToken          │
│  2. Вызвать refreshTokens mutation  │
│  3. Сохранить новые токены          │
│  4. Повторить оригинальный запрос   │
└─────────────────────────────────────┘
```

---

## Игровая синхронизация

### useGameSync Hook

```typescript
function useGameSync(gameId: string, options?: UseGameSyncOptions) {
  return {
    isConnected: boolean,
    isConnecting: boolean,
    isReconnecting: boolean,
    hasError: boolean,
    connectionStatus: ConnectionStatus
  };
}
```

**Функции:**
- Подключается к `gameStateUpdated` subscription
- Автоматически переподключается при потере соединения
- Проверяет sequence gaps

### Reconnection Strategy

```typescript
// Экспоненциальный backoff
reconnectDelay * reconnectAttempts

// Макс. 5 попыток
maxReconnectAttempts = 5
```

---

## Оптимистичные обновления

### useOptimisticUpdate Hook

```typescript
const { execute, rollback, isMutating } = useOptimisticUpdate({
  mutation: ManeuverDocument,
  predictState: (state, { fighterId }) => {
    // Предсказываем состояние
    return engine.maneuver(state, fighterId);
  },
  onSuccess: (data) => console.log('Success!'),
  onError: (error) => console.error('Error!', error)
});

// Мгновенный UI отклик
execute({ fighterId: 'hero-1' });
```

**Flow:**

```
┌─────────────┐     1. Предсказать состояние     ┌─────────────┐
│   Client    │ ──────────────────────────────▶│   GameStore │
│             │                                 │             │
│             │     2. Обновить UI немедленно    │             │
│             │ ◀───────────────────────────────│             │
└─────────────┘                                 └─────────────┘
       │
       │ 3. Отправить мутацию на сервер
       ▼
┌─────────────┐
│   Backend   │ ◀─── mutation ───
│             │
│             │ ──── result ────▶
└─────────────┘
       │
       │ 4a. Success → ничего не делаем (UI уже обновлён)
       │ 4b. Error → rollback к предыдущему состоянию
```

---

## Routing

### Protected Routes

```tsx
<AuthGuard>
  <DashboardPage />
</AuthGuard>
```

### Public-Only Routes

```tsx
<PublicOnlyGuard redirectTo="/">
  <LoginPage />
</PublicOnlyGuard>
```

---

## Компоненты

### Структура

```
components/
├── auth/
│   ├── LoginForm.tsx       # Форма входа
│   ├── RegisterForm.tsx   # Форма регистрации
│   └── AuthGuard.tsx      # HOC для защиты маршрутов
├── board/
│   └── BoardView.tsx      # Игровое поле
├── cards/
│   ├── Card.tsx           # Отдельная карта
│   └── HandView.tsx       # Рука игрока
└── controls/
    └── GameControls.tsx   # Контролы игры
```

---

## Стилизация

### Подход

- **Component-scoped CSS** — каждый компонент имеет свой `.css` файл
- **BEM-подобная номенклатура** для auth форм
- **Russian localization** в UI тексте

### Пример

```css
/* LoginForm.module.css */
.auth-form-container { /* ... */ }
.auth-form-card { /* ... */ }
.form-input--error { /* ... */ }
```

---

## Обработка ошибок

### Error Boundary

```tsx
<ErrorBoundary
  fallback={<ErrorFallback />}
  onError={(error) => console.error(error)}
>
  <App />
</ErrorBoundary>
```

### GraphQL Errors

```typescript
try {
  const { data } = await client.mutate({ ... });
} catch (error) {
  if (error.networkError) {
    // Сетевая ошибка
  } else if (error.graphQLErrors) {
    // GraphQL ошибка
    const code = error.graphQLErrors[0].extensions?.code;
  }
}
```

---

## Performance

### Оптимизации

| Техника | Описание |
|---------|----------|
| **Code splitting** | Vite автоматическое разбиение |
| **Lazy loading** | `React.lazy()` для тяжёлых компонентов |
| **Memoization** | `React.memo()` для карточек |
| **Cache policies** | `cache-and-network` для queries |
| **Debounce** | `useOptimisticDebounce` для частых действий |

### Bundle Size

```
dist/
├── assets/
│   ├── index-[hash].js      ~150KB (gzipped)
│   └── index-[hash].css     ~20KB (gzipped)
```

---

## Testing

### Unit Tests

```typescript
// authStore.test.ts
describe('authStore', () => {
  it('should login successfully', async () => {
    const store = createAuthStore();
    await store.getState().login('test@example.com', 'password');
    expect(store.getState().isAuthenticated).toBe(true);
  });
});
```

### Integration Tests

```typescript
// useGameSync.test.ts
describe('useGameSync', () => {
  it('should connect to game and receive updates', async () => {
    const { result } = renderHook(() => useGameSync('game-123'));
    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });
});
```

### E2E Tests

```typescript
// auth.spec.ts (Playwright)
test('user can login', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'password');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/');
});
```

---

## Диаграммы

### Data Flow (Login)

```
User        LoginForm    authStore    tokenStorage    Apollo    Backend
 │              │            │              │            │          │
 ├─click───────▶│            │              │            │          │
 │              ├─login()───▶│              │            │          │
 │              │            ├─setTokens()─▶│            │          │
 │              │            │              │            ├─mutation─▶│
 │              │            │              │            │◀─tokens──│
 │              │            │◀─accessToken─│            │          │
 │              │            │              │            │          │
 │              │◀─redirect──│              │            │          │
```

### Data Flow (Game Action)

```
User        GameBoard    useOptimisticUpdate    gameStore    Backend
 │              │              │                 │            │
 ├─action──────▶│              │                 │            │
 │              ├─execute()───▶│                 │            │
 │              │              ├─predictState()─▶│            │
 │              │              │◀─newState──────│            │
 │              │◀─UI update──│                 │            │
 │              │              │                 │            │
 │              │              ├─mutation─────────────────────▶│
 │              │              │                 │            │
 │              │              │                 │◀─result────│
 │              │              │                 │            │
 │              │              ├─onSuccess()     │            │
```

---

## Checklist для разработчиков

При добавлении новых фич:

- [ ] Создать `.graphql` операции в `src/graphql/`
- [ ] Запустить `npm run codegen` для генерации типов
- [ ] Добавить state в соответствующий Zustand store
- [ ] Создать компонент в `src/components/`
- [ ] Добавить стили в `.module.css`
- [ ] Написать unit тесты
- [ ] Проверить TypeScript типы
- [ ] Протестировать в dev режиме

---

## Полезные команды

```bash
# Разработка
npm run dev

# Сборка
npm run build

# Генерация GraphQL типов
npm run codegen

# Тесты
npm run test
npm run test:ui

# E2E тесты
npm run test:e2e

# Линтинг
npm run lint
```

---

## Связанные документы

- [Backend Architecture](../backend/README.md)
- [API Documentation](../backend/docs/API.md)
- [Deployment Guide](./DEPLOYMENT.md)
