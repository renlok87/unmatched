# ENV-MAPS P3: packaged -Bench на оригинальных картах, производительность и кадры K1/K2 (2026-10-01)

**Статус: измерено** на dev-PC (RTX 4090, i9-13900F). Это не целевой ПК D-07, и машина не была полностью тихой (см. «Фон GPU»). ACC-022 этими числами не закрывается. Кадры технически сняты на эталоне рендера. Художественная приёмка здесь не выставляется: это решение пользователя.

Сцена бенча воспроизводится без бэкенда из фикстур `Config/Bench/S08Bench{Cobble,Marmoreal,Sarpedon}.json`: Medusa + 3 Harpy против King Arthur + Merlin. Флаги `-ArtPreview -ArtPreviewHeroesV2 -ArtPreviewDiorama`. Настройки рендера: High (`sg.* = 2`), SP 100, DX12/SM6 + Lumen, 1920×1080 offscreen. Базовая линия — Cobble 5×6 с подносом из прецедента GD-058, вариант `dx12-lumen-high-v2`.

## Сборка и данные

- Упакованный клиент Development из этапа PACKAGE: worktree `C:/tmp/wt-envmaps`, HEAD 9f1c66c4.
  - Внутренний `Unmatched/Binaries/Win64/Unmatched.exe`: sha256 `d0b49f8c3bbee39b59685756a8e5954e56c71b5458e386edcd38ae459c99057a`. Значение `exeSha256` во всех 12 `bench-run.json` совпадает с ним.
  - Пак `Unmatched-Windows.pak`: `17cb484f…a0d6`.
- Профили, layout и фикстуры читались **из пака**:
  - профили: `profilesSource=pak`, `profilesSha256=aae181a4…4230`;
  - layout Marmoreal: `envlayout … sha256=3794cddb…e51f source=pak`;
  - layout Sarpedon: `sha256=31edb81b…06ca source=pak`.

  Хэши равны файлам worktree.
- Фикстура карты передаётся как `-BenchFixture=../../../Unmatched/Config/Bench/S08Bench<Map>.json`: это относительный путь, клиент читает его из пака. В трассе: `BENCH scene fixture=S08BenchMarmoreal.json board=7x6 fighters=6 … profile=marmoreal-original` и `… S08BenchSarpedon.json board=9x6 …`.
- `/Game/EnvMaps/Data` (SDF, SpaceID) не куются по замыслу. В трассе `ARTPREVIEW map-image assets … boundBc=1 boundMask=1 sdf=-1 id=-1`, строки `missing` нет.
- Строк `Error:` / `Fatal` в логах клиентов нет (0 во всех 12).

## Команды

```
# GPU-токен взят 07:36:59, снят 08:14:31 (gpu-quiet/lock-*.txt)
# 9 прогонов без ограничения FPS, вперемешку r1: marmoreal, cobble, sarpedon; затем r2; затем r3
python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --name <cobble|marmoreal|sarpedon> --repeats <1|2|3> \
  --views K1+K1x0.65+K2x1.6+K2x2.5 --out C:/tmp/envmaps-research/p3/bench-runs \
  [--bench-fixture ../../../Unmatched/Config/Bench/S08Bench<Marmoreal|Sarpedon>.json]
# эффективные FPS одного клиента при ограничении 60 (как FrameRateLimit=60 по умолчанию), по 1 прогону
python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2-fps60 --name <board>-fps60 --repeats 1 \
  --views K1+K2x1.6 --measure 30 --out C:/tmp/envmaps-research/p3/bench-runs [--bench-fixture …]
python tools/art/render/render_bench.py summarize --out bench-summary.json <runs>/cobble <runs>/marmoreal <runs>/sarpedon
python C:/tmp/envmaps-research/p3/bench/analyze.py p3-bench-summary.json    # счётчики CSV, nvidia-smi в окне, Δ к Cobble
python tools/art/render_fingerprint.py check --trace runs/<board>/r1/bench.trace.log --shot <png>
```

Строка клиента (полная — `argv` в каждом `bench-run.json`):

