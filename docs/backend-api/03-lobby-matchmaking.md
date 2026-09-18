# Лобби, комнаты и матчмейкинг

Полная документация API лобби/комнат/матчмейкинга бэкенда (NestJS + GraphQL, Apollo Server, протокол `graphql-ws`).

- **HTTP endpoint:** `http://localhost:3000/graphql`
- **WebSocket endpoint:** `ws://localhost:3000/graphql` (subscriptions)
- **Авторизация:** JWT `Authorization: Bearer <accessToken>` для queries/mutations; для subscriptions — токен в connection params (`{ "authorization": "Bearer <accessToken>" }`). Детали в `docs/backend-api/02-auth.md`.
- Исходники: `backend/src/games/` (резолверы и сервисы лобби/комнат), `backend/src/lobby/` (re-export модуля games), `backend/src/matchmaking/`, `backend/src/presence/`
- Ссылка на клиента-образец (web): `src/store/lobbyStore.ts`, `src/store/matchmakingStore.ts`, `src/graphql/queries/{lobby,room,matchmaking}.graphql`, `src/graphql/mutations/room.graphql`, `src/graphql/subscriptions/{room,matchmaking}.graphql`

---

## 1. Общая архитектура

```
┌──────────────┐   createGame/joinGame/toggleReady    ┌─────────────────┐
│  Лобби/комнаты│ ───────────────────────────────────► │  Game (Prisma)   │
│ (games module)│ ◄───────────── GameResponse ───────── │  PENDING→LOBBY→  │
└──────────────┘                                       │  IN_PROGRESS→…   │
┌──────────────┐   joinQueue → Redis sorted set        └─────────────────┘
│ Матчмейкинг   │ ─► scheduler (5 сек) ► пара по ELO
│ (matchmaking) │ ◄─ matchFound (subscription) + подтверждение 30 сек
└──────────────┘
┌──────────────┐   heartbeat (TTL 300 сек) — статус online/ingame/inqueue
│   Presence   │ ─► presenceUpdated (subscription)
└──────────────┘
```

Три способа попасть в игру:

1. **Приватная комната** — `createGame` → шарь `game.id`/`code` → `joinGame`.
2. **Список открытых игр** — `availableGames` → `joinGame`.
3. **Матчмейкинг** — `joinQueue` → подписка `matchFound` → `acceptMatch` (оба игрока) → игра в статусе `LOBBY` (далее обычный лобби-флоу: `selectHero`, `toggleReady`, `startGame`).

### Enums

```graphql
enum GameMode { ONE_V_ONE  TWO_V_TWO  FREE_FOR_ALL  VS_AI }
enum GameStatus { PENDING  LOBBY  IN_PROGRESS  PAUSED  FINISHED  ABORTED }
enum GamePhase { DRAFT  PLACEMENT  BATTLE  ...  GAME_OVER }  # фазы game-engine
```

### Ключевые типы

```graphql
type GamePlayerResponse {
  id: String!          # id записи GamePlayer
  userId: String!
  username: String!
  avatar: String
  heroId: String       # выбранный герой (null, пока не выбран)
  isReady: Boolean!
  hasPassed: Boolean!
  seatOrder: Int!      # 0 = хост, 1 = opponent
}

type GameResponse {
  id: String!          # Prisma cuid
  code: String         # короткий код приглашения
  status: GameStatus!
  mode: GameMode!
  hostId: String!
  host: GamePlayerResponse!
  opponentId: String
  opponent: GamePlayerResponse
  boardId: String!
  boardState: String
  createdAt: DateTime!
  updatedAt: DateTime!
  startedAt: DateTime
  endedAt: DateTime
  winnerId: String
  version: Int!
  players: [GamePlayerResponse!]!
  phase: GamePhase
  currentTurn: Int
}

type GameStateResponse {
  id: String!            # "<gameId>-state"
  gameId: String!
  state: String!         # JSON-снапшот состояния (приватные данные отфильтрованы по userId)
  sequenceNumber: Int!
  currentTurnPlayerId: String
  phase: String!
  turnCount: Int!
  updatedAt: DateTime!
}
```

