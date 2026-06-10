# Починка админ-панели Unmatched — план реализации

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Привести админку (admin/) в полностью рабочее состояние: все CRUD-операции, auth, списки, пагинация, фильтры и страницы работают без ошибок; сборка проходит; данные сидов починены.

**Architecture:** Админка — React 18 + Refine v5 + Ant Design + urql, бэкенд — NestJS GraphQL (code-first) + Prisma. Чиним в три слоя: (1) бэкенд-контракт (admin-модуль), (2) провайдеры Refine, (3) страницы. Затем верификация (tsc/build/runtime) и починка данных сидов.

**Tech Stack:** TypeScript, @refinedev/core 5.0.8, @refinedev/antd 6.x, urql, NestJS 10, Prisma, Docker Compose.

**Исходник истины:** аудит из 91 подтверждённой находки (полный JSON: `C:\Users\ren\AppData\Local\Temp\claude\C--Users-ren-WebstormProjects-unmached-unmached\e5dc5fa4-c408-49d5-8a80-0ddf4cd70156\tasks\w01o2lf3n.output`).

**Окружение:** бэкенд запущен в Docker (`unmatched-backend`, порт 3000, start:prod — изменения бэка требуют `docker compose up -d --build backend`). Админка — vite dev на 5480 (hot reload). Postgres на 5433. Админ: `admin@unmached.local / Admin123!`.

**Git:** работа в ветке `fix/admin-panel`. Исполнители задач НЕ коммитят — коммиты делает оркестратор после верификации каждой фазы. Не трогать файлы вне своей задачи.

---

## Зафиксированный контракт (обязателен для всех задач)

После Фазы 1 бэкенд и провайдеры гарантируют:

1. **Query `adminUser(id: String!): UserDto`** — переименованный admin-запрос `user` (публичный `user` снова принадлежит users-модулю). `UserDto` получает поля `updatedAt: Date` и `deletedAt: Date | null`.
2. **Query `adminGame(id: String!): AdminGameDto`** — новый запрос для Game Show:
   `{ id, code, mode, status, createdAt, startedAt?, finishedAt?, boardId, boardName, gamePlayers: [{ id, playerId, heroId, status, username, avatar }] }`.
3. **`gameList`**: `GameListItemDto` дополняется `code: string`, `mode: string`; `boardName` заполняется реально; `search` не роняет запрос; `sortBy` — whitelist.
4. **`UpdateCardInput.heroId?: string`** — поддержан в `updateCard`.
5. **JSON-поля** (`ability`, `deckCards`, `properties`, `effects`, `cells`, `features`) во ВСЕХ ответах admin-модуля — сериализованные JSON-строки. Формы отправляют их **строками** (input-типы — String).
6. **Мутация refresh**: `refreshTokens(refreshToken: String!) { accessToken refreshToken }` (уже существует на бэке — `refreshAccessToken` НЕ существует).
7. **`matchmakingQueue`** возвращает реальные данные очереди (контракт полей не меняется).
8. **`auditLogs(page, limit)`** — настоящая серверная пагинация, `total` = общее число записей.
9. **Хук `admin/src/hooks/useDebounce.ts`** создаёт ТОЛЬКО Задача 12; страницы (4–10) его импортируют: `import { useDebounce } from '../../hooks/useDebounce';` сигнатура `useDebounce<T>(value: T, delay?: number): T` (default 400ms).
10. dataProvider: `getList` поддерживает `search`/`sortBy`/`sortOrder` для heroList/cardList/boardList/userList/gameList; `getOne('users')` → `adminUser`; `getOne('games')` → `adminGame`; `update('users')` → `updateUser`.

---

## Фаза 1 — Бэкенд и провайдеры (задачи 1–3 параллельно, файлы не пересекаются)

### Задача 1: Бэкенд admin-модуля

**Files:**
- Modify: `backend/src/admin/admin.service.ts`
- Modify: `backend/src/admin/admin.resolver.ts`
- Modify: `backend/src/admin/dto/admin.dto.ts`
- Modify: `backend/src/admin/admin.module.ts` (если нужен импорт MatchmakingModule)
- Modify: `backend/src/audit/audit.service.ts`
- Возможно Modify: `backend/src/matchmaking/matchmaking.module.ts` (export QueueManagerService)

**Шаги (после каждого пункта — `cd backend && npx tsc --noEmit`, должно быть 0 ошибок):**

