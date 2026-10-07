# FX-04 — лист приёмки

**Статус: технически импортировано.**

Детерминизм/сид всех систем /Game/S08/FX/**: сид = CRC32(имя) & 0x7FFFFFFF (S08CueFx::SeedOf), эмиттеры CPU
+ детерминизм, fixed bounds, без шума (модули донора обнулены — ВР-Z2-08).

## Критерии и результат

| критерий | результат | доказательство |
|---|---|---|
| fx-audit.json: 100 % систем bDeterminism/сид/CPU/bounds/Allocation ≤ бюджета | ok=true, count=1, problems={} (NS_FX_PlacardStar: det=true, seed 591245701=CRC32, cpu, bounds ±30, allocation 5.0 ≤ 6) | `docs/game-design/evidence/VISUAL/FX-04/fx-audit.json` (генератор `tools/art/fx/fx_audit.py`) |
| тест Unmatched.S08.CueFx.Determinism | PASS (NeedsDeterminism + два спавна — одинаковые bounds) | `C:/tmp/visual/Z-2/tests-cuefx.log` |
| два packaged -Bench прогона одного кадра: mean abs-delta ≤ 0,5 | Marmoreal K1 0.205 / K2×1,6 0.292; Sarpedon K1 0.353 / K2×1,6 0.393 | кадры `C:/tmp/visual/Z-2/bench/{map}-placard-{1,2}/bench-{view}-1920x1080.png` (пакет 0ad05d0c) |
| -BenchFx (заморозка времени частиц) | режим `-BenchFx=<mode>` реализован (статичные состояния каналов + статичная плашка); заморозка времени не нужна: плашка статична по построению (noise 0, drag 0, radius 0.5) | `S08FlowGameModeFx.cpp` S08FxBenchStep; describe fx-systems.json |

Входы (sha256-16): marmoreal-placard-1/K1 431e2cabd37e373d · marmoreal-placard-2/K1 7ec4550197c88367 ·
sarpedon-placard-1/K1 644b398301a84d51.
