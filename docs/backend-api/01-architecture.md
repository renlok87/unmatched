# Архитектура бэкенда Unmatched

> Документ для разработчиков, подключающих клиент **Unreal Engine** к бэкенду.
> Здесь: обзор системы, дерево модулей, транспорт (HTTP + WebSocket), конфигурация/ENV, схема данных Prisma, инфраструктура и инструкции по локальному запуску.

---

## 1. Обзор

Бэкенд — **NestJS 11 + Apollo Server (GraphQL)** приложение, реализующее онлайн-версию настольной игры Unmatched:

- **GraphQL API** (code-first, схема генерируется автоматически в `schema.gql`) — queries, mutations и **subscriptions через WebSocket (протокол `graphql-ws`)**;
- **PostgreSQL** через **Prisma ORM** — пользователи, игры, игровой контент (герои/карты/доски);
- **Redis** (ioredis) — presence, pub/sub для синхронизации игровых событий между инстансами, распределённые локи, кэш;
- **BullMQ** — фоновые очереди (таймауты боя, обработка игровых действий, матчмейкинг, аудит);
- **JWT-аутентификация** (access + refresh токены с ротацией);
- **Prometheus-метрики** (`/metrics`), health-checks (`/health`, `/health/live`, `/health/ready`, `/health/detail`).

### Ключевые URL локального окружения

| Назначение | URL |
|---|---|
| GraphQL HTTP endpoint (queries/mutations) | `http://localhost:3000/graphql` |
| GraphQL Playground (браузер) | `http://localhost:3000/graphql` (GET) |
| GraphQL WebSocket (subscriptions, протокол `graphql-ws`) | `ws://localhost:3000/graphql` |
| Health check | `http://localhost:3000/health` |
| Prometheus метрики | `http://localhost:3000/metrics` |

> **Для UE-клиента:** и HTTP, и WS живут на одном и том же пути `/graphql`. HTTP — для queries/mutations, WS-соединение с субпротоколом `graphql-ws` — для подписок.

---

## 2. Дерево модулей и их роли