1. **JSON-сериализация всех ответов.** В `admin.service.ts` завести приватные хелперы `serializeHero(hero)`, `serializeCard(card)`, `serializeBoard(board)`, которые `JSON.stringify` Json-поля (`ability`, `deckCards`, `properties` / `effects` / `cells`, `features`) если значение не строка и не null. Применить во всех местах, возвращающих AdminHero/AdminCard/AdminBoard: `getAllHeroes` (items), `createHero`, `updateHero`, `getAllCards`, `createCard`, `updateCard`, `getAllBoards`, `createBoard`, `updateBoard` (образец уже есть в `getHero`/`getCard`/`getBoard` — переиспользовать единый хелпер, убрать дублирование).
2. **`user` → `adminUser`.** В `admin.resolver.ts` строка ~149: `@Query(() => UserDto, { name: 'adminUser' })`. Проверить интроспекцией после деплоя, что публичный `user` из users-модуля вернулся в схему.
3. **`UserDto` + `updatedAt`/`deletedAt`.** В `dto/admin.dto.ts` добавить `@Field() updatedAt: Date;` и `@Field({ nullable: true }) deletedAt?: Date;` в UserDto; заполнить их в маппингах `getUserById` и `getAllUsers` (поля есть в Prisma-модели User — сверить с `backend/prisma/schema.prisma`).
4. **`adminGame`.** Новый DTO `AdminGameDto` (поля из контракта §2; `gamePlayers` — переиспользовать существующий GamePlayer-DTO из GameListItemDto). В `admin.service.ts` метод `getGameById(id)`: `game.findUnique` + `gamePlayer.findMany({ where: { gameId } })` + join username/avatar через user lookup (по образцу `getAllGames`) + `board.findUnique({ where: { id: game.boardId }, select: { name: true } })` → boardName. `NotFoundException` если игры нет. В резолвере — `@Query(() => AdminGameDto, { name: 'adminGame' })` с теми же guard'ами, что у остальных admin-запросов.
5. **`gameList` фиксы.** В `GameListItemDto` добавить `code`, `mode`. В `getAllGames`: (а) собрать `boardId` всех игр страницы, одним `board.findMany({ where: { id: { in: [...] } }, select: { id: true, name: true } })` построить мапу и заполнить `boardName`; (б) search: убрать `contains` по `status` (enum!); искать по `code: { contains: search, mode: 'insensitive' }`, и если `search.toUpperCase()` ∈ значения enum GameStatus — добавить `OR: [{ status: ... }]`; (в) sortBy whitelist `['createdAt', 'status', 'code', 'mode']`, иначе `createdAt`.
6. **sortBy whitelist везде.** Общий хелпер `safeSort(sortBy, allowed, fallback = 'createdAt')`; применить в heroList/cardList/boardList/userList (разрешённые поля — реальные колонки моделей, посмотреть в schema.prisma).
7. **`UpdateCardInput.heroId`.** Добавить `@Field({ nullable: true }) heroId?: string;` в UpdateCardInput; в `updateCard` — если heroId передан, проверить `hero.findUnique`, иначе `NotFoundException`.
8. **matchmakingQueue.** Убрать заглушку (resolver:362-372). Инжектировать `QueueManagerService` (см. `backend/src/matchmaking/services/queue-manager.service.ts`: `getAllEntries`, `getQueueSize`); если не экспортирован — экспортировать из MatchmakingModule и импортировать модуль в AdminModule. Собрать items по всем режимам: `{ id, userId, username, avatar, mode, elo, joinedAt, position }` (username/avatar — user lookup), `total`, `activeQueues` = число режимов с непустой очередью.
9. **auditLogs пагинация.** В `audit.service.ts` (метод с `take: 100`, ~строка 89-93): добавить параметры skip/take, вернуть `{ items, total }` с настоящим `prisma.authAuditLog.count()`. В `admin.resolver.ts` (auditLogs, ~342-355) передавать `skip = (page-1)*limit, take = limit`, отдавать серверный total, убрать срез в памяти. **metadata**: у модели AuthAuditLog нет колонки metadata — вернуть JSON-строку из реально существующих полей (например `{ userAgent, errorMessage }`, null-ы не включать) либо `null`; не делать `JSON.stringify(undefined)`.

**Verify:** `cd backend && npx tsc --noEmit` → 0 ошибок. Юнит-прогон не требуется; живая проверка — в Фазе 3 после rebuild.

