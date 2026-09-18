# 07. GraphQL: исчерпывающий справочник контракта

> Источники: декораторы `@nestjs/graphql` в `backend/src/**` (schema генерируется кодом-first, `autoSchemaFile: true`, `sortSchema: true` — файла schema.gql в репозитории нет) + операции фронтенда `src/graphql/*.graphql`.
> Endpoint: HTTP `POST /graphql`, подписки — WebSocket `graphql-ws` (`subscriptions: { 'graphql-ws': true }`).
> Playground включён. CSRF-prevention отключён (локальная разработка).

**Авторизация.** Глобального guard'а нет — каждый resolver сам вешает `@UseGuards(GqlAuthGuard, ...)`. Поля/мутации без guard'а фактически публичны (даже если помечены `@Public()` или используют `@CurrentUser()`). JWT передаётся в заголовке `Authorization: Bearer <accessToken>`; для подписок — в `connectionParams.authorization` (или `token`).

**Роли** (enum Prisma `UserRole`): `USER`, `ADMIN` (AdminGuard), `MODERATOR` (ModeratorGuard: ADMIN + MODERATOR).

**Защита запросов** (validationRules в `src/graphql/graphql.module.ts`):
- complexity limit: максимум 1000 (при >500 — warning в лог);
- depth limit: 7 (кроме `_entities`, `_service`).

---

## Содержание

