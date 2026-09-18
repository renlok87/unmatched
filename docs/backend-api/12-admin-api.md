# 12. Админский API (Admin API)

> Источники: `backend/src/admin/admin.resolver.ts`, `backend/src/admin/admin.service.ts`,
> `backend/src/admin/dto/admin.dto.ts`, `backend/src/admin/guards/admin.guard.ts`,
> `admin/src/**` (React-админка на Refine).

Админская часть GraphQL API реализована в `AdminResolver` и покрывает:
CRUD героев/карт/бордов, управление пользователями (в т.ч. бан/разбан и смена роли),
просмотр игр и аудит-логов, мониторинг очереди матчмейкинга, статистику дашборда
и очистку старых игр.

**Итого: 18 queries и 13 mutations.**

---

## 1. Авторизация и роли

### 1.1. Роли (`UserRole`, Prisma enum)

```prisma
enum UserRole {
  USER        // обычный игрок (default)
  ADMIN       // полный доступ ко всем admin-мутациям
  MODERATOR   // доступ к чтению + auditLogs
}
```

### 1.2. Как выдаётся админ-доступ

Роль хранится в `User.role` в БД. Способов выдачи два:

1. **Сид-скрипт** `backend/prisma/seed-admin.ts` (upsert):
   - `<LOCAL_P1_EMAIL>` / `<LOCAL_P1_PASSWORD>` → `ADMIN`
   - `moderator@unmached.local` / `Moderator123!` → `MODERATOR`
2. **Мутация `updateUser`** — существующий ADMIN может выставить любому
   пользователю `role: ADMIN` / `MODERATOR` / `USER` через админку (страница Users → Edit).

### 1.3. Guard'ы (`backend/src/admin/guards/admin.guard.ts`)

Все операции защищены цепочкой `@UseGuards(GqlAuthGuard, ...)`:

| Guard | Пропускает | Где используется |
|---|---|---|
| `GqlAuthGuard` | Любой авторизованный пользователь (JWT Bearer в заголовке) | Все queries и mutations |
| `AdminGuard` | Только `role === ADMIN` | Все mutations |
| `ModeratorGuard` | `ADMIN` или `MODERATOR` | Только `auditLogs` |

Guard берёт `req.user` из GraphQL-контекста (его туда кладёт JWT-стратегия);
при отсутствии пользователя или роли возвращает `false` → GraphQL-ошибка `FORBIDDEN`.

**Правило доступа:**
- **Чтение** (все queries, кроме `adminStats` и `auditLogs`) — достаточно быть
  авторизованным (любой игрок с валидным JWT может читать списки).
- `adminStats` — только ADMIN.
- `auditLogs` — ADMIN или MODERATOR.
- **Все 13 mutations** — только ADMIN.

Админка (`admin/`) авторизуется через обычный `login` mutation (JWT access +
refresh в localStorage, см. `admin/src/providers/authProvider.ts`); `getPermissions`
возвращает роль из `me { role }`.

---

## 2. Queries (18)

Все пагинированные списки возвращают `{ items | users, total, page, limit, totalPages }`.
Аргументы `page` (с 1), `limit` (по умолчанию 20), `search` (case-insensitive `contains`),
`sortBy`/`sortOrder` — общие; сортировка ограничена whitelist'ом полей (иначе fallback
`createdAt desc`).

### 2.1. `adminStats` — статистика дашборда

- Сигнатура: `adminStats: AdminStatsDto`
- Аргументы: нет.
- Возврат: `{ totalUsers, totalHeroes, totalCards, totalBoards, totalGames: Int! }`
- Авторизация: `GqlAuthGuard + AdminGuard` (ADMIN).
- Действие: параллельные `prisma.*.count()` по пяти таблицам.

```graphql
query { adminStats { totalUsers totalHeroes totalCards totalBoards totalGames } }
```

### 2.2. `adminHero(id: String!): AdminHero`

- Авторизация: любой авторизованный.
- Возвращает героя со всеми полями, включая связанные `cards: [AdminCard]`.
  404 `NotFoundException`, если не найден.
