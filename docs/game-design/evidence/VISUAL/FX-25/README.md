# FX-25 — CUE-012 лечение: событие и сборка

Шаг VS-6 F2, коммит `e67def78` (ветка `feat/visual-vs6`, не влито). Общий отчёт — [../VS-6-F2/README.md](../VS-6-F2/README.md).
Статус: **технически импортировано**; живая партия с The Holy Grail на обеих картах и лист K2 — шаг Frames.

- `FS08FlowController::ComputeCues` — тип `FighterHealed` (ВР-FX13): HP бойца, живого до и после, выросло; N = HP после −
  HP до; после строк урона seq; воскрешение (HP 0 / `isDefeated`) — не лечение. Тест `Unmatched.S08.CombatFx.Heal`.
- Показ: кадр снимка + 200 мс; если идёт постановка того же seq — в её `stage=end` (`S08FxCombatEnd`), с seq боя и `staged`
  (без D3). Строка CUE-012 в `S08CueRows` (server, replace subject, reduced shorten 100, vfx `NS_FX_HealMotes`, сокет Base);
  трассы `CUE fx id=CUE-012 … vfx=NS_FX_HealMotes socket=Base`, `FX heal plan`, `FX heal … motes=`.
- «+N» — виджет FX-22 (700 мс), точки FX-24; реконнект: снимок-барьер не даёт cue — лечения нет.
- Фикстура `docs/unreal/contracts/cue-dispatcher/fixtures/heal-after-combat.json`: бой seq 50, следующий ход уже объявил
  атаку (seq 51), лечение Arthur в конце постановки — показ, повтор — duplicate, старый seq без постановки — stale;
  run-fixtures PASS (20 / 0), C++ `CueDispatcher.Fixtures` PASS.
- Остатки: HP в теге — новое значение с кадра снимка (не t0+80); звук лечения `CMB-HEAL` (чат звука) звучит в кадр снимка,
  а не в кадр показа — см. сводку.
