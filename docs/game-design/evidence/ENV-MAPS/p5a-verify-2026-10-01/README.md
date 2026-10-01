# ENV-MAPS P5a: проверка P4 в packaged-сборке и недостающие живые доказательства (2026-10-01)

Статус: **измерено, технически импортировано** (packaged-сборка, кук, бенч, живые дуэли). Это не арт-приёмка: «художественно принято» решает только пользователь. Платных шагов, загрузок и новых CC0-наборов не было. Коммитов нет: коммитит оркестратор.

Worktree `C:/tmp/wt-envmaps`, ветка `feat/env-original-maps`, HEAD 2fa377f8 плюс правки этого этапа (§1). Рендер: High (`sg.* = 2`), SP 100, DX12/SM6 + Lumen, 1920×1080 offscreen. Ключевой свет (−55, 30, 0) не трогали (ENV-U12).

Полномочия (пользователь, дословно): ENV-U11 «Сначала packaged + live, потом правки (Recommended)»; ENV-U12 «Оставить как есть (Recommended)»; сервисы «Ты можешь сам все поднять при необходимости, если тебе нужно, и не ограничиваться.»

## Итог

| Пункт | Результат |
|---|---|
| 1. Merlin, дальняя атака вживую | **Доказано на обеих картах.** Opt-in `-JoinerAttack` (новые токены плана `ranged`, `ownresult`). Marmoreal: 8 атак Merlin через общую зону (blue), Sarpedon: 2 (purple). Medusa — по 1. Оба проверяльщика: exit 0 с `--require-ranged-attacker f-1-sk0` и `f-0-hero` |
| Автотесты | `Unmatched.S08+S09+S10`: 224 / 224 Success, «EXIT CODE: 0» (+2 новых теста). `verify_graph_duel.py --self-test`: PASS (12/12) |
| 2. Кук | 886 пакетов, «Success - 0 error(s), 0 warning(s)». Все требуемые ассеты P4 в utoc; профили rev 11, оба layout и 3 фикстуры бенча в паке байт в байт |
| 3. Производительность | GPU нашего процесса на картах +0,15…+0,27 мс к P3 (+7…12 %, значимо), на Cobble +0,02…+0,06 мс. Главный вклад — проход Translucency (+0,08…+0,12 мс). FPS и render thread **не сравнимы с P3**: фон GPU/CPU выше, это касается и неизменного Cobble (§3.3) |
| 4. Живые прогоны | K1 и K3 до GAME_OVER на обеих картах: все гейты скриптов пройдены. 19 кадров `packaged-live` / `strict`. Ходы только по связям, итог совпадает с сервером |
| Подложки подписей | Видны в живых кадрах: в каждом из 19 кадров 5–6 подписей на тёмной подложке. Подложка темнее фона во всех 112 случаях, минимум на 23,7 L. Контраст текста 5,9–10,3 : 1 (§4.3) |
| Тёплый засвет S07 / S15 / S27 | Измерен. Локальный тёплый сдвиг кругов dab ≈ 21–23 (P3: 8,6–17,8). Сдвиг одинаков в бенче и в живом кадре. Разделение brown–red выросло: ΔE 32,3 → 36,0 (§5) |
| Скан секретов | 0 совпадений (§6) |

## 1. Правки кода и скриптов (рабочее дерево, не закоммичены)

Без флага `-JoinerAttack` поведение по умолчанию не меняется: планы `attack` и `defend+resolve` прежние, порядок автоатаки без токена `ranged` прежний (тест `AutoPicks`). Единственное исключение — сужение регулярки приватности (п. 6 списка ниже).

1. **`S09/S09ManeuverUi.{h,cpp}`**
   - `FS09CommandUi::AutoAttackPicks` — чистая функция с порядком автоатаки S09AUTO. Логика вынесена из цикла `S08FlowGameMode` без изменений: сначала смежный враг, затем, на досках с топологией, враг только через общую зону.
   - С `bPreferRanged` пары «только через зону» идут первыми.
   - `FS09CommandUi::PickRangedPosition` — клетка, из которой дальнобойный боец видит цель только через зону: связанного врага нет, общая зона есть. Кандидаты берутся из `ComputeReachableCells` за вычетом конечных клеток других ходов. Путь строит `BuildManeuverPath`, по связям. Выбор: меньше шагов, затем Y, затем X. На сетках позиции нет.
2. **`S08/S08FlowGameMode.cpp`** — драйвер S09AUTO.
   - Цикл автоатаки использует `AutoAttackPicks`.
   - Токен `ranged` в `-S09Combat=…`:
     - пары «через зону» идут первыми;
     - такая атака не откладывается ради карты «may boost»;
     - дальнобойные помощники (Merlin) маневрируют в позицию «через зону». В трассе: `S09AUTO ranged position fighter=… from=… to=… steps=… zoneTarget=…`.
   - В строку `S09AUTO ranged target …` добавлен суффикс ` prefer=ranged`.
   - Токен `ownresult`: кадр `s09-combat-result.png` снимается только в бою, где атаковала эта сторона.
3. **`S08/S08BoardGraphTests.cpp`** — новые тесты на синтетическом графе:
   - `Unmatched.S09.RangedTargets.AutoPicks`: порядок хоста; порядок присоединившегося с `ranged` и без; связь сильнее зоны; мёртвые бойцы; сетка без зонных пар;
   - `Unmatched.S09.RangedTargets.RangedPosition`: Merlin остаётся на месте или идёт по связи G05 → G02; резерв клетки; melee-боец, мёртвый боец и сетка — без позиции.