1. [Query](#1-query)
2. [Mutation](#2-mutation)
3. [Subscription](#3-subscription)
4. [Object-типы](#4-object-типы)
5. [Input-типы](#5-input-типы)
6. [Enum-типы](#6-enum-типы)
7. [Скаляры](#7-скаляры)
8. [Формат ошибок](#8-формат-ошибок)

---

## 1. Query

### 1.1. Контент (публичные, `ContentResolver`)

| Поле | Сигнатура | Возврат | Auth | Описание / ошибки |
|---|---|---|---|---|
| `heroes` | `heroes: [Hero!]!` | `[Hero!]!` | публичное | Все герои. |
| `heroesPaginated` | `(page: Int, limit: Int, set: String)` | `PaginatedHeroes!` | публичное | Пагинированный список героев (по умолчанию page=1, limit=10). |
| `hero` | `(id: String!)` | `Hero` (nullable) | публичное | Герой по slug; не найден → `null`. |
| `cards` | `(heroId: String!)` | `[Card!]!` | публичное | Карты колоды героя. |
| `card` | `(id: String!)` | `Card` (nullable) | публичное | Карта по ID; не найдена → `null`. |
| `boards` | `boards: [Board!]!` | `[Board!]!` | публичное | Все поля (доски). |
| `boardsPaginated` | `(page: Int, limit: Int)` | `PaginatedBoards!` | публичное | Пагинированный список досок. |
| `board` | `(id: String!)` | `Board` (nullable) | публичное | Доска по slug; не найдена → `null`. |
| `contentVersion` | `contentVersion: String!` | `String!` | публичное | Версия контента (для инвалидации кэша клиента). |
| `sets` | `sets: [String!]!` | `[String!]!` | публичное | Все наборы-расширения. |
| `heroesBySet` | `(set: String!)` | `[Hero!]!` | публичное | Герои конкретного набора. |
| `contentSummary` | `contentSummary: ContentSummary!` | `ContentSummary!` | публичное | Сводка контента (версия, счётчики). |
| `clearContentCache` | `clearContentCache: Boolean!` | `Boolean!` | публичное (см. прим.) | Сброс кэша контента. **Недочёт:** помечено `@Public()`, хотя комментарий обещает admin-only. |

`Hero.cards` — field resolver `HeroResolver.getCards` (дозагрузка колоды из БД).

### 1.2. Игры (`GameResolver`)

| Поле | Аргументы | Возврат | Auth | Описание / ошибки |
|---|---|---|---|---|
| `game` | `id: String!` | `GameResponse` (nullable) | JWT | Игра по ID; проверка доступа (`checkGameAccess`). Ошибки: не участник/не существует. |
| `myGames` | `filters: GameFiltersDto` (nullable) | `[GameResponse!]!` | JWT | Игры текущего пользователя. |
| `availableGames` | `mode: String`, `limit: Float` (оба nullable) | `[GameResponse!]!` | **публичное** (guard отсутствует) | Открытые игры для присоединения. |
| `gameState` | `gameId: String!` | `GameStateResponse` (nullable) | JWT | Полное состояние игры (приватные данные отфильтрованы по userId из JWT). Ошибки: не участник. |
| `heroStances` | `heroSlug: String!` | `[StanceOptionDto!]!` | публичное (`@Public()`) | Опции стоек героя из ABILITY_CONFIGS; без стоек — `[]`. |
| `gameSequence` | `gameId: String!` | `Float` (nullable) | JWT | Текущий sequence number (для optimistic updates). |
| `eventsSince` | `gameId: String!`, `sinceSequence: Float!` | `EventsSinceResponse` (nullable) | JWT | События с заданного sequence (catch-up при реконнекте; пачка ≤100, `hasMore` при =100). Ошибки: нет доступа к игре. |

### 1.3. Админ-панель (`AdminResolver`)

Аргументы `page: Int`, `limit: Int`, `search: String`, `sortBy: String`, `sortOrder: String ('asc'|'desc')` — везде nullable.

| Поле | Аргументы | Возврат | Auth | Описание |
|---|---|---|---|---|
| `adminStats` | — | `AdminStatsDto!` | JWT + **ADMIN** | Агрегированные счётчики (users/heroes/cards/boards/games). |
| `adminHero` | `id: String!` | `AdminHero!` | JWT | Герой по ID (детальный, с картами). |
| `adminCard` | `id: String!` | `AdminCard!` | JWT | Карта по ID. |
| `adminBoard` | `id: String!` | `AdminBoard!` | JWT | Доска по ID. |
| `adminUser` | `id: String!` | `UserDto!` | JWT | Пользователь по ID. |
| `usersList` | page, limit, search, sortBy, sortOrder | `PaginatedUsersDto!` | JWT | Пользователи (пагинация/поиск/сортировка). |
| `userList` | те же | `PaginatedUsersDto!` | JWT | Алиас `usersList` (для Refine, singular form). |
| `cardsList` | page, limit, `heroId: String`, search, sortBy, sortOrder | `CardsPaginatedDto!` | JWT | Все карты (фильтр по герою). |
| `cardList` | те же | `CardsPaginatedDto!` | JWT | Алиас `cardsList`. |
| `heroesList` | page, limit, search, sortBy, sortOrder | `HeroesPaginatedDto!` | JWT | Все герои. |
| `heroList` | те же | `HeroesPaginatedDto!` | JWT | Алиас `heroesList`. |
| `boardsList` | page, limit, search, sortBy, sortOrder | `BoardsPaginatedDto!` | JWT | Все доски. |
| `boardList` | те же | `BoardsPaginatedDto!` | JWT | Алиас `boardsList`. |
| `gamesList` | page, limit, search, sortBy, sortOrder | `GamesPaginatedDto!` | JWT | Все игры. |
| `gameList` | те же | `GamesPaginatedDto!` | JWT | Алиас `gamesList`. |
| `adminGame` | `id: String!` | `AdminGameDto!` | JWT | Игра по ID (админ-вид). |
| `auditLogs` | page, limit, `userId: String` (nullable) | `AuditLogsPaginatedDto!` | JWT + **MODERATOR** (ADMIN или MODERATOR) | Журнал аудита (limit по умолчанию 50). |
| `matchmakingQueue` | — | `MatchmakingQueueDto!` | JWT | Текущая очередь матчмейкинга. |

### 1.4. Пользователи (`UsersResolver`)

| Поле | Аргументы | Возврат | Auth | Описание / ошибки |
|---|---|---|---|---|
| `me` | — | `UserWithSettingsResponse` (nullable) | JWT | Текущий пользователь + настройки (включая email). |
| `user` | `id: String!` | `PublicUserResponse` (nullable) | публичное (токен опционален) | Публичный профиль; при `profileVisible=false` и запросе не владельцем → `username: "Hidden"`. |
| `userByUsername` | `username: String!` | `PublicUserResponse` (nullable) | публичное | То же по username. |
| `myStats` | — | `UserStatsResponse!` | JWT | Статистика текущего пользователя. |
| `stats` | `userId: String!` | `UserStatsResponse` (nullable) | публичное | Публичная статистика пользователя. |
| `mySettings` | — | `UserSettingsGraphql!` | JWT | Настройки текущего пользователя. |

### 1.5. Лидерборд (`LeaderboardResolver`, публичный)

| Поле | Аргументы | Возврат | Описание |
|---|---|---|---|
| `leaderboard` | `heroId: String`, `timeFrame: TimeFrame`, `page: Int` (def 0), `pageSize: Int` (def 50) | `String!` | Таблица лидеров как **JSON-строка** (`JSON.stringify(LeaderboardResponse)`). |
| `topPlayers` | `limit: Int` (def 10), `timeFrame: String` (def `"all"`) | `String!` | Топ игроков, JSON-строка. |
| `getPlayerRank` | `userId: String!`, `heroId: String`, `timeFrame: String` (def `"all"`) | `LeaderboardRankResponse!` | Место игрока в рейтинге. |

### 1.6. Матчмейкинг (`MatchmakingResolver`)

| Поле | Аргументы | Возврат | Auth | Описание |
|---|---|---|---|---|
| `queueStatus` | `mode: GameMode!` | `QueueStatusResponse!` | без guard (рассчитан на JWT-контекст) | Позиция/размер очереди/ожидание. |
| `allQueueStatus` | — | `String!` | без guard | Статистика всех очередей (JSON-строка). |
| `penaltyInfo` | — | `PenaltyInfoDto!` | без guard | Штрафы текущего пользователя (declineCount, tempBan и т.д.). |
| `metrics` | — | `String!` | без guard | Метрики матчмейкинга (JSON-строка). |

### 1.7. Presence (`PresenceResolver`, без guard'ов — публичные)

| Поле | Аргументы | Возврат | Описание |
|---|---|---|---|
| `getPresence` | `userId: String!` | `Presence` (nullable) | Присутствие пользователя (`null` — нет записи). |
| `getOnlineUsers` | — | `OnlineUsersResponse!` | Список онлайн userId + количество. |
| `getOnlineCount` | — | `Float!` | Количество онлайн. |

**Итого Query: 53 root-поля.**

---

## 2. Mutation

### 2.1. Аутентификация (`AuthResolver`)

| Мутация | Аргументы | Возврат | Auth | Rate-limit | Описание / ошибки |
|---|---|---|---|---|---|
| `register` | `input: RegisterDto!` | `AuthResponseDto!` | публичное | 5/мин | Регистрация. Ошибки: email/username занят. |
| `login` | `input: LoginDto!` | `AuthResponseDto!` | публичное | 10/мин | Логин (IP + UA пишутся в аудит). Ошибки: неверные креды. |
| `logout` | — | `Boolean!` | JWT (guard-класса нет, но требует `@CurrentUser`) | — | Ревокация access-токена. |
| `refreshTokens` | `refreshToken: String!` | `AuthResponseDto!` | публичное | 3/мин | Обновление пары токенов. Ошибки: невалидный/отозванный refresh. |
| `resetPassword` | `token: String!`, `newPassword: String!` | `Boolean!` | публичное | 3/мин | Сброс пароля по токену. |
| `verifyEmail` | `token: String!` | `Boolean!` | публичное | 5/мин | Подтверждение email. |

### 2.2. Лобби/игра (`GameResolver`, все JWT)

| Мутация | Аргументы | Возврат | Rate-limit | Описание / ошибки |
|---|---|---|---|---|
| `createGame` | `input: CreateGameDto!`, `idempotencyKey: String` (nullable) | `GameResponse!` | 10/мин | Создать игру (идемпотентность по ключу). |
| `joinGame` | `input: JoinGameDto!` | `GameResponse!` | 15/мин | Присоединиться (валидация heroId). Ошибки: игра заполнена/не найдена, неверный heroId. |
| `leaveGame` | `gameId: String!` | `Boolean!` | 10/мин | Хост передаёт хостство/удаляет игру; opponent просто выходит. |
| `startGame` | `gameId: String!` | `GameResponse!` | 5/мин | Начать игру. Ошибки: не хост, не все готовы. |
| `abortGame` | `gameId: String!` | `GameResponse!` | 5/мин | Прервать игру. |
| `toggleReady` | `gameId: String!` | `GameResponse!` | 20/мин | Переключить готовность. |
| `selectHero` | `gameId: String!`, `heroId: String!` | `GameResponse!` | 10/мин | Выбрать героя в лобби. |

### 2.3. Игровые действия (`GameActionsResolver`, все JWT)

Единый конвейер: `GqlAuthGuard → GameStatusGuard (IN_PROGRESS) → GamePlayerGuard → PhaseGuard → distributed lock → executor → saveState → publish → журнал GameAction → фильтрация приватных данных`. Все возвращают `GameMutationResult!` (payload `state` — JSON-строка отфильтрованного состояния).

| Мутация | Input | Guard-фаза | Rate-limit | Событие | Описание |
|---|---|---|---|---|---|
| `maneuver` | `ManeuverDto!` | ActionPhaseGuard | 30/мин | `MANEUVER` | Манёвр: добор 1 + движение всех своих бойцов (+ опц. boost-карта). Тратит 1 действие. |
| `moveFighter` | `MoveFighterDto!` | ActionPhaseGuard | 30/мин | `FIGHTER_MOVED` | Простое перемещение бойца (1 действие). |
| `attack` | `AttackDto!` | ActionPhaseGuard | 20/мин | `ATTACK_INITIATED` | Объявить атаку (1 действие); ставит 30-сек auto-resolve таймер. |
| `playDefense` | `PlayDefenseDto!` | DefensePlayGuard | 20/мин | `DEFENSE_PLAYED` | Карта защиты в фазе COMBAT (только защищающийся); отменяет auto-resolve. |
| `playScheme` | `PlaySchemeDto!` | ActionPhaseGuard | 20/мин | `CARD_PLAYED` | Scheme-карта из руки (1 действие). |
| `resolvePendingEffect` | `ResolvePendingEffectDto!` | GamePlayerGuard (без фазового guard) | 30/мин | `CARD_PLAYED` | Выбор бойца/клетки/опции для отложенного эффекта (MOVE/PLACE/CHOOSE_ONE). Действие не тратит. |
| `resolveCombat` | `ResolveCombatDto!` | CombatResolveGuard | 20/мин | `COMBAT_RESOLVED` | Разрешить бой, нанести урон; отменяет auto-resolve. |
| `endTurn` | `EndTurnDto!` | ActionPhaseGuard | 30/мин | `TURN_ENDED` | Завершить ход. |
| `pass` | `PassDto!` | ActionPhaseGuard | 20/мин | `CARD_PLAYED` | Сброс карты + доп. действие. |
| `toggleDoor` | `ToggleDoorDto!` | ActionPhaseGuard | 30/мин | `DOOR_TOGGLED` | Открыть/закрыть дверь (способность, напр. Bjorn). |
| `setStance` | `SetStanceDto!` | ActionPhaseGuard | 30/мин | `SPECIAL_ABILITY` | Смена стойки героя (STANCE); действие НЕ тратит. |

Ошибки всех игровых мутаций: `BAD_USER_INPUT` при провале действия (сообщение движка), `ConflictException` при конфликте состояния.

### 2.4. Профиль (`UsersResolver`, все JWT)

| Мутация | Аргументы | Возврат | Rate-limit | Описание |
|---|---|---|---|---|
| `updateProfile` | `input: UpdateProfileDto!` | `UserResponse!` | 5/мин | Обновить username/avatar. |
| `updateSettings` | `input: SettingsDto!` | `UserSettingsGraphql!` | 10/мин | Обновить настройки. |
| `changePassword` | `input: ChangePasswordDto!` | `Boolean!` | 3/мин | Смена пароля. Ошибки: неверный текущий пароль. |
| `deleteAccount` | — | `Boolean!` | 2/час | Удалить аккаунт. |
| `uploadAvatar` | `fileUrl: String!` | `String!` | 5/мин | Установить аватар по URL. |
| `removeAvatar` | — | `Boolean!` | 10/мин | Удалить аватар. |

### 2.5. Матчмейкинг (`MatchmakingResolver`)

| Мутация | Аргументы | Возврат | Auth | Rate-limit | Описание / ошибки |
|---|---|---|---|---|---|
| `joinQueue` | `input: JoinQueueDto!` | `QueueStatusResponse!` | MatchmakingGuard | 5/мин | Войти в очередь (повторный вход → ре-вход). Под distributed-lock. |
| `leaveQueue` | `mode: GameMode!` | `Boolean!` | MatchmakingGuard | — | Выйти из очереди режима. |
| `leaveAllQueues` | — | `Boolean!` | MatchmakingGuard | — | Выйти из всех очередей. |
| `acceptMatch` | `gameId: String!` | `Boolean!` | без guard | — | Принять матч; `true` = оба приняли. Ошибки: temp-ban (FORBIDDEN), истекло подтверждение (NOT_FOUND). |
| `declineMatch` | `gameId: String!` | `Boolean!` | без guard | — | Отклонить матч (записывает штраф). |

### 2.6. Админ (`AdminResolver`; все мутации JWT + ADMIN)

| Мутация | Аргументы | Возврат | Описание |
|---|---|---|---|
| `createHero` | `input: CreateHeroInput!` | `AdminHero!` | Создать героя. |
| `updateHero` | `id: String!`, `input: UpdateHeroInput!` | `AdminHero!` | Обновить героя. |
| `deleteHero` | `id: String!` | `Boolean!` | Удалить героя. |
| `createCard` | `input: CreateCardInput!` | `AdminCard!` | Создать карту. |
| `updateCard` | `id: String!`, `input: UpdateCardInput!` | `AdminCard!` | Обновить карту. |
| `deleteCard` | `id: String!` | `Boolean!` | Удалить карту. |
| `createBoard` | `input: CreateBoardInput!` | `AdminBoard!` | Создать доску. |
| `updateBoard` | `id: String!`, `input: UpdateBoardInput!` | `AdminBoard!` | Обновить доску. |
| `deleteBoard` | `id: String!` | `Boolean!` | Удалить доску. |
| `updateUser` | `id: String!`, `input: UpdateUserInput!` | `UserDto!` | Обновить пользователя (в т.ч. роль). |
| `banUser` | `id: String!` | `Boolean!` | Забанить (soft-delete). |
| `unbanUser` | `id: String!` | `Boolean!` | Разбанить. |
| `cleanupGames` | `input: CleanupGamesInput` (nullable) | `CleanupGamesResultDto!` | Чистка: удаление FINISHED/ABORTED старше N дней + прерывание застрявших игр. |

### 2.7. Presence

| Мутация | Аргументы | Возврат | Auth | Описание |
|---|---|---|---|---|
| `heartbeat` | `input: HeartbeatInput!` | `HeartbeatResponse!` | без guard (нужен `@CurrentUser`) | Обновить присутствие; TTL = 300 c. |

**Итого Mutation: 49.**

---

## 3. Subscription

Все игровые подписки — JWT (`GqlAuthGuard`), транспорт `graphql-ws`. Токен — в `connectionParams`.

### 3.1. Игровые (`GameSubscriptionResolver`)

| Подписка | Аргументы | Payload | Фильтр |
|---|---|---|---|
| `gameStateUpdated` | `gameId: String!`, `since: Int` (nullable), `userId: String` (nullable, **игнорируется** — фильтрация по JWT) | `GameState!` | `gameId` совпадает, `eventType === 'STATE_UPDATED'`, `sequenceNumber > since` (если задан). Данные фильтруются по userId из JWT (руки соперника скрыты). |
| `attackInitiated` | `gameId: String!` | `GameEvent!` | `eventType === ATTACK_INITIATED`. |
| `defensePlayed` | `gameId: String!` | `GameEvent!` | `eventType === DEFENSE_PLAYED`. |
| `combatResolved` | `gameId: String!` | `GameEvent!` | `eventType === COMBAT_RESOLVED`. |
| `turnChanged` | `gameId: String!` | `TurnState!` | `eventType ∈ {TURN_ENDED, TURN_CHANGED}`. |
| `playerJoined` | `gameId: String!` | `GameEvent!` | `eventType === PLAYER_JOINED`. **Известный пробел:** событие пока никто не публикует — подписка молчит. |
| `playerLeft` | `gameId: String!` | `GameEvent!` | `eventType === PLAYER_LEFT`. Аналогично не публикуется. |
| `gameEnded` | `gameId: String!` | `GameEvent!` | `eventType === GAME_ENDED` (публикуется при `phase === GAME_OVER`). |

Payload `GameEvent.payload` — безопасное подмножество состояния (phase, turnCount, currentTurnPlayerId) JSON-строкой; полное состояние — через `gameStateUpdated`.

### 3.2. Матчмейкинг (`MatchmakingSubscriptionResolver`, без guard)

| Подписка | Аргументы | Payload | Фильтр |
|---|---|---|---|
| `matchFound` | `userId: String!` | `MatchFoundResponse!` | `payload.player1Id === userId || player2Id === userId` (userId — аргумент подписки, резолв «за соперника»). Payload содержит данные соперника + `expiresAt`. |

### 3.3. Presence (`PresenceResolver`, без guard)

| Подписка | Аргументы | Payload | Фильтр |
|---|---|---|---|
| `presenceUpdated` | `userIds: [String]` (nullable) | `Presence!` | Если `userIds` пуст/не задан — все события; иначе только по id из списка. |

**Итого Subscription: 10.**

---

## 4. Object-типы

Обозначения: тип GraphQL → источник (класс). Поля `DateTime` сериализуются как **epoch-миллисекунды** (кастомный скаляр, см. §7).

### Auth

**TokensPair** (интерфейс, `auth-response.dto.ts`)

| Поле | Тип | Nullable | Описание |
|---|---|---|---|
| `accessToken` | `String!` | нет | JWT access-токен. |
| `refreshToken` | `String!` | нет | JWT refresh-токен. |

**AuthUserResponse**

| Поле | Тип | Nullable | Описание |
|---|---|---|---|
| `id` | `ID!` | нет | ID пользователя. |
| `email` | `String!` | нет | Email. |
| `username` | `String!` | нет | Имя. |
| `avatar` | `String` | да | Аватар. |
| `role` | `UserRole!` | нет | Роль. |
| `createdAt` | `DateTime!` | нет | Создан. |
| `emailVerified` | `DateTime` | да | Когда подтверждён email. |

**AuthResponseDto** (implements TokensPair): `accessToken: String!`, `refreshToken: String!`, `user: AuthUserResponse!`.

### Users / профиль

**UserResponse**: `id: ID!`, `email: String!`, `username: String!`, `avatar: String`, `role: UserRole!`, `createdAt: DateTime!`, `emailVerified: DateTime`.

**PublicUserResponse**: `id: ID!`, `username: String!`, `avatar: String`, `createdAt: DateTime!` (без email).

**UserSettingsResponse**: `id: ID!`, `theme: String!`, `language: String!`, `soundEnabled: Boolean!`, `musicEnabled: Boolean!`, `profileVisible: Boolean!`, `showOnlineStatus: Boolean!`.

**UserWithSettingsResponse** (extends UserResponse): + `settings: UserSettingsResponse`.

**PublicUserWithSettingsResponse** (extends PublicUserResponse): + `settings: UserSettingsResponse` (в схеме присутствует, запросами не используется).

**UserSettingsGraphql**: поля идентичны `UserSettingsResponse`.

**FavoriteHero**: `id: String!`, `name: String!`, `nameEn: String!`, `nameRu: String!`.

**UserStatsResponse**: `userId: String!`, `gamesPlayed: Int!`, `gamesWon: Int!`, `gamesLost: Int!`, `winRate: Float!`, `currentElo: Int!`, `peakElo: Int!`, `lastPlayedAt: DateTime`, `totalPlayTime: Int!`, `favoriteHero: FavoriteHero`.

**LeaderboardUser**: `id: String!`, `username: String!`, `avatar: String`.
**LeaderboardEntryResponse**: `rank: Int!`, `user: LeaderboardUser!`, `elo: Int!`, `gamesWon: Int!`, `gamesPlayed: Int!`.
**LeaderboardRankResponse** (leaderboard.resolver.ts): `rank: Int!`, `userId: String!`, `elo: Int!`, `heroId: String`, `timeFrame: String!`.

### Игры (lobby / game models)

**GameResponse**: `id: ID!`, `code: String`, `status: GameStatus!`, `mode: GameMode!`, `hostId: String!`, `host: GamePlayerResponse!`, `opponentId: String`, `opponent: GamePlayerResponse`, `boardId: String!`, `boardState: String`, `createdAt: DateTime!`, `updatedAt: DateTime!`, `startedAt: DateTime`, `endedAt: DateTime`, `winnerId: String`, `version: Int!`, `players: [GamePlayerResponse!]!`, `phase: GamePhase`, `currentTurn: Int`.

**GamePlayerResponse**: `id: ID!`, `userId: String!`, `username: String!`, `avatar: String`, `heroId: String`, `isReady: Boolean!`, `hasPassed: Boolean!`, `seatOrder: Int!`.

**GameStateResponse**: `id: ID!`, `gameId: String!`, `state: String!` (JSON-строка полного состояния), `sequenceNumber: Int!`, `currentTurnPlayerId: String`, `phase: String!` (строка, не enum), `turnCount: Int!`, `updatedAt: DateTime!`.

**PageInfo**: `hasNextPage: Boolean!`, `hasPreviousPage: Boolean!`, `startCursor: String`, `endCursor: String`, `totalCount: Int!`.
**GameEdge**: `cursor: String!`, `node: GameResponse`.
**GameConnection**: `edges: [GameEdge!]!`, `pageInfo: PageInfo!` (Relay-пагинация; в resolver'ах не используется, но присутствует в схеме).

### Игровой процесс (gameplay.dto.ts)

**GameMutationResult** (общий возврат всех игровых мутаций): `state: String` (JSON отфильтрованного состояния), `sequenceNumber: Int!`, `timestamp: DateTime!`, `phase: GamePhase!`, `currentTurnPlayerId: String`, `turnCount: Int!`.

**GameState** (GraphQL-версия состояния): `gameId: String!`, `sequenceNumber: Int!`, `phase: GamePhase!`, `turnCount: Int!`, `currentTurnPlayerId: String!`, `players: String` (JSON), `fighters: String` (JSON), `handZones: String` (JSON), `boardState: String` (JSON), `metadata: String` (JSON).

**GameStatePlayer**: `userId: String!`, `heroId: String!`, `health: Int!`, `maxHealth: Int!`, `fighterIds: [String!]!`, `isAlive: Boolean!`.

**Fighter**: `id: String!`, `ownerId: String!`, `heroId: String!`, `name: String!`, `type: String!`, `health: Int!`, `maxHealth: Int!`, `position: String` (JSON), `effects: [String!]`, `hasSidekick: Boolean!`.

**HandZone**: `cards: String` (JSON), `maxSize: Int!`.

**TurnState**: `playerId: String!`, `turnCount: Int!`, `phase: GamePhase!`.

**GameEvent**: `type: GameEventType!`, `gameId: String!`, `sequenceNumber: Int!`, `timestamp: DateTime!`, `payload: String` (JSON безопасного подмножества состояния).

**CombatState**: `attackerId: String!`, `targetId: String!`, `attackCardId: String`, `defenseCardId: String`, `timeoutAt: DateTime!`.

**StanceOptionDto**: `id: String!`, `label: String!`, `isDefault: Boolean!`.

**EventsSinceResponse**: `gameId: String!`, `events: [GameEvent!]!`, `lastSequence: Int!`, `hasMore: Boolean!`.

### Контент (content.dto.ts)

**HeroUrls**: `avatar: String!`, `mini: String!`, `cardCover: String!`.

**HeroAbility**: `id: String!`, `name: String!`, `text: String!`, `trigger: AbilityTrigger!`.

**CardEffect**: `id: String!`, `timing: EffectTiming!`, `text: String!`.

**Card**: `id: String!`, `title: String!`, `type: CardType!`, `value: Int!`, `boost: Int!`, `quantity: Int!`, `characterName: String!`, `effects: [CardEffect!]!`, `imageUrl: String`, `imageUrlRu: String`.

**Hero**: `id: String!`, `name: String!`, `nameEn: String`, `nameRu: String`, `health: Int!`, `movement: Int!`, `set: String!`, `abilities: [HeroAbility!]!`, `cards: [Card!]!`, `fighterType: FighterType!`, `sidekickCount: Int`, `sidekickHealth: Int`, `urls: HeroUrls`, `imageUrl: String`, `avatarUrl: String`, `createdAt: DateTime`, `updatedAt: DateTime`.

**Position**: `x: Int!`, `y: Int!`.

**BoardSpace**: `position: Position!`, `zones: [Zone!]!`, `isObstacle: Boolean`, `startingPositionsJson: String`.

**Board**: `id: String!`, `name: String!`, `width: Int!`, `height: Int!`, `recommendedPlayers: Int!`, `spaces: [BoardSpace!]!`, `imageUrl: String`.

**PaginationInfo**: `total: Int!`, `page: Int!`, `limit: Int!`, `totalPages: Int!`, `hasNextPage: Boolean!`, `hasPreviousPage: Boolean!`.

**PaginatedHeroes**: `items: [Hero!]!`, `pagination: PaginationInfo!`.
**PaginatedBoards**: `items: [Board!]!`, `pagination: PaginationInfo!`.

**ContentSummary**: `version: String!`, `heroesCount: Int!`, `boardsCount: Int!`, `setsCount: Int!`, `sets: [String!]!`.

### Админ (admin.dto.ts)

**AdminCard**: `id!`, `name!`, `nameEn!`, `nameRu!`, `cardType!`, `subType?`, `attackValue: Int?`, `defenseValue: Int?`, `boostValue: Int?`, `bannerName?`, `effects?`, `text?`, `textEn?`, `textRu?`, `effectAfter?`, `effectDuring?`, `effectBoost?`, `effectImmediately?`, `effectOngoing?`, `heroId!`, `count: Int!` (все строковые — String, `!` = non-null), `imageUrl?`, `imageUrlRu?`, `createdAt: DateTime!`, `updatedAt: DateTime!`.

**AdminHero**: `id!`, `name!`, `nameEn!`, `nameRu!`, `set!`, `health: Int!`, `fighterType!`, `movement: Int?`, `color?`, `ability?`, `deckCards?`, `properties?`, `hasTokens: Boolean?`, `sidekicks?`, `additionalMinis?`, `imageUrl?`, `avatarUrl?`, `characterCardUrl?`, `miniModelUrl?`, `cards: [AdminCard!]?`, `createdAt: DateTime!`, `updatedAt: DateTime!`.

**AdminBoard**: `id!`, `name!`, `nameEn!`, `nameRu!`, `set!`, `width: Int!`, `height: Int!`, `cells?`, `features?`, `imageUrl?`, `imageUrlDark?`, `createdAt: DateTime!`, `updatedAt: DateTime!`.

**AdminStatsDto**: `totalUsers: Float!`, `totalHeroes: Float!`, `totalCards: Float!`, `totalBoards: Float!`, `totalGames: Float!` (без `() => Int` → Float).

**ImportResultDto**: `success: Boolean!`, `heroesCreated: Float!`, `heroesUpdated: Float!`, `errors: String!` (в схеме присутствует, запросами не используется).

**UserStatsDto**: `gamesPlayed: Int?`, `gamesWon: Int?`, `currentElo: Int?`.

**UserDto**: `id!`, `username!`, `email!`, `avatar?`, `role!`, `createdAt: DateTime!`, `updatedAt: DateTime!`, `deletedAt: DateTime?`, `emailVerified: DateTime?`, `stats: UserStatsDto?`.

**UserListItemDto**: поля идентичны `UserDto`.

**PaginatedUsersDto**: `users: [UserListItemDto!]!`, `total: Float!`, `page: Float!`, `limit: Float!`, `totalPages: Float!`.

**CardListItemDto**: `id!`, `name!`, `nameEn!`, `nameRu!`, `cardType!`, `subType?`, `attackValue: Int?`, `defenseValue: Int?`, `boostValue: Int?`, `bannerName?`, `count: Int!`, `heroId!`, `imageUrl?`, `imageUrlRu?`, `createdAt: DateTime?`.

**CardsPaginatedDto**: `items: [CardListItemDto!]!`, `total/page/limit/totalPages: Float!`.

**GamePlayerInfoDto**: `id!`, `playerId!`, `heroId?`, `status!`, `username?`, `avatar?`.

**GameListItemDto**: `id!`, `code?`, `mode!`, `status!`, `createdAt: DateTime!`, `boardId?`, `boardName?`, `gamePlayers: [GamePlayerInfoDto!]!`.

**AdminGameDto**: `id!`, `code?`, `mode!`, `status!`, `createdAt: DateTime!`, `startedAt: DateTime?`, `finishedAt: DateTime?`, `boardId!`, `boardName?`, `gamePlayers: [GamePlayerInfoDto!]!`.

**GamesPaginatedDto**: `items: [GameListItemDto!]!`, `total/page/limit/totalPages: Float!`.

**CleanupGamesResultDto**: `deleted: Int!`, `aborted: Int!`.

**AuditLogDto**: `id!`, `action!`, `userId?`, `ipAddress?`, `userAgent?`, `success: Boolean!`, `errorMessage?`, `timestamp: DateTime!`, `metadata?` (JSON-строка из userAgent/errorMessage).

**AuditLogsPaginatedDto**: `items: [AuditLogDto!]!`, `total: Float!`.

**QueuePlayerDto**: `id!`, `userId!`, `username!`, `avatar?`, `mode!`, `elo: Int!`, `joinedAt: DateTime!`, `position: Int!`.

**MatchmakingQueueDto**: `items: [QueuePlayerDto!]!`, `total: Float!`, `activeQueues: Float!`.

**HeroListItemDto**: `id!`, `name!`, `nameEn!`, `nameRu!`, `set!`, `health: Float!`, `fighterType!`, `ability?`, `imageUrl?`, `avatarUrl?`, `createdAt: DateTime!`.

**HeroesPaginatedDto** (admin): `items: [HeroListItemDto!]!`, `total/page/limit/totalPages: Float!`.

**BoardListItemDto**: `id!`, `name!`, `nameEn!`, `nameRu!`, `set!`, `width: Float!`, `height: Float!`, `imageUrl?`, `imageUrlDark?`, `createdAt: DateTime!`.

**BoardsPaginatedDto** (admin): `items: [BoardListItemDto!]!`, `total/page/limit/totalPages: Float!`.

### Матчмейкинг

**QueueStatusResponse**: `inQueue: Boolean!`, `mode: String`, `position: Int`, `totalPlayers: Int!`, `estimatedWaitTime: Int!` (секунды), `joinedAt: DateTime`.

**MatchFoundResponse**: `gameId: String!`, `opponentId: String!`, `opponentUsername: String!`, `opponentRating: Int!`, `mode: String!`, `expiresAt: DateTime!`.

**PenaltyInfoDto**: `canJoinQueue: Boolean!`, `declineCount: Int!`, `tempBanUntil: DateTime`, `penaltyElo: Int`, `reason: String`.

### Presence

**Presence**: `userId: String!`, `status: PresenceStatus!`, `currentGameId: String`, `lastSeenAt: Float!` (epoch-ms).
**HeartbeatResponse**: `presence: Presence!`, `ttl: Float!` (300).
**OnlineUsersResponse**: `userIds: [String!]!`, `count: Float!`.

**Итого Object/Interface-типов: 73.**

---

## 5. Input-типы

Формат: поле — тип GraphQL — обязательность — валидация (class-validator). Все `@Field(..., { nullable: true })` сопровождаются `@IsOptional()`.

### Auth

**RegisterDto** (`register`)
- `email: String!` — `@IsEmail`, `@IsNotEmpty`
- `username: String!` — `@IsString`, `@MinLength(3)`, `@MaxLength(20)`, `@Matches(/^[a-zA-Z0-9_]+$/)` (буквы/цифры/подчёркивание), `@IsNotEmpty`
- `password: String!` — `@IsString`, `@MinLength(8)`, `@IsNotEmpty`

**LoginDto** (`login`): `email: String!` (`@IsEmail`, `@IsNotEmpty`); `password: String!` (`@IsString`, `@IsNotEmpty`).

### Игры / лобби

**CreateGameDto**: `mode: GameMode` (optional, `@IsEnum(GameMode)`), `boardId: String` (optional, `@IsString`).

**JoinGameDto**: `gameId: String!` (`@IsString`, `@IsNotEmpty`; cuid, не UUID); `heroId: String` (opt); `asOpponent: Boolean` (opt).

**GameFiltersDto**: `status: GameStatus` (opt, `@IsEnum`), `mode: GameMode` (opt, `@IsEnum`), `limit: Float` (opt, `@IsInt`, `@Min(1)`, `@Max(100)`), `offset: Float` (opt, `@IsInt`, `@Min(0)`).

**PaginationDto** (Relay; в resolver'ах не используется, но в схеме): `after: String`, `before: String`, `first: Int` (`@Min(1)`), `last: Int` (`@Min(1)`) — все optional.

### Игровые действия (все `gameId` — `@IsNotEmpty`)

**PositionInput**: `x: Int!`, `y: Int!` — `@IsInt`, `@Min(0)`, `@Max(19)`.

**ManeuverMoveInput**: `fighterId: String!` (`@IsNotEmpty`, `@IsString`); `path: [PositionInput!]!` (`@IsArray`, `@ValidateNested({each:true})`).

**ManeuverDto**: `gameId: String!`; `fighterId: String` (**deprecated**, legacy-одиночный режим); `moves: [ManeuverMoveInput!]` (ходы нескольких бойцов; приоритетно над legacy); `cardId: String` (**deprecated**); `boostCardId: String` (сброс карты → +boostValue к очкам движения); `path: [PositionInput!]` (**deprecated**).

**MoveFighterDto**: `gameId!`, `fighterId!` (оба `@IsNotEmpty`), `x: Int!`, `y: Int!` (`@IsInt`, `0..19`).

**AttackDto**: `gameId!`, `attackerId!`, `cardId!`, `targetId!` (все `@IsNotEmpty`); `boostCardId: String` (opt).

**PlayDefenseDto**: `gameId!`, `cardId!`; `boostCardId: String` (opt).

**PlaySchemeDto**: `gameId!`, `cardId!`.

**ResolvePendingEffectDto**: `gameId!`, `effectId!`; `fighterId: String` (opt; для MOVE/PLACE); `x: Int`, `y: Int` (opt, `@Min(0)`); `optionIndex: Int` (opt, `@Min(0)`; для CHOOSE_ONE).

**ResolveCombatDto**: `gameId!`. **EndTurnDto**: `gameId!`. **PassDto**: `gameId!`.

**ToggleDoorDto**: `gameId!`, `x: Int!`, `y: Int!` (0..19).

**SetStanceDto**: `gameId!`, `stanceId!` (`@IsNotEmpty`, `@IsString`).

### Профиль

**UpdateProfileDto**: `username: String` (opt, `@MinLength(3)`, `@MaxLength(20)`, `@Matches(/^[a-zA-Z0-9_]+$/)`); `avatar: String` (opt, `@MaxLength(500)`, `@IsUrl`).

**SettingsDto**: `theme: String` (opt, `@IsIn(['light','dark','auto'])`); `language: String` (opt, `@IsIn(['ru','en'])`); `soundEnabled`, `musicEnabled`, `profileVisible`, `showOnlineStatus` — `Boolean` (opt, `@IsBoolean`).

**ChangePasswordDto**: `currentPassword: String!` (`@IsNotEmpty`); `newPassword: String!` (`@IsNotEmpty`, `@MinLength(8)`).

**LeaderboardOptionsDto** (в resolver'ах не используется, в схеме присутствует): `heroId: String` (opt); `timeFrame: TimeFrame` (opt, `@IsEnum`); `limit: Int` (opt, `@IsInt`, `@Min(1)`, `@Max(100)`).

### Матчмейкинг

**JoinQueueDto**: `mode: GameMode!` (`@IsEnum`); `heroPref: String` (opt).

**AcceptMatchDto** (`@ArgsType`): `gameId: String!` (`@IsString`). В схеме разворачивается в аргументы `acceptMatch(gameId: String!)`.

### Админ

**CreateHeroInput**: обязательные `name/nameEn/nameRu/set: String!`, `fighterType: String!` (`@IsString`); `health: Int` (`@IsOptional`, `@IsInt` — фактически nullable в схеме); optional: `movement: Int`, `color`, `ability`, `deckCards`, `properties`, `hasTokens: Boolean`, `sidekicks`, `additionalMinis`, `imageUrl`, `avatarUrl`, `characterCardUrl`, `miniModelUrl` (все String).

**UpdateHeroInput**: все поля optional (nullable) — тот же набор + `health/movement: Int`, `hasTokens: Boolean`.

**CreateCardInput**: обязательные `name/nameEn/nameRu/heroId/cardType: String!`; optional: `subType`, `attackValue/defenseValue/boostValue/count: Int`, `bannerName`, `effects`, `text`, `textEn`, `textRu`, `effectAfter`, `effectDuring`, `effectBoost`, `effectImmediately`, `effectOngoing`, `imageUrl`, `imageUrlRu`.

**UpdateCardInput**: тот же набор, все optional.

**CreateBoardInput**: обязательные `name/nameEn/nameRu/set/cells: String!`; `width/height: Int` (nullable, `@IsInt`); optional `features`, `imageUrl`, `imageUrlDark`.

**UpdateBoardInput**: все optional (`width/height: Int`).

**UpdateUserInput**: `username: String`, `avatar: String`, `email: String`, `role: UserRole` — все optional (`@IsOptional`).

**CleanupGamesInput**: `finishedOlderThanDays: Int` (opt; удаление FINISHED/ABORTED старше N дней, def 7); `abortStuckInProgress: Boolean` (opt; прерывать застрявшие IN_PROGRESS/PAUSED); `stuckMinutes: Int` (opt; порог неактивности в минутах, def 60).

### Presence

**HeartbeatInput**: `status: PresenceStatus` (opt, defaultValue `ONLINE`); `currentGameId: String` (opt).

**GetPresenceInput** (в схеме присутствует, не используется): `userId: String!`.

**Итого Input/Args-типов: 35.**

---

## 6. Enum-типы

| Enum | Значения | Смысл |
|---|---|---|
| **UserRole** (Prisma) | `USER`, `ADMIN`, `MODERATOR` | Роль пользователя. ADMIN — полный доступ (AdminGuard); MODERATOR — аудит (ModeratorGuard). |
| **GameMode** | `ONE_V_ONE`, `TWO_V_TWO`, `FREE_FOR_ALL`, `VS_AI` | Режим игры (VS_AI — против бота). |
| **GameStatus** | `PENDING`, `LOBBY`, `IN_PROGRESS`, `PAUSED`, `FINISHED`, `ABORTED` | Статус игры (жизненный цикл лобби→игра→итог). |
| **GamePhase** (game-engine) | `SETUP`, `TURN_START`, `ACTION_MANEUVER`, `ACTION_ATTACK`, `COMBAT`, `COMBAT_RESOLVE`, `TURN_END`, `GAME_OVER` | Фаза внутри хода/игры: размещение, начало хода, фазы действий (манёвр/атака; 2 действия за ход), ожидание защиты, разрешение боя, конец хода, конец игры. |
| **GameEventType** | `ATTACK_INITIATED`, `DEFENSE_PLAYED`, `COMBAT_RESOLVED`, `TURN_CHANGED`, `PLAYER_JOINED`, `PLAYER_LEFT`, `GAME_ENDED`, `FIGHTER_MOVED`, `DOOR_TOGGLED`, `MANEUVER`, `TURN_ENDED`, `CARD_PLAYED`, `GAME_CREATED`, `GAME_JOINED`, `GAME_STARTED`, `GAME_ABORTED`, `TURN_STARTED`, `PASSED`, `CARD_DISCARDED`, `PLACED`, `EFFECT_APPLIED`, `SPECIAL_ABILITY` | Типы игровых событий (подписки + журнал eventsSince). Включает зеркало Prisma-enum `GameActionType`. |
| **PaginationOrder** | `ASC = 'asc'`, `DESC = 'desc'` | Направление сортировки (в resolver'ах не используется, в схеме есть). |
| **CardType** | `ATTACK = 'attack'`, `DEFENSE = 'defense'`, `VERSATILE = 'versatile'`, `SCHEME = 'scheme'` | Тип карты. |
| **EffectTiming** | `immediately`, `during_combat`, `after_combat`, `start_of_turn`, `end_of_turn`, `when_played`, `when_attacked`, `when_defending` | Момент срабатывания эффекта карты. |
| **AbilityTrigger** | `start_of_turn`, `during_combat`, `passive`, `when_attacked`, `when_defending`, `end_of_turn` | Условие срабатывания способности героя. |
| **FighterType** | `HERO = 'hero'`, `SIDEKICK = 'sidekick'` | Тип бойца. |
| **Zone** | `blue`, `green`, `yellow`, `red`, `purple`, `brown`, `gray`, `orange`, `pink`, `white`, `gold`, `beige` | Цветовые зоны клеток доски. |
| **PresenceStatus** | `offline`, `online`, `ingame`, `inqueue` | Статус присутствия пользователя. |
| **TimeFrame** | `ALL = 'all'`, `WEEK = 'week'`, `MONTH = 'month'` | Период для статистики/лидерборда. |

**Итого Enum: 13.**

---

## 7. Скаляры

| Скаляр | Реализация | Поведение |
|---|---|---|
| **DateTime** | `src/graphql/scalars/date-time.scalar.ts` | Вход: число (epoch-ms) — `parseValue`; литерал `Int`. Выход: **epoch-миллисекунды** (`Date.getTime()`); строки конвертируются. Ошибка сериализации — `GraphQLError`. |
| **JSON** | `src/graphql/scalars/json.scalar.ts` | Прозрачный pass-through (строки/числа/булевы/объекты/списки; прочие литералы → `null`). Зарегистрирован, но в текущих DTO почти не используется — структурированные данные передаются строками JSON (напр. `GameMutationResult.state`). |
| Встроенные | — | `String`, `Int`, `Float`, `Boolean`, `ID`. Прим.: поля TS `number` без `() => Int` сериализуются как `Float` (напр., счётчики в админ-пагинации, `gameSequence`, `getOnlineCount`, `winRate`). |

---

## 8. Формат ошибок

Конфигурация — `formatError` в `src/graphql/graphql.module.ts`.

**Development / не-production** — полная информация:

```json
{
  "message": "<исходное сообщение>",
  "code": "<extensions.code || 'INTERNAL_SERVER_ERROR'>",
  "path": ["maneuver"],
  "locations": [ ... ],
  "extensions": { ... }
}
```

**Production** — бизнес-ошибки проходят, системные скрываются:
- бизнес (проходят как `{message, code, path}`): `extensions.code === 'BAD_USER_INPUT' | 'GRAPHQL_VALIDATION_FAILED'`, либо сообщение содержит `not found` / `unauthorized`;
- прочее → `{ "message": "Internal server error", "code": "INTERNAL_SERVER_ERROR" }`.

**Коды, встречающиеся на практике** (Apollo/Nest маппинг `HttpException` → extensions.code):

| code | Источник | Примеры |
|---|---|---|
| `UNAUTHENTICATED` | GqlAuthGuard (401) | Нет/просрочен JWT. |
| `FORBIDDEN` | AdminGuard/ModeratorGuard, `ForbiddenException` (403) | Не админ; temp-ban матчмейкинга; `Cannot accept/decline match`. |
| `NOT_FOUND` | `NotFoundException` (404) | `Match confirmation has expired`; игра/герой не найдены. |
| `BAD_USER_INPUT` | `BadRequestException` (400), ошибки валидации class-validator | Провал игрового действия (сообщение движка), `Unexpected error during <action>`. |
| `CONFLICT` | `ConflictException` (409) | Конфликт состояния (optimistic concurrency). |
| `GRAPHQL_VALIDATION_FAILED` | Схема/валидация запроса | Неверный тип аргумента. |
| `INTERNAL_SERVER_ERROR` | Прочее (500) | Всё остальное (в prod скрыто). |

Дополнительно:
- **Throttler**: превышение rate-limit → ошибка 429-типа (Too Many Requests) от `@nestjs/throttler`.
- **Complexity/depth**: `Query is too complex: <N>. Maximum allowed complexity is 1000.` (validation rule).
- Логирование: все ошибки логируются (`console.error`), сообщения санитизируются (пароли маскируются `password:***`).
- `stacktrace` в ответе отключён стандартным Apollo-поведением в prod.

---

## Приложение: Cross-check покрытия

Каждый тип, найденный при обходе декораторов (`grep @ObjectType/@InputType/registerEnumType/@InterfaceType/@Scalar` + все `*.resolver.ts`), включён в документ:

- Query (53): heroes, heroesPaginated, hero, cards, card, boards, boardsPaginated, board, contentVersion, sets, heroesBySet, contentSummary, clearContentCache, game, myGames, availableGames, gameState, heroStances, gameSequence, eventsSince, adminStats, adminHero, adminCard, adminBoard, adminUser, usersList, userList, cardsList, cardList, heroesList, heroList, boardsList, boardList, gamesList, gameList, adminGame, auditLogs, matchmakingQueue, me, user, userByUsername, myStats, stats, mySettings, leaderboard, topPlayers, getPlayerRank, queueStatus, allQueueStatus, penaltyInfo, metrics, getPresence, getOnlineUsers, getOnlineCount.
- Mutation (49): register, login, logout, refreshTokens, resetPassword, verifyEmail, createGame, joinGame, leaveGame, startGame, abortGame, toggleReady, selectHero, maneuver, moveFighter, attack, playDefense, playScheme, resolvePendingEffect, resolveCombat, endTurn, pass, toggleDoor, setStance, updateProfile, updateSettings, changePassword, deleteAccount, uploadAvatar, removeAvatar, joinQueue, leaveQueue, leaveAllQueues, acceptMatch, declineMatch, createHero, updateHero, deleteHero, createCard, updateCard, deleteCard, createBoard, updateBoard, deleteBoard, updateUser, banUser, unbanUser, cleanupGames, heartbeat.
- Subscription (10): gameStateUpdated, attackInitiated, defensePlayed, combatResolved, turnChanged, playerJoined, playerLeft, gameEnded, matchFound, presenceUpdated.
- Object/Interface (73), Input/Args (35), Enum (13), скаляры DateTime/JSON — см. разделы 4–7.

Не-GraphQL-типы (TS-интерфейсы без декораторов: `LeaderboardEntry`, `ReplayData`, `AuditEvent`, `GameAction`, `MatchFoundPayload` и т.п.) в схему не входят и в документе описаны только там, где формируют JSON-строки payload'ов.
