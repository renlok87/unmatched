# HB-28 — панель колоды: UUmHudDeckPanel своя и соперника, браузер сброса внутри (шаг H8)

VS-3, шаг U3, 2026-10-07, ветка `feat/visual-vs3` (worktree `C:/tmp/wt-visual`). Карточка — `hud.csv` HB-28; 04 §2.9,
§1.6, §3.3, §6.2, §7.1; принятый макет HB-26 `art/imagegen/hud-decks-v1-codex/` (D1–D14, ВР-VS2-HB26-01…13, «Дельта 04»).
Фишки — [HB-27](../HB-27/README.md), скелет загрузки — [HB-47](../HB-47/README.md).

**Статус:** блок, WBP, трассы, тесты, лист галереи и живая проверка на одном клиенте готовы. Код — коммит `4a3ca23b`
(вместе с HB-27). Приёмочные кадры набора E в партии (обе доски; 1080p 100 %, 720p 100 и 150 %) — шаг «Кадры» VS-3
(одна упаковка). Приёмка — «по делегированию», в едином проходе ревью VS-3.
**Откат:** `-S08SlateHud=deckpanel` — прежняя Slate-панель `S08FlowGameModeDeckPanel.cpp` и Slate-браузер сброса (D);
трасса `HUD-DECKPANEL-UMG impl=slate`. Проверено на живом клиенте: английская панель «YOUR DECK · Medusa» на месте
(`bench-own-1080-100-slate`).

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. `UUmHudDeckPanel`, BindWidget `Title`, `Tabs` (`TabOwn`, `TabOpp` — `UUmButton`), `Summary`, `Rows` (`UScrollBox`, пул `UUmDeckRow`), `CloseButton` | `S08/UI/UmHudDeckPanel.{h,cpp}`. Дерево: `Root` (Canvas) > `Panel` (T_Skin_Panel, отступ 12) > `Body` (Canvas) > `Title`, `Tabs`, `CloseButton`, `Summary`, `Backs`, `FilterButton`, `Rows`, `Track`, `Thumb`, `Skeleton`, `ErrorText`, `RetryButton`. Вход — `ApplyModel(FUmDeckPanelModel)`; модель собирает `UmHudDeckPanel::Gather` из `FS09DeckPanelModel` (S09, без правок) и `FS09DeckPanelView` (открытая сторона, прозрачность). `/Game/S08/UI/Hud/WBP_UI_HUD_DECKPANEL` сгенерирован из того же дерева (`ue_author_um_hud.py`, `UM_HUD_WBP_OVERWRITE=0`, прочие WBP не тронуты), `git add -f`. |
| 2. `UUmDeckRow` | `S08/UI/UmDeckRow.{h,cpp}`: строка 48 su на `panel.bg.inset` с линией `panel.divider` 1 su; диск типа v3 24 su в (4, 3) — `action-attack` / `-defense` / `-maneuver` (универсальная) / `-scheme`; «×N» 20 su; имя 20 su Bold Condensed, не капс; значения справа (6 su) «A2 B4» / «D0 B2» / «V3 B1» / «B4» (ВР-HB14); у всех трёх одна базовая линия (верх прописной 20 su — 3 su от верха строки, ВР-VS2-HB26-12). Метки на второй строке (y 29): своя — «В руке n» (n > 0), «В сбросе n» (n > 0), «Осталось n» (всегда); соперника — только «В сбросе n». Бюджет имени D4: 20 su → 16 su → «…». Сортировка — тип (атака, защита, универсальная, схема), затем показанное имя (кодовые точки нижнего регистра). Наведение — `panel.bg.hover`. |
| 3. Браузер сброса Slate сливается сюда | фильтр «Только сброс» (`FilterButton`, Btn_Selected при включении). D и фишка сброса открывают панель на «Ваша» с фильтром, второе нажатие на том же виде закрывает; вкладки сохраняют фильтр — так видны оба публичных сброса, как в старом браузере (ВР-VS3-43). Slate-браузер остаётся только при `-S08SlateHud=deckpanel`. |
| 4. Якорь, класс S, скелет, закрытие | прямоугольники HB-26 «Дельта 04» в `FUmHudLayout`: L 1080p (1516, 268, 380, 644), L 720p (1346.67, 268, 336, 524), S 1080p 150 % (964, 120, 300, 472), S 720p 150 % (821.78, 120, 300, 392). Карточка называла 04 §1.6 (верх 248 / 168, 720p 340) — макет HB-26 их уточнил (верх под OPP-HAND + 8 и под PANEL-OPP + 8, 336 su — ВР-VS2-HB26-05 / -08); `UmHudTests` переведён на них. В S панель только для чтения лежит над OPP-HAND и краем поля (исключение 04 §1.6). До ответа `gameDeckLists` — 6 строк скелета (HB-47, через 300 мс). `CloseButton` — глиф `ui-close` 24 su в квадрате 32 su (IC-54), «Закрыть» — его подсказка (ВР-VS3-38). |
| 5. Клик по строке — инспектор | `HandleUmDeckRowInspect`: карта каталога строки (`FS09DeckRow::AsCardView`) в прежний Slate-инспектор до H13 (INSPECT, VS-4); Slate-боковая панель на время открытой панели сдвинута влево от неё на её ширину + 8 su (ВР-VS3-41); подпись источника — «deck». |
| 6. Строки | `hud.deckpanel.title.own` / `.title.opp`, `.tab.own`, `.tab.opp`, `.close` (подсказка), `.summary`, `.mark.hand`, `.mark.discard`, `.mark.left`, `.filter.discard` — из ST_Hud; «≈» перед устаревшим числом сводки — `hud.decks.stale`. Ошибка загрузки — `screens.boot.error.server` и `common.btn.retry` (новых ключей нет, ВР-VS3-39). |
| 7. `SHOT widget` | `SHOT widget id=UI-HUD-DECKPANEL impl=umg state=own\|opp … class= filter=0\|1 list=loaded\|loading\|failed rows= shown= rowsVisible= first= capacity= copies= deck= discard= hand= sumHand= sumDiscard= sumLeft= titleSu= titleLines= header= viewport= scroll= skeleton= alpha= open= bottom= pool=` — только числа, без имени и id карты. `HUD-LAYOUT` получил `deckpanel=(x,y,w,h) deckpanelBlocks=<px²> deckpanelTransient=<px²>`; `hud_contract.py check-trace` валит строку с `deckpanelBlocks > 0`. |
| 8. Slate-панель — только `-S08SlateHud=deckpanel` | `RebuildDeckPanelContent` и Slate-рамка панели не рисуются при UMG-панели (`S08FlowGameModeDeckPanel.cpp` +7). |
| 9. Тесты | `Unmatched.S08.Hud.DeckPanel.Rows` (Medusa 11 / 30, King Arthur 16 / 30), `.AutoClose`, плюс `.Layout`, `.Tree`, `.Blocks` (`S08/UI/UmHudDeckPanelTests.cpp`). |

