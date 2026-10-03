# 05. План реализации

Дата: 2026-10-03. Статус: ПРЕДЛОЖЕНИЕ, v2 (после адверсариального ревью — [09](09-review-log.md)). Решения —
[01](01-research-synthesis.md), требования — [03](03-ux-spec.md) (MS-R-01..40, 71, 72) и
[04](04-technical-design.md) (MS-R-41..70, 73, 74), тесты — [06](06-test-and-acceptance.md).

Размеры — **оценка** (S ≤ 0,5 дня, M — 1–2 дня, L — 3–4 дня работы агента); время сборок UE оценивается по логам UBT
(инкрементальная сборка редактора ~10–40 с, `MEMORY: feedback-estimates-from-logs`). Режим — по AGENTS.md «Iteration
speed», дословно: **light** — «small visual fixes and parameter tuning that add no new system» (≤ 3 итерации, кадры
до/после затронутых видов, только затронутые гейты, без отдельного ревью, без cost-бенча, UE-тесты только при изменении
C++); **full** — новые системы и изменения архитектуры (ревью, все гейты, cost-бенч `render_bench.py` при новых
светах, мешах, материалах или FX). Новый кэш, новый контракт ошибок, изменения правил сервера и новые кнопки — full.

## 1. Задачи

### Веха M0. Подготовка (параллельно, без кода)

| ID | Цель | Файлы | Зависит от | Размер | Режим | Закрывает | Тесты |
|---|---|---|---|---|---|---|---|
| MS-T-00 | **Сделано 2026-10-03.** Макеты MS-C-01..09 на реальных данных: карты и топология, герои и сайдкики из БД, RU-карты; значки v2 в языке карт. Два варианта цвета подложки на картах. ImageGen-концепты v1 отклонены пользователем | `tools/art/move_selection/`, `art/imagegen/move-selection-v2/` (README, manifest), изображения — `scraped-data/derived/move-selection/` (ENV-U3, вне git) | — | S | — (арт) | вход для MS-Q-04, MS-T-08, MS-T-13 | критерии 08 §4 |
| MS-T-01 | **Сделано 2026-10-03.** Сверить с официальными источниками Restoration Games (FAQ, правила томов) O-7, O-14..O-16, «Move N» без «up to», буст без движения | `docs/game-design/move-selection/_research/R6-rules-faq.md` (новый) | — | S | — (исследование) | MS-Q-01..03 | — |

### Веха M1. Правильность

