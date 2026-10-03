# Расхождение баз данных между спринтами: разбор 2026-10-03

Запрос пользователя (2026-10-03): «Я еще видимо у тебя рассогласованность баз данных в зависимости от
спринта, который мы делали. Обрати на это внимание и разбери отдельно.»

Режим работы: только чтение. Выполнялись только `SELECT` по `information_schema`, `pg_catalog` и
таблицам, плюс `git show`, `git log` и `docker inspect`. Сидов, миграций и `db push` не было, ни одна
строка не изменена. Чтобы прочитать данные, я запустил контейнеры `codex-s04-postgres`,
`codex-s08-postgres`, `codex-s09-postgres` и `codex-s10-postgres`, а после чтения остановил их снова.
Контейнеры `unmatched-*` и redis-контейнеры не трогал. Пароли в отчёт не попали. Учётные данные
берутся из `docker-compose.yml` и из `backend/.env` каждого checkout (файл в `.gitignore`).

## 1. Итог

Схема у всех рабочих баз одинаковая. Расходятся данные: каждый спринт поднимал свою БД через
`docker run`, сеял её своей цепочкой сидов из своей версии скриптов и брал свою копию
`scraped-data`, которая лежит в `.gitignore`.

1. **Доски-графы Marmoreal и Sarpedon и арт-фикстуры есть только на стенде S09** (`:55434`, бэкенд
   `:3120`). Их сиды отказываются писать в любую другую БД. В основной БД (`:5433`, бэкенд `:3000`)
   этих досок нет.
2. **Структурные эффекты карт (`Card.effects`) есть только в основной БД:** 712 карт, `parserVersion`
   6, backfill от 2026-06-14. Во всех спринтовых БД у всех карт `effects=[]`. Движок восстанавливает
   на лету только часть эффектов, поэтому эффекты 394 карт работают только в основной БД. Среди них
   Gaze of Stone (8 урона), Swift Strike (переместиться на 4), Feint и Bewilderment (часть «during»).
3. **Стенд S08** (`:55433`, бэкенд `:3100`): у всех досок `cells=[]`, поэтому каждая партия идёт на
   пустой сетке 20×20. У героев нет `attackType`, поэтому Medusa играет ближним боем.
4. **Стенд S10** (`unmatched_s10_live`): сиды прошли в неверном порядке, а фиксы не запускались.
   - Krang и Shredder записаны как NPC-злодеи без колод.
   - У Daredevil и Ms. Marvel фейковые колоды.
   - У 7 карт нет значений.
   - Нет админа.
   - Доска по умолчанию — McMinnville OR.
5. **id досок генерируются случайно (cuid) в каждой БД.** Профиль Cobble в UE привязан к id из S09.
   Совпадают между базами только доски из фикстур, потому что их id детерминированы.
6. Схема рабочих БД совпадает с HEAD: `schema.prisma` одинаков во всех ветках, blob `7106de95`,
   последнее изменение в `0641577c` от 2026-06-11. Исключение — пустая БД `unmatched` в
   `codex-s10-postgres`. Её создал `prisma migrate deploy` по устаревшей миграции `init`, поэтому в ней
   нет 19 колонок и таблицы `GameReplay`.

Что это значит для текущей работы: UE-клиент по умолчанию ходит на `:3000`, то есть в основную БД,
где досок-графов нет. `run-phase2-demo.ps1` по умолчанию ходит на `:3100`, то есть в самую старую БД
S08. Нужные доски, аккаунты и свежие партии есть только на `:3120` (S09). Если запустить MS-AT-32 с
настройками по умолчанию, партия пойдёт на пустой сетке 20×20.

## 2. Инвентаризация

