# R6-admin — Админ-API и веб-админка: что остаётся, что нужно UE-клиенту, кэш контента, Game Tester как эталон e2e, статусы незавершённых фич

> Ридер R6-admin. Дата: 2026-09-02. Ветка `fix/admin-panel`.
> Источники перечислены в §5; в тексте ссылки вида `файл:строка`. Пути относительны корня репозитория `C:/Users/ren/WebstormProjects/unmached/unmached/`, кроме явно абсолютных. Всё, что не подтверждено источником, помечено «не найдено».

---

## 1. Краткое резюме

1. **Веб-админка (Refine + Ant Design + urql, порт 5480) остаётся как есть и целиком.** Это единственный UI для CRUD контента (герои/карты/доски с JSON-редакторами и валидатором геометрии доски), управления пользователями (роли ADMIN/MODERATOR/USER, бан = soft delete), мониторинга игр/очереди матчмейкинга/аудит-логов, очистки старых игр и текстового прогона партии (Game Tester). Ни одна из этих функций в UE-клиент не переносится (`docs/backend-api/12-admin-api.md:7-12`, `admin/src/App.tsx:54-153`).
2. **Из 31 админской операции UE-клиенту нужны ровно две read-only query — `heroList`/`heroesList` и `boardList`/`boardsList`** (обе только под JWT любого авторизованного игрока, без роли ADMIN), потому что только они отдают **Prisma cuid** героя/доски, а игровые мутации `selectHero(heroId)` и `createGame(boardId)` принимают именно cuid (`backend/src/games/game.service.ts:310-322`, `backend/src/games/services/game-initialization.service.ts:85-94`). Публичные контентные query `heroes`/`hero`/`boards` отдают `id = name` (`backend/src/content/mappers/content.mapper.ts:59,195,251`). Все 13 admin-мутаций и `adminStats`/`auditLogs` UE не нужны.
3. **`contentVersion` — НЕ админ-API**, это публичная контентная query, возвращающая захардкоженную константу `CONTENT_VERSION = '2.0.0'` (`backend/src/content/content-db.service.ts:12`, `content.resolver.ts:144-148`). Она **не меняется при правках в админке**, поэтому как сигнал инвалидации клиентского кэша бесполезна: правки контента через админку не отражаются ни в версии, ни в Redis-кэше (admin-сервис кэш не трогает — grep `cache|redis|invalidat` по `backend/src/admin/admin.service.ts` = 0 совпадений). Кэш живёт 1 час (`CACHE_TTL = 3600`, `content-db.service.ts:17`); `clearContentCache` — публичная (без guard!) query, чистящая только 4 агрегатных ключа, но не per-id/slug ключи (`content-db.service.ts:429-442`, `content.resolver.ts:177-185`).
4. **Расхождение источников контента**: инициализация партии (`GameInitializationService`) и валидация героя читают Prisma напрямую, минуя кэш (`game-initialization.service.ts:85-128`), а контентные query для рендера — через Redis-кэш. Значит, после правки карты в админке новая партия уже играет новыми данными, а UE-клиент может показывать устаревший арт/значения до 1 часа.
5. **Game Tester (`admin/src/pages/game-tester/`) — рабочий эталон e2e-прогона через реальный GraphQL API**: два JWT (P1 = админ из localStorage, P2 = `<LOCAL_P2_EMAIL> / <LOCAL_P2_PASSWORD>`), полный лобби-флоу `createGame → joinGame → selectHero×2 → toggleReady×2 → startGame → gameState`, затем текстовые команды, 1:1 отображённые на gameplay-мутации. Он показывает точный порядок вызовов, формат `state` (JSON-строка), как читать руку (`handZones[userId].cards`), как определять актора (`currentTurnPlayerId` / `combatInfo.defenderId`). Не покрывает `setStance`, `leaveGame`, подписки WS и не печатает `manualEffects`.
6. **Статусы фич (по планам + истории коммитов)**: план починки админки — выполнен; план «оставшиеся фичи» — блок A (эффекты карт, BOOST, banner) и блок B (web-фронт) выполнены, из блока C выполнены мультизонность, pendingEffects (MOVE/PLACE/CHOOSE_ONE), манёвр всех бойцов, VS_AI-бот, attackType; **не сделаны**: токены героев, оригинальные раскладки досок (геометрия сгенерирована), e2e матчмейкинга, удаление deprecated web-кода. Способности героев: 29 из ~70 (3 хардкод + 26 config), остаток — 11 подсистем (ресурсы, токены, стойки прочих героев, identity-cycle, под-колоды, призыв, movement-override, rules-override, ауры, resurrect, info-reveal), большинству нужен выбор игрока на клиенте. Парсер текстов карт: 240/712 карт (34%) до v7; точная цифра после v7 не найдена. Всё это напрямую определяет, какие UI-состояния UE-клиент должен уметь показывать уже сейчас, а какие — закладывать на будущее.

---

## 2. Факты по фокусу

### 2.1. Авторизация и роли админ-API

| Факт | Источник |
|---|---|
| Prisma enum `UserRole { USER, ADMIN, MODERATOR }`; USER — default | `docs/backend-api/12-admin-api.md:18-26` |
| Роль выдаётся (а) сидом `backend/prisma/seed-admin.ts` (upsert `<LOCAL_P1_EMAIL> / <LOCAL_P1_PASSWORD>` → ADMIN, `moderator@unmached.local / Moderator123!` → MODERATOR), (б) мутацией `updateUser(id, input:{role})` существующим ADMIN | `backend/prisma/seed-admin.ts:9-21,32-45`; `12-admin-api.md:28-36` |
| Цепочка guard'ов: `GqlAuthGuard` (любой JWT) → `AdminGuard` (только `role === ADMIN`) / `ModeratorGuard` (ADMIN или MODERATOR). Guard берёт `req.user` из GraphQL-контекста; нет пользователя/роли → `false` → GraphQL-ошибка FORBIDDEN | `backend/src/admin/guards/admin.guard.ts:10-40,46-76`; `12-admin-api.md:38-49` |
| **Правило доступа**: все query, кроме `adminStats` (ADMIN) и `auditLogs` (MODERATOR+), доступны **любому авторизованному игроку**; все 13 мутаций — только ADMIN | `12-admin-api.md:51-56`; декораторы `backend/src/admin/admin.resolver.ts:49-384` |
| Админка логинится обычной `login`-мутацией, хранит `accessToken`/`refreshToken` в `localStorage` под ключами `accessToken`/`refreshToken`; refresh — мутация `refreshTokens(refreshToken)`; `getPermissions` — из `me { role }` | `admin/src/providers/authProvider.ts:45-52,66-67,160-161`; `12-admin-api.md:58-60` |
| Админка ходит на `VITE_BACKEND_URL=http://localhost:3000`, `VITE_WS_URL=ws://localhost:3000/graphql`; dev-порт 5480 | `admin/.env:2-3`; `admin/vite.config.ts:8` |

Замечание безопасности (не влияет на UE, но фиксируется): `usersList`/`userList`/`adminUser` (с e-mail всех пользователей), `gamesList`, `matchmakingQueue` (вся очередь всех режимов с userId/elo) читаются любым авторизованным игроком — `admin.resolver.ts:152-172,297-323,383-384`; `12-admin-api.md:52-53,123-133,161-168`.

### 2.2. Полный перечень операций admin-API (18 queries + 13 mutations)

Общие правила пагинированных списков: `{ items | users, total, page, limit, totalPages }`; `page` с 1, `limit` default 20, `search` — case-insensitive `contains`; `sortBy` из whitelist, иначе fallback `createdAt desc` (`12-admin-api.md:66-69`).