### Задача 2: dataProvider

**Files:**
- Modify: `admin/src/providers/dataProvider.ts`

**Шаги:**

1. `getList`: `pagination?.current` → `pagination?.currentPage` (Refine v5; чинит tsc TS2339).
2. `getList`: поддержать `filters`/`sorters` для heroes/cards/boards/users/games: из `filters` взять первое значение (field `q`/`search` или operator `contains`) → переменная `search: String`; `sorters?.[0]` → `sortBy: String`, `sortOrder: String` (`asc`/`desc`). Обновить gql-документы list-запросов: `query GetHeroesList($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) { heroList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) { ... } }` — бэкенд эти аргументы уже принимает (сверить интроспекцией: `curl -s http://localhost:3000/graphql -H 'Content-Type: application/json' -d '{"query":"{ __type(name: \"Query\") { fields { name args { name } } } }"}'`). Для auditLogs/matchmakingQueue — не передавать.
3. `GET_HEROES_LIST`: убрать поле `ability` (в списке не нужно; до rebuild бэка оно роняет запрос).
4. `GET_USER`: `user(id:)` → `adminUser(id:)`, dataKey `'adminUser'`; добавить поля `updatedAt`, `deletedAt`.
5. `GET_GAME` → запрос `adminGame` по контракту §2, dataKey `'adminGame'`.
6. `update`: добавить `case 'users'` с мутацией `updateUser($id: String!, $input: UpdateUserInput!) { updateUser(id: $id, input: $input) { id username email role } }` (поля input сверить с `backend/src/admin/dto/admin.dto.ts` → UpdateUserInput).
7. `deleteOne`: возвращать `{ data: { id: actualId } as any }` вместо boolean.
8. urql client: не слать `Authorization: Bearer null` — `fetchOptions: () => { const token = getToken(); return token ? { headers: { Authorization: \`Bearer ${token}\` } } : {}; }`.
9. `getList` default-ветка: `throw new Error(...)` вместо тихого `{ data: [], total: 0 }`.
10. Убрать отладочные `console.log` (оставить только `console.error`).

**Verify:** `cd admin && npx tsc -b --force` — ошибка TS2339 (dataProvider.ts:468) исчезла; новых нет (остальные две ошибки чинятся задачами 8–9).

### Задача 3: authProvider и страница логина

**Files:**
- Modify: `admin/src/providers/authProvider.ts`
- Modify: `admin/src/pages/login.tsx`

**Шаги:**

1. `refreshToken()`: мутация `mutation RefreshToken($refreshToken: String!) { refreshTokens(refreshToken: $refreshToken) { accessToken refreshToken } }` (точную сигнатуру сверить интроспекцией, см. Задачу 2 шаг 2). Тип ответа — `refreshTokens`, не `refreshAccessToken`.
2. `check()`: нет токена → `{ authenticated: false, redirectTo: '/login' }`; есть токен → запрос `me`; если null — попытаться `refreshToken()` и повторить `me`; если снова null → false.
3. `onError`: GraphQL-ошибки приходят с HTTP 200; у urql `CombinedError` нет `.status`. Детект: `error?.graphQLErrors?.some(e => ['UNAUTHENTICATED','FORBIDDEN'].includes(e?.extensions?.code))` или `error?.response?.status === 401`. При детекте — refresh, при провале `{ logout: true }`.
4. `login.tsx`: показать ошибку логина (Alert с текстом из `error` мутации useLogin); демо-креды из initialValues убрать или обернуть `import.meta.env.DEV ? {...} : {}`.

**Verify:** `cd admin && npx tsc -b --force` без новых ошибок. Живой логин — Фаза 3.

---

## Фаза 2 — Страницы (задачи 4–12 параллельно, файлы не пересекаются)

### Задача 4: Heroes

**Files:** Modify: `admin/src/pages/heroes/{create,edit,show,list}.tsx`

