# FX-34 — CUE-016 грейд и виньетка исхода

**Статус: технически импортировано (VS-6 F4, `1ddec221`, ветка `feat/visual-vs6`, не влито).** Кадры — editor `-Bench`
(проверочные). Приёмочные packaged-кадры и живая партия до GAME_OVER на двух клиентах — шаг Frames. Приёмка — по
делегированию.

## Что сделано

- `S08/Fx/S08CuePostProcess.h/.cpp`: мировой независимый расчёт (`FS08CuePostProcessState`, `Compose`) и один
  несвязанный `APostProcessVolume` с приоритетом 200, выше объёма экспозиции профиля доски (100). Объём профиля
  задаёт только экспозицию, виньетку не задаёт: база — движковая 0,4, `grade.devignette 0,4` вклейки снимает ровно её,
  поэтому +0,25 видно и на нарисованной плите.
- Наборы: победа — WhiteTemp 6500 → **7100**; поражение — WhiteTemp 6500 → **5700**, ColorSaturation × 0,8; оба —
  VignetteIntensity 0,4 + 0,25. Вес 0 → 1 за 500 мс ease-in-out (reduced motion — 100 мс).
- Старт: запланированное время строки `CUE death stage=gone` павшего героя (`FS09DeathStage::LatestHeroGoneMs`),
  без смерти героя — кадр `RESULT screen`. Свой вердикт каждого клиента (`bViewerWon`). Ничья, неизвестный вердикт,
  ABORTED (до GAME_OVER не доходит) и `-S08FxLegacy` — без грейда (`FX grade outcome=none reason=…`). Грейд держится,
  пока применённая фаза — GAME_OVER («посмотреть доску» снимает только вуаль).
- Трасса: `FX grade outcome=<victory|defeat> t=<ms> ms=<500|100> reduced=<0|1> src=<gone|result> fighter=<id>`,
  `FX postprocess on=… temp=… sat=… vignette=…`.
- Адаптер: `S08/Fx/S08FlowGameModeOutcomeFx.cpp` (из `S08FxTick`); горячие файлы — только объявления в `.h`.
- Бенч: `-BenchFx=outcome,<w>[,victory|defeat]` — замороженный вес (кадр «до грейда» = `outcome,0`).

## Приёмка

| Пункт | Итог |
|---|---|
| `FX grade` в кадр `CUE death stage=gone` героя ±17 мс | 0 мс: `FX grade outcome=defeat t=1787 … src=gone fighter=f-0-hero` и `CUE death … stage=gone t=1787` (Marmoreal), 1769 / 1769 (Sarpedon), победа 1778 / 1768 |
| DS5 (экран через 1000 мс) не сдвинулся | `FS09ResultGate` не тронут; полный прогон `Unmatched.S08+S09+S10` 537 / 537 (вкл. `S09.Result*`). В `-BenchResult` экран открывается сразу (так устроен бенч, не живая партия) |
| «посмотреть доску», победа и поражение, обе карты, 6 фигур v2 (павший исчез), K1, до / после, цвет / серый | `-Bench -BenchResult=board [-BenchResultLoser]`, кадры открыты. Кропы ×4 без HUD: [Marmoreal кромка рамы](crops-marmoreal-frame-edge-x4.jpg), [Marmoreal поле](crops-marmoreal-field-x4.jpg), [Sarpedon жаровня](crops-sarpedon-brazier-x4.jpg), [Sarpedon поле](crops-sarpedon-field-x4.jpg). Полные кадры несут портреты (аватары) — вне git, [индекс](visual-evidence-index.json) |
| Числа кадра (K1, [frame-metrics.json](../VS-6-F4/data/frame-metrics.json)) | Marmoreal R/B 1,071 → победа 1,217 (теплее) / поражение 0,909 (холоднее); Y 0,135 → 0,110 / 0,111 (темнее, края). Sarpedon R/B 1,564 → 1,705 / 1,174; HSV S 0,443 → 0,484 / 0,401 |
| В сером поражение темнее и бледнее | темнее — да (Y −18 %); бледнее по HSV S — Sarpedon −9 %, Marmoreal +3 % (холодный баланс поднимает S синих тонов плиты; × 0,8 его не перекрывает) — см. остатки |
| Камера стоит, без bloom / зерна / LUT, UMG не тронут | объём меняет только WhiteTemp, ColorSaturation, VignetteIntensity |
| Бюджет ΔGPU ≤ 0,05 мс | тонмаппер, лишнего прохода нет; замер render_bench — FX-37 / Frames |

## Решения (по делегированию)

- **ВР-VS6-41.** `UPostProcessComponent`, зарегистрированный на режиме игры, кадр не менял (у режима нет корневого
  компонента; движковый класс MinimalAPI, наследовать нельзя) — первый прогон: кадры «до» и «после» совпали байт в байт
  по метрикам. Берётся тот же несвязанный `APostProcessVolume`, что спавнит профиль доски для экспозиции.
- **ВР-VS6-44.** WhiteTemp в UE — опорная точка баланса белого: меньше — кадр холоднее (5900 дало R/B 1,07 → 0,94,
  7300 — 1,20). Числа карточки 5900 / 7300 означали «тёплая победа, холодное поражение» (цель карточки), поэтому
  отклонения зеркалены: победа 7100, поражение 5700. cue-table CUE-016 исправлена.
- **ВР-VS6-45.** Ничья и неизвестный вердикт — без грейда (карточка называет только победу и поражение).

## Остатки

- Живая партия до GAME_OVER (DS1–DS6 + `FX grade` в кадр `gone`), packaged-кадры с `RENDER`, ΔGPU — шаг Frames.
- «Бледнее» в сером на Marmoreal не выполняется по HSV S: если Frames подтвердит на packaged, поднять × 0,8 → × 0,7
  (параметр `DefeatSaturation`).
