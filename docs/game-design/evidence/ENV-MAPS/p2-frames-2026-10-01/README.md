# ENV-MAPS P2: ночной свет диорам Marmoreal и Sarpedon (2026-10-01)

Статус: **калибровка света, не арт-приёмка** (профили `предложено`). Кадры сняты без бэкенда в режиме `-Bench` в редакторе в игровом режиме (`UnrealEditor.exe -game`, некукнутый контент worktree `C:/tmp/wt-envmaps`, ветка `feat/env-original-maps`), High, SP 100, DX12/SM6 + Lumen. Все 6 кадров на эталоне рендера (`render-fingerprint.json`: `reference: true`, причин нет).

Цель: диорамы читаются как концепты пользователя (`scraped-data/derived/concepts/env-v1/marmoreal-v1.png`, `sarpedon-v2.png`): мрачная лунная ночь (холодный сине-серый ключ с З–СЗ, низкий амбиент, тёмный фон с дымкой), тёплые пятна от фонарей, костров и портала, а круги, линии и цвета зон карты остаются читаемыми.

| Карта | K1 (2340 uu) | Отдаление 0,65× (2880 uu, дальний предел) | Приближение 1,6× на Medusa (1463 uu) |
|---|---|---|---|
| Marmoreal | [marmoreal/bench-K1-1920x1080.png](marmoreal/bench-K1-1920x1080.png) | [marmoreal/bench-K1x0p65-1920x1080.png](marmoreal/bench-K1x0p65-1920x1080.png) | [marmoreal/bench-K2x1p6-1920x1080.png](marmoreal/bench-K2x1p6-1920x1080.png) |
| Sarpedon | [sarpedon/bench-K1-1920x1080.png](sarpedon/bench-K1-1920x1080.png) | [sarpedon/bench-K1x0p65-1920x1080.png](sarpedon/bench-K1x0p65-1920x1080.png) | [sarpedon/bench-K2x1p6-1920x1080.png](sarpedon/bench-K2x1p6-1920x1080.png) |

[before-after-K1.jpg](before-after-K1.jpg): K1 до (кадры интеграции P2, 2026-10-01 00:34) и после. Сравнение с концептами лежит вне git (`C:/tmp/envmaps-research/p2/light/concept-vs-final-K1x0p65.jpg`, `montage-final.jpg`): концепты содержат оригинальные карты (ENV-U3/U7).

## Что изменено

**Профили света** `unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json`, revision 8 → 9, заметка `nightCalibrationNoteRev9`. Профили `marmoreal-night` и `sarpedon-night` (остальные профили не тронуты):

| Параметр | Было (rev 8) | Стало (rev 9) |
|---|---|---|
| Ключ (directional) | 3,0 лк, (0,62; 0,70; 0,90) | 3,5 лк, (0,62; 0,72; 0,95) / Sarpedon (0,60; 0,71; 0,97); поворот (-55, 30, 0) без изменений (закреплён тестом), это свет с З–СЗ |
| Небо (SkyLight) | 12,5 / 13,0 | 3,0, холодный (0,60; 0,70; 1,0) / (0,58; 0,70; 1,0) |
| Точка профиля | moon-pool 60 кд r420 / water-rim 70 кд r440 у края карты | `moon-pool` 260 кд на 750 uu над центром карты, r1250, (0,82; 0,88; 1,0): карта светлее окружения |
| `fog` (новый блок) | нет, фон чёрный | цвет (0,20; 0,255; 0,46), density 0,32, falloff 0,2, heightZ −400, start 2900 uu, end 6000 uu, maxOpacity 1 |
| `mapGrade` (новый блок) | значения MI: NightEV −0,7, NightSaturation 0,7, Lift 0,35, тинт (0,93; 1,0; 1,16) | NightEV −0,35, NightSaturation 0,75, Lift 1,5, тинт (0,97; 1,0; 1,05) |
| Экспозиция | EV100 2,05 fixed | без изменений |

**Окружение** (`Config/ArtBoards/EnvLayouts/<map>.layout.json`, точки без теней; профиль + layout = 1 ключ + 6 точек на каждой карте):

