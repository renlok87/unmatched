# 04. Технический дизайн

Дата: 2026-10-03. Статус: ПРЕДЛОЖЕНИЕ, v2 (после адверсариального ревью — [09](09-review-log.md)). Дизайн
надстраивается над существующим кодом; новые сущности добавляются только там, где старые не годятся. Требования этого
документа — **MS-R-41..MS-R-70, MS-R-73, MS-R-74**. Пути UE даны от `unreal/Unmatched/Source/Unmatched/`, если не
указано иное.

Синхронизация с живым исследованием DE (DE-004, прогон A, 2026-10-04): §6.3 «Анимация перемещения» и блок `anim` §4.7 —
по SD-50 ([02-spec-deltas](../de-footage/task/02-spec-deltas.md)) и решению [01 F-02](../de-footage/task/01-decisions.md#f-02-d-de-02-шаг-и-подскок) (по умолчанию,
D-DE-02; R-14 live 2026-10-04): время постоянно на ребро, подскок 0 (параметр), наклон хода 10°, доворот 120 мс,
возврат в Idle 150 мс, ease — параметр, по умолчанию выкл.

## 1. Архитектура

```
 Сервер (авторитет)                                  Клиент UE (подсказка + показ)
 ─────────────────                                   ──────────────────────────────
 beginManeuver ─┐                                    AS08FlowGameMode  ── ввод (опрос клавиш/мыши), панель HUD
 maneuver ──────┤ GameActionExecutor                    │  луч мыши → плоскость поля → клетка; клик на отпускании
 resolvePending ┘   ├ GameRulesValidator (GD-015)       ▼
                    ├ movement/canonical-path.ts ◄─┐ FS09CommandUi (S09)  ── машина черновика MS-S-xx
                    │  (НОВОЕ: reach + путь)        │   ├ FS09ManeuverDraft: ходы, порядок, буст, стек отката
                    ├ ruleCode в ошибках (НОВОЕ)    │   └ FS09DraftEval: последовательная симуляция, статусы
                    └ metadata.lastMovement (НОВОЕ, │      ▼
                      сохраняется в БД ключом lm)   │
 golden-фикстуры backend/prisma/fixtures/movement ──┴► FS08BoardModel (S08)  ── Neighbours, ComputeReachMap,
                                                       │                       BuildCanonicalPath (НОВОЕ)
 GameStateService.filterPrivateData ──► снапшот ──►  FS08FlowController ── транспорт, seq-guard, дедлайн 10 с, cue (+Path)
                                                       │
                                                       ▼
                                                     AS08BoardActor ── US08MoveHighlightComponent (НОВОЕ: ISM-подложки,
                                                       │                 ISM-сегменты пути, призраки, бейджи)
                                                     AS08FighterActor ── FS08MoveAnim (НОВОЕ: скольжение + наклон, подскок 0)
```

Принципы:
- **Одна функция правил на сторону, один алгоритм на обе стороны.** Сервер: `traversal.ts` + `board-topology.ts` +
  новый `canonical-path.ts`. Клиент: `FS08BoardModel`. Паритет держат golden-фикстуры (MS-R-41).
- **Модель черновика не знает о мире.** `FS09CommandUi` остаётся чистой логикой (тестируется без мира), отдаёт
  `FS08MoveDraftView` — описание того, что нарисовать. Отрисовка — только `US08MoveHighlightComponent`.
- **Состояние не ждёт анимации** (`docs/unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md`). Логическая позиция
  фигурки = снапшот; анимация — только визуальная позиция; индикатор хода — по снапшоту (MS-E-45).

## 2. Что меняется в каких файлах

### 2.1. Сервер

| Файл | Изменение | Задача |
|---|---|---|
| `backend/src/game-engine/movement/canonical-path.ts` (новый) | `computeReach(state, moverId, maxSteps, opts)` → `{dist, parent}`; `canonicalPath(reach, state, dest)`; ключ `spaceId`/`(y,x)` | MS-T-02 |
| `backend/src/game-engine/movement/canonical-path.spec.ts`, `move-parity.spec.ts`, `move-parity.property.spec.ts` (новые) | golden-фикстуры и property-тест | MS-T-02 |
| `backend/src/test/fixtures/move-fixture-state.ts` (новый) | сборщик полного `GameState` из фикстуры §4.8 поверх `s03Engine()`/`s03Fixture()` (`backend/test/fixtures/s03-engine.fixture.ts`, импорт — `s03-turn.spec.ts:2`): фаза, `pendingManeuver`, `handZones`, колоды, реестр способностей | MS-T-02 |
| `backend/prisma/fixtures/movement/*.move-fixture.json` (новые) | golden-фикстуры паритета (формат §4.8) | MS-T-02 |
| `backend/src/game-engine/models/game-state.model.ts` | `GameStateMetadata.lastMovement?: LastMovement` (рядом с `pendingManeuver`, `:160`) | MS-T-14 |
| `backend/src/games/game-state.service.ts` | `serialize`/`deserialize` (`:556-663`, `:671-790`) пишут и читают ключ `lm` ← `lastMovement`; поле `lm?` в `SerializedGameState` (`:49-84`). Без этого след теряется при чтении из БД (промах кэша, перезапуск — `getState` → `deserialize`, `:488`) | MS-T-14 |
| `backend/src/game-engine/services/game-action-executor.service.ts` | `executeManeuver` пишет `lastMovement` (после `:1781-1784`); резолв MOVE/PLACE (`:584-707`) пишет `lastMovement` с каноническим путём; `ActionResult` несёт `code` (таблица 02 §1.1); `canPlayerAct` передаёт свой `code`; фаза 4 после MS-T-01: проверка `boostValue == null` → `BOOST_NO_VALUE` **в исполнителе до цикла ходов** (после `:1719-1721`), чтобы покрыть `moves: []` (MS-E-81) | MS-T-14, MS-T-06, MS-T-20 |
| `backend/src/games/resolvers/game-actions.resolver.ts` | `handleActionResult` (`:134-138`) бросает `GraphQLError` с `extensions: { code: 'BAD_USER_INPUT', ruleCode }` вместо `BadRequestException` | MS-T-06 |
| `backend/src/graphql/graphql.module.ts` | `formatError` (`:60-102`) пропускает `extensions.ruleCode` в обоих режимах; сейчас в production ошибка с кодом `BAD_REQUEST` заменяется на «Internal server error» без `extensions` (окружение сейчас development — `backend/.env:2`) | MS-T-06 |
| `backend/src/game-engine/validators/game-rules.validator.ts` | фаза 4 после сверки: общий хелпер `isImmobilized` для манёвра и эффектов | MS-T-19 |
| `backend/src/game-engine/ai/score-moves.ts` (новый), резолвер `moveHints` | фаза 4 | MS-T-21 |
| `backend/src/game-engine/services/ai-decision.service.ts` | фаза 4: путь — `canonicalPath`; выбор — `scoreMoves`, буст, сайдкики | MS-T-21 |

### 2.2. Клиент UE и инструменты

| Файл | Изменение | Задача |
|---|---|---|
| `S08/S08BoardModel.h/.cpp` | `FS08ReachMap`, `ComputeReachMap` (FIFO BFS, dist/parent), `BuildCanonicalPath`; `FS08BoardFighter`: `bDefeated`, сырое значение движения (`double MovementRaw`, `bool bMovementPresent`, строка → `Number`-подобный разбор); `FighterMovement` (зеркало `getFighterMovement` по сырому значению, MS-E-107); предикаты `IsAliveBlocker()` (`health > 0 && !bDefeated`) и `CanBeMover()` (`health > 0`) — MS-E-24, MS-E-77; `ComputeReachableCells`/`BuildManeuverPath` становятся обёртками. Сделано в MS-T-03, с уточнениями: обёртки сохраняют прежнее поведение, в том числе выбор маршрута `BuildManeuverPath` обратным обходом соседей (не по `K`) и отсутствие проверки конечной клетки, кроме правил сервера, внесённых в модель: блокирует и занимает только `IsAliveBlocker` (боец с `isDefeated` при здоровье > 0 — нет, MS-E-24; это и через `FighterAt`), id сравниваются точно; канонический путь даёт только `BuildCanonicalPath`, вызовы переводятся в MS-T-04/05/07. Поле `Movement` (int, прежний разбор) остаётся до перевода вызовов на `FighterMovement` в MS-T-04. Добавлены `IsReachEndpoint`, `CompareCanonical`, `ReachEndpoints` (ярусы — разбиение по дистанции), `JsNumber` (разбор сырого значения как JS `Number()`) | MS-T-03, MS-T-04 |
| `S08/S08Contracts.h/.cpp` | `FS08GraphQLError` (`S08Contracts.h:15-22`) получает `RuleCode`, разбор `extensions.ruleCode` рядом с `extensions.code` (`S08Contracts.cpp:263-269`) | MS-T-06 |
| `S09/S09ManeuverUi.h/.cpp` | `FS09DraftMove` + `Path`, `Order`, `Status`, `RequiredBoost`; `FS09DraftEval` (последовательная симуляция); стек отката с барьером по seq; `ClearMove` в ввод; предвыбор; `ConfirmManeuver` без нулевых ходов; `ToggleBoostCard` с пересчётом; гейт `immobilized`; причины как `FS09Reason{Key, Args}`; `BuildDraftView()`; `PendingChoice.bHasValue` сохраняется (MS-E-57/76) | MS-T-04, MS-T-05, MS-T-07 |
| `S08/S08FlowGameMode.cpp` | клавиши 03 §3.2; клик на отпускании; клетка — луч к плоскости поля (§6.2); hover-кэш; предвыбор и MS-S-04; быстрый ход TASK-022 (`:1211-1260`) за флагом `-S08LegacyQuickMove`; автодрайвер `-S08Maneuver` (`RunAutoManeuver`, `:3405-3437`, второй шаг `:3645-3651`) переводится на путь черновика S09; панель манёвра; индикатор соперника; лента событий; стрелка у края | MS-T-07, MS-T-11, MS-T-17 |
| `S08/S08FlowController.h/.cpp` | `FS08Cue` + `Path`, `OrderInSeq`, `Kind`, `PathSource` (`:49-57`); `ComputeCues` по правилам §4.6; `SubmitManeuver` (`:1673-1720`) дополнительно отбрасывает пустые пути; ошибки — `RuleCode` → класс 02 §1.1; дедлайн 10 с и снятие гейта снапшотом (§5); кэш черновика по `maneuverId` | MS-T-15, MS-T-06, MS-T-04 |
| `S08/S08GraphqlClient.h/.cpp` | таймаут запроса мутации 10 с (сейчас таймаута нет: `grep SetTimeout` по `Source` и `Config` — 0) с исходом «неизвестен» | MS-T-06 |
| `S08/S08BoardArt.h/.cpp` | новый `ParseMoveSelection`: корневой блок `moveSelection` (умолчания для всех досок) и `boards[i].moveSelection` (переопределение, **любая** поверхность). Блок `readability` не трогается: он разрешён только для досок-картинок (`S08BoardArt.cpp:978-984`), и сетка с ним отклоняется целиком | MS-T-08 |
| `S08/S08BoardActor.h/.cpp` | `SetSelectedFighter` (`:1750-1895`) перестаёт спавнить акторы; новый `SetMoveDraftView(const FS08MoveDraftView&)`; владеет `US08MoveHighlightComponent`; `ShowIllegalCell` остаётся для CUE-004 | MS-T-08 |
| `S08/S08MoveHighlight.h/.cpp` (новые) | `US08MoveHighlightComponent`: ISM подложек (4 канала), ISM сегментов пути, точек и наконечников, призраки, бейджи | MS-T-08..MS-T-10 |
| `S08/S08MoveAnim.h/.cpp` (новые) | чистая функция расписания анимации; интеграция с `AS08FighterActor` | MS-T-16 |
| `S08/S08FighterActor.h/.cpp` | визуальная позиция отдельно от логической; `PlayMove(points, schedule)`, `SnapToLogical()`; наклон хода, разворот и доворот, возврат в Idle; подскок — параметр, по умолчанию 0 (D-DE-02) | MS-T-16, DE-021 |
| `S08/S08UserSettings.h/.cpp` (новые) | `US08UserSettings` — объект конфигурации в `GameUserSettings.ini` (`config=GameUserSettings`, секция `[/Script/Unmatched.S08UserSettings]`): `bReducedMotion`, `AnimSpeed`, `bScreenShake` (UI-ACC-005). Не подкласс `UGameUserSettings` — уточнение MS-T-16 в §6.3 | MS-T-16 |
| `unreal/Unmatched/Config/DefaultEngine.ini` | не меняется: `GameUserSettingsClassName` не подменяется (уточнение MS-T-16 в §6.3) | MS-T-16 |
| `S09/S09MoveSelectionTests.cpp`, `S08/S08MoveHighlightTests.cpp`, `S08/S08MoveAnimTests.cpp`, `S08/S08MoveParityTests.cpp` (новые) | автотесты MS-AT-10..29 | по задачам |
| `unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json` | корневой `moveSelection` и `boards[i].moveSelection` (схема §4.7); старый `readability.reach` остаётся как запасной до удаления | MS-T-08, MS-T-13 |
| `docs/unreal/contracts/hud/why-reasons.json`, StringTable `ms`/`why` | ключи `why.*`, `ms.*` (03 §8.2, §9); механизм RU/EN и упаковка — MS-T-28 | MS-T-06, MS-T-28 |
| `unreal/Unmatched/Content/S08/MoveSelection/` | `M_UM_MovePlate`, `M_UM_MovePath`, `M_UM_Ghost` (unlit игровой слой по образцу `M_UM_GameLayer`), MPC `MPC_UM_MoveSelection`; меши плиток круга и квадрата, сегмента пути, наконечника; атлас глифов. Папка внутри `/Game/S08`, которая уже упаковывается (`unreal/Unmatched/Config/DefaultGame.ini:17`); `/Game/UM/Materials` в `DirectoriesToAlwaysCook` нет (есть только `/Game/UM/Materials/v2`, `:44`) | MS-T-08..MS-T-10 |
| `docs/unreal/contracts/cue-dispatcher/cue-table.json`, `cue-table.schema.json`, `tools/s08/cue_contract/cue_contract.py`, `docs/game-design/07-animation-vfx-audio.csv` (строка CUE-007) | CUE-007: `params.path`, `order_in_seq`, потолки `cap_subject_ms`, `cap_seq_ms`, `min_step_ms`, `overlap`, `place_ms`; `_duration` (`cue_contract.py:168-171`) считает по §6.3; проверка формата `durationMs` (`:90-92`) — по новой строке 07 | MS-T-15, MS-T-26 |
| `tools/art/render/render_bench.py` | новый вариант в `VARIANTS` (`:165`) с `-S08MovePlates -BenchMoveDraft=<путь>`; чтение числа draw calls из CSV (`RHI/DrawCalls`; наличие колонки в нашем CSV — **не проверено**) | MS-T-08 |
| `tools/s08/run-phase2-demo.ps1` | переключатель `-Interactive`: оба клиента видимы (без `-RenderOffScreen`, `:458`), без `-S08Maneuver` (`:481`), окна 1280×720 рядом, `-ClientFps 30` | MS-T-27 |

