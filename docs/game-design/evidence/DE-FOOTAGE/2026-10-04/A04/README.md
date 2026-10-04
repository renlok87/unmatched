# Прогон A04: живая приёмка G-LIVE (2026-10-04)

**Итог: пройдено.** Одна упаковка на прогон (штамп `20aafcfb`). Два клиента на Marmoreal original и на Sarpedon
original, 30 FPS на клиент. Все гейты скрипта прошли, трассы прошли `check-trace`, кадры просмотрены глазом до отчёта.
При значениях по умолчанию вид не изменился: кадры `-Bench` нового пакета отличаются от пакета до прогона (`0f2bdb9a`)
меньше, чем два свежих бенча нового пакета между собой.

- Полномочия, порядок и решения оркестратора — [IMPL-2026-10-04.md](../../../../de-footage/task/runs/IMPL-2026-10-04.md).
- Журнал прогона — [A04-2026-10-04.md](../../../../de-footage/task/runs/A04-2026-10-04.md), раздел «Живая приёмка G-LIVE».
- Гейт — [07-sprint-plan.md](../../../../de-footage/task/07-sprint-plan.md) §8, строка G-LIVE.

## Сборка и упаковка

| Шаг | Команда | Результат |
|---|---|---|
| Игровая цель | `node tools/s08/build-editor.cjs Unmatched Win64 Development -Project=… -WaitMutex -NoXGE -MaxParallelActions=6` | `Result: Succeeded`, ошибок в логе нет |
| Упаковка, один раз | `tools/s08/package-client.ps1 -SkipBuild -Log C:\tmp\a04-live\uat.log` | `UAT_EXIT=0`, предупреждений cook (`LogCook: Warning/Error`) — 0 |
| Штамп | [BuildStamp.json](BuildStamp.json) | commit `20aafcfb`, sourceHash `b6ed404f…`, 142 файла |
| Внутренний exe | sha256 staged `Unmatched/Binaries/Win64/Unmatched.exe` = `Binaries/Win64/Unmatched.exe` | `c8c41d6a…` в обоих |

Что из прогона попало в pak (по `Manifest_UFSFiles_Win64.txt`):
- DE-010: четыре клипа `PipelineCandidates/*/H2Anim/AM_*_LungeAttack` с notify `Contact`, мастер `UM/Materials/v2/M_UM_Figure_v2`;
- DE-011: 8 MIC растворения `UM/Materials/v2/Dissolve/MI_*_Dissolve` — все 8;
- DE-012: 76 новых текстур `S08/UI/IconsV3/T_IV3_*` (кольцо хода, сердце, крест, трекер DE) — все 76; `Config/S08IconMotion.json`
  (файл не новый, регенерация makefile не нужна);
- DE-013: в UE ничего не меняет.

## A/B вида по умолчанию: `-Bench` пакета до и после

`python tools/art/render/live_tune.py bench --packaged --map <map> --views K1+K2x1.6 --out …`:
- «до» — пакет `0f2bdb9a`, снят перед упаковкой;
- «после» — новый пакет, два свежих запуска (`after1`, `after2`; второй — шум бенча);
- `live_tune.py compare --a after1 --b before --noise after2` — [compare-marmoreal.json](bench/compare-marmoreal.json), [compare-sarpedon.json](bench/compare-sarpedon.json).

| Карта, вид | до / после: mean \|d\|, пикс. > 24 | после / после (шум бенча) | вне маски шума |
|---|---|---|---|
| Marmoreal K1 | 0,159 / 0 % (max 17) | 0,350 / 0,005 % | 0 %, pass |
| Marmoreal K2x1,6 | 0,143 / 0,0005 % | 0,369 / 0,007 % | 0 %, pass |
| Sarpedon K1 | 0,118 / 0,010 % | 0,286 / 0,052 % | 0 %, pass |
| Sarpedon K2x1,6 | 0,134 / 0,026 % | 0,356 / 0,112 % | 0 %, pass |

