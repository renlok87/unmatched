# R3 — Игровое API и полный GraphQL-контракт (research для UE-клиента)

> Ридер: R3-game-api-schema. Дата: 2026-09-02.
> Основные источники: `docs/backend-api/04-game-api.md` (далее **D04**), `docs/backend-api/07-graphql-schema-reference.md` (далее **D07**).
> Сверка с кодом: `backend/src/games/**`, `backend/src/game-engine/**`, `backend/src/graphql/**`, `backend/prisma/schema.prisma`, `src/graphql/**`, `src/gql/graphql.ts` (сгенерированные типы схемы), `src/lib/**`, `src/phaser/**`.
> Все пути ниже — относительно корня репозитория `C:/Users/ren/WebstormProjects/unmached/unmached/`.
> Обозначение `файл:строка` — ссылка на источник факта. Где документ и код расходятся — это явно помечено «**РАСХОЖДЕНИЕ**» и вынесено в §4.

---

## 1. Краткое резюме

Игровой контракт — code-first GraphQL (NestJS + Apollo, `autoSchemaFile: true`, `sortSchema: true`; файла `schema.gql` в репозитории нет — D07:3, `backend/src/graphql/graphql.module.ts:14-15`). Queries/mutations — HTTP `POST /graphql`; подписки — WebSocket по протоколу **graphql-ws** (D04:13-14, `graphql.module.ts:19-21`). Авторизация — JWT Bearer; для WS токен передаётся в `connectionParams.authorization` (или `Authorization`/`token`, префикс `Bearer ` дописывается сервером при отсутствии — `graphql.module.ts:25-31`). `userId` всегда берётся из JWT, в аргументах не передаётся (D04:19).

Все 11 gameplay-мутаций (`maneuver`, `moveFighter`, `attack`, `playDefense`, `playScheme`, `resolvePendingEffect`, `resolveCombat`, `endTurn`, `pass`, `toggleDoor`, `setStance`) принимают один аргумент `input: <XxxDto>!` и возвращают единый `GameMutationResult!` (`state: String` — JSON отфильтрованного `GameState`, `sequenceNumber: Int!`, `timestamp: DateTime!`, `phase: GamePhase!`, `currentTurnPlayerId: String`, `turnCount: Int!`) — D07:321, `backend/src/games/dto/gameplay.dto.ts:437-458`.

Состояние игры доставляется **двумя формами**: (а) одной JSON-строкой `state` (query `gameState`, все мутации); (б) в подписке `gameStateUpdated` — пятью отдельными JSON-строками `players/fighters/handZones/boardState/metadata` (**без** `decks`/`discardPiles`). Обе формы фильтруются под запросившего пользователя по JWT: чужие карты в руке обезличены (`name: "???"`, значения удалены), `topCard` чужой колоды удалён (`backend/src/games/game-state.service.ts:494-538`). Синхронизация — по монотонному `sequenceNumber` (+1 на каждую мутацию, включая авто-ходы ИИ и auto-resolve), дедупликация и детект gap — обязанность клиента; для реконнекта есть аргумент `since` подписки и query `eventsSince` (журнал действий, без состояния). Даты в GraphQL-полях `DateTime` сериализуются как **epoch-миллисекунды (число)**, а даты внутри JSON-состояния — как ISO-строки.

Главные находки сверки с кодом (детали в §4): скаляры некоторых полей на самом деле `Float`, а не `Int` (`since`, `sinceSequence`, `gameSequence`, `GameStateResponse.sequenceNumber/turnCount`, `GamePlayerResponse.seatOrder`, `GameResponse.version`); `combatInfo.timeoutAt` в коде **никогда не выставляется**; auto-resolve по таймауту **не разрешает бой**, а лишь переводит фазу в `COMBAT_RESOLVE` (TODO в коде); `pass` **не сбрасывает карту** (TODO); `toggleDoor` **не тратит действие**; ходы ИИ и auto-resolve **не пишутся в журнал** `eventsSince`; `GameStateResponse.phase` — `String!`, а не enum; `combatInfo.attackerId` — id **бойца**, `defenderId` — **userId**.

---

## 2. Факты

### 2.1. Транспорт, авторизация, лимиты

| Факт | Источник |
|---|---|
| Queries/Mutations: HTTP `POST http://<host>:3000/graphql` | D04:13 |
| Subscriptions: WebSocket `ws://<host>:3000/graphql`, протокол **graphql-ws** (`subscriptions: { 'graphql-ws': true }`) | D04:14; D07:4; `backend/src/graphql/graphql.module.ts:19-21` |
| HTTP-авторизация: заголовок `Authorization: Bearer <accessToken>` | D04:15; D07:7 |
| WS-авторизация: `connectionParams: { authorization: "Bearer <token>" }`; сервер принимает ключи `authorization`, `Authorization`, `token`; если значение не начинается с `Bearer`, префикс дописывается | D04:15; D07:7; `graphql.module.ts:25-31` |
| Контекст подписки формируется как `{ req: { headers: { authorization } }, isSubscription: true }` (тот же `GqlAuthGuard`) | `graphql.module.ts:31-32` |
| CORS-заголовки: `Content-Type`, `Authorization`, `X-Idempotency-Key`, `apollo-require-preflight` | D04:16 |
| Playground включён; CSRF-prevention отключён | D07:5; `graphql.module.ts:16-17` |
| Глобального guard'а нет — каждый резолвер вешает `@UseGuards(GqlAuthGuard, ...)`; поля без guard'а публичны | D07:7 |
| Защита запросов: complexity ≤ 1000 (warning при >500), depth ≤ 7 | D07:11-14; `graphql.module.ts:38-58` |
| Все игровые queries/mutations требуют JWT, кроме `availableGames`, `heroStances` и контент-запросов | D04:19; D07:58,60 |
| `userId` игрока всегда из JWT | D04:19 |
| Rate limits (`@Throttle`, за 60 с): `createGame` 10, `joinGame` 15, `leaveGame` 10, `startGame`/`abortGame` 5, `toggleReady` 20, `selectHero` 10; `attack`/`playDefense`/`resolveCombat`/`playScheme`/`pass` 20; `maneuver`/`moveFighter`/`endTurn`/`toggleDoor`/`setStance`/`resolvePendingEffect` 30 | D04:21; D07:146-170; `backend/src/games/resolvers/game-actions.resolver.ts:258,284,311,338,364,388,414,440,465,488,517` |
| Превышение лимита → ошибка типа 429 (Too Many Requests) от `@nestjs/throttler` | D07:590 |

Клиентская референс-реализация WS (Phaser): `graphql-ws createClient({ url, connectionParams: () => ({ authorization: 'Bearer ' + token }), lazy: true, retryAttempts: 5 })` — `src/lib/apolloClient.ts:16-36`; после refresh токена соединение принудительно закрывается `wsClient.terminate()` и переоткрывается лениво — `src/lib/apolloClient.ts:150-155`.

### 2.2. Конвейер выполнения gameplay-мутации (сервер)

Порядок (`backend/src/games/resolvers/game-actions.resolver.ts`, метод `executeMutation`, строки 141-246; D04:27-41; D07:156):

1. `GqlAuthGuard` → userId из JWT.
2. `GameInProgressGuard` → `game.status == IN_PROGRESS`, иначе `ForbiddenException("Game status is <S>. Required: IN_PROGRESS")` (`backend/src/games/guards/game-status.guard.ts:94-98`).
3. `GamePlayerGuard` → userId ∈ участники, иначе `ForbiddenException("You are not a participant in game <id>")` (`game-player.guard.ts:46`).
4. Фазовый guard (см. таблицу ниже) — `BadRequestException`.
5. `DistributedLockService.withLockOptions("game:<gameId>", ..., { ttl: 10000, retryCount: 1, retryDelay: 100 })` (`game-actions.resolver.ts:148-235`).
6. `loadState` → executor (`GameActionExecutorService.executeXxx`) → при `success: false` — `BadRequestException(result.error)` (`game-actions.resolver.ts:131-137`).
7. `saveState`: optimistic-lock (`existing.sequenceNumber !== state.sequenceNumber - 1` → `ConcurrentModificationException`), upsert в Prisma `GameState`, `Game.version = sequenceNumber`, кэш Redis (TTL 600 с), **публикация `STATE_UPDATED`** (`backend/src/games/game-state.service.ts:170-216`).
8. `attack` → `scheduleAutoResolve(gameId, 30, seq)`; `playDefense`/`resolveCombat` → `cancelAutoResolve` (`game-actions.resolver.ts:173-182`).
9. `publishGameUpdate(gameId, eventType, state)` → PubSub topic `game.updates.<gameId>` + Redis broadcast (`game-actions.resolver.ts:185-189`; `backend/src/games/game-subscription.service.ts:158-176`).
10. Журнал `GameAction` (BullMQ-очередь `game-action`, best-effort) с `metadata: { action: <имя мутации>, input: <dto> }` (`game-actions.resolver.ts:101-129`; `backend/src/games/processors/game-action.processor.ts:27-45`).
11. Если `phase == GAME_OVER` — дополнительно `publishGameUpdate(..., 'GAME_ENDED', state)` и журнал `GAME_ENDED` с `{ winnerId }` (`game-actions.resolver.ts:200-218`).
12. `filterPrivateData(state, userId)` → `GameMutationResult` (`game-actions.resolver.ts:222-227`).
13. Любая иная ошибка → `BadRequestException("Unexpected error during <action>")` (`game-actions.resolver.ts:228-233`).
14. После снятия lock — fire-and-forget `aiTurnService.maybeRunAiTurns(gameId)` (VS_AI) (`game-actions.resolver.ts:238-244`).

**Два PubSub-события на мутацию**: `STATE_UPDATED` (из `saveState`) и специфичный `eventType` (шаг 9). Подписка `gameStateUpdated` фильтрует `eventType === 'STATE_UPDATED'` → ровно одно срабатывание на мутацию (D04:41; `backend/src/games/resolvers/game-subscription.resolver.ts:150-164`).

**Фазовые guard'ы** (`backend/src/games/guards/game-turn.guard.ts`):