4. **`tools/s09/run-combat-demo.ps1`** — opt-in `-JoinerAttack`.
   - План хоста `attack+defend+ownresult`, план присоединившегося `attack+ranged+defend+resolve`.
   - Гейты:
     - в трассе присоединившегося есть `S09AUTO attack (`, `ATTACK sent`, `ATTACK done seq=`;
     - хост ответил на окно защиты;
     - счётчики пишутся в `manifest.json` → `joinerAttack`.
5. **`tools/s09/verify_graph_duel.py`**
   - Дальние атаки ищутся в трассах **обеих** сторон (`seat`) и считаются по атакующим (`byAttacker`).
   - Новый гейт `--require-ranged-attacker ID`.
   - Self-test дополнен случаем Merlin со стороны присоединившегося.
   - **`tools/s09/xcheck_graph_duel.py`**: `rangedByAttacker` и тот же гейт.
6. **Гейт приватности в `run-combat-demo.ps1`** — регулярка `(?<!PEND-)(ATTACK|DEFENSE|RESOLVE|SCHEME) sent .*card`.
   - Первая попытка K3 упала на строке `PEND-RESOLVE sent type=DISCARD_CARDS … id=discard-choice-<cardId>-after-0-61`. Это ответ на pending-выбор, а не боевая команда. Сработал регистронезависимый `card` в имени типа.
   - Тот же класс id (`<cardId>-during-0-boost`, `<cardId>-after-0-p0`) уже был в принятых трассах P3.
   - Изменение **сужает гейт по умолчанию** только для строк `PEND-RESOLVE`. Это записано в открытых вопросах.

Почему `ownresult`. Во второй попытке K3 у хоста первый бой был защитой от Merlin. Сразу после результата открылся pending-выбор Medusa `TARGET_FIGHTER`, и в кадре результата не было маркера: `rst=0`, гейт скрипта упал. В плане по умолчанию хост всегда атакующий, поэтому токен нужен только при `-JoinerAttack`.

## 2. Сборка, тесты, packaged и кук

Сборки шли с флагами `-NoXGE -MaxParallelActions=6` под `C:/tmp/unmatched-package.lock`. Логи лежат вне git: `C:/tmp/envmaps-research/p5a/build/{b1,b2,.}/`, `…/package/{pk1,pk2,.}/`.

| Шаг | Результат |
|---|---|
| Build.bat `UnmatchedEditor` и `Unmatched`, три итерации (b1 → токен `ranged`; b2 → `PickRangedPosition`; финал → `ownresult`) | каждый раз «Result: Succeeded», ошибок C/LNK нет |
| `node tools/s08/run-ue-tests.cjs "Unmatched.S08+Unmatched.S09+Unmatched.S10"` | b1 223/223, b2 224/224, финал **224/224**, Fail 0, «EXIT CODE: 0» |
| `tools/s08/package-client.ps1 -SkipBuild` (финал pk3, 11:44–11:45) | «BUILD SUCCESSFUL», BuildCookRun 58,6 с; кук: Packages Cooked 886, Total 893, «Success - 0 error(s), 0 warning(s)» ([package/uat-summary.txt](package/uat-summary.txt)) |

Хэши финальной сборки ([package/hashes.txt](package/hashes.txt)):
- внутренний `Unmatched.exe` = `Binaries/Win64` = `52e76f392be1aabb…fd87`;
- `Unmatched-Windows.pak` `e227ca5c…c720`;
- utoc `1f7a6aae…f97e`;
- ucas `6d50fcdc…d421`.

**Бенч шёл на первой упаковке pk1** (exe `678caa54…328f`), живые прогоны — на финальной pk3.
- Все 1196 записей utoc pk1 и pk3 имеют одинаковые хэши чанков, pak тоже совпадает (`e227ca5c…`). Значит, кукнутый контент одинаков.
- Exe отличаются только драйвером S09AUTO, а в `-Bench` он не работает.

**Проверка кука** ([package/cook-check.json](package/cook-check.json), [package/content-check.txt](package/content-check.txt)):
- `/Game/EnvKit` и `/Game/EnvMaps`: 111 из 115 исходных ассетов в utoc. Четыре отсутствующих — `/Game/EnvMaps/Data/*` (GameSDF/SpaceID), они в `DirectoriesToNeverCook` по замыслу, как в P3.
- Требуемые P4 — все в utoc:
  - `EnvKit/Shared/M_EnvProp`;
  - `M_EnvGround`, `MI_EnvGround_{Marmoreal,Sarpedon}`;
  - `M_EnvWaterfall`, `MI_EnvWaterfall_Sarpedon`;
  - `EnvMaps/M_MapFrameWood`, `M_MapContactShadow`, `M_MapBoard`, `MI_{Marmoreal,Sarpedon}_MapBoard`;
  - `T_EnvGround_{Marmoreal,Sarpedon}_Aux`, `Sets/T_Ground_WaterRipple_N`.