| # | Операция | Тип | Роль | Нужно UE? | Ключевые детали | Источник |
|---|---|---|---|---|---|---|
| 1 | `adminStats` | query | ADMIN | нет | 5 параллельных `count()` | `12-admin-api.md:71-81`; `admin.resolver.ts:49-50` |
| 2 | `adminHero(id)` | query | auth | нет | герой + `cards`; JSON-поля `ability, deckCards, properties, sidekicks, additionalMinis` — **строки** | `12-admin-api.md:83-89` |
| 3/4 | `heroesList` / `heroList` | query | auth | **ДА** | `(page, limit, search, sortBy, sortOrder)`; search по `name, nameEn, nameRu, set`; `HeroListItemDto: id(cuid), name, nameEn, nameRu, set, health, fighterType, ability(String), imageUrl, avatarUrl, createdAt` | `12-admin-api.md:91-98`; `07-graphql-schema-reference.md:79-80,408-410` |
| 5 | `adminCard(id)` | query | auth | нет | `effects` — строка | `12-admin-api.md:100-103` |
| 6/7 | `cardsList` / `cardList` | query | auth | нет (опц.) | `(page, limit, heroId, search, sortBy, sortOrder)`; фильтр по `heroId` (cuid) | `12-admin-api.md:105-109` |
| 8 | `adminBoard(id)` | query | auth | нет | `cells`, `features` — строки | `12-admin-api.md:111-114` |
| 9/10 | `boardsList` / `boardList` | query | auth | **ДА** | `BoardListItemDto: id(cuid), name*, set, width, height, imageUrl, imageUrlDark, createdAt` | `12-admin-api.md:116-121` |
| 11 | `adminUser(id)` | query | auth | нет | `UserDto` со `stats { gamesPlayed, gamesWon, currentElo }` | `12-admin-api.md:123-127` |
| 12/13 | `usersList` / `userList` | query | auth | нет | поле называется `users`, не `items` | `12-admin-api.md:129-133` |
| 14/15 | `gamesList` / `gameList` | query | auth | нет | `search` по `id`, `code`, точному `status`; догружает `gamePlayers` и `boardName` | `12-admin-api.md:135-141` |
| 16 | `adminGame(id)` | query | auth | нет | + `startedAt`, `finishedAt` | `12-admin-api.md:143-146` |
| 17 | `auditLogs(page, limit=50, userId)` | query | MODERATOR+ | нет | `{ items, total }`, читает `AuthAuditLog` | `12-admin-api.md:148-159`; `admin.resolver.ts:340-341` |
| 18 | `matchmakingQueue` | query | auth | нет | `QueueManagerService.getAllEntries` по всем `GameMode`; `{ items, total, activeQueues }` | `12-admin-api.md:161-168` |
| 19–21 | `createHero` / `updateHero` / `deleteHero` | mutation | ADMIN | нет | JSON-поля парсятся `JSON.parse` (невалидный JSON → 500); `deleteHero` каскадно удаляет карты | `12-admin-api.md:174-190` |
| 22–24 | `createCard` / `updateCard` / `deleteCard` | mutation | ADMIN | нет | `effects` — JSON-строка, default `[]`; `updateCard` умеет менять `heroId` | `12-admin-api.md:192-208` |
| 25–27 | `createBoard` / `updateBoard` / `deleteBoard` | mutation | ADMIN | нет | валидация геометрии `validateBoardGeometry` (`backend/src/content/validators/board-geometry.validator`): невалидный JSON → 400, жёсткие ошибки блокируют, `warn:` — нет; `updateBoard` валидирует слияние | `12-admin-api.md:210-226` |
| 28 | `updateUser(id, input:{username, avatar, email, role})` | mutation | ADMIN | нет | выдача/отзыв ролей | `12-admin-api.md:228-231` |
| 29/30 | `banUser` / `unbanUser` | mutation | ADMIN | нет | soft delete: `deletedAt = now()` / `null` | `12-admin-api.md:233-239` |
| 31 | `cleanupGames(input:{finishedOlderThanDays=7, abortStuckInProgress=false, stuckMinutes=60})` | mutation | ADMIN | нет | удаляет FINISHED/ABORTED по `updatedAt`, опц. abort IN_PROGRESS/PAUSED; PENDING/LOBBY не трогает; `{ deleted, aborted }` | `12-admin-api.md:241-257`; `admin.resolver.ts:328-329` |

### 2.3. Страницы веб-админки (что остаётся)

Полный список файлов `admin/src/pages/` (31 файл) и маршруты `admin/src/App.tsx`:

| Раздел | Файлы | Роуты (`App.tsx`) | Операции | Источник |
|---|---|---|---|---|
| Login | `login.tsx` | `/login` (L113) | `login`, `refreshTokens`, `me`, `logout` | `12-admin-api.md:287` |
| Dashboard | `dashboard.tsx` | `/` index (L116) | `adminStats`, список последних игр | `12-admin-api.md:288` |
| Heroes | `heroes/{list,show,create,edit}.tsx`, `index.ts` | `/heroes`, `/heroes/show/:id`, `/heroes/create`, `/heroes/edit/:id` (L119-122) | `heroList`, `adminHero`, `createHero`, `updateHero`, `deleteHero` | `12-admin-api.md:289` |
| Cards | `cards/{list,show,create,edit}.tsx`, `index.ts` | `/cards…` (L125-128) | `cardList`, `adminCard`, `createCard`, `updateCard`, `deleteCard` | `12-admin-api.md:290` |
| Boards | `boards/{list,show,create,edit}.tsx`, `index.ts` | `/boards…` (L131-134) | `boardList`, `adminBoard`, `createBoard`, `updateBoard`, `deleteBoard` | `12-admin-api.md:291` |
| Users | `users/{list,show,edit}.tsx`, `index.ts` | `/users`, `/users/show/:id`, `/users/edit/:id` (L137-139) | `userList`, `adminUser`, `updateUser`, `banUser`, `unbanUser` | `12-admin-api.md:292` |
| Games | `games/{list,show}.tsx`, `index.ts` | `/games`, `/games/show/:id` (L142-143) | `gameList`, `adminGame`, **кнопка «Cleanup old games» → `cleanupGames`** | `admin/src/pages/games/list.tsx:33-34,151-177,297` |
| Game Tester | `game-tester/{GameTester.tsx,api.ts,index.ts}` | `/game-tester` (L146) | игровое API + `heroList`/`boardList` для справочников | `game-tester/api.ts:73-87` |
| Matchmaking | `matchmaking/list.tsx`, `index.ts` | `/matchmaking` (L149) | `matchmakingQueue` | `12-admin-api.md:294` |
| Audit Logs | `audit-logs/list.tsx`, `index.ts` | `/audit-logs` (L152) | `auditLogs` | `12-admin-api.md:295` |

Ресурсы Refine (`App.tsx:54-102`): `heroes`, `cards`, `boards` (canDelete), `users`, `games`, `matchmakingQueue`, `auditLogs`. `dataProvider.ts` маппит ресурсы на GraphQL-документы (`admin/src/providers/dataProvider.ts:19-449`: `GetHeroesList`, `GetHero`, `GetCardsList`, `GetCard`, `GetBoardsList`, `GetBoard`, `GetUsersList`, `GetUser`, `GetGame`, `GetGamesList`, `GetMatchmakingQueue`, `GetAuditLogs`, `CreateHero/UpdateHero/DeleteHero`, `CreateCard/UpdateCard/DeleteCard`, `CreateBoard/UpdateBoard/DeleteBoard`, `UpdateUser`).

Незакоммиченные правки в рабочем дереве (git diff): `heroes/create.tsx` и `heroes/edit.tsx` добавляют поля формы `characterCardUrl` и `miniModelUrl`, переименовывают лейбл `Image URL` → `Card Back URL` (диф `admin/src/pages/heroes/create.tsx` +12/−2, `edit.tsx` +16/−2). `miniModelUrl` — `.glb` (`05-engine-and-content.md:365`) — потенциальный источник 3D-моделей миниатюр для UE.

**Вывод по «что остаётся в админке»**: всё. UE-клиент не дублирует ни один экран админки. Единственная точка соприкосновения — read-only списки `heroList`/`boardList` (см. §2.4) и, косвенно, `miniModelUrl`/`characterCardUrl` героя как ассеты.

### 2.4. Что из admin-API нужно UE-клиенту

