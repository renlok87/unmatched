# FX-P4 — худший набор VFX: бенч ΔGPU и лист приёмки P4 (FX-37)

Карточка FX-37 (`docs/game-design/visual/06-tasks/vfx.csv`), шаг Frames спринта VS-6. Worktree `C:/tmp/wt-visual`, ветка
`feat/visual-vs6`, **не влито**. Пакет приёмки — `bcaf737b` (штамп `Saved/StagedBuilds/Windows/BuildStamp.json`,
sourceHash `c1c480c9…`). Решения и приёмка — по делегированию пользователя 2026-10-06 («Все решения принимай»);
статусы «художественно принято, по делегированию 2026-10-08» стоят только у того, что я открыл и проверил глазами.

## Как мерили

- `tools/art/render/render_bench.py run`, упакованный Development `-Bench`, без лимита FPS, RTX 4090, High, SP 100,
  виды K1 и K2×1,6, warm-up 30 с, settle 8 с, measure 20 с, ProfileGPU + CSV по проходам. Под замком
  `C:/tmp/unmatched-gpu.lock`, других клиентов UE не было.
- База fix/admin-panel — копия staged-сборки основной копии (`b68e21b4`, VS-5) в `C:/tmp/visual/VS6/staged-main`
  (`--exe`; CSV профайлера теперь ищется рядом с запущенным exe).
- Новые варианты (`74a0b85d`): `dx12-lumen-high-v2-fx-each-<star|heal|ash|vortex|arc|dust|chevrons|grade>`,
  `-fx-worst`, `-fx-worst-legacy` (контроль `-S08FxLegacy`), список худшего набора — `--fx-worst`. Набор строится из
  шагов `-BenchFx` клиента, каждая система заморожена на середине жизни (ВР-VS6-46). Тест
  `tools/art/tests/test_render_bench_fx37.py`.
- Худший набор (CUE-DISPATCHER §9 п. 4 под капом NET_UM_Combat = 3): взгляд Medusa убивает King Arthur — вихрь
  (CUE-014) + звезда (CUE-011) + 40 угольков с растворением Arthur (CUE-013), плюс пыль (CUE-007) и шевроны (CUE-008).
  Грейд CUE-016 живёт только при GAME_OVER, поэтому он оценён отдельно на теле `-BenchResult=board` против того же тела
  с `-S08FxLegacy` и прибавлен (ВР-VS6-47).
- Кап проверен отдельно в editor-клиенте: пять боевых систем одновременно — четвёртая и пятая `result=missing`
  (`C:/tmp/visual/VS6/pre/m-cap5`).

## Итог (пакет `bcaf737b`, 3 повтора)

| Карта, вид | fix/admin-panel | база ветки | худший набор | Δ к fix/admin-panel | Δ к базе ветки | разброс |
|---|---|---|---|---|---|---|
| Marmoreal K1 | 2,13 / 2,13 / 2,14 | 2,14 ×3 | 2,17 / 2,16 / 2,17 | **+0,033** | +0,027 | ≤ 0,01 |
| Marmoreal K2×1,6 | 2,20 ×3 | 2,20 ×3 | 2,22 / 2,21 / 2,22 | **+0,017** | +0,017 | ≤ 0,01 |
| Sarpedon K1 | 2,61 / 2,61 / 2,62 | 2,60 ×3 | 2,62 / 2,62 / 2,65 | **+0,017** | +0,030 | ≤ 0,03 |
| Sarpedon K2×1,6 | 2,50 / 2,50 / 2,51 | 2,51 / 2,52 / 2,51 | 2,56 / 2,55 / 2,57 | **+0,057** | +0,047 | ≤ 0,02 |

- Грейд CUE-016: +0,010 мс (Marmoreal), +0,015 мс (Sarpedon), 2 повтора. Худший набор + грейд ≤ **0,07 мс** при
  пороге 1,0 мс — **G-COST PASS** на обеих картах.
