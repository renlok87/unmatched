# R9 — Ассеты и дизайн-система (research для UE-клиента)

Дата: 2026-09-02. Ридер: R9-assets-design-system.
Все пути — относительно корня репозитория `C:/Users/ren/WebstormProjects/unmached/unmached/`.
Размеры изображений измерены PIL (`python -c "from PIL import Image"`) по каждому файлу `public/assets/**` (388 файлов); размеры каталогов — `du -sb`.

---

## 1. Краткое резюме

1. Все статические ассеты клиента лежат в `public/assets/` (Vite `publicDir: 'public'`, `vite.config.ts:20`), раздаются фронтендом как корневые URL `/assets/…`; бэкенд Nest их не раздаёт (`docs/backend-api/05-engine-and-content.md:478`). **В git они не закоммичены** — `git ls-files public/assets` возвращает только `public/assets/phaser/README.md`; каталоги `boards/`, `decks/`, `heroes/`, `ui/` в статусе `??` (git status). Источник правды — локальный диск + Supabase-хранилище `https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/{decks,decks/ru,heroes/avatars,heroes/minis,heroes/card-covers,maps}/<nanoid>.webp`.
2. Инвентарь: **388 изображений, ≈229,3 МБ**: 276 WebP + 112 PNG. Из них: 1 борд (`hells-kitchen.webp`, 1337×866), 6 файлов героев (только `daredevil` и `ms-marvel`: avatar/mini/card-cover), **227 EN-карт (18 героев, WebP)**, **133 RU-карт** (42 WebP + 91 PNG-скан по ~2,5 МБ, итого 207,6 МБ — 90 % всего объёма), 15 HUD-PNG + 6 FX-PNG (сгенерированы PowerShell-скриптом, суммарно 104 КБ).
3. Покрытие: EN 227/227 для 18 героев из `TARGET_HEROES` (`scripts/verify-card-asset-coverage.mjs:9-28`); RU 133/227 — **94 RU-карты отсутствуют** (krang, leonardo, philippa, raphael, shredder, yennefer-triss — полностью; eredin 9, muhammad-ali 12, donatello 2). Из 88 «героев» scraped-data колоды локализованы для 18; медиа героя (avatar/mini/cover) локально только у 2; в `scraped-data/images/heroes/` есть 70 аватаров, 77 миниатюр, 70 обложек (имена — nanoid, без slug).
4. Именование: `/assets/decks/<heroSlug>/<cardSlug>.webp` (EN), `/assets/decks/<heroSlug>/ru/<cardSlug>-ru.{webp|png}` (RU), `/assets/heroes/<heroSlug>/{avatar,mini,card-cover}.webp`, `/assets/boards/<boardSlug>.webp`. `cardSlug = slugify(title EN)` (NFKD, удаление апострофов, `[^a-z0-9]+ → -`), `scripts/sync-card-assets.mjs:23-31`. Манифест `public/assets/decks/card-assets.generated.json` **устарел** (generatedAt 2026-06-14T11:32Z, показывает ru=0 для 14 героев, хотя RU-файлы есть).
5. Дизайн-токены существуют в **трёх несогласованных слоях**: (a) Figma-спека `docs/figma/DESIGN_SYSTEM.md` + `design-system.json` (карта 300×420, палитра #FFD700/#6B4C9A/#DC143C/#1E3A8A, Impact/Arial vs Inter); (b) реальные CSS-токены React `src/design-system/design-tokens.css` (Tailwind-подобная палитра, карта 140×200, клетка 80 px, Inter); (c) константы Phaser-HUD `src/phaser/scenes/GameScene.ts:52-80` (тёмная база `0x040711`, золотая линия `0xf2b84b`, cyan `0x00d4ff`, red `0xff3f4f`, 12 цветов зон, Arial). Для UE базовым слоем следует считать (c) + (b).
6. Три HUD-концепта (`docs/hud-concepts/hud-{noir-tactical,premium-tabletop,arcade-comic}.png`, 1672×941) — AI-генерированные референсы одной и той же композиции: оппонент вверху слева, фаза по центру вверху, рука оппонента вверху справа, борд по центру, локальный игрок внизу слева, рука внизу по центру, колода/сброс внизу справа. Финальный HUD (`hud-game-desktop-final.png`) реализован в Phaser 800×600 **процедурно** (панели рисуются `drawComicPanel`, а не PNG-ассетами) в стиле «arcade-comic/noir»; из 21 сгенерированного UI-PNG на сцене реально используются только `board-vignette.png` и `board-frame-6x4.png` (`GameScene.ts:300-330`).
7. Для UE: WebP (276 файлов, вся EN-графика карт, герои, борд) требует конвертации в PNG/TGA офлайн либо WebP-декодера в клиенте; RU-PNG-сканы 1030–1065 × 1477–1526 требуют даунскейла/нормализации; все карты имеют пропорцию ≈ 0,716 (покерная 63,5×88,9 мм) — канонический размер текстуры карты для UE предлагается 512×716 (без мипов, группа UI) или паддинг до 1024×2048 (мипы/стриминг); спрайт-полосы (64×64×8, 96×96×8, 64×64×6, 72×72×5) — во Flipbook/атлас Paper2D.

---

## 2. Факты по темам

### 2.1. Расположение, раздача, отслеживание

| Факт | Источник |
|---|---|
| Vite: `publicDir: 'public'`, `assetsInclude: ['**/*.png','**/*.jpg','**/*.jpeg','**/*.webp']` | `vite.config.ts:20,22` |
| URL в БД (`imageUrl` и т. д.) — корневые пути `/assets/…`, резолвятся относительно хоста фронтенда/CDN; бэкенд их не раздаёт | `docs/backend-api/05-engine-and-content.md:478` |
| Единственный отслеживаемый git-файл в `public/assets` — `phaser/README.md`; остальные каталоги untracked (`?? public/assets/boards/ decks/ heroes/ ui/`) | `git ls-files public/assets`, `git status` |
| Правил `.gitignore` для `public/assets` нет (grep по `assets|webp|png` в `.gitignore` пуст) | `.gitignore` |
| Каталог `public/assets/phaser/` содержит только README с описанием **несуществующих** placeholder-ассетов (board-placeholder 1024×768 8×8, fighter spritesheet 64×64 idle/walk/attack/hit/defeat, card 120×180, zones/*.png) | `public/assets/phaser/README.md:7-36` |
| `src/phaser/assets/AssetLoader.ts` ссылается на `/assets/fighters/<heroId>.png`, `/assets/portraits/<heroId>.png`, `/assets/boards/<boardId>.png` — таких файлов нет (устаревший загрузчик, экспортируется из `src/phaser/index.ts:41-52`) | `src/phaser/assets/AssetLoader.ts:126,132,171` |

Дерево (фактическое):

```
public/assets/
├── boards/hells-kitchen.webp                       1 файл, 129 036 Б
├── decks/                                          228 578 212 Б
│   ├── card-assets.generated.json                  95 105 Б (манифест, устарел)
│   └── <heroSlug>/<cardSlug>.webp  +  <heroSlug>/ru/<cardSlug>-ru.{webp|png}
│       (18 героев: blackbeard, chupacabra, ciri, daredevil, deadpool, donatello, eredin, krang,
│        leonardo, loki, michelangelo, ms-marvel, muhammad-ali, pandora, philippa, raphael,
│        shredder, yennefer-triss)
├── heroes/{daredevil,ms-marvel}/{avatar,mini,card-cover}.webp   6 файлов, 453 906 Б
├── phaser/README.md
└── ui/
    ├── hud/      15 PNG (генерируются scripts/generate-hud-assets.ps1)
    └── effects/   6 PNG (то же)                    ui/ итого 103 593 Б
```

### 2.2. Сводный инвентарь

| Категория | Файлов | Формат | Объём | Примечание |
|---|---|---|---|---|
| Борды | 1 | WebP RGBA 1337×866 | 129 КБ | `hells-kitchen.webp`; в Phaser ключ `board-cobble-city` (`gameAssetManifest.ts:42`) |
| Герои (avatar/mini/card-cover) | 6 | WebP | 454 КБ | только daredevil, ms-marvel |
| Карты EN | 227 | WebP (131 RGB + 96 RGBA) | 18,8 МБ | 18 героев |
| Карты RU | 133 | 42 WebP + 91 PNG | 209,7 МБ (PNG — 207,6 МБ) | 12 героев (частично) |
| HUD | 15 | PNG RGBA | ≈ 86 КБ | процедурно сгенерированы |
| FX | 6 | PNG RGBA | ≈ 27 КБ | 2 спрайт-полосы |
| **Итого** | **388** | 276 WebP / 112 PNG | **≈ 229,3 МБ** | |

Источник: замер PIL по `public/assets/**` и `du -sb` (см. шапку). Формула: 1 + 6 + 227 + 133 + 15 + 6 = 388.

### 2.3. Борды

| Факт | Источник |
|---|---|
| Локально один борд: `public/assets/boards/hells-kitchen.webp`, WebP RGBA, **1337×866**, 129 036 Б | замер PIL |
| В Phaser он зарегистрирован как `{ key: 'board-cobble-city', path: '/assets/boards/hells-kitchen.webp' }` — id борда `cobble-city`, арт — Hell's Kitchen | `src/phaser/assets/gameAssetManifest.ts:41-43`; `src/core/data/boards/cobble-city.ts:15,20`; `src/store/testGameStore.ts:721,726` |
| Паттерн URL борда по документации: `/assets/boards/<boardSlug>.webp` | `05-engine-and-content.md:509` |
| Рендер: сетка `width×height` клеток по `SPACE_SIZE = 72` px, `BOARD_TOP = 130`, по умолчанию 6×4 (432×288 px); арт рисуется под сеткой размером `boardW+32 × boardH+32` (464×320) с `alpha 0.72`; сверху `hud-board-frame-6x4.png` размером `boardW+44 × boardH+44`, alpha 0.9; под всем — `hud-board-vignette.png` 800×600 alpha 0.5 | `GameScene.ts:105-107, 300-330, 987-994` |
| Источник других бордов: `scraped-data/api/maps.json` — **29 карт** с абсолютными Supabase-URL (27 `.webp`, 2 `.avif`: `santas-workshop`, `venice`); физические размеры `width×height`: lg 505×405 (mcminnville-or, point-pleasant), md 420×275 (19 карт, в т. ч. hells-kitchen: 7 зон, 30 клеток), sm 400×230 (8 карт) | парсинг `scraped-data/api/maps.json` (`nodes[2].data`, поля `name,key,width,height,zones,image,zonesCount,spacesCount`) |
| В БД борды сидятся с `imageUrl: mapData.imageUrl` и `imageUrlDark: mapData.imageUrl` (тот же Supabase-URL) | `backend/prisma/seed-all-scraped.ts:307-308` |
| `BoardDto.imageUrl?` есть в GraphQL; `imageUrlDark` — в admin DTO | `backend/src/content/dto/content.dto.ts:202`; `backend/src/admin/dto/admin.dto.ts:189` |
| Пропорции: 1337/866 = 1,544; физ. 420/275 = 1,527; Phaser рисует арт 464/320 = 1,45 — лёгкое искажение | вычислено из чисел выше |

### 2.4. Герои: avatar / mini / card-cover

| Файл | Формат | Размер, px | Байт |
|---|---|---|---|
| `heroes/daredevil/avatar.webp` | WebP RGB | 402×402 | 49 652 |
| `heroes/daredevil/card-cover.webp` | WebP RGBA | 375×523 | 72 182 |
| `heroes/daredevil/mini.webp` | WebP RGBA | 558×764 | 24 380 |
| `heroes/ms-marvel/avatar.webp` | WebP RGB | **750×705** (не квадрат) | 185 940 |
| `heroes/ms-marvel/card-cover.webp` | WebP RGBA | 375×523 | 97 380 |
| `heroes/ms-marvel/mini.webp` | WebP RGBA | 558×764 | 24 372 |

| Факт | Источник |
|---|---|
| Ключи Phaser: `hero-mini-<id>`, `hero-avatar-<id>`, `hero-cover-<id>` для `HERO_ASSET_IDS = ['ms-marvel','daredevil']` | `gameAssetManifest.ts:6-12` |
| `HERO_VISUALS` содержит только `ms-marvel` (accent `0xd7b84b`) и `daredevil` (accent `0xb23a48`); для остальных — `FALLBACK_HERO` (ассеты ms-marvel, accent `0x4ecca3`) — поэтому на финальном скриншоте все фишки Achilles/Little Red имеют силуэт Ms. Marvel | `GameScene.ts:25-50, 1017-1020` |
| Источник массово: `scraped-data/images/heroes/avatars/` — 70 WebP RGB (56 шт. 402×402, остальные 450–1024 квадратные, один 750×705); `minis/` — 77 (58 WebP + 19 PNG), все RGBA **558×764**; `card-covers/` — 70 (54 WebP, 8 PNG, 5 JPEG, 1 AVIF, 2 GIF), 49 шт. 375×523, 9 шт. 768×1051, прочие 323×450…760×1051; `models/` — 6 `.glb` (0,48–1,84 МБ) | замер PIL по `scraped-data/images/heroes/*` |
| Имена файлов в scraped-data — nanoid (`kZQUve8tqIcvmVUC-bGge.webp`), соответствие slug → файл только через `scraped-data/api/normalized/<slug>.json` → `urls.avatar/mini/cardCover` и `cards[].url/filename` | `scraped-data/api/normalized/daredevil.json:1-10`; `scraped-data/summary.md:132-147` |
| Копия тех же файлов — `docs/figma/figma-ready/heroes/{avatars(70),card-covers(69),minis(77)}` и `docs/figma/figma-ready/decks/` (1794 файла); манифест `figma-import.csv` (1791 строка) объявляет размеры 150×150 / 300×420 / 100×100, **не совпадающие с реальными** | `find docs/figma/figma-ready`; `docs/figma/figma-ready/README.md:10-18`; `figma-import.csv:1-5` |
| В GraphQL `HeroDto.urls { avatar mini cardCover }` (абсолютные Supabase-URL из scraped), плюс `imageUrl?` (card back) и `avatarUrl?` | `backend/src/content/dto/content.dto.ts:31-40,141-148`; `backend/src/content/data/heroes/daredevil.ts:111-117` |
| Сид героев: `imageUrl: hero.cardBackImage`, `avatarUrl: hero.avatar`, `characterCardUrl`, `miniModelUrl` — всё Supabase | `backend/prisma/seed-scraped.ts:308-311`; `update-hero-images.ts:98-99` |
| Фронт запрашивает `urls { avatar … }` в `heroes.graphql:13-14,31-32,65-66`, `avatar` в `game.graphql:21,42,57` | указанные файлы |
| Фигурка на борде: `size = 62` (hero) / `48` (sidekick), mini `setDisplaySize(size,size)` (т. е. 558×764 сжимается в квадрат — искажение), круглая база `size/2+3`, HP-бар над фишкой 7 px | `GameScene.ts:405-430` |
| В панели игрока: cover 46×(h−12), аватар 44/50 px в круге r=24/27, mini 22/28 px | `GameScene.ts:614-631` |

### 2.5. Колоды карт — покрытие и размеры

Источники: замер PIL; `node scripts/verify-card-asset-coverage.mjs` (read-only) — итог «Missing assets (94)».

| Hero slug | EN файлов | EN размер, px (формат) | RU файлов | RU формат / размер | Пробелы RU |
|---|---|---|---|---|---|
| blackbeard | 12 | 396×555 RGB ×8; 590×827/829 RGB ×4; 396×554 RGBA ×2 | 12 | PNG RGB 1030–1062 × 1482–1526 | 0 |
| chupacabra | 11 | 396–398×554/555 ×8; 588×820 RGBA ×3 | 11 | PNG RGB 1051–1065 × 1477–1496 | 0 |
| ciri | 11 | **1005×1403** RGB ×11 | 11 | PNG RGB 1061–1065 × 1477–1483 | 0 |
| daredevil | 8 | 398×556 RGBA ×8 | 8 | **WebP RGB 402×556** | 0 |
| deadpool | 30 | 398×556 RGBA ×30 | 30 | WebP 407/408×575–578 ×23; PNG RGB ~1061×1483 ×2; PNG RGBA 398×556 ×5 (синтетика, см. 2.7) | 0 |
| donatello | 14 | 413×578 RGB ×14 | 12 | PNG RGB 1054–1060 × 1484–1493 | 2 (smoke-bomb, bo-staff) |
| eredin | 11 | **250×349** RGBA ×11 | 2 | PNG RGB 1061×1482/1483 | 9 |
| krang | 10 | 546×763 RGB ×10 | 0 | — | 10 |
| leonardo | 12 | 413×578 RGB (один 414×578) | 0 | — | 12 |
| loki | 11 | 396×555 ×4; 396×554 RGBA ×2; 590×827/829 ×5 | 11 | PNG RGB 1051–1060 × 1484–1496 | 0 |
| michelangelo | 12 | 413×578 RGB ×12 | 12 | PNG RGB 1053–1060 × 1484–1494 | 0 |
| ms-marvel | 11 | 398×556 RGBA ×11 | 11 | WebP RGB 402×556 | 0 |
| muhammad-ali | 13 | 546×763 RGB ×13 | 1 | PNG RGB 1060×1484 (jab) | 12 |
| pandora | 12 | 396×555 ×4; 396×554 RGBA ×2; 590×827/829 ×6 | 12 | PNG RGB 1035–1061 × 1483–1520 | 0 |
| philippa | 13 | 250×349 RGBA ×13 | 0 | — | 13 |
| raphael | 12 | 413×578 RGB ×12 | 0 | — | 12 |
| shredder | 13 | 546×763 RGB ×13 | 0 | — | 13 |
| yennefer-triss | 11 | 250×349 RGBA ×11 | 0 | — | 11 |
| **Итого** | **227** | | **133** | 42 WebP + 91 PNG | **94** |

Наблюдения:
- Все EN-карты имеют пропорцию ширина/высота ≈ 0,712–0,717 (398/556 = 0,716; 250/349 = 0,716; 413/578 = 0,714; 546/763 = 0,716; 1005/1403 = 0,716; 590/829 = 0,712). Это соответствует «300×420» дизайн-системы (0,714) и покерному формату 63,5×88,9 мм (0,714). — вычислено.
- Разрешение EN-арта различается по героям в 4 раза (250×349 у eredin/philippa/yennefer-triss против 1005×1403 у ciri) — источник: замер PIL.
- RU-PNG (91 файл) — неравномерные размеры 1030–1065 × 1477–1526 и ~2,5 МБ каждый, что типично для сканов/фото физических карт (интерпретация; факт — размеры из PIL). Скрипт `sync-card-assets.mjs` их не создаёт: он копирует только `.webp` из scraped-data (`sync-card-assets.mjs:138-139`), а для RU сначала ищет уже существующий файл с любым расширением из `IMAGE_EXTENSIONS` (`:109-120`). Происхождение RU-PNG в репозитории не задокументировано — **не найдено**.
- В `scraped-data/images/decks/` — 1575 файлов (1480 WebP, 95 PNG), топ размеров: 250×349 (233), 398×556 (233), 402×556 (228), 249×348 (168), 287×398 (133), 399×557 (116), 1005×1403 (63), 413×578 (58), 546×763 (43) — замер PIL. Это полный пул EN+RU карт всех 88 записей, но соответствие карта → файл есть только через `scraped-data/api/heroes/<slug>.json` (`nodes[2].data`, `item.image`, `item.i18n.ru.image`) — `sync-card-assets.mjs:51-96`.
- Карты 402×556 (228 шт. в scraped) — это RU-варианты (`decks/ru/<nanoid>.webp` в normalized JSON: `scraped-data/api/normalized/daredevil.json:14-17`).

### 2.6. Именование и соответствие slug ↔ файл ↔ API

| Факт | Источник |
|---|---|
| `slugify(title)`: `normalize('NFKD')` → удалить диакритику `[\u0300-\u036f]` → удалить `'` и `’` → lowercase → `[^a-z0-9]+` → `-` → обрезать дефисы по краям | `scripts/sync-card-assets.mjs:23-31`; идентично `verify-card-asset-coverage.mjs:38-46` |
| Примеры: «Avast Ye!» → `avast-ye`; «Queen Anne's Revenge» → `queen-annes-revenge`; «Deadpool™ Merc for Hire, LLC» → `deadpooltm-merc-for-hire-llc`; «3 of Hearts» → `3-of-hearts`; «I'm Not Touching You» → `im-not-touching-you` | `card-assets.generated.json`, имена файлов |
| Дубликаты title внутри колоды схлопываются (`bySlug.has(cardSlug) → continue`) — один файл на уникальное название | `sync-card-assets.mjs:88` |
| Hero slug = имя JSON в `scraped-data/api/heroes/<slug>.json` = имя каталога `public/assets/decks/<slug>` | `sync-card-assets.mjs:6,62,138` |
| В БД `Hero.id` — cuid; `getHeroBySlug(slug)` ищет `OR: [{id: slug}, {name: equals slug, insensitive}]` — т. е. «slug» на уровне API = имя героя (например `Ms. Marvel`), а не `ms-marvel` | `05-engine-and-content.md:351`; `backend/src/content/content-db.service.ts:176-193` |
| Во wire-состоянии игры у бойца есть `heroSlug?`; фронт берёт `definitionId = f.heroSlug ?? f.heroId`, этим ключом выбирает `HERO_VISUALS` и `getCardArtAsset(heroId, cardId)` (ключ `'<heroSlug>:<cardSlug>'`) | `src/lib/gameStateAdapter.ts:45,270`; `GameScene.ts:1027-1036`; `gameAssetManifest.ts:134-137` |
| Арт карты в бою: `heroAssets[heroName].cards.find(c => c.id === card.cardId || c.title === (card.nameEn ?? card.name))` → `imageUrl/imageUrlRu` | `src/lib/gameStateAdapter.ts:143-149, 250-262` |
| Выбор локали изображения: `definition.imageUrl || definition.imageUrlRu` — **EN приоритет, RU — только как fallback**; настройки локали для картинок нет | `src/components/cards/Card.tsx:48`; `src/store/testGameStore.ts:161` |
| Значения `Card.imageUrl/imageUrlRu` в БД: сиды пишут **абсолютные Supabase-URL** (`card.image`, `card.imageRu` из scraped) | `backend/prisma/seed-scraped.ts:347-348`; `update-card-images.ts:166-172` |
| Локальные `/assets/decks/...` пути есть только в статических данных двух героев (`daredevil.ts:84-85`, `ms-marvel.ts:36-37,54-55,72-73,90-91`, RU там указан как `-ru.webp`) | `backend/src/content/data/heroes/*.ts`; `src/core/data/heroes/*.ts` |
| Документация утверждает RU-паттерн `ru/<cardSlug>-ru.png`, фактически 42 из 133 RU — `.webp` (daredevil, ms-marvel, 23 deadpool); `sync-card-assets.mjs` при копировании из scraped всегда пишет `-ru.webp` | `05-engine-and-content.md:489,506`; `sync-card-assets.mjs:139,151` |
| Манифест `card-assets.generated.json`: `{ generatedAt, heroes: { <slug>: { id, name, cards:[{id,title,imageUrl,imageUrlRu}], missing:[{id,title,missingEn,missingRu,sourceImage}] } } }` | `sync-card-assets.mjs:190-204`; файл |
| Манифест устарел: `generatedAt: 2026-06-14T11:32:33Z`, 227 карт, `imageUrlRu` задан у 61 (blackbeard 12, deadpool 30, daredevil 8, ms-marvel 11), для 14 героев `missing` = все карты с `missingRu: true` и `sourceImage` = Supabase-URL; но на диске RU есть ещё у chupacabra, ciri, donatello, eredin, loki, michelangelo, muhammad-ali, pandora (каталоги `decks/` изменены 2026-06-14 14:12) | `node -e` парсинг манифеста; `ls -la public/assets/decks` |

### 2.7. Скрипты генерации и их источники

| Скрипт | Что делает | Вход | Выход | Источник |
|---|---|---|---|---|
| `scripts/sync-card-assets.mjs` | По списку героев (argv или `DEFAULT_HEROES = ['daredevil','ms-marvel','deadpool']`) парсит `scraped-data/api/heroes/<slug>.json` (`nodes[2].data`, элементы с `hero === 1|2`, `card.title`, `item.image`, `item.i18n.ru.image`), ищет файл по имени из URL в `scraped-data/images/decks/` затем в `docs/figma/figma-ready/decks/`, копирует как `<cardSlug>.webp` и `ru/<cardSlug>-ru.webp`; пишет манифест | scraped JSON + два каталога картинок | `public/assets/decks/**`, `card-assets.generated.json` | `:6-15, 39-49, 131-185, 187-223` |
| `scripts/verify-card-asset-coverage.mjs` | Для 18 `TARGET_HEROES` проверяет наличие EN `<slug>.{webp,png,jpg,jpeg}` и RU `ru/<slug>-ru.*`; печатает JSON-сводку, при пробелах `exit 1` | scraped JSON + `public/assets/decks` | stdout | `:9-30, 74-112` |
| `scripts/localize-deadpool-ru.py` | PIL: открывает EN `deadpool/<name>.webp`, закрашивает прямоугольники и рисует русский текст шрифтами `C:/Windows/Fonts/comic.ttf`, `comicbd.ttf`, `Inkfree.ttf` (fallback `arial.ttf`), сохраняет `ru/<name>-ru.png` для 5 карт: `time-out-time-out-time-out`, `transit-card`, `underrated-super-heroes`, `wanna-bet`, `xavier-institute-faculty` | 5 EN WebP | 5 PNG RGBA 398×556 | `:7-10, 26-28, 105-112, 233-239` |
| `scripts/generate-hud-assets.ps1` | System.Drawing (GDI+): рисует 15 HUD и 6 FX PNG (Format32bppArgb, AntiAlias) — скруглённые панели, пилюля, лоток, слоты, рубашка, виньетка, рамка, чип, бейджи, кнопки, кольцо, подсветки, щит, две спрайт-полосы | нет | `public/assets/ui/hud/*.png`, `ui/effects/*.png` | `:1-17, 284-310` |
| `backend/prisma/seed-scraped.ts`, `update-card-images.ts`, `update-hero-images.ts`, `seed-all-scraped.ts` | Заливают в Postgres URL из scraped (Supabase) для карт, героев, бордов | `scraped-data/api/**` | БД | `seed-scraped.ts:7,308-311,347-348`; `update-card-images.ts:7,166-172,193-198`; `seed-all-scraped.ts:307-308` |
| `docs/figma/figma_exporter.py` | Экспорт `scraped-data/images` → `docs/figma/figma-ready` (по README) | | `figma-ready/**`, `figma-import.csv` | `docs/figma/README.md:52-56` |

Происхождение scraped-data: сайт `https://www.the-unmatched.club`, скрейп 2026-01-26, 88 записей (`scraped-data/index.json:2-4`, `summary.md:3-13`). Список «героев» включает наборы и служебные ключи (`battle-of-legends-volume-one/two/three`, `cobble-fog`, `hells-kitchen`, `for-king-and-country`, `teen-spirit`, `the-witcher-realms-fall`, `the-witcher-steel-silver`, `brains-and-brawn`, `redemption-row`, `slings-and-arrows`, `suns-origin`, `buffy-the-vampire-slayer`, `data`, `melee`, `range`, `refresh`) — `summary.md:17-104`; реальных героев меньше 88 (точное число — **не найдено** в источниках).

### 2.8. HUD- и FX-ассеты (`public/assets/ui/**`)

Все 21 файл — PNG RGBA, сгенерированы `generate-hud-assets.ps1`; размеры совпадают с планом `docs/plans/imagegen-hud-asset-plan-2026-06-11.md:191-293`.

| Файл | Размер, px | Кадры | Ключ Phaser | Используется в `GameScene.ts` | Источник размера |
|---|---|---|---|---|---|
| `hud/player-panel-local.png` | 380×112 | — | `hud-player-panel-local` | нет | `.ps1:287` |
| `hud/player-panel-opponent.png` | 380×96 | — | `hud-player-panel-opponent` | нет | `:288` |
| `hud/turn-phase-pill.png` | 220×54 | — | `hud-turn-phase-pill` | нет | `:289` |
| `hud/selected-card-panel.png` | 260×360 | — | `hud-selected-card-panel` | нет | `:290` |
| `hud/mobile-bottom-sheet.png` | 390×320 | — | `hud-mobile-bottom-sheet` | нет | `:291` |
| `hud/hand-tray.png` | 760×130 | — | `hud-hand-tray` | нет | `:292` |
| `hud/hand-tray-mobile.png` | 390×122 | — | `hud-hand-tray-mobile` | нет | `:293` |
| `hud/deck-slot.png` | 96×132 | — | `hud-deck-slot` | нет | `:294` |
| `hud/discard-slot.png` | 96×132 | — | `hud-discard-slot` | нет | `:295` |
| `hud/hidden-card-back.png` | 120×180 | — | `hud-hidden-card-back` | нет | `:296` |
| `hud/board-vignette.png` | 1024×768 | — | `hud-board-vignette` | **да** (800×600, alpha 0.5) | `:297`; `GameScene.ts:300-304` |
| `hud/board-frame-6x4.png` | 640×430 | — | `hud-board-frame-6x4` | **да** (boardW+44 × boardH+44, alpha 0.9) | `:298`; `GameScene.ts:325-330` |
| `hud/zone-legend-chip.png` | 132×34 | — | `hud-zone-legend-chip` | нет | `:299` |
| `hud/status-badges.png` | 384×64 | 6 × 64×64 (health, movement, attack, defense, boost, card-count) | `hud-status-badges` | нет | `:300`; план `:258-262` |
| `hud/action-buttons.png` | 360×72 | 5 × 72×72 (move, attack, defend, boost, end-turn) | `hud-action-buttons` | нет | `:301`; план `:264-268` |
| `effects/selection-ring.png` | 128×128 | — | `fx-selection-ring` | нет | `:303` |
| `effects/move-highlight.png` | 128×128 | — (цвет 76,210,220) | `fx-move-highlight` | нет | `:304` |
| `effects/attack-highlight.png` | 128×128 | — (цвет 230,92,70) | `fx-attack-highlight` | нет | `:305` |
| `effects/defense-shield.png` | 96×96 | — | `fx-defense-shield` | нет | `:306` |
| `effects/hit-spark-strip.png` | 512×64 | 8 × 64×64 | `fx-hit-spark-strip` | нет | `:307` |
| `effects/card-play-flash-strip.png` | 768×96 | 8 × 96×96 | `fx-card-play-flash-strip` | нет | `:308` |

Все 21 текстура загружаются в `BootScene` через `GAME_IMAGE_ASSETS` (`gameAssetManifest.ts:14-39,126-132`; `BootScene.ts:2`), но grep по `'hud-`/`'fx-` в `src/phaser` даёт только два использования (`GameScene.ts:300,325`). Остальной HUD рисуется примитивами (`drawComicPanel`, `drawHudBar`, `drawCardSlot`, `drawMiniCardBack`) — `GameScene.ts:246-290, 455-500`.

Палитра сгенерированных PNG (ARGB из скрипта): база панелей `18,22,33 → 41,47,62` (градиент), линия «латунь» `209,177,87`, cyan `70,215,220` / `76,210,220`, gold `220,159,68`, red `226,67,83`, purple `151,96,222`, blue `92,142,226`, шелл карт `15,20,34` с рамкой `207,173,84` — `generate-hud-assets.ps1:50-58, 92-93, 117, 134-136, 185-192`.

### 2.9. Phaser-манифест и runtime-загрузка

| Факт | Источник |
|---|---|
| `PhaserImageAsset { key, path }`; наборы `HERO_IMAGE_ASSETS`, `HUD_IMAGE_ASSETS`, `EFFECT_IMAGE_ASSETS`, `BOARD_IMAGE_ASSETS`, `CARD_IMAGE_ASSETS` (захардкожены 11 ms-marvel + 8 daredevil EN) | `gameAssetManifest.ts:1-132` |
| Ключи карт: `card-<heroSlug>-<cardSlug>`; хелперы `getCardArtAsset(heroId, cardId)`, `getBoardArtAsset(boardId)` | `:45-142` |
| Если в манифесте карты нет, но у `definition.imageUrl` есть URL — Phaser грузит текстуру на лету (`this.load.image(key, url)`, ключ `runtime-image-<hash>`), после `filecomplete` перерисовывает руку/борд; так же для `board.imageUrl` | `GameScene.ts:1027-1075` |
| Canvas: 800×600 логических px, `Phaser.Scale.FIT`, `CENTER_BOTH`; на узких экранах CSS-`transform: scale(renderScale)`, `renderScale = min(1, availableWidth/800)` | `src/phaser/PhaserGame.tsx:50-51,119-126,152-156,241-254` |
| BootScene: фон `0x121522`, текст `#f7f0d2` 28 px, прогресс-бар 360×18 (`0x252a3a` / `0xd7b84b`) | `BootScene.ts:25-37` |

### 2.10. Дизайн-токены

#### 2.10.1. Figma-спека (`docs/figma/DESIGN_SYSTEM.md`, `docs/figma/design-system.json`, 2026-01-31)

| Токен | Значение | Источник |
|---|---|---|
| Игровая карта / карточка героя | 300×420 px (1:1,4) | `DESIGN_SYSTEM.md:17-18`; `design-system.json:74-76,83-85` |
| Аватар героя | 150×150; миниатюра 100×100 | `DESIGN_SYSTEM.md:19-20` |
| Зоны карты | md: 15 % / 10 % / 75 % (63/42/315 px); json: top 60 % (252 px) / bottom 40 % (168 px) — **противоречие** | `DESIGN_SYSTEM.md:24-34`; `design-system.json:77-80,178-181` |
| Spacing | xs 4, sm 8, md 16, lg 24, xl 32 | `DESIGN_SYSTEM.md:41-45`; `json:50-56` |
| Primary | yellow `#FFD700`, purple `#6B4C9A`, red `#DC143C`, blue `#1E3A8A` | `DESIGN_SYSTEM.md:55-58`; `json:9-14` |
| Neutral | `#000000`, `#1F1F1F`, `#808080`, `#D3D3D3`, `#FFFFFF` | `md:64-68` |
| Semantic | energy `#FF6B35`, speed `#4ECDC4`, defense `#95E1D3`, magic `#A8DADC` | `md:74-77` |
| Фракции | Marvel `#DC143C`, Historical `#D2B48C`, Mythical `#6B4C9A` (только md), Witcher `#1E3A8A`, Jurassic `#228B22`, TMNT `#00A86B` | `md:85-90`; `json:28-34` |
| Шрифты | md: заголовки Impact/Arial Black 700+, текст Arial/Roboto; json: `Inter, Arial, sans-serif` — **противоречие** | `md:100-103`; `json:38` |
| Размеры текста | xs 10, sm 12, base 14, md 16, lg 18, xl 24, 2xl 32, 3xl 40; веса 300/400/500/700/900; line-height 1.2/1.5/1.75 | `md:109-134`; `json:39-47` |
| Радиусы | 0/4/8/12/16/full | `md:209-214` |
| Границы | thin 1 gray, medium 2 primary, thick 4 accent | `md:220-223` |
| Тени | sm `0 1px 2px rgba(0,0,0,.05)` … xl `0 20px 25px rgba(0,0,0,.2)` | `md:234-237` |
| Иконки | faction 40, value-circle 30, sword/shield/energy 24 | `md:195-199`; `json:93-102` |
| Типы карт (цвет фона) | Action `primary-red`, Defense `accent-defense`, Special `primary-purple`, Passive `neutral-dark-gray` | `md:252-257` |
| Компонент Action Card | topZone 252, factionBadge 40 top-left, valueBadge 30 top-right, bottomZone 168, title 16/700, effect 12/400, factionName 10 | `json:173-185` |
| Компонент Hero Card | topZone 63, centerZone 252, emblem 120 circle, bottomZone 105, heroName 24/700, heroRole 14/400 | `json:187-198` |
| Экспорт | print PDF ×3 300 dpi; digital PNG ×2 144 dpi; web SVG ×1 | `json:201-205` |
| Примеры героев в json | oda-nobunaga, ms-marvel, geralt, sun-wukong, dracula с палитрами (`ms-marvel: #DC143C, #FFD700, #6B4C9A`) | `json:104-171` |

Производные файлы: `docs/figma/figma-generated/design_tokens.json` (те же 18 цветов + textStyles), `figma_schema.json`, SVG/PNG примеры карт (`svg-cards/*.svg`, `cards/*.png`) — `find docs/figma/figma-generated`. `docs/figma/figma-ready/design-system.json` — другая структура (массив `colors[]`), отличается от `docs/figma/design-system.json` (`diff -q`).

#### 2.10.2. Реальные CSS-токены React (`src/design-system/design-tokens.css`)

| Группа | Значения | Строки |
|---|---|---|
| Primary (Attack Red) | `#dc2626` / light `#ef4444` / dark `#b91c1c` | 14-16 |
| Secondary (Defense Blue) | `#2563eb` / `#3b82f6` / `#1d4ed8` | 18-20 |
| Accent (Versatile Purple) | `#a855f7` / `#c084fc` / `#9333ea` | 22-24 |
| Special (Scheme Gold) | `#ca8a04` / `#eab308` / `#a16207` | 26-28 |
| Gray | 50 `#f9fafb` … 900 `#111827` (Tailwind-шкала) | 34-43 |
| Zone colors | blue `#3b82f6`, green `#22c55e`, yellow `#eab308`, red `#ef4444`, purple `#a855f7` | 46-50 |
| Status | success `#22c55e`, warning `#f59e0b`, error `#ef4444`, info `#3b82f6` | 53-56 |
| Градиенты | dark `#1f2937→#111827`; card-attack `#7f1d1d→#450a0a`; defense `#1e3a8a→#1e40af`; versatile `#581c87→#6b21a8`; scheme `#713f12→#78350f` | 59-64 |
| Шрифты | base/heading/display `'Inter', -apple-system, …, Roboto, sans-serif`; mono `'JetBrains Mono','Fira Code','Courier New'` — `@font-face`/Google Fonts **не найдено** в `src`/`index.html` (шрифт не бандлится) | 71-74; grep |
| Размеры текста | xs 12, sm 14, md 16, lg 18, xl 20, 2xl 24, 3xl 30, 4xl 36, 5xl 48 px; веса 300–800; line-height 1.25–2; letter-spacing −0.025em…0.1em | 77-107 |
| Spacing | 0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96 px | 113-125 |
| Радиусы | sm 2, md 6, lg 8, xl 12, 2xl 16, 3xl 24, full 9999 | 131-138 |
| Тени | sm…2xl, inner; цветные `--shadow-attack/defense/versatile/scheme/glow` | 144-156 |
| Transitions | 150/200/300/500 ms ease-in-out; ease-bounce `cubic-bezier(0.68,-0.55,0.265,1.55)` | 162-171 |
| z-index | base 0 … toast 800 | 177-185 |
| **Карта** | `--card-width: 140px; --card-height: 200px; --card-ratio: 1.428`; header 32 px; boost-badge 24 px; цвета типов attack `#ef4444`, defense `#3b82f6`, versatile `#a855f7`, scheme `#eab308` | 192-206 |
| **Борд** | `--grid-cell-size: 80px; --grid-gap: 2px`; fighter token 60 / hero 48 / sidekick 32; zone-indicator 8 px | 213-222 |
| UI | кнопки 32/40/48; input 40, radius 8; badge full; progress 8 px | 229-244 |
| Dark mode | bg `#111827/#1f2937/#374151`, text `#f9fafb/#d1d5db/#9ca3af` | 251-261 |
| CSS-карты | `.card` width `var(--card-width)` min-height `var(--card-height)`; варианты 100×140 и 180×260 | `src/design-system/card-styles.css:12-13, 303-304, 321-322` |
| Глобальный шрифт | `index.css`: `Inter, system-ui, Avenir, Helvetica, Arial, sans-serif` | `src/index.css:4` |

#### 2.10.3. Константы Phaser-HUD (`src/phaser/scenes/GameScene.ts`)

| Константа | Значение | Строки |
|---|---|---|
| `ZONE_COLORS` (12) | blue `0x3286d9`, green `0x48a76a`, yellow `0xd7b84b`, red `0xb23a48`, purple `0x7b5ac8`, brown `0x92400e`, gray `0x6b7280`, orange `0xf97316`, pink `0xec4899`, white `0xe5e7eb`, gold `0xd4af37`, beige `0xd6c8a8` | 53-66 |
| `HUD` | ink `0x040711`, surface `0x08101d`, surfaceRaised `0x111827`, line `0xf2b84b`, lineDim `0x4b5875`, cyan `0x00d4ff`, gold `0xffc84a`, red `0xff3f4f`, purple `0x9c55ff`, text `#fff4c7`, mutedText `#9fb0ca` | 68-80 |
| Акценты героев | ms-marvel `0xd7b84b`, daredevil `0xb23a48`, fallback `0x4ecca3` | 32, 40, 50 |
| Фон камеры | `0x111522` | 144 |
| Геометрия | `SPACE_SIZE 72`, `BOARD_TOP 130`, `BOARD_PADDING 16`, `CARD_WIDTH 58`, `CARD_HEIGHT 84` | 105-109 |
| HP-цвет | ratio > 0.6 `0x4ecca3`; > 0.3 `0xd7b84b`; иначе `0xff4d5f` | 1110-1112 |
| Шрифт | везде `'Arial, sans-serif'`, размеры 8–40 px, обводка `#05070d/#070a12` 3 px | 339-913 |
| Фазовые цвета пилюли | `[cyan, 0x39d98a, gold, red, purple]` | 674 |
| Панели-«комиксы» | `drawComicPanel(container,x,y,w,h,accent,{fill,alpha,cut,lineAlpha,inner})` — скошенные углы `cut` 7–22 px | 246-260, 517-522 |

Зоны в API: enum `BLUE GREEN YELLOW RED PURPLE BROWN GRAY ORANGE PINK WHITE GOLD BEIGE` (`05-engine-and-content.md:471`) — 12 значений, совпадают с `ZONE_COLORS`; CSS-токены покрывают только 5.

### 2.11. Три HUD-концепта (`docs/hud-concepts/*.png`, PNG RGB 1672×941)

Ни один документ в репозитории на эти файлы не ссылается (grep по `noir-tactical|premium-tabletop|arcade-comic|hud-concepts` пуст) — описание ниже по визуальному просмотру. Композиция во всех трёх идентична и соответствует «HUD Composition Target» плана (`docs/plans/imagegen-hud-asset-plan-2026-06-11.md:164-173`).

**Общая раскладка (все три):**
- Верх-лево: панель оппонента (портрет, HP-шкала сегментами, вторая шкала/пипсы ресурсов, иконки статусов).
- Верх-центр: пилюля хода/фазы с 5–8 цветными узлами (cyan слева → red справа), активный узел крупнее.
- Верх-право: рука оппонента — 5–6 рубашек, справа бейдж.
- Центр (~60 % ширины): борд в рамке; сетка 6–7 × 4 круглых клеток, окрашенных цветом зоны (синие/бирюзовые/зелёные/жёлтые вверху, фиолетовые/красные внизу), соединённых линиями; маркеры «»» (фиолетовые, перемещение) и «⚡» (золотые, буст); две фигурки — белая/красная слева вверху с cyan/red кольцом выбора, вторая справа внизу.
- Лево/право по бокам: вертикальные рейлы (иконки действий слева, легенда зон / статусы справа).
- Низ-лево: панель локального игрока (портрет, cyan-шкала HP, вторая шкала, пипсы).
- Низ-центр: лоток руки с 5 картами в рамках (цветовые подложки по типу: cyan/blue, red, gold, purple, green), внизу карт слот значения.
- Низ-право: колода (cyan/blue рамка, счётчик «10») и сброс (red рамка, счётчик «0»/«03»).

| Концепт | Стиль | Отличия |
|---|---|---|
| `hud-noir-tactical.png` | Чёрный фон с туманом, латунные тонкие рамки, неоновые cyan/red акценты, силуэтные портреты (мужчина в шляпе — красный, женщина — cyan), дождливый ночной город на борде; по бокам две вертикальные «витрины» с городскими пейзажами (синий слева, красный справа) и слотом герба под ними | HP — 8 сегментов (heart-иконка), энергия — золотая шкала (lightning), ромбовидные пипсы; карты руки — силуэты на цветной подложке с ромбом-значением |
| `hud-premium-tabletop.png` | Тёмно-синий «войлок/кожа», золотые филиграни, круглые медальоны-портреты, розы ветров на рубашках, пергаментные карты | HP — «капли» (7 шт.) + сплошная шкала, бейдж «5» (действия); левый рейл — 5 шестиугольных иконок (ботинок/щит/солнце/мечи/спираль), правый — вертикальная легенда 5 зон с цветными точками; борд 7×4 из полупрозрачных дисков поверх карты; справа внизу баннер |
| `hud-arcade-comic.png` | Комикс/полутон, толстые неоновые контуры (cyan у локального, red у оппонента, gold у фазы), комикс-портреты (красный герой с посохом, героиня в стиле Ms. Marvel) | HP — 8 шестиугольных пипсов + шкала; 4 квадратные иконки статусов под шкалой; левый рейл 3 кнопки, правый — 4 hex-кнопки; карты руки — яркий комикс-арт с hex-слотом значения; счётчики «10»/«03» в кругах |

Финальный Phaser-HUD (2.12) визуально ближе всего к `arcade-comic` (скошенные углы, cyan/gold/red неон, тёмный ink-фон) — интерпретация по скриншоту.

### 2.12. Финальный HUD

#### Desktop — `hud-game-desktop-final.png` (PNG RGB 1425×930, viewport 1440×900)

Это страница `TestGamePage` (`src/pages/test-game/TestGamePage.tsx`): заголовок «Test Game» + кнопка «HIDE PHASER»; три колонки.

**Колонка 1 — Phaser-канвас 800×600** (координаты — из `GameScene.ts`):
- Панель оппонента: `x=14, y=12, 292×76`, fill `0x170b10`, акцент red; слева cover 46 px, аватар 50 px в круге, mini 28 px; имя 14 px bold, HP-бар 150×12 на `y+42`, строка статов 11 px (`HP 14/14  Hand 5  Deck 25  Action`), 4 ромбовидных пипса действий (`x+204+i*13`) — `:588-664`.
- Пилюля хода: `308,20, 184×44`, gold; 5 кругов фаз (`340+i*30, 42`), текст «Turn N» 15 px + фаза 11 px (`action selection`) — `:666-700`.
- Рука оппонента: `528,14, 242×76`, до 7 мини-рубашек 40 px шагом 28 (`560+i*28, 52`), подпись «Hand N» — `:702-735`.
- Борд: подпись «Cobble City», сетка 6×4 × 72 px, начало `y=130`, центр по X; клетки — круги цвета зоны (`ZONE_COLORS`) с белой обводкой 2 px alpha 0.52; фишки 62/48 px с HP-баром; арт борда alpha 0.72; рамка `board-frame-6x4` — `:297-330, 355-386, 405-430`.
- Панель локального игрока: `14,424, 292×62`, fill `0x071624`, акцент cyan («Achilles», HP 18/18) — `:591-596`.
- Лоток руки: `40,488, 720×96`, cyan; 7 слотов 48×72 (`196+i*68, 536`), карты 58×84 по центру `y=532` шагом 68, выбранная — масштаб 1.08 и gold-обводка 3 px; арт `setDisplaySize(54,80)`; справа мини-рубашки колоды (`696,536`, cyan) и сброса (`750,536`, red) с счётчиками на `y=579` — `:455-500, 503-560`.
- Инспектор выбранной карты (только при выборе): `565,132, 224×322`, purple; арт 122×176 в `(680,264)`; мета 13 px — `:740-790`.

**Колонка 2 — React-панель текущего игрока** («Achilles», бейдж «Текущий ход»): блоки «Герой» (аватар-иконка, зелёный HP-бар 18/18, «Позиция: (0, 2)»), «Помощник» (5/5), «Рука (5)», «Колода: 25», «Сброс: 0», сетка CSS-карт 140×200 с артом (ACHILLES' HEEL, SPEAR THROW, UNDER ACHILLES' HELM, BROTHERS IN ARMS — арт грузится по `imageUrl` из API), «Очки действий: 2»; ниже «VS» и панель «Little Red».

**Колонка 3 — управление**: «УПРАВЛЕНИЕ ИГРОЙ» (красная «НОВАЯ ИГРА (РАНДОМ)», «КОНЕЦ ХОДА»), «СОСТОЯНИЕ ИГРЫ» (ХОД: 1; ФАЗА: Выбор действия; ТЕКУЩИЙ ИГРОК: Achilles), «Debug (JSON)».

Наблюдения по скриншоту: (1) все 5 фишек — одинаковый силуэт (fallback ms-marvel, см. 2.4); (2) арт карт Achilles в Phaser отрисован — значит runtime-загрузка по абсолютному URL работает (`GameScene.ts:1027-1075`); (3) Cover/avatar в панелях — тоже fallback ms-marvel для Achilles/Little Red.

#### Mobile — `hud-game-mobile-fixed.png` (PNG RGB 375×1642, viewport 390×844)

Тот же 800×600 канвас, уменьшенный CSS-масштабом (~0,42) в верхней части (панели «Michelangelo» / «Ant Queen», пустые слоты руки), под ним вертикально: React-панель текущего игрока («Ant Queen», Герой 10/10, «Рука (0)» — «Нет карт», «Очки действий: 2»), «VS», панель «Michelangelo» (14/14, Позиция (5, 2)), блок управления и состояния. Отдельной мобильной раскладки HUD в Phaser **нет** (нет `isMobile`/compact-веток в `GameScene.ts` — grep пуст); мобильные ассеты `hand-tray-mobile.png`, `mobile-bottom-sheet.png` не используются. План описывал bottom-sheet-инспектор и сворачиваемую руку (`imagegen-hud-asset-plan:176-185, 450-453`) — не реализовано.

### 2.13. Требования к конвертации для UE (факты + инженерные выводы)

Факты о входных данных (из замеров):
- 276 WebP: 227 EN-карт, 42 RU-карт, 6 hero-медиа, 1 борд. 96 EN WebP — RGBA (в основном daredevil/deadpool/ms-marvel/eredin/philippa/yennefer-triss + отдельные карты blackbeard/chupacabra/loki/pandora), 131 — RGB.
- 112 PNG: 91 RU-скана (RGB, ~1060×1484, ~2,5 МБ), 5 RU-синтетики (RGBA 398×556), 21 UI (RGBA).
- Ни один размер не является степенью двойки; спрайт-полосы — 512×64, 768×96, 384×64, 360×72; кадры 64×64, 96×96, 72×72.
- Пропорция карт 0,712–0,717; аватары 402×402 (квадрат) кроме ms-marvel 750×705; mini 558×764 (0,730); cover 375×523 (0,717); борд 1337×866 (1,544).
- Supabase-источники включают `.avif` (2 борда: santas-workshop, venice; 1 card-cover в scraped) и `.gif` (2 card-cover) — замер PIL; `maps.json`.

Инженерные выводы (движковые факты не из репозитория — помечены «UE-знание, проверить в 5.8»):
1. **WebP → PNG/TGA**: штатный импорт текстур UE и `IImageWrapper` (runtime) поддерживают PNG/JPEG/BMP/TGA/EXR/HDR/TIFF/DDS, но не WebP и не AVIF (UE-знание, проверить в 5.8). Следовательно, либо офлайн-пайплайн конвертации всех 276 WebP в PNG (lossless из декодированного WebP; RGBA сохранить), либо WebP-декодер (libwebp) в клиенте для runtime-загрузки Supabase-URL.
2. **Power-of-two**: для UMG/Slate NPOT-текстуры допустимы при `MipGenSettings = NoMipmaps`, `TextureGroup = UI`, `NeverStream` (UE-знание). Для 3D-стола с мип-стримингом — паддинг/ресайз: карты → 512×716 внутри 512×1024 (или 1024×1432 внутри 1024×2048), аватары → 512×512, mini → 512×704 внутри 512×1024, борд → 2048×1326 внутри 2048×2048.
3. **Нормализация**: привести все карты к одному разрешению (предложение: 512×716 для руки/HUD, 1024×1432 для инспектора), RU-сканы даунскейлить с 1060×1484 (экономия ~200 МБ исходников; в BC7 1024×1432 ≈ 1,5 МБ/карта против 6 МБ RGBA8).
4. **Атласы**: 15 HUD + 6 FX PNG (103 КБ) — кандидаты в один Paper2D/Slate-атлас 1024×1024; полосы `hit-spark-strip` (8×64×64), `card-play-flash-strip` (8×96×96), `status-badges` (6×64×64), `action-buttons` (5×72×72) — в PaperFlipbook или материал с UV-смещением. Однако, т. к. финальный HUD их не использует (2.8), для UE достаточно воспроизвести стиль процедурно (UMG Border/9-slice + материалы).
5. **sRGB/alpha**: карты и портреты — sRGB, alpha только у RGBA-вариантов (скруглённые углы/прозрачный фон mini); UI-PNG — straight alpha.
6. **Именование в UE**: `T_Card_<heroSlug>_<cardSlug>_EN|RU`, `T_Hero_<heroSlug>_Avatar|Mini|Cover`, `T_Board_<boardSlug>`; ключи `<heroSlug>:<cardSlug>` из `gameAssetManifest.ts:46-121` можно переиспользовать как ключи DataTable.

---

## 3. Следствия для UE-клиента

1. **Два режима получения арта**: (а) офлайн-пакетирование `public/assets/**` (после конвертации WebP→PNG) в контент проекта с DataTable «slug → Texture2D»; (б) runtime-загрузка по `Card.imageUrl/imageUrlRu`, `Hero.urls.{avatar,mini,cardCover}`, `Board.imageUrl` из GraphQL (могут быть как `/assets/...`, так и абсолютные Supabase-URL — `seed-scraped.ts:347-348` vs `daredevil.ts:84-85`). Клиенту нужны: настраиваемый base-URL фронтенда/CDN для корневых путей, HTTP-загрузчик с дисковым кэшем и декодер PNG/JPEG (+ WebP/AVIF через плагин или серверную конвертацию).
2. **Локаль изображений**: текущая логика `imageUrl || imageUrlRu` (`Card.tsx:48`) — EN-первым. Для русского UI в UE нужна инверсия (RU → EN fallback), при этом RU покрытие 133/227: fallback на EN обязателен; UI не должен дублировать заголовок/значение поверх полного арта карты (`imagegen-hud-asset-plan:56, 443, 463`).
3. **Slug-совместимость**: реализовать в UE (или на пайплайне) точную копию `slugify` (`sync-card-assets.mjs:23-31`) — NFKD, удаление комбинируемых диакритик и апострофов `'`/`’`, lowercase, `[^a-z0-9]+→-`, trim `-`. Hero-slug — имя каталога/JSON; в GraphQL «slug» героя = имя (`content-db.service.ts:187`), а в игровом состоянии есть `heroSlug` (`gameStateAdapter.ts:45`) — ключ для визуалов.
4. **Медиа героев**: локально только 2 героя; для остальных 68–75 брать `Hero.urls.*` (Supabase) или расширить `sync-card-assets.mjs` на heroes (`scraped-data/api/normalized/<slug>.json → urls`) и опубликовать под `/assets/heroes/<slug>/`. Аватары не всегда квадратные (750×705) — UE-виджет портрета должен делать cover-crop; mini 558×764 не сжимать в квадрат, как делает Phaser (`GameScene.ts:424`), а вписывать по высоте.
5. **Борды**: локально один; 29 карт в `maps.json` с Supabase-URL, 2 — AVIF. Для UE: пайплайн конвертации + DataTable `boardSlug → texture`; арт рисовать под сеткой с прозрачностью (Phaser alpha 0.72) либо без затемнения на 3D-столе. Учесть, что id `cobble-city` ↔ арт `hells-kitchen` (`gameAssetManifest.ts:42`).
6. **Токены для UMG** (рекомендуемый базовый набор): фон `#040711`/`#08101d`/`#111827`; линия-латунь `#f2b84b`; акценты cyan `#00d4ff` (локальный), red `#ff3f4f` (оппонент), gold `#ffc84a` (фаза/выбор), purple `#9c55ff` (инспектор); текст `#fff4c7`, muted `#9fb0ca`; 12 цветов зон `ZONE_COLORS`; HP-цвета `#4ecca3/#d7b84b/#ff4d5f`; типы карт attack `#ef4444`, defense `#3b82f6`, versatile `#a855f7`, scheme `#eab308` (`design-tokens.css:197-200`). Радиусы/скосы 7–22 px, обводка 1–3 px.
7. **Шрифт**: React — Inter (не бандлится), Phaser — Arial, Figma-спека — Impact/Arial Black. Для UE нужен собственный Font Asset (Inter OFL как основной; для кириллицы RU-карт localize-скрипт использовал Comic Sans/Ink Free — не переносить). Размеры HUD-текста в Phaser 8–18 px при 800×600 → масштабировать ×2,4 для 1920×1080.
8. **Раскладка**: воспроизвести zoning финального HUD (2.12) в UMG Canvas с якорями: оппонент TL, фаза TC, рука оппонента TR, борд по центру (cell 72/800 = 9 % ширины), локальный игрок BL, рука BC (7 слотов), колода/сброс BR, инспектор — правая панель (desktop) или bottom-sheet (mobile, по плану `:176-185`). Сгенерированные PNG-панели можно не переносить — они не задействованы.
9. **Спрайт-эффекты**: если нужны — `hit-spark-strip` 8×64², `card-play-flash-strip` 8×96² как Flipbook/атлас; кольцо выбора, подсветки move/attack, щит — можно заменить материалами (цвета из `.ps1:304-305`: move `76,210,220`, attack `230,92,70`).
10. **Бюджет**: при упаковке всех 388 файлов после конвертации/нормализации до 512×716 объём EN+RU карт ≈ 360 × ~0,5 МБ BC7 ≈ 180 МБ в cooked (оценка); исходные RU-PNG (207 МБ) в проект не тащить без даунскейла.
11. **Версионирование**: ассеты не в git и манифест устарел — UE-пайплайн должен считать источником правды либо API (`contentVersion`/`contentSummary`, `05-engine-and-content.md:637-644`), либо собственный экспорт из `public/assets` с пересборкой манифеста (`node scripts/sync-card-assets.mjs <slugs…>` + `verify`).

---

## 4. Открытые вопросы / несоответствия

1. **RU-паттерн**: документация B.4 — `ru/<cardSlug>-ru.png` (`05-engine-and-content.md:489,506`), скрипт — `-ru.webp` (`sync-card-assets.mjs:139`), на диске — 42 webp + 91 png. Какой формат канонический для новых RU?
2. **Манифест устарел** (`card-assets.generated.json` от 2026-06-14T11:32Z, ru=61) против диска (ru=133). Нужен перезапуск `sync-card-assets.mjs` для всех 18 героев; но скрипт перезапишет EN из scraped — совпадут ли размеры (например, откуда взялись 1005×1403 у ciri, если в scraped 63 таких файла)?
3. **Происхождение 91 RU-PNG-сканов** и прав на них — не задокументировано; 5 deadpool-RU — синтетика PIL с Comic Sans (`localize-deadpool-ru.py`).
4. **Источник URL в БД**: B.4 утверждает, что `Card.imageUrl` = `/assets/...` и «проставлены сидами `update-*-images.ts`» (`:511`), но `update-card-images.ts:170` и `seed-scraped.ts:347` пишут Supabase-URL. Фактическое содержимое БД проверить не удалось (MCP postgresql не подключился). UE-клиент должен поддерживать оба варианта.
5. **Hero «slug»**: `getHeroBySlug` ищет по `id` (cuid) или `name` — файловый slug `ms-marvel` ≠ API-slug `Ms. Marvel`. Есть ли в GraphQL поле с файловым slug героя (кроме `heroSlug` в состоянии игры)? — в прочитанных источниках не найдено.
6. **Борд `cobble-city`** использует арт Hell's Kitchen; в `maps.json` ключа `cobble-city` нет (есть set `cobble-fog` в scraped). Какой борд считать «первым» для UE?
7. **Figma-спека vs реальность**: карта 300×420 / аватар 150 / mini 100 (`DESIGN_SYSTEM.md:17-20`, `figma-ready/README.md:14-16`) против фактических 398×556 / 402×402 / 558×764; зоны карты 15/10/75 % vs 60/40 %; шрифты Impact vs Inter; палитра Figma (#FFD700…) нигде в коде HUD не используется (Phaser/CSS используют другие значения). Какой слой токенов утверждён?
8. **«88 героев»** в спеке и `summary.md` включают наборы и служебные записи (`data`, `melee`, `range`, `refresh`, `cobble-fog`, …) — реальное число героев не найдено.
9. **HUD-PNG не используются**: 19 из 21 сгенерированных ассетов загружаются, но не рисуются; план (`imagegen-hud-asset-plan`) предполагал их как фон панелей. Оставлять ли их в UE-пайплайне?
10. **Мобильная раскладка** в Phaser отсутствует (только CSS-масштаб) — план bottom-sheet не реализован; для UE mobile нужна отдельная спецификация.
11. **Аватар ms-marvel 750×705**, cover-форматы в scraped (JPEG/GIF/AVIF) — нужна политика нормализации.
12. **AssetLoader.ts / phaser/README.md** описывают несуществующие спрайтшиты бойцов (64×64, idle/walk/attack/hit/defeat) — анимированных фигурок нет; 6 `.glb`-моделей миниатюр в `scraped-data/images/heroes/models/` (без привязки к slug в имени) — использовать ли их в UE как 3D-фишки?
13. **Ассеты вне git**: нет ни коммита, ни LFS, ни `.gitignore`-правила; при переносе в UE — где хранить (Git LFS / Perforce / CDN)?
14. **Design tokens дублируются** в `docs/figma/design-system.json`, `figma-ready/design-system.json`, `figma-generated/design_tokens.json`, `figma_schema.json`, `UnmatchedDesignSystem.ts` — файлы различаются структурой; единый источник не определён.

---

## 5. Источники

- `public/assets/**` — 388 файлов, замер PIL/`file`/`du` (2026-09-02).
- `public/assets/decks/card-assets.generated.json` (2026-06-14T11:32:33Z).
- `public/assets/phaser/README.md`.
- `scripts/sync-card-assets.mjs`, `scripts/verify-card-asset-coverage.mjs` (запущен, read-only), `scripts/localize-deadpool-ru.py`, `scripts/generate-hud-assets.ps1`.
- `src/phaser/assets/gameAssetManifest.ts`, `src/phaser/assets/AssetLoader.ts`, `src/phaser/index.ts`, `src/phaser/scenes/BootScene.ts`, `src/phaser/scenes/GameScene.ts`, `src/phaser/PhaserGame.tsx`.
- `src/design-system/design-tokens.css`, `src/design-system/card-styles.css`, `src/index.css`, `src/components/cards/Card.tsx`, `src/lib/gameStateAdapter.ts`, `src/store/testGameStore.ts`, `src/core/data/boards/cobble-city.ts`, `src/core/data/heroes/*.ts`, `src/graphql/queries/*.graphql`, `vite.config.ts`.
- `docs/figma/DESIGN_SYSTEM.md`, `docs/figma/design-system.json`, `docs/figma/README.md`, `docs/figma/figma-ready/README.md`, `docs/figma/figma-ready/figma-import.csv`, `docs/figma/figma-generated/design_tokens.json`.
- `docs/hud-concepts/hud-noir-tactical.png`, `hud-premium-tabletop.png`, `hud-arcade-comic.png`; `hud-game-desktop-final.png`; `hud-game-mobile-fixed.png` (просмотр).
- `docs/plans/imagegen-hud-asset-plan-2026-06-11.md`.
- `docs/backend-api/05-engine-and-content.md` (разделы B.3–B.5, приложение).
- `backend/src/content/dto/content.dto.ts`, `backend/src/content/content-db.service.ts`, `backend/src/content/interfaces/hero-definition.interface.ts`, `backend/src/content/data/heroes/{daredevil,ms-marvel}.ts`, `backend/prisma/{seed-scraped,seed-all-scraped,update-card-images,update-hero-images}.ts`, `backend/src/admin/dto/admin.dto.ts`, `admin/src/pages/heroes/create.tsx`.
- `scraped-data/index.json`, `scraped-data/summary.md`, `scraped-data/api/maps.json`, `scraped-data/api/normalized/daredevil.json`, `scraped-data/images/**` (замер PIL).
- Supabase-хранилище: `https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/…` (URL из scraped-данных; доступность не проверялась).
