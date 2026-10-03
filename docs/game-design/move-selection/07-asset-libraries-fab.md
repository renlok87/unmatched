# 07. Библиотеки Fab и другие готовые ассеты для подбора хода

Дата проверки данных: **2026-10-03**. Статус: исследование, предложение. Часть пакета [подбора хода](README.md); как
выводы этого документа входят в план — [05 §6](05-implementation-plan.md). Ничего не куплено, не добавлено в библиотеку Fab и не скачано. Сырые данные, метод и полный список непроверенного — в [_research/R5-fab-libraries.md](_research/R5-fab-libraries.md).

Тема — готовые библиотеки для всех шагов подбора хода: выбор бойца, подсветка достижимых клеток, превью пути, подтверждение и отмена, анимация перемещения фигурки, показ хода сопернику. Исследование продолжает каталог 27.09 ([каталог](../../research/2026-09-27-ue-assets-catalog.md), [шорт-лист](../../research/2026-09-27-ue-assets-shortlist.md)) и не повторяет его. Принятые там решения ([18-third-party-tools-and-assets-decisions.md](../18-third-party-tools-and-assets-decisions.md)) остаются в силе.

## Коротко

1. **Готового «модуля подбора хода» под нашу архитектуру нет ни на Fab, ни вне его.** Все тактические шаблоны (ATBTT, Turn-Based Tactic Template, Mega Grid, Hex Grids) приносят свою сетку, поиск пути, ходы и ИИ. У нас всё это делает сервер, а доска строится из `boardState`, в том числе графовая доска оригинальных карт. Подбор хода собираем из встроенных средств UE 5.8: ISM с per-instance custom data (подложки и линия пути — 04 §6.1), Custom Depth, Niagara (только акценты), UMG-гибрид (решение U-4). Это бесплатно, без лицензионных ограничений и уже частично сделано (`S08BoardActor.h:252-253`). CommonUI в проекте не включён (нет в `Unmatched.uproject` и в зависимостях `Unmatched.Build.cs:5-11`) и в MVP не вводится (U-4, `decisions/2026-09-29-render-ui-user-decisions.md:46`).
2. **Новый факт: все проверенные сэмплы Epic помечены NoAI.** Это Game Animation Sample, Lyra, City Sample, Cropout, Paragon, UI Material Lab, Niagara Examples и Control Rig Samples. Помечены и большинство дешёвых UI/FX-паков: обводки, курсоры, радиальные меню, маркеры. NoAI-контент нельзя подавать на вход генеративному ИИ, а наш конвейер отдаёт кадры агентам на ревью. Поэтому такие ассеты годятся только как ручной референс пользователя или как отдельный вариант вне кадров для агентов. Так уже сделано с Megaplants (`docs/art-pipeline/CREDITS-fab.md:13`).
3. **Анимация перемещения.** D-11 и CUE-007 задают скольжение актора без клипа (`00-vision-and-scope.md:105`, `07-animation-vfx-audio.csv:8`). Под это ассеты не нужны: дугу «подскока» и сжатие-растяжение можно сделать кодом актора. Если пользователь захочет клип шага или прыжка, нужно изменить D-11. Источники такого клипа — CC0-библиотеки KayKit (уже пилот) и Quaternius Universal Animation Library. Game Animation Sample не подходит: NoAI, реализм, около 90 костей Manny против 17 у UM17.
4. **Что стоит оценить за деньги** (всё без NoAI, заявлена UE 5.8, вместе меньше $100):
   - Magic Circle Creator ($14.99) — кольца выбора и цели;
   - Simple Path Tracer ($19.99, C++) — стрелка пути;
   - Glow Path ($34.99) — световой след хода соперника;
   - Card & Board Game SFX ($29.99) — тик шага.

   Каждый оцениваем против собственной реализации за 0,5–1 день. Покупка — только если плагин быстрее и проходит наши правила для FX (`tools/art/env_kit/ue_import_fab_fx.py:7-11`).
5. **ATBTT теперь заявляет UE 5.8**, на 27.09 было «не подтверждена». Вердикт «не брать» от этого не меняется: причина отказа была архитектурная, а не в версии.

## 1. Рамки отбора

| Ограничение | Источник | Что отсекает |
|---|---|---|
| Тонкий клиент: правила решает сервер; достижимость и путь клиент считает как подсказку тем же алгоритмом (сервер их не отдаёт — [R1](_research/R1-rules-engine.md) §1 п. 4) | P4/INT-001; `09-vertical-slice-and-backlog.md:343-354` (TASK-027: BFS-подсказка = логика сервера) | тулкиты со своим pathfinding, менеджером ходов, ИИ, репликацией |
| Доска из `boardState`: сетка и графовые карты (пространства, связи, зоны) | `S08BoardActor.cpp:1783` (`IsBoardSpace` — подсветка только на точках графа) | генераторы сеток, hex-координаты |
| Перемещение — скольжение актора, не клип | D-11 `00-vision-and-scope.md:105`; CUE-007 `07-animation-vfx-audio.csv:8`; `RIG-CONTRACT.md:86-89` | локомоционные паки, Motion Matching (как зависимость) |
| Свой риг UM17 v2 (17 костей, rest = поза миниатюры, 24 FPS) | `RIG-CONTRACT.md:80-82, 113, 135` | прямое использование клипов Manny/Mixamo без ретаргета |
| Кадры отдаются ИИ-агентам: NoAI нельзя в кадры для ревью | `fab-free-assets-research-2026-10-01.md:26`; `ue_import_fab_fx.py:57-59` | NoAI-паки в основном варианте |
| FX: CPU, детерминизм, без света из Niagara | `ue_import_fab_fx.py:7-11` | эффекты, которые держатся на точечных источниках света |
| UE 5.8, DX12 + Lumen, эталон High | `Unmatched.uproject:1`; AGENTS.md «Unreal GPU load» | паки без 5.8, тяжёлые пост-процессы без замера |
| Использование только личное и локальное | `CREDITS-fab.md:3-4` | лицензионно подходят Personal-тир Fab, CC0, CC BY (с атрибуцией) и UE-Only |

