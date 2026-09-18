# 04 — Игровое API и протокол синхронизации состояния

> Документ для разработчика клиента (в т.ч. Unreal Engine), повторяющего протокол.
> Источники: `backend/src/games/**`, `backend/src/game-engine/**`, `backend/src/game/validators/**`,
> `src/graphql/{queries,mutations,subscriptions}/game.graphql`, `src/phaser/network/**`, `src/phaser/hooks/**`.

---

## 1. Транспорт и аутентификация

| Что | Как |
|---|---|
| Queries / Mutations | HTTP POST на `http://<host>:3000/graphql` |
| Subscriptions | WebSocket по протоколу **graphql-ws** (`ws://<host>:3000/graphql`) |
| Авторизация | JWT Bearer: заголовок `Authorization: Bearer <accessToken>` (HTTP), `connectionParams: { authorization: "Bearer <token>" }` (WS) |
| CORS-заголовки | `Content-Type`, `Authorization`, `X-Idempotency-Key`, `apollo-require-preflight` |
| Формат | Стандартный GraphQL over JSON, ответы без обёртки `data/` на уровне транспорта Apollo (сам GraphQL возвращает `{ "data": ..., "errors": ... }`) |

Все игровые queries/mutations (кроме `availableGames`, `heroStances` и контент-запросов) требуют JWT. `userId` игрока **всегда** берётся из токена на сервере — передавать его в аргументах не нужно и бессмысленно.

Rate limits (NestJS Throttler, на мутацию): `createGame` 10/мин, `joinGame` 15/мин, `startGame`/`abortGame` 5/мин, `toggleReady` 20/мин, `selectHero` 10/мин, `attack`/`playDefense`/`resolveCombat`/`playScheme`/`pass` 20/мин, `maneuver`/`moveFighter`/`endTurn`/`toggleDoor`/`setStance`/`resolvePendingEffect` 30/мин.

---

## 2. Конвейер выполнения мутации (сервер)

Каждая gameplay-мутация проходит один и тот же путь (`backend/src/games/resolvers/game-actions.resolver.ts`, `executeMutation`):

1. `GqlAuthGuard` — userId из JWT.
2. `GameInProgressGuard` — `game.status == IN_PROGRESS`.
3. `GamePlayerGuard` — userId ∈ игроки игры.
4. Фазовый guard (`ActionPhaseGuard` / `DefensePlayGuard` / `CombatResolveGuard`).
5. `DistributedLockService.withLock("game:<gameId>")` — сериализация одновременных мутаций (TTL 10 с).
6. Загрузка состояния (`GameStateService.loadState`), выполнение через `GameActionExecutorService.executeXxx(...)` (game-engine).
7. `saveState` — инкремент `sequenceNumber`, публикация внутреннего события `STATE_UPDATED`.
8. Спец-логика боя: после `attack` планируется **auto-resolve через 30 с**; `playDefense`/`resolveCombat` отменяют таймер.
9. `publishGameUpdate(gameId, eventType, state)` — публикация в PubSub (topic `game.updates.<gameId>` + Redis broadcast для нескольких инстансов).
10. Запись в журнал `GameAction` (для `eventsSince`/catch-up). При `phase == GAME_OVER` дополнительно публикуется событие `GAME_ENDED`.
11. **Фильтрация приватных данных** под запросившего пользователя и возврат `GameMutationResult`.

Обрати внимание: на **каждую** мутацию PubSub получает **два** события — `STATE_UPDATED` (из saveState) и специфичный `eventType` (из шага 9). Подписка `gameStateUpdated` фильтрует по `eventType == 'STATE_UPDATED'`, поэтому срабатывает ровно один раз на мутацию.

### Ошибки

Невалидный ход → GraphQL `errors` с `BadRequestException` (`message` = причина, напр. `"Not your turn"`, `"Card not in hand"`). Конфликты — `ConflictException` (409). Ошибки валидации DTO — 400 с описанием поля.

---

## 3. Основные enum