| ID | Цель | Файлы | Зависит от | Размер | Режим | Закрывает | Тесты |
|---|---|---|---|---|---|---|---|
| MS-T-02 | **Сделано 2026-10-03.** Каноническая функция достижимости и пути на сервере; golden-фикстуры (≥ 40, из них ≥ 15 с ожиданиями вручную) и property-тест с перебором простых путей; генератор фикстур; сборщик полного `GameState` для фикстур (поверх `s03Engine()`/`s03Fixture()`); маршрутизация по `expect.layer` (dto / validator / executor / resolvePending). Итог: 102 фикстуры (30 ручных) на Cobble, Marmoreal, Sarpedon; property — 500 состояний; старые BFS резолва MOVE и `validateMovement` — обёртки `computeReach` (поведение то же); расхождения с правилами (MS-T-19/20) только записаны в фикстурах (`pendingRuleChange`). Сборщик лежит рядом с s03-фикстурой в `backend/src/test/fixtures/` (пути `backend/test/fixtures/` нет); дополнения к формату 04 §4.8 описаны в его заголовке | `backend/src/game-engine/movement/canonical-path.ts`, `*.spec.ts`; `backend/prisma/fixtures/movement/`; `backend/scripts/gen-move-fixtures.ts`; `backend/src/test/fixtures/move-fixture-state.ts` | — | M | full | MS-R-41, 42, 67, 68 | MS-AT-01, 02, 06, 08, 09 |
| MS-T-03 | **Сделано 2026-10-03.** `ComputeReachMap` (FIFO, dist/parent), `BuildCanonicalPath`, `FighterMovement` по сырому значению, `bDefeated` и два предиката «живой» в `FS08BoardModel`; старые функции — обёртки; тест паритета по фикстурам. Итог: `FS08ReachMap` (`Dist`, `Parent`, `Order`), `IsReachEndpoint`, `CompareCanonical` (spaceId — ordinal с учётом регистра), `ReachEndpoints`; сырое `movement` разбирается как JS `Number()` (`JsNumber`); `IsAliveBlocker()` — блокирующий, занимающий и двигаемый эффектом, `CanBeMover()` — двигаемый манёвром; `FighterAt` — по `IsAliveBlocker`. `ComputeReachableCells`/`BuildManeuverPath` — обёртки над `ComputeReachMap` с прежним поведением (маршрут — прежний обратный обход, не `K`; `Movement` int остаётся до MS-T-04), кроме MS-E-24: боец с `isDefeated` при здоровье > 0 больше не блокирует и не занимает клетку. Паритет `Unmatched.S08.MoveParity.GoldenFixtures`: 98 из 102 фикстур (28 ручных; Cobble, сетка 20×20, Marmoreal, Sarpedon), 0 расхождений; пропущены 4 без клиентских ожиданий — 2 PLACE (клетки PLACE — MS-T-12) и 2 буста без ходов. Модельная часть MS-AT-14 — `MoveParity.FighterMovement`, `AlivePredicates`; гейт `immobilized` и трасса `MS-DATA` — MS-T-04. Передача в MS-T-04: S09 ещё судит по `IsAlive()` (`S09ManeuverUi.cpp:1045` — двигаемый pending-эффектом, `:1092` — враги в BFS pending MOVE, строже сервера на грязных данных); тестовые бойцы, собранные вручную только с `Movement` (`S08BoardArtTests.cpp:739`, `S08BoardGraphTests.cpp:158`, `S08Phase2Tests.cpp:255`), после перевода на `FighterMovement` переходят на `SetRawMovement`. Уточнения в 04 §2.2, §3.1, §4.8 | `S08/S08BoardModel.h/.cpp`, `S08/S08MoveParityTests.cpp` | MS-T-02 | M | full | MS-R-41, 45 | MS-AT-10, 14 |
| MS-T-04 | Исправления черновика: нулевые ходы не отправляются (B-01), пересчёт при смене буста (B-02/F8), гейт `immobilized` (B-06/F3), `FighterMovement`/«живой» по ролям (F4/F10), кэш черновика по `maneuverId` (новый кэш — full) | `S09/S09ManeuverUi.*`, `S08/S08FlowController.cpp` | MS-T-03 | M | full | MS-R-05, 11, 15, 44, 45, 55 | MS-AT-11, 12, 14, 20 |
| MS-T-05 | **Сделано 2026-10-03.** Последовательная оценка черновика (`FS09DraftEval`), порядок ходов, статусы `Ok/NeedBoost/Conflict` по `RequiredBoost`, ярусы базы и буста (MS-E-80), подсветка карт для NeedBoost. Итог: `FS09DraftEval::Evaluate` — зеркало серверного `evaluateDraft` (гейты duplicate → missing → not-yours → defeated (`health <= 0`) → immobilized; `FighterMovement`; reach с `base + max(s, M)`; канонический путь; ярусы хода на `work_i`; `Work` = `work_n`); причины — `FS09Reason{Key, Args}` по 03 §8.2: `why.cell.ally` (с аргументом `orderHint`, если союзник уходит позже по порядку, MS-E-34), `why.swap.impossible` (MS-E-35), `why.cell.enemy`, `why.cell.unreachable {need, have}` (`have = base + max(s, M)`), `why.cell.no.path`, `why.cell.needs.boost {n}`; `FS09DraftMove` получил ещё `Conflict`, `Base`, `Allowance` и `BadgeText()` («6/5 · need +3», EN до MS-T-28). `FS09CommandUi`: `EvaluateDestination` (цель на `work_i` бойца с ходом, иначе на `work_n`), `SetDestination` принимает ярус буста со статусом NeedBoost (перезапись сохраняет номер, новое назначение — в конец), `MoveOrder` (клавиши — MS-T-07), `ClearMove` с пересчётом, `DeselectFighter`; `ToggleBoostCard` заменяет карту, отклоняет карту без BOOST (`why.boost.no.value`; `FS09CardView.bHasBoostValue`) и пересчитывает черновик в том же вызове — B-02/F8 закрыт здесь; `SelectedTiers` (база, буст, чип `dist − base`), `ReachableCells` = старт + ярус базы (прежняя подсветка); `BoostOffers`, `Eval.HighlightCardIds`; `ConfirmManeuver` пересчитывает, шлёт канонические пути и блокирует NeedBoost/Conflict с причиной (MS-R-16); трассы `MS-DRAFT`/`MS-PATH` (поле `src` — MS-T-07). `MoveParity.GoldenFixtures` теперь идёт через `FS09DraftEval`: 98 из 102, 0 расхождений. Тесты `Unmatched.S09.MoveSel.SequentialDraft` (MS-AT-13, команда сверена с `multi-cobble-free-then-occupy`/`-occupy-before-free`) и `BoostRecompute` (MS-AT-12). Не сделано здесь: нулевой ход ещё уходит пустым путём (B-01), запрет назначения обездвиженному, роли «живой» в `FindOwnFighter`, кэш по `maneuverId` — MS-T-04; трёхаргументные `ToggleBoostCard`/`ClearMove` пересчитывают на модели последнего снапшота, а `HandleApplied` декодирует доску после `OnSnapshot` — перевод вызовов на живую модель в MS-T-04/07. Живой автодрайвер S09AUTO больше не бустит картой без BOOST (в колодах MVP таких карт нет) | `S09/S09ManeuverUi.*`, `S09/S09MoveSelectionTests.cpp`; также `S09/S09HudModel.h/.cpp` (`bHasBoostValue`), `S08/S08MoveParityTests.cpp` | MS-T-03 | M | full | MS-R-16, 17, 43, 06 (данные) | MS-AT-12, 13 |
| MS-T-06 | Коды ошибок по 02 §1.1: `ActionResult.code`, коды `canPlayerAct`, `GraphQLError` с `extensions.ruleCode`, пропуск `ruleCode` в `formatError` в обоих режимах; клиент — поле `RuleCode`, классы И/С, дедлайн 10 с, снятие гейта снапшотом, `why.auth.refreshed`; ключи `why.*` в `why-reasons.json`; тосты по ключам и `CellLabel` (исправляет B-03, B-04, B-05, B-13). EN-тексты — в существующей таблице до MS-T-28 | `game-action-executor.service.ts`, `game-actions.resolver.ts`, `backend/src/graphql/graphql.module.ts`, `docs/unreal/contracts/hud/why-reasons.json`, `S08/S08Contracts.h/.cpp`, `S08/S08GraphqlClient.*`, `S08/S08FlowGameMode.cpp`, `S08/S08FlowController.cpp` | — | M (верх диапазона) | full | MS-R-10, 21, 26 (ключи и `CellLabel`), 46, 56, 73 | MS-AT-04, 18, 19 (дедлайн и гейт), 20 |
| MS-T-07 | Ввод: предвыбор (MS-S-03, ярус буста, повторный клик), подтверждение истощения (MS-S-04), быстрый ход за `-S08LegacyQuickMove`, перевод автодрайвера `-S08Maneuver` на черновик S09 с сохранением гейта демо, приоритет клика MS-R-71 (луч к плоскости поля), Esc по шагам с D/I первыми, стек отката с барьером, Delete/`ClearMove`, Tab/Shift+Tab, Ctrl+↑/↓ раньше стрелок просмотра сброса, ←/→ в MS-S-08, клик на отпускании, потеря фокуса | `S08/S08FlowGameMode.cpp`, `S09/S09ManeuverUi.*` | MS-T-05 | M (верх диапазона) | full | MS-R-01..04, 09, 18, 32, 34, 35, 62, 71 | MS-AT-15, 16, 17 |

