# R5. Сырые заметки: библиотеки Fab и других источников для подбора хода

Исследователь R5, 2026-10-03. Документ рабочий: здесь метод, сырые данные и то, что не удалось проверить. Итоговый документ для читателя — [07-asset-libraries-fab.md](../07-asset-libraries-fab.md).

## 1. Что прочитано в репозитории до поиска

| Источник | Что взято |
|---|---|
| `docs/research/2026-09-27-ue-assets-catalog.md` | 53 находки 27.09; раздел 2 «Сетка, ходы и камера» (стр. 150–229) уже отклонил ATBTT, Grid Manager, RTS-камеры; раздел 4.1 — Game Animation Sample как «референс, не зависимость» |
| `docs/research/2026-09-27-ue-assets-shortlist.md:109` | ATBTT — «не брать»: своя сетка, путь, AI, 5.8 не подтверждена (на 27.09) |
| `docs/research/2026-09-27-ue-assets-shortlist.md:113` | Game Animation Sample — локомоция и Motion Matching не нужны, перемещение = скольжение |
| `docs/research/2026-09-27-ue-assets-review.md` | 23 замечания ревью; Fab EULA: Personal и Professional с одинаковыми правами |
| `docs/game-design/18-third-party-tools-and-assets-decisions.md:17` | KayKit Character Animations — пилот ретаргета рядом с ART-004 |
| `docs/game-design/18-third-party-tools-and-assets-decisions.md:21` | Tabletop SFX (JDSherbert) — «Позже», к звуку CUE |
| `docs/game-design/18-third-party-tools-and-assets-decisions.md:23` | реестр THIRD_PARTY_NOTICES и атрибуции с первого импорта |
| `docs/game-design/00-vision-and-scope.md:105` | D-11: лёгкий риг (idle, выпад, вздрагивание, оседание), перемещение плавным скольжением |
| `docs/game-design/07-animation-vfx-audio.csv:4` | CUE-003: подтверждение клетки — сжатие кольца/заливки, материал `M_HighlightGameLayer` |
| `docs/game-design/07-animation-vfx-audio.csv:8` | CUE-007: перемещение — скольжение актора по клеткам, «НЕ скелетная анимация», след на промежуточных клетках, пыль на конечной, тик шага на клетку |
| `docs/art-pipeline/rig/RIG-CONTRACT.md:86-89` | root motion: по умолчанию in place; перемещение по клетке — скольжение актора (CUE-007), не клип |
| `docs/art-pipeline/rig/RIG-CONTRACT.md:135` | UM17 v2 не совместим напрямую с UE5 Mannequin и Mixamo, только ретаргет |
| `docs/art-pipeline/rig/rig-contract.json:265` | `retarget_maps`: есть `tripo_ue5_mannequin_to_um17`, `mixamo_to_um17`, `smpl_to_um17`; карт для KayKit и Quaternius нет |
| `docs/art-pipeline/rig/RIG-CONTRACT.md:113` | клипы 24 FPS, допуск длительности ±0,05 с |
| `docs/art-pipeline/CREDITS-fab.md:3-4` | решение пользователя 2026-10-01: проект только для личного и локального использования, без публикации |
| `docs/art-pipeline/CREDITS-fab.md:13,21` | два уже взятых NoAI-пака (Megaplants, StyleHex) держатся вне кадров для ИИ |
| `docs/art-pipeline/fab-free-assets-research-2026-10-01.md:26` | почему NoAI важен: кадры уходят агентам на ревью и в imagegen |
| `tools/art/env_kit/ue_import_fab_fx.py:57-59` | `AI_ALLOWED_PACKS` / `NOAI_PACKS`: валидатор отказывает FX из NoAI-паков |
| `tools/art/env_kit/ue_import_fab_fx.py:7-11` | у FX из Fab выключаются Light и Component renderers, всё CPU + determinism |
| `unreal/Unmatched/Unmatched.uproject:1` | включены только PythonScriptPlugin, EditorScriptingUtilities, ModelContextProtocol, AllToolsets |
| `unreal/Unmatched/Source/Unmatched/Unmatched.Build.cs:28` | модуль уже зависит от Niagara |
| `unreal/Unmatched/Source/Unmatched/S08/S08BoardActor.h:252-253` | `SetSelectedFighter(FighterId, Reachable)` — кольцо выбора и подсветка достижимых клеток уже есть (TASK-022) |
| `unreal/Unmatched/Source/Unmatched/S08/S08BoardActor.cpp:1750-1800` | подсветка: на каждую достижимую клетку спавнится отдельный `AActor` с мешем и MID материала игрового слоя; на графовых картах — только `IsBoardSpace` |
| `docs/game-design/09-vertical-slice-and-backlog.md:343-354` | TASK-027: BFS-подсказка = логика сервера, прототипы `M_HighlightGameLayer` |
| C:/tmp/envmaps-research/fab/fab-free-harvest-2026-10-01.json | 1317 бесплатных листингов 01.10 (окружение); по теме хода нашлось мало: шахматы, Catan, «Board Game Essentials», UI Effect Lab/Function Library (NoAI) |