## 2. База: что даёт сам движок

| Шаг подбора хода | Встроенное средство UE 5.8 | Что уже есть у нас |
|---|---|---|
| Выбор бойца | кольцо-меш с MID; обводка через Custom Depth/Stencil | `SetSelectedFighter` (`S08BoardActor.h:252-253`), кольцо команды |
| Достижимые клетки и точки графа | ISM с per-instance custom data (MS-D-12); декали отклонены (01 §4) | спавн `AActor` на клетку (`S08BoardActor.cpp:1783-1800`) |
| Превью пути | `USplineComponent` + `USplineMeshComponent` (тело стрелки), наконечник отдельным мешем, материал с панорамой UV ([доки Epic](https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-spline-components-overview-in-unreal-engine)); в плане — ISM прямых сегментов, потому что связи и шаги сетки прямые (04 §6.1) | нет |
| Подтверждение и отмена | CUE-003: сжатие кольца/заливки, `M_HighlightGameLayer`; кнопки UMG-гибрида (U-4) | материал игрового слоя (W4-A) |
| Перемещение фигурки | интерполяция актора по точкам пути (Timeline/Tick), опционально дуга по Z и squash по шкале | CUE-007 в спецификации |
| Ход соперника | контур формы команды на подложках и точки пути (V-14/V-15, 03 §4.2); Niagara — только акценты | нет |
| Тик шага, пыль | `SoundCue` на клетку, Niagara-пыль (CPU, без света) | Niagara уже в `Unmatched.Build.cs:28` |
| Ретаргет клипа (если понадобится) | IK Rig / IK Retargeter ([доки Epic](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine)) | `ik_chains` и `retarget_maps` в `rig-contract.json:265` |

Вывод: всю механику подбора хода закрывает движок. От Fab имеет смысл брать только **внешний вид**: стилизованные кольца, след и звук, и только без NoAI.

## 3. Топ-10 с вердиктом

Вердикты: **adopt** — брать/использовать; **evaluate** — проверить коротким спайком против своей реализации; **avoid** — не брать (для референса — только человеком).

