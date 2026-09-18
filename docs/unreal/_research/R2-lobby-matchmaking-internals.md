# R2 — Лобби, комнаты, матчмейкинг, presence и серверные внутренности

Research-справочник для проектирования UE-клиента (Unreal Engine 5.8) к существующему NestJS/GraphQL-бэкенду Unmatched.

- Дата: 2026-09-02, ветка `fix/admin-panel`.
- Первичные источники: `docs/backend-api/03-lobby-matchmaking.md` (далее **D03**) и `docs/backend-api/11-server-internals.md` (далее **D11**). Все утверждения документов сверены с исходниками `backend/src/**` (ссылки вида `файл:строка` — относительно `backend/src/`, если не указано иное) и с сгенерированной клиентской схемой `src/gql/graphql.ts` (далее **GQLGEN**). Расхождения вынесены в раздел 4.
- Что НЕ проверялось в рантайме: бэкенд и Docker-стек в момент исследования не были запущены (`curl localhost:3000/graphql` — пусто, `docker ps` — пусто), поэтому все выводы о поведении сделаны по коду. Пункты, требующие живой проверки, помечены «⚠ runtime».

---

## 1. Краткое резюме

1. **Три пути в игру**: приватная комната (`createGame` → `joinGame`), список открытых игр (`availableGames` → `joinGame`), матчмейкинг (`joinQueue` → подписка `matchFound` → `acceptMatch` обоими → комната в `LOBBY`). Дальше общий лобби-флоу `selectHero` → `toggleReady` → `startGame` (только хост) → `IN_PROGRESS` (D03:29-33).
2. **Статусы** `PENDING → LOBBY → IN_PROGRESS → FINISHED/ABORTED` (+ `PAUSED` объявлен, но нигде не используется) (D11:30-34; `games/dto/create-game.dto.ts:16-23`). ВАЖНО: в коде **ничего не переводит игру в `FINISHED`** — при `GAME_OVER` меняется только `GameState.phase`; `Game.status` остаётся `IN_PROGRESS`, пока кто-то не вызовет `leaveGame`/`abortGame` (→ `ABORTED`). См. §2.3 и §4.
3. **Синхронизация состояния** — подписка `gameStateUpdated(gameId, since)` (ровно одно событие `STATE_UPDATED` на мутацию, приватные данные вырезаны по JWT) + реконнект через `gameSequence` → `eventsSince` (пачки по 100) → `gameState` → повторная подписка с `since` (D11:292-302).
4. **Матчмейкинг**: Redis ZSET по ELO, планировщик BullMQ каждые 5 с, expanding window (±100/±200/±400/∞), пара → игра `PENDING` + подтверждение 30 с (TTL записи 35 с), штрафы за decline (−25 ELO, 3 decline/час → бан 30 мин) (D03:397-430; D11:213-268).
5. **Presence**: heartbeat с TTL 300 с, статусы `OFFLINE/ONLINE/INGAME/INQUEUE` (GraphQL-имена), подписка `presenceUpdated` (D03:461-477; D11:272-284).
6. **Критические находки при сверке с кодом** (подробно в §4):
   - Резолверы матчмейкинга и presence **не имеют `GqlAuthGuard`**, читают `user.userId`, тогда как JWT-стратегия кладёт в `req.user` объект с полем `id`; `MatchmakingGuard` берёт request через `switchToHttp()`, что в GraphQL-контексте не даёт Express-request. По коду весь matchmaking/presence API должен падать на любом запросе (⚠ runtime).
   - Матчмейкинг **не создаёт записи `GamePlayer`**, поэтому после `acceptMatch` обоими `selectHero`/`toggleReady`/`gameState` отвечают «не участвуете», а `startGame` откатывается с «нужно минимум 2 игрока».
   - Подписка `presenceUpdated` возвращает `Promise<void>` вместо AsyncIterator — нерабочая.
   - `@Throttle`-декораторы объявлены, но **`ThrottlerGuard` нигде не зарегистрирован** — rate limits фактически не применяются.
   - Таймаут подтверждения матча **не начисляет штраф** и **не уведомляет** второго игрока; событий `matchTimeout`/`queueUpdated` в GraphQL-схеме нет.
   - Web-клиент и `06-unreal-integration-guide.md` передают в `joinQueue/leaveQueue/leaveAllQueues` аргумент `idempotencyKey`, которого нет в схеме, и `matchFound(userId: ID!)` вместо `String!` — образец нерабочий.

---

## 2. Факты

### 2.1. Транспорт, авторизация, контекст

| Факт | Источник |
|---|---|
| HTTP endpoint `http://localhost:3000/graphql`, WS `ws://localhost:3000/graphql`, протокол `graphql-ws` | D03:5-6; `graphql/graphql.module.ts:19-21`; `main.ts:134` |
| Queries/mutations: заголовок `Authorization: Bearer <accessToken>` | D03:7 |
| Subscriptions: токен в `connectionParams`; принимаются ключи `authorization`, `Authorization` или `token`; если значение не начинается с `Bearer`, префикс добавляется сервером | `graphql/graphql.module.ts:22-32` |
| Контекст WS-соединения формируется как `{ req: { headers: { authorization } }, isSubscription: true }` — `GqlAuthGuard` читает `req.headers.authorization` | `graphql/graphql.module.ts:30-31`; `auth/guards/gql-auth.guard.ts:13-16` |
| `GqlAuthGuard` пропускает без токена только методы/классы с `@Public()` | `auth/guards/gql-auth.guard.ts:18-30` |
| Объект пользователя в `req.user` после JWT-валидации: `{ id, email, username, avatar, role, createdAt, emailVerified }` (кешируется в Redis `user:<sub>` на 300 с; проверяется blacklist токена) | `auth/strategies/jwt.strategy.ts:24-63` |
| `@CurrentUser()` возвращает `GqlExecutionContext.getContext().req.user` | `common/decorators/current-user.decorator.ts:4-9` |
| Глобального guard'а (`APP_GUARD`), middleware и `ThrottlerGuard` в приложении **нет** (grep по `backend/src`: совпадений нет) | `app.module.ts:25-81`; `auth/auth.module.ts:12-31` |
| Ограничения запросов: complexity ≤ 1000, depth ≤ 7 | `graphql/graphql.module.ts:37-58`; D11:150 |
| `ValidationPipe` глобально: `whitelist: true`, `forbidNonWhitelisted: true`, `transform: true` — лишние поля во входных объектах отклоняются | `main.ts:66-75` |
| CORS: allowlist `localhost:5173/5174/5480` + `FRONTEND_URL`; **запросы без `Origin` (нативные клиенты) разрешены** | `main.ts:104-132`, в частности `main.ts:115` |
| Разрешённые заголовки: `Content-Type, Authorization, X-Idempotency-Key, apollo-require-preflight` | `main.ts:126-131` |
| Формат ошибок: в dev — `{message, code, path, locations, extensions}`; в production — бизнес-ошибки (`extensions.code` = `BAD_USER_INPUT`/`GRAPHQL_VALIDATION_FAILED` или текст содержит `not found`/`unauthorized`) отдаются как `{message, code, path}`, остальные маскируются `Internal server error` с `code: INTERNAL_SERVER_ERROR` | `graphql/graphql.module.ts:60-103` |
| Ответ 401 / `extensions.code == "UNAUTHENTICATED"` → `refreshTokens`, затем переподключить WS с новым токеном | `docs/backend-api/02-auth.md:319` |

### 2.2. Enum'ы и GraphQL-типы

**Enum'ы**

| Enum | Значения | Источник |
|---|---|---|
| `GameMode` | `ONE_V_ONE`, `TWO_V_TWO`, `FREE_FOR_ALL`, `VS_AI` | `games/dto/create-game.dto.ts:9-14`; `prisma/schema.prisma:168-173` |
| `GameStatus` | `PENDING`, `LOBBY`, `IN_PROGRESS`, `PAUSED`, `FINISHED`, `ABORTED` | `games/dto/create-game.dto.ts:16-23`; `prisma/schema.prisma:159-166` |
| `GamePhase` (engine) | включает `ACTION_MANEUVER`, `ACTION_ATTACK`, `COMBAT`, `COMBAT_RESOLVE`, `GAME_OVER`, `SETUP` и др.; Prisma-enum `GamePhase` (`SETUP, TURN_START, ACTION_MANEUVER, ACTION_ATTACK, COMBAT, COMBAT_RESOLVE, TURN_END`) **не содержит `GAME_OVER`**, но `GameState.phase` хранится строкой | `games/dto/create-game.dto.ts:5-7`; `prisma/schema.prisma:175-183, 284` |
| `GameEventType` | `ATTACK_INITIATED, DEFENSE_PLAYED, COMBAT_RESOLVED, TURN_CHANGED, PLAYER_JOINED, PLAYER_LEFT, GAME_ENDED, FIGHTER_MOVED, DOOR_TOGGLED, MANEUVER, TURN_ENDED, CARD_PLAYED, GAME_CREATED, GAME_JOINED, GAME_STARTED, GAME_ABORTED, TURN_STARTED, PASSED, CARD_DISCARDED, PLACED, EFFECT_APPLIED, SPECIAL_ABILITY` | `games/dto/gameplay.dto.ts:24-48` |
| `PresenceStatus` | GraphQL-имена `OFFLINE`, `ONLINE`, `INGAME`, `INQUEUE` (внутренние строки `offline/online/ingame/inqueue`) | `presence/models/presence.model.ts:1-6`; `presence/dto/presence.dto.ts:4-7`; GQLGEN:1107-1112 |

**Типы лобби**

```graphql
type GamePlayerResponse { id: String!  userId: String!  username: String!  avatar: String
  heroId: String  isReady: Boolean!  hasPassed: Boolean!  seatOrder: Float! }
type GameResponse { id: String!  code: String  status: GameStatus!  mode: GameMode!
  hostId: String!  host: GamePlayerResponse!  opponentId: String  opponent: GamePlayerResponse
  boardId: String!  boardState: String  createdAt: DateTime!  updatedAt: DateTime!
  startedAt: DateTime  endedAt: DateTime  winnerId: String  version: Float!
  players: [GamePlayerResponse!]!  phase: GamePhase  currentTurn: Int }
type GameStateResponse { id: String!  gameId: String!  state: String!  sequenceNumber: Float!
  currentTurnPlayerId: String  phase: String!  turnCount: Float!  updatedAt: DateTime! }
```
Источник: `games/models/game.model.ts:5-90`, `games/models/game-player.model.ts:3-28`. Примечание: поля, объявленные как TS `number` без `() => Int`, сериализуются как `Float` (`seatOrder`, `version`, `sequenceNumber`, `turnCount`, `gameSequence`, `getOnlineCount`, `ttl`, `lastSeenAt`) — `docs/backend-api/07-graphql-schema-reference.md:553`.