Конфиги: стиль подсветки живёт в существующем `S08ArtBoardProfiles.json` (MS-D-24), поэтому новый `Config/**.json` не
вводится. Ловушка упаковки AGENTS.md («Packaging trap») срабатывает в MS-T-28: новая CSV StringTable — новая
`RuntimeDependencies` в `Unmatched.Build.cs` (как `S08ArtHud.csv`, `Unmatched.Build.cs:50`); правка `Build.cs` сама
перегенерирует makefile, сборка игровой цели — с `-MaxParallelActions=4`.

## 3. Достижимость и путь

### 3.1. Алгоритм (одинаковый на сервере и клиенте)

```
computeReach(board, fighters, mover, maxSteps, opts):
  start = mover.position
  dist[start] = 0; parent[start] = none; queue = [start]          // FIFO
  while queue:
    c = pop_front(queue)
    if dist[c] >= maxSteps: continue                              // >=: сервер и паритет (MS-T-02)
    for n in neighbours(board, c):                                // links (симметризованы) | 4 ортогональных
      if n in dist: continue
      if not passableTerrain(board, n): continue                   // wall/obstacle/closed door/нет клетки
      if livingEnemyOf(mover, n) and not opts.passThroughEnemies: continue
      dist[n] = dist[c] + 1; parent[n] = c; push_back(queue, n)
  return dist                                                      // parent не нормативен (зависит от порядка соседей)

isEndpoint(c) = (c == start) or (no living fighter other than mover at c)

canonicalPath(board, fighters, mover, dist, dest):                 // без стартовой клетки
  if dest == start: return []                                      // «остаться»: в moves[] не включать
  if dest not in dist or not isEndpoint(dest): return none
  path = [dest]; cur = dest
  while dist[cur] > 1:
    cands = [p in neighbours(board, cur) : p in dist and dist[p] == dist[cur] - 1]
    cur = min(cands, key = K); path.prepend(cur)
  return path
K(c) = (spaceId(c), c.y, c.x) на графовой доске; (c.y, c.x) на сетке
```

- «Живой» для блокировки и конца пути = `isLivingFighter` (`health > 0 && !isDefeated`, `traversal.ts:19-21`).
  Двигаемый боец допускается при `health > 0` (`game-rules.validator.ts:294-296`) — клиент повторяет оба предиката
  по ролям (MS-E-24, MS-E-77). Уточнение MS-T-03: третья роль — боец, двигаемый MOVE/PLACE-эффектом, — на сервере
  тоже `isLivingFighter` (`game-action-executor.service.ts:617`, кроме revive-PLACE), на клиенте `IsAliveBlocker()`.
  `ComputeReachMap` состояние двигаемого не проверяет — это делает вызывающий по роли.
- `neighbours` на клиенте — `FS08BoardModel::Neighbours` (`S08BoardModel.h`; номер строки сдвинулся в MS-T-03); на сервере — `board-topology.ts:174-185`.
  Порядок соседей на результат не влияет: `dist` от порядка не зависит, `K` выбирает предшественника однозначно.
- Кандидаты-предшественники проходимы по построению (`dist` определён только для проходимых клеток), союзники в них
  допустимы — как на сервере.
- Допуск манёвра — `FighterMovement(f) + boost`; MOVE-эффект — `pending.value ?? 1` с `passThroughEnemies` по
  `canPassThroughEnemies` и врагами относительно владельца двигаемого бойца (`game-action-executor.service.ts:647-660`).
- Сложность: ≤ 38 вершин на графе, ≤ 400 на сетке 20×20; один BFS — микросекунды (оценка; замер — MS-AT-40).

### 3.2. Ярусы, статусы и последовательная симуляция

Буст — одна карта на манёвр; другая карта **заменяет** выбранную (`boostCardId` один, `game-rules.validator.ts:317-344`).
Поэтому нужный буст хода считается от базы, а не от текущего допуска.

```
draft.moves = [m_0 .. m_{n-1}]                                     // порядок отправки
s = BOOST выбранной карты или 0;  M = max BOOST пригодных карт руки (boostValue ≠ null), 0 если их нет
work_0 = snapshot.fighters
for i in 0..n-1:
  base_i       = FighterMovement(m_i.fighter)
  reachMax_i   = computeReach(board, work_i, m_i.fighter, base_i + max(s, M))
  path_i       = canonicalPath(..., reachMax_i, m_i.dest)
  required_i   = max(0, len(path_i) - base_i)                      // абсолютный нужный BOOST
  status_i     = Ok              если path_i и required_i <= s
               = NeedBoost(required_i)  если path_i и required_i > s
               = Conflict(why)   если path_i нет (занято, блок, порядок)
  work_{i+1}   = work_i с m_i.fighter на m_i.dest (при Ok/NeedBoost)
highlightCards = карты с BOOST >= max(required_i по NeedBoost), кроме выбранной
```

- Подсветка выбранного бойца: если у него есть ход m_i — по `work_i`; если нет — по `work_n` (новый ход встанет в
  конец).
- Ярус базы: `dist ≤ base + s` и `isEndpoint`. Ярус буста: `base + s < dist ≤ base + M` и `isEndpoint` (пуст при
  `s ≥ M`); чип у пространства — `dist − base` (MS-E-80).
- Бейдж и строка панели: `{len}/{base + s}`; при `required > s` — `{len}/{base + s} · нужно +{required}`.
- Любая операция черновика (назначение, снятие, смена буста, порядок, снапшот) пересчитывает все ходы — n ≤ 9, BFS
  дешёвый; инкрементальность не нужна.
- Ход с `dest == start` не попадает в `moves[]` (MS-D-08); при подтверждении такие записи отбрасываются ещё раз в
  `SubmitManeuver` (защита, MS-R-44).
- Подтверждение активно, только если все ходы Ok и поток WS готов (MS-E-91).

### 3.3. Pending MOVE/PLACE

`FS09CommandUi::ComputePendingCells` (`S09ManeuverUi.h:328-330`) переводится на `ComputeReachMap` с допуском
`PendingChoice.bHasValue ? Value : 1` — клиент уже различает отсутствие поля и 0 (`S09ManeuverUi.cpp:1142`), это
сохраняется: отсутствие → 1, `0` → 0 (только «остаться», MS-E-76). PLACE — все свободные проходимые пространства (с
зоной `zoneFighterName`, если есть), без пути. Для MOVE превью пути — `canonicalPath`; сервер после MS-T-14 записывает
тот же путь в след.

С DE-016 сервер не оставляет MOVE/PLACE во главе очереди, если подсветить нечего: ни у одного допустимого бойца нет
свободного пространства, кроме своего (для MOVE — в пределах `value` шагов, для PLACE — в зоне `zoneFighterName`).
Такой выбор снимается, а нулевой шаг применяется без ввода; причина — в `metadata.skippedEffects` (§4.3.1). Поэтому
клиенту не нужен отдельный случай «pending без подсвеченной клетки».

Уточнение MS-T-12 (реализация): единственный допустимый боец выбирается снапшотом, пространства выбранного бойца
пересчитываются каждым снапшотом. Своё пространство двигаемого бойца легально (нулевой шаг), но подложки не получает:
«остаться» — кнопка панели `ms.btn.stay`, поэтому `value` 0 (если старый сервер откроет такой выбор) подложек не рисует.
Выбранная цель — V-04 с `canonicalPath` (MOVE) или без пути (PLACE). Отказанное пространство называет why.* по ключу
(`FS09CommandUi::PendingCellReason`); `MS-REJECT place.no.space` остаётся сигналом серверного пробела (после DE-016 его быть
не должно).

### 3.4. Паритет

| Свойство | Как обеспечено | Тест |
|---|---|---|
| Одинаковое множество достижимых пространств | общая спецификация §3.1 + фикстуры | MS-AT-01, MS-AT-10 |
| Одинаковый канонический путь | ключ `K` не зависит от порядка соседей | MS-AT-01, MS-AT-10 |
| Клиент не строже и не мягче сервера | property-тест: каждый путь `canonicalPath` принимается `validateManeuver`; для каждого пространства вне `reach` **все простые пути** длиной ≤ допуска (перебор DFS, граф ≤ 38 вершин) отклоняются | MS-AT-06 |
| Последовательная семантика | фикстуры с несколькими ходами против `executeManeuver` на полном `GameState` (сборщик §2.1) | MS-AT-02, MS-AT-13 |
| `getFighterMovement`, предикаты «живой» | фикстуры с `movement` 0/null/2.5/3.5/`"3"` и `isDefeated` при `health > 0` у блокирующего и у двигаемого | MS-AT-02, MS-AT-14 |
| Свежесть фикстур | фикстура хранит sha256 файла топологии; при расхождении тест падает с просьбой перегенерировать | MS-AT-08 |
| Независимость ожиданий | ≥ 15 фикстур с ожиданиями, выписанными вручную из правил (`expectSource: "manual"`, ревью при добавлении); остальные — генератор (`"generated"`), для них MS-AT-01 — регрессионный | MS-AT-01 |