- Marmoreal: 4 фонаря подняты над колпаком (z 70,1 → 105), #FFB870 → #FFA552, 45/40 → 60/55 кд, r 320/300 → 480/460. `portal-glow` #FFC98A → #FFB066, r 360 → 380, 55 кд.
- Sarpedon: костры подняты (z 28/25 → 60), 80/60 → 55/45 кд, r 380/330 → 460/420. Огни корпуса #FFA552, 45/40 → 70/65 кд, r 340/320 → 480/460. Новая 6-я точка `ship-lantern-stern` у южного конца `hull-e2` (690, −30, 140), 50 кд, r440: тёплое пятно на палубе ЮВ.

**Земля** (`art/pipeline-candidates/ASSET-ENV-KIT-001/ground/ground-params.json`, импорт `ue_import_env_ground.py`, MI вне git): grade `ev` −0,7 → −1,0 на обеих картах; Marmoreal L3 (мраморная мостовая) tint (0,8; 0,82; 0,88) → (0,48; 0,5; 0,56); Sarpedon L1 (песок) tint (0,78; 0,64; 0,46) → (0,62; 0,51; 0,37). Так закрыт пункт интеграции «мостовая светлее карты» (paving/map было 1,31).

**Код** (новые необязательные блоки профиля света; оба проверяются при загрузке, сломанный блок отклоняет профиль):

- `S08BoardArt.h/.cpp`: `FS08FogSpec` и `FS08MapGradeSpec`, разбор `fog` и `mapGrade` в `ParseRenderBlocks`; имена параметров M_MapBoard в `S08MapSurfaceSpec`.
- `S08BoardActor.cpp/.h`: `ApplyArtLights` создаёт один `AExponentialHeightFog` вместе со светом (без volumetric fog; Lumen, scalability и SP не трогаются; уничтожается вместе со светом). `ApplyMapGrade` ставит NightEV, NightSaturation, Lift и NightTint на MID карты map-image доски. Строки трассы: `ARTPREVIEW fog ...` и `ARTPREVIEW map grade ... source=profile|mi`.
- `S08Render.h`: `FS08AppliedRender::bFog`. В строку RENDER туман не входит, `render-reference.json` не менялся.
- Тесты: `BoardArt.Parser` (разбор и 7 случаев отказа), `BoardArt.MapProfiles` (у обеих ночных профилей есть туман со start ≥ 2800 и mapGrade с Lift > 0,35), `BoardArt.MapActor` (MID рендерит Lift и NightEV профиля, туман создан).
- `tools/art/art_board_fixtures.py`: `check_night_blocks` с теми же диапазонами; тест `test_profile_night_blocks`.

Почему туман: без сцены вокруг диорамы фон оставался чёрным цветом очистки. `endDistanceUU` ограничивает горизонтальную длину луча, поэтому крутые лучи внизу кадра набирают больше дымки: верх фона тёмный, низ туманнее. `startDistanceUU` 2900 больше самой дальней точки подноса в K1 (~2800 uu), так что доска в K1 и K2 вне тумана. При 0,65× дальний край подноса (до 3313 uu) получает лёгкую дымку.

## Команды

```
# одна итерация (оба кадра последовательно, GPU-лок C:/tmp/unmatched-gpu.lock), замеры, монтаж
sh C:/tmp/envmaps-research/p2/light/iter.sh <tag> [m s]       # BENCH_WARMUP=25 в итерациях, 60 в финале
python C:/tmp/envmaps-research/p2/light/apply.py specs/<it>.spec.json
node C:/tmp/envmaps-research/p2/light/run-ue-cmd.cjs ground-<it> "<wt>/tools/art/env_kit/ue_import_env_ground.py" -ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False
python C:/tmp/envmaps-research/p2/light/measure.py frames runs/<tag>-<m|s> [--json out]
python C:/tmp/envmaps-research/p2/light/measure.py concept
```

Строка клиента (полная: `<map>/cmdline.txt`):

