# SC-21 — INSPECT: своя карта крупно, `UUmScreenInspect` (шаг H13)

VS-4, шаг V4 (H13), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `d668f0e5`. Карточка —
`screens.csv` SC-21; 04 §1.7 (+ дельта VS-4 V4), §3.3, §4.2, §7.1; 02 §6.1–§6.3; ВР-47…ВР-51; принятый макет CX-23
`art/imagegen/sc21-inspect-own-codex/` (ВР-VS3-SC21-01…08). Тот же модальный экран несёт [SC-22](../SC-22/README.md)
(скрытая карта), [SC-23](../SC-23/README.md) (режим колоды) и показ карты [CP-22](../CP-22/README.md).

**Статус:** UE-часть готова — модаль, колонка текста, строки, шесть путей открытия, клавиши, WBP, тесты, лист галереи и
живая проверка одним клиентом; по делегированию. Кадры набора E packaged `-Bench` с отпечатком `RENDER` (обе доски,
1080p 100 % и 720p 100 %, шесть фигур v2) — шаг «Кадры». **Откат:** `-S08SlateHud=inspect` — прежний текстовый инспектор
боковой панели (`BuildInspectorLines`), UMG-модаль не создаётся.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Модаль | `UUmScreenInspect : UUmModalBase` (`S08/UI/UmScreenInspect.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_INSPECT` (`UUmHudAuthoring`, `ue_author_um_hud.py`), в `Modals` корня. 852×688 (класс S 784×600) по центру над `panel.veil` 0,6, скин `modal`; появление 250 мс, уход 120, reduced 100. Главной кнопки нет (ВР-VS3-SC21-06); «×» — `UUmButton` с глифом `ui-close` (IC-54) 32 su, подсказка «Закрыть». |
| BindWidget | `Card` (`UUmCardWidget`), `TitleText`, `TypeIcon`, `TypeText`, `ValueText`, `BoostText`, `BodyText` (`UScrollBox`), `CopiesText`, `LangToggle`, `CloseButton`; для SC-23 — `DeckGrid`, `BackButton`. Дерево в коде (`BuildDefaultTree`) и в WBP одинаковое. |
| Карта | слот (24, 24, 460, 640), класс S 400×555 — показ CP-22 (кэп 1,6×, рамка обнимает скан по центру слота). Скан грузится — рамка и текст сразу, спиннер 32 su после 300 мс (HB-47). Нет ключа скана — плашка 02 §6.1 и «Скан карты недоступен» (`hud.inspect.art.missing`). |
| Колонка | (508, 24, 320, …) / S (448, 24, 312, …): название `type.title` (до 2 строк), диск типа v3 32 su + слово (`hud.inspect.type.*`), «Значение n» и «BOOST n» `type.heading` (= начертание `font.card`, поверх скана ничего, ВР-49), текст эффекта `type.body` в прокрутке, строка копий своей колоды «В колоде: n · в руке: h · в сбросе: d» (n = копии − рука − сброс, ВР-VS3-SC21-03). Внизу — чип «Tab» и «Язык карты», если в реестре оба скана (ВР-VS3-SC21-04); Tab переключает скан и название. |
| Закрытие | «×», Esc, I, ПКМ в любом месте модали, клик мимо (по вуали) — `Close(why)` один раз; трасса `INSPECT close why=button|esc|key-i|rmb|outside|owner`. |
| Только чтение | `FInput` модали — только `OnClose` / `OnPage`; пока модаль открыта, все клавиши её (`UmInspectOwnsInput`: Space / Enter не пропускают постановку боя, клик и клавиши не доходят до поля и команд, UI-INP-006). |
| Пути открытия | рука (ПКМ), сброс (строка панели колоды с фильтром «Только сброс»), строка журнала, строка панели колоды, карта боя (рубашка — скрытая карта, SC-22), карта в SLOT (ПКМ по прямоугольнику карты: слот пропускает клик в поле), клавиша I (выбранная карта руки, иначе под курсором), рука соперника (OPP-HAND), «Весь состав» (SC-23). Трасса `INSPECT open source=<…> mode=<…> grid=<n> copies=<n> known=0|1` — без имени и значений. |
| Звук | `CRD-INSPECT-OPEN` / `CRD-INSPECT-PAGE` / `UI-PANEL-CLOSE` — прежний аудио-хук по `bInspecting` / смене карты (сетка — страница). |
| Строки | были: `hud.inspect.*` (HB-05); добавлены `hud.inspect.deck.title`, `.copies.short`, `.back` и `hud.deckpanel.all` (`st-hud.csv` → `ST_Hud`, locres; `hud_strings_build.py build` PASS). `common.confirm.yes` / `.cancel` уже есть в `st-screens.csv` и `ST_Screens` с SC-01 (`05c3e3dd`) — проверено, не менялось. |
| SHOT | `SHOT widget id=UI-SCR-INSPECT impl=umg state=own|hidden|deck|loading … modal=1 class=L|S alpha= mode= source= face=ru|en|back|fallback cap=<scale> grid= first= copies= lang=0|1 primary=0` + строка `CARD-ART` каждой показанной карты. Состояние ждёт конца 150 мс смены содержимого и загрузки сканов сетки (ВР-VS4-71). |
| Хуки | `S08FlowGameMode.cpp` — 2 строки (вход ввода, Slate-инспектор под UMG), `…CardSlot.cpp` — 1 (курсор над HUD), `S08FlowGameMode.h` — объявления; остальное — `S08FlowGameModeUmHud.cpp` (`BuildUmInspect`, `TickUmInspect`, `UmInspectOwnsInput`, `OpenUmInspectDeck`, `HandleUmLogInspect`). |

## Решения по делегированию (шаг V4)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-62 | Класс S: карта в слоте 400×555 — новый показ `classS-inspector` | 460×640 не входит в модаль S 784×600; кэп 1,6× не меняется |
| ВР-VS4-63 | Колонка текста — поток (`UVerticalBox`): ритм макета CX-23 для однострочного названия (тип на y 128, значения 180 / 216, текст с 272); двустрочное название сдвигает остальное вниз; текст эффекта и строка копий — в одной прокрутке | реальные названия бывают в 2 строки (04 §6.2); строка копий идёт сразу за текстом, как на макете |
| ВР-VS4-64 | Данные — из бэкенда как есть: в БД `nameRu` = EN, `text` пуст у карт с разобранными эффектами; пустой текст берётся из `EffectText` известного экземпляра той же карты (рука / сброс); RU-тексты макета (скрап, ВР-VS3-SC21-01) в клиент не переносятся | придумывать нельзя; RU-название и RU-текст — задача контента бэкенда / админки |
| ВР-VS4-66 | Клавиша I: выбранная карта руки, иначе карта под курсором, иначе ничего (`INSPECT key-i nothing-selected`) | старое I открывало последнюю инспектированную карту — без неё пустую модаль |
| ВР-VS4-67 | Открытая модаль забирает все клавиши: Esc и I закрывают, Tab — язык, Backspace — к сетке; ПКМ в любом месте модали закрывает | 04 §1: «ввод вне модали закрыт»; Space / Enter иначе пропускали бы постановку боя за модалью |
| ВР-VS4-70 | Строка журнала открывает карту каталога из любого из двух списков колоды (не только из стороны панели) | в журнале и свои, и чужие карты; список колоды публичный (F-05) |
| ВР-VS4-71 | Состояние гейта следует за содержимым: во время 150 мс смены стоит прежнее, сетка с ещё грузящимися сканами — `loading` | первый живой кадр `-S08ScreenShots` поймал полупрозрачную сетку с пустыми рамками |
| ВР-VS4-72 | Живые доказательства — opt-in `-S08InspectShots` (+ `-S08ScreenShots`): с первого своего неначального хода +1 с модаль показывает своя / скрытая / колода / карта сетки по 1,4 с; HB-47 — скелет панели колоды при задержанном `gameDeckLists` (`tools/s10/delay-graphql-query-proxy.cjs`) | состояния нужны в живой партии; шаг «Кадры» берёт тот же механизм для набора E |
| ВР-VS4-73 | Строка копий — только у карт своей колоды; у открытой карты соперника (его сброс, раскрытая карта боя) её нет | о руке и колоде соперника клиент ничего не знает |

## Лист и проверки

- Галерея `-S08IconGalleryInspect=<board>` (инструмент ревью; `S08/UI/UmInspectGallery.h`): настоящий
  `UUmScreenInspect` поверх кадра bench K1 доски (Sarpedon original — lit3d, Marmoreal original — `-ConceptPaste`, шесть
  фигур v2), данные — захват S01 контента бэкенда (`content-<hero>.json`: name, nameRu, типы, значения, BOOST, копии,
  textEn / тексты эффектов), момент HB-26 (своя Medusa, Gaze of Stone ×2 в руке). Состояния по секунде: 0 own, 1 own-en,
  2 loading, 3 missing, 4 hidden, 5 deck, 6 deck-end, 7 deck-card, 8 deck-ka, 9 opp-card. Прогоны: Sarpedon 1080p 100 /
  150 %, 720p 100 / 150 %; Marmoreal 1080p 100 %, 720p 100 %.
- Вне git (сканы, рубашки, доска; ВР-VS4-01): `scraped-data/derived/visual-evidence/SC-21/` —
  [`visual-evidence-index.json`](visual-evidence-index.json): контактные листы 6 прогонов (цвет, серый), листы состояний
  own / own-en / loading / missing / opp-card (цвет, серый, дейтеранопия), живые кадры `live/`.
- Живая проверка одним клиентом (UnrealEditor `-game` worktree, VS_AI на основном бэкенде :3000, Sarpedon original,
  30 FPS, offscreen; `C:/tmp/visual/vs4-v4/live/l5-sarp-1080-100`, `l7-sarp-720-150`): `INSPECT open source=hand`,
  кадр `UI-SCR-INSPECT-own` — Hiss and Slither, «Защита», «Значение 4», «BOOST 3», текст эффекта из снапшота, «В колоде: 2 ·
  в руке: 1 · в сбросе: 0». Бот VS_AI берёт сильнейшего героя (T. Rex, правило бэкенда) — фигуры не шесть v2: это проверка
  работы, не кадр приёмки.
- Открыты (Read): контакт Marmoreal 1080p 100 %, лист состояний (серый), живые `UI-SCR-INSPECT-own` 1080p 100 % и 720p
  150 %, кадры галереи Sarpedon own / loading / missing / hidden / deck / deck-card / opp-card (1080p 100 %), own 1080p
  150 %, deck-card и deck-ka 720p 150 %.
- Сборки: UnmatchedEditor (`build-12`) и игровая цель (`build-game-1`) — Succeeded.
- Тесты: `Unmatched.S08.Hud.Screens.Inspect.Tree`, `.Paths`, `.Input`, `.Privacy`, `Unmatched.S08.Hud.Inspector.Cap`
  — PASS; полный `Unmatched.S08 + S09 + S10` (код `build-10`; дальше менялись только лист галереи и порядок полей) — 504 из
  505, упал
  `Hud.Actions.KeyHints`: живые партии этого шага подняли `CompletedMatches` профиля worktree до 7; после возврата 0 —
  `Hud.Actions.*` 3 из 3.
- Гейты: `hud_contract.py check-trace` — галерея PASS (70 строк `SHOT widget`); живые трассы — строки `UI-SCR-INSPECT` и
  `CARD-ART` без ошибок (падают только известные строки W5b-R `plate*`, VS-2 п. 7); `hud_contract.py validate` PASS;
  `hud_strings_build.py check` PASS; `hud_tokens_codegen.py --check` FRESH; pytest `tools/s08/hud_contract` +
  `cue_contract` 134 из 134.

## Что не сделано в этом шаге

- Кадры набора E packaged `-Bench` с отпечатком `RENDER` на Marmoreal и Sarpedon original, 1080p 100 % и 720p 100 %,
  шесть фигур v2 (нужна дуэль двух клиентов: VS_AI всегда даёт T. Rex) и лист приёмки в цвете / сером / дейтеранопии —
  шаг «Кадры» (механизм — `-S08InspectShots`).
- Бюджет ≤ 0,5 мс GT p95 / ≤ 0,3 мс GPU — замер HUD в HB-49.
- RU-названия и RU-тексты карт в БД (данные бэкенда / админки).