---

## 2. Queries (лобби/комнаты)

Все — `backend/src/games/game.resolver.ts`.

### 2.1. `game(id: String!): GameResponse`

Игра по ID. Требует авторизации; `GameService.checkGameAccess` проверяет, что пользователь — участник (для активных игр).

### 2.2. `myGames(filters: GameFiltersDto): [GameResponse!]!`

Игры текущего пользователя (host или opponent). Пример фильтра — статус/режим (см. `backend/src/games/dto/game-filters.dto.ts`).

```graphql
query MyGames {
  myGames {
    id status mode code players { userId username isReady heroId }
  }
}
```

### 2.3. `availableGames(mode: String, limit: Float): [GameResponse!]!`

Список игр в статусе `LOBBY`/`PENDING` без opponent, доступных для присоединения. Публичный (без `@Public`, но без доп. проверок участия).

```graphql
query LobbyAvailableGames($mode: String, $limit: Float) {
  availableGames(mode: $mode, limit: $limit) {
    id mode status
    host { id username avatar }
    boardId createdAt updatedAt
  }
}
```

### 2.4. `gameState(gameId: String!): GameStateResponse`

Полный снапшот состояния игры. Только участники (`requireParticipation`). **Важно для UE:** `state` — JSON-строка; приватные зоны (рука соперника и т.п.) вырезаны сервером по JWT-пользователю, парсить на клиенте безопасно.

### 2.5. `gameSequence(gameId: String!): Int`

Текущий `sequenceNumber` — для optimistic updates и для параметра `since` подписки `gameStateUpdated`.

### 2.6. `eventsSince(gameId: String!, sinceSequence: Int!): EventsSinceResponse`

Догоняющие события после реконнекта (по 100 за запрос, `hasMore: Boolean`):

```graphql
query EventsSince($gameId: String!, $sinceSequence: Int!) {
  eventsSince(gameId: $gameId, sinceSequence: $sinceSequence) {
    gameId
    events { ... }
    lastSequence
    hasMore
  }
}
```

### 2.7. `heroStances(heroSlug: String!): [StanceOptionDto!]!`

Публичный (`@Public`) статичный справочник стоек героя `{id, label, isDefault}` — кэшировать на клиенте, запрашивать один раз.

---

## 3. Mutations (жизненный цикл комнаты)

Источник: `backend/src/games/game.resolver.ts` + `backend/src/games/game.service.ts`.

### 3.1. `createGame(input: CreateGameDto!, idempotencyKey: String): GameResponse!`

Throttle: **10/мин**. Создаёт игру со статусом `LOBBY`, автор = host (`seatOrder: 0`), генерируется `code` приглашения.

```graphql
mutation CreateGame($input: CreateGameDto!, $idempotencyKey: String) {
  createGame(input: $input, idempotencyKey: $idempotencyKey) {
    id code status mode boardId players { userId username isReady }
  }
}
```

`CreateGameDto`:

```graphql
input CreateGameDto { mode: GameMode   boardId: String }   # оба опциональны; mode по умолчанию ONE_V_ONE, boardId — первая доска в БД
```

Особенности:
- **Идемпотентность:** при повторном вызове с тем же `idempotencyKey` возвращается уже созданная игра (защита от двойного клика / ретрая в UE).
- Лимит активных игр на пользователя (`MAX_ACTIVE_GAMES`, см. сервис) — иначе `MaxActiveGamesException`.

### 3.2. `joinGame(input: JoinGameDto!): GameResponse!`

Throttle: **15/мин**.

```graphql
input JoinGameDto {
  gameId: String!      # Prisma cuid
  heroId: String       # опционально — сразу выбрать героя
  asOpponent: Boolean  # опционально
}
```