```
UnrealEditor.exe <wt>\unreal\Unmatched\Unmatched.uproject /Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode
  -game -windowed -resx=1920 -resy=1080 -ForceRes -RenderOffScreen -nosplash -unattended -NoSound
  -ArtPreview -ArtPreviewDiorama -ArtPreviewHeroesV2
  -Bench -BenchFixture=<wt>\unreal\Unmatched\Config\Bench\S08Bench<Map>.json -BenchOut=<dir>
  -BenchViews=K1+K1x0.65+K2x1.6 -BenchWarmup=60 -BenchSettle=6 -BenchMeasure=5 -BenchNoProfileGPU -BenchFps=60
  -S08RenderPreset=High -S08Trace=<dir>\bench.trace.log -abslog=<dir>\client.log -ExecCmds=DisableAllScreenMessages
```

Финальные прогоны длились 128,7 и 127,8 с и завершились сами с EXIT=0 (`<map>/exit.txt`). Это второй финальный прогон: первый (те же значения света) был до дописывания заметок в layout; его кадры совпали с этими в пределах 0,1 яркости, они лежат вне git в `runs/final0-*`.

## Строки трассы (Marmoreal; Sarpedon в `sarpedon/bench.trace.log`)

```
ARTPREVIEW light profile=marmoreal-night name=key role=key kind=directional at=(-350,-150,600) intensity=3.5 units=lux radius=0 color=(0.62,0.72,0.95) shadow=1
ARTPREVIEW light profile=marmoreal-night name=moon-pool role=cool kind=point at=(0,0,750) intensity=260 units=candelas radius=1250 color=(0.82,0.88,1.00) shadow=0
ARTPREVIEW sky profile=marmoreal-night cubemap=/Game/S08/Render/TC_S08_AmbientDome loaded=1 spawned=1 intensity=3 color=(0.60,0.70,1.00) lowerBlack=0
ARTPREVIEW fog profile=marmoreal-night spawned=1 color=(0.2000,0.2550,0.4600) density=0.32 falloff=0.2 heightZ=-400 start=2900 end=6000 maxOpacity=1.00 volumetric=0
ARTPREVIEW exposure profile=marmoreal-night method=histogram-fixed min=4.14106 max=4.14106 bias=0.000 ev100=2.05 volume=1
ARTPREVIEW lights applied profile=marmoreal-night directional=1 shadow=1 points=1 pointShadows=0 budgetOk=1
ARTPREVIEW map grade profile=marmoreal-night source=profile nightEV=-0.35 nightSaturation=0.75 lift=1.50 nightTint=(0.9700,1.0000,1.0500)
ARTPREVIEW envlayout light id=lamp-nw kind=point at=(-520.0,-365.0,105.0) intensity=60 units=candelas radius=480 color=#FFA552 shadow=0
ARTPREVIEW envlayout ground map=marmoreal mode=runtime strips=4 material=MI_EnvGround_Marmoreal z=-1.0 outer=(-780.0,-515.0)..(780.0,425.0) hole=(-467.7,-310.7)..(467.7,310.7) splatRect=(-820.0,-560.0)..(820.0,470.0) splatCovers=1 areaUU2=885246 status=ok
ARTPREVIEW envlayout map=marmoreal props=17 lights=5 missingMeshes=0 ... intrusions=0 outsideTray=0 outsideKit=0 shadowCasters=17 profilePoints=1 combinedPoints=6 combinedBudgetOk=1 ... sha256=3794cddb4d27f63d690320395502bdc5dee3e42576a12daa51231f5c2ce3e51f source=pak status=ok
ARTPREVIEW envlayout tray map=marmoreal source=layout outerHalf=780.0x470.0 offsetY=-45.0 frameHalf=469.7x312.7 mesh=T2 t2Top=780.0x470.0 mismatchUU=0.0
ARTPREVIEW diorama tray=/Game/PipelineCandidates/TableBase/T2/SM_TableBase_T2.SM_TableBase_T2 mi=MI_TableBase_T2 surface=map-image yaw=0.0 scale=1.000x1.000x1.000 ... kind=T2 ... offset=(0.0,-45.0) source=layout mismatchUU=0.0 match=1
CAMERA extents source=map-image half=445.7x288.7 dist=2340.2 fit=1872.2 k1Mul=1.250
SHOT camera dist=2340.2 target=2340.2 overview=2340.2 errPct=0.000 focusErr=0.00 settled=1 zoom=1.00
BENCH view=K1x0.65 zoom-out wanted=0.65 target=2880.2 zoom=0.81 limit=far
SHOT camera dist=1462.6 target=1462.6 overview=2340.2 errPct=0.000 focusErr=0.00 settled=1 zoom=1.60
RENDER tag=SHOT rhi=D3D12 featureLevel=SM6 shaderPlatform=PCD3D_SM6 lumenPlatform=1 gi=lumen ... refl=lumen ... sg.res=100 ... preset=High screenPct=100.0 ... exposure=fixed-histogram expMin=4.14106 expMax=4.14106 expBias=0.000 ev100=2.05 lightUnits=candelas sky=1 skyIntensity=3.000 keyShadow=csm-3600uu-2c-contact0.000 shadowCasters=1 profile=marmoreal-night profilesSha256=aae181a4e6122bbe6f49a0f11122caf379c91b78f20b97140f96277038744230 profilesSource=pak legacyRender=0 ... viewport=1920x1080 reference=1
```