- Гейт FIDELITY (mean ≤ 0,5 и ≤ 0,05 % пикселей > 24) пройден на всех видах и вне маски шума.
- Колонка фигур Marmoreal K2x1,6: до/после 0,275 против после/после 0,634. Контуры фигур на карте разницы ×10 — это
  фаза Idle, она на уровне шума.
- Значит, `CPD_HitTint` = 0 (DE-010) и выключенный `UseDissolve` (DE-011) по умолчанию вида не меняют. Отпечаток `RENDER`
  совпадает (D3D12 SM6, Lumen, `sg.*=2`, SP 100); строка `ARTLOOK art=1 source=default heroes=v2 tray=on env=on`
  одинакова до и после.
- Листы: [Marmoreal K1](bench/marmoreal-K1-before-after-diff.jpg), [Marmoreal K2x1,6](bench/marmoreal-K2x1p6-before-after-diff.jpg),
  [Sarpedon K1](bench/sarpedon-K1-before-after-diff.jpg), [Sarpedon K2x1,6](bench/sarpedon-K2x1p6-before-after-diff.jpg)
  (до | после | разница ×10). Трассы и командные строки бенчей — `bench/*.trace.txt`, `bench/*.cmdline.txt`.

## Живой прогон двух клиентов

Обёртка `C:\tmp\a04-live\run-demo.ps1` (вне репозитория):
- берёт демо-аккаунты `S08_DEMO_*` из `C:/tmp/wt-envmaps/backend/.env` только в окружение процесса и не печатает их;
- держит замок `C:/tmp/unmatched-gpu.lock` (`owner=A04-LIVE`) на время прогона;
- вызывает `tools/s08/run-phase2-demo.ps1`.

```
run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ArtPreviewBoardId <board> -EvidenceDir <dir>
  -HostManeuver -RequireRenderReference -RequireShotCaptured -ClientPerf
  -ClientExtraArgs '-ConceptPaste+-S08ManeuverPlan=boost3'   # Marmoreal
  -ClientExtraArgs '-S08ManeuverPlan=boost3'                 # Sarpedon
```

- `-ClientFps 30` (по умолчанию) — на каждом клиенте, оба offscreen, пресет High.
- Marmoreal снят с `-ConceptPaste` по IMPL п. 3: это нарисованный задник, правило AGENTS.md «Board scenes and heroes».
  ENV-U16 (задник по умолчанию) открыт, в прогон не входит.
- `-S08ManeuverPlan=boost3`: на Marmoreal Medusa в начале зажата своими Harpy, и драйвер одного шага героя манёвр не
  начинает (см. «Замечания»). План двигает приспешников, и гейт манёвра становится проверяемым.
- Бэкенд — основной стек `:3000`, `/health` = database up, redis up.

### Marmoreal · original map — [demo/marmoreal/run-20261004-231953](demo/marmoreal/run-20261004-231953/)

| Проверка | Хост | Джойнер |
|---|---|---|
| Доска | `c121b47f8d6eb28daccb76d05`, профиль `marmoreal-original`, 7×6, 31 клетка / 42 связи, свет `marmoreal-night` | то же |
| `ARTLOOK` | `art=1 source=default heroes=v2 tray=on env=on review=1 legacyRender=0 aliases=-` | то же |
| Фигуры | `heroesV2 summary fighters=6 mapped=6 v2=6` | то же |
| Задник | `envlayout variant=concept … status=ok`, `propsRemoved=64`: 3D-окружение P5c снято, нарисованный задник | то же |
| Манёвр | `MANEUVER begin seq=2 (apply)`, `MANEUVER-CONFIRM moves=3 boost=card`, 3 × `MS-CUE move` | 3 × `MS-CUE move`, 3 × `CUE move` |
| `check-trace --min-ms-cue 3` | `CUE_TRACE PASS`, ms_cue 3 (trail 3) | `CUE_TRACE PASS`, ms_cue 3 |
| Гейты скрипта | все: пиксельный арт-гейт, шесть центров фигур в кадре, `SHOT captured`, `RENDER reference=1`, сходимость после WS drop | — |
| FPS | 29,93 (afterWarmup), gpuMs 2,19 | 29,93, gpuMs 2,15 |
| Уборка | игра этого прогона снята, `ABORTED (verified)` | — |