| Потребность | Почему нельзя обойтись публичным контентным API | Решение | Источник |
|---|---|---|---|
| **Prisma cuid героя для `selectHero(gameId, heroId)`** | `validateHeroId` делает `prisma.hero.findUnique({ where: { id: heroId } })` → нужен cuid. Публичные `heroes`/`heroesPaginated`/`hero` отдают `HeroDto.id = hero.name` (`prismaHeroToHeroDto` L59, `prismaHeroToHeroDefinition` L195); поля с cuid в `HeroDto` нет (поля L104-154: `id, name, nameEn, nameRu, health, movement, set, abilities, cards, fighterType, sidekickCount, sidekickHealth, urls, imageUrl, avatarUrl, createdAt, updatedAt`); `CardDto` не содержит `heroId` | `heroList(page:1, limit:300, sortBy:"name", sortOrder:"asc") { items { id name health fighterType } }` под JWT игрока — ровно так делает Game Tester и web-RoomView | `backend/src/games/game.service.ts:310-322`; `content.mapper.ts:59,195`; `content.dto.ts:104-154`; `game-tester/api.ts:73-79`; память `game-tester-and-logic-gaps.md:52` |
| **Prisma cuid доски для `createGame(input:{mode, boardId})`** | `GameInitializationService` берёт `prisma.board.findUnique({ where: { id: game.boardId } })`; публичный `boards` отдаёт `id = board.name` (L251) | `boardList(page:1, limit:100, sortBy:"name", sortOrder:"asc") { items { id name width height } }` | `game-initialization.service.ts:85-92`; `content.mapper.ts:251`; `game-tester/api.ts:81-87` |
| Сопоставление cuid ↔ контент для рендера | `GameState.fighters[].heroId` = cuid, `heroSlug` = slugify(name); `game.players[].heroId` = cuid. Контентный `hero(id)` принимает **cuid ИЛИ имя** (`getHeroBySlug` OR `{ id: slug }` / `{ name: equals, insensitive }`) — **но эта правка НЕ закоммичена** (git diff `content-db.service.ts:182-190`) | использовать `hero(id: <cuid>)` после коммита правки, либо `hero(id: <name>)` по `fighter.name`/`heroSlug`; `heroStances(heroSlug)` — по слагу из `ABILITY_CONFIGS` | `content-db.service.ts:176-199`; `docs/backend-api/05-engine-and-content.md:389,405`; `backend/src/games/game.resolver.ts:100-109` |
| `contentVersion` / `contentSummary` | это **публичный контентный API**, не admin | см. §2.5 — как сигнал изменений непригоден | `content.resolver.ts:144-148,171-175` |
| Admin-мутации, `adminStats`, `auditLogs`, `matchmakingQueue`, `gamesList`, `usersList` | не нужны игровому клиенту | не использовать | `12-admin-api.md:330-362` |

Итого: из admin-резолвера UE использует только `heroList` и `boardList` (можно — `cardList(heroId)` для обзора колоды по cuid, но то же даёт публичный `hero(id).cards`).

### 2.5. Кэш `ContentDbService` и инвалидация

Константы и ключи (`backend/src/content/content-db.service.ts`):

| Элемент | Значение | Строка |
|---|---|---|
| `CONTENT_VERSION` | `'2.0.0'` — «Increment when content changes» (вручную) | 9-12 |
| `CACHE_TTL` | `3600` с (1 час) | 14-17 |
| `CACHE_DISABLED` | `process.env.DISABLE_CACHE === 'true'` → `getFromCache` возвращает `null`, `setCache` no-op | 22, 54-57, 67-70 |
| Ключи | `content:heroes:all`, `content:boards:all`, `content:heroes:{id}`, `content:heroes:slug:{slug}`, `content:boards:{id}`, `content:heroes:set:{set}`, `content:sets:all`, `content:summary` | 27-36 |
| Ошибки Redis | `get`/`setex` в try/catch → warn-лог, сервис продолжает работать без кэша | 58-64, 71-75 |

Какие методы кэшируются, а какие читают Prisma напрямую:

| Метод | Кэш | Кто вызывает (GraphQL) | Строки |
|---|---|---|---|
| `getAllHeroes()` | да, `content:heroes:all` (маппер `prismaHeroToHeroDto`) | `heroes`, `getContentDiff` | 89-105 |
| `getHeroesPaginated(page, limit, set?)` | **нет** | `heroesPaginated` | 110-146 |
| `getHeroById(id)` | да, `content:heroes:{id}` | (внутренний; после незакоммиченной правки `getCardsByHero` переведён на `getHeroBySlug`) | 152-171 |
| `getHeroBySlug(slug)` | да, `content:heroes:slug:{slug}`; поиск `OR [{id: slug}, {name equals insensitive}]` (id-ветка — незакоммичена) | `hero(id)`, `cards(heroId)`, field-resolver `Hero.cards` | 176-199; `content.resolver.ts:25-29,75-83,88-92` |
| `getHeroesBySet(set)` | да | `heroesBySet` | 204-220 |
| `getCardById(id)` | **нет** | `card(id)` | 235-245 |
| `getAllBoards()` | да, `content:boards:all` | `boards`, `getContentDiff` | 252-266 |
| `getBoardsPaginated` | **нет** | `boardsPaginated` | 271-299 |
| `getBoardById(id)` | да | (внутренний) | 305-323 |
| `getBoardBySlug(slug)` | **нет** (по `name` insensitive) | `board(id)` | 328-340; `content.resolver.ts:131-139` |
| `getDefaultBoard()` | нет (`getBoardBySlug('cobble-city')`) | — | 345-347 |
| `getAllSets()` | да | `sets`, `getContentSummary` | 377-394 |
| `getContentSummary()` | да, `content:summary` (`{ version, heroesCount, boardsCount, setsCount, sets }`) | `contentSummary` | 399-422; DTO `content.dto.ts:245-260` |
| `getContentDiff(oldVersion)` | — | **не экспонирован в GraphQL** (нет `@Query`; в списке 53 query его нет) | 354-370; `07-graphql-schema-reference.md:601` |
| `clearCache()` | удаляет **только** `ALL_HEROES, ALL_BOARDS, ALL_SETS, SUMMARY` — per-id/slug/set ключи остаются до TTL | `clearContentCache` (`@Query`, `@Public()`, без guard) | 429-442; `content.resolver.ts:177-185` |

Инвалидация при правках в админке:

- `AdminService` пишет в Prisma напрямую и **не инжектит ни `ContentDbService`, ни Redis** — grep `ContentDbService|contentDb|redis|cache|invalidat` по `backend/src/admin/admin.service.ts` и `admin.module.ts` дал 0 совпадений. Док подтверждает: «admin-мутации не инвалидируют Redis-кэш автоматически — изменения доезжают до игроков по истечении TTL (до 1 часа) либо после ручного `clearCache()`» (`12-admin-api.md:274-276`).
- `CONTENT_VERSION` при этом не меняется, т.е. `contentVersion`/`contentSummary.version` **не сигнализируют** о правках через админку; `getContentDiff` при несовпадении версий возвращает «всё изменилось» (`heroesChanged: true, boardsChanged: true`, все id) — `content-db.service.ts:354-370`, интерфейс `backend/src/content/interfaces/content-diff.interface.ts:5-12`.
- Док 07 фиксирует недочёт: `clearContentCache` «помечено `@Public()`, хотя комментарий обещает admin-only» (`07-graphql-schema-reference.md:48`; комментарий в коде `content.resolver.ts:178`).
- Второй, статический `ContentService` (`content/content.service.ts`, definition-файлы `content/data/*.ts`) всё ещё в провайдерах модуля (`content.module.ts:15-28`) и используется `turn-management.service.ts:111` (`contentService.getHeroById(player.heroId)` в try/catch). Док 05 называет его «локальный fallback» (`05-engine-and-content.md:387`).

Источник контента для **самой партии** (важно для рассинхрона с кэшем):