```
Unmatched.exe /Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode -windowed -resx=1920 -resy=1080 -ForceRes -RenderOffScreen
  -ArtPreview -Bench -BenchOut=<run> -S08Trace=<run>\bench.trace.log -BenchViews=K1+K1x0.65+K2x1.6+K2x2.5
  -BenchWarmup=30 -BenchSettle=8 -BenchMeasure=20 -BenchCsv -csvGpuStats -abslog=<run>\client.log
  -S08RenderPreset=High -ArtPreviewHeroesV2 -ArtPreviewDiorama [-BenchFixture=…] -ExecCmds=DisableAllScreenMessages
```

- Прогон без ограничения длится 158,6–158,8 с, прогон с fps60 — 115,5–116,6 с.
- Все 12 прогонов: `exit 0`, `BENCH done`, тайм-аутов нет.
- Режим: `t.MaxFPS 0`, VSync 0, окно замера 20 с на вид. CSV-профилировщик собирает время GPU по проходам. После окна снимается один кадр ProfileGPU и один SHOT.

**Правки `tools/art/render/render_bench.py` на этом этапе:**
- `--bench-fixture` передаёт `-BenchFixture=` клиенту и записывается в `notes.benchFixture`;
- `--name` задаёт каталог вывода;
- тайм-аут прогона растёт с числом видов (раньше был рассчитан на 2 вида);
- `summarize` находит кадр вида с точкой: ключ кадра `K1x0p65`, вид в трассе `K1x0.65`. Раньше яркость таких видов не попадала в сводку.

`pytest tools/art/tests -k "bench or face_roi"`: 4 passed.

## Фон GPU и пометка загрязнения

| Момент | GPU nvidia-smi p50 / p95 | Потребители (pmon SM %) |
|---|---|---|
| 07:37, до замера (30 с) | 98 / 99 % | `WardogsClient-Win64-Shipping` (PID 37024, игра вне этой сессии) 83–98 %, `cmd.exe` 12–36 % |
| 07:38–07:42, ожидание (опрос раз в 60 с) | 98 → 20 % | в 07:42 игры среди процессов уже нет ([gpu-quiet/wait-quiet.log](gpu-quiet/wait-quiet.log)) |
| 07:42, базовая линия (30 с) | 30 / 32 %, max 39 % | `dwm.exe` 28–30 % ([gpu-quiet/quiet-baseline-30s.csv](gpu-quiet/quiet-baseline-30s.csv)) |
| 07:46–08:07, прогоны 2–9 из 9 (pmon каждые 5 с) | — | В 30 выборках из 192 посторонний процесс > 20 %: `claude.exe` (UI) до 37 %, `dwm.exe` до 32 %. Остальные ≤ 7 %: `chrome.exe`, ChatGPT, steamwebhelper. Других игр и рендеров нет ([gpu-quiet/pmon-summary.json](gpu-quiet/pmon-summary.json)) |

**Пометка: частично загрязнено фоном** (композитор `dwm.exe` и UI `claude.exe` до 37 % SM в отдельных выборках). Фон того же порядка, что в прецеденте GD-058: там было 25 %, `dwm` ≈ 23 %, `claude` ≈ 19 %. Время GPU нашего процесса (`RHIGetGPUFrameCycles`, CSV `GPUTime`) от фона почти не зависит: разброс по 3 повторам ≤ 0,06 мс. FPS без ограничения шумит сильнее (2–9 fps). В течение замеров игры `WardogsClient` не было. Лог pmon первого прогона (marmoreal r1, 07:43–07:46) не сохранился: файл перезаписан вторым запуском цепочки. Числа этого прогона совпадают с r2/r3 в пределах шума.

## Результаты: без ограничения FPS, 3 повтора

Среднее по 3 повторам, в скобках разброс (max − min). Кадр, GPU и render thread — из строки `BENCH measure` трассы. GPU CSV — среднее `GPUTime` CSV-профилировщика. Вызовы отрисовки, примитивы и свет — средние `RHI/DrawCalls`, `RHI/PrimitivesDrawn` и `LightCount/All` из CSV. nvidia-smi показывает долю времени занятости всей GPU вместе с фоном. Без ограничения кадры идут подряд, поэтому эта доля — не запас мощности. hitches — кадры > 50 мс, указан максимум по повторам.