| БД | Контейнер, порт | Кем и когда создана | Кто её использует | Схема | Hero / Card / Board / User / Game / GameState | Доски-графы | Арт-фикстуры |
|---|---|---|---|---|---|---|---|
| **main** `unmatched` | `unmatched-postgres` `0.0.0.0:5433`, volume `unmached_postgres_data` | compose-проект `unmached` (`docker-compose.yml:2-17`); данные с 2026-06-10; контейнер пересоздан 2026-10-03 05:14 UTC | `unmatched-backend` `:3000` (bind mount `./backend`, `docker-compose.yml:55`); сиды с хоста через `backend/.env` → `localhost:5433`; фронт 5174, админка 5480 | = HEAD (лог бэкенда сегодня: «The database is already in sync with the Prisma schema») | 84 / 880 / 30 / 9 / 95 / 87 | нет | нет |
| **s08** `unmatched` | `codex-s08-postgres` `127.0.0.1:55433` (redis `codex-s08-redis` 6380) | `docker run` без compose (метки пусты), 2026-09-25 12:46 UTC, worktree `s08-ue-vertical` (`.env`: PORT=3100, 55433, 6380) | бэкенд `:3100`: `tools/s08/run-phase2-demo.ps1:3`, `capture-fixtures.mjs:22` | = HEAD | 84 / 880 / 30 / 8 / 29 / 22 | нет | нет |
| **s09** `unmatched` | `codex-s09-postgres` `127.0.0.1:55434` (redis 6381) | `docker run`, 2026-09-25 21:15 UTC, worktree `glm-s09-hud-flow`; позже его же используют `art-foundation` и `C:/tmp/wt-envmaps` (`.env`: PORT=3120) | бэкенд `:3120`: `tools/s09/*.ps1`, `tools/art/art004_live_k2.py:94`, `t52_art3_live.py:182`; спека `S09_PG_URL` | = HEAD | 84 / 880 / 46 / 61 / 559 / 554 | **да** (fixtureSha256 = HEAD) | **да** |
| **s10live** `unmatched_s10_live` | `codex-s10-postgres` `127.0.0.1:55435` (redis 6382) | `docker run`, 2026-09-27 09:00 UTC, worktree `s10-vs-ai` (`.env`: PORT=3121) | бэкенд `:3121`: `tools/s10/run-vs-ai-demo.ps1:3`; `S10_TEST_DB_URL` | = HEAD (db push) | 84 / **866** / 38 / 13 / 7 / 7 | нет | нет |
| **s10tests** `unmatched_s10_tests` | тот же | спеки S04/S09/S10 (`docs/game-design/evidence/S10/README.md:32-33`) | jest | = HEAD | 3 / 0 / 10 / 38 / 387 / 99 (только тестовые данные) | — | — |
| **s10** `unmatched` | тот же | `prisma migrate deploy` 2026-09-27 09:00:26 UTC (`_prisma_migrations`: `20260130162000_init`) | никто | **устарела:** нет 19 колонок, `GameReplay` и enum `UserRole` | все 0 | — | — |
| **s04** `s04_test` | `codex-s04-postgres` **`0.0.0.0:55432`**, `trust` | `docker run`, 2026-09-27 10:15 UTC (`docs/game-design/evidence/S04/README.md:214`) | `s04-concurrency-postgres.spec.ts`, сама делает `db push` | = HEAD | 3 / 0 / 1 / 2 / 32 / 0 (только тестовые данные) | — | — |

Какие сиды и бэкфиллы прошли в каждой БД, восстановлено по `createdAt` и `updatedAt` строк и по
признакам в данных:

| Шаг | main | s08 | s09 | s10live |
|---|---|---|---|---|
| `seed.ts` (Cobble City 5×6, тестовые юзеры, `seed-ai`) | 06-10 | 09-25 | 09-25 21:19 | 09-27, **после** карт: Cobble создана в 09:03, остальные доски в 09:02 |
| `seed-admin.ts` | да | да | да | **нет** |
| `seed-scraped.ts` + `seed-all-scraped.ts` | 06-10 | 09-25 12:50 | 09-25 21:22 | 09-27 09:02, **порядок неверный** |
| `fix-card-gaps.ts` + `fix-audit-findings.ts` | 06-11 08:49 (14 героев) | да | да | **нет** |
| attackType (`seed-scraped` или `backfill-attack-type.ts`) | 06-11 13:36, все 84 | **нет** (0 из 84) | 09-30 18:00, 70 из 84 (`1a8d72aa`) | 68 из 84, при создании |
| `backfill-board-cells.ts` | 06-11 12:42, старый `maps.json` | **нет** (`cells=[]`) | 09-26 03:22 | 09-27 09:03 |
| `backfill-card-effects.ts` | **06-14 04:03, только здесь** | нет | нет | нет |
| `seed-art-fixture-boards.ts` | нет | нет | 09-28 14:19 | нет |
| `seed-env-map-boards.ts` | нет | нет | 10-01 02:16 | нет |
| Демо-аккаунты (`ensure-demo-users.cjs`, `prepare_artpreview_accounts.cjs`) | нет | нет | да | нет (только s10-аккаунты) |

## 3. Различия

### 3.1. Схема

- Набор колонок, индексов, enum и ограничений совпадает у main, s04, s08, s09, s10live и s10tests:
  19 таблиц, 195 колонок, `diff` пустой.
- `schema.prisma` одинаков во всех спринтовых ветках: blob `7106de95` у `codex/s03` … `codex/s10-*`,
  `feat/env-original-maps` и HEAD.
- Отличается только `codex-s10-postgres/unmatched`. В ней нет колонок `Card.imageUrl`, `imageUrlRu`,
  `bannerName` и `effect*`, `Hero.movement`, `color`, `sidekicks`, `hasTokens`, `characterCardUrl`,
  `miniModelUrl` и `additionalMinis`, `Game.code` и `idempotencyKey`, `User.role`, нет таблицы
  `GameReplay` и enum `UserRole`. Причина — единственная миграция
  `backend/prisma/migrations/20260130162000_init` датирована январём, а схема менялась в `0641577c`
  (2026-06-11). Все остальные БД живут на `db push`.

### 3.2. Доски

- **Доски-графы** «Marmoreal · original map» (`c121b47f8d6eb28daccb76d05`, решётка 7×6, 31
  пространство) и «Sarpedon · original map» (`c7fa64a26c29a0835f2383e63`, 9×6, 38 пространств) есть
  только в s09. Их `features.fixtureSha256` равен хешу текущих фикстур
  (`backend/prisma/fixtures/boards/*.topology.json`: `425bebf2…` и `d1a72214…`).
- **Арт-фикстуры** «ART FIXTURE · Sherwood Forest» (`c37a3b6643a96c45fa71f10de`, 8×5) и
  «ART FIXTURE · T. Rex Paddock» (`c70e9f624617750c2a2b856fd`, 7×5) тоже есть только в s09, хеши
  совпадают с HEAD.