### Sarpedon · original map — [demo/sarpedon/run-20261004-232442](demo/sarpedon/run-20261004-232442/)

| Проверка | Хост | Джойнер |
|---|---|---|
| Доска | `c7fa64a26c29a0835f2383e63`, профиль `sarpedon-original`, 9×6, 38 клеток / 61 связь, свет `sarpedon-night` | то же |
| `ARTLOOK` | `art=1 source=default heroes=v2 tray=on env=on review=1 legacyRender=0 aliases=-` | то же |
| Фигуры | `heroesV2 summary fighters=6 mapped=6 v2=6` | то же |
| Задник | `concept-paste mode=on … reason=default`, `concept-scene status=ok mode=lit3d`, анимации `flickers=5 sways=1 winds=21/21` | то же |
| Манёвр | `MANEUVER begin seq=2 (apply)`, 3 × `MS-CUE move` (герой S20>S10 и два приспешника) | 3 × `MS-CUE move` |
| `check-trace --min-ms-cue 3` | `CUE_TRACE PASS` | `CUE_TRACE PASS` |
| Гейты скрипта | все прошли | — |
| Уборка | `ABORTED (verified)` | — |

### Кадры (просмотрены глазом до отчёта)

- **Marmoreal** — [хост](demo/marmoreal/run-20261004-231953/phase2-board-host-1920x1080.png),
  [джойнер](demo/marmoreal/run-20261004-231953/phase2-board-joiner-1920x1080.png),
  [фигуры хоста ×2](demo/marmoreal-host-figures-2x.jpg).
  - Настоящая карта Marmoreal на подносе.
  - Вокруг — нарисованный задник из концепта: лестница дворца, колонны, фонари, сакура. 3D-дворца P5c нет.
  - Все шесть фигур — v2: Medusa в золоте, три крылатые Harpy, Merlin в синей мантии с посохом, King Arthur в
    красном плаще.
  - Красной заливки удара нет, фигуры не растворяются и не прозрачны: так и должно быть по умолчанию.
- **Sarpedon** — [хост](demo/sarpedon/run-20261004-232442/phase2-board-host-1920x1080.png),
  [джойнер](demo/sarpedon/run-20261004-232442/phase2-board-joiner-1920x1080.png),
  [фигуры хоста ×2](demo/sarpedon-host-figures-2x.jpg).
  - Настоящая карта Sarpedon.
  - Вокруг — `lit3d` путь 1: остров под концептом, корабль с пушками, костры, фонари, берег.
  - Шесть фигур v2. Medusa уже после манёвра на S10, приспешники переставлены.
- На кадрах нет ничего, что включил бы прогон A04: глифы DE-012 — только кандидаты галереи, звуков нет (DE-013 — список).
  Видимых изменений прогон по умолчанию не даёт, и это совпадает с приёмкой задач.

## Приёмка задач прогона

| Задача | Что проверено в пакете | Статус |
|---|---|---|
| DE-010 | Notify-клипы и мастер v2.2 в pak; при `CPD_HitTint` = 0 вид не изменился (A/B бенча, кадры демо) | **принято** (G-LIVE, G-ART-TECH K1). Вид заливки — на лист A/B DE-028 |
| DE-011 | 8 MIC растворения в pak, мастер v2.3; по умолчанию шейдер прежний, вид не изменился | **принято** (G-LIVE). G-COST не мерялся, см. «Решения» |
| DE-012 | 76 текстур кандидатов в pak, `S08IconMotion.json` в pak; HUD их не показывает, принятые значки прежние | **принято технически**; **G-ART ждёт пользователя** |
| DE-013 | В UE и упаковке ничего | не применимо к G-LIVE; **G-ART (на слух) ждёт пользователя** |