Sarpedon: `envlayout map=sarpedon props=18 lights=5 ... profilePoints=1 combinedPoints=6 combinedBudgetOk=1 ... sha256=31edb81b83780d354912117d69ac935912913a718acf486168d9081b26b006ca`; лучи огней `campfire-nw` (−548, −352, 60) 55 кд, `campfire-w` 45 кд, `ship-lantern-n/-s/-stern` 70/65/50 кд. sha256 профилей и обоих layout в трассе равны файлам worktree.

## Замеры

`measure.py`: ROI проецируются камерой S08 из трассы (`SHOT ctx`, HFOV 35°). Карта = прямоугольник карты с отступом 8 uu; окружение = верх подноса минус рамка; фон = вне оболочки подноса (z до 260) на 0,65×; круги = 48 лучей на пространство (заливка 0,45–0,75 R, контур 0,94–1,06 R минимум по лучу, снаружи 1,2–1,4 R), в L* CIELAB. У концептов ROI заданы вручную (грубая оценка). Y = среднее Rec.709 по sRGB 0–255. Полные числа: `<map>/measure.json`.

| Кадр | Карта Y | Окружение Y | окр./карта | Фон Y / b* (0,65×) | b* карты | b* окр. / тёплые | Край круга ΔL* (p10) | Заливка−снаружи ΔL* | C* заливки |
|---|---|---|---|---|---|---|---|---|---|
| Marmoreal до (it0) | 145,8 | 134,6 | 0,92 | 0,1 / 0 | −4,4 | 1,2 / 0,02 | 34,6 (25,6) | 11,3 | 16,1 |
| Marmoreal после | 115,3 | 68,4 | 0,59 | 32,3 / −14,9 | −2,7 | 3,8 / 0,15 | 36,1 (26,2) | 15,2 | 19,9 |
| концепт marmoreal-v1 | 115,0 | 74,8 | 0,65 | 29,4 / −14,6 | −0,2 | 1,9 / 0,19 | – | – | – |
| Sarpedon до (it0) | 142,0 | 91,6 | 0,65 | 0,1 / 0 | −0,8 | 6,4 / 0,08 | 32,1 (26,2) | 8,4 | 22,3 |
| Sarpedon после | 104,8 | 41,2 | 0,39 | 32,3 / −14,9 | 0,0 | 6,4 / 0,08 | 33,7 (26,4) | 19,2 | 25,5 |
| концепт sarpedon-v2 | 104,9 | 40,2 | 0,38 | 29,8 / −16,7 | 6,4 | 8,6 / 0,14 | – | – | – |

- Яркость карты совпала с концептами (±0,5), окружение темнее карты как в концепте (0,59 против 0,65 и 0,39 против 0,38), фон стал тёмно-синей дымкой (Y 32, b* −15 против 29–30 и −15…−17).
- Читаемость карты не упала, а выросла: контраст контура круга ΔL* 34,6 → 36,1 и 32,1 → 33,7, отрыв заливки от рисунка вокруг 11,3 → 15,2 и 8,4 → 19,2, насыщенность зон C* 16 → 20 и 22 → 26. Lift 1,5 внутри игровой маски держит круги при тёмном свете.
- Тёплые пятна есть на обеих картах, но тёплых пикселей в окружении меньше, чем в концептах (0,15 против 0,19; 0,08 против 0,14).