```graphql
enum GameMode { ONE_V_ONE  TWO_V_TWO  FREE_FOR_ALL  VS_AI }
enum GameStatus { PENDING  LOBBY  IN_PROGRESS  PAUSED  FINISHED  ABORTED }

# Фазы игры (машина состояний хода)
enum GamePhase {
  SETUP              # размещение бойцов
  TURN_START         # начало хода
  ACTION_MANEUVER    # фаза действия (манёвр/scheme/атака — 2 действия за ход)
  ACTION_ATTACK      # фаза действия (атака)
  COMBAT             # атака объявлена, ждём защиту (таймаут 30 с)
  COMBAT_RESOLVE     # разрешение боя
  TURN_END           # конец хода
  GAME_OVER          # игра окончена
}

enum GameEventType {
  ATTACK_INITIATED  DEFENSE_PLAYED  COMBAT_RESOLVED  TURN_CHANGED
  PLAYER_JOINED  PLAYER_LEFT  GAME_ENDED  FIGHTER_MOVED  DOOR_TOGGLED
  MANEUVER  TURN_ENDED  CARD_PLAYED  GAME_CREATED  GAME_JOINED
  GAME_STARTED  GAME_ABORTED  TURN_STARTED  PASSED  CARD_DISCARDED
  PLACED  EFFECT_APPLIED  SPECIAL_ABILITY
}
```

Правила Unmatched: у игрока **ровно 2 действия за ход** (`ACTIONS_PER_TURN = 2`; счётчик — `metadata.actionsRemaining`). Манёвр / атака / scheme — 1 действие, атаковать можно дважды. `setStance` и `resolvePendingEffect` действие **не тратят**.

---

## 4. Queries

### 4.1 game(id) — метаданные игры

```graphql
query GetGame($id: String!) {
  game(id: $id) {
    id mode status hostId boardId winnerId
    createdAt updatedAt startedAt endedAt phase currentTurn
    players { id userId username avatar heroId isReady hasPassed seatOrder }
  }
}
```

Только участники (или публичные/завершённые игры). Возвращает лоббийно-метаданные из БД (Prisma), не engine-состояние.

### 4.2 myGames / availableGames

```graphql
query MyGames($filters: GameFiltersDto) {
  myGames(filters: $filters) { id mode status hostId createdAt phase currentTurn
    players { userId username avatar heroId isReady } }
}
query AvailableGames($mode: String, $limit: Float) {
  availableGames(mode: $mode, limit: $limit) { id mode status players { userId username avatar heroId } }
}
```

`GameFiltersDto: { status?: GameStatus, mode?: GameMode, limit?: Int (1..100), offset?: Int }`.

### 4.3 gameState(gameId) — полный снапшот engine-состояния

```graphql
query GetGameState($gameId: String!) {
  gameState(gameId: $gameId) {
    id                 # "<gameId>-state"
    gameId
    state              # String: JSON GameState (уже отфильтрован под тебя!)
    sequenceNumber
    currentTurnPlayerId
    phase
    turnCount
    updatedAt
  }
}
```

Только участники. **`state` — это сериализованный в JSON `GameState` (см. §6), из которого удалены приватные данные других игроков** (карты в их руках показываются как рубашки, `topCard` их колод скрыт). На UE: `JSON.parse(state)`.

### 4.4 gameSequence(gameId) → Float/Int

Текущий `sequenceNumber` — для оптимистичных обновлений и проверки пропусков.

### 4.5 eventsSince(gameId, sinceSequence) — catch-up при реконнекте

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

Возвращает до 100 событий журнала `GameAction` после указанного sequence (`hasMore == true` → листать дальше). `payload` — JSON-строка с `{ action, input, ... }`.

### 4.6 heroStances(heroSlug) → [StanceOptionDto] (публичный)

```graphql
query { heroStances(heroSlug: "alice") { id label isDefault } }
# → [{ "id": "big", "label": "Big", "isDefault": true }, { "id": "small", ... }]
```

Статичный справочник стоек героя (читается из `ABILITY_CONFIGS`, не из состояния). Для героев без стоек — `[]`. Кэшировать на клиенте, в снапшот не входит.

