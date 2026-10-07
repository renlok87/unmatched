# FX-06 — лист приёмки

**Статус: технически импортировано.**

Строка CUE-001 (local, replace_scope cue, reduced keep, sfx-троттлинг 150 мс, mat=Rim) в S08CueRows;
hover-хук `S08FxHoverChanged` (обод 0.6/0.2 с удержанием, уход 120 мс, павшие без обода); фикстура
hover-retrigger переносится в C++ (Unmatched.S08.CueDispatcher.Fixtures — портится автоматически, строка в
таблице есть).

## Критерии и результат

| критерий | результат | доказательство |
|---|---|---|
| кадры packaged -Bench, RENDER, обе карты, наведение на Arthur, Medusa и гарпию 2 | 6 прогонов: обод 0.6/0.2 виден на всех трёх фигурах обеих карт (кропы ×4) | `C:/tmp/visual/Z-2/bench/{map}-hover-f-{1-hero,0-hero,0-sk1}/bench-K1…png`; трейсы `FX bench rim fighter=… i=0.60 w=0.20` + `CUE fx id=CUE-001 … mat=Rim result=spawned` в bench.trace.log |
| обод виден на тёмном небе Marmoreal и на красной палубе Sarpedon | виден на обеих (кроп ×4 каждой) | `C:/tmp/visual/Z-2/_fx-rim-stack.png` (строки hover) |
| hover-retrigger PASS в C++ | порт фикстуры: Fixtures теперь пропускает hover-retrigger.json (7 строк таблицы) | `C:/tmp/visual/Z-2/tests-cuedispatcher.log` EXIT=0; счётчик строк таблицы 7 в тесте Table |
| G-CUE PASS | PASS (демо-трейсы) | `C:/tmp/visual/Z-2/demo/*/combat-*/combat-client-host.trace.log` |

Без звука/масштаба фигуры/обода на подставке; обод не красится командой. Reduced: сразу 0.6/100 мс.
Входы (sha256-16): hover-arthur marmoreal 16c74a1e79e6a4c4 · hover-medusa K2 bf96122e9c9a564e ·
hover-harpy marmoreal 6d1cd8e028cdebe5 · hover-arthur sarpedon 6fa2d482746f3d9f ·
hover-harpy sarpedon fdfdd921823cd718.