- `GameInitializationService.initializeGameState` читает `prisma.game.findUnique` (L85), `prisma.board.findUnique({ id: game.boardId })` (L90), `prisma.gamePlayer.findMany` (L94), `prisma.hero.findUnique` с картами (L121), отказывает, если у героя нет карт (L128), и собирает колоду из `hero.cards` × `count` (L195) — **без кэша**.
- `setupAiOpponent` (VS_AI) выбирает героя `prisma.hero.findMany({ where: { cards: { some: {} } } })` — сильнейшего по `health` (`game.service.ts:745-770`).

### 2.6. Game Tester как эталон e2e-прогона

Архитектура (`admin/src/pages/game-tester/GameTester.tsx`, `api.ts`):

| Аспект | Факт | Источник |
|---|---|---|
| Транспорт | raw `fetch` на `${VITE_BACKEND_URL}/graphql` (default `http://localhost:3000`), `Authorization: Bearer <token>` при наличии; GraphQL-ошибки (`json.errors`) превращаются в `GqlError` с объединёнными сообщениями | `api.ts:7,15-33` |
| Два токена | P1 — админ, токен из `localStorage.accessToken`, userId декодируется из JWT (`sub`/`userId`/`id`); P2 — `<LOCAL_P2_EMAIL>` / `tester2` / `<LOCAL_P2_PASSWORD>`, сперва `login`, при неудаче `register` | `GameTester.tsx:98-100,146-156,158-190`; `api.ts:36-45,51-67` |
| Справочники | `heroList(page:1, limit:300, sortBy:"name", sortOrder:"asc") { items { id name health fighterType } }`, `boardList(page:1, limit:100, …) { items { id name width height } }` — под admin-токеном; по умолчанию герои P1/P2 = первые два, доска = первая | `api.ts:73-87`; `GameTester.tsx:429-440` |
| Сетап («Сетап игры») | `createGame(input:{mode: ONE_V_ONE, boardId})` (P1) → `joinGame(input:{gameId})` (P2) → `selectHero(gameId, heroId)` P1, P2 → `toggleReady(gameId)` P1, P2 → `startGame(gameId)` (P1) → `gameState(gameId)` под обоими токенами | `GameTester.tsx:448-499`; `api.ts:105-151` |
| Поля ответа лобби-мутаций | `id code status mode hostId boardId phase currentTurn players { id userId username heroId isReady seatOrder }` | `api.ts:93-103` |
| Поля ответа gameplay-мутаций | `state sequenceNumber timestamp phase currentTurnPlayerId turnCount`; `state` — JSON-строка полного состояния | `api.ts:157-164` |
| Чтение руки | `JSON.parse(state).handZones[userId].cards` (cards может быть строкой → второй `JSON.parse`); рука видна только владельцу → состояние запрашивается под каждым токеном | `GameTester.tsx:327-333,339-361` |
| Определение актора («auto») | ход — `slotByUserId(state.currentTurnPlayerId)`; защита — `state.metadata.combatInfo.defenderId` (это **userId**), иначе «не текущий» игрок | `GameTester.tsx:204-226` |
| Сводка состояния | `turnCount, phase, currentTurnPlayerId, metadata.actionsRemaining (default 2), sequenceNumber`; игроки `health/maxHealth/isAlive`; бойцы `name, type, attackType ('ranged'→🏹), health/maxHealth, position{x,y}, ownerId, effects[]`; бой `combatInfo.attackerId → defenderId, attackValue, defenseValue` | `GameTester.tsx:251-280` |
| Дифф состояний | фаза, ход, действия, смена хода, +боец, HP бойца, позиция бойца, HP игрока | `GameTester.tsx:282-313` |
| Ссылки | бойцы `f<index>` по порядку в `state.fighters` (или id/префикс/имя), карты `c<index>` по порядку в руке актора | `GameTester.tsx:365-391` |

Отображение команд на мутации (`GameTester.tsx:503-698`, документы `api.ts:166-224`):

| Команда | Мутация / input | Строки |
|---|---|---|
| `state [raw]` | `gameState(gameId)` | 522-530 |
| `hand [p1|p2]` | `gameState` под токеном игрока | 531-543 |
| `move <f> <x> <y>` | `moveFighter(input:{gameId, fighterId, x, y})` — тратит 1 действие | 544-553 |
| `maneuver <f> [<c>|-] <x>,<y> […]` | `maneuver(input:{gameId, fighterId, boostCardId|null, path[{x,y}]})` | 554-587 |
| `attack <f1> <f2> <c> [<boost>]` | `attack(input:{gameId, attackerId, targetId, cardId, boostCardId|null})` | 588-603 |
| `defense <c> [<boost>]` | `playDefense(input:{gameId, cardId, boostCardId|null})` — от защищающегося | 604-617 |
| `scheme <c>` | `playScheme(input:{gameId, cardId})` | 618-627 |
| `resolve` | `resolveCombat(input:{gameId})` | 628-634 |
| `pending` | печатает `metadata.pendingEffects[] {id, type, value, text}` | 635-646 |
| `peffect <id> <f> <x>,<y>` | `resolvePendingEffect(input:{gameId, effectId, fighterId, x, y})` (MOVE/PLACE; для CHOOSE_ONE в тестере команды нет — `optionIndex` не передаётся) | 647-659 |
| `end` / `pass` | `endTurn(input:{gameId})` / `pass(input:{gameId})` | 660-669 |
| `door <x> <y>` | `toggleDoor(input:{gameId, x, y})` | 670-678 |
| `abort` | `abortGame(gameId)` (P1) | 679-686 |
| `help` | справка `HELP_TEXT` (2 действия за ход; после 2-го — авто-завершение) | 72-90, 509-512 |

Покрытие относительно полного набора gameplay-мутаций (`backend/src/games/resolvers/game-actions.resolver.ts`: `maneuver, moveFighter, attack, playDefense, playScheme, resolvePendingEffect, resolveCombat, endTurn, pass, toggleDoor, setStance`; `game.resolver.ts`: `createGame, joinGame, leaveGame, startGame, abortGame, toggleReady, selectHero`): **не покрыты** `setStance`, `leaveGame`, резолв `CHOOSE_ONE` через `optionIndex`; grep `manualEffects|appliedEffects|stance` по `GameTester.tsx`/`api.ts` = 0 совпадений (план A4 шаг 6 обещал печать `appliedEffects`/`manualEffects` — `2026-06-12-remaining-features.md:263`, не реализовано). WS-подписки тестер не использует (только HTTP polling по команде).

Node-скрипты e2e — тот же паттерн вне браузера (`backend/scripts/`): `e2e-card-effects.mjs` (15 КБ), `e2e-choose-one.mjs`, `e2e-vs-ai-setup.mjs`, `e2e-vs-ai-play.mjs`, `e2e-vs-ai-defense.mjs`, `setup-test-game.mjs`. Общие приёмы: учётки `<LOCAL_P1_EMAIL>/<LOCAL_P1_PASSWORD>` и `<LOCAL_P2_EMAIL>/<LOCAL_P2_PASSWORD>` (`e2e-card-effects.mjs:17-19`); перед стартом **прибирание активных игр** — `myGames { id status }` → `abortGame` для статусов `LOBBY | IN_PROGRESS | PENDING` из-за лимита 5 активных игр (`MaxActiveGamesException`) (`e2e-card-effects.mjs:58-66`; `setup-test-game.mjs:22-27`; `2026-06-12-remaining-features.md:485`); поиск героя через `heroList(limit:5, search)` с комментарием «heroList — Prisma-идентификаторы (контентный `heroes` отдаёт id=name)» (`e2e-card-effects.mjs:68-77`); `setup-test-game.mjs` печатает `gameId, code, accessToken/refreshToken` обоих игроков для ручной проверки клиента (`setup-test-game.mjs:44-52`).

### 2.7. Статусы фич из планов (`docs/plans/*.md`) и влияние на UE

#### 2.7.1. `2026-06-10-admin-panel-fix.md` — починка админки