- **Одноимённые доски «Marmoreal» и «Sarpedon» во всех БД — это не графы.** Это приближение сеткой
  12×8 с зонами и препятствиями, которые сгенерировал `backfill-board-cells.ts`. В основной БД у них
  id `cmq7d5h4b000awiospx91ug5e` и `cmq7d5h4r000fwios0ea48f62` и ни одной клетки с `links`.
- **id досок разные в каждой БД (cuid).** Cobble City: main `cmq7d4b9k001lwi20keq745bb`, s08
  `cmugykjrq001mwi9wj1qwjfqb`, s09 `cmuhgs4b2001mwik4f2b2xtf8`, s10live
  `cmujlc8h8001iwi30ziyiz4e3`. UE-профиль `cobble-city` указывает на id из s09
  (`unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json:115`). Для сеточных досок клиент
  подбирает профиль запасным путём по W×H и ключам зон (`S08/S08BoardArt.cpp:1092-1100`); клетки
  Cobble в main и s09 совпадают, так что на main этот путь сработает. Доски-графы подбираются
  **только по id** (`S08BoardArt.cpp:1089-1091`).
- **Клетки** (`Board.cells`):
  - s08: у всех 30 досок пустой массив. `buildBoardState` в таком случае строит пустую сетку 20×20
    (`backend/src/games/services/game-initialization.service.ts:383-395`).
  - main против s09 и s10live: отличаются только Azuchi Castle и Raptor Paddock. В main ключ зоны
    `biege`, в остальных — `beige`. Клетки main сгенерированы 06-11, а `scraped-data/api/maps.json`
    обновлён 06-13 (опечатку исправили). `backfill-board-cells.ts` без `--force` непустые клетки не
    трогает.
- **Доска по умолчанию** — первая созданная (`backend/src/games/game.service.ts:116-119`). В main, s08
  и s09 это Cobble City, в s10live — McMinnville OR 505×405 (все 7 игр VS_AI шли на ней).
- **Тестовый мусор в s09:** 12 досок `s09-board-<uuid>` (set `test`), 45 юзеров `@test.invalid` и
  около 111 игр на этих досках. Их создаёт `backend/src/games/s09-terminal-postgres.spec.ts:24-38`:
  `beforeAll` создаёт строки, а `afterAll` их не удаляет.

### 3.3. Карты и эффекты

Сводные цифры по картам (SQL в §8, запрос Q6):

| БД | Карт | С `effects≠[]` | `parserVersion` | `imageUrl` null | `imageUrlRu` null | `boostValue` null (кроме SCHEME) | Сумма копий |
|---|---|---|---|---|---|---|---|
| main | 880 | **712** | 6 (1039 эффектов, все `source:parser`) | 0 | 185 | 7 | 2094 |
| s08 | 880 | 0 | — | 0 | 185 | 7 | 2094 |
| s09 | 880 | 0 | — | 0 | 185 | 7 | 2094 |
| s10live | **866** | 0 | — | 9 | 171 | 15 | 2055 |

- Значения ATTACK, DEFENSE и BOOST и количество копий у main, s08 и s09 совпадают у всех 84 героев.
  В s10live отличаются колоды 11 героев: не прошёл `fix-card-gaps.ts`, у Krang и Shredder нет колод,
  у Daredevil и Ms. Marvel фейковые карты из `seed.ts`.
- **Эффекты.** Если `effects` пуст, движок разбирает текст карты на лету только в трёх случаях
  (`game-initialization.service.ts:319-364`): у SCHEME полный текст, у ATTACK — `effectDuring`, у
  DEFENSE и VERSATILE — `effectAfter`. Остальные тексты не разбираются. Поэтому в S08, S09 и S10
  **не действуют** эффекты 394 карт, которые в main есть: у ATTACK — «after» и «on reveal», у
  DEFENSE и VERSATILE — «during» и «on reveal». Для героев текущей работы:

| Герой | Карта | Тип | Эффект в main | В S08/S09/S10 |
|---|---|---|---|---|
| Medusa | Gaze of Stone | ATTACK | AFTER_COMBAT DAMAGE 8 | нет |
| Medusa и King Arthur | Feint | VERSATILE | ON_REVEAL CANCEL_EFFECTS | нет |
| King Arthur | Swift Strike | ATTACK | AFTER_COMBAT **MOVE 4** | нет |
| King Arthur | Aid the Chosen One, The Aid of Morgana | ATTACK | AFTER_COMBAT DRAW_CARD 2 | нет |
| King Arthur | Momentous Shift | VERSATILE | DURING SET_VALUE 5 | нет |
| King Arthur | Bewilderment | DEFENSE | DURING PREVENT_DAMAGE (часть «after», PLACE, работает везде) | частично |

- В main эффекты сохранены с `parserVersion` 6, а в коде `PARSER_VERSION = 9`
  (`backend/src/game-engine/effects/effect-text-parser.ts:27`). Рантайм пере-разбирает устаревшие
  эффекты (`upgradeStaleParserEffects`), но заменяет их только при полном распознавании. Поэтому
  итоговое поведение main зависит от того, что распознаётся в версии 9.

