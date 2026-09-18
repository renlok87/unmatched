# Руководство по интеграции Unreal Engine клиента с бэкендом

Практическое руководство для UE-разработчиков по подключению к NestJS GraphQL бэкенду проекта **unmached**. Документ описывает протокольный уровень: endpoints, авторизацию, жизненный цикл сессии и форматы сообщений. C++-реализация не приводится — только GraphQL-операции, JSON-тела HTTP-запросов и WS-сообщения.

---

## 1. Обзор архитектуры

Веб-клиент (React + Phaser) общается с бэкендом через **единый GraphQL endpoint** двумя каналами:

| Канал | Протокол | Назначение |
|---|---|---|
| HTTP POST `/graphql` | HTTP + JSON | Queries и Mutations |
| WebSocket `/graphql` | **graphql-ws** (не legacy `subscriptions-transport-ws`!) | Subscriptions (real-time события игры) |

Бэкенд: NestJS + Apollo Server, `graphql-ws` протокол для подписок (см. `backend/src/graphql/graphql.module.ts`, опция `subscriptions: { 'graphql-ws': true }`).

Веб-клиент использует Apollo Client с split-линком: операции `subscription` идут через WebSocket, всё остальное — через HTTP (`src/lib/apolloClient.ts`). В UE нужно воспроизвести ту же логику.

### Важно про версию WS-протокола

Используется **graphql-ws** (`graphql-ws` npm-пакет, протокол-подпротокол `graphql-transport-ws`), а НЕ старый `subscriptions-transport-ws`. Отличия критичны:

- Handshake: клиент шлёт `connection_init` → сервер отвечает `connection_ack`
- Подписка: клиент шлёт `subscribe` (не `start`)
- Авторизация — через `connection_params` в `connection_init`, а не query-string

Большинство UE GraphQL-плагинов поддерживают только legacy-протокол — это нужно проверять до выбора плагина.

---

## 2. Endpoints

### Базовые URL

```
# HTTP (queries/mutations)
http://localhost:3000/graphql

# WebSocket (subscriptions) — тот же путь!
ws://localhost:3000/graphql
```

Порт и хост бэкенда: `PORT` env-переменная, по умолчанию `3000`. В веб-клиенте адреса задаются через `VITE_API_URL` / `VITE_WS_URL` (см. `src/env.ts`), с дефолтами выше. Для UE-сборки рекомендуется вынести оба URL в конфиг (Project Settings / ini), например:

```
ApiBaseUrl=http://localhost:3000
GraphQLPath=/graphql
```

и собирать `{{ApiBaseUrl}}{{GraphQLPath}}` для обоих каналов.

### Вспомогательные endpoints

| URL | Назначение |
|---|---|
| `GET /health` | Health-check |
| `GET /metrics` | Prometheus-метрики |
| `GET /graphql` (браузер) | GraphQL Playground (dev) |

### CORS

Бэкенд ограничивает CORS origin'ы (`localhost:5173/5174/5480` + `FRONTEND_URL`). **Для UE это не имеет значения**: CORS — механизм браузеров, нативный клиент не шлёт `Origin`-заголовок, а сервер явно разрешает запросы без origin. Никаких настроек на стороне UE не требуется.

### Ограничения сервера (validation rules)

Запросы валидируются на сервере — UE-клиент должен укладываться в лимиты:

- **Complexity limit**: максимум 1000 (запросы сложнее — ошибка `Query is too complex`)
- **Depth limit**: максимум 7 уровней вложенности (игнорируются только `_entities`/`_service`)
- **ValidationPipe**: `whitelist + forbidNonWhitelisted` — лишние поля в input-DTO дают ошибку валидации. Слать нужно строго те поля, что описаны в схеме.

---

## 3. Аутентификация

### Модель

JWT-токены с refresh-механизмом. Пара `accessToken` + `refreshToken` выдаётся при `login`/`register`. Access-токен живёт ~1 час (клиент хранит `expiresAt = now + 60 мин`).

### Передача токена