### Веха M2. Видимый план

| ID | Цель | Файлы | Зависит от | Размер | Режим | Закрывает | Тесты |
|---|---|---|---|---|---|---|---|
| MS-T-08 | `US08MoveHighlightComponent` на ISM (4 канала подложки, геометрия 03 §4.1, вырез под ромб лидера); материал `M_UM_MovePlate`, MPC в `/Game/S08/MoveSelection/` с флагами usage; новый `ParseMoveSelection` (корневой блок и `boards[i].moveSelection`, любая поверхность) — согласовать с ENV-MAPS (§4); `SetMoveDraftView`; `-BenchMoveDraft` поверх `-BenchFixture` (проверить сначала, что `FS09CommandUi` работает в `-ArtPreview` без сервера); новый вариант `render_bench.py` с чтением draw calls; новая подсветка за флагом `-S08MovePlates` до арт-приёмки | `S08/S08MoveHighlight.*`, `S08/S08BoardActor.*`, `S08/S08BoardArt.h/.cpp`, `Content/S08/MoveSelection/`, `Config/ArtBoards/S08ArtBoardProfiles.json`, `S08/S08MoveHighlightTests.cpp`, `tools/art/render/render_bench.py`, `tools/s08/fixtures/move-draft/` | MS-T-05, MS-T-00 (для стартовых значений) | L (+1 день скрытой работы: парсер, упаковка ассетов, вариант бенча) | full | MS-R-06, 49, 50, 61, 72, 74 | MS-AT-21, 34, 41 |
| MS-T-09 | Наведение (луч к плоскости поля, hover-кэш, превью без BFS), линия пути на ISM сегментов/точек/наконечников с ростом пула, бейдж шагов | `S08/S08MoveHighlight.*`, `S08/S08FlowGameMode.cpp` | MS-T-08 | M | full | MS-R-07, 08, 12, 51 | MS-AT-22, 40 |
| MS-T-10 | Призраки (и полупрозрачность уходящей фигурки), бейджи порядка на якорях, значки последствий у цели | `S08/S08MoveHighlight.*`, `M_UM_Ghost` | MS-T-09 | M | full | MS-R-13, 14, 52 | MS-AT-23, 29 |
| MS-T-11 | Панель манёвра (UMG-гибрид): строки бойцов, буст, откат/сброс, подтверждение с итогом, «Отправлено…», баннер отказа, состояния 3 с / 10 с | `S08/S08FlowGameMode.cpp` (панель `:4660-4687`), виджет HUD | MS-T-05, MS-T-06 | M | full | MS-R-15 (панель), 16, 19, 20, 40 | MS-AT-19, 23, 31 |
| MS-T-12 | Pending MOVE/PLACE на тех же подложках (V-11/V-12), `value` 0 / нет, подписи «чей выбор», кнопки «Оставить на месте»/«Отказаться» | `S09/S09ManeuverUi.*`, `S08/S08FlowGameMode.cpp` | MS-T-08 | S | full (новые кнопки) | MS-R-25 | MS-AT-27 |
| MS-T-13 | Подбор стиля live tune (≤ 3 итерации) на Marmoreal, Sarpedon, Cobble; таблица ΔE по зонам каждой доски (03 §4.2b) и выбор цвета карт (`#FFC857` или `#4CD2DC`); кадры до/после; замеры контраста и ΔE | `Config/ArtBoards/S08ArtBoardProfiles.json` | MS-T-10 | S | light | MS-R-27, 28, 29, 30 | MS-AT-30 (предварительно), 31 |
| MS-T-28 | Локализация RU/EN: выбрать механизм (gather + `.locres` или CSV StringTable на культуру с переключением в коде), таблицы `ms`/`why`, `RuntimeDependencies` в `Unmatched.Build.cs` (как `S08ArtHud.csv`, `:50`), сборка игровой цели `-MaxParallelActions=4`, проверка в упакованном клиенте. Сейчас есть только `Content/Localization/StringTables/S08ArtHud.csv` с одной колонкой EN; `/Game/UI/Localization/ST_Why` из `why-reasons.json` не существует | `Content/Localization/StringTables/`, `Unmatched.Build.cs`, `S08/*` (загрузка таблиц) | MS-T-06 | M | full | MS-R-26 (RU/EN), 69 | MS-AT-35 |

