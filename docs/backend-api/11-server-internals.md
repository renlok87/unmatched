# 11. Серверные внутренности (Server Internals)

Исчерпывающая документация внутренних механизмов бэкенда, критичных для клиента: жизненный цикл игры, персистентность состояния, распределённые локи, публикация событий, BullMQ-джобы, матчмейкинг, presence, реконнект-протокол, rate limits и аудит.

Все пути — от корня `backend/src/`.

---

## Содержание

1. [Жизненный цикл игры](#1-жизненный-цикл-игры)
2. [Персистентность состояния](#2-персистентность-состояния)
3. [Распределённые локи](#3-распределённые-локи)
4. [sequenceNumber](#4-sequencenumber)
5. [Публикация событий (PubSub)](#5-публикация-событий-pubsub)
6. [BullMQ-очереди и джобы](#6-bullmq-очереди-и-джобы)
7. [Матчмейкинг](#7-матчмейкинг)
8. [Presence](#8-presence)
9. [Реконнект-протокол](#9-реконнект-протокол)
10. [Rate limits](#10-rate-limits)
11. [Аудит-логи](#11-аудит-логи)
12. [Кеш-ключи Redis (сводка)](#12-кеш-ключи-redis-сводка)

---

## 1. Жизненный цикл игры

Ключевые классы: `GameService` (`games/game.service.ts`), `GameInitializationService` (`games/services/game-initialization.service.ts`), `GameStateService` (`games/game-state.service.ts`), `MatchConfirmationService` (`matchmaking/services/match-confirmation.service.ts`), `MatchmakingSchedulerService` (`matchmaking/services/matchmaking-scheduler.service.ts`).

### Статусы (Prisma enum `GameStatus`)

```
PENDING → LOBBY → IN_PROGRESS → FINISHED / ABORTED
```

### Два пути создания игры

**A. Лобби (явное):** мутация `createGame` → статус `LOBBY` сразу, код приглашения из 6 символов (алфавит без `I O 0 1`), хост становится `GamePlayer` с `seatOrder: 0`. Поддерживается `idempotencyKey` (уникальность по паре ключ+хост — повторный вызов возвращает уже созданную игру).

**B. Матчмейкинг:** планировщик создаёт игру в статусе `PENDING` (модель `Game` с `hostId`/`opponentId`, `boardId` = первая доска в БД), затем двухфазное подтверждение. При accept обоих — `MatchConfirmationService.startGame()` переводит в `LOBBY` + `startedAt`. При decline/timeout — `ABORTED`.

### startGame (лобби-путь)

`GameService.startGame(gameId, userId)` — только хост, только из `LOBBY`, все игроки `isReady`. Для `VS_AI` автоматически добавляется системный бот (`ai@unmached.local`, сидируется через `prisma/seed-ai.ts`) вторым игроком с сильнейшим по health героем и `isReady: true`.

Порядок:
1. `game.status = IN_PROGRESS`, `startedAt = now` (Prisma-обновление).
2. `GameInitializationService.initializeGameState(gameId)` — строит `GameState`: геометрия доски из `Board.cells` (fallback — пустая сетка 20×20), бойцы (герой `f-<seat>-hero` + sidekicks `f-<seat>-sk<i>`, реальные HP из БД, стартовые углы доски + поиск свободной клетки), колоды из карт героя (развёрнутые по `count`, перетасованные Fisher–Yates), стартовая рука 5 карт (макс. рука 7), фаза `ACTION_MANEUVER`, первым ходит хост, `actionsRemaining = ACTIONS_PER_TURN` (2 действия/ход), `sequenceNumber = 1`.
3. При ошибке инициализации статус **откатывается** в `LOBBY` (`startedAt: null`) — лобби остаётся рабочим.
4. Инвалидация кеша (`game:<id>`, `games:list:<userId>:*`, `games:available:*`).
5. Журналирование `GAME_STARTED` (seq 1) через `GameActionService`.

### Игровой цикл (IN_PROGRESS)

Все игровые мутации идут через `GameActionsResolver.executeMutation()` (`games/resolvers/game-actions.resolver.ts`):

```
GqlAuthGuard → GameInProgressGuard → GamePlayerGuard → фазовый guard
  → DistributedLockService.withLockOptions('game:<gameId>')
  → loadState → GameActionExecutorService.execute*
  → saveState (optimistic lock!) → (auto-resolve таймер при атаке)
  → publishGameUpdate(eventType) → recordAction (журнал)
  → [phase === GAME_OVER → publishGameUpdate('GAME_ENDED') + журнал]
  → filterPrivateData → возврат клиенту
```

Фазовые guards: `ActionPhaseGuard` (ACTION_MANEUVER / ACTION_ATTACK), `CombatPhaseGuard`, `DefensePlayGuard`, `CombatResolveGuard` (`games/guards/`).

Для `VS_AI`: после хода человека fire-and-forget запускается `AiTurnService.maybeRunAiTurns()` (`games/services/ai-turn.service.ts`) — до 40 шагов бота (load → decide → execute → save → publish), каждый шаг под локом `game:<id>`.

### Конец игры

- **GAME_OVER**: когда `GameActionExecutorService` переводит `phase === GAME_OVER`, резолвер дополнительно публикует событие `GAME_ENDED` и пишет действие `GAME_ENDED` с `winnerId` в журнал.
- **ABORTED**: `abortGame` (или `leaveGame` во время `IN_PROGRESS` с reason `player_left`) — статус `ABORTED`, `endedAt`, публикация лобби-события `GAME_ENDED` (компактный payload `{reason, abortedBy}`), журнал `GAME_ABORTED` с текущим seq состояния.
- **ELO после игры**: `StatsAggregatorService.updateEloRatings(gameId, winnerId, loserId)` (`games/services/stats-aggregator.service.ts`) — Elo-формула с K-фактором 32, транзакция upsert обоих `UserStats` (currentElo/peakElo/gamesWon/gamesLost/gamesPlayed/winRate/lastPlayedAt) + обновление лидерборда. ВАЖНО: в текущем коде вызов `updateEloRatings` не подключён к завершению мутаций (`GAME_OVER` его не вызывает) — ELO-обновление после игры доступно как сервисный метод, но автоматического триггера в `games/` нет.

---

## 2. Персистентность состояния

Класс: `GameStateService` (`games/game-state.service.ts`).

### Хранилища

| Хранилище | Что лежит | TTL / ключ |
|---|---|---|
| Prisma `GameState` (таблица) | сериализованный JSON состояния (`state`), `sequenceNumber`, `currentTurnPlayerId`, `phase`, `turnCount` | постоянно, ключ `gameId` |
| Prisma `Game` | статус/режим/игроки/`version` (= sequenceNumber) | постоянно |
| Redis | тот же `GameState` в полном (несжатом) виде | ключ `gamestate:<gameId>`, TTL **600 с** (10 мин) |
| Prisma `GameAction` | журнал событий (для eventsSince/реплеев) | постоянно; `cleanupOldActions(30 дней)` |

Чтение: сначала Redis-кеш (`getCachedState`), при промахе — БД + запись в кеш. Запись — всегда: БД-транзакция, затем кеш, затем публикация `STATE_UPDATED`.

### Optimistic locking при записи (`saveState`)

Внутри Prisma-транзакции читается текущий `GameState.sequenceNumber`; если он не равен `state.sequenceNumber - 1` → `ConcurrentModificationException` (класс в `games/exceptions/game.exceptions.ts`). Затем upert состояния + `game.version = sequenceNumber`.

### Сериализованный формат (JSON-поле `state`, компактные ключи)

`SerializedGameState` (v=1):
- `g` gameId, `s` sequenceNumber, `p` phase, `t` turnCount, `c` currentTurnPlayerId
- `pl[]` players: `uid/hid/hp/mhp/fid/alv`
- `f[]` fighters: `id/oid/hid/n/ty/hp/mhp/pos/e/hs/si/df/mv/at/sl` (включая `attackType`, `heroSlug`, `isDefeated`)
- `d{}` decks: `{c, tc, cards, pile}` — полное содержимое колоды (иначе терялось при load)
- `dp` discard piles, `h{}` handZones (`{c[], ms}`, карта с флагом `v` isVisible)
- `b` board: `dr` doors, `fg` fog, `tk` tokens, `cells[][]`, `w`, `h` (легаси-сейвы без cells → fallback сетка 20×20)
- `m` metadata: `la/lastActionAt`, `lb`, `v`, `ar` actionsRemaining, `ci` combatInfo (`aid/did/tf/ac/dc/av/dv/sa/ta` — даты ISO), `pc` passCount, `wi` winnerId, `tsp` turnStartPositions, `pe` pendingEffects, `mt/at/lc` per-turn флаги (maneuvered/attacked/lostCombat), `hs` heroStances.

Все необязательные поля проходят round-trip «прозрачно» (undefined в легаси-сейвах дефолтятся в геттерах).

### Приватные данные — `filterPrivateData(state, playerId)`

Для чужих userId: карты руки заменяются заглушкой (`name: '???'`, `attackValue/defenseValue/boostValue/effects/text: undefined`, `isVisible: false`); `topCard` колоды скрывается (`undefined`). Вызывается в `gameState` query, в resolve-функции подписки `gameStateUpdated` и при возврате результата мутаций. userId всегда берётся из JWT-контекста, а не из args.

---

## 3. Распределённые локи

Два механизма:

### `DistributedLockService` (`common/services/distributed-lock.service.ts`)

- Redis `SET lock:<key> <token> PX <ttl> NX`; токен = `время-rand-pid`.
- Дефолтный TTL **10000 мс** (защита от GC pause).
- Освобождение — атомарный Lua-скрипт (сравнение токена + DEL); продление — Lua (токен + PEXPIRE).
- `withLock(key, fn)` / `withLockOptions(key, fn, {ttl, retryCount, retryDelay})`; если лок не взят и ретраи исчерпаны — бросает `Could not acquire lock`.
- `acquireGameLock(gameId)` → ключ `lock:game:<gameId>`.

Используется всеми игровыми мутациями (`withLockOptions('game:<id>', ..., {ttl: 10000, retryCount: 1, retryDelay: 100})`), auto-resolve (`game:<gameId>`), VS_AI-ходами бота и matchmaking-мутациями (`mm:join:<userId>` TTL 5000, `mm:leave:<uid>` 3000, `mm:accept:<gameId>:<userId>` 5000 — все без ретраев).

### Простой `RedisService.acquireLock/withLock` (`redis/redis.service.ts`)

SET NX PX + auto-release по таймауту. Используется матчмейкинг-планировщиком: ключ `matchmaking:scheduler:lock`, TTL **15000 мс** (> интервала 5 с).

Ещё один слой защиты — optimistic lock по `sequenceNumber` в `saveState`/`updateWithLock` (`GameStateService`).

---

## 4. sequenceNumber

- Генерация: **инкремент при каждом изменении состояния**. `updateWithLock` — `expectedSequence + 1`; `performAutoResolve` (таймаут боя) — `state.sequenceNumber + 1`; инициализация — `1`. Сервер генерирует, клиент только передаёт как `since`.
- Хранится в `GameState.sequenceNumber`, `Game.version` (дублируется) и в каждой записи `GameAction.sequenceNumber`.
- `getSequenceNumber(gameId)` — query `gameSequence` (для optimistic updates и реконнекта).
- Роль в auto-resolve: BullMQ-джоб несёт `attackSequenceNumber`; при срабатывании, если `state.sequenceNumber > attackSequenceNumber` (за это время успели сыграть защиту/резолв), задача пропускается с reason `State changed`.

---

## 5. Публикация событий (PubSub)

Класс: `GameSubscriptionService` (`games/game-subscription.service.ts`). GraphQL-подписки — `GameSubscriptionResolver` (`games/resolvers/game-subscription.resolver.ts`). Настройка Apollo Server (graphql-ws, complexity limit 1000, depth limit 7) — `graphql/graphql.module.ts`.

### Каналы

| Слой | Канал | Назначение |
|---|---|---|
| In-memory `graphql-subscriptions.PubSub` | `game.updates.<gameId>` | доставка в `@Subscription` этого инстанса |
| Redis Pub/Sub | `game:updates:broadcast` | fan-out между инстансами (multi-instance); событие несёт `instanceId` (UUID инстанса) — при получении своего сообщения оно отбрасывается (guard от дублей) |
| Redis Pub/Sub | `presence:updates` | presence (см. §8) |

### Поток публикации

`publishGameUpdate(gameId, eventType, gameState)`:
1. `notifyLocalObservers` — rxjs-наблюдатели `subscribeToGame` (legacy-путь).
2. `publishToPubSub` — в локальный PubSub как `GamePubSubEvent {gameId, sequenceNumber, timestamp, eventType, payload}`.
3. `redis.publish('game:updates:broadcast', JSON(...))` — другим инстансам; там событие повторно проходит шаги 1–2.

Форма `GameUpdateEvent`: `{gameId, eventType, gameState, sequenceNumber, timestamp, instanceId}`.

### Двойное событие на мутацию (STATE_UPDATED + eventType)

Каждая игровая мутация публикует **два** события:
1. `'STATE_UPDATED'` — из `GameStateService.saveState()` (внутри транзакции сохранения);
2. специфичный `eventType` — из `executeMutation` (после save): `MANEUVER`, `FIGHTER_MOVED`, `ATTACK_INITIATED`, `DEFENSE_PLAYED`, `CARD_PLAYED`, `COMBAT_RESOLVED`, `TURN_ENDED`, `DOOR_TOGGLED`, `SPECIAL_ABILITY`, `GAME_ENDED`; лобби: `PLAYER_JOINED`, `PLAYER_LEFT` (компактный payload `{userId, username}`, seq 0).

Фильтр подписки `gameStateUpdated` пропускает только `eventType === 'STATE_UPDATED'` и `sequenceNumber > since` (если `since` передан) — ровно одно срабатывание на мутацию. Подписки на конкретные события (`attackInitiated`, `defensePlayed`, `combatResolved`, `turnChanged` [принимает `TURN_ENDED` и `TURN_CHANGED`], `gameEnded`) фильтруют по своему eventType.

### Фильтрация по userId (приватные данные)

Resolve-функция `gameStateUpdated` берёт userId из JWT (`context.req.user.id`; аргумент `userId` в схеме **игнорируется** — спуфинг невозможен) и применяет `GameStateService.filterPrivateData(payload, userId)` — у каждого подписчика своя проекция. В resolve `attackInitiated` и др. payload обрезан до безопасного подмножества (`phase/turnCount/currentTurnPlayerId` JSON-строкой) — руки туда не попадают.

Матчмейкинг-подписка: `MatchmakingPubSubService` (`matchmaking/resolvers/matchmaking.subscription.ts`) — собственный простой in-memory PubSub (без Redis broadcast!), события `matchFound` (filter: `player1Id/player2Id === variables.userId`; resolve подставляет данные оппонента), `matchTimeout`, `queueUpdated`.

---

## 6. BullMQ-очереди и джобы

Регистрация: `games/games.module.ts`, `game/jobs/game-jobs.module.ts`, `matchmaking/matchmaking.module.ts`, `audit/audit.module.ts`. Постановка: `GameJobsService` (`game/jobs/game-jobs.service.ts`), `GameActionService`, `CombatTimeoutService`, `MatchmakingSchedulerService`, `MatchConfirmationService`, `AuditService`.

### Сводная таблица

| Очередь | Джоб | Что делает | Таймеры/расписание | Retry | При таймауте/сбое |
|---|---|---|---|---|---|
| `combat-timeout` | `auto-resolve` | авто-разрешение боя, если защитник за 30 с не сыграл карту. jobId `combat:scheduled:<gameId>` (один на игру — старый удаляется при перепланировании) | delay **30 с** с момента атаки (`CombatTimeoutService.scheduleAutoResolve`, константа `DEFAULT_DEFENSE_TIMEOUT = 30`; есть и `DEFAULT_RESOLVE_TIMEOUT = 10`) | attempts 1 | Processor `CombatTimeoutProcessor` (`games/processors/combat-timeout.processor.ts`) → `processAutoResolve`: под локом `game:<id>`; если phase ≠ COMBAT или seq изменился — skip; иначе `performAutoResolve` (defense = null, phase → COMBAT_RESOLVE, seq+1) + `saveState`. Публикация идёт через saveState (`STATE_UPDATED`). removeOnComplete: 10, removeOnFail: 50 |
| `matchmaking-scheduler` | `find-matches` (repeatable) | поиск пар во всех 4 режимах, создание игр PENDING + confirmations | **каждые 5000 мс** (`repeat.every`), worker concurrency 1; distributed lock `matchmaking:scheduler:lock` TTL 15 с — одну итерацию обрабатывает один инстанс; до 20 пар за итерацию (`MATCH_FIND_BATCH_SIZE`) | attempts 1 | Ошибка итерации логируется, lock освобождается в finally; следующая итерация через 5 с |
| `match-confirmation` | `timeout` | таймаут подтверждения матча. jobId `timeout:<gameId>` | delay **30 с** (`CONFIRMATION_TIMEOUT_SECONDS = 30`); Redis-запись подтверждения `mm:confirm:<gameId>` TTL **35 с** (`CONFIRMATION_TTL_SECONDS = 35`) | attempts 1 | `handleConfirmationTimeout`: если confirmation ещё в Redis — определить не принявшего (PENDING при ACCEPTED у второго), удалить ключ, перевести игру в `ABORTED`. Успешный accept обоих удаляет job и ключ и запускает игру |
| `game-action` | `record-action` | асинхронная запись журнала `GameAction` (upsert по заранее сгенерированному UUID) — источник `eventsSince` | — | attempts 3, exponential backoff 1000 мс | removeOnComplete age 3600, removeOnFail age 86400. Запись best-effort: ошибка журнала не роняет мутацию |
| `audit` | `log-audit-event` | запись `AuthAuditLog` (см. §11) | — | attempts 3, exponential 1000 мс | removeOnComplete 7 дней, removeOnFail 30 дней |
| `combat-resolution` | `resolve` | джоб разрешения боя (legacy/заготовка; processor `CombatProcessor` — `game/jobs/combat.processor.ts` — содержит TODO, реальный резолв сейчас синхронный в мутациях) | — | attempts 3, exponential 1000 мс | removeOnComplete 3600, removeOnFail 7200 |
| `game-state-persist` | `persist` | фоновое сохранение снапшотов (заготовка, `GameStatePersistProcessor` — TODO) | — | attempts 5, exponential 2000 мс | removeOnComplete 3600, removeOnFail 7200 |

Важно: реальная защита от таймаута атаки — отмена джоба `playDefense`/`resolveCombat` (`cancelAutoResolve`) при действии защитника; `getTimeUntilResolve(gameId)` возвращает остаток таймера.

### Cron-задачи (не BullMQ, `@nestjs/schedule`)

| Сервис | Расписание | Что делает |
|---|---|---|
| `PresenceCleanupService` (`presence/presence-cleanup.service.ts`) | каждые 10 мин | удаляет presence старше 5 мин |
| `QueueSyncService` (`matchmaking/services/queue-sync.service.ts`) | при старте + каждые 10 мин | восстановление очереди из PostgreSQL после рестарта Redis (записи младше 600 с); очистка истёкших |
| `GameSanityService` (`matchmaking/services/game-sanity.service.ts`) | каждую минуту | zombie-игры: `PENDING` без обновления > 5 мин → обработка; застрявшие confirmations > 2 мин |

---

## 7. Матчмейкинг

Классы: `QueueManagerService`, `MatchmakingSchedulerService`, `MatchConfirmationService`, `PenaltyService`, `QueueSyncService`, `GameSanityService`, `MatchmakingMetricsService`, `MatchmakingPubSubService`; API — `matchmaking/resolvers/matchmaking.resolver.ts`, guard `MatchmakingGuard`.

### Redis-структуры

| Ключ | Тип | Назначение |
|---|---|---|
| `mm:queue:<MODE>` | Sorted Set (score = ELO, member = userId) | сама очередь режима; TTL 300 с (обновляется при каждом добавлении) |
| `mm:queue:data:<userId>` | Hash (`userId, rating, mode, heroPref, joinedAt`) | данные записи; TTL 900 с |
| `mm:confirm:<gameId>` | JSON (TTL 35 с) | `MatchConfirmation {player1Id, player2Id, player1Status, player2Status, expiresAt, createdAt}` |
| `mm:penalty:<userId>` | JSON (TTL окно decline 1 ч + 300 с) | `PenaltyRecord {declineCount, lastDeclineAt}` |
| `mm:tempban:<userId>` | JSON (TTL 30 мин) | `TempBanInfo {bannedAt, expiresAt, reason}` |
| `lock:mm:join/leave/accept:<...>` | String NX | локи мутаций |

Резервная копия очереди — Prisma `MatchmakingQueueEntry` (upsert при добавлении, delete при удалении; recovery через `QueueSyncService`).

Режимы: `ONE_V_ONE`, `TWO_V_TWO`, `FREE_FOR_ALL`, `VS_AI`.

### Expanding window (ELO-диапазон по времени ожидания)

`getEloRange()` в `matchmaking/models/queue-entry.model.ts`:

| Ожидание | Диапазон |
|---|---|
| 0–30 с | ±100 ELO |
| 30–60 с | ±200 ELO |
| 60–120 с | ±400 ELO |
| 120+ с | без ограничений (∞) |

Поиск: `ZRANGEBYSCORE` в диапазоне [rating−minDelta, rating+maxDelta], кандидаты сортируются по близости рейтинга, берётся ближайший. Массовый режим (`findMultipleMatches`) — приоритет долгождущим, до `maxMatches` пар. Zombie-записи (есть в ZSET, нет data-hash) вычищаются при чтении.

### Создание игры при матче (`MatchmakingSchedulerService.createMatch`)

1. Prisma `game.create` (`status: PENDING`, hostId = player1, opponentId = player2, boardId = первая доска).
2. `createConfirmation(gameId, p1, p2)` — Redis-ключ TTL 35 с + delayed job `timeout` 30 с.
3. Оба игрока удаляются из очереди.
4. `publishMatchFound` — подписка `matchFound` (payload: gameId, оба id/username/rating, mode, expiresAt).
5. Метрика `recordMatchCreated`.

### Подтверждения

- `acceptMatch`: под локом `mm:accept:<gameId>:<userId>`; проверка temp-ban; повторный accept идемпотентен. Когда оба ACCEPTED → `startGame` (статус `LOBBY`, `startedAt`), ключ подтверждения удалён, timeout-job отменён.
- `declineMatch`: статус обоих → DECLINED, ключ удалён, timeout-job отменён, игра → `ABORTED`, `PenaltyService.recordDecline()`.
- Таймаут (джоб через 30 с): подтверждение удалено, игра → `ABORTED`; определяется не принявший игрок.

### Penalty (`PenaltyService`, `matchmaking/models/penalty.model.ts`)

- Каждый decline → **−25 ELO** (`ELO_PENALTY: 25`, `max(0, elo−25)` в `UserStats`).
- **3 decline за 1 час** (`DECLINES_FOR_BAN: 3`, `DECLINE_WINDOW_HOURS: 1`) → **temp ban 30 мин** (`BAN_DURATION_MINUTES: 30`), счётчик decline сбрасывается; ELO-штраф при банящем decline не начисляется.
- `canJoinQueue` проверяется в `joinQueue`/`acceptMatch` (guard `MatchmakingGuard` + резолвер). `penaltyInfo` query отдаёт `{canJoinQueue, declineCount, tempBanUntil, penaltyElo, reason}`.
- Timeout подтверждения ≡ decline (`recordTimeout` → `recordDecline`; вызывается из `GameSanityService` для зависших подтверждений).

### ELO после игры

`StatsAggregatorService.updateEloRatings` — Elo K=32, транзакция upsert `UserStats` для победителя/проигравшего + `LeaderboardService.updatePlayerStats`. Дефолтный рейтинг 1200 (и в `getUserRating` матчмейкинга). См. примечание в §1 об отсутствии автотриггера.

---

## 8. Presence

Классы: `PresenceService`, `PresenceResolver`, `PresenceCleanupService` (`presence/`).

- **Heartbeat**: мутация `heartbeat(input: {status?, currentGameId?})` → `updatePresence`:
  - `presence:<userId>` — JSON `PresenceData {userId, status, currentGameId, lastSeenAt}`, **TTL 300 с**;
  - `presence:online` — Sorted Set (score = lastSeenAt) — индекс онлайна;
  - публикация JSON в Redis-канал `presence:updates`.
  - Ответ содержит `ttl: 300` — клиент должен слать heartbeat чаще (напр. каждые 60–120 с).
- Статусы (`PresenceStatus`): ONLINE / OFFLINE / IN_GAME / AWAY (модель `presence/models/presence.model.ts`).
- Query: `getPresence(userId)`, `getOnlineUsers`, `getOnlineCount`.
- Подписка `presenceUpdated(userIds?)` — фильтр по списку userId (без списка — все события).
- Клинап: cron каждые 10 минут удаляет ZSET-записи со score < now−5 мин (`zrangebyscore 0 <fiveMinutesAgo>`) и соответствующие ключи.

---

## 9. Реконнект-протокол

Компоненты: query `gameSequence` и `eventsSince` (`games/game.resolver.ts`), `GameStateService.getEventsSince`, подписка `gameStateUpdated(gameId, since)`.

Схема:

1. Клиент хранит последний полученный `sequenceNumber`.
2. При реконнекте: `gameSequence(gameId)` → текущий seq сервера.
3. Если есть gap: `eventsSince(gameId, sinceSequence)` → из таблицы `GameAction` записи с `sequenceNumber > since`, по возрастанию, **пачками по 100** (`take: 100`). Ответ `EventsSinceResponse {gameId, events[], lastSequence, hasMore}`; `hasMore = events.length >= 100` — клиент повторяет запрос с новым `lastSequence`, пока `hasMore` истинно.
4. Event-форма: `{sequenceNumber, type, gameId, playerId, payload (JSON-строка), timestamp}`.
5. Параллельно/после — перевзятие подписки `gameStateUpdated(gameId, since: <lastSequence>)`: filter отсеет события с seq ≤ since, т.е. переходный период без дублей и потерь.

**Поведение при gap**: события не переигрываются сервером автоматически — клиент обязан добирать их через `eventsSince` (пачками) и затем взять свежий снапшот `gameState(gameId)` (или первое событие `STATE_UPDATED`). Если событий между seq нет вовсе (например, журнал вычищен `cleanupOldActions` за 30 дней), `events` пуст, `lastSequence = sinceSequence`, `hasMore = false` — клиенту нужно полное состояние через `gameState`.

Аналогичный механизм для live-подписки: `since` в `gameStateUpdated` — серверный filter `sequenceNumber > since` гарантирует, что события, случившиеся до перевзятия подписки, не доставятся повторно.

---

## 10. Rate limits

`@nestjs/throttler`, декоратор `@Throttle({default: {limit, ttl: 60000}})` — лимиты в минуту.

### Лобби/игра (`games/game.resolver.ts`)

| Операция | Лимит |
|---|---|
| `createGame` | 10/мин |
| `joinGame` | 15/мин |
| `leaveGame` | 10/мин |
| `startGame` | 5/мин |
| `abortGame` | 5/мин |
| `toggleReady` | 20/мин |
| `selectHero` | 10/мин |

### Игровые мутации (`games/resolvers/game-actions.resolver.ts`)

| Мутация | Лимит |
|---|---|
| `maneuver` | 30/мин |
| `moveFighter` | 30/мин |
| `attack` | 20/мин |
| `playDefense` | 20/мин |
| `playScheme` | 20/мин |
| `resolvePendingEffect` | 30/мин |
| `resolveCombat` | 20/мин |
| `endTurn` | 30/мин |
| `pass` | 20/мин |
| `toggleDoor` | 30/мин |
| `setStance` | 30/мин |

### Матчмейкинг (`matchmaking/resolvers/matchmaking.resolver.ts`)

| Операция | Лимит |
|---|---|
| `joinQueue` | 5/мин |
| `leaveQueue` / `leaveAllQueues` / `acceptMatch` / `declineMatch` | без @Throttle (защита локами) |

### Auth (`auth/auth.resolver.ts`, для контекста)

`login` 5/мин, `register` 10/мин, `refresh` 3/мин, `logout` 3/мин, смена пароля 5/мин.

Прочие естественные ограничения: максимум **5 активных игр** на пользователя (`MAX_ACTIVE_GAMES`, `MaxActiveGamesException`); GraphQL complexity ≤ 1000, depth ≤ 7 (`graphql/graphql.module.ts`).

---

## 11. Аудит-логи

Классы: `AuditService` (`audit/audit.service.ts`), `AuditProcessor` (`audit/audit.processor.ts`), модель `games/models/audit.model.ts`.

- Запись: `logEvent(CreateAuditEventDto)` → очередь BullMQ `audit` (attempts 3, exponential 1 с; completed хранятся 7 дней, failed 30 дней) → processor пишет Prisma `AuthAuditLog` (`action, userId, ipAddress, userAgent, success, errorMessage, metadata`, `createdAt`).
- Metadata ≥ 1 МБ обрезаются с маркером `truncated`.
- Типы (`AuditEventType`): LOGIN_FAILED, UNAUTHORIZED_ACCESS, SUSPICIOUS_ACTIVITY, RATE_LIMIT_EXCEEDED и др.
- Чтение: `getAuditLogs(filter)` (take 100), `getAuditLogsPaginated(filter, skip, take=50)` с `total`, `getUserAuditLogs`.
- Детекция подозрительной активности: `getSuspiciousActivity(windowMinutes=60)` — группировка по IP событий LOGIN_FAILED/UNAUTHORIZED_ACCESS/SUSPICIOUS_ACTIVITY/RATE_LIMIT_EXCEEDED; порог ≥ 5 событий.
- `getLoginAttempts(userId, 15 мин)` — счётчик неудачных логинов; `cleanupOldLogs(90 дней)`.
- Использование в игровой логике: `StatsAggregatorService.applyQueuePenalty` пишет `SUSPICIOUS_ACTIVITY` при ELO-штрафе.

Отдельно от аудита — **журнал игровых действий** (`GameAction`, очередь `game-action`, `GameActionService`): каждая мутация и лобби-операция пишут `{gameId, sequenceNumber, type (GameActionType), playerId, payload {action, input}}`. Это источник данных для `eventsSince` и `replay` (`games/services/replay.service.ts` + `ReplayCompressorService`).

---

## 12. Кеш-ключи Redis (сводка)

| Ключ | Тип | TTL | Владелец |
|---|---|---|---|
| `gamestate:<gameId>` | JSON GameState | 600 с | GameStateService |
| `gamestate:lock:<gameId>` (через `lock:`-префикс) | lock | 5000 мс | GameStateService.updateWithLock |
| `lock:game:<gameId>` | lock | 10000 мс | DistributedLockService |
| `lock:mm:*` | lock | 3000–5000 мс | matchmaking resolver |
| `matchmaking:scheduler:lock` | lock | 15000 мс | MatchmakingSchedulerService |
| `game:<gameId>` | JSON GameResponse | 300 с | GameService |
| `games:list:<userId>:<status>` | JSON | 60 с | GameService.myGames |
| `games:available:<mode|all>` | JSON | 30 с | GameService.availableGames |
| `mm:queue:<MODE>` | ZSet | 300 с | QueueManagerService |
| `mm:queue:data:<userId>` | Hash | 900 с | QueueManagerService |
| `mm:confirm:<gameId>` | JSON | 35 с | MatchConfirmationService |
| `mm:penalty:<userId>` | JSON | 3900 с | PenaltyService |
| `mm:tempban:<userId>` | JSON | 1800 с | PenaltyService |
| `presence:<userId>` | JSON | 300 с | PresenceService |
| `presence:online` | ZSet | — (клинап cron) | PresenceService |
| Каналы Pub/Sub: `game:updates:broadcast`, `presence:updates` | — | — | GameSubscriptionService / PresenceService |

Кеш-инфраструктура контента (тег-инвалидация, прогрев) — `cache/cache-tags.service.ts`, `cache/cache-warming.service.ts`.

---

## Известные пробелы (Known gaps, на момент написания)

1. Очереди `combat-resolution` и `game-state-persist` (модуль `game/jobs/`) — процессоры-заготовки (TODO); реальный резолв боя выполняется синхронно в мутациях `attack`/`playDefense`/`resolveCombat` через `GameActionExecutorService`.
2. `AutoResolve` (`CombatTimeoutService.performAutoResolve`) переводит в `COMBAT_RESOLVE` без применения урона (TODO-блок) — полный резолв должен идти через `resolveCombat`.
3. `updateEloRatings` не вызывается автоматически при `GAME_OVER`.
4. Матчмейкинг-PubSub (`matchFound`) — только in-memory, без Redis broadcast между инстансами.
5. Подписки `playerJoined`/`playerLeft` получают лобби-события (компактный payload), а не полный GameState.
