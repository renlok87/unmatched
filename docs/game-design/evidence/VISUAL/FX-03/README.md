# FX-03 — лист приёмки

**Статус: технически импортировано** (ревью 2026-10-07: доработано, см. ниже). Боевые системы появятся в FX-13+.

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

## Ревью и доработка 2026-10-07

Ложные утверждения Z-2 исправлены (правка 13 обзора): «97 Success / 0 Fail» — набор S08 падал на CueFx.Determinism и обрывался; «Determinism PASS» — тест падал; «трассы ms=300» — в демо было ms=0 (секунды вместо мс); хит-трио демо не доказывало FX-19 (вспышка жила один кадр). Таблицы ниже старой версии оставлены как история и в этих местах недействительны.

- Лимиты ВР-25 выставлены (`a13e6777`): NET_UM_Combat 3, NET_UM_Board 6, CullReaction Deactivate —
  `US08FxAuthoringLibrary::SetEffectTypeCaps`; тест `Unmatched.S08.CueFx.EffectTypes` PASS (ВР-Z2R-04: сейчас, не в FX-13).
- Спавнер не пишет мёртвый user-параметр RandomSeed; прогрев — флаг на компоненте, не static.
- Приоритет сортировки полупрозрачных FX = 20 (поверх плиток хода 10). Комментарий в `S08CueFx.h` связывает его с
  прозрачным ромбом — это неверно (причина была в маске Opacity, FX-02); исправить формулировку при следующей
  правке C++ (сейчас это сменило бы хеш исходников пакета).
- Листы FX-03 sheet-01/02 с аватарами вынесены из git (ВР-VS4-01): индекс `../Z-2/visual-evidence-index.json`.
- Живой бой на пакете `c4db1fba`: G-CUE PASS на 4 прогонах × 2 клиента; `FX prewarm` раньше первого `CUE fx`.
