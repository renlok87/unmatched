# Прогон B (S11b — ввод и кандидаты): живая приёмка G-LIVE (2026-10-04)

**Итог: пройдено** для DE-014, DE-015, DE-017 и MS-T-08 (живая часть). Одна упаковка на прогон (штамп `36a74fc5`).
Два клиента на Marmoreal original и на Sarpedon original, 30 FPS на клиент, оба offscreen. Все гейты скрипта прошли,
трассы прошли `check-trace`, кадры просмотрены глазом до отчёта. Остатки и замечания — в конце.

- Полномочия, порядок и решения оркестратора — [IMPL-2026-10-04.md](../../../../de-footage/task/runs/IMPL-2026-10-04.md).
- Журнал прогона — [B-2026-10-04.md](../../../../de-footage/task/runs/B-2026-10-04.md), раздел «Живая приёмка G-LIVE».
- Гейт — [07-sprint-plan.md](../../../../de-footage/task/07-sprint-plan.md) §8, строка G-LIVE.

## Что пришлось добавить для приёмки (коммиты агента приёмки)

Живой прогон двух клиентов не умел показать то, что требуют хвосты задач прогона: кадр открытого черновика с кольцами
V-17, нажатие на HUD и клавишу E. Добавлены опциональные пробы, вид по умолчанию они не меняют.

| Коммит | Что |
|---|---|
| `36a74fc5` | Клиент: `-S08ManeuverDraftHold=<с>` держит открытый черновик авто-манёвра (MS-S-06) и `-S08ManeuverDraftShot=<png>` снимает его кадр (кадр свидетельства прогона не подменяется). Шаги `-ArtPreviewInputPlan`: `endturnkey` — путь клавиши E (`MoveInput.OnKey(E)` → `EndTurnCommand`), `hudendturn` — нажатие и отпускание на живом элементе `hud.end.turn` через его Slate-обработчики (`SS09HudPress` → арбитр → `HandleHudPressOutcome`). Тест `Unmatched.S08.ArtHud.Flags` дополнен. Гейты скрипта на ответы этих шагов |
| `0aa307a9` | `run-phase2-demo.ps1`, три гейта, падавших из-за кода прогона или известной гонки: (1) с `-S08MovePlates` старое кольцо `ARTPREVIEW reachable rings` не спавнится (MS-T-08) — гейт теперь `MS-HL assets plate=M_UM_MovePlate … ready=1`, `MS-HL geom … ok=1` и вид `MS-HL view source=reach … ring>0`; (2) «шесть центров фигур в кадре» считается только по блоку SHOT кадра свидетельства (кадр черновика пишет свой блок); (3) нога манёвра, закрытая снапшотом WS раньше ответа HTTP, пишет `MS-NET late-reply op=<нога> ok=1` вместо `MANEUVER begin seq=` / `MANEUVER done` — принимается любой из двух (замечание A04 п. 1) |

Гейты после правки: сборка редактора и игровой цели — `Result: Succeeded`; UE `Unmatched.S08+Unmatched.S09+Unmatched.S10` —
312/312 Success.

## Сборка и упаковка

| Шаг | Команда | Результат |
|---|---|---|
| Редактор | `node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=… -WaitMutex -NoXGE -MaxParallelActions=6` | `Result: Succeeded`, ошибок в логе нет |
| UE-тесты | `node tools/s08/run-ue-tests.cjs "Unmatched.S08+Unmatched.S09+Unmatched.S10" <log>` | 312/312 Success |
| Игровая цель | то же, цель `Unmatched` | `Result: Succeeded` |
| Упаковка, один раз | `tools/s08/package-client.ps1 -SkipBuild -Log C:\tmp\b-live\uat.log` | `UAT_EXIT=0`, `LogCook: Warning/Error` — 0 |
| Штамп | [BuildStamp.json](BuildStamp.json) | commit `36a74fc5`, sourceHash `4e383d9d…`, 151 файл |
| Внутренний exe | sha256 staged `Unmatched/Binaries/Win64/Unmatched.exe` = `Binaries/Win64/Unmatched.exe` | `926c8471…` в обоих |