```
backend/src/
├── main.ts                  # Bootstrap: ENV-валидация, ValidationPipe, CORS, порт
├── app.module.ts            # Корневой модуль: импортирует все модули, BullMQ, Throttler
├── app.controller.ts        # REST-корень (не GraphQL)
│
├── config/                  # Конфигурация
│   ├── configuration.ts     # Фабрика конфига из ENV
│   └── validation.schema.ts # Схема обязательных переменных
│
├── graphql/                 # Настройка GraphQL (Apollo, graphql-ws, validation rules)
│   └── scalars/             # DateTime, JSON скаляры
│
├── database/                # PrismaService + PrismaModule (глобальный)
├── redis/                   # RedisService (глобальный): client + publisher + subscriber
├── cache/                   # Кэш-сервисы: cache-tags, cache-warming
│
├── auth/                    # Регистрация, вход, refresh-ротация, JWT-стратегии
│   ├── auth.resolver.ts     # register / login / logout / refreshTokens / ...
│   ├── guards/              # GqlAuthGuard (passport-jwt)
│   └── strategies/          # JwtStrategy, RefreshStrategy
│
├── users/                   # Профили, статистика, ELO-рейтинг, лидерборд
│   ├── users.resolver.ts    # me / user / userByUsername / myStats / mySettings
│   ├── leaderboard.resolver.ts # leaderboard / topPlayers / getPlayerRank
│   ├── rating.service.ts    # ELO
│   └── user-stats.service.ts
│
├── content/                 # Статический контент игры: герои, карты, доски, сеты
│   ├── content.resolver.ts  # getAllHeroes / getHero / getCards / getAllBoards / ... (Public)
│   ├── content-db.service.ts# Загрузка контента из PostgreSQL (Hero/Card/Board)
│   └── data/, mappers/, validators/
│
├── lobby/                   # Фасадный модуль лобби (реэкспортирует GamesModule)
│
├── games/                   # ИГРОВОЕ ЯДРО API: CRUD игр, лобби, мутации, подписки
│   ├── game.resolver.ts     # createGame / joinGame / leaveGame / startGame /
│   │                        # toggleReady / selectHero / abortGame, queries:
│   │                        # game / myGames / availableGames / gameState /
│   │                        # gameSequence / eventsSince / heroStances
│   ├── resolvers/
│   │   ├── game-actions.resolver.ts   # maneuver / moveFighter / attack / playDefense /
│   │   │                               # playScheme / resolveCombat / endTurn / pass /
│   │   │                               # toggleDoor / setStance / resolvePendingEffect
│   │   └── game-subscription.resolver.ts # Подписки: gameStateUpdated / attackInitiated /
│   │                                      # defensePlayed / combatResolved
│   ├── game-subscription.service.ts  # PubSub + Redis pub/sub broadcast (multi-instance)
│   ├── game-state.service.ts         # Хранение/версионирование состояния игры
│   ├── services/           # ai-turn, combat-timeout, replay, leaderboard, stats
│   ├── processors/          # BullMQ processors: game-action, combat-timeout
│   └── guards/              # GameStatusGuard, GameTurnGuard, AttackPhaseGuard и др.
│
├── game-engine/             # Чистая игровая логика Unmatched (без GraphQL)
│   ├── engine/              # combat-resolver, movement, adjacency, value-modifier
│   ├── effects/             # card-effect-executor (исполнение эффектов карт)
│   ├── abilities/           # hero-ability-registry + хендлеры героев (Daredevil, Ms. Marvel, Arthur...)
│   ├── movement/            # A* pathfinding + path-cache
│   ├── services/            # turn-management, deck-management, ai-decision
│   └── validators/          # game-rules.validator
│
├── matchmaking/             # Автоматический матчмейкинг (фазы 8A–8E)
│   ├── resolvers/           # joinQueue / leaveQueue / queueStatus / acceptMatch /
│   │                        # declineMatch / penaltyInfo; подписка matchFound
│   └── services/            # queue-manager, scheduler, match-confirmation, penalty
│
├── presence/                # Online-статусы игроков
│   ├── presence.resolver.ts # heartbeat (mutation), getPresence / getOnlineUsers /
│   │                        # подписка presenceUpdated
│   └── presence-cleanup.service.ts
│
├── audit/                   # Security/audit логирование (BullMQ очередь 'audit')
├── admin/                   # Админ-резолвер: управление юзерами/контентом/играми
├── metrics/                 # Prometheus (game_actions_total, combat_duration_seconds, ...)
├── health/                  # Health checks для k8s/мониторинга
└── common/                  # Общие декораторы (@CurrentUser, @Public) и сервисы
```

### Роли модулей (таблица)

| Модуль | Роль | Экспортирует |
|---|---|---|
| `DatabaseModule` (Prisma) | ORM-доступ к PostgreSQL, retry-подключение | `PrismaService` (глобально) |
| `RedisModule` | ioredis client + pub/sub (3 соединения), graceful degradation без Redis | `RedisService` (глобально) |
| `GraphqlModule` | Apollo Server, `graphql-ws`, complexity/depth limits, санитайзинг ошибок | — |
| `AuthModule` | JWT auth (access 1h / refresh 24h по умолчанию), refresh-ротация | `AuthService`, `GqlAuthGuard` |
| `UsersModule` | Профили, статистика, ELO, лидерборды | сервисы пользователей |
| `ContentModule` | Публичный контент: герои, карты, доски, сеты (кэшируется) | `ContentService` и др. |
| `GamesModule` | Лобби + игровые мутации + подписки + очереди BullMQ (`game-action`, `combat-timeout`) | игровые сервисы |
| `LobbyModule` | Фасад над GamesModule (историческая миграция) | `GamesModule` |
| `GameEngineModule` | Детерминированная игровая логика: бой, движение (A*), эффекты карт, способности героев, управление ходами | движковые сервисы |
| `MatchmakingModule` | Автопоиск матчей, 2-фазное подтверждение, штрафы, recovery после краша | queue/scheduler сервисы |
| `PresenceModule` | Heartbeat, online/away/offline, автоочистка | `PresenceService` |
| `AuditModule` | Асинхронные audit-логи через BullMQ (`audit`) | `AuditService` |
| `AdminModule` | Админ-операции (RBAC `UserRole.ADMIN`) | — |
| `CacheModule` | Разогрев кэша, теги кэша | — |
| `HealthModule` | `/health`, `/health/live`, `/health/ready`, `/health/detail` | — |
| `MetricsModule` | Prometheus `/metrics` (используется GamesModule/движком) | `PrometheusModule`, `MetricsService` |

