# VS-1 — чистый вид и основа: итог спринта

Спринт VS-1 из [05-production-plan.md §3](../../../visual/05-production-plan.md). Работа шла в worktree
`C:/tmp/wt-visual`, ветка `feat/visual-vs1`. Этот файл написан 2026-10-06 на шаге «кадры и упаковка» (05 §1.5 п. 7,
§1.6, §1.7 п. 1; ВР-PL14).

Ветка в `fix/admin-panel` **не интегрирована**: шаг `safe-integrate.sh` в этот шаг не входил. Статусы карточек в
`06-tasks/*.csv` и в реестре 03 правит основная копия после интеграции (ВР-PL09).

## Карточки

| Карточка | Коммит | Что | Приёмка |
|---|---|---|---|
| HB-01 | `b1a3ea6a` | флаг `-S09Markers`, поле `markers=` в `ARTLOOK`, флаг явно передан в 7 гейтах s09/s10 | технически импортировано; гейты — ниже |
| HB-02 | `88dc56f6` | слой гейтов по умолчанию скрыт: маркеры, полоса результата, `seq=` / `phase=`, эхо, AUTO, заголовок, F10 | вид игрока — **художественно принято, по делегированию (2026-10-06)**, лист [HB-02](../HB-02/README.md); гейты 5 из 7 |
| HB-03 | `3899210c` | генератор токенов, `S08HudTokens.generated.h` | технически импортировано (вид не меняется) |
| HB-04 | `e7f34ee6` | тема `UUmHudTheme`, `DA_UmHudTheme` | технически импортировано (вид не меняется) |
| HB-05 | `f0e3080c` | таблицы строк RU/EN, `UmText`, культура `ru` по умолчанию | технически импортировано; видно в упаковке: субтитры озвучки теперь на русском (открыто п. 3) |
| HB-09 | `1edf52e7` | кривая DPI 720 → 0,75, масштаб UI 75–150 %, `-S08DpiLegacy` | технически импортировано; кадры 720p и 150 % открыты, находка — открыто п. 2 |
| FX-01, FX-11, FX-12, FX-18 | `3a06a51c` | контракт CUE `fx-p4-2026-10` | технически импортировано (вид не меняется) |
| IC-33 | `2e958db1` | движок значков v3: наборы ВР-44, экспорт 18/36/72, импорт по `ue_sizes` | технически импортировано |
| CP-01 | `16f709e8` | конвертер WebP → PNG для сканов, аватаров и рубашек | технически импортировано |
| CP-02 | `3c6b314d` | импорт сканов, рубашек и портретов в UE, реестр ключей, флаги отката | технически импортировано |
| EN-05 | `e088d62b` | гейты окружения `env_gates.py` | технически импортировано |

Коммиты этого шага:
- `9052701d` — в ветку влит `fix/admin-panel` (`8807d3d4`, звук AU-S6 и тема меню). Конфликтов не было.
- `ae8950dc` — две правки, без которых не собиралась упаковка и не проходил G-TOKENS:
  - `UmTextTests.cpp` (HB-05) теперь только для редактора. API `Enable/DisableGameLocalizationPreview` есть только
    `WITH_EDITOR`, и игровая цель падала с C2039.
  - В `UmCardMediaTests.cpp` (CP-02) литерал `FColor(6, 22, 35, 0)` заменён на `S08HudTokens::Color_PanelBg` с
    альфой 0.
- Коммит с листами (этот файл, [HB-02](../HB-02/README.md)) и флагом `run-combat-demo.ps1 -PlayerView`.

## Генерация (CX-01…CX-07)

Пакеты Codex сделаны в основной копии, вне этого шага. По журналу трат на 2026-10-06:
- CX-01 (HB-07), CX-02 (HB-08), CX-03 (HB-44), CX-06 (CP-13) — ревью «fix-needed», не закоммичены.
- CX-04 (IC-36): end-turn и card-drop приняты, log и pointer — «fix-needed».
- CX-05 (IC-37) — 2 прогона, правок 0.
- CX-07 (EN-01): маски field и remove приняты, clean и lantern-mask — «fix-needed».

Итог их приёмки — за шагом генерации, здесь он не повторяется.

## Упаковка

Одна упаковка Development, `tools/s08/package-client.ps1`:
- Порядок: `touch Unmatched.Build.cs` (новый `Config/Cards/S08CardMedia.json`), сборка игровой цели с
  `-MaxParallelActions=4`, затем BuildCookRun `-build`.
- UAT: `BUILD SUCCESSFUL`, `UAT_EXIT=0`. Кук: 2109 пакетов, `0 error(s), 0 warning(s)`.
- `BuildStamp.json`: `commit ae8950dc` (это HEAD ветки в момент упаковки), `sourceHash c3c4e930…`, 241 файл,
  `skipBuild false`.