В pak (по `Manifest_UFSFiles_Win64.txt`): `Content/S08/MoveSelection/M_UM_MovePlate.uasset` (MS-T-08, через
`DirectoriesToAlwaysCook`), `Config/ArtBoards/S08ArtBoardProfiles.json` rev 22 (файл не новый — регенерация makefile не
нужна). В упакованном клиенте трасса `MS-HL assets plate=M_UM_MovePlate … ready=1` на обоих клиентах обеих карт (MS-R-74).

## Живой прогон двух клиентов

Обёртка `C:\tmp\b-live\run-demo.ps1` (вне репозитория, копия обёртки A04): демо-аккаунты `S08_DEMO_*` из
`C:/tmp/wt-envmaps/backend/.env` только в окружение процесса, не печатаются; замок `C:/tmp/unmatched-gpu.lock`
(`owner=B-LIVE`) на время прогона.

```
run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ArtPreviewBoardId <board> -EvidenceDir <dir>
  -HostManeuver -RequireRenderReference -RequireShotCaptured -ClientPerf
  -ArtPreviewInputPlan 'endturnkey+hudendturn'
  -ClientExtraArgs '-ConceptPaste+-S08MovePlates+-S08ManeuverPlan=boost3+-S08ManeuverDraftHold=2.5+-S08ManeuverDraftShot=<png>'  # Marmoreal
  -ClientExtraArgs '-S08MovePlates+-S08ManeuverPlan=boost3+-S08ManeuverDraftHold=2.5+-S08ManeuverDraftShot=<png>'                # Sarpedon
```

- `-ClientFps 30` (по умолчанию) на каждом клиенте, пресет High, `RENDER reference=1`.
- `-S08MovePlates` — новая подсветка MS-T-08 включается флагом до арт-приёмки MS-T-27 (05 §4; решение 4 DE-017).
  Без флага колец V-17 нет по замыслу.
- Marmoreal снят с `-ConceptPaste` (IMPL п. 3, правило задника AGENTS.md). ENV-U16 открыт, в прогон не входит.
- Бэкенд — основной стек `:3000`, `/health` = database up, redis up (стек был поднят до агента и оставлен).

### Marmoreal · original map — [demo/marmoreal/run-20261005-040857](demo/marmoreal/run-20261005-040857/)

| Проверка | Хост | Джойнер |
|---|---|---|
| Доска | `c121b47f8d6eb28daccb76d05`, `marmoreal-original`, 7×6, 31 пространство / 42 связи | то же |
| `ARTLOOK` | `art=1 source=default heroes=v2 tray=on env=on review=1 legacyRender=0 aliases=-` | то же |
| Фигуры | `heroesV2 summary fighters=6 mapped=6 v2=6` | то же |
| Задник | `envlayout variant=concept … status=ok propsRemoved=64`, `concept-paste status=ok`, поднос скрыт | то же |
| Подсветка (MS-T-08) | `MS-HL assets plate=M_UM_MovePlate … ready=1`, `MS-HL geom … ok=1` | то же |
| Кандидаты (DE-017) | `MS-DRAFT op=candidates rev=1 src=snapshot n=4 ids=f-0-hero,f-0-sk0,f-0-sk1,f-0-sk2 autoselect=-`, `MS-HL view source=draft plates=4 ring=4`, кадр черновика | — |
| Манёвр | `MANEUVER-CONFIRM moves=3 boost=card`, 3 × `MS-CUE move` | 3 × `MS-CUE move`, 3 × `CUE move` |
| `check-trace --min-ms-cue 3` | `CUE_TRACE PASS`, ms_cue 3 (trail 3) | `CUE_TRACE PASS`, ms_cue 3 |
| Начало хода (DE-015) | `TURN-INPUT open seq=1 frame=550 gate=none` | хода нет — строки нет (верно) |
| Клавиша E (DE-015) | `INPUT key=E src=flag` → `ENDTURN refused why=why.actions.remaining` → `TOAST why=why.actions.remaining text="Use your actions first: 1 left"` | — |
| Нажатие END TURN (DE-014) | `HUD-PRESS id=hud.end.turn result=refused over=hud.end.turn rebuilds=0 frames=942->942 why=why.actions.remaining`, `TOAST why=…` в том же кадре | — |
| Первый ввод хода (DE-015) | `TURN-INPUT first src=hud id=hud.end.turn result=refused frame=942 open=550 dframes=392 why=why.actions.remaining` | — |
| Гейты скрипта | все: пиксельный арт-гейт (`pass`), шесть центров фигур в кадре, `SHOT captured`, `RENDER reference=1`, сходимость seq 3/3 после WS drop | — |
| FPS (afterWarmup) | 29,87, gpuMs 2,33 | 29,90, gpuMs 2,37 |
| Уборка | игра этого прогона снята, `ABORTED (verified)` | — |