## Решения агента приёмки

1. **A/B бенчем вместо старого эталона K1.** Эталоны `C:/tmp/envmaps-research/lightcheck/*` сняты на прежних сборках.
   С тех пор менялся вид Marmoreal по умолчанию (P5c, `0f2bdb9a`), а эталон lightcheck и так дрейфует (PLAN-STATUS,
   ART-TUNER). Чистое сравнение «до/после прогона» даёт бенч пакета
   `0f2bdb9a`, снятый перед упаковкой, против нового пакета, плюс второй бенч нового пакета как маска шума. Между
   `0f2bdb9a` и стартом прогона `2976185d` в `unreal/` только документ (`5da37b44`).
2. **G-COST (`render_bench.py`) не запускался.** Причины:
   - пермутация по умолчанию та же, что до прогона (PS 710 инструкций), а кадры совпадают на уровне шума;
   - ни одна фигура не берёт MIC растворения до DE-019;
   - на машине работала купленная игра пользователя (Unmatched Digital Edition, Steam) — она грузит GPU, и замеры
     стоимости были бы нечестными.

   Стоимость кадра смерти мерить в прогоне C после DE-019, на тихой машине.
3. **Стек.** Основной `docker compose` (postgres, redis, backend :3000) упал за ~6 минут до старта (exit 255) и был поднят
   заново (`docker compose up -d`). Агент оставил его запущенным: до падения он работал, и следующие прогоны (B, C) его
   ждут.

## Замечания (не дефекты прогона A04)

1. **Гонка в гейте манёвра `run-phase2-demo.ps1`** (первый прогон Sarpedon).
   - Снимок `seq=2` пришёл по WS раньше ответа HTTP `beginManeuver`: `MS-NET gate released by snapshot op=begin seq=2
     (before the HTTP answer)`, затем `MS-NET late-reply op=begin ok=1 settled=snapshot`.
   - В такой ветке строка `MANEUVER begin seq=` не пишется. Манёвр при этом прошёл полностью (`MANEUVER-CONFIRM moves=3`,
     3 × `MS-CUE move`), а скрипт упал на `host maneuver trace missing 'MANEUVER begin seq='`.
   - Повтор прошёл. Гейт стоит принимать и `MS-NET late-reply op=begin ok=1`. Это задача подбора хода, не A04.
2. **`-HostManeuver` без плана на Marmoreal не стартует.**
   - Medusa в начале на M13 зажата своими Harpy. `AutoManeuverTarget` не находит шаг, и драйвер тихо выходит: нет ни
     строки `MANEUVER`, ни причины в трассе.
   - С `-S08ManeuverPlan=boost3` всё работает. Стоит писать строку причины, как это уже делает ветка плана.
3. На Sarpedon у левого края кадра (x ≈ 0, y ≈ 930) есть белое пятно. Оно есть и в бенче пакета `0f2bdb9a`, то есть
   появилось раньше прогона: окружение lit3d, не A04.
4. У джойнера `PERF summary scope=artHud frames=0`. Окно artHud, видимо, открывается только у хоста (выбор своего героя).
   Это наблюдение по `-ClientPerf`, не гейт.

## Процессы

- Агент запускал клиенты `-Bench` (по одному, под замком `live_tune`) и пары клиентов демо. Все завершились сами, замок
  снят.
- Окно Unmatched Digital Edition (Steam, PID 17824) не трогалось.
- Room code в опубликованных трассах заменён на `<redacted>` самим скриптом. `*.log` переименованы в `*.txt`, потому что
  `*.log` в gitignore; байты не менялись.
