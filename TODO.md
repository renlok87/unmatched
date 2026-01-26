# Unmatched Digital Edition - Архитектура Бэкенда v2.0

## 📊 Прогресс реализации

### ✅ ФАЗА 0: Infrastructure Setup (ЗАВЕРШЕНА)
- [x] 0.1 - Создана структура monorepo с backend директорией
- [x] 0.2 - Настроен Docker Compose (PostgreSQL 15, Redis 7, PgAdmin, Redis Commander)
- [x] 0.3 - Настроены ESLint, Prettier, Husky для backend
- [x] 0.4 - Создан .env.example с описанием всех переменных

**Файлы:**
- [docker-compose.yml](docker-compose.yml)
- [.env.docker](.env.docker)
- [backend/](backend/)
- [backend/.env.example](backend/.env.example)
- [backend/.eslintrc.json](backend/.eslintrc.json)
- [backend/.prettierrc](backend/.prettierrc)
- [backend/.gitignore](backend/.gitignore)
- [.husky/pre-commit](.husky/pre-commit)
- [.lintstagedrc.json](.lintstagedrc.json)

### ✅ ФАЗА 1: Core Infrastructure (ЗАВЕРШЕНА)
- [x] 1.1 NestJS Project Setup - ConfigModule настроен
- [x] 1.2 Prisma + PostgreSQL Setup - Полный schema создан
- [x] 1.3 Redis Setup - RedisModule с pub/sub, locks
- [x] 1.4 GraphQL Apollo Server Setup - Subscriptions настроены

**Файлы:**
- [backend/src/config/configuration.ts](backend/src/config/configuration.ts)
- [backend/prisma/schema.prisma](backend/prisma/schema.prisma)
- [backend/src/database/prisma.service.ts](backend/src/database/prisma.service.ts)
- [backend/src/redis/redis.service.ts](backend/src/redis/redis.service.ts)
- [backend/src/graphql/graphql.module.ts](backend/src/graphql/graphql.module.ts)

### ✅ ФАЗА 2: Auth Module (ЗАВЕРШЕНА)
- [x] 2.1 Auth Module - Core
- [x] 2.2 JWT Strategy & Guards
- [x] 2.3 Auth GraphQL API

**Файлы:**
- [backend/src/auth/auth.module.ts](backend/src/auth/auth.module.ts)
- [backend/src/auth/auth.service.ts](backend/src/auth/auth.service.ts)
- [backend/src/auth/auth.resolver.ts](backend/src/auth/auth.resolver.ts)
- [backend/src/auth/strategies/](backend/src/auth/strategies/)
- [backend/src/auth/guards/](backend/src/auth/guards/)
- [backend/src/auth/dto/](backend/src/auth/dto/)
- [backend/src/common/decorators/](backend/src/common/decorators/)

**Архитектурное ревью:** [02-auth-improvements.md](.claude/tasks/02-auth-improvements.md) — план улучшений безопасности

### 🚧 ФАЗА 2.1: Auth Module Improvements (ПЛАНИРУЕТСЯ)
> Критичные улучшения безопасности перед продакшеном

- [ ] Refresh Token Management (модель RefreshToken в Prisma)
- [ ] Redis Blacklist для logout
- [ ] Rate Limiting (@Throttle декораторы)
- [ ] Timing Attack Protection
- [ ] Transaction Safety при регистрации
- [ ] ENV Validation

---

## Обзор
Детально проработанная архитектура монолитного бэкенда на NestJS + PostgreSQL + GraphQL + Redis для онлайн-мультиплеера игры Unmatched.

**ВАЖНО**: Этот план учитывает официальные правила и уточнения по механикам игры (см. scraped-data/rules/UNMATCHED_RULES_RU.txt)

### Архитектурные принципы
- **Monolith first** — модули спроектированы с чёткими границами для возможного извлечения microservice позже
- **Event Sourcing для геймплея** — GameActions являются source of truth, GameState кэшируется
- **Defensive programming** — все внешние вводы валидируются, ожидается network failures

## Технологический стек
- **Framework**: NestJS 10.x с TypeScript 5.x
- **Database**: PostgreSQL 15+ с Prisma ORM (partitioning for GameActions)
- **API**: GraphQL с Apollo Server (Code-first подход)
- **Cache**: Redis 7+ (кэш, очереди, streams, блокировки)
- **Real-time**: GraphQL Subscriptions + Redis Streams (масштабируемость)
- **Auth**: JWT с refresh tokens + Passport
- **Validation**: class-validator + class-transformer

---

## Что НЕ входит в scope (Out of Scope)

Чтобы избежать scope creep, следующие задачи сознательно исключены из MVP:

| Функционал | Причина исключения | Когда рассматривать |
|------------|-------------------|---------------------|
| In-app покупки / монетизация | Не требуется для MVP | Post-MVP, при наличии user base |
| Клановая система / гильдии | Сложность > пользы на старте | После 1000+ активных игроков |
| Рейтинг с сезонами | Достаточно базового ELO | Post-MVP |
| AI противники (bot) | Требует отдельной архитектуры | Отдельный проект |
| Торговая система карт | Нет карт для торговли | N/A |
| Voice/Chat в игре | Сложно модерировать | Post-MVP |
| Мобильные приложения | Специфическая архитектура | После web версии |
| Turn-based async игры (игра по почте) | Требует перепроектирования timeline | Post-MVP |

---

## Non-Functional Requirements

| Категория | Требование | Метрика |
|-----------|-----------|---------|
| Performance | Latency игровых mutations | < 200ms p95 |
| Performance | Время доставки subscription | < 500ms p95 |
| Availability | Uptime | 99.5% (допускаются плановые окна) |
| Scalability | Одновременных игр | 1000+ (MVP), 10000+ (stretch) |
| Consistency | Game state consistency | Strong consistency в рамках игры |
| Security | Rate limiting | Per-user, per-endpoint |

---

## Ключевые игровые механики (по правилам Unmatched)

### 1. Типы действий
- **МАНЁВР (Maneuver)**: Перемещение бойца + розыгрыш карты с руки
- **АТАКА (Attack)**: Выбор смежного врага, розыгрыш карты атаки
  - Защищающийся может сыграть карту защиты
- **СБРОС (Pass)**: Сброс карты из руки + дополнительное действие (если есть)

### 2. Порядок применения эффектов в бою

```
1. Объявление атаки (атакующий выбирает цель)
2. Защищающийся может сыграть карту защиты
3. ЭФФЕКТЫ ВО ВРЕМЯ БОЯ (в порядке: атакующий → защищающийся → атакующий...)
4. Применение способностей героев (бонусы к атаке/защите)
5. Определение победителя (Атака - Защита)
6. Нанесение боевого урона
7. ЭФФЕКТЫ ПОСЛЕ БОЯ (сначала защищающийся, затем атакующий)
8. Дополнительные атаки (если есть)
```

**ВАЖНО**: Если два эффекта срабатывают одновременно - первым применяется эффект **Обороняющегося**

### 3. Модификаторы значений карт

| Тип модификатора | Поведение |
|------------------|-----------|
| "становится равным X" | Сбрасывает предыдущие модификаторы |
| "увеличьте/уменьшите на X" | Суммируется с другими модификаторами |
| "игнорируйте значение" | Значение не меняется, просто не учитывается |
| "не может быть изменено эффектами карт" | Значение фиксируется, но способности героев работают |

**Важное правило**: При наличии нескольких SET-модификаторов применяется **последний по времени применения**. Способности героев применяются поверх всех модификаторов карт.

**Пример**:
```
Базовое значение: 3
Карта А (SET 5): → 5
Карта Б (SET 3): → 3 (SET сбрасывает предыдущий SET)
Способность героя (+2): → 5
Итог: 5
```

### 4. Перемещение

| Термин | Правила |
|--------|---------|
| **Переместить** | Соблюдается смежность, нельзя сквозь врагов |
| **Поместить** | Телепортация на свободную ячейку, игнорирует правила |
| **Дистанция 0** | Включается в "до N ячеек" (можно остаться на месте) |
| **"на другую ячейку"** | Обязательно покинуть текущую ячейку |

### 5. Дополнительные атаки
- Цель сохраняется, даже если боец переместился
- Если защищающийся повержен первой атакой - доп. атака не происходит
- Если атакующий повержен, но игра не закончилась - доп. атака происходит

### 6. Истощение (Fatigue)
- Когда игрок обязан взять карту, но не может - **все** его бойцы получают 2 урона одновременно
- Урон от истощения ≠ сброс карты из колоды
- Урон наносится в момент, когда нужно взять карту

### 7. Специальные правила полей

#### Потайные ходы (Туман над мостовой)
- Ячейки считаются смежными **только для перемещения**
- Для атак и эффектов - НЕ смежные

#### Двери (Беовульф)
- Можно открывать/закрывать за 1 очко движения
- Закрытая дверь блокирует смежность и делит зоны

#### Возвышенность (Битва Легенд 2)
- +1 к атаке если: атакующий на возвышенности, защищающийся ниже, смежны, есть стрелка
- Бонус НЕ суммируется (максимум +1)
- Для доп. атаки проверяется заново

### 8. Особые механики героев

#### Дракула
- Способность: может наносить 1 урон **любому** смежному бойцу (включая Сестёр)
- "Исполняй мои приказания": эффект срабатывает **до** возможности сыграть "Уловку"

#### Король Артур
- Усиление (Boost) - эффект **способности**, не карты
- Не отменяется "Уловкой"
- Работает поверх "Невидимого противника"

#### Человек-Невидимка
- Жетоны тумана: ячейки считаются свободными для размещения
- Перемещение между жетонами работает как смежность
- "Невидимый противник": значение становится 0, эффекты карт не отменяются
- Способности героев (например, Артура) работают поверх "Невидимого противника"

#### Сунь Укун
- Клоны получают урон при истощении (все бойцы одновременно)
- "Золотая кольчуга": если урон перенаправлен → Укун не получил урона → победил защищающийся

#### Йенненга
- Лучники возвращаются с **2 здоровья**
- Урон от истощения нельзя перенаправить (наносится всем одновременно)

#### Красная Шапочка
- Символ "Любой" = любой предмет, но не обязан активировать эффект
- При сбросе карты меняется содержимое корзинки

### 9. Проверки GameRulesValidator

