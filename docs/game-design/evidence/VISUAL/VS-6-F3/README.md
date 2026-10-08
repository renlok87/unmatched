# VS-6 F3 — смерть и способности (FX-26, FX-27, AN-29, FX-28, FX-30, FX-32)

Шаг F3 спринта VS-6 (`docs/game-design/visual/05-production-plan.md` §3, пункты «смерть» и «способности»). Worktree
`C:/tmp/wt-visual`, ветка `feat/visual-vs6` (перед шагом `merge fix/admin-panel` — «Already up to date»). **Не влито.**
Кадры — editor-client `-Bench` (проверочные); приёмочные packaged `-Bench` с `RENDER`, живая партия до GAME_OVER на двух
клиентах, `run-combat-demo`, render_bench — шаг Frames одной упаковкой (поручение: «no packaging»). Статус всех
карточек — **технически импортировано**; художественная приёмка по делегированию — Frames.

## Коммиты

| коммит | что |
|---|---|
| `cef3c9cc` | ассеты: `T_FX_MedusaVortex_4x4`, `T_FX_ArthurArc_4x4`, `SM_FX_VortexRings`, `M_FX_AbilityPrint(Depth)` + `MI_FX_Arc` / `MI_FX_Vortex` / `MI_FX_Ember`, `NS_FX_AshEmbers` / `NS_FX_MedusaVortex` / `NS_FX_ArthurArc`; `M_UM_Figure_v2` v2.5 + 8 MIC растворения (AN-29); `tools/art/fx/fx_ability.py` + `ue_fx_ability.py`; `US08FxAuthoringLibrary::BindUserMaterialParameters`; fx-audit |
| `c10f2062` | C++ (FX-26/27/28/30/32, стиль AN-29), cue-table `by_hero` + схема, фикстуры `ability-medusa-gaze` / `ability-arthur-boost`, правило A1 в `cue_contract.py`, CUE-DISPATCHER.md, render_bench |
| `2590f74e` | бенч: полностью растворённая фигура не скрывает актор (кадрирование K2) |
| (этот) | README карточек, листы, ВР-VS6-22…33, статусы `06-tasks/vfx.csv`, `anim.csv` |

## Что сделано (подробно — README карточек)

- **AN-29 / FX-27** — смерть «пепел» по умолчанию (ВР-13): `DecideDissolveStyle(bFadeFlag, bReduced)`, откат
  `-S08DissolveFade`, reduced motion — fade, `-S08DissolveAsh` — пустой псевдоним; ARTLOOK `death=`; фронт — accent.warm
  (мастер v2.5), пепел — цвет команды.
- **FX-26** `NS_FX_AshEmbers`: ≤ 40 ромбов-угольков от фронта, тело team.pN.screen, кромка accent.warm, 600 мс.
- **FX-28** CUE-014: `AbilityTriggered` Medusa в `ComputeCues`, `bAbilityBoost` Arthur в постановке боя, сокет и система —
  поле героя (`by_hero`, SocketResolver).
- **FX-30** `FS09AbilityStage` + `NS_FX_MedusaVortex`: вихрь t0, контакт t0+454, «−N» +60, HP +80; гейт A1.
- **FX-32** `NS_FX_ArthurArc` у сокета Weapon в кадр FlipAttack, 400 мс × скорость.

## Решения по делегированию (ВР-VS6, «по делегированию», 2026-10-08)

- **ВР-VS6-22** Угольки, вихрь и дуга — носители одной частицы (рецепт пыли F1 / звезды F2, ВР-VS6-06 / -13): рисунок и
  время — в шейдере по ParticleRelativeTime (модулей Spawn Rate / SubUV / Shape Location из скрипта не добавить). Два
  мастера с одним HLSL: `M_FX_AbilityPrint` (без теста глубины — дуга) и `M_FX_AbilityPrintDepth` (тест глубины —
  вихрь, угольки). `MI_FX_Ember` / `MI_FX_Vortex` / `MI_FX_Arc` перевешены с `M_FX_Print`, `fx_import.py` их не трогает.
