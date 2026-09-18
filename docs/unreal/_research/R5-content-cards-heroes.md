# R5 — Контент: герои, карты, эффекты, ассеты (research для UE-клиента)

> Ридер R5. Источники прочитаны полностью: `docs/backend-api/05-engine-and-content.md` (часть B + релевантные разделы части A), `docs/backend-api/08-heroes-abilities.md`, `docs/backend-api/09-cards-and-effects.md` (1555 строк). Ключевые утверждения документов сверены с кодом (`backend/src/content/**`, `backend/src/game-engine/models/card.model.ts`, `backend/src/game-engine/abilities/ability-config.ts`, `backend/prisma/**`, `scripts/sync-card-assets.mjs`, `public/assets/**`, `scraped-data/api/**`, `src/gql/graphql.ts`). Живой бэкенд (`localhost:3000`) на момент чтения **не был запущен** — всё, что помечено «не проверено вживую», требует прогона запросов при поднятом стеке.
>
> Формат ссылок: `путь:строка` — файл репозитория `C:/Users/ren/WebstormProjects/unmached/unmached/`. Сокращения: **doc05** = `docs/backend-api/05-engine-and-content.md`, **doc08** = `docs/backend-api/08-heroes-abilities.md`, **doc09** = `docs/backend-api/09-cards-and-effects.md`.

---

## 1. Краткое резюме

1. **Единственный источник контента — PostgreSQL через Prisma** (модели `Hero`, `Card`, `Board`; `backend/prisma/schema.prisma:399-527`), выдаваемый публичными (без JWT) GraphQL-запросами `heroes / heroesPaginated / hero / heroesBySet / cards / card / boards / boardsPaginated / board / sets / contentSummary / contentVersion / heroStances` (doc05:406-424; `backend/src/content/content.resolver.ts:53-181`; `backend/src/games/game.resolver.ts:100-109`). Статические definition-файлы `backend/src/content/data/**` — только локальный fallback (doc05:387).
2. **Публичный DTO контента беднее, чем модель движка.** `Hero` наружу: `id` (= имя героя, не cuid), `name/nameEn/nameRu`, `health`, `movement` (**захардкожен 3**), `set`, `abilities[{id,name,text,trigger}]`, `cards[]`, `fighterType` (HERO|SIDEKICK), `sidekickCount`, `sidekickHealth` (**никогда не заполняется**), `urls{avatar,mini,cardCover}`, `imageUrl`, `avatarUrl` (`backend/src/content/dto/content.dto.ts:102-155`). `Card` наружу: `id` (cuid), `title`, `type` (ATTACK|DEFENSE|SCHEME|VERSATILE), `value`, `boost`, `quantity`, `characterName` (**= английское название карты, а не banner**), `effects[{id,timing,text}]`, `imageUrl`, `imageUrlRu` (`content.dto.ts:69-100`). **Не отдаются публично**: `bannerName` (кто может играть карту), `attackType` героя (melee/range), список сайдкиков (имена/HP/движение/тип атаки), `color`, полный текст карты `Card.text`, поля `effectAfter/During/Immediately/Boost/Ongoing`.
3. **Движок работает со структурированными эффектами** `CardEffect` (21 `EffectType`, 8 `EffectTiming`, 10 `EffectTarget`, 14 условий `when`, 5 источников `CountSpec`, 3 `BoostSource`, `options/chooseCount` для CHOOSE_ONE) — `backend/src/game-engine/models/card.model.ts:50-222`. Эффекты, требующие выбора игрока (MOVE / PLACE / CHOOSE_ONE), не блокируют игру, а кладутся в `metadata.pendingEffects` и резолвятся отдельной мутацией `resolvePendingEffect` (doc05:237-253). Нераспознанный текст (`UNSUPPORTED`) и ручные эффекты приезжают в `manualEffects` результата действия — клиент обязан показывать их в логе (doc05:235; doc09:120).
4. **Способности реализованы у 29 героев из 70 играбельных** (26 декларативных `ABILITY_CONFIGS` + daredevil + ms-marvel + king-arthur; doc08:12, 293-295). Спец-UI нужен для: стоек (`alice`, `muhammad-ali` — query `heroStances`, мутация `setStance`), BLIND BOOST (`daredevil` — отдельная мутация), отложенных перемещений (`robin-hood`, `leonardo`, `bruce-lee`, `ms-marvel`), расширенной дальности атаки (`bullseye` 5, `t-rex` 2, `ms-marvel` 2, `muhammad-ali` FLOAT 2), разрешения BOOST-а из руки на любую атаку (`king-arthur`). Остальные 41 герой — способность только текстом; 122 карты из 880 завязаны на немоделируемые ресурсы/токены (rage, hellfire, doubloons, fog/insight/shadow tokens, coils, missions, glamour, line, cauldron, Vibranium Suit, machines, identity/transform, traps, squirrels, clones).
5. **Реестр карт**: 70 героев × в сумме 880 уникальных карт (2094 копий) в doc09 (сверено скриптом по таблицам). Типы (по уникальным): attack 267, versatile 348, defense 114, scheme 151. Значение 0–7, BOOST 0–4 (одна карта 6), копий 1–4. Banner: `Any` 256, «своя» (без banner-пометки) 413, именная 211 (62 разных имени бойца, включая опечатки источника `Allice`, `Djkstra`, `Michelangelo ` с пробелом).
6. **Ассеты** лежат на фронте в `public/assets/**` (Vite `publicDir: 'public'`, `vite.config.ts:20`), бэкенд их не раздаёт. Фактически на диске: 1 картинка борда (`boards/hells-kitchen.webp`), колоды 18 героев (227 EN-карт `.webp`, RU-карты частично, `.png` и `.webp`), медиа только для 2 героев (`heroes/daredevil`, `heroes/ms-marvel`), HUD/эффекты `ui/**` (21 png). **В БД же (по сидам) хранятся абсолютные Supabase-URL** (`https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/...`), а не `/assets/...`, вопреки doc05:478 — UE-клиент должен уметь и то и другое.
7. **Версия контента** — константа `CONTENT_VERSION = '2.0.0'` (`backend/src/content/content-db.service.ts:12`), Redis-кэш TTL 3600 с (`:17`), инвалидация клиентского кэша — сравнение `contentVersion` (doc05:611-623, 639).

---

## 2. Факты по фокусу

### 2.1. Хранение: Prisma-модели (все поля)

#### `Hero` (`backend/prisma/schema.prisma:399-445`; doc05:351-366)

| Поле | Тип | Заполнение (сид `backend/prisma/seed-scraped.ts`) | Выдаётся публично? |
|---|---|---|---|
| `id` | cuid | авто | **Нет** как id (в `Hero.id` GraphQL подставляется `name`, `content.mapper.ts:60,194`); принимается в `hero(id)` (`content-db.service.ts:187`) |
| `name` (unique), `nameEn`, `nameRu` | String | `hero.name` во все три (`seed-scraped.ts:280-282`) — RU не локализован | да |
| `set` | String | `hero.set.title` — человекочитаемое название выпуска (`:283`) | да |
| `health` | Int | `hero.startHealth` | да |
| `fighterType` | String `HERO/MINION/HUGE` | `normalizeFighterType(hero.attack)` → всегда `'HERO'` для скрапа (`:184-191`) | да, как `FighterType` HERO/SIDEKICK (`mapper:315-322`) |
| `movement` | Int (default 2) | `hero.move \|\| 2` (`:286`) | **нет — маппер отдаёт константу 3** (`mapper:64,200`) |
| `color` | String? | `hero.color` | нет |
| `ability` | Json | `{type:'CUSTOM', timing:'PASSIVE', effect, description}` (`:288-293`) | да, как `abilities[]` (см. 2.3) |
| `deckCards` | Json | `[]` (`:294`) — карты живут в relation `cards` | — |
| `properties` | Json? | `{hasSidekick, sidekickCount, attackType: 'melee'\|'range'\|'melee_range'}` (`:295-300`) | `sidekickCount` да; `attackType` **нет** |
| `hasTokens` | Boolean | `hero.hasTokens` (`:302`) — в doc05 таблице отсутствует | нет |
| `sidekicks` | Json? | `[{name, health, movement, attackType, avatarUrl}]` (`:202-245, 303`) | **нет** |
| `additionalMinis` | Json? | `{images, models}` (`:304-307`) — в doc05 отсутствует | нет |
| `imageUrl` | String? | `hero.cardBackImage` — **рубашка колоды** (`:308`) | да (`imageUrl`, и как `urls.mini`/`urls.cardCover`) |
| `avatarUrl` | String? | `hero.avatar` (`:309`) | да (`avatarUrl`, `urls.avatar`) |
| `characterCardUrl`, `miniModelUrl` (.glb) | String? | `hero.characterCardImage`, `hero.miniatureModel` (`:310-311`) | нет |
| `cards` | Card[] | relation | да |
| `createdAt/updatedAt` | DateTime | авто | да |

#### `Card` (`schema.prisma:447-500`; doc05:368-370)

| Поле | Заполнение сидом (`seed-scraped.ts:320-350`) | Публично |
|---|---|---|
| `id` cuid | авто | да (`Card.id`) |
| `name/nameEn/nameRu` | `card.title` во все три | `title` = `name`; `characterName` = `nameEn \|\| name` (`mapper:228`) |
| `cardType` `ATTACK/DEFENSE/SCHEME/UNIVERSAL/VERSATILE/MANEUVER` | `normalizeCardType` (`:174-182`) | да, но `MANEUVER/UNIVERSAL/прочее → VERSATILE` (`mapper:395-410`) |
| `subType` | `'Movement'` только для MANEUVER (`:329`) | нет |
| `attackValue` / `defenseValue` | ATTACK → attack; DEFENSE → defense; **VERSATILE → в оба** (`:331-332`) | схлопнуты в `value` (см. 2.3) |
| `boostValue` | `card.boostValue` | `boost` |
| `bannerName` | `card.bannerName \|\| heroName` при парсинге (`:142`), в БД `card.bannerName \|\| null` (`:334`) | **нет** (только JWT `cardList`, `backend/src/admin/dto/admin.dto.ts:847-848`) |
| `effects` Json | `[]` при сидировании (`:335`); заполняется `backfill-card-effects.ts` парсером | да (`effects[]`, см. риск в 2.3) |
| `effectAfter/During/Boost/Immediately/Ongoing` | из скрапа (`:340-344`) | нет |
| `text/textEn/textRu` | `card.effect` (`:336-338`) | **нет** напрямую; только как fallback `effects[].text` (`mapper:234`) |
| `heroId` FK, `count` | `newHero.id`, `card.copies \|\| 1` | `quantity` = `count` |
| `imageUrl`, `imageUrlRu` | `card.image`, `card.imageRu` — Supabase-URL из скрапа (`:347-348`) | да |

#### `Board` (`schema.prisma:502-527`; doc05:372-374)

