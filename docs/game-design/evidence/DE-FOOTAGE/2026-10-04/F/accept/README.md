# Прогон F (S11f): живая приёмка G-LIVE агентом приёмки (2026-10-05)

**Итог: пройдено.** Одна упаковка `b2e5f6d3`, пять живых прогонов по два клиента на Marmoreal original и Sarpedon original.
- `check-trace` PASS на всех 10 трассах.
- Кадры просмотрены глазами до отчёта: настоящая карта, задник по AGENTS.md, шесть фигур v2, строка `ARTLOOK … heroes=v2`.
- Видимые изменения прогона F (DE-029 экран результата и итоговая доска, DE-030 панель колоды) на месте на обеих картах.
- Дефектов кода прогона F не найдено, правок кода нет. Два замечания вне прогона F — в конце.

Ссылки:
- полномочия — [IMPL-2026-10-04.md](../../../../../de-footage/task/runs/IMPL-2026-10-04.md) п. 6;
- журнал — [F-2026-10-04.md](../../../../../de-footage/task/runs/F-2026-10-04.md), раздел «Живая приёмка G-LIVE (агент приёмки)»;
- гейт — [07-sprint-plan.md](../../../../../de-footage/task/07-sprint-plan.md) §8 G-LIVE;
- приёмка DE-031 и её дефекты — [../live/README.md](../live/README.md).

## Упаковка

- HEAD `b2e5f6d3`. Код с итоговой упаковки DE-031 (`bd109788`) не менялся: `b2e5f6d3` — только документы.
- Сборка игровой цели `Unmatched Win64 Development`: `Result: Succeeded` (ничего не пересобиралось).
- `tools/s08/package-client.ps1 -SkipBuild`: `UAT_EXIT=0`, `BUILD SUCCESSFUL`, cook `0 error(s), 0 warning(s)`.
- Штамп — [BuildStamp.json](BuildStamp.json): commit `b2e5f6d3`, sourceHash `aa1cbd79…` (192 файла). Это тот же хеш
  исходников, что у `bd109788`, то есть клиент тот же. Упаковка одна; все прогоны ниже сняты на ней.

## Окружение

- Основной стек `:3000` (unmatched-backend, -postgres, -redis) был поднят до агента. `/health`: database up, redis up.
  Стек оставлен как есть.
- Демо-аккаунты передавались только в окружение процесса, через обёртку `C:/tmp/f-accept/env-s08.cjs` (вне репозитория).
  Нигде не печатались. Код комнаты в трассах — `<redacted>`.
- GPU: каждый прогон — под замком `C:/tmp/unmatched-gpu.lock`, владелец `F-ACCEPT`; после прогона замок снят.
  По 30 FPS на клиент, оба клиента offscreen, пресет High.
- Marmoreal снят с `-ConceptPaste` (IMPL п. 3: ENV-U16 открыт), то есть с нарисованным задником. Sarpedon — `lit3d`,
  путь 1, без оговорок.

## Команды

```
# манёвр хоста через черновик (G-LIVE 07 §8)
run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ArtPreviewBoardId <board> -ClientFps 30 -ClientRenderPreset High
  -RequireRenderReference -RequireShotCaptured -ClientPerf -HostManeuver
  -ClientExtraArgs '[-ConceptPaste+]-S08MovePlates+-S08ManeuverPlan=boost3+-S08ManeuverDraftHold=2.5+-S08ManeuverDraftShot=<png>'
# партия до GAME_OVER: экран результата, итоговая доска, панель колоды (DE-029, DE-030)
run-combat-demo.ps1 -Api http://localhost:3000/graphql -ArtPreview -FullHd -ArtPreviewBoardId <board> -ArtPreviewHeroesV2
  -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf
  -RequireGameOver -RunSeconds 480 -JoinerAttack -HostScheme -ClientExtraArgs '[-ConceptPaste+]-S08MovePlates+-S09SchemeQuiet=3.5'
python tools/s08/cue_contract/cue_contract.py check-trace <trace> --min-ms-cue 1 [--min-combat 1 --min-death 1]
```