### Sarpedon · original map — [demo/sarpedon/run-20261005-041533](demo/sarpedon/run-20261005-041533/)

| Проверка | Хост | Джойнер |
|---|---|---|
| Доска | `c7fa64a26c29a0835f2383e63`, `sarpedon-original`, 9×6, 38 пространств / 61 связь | то же |
| `ARTLOOK` | `art=1 source=default heroes=v2 tray=on env=on review=1 legacyRender=0 aliases=-` | то же |
| Фигуры | `heroesV2 summary fighters=6 mapped=6 v2=6` | то же |
| Задник | `concept-paste mode=on reason=default`, `concept-scene status=ok mode=lit3d`, `anim flickers=5 sways=1 winds=21/21` | то же |
| Подсветка (MS-T-08) | `MS-HL assets … ready=1`, `MS-HL geom … ok=1`; кадр черновика: ярусы и цель | то же (assets/geom) |
| Кандидаты (DE-017) | `MS-DRAFT op=candidates rev=3 n=4 … autoselect=-`; герой уже выбран перенесённым предвыбором (`MS-DRAFT op=predraft src=auto fighter=f-0-hero dest=S10`), поэтому колец нет — по 03 MS-R-02 и решению 2 DE-017 это верно | — |
| Манёвр | `MANEUVER-CONFIRM moves=3 boost=card`, 3 × `MS-CUE move`; ноги закрыты снапшотом раньше HTTP (`MS-NET late-reply op=maneuver ok=1 settled=snapshot`) | 3 × `MS-CUE move` |
| `check-trace --min-ms-cue 3` | `CUE_TRACE PASS` | `CUE_TRACE PASS` |
| Начало хода / E / END TURN | `TURN-INPUT open seq=1 … gate=none`; `ENDTURN refused why=why.actions.remaining`; `HUD-PRESS id=hud.end.turn result=refused … frames=939->939 why=why.actions.remaining`; `TURN-INPUT first src=hud … result=refused … why=why.actions.remaining` | — |
| Гейты скрипта | все прошли, сходимость seq 3/3 | — |
| FPS (afterWarmup) | 29,85, gpuMs 2,76 | 29,91, gpuMs 2,85 |
| Уборка | `ABORTED (verified)` | — |

### Кадры (просмотрены глазом до отчёта)

- **Marmoreal, черновик открыт (MS-S-06)** — [кадр](demo/marmoreal/run-20261005-040857/draft-marmoreal-host-1920x1080.png),
  [вырезка](marmoreal-draft-candidates-crop.jpg).
  - Настоящая карта Marmoreal, вокруг — нарисованный задник из концепта (лестница дворца, колонны, фонари, сакура).
  - HUD: «MANEUVER DRAFT - MOVE FIGHTERS», `moves drafted: 0`.
  - Под четырьмя своими бойцами (Medusa и три Harpy) — кольца-кандидаты V-17 снаружи командного кольца; у Medusa кольцо
    крупнее (масштаб героя). Под King Arthur и Merlin колец нет.
- **Marmoreal, после манёвра** — [хост](demo/marmoreal/run-20261005-040857/phase2-board-host-1920x1080.png),
  [джойнер](demo/marmoreal/run-20261005-040857/phase2-board-joiner-1920x1080.png).
  - Шесть фигур v2: Medusa, три крылатые Harpy (переставлены планом), Merlin в синем, King Arthur в красном.
  - У хоста выбрана Medusa: плашки её досягаемых пространств (9 колец с заливкой). Кнопка END TURN (E) приглушена — одно
    действие осталось.
  - У джойнера «OPPONENT'S TURN», плашек нет.
- **Sarpedon, черновик открыт** — [кадр](demo/sarpedon/run-20261005-041533/draft-sarpedon-host-1920x1080.png),
  [вырезка](sarpedon-draft-tiers-crop.jpg).
  - Настоящая карта Sarpedon, вокруг — `lit3d` путь 1: остров, корабль с пушками, костры, фонари.
  - Выбрана Medusa (предвыбор S10): сплошные кольца базового яруса, пунктир яруса буста, двойное кольцо цели.