## 4. Контракты данных

### 4.1. Команда (без изменений)

`maneuver(input: { gameId, maneuverId, moves: [{ fighterId, path: [{x,y}] }], boostCardId? })`
(`backend/src/games/dto/gameplay.dto.ts:111-159`). Путь — без стартовой клетки, координаты решётки, не `spaceId`.
Ходы нулевой длины не включаются. `beginManeuver(input: { gameId, expectedSequenceNumber })` — без изменений.

### 4.2. Ошибки

`ActionResult` получает необязательный `code`. Исполнитель передаёт `validation.code` (в том числе от `canPlayerAct`);
свои ошибки получают коды из 02 §1.1 (`BEGIN_NOT_ALLOWED`, `STATE_CHANGED`, `PENDING_CHOICE_OPEN`,
`COMBAT_IN_PROGRESS`, `GAME_OVER`, `MANEUVER_NOT_OPEN`, `DUPLICATE_FIGHTER`, `PENDING_WRONG_FIGHTER`,
`PLACE_OUTSIDE_ZONE`; для существующих смыслов — уже имеющиеся `CARD_NOT_IN_HAND`, `POSITION_OCCUPIED`,
`INVALID_POSITION`, `NOT_ENOUGH_MOVEMENT`). Резолвер бросает `GraphQLError` с
`extensions: { code: 'BAD_USER_INPUT', ruleCode }`; `formatError` пропускает `ruleCode` в обоих режимах
(`backend/src/graphql/graphql.module.ts:60-102`). Имя `ruleCode` выбрано, чтобы не конфликтовать со стандартным
`extensions.code`; клиент сейчас читает только `extensions.code` (`S08Contracts.cpp:263-269`) и получает поле
`RuleCode` в MS-T-06. Текст ошибки остаётся для старых клиентов и веба.

Уточнение MS-T-06 (реализация):
- Сервер. Кроме мест таблицы 02 §1.1 код получают ранние отказы `resolvePendingEffect`: открыт
  `pendingManeuver`/`pendingHandDiscard` — `PENDING_CHOICE_OPEN`, конец игры — `GAME_OVER`, выбор не найден или не голова
  очереди — `STATE_CHANGED`, боец вне `fighterIds` эффекта — `PENDING_WRONG_FIGHTER`, «Боец не найден или повержен» —
  `FIGHTER_NOT_FOUND` или `FIGHTER_DEFEATED`. Тексты сообщений не менялись. Отказ без кода (остальные мутации, «выбор
  принадлежит другому игроку») остаётся `BadRequestException`, ответы guard'ов не менялись — клиент показывает для них
  `why.command.rejected` (так `NOT_YOUR_TURN` и `INVALID_PHASE` при обычном запросе приходят от `ActionPhaseGuard` без
  `ruleCode`; с кодом они доходят только из исполнителя). `formatError` вынесен в экспортируемую `formatGraphqlError`:
  в production бизнес-ошибка с `ruleCode` получает `extensions: { code, ruleCode }`, системная — только `ruleCode`, если
  он есть. Apollo отвечает на такой отказ HTTP 200 (проверено в `maneuver-error-codes.spec.ts`), клиент читает его из
  `errors[]`.
- Клиент. Таблица 02 §1.1 — `FS08RuleCodes::Classify` (`S08/S08Contracts.h`): ключ `why.*`, класс И/С, клетка из текста
  (`PATH_BLOCKED_BY_ENEMY` на конце хода → `why.cell.enemy`), `need`/`have` из текста `NOT_ENOUGH_MOVEMENT`; лимит
  запросов → `why.syncing` без перечитывания; без кода или неизвестный код → `why.command.rejected`. Недостающие
  аргументы тоста заполняет `FS09CommandUi::RejectionReason` (пространство по одному концу хода команды, имя бойца из
  черновика или pending-выбора и из «…» текста `PLACE_OUTSIDE_ZONE`, `need` — путь на снапшоте, `have` — допуск;
  пути нет — `why.cell.no.path`), поэтому в тосте нет «?». Оба класса
  перечитывают снапшот (`FetchGameState`), команда не повторяется. Трасса `MS-REJECT code=<ruleCode|-> why=<key>
  class=<И|С> op=<begin|maneuver|pending>`: контроллер не знает `CellLabel`, поэтому пространство пишет трасса тоста
  `TOAST why=<key> text="…"` режима игры. EN-тексты по ключам — таблица кода `S08/S08WhyText` (столбец `en`
  `why-reasons.json`, тест сверяет побайтно; RU и StringTable — MS-T-28). Новый ключ `ms.begin.already` («Maneuver
  already begun — Enter confirms») — тост клавиши M в черновике (03 §3.2, B-03).

### 4.3. `metadata.lastMovement` (новое, публичное, аддитивное)

```json
{
  "lastMovement": {
    "seq": 128,
    "playerId": "u-host",
    "source": "MANEUVER",
    "sourceRef": "maneuver:3:127",
    "boost": { "cardId": "card-42", "catalogId": "c-17", "name": "Gaze of Stone", "value": 4 },
    "moves": [
      { "order": 0, "fighterId": "f-medusa", "kind": "MOVE",
        "from": { "x": 2, "y": 3 }, "path": [ { "x": 3, "y": 3 }, { "x": 3, "y": 4 } ] }
    ]
  }
}
```

| Поле | Правило |
|---|---|
| `seq` | равен `sequenceNumber` состояния после применения этого перемещения; пишется на итоговом состоянии действия, поэтому при передаче хода в том же seq (MS-E-45) и после дренажа выборов значение то же |
| `playerId` | игрок, чья команда или выбор двигали бойцов; для PLACE бойца соперника — тот, кто выбирал |
| `source` | `MANEUVER` — из `executeManeuver`; `EFFECT` — из резолва MOVE/PLACE; `sourceRef` — `maneuverId` или id pending-эффекта. Перемещения способностей героев (например, `abilities/heroes/ms-marvel.handler.ts:170-185`) и реакций следа не пишут — клиент для них берёт канонический путь (§4.6, MS-E-109) |
| `boost` | только для `MANEUVER` с картой; `null` без буста и всегда у `EFFECT`. Все поля публичны, `cardId` (instance id) тоже: карта уже лежит в сбросе владельца с тем же id, а сброс сопернику виден (MS-Q-05, закрыт в MS-T-14). `catalogId` = `Card.cardId`; `value` — напечатанный BOOST, `null`, если его у карты нет (до MS-T-20 такой буст принимается как +0) |
| `moves` | в порядке применения, `order` = индекс в массиве; `from` — позиция бойца перед этим ходом (после предыдущих ходов того же манёвра); для `MANEUVER` без движения и для эффекта, решённого как «остаться», — `[]`; бойцы, оставшиеся на месте, не пишутся |
| `kind` | `MOVE` — путь по шагам; `PLACE` — `path` из одной конечной клетки, клиент показывает перенос без пути (MS-T-16) |
| `path` | без стартовой клетки (формат `maneuver.moves[].path`); для `MOVE` из манёвра — путь, присланный клиентом (как есть, в том числе с возвратом на старт); для MOVE-эффекта — `canonicalPath` сервера; для PLACE — `[цель]` |
| Жизнь поля | заменяется следующим записанным перемещением; клиент использует путь, только если `lastMovement.seq == seq` применённого снапшота |
| Хранение | `serialize`/`deserialize` (`backend/src/games/game-state.service.ts:556-790`) переносят метаданные явным списком коротких ключей; поле добавляется ключом `lm`. Сейвы без поля читаются как «следа нет» (MS-E-108) |
| Приватность | поле проходит через `filterPrivateData` как часть `metadata` (`game-state.service.ts:809-860`, копирование `{ ...state.metadata }`); содержит только публичную информацию |
| Совместимость | добавление поля обратно совместимо (`docs/game-design/16-network-contract.md` §8); снапшот передаётся строкой JSON в поле `state: String` (`backend/src/games/dto/gameplay.dto.ts:504-505`, `game-actions.resolver.ts:78` — `JSON.stringify(state)`; клиент разбирает в два этапа — `S08Contracts.cpp:469`), поэтому схема GraphQL не меняется |
| Чтение клиентом (MS-T-15) | клиент читает `metadata.lastMovement` из JSON снапшота (запрос `gameState`, ответ мутации, подписка) с полными именами полей; `lm` — только ключ в БД. Поля нет в старых сейвах и в играх без записанного перемещения — это «следа нет». Выбор пути — по §4.6. След описывает только записанные перемещения: в том же seq способность или реакция (например, хук начала хода после передачи хода) может сдвинуть того же бойца дальше, и тогда последняя клетка его `path` не совпадёт с позицией в снапшоте; правило для этого случая задаёт MS-T-15. Неизвестные поля клиент игнорирует: `metadata` в UE хранится сырой JSON-строкой (`S08Contracts.cpp:512`) |

### 4.3.1. `metadata.skippedEffects` (DE-016, публичное, аддитивное)

Эффект без допустимых целей сервер пропускает и не ждёт ввода (D-DE-11, SD-10, SD-16;
`backend/src/game-engine/effects/pending-targets.ts`). Каждый пропуск оставляет заметку:

```json
{
  "skippedEffects": [
    { "n": 3, "seq": 41, "reason": "NO_VALID_TARGETS", "playerId": "u-host",
      "effectId": "s1-e1-p0", "kind": "PLACE", "text": "Place Ghost in any space." }
  ]
}
```

| Поле | Правило |
|---|---|
| Когда пишется | (1) выбор MOVE/PLACE/TARGET_FIGHTER во главе очереди без цели — при открытии на пустой очереди (эффект карты, хук способности героя) и при дренаже после каждого resolve/decline; (2) автоматический эффект без целей (урон, лечение, MOVE без бойцов) — там, где раньше был только `message: 'No valid targets'` в `appliedEffects` |
| Что считается целью | MOVE/PLACE — допустимый боец (как в резолве: `fighterIds`, живой, кроме возврата побеждённого; владелец, если не `anyOwner`; баннер) со свободным проходимым пространством, кроме своего; MOVE — в пределах `value` шагов (`computeReach`), с учётом `canPassThroughEnemies`; зона `zoneFighterName`, если задана. TARGET_FIGHTER — живой боец из `targetFighterIds`. Доска без данных клеток не судится — выбор остаётся |
| Очередь | проверяется только голова: выборы перед ней ещё двигают бойцов, поэтому следующий проверяется, когда станет головой. Боец EACH-эффекта, запертый только предыдущим бойцом той же пачки, не пропускается |
| `n` | сквозной номер в партии (1, 2, …). Клиент объясняет каждую заметку с `n` больше последнего показанного; при первом снапшоте (вход, переподключение) запоминает максимум `n` без показа |
| `seq` | `sequenceNumber` состояния, на котором сделан пропуск; снапшот, где заметка появилась впервые, имеет `seq` ≥ этого значения. Для диагностики, не для отбора |
| `reason` | пока только `NO_VALID_TARGETS` → ключ `why.effect.no.targets` (CUE-004) |
| `playerId`, `kind`, `effectId`, `text` | чей был выбор; тип выбора (`PendingEffect.type`) или эффекта (`EffectType`); id выбора или эффекта карты; печатный текст, если есть |
| Хранение | последние 8 заметок (`SKIPPED_EFFECTS_KEPT`), старые первыми; ключ в БД `se`; сейвы без поля — «пропусков нет». `seq` отдельно не увеличивается: заметка едет с мутацией, которая пропустила |
| Приватность и совместимость | как у `lastMovement` (§4.3): только публичные данные, проходит `filterPrivateData`, схема GraphQL не меняется |

### 4.4. Черновик (C++)