**HTTP-запросы** — заголовок:

```
Authorization: Bearer <accessToken>
```

**WebSocket** — connection params при `connection_init` (см. раздел 6). Бэкенд принимает поле `authorization` (также `Authorization` или `token`), значение можно передавать как с префиксом `Bearer `, так и без — сервер сам нормализует:

```json
{ "authorization": "Bearer <accessToken>" }
```

### GraphQL-операции авторизации

```graphql
mutation Login($input: LoginDto!) {
  login(input: $input) {
    accessToken
    refreshToken
    user { id email username }
  }
}

mutation Register($input: RegisterDto!) {
  register(input: $input) {
    accessToken
    refreshToken
    user { id email username }
  }
}

mutation RefreshTokens($refreshToken: String!) {
  refreshTokens(refreshToken: $refreshToken) {
    accessToken
    refreshToken
  }
}

mutation Logout {
  logout
}

query Me {
  me {
    id
    email
    username
    avatar
    createdAt
    settings { theme soundEnabled musicEnabled language profileVisible }
  }
}
```

### Refresh-цикл (обязателен к реализации в UE)

Веб-клиент делает это автоматически (`src/lib/error-link.ts`). Алгоритм:

1. Любой запрос вернул ошибку с `extensions.code == UNAUTHENTICATED` / `AUTH_TOKEN_EXPIRED` / `AUTH_INVALID_TOKEN` (или HTTP 401, или сообщение содержащее `token expired` / `invalid token`)
2. Вызвать `refreshTokens(refreshToken: ...)` с сохранённым refresh-токеном
3. Сохранить новую пару токенов, **повторить исходный запрос** с новым access-токеном
4. Если refresh не удался или refresh-токена нет — logout (в UI — возврат на экран логина)

Для WebSocket после refresh нужно пересоздать соединение (клиент вызывает `wsClient.terminate()` — graphql-ws переподключается и снова вызывает `connection_init` с уже обновлённым токеном из хранилища). В UE: закрыть сокет и переподключиться.

Хранить токены в UE можно в файле сохранения / `USaveGame` — эквивалент localStorage веб-клиента (ключи веб-версии: `unmached_access_token`, `unmached_refresh_token`, `unmached_token_expiry`).

---

## 4. Подходы к реализации в UE

### Вариант A: GraphQL-плагин для UE

Кандидаты (проверить актуальность и поддержку graphql-ws перед выбором):

- **UE GraphQL** (badumbat/UEGraphQL и форки) — HTTP-запросы; подписки обычно нужно дописывать
- **Graphql Client Plugin for Unreal Engine** (Mountea framework) — претензия на полный клиент
- Коммерческие решения с codegen из схемы

Требования к плагину от нашего бэкенда:

1. Поддержка кастомного заголовка `Authorization` на каждый запрос
2. Поддержка протокола **graphql-ws** (`connection_init`/`connection_ack`/`subscribe`) — большинство плагинов из коробки умеют только HTTP
3. Возможность передать `connectionParams` при WS-handshake

Если плагин не поддерживает graphql-ws — подписки реализуются вручную (вариант B), а плагин используется только для queries/mutations.

### Вариант B: Plain HTTP + WebSocket (рекомендуется как минимум для старта)

GraphQL over HTTP — это просто POST JSON. Подписки — текстовые JSON-сообщения по WebSocket. Никакого exotic-протокола нет, в UE это `FHttpModule` / `IWebSocket` из `WebSockets`-модуля. Все примеры ниже — в этом варианте.

---

## 5. HTTP: формат запросов

Все queries и mutations — POST на `http://<host>:3000/graphql`:

```
POST /graphql HTTP/1.1
Content-Type: application/json
Authorization: Bearer <accessToken>
```

Тело:

```json
{
  "query": "query GetGame($id: String!) { game(id: $id) { id mode status phase players { userId username heroId isReady } } }",
  "variables": { "id": "abc-123" },
  "operationName": "GetGame"
}
```