### 4.7 Контент

`heroes`, `hero(id)`, `boards`, `board(id)`, `contentSummary`, `sets` — публичные справочники (герои с `health/movement/set/fighterType/sidekickCount`, карты `id/title/type/value/boost/quantity/imageUrl/imageUrlRu`, доски с `spaces { position {x y} zones isObstacle }`). Для UE нужны для отрисовки_assets и колод.

---

## 5. Mutations

### 5.1 Лоббийные

| Мутация | Сигнатура | Возвращает |
|---|---|---|
| createGame | `(input: { mode?: GameMode, boardId?: String }, idempotencyKey?: String)` | `GameResponse` |
| joinGame | `(input: { gameId: String!, heroId?: String, asOpponent?: Boolean })` | `GameResponse` |
| leaveGame | `(gameId: String!)` → `Boolean` | хост передаёт хостство или игра удаляется |
| startGame | `(gameId: String!)` | `GameResponse`, инициализирует engine-состояние |
| abortGame | `(gameId: String!)` | `GameResponse` |
| toggleReady | `(gameId: String!)` | `GameResponse` |
| selectHero | `(gameId: String!, heroId: String!)` | `GameResponse` |

### 5.2 Gameplay-мутации — единый формат ответа

Все возвращают `GameMutationResult`:

```graphql
type GameMutationResult {
  state: String            # JSON отфильтрованного GameState (может быть null)
  sequenceNumber: Int!
  timestamp: DateTime!
  phase: GamePhase!
  currentTurnPlayerId: String
  turnCount: Int!
}
```

#### maneuver(input: ManeuverDto) — тратит 1 действие

Манёвр = добор 1 карты + движение **всех своих бойцов** (+ boost при сбросе карты).

```graphql
input PositionInput { x: Int!  y: Int! }   # 0..19
input ManeuverMoveInput { fighterId: String!  path: [PositionInput!]! }
input ManeuverDto {
  gameId: String!
  moves: [ManeuverMoveInput!]   # новый формат: движение каждого бойца
  boostCardId: String           # сброс карты из руки → +boostValue к движению ВСЕМ
  # legacy (deprecated): fighterId, cardId, path
}
```

#### moveFighter(input: MoveFighterDto) — тратит 1 действие

```graphql
input MoveFighterDto { gameId: String!  fighterId: String!  x: Int!  y: Int! }
```

#### attack(input: AttackDto) — тратит 1 действие, переводит в COMBAT

```graphql
input AttackDto {
  gameId: String!
  attackerId: String!   # id бойца-атакующего (из fighters)
  targetId: String!     # id бойца-цели (должен быть в зоне атаки)
  cardId: String!       # ATTACK/VERSATILE карта из руки
  boostCardId: String   # опц.: сброс карты → +boostValue к атаке
}
```

Сервер ставит 30-секундный таймер auto-resolve: если защитник не успел — бой разрешается автоматически.

#### playDefense(input: PlayDefenseDto) — фаза COMBAT, только защитник

```graphql
input PlayDefenseDto { gameId: String!  cardId: String!  boostCardId: String }
```

userId из JWT. Отменяет таймер auto-resolve.

#### resolveCombat(input: ResolveCombatDto) — фазы COMBAT/COMBAT_RESOLVE

```graphql
input ResolveCombatDto { gameId: String! }
```

Сравнивает финальные значения: `finalAttack > finalDefense` → урон защите; ничья — в пользу защитника (правило Unmatched). Применяет эффекты карт (WON/LOST_COMBAT), переводит фазу назад в action-фазу.

#### playScheme(input: PlaySchemeDto) — тратит 1 действие

```graphql
input PlaySchemeDto { gameId: String!  cardId: String! }
```

Авто-эффекты применяются best-effort; эффекты с выбором (MOVE/PLACE/CHOOSE_ONE) складываются в `metadata.pendingEffects`.

#### resolvePendingEffect(input: ResolvePendingEffectDto) — НЕ тратит действие