Правила (`GameService.joinGame`):
- Игра должна быть в `LOBBY`/`PENDING`, иначе `BadRequestException('Нельзя присоединиться…')`.
- Хост не может присоединиться к своей игре; если opponent уже есть (и это не ты) — `'Игра уже заполнена'`.
- Повторный join тем же opponent — идемпотентен (возвращает игру).
- При успехе: пользователь становится opponent (`seatOrder: 1`), публикуется событие лобби `PLAYER_JOINED` (см. подписки), инвалидируется кеш `availableGames`.

### 3.3. `toggleReady(gameId: String!): GameResponse!`

Throttle: **20/мин**. Переключает `isReady` игрока (только участник). Возвращает обновлённую игру.

```graphql
mutation ToggleReady($gameId: String!) {
  toggleReady(gameId: $gameId) { id players { userId isReady } }
}
```

### 3.4. `selectHero(gameId: String!, heroId: String!): GameResponse!`

Throttle: **10/мин**. Выбор героя; только в статусе `LOBBY`; `heroId` валидируется по справочнику героев.

### 3.5. `startGame(gameId: String!): GameResponse!`

Throttle: **5/мин**. **Только хост.** Условия (`GameService.startGame`):
- статус `LOBBY`;
- есть opponent (для `VS_AI` бот добавляется автоматически через `setupAiOpponent`);
- **все** игроки `isReady = true`.

При успехе: `status: IN_PROGRESS`, `startedAt` ставится, инициализируется начальное состояние игры (`GameInitializationService.initializeGameState` — бойцы, колоды, руки). При ошибке инициализации статус откатывается в `LOBBY`.

```graphql
mutation StartGame($gameId: String!) {
  startGame(gameId: $gameId) {
    id status phase players { userId heroId }
  }
}
```

### 3.6. `leaveGame(gameId: String!): Boolean!`

Throttle: **10/мин**. Логика (`GameService.leaveGame`):
- opponent выходит → просто освобождается слот opponent;
- хост выходит и есть opponent → opponent становится новым хостом;
- хост выходит без opponent → игра удаляется;
- выход из начавшейся игры → игра прерывается.

```graphql
mutation LeaveGame($gameId: String!) { leaveGame(gameId: $gameId) }
```

### 3.7. `abortGame(gameId: String!): GameResponse!`

Throttle: **5/мин**. Принудительное прерывание (`ABORTED`).

### 3.8. Игровые мутации (упомянуты для контекста, детали — в doc по game API)

`moveFighter(input: MoveFighterDto!)`, `pass(input: {gameId})` — размещение бойцов/пас в фазе `PLACEMENT`; обе возвращают обновлённый стейт `{ state, sequenceNumber, phase, currentTurnPlayerId, turnCount, timestamp }` и пушат событие `STATE_UPDATED`.

### 3.9. Схема жизненного цикла комнаты

```
createGame ──► LOBBY (host, seatOrder 0)
                 │  joinGame(code/id) ──► opponent (seatOrder 1) ──► [PLAYER_JOINED]
                 │  selectHero (оба, опционально)
                 │  toggleReady (оба → isReady=true)
                 │  startGame (только host, все ready)
                 ▼
             IN_PROGRESS (initializeGameState, phase=DRAFT/PLACEMENT…)
                 │  moveFighter / pass / …
                 ▼
             FINISHED / ABORTED (leaveGame, abortGame, gameEnded)
```

---

## 4. Подписки на события комнаты

Источник: `backend/src/games/resolvers/game-subscription.resolver.ts`. Все требуют `GqlAuthGuard` (токен в connection params WS). Каждая мутация публикует событие с `eventType`; подписки фильтруют по `gameId` + `eventType`.

### 4.1. `gameStateUpdated(gameId: String!, since: Float, userId: String): GameStateGQL`

Главный канал синхронизации состояния. Фильтр: `eventType === 'STATE_UPDATED'` и `sequenceNumber > since` (если передан) — ровно одно срабатывание на мутацию + catch-up при реконнекте. `resolve` фильтрует приватные данные по JWT-пользователю (аргумент `userId` игнорируется).