### 3.4. Герои

- **Medusa и King Arthur одинаковы во всех четырёх контентных БД**:
  - Medusa: HP 16, movement 3, `range`, три Harpies с `health "1"` и `movement "3"`.
  - King Arthur: HP 18, movement 2, `melee`, Merlin с `health "7"`, `movement "2"` и `range`.
  - Колоды: Medusa — 11 строк и 30 копий, сумма BOOST 72; King Arthur — 16 строк и 30 копий, сумма
    BOOST 52.

  Исключение — **s08: `attackType` нет ни у кого**, и движок считает таких героев `melee`
  (`backfill-attack-type.ts:10-13`). У помощников в JSON health и movement хранятся строками во всех
  БД — это реальный случай MS-E-107.
- **attackType у 14 NPC** (злодеи и миньоны из `villains.json`): в main у всех стоит `melee`, в s09 и
  s10live поля нет. Функционально это то же самое, потому что значение по умолчанию тоже `melee`.
- **Krang и Shredder:**
  - main, s08 и s09: играбельные герои (HERO) с колодами 10 и 13 карт.
  - s10live: VILLAIN, HP 14, set «Adventures: TMNT», 0 карт.
  - У Krang в main помощник-заглушка «Unknown» с health 0 и movement 0, в s08 и s09 — с 1 и 1
    (`fix-audit-findings.ts:132`).
- **Daredevil и Ms. Marvel в s10live:** 13 и 15 строк вместо 8 и 11 (смешаны реальные и фейковые
  карты), у 5 и 4 карт нет картинок.
- Арты Shakespeare (Horror ×5) совпадают — разница в первом проходе была артефактом сортировки.

### 3.5. Пользователи и демо-аккаунты

- main: 5 тестовых аккаунтов, admin, moderator, `tester2@unmached.local`, `ai@unmached.local`.
- s09: то же плюс `s09-gd034-host` и `joiner`, `art-preview-host` и `joiner` (`@test.local`),
  `s09-host/joiner-tester`, `s09-host/joiner-muhisb0t` и 45 тестовых `@test.invalid`.
- s10live: нет admin и moderator; есть `s10-*` аккаунты.
- В `backend/.env` основного checkout лежат переменные `S09_DEMO_*`, но таких пользователей в main
  нет. Эти учётные данные действуют только на стенде S09.

### 3.6. Игры

- main: 95 игр (94 ABORTED и 1 LOBBY). Последняя создана **2026-09-18 08:11 UTC**, то есть с S08 по
  S10, для арта и ENV-MAPS основная БД под игры не использовалась. 12 игр ссылаются на
  несуществующие доски: старый баг со слагом вместо id, такие игры получают сетку 20×20.
- s09: 559 игр (155 FINISHED). Последние созданы **сегодня**, 2026-10-03 02:41–02:51 UTC, на
  «Sarpedon · original map» с хостом `art-preview-host`. Это рабочий стенд арта и ENV-MAPS.
- s08: 29 игр, все на Cobble City, клетки пустые, то есть фактически на 20×20.

## 4. Причины