### Граф зависимостей (упрощённо)

```
AppModule
 ├── ConfigModule (global)      ├── BullModule.forRoot(Redis)
 ├── ThrottlerModule (10/60s)   ├── PrismaModule, RedisModule (global)
 ├── GraphqlModule ─────────────┐
 ├── AuthModule                 │  Apollo context: { req, isSubscription }
 ├── UsersModule                │
 ├── ContentModule              │
 ├── AdminModule                │
 ├── CommonModule               │
 ├── GamesModule ── imports ──► GameEngineModule ──► ContentModule, MetricsModule, GameJobsModule
 ├── LobbyModule (→ GamesModule)
 ├── MatchmakingModule (→ Redis, Prisma, BullMQ queues, Scheduler)
 ├── PresenceModule, AuditModule, CacheModule, HealthModule
```

---

## 3. Транспорт

### 3.1 HTTP (queries / mutations)

- Endpoint: `POST http://localhost:3000/graphql` (Apollo через Express 5).
- Формат — стандартный GraphQL over HTTP JSON.
- Авторизация: заголовок `Authorization: Bearer <accessToken>`.
- Глобальный `ValidationPipe` с `whitelist: true, forbidNonWhitelisted: true` — лишние поля в DTO отклоняются.
- Rate limiting (Throttler): по умолчанию 10 запросов / 60 сек; на auth — жёстче (login 10/мин, register 5/мин).
- Защита GraphQL: complexity limit 1000, depth limit 7.

Пример (raw HTTP):

```http
POST /graphql HTTP/1.1
Host: localhost:3000
Content-Type: application/json
Authorization: Bearer <accessToken>

{
  "query": "query { me { id username email } }"
}
```

### 3.2 WebSocket (subscriptions)

- Endpoint: `ws://localhost:3000/graphql`, субпротокол **`graphql-ws`** (современный протокол, НЕ legacy `subscriptions-transport-ws`).
- **Важно для UE:** при установке WS-соединения токен передаётся в `connectionParams`:

```json
{
  "type": "connection_init",
  "payload": {
    "authorization": "Bearer <accessToken>"
  }
}
```

Бэкенд принимает `authorization` / `Authorization` / `token` (с префиксом `Bearer` или без — нормализуется автоматически) и кладёт в `req.headers.authorization`, так что `GqlAuthGuard` работает одинаково для HTTP и WS.

- Подписки фильтруются на сервере по `gameId` / `userId` (см. `game-subscription.resolver.ts`).

### 3.3 Real-time доставка: PubSub + Redis Pub/Sub

- Внутри инстанса — in-memory `graphql-subscriptions.PubSub` (`GameSubscriptionService`, `MatchmakingPubSubService`).
- При нескольких инстансах бэкенда события броадкастятся через **Redis Pub/Sub** каналы `game:updates:<gameId>` (каждый инстанс перепубликует чужие события в локальный PubSub; self-delivery отсекается по `instanceId`).
- Т.е. для UE-клиента это прозрачно: достаточно WS-подписки.

