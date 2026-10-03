# Live tune — подгонка без перезапуска игры

Запрос пользователя (2026-10-02): «Конечно, делай и закрепи это в основном пайплайне.» Правило — AGENTS.md, раздел
«Iteration speed». Доказательство точности и замеры — `docs/game-design/evidence/ENV-MAPS/live-tune-2026-10-02/`.

Один клиент запускается один раз со сценой `-Bench` (та же фикстура, доска, фигуры, камера) и флагом
`-ArtLiveTune=<папка>`. Дальше профиль света и раскладки перечитываются на лету, кадры снимаются командой.

| | `-Bench`, перезапуск на каждый прогон | live tune |
|---|---|---|
| запуск | 114 с на 3 вида (60 с прогрев + 3 × 14 с) | один раз, 40 с до `ready` (прогрев 30 с) |
| правка → 3 вида K1 + K2x1,6 + K2x2,5 | 114 с | **19,5–19,8 с** (`cycle`: reload 25–60 мс + кадры) |

## Команды

```
python tools/art/render/live_tune.py start --map sarpedon [--warmup 30] [--packaged] [--extra=-NoHeroLight]
#   ...правим unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json или EnvLayouts/*.layout.json...
python tools/art/render/live_tune.py cycle --views K1+K2x1.6+K2x2.5 --out C:/tmp/<run>/i1 --tag i1   # reload + shot
python tools/art/render/live_tune.py reload [--profiles <json>] [--env-dir <dir>]
python tools/art/render/live_tune.py shot --views K1 --out <dir> [--settle 6] [--live] [--clock free] [--no-fresh]
python tools/art/render/live_tune.py state
python tools/art/render/live_tune.py stop
python tools/art/render/live_tune.py bench --map cobble --views K1+K2x1.6+K2x2.5 --out <dir>   # свежий -Bench
python tools/art/render/live_tune.py compare --a <bench run> --b <live run> --noise <второй bench run>
python tools/art/render/live_tune.py --check        # самопроверка на фейковом клиенте (без UE)
```

- `start` ждёт свободный `C:/tmp/unmatched-gpu.lock` и держит его всю сессию: `owner=LIVE-TUNE pid=<pid клиента> map=...`.
  Поэтому `bench` и чужие прогоны ждут `stop`.
- `stop` отправляет `quit`. Если клиент завис, `stop` убивает только свой PID, и только после проверки, что в его командной
  строке есть `-ArtLiveTune=<папка сессии>`. Затем снимает только свой замок.
- Сессия без команд дольше 30 мин (`-ArtLiveTuneIdleExit=`) завершается сама.
- `--packaged` запускает собранный клиент `Saved/StagedBuilds`. В нём профиль из pak, поэтому `reload` читает файлы
  ворктри. В отпечатке это `profilesSource=override`, `reference=0`: такие кадры не эталон.
- Кадры и `bench.trace.log` в формате `-Bench`: `bench-<View>-1920x1080.png`, строки `RENDER`, блоки `SHOT`, строки
  профиля и оверлея текущей сборки доски. Поэтому `gates.py`, `hero_light_metrics.py`, `vsref.py` и
  `render_fingerprint.py` работают с ними без изменений. `shot` сам проверяет отпечаток каждого кадра.

## Протокол (S08LiveTune.h)

Драйвер пишет `<папка>/cmd-<seq>.json` атомарно (`.tmp` → rename). Игра опрашивает папку раз в 0,25 с в игровом потоке и
отвечает `done-<seq>.json`: `{seq, action, ok, ms, errors[], warnings[], files[], ...}`. Сокетов нет. Без флага код не
работает: нет опроса, нет журнала трассы, состояние `-Bench` не меняется, тест `Unmatched.S08.LiveTune.OffByDefault`.

