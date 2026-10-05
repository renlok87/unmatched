# Прогон G (S12/S13): живая приёмка G-LIVE агентом приёмки (2026-10-05)

**Итог: пройдено после одной правки гейта.** Одна упаковка `f4d77d98`, пять живых прогонов по два клиента на
Marmoreal original и Sarpedon original.
- Звук точек синхронизации DE-032 работает вживую на обеих картах. Каждая точка пишет строку `CUE sound … result=fallback`,
  потому что ассетов пока нет (IMPL п. 4). Ошибок нет. Начало хода соперника беззвучно (`reason=opponent`). Громкость
  меняется без перезапуска (`applied=change`), и следующий звук идёт с новым `gain`.
- `check-trace --min-sound 1` дал PASS на 9 трассах из 10. Десятая — трасса джойнера в прогоне ui: там 0 звуков, это
  ожидаемо (см. «Прогоны»).
- Один дефект в коде прогона G: гейт AU6 ложно краснел на кадре, который остановил снимок доказательств. Исправлен в
  `cue_contract.py` (см. «Дефекты»).
- Кадры просмотрены глазами до отчёта:
  - настоящая карта;
  - задник по AGENTS.md;
  - шесть фигур v2;
  - строка `ARTLOOK … heroes=v2` на всех 10 трассах.

Ссылки:
- полномочия — [IMPL-2026-10-04.md](../../../../de-footage/task/runs/IMPL-2026-10-04.md) п. 4 и 6;
- журнал — [G-2026-10-04.md](../../../../de-footage/task/runs/G-2026-10-04.md), раздел «Живая приёмка G-LIVE»;
- гейт — [07-sprint-plan.md](../../../../de-footage/task/07-sprint-plan.md) §8 G-LIVE;
- формат строк и гейт AU — [CUE-DISPATCHER.md](../../../../../unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md) §3.2, §5, §6.

## Упаковка

- HEAD `f4d77d98`: DE-032 `07f29bae` + документы DE-033.
- Сборка игровой цели `Unmatched Win64 Development`: `Result: Succeeded`, цель уже была собрана исполнителем DE-032.
- `tools/s08/package-client.ps1 -SkipBuild`: `UAT_EXIT=0`, `BUILD SUCCESSFUL`, cook `0 error(s), 0 warning(s)`.
- Штамп — [BuildStamp.json](BuildStamp.json): commit `f4d77d98`, sourceHash `fb61f834…`, 196 файлов. Все прогоны ниже
  сняты на этой одной упаковке.
- Правка гейта (`cue_contract.py`, Python) клиент не меняет, поэтому повторная упаковка не нужна.

## Окружение

- Основной стек `:3000` (unmatched-backend, -postgres, -redis) был поднят до агента. `/health`: database up, redis up.
  Стек оставлен как есть.
- Демо-аккаунты передавались только в окружение процесса, через обёртку `C:/tmp/g-accept/env-s08.cjs` (вне репозитория).
  Учётные данные в трассах и выводе проверены поиском: их нет. Код комнаты в трассах — `<redacted>`.
- GPU: каждый прогон шёл под замком `C:/tmp/unmatched-gpu.lock` с владельцем `G-ACCEPT`. Клиенты offscreen, по 30 FPS на
  клиент, пресет High.
- Marmoreal снят с `-ConceptPaste` (IMPL п. 3: ENV-U16 открыт) — нарисованный задник. Sarpedon — `lit3d`, путь 1.
- Проверка громкости меняла сохранённые настройки упакованного клиента
  (`Saved/StagedBuilds/…/GameUserSettings.ini`, секция `S08UserSettings`). После каждого прогона агент удалял эту секцию
  (`strip-settings.py`), так что упаковка осталась с громкостями по умолчанию.

## Команды