| # | Кандидат | Цена (2026-10-03) | Лицензия / NoAI | UE | Вердикт | Почему |
|---|---|---|---|---|---|---|
| 1 | **Встроенные средства UE 5.8**: ISM, Spline/SplineMesh, Custom Depth/Stencil, Niagara, UMG, IK Retargeter (CommonUI не включён, в MVP не вводится — U-4) | $0 | UE EULA; NoAI-тега нет | 5.8 | **adopt** | закрывают всю механику §2; C++ в S08/S09; часть уже работает |
| 2 | [KayKit — Character Animations](https://kaylousberg.itch.io/kaykit-character-animations) | $0 (SOURCE $14.99) | CC0, ИИ разрешён | FBX/GLTF | **adopt** (как источник опционального клипа, уже пилот по 18:17) | есть walking/running/jumping/dodging; стилизованная простая пластика ближе к «миниатюре»; нужен `kaykit_to_um17` в `retarget_maps` — его нет |
| 3 | [Quaternius — Universal Animation Library](https://quaternius.com/packs/universalanimationlibrary.html) | $0 Standard / Pro / Source | CC0 | FBX/glTF, «tested in Unreal» | **evaluate** | второй CC0-источник локомоции и прыжков на едином гуманоидном риге; состав бесплатного тира «не проверено» |
| 4 | [Magic Circle Creator](https://www.fab.com/listings/dda318c7-92ae-443f-a7ab-7a2d656758a4) (Dragon Motion) | $14.99 / $29.99 | Fab Standard; NoAI нет | 4.22–5.8 | **evaluate** | параметрический круг под кольцо выбора и кольцо цели (CUE-003); 4.79 при 43 оценках. Риск: у других паков продавца Niagara добавляет PointLight (`CREDITS-fab.md:18`) — проверить и выключить |
| 5 | [Simple Path Tracer](https://www.fab.com/listings/15d5f5c7-72ce-42e3-9e8f-bf0f4c5726b6) (Andrew Esenin) | $19.99 | Fab Standard; NoAI нет | 4.27–5.8, C++ code plugin | **evaluate** | пути, границы и стрелки в рантайме по массиву точек — ровно превью пути и обводка зон. Сравнить со своей ISM-линией из прямых сегментов (04 §6.1; около дня работы) |
| 6 | [Glow Path](https://www.fab.com/listings/471de6d6-2d88-40c6-ad2e-776870c3d51e) (Richarme) | $34.99 / $49.99 | Fab Standard; NoAI нет | 4.27–5.8, BP | **evaluate** | анимированный световой след по сплайну: показать путь хода соперника и бота. Проверить стоимость на Lumen High |
| 7 | [Card & Board Game Sound Effects](https://www.fab.com/listings/fb84a9a9-1464-4588-8d26-2baf6d7a3da4) (Cyberwave Orchestra) | $29.99 / $44.99 | Fab Standard; NoAI нет | 4.23–5.8 | **evaluate** | 137 звуков настолки: тик шага на клетку (CUE-007), подтверждение и отмена. Альтернатива — JDSherbert, уже «Позже» по 18:21. Оценок нет — слушать до покупки |
| 8 | [100 Buffs, Auras and Magic Circles](https://www.fab.com/listings/e3f3688d-8501-4901-9a65-3ef7c6bc9937) (VAP1) | $29.99 / $34.99 | Fab Standard; NoAI нет | 4.26–5.8 | **evaluate** (запасной к №4) | библиотека аур и кругов для подсветки целей и зон; стиль сверить с «окрашенной статуэткой» |
| 9 | [Advanced Turn Based Tile Toolkit](https://www.fab.com/listings/d9975a03-797a-47ca-8da0-06d8eee49b69) (ATBTT) | $59.99 | Fab Standard; NoAI нет | 4.6–5.8 (новое) | **avoid** | своя сетка, путь, ходы, ИИ и сетевой код против сервера-авторитета; 100 % BP; решение 27.09 (`shortlist.md:109`) в силе. Смотреть только видео как UX-референс |
| 10 | Сэмплы Epic: [Game Animation Sample](https://www.fab.com/listings/880e319a-a59e-4ed2-b268-b32dac7fa016), [Lyra](https://www.fab.com/listings/93faede1-4434-47c0-85f1-bf27c0820ad0), [Cropout](https://www.fab.com/listings/bd733d81-7c29-44fe-b53f-65b14d06a9e2), [UI Material Lab](https://www.fab.com/listings/69680f34-e5d2-44e6-b023-f054bbf629eb) | $0 | Epic; **NoAI**; GASP — UE-Only | 5.0–5.8 (UI Material Lab 5.1–5.5) | **avoid** в проекте и в работе агентов | NoAI запрещает подавать их агентам. GASP — Motion Matching на Manny против D-11 и UM17. Cropout (top-down, CommonUI, click-to-move) и Lyra полезны только пользователю для ручного просмотра |

## 4. Анимации перемещения

**Вывод: по текущим решениям анимационная библиотека для хода не нужна.**
- D-11 и CUE-007 прямо говорят «скольжение, не скелетная анимация» (`07-animation-vfx-audio.csv:8`).
- Клипы ART-004 сделаны in place, а root motion выключен на импорте (`RIG-CONTRACT.md:89`).

**Если пользователь захочет живее, есть три уровня.**
- **0, текущий.** Скольжение по точкам пути, idle продолжает играть. Ассетов не нужно.
- **1, рекомендуемый следующий шаг.**
  - Процедурный «подскок миниатюры»: дуга по Z высотой 8–15 % роста и короткий squash/stretch на взлёте и посадке, по одному на клетку. Пыль Niagara — на конечной клетке.
  - Тоже без клипов и без изменения D-11. Это поведение актора: чистый C++ в `AS08FighterActor`.
  - Числа — предложение, «не проверено» на кадрах.
- **2, требует изменить D-11 (решение пользователя).** Короткий in-place клип «hop» или «step», 0,3–0,5 с при 24 FPS. Его проигрываем поверх скольжения. Источник:
  - KayKit, ретаргет Rig_Medium → UM17, нужна новая карта в `rig-contract.json`;
  - или Quaternius UAL;
  - или анимируем сами в Blender по брифу 18.

  Клип проходит `validate_clip.py` как `oneshot`: кадр 0 и последний = rest, in place.

**Почему не платные локомоционные паки.** Проверено 13 листингов (таблица 7.1). Почти все помечены NoAI: Jump Animations Pack, Hopping Pack, Locomotion Pack, Toon Movement, AnimQuest, RPG Animations. Почти все сняты на Manny/UE4-скелете и рассчитаны на реалистичную пластику. Без NoAI только Cool Turn Animations, но там root motion и разворот «босса» — не наш случай.

**Game Animation Sample (5.8, обновлён 2026-08-12).** Новое в версии: Physics Control, multi-character motion matching, ragdoll, Look-At Control Rig. Ничего из этого не нужно фигурке на подносе. Плюс NoAI. Вердикт 27.09 «референс, не зависимость» уточняется: референс только для пользователя.

## 5. Шаблоны настолок и сеток

Все проверенные шаблоны конфликтуют с правилом «правила — на сервере»:
- ATBTT;
- Dungeon Crawler Toolkit;
- Turn-Based Tactic Template;
- Turn Based Tactic Starter Pack;
- Hex Grid Toolkit, Hex Grids V11, Mega Grid System, Hex Grid Manager;
- Board Game - Template;
- Universal Multiplayer Tabletop Engine;
- Dn2 Game Grids.

Сетку и hex-координаты нам не нужно генерировать: доска приходит из `boardState`, на оригинальных картах это граф точек и связей. Достижимость повторяет серверный BFS (TASK-027). Сеть идёт через GraphQL. Брать их ради подсветки клеток дороже, чем подсветка, которая уже есть.

**Отдельные причины против:**
- *Universal Multiplayer Tabletop Engine* — физическая репликация фигур прямо противоречит серверной авторитетности; 5.8 не заявлена.
- *Board Game - Template (kcStudio)* — NoAI и AI-generated, экономика «монополии».
- *Паки Ultima Store* (миниатюры, фигуры, тактические карты) — у всех `isAiGenerated=true`, половина с NoAI. Качество уровня Tripo, как у других AI-паков в ресерче 01.10.
- *Подставки миниатюр* (Dioramas 15 modular bases) — NoAI. Подставки у нас и так делаются в своём конвейере (`SM_Medusa_Base`, `RIG-CONTRACT.md:118`).

Карточные (CCG Toolkit, Card Hand Template) — вне темы хода. Оба NoAI, решение 27.09 в силе.

## 6. UI и FX выбора и пути

| Задача | Своё (рекомендация) | Кандидат с Fab без NoAI | NoAI-аналоги (не брать в основной вариант) |
|---|---|---|---|
| Кольцо выбора бойца | меш-кольцо + MID (уже есть) | Magic Circle Creator, 100 Buffs/Auras | RTS Essentials Selection VFX, Eroding Circle |
| Обводка выбранного/цели | Custom Depth/Stencil + post-process, 1 материал | — (все найденные обводки NoAI) | Highlight & outline PP, Local Outlines, OutlineMaker, Selection outline highlights |
| Подсветка достижимых точек | ISM-подложки с custom data сразу (MS-D-12) | Grid material (Pixel Affect, бесплатно для Personal) — только прототип | Zero Aliasing Procedural Grid, Scan Grid Effect |
| Стрелка пути | ISM прямых сегментов + наконечник (04 §6.1) | Simple Path Tracer (C++), Path Tracer Toolkit (BP, $14.99) | Dynamic Navigation Arrows |
| Ход соперника, след | контур формы команды на подложках V-14/V-15 + точки пути | Glow Path | Map Track Markers VFX |
| Радиальное меню (буст / действие) | в MVP нет: буст — в панели руки; при необходимости — UMG-виджет (U-4) | Narrative Common UI (бесплатно, но лишний фреймворк) | DzX Radial Menu, Generic Radial Menus v2 |
| Курсоры | свои по UI-семейству ART-011 | — | Stylized RPG Cursors, Fantasy RPG Cursors |
| Выбор кликом/рамкой | TASK-022 (уже есть) | Selection Manager — **avoid**, дублирует TASK-022 | — |

## 7. Полная таблица

Цены — Personal / Professional в USD без налогов на 2026-10-03, из `priceTierId` карточки Fab. UE — список версий из API поиска Fab; «—» значит FBX/OBJ или не указано. NoAI и AI-сген. — поля `isAiForbidden` и `isAiGenerated` карточки. Тип: code plugin / content (asset pack) / project.

### 7.1 Анимации

| Кандидат | Продавец | Цена | Лицензия | NoAI | UE | Тип | Что решает | Вердикт |
|---|---|---|---|---|---|---|---|---|
| [KayKit Character Animations](https://kaylousberg.itch.io/kaykit-character-animations) | Kay Lousberg | $0 | CC0 | нет | FBX/GLTF | content | опциональный hop/jump/walk, idle | adopt (пилот) |
| [Quaternius UAL](https://quaternius.com/packs/universalanimationlibrary.html) | Quaternius | $0 / Pro / Source | CC0 | нет | FBX/glTF | content | локомоция, прыжок | evaluate |
| Mixamo | Adobe | $0 | Adobe ToS, сырые файлы не распространять | не проверено | FBX | content | mocap-клипы | avoid (вход в Adobe — действие пользователя; реализм) |
| [Game Animation Sample](https://www.fab.com/listings/880e319a-a59e-4ed2-b268-b32dac7fa016) | Epic Games | $0 | Epic, UE-Only | **да** | 5.4–5.8 | project | Motion Matching | avoid |
| [GASP retargeted to Manny](https://www.fab.com/listings/259f8545-f820-47b3-8fc1-e8ec5458214d) | Kingboars | $0 | Fab Standard (переупаковка Epic) | **да** | — | content | то же | avoid |
| [Slay Animation Sample](https://www.fab.com/listings/ef920974-4e1d-4ca9-afe2-277f5adcfe53) | Epic Games | $0 | Epic | **да** | 4.27–5.8 | project | боевые клипы | avoid |
| [Paragon (серия, пример Serath)](https://www.fab.com/listings/522b6160-15ab-492b-a2b0-c09f9bb5f6e6) | Epic Games | $0 | Epic | **да** | 4.19–5.8 | content | герои с анимациями | avoid |
| [Control Rig Samples Pack](https://www.fab.com/listings/2ce3fe44-9ee6-4fa7-99fc-b9424a402386) | Epic Games | $0 | Epic | **да** | 5.1–5.7 | content | процедурная анимация | avoid |
| [Jump Animations Pack](https://www.fab.com/listings/3ffd8680-1d1e-4650-a6ff-f27128059a16) | Jane Gintsar | $4.99 / $9.99 | Fab Standard | **да** | 5.5–5.8 | content | 14 прыжков | avoid |
| [Hopping Animation Pack](https://www.fab.com/listings/8f27bbc1-457c-4de0-809b-627821661521) | Ailive | $3.99 / $7.99 | Fab Standard | **да** | — | content | 5 mocap-подскоков | avoid |
| [Cool Turn Animations](https://www.fab.com/listings/ba95e214-542a-42c6-8d83-275337bc63cc) | Bacengdu | $10.99 / $27.99 | Fab Standard | нет | 5.1–5.8 | content | 33 разворота, root motion | avoid (не наш случай) |
| [Simple Turn In Place Control Rig](https://www.fab.com/listings/ccea2285-893e-449b-8843-04fc90197b91) | Pyrebyte | $9.99 | Fab Standard | **да** | 5.0–5.7 | content | разворот на месте (Manny) | avoid |
| [Toon Movement Animation Set](https://www.fab.com/listings/f5f95dc3-19cd-414b-b6d9-b60053dfbf61) | Threepeat Games | $54.99 / $109.99 | Fab Standard | **да** | 5.0–5.6 | content | мультяшная локомоция | avoid |
| [AnimQuest Pack 01](https://www.fab.com/listings/9c15f3a9-b5de-486b-be40-ad60b7f66b7d) | animquest22 | $19.99 / $39.99 | Fab Standard | **да** | FBX 24 fps | content | 6 стилиз. клипов | avoid |
| [The Locomotion Animation Pack](https://www.fab.com/listings/c9d28dc9-7730-468e-8bfb-f2b2c464d9be) | ByteSumPi | $29.99 / $40.99 | Fab Standard | **да** | 5.3–5.7 | content | локомоция | avoid |
| [RPG Animations Pack](https://www.fab.com/listings/006f8bf4-7be4-412b-8b5d-16e3e5d3206a) | DoubleLSoft | $129.99 / $399.99 | Fab Standard | **да** | 5.0–5.8 | content | RPG-набор | avoid |

### 7.2 Шаблоны, тулкиты, реквизит

| Кандидат | Продавец | Цена | NoAI / AI-сген. | UE | Тип | Что решает | Вердикт |
|---|---|---|---|---|---|---|---|
| [ATBTT](https://www.fab.com/listings/d9975a03-797a-47ca-8da0-06d8eee49b69) | Knut Overbye | $59.99 | нет / нет | 4.6–5.8 | project (BP) | тактика на сетке целиком | avoid |
| [Dungeon Crawler Toolkit](https://www.fab.com/listings/3b088653-426d-4c49-a14f-759817133647) | Knut Overbye | $49.99 | нет / нет | 4.25–5.8 | project | first-person grid crawler | avoid |
| [Turn-Based Tactic - Strategy Template](https://www.fab.com/listings/bd11e459-47bd-45b4-a7ce-af1a227bc5ac) | Alex Quevillon | $49.99 / $69.99 | **да** / нет | 4.25–5.8 | project | тактический шаблон | avoid |
| [Turn Based Tactic Starter Pack](https://www.fab.com/listings/9536637b-0385-4eb9-8faa-21e72b14b07a) | SoerGame | $4.99 / $9.99 | **да** / нет | 4.26–5.8 | project | стартер | avoid |
| [Hex Grid Toolkit](https://www.fab.com/listings/26e3f40e-3fa1-4c4f-b948-e4dbdcb56fbb) | Erades | $14.99 / $29.99 | **да** / нет | 4.27–5.8 | project | hex-координаты | avoid |
| [Hex Grids V11.0](https://www.fab.com/listings/adc00c7f-6204-4504-9b9c-338377def5e6) | Zenith Digital | $34.99 / $80.99 | нет / нет | 4.17–5.8 | code plugin | hex-сетки C++ | avoid |
| [Mega Grid System](https://www.fab.com/listings/d2dfa825-276b-429a-a46a-1152edd231cc) | Two Bit Studios | $49.99 / $99.99 | нет / нет | 5.0–5.8 | code plugin | сетка + pathfinding C++ | avoid |
| [Hex Grid Manager Basic](https://www.fab.com/listings/9eeaebe7-3a8a-46ed-be9d-e5b58aaaa6b6) | Mj12 Studio | $49.99 / $89.99 | **да** / нет | 5.6 | code plugin | hex-менеджер | avoid |
| [Board Game - Template](https://www.fab.com/listings/a338fd7d-4e5a-4806-a612-862e1c5af4eb) | kcStudio | $44.99 / $74.99 | **да** / **да** | 5.0–5.8 | content (BP) | «монополия» | avoid |
| [Universal Multiplayer Tabletop Engine](https://www.fab.com/listings/c26f2549-3e10-4094-9b22-432fe858ec78) | oguzgames | $19.99 / $29.99 | нет / нет | 5.5–5.7 | content | физическая настолка + репликация | avoid |
| [Dn2 Game Grids](https://dn2.itch.io/unreal-engine-game-grids) | Dn2 | $5 itch / GitHub бесплатно | не проверено | 4.27, 5.1+ | code plugin | square + A*; hex не готов | avoid |
| [CCG Toolkit](https://www.fab.com/listings/b9d7f0ae-d9f1-4086-9014-4c5c5bc04872) | Aaron Scott | $49.99 / $99.99 | **да** / нет | 5.1–5.6 | project | карточный фреймворк | avoid (решение 27.09) |
| [Card Hand Template](https://www.fab.com/listings/74c2618d-4efa-4355-8126-11cd050e14f2) | Davide Socol | $23.99 | **да** / нет | 5.0–5.7 | project | виджет руки | avoid |
| [Ultimate Tabletop RPG & Miniatures](https://www.fab.com/listings/327ed15e-13e3-484c-9c52-0c66f7232474) | Ultima Store | $9.99 / $49.99 | нет / **да** | 5.0–5.8 | content | миниатюры, D20 | avoid |
| [Ultimate Fantasy Board Game Pieces](https://www.fab.com/listings/7e12431a-f2aa-4476-866d-011a1bd2f82a) | Ultima Store | $9.99 / $49.99 | **да** / **да** | 5.0–5.8 | content | фишки | avoid |
| [Strategy Fog of War & Tactical Map Elements](https://www.fab.com/listings/b2be03c9-fe97-46d4-91c0-64038f30a11b) | Ultima Store | $9.99 / $49.99 | нет / **да** | 5.0–5.8 | content | столы-карты, тайлы | avoid |
| [Tabletop Auto-Battler Environment Props](https://www.fab.com/listings/a548d795-ec2e-47b2-9a31-0009ee97207a) | Ultima Store | $9.99 / $49.99 | нет / **да** | 5.0–5.8 | content | реквизит | avoid |
| [Dioramas - 15 modular figurine bases](https://www.fab.com/listings/1cea292e-201a-41f2-b545-63b998eb674c) | Bernhard van der Horst | $28.99 / $99.99 | **да** / нет | OBJ | content | подставки | avoid |
| [Stylized World Map (Cartoon)](https://www.fab.com/listings/e12dbd00-aaac-4eb9-b371-b9abe5fd4ec3) | Openclay | $39.99 / $79.99 | **да** / нет | 5.0–5.8 | project | карта мира | avoid |
| [Tabletop & RPG - Cinematic Card & Dice VFX](https://www.fab.com/listings/8d02e633-76f6-4a53-a206-8d64965b6b77) | VRhinoFX | $59.99 / $119.99 | нет / нет | 4.27–5.8 | content | VFX карт и кубов | avoid для хода (вне темы; к CUE-006 — отдельно) |

### 7.3 UI, FX, звук

| Кандидат | Продавец | Цена | NoAI | UE | Тип | Что решает | Вердикт |
|---|---|---|---|---|---|---|---|
| [Magic Circle Creator](https://www.fab.com/listings/dda318c7-92ae-443f-a7ab-7a2d656758a4) | Dragon Motion | $14.99 / $29.99 | нет | 4.22–5.8 | content | кольцо выбора/цели | evaluate |
| [100 Buffs, Auras and Magic Circles](https://www.fab.com/listings/e3f3688d-8501-4901-9a65-3ef7c6bc9937) | VAP1 | $29.99 / $34.99 | нет | 4.26–5.8 | content | ауры, круги | evaluate (запас) |
| [Simple Path Tracer](https://www.fab.com/listings/15d5f5c7-72ce-42e3-9e8f-bf0f4c5726b6) | Andrew Esenin | $19.99 | нет | 4.27–5.8 | code plugin | стрелка пути, границы | evaluate |
| [Path Tracer Toolkit](https://www.fab.com/listings/903895b4-4f70-4024-a943-882c970cee08) | Andrew Esenin | $14.99 | нет | 4.27–5.8 | project (BP) | то же на BP | evaluate (если не C++) |
| [Glow Path](https://www.fab.com/listings/471de6d6-2d88-40c6-ad2e-776870c3d51e) | Richarme | $34.99 / $49.99 | нет | 4.27–5.8 | content (BP) | след хода соперника | evaluate |
| [Card & Board Game Sound Effects](https://www.fab.com/listings/fb84a9a9-1464-4588-8d26-2baf6d7a3da4) | Cyberwave Orchestra | $29.99 / $44.99 | нет | 4.23–5.8 | content | тик шага, клики | evaluate |
| [Grid material](https://www.fab.com/listings/f530e3f4-93e7-4827-a8f1-ee1a22e19f2a) | Pixel Affect | $0 / $4.99 | нет | 5.0–5.8 | content | серые сетки прототипа | evaluate (низкий приоритет) |
| [Narrative Common UI](https://www.fab.com/listings/e36ccd68-6ba6-4a2d-9bff-a857c39ad2e3) | Narrative Tools | $0 | нет | 5.1–5.8 | code plugin | надстройка CommonUI | avoid (лишний слой) |
| [Selection Manager](https://www.fab.com/listings/60701332-bc86-48ea-88ac-c13a145bf747) | Andrew Esenin | $15.99 / $19.99 | нет | 4.26–5.8 | code plugin | выбор мышью/рамкой | avoid (дублирует TASK-022) |
| [Map Track Markers VFX](https://www.fab.com/listings/8e33a0bf-01fe-415c-a664-08fd92a2d33e) | Hovl Studio | $12.99 | **да** | 4.24–5.8 | content | маркеры пути | avoid |
| [RPG Indicator](https://www.fab.com/listings/87b2de15-8d90-4969-99b5-39a37e18e86e) | World Protocol | $14.99 / $24.99 | **да** | 5.1–5.8 | content | индикаторы | avoid |
| [RTS Essentials - Selection VFX](https://www.fab.com/listings/cc39c463-962c-4795-9094-4d357d308c5a) | AmberleafCotton | $2.99 / $3.99 | **да** | 5.0–5.7 | content | контуры выбора | avoid |
| [Selection outline highlights](https://www.fab.com/listings/c49fb9f8-5a3a-4651-bbbd-28d2d3cd0d91) | Construct Games | $3.99 / $9.99 | **да** | 5.1–5.4 | content | обводка | avoid |
| [Highlight & outline Post-Process](https://www.fab.com/listings/c603ad45-c9b0-4f9a-8abe-cd0a9e27e716) | Aukke Production | $9.99 / $19.99 | **да** | 5.3–5.8 | content | обводка PP | avoid |
| [Local Outlines](https://www.fab.com/listings/8d7a85c6-8ff6-4bc0-952c-b1fec05d15e5) | Luna Joy | $9.99 | **да** | 4.22–5.8 | content | обводка декалями | avoid |
| [OutlineMaker](https://www.fab.com/listings/7be55587-5fd1-4a31-9162-004593a0cb61) | Francesco Desogus | $14.99 / $19.99 | **да** | 4.19–5.8 | content | обводка | avoid |
| [Eroding Circle Niagara](https://www.fab.com/listings/2e438fb0-b962-4f4f-83a5-dd6c72053b48) | semko | $0 / $0.99 | **да** | 5.7–5.8 | content | круг | avoid |
| [Scan Grid Effect](https://www.fab.com/listings/060f0bcd-9fa2-4563-a992-b632931cd637) | Studio Cloe | $24.99 / $44.99 | **да** | 5.1–5.8 | content | скан-сетка | avoid |
| [Zero Aliasing Procedural Grid](https://www.fab.com/listings/10431a22-59a3-4702-866a-63c5fd2a432f) | Two Bit Studios | $14.99 / $29.99 | **да** | 5.0–5.8 | content | сетка-материал | avoid |
| [Dynamic Navigation Arrows](https://www.fab.com/listings/a11e7bbc-aecd-4089-99cf-3a41bf410f2f) | Pieria Software | $1.99 / $3.99 | **да** | 5.0–5.8 | content | стрелки | avoid |
| [DzX Radial Menu - UMG](https://www.fab.com/listings/d3b25ec5-7ef1-4422-a8e6-6f15b066f0b6) | IgorLekic | $0 | **да** | 4.23–5.8 | code plugin | радиальное меню | avoid |
| [Generic Radial Menus v2.0](https://www.fab.com/listings/a01c3623-d62d-4de1-bffb-9696943249c9) | PolyHavoc | $19.99 / $29.99 | **да** | 4.19–5.8 | content | радиальное меню | avoid |
| [UI Effect Function Library](https://www.fab.com/listings/00621b21-3d59-422e-8bf0-cac99bb01f2b) | UI Effect Fantasy | $0 | **да** | 5.0–5.8 | code plugin | UI-эффекты | avoid |
| [Stylized RPG Cursors](https://www.fab.com/listings/5dce0c7e-9dfc-422b-9319-29e20c7de60e) | Lid Games | $9.99 / $29.99 | **да** | 4.27–5.7 | content | курсоры | avoid |
| [Fantasy RPG Cursors](https://www.fab.com/listings/370b30f9-52a0-4015-85ad-bdcb1f6b4ec9) | Leonid Deburger | $9.99 | **да** | 4.18–5.4 | content | курсоры | avoid |
| [Anime Stylized VFX](https://www.fab.com/listings/d85dee78-9584-4b4b-a3b7-4b96de33c2b8) | Vefects | $52.99 / $99.99 | **да** | 4.27–5.8 | content | VFX | avoid |
| [Stylized Toon VFX](https://www.fab.com/listings/21554aed-65d3-4793-aa30-d17ac583fc38) | Hovl Studio | $24.99 / $28.99 | **да** | 4.25–5.8 | content | VFX | avoid |
| [UI Material Lab](https://www.fab.com/listings/69680f34-e5d2-44e6-b023-f054bbf629eb) | Epic Education | $0 | **да** | 5.1–5.5 | project | UI-материалы | avoid (только ручной референс) |
| [Niagara Examples Pack](https://www.fab.com/listings/0e188eca-4e54-4fb2-a9ed-d8b8a565e600) | Epic Games | $0 | **да** | 5.7 | content | примеры Niagara | avoid (только ручной референс) |
| [Lyra Starter Game](https://www.fab.com/listings/93faede1-4434-47c0-85f1-bf27c0820ad0) / [Cropout](https://www.fab.com/listings/bd733d81-7c29-44fe-b53f-65b14d06a9e2) / [City Sample](https://www.fab.com/listings/4898e707-7855-404b-af0e-a505ee690e68) | Epic Games | $0 | **да** | 5.0–5.8 | project | CommonUI, top-down ввод | avoid (только ручной референс) |

## 8. Как проверять кандидатов с вердиктом evaluate

1. **Перед добавлением в библиотеку.** Пользователь открывает листинг и сверяет:
   - флаг NoAI;
   - цену тира Personal;
   - «Supported Engine Versions».

   Добавление в библиотеку означает принятие лицензии (`fab-free-assets-research-2026-10-01.md`, раздел 5). Это действие пользователя.
2. **Спайк — не дольше дня на кандидата.** Делаем на ветке или в worktree против своей реализации из §2. Критерии:
   - стоимость кадра на эталоне High по `render_bench.py`;
   - читаемость на K1/K2;
   - FX: CPU + детерминизм, без Light renderer (`ue_import_fab_fx.py`);
   - работает на графовой доске (точки и связи), а не только на сетке.
3. **Если берём.** Строка в `CREDITS-fab.md` и в реестре THIRD_PARTY_NOTICES (`18-...-decisions.md:23`). Пак — в gitignored `Content/<Pack>/`, производные копии — в своих папках, как в `ue_import_fab_fx.py`.

## 9. Решения за пользователем

- **D-11:** оставить чистое скольжение (уровень 0)? Или разрешить процедурный «подскок миниатюры» (уровень 1, D-11 не меняется)? Или нужен скелетный клип шага (уровень 2, D-11 меняется)? Рекомендация исследователя — уровень 1.
- **Покупки до $100** в общей сумме по четырём кандидатам evaluate. По standing-делегированию «паки Fab выбираю сам» оркестратор может решить сам. Но оплату и добавление в библиотеку делает только пользователь.
- **Epic-сэмплы как ручной референс UX.** Cropout (top-down ввод, CommonUI) и Lyra полезны только пользователю, агентам их не подавать.

## 10. Риски

| Риск | Чем закрыт |
|---|---|
| NoAI-ассет случайно попадает в кадры ревью | брать только паки без NoAI; список `NOAI_PACKS` в `ue_import_fab_fx.py` расширять при каждом новом паке |
| Платный плагин не собирается под 5.8 или ломается при апдейте | у кандидатов 5.8 заявлена, но сборка не проверялась; спайк до серийного использования; code plugin — копия в `Plugins/` с фиксированной версией |
| FX тянет свет или GPU сверх бюджета 60/30 FPS | правила FX §1; замер `render_bench.py` |
| Клипы KayKit/UAL плохо ложатся на позу миниатюры (rest ≠ T-поза) | Retarget Pose по `RIG-CONTRACT.md:82`; новая карта в `retarget_maps`; `validate_clip.py` |
| Клиент начинает «решать» ход сам (тулкиты с pathfinding) | вердикт avoid для всех тактических тулкитов; путь и достижимость берём из сервера/BFS-подсказки TASK-027 |
| Данные устареют (цены, версии, NoAI меняются) | дата проверки 2026-10-03; перед покупкой — повторная сверка листинга |

## 11. Источники

Репозиторий: все ссылки вида `путь:строка` выше. Метод, сырые карточки и непроверенное — [_research/R5-fab-libraries.md](_research/R5-fab-libraries.md).

Внешние источники, доступ 2026-10-03:
- Fab, публичный JSON поиска `https://www.fab.com/i/listings/search?q=…` и карточки `https://www.fab.com/i/listings/<uid>` (листинги по ссылкам в таблицах);
- [Epic Content License Agreement](https://www.unrealengine.com/eula/content) — формулировки про NoAI и UE-Only по выдаче поиска, полный текст не открывался;
- [Epic tech-blog: GASP для UE 5.8](https://www.unrealengine.com/tech-blog/download-the-latest-game-animation-sample-project-now-updated-for-ue-5-8);
- [KayKit Character Animations](https://kaylousberg.itch.io/kaykit-character-animations);
- [Quaternius UAL](https://quaternius.com/packs/universalanimationlibrary.html);
- [Dn2 Game Grids](https://dn2.itch.io/unreal-engine-game-grids);
- [Adobe Mixamo FAQ](https://community.adobe.com/questions-696/mixamo-faq-licensing-royalties-ownership-eula-and-tos-589400);
- [Cropout, блог Epic](https://www.unrealengine.com/blog/cropout-casual-rts-game-sample-project);
- доки Epic: [Spline Components](https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-spline-components-overview-in-unreal-engine), [IK Rig Retargeting](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine).

## 12. Правки ведущего автора пакета (2026-10-03)

- Добавлена ссылка на пакет в шапке.
- §1, строка «Тонкий клиент»: было «правила, достижимость и путь считает сервер, клиент только показывает». Исправлено:
  сервер не отдаёт достижимые клетки и путь, клиент считает их сам как подсказку (`R1` §1 п. 4; `S08BoardModel.h:207-221`).
  Вывод раздела (тулкиты со своим pathfinding не подходят) не меняется.
- 2026-10-03, ревью v2 (C-19, F-13 — [09](09-review-log.md)): «Коротко» п. 1, §2 (строки «Достижимые клетки»,
  «Превью пути», «Подтверждение и отмена», «Ход соперника»), §3 №1 и §6 (строки «Подсветка достижимых точек»,
  «Стрелка пути», «Ход соперника, след», «Радиальное меню») приведены к решениям пакета: CommonUI заменён на UMG-гибрид
  (U-4, CommonUI в проекте не включён); подсветка — ISM сразу (MS-D-12, X-09), декали отклонены; линия пути — ISM
  прямых сегментов (04 §6.1). Вердикты кандидатов Fab не меняются; вывод «не брать Narrative Common UI» остаётся.
