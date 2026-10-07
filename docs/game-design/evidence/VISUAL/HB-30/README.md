# HB-30 — карты боя у краёв: UUmHudCombatEdge ×2, лента роли, слот защиты, кнопки защиты (шаг H9)

VS-3, шаг U4, 2026-10-07, ветка `feat/visual-vs3` (worktree `C:/tmp/wt-visual`). Карточка — `hud.csv` HB-30; 04 §2.7,
§4.3, §5.2 H9, §7.1; ВР-H04, ВР-78; принятый макет HB-29 `art/imagegen/hud-combat-v1-codex/` (ВР-VS2-HB29-01…15,
«Дельта 04»). Таймер — [HB-31](../HB-31/README.md), переворот и уход — [HB-32](../HB-32/README.md), центр —
[HB-33](../HB-33/README.md), основа экранов — [SC-01](../SC-01/README.md). Общие для H9 проверки, листы и решения — здесь.

**Статус:** блок, WBP, адаптер, трассы, гейт приватности, тесты и листы галереи готовы. Код — коммит `05c3e3dd` (H9 и
SC-01 одним коммитом: общие файлы подключения). Живой прогон боя двух клиентов (`run-combat-demo`, обе доски, набор C) —
шаг «Кадры» VS-3 (одна упаковка; в этом шаге стенды S09 / S10 были выключены, упаковка запрещена). Приёмка — «по
делегированию», в едином проходе ревью VS-3.
**Откат:** `-S08SlateHud=combat` — края, центр и окно защиты снова Slate (`BuildCombatStageHud`, командная панель);
трасса `HUD-COMBAT-UMG impl=slate`. `-S08CrossLegacy` — текстовый X вместо штампа v3.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. `UUmHudCombatEdge`, свойство `Side` (Own — слева, Opp — справа, от роли не зависит) | `S08/UI/UmHudCombatEdge.{h,cpp}`. BindWidget `Card` (`UUmCardWidget`, показ `Combat` 230×319 / `ClassSCombat` 150×208), `Ribbon`, `RoleIcon`, `RoleText`, `TimerText`, `TimerBar`, `DefendButton`, `NoDefenseButton` (`UUmButton`), `Stamp` (`US08AnimatedIconWidget` marker-x-stamp 64); необязательные — пустой слот (`SlotUnderlay`, `SlotFrame`, `SlotGlyph`, `SlotText`), `CaptionPlate` / `CaptionText`, `TeamChip`, `TimerTrack`, `WarnEdge`, `WarnIcon`, `StampText`. Вход — `ApplyModel(FUmCombatEdgeModel)`; модель собирает `FUmCombatBlocks::Gather` из `FS08CombatInfo` (снимок), `FS09CombatReveal` / `FS09CombatStage` (постановка), черновика защиты (`CommandUi.DefenseCardId`). `/Game/S08/UI/Hud/WBP_UI_HUD_COMBAT_EDGE` сгенерирован из того же дерева (`ue_author_um_hud.py`, `UM_HUD_WBP_OVERWRITE=0`, прочие WBP не тронуты), `git add -f`. |
| 2. Слот защиты (SD-04) | `shield` — пустая рамка CP-13 (`card.frame.idle`) на `card.navy`, `action-defense` 64 su в верхней половине (y 0,27 высоты), «Карта не выбрана» (`hud.combat.slot.empty`, type.body, text.secondary) ниже; `chosen` — рубашка героя-владельца колоды + «Карта выбрана» (`hud.combat.slot.chosen`) на своей плашке 24 su в 4 su над картой (HB-29 SLOT-CAPTION); `nodefense` — пустая рамка и штамп `marker-x-stamp` 64 по центру, «appear» 200 мс один раз на бой (трасса `HUD-STAMP no-defense seq= side= icon=`; автоклиент снимает кадр штампа, как раньше Slate). |
| 3. Лента | панель `panel` под картой (зазор 4): диск типа 24 su (`action-attack` / `action-defense`), «АТАКА · Merlin» / «ЗАЩИТА · Medusa» (`hud.combat.role.*`, type.tag 14, text.primary) — перенос в две строки, не обрезка (класс S: «ЗАЩИТА ·» / «Medusa», лента 40 su); чип команды 24 su справа — v3 `team-chip-p1` (круг) / `-p2` (шестигранник), цвет `team.p1.screen` / `team.p2.screen` (IC-44 / IC-45, ВР-78). Имена — как в данных (`Medusa`, `King Arthur`, `Merlin`). |
| 4. Кнопки только у защитника | «ЗАЩИТИТЬСЯ» — главная (Enter), «БЕЗ ЗАЩИТЫ» — обычная (N), по одной в строку в прямоугольнике `Defend` раскладки. Причины: `why.defense.pick` (карта не выбрана, новый ключ ВР-VS3-51), `why.defense.none`, `why.deadline.passed` (после дедлайна обе), занятость (`HudBusyReason`); нажатие — арбитр (`hud.combat.defend` / `hud.combat.no.defense`), ответ в кадре отпускания: `ConfirmCombat` / `NoDefenseCommand`. |
| 5. ПКМ по карте — инспектор | `UUmCardWidget::SetOnInspect` → `InspectCard` показанного лица (Slate-инспектор до H13); рубашка соперника не открывает ничего. |
| 6. `SHOT widget` | `SHOT widget id=UI-HUD-COMBAT-EDGE impl=umg state=back\|shield\|chosen\|reveal\|nodefense fighter=own\|opp bbox=… role=attack\|defense face=0\|1 class=L\|S card=230x319 ribbon=230x28 rows=1 timer=<n>\|- timerState=… buttons=0\|1 defend=on\|off:<why> stamp=0\|1 leave=0\|1 seq=<n>` — без имени и id карты. |
| 7. Приватность | лицо карты соперника входит в модель только из публичных данных (раскрытый `combatInfo` окна разрешения или закрывающий снимок постановки); до этого в модели только стабильный id боя `combat.<key>.attack\|defense`, без имени и id каталога; виджет карты лицом вниз хранит только этот id (QA-005). `hud_contract.py check-trace`: строка `fighter=opp face=1` не в `state=reveal` — ошибка «приватность» (pytest `test_check_trace_combat_privacy_hb30`). |
| 8. Slate-панели «ATTACK - Merlin …» — только `-S08SlateHud=combat` | `BuildCombatStageHud` (+4 строки): при UMG-краях и центре Slate-края и строка счёта пусты — и с `-S09Markers` тоже. Блок окна защиты командной панели («YOU ARE ATTACKED …») не рисуется, пока окно на UMG-крае, кроме слоя гейтов `-S09Markers` (маркеры `#7CFC00` и др. — только там, как было, ВР-VS3-61). |
| 9. Тесты | `Unmatched.S08.Hud.CombatEdge.Tree`, `.Sides`, `.Slot`, `.Privacy` (+ `.Timer`, `.Flip`, `.Leave` — HB-31 / HB-32) в `S08/UI/UmHudCombatTests.cpp`. |