- Шейдеры заново собраны при куке pk1, SM5 и SM6, 14 строк ([package/shadermaps-compiled-pk1.txt](package/shadermaps-compiled-pk1.txt)): `M_EnvGround`, `M_EnvWaterfall`, `M_EnvProp`, `MI_Env_Cherry`, `M_MapBoard`, `M_MapContactShadow`, `M_MapFrameWood`. Это новые графы P4.
- Все 66 путей `/Game/…` из профилей, layout и фикстур бенча есть в utoc, кроме тех же четырёх Data.
- Пак (UnrealPak -Extract) против файлов worktree ([package/config-identity.txt](package/config-identity.txt)) — **байт в байт**:
  - `S08ArtBoardProfiles.json` (revision 11, `c90dddd9…0a8b`);
  - `EnvLayouts/marmoreal.layout.json` (`a58b72dd…fc11`) и `sarpedon.layout.json` (`1cd648a3…d738`);
  - `Bench/S08Bench{Cobble,Marmoreal,Sarpedon}.json`.
- `DefaultGameUserSettings.ini` в паке без комментариев: UAT вырезает их при стейджинге, хэш тот же, что в P3. Значения `FrameRateLimit=60`, `sg.*=2`, `ResolutionQuality=100`.
- **Графы v2 работают в рантайме packaged**. Строки трассы бенча:
  ```
  ARTPREVIEW board profiles source=pak sha256=c90dddd95a8a7a0b12294b1a6f47218d6e7a860f74b8c51660d4fdb00c320a8b
  ARTPREVIEW map grade profile=sarpedon-night source=profile … maskSaturation=1.05 liftSaturation=1.10 maskInverseTint=(1.0500,0.9960,0.8910) graph=v2 maskTerms=1
  ARTPREVIEW envlayout ground map=sarpedon mode=runtime strips=4 material=MI_EnvGround_Sarpedon … falls=1/1 fallCards=2 status=ok
  ARTPREVIEW envlayout map=sarpedon props=24 lights=5 missingMeshes=0 … combinedPoints=6 combinedBudgetOk=1 … status=ok
  ARTPREVIEW map frame wood=frame-wood material=M_MapFrameWood valueScaleSrgb=0.70 valueScaleLinear=0.4563 saturation=0.75
  ARTPREVIEW readability fighter=f-0-hero hero=1 contactShadow=1 diameterUU=52.0 strength=0.25 leaderPip=1 look=P1 ringScale=1.00
  ARTPREVIEW reachable rings cells=19 placed=1 radiusUU=36 segments=48 style=readability color=#FFC857 stroke=#14110C widthUU=3.50 strokeUU=1.50
  ```
  У Marmoreal то же: `props=21`, `falls=0/0`, `graph=v2`.
- **Packaged = editor P4.** Кадры бенча r1 против кадров P4 (editor `-game`) тех же видов: средняя |d| RGB 0,39–0,64, p99 |ΔY| ≤ 4,6. Cobble K1 против packaged P3: |d| 0,30, яркость 45,58 / 45,57. Сеточная доска не изменилась.

## 3. Производительность: packaged `-Bench`, 3 повтора

```
# GPU-лок C:/tmp/unmatched-gpu.lock: 10:59:45 – 11:24:00 (bench/gpu-quiet/lock-*.txt); вперемешку r1 marmoreal, cobble, sarpedon, затем r2, r3
python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --name <board> --repeats <1|2|3> \
  --views K1+K1x0.65+K2x1.6+K2x2.5 --out C:/tmp/envmaps-research/p5a/bench/runs-raw [--bench-fixture ../../../Unmatched/Config/Bench/S08Bench<Map>.json]
python tools/art/render/render_bench.py summarize --out bench/bench-summary.json <runs>/cobble <runs>/marmoreal <runs>/sarpedon
python bench/analyze.py      # → bench/p5a-bench-summary.json (CSV-счётчики, nvidia-smi в окне)
python bench/compare_p3.py   # → bench/p5a-vs-p3.json (Δ к P3, порог 2 × max шума)
```

Все 9 прогонов: `exit 0`, `BENCH done`, 158–162 с. Все 36 кадров на эталоне рендера (`referenceCheck`: `reference: true`).

### 3.1 P3 → P5a (среднее по 3 повторам)

GPU — `BENCH measure` (avg, мс). Δ значима, если |Δ| > 2 × max(шум). «Translucency Δ» — изменение прохода `GPU/Translucency` по CSV. «Окружение» — GPU карты минус GPU Cobble того же этапа (P3 → P5a).