- **Sarpedon, после манёвра** — [хост](demo/sarpedon/run-20261005-041533/phase2-board-host-1920x1080.png),
  [джойнер](demo/sarpedon/run-20261005-041533/phase2-board-joiner-1920x1080.png): шесть фигур v2, Medusa на S10,
  приспешники переставлены; у хоста плашки досягаемости Medusa.

## Стоимость подсветки (MS-AT-41) и кадр кандидатов в пакете

`render_bench.py run` на этом же пакете, без ограничения FPS, по 2 повтора, виды K1 и K2x1,6, под замком
`owner=B-LIVE-BENCH`. Steam-игры пользователя на машине не было (GPU тихий).

```
render_bench.py run --variant dx12-lumen-high-v2 --repeats 2 --views K1+K2x1.6 --bench-fixture ../../../Unmatched/Config/Bench/S08Bench<Map>.json
render_bench.py run --variant dx12-lumen-high-v2-moveplates … --move-draft tools/s08/fixtures/move-draft/<map>-2-draft-conflict-needboost.json
render_bench.py run --variant dx12-lumen-high-v2-moveplates --repeats 1 … --move-draft tools/s08/fixtures/move-draft/<map>-0-candidates.json
```

Сводка — [bench/ms-at-41.json](bench/ms-at-41.json), записи и трассы — `bench/*-bench-run.json`, `bench/*.trace.txt`.
Колонка `RHI/DrawCalls` в CSV профайлера есть (вопрос из хвоста MS-T-08 закрыт).

| Карта, вид | GPU, мс: база → плашки (сцена 2) | Δ GPU | Draw calls: база → плашки | Δ |
|---|---|---|---|---|
| Marmoreal K1 | 2,51 → 2,52 | +0,010 | 435,5 → 443,5 | **+8** |
| Marmoreal K2x1,6 | 2,455 → 2,465 | +0,010 | 347,9 → 319,4 | −28,5 |
| Sarpedon K1 | 2,63 → 2,645 | +0,015 | 480,6 → 488,7 | **+8** |
| Sarpedon K2x1,6 | 2,515 → 2,51 | −0,005 | 474,1 → 400,0 | −74 |

- **GPU: пройдено с запасом** — не больше +0,015 мс при пороге +0,30 мс (шум повторов 0,00–0,01 мс).
- **Draw calls.** На K2 база выбирает Medusa и спавнит старые кольца-акторы (`ARTPREVIEW reachable rings cells=8`),
  плашки их заменяют — вызовов меньше. Чистая добавка видна на K1 (в базе ничего не выбрано): **+8** при пороге
  7 + 4 × S, где S = 0 (`MS-HL ghost sections` появится только в MS-T-10). По разбивке профайлера это примерно +4 в
  проходе Translucency (четыре ISM) и примерно +4 в `BeginOcclusionTests` (запросы окклюзии для четырёх новых
  примитивов). Перерасход — один вызов, и он из дешёвых запросов окклюзии. Это **дефект MS-T-08 (MS-AT-41, мелкий)**:
  снять запросы окклюзии с ISM плашек (например, `bTreatAsBackgroundForOcclusion` / отключение окклюзионного
  отсечения для слоя, лежащего на доске). Крайний случай с 9 бойцами (MS-T-27) не мерялся — сцены нет.
- **Кадры кандидатов в упакованном клиенте** (сцена 0, MS-S-06): [Marmoreal K1](bench/marmoreal-plates0-K1-candidates.jpg),
  [Sarpedon K1](bench/sarpedon-plates0-K1-candidates.jpg) — кольца V-17 под четырьмя своими бойцами, `MS-HL view source=bench
  plates=4 ring=4`. Кадры сцены 2: [Marmoreal](bench/marmoreal-plates2-K1-draft.jpg), [Sarpedon](bench/sarpedon-plates2-K1-draft.jpg).
  Бенч Marmoreal идёт без `-ConceptPaste`, поэтому вокруг поля 3D-окружение P5c (вид по умолчанию до ENV-U16,
  известный разрыв): эти кадры — только про плашки и стоимость, не свидетельство вида Marmoreal.

## Приёмка задач прогона