- Проходы: Lumen (SceneUpdate, ScreenProbeGather, Reflections) не растут (|Δ| < 0,002 мс); весь прирост —
  Translucency +0,008…+0,017 мс. Draw calls худшего набора +9,3…+10 (эффекты).
- Контроль `-S08FxLegacy` на том же наборе: Δ −0,01…+0,007 мс (шум).
- fx-each (пакет 1, 1 повтор, к базе того же пакета): каждая система +0,00…+0,04 мс — все в пределах шага 0,01 мс
  трассы, ранжирование «трёх самых дорогих» по замеру невозможно; взяты три самых тяжёлых по спрайтам (40 угольков,
  меш вихря, звезда 0,8 H), ВР-VS6-46.
- **MS-AT-41 (повтор):** плашки сцены 2 (`*-2-draft-conflict-needboost`) против базы того же пакета: Δ draw calls K1
  **0,0 / 0,0** (≤ 7), K2×1,6 −35 / −78; ΔGPU 0,00 / −0,04 мс — PASS.
- **UNiagaraEffectType (ВР-25):** повтор аудита FX-04 (`tools/art/fx/fx_audit.py` в редакторе) — ok, 8 систем,
  у каждой NET_UM_Combat или NET_UM_Board, бюджеты спрайтов в норме (`../FX-04/fx-audit.json`).
- Данные: [data/fx37-cost.json](data/fx37-cost.json) (все повторы, проходы, draw calls), пакет 1 до исправления —
  [data/fx37-cost-pkg1-before-nanite-fix.json](data/fx37-cost-pkg1-before-nanite-fix.json).

### Найдено бенчем и исправлено (ВР-VS6-48)

Первый пакет (`74a0b85d`) показал базу ветки на **+0,31…+0,39 мс** дороже fix/admin-panel на обеих картах. ProfileGPU:
`ShadowDepths` 0,33 против 0,065 мс, внутри — проход **«Nanite Shadows» 0,26 мс** в каждом кадре, даже без эффектов и с
`-S08FxLegacy`. Причина: `SM_FX_VortexRings` (F3) импортирован Interchange с `bBuildNanite`, а зарегистрированные
компоненты вихря (прогрев / пул) давали Nanite-тень. Исправления:
- `20d7951c`: компоненты CUE не отбрасывают тень и не входят в Lumen / DF (`SceneNeutral`), проход прогрева
  гасится через 0,5 с, при `-S08FxLegacy` прогрева нет;
- `9edb16d3`: пакет 2 падал через 0,5 с (null в лямбде таймера после `DeactivateImmediate`) — проверка указателя;
- `bcaf737b`: `SM_FX_VortexRings` без Nanite (`tools/art/fx/ue_fx_mesh_flags.py`, импорт `ue_fx_ability.py` делает так же).
Пакет 3 (только C++) ещё держал «Nanite Shadows» — причина подтверждена ассетом; пакет 4 (`bcaf737b`): `ShadowDepths`
0,079 мс, база ветки = fix/admin-panel (Δ −0,013…+0,010 мс).

## Лист приёмки (кадры свежего packaged `-Bench` пакета `bcaf737b`, 1920×1080, RENDER в эталоне)

Все листы — кропы ×3 (200×150 → 600×450) в цвете, в сером и при дейтеранопии (Machado 2009), JPEG; кадры доски без HUD.