| Guard | Разрешённые фазы | Проверка игрока | Кто использует |
|---|---|---|---|
| `ActionPhaseGuard` | `ACTION_MANEUVER`, `ACTION_ATTACK` (`:136-143`) | `currentTurnPlayerId === userId`, иначе `"Not your turn. Current player: <id>"` (`:70-73`) | maneuver, moveFighter, attack, playScheme, endTurn, pass, toggleDoor, setStance (`game-actions.resolver.ts:257,283,310,363,439,464,487,516`) |
| `DefensePlayGuard` | только `COMBAT` (`:169,196-199`) | нужен `metadata.combatInfo`; владелец `combatInfo.attackerId` (боец) → `"Attacker cannot play defense"`; `combatInfo.defenderId !== userId` → `"Only defender can play defense"` (`:203-218`) | playDefense (`:337`) |
| `CombatResolveGuard` | `COMBAT`, `COMBAT_RESOLVE` (`:236,263-266`) | участник боя (владелец атакующего бойца или `defenderId`), иначе `"Only combat participants can resolve combat"` (`:273-281`) | resolveCombat (`:413`) |
| (нет фазового guard'а) | любая | только `GamePlayerGuard` | resolvePendingEffect (`:387`); D07:165 |
| Сообщение при неверной фазе | `"Invalid phase. Current: <P>, Required: <A or B>"` (`:65-67`), `"Invalid phase for defense. Current: <P>, Required: COMBAT"` (`:197-199`), `"Invalid phase for combat resolve. Current: <P>"` (`:264-266`), `"No combat in progress"` (`:205,271`) | | |

### 2.3. Enum-ы

#### 2.3.1. Зарегистрированные в GraphQL-схеме (можно маппить на UENUM напрямую)

| Enum | Значения (точно) | Источник |
|---|---|---|
| `GameMode` | `ONE_V_ONE`, `TWO_V_TWO`, `FREE_FOR_ALL`, `VS_AI` | D04:52; D07:530; `backend/src/games/dto/create-game.dto.ts:9-14` |
| `GameStatus` | `PENDING`, `LOBBY`, `IN_PROGRESS`, `PAUSED`, `FINISHED`, `ABORTED` | D04:53; D07:531; `create-game.dto.ts:16-23` |
| `GamePhase` | `SETUP`, `TURN_START`, `ACTION_MANEUVER`, `ACTION_ATTACK`, `COMBAT`, `COMBAT_RESOLVE`, `TURN_END`, `GAME_OVER` | D04:56-65; D07:532; `backend/src/game-engine/models/game-state.model.ts:15-24` |
| `GameEventType` | `ATTACK_INITIATED`, `DEFENSE_PLAYED`, `COMBAT_RESOLVED`, `TURN_CHANGED`, `PLAYER_JOINED`, `PLAYER_LEFT`, `GAME_ENDED`, `FIGHTER_MOVED`, `DOOR_TOGGLED`, `MANEUVER`, `TURN_ENDED`, `CARD_PLAYED`, `GAME_CREATED`, `GAME_JOINED`, `GAME_STARTED`, `GAME_ABORTED`, `TURN_STARTED`, `PASSED`, `CARD_DISCARDED`, `PLACED`, `EFFECT_APPLIED`, `SPECIAL_ABILITY` (22 значения) | D04:67-73; D07:533; `backend/src/games/dto/gameplay.dto.ts:24-48` |
| `UserRole` | `USER`, `ADMIN`, `MODERATOR` | D07:529 |
| `PaginationOrder` | `ASC` (= `'asc'`), `DESC` (= `'desc'`) — в резолверах не используется | D07:534 |
| `CardType` (**контентный**, content-API) | `ATTACK`=`'attack'`, `DEFENSE`=`'defense'`, `VERSATILE`=`'versatile'`, `SCHEME`=`'scheme'` | D07:535; `backend/src/content/interfaces/card-definition.interface.ts:31-36` |
| `EffectTiming` (**контентный**) | `immediately`, `during_combat`, `after_combat`, `start_of_turn`, `end_of_turn`, `when_played`, `when_attacked`, `when_defending` | D07:536; `card-definition.interface.ts:42-51` |
| `AbilityTrigger` | `start_of_turn`, `during_combat`, `passive`, `when_attacked`, `when_defending`, `end_of_turn` | D07:537; `backend/src/content/interfaces/hero-definition.interface.ts:49-56` |
| `FighterType` (**контентный**) | `HERO`=`'hero'`, `SIDEKICK`=`'sidekick'` | D07:538; `hero-definition.interface.ts:61-64` |
| `Zone` | `blue`, `green`, `yellow`, `red`, `purple`, `brown`, `gray`, `orange`, `pink`, `white`, `gold`, `beige` | D07:539; `backend/src/content/interfaces/board-definition.interface.ts:43-56` |
| `PresenceStatus` | `offline`, `online`, `ingame`, `inqueue` | D07:540 |
| `TimeFrame` | `ALL`=`'all'`, `WEEK`=`'week'`, `MONTH`=`'month'` | D07:541 |

Итого в схеме 13 enum'ов (D07:543). Примечание к enum'ам вида `NAME = 'value'`: в GraphQL-схеме имя члена — `NAME` (код-first NestJS регистрирует ключи TS-enum), а внутреннее значение — строка; в JSON-ответах GraphQL enum отдаётся именем члена (D07:534-541 — «в резолверах не используется»/значения в кавычках даны как TS-значения). Для UE важно: контентные `CardType`/`FighterType` **не совпадают** с engine-значениями в JSON-состоянии (см. 2.3.2).

#### 2.3.2. Строковые «enum'ы» внутри JSON-состояния (НЕ в GraphQL-схеме; парсить как строки → UENUM вручную)

| Поле | Значения | Источник |
|---|---|---|
| `Fighter.type` | `HERO`, `MINION`, `HUGE` | `backend/src/game-engine/models/fighter.model.ts:10-14`; D04:350 |
| `Fighter.attackType` | `melee`, `ranged` (отсутствие/мусор → `melee`) | `fighter.model.ts:56-58,90-104`; D04:355 |
| `FighterEffect.duration` | `permanent`, `turn`, `round` | `fighter.model.ts:27-33` |
| `Card.cardType` (engine) | `ATTACK`, `DEFENSE`, `SCHEME`, `UNIVERSAL`, `VERSATILE`, `MANEUVER` | `backend/src/game-engine/models/card.model.ts:10-19`; D04:374 |
| `CardEffect.type` (`EffectType`) | `MODIFY_ATTACK`, `MODIFY_DEFENSE`, `DAMAGE`, `HEAL`, `MOVE`, `PLACE`, `DRAW_CARD`, `DISCARD`, `MODIFY_VALUE`, `SET_VALUE`, `VALUE_PER_COUNT`, `BOOST`, `CANCEL_EFFECTS`, `OPPONENT_DISCARD`, `RETURN_TO_HAND`, `IMMOBILIZE`, `GAIN_ACTION`, `PREVENT_DAMAGE`, `END_TURN`, `CHOOSE_ONE`, `UNSUPPORTED` | `card.model.ts:153-189` |
| `CardEffect.timing` (engine `EffectTiming`) | `BEFORE_COMBAT`, `DURING_COMBAT`, `AFTER_COMBAT`, `ON_PLAY`, `ON_DISCARD`, `TURN_START`, `TURN_END`, `ON_REVEAL` | `card.model.ts:191-204` |
| `CardEffect.target` (`EffectTarget`) | `ATTACKER`, `DEFENDER`, `SELF`, `ALL_ENEMIES`, `ALL_ALLIES`, `OPPOSING_FIGHTER`, `ENEMIES_ADJACENT_TO_SELF`, `ADJACENT_ENEMY`, `NAMED_FIGHTER`, `OPPONENT_PLAYER` | `card.model.ts:206-226` |
| `CardEffect.when.kind` (`EffectConditionKind`) | `WON_COMBAT`, `LOST_COMBAT`, `IS_ATTACKING`, `IS_DEFENDING`, `ADJACENT_TO_OPPONENT`, `NOT_ADJACENT_TO_OPPONENT`, `DECK_EMPTY`, `HAND_COUNT_AT_MOST`, `HAND_COUNT_AT_LEAST`, `HEALTH_AT_MOST`, `MOVED_THIS_TURN`, `OPPONENT_IS_HERO`, `SHARES_ZONE_WITH_OPPONENT`, `NOT_SHARES_ZONE_WITH_OPPONENT` | `card.model.ts:86-102` |
| `CardEffect.count.source` (`CountSource`) | `FRIENDLY_ADJACENT_TO_OPPONENT`, `CARDS_IN_HAND`, `DISCARD_NAME_PREFIX`, `DAMAGE_DEALT`, `DAMAGE_TAKEN` | `card.model.ts:122-131` |
| `CardEffect.boostSource` (`BoostSource`) | `PLAYER_CHOICE_HAND`, `SELF_DECK_TOP`, `OPPONENT_RANDOM_HAND` | `card.model.ts:142-149` |
| `CardEffect.source` | `parser`, `manual` | `card.model.ts:80` |
| `Cell.type` | `normal`, `wall`, `obstacle`, `door`, `zone-line` | `backend/src/game-engine/models/board.model.ts:24-26` |
| `PendingEffect.type` | `MOVE`, `PLACE`, `CHOOSE_ONE` | `game-state.model.ts:132-139`; D04:259 |
| `GameStateResponse.phase` | строка с именем `GamePhase` (тип поля `String!`) | D07:313; `backend/src/games/models/game.model.ts:83` |
| Prisma `GameActionType` (тип события в `eventsSince`) | `GAME_CREATED`, `GAME_JOINED`, `GAME_STARTED`, `GAME_ENDED`, `GAME_ABORTED`, `TURN_STARTED`, `TURN_ENDED`, `PASSED`, `CARD_PLAYED`, `CARD_DISCARDED`, `FIGHTER_MOVED`, `MANEUVER`, `PLACED`, `ATTACK_INITIATED`, `DEFENSE_PLAYED`, `COMBAT_RESOLVED`, `EFFECT_APPLIED`, `SPECIAL_ABILITY`, `DOOR_TOGGLED` (19; подмножество `GameEventType`) | `backend/prisma/schema.prisma:335-366`; `backend/src/games/models/game-action.model.ts:1-21` |

**Фазы, реально выставляемые продакшен-потоком** (важно для UI-автомата): инициализация при `startGame` → `ACTION_MANEUVER` (`backend/src/games/services/game-initialization.service.ts:241`); `attack` → `COMBAT` (`backend/src/game-engine/services/game-action-executor.service.ts:1108`); `playDefense` → `COMBAT_RESOLVE` (`:1244`); auto-resolve → `COMBAT_RESOLVE` (`backend/src/games/services/combat-timeout.service.ts:265`); `resolveCombat`/`advanceTurn` → `ACTION_MANEUVER` (`:224,1676`); game-over → `GAME_OVER` (`:664`). `SETUP`, `TURN_START`, `TURN_END` встречаются только в легаси-коде (`game-state.service.ts:553`, `game-action-executor.service.ts:702`, `backend/src/game-engine/services/turn-management.service.ts:140,199,234,269`) и в дефолте Prisma `GameState.phase = "SETUP"` (`schema.prisma:284`); `ACTION_ATTACK` — «легаси-фаза для idle-состояний, сохранённых до фикса» (`game-turn.guard.ts:130-134`). Клиент обязан принимать все 8 значений, но основной поток: `ACTION_MANEUVER ↔ COMBAT → COMBAT_RESOLVE → ACTION_MANEUVER … → GAME_OVER`.

### 2.4. Скаляры

| Скаляр | Поведение | Источник |
|---|---|---|
| `DateTime` | Выход: **epoch-миллисекунды** (`Date.getTime()`), строки конвертируются через `new Date(str).getTime()`; вход: число (`parseValue`) или литерал `Int`; иначе `GraphQLError` | D07:551; `backend/src/graphql/scalars/date-time.scalar.ts:9-25` |
| `JSON` | pass-through; зарегистрирован, но в игровых DTO не используется (структуры едут `String`-ами) | D07:552 |
| `Int`/`Float` | TS `number` без явного `() => Int` → **`Float`** | D07:553 |
| `ID` | `GameResponse.id`, `GamePlayerResponse.id`, `GameStateResponse.id` (`@Field()` над `string` даёт `String!` в сгенерированной схеме — см. `src/gql/graphql.ts:549-559`, `:500-510`, где `id: Scalars['String']`) | D07:309-313 (говорит `ID!`) — **РАСХОЖДЕНИЕ** с генерацией, см. §4 |

Поля, которые в реальной схеме **`Float`** (по `src/gql/graphql.ts`, сгенерированному из живой схемы):
- `gameStateUpdated(since: Float)` — `src/gql/graphql.ts:1522-1526`; фронтовая операция объявляет `$since: Float` (`src/graphql/subscriptions/game.graphql:3`); в коде `@Args('since', { nullable: true }) since?: number` без `type` (`game-subscription.resolver.ts:173`). **D07:231 говорит `Int` — РАСХОЖДЕНИЕ.**
- `eventsSince(sinceSequence: Float!)` — `src/gql/graphql.ts:1278-1281`; `@Args('sinceSequence', { type: () => Number })` (`backend/src/games/game.resolver.ts:225`); D04:136 (`Float!`) — совпадает.
- `gameSequence: Float` — `src/gql/graphql.ts:1148`; `@Query(() => Number)` (`game.resolver.ts:212`); D07:61 — совпадает.
- `availableGames(mode: String, limit: Float)` — `game.resolver.ts:51-56`; D04:103.
- `GameStateResponse.sequenceNumber: Float!`, `turnCount: Float!` — `src/gql/graphql.ts:549-559`; `@Field() sequenceNumber: number` (`backend/src/games/models/game.model.ts:76-86`). **D07:313 говорит `Int!` — РАСХОЖДЕНИЕ.**
- `GamePlayerResponse.seatOrder: Float!` — `src/gql/graphql.ts:500-510`; `game-player.model.ts:26-27`. **D07:311 говорит `Int!` — РАСХОЖДЕНИЕ.**
- `GameResponse.version: Float!` — `src/gql/graphql.ts:512-533`; `game.model.ts:52-53`. **D07:309 говорит `Int!` — РАСХОЖДЕНИЕ.**
- `GameFiltersDto.limit/offset: Float` — D07:453; `backend/src/games/dto/game-filters.dto.ts:17-27`.

Поля, которые действительно **`Int`**: `GameMutationResult.sequenceNumber/turnCount`, `GameState.sequenceNumber/turnCount`, `GameEvent.sequenceNumber`, `EventsSinceResponse.lastSequence`, `TurnState.turnCount`, `GameStatePlayer.health/maxHealth`, `HandZone.maxSize`, `GameResponse.currentTurn`, все `x/y` и `optionIndex` в input-DTO (`gameplay.dto.ts:63-79,244-281,313-334,380-458,461-495`; `src/gql/graphql.ts:468-476,378-384,406-413,535-547`).

### 2.5. Queries (игровые)

| Query | Аргументы | Возврат | Auth | Примечания | Источник |
|---|---|---|---|---|---|
| `game` | `id: String!` | `GameResponse` (nullable) | JWT | `checkGameAccess` — участники (или публичные/завершённые); данные из Prisma `Game`, не engine | D04:82-94; D07:56; `game.resolver.ts:27-35` |
| `myGames` | `filters: GameFiltersDto` | `[GameResponse!]!` | JWT | | D04:99-101; D07:57; `game.resolver.ts:39-46` |
| `availableGames` | `mode: String`, `limit: Float` | `[GameResponse!]!` | **публичный** (guard отсутствует) | | D04:103-105; D07:58; `game.resolver.ts:51-57` |
| `gameState` | `gameId: String!` | `GameStateResponse` (nullable) | JWT | `requireParticipation`; `id = "<gameId>-state"`; `state = JSON.stringify(filterPrivateData(state, userId))`; `updatedAt = metadata.lastActionAt` | D04:110-127; D07:59; `game.resolver.ts:63-87` |
| `gameSequence` | `gameId: String!` | `Float` (nullable) | JWT | из Prisma `GameState.sequenceNumber`, 0 если нет | D04:129-131; D07:61; `game.resolver.ts:212-216`; `game-state.service.ts:633-640` |
| `eventsSince` | `gameId: String!`, `sinceSequence: Float!` | `EventsSinceResponse` (nullable) | JWT | `checkGameAccess`; ≤100 событий `sequenceNumber > since` по возрастанию; `lastSequence` = seq последнего или `sinceSequence`; `hasMore = events.length >= 100` | D04:133-146; D07:62; `game.resolver.ts:221-238`; `game-state.service.ts:710-733` |
| `heroStances` | `heroSlug: String!` | `[StanceOptionDto!]!` | **публичный** (`@Public()`) | из `ABILITY_CONFIGS.find(c => c.heroId === heroSlug).stances`; `[]` если нет | D04:148-155; D07:60; `game.resolver.ts:100-108` |
| Контент: `heroes`, `heroesPaginated`, `hero(id)`, `cards(heroId)`, `card(id)`, `boards`, `boardsPaginated`, `board(id)`, `contentVersion`, `sets`, `heroesBySet(set)`, `contentSummary`, `clearContentCache` | | | публичные | `hero(id)`/`board(id)` — по **slug** | D04:157-159; D07:36-50 |

**`GameResponse`** (D07:309; `backend/src/games/models/game.model.ts:6-63`; `src/gql/graphql.ts:512-533`): `id: String!`, `code: String`, `status: GameStatus!`, `mode: GameMode!`, `hostId: String!`, `host: GamePlayerResponse!`, `opponentId: String`, `opponent: GamePlayerResponse`, `boardId: String!`, `boardState: String`, `createdAt: DateTime!`, `updatedAt: DateTime!`, `startedAt: DateTime`, `endedAt: DateTime`, `winnerId: String`, `version: Float!`, `players: [GamePlayerResponse!]!`, `phase: GamePhase` (nullable), `currentTurn: Int` (nullable).

**`GamePlayerResponse`** (D07:311; `game-player.model.ts:4-28`): `id: String!`, `userId: String!`, `username: String!`, `avatar: String`, `heroId: String`, `isReady: Boolean!`, `hasPassed: Boolean!`, `seatOrder: Float!`.

**`GameStateResponse`** (D07:313; `game.model.ts:66-90`; `src/gql/graphql.ts:549-559`): `id: String!`, `gameId: String!`, `state: String!`, `sequenceNumber: Float!`, `currentTurnPlayerId: String`, `phase: String!`, `turnCount: Float!`, `updatedAt: DateTime!`.

**`EventsSinceResponse`** (D07:339; `gameplay.dto.ts:569-582`): `gameId: String!`, `events: [GameEvent!]!`, `lastSequence: Int!`, `hasMore: Boolean!`.

**`StanceOptionDto`** (D07:337; `gameplay.dto.ts:362-375`): `id: String!`, `label: String!`, `isDefault: Boolean!`. Известные стойки: `alice` → `big` (default, «Big»), `small` («Small»); `muhammad-ali` → `float` (default, «Float Like a Butterfly», `attackRange: 2`), `sting` («Sting Like a Bee») — `backend/src/game-engine/abilities/ability-config.ts:850-893`. `heroSlug` = `slugifyHeroName(hero.name)` — нижний регистр, не-alnum → `-` (`fighter.model.ts:80-85`); слаг есть в `Fighter.heroSlug`.

**Payload `eventsSince.events[].payload`** — JSON-строка объекта `{ "action": "<имя мутации>", "input": <dto как отправлен> }` (`game-actions.resolver.ts:117-121`, `game-state.service.ts:730`), для `GAME_ENDED` — `{ "action": "<мутация>", "input": { "winnerId": ... } }` (`game-actions.resolver.ts:207-218`). `type` — Prisma `GameActionType`. Поле `playerId` сервис возвращает, но GraphQL-тип `GameEvent` его не содержит (`game-state.service.ts:725-732` vs `gameplay.dto.ts:395-413`). Запись в журнал асинхронная (BullMQ, 3 попытки, backoff 1 с) — `backend/src/games/services/game-action.service.ts:18-49` → eventual consistency.

**Фронтовые операции** (готовы к копированию в UE): `src/graphql/queries/game.graphql:1-113` (`GetGame`, `MyGames`, `AvailableGames`, `GetGameState`, `GetGameSequence`, `EventsSince`), контент `:115-207`.

### 2.6. Лоббийные мутации (для полноты)

| Мутация | Аргументы | Возврат | Источник |
|---|---|---|---|
| `createGame` | `input: CreateGameDto!` (`mode: GameMode`, `boardId: String` — оба optional), `idempotencyKey: String` | `GameResponse!` | D04:169; D07:146,449; `create-game.dto.ts:41-51`; `game.resolver.ts:114-123` |
| `joinGame` | `input: JoinGameDto!` (`gameId: String!` — cuid, `@IsNotEmpty`; `heroId: String`; `asOpponent: Boolean`) | `GameResponse!` | D04:170; D07:147,451; `join-game.dto.ts:4-21` |
| `leaveGame` | `gameId: String!` | `Boolean!` | D04:171; D07:148 |
| `startGame` | `gameId: String!` | `GameResponse!`; инициализирует engine-состояние | D04:172; D07:149 |
| `abortGame` | `gameId: String!` | `GameResponse!` | D04:173; D07:150 |
| `toggleReady` | `gameId: String!` | `GameResponse!` | D04:174; D07:151 |
| `selectHero` | `gameId: String!`, `heroId: String!` | `GameResponse!` | D04:175; D07:152 |

Операции: `src/graphql/mutations/game.graphql:1-72`.

### 2.7. Gameplay-мутации и input-DTO

Общее: все `gameId` — `@IsNotEmpty` (D07:457); все optional-поля — `@Field(..., { nullable: true }) + @IsOptional()` (D07:436). Каждая мутация — `mutation X($input: XDto!) { x(input: $input) { state sequenceNumber phase currentTurnPlayerId turnCount timestamp } }` (`src/graphql/mutations/game.graphql:76-206`).

| Мутация | Input | Guard | Тратит действие | `eventType` | Переход фазы | Источник |
|---|---|---|---|---|---|---|
| `maneuver` | `ManeuverDto` | ActionPhase | да (`consumeAction`) | `MANEUVER` | не меняет (или авто-`advanceTurn` при 0 действий) | D04:192-205; D07:160; `game-action-executor.service.ts:745-893` |
| `moveFighter` | `MoveFighterDto` | ActionPhase | да | `FIGHTER_MOVED` | не меняет | D04:207-211; D07:161; `:895-970` |
| `attack` | `AttackDto` | ActionPhase | да (списывается при объявлении: `actionsRemaining = max(0, n-1)`) | `ATTACK_INITIATED` (+ таймер 30 с) | → `COMBAT` | D04:213-225; D07:162; `:972-1148,1108-1118` |
| `playDefense` | `PlayDefenseDto` | DefensePlay | нет | `DEFENSE_PLAYED` (отменяет таймер) | → `COMBAT_RESOLVE` | D04:227-233; D07:163; `:1150-1284,1244` |
| `resolveCombat` | `ResolveCombatDto` | CombatResolve | нет (остаток уже списан атакой) | `COMBAT_RESOLVED` (отменяет таймер) | → `ACTION_MANEUVER` (если у атакующего остались действия) / `advanceTurn` / `GAME_OVER` | D04:235-241; D07:166; `:1394-1728,1640-1690` |
| `playScheme` | `PlaySchemeDto` | ActionPhase | да | `CARD_PLAYED` | не меняет | D04:243-249; D07:164; `:1286-1392` |
| `resolvePendingEffect` | `ResolvePendingEffectDto` | **нет фазового** | **нет** | `CARD_PLAYED` | не меняет | D04:251-261; D07:165; `:432-640` |
| `endTurn` | `EndTurnDto` | ActionPhase | — (передаёт ход) | `TURN_ENDED` (триггерит `turnChanged`) | `advanceTurn` → `ACTION_MANEUVER` следующего | D04:263-266; D07:167; `:1730-1768` |
| `pass` | `PassDto` | ActionPhase | да | `CARD_PLAYED` (журнал: `PASSED` — но см. §4) | не меняет | D04:263-267; D07:168; `:1772-1823` |
| `toggleDoor` | `ToggleDoorDto` | ActionPhase | **нет** (см. §4) | `DOOR_TOGGLED` | не меняет | D04:263-268; D07:169; `:1827-1896` |
| `setStance` | `SetStanceDto` | ActionPhase | **нет** | `SPECIAL_ABILITY` | не меняет | D04:271-277; D07:170; `:1898-1955` |

Экономика хода: ровно `ACTIONS_PER_TURN = 2` действия (`game-state.model.ts:165`), счётчик `metadata.actionsRemaining`, чтение через `getActionsRemaining` (мусор/отсутствие → 2; `:172-175`). `consumeAction`: при остатке 0 — авто-`advanceTurn` **без** дополнительного инкремента seq (`game-action-executor.service.ts:680-690`). `advanceTurn`: добор 1 карты следующему игроку, снятие эффектов `duration: 'turn'`, снапшот `turnStartPositions`, `phase = ACTION_MANEUVER`, `turnCount + 1` (если игрок сменился), `actionsRemaining = 2`, сброс `maneuveredThisTurn/attackedThisTurn/lostCombatThisTurn`, очистка `pendingEffects` владельца, которому возвращается ход, затем `onTurnStart`-хуки способностей (`:200-260`).

#### 2.7.1. `PositionInput` (`gameplay.dto.ts:62-79`; D07:459)
| Поле | GraphQL | Обяз. | Валидация |
|---|---|---|---|
| `x` | `Int!` | да | `@IsInt @Min(0) @Max(19)` |
| `y` | `Int!` | да | `@IsInt @Min(0) @Max(19)` |

#### 2.7.2. `ManeuverMoveInput` (`gameplay.dto.ts:81-93`; D07:461)
| Поле | GraphQL | Обяз. | Валидация |
|---|---|---|---|
| `fighterId` | `String!` | да | `@IsNotEmpty @IsString` |
| `path` | `[PositionInput!]!` | да | `@IsArray @ValidateNested({each:true})` |

#### 2.7.3. `ManeuverDto` (`gameplay.dto.ts:95-140`; D04:196-205; D07:463)
| Поле | GraphQL | Обяз. | Валидация / семантика |
|---|---|---|---|
| `gameId` | `String!` | да | `@IsNotEmpty` |
| `moves` | `[ManeuverMoveInput!]` | нет* | движение нескольких бойцов одним манёвром; каждый боец — не более одного раза (`"Каждый боец двигается в манёвре не более одного раза"`, executor `:773`); ходы применяются последовательно |
| `boostCardId` | `String` | нет | сброс карты из руки → `+boostValue` к очкам движения **каждого** бойца; карта должна быть в руке (`"Boost card not in hand"`, validator `:328`) |
| `fighterId` | `String` | нет | **deprecated** legacy-одиночный режим |
| `cardId` | `String` | нет | **deprecated**; без `boostCardId` трактуется как boost-карта (`executor :753`) |
| `path` | `[PositionInput!]` | нет | **deprecated** (с `fighterId`) |

\* Нужно либо `moves[]`, либо `fighterId + path`, иначе `"Манёвр без ходов: задай moves[] или fighterId+path"` (`:768`). Семантика: манёвр = добор 1 карты (после движения; `drawCards(…,1)`, `:868-873`) + движение всех своих бойцов; манёвр без карты валиден (`:751-754`). Валидация пути: соседние клетки, длина ≤ `movement (+boost)` — `"Путь длиной N превышает очки движения бойца (M)"`, `"Шаг (a,b)→(c,d) не является ходом на соседнюю клетку"`, `"Клетка (x, y) занята"`, `"Боец обездвижен до конца хода (эффект карты)"` (`backend/src/game-engine/validators/game-rules.validator.ts:278-372`; executor `:808`).

#### 2.7.4. `MoveFighterDto` (`gameplay.dto.ts:142-167`; D07:465)
| Поле | GraphQL | Обяз. | Валидация |
|---|---|---|---|
| `gameId` | `String!` | да | `@IsNotEmpty` |
| `fighterId` | `String!` | да | `@IsNotEmpty @IsString` |
| `x`, `y` | `Int!` | да | `@IsInt @Min(0) @Max(19)` |

Ошибки: `"Fighter not found"`, `"Not your fighter"`, `"Fighter is defeated"`, `"Invalid target position"`, `"Недостаточно очков движения: до клетки (x, y) не добраться за N шаг(ов) по проходимым клеткам"` (`game-rules.validator.ts:374-436`). Не добирает карту (`executor :895-970`).

#### 2.7.5. `AttackDto` (`gameplay.dto.ts:169-201`; D04:216-222; D07:467)
| Поле | GraphQL | Обяз. | Валидация / семантика |
|---|---|---|---|
| `gameId` | `String!` | да | `@IsNotEmpty` |
| `attackerId` | `String!` | да | id **бойца**-атакующего (из `fighters`), должен принадлежать игроку (`"Not your attacker"`, validator `:160`) |
| `cardId` | `String!` | да | карта из руки: принимается и instance-`id` (`<cardId>::n`), и базовый `cardId` (`findHandCard`, executor `:1963-1967`); тип `ATTACK`/`VERSATILE` (`"Картой типа X нельзя атаковать"`, validator `:203`); `bannerName` (`"Карту с банером «B» может играть только этот боец (играет F)"`, `:581`) |
| `targetId` | `String!` | да | id бойца-цели; дальность: `melee` — смежная клетка, `ranged` — пересечение зон (`"Target out of range"`, `:123`) |
| `boostCardId` | `String` | нет | сброс карты → `+boostValue` к атаке; не та же карта (`"Нельзя BOOST-ить атаку той же картой"`, executor `:1076`), должна быть в руке (`:1072`) |

Результат: карты (сыгранная и boost) уходят в сброс **сразу** (`:1089-1093`); `metadata.combatInfo = { attackerId: dto.attackerId (боец), defenderId: target.ownerId (userId), targetFighterId: target.id, attackerCardId, attackValue: attackValue + boost, defenseValue: 0, startedAt: now }` — **без `timeoutAt`** (`:1096-1104`); `phase = COMBAT`; `actionsRemaining - 1` (`:1108-1118`). Сервер планирует auto-resolve через 30 с (`game-actions.resolver.ts:173-178`; `combat-timeout.service.ts:59`).

#### 2.7.6. `PlayDefenseDto` (`gameplay.dto.ts:202-222`; D07:469)
| Поле | GraphQL | Обяз. | Валидация |
|---|---|---|---|
| `gameId` | `String!` | да | `@IsNotEmpty` |
| `cardId` | `String!` | да | `DEFENSE`/`VERSATILE`/`UNIVERSAL` (`"Card must be DEFENSE, VERSATILE or UNIVERSAL"`, validator `:460`), в руке (`"Card not in hand"`, `:448`), banner |
| `boostCardId` | `String` | нет | `+boostValue` к защите; не та же карта (`executor :1214-1217`) |

Только защитник (`combatInfo.defenderId === userId`), фаза `COMBAT`; переводит в `COMBAT_RESOLVE`, пишет `combatInfo.defenderCardId/defenseValue` (`executor :1150-1284`). Отменяет таймер.

#### 2.7.7. `ResolveCombatDto` — `{ gameId: String! }` (`gameplay.dto.ts:282-289`; D07:475)
Фазы `COMBAT`/`COMBAT_RESOLVE`, участник боя. Пайплайн: `ON_REVEAL` → `DURING_COMBAT` → модификаторы способностей героев → сравнение `finalAttack > finalDefense` (ничья — за защитником) → урон → `AFTER_COMBAT` (WON/LOST) → game-over-проверка (`executor :1394-1700`). Далее: `GAME_OVER` (+`winnerId`, `combatInfo` очищен) или остаток действий > 0 → `ACTION_MANEUVER` тому же игроку, иначе `advanceTurn` (`:1640-1690`). `combatInfo` очищается.

#### 2.7.8. `PlaySchemeDto` — `{ gameId: String!, cardId: String! }` (`gameplay.dto.ts:224-242`; D07:471)
Карта должна быть `SCHEME` (`"Card is not a SCHEME card (got X)"`, `executor :1305`), в руке (`"Card not found in hand"`, `:1298`), banner (`:1318-1326`). Авто-эффекты best-effort; эффекты с выбором (MOVE/PLACE/CHOOSE_ONE) → `metadata.pendingEffects` (D04:249). Карта всегда уходит в сброс; тратит действие (`:1341-1365`).

#### 2.7.9. `ResolvePendingEffectDto` (`gameplay.dto.ts:243-281`; D04:254-261; D07:473)
| Поле | GraphQL | Обяз. | Валидация / семантика |
|---|---|---|---|
| `gameId` | `String!` | да | `@IsNotEmpty` |
| `effectId` | `String!` | да | `id` из `metadata.pendingEffects[]` (`"Отложенный эффект не найден (протух или уже резолвлен)"`, `executor :449`; `"Этот выбор принадлежит другому игроку"`, `:452`) |
| `fighterId` | `String` | для MOVE/PLACE | `"MOVE/PLACE требует fighterId, x, y"` (`:462`); `"Боец не найден или повержен"` (`:467`); `"Эффект двигает не этого бойца"` (`:473`) |
| `x`, `y` | `Int` | для MOVE/PLACE | `@IsInt @Min(0)` (без `@Max`); `"Клетка вне доски"`/`"Клетка непроходима"`/`"Клетка занята"` (`:491-501`) |
| `optionIndex` | `Int` | для CHOOSE_ONE | `@IsInt @Min(0)`; индекс из `pending.options[].index` |

Не тратит действие; без фазового guard'а (доступен и в `COMBAT` — см. §4).

#### 2.7.10. `EndTurnDto` / `PassDto` — `{ gameId: String! }` (`gameplay.dto.ts:292-310`; D07:475)
`endTurn`: валидатор разрешает фазы `ACTION_MANEUVER`/`ACTION_ATTACK`/`TURN_END` (`"Cannot end turn in current phase"`, `game-rules.validator.ts:471-491`), **требования «≥1 манёвр» в коде нет** (см. §4); вызывает `advanceTurn` (`executor :1747`).
`pass`: `passCount + 1`, `consumeAction` (`executor :1790-1803`); фактического сброса карты нет (TODO `:1787-1788`).

#### 2.7.11. `ToggleDoorDto` — `{ gameId: String!, x: Int!, y: Int! }` (0..19) (`gameplay.dto.ts:312-334`; D07:477)
Требует наличия ключа `"<x>:<y>"` в `boardState.doors` (`"No door at (x, y)"`, validator `:546`); переключает `doors["x:y"]`; **не вызывает `consumeAction`** (`executor :1827-1896`).

#### 2.7.12. `SetStanceDto` — `{ gameId: String!, stanceId: String! }` (`gameplay.dto.ts:336-355`; D04:274; D07:479)
Ошибки: `"У игрока нет героя на доске"`, `"У этого героя нет стоек"`, `"Неизвестная стойка «X» (доступны: a, b)"` (`executor :1910-1920`). Эффект: `metadata.heroStances[userId] = stanceId`, seq +1, действие не тратится (`:1922-1934`). Доступно только текущему игроку в action-фазах (ActionPhaseGuard).

### 2.8. `GameMutationResult` (единый ответ)

| Поле | GraphQL | Значение | Источник |
|---|---|---|---|
| `state` | `String` (nullable) | `JSON.stringify(filterPrivateData(newState, userId))` — на практике всегда не null | `game-actions.resolver.ts:72-80,222-227`; D04:181-190; D07:321 |
| `sequenceNumber` | `Int!` | новый seq | |
| `timestamp` | `DateTime!` | `new Date()` момента ответа → **epoch-ms число** | `game-actions.resolver.ts:76`; `date-time.scalar.ts:13-16` |
| `phase` | `GamePhase!` | | |
| `currentTurnPlayerId` | `String` (nullable) | | |
| `turnCount` | `Int!` | | |

Сгенерированный тип: `src/gql/graphql.ts:468-476`.

### 2.9. Полная структура `GameState` (JSON в `state` и в полях подписки)

Внутренний тип — `backend/src/game-engine/models/game-state.model.ts:30-53` (D04:322). В JSON попадает **engine-форма** (не компактная `SerializedGameState` с ключами `g/s/p/...` — та используется только для хранения в БД, `game-state.service.ts:44-146,274-489`). Все объекты `readonly` — клиент получает снимок.

#### 2.9.1. Корень (`game-state.model.ts:30-53`)
| Поле | Тип JSON | Описание | Источник |
|---|---|---|---|
| `gameId` | string | cuid игры | |
| `sequenceNumber` | number (int) | монотонный счётчик; старт 1 | `game-initialization.service.ts:240` |
| `phase` | string (`GamePhase`) | | |
| `turnCount` | number | старт 1 | `:242` |
| `currentTurnPlayerId` | string | userId | |
| `players` | `GameStatePlayer[]` | | |
| `fighters` | `Fighter[]` | все бойцы (включая поверженных, `isDefeated`) | |
| `decks` | `Record<userId, DeckState>` | **отсутствует в подписке** | `game-subscription.resolver.ts:53-63` |
| `discardPiles` | `Record<userId, Card[]>` | **отсутствует в подписке** | там же |
| `handZones` | `Record<userId, HandZone>` | | |
| `boardState` | `BoardState` | | |
| `metadata` | `GameStateMetadata` | | |

#### 2.9.2. `GameStatePlayer` (`game-state.model.ts:60-67`; D04:332-341)
| Поле | Тип | Примечание |
|---|---|---|
| `userId` | string | |
| `heroId` | string | Prisma cuid героя (не slug) |
| `health` | number | HP героя на старте = `hero.health` (`game-initialization.service.ts:230-231`) |
| `maxHealth` | number | |
| `fighterIds` | string[] | `[heroFighterId, ...sidekickIds]` (`:232`) |
| `isAlive` | boolean | |

#### 2.9.3. `Fighter` (`fighter.model.ts:38-62`; D04:343-361)
| Поле | Тип | Обяз. | Примечание |
|---|---|---|---|
| `id` | string | да | формат при инициализации: герой `f-<seat>-hero`, сайдкик `f-<seat>-sk<i>` (`game-initialization.service.ts:140,154`) |
| `ownerId` | string | да | userId |
| `heroId` | string | да | Prisma cuid |
| `name` | string | да | |
| `type` | `'HERO'|'MINION'|'HUGE'` | да | сайдкики → `MINION` (`:157`) |
| `health`, `maxHealth` | number | да | |
| `position` | `{ x: number, y: number }` | да | |
| `effects` | `FighterEffect[]` | да | `{ type: string, value?: number, duration?: 'permanent'|'turn'|'round', expiresAt?: number, source?: string }` (`fighter.model.ts:27-33`) |
| `hasSidekick` | boolean | да | |
| `sidekickIds` | string[] | нет | |
| `isDefeated` | boolean | нет | |
| `movement` | number | нет | дефолт 2 при отсутствии/мусоре (`:65-73`) |
| `attackType` | `'melee'|'ranged'` | нет | дефолт `melee` (`:96-104`) |
| `heroSlug` | string | нет | ключ для `heroStances(heroSlug)` и реестра способностей |

#### 2.9.4. `Card` / `HandCard` (`card.model.ts:25-48,282-284`; D04:372-379)
| Поле | Тип | Обяз. | Примечание |
|---|---|---|---|
| `id` | string | да | **instance id** `"<prismaCardId>::<copy>"` (`game-initialization.service.ts:197`) — именно его слать в `cardId`/`boostCardId` |
| `cardId` | string | да | Prisma id карты (для картинок/справочника контента) |
| `name`, `nameEn`, `nameRu` | string | да | у чужих карт: `"???"`, `"Hidden"`, `"Скрыто"` |
| `cardType` | engine `CardType` | да | `ATTACK|DEFENSE|SCHEME|UNIVERSAL|VERSATILE|MANEUVER` |
| `attackValue`, `defenseValue`, `boostValue` | number | нет | у чужих карт удалены |
| `effects` | `CardEffect[]` | нет | у чужих удалены |
| `text` | string | нет | у чужих удалён |
| `bannerName` | string | нет | `'Any'`/пусто — любой боец, иначе имя бойца |
| `isVisible` (только `HandCard`) | boolean | да | у чужих `false`; у своих — `false` при стартовой раздаче (`game-initialization.service.ts:218`), `true` после добора (`deck-management.service.ts:98-101`) — **не использовать как признак «своя карта»** |

`CardEffect` (`card.model.ts:50-84`): `id: string`, `type: EffectType`, `timing: EffectTiming`, `target?: EffectTarget`, `value?: number`, `condition?: string` (legacy), `when?: { kind: EffectConditionKind, value?: number }`, `count?: { source: CountSource, namePrefix?: string, per?: number }`, `optional?: boolean`, `fighterName?: string`, `boostSource?: BoostSource`, `blind?: boolean`, `options?: { label: string, effects: CardEffect[] }[]`, `chooseCount?: number`, `text?: string`, `source?: 'parser'|'manual'`, `parserVersion?: number`.

#### 2.9.5. `DeckState` / `HandZone` (`card.model.ts:289-301`; D04:363-367)
| Тип | Поля |
|---|---|
| `DeckState` | `cards: Card[]` (полный список колоды), `drawPile: Card[]` (**полные объекты карт**, не только id — `game-initialization.service.ts:219-224`; D04:364 говорит «id карт, рубашки» — **РАСХОЖДЕНИЕ**), `topCard?: Card` (у чужой колоды удалён) |
| `HandZone` | `cards: HandCard[]`, `maxSize: number` (= 7 при инициализации, `game-initialization.service.ts:40,227`; D04:371 показывает 10 — **РАСХОЖДЕНИЕ**) |

Стартовая рука — 5 карт (`:39,215-218`). Добор при полной руке пропускается (`deck-management.service.ts:73-77`); при пустой колоде сброс перетасовывается в колоду (`:216-240`).

#### 2.9.6. `BoardState` / `Cell` (`board.model.ts:12-39`; D04:386-392,423)
| Поле | Тип | Примечание |
|---|---|---|
| `width`, `height` | number | из `Board.cells` БД, иначе fallback 20×20 (`game-initialization.service.ts:43,277-300`; на момент кода «у всех досок cells=[]» — `:284-288`) |
| `cells` | `Cell[][]` | индексация **`cells[y][x]`** (`:320-327`) |
| `Cell.type` | `'normal'|'wall'|'obstacle'|'door'|'zone-line'` | из БД: `isObstacle ? 'obstacle' : 'normal'` (`:330`) |
| `Cell.x`, `Cell.y` | number | |
| `Cell.zones` | string[] (нет) | 1–2 зоны; ranged/зонные эффекты — по пересечению (`board.model.ts:29-32`; D04:423) |
| `Cell.zone` | string (нет) | deprecated, первая зона |
| `Cell.isOpen`, `Cell.isHighGround` | boolean (нет) | |
| `doors` | `Record<string, boolean>` | ключ **`"<x>:<y>"`** (`executor :1849`; `board.model.ts:110-112`); D04:389 показывает `"door-1"` — **РАСХОЖДЕНИЕ** |
| `fog` | `Record<string, boolean>` | записей в коде не найдено — всегда `{}` |
| `tokens` | `Record<string, any>` | записей в коде не найдено — всегда `{}` |

Стартовые позиции по `seatOrder`: `(2,2)`, `(w-3,h-3)`, `(w-3,2)`, `(2,h-3)` с поиском ближайшей свободной клетки; сайдкики — со смещениями вокруг героя (`game-initialization.service.ts:47-53,367-380`).

#### 2.9.7. `GameStateMetadata` (`game-state.model.ts:90-130`; D04:394-419)
| Поле | Тип JSON | Обяз. | Примечание |
|---|---|---|---|
| `lastActionAt` | string (ISO 8601) | да | `Date` → `JSON.stringify` → ISO |
| `lastActionBy` | string | да | userId или `"system"` |
| `version` | number | да | |
| `compressed` | boolean | нет | |
| `combatInfo` | `CombatState` | нет | живёт между `attack` и `resolveCombat`/game-over |
| `passCount` | number | нет | |
| `winnerId` | string | нет | при `GAME_OVER` |
| `actionsRemaining` | number | нет | отсутствие → трактовать как 2 |
| `turnStartPositions` | `Record<fighterId, {x,y}>` | нет | |
| `pendingEffects` | `PendingEffect[]` | нет | |
| `maneuveredThisTurn`, `attackedThisTurn`, `lostCombatThisTurn` | boolean | нет | отсутствие → false |
| `heroStances` | `Record<userId, stanceId>` | нет | отсутствие → стойка по умолчанию из `heroStances(heroSlug)` |

#### 2.9.8. `CombatState` (engine, в JSON) (`game-state.model.ts:73-84`)
| Поле | Тип | Обяз. | Значение |
|---|---|---|---|
| `attackerId` | string | да | **id бойца**-атакующего (`executor :1096-1097`; `game-state.service.ts:104`; `src/lib/gameStateAdapter.ts:82`) |
| `defenderId` | string | да | **userId** защитника (`target.ownerId`) |
| `targetFighterId` | string | нет | id атакованного бойца (легаси-сейвы без поля → первый боец защитника) |
| `attackerCardId` | string | да | instance id |
| `defenderCardId` | string | нет | появляется после `playDefense` |
| `attackValue` | number | да | значение карты + boost (до модификаторов) |
| `defenseValue` | number | да | 0 до защиты |
| `startedAt` | string (ISO) | да | |
| `timeoutAt` | string (ISO) | нет | **в коде никогда не выставляется** (grep по `backend/src` — записей нет) |

**Важно:** GraphQL-тип `CombatState` (`attackerId`, `targetId`, `attackCardId`, `defenseCardId`, `timeoutAt: DateTime!` — D07:335; `gameplay.dto.ts:416-432`) зарегистрирован в схеме, но ни одним резолвером не возвращается; форма в JSON — engine-форма выше.

#### 2.9.9. `PendingEffect` (`game-state.model.ts:132-163`; D04:412-414)
| Поле | Тип | Обяз. | Примечание |
|---|---|---|---|
| `id` | string | да | → `effectId` |
| `type` | `'MOVE'|'PLACE'|'CHOOSE_ONE'` | да | |
| `playerId` | string | да | чей выбор |
| `value` | number | нет | дистанция для MOVE |
| `fighterName` | string | нет | ограничение бойца |
| `targetsOpponent` | boolean | нет | двигается боец противника |
| `text` | string | нет | исходный текст |
| `options` | `{ index: number, label: string }[]` | нет | CHOOSE_ONE |
| `chooseCount` | number | нет | default 1 |
| `optionEffects` | `CardEffect[][]` | нет | параллельно `options` |
| `card` | `Card` | нет | карта-источник |

Нерезолвленные эффекты протухают при возврате хода их владельцу (`executor :243-245`).

### 2.10. Фильтрация приватных данных (`game-state.service.ts:494-538`; D04:425-432; D07:59,231)

- Рука **чужого** игрока: каждая карта → `{ ...card, id, cardType, name: '???', nameEn: 'Hidden', nameRu: 'Скрыто', attackValue/defenseValue/boostValue/effects/text: undefined (в JSON — отсутствуют), isVisible: false }` — `bannerName` **не** удаляется (`:503-524`).
- `decks[<чужой>].topCard` → удалён (`:528-534`); `cards`/`drawPile` чужой колоды **не** фильтруются (в JSON остаются полные объекты карт, включая порядок `drawPile` — см. §4).
- `discardPiles` не фильтруются (комментарий `:490` обещает, код — нет).
- Своя рука/колода — полностью.
- Применяется: в `gameState` (`game.resolver.ts:76`), в каждом ответе мутации (`game-actions.resolver.ts:222`), в каждой доставке `gameStateUpdated` — по JWT подписчика, аргумент `userId` игнорируется (`game-subscription.resolver.ts:47-51,174-177`).

### 2.11. JSON-строковые поля и двухфазный парсинг

| Место | Что приходит | Как парсить | Источник |
|---|---|---|---|
| `gameState.state`, `<мутация>.state` | одна JSON-строка полного `GameState` (с `decks`, `discardPiles`) | GraphQL-парсинг ответа → затем `JSON.parse(state)` | D04:117,127; `src/lib/gameStateAdapter.ts:9-12,171-173` |
| `gameStateUpdated.{players,fighters,handZones,boardState,metadata}` | пять JSON-строк (`JSON.stringify` каждого поля отфильтрованного состояния); `decks`/`discardPiles` **отсутствуют** | парсить каждое поле отдельно; `decks`/`discardPiles` мержить из последнего полного снапшота | `game-subscription.resolver.ts:53-63`; `src/lib/gameStateAdapter.ts:13-15,176-199` |
| `GameEvent.payload` | JSON-строка `{ phase, turnCount, currentTurnPlayerId }` (или `null`); для лобби-событий — компактный объект без `phase`, отдаётся как есть | `JSON.parse` при ненулевом | `game-subscription.resolver.ts:80-100`; D04:490 |
| `eventsSince.events[].payload` | JSON-строка `{ action, input }` | `JSON.parse` | `game-state.service.ts:730` |
| `GameResponse.boardState` | `String` nullable (лоббийное поле из Prisma) | не нужно для игры | D07:309 |
| Даты внутри JSON-состояния | ISO-строки (`metadata.lastActionAt`, `combatInfo.startedAt`) | парсить ISO 8601 | `JSON.stringify(Date)` |
| Даты в GraphQL-полях `DateTime` | epoch-ms число | int64/double | `date-time.scalar.ts:13-16` |

Референс-контракт wire-типов на клиенте: `src/lib/gameStateAdapter.ts:36-135` (`WireFighter`, `WireCard`, `WirePlayer`, `WireCombatInfo`, `WireGameState`, `WirePendingEffect`).

### 2.12. Subscriptions

Все игровые — JWT (`GqlAuthGuard`), graphql-ws, фильтр по `gameId` в variables (D04:438; D07:225). Резолвер: `backend/src/games/resolvers/game-subscription.resolver.ts`.

| Подписка | Аргументы | Payload-тип | Фильтр | Источник |
|---|---|---|---|---|
| `gameStateUpdated` | `gameId: String!`, `since: Float` (nullable), `userId: String` (nullable, **игнорируется**) | `GameState!` | `payload.gameId === gameId && eventType === 'STATE_UPDATED' && (since == null \|\| sequenceNumber > since)` | `:150-179`; D04:440-457; D07:231 |
| `attackInitiated` | `gameId: String!` | `GameEvent!` | `eventType === ATTACK_INITIATED` | `:181-199`; D07:232 |
| `defensePlayed` | `gameId: String!` | `GameEvent!` | `DEFENSE_PLAYED` | `:201-219`; D07:233 |
| `combatResolved` | `gameId: String!` | `GameEvent!` | `COMBAT_RESOLVED` | `:221-239`; D07:234 |
| `turnChanged` | `gameId: String!` | `TurnState!` | `TURN_ENDED` или `TURN_CHANGED` (`TURN_CHANGED` никто не публикует) | `:241-263`; D04:500-508; D07:235 |
| `playerJoined` | `gameId: String!` | `GameEvent!` | `PLAYER_JOINED` — **в игре не публикуется** | `:265-286`; D04:510-512; D07:236 |
| `playerLeft` | `gameId: String!` | `GameEvent!` | `PLAYER_LEFT` — не публикуется | `:288-305`; D07:237 |
| `gameEnded` | `gameId: String!` | `GameEvent!` | `GAME_ENDED` (публикуется при `phase === GAME_OVER` из `executeMutation` и из ИИ-хода) | `:307-325`; `game-actions.resolver.ts:200-205`; `ai-turn.service.ts:82-83`; D07:238 |
| `matchFound` | `userId: String!` | `MatchFoundResponse!` | без guard; `player1Id/player2Id === userId` | D07:246 |
| `presenceUpdated` | `userIds: [String]` | `Presence!` | без guard | D07:252 |

**`GameState` (GraphQL, payload `gameStateUpdated`)** (`gameplay.dto.ts:461-495`; D07:323; `src/gql/graphql.ts:535-547`): `gameId: String!`, `sequenceNumber: Int!`, `phase: GamePhase!`, `turnCount: Int!`, `currentTurnPlayerId: String!` (non-null), `players: String`, `fighters: String`, `handZones: String`, `boardState: String`, `metadata: String` (nullable по схеме, на практике всегда строки).

**`GameEvent`** (`gameplay.dto.ts:395-413`; D07:333): `type: GameEventType!`, `gameId: String!`, `sequenceNumber: Int!`, `timestamp: DateTime!` (epoch-ms; из `Date.now()` публикации), `payload: String` (nullable).

**`TurnState`** (`gameplay.dto.ts:380-392`; D07:331): `playerId: String!` (= **следующий** игрок, `currentTurnPlayerId` нового состояния), `turnCount: Int!`, `phase: GamePhase!` (`game-subscription.resolver.ts:105-122`).

Нерелевантные, но присутствующие в схеме типы: `GameStatePlayer`, `Fighter` (с `position: String`, `effects: [String!]`), `HandZone`, `CombatState` — резолверами не возвращаются (`gameplay.dto.ts:497-566`; D07:325-329,335).

Публикация из ИИ-хода (VS_AI): `saveState` (→ `STATE_UPDATED`) + `publishGameUpdate(eventType)` + при `GAME_OVER` `GAME_ENDED`; журнал не пишется (`backend/src/games/services/ai-turn.service.ts:79-84`). Публикация из auto-resolve: только `saveState` → `STATE_UPDATED` (`combat-timeout.service.ts:233`).

Протокол graphql-ws (D04:516): `connection_init { payload: connectionParams }` → `connection_ack`; `subscribe { id, payload: { query, variables, operationName } }`; сообщения `next { id, payload: { data, errors } }`, `error { id, payload: [GraphQLError] }`, `complete { id }`; `ping`/`pong`. Фронтовые операции: `src/graphql/subscriptions/game.graphql:1-93`.

### 2.13. Протокол синхронизации (seq / since / gap / eventsSince)

Семантика `sequenceNumber`:
- Инициализация `startGame` → `1` (`game-initialization.service.ts:240`).
- Каждая успешная gameplay-мутация → ровно `+1`, даже если внутри произошёл авто-`advanceTurn` (`consumeAction` с `incrementSeq=false`, `executor :680-690`; комментарии `:822-828,1652-1660`).
- `saveState` отвергает состояние, если `existing.sequenceNumber !== new - 1` (`game-state.service.ts:176-181`) → нумерация без дыр на сервере.
- Auto-resolve (через 30 с после `attack`, если фаза всё ещё `COMBAT` и seq не изменился) → `+1`, `phase = COMBAT_RESOLVE` (`combat-timeout.service.ts:205-240,260-277`).
- Ход ИИ (VS_AI): по `+1` на каждое действие бота, асинхронно после ответа на мутацию человека (`ai-turn.service.ts:14-20,79-80`; D04:533).

Рекомендуемый алгоритм (D04:522-534, реализация `src/phaser/network/SubscriptionHandler.ts` и `src/phaser/hooks/useGameSync.ts`):
1. Вход: `query gameState` → `JSON.parse(state)`, `lastSeq = sequenceNumber` (`useGameSync.ts:289-340`).
2. Подписки: `gameStateUpdated(gameId, since: lastSeq)` + событийные (`SubscriptionHandler.ts:183-193`).
3. На каждое обновление: `seq <= lastSeq` → пропустить; `seq > lastSeq + 1` → gap (в Phaser-клиенте только `console.warn` + TODO — `SubscriptionHandler.ts:335-350`); иначе применить (`JSON.parse` пяти полей).
4. Свой ход: ответ мутации содержит `state` и `sequenceNumber` — применять сразу; подписка продублирует тот же seq → дедупликация по номеру обязательна (D04:530).
5. Атака оппонента: `attackInitiated` + `gameStateUpdated` с `phase: COMBAT` → таймер защиты 30 с от `combatInfo.startedAt` (поскольку `timeoutAt` не выставляется — см. §4) (D04:531).
6. Реконнект WS: экспоненциальный backoff (`delay = 1000 * 2^(n-1)`, максимум 5 попыток — `SubscriptionHandler.ts:97-101,486-508`), затем `since: lastSeq`; при большой дыре — `eventsSince` и/или полный `gameState` (D04:532).
7. Ограничение `eventsSince` как средства догоняния: события содержат только `{action, input}` (без состояния), не включают ходы ИИ и auto-resolve, пишутся асинхронно → **единственный надёжный способ закрыть gap — повторный `query gameState`** (см. §3, §4).

### 2.14. Формат ошибок

`formatError` (`graphql.module.ts:60-102`; D07:557-575):
- Не-production: `{ message, code: extensions.code || 'INTERNAL_SERVER_ERROR', path, locations, extensions }` — обратить внимание: `code` продублирован **на верхнем уровне** объекта ошибки.
- Production: бизнес-ошибки (`extensions.code ∈ {BAD_USER_INPUT, GRAPHQL_VALIDATION_FAILED}` или `message` содержит `not found`/`unauthorized`) → `{ message, code, path }`; всё остальное → `{ message: 'Internal server error', code: 'INTERNAL_SERVER_ERROR' }`.
- Ответ GraphQL: `{ "errors": [ ... ], "data": null }` (D04:315).

Коды (D07:577-587): `UNAUTHENTICATED` (401, нет/просрочен JWT), `FORBIDDEN` (403: не участник, статус игры не `IN_PROGRESS`, temp-ban), `NOT_FOUND` (404), `BAD_USER_INPUT` (400: провал игрового действия, валидация DTO, `Unexpected error during <action>`), `CONFLICT` (409, optimistic concurrency), `GRAPHQL_VALIDATION_FAILED`, `INTERNAL_SERVER_ERROR`. Ошибки Throttler — 429-типа (D07:590); complexity — `"Query is too complex: N. Maximum allowed complexity is 1000."` (D07:591).

Каталог сообщений движка, которые увидит клиент в `errors[0].message` (все → `BadRequestException`): см. 2.2 (guard'ы) и 2.7 (по мутациям); дополнительно `"Not your turn"`, `"Player is not in game"` (`game-rules.validator.ts:219-227`), `"Fighter not found"`, `"Not your fighter"`, `"Fighter is defeated"`, `"Hand not found"`, `"Card not in hand"`, `"Attacker not found"`, `"Target not found"`, `"Attacker is dead"`, `"Target is dead"`, `"Target out of range"`, `"Attacker or target not found"` (`executor :1005`), `"Not in combat phase"` (`:1159,1405`), `"Combat participants not found"` (`:1426`). Часть сообщений на русском (см. 2.7) — UI должен показывать `message` как есть либо маппить по подстроке.

### 2.15. Начальное состояние после `startGame` (что увидит клиент первым)

`backend/src/games/services/game-initialization.service.ts:83-256`: минимум 2 игрока с выбранным `heroId` и картами в БД; `phase = ACTION_MANEUVER`, `turnCount = 1`, `sequenceNumber = 1`, `currentTurnPlayerId = players[seatOrder 0].userId` (хост), `metadata = { lastActionAt, lastActionBy: 'system', version: 1, actionsRemaining: 2 }`; бойцы `f-<seat>-hero` (+ `f-<seat>-sk<i>`, `type: MINION`, HP из `hero.sidekicks`), `heroSlug`, `movement` (дефолт 2), `attackType` из `Hero.properties.attackType`; колода — карты героя, развёрнутые по `count` (instance id `<cardId>::<copy>`), перетасованы; рука 5, `maxSize` 7; `topCard = drawPile[0]`; `discardPiles[userId] = []`; доска из `Board.cells` или пустая 20×20.

---

## 3. Следствия для UE-клиента (требования и ограничения)

1. **Два GraphQL-транспорта**: HTTP POST для queries/mutations (`FHttpModule`) и WebSocket graphql-ws для подписок (`FWebSocketsModule`, сабпротокол `graphql-transport-ws`); токен — в `Authorization: Bearer` и в `connection_init.payload.authorization`. При refresh токена — закрыть WS и переподключиться, затем переподписаться с `since` (`src/lib/apolloClient.ts:150-155`).
2. **USTRUCT для GraphQL-обёрток** (парсятся из ответа GraphQL): `FGameMutationResult` (`state: FString`, `sequenceNumber: int32`, `timestamp: int64` epoch-ms, `phase: EGamePhase`, `currentTurnPlayerId: FString` nullable, `turnCount: int32`); `FGameStateResponse` (`sequenceNumber`/`turnCount` приходят как `Float` — парсить как double → int32; `phase: FString`, не enum); `FGameStateSubscriptionPayload` (пять `FString` JSON); `FGameEvent`; `FTurnState`; `FEventsSinceResponse`; `FStanceOption`; `FGameResponse`/`FGamePlayerResponse` (`version`/`seatOrder` — Float).
3. **USTRUCT для JSON-состояния** (второй парсинг через `FJsonObjectConverter` или ручной `FJsonObject`): `FGameState`, `FGameStatePlayer`, `FFighter`, `FFighterEffect`, `FPosition`, `FCard`/`FHandCard`, `FCardEffect` (+ `FEffectCondition`, `FCountSpec`, `FChooseOption` — рекурсивный `effects`), `FDeckState`, `FHandZone`, `FBoardState`, `FCell`, `FGameStateMetadata`, `FCombatState`, `FPendingEffect`. Опциональные поля (`movement`, `attackType`, `heroSlug`, `combatInfo`, `timeoutAt`, `actionsRemaining`, …) — моделировать как «отсутствует» (`TOptional`/флаг), а не как значение по умолчанию, и применять серверные дефолты: `movement→2`, `attackType→melee`, `actionsRemaining→2`, флаги `*ThisTurn→false`, `heroStances→isDefault`-стойка.
4. **UENUM**: `EGamePhase` (8), `EGameEventType` (22), `EGameMode` (4), `EGameStatus` (6) — по GraphQL-именам; плюс JSON-строковые: `EFighterType` (HERO/MINION/HUGE), `EAttackType`, `ECardTypeEngine` (6), `EEffectType` (21), `EEffectTimingEngine` (8), `EEffectTarget` (10), `EEffectConditionKind` (14), `ECellType` (5), `EPendingEffectType` (3). Парсер обязан быть толерантным к неизвестным строкам (в `EffectType` есть `UNSUPPORTED`; новые значения возможны).
5. **Не смешивать контентные и engine enum'ы**: контентный `CardType` (`attack/defense/versatile/scheme`) и `FighterType` (`hero/sidekick`) относятся к справочнику `heroes/cards/boards`; в состоянии игры — `ATTACK/…/MANEUVER` и `HERO/MINION/HUGE`. Связка состояния со справочником: `HandCard.cardId` ↔ `Card.id` (контент), `Fighter.heroId` ↔ `Hero.id`, `Fighter.heroSlug` ↔ `heroStances(heroSlug)`.
6. **Модель состояния на клиенте — «последний полный снапшот + патчи»**: подписка не несёт `decks`/`discardPiles`; хранить их из последнего `gameState`/ответа мутации и не затирать при апдейтах подписки (как `remoteGameStore` во фронте — `src/lib/gameStateAdapter.ts:13-15`). Размер колоды/сброса можно показывать по последнему известному значению, а при необходимости точности — перечитывать `gameState` после своих действий (ответ мутации содержит их всегда).
7. **Дедупликация и gap-детект по `sequenceNumber` обязательны**: ответ мутации и `gameStateUpdated` приносят один и тот же seq; события ИИ и auto-resolve приходят только через подписку; при `seq > last+1` — надёжный путь восстановления: `query gameState` (а не `eventsSince`, которое не даёт состояния и не содержит ходов ИИ/auto-resolve).
8. **Таймер защиты**: считать дедлайн как `combatInfo.startedAt + 30 с` (поле `timeoutAt` не приходит). Учитывать, что после срабатывания серверного таймера фаза станет `COMBAT_RESOLVE` без нанесения урона и без события `combatResolved`; чтобы бой действительно завершился, один из участников должен вызвать `resolveCombat` (UE-клиенту атакующего стоит делать это автоматически при `phase == COMBAT_RESOLVE && combatInfo != null`).
9. **Экран боя**: `attackerId` в `combatInfo` — это **боец**, `defenderId` — **userId**; цель — `targetFighterId` (fallback: первый боец `defenderId`). Роль локального игрока: защитник, если `combatInfo.defenderId == myUserId`; в `COMBAT` защитник может `playDefense`, оба участника — `resolveCombat`.
10. **Идентификаторы карт**: в мутации слать `HandCard.id` (instance `<cardId>::n`); сервер принимает и базовый `cardId`, но при нескольких копиях это неоднозначно — использовать instance id.
11. **Доступность действий в UI** (без запроса к серверу): текущий игрок (`currentTurnPlayerId == me`), фаза ∈ {`ACTION_MANEUVER`, `ACTION_ATTACK`}, `actionsRemaining > 0` для maneuver/moveFighter/attack/playScheme/pass; `endTurn`/`setStance`/`toggleDoor` — без проверки остатка; `resolvePendingEffect` — если есть `pendingEffects` с `playerId == me`. Любая мутация может быть отклонена → откат к последнему снапшоту и показ `errors[0].message`.
12. **Даты**: два формата — epoch-ms (int64) в GraphQL-полях `DateTime` и ISO-строки внутри JSON-состояния. Не полагаться на `GameEvent.timestamp` для дедлайнов (это время публикации).
13. **Приватность на клиенте**: чужие карты приходят обезличенными (`name: "???"`, без значений) — рендерить рубашки; `bannerName` у чужих карт остаётся (мелкая утечка, не использовать в UI). Свою руку определять по ключу `handZones[myUserId]`, а не по `isVisible`.
14. **Ошибки**: читать `errors[0].message` и `errors[0].code` (верхний уровень) / `errors[0].extensions.code`; в production сообщение может быть заменено на `"Internal server error"` (см. §4, п. 9) — UI должен иметь общий фолбэк «Ход отклонён».
15. **Rate limits**: не слать мутации чаще лимитов (20–30/мин); при 429 — не ретраить автоматически, показать ошибку.
16. **Схема без файла**: для генерации кода/валидации операций получить SDL через introspection с живого сервера (или из `src/gql/graphql.ts`), а не из документации — D07 содержит неточности по скалярам.
17. **Доска**: рендер геометрии брать из `boardState` (`cells[y][x]`, `width/height`), поскольку в игре может использоваться fallback 20×20, не совпадающий с `Board.spaces` контента; ключи дверей — `"x:y"`.
18. **Подписки `playerJoined`/`playerLeft`/`turnChanged(TURN_CHANGED)`** в игре фактически молчат — состав игроков брать из `players` в состоянии и из `game(id).players` (лобби).

---

## 4. Открытые вопросы / несоответствия

1. **`since` и другие скаляры `Float` vs `Int`.** D07:231 указывает `since: Int`, D07:313/311/309 — `Int!` для `GameStateResponse.sequenceNumber/turnCount`, `GamePlayerResponse.seatOrder`, `GameResponse.version`. Код и сгенерированная схема (`src/gql/graphql.ts:1522-1526,549-559,500-510,512-533`; `game-subscription.resolver.ts:173`; `game.model.ts:77,86`; `game-player.model.ts:27`) дают `Float`. Также D07:309-313 пишет `id: ID!`, а генерация — `String!`. **Верить коду/генерации.** Рекомендация: снять introspection перед кодогенерацией в UE.
2. **`combatInfo.timeoutAt` никогда не выставляется.** D04:406,414,531 обещают `timeoutAt` как дедлайн auto-resolve; grep по `backend/src` находит запись `timeoutAt` только в моделях/сериализации (`game-state.model.ts:82`, `game-state.service.ts:114,371,470`). `executeAttack` пишет только `startedAt` (`executor :1096-1104`). Клиент должен считать `startedAt + 30 с`.
3. **Auto-resolve не разрешает бой.** `performAutoResolve` лишь ставит `phase = COMBAT_RESOLVE` и `+1` к seq (TODO — `combat-timeout.service.ts:260-277`); публикуется только `STATE_UPDATED`, без `COMBAT_RESOLVED` и без журнала. D04:225,531,547 («бой разрешается автоматически») неточны. Кто и когда вызовет `resolveCombat` после таймаута — решение клиента/продукта (открытый вопрос дизайна).
4. **`pass` не сбрасывает карту.** D04:267 и D07:168 описывают «сброс верхней карты + доп. действие»; в коде — только `passCount + 1` и списание действия (`executor :1786-1803`, TODO `:1787`). Также журнал пишет `CARD_PLAYED`, а не `PASSED` (`game-actions.resolver.ts:463-481`; D04:565 говорит «журнал: PASSED» — не подтверждено кодом: `recordGameAction` использует тот же `eventType`).
5. **`toggleDoor` не тратит действие и не проверяет `actionsRemaining`.** D04:543 включает `toggleDoor` в список проверяющих `actionsRemaining > 0`; `executeToggleDoor`/`validateToggleDoor` этого не делают (`executor :1827-1896`; `game-rules.validator.ts:519-550`).
6. **`endTurn` «после ≥1 манёвра»** (D04:266) — в коде такого требования нет (`validateEndTurn`, `game-rules.validator.ts:471-491`): ход можно завершить сразу.
7. **`combatInfo.attackerId` в примере D04:399 — `"user-1"`** (userId), тогда как код и пример D04:301 — id бойца (`executor :1096-1097`; `DefensePlayGuard` ищет `fighters.find(f => f.id === combatInfo.attackerId)`, `game-turn.guard.ts:208-213`). Верно: **id бойца**.
8. **Примеры структуры в D04:363-392 неточны**: `drawPile` — полные объекты карт, не id (`game-initialization.service.ts:219-224`); `maxSize` = 7, не 10 (`:40`); ключ двери `"x:y"`, не `"door-1"` (`executor :1849`); `fog`/`tokens` всегда `{}` (записей не найдено). Формат `timestamp` в примерах D04:306,496 — ISO-строка, фактически — epoch-ms число (`date-time.scalar.ts:13-16`).
9. **Код ошибки игровых мутаций.** D04:315 показывает `extensions.code: "BAD_REQUEST"`, D07:172,584 — `BAD_USER_INPUT`. Реальное значение `extensions.code` для `BadRequestException` под Apollo 4 в этом проекте в исследованных файлах не подтверждено (не найдено). Критично для production: `formatError` пропускает бизнес-ошибку только при `BAD_USER_INPUT`/`GRAPHQL_VALIDATION_FAILED` или подстроках `not found`/`unauthorized` (`graphql.module.ts:71-83`); если код окажется иным, сообщения движка (`"Not your turn"` и т.п.) в prod превратятся в `"Internal server error"`. Требуется живая проверка на сервере.
10. **Журнал `eventsSince` неполон**: ходы ИИ (`ai-turn.service.ts:79-84`) и auto-resolve (`combat-timeout.service.ts:233`) не пишут `GameAction`; запись асинхронная (BullMQ). `payload` = `{action,input}` без состояния → полноценный replay/catch-up на клиенте невозможен; D04:528 (использовать `eventsSince` для догоняния) — только как индикатор, восстановление — через `gameState`.
11. **Утечка информации через `decks`/`discardPiles`**: фильтр удаляет только `topCard` чужой колоды (`game-state.service.ts:528-534`), но `decks[<чужой>].drawPile` (полный упорядоченный список) и `cards` остаются в `state` (в подписке `decks` не передаются). Комментарий `:490` («скрывает содержимое сброса соперника») коду не соответствует (сброс в Unmatched открыт — это не баг правил, но `drawPile` — утечка). UE-клиент не должен показывать чужой `drawPile`; вопрос к бэкенду.
12. **`resolvePendingEffect` без фазового guard'а** (D07:165; `game-actions.resolver.ts:387`) может изменить seq во время `COMBAT`, что заставит auto-resolve пропустить срабатывание (`combat-timeout.service.ts:220-227`: `state.sequenceNumber > attackSequenceNumber` → skip). Edge-case; на клиенте желательно не предлагать pending-выборы в `COMBAT`.
13. **Легаси-поля `ManeuverDto` (`fighterId`, `cardId`, `path`)** остаются в схеме; UE использовать только `moves[]` + `boostCardId`. Фронтовый `GameActions.maneuver` всё ещё шлёт legacy-формат (`src/phaser/network/GameActions.ts:112-125`) — не копировать.
14. **`GameStateResponse.phase: String!`** (не enum) и `GameState.currentTurnPlayerId: String!` (non-null в подписке) vs nullable в `GameMutationResult` — разнотипность одного и того же поля в трёх типах (`game.model.ts:83`; `gameplay.dto.ts:475-476,450-451`).
15. **Фазы `SETUP`/`TURN_START`/`TURN_END`**: в продакшен-потоке не выставляются (см. 2.3.2), но Prisma-дефолт `GameState.phase = "SETUP"` (`schema.prisma:284`) и `turn-management.service.ts` могут их выдать в неизвестных путях — клиент должен их принимать без падения. Нужно ли UE поддерживать «размещение бойцов» (`SETUP`, событие `PLACED`) — в API мутации размещения нет (не найдено).
16. **`GameResponse.phase/currentTurn`** — лоббийные поля Prisma `Game`; не найдено, где они обновляются по ходу игры (`saveState` обновляет только `Game.version`, `game-state.service.ts:203-207`). Считать их ненадёжными для геймплея.
17. **Подписка `gameStateUpdated` требует наличия `req.user`** в контексте; при невалидном токене в `connectionParams` guard отклонит `subscribe` (сообщение `error` в graphql-ws), а не `connection_init` — поведение на уровне транспорта не проверялось (открытый вопрос для UE-реализации reconnect-логики).
18. **`heroStances` только для 2 героев** (`alice`, `muhammad-ali`) на момент исследования (`ability-config.ts:850-893`); список может расти — кэшировать по `heroSlug` с инвалидацией по `contentVersion`.

---

## 5. Источники

Документация:
- `docs/backend-api/04-game-api.md` (D04) — транспорт (9-21), конвейер (25-45), enum (49-76), queries (80-159), mutations (163-316), GameState (320-433), subscriptions (436-517), синхронизация (520-534), валидация (537-549), шпаргалка событий (553-570).
- `docs/backend-api/07-graphql-schema-reference.md` (D07) — Query (30-125), Mutation (129-219), Subscription (223-254), Object-типы (258-430), Input-типы (434-521), Enum (525-543), скаляры (547-553), ошибки (557-593).

Бэкенд (сверка):
- `backend/src/game-engine/models/game-state.model.ts` (GamePhase 15-24; GameState 30-53; GameStatePlayer 60-67; CombatState 73-84; GameStateMetadata 90-130; PendingEffect 132-163; ACTIONS_PER_TURN 165; getActionsRemaining 172-175).
- `backend/src/game-engine/models/fighter.model.ts` (FighterType 10-14; Position 19-22; FighterEffect 27-33; Fighter 38-62; DEFAULT_FIGHTER_MOVEMENT 65; slugifyHeroName 80-85; AttackType 90-104).
- `backend/src/game-engine/models/card.model.ts` (CardType 10-19; Card 25-48; CardEffect 50-84; EffectConditionKind 86-102; ChooseOption 114-117; CountSource 122-131; BoostSource 142-149; EffectType 153-189; EffectTiming 191-204; EffectTarget 206-226; HandCard 282-284; DeckState 289-293; HandZone 298-301).
- `backend/src/game-engine/models/board.model.ts` (BoardState 12-20; Cell 24-35; getCellZones 41-45; createEmptyBoardState 82-105; cellKey 110-112).
- `backend/src/games/dto/gameplay.dto.ts` (GameEventType 24-53; PositionInput 62-79; ManeuverMoveInput 81-93; ManeuverDto 95-140; MoveFighterDto 142-167; AttackDto 169-201; PlayDefenseDto 202-222; PlaySchemeDto 224-242; ResolvePendingEffectDto 243-281; ResolveCombatDto 282-289; EndTurnDto 292-299; PassDto 302-310; ToggleDoorDto 312-334; SetStanceDto 336-355; StanceOptionDto 362-375; TurnState 380-392; GameEvent 395-413; CombatState 416-432; GameMutationResult 437-458; GameState 461-495; GameStatePlayer 497-518; Fighter 521-554; HandZone 557-566; EventsSinceResponse 569-582).
- `backend/src/games/dto/create-game.dto.ts` (GameMode 9-14; GameStatus 16-23; CreateGameDto 41-51), `join-game.dto.ts` (4-21), `game-filters.dto.ts` (7-28).
- `backend/src/games/models/game.model.ts` (GameResponse 6-63; GameStateResponse 66-90), `game-player.model.ts` (4-28), `game-action.model.ts` (GameActionType 1-21).
- `backend/src/games/resolvers/game-actions.resolver.ts` (createMutationResult 72-80; recordGameAction 101-129; executeMutation 141-246; мутации 256-535).
- `backend/src/games/resolvers/game-subscription.resolver.ts` (resolveGameState 43-63; resolveGameEvent 65-102; resolveTurnState 104-122; подписки 150-325).
- `backend/src/games/game.resolver.ts` (game 27-35; myGames 39-46; availableGames 51-57; gameState 63-87; heroStances 100-108; gameSequence 212-216; eventsSince 221-238).
- `backend/src/games/game-state.service.ts` (SerializedGameState 44-146; saveState 170-216; loadState 222-240; serialize 274-372; deserialize 378-489; filterPrivateData 494-538; createInitialState 542-587; getSequenceNumber 633-640; getEventsSince 710-733).
- `backend/src/games/game-subscription.service.ts` (GameUpdateEvent 11-20; GamePubSubEvent 27-33; publishGameUpdate 158-176; publishLobbyEvent 182-198; publishToPubSub 205-214; asyncIteratorForGame 220-222).
- `backend/src/games/guards/game-turn.guard.ts` (GameTurnGuard 37-91; ActionPhaseGuard 136-144; CombatPhaseGuard 147-155; DefensePlayGuard 163-222; CombatResolveGuard 230-284), `game-status.guard.ts` (GameInProgressGuard 79-102), `game-player.guard.ts` (11-50).
- `backend/src/games/services/game-initialization.service.ts` (константы 39-53; initializeGameState 83-256; buildBoardState 277-345; computeStartPositions 367-380).
- `backend/src/games/services/combat-timeout.service.ts` (DEFAULT_DEFENSE_TIMEOUT 59; scheduleAutoResolve 90-131; cancelAutoResolve 135-150; processAutoResolve 199-253; performAutoResolve 260-277), `backend/src/games/processors/combat-timeout.processor.ts` (34-63).
- `backend/src/games/services/game-action.service.ts` (recordAction 18-49), `backend/src/games/processors/game-action.processor.ts` (17-48).
- `backend/src/games/services/ai-turn.service.ts` (14-20, 76-84).
- `backend/src/game-engine/services/game-action-executor.service.ts` (advanceTurn 168-260; checkAndApplyGameOver 657-671; consumeAction 680-690; executeManeuver 745-893; executeMoveFighter 895-970; executeAttack 972-1148; executePlayDefense 1150-1284; executePlayScheme 1286-1392; executeResolveCombat 1394-1728; executeEndTurn 1730-1768; executePass 1772-1823; executeToggleDoor 1827-1896; executeSetStance 1898-1955; findHandCard 1963-1967).
- `backend/src/game-engine/validators/game-rules.validator.ts` (validateAttackWithParams 135-215; canPlayerAct 219-227; validateManeuver 278-372; validateMovement 374-436; validateDefense 440-466; validateEndTurn 471-491; validatePass 496-515; validateToggleDoor 519-550; validateBanner 559-585).
- `backend/src/game-engine/services/deck-management.service.ts` (drawCards 53-115; recycleDeck 216-245).
- `backend/src/game-engine/abilities/ability-config.ts` (alice 850-874; muhammad-ali 884-905).
- `backend/src/graphql/graphql.module.ts` (конфиг 14-35; validationRules 38-58; formatError 60-102), `backend/src/graphql/scalars/date-time.scalar.ts` (5-27).
- `backend/src/content/interfaces/card-definition.interface.ts` (CardType 31-36; EffectTiming 42-51), `hero-definition.interface.ts` (AbilityTrigger 49-56; FighterType 61-64), `board-definition.interface.ts` (Zone 43-56).
- `backend/prisma/schema.prisma` (GameState 271-290; GameActionType 335-366; GameAction 368-390).

Фронтенд (референс-клиент):
- `src/graphql/queries/game.graphql` (1-207), `src/graphql/mutations/game.graphql` (1-206), `src/graphql/subscriptions/game.graphql` (1-93).
- `src/gql/graphql.ts` (сгенерированные типы: EventsSinceResponse 378; GameEvent 406; GameMutationResult 468; GamePlayerResponse 500; GameResponse 512; GameState 535; GameStateResponse 549; QueryEventsSinceArgs 1278; gameSequence 1148; StanceOptionDto 1480; SubscriptionGameStateUpdatedArgs 1522; TurnState 1566).
- `src/lib/apolloClient.ts` (WS-клиент 16-36; reconnectWebSocket 150-155), `src/lib/gameStateAdapter.ts` (wire-типы 36-135; parseWireState 171-173; parseSubscriptionState 176-199).
- `src/phaser/network/SubscriptionHandler.ts` (реконнект 97-101, 486-508; since 183-193; gap 335-350), `src/phaser/hooks/useGameSync.ts`, `src/phaser/network/GameActions.ts` (112-125), `src/phaser/state/GameStateBridge.ts` (570-610).