```typescript
// Должен проверять:
- Можно ли сыграть карту (тип: атака/защита/приём)
- Смежность для атак (ближний бой)
- Находится ли в зоне (дальний бой)
- Соблюдены ли условия эффекта карты
- Достаточно очков движения
- Есть ли действия для розыгрыша
- Правила размещения бойцов (зона героя, помощники)

// Специальные случаи:
- Потайные ходы: смежность только для перемещения
- Двери: проверять статус (открыта/закрыта)
- Возвышенность: проверять бонус к атаке
```

---

## Архитектурные диаграммы

### 1.1 Общая архитектура системы

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Клиент (React)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Apollo CLI  │  │   Zustand    │  │   React UI   │  │   Game UI    │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API Gateway (NestJS)                             │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    GraphQL Apollo Server                            │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │ │
│  │  │ Queries │ │Mutations│ │Subscrip.│ │ Guards  │ │ Interceptors│  │ │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └──────┬──────┘  │ │
│  └───────┼────────────┼────────────┼────────────┼───────────────┼───────┘ │
└──────────┼────────────┼────────────┼────────────┼───────────────┼─────────┘
           │            │            │            │               │
           ▼            ▼            ▼            ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Business Logic Layer                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │   Auth   │ │   Game   │ │Matchmake.│ │Leaderbrd │ │   Content    │  │
│  │  Module  │ │  Module  │ │  Module  │ │  Module  │ │    Module    │  │
│  │          │ │          │ │          │ │          │ │              │  │
│  │ ┌──────┐ │ │ ┌──────┐ │ │ ┌──────┐ │ │ ┌──────┐ │ │ ┌──────────┐ │  │
│  │ │JWT   │ │ │ │Game  │ │ │ │Rating│ │ │ │Stats │ │ │ │   Hero   │ │  │
│  │ │Auth  │ │ │ │Engine│ │ │ │Service│ │ │      │ │ │ │  Service │ │  │
│  │ └──────┘ │ │ │      │ │ │ └──────┘ │ │ └──────┘ │ │ │   Card   │ │  │
│  │ ┌──────┐ │ │ │Rules │ │ │ ┌──────┐ │ │          │ │ │  Service │ │  │
│  │ │Passp.│ │ │ │Valid.│ │ │ │Queue │ │ │          │ │ └──────────┘ │  │
│  │ └──────┘ │ │ └──────┘ │ │ │Mgr   │ │ │          │ │              │  │
│  └──────────┘ │          │ │ └──────┘ │ │          │ │              │  │
│               │ ┌──────┐ │ │          │ │          │ │              │  │
│               │ │Lock  │ │ │          │ │          │ │              │  │
│               │ │Mgr   │ │ │          │ │          │ │              │  │
│               │ └──────┘ │ │          │ │          │ │              │  │
│               └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
           │            │            │            │               │
           ▼            ▼            ▼            ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Data Access Layer                               │
│  ┌──────────────┐              ┌──────────────┐                        │
│  │ Prisma ORM   │              │   Redis      │                        │
│  │              │              │              │                        │
│  │ ┌──────────┐ │              │ ┌──────────┐ │                        │
│  │ │  User    │ │              │ │ Game     │ │                        │
│  │ │  Game    │ │              │ │ State    │ │                        │
│  │ │ GameState│ │              │ │ Streams  │ │  ← Redis Streams        │
│  │ │ Action   │ │              │ │ Locks    │ │                        │
│  │ └──────────┘ │              │ │ Presence │ │                        │
│  └──────┬───────┘              │ └──────────┘ │                        │
└─────────┼───────────────────────┴──────┬───────┘                        │
          │                              │                                │
          ▼                              ▼                                │
┌───────────────────────┐    ┌───────────────────────┐                     │
│   PostgreSQL 15+      │    │      Redis 7+         │                     │
│  ┌─────────────────┐  │    │  ┌─────────────────┐  │                     │
│  │ Users           │  │    │  │ Cache (TTL)     │  │                     │
│  │ Games           │  │    │  │ Streams (Pub)   │  │                     │
│  │ GameStates      │  │    │  │ Streams (Cons.) │  │                     │
│  │ GameActions     │  │    │  │ Distributed LK  │  │                     │
│  │ (Partitioned)   │  │    │  │ Queue Manager   │  │                     │
│  │ Leaderboards    │  │    │  └─────────────────┘  │                     │
│  └─────────────────┘  │    └───────────────────────┘                     │
└───────────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Модульная архитектура NestJS

```
AppModule (root)
├── ConfigModule (@nestjs/config) - конфигурация
├── PrismaModule (@nestjs/prisma) - БД
├── RedisModule (@nestjs/terminus+ioredis) - кэш
│
├── AuthModule (авторизация + JWT)
│   ├── AuthService - регистрация, вход, токены
│   ├── JwtStrategy - Passport JWT
│   ├── RefreshGuard - refresh token validation
│   ├── GqlAuthGuard - защита резолверов
│   └── ThrottlerGuard - rate limiting
│
├── UsersModule (пользователи + профили)
│   ├── UsersService - CRUD операции
│   ├── UserStatsService - статистика + ELO
│   └── ProfileService - аватары, настройки
│
├── GameModule (игровые сессии + логика)
│   ├── GameService - управление сессиями
│   ├── GameStateService - сериализация/персистентность
│   ├── GameEngineService - игровая логика (портирована)
│   ├── GameRulesValidator - валидация действий
│   ├── DistributedLockService - блокировки на Redis
│   ├── GameResolver - GraphQL + Subscriptions
│   └── dto/ - все input/output типы
│
├── MatchmakingModule (матчмейкинг)
│   ├── MatchmakingService - поиск матчей
│   ├── RatingService - расчёт ELO
│   ├── QueueManagerService - Redis очередь
│   └── MatchmakingResolver - GraphQL + Subscriptions
│
├── LeaderboardModule (рейтинги)
│   ├── LeaderboardService - агрегация
│   ├── StatsAggregator - расчёт статистики
│   └── LeaderboardResolver - GraphQL
│
├── ContentModule (статический контент)
│   ├── HeroService - определения героев
│   ├── CardService - определения карт
│   ├── BoardService - определения досок
│   └── ContentResolver - GraphQL
│
├── PresenceModule (онлайн статус)
│   ├── PresenceService - отслеживание (Redis)
│   └── PresenceGateway - WebSocket events
│
├── HistoryModule (реплеи + аудит)
│   ├── GameActionService - запись действий
│   ├── ReplayService - восстановление игр
│   └── AuditService - аудит лог
│
└── CommonModule (общая функциональность)
    ├── guards/ - все guards
    ├── decorators/ - кастомные декораторы
    ├── interceptors/ - логирование, трансформация
    ├── filters/ - обработка ошибок
    ├── pipes/ - валидация
    └── utils/ - вспомогательные функции
```

---

## 2. Детальное описание модулей

### 2.1 AuthModule

**Ответственность**: Аутентификация, авторизация, управление сессиями

#### Компоненты
```typescript
// services/auth.service.ts
class AuthService {
  register(dto: RegisterDto): Promise<AuthResponse>
  login(dto: LoginDto): Promise<AuthResponse>
  refreshTokens(refreshToken: string): Promise<TokensPair>
  logout(userId: string): Promise<void>
  generateTokens(userId: string): TokensPair
  validateUser(email: string, password: string): Promise<User>
}

// strategies/jwt.strategy.ts
class JwtStrategy extends PassportStrategy(Strategy) {
  validate(payload: JwtPayload): Promise<User>
}

// strategies/refresh.strategy.ts
class RefreshStrategy extends PassportStrategy(Strategy) {
  validate(payload: JwtPayload): Promise<User>
}

// guards/gql-auth.guard.ts
class GqlAuthGuard implements CanActivate {
  getRequest(context: GqlExecutionContext): Request
  canActivate(): boolean
}

// guards/gql-public.guard.ts
class GqlPublicGuard implements CanActivate {
  handleRequest(err, user, info): User
}

// dto/
RegisterDto, LoginDto, AuthResponse, TokensPair
```

#### GraphQL API
```graphql
type AuthPayload {
  accessToken: String!
  refreshToken: String!
  user: User!
}

extend type Mutation {
  register(input: RegisterInput!): AuthPayload!
  login(input: LoginInput!): AuthPayload!
  logout: Boolean!
  refreshTokens(refreshToken: String!): AuthPayload!
}
```

#### Security
- **Access Token**: 15 минут, хранится в памяти клиента
- **Refresh Token**: 7 дней, HttpOnly cookie + SameSite=Strict
- **Password**: bcrypt с salt rounds = 10
- **Rate Limiting**: 5 попыток входа за 15 минут на IP

---

### 2.2 UsersModule

**Ответственность**: Профили пользователей, статистика, настройки

#### Компоненты
```typescript
// services/users.service.ts
class UsersService {
  findById(id: string): Promise<User>
  findByEmail(email: string): Promise<User>
  updateProfile(userId: string, dto: UpdateProfileDto): Promise<User>
  changePassword(userId: string, dto: ChangePasswordDto): Promise<void>
  deleteAccount(userId: string): Promise<void>
}

// services/user-stats.service.ts
class UserStatsService {
  getStats(userId: string): Promise<UserStats>
  updateStatsAfterGame(gameId: string, userId: string): Promise<void>
  getLeaderboard(options: LeaderboardOptions): Promise<LeaderboardEntry[]>
  recalculateElo(winnerId: string, loserId: string): Promise<void>
}

// services/profile.service.ts
class ProfileService {
  uploadAvatar(userId: string, file: File): Promise<string>
  updateSettings(userId: string, dto: SettingsDto): Promise<UserSettings>
}
```

#### GraphQL API
```graphql
type User {
  id: ID!
  email: String!
  username: String!
  avatar: String
  createdAt: DateTime!
  settings: UserSettings
}

type UserStats {
  userId: ID!
  gamesPlayed: Int!
  gamesWon: Int!
  gamesLost: Int!
  winRate: Float!
  currentElo: Int!
  peakElo: Int!
  favoriteHero: Hero
}

type LeaderboardEntry {
  rank: Int!
  user: User!
  elo: Int!
  gamesWon: Int!
  gamesPlayed: Int!
}

extend type Query {
  me: User
  user(id: ID!): User
  myStats: UserStats
  leaderboard(
    hero: String
    timeFrame: TimeFrame
    limit: Int
  ): [LeaderboardEntry!]!
}

extend type Mutation {
  updateProfile(input: UpdateProfileInput!): User!
  changePassword(input: ChangePasswordInput!): Boolean!
  deleteAccount: Boolean!
}
```

---

### 2.3 GameModule

**Ответственность**: Игровые сессии, игровая логика, валидация, блокировки

#### Компоненты