### Веха M3. Движение и соперник

| ID | Цель | Файлы | Зависит от | Размер | Режим | Закрывает | Тесты |
|---|---|---|---|---|---|---|---|
| MS-T-14 | **Сделано 2026-10-03.** `metadata.lastMovement` для манёвра и MOVE/PLACE (канонический путь эффектов); ключ `lm` в `serialize`/`deserialize` и `SerializedGameState`; проверить MS-Q-05 (публичность instance id сброса) и MS-Q-06. Итог: след пишется на итоговом состоянии действия (`seq` = итоговый seq, в том числе при передаче хода в том же seq); манёвр — путь клиента, MOVE-эффект — `canonicalPath`, PLACE — `kind: PLACE` с одной клеткой, «остаться» — `moves: []`; `boost: null` у эффектов, `value: null` у карты без BOOST. `last-movement.spec.ts` — 61 тест, в том числе след на 46 принятых golden-фикстурах MS-T-02. MS-Q-05 (да, публичен) и MS-Q-06 (нет, `expectedSequenceNumber` не нужен) закрыты в 01 §6; что читает клиент — 04 §4.3 «Чтение клиентом» | `game-state.model.ts`, `game-action-executor.service.ts`, `backend/src/games/game-state.service.ts`, `last-movement.spec.ts` | MS-T-02 | M | full | MS-R-47, 68 | MS-AT-03, 09 |
| MS-T-15 | `FS08Cue` с путём, порядком, видом и источником; `ComputeCues` по таблице 04 §4.6; трассы `MS-CUE`; контракт CUE-007: поля потолков в `cue-table.json` и схеме, `_duration` и проверка `steps`/`ms` в `cue_contract.py` | `S08/S08FlowController.*`, `tools/s08/cue_contract/cue_contract.py`, `docs/unreal/contracts/cue-dispatcher/cue-table.json`, `cue-table.schema.json` | MS-T-14, MS-T-03 | M | full | MS-R-48, 60 | MS-AT-25, 28 |
| MS-T-16 | Анимация: `FS08MoveAnim` (расписание 04 §6.3), скольжение + подскок + доворот, PLACE-переход, пропуск (кроме Space и колеса), `jump_to_final`, snap; `US08UserSettings` (reduced motion, скорость, тряска) и `GameUserSettingsClassName` в `DefaultEngine.ini`; флаги `-S08ReducedMotion`, `-S08AnimSpeed` | `S08/S08MoveAnim.*`, `S08/S08FighterActor.*`, `S08/S08UserSettings.*`, `Config/DefaultEngine.ini`, `S08/S08MoveAnimTests.cpp` | MS-T-15 | L | full | MS-R-22, 23, 53, 54 | MS-AT-24, 33 |
| MS-T-17 | Взгляд соперника: индикатор планирования, подсветка последнего хода (V-14/V-15, правило MS-P-03, восстановление после переподключения), лента событий с усечением, стрелка у края экрана | `S08/S08FlowGameMode.cpp`, `S08/S08MoveHighlight.*` | MS-T-15, MS-T-08 | M | full | MS-R-24, 31 | MS-AT-26, 30 |
| MS-T-18 | Звук шага и пыль: подключение к CUE-007 с fallback без ассетов | `S08/S08MoveAnim.*`, `cue-table.json` | MS-T-16 | S | full (FX — cost-бенч) | MS-R-33 | MS-AT-28 |