| Доска | Вид | FPS | кадр avg / p95, мс | GPU avg (разброс) / p95, мс | render thread, мс | game thread, мс | GPU CSV, мс | вызовы отрисовки | примитивы, млн | свет | nvidia-smi p50, % | VRAM max, МиБ | hitches |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Cobble 5×6 | K1 | 241,2 (5,5) | 4,15 / 4,98 | 1,82 (0,01) / 1,89 | 4,14 | 1,12 | 1,823 | 213 | 0,85 | 2 | 89 | 4248 | 0 |
| Cobble 5×6 | K1x0,65 | 248,2 (8,9) | 4,03 / 4,92 | 1,74 (0,01) / 1,79 | 4,03 | 1,12 | 1,736 | 204 | 0,68 | 2 | 88 | 4245 | 0 |
| Cobble 5×6 | K2x1,6 | 235,1 (4,5) | 4,25 / 5,16 | 1,93 (0,01) / 2,15 | 4,25 | 1,13 | 1,930 | 284 | 0,93 | 2 | 90 | 4312 | 0 |
| Cobble 5×6 | K2x2,5 | 235,0 (2,3) | 4,25 / 5,18 | 2,07 (0,02) / 2,23 | 4,25 | 1,11 | 2,074 | 250 | 1,02 | 2 | 89 | 4312 | 0 |
| Marmoreal | K1 | 228,8 (7,0) | 4,37 / 5,45 | 2,28 (0,03) / 2,46 | 4,37 | 1,12 | 2,286 | 239 | 1,17 | 7 | 89 | 4406 | 0 |
| Marmoreal | K1x0,65 | 234,4 (5,8) | 4,27 / 5,17 | 2,19 (0,06) / 2,33 | 4,27 | 1,15 | 2,187 | 235 | 1,04 | 7 | 82 | 4446 | 0 |
| Marmoreal | K2x1,6 | 233,2 (2,7) | 4,29 / 5,17 | 2,21 (0,01) / 2,41 | 4,28 | 1,10 | 2,218 | 293 | 1,02 | 7 | 88 | 4373 | 0 |
| Marmoreal | K2x2,5 | 235,7 (2,9) | 4,24 / 5,09 | 2,23 (0,03) / 2,41 | 4,24 | 1,11 | 2,230 | 236 | 0,93 | 5 | 88 | 4374 | 0 |
| Sarpedon | K1 | 232,3 (4,3) | 4,30 / 5,38 | 2,24 (0,01) / 2,39 | 4,30 | 1,12 | 2,240 | 239 | 1,18 | 7 | 88 | 4315 | 0 |
| Sarpedon | K1x0,65 | 233,0 (2,2) | 4,29 / 5,27 | 2,17 (0,02) / 2,31 | 4,29 | 1,13 | 2,174 | 235 | 1,07 | 7 | 88 | 4318 | 0 |
| Sarpedon | K2x1,6 | 228,7 (6,0) | 4,37 / 5,48 | 2,14 (0,00) / 2,35 | 4,37 | 1,11 | 2,143 | 469 | 1,26 | 6 | 88 | 4379 | 0 |
| Sarpedon | K2x2,5 | 229,6 (5,0) | 4,36 / 5,46 | 2,17 (0,03) / 2,34 | 4,36 | 1,14 | 2,173 | 365 | 1,01 | 5 | 87 | 4382 | 0 |

**Свет.** Cobble: 1 ключ + 1 точка профиля `cobble-probe`. Карты: 1 ключ + 1 точка профиля + 5 точек layout. В трассе `combinedPoints=6 combinedBudgetOk=1`, тень отбрасывает только ключ. На K2 часть точек отсекается видом.

**Виды.** Виды названы одинаково, но камеры на досках разные. На картах K1 = 2340,2 uu (fit × 1,25), K1x0,65 = дальний предел 2880,2 uu, K2x1,6 = 1462,6 uu, K2x2,5 = 936,1 uu (фокус Medusa). На Cobble K1 = 1930,8 uu, K2x1,6 = 1206,7, K2x2,5 = 772,3.