| # | Расхождение | Причина | Источник |
|---|---|---|---|
| C1 | Отдельная БД у каждого спринта | Каждая сессия Codex поднимала свой стенд (`docker run`, свой `backend/.env`, свои порты 3100/3120/3121 и 55433/55434/55435), чтобы не трогать основную БД | `docs/game-design/evidence/S08/README.md:70`, `S09/README.md:7-11`, `S10/README.md:4,32-33`; `.env` в worktree (§2) |
| C2 | Нет одной цепочки сидов | Цепочка из памяти (6 шагов) не включает `backfill-attack-type`, `backfill-board-cells` и `backfill-card-effects`. `bootstrap-s09-stack.cjs` не запускает `seed.ts`, `fix-card-gaps` и `fix-audit-findings`, а `seed-all-scraped` ставит **перед** `seed-scraped`, хотя память предупреждает, что так NPC Krang и Shredder займут имена. Основную БД в июне досеивали вручную (06-11 и 06-14) | `tools/s09/bootstrap-s09-stack.cjs:85-92`; `memory/unmatched-launch-procedure.md:15-21`; таймлайн в §2 |
| C3 | Нет `attackType` в s08 (и в s09 до 09-30) | В `seed-scraped.ts` строка `attackType: hero.attack` появилась только в `623db845` (2026-09-26, «preserve complete project snapshot»). Worktree S08 и S09 отпочкованы раньше (merge-base S08 — `6121b72c`) и сеяли 09-25 старой версией. В S09 это исправлено `1a8d72aa` (09-30), в S08 — нет | `git log -S'attackType: hero.attack' -- backend/prisma/seed-scraped.ts`; `git show codex/s08-ue-vertical:backend/prisma/seed-scraped.ts:295-298` |
| C4 | `effects` есть только в main | `backfill-card-effects.ts` (добавлен `2c0f43a2` 06-12) запускался только на main 06-14 и не входит ни в одну цепочку. Спринты S05, S06 и S09 вместо этого сделали частичный разбор текста на лету | `game-initialization.service.ts:305-364` |
| C5 | Доски-графы и арт-фикстуры только в s09 | Так задумано: сиды пишут только в `127.0.0.1/localhost:55434` («the main dev DB is never written»). То же ограничение у арт-аккаунтов | `seed-art-fixture-boards.ts:12-14,30-31,60-75`; `seed-env-map-boards.ts:24-30,48-66`; `tools/art/prepare_artpreview_accounts.cjs:10-12` |
| C6 | Пустые `cells` в s08 | `backfill-board-cells.ts` (`5696061e` 06-12) в цепочку S08 не входил. В S09 его добавил `bootstrap-s09-stack.cjs` (`cff35c10` 09-27) | `bootstrap-s09-stack.cjs:90` |
| C7 | `biege` и `beige` | `scraped-data/` лежит в `.gitignore` (`.gitignore:23`) и копируется в каждый worktree вручную (`S09/README.md:9-11`). Клетки main построены до правки `maps.json` от 06-13 | mtime `scraped-data/api/maps.json` |
| C8 | Дефекты s10live | Сеяли в порядке `seed-all-scraped` → `seed-scraped` → `seed.ts`, без `seed-admin`, `fix-card-gaps` и `fix-audit-findings` (видно по timestamp и признакам в данных; явного скрипта в репозитории нет) | §2, §3.4 |
| C9 | Разные id досок | `Board.id` — `cuid()` при каждом сиде. Детерминированы только доски из фикстур (`'c' + sha256(...)[:24]`) | `seed-env-map-boards.ts:128-138` |
| C10 | Устаревшая БД s10 `unmatched` | Миграции не поддерживаются: в папке только `init` 20260130162000, а схема менялась в `0641577c`. `migrate deploy` создаёт неполную схему | `backend/prisma/migrations/` |
| C11 | Тестовый мусор в s09 | `S09_PG_URL` указывает на рабочий стенд S09, а спека не убирает за собой | `s09-terminal-postgres.spec.ts:18-38`; `.env` s10-vs-ai |
| C12 | Разные адреса API по умолчанию | UE берёт `:3000` (`unreal/Unmatched/Config/DefaultGame.ini:2`), переопределение через `-S08Api` (`S08FlowGameMode.cpp:155-158`); S08-демо — `:3100` (`run-phase2-demo.ps1:3`); S09 и арт — `:3120`; S10 — `:3121` | §2 |

## 5. Риски для текущей работы

1. **UE против основной БД.** Без `-S08Api` клиент ходит на `:3000`. При выборе «Marmoreal» в лобби
   получится сетка 12×8, а не граф. С `-ArtPreviewBoardId c121b47…` строки Board с таким id нет, и
   партия **молча** пойдёт на пустой сетке 20×20 (`game-initialization.service.ts:383-386`,
   комментарий в `run-phase2-demo.ps1:134-136`).
2. **MS-AT-32** (`docs/game-design/move-selection/06-test-and-acceptance.md:66`) запускает
   `tools/s08/run-phase2-demo.ps1`, а там по умолчанию `-Api` = `:3100`, то есть стенд S08. Досок-графов
   там нет, `cells=[]`, Medusa играет ближним боем. Запускать нужно явно с
   `-Api http://localhost:3120/graphql` и `-ArtPreviewBoardId c121b47f8d6eb28daccb76d05` или
   `c7fa64a26c29a0835f2383e63`, либо сначала перенести доски в main (§6).
3. **Эффекты карт.** На S09 King Arthur не получит отложенный MOVE от Swift Strike (move 4), а Medusa
   не нанесёт 8 урона от Gaze of Stone. В main эти эффекты есть. Golden-фикстуры move-selection
   хранятся в файлах (`backend/prisma/fixtures/movement`), их это не задевает. Живые проверки на
   разных стендах дадут разный ход партии, отсюда эффект «на одном стенде работает, на другом нет».
4. **Значения движения героев** одинаковы во всех контентных БД, расхождение на них не влияет.
5. **`db push --accept-data-loss` при каждом старте** (`backend/docker-entrypoint.sh:7`) берёт схему
   из того checkout, который смонтирован в `/app`. Если когда-нибудь поднять compose из ветки, где
   схема удаляет колонку, данные в main пропадут молча. Сейчас схема одинакова во всех ветках,
   поэтому прямого риска нет.
6. **Демо-аккаунты.** У `tools/s09/ensure-demo-users.cjs` нет проверки, в какую БД он пишет, и он
   перезаписывает пароли `S09_DEMO_*` в `backend/.env`. Если запустить его в основном checkout, он
   создаст пользователей в main и сломает вход на S09 по учётным данным из этого `.env`.
7. **e2e, вероятно, пишут в main.** `backend/test/setup.ts:3` грузит `.env.test`, которого нет, так
   что Prisma и Nest возьмут `backend/.env` → `:5433`. Кроме того, `backend/docker-compose.test.yml`
   занимает порты 5433 и 6380, которые уже заняты main и `codex-s08-redis`.
8. **`codex-s04-postgres` при запуске слушает `0.0.0.0:55432` с `trust`.** В README сказано
   `127.0.0.1`.
9. **Мусор в s09** (12 досок `s09-board-*`) виден в списке досок лобби на `:3120`.

## 6. План сведения (предложение, ничего не выполнялось)

Сначала нужно два решения пользователя:

- **D1. Какой стенд считать эталонным для игры и UE.**
  - Вариант A (рекомендую): основная БД (`:5433` / `:3000`). Она самая полная по контенту, в неё
    нужно перенести доски-графы и, по желанию, арт-фикстуры и демо-аккаунты.
  - Вариант B: стенд S09 (`:3120`). Тогда main остаётся для фронта и админки, S09 нужно догнать по
    `effects`, а адреса по умолчанию в UE и скриптах перевести на `:3120`.
- **D2. Разрешить ли сидам `seed-env-map-boards.ts` и `seed-art-fixture-boards.ts` писать в main.**
  Сейчас это жёстко запрещено (`ISOLATED_DB_PORTS=['55434']`). Нужна правка кода: явный флаг, например
  `--allow-main-dev-db`, который разрешает только `localhost:5433/unmatched` и оставляет остальные
  проверки (таблица Board не пуста, имя не занято, id детерминированы).

Шаги для варианта A. Все повторяемые, сначала dry-run. Запуск из `backend/` основного checkout, где
`DATABASE_URL` в `backend/.env` указывает на `:5433`:

| # | Шаг | Команда (предложение) | Ожидаемый результат |
|---|---|---|---|
| 0 | Снимок main | `docker exec unmatched-postgres pg_dump -U unmatched -d unmatched -Fc -f /tmp/unmatched-2026-10-03.dump` и `docker cp unmatched-postgres:/tmp/unmatched-2026-10-03.dump <backup-dir вне репо>` | дамп есть |
| 1 | Проверить схему (только чтение) | `npx prisma migrate diff --from-schema-datasource prisma/schema.prisma --to-schema-datamodel prisma/schema.prisma --exit-code` | код 0 |
| 2 | attackType | `node -r ts-node/register/transpile-only prisma/backfill-attack-type.ts --check` | код 0 (в main все 84 заполнены) |
| 3 | Эффекты карт до версии 9 | `node -r ts-node/register/transpile-only prisma/backfill-card-effects.ts --dry-run` → просмотреть отчёт → без `--dry-run` | parser-эффекты переразобраны, ручных нет |
| 4 | Клетки (по желанию, ради `beige`) | `npx ts-node --transpile-only prisma/backfill-board-cells.ts --force` | меняются только Azuchi Castle и Raptor Paddock; доски-графы пропускаются |
| 5 | Доски-графы (после D2) | `node node_modules/ts-node/dist/bin.js --transpile-only prisma/seed-env-map-boards.ts --dry-run` → `--apply --report <путь>` → `--verify` | 2 доски, `verified=true`, `defaultBoardUnchanged=true` (Cobble City `cmq7d4b9k001lwi20keq745bb`) |
| 6 | Арт-фикстуры (по желанию, после D2) | `prisma/seed-art-fixture-boards.ts --dry-run` → `--apply` → `--verify` | 2 доски |
| 7 | Демо-аккаунты (если нужны на main) | не через `ensure-demo-users.cjs` как есть (он перезапишет `S09_DEMO_*`): отдельные переменные `MAIN_DEMO_*` или явный параметр цели | аккаунты есть, `.env` S09 не тронут |
| 8 | Проверка | запросы §8 Q3–Q7 по main | 32 доски (34 с арт-фикстурами), `effects` версии 9, `attackType` 84 из 84 |

Кеш сбрасывать не нужно: в compose `DISABLE_CACHE: true`. Перезапуск бэкенда тоже не нужен, меняются
только данные.

Чтобы расхождение не вернулось:

1. Завести одну каноническую цепочку, например `tools/db/bootstrap-dev-db.cjs`, с явным портом
   назначения и повторяемыми шагами:
   1. `seed.ts`
   2. `seed-admin`
   3. `seed-scraped`
   4. `seed-all-scraped`
   5. `fix-card-gaps`
   6. `fix-audit-findings`
   7. `backfill-attack-type` и `--check`
   8. `backfill-board-cells`
   9. `backfill-card-effects`
   10. `seed-env-map-boards`
   11. `seed-art-fixture-boards`
   12. демо-аккаунты
2. Исправить порядок в `bootstrap-s09-stack.cjs` и обновить память `unmatched-launch-procedure.md`.
3. Решить судьбу `prisma/migrations`: либо регенерировать, либо удалить и записать, что проект живёт
   на `db push`.
4. Поменять адрес по умолчанию в `run-phase2-demo.ps1` (`:3100` → эталонный стенд) и описать
   `-S08Api` для ручных запусков UE.
5. Направить `S09_PG_URL` на отдельную тестовую БД.

Что делать со спринтовыми контейнерами (только рекомендация):