Особенности маппинга `GameResponse` (`games/game.service.ts:939-990`):
- `host.id` и `opponent.id` — это **`User.id`**, а `players[].id` — id записи `GamePlayer` (`game.service.ts:947-948, 978-979`). Для идентификации использовать `userId`.
- `host.isReady`/`host.heroId` берутся из соответствующей записи `players` (иначе `false`/`null`); `hasPassed` у `host`/`opponent` всегда `false` (`game.service.ts:951-954, 963-966`).
- `phase`/`currentTurn` берутся из связанного `GameState` (`null`, пока игра не начата) (`game.service.ts:987-988`).

**Типы подписок игры** (`games/dto/gameplay.dto.ts:380-409, 461-490, 569-580`):

```graphql
type GameEvent { type: GameEventType!  gameId: String!  sequenceNumber: Int!  timestamp: DateTime!  payload: String }
type TurnState { playerId: String!  turnCount: Int!  phase: GamePhase! }
type GameState { gameId: String!  sequenceNumber: Int!  phase: GamePhase!  turnCount: Int!
  currentTurnPlayerId: String!  players: String  fighters: String  handZones: String  boardState: String  metadata: String }
type EventsSinceResponse { gameId: String!  events: [GameEvent!]!  lastSequence: Int!  hasMore: Boolean! }
```

**Типы матчмейкинга** (`matchmaking/dto/*.ts`):

```graphql
input JoinQueueDto { mode: GameMode!  heroPref: String }                 # join-queue.dto.ts:5-15
type QueueStatusResponse { inQueue: Boolean!  mode: String  position: Int  totalPlayers: Int!
  estimatedWaitTime: Int!  joinedAt: DateTime }                          # queue-status-response.dto.ts:3-22
type MatchFoundResponse { gameId: String!  opponentId: String!  opponentUsername: String!
  opponentRating: Int!  mode: String!  expiresAt: DateTime! }            # match-found-response.dto.ts:3-22
type PenaltyInfoDto { canJoinQueue: Boolean!  declineCount: Int!  tempBanUntil: DateTime
  penaltyElo: Int  reason: String }                                      # penalty-info.dto.ts:3-19
```

**Типы presence** (`presence/dto/presence.dto.ts:9-40`, `presence/dto/heartbeat.dto.ts:4-11`):

```graphql
input HeartbeatInput { status: PresenceStatus = ONLINE  currentGameId: String }
type Presence { userId: String!  status: PresenceStatus!  currentGameId: String  lastSeenAt: Float! }  # epoch-ms
type HeartbeatResponse { presence: Presence!  ttl: Float! }
type OnlineUsersResponse { userIds: [String!]!  count: Float! }
```

### 2.3. Жизненный цикл комнаты: статусы и переходы