```
# партия до GAME_OVER: удар, шаг, перезвон, стинг результата (DE-032)
run-combat-demo.ps1 -Api http://localhost:3000/graphql -ArtPreview -FullHd -ArtPreviewBoardId <board> -ArtPreviewHeroesV2
  -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf
  -RequireGameOver -RunSeconds 480 -JoinerAttack -HostScheme -ClientExtraArgs '[-ConceptPaste+]-S08MovePlates+-S09SchemeQuiet=3.5'
# манёвр хоста + смена громкости без перезапуска (s08.Settings на первом кадре, после applied=start)
run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ArtPreviewBoardId <board> -ClientFps 30 -ClientRenderPreset High
  -RequireRenderReference -RequireShotCaptured -ClientPerf -HostManeuver
  -ClientExtraArgs '-ExecCmds=t.MaxFPS 30, s08.Settings master=60 ambience=40+[-ConceptPaste+]-S08MovePlates+-S08ManeuverPlan=boost3+-S08ManeuverDraftHold=2.5+-S08ManeuverDraftShot=<png>'
# точка ui: хост нажимает END TURN флагом (HUD-PRESS → CUE-003/004), без манёвра
run-phase2-demo.ps1 … -ArtPreviewBoardId c121b47f8d6eb28daccb76d05 -ArtPreviewInputPlan hudendturn -ClientExtraArgs '-ConceptPaste+-S08MovePlates'
python tools/s08/cue_contract/cue_contract.py check-trace <trace> --min-sound 1 [--min-combat 1 --min-death 1 --min-ms-cue 1]
```

`<board>`: Marmoreal original `c121b47f8d6eb28daccb76d05`, Sarpedon original `c7fa64a26c29a0835f2383e63`.

Свой `-ExecCmds` идёт в `ClientExtraArgs` раньше, чем `-ExecCmds="t.MaxFPS 30"` сценария, и UE берёт первый. Поэтому в
нём повторён `t.MaxFPS 30`, и кап 30 FPS сохраняется.

## Прогоны и гейты

| Прогон | Итог скрипта | `check-trace --min-sound 1` | Звук (хост / джойнер) |
|---|---|---|---|
| [combat Marmoreal](demo/marmoreal/combat-20261005-181651/) | опубликован; FINISHED, seq 51, Medusa (хост), ход 9, 0:27 | PASS ×2 (`--min-combat 1 --min-death 1 --min-ms-cue 1`): `combat_totals` 3933, `hit_to_screen` 3167 | 28 / 26 строк: hit 10 / 11, step 9 / 6, turn 8 / 8 (по 4 беззвучных `opp`), result 1 / 1; `sound_late_shot` 1 / 0 |
| [combat Sarpedon](demo/sarpedon/combat-20261005-181804/) | опубликован; FINISHED, seq 42, Medusa (хост), ход 7, 0:17 | PASS ×2 (те же ключи): `combat_totals` 3933, `hit_to_screen` 3167 | 17 / 14: hit 5 / 5, step 5 / 2, turn 6 / 6, result 1 / 1 |
| [phase2 Marmoreal](phase2/marmoreal/run-20261005-181906/) | `DEMO_EXIT=0` | PASS ×2 (`--min-ms-cue 1`) | step 9 / 9 (манёвр boost3 по рёбрам, `edge=k/7`); хост: `applied=start` 100/60 → `applied=change` 60/40, затем все шаги с `gain=0.60`; `sound_late_shot` 1 / 0 |
| [phase2 Sarpedon](phase2/sarpedon/run-20261005-182117/) | `DEMO_EXIT=0` | PASS ×2 | step 9 / 9; на хосте тот же `applied=change` и `gain=0.60`; `sound_late_shot` 1 / 0 |
| [phase2 ui Marmoreal](phase2-ui/marmoreal/run-20261005-182703/) | `DEMO_EXIT=0` | хост PASS; у джойнера `AU10 0 < 1` (без `--min-sound` — PASS) | хост: `HUD-PRESS id=hud.end.turn result=refused` и `CUE sound id=CUE-004 point=ui … result=fallback` в том же кадре (t=31508). У джойнера в этом прогоне не было ни одного события со звуком |

Гейты `run-combat-demo` на обеих партиях:
- `heroes v2 … figures=6 idle=6` у обоих клиентов;
- `render fingerprint … offReference=0`, пресет High;
- `GAME_OVER gate ok: row FINISHED`, результат на обоих местах.

Число клипов HitReact на клиенте (10 / 11 и 5 / 5) совпадает с числом строк `point=hit`: на каждый HitReact есть ровно
один звук удара.

Что видно в трассах по точкам DE-032 (02 SD-51, 01 F-07):
- **hit (CUE-011).**
  - Удар постановки: `due` = `t` этапа `contact` своего seq. Пример — Marmoreal seq 51: `CUE combat … stage=contact
    t=48405` → `CUE sound id=CUE-011 … t=48405 … due=48405`.
  - Удар без постановки (каскад, эффект) звучит в кадр своего HitReact без `due`.
- **step (CUE-007).** Один звук на ребро, все k из n. У манёвра boost3 — `edge=1/7…7/7` с шагом 200 мс.
- **turn (CUE-015).**
  - Свой ход — `result=fallback turn=own`.
  - Ход соперника — `result=silent turn=opp reason=opponent`.
  - Каждой строке `HUD-TURN … initial=0` соответствует строка перезвона (AU3).