| Контейнер | Рекомендация | Почему |
|---|---|---|
| `codex-s09-postgres` + `codex-s09-redis` | **оставить** | Рабочий стенд арта и ENV-MAPS: партии сегодня, единственная БД с досками-графами и демо-аккаунтами. Если выбран вариант B — догнать по `effects` и очистить тестовый мусор (отдельное разрешение на `DELETE`) |
| `codex-s10-postgres` + `codex-s10-redis` | оставить остановленными, пока нужны демо и спеки S10 | `unmatched_s10_tests` нужен спекам. `unmatched_s10_live` с дефектами из C8 — пересеять, если снова понадобится. Пустую `unmatched` (миграция init) можно удалить |
| `codex-s08-postgres` + `codex-s08-redis` | сделать `pg_dump` в архив и удалить | Самая старая и неполная БД (нет клеток, `attackType`, `effects`). Её единственный потребитель — адрес по умолчанию в `run-phase2-demo.ps1`, который всё равно надо перенастроить |
| `codex-s04-postgres` | одноразовый: удалить или пересоздать с `-p 127.0.0.1:55432:5432` | спека сама делает `db push`; сейчас порт открыт на всех интерфейсах с `trust` |
| 6 висящих анонимных volume | не трогать без проверки | часть из них от проекта `alix` (2026-06-15) |

## 7. Открытые вопросы

1. D1: эталонный стенд — main (вариант A) или S09 (вариант B)?
2. D2: можно ли ослабить запрет «только 55434» явным флагом для основной БД?
3. Нужны ли в main арт-фикстуры Sherwood и T. Rex (сеточные приближения «art fixture, не правила»)?
4. Поднимать ли `effects` до версии 9 в main, и записывать ли `effects` в S09? Это меняет ход партий
   по сравнению с прошлыми evidence S09 и ENV-MAPS, которые сняты без этих эффектов.
5. Миграции: перейти на них или официально оставить `db push`?
6. Krang в main: помощник «Unknown» с health 0 и movement 0. Это ошибка данных `fix-audit-findings`
   или так задумано?
7. Пользователь видел, что бэкенд запущен «~08:15»; по `docker inspect` контейнеры `unmatched-*`
   созданы 2026-10-03 05:14:40 UTC (10:14 по +05). Поднимался ли стек ещё раз между этими моментами?

## 8. Как проверялось

Чтение шло через `docker exec <container> psql -U <user> -d <db> -At -c "<SQL>"`. MCP-сервер
`postgresql` в этой сессии не подключился.

- **Q1. Колонки:**
  `select table_name||'.'||column_name||' '||data_type||' '||is_nullable||' '||coalesce(column_default,'') from information_schema.columns where table_schema='public' order by 1`,
  затем `diff` с main. Так же по `pg_indexes`, `pg_enum` и `pg_constraint`.
- **Q2. Число строк:** `select (select count(*) from "<T>")||'|'||…` по всем 19 таблицам.
- **Q3. Доски:** `id, name, set, width×height, createdAt`, ключи `features`, длина `cells`, число
  клеток с непустыми `zones`; отдельно `features->>'fixtureSha256'` против
  `tr -d '\r' < fixture | sha256sum` и число клеток с `links` и `start`.
- **Q4. Отпечаток героя:** stats, `properties->>'attackType'`, `md5(sidekicks)`, число карт,
  сумма копий и BOOST, md5 по `(name, cardType, attack, defense, boost, count)`, md5 эффектов и
  текстов, md5 картинок; построчный разбор `cmp_hero.py` во временной папке сессии, в репозиторий
  не попал.
- **Q5. Таймлайн:** `to_char("updatedAt")` и `createdAt` с группировкой по Hero, Card и Board.
- **Q6. Эффекты:**
  `count(*) filter (where jsonb_array_length(effects)>0)`, распределение `e->>'parserVersion'` и
  `e->>'source'` по `jsonb_array_elements(effects)`, `(cardType, timing)`, и карты, у которых
  `timing` не покрыт разбором на лету (условие из `game-initialization.service.ts:335-343`).
- **Q7. Игры:** статусы, режимы, доски (`left join "Board"`), ссылки на несуществующие доски, дата
  последней игры.
- **Q8. Пользователи:** только email и role, без хешей.
- **Git:** `git show <branch>:backend/prisma/schema.prisma | git hash-object --stdin` для 13 веток;
  `git log -S'attackType: hero.attack'`; `git log --diff-filter=A` для сидов.
- **Docker:** `docker inspect` (Created, StartedAt, PortBindings, Labels, Mounts; переменные
  окружения выводились с маскированными паролями); `docker logs unmatched-backend`.

## 9. Выполнено 2026-10-03: одна обвязка и одни данные на всех стендах

Решение пользователя (чат 2026-10-03): «Мне нужно, чтобы база, Redis и все остальное в обвязке было одинаковым.
Нужно привести ее к максимально эффективному последнему виду.» Ответ на D1 — вариант A: эталон — основная БД. Ответ на
D2 — разрешено: появился явный флаг `--allow-main-dev-db`.

### 9.1. Резервные копии

Перед любыми изменениями сняты полные дампы (`pg_dump -Fc`) всех 7 БД в `C:/tmp/db-backups-2026-10-03/`:
`unmatched-postgres--unmatched`, `codex-s04-postgres--s04_test`, `codex-s08-postgres--unmatched`,
`codex-s09-postgres--unmatched`, `codex-s10-postgres--{unmatched,unmatched_s10_live,unmatched_s10_tests}`.

Старые анонимные volume удалённых контейнеров не удалялись, их список — в `old-container-volumes.txt` в той же папке.

### 9.2. Эталон: основная БД `localhost:5433/unmatched`