`<board>`: Marmoreal original `c121b47f8d6eb28daccb76d05`, Sarpedon original `c7fa64a26c29a0835f2383e63`.

## Прогоны и гейты

| Прогон | Итог скрипта | `check-trace` | Ключевые строки трассы |
|---|---|---|---|
| [phase2 Marmoreal](phase2/marmoreal/run-20261005-172845/) | `pass: true` ×2, `DEMO_EXIT=0` | PASS ×2, `ms_cue 3` | `ARTLOOK art=1 source=default heroes=v2`, `concept-paste status=ok`, `HUD-TRACK chosen=maneuver`, `HUD-SLOT show seq=3 ribbon=boosted owner=opp card="Hiss and Slither" … min=1000` |
| [phase2 Sarpedon](phase2/sarpedon/run-20261005-173056/) | `pass: true` ×2, `DEMO_EXIT=0` | PASS ×2 | `concept-scene status=ok mode=lit3d`, `heroesV2 summary fighters=6 mapped=6 v2=6`, `MS-ANIM settings … hop=0.000 lean=10.0`, буст соперника «Gaze of Stone» |
| [combat Marmoreal №1](demo/marmoreal/combat-20261005-173307/) | опубликован; FINISHED, seq 40, Medusa (хост), ход 7, 0:18 | PASS ×2: `combat_totals` 3933, `death_sets 1` | герой погиб от эффекта вне боя (`CUE death … staged=0`), поэтому `hit_to_screen` пуст; экран через 2666 мс после GAME_OVER |
| [combat Marmoreal №2](demo/marmoreal/combat-20261005-173556/) | опубликован; FINISHED, seq 92, Medusa (хост), ход 17, 0:47 | PASS ×2: `combat_totals` 3933, `hit_to_screen` 3168 / 3167 | `DECKLIST loaded … lists=2`, панель колоды открыта и закрыта (`why=input:turn|defend|choice`), тост лимита руки, `HUD-SLOT effect … release=time … chain=2/4` |
| [combat Sarpedon](demo/sarpedon/combat-20261005-173408/) | опубликован; FINISHED, seq 95, Medusa (хост), ход 17, 0:43 | PASS ×2: `combat_totals` 3933, `hit_to_screen` 3167 | `concept-scene status=ok mode=lit3d`, `DECKLIST loaded … lists=2`, панель колоды, тост лимита руки |

Гейты `run-combat-demo` на всех трёх партиях:
- `heroes v2 … figures=6 idle=6` у обоих клиентов;
- `render fingerprint … offReference=0`, preset High;
- `GAME_OVER gate ok: row FINISHED`, результат на обоих местах.

Целостность трасс: `SNAPSHOT applied` = `HANDLE_APPLIED` = `MODE` на каждой трассе: 62 / 54 (№1), 148 / 127 (№2),
142 / 142 (Sarpedon).

Повторная партия Marmoreal (№2) снята на той же упаковке. Причина: партия №1 кончилась на ходу 7. Автоклиент открыл
панель колоды, но окно защиты или конец партии закрывали её через 66–200 мс, раньше кадра. Тост лимита руки за партию не выпал.
Обе партии опубликованы: №1 показывает экран результата при смерти вне боя.

Темп (01: D-DE-01, D-DE-03, F-01, F-09):
- бой с текстом и 0 сработавших строк — 3933 мс во всех полных постановках;
- удар → экран результата — 3167–3168 мс;
- ход — 280 мс на ребро (1 шаг 280, 2 — 560, 3 — 840), 6–7 шагов = потолок 1400.

FPS: кап 30.
- phase2: 84 из 92 окон `PERF window` — не ниже 29,9 FPS, минимум 27,5.
- Партии: 32 из 73 окон — не ниже 29,9, минимум 17,7. Все 41 провал приходятся на окна, где за ≤ 6 с был запрос или
  снимок кадра доказательств (`gameMs p95` до 223 мс в момент снимка). Провалов без снимка нет. У партий DE-031 то же:
  36 из 55 окон, все со снимком, минимум 20,5. Партии снимают 17–24 кадра на клиента, поэтому окон со снимком много.