### Карты против Cobble

Разница значима, если |Δ| > 2 × max(разброс).

| Карта, вид | GPU avg Cobble → карта, мс | Δ | Главные вклады Δ по CSV, мс | Δ FPS (порог) |
|---|---|---|---|---|
| Marmoreal K1 | 1,823 → 2,280 | **+0,457 (+25 %)**, значимо | RenderDeferredLighting +0,181, LumenReflections +0,072, Basepass +0,056, Lights +0,056 | −12,3 (14,0), не значимо |
| Marmoreal K1x0,65 | 1,737 → 2,187 | **+0,450 (+26 %)** | Basepass +0,045, LumenReflections +0,044, Lights +0,042, RenderDeferredLighting +0,039, ShadowDepths +0,023 | −13,9 (17,9), не значимо |
| Marmoreal K2x1,6 | 1,927 → 2,213 | **+0,286 (+15 %)** | RenderDeferredLighting +0,155, LumenReflections +0,048, Lights +0,045 | −1,8 (9,1), не значимо |
| Marmoreal K2x2,5 | 2,070 → 2,227 | **+0,157 (+8 %)** | RenderDeferredLighting +0,093, Lights +0,047, LumenReflections +0,033 | +0,7 (5,7), не значимо |
| Sarpedon K1 | 1,823 → 2,237 | **+0,414 (+23 %)** | RenderDeferredLighting +0,126, Lights +0,050, Basepass +0,042, LumenReflections +0,023 | −8,8 (10,9), не значимо |
| Sarpedon K1x0,65 | 1,737 → 2,170 | **+0,433 (+25 %)** | Unaccounted +0,050, Basepass +0,038, Lights +0,038, RenderDeferredLighting +0,036 | −15,2 (17,9), не значимо |
| Sarpedon K2x1,6 | 1,927 → 2,140 | **+0,213 (+11 %)** | RenderDeferredLighting +0,065, Lights +0,034, LumenSceneUpdate +0,021 | −6,4 (12,1), не значимо |
| Sarpedon K2x2,5 | 2,070 → 2,167 | **+0,097 (+5 %)** | RenderDeferredLighting +0,062, Lights +0,027, LumenSceneUpdate +0,022 | −5,4 (10,0), не значимо |

- **Стоимость окружения: +0,4–0,46 мс GPU на K1 (+23–26 %).** Главные вклады: освещение (6 точек вместо 1 и туман профиля), отражения Lumen и base pass (17–18 пропсов, земля, поднос T2). В одном кадре ProfileGPU работа GI/AO Lumen составляет: Cobble K1 0,92 мс, Marmoreal 1,49 мс, Sarpedon 1,36 мс (`bench-summary.json`, `derived.pgLumen`). Вызовы отрисовки на K1 выросли с 213 до 239, примитивы — с 0,85 до 1,17–1,18 млн. VRAM всей GPU выросла на 70–200 МиБ.
- **FPS без ограничения от карт значимо не меняется.** Кадр упирается в render thread: 4,2–4,4 мс при GPU 2,1–2,3 мс. Разница FPS к Cobble меньше порога шума.
- K1x0,65 Cobble нельзя напрямую сравнивать с K1x0,65 карт: на Cobble это дальний предел сетки, доска маленькая и вокруг чёрный фон. Δ на этом виде завышена.

## Эффективные FPS одного клиента при ограничении 60 (ACC-022: 1080p / 60 FPS, High)

Источник: [fps60-summary.json](fps60-summary.json). 1 прогон на доску, окно 30 с на вид, `-BenchFps=60` (t.MaxFPS 60, как `FrameRateLimit=60` по умолчанию).