- `query` — строка GraphQL-операции (можно с `\n`, сервер парсит)
- `variables` — JSON-объект значений для переменных
- `operationName` — обязателен, если в `query` несколько операций

Ответ (успех):

```json
{
  "data": {
    "game": {
      "id": "abc-123",
      "mode": "ONE_V_ONE",
      "status": "IN_PROGRESS",
      "phase": "MAIN",
      "players": [
        { "userId": "u1", "username": "Alice", "heroId": "deadpool", "isReady": true }
      ]
    }
  }
}
```

Ответ (ошибка): см. раздел 8. Статус-код может быть 200 даже при GraphQL-ошибках — **всегда смотреть поле `errors` в теле**.

### Идемпотентность

Некоторые мутации защищены от дублей и ожидают идемпототентности:

- `joinQueue` / `leaveQueue` / `leaveAllQueues` — принимают `idempotencyKey` как **GraphQL-переменную**
- `toggleReady`, `selectHero` — веб-клиент шлёт HTTP-заголовок **`X-Idempotency-Key`** (генерируется как `${timestamp}-${random}`)

В UE: генерировать GUID/строку на каждую операцию и передавать тем же способом.

---

## 6. WebSocket: протокол graphql-ws

URL: `ws://<host>:3000/graphql`, subprotocol: `graphql-transport-ws`.

### 6.1 Handshake

Клиент → сервер после открытия сокета:

```json
{
  "type": "connection_init",
  "payload": {
    "authorization": "Bearer <accessToken>"
  }
}
```

Сервер → клиент:

```json
{ "type": "connection_ack" }
```

(Опционально сервер может прислать `{ "type": "ka" }` — keep-alive/heartbeat, игнорировать или использовать для проверки живости.)

Если токен невалиден — сервер пришлёт `{"type": "error", "payload": [...]}` или закроет соединение (код 4403 `Forbidden`). Реакция: refresh-цикл из раздела 3.

### 6.2 Подписка

Клиент → сервер (регистрация подписки, у каждой свой уникальный `id`):

```json
{
  "id": "sub-1",
  "type": "subscribe",
  "payload": {
    "operationName": "GameStateUpdated",
    "query": "subscription GameStateUpdated($gameId: String!, $since: Float) { gameStateUpdated(gameId: $gameId, since: $since) { gameId sequenceNumber phase turnCount currentTurnPlayerId players fighters handZones boardState metadata } }",
    "variables": { "gameId": "abc-123", "since": 0 }
  }
}
```

Сервер → клиент (данные):

```json
{
  "id": "sub-1",
  "type": "next",
  "payload": {
    "data": {
      "gameStateUpdated": {
        "gameId": "abc-123",
        "sequenceNumber": 42,
        "phase": "MAIN",
        "turnCount": 7,
        "currentTurnPlayerId": "u1",
        "players": "{...}",
        "fighters": "{...}",
        "handZones": "{...}",
        "boardState": "{...}",
        "metadata": { "lastUpdatedAt": 1756800000000 }
      }
    }
  }
}
```

Сервер → клиент (завершение подписки):

```json
{ "id": "sub-1", "type": "complete" }
```

Отписка от клиента:

```json
{ "id": "sub-1", "type": "complete" }
```

Примечание: авторизацию можно передать и **per-subscription** в `payload.extensions` или `payload` — но наш бэкенд читает токен из `connectionParams`, поэтому используйте `connection_init`.

---

## 7. Жизненный цикл сессии

Типовой флоу (как в веб-клиенте): **Login → Lobby → (Room | Matchmaking) → Game**.

### 7.1 Login / восстановление сессии

1. `login(input: { email, password })` (или `register`) → сохранить `accessToken`, `refreshToken`
2. `me` → профиль пользователя для UI
3. При старте приложения с сохранёнными токенами: если токен не истёк — сразу `me`; при `UNAUTHENTICATED` — refresh-цикл

### 7.2 Лобби

Список открытых игр:

```graphql
query LobbyAvailableGames($mode: String, $limit: Float) {
  availableGames(mode: $mode, limit: $limit) {
    id mode status
    host { id username avatar }
    opponent { id username avatar }
    boardId createdAt updatedAt
  }
}
```

Создать игру:

```graphql
mutation CreateGame($input: CreateGameDto!) {
  createGame(input: $input) {
    id mode status hostId phase
    players { userId username heroId isReady }
  }
}
```

Присоединиться:

```graphql
mutation JoinGame($input: JoinGameDto!) {
  joinGame(input: $input) {
    id status phase
    players { userId username heroId isReady }
  }
}
```

### 7.3 Комната (room) — при игре по приглашению

Операции (все — HTTP mutations):

```graphql
mutation SelectHero($gameId: String!, $heroId: String!) {
  selectHero(gameId: $gameId, heroId: $heroId) { id players { userId heroId } }
}

mutation ToggleReady($gameId: String!) {
  toggleReady(gameId: $gameId) { id players { userId isReady } }
}

mutation StartGame($gameId: String!) {
  startGame(gameId: $gameId) { id status phase players { userId heroId } }
}

mutation LeaveGame($gameId: String!) { leaveGame(gameId: $gameId) }
```

`toggleReady` и `selectHero` — с заголовком `X-Idempotency-Key`.

Подписки комнаты (WebSocket): `playerJoined(gameId)`, `playerLeft(gameId)`, `gameStateUpdated(gameId, since)`.

Справочник контента для UI выбора:

```graphql
query Heroes { heroes { id name health movement set fighterType sidekickCount sidekickHealth urls { avatar mini cardCover } } }
query Boards { boards { id name width height recommendedPlayers imageUrl spaces { position { x y } zones isObstacle } } }
```

### 7.4 Матчмейкинг

Вступление в очередь (idempotencyKey — GraphQL-переменная):

```graphql
mutation JoinQueue($input: JoinQueueDto!, $idempotencyKey: String!) {
  joinQueue(input: $input, idempotencyKey: $idempotencyKey) {
    inQueue mode position totalPlayers estimatedWaitTime joinedAt
  }
}
```

Переменные: `{ "input": { "mode": "ONE_V_ONE", "heroPref": "<heroId>" }, "idempotencyKey": "<guid>" }`

Статус очереди и штрафы:

```graphql
query QueueStatus($mode: String!) {
  queueStatus(mode: $mode) { inQueue mode position totalPlayers estimatedWaitTime joinedAt }
}
query PenaltyInfo {
  penaltyInfo { canJoinQueue declineCount tempBanUntil penaltyElo reason }
}
```

Выход:

```graphql
mutation LeaveQueue($mode: String!, $idempotencyKey: String!) { leaveQueue(mode: $mode, idempotencyKey: $idempotencyKey) }
mutation LeaveAllQueues($idempotencyKey: String!) { leaveAllQueues(idempotencyKey: $idempotencyKey) }
```

Подписка на найденный матч:

```graphql
subscription MatchFound($userId: ID!) {
  matchFound(userId: $userId) {
    gameId opponentId opponentUsername opponentRating mode expiresAt
  }
}
```

WS-сообщение `subscribe` для неё:

```json
{
  "id": "sub-mm",
  "type": "subscribe",
  "payload": {
    "operationName": "MatchFound",
    "query": "subscription MatchFound($userId: ID!) { matchFound(userId: $userId) { gameId opponentId opponentUsername opponentRating mode expiresAt } }",
    "variables": { "userId": "u1" }
  }
}
```

По `matchFound` — перейти в комнату с полученным `gameId` (обратить внимание на `expiresAt` — подтверждение ограничено по времени).

### 7.5 Игра

**Инициализация:**

1. Запросить снапшот состояния:

```graphql
query GetGameState($gameId: String!) {
  gameState(gameId: $gameId) {
    id gameId state sequenceNumber currentTurnPlayerId phase turnCount updatedAt
  }
}
```

2. Открыть подписки (примеры payload — в разделе 6.2 и ниже):