Сторона игрового режима — `FUmCombatBlocks` (`S08/UI/UmHudCombatBlocks.{h,cpp}`, без мира): строит оба края и центр (или
пишет откат), каждый кадр собирает модели из `FUmCombatInput` (снимок, команда, постановка, часы), держит ключ боя
(открытый бой → его постановка — один ключ, новый CUE-008 — новый), объявление 600 мс × скорость (ВР-VS3-59), уход
(HB-32). Точки подключения (04 §5.1): `S08FlowGameModeUmHud.cpp` (+248: сборка с колбэками, вход обновления, якорь
дедлайна, трассы, слой панели колоды, баннер, `-S08ScreenShots`, лист галереи), `S08FlowGameMode.cpp` +10 / −2
(`BuildCombatStageHud`, отмена атаки в `StartCombatStage`, условие блока защиты, строки COMBAT RESULT), `S08FlowGameMode.h`
+12, S09: `S09CombatStage.h` +1 (`bAttackCardCancelled`), `S09CombatEffectLog.{h,cpp}` +2 (`bPrintedText`),
`S09HudModel.{h,cpp}` +12 (`EffectText` — напечатанные эффекты карты).

## Раскладка (HB-29 «Дельта 04», ВР-VS3-57)

| Холст | Своя карта | Чужая карта | Лента своя (с таймером) | Кнопки | `COMBAT-L` / `COMBAT-R` / `Defend` раскладки |
|---|---|---|---|---|---|
| 1080p 100 % (L) | (24, 360, 230, 319) | (1666, 360, 230, 319) | (24, 683, 230, 28 / 56) | (32, 747, 230, 48), (32, 803, 230, 48) | 230×379 / 230×351 / (32, 747, 230, 104) |
| 720p 100 % (L, 1706,7×960) | (24, 360) | (1452,67, 360) | то же | (32, 112), (32, 168) — над картой | то же, `Defend` (32, 112, 230, 104) |
| 1080p 150 % (S, 1280×720) | (16, 240, 150, 208) | (1114, 240) | (16, 452, 150, 24–40 / 68) | (32, 112, 150, 40), (32, 160, 150, 40) | 150×280 / 150×252 / (32, 112, 150, 88) |
| 720p 150 % (S, 1137,8×640) | (16, 240) | (971,78, 240) | то же | то же | то же |