```graphql
subscription GameStateUpdated($gameId: String!, $since: Float) {
  gameStateUpdated(gameId: $gameId, since: $since) {
    gameId
    sequenceNumber
    phase
    turnCount
    currentTurnPlayerId
    players      # JSON-строка
    fighters     # JSON-строка
    handZones    # JSON-строка
    boardState   # JSON-строка
    metadata     # JSON-строка
  }
}
```

Стратегия для UE: хранить последний `sequenceNumber`; при реконнекте — подписаться с `since = lastSeq`, при пропусках добирать `eventsSince`.

### 4.2. Событийные подписки (`GameEvent`)

Общий payload:

```graphql
type GameEvent {
  type: String!          # eventType, напр. PLAYER_JOINED
  gameId: String!
  sequenceNumber: Int!
  timestamp: DateTime!
  payload: String        # JSON-строка с деталями
}
```

| Подписка | eventType | Когда публикуется |
|---|---|---|
| `playerJoined(gameId)` | `PLAYER_JOINED` | `joinGame` (payload: `{userId, username}`) |
| `playerLeft(gameId)` | `PLAYER_LEFT` | выход игрока |
| `attackInitiated(gameId)` | `ATTACK_INITIATED` | игровая мутация атаки |
| `defensePlayed(gameId)` | `DEFENSE_PLAYED` | игровая мутация защиты |
| `combatResolved(gameId)` | `COMBAT_RESOLVED` | разрешение боя |
| `turnChanged(gameId)` | `TURN_ENDED` / `TURN_CHANGED` | конец хода |
| `gameEnded(gameId)` | `GAME_ENDED` | `phase === GAME_OVER` |

```graphql
subscription PlayerJoined($gameId: String!) {
  playerJoined(gameId: $gameId) { type gameId sequenceNumber timestamp payload }
}
```

---

## 5. Матчмейкинг — Queries

Источник: `backend/src/matchmaking/resolvers/matchmaking.resolver.ts`.

### 5.1. `queueStatus(mode: GameMode!): QueueStatusResponse!`

```graphql
type QueueStatusResponse {
  inQueue: Boolean!
  mode: String
  position: Int            # позиция в очереди (сортировка по rating)
  totalPlayers: Int!
  estimatedWaitTime: Int!  # секунды; эвристика position * 5
  joinedAt: DateTime
}
```

### 5.2. `penaltyInfo: PenaltyInfoDto!`

```graphql
type PenaltyInfoDto {
  canJoinQueue: Boolean!
  declineCount: Int!
  tempBanUntil: DateTime   # если активен temp ban
  penaltyElo: Int          # 25 ELO штрафа за decline
  reason: String
}
```

### 5.3. `allQueueStatus: String!`, `metrics: String!`

Диагностические — JSON-строка со статистикой всех очередей / метриками.

---

## 6. Матчмейкинг — Mutations

`MatchmakingGuard` (для join): JWT обязателен; запрещён при активном temp ban и при наличии активной игры (`PENDING`/`LOBBY`/`IN_PROGRESS`) — «Finish or leave it first». Все операции защищены distributed lock в Redis на пользователя.

### 6.1. `joinQueue(input: JoinQueueDto!): QueueStatusResponse!`

Throttle: **5/мин**. Повторный join — перезаход (старая запись удаляется). Рейтинг берётся из `UserStats.currentElo` (default **1200**).

```graphql
mutation JoinQueue($input: JoinQueueDto!) {
  joinQueue(input: $input) {
    inQueue mode position totalPlayers estimatedWaitTime joinedAt
  }
}
# input JoinQueueDto { mode: GameMode!  heroPref: String }
```

### 6.2. `leaveQueue(mode: GameMode!): Boolean!` / `leaveAllQueues: Boolean!`

Выход из очереди / из всех очередей. `true`, если реально был в очереди.

### 6.3. `acceptMatch(gameId: String!): Boolean!`

Принять найденный матч. Возвращает `bothAccepted` — `true`, когда приняли **оба** (после этого игра переводится в `LOBBY` и готова к обычному лобби-флоу). Ошибки: `NotFoundException('Match confirmation has expired')` (TIMEOUT), `ForbiddenException` (нельзя принять / temp ban).

