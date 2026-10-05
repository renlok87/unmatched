# Прогон D (S11d — движение и соперник): живая приёмка G-LIVE (2026-10-05)

**Итог: пройдено после двух исправлений.**
- MS-T-16, DE-021 и MS-T-17 приняты в той части, которую воспроизводит живая партия двух клиентов.
- DE-022 принят частично: плашка «ваш боец» вживую не выпала ни разу.
- Что не воспроизводится вживую, перечислено в таблице приёмки ниже.

Как проверяли:
- упакованная сборка, два клиента, 30 FPS на клиент, оба offscreen;
- две партии до GAME_OVER (`run-combat-demo`, Marmoreal original и Sarpedon original);
- два коротких прогона с манёвром хоста через черновик (`run-phase2-demo -HostManeuver`) — это MS-AT-32 (а);
- `check-trace` прошёл на всех восьми трассах;
- все кадры просмотрены глазом до отчёта.

Ссылки:
- полномочия и решения оркестратора — [IMPL-2026-10-04.md](../../../../de-footage/task/runs/IMPL-2026-10-04.md);
- журнал прогона — [D-2026-10-04.md](../../../../de-footage/task/runs/D-2026-10-04.md), раздел «Живая приёмка G-LIVE»;
- гейт — [07-sprint-plan.md](../../../../de-footage/task/07-sprint-plan.md) §8, G-LIVE; кадры клиента-соперника — MS-AT-30 и MS-AT-32 в [06-test-and-acceptance.md](../../../../move-selection/06-test-and-acceptance.md).

## Коммиты агента приёмки

| Коммит | Что |
|---|---|
| `21db5c61` | **Кадры клиента-соперника.** Автоклиент S09 снимает два кадра для MS-AT-30. `s09-opponent-move.png` — первый ход соперника в середине первого плана (MS-T-16, DE-021). `s09-opponent-last-move.png` — через 0,5 с после того, как показана подсветка этого хода, вместе со строкой ленты (MS-T-17, DE-022). `run-combat-demo.ps1` публикует их, если клиент их записал. Гейты не менялись |
| `077e7b43` | **Исправление MS-T-16.** `FigureScreenRect` строил рамку фигуры по клетке снапшота, то есть по месту назначения. Поэтому плашка, экранные метки и значок фигуры прыгали в конец пути сразу, а фигура ещё ехала до 2,4 с. Теперь, пока актёр движется, рамка идёт за ним. **Исправление гонки кадров демо:** кадр окна защиты затирал кадр, запрошенный в том же кадре раньше. Так `s09-damage-number.png` джойнера не записался, и Marmoreal упал на `-RequireShotCaptured`. Теперь защита ждёт один кадр |
| `81181469` | **Исправление трассы MS-T-16.** Строка `MS-ANIM settings …` (hop, lean, turn, settle, ease) писалась в `BeginPlay` до `FS08Trace::Open`. Поэтому её не было ни в одной трассе упакованного клиента. Теперь строка ждёт в `ArtHud.PendingTrace`, как остальные загрузочные строки. Сборка и тесты зелёные. **Вживую не проверено:** исправление сделано после упаковки, строку покажет следующая упаковка (прогон E) |

Гейты после исправлений:

| Гейт | Результат |
|---|---|
| Сборка редактора и игровой цели после `077e7b43` и после `81181469` | `Result: Succeeded`, ошибок нет |
| UE `Unmatched.S08+Unmatched.S09+Unmatched.S10` после `21db5c61` и после `077e7b43` | 332/332 Success |
| UE `Unmatched.S08.MoveAnim+Unmatched.S09.MoveSel` после `81181469` | 24/24 Success |
| `cue_contract.py check-trace` на 8 трассах итогового пакета | `CUE_TRACE PASS` на всех (параметры — ниже) |

## Окружение

- **Бэкенд.** Основной стек `:3000`: postgres, redis и backend были подняты до агента и оставлены как есть. `/health` отвечает database up, redis up. В прогоне D нет серверных правок (`git diff 01edba4d..HEAD -- backend` пуст), поэтому `dist` не пересобирался.
- **Аккаунты.** Демо-аккаунты `S08_DEMO_*` из `C:/tmp/wt-envmaps/backend/.env` передавались только в окружение процесса и нигде не печатались. Обёртки лежат вне репозитория, в `C:/tmp/d-live/`.
- **GPU.** Демо шли под замком `C:/tmp/unmatched-gpu.lock`, владелец `D-LIVE`. Steam-клиент был запущен, игры из Steam не было.