| Поле | Заполнение | Публично |
|---|---|---|
| `id` cuid | авто | нет (`Board.id` = `name`, `mapper:250`) |
| `name` (unique)/`nameEn`/`nameRu`, `set` | из `scraped-data/api/maps.json` (`backend/prisma/seed-all-scraped.ts:291-295`); Cobble City — `backend/prisma/seed.ts:256-270` | `id`, `name` |
| `width`, `height` | **для скрапнутых досок — пиксели картинки**, не клетки (`backend/prisma/backfill-board-cells.ts:4-6, 16-17`); Cobble City 5×6 — уже сетка (`:5`, `seed.ts:261-262`) | да (как есть) |
| `cells` Json | `[]` при импорте; генерируются `backfill-board-cells.ts` (сетка ≤12 клеток по длинной стороне, зоны полосами, препятствия 5–15 %) | да, как `spaces[{position{x,y}, zones[], isObstacle}]` |
| `features` Json | `{type, description, mapKey, minPlayers, maxPlayers}` (`seed-all-scraped.ts:298-304`) | нет; `recommendedPlayers` — константа 2 (`mapper:255`) |
| `imageUrl`, `imageUrlDark` | оба = `maps.json image` (Supabase) (`:306-307`) | `imageUrl` |

Прочие сиды/бэкфиллы (doc05:376-381): `seed.ts`, `seed-heroes.ts`, `seed-all-scraped.ts`/`seed-scraped.ts`, `update-card-images.ts` (проставляет `imageUrl/imageUrlRu` из скрапа только если пусто, `backend/prisma/update-card-images.ts:166-171`), `update-all-cards-images.ts`, `update-hero-images.ts`, `update-all-heroes.ts`, `backfill-card-effects.ts` (идемпотентный; `source:'manual'` не перезаписывает; `--dry-run`, `--hero=<name>`; doc09:157), `backfill-attack-type.ts`, `backfill-board-cells.ts`, `fix-audit-findings.ts`.

Объём в БД (по памяти о запуске, **не проверено вживую**): ≈ 84 героя / 880 карт / 30 досок (`C:/Users/ren/.claude/projects/C--Users-ren-WebstormProjects-unmached-unmached/memory/unmatched-launch-procedure.md:14`). 84 > 70 играбельных, т.к. `seed-all-scraped.ts` добавляет NPC-злодеев/миньонов из `villains.json`/`minions.json` (там же, строка 14; `scraped-data/api/` содержит `heroes.json, maps.json, minions.json, sets.json, villains.json`).

#### Скрап-данные (`scraped-data/api/heroes/*.json`)

- 88 JSON-файлов: 70 героев + файлы сетов (`battle-of-legends-volume-one.json`, `hells-kitchen.json`, …) + служебные (`data.json`, `melee.json`, `range.json`, `refresh.json`). Формат — Nuxt-payload (`{type:'data', nodes:[{data:[...]}]}`, значения через индексы), см. `seed-scraped.ts` `resolveValue`.
- Поля героя: `name, attack ('melee'|'range'|'melee_range'), startHealth, move, specialAbility, sidekicks[], key (слаг), cardBackImage, miniatureImage, miniatureModel, avatar, color, hasTokens, …` (первые 900 байт `scraped-data/api/heroes/daredevil.json`).
- Все картинки — хост `https://yptpnirqgfmxphjvsdjz.supabase.co` (2571 вхождение по всем hero-json; нет ни одного пути `/assets/`). Подпапки: `heroes/avatars`, `heroes/minis`, `heroes/card-covers`, `heroes/character-cards`, `heroes/sidekicks`, `decks`, `decks/ru`, `maps`; расширения `.webp/.png/.gif`.
- doc08 говорит «Статы героев/дек: `scraped-data/api/heroes/*.json` (сеется через `seed-scraped.ts`)» (doc08:10) — путь в doc09:3 указан как `backend/scraped-data/api/heroes/*.json`; **фактически каталог лежит в корне репо** `scraped-data/`, а `backend/prisma/backfill-board-cells.ts:33` читает `../../scraped-data/api/maps.json`.

### 2.2. Публичный контентный GraphQL: запросы

Все `@Public()` (doc05:404; `content.resolver.ts:54,63,76,89,98,111,120,132,145,154,163,172,181`; `game.resolver.ts:101`). `cardList`/`cardsList` — JWT (`backend/src/admin/admin.resolver.ts:208-233`).

| Query | Аргументы | Возврат | Особенности |
|---|---|---|---|
| `heroes` | — | `[Hero!]!` | путь `getAllHeroes → prismaHeroToHeroDto` (`content-db.service.ts:97-102`) — включает `imageUrl/avatarUrl/createdAt/updatedAt`; **N+1** при выборке `cards` (doc05:474; `content.resolver.ts:25-29`) |
| `heroesPaginated` | `page?, limit?, set?` | `PaginatedHeroes{items, pagination{total,page,limit,totalPages,hasNextPage,hasPreviousPage}}` | `content.dto.ts:205-233` |
| `hero` | `id: String!` | `Hero` (nullable) | `id` = cuid **или** имя (case-insensitive) — `content-db.service.ts:183-189`; путь `prismaHeroToHeroDefinition → toHeroDto` (`:196`), в нём `fighterType` **всегда HERO** (`mapper:43`) |
| `heroesBySet` | `set: String!` | `[Hero!]!` | `set` сравнивается insensitive (`:212`) |
| `cards` | `heroId: String!` | `[Card!]!` | `getCardsByHero → getHeroBySlug(heroId).deckCards` (`:227-229`) — т.е. `heroId` тоже cuid или имя |
| `card` | `id: String!` (cuid) | `Card` (nullable) | `:236` |
| `boards` | — | `[Board!]!` | |
| `boardsPaginated` | `page?, limit?` | `PaginatedBoards` | |
| `board` | `id: String!` | `Board` (nullable) | по имени, insensitive (`:329-331`); дефолтный борд — `cobble-city` (`:346`) |
| `sets` | — | `[String!]!` | distinct `Hero.set` (doc05:389) |
| `contentSummary` | — | `{version, heroesCount, boardsCount, setsCount, sets}` | `content.dto.ts:244-260` |
| `contentVersion` | — | `String!` | `'2.0.0'` |
| `heroStances` | `heroSlug: String!` | `[StanceOption{id,label,isDefault}]` | читает `ABILITY_CONFIGS.find(c => c.heroId === heroSlug)` (`game.resolver.ts:103-108`); непустой только для `alice`, `muhammad-ali` |
| `clearContentCache` | — | `Boolean` | **публичный** админ-инструмент (`content.resolver.ts:180-181`) |
| `cardList` / `cardsList` (JWT) | `page?, limit?, heroId?, search?, sortBy?, sortOrder?` | `CardsPaginated{items[CardListItem], total, …}` | `CardListItem`: `id,name,nameEn,nameRu,cardType,subType,attackValue,defenseValue,boostValue,bannerName,count,heroId,imageUrl,imageUrlRu` (`admin.dto.ts:820-860`) — **единственный запрос с `bannerName` и raw-типами**, текста эффекта нет |

Примеры готовых документов фронта: `src/graphql/queries/heroes.graphql` (`AllHeroes`, `HeroDetails`, `HeroesBySet`, `HeroStanceOptions`), `src/graphql/queries/cards.graphql` (`GetCards` = `cardList`, `GetCard`). Примеры для UE — doc05:519-635.

### 2.3. Публичные типы (DTO) и семантика полей — wire-формат

GraphQL-имена enum-значений (сгенерированные типы фронта `src/gql/graphql.ts`):

| Enum | Значения на проводе | TS-значения (внутри) | Источник |
|---|---|---|---|
| `CardType` | `ATTACK, DEFENSE, SCHEME, VERSATILE` | `attack/defense/versatile/scheme` | `src/gql/graphql.ts:256-261`; `backend/src/content/interfaces/card-definition.interface.ts:31-36` |
| `EffectTiming` (контент) | `IMMEDIATELY, DURING_COMBAT, AFTER_COMBAT, START_OF_TURN, END_OF_TURN, WHEN_PLAYED, WHEN_ATTACKED, WHEN_DEFENDING` | snake_case | `graphql.ts:363-372`; `card-definition.interface.ts:42-51` |
| `AbilityTrigger` | `PASSIVE, START_OF_TURN, DURING_COMBAT, WHEN_ATTACKED, WHEN_DEFENDING, END_OF_TURN` | snake_case | `graphql.ts:24-31`; `hero-definition.interface.ts:49-56` |
| `FighterType` | `HERO, SIDEKICK` | `hero/sidekick` | `graphql.ts:395-398`; `hero-definition.interface.ts:61-64` |
| `Zone` | `BLUE, GREEN, YELLOW, RED, PURPLE, BROWN, GRAY, ORANGE, PINK, WHITE, GOLD, BEIGE` (12) | lowercase | `graphql.ts:1746-1758`; `board-definition.interface.ts:43-56` |

Важно: enum контента `EffectTiming` **не совпадает** с enum движка `EffectTiming` (`ON_REVEAL, DURING_COMBAT, AFTER_COMBAT, ON_PLAY, BEFORE_COMBAT, ON_DISCARD, TURN_START, TURN_END`, `card.model.ts:191-201`) — это два разных типа с одним именем.

#### `Hero` (`content.dto.ts:102-155`)

| Поле | Семантика / подводные камни |
|---|---|
| `id: String!` | = `Hero.name` (`mapper:60,194`). Не cuid. Для запроса `hero(id)` подходит и cuid, и имя |
| `name`, `nameEn?`, `nameRu?` | `nameRu` = английское имя (сид не локализует, `seed-scraped.ts:281-282`) |
| `health: Int!` | печатное здоровье |
| `movement: Int!` | **константа 3** (`mapper:64,200`, TODO в коде; doc05:396). Реальное движение — `Hero.movement` в БД (`hero.move \|\| 2`) и `Fighter.movement` в игровом состоянии (`backend/src/games/services/game-initialization.service.ts:185`) |
| `set: String!` | название выпуска, 25 уникальных по doc09 (см. 2.9) |
| `abilities: [HeroAbility!]!` | для скрапнутых героев ровно один элемент: `id = "<name>-ability-0"`, **`name = "Ability"`** (в `Hero.ability` нет поля name), `text = description` (= печатный текст способности, включая её заголовок капсом, напр. «NECKLACE OF PEARLS Add +2 …»), `trigger = PASSIVE` (`mapper:69-73, 263-294`; сид `seed-scraped.ts:288-293`) |
| `cards: [Card!]!` | field-resolver `HeroResolver.getCards` → отдельный запрос на героя (`content.resolver.ts:25-29`) |
| `fighterType: FighterType!` | `heroes/heroesPaginated`: `parseFighterType(Hero.fighterType)` — MINION/SIDEKICK → SIDEKICK, иначе HERO (`mapper:315-322`); `hero/heroesBySet`: **всегда HERO** (`mapper:43`) |
| `sidekickCount: Int?` | `properties.sidekickCount` = длина `Hero.sidekicks` (`seed-scraped.ts:297`) — см. риск «фантомный сайдкик» в §4 |
| `sidekickHealth: Int?` | читается из `properties.sidekickHealth` (`mapper:332-347`), **но ни один сид/скрипт его не пишет** (grep по `backend/prisma/*.ts`, `backend/src/content/*.ts`, `backend/src/admin/*.ts` — 0 вхождений) → всегда `null` |
| `urls: HeroUrls?` | `avatar = avatarUrl`; **`mini = imageUrl \|\| avatarUrl`; `cardCover = imageUrl \|\| avatarUrl`** (`mapper:350-357`), где `imageUrl` = рубашка колоды (`cardBackImage`). `null`, если нет `avatarUrl` |
| `imageUrl?`, `avatarUrl?` | сырые поля Prisma (только путь `prismaHeroToHeroDto`, т.е. `heroes/heroesPaginated`; в `hero(id)` не заполняются — `mapper:189-210` их не задаёт) |
| `createdAt?`, `updatedAt?` | аналогично — только в `heroes/heroesPaginated` |