## Кадры (просмотрены глазами до отчёта)

Все кадры сняты в 1920×1080, опубликованы JPG шириной 1600 (q88). sha256 исходных PNG — в [png-sha256.txt](png-sha256.txt),
в `manifest.json` и в строках `SHOT captured` трасс. Трассы `*.trace.log` переименованы в `*.trace.txt`, байты не менялись.

Общее для всех кадров:
- Доска — настоящая карта.
- Marmoreal — нарисованный задник: дворец, колонны, фонари, сакура.
- Sarpedon — остров `lit3d`: корабль, пушки, огни, причал.
- Шесть фигур v2. На итоговой доске их пять: павший King Arthur растворён.

| Что проверить | Marmoreal | Sarpedon |
|---|---|---|
| DE-029 экран результата: «VICTORY / DEFEAT», «MEDUSA WINS», «King Arthur's HP reached 0», «Turn N · m:ss», две стороны, силуэт проигравшего | [хост, №1, «Turn 7 · 0:18»](demo/marmoreal/combat-20261005-173307/host/s09-result-screen.jpg), [джойнер, №2, «Turn 17 · 0:47»](demo/marmoreal/combat-20261005-173556/joiner/s09-result-screen.jpg) | [джойнер, «Turn 17 · 0:43»](demo/sarpedon/combat-20261005-173408/joiner/s09-result-screen.jpg) |
| DE-029 итоговая доска: «FINAL BOARD · …», портрет 0/18 | [джойнер, №1](demo/marmoreal/combat-20261005-173307/joiner/s09-result-board.jpg), [хост, №2](demo/marmoreal/combat-20261005-173556/host/s09-result-board.jpg) | [хост](demo/sarpedon/combat-20261005-173408/host/s09-result-board.jpg) |
| DE-030 своя колода: «IN HAND» / «DISCARD» / «LEFT», копии рядом, без порядка | [хост, №2](demo/marmoreal/combat-20261005-173556/host/s09-deck-own.jpg) | [хост](demo/sarpedon/combat-20261005-173408/host/s09-deck-own.jpg) |
| DE-030 колода соперника: только «DISCARD», рука — рубашками | [хост, №2](demo/marmoreal/combat-20261005-173556/host/s09-deck-opp.jpg) | [джойнер](demo/sarpedon/combat-20261005-173408/joiner/s09-deck-opp.jpg) |
| DE-024 тост лимита руки | [хост, №2](demo/marmoreal/combat-20261005-173556/host/s09-hand-limit-hint.jpg) | [джойнер](demo/sarpedon/combat-20261005-173408/joiner/s09-hand-limit-hint.jpg) |
| DE-017 черновик манёвра, DE-026 буст соперника | [хост, черновик](phase2/marmoreal/run-20261005-172845/host-maneuver-draft.jpg), [джойнер, BOOSTED](phase2/marmoreal/run-20261005-172845/phase2-board-joiner-1920x1080.jpg) | [хост, черновик](phase2/sarpedon/run-20261005-173056/host-maneuver-draft.jpg), [джойнер, BOOSTED](phase2/sarpedon/run-20261005-173056/phase2-board-joiner-1920x1080.jpg) |

Сверка чисел на кадрах колоды:
- **Marmoreal, своя колода** (Medusa). Шапка: в колоде ~21, сброс 3, рука 6. Метки «IN HAND» на строках дают в сумме 6 —
  столько же карт в руке на HUD. «DISCARD» дают 3. «LEFT» в сумме 21, всего 30 карт.
- **Marmoreal, колода соперника** (King Arthur). Рука 7 — семь рубашек. «DISCARD» дают 3 (Feint 1, Regroup 2), меток
  руки нет.
- **Sarpedon, своя колода.** Рука 2, сброс 5, «LEFT» в сумме 23.