| Шаг | Результат |
|---|---|
| `fix-card-gaps.ts`, `fix-audit-findings.ts` (текущие версии) | карт без значений 0; Krang, Shredder, Ms. Marvel, Daredevil актуальны |
| `backfill-attack-type.ts --check` | exit 0, 84 из 84 |
| `backfill-board-cells.ts --force` | 30 досок перезаписаны по текущему `maps.json`; `biege` заменено на `beige` |
| `backfill-card-effects.ts` | 855 карт, `parserVersion` 9. Полностью распознано 271 карта против 240 при v6. Ручных правок нет |
| `seed-env-map-boards.ts --allow-main-dev-db` (dry-run, apply, verify) | доски-графы Marmoreal `c121b47f…` и Sarpedon `c7fa64a2…`; доска по умолчанию не изменилась |
| `seed-art-fixture-boards.ts --allow-main-dev-db` (dry-run, apply, verify) | арт-фикстуры Sherwood и T. Rex |
| Аккаунты из S09 | 8 демо- и арт-аккаунтов (`art-preview-*`, `s09-gd034-*`, `s09-*-tester`, `s09-*-muhisb0t`) перенесены вместе с `UserSettings` и `UserStats`, хеши паролей те же. Тестовый мусор `@test.invalid` не переносился |
| id Cobble City | закреплён `cmuhgs4b2001mwik4f2b2xtf8` — тот id, на который ссылаются UE-профиль, бенч, `run-phase2-demo.ps1` и арт-скрипты; 72 игры перепривязаны; `seed.ts` теперь создаёт Cobble с этим id |

Итог эталона: Hero 84, Card 880, Board 34 (из них 2 графа и 2 арт-фикстуры), User 17, эффекты v9.

### 9.3. Одинаковая обвязка

| Что | Было | Стало |
|---|---|---|
| Определение стендов | ручные `docker run`, анонимные volume | `docker-compose.stands.yml` с профилями `s04`, `s08`, `s09`, `s10`, `all`; именованные volume |
| Порты | основной Postgres, Redis и бэкенд, а также S04 на `0.0.0.0` | всё только на `127.0.0.1` (`docker-compose.yml`, `docker-compose.stands.yml`) |
| Postgres | 16.14 везде | без изменений, один образ `postgres:16-alpine` |
| Redis | 7.4.9; AOF только у основного и S08 | `redis:7-alpine --appendonly yes` везде, именованные volume (у основного тоже) |
| Бэкенды стендов (:3100, :3120, :3121) | процессы из старых worktree с разным кодом | сервисы `codex-sNN-backend`: образ `unmached-backend`, тот же `./backend` и `dist`, общий volume `node_modules`, переменные окружения как у основного бэкенда (`DISABLE_CACHE=true`) |
| Данные стендов | разные цепочки сидов | побайтовые клоны эталона (`tools/db/sync-dev-stands.cjs sync --apply`), Redis стенда очищается |
| Пароли стендов | в `docker run` | прежние значения в игнорируемом `.env.stands`; `backend/.env` в worktree (ENV-MAPS, S09) подходят без правок |
| Тестовые БД спек (`s04_test`, `unmatched_s10_tests`) | — | восстановлены из дампов, не клонируются; S04 по-прежнему trust, но только на `127.0.0.1` |
| Устаревшая БД `codex-s10-postgres/unmatched` (миграция `init`) | — | не воссоздавалась; дамп есть |
| `tools/s09/bootstrap-s09-stack.cjs` | сеял S09 отдельно | по умолчанию отказывается работать и отправляет к `sync-dev-stands.cjs`; старый путь — только с флагом `--legacy-seed` |

### 9.4. Проверка

- `node tools/db/sync-dev-stands.cjs status`: s08, s09 и s10 — **IDENTICAL** с main. Совпадают md5 таблиц Hero, Card,
  Board, User, UserSettings, UserStats, Game, GamePlayer, GameState, версия эффектов и число досок-графов.
- API: логин тестовым аккаунтом и списки досок и героев на `:3000`, `:3100`, `:3120`, `:3121` совпадают по md5.
- Логины стендов по паролям из `.env.stands` и `backend/.env` worktree работают; S04 по trust работает.
- Админка (`:5480`) показывает «Marmoreal · original map» и «Sarpedon · original map».
- `env-maps-board-seed.spec.ts`: 26 из 26, в том числе новые проверки `allowMainDevDb`.
- После проверки стенды остановлены. Запущен только основной стек — он нужен админке.

### 9.5. Как пользоваться дальше

```bash
docker compose -f docker-compose.stands.yml --env-file .env.stands --profile s09 up -d   # поднять стенд целиком
node tools/db/sync-dev-stands.cjs status                                                 # сверить стенды с эталоном
node tools/db/sync-dev-stands.cjs sync --apply [--only s09]                              # пересинхронизировать после изменений эталона
```

- Изменения данных делаются только в эталоне (`:5433`), затем `sync --apply`.
- Бэкенды стендов не запускать из worktree: их порты заняты сервисами compose.

Открыто:
- e2e-тесты бэкенда по-прежнему могут писать в основную БД (риск 7 в разделе 5).
- `backend/docker-compose.test.yml` конфликтует по портам.
- Миграции Prisma устарели, проект живёт на `db push` (C10).
- Помощник Krang «Unknown» 0/0 — значение из источника данных (вопрос 6 в разделе 7).