- sha256 внутреннего exe: `f69b8e8f63e2584e17e11830918977e8dc9a5854e74d0f57faccb16d95a621bf`.
- В pak вошли: `Config/Cards/S08CardMedia.json`, `S08IconMotion.json`, `Localization/Game/{en,ru}/Game.locres`.
- Коммиты после упаковки трогают только `tools/` и `docs/`, `sourceHash` они не меняют. После `safe-integrate.sh`
  основной копии нужен `sync-staged-build.ps1 -From C:/tmp/wt-visual`, перепаковывать не нужно.

## Гейты

Общие условия:
- Упаковка выше, Api `http://localhost:3000/graphql` (основной стек).
- Два клиента, у каждого 30 FPS:
  - `t.MaxFPS 30` у combat, duel и vs-ai;
  - у hud и pending — `FrameRateLimit=30` в сохранённых настройках упаковки на время прогона.
- Демо-аккаунты передавались только через окружение процесса.

| Гейт (с `-S09Markers`) | Доска | Итог |
|---|---|---|
| `run-hud-probe` | фикстура S08, 1280×720 | PASS: SLATE-PASS, маркеры |
| `run-hud-demo` | Marmoreal original (серый вид карты, `-S08GreyBoard` задан в самом гейте) | PASS (draft `#FF00FF` 1370, discard `#00FFFF` 1490) |
| `run-hud-demo` | Sarpedon original (серый вид) | PASS |
| `run-combat-demo` 720p, `-ConceptPaste` | Marmoreal original | PASS: маркеры def 900 / res 1350 / rst 1190–1245, подмены не проходят, проверка раскрытия есть, FINISHED seq 86, `v2=6`, `RENDER` 0 вне эталона |
| `run-combat-demo` 720p | Sarpedon original | PASS: FINISHED seq 29; раскрытия в этой партии не было (честное отсутствие) |
| `run-duel-demo` | Marmoreal (доска бэкенда по умолчанию) | PASS (GD-036) |
| `run-vs-ai-abort-demo` | Marmoreal | PASS (GD-040: ABORTED, `#FF6414`, чистое лобби) |
| `run-pending-demo` | Marmoreal | **FAIL ×2** — п. 4 ниже |
| `run-vs-ai-demo` | Marmoreal | **FAIL ×2** — п. 5 ниже |

Кадры игрока: `run-combat-demo -PlayerView` без `-S09Markers`, обе доски, 1080p и 720p. Дополнительно 720p с
`-S08DpiLegacy` и 1080p с UI 150 %. Все 6 прогонов — PASS, подробности в листе [HB-02](../HB-02/README.md).

Тесты и скриптовые гейты:
- UE после слияния:
  - `Unmatched.S08.ArtLook + Unmatched.S08.Hud + Unmatched.S08.IconMotion` — 19/19;
  - `Unmatched.S08 + S09 + S10` — 390/390;
  - `Unmatched.S08.CardMedia` после правки — 3/3.
- G-TOKENS (`hud_contract.py validate`): сначала FAIL на литерале из CP-02, после `ae8950dc` — PASS.
- `hud_tokens_codegen.py --check` — FRESH. `hud_strings_build.py check` — PASS.
- `cue_contract.py validate-table` — PASS (18 CUE). `run-fixtures` — PASS (19).
- pytest `tools/s08/hud_contract` + `tools/s08/cue_contract` — 120 passed.
- pytest `tools/art` — 838 passed, 6 skipped, 1 failed: `test_de013_sound_list.py::test_nothing_acquired_yet`. Тест
  падает и на `fix/admin-panel` в основной копии: это файл звуковой сессии, тест устарел после закупки звуков.

## Кадры

Лист [HB-02](../HB-02/README.md):
- «до» и «после» на Marmoreal и Sarpedon original, свой ход, бой и результат, 1080p и 720p;
- листы цвет / серый / дейтеранопия;
- проверка маркеров на 150 кадрах игрока и контроль на 12 кадрах со слоем.

Каждый кадр выхода открыт глазами. Доска настоящая, задник верный: Marmoreal нарисованный через `-ConceptPaste` до
EN-13, Sarpedon `lit3d`. Все шесть фигур — v2.

## Траты

- **Этот шаг:** 0. SYNTX не вызывался, покупок нет.
- **Весь VS-1 по `credits-ledger.json` на 2026-10-06:** SYNTX — 0 токенов. Codex — 7 пакетов (CX-01…CX-07), из них
  28 генераций image_gen: CX-04 — 8, CX-05 — 16, CX-07 — 4. Денежных трат нет.

## Решения шага (по делегированию)