#### `Card` (`content.dto.ts:69-100`)

| Поле | Семантика / подводные камни |
|---|---|
| `id: String!` | Prisma cuid шаблона карты. В игре экземпляр карты имеет `id = "${cardId}::n"`, `cardId` = этот cuid (doc05:101-102) |
| `title: String!` | `Card.name` |
| `type: CardType!` | `parseCardType`: только attack/defense/scheme/versatile/universal; **всё остальное (в т.ч. `MANEUVER`) → VERSATILE** (`mapper:395-410`). В doc09-таблицах карт типа `maneuver` нет (0 строк из 880), т.е. практически не встречается |
| `value: Int!` | `attackValue ?? defenseValue ?? boostValue ?? 0` (`mapper:221-225`). Следствие: **для SCHEME (attack/defense = null) `value` = BOOST**; то же для 3 defense- и 4 versatile-карт без печатного значения (напр. Luke Cage «Skin Like Titanium», Black Widow «Life Model Decoy», She Hulk «Lady Justice», Dr. Sattler «I Think We're Back In Business») |
| `boost: Int!` | `boostValue ?? 0` (`mapper:226`) — 8 карт без BOOST в скрапе (6 Sinbad «Voyage…», Krang «IQ of 968», «Pan-dimensional Portal») получат 0 |
| `quantity: Int!` | `Card.count` — число копий в колоде |
| `characterName: String!` | **`Card.nameEn \|\| Card.name` — название самой карты** (`mapper:228`), а НЕ имя бойца/banner. Не использовать для banner-логики |
| `effects: [CardEffect!]!` | из `Card.effects` (Json). У скрапнутых карт до бэкфилла `[]` (`seed-scraped.ts:335`) → **текста эффекта в публичном API нет**. После `backfill-card-effects.ts` элементы — движковые `CardEffect` с `timing ∈ {ON_REVEAL, DURING_COMBAT, AFTER_COMBAT}` (`backend/src/game-engine/effects/effect-text-parser.ts:62-64`); маппер `normalizeTiming` превращает `'DURING_COMBAT'` в `'d_u_r_i_n_g_c_o_m_b_a_t'` (проверено в node по коду `mapper:378-386`), что **не входит в GraphQL-enum `EffectTiming` контента → при выборке поля `timing` ожидаем ошибку сериализации enum** (не проверено вживую; см. §4). `text` = предложение эффекта (`e.text \|\| Card.text`, `mapper:234`) |
| `imageUrl?`, `imageUrlRu?` | как в БД: по сидам — Supabase-URL; в контент-модуле fallback — `/assets/decks/...` (`backend/src/content/data/heroes/daredevil.ts:84-85`) |

#### `Board` / `BoardSpace` (`content.dto.ts:157-203`)

| Поле | Семантика |
|---|---|
| `id: String!` | = `Board.name` (`mapper:250`) |
| `name`, `width: Int!`, `height: Int!` | **для скрапнутых досок width/height — пиксели исходной картинки** (`backfill-board-cells.ts:4-6,16-17`); размер сетки выводить из `spaces` (max x+1, max y+1). Cobble City — 5×6 в `seed.ts:261-262`, но 6×4 в fallback-модуле `backend/src/content/data/boards/cobble-city.ts:14-18` (расхождение) |
| `recommendedPlayers: Int!` | константа 2 (`mapper:255`); реальные `minPlayers/maxPlayers` лежат в `Board.features` и не выдаются |
| `spaces: [BoardSpace!]!` | `{position{x,y}, zones: [Zone!]!, isObstacle?}` из `Board.cells`; зоны нормализованы через `ZONE_ALIASES` (violet→PURPLE, grey→GRAY, biege→BEIGE, оттенки `blue-dark`→BLUE по первому токену; неизвестное отбрасывается — иначе падал весь `boards`) (`mapper:430-466`) |
| `BoardSpace.startingPositionsJson?` | объявлен в DTO (`content.dto.ts:177-178`), но маппер его **не заполняет** (`mapper:241-259`) → всегда `null` |
| `imageUrl?` | Supabase-URL карты (`seed-all-scraped.ts:306`) или `null` (Cobble City, `seed.ts:269`) |

`StanceOption` (`backend/src/games/dto/gameplay.dto.ts:362-370`): `id: String!` (`'big'|'small'|'float'|'sting'`), `label: String!`, `isDefault: Boolean!`.

### 2.4. Модель карты в движке (`backend/src/game-engine/models/card.model.ts`)

Это то, что приходит внутри игрового состояния (руки/сбросы/колоды; JSON — см. R4), и что описывает doc09:7-56.

`CardType` (`:10-20`): `ATTACK, DEFENSE, SCHEME, UNIVERSAL, VERSATILE, MANEUVER`. VERSATILE — значение в оба поля; MANEUVER — `subType 'Movement'`, играется ради движения и бустится другой картой (doc09:11-18).

`Card` (`:25-42`): `id` (instance `"${cardId}::n"`), `cardId` (cuid), `name/nameEn/nameRu`, `cardType`, `attackValue?`, `defenseValue?`, `boostValue?`, `effects?: CardEffect[]`, `text?` (текст из БД для отображения/ручного применения), `bannerName?` (`'Any'`/пусто — любой боец, иначе имя бойца; валидация `bannerAllows` в `game-rules.validator`, doc09:32). `HandCard` добавляет `isVisible` (`:282-284`); `DeckState {cards, drawPile, topCard?}` (`:289-293`); `HandZone {cards: HandCard[], maxSize}` (`:298-301`).

`CardEffect` (`:50-79`; doc09:34-56):

| Поле | Тип | Смысл |
|---|---|---|
| `id` | string | идентификатор |
| `type` | `EffectType` | см. 2.5 |
| `timing` | `EffectTiming` | см. 2.6 |
| `target?` | `EffectTarget` | см. 2.6 |
| `value?` | number | +N, урон, число карт, дистанция |
| `condition?` | string | legacy (`'low_health'` = HP < 50 %) |
| `when?` | `{kind, value?}` | структурное условие (2.6) |
| `count?` | `CountSpec` | счётчик для VALUE_PER_COUNT / draw-per-damage |
| `optional?` | boolean | «You may …» — в MVP авто-применение выгодных (doc09:46) |
| `fighterName?` | string | якорь для `NAMED_FIGHTER` / `ADJACENT_ENEMY` («Move Daredevil…») |
| `boostSource?` | `BoostSource` | для `type: BOOST` |
| `blind?` | boolean | BLIND BOOST (вскрытие верха колоды) |
| `options?` | `ChooseOption[] {label, effects[]}` | варианты CHOOSE_ONE (`:114-117`) |
| `chooseCount?` | number | сколько опций выбрать (default 1; «choose 2 different effects» = 2) |
| `text?` | string | исходное предложение — для лога / `manualEffects` |
| `source?` | `'parser'\|'manual'` | ручные (админка) не перезаписываются бэкфиллом |
| `parserVersion?` | number | |

`normalizeCardEffects(raw, cardId)` (`:230-268`): никогда не бросает; строка → JSON.parse; мусор → один `UNSUPPORTED` с сырым текстом; неизвестный `type` → `UNSUPPORTED`, неизвестный `timing` → `AFTER_COMBAT`.

### 2.5. `EffectType` — 21 значение и что должен уметь UI

Стадии боя (doc09:96): **ON_REVEAL** (первым атакующий) → **DURING_COMBAT** (порядок внутри стороны: `SET_VALUE` → `MODIFY_*` → `VALUE_PER_COUNT` → прочее) → урон → **AFTER_COMBAT** (сначала все эффекты атакующего, потом защитника). Scheme: `ON_PLAY` + тексты `AFTER_COMBAT`. `TURN_START/TURN_END` — по всем картам в руке.

| # | `EffectType` | Что делает (doc09:98-120) | Типовой timing | Требование к UI клиента |
|---|---|---|---|---|
| 1 | `MODIFY_ATTACK` (legacy) | +`value` к атаке | DURING | показать дельту в `combatSummary`/логе |
| 2 | `MODIFY_DEFENSE` (legacy) | +`value` к защите | DURING | то же |
| 3 | `MODIFY_VALUE` | +N к значению своей карты, роль по стороне боя (VERSATILE) | DURING | то же |
| 4 | `SET_VALUE` | «value is N instead»; порядок 0, последний выигрывает; комбо `SET_VALUE 0` + `VALUE_PER_COUNT CARDS_IN_HAND` | DURING | показать итоговое значение вместо печатного (56 карт в реестре с таким текстом) |
| 5 | `VALUE_PER_COUNT` | +`per × count` по `CountSpec` | DURING | показать источник счётчика (40 карт «+N for each») |
| 6 | `BOOST` | +boostValue карты из `boostSource` | DURING | `PLAYER_CHOICE_HAND` — **выбор карты из руки (поле `boostCardId` мутации)**; `SELF_DECK_TOP` — авто, пустая колода → fail; `OPPONENT_RANDOM_HAND` — авто, у оппонента нет карт → fail |
| 7 | `DAMAGE` | `value` урона целям (clamp ≥ 0) | AFTER / ON_PLAY | анимация урона; «No valid targets» → fail без входа |
| 8 | `HEAL` | +`value` HP (≤ max) | любой | анимация лечения |
| 9 | `MOVE` | движение бойца на `value` клеток | любой | **интерактив**: `pendingEffects` типа MOVE → подсветка достижимых клеток (BFS `getReachableCells`), выбор клетки или отказ; мутация `resolvePendingEffect`; протухает при возврате хода владельцу (doc05:253) |
| 10 | `PLACE` | размещение бойца в клетку | любой | **интерактив**: PLACE → любая свободная проходимая клетка; `target: OPPOSING_FIGHTER` → `targetsOpponent` (двигаем чужого) |
| 11 | `DRAW_CARD` | добор `value` (default 1) | любой | анимация добора |
| 12 | `DISCARD` | сброс `value` случайных карт своей руки | любой | анимация сброса (сервер решает какие) |
| 13 | `OPPONENT_DISCARD` | оппонент сбрасывает `value` случайных | любой | анимация у оппонента |
| 14 | `CANCEL_EFFECTS` | «Cancel all effects on your opponent's card» | ON_REVEAL | пометить карту противника как отменённую (печатное значение сохраняется; отменённый защитник не отменяет в ответ) — 72 карты |
| 15 | `RETURN_TO_HAND` | вернуть ЭТУ карту из сброса в руку | любой | fail, если нет в сбросе / рука полна (`HandZone.maxSize`) |
| 16 | `IMMOBILIZE` | «cannot leave their space this turn» | любой | статус-иконка на бойце (`FighterEffect {type:'immobilized', duration:'turn'}`) |
| 17 | `GAIN_ACTION` | +`value` к `actionsRemaining` | ON_PLAY | обновить счётчик действий (86 карт «Gain N action») |
| 18 | `PREVENT_DAMAGE` | «Prevent all damage» своей роли | DURING | отобразить в `combatSummary` |
| 19 | `END_TURN` | `actionsRemaining = 0` | ON_PLAY | ход заканчивается автоматически |
| 20 | `CHOOSE_ONE` | «Choose one: …» — выбрать `chooseCount` из `options` | ON_PLAY | **интерактив**: `pendingEffects` типа CHOOSE_ONE → диалог с `options[].label`; `resolvePendingEffect(optionIndex)`; при `chooseCount > 1` pending остаётся с остатком опций; вложенный MOVE/PLACE порождает новый pending; боевые эффекты опций вне боя → `manualEffects` |
| 21 | `UNSUPPORTED` | нераспознанный текст; не исполняется | — | **обязательно** показать текст из `manualEffects` (warn-лог, метрика `unsupported-effect`) — игра не блокируется |

Контракты исполнителя (doc09:148-153): эффекты не меняют `sequenceNumber` (ровно +1 на мутацию); бойцы и игроки — разные id (`*FighterId` vs `*PlayerId` = userId); ничья в бою = победа защитника. Результат каждого действия содержит `appliedEffects` и `manualEffects` (doc05:147, 235), а резолв боя — `combatSummary {finalAttack, finalDefense, урон обеих сторон, attackerWon, cancel-флаги}` (doc05:221).

### 2.6. Тайминги, цели, условия, счётчики, источники BOOST, отложенные эффекты

**`EffectTiming` движка** (`card.model.ts:191-201`; doc09:122-132): `ON_REVEAL` (вскрытие в COMBAT_RESOLVE, до during; отменённая карта не исполняет), `DURING_COMBAT`, `AFTER_COMBAT` (и «после розыгрыша» scheme), `ON_PLAY` (scheme), `BEFORE_COMBAT` и `ON_DISCARD` (только значения enum, стадии нет), `TURN_START`/`TURN_END` (по картам в руке). Парсер: `effectImmediately → ON_REVEAL`, `effectDuring → DURING_COMBAT`, `effectAfter → AFTER_COMBAT` (`effect-text-parser.ts:62-64`; doc09:157).

**`EffectTarget`** (`card.model.ts:206-222`; doc09:134-146): `SELF` (default; играющий боец или первый живой), `OPPOSING_FIGHTER`, `ATTACKER`, `DEFENDER`, `ALL_ENEMIES`, `ALL_ALLIES`, `ENEMIES_ADJACENT_TO_SELF`, `ADJACENT_ENEMY` (MVP: первый валидный + warn; якорь `fighterName`), `NAMED_FIGHTER` (по `fighterName` среди своих; «Harpy 2» ↔ «Harpy» регистронезависимо), `OPPONENT_PLAYER`. → Для `ADJACENT_ENEMY` сервер **не спрашивает** игрока (выбирает первого) — UI выбора цели для карточных эффектов пока не нужен, но результат нужно показывать.

**`EffectConditionKind`** (`card.model.ts:86-102`; doc09:58-70): `WON_COMBAT`, `LOST_COMBAT` (ничья = победа защитника; в during-стадии → false), `IS_ATTACKING`, `IS_DEFENDING`, `ADJACENT_TO_OPPONENT`, `NOT_ADJACENT_TO_OPPONENT`, `DECK_EMPTY`, `HAND_COUNT_AT_MOST`/`HAND_COUNT_AT_LEAST` (`value`), `HEALTH_AT_MOST` (`value`), `MOVED_THIS_TURN` (позиция ≠ `metadata.turnStartPositions`), `OPPONENT_IS_HERO`, `SHARES_ZONE_WITH_OPPONENT`/`NOT_SHARES_ZONE_WITH_OPPONENT` (пересечение зон клеток, мультизонность).

**`CountSpec {source, namePrefix?, per?}`** (`card.model.ts:122-137`; doc09:72-82): `FRIENDLY_ADJACENT_TO_OPPONENT` (другие живые союзники, смежные с противником), `CARDS_IN_HAND`, `DISCARD_NAME_PREFIX` (карты в своём сбросе с именем на `namePrefix`, кроме самой карты — «for each other VOYAGE card»), `DAMAGE_DEALT`, `DAMAGE_TAKEN`; `per` — множитель (default 1).

**`BoostSource`** (`card.model.ts:142-148`; doc09:84-90): `PLAYER_CHOICE_HAND` (игрок сбрасывает карту из руки — `boostCardId` в мутации), `SELF_DECK_TOP` (BLIND BOOST, авто), `OPPONENT_RANDOM_HAND` (случайная карта оппонента).

**`PendingEffect`** (doc05:239-253): `{id, type: 'MOVE'|'PLACE'|'CHOOSE_ONE', playerId, value? (дистанция MOVE), fighterName? (именное ограничение), targetsOpponent?, options?, chooseCount?, optionEffects?, card?}`. Резолв — мутация `resolvePendingEffect` (действие **не тратится**, seq +1); MOVE — BFS-достижимость за `value` шагов; PLACE — любая свободная проходимая клетка; заявки протухают при возврате хода владельцу (doc05:158, 253). Источники pending: карточные MOVE/PLACE/CHOOSE_ONE и способности `pending-move` (robin-hood, leonardo, bruce-lee; doc08:66).

### 2.7. Правила BOOST (doc09:161-177; doc05:181-183)

1. **Когда разрешён BOOST из руки** (`game-action-executor.service.ts → boostAllowed`): играемая карта атаки/защиты имеет эффект `type: BOOST` с `boostSource: PLAYER_CHOICE_HAND` (или без источника), **или** способность героя разрешает (`allowsAttackBoost` / `allowsDefenseBoost`; King Arthur — атака).
2. **Механика**: `boostCardId` в мутации атаки/защиты; карта обязана быть в руке (`Boost card not in hand`); **нельзя бустить той же картой** (`boostCard.id === playedCard.id` → ошибка); буст-карта сбрасывается, её `boostValue` прибавляется к `attackValue`/`defenseValue`; **после сброса буст-карты — добор 1 карты**; лимит — одна буст-карта на разыгранную (одно поле); дальнейший стакинг — только эффектами `BOOST` (SELF_DECK_TOP / OPPONENT_RANDOM_HAND).
3. **BOOST манёвра**: `boostCardId` (legacy `cardId`) в `executeManeuver` даёт +`boostValue` к движению **каждого** передвигаемого бойца (`getFighterMovement(fighter) + boostValue`), буст-карта в сброс + добор 1 (doc09:173; doc05:177-178). Манёвр двигает всех своих бойцов (`moves: [{fighterId, path}]`, каждый ≤ 1 раза), промежуточные клетки проходимы, конечная должна быть свободна (doc05:175-176).
4. **BLIND BOOST (Daredevil)**: при бое с ≤ 2 картами в руке можно сбросить верх колоды и прибавить его `boostValue` (`BOOST` + `SELF_DECK_TOP`) — отдельная мутация (doc09:175; doc08:230).
5. **BOOST за счёт оппонента**: `OPPONENT_RANDOM_HAND` (doc09:177).
6. В бою `combatInfo.attackValue = attackValue + boostValue` пишется при объявлении атаки, `defenseValue = defenseValue + boostValue` при защите; без защиты — резолв с 0 (doc05:191, 195).
7. В текстах карт: «You may BOOST this card» — 36 карт; «BLIND BOOST» — 6 карт (Daredevil «Man Without Fear»; Doctor Strange «Seven Suns of Cinnibus» (до двух раз), «Bolts of Balthakk»; Spike/Drusilla «Always Surprising»; Willow «Black Magic», «Flayed Alive»); «opponent discards 1 random card. Add its BOOST» — 6; «Discard the top card of your deck. Add its BOOST» — 3 (подсчёт по doc09-таблицам).

### 2.8. Герои со способностями в реестре (29) и требования к спец-UI

Архитектура (doc08:16-46; doc05:255-331): классический `HeroAbilityHandler` (только king-arthur) и расширенный `ExtendedHeroAbilityHandler` (daredevil, ms-marvel + 26 `GenericHeroAbilityHandler` по `ABILITY_CONFIGS`). Хуки: `onTurnStart/onTurnEnd/onAfterCombat/onFighterDefeated/onFighterMoved/canAttackAtRange/getStanceIds/getStatefulCombatModifiers/getAuraCombatModifiers`; все обёрнуты в try/catch (ошибка хендлера не рвёт поток). Слаг героя берётся с бойца: `fighter.heroSlug ?? fighter.heroId`, `heroSlug = slugifyHeroName(hero.name)` (doc05:282; `game-initialization.service.ts:144`).

DSL (`ability-config.ts:365-422`; doc08:47-77): триггеры `combat-passive | turn-start | turn-end | after-attack | after-defense | sidekick-defeated | enemy-hero-left-my-zone`; условия `always, attacking, defending, self-health-below-defender, all-own-sidekicks-defeated, {handSizeEquals:N}, no-enemy-in-own-zone, won-combat, lost-combat, has-not-maneuvered-this-turn, has-attacked-this-turn, first-lost-combat-this-turn, won-combat-and-all-sidekicks-defeated`; эффекты `combat-modifier, combat-modifier-per-count, aura-combat-modifier, turn-effect (draw/drawToHandSize/heal/gainAction), pending-move, turn-damage (+thenDraw), discard-random, reactive-damage, set-stance (to:'<id>'|'toggle'), cycle-stance`; `whenStance` гейтит правило по стойке; `StanceConfig {id, label, default?, attackRange?, combat?}`; `config.attackRange` — Manhattan-дальность атаки, игнорируя зоны (базовая у всех — 1).

| slug | Герой (атака; HP; move; сайдкики) | Способность как в коде | Хук/механика | Что нужно UE-клиенту | doc08 |
|---|---|---|---|---|---|
| `luke-cage` | Luke Cage (melee; 13; 2; Misty Knight 6/2/range) | «Skin Like Titanium»: постоянный **+2 к защите** | combat-passive | только отображение модификатора в итогах боя | :85-88 |
| `annie-christmas` | Annie Christmas (melee; 14; 2; Charlie 8/2/range) | «Long Shot» (печатно Necklace of Pearls): +2 атака, если HP атакующего < HP защитника | combat-passive | индикатор условия (опц.) | :90-93 |
| `eredin` | Eredin (melee; 14; 2; 4× Red Rider 1/2/melee) | «Unyielding Hordes»: +1 атака и защита, когда все Red Rider повержены («move value 3» не моделируется) | combat-passive | бейдж ENRAGED (опц.) | :95-98 |
| `bloody-mary` | Bloody Mary (melee; 16; 3; —) | «Infinity Mirror»: в начале хода при ровно 3 картах в руке +1 действие | turn-start | обновление счётчика действий | :100-103 |
| `philippa` | Philippa (range; 12; 2; Dijkstra 6/2/melee) | «Spellbreaker» (Two Steps Ahead): в конце хода добор до 4 карт | turn-end | анимация добора | :105-108 |
| `t-rex` | T. Rex (melee; 27; 1; —) | `attackRange: 2` + добор 1 в конце хода; большая база/хвост не моделируются | RNG(2), turn-end | **подсветка целей на дистанции 2 (игнорируя зоны)** | :110-113 |
| `bigfoot` | Bigfoot (melee; 16; 3; The Jackalope 6/3/melee) | «It's Just Your Imagination»: в конце хода добор 1, если в зоне нет врагов | turn-end | — | :115-118 |
| `chupacabra` | Chupacabra (melee; 14; 3; —) | «Blood Frenzy» (The Hunger): добор 1 после каждой своей атаки | after-attack | — | :120-123 |
| `deadpool` | Deadpool (melee; 10; 2; —) | «Regeneration»: +1 HP после своей атаки | after-attack | — | :125-128 |
| `michelangelo` | Michelangelo (melee; 14; 3; April O'Neil 6/3/range) | «Party Dude»: добор 1 после атаки (лимит руки 3 не моделируется) | after-attack | — | :130-133 |
| `angel` | Angel (melee; 16; 2; Faith 8/2/melee) | «Fallen Grace»: добор 1, если бой не выигран (ничья = проигрыш) | after-attack + lost-combat | — | :135-138 |
| `golden-bat` | Golden Bat (melee; 18; 3; Daisy 6/2/melee) | «The First Superhero»: +2 атака, если в этом ходу не было манёвра | combat-passive | индикатор «манёвра не было» (опц.) | :140-143 |
| `ancient-leshen` | Ancient Leshen (range; 13; 1; 2× Wolf 1/3/melee) | «Heart of the Forest»: +3 атака, если уже атаковал в этом ходу («Wolves move 3» не моделируется) | combat-passive | — | :145-148 |
| `raphael` | Raphael (melee; 17; 2; Casey Jones 8/2/range) | «Anger Issues»: +1 действие при первом проигрыше боя в ходу | after-attack | обновление счётчика действий | :150-153 |
| `robin-hood` | Robin Hood (range; 13; 2; 4× Outlaws 1/2/melee) | «Trick Shot»: после своей атаки — MOVE pending на атаковавшего бойца до 2 клеток (можно отклонить) | after-attack → pending-move | **UI отложенного перемещения** | :155-158 |
| `leonardo` | Leonardo (melee; 16; 2; Splinter 9/2/melee) | «Tactical Genius» (Team Tactics): в начале хода MOVE pending любого СВОЕГО бойца на 1 (чужих — не поддержано) | turn-start → pending-move | **UI отложенного перемещения с выбором бойца** | :160-163 |
| `dracula` | Dracula (melee; 13; 2; 3× The Sisters 1/2/melee) | «Children of the Night»: в начале хода авто-1 урон ПЕРВОМУ смежному врагу, при попадании добор 1 («you may» не моделируется) | turn-start → turn-damage | показать авто-урон в логе | :165-168 |
| `medusa` | Medusa (range; 16; 3; 3× Harpies 1/3/melee) | «Petrifying Gaze»: в начале хода авто-1 урон первому врагу в зоне | turn-start → turn-damage | то же | :170-173 |
| `bullseye` | Bullseye (range; 14; 2; —) | `attackRange: 5`, `rules` пуст | RNG(5) | **подсветка целей до 5 клеток, игнорируя зоны** | :175-178 |
| `bruce-lee` | Bruce Lee (melee; 14; 3; —) | «Be Like Water»: в конце хода MOVE pending героя на 1 | turn-end → pending-move | **UI отложенного перемещения** | :180-183 |
| `raptors` | Raptors (melee; 7 за раптора; 3; стая, сайдкиков нет) | «Pack Tactics»: +1 атака за каждого ДРУГОГО живого раптора, смежного с защитником (только при count > 0) | combat-passive → per-count | — | :185-188 |
| `oda-nobunaga` | Oda Nobunaga (melee; 13; 2; 2× Honor Guard 6/2/melee) | «Banner of the Demon King» (Master Strategist): аура +1 атака/защита ДРУГИМ дружественным бойцам в зоне Oda; сам не получает | aura-combat-modifier | — | :190-193 |
| `achilles` | Achilles (melee; 18; 2; Patroclus 6/2/melee) | 3 правила: +2 атака пока Patroclus повержен; добор 1 при победе с поверженным сайдкиком; при гибели Patroclus сброс 2 карт (детерминированно первые 2) | combat-passive, after-attack, sidekick-defeated | анимация сброса при гибели сайдкика | :195-200 |
| `tomoe-gozen` | Tomoe Gozen (range; 14; 2; —) | «Unwavering Resolve» (Attack of Opportunity): вражеский ГЕРОЙ покидает её зону → 1 урон ему | enemy-hero-left-my-zone (onFighterMoved) | показать реактивный урон после чужого хода/манёвра | :202-205 |
| `alice` | Alice (melee; 13; 2; The Jabberwock 8/2/melee) | стойки `big` (default) / `small`: BIG +2 атака, SMALL +1 защита; **смена только вручную** (`setStance`) — при размещении и картами «Change size» (авто-флипа нет) | Stance | **STANCE HUD**: `heroStances('alice')`, кнопки `setStance`, индикатор текущей стойки | :207-213 |
| `muhammad-ali` | Muhammad Ali (melee; 16; 3; —) | стойки `float` (default, **attackRange 2**) / `sting` (+2 атака); **авто-toggle после каждой выигранной атаки**; эффекты [Butterfly] на картах — только в FLOAT | Stance + RNG(stance) + after-attack | **STANCE HUD** + подсветка целей на 2 клетки только в FLOAT + уведомление об авто-смене | :215-221 |
| `king-arthur` | King Arthur (melee; 18; 2; Merlin 7/2/range) | «Holy Avenger»: `allowsAttackBoost: true` — любую атаку можно бустить картой из руки; combat-модификаторов нет | Boost | **кнопка/слот BOOST при любой атаке** | :223-226 |
| `daredevil` | Daredevil (melee; 17; 3; —) | «Blind Boost»: рука ≤ 2 И колода непуста → отдельной мутацией сброс верха колоды, +boostValue к атаке/защите (`executeBlindBoost(state, playerId, forAttack)`); есть `peekTopCard`/`getBoostValue` (превью) | отдельная мутация | **кнопка BLIND BOOST в бою** (доступность по условию) | :228-231 |
| `ms-marvel` | Ms. Marvel (melee; 14; 2; —) | «Stretchy»: атака с ≤ 2 клеток (игнорируя зоны) + в начале хода сдвиг на 1 клетку отдельной мутацией (`executeTurnStartMove(state, playerId, targetPosition)`; `getAvailableTurnStartPositions` — 4 соседние клетки; препятствия/двери TODO) | canAttackAtRange + мутация | **подсветка целей до 2 клеток + UI выбора клетки в начале хода** | :233-238 |

Стойки в коде: `ability-config.ts:856-858` (`{id:'big', label:'Big', default:true}`, `{id:'small', label:'Small'}`), `:889-891` (`{id:'float', label:'Float Like a Butterfly', default:true, attackRange:2}`, `{id:'sting', label:'Sting Like a Bee'}`). Текущая стойка — `metadata.heroStances[userId]` (doc05:313); смена — мутация `setStance` (бесплатная, seq +1) (doc05:314). Query `heroStances` для всех остальных 27 героев вернёт `[]`.

Задокументированные приближения (doc08:242-250): «you may» не моделируется для turn-damage (Dracula, Medusa); «random» discard детерминирован (Achilles); движение чужих бойцов не поддержано (Leonardo); статы сайдкиков в способности не моделируются (Eredin, Leshen); лимит руки Michelangelo — нет; `after-defense` инфраструктура есть, героя нет (Spider-Sense намеренно не реализован); T. Rex — только дальность 2.

Дальность атаки в целом (doc05:190): `melee` — только смежная цель; `ranged` — смежная **или** та же зона (пересечение зон клеток); если не достаёт — `canAttackAtRange(slug, attackerId, targetId, range, stance)` (только добавляет). Ranged-герои среди 29: philippa, ancient-leshen, robin-hood, medusa, bullseye, tomoe-gozen; ranged-сайдкики: Misty Knight, Charlie, April O'Neil, Casey Jones, Merlin (doc08). Для остальных 41 героя тип атаки в doc08/doc09 не указан; в скрапе он есть (`attack`), в БД — `Hero.properties.attackType` (не выдаётся).

**41 герой без реализации способности** (только текст): Beowulf, Black Panther, Black Widow, Blackbeard, Buffy, Ciri, Cloak Dagger, Doctor Strange, Donatello, Dr. Jill Trent, Dr. Sattler, Elektra, Geralt of Rivia, Ghost Rider, Hamlet, Harry Houdini, Invisible Man, Jekyll & Hyde, Krang, Little Red, Loki, Moon Knight, Nikola Tesla, Pandora, Robert Muldoon, Shakespeare, She Hulk, Sherlock Holmes, Shredder, Sinbad, Spiderman, Spike, Squirrel Girl, Sun Wukong, The Genie, The Wayward Sisters, Titania, Willow, Winter Soldier, Yennefer & Triss, Yennenga (разность списков doc09 §4 и doc08 §2).

### 2.9. Полный реестр героев (70) — сводка из doc09 §4

Здоровье/движение — из заголовков doc09 (`### <Имя> (<Сет>) — здоровье N, движение M`), «колода» — сумма копий по таблице, «реестр» — есть ли способность в коде (doc08).

| Герой | Сет | HP | Move | Карт (копий) | В реестре способностей |
|---|---|---|---|---|---|
| Achilles | Battle of Legends, Volume Two | 18 | 2 | 30 | `achilles` |
| Alice | Battle of Legends, Volume One | 13 | 2 | 30 | `alice` (стойки) |
| Ancient Leshen | The Witcher - Steel & Silver | 13 | 1 | 30 | `ancient-leshen` |
| Angel | Buffy the Vampire Slayer | 16 | 2 | 30 | `angel` |
| Annie Christmas | Adventures: Tales to Amaze | 14 | 2 | 30 | `annie-christmas` |
| Beowulf | Little Red Riding Hood vs. Beowulf | 17 | 2 | 30 | — |
| Bigfoot | Robin Hood vs Bigfoot | 16 | 3 | 30 | `bigfoot` |
| Black Panther | For King and Country | 14 | 2 | 30 | — |
| Black Widow | For King and Country | 13 | 2 | 31 | — |
| Blackbeard | Battle of Legends, Volume Three | 13 | 2 | 30 | — |
| Bloody Mary | Battle of Legends, Volume Two | 16 | 3 | 30 | `bloody-mary` |
| Bruce Lee | Bruce Lee | 14 | 3 | 30 | `bruce-lee` |
| Buffy | Buffy the Vampire Slayer | 14 | 3 | 35 | — |
| Bullseye | Hell's Kitchen | 14 | 2 | 30 | `bullseye` |
| Chupacabra | Battle of Legends, Volume Three | 14 | 3 | 30 | `chupacabra` |
| Ciri | The Witcher - Steel & Silver | 15 | 2 | 30 | — |
| Cloak Dagger | Teen Spirit | 8 | 2 | 30 | — |
| Daredevil | Hell's Kitchen | 17 | 3 | 22 | `daredevil` (blind boost) |
| Deadpool | Deadpool | 10 | 2 | 30 (30 уникальных ×1) | `deadpool` |
| Doctor Strange | Brains and Brawn | 14 | 2 | 30 | — |
| Donatello | Adventures: Teenage Mutant Ninja Turtles | 14 | 2 | 30 | — |
| Dr. Jill Trent | Adventures: Tales to Amaze | 13 | 2 | 30 | — |
| Dr. Sattler | Jurassic Park - Sattler vs. T-Rex | 13 | 2 | 30 | — |
| Dracula | Cobble & Fog | 13 | 2 | 30 | `dracula` |
| Elektra | Hell's Kitchen | 7 | 2 | 20 | — |
| Eredin | The Witcher - Realms Fall | 14 | 2 | 30 | `eredin` |
| Geralt of Rivia | The Witcher - Steel & Silver | 16 | 2 | 36 | — |
| Ghost Rider | Redemption Row | 17 | 2 | 30 | — |
| Golden Bat | Adventures: Tales to Amaze | 18 | 3 | 30 | `golden-bat` |
| Hamlet | Slings and Arrows | 15 | 2 | 30 | — |
| Harry Houdini | Houdini vs. The Genie | 14 | 2 | 30 | — |
| Invisible Man | Cobble & Fog | 15 | 2 | 30 | — |
| Jekyll & Hyde | Cobble & Fog | 16 | 2 | 30 | — |
| King Arthur | Battle of Legends, Volume One | 18 | 2 | 30 | `king-arthur` (boost) |
| Krang | TMNT: Shredder vs Krang | 16 | 1 | 30 | — |
| Leonardo | Adventures: Teenage Mutant Ninja Turtles | 16 | 2 | 30 | `leonardo` |
| Little Red | Little Red Riding Hood vs. Beowulf | 14 | 2 | 30 | — |
| Loki | Battle of Legends, Volume Three | 16 | 2 | 30 | — |
| Luke Cage | Redemption Row | 13 | 2 | 30 | `luke-cage` |
| Medusa | Battle of Legends, Volume One | 16 | 3 | 30 | `medusa` |
| Michelangelo | Adventures: Teenage Mutant Ninja Turtles | 14 | 3 | 30 | `michelangelo` |
| Moon Knight | Redemption Row | 16 | 3 | 30 | — (3 стойки-identity, `cycle-stance` заготовлен, конфига нет) |
| Ms. Marvel | Teen Spirit | 14 | 2 | 30 | `ms-marvel` |
| Muhammad Ali | Muhammad Ali vs Bruce Lee | 16 | 3 | 30 | `muhammad-ali` (стойки) |
| Nikola Tesla | Adventures: Tales to Amaze | 14 | 2 | 30 | — |
| Oda Nobunaga | Sun's Origin | 13 | 2 | 30 | `oda-nobunaga` |
| Pandora | Battle of Legends, Volume Three | 14 | 2 | 30 | — |
| Philippa | The Witcher - Realms Fall | 12 | 2 | 30 | `philippa` |
| Raphael | Adventures: Teenage Mutant Ninja Turtles | 17 | 2 | 30 | `raphael` |
| Raptors | Jurassic Park - Ingen vs. Raptors | 7 | 3 | 30 | `raptors` |
| Robert Muldoon | Jurassic Park - Ingen vs. Raptors | 14 | 3 | 30 | — |
| Robin Hood | Robin Hood vs Bigfoot | 13 | 2 | 30 | `robin-hood` |
| Shakespeare | Slings and Arrows | 13 | 2 | 30 | — |
| She Hulk | Brains and Brawn | 20 | 2 | 30 | — |
| Sherlock Holmes | Cobble & Fog | 16 | 2 | 30 | — |
| Shredder | TMNT: Shredder vs Krang | 15 | 3 | 30 | — |
| Sinbad | Battle of Legends, Volume One | 15 | 2 | 30 | — |
| Spiderman | Brains and Brawn | 15 | 3 | 30 | — |
| Spike | Buffy the Vampire Slayer | 15 | 2 | 30 | — |
| Squirrel Girl | Teen Spirit | 13 | 2 | 30 | — |
| Sun Wukong | Battle of Legends, Volume Two | 17 | 2 | 30 | — |
| T. Rex | Jurassic Park - Sattler vs. T-Rex | 27 | 1 | 30 | `t-rex` |
| The Genie | Houdini vs. The Genie | 16 | 3 | 30 | — |
| The Wayward Sisters | Slings and Arrows | 6 | 2 | 30 | — |
| Titania | Slings and Arrows | 12 | 2 | 30 | — |
| Tomoe Gozen | Sun's Origin | 14 | 2 | 30 | `tomoe-gozen` |
| Willow | Buffy the Vampire Slayer | 14 | 2 | 30 | — |
| Winter Soldier | For King and Country | 15 | 2 | 30 | — |
| Yennefer & Triss | The Witcher - Realms Fall | 14 | 2 | 30 | — |
| Yennenga | Battle of Legends, Volume Two | 15 | 2 | 30 | — |

Замечания: Daredevil в контент-модуле `backend/src/content/data/heroes/daredevil.ts` — 5 уникальных ×3 = 15 карт (Billy Club, Radar Sense, Mania, Grappling Hook, Daredevil), в скрапе — 22 карты / 8 уникальных; Ms. Marvel — 15 в модуле / 30 в скрапе (doc08:231, 238, 295). Deadpool — 30 уникальных ×1 (doc08:128).

### 2.10. Сводная статистика карт (по 70 таблицам doc09 §4, подсчитано скриптом)

- **Итого**: 70 героев, **880 уникальных строк карт** (совпадает с doc09:181 «880 карт»), **2094 копий**. Размер колод: 30 копий у 65 героев; Elektra 20, Daredevil 22, Black Widow 31, Buffy 35, Geralt of Rivia 36.
- **Типы** (уникальных / копий): `attack` 267 / 622, `versatile` 348 / 896, `defense` 114 / 263, `scheme` 151 / 313. Тип `maneuver` — 0.
- **Значение (value)**: attack 0–7; versatile 0–7 (4 карты без значения «—»); defense 0–5 (3 без значения); scheme — «—» у 140, `0` у 11. Гистограмма по уникальным: 0 → 28, 1 → 52, 2 → 221, 3 → 252, 4 → 125, 5 → 41, 6 → 9, 7 → 5, «—» → 147. Максимум 7: Blackbeard «Queen Anne's revenge» (versatile), Cloak Dagger «Lightforce Barrage», Sun Wukong «Ox Form», Tomoe Gozen «Witness My Last Battle», Yennefer «Incinerate».
- **BOOST**: 0–4, одна карта 6 (Deadpool «Push to Teleport»), 8 карт без BOOST («—»: 6 Sinbad «Voyage …», Krang «IQ of 968», «Pan-dimensional Portal»). Гистограмма: 0 → 4, 1 → 232, 2 → 378, 3 → 220, 4 → 37, 6 → 1, «—» → 8.
- **Копий**: 1 → 80 карт, 2 → 403, 3 → 380, 4 → 17.
- **Banner** (пометка `(Имя)` в таблицах doc09): `Any` — 256; без пометки (карта героя) — 413; именные (сайдкик/герой) — 211, 62 различных имени. Крупнейшие: Geralt 13, Ali 13, Spider Man 12, Tesla 11, T-Rex 11, Allice 8, Holmes 7, Michelangelo (с пробелом) 7, Annie 6, Arthur 6, Leshen 5, Houdini 5, Mr. Hyde 5, Dr. Jekyll 5, Merlin 5, Muldoon 4. Опечатки источника: `Allice`, `Djkstra`, `Michelangelo ` (trailing space), `Spider Man` (vs «Spider-Man» в тексте). Валидация `bannerAllows` в движке — по имени бойца; для «Harpy 2» ↔ «Harpy» есть матч по префиксу только у `NAMED_FIGHTER` (doc09:145) — как banner-валидатор сопоставляет `Harpies`/`Harpy`, `Outlaws`/`Outlaw`, `The Sisters`/`Sister` — в источниках не описано.
- **HP героев**: 6 (The Wayward Sisters) … 27 (T. Rex). **Move**: 1 → 3 героя (Ancient Leshen, Krang, T. Rex), 2 → 51, 3 → 16.
- **Сеты**: 25 (Battle of Legends I/II/III по 4; Buffy 4; Tales to Amaze 4; TMNT Adventures 4; Cobble & Fog 4; Slings and Arrows 4; Witcher S&S 3; For King and Country 3; Hell's Kitchen 3; Teen Spirit 3; Brains and Brawn 3; Witcher Realms Fall 3; Redemption Row 3; и по 1–2: LRRH vs Beowulf, RH vs Bigfoot, Bruce Lee, Deadpool, JP Sattler vs T-Rex, Houdini vs Genie, TMNT Shredder vs Krang, Ali vs Bruce Lee, Sun's Origin, JP Ingen vs Raptors).
- **Карт без эффекта** («—»): 19 (чистые числа, напр. Bigfoot «Larger Than Life» 6, Luke Cage «Sweet Christmas!» 6, Leonardo «Katana» 6, King Arthur «Excalibur» 6).
- **Тайминги в текстах** (по строкам): `after` 452, `during` 200, `effect` (scheme/пояснение) 176, `immediately` 126, `ongoing` 7, `boost` (BOOSTED WITH — только Houdini) 6.
- **Ключевые механики в текстах** (кол-во карт): Cancel all effects 72; Gain N action 86; Draw 176; Move up to N 124; Place in any space 39; Deal N damage 130; recover health 70; «value is N instead» 56; «+N for each» 40; ignore the value 23; look at hand 23; swap spaces / now the defender 11; cannot be canceled 10; cannot leave (immobilize) 8; Summon 8; Return to hand 14; End the turn 7; Prevent all damage 2; play face up 4; ресурсы/токены/спец-сущности 122.
- **Карты с «Choose one / choose N different effects» (CHOOSE_ONE UI, 16)**: Alice «Looking Glass» (2 из 3), Beowulf «Golden Drinking Horn», Dr. Jill Trent «Utility Belt», Geralt «Riposte», Hamlet «The Ghost», Krang «Welcome to the Technodrome!», Loki «Shapershifter», Michelangelo «Shell insertion» (2 из 4), Ms. Marvel «Shrink! Shrink! Shrink!» (1 или оба), Nikola Tesla «The Alternating Current», Oda Nobunaga «Reinforce» (2 из 3), Philippa «Backup plan», Robert Muldoon «Call for Backup» (2 из 3), The Genie «Three Wishes», Titania «Gift Of The Fair Folk» (2 из 3), Tomoe Gozen «Lord Kiso's Final Stand». (Плюс Yennefer «Merigold's Hailstorm» — выбор делает **оппонент**; Wayward Sisters «Hurly-Burly» — тоже оппонент.)

### 2.11. Версия контента и инвалидация кэша

- `CONTENT_VERSION = '2.0.0'` (`content-db.service.ts:12`); query `contentVersion` возвращает её (`:81`); `contentSummary.version` — она же (`:413`); `getContentDiff(oldVersion)` — примитивный diff «всё изменилось» (`:354-364`, doc05:387).
- Redis-кэш: TTL 3600 с (`:17`), отключается `DISABLE_CACHE=true` (`:22`), ключи `content:heroes:all`, `content:boards:all`, `content:heroes:<id>`, `content:heroes:slug:<slug>`, `content:boards:<id>`, `content:heroes:set:<set>` (`:28-33`); `clearContentCache` — публичная mutation-like query (`content.resolver.ts:180-181`).
- Версия — константа в коде, **не меняется при правке контента через админку/сиды** → сравнение `contentVersion` не гарантирует свежести; дополнительно можно сравнивать `Hero.updatedAt` (доступен в `heroes`) и `contentSummary.heroesCount/boardsCount`.
- Рекомендуемый порядок загрузки (doc05:637-645): 1) `contentVersion`/`contentSummary` → сверить с локальным кэшем; 2) `AllHeroes` (каталог + URL аватаров); 3) `HeroDetails` по выбранным героям (колоды, способности, URL карт) — по одному, а не `heroes { cards }` (N+1, doc05:474); 4) `AllBoards`; 5) `HeroStanceOptions` для stance-героев; 6) скачать изображения по URL; 7) в матче — игровые мутации/подписки.