- Цель/архитектура: React 18 + Refine v5 + AntD + urql; 3 слоя (бэкенд-контракт admin-модуля, провайдеры, страницы) + верификация + сиды (`:5-7`). Контракт: `adminUser`, `adminGame`, `gameList` с `code/mode/boardName`, `UpdateCardInput.heroId`, JSON-поля — строки, `refreshTokens`, реальный `matchmakingQueue`, серверная пагинация `auditLogs` (`:19-33`).
- **Статус: выполнен** — коммиты `1107114 fix(admin): рабочая админка…`, `20eea80 fix(backend): admin-модуль…`, `0641577`, `2ec9a01`, `47824f7 feat(admin): вкладка Game Tester`, `3fb8d7d feat(admin): очистка старых игр + валидация геометрии доски` (git log `admin/`, `backend/src/admin/`). Фаза 4 (сиды) сделана точечным скриптом `backend/prisma/update-scraped-data.ts` без пересоздания id (память `unmatched-launch-procedure.md:37`).
- Влияние на UE: контракт admin-API стабилен и задокументирован; JSON-поля в admin-ответах — строки (не нужно UE).

#### 2.7.2. `2026-06-12-remaining-features.md` — «оставшиеся фичи»

| Блок | Содержание | Статус | Источник статуса |
|---|---|---|---|
| A0–A8 (бэкенд: эффекты карт) | `targetFighterId`, `heroSlug`, DSL `CardEffect` (21 EffectType), парсер текстов + backfill, executor (reveal/cancel/during/after), BOOST в манёвре/атаке/защите, BLIND BOOST, bannerName-валидация, чистка `initializeDeck` | **выполнен целиком** (9 коммитов b4a531c..e86755a; 712/880 карт получили effects) | план `:53-335`; память `game-tester-and-logic-gaps.md:40-47`; git `b4a531c`, `0471d8e`, `272396a` |
| B0–B5 (web-фронт) | `PlayScheme`-документ, лобби, `gameStateAdapter`, `remoteGameStore v2`, действия кликами, боевой цикл, deprecated-маркировка | выполнен для web (коммиты 8872c8e, e49fac2, 83eb611); B5-удаление deprecated-кода — не сделано | план `:339-446`; память `:49`; план `:459` |
| C1 мультизонность `Cell.zones[]` | «та же зона» = пересечение списков; DSL `SHARES_ZONE…`; Ms. Marvel 6/9 | **сделано** (коммит `5576fec`) | план `:452`; git log; память `:53` |
| C2 pendingEffects | `metadata.pendingEffects` (wire `m.pe`), `resolvePendingEffect` для MOVE/PLACE; протухают при возврате хода владельцу; + CHOOSE_ONE с `optionIndex` (коммит `5d91bef`) | **сделано** (коммит `b4c4b57`, `5d91bef`) | план `:453`; память `:55,65`; git log |
| C3 манёвр всех бойцов | `ManeuverDto.moves[]` (legacy `fighterId+path` жив), единый +1 seq | **сделано** | план `:454`; память `:56` |
| C4 оригинальные раскладки досок | геометрия сгенерирована backfill'ом (`backfill-board-cells.ts`, сетки 12×7..12×10, препятствия 5–15% детерминированно); реальных сеток в scraped нет | **не сделано** — вводить вручную через админку Boards (валидатор геометрии есть с 14.06) | план `:455`; память `:25,96`; `engine-gaps-batch-2026-06-14.md:8` |
| C5 VS_AI-бот | см. 2.7.5 | **сделано** (Inc 1–3 + полировка) | план `:456`; git `1a2d437` |
| C6 attackType null у 14 героев | SQL → явный `'melee'` | **сделано** («уточнять через админку») | план `:457`; память `:54` |
| C7 Matchmaking e2e | модуль полный (queue-manager/scheduler/confirmation/penalty), «не проверен с новой игровой логикой» | **не сделано** — подтверждений e2e не найдено | план `:458` |
| C8 токены героев, «look at hand», swap spaces | парсер v2/v3 | **не сделано** (токены — «design-heavy, отложены») | план `:459`; `engine-gaps-batch:9`; память `:82` |
| C9 удаление deprecated web-кода | — | не сделано | план `:460` |

Факты о данных, важные для UE (план `:18-24`): 880 карт (VERSATILE 348, ATTACK 267, SCHEME 151, DEFENSE 114); 84 героя (melee 53 / range 17 / null 14 → после C6 все melee/ranged); сайдкики у 68; `Hero.ability` Json `{type: CUSTOM|VILLAIN|MINION, timing: PASSIVE, effect}`; `Board.cells` у 30/30 досок.

Wire-контракты (план `:341-347`, актуальны для UE-адаптера): query/mutation → `state: string` (одна JSON-строка `{ gameId, sequenceNumber, phase, turnCount, currentTurnPlayerId, players[], fighters[], decks{}, discardPiles{}, handZones{}, boardState{}, metadata{} }`); подписка `gameStateUpdated` → те же данные, но `players/fighters/handZones/boardState/metadata` — **пять отдельных JSON-строк, без `decks/discardPiles`** (merge из предыдущего снапшота); каждое событие — полный снапшот. `combatInfo.attackerId` = fighterId, `defenderId` = **userId**, `targetFighterId` — боец-цель. Карты соперника приходят с `name: '???'` без значений. Фазы: `SETUP|TURN_START|ACTION_MANEUVER|ACTION_ATTACK|COMBAT|COMBAT_RESOLVE|TURN_END|GAME_OVER`; после `startGame` бэк сам расставляет бойцов и ставит `ACTION_MANEUVER`.

#### 2.7.3. `engine-gaps-batch-2026-06-14.md`

| Задача | Статус | Источник |
|---|---|---|
| A — TURN_START-хук в prod-потоке (`advanceTurn` → `triggerOnTurnStartExtended`) | сделано, коммит `ba64a88` | план `:13-16`; память `:74` |
| B — парсер v7 (`unless`, `do both`, `and`-цепочки, adjacency-heal) | сделано, коммит `c47aeeb`; покрытие до v7 — 240/712 (34%, коммит `5d91bef`), цифра после v7 в источниках **не найдена** | план `:18-20`; git log `c47aeeb`, `5d91bef` |
| C — `cleanupGames` + кнопка в admin Games | сделано, коммит `3fb8d7d` | план `:22-24`; `games/list.tsx:33,151-177,297` |
| D — `board-geometry.validator` (границы, дубли (x,y), реципрокность connections по направлениям up/down/left/right, 12 канонических зон — неизвестное warn, ref-ы дверей/secretPassages/highGround) + wiring в create/updateBoard | сделано, коммит `3fb8d7d` | план `:26-28`; память `:77` |
| Коррекции: `initializeDeck` — не гэп (удалён в A8); Board admin CRUD — уже есть; токены / per-hero abilities (50) / choose-one opponent-targeting — отложены как design-heavy | — | план `:5-9` |

#### 2.7.4. `hero-abilities-framework-2026-06-14.md` — способности героев