Сторона игрового режима — `FUmDeckBlocks` (`S08/UI/UmHudDeckBlocks.{h,cpp}`): строит оба блока (или пишет откат),
кормит их снимком и списками, ведёт вид панели каждый кадр (80 / 150 мс `FS09DeckPanelView`, reduced — 100 мс) и фильтр.
Точки подключения (04 §5.1): `S08FlowGameModeUmHud.cpp` (+216: сборка с колбэками нажатий, вход обновления, D / фишка
сброса, строка → инспектор, курсор над панелью, слои ВР-VS3-41 / -42, трассы, лист галереи), `S08FlowGameModeDeckPanel.cpp`
+7, `S08FlowGameModeCardSlot.cpp` +1 / −1, `S08FlowGameMode.cpp` +14 / −8 (D, кнопки Slate под `decks`, подпись источника
инспектора), `S08FlowGameMode.h` +12. Общий виджет кнопки: `FUmButtonModel::PadXSu` (вкладки — текст + 12 su, фильтр —
текст + 16 su, как в HB-26; по умолчанию `space.m` без изменений).

Автозакрытие — прежнее `S09DeckPanel::InputDemandKey` (начало моего хода, моё окно защиты, мой выбор, мой сброс, конец
игры): трасса `DECK panel close … why=input:turn|defend|…` и тест `.AutoClose`.