```graphql
input ResolvePendingEffectDto {
  gameId: String!
  effectId: String!      # id из metadata.pendingEffects[]
  fighterId: String      # для MOVE/PLACE
  x: Int  y: Int         # для MOVE/PLACE
  optionIndex: Int       # для CHOOSE_ONE (индекс из pending.options)
}
```

#### endTurn(input: EndTurnDto) / pass(input: PassDto) / toggleDoor(input: ToggleDoorDto)

```graphql
input EndTurnDto { gameId: String! }        # завершить ход (после ≥1 манёвра)
input PassDto { gameId: String! }           # сброс верхней карты колоды + доп. действие
input ToggleDoorDto { gameId: String!  x: Int!  y: Int! }  # спец-способность (Bjorn)
```

#### setStance(input: SetStanceDto) — НЕ тратит действие

```graphql
input SetStanceDto { gameId: String!  stanceId: String! }  # id из heroStances(heroSlug)
```

Меняет `metadata.heroStances[userId]`. Доступно в action-фазах текущему игроку; стойку можно менять при размещении/начале хода/«Change size»-картах.

### 5.3 Пример полного запроса + ответа

```graphql
mutation Attack($input: AttackDto!) {
  attack(input: $input) {
    state sequenceNumber phase currentTurnPlayerId turnCount timestamp
  }
}
```

Variables:

```json
{ "input": { "gameId": "clx abc123", "attackerId": "f-alice-p1", "targetId": "f-kingarthur-p2", "cardId": "card-42", "boostCardId": "card-7" } }
```

Ответ (типичный):

```json
{
  "data": {
    "attack": {
      "state": "{\"gameId\":\"clx...\",\"sequenceNumber\":14,\"phase\":\"COMBAT\",\"turnCount\":6,\"currentTurnPlayerId\":\"user-1\",\"players\":[...],\"fighters\":[...],\"handZones\":{...},\"boardState\":{...},\"metadata\":{\"combatInfo\":{\"attackerId\":\"f-alice-p1\",\"defenderId\":\"user-2\",\"targetFighterId\":\"f-kingarthur-p2\",\"attackerCardId\":\"card-42\",\"attackValue\":5,\"startedAt\":\"2026-09-02T10:00:00.000Z\",\"timeoutAt\":\"2026-09-02T10:00:30.000Z\"},\"actionsRemaining\":1,...}}",
      "sequenceNumber": 14,
      "phase": "COMBAT",
      "currentTurnPlayerId": "user-1",
      "turnCount": 6,
      "timestamp": "2026-09-02T10:00:00.123Z"
    }
  }
}
```

Ошибка (не твой ход):

```json
{ "errors": [{ "message": "Not your turn", "extensions": { "code": "BAD_REQUEST" } }], "data": null }
```

---

## 6. Структура GameState (JSON в полях `state` / подписках)

Внутренний тип — `backend/src/game-engine/models/game-state.model.ts`. Все массивы/объекты сериализуются в JSON-строки в GraphQL-полях.