- `gameStateUpdated(gameId, since)` — основное состояние (авторитетный источник)
- `turnChanged(gameId)` — `{ playerId, turnCount, phase }`
- События: `attackInitiated`, `defensePlayed`, `combatResolved`, `playerJoined`, `playerLeft`, `gameEnded` — каждое возвращает `{ type, gameId, sequenceNumber, timestamp, payload }`

**Игровые мутации** (все возвращают одинаковый shape — `GameActionResult`):

```graphql
mutation Attack($input: AttackDto!) {
  attack(input: $input) { state sequenceNumber phase currentTurnPlayerId turnCount timestamp }
}
```

Полный список: `maneuver`, `moveFighter`, `attack`, `playDefense`, `resolveCombat`, `endTurn`, `pass`, `toggleDoor`, `playScheme`, `resolvePendingEffect`, `setStance` (смена стойки — не тратит действие). Пример тела HTTP POST:

```json
{
  "query": "mutation Attack($input: AttackDto!) { attack(input: $input) { state sequenceNumber phase currentTurnPlayerId turnCount timestamp } }",
  "variables": {
    "input": { "gameId": "abc-123", "attackerId": "f1", "defenderId": "f2", "cardIds": ["c1", "c2"] }
  },
  "operationName": "Attack"
}
```

(Точные поля `AttackDto` и остальных DTO смотреть в SDL-схеме: `backend` генерирует схему автоматически — `autoSchemaFile: true`; актуальный SDL можно получить introspection-запросом или из Playground `http://localhost:3000/graphql`.)

**Восстановление после пропусков (sequence numbers):**

Каждый апдейт несёт `sequenceNumber`. Клиентская логика (см. `src/phaser/network/SubscriptionHandler.ts`):

- `sequenceNumber <= last` → устаревшее, отбросить
- `sequenceNumber > last + 1` → gap: запросить пропущенные события:

```graphql
query EventsSince($gameId: String!, $sinceSequence: Float!) {
  eventsSince(gameId: $gameId, sinceSequence: $sinceSequence) {
    gameId
    events { sequenceNumber type gameId payload timestamp }
    lastSequence
    hasMore
  }
}
```

- после разрыва WS: переподключиться, взять `gameState`-снапшот и/или `eventsSince(lastKnownSequence)`, затем возобновить подписку с `since: <lastSequence>`

**Завершение:** подписка `gameEnded` → показать результаты → `leaveGame(gameId)` → закрыть подписки.

---

## 8. Маппинг GameState на UE-структуры

Ключевой момент: в `gameStateUpdated` поля `players`, `fighters`, `handZones`, `boardState` — это **JSON-строки** (серериализованный JSON внутри GraphQL-строкового поля), а не вложенные GraphQL-объекты. Аналогично `state` в query `gameState` и `payload` в событиях.

То есть ответ приходит как:

```json
{
  "fighters": "[{\"id\":\"f1\",\"heroId\":\"deadpool\",\"position\":{\"x\":2,\"y\":3},\"health\":18,\"stance\":\"NEUTRAL\"}]"
}
```

и UE-клиент обязан **двухфазно парсить**: сначала JSON-ответ GraphQL, затем повторно распарсить строковые поля в структуры (`FJsonObjectConverter::JsonStringToUStruct` или аналог).

Рекомендуемые UE-структуры (символически):

```
FUnmGameState:
  gameId: String
  sequenceNumber: int64
  phase: EGamePhase          // enum: DEPLOYMENT, MAIN, ... (значения — из schema)
  turnCount: int32
  currentTurnPlayerId: String
  players:   TArray<FPlayerState>    <- парсить из JSON-строки
  fighters:  TArray<FFighterState>   <- парсить из JSON-строки
  handZones: THandZones              <- парсить из JSON-строки
  boardState: FBoardState            <- парсить из JSON-строки
```

Для событий (`attackInitiated` и т.п.) — общий `FGameEvent { type, gameId, sequenceNumber, timestamp, payload }`, где `payload` — снова JSON-строка с деталями события (атакующая/защищающаяся карты, урон и т.п.).

