# FX-28 — CUE-014 событие способности и сокет по герою

Шаг VS-6 F3 (`c10f2062`, не влито). Общий отчёт — [../VS-6-F3/README.md](../VS-6-F3/README.md). Статус: **технически
импортировано**; живая партия Medusa против King Arthur на обеих картах (строки CUE-014 обоих героев, G-CUE) — Frames.

- `FS08FlowController::ComputeCues(…, OldMetadata, …)` → `ES08CueType::AbilityTriggered` (`S08/Fx/S08AbilityCues.*`):
  pending `ability-medusa-target-p<n>` (TARGET_FIGHTER) применённого состояния исчез из `metadata.pendingEffects`
  снимка (отсутствие массива — тоже «исчез»), и одна из его целей потеряла HP → cue перед уроном: subject = герой
  игрока pending, цель, урон, HP до, клетка цели. Отказ (HP не изменился), открытый pending, отсутствие pending (карта
  Gaze of Stone), барьер / разрыв — cue нет. Бэкенд не тронут.
- King Arthur: `FS09CombatStageInput::bAbilityBoost` = атакующий King Arthur и есть раскрытый буст (ВР-FX10, ВР-VS6-29)
  → CUE-014 атакующего в кадр `FlipAttack`.
- Поле героя: cue-table CUE-014 `vfx.by_hero` — KingArthur `Weapon` NS_FX_ArthurArc (FX-32), Medusa `Root`
  NS_FX_MedusaVortex (FX-30) (ВР-VS6-32); реестр `S08CueFx` (бюджет вихря 2), `SocketResolver` диспетчера → трасса
  `socket=Weapon` / `socket=Root`, токен vfx — система героя.
- Фикстуры `ability-medusa-gaze.json`, `ability-arthur-boost.json`: run-fixtures PASS (22 / 0), C++-порт
  `Unmatched.S08.CueDispatcher.Fixtures` PASS; `CueDispatcher.Table`, `CueFx.Registry` (by_hero ↔ реестр),
  `CueFx.AbilityCues` (правило cue), `CueFx.AbilityFx` (сокет в строке показа) — PASS.
