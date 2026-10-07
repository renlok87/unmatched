# FX-04 — лист приёмки

**Статус: технически импортировано** (ревью 2026-10-07: тест переписан и проходит, A/B в пороге).

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

## Ревью и доработка 2026-10-07

Ложные утверждения Z-2 исправлены (правка 13 обзора): «97 Success / 0 Fail» — набор S08 падал на CueFx.Determinism и обрывался; «Determinism PASS» — тест падал; «трассы ms=300» — в демо было ms=0 (секунды вместо мс); хит-трио демо не доказывало FX-19 (вспышка жила один кадр). Таблицы ниже старой версии оставлены как история и в этих местах недействительны.

- Тест `Unmatched.S08.CueFx.Determinism` (`b6561dac`): мир с контекстом, BeginPlay, синхронный AdvanceSimulation двух
  компонентов, позиции частиц в 0,1 / 1 / 6 с. Под -nullrhi Niagara не активируется вовсе, поэтому там тест
  проверяет половину ассета и пишет об этом (ВР-Z2R-05); полная проверка — в процессе с RHI:
  `C:/tmp/visual/Z-2/review/tests-cuefx-determinism-rhi-final.log` — PASS (1 частица размером 96 с первых 0,1 с, позиции двух спавнов совпадают в 0,1 / 1 / 6 с).
- fx_audit: emitters disabled пропускаются, бюджет burst-систем считается; `fx-audit.json` ok.
- A/B двух packaged прогонов плашки (pk / pk2), область плашки mean |Δ|: Marmoreal K1 0,362 · K2 0,333;
  Sarpedon K1 0,321 · K2 0,361 (порог 0,5).