| Доска | Вид | FPS (кадров) | кадр p95 / max, мс | GPU avg / p95, мс | render thread avg, мс | nvidia-smi p50 / p95, % (с фоном ~30 %) | VRAM max, МиБ | hitches |
|---|---|---|---|---|---|---|---|---|
| Cobble | K1 | 60,00 (1800) | 16,67 / 16,71 | 2,04 / 2,28 | 2,65 | 39 / 40 | 4100 | 0 |
| Cobble | K2x1,6 | 60,00 (1800) | 16,67 / 16,70 | 2,13 / 2,23 | 2,58 | 39 / 41 | 4163 | 0 |
| Marmoreal | K1 | 60,00 (1800) | 16,67 / 16,71 | 2,26 / 2,45 | 2,75 | 38 / 42 | 4159 | 0 |
| Marmoreal | K2x1,6 | 60,00 (1800) | 16,67 / 16,70 | 2,26 / 2,48 | 2,73 | 39 / 41 | 4223 | 0 |
| Sarpedon | K1 | 60,00 (1800) | 16,67 / 16,71 | 2,56 / 2,91 | 2,69 | 38 / 42 | 4163 | 0 |
| Sarpedon | K2x1,6 | 60,00 (1800) | 16,67 / 16,70 | 2,28 / 2,55 | 2,73 | 39 / 41 | 4225 | 0 |

На этом ПК обе карты держат 60,00 FPS на High при 1080p без провалов. GPU занимает 2,3–2,9 мс из бюджета 16,67 мс. **Это не закрытие ACC-022:** ПК не D-07, машина не тихая, пара клиентов по 30 FPS на картах будет на live-этапе.

## Кадры

Кадры сняты в тех же прогонах (r1), 1920×1080, по одному SHOT на вид после окна замера. RENDER-отпечаток `render_fingerprint.py check --shot`: exit 0, `reference: true`, причин нет, для всех 10 опубликованных кадров. Во всех 42 кадрах 12 прогонов `referenceCheck` равен `reference: true`.

| Доска | K1 | K1x0,65 | K2x1,6 (Medusa) | K2x2,5 (крупный план) |
|---|---|---|---|---|
| Marmoreal | [K1](frames/marmoreal/bench-K1-1920x1080.png) | [K1x0.65](frames/marmoreal/bench-K1x0p65-1920x1080.png) | [K2x1.6](frames/marmoreal/bench-K2x1p6-1920x1080.png) | [K2x2.5](frames/marmoreal/bench-K2x2p5-1920x1080.png) |
| Sarpedon | [K1](frames/sarpedon/bench-K1-1920x1080.png) | [K1x0.65](frames/sarpedon/bench-K1x0p65-1920x1080.png) | [K2x1.6](frames/sarpedon/bench-K2x1p6-1920x1080.png) | [K2x2.5](frames/sarpedon/bench-K2x2p5-1920x1080.png) |
| Cobble (база) | [K1](frames/cobble/bench-K1-1920x1080.png) | — | [K2x1.6](frames/cobble/bench-K2x1p6-1920x1080.png) | — |

Лист всех 12 видов r1: [contact-sheet-r1.jpg](contact-sheet-r1.jpg).

| Кадр | sha256 |
|---|---|
| marmoreal K1 | `bf643dc3918c6b87a152b8ce9d586799a83660c67ffa1617304d4f0cd293eb0e` |
| marmoreal K1x0p65 | `e5d638b13404f439508f85b00ab14adecccf94cd7f791fd4739bd52243243d4d` |
| marmoreal K2x1p6 | `276c63993a5d04130e2a06bcdbba336115af5999ff26492fdc311253b93df68e` |
| marmoreal K2x2p5 | `5365b997e044abbce46b02bbce874b479401d41be2087f25f44ab15118246a22` |
| sarpedon K1 | `edd47f36b6336e555dfaa79487101fc71975d47ab95eee66ae87f046d555e53a` |
| sarpedon K1x0p65 | `522803a6029e59afcbc13125e5d50e3b5009e910bd29f3498f83781897dc4c34` |
| sarpedon K2x1p6 | `d93f40f714e497619fb76d1ad95b8bf5ce7b0e90234dbd39d376b5b307144743` |
| sarpedon K2x2p5 | `6d523bdef1566aa0727dd1075e092eb948e0a9a6a4695e127b3bf1c02a795a06` |
| cobble K1 | `8b6fe1084824ff0989845f809a709cebdbc4605cab91fb8a1b6148e39b0b150c` |
| cobble K2x1p6 | `b15b5cdd42e65a75ef6924c6bcc691a36f60273304ae522fb7dd5757b6de8f75` |