| Доска | Вид | GPU avg, мс | Δ / порог | GPU p95 | Translucency Δ | FPS | render thread, мс | вызовы | примитивы, млн | nvidia-smi p50, % | VRAM, МиБ | Окружение, мс |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Cobble | K1 | 1,823 → 1,857 | +0,034 / 0,020 знач. | 1,89 → 1,92 | +0,000 | 241,2 → 158,7 | 4,14 → 6,30 | 213 → 213 | 0,85 → 0,85 | 89 → 96 | 4068 | – |
| Cobble | K1x0,65 | 1,737 → 1,773 | +0,036 / 0,020 знач. | 1,79 → 1,84 | −0,001 | 248,2 → 161,0 | 4,03 → 6,21 | 204 → 204 | 0,68 → 0,68 | 88 → 95 | 4117 | – |
| Cobble | K2x1,6 | 1,927 → 1,943 | +0,016 / 0,020 не знач. | 2,15 → 2,03 | −0,001 | 235,1 → 150,4 | 4,25 → 6,65 | 284 → 283 | 0,93 → 0,93 | 90 → 96 | 4182 | – |
| Cobble | K2x2,5 | 2,070 → 2,127 | +0,057 / 0,040 знач. | 2,23 → 2,33 | +0,003 | 235,0 → 149,9 | 4,25 → 6,67 | 250 → 250 | 1,02 → 1,02 | 89 → 96 | 4180 | – |
| Marmoreal | K1 | 2,280 → **2,440** | +0,160 (+7,0 %) / 0,060 | 2,46 → 2,64 | +0,121 | 228,8 → 147,0 | 4,37 → 6,80 | 239 → 263 | 1,17 → 1,25 | 89 → 96 | 4118 | +0,457 → **+0,583** |
| Marmoreal | K1x0,65 | 2,187 → 2,347 | +0,160 / 0,120 | 2,33 → 2,56 | +0,082 | 234,4 → 148,2 | 4,27 → 6,75 | 235 → 259 | 1,04 → 1,12 | 82 → 96 | 4100 | +0,450 → +0,574 |
| Marmoreal | K2x1,6 | 2,213 → 2,483 | +0,270 / 0,020 | 2,41 → 2,67 | +0,104 | 233,2 → 147,7 | 4,28 → 6,77 | 293 → 244 | 1,02 → 1,06 | 88 → 96 | 4166 | +0,286 → +0,540 |
| Marmoreal | K2x2,5 | 2,227 → 2,460 | +0,233 / 0,060 | 2,41 → 2,63 | +0,099 | 235,7 → 149,4 | 4,24 → 6,69 | 236 → 203 | 0,93 → 0,96 | 88 → 96 | 4198 | +0,157 → +0,333 |
| Sarpedon | K1 | 2,237 → **2,393** | +0,156 (+7,0 %) / 0,080 | 2,39 → 2,60 | +0,100 | 232,3 → 146,5 | 4,30 → 6,83 | 239 → 268 | 1,18 → 1,33 | 88 → 96 | 4195 | +0,414 → **+0,536** |
| Sarpedon | K1x0,65 | 2,170 → 2,320 | +0,150 / 0,040 | 2,31 → 2,53 | +0,082 | 233,0 → 149,8 | 4,29 → 6,67 | 235 → 267 | 1,07 → 1,21 | 88 → 96 | 4224 | +0,433 → +0,547 |
| Sarpedon | K2x1,6 | 2,140 → 2,360 | +0,220 / 0,040 | 2,35 → 2,59 | +0,099 | 228,7 → 146,1 | 4,37 → 6,84 | 469 → 329 | 1,26 → 1,38 | 88 → 96 | 4264 | +0,213 → +0,417 |
| Sarpedon | K2x2,5 | 2,167 → 2,363 | +0,196 / 0,060 | 2,34 → 2,57 | +0,093 | 229,6 → 152,5 | 4,36 → 6,55 | 365 → 251 | 1,01 → 1,02 | 87 → 96 | 4293 | +0,097 → +0,236 |

### 3.2 Что изменилось (GPU нашего процесса)

- **Окружение на K1 стоит +0,54–0,58 мс GPU** к Cobble (в P3 было +0,41–0,46): прирост за P4 около 0,12 мс на K1 и 0,14–0,25 мс на K2.
- Самый большой вклад — **Translucency, +0,08–0,12 мс на обеих картах**, на Cobble ≈ 0. Раз он есть и на Marmoreal, где водопада нет, вероятные источники — общие для карт новинки читаемости: пятна контактной тени `M_MapContactShadow` под 6 фигурами и, возможно, кольца хода. Водопад Sarpedon сверх этого заметно не добавляет. Это гипотеза по счётчикам, по-проходных замеров отдельных объектов нет.
- На K2x1,6 и K2x2,5 добавляется RenderDeferredLighting: +0,10 / +0,12 мс на Marmoreal (ярче фонари) и +0,03 мс на Sarpedon.
- Вызовы отрисовки на K1 выросли с 239 до 263–268: новые пропсы (21 / 24 против 17 / 18). Примитивы — с 1,17 до 1,25–1,33 млн. На K2 вызовов меньше, потому что корпус корабля переехал.
- Свет не изменился: 1 ключ + 6 точек (`combinedPoints=6 combinedBudgetOk=1`).
- Бюджет не превышен: 2,4 мс GPU на 1080p High против 16,67 мс при 60 FPS.

### 3.3 Фон и пометка загрязнения

**Пометка: загрязнено фоном сильнее, чем в P3. FPS и render thread с P3 не сравнимы.** Доказательство — неизменный Cobble: тот же контент, те же вызовы и примитивы, а FPS упал с 241 до 159, render thread вырос с 4,1 до 6,3 мс, game thread — с 1,12 до 1,29 мс. GPU нашего процесса на Cobble сдвинулся лишь на +0,02…+0,06 мс. Сравнивать с P3 можно только время GPU процесса (`RHIGetGPUFrameCycles`, CSV `GPUTime`).

| Момент | Замер |
|---|---|
| 10:58, до бенча, 30 с ([bench/gpu-quiet/quiet-pre-30s.csv](bench/gpu-quiet/quiet-pre-30s.csv)) | GPU p50 39 %, p95 41 %, макс 46 % (в P3 было 30 / 32 / 39). pmon: `claude.exe` 29–37 % SM, ChatGPT 4–9 % ([consumers-pre.txt](bench/gpu-quiet/consumers-pre.txt)) |
| CPU до бенча ([cpu-pre.json](bench/gpu-quiet/cpu-pre.json)) | всего 0–23 % по 32 потокам; верх — `claude`, `TextInputHost`, `chrome`, `dwm`, ChatGPT |
| Во время 9 прогонов, pmon раз в 5 с, 10:59–11:24 ([pmon-summary.json](bench/gpu-quiet/pmon-summary.json)) | `claude.exe` до 47 % SM, > 20 % в 104 из 283 выборок; `dwm` до 31 %, Chrome до 22 % (оркестратор параллельно ведёт Chrome и Codex), ChatGPT до 21 %. Других игр и рендеров нет, Blender не запущен |
| CPU после бенча ([cpu-post.jsonl](bench/gpu-quiet/cpu-post.jsonl)) | 3–42 %, всплески `git` / `pwsh` других сессий |