Плашка «Карта выбрана» — в 28 su над картой (L 332, S 212); в прямоугольник гейта `COMBAT-L` не входит (поле от неё
далеко: x 24…254). Слот GAME левого края — столбец плашка…кнопки (`UmGameHudSlots::SlotRect`). `HUD-LAYOUT
overlapField=0` на обеих досках во всех четырёх холстах (тест `Unmatched.S08.Hud.Root.Layout` с FIELD камеры K1).

## Решения по делегированию (серия ВР-VS3, шаг U4)

| № | Решение | Почему |
|---|---|---|
| ВР-VS3-51 | Новая причина `why.defense.pick` «Выберите карту защиты в руке» / «Pick a defense card in your hand» для недоступной «Защититься» до выбора карты; 02 §4.2, `why-reasons.json`, `S08WhyText`, ST_Why | ВР-VS2-HB29-06 делает главную кнопку недоступной без карты, а 04 §3.1 требует причину у каждой недоступной кнопки; ключи 04 (`why.choice.required` — буст-выбор) этого не говорят |
| ВР-VS3-57 | Прямоугольники боя — HB-29 «Дельта 04»: `COMBAT-L` выше на ленту с таймером (L 379, S 280), `COMBAT-R` — S 252 (лента в две строки), `Defend` — две кнопки в строку при x 32: 1080p под лентой (y 747), 720p и класс S — слева сверху (y 112); плашка «Карта выбрана» — 28 su над картой | макет принят с этими числами (ВР-VS2-HB29-11); прежние 04 (719, одна строка) не вмещают строку таймера, на 720p кнопки под лентой ушли бы на PANEL-LOC (y 800) |
| ВР-VS3-59 | Объявление CUE-008: первые 600 мс × скорость нового боя виден только край атакующего с лентой; слот, таймер, кнопки и «Ждём защиту…» — после. Slate-блок окна защиты отдаётся UMG с кадра CUE-008 (без мигания) | HB-29 «declare» и шкала 04 §2.7 (объявление → окно защиты) |
| ВР-VS3-60 | Состояние трассы `back` — закрытая карта до раскрытия; лицо (`face=1`) только на собственном крае владельца (своя карта атаки у атакующего — лицом, ВР-VS2-HB29-07). Гейт: `fighter=opp face=1` — только в `state=reveal` | список состояний 04 §7.1 не знает «своя открытая до раскрытия»; приватность проверяема одним правилом |
| ВР-VS3-61 | Slate-края и строка счёта не рисуются при UMG-бое и под `-S09Markers`; блок окна защиты и строки «COMBAT RESULT» командной панели остаются только для слоя гейтов `-S09Markers` | карточка: Slate-панели — только `-S08SlateHud=combat`, маркеры — только `-S09Markers`; пиксельные гейты S09 идут с маркерами |
| ВР-VS3-62 | Лист блока — галерея движка `-S08IconGallery -S08IconGalleryCombat=marmoreal\|sarpedon`: настоящие `FUmCombatBlocks` (оба края и центр в `UUmGameHud` на раскладке окна с FIELD K1) поверх кадра bench K1 доски как картинки, матрица HB-29 (A, B, C прогона I), строки эффектов — тестовый набор HB-29 (`facts.json`), скорость 0 и замороженные часы (каждый переворот и штамп — в конце) | шаг без упаковки; так макет и движок сравниваются кадр к кадру; живые кадры — шаг «Кадры» |
| ВР-VS3-65 | Чип «+N» на карте атаки — только когда число публично: своя атака до раскрытия (`combatInfo.boostValue`), обе после раскрытия (атака − напечатанное значение); скрытый буст соперника не намекается | приватность; в макете HB-29 буста нет |

Решения HB-31…HB-33 и SC-01 — ВР-VS3-49, -50, -52…-56, -58, -63, -64, -66, -67 в их README.