```cpp
enum class ES09DraftMoveStatus : uint8 { Ok, NeedBoost, Conflict };
struct FS09Reason { FName Key; TMap<FString, FString> Args; };          // why.* + аргументы
struct FS09DraftMove {
  FString FighterId; int32 DestX = -1, DestY = -1;
  int32 Order = 0;                                // позиция в moves[]
  TArray<FIntPoint> Path;                         // канонический, без старта; пуст = «остаться»
  ES09DraftMoveStatus Status = ES09DraftMoveStatus::Ok;
  int32 RequiredBoost = 0;  FS09Reason Reason;    // абсолютный нужный BOOST (§3.2)
};
struct FS09DraftOp { TArray<FS09DraftMove> Moves; FString BoostCardId; };  // запись стека отката (≤ 32)
// Стек: 33-я запись вытесняет старейшую; новый seq применённого снапшота или смена maneuverId — очистка;
// отказ сервера стек не трогает (MS-E-94, 95, 113).
struct FS09PreDraft { FString FighterId; int32 X = -1, Y = -1; bool bSet = false; int32 RequiredBoost = 0; };
```

Уточнение MS-T-05 (реализация): `FS09DraftMove` дополнительно несёт `Conflict` (`ES09DraftConflict`: missing,
not-yours, defeated, immobilized, duplicate, no-path — как `DraftConflict` сервера), `Base` (`FighterMovement`) и
`Allowance` (`Base + s`, бейдж «шаги/допуск»). `FS09DraftEval` — статический `Evaluate` над массивом ходов (поля хода
пишутся на месте) с итогом `SelectedBoost`, `MaxBoost`, ярусами каждого хода на `work_i` (`FS09ReachTiers`: база, буст,
`ReachMap` для превью), `Work` (`work_n`), счётчиками статусов и `HighlightCardIds`. `why.cell.unreachable {have}` —
`base + max(s, M)`: с лучшим бустом руки не хватает и его.

### 4.5. Описание вида (`FS08MoveDraftView`)

```cpp
enum class ES08RingState : uint8 { None, Conflict, NeedBoost, Destination, Sent, EnemyBlock, AllyPass,
                                   ReachBase, ReachBoost, PendingMove, PendingPlace };          // убывание приоритета
enum class ES08OutlineState : uint8 { None, Threat, LastTo, LastFrom };
enum class ES08GlyphState : uint8 { None, Invalid, Conflict, Order, Step, Hint };
struct FS08PlateView { int32 X, Y; ES08RingState Ring; ES08OutlineState Outline; bool bPathDot = false;
                       ES08GlyphState Glyph; int32 Steps = 0; int32 Chip = 0; int32 Order = 0; int32 Rank = 0;
                       uint8 Flags = 0; /* 1 hover, 2 sent, 4 pulse, 8 occupied, 16 leader pip */ };
struct FS08PathView  { FString FighterId; int32 Order; TArray<FIntPoint> Cells; /* со стартом */
                       bool bConflict = false; bool bNeedBoost = false; bool bSent = false; bool bPreview = false; };
struct FS08GhostView { FString FighterId; int32 X, Y; float Alpha; int32 Order; FString Label; };
struct FS08MoveDraftView { TArray<FS08PlateView> Plates; TArray<FS08PathView> Paths;
                           TArray<FS08GhostView> Ghosts; TArray<FString> FadedFighters; /* уходят с клетки призрака, 50 % */
                           FIntPoint Hover = {-1,-1}; uint32 Revision = 0; };
```

`BuildDraftView()` сводит состояния каждого пространства по приоритетам 03 §4.2a (одна запись на пространство, по
одному состоянию на канал). `AS08BoardActor::SetMoveDraftView` сравнивает `Revision` и обновляет только изменившиеся
экземпляры.

### 4.6. Cue перемещения

`FS08Cue` (`S08/S08FlowController.h:49-57`) получает поля `TArray<FIntPoint> Path` (со стартом), `int32 OrderInSeq`,
`uint8 Kind` (Move/Place) и `uint8 PathSource` (Trail/Canonical/Straight). Правила выбора пути:

| Случай | Поведение | MS-E |
|---|---|---|
| seq применён не по порядку (пропуск, барьер, переподключение — `skip`) | cue не выпускается, снап (§5) | MS-E-71, MS-E-68 |
| применённый seq, `lastMovement.seq == seq`, боец есть в `lastMovement.moves` | путь из следа (`Trail`) | — |
| применённый seq, позиция бойца сменилась, но следа этого seq нет (способность, реакция, старый сейв) или он про другого бойца | `canonicalPath` на позициях бойцов **до** применения снапшота с неограниченным допуском (`Canonical`); если пути нет — прямая from→to (`Straight`) | MS-E-108, MS-E-109 |

Дедуп `(cue, subject, seq)` (контракт D2) не меняется: у бойцов разный subject.

Уточнение MS-T-15 (реализация, `FS08FlowController::ComputeCues`):
- След читается только из метаданных самого тела (`Snapshot.Metadata`). Частичное тело без `metadata` — «следа нет»:
  более старый `lastMovement`, оставшийся в хранилище после слияния, никогда не относится к этому seq.
- Ход следа берётся, только если его `from` равен позиции бойца до снапшота, а последняя клетка `path` — позиции в
  снапшоте (`kind` MOVE или PLACE, у PLACE ровно одна клетка). Иначе — правило, отложенное в §4.3: способность или
  реакция сдвинула бойца в том же seq дальше (или боец указан в следе дважды), и путь строится как без следа
  (канонический, иначе прямая); у cue `bTrailMismatch`, в трассе хвост `trail=mismatch`, порядок — по следу.
- Канонический путь — `ComputeReachMap` с `MaxSteps = MAX_int32` и `BuildCanonicalPath` на бойцах **до** снапшота по
  обычным правилам: живые враги блокируют шаг, конечная клетка свободна на позициях до снапшота. Пути нет — прямая
  from→to, один шаг.
- Боец, чья позиция не изменилась, cue не получает, даже если след его упоминает (путь с возвратом на старт).
- `OrderInSeq` — 0..n−1: порядок `moves[]` следа, затем бойцы без хода в следе в порядке `fighters[]`. В наборе cue
  сначала перемещения по `OrderInSeq`, затем урон (каскад MS-E-48 строит MS-T-16).
- Доска канонического пути и подписей трассы — `boardState` тела, иначе применённая.
- Трасса при выпуске cue — по строке на перемещение: `MS-CUE move seq=<n> fighter=<id> order=<k> of=<n>
  kind=<move|place> steps=<n> source=<trail|canonical|straight> start=<мс> ms=<мс> snapped=<0|1>
  path=<CellLabel>>…[ trail=mismatch]`. `start`, `ms`, `snapped` — расписание §6.3 (`FS08MoveCueSchedule`, скорость
  «Обычно», потолки по умолчанию = `cue-table.json` CUE-007, тест `Unmatched.S08.MoveAnim.CueTrace` их сверяет).
  Скорость и reduced motion подключает MS-T-16 (гейт уже понимает поля `speed=` и `reduced=`). Проверка —
  `cue_contract.py check-trace` (коды M1..M5, `docs/unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md` §6).

### 4.7. Стиль подсветки в профиле досок

`unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json`: корневой блок `moveSelection` задаёт умолчания для всех
досок; `boards[i].moveSelection` переопределяет любые поля для одной доски и разрешён на **любой** поверхности (сетка,
`tiles`, `map-image`). Блок не вкладывается в `readability`: тот разрешён только доскам-картинкам, и парсер отклоняет
сетку с ним целиком (`S08BoardArt.cpp:978-984`, `S08BoardArt.h:372-374`). Парсер — новый `ParseMoveSelection` в
`S08BoardArt.cpp` (MS-T-08); файл общий с сессией ENV-MAPS, правка согласуется по 05 §4. Значения — ПРЕДЛОЖЕНИЕ,
подбираются live tune в MS-T-13.

```json
"moveSelection": {
  "plate": { "colorSrgb": "#F2E9D8", "keylineSrgb": "#111317", "fillAlpha": 0.18,
             "ringCenterUU": 36.0, "ringWidthUU": 3.5, "keylineUU": 1.5, "outlineInnerUU": 39.6,
             "outlineOuterUU": 41.0, "occupiedClearUU": 30.0, "pipCutDeg": 15.0, "zFill": 0.3, "zRing": 0.9 },
  "boostTier": { "dashCount": 12, "dashDuty": 0.6, "chipBgSrgb": "#161A28", "chipTextSrgb": "#F2ECDE" },
  "path": { "colorSrgb": "#FFF4DC", "widthUU": 6.0, "keylineUU": 1.5, "stepDotUU": 8.0, "z": 1.5 },
  "ghost": { "alpha": 0.45, "alphaSent": 0.30, "leavingFighterAlpha": 0.5 },
  "invalid": { "colorSrgb": "#D9483F", "ms": 350 },
  "lastMove": { "alpha": 0.6, "fadeMs": 300 },
  "anim": { "stepMs": 280, "capFighterMs": 1400, "capManeuverMs": 2400, "minStepMs": 90,
            "overlap": 0.3, "placeMs": 240, "hopHeightRel": 0.0, "turnMs": 120, "startTurnMs": 50,
            "travelLeanDeg": 10.0, "leanInMs": 60, "settleMs": 150, "easeEnds": false }
}
```

Переопределения на старте (03 §4.2b): `marmoreal-original` и `sarpedon-original` —
`"moveSelection": { "plate": { "colorSrgb": "#FFC857" }, "path": { "colorSrgb": "#FFC857" } }`. Ограничения парсера:
кольцо с кромкой в полосе [30, 40] uu, контур внутри 41,6 uu (как у `readability.reach` — `S08BoardArt.cpp:430-433`);
нарушение отклоняет документ (как остальные блоки, `S08BoardArt.cpp:385-386`).

`hopHeightRel` — доля роста фигурки; по умолчанию **0** — скольжение без подскока (по умолчанию, D-DE-02; 01 F-02;
R-14 live 2026-10-04: корень 3D-героя DE без подскока, отклонение ≤ 2 px, S4H-M17). Параметр остаётся для A/B (лист
DE-028); значение > 0 — только по слову пользователя (MS-Q-04 остаётся за ним, 01 «Резолюция ревью» п. 3).
`travelLeanDeg`/`leanInMs` — наклон корпуса в пути, `startTurnMs` — разворот к первому ребру, `turnMs` — доворот на
вершине, `settleMs` — возврат в Idle, `easeEnds` — ease-in-out на первом и последнем ребре (§6.3). Отсутствие обоих блоков → поведение по умолчанию из кода с теми же числами (тест «нет блока»,
на сетке и на карте).

### 4.8. Golden-фикстура паритета

`backend/prisma/fixtures/movement/<name>.move-fixture.json` (формат `unmatched.move-fixture/1`, развитие R4 §3.5).
Дополнения формата, сделанные в MS-T-02 (`name`, `description`, `cases`, `actor`, `board.lattice`, принудительный
`draft.moves[i].path`, сырой `fighters[i].movement`, `expect.serverDetail`, `expect.pendingRuleChange`, сравнение
`reach` множествами и `paths` точно), описаны в заголовке `backend/src/test/fixtures/move-fixture-state.ts` — это
эталон для читателя паритета в UE (MS-T-03). Тай-брейк сравнивает id пространств по порядку кодов (ordinal, с учётом
регистра). Наблюдение MS-T-02: резолв MOVE-эффекта отклоняет бойца с `isDefeated` и здоровьем > 0, а манёвр
принимает — к двум предикатам «живой» MS-T-03/MS-T-04. В MS-T-03 подтверждено чтением кода (прогоном — нет: фикстуры
pending MOVE с таким бойцом нет): резолв MOVE/PLACE требует `isLivingFighter` от двигаемого бойца, кроме revive-PLACE
(`game-action-executor.service.ts:617`); роль «двигаемый эффектом» на клиенте — `IsAliveBlocker()` (§3.1).