## Сборка и упаковка

| Шаг | Результат |
|---|---|
| Упаковка 1 — `package-client.ps1 -SkipBuild`, штамп `21db5c61` | `UAT_EXIT=0`, `LogCook: Warning/Error` — 0. Первый прогон Marmoreal на ней нашёл оба дефекта `077e7b43` |
| Упаковка 2, вынужденная, после `077e7b43` | `UAT_EXIT=0`, cook без предупреждений. Штамп [BuildStamp.json](BuildStamp.json): commit `077e7b43`, sourceHash `028d955c…`, 172 файла. Внутренний exe `cb9978be…` совпадает с `Binaries/Win64` |

- Ещё до первой упаковки агент остановил свой же запуск UAT, чтобы добавить кадры `21db5c61`. Перед этим проверил командную строку и родителя процесса.
- Новых `Config/**.json` в прогоне D нет, поэтому регенерация makefile не нужна.

## Живые прогоны (итоговый пакет `077e7b43`)

### Партии до GAME_OVER — `run-combat-demo`

Обёртка `C:\tmp\d-live\run-combat.ps1` (как в прогоне C, владелец замка `D-LIVE`). Команда:

```
run-combat-demo.ps1 -Api http://localhost:3000/graphql -ArtPreview -FullHd -ArtPreviewBoardId <board>
  -ArtPreviewHeroesV2 -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High -RequireRenderReference
  -RequireShotCaptured -ClientPerf -RequireGameOver -RunSeconds 480 -JoinerAttack
  -ClientExtraArgs '-ConceptPaste+-S08MovePlates'    # только Marmoreal: задник (IMPL п. 3) и V-14 на доске
python tools/s08/cue_contract/cue_contract.py check-trace <trace> --min-ms-cue 1 --min-combat 1 --min-death 1
```

- Sarpedon прогнан без дополнительных флагов, то есть в виде по умолчанию.
- Подложки и V-14 видны только с `-S08MovePlates` (до MS-T-27). Поэтому на Marmoreal флаг включён, на Sarpedon подсветку подтверждают трассы.

| Проверка | Marmoreal — [combat-20261005-104451](demo/marmoreal/combat-20261005-104451/) | Sarpedon — [combat-20261005-104620](demo/sarpedon/combat-20261005-104620/) |
|---|---|---|
| Доска | `c121b47f8d6eb28daccb76d05`, `marmoreal-original`, 7×6. Сверено с записью игры | `c7fa64a26c29a0835f2383e63`, `sarpedon-original`, 9×6. Сверено с записью игры |
| `ARTLOOK` | `art=1 source=default heroes=v2 tray=on env=on review=1 legacyRender=0` на обоих клиентах | то же |
| Фигуры | `heroesV2 summary fighters=6 mapped=6 v2=6`, Idle 6/6 | то же |
| Задник | `envlayout variant=concept … status=ok`, `concept-paste status=ok`: нарисованный задник | `concept-scene status=ok mode=lit3d` (путь 1), 5 огней |
| Партия | seq 72, FINISHED, хост VICTORY. Атак джойнера 7, атак хоста 3. Сходимость seq 72/72 | seq 39, FINISHED, хост VICTORY. Атак хоста 5, атак джойнера 3. Сходимость 39/39 |
| `check-trace` | PASS на обоих: stale 0, `ms_cue` 5 / 4 (все `source=trail`), `combat_sets 10`, `death_sets 1`, `hit_to_screen [3167]` | PASS на обоих: stale 0, `ms_cue` 3 / 2 (trail), `combat_sets 8`, `death_sets 1`, `hit_to_screen [3167]` |
| FPS (`PERF summary`) | кап 30, `fps=29.88…29.93` | `fps=29.85…29.90` |

### Манёвр хоста через черновик — `run-phase2-demo` (MS-AT-32 а)