- JSON-поля Prisma (`ability`, `deckCards`, `properties`, `sidekicks`, `additionalMinis`)
  сериализуются в **строки** (`JSON.stringify`) — в GraphQL они `String`.

### 2.3. `heroesList` / 2.4. `heroList` (alias для Refine)

- Сигнатура: `(page: Int, limit: Int, search: String, sortBy: String, sortOrder: String): HeroesPaginatedDto`
- Авторизация: любой авторизованный.
- `search` ищет по `name`, `nameEn`, `nameRu`, `set`. Sort whitelist:
  `createdAt, updatedAt, name, nameEn, nameRu, set, health, fighterType, movement`.
- Возврат `HeroListItemDto`: `id, name, nameEn, nameRu, set, health, fighterType, ability(String), imageUrl, avatarUrl, createdAt` + пагинация.
- `heroList` — идентичный алиас (Refine ожидает имя ресурса в единственном числе).

### 2.5. `adminCard(id: String!): AdminCard`

- Авторизация: любой авторизованный. 404 если нет.
- Полная карта; JSON-поле `effects` сериализуется в строку.

### 2.6. `cardsList` / 2.7. `cardList` (alias)

- Сигнатура: `(page, limit, heroId: String, search, sortBy, sortOrder): CardsPaginatedDto`
- `heroId` — фильтр по герою; `search` — по `name/nameEn/nameRu`.
- Sort whitelist: `createdAt, updatedAt, name, nameEn, nameRu, cardType, subType, attackValue, defenseValue, boostValue, count`.

### 2.8. `adminBoard(id: String!): AdminBoard`

- Авторизация: любой авторизованный. 404 если нет.
- JSON-поля `cells`, `features` — строки.

### 2.9. `boardsList` / 2.10. `boardList` (alias)

- `(page, limit, search, sortBy, sortOrder): BoardsPaginatedDto`
- `search` по `name/nameEn/nameRu/set`. Sort whitelist:
  `createdAt, updatedAt, name, nameEn, nameRu, set, width, height`.
- `BoardListItemDto`: `id, name*, set, width, height, imageUrl, imageUrlDark, createdAt` + пагинация.

### 2.11. `adminUser(id: String!): UserDto`

- Авторизация: любой авторизованный. 404 если нет.
- `UserDto`: `id, username, email, avatar, role, createdAt, updatedAt, deletedAt, emailVerified, stats { gamesPlayed, gamesWon, currentElo }`.
- Пароль не отдаётся (select ограничен).

### 2.12. `usersList` / 2.13. `userList` (alias)

- `(page, limit, search, sortBy, sortOrder): PaginatedUsersDto`
- `search` по `email` и `username`. Sort whitelist: `createdAt, updatedAt, username, email, role`.
- Возврат: `{ users: [UserListItemDto], total, page, limit, totalPages }` (поле называется `users`, не `items`).

### 2.14. `gamesList` / 2.15. `gameList` (alias)

- `(page, limit, search, sortBy, sortOrder): GamesPaginatedDto`
- `search` по `id`, `code` и точному совпадению `status` (если строка — валидное значение enum `GameStatus`).
- Sort whitelist: `createdAt, status, code, mode`.
- Для каждой игры дополнительно догружаются `gamePlayers` (с `username/avatar`, статус `READY|PENDING` по `isReady`)
  и `boardName`. `GameListItemDto`: `id, code, mode, status, createdAt, boardId, boardName, gamePlayers[]`.

### 2.16. `adminGame(id: String!): AdminGame`

- Авторизация: любой авторизованный. 404 если нет.
- То же + `startedAt`, `finishedAt` (`endedAt` в БД).

### 2.17. `auditLogs` — журнал аудита

- Сигнатура: `(page: Int, limit: Int = 50, userId: String): AuditLogsPaginatedDto`
- Авторизация: `GqlAuthGuard + ModeratorGuard` (**ADMIN или MODERATOR**).
- Читает `AuthAuditLog` через `AuditService.getAuditLogsPaginated`. `AuditLogDto`:
  `id, action (=type), userId, ipAddress, userAgent, success, errorMessage, timestamp, metadata(String|null)`
  (metadata собирается из `userAgent`/`errorMessage` в JSON-строку).