##### GameService
```typescript
class GameService {
  // CRUD
  createGame(dto: CreateGameDto): Promise<Game>
  getGame(gameId: string): Promise<Game>
  listGames(filters: GameFilters): Promise<Game[]>
  joinGame(gameId: string, heroId: string): Promise<Game>
  leaveGame(gameId: string): Promise<void>
  startGame(gameId: string): Promise<Game>

  // State management
  getGameState(gameId: string): Promise<GameState>
  updateGameState(gameId: string, state: GameState): Promise<void>

  // Lifecycle
  endGame(gameId: string, winnerId: string): Promise<void>
  abortGame(gameId: string, reason: AbortReason): Promise<void>
}
```

##### GameStateService
```typescript
class GameStateService {
  // Persistence
  saveState(gameId: string, state: GameState): Promise<void>
  loadState(gameId: string): Promise<GameState>

  // Cache
  cacheState(gameId: string, state: GameState): Promise<void>
  getCachedState(gameId: string): Promise<GameState | null>

  // Serialization
  serialize(state: GameState, forPlayerId: string): SerializedGameState
  deserialize(data: SerializedGameState): GameState

  // Privacy - скрытие карт соперника
  filterPrivateData(state: GameState, playerId: string): GameState
}
```

##### GameEngineService
```typescript
class GameEngineService {
  // Инициализация
  initializeGame(config: GameConfig): GameState

  // Игровые действия
  maneuver(state: GameState, dto: ManeuverDto): GameState
  moveFighter(state: GameState, dto: MoveDto): GameState
  attack(state: GameState, dto: AttackDto): GameState
  playDefense(state: GameState, dto: DefenseDto): GameState  // изменено с defend
  resolveCombat(state: GameState, combatData: CombatData): GameState
  endTurn(state: GameState): GameState
  pass(state: GameState): GameState

  // Combat - ключевой метод с правильным порядком эффектов
  resolveCombat(state: GameState, attackerId: string, defenderId: string,
                attackCard: Card, defenseCard?: Card): CombatResult {
    // 1. Проверяем смежность/зону
    // 2. Защищающийся может сыграть карту защиты (опционально)

    // 3. Собираем эффекты ВО ВРЕМЯ БОЯ с обеих карт
    //    - Создаём список эффектов с привязкой к владельцу (attacker/defender)

    // 4. Сортируем одновременные эффекты:
    //    - Эффекты защищающегося → первыми
    //    - Эффекты атакующего → вторыми
    //    - Если несколько эффектов одного игрока → по timestamp применения

    // 5. Применяем эффекты по порядку
    //    - Учёт модификаторов (SET сбрасывает, ADD суммируется)
    //    - Фиксация "последний SET выигрывает"

    // 6. Применяем способности героев (поверх всех модификаторов карт)

    // 7. Вычисляем итоговые значения (applyValueModifiers)

    // 8. Определяем победителя (Атака - Защита)
    //    - Если атака = 0 → побеждает защищающийся

    // 9. Наносим боевой урон

    // 10. Применяем эффекты ПОСЛЕ БОЯ
    //     - Сначала защищающийся, затем атакующий

    // 11. Обрабатываем дополнительные атаки
    //     - Цель сохраняется, даже если боец переместился
  }

  // Модификаторы значений карт
  applyValueModifiers(baseValue: number, modifiers: ValueModifier[]): number {
    // Алгоритм применения:
    // 1. Найти последний SET-модификатор по timestamp
    //    - Если есть → baseValue = setValue, сбросить все предыдущие
    // 2. Применить все ADD-модификаторы (суммировать)
    // 3. Применить IGNORE (пропустить при подсчёте, но не сбрасывать)
    // 4. Применить способности героев (поверх всех модификаторов)

    // Пример:
    // baseValue = 3
    // [SET 5, ADD 2, SET 3, ADD 1] → 3 (SET) + 1 (ADD) = 4
    // [SET 5, ADD 2] → 5 (SET) + 2 (ADD) = 7
  }

  // Queries
  getValidMoves(state: GameState, fighterId: string): Position[]
  getValidTargets(state: GameState, attackerId: string): Fighter[]
  canPlayCard(state: GameState, playerId: string, cardId: string): boolean
  checkAdjacency(state: GameState, pos1: Position, pos2: Position,
                 forMovement: boolean): boolean  // для потайных ходов
}
```

##### GameRulesValidator
```typescript
class GameRulesValidator {
  // Валидация действий перед применением
  validateManeuver(state: GameState, dto: ManeuverDto): ValidationResult
  validateMove(state: GameState, dto: MoveDto): ValidationResult
  validateAttack(state: GameState, dto: AttackDto): ValidationResult
  validateDefense(state: GameState, dto: DefenseDto): ValidationResult
  validateTurn(state: GameState, playerId: string): ValidationResult

  // Проверки смежности (с учётом специальных полей)
  isAdjacent(state: GameState, pos1: Position, pos2: Position,
             context: 'movement' | 'attack' | 'effect'): boolean
  // - Потайные ходы: смежны только для movement
  // - Двери: проверять статус (открыта/закрыта)

  // Проверки размещения
  canPlaceFighter(state: GameState, fighterId: string, pos: Position): boolean
  // - Зона героя для стартового размещения
  // - Если зона забита: смежные ячейки (только для старта)
  // - Жетоны тумана считаются свободными

  // Проверки состояния
  isPlayerTurn(state: GameState, playerId: string): boolean
  hasActionsRemaining(state: GameState, playerId: string): boolean
  isGameActive(state: GameState): boolean

  // Проверки карт
  canPlayCardAsAttack(state: GameState, card: Card): boolean  // не защита/приём
  canPlayCardAsDefense(state: GameState, card: Card): boolean  // не атака/приём

  // Проверки бонуса возвышенности
  getHighGroundBonus(state: GameState, attackerPos: Position,
                     defenderPos: Position): number  // 0 или 1
}
```

##### DistributedLockService
```typescript
class DistributedLockService {
  // Получить блокировку на игру для предотвращения race conditions
  // TTL увеличен до 10 сек + auto-extend для защиты от GC pause
  acquireGameLock(gameId: string, ttl: number = 10000): Promise<Lock>

  // Освободить блокировку
  releaseLock(lock: Lock): Promise<void>

  // Автоматически продлевать блокировку во время выполнения
  withAutoExtendLock<T>(gameId: string, fn: (signal: AbortSignal) => Promise<T>): Promise<T>

  // Выполнить действие под блокировкой (backward compat)
  withLock<T>(gameId: string, fn: () => Promise<T>): Promise<T>

  // Проверить занятость игры
  isGameLocked(gameId: string): Promise<boolean>
}

// Пример auto-extend:
// Lock acquired (TTL: 10s)
// [5s elapsed] → extend to 10s
// [8s elapsed] → extend to 10s
// Lock released
```

#### GraphQL API
```graphql
# Типы
type Game {
  id: ID!
  status: GameStatus!
  players: [GamePlayer!]!
  currentTurn: Int
  phase: GamePhase
  createdAt: DateTime!
  startedAt: DateTime
  endedAt: DateTime
  winner: User
}

type GamePlayer {
  id: ID!
  user: User!
  hero: Hero!
  isReady: Boolean!
  hasPassed: Boolean!
}

type GameState {
  id: ID!
  gameId: ID!
  players: [PlayerState!]!
  board: BoardState!
  currentTurn: TurnState!
  phase: GamePhase!
  combatState: CombatState
  turnCount: Int!
  sequenceNumber: Int!  # для реконнекта
}

type GameEvent {
  type: GameEventType!
  sequenceNumber: Int!
  timestamp: DateTime!
  payload: JSON!
}

# Queries
extend type Query {
  game(id: ID!): Game
  myGames(status: GameStatus, limit: Int): [Game!]!
  gameState(gameId: ID!): GameState
  availableGames: [Game!]!
}

# Mutations
extend type Mutation {
  # Game management
  createGame(input: CreateGameInput!): Game!
  joinGame(gameId: ID!, heroId: ID!): Game!
  leaveGame(gameId: ID!): Boolean!
  startGame(gameId: ID!): Game!
  abortGame(gameId: ID!, reason: String): Boolean!

  # Игровые действия (все требуют блокировок)
  maneuver(gameId: ID!, fighterId: ID!, cardId: ID!, path: [PositionInput!]!): GameState!
  moveFighter(gameId: ID!, fighterId: ID!, x: Int!, y: Int!): GameState!
  attack(gameId: ID!, attackerId: ID!, cardId: ID!, targetId: ID!): GameState!
  playDefense(gameId: ID!, cardId: ID!): GameState!  # защищающийся отвечает на атаку
  resolveCombat(gameId: ID!): GameState!
  endTurn(gameId: ID!): GameState!
  pass(gameId: ID!): GameState!

  # Действия с полями
  toggleDoor(gameId: ID!, x: Int!, y: Int!): GameState!  # открыть/закрыть дверь
}

# Subscriptions
extend type Subscription {
  gameStateUpdated(gameId: ID!): GameState!
  gameEvent(gameId: ID!): GameEvent!
  playerJoined(gameId: ID!): GamePlayer!
  playerLeft(gameId: ID!): ID!
}
```

#### Flow для игровых действий
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Mutation: maneuver(gameId, ...)                   │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     1. GqlAuthGuard проверяет токен                      │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              2. GameResolver получает запрос с userId                     │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     3. DistributedLockService.acquireGameLock(gameId, 5000ms)            │
│        - Ожидание блокировки max 5 секунд                                │
│        - Если timeout → ошибка "Game is busy"                             │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     4. GameRulesValidator.validateManeuver(state, dto)                   │
│        - Проверка: очередь игрока?                                       │
│        - Проверка: достаточно действий?                                  │
│        - Проверка: карта есть в руке?                                    │
│        - Если невалидно → ошибка + releaseLock                           │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     5. GameEngineService.maneuver(state, dto)                            │
│        - Применяет действие к state                                      │
│        - Возвращает новый GameState                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     6. GameStateService.saveState(gameId, newState)                      │
│        - Сохраняет в PostgreSQL (GameActions table)                      │
│        - Кэширует в Redis (game:state:{gameId})                         │
│        - Инкрементирует sequenceNumber                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     7. PubSub.publish('game:state:updated', { gameId, state })           │
│        - Отправляет в Redis Pub/Sub                                      │
│        - GraphQL Subscriptions подхватывают и шлют клиентам             │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     8. DistributedLockService.releaseLock(lock)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     9. Return GameState (фильтрованный для текущего игрока)              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 2.4 MatchmakingModule