```json
{
  "schema": "unmatched.move-fixture/1",
  "expectSource": "manual",
  "board": { "key": "marmoreal", "topologySha256": "…" },
  "fighters": [ { "id": "f1", "ownerId": "p1", "position": {"x":2,"y":3},
                  "health": 16, "isDefeated": false, "movement": 3, "effects": [] } ],
  "hand": [ { "id": "c1", "boostValue": 2 }, { "id": "c2", "boostValue": null } ],
  "draft": { "moves": [ { "fighterId": "f1", "dest": {"x":4,"y":5} } ], "boostCardId": "c1" },
  "pending": { "type": "MOVE", "fighterId": "f1", "ownerId": "p1", "value": 0,
               "canPassThroughEnemies": false, "targetsOpponent": false, "zoneFighterName": null,
               "optional": true, "target": {"x":2,"y":3} },
  "expect": {
    "layer": "executor",
    "reach": { "f1": { "base": [[x,y],…], "boost": [[x,y],…] } },
    "paths": { "f1": [[x,y],…] },
    "status": { "f1": "ok" },
    "requiredBoost": { "f1": 0 },
    "server": "ok"
  }
}
```

- `draft` и `pending` взаимоисключающие. `pending.value` можно опустить (тогда допуск 1) — отсутствие и `0`
  различаются (MS-E-57, MS-E-76).
- `expect.layer`: `dto` — проверка class-validator над `ManeuverDto`/`PositionInput` (`gameplay.dto.ts:64-77`, случай
  «координата 20»); `validator` — только `validateManeuver`; `executor` — `executeManeuver` на полном `GameState`
  (сборщик §2.1); `resolvePending` — `resolvePendingEffect` для `pending-*`.
- `server` — `"ok"` или код из 02 §1.1. `board` может быть встроенной решёткой (`"lattice": {...}`) для сеточных
  случаев.
- Обязательный набор — все строки MS-E с тестом MS-AT-01/02/10/13/14 (02 §3) на трёх досках; минимум 40 фикстур, из них
  ≥ 15 с `expectSource: "manual"`. UE-тесты читают те же файлы, как сейчас читают топологию
  (`S08/S08BoardGraphTests.cpp:332-376`).

## 5. Сеть, задержки, рассинхрон

| Этап | Что защищает | Клиент | Состояние |
|---|---|---|---|
| `beginManeuver` | `expectedSequenceNumber` (`game-action-executor.service.ts:1656-1657`) | флаг «в полёте»; без автоповтора; `STATE_CHANGED` → refetch | MS-S-05 |
| Черновик | ничего не уходит на сервер | локально; кэш по `maneuverId` в `FS08FlowController` переживает переподключение в том же процессе (MS-T-04: ключ — матч, пользователь и `maneuverId`; переживает и сброс HUD при выходе из матча с повторным входом после перелогина, очищается принятым `leaveGame`, закрытым манёвром и `GAME_OVER`); при `!IsStreamReady()` подтверждение неактивно (MS-E-91) | MS-S-06..08 |
| `maneuver` | `maneuverId == pendingManeuver.id`, после успеха поле очищается (`:1708-1711`, `:1811`) | одна команда на подтверждение (`bManeuverInFlight`) | MS-S-09 |
| Дедлайн | нет ответа 10 с | запрос отменяется, исход «неизвестен» → `EnterMutationRecovery`, без повтора (MS-E-89) | MS-S-10 |
| Снапшот раньше HTTP | WS принёс снапшот, закрывший мой `maneuverId` (или открывший мой `pendingManeuver` после `begin`) | гейт `bManeuverInFlight` снимается применением снапшота; поздний HTTP-ответ — только трасса `MS-NET late-reply` (MS-E-90). Сейчас гейт снимается только в `OnDone` (`S08FlowController.cpp:1714, 1722`) | MS-S-09 → MS-S-01 |
| Обновление авторизации | `S08FlowController.cpp:1724-1727` — команда не пересылается | черновик остаётся в MS-S-06/07, баннер `why.auth.refreshed`, повтор — игроком (MS-E-92) | MS-S-06/07 |
| Исход неизвестен | GD-037: без повтора (`S08FlowController.cpp:1729-1733`) | recovery-lock; свежий снапшот решает (предвыбор переносится, MS-E-84) | MS-S-10 |
| Дубли HTTP-эхо и WS | seq-guard, один cue на seq (`S08FlowController.cpp:1327-1358`) | анимация по первому применению seq (QA-007) | MS-P-01/02 |
| Барьер, пропуск seq | cue не выпускается | снап без анимации (MS-E-71) | — |
| Снапшот с новым seq во время черновика | — | черновик пересчитывается §3.2 (Conflict/NeedBoost); стек отката очищается | MS-S-06/07 |

Уточнение MS-T-06 (реализация): дедлайн считает `FS08FlowController` (`TickConnectivity`), а не таймаут HTTP-модуля —
так одинаково работают живая сеть и офлайн-харнесс тестов. Команда `beginManeuver`/`maneuver` получает токен; через 3 с
`IsCommandSlow()` (баннер `why.syncing`, трасса `MS-NET slow`), через 10 с запрос отменяется (`CancelRequest`, `Execute`
возвращает запрос), трасса `MS-NET deadline`, `EnterMutationRecovery` без повтора. Снапшот снимает гейт, если его seq
больше seq отправки и **его собственные** метаданные показывают итог (`begin` — открыт мой `pendingManeuver`;
`maneuver` — `pendingManeuver` с этим id закрыт); частичное тело без `metadata` ничего не доказывает. Ответ на уже
закрытый токен (снапшотом, дедлайном или отменой) не трогает гейт и не показывает ошибок: трасса
`MS-NET late-reply op=<…> ok=<0|1> settled=<snapshot|deadline>`. Отступление от буквы MS-E-90 («только трасса»), решение
ревью MS-T-06: **успешное** позднее тело всё же сливается через seq-guard (`MS-NET late-reply merged seq=<n>`) — события
WS не несут `decks`, и без него счётчик колоды после своего `begin`/`maneuver` остаётся устаревшим (нужен MS-S-04). Тело
того же seq сливается без cue; более новое применяется (после дедлайна оно и есть исход и снимает recovery-lock). Ход,
открытый в момент выхода из матча, истечения сессии или отмены комнаты, закрывается без дедлайна.

`expectedSequenceNumber` в `maneuver` не добавляется, пока не найдено, что состояние может измениться между `begin` и
`maneuver` не по воле игрока (MS-Q-06; проверка — MS-T-14). Если найдётся — добавить необязательным полем DTO.

Оптимистичного перемещения нет (MS-D-01). После Enter: линии и призраки в стиле «отправлено» (V-10); при успехе —
анимация по снапшоту; при отказе — по классу кода (02 §1.1).

| ID | Требование | Тест |
|---|---|---|
| MS-R-55 | Черновик восстанавливается после переподключения в том же процессе, если `pendingManeuver.id` не изменился; иначе сбрасывается | MS-AT-20 |
| MS-R-56 | При неизвестном исходе команда не повторяется; клиент ждёт свежий снапшот (recovery-lock) | MS-AT-20 |
| MS-R-73 | Дедлайн ответа на `beginManeuver`/`maneuver` — 10 с, затем MS-S-10 без повтора; снапшот, подтвердивший исход, снимает гейт раньше HTTP-ответа; при `!IsStreamReady()` подтверждение неактивно, черновик сохраняется; после обновления авторизации команда не повторяется автоматически | MS-AT-19, MS-AT-20 |

## 6. Презентация в UE 5.8

### 6.1. `US08MoveHighlightComponent`

- Владелец — `AS08BoardActor`. Создаётся один раз при сборке доски; пересоздаётся только при `RequestFullRebuild`
  (live tune reload).
- Подложки — `UInstancedStaticMeshComponent` × 4: `PlateFill`, `PlateRing`, `PlateOutline`, `Glyphs`. Экземпляров — по
  числу пространств доски (`IsBoardSpace`), созданы заранее, скрыты масштабом 0 или флагом в custom data.
  `NumCustomDataFloats = 6`: `[0]` состояние канала (кольцо/контур/глиф — в своём ISM), `[1]` шаги / 10,
  `[2]` чип (+N / +k), `[3]` индекс глифа в атласе, `[4]` флаги (1 hover, 2 sent, 4 pulse, 8 occupied, 16 leader pip),
  `[5]` индекс цвета (подложка / команда P1 / команда P2 / ошибка). Материал читает custom data через
  `PerInstanceCustomData` в вершинном шейдере и передаёт в пиксельный через VertexInterpolator (R4 §5.1). Вырез под
  ромб лидера и пустой круг r ≤ 30 uu на занятом пространстве — в материале по флагам 8/16 (03 §4.1).
- MPC `MPC_UM_MoveSelection`: время пульса, флаг reduced motion, цвета из `moveSelection` (чтобы live tune не трогал
  экземпляры).
- Путь — **ISM, не SplineMesh**: связи и шаги сетки — прямые отрезки между центрами (MS-E-26, MS-E-27), поэтому
  достаточно `PathSegments` (единичный отрезок, масштаб по длине, поворот по направлению), `PathDots` и `PathHeads`.
  Цвет, пунктир (NeedBoost/Conflict) и «отправлено» — в custom data. Совпадающие сегменты разных бойцов смещаются
  поперёк (03 §4.2a). Заранее создаётся 128 экземпляров сегментов; при нехватке ISM дорастает `AddInstance` с трассой
  `MS-HL pool.grow n=<k>` — потолка длины пути нет (MS-E-03, MS-E-100). Весь путь — 3 draw call независимо от числа
  путей и сегментов.
- Призраки: на каждого бойца с ходом — компонент с тем же мешем фигурки (skeletal — замороженная поза idle; серая
  фигурка — static), материал `M_UM_Ghost` с dithered opacity mask по параметру `Fade` (Custom Primitive Data, индекс
  11 из `CUE-DISPATCHER.md`), `CastShadow = false`, без коллизии. Фигурка, уходящая с клетки чужого призрака, получает
  `Fade = 0,5` (`FadedFighters`).
- Ассеты — в `/Game/S08/MoveSelection/` (упаковывается через `/Game/S08`, `DefaultGame.ini:17`). Материалы, которые
  назначаются в рантайме, создаются с флагами usage: `bUsedWithInstancedStaticMeshes` (подложки, путь),
  `bUsedWithSkeletalMesh` (скелетный призрак). При загрузке компонент пишет трассу
  `MS-HL assets plate=<имя> path=<имя> ghost=<имя>`; подстановка материала по умолчанию — ошибка гейта (MS-R-74).
- Бейджи: порядок и «шаги/допуск» — экранные UMG-виджеты (проекция `CellToWorld` в экран) в слое HUD, чтобы
  подчиняться UI-ACC-001 и StringTable; пересчёт в том же кадре при изменении размера вьюпорта (MS-E-105). Плашки HUD
  учитывают их в раскладке (`PLATE overlapReachable`).
- До арт-приёмки (MS-T-27) новая подсветка включается флагом `-S08MovePlates`; без флага рисуется прежнее кольцо
  `readability.reach`, чтобы не менять эталонные кадры сессии ENV-MAPS (05 §4). После приёмки флаг становится значением
  по умолчанию, старый путь удаляется.
- `SetSelectedFighter(Id, Reachable)` остаётся как совместимая обёртка: строит `FS08MoveDraftView` из множества и
  вызывает `SetMoveDraftView` — старые вызовы (`S08FlowGameMode.cpp:743, 746, 953, 977, 999, 1102, 1496`) работают без изменений до перевода.

Уточнение MS-T-08 (реализация, 2026-10-04):
- **MPC не заводится.** Стиль (`moveSelection`) идёт скалярными и векторными параметрами MID каждого из четырёх ISM
  (`S08MovePlateSpec::Param*`); live tune меняет параметры MID и не трогает экземпляры — то же свойство, что у MPC,
  без лишнего ассета и без глобального состояния мира. Время пульса и reduced motion — параметрами MID в MS-T-16.
- **Материал** `M_UM_MovePlate`: unlit, translucent (заливка 18 % / 35 % требует прозрачности; masked дал бы дизеринг под
  TSR), `bUsedWithInstancedStaticMeshes`, без тумана (`Apply Fogging` off), responsive AA, emissive через
  EyeAdaptationInverse (правило игрового слоя). Экземпляр — плоскость движка 100 uu в масштабе 2 × 44 / 100; форму рисует
  Custom-узел по LocalPosition (начало экземпляра) и custom data, переданным в пиксельный шейдер двумя VertexInterpolator.
  Порядок слоёв — `TranslucentSortPriority` 10..13 (заливка < кольцо < контур < глиф). Сборка —
  `tools/art/move_selection/ue_move_plate_material.py` (UnrealEditor-Cmd, `-run=pythonscript`), `--check` сверяет имена
  параметров с `S08MoveHighlight.h`. Ассет лежит в gitignored `Content/` и добавлен принудительно, как остальные `/Game/S08`.