- Возврат: `{ items, total }` (без page/totalPages).

```graphql
query { auditLogs(page: 1, limit: 50) { items { id action userId success timestamp } total } }
```

### 2.18. `matchmakingQueue` — очередь матчмейкинга

- Сигнатура: `matchmakingQueue: MatchmakingQueueDto` (без аргументов).
- Авторизация: любой авторизованный.
- Действие: `QueueManagerService.getAllEntries(mode)` для **всех** режимов `GameMode`,
  позиции считаются сортировкой по рейтингу (asc), пользователи догружаются из Prisma.
- Возврат: `{ items: [QueuePlayerDto], total, activeQueues }`;
  `QueuePlayerDto`: `id ("{mode}:{userId}"), userId, username, avatar, mode, elo, joinedAt, position`.

---

## 3. Mutations (13) — все требуют ADMIN

### 3.1. `createHero(input: CreateHeroInput!): AdminHero`

- `CreateHeroInput`: обязательные `name, nameEn, nameRu, set, fighterType: String`, `health: Int`;
  опциональные `movement: Int` (default 2), `color, ability, deckCards, properties, sidekicks, additionalMinis`
  (JSON-строки, парсятся через `JSON.parse`), `hasTokens: Boolean`, `imageUrl, avatarUrl, characterCardUrl, miniModelUrl`.
- Конфликт имени → `ConflictException` (Prisma P2002).
- Некорректный JSON в ability/deckCards/... → 500 (в отличие от бордов, здесь нет мягкой обработки).

### 3.2. `updateHero(id: String!, input: UpdateHeroInput!): AdminHero`

- Все поля `CreateHeroInput`, но nullable — обновляются только переданные (partial update).
- 404, если герой не найден. Возврат — обновлённый герой.

### 3.3. `deleteHero(id: String!): Boolean`

- Сначала каскадно удаляет все связанные карты (`card.deleteMany({ heroId })`), затем героя.
- Возвращает `true`; 404 если героя нет.

### 3.4. `createCard(input: CreateCardInput!): AdminCard`

- Обязательные: `name, nameEn, nameRu, heroId, cardType: String`.
- Опциональные: `subType`, `attackValue/defenseValue/boostValue: Int`, `bannerName`,
  `effects` (JSON-строка, default `[]`), `text/textEn/textRu`, тексты эффектов
  `effectAfter/effectDuring/effectBoost/effectImmediately/effectOngoing`,
  `count: Int` (default 1), `imageUrl`, `imageUrlRu`.
- Проверяет существование героя (`heroId`) → 404 если нет.

### 3.5. `updateCard(id: String!, input: UpdateCardInput!): AdminCard`

- Partial update всех полей выше + смена `heroId` (с проверкой существования героя).
- 404 если карта не найдена.

### 3.6. `deleteCard(id: String!): Boolean`

- Удаляет карту. 404 если нет; иначе `true`.

### 3.7. `createBoard(input: CreateBoardInput!): AdminBoard`

- Обязательные: `name, nameEn, nameRu, set, cells: String` (JSON), `width, height: Int`.
- Опциональные: `features` (JSON), `imageUrl`, `imageUrlDark`.
- **Валидация геометрии**: `parseBoardJson` (невалидный JSON → 400 `BadRequestException`)
  и `assertBoardGeometry` → `validateBoardGeometry` (`backend/src/content/validators/board-geometry.validator`);
  жёсткие ошибки блокируют сохранение, предупреждения (`warn:` prefix) — нет.
- Дубликат имени → 409 `ConflictException`.

### 3.8. `updateBoard(id: String!, input: UpdateBoardInput!): AdminBoard`

- Partial update. Геометрия валидируется по **слиянию** существующей доски и новых полей
  (смена `width/height` не может «сломать» уже сохранённые клетки). 404 если доски нет.