```jsonc
{
  "gameId": "clx...",
  "sequenceNumber": 14,          // монотонный счётчик, +1 на каждую мутацию
  "phase": "ACTION_MANEUVER",
  "turnCount": 6,
  "currentTurnPlayerId": "user-1",

  "players": [                   // GameStatePlayer[]
    {
      "userId": "user-1",
      "heroId": "clz...",        // Prisma cuid героя
      "health": 16,              // здоровье героя (суммарное по команде см. fighters)
      "maxHealth": 18,
      "fighterIds": ["f-alice-p1", "f-sidekick-p1"],
      "isAlive": true
    }
  ],

  "fighters": [                  // Fighter[] — все бойцы на доске
    {
      "id": "f-alice-p1",
      "ownerId": "user-1",
      "heroId": "clz...",
      "heroSlug": "alice",       // слаг для реестра способностей
      "name": "Alice",
      "type": "HERO",            // HERO | MINION | HUGE
      "health": 16,
      "maxHealth": 18,
      "position": { "x": 3, "y": 4 },
      "movement": 2,             // очки движения (default 2)
      "attackType": "melee",     // melee | ranged
      "effects": [ { "type": "...", "value": 1, "duration": "turn" } ],
      "hasSidekick": true,
      "sidekickIds": ["f-sidekick-p1"],
      "isDefeated": false
    }
  ],

  "decks": {                     // Record<userId, DeckState>
    "user-1": { "cards": [...], "drawPile": [/* id карт, рубашки */], "topCard": { ... } }
    // topCard чужой колоды скрыт фильтром (undefined)
  },
  "discardPiles": { "user-1": [ /* Card[] */ ] },

  "handZones": {                 // Record<userId, HandZone>
    "user-1": {
      "maxSize": 10,
      "cards": [                 // HandCard = Card + isVisible
        { "id": "card-42", "cardId": "c-42", "name": "Swift Strike", "nameEn": "...", "nameRu": "...",
          "cardType": "ATTACK",   // ATTACK | DEFENSE | SCHEME | UNIVERSAL | VERSATILE | MANEUVER
          "attackValue": 4, "defenseValue": 3, "boostValue": 2,
          "effects": [ { "id": "e1", "type": "DAMAGE", "timing": "...", "value": 1, "when": { "kind": "WON_COMBAT" } } ],
          "text": "After combat...", "bannerName": "Medusa",
          "isVisible": true }
      ]
    },
    "user-2": {
      "cards": [ /* чужие карты: только id/cardType/name:"???"/isVisible:false — значения скрыты */ ]
    }
  },

  "boardState": {                // BoardState
    "width": 8, "height": 8,
    "cells": [ [ { "type": "normal", "x": 0, "y": 0, "zones": ["red"], "isHighGround": false } ] ],
    "doors":  { "door-1": true },            // doorId -> открыта?
    "fog":    { "0,0": false },              // клетка -> туман
    "tokens": {}                             // клетка -> жетоны
  },

  "metadata": {                  // GameStateMetadata
    "lastActionAt": "2026-09-02T10:00:00.000Z",
    "lastActionBy": "user-1",
    "version": 1,
    "combatInfo": {              // CombatState | undefined — живёт между attack и resolveCombat
      "attackerId": "user-1",
      "defenderId": "user-2",
      "targetFighterId": "f-kingarthur-p2",
      "attackerCardId": "card-42",
      "defenderCardId": "card-9",
      "attackValue": 5,
      "defenseValue": 4,
      "startedAt": "...", "timeoutAt": "..."   // auto-resolve дедлайн (30 с)
    },
    "actionsRemaining": 1,       // осталось действий (default 2)
    "passCount": 0,
    "winnerId": null,            // при GAME_OVER
    "turnStartPositions": { "f-alice-p1": { "x": 2, "y": 4 } },
    "pendingEffects": [          // PendingEffect[] — эффекты, ждущие выбора игрока
      { "id": "pe-1", "type": "MOVE", "playerId": "user-1", "value": 2, "text": "You may move..." }
    ],
    "maneuveredThisTurn": true,  // per-turn флаги для условий способностей
    "attackedThisTurn": false,
    "lostCombatThisTurn": false,
    "heroStances": { "user-1": "big" }   // Record<userId, stanceId> — STANCE-подсистема
  }
}
```

**Cell.zones**: клетка может состоять в 1–2 зонах; ranged-атаки и зонные эффекты работают по **пересечению** зон бойцов (legacy-поле `zone` = первая зона).

### Фильтрация приватных данных (per-user)

`GameStateService.filterPrivateData(state, userId)`:
- рука **чужого** игрока: карты с `name: "???", nameEn: "Hidden", nameRu: "Скрыто"`, `isVisible: false`, без `attackValue/defenseValue/boostValue/effects/text`;
- `topCard` чужой колоды — удалён;
- своя рука и своя колода — полностью.

Это применяется и в `query gameState`, и в ответе каждой мутации, и в каждой доставке `gameStateUpdated` (индивидуально под каждого подписчика, по JWT-контексту, не по аргументам!).

---

## 7. Subscriptions