- **Каналы.** Состояние канала = custom data `[0]`; скрытый экземпляр — масштаб 0 (пикселей нет). Кольцо: V-01 сплошное,
  V-02 пунктир `dashCount`/`dashDuty`, V-04 двойное (внутреннее r 26), V-04b с пунктирным внешним, V-09 двойное пунктирное
  `#D9483F`, V-10 −30 %, V-07 штриховка 45° в полосе `occupiedClearUU`..кромка, V-06 только при наведении, V-11/V-12 длинный
  пунктир, V-17 тонкое кольцо под фигуркой (радиус × масштаб фигурки — custom data `[1]`, исключение из правила «ничего при
  r ≤ 30»). Заливка: V-01/V-04/V-04b `fillAlpha`, V-10 × 0,7, V-07 тёмная 35 %, V-11 10 %. Контур: V-14/V-15 окружность цвета
  команды (у P2 — шесть разрывов вместо шестигранника, до MS-T-17), V-16 четыре скобки. Глиф в мире рисует только X (V-08) и
  «!» (V-09); порядок, шаги и подсказки — экранные бейджи (MS-T-10). Сетка (`Shape` 1) — скруглённый квадрат 0,82 клетки.
- **Схема `moveSelection`** дополнена блоком `candidate` (`radiusUU` 18,9, `widthUU` 1,2, `alpha` 0,7, `z` 1,6 — полоса
  кольца выбора `SM_Marker_SelectionRing` 17,8–20 uu, над пьедесталом) для V-17 (DE-017). Неизвестный блок или поле —
  ошибка документа (опечатка в live tune не становится тихим умолчанием); поля `note*` допускаются.
- **Трассы:** `MS-HL assets plate=<имя> path=- ghost=- plane=<меш> ready=<0|1>[ fallback=legacy-ring]`, `MS-HL build n= spaces=
  channels=4 shape=circle|square style=code|root|board plate=#.. path=#.. ready=`, `MS-HL geom ... ok=` (кольцо с кромкой,
  контур, круг занятого пространства, вырез под ромб лидера: `pipHalf` — угол, который ромб с кромкой занимает в полосе
  кольца, 9,2° при вырезе 15°), `MS-HL view source=draft|inspect|pending|reach|bench rev= plates= fill= ring= outline= glyph=
  paths= updates= hover=` (только когда что-то изменилось).
- **Провайдер вида.** `AS08BoardActor::SetSelectedFighter` с плашками строит вид через провайдер режима игры
  (`BuildMoveDraftViewFor`: черновик, осмотр MS-S-02/03, pending MOVE/PLACE), иначе `ViewFromReachable`; `Tick` перерисовывает
  плашки по ключу черновика (ревизия, режим, полёт, предвыбор, выбранный боец, наведение). Без флага или без материала —
  прежнее кольцо `readability.reach`.
- **`-BenchMoveDraft`:** формат расширен полем `moveOrder` (`[{fighterId, delta ±1}]`) — сцена 2 строит Conflict сменой
  порядка; MS-T-17: `lastMovement` синтезирует `metadata.lastMovement` бенч-seq (формат 04 §4.3, клетки — id пространств или [x, y], путь кончается на клетке бойца фикстуры; без черновика — MS-S-00), см. «Уточнение MS-T-17» ниже. MS-T-12: блок `pending` (`type` MOVE | PLACE,
  `fighterId`, `value`, `optional`, `targetsOpponent`, `to`) синтезирует `metadata.pendingEffects` зрителя вместо
  `pendingManeuver` — сцена MS-S-12 (V-11/V-12, с `to` — V-04 и путь); с `boostCardId`/`moves`/`moveOrder`/`selected` несовместим. `FS09CommandUi` в `-ArtPreview`
  без сервера работает (проверено прогоном). Абсолютный путь `-BenchFixture` вне `Config/Bench` принимает редакторный
  клиент; упакованный — **не проверено** (сцена худшего случая — MS-T-27).
- **Уточнение MS-T-17 (2026-10-05, прогон D).**
  - **Модель.** Чистая модель взгляда соперника — `S09/S09OpponentView.*`, в игре — `S08FlowGameModeOpponent.cpp`.
  - **Подсветка последнего хода.** Она приходит в вид подложек полем `FS08MoveDraftInput::LastMove`: старты дают
    LastFrom, концы — LastTo, промежуточные клетки пути — `bPathDot`. Цвет — вид команды ходившего, абсолютный или
    `-S08TeamColorMode`.
  - **Слияние.** Подсветка вливается в любой вид: в наблюдение (MS-S-00, источник `last`), в черновик и в pending. При
    обычном выборе без черновика сохраняется набор досягаемости, как его рисует `ViewFromReachable`.
  - **Затухание.** Скаляр `LastMoveFade` материала (граф v2, только MID канала контура) умножает оба состояния
    LastTo/LastFrom. Ключ перерисовки `SyncMovePlates` включает ревизию трекера.
  - **Флаг.** Без `-S08MovePlates` (до MS-T-27) подсветки на доске нет, а индикатор, лента и стрелка работают.
  - **Новый след при видимом старом.** Новый след заменяет старый сразу, без 300 мс затухания: альфа одна на все
    контуры последнего хода, а доска в этот момент и так меняется под новым ходом.

| ID | Требование | Тест |
|---|---|---|
| MS-R-49 | С новой подсветкой (флаг `-S08MovePlates`, после MS-T-27 — по умолчанию) выбор бойца, hover и смена буста не спавнят и не уничтожают акторы и компоненты; меняются только custom data, трансформы и видимость экземпляров (рост ISM пути — `AddInstance`, не новый компонент) | MS-AT-21 |
| MS-R-50 | Стиль читается из корневого `moveSelection` и `boards[i].moveSelection` (любая поверхность); `live_tune.py reload` применяет его без перезапуска; без блоков — значения по умолчанию | MS-AT-34 |
| MS-R-51 | Линия пути — ISM сегментов, точек и наконечников; перестраивается только при смене пространства под курсором или черновика; ISM дорастает без потолка длины | MS-AT-22, MS-AT-40 |
| MS-R-52 | Призраки — masked dithered, без теней и коллизии, не больше числа бойцов с ходами | MS-AT-23, MS-AT-41 |
| MS-R-74 | Новые ассеты лежат в упаковываемой папке (`/Game/S08/MoveSelection/`), материалы имеют нужные флаги usage; в упакованном клиенте трасса `MS-HL assets` называет именно эти материалы | MS-AT-30 |

### 6.2. Наведение и выбор

- Клетка под курсором: луч мыши (`APlayerController::DeprojectMousePositionToWorld`) пересекается с плоскостью поля
  (z = 0) → `WorldToCell`. Попадание в декор 3D-окружения ENV-MAPS (P8 «путь 1») и в фигурки на клетку не влияет;
  отдельный trace channel не нужен. Наведение считается в `Tick` GameMode; кэш `HoverCell`; при смене —
  `FS09CommandUi::SetHover(cell)` → новый `FS08MoveDraftView`. Путь берётся из уже посчитанной `ReachMap` (без BFS).
- Выбор бойца: `GetHitResultUnderCursor(ECC_Visibility)` по акторам фигурок (как сейчас, `S08FlowGameMode.cpp:993-1000`)
  — только после правила MS-R-71: в MS-S-07/12 клетка из луча, входящая в V-01/V-02 выбранного бойца, побеждает
  попадание в фигурку.
- Правило клика на отпускании (MS-R-34): `WasInputKeyJustPressed(LeftMouseButton)` запоминает пространство,
  `WasInputKeyJustReleased` выполняет действие при совпадении. Потеря фокуса вьюпорта (`FSlateApplication`/
  `UGameViewportClient` — способ определения выбирается в MS-T-07) или отсутствие клетки под курсором сбрасывают
  сохранённое нажатие и hover (MS-E-104). Придёт ли событие отпускания после Alt+Tab — **не проверено**; правило от
  этого не зависит.
- Уточнение MS-T-07 (реализация): семантика ввода — чистая логика `FS09MoveInput` (`S09/S09MoveInput.h`) над
  `FS09CommandUi`: клавиши 03 §3.2, лестница Esc/ПКМ, клик на отпускании, приоритет MS-R-71, панель буста MS-S-08 со
  стрелочным курсором, подтверждение истощения MS-S-04; режим игры только опрашивает ввод и применяет результат
  (`ApplyMoveInput`). Плоскость поля — z актора доски; фокус — `FApp::HasFocus() && Viewport->HasFocus()`, без фокуса
  нажатие и hover сбрасываются. Предвыбор (MS-S-02/03) живёт в `FS09CommandUi::PreDraft`, переживает перечитывания
  (в том числе MS-S-10), снимается при выходе из хода; при открытии черновика с новым id переносится ходом по новой руке
  (`MS-DRAFT op=assign src=<источник предвыбора>`) или даёт `why.predraft.lost`. Стек отката — `FS09CommandUi::UndoStack`
  (запись до операции: назначение, снятие, буст, порядок, сброс Esc, перенос предвыбора). Клик в pending MS-S-12 с MS-T-12
  идёт тем же отпусканием (`FS09MoveInput::PendingClick`, MS-R-71: пространство выбранного бойца — цель, иначе боец эффекта); бейджи, призраки (и 50 % уходящей фигурки, `FadedFighters`) и кнопки ▲/▼ панели — MS-T-10/11.

### 6.3. Анимация перемещения

Чистая функция (тестируется без мира):

```
schedule(moves[], p, speed, reducedMotion) -> [{fighterId, startMs, stepDurMs, steps, snapAtMs}]
  if reducedMotion or speed == None: все snap в 0
  mul  = {Fast 0.5, Normal 1, Slow 1.5}[speed]
  base = p.stepMs*mul; capF = p.capFighterMs*mul; capM = p.capManeuverMs*mul; minStep = p.minStepMs  // без mul
  1) для каждого i: PLACE → steps_i = 1, dur_i = p.placeMs*mul;  MOVE → dur_i = min(steps_i*base, capF)
  2) total = Σ_{i<n-1} (1-overlap)*dur_i + dur_{n-1};  k = min(1, capM/total)
  3) stepDur_i = max(dur_i*k/steps_i, minStep);  act_i = stepDur_i*steps_i
  4) start_0 = 0;  start_i = start_{i-1} + (1-overlap)*act_{i-1}            // от фактических длительностей
  5) j = первый i с start_i + act_i > capM (+1 мс допуск);  бойцы j..n-1 — snap
     snapAt = конец последнего анимированного бойца (start_{j-1} + act_{j-1}; 0 при j = 0);
     все snap-бойцы встают в snapAt одновременно, в порядке moves[] (не раньше, чем освободивший их цель боец
     доехал — он либо анимирован и закончил к snapAt, либо снапается в тот же момент раньше по порядку)
```

Контрольные значения (MS-AT-24): 1 шаг — 280 мс; 9 шагов одного бойца — 1400 мс (155,6 мс/шаг); 4×7 «Обычно» — конец
2400 мс, шаг 110,6 мс; 4×7 «Медленно» — конец 3600 мс; 9×9 «Обычно» — 3 анимации (концы 810, 1377, 1944 мс) и 6 snap в
1944 мс; 9×9 «Быстро» — 1 анимация, 8 snap в 810 мс; PLACE — 240 мс.

- Шаг = ребро графа. Время шага (`stepDur_i` выше) одно для коротких и длинных рёбер; скорость внутри ребра постоянна
  (линейно по сегменту); на промежуточных вершинах нет ни остановки, ни замедления (SD-50 п. 1; R-14 live 2026-10-04:
  у DE одно время на ребро для 131–392 px, два ребра — 683 мс без паузы; TL `move_edge`, `move_two_edges`).