## Числа (сверены с HB-26 `panel_geometry`)

| Холст | Сторона | Шапка, su | Окно, su | Видно / строк | Заголовок |
|---|---|---|---|---|---|
| Marmoreal 1080p 100 % | своя Medusa | 155.6 | 432 | 9 / 11 | 28 su, 1 строка |
| Marmoreal 1080p 100 % | соперник King Arthur | 221.2 | 384 | 8 / 16 | 28 su, 2 строки («Колода соперника ·» / «King Arthur») |
| Marmoreal 720p 150 % | своя | 155.6 | 192 | 4 / 11 | 1 строка |
| Marmoreal 720p 150 % | соперник | 221.2 | 144 | 3 / 16 | 2 строки |
| Sarpedon 1080p 150 % | свой King Arthur | 189.2 | 240 | 5 / 16 | 2 строки |
| Sarpedon 720p 100 % | свой | 155.6 | 336 | 7 / 16 | 1 строка |

Суммы меток равны сводке: Marmoreal своя — в руке 5, в сбросе 2, осталось 23; Sarpedon свой — 3 / 2 / 25 (трассы
`sumHand / sumDiscard / sumLeft`, тест `.Rows`). Бюджет имени: на 720p и 1080p 150 % «The Hounds of Mighty Zeus» →
16 su «The Hounds of Might…», «Aid the Chosen One» / «The Aid of Morgana» → 16 su целиком; EN 1080p 100 % — всё 20 su.
Бюджет: полная пересборка модели p95 0,26 мс (кадр открытия ≤ 2 мс); открытая панель на кадр p95 0,0005 мс (≤ 0,05).

## Решения по делегированию (шаг U3, «Все решения принимай», 2026-10-06)