### 2.12. Статические ассеты

**Где**: `public/assets/**` на фронте, Vite `publicDir: 'public'` (`vite.config.ts:20`); бэкенд их не раздаёт (doc05:478). Фактическое дерево (листинг ФС на дату исследования; 276 `.webp`, 112 `.png`, 1 `.json`, 1 `.md`):

```
public/assets/
├── boards/hells-kitchen.webp                     # единственная картинка борда (129 KB)
├── decks/card-assets.generated.json              # манифест (generatedAt 2026-06-14T11:32:33Z)
├── decks/<hero-slug>/<card-slug>.webp            # EN; 18 героев: blackbeard, chupacabra, ciri, daredevil,
│                                                 #   deadpool, donatello, eredin, krang, leonardo, loki,
│                                                 #   michelangelo, ms-marvel, muhammad-ali, pandora,
│                                                 #   philippa, raphael, shredder, yennefer-triss
├── decks/<hero-slug>/ru/<card-slug>-ru.(webp|png) # RU — частично
├── heroes/daredevil/{avatar,mini,card-cover}.webp  # медиа только 2 героев
├── heroes/ms-marvel/{avatar,mini,card-cover}.webp
├── ui/hud/  action-buttons, board-frame-6x4, board-vignette, deck-slot, discard-slot,
│            hand-tray, hand-tray-mobile, hidden-card-back, mobile-bottom-sheet,
│            player-panel-local, player-panel-opponent, selected-card-panel,
│            status-badges, turn-phase-pill, zone-legend-chip      (15 × .png)
├── ui/effects/ attack-highlight, card-play-flash-strip, defense-shield, hit-spark-strip,
│               move-highlight, selection-ring                       (6 × .png)
└── phaser/README
```

