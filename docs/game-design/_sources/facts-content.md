# Приложение: инвентаризация контента и ассетов (по файлам репозитория)

Статус: исследование 2026-09-18, только файлы репозитория (БД не открывалась). Пометки: «ФАКТ файла» = файл существует в репо; всё остальное — требует проверки.

## Герои в коде контента

- `backend/src/content/data/heroes/` — только **ms-marvel.ts** и **daredevil.ts** (+ index с HERO_REGISTRY из 2 записей). `src/core/data/heroes/` — то же самое (core-версия чуть старее, без блока urls).
- medusa/king-arthur/muhammad-ali/alice/tomoe-gozen/oda-nobunaga/achilles как .ts-файлов НЕТ.
- Обработчики способностей `backend/src/game-engine/abilities/heroes/`: **arthur.handler.ts** (king-arthur, "Holy Avenger", allowsAttackBoost), daredevil.handler.ts, ms-marvel.handler.ts + generic-hero-ability.handler.ts. Обработчика Medusa НЕТ → её уникальные механики идут через generic-обработчик, работоспособность не подтверждена.
- `scraped-data/api/heroes/` — 88 JSON (все перечисленные герои есть); `backend/prisma/seed-scraped.ts` (строки 366-384) — список ~79 ключей для импорта в БД. Сколько реально в БД сейчас — по файлам не определить (сид идемпотентен). Бриф 18.09 проверил через API/админку: 84 героя, 880 записей карт, 30 досок.

## Доски

- `src/core/data/boards/cobble-city.ts` — единственная доска в коде: id 'cobble-city', width 6, height 4 (регулярная сетка 6×4 = 24 ячейки, rows 0-3, cols 0-5), ячейка = {position:{x,y}, zones:Zone[]}; зоны blue/green/yellow (ряды 0-1), purple/red (ряды 2-3); часть ячеек с 2 зонами (напр. (1,1): blue+green; (1,2): purple+red); связей/adjacency нет; imageUrl='/assets/boards/hells-kitchen.webp' (временная подмена арта).
- ПРОТИВОРЕЧИЕ: бриф 18.09 проверил через API доску Cobble City «5×6, 30 элементов cells». Код ≠ БД. Истина для клиента — `boardState` живой партии; до её проверки геометрию фиксировать нельзя.

## Ассеты public/assets (ФАКТ файлов)

| Папка | Файлов | Что | Размер |
|---|---|---|---|
| heroes/ | 6 | .webp: daredevil/, ms-marvel/ (avatar, mini, card-cover) | 460K |
| boards/ | 1 | hells-kitchen.webp | 128K |
| decks/ | 361 | 269 .webp + 91 .png + card-assets.generated.json; 18 героев: blackbeard, pandora, chupacabra, michelangelo, loki, donatello, ciri, deadpool, eredin, muhammad-ali, shredder, ms-marvel, krang, raphael, daredevil, leonardo, philippa, yennefer-triss; у 13 подпапка ru/ | 219M |
| ui/ | 21 | .png (6 effects/ + 15 hud/) | 156K |
| phaser/ | 1 | README-заглушка | 8K |

- **medusa и king-arthur в decks/ ОТСУТСТВУЮТ** — их арты карт не синхронизированы из скрапа. Задача: `node scripts/sync-card-assets.mjs medusa king-arthur` (исходники карт лежат в scraped-data/images/decks + docs/figma/figma-ready/decks).
- RU-локализация decks неполна: у philippa, raphael, shredder, yennefer-triss папки ru/ пустые; в манифесте есть missing-записи.

## 3D-модели

- В репо 6 .glb (4.8M суммарно) в `scraped-data/images/heroes/models/`: medusa (3eR7yPmdggV...), king-arthur (xfdrwhmlwG...), alice, bigfoot, robin-hood, sinbad. Имена = хэши из miniModelUrl.
- .gltf/.fbx/.obj/.usdz нет. Качество сетки/масштаб/ориентация .glb НЕ проверялись (не открывались).
- miniModelUrl/characterCardUrl ведут на Supabase (`yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/...`), локальных путей нет; заполняются сидом из скрапа (seed-scraped.ts:310-311).
- В публичном GraphQL API miniModelUrl НЕ экспортируется (только админский AdminHero) — см. facts-backend.md.

## Medusa и King Arthur (из scraped JSON)

| Параметр | Medusa | King Arthur |
|---|---|---|
| Набор | Battle of Legends, Vol. One | Battle of Legends, Vol. One |
| HP | 16 | 18 |
| Движение | 3 | 2 |
| Тип атаки | range | melee |
| Sidekicks | 3 × Harpies (HP 1, move 3) | 1 × Merlin (HP 7, move 2) |
| Карт (уникальных / копий) | 11 / 30 | 16 / 30 |
| miniModelUrl | Supabase .glb (локальная копия есть) | Supabase .glb (локальная копия есть) |

- Копии карт: scraped `copies` → `Card.count` (seed-scraped.ts:345). Примеры: Medusa — Second Shot x3, A Momentary Glance x2, Winged Frenzy x2, Gaze of Stone x3; Arthur — Excalibur x1, The Holy Grail x1, Momentous Shift x3, Feint x3, Noble Sacrifice x3, Skirmish x3.
- Способности: у Arthur есть специализированный обработчик ("Holy Avenger"); у Medusa специализированного обработчика НЕТ (generic).

## scripts/sync-card-assets.mjs (223 строки)

1. Читает `scraped-data/api/heroes/<slug>.json`, строит список карт (id = slug заголовка, image/imageRu).
2. Ищет картинки в `scraped-data/images/decks/` и `docs/figma/figma-ready/decks/`.
3. Копирует в `public/assets/decks/<hero>/<card>.webp` (EN) и `.../ru/<card>-ru.webp` (RU).
4. Пишет манифест `public/assets/decks/card-assets.generated.json` + отчёт missing.
По умолчанию обрабатывает daredevil/ms-marvel/deadpool; slug'и передаются аргументами CLI.

## Что требует проверки (за пределами файлов)

- Доступность/кэшируемость Supabase-бакета; 82 из 88 героев вообще без .glb.
- **Лицензии скрап-контента (Unmatched, Marvel, Witcher и т.п.) не подтверждены ничем в репо** — только внутренний прототип.
- Пригодность 6 .glb (формат/масштаб/ориентация) не проверялись.
- Соответствие БД ↔ файлам сида; реальное количество героев/карт в БД.
- Геометрия Cobble City в БД (см. противоречие выше).