| № | Решение | Почему |
|---|---|---|
| ВР-VS3-36 | Имя строки — из данных: `nameRu` в RU-сборке, если не пусто, иначе `name`. В БД `Card.nameRu` равен EN у обеих колод (ВР-VS2-02), поэтому живая панель показывает EN-названия и у Medusa, а не i18n RU скрапа, как макет HB-26. Когда бэкенд получит RU-названия, панель их возьмёт | 04 §6.1 / HB-28 do 2: имена карт — данные, не таблицы строк; скрап в клиент не идёт |
| ВР-VS3-37 | Низ панели поднимается на 8 su над нарисованной рукой (карты и подпись), если та заходит под панель: в L 1080p и 75 % веер 8+ карт доходит до x 1540 при панели от 1516; окно теряет строку, панель не закрывает руку | HB-26 D8: в классе L панель не закрывает ни одного видимого блока; прямоугольник HAND макета — пять карт по центру, а не весь коридор |
| ВР-VS3-38 | Кнопка закрытия — глиф `ui-close` 24 su в квадрате 32 su (IC-54), «Закрыть» — подсказка; вкладки как в HB-26 | карточка HB-28 do 4 прямо называет глиф; с текстовой кнопкой вкладки и «ЗАКРЫТЬ» не помещаются в 276 su класса S |
| ВР-VS3-39 | Список не загрузился — «Сервер недоступен» + «Повторить» (`EnsureDeckLists(true)`) вместо скелета | HB-47: спиннер / скелет без подписи дольше 10 с без ошибки не оставлять; ключи уже есть (BOOT) |
| ВР-VS3-40 | Reduced motion: закрытие панели за 100 мс (150 мс вида S09 пересчитаны), открытие 80 мс без изменений | карточка: «reduced — прозрачность ≤ 100» |
| ВР-VS3-41 | Строка открывает прежний Slate-инспектор (до H13); пока панель открыта, Slate-боковая панель сдвинута влево от неё на ширину + 8 su | иначе инспектор ложится под панель в правом верхнем углу |
| ВР-VS3-42 | При UMG-панели PANEL-OPP не гаснет никогда, OPP-HAND гаснет только в классе S, где панель лежит над ним (сужение ВР-VS2-71) | в классе L панель HB-26 начинается под OPP-HAND и ничего не закрывает: прятать портрет соперника незачем |
| ВР-VS3-43 | D и фишка сброса — панель «Ваша» с «Только сброс», повтор закрывает; K, фишка колоды, клик по портрету — без фильтра; переключение вкладок сохраняет фильтр | старый браузер показывал оба публичных сброса; новый открытый вид с K не должен наследовать фильтр |
| ВР-VS3-44 | Метки — скин Btn_Normal (тело `card.navy`, кромка `card.cream` 0,45, радиус 4), как нарисовал HB-26, а не токен-скин `chip` (тело `panel.bg.inset`) | на ячейке `panel.bg.inset` метка того же цвета держится одной кромкой; макет принят с navy |
| ВР-VS3-45 | Закрытые записи сброса (карта боя до раскрытия) и карты вне списка входят в сводку, но строки и метки не получают; верх сброса лицом вниз — рубашка | без лица их нельзя отнести к строке (QA-005), счёт — серверный |
| ВР-VS3-47 | Лист блока — галерея движка `-S08IconGallery -S08IconGalleryDecks=marmoreal\|sarpedon`: настоящие `UUmHudDecks` / `UUmHudDeckPanel` на раскладке окна с FIELD живой камеры поверх кадра bench K1 доски как картинки, момент прогона I из HB-26 (ВР-VS2-HB26-02), колоды — снимок content API S01. Живая проверка игрового режима — `-Bench -BenchDeckPanel` (инструмент DE-030) на Marmoreal | шаг без упаковки; приёмочные кадры — шаг «Кадры» |
| ВР-VS3-48 | `HUD-LAYOUT deckpanelBlocks` — пересечение прямоугольника панели с TOP, STATUS в две строки (78 su), BANNER, PANEL-LOC, PANEL-OPP, LOG, DECKS, ACTIONS (в L ещё OPP-HAND) — гейт `check-trace`; `deckpanelTransient` (S: OPP-HAND, CENTER, FIELD) — только замер | открытый пункт 3 VS-2: на 720p 150 % STATUS закрывал шапку; теперь верх панели 120 su, низ STATUS в две строки — 94 su (`deckpanelBlocks=0` на всех холстах) |

## Проверки

- Сборка UnmatchedEditor в worktree — `Result: Succeeded` (`C:/tmp/visual/VS3-U3/build-9.log`; новых предупреждений C
  нет, два прежних C4996 в `S08BoardActor.cpp`). Игровая цель `Unmatched Win64 Development` — `Succeeded`
  (`build-game-1.log`, ловушка C2039 не сработала: тесты берут `EnableGameLocalizationPreview` только `WITH_EDITOR`).
- UE: `Unmatched.S08 + S09 + S10` — 459 из 459 (`ue-tests-full-1.log`); после выноса `FUmDeckBlocks` —
  `Unmatched.S08.Hud + S09.HudPress + S09.DeckPanel` — 69 из 69 (`ue-tests-hud-2.log`, добавлен `.Blocks`).
- `hud_contract.py validate` — PASS (G-TOKENS: литералов цвета в `S08/UI` нет). pytest `tools/s08/hud_contract` +
  `tools/s08/cue_contract` — 130 passed, 2 failed — прежние `test_hud_strings_build` (`hud.log.turn` в 04, пришёл слиянием
  `fix/admin-panel`, см. HB-24), не этот шаг. Новый тест `test_layout_trace_deck_panel_gate` — passed.