**Ответственность**: Поиск соперников, очереди, расчёт рейтинга

#### Компоненты
```typescript
class MatchmakingService {
  joinQueue(userId: string, criteria: QueueCriteria): Promise<QueueEntry>
  leaveQueue(userId: string): Promise<void>
  findMatch(criteria: QueueCriteria): Promise<Match | null>
  cancelMatchmaking(gameId: string): Promise<void>
}

class RatingService {
  calculateNewRatings(winnerElo: number, loserElo: number): {winner: number, loser: number}
  getPlayerRating(userId: string, heroId?: string): Promise<number>
}

class QueueManagerService {
  // Redis sorted sets для очередей
  addToQueue(queueKey: string, userId: string, rating: number): Promise<void>
  removeFromQueue(queueKey: string, userId: string): Promise<void>
  findMatch(queueKey: string, rating: number, delta: number): Promise<string | null>
  getQueueSize(queueKey: string): Promise<number>
}
```

#### GraphQL API
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

#### Matchmaking Algorithm
```
1. Игрок вступает в очередь с указанием критериев:
   - gameMode (1v1, 2v2, free-for-all)
   - heroPreference (опционально)
   - ratingRange (опционально)

2. QueueManager помещает игрока в Redis Sorted Set:
   Key: "queue:{gameMode}"
   Score: playerElo
   Member: JSON с userId и metadata

3. Фоновый процесс (Cron) каждую секунду:
   - Для каждого игрока ищет соперника в диапазоне ±EloDelta
   - EloDelta растёт со временем ожидания:
     * 0-30 сек: ±100
     * 30-60 сек: ±200
     * 60-120 сек: ±400
     * 120+ сек: без ограничений

4. При нахождении матча:
   - Создаётся игра в статусе PENDING
   - Оба игрока получают matchFound subscription
   - 30 секунд на принятие
   - Если кто-то отклонил/таймаут → другому возвращается в очередь

5. После принятия обоими:
   - Игра переходит в LOBBY
   - Игроки выбирают героев
   - Host может начать игру
```

---

### 2.5 ContentModule

**Ответственность**: Статические данные игры (герои, карты, доски)

#### Стратегия
- Данные versioned и загружаются при старте сервера
- Кэшируются в памяти (без TTL)
- CDN для статических ассетов (картинки героев)

```typescript
class ContentService {
  // Heroes
  getAllHeroes(): Hero[]
  getHeroById(id: string): Hero
  getHeroesBySet(set: string): Hero[]

  // Cards
  getAllCards(): Card[]
  getCardsByHero(heroId: string): Card[]

  // Boards
  getAllBoards(): Board[]
  getBoardById(id: string): Board

  // Versioning
  getCurrentVersion(): string
  getContentDiff(oldVersion: string): ContentDiff
}
```

#### GraphQL API
```graphql
extend type Query {
  heroes: [Hero!]!
  hero(id: ID!): Hero!
  cards(heroId: ID!): [Card!]!
  boards: [Board!]!
  board(id: ID!): Board!
  contentVersion: String!
}
```

---

### 2.6 PresenceModule

**Ответственность**: Онлайн-статус, heartbeat

```typescript
class PresenceService {
  // Heartbeat каждые 30 секунд
  updatePresence(userId: string, status: PresenceStatus): Promise<void>
  getPresence(userId: string): Promise<Presence | null>
  getOnlineUserIds(): Promise<string[]>
  isUserOnline(userId: string): Promise<boolean>
}

class PresenceGateway extends Gateway {
  // WebSocket для presence событий
  @SubscribeMessage('heartbeat')
  handleHeartbeat(@ConnectedSocket() socket: Socket): void

  @SubscribeMessage('subscribeToUsers')
  subscribeToUsers(@MessageBody() userIds: string[]): void
}
```

---

### 2.7 HistoryModule

**Ответственность**: Реплеи, аудит лог

```typescript
class GameActionService {
  recordAction(gameId: string, action: GameAction): Promise<void>
  getGameActions(gameId: string): Promise<GameAction[]>
}

class ReplayService {
  buildReplay(gameId: string): Promise<Replay>
  getReplay(replayId: string): Promise<Replay>
}

class AuditService {
  logAction(userId: string, action: AuditAction, metadata: any): Promise<void>
  getUserAuditLog(userId: string): Promise<AuditEntry[]>
}
```

---

## 3. База данных (PostgreSQL + Prisma Schema)

### 3.1 Полная схема Prisma

```prisma
// prisma/schema.prisma

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

// ============================================
// USERS & AUTH
// ============================================

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  username  String   @unique
  password  String   // bcrypt hash
  avatar    String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  // Relations
  stats     UserStats?
  settings  UserSettings?
  gamePlayers GamePlayer[]
  ownedGamesAsPlayer1 Game[] @relation("Player1Games")
  ownedGamesAsPlayer2 Game[] @relation("Player2Games")

  @@index([email])
  @@index([username])
}

model UserSettings {
  id               String  @id @default(cuid())
  userId           String  @unique
  user             User    @relation(fields: [userId], references: [id], onDelete: Cascade)

  // Preferences
  theme            String  @default("dark")
  language         String  @default("ru")
  soundEnabled     Boolean @default(true)
  musicEnabled     Boolean @default(true)

  // Privacy
  profileVisible   Boolean @default(true)
  showOnlineStatus Boolean @default(true)
}

model UserStats {
  id              String   @id @default(cuid())
  userId          String   @unique
  user            User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  // Overall stats
  gamesPlayed     Int      @default(0)
  gamesWon        Int      @default(0)
  gamesLost       Int      @default(0)
  winRate         Float    @default(0)

  // ELO rating
  currentElo      Int      @default(1200)
  peakElo         Int      @default(1200)

  // Hero stats (JSONB для гибкости)
  heroStats       Json     @default("{}")

  // Time-based stats
  lastPlayedAt    DateTime?
  totalPlayTime   Int      @default(0) // seconds

  @@index([currentElo])
  @@index([gamesWon])
}

// ============================================
// GAMES
// ============================================

enum GameStatus {
  PENDING     // Создана, ожидание игроков
  LOBBY       // Лобби, выбор героев
  IN_PROGRESS // Игра идёт
  PAUSED      // Пауза
  FINISHED    // Завершена
  ABORTED     // Прервана
}

enum GameMode {
  ONE_V_ONE
  TWO_V_TWO
  FREE_FOR_ALL
  VS_AI
}

enum GamePhase {
  SETUP          // Подготовка (размещение бойцов)
  TURN_START     // Начало хода (способности в начале хода)
  ACTION_MANEUVER // Манёвр
  ACTION_ATTACK  // Атака
  COMBAT         // Бой (ожидание защиты)
  COMBAT_RESOLVE // Разрешение боя
  TURN_END       // Конец хода
}

model Game {
  id          String     @id @default(cuid())
  status      GameStatus @default(PENDING)
  mode        GameMode   @default(ONE_V_ONE)

  // Host (создатель)
  hostId      String
  host        User       @relation("Player1Games", fields: [hostId], references: [id])

  // Опционально второй игрок для 1v1
  opponentId  String?
  opponent    User?      @relation("Player2Games", fields: [opponentId], references: [id])

  // Board
  boardId     String
  boardState  Json?      // состояние дверей, жетонов тумана и т.д.

  // Timing
  createdAt   DateTime   @default(now())
  updatedAt   DateTime   @updatedAt  // для сортировки по времени обновления
  startedAt   DateTime?
  endedAt     DateTime?

  // Winner
  winnerId    String?

  // Version для optimistic locking
  version     Int        @default(0)

  // Relations
  players     GamePlayer[]
  state       GameState?
  actions     GameAction[]

  // Индексы для оптимизации запросов
  @@index([status])
  @@index([hostId])
  @@index([hostId, status])  // "my games" query
  @@index([createdAt])
  @@index([status, createdAt]) // для листинга активных игр
  @@index([mode, status])  // "find 1v1 games"
  @@index([winnerId])  // "games I won" query
  @@index([updatedAt])  // для сортировки по времени обновления
}

model GamePlayer {
  id          String   @id @default(cuid())
  gameId      String
  game        Game     @relation(fields: [gameId], references: [id], onDelete: Cascade)

  userId      String
  user        User     @relation(fields: [userId], references: [id])

  // Hero selection
  heroId      String?  // выбран в лобби

  // Status
  isReady     Boolean  @default(false)
  hasPassed   Boolean  @default(false)

  // Position за столом (для порядка ходов)
  seatOrder   Int      @default(0)

  @@unique([gameId, userId])
  @@index([gameId])
}

// ============================================
// GAME STATE
// ============================================

model GameState {
  id              String   @id @default(cuid())
  gameId          String   @unique
  game            Game     @relation(fields: [gameId], references: [id], onDelete: Cascade)

  // Полное состояние в JSONB
  // Структура:
  // {
  //   players: [{
  //     userId, heroId, fighters: [{id, health, maxHealth, position, ...}],
  //     hand: [{cardId, ...}], deck: [cardIds], discard: [cardIds],
  //     actionsRemaining, hasPassed
  //   }],
  //   board: { cells: [{x, y, type, ...}] },
  //   currentTurn: { playerId, phase, actionCount },
  //   combatState: { // если идёт бой
  //     attackerId, defenderId, attackCard, defenseCard,
  //     effectsApplied: [], awaitingDefense: boolean
  //   },
  //   activeEffects: [{type, source, target, timing, ...}],
  //   fogTokens: [{x, y, ownerId}] // для Невидимки
  // }
  state           Json

  // Sequence number для optimistic updates и реконнекта
  sequenceNumber  Int      @default(0)

  // Для оптимизации запросов
  currentTurnPlayerId String?
  phase           String   @default("SETUP")
  turnCount       Int      @default(0)

  updatedAt       DateTime @updatedAt

  @@index([gameId])
  @@index([sequenceNumber])
}

// ============================================
// GAME ACTIONS (for replay/audit)
// ============================================

enum GameActionType {
  // Game management
  GAME_CREATED
  GAME_JOINED
  GAME_STARTED
  GAME_ENDED
  GAME_ABORTED

  // Turn actions
  TURN_STARTED
  TURN_ENDED
  PASSED

  // Card actions
  CARD_PLAYED
  CARD_DISCARDED

  // Movement
  FIGHTER_MOVED
  MANEUVER
  PLACED  // для эффекта "поместить"

  // Combat
  ATTACK_INITIATED
  DEFENSE_PLAYED
  COMBAT_RESOLVED
  EFFECT_APPLIED

  // Special
  SPECIAL_ABILITY
  DOOR_TOGGLED  // для дверей Беовульфа
}

model GameAction {
  id              String          @id @default(cuid())
  gameId          String
  game            Game            @relation(fields: [gameId], references: [id], onDelete: Cascade)

  type            GameActionType
  sequenceNumber  Int

  // Кто сделал действие
  playerId        String?

  // Данные действия
  payload         Json            // { fighterId, targetId, cardId, ... }

  // Для diff/state recovery
  previousStateId String?         // ссылка на предыдущий GameState
  newStateId     String?         // ссылка на новый GameState

  timestamp       DateTime        @default(now())

  // Partitioning: по createdAt для удаления старых данных
  // В migration: PARTITION BY RANGE (createdAt)
  @@index([gameId, sequenceNumber])
  @@index([gameId, timestamp])
  @@index([timestamp])  // для partitioning cleanup
}

// Политика очистки (реализуется через pg_cron или приложение):
// - GameActions старше 30 дней → архив в S3/Cold storage
// - Games со статусом FINISHED старше 7 дней → сжать state

// ============================================
// HEROES (для Content Module)
// ============================================

model Hero {
  id          String   @id @default(cuid())
  name        String   @unique
  nameEn      String   // английское название
  nameRu      String   // русское название
  set         String   // выпуск (например, "Битва легенд. Том первый")

  // Характеристики
  health      Int
  fighterType String   // HERO, MINION, HUGE

  // Способность (в формате JSON для гибкости)
  ability     Json     // { type, timing, effect, description }

  // Стартовое содержание колоды
  deckCards   Json     // [{cardId, count}, ...]

  // Специфические свойства
  properties  Json?    // { hasSidekick: true, sidekickCount: 2, ... }

  // Медиа
  imageUrl    String?
  avatarUrl   String?

  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt

  @@index([set])
}

// ============================================
// CARDS (для Content Module)
// ============================================

model Card {
  id          String   @id @default(cuid())
  name        String
  nameEn      String   // английское название
  nameRu      String   // русское название

  // Тип карты
  cardType    String   // ATTACK, DEFENSE, SCHEME, UNIVERSAL
  subType     String?  // для уточнения (например, " Journey")

  // Значения
  attackValue Int?     // для карт атаки
  defenseValue Int?    // для карт защиты
  boostValue  Int?     // для усиления

  // Эффекты карты (JSON для гибкости)
  effects     Json     // [{ timing, type, value, condition, ... }]

  // Дополнительная информация
  text        String?  // описание текста карты
  textEn      String?
  textRu      String?

  // Каким героям принадлежит
  heroId      String
  hero        Hero     @relation(fields: [heroId], references: [id])

  // Количество в колоде героя
  count       Int      @default(1)

  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt

  @@index([heroId])
  @@index([cardType])
}

// ============================================
// BOARDS (для Content Module)
// ============================================

model Board {
  id          String   @id @default(cuid())
  name        String   @unique
  nameEn      String
  nameRu      String
  set         String   // выпуск

  // Размеры доски
  width       Int
  height      Int

  // Ячейки доски
  cells       Json     // [{x, y, type, zone, connections, ...}]

  // Специальные свойства
  features    Json?    // { secretPassages, doors, highGround, ... }

  // Медиа
  imageUrl    String?
  imageUrlDark String?

  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt

  @@index([set])
}

// ============================================
// MATCHMAKING
// ============================================

model MatchmakingQueueEntry {
  id          String   @id @default(cuid())
  userId      String   @unique

  // Критерии поиска
  mode        GameMode
  heroPref    String?  // предпочтительный герой

  // Rating на момент входа
  rating      Int

  // Когда зашёл в очередь (для expanding search window)
  joinedAt    DateTime @default(now())

  @@index([mode, rating])
  @@index([joinedAt])
}

// ============================================
// LEADERBOARDS
// ============================================

model LeaderboardEntry {
  id          String   @id @default(cuid())
  userId      String
  heroId      String?  // null = overall

  // Временной период
  timeFrame   String   @default("all") // all, week, month

  // Метрики
  rank        Int
  elo         Int
  gamesWon    Int
  gamesPlayed Int

  updatedAt   DateTime @updatedAt

  @@unique([userId, heroId, timeFrame])
  @@index([heroId, timeFrame, elo])
}

// ============================================
// PRESENCE (опционально, можно только Redis)
// ============================================

model Presence {
  userId          String   @id
  status          String   @default("offline") // online, away, offline
  lastSeenAt      DateTime @default(now())
  currentGameId   String?

  @@index([status])
}
```