**Покрытие колод (манифест vs диск)** — `card-assets.generated.json` (`{generatedAt, heroes: {<slug>: {id, name, cards: [{id, title, imageUrl, imageUrlRu}]}}}`): 18 героев, 227 карт, все 227 с EN `.webp` (все существуют на диске); `imageUrlRu` задан у 61 карты (blackbeard 12 `.png`, deadpool 30 = 23 `.webp` + 7 `.png`, daredevil 8 `.webp`, ms-marvel 11 `.webp`). На диске RU-файлы есть ещё у chupacabra (11 png), ciri (11), donatello (12), eredin (2), loki (11), michelangelo (12), muhammad-ali (1), pandora (12), но в манифесте у них `imageUrlRu` нет → **манифест устарел относительно диска** (перегенерировать `node scripts/sync-card-assets.mjs`). Списки целевых героев: `scripts/verify-card-asset-coverage.mjs:9-28`.

**Правило слагификации** (`scripts/sync-card-assets.mjs:23-30`): `NFKD` → убрать диакритику → убрать `'` и `’` → lowercase → все не-`[a-z0-9]` последовательности → `-` → обрезать `-` по краям. Примеры на диске: «Devil of Hell's Kitchen» → `devil-of-hells-kitchen.webp`, «Take A Knee» → `take-a-knee.webp`. `card.id` в манифесте = slug(title) (`:87`). EN-цель всегда `<slug>.webp` (`:138`), RU — `<slug>-ru<ext>` с `ext ∈ .webp/.png/.jpg/.jpeg` из локализованной папки (`:15, :113-115`). Слаг героя = ключ скрапа `key` (`ms-marvel`, `yennefer-triss`, `t-rex`, `dr-jill-trent`), совпадает с `slugifyHeroName` движка для проверенных случаев (doc05:92: `'Ms. Marvel' → 'ms-marvel'`).