CPU **во время** бенча не записан: сэмплер писал файл только в конце и был остановлен вместе с цепочкой. Сэмплер исправлен (построчная запись) и использован после бенча. В итоге фон GPU примерно на 9 п.п. выше P3, и в окнах замера вся GPU занята на 96 % против 88–89 %. На FPS без ограничения это влияет сильнее, чем на время GPU процесса.

Сырые CSV профилировщика (36 файлов) лежат вне git: `C:/tmp/envmaps-research/p5a/bench/runs-raw/`, sha256 — в [bench/bench-csv-SHA256SUMS.txt](bench/bench-csv-SHA256SUMS.txt). Кадры r1 — в `bench/frames/<доска>/`. В `bench/runs/<доска>/r{1,2,3}/` лежат `bench-run.json`, трасса, `nvidia-smi.csv` и `client.log` (`loginid` заменён на `<redacted>`).

## 4. Живые прогоны (S09-стек, packaged pk3, пара клиентов по 30 FPS)

**Стек.**
- Docker Desktop был остановлен. Его запустил этот этап (`docker desktop start`) после обхода устаревших сокетов, как в P3. Каталоги `%LOCALAPPDATA%/Docker/run` и `%LOCALAPPDATA%/docker-secrets-engine` отодвинуты в `*.stale-20261001-p5a`, ничего не удалено.
- Запущены `docker start codex-s09-postgres codex-s09-redis` (:55434 / :6381).
- `node tools/s09/bootstrap-s09-stack.cjs` → «Bootstrap OK». Типы атаки: Medusa ranged, Merlin ranged.
- `seed-env-map-boards.ts --verify`: обе доски `present / cellsIdentical / featuresTopology / featuresFixtureSha256 / sizeIdentical = true`. Marmoreal `c121b47f8d6eb28daccb76d05` — 31 пространство и 42 связи; Sarpedon `c7fa64a26c29a0835f2383e63` — 38 и 61.
- Бэкенд :3120 — `node -r dotenv/config dist/src/main.js` из `backend/` worktree. `dist` не пересобирался: он собран в 07:15, после последней правки `backend/src`.

**GPU-лок** `C:/tmp/unmatched-gpu.lock` — три окна ([live/gpu-lock.txt](live/gpu-lock.txt)), между ними пересборки. Фон перед прогонами, 20 с ([live/gpu-baseline-20s.csv](live/gpu-baseline-20s.csv)): p50 46 %, p95 49 %, макс 50 % (в P3 было 29–32 %).

**Команды.** Обёртка [helpers/live_run.py](helpers/live_run.py) — копия обёртки P3 с владельцем лока `ENV-MAPS-P5a`. Учётные данные передаются только через окружение (`tools/s09/run-with-env.cjs`).

```
python helpers/live_run.py --kind phase2 --label k1-<map> --evidence-dir live/<map>/k1 -- -Api http://localhost:3120/graphql \
  -ArtPreviewBoardId <id> -ArtPreviewHeroesV2 -ArtPreviewDiorama -ArtPreviewShotAfter 36 -RunSeconds 50 -ClientFps 30 \
  -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf
python helpers/live_run.py --kind combat --label k3-<map> --evidence-dir live/<map>/k3 -- -Api http://localhost:3120/graphql \
  -ArtPreview -FullHd -ArtPreviewBoardId <id> -ArtPreviewHeroesV2 -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High \
  -RequireRenderReference -RequireShotCaptured -ClientPerf -RequireGameOver -RunSeconds 480 -JoinerAttack
python tools/s09/verify_graph_duel.py --host-trace <K3>/combat-client-host.trace.log --joiner-trace <K3>/combat-client-joiner.trace.log \
  --require-moves --require-ranged --require-result --require-ranged-attacker f-0-hero --require-ranged-attacker f-1-sk0 --json <K3>/graph-duel-check.json
python tools/s09/xcheck_graph_duel.py --host-trace … --joiner-trace … --require-ranged-attacker f-0-hero --require-ranged-attacker f-1-sk0 --json <K3>/graph-duel-xcheck.json
python helpers/sidecars.py live/<map> <K1> <K3>
python tools/art/classify_evidence.py --require packaged-live --strict --render-reference --require-captured <K1> <K3>
```

### 4.1 Прогоны