## Проверки

- Сборка UnmatchedEditor в worktree — `Result: Succeeded` (`C:/tmp/visual/VS3-U4/build-7.log`; после правки часов листа
  галереи — `build-8.log`; ошибок и новых предупреждений C нет). Игровая цель `Unmatched Win64 Development` — `Succeeded` (`build-game-1.log`; ловушка C2039 не
  сработала: новые тесты берут `EnableGameLocalizationPreview` только `WITH_EDITOR`).
- UE: новые тесты — 12 из 12 (`ue-tests-new-2.log`); `Unmatched.S08.Hud + S09.HudPress + S09.Combat` — 89 из 89
  (`ue-tests-hud-1.log`); полный прогон `Unmatched.S08 + S09 + S10` — см. HB-33 «Проверки» (`ue-tests-full-2.log`).
  `Refresh` обоих краёв и центра на кадр постановки: p50 0,0017 / p95 0,0018 мс (бюджет HB-30 0,08, HB-33 0,05 мс GT p95).
- `hud_contract.py validate` — PASS (G-TOKENS: литералов цвета в `S08/UI` нет). pytest `tools/s08/hud_contract` +
  `tools/s08/cue_contract` — 131 passed, 2 failed — прежние `test_hud_strings_build` (`hud.log.turn` в 04 §2.10, будущий
  ключ HB-38, VS-4; см. HB-24 / HB-28), не этот шаг. Новый тест `test_check_trace_combat_privacy_hb30` — passed.
- G-WIDGET (`check-trace`) — PASS на трассах всех листов галереи (см. «Листы»).
- WBP: `C:/tmp/visual/VS3-U4/um-hud-wbp-report.json` — `WBP_UI_HUD_COMBAT_EDGE`, `WBP_UI_HUD_COMBAT`,
  `WBP_UmConfirmDialog` created, up-to-date, родители верны; остальные 17 WBP не перезаписаны.

## Листы

Галерея (`C:/tmp/visual/VS3-U4/run-combat-gallery.ps1`, `run-combat-batch.ps1`; editor `-game`, один клиент, `t.MaxFPS 30`,
`-RenderOffScreen`; клиентов ZCode и других процессов UE в это время не было). Состояния HB-29 по секундам часов:
Marmoreal (владелец — игрок Medusa) 11: declare, defense-window, timer-warning, defense-chosen, reveal, effects, slam, hit,
effects-long, holds, nodefense; Sarpedon (владелец — игрок King Arthur) 10 (без timer-warning). Холсты 1080p 100 / 150 %,
720p 100 / 150 %; ещё Marmoreal 1080p 100 % с `-S08ReducedMotion`. Листы — `compose.py`: контакт всех состояний (кадры в
½ / ¾) и вырезки краёв и центра в родных пикселях; цвет, серый Rec.709, на 1080p 100 % ещё дейтеранопия.

- В git (без картинки доски и без сканов карт: `-S08IconGalleryHandPlain -S08CardArtLegacy`, фон `panel.bg.inset`, лица
  карт — запасной вид; проверяет раскладку, ленту, слот, таймер, кнопки и центр):
  `marm-1080-100-plain-contact-colour.png` (`a55c79e9…`), `-grey.png` (`6d1314a9…`),
  `marm-720-150-plain-contact-colour.png` (`4a2966b6…`), `-grey.png` (`eb77c54c…`) — в этой папке.
- Вне git (кадр K1 доски и сканы карт — `scraped-data/`, gitignored): `scraped-data/derived/visual-evidence/HB-30/` в
  worktree — `<run>-contact-{colour,grey}.png` и `<run>-crops-{colour,grey}.png` для `marm|sarp-1080-100|1080-150|720-100|720-150`,
  на 1080p 100 % ещё `-deut`; `marm-1080-100-reduced-*`; листы модали SC-01 `confirm-*`. 50 листов, sha256 каждого —
  [`sheets-sha.json`](sheets-sha.json) (копия индекса). Кадры прогонов — `C:/tmp/visual/VS3-U4/gallery/<run>/`
  (`icon-gallery-normal-<мс>.png`, `trace.log`).
- Прогон batch-4 после сборки build-8 (последняя правка — часы листа: база и заморозка + 400 мс, дедлайн 30,4 / 9,9 с,
  чтобы знак warning доиграл «appear» к кадру): 11 прогонов, все `exit=0`, 11 / 10 кадров; `check-trace` — PASS на всех
  16 трассах (бой 72 строки SHOT Marmoreal / 67 Sarpedon, модаль 5).