### 3.2 Redis Keys Structure

```
# Game State Cache
game:state:{gameId} -> GameState JSON (TTL: 1 час)
game:lock:{gameId} -> distributed lock (TTL: 10 сек, auto-extend)

# Matchmaking Queue
queue:{mode} -> Redis Sorted Set (score = ELO)
queue:entry:{userId} -> QueueEntry JSON

# Presence (с более длинным TTL для снижения нагрузки)
presence:{userId} -> Presence JSON (TTL: 3 мин, exponential backoff на heartbeat)
presence:online -> Set of userIds

# Rate Limiting (Token Bucket для более плавных лимитов)
ratelimit:{userId}:{action} -> token bucket state

# Redis Streams (вместо Pub/Sub для масштабируемости)
streams:game:{gameId}:state -> GameState updates (MAXLEN ~1000)
streams:game:{gameId}:events -> Game events (MAXLEN ~10000)
streams:match:{userId} -> Matchmaking events
streams:presence -> Online status updates
```

**Примечание по Streams**: Consumer groups позволяют нескольким инстансам читать события без потерь. MAXLEN ограничивает размер для предотвращения переполнения памяти.

---

## 4. Безопасность

### 4.1 Rate Limiting Strategy

**Примечание**: Используется Token Bucket алгоритм вместо Fixed Window для более плавного ограничения.