- **result (CUE-016).** Один стинг на `RESULT screen`, `event_t` = `t` экрана (AU7), класс `Music`.
- **ui (CUE-003/004).** Звучит в кадре отклика `HUD-PRESS`. Автоклиенты партий ходят через API, а не через отпускание
  кнопки, поэтому в партиях `ui = 0`. Точку подтверждает отдельный прогон ui.
- **Громкости.**
  - `CUE audio … applied=start` стоит до первого звука.
  - `s08.Settings master=60 ambience=40` дал `applied=change` с `gain_master=0.60 gain_ambience=0.24` (AU8).
  - Строка `SETTINGS saved … audioApplied=1`.
  - Джойнер phase2 стартовал уже с сохранёнными 60/40 (хост сохранил раньше, папка Saved общая), поэтому у него только
    `applied=start` 60/40.
- `sound_dt_max` = 0 на всех трассах: звук играет в кадре визуального события (AU2).
- `GATE AU*` нет ни на одной трассе.

FPS: кап 30. 142 из 176 окон `PERF window` — не ниже 29,9, минимум 19,9. Провалы — в окнах со снимками доказательств,
как в прогонах C–F.

## Дефекты

1. **AU6 / AU5 краснели на кадре, остановленном снимком доказательств (DE-032, гейт `check-trace`). Исправлено.**
   - Что было:
     - Marmoreal, combat, хост, строка 997: `CUE sound id=CUE-007 … seq=7 t=24834 … edge=1/2 due=24680`, то есть
       t − due = 154 мс при допуске 100.
     - Phase2, хосты обеих карт: `edge=2/7`, t − due = 175 мс.
   - Причина: между предыдущей строкой (t=24588) и этим звуком стоит `SHOT captured file=s09-opponent-move.png`.
     Синхронный снимок 1920×1080 держит игровой поток примерно 250 мс. Звук при этом в кадре своего визуального
     события (`dt=0`): фигура и звук опоздали вместе, логика DE-032 не ошибается.
   - Правка: `tools/s08/cue_contract/cue_contract.py`, функция `_shot_stall`.
     - Опоздание шага или удара больше допуска не считается ошибкой, если выполнены два условия:
       - между строкой с t ≤ due + 100 и первой строкой с t после неё стоит `SHOT captured`;
       - звук прозвучал не позже 100 мс от этой строки.
     - Такое опоздание идёт в счётчик `sound_late_shot`.
     - Без снимка, при снимке задолго до due и при звуке позже первого кадра после снимка AU5/AU6 краснеют, как раньше.
   - Тест `test_late_frame_after_evidence_shot_is_counted_not_failed`; unittest 48 OK; `validate-table` и
     `run-fixtures` PASS.
   - Трассы прогона C (до DE-032) по-прежнему проходят.

## Кадры (просмотрены глазами до отчёта)

Все кадры сняты в 1920×1080 и опубликованы JPG шириной 1600 (q88). sha256 исходных PNG — в
[png-sha256.txt](png-sha256.txt), в `manifest.json` и в строках `SHOT captured` трасс. Трассы `*.trace.log`
переименованы в `*.trace.txt`, байты не менялись.

Общее для всех кадров:
- Доска — настоящая карта.
- Marmoreal — нарисованный задник: дворец, колонны, фонари, сакура.
- Sarpedon — остров `lit3d`: корабль, пушки, огни, причал, вода.
- Шесть фигур v2 (`heroesV2 summary fighters=6 mapped=6 v2=6` на всех трассах). На итоговой доске их пять: павший
  King Arthur растворён.