Ориентир по разбору — веб-адаптер `src/lib/gameStateAdapter.ts`: он делает ровно это (stringify/parse строковых полей GameState).

---

## 9. Обработка ошибок

### Формат GraphQL-ошибок

Ошибки приходят в теле ответа (HTTP может быть 200):

```json
{
  "data": null,
  "errors": [
    {
      "message": "Game not found",
      "extensions": { "code": "NOT_FOUND" },
      "path": ["game"]
    }
  ]
}
```

### Коды и реакции

| Признак | Реакция в UE |
|---|---|
| `code: UNAUTHENTICATED`, `AUTH_TOKEN_EXPIRED`, `AUTH_INVALID_TOKEN`, HTTP 401 | Refresh-цикл (раздел 3): `refreshTokens` → повтор запроса |
| Refresh не удался / нет refresh-токена | Logout, экран логина |
| `code: BAD_USER_INPUT` / `GRAPHQL_VALIDATION_FAILED` | Ошибка пользовательского ввода — показать в UI |
| Сетевые ошибки / обрыв WS | Retry с backoff (веб-клиент: 5 попыток переподключения WS, задержка между попытками); после reconnect — resync через `gameState` + `eventsSince` |
| `Query is too complex` / depth | Упростить запрос (меньше полей/вложенности) |

### Санитайзинг на сервере

В production `formatError` скрывает внутренние детали: системные ошибки приходят как `{ message: "Internal server error", code: "INTERNAL_SERVER_ERROR" }`. Бизнес-ошибки (`BAD_USER_INPUT`, валидация, `not found`/`unauthorized` в сообщении) приходят как есть. Не полагайтесь на тексты системных ошибок.

### WS-ошибки

- `{"type": "error", "payload": [...]}` — ошибка подписки (например, невалидная операция)
- Закрытие сокета с кодом **4403** — Forbidden (токен отклонён на handshake) → refresh и reconnect
- Закрытие сокета с кодом **4408** — Connection initialisation timeout (не послали `connection_init` вовремя)
- Закрытие сокета с кодом **4409** — Subscriber already exists (дубликат `id` подписки) — генерировать уникальные id

---

## 10. Чек-лист подключения (кратко)

1. POST `http://host:3000/graphql` — все queries/mutations, `Authorization: Bearer ...`
2. WS `ws://host:3000/graphql` + subprotocol `graphql-transport-ws`
3. Handshake: `connection_init` с `payload.authorization = "Bearer <token>"`, ждать `connection_ack`
4. Подписки через `subscribe` с уникальными id; данные — в `next`, конец — `complete`
5. Refresh-цикл на 401/UNAUTHENTICATED, повтор запроса, пересоздание WS после refresh
6. `X-Idempotency-Key` для `toggleReady`/`selectHero`; `idempotencyKey`-переменная для matchmaking-мутаций
7. Строковые JSON-поля GameState (`players`, `fighters`, `handZones`, `boardState`, `state`, `payload`) — парсить вторым проходом
8. Отслеживать `sequenceNumber`, gap-ы закрывать через `eventsSince`
9. Ограничения запросов: complexity ≤ 1000, depth ≤ 7, никаких лишних полей в input-DTO

### Источники в репозитории

- `src/lib/apolloClient.ts` — цепочка ссылок, WS-конфиг, `connectionParams`
- `src/lib/auth-link.ts`, `src/lib/error-link.ts`, `src/lib/token-storage.ts` — авторизация и refresh
- `src/phaser/network/SubscriptionHandler.ts` — подписки игры, обработка sequenceNumber/gap/reconnect
- `src/graphql/{queries,mutations,subscriptions}/*.graphql` — полный каталог операций
- `src/store/matchmakingStore.ts`, `src/store/roomStore.ts` — идемпотентность, флоу лобби/матчмейкинга
- `backend/src/main.ts` — CORS, порт, allowed headers
- `backend/src/graphql/graphql.module.ts` — graphql-ws, validation rules, formatError