Что видно (Read: все контактные листы цветом, серые 1080p 100 % обеих досок, отдельные кадры timer-warning, slam,
effects-long, nodefense Marmoreal 1080p 100 %, timer-warning 1080p 150 %, effects-long 720p 150 %, defense-window Sarpedon
1080p 100 %):

- Состояния совпадают с матрицей HB-29 на обеих досках: declare — только правый край атакующего (рубашка Merlin,
  лента «АТАКА · Merlin»); defense-window — слот «Карта не выбрана» со щитом, лента «ЗАЩИТА · Medusa», «30 с» и полная
  полоса, «ЗАЩИТИТЬСЯ» недоступна (серая), «БЕЗ ЗАЩИТЫ» доступна; timer-warning — «10 с», треть полосы, оранжевая кромка
  `state.warning` и треугольник `state-warning` (в сером видны: кромка светлее ленты, знак — форма); defense-chosen —
  рубашка Medusa и плашка «Карта выбрана», главная кнопка жёлтая; reveal — оба лица («Уловка» / «Стремительный удар»);
  effects — центр с текущей «Уловка» (полоса слева) и Swift Strike с X; slam / hit — «3 : 2», «Merlin побеждает», те же
  две строки; effects-long — 3 строки, «Крылатое буйство» в 2 ряда с «…», чип «ещё 1» (S: 2 строки, «ещё 2»); holds —
  «3 : 3», «Защита держит», «Рывок» в 2 ряда; nodefense — правый край: пустая рамка с X, лента «ЗАЩИТА · King Arthur».
- Sarpedon (владелец — атакующий): у атакующего в окне защиты — «Ждём защиту…» в центре, свой край лицом, у соперника
  слот без кнопок; карты соперника рубашкой до reveal.
- Класс S (1080p 150 %, 720p 150 %): кнопки над картой слева, лента «ЗАЩИТА ·» / «Medusa» в две строки, таймер под ней;
  центр 480 su временно закрывает верхний ряд клеток (исключение 04 §1.6). 720p 100 %: кнопки над картой (ВР-VS3-57).
- Reduced motion: кадры в конце движения те же, вырезки краёв и центра побайтно равны обычному прогону (sha
  `72b55e45…` у обоих) — reduced меняет путь, а не итог.
- Строки эффектов Swift Strike — английские (в данных бэкенда RU нет, ВР-VS3-53); «Уловка», «Крылатое буйство» — RU
  из тестового набора HB-29 `facts.json`.

## Что не сделано в этом шаге

- Живой бой двух клиентов (`tools/s09/run-combat-demo.ps1`, обе доски, оба клиента; набор C 1080p 100 / 150 %, 720p
  100 / 150 %) и `check-trace` живых трасс — шаг «Кадры» (одна упаковка). Стенды S09 / S10 в этом шаге были выключены,
  учётные данные демо-аккаунтов — переменные окружения прогона, не файлы проекта.
- «−N» над целью — мировой слой (HB-44 / HB-46, VS-4); в живой игре — нынешнее число урона W5b-R.
- Ключ `hud.log.turn` (HB-38) — `hud_strings_build.py check` падает на нём до VS-4; строки этого шага собраны тем же
  `build` без этой проверки (ВР-VS3-67, SC-01).

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/HB-30/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: окно защиты у защитника (слот «Карта не выбрана» со щитом, лента «ЗАЩИТА · …», таймер, «ЗАЩИТИТЬСЯ» серая до выбора, «БЕЗ ЗАЩИТЫ»), у атакующего — своя карта лицом, «Ждём защиту…», раскрытие обоих лиц, штамп X «нет защиты» — обе доски, 1080p 100 / 150 / 75 %, 720p 100 / 150 %. Трассы: `back`, `shield`, `chosen`, `reveal`, `nodefense` на обеих сторонах; приватность — 0 ошибок `check-trace`, в кадрах до раскрытия 0 пикселей раскрытия.

**Вердикт: художественно принято, по делегированию (2026-10-07)**, с замечанием: в классе S (1080p 150 %) Slate-блок окна разрешения («COMBAT RESOLVE WINDOW … BOOST_CHOICE») закрывает верх своей карты боя (VS-4, открыто п. 3 VS-3).