## Приёмка задач прогона

| Задача | Вживую на упаковке `b2e5f6d3` | Статус |
|---|---|---|
| DE-029 | Экран результата и итоговая доска на обеих картах, у обоих мест; заголовок по герою-победителю; причина по HP проигравшего. Длительность «m:ss» на месте (`RESULT summary … duration=18/47/43`). Экран сам не закрывается: «VIEW BOARD» нажал автоклиент — `RESULT view mode=board … fade=250 why=auto`. Вход 500 мс (`intro=500`). Маркерная полоса на месте | принято |
| DE-030 | `DECKLIST loaded … lists=2` на всех клиентах обеих карт. Своя колода и колода соперника — на обеих картах, числа сходятся с HUD. Автозакрытие `why=input:turn`, `input:defend`, `input:choice`. Порядок колоды и карты руки соперника на кадрах не видны | принято |
| DE-031 | Одна упаковка со штампом, два клиента на двух картах, `check-trace` PASS на 10 трассах, кадры просмотрены, темп по 01 | принято (повтор G-LIVE подтверждает [../live/README.md](../live/README.md)) |

Не перепроверялось (без изменений кода с `bd109788`, данные — в [../live/README.md](../live/README.md)):
- гейты GD-036 / GD-039 (`run-duel-demo`, `run-vs-ai-demo`);
- бенч G-COST;
- ACC-022;
- автотест кликов.

## Замечания (не дефекты прогона F)

1. **Тост статуса накрывает ленту событий (MS-T-17, прогон D).** Тост «begin maneuver sent (server draws 1 card)»
   ложится поверх длинных строк ленты `MS-LOG` над рукой. Кадр: [Sarpedon, хост](demo/sarpedon/combat-20261005-173408/host/s09-deck-own.jpg) —
   строки «King Arthur: Skirmish effect: no movement» и «Medusa: Dash effect…» читаются плохо. На коротких строках
   (Marmoreal) тост стоит правее ленты и не мешает. Это вёрстка HUD, гейты не падают. Правка — в проход исправлений
   ленты (MS-T-17 / DE-022): сдвинуть тост или ограничить ширину строки ленты.
2. **Смерть вне боя во время чужой постановки (DE-019, прогон C).** Это партия Marmoreal №1, seq 37 → 40. King Arthur
   погиб от эффекта вне боя (`staged=0`, по решению прогона C — сразу, под seq снапшота). В это время ещё шла
   постановка боя seq 37. Падение и растворение шли одновременно с этой постановкой. Экран результата открылся в
   39 695 мс, а постановка закончилась в 39 928 мс. Её последние 233 мс прошли под затемнением. `check-trace` PASS,
   на кадре экрана артефактов нет. Если нужно строже, смерть `staged=0` может ждать конца очереди постановок. Это
   вопрос к DE-019, не к F.
3. **Схема хоста (`WARN: scheme not played this run`)** — предупреждение сценария, не гейт. Оно было и во всех партиях
   DE-031. Своя схема и схема соперника в слоте сняты на кадрах `s09-card-slot-own` / `s09-card-slot-opp`.
4. **Не выпало вживую** (как в DE-031): «ваш боец» (`MS-OPP yours` = 0); бой без текста.

## Процессы

- **Запускал агент:**
  - сборка игровой цели (UBT, 1 раз);
  - упаковка RunUAT (1 раз);
  - `run-phase2-demo` ×2;
  - `run-combat-demo` ×3.

  Все процессы завершились сами. Перед отчётом проверено: ни одного Unmatched, UnrealEditor, UBT или UAT не осталось,
  замок снят.
- Окно Unmatched: Digital Edition (Steam) не трогалось.
- Docker-стек был поднят до агента и оставлен как есть.
- Временные папки прогонов (`%TEMP%\s08-phase2-20261005-*`, `%TEMP%\s09-combat-20261005-173*`) оставлены на месте.
- Обёртки и логи упаковки лежат вне репозитория, в `C:/tmp/f-accept/`.
