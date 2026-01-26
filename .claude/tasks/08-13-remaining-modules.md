# ФАЗЫ 8-13: Remaining Modules

## ФАЗА 8: Matchmaking Module

### Задача 8.1 - QueueManager

Создать менеджер очереди на Redis Sorted Sets.

### Действия:
1. Создать QueueManagerService:
   - `addToQueue(queueKey: string, userId: string, rating: number)`
   - `removeFromQueue(queueKey: string, userId: string)`
   - `findMatch(queueKey: string, rating: number, delta: number)`
   - `getQueueSize(queueKey: string)`

### Файлы:
```
backend/src/matchmaking/
└── queue-manager.service.ts
```

---

### Задача 8.2 - Matchmaking Service

Создать сервис матчмейкинга с expanding search window.

### Действия:
1. Создать MatchmakingService:
   - `joinQueue(userId: string, criteria: QueueCriteria)`
   - `leaveQueue(userId: string)`
   - `findMatch(criteria: QueueCriteria)`

2. Создать Cron job для поиска матчей (каждую секунду)

3. Реализовать expanding search window:
   - 0-30 сек: ±100 ELO
   - 30-60 сек: ±200 ELO
   - 60-120 сек: ±400 ELO
   - 120+ сек: без ограничений

### Файлы:
```
backend/src/matchmaking/
├── matchmaking.service.ts
└── matchmaking-scheduler.service.ts
```

---

### Задача 8.3 - Matchmaking GraphQL API

Создать резолвер для матчмейкинга.

### GraphQL Schema:
```graphql
type QueueEntry {
  userId: ID!
  criteria: QueueCriteria!
  joinedAt: DateTime!
  position: Int!
  estimatedWaitTime: Int!
}

type MatchFoundEvent {
  gameId: ID!
  players: [User!]!
  gameConfig: GameConfig!
}

extend type Mutation {
  joinQueue(criteria: QueueCriteria!): QueueEntry!
  leaveQueue: Boolean!
  acceptMatch(gameId: ID!): Boolean!
  declineMatch(gameId: ID!): Boolean!
}

extend type Subscription {
  matchFound(userId: ID!): MatchFoundEvent!
  queueUpdated(userId: ID!): QueueEntry!
}
```

---

## ФАЗА 9: Presence Module

### Задача 9.1 - Presence Service

Создать сервис онлайн-статуса.

### Действия:
1. Создать PresenceService:
   - `updatePresence(userId: string, status: PresenceStatus)`
   - `getPresence(userId: string)`
   - `getOnlineUserIds()`
   - `isUserOnline(userId: string)`

2. Хранить в Redis (TTL 5 мин)

### Файлы:
```
backend/src/presence/
└── presence.service.ts
```

---

### Задача 9.2 - Presence Gateway

Создать WebSocket Gateway для presence.

### Действия:
1. Создать PresenceGateway:
   - @SubscribeMessage('heartbeat')
   - @SubscribeMessage('subscribeToUsers')

2. Отправлять presence updates через pub/sub

### Файлы:
```
backend/src/presence/
└── presence.gateway.ts
```

---

## ФАЗА 10: History Module

### Задача 10.1 - Game Action Recording

Создать сервис записи действий.

### Действия:
1. Обновить GameStateService для записи действий
2. Создать GameActionService:
   - `recordAction(gameId: string, action: GameAction)`
   - `getGameActions(gameId: string)`

### Файлы:
```
backend/src/history/
└── game-action.service.ts
```

---

### Задача 10.2 - Replay Service

Создать сервис реплеев.

### Действия:
1. Создать ReplayService:
   - `buildReplay(gameId: string)`
   - `getReplay(replayId: string)`

2. Replay строится из последовательности GameAction

### Файлы:
```
backend/src/history/
└── replay.service.ts
```

---

### Задача 10.3 - Audit Service

Создать сервис аудита.

### Действия:
1. Создать AuditService:
   - `logAction(userId: string, action: AuditAction, metadata: any)`
   - `getUserAuditLog(userId: string)`