### 6.4. `declineMatch(gameId: String!): Boolean!`

Отклонить матч. Фиксирует decline в `PenaltyService`. Ошибки аналогичны.

---

## 7. Матчмейкинг — логика сервера

### 7.1. Очередь

- Redis **sorted set** `mm:queue:<MODE>` (score = ELO) + записи `mm:queue:data:<userId>`. TTL: очередь 300 с, данные 900 с, запись 600 с (страховка от «вечно висящих» игроков).
- Режимы: `ONE_V_ONE`, `TWO_V_TWO`, `FREE_FOR_ALL`, `VS_AI` (очереди независимы).

### 7.2. Scheduler (подбор пар)

- BullMQ repeating job каждые **5 секунд** (`SCHEDULER_INTERVAL_MS`), глобальный Redis-lock на тик (один инстанс обрабатывает).
- Алгоритм: все записи сортируются по `joinedAt` (кто дольше ждёт — первый); для каждой расширяющееся ELO-окно (**expanding window**):

| Время в очереди | Диапазон ELO |
|---|---|
| 0–30 с | ±100 |
| 30–60 с | ±200 |
| 60–120 с | ±400 |
| 120+ с | без ограничений |

- Из кандидатов в окне выбирается ближайший по ELO. Пара → создается игра (Prisma `Game`, дефолтная доска) + запись подтверждения в Redis `mm:confirm:<gameId>` (TTL **35 с**) + delayed-job «timeout» через **30 с** (`CONFIRMATION_TIMEOUT_SECONDS`).
- Публикуется событие **`matchFound`** обоим игрокам.

### 7.3. Подтверждение (match confirmation)

- Игрок принимает через `acceptMatch(gameId)`; когда оба приняли → `status: LOBBY`, timeout-job отменяется, матч передан лобби-флоу (`selectHero` → `toggleReady` → `startGame`).
- `declineMatch` или истечение 30 с → игра отменяется; не принявший/отклонивший получает штраф; соперник, который принял, возвращается в приоритете (возвращается в очередь со старым `joinedAt`-приоритетом логикой отмены).
- События внутреннего PubSub: `matchFound`, `matchTimeout` (`reason: timeout | declined | cancelled`), `queueUpdated`.

### 7.4. Штрафы (PenaltyService)

| Параметр | Значение |
|---|---|
| ELO-штраф за decline | 25 |
| Declines до temp ban | 3 |
| Длительность temp ban | 30 минут |
| Окно подсчёта declines | 1 час |

Пока temp ban активен, `MatchmakingGuard` блокирует `joinQueue` и `acceptMatch`.

---

## 8. Матчмейкинг — Subscription

### 8.1. `matchFound(userId: String!): MatchFoundResponse!`

Источник: `backend/src/matchmaking/resolvers/matchmaking.subscription.ts`. Фильтр на сервере: событие приходит только если `userId` — один из двух игроков; payload автоматически «разворачивается» так, что всегда данные **соперника**.

```graphql
subscription MatchFound($userId: String!) {
  matchFound(userId: $userId) {
    gameId            # id созданной игры — принять через acceptMatch(gameId)
    opponentId
    opponentUsername
    opponentRating    # ELO соперника
    mode
    expiresAt         # DateTime, дедлайн подтверждения (создание + 35 с)
  }
}
```

**Важно для UE:** аргумент `userId` обязателен и должен совпадать с JWT-пользователем. Подписку нужно установить **до** `joinQueue` (событие публикуется сразу при создании пары). При получении — показать экран подтверждения с таймером до `expiresAt`, затем `acceptMatch`/`declineMatch`. `matchFound`-событие не повторяется: если соединение оборвалось, состояние можно восстановить запросом `myGames`/`game(id)` (игра уже создана в статусе `PENDING`).

Технически matchmaking-подписки работают через локальный in-memory PubSub (не Redis) — событие доставляется только при соединении с тем же инстансом, что и подписчик; при горизонтальном масштабировании учитывайте (web-клиент подключается к одному endpoint).