**URL-паттерны** (doc05:500-509, с поправками по факту):

| Ассет | Паттерн | Примечание |
|---|---|---|
| Карта EN | `/assets/decks/<heroSlug>/<cardSlug>.webp` | подтверждено |
| Карта RU | `/assets/decks/<heroSlug>/ru/<cardSlug>-ru.png` (doc05:488,505) | **фактически `.webp` у daredevil/ms-marvel/23 карт deadpool, `.png` у остальных** — расширение брать из `Card.imageUrlRu`/манифеста, не вычислять |
| Аватар героя | `/assets/heroes/<heroSlug>/avatar.webp` | есть только для 2 героев |
| Миниатюра | `/assets/heroes/<heroSlug>/mini.webp` | то же |
| Обложка/рубашка | `/assets/heroes/<heroSlug>/card-cover.webp` | то же |
| Борд | `/assets/boards/<boardSlug>.webp` | есть только `hells-kitchen.webp`; в БД `Board.imageUrl` — Supabase |

**Что реально в БД**: по сидам — абсолютные Supabase-URL (`seed-scraped.ts:308-309` герои, `:347-348` карты; `seed-all-scraped.ts:306-307` борды; `update-card-images.ts:166-171` тоже из скрапа). Утверждение doc05:478 («URL в БД — корневые пути `/assets/…`») **не подтверждается кодом сидов**; вероятно, часть URL заменена вручную через админку (`updateCard`) или скриптами — проверить вживую (`hero(id:"Daredevil") { cards { imageUrl } }`). Fallback-модуль `daredevil.ts:84-85` содержит `/assets/decks/daredevil/grappling-hook.webp` (только у одной карты), а `urls` — Supabase (`:111-117`). **Вывод для UE**: резолвер URL должен принимать и абсолютные `https://…`, и корневые `/assets/…` (префикс = хост фронта/CDN, конфигурируемый).