- Ease-in-out (sine) на первом и последнем ребре пути — параметр `easeEnds`, по умолчанию **выкл** (02 «Резолюция
  ревью» п. 1): у DE ease нет, резкую остановку прячет возврат в Idle. A/B-кадр — DE-028.
- Подскок `z = hopHeight * sin(π t)` на каждом ребре (`hopHeight = hopHeightRel × рост фигурки`) остаётся в коде как
  параметр; по умолчанию `hopHeightRel = 0` — подскока нет (по умолчанию, D-DE-02; 01 F-02).
- Поза перемещения: процедурный наклон корпуса вперёд по ходу `travelLeanDeg` 10°, вход за `leanInMs` 60 мс от старта
  движения (0 = выкл). Кадр LungeAttack для позы не держим: выпад у нас — сигнал удара (01 F-03); нового клипа нет
  (D-11). Основание — поза рывка 3D-героя DE (S4HV-O01).
- Разворот к первому ребру — не дольше `startTurnMs` 50 мс; доворот к следующему ребру на вершине — `turnMs` 120 мс на
  ходу, без остановки (DE ~100–150 мс, s04 517.917–518.067).
- После прибытия — возврат в Idle за `settleMs` 150 мс: наклон → 0, ориентация → правило половины поля
  (`S08FighterActor.cpp:550-561`; DE 130–170 мс, S4HV-M05, TL `hero_move_return_to_idle`). Поворот к цели и итоговое
  направление — ART-012, за пользователем.
- Старт — в кадр применения снапшота с перемещением (MS-R-22, SD-13).
- Посадку жетона DE (134–167 мс) не переносим: жетонов нет, все 6 фигур скелетные — одно правило на всех.
- PLACE (`kind: PLACE`): dithered fade-out 120 мс в старой точке и fade-in 120 мс в новой (решение AD-CNF-29 в пользу
  «телепорт с переходом» — ПРЕДЛОЖЕНИЕ); reduced motion — snap.
- Пропуск: любая клавиша или кнопка мыши, кроме Space и колеса (они — камера), — все активные анимации к финалу за
  ≤ 1 кадр (MS-E-70, MS-E-110).
- Новое событие той же фигурки — `jump_to_final`; переподключение — `skip`; reduced motion — `snap` (CUE-007 в
  `cue-table.json`).
- Каскад: cue урона (`FighterDamaged`) того же seq стартует после конца анимации перемещения цели (MS-E-48).
- Звук: тик шага на каждом шаге (CUE-007, ≤ 1 одновременного); пыль Niagara на конечном пространстве — CPU,
  детерминированный seed. Ассетов сейчас нет (`status: missing`) — fallback cue-table: Warning без падения.
- Контракт CUE-007 (`cue-table.json`, сейчас `duration_per_step_ms: 280`, `duration_ms: null`; 07 csv строка 8
  «280*N») дополняется потолками этой функции, а `cue_contract.py` (`_duration`, `:168-171`) считает длительность по
  ней — MS-T-15. Строка CUE-007 в 07 csv правится в MS-T-26 («280*N; ≤ 1400 на бойца; ≤ 2400 на манёвр; шаг ≥ 90»),
  префикс «280*» сохраняется для проверки `cue_contract.py:90-92`.
- Настройки игрока: `US08UserSettings` (`bReducedMotion`, `AnimSpeed`, `bScreenShake`), класс подключается строкой
  `GameUserSettingsClassName` в `DefaultEngine.ini`; флаги `-S08ReducedMotion`, `-S08AnimSpeed=<none|fast|normal|slow>`
  перекрывают сохранённое. UI-ACC-005 «без тряски» выключает встряску V-08 (CUE-004). Экрана паузы UI-SCR-PAUSE, где
  02 размещает настройки, в клиенте нет (`grep` по `unreal/Unmatched/Source` — 0); до него настройки меняются флагами и
  ini.
- Полноценный cue-диспетчер GD-044 этим планом не делается: `FS08MoveAnim` реализует только CUE-007 и соблюдает его
  поля контракта, чтобы позже стать обработчиком диспетчера.

Уточнение MS-T-16 (реализация, 2026-10-05; журнал `de-footage/task/runs/D-2026-10-04.md`):
- **`S08/S08MoveAnim.*`.** `FS08MoveAnim::Schedule` — расписание выше с настройками (`FS08MotionSettings`: reduced motion
  или скорость «нет» — все snap в 0, иначе `FS08MoveCueSchedule` с множителем); `BuildPlans` — план на бойца (мировые
  точки пути со стартом, слот seq, покой-разворот на старте и на финише по правилу половины поля); `Sample` — поза в
  любой момент плана (скольжение по ребру, подскок-параметр, наклон, разворот и доворот, возврат в Idle, PLACE с
  растворением). Чистые функции, тесты `Unmatched.S08.MoveAnim.Schedule`, `.Pose`.
- **Фигура.** `AS08FighterActor::PlayMove / TickMove / FinishMove`: двигается сам актор (кольца, свет героя, тень и ярлыки
  едут с фигурой); логическая позиция — по снапшоту: капсула клика на время хода закреплена на клетке снапшота, база и
  серый короб клик не ловят (MS-R-53). Поворот и наклон — у меша фигуры (v2 смотрит по +X, кандидат Medusa и блокауты —
  по +Y). Повторное применение снапшота с той же клеткой ход не прерывает; новая клетка или смерть — `jump_to_final`.
  PLACE у v2-фигуры — MIC растворения DE-011 в стиле fade (120 + 120 мс), после — MI тела; без MIC — перенос в середине.
- **Часы и пропуск.** Ходы идут по игровым часам режима (`NowMs`), старт — в кадре применения снапшота (`HandleCues`
  сразу после синхронизации доски, SD-13). Пропуск — любая клавиша или кнопка мыши, кроме Space и колеса
  (`S08Motion::SkipsMove`), в том же кадре; ввод не поглощается и работает по логическому состоянию (MS-E-70, MS-E-110).
- **Каскад MS-E-48.** Урон того же seq по движущемуся бойцу (не постановка боя DE-018) ждёт прибытия цели; строка
  `CUE damage … after=move ms=<n>`, показ — `MS-ANIM cascade damage …`; пропуск делает его срочным.
- **Трассы.** `MS-ANIM settings …` (старт), `MS-ANIM play seq= moves= animated= speed= reduced= end=`, `MS-ANIM skip key=
  fighters= frame=`; строки `MS-CUE` получают хвост ` speed=<none|fast|normal|slow> reduced=<0|1>` и расписание с этими
  настройками — `cue_contract.py check-trace` их уже понимает.
- **Настройки — отклонение от плана.** `US08UserSettings` — не подкласс `UGameUserSettings`, а обычный объект
  конфигурации в том же `GameUserSettings.ini`; `GameUserSettingsClassName` в `DefaultEngine.ini` не меняется. Причина
  (замер тестом `Unmatched.S08.MoveAnim.Settings`): подкласс читает ключи только из своей секции, и
  `[/Script/Engine.GameUserSettings] FrameRateLimit=60` (ACC-022, правило 60 FPS из AGENTS.md) у него становится 0 — CDO
  родителя 60, CDO подкласса 0; так же терялись бы сохранённые разрешения, а скрипты демо (`tools/s09/run-*-demo.ps1`)
  правили бы игнорируемую секцию. `S08IconMotion::IsReducedMotion` теперь учитывает и сохранённый `bReducedMotion`.
- **Параметры A/B (DE-028):** `-S08MoveHop=<доля роста>`, `-S08MoveLean=<градусы>`, `-S08MoveEase`; по умолчанию —
  F-02 (подскока нет, наклон 10°, ease выкл).
- **DE-021 (2026-10-05).** Поза хода записана в `cue-table.json` CUE-007 блоком `pose` (`hop_height_rel` 0,
  `travel_lean_deg` 10, `lean_in_ms` 60, `start_turn_ms` 50, `turn_ms` 120, `settle_ms` 150, `ease_ends` false); тест
  `Unmatched.S08.MoveAnim.CueTrace` сверяет с ней умолчания `FS08MoveAnimParams` («код = cue-table»), схема и
  `cue_contract.py validate-table` её стерегут. Старт в кадре снапшота — `Unmatched.S08.MoveAnim.StartFrame` (один
  `ApplySnapshot`: синхронизация доски, затем cue; план своей фигуры с 0, через один кадр 60 FPS она уже на ребре).
  Кадры A/B — bench-флаг `-BenchMovePose=<мс>` (+ `-BenchMovePoseFighter=<id>`): фигура проходит два ребра в свою
  клетку фикстуры (`FS08MoveAnim::ReviewPath`, последнее ребро — боком к камере) и держится на `<мс>` хода во всех видах;
  трасса `MS-ANIM bench-pose …`. Кадры — `docs/game-design/evidence/DE-FOOTAGE/de021-ab-2026-10-05/`.
- **Не сделано здесь.** Встряски V-08 в клиенте нет — `bScreenShake` пока только хранится; пульса подложек нет в
  материале `M_UM_MovePlate` — выключать нечего; переподключение во время хода (`on_reconnect: skip`) — ход доигрывает,
  если клетка в барьерном снапшоте не изменилась (иначе `jump_to_final`); тик шага и пыль — MS-T-18; множитель скорости
  в бою — DE-025.

| ID | Требование | Тест |
|---|---|---|
| MS-R-53 | Расписание анимации — чистая функция с алгоритмом выше (масштаб, минимальный шаг, старты от фактических длительностей, одновременный snap не уместившихся); логическая позиция фигурки и хит-тест — по снапшоту, визуальная догоняет | MS-AT-24 |
| MS-R-54 | Reduced motion (флаг `-S08ReducedMotion` и `bReducedMotion` в `US08UserSettings`) даёт snap для перемещения, отключает пульсы, подскок (если высота > 0), наклон хода и встряску V-08; `bScreenShake = false` выключает встряску | MS-AT-33 |

### 6.4. Bench-сцена для кадров

`-Bench` получает параметр `-BenchMoveDraft=<абсолютный путь>`; он накладывается **поверх** `-BenchFixture` (захват
`gameState`, `kind: "gameState-query"` — `unreal/Unmatched/Config/Bench/S08BenchMarmoreal.json`; по умолчанию
`S08BenchCobble.json` — `S08FlowGameMode.cpp:6775-6781`):

- доска, игроки, бойцы и руки берутся из `-BenchFixture`;
- файл `-BenchMoveDraft` (формат `unmatched.move-draft/1`, `tools/s08/fixtures/move-draft/<board>-<scene>.json`, вне
  `Config/`, в pak не попадает) задаёт только: `draft` (id бойцов и instance id карты буста — из bench-фикстуры),
  `hover`, `selected`, `lastMovement` (для кадра соперника), `pending` (сцена 4);
- `pendingManeuver` клиент синтезирует: `{ id: "bench:<имя файла>", playerId: benchViewerId }`;
- id бойца или карты, которых нет в bench-фикстуре, — ошибка: трасса `MS-BENCH mismatch id=<id>`, черновик не
  открывается, кадр не снимается;
- для худшего случая (MS-E-112) — синтетический `gameState` с 9 бойцами на Sarpedon, путь передаётся в `-BenchFixture`
  абсолютным (принимает ли `-BenchFixture` путь вне `Config/Bench` — **не проверено**, проверка в MS-T-08).

Bench всегда идёт с `-ArtPreview` (`render_bench.py:384`); работа `FS09CommandUi` без сервера в этом режиме — **не
проверено**, проверяется в MS-T-08 первым шагом.

| ID | Требование | Тест |
|---|---|---|
| MS-R-61 | `-BenchMoveDraft` даёт одинаковые кадры при повторных запусках (отпечаток `RENDER` и трасса `MS-HL` совпадают) | MS-AT-30 |

## 7. Производительность