- **Повторяемость.** Средняя яркость центра кадра различается между 3 повторами не более чем на 0,11 (0–255) на любом виде (`bench-summary.json`, `luma.center`).
- **Packaged = editor P2.** Те же виды P2 (некукнутый editor `-game`) сравнивались с packaged r1:
  - средняя яркость Y: Marmoreal K1 81,97 → 82,12, Sarpedon K1 61,91 → 61,98;
  - средняя абсолютная разница RGB 0,39–0,65, p95 |ΔY| ≤ 1,5 на всех 6 кадрах.

  Упакованный контент (карта, окружение, земля, туман, mapGrade) рендерится так же, как в редакторе.
- **K3 в бенче нет.** K3 — это кадры боя (прицел, урон, клипы), их снимает только живой прогон (`run-combat-demo.ps1`). Вместо него добавлен крупный план K2x2,5 на Medusa, как K2 2,5× в GD-058.
- Скриншоты содержат оригинальные карты, как и кадры P2 и `first-frames-2026-09-30`.

## Файлы

- `runs/<доска>/r{1,2,3}/` и `runs/<доска>-fps60/r1/`: `bench-run.json` (argv, хэши, сводки CSV, ProfileGPU, проверка эталона, яркость), `bench.trace.log`, `nvidia-smi.csv` (вся GPU, 500 мс), `client.log` (дампы ProfileGPU; `loginid` CSV-профилировщика заменён на `<redacted>`). PNG повторов r2/r3 и fps60 лежат вне git, их sha256 есть в `bench-run.json`.
- [bench-summary.json](bench-summary.json): `render_bench.py summarize`, проходы CSV и ProfileGPU, яркость. [p3-bench-summary.json](p3-bench-summary.json): таблицы выше, счётчики CSV, nvidia-smi в окне замера, Δ к Cobble с порогом 2 × шум. [fps60-summary.json](fps60-summary.json).
- [gpu-quiet/](gpu-quiet/): замеры до прогона и базовая линия (30 с), опрос ожидания, потребители, сводка pmon, время взятия и снятия токена.
- **Сырые CSV профилировщика** (42 файла, 338 МБ) лежат вне git: `C:/tmp/envmaps-research/p3/bench-csv/`. Их sha256 — в [bench-csv-SHA256SUMS.txt](bench-csv-SHA256SUMS.txt) и в `bench-run.json` → `csv[].sha256`. Рабочие копии: `C:/tmp/envmaps-research/p3/bench-runs/`.
- **Проверка секретов** по каталогу (JWT, URL postgres/redis, `DATABASE_URL`, password, e-mail, `code=`, `loginid`, а также значения PASS/SECRET/TOKEN/EMAIL/DATABASE/REDIS/KEY из `backend/.env`; сами значения не печатались): 0 совпадений. Бенч работает без бэкенда, учётных записей и комнат в нём нет.

## Процессы

- Клиенты `Unmatched.exe` запускал только `render_bench.py`, каждый завершился сам с exit 0. После этапа процессов `Unmatched*` и `nvidia-smi` нет.
- Фоновый `nvidia-smi pmon` этого этапа завершился вместе с цепочкой.
- Чужие процессы не трогались: игра `WardogsClient`, `dwm`, `claude.exe`, Docker, бэкенд :3120 (PID 56068 предыдущего этапа), MCP.
- Лок пакета не нужен: пересборки не было.

## Открытое

1. Пометка «частично загрязнено фоном» (dwm, UI claude.exe). Чистый замер — на тихой машине или на ПК D-07.
2. Стоимость окружения (+0,4–0,46 мс GPU на K1) — в основном точечный свет и Lumen. Бюджет пока не превышен: `combinedBudgetOk=1`, FPS ограничен render thread. Если понадобится резерв, первые кандидаты — радиусы и число точек layout. Это предложение, не решение.
3. Пара клиентов по 30 FPS на картах и K3 (бой) — следующий, live-этап.