- **ВР-VS6-23** User-параметры карточек (FrontHeight, TeamScreenColor, DissolveMs, ArcTilt) связаны с параметрами
  материала через Niagara material parameter bindings (MID берёт значение каждый кадр); C++ пишет
  `UNiagaraComponent::SetVariable*`.
- **ВР-VS6-24** Угольки спавнит FX-адаптер режима игры в первом кадре, когда фигура растворяется (опрос, ≤ 1 кадр), и
  пишет FrontHeight каждый кадр — не `AS08FighterActor` (горячий файл; актёр не знает спавнер и часы CUE). Трасса
  `FX embers fighter= t= dissolve= count= look= result=`.
- **ВР-VS6-25** Жизнь уголька 250–400 мс ограничена 600 мс системы (ВР-13): поздние угольки живут 112–250 мс; тело ромба
  — 60 % (цвет команды читается на K2), кромка 20 %, обводка 20 %; квад к камере сдвинут к камере на радиус фигуры (тест
  глубины включён — угольки перед телом, за чужими фигурами); цилиндр 0,35 H — проекцией R·cos θ.
- **ВР-VS6-26** Фронт v2.5: accent.warm как экранная цель через обратную тоновую кривую FX-05, маска
  saturate(Edge × DissolveEdgeEmissive) закрывает альбедо; DissolveEdgeEmissive 1,5 → 3,0 (первые кадры: медиана
  полосы ΔE76 23 → 19–21).
- **ВР-VS6-27** Ось клинка — ось сокета Weapon, ближайшая к вертикали мира (X сокета на риге Arthur v2 лежит поперёк
  поднятого меча, и дуга упиралась в ограничение 45°); дуга наклоняется на наклон клинка (на бенче −5°).
- **ВР-VS6-28** Вихрь — меш из двух горизонтальных квадов (0,45 H и 0,7 H; 1,4 H и 1,12 H), верхний отзеркален по U —
  «вращение навстречу» даёт зеркало, а не лишний поворот 180°/с (кольца атласа FX-29 уже вращаются навстречу); рыскание
  ставит сектор вспышки кадра 12 к камере (ВР-VS2-FX29-08).
- **ВР-VS6-29** CUE-014 Arthur — атака Arthur с любым раскрытым бустом (правило AU-S5: id буста способности защитнику не
  виден).
- **ВР-VS6-30** Взгляд Medusa: правило в `ComputeCues` (старые `metadata.pendingEffects` применённого состояния), старт
  постановки в `HandleApplied` до отрисовки доски (`GetApplyingCues`) — удержание HP / фигуры цели с кадра снимка; конец
  = max(t0+800, контакт+80, падение); «−N» 900 мс не масштабируется (как вихрь); CUE-011 цели — staged.
- **ВР-VS6-31** Дуга — квад к камере с центром на сокете, сторона 1,75 ячейки (пивот ячейки в центре квада при наклоне до
  45°), приоритет сортировки 30 (= 20 эффектов + 10 карточки).
- **ВР-VS6-32** Поле героя CUE-014 в таблице — `vfx.by_hero` (система, сокет, строка vfx.csv), `SocketResolver`
  диспетчера пишет сокет героя в строку показа; эталонная модель и C++-порт фикстур читают его одинаково.
- **ВР-VS6-33** `de011.py compare --evidence` — отчёт AN-29 в свою папку (`VISUAL/AN-29/de011`), лист DE-011 не
  переписывается.

## Проверки