| Карта | Прогон | Каталог | Комната | seq | Итог |
|---|---|---|---|---|---|
| Marmoreal | K3, попытка 1 (pk1) | [k3/failed-20261001-113325](live/marmoreal/k3/failed-20261001-113325/attempt.json) | FINISHED | – | гейт приватности сработал на `PEND-RESOLVE … DISCARD_CARDS` (§1, п. 6). Merlin в этой попытке был на M24 (только violet), зонных целей не было: `ranged picks=0` → добавлен `PickRangedPosition` |
| Marmoreal | K3, попытка 2 (pk2) | [k3/failed-20261001-114214](live/marmoreal/k3/failed-20261001-114214/attempt.json) | FINISHED | – | Merlin уже атаковал через зону, но у хоста не было маркера результата (`rst=0`, §1) → добавлен `ownresult` |
| Marmoreal | **K1** | [k1/run-20261001-114548](live/marmoreal/k1/run-20261001-114548/) | ABORTED (проверено) | 1 / 1 | `artcheck` пройден у хоста и присоединившегося, 2 кадра |
| Marmoreal | **K3 + GAME_OVER** | [k3/combat-20261001-114658](live/marmoreal/k3/combat-20261001-114658/) | FINISHED, победа хоста | 131 / 131 | 10 кадров, все гейты |
| Sarpedon | **K1** | [k1/run-20261001-114858](live/sarpedon/k1/run-20261001-114858/) | ABORTED (проверено) | 1 / 1 | `artcheck` пройден у обоих, 2 кадра |
| Sarpedon | **K3 + GAME_OVER** | [k3/combat-20261001-115008](live/sarpedon/k3/combat-20261001-115008/) | FINISHED, победа хоста | 40 / 40 | 9 кадров, все гейты, с первой попытки |

Обе неудачные попытки сделаны на промежуточных бинарниках, их `attempt.json`, трассы и логи сохранены. Промежуточные K1 Marmoreal на pk1 и pk2 вынесены вне git (`C:/tmp/envmaps-research/p5a/live/superseded/`): все опубликованные прогоны должны быть на одном финальном бинарнике.

Гейты K3, вывод скрипта (Marmoreal / Sarpedon):
```
combat plans: host=attack+defend+ownresult joiner=attack+ranged+defend+resolve
joiner attack plan: joiner attacks done=8 ranged picks=21; host attacks done=8 defenses=8      # Sarpedon: 2 / 6; 5 / 2
markers joiner: defense(def=1729 …) resolve(res=2590 …) result(rst=2387 …) host: result(rst=2366 …)
reveal markers joiner: resolve(res=2373) reveal(rvl=3063 …)                                     # Sarpedon rvl=3032
heroes v2 host: figures=6 idle=6 clips Idle=36 LungeAttack=16 HitReact=16 DeathSettle=1        # Sarpedon 20/7/7/1
render fingerprint host: shots=18 gated=17 offReference=0 …                                     # Sarpedon 13/12/0
convergence: host maxSeq=131 joiner maxSeq=131                                                  # Sarpedon 40/40
GAME_OVER gate ok: row FINISHED, winner seat=host (host VICTORY, joiner DEFEAT), result seq host=131 joiner=131
```
Строки игр FINISHED с `boardId` своей карты. В изолированной БД 8 игр этого этапа, все ABORTED или FINISHED.

**Классификация:** [marmoreal](live/marmoreal/classify-strict.json) — 10 кадров, [sarpedon](live/sarpedon/classify-strict.json) — 9. Все `packaged-live` / `strict` / `rejected=false`, EXIT 0.

### 4.2 Доказательство игры по графу и Merlin

| Проверка | Marmoreal `verify` / `xcheck` | Sarpedon `verify` / `xcheck` |
|---|---|---|
| (a) ходы манёвра по связям | 4 хода, 8 шагов, `allLinked` / нарушений 0 | 4 хода, 6 шагов, `allLinked` / нарушений 0 |
| перемещения не манёвром | 0 | 0 |
| (b) дальняя атака через общую зону, по атакующим | `f-1-sk0` (Merlin) **8**, `f-0-hero` (Medusa) 1 / то же | `f-1-sk0` **1** / **2**, `f-0-hero` 1 / 1 |
| атаки, похожие на нелегальные | – / 0 | – / 0 |
| (c) итог | VICTORY / DEFEAT, GAME_ENDED | VICTORY / DEFEAT, GAME_ENDED |
| код выхода с `--require-ranged-attacker f-0-hero f-1-sk0` | 0 / 0 | 0 / 0 |

JSON: [marmoreal check](live/marmoreal/k3/combat-20261001-114658/graph-duel-check.json), [xcheck](live/marmoreal/k3/combat-20261001-114658/graph-duel-xcheck.json); [sarpedon check](live/sarpedon/k3/combat-20261001-115008/graph-duel-check.json), [xcheck](live/sarpedon/k3/combat-20261001-115008/graph-duel-xcheck.json).

**Marmoreal: Merlin.**
- Манёвр seq 9: King Arthur M31 → M23 → M26 и Merlin M23 → M24 → M16 одним ходом. Трасса присоединившегося:
  ```
  S09AUTO ranged position fighter=f-1-sk0 from=M23 to=M16 steps=2 zoneTarget=f-0-hero
  S09AUTO ranged target attacker=f-1-sk0 at=M16 target=f-0-hero at=M25 via=shared-zone (not linked) prefer=ranged
  S09AUTO attack (attacker=f-1-sk0 target-set card-set)
  ```
- Сервер принял атаки Merlin по Medusa:
  - seq 10, 18, 21 — с M16 на M25;
  - seq 34, 44, 59, 97, 120 — с M12 на M25, после манёвра M16 → M12 в seq 33.
- Во всех случаях пространства **не связаны**, общая зона **blue**.
- Medusa: seq 4, M25 → M31, общая зона brown, не связаны. Её остальные атаки (M25 → M26) шли по связи.