| Из | В | Триггер | Условия / побочные эффекты | Источник |
|---|---|---|---|---|
| — | `LOBBY` | `createGame` | Хост = `GamePlayer(seatOrder 0)`, генерируется `code` (6 символов из `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, fallback `GM-XXXXXXXX`), `boardId` = переданный либо первая доска по `createdAt asc` либо строка `'default'`; журнал `GAME_CREATED` (seq 0); проверка лимита активных игр | `games/game.service.ts:85-157, 179-203`; D11:38 |
| — | `PENDING` | планировщик матчмейкинга `createMatch` | `hostId = player1` (дольше ждавший), `opponentId = player2`, `boardId` = `board.findFirst()` либо `'default-board'`; **`GamePlayer` не создаются**; Redis-подтверждение + delayed-job таймаута | `matchmaking/services/matchmaking-scheduler.service.ts:192-233, 251-254` |
| `PENDING` | `LOBBY` | `acceptMatch` вторым из двух игроков | `MatchConfirmationService.startGame()` ставит `status: LOBBY`, `startedAt: now` (да, `startedAt` проставляется уже на этом шаге) | `matchmaking/services/match-confirmation.service.ts:180-194, 300-310` |
| `PENDING` | `ABORTED` | `declineMatch`, таймаут подтверждения (30 с), `GameSanityService` для зомби-игр | `cancelGame()` — только `status: ABORTED` (без `endedAt`) | `match-confirmation.service.ts:206-246, 251-285, 315-324`; `matchmaking/services/game-sanity.service.ts:34-88` |
| `LOBBY`/`PENDING` | (без смены статуса) | `joinGame` | Пользователь становится `opponentId` + `GamePlayer(seatOrder 1, heroId?)`; событие `PLAYER_JOINED`; журнал `GAME_JOINED` (seq 0) | `game.service.ts:451-530` |
| `LOBBY` | (без смены) | `selectHero`, `toggleReady` | `selectHero` только в `LOBBY`; `toggleReady` **без проверки статуса**; событий в подписки **не публикуется** | `game.service.ts:825-849, 854-891` |
| `LOBBY` | `IN_PROGRESS` | `startGame` (только хост) | Все `GamePlayer.isReady`; для не-`VS_AI` нужен `opponentId`; `VS_AI` — бот добавляется автоматически (`ai@unmached.local`, сильнейший по `health` герой с картами, `isReady: true`); ставится `startedAt`; `initializeGameState` создаёт `GameState` seq 1 и публикует `STATE_UPDATED`; при ошибке инициализации откат в `LOBBY` (`startedAt: null`) и `BadRequestException`; журнал `GAME_STARTED` (seq 1) | `game.service.ts:639-717, 745-772`; `games/services/game-initialization.service.ts:94-100, 240-260` |
| `IN_PROGRESS` | `ABORTED` | `leaveGame` (любой участник) → `abortGame(reason 'player_left')`; `abortGame` напрямую (хост или opponent) | `status: ABORTED`, `endedAt: now`; журнал `GAME_ABORTED` с текущим seq состояния; лобби-событие `GAME_ENDED` c payload `{reason, abortedBy}` (seq 0) | `game.service.ts:556-560, 777-820` |
| любой | `ABORTED` | `abortGame` | **Проверки статуса нет** — можно прервать игру в `LOBBY`, `PENDING` и даже уже `ABORTED` | `game.service.ts:777-797` |
| `IN_PROGRESS` | остаётся `IN_PROGRESS` | `phase === GAME_OVER` в игровой мутации | Публикуется `GAME_ENDED` (полный state) и журнал `GAME_ENDED` с `winnerId`; **`Game.status`, `Game.winnerId`, `Game.endedAt` не обновляются** (grep `GameStatus.FINISHED` по `backend/src`: только admin `cleanupGames`) | `games/resolvers/game-actions.resolver.ts:200-219`; `admin/admin.service.ts:934, 950` |
| `LOBBY` (хост уходит без opponent) | игра **удаляется** | `leaveGame` | `game.delete` + `gamePlayer.deleteMany`; затем всё равно публикуется `PLAYER_LEFT`; `game(id)` → «Игра не найдена» | `game.service.ts:596-606, 633` |
| `LOBBY` (хост уходит, есть opponent) | (без смены) | `leaveGame` | Opponent становится хостом (`hostId = opponentId`, `opponentId = null`, `seatOrder → 0`); запись старого хоста удаляется | `game.service.ts:563-595` |
| `LOBBY` (opponent уходит) | (без смены) | `leaveGame` | `opponentId = null`, запись `GamePlayer` удалена; событие `PLAYER_LEFT` `{userId}` | `game.service.ts:607-624, 633` |

Дополнительно:
- Лимит активных игр: **5** на пользователя (считаются `PENDING/LOBBY/IN_PROGRESS` как host или opponent) → `MaxActiveGamesException` (наследник `ConflictException`, текст `You have N active games. Maximum allowed: 5`) (`game.service.ts:31, 99-108`; `games/exceptions/game.exceptions.ts:40-45`).
- Идемпотентность `createGame`: поиск по паре `idempotencyKey + hostId` (`game.service.ts:162-173`), но в БД `Game.idempotencyKey` **глобально уникален** (`prisma/schema.prisma:204`) — один и тот же ключ у разных пользователей даст ошибку уникальности.
- Кеш `game:<id>` (TTL 300 с) инвалидируется во всех мутациях комнаты; кеш `myGames` (60 с) инвалидируется на `create/join/leave/start/abort`, но **не** на `toggleReady`/`selectHero` (`game.service.ts:846, 888, 896-934`).
- `code` приглашения хранится в `Game.code` (unique), но **никакой query/mutation не принимает `code`** — `joinGame` требует `gameId` (`games/dto/join-game.dto.ts:4-21`; grep `where: { code` — только генератор кода `game.service.ts:191-192`).
- `JoinGameDto.asOpponent` принимается схемой, но сервисом игнорируется (`game.resolver.ts:141`).

### 2.4. Queries лобби/комнат

Все — `games/game.resolver.ts`.

| Query | Аргументы | Guard | Поведение | Ошибки | Источник |
|---|---|---|---|---|---|
| `game(id: String!): GameResponse` | `id` = Prisma cuid | JWT | `checkGameAccess`: для `FINISHED/ABORTED` — доступно всем; иначе только host/opponent. Кеш `game:<id>` 300 с | `NotFoundException('Игра не найдена')`, `GameAccessDeniedException` (`ConflictException`, `You do not have access to game <id>`) | `game.resolver.ts:28-34`; `game.service.ts:208-290` |
| `myGames(filters: GameFiltersDto): [GameResponse!]!` | `filters { status, mode, limit(1..100), offset }` — сервис использует **только `status` и `limit`** (`mode`, `offset` игнорируются) | JWT | host или opponent; `orderBy updatedAt desc`; `take = limit ?? 50`; кеш `games:list:<userId>:<status|all>` 60 с | — | `game.resolver.ts:39-46`; `game.service.ts:327-385`; `games/dto/game-filters.dto.ts:5-29` |
| `availableGames(mode: String, limit: Float): [GameResponse!]!` | оба опциональны | **нет guard** (полностью публичная) | Только `status: LOBBY` и `opponentId: null` (не `PENDING`, вопреки D03:115); фильтр по `mode`; `orderBy createdAt desc`; `take = limit ?? 20`; кеш `games:available:<mode|all>` 30 с; собственные игры не исключаются | — | `game.resolver.ts:51-57`; `game.service.ts:390-446` |
| `gameState(gameId: String!): GameStateResponse` | | JWT + `requireParticipation` (нужна запись `GamePlayer`) | `loadState` (Redis `gamestate:<id>` 600 с → БД), `filterPrivateData` по JWT, `state` — JSON-строка; `id = "<gameId>-state"`; `updatedAt = metadata.lastActionAt` | `GameAccessDeniedException`; `NotFoundException('Состояние игры <id> не найдено')` если игра не начата | `game.resolver.ts:63-87`; `game.service.ts:295-305`; `games/game-state.service.ts:222-240` |
| `gameSequence(gameId: String!): Float` | | JWT (без проверки участия) | `GameState.sequenceNumber` из БД; **`0`, если состояния нет** | — | `game.resolver.ts:212-216`; `game-state.service.ts:633-640` |
| `eventsSince(gameId: String!, sinceSequence: Float!): EventsSinceResponse` | | JWT + `checkGameAccess` | `GameAction` с `sequenceNumber > since`, `asc`, `take 100`; `lastSequence` = seq последнего события либо `sinceSequence`; `hasMore = events.length >= 100`; `payload` — JSON-строка | как у `game` | `game.resolver.ts:221-238`; `game-state.service.ts:710-733` |
| `heroStances(heroSlug: String!): [StanceOptionDto!]!` | | `@Public` | Статичный справочник `{id, label, isDefault}` из `ABILITY_CONFIGS`; `[]` для героев без стоек | — | `game.resolver.ts:100-109` |

### 2.5. Mutations лобби/комнат

Все — `games/game.resolver.ts` + `games/game.service.ts`. Все с `GqlAuthGuard`.

| Mutation | Аргументы | Объявленный @Throttle | Правила | Ошибки (тексты) | Источник |
|---|---|---|---|---|---|
| `createGame(input: CreateGameDto!, idempotencyKey: String): GameResponse!` | `input { mode?: GameMode = ONE_V_ONE, boardId? }` | 10/мин | См. §2.3; повторный вызов с тем же ключом (тот же хост) возвращает существующую игру | `MaxActiveGamesException` | `game.resolver.ts:115-124`; `game.service.ts:85-157` |
| `joinGame(input: JoinGameDto!): GameResponse!` | `input { gameId!, heroId?, asOpponent? }` | 15/мин | `heroId` валидируется по `Hero.id` (cuid) до сервиса; статус `LOBBY` или `PENDING`; хост не может; если `opponentId` уже есть: тот же пользователь → идемпотентно вернуть игру, иначе ошибка; после успеха — `PLAYER_JOINED {userId, username}` | `'Игра не найдена'`, `'Нельзя присоединиться к игре, которая уже началась или завершилась'`, `'Вы уже являетесь хостом этой игры'`, `'Игра уже заполнена'`, `'Вы уже участвуете в этой игре'`, `'Герой не найден'` | `game.resolver.ts:130-142`; `game.service.ts:310-322, 451-530` |
| `toggleReady(gameId: String!): GameResponse!` | | 20/мин | Требует запись `GamePlayer`; инвертирует `isReady`; **статус не проверяется**; событие не публикуется | `NotFoundException('Вы не участвуете в этой игре')` | `game.resolver.ts:184-192`; `game.service.ts:825-849` |
| `selectHero(gameId: String!, heroId: String!): GameResponse!` | | 10/мин | `validateHeroId`; только `LOBBY`; требует `GamePlayer`; событие не публикуется | `'Герой не найден'`, `'Героя можно выбрать только в лобби'`, `'Вы не участвуете в этой игре'` | `game.resolver.ts:198-207`; `game.service.ts:854-891` |
| `startGame(gameId: String!): GameResponse!` | | 5/мин | См. §2.3 | `'Только хост может начать игру'`, `'Игру можно начать только из лобби'`, `'Для начала игры нужен opponent'`, `'Не все игроки готовы'`, `'Не удалось инициализировать состояние игры: …'`, `'Для инициализации игры нужно минимум 2 игрока'`, `'ИИ-оппонент не сидирован (ai@unmached.local) — запустите prisma/seed-ai.ts'`, `'Нет героев с картами для ИИ-оппонента'` | `game.resolver.ts:162-167`; `game.service.ts:639-772`; `game-initialization.service.ts:99-100` |
| `leaveGame(gameId: String!): Boolean!` | | 10/мин | Всегда возвращает `true`; логика по статусу/роли — §2.3; событие `PLAYER_LEFT {userId}` (без `username`) | `'Игра не найдена'`, `ForbiddenException('Вы не участвуете в этой игре')` | `game.resolver.ts:150-156`; `game.service.ts:539-634` |
| `abortGame(gameId: String!): GameResponse!` | | 5/мин | Хост или opponent; любой статус; `ABORTED` + `endedAt`; событие `GAME_ENDED {reason: 'aborted', abortedBy}` | `'Игра не найдена'`, `ForbiddenException('Вы не можете прервать эту игру')` | `game.resolver.ts:173-178`; `game.service.ts:777-820` |

Игровые мутации (для контекста; детали — в R-документе по game API): `maneuver`, `moveFighter`, `attack`, `playDefense`, `playScheme`, `resolvePendingEffect`, `resolveCombat`, `endTurn`, `pass`, `toggleDoor`, `setStance` — все через `executeMutation` (`games/resolvers/game-actions.resolver.ts:140-246`), возвращают `GameMutationResult { state, sequenceNumber, phase, currentTurnPlayerId, turnCount, timestamp }` (`game-actions.resolver.ts:72-81`), guard'ы `GqlAuthGuard, GameInProgressGuard, GamePlayerGuard, <фазовый>` (`game-actions.resolver.ts:257`). `GamePlayerGuard` отвечает `ForbiddenException('You are not a participant in game <id>')` (`games/guards/game-player.guard.ts:46`), `GameInProgressGuard` — `'Game status is <status>. Required: IN_PROGRESS'` (`games/guards/game-status.guard.ts:97-98`).

### 2.6. Подписки комнаты и игры

Источник: `games/resolvers/game-subscription.resolver.ts`. Все восемь подписок с `@UseGuards(GqlAuthGuard)`; все читают один и тот же топик `game.updates.<gameId>` и различаются фильтром по `eventType`.

| Подписка | Аргументы | Фильтр | Тип ответа / payload | Источник |
|---|---|---|---|---|
| `gameStateUpdated` | `gameId: String!`, `since: Float`, `userId: String` (игнорируется) | `eventType === 'STATE_UPDATED'` и (`since == null` или `sequenceNumber > since`) | `GameState` — `players/fighters/handZones/boardState/metadata` как JSON-строки, отфильтрованные `filterPrivateData` по JWT-пользователю | `game-subscription.resolver.ts:44-65, 156-179` |
| `attackInitiated` | `gameId` | `ATTACK_INITIATED` | `GameEvent`, `payload` = JSON `{phase, turnCount, currentTurnPlayerId}` (рук нет) | `:67-102, 184-199` |
| `defensePlayed` | `gameId` | `DEFENSE_PLAYED` | то же | `:204-219` |
| `combatResolved` | `gameId` | `COMBAT_RESOLVED` | то же | `:224-239` |
| `turnChanged` | `gameId` | `TURN_ENDED` **или** `TURN_CHANGED` (реально публикуется только `TURN_ENDED`) | `TurnState {playerId, turnCount, phase}` | `:104-122, 246-263` |
| `playerJoined` | `gameId` | `PLAYER_JOINED` | `GameEvent`, `sequenceNumber: 0`, `payload` = JSON `{userId, username}` (лобби-payload отдаётся как есть, т.к. у него нет `phase`) | `:84-93, 270-285`; `game.service.ts:524-527` |
| `playerLeft` | `gameId` | `PLAYER_LEFT` | `GameEvent`, seq 0, `payload` = JSON `{userId}` | `:291-304`; `game.service.ts:633` |
| `gameEnded` | `gameId` | `GAME_ENDED` | При `GAME_OVER`: `payload` = `{phase, turnCount, currentTurnPlayerId}`, seq = seq состояния; при `abortGame`: seq 0, `payload` = `{reason, abortedBy}` | `:310-323`; `game-actions.resolver.ts:200-206`; `game.service.ts:817` |

Примечания:
- Комментарии в коде `playerJoined`/`playerLeft` («Known gap: пока никто не публикует», `game-subscription.resolver.ts:265-268, 287-289`) **устарели**: `GameService.publishLobby` публикует оба события (`game.service.ts:46-56, 524-527, 633`). D03:536 и D11:400 это подтверждают.
- Нет событий на `toggleReady`, `selectHero`, `startGame` (как лобби-событий). Единственный сигнал о старте — первое `STATE_UPDATED` (seq 1) из `initializeGameState → saveState` (`game-initialization.service.ts:260`; `game-state.service.ts:215`), который придёт подписчику `gameStateUpdated(gameId)`, если он подписался **до** `startGame`.
- Схема требует `GameState.currentTurnPlayerId: String!` (`gameplay.dto.ts:474-475`) — событие с `null` вызовет ошибку подписки (⚠ runtime, при нормальной инициализации `currentTurnPlayerId = players[0].userId`, `game-initialization.service.ts:243`).
- `@Subscription` должен возвращать AsyncIterator, не rxjs Observable (иначе подписка виснет) — `game-subscription.resolver.ts:10-12`.

### 2.7. Матчмейкинг — серверная логика

**Redis-структуры и TTL** (`matchmaking/services/queue-manager.service.ts:16-20, 60-92`; D11:219-228):

| Ключ | Тип | TTL | Назначение |
|---|---|---|---|
| `mm:queue:<MODE>` | ZSET (score = ELO, member = userId) | **300 с**, обновляется при каждом `addToQueue` в этот режим | сама очередь |
| `mm:queue:data:<userId>` | Hash `{userId, rating, mode, heroPref, joinedAt(ms)}` | 900 с | данные записи; **одна на пользователя** (перезаписывается при входе в другой режим) |
| `mm:confirm:<gameId>` | JSON `MatchConfirmation {gameId, player1Id, player2Id, player1Status, player2Status, expiresAt, createdAt}` | 35 с (`CONFIRMATION_TTL_SECONDS`) | подтверждение матча (`match-confirmation.service.ts:95-124`; `models/match-confirmation.model.ts:15-33`) |
| `mm:penalty:<userId>` | JSON `{userId, declineCount, lastDeclineAt}` | 3900 с (1 ч + 300 с) | счётчик decline (`penalty.service.ts:164-170`) |
| `mm:tempban:<userId>` | JSON `{userId, bannedAt, expiresAt, reason}` | 1800 с | temp ban (`penalty.service.ts:100-117`) |
| Prisma `MatchmakingQueueEntry` (`userId` unique) | — | записи старше 600 с считаются протухшими | резервная копия очереди для восстановления после рестарта Redis (`queue-manager.service.ts:414-473`; `prisma/schema.prisma:533-549`) |

Следствие TTL 300 с на ZSET: если в режим никто не входит 5 минут, **весь ZSET исчезает** вместе с ожидающими игроками; восстановление — только cron `QueueSyncService` раз в 10 минут (записи младше 600 с) (`queue-sync.service.ts:90-111`). Cron также удаляет записи старше 600 с — эффективный максимум ожидания ≈ 10 мин.

**Планировщик** (`matchmaking/services/matchmaking-scheduler.service.ts`; D11:194):
- BullMQ очередь `matchmaking-scheduler`, repeatable job `find-matches` каждые **5000 мс** (`:26, 70-79`), worker `concurrency: 1` (`:93`), лок `matchmaking:scheduler:lock` TTL 15000 мс через `RedisService.acquireLock` (`:24-25, 143`).
- Режимы обрабатываются последовательно: `ONE_V_ONE, TWO_V_TWO, FREE_FOR_ALL, VS_AI` (`:154`); режим пропускается при размере очереди < 2 (`:172-176`); до **20** пар за итерацию (`MATCH_FIND_BATCH_SIZE`, `:27, 179`).
- Алгоритм `findMultipleMatches` (`queue-manager.service.ts:193-244`): записи сортируются по `joinedAt` (дольше ждущий — первый); для каждой считается окно по **её** времени ожидания; партнёром берётся **первый по порядку ожидания** кандидат, попавший в окно (не ближайший по ELO — сортировка по близости есть только в неиспользуемом планировщиком `findMatch`, `:144-184`).
- Expanding window (`matchmaking/models/queue-entry.model.ts:33-55`, сравнение `waitTime <= seconds`):

| Ожидание | Диапазон |
|---|---|
| 0–30 с | ±100 ELO |
| 31–60 с | ±200 ELO |
| 61–120 с | ±400 ELO |
| 121+ с | без ограничений |

- Zombie-записи (есть в ZSET, нет hash) вычищаются при любом чтении очереди (`queue-manager.service.ts:295-330`).
- `createMatch` (`matchmaking-scheduler.service.ts:192-233`): режим игры = первая очередь (в порядке `ONE_V_ONE, TWO_V_TWO, FREE_FOR_ALL, VS_AI`), где найден `player1` (`:238-246`); `game.create({status: PENDING, hostId: player1, opponentId: player2, boardId})`; `createConfirmation`; оба удаляются из очереди; `publishMatchFound(gameId, p1, p2, mode, expiresAt = now + 35 с)`; метрика. Ошибки только логируются (`:230-232`).
- Матчмейкинг для `TWO_V_TWO`/`FREE_FOR_ALL` всё равно создаёт игру на **двух** игроков (модель `Game` знает только `hostId`/`opponentId`).

**Подтверждение** (`matchmaking/services/match-confirmation.service.ts`):
- Создание: Redis-ключ TTL 35 с + delayed job `timeout` (`jobId: timeout:<gameId>`, delay **30 с**, очередь `match-confirmation`, worker `concurrency: 5`) (`:95-124, 55-69`; константы `models/match-confirmation.model.ts:32-33`).
- `acceptMatch(gameId, userId)` (`:129-201`): ключа нет → `{success: false, status: TIMEOUT}`; не участник → `throw new Error('User is not a participant in this match')` (обычный `Error`, не HttpException); повторный accept — идемпотентен; статус не `PENDING` → `{success:false}`; при обоих `ACCEPTED` → `startGame()` (`LOBBY`, `startedAt`), удаление ключа, отмена job. Возвращает `{success, bothAccepted, status}`.
- `declineMatch` (`:206-246`): оба статуса → `DECLINED`, ключ удалён, job отменён, игра → `ABORTED`.
- Таймаут (`handleConfirmationTimeout`, `:251-285`): если ключ ещё есть — вычисляет `timeoutUserId` **только для лога**, удаляет ключ, игра → `ABORTED`. **Штраф не начисляется, событие не публикуется, в очередь никого не возвращают** (`PenaltyService` и `MatchmakingPubSubService` в сервис не инжектируются, `:37-42`).
- Возврат принявшего игрока в очередь «со старым приоритетом» (D03:418) в коде **не найден**: `addToQueue` вызывается только из `joinQueue` и `QueueSyncService` (grep `addToQueue(`: `matchmaking.resolver.ts:64`, `queue-sync.service.ts:66`).

**Штрафы** (`matchmaking/services/penalty.service.ts`; `matchmaking/models/penalty.model.ts:21-26`):

| Параметр | Значение | Источник |
|---|---|---|
| ELO-штраф за decline | 25 (`max(0, elo − 25)`; если `UserStats` нет — пропуск) | `penalty.model.ts:22`; `penalty.service.ts:122-143` |
| Declines до temp ban | 3 в окне 1 ч (окно считается от `lastDeclineAt`) | `penalty.model.ts:23, 25`; `penalty.service.ts:49-64, 148-151` |
| Temp ban | 30 мин; счётчик сбрасывается в 0; при банящем decline ELO-штраф **не** начисляется | `penalty.model.ts:24`; `penalty.service.ts:60-78, 100-117` |
| `recordTimeout(userId)` ≡ `recordDecline` | вызывается **только** из `GameSanityService.forceCancelConfirmation` — для **обоих** игроков | `penalty.service.ts:93-95`; `game-sanity.service.ts:93-122` |
| `canJoinQueue` | `!tempBan || tempBan.expiresAt < now` | `penalty.service.ts:31-43` |
| `penaltyInfo.reason` | `Too many declines. Ban expires at <date>` (только при бане) | `matchmaking.resolver.ts:251-253` |

**Санитарные проверки** (`matchmaking/services/game-sanity.service.ts`):
- Cron каждую минуту: `PENDING` игры с `createdAt` старше 5 мин (до 50) → если подтверждение есть и истекло → `forceCancelConfirmation` (штраф обоим + `ABORTED`); если подтверждения нет → `ABORTED` (`:17, 34-88`).
- `verifyPendingGames` содержит ошибку `gameAge = Date.now() - new Date().getTime()` (всегда ≈ 0) — ветка никогда не срабатывает (`:179-183`).
- `recoverFromCrash` при старте модуля: `verifyPendingGames`, `verifyQueueConsistency` (удаляет из очередей игроков, у которых есть `PENDING` игра), `cleanupZombieGames` (`:367-387`; `matchmaking/matchmaking.module.ts:90-95`).
- `cleanupStuckQueueEntries` (30 мин) по расписанию **не** вызывается — только из `runAllChecks` (`:127-151, 281-292`).

**ELO после игры**: `StatsAggregatorService.updateEloRatings(gameId, winnerId, loserId)` (K = 32, дефолт 1200) существует, но **не вызывается** при `GAME_OVER` (D11:75, 268, 398; `games/services/stats-aggregator.service.ts:18`). Рейтинг для очереди — `UserStats.currentElo ?? 1200` (`matchmaking.resolver.ts:267-279`).

**Presence при матчмейкинге**: сервер **не** меняет presence-статус при `joinQueue`/`matchFound` — статус `INQUEUE`/`INGAME` выставляет только сам клиент через `heartbeat` (grep `updatePresence` вне presence-модуля: не найдено).

### 2.8. Матчмейкинг — API

Источник: `matchmaking/resolvers/matchmaking.resolver.ts`, `matchmaking/resolvers/matchmaking.subscription.ts`, `matchmaking/guards/matchmaking.guard.ts`.

| Операция | Сигнатура (по коду/GQLGEN) | Guard | Лок | Поведение | Ошибки | Источник |
|---|---|---|---|---|---|---|
| `joinQueue(input: JoinQueueDto!): QueueStatusResponse!` | `input { mode: GameMode!, heroPref: String }` — **без `idempotencyKey`** | `MatchmakingGuard` (+ `@Throttle` 5/мин) | `mm:join:<userId>` TTL 5000, без ретраев | Рейтинг из `UserStats`; если уже в **этом** режиме — старая запись удаляется (в других режимах остаётся); ответ `{inQueue: true, mode, position, totalPlayers, estimatedWaitTime, joinedAt: now}` | ошибки guard'а; `'Could not acquire lock'` при параллельном вызове | `matchmaking.resolver.ts:44-86`; GQLGEN:872-874 |
| `leaveQueue(mode: String!): Boolean!` | `mode` — **`String`**, не `GameMode` | `MatchmakingGuard` | `mm:leave:<userId>` 3000 | `true`, если реально удалён из ZSET | ошибки guard'а (в т.ч. **«already in game»**, если есть `PENDING/LOBBY/IN_PROGRESS` игра) | `:91-111`; GQLGEN:882-884 |
| `leaveAllQueues: Boolean!` | | `MatchmakingGuard` | `mm:leaveAll:<userId>` 3000 | `true`, если удалён хотя бы из одного режима | как выше | `:116-130` |
| `acceptMatch(gameId: String!): Boolean!` | | **нет guard** (только проверка temp ban внутри) | `mm:accept:<gameId>:<userId>` 5000 | Возвращает `bothAccepted` (`true` = оба приняли, игра уже `LOBBY`); `false` = ждём второго | `ForbiddenException('You are temporarily banned from matchmaking')`; `NotFoundException('Match confirmation has expired')` (ключа нет); `ForbiddenException('Cannot accept match')` (уже decline/timeout); `Error('User is not a participant in this match')` | `:135-169` |
| `declineMatch(gameId: String!): Boolean!` | | **нет guard** | нет | Проверка статуса → decline → `PenaltyService.recordDecline` (всегда, даже если `result.success === false`) → `true` | `NotFoundException('Match confirmation has expired')`; `ForbiddenException('Cannot decline match')` | `:174-198` |
| `queueStatus(mode: String!): QueueStatusResponse!` | `mode` — `String` | **нет guard** | Не в очереди → `{inQueue: false, mode, totalPlayers, estimatedWaitTime: 0}`; в очереди → `position` (ранг по рейтингу asc, 1-based), `estimatedWaitTime = position * 5` с; **`joinedAt` никогда не заполняется** | — | `:203-228`; `queue-manager.service.ts:259-290` |
| `penaltyInfo: PenaltyInfoDto!` | | **нет guard** | `{canJoinQueue, declineCount, tempBanUntil, penaltyElo (25 или null при бане), reason}` | — | `:242-255` |
| `allQueueStatus: String!`, `metrics: String!` | | нет guard | JSON-строки диагностики | — | `:233-237, 257-262` |
| `matchFound(userId: String!): MatchFoundResponse!` (subscription) | `userId` — `String!` (не `ID!`) | **нет guard** | Фильтр `player1Id === userId || player2Id === userId`; resolve подставляет данные **соперника** (`opponentId/opponentUsername/opponentRating`), `mode`, `expiresAt` | — | `matchmaking.subscription.ts:214-239`; GQLGEN:1529-1531 |

`MatchmakingGuard` (`matchmaking/guards/matchmaking.guard.ts:13-46`): (1) `request = context.switchToHttp().getRequest()`, `user = request.user`, требует `user.userId` → `ForbiddenException('Not authenticated')`; (2) temp ban → `ForbiddenException('You are temporarily banned from matchmaking until <date>')`; (3) активная игра (`PENDING/LOBBY/IN_PROGRESS` как host или opponent) → `ForbiddenException('You are already in game <id>. Finish or leave it first.')`.

Внутренний PubSub матчмейкинга (`matchmaking.subscription.ts:16-87, 117-212`): собственный in-memory класс (без Redis-broadcast — D11:181, 399); события `matchFound`, `matchTimeout {gameId, userId, reason: 'timeout'|'declined'|'cancelled'}`, `queueUpdated {mode, totalPlayers, estimatedWaitTime}`. В GraphQL-схему выведен **только `matchFound`**; `publishMatchTimeout`/`publishQueueUpdated` **нигде не вызываются** (grep: только определения `:178-207`). Итератор хранит **один** непрочитанный payload (`pushValue`, `:42-49`) — при двух событиях подряд без `next()` первое теряется.

### 2.9. Presence

Источник: `presence/presence.resolver.ts`, `presence/presence.service.ts`, `presence/presence-cleanup.service.ts`.

| Операция | Сигнатура | Guard | Поведение | Источник |
|---|---|---|---|---|
| `heartbeat(input: HeartbeatInput!): HeartbeatResponse!` (mutation) | `input` **обязателен** (`{status?: PresenceStatus = ONLINE, currentGameId?}`) | **нет guard**; читает `user.userId` | `presence:<userId>` JSON `{userId, status, currentGameId, lastSeenAt(ms)}` TTL **300 с**; ZADD `presence:online` (score = lastSeenAt); publish в Redis-канал `presence:updates`; ответ `{presence, ttl: 300}` | `presence.resolver.ts:18-35`; `presence.service.ts:5-8, 16-45`; GQLGEN:862-864 |
| `getPresence(userId: String!): Presence` | | нет guard | `null`, если записи нет | `presence.resolver.ts:37-51` |
| `getOnlineUsers: OnlineUsersResponse!` | | нет guard | все member'ы ZSET `presence:online` (ZSET **не** имеет TTL — только cron-очистка) | `:53-61`; `presence.service.ts:59-67` |
| `getOnlineCount: Float!` | | нет guard | `ZCARD presence:online` | `:63-66` |
| `presenceUpdated(userIds: [String!]): Presence!` (subscription) | пустой/отсутствующий список = все | нет guard | Метод возвращает результат `subscribeToPresenceUpdates(...)`, который имеет тип **`Promise<void>`**, а не AsyncIterator — подписка не может доставлять события (см. §4) | `presence.resolver.ts:68-83`; `presence.service.ts:150-165` |

- Имена queries в коде: `getPresence`, `getOnlineUsers`, `getOnlineCount` (D03:467 называет их `onlineUsers`/`onlineCount` — неверно; D11:282 и `07-graphql-schema-reference.md:121-123` — верно).
- Cron каждые 10 мин: `ZRANGEBYSCORE presence:online 0 (now − 5 мин)` → удаление из ZSET и ключей `presence:<userId>` (`presence-cleanup.service.ts:11-19`; `presence.service.ts:113-140`).
- Статусы в D11:281 (`ONLINE / OFFLINE / IN_GAME / AWAY`) **не соответствуют коду**; реальные: `OFFLINE, ONLINE, INGAME, INQUEUE` (`presence.model.ts:1-6`).

### 2.10. sequenceNumber, персистентность, приватность

| Факт | Источник |
|---|---|
| `sequenceNumber` генерирует только сервер: инициализация — 1; каждая мутация +1; auto-resolve — `state.sequenceNumber + 1`; `updateWithLock` — `expected + 1` | D11:141; `game-initialization.service.ts:240`; `combat-timeout.service.ts:264`; `game-state.service.ts:595-608` |
| Хранится в `GameState.sequenceNumber`, дублируется в `Game.version`, и в каждой `GameAction.sequenceNumber` | D11:142; `game-state.service.ts:203-207`; `prisma/schema.prisma:217, 280, 374` |
| `saveState`: Prisma-транзакция с optimistic lock (`existing.sequenceNumber !== state.sequenceNumber − 1` → `ConcurrentModificationException`, `ConflictException` с текстом `Concurrent modification detected. Expected sequence X, got Y. Please refresh and try again.`), upsert, `game.version`, затем кеш Redis `gamestate:<id>` (TTL 600 с), затем публикация `STATE_UPDATED` | `game-state.service.ts:157-158, 170-216`; `games/exceptions/game.exceptions.ts:7-15` |
| `loadState`: сначала Redis, при промахе — БД (`NotFoundException('Состояние игры <id> не найдено')`) + запись в кеш | `game-state.service.ts:222-240` |
| Сериализованный формат `state` (компактные ключи `g/s/p/t/c/pl/f/d/dp/h/b/m`, версия 1) | D11:98-109 |
| `filterPrivateData(state, playerId)`: карты чужой руки → `name: '???'`, значения/эффекты/текст `undefined`, `isVisible: false`; `topCard` чужой колоды скрыт. Применяется в `gameState`, в resolve `gameStateUpdated` и при возврате мутаций; userId всегда из JWT | D11:113; `game-state.service.ts:494`; `game.resolver.ts:75`; `game-subscription.resolver.ts:49-51`; `game-actions.resolver.ts:222` |
| Журнал `GameAction` пишется асинхронно через BullMQ `game-action`/`record-action` (best-effort: ошибка не роняет мутацию); лобби-операции пишут `GAME_CREATED`(seq 0), `GAME_JOINED`(0), `GAME_STARTED`(1), `GAME_ABORTED`(текущий seq) | `games/services/game-action.service.ts:18-49`; `game.service.ts:61-80, 151, 517, 714, 812`; `game-actions.resolver.ts:101-125` |
| `cleanupOldActions(30 дней)` — сервисный метод; автоматического расписания в `games/` не найдено | `game-action.service.ts:131-140`; D11:90 |

### 2.11. PubSub-каналы и двойные события

| Слой | Канал/топик | Назначение | Источник |
|---|---|---|---|
| In-memory `graphql-subscriptions.PubSub` | `game.updates.<gameId>` | доставка в `@Subscription` этого инстанса | `games/game-subscription.service.ts:50, 205-222` |
| Redis Pub/Sub | `game:updates:broadcast` | fan-out между инстансами; событие несёт `instanceId`; своё сообщение отбрасывается | `:53, 76-93, 175` |
| Redis Pub/Sub | `presence:updates` | presence | `presence.service.ts:8, 142-148` |
| In-memory (собственный класс) | `matchFound`, `matchTimeout`, `queueUpdated` | матчмейкинг, **без Redis** | `matchmaking.subscription.ts:89-91, 117-122` |

Форма события: `GameUpdateEvent {gameId, eventType, gameState, sequenceNumber, timestamp, instanceId}` → в PubSub как `GamePubSubEvent {gameId, sequenceNumber, timestamp, eventType, payload}` (`game-subscription.service.ts:11-33, 205-214`).

Поток `publishGameUpdate(gameId, eventType, state)`: `notifyLocalObservers` (legacy rxjs) → `publishToPubSub` → `redis.publish('game:updates:broadcast')` (`:158-176`). `publishLobbyEvent(gameId, eventType, payload)` — то же с `sequenceNumber: 0` и компактным payload (`:182-199`).

**Двойное событие на игровую мутацию**: (1) `STATE_UPDATED` из `saveState`; (2) специфичный `eventType` из `executeMutation` (`MANEUVER`, `FIGHTER_MOVED`, `ATTACK_INITIATED`, `DEFENSE_PLAYED`, `CARD_PLAYED`, `COMBAT_RESOLVED`, `TURN_ENDED`, `DOOR_TOGGLED`, `SPECIAL_ABILITY`, …); при `GAME_OVER` — ещё и `GAME_ENDED` (третье событие) (`game-state.service.ts:215`; `game-actions.resolver.ts:185-189, 200-206`; D11:169-175). Auto-resolve публикует **только** `STATE_UPDATED` (через `saveState`) — специфичного события нет (`combat-timeout.service.ts:233`; D11:193).

Порядок в `executeMutation`: лок `game:<id>` → `loadState` → executor → `saveState` (публикует `STATE_UPDATED`) → планирование/отмена auto-resolve → `publishGameUpdate(eventType)` → журнал → `[GAME_OVER → GAME_ENDED]` → `filterPrivateData` → ответ; после снятия лока — fire-and-forget `AiTurnService.maybeRunAiTurns` (`game-actions.resolver.ts:148-246`).

### 2.12. Распределённые локи

| Лок | Ключ | TTL | Ретраи | Где | Источник |
|---|---|---|---|---|---|
| Игровая мутация | `lock:game:<gameId>` | 10000 мс | 1 × 100 мс | `executeMutation` | `game-actions.resolver.ts:148-149, 235`; `common/services/distributed-lock.service.ts:58, 61, 86-120` |
| Auto-resolve | `lock:game:<gameId>` | 10000 (дефолт) | 0 | `processAutoResolve` | `combat-timeout.service.ts:206` |
| `updateWithLock` | `lock:gamestate:lock:<gameId>` | — | — | `GameStateService` | `game-state.service.ts:595-600` |
| joinQueue / leaveQueue / leaveAllQueues / acceptMatch | `lock:mm:join:<uid>` 5000, `lock:mm:leave:<uid>` 3000, `lock:mm:leaveAll:<uid>` 3000, `lock:mm:accept:<gameId>:<uid>` 5000 | | 0 | резолвер | `matchmaking.resolver.ts:51-52, 97-98, 119-120, 140-141` |
| Планировщик | `matchmaking:scheduler:lock` | 15000 мс | — | `RedisService.acquireLock` (SET NX PX + авто-`DEL` по `setTimeout`, без проверки токена) | `matchmaking-scheduler.service.ts:24-25, 143`; `redis/redis.service.ts:206-229` |

Если лок не взят и ретраи исчерпаны — `Error('Could not acquire lock …')` → для клиента это generic GraphQL-ошибка (D11:126).

### 2.13. BullMQ-очереди, cron и таймеры

| Очередь / джоб | Задержка / расписание | Retry / хранение | Что делает; влияние на клиент | Источник |
|---|---|---|---|---|
| `combat-timeout` / `auto-resolve` (`jobId combat:scheduled:<gameId>`) | delay **30 с** после `attack` (`executeMutation(..., scheduleAutoResolve=true)` передаёт 30 и seq атаки); `DEFAULT_DEFENSE_TIMEOUT = 30`, `DEFAULT_RESOLVE_TIMEOUT = 10` (второй не используется) | attempts 1; removeOnComplete 10 / removeOnFail 50 | Отменяется мутациями с `eventType` `DEFENSE_PLAYED`/`COMBAT_RESOLVED`. При срабатывании: под локом, если `phase !== COMBAT` — skip (`'Not in combat phase'`); если `state.sequenceNumber > attackSequenceNumber` — skip (`'State changed'`); иначе `performAutoResolve`: `phase → COMBAT_RESOLVE`, seq+1, `lastActionAt`, **урон не применяется (TODO)**; `saveState` → `STATE_UPDATED` | `game-actions.resolver.ts:172-182`; `combat-timeout.service.ts:54-69, 90-128, 135-147, 199-282`; `games/processors/combat-timeout.processor.ts:34-64` |
| `getTimeUntilResolve(gameId)` | остаток таймера в мс | | **Не выведен в GraphQL** (grep по `games/resolvers`, `game.resolver.ts`: не найдено); клиент считает 30 с сам от `ATTACK_INITIATED`/`timestamp` либо использует `CombatState.timeoutAt` (если заполняется движком — вне scope R2) | `combat-timeout.service.ts:171-193`; `game-engine/models/game-state.model.ts:84` |
| `matchmaking-scheduler` / `find-matches` | каждые 5000 мс; лок 15 с; worker concurrency 1; до 20 пар | attempts 1; removeOnComplete age 3600 / removeOnFail 7200 | см. §2.7 | `matchmaking-scheduler.service.ts:23-27, 70-95`; `matchmaking.module.ts:32-49` |
| `match-confirmation` / `timeout` (`jobId timeout:<gameId>`) | delay 30 с; Redis-ключ TTL 35 с | attempts 1 | `handleConfirmationTimeout` → `ABORTED` без штрафа и уведомлений; отменяется при accept обоими или decline | `match-confirmation.service.ts:114-124, 191, 231, 251-285, 329-334` |
| `game-action` / `record-action` | — | attempts 3, exponential 1000 мс; removeOnComplete age 3600 / removeOnFail 86400 | журнал `GameAction` → источник `eventsSince` (запись асинхронная — `eventsSince` сразу после мутации может ещё не содержать последнее событие) | `game-action.service.ts:18-49`; `games/games.module.ts:81-96` |
| `audit` / `log-audit-event` | — | attempts 3, exp 1000; completed 7 дней, failed 30 дней | `AuthAuditLog` | D11:197, 355-363 |
| `combat-resolution` / `resolve`, `game-state-persist` / `persist` | — | attempts 3/5 | заготовки (TODO), реальный резолв синхронный | D11:198-199, 396 |
| Дефолт BullMQ приложения | | `removeOnComplete: true, removeOnFail: true` | | `app.module.ts:47-50` |

Cron (`@nestjs/schedule`):

| Сервис | Расписание | Действие | Источник |
|---|---|---|---|
| `PresenceCleanupService` | каждые 10 мин | удалить presence старше 5 мин | `presence-cleanup.service.ts:11-19` |
| `QueueSyncService` | при старте + каждые 10 мин | восстановить очередь из Postgres (записи < 600 с); удалить записи > 600 с | `queue-sync.service.ts:24-27, 33-111` |
| `GameSanityService` | каждую минуту | зомби-`PENDING` старше 5 мин | `game-sanity.service.ts:34-60` |

### 2.14. Rate limits

Объявленные `@Throttle({default: {limit, ttl: 60000}})`:

| Операция | Лимит/мин | Источник |
|---|---|---|
| `createGame` | 10 | `game.resolver.ts:117` |
| `joinGame` | 15 | `:132` |
| `leaveGame` | 10 | `:152` |
| `startGame` | 5 | `:164` |
| `abortGame` | 5 | `:175` |
| `toggleReady` | 20 | `:186` |
| `selectHero` | 10 | `:200` |
| `maneuver`, `moveFighter`, `resolvePendingEffect`, `endTurn`, `toggleDoor`, `setStance` | 30 | `game-actions.resolver.ts:258, 284, 388, 440, 488, 517` |
| `attack`, `playDefense`, `playScheme`, `resolveCombat`, `pass` | 20 | `:311, 338, 364, 414, 465` |
| `joinQueue` | 5 | `matchmaking.resolver.ts:46` |
| `leaveQueue`, `leaveAllQueues`, `acceptMatch`, `declineMatch` | без `@Throttle` | D11:343 |
| Auth: `login` 5, `register` 10, `refresh` 3, `logout` 3, смена пароля 5 | | D11:347 |

**Фактическое применение**: `ThrottlerModule.forRoot([{ttl: 60000, limit: 10}])` подключён (`app.module.ts:54-59`), но `ThrottlerGuard` **не зарегистрирован ни глобально (`APP_GUARD`), ни на резолверах** (grep `ThrottlerGuard|APP_GUARD` по `backend/src`: пусто). Следовательно, лимиты в текущем коде не enforce'ятся; устаревший e2e-тест ожидает код `TOO_MANY_REQUESTS` (`backend/test/matchmaking.api.e2e-spec.ts:184-201`), а D03:530 ссылается на расширение `THROTTLED`, которого в `02-auth.md` нет (grep). ⚠ runtime.

Прочие ограничения: 5 активных игр (§2.3), complexity/depth (§2.1).

### 2.15. Формат ошибок и типовые тексты

- Общий формат: `{ "data": …, "errors": [ { "message", "path", "extensions": { "code" } } ] }` (`02-auth.md:293`); `formatError` — §2.1. В production поле `code` дублируется на верхний уровень объекта ошибки (`graphql/graphql.module.ts:81-85, 89-92`).
- Классы исключений лобби: `ConcurrentModificationException`, `GameAccessDeniedException`, `InvalidGameStatusException`, `MaxActiveGamesException` — все наследники `ConflictException` (HTTP 409) (`games/exceptions/game.exceptions.ts:7-45`).
- Тексты ошибок лобби — на русском (§2.5), матчмейкинга — на английском (§2.8). В production большинство `BadRequestException`-текстов (напр. `'Игра уже заполнена'`) **маскируется** как `Internal server error`, т.к. не подпадает под критерии «бизнес-ошибки» (`graphql.module.ts:73-77`).
- Точное соответствие NestJS-исключений → `extensions.code` (кроме `UNAUTHENTICATED` для 401, `02-auth.md:319`) в источниках не описано — открытый вопрос.

### 2.16. Redis-ключи (сводка)

| Ключ | Тип | TTL | Владелец | Источник |
|---|---|---|---|---|
| `gamestate:<gameId>` | JSON GameState | 600 с | GameStateService | `game-state.service.ts:157-158` |
| `lock:gamestate:lock:<gameId>` | lock | 5000 мс (по D11) | GameStateService.updateWithLock | `game-state.service.ts:600`; D11:374 |
| `lock:game:<gameId>` | lock | 10000 мс | DistributedLockService | `distributed-lock.service.ts:58, 61` |
| `lock:mm:*` | lock | 3000–5000 мс | matchmaking resolver | `matchmaking.resolver.ts` |
| `matchmaking:scheduler:lock` | lock | 15000 мс | scheduler | `matchmaking-scheduler.service.ts:24-25` |
| `game:<gameId>` | JSON GameResponse | 300 с | GameService | `game.service.ts:28-29` |
| `games:list:<userId>:<status|all>` | JSON | 60 с | GameService.myGames | `game.service.ts:331, 382` |
| `games:available:<mode|all>` | JSON | 30 с | GameService.availableGames | `game.service.ts:391, 443` |
| `mm:queue:<MODE>` | ZSET | 300 с | QueueManagerService | `queue-manager.service.ts:16-18` |
| `mm:queue:data:<userId>` | Hash | 900 с | QueueManagerService | `:17, 19` |
| `mm:confirm:<gameId>` | JSON | 35 с | MatchConfirmationService | `match-confirmation.service.ts:24, 111` |
| `mm:penalty:<userId>` | JSON | 3900 с | PenaltyService | `penalty.service.ts:16, 167` |
| `mm:tempban:<userId>` | JSON | 1800 с | PenaltyService | `:17, 112` |
| `presence:<userId>` | JSON | 300 с | PresenceService | `presence.service.ts:5, 7` |
| `presence:online` | ZSET | — (cron) | PresenceService | `:6` |
| `user:<userId>` | JSON user | 300 с | JwtStrategy | `jwt.strategy.ts:33, 60` |
| Каналы: `game:updates:broadcast`, `presence:updates` | Pub/Sub | — | | `game-subscription.service.ts:78`; `presence.service.ts:8` |

### 2.17. Известные пробелы

Из документации (D11:394-400; D03:536-541):
1. Очереди `combat-resolution` и `game-state-persist` — заготовки.
2. Auto-resolve переводит в `COMBAT_RESOLVE` без применения урона.
3. `updateEloRatings` не вызывается при `GAME_OVER`.
4. `matchFound` — только in-memory PubSub (один инстанс).
5. `playerJoined`/`playerLeft` несут компактный payload, не GameState.
6. `acceptMatch` возвращает «оба приняли», а не «принял я»; подтверждение живёт 30–35 с; `heroPref` — только подсказка, герой выбирается `selectHero`.

Найденные при сверке с кодом — см. раздел 4.

---

## 3. Следствия для UE-клиента

**Транспорт и сессия**
1. Два канала: HTTP POST `/graphql` для queries/mutations (заголовок `Authorization: Bearer …`) и WebSocket `graphql-ws` для подписок с `connectionParams: { "authorization": "Bearer <accessToken>" }` (`graphql.module.ts:22-32`). Нативный клиент без `Origin` проходит CORS (`main.ts:115`).
2. При `UNAUTHENTICATED`/401 — `refreshTokens`, затем **переустановить WS-соединение** (токен фиксируется на этапе `connection_init`) (`02-auth.md:319`).
3. Никогда не отправлять во входных объектах поля, которых нет в DTO (`forbidNonWhitelisted`, `main.ts:66-75`): в `JoinQueueDto` — только `mode`, `heroPref`; в `CreateGameDto` — только `mode`, `boardId`; в `HeartbeatInput` — только `status`, `currentGameId`.
4. Все числовые поля-«счётчики» приходят как `Float` (`seatOrder`, `version`, `sequenceNumber`, `turnCount`, `gameSequence`, `lastSeenAt`, `ttl`, `getOnlineCount`); аргументы `since`, `sinceSequence`, `limit` — тоже `Float` (GQLGEN:1213-1216, 1278-1281, 1522-1526). В UE держать их как `double`/`int64` с конверсией.
5. Обрабатывать ошибки по `extensions.code` **и** по верхнеуровневому `code` (production-ветка `formatError`), не полагаться на текст (в production бизнес-тексты маскируются) (`graphql.module.ts:60-103`).
6. Соблюдать объявленные rate limits (§2.14), даже если сейчас они не enforce'ятся — их могут включить.

**Лобби / комната**
7. Приватная комната: `createGame(input, idempotencyKey: <UUID v4>)` → отдать пользователю `game.id` (cuid). Инвайт-код `code` **нельзя обменять на `gameId` через API** — либо передавать сам `gameId` (deep-link), либо ждать появления query по коду (§2.3). `idempotencyKey` должен быть глобально уникальным (UUID), не «время+рандом» (`prisma/schema.prisma:204`).
8. Хост в лобби подписывается на `playerJoined(gameId)` и `playerLeft(gameId)` (payload — JSON `{userId, username}` / `{userId}`), **но** для `isReady`/`heroId` соперника событий нет — нужен поллинг `game(id)` (кеш `game:<id>` инвалидируется на `toggleReady`/`selectHero`, поэтому `game(id)` свежий; `myGames` может отставать до 60 с) (`game.service.ts:846, 888`).
9. Подписку `gameStateUpdated(gameId)` устанавливать **ещё в лобби**, до `startGame` — первое `STATE_UPDATED` (seq 1) и есть сигнал старта для не-хоста; альтернативно поллить `game(id).status`.
10. Пре-просмотр чужой комнаты через `game(id)` невозможен для не-участника (`GameAccessDeniedException`), пока игра не `FINISHED/ABORTED` — для списка использовать только `availableGames` (публичный, без токена, только `LOBBY` без opponent; ограничение по `mode` и `limit`) (`game.service.ts:267-290, 390-446`).
11. `joinGame` идемпотентен для уже присоединившегося opponent; повторный `toggleReady` **инвертирует** флаг (не идемпотентен) — не ретраить вслепую, читать `players[].isReady` из ответа.
12. Для `VS_AI`: `createGame({mode: VS_AI})` → `selectHero` → `toggleReady` → `startGame`; бот добавится сам (нужен сидированный `ai@unmached.local`). Список доступных игр может содержать `VS_AI`-комнаты (фильтровать по `mode`).
13. После `GAME_OVER` (событие `gameEnded` / `phase === GAME_OVER` в `gameStateUpdated`) игра остаётся `IN_PROGRESS` в `Game.status`; чтобы освободить слот (лимит 5 активных, блокировка `MatchmakingGuard`), клиент должен вызвать `leaveGame`/`abortGame` → статус станет `ABORTED` (не `FINISHED`); `Game.winnerId` не заполняется — победителя брать из `GameState.metadata.winnerId`/payload журнала `GAME_ENDED` (`game-actions.resolver.ts:200-219`).
14. `leaveGame` хостом без opponent удаляет игру — последующие запросы по `gameId` дадут «Игра не найдена»; UI должен перейти в главное меню без повторных запросов.
15. `abortGame` доступен из любого статуса и любому из двух участников (`game.service.ts:786-797`) — подтверждать действие в UI.
16. Соперник узнаёт об abort/leave в `IN_PROGRESS` только через `gameEnded(gameId)` (seq 0, payload `{reason, abortedBy}`) — держать эту подписку активной всю игру.

**Синхронизация и реконнект**
17. Хранить `lastSeq` = последний `sequenceNumber` из `STATE_UPDATED`/ответа мутации. При реконнекте: `gameSequence(gameId)` → если больше `lastSeq` → `eventsSince(gameId, lastSeq)` циклом, пока `hasMore` → `gameState(gameId)` (полный снапшот; `state` — JSON-строка) → `gameStateUpdated(gameId, since: lastSeq)` (`game.resolver.ts:212-238`; D11:292-302). Если `events` пуст при gap — брать `gameState` (D11:300).
18. `eventsSince` пишется асинхронно (BullMQ) — сразу после мутации журнал может отставать; для актуального состояния использовать `gameState`/подписку, журнал — только для догоняющих событий/реплея.
19. Ожидать **по одному** `STATE_UPDATED` на мутацию плюс отдельные типизированные события (`attackInitiated` и др.), а при `GAME_OVER` — ещё `gameEnded`; дедуплицировать по `(gameId, sequenceNumber, eventType)`.
20. Каждая мутация отвечает `GameMutationResult` с уже отфильтрованным состоянием — можно применять его сразу (optimistic-free), а пришедший затем `STATE_UPDATED` с тем же seq игнорировать.
21. `ConcurrentModificationException` (409, `Concurrent modification detected…`) → перечитать `gameState` и повторить действие; не ретраить автоматически более одного раза.
22. Таймер защиты: **30 с** от момента `ATTACK_INITIATED` (`timestamp` события/`metadata.lastActionAt`); сервер не отдаёт остаток таймера; по истечении придёт `STATE_UPDATED` с `phase: COMBAT_RESOLVE` без урона — далее нужен `resolveCombat` атакующим (`combat-timeout.service.ts:260-282`; D11:397).
23. Для multi-instance деплоя игровые подписки переживают fan-out через Redis, но `matchFound` — нет (D11:181, 399): клиент матчмейкинга должен держать WS к тому же инстансу, что и HTTP (или использовать один endpoint без балансировки).

**Матчмейкинг**
24. Перед `joinQueue`: `penaltyInfo` (`canJoinQueue`, `tempBanUntil`) и убедиться, что у пользователя **нет** игр в `PENDING/LOBBY/IN_PROGRESS` (`myGames`), иначе `Forbidden 'You are already in game …'` — предлагать `leaveGame`.
25. Установить `matchFound(userId: <мой User.id>)` **до** `joinQueue` — событие публикуется один раз и не повторяется; при потере WS восстанавливать через `myGames({status: PENDING})` (`matchmaking-scheduler.service.ts:219-225`; D03:453).
26. Не передавать `idempotencyKey` в `joinQueue/leaveQueue/leaveAllQueues` и объявлять переменную `matchFound` как `String!` (GQLGEN:872-884, 1529-1531).
27. Поллить `queueStatus(mode)` (например, каждые 5 с); если `inQueue` стал `false` без `matchFound` — очередь протухла (TTL ZSET 300 с / cron 600 с) — показать таймаут и предложить повторный `joinQueue`. Поле `joinedAt` в `queueStatus` всегда `null` — считать время ожидания локально от ответа `joinQueue`.
28. Перед сменой режима вызывать `leaveAllQueues` (hash данных один на пользователя, иначе можно оказаться в двух ZSET).
29. Экран подтверждения: таймер до `expiresAt` (создание + 35 с; job таймаута — 30 с) → `acceptMatch(gameId)`: `false` = ждём соперника, `true` = оба приняли, игра в `LOBBY`; `NOT_FOUND 'Match confirmation has expired'` = таймаут/decline второго — вернуться в очередь вручную. Пока ждём второго — поллить `game(gameId).status` (`LOBBY` — успех, `ABORTED` — отменено), т.к. уведомлений о decline/timeout сервер не шлёт.
30. `declineMatch` → −25 ELO и счётчик; 3 за час → бан 30 мин; **таймаут без ответа штрафа не даёт** — UX-предупреждение об этом должно опираться на реальное поведение (§2.7).
31. После `bothAccepted`: по текущему коду `selectHero`/`toggleReady` для матчмейкинговой игры **упадут** («Вы не участвуете в этой игре»), `startGame` — «нужно минимум 2 игрока» (§4, п. 3). До серверного фикса UE-клиент не может завершить матчмейкинговый флоу; закладывать feature-flag.
32. Матчмейкинг для `TWO_V_TWO`/`FREE_FOR_ALL` создаёт 2-игроковую партию; в UI предлагать только `ONE_V_ONE` (и, возможно, `VS_AI` через `createGame`, а не очередь).

**Presence**
33. Слать `heartbeat(input: {status, currentGameId})` каждые 60–120 с (TTL 300 с); значения enum — `ONLINE`/`INGAME`/`INQUEUE`/`OFFLINE`; `input` обязателен. Сервер сам статус не меняет — клиент должен выставлять `INQUEUE`/`INGAME` при входе в очередь/игру.
34. `presenceUpdated` в текущем коде нерабочая (§4, п. 4) — статус друзей/соперника получать поллингом `getPresence(userId)` / `getOnlineUsers`.
35. По коду `heartbeat` и весь matchmaking-API не имеют auth-guard и читают `user.userId` — до серверного фикса ожидать ошибку на любой вызов (§4, п. 1). Проверить на живом стенде до начала реализации.

---

## 4. Открытые вопросы / несоответствия

1. **Auth в matchmaking/presence-резолверах (критично, ⚠ runtime).** `MatchmakingResolver`, `MatchmakingSubscriptionResolver`, `PresenceResolver` не имеют `@UseGuards(GqlAuthGuard)` (`matchmaking.resolver.ts:44-46, 91-92, 116-117, 135, 174, 203, 242`; `matchmaking.subscription.ts:218-236`; `presence.resolver.ts:18-83`), глобального guard'а нет (`app.module.ts`). `@CurrentUser()` вернёт `undefined`, а резолверы читают `user.userId` (`matchmaking.resolver.ts:51, 57`; `presence.resolver.ts:24`). Даже при наличии guard'а JWT-стратегия кладёт в `req.user` объект с полем `id`, а не `userId` (`jwt.strategy.ts:42-53, 62`; ср. `game.resolver.ts:32` использует `user.id`). `MatchmakingGuard` берёт request через `context.switchToHttp().getRequest()` (`matchmaking.guard.ts:13-14`) — в GraphQL-контексте это не Express-request (см. правильный паттерн в `admin/guards/admin.guard.ts:14-24`). Схема-справочник уже помечает эти операции как «без guard» (`07-graphql-schema-reference.md:112, 114, 192-193, 217`). Вывод: по коду matchmaking и presence API неработоспособны для любого клиента; требуется серверный фикс (guard + `user.id`) и живая проверка.
2. **Rate limits не применяются**: `ThrottlerGuard` не зарегистрирован (§2.14) — D03:518-530 и D11:306-343 описывают декларации, а не поведение.
3. **Матчмейкинг не создаёт `GamePlayer`** (`matchmaking-scheduler.service.ts:204-212`), при этом `toggleReady`/`selectHero`/`requireParticipation`/`GamePlayerGuard`/`initializeGameState` требуют записи (`game.service.ts:295-305, 826-837, 870-881`; `game-initialization.service.ts:94-100`). `joinGame` не помогает: для opponent возвращает игру без создания записи (`game.service.ts:476-480`), для хоста — ошибка (`:471-473`). Флоу D03:33, 494-505 («далее обычный лобби-флоу») в коде не реализуем.
4. **`presenceUpdated` нерабочая**: резолвер возвращает `Promise<void>` от `subscribeToPresenceUpdates` (`presence.resolver.ts:76-83`; `presence.service.ts:150-165`) вместо AsyncIterator (требование — `game-subscription.resolver.ts:10-12`). Кроме того, `RedisService.subscribe` навешивает новый `on('message')` при каждом вызове без снятия (`redis/redis.service.ts:191-199`).
5. **Таймаут подтверждения**: D03:418 («не принявший получает штраф; принявший возвращается в очередь») и D11:257 («определяется не принявший игрок») не соответствуют коду — `handleConfirmationTimeout` ничего не начисляет и не публикует (`match-confirmation.service.ts:251-285`); `matchTimeout`/`queueUpdated` в схеме отсутствуют, `publishMatchTimeout`/`publishQueueUpdated` не вызываются.
6. **Выбор пары**: D03:412 / D11:243 («ближайший по ELO») — планировщик использует `findMultipleMatches`, берущий первого по времени ожидания кандидата в окне (`queue-manager.service.ts:221-236`); ближайший по ELO — только в неиспользуемом `findMatch`.
7. **Статус `FINISHED` недостижим** игровой логикой; `Game.winnerId`/`endedAt` при `GAME_OVER` не пишутся (§2.3). D03:263 показывает `FINISHED` как результат `gameEnded` — не так.
8. **`availableGames`**: D03:115 «LOBBY/PENDING» — код только `LOBBY` (`game.service.ts:398-401`).
9. **`eventsSince(sinceSequence)`**: D03:135, 140 указывает `Int!`, фактически `Float!` (GQLGEN:1278-1281; `game.resolver.ts:225`); `gameSequence` — `Float` (`07-…md:61`).
10. **`queueStatus(mode)`/`leaveQueue(mode)`**: D03:331, 379 и `07-…md:112, 190` указывают `GameMode!`, в коде — `String!` (`matchmaking.resolver.ts:94, 205`; GQLGEN:882-884, 1382-1384). Значения всё равно должны быть строками enum (`ONE_V_ONE` …).
11. **`joinQueue`/`leaveQueue`/`leaveAllQueues` с `idempotencyKey`** в `06-unreal-integration-guide.md:224, 398-405, 421-422` и `src/store/matchmakingStore.ts:6-29` — аргумента нет в схеме (GQLGEN:872-884) → GraphQL validation error. `matchFound(userId: ID!)` там же (`06-…md:443`; `matchmakingStore.ts:57`) против `String!` в схеме. Web-образец для матчмейкинга нерабочий; `backend/test/matchmaking.api.e2e-spec.ts` использует несуществующие режимы `RANKED`/`CASUAL` (`:133, 152`).
12. **Presence-имена/статусы**: D03:467 (`onlineUsers`, `onlineCount`) и D11:281 (`IN_GAME`, `AWAY`) неверны; факт — `getOnlineUsers`, `getOnlineCount`, `OFFLINE/ONLINE/INGAME/INQUEUE`. D03:463 показывает `heartbeat(input: HeartbeatInput)` как опциональный — в схеме `HeartbeatInput!` (GQLGEN:862-864). `lastSeenAt` — `Float` (epoch-ms), не `DateTime` (`presence.dto.ts:20-21`).
13. **`PLAYER_LEFT` payload** — только `{userId}` (`game.service.ts:633`), D03:536 говорит о `{userId, username}` для обоих событий.
14. **`GameSanityService.verifyPendingGames`**: `gameAge` всегда ≈ 0 (`game-sanity.service.ts:179`); `forceCancelConfirmation` штрафует обоих игроков (`:104-110`) — при отказе BullMQ-воркера принявший игрок тоже получит штраф.
15. **Формат `extensions.code`** для NestJS-исключений (400/403/404/409) и код для throttling (`THROTTLED` по D03:530 vs `TOO_MANY_REQUESTS` по e2e) — в источниках не зафиксирован; нужна живая проверка.
16. **Invite-код**: D03:31, 486-488 подразумевают присоединение «по коду», но API принимает только `gameId` (§2.3). Нужна серверная query (напр. `gameByCode`) либо отказ от кода в UE.
17. **`leaveGame` в `PENDING`-игре матчмейкинга** (до accept обоими): статус не `IN_PROGRESS`, поэтому сработает ветка передачи хоста/удаления (`game.service.ts:562-624`), при этом Redis-подтверждение остаётся; поведение `acceptMatch` второго игрока после этого не определено (⚠ runtime).
18. **`gameStateUpdated.currentTurnPlayerId: String!`** — при `null` в состоянии подписка отдаст ошибку вместо события (`gameplay.dto.ts:474-475`; ⚠ runtime).
19. **`abortGame` не отменяет `combat-timeout` job** (`game.service.ts:777-820`); job при срабатывании проверяет только `phase`/seq, не `Game.status` (`combat-timeout.service.ts:206-227`) — возможен `STATE_UPDATED` по уже прерванной игре.
20. **`GameSubscriptionService.notifyLocalObservers`/`subscribeToGame`** — legacy rxjs-путь без использования в резолверах (`game-subscription.service.ts:98-125, 227-240`); безопасно игнорировать.
21. **Не проверено в рантайме** (стенд не был запущен): пп. 1, 2, 15, 17, 18. Рецепт проверки п. 1: `POST /graphql {"query":"{ penaltyInfo { canJoinQueue } }"}` с валидным Bearer — ожидается ошибка `Cannot read properties of undefined (reading 'userId')`.

---

## 5. Источники

Документация (пути от корня репозитория):
- `docs/backend-api/03-lobby-matchmaking.md` (D03) — строки 5-9, 29-41, 46-88, 97-152, 160-264, 270-323, 331-357, 364-389, 397-430, 436-455, 461-477, 483-514, 520-530, 536-541.
- `docs/backend-api/11-server-internals.md` (D11) — строки 30-51, 55-75, 85-113, 121-135, 141-144, 152-181, 187-209, 219-268, 276-284, 292-302, 308-349, 355-365, 371-390, 394-400.
- `docs/backend-api/07-graphql-schema-reference.md` — 58, 61-62, 112, 114, 121-123, 189-193, 217, 246, 252, 426, 495, 517, 540, 553, 601-603.
- `docs/backend-api/02-auth.md` — 20, 293, 319.
- `docs/backend-api/06-unreal-integration-guide.md` — 224, 398-405, 421-422, 443, 449.

Исходники бэкенда (`backend/src/`):
- `main.ts`; `app.module.ts`; `graphql/graphql.module.ts`; `auth/auth.module.ts`; `auth/strategies/jwt.strategy.ts`; `auth/guards/gql-auth.guard.ts`; `common/decorators/current-user.decorator.ts`; `common/common.module.ts`; `common/services/distributed-lock.service.ts`; `redis/redis.service.ts`; `admin/guards/admin.guard.ts`; `admin/admin.service.ts`.
- `games/game.resolver.ts`; `games/game.service.ts`; `games/game-state.service.ts`; `games/game-subscription.service.ts`; `games/games.module.ts`; `games/resolvers/game-subscription.resolver.ts`; `games/resolvers/game-actions.resolver.ts`; `games/services/combat-timeout.service.ts`; `games/services/game-action.service.ts`; `games/services/game-initialization.service.ts`; `games/services/stats-aggregator.service.ts`; `games/processors/combat-timeout.processor.ts`; `games/guards/game-player.guard.ts`; `games/guards/game-status.guard.ts`; `games/dto/create-game.dto.ts`; `games/dto/join-game.dto.ts`; `games/dto/game-filters.dto.ts`; `games/dto/gameplay.dto.ts`; `games/models/game.model.ts`; `games/models/game-player.model.ts`; `games/models/game-action.model.ts`; `games/exceptions/game.exceptions.ts`.
- `matchmaking/matchmaking.module.ts`; `matchmaking/resolvers/matchmaking.resolver.ts`; `matchmaking/resolvers/matchmaking.subscription.ts`; `matchmaking/guards/matchmaking.guard.ts`; `matchmaking/services/match-confirmation.service.ts`; `matchmaking/services/matchmaking-scheduler.service.ts`; `matchmaking/services/queue-manager.service.ts`; `matchmaking/services/penalty.service.ts`; `matchmaking/services/game-sanity.service.ts`; `matchmaking/services/queue-sync.service.ts`; `matchmaking/models/match-confirmation.model.ts`; `matchmaking/models/queue-entry.model.ts`; `matchmaking/models/penalty.model.ts`; `matchmaking/models/user-payload.model.ts`; `matchmaking/dto/join-queue.dto.ts`; `matchmaking/dto/queue-status-response.dto.ts`; `matchmaking/dto/match-found-response.dto.ts`; `matchmaking/dto/penalty-info.dto.ts`.
- `presence/presence.resolver.ts`; `presence/presence.service.ts`; `presence/presence-cleanup.service.ts`; `presence/models/presence.model.ts`; `presence/dto/heartbeat.dto.ts`; `presence/dto/presence.dto.ts`.
- `game-engine/models/game-state.model.ts:84`.
- `backend/prisma/schema.prisma` — 159-183, 185-225, 242-264, 271-291, 368-393, 533-549.
- `backend/test/matchmaking.api.e2e-spec.ts` — 133, 152, 184-201 (устаревший тест).

Клиент-образец (web):
- `src/gql/graphql.ts` (GQLGEN) — 585-589, 862-884, 1098-1112, 1151-1154, 1213-1216, 1278-1281, 1298-1300, 1382-1384, 1522-1531, 1544-1546.
- `src/store/matchmakingStore.ts` — 6-67.
- `src/graphql/queries/{lobby,room,matchmaking,game}.graphql`, `src/graphql/mutations/room.graphql`, `src/graphql/subscriptions/{room,matchmaking,game}.graphql`.