- Сборки (worktree): UnmatchedEditor и `Unmatched Win64 Development` — Succeeded (`C:/tmp/visual/vs6-f3/build-*.log`).
- UE: полный `Unmatched.S08+S09+S10` — 531 Success, 1 Fail (`CueDispatcher.Fixtures`: фикстура `missing-assets-fallback`
  ещё без `NS_FX_AshEmbers` в unloadable — правлена во время прогона); повтор `CueDispatcher.* + CueFx.* + HeroesV2.* +
  S09.AbilityStage + S09.CombatStage` — **29 / 29 Success** (`logs/tests-2.log`), в т. ч. новые `CueFx.AbilityCues`,
  `CueFx.AbilityFx`, `HeroesV2.DissolveStyle`, `S09.AbilityStage.Timeline`.
- Python: `cue_contract.py validate-table` PASS (18 CUE, missing-report: только CUE-001 sfx); `run-fixtures` PASS 22 / bad 0;
  `pytest tools/s08/cue_contract tools/s08/hud_contract` 145 passed; `test_ue_v2_master.py` 27 passed;
  `fx_ability.py` PASS; `fx_import.py --check` PASS; fx_audit (в UE) ok — 8 систем; `de011.py compare` all_ok.
- Кадры (editor `-Bench`, Marmoreal original — нарисованный задник, Sarpedon original — lit3d, шесть фигур v2):
  угольки +0/+150/+300/+500/+600 (Medusa P1 герой, Harpy P1 помощник, Arthur / Merlin P2), вихрь t0+0…+600, дуга
  F0+0…+400, откат fade. Фронт: медиана «тёплых» пикселей полосы ΔE76 19,4 (Marmoreal) / 21,5 (Sarpedon) к #FFB45C,
  p25 10,8 / 11,6 (грубая метрика: в полосу входят края угольков и смешение TSR); пикселей ≥ 245 — 0,10 % / 0,001 % кадра.

## Кадры, которые я открыл

`C:/tmp/visual/vs6-f3/bench/{m-ash,m-ash2,s-ash,m-fade,m-vortex,m-vortex12,s-vortex,m-arc,s-arc,ser-*}/bench-K2x1p6-1920x1080.png`
(кропы ×3…×4, цвет и серый), лист DE-011 `sheet-de011-after.png` (до правки типов он показал провал компиляции MIC —
найдено и исправлено, ВР-VS6-26), все листы карточек этого шага. Первые прогоны нашли: дугу на упоре −45° (ВР-VS6-27),
блёклый тёмный фронт (ВР-VS6-26), ромбы без читаемого цвета команды (ВР-VS6-25), уход кадрирования K2 при скрытой фигуре
(`2590f74e`), неверную ось импорта OBJ (Y зеркален — исправлено в `fx_ability.py`).

## Остатки и почему

1. Приёмочные кадры packaged `-Bench` с `RENDER`, живая партия до GAME_OVER на обеих картах (DS1–DS6, `style=ash`, A1 с
   `--min-ability`, CUE-014 у обоих героев, G-CUE), `run-combat-demo`, кадры хука FXSHOT (`s09-fx26-embers-d300`,
   `s09-fx30-vortex-t300`, `s09-fx32-arc-f133`) — шаг Frames (одна упаковка; бой требует двух клиентов и бэкенда).
2. render_bench: G-COST «пепел» против fade ≤ 0,1 мс (`dx12-lumen-high-v2-dissolve-ash` / `-fade`), угольки ≤ 0,05,
   вихрь ≤ 0,05, дуга ≤ 0,03 мс — FX-37 / Frames. MIC растворения: 889 PS-инструкций (родитель 779).
3. AN-29: строгий замер «медиана полосы фронта ΔE76 ≤ 10» на packaged K2×1,6 — Frames; моя метрика 19–21 (p25 ≈ 11);
   если не пройдёт — поднять DissolveEdgeEmissive или сузить DissolveEdgeWidth (параметры Cue-группы).
4. Бенч: цифра гарпии на подставке и тёмная подставка при прогрессе 1 видны только на `-BenchFx=ash` (живая смерть
   скрывает цифру со старта растворения и фигуру после него).
5. Подписи «Medusa 16/16» над фигурами — мировые подписи `-ArtPreview` бенча (остаток Z-2, как в F2).