| Лист | Что | Вывод |
|---|---|---|
| [hit-heal-k1.jpg](hit-heal-k1.jpg), [hit-heal-k2.jpg](hit-heal-k2.jpg) | звезда через 135 мс после спавна (C+205) на Arthur, 4 точки лечения на Merlin, обе карты | звезда с тёмным кантом читается на розовой и красной клетке; точки и звезда различимы по форме в сером |
| [death-ability-k2.jpg](death-ability-k2.jpg) | вихрь Medusa t300, пепел гарпии d300, дуга Arthur f150 + пепел Merlin | вихрь — два кремовых кольца, угольки-ромбы цвета команды, дуга над Arthur; в сером всё держится |
| [field-k1.jpg](field-k1.jpg), [field-k2.jpg](field-k2.jpg) | след хода, дуги цели + жетон IC-35, шевроны, ожидающие клетки, пыль, кольцо выбора | бирюзовое кольцо и дуги цели читаются; шевроны указывают направление и в сером |
| [strips-star-ash-k1.jpg](strips-star-ash-k1.jpg), [strips-vortex-arc.jpg](strips-vortex-arc.jpg) | полосы таймингов: звезда через 20/135/250 мс после спавна (C+90/205/320), пепел d100/300/500, вихрь t120/300/480, дуга f50/150/320 | фазы видны: звезда растёт, к C+320 остаётся контур; пепел d500 — только угасающие угольки |
| [rollbacks-k2.jpg](rollbacks-k2.jpg) | откаты `-S08HitTintLegacy`, `-S08DissolveFade`, `-S08ChoiceLegacy`, `-S08FxLegacy` | фейд без угольков, старое кольцо, без систем; вспышка бенча откат оттенка не показывает (ВР-VS6-53, живой прогон rb) |
| [live-hooks-crops.jpg](live-hooks-crops.jpg) | живые кадры хука: вспышка C+20 и «−1», звезда C+137 и «−9», обод защиты, вихрь t300, пепел d300, дуга f133 | всё видно; дуга f133 — только начало взмаха, обод защиты слабый на тёмном поле |
| [worst-*-k1.jpg](worst-marmoreal-k1.jpg), [worst-*-k2x1p6.jpg](worst-marmoreal-k2x1p6.jpg) | худший набор целиком | шесть фигур v2, нарисованный Marmoreal / lit3d Sarpedon, слоя отладки нет |
| [desat-marmoreal-k1.jpg](desat-marmoreal-k1.jpg), [desat-sarpedon-k1.jpg](desat-sarpedon-k1.jpg) | обесцвечивание связи w=1 | HSV S кадра −30,6 / −30,2 % (w 1/3: −9,7 / −9,8 %) |
| [reduced-motion-bench-marmoreal-k1.jpg](reduced-motion-bench-marmoreal-k1.jpg) | `-S08ReducedMotion` в бенче | фейд смерти, окружение заморожено; постановщик `-BenchFx` reduced motion не учитывает — живые кадры h-* |
| [field-*-k1.jpg](field-marmoreal-k1.jpg), [rollback-fxlegacy-marmoreal-k1.jpg](rollback-fxlegacy-marmoreal-k1.jpg) | целые кадры | доска, задник, фигуры |

Кадры победы (грейд, полоса результата и портреты — HUD) и все живые кадры HUD — вне git, индекс
[../VS-6/data/vs6-evidence-index.json](../VS-6/data/vs6-evidence-index.json) (ВР-VS4-01).

## Флаги отката

`-S08FxLegacy` (все CUE-системы, прогрев 0), `-S08HitTintLegacy`, `-S08DissolveFade`, `-S08ChoiceLegacy`,
`-S08FigureCueLegacy`, `-S08MovePlatesLegacy`, `-S08TargetArcLegacy`, `-S08LastMoveLegacy`. ARTLOOK в живых прогонах rb /
rbfx: `hitFx=legacy fieldFx=legacy death=legacy` и `fx=legacy combatFx=legacy`.

## Итог карточки

FX-37 — **художественно принято, по делегированию 2026-10-08**: G-COST PASS (≤ 0,07 мс), ≤ 3 боевые системы (кап
проверен), UNiagaraEffectType у всех, MS-AT-41 PASS, G-GRAY по листам PASS, G-LOOK PASS. Открытое — в
[../VS-6/README.md](../VS-6/README.md).