### Веха M4. Опционально

| ID | Цель | Файлы | Зависит от | Размер | Режим | Закрывает | Тесты |
|---|---|---|---|---|---|---|---|
| MS-T-19 | Сервер: `immobilized` для MOVE/PLACE-эффектов; клиент — гасить и в эффектах | `game-rules.validator.ts`, `game-action-executor.service.ts`, `S09/S09ManeuverUi.*` | MS-T-01 (подтверждение O-15) | S | full (правила сервера) | MS-R-63 | MS-AT-05 |
| MS-T-20 | Сервер: буст картой без BOOST → `BOOST_NO_VALUE` в исполнителе до цикла ходов (покрывает `moves: []`) | `game-action-executor.service.ts` | MS-T-01 (подтверждение O-7), MS-T-06 | S | full (правила сервера) | MS-R-64 | MS-AT-07 |
| MS-T-21 | `scoreMoves`, запрос `moveHints`, бот с бустом и сайдкиками | `backend/src/game-engine/ai/score-moves.ts`, резолвер, `ai-decision.service.ts` | MS-T-02 | L | full | MS-R-65, 66 | MS-AT-50, 55 |
| MS-T-22 | Клиент: подсказки (V-13, H) и слой угроз (V-16, T) | `S09/*`, `S08/S08MoveHighlight.*` | MS-T-21, MS-T-10 | M | full | MS-R-36, 37 | MS-AT-51, 52 |
| MS-T-23 | Точки маршрута (W) | `S09/S09ManeuverUi.*`, `S08/S08FlowGameMode.cpp` | MS-T-09 | M | full | MS-R-38 | MS-AT-53 |
| MS-T-24 | Клавиатурный курсор по графу (стрелки) | `S08/S08FlowGameMode.cpp`, `S08/S08BoardModel.*` | MS-T-09 | M | full | MS-R-39 | MS-AT-54 |
| MS-T-25 | Спайки Fab (не дольше дня каждый): Simple Path Tracer против своей ISM-линии, Magic Circle Creator против кольца подложки, Glow Path против следа соперника, Card & Board Game SFX для тика шага | ветка спайка; `docs/art-pipeline/CREDITS-fab.md` при принятии | MS-T-09 / MS-T-08 / MS-T-17 / MS-T-18; **покупка — пользователь** | S × 4 | full (бенч) | MS-D-22 | MS-AT-41 по каждому |

### Веха M5. Документы и приёмка

| ID | Цель | Файлы | Зависит от | Размер | Режим | Закрывает | Тесты |
|---|---|---|---|---|---|---|---|
| MS-T-26 | Исправить устаревшие места: `docs/backend-api/04-game-api.md:192-211`, `05-engine-and-content.md:173-179, 253`, `10-mechanics-deep-dive.md:35-36, 95-101, 240-271`, `docs/unreal/_research/R4-engine-mechanics.md`, `docs/game-design/01-gameplay-experience.md:47, 154, 164, 256`, `02-ux-ui-spec.md` (UI-INP-005, UI-INP-008, §4.4, §4.10), `docs/unreal/08-gameplay-flows.md:419-430`, `03-art-direction.md` §6 (ссылка на MS-D-12), `07-animation-vfx-audio.csv` строка CUE-007 (потолки, префикс «280*» сохраняется) | перечисленные | M1–M3 | S | — (документы) | MS-R-70 | MS-AT-60 |
| MS-T-27 | Приёмка: упакованный клиент, кадры `-BenchMoveDraft` трёх досок (включая худший случай), автоматическая дуэль двух клиентов на пути черновика, ручная дуэль с переключателем `-Interactive` в `run-phase2-demo.ps1` (видимые окна, без автоманёвра, 30 FPS), reduced motion, `render_bench.py`, FPS; арт-приёмка пользователем; после неё — новая подсветка по умолчанию (снять флаг `-S08MovePlates`) | `docs/game-design/evidence/MOVE-SEL/<дата>/`, `tools/s08/run-phase2-demo.ps1` | M1–M3, MS-T-28 | M | full | MS-R-57..59, 61, 74, 24 (живьём) | MS-AT-30..35, 40..42, 32 |