- Prod-геймплей только через `GameActionExecutorService`; живые хуки: классический combat `applyCombatModifier` (суммируется только ADD), `onTurnStart` (extended), stateful combat `getStatefulCombatModifiers`, `onTurnEnd`, after-attack `triggerOnAfterCombat`, `after-defense` (инфра без героя), `canAttackAtRange`, aura `getAuraCombatModifiers`, `onFighterDefeated`, `onFighterMoved`. Из мёртвых остался `onCombat` (`:7-16,46`).
- Декларативный `AbilityConfig {heroId(slug), abilityName, description, rules[], attackRange?, stances[]}`; добавить героя = одна строка в `ABILITY_CONFIGS` (`backend/src/game-engine/abilities/ability-config.ts:436`) (`:18-25`).
- **Покрытие: 29/~70 героев** (3 хардкод daredevil/ms-marvel/king-arthur + 26 config: luke-cage, annie-christmas, eredin, bloody-mary, philippa, t-rex, bigfoot, chupacabra, deadpool, michelangelo, angel, golden-bat, ancient-leshen, raphael, robin-hood, leonardo, dracula, medusa, bullseye, bruce-lee, raptors, achilles, oda-nobunaga, tomoe-gozen, muhammad-ali, alice) (`:27-54`; README 07 «ВСЕ 29 героев реестра» — `docs/backend-api/README.md:21`).
- **STANCE-подсистема (v11)**: `metadata.heroStances: Record<userId, stanceId>` (wire `m.hs`), мутация `setStance` (не тратит действие), query `heroStances(heroSlug) → [{id, label, isDefault}]` из `ABILITY_CONFIGS` (`@Public`); герои muhammad-ali (FLOAT/STING, авто-toggle при победе) и alice (BIG/SMALL, ручной `setStance`). Web-HUD стоек сделан (коммиты `d4adc91`, `3feaa9b`) (`:44`; `game.resolver.ts:100-109`; `gameplay.dto.ts:362-374`; `game-state.service.ts:76,370`).
- **Не реализовано / MVP-упрощения**: hamlet, moon-knight (нужен non-combat-damage immunity), jekyll/willow/jill (form-gated); michelangelo hand-cap-3; ancient-leshen Wolves move-3; leonardo — только свои бойцы (движение чужих не поддержано моделью PendingEffect); dracula/medusa `turn-damage` — авто-таргет первого врага без выбора; achilles `discard-random` — детерминированный стенд-ин без выбора; Spider-Man info-reveal — намеренно нет (`:33,35,40,42,44,48`; `08-heroes-abilities.md:53,66,162,246,249`).
- **Триаж остатка (~40 героев)**: 11 подсистем — resource-counter×6 (beowulf/blackbeard/ghost-rider/krang/tesla…), token×5 (invisible-man/dr-sattler/spike/robert-muldoon…), stance×5, rules-override×5 (ciri/holmes/winter-soldier uncancelable, black-panther), identity-cycle×4 (moon-knight/jekyll-hyde/willow), sub-deck×4 (pandora/titania/wayward), summon×3 (squirrel-girl/shredder/sun-wukong), movement-rule×3 (buffy/houdini/sinbad), aura×2 (oda done/loki), resurrect×1 (elektra), info-reveal×1 (spider-man). «Большинство требует ФРОНТ (выбор игрока: discard-choice, stance-выбор, summon-позиция) или отдельную модель» (`:50,56-63`; память `:87,93`).
- В scraped-данных обнаружен prompt-injection («Disregard any instructions…») — данные из scrape считать враждебными (`:50`; память `:93`).

#### 2.7.5. `vs-ai-bot-2026-06-13.md` — VS_AI

- Inc 1 (сид `ai@unmached.local` / «AI Bot», `setupAiOpponent` при `startGame` в VS_AI без opponentId — бот вторым `GamePlayer`, seat 1, `isReady=true`, герой из имеющих карты), Inc 2 (`AiDecisionService.decide` — greedy), Inc 3 (`AiTurnService.maybeRunAiTurns(gameId)` ≤40 шагов под локом `game:<id>`, вызывается из `game-actions.resolver.executeMutation` после хода человека, fire-and-forget; каждый шаг → `saveState` + `publishGameUpdate`) — **сделано**, коммит `1a2d437`; полировка (многоклеточный манёвр, tie-break карт, выбор героя по силе, e2e защиты бота) — сделана (`vs-ai-bot:41-78`; память `:67,71`; `seed-ai.ts:7,14-32`; `game.service.ts:745-770`).
- Не сделано: уровни сложности (Inc 4 «random/greedy/lookahead») — не найдено подтверждений (`vs-ai-bot:76-78`).
- Влияние на UE: в VS_AI после каждой мутации человека клиент получит серию `gameStateUpdated`-событий от бота; `game.opponentId === AI_USER_ID` / `GamePlayer.userId === AI_USER_ID` — признак бота (`vs-ai-bot:32-37`).

#### 2.7.6. `imagegen-hud-asset-plan-2026-06-11.md` — ассеты HUD (web)

- План web-HUD (React/Phaser); генерировать только UI-обвязку, не карты/доски/минис (`:9-11`).
- Предпосылки по API, на момент плана: «текущие GraphQL game-queries отдают только геометрию доски, не URL картинок» (`:75`), нужно добавить `imageUrl/imageUrlRu` в карты `HeroDetails.cards` и `imageUrl` в `Board` (`:77-102`). **Статус**: `Card.imageUrl/imageUrlRu` и `Board.imageUrl` есть в контентных DTO (`05-engine-and-content.md:443,458-459,469`); незакоммиченный диф `content.mapper.ts:79-81` добавляет `imageUrl/imageUrlRu` в карты `HeroDto.cards`; web-запрос `Hero.cards { imageUrl imageUrlRu }` уже в `src/gql/gql.ts:22`.
- **Где лежат ассеты**: в `public/assets/**` фронтенда (Vite `publicDir`), URL в БД — корневые пути `/assets/…`, **бэкенд Nest их не раздаёт** (grep `static|assets|useStaticAssets` по `backend/src/main.ts`, `app.module.ts` = 0). Паттерны: карта EN `/assets/decks/<heroSlug>/<cardSlug>.webp`, RU `/assets/decks/<heroSlug>/ru/<cardSlug>-ru.png`, аватар `/assets/heroes/<heroSlug>/avatar.webp`, мини `/assets/heroes/<heroSlug>/mini.webp`, обложка `/assets/heroes/<heroSlug>/card-cover.webp`, доска `/assets/boards/<boardSlug>.webp`; манифест `public/assets/decks/card-assets.generated.json` (`05-engine-and-content.md:476-511`). Ранние сиды содержат абсолютные Supabase-URL (`backend/prisma/seed.ts:68-69`) — в БД могут быть оба вида.

#### 2.7.7. Прочие известные ограничения бэкенда (из доков), влияющие на клиент

| Ограничение | Источник |
|---|---|
| Auto-resolve боя по таймауту (`DEFAULT_DEFENSE_TIMEOUT = 30` с, `DEFAULT_RESOLVE_TIMEOUT = 10` с): интеграция с CombatResolver — TODO, урон при чистом таймауте не применяется | `10-mechanics-deep-dive.md:133` |
| PLACE-эффект: зонные ограничения — TODO | `10-mechanics-deep-dive.md:266` |
| `HeroDto.movement` захардкожен `3` (TODO) — реальное значение только в `Fighter.movement` (default 2) | `05-engine-and-content.md:396` |
| Ms. Marvel: движение в начале хода — «активация отдельной мутацией», авто-хук no-op; препятствия/двери — TODO | `08-heroes-abilities.md:237` |
| choose-one таргетинг: только свои бойцы; нет выбора фигуры оппонента | память `:94` |
| Эффекты карт «поверхностные»: сложные тексты → `UNSUPPORTED` → `manualEffects` (игра не блокируется) | план `:48`; память `:95` |
| Лимит 5 активных игр на юзера (`MaxActiveGamesException`) | план `:485` |

### 2.8. Незакоммиченные изменения рабочего дерева, влияющие на контракты

`git diff --stat` по admin/backend-content: 8 файлов, +45/−8.

| Файл | Суть | Влияние |
|---|---|---|
| `backend/src/content/content-db.service.ts:182-190` | `getHeroBySlug`: `OR: [{ id: slug }, { name … }]` — принимает cuid И имя; `getCardsByHero` → через `getHeroBySlug` | без этого `hero(id: <cuid>)` возвращает `null` — UE не сможет резолвить контент по `players[].heroId`/`fighters[].heroId` |
| `backend/src/content/mappers/content.mapper.ts:79-81` | `imageUrl`, `imageUrlRu` в картах `HeroDto.cards` | арты карт в `hero(id).cards` |
| `admin/src/pages/heroes/{create,edit}.tsx` | поля `characterCardUrl`, `miniModelUrl`; лейбл «Card Back URL» | админ сможет проставить URL 3D-модели миниатюры (`.glb`) |
| `backend/src/content/data/heroes/{daredevil,ms-marvel}.ts`, `backend/prisma/seed-scraped.ts`, `update-card-images.ts` | правки статических definition/сидов | не для UE |

Память фиксирует, что рабочее дерево «смешано с чужими правками», коммитить надо явными путями (`game-tester-and-logic-gaps.md:69,91`). Деплой бэка: `docker exec unmatched-backend npm run build && docker compose restart backend` (bind mount, образ не пересобирать) (`unmatched-launch-procedure.md:33`).