Ориентиры: 60 FPS упакованного клиента (`unreal/Unmatched/Config/DefaultGameUserSettings.ini`, `FrameRateLimit=60`),
ACC-022 1080p p95 ≤ 16,7 мс; демо двух клиентов — по 30 FPS (`tools/s08/run-phase2-demo.ps1`); HUD ≤ 0,5 мс GT и
≤ 0,3 мс GPU (HUD-RULES П8). Стоимость рендера сравнивается только `tools/art/render/render_bench.py` (`-Bench`, без
ограничения FPS), не по `gpuMs` в ограниченном режиме (AGENTS.md).

| Элемент | MVP (4 бойца) | Крайний случай (9 бойцов, допуск 9, Sarpedon — MS-E-112) | Как измерить |
|---|---|---|---|
| Пересчёт черновика (все ходы) | p95 ≤ 0,10 мс GT | p95 ≤ 0,25 мс GT | трасса `MS-PERF draft us=` (MS-AT-40) |
| Обновление вида на смену hover | p95 ≤ 0,20 мс GT | p95 ≤ 0,40 мс GT | `MS-PERF view us=` |
| Спавн акторов на выбор / hover | 0 | 0 | счётчик акторов в тесте (MS-AT-21) |
| Подложки + путь + призраки на GPU | ≤ +0,30 мс GPU на High 1080p против базового кадра | ≤ +0,50 мс | `render_bench.py` до/после (MS-AT-41) |
| Draw calls (базовый проход) | ≤ 7 + 4 × S | ≤ 7 + 9 × S | колонка `RHI/DrawCalls` CSV в новом варианте `render_bench.py` (MS-T-08) |
| Кадр с открытым черновиком | p95 ≤ 16,7 мс (ACC-022) | p95 ≤ 16,7 мс | упакованный Development (MS-AT-42) |

7 = 4 ISM подложек + 3 ISM пути; S — число секций материала меша фигурки (у призрака, `CastShadow = false`, теневых
проходов нет). S для фигурок MVP — **не проверено** (оценка S ≤ 2: MVP ≤ +15, крайний случай ≤ +25); MS-T-08
записывает фактическое S в трассу `MS-HL ghost sections=<S>`.

| ID | Требование | Тест |
|---|---|---|
| MS-R-57 | CPU-бюджеты таблицы выше выполняются (MVP и крайний случай) | MS-AT-40 |
| MS-R-58 | GPU-бюджет и бюджет draw calls выполняются на эталоне High (MVP и крайний случай) | MS-AT-41 |
| MS-R-59 | 60 FPS упакованного клиента и 30 FPS каждого из двух клиентов демо не ухудшаются | MS-AT-42 |

## 8. Подсказки ходов и бот (фаза 4, опционально)

- `scoreMoves(state, playerId, opts) → [{fighterId, dest, path, score, reasons[]}]` в
  `backend/src/game-engine/ai/score-moves.ts`. Признаки (R4 §6.2, стартовые веса): `canAttackAfter` +10;
  `distToNearestEnemy` −1/шаг; `threat` −3 за врага (герой ×2), где досягаемость врага = его движение + публичная
  оценка буста (максимум BOOST его колоды — состав колоды открыт); `zoneControl` ± по роли; `protectAlly` +2;
  `stepsUsed` −0,1. Финальный тай-брейк — ключ `K`.
- Несколько бойцов: жадно «герой → сайдкики» на последовательной симуляции §3.2.
- GraphQL-запрос `moveHints(gameId, maneuverId)`: только владельцу открытого `pendingManeuver`; считает по
  viewer-проекции (без руки соперника); кэш клиента по `seq + maneuverId`.
- Бот (`ai-decision.service.ts`): путь — `canonicalPath`; цели — `scoreMoves`; буст — по разнице лучшей оценки «с
  бустом / без»; двигает и сайдкиков.

| ID | Требование | Тест |
|---|---|---|
| MS-R-65 | `scoreMoves` детерминирован, использует только публичные данные, его результат стабилен при одинаковом входе | MS-AT-50 |
| MS-R-66 | Бот использует `scoreMoves`: бустит, когда это улучшает оценку, и двигает сайдкиков | MS-AT-55 |

## 9. Телеметрия и трассы

Трассы пишет `FS08Trace` (как остальные гейты: проверка по трассам, не по пикселям — HUD-RULES).

| Строка | Когда | Поля |
|---|---|---|
| `MS-DRAFT op=<assign|clear|boost|order|undo|reset|snapshot|restore|predraft|predraft.lost> rev=<n> src=<click|key|auto|snapshot>` | любая операция черновика (`restore` — черновик из кэша по `maneuverId`, MS-T-04; `snapshot`/`restore` пишутся с `src=snapshot`; `predraft` — цель предвыбора MS-S-03, `predraft.lost` — цель не перенеслась, MS-T-07) | `fighter`, `dest=<CellLabel>`, `order`, `status`, `required`, `boost` |
| `MS-PATH fighter=<id> steps=<n> allowance=<n> key=<canonical>` | новый путь хода или превью | `cells=M13>M14>M18` |
| `MS-HL base=<n> boost=<n> ally=<n> enemy=<n> conflict=<n> needboost=<n> ghosts=<n> paths=<n>` | смена вида | счётчики подложек по состояниям |
| `MS-HL geom ringIn=<uu> ringOut=<uu> outline=<uu>..<uu> clear=<uu> pipCut=<deg>` | сборка доски | геометрия подложки (MS-AT-21, MS-AT-30) |
| `MS-HL assets plate=<имя> path=<имя> ghost=<имя>` / `MS-HL ghost sections=<S>` / `MS-HL pool.grow n=<k>` | загрузка, рост ISM пути | MS-R-74, §7 |
| `MS-REJECT code=<ruleCode> why=<key> class=<И|С>` | отказ клиента или сервера | `cell`, `fighter` |
| `MS-NET late-reply op=<begin|maneuver>` / `MS-NET deadline op=<…>` | поздний HTTP-ответ, дедлайн 10 с | — |
| `MS-DATA dirtyDefeated fighter=<id>` | двигаемый боец с `isDefeated` при `health > 0` | — |
| `MS-CUE move seq=<n> fighter=<id> order=<k> of=<n> kind=<move|place> steps=<n> source=<trail|canonical|straight> start=<ms> ms=<n> snapped=<0|1> path=<A>B>…>` | выпуск cue перемещения (MS-T-15), старт анимации (MS-T-16) | `trail=mismatch`; MS-T-16 — `speed=`, `reduced=` |
| `MS-ANIM skip|jump|snap seq=<n> count=<n>` | пропуск, `jump_to_final`, snap | — |
| `MS-PERF draft us=<n> view us=<n>` | каждые 60 пересчётов (агрегат p50/p95) | — |
| `MS-OPP planning=<0|1> seq=<n>` | смена индикатора соперника | — |
| `MS-OPP arrow=<0|1> cell=<CellLabel> x= y= angle= seq=` | стрелка у края экрана к концу пути соперника появилась, сменила цель или пропала (MS-T-17, MS-E-73) | — |
| `MS-LAST enter|show|fade|off|replace seq=<n>` | подсветка последнего хода (MS-T-17, MS-P-03): след вошёл, показан (`mode=anim|restore`), гаснет (`at=<seq> ms=300`), погас | `player`, `from`, `to` |
| `MS-LOG seq=<n> moves=<n> truncated=<0|1> text="…"` | строка ленты событий (MS-T-17, 03 §7) | — |
| `MS-BENCH mismatch id=<id>` | id из `-BenchMoveDraft` нет в bench-фикстуре | — |

`tools/s08/cue_contract/cue_contract.py` (`check-trace`) получает проверку параметра `steps`, источника пути и
длительности `ms=` по расписанию §6.3 для CUE-007 — сделано в MS-T-15 (коды M1..M5, `--min-ms-cue N`).

| ID | Требование | Тест |
|---|---|---|
| MS-R-60 | Трассы таблицы пишутся; `cue_contract.py check-trace` проходит с проверкой `steps` и длительности по §6.3 | MS-AT-28 |

## 10. Требования MS-R-41..MS-R-74 (сводка)

| ID | Требование | Тест |
|---|---|---|
| MS-R-41 | Канонический путь и множества достижимости TS и C++ совпадают на всех golden-фикстурах | MS-AT-01, MS-AT-10 |
| MS-R-42 | Каждый канонический путь клиента принимается сервером; для каждого пространства вне `reach` сервер отклоняет все простые пути длиной ≤ допуска (property, ≥ 500 случайных состояний) | MS-AT-06 |
| MS-R-43 | Ходы черновика оцениваются последовательно на позициях после предыдущих ходов (§3.2), статусы Ok/NeedBoost/Conflict по `RequiredBoost` | MS-AT-13, MS-AT-12 |
| MS-R-44 | Ходы нулевой длины не сериализуются ни в `ConfirmManeuver`, ни в `SubmitManeuver` | MS-AT-11 |
| MS-R-45 | Клиент повторяет `getFighterMovement` (по сырому значению) и оба предиката «живой» сервера по ролям: блокирующий/занимающий — `isLivingFighter`, двигаемый — `health > 0` | MS-AT-14 |
| MS-R-46 | Ошибки `beginManeuver`/`maneuver`/`resolvePendingEffect` несут `extensions.ruleCode` из 02 §1.1 в development и в production | MS-AT-04 |
| MS-R-47 | `metadata.lastMovement` пишется по §4.3 для манёвра и MOVE/PLACE; переживает сохранение в БД и загрузку (`lm`); виден сопернику; не содержит скрытых данных | MS-AT-03 |
| MS-R-48 | Cue перемещения несёт путь и порядок; источник — по таблице §4.6 (след того же seq, иначе канонический, иначе прямая; пропуск seq — без cue) | MS-AT-25 |
| MS-R-49..54 | см. §6 | MS-AT-21..24, MS-AT-33, MS-AT-34 |
| MS-R-55, 56 | см. §5 | MS-AT-20 |
| MS-R-57..59 | см. §7 | MS-AT-40..42 |
| MS-R-60, 61 | см. §9 и §6.4 | MS-AT-28, MS-AT-30 |
| MS-R-62 | Мышиный быстрый ход TASK-022 (клик по клетке вне черновика) без `-S08LegacyQuickMove` не вызывает `TryManeuverTo`/`FinishPendingManeuver`. Автодрайвер `-S08Maneuver` (`RunAutoManeuver`) идёт через черновик S09 (`beginManeuver` → снапшот с `pendingManeuver` → `FS09CommandUi` → `ConfirmManeuver`); гейт демо `bAutoManeuverDone` / `ManeuverStartSeq + 2` (`S08FlowGameMode.cpp:3759-3762`) сохраняется (begin + 1, maneuver + 1) | MS-AT-16 |
| MS-R-63 | (фаза 4, после MS-T-01) сервер отклоняет MOVE/PLACE обездвиженного бойца кодом `FIGHTER_IMMOBILIZED` | MS-AT-05 |
| MS-R-64 | (фаза 4, после MS-T-01) сервер отклоняет буст картой без BOOST кодом `BOOST_NO_VALUE`, в том числе при `moves: []` | MS-AT-07 |
| MS-R-65, 66 | см. §8 | MS-AT-50, MS-AT-55 |
| MS-R-67 | Golden-фикстуры привязаны к sha256 топологии; при изменении топологии тест падает с понятным сообщением | MS-AT-08 |
| MS-R-68 | Изменения сервера аддитивны: существующие тесты backend (манёвр, движение, топология, бот) и веб-клиент не ломаются | MS-AT-09 |
| MS-R-69 | Каждый ключ `ms.*`/`why.*` имеет RU и EN; StringTable попадает в упакованный клиент (MS-T-28); `why-reasons.json` проходит `tools/s08/hud_contract/hud_contract.py` | MS-AT-35 |
| MS-R-70 | Устаревшие места документации (R1-S01..S07, R2 §6, 02 UI-INP-008/§4.10, `docs/unreal/08-gameplay-flows.md:430`, строка CUE-007 в 07 csv) исправлены | MS-AT-60 |
| MS-R-73 | см. §5 | MS-AT-19, MS-AT-20 |
| MS-R-74 | см. §6.1 | MS-AT-30 |