## 2. Вехи и критерии выхода

| Веха | Задачи | Критерий выхода |
|---|---|---|
| M0 | MS-T-00, MS-T-01 | лист концептов; ответы на MS-Q-01..03 или пометка «официального ответа нет» |
| M1 | MS-T-02..07 | MS-AT-01, 02, 04, 06, 08..18, 20 зелёные; часть MS-AT-19, которая уже существует (тест `Unmatched.S09.CMD double-fire gate`, и новые случаи дедлайна и гейта из MS-T-06), зелёная; все 9 существующих тестов с префиксом `Unmatched.S09.CMD` (после `CMD` — пробел; запуск `node tools/s08/run-ue-tests.cjs "Unmatched.S09.CMD" <лог>`) и 6 тестов `Unmatched.S08.BoardGraph.` зелёные; живой манёвр с бустом и тремя бойцами принят сервером (трасса) |
| M2 | MS-T-08..13, MS-T-28 | MS-AT-19 (полностью: «Отправлено…», 3 с), 21..23, 27, 29, 31, 34, 35 зелёные; MS-AT-41 (cost) в бюджете для MVP и крайнего случая; кадры трёх досок для арт-ревью |
| M3 | MS-T-14..18 | MS-AT-03, 24..26, 28, 33 зелёные; путь соперника совпадает с путём автора в автоматической дуэли |
| M4 | MS-T-19..25 | по каждой задаче — свои тесты; веха не блокирует M5 |
| M5 | MS-T-26, 27 | MS-AT-30, 32, 40..42, 60 зелёные; арт-приёмка пользователя (MS-Q-04) |

## 3. Критический путь

```
MS-T-02 ─► MS-T-03 ─► MS-T-05 ─► MS-T-08 ─► MS-T-09 ─► MS-T-10 ─► MS-T-13 ─► [арт-приёмка пользователя] ─► MS-T-27
   │                     │          └─► MS-T-12                                   ▲
   │                     ├─► MS-T-07, MS-T-11 (параллельно M2) ───────────────────┤
   │                     └─► MS-T-06 ─► MS-T-28 ──────────────────────────────────┤
   └─► MS-T-14 ─► MS-T-15 ─► MS-T-16 ─► MS-T-18                                    │
                     └─────► MS-T-17 ──────────────────────────────────────────────┘
```

- Самая длинная цепочка: MS-T-02 (M) → 03 (M) → 05 (M) → 08 (L + 1) → 09 (M) → 10 (M) → 13 (S) → арт-приёмка →
  27 (M): **оценка 11–18 дней агента** (6 × M = 6–12, L + 1 = 4–5, S ≤ 0,5) **плюс ожидание арт-приёмки пользователя**
  (внешнее, не оценивается). Было 11–15 дней без MS-T-13, без ожидания и без скрытой работы ревью F-01, F-02, F-05,
  F-06, F-07, F-12 (09).
- Серверная ветка MS-T-14 идёт параллельно сразу после MS-T-02; MS-T-16 (L) и MS-T-17 должны закончиться до MS-T-27.
- MS-T-04, MS-T-06 и MS-T-28 не на критическом пути, но MS-T-28 нужна до MS-T-27 (MS-AT-35 в упакованном клиенте).
- MS-T-00 (концепты) должен закончиться до MS-T-08: стартовые значения стиля берутся из выбранного концепта.

## 4. Связь с сессией ENV-MAPS

Параллельная сессия пользователя работает над оригинальными картами в worktree `C:/tmp/wt-envmaps` (только чтение для
этого плана). Пересечения:

| Что общее | Риск | Правило |
|---|---|---|
| `S08/S08BoardActor.cpp/.h` | конфликт слияния | новая подсветка — в новых файлах `S08MoveHighlight.*`; в `S08BoardActor` меняются только `SetSelectedFighter` (`:1750-1895`) и новые члены |
| `S08/S08BoardArt.h/.cpp` (парсер профилей, его ведёт ENV-MAPS) | конфликт слияния; отказ документа целиком при ошибке парсера | добавляется отдельная функция `ParseMoveSelection` и вызов на корневом уровне и в цикле досок; `ParseReadability` не меняется; перед интеграцией — сверка с актуальным `fix/admin-panel` и прогон тестов `S08BoardArtTests` |
| `Config/ArtBoards/S08ArtBoardProfiles.json` | конфликт и смена эталонных кадров | правим только корневой `moveSelection` и `boards[i].moveSelection`; `readability.reach` не трогаем до M5 |
| Топология карт `backend/prisma/fixtures/boards/*.topology.json` | фикстуры паритета устареют; цвета зон для порога ΔE (03 §4.2b) | фикстуры хранят sha256 топологии (MS-R-67); при смене — перегенерация `backend/scripts/gen-move-fixtures.ts` и пересчёт таблицы ΔE в MS-T-13 |
| Эталонные кадры и `docs/art-pipeline/render-reference.json` | новая подсветка меняет кадры с выбором | новая подсветка за флагом `-S08MovePlates` до арт-приёмки (MS-T-27); кадры ENV-MAPS снимаются без флага |
| 3D-окружение (P8 «путь 1») | декор перехватывает трассировку клика | клетка определяется лучом к плоскости поля (04 §6.2), декор не влияет; проверка в MS-T-09 |
| `Config/DefaultEngine.ini`, `tools/s08/run-phase2-demo.ps1`, `tools/art/render/render_bench.py` | одновременные правки | добавляются только новые строки и новые параметры; существующие значения по умолчанию не меняются |
| Упаковка и UnmatchedEditor | одновременные сборки | по AGENTS.md: интеграция только `tools/git/safe-integrate.sh <branch>` (сначала dry run), ветка содержит свежий `fix/admin-panel`; после интеграции с `unreal/` — пересборка UnmatchedEditor в основном checkout и `tools/s08/sync-staged-build.ps1`; один пакет на изменение |

Процесс: работа в отдельном worktree на ветке фичи (например, `feature/move-selection`), коммиты
`git commit --no-verify` (AGENTS.md), интеграция в `fix/admin-panel` после каждой вехи через `safe-integrate.sh`.

## 5. Риски

| # | Риск | Вероятность / влияние | Снижение |
|---|---|---|---|
| RK-01 | Цвет подложки сливается с зонами доски: тёплый белый `#F2E9D8` не проходит порог ΔE76 ≥ 20 на 6 из 8 зон Marmoreal (12,3–19,4) и на зоне blue Sarpedon (19,5); у `#FFC857` на картах запас к P1 (экран) мал — 23,3 | высокая / высокое | цвет задаётся на доску (03 §4.2b): сетка Cobble — `#F2E9D8`, карты — `#FFC857`; запасной для карт — бирюзовый `#4CD2DC` (≥ 31,0 до зон карт, ≥ 36,3 до команд по hex); несущий канал — кольцо с тёмной кромкой и глиф; выбор в MS-T-13 по таблице и кадрам, экранный замер в MS-AT-30 |
| RK-02 | Расхождение клиента и сервера в достижимости | низкая / высокое | общая спецификация, golden-фикстуры в обоих наборах тестов (часть с ручными ожиданиями), property-тест с перебором путей |
| RK-03 | GPU-стоимость оверлеев выше бюджета | низкая / среднее | unlit/masked материалы, ISM для подложек и пути, `render_bench.py` в M2 (MVP и крайний случай) |
| RK-04 | Скелетный призрак дорогой или неверно позируется | средняя / низкое | запасной вариант — статичный меш позы покоя |
| RK-05 | Анимация кажется долгой | средняя / среднее | потолки 1400/2400 мс, скорость, пропуск; число подскока утверждает пользователь |
| RK-06 | `lastMovement` раскрывает скрытое | низкая / высокое | только публичные поля; проверка MS-Q-05; тест проекции соперника в MS-AT-03 |
| RK-07 | Формат ошибки ломает веб или старый UE-разбор; в production `formatError` съедает `extensions` | низкая / среднее | текст сообщения сохраняется, `ruleCode` — дополнительное поле; `formatError` правится в MS-T-06; MS-AT-04 в режиме production; MS-AT-09 |
| RK-08 | Исправления правил на сервере неверны (фан-источник) | средняя / среднее | MS-T-19/20 только после MS-T-01 |
| RK-09 | Конфликты с ENV-MAPS | высокая / среднее | §4 |
| RK-10 | Новые материалы требуют редактора | высокая / низкое | создание ассетов скриптом в редакторе (EditorScriptingUtilities уже включён — `unreal/Unmatched/Unmatched.uproject`) в сессии реализации; правило AGENTS.md: не закрывать редактор пользователя |
| RK-11 | Разрастание фазы 4 | средняя / среднее | фаза 4 опциональна и не блокирует M5 |
| RK-12 | Новая подсветка меняет эталонные кадры до приёмки | высокая / среднее | флаг `-S08MovePlates` до MS-T-27 |
| RK-13 | Перевод ввода и автодрайвера ломает демо двух клиентов: `-S08Maneuver` сейчас вызывает `TryManeuverTo` (`S08FlowGameMode.cpp:3405-3437`) и `FinishPendingManeuver` (`:3645-3651`), на нём держится гейт `bAutoManeuverDone` (`:3759-3762`) и запуск `run-phase2-demo.ps1:481` | средняя / среднее | автодрайвер переводится на путь черновика в MS-T-07 с тем же гейтом (seq + 2); трасса `MS-DRAFT src=auto`; прогон демо в критерии M1 |
| RK-14 | Инфраструктуры RU/EN нет (одна EN-таблица `S08ArtHud.csv`; `ST_Why` не существует) | высокая / среднее | отдельная задача MS-T-28 (full); до неё EN-ключи в существующей таблице, RU — честно «отложено» в отчёте M1 |
| RK-15 | `-BenchMoveDraft` в режиме `-ArtPreview` без сервера: `FS09CommandUi` может требовать живой поток | средняя / среднее | первый шаг MS-T-08 — проверка; запасной путь — заполнение `FS08MoveDraftView` напрямую из файла сцены без `FS09CommandUi` |
| RK-16 | Базы данных стендов расходятся (`docs/backend-api/db-divergence-2026-10-03.md`). Графовые доски Marmoreal/Sarpedon есть только на стенде S09 (бэкенд :3120). UE по умолчанию ходит на :3000, а `run-phase2-demo.ps1` — на :3100, где у досок пустые клетки. Без явного указания живые прогоны MS-AT-25/32 молча пойдут не на тех досках | **закрыт 2026-10-03** | все стенды — клоны одного эталона, совпадает и id Cobble City (`74098302`, раздел 9 отчёта); на любом из :3000, :3100, :3120, :3121 есть доски-графы и эффекты v9. Остаётся правило: данные менять только в эталоне, затем `node tools/db/sync-dev-stands.cjs sync --apply`; в трассе прогона проверять `boardId` из топологии |