| Что | Marmoreal | Sarpedon |
|---|---|---|
| Доска в ходе партии, 6 фигур v2 | [хост, ход соперника](demo/marmoreal/combat-20261005-181651/host/s09-opponent-move.jpg) | [хост, колода соперника и итог боя](demo/sarpedon/combat-20261005-181804/host/s09-opponent-move.jpg) |
| Экран результата (кадр стинга CUE-016) | [хост, «Turn 9 · 0:27»](demo/marmoreal/combat-20261005-181651/host/s09-result-screen.jpg) | [хост, «Turn 7 · 0:17»](demo/sarpedon/combat-20261005-181804/host/s09-result-screen.jpg) |
| Удар (кадр звука CUE-011) | [джойнер, урон](demo/marmoreal/combat-20261005-181651/joiner/s09-damage-combat.jpg) | [джойнер, урон](demo/sarpedon/combat-20261005-181804/joiner/s09-damage-combat.jpg) |
| Свой ход (кадр перезвона CUE-015) | [хост, баннер](demo/marmoreal/combat-20261005-181651/host/s09-turn-banner.jpg) | [хост, баннер](demo/sarpedon/combat-20261005-181804/host/s09-turn-banner.jpg) |
| Манёвр boost3 (шаги CUE-007), смена громкости | [хост, доска](phase2/marmoreal/run-20261005-181906/phase2-board-host-1920x1080.jpg), [черновик](phase2/drafts/phase2-draft-marmoreal.jpg) | [джойнер, BOOSTED](phase2/sarpedon/run-20261005-182117/phase2-board-joiner-1920x1080.jpg), [черновик](phase2/drafts/phase2-draft-sarpedon.jpg) |
| Прогон ui | [хост](phase2-ui/marmoreal/run-20261005-182703/phase2-board-host-1920x1080.jpg) | — |

Звук на кадре не виден, поэтому для DE-032 кадр доказывает только визуальное событие. Сам звук доказывают строки трассы
в том же кадре (`event_t` = `t` визуального события, `dt=0`).

## Приёмка задач прогона

| Задача | Вживую на упаковке `f4d77d98` | Статус |
|---|---|---|
| DE-032 | Пять точек на обеих картах (ui — в отдельном прогоне на Marmoreal). У каждой точки строка в кадре события, фолбэк без ассетов без ошибок. Беззвучное начало хода соперника. Удар в кадре `contact`. Один звук на ребро. Стинг с экраном. Общая громкость и громкость окружения меняются без перезапуска, следующий звук идёт с новым `gain`. Гейт AU1–AU10 PASS после правки AU5/AU6 | принято (в объёме IMPL п. 4: слышимый звук — после выбора на слух DE-013 и импорта ассетов) |
| DE-033 | Живой части нет: раздел протокола GD-050, код не менялся. Строки трассы, на которые опирается протокол, вживую на месте: `CUE combat stage=read/pause/end` (`stage=effect` в этих партиях не выпал: сработавших строк эффекта не было), `CUE death`, `RESULT screen`, `HUD-PRESS`, `CUE sound point=ui`, `check-trace --min-combat`. Темп совпадает с 2.1 протокола: бой 3933 мс, удар → экран 3167 мс | принято (раздел протокола; приёмка самой строки — в сессиях GD-050) |

## Замечания (не дефекты прогона G)

1. **`-ArtPreviewInputPlan` вместе с `-HostManeuver` не дают манёвра.** Первая попытка прогона ui включала оба флага.
   Скрипт упал на `host maneuver trace missing 'CUE move'`: автоманёвр не начался. Вероятная причина — флаговый выбор
   своего героя открывает режим команды (`CommandUi.Mode != None`), и `RunAutoManeuver` выходит. Это инструмент
   демо-сценария, а не прогон G. Прогон ui повторён без `-HostManeuver`; попытка не опубликована.
2. **Звук ui в партиях не проверяется.** Автоклиенты `run-combat-demo` действуют через API, а не через отпускание
   кнопки, поэтому `point=ui` в партиях всегда 0. Если нужен ui-звук в партии — добавить шаг `hudendturn` в план
   автоклиента. Это не входит в G.
3. **Кадр, остановленный снимком, бывает и у визуальных гейтов** (DS4/DS5, падения FPS — прогоны C–F). Гейт звука
   теперь учитывает это явно (`sound_late_shot`). У гейтов DS такого счётчика нет; пока они не краснели.

## Процессы

- **Запускал агент:**
  - сборка игровой цели (UBT, 1 раз, без изменений);
  - упаковка RunUAT (1 раз);
  - `run-combat-demo` ×2;
  - `run-phase2-demo` ×4 (одна попытка ui не прошла гейт сценария).

  Все процессы завершились сами. Перед отчётом проверено: ни одного Unmatched, UnrealEditor, UBT, UAT или dotnet не
  осталось, замок GPU снят. Комнаты этих прогонов — FINISHED или ABORTED (очистка сценария).
- Окно Unmatched: Digital Edition (Steam) не трогалось.
- Docker-стек был поднят до агента и оставлен как есть.
- Временные папки прогонов (`%TEMP%\s08-phase2-20261005-18*`, `%TEMP%\s09-combat-20261005-18*`) оставлены на месте.
- Обёртки и логи упаковки лежат вне репозитория, в `C:/tmp/g-accept/`.