```
run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ArtPreviewBoardId <board> -EvidenceDir <dir> -ClientFps 30
  -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf -HostManeuver
  -ClientExtraArgs '[-ConceptPaste+]-S08MovePlates+-S08ManeuverPlan=boost3+-S08ManeuverDraftHold=2.5+-S08ManeuverDraftShot=<png>'
```

- Без `-S08ManeuverPlan` автоманёвр на Marmoreal не начался: у героя нет свободного шага, а повтор молчит. Этот прогон не опубликован. Поэтому, как в прогоне B, взят план `boost3`.
- По ошибке экранирования оба прогона сначала легли в папку `D/phase2$m/`. Их перенесли в `phase2/<карта>/` без изменения байтов, а указатель `latest.json` удалили.

| Проверка | Marmoreal — [run-20261005-105131](phase2/marmoreal/run-20261005-105131/) | Sarpedon — [run-20261005-105342](phase2/sarpedon/run-20261005-105342/) |
|---|---|---|
| Манёвр хоста | `MANEUVER begin seq=2` → `MANEUVER done seq=3 boost=card`: три гарпии, буст +4 (Gaze of Stone) | Medusa и две гарпии, буст +3 (Hiss and Slither) |
| Путь автора = путь анимации у соперника (100 %) | `MS-PATH` хоста `M07>M08>M09>M15>M10>M19>M16>M24`, `M20>M21`, `M01>M02` — тот же `path=` в `MS-CUE` джойнера | `S20>S10`, `S19>S20>S21>S12>S13>S16>S14`, `S18>S08` — совпадает |
| Расписание (04 §6.3) | 7 шагов → `ms=1400` (потолок), старты 0 / 980 / 1176 (перекрытие 30 %), `end=1606` | 1 / 6 / 1 шаг → 280 / 1400 / 280, старты 0 / 196 / 1176, `end=1746` |
| Взгляд соперника (джойнер) | `MS-OPP verb=maneuver` + `planning=1` на seq 2 → `verb=turn` + `planning=0` на seq 3; `MS-LAST show seq=3 mode=anim` после анимации; `MS-LOG … "Medusa: maneuver, boost +4 (Gaze of Stone): Harpies 1 M07→M24, …"` | то же; лента `"… boost +3 (Hiss and Slither): Medusa S20→S10, …"` |
| Старт хода в кадре снапшота (SD-13, DE-021) | У джойнера `SNAPSHOT applied seq=3` → `MS-CUE`×3 → `MS-ANIM play seq=3` идут подряд в одном вызове `HandleApplied`, между ними нет строк тика. Значит, старт в том же кадре | то же |
| `check-trace --min-ms-cue 1` | PASS на обоих (`ms_cue 3`, `trail 3`) | PASS на обоих |
| Остальное | `ARTLOOK … heroes=v2`, `v2=6`, задник concept-paste; 30 FPS без отказов сервера | `lit3d`, `v2=6` |

## Кадры (просмотрены глазом до отчёта)

- Все кадры сняты в 1920×1080 и сохранены в JPG шириной 1600 (q88).
- sha256 исходных PNG остались в `manifest.json` и в строках `SHOT captured` трасс.
- Файлы `*.trace.log` переименованы в `*.trace.txt`, потому что `*.log` в `.gitignore`. Байты не менялись.

**Плашка следует за фигурой — до и после `077e7b43`:** [plate-follow-before-after.jpg](plate-follow-before-after.jpg).
- Хост, Marmoreal, ход Merlin `M23>M24>M16`, кадр в середине пути (280 мс — фигура на M24).
- До исправления плашка «7/7» уже стоит над M16, а Merlin только на M24 ([исходный кадр](before-fix/marmoreal-host-opponent-move-plate-at-destination.jpg), пакет `21db5c61`).
- После исправления плашка над Merlin.