## 6. Библиотеки Fab и вне Fab: что и когда

По [07](07-asset-libraries-fab.md):

| Кандидат | Вердикт 07 | Когда | Условие |
|---|---|---|---|
| Встроенные средства UE 5.8 (ISM с custom data, MPC, Niagara, UMG-гибрид U-4) | adopt | M1–M3 | основа всех задач; CommonUI в MVP не вводится (U-4) |
| Magic Circle Creator ($14.99 Personal) | evaluate | MS-T-25 после MS-T-08 | лучше своего кольца по кадрам и не дороже по `render_bench.py`; без света из Niagara |
| Simple Path Tracer ($19.99, C++) | evaluate | MS-T-25 после MS-T-09 | быстрее и не хуже своей ISM-линии; собирается под 5.8 |
| Glow Path ($34.99) | evaluate | MS-T-25 после MS-T-17 | след соперника; стоимость на Lumen High |
| Card & Board Game SFX ($29.99) | evaluate | MS-T-25 вместе с MS-T-18 | тик шага, подтверждение, отказ; прослушать до покупки |
| 100 Buffs, Auras and Magic Circles | evaluate (запас) | если Magic Circle Creator не подошёл | — |
| KayKit / Quaternius UAL | adopt / evaluate как источник клипа | только если пользователь выберет уровень 2 D-11 (07 §4) | нужна карта ретаргета в `docs/art-pipeline/rig/rig-contract.json` |
| ATBTT, тактические шаблоны, Epic-сэмплы (NoAI) | avoid | никогда в проекте | Epic-сэмплы — только ручной референс пользователя |

Покупку и добавление в библиотеку Fab делает только пользователь (принятие лицензии); перед покупкой — повторная
сверка флага NoAI, цены Personal и версий UE (07 §8).

## 7. Что нужно от пользователя

- Арт-приёмка: цвет подложек по доскам (на картах `#FFC857` или `#4CD2DC`), высота подскока, вид следа соперника
  (MS-Q-04) — по концептам MS-T-00 и кадрам MS-T-27.
- Покупки Fab по итогам спайков MS-T-25 (по желанию).
- Решение по подсказкам в PvP (MS-Q-08) — до MS-T-22.
- Уровень 2 D-11 (скелетный клип шага) — только если захочет; по умолчанию не делается.
- По желанию — ручная дуэль MS-AT-32 (б) самим пользователем вместо агента.