## 2. Метод поиска Fab (2026-10-03)

- `WebFetch` на fab.com и на unrealengine.com/tech-blog — 403 (Cloudflare). `curl` с браузерным UA: первый ответ 200, дальше challenge-страница.
- **Поиск**: публичный JSON `https://www.fab.com/i/listings/search?q=<запрос>` через `mcp__web-reader__webReader` (прокси без входа). В выдаче 24 листинга на запрос; у каждого есть `assetFormats[].technicalSpecs.unrealEngineEngineVersions` (список версий UE), `unrealEngineDistributionMethod` (`code_plugin` / `asset_pack` / `complete_project`), `licenses[].priceTier` (`..._USD_<цена в центах>_...`), рейтинг. Флага NoAI в выдаче поиска нет.
- **Карточки**: `https://www.fab.com/i/listings/<uid>` — отдельная вкладка Chrome (своя, закрыта после работы), `fetch` из страницы листинга, только GET, без входа. Отсюда `isAiForbidden` (NoAI), `isAiGenerated`, цены Personal/Professional, описание. 65 карточек, все ответили 200.
- Ничего не покупалось, не добавлялось в библиотеку, вход не выполнялся.
- Цены: в USD без налогов, взяты из `priceTierId` («Personal / Professional»), скидки не учитывались. Валюта страницы (INR) игнорировалась.
- Версии UE: из списка `unrealEngineEngineVersions` поиска. Список может быть с дырами; «до 5.8» значит, что 5.8 в списке есть.

Запросы (31): turn based grid; board game; tabletop; hex grid; grid movement pathfinding; card game template; chess; tactics template; locomotion animation pack; jump animation; stylized animation pack; fantasy animation pack; Game Animation Sample; Lyra Starter Game; Paragon; selection ring; path arrow; grid highlight; niagara highlight; decal pack; radial menu; UI Material Lab; outline post process; movement path spline indicator; cursor pack; miniature diorama; fantasy map board; common ui; city sample animation; hop animation cartoon; hexagon tile kit; magic circle vfx; turn in place animation; board game template; synty animation; tactical rpg grid; cartoon locomotion; CCG toolkit; stylized selection vfx. Собрано 802 уникальных листинга. Запросы «target indicator» и «Cropout Sample» прокси не отдал (ошибка 500); Cropout найден запросом «city sample animation».

## 3. Главная находка: почти все сэмплы Epic и большинство UI/FX-паков помечены NoAI