| Задача | Что проверено в пакете | Статус |
|---|---|---|
| DE-014 | Нажатие на живой `hud.end.turn` через `SS09HudPress` в упакованном клиенте: ответ в кадре отпускания (`frames=N->N`), отказ с ключом `why.actions.remaining`, тост по ключу. На обеих картах. Пересборка HUD под удержанием и окно боя с отсчётом живьём не воспроизводились — их покрывает `Unmatched.S09.HudPress.SyntheticClicks` (920/920) | **принято** (G-LIVE). ACC-020 в окне боя живьём — прогон C (бой); ручные 50 кликов — пользователь |
| MS-T-08 | `M_UM_MovePlate` в pak, `MS-HL assets … ready=1`, `geom ok=1` на 4 клиентах; ярусы, цель, досягаемость видны на кадрах обеих карт. Стоимость — см. MS-AT-41 | **принято** (G-LIVE). MS-AT-41: GPU пройдено (+0,015 мс), draw calls +8 при пороге 7 — мелкий дефект, хвост MS-T-08. Арт-приёмка MS-T-27 — пользователь |
| DE-015 | `TURN-INPUT open … gate=none` на начале своего хода; первый ввод `TURN-INPUT first src=hud … result=refused … why=…` (не тишина); E до двух действий — `TOAST why=why.actions.remaining`, кнопка и клавиша отвечают одним ключом | **принято** (G-LIVE) |
| DE-017 | Кадр открытия черновика Marmoreal: кольца V-17 под всеми четырьмя своими подвижными, под соперником нет; `MS-DRAFT op=candidates n=4`. Sarpedon: трасса `n=4`, колец нет из-за перенесённого предвыбора (верно). Случай «один подвижный» живьём не собирался — тест `CandidatesAndAutoSelect` | **принято** (G-LIVE). Контраст колец — MS-T-13 / MS-T-27 |

## Замечания и дефекты

1. **Гейты `run-phase2-demo.ps1` падали из-за кода прогона** (исправлено в `0aa307a9`):
   - с `-S08MovePlates` гейт требовал старое кольцо `ARTPREVIEW reachable rings` (MS-T-08 его больше не спавнит) —
     первый прогон Marmoreal упал, хотя всё прошло;
   - гонка WS/HTTP: на Sarpedon обе ноги манёвра закрыты снапшотом, строки `MANEUVER done` нет — первый прогон
     Sarpedon упал, хотя манёвр прошёл (`MANEUVER-CONFIRM`, 3 × `MS-CUE`, `late-reply ok=1`). Это замечание A04 п. 1,
     теперь закрыто в гейте.
2. **Контраст V-17** (MS-T-13 / MS-T-27). Кольцо кандидата `#FFC857` того же золота, что и командное кольцо под фигурой
   и жёлтые зоны Marmoreal: на кадре кольцо видно, но читается как второе командное кольцо. Числа не менялись —
   предмет live tune MS-T-13 и арт-приёмки подсветки.
3. **Заливка 18 % плашек** на зелёных зонах Marmoreal выглядит сероватой (кадр хоста после манёвра) — уже записано
   в MS-T-08 (MS-T-13).
4. На Sarpedon у левого края кадра (x ≈ 0, y ≈ 930) белое пятно — было и до прогона (A04 п. 3), окружение lit3d.
5. У джойнера `PERF summary scope=artHud frames=0` — как в A04 п. 4, не гейт.
6. **MS-AT-41, draw calls +8 при пороге 7** (S = 0) — четыре запроса окклюзии ISM плашек сверх четырёх вызовов
   отрисовки. Хвост MS-T-08, см. раздел стоимости.

## Процессы

- Агент запускал: сборки UBT, UE-тесты (UnrealEditor-Cmd), RunUAT, пары клиентов демо (5 прогонов: Marmoreal 3, из них 2 упали на гейтах
  п. 1; Sarpedon 2, из них 1 упал на гонке п. 1), клиенты `-Bench` (render_bench, по одному под замком `owner=B-LIVE-BENCH`). Все завершились сами, замки сняты.
- Docker-стек (postgres, redis, backend :3000) был поднят до агента и оставлен.
- Room code в опубликованных трассах заменён на `<redacted>` самим скриптом. `*.log` переименованы в `*.txt` (`*.log` в
  gitignore), байты не менялись.