- G-WIDGET (`check-trace`) — PASS на всех 11 прогонах галереи (последний сеанс трассы) и на 5 живых прогонах;
  `UI-HUD-DECKPANEL` — own и opp; `deckpanelBlocks=0` на 1080p 75 / 100 / 150 % и 720p 100 / 150 %.
- WBP: `C:/tmp/visual/VS3-U3/um-hud-wbp-report.json` — `WBP_UI_HUD_DECKPANEL created, up-to-date`, родитель
  `UmHudDeckPanel`, sha256 `cd0c18ae46af78a8…`.

## Листы и кадры

Галерея (`run-decks-gallery.ps1`, `run-decks-batch.ps1`; editor `-game`, один клиент, `t.MaxFPS 30`, `-RenderOffScreen`,
после проверки клиентов ZCode — их не было): по секундам часов — chips, chips-stale, own, own-end, own-discard, opp,
opp-end, loading +200 мс, loading +600 мс, failed, empty-discard, own-fan9. Листы — `compose.py`: область панели и фишек
каждого состояния в родных пикселях; цвет, серый Rec.709, на 1080p 100 % ещё дейтеранопия.

Вне git (кадр доски, сканы и рубашки — ВР-CP12), `scraped-data/derived/visual-evidence/HB-28/`:
- Marmoreal: `marm-1080-100-{colour,grey,deut}` (`c2260a06799906c3`, `9332b55e03c5abd2`, `d93f2bf8a230a1a4`),
  `marm-1080-150-*` (`54a8053e271f68fc`, `b304bc6bf1084371`), `marm-1080-75-*` (`02b5fb8f282c7fbf`, `7fd9692cb94558e5`),
  `marm-720-100-*` (`3cc66083c8e1255a`, `3c6d0d51353169c0`), `marm-720-150-*` (`27ab9bf14cb274c0`, `17310798721208f6`),
  reduced `marm-1080-100-reduced-*` (`22135f24d5939116`, `5dff897bf2968a1a`).
- Sarpedon: `sarp-1080-100-{colour,grey,deut}` (`60de326de92cf5af`, `4533fcbb76385932`, `d61ad5e8f14e31f9`),
  `sarp-1080-150-*` (`dc24aaa4eb448396`, `803fe04db68e183f`), `sarp-720-100-*` (`8db75070e189fc22`, `fbb21f6ae247f4de`),
  `sarp-720-150-*` (`6a5dc3fe52c49b36`, `65da9077c59ca617`), EN `sarp-1080-100-en-*` (`18eaddf526a8e610`, `dc76dd6e094b65e3`).
- Живые кадры игрового режима (`run-bench-deck.ps1`: `-Bench -BenchDeckPanel`, Marmoreal original, `-ConceptPaste`, шесть
  фигур v2, `ARTPREVIEW heroesV2 … v2=6`), `bench/`: `bench-own-1080-100` (`0c113da5936f4e77`), `bench-opp-1080-100`
  (`99de7b82c3245a86`), `bench-own-720-150` (`a0ef832285399ad3`), `bench-opp-720-100` (`e7bed511238ec2e8`), откат
  `bench-own-1080-100-slate` (`c0ed26a8f62f09fd`).

В git (без сканов, рубашек и доски: `-S08IconGalleryHandPlain -S08CardArtLegacy`):
[`plain-legacy-1080-100-colour.png`](plain-legacy-1080-100-colour.png) (`c880ad4bd2e455fe`),
[`-grey`](plain-legacy-1080-100-grey.png) (`ad21819985b298e0`), [`-deut`](plain-legacy-1080-100-deut.png)
(`68dfce8eaa9e631f`), [`plain-legacy-720-150-colour.png`](plain-legacy-720-150-colour.png) (`4176fb2102c47f67`),
[`-grey`](plain-legacy-720-150-grey.png) (`f0e00b7bbd876f08`).