**Marmoreal** — настоящая карта Marmoreal, вокруг нарисованный задник: дворец, колонны, фонари, сакура. 3D-окружения P5c нет. Шесть фигур v2.
- [Хост, ход соперника в полёте](demo/marmoreal/combat-20261005-104451/host/s09-opponent-move.jpg). Merlin едет по пути `M23>M24>M16`, плашка «7/7» идёт за ним. У панели соперника глагол «Opponent is choosing an action». Ряд «opponent actions» виден: ход соперника. Над рукой строка «King Arthur — Opponent is choosing an action» и лента.
- [Хост, после хода](demo/marmoreal/combat-20261005-104451/host/s09-opponent-last-move.jpg). Merlin на M16. В ленте новая строка «King Arthur: maneuver: Merlin M23→M16». Трасса `MS-HL view source=last plates=3 outline=2`: V-14 нарисована, но на Marmoreal её почти не видно. Это известное замечание MS-T-13 / MS-T-27.
- [Джойнер, ход соперника в полёте](demo/marmoreal/combat-20261005-104451/joiner/s09-opponent-move.jpg): Medusa на ребре M25→M26, плашка «16/16» над ней. У джойнера уже свой ход и открыт черновик, поэтому глагола соперника нет, и это верно.
- [Джойнер, после хода](demo/marmoreal/combat-20261005-104451/joiner/s09-opponent-last-move.jpg): Medusa на M26, контур V-14 на M25 и M26 (слабый), две строки ленты.
- [Джойнер, окно защиты](demo/marmoreal/combat-20261005-104451/joiner/s09-combat-defense-open.jpg) — кадр клиента-соперника в бою. Глагол «Opponent is attacking» (пульс). Ряд «opponent actions». Строка «You are attacked: choose a defense card or No defense (N)». Лента из трёх строк.
- Просмотрены и остальные кадры: удар, «−N», окно резолва, раскрытие, результат, экран результата у обоих мест. Экран результата пока отладочного вида — это DE-029.

**Sarpedon** — настоящая карта Sarpedon, вокруг `lit3d`: остров, корабль с пушками, костры, фонари. Шесть фигур v2.
- [Хост, ход соперника в полёте](demo/sarpedon/combat-20261005-104620/host/s09-opponent-move.jpg): Merlin в пути `S25→S22`, плашка «7/7» с ним. Ход идёт во время постановки боя seq 32, поэтому карты боя у краёв ещё видны, и это верно.
- [Хост, после хода](demo/sarpedon/combat-20261005-104620/host/s09-opponent-last-move.jpg): Merlin на S22, строка ленты «King Arthur: maneuver: Merlin S25→S22».
- [Джойнер, ход соперника](demo/sarpedon/combat-20261005-104620/joiner/s09-opponent-move.jpg). Ход Medusa `S20→S35`, 140 мс. Автодрайвер джойнера за это время уже объявил атаку (seq 6 COMBAT), поэтому глагол «Opponent is defending». Строка «Waiting for the defender».
- [Phase2, джойнер после манёвра хоста](phase2/sarpedon/run-20261005-105342/phase2-board-joiner-1920x1080.jpg) и [Marmoreal](phase2/marmoreal/run-20261005-105131/phase2-board-joiner-1920x1080.jpg). Кадр снят во время анимации (лента ещё пуста). Строка «Medusa — Opponent is choosing an action», ряд «opponent actions».
- Черновики хоста: [Marmoreal](phase2/marmoreal/run-20261005-105131/host-maneuver-draft.jpg), [Sarpedon](phase2/sarpedon/run-20261005-105342/host-maneuver-draft.jpg).

## Приёмка задач прогона