### 3.4 Основные GraphQL-операции (справка для интеграции)

| Тип | Имя | Назначение |
|---|---|---|
| Mutation | `register`, `login`, `logout`, `refreshTokens` | Аутентификация |
| Query | `me`, `user`, `userByUsername`, `myStats`, `mySettings` | Профиль |
| Query | `leaderboard`, `topPlayers`, `getPlayerRank` | Рейтинги |
| Query | `getAllHeroes`, `getHero`, `getCards`, `getCard`, `getAllBoards`, `getAllSets`, `getContentVersion` | Контент (Public) |
| Mutation | `createGame`, `joinGame`, `leaveGame`, `startGame`, `abortGame`, `toggleReady`, `selectHero` | Лобби |
| Query | `game`, `myGames`, `availableGames`, `gameState`, `gameSequence`, `eventsSince`, `heroStances` | Игровые запросы |
| Mutation | `maneuver`, `moveFighter`, `attack`, `playDefense`, `playScheme`, `resolveCombat`, `endTurn`, `pass`, `toggleDoor`, `setStance`, `resolvePendingEffect` | Игровые действия |
| Mutation/Query | `joinQueue`*, `leaveQueue`, `queueStatus`, `acceptMatch`, `declineMatch`, `penaltyInfo` | Матчмейкинг |
| Mutation | `heartbeat` | Presence |
| Subscription | `gameStateUpdated`, `attackInitiated`, `defensePlayed`, `combatResolved` | События игры |
| Subscription | `matchFound` | Матч найден |
| Subscription | `presenceUpdated` | Статусы игроков |

\* Точные имена мутаций матчмейкинга см. в сгенерированной `schema.gql` (запуск `npm run start:dev`).

**Восстановление после потери соединения:** query `gameSequence(gameId)` возвращает текущий номер события, `eventsSince(gameId, sequence)` — пропущенные события. Клиент UE должен использовать это при реконнекте.

---

## 4. Аутентификация (для UE-клиента)

1. `mutation register(input: { email, username, password })` или `login(input: { email, password })` → `AuthResponse { accessToken, refreshToken, user }`.
2. Access-токен — в `Authorization: Bearer ...` для каждого HTTP-запроса и в `connectionParams` WS.
3. По истечении — `mutation refreshTokens(refreshToken: "...")` → новая пара (ротация: старый refresh инвалидируется, refresh-токены хранятся в БД хэшированными).
4. Дефолтные TTL: access `JWT_EXPIRES_IN=1h` (env: `JWT_ACCESS_EXPIRATION=15m` в .env.example), refresh `24h` (`JWT_REFRESH_EXPIRATION=7d`).

Защищённые резолверы помечены `@UseGuards(GqlAuthGuard)`; публичные — `@Public()` (контент, auth).

---

## 5. Как поднять локально

### Вариант A: всё в Docker (из корня репозитория)

```bash
# Postgres (порт 5433), Redis (6379), backend (3000)
docker compose up -d
```

`docker-compose.yml` в корне поднимает `postgres:16-alpine`, `redis:7-alpine` и сам бэкенд (`npm run start:dev` внутри контейнера). БД: `postgresql://unmatched:password@postgres:5432/unmatched`.

### Вариант B: инфраструктура в Docker, бэкенд локально

```bash
docker compose up -d postgres redis   # из корня репозитория
cd backend
cp .env.example .env                  # заполнить DATABASE_URL и секреты
npm install
npx prisma migrate dev                # миграции + генерация клиента
npx prisma db seed                    # сидинг контента (или prisma:seed-scraped)
npm run start:dev                     # http://localhost:3000/graphql
```

> Postgres в docker-compose наружу даёт порт **5433**, поэтому `DATABASE_URL=postgresql://unmatched:password@localhost:5433/unmached` (имя БД `unmatched` в compose, `unmached` в .env.example — сверяйтесь со своим `.env`).