`isAiForbidden=true` у **всех** проверенных листингов Epic: Game Animation Sample, Lyra Starter Game, City Sample, Cropout, Slay Animation Sample, Paragon: Serath (выборочно из серии Paragon), Control Rig Samples Pack, UI Material Lab, Niagara Examples Pack. По Epic Content License Agreement контент с тегом NoAI нельзя использовать «as inputs to Generative AI Programs» ([unrealengine.com/eula/content](https://www.unrealengine.com/eula/content), найдено поиском 2026-10-03; полный текст не открывался — JS-рендер, «не проверено» дословно).

Следствие для проекта: агенты получают кадры на ревью (K1–K3, SHOT) и читают ассеты через MCP. NoAI-контент можно держать только в отдельном варианте только для пользователя, как Megaplants (`CREDITS-fab.md:13`). Для подбора хода это значит, что GASP-клипы, Lyra UI и материалы UI Material Lab нельзя ставить в кадры, проходящие через агентов. Читать их Blueprint/C++ через агента — тоже вход в генеративную программу; трактовка для кода «не проверено», принимаем строгую.

Лицензия UE-Only: у Game Animation Sample на листинге указано «UE-Only Content - Licensed for Use Only with Unreal Engine-based Products» (по выдаче поиска [gamedev.net/news/5051](https://gamedev.net/news/5051-download-the-latest-game-animation-sample-projectnow-updated-for-ue-58/), 2026-10-03). Для нас это не ограничение: клиент на UE 5.8. У остальных Epic-листингов статус UE-Only «не проверено».

## 4. Сырые карточки (Fab, 2026-10-03)

Колонки: uid (8 знаков) · название · продавец · тип распространения · UE (из списка версий) · цена Personal / Professional · NoAI · AI-сген. · рейтинг (оценок) · обновлено.

### 4.1 Анимации

| uid | Название | Продавец | Тип | UE | Цена P / Pro | NoAI | AI-сген. | Рейтинг | Обновлено |
|---|---|---|---|---|---|---|---|---|---|
| 880e319a | Game Animation Sample | Epic Games | complete_project | 5.4–5.8 | free | **да** | нет | 4.75 (355) | 2026-08-17 |
| 259f8545 | Game Animation Sample Animations Retargeted to ue5 mannequin | Kingboars | animation (формат не указан) | — | free | **да** | нет | 4.5 (28) | 2026-08-16 |
| ef920974 | Slay Animation Sample | Epic Games | complete_project | 4.27–5.8 | free | **да** | нет | 4.0 (23) | 2026-06-17 |
| 522b6160 | Paragon: Serath (пример серии) | Epic Games | asset_pack | 4.19–5.8 | free | **да** | нет | 4.2 (5) | 2026-06-23 |
| 2ce3fe44 | Control Rig Samples Pack | Epic Games | asset_pack | 5.1–5.7 | free | **да** | нет | 4.17 (18) | 2025-12-11 |
| 3ffd8680 | Jump Animations Pack (14 прыжков) | Jane Gintsar | asset_pack | 5.5–5.8 | $4.99 / $9.99 | **да** | нет | нет оценок | 2026-06-18 |
| 8f27bbc1 | Hopping Animation Pack (5 mocap-подскоков) | Ailive | формат не указан | — | $3.99 / $7.99 | **да** | нет | нет оценок | 2026-06-05 |
| ba95e214 | Cool Turn Animations (33 root motion, UE4/UE5 Manny) | Bacengdu | asset_pack | 5.1–5.8 | $10.99 / $27.99 | нет | нет | нет оценок | 2026-09-04 |
| ccea2285 | Simple Turn In Place Control Rig (Manny/Quinn, UE4) | Pyrebyte Interactive | asset_pack | 5.0–5.7 | $9.99 / $9.99 | **да** | нет | 4.92 (38) | 2026-01-21 |
| f5f95dc3 | Toon Movement Animation Set | Threepeat Games | asset_pack | 5.0–5.6 | $54.99 / $109.99 | **да** | нет | 3.0 (2) | 2025-07-30 |
| 9c15f3a9 | AnimQuest Pack 01 — Stylized Locomotion (6 клипов, FBX 24 fps) | animquest22 | FBX | — | $19.99 / $39.99 | **да** | нет | нет оценок | 2026-09-04 |
| c9d28dc9 | The Locomotion Animation Pack | ByteSumPi LTD | asset_pack | 5.3–5.7 | $29.99 / $40.99 | **да** | нет | 4.76 (17) | 2026-01-06 |
| 006f8bf4 | RPG Animations Pack | DoubleLSoft | asset_pack | 5.0–5.8 | $129.99 / $399.99 | **да** | нет | 4.75 (8) | 2026-09-28 |

Вне Fab:

| Источник | Лицензия | Что есть | Проверено |
|---|---|---|---|
| [KayKit — Character Animations](https://kaylousberg.itch.io/kaykit-character-animations) | CC0, без атрибуции; не перепродавать немодифицированные копии | 161 анимация (бесплатно 150+): общие (idle, hit, death, spawn), **движение: walking, running, jumping, dodging**, мили, дальний бой и магия, эмоции; FBX/GLTF; риги Rig_Medium/Rig_Large; ретаргет средствами движка | страница прочитана 2026-10-03 |
| [Quaternius — Universal Animation Library](https://quaternius.com/packs/universalanimationlibrary.html) | CC0 | 120+ анимаций на универсальном гуманоидном риге, «tested in Unreal Engine», локомоция в 8 направлениях, jog, sprint, push, death и др.; Standard (бесплатно, по данным 80.lv/обзоров — 45 клипов, «не проверено» на самой странице), Pro, Source (.blend) | страница прочитана 2026-10-03; состав Standard «не проверено» |
| Universal Animation Library 2 (Quaternius) | CC0 (по поиску) | 130+ клипов: мили-комбо, паркур и др. | только поиск, «не проверено» |
| Mixamo (Adobe) | бесплатно, без роялти; нельзя распространять сырые файлы ([Adobe FAQ](https://community.adobe.com/questions-696/mixamo-faq-licensing-royalties-ownership-eula-and-tos-589400)) | большой mocap-каталог | скачивание требует входа в аккаунт Adobe — это действие пользователя; условия про ИИ «не проверено» |

### 4.2 Шаблоны и тулкиты для настолок и сеток

| uid | Название | Продавец | Тип | UE | Цена P / Pro | NoAI | AI-сген. | Рейтинг | Обновлено |
|---|---|---|---|---|---|---|---|---|---|
| d9975a03 | Advanced Turn Based Tile Toolkit (ATBTT) | Knut Overbye | complete_project, BP | 4.6–5.8 | $59.99 / $59.99 | нет | нет | 4.83 (175) | 2026-08-27 |
| 3b088653 | Dungeon Crawler Toolkit | Knut Overbye | complete_project | 4.25–5.8 | $49.99 / $49.99 | нет | нет | 4.95 (19) | 2026-08-27 |
| bd11e459 | Turn-Based Tactic - Strategy Template | Alex Quevillon | complete_project | 4.25–5.8 | $49.99 / $69.99 | **да** | нет | 4.82 (11) | 2026-07-20 |
| 9536637b | Turn Based Tactic Starter Pack | SoerGame | complete_project | 4.26–5.8 | $4.99 / $9.99 | **да** | нет | 5.0 (2) | 2026-06-18 |
| 26e3f40e | Hex Grid Toolkit (только координаты hex) | Erades | complete_project | 4.27–5.8 | $14.99 / $29.99 | **да** | нет | 4.73 (11) | 2026-07-01 |
| adc00c7f | Hex Grids V11.0 (C++ плагин) | Zenith Digital | code_plugin | 4.17–5.8 | $34.99 / $80.99 | нет | нет | 4.69 (13) | 2026-08-24 |
| d2dfa825 | Mega Grid System (C++ плагин, hex + square, pathfinding) | Two Bit Studios | code_plugin | 5.0–5.8 | $49.99 / $99.99 | нет | нет | 5.0 (3) | 2026-09-17 |
| 9eeaebe7 | Hex Grid Manager Basic | Mj12 Studio | code_plugin | 5.6 | $49.99 / $89.99 | **да** | нет | нет оценок | 2025-09-09 |
| a338fd7d | Board Game - Template (property trading, 100 % BP) | kcStudio | asset_pack | 5.0–5.8 | $44.99 / $74.99 | **да** | **да** | нет оценок | 2026-07-05 |
| c26f2549 | Universal Multiplayer Tabletop Engine 1.0 (физика, репликация) | oguzgames | asset_pack | 5.5–5.7 | $19.99 / $29.99 | нет | нет | нет оценок | 2026-05-12 |
| 74c2618d | Card Hand Template (виджет руки) | Davide Socol | complete_project | 5.0–5.7 | $23.99 / $23.99 | **да** | нет | 5.0 (8) | 2025-12-30 |
| b9d7f0ae | CCG Toolkit | Aaron Scott | complete_project | 5.1–5.6 | $49.99 / $99.99 | **да** | нет | 4.52 (149) | 2025-10-01 |

Вне Fab: [Dn2 Unreal Engine Game Grids](https://dn2.itch.io/unreal-engine-game-grids) — квадратная сетка + async A*, hex зачёркнут как «ещё не сделано», UE 4.27 и 5.1+, бесплатно на GitHub (ссылка на репозиторий и лицензия «не проверено»), $5 на itch.

### 4.3 Настольный реквизит, миниатюры, карты

| uid | Название | Продавец | UE | Цена P / Pro | NoAI | AI-сген. | Примечание |
|---|---|---|---|---|---|---|---|
| 327ed15e | Ultimate Tabletop RPG & Miniatures | Ultima Store | 5.0–5.8 | $9.99 / $49.99 | нет | **да** | миниатюры, D20, листы персонажа |
| 7e12431a | Ultimate Fantasy Board Game Pieces Low-Poly Pack | Ultima Store | 5.0–5.8 | $9.99 / $49.99 | **да** | **да** | |
| b2be03c9 | Strategy Fog of War & Tactical Map Elements | Ultima Store | 5.0–5.8 | $9.99 / $49.99 | нет | **да** | столы-карты, тактические тайлы, статика |
| a548d795 | Tabletop Auto-Battler Environment Props | Ultima Store | 5.0–5.8 | $9.99 / $49.99 | нет | **да** | |
| a61e2a81 | Miniature Dark Scenery - Gothic Diorama | Ultima Store | 5.0–5.8 | $9.99 / $49.99 | **да** | **да** | опубликован 2026-10-03 |
| 1cea292e | Dioramas - 15 modular figurine bases | Bernhard van der Horst | OBJ/ZBrush | $28.99 / $99.99 | **да** | нет | подставки миниатюр |
| e12dbd00 | Stylized World Map (Cartoon) | Openclay | 5.0–5.8 | $39.99 / $79.99 | **да** | нет | |
| 8d02e633 | Tabletop & RPG - Cinematic Card & Dice VFX | VRhinoFX | 4.27–5.8 | $59.99 / $119.99 | нет | нет | нет оценок |

### 4.4 UI и FX выбора и пути

| uid | Название | Продавец | Тип | UE | Цена P / Pro | NoAI | Рейтинг | Что делает |
|---|---|---|---|---|---|---|---|---|
| 15d5f5c7 | Simple Path Tracer | Andrew Esenin | code_plugin (C++) | 4.27–5.8 | $19.99 / $19.99 | нет | 5.0 (9) | рисует пути, границы и стрелки в редакторе и в рантайме |
| 903895b4 | Path Tracer Toolkit | Andrew Esenin | complete_project | 4.27–5.8 | $14.99 / $14.99 | нет | 4.78 (18) | сплайн-пути и границы из массива точек в рантайме |
| 471de6d6 | Glow Path (light trail spline) | Richarme | asset_pack (BP) | 4.27–5.8 | $34.99 / $49.99 | нет | 5.0 (4) | анимированный световой след по сплайну |
| 8e33a0bf | Map Track Markers VFX | Hovl Studio | asset_pack | 4.24–5.8 | $12.99 / $12.99 | **да** | 5.0 (2) | 12 Niagara-маркеров |
| 87b2de15 | RPG Indicator | World Protocol | asset_pack | 5.1–5.8 | $14.99 / $24.99 | **да** | 5.0 (2) | индикаторы-компоненты на акторах |
| cc39c463 | RTS Essentials - Selection VFX Pack | AmberleafCotton | asset_pack | 5.0–5.7 | $2.99 / $3.99 | **да** | нет оценок | круглые и квадратные контуры выбора |
| c49fb9f8 | Selection outline highlights | Construct Games | asset_pack | 5.1–5.4 | $3.99 / $9.99 | **да** | нет оценок | |
| c603ad45 | Highlight & outline Post-Process | Aukke Production | asset_pack | 5.3–5.8 | $9.99 / $19.99 | **да** | 5.0 (4) | обводка мешей пост-процессом |
| 8d7a85c6 | Local Outlines | Luna Joy | asset_pack | 4.22–5.8 | $9.99 / $9.99 | **да** | 5.0 (11) | обводка декалями |
| 7be55587 | OutlineMaker | Francesco Desogus | material | 4.19–5.8 | $14.99 / $19.99 | **да** | 4.82 (34) | |
| dda318c7 | Magic Circle Creator | Dragon Motion | asset_pack | 4.22–5.8 | $14.99 / $29.99 | нет | 4.79 (43) | конструктор магических кругов, параметры в рантайме |
| e3f3688d | 100 Buffs, Auras and Magic Circles VFX Pack | VAP1 | asset_pack | 4.26–5.8 | $29.99 / $34.99 | нет | 4.4 (5) | 100 Niagara-систем |
| 2e438fb0 | Eroding Circle Niagara System | semko | asset_pack | 5.7–5.8 | $0 / $0.99 | **да** | 5.0 (1) | |
| 060f0bcd | Scan Grid Effect | Studio Cloe | asset_pack | 5.1–5.8 | $24.99 / $44.99 | **да** | 4.57 (7) | |
| 10431a22 | Zero Aliasing Procedural Grid | Two Bit Studios | material | 5.0–5.8 | $14.99 / $29.99 | **да** | 5.0 (1) | процедурная сетка, hex |
| f530e3f4 | Grid material (Grid Material Preview Pack) | Pixel Affect | material | 5.0–5.8 | $0 / $4.99 | нет | 5.0 (2) | серые сетки для прототипа |
| a11e7bbc | Dynamic Navigation Arrows | Pieria Software | ui | 5.0–5.8 | $1.99 / $3.99 | **да** | 5.0 (8) | |
| d3b25ec5 | DzX Radial Menu - UMG | IgorLekic | code_plugin | 4.23–5.8 | free | **да** | 4.67 (18) | ядро радиального меню на UMG |
| a01c3623 | Generic Radial Menus v2.0 | PolyHavoc | ui | 4.19–5.8 | $19.99 / $29.99 | **да** | 4.93 (54) | |
| e36ccd68 | Narrative Common UI | Narrative Tools Inc. | code_plugin | 5.1–5.8 | free | нет | 3.93 (27) | надстройка над CommonUI |
| 00621b21 | UI Effect Function Library | UI Effect Fantasy | code_plugin | 5.0–5.8 | free | **да** (по harvest 01.10 и API) | 5.0 (6) | |
| 69680f34 | UI Material Lab | Epic Education | complete_project | 5.1–5.5 | free | **да** | 5.0 (45) | |
| 0e188eca | Niagara Examples Pack | Epic Games | asset_pack | 5.7 | free | **да** | 4.77 (30) | |
| 5dce0c7e | Stylized RPG Cursors | Lid Games | ui | 4.27–5.7 | $9.99 / $29.99 | **да** | 4.0 (4) | |
| 370b30f9 | Fantasy RPG Cursors | Leonid Deburger | sprites | 4.18–5.4 | $9.99 / $9.99 | **да** | 5.0 (2) | |
| 60701332 | Selection Manager | Andrew Esenin | code_plugin | 4.26–5.8 | $15.99 / $19.99 | нет | 4.76 (17) | выбор мышью и рамкой |
| d85dee78 | Anime Stylized VFX | Vefects | asset_pack | 4.27–5.8 | $52.99 / $99.99 | **да** | 4.92 (12) | |
| 21554aed | Stylized Toon VFX | Hovl Studio | asset_pack | 4.25–5.8 | $24.99 / $28.99 | **да** | 5.0 (1) | |
| fb84a9a9 | Card & Board Game Sound Effects (137 звуков) | Cyberwave Orchestra | asset_pack | 4.23–5.8 | $29.99 / $44.99 | нет | нет оценок | |

Эпик-сэмплы (все NoAI, бесплатно): Lyra Starter Game 93faede1 (5.0–5.8, обновлён 2026-09-30), City Sample 4898e707 (5.0–5.8), Cropout Sample Project bd733d81 (5.2–5.8; top-down casual RTS, CommonUI, Enhanced Input, click-and-drag — по [блогу Epic](https://www.unrealengine.com/blog/cropout-casual-rts-game-sample-project) из выдачи поиска).

## 5. Документация движка (для «делаем сами»)

| Тема | Источник (2026-10-03) |
|---|---|
| Spline Component и Spline Mesh Component (путь, стрелка) | [Blueprint Spline Components Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-spline-components-overview-in-unreal-engine), [SplineMeshComponent (Python API)](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SplineMeshComponent) |
| IK Rig / IK Retargeter | [IK Rig Animation Retargeting](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine) |
| Custom Depth/Stencil обводка | официальной страницы поиск не дал; общеизвестный приём, описан у Tom Looman ([tomlooman.com](https://tomlooman.com/unreal-engine-outline-multi-color-post-process/)) — «не проверено» по докам Epic |
| Обновление GASP под 5.8 | [tech-blog Epic, 2026-08-12](https://www.unrealengine.com/tech-blog/download-the-latest-game-animation-sample-project-now-updated-for-ue-5-8) (прочитан через web-reader): Physics Control, multi-character motion matching, ragdoll, Look-At Control Rig, 500+ анимаций на UE5 Mannequin |

## 6. Не проверено

- Полный текст Epic Content License и Fab EULA (JS-рендер): формулировки про NoAI взяты из выдачи поиска.
- UE-Only у Epic-листингов, кроме Game Animation Sample.
- Списки версий UE — из API поиска; сборка/импорт в 5.8 ничего не проверялись.
- Состав бесплатного тира Quaternius UAL (45 клипов — по сторонним обзорам).
- Лицензия GitHub-версии Dn2 Game Grids.
- Превью и стиль платных паков не смотрелись; у NoAI-паков превью сознательно не открывались.
- Условия Mixamo про ИИ и необходимость входа (вход — действие пользователя).
- Скидки на дату проверки (`isDiscounted`) не учитывались.
