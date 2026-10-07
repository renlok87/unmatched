# FX-06 — лист приёмки

**Статус: технически импортировано** (ревью 2026-10-07: наведение видно на K1, но на гарпии слабое — замечание ниже).

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

## Ревью и доработка 2026-10-07

Ложные утверждения Z-2 исправлены (правка 13 обзора): «97 Success / 0 Fail» — набор S08 падал на CueFx.Determinism и обрывался; «Determinism PASS» — тест падал; «трассы ms=300» — в демо было ms=0 (секунды вместо мс); хит-трио демо не доказывало FX-19 (вспышка жила один кадр). Таблицы ниже старой версии оставлены как история и в этих местах недействительны.

Длительности теперь в мс (`2b5278b4`): вход 150 мс ease-out, удержание, уход 120 мс (тест FxChannelTiming).
Обод наведения — тонкая кремовая кромка (интенсивность 0,6 сужает полосу, цвет полный, ВР-Z2R-08).
Средняя яркость маски фигуры на K1 (база → наведение): Marmoreal Arthur 0,218 → 0,495, Medusa 0,271 → 0,523,
гарпия 2 0,297 → 0,537; Sarpedon 0,217 → 0,499, 0,251 → 0,486, 0,321 → 0,510. На гарпии наведение видно слабо
(кроп ×4). Я открыл все шесть кропов ×4 в цвете и сером.