| Задача | Что проверено в пакете | Статус |
|---|---|---|
| MS-T-16 | Живые `MS-ANIM play`: 14 строк на четырёх трассах партий и по одной на каждом клиенте phase2. Расписание 04 §6.3: 1 шаг — 280 мс, 2 шага — 560 мс, 7 шагов — потолок 1400 мс, перекрытие 30 %, возврат +150 мс. `snapped=0`. Фигура на кадрах в середине пути. После `077e7b43` плашка, метки и значок идут за фигурой | **принято** (G-LIVE) после исправления `077e7b43`. Трассу `MS-ANIM settings` вернул `81181469`, вживую её покажет прогон E. Не видели вживую: пропуск клавишей, PLACE, каскад урона (`CUE damage … after=move`) — их покрывают тесты `Unmatched.S08.MoveAnim.*` |
| DE-021 | Старт в кадре снапшота: `SNAPSHOT applied` → `MS-ANIM play` в одном вызове. Подскока на кадрах нет. Наклон на 10° на кадре 1080p K1 глазом не различить: фигура 40–60 px. A/B-кадры наклона и подскока сделаны бенчем DE-021 | **принято** (G-LIVE): старт и тайминги. Значения позы (hop 0, lean 10) в упакованной трассе подтвердит строка `MS-ANIM settings` после `81181469`. Лист A/B — DE-028 |
| MS-T-17 | Индикатор планирования: `MS-OPP planning=1` у соперника на время манёвра (phase2, обе карты). `MS-LAST show mode=anim` после `MS-ANIM play … end=`, `MS-LAST fade/replace` на следующем изменившемся seq. Лента `MS-LOG` со строками `ms.log.*`, в том числе с бустом и тремя ходами. Подсветка V-14 нарисована (`MS-HL view source=last outline=2`) | **принято** (G-LIVE). Замечания: V-14 почти не видна на Marmoreal (MS-T-13 / MS-T-27). Стрелка у края мигнула в кадре входа джойнера, до установки камеры (замечание 4) |
| DE-022 | Глагол соперника из состояния сервера: `turn`, `maneuver`, `attack`, `defend`, `card`, `ability` на четырёх трассах и на кадрах. Ряд «opponent actions» виден только в его ход (`MS-TRACK … oppVisible=1` на передаче хода). Строка «что делать» над рукой у обоих клиентов во всех состояниях (`MS-STATUS`, 12+ текстов). Камера стоит | **принято частично** (G-LIVE). Вживую не выпало: плашка «ваш боец» (`MS-OPP yours` — 0 в четырёх партиях, ни один эффект соперника не двигал моего бойца) — остаётся на тесте `Unmatched.S09.MoveSel.OpponentStatus` и DE-031 |

## Замечания и дефекты

1. **MS-T-16, исправлен** (`077e7b43`). Плашка, экранные метки и значок движущейся фигуры стояли в конце пути до 2,4 с.
2. **Гонка кадров демо, исправлена** (`077e7b43`). Кадр окна защиты затирал кадр «−N», запрошенный в том же кадре. Дефект был и раньше, проявился на Marmoreal в прогоне D.
3. **MS-T-16, трасса, исправлена в коде** (`81181469`, вживую не проверено). Строка `MS-ANIM settings` терялась в упакованных трассах.
4. **MS-T-17, открыто, мелкое.** Стрелка у края мигает на кадре входа или переподключения, пока камера ещё не установлена: `MS-OPP arrow=1 cell=S35 x=1872` → `arrow=0` в ту же секунду (джойнер Sarpedon, seq 3). Метки в этот момент тоже стоят не на месте. Предложение: не считать стрелку, пока камера не подогнана под доску. Задача — MS-T-27 или хвост MS-T-17.
5. **DE-022 / MS-T-17, открыто, мелкое.** Плашка тоста по центру («resolve sent», «choice sent», «attack sent») закрывает первую строку ленты над рукой, когда в руке 2–4 карты и панель узкая. Видно на кадрах окна защиты и хода соперника. Предложение: сдвинуть тост выше ленты. Задача — DE-023 (HUD у портрета) или MS-T-27.
6. **V-14 почти не видна на Marmoreal** — известное замечание MS-T-13 / MS-T-27, решает арт-приёмка.
7. **Темп автодрайвера.** Джойнер объявляет атаку через 140 мс после хода соперника, не дожидаясь конца анимации. У людей так не бывает. Это не дефект клиента.
8. Строки на английском — это MS-T-28 (StringTable).

## Процессы

- **Запускал агент:**
  - сборки UBT;
  - UE-тесты (UnrealEditor-Cmd);
  - RunUAT: первый запуск агент остановил сам, ещё два довёл до конца;
  - пары клиентов: 3 прогона `run-combat-demo` и 3 прогона `run-phase2-demo` (по одному из каждого — неудачный).

  Все процессы завершились, замок снят.
- Временную папку неудачного прогона (`%TEMP%\s09-combat-20261005-103807-*`, не опубликован) агент удалил. Чужие временные папки не трогал.
- **Docker-стек** был поднят до агента и оставлен как есть.
- **Приватность.** Коды комнат в трассах заменены скриптами на `<redacted>`. Email и паролей в трассах нет.