| action | поля | что делает |
|---|---|---|
| `reload` | `profiles`, `envDir` (абсолютные; по умолчанию источники старта) | 1) разбирает и проверяет профиль и **все** `*.layout.json` с оверлеями, доску не трогает; 2) при ошибке — `ok:false` с ошибками, доска остаётся как была; 3) иначе подменяет данные, сносит арт-рантайм до состояния после BeginPlay и пересобирает доску обычным путём первой сборки (`SyncBoardFromApplied` → полный `Rebuild` + `SyncFighters`) |
| `shot` | `views`, `out`, `tag`, `settle` (6), `measure` (0), `post` (0), `warmup` (0), `live`, `clock` (`bench`/`free`), `fresh` (true), `append`, `bench {warmup, settle, measure, gap, gapLater}` | камера и выбор героя как у `-Bench` (общий `BenchSetupView`), ожидание, снимок через `TakeEvidenceShot` |
| `state` | — | ревизия / sha / источник профиля, sha раскладки и оверлея, счётчики света, сводка света героя, concept paste, `renderReference` |
| `quit` | — | ответ, затем выход |

## Почему кадр равен свежему `-Bench` (то, что пришлось доказать)

- **Reload = первая сборка.** `AS08BoardActor::ReloadArtData` + `RequestFullRebuild` сбрасывают ключи
  (light profile, env layout, concept paste, backdrop, trace-ключи) и уничтожают компоненты. Следующий `Rebuild` идёт по
  пути первой сборки. Трасса reload совпадает со стартовой: отличаются только строки BeginPlay.
- **`fresh` (по умолчанию).** Перед первым видом выставляется `r.Streaming.DropMips=1` (до снимка первого вида) и
  `r.LumenScene.SurfaceCache.Reset 1`. Без этого K1 после K2-видов резче свежего прогона: в памяти остаются мипы карты
  от K2. Было: средняя |разница| K1 0,99, после — 0,45–0,50.
- **Часы `-Bench` (`clock: bench`, по умолчанию).** Idle-анимации фигур и материалы, завязанные на время (вода, водопады,
  дымка), зависят от времени с момента старта. Live-клиент в каждом виде выставляет позицию клипа каждой фигуры и
  `World->TimeSeconds` такими, какие у свежего `-Bench` в кадре этого вида:
  - стартовая точка — прогрев 60 с + 2,5 кадра;
  - на каждый вид: settle 6 + measure 5 + post 3 с;
  - паузы «снимок → следующий вид»: 0,57 с после первого снимка и 0,41 с после следующих. В них входит фриз чтения и
    записи PNG. Значения откалиброваны перебором по позам на K2 Sarpedon и Cobble (`calibration.json`).

  Смещение первого кадра анимации калибруется на собственном старте сессии. После `reload` фигуры спавнятся заново,
  и смещение нужно, чтобы позы совпали. `clock: free` — без этого; погрешность там до 1,3 % пикселей.

## Статус точности (editor `-game`, High, DX12 Lumen; кадры после reload «вернуть как было»)

Гейт задачи: средняя |разница| ≤ 0,5 и пикселей с разницей > 24 ≤ 0,05 %. Учитывается и шум самого бенча: два свежих
`-Bench` уже различаются в огне Niagara и в воде, которая движется со временем мира. Поэтому `compare --noise` считает
гейт и вне маски этого шума.

| Карта | K1 | K2x1,6 | K2x2,5 | свежий `-Bench` против свежего `-Bench` |
|---|---|---|---|---|
| Sarpedon | 0,45 / 0,015 % / вне шума 0 % | 0,49 / 0,114 % / 0,0002 % | 0,45 / 0,006 % / 0,0001 % | 0,33 / 0,063 %; 0,36 / 0,114 %; 0,36 / 0,002 % |
| Cobble | 0,39 / 0,003 % / 0,0003 % | 0,51 / 0,003 % / 0,0001 % | **0,72** / 0,008 % / 0,0004 % | 0,24 / 0,003 %; 0,38 / 0,002 %; 0,48 / 0,008 % |