Все — по websocket (graphql-ws), все с guard'ом JWT, все фильтруются по `gameId` в variables.

### 7.1 gameStateUpdated — основной канал состояния

```graphql
subscription GameStateUpdated($gameId: String!, $since: Float) {
  gameStateUpdated(gameId: $gameId, since: $since) {
    gameId sequenceNumber phase turnCount currentTurnPlayerId
    players      # String: JSON GameStatePlayer[]
    fighters     # String: JSON Fighter[]
    handZones    # String: JSON Record<userId, HandZone> (уже отфильтровано под ТЕБЯ)
    boardState   # String: JSON BoardState
    metadata     # String: JSON GameStateMetadata
  }
}
```

- Публикуется на **каждую** сохраняющую состояние мутацию (фильтр `eventType == 'STATE_UPDATED'`).
- `since` — серверный фильтр: события с `sequenceNumber <= since` не доставляются (для реконнекта).
- Клиент обязан трекать `sequenceNumber` и обрабатывать пропуски (§8).

Пример доставленных `next`-данных:

```json
{
  "data": {
    "gameStateUpdated": {
      "gameId": "clx...",
      "sequenceNumber": 15,
      "phase": "COMBAT_RESOLVE",
      "turnCount": 6,
      "currentTurnPlayerId": "user-1",
      "players": "[{\"userId\":\"user-1\",...}]",
      "fighters": "[{\"id\":\"f-alice-p1\",...}]",
      "handZones": "{\"user-1\":{\"cards\":[...]},\"user-2\":{\"cards\":[{\"name\":\"???\",\"isVisible\":false}...]}}",
      "boardState": "{\"width\":8,...}",
      "metadata": "{\"combatInfo\":{...},\"actionsRemaining\":1,...}"
    }
  }
}
```

### 7.2 Событийные подписки — `GameEvent`

`attackInitiated`, `defensePlayed`, `combatResolved`, `gameEnded` (тип `GameEvent`):

```graphql
subscription AttackInitiated($gameId: String!) {
  attackInitiated(gameId: $gameId) { type gameId sequenceNumber timestamp payload }
}
```

`payload` — JSON-строка **безопасного подмножества**: `{"phase","turnCount","currentTurnPlayerId"}` (без рук). Это «пинговые» события для анимаций/UI; полный состояние — через `gameStateUpdated`. Пример:

```json
{ "data": { "attackInitiated": {
    "type": "ATTACK_INITIATED", "gameId": "clx...", "sequenceNumber": 14,
    "timestamp": "2026-09-02T10:00:00.123Z",
    "payload": "{\"phase\":\"COMBAT\",\"turnCount\":6,\"currentTurnPlayerId\":\"user-1\"}"
} } }
```

### 7.3 turnChanged — `TurnState`

```graphql
subscription TurnChanged($gameId: String!) {
  turnChanged(gameId: $gameId) { playerId turnCount phase }
}
```

Срабатывает на `TURN_ENDED` (мутация `endTurn`) и `TURN_CHANGED`; `playerId` = **следующий** игрок (из нового состояния).

### 7.4 playerJoined / playerLeft — `GameEvent`

Известный gap на бэкенде: в игре (когда есть GameState) эти события сейчас никто не публикует — лоббийные join/leave идут через `publishLobbyEvent` с компактным payload `{userId, username}` (см. доки lobby/room). Подписки не виснут, но в игровой фазе молчат.

### 7.5 Отправка подписки на WS (для UE)

graphql-ws протокол: `connection_init` с `connectionParams`, затем `subscribe` с `id` и `query/variables`; события приходят как `next` / `error` / `complete`.

---

## 8. Протокол синхронизации: порядок обработки на клиенте

Рекомендуемый (и реализованный в Phaser-клиенте) алгоритм:

1. **Вход в игру**: `query gameState` → полный снапшот, запомнить `sequenceNumber` (N).
2. **Подписка**: `subscription gameStateUpdated(gameId, since: N)` + событийные подписки. Событие с `sequenceNumber <= N` игнорируется (дедупликация).
3. **Каждое обновление**:
   - если `seq <= lastSeq` → пропустить (устаревшее);
   - если `seq > lastSeq + 1` → **gap**: переподписаться с `since: lastSeq` и/или `query eventsSince(gameId, lastSeq)` для догоняния, в крайнем случае перезачитать `gameState`;
   - иначе применить снапшот: распарсить `players/fighters/handZones/boardState/metadata` (JSON.parse каждого поля) и обновить мир.
4. **Свой ход**: мутация (HTTP) → ответ `GameMutationResult` уже содержит новое состояние (`state`) и `sequenceNumber`. Можно применить оптимистично, но подписка продублирует то же `sequenceNumber` — дедупликация по номеру обязательна. При ошибке мутации — откат оптимистичного UI и показать `errors[0].message`.
5. **Атака оппонента**: приходит `attackInitiated` (триггер UI защиты) и `gameStateUpdated` с `phase: COMBAT` и `metadata.combatInfo.timeoutAt` — запустить таймер защиты на 30 с. Если ты защитник и успеваешь — `playDefense`; иначе сервер разрезолвит сам (auto-resolve).
6. **Реконнект WS**: переподключение (экспоненциальный backoff, ~5 попыток на клиенте), затем `since: lastSeq` в подписке; при больших дырах — `eventsSince` / полный `gameState`.
7. **VS_AI**: после твоей мутации бот отыгрывает свой ход асинхронно — его апдейты приходят только через подписку.

---

## 9. Валидация ходов (сервер, `GameRulesValidator` + executor)

Что проверяется при каждой мутации (не исчерпывающе, но контракт такой):

- **Чей ход**: `userId == currentTurnPlayerId` (кроме `playDefense` — защитник; `resolveCombat` — участник боя).
- **Фаза**: action-мутации — только в `ACTION_MANEUVER`/`ACTION_ATTACK`; `playDefense` — `COMBAT`; `resolveCombat` — `COMBAT`/`COMBAT_RESOLVE`.
- **Действия**: `metadata.actionsRemaining > 0` для манёвра/атаки/scheme/pass/moveFighter/toggleDoor.
- **Владение**: боец/карта принадлежат текущему игроку, карта — в его `handZones`.
- **Тип карты**: атака — `ATTACK`/`VERSATILE` (учитывая `bannerName` — кто может играть), защита — `DEFENSE`/`VERSATILE`.
- **Геометрия**: длина пути ≤ `movement` бойца (+boost), проходимость клеток, двери; цель атаки в зоне досягаемости (`melee` — смежная клетка, `ranged` — та же/смежная зона по пересечению зон); бонус возвышенности (`isHighGround`) ±1.
- **Бой**: `combatInfo` согласован с мутацией; таймаут 30 с → auto-resolve; ничья в пользу защитника.

Все нарушения → `BadRequestException` в `errors[0].message`. Клиент UE должен рассчитывать на отказ любой мутации и уметь откатываться к последнему снапшоту.

---

## 10. Шпаргалка соответствия мутация → событие

| Мутация | eventType (журнал/подписки) |
|---|---|
| maneuver | `MANEUVER` |
| moveFighter | `FIGHTER_MOVED` |
| attack | `ATTACK_INITIATED` (+ таймер auto-resolve 30 с) |
| playDefense | `DEFENSE_PLAYED` (отменяет таймер) |
| resolveCombat | `COMBAT_RESOLVED` (отменяет таймер) |
| playScheme | `CARD_PLAYED` |
| resolvePendingEffect | `CARD_PLAYED` |
| endTurn | `TURN_ENDED` (триггерит `turnChanged`) |
| pass | `CARD_PLAYED` (журнал: `PASSED`) |
| toggleDoor | `DOOR_TOGGLED` |
| setStance | `SPECIAL_ABILITY` |
| любая мутация, доведшая `phase` до `GAME_OVER` | дополнительно `GAME_ENDED` |

При этом `gameStateUpdated` срабатывает на каждую из них ровно один раз (внутренний `STATE_UPDATED`).