### 3.9. `deleteBoard(id: String!): Boolean`

- Удаляет доску; 404 если нет; иначе `true`.

### 3.10. `updateUser(id: String!, input: UpdateUserInput!): UserDto`

- `UpdateUserInput`: опциональные `username, avatar, email, role: UserRole`.
- Именно так выдаётся/отзывается роль ADMIN/MODERATOR. 404 если пользователя нет.

### 3.11. `banUser(id: String!): Boolean`

- **Soft delete**: ставит `deletedAt = now()` (пользователь сохраняется в БД, но считается забаненным). 404 если нет.

### 3.12. `unbanUser(id: String!): Boolean`

- Снимает бан: `deletedAt = null`.

### 3.13. `cleanupGames(input: CleanupGamesInput): CleanupGamesResult`

- `CleanupGamesInput` (все опциональны):
  - `finishedOlderThanDays: Int` (default **7**) — удалять FINISHED/ABORTED игры без активности старше N дней (по `updatedAt`);
  - `abortStuckInProgress: Boolean` (default false) — прерывать зависшие IN_PROGRESS/PAUSED;
  - `stuckMinutes: Int` (default **60**) — порог неактивности.
- **Безопасность**: PENDING/LOBBY не трогаются никогда (zombie-PENDING — зона ответственности `GameSanityService`).
- Возврат: `{ deleted: Int!, aborted: Int! }`.

```graphql
mutation {
  cleanupGames(input: { finishedOlderThanDays: 14, abortStuckInProgress: true, stuckMinutes: 120 }) {
    deleted
    aborted
  }
}
```

---

## 4. Обмен контентом между админкой и БД (ContentDbService, кэш)

Админка пишет напрямую в Prisma (`Hero/Card/Board`), а **игровое API** читает контент
через `ContentDbService` (`backend/src/content/content-db.service.ts`) с Redis-кэшем:

- Ключи кэша: `content:heroes:all`, `content:boards:all`, `content:heroes:{id}`,
  `content:heroes:slug:{slug}`, `content:boards:{id}`, `content:heroes:set:{set}`,
  `content:sets:all`, `content:summary`.
- TTL кэша — **1 час** (`CACHE_TTL = 3600`); полностью отключается env `DISABLE_CACHE=true`.
- **Версионирование**: константа `CONTENT_VERSION = '2.0.0'` (инкрементируется вручную при
  изменениях структуры контента). Клиенты могут сверять версию через `contentSummary`
  и получить `contentDiff(oldVersion)` — при несовпадении версий возвращаются все
  `changedHeroIds`/`changedBoardIds` как изменённые.
- **Важно**: admin-мутации **не инвалидируют** Redis-кэш автоматически — изменения,
  сделанные в админке, доезжают до игроков либо по истечении TTL (до 1 часа), либо после
  ручного `clearCache()` (используется в content-резолвере).

JSON-поля (`ability`, `effects`, `cells` и т.д.) ходят через GraphQL как **строки**:
сервис сериализует объекты из Prisma в JSON-строки при чтении и парсит строки при записи.

---

## 5. Страницы админки (admin/, Refine + react-router)

| Страница (роут) | Файл | Используемые операции |
|---|---|---|
| Login (`/login`) | `pages/login.tsx` | `login`, `refreshTokens`, `me`, `logout` |
| Dashboard (`/`) | `pages/dashboard.tsx` | `adminStats` |
| Heroes (`/heroes`, `/show`, `/create`, `/edit`) | `pages/heroes/*` | `heroesList`/`heroList`, `adminHero`, `createHero`, `updateHero`, `deleteHero` |
| Cards (`/cards`…) | `pages/cards/*` | `cardsList`/`cardList`, `adminCard`, `createCard`, `updateCard`, `deleteCard` |
| Boards (`/boards`…) | `pages/boards/*` | `boardsList`/`boardList`, `adminBoard`, `createBoard`, `updateBoard`, `deleteBoard` |
| Users (`/users`, `/show`, `/edit`) | `pages/users/*` | `usersList`/`userList`, `adminUser`, `updateUser`, `banUser`, `unbanUser` |
| Games (`/games`, `/show`) | `pages/games/*` | `gamesList`/`gameList`, `adminGame` (только чтение; `cleanupGames` доступен через API/дашборд) |
| Matchmaking (`/matchmaking`) | `pages/matchmaking/list.tsx` | `matchmakingQueue` |
| Audit Logs (`/audit-logs`) | `pages/audit-logs/list.tsx` | `auditLogs` (MODERATOR+) |
| Game Tester (`/game-tester`) | `pages/game-tester/*` | игровое API (не admin-резолвер) |