- Вне маски шума бенча доля пикселей > 24 на всех видах обеих карт ≤ 0,0004 %. RENDER `reference=1` на всех кадрах.
- Без маски Sarpedon K2x1,6 даёт 0,11 %. Это шум огня и воды: столько же между двумя свежими бенчами.
- Cobble K2x2,5 и иногда K2x1,6: средняя |разница| 0,5–0,72 против 0,48 бенч-бенч. Это равномерный шум 1–3 уровня
  (Lumen / TSR долгоживущей сессии). Видимых отличий нет (> 24: 0,008 %). Более долгий settle и `fresh` его не убирают.
- **Использовать для гейтов можно:**
  - любые метрики по видимым отличиям и областям (зоны, фигуры, маски `hero_light_metrics`);
  - сравнения кадров одной live-сессии между собой (live против live K2x2,5: 0,002–0,006 %).
- **С оговоркой:** метрики, чувствительные к средней разнице на уровне ±0,2 по всему кадру.
- Приёмочные кадры (K1–K3 / GD-058 / ACC-022) снимать свежим `-Bench` или пакетным прогоном, как раньше.

## Что покрывает reload и что требует перезапуска

Reload покрывает:
- `S08ArtBoardProfiles.json`: профили света (направленный, точки, небо, туман, экспозиция, `mapGrade`, `keyShadow`), `heroLight`, `conceptPaste`
  (в т. ч. `lit3d.lights` / `winds` / `anims` / `hide` / `casters`), `readability`, `backdrop`, `mapFrame`, `k1DistanceMul`,
  выбор профиля доски;
- `EnvLayouts/*.layout.json` и оверлеи: пропсы, свет, fx, земля, поднос.

Нужен перезапуск (`stop` + `start`):
- изменения C++;
- новые или изменённые меши, текстуры, материалы, материал-инстансы (`ue_scene_material.py`, `ue_import_*`);
- новый ассет, на который ссылается профиль, если его ещё нет в сборке (в пакете — нужна пересборка pak);
- `zoneStyles` / `fallbackZoneStyle` / `glyphMeshes` / `zoneKeyline` — их загружает только BeginPlay; `reload` предупреждает
  об этом в `warnings`.

Live-кадры одной сессии используют одну и ту же модель времени. Для «до / после» снимайте оба кадра в одной сессии
(или оба свежим `-Bench`). Калибровка пауз сделана под эту машину; на другом железе её надо перепроверить: `bench` + `shot`
с `--bench-gap` / `--bench-gap-later` + `compare`.

## Art Tuner и просмотр без сервера (2026-10-03)

Те же сессии обслуживают панель тюнера ([tools/art/ART-TUNER.md](../ART-TUNER.md)). Действия идут тем же кодом, что и
ползунки панели (`AS08FlowGameMode::ArtTunerSetValue`): проверка строки реестра, запись в документ, профильный парсер,
применение на компонентах без пересборки (кроме группы «пересборка»).

| Команда | Действие протокола | Что делает |
|---|---|---|
| `start ... --art-view` | — | `-ArtView=<map>` вместо `-Bench`: та же фикстура, эффекты живые, свободная камера |
| `start ... --tuner` / `--tuner-file <файл>` | — | `-ArtTuner` (+ `-ArtTunerFile`): модель панели; файл подхватывается при старте |
| `tune --set <id или путь>=<json>` | `tune` | значения строк, применяются сразу (`applyMs` в ответе) |
| `tuner-state` | `tunerState` | строки этой доски, значения, изменённые записи, предупреждения |
| `tuner-save [--file]` | `tunerSave` | `S08ArtTuner.overrides.json` |
| `tuner-reset [--group]` | `tunerReset` | группа (или всё) к значениям профиля |
| `tuner-panel open/close` | `tunerPanel` | панель на экране (кадры `shot` включают UI) |
| `art-view --view --yaw --pitch --pan --select --hero-light --pause --help-card` | `artView` | камера и клавиши `-ArtView` |

Замер 2026-10-03 (editor `-game`, Sarpedon): `tune` трёх строк — 10 мс на команду, применение 1–4 мс; материалы
острова / корабля / листвы — 1,1 мс. `reload` переносит значения тюнера на перечитанный документ.