| № | Решение | Почему |
|---|---|---|
| ВР-VS1-F01 | Кадры выхода HB-02 сняты в живой партии `run-combat-demo -PlayerView`, а не на `-Bench` | бенч не строит живой HUD (`-BenchTurnHud`: «the live HUD is not built here»), строк `seq=` и эха на нём не было бы и до HB-02 |
| ВР-VS1-F02 | «До» на 1080p — кадры прогона I (ВР-PL11). «До» на 720p — эта же упаковка с `-S09Markers` | у прогона I нет 720p, а флаг возвращает ровно прежний слой |
| ВР-VS1-F03 | Перед упаковкой влит `fix/admin-panel` | одна упаковка на изменение: штамп должен совпасть с основной копией после интеграции |
| ВР-VS1-F04 | Гейтам без своего капа FPS (hud, pending) кап ставится через `FrameRateLimit=30` в сохранённых настройках упаковки, после прогона ключ снимается | AGENTS.md: по 30 FPS на клиент |
| ВР-VS1-F05 | Падения pending и vs-ai не чинятся в этом шаге | причина в чужом коде: гейт S09 и звук (AU); правка гейта или звука — не рамки VS-1. Нужен отдельный шаг |

## Открыто

1. **Ветка не интегрирована.** Дальше: `safe-integrate.sh feat/visual-vs1` (сначала сухой прогон), затем в основной
   копии пересборка редактора и `sync-staged-build.ps1`. После этого — статусы HB-01, HB-02 и остальных в
   `06-tasks/*.csv`.
2. **720p: ряд карт руки уходит за нижний край** в части состояний. С `-S08DpiLegacy` то же самое. При UI 150 % на
   1080p: обрезан ряд руки, левая панель карты закрывает фигуры. Это задача корня HUD (VS-2); лист HB-02, «Что не
   прошло», п. 2.
3. **Язык.** Культура `ru` по умолчанию (HB-05), поэтому субтитры озвучки на русском, а Slate HUD на английском. Так
   будет, пока HUD не переведён на `UmText`.
4. **`run-pending-demo` (FAIL, ложное срабатывание гейта).** Гейт считает каждый pending, кроме BOOST_CHOICE, открытым
   до раскрытия. На Marmoreal теперь бывает MOVE после боя: «If you won the combat, choose one of the fighters…»,
   фаза `COMBAT_RESOLVE`. Бой уже раскрыт, поэтому строка «REVEALED combat» (`#8040FF`) и текст `#7CFC00` видны
   законно.
   - Попытка 1: `s09-pending-MOVE.png`, revealline = 1712.
   - Попытка 2: `s09-resolve-blocked-MOVE.png`, revealtext = 1403.
   - Покрытие обеих попыток полное: BOOST_CHOICE, CHOOSE_SPACE, DECK_TOP_PICK, MOVE, PLACE, TARGET_FIGHTER.
   - Последняя опубликованная партия pending — от 2026-09-26, она шла ещё до правила о настоящих досках.
   - Кадры и трассы: `C:/tmp/visual/VS1-frames/fail-pending-try1/`, `…/fail-pending-try2/`.
   - Нужно: гейт должен отличать pending до раскрытия от pending после. Владелец — гейты S09.
5. **`run-vs-ai-demo` (FAIL, дефект звука).** В кадре возврата в лобби 596 ярких пикселей. Это субтитр «Медуза:
   Красиво. И так неподвижно.» (`VO subtitle line=MEDUSA-VICTORY-02`): реплика победы стартует через секунду после
   `LEFT room`, и субтитр переживает смену сцены.
   - Обе попытки дали одинаковый результат.
   - Все остальные проверки прогона прошли: место бота, FINISHED, маркеры результата 180 ×4.
   - Кадры и трассы: `C:/tmp/visual/VS1-frames/fail-vsai-try1/`, `…/fail-vsai-try2/` (во второй попытке `LEFT room` в 06:11:36, субтитр в 06:11:37).
   - Нужно: гасить VO и субтитры при уходе в лобби. Владелец — звуковая сессия (AU-S4).
6. **Командная панель показывает служебные слова:** «COMBAT OVER (seq N)», «phase: ACTION_MANEUVER», «next:
   TARGET_FIGHTER». Кандидат в VS-4.
7. **Без `-ConceptPaste` Marmoreal в duel, pending и vs-ai идёт с 3D-окружением P5c.** Эти гейты не принимают флагов
   клиента. Это известный разрыв ENV-U16, его закрывает EN-13.
8. **Герой бота VS_AI — T. Rex, у него нет фигуры v2** (серая болванка). Правило «шесть фигур v2» относится к партии
   Medusa против King Arthur.
9. **pytest `test_de013_sound_list`** падает и на `fix/admin-panel`, это тест звуковой сессии.