Лог 7 итераций (что менялось и замеры каждой): `C:/tmp/envmaps-research/p2/light/log.md`, спеки `specs/it*.spec.json`, кадры `runs/`, монтажи `montage-it*.jpg`.

## Проверки

- Сборки `-NoXGE -MaxParallelActions=6`: UnrealEditor e1 (17 действий) и e2 (4 действия, только тесты), оба «Result: Succeeded», игровая цель Unmatched g1 (16 действий, `Link [x64] Unmatched.exe`, «Result: Succeeded»). Ошибок нет; предупреждения только старые C4996 `AddInstanceWorldSpace` в S08BoardActor.cpp (строки 1136 и 1153). Логи: `C:/tmp/envmaps-research/p2/light/build/`.
- Автотесты `Unmatched.S08+Unmatched.S09+Unmatched.S10`: найдено 213, прошло 213, EXIT CODE 0 (`C:/tmp/envmaps-research/p2/light/tests/r1-all.*`). Предупреждений LogJson 558, как в прогоне интеграции.
- Python: `tools/art/tests` 210 passed + 69 subtests; `map_surface` 16 passed; `layout_check.py` EXIT 0 (обе карты OK, старое WARN `hull-e1` 20 uu от края подноса), self-test 21/21; `ground_splat.py --check` и `ue_import_env_ground.py --check` ok; импорт земли `ENVGROUND-IMPORT-RESULT ok` (0 ошибок, 0 предупреждений).
- `render_fingerprint.py check --shot` для всех 6 кадров: exit 0, `reference: true`.

## Известные пробелы

- **Контровой свет.** Поворот ключа закреплён на (−55, 30, 0) тестом `BoardArt.Shipped` и правилом теней `layout_check.py`. Свет с З–СЗ даёт боковой рисующий свет слева сверху, но не настоящий контур сзади. Более низкий или задний ключ потребует решения и правки теста, правила теней и `k1_mock.KEY_LIGHT_ROT`.
- **Свечение луны.** Туман даёт только вертикальный градиент фона; диска луны и ореола нет (камера не смотрит в небо, directional inscattering не используется).
- **Отличия контента, а не света:** вишни насыщенно-малиновые (материал env kit), у Sarpedon нет фонарей на столбах, бочек и ящиков концепта, песок и галька на севере под луной серые, скала подноса без мха и лепестков. Подписи HUD на светлых кругах в K2 малоконтрастны (UMG).
- **Моки K1** (`k1_mock.py`, `manifest.<map>.json` k1.grade_b_c) по-прежнему считают грейд MI (−0,7 / 0,7 / 0,35); в игре его заменяет `mapGrade` профиля.
- **Производительность не мерилась.** Это некукнутый editor `-game`. В финальных прогонах было 9,9 и 9,6 fps при gpuMs 2,5 и 2,4 и renderMs ~100: с ~01:22 UTC видеокарту грузил процесс вне этого прогона (после прогонов nvidia-smi: 99 %, 14,3 ГБ, процессов UE этого прогона нет). Итерации с тем же туманом до этого шли 46–60 fps при renderMs ~5. На кадры это не влияет: камера в каждом кадре settled=1, замеры совпали с итерациями. Мерить нужно `tools/art/render/render_bench.py` (упакованный `-Bench`, с `-BenchFixture` карт).
- **Не сделано:** упаковка (AExponentialHeightFog — класс движка, отдельного cook не требует), живой прогон с двумя клиентами.
- **Для коммита:** `ground-params.json` лежит в неотслеживаемом каталоге `art/pipeline-candidates/ASSET-ENV-KIT-001/ground/`; MI земли и карт — в gitignored Content. Скриншоты содержат оригинальную карту, как и кадры `first-frames-2026-09-30`.
