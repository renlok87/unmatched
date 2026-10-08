# FX-10 — CUE-004 знак X отказа у клетки

Шаг VS-6 F1, коммит `a797f97c` (ветка `feat/visual-vs6`, не влито). Общий отчёт, решения ВР-VS6-NN, тесты и остатки — [../VS-6-F1/README.md](../VS-6-F1/README.md). Кадры — editor-client `-Bench` (проверочные), приёмочные packaged `-Bench` с `RENDER` — шаг Frames. Статус: технически импортировано.

- Штамп `badge-refuse` у клетки (UMG HB-40, `UUmToastStack::ShowBadge`): 0 мс scale 1,2 / opacity 0 → 80 мс 1,0 / 1, удержание до 230, угасание к 350; reduced motion — только прозрачность ≤ 100 мс (`S08FieldFx::RefuseStamp`).
- Размер: clamp(0,3 × диаметр клетки на экране; 24; 32) px (ВР-VS6-04); повтор раньше 300 мс не перезапускает знак (`ShowBadge` → false, трасса `HUD-REFUSE … restart=0`), звук — `sfx=throttled`.
- Красной заливки клетки нет: `ShowIllegalCell` рисует диск только с `-S08FxLegacy`. Тряски нет.
- Строка CUE-004 (local, retrigger 300, max 1), трасса `CUE fx id=CUE-004`.
- Кадра нет: в `-Bench` UMG HUD не строится — кадры 1080p / 720p на красной и зелёной клетке — живой прогон шага Frames (остаток 3 общего отчёта).