Что видно (Read: все 13 листов цветом, серые 1080p 100 %, живые кадры целиком и вырезки панели в 3×):
- Доска настоящая: Marmoreal original с нарисованным задником (`-ConceptPaste`), Sarpedon original `lit3d`; в живом кадре —
  шесть фигур v2 (гарпии 1–3, Medusa, King Arthur, Merlin), рука 5/7 сканами, PANEL-LOC / PANEL-OPP / OPP-HAND / STATUS.
- Английской Slate-панели в виде по умолчанию нет; она возвращается только откатом.
- Класс L: панель справа от поля, над DECKS, под OPP-HAND; фигуры и клетки не закрыты; PANEL-OPP и OPP-HAND видны.
  Класс S (720p 150 %): панель с y 120 su под PANEL-OPP, STATUS «Выберите действие…» над ней, шапка «Ваша колода · Medusa»
  целиком (открытый пункт 3 VS-2 закрыт); OPP-HAND под панелью погашен, край поля закрыт — исключение 04 §1.6.
- Строки: диск типа, «×N», имя, значения на одной линии; метки второй строкой; у соперника только «В сбросе 1»; рубашки
  руки соперника (5 King Arthur, 6 Medusa); фильтр — две строки с меткой сброса; -end — последняя строка последней;
  1080p 75 % — список целиком, -end равен верху (как правило HB-26).
- Скелет: на +200 мс пусто, на +600 мс 6 строк; failed — «Сервер недоступен» и «ПОВТОРИТЬ»; reduced — тот же вид.
- Серый: выбранная вкладка и включённый фильтр — светлее тело и яркая кромка; «≈» отличает stale формой.
- EN: «Your deck · King Arthur», «YOURS / OPPONENT», «DISCARD ONLY», «In discard 1», «Left 2», «Server unavailable / RETRY».
- Замечено и исправлено до коммита: разделитель строки рисовался 32 su (кисть изображения по умолчанию), имя поля трассы
  `visible=` в хвосте строки ломало G-WIDGET, в галерее загрузка и ошибка строились с уже известным списком.

## Что не сделано в этом шаге

- Приёмочные кадры набора E в партии (своя и чужая панель, обе доски, 1080p 100 %, 720p 100 и 150 %) и автозакрытие в
  живой партии — шаг «Кадры» (одна упаковка; `TakeS09DeckPanelShots` даёт `s09-deck-own/opp.png`).
- Инспектор строки — экран INSPECT (H13, VS-4); пока Slate-инспектор.
- Дельта 04 §1.6 / §2.9 (прямоугольники HB-26) в самом документе 04 — отдельный шаг документа.
- Превью наведения крайней карты веера из 8+ карт на 1080p может уйти под открытую панель (временно, панель только для
  чтения); не обрабатывалось.

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/HB-28/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: панель своя и соперника на обеих досках при 1080p 100 / 150 / 75 %, 720p 100 / 150 % (`s09-deck-own/opp`): заголовок «Ваша колода · …» / «Колода соперника ·» + имя во второй строке, вкладки, «Только сброс», строки с диском типа, «×N», значениями и метками; у соперника — «В сбросе n»; `deckpanelBlocks=0` во всех трассах. Имена карт — английские из данных (ВР-VS3-36). Панель, открытая автоклиентом во время раскрытия, гасит правый край боя (как задумано).

**Вердикт: художественно принято, по делегированию (2026-10-07).**

**Ревью VS-3 (2026-10-07, единый проход):** принято, по делегированию, с замечанием: в классе S (1080p 150 %, 720p 150 %) метки строк «Осталось n» / «В руке n» / «В сбросе n» срезаны снизу границей следующей строки — правка `UUmDeckRow` со следующей упаковкой ([VS-3](../VS-3/README.md) п. 11, ВР-VS3-R03).