---

## 9. Presence (сопутствующий API)

Источник: `backend/src/presence/presence.resolver.ts`. Статусы: `offline | online | ingame | inqueue`.

### 9.1. `heartbeat(input: HeartbeatInput): HeartbeatResponse` (mutation)

Обновляет presence; возвращает `{ presence, ttl: 300 }` — **клиент обязан пульсировать чаще 300 с**, иначе запись протухает (presence-cleanup). `HeartbeatInput: { status: PresenceStatus, currentGameId: String }`.

### 9.2. `getPresence(userId: String!): Presence`, `onlineUsers: OnlineUsersResponse { userIds, count }`, `onlineCount: Int!` (queries)

### 9.3. `presenceUpdated(userIds: [String]): Presence` (subscription)

Фильтр по списку `userIds` (пустой список = все обновления):

```graphql
subscription PresenceUpdated($userIds: [String]) {
  presenceUpdated(userIds: $userIds) { userId status currentGameId lastSeenAt }
}
```

---

## 10. Типовые сценарии для UE-клиента

### 10.1. Приватная комната (по коду)

```
1. createGame(input: {mode: ONE_V_ONE}, idempotencyKey: UUID)  → game.id, game.code
2. Хост: подписка playerJoined(gameId) — ждём opponent
3. Оппонент: availableGames / myGames / код → joinGame(input: {gameId})
4. Оба: selectHero(gameId, heroId) → toggleReady(gameId)
5. Хост: startGame(gameId) → status IN_PROGRESS
6. Оба: подписка gameStateUpdated(gameId) + moveFighter/pass/…
```

### 10.2. Матчмейкинг

```
1. (опционально) penaltyInfo → проверка canJoinQueue
2. Подписка matchFound(userId: <мой id>)
3. joinQueue(input: {mode: ONE_V_ONE, heroPref: "…"})
4. Поллинг queueStatus(mode) — позиция/ETA
5. matchFound payload → экран подтверждения, таймер до expiresAt
6. acceptMatch(gameId) → true когда оба приняли
7. Далее — лобби-флоу: selectHero → toggleReady → startGame (хост)
   (или leaveGame при отказе; declineMatch — штраф)
```

### 10.3. Реконнект

```
1. gameSequence(gameId) / сохранённый lastSeq
2. eventsSince(gameId, sinceSequence: lastSeq) — догнать события
3. gameState(gameId) — свежий снапшот
4. gameStateUpdated(gameId, since: lastSeq) — продолжить поток
```

---

## 11. Rate limits (сводка)

| Операция | Лимит |
|---|---|
| `createGame` | 10/мин |
| `joinGame` | 15/мин |
| `leaveGame` | 10/мин |
| `toggleReady` | 20/мин |
| `selectHero` | 10/мин |
| `startGame` / `abortGame` | 5/мин |
| `joinQueue` | 5/мин |

Ошибки throttle — стандартные GraphQL-ошибки с `THROTTLED`-расширением (см. 02-auth.md).

---

## 12. Известные особенности (важно при интеграции)

1. `playerJoined`/`playerLeft` публикуются лобби-сервисом (`publishLobby`) с payload-JSON `{userId, username}`; event-тип `PLAYER_JOINED`. Подписка не виснет, если событие не публикуется — просто молчит.
2. `gameStateUpdated` отдаёт `players/fighters/handZones/boardState/metadata` как **JSON-строки** — парсить на клиенте.
3. `acceptMatch` возвращает `Boolean` = «оба приняли», а не «принял я». Если `false` — матч ещё ждёт второго.
4. Подтверждение матча живёт 30–35 с; при истечении — `NotFoundException('Match confirmation has expired')`.
5. `MatchmakingGuard` не пускает в очередь при активной игре — перед `joinQueue` завершите/покиньте текущую игру (`leaveGame`).
6. Матчмейкинг после подтверждения создаёт игру в `LOBBY`, но **не** проставляет героя автоматически: `heroPref` из очереди — только подсказка серверу, герой выбирается через `selectHero` в лобби.