### 2.13. Связь контента с игровым состоянием (для маппинга на ассеты)

- `Fighter.heroId` = **Prisma cuid** героя (и у героя, и у сайдкиков) (`game-initialization.service.ts:143-144, 156, 175`); `Fighter.heroSlug = slugifyHeroName(hero.name)` (`:144, 168, 189`). Публичный `Hero.id` = имя → для маппинга бойца на контент использовать `hero(id: fighter.heroId)` (cuid принимается) либо `heroSlug` для путей ассетов.
- Сайдкики строятся из `Hero.sidekicks` JSON с разворотом `count/quantity` (≤ 4) и именами `"<name> N"` при count > 1 (`:425-441`); `type: MINION`, HP/движение из JSON (default 1 / 2), `attackType` нормализуется `'range' → 'ranged'` (`fighter.model.ts:97`).
- Тип атаки героя-бойца — из `Hero.properties.attackType` (`:186-188`), движение — из `Hero.movement` (`:185`), default 2 (`fighter.model.ts:65`).
- Экземпляр карты: `id = "${cardId}::n"`, `cardId` = cuid из контента (doc05:101-102) → изображение карты ищется по `cardId` в загруженном каталоге `Card.id`.
- `bannerName` в движковой карте (в игровом состоянии) — единственное место, где клиент видит ограничение «кто может играть» (doc09:32).

---

## 3. Следствия для UE-клиента

1. **Слой контента должен строиться на публичном GraphQL контента, но не доверять пяти полям**: `Hero.movement` (константа 3 — показывать движение из игрового `Fighter.movement`), `Card.value` для SCHEME и карт без печатного значения (равен BOOST — для SCHEME значение не рисовать), `Card.characterName` (это название карты, не banner), `Hero.urls.mini/cardCover` (оба = рубашка колоды), `Hero.sidekickHealth` (всегда null).
2. **Не выбирать `effects { timing }` в контентных запросах** до живой проверки: маппер генерирует значения вне GraphQL-enum для бэкфилленных эффектов; безопасно `effects { id text }`. Основной текст карты (`Card.text`) публично не доступен — для отображения правил карты вне матча опираться на **изображение карты** (`imageUrl`/`imageUrlRu`), в матче — на `Card.text`/`effects` из игрового состояния.
3. **Banner-ограничения** (кто может играть карту) в каталоге недоступны без JWT-запроса `cardList` (там `bannerName`). Варианты: (а) после логина подгрузить `cardList(heroId)` для выбранных героев; (б) в матче использовать `bannerName` карт из руки; (в) просить бэкенд добавить `bannerName` в публичный `Card`.
4. **Тип атаки (melee/ranged) героя и сайдкиков** публично не отдаётся → для подсветки целей брать `Fighter.attackType` из игрового состояния (R4), либо запросить расширение DTO. Для 29 героев реестра справочные значения есть в §2.8.
5. **Сетка борда**: размер брать из `spaces` (max x/y + 1), а не из `width/height` (пиксели для скрапнутых досок); `recommendedPlayers` всегда 2; `startingPositionsJson` всегда null; зоны — 12 базовых цветов `Zone`, клетка может быть в 1–2 зонах (мультизонность → ranged-дальность и зонные условия).
6. **Резолвер URL ассетов**: поддерживать абсолютные Supabase-URL (`.webp/.png/.gif`) и корневые `/assets/...` (base = хост фронта/CDN из конфига). Кэшировать на диске по ключу URL; расширение RU-карт не вычислять, а брать из данных. Готовые локальные ассеты есть лишь для 18 колод и 2 героев — остальное качается из Supabase.
7. **Обязательные интерактивы** (без них игра зависнет в pending): (а) MOVE/PLACE pending — подсветка клеток + выбор/отказ → `resolvePendingEffect`; (б) CHOOSE_ONE — диалог по `options[].label`, `chooseCount`, повторный выбор при `chooseCount > 1`; (в) BOOST из руки при атаке/защите/манёвре (`boostCardId`, запрет той же карты, отображение +boost и последующего добора); (г) стойки — `heroStances(heroSlug)` → кнопки `setStance` + индикатор `metadata.heroStances[userId]`; (д) BLIND BOOST Daredevil — кнопка, активная при руке ≤ 2 и непустой колоде; (е) Ms. Marvel turn-start move — выбор из 4 соседних клеток.
8. **Подсветка целей атаки**: melee — смежные; ranged — смежные ∪ та же зона; плюс дальность `attackRange` для bullseye (5), t-rex (2), ms-marvel (2), muhammad-ali только в `float` (2) — всё Manhattan, игнорируя зоны. Сервер валидирует; клиент лишь предлагает.
9. **Лог/уведомления обязательны** для: `appliedEffects`, `manualEffects` (UNSUPPORTED/ручные), `combatSummary` (finalAttack/finalDefense/урон/cancel-флаги), авто-эффектов способностей (turn-damage Dracula/Medusa, реактивный урон Tomoe, авто-смена стойки Ali, сброс 2 карт Achilles, добор/лечение/действия), отмены эффектов карты (CANCEL_EFFECTS — 72 карты).
10. **Каталог героев**: фильтровать `fighterType == HERO` (в `heroes` могут быть NPC/миньоны из `seed-all-scraped`); имя как ключ (`Hero.id`), при этом хранить cuid из игрового состояния для обратного маппинга; `abilities[0].name` = "Ability" — заголовок способности вытаскивать из текста (первые слова капсом) или показывать только текст.
11. **41 герой без реализованной способности** — показывать текст способности с пометкой «ручное применение», не обещать автоматики; карты с ресурсами/токенами (122) в бою дадут `UNSUPPORTED`/`manualEffects`.
12. **Инвалидация**: сравнивать `contentVersion` + `contentSummary.heroesCount/boardsCount` + max(`Hero.updatedAt`) — сама версия константна. При загрузке всех героев использовать `heroesPaginated` без `cards`, затем `hero(id)` по одному (N+1 на сервере при вложенном `cards`).
13. Локализация: `nameRu` героев и карт = английские (сид не переводит); RU-изображения карт есть частично; текст карт RU (`textRu`) публично не отдаётся. UE-клиент должен иметь fallback EN → RU-картинка при наличии.

