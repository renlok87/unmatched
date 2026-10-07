# FX-03 — лист приёмки

**Статус: технически импортировано.** Художественную приёмку делает визуальный чат.

Реестр `S08/Fx/S08CueFx.h/.cpp` (CUE → система/тип/крепление/бюджет, сид CRC32), спавнер
`S08/Fx/S08CueFxSpawner.h/.cpp` (прогрев + пул AutoRelease + грейд), адаптер `S08/Fx/S08FlowGameModeFx.cpp`,
типы `NET_UM_Combat`/`NET_UM_Board`, система плашки `NS_FX_PlacardStar`, откат `-S08FxLegacy` (ARTLOOK `fx=`).

## Критерии и результат

| критерий | результат | доказательство |
|---|---|---|
| Unmatched.S08.CueFx.Registry PASS | PASS (сверяет все vfx-блоки cue-table.json: пути/attach/socket/prewarm) | лог `C:/tmp/visual/Z-2/tests-cuefx.log` (Result={Success}); полный набор `C:/tmp/visual/Z-2/tests-s08-full.log` — 97 Success / 0 Fail |
| G-CUE PASS на живой партии, обе карты | PASS host+joiner × 2 карты + легаси-прогон | `C:/tmp/visual/Z-2/demo/{marmoreal,sarpedon}/combat-*/combat-client-*.trace.log` |
| `vfx=NS_FX_*` вместо missing | **частично, отложено до FX-13+** (системы боя создаёт визуальный чат): CUE-011 `vfx=missing` честно; резолвер уже называет реальные активы — CUE-009 `sfx=SW_CMB_DEFENSE_PLAYED_01 … result=spawned`, CUE-011 `clip=AM_Medusa_HitReact` вместо missing (ВР-FX16) | строки `CUE fx id=CUE-009|CUE-011` в тех же trace.log |
| `FX prewarm` раньше первого `CUE fx` | да: `FX prewarm systems=0 ms=1` (0 — в реестре пока нет существующих систем, ВР-Z2-01) | trace.log демо (первая FX-строка до первого CUE fx) |
| первый показ без кадра > 33 мс | боевые системы не спавнятся (missing) — критерий применим к системам FX-13+; плашка bench-only прогревается пулом (PoolPrimeSize 2) | describe `C:/tmp/z2-fx/fx-systems.json` |
| packaged -Bench находит все системы (нет result=fallback) | спавн плашки: `FX bench placard star=registered` — все существующие системы грузятся; fallback нет | `C:/tmp/visual/Z-2/bench/marmoreal-placard-1/bench.trace.log` |
| кук /Game/S08/FX | покрыто существующей строкой `/Game/S08` (DefaultGame.ini:17) — отдельная не нужна (ВР-Z2-07); 17 FX-файлов в манифесте пакета | `Saved/StagedBuilds/Windows/Manifest_UFSFiles_Win64.txt` (grep "S08/FX" = 17) |

Прогрев ≤ 300 мс: `FX prewarm ms=1`. Входы: demo/marmoreal/combat-…/host/s09-combat-result.png (4fef34ba24bc5d1a),
bench плашки — как в FX-02.