**Sarpedon: Merlin.**
- seq 8: S25 → S35, purple, не связаны.
- seq 33: S22 → S35, purple, не связаны (Merlin сходил S25 → S22 в seq 32).
- `verify` считает только seq 33. Для seq 8 его окно не нашло `ATTACK done`: драйвер записал ту же строку выбора цели ещё 4 раза, до неё. `xcheck` по серверным строкам видит обе атаки.
- Medusa: seq 4, S35 → S32, purple, не связаны.

Сервер принимал дальние атаки по одному правилу для обоих героев. Принуждения к нелегальной атаке нет: драйвер выбирает только пары, которые проходят `SelectAttacker` / `SelectTarget`, а их сверяет сервер.

### 4.3 Подложки подписей в живых кадрах (пробел ревью P4)

Трасса обоих клиентов на обеих картах: `HUD tags boardPlate=1 hardPadPx=3 profile=<map>-original`. Замер — [helpers/plates.py](helpers/plates.py) → [label-plates.json](label-plates.json): прямоугольники `SHOT widget id=board.tag … geom=painted visible=1` из блока кадра, пиксели кадра.

- **19 кадров, 112 подписей.** В K1 у хоста 5 подписей (подпись выбранной Medusa заменена плашкой), у присоединившегося 6.
- **Подложка темнее фона в 112 случаях из 112.** Медиана L тёмной части подложки 19,6–50,1, кольцо 4–9 px вокруг — 46,7–209,7, разница не меньше 23,7.
- **Контраст текста к подложке** (WCAG) 5,9–10,3 : 1. Подписи P1 — 8,0–10,3, P2 — 5,9–7,2: у текста P2 ниже 90-я перцентиль.
- Контур в цвет команды: P1 золотистый (~187, 162, 106), P2 голубой (~98, 137, 164).
- Минимальный зазор между подписями в кадре — 33 px (требование ≥ 3 px).
- Кадры с подложками:
  - K1: [Marmoreal хост](live/marmoreal/k1/run-20261001-114548/phase2-board-host-1920x1080.png), [Marmoreal присоед.](live/marmoreal/k1/run-20261001-114548/phase2-board-joiner-1920x1080.png), [Sarpedon хост](live/sarpedon/k1/run-20261001-114858/phase2-board-host-1920x1080.png), [Sarpedon присоед.](live/sarpedon/k1/run-20261001-114858/phase2-board-joiner-1920x1080.png);
  - K3: все 8 / 7 кадров боя.
- Листы кропов ×3 лежат вне git (в них пиксели карты, ENV-U3/U7): `C:/tmp/envmaps-research/p5a/plates/*-tags.png`. Визуально — тёмные скруглённые подложки с контуром в цвет команды, текст «16/16», «1/1», «18/18», «7/7».

### 4.4 Производительность пары (запись, не ACC-022)

Пометка: **dev-PC (RTX 4090), не D-07; фон 46 % до прогонов; не тихая машина.**

| Прогон | GPU пары p50 / p95 / макс, % | VRAM макс, МиБ | FPS хост / присоед. (медиана окон) | gpuMs p50 хост / присоед. (`afterWarmup`) |
|---|---|---|---|---|
| Marmoreal K1 | 49 / 54 / 62 | 5711 | 30,0 / 30,0 | 2,41 / 2,41 |
| Marmoreal K3 | 47 / 57 / 60 | 5857 | 29,8 / 30,0 | – * |
| Sarpedon K1 | 46 / 52 / 53 | 5701 | 30,0 / 30,0 | 2,33 / 2,44 |
| Sarpedon K3 | 43 / 53 / 59 | 5999 | 28,6 / 28,6 | – * |

\* После GAME_OVER бой выходит сразу, итоговой строки нет (как в P3). Провалы > 50 мс в K3 приходятся на кадры-доказательства. Подробности — `perf.json` каждого прогона. Фон до прогонов уже 46 %, поэтому прирост пары к фону здесь не выделяется.

## 5. Тёплый засвет фонарей корабля на восточных кругах Sarpedon (S07 / S15 / S27)

Метод: [helpers/spill.py](helpers/spill.py) → [sarpedon-lantern-spill.json](sarpedon-lantern-spill.json).
- Для каждого круга берётся медиана CIELAB заливки (0,35–0,75 радиуса) в кадре по камере `SHOT ctx` минус медиана тех же точек оригинальной карты. Это остаток.
- Опорный остаток — медиана по 12 «неосвещённым» кругам: дальше 450 uu от всех тёплых точек (фонари и костры) обоих layout, P3 и P5a. Набор общий для всех кадров.
- Локальный сдвиг = остаток круга − опора.
- Одинаковой зоны вне корабельной стороны нет: все red/brown круги восточные. Поэтому прямое сравнение «зона к зоне» невозможно.

| Кадр | S07 (brown) dL / da / db / dab | S15 (red) | S27 (red) | Расст. до фонаря S07 / S15 / S27, uu |
|---|---|---|---|---|
| P3 packaged бенч K1 (фонари до переноса) | +0,1 / +10,3 / +14,5 / **17,8** | −0,8 / +7,0 / +12,4 / **14,3** | −5,9 / +3,9 / +7,7 / **8,6** | 261 / 298 / 336 |
| P3 packaged live K1 (хост) | −0,1 / +10,6 / +14,3 / 17,8 | −0,9 / +7,2 / +12,2 / 14,1 | −6,1 / +4,0 / +7,6 / 8,6 | то же |
| P4 editor бенч K1 | −0,3 / +14,4 / +15,8 / 21,4 | +1,4 / +14,9 / +16,5 / 22,2 | −0,1 / +15,5 / +16,5 / 22,6 | 254 / 266 / 249 |
| **P5a packaged бенч K1, r1 / r2 / r3** | −0,2…−0,3 / +14,2…14,3 / +15,8…15,9 / **21,3–21,4** | +1,4…1,5 / +14,6…14,8 / +16,5…16,6 / **22,1–22,2** | −0,1 / +15,4…15,5 / +16,3…16,4 / **22,5–22,6** | 254 / 266 / 249 |
| P5a packaged live K1, хост / присоед. | 20,3 / 21,4 | 21,1 / 22,1 | 21,4 / 22,5 | то же |