### Полезные npm-скрипты (backend/)

| Скрипт | Действие |
|---|---|
| `npm run start:dev` | dev-режим с watch |
| `npm run prisma:migrate` / `prisma:push` | миграции / синхронизация схемы |
| `npm run prisma:seed` / `prisma:seed-scraped` / `prisma:seed-admin` | сидинг контента / админа |
| `npm run prisma:studio` | Prisma Studio (GUI по БД) |
| `npm test` / `test:e2e` | unit / e2e тесты |

### Смоук-проверка

```bash
curl -X POST http://localhost:3000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ getAllHeroes { id name } }"}'
```

---

## 6. Конфигурация / переменные окружения

`ConfigModule` читает `.env` → `.env.local` → `.env.docker`. Полный образец — `backend/.env.example`.

| Переменная | Значение по умолчанию | Описание |
|---|---|---|
| `NODE_ENV` | `development` | В production валидируются секреты (мин. 32 символа, запрет дефолтных) |
| `PORT` | `3000` | HTTP + WS порт |
| `FRONTEND_URL` | `http://localhost:5173` | Доп. CORS origin |
| `DATABASE_URL` | — (обязательна) | PostgreSQL connection string |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | `localhost` / `6379` / — | Redis (отсутствие Redis не блокирует запуск) |
| `JWT_SECRET` | dev-дефолт | Access-токен подпись (prod: обязателен, ≥32 симв.) |
| `JWT_REFRESH_SECRET` | dev-дефолт | Refresh-токен подпись (prod: обязателен, ≥32 симв.) |
| `JWT_EXPIRES_IN` | `1h` | TTL access-токена |
| `REFRESH_TOKEN_EXPIRES_IN` | `24h` | TTL refresh-токена |
| `DEFAULT_BOARD_ID` | `cobble-city` | Доска по умолчанию |
| `MAX_PLAYERS_PER_GAME` | `4` | Лимит игроков |
| `TURN_TIME_LIMIT` | `300` | Секунд на ход |
| `THROTTLE_TTL` / `THROTTLE_LIMIT` | `60` / `100` | Rate limiting |
| `DISABLE_CACHE` | `false` | Отключить Redis-кэш (удобно в dev) |
| `LOG_LEVEL` / `LOG_FORMAT` | `debug` / `json` | Логирование |
| `SENTRY_DSN`, `PROMETHEUS_ENABLED` | — | Мониторинг (опционально) |

**CORS:** разрешены origins `http://localhost:5173`, `5174`, `5480` + `FRONTEND_URL`. Запросы **без Origin** (мобильные клиенты, UE, curl) разрешены — для нативного UE-клиента CORS не помеха.

---

## 7. Схема данных Prisma (основные модели)

PostgreSQL, 19 моделей. Полная схема — `backend/prisma/schema.prisma`.

### Пользователи и auth

| Модель | Назначение | Ключевые поля |
|---|---|---|
| `User` | Аккаунт | `id (cuid)`, `email`, `username`, `password (bcrypt)`, `role (USER/MODERATOR/ADMIN)`, soft-delete `deletedAt` |
| `UserSettings` | Настройки | `theme`, `language`, `profileVisible`, `showOnlineStatus` |
| `UserStats` | Статистика | `gamesPlayed/Won/Lost`, `winRate`, `currentElo` (деф. 1200), `peakElo`, `heroStats (Json)` |
| `RefreshToken` | Ротация refresh | `token` (хэш), `expiresAt`, `revokedAt`, `replacedBy` |
| `Session` | Сессии | привязка к `User` |
| `AuthAuditLog` | Логи входов | события безопасности |

### Игры и состояние