1. **create.tsx**: JSON-поля (`ability`, `deckCards`, `properties`) отправлять **строками** (значение редактора как есть, предварительно проверив `JSON.parse` на валидность; невалидно → message.error и не отправлять). Сейчас отправляются распарсенные объекты в String-поля — это всегда падало.
2. **edit.tsx**: при загрузке — `const pretty = (v) => JSON.stringify(typeof v === 'string' ? JSON.parse(v) : (v ?? defaultVal), null, 2)` c try/catch (образец: cards/edit.tsx:22-31); при сохранении — отправлять строку (компактный `JSON.stringify(JSON.parse(editorValue))`), не объект. Защититься от `null` properties.
3. **show.tsx**: читать `query?.data?.data` (envelope dataProvider) или `const { result } = useShow()`; убрать дублирующий прямой urql-fetch — один источник данных.
4. **list.tsx**: fallback-изображение `/placeholder.png` не существует — заменить на AntD `<Avatar shape="square" icon={<PictureOutlined />} />` при отсутствии/ошибке imageUrl; поиск обернуть в `useDebounce` (контракт §9).
5. **create.tsx + edit.tsx**: поле Set — заменить захардкоженный Select (русские названия, не совпадающие с БД) на обычный `<Input />`.

**Verify:** `npx tsc -b --force` чисто; страницы откроются в Фазе 3.

### Задача 5: Cards

**Files:** Modify: `admin/src/pages/cards/{create,edit,list}.tsx`

1. **edit.tsx**: `useUpdate().mutate` вызывать с `{ resource: 'cards', id, values }` — id из `useParams()` (react-router). Сейчас сохранение всегда падает missingIdError.
2. **edit.tsx + create.tsx**: select героя захардкожен (`value="1"/"2"`) — загрузить реальных героев через urql: `heroList(page: 1, limit: 100, sortBy: "name", sortOrder: "asc") { items { id name } }`, опции `value=id label=name`, `showSearch` + `filterOption` по label. Текущее значение резолвится в имя автоматически по совпадению value.
3. **edit.tsx**: heroId теперь принимается бэкендом (контракт §4) — отправлять можно; effects — строкой (как в heroes).
4. **list.tsx**: колонки с `sorter` — подключить серверную сортировку: в `onChange` таблицы брать `sorter.field`/`sorter.order` → передавать `sortBy`/`sortOrder` в запрос (страница уже ходит в urql напрямую). Изображение при ошибке загрузки — не `display:none`, а заглушка (см. Задачу 4.4). Поиск — useDebounce.

### Задача 6: Boards

**Files:** Modify: `admin/src/pages/boards/{create,edit,show,list}.tsx`

1. **create.tsx**: `cells`/`features` отправлять строками (валидация парсингом, как Задача 4.1). Сейчас создание всегда падает.
2. **edit.tsx**: двойная сериализация при загрузке (parse-if-string → pretty) и отправка строкой при сохранении (как Задача 4.2).
3. **show.tsx**: envelope-баг — `query?.data?.data`; убрать дублирующий прямой fetch.
4. **list.tsx**: поиск — useDebounce; мёртвую ветку toggle в Select убрать.

### Задача 7: Users

**Files:** Modify: `admin/src/pages/users/{edit,show,list}.tsx`

1. **edit.tsx**: id брать из `useParams()` (сейчас — regex под несуществующий URL, форма никогда не работала); загрузка через `useOne({ resource: 'users', id })` или useShow; сохранение через `useUpdate` c `{ resource: 'users', id, values }` (dataProvider теперь поддерживает users — контракт §10). Поля формы — сверить с UpdateUserInput (как минимум role; username/email если есть в input).
2. **edit.tsx**: поле «Banned Until»/deletedAt из формы убрать — бан делается отдельными мутациями. Добавить кнопки «Ban»/«Unban» (Popconfirm) → прямые urql-мутации `banUser(id: $id)` / `unbanUser(id: $id)` (сигнатуры сверить с admin.resolver.ts); после успеха — refetch и message.success.
3. **show.tsx**: envelope-баг `query?.data?.data`; `updatedAt`/`deletedAt` теперь приходят (контракт §1) — Status вычислять по `deletedAt` (Banned/Active), даты через `new Date(Number(...))` если приходят числом — проверить формат и отобразить корректно (сейчас 'Invalid Date').
4. **list.tsx**: поиск — useDebounce.

### Задача 8: Games

**Files:** Modify: `admin/src/pages/games/{list,show}.tsx`