| Endpoint        | Limit      | Burst | Алгоритм |
|-----------------|------------|-------|----------|
| auth/login      | 5 attempts | 5     | Fixed Window |
| auth/register   | 3 attempts | 3     | Fixed Window |
| game/* (write)  | 60 req/min | 10    | Token Bucket |
| game/subscribe  | 120 req/min | 20   | Token Bucket |
| queries         | 100 req    | 20    | Token Bucket |

**Обоснование**: Game mutations требуют больше 30 req/min (каждый ход = 3-5 действий). Token Bucket позволяет burst активности при сохранении среднего лимита.

### 4.2 Input Validation

```typescript
// Все DTO должны наследовать базовую валидацию
@MinLength(3)
@MaxLength(20)
@Matches(/^[a-zA-Z0-9_]+$/)
username: string

@Min(0)
@Max(100)
x: number
@Min(0)
@Max(100)
y: number
```

### 4.3 Authorization Levels

```typescript
enum Permission {
  // Basic
  READ_OWN_PROFILE,
  UPDATE_OWN_PROFILE,

  // Game
  CREATE_GAME,
  JOIN_GAME,
  PLAY_IN_GAME,      // Проверка: userId in game.players
  TAKE_TURN,         // Проверка: isPlayerTurn(userId, gameState)
  SURRENDER_GAME,    // Проверка: userId in game.players

  // Admin
  BAN_USER,
  MODERATE_GAME,
  VIEW_AUDIT_LOGS,
}

// Дополнительные проверки в GameGuard
class GameGuard {
  canActivate(context: GqlExecutionContext): boolean {
    // 1. Проверка: userId in game.players
    // 2. Для mutations: isPlayerTurn(userId, gameState)
    // 3. Anti-cheat: игрок не делает ход в другой игре одновременно
    // 4. Rate limit per-game: не более X действий за Y секунд
  }
}
```

---

## 5. Error Handling и Recovery

### 5.1 Network Failures During Gameplay

**Проблема**: Игрок может потерять связь во время своего хода

**Стратегия**:

```typescript
// Client-side: exponential backoff для реконнекта
class ReconnectionManager {
  async reconnect(gameId: string, lastSequenceNumber: number) {
    // 1. Подключиться к WebSocket
    // 2. Запросить GameState с sequenceNumber > lastSequenceNumber
    // 3. Применить пропущенные события
    // 4. Если ход игрока ещё активен — продолжить
    // 5. Если ход перешёл к другому игроку — показать состояние
  }
}

// Server-side: timeout на ход
class TurnTimeoutService {
  // Если игрок не сделал ход за 2 минуты → auto-pass
  // Конфигурируемо для дружеских/ранжированных игр
}
```

### 5.2 Reconnection Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Client Disconnect                                │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. Client сохраняет: lastSequenceNumber, currentPhase                 │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. Exponential backoff: 1s → 2s → 4s → 8s → max 30s                   │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. На успешном реконнекте:                                              │
│     GET /games/{id}?since={sequenceNumber}                              │
│     → Возвращает missed events + currentState                           │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. Client применяет events по порядку                                  │
│     → Если sequenceNumber пропущен → полный reload                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Game Abandonment Handling

**Сценарии**:

| Сценарий | Действие | Timeout |
|----------|----------|---------|
| Игрок вышел из браузера | Ожидание реконнекта | 2 мин |
| Игрок explicit disconnect | Auto-surrender опция | немедленно |
| Network failure | Auto-pass после timeout | 2 мин за ход |
| Оба игрока отключены | Игра ставится на паузу | 24 часа → удаление |

**Anti-abuse**: Игроки с частыми abandonments получают рейтинг penalty.

---

## 6. Cheating Prevention

### 6.1 Server-Side Validation

**Все игровые действия валидируются на сервере**:

```typescript
// Client отправляет только intention, не результат
maneuver(gameId, fighterId, cardId, path)  // NOT: maneuver(gameId, result)

// Server проверяет:
// 1. Карта есть в руке игрока
// 2. Fighter принадлежит игроку
// 3. Path валиден (смежность, препятствия)
// 4. Действие доступно в текущей фазе
// 5. У игрока есть actionsRemaining
```

### 6.2 Anti-Cheat Measures

| Мера | Описание |
|------|----------|
| **State validation** | Каждый шаг проверяется GameRulesValidator |
| **Replay verification** | Постфактум проверка корректности игры |
| **Anomaly detection** | Подозрительно быстрые ходы (< 500ms) |
| **Multi-account detection** | IP/fingerprint анализ |
| **Rate limiting per game** | Не более 10 действий за 30 секунд |
| **Audit log** | Все действия записываются для анализа |

### 6.3 Client-Side Protections

```typescript
// Obfuscation (не надёжно, но усложняет реверс-инжиниринг)
// - Minification + mangling
// - Response integrity checks
// - Anti-tamper (devtools detection)
```

---

## 7. Migration Strategy

### 7.1 Content Versioning

**Проблема**: Герои/карты могут меняться

**Решение**:

```typescript
interface ContentVersion {
  version: string;  // "1.2.0"
  releasedAt: Date;
  heroes: HeroDefinition[];
  cards: CardDefinition[];
}

// API для проверки версий
GET /content/version          // Текущая версия
GET /content/diff/{fromVersion}  // Изменения
```

### 7.2 Breaking Changes Handling

| Тип изменения | Стратегия |
|--------------|-----------|
| Добавление героя | Игры до изменения → старый набор |
| Изменение карты героя | Старые игры finish с old version |
| Изменение правил | Версия rules в GameState |

### 7.3 Schema Migrations

```bash
# Prisma migrate с downtime
npx prisma migrate deploy

# Для больших изменений:
# 1. Create new table
# 2. Dual-write
# 3. Backfill data
# 4. Switch reads
# 5. Remove old table
```

---

## 8. Monitoring и Observability

### 8.1 Key Metrics

| Категория | Метрика | Alert |
|-----------|---------|-------|
| Performance | mutation latency p95 | > 500ms |
| Performance | subscription delivery lag | > 1s |
| Reliability | error rate | > 1% |
| Reliability | failed locks per minute | > 10 |
| Business | active games | — |
| Business | games completed today | — |
| Security | failed auth attempts | > 100/min |

### 8.2 Structured Logging

```typescript
// Pino/Winston
logger.info({
  event: 'game_action',
  gameId,
  userId,
  action: 'maneuver',
  duration: 45,
  success: true
});
```

### 8.3 Distributed Tracing

```typescript
// OpenTelemetry
import { trace } from '@opentelemetry/api';

const span = trace.getActiveSpan();
span?.setAttribute('game.id', gameId);
span?.setAttribute('game.phase', phase);
```

---

## 9. Детальный план реализации по фазам

### ФАЗА 0: Подготовка (Infrastructure)

#### Задачи:
- [ ] **0.1** Создать monorepo структуру или отдельный backend репозиторий
- [ ] **0.2** Настроить Docker Compose для локальной разработки:
  - PostgreSQL 15
  - Redis 7
  - Backend (NestJS)
  - (Опционально) PgAdmin, Redis Commander
- [ ] **0.3** Настроить ESLint, Prettier, Husky для backend
- [ ] **0.4** Создать .env.example с описанием всех переменных окружения

**Результат**: Готовая инфраструктура для разработки

---

### ФАЗА 1: Фундамент (Core Infrastructure)

#### Задачи:

##### 1.1 NestJS Project Setup
- [ ] Инициализировать NestJS проект: `nestjs new backend`
- [ ] Настроить tsconfig paths для чистых импортов
- [ ] Установить зависимости:
  ```
  @nestjs/config
  @nestjs/throttler
  @nestjs/passport
  @nestjs/jwt
  passport
  passport-jwt
  bcrypt
  class-validator
  class-transformer
  ```
- [ ] Настроить ConfigModule с validation schema
- [ ] Создать базовые DTO: BaseDto, PaginationDto

**Файлы**:
- `backend/src/config/configuration.ts`
- `backend/src/config/validation.schema.ts`
- `backend/.env.example`

##### 1.2 Prisma + PostgreSQL Setup
- [ ] Установить Prisma: `@prisma/client`, `prisma`
- [ ] Создать начальный schema.prisma (User, UserStats, UserSettings)
- [ ] Настроить PrismaModule в NestJS
- [ ] Создать миграцию: `prisma migrate dev --name init`
- [ ] Создать PrismaService с soft delete middleware

**Файлы**:
- `backend/prisma/schema.prisma`
- `backend/src/database/prisma.service.ts`
- `backend/src/database/prisma.module.ts`

##### 1.3 Redis Setup
- [ ] Установить: `@nestjs/terminus`, `ioredis`
- [ ] Создать RedisModule с health check
- [ ] Создать RedisService с методами:
  - `get`, `set`, `del`, `exists`
  - `setex` (с TTL)
  - `publish`, `subscribe` (для pub/sub)
  - `acquireLock`, `releaseLock` (для distributed locks)

**Файлы**:
- `backend/src/redis/redis.module.ts`
- `backend/src/redis/redis.service.ts`

##### 1.4 GraphQL Apollo Server Setup
- [ ] Установить: `@nestjs/graphql`, `@apollo/server`, `graphql`
- [ ] Настроить GraphQLModule в code-first режиме
- [ ] Настроить Apollo Server с playground
- [ ] Создать базовые скаляры: DateTime, JSON
- [ ] Настроить CORS для GraphQL playground

**Файлы**:
- `backend/src/graphql/graphql.module.ts`
- `backend/src/graphql/scalars/date-time.scalar.ts`
- `backend/src/graphql/scalars/json.scalar.ts`

**Результат**: Работающий GraphQL playground с health checks

---

### ФАЗА 2: Аутентификация и Авторизация

#### Задачи:

##### 2.1 Auth Module - Core
- [ ] Создать AuthModule
- [ ] Создать AuthService с методами:
  - `register(dto: RegisterDto)`
  - `login(dto: LoginDto)`
  - `refreshTokens(refreshToken: string)`
  - `logout(userId: string)`
  - `validateUser(email: string, password: string)`
- [ ] Создать DTO: RegisterDto, LoginDto, AuthResponseDto
- [ ] Настроить bcrypt (10 rounds)

**Файлы**:
- `backend/src/auth/auth.module.ts`
- `backend/src/auth/auth.service.ts`
- `backend/src/auth/dto/*.dto.ts`

##### 2.2 JWT Strategy & Guards
- [ ] Создать JwtStrategy (Passport)
- [ ] Создать RefreshTokenStrategy
- [ ] Создать Guards:
  - `GqlAuthGuard` - для защищённых резолверов
  - `GqlPublicGuard` - для опциональной авторизации
  - `ThrottlerGuard` - для rate limiting
- [ ] Создать декораторы:
  - `@CurrentUser()` - получить текущего пользователя
  - `@Public()` - отметить публичный резолвер

**Файлы**:
- `backend/src/auth/strategies/jwt.strategy.ts`
- `backend/src/auth/strategies/refresh.strategy.ts`
- `backend/src/auth/guards/gql-auth.guard.ts`
- `backend/src/common/decorators/current-user.decorator.ts`
- `backend/src/common/decorators/public.decorator.ts`

##### 2.3 Auth GraphQL API
- [ ] Создать AuthResolver с мутациями:
  - `register(input: RegisterInput!)`
  - `login(input: LoginInput!)`
  - `logout`
  - `refreshTokens(refreshToken: String!)`
- [ ] Создать GraphQL типы:
  - `AuthPayload`
  - `TokensPair`

**Файлы**:
- `backend/src/auth/auth.resolver.ts`

**Результат**: Работающая регистрация, вход, refresh токенов

---

### ФАЗА 3: Пользователи и Профили

#### Задачи:

##### 3.1 Users Module
- [ ] Создать UsersModule
- [ ] Создать UsersService:
  - `findById(id: string)`
  - `findByEmail(email: string)`
  - `updateProfile(userId: string, dto: UpdateProfileDto)`
  - `changePassword(userId: string, dto: ChangePasswordDto)`
  - `deleteAccount(userId: string)`
- [ ] Создать ProfileService:
  - `uploadAvatar(userId: string, file: File)`
  - `updateSettings(userId: string, dto: SettingsDto)`

**Файлы**:
- `backend/src/users/users.module.ts`
- `backend/src/users/users.service.ts`
- `backend/src/users/profile.service.ts`

##### 3.2 User Stats Module
- [ ] Создать UserStatsService:
  - `getStats(userId: string)`
  - `updateStatsAfterGame(gameId: string, userId: string)`
  - `getLeaderboard(options: LeaderboardOptions)`
- [ ] Создать RatingService:
  - `calculateNewRatings(winnerElo, loserElo)` (ELO formula)
  - `getPlayerRating(userId: string, heroId?: string)`

**Файлы**:
- `backend/src/users/user-stats.service.ts`
- `backend/src/users/rating.service.ts`

##### 3.3 Users GraphQL API
- [ ] Создать UsersResolver:
  - Queries: `me`, `user(id: ID!)`, `myStats`
  - Mutations: `updateProfile`, `changePassword`, `deleteAccount`
- [ ] Создать LeaderboardResolver:
  - Query: `leaderboard(hero, timeFrame, limit)`

**Файлы**:
- `backend/src/users/users.resolver.ts`
- `backend/src/users/leaderboard.resolver.ts`

**Результат**: Полностью рабочий users module

---

### ФАЗА 4: Content Module (Статический контент)

#### Задачи:

##### 4.1 Content Module Setup
- [ ] Создать ContentModule
- [ ] Перенести данные героев из фронтенда:
  - Скопировать `src/core/data/heroes/` в `backend/src/content/data/`
  - Создать TypeScript интерфейсы для HeroDefinition
- [ ] Создать ContentService:
  - `getAllHeroes()`
  - `getHeroById(id: string)`
  - `getCardsByHero(heroId: string)`
  - `getAllBoards()`
  - `getCurrentVersion()`

**Файлы**:
- `backend/src/content/content.module.ts`
- `backend/src/content/content.service.ts`
- `backend/src/content/data/heroes/*.ts`
- `backend/src/content/data/boards/*.ts`

##### 4.2 Content GraphQL API
- [ ] Создать ContentResolver:
  - Queries: `heroes`, `hero(id: ID!)`, `boards`, `contentVersion`

**Файлы**:
- `backend/src/content/content.resolver.ts`

##### 4.3 Shared Types Package
- [ ] Создать shared package для типов между фронтендом и бэкендом
- [ ] Вынести общие типы:
  - GameState, PlayerState, FighterState
  - Card, Hero, Board
  - GamePhase, GameStatus

**Вариант А**: Создать `packages/shared/` в monorepo
**Вариант Б**: Создать отдельный npm пакет

**Результат**: Контент доступен через GraphQL

---

### ФАЗА 5: Game Module - Часть 1 (CRUD + State)

#### Задачи:

##### 5.1 Game Module Setup & CRUD
- [ ] Обновить Prisma schema с Game, GamePlayer моделями
- [ ] Создать миграцию
- [ ] Создать GameService:
  - `createGame(dto: CreateGameDto)`
  - `getGame(gameId: string)`
  - `listGames(filters: GameFilters)`
  - `joinGame(gameId: string, heroId: string)`
  - `leaveGame(gameId: string)`
  - `startGame(gameId: string)`

**Файлы**:
- `backend/src/game/game.module.ts`
- `backend/src/game/game.service.ts`
- `backend/src/game/dto/*.dto.ts`

##### 5.2 GameStateService
- [ ] Создать GameStateService:
  - `saveState(gameId: string, state: GameState)`
  - `loadState(gameId: string)`
  - `cacheState(gameId: string, state: GameState)`
  - `getCachedState(gameId: string)`
  - `serialize(state: GameState, forPlayerId: string)`
  - `deserialize(data: SerializedGameState)`
  - `filterPrivateData(state: GameState, playerId: string)`

**Ключевые моменты**:
- Сериализация Map/классов в plain JSON
- Скрытие карт соперника
- Сжатие больших state (опционально)

**Файлы**:
- `backend/src/game/game-state.service.ts`
- `backend/src/game/serializers/*.ts`

##### 5.3 Game GraphQL API - Часть 1
- [ ] Создать GameResolver (первые мутации):
  - Queries: `game(id: ID!)`, `myGames`, `availableGames`
  - Mutations: `createGame`, `joinGame`, `leaveGame`, `startGame`
- [ ] Создать GraphQL типы: Game, GamePlayer

**Файлы**:
- `backend/src/game/game.resolver.ts`
- `backend/src/game/models/*.model.ts`

**Результат**: Можно создавать и присоединяться к играм

---

### ФАЗА 6: Game Module - Часть 2 (Engine + Rules)

#### Задачи:

##### 6.1 Типы для игровых механик
- [ ] Создать enum для типов эффектов карт:
  - `EffectTiming.DURING_COMBAT` - ВО ВРЕМЯ БОЯ
  - `EffectTiming.AFTER_COMBAT` - ПОСЛЕ БОЯ
  - `EffectTiming.IMMEDIATE` - НЕМЕДЛЕННО
  - `EffectTiming.ON_DEFEAT` - при повержении
- [ ] Создать типы для модификаторов значений:
  - `ValueModifierType.SET` - "становится равным"
  - `ValueModifierType.ADD` - "увеличьте/уменьшите"
  - `ValueModifierType.IGNORE` - "игнорируйте"
- [ ] Создать типы для перемещения:
  - `MovementType.MOVE` - соблюдать правила движения
  - `MovementType.PLACE` - телепортация

**Файлы**:
- `backend/src/game/engine/types/effects.ts`
- `backend/src/game/engine/types/modifiers.ts`
- `backend/src/game/engine/types/movement.ts`

##### 6.2 CombatResolver - ключевая система
- [ ] Создать `CombatResolverService` с методом `resolveCombat()`:
  ```
  1. Проверяем смежность/зону (isAdjacent с context)
  2. Защищающийся может сыграть карту защиты
  3. Собираем эффекты ВО ВРЕМЯ БОЯ с обеих карт
  4. Применяем эффекты: атакующий → защищающийся → атакующий...
  5. Применяем способности героев (бонусы к атаке/защите)
  6. Вычисляем итоговые значения (applyValueModifiers)
  7. Определяем победителя (Атака - Защита)
  8. Наносим боевой урон
  9. Применяем эффекты ПОСЛЕ БОЯ (сначала защищающийся!)
  10. Обрабатываем дополнительные атаки
  ```
- [ ] Правило: если два эффекта одновременно - первым защищающийся
- [ ] Проверка: атака = 0 → побеждает защищающийся
- [ ] Обработка доп. атак: цель сохраняется, даже если переместился

**Файлы**:
- `backend/src/game/engine/combat-resolver.service.ts`
- `backend/src/game/engine/combat-state.ts`

##### 6.3 ValueModifierSystem
- [ ] Создать сервис для применения модификаторов:
  - SET ("становится равным") - сбрасывает предыдущие
  - ADD ("увеличьте/уменьшите") - суммируется
  - IGNORE ("игнорируйте") - не учитывается
- [ ] Обработка специальных случаев:
  - "Невидимый противник": значение = 0, эффекты карт не отменяются
  - Способности героев (Артур) работают поверх "игнорирования"

**Файлы**:
- `backend/src/game/engine/value-modifier.service.ts`

##### 6.4 AdjacencySystem - смежность с учётом полей
- [ ] Создать `AdjacencyService`:
  - `isAdjacent(pos1, pos2, context)` - проверка смежности
  - Учесть потайные ходы: смежны только для movement
  - Учесть двери: проверять статус (открыта/закрыта)
  - Учесть возвышенность: проверять бонус к атаке

**Файлы**:
- `backend/src/game/engine/adjacency.service.ts`
- `backend/src/game/engine/board-features/secret-passage.ts`
- `backend/src/game/engine/board-features/door.ts`
- `backend/src/game/engine/board-features/high-ground.ts`

##### 6.5 MovementSystem
- [ ] Создать `MovementService`:
  - Различать MOVE (соблюдать правила) и PLACE (телепорт)
  - Проверять: дистанция 0 включается в "до N"
  - Нельзя двигаться сквозь врагов
  - Жетоны тумана считаются свободными

**Файлы**:
- `backend/src/game/engine/movement.service.ts`

##### 6.6 GameRulesValidator (обновлённый)
- [ ] Создать GameRulesValidator:
  - `validateManeuver()`, `validateMove()`, `validateAttack()`
  - `isAdjacent()` с контекстом (movement/attack/effect)
  - `canPlaceFighter()` - зона героя, жетоны тумана
  - `canPlayCardAsAttack()`, `canPlayCardAsDefense()`
  - `getHighGroundBonus()` - 0 или 1

**Файлы**:
- `backend/src/game/validators/game-rules.validator.ts`
- `backend/src/game/validators/validation-result.ts`

##### 6.7 DistributedLockService
- [ ] Создать DistributedLockService:
  - `acquireGameLock(gameId: string, ttl: number)`
  - `releaseLock(lock: Lock)`
  - `withLock<T>(gameId: string, fn: () => Promise<T>)`

**Файлы**:
- `backend/src/common/services/distributed-lock.service.ts`

**Результат**: Игровая логика соответствует правилам Unmatched

---

### ФАЗА 7: Game Module - Часть 3 (Gameplay Mutations + Subscriptions)

#### Задачи:

##### 7.1 Gameplay Mutations
- [ ] Добавить мутации в GameResolver:
  - `maneuver(gameId, fighterId, cardId, path)` - перемещение + розыгрыш
  - `moveFighter(gameId, fighterId, x, y)` - простое перемещение
  - `attack(gameId, attackerId, cardId, targetId)` - объявление атаки
  - `playDefense(gameId, cardId)` - розыгрыш защиты (в ответ на атаку)
  - `resolveCombat(gameId)` - разрешение боя после защиты
  - `endTurn(gameId)` - конец хода
  - `pass(gameId)` - сброс карты + доп. действие
  - `toggleDoor(gameId, x, y)` - открыть/закрыть дверь
- [ ] Обернуть каждую мутацию в distributed lock
- [ ] Добавить валидацию перед выполнением

**Flow для attack мутации**:
```
1. GqlAuthGuard проверяет токен
2. DistributedLockService.acquireGameLock()
3. GameRulesValidator.validateAttack()
   - Проверка: очередь атакующего?
   - Проверка: смежность (с учётом потайных ходов/дверей)
   - Проверка: карта может быть атакой
4. GameEngineService.attack()
   - Создаём состояние "ожидание защиты"
5. GameStateService.saveState() (DB + Redis)
6. PubSub.publish('attackInitiated', { gameId, attackerId })
7. DistributedLockService.releaseLock()
8. Return состояние (защищающийся видит, что может сыграть защиту)
```

**Flow для playDefense мутации**:
```
1. GqlAuthGuard проверяет токен
2. DistributedLockService.acquireGameLock()
3. GameRulesValidator.validateDefense()
   - Проверка: игрок защищающийся?
   - Проверка: карта может быть защитой?
4. GameEngineService.playDefense()
   - Добавляем карту защиты в состояние боя
5. GameStateService.saveState()
6. PubSub.publish('defensePlayed', { gameId, defenseCard })
7. DistributedLockService.releaseLock()
```

**Flow для resolveCombat мутации**:
```
1. GqlAuthGuard проверяет токен
2. DistributedLockService.acquireGameLock()
3. CombatResolver.resolveCombat()
   - Полный цикл разрешения боя (см. ФАЗУ 6.2)
4. Проверка условий победы/поражения
5. GameStateService.saveState()
6. PubSub.publish('combatResolved', { gameId, result })
7. DistributedLockService.releaseLock()
```

**Файлы**:
- `backend/src/game/game.resolver.ts` (update)

##### 7.2 GraphQL Subscriptions
- [ ] Настроить Redis Pub/Sub для subscriptions
- [ ] Создать subscriptions:
  - `gameStateUpdated(gameId: ID!)` - полное обновление состояния
  - `attackInitiated(gameId: ID!)` - атака объявлена (защищающийся должен ответить)
  - `defensePlayed(gameId: ID!)` - защита сыграна
  - `combatResolved(gameId: ID!)` - бой разрешён
  - `playerJoined(gameId: ID!)`
  - `playerLeft(gameId: ID!)`
  - `turnChanged(gameId: ID!)` - смена хода
- [ ] Добавить sequenceNumber для реконнекта
- [ ] Добавить фильтрацию приватных данных (карты соперника)

**Файлы**:
- `backend/src/game/subscriptions/`
- `backend/src/common/services/pubsub.service.ts`

**Результат**: Полноценный онлайн геймплей с механикой защиты

---

### ФАЗА 8: Matchmaking Module

#### Задачи:

##### 8.1 Queue Manager
- [ ] Создать QueueManagerService:
  - `addToQueue(queueKey: string, userId: string, rating: number)`
  - `removeFromQueue(queueKey: string, userId: string)`
  - `findMatch(queueKey: string, rating: number, delta: number)`
  - `getQueueSize(queueKey: string)`
- [ ] Использовать Redis Sorted Sets

**Файлы**:
- `backend/src/matchmaking/queue-manager.service.ts`

##### 8.2 Matchmaking Service
- [ ] Создать MatchmakingService:
  - `joinQueue(userId: string, criteria: QueueCriteria)`
  - `leaveQueue(userId: string)`
  - `findMatch(criteria: QueueCriteria)`
- [ ] Создать Cron job для поиска матчей (каждую секунду)
- [ ] Реализовать expanding search window:
  - 0-30 сек: ±100 ELO
  - 30-60 сек: ±200 ELO
  - 60-120 сек: ±400 ELO
  - 120+ сек: без ограничений

**Файлы**:
- `backend/src/matchmaking/matchmaking.service.ts`
- `backend/src/matchmaking/matchmaking-scheduler.service.ts`

##### 8.3 Matchmaking GraphQL API
- [ ] Создать MatchmakingResolver:
  - Mutations: `joinQueue`, `leaveQueue`, `acceptMatch`, `declineMatch`
  - Subscriptions: `matchFound`, `queueUpdated`

**Файлы**:
- `backend/src/matchmaking/matchmaking.resolver.ts`

**Результат**: Работающий матчмейкинг

---

### ФАЗА 9: Presence Module

#### Задачи:

##### 9.1 Presence Service
- [ ] Создать PresenceService:
  - `updatePresence(userId: string, status: PresenceStatus)`
  - `getPresence(userId: string)`
  - `getOnlineUserIds()`
  - `isUserOnline(userId: string)`
- [ ] Хранить в Redis (TTL 5 мин)

**Файлы**:
- `backend/src/presence/presence.service.ts`

##### 9.2 Presence Gateway
- [ ] Создать WebSocket Gateway для presence:
  - @SubscribeMessage('heartbeat')
  - @SubscribeMessage('subscribeToUsers')
- [ ] Отправлять presence updates через pub/sub

**Файлы**:
- `backend/src/presence/presence.gateway.ts`

**Результат**: Онлайн-статус работает

---

### ФАЗА 10: History Module (Реплеи + Аудит)

#### Задачи:

##### 10.1 Game Action Recording
- [ ] Обновить GameStateService для записи действий
- [ ] Создать GameActionService:
  - `recordAction(gameId: string, action: GameAction)`
  - `getGameActions(gameId: string)`

**Файлы**:
- `backend/src/history/game-action.service.ts`

##### 10.2 Replay Service
- [ ] Создать ReplayService:
  - `buildReplay(gameId: string)`
  - `getReplay(replayId: string)`
- [ ] Replay строится из последовательности GameAction

**Файлы**:
- `backend/src/history/replay.service.ts`

##### 10.3 Audit Service
- [ ] Создать AuditService:
  - `logAction(userId: string, action: AuditAction, metadata: any)`
  - `getUserAuditLog(userId: string)`
- [ ] Логировать: login, logout, game_abuse, admin_actions

**Файлы**:
- `backend/src/history/audit.service.ts`

**Результат**: Работают реплеи и аудит

---

### ФАЗА 11: Leaderboard Module

#### Задачи:

##### 11.1 Leaderboard Service
- [ ] Создать LeaderboardService:
  - `getLeaderboard(options: LeaderboardOptions)`
  - `refreshLeaderboards()` (cron job)
- [ ] Оптимизировать запросы с materialized views

**Файлы**:
- `backend/src/leaderboard/leaderboard.service.ts`
- `backend/src/leaderboard/leaderboard-scheduler.service.ts`

##### 11.2 Stats Aggregator
- [ ] Создать StatsAggregator:
  - `calculateUserStats(userId: string)`
  - `getHeroStats(heroId: string)`
  - `getTimeFrameStats(timeFrame: string)`

**Файлы**:
- `backend/src/leaderboard/stats-aggregator.service.ts`

**Результат**: Работающая таблица лидеров

---

### ФАЗА 12: Интеграция с Фронтендом

#### Задачи:

##### 12.1 Apollo Client Setup
- [ ] Установить на фронтенд: `@apollo/client`, `graphql`
- [ ] Настроить ApolloClient:
  - HTTP link: http://localhost:3000/graphql
  - WebSocket link: ws://localhost:3000/graphql
  - Auth link для токенов
- [ ] Настроить error handling

**Файлы**:
- `frontend/src/lib/apollo-client.ts`
- `frontend/src/lib/graphql.ts`

##### 12.2 GraphQL Operations
- [ ] Создать GraphQL queries/mutations/subscriptions:
  - Auth: register, login, logout, refreshTokens
  - Game: createGame, joinGame, startGame, maneuver, attack, etc.
  - Matchmaking: joinQueue, leaveQueue
- [ ] Использовать graphql-codegen для типизации

**Файлы**:
- `frontend/src/graphql/queries/*.ts`
- `frontend/src/graphql/mutations/*.ts`
- `frontend/src/graphql/subscriptions/*.ts`

##### 12.3 Enhanced GameStore
- [ ] Обновить gameStore:
  - Добавить `mode: 'offline' | 'online'`
  - Добавить GraphQL операции для online режима
  - Сохранить локальный GameEngine для offline
  - Добавить обработку subscriptions
- [ ] Добавить reconnection logic:
  - При реконнекте запрашивать state с sequenceNumber
  - Применять missed events

**Файлы**:
- `frontend/src/store/gameStore.ts`
- `frontend/src/store/onlineGameStore.ts`

##### 12.4 Auth UI
- [ ] Создать компоненты:
  - LoginForm
  - RegisterForm
  - ProfileSettings
- [ ] Добавить роуты: /login, /register, /profile

**Файлы**:
- `frontend/src/components/auth/LoginForm.tsx`
- `frontend/src/components/auth/RegisterForm.tsx`
- `frontend/src/pages/LoginPage.tsx`

**Результат**: Полностью работающий онлайн режим

---

### ФАЗА 13: Production Readiness

#### Задачи:

##### 13.1 Testing
- [ ] Unit tests для всех сервисов
- [ ] Integration tests для GraphQL API
- [ ] E2E tests для критичных flows

**Файлы**:
- `backend/**/*.spec.ts`

##### 13.2 Logging & Monitoring
- [ ] Настроить structured logging (Winston/Pino)
- [ ] Добавить request tracing
- [ ] Настроить health checks

**Файлы**:
- `backend/src/common/logging/`

##### 13.3 Performance
- [ ] Добавить database indexes
- [ ] Оптимизировать N+1 queries
- [ ] Добавить response caching
- [ ] Load testing

##### 13.4 Security Hardening
- [ ] Security audit
- [ ] Rate limiting tuning
- [ ] Input validation review
- [ ] CORS configuration
- [ ] Helmet.js headers

**Результат**: Production-ready приложение

---

## 10. Приоритизация фаз

| Фаза | Критичность | Зависимости | Время (примерно) | Комментарий |
|------|-------------|-------------|------------------|-------------|
| 0 | Критично | - | 1 день | Infrastructure |
| 1 | Критично | 0 | 2-3 дня | Core setup |
| 2 | Критично | 1 | 2-3 дня | Auth |
| 3 | Высокий | 2 | 2-3 дня | Users |
| 4 | Высокий | 1 | 1-2 дня | Content |
| 5 | Высокий | 2, 3, 4 | 3-4 дня | Game CRUD |
| 6 | Критично | 5 | **10-14 дней** | Game Engine (усложнена) |
| 7 | Критично | 6 | 4-5 дней | Game mutations |
| 8 | Средний | 7 | 2-3 дня | Matchmaking |
| 9 | Низкий | 1 | 1-2 дня | Presence |
| 10 | Низкий | 7 | 2-3 дня | History/Replay |
| 11 | Низкий | 3 | 2-3 дня | Leaderboard |
| 12 | Критично | 7 | 4-5 дня | Frontend integration |
| 13 | Высокий | 12 | 3-5 дней | Production hardening |

**MVP (Minimum Viable Product)**: Фазы 0-7 + 12 ≈ **6-8 недель**
**Полный продукт**: Все фазы ≈ **10-12 недель**

> **Примечание по ФАЗЕ 6**: Усложнена из-за:
> - CombatResolver с полным циклом эффектов (ВО ВРЕМЯ БОЯ / ПОСЛЕ БОЯ)
> - ValueModifierSystem с разными типами модификаторов (SET, ADD, IGNORE)
> - AdjacencySystem с учётом потайных ходов, дверей, возвышенности
> - Правила: эффект защищающегося первым, доп. атаки, условия победы
> - Одновременные эффекты с сортировкой (defender → attacker)

---

## 11. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Сложность боевой системы | Высокая | Высокое | Unit тесты на каждую механику, пошаговая реализация |
| Race conditions в многопользовательской игре | Высокая | Критичное | Distributed locks, тесты под нагрузкой |
| Проблемы с производительностью при 1000+ игр | Средняя | Высокое | Redis кэш, partitioning, load testing заранее |
| Подделка действий на клиенте | Средняя | Высокое | Server-side validation для всех действий |
| Desync состояние между клиентами | Средняя | Высокое | Sequence numbers, replay recovery, тесты реконнекта |
| Exploit в правилах игры | Низкая | Высокое | Peer-review правил, comprehensive test suite |

---

## 12. Критичные файлы для модификации

### Существующие (фронтенд) - для чтения/копирования
- `src/core/models/types.ts` - типы для shared package
- `src/core/engine/GameEngine.ts` - логика для порта (требуется доработка!)
- `src/core/engine/TurnManager.ts` - логика для порта
- `src/core/engine/CombatResolver.ts` - **требует полной переработки** по правилам
- `src/core/engine/MovementSystem.ts` - логика для порта
- `src/store/gameStore.ts` - store для расширения
- `src/core/data/heroes/index.ts` - данные героев

### Новые (бэкенд) - для создания (с учётом правил Unmatched)

**ФАЗА 6 - Критичные файлы для механики боя:**
- `backend/src/game/engine/types/effects.ts` - enum EffectTiming
- `backend/src/game/engine/types/modifiers.ts` - ValueModifierType
- `backend/src/game/engine/combat-resolver.service.ts` - **ключевой файл**
- `backend/src/game/engine/value-modifier.service.ts` - обработка модификаторов
- `backend/src/game/engine/adjacency.service.ts` - смежность с учётом полей
- `backend/src/game/engine/board-features/secret-passage.ts` - потайные ходы
- `backend/src/game/engine/board-features/door.ts` - двери
- `backend/src/game/engine/board-features/high-ground.ts` - возвышенность
- `backend/src/game/engine/movement.service.ts` - MOVE vs PLACE
- `backend/src/game/validators/game-rules.validator.ts` - валидация с правилами

### Новые (фронтенд) - для модификации
- `src/lib/apollo-client.ts` - создать
- `src/graphql/*` - создать
- `src/store/onlineGameStore.ts` - создать или расширить
- `src/components/auth/*` - создать
- `src/components/combat/*` - UI для механизма защиты