| Модель | Назначение | Ключевые поля |
|---|---|---|
| `Game` | Партия | `status (GameStatus, деф. PENDING)`, `hostId`, `opponentId`, `mode`, `currentTurn` и др.; индексы под `myGames`, `availableGames` |
| `GamePlayer` | Участник | связь User↔Game, выбранная сторона |
| `GameState` | Полное состояние партии | `phase (деф. SETUP)`, состояние в JSON |
| `GameStateHistory` / `GameStateSnapshot` | История/снапшоты | версионирование, реплеи |
| `GameAction` | Журнал действий | audit-trail ходов |
| `GameReplay` | Реплеи | сжатые данные реплеев |

### Контент

| Модель | Назначение |
|---|---|
| `Hero` | Герои (характеристики, способности, привязка к сетам) |
| `Card` | Карты (типы, значения, эффекты) |
| `Board` | Игровые доски (клетки, двери, особенности) |

### Прочее

| Модель | Назначение |
|---|---|
| `MatchmakingQueueEntry` | Очередь матчмейкинга |
| `LeaderboardEntry` | Лидерборды |
| `Presence` | online / away / offline статусы игроков |

---

## 8. Инфраструктура

### PostgreSQL

- Версия 16 (alpine), локально порт **5433** (docker-compose) или 5432.
- Доступ через глобальный `PrismaService` (retry до 5 попыток с интервалом 5 c).
- Миграции: `backend/prisma/migrations`, управление через `prisma migrate dev`.

### Redis

- Версия 7 (alpine), порт **6379** (внешние подключения без пароля локально).
- `RedisService` держит **3 соединения**: client (кэш/локи), publisher, subscriber — под pub/sub событий игры между инстансами.
- Подключение с таймаутом 2 c и **graceful degradation**: без Redis бэкенд стартуется, real-time broadcast деградирует до in-process PubSub (одиночный инстанс работает).
- Использование: presence, кэш контента/карт, распределённые локи (матчмейкинг), pub/sub `game:updates:<gameId>`.

### BullMQ (очереди на Redis)

| Очередь | Модуль | Назначение |
|---|---|---|
| `game-action` | Games | Асинхронная обработка игровых действий |
| `combat-timeout` | Games | Таймауты разрешения боя |
| `matchmaking-scheduler` | Matchmaking | Cron-задачи поиска матчей |
| `match-confirmation` | Matchmaking | Таймауты 2-фазного подтверждения матча |
| `audit` | Audit | Асинхронная запись audit-логов (3 попытки, exponential backoff) |

### Наблюдаемость

- `GET /health`, `/health/live`, `/health/ready`, `/health/detail` — readiness/liveness (@nestjs/terminus).
- `GET /metrics` — Prometheus: `game_actions_total`, `combat_duration_seconds`, `card_effects_total`, `game_service_duration_seconds`, `path_cache_operations_total`, `game_service_errors_total`.

---

## 9. Что важно знать при подключении Unreal Engine

1. **GraphQL-клиент:** в UE нет «из коробки» GraphQL — используйте HTTP-плагин (queries/mutations) + WebSocket-плагин с поддержкой субпротокола `graphql-ws` (или собственную реализацию протокола: `connection_init` → `subscribe` → `next`/`complete`).
2. **Один endpoint `/graphql`** и для HTTP, и для WS — порт 3000.
3. **Токен в WS** передаётся через `connection_params` (`authorization: Bearer ...`), а не через HTTP-заголовок handshake.
4. **Точность схемы:** актуальный SDL смотрите в `backend/schema.gql` (генерируется при старте, `autoSchemaFile: true, sortSchema: true`) — имена типов/полей authorитетнее таблиц этого документа.
5. **Реконнект:** используйте `gameSequence` + `eventsSince` для догоняющей выборки пропущенных событий.
6. **Валидация входа:** сервер отклоняет неизвестные поля DTO (`forbidNonWhitelisted`) — отправляйте только поля из схемы.
7. **Rate limits:** не спамьте мутациями (троттлер 10 req/мин глобально по умолчанию, на auth — 5–10/мин).