1. **list.tsx**: убрать неиспользуемый импорт `Tag` (tsc TS6133) либо начать использовать его легитимно; значения фильтра статусов привести к реальному enum GameStatus (посмотреть `backend/prisma/schema.prisma` — НЕ выдумывать WAITING/COMPLETED); из опций сортировки убрать `boardName` (нет такой колонки); поиск — useDebounce.
2. **show.tsx**: переписать на `adminGame` (контракт §2) через `useShow` + dataProvider (`query?.data?.data` или `result`): шапка — code/mode/status/boardName/даты; таблица gamePlayers — username/avatar/heroId/status. Убрать обращения к несуществующим `game.board.*`, `gp.player.*`, `gp.hero.*`, `gp.deckCards`, `game.gameState`. `getStatusColor` — по реальному enum.

### Задача 9: Audit Logs

**Files:** Modify: `admin/src/pages/audit-logs/list.tsx`

1. **Пагинация**: хранить серверный total (`const [total, setTotal] = useState(0)`) и передавать в `pagination.total` — сейчас `filteredData.length` запирает на первой странице.
2. **Фильтр action**: значения опций привести к реальным (lowercase `login`, `register` и др. — проверить живым запросом `auditLogs(page:1,limit:50)` какие action есть); сравнение и `actionColors` — нормализовать через `.toLowerCase()`. Клиентские фильтр/поиск действуют в пределах загруженной страницы — допустимо, но total при активном фильтре показывать честно (например, отключать серверную пагинацию при активном фильтре или сбрасывать фильтр при смене страницы).
3. **metadata**: перед выводом `typeof metadata === 'string' ? JSON.parse(...)` с try/catch, потом pretty-stringify; null → прочерк.
4. **tsc TS2322 (строки 211-212)**: для сравнения дат завести отдельные числовые переменные (`const aTime = new Date(a.timestamp).getTime()`), не переиспользовать union-типизированные aVal/bVal.

### Задача 10: Matchmaking

**Files:** Modify: `admin/src/pages/matchmaking/list.tsx`

1. Значения фильтра режимов привести к реальному enum GameMode (`backend/prisma/schema.prisma`); бэкенд теперь отдаёт реальную очередь (контракт §7) — сверить отображаемые поля с контрактом, поправить расхождения.
2. Если есть текстовый поиск — useDebounce.

### Задача 11: Dashboard

**Files:** Modify: `admin/src/pages/dashboard.tsx`

1. `GET_RECENT_GAMES`: добавить поля `code`, `mode`, `boardName` (контракт §3); renderItem: `Game #${code || id}`, mode без болтающегося `•` при пустом значении, boardName вместо `board?.name`.
2. Ошибки urql-запросов не глотать: показать `<Alert type="error">` при `result.error`.
3. Кнопка «View All» — рабочая навигация на `/games` (`useNavigate`).
4. `totalGames` запрашивается — отобразить в статистике.

### Задача 12: App, layout, общие хуки

**Files:**
- Create: `admin/src/hooks/useDebounce.ts`
- Modify: `admin/src/App.tsx`, `admin/src/main.tsx`, `admin/src/components/layout/AdminLayout.tsx`
- Modify/Delete: `admin/src/components/layout/ThemedApp.tsx`

1. **useDebounce.ts** (контракт §9):
```ts
import { useEffect, useState } from 'react';
export function useDebounce<T>(value: T, delay = 400): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}
```
2. **notificationProvider**: в App.tsx подключить `useNotificationProvider` из `@refinedev/antd` (`notificationProvider={useNotificationProvider}`); в main.tsx обернуть приложение в antd `<ConfigProvider><AntdApp>...</AntdApp></ConfigProvider>` (требование useNotificationProvider). ThemedApp задействовать для этого или удалить как мёртвый код — одно из двух, не оставлять висеть.
3. **AdminLayout**: убрать двойной контракт — компонент рендерит `{children}`, а не собственный `<Outlet/>` (LayoutWrapper в App.tsx уже передаёт `<Outlet/>` ребёнком). Подсветка меню: `selectedKeys` вычислять по префиксу pathname (`/heroes/show/1` → подсвечен Heroes), а не по точному совпадению.

**Verify (вся фаза):** `cd admin && npx tsc -b --force` → 0 ошибок; `npm run build` → успех.

---

## Фаза 3 — Верификация

### Задача 13: Сборка, деплой бэка, runtime-прогон