Общие компоненты: `dataProvider.ts` (маппинг Refine-ресурсов на GraphQL-операции),
`authProvider.ts` (JWT-логин/refresh), `JsonEditor`/`JsonViewer` (редактирование
JSON-полей — `ability`, `effects`, `cells` — как текст).

---

## 6. Типовые примеры

```graphql
# Список героев с поиском и сортировкой
query {
  heroesList(page: 1, limit: 20, search: "cobble", sortBy: "name", sortOrder: "asc") {
    items { id name set health fighterType imageUrl }
    total totalPages
  }
}

# Создание карты
mutation {
  createCard(input: {
    name: "Shield Block", nameEn: "Shield Block", nameRu: "Блок щитом",
    heroId: "clx...", cardType: "ACTION", defenseValue: 3,
    effects: "[{\"type\":\"BLOCK\",\"value\":3}]", count: 2
  }) { id name cardType }
}

# Бан пользователя
mutation { banUser(id: "clx...") }
```

## 7. Сводная таблица операций

| # | Операция | Тип | Роль | Назначение |
|---|---|---|---|---|
| 1 | `adminStats` | query | ADMIN | счётчики дашборда |
| 2 | `adminHero` | query | auth | герой + его карты |
| 3 | `heroesList` | query | auth | пагинированный список героев |
| 4 | `heroList` | query | auth | alias #3 (Refine) |
| 5 | `adminCard` | query | auth | карта |
| 6 | `cardsList` | query | auth | список карт (+фильтр heroId) |
| 7 | `cardList` | query | auth | alias #6 |
| 8 | `adminBoard` | query | auth | борд |
| 9 | `boardsList` | query | auth | список бордов |
| 10 | `boardList` | query | auth | alias #9 |
| 11 | `adminUser` | query | auth | пользователь + статистика |
| 12 | `usersList` | query | auth | список пользователей |
| 13 | `userList` | query | auth | alias #12 |
| 14 | `gamesList` | query | auth | список игр с игроками и бордом |
| 15 | `gameList` | query | auth | alias #14 |
| 16 | `adminGame` | query | auth | детали игры |
| 17 | `auditLogs` | query | MODERATOR+ | журнал аудита |
| 18 | `matchmakingQueue` | query | auth | очередь матчмейкинга по всем режимам |
| 19 | `createHero` | mutation | ADMIN | создать героя |
| 20 | `updateHero` | mutation | ADMIN | изменить героя |
| 21 | `deleteHero` | mutation | ADMIN | удалить героя (+его карты) |
| 22 | `createCard` | mutation | ADMIN | создать карту |
| 23 | `updateCard` | mutation | ADMIN | изменить карту |
| 24 | `deleteCard` | mutation | ADMIN | удалить карту |
| 25 | `createBoard` | mutation | ADMIN | создать борд (+валидация геометрии) |
| 26 | `updateBoard` | mutation | ADMIN | изменить борд |
| 27 | `deleteBoard` | mutation | ADMIN | удалить борд |
| 28 | `updateUser` | mutation | ADMIN | профиль/роль пользователя |
| 29 | `banUser` | mutation | ADMIN | бан (soft delete) |
| 30 | `unbanUser` | mutation | ADMIN | разбан |
| 31 | `cleanupGames` | mutation | ADMIN | удаление старых и прерывание зависших игр |