---

## 4. Открытые вопросы / несоответствия

1. **`Card.effects[].timing` в публичном API** — `content.mapper.ts:378-386` превращает `DURING_COMBAT` в `d_u_r_i_n_g_c_o_m_b_a_t` (проверено логикой функции в node), а парсер пишет именно верхний регистр (`effect-text-parser.ts:62-64`). Значения `ON_REVEAL/ON_PLAY/TURN_*` в любом случае отсутствуют в контентном enum (`IMMEDIATELY/WHEN_PLAYED/START_OF_TURN/END_OF_TURN`). Ожидаемый эффект — ошибка сериализации GraphQL при выборке `timing` у бэкфилленных карт. **Не проверено вживую** (бэкенд не запущен). Фронт в `HeroDetails` `effects` не запрашивает (`src/graphql/queries/heroes.graphql`), в `GetCard` — запрашивает.
2. **URL в БД: `/assets/...` (doc05:478, 511) vs Supabase (все сиды)** — какой формат реально лежит в `Card.imageUrl`/`Hero.avatarUrl`/`Board.imageUrl`? Проверить `hero(id:"Daredevil"){ urls{avatar} cards{imageUrl imageUrlRu} }`.
3. **Расширение RU-карт**: doc05:488,505 — `.png`; на диске у daredevil/ms-marvel/большинства deadpool — `.webp`; манифест содержит оба варианта.
4. **Манифест `card-assets.generated.json` устарел**: RU-файлы на диске у 8 героев (chupacabra, ciri, donatello, eredin, loki, michelangelo, muhammad-ali, pandora) не отражены в `imageUrlRu`.
5. **Фантомный сайдкик у героев без сайдкиков**: в скрапе у daredevil/ms-marvel/bullseye/raptors/t-rex поле `sidekicks` содержит placeholder `{name:"", startHealth:0, move:0}` (извлечено скриптом из `scraped-data/api/heroes/*.json`); `seed-scraped.ts:202-245` превращает его в `{name:'Unknown', health:1, movement:1, attackType:'melee'}`, а `properties.sidekickCount = sidekicks.length` (`:297`) → `sidekickCount = 1` и при старте игры `game-initialization.service.ts:146-168` создаст MINION «Unknown». Могли исправить `fix-audit-findings.ts`/`update-all-heroes.ts` (там тот же fallback `'Unknown'`, `:132`, `:181,190`). Проверить в БД: `SELECT name, sidekicks, properties FROM "Hero" WHERE name IN ('Daredevil','Bullseye')`.
6. **`Hero.movement`** — doc05:396 и код (`mapper:64,200`) согласны, что публично отдаётся 3; реальное значение в БД `hero.move || 2`. Нужен фикс на бэке или игнорирование поля клиентом.
7. **`fighterType` расходится по путям**: `heroes/heroesPaginated` → парсинг из БД; `hero/heroesBySet` → всегда HERO (`mapper:43`).
8. **Cobble City**: 5×6 в `seed.ts:261-262` (grid, `cells: []`, зоны дефолтные `['blue','red']` по `backfill-board-cells.ts:39`) vs 6×4 с 5 зонами и мультизонными клетками в `content/data/boards/cobble-city.ts:14-59`. Какая версия реально в БД и используется `getDefaultBoard('cobble-city')` — проверить (`board(id:"Cobble City"){width height spaces{...}}`).
9. **Число героев**: doc09:181 — 70 героев/880 карт (скрап); память о запуске — ≈ 84 героя в БД (NPC/миньоны из `villains.json`/`minions.json`). Как они помечены (`fighterType MINION/HUGE`?) и стоит ли их скрывать в каталоге — проверить `heroes { id fighterType set }`.
10. **`bannerName` публично недоступен** — нужен ли фикс DTO (добавить `bannerName` в `Card`) или клиент берёт его из JWT `cardList`/игрового состояния? Также неясно, как `bannerAllows` матчит `Harpies`/`Harpy`, `Outlaws`/`Outlaw`, `The Sisters`/`Sister`, опечатки `Allice`/`Djkstra`/`Michelangelo ` — не описано в источниках; в `game-rules.validator.ts` не проверялось (вне фокуса R5).
11. **Путь скрап-данных**: doc08:10 и doc09:3 указывают `backend/scraped-data/api/heroes/*.json` / `scraped-data/api/heroes/*.json`; фактически каталог — `<repo>/scraped-data/api/heroes/` (в `backend/` его нет).
12. **`abilities[].name`** для скрапнутых героев — литерал `'Ability'` (`Hero.ability` без `name`, `seed-scraped.ts:288-293`; `mapper:70`). doc05:397 описывает парсинг «в `[{id,name,text,trigger}]`», не упоминая, что имя не заполняется.
13. **`characterName` карты** — doc05:398 перечисляет поле без семантики; код: `nameEn || name` карты (`mapper:228`). Если задумывалось имя бойца — это баг маппера.
14. **CardType MANEUVER**: сид пишет `MANEUVER` (`seed-scraped.ts:180`), публичный маппер не знает его → VERSATILE. В doc09-таблицах maneuver-карт нет; есть ли они в БД — неизвестно.
15. **Blind Boost превью** (`peekTopCard`/`getBoostValue`, doc08:230) — есть ли GraphQL-запрос/поле для превью верхней карты клиенту, не найдено в контентных источниках (вопрос к R4 game API).
16. **`sidekickHealth`** нигде не пишется; `Hero.sidekicks` (имена/HP/движение/тип атаки/аватар сайдкиков) публично не отдаётся — UE-клиент не сможет показать сайдкиков до старта матча без расширения DTO.
17. Живая проверка всех пунктов 1–9 требует `docker compose up` (порт 3000; см. `memory/unmatched-launch-procedure.md:13-14`).

---

## 5. Источники

Документы:
- `docs/backend-api/05-engine-and-content.md` — A.2 (94-143), A.3 (173-183), A.4 (187-223), A.5 (225-235), A.6 (237-253), A.7 (255-331), B.1 (347-381), B.2 (383-400), B.3 (402-474), B.4 (476-511), B.5 (513-645), приложение (649-674).
- `docs/backend-api/08-heroes-abilities.md` — 1-77 (система), 81-238 (29 героев), 242-250 (приближения), 254-295 (чеклист).
- `docs/backend-api/09-cards-and-effects.md` — 7-90 (модель), 94-157 (EffectType/timing/target/парсер), 161-177 (BOOST), 181-1555 (реестр 70 героев).

Код (сверка):
- `backend/src/content/dto/content.dto.ts` (30-260), `backend/src/content/interfaces/{hero,card,board}-definition.interface.ts`, `backend/src/content/mappers/content.mapper.ts` (29-99, 189-259, 263-322, 350-466), `backend/src/content/content-db.service.ts` (12-33, 81, 97-102, 176-229, 329-364, 413), `backend/src/content/content.resolver.ts` (25-181), `backend/src/content/data/heroes/daredevil.ts`, `backend/src/content/data/boards/cobble-city.ts`.
- `backend/src/games/game.resolver.ts` (100-109), `backend/src/games/dto/gameplay.dto.ts` (362-370), `backend/src/games/services/game-initialization.service.ts` (141-192, 425-441), `backend/src/admin/dto/admin.dto.ts` (820-860), `backend/src/admin/admin.resolver.ts` (208-233).
- `backend/src/game-engine/models/card.model.ts` (10-301), `backend/src/game-engine/models/fighter.model.ts` (65, 80, 97), `backend/src/game-engine/abilities/ability-config.ts` (365-422, 439-891), `backend/src/game-engine/effects/effect-text-parser.ts` (62-64).
- `backend/prisma/schema.prisma` (399-527), `backend/prisma/seed-scraped.ts` (142, 174-245, 277-350), `backend/prisma/seed-all-scraped.ts` (115-135, 285-315), `backend/prisma/seed.ts` (256-270), `backend/prisma/backfill-board-cells.ts` (1-40), `backend/prisma/update-card-images.ts` (166-171), `backend/prisma/fix-audit-findings.ts` (132).
- `scripts/sync-card-assets.mjs` (12-30, 87, 113-138, 172-219), `scripts/verify-card-asset-coverage.mjs` (9-28), `vite.config.ts` (20), `src/gql/graphql.ts` (24-31, 256-261, 363-372, 395-398, 1746-1758), `src/graphql/queries/heroes.graphql`, `src/graphql/queries/cards.graphql`.
- Файловая система: `public/assets/**`, `public/assets/decks/card-assets.generated.json`, `scraped-data/api/**` (88 файлов; Nuxt-payload).
- Память запуска: `C:/Users/ren/.claude/projects/C--Users-ren-WebstormProjects-unmached-unmached/memory/unmatched-launch-procedure.md` (13-14, 23-24).