1. `cd admin && npx tsc -b --force` → **0 ошибок**; `npm run build` → успех.
2. `cd backend && npx tsc --noEmit` → 0 ошибок.
3. Пересобрать бэкенд: из корня `docker compose up -d --build backend`; дождаться `curl -s http://localhost:3000/health` → database+redis up.
4. GraphQL-smoke (curl, токен из мутации login): интроспекция — есть `adminUser`, `adminGame`, нет дублей `user`; `gameList(page:1,limit:5,search:"x")` не падает; `auditLogs(page:2,limit:5)` отдаёт total > items.length при наличии данных; `matchmakingQueue` отвечает; `updateHero` с JSON-строками проходит.
5. Playwright-прогон (vite на 5480 подхватит изменения сам): логин → все 8 разделов открываются без ошибок консоли/сети → CRUD-цикл: создать героя «Test Hero E2E» (JSON-поля по умолчанию) → отредактировать → удалить; то же для карты и доски; users: открыть show/edit реального тестового юзера (test1@unmatched.com), сменить роль туда-обратно, ban/unban; audit-logs: фильтр по action `login` возвращает данные, пагинация листается (если записей > 20); проверить картинки и dashboard.
6. Все падения — чинить и повторять пункт с падением (максимум 3 итерации, потом фиксировать остаток в отчёте).

**Чек-лист приёмки:** tsc 0 ошибок · build успешен · все 8 страниц без console-ошибок · create/edit/delete героя/карты/доски проходят · users edit/ban работает · Game Show рендерит игру · audit-логи листаются и фильтруются · логин с неверным паролем показывает ошибку.

---

## Фаза 4 — Данные сидов (после успешной Фазы 3)

### Задача 14: Парсер scraped-данных и пересид

**Files:**
- Modify: `backend/prisma/seed-scraped.ts`
- Modify: `backend/prisma/seed-all-scraped.ts`

1. **Бага №1 (set)**: `heroSchema.set` — числовой индекс в data-массиве, а код делает `heroSchema.set?.key` (число не имеет .key) → set всегда ''. Фикс: `const setObj = resolveValue(data, heroSchema.set); const setKey = resolveValue(data, setObj?.key); const setTitle = resolveValue(data, setObj?.title);` Проверено на scraped-data/yennenga.json: data[24] = {key:25,title:26} → 'Battle of Legends, Volume Two'. Тот же баг в seed-all-scraped.ts (строки ~109/151/193).
2. **Бага №2 (карты)**: `type/value/boostValue/image` — ключи элемента КОЛОДЫ (deck item), а не cardSchema; код читает `cardSchema.type` (undefined) → все карты MANEUVER/null. Фикс: резолвить эти поля с уровня deck item (проверить на scraped-data/achilles: «Achilles' Heel» = defense 4 / boost 2 + реальный image URL).
3. **nameEn=nameRu=name** (строки ~276-277): если в данных есть отдельные локали — использовать; нет — оставить как есть и зафиксировать в отчёте.
4. **Перед пересидом ОБЯЗАТЕЛЬНО** прочитать, как сид пишет в БД (upsert по какому ключу / delete+create). Если пересоздание меняет id героев/карт/досок, на которые ссылаются games/gamePlayers — НЕ запускать полный пересид; вместо этого написать точечный апдейт-скрипт (update по совпадению heroId+name), обновляющий только cardType/subType/attack/defense/boost/imageUrl/set. БД: `DATABASE_URL` из `backend/.env` (localhost:5433).
5. Запуск: `cd backend && npx ts-node --transpile-only -e "require('./prisma/seed-scraped.ts')"` (без --transpile-only падает на типах). Проверка после: GraphQL `cardList(page:1,limit:20)` — разнообразие cardType (ATTACK/DEFENSE/SCHEME/VERSATILE), ненулевые value, непустые imageUrl; `heroList` — непустые set.
6. Открыть Heroes и Cards в админке (Playwright) — картинки и значения отображаются.

---

## Порядок исполнения и коммиты

1. Ветка `fix/admin-panel` (создаёт оркестратор до начала).
2. Фаза 1 (задачи 1–3 параллельно) → tsc обоих проектов → коммит `fix(admin): backend contract + data/auth providers`.
3. Фаза 2 (задачи 4–12 параллельно) → tsc + build → коммит `fix(admin): resource pages, layout, notifications`.
4. Фаза 3 (задача 13) → итерации починки → коммит `fix(admin): verification fixes`.
5. Фаза 4 (задача 14) → проверка данных → коммит `fix(seeds): scraped data parser (sets, card types/values/images)`.
6. Финал: superpowers:verification-before-completion — полный чек-лист приёмки с доказательствами.