### 2.9. Окружение и тестовые учётки (для e2e из UE)

| Элемент | Значение | Источник |
|---|---|---|
| Бэкенд | `http://localhost:3000/graphql` (HTTP), `ws://localhost:3000/graphql` (graphql-transport-ws); `curl http://localhost:3000/health` → database+redis up | `docs/backend-api/README.md:29-30`; `unmatched-launch-procedure.md:29` |
| Postgres / Redis | 5433 / 6379 (конфликт с WSL redis-server) | `unmatched-launch-procedure.md:12-13` |
| Web-фронт / админка | 5174 / 5480 | `unmatched-launch-procedure.md:23-24` |
| Админ / модератор | `<LOCAL_P1_EMAIL> / <LOCAL_P1_PASSWORD>`, `moderator@unmached.local / Moderator123!` | `seed-admin.ts:9,33` |
| Тестовые игроки | `test1@unmatched.com … veteran@unmatched.com / password123` (5 шт.) | `backend/prisma/seed.ts:21-47` |
| Tester2 | `<LOCAL_P2_EMAIL> / <LOCAL_P2_PASSWORD>` (создаётся Game Tester'ом через `register`) | `GameTester.tsx:98-100,173-189` |
| AI-бот | `ai@unmached.local`, username «AI Bot», role USER, паролем не логинится | `seed-ai.ts:7,14-32` |
| Объём БД | ≈84 героя / 880 карт / 30 досок / 9 юзеров; порядок сидов: `prisma db seed` → `seed-admin` → `seed-scraped` (`--transpile-only`) → `seed-all-scraped` → `fix-card-gaps` → `fix-audit-findings` | `unmatched-launch-procedure.md:14-20` |
| Pre-commit hook сломан → `--no-verify` | `unmatched-launch-procedure.md:35` |

---

## 3. Следствия для UE-клиента

1. **Не реализовывать в UE ничего из админки.** Контент, пользователи, роли, бан, аудит, очистка игр, мониторинг очереди — только веб-админка (§2.3). UE-клиент — «игрок», и все его токены — обычные USER.
2. **Обязательные вызовы admin-резолвера — только `heroList` и `boardList`** (JWT игрока, без ролей): они единственные отдают Prisma cuid, требуемые `selectHero(gameId, heroId)` и `createGame(input:{boardId})` (§2.4). Реализовать в UE «справочник id»: `name → cuid` для героев и досок, загружаемый после логина (`limit: 300` / `100`, как в Game Tester `api.ts:73-87`). Нельзя подставлять `id` из публичных `heroes`/`boards` (там `id = name`).
3. **Контент для рендера — публичные `heroes`/`hero(id)`/`boards`/`board(id)`/`heroStances(heroSlug)`** без токена; сопоставление с состоянием партии — по `fighter.name`/`heroSlug`/`players[].heroId`. Резолв `hero(id: <cuid>)` работает только после коммита/деплоя правки `content-db.service.ts:182-190` (§2.8) — до этого использовать `hero(id: <name>)`.
4. **Клиентский кэш контента нельзя строить на `contentVersion`.** Версия — константа `'2.0.0'`, не меняется при правках через админку; `contentDiff` не экспонирован; Redis-кэш сервера живёт до 1 часа и не сбрасывается admin-мутациями (§2.5). Рекомендации: (а) считать контент «мягко-стабильным» — перезапрашивать при старте клиента и при входе в партию; (б) для критичных значений (HP, значения карт, движение) — **источник истины только `GameState`** (`fighters[].health/maxHealth/movement/attackType`, `handZones[].cards[].attackValue/defenseValue/boostValue`), контент — только для арта/текста; (в) по `updatedAt` героя (`HeroDto.updatedAt`, `content.dto.ts:153-154`) можно инвалидировать локальный кэш точечно, помня, что сам ответ может быть кэшированным до 1 часа; (г) для dev-стенда — `DISABLE_CACHE=true` на бэке или вызов публичной `clearContentCache` (чистит только агрегаты; `hero(id)`/`heroesBySet` остаются в кэше до TTL).
5. **Ассеты грузить не с бэкенда**: URL в БД — корневые пути `/assets/…`, раздаёт их web-фронт (Vite `public/`) или CDN; Nest статику не отдаёт (§2.7.6). UE-клиенту нужен настраиваемый `AssetBaseUrl` (например `http://localhost:5174`) для относительных путей и прямая загрузка абсолютных `https://…supabase…` URL; предусмотреть fallback-рендер карты без арта. `miniModelUrl` (`.glb`) — потенциальный источник 3D-миниатюр, проставляется в админке (незакоммиченные поля формы).
6. **Эталон e2e = Game Tester + `backend/scripts/*.mjs`.** Для UE-автотестов повторить их сценарий: логин двух аккаунтов → abort активных игр (лимит 5) → `heroList`/`boardList` → `createGame → joinGame → selectHero×2 → toggleReady×2 → startGame → gameState` → gameplay-мутации с полями `state sequenceNumber timestamp phase currentTurnPlayerId turnCount` → `JSON.parse(state)`; актор защиты — `metadata.combatInfo.defenderId` (userId). Ожидания: `sequenceNumber` строго +1 на мутацию; 2 действия за ход с авто-`advanceTurn`; `resolveCombat` передаёт ход только при `actionsRemaining = 0`.
7. **UI-состояния, которые UE обязан поддерживать уже сейчас** (фичи бэкенда готовы): pendingEffects трёх типов — `MOVE`/`PLACE` (выбор бойца+клетки, `resolvePendingEffect{effectId, fighterId, x, y}`) и `CHOOSE_ONE` (кнопки `options[{index,label}]`, `chooseCount`, `resolvePendingEffect{effectId, optionIndex}`); стойки (`heroStances`, `metadata.heroStances`, `setStance`); BOOST-карта в манёвре/атаке/защите (`boostCardId`); манёвр несколькими бойцами (`ManeuverDto.moves[]`); двери (`toggleDoor`); `manualEffects` в `ActionResult.metadata` — показывать игроку текст неисполненного эффекта; VS_AI — серия событий бота после каждого хода человека.
8. **Закладывать расширяемость под незавершённые подсистемы** (§2.7.4): выбор карты для сброса (the-genie/she-hulk), выбор позиции призыва, токены на клетках (`boardState.tokens/fog` структурно есть, типов нет), ресурс-счётчики героя, под-колоды, identity-cycle. Не реализовывать заранее конкретную механику — правил в бэкенде нет; проектировать HUD так, чтобы новый тип `PendingEffect` добавлялся без переделки.
9. **Известные дыры бэкенда, которые клиент должен переживать**: auto-resolve по таймауту без урона (`10:133`), `HeroDto.movement = 3` (брать из `Fighter.movement`), сгенерированная геометрия досок (рендер по `Board.spaces`/`boardState.cells`, а не по картинке), карты с `UNSUPPORTED`-эффектами.
10. **Game Tester не покрывает `setStance`, `leaveGame`, CHOOSE_ONE-резолв и WS-подписки** — для этих сценариев в UE опираться на `backend/scripts/e2e-choose-one.mjs` и доки 04/06/07; при необходимости расширить Game Tester (админка остаётся) командами `stance`, `choose`.

---

## 4. Открытые вопросы / несоответствия

1. **`contentDiff` в доке 12 vs код.** `12-admin-api.md:270-273` говорит «клиенты могут… получить `contentDiff(oldVersion)`», но GraphQL-query с таким именем нет: в `content.resolver.ts` нет `@Query` для `getContentDiff`, в списке 53 query (`07:601`) его нет. Есть только сервисный метод `content-db.service.ts:354-370`.
2. **`clearContentCache` публичная.** Комментарий «admin only» (`content.resolver.ts:178`), реальность — `@Query` + `@Public()` без guard (`:180-185`); док 07 это фиксирует как недочёт (`07:48`), док 05 называет «admin-инструмент» (`05:424`). Любой аноним может сбрасывать кэш. Решение (guard/перенос в admin-резолвер) — не найдено.
3. **`clearCache()` неполный**: чистит 4 агрегатных ключа, но не `content:heroes:{id}`, `content:heroes:slug:{slug}`, `content:boards:{id}`, `content:heroes:set:{set}` (`content-db.service.ts:429-442`) — `hero(id)` после правки в админке остаётся устаревшим до 1 часа даже после `clearContentCache`.
4. **`CONTENT_VERSION` статична.** Комментарий «Increment when content changes» (`:9-11`) — ручной процесс; нигде не найден механизм авто-инкремента при admin-мутациях. Для UE-инвалидации нужна либо версия из БД (например `max(updatedAt)`), либо инвалидация кэша в `AdminService` — ни того, ни другого нет.
5. **cuid vs name — правка не закоммичена.** `getHeroBySlug` с `OR [{ id }, { name }]` присутствует только в рабочем дереве (git diff `content-db.service.ts:182-190`), а доки 05 (`:389`) описывают её как факт. До коммита/деплоя `hero(id: <cuid>)` → `null`.
6. **Валидирует ли `createGame` `boardId`?** Найдено только, что инициализация делает `prisma.board.findUnique({ id: game.boardId })` при непустом `boardId` (`game-initialization.service.ts:90`) и что Game Tester передаёт `boardId` из `boardList` (cuid). Поведение при передаче имени доски или несуществующего id — не найдено.
7. **Игра читает контент минуя кэш** (`game-initialization.service.ts:85-128`), а клиент — через кэш (§2.5). Возможен рассинхрон «арт/текст карты в UE ≠ значения в партии» до 1 часа после правки в админке. Нужен ли `clearCache` в admin-мутациях — открытый продуктовый вопрос.
8. **Статический `ContentService`** (`content/content.service.ts`, definition-файлы `content/data/heroes/*.ts` — есть незакоммиченные правки daredevil/ms-marvel) всё ещё в DI и используется `turn-management.service.ts:111`. Является ли `turn-management` prod-путём (память утверждает, что prod — только `GameActionExecutorService`, `hero-abilities-framework:7`) — не проверено в этом ридере.
9. **Доступ к спискам пользователей любым игроком.** `usersList`/`adminUser` (e-mail, роль, `deletedAt`), `gamesList`, `matchmakingQueue` — только `GqlAuthGuard` (`admin.resolver.ts:152-172,297-323,383-384`; `12:52-53`). Для публичного UE-клиента это утечка PII; исправление не найдено.
10. **Место кнопки cleanup.** `12-admin-api.md:293` говорит «`cleanupGames` доступен через API/дашборд», фактически кнопка «Cleanup old games» на странице Games (`admin/src/pages/games/list.tsx:151-177,297`), в `dashboard.tsx` мутации нет (grep `cleanupGames` по `admin/src` — только `games/list.tsx`).
11. **Game Tester не печатает `manualEffects`/`appliedEffects`**, хотя план A4 шаг 6 это требовал (`2026-06-12-remaining-features.md:263`; grep по `GameTester.tsx` = 0). Формат `ActionResult.metadata.manualEffects` в доке 04 не найден (grep `manualEffects` по `04-game-api.md` = 0) — для UE нужно уточнить контракт по коду executor'а (вне scope R6).
12. **Покрытие парсера после v7** — не найдено (последняя цифра 240/712 в коммите `5d91bef`; коммит `c47aeeb` цифру не приводит).
13. **Уровни сложности VS_AI (Inc 4)** — подтверждений реализации не найдено (`vs-ai-bot:76-78`).
14. **`HeroListItemDto.health: Float!`** в доке 07 (`:408`) при `health: Int` в Prisma/доке 12 (`:97` не уточняет тип) — расхождение типов в доках; для UE — парсить как число.
15. **Двойные Supabase-URL vs `/assets/…`.** Базовый сид пишет абсолютные Supabase-URL (`seed.ts:68-69`), скрипты `update-*-images.ts` — пути `/assets/…` «только если поле ещё не заполнено» (`05:379`). Какой формат у каждого героя/карты в живой БД — не проверялось; UE должен поддерживать оба.

---

## 5. Источники

Документация:
- `docs/backend-api/12-admin-api.md` (полностью)
- `docs/backend-api/05-engine-and-content.md:365-424, 476-511, 600-646`
- `docs/backend-api/07-graphql-schema-reference.md:44-48, 79-80, 364, 408-410, 601`
- `docs/backend-api/08-heroes-abilities.md:53, 66, 162, 237, 246, 249`
- `docs/backend-api/10-mechanics-deep-dive.md:133, 266`
- `docs/backend-api/README.md:9-32`
- `docs/unreal/00-mcp-verification.md` (контекст UE MCP)

Планы:
- `docs/plans/2026-06-10-admin-panel-fix.md` (полностью)
- `docs/plans/2026-06-12-remaining-features.md` (полностью)
- `docs/plans/engine-gaps-batch-2026-06-14.md` (полностью)
- `docs/plans/hero-abilities-framework-2026-06-14.md` (полностью)
- `docs/plans/vs-ai-bot-2026-06-13.md` (полностью)
- `docs/plans/imagegen-hud-asset-plan-2026-06-11.md:1-120`

Код бэкенда:
- `backend/src/admin/admin.resolver.ts` (декораторы L49-384), `backend/src/admin/guards/admin.guard.ts`, `backend/src/admin/admin.service.ts` (grep), `backend/src/admin/admin.module.ts` (grep)
- `backend/src/content/content-db.service.ts` (полностью), `backend/src/content/content.resolver.ts` (полностью), `backend/src/content/content.module.ts`, `backend/src/content/mappers/content.mapper.ts:54-59, 79-81, 189-195, 214-218, 242-251`, `backend/src/content/dto/content.dto.ts:104-154, 245-260`, `backend/src/content/interfaces/content-diff.interface.ts:5-12`, `backend/src/common/decorators/public.decorator.ts`
- `backend/src/games/game.service.ts:310-322, 745-770`, `backend/src/games/services/game-initialization.service.ts:85-128, 195`, `backend/src/games/game.resolver.ts:97-109`, `backend/src/games/dto/gameplay.dto.ts:362-374`, `backend/src/games/game-state.service.ts:76, 370`, `backend/src/games/resolvers/game-actions.resolver.ts` (имена мутаций), `backend/src/game-engine/services/turn-management.service.ts:109-117`, `backend/src/game-engine/abilities/ability-config.ts:436`
- `backend/prisma/seed.ts:9-47, 68-69`, `backend/prisma/seed-admin.ts`, `backend/prisma/seed-ai.ts`
- `backend/scripts/e2e-card-effects.mjs:1-77`, `backend/scripts/setup-test-game.mjs` (полностью), список `backend/scripts/`

Код админки:
- `admin/src/App.tsx` (полностью), `admin/src/pages/**` (список файлов), `admin/src/pages/game-tester/GameTester.tsx` (полностью), `admin/src/pages/game-tester/api.ts` (полностью), `admin/src/pages/games/list.tsx:33-34, 151-177, 297`, `admin/src/providers/dataProvider.ts:19-449` (имена операций), `admin/src/providers/authProvider.ts:45-52, 66-67, 160-161`, `admin/.env`, `admin/vite.config.ts:8`

Git:
- `git log` по `docs/plans/`, `admin/`, `backend/src/admin/`, `backend/src/game-engine/effects/effect-text-parser.ts` (коммиты `1107114`, `20eea80`, `47824f7`, `3fb8d7d`, `b4a531c`, `5576fec`, `5d91bef`, `c47aeeb`, `1a2d437`, `cace5d8`…`5abac77`, `d4adc91`, `3feaa9b`)
- `git diff` рабочего дерева: `backend/src/content/content-db.service.ts`, `backend/src/content/mappers/content.mapper.ts`, `admin/src/pages/heroes/{create,edit}.tsx`

Память проекта (вне репозитория, `C:/Users/ren/.claude/projects/C--Users-ren-WebstormProjects-unmached-unmached/memory/`):
- `game-tester-and-logic-gaps.md` (полностью)
- `unmatched-launch-procedure.md` (полностью)