- После переноса фонарей на корпус (P4) **все три круга получают почти одинаковый тёплый сдвиг**, dab ≈ 21–23. Это a\* +14…15, b\* +16, яркость почти не меняется (|dL| ≤ 1,7).
- В P3 сдвиг падал с севера на юг: 17,8 → 14,3 → 8,6. S27 тогда был в 336 uu от фонаря, теперь в 249 uu. Интенсивность выросла: 70 / 65 / 50 → 85 / 80 / 65 кд.
- Медиана сдвига всех кругов в 350 uu от фонарей: P3 da / db = 5,0 / 10,0, P5a — 14,3 / 15,8.
- Повторяемость: 3 повтора бенча расходятся не более чем на 0,1. Живой кадр совпадает с бенчем в пределах ~1 (у хоста над S07 и S15 видна подпись или кольцо).
- **Влияние на читаемость зон:** brown–red (S07 против S15/S27) в packaged K1 — ΔE 32,3 (P3) → **36,0** (P5a), `zone_separation.py measure`. Минимальная смежная пара Sarpedon blue–purple — 22,3 → 23,2, Marmoreal — 21,0 → 23,3, как в editor P4. Засвет красные круги не «сливает». Но он равномерно окрашивает весь восточный столбец в тёплый цвет. Это вопрос художественной оценки, решает пользователь.

## 6. Приватность, секреты, процессы

- **Скан секретов** — `python ../p3-packaged-2026-10-01/live/helpers/secret_scan.py <этот каталог> --staging <коды>`. Проверялось:
  - значения `backend/.env` (11 ключей PASSWORD / EMAIL / SECRET / DATABASE_URL);
  - JWT-подобные строки, `Bearer`, URL postgres;
  - коды комнат всех 8 игр этапа, взятые из `Game.code` изолированной БД во временный файл вне git.

  Итог: **0 совпадений**, весь каталог включая этот README ([secret-scan.json](secret-scan.json)).
- Коды комнат в трассах, логах и `demo.stdout.txt` — `<redacted>`. `loginid` CSV-профилировщика в `client.log` бенча — `<redacted>`.
- **Процессы.** Клиенты `Unmatched.exe` запускали только `render_bench.py` и `live_run.py`. Все завершились сами, PID — в `run-record.json` и `bench-run.json`. После этапа процессов Unmatched, `nvidia-smi` и сэмплеров нет.
- Бэкенд :3120 этого этапа и контейнеры `codex-s09-postgres` / `codex-s09-redis` остановлены в конце. Docker Desktop остановлен (`docker desktop stop`): его запускал этот этап.
- Чужие процессы не трогались: MCP `mcp-for-blender`, Chrome, Codex, `claude.exe`, ChatGPT, Steam.
- Локи сняты: пакетный 3 раза, GPU 4 раза.

## 7. Открытые вопросы

1. **Гейт приватности `run-combat-demo.ps1` сужен для всех режимов:** строки `PEND-RESOLVE sent` больше не проверяются на `card` (§1, п. 6). В P3 по умолчанию такие строки уже несли id карты (`BOOST_CHOICE`, `MOVE`) и проходили. Нужно решение оркестратора: оставить так или ограничить исключение режимом `-JoinerAttack`.
2. **`ranged`: одна пара на ход.** Цикл атаки, как и раньше, пробует карты только для первой выбранной пары. Если у Merlin нет подходящей карты, King Arthur в этот ход не атакует: на Marmoreal 21 выбор цели Merlin дал 8 атак. Улучшение — переходить к следующей паре без карты. Только opt-in, на доказательство не влияет.
3. **`ownresult` без автотеста:** это одно условие в обработчике результата GameMode, проверено живым прогоном (кадр хоста `rst=2366` / `2366`).
4. **Стоимость Translucency +0,08–0,12 мс** на обеих картах. Источник по объектам не изолирован (гипотеза — пятна контактной тени). Если нужен резерв, это первый кандидат на `-Bench` без `contactShadow` (предложение).
5. **Загрязнение замеров:** FPS и render thread бенча не сравнимы с P3 (§3.3), CPU во время бенча не записан. Чистый замер — на тихой машине или ПК D-07. ACC-022 этими числами не закрывается.
6. **Засвет восточного столбца Sarpedon** равномерный и сильный (dab ≈ 22). Нужно ли его ослаблять (интенсивность или радиус фонарей корпуса) — художественное решение пользователя.
7. **Короткие дуэли:** Sarpedon K3 закончилась на seq 40, в обеих по 4 манёвра. Доказательство (a) для ходов есть, но выборка меньше, чем в P3 (16–28 ходов).
8. Пробелы P4, которые требуют новых ассетов (3, 4, 6–9, 12), этим этапом не трогались.