2. Логировать: login, logout, game_abuse, admin_actions

### Файлы:
```
backend/src/history/
└── audit.service.ts
```

---

## ФАЗА 11: Leaderboard Module

### Задача 11.1 - Leaderboard Service

Создать сервис таблицы лидеров.

### Действия:
1. Создать LeaderboardService:
   - `getLeaderboard(options: LeaderboardOptions)`
   - `refreshLeaderboards()` (cron job)

2. Оптимизировать запросы с materialized views

### Файлы:
```
backend/src/leaderboard/
├── leaderboard.service.ts
└── leaderboard-scheduler.service.ts
```

---

### Задача 11.2 - Stats Aggregator

Создать агрегатор статистики.

### Действия:
1. Создать StatsAggregator:
   - `calculateUserStats(userId: string)`
   - `getHeroStats(heroId: string)`
   - `getTimeFrameStats(timeFrame: string)`

### Файлы:
```
backend/src/leaderboard/
└── stats-aggregator.service.ts
```

---

## ФАЗА 12: Frontend Integration

### Задача 12.1 - Apollo Client Setup

Настроить Apollo Client на фронтенде.

### Действия:
1. Установить: `@apollo/client`, `graphql`
2. Настроить ApolloClient:
   - HTTP link: http://localhost:3000/graphql
   - WebSocket link: ws://localhost:3000/graphql
   - Auth link для токенов
3. Настроить error handling

### Файлы:
```
frontend/src/lib/
├── apollo-client.ts
└── graphql.ts
```

---

### Задача 12.2 - GraphQL Operations

Создать GraphQL операции.

### Действия:
1. Создать queries/mutations/subscriptions:
   - Auth: register, login, logout, refreshTokens
   - Game: createGame, joinGame, startGame, maneuver, attack, etc.
   - Matchmaking: joinQueue, leaveQueue

2. Использовать graphql-codegen для типизации

### Файлы:
```
frontend/src/graphql/
├── queries/
├── mutations/
└── subscriptions/
```

---

### Задача 12.3 - Enhanced GameStore

Обновить store для online режима.

### Действия:
1. Обновить gameStore:
   - Добавить `mode: 'offline' | 'online'`
   - Добавить GraphQL операции для online режима
   - Сохранить локальный GameEngine для offline
   - Добавить обработку subscriptions

2. Добавить reconnection logic

### Файлы:
```
frontend/src/store/
├── gameStore.ts
└── onlineGameStore.ts
```

---

### Задача 12.4 - Auth UI

Создать UI для авторизации.

### Действия:
1. Создать компоненты:
   - LoginForm
   - RegisterForm
   - ProfileSettings

2. Добавить роуты: /login, /register, /profile

### Файлы:
```
frontend/src/components/auth/
├── LoginForm.tsx
├── RegisterForm.tsx
└── ProfileSettings.tsx

frontend/src/pages/
├── LoginPage.tsx
├── RegisterPage.tsx
└── ProfilePage.tsx
```

---

## ФАЗА 13: Production Readiness

### Задача 13.1 - Testing

Написать тесты.

### Действия:
1. Unit tests для всех сервисов
2. Integration tests для GraphQL API
3. E2E tests для критичных flows

### Файлы:
```
backend/**/*.spec.ts
```

---

### Задача 13.2 - Logging & Monitoring

Настроить логирование и мониторинг.

### Действия:
1. Настроить structured logging (Winston/Pino)
2. Добавить request tracing
3. Настроить health checks

### Файлы:
```
backend/src/common/logging/
```

---

### Задача 13.3 - Performance

Оптимизировать производительность.

### Действия:
1. Добавить database indexes
2. Оптимизировать N+1 queries
3. Добавить response caching
4. Load testing

---

### Задача 13.4 - Security Hardening

Усилить безопасность.

### Действия:
1. Security audit
2. Rate limiting tuning
3. Input validation review
4. CORS configuration
5. Helmet.js headers
