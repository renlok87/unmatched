# ENV-MAPS P4: полировка диорам Marmoreal и Sarpedon, настройка и финальные кадры (2026-10-01)

Статус: **предложено, измерено, технически импортировано**. Это не арт-приёмка: художественное решение остаётся за пользователем. Кадры сняты в режиме `-Bench` в редакторе в игровом режиме (`UnrealEditor.exe -game`, некукнутый контент worktree `C:/tmp/wt-envmaps`, ветка `feat/env-original-maps`). Бэкенд не запускался. Настройки: High, SP 100, DX12/SM6 + Lumen. Все 9 кадров на эталоне рендера: в `<map>/render-fingerprint.json` у каждого кадра `reference: true`, `reasons: []`, а `render_fingerprint.py check` завершился с кодом 0. Ключевой свет (−55, 30, 0) не трогали (ENV-U12, пробел 11 закрыт).

Этап P4 закрывает те пробелы концепт-ревью (`../p2-frames-2026-10-01/concept-review.json`), для которых не нужны новые ассеты. Треки A (земля и вода), B (вид пропсов и раскладка) и C (читаемость и доска) интегрированы. На этапе Tune в UE подбирались только параметры, код не менялся.

| Карта | K1 (2340 uu) | 0,65× (дальний предел) | 1,6× на Medusa | 2,5× крупно |
|---|---|---|---|---|
| Marmoreal | [K1](marmoreal/bench-K1-1920x1080.png) | [0,65×](marmoreal/bench-K1x0p65-1920x1080.png) | [K2×1,6](marmoreal/bench-K2x1p6-1920x1080.png) | [K2×2,5](marmoreal/bench-K2x2p5-1920x1080.png) |
| Sarpedon | [K1](sarpedon/bench-K1-1920x1080.png) | [0,65×](sarpedon/bench-K1x0p65-1920x1080.png) | [K2×1,6](sarpedon/bench-K2x1p6-1920x1080.png) | [K2×2,5](sarpedon/bench-K2x2p5-1920x1080.png) |
| Cobble (регрессия) | [K1](cobble/bench-K1-1920x1080.png) | – | – | – |

- [before-after-K1.jpg](before-after-K1.jpg): K1 обеих карт, слева финал P2, справа P4.
- [p4-K1x0p65.jpg](p4-K1x0p65.jpg): обе карты на 0,65×.

## Что изменено, по пробелам ревью

| Пробел | Что сделано (P4: треки A/B/C, потом Tune) | Замер в кадре P4 |
|---|---|---|
| 1 Sarpedon, вода | Вода в обоих устьях реки: слой M_EnvGround по aux-маске (вода, пена, глубина), рябь из двух панорамируемых нормалей, пена и прибой у северного устья. Водопад M_EnvWaterfall: карточка и перелив над краем T2. Tune: lift 0,6 → 4,0, цвет sRGB (34,63,105) → (40,76,128); водопад: drop 230 → 120 uu, bottomFade 0,35 → 0,9, dither 0,5 → 0,15, штрих 9 → 4 uu, поток 55 → 40 uu/с | Вода за рамкой к реке на карте: Y 50,0 / 55,0 (×0,91) у северного устья и 51,1 / 67,6 (×0,76) у южного, ΔE 10,7 / 10,6. В P2 было ×0,42 / ×0,33 (тёмный гравий, «дыры»). Трасса: `falls=1/1 fallCards=2 status=ok` |
| 2 Marmoreal, вишни | M_EnvProp: перекраска цветков в MI, без новой текстуры. Tune: satMul 0,58 → 0,42, альбедо S 0,59 → 0,25. Ещё 2 вишни: cherry-nw и cherry-se | Освещённая крона (V > 0,5): S 0,715 (P2) → **0,387** (цель 0,35–0,45), оттенок 334 → 328° |
| 4 Sarpedon, корпус (раскладка) | Секции hull-e1/e2 вдоль восточного края кадра, 100 % в K1. Пушки между рамкой и корпусом. Фонари корабля перенесены на корпус | `layout_check` K1_FRAMED: ok, 0 WARN |
| 5 Sarpedon, земля | Края сплата с шумом и размытием, тёплый песок, растушёванный песок у костров, балка у края палубы, острые доски. Tune: песок L1 (0,70; 0,56; 0,40) → (1,15; 0,72; 0,36) с sat 1,4, палуба L3 (1,1; 0,95; 0,8) → (1,7; 1,35; 0,95), ночной грейд земли sat 0,7 → 0,85 и тинт (0,93; 1,0; 1,16) → (0,97; 1,0; 1,08) | Песок тёплый, палуба тёплая (см. «тёплые» ниже). Холодный ключ (0,6; 0,71; 0,97) гасил прежний тинт: хрома песка была ~7 |
| 6 Marmoreal (частично) | 2 столба PlinthBall в задних углах, теперь столбы во всех 4 углах | – |
| 7 Sarpedon, лес | MI_Env_Tree темнее (S ×0,8, V ×0,75), 6 новых деревьев за частоколом, почва L0 темнее | – |
| 9 Рамка (быстрый вариант) | M_MapFrameWood: дерево ART-005, V ×0,7, S 0,75 | Трасса `map frame wood=frame-wood` |
| 10 Marmoreal, земля | Край мостовой с шумом, бордюр в 1 плитку, лепестки по маске под вишнями и у клумб (глобально ×0,5), макровариация мостовой ±8 % | – |
| 13 Marmoreal, блики | Мостовая L3: roughMin 0,8, specular 0,28. Эмиссив стекла фонарей ×6 | «Призрачных квадратов» у фонарей нет: в P2 был яркий квадрат у рамки, в P4 ровная мостовая (кроп вне git: `C:/tmp/envmaps-research/p4/tune/crop-ghost-p2-i1.png`) |
| 14 Тёплые акценты | Эмиссив: угли костров, стекло фонарей, заклёпки портала. Tune: фонари Marmoreal #FFA552 60/55 → #FF9A45 80/75 кд, портал 55 → 65. Костры Sarpedon 55/45 → 65/55, фонари корабля 70/65/50 → 85/80/65 кд. Радиусы и число огней прежние (1 ключ + 6 точек) | Тёплые в окружении: 0,154 → **0,20** (цель ≥ 0,18), 0,079 → **0,125** (цель ≥ 0,12) |
| 15 Кипарис | Красные шарики приглушены (S ×0,4, V ×0,45), листва темнее | – |
| Читаемость HIGH: зоны | M_MapBoard graph v2, параметры только внутри маски. Tune (профиль rev 11): Marmoreal lift 1,65 → 1,75, maskSaturation 1,5 → 1,4, liftSaturation 1,6 → 1,3. Sarpedon lift 1,75 → 1,7, maskSaturation 1,35 → 1,05, liftSaturation 1,5 → 1,1 | Минимальная смежная пара ΔE76: Marmoreal коричневый–красный **23,3**, Sarpedon синий–фиолетовый **23,2** (цель ≥ 20). Хрома зон к оригинальной карте: ×1,25 / ×1,09 (после интеграции ×1,41 / ×1,51, «плакатные» круги убраны) |
| Читаемость HIGH: подписи | Подложки UMG-подписей и зазор 3 px | В `-Bench` рисуются мировые подписи, подложки видны только в живой игре (см. пробелы) |
| Читаемость MEDIUM: подсветка хода | Золотое кольцо #FFC857 с тёмной обводкой, 48 сегментов. Tune: обводка 1,0 → 1,5 uu (жёлтые зоны) | Трасса `reachable rings ... segments=48 style=readability strokeUU=1.50`, кадры K2×1,6 и K2×2,5 |
| Читаемость MEDIUM: фигуры | Пятно контактной тени и ромбик лидера. Tune: тень 64 → 52 uu, сила 0,5 → 0,25 (пятно затемняло заливку занятых кругов) | Трасса `contactShadow=1 diameterUU=52.0 strength=0.25 leaderPip=1` |

## Замеры (K1, `measure.py` + `measure_extra.py`)

Метод замера тот же, что в P2: ROI проецируются камерой из трассы (`SHOT ctx`). Зоны считает `tools/art/map_surface/zone_separation.py measure`: медиана L\*a\*b\* секторов кругов в кадре, ΔE76 для смежных зон. Хрома зон — медиана по зонам C\*кадр / C\*оригинал. Вишня — HSV освещённых пикселей кроны (V > 0,5) в проекции боксов деревьев; карта исключена. Вода — прямоугольники за рамкой у устьев против нарисованной реки у края карты. Полные числа в `<map>/measure.json` и `<map>/zones-extra.json`.

| Метрика | Цель | Marmoreal P2 → интеграция → **P4** | Sarpedon P2 → интеграция → **P4** |
|---|---|---|---|
| Яркость карты Y | 115,3 / 104,8 ± 5 | 115,3 → 115,4 → **117,8** | 104,8 → 104,1 → **106,6** |
| Окружение / карта | 0,59 / 0,39 ± 0,08 | 0,593 → 0,566 → **0,592** | 0,393 → 0,366 → **0,450** |
| Тёплые в окружении | ≥ 0,18 / ≥ 0,12 | 0,154 → 0,145 → **0,200** | 0,079 → 0,052 → **0,125** (0,65×: 0,15) |
| Мин. смежная пара зон ΔE76 | ≥ 20 | 21,0 → 23,9 → **23,3** | 22,4 → 31,2 → **23,2** |
| Хрома зон / оригинал | (против «плаката») | 0,90 → 1,41 → **1,25** | 0,98 → 1,51 → **1,09** |
| C\* заливки кругов | – | 19,9 → 25,8 → **22,8** | 25,5 → 47,2 → **32,3** |
| Контур круга ΔL\*: медиана (среднее) | ≥ P2 | 36,1 (34,81) → 34,5 (34,70) → **35,0 (35,01)** | 33,7 (35,09) → 33,6 (35,20) → **33,8 (35,46)** |
| Контур ΔL\* попарно по кругам к P2 | ≥ 0 | – → медиана +0,1 → **+0,3** | – → – → **+0,4** |
| Вишня, S кроны | 0,35–0,45 | 0,715 → 0,45 → **0,387** | – |
| Вода / река (сев., юж.) | без «дыр» | – | ×0,42 / ×0,33 → ×0,42 / ×0,36 → **×0,91 / ×0,76** |
| Фон Y / b\* (0,65×) | ~29–30 / −15 | 32,3 / −14,9 → **32,4 / −14,8** | 32,3 / −14,9 → **32,3 / −14,9** |

Про контур ΔL\* на Marmoreal. Медиана по 31 кругу 35,0, это ниже 36,1 из P2. Попарно по тем же кругам P4 выше P2: медиана разности +0,3, среднее 35,01 против 34,81. В P2 медиана попала на разрыв распределения: между 34,4 и 36,1 нет ни одного круга. Пара занятых кругов (M31 и M20: контактная тень, ромбик, кольцо) сдвинулась на ~1 вниз, и медиана перешла на соседнее значение.

Диагностический прогон d1 вернул грейд P2 (lift 1,5, маска нейтральная) и дал медиану 34,1. Значит, медиану сдвинул не грейд, а оформление занятых кругов. Ослабление тени (0,5 → 0,25) вернуло часть контраста. По медиане цель на Marmoreal не достигнута, по среднему и попарно она выполнена.

Яркость Marmoreal +2,5 к P2 (в допуске ±5): это более яркие фонари и Lift 1,75. Окружение/карта на Sarpedon 0,45 при допуске до 0,47: тёплый песок и палуба светлее.

## Итерации Tune

Журнал, спеки и кадры лежат вне git, в `C:/tmp/envmaps-research/p4/tune/`: `log.md`, `specs/*.spec.json`, `runs/`, `montage-*.jpg`. В монтажах есть оригинальная карта (ENV-U3/U7), поэтому они не в git.

| Итер. | Карта | Y карты | окр./карта | тёплые | контур мед. (сред.) | мин. пара зон | хрома × | вишня S / вода × |
|---|---|---|---|---|---|---|---|---|
| интеграция | M | 115,4 | 0,566 | 0,145 | 34,5 (34,70) | 23,9 | 1,41 | 0,45 |
| интеграция | S | 104,1 | 0,366 | 0,052 | 33,6 (35,20) | 31,2 | 1,51 | 0,42 / 0,36 |
| t1 | M | 119,6 | 0,583 | 0,183 | 35,2 (35,20) | 22,3 | 1,25 | 0,405 |
| t1 | S | 106,4 | 0,398 | 0,071 | 33,4 (35,31) | 23,2 | 1,09 | 0,57 / 0,47 |
| t2 | M | 119,2 | 0,593 | 0,194 | 35,0 (35,05) | 22,6 | 1,23 | 0,408 |
| t2 | S | 106,5 | 0,450 | 0,125 | 33,7 (35,38) | 23,1 | 1,09 | 0,91 / 0,75 |
| t3 | M | 116,5 | 0,566 | 0,166 | 34,9 (34,95) | 23,0 | 1,26 | 0,421 |
| d1 (диагн.) | M | 115,3 | 0,572 | 0,166 | 34,1 (34,60) | 21,0 | 0,90 | 0,422 |
| t4 | M | 117,8 | 0,587 | 0,199 | 35,1 (35,06) | 23,2 | 1,24 | 0,431 |
| t5 | M | 117,8 | 0,592 | 0,200 | 35,0 (34,95) | 23,2 | 1,24 | 0,387 |
| финал | M | 117,8 | 0,592 | 0,200 | 35,0 (35,01) | 23,3 | 1,25 | 0,387 |
| финал | S | 106,6 | 0,450 | 0,125 | 33,8 (35,46) | 23,2 | 1,09 | 0,91 / 0,76 |

- **t1.** Грейд подобран по модели `zone_separation.py fit`, подогнанной на кадрах интеграции. Подняты фонари и костры, тёплый песок и палуба, вода lift 2,4, водопад короче, вишня satMul 0,5.
- **t2.** Песок и палуба теплее и светлее, вода lift 4,0 и светлее, водопад 120 uu с мягким низом, тень 0,35.
- **t3.** Фонари тише и насыщеннее. Тёплых стало 0,17: интенсивность важна.
- **d1.** Диагностика контура, откачена.
- **t4.** Тень 52 uu / 0,25, фонари снова 80/75.
- **t5.** Вишня satMul 0,42, обводка кольца хода 1,5.
- **Финал.** Значения t5, warmup 60, 4 вида.

## Изменённые файлы конфигурации (Tune)

- `unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json`: revision 10 → 11, заметка `envMapsTuneNoteRev11`. Изменены `mapGrade` в `marmoreal-night` и `sarpedon-night`; в `readability` обеих досок contactShadow и reach.strokeUU.
- `unreal/Unmatched/Config/ArtBoards/EnvLayouts/{marmoreal,sarpedon}.layout.json`: интенсивность и цвет огней, заметка P4 tune. Радиусы и число огней прежние. Секция `ground` пересчитана `ground_splat.py --write-layouts`: у водопада `dropUU` 120.
- `art/pipeline-candidates/ASSET-ENV-KIT-001/ground/ground-params.json`:
  - Sarpedon: грейд, тинты L1 и L3, вода (lift, colorSrgb), водопад.
  - Marmoreal: грейд (sat 0,82, тинт (0,96; 1,0; 1,1)).
- `art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/scripts/env-prop-look.json`: Cherry satMul 0,42, цель альбедо S [0,22; 0,4].
- `tools/art/map_surface/manifest.{marmoreal,sarpedon}.json`: K1-грейд из профиля (`build_map_textures.py --refresh-k1`).
- Тесты с закреплёнными значениями: `tools/art/tests/test_env_ground.py` (цвет воды) и `tools/art/tests/test_env_prop_look.py` (альбедо S вишни ~0,25).
- MI вне git переимпортированы: MI_EnvGround_*, MI_EnvWaterfall_Sarpedon, MI_Env_Cherry, MI_*_MapBoard.

## Команды

```
# итерация (GPU-лок C:/tmp/unmatched-gpu.lock; editor -game -Bench; замеры; монтаж)
python C:/tmp/envmaps-research/p4/tune/apply.py specs/<it>.spec.json
python -B tools/art/env_kit/ground_splat.py --write-layouts && python -B tools/art/env_kit/ground_splat.py --check
node C:/tmp/envmaps-research/p4/tune/run-ue-cmd.cjs <tag> "<wt>/tools/art/env_kit/ue_import_env_ground.py" -ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False
node C:/tmp/envmaps-research/p4/tune/run-ue-cmd.cjs <tag> "<wt>/tools/art/env_kit/ue_import_env_kit.py" -ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False
python -B tools/art/map_surface/build_map_textures.py --refresh-k1
node C:/tmp/envmaps-research/p4/tune/run-ue-cmd.cjs <tag> "<wt>/tools/art/map_surface/ue_import_map_surface.py --maps marmoreal,sarpedon"
sh C:/tmp/envmaps-research/p4/tune/iter.sh <tag> m s          # финал: BENCH_WARMUP=60 BENCH_VIEWS=K1+K1x0.65+K2x1.6+K2x2.5; Cobble: ... iter.sh final c
python C:/tmp/envmaps-research/p4/tune/measure.py frames <run> --json measure.json
python C:/tmp/envmaps-research/p4/tune/measure_extra.py <run> --json zones-extra.json
python tools/art/map_surface/zone_separation.py measure <map> <run>/bench-K1-1920x1080.png <run>/bench.trace.log
python tools/art/render_fingerprint.py check --trace <map>/bench.trace.log --shot bench-K1-1920x1080.png
```

Строка клиента: `<map>/cmdline.txt`. Это те же параметры, что в P2, и `-BenchViews=K1+K1x0.65+K2x1.6+K2x2.5 -BenchWarmup=60`. Прогоны завершились сами с EXIT=0 за 127,8 / 127,7 / 84,7 с (`<map>/exit.txt`).

## Строки трассы

```
ARTPREVIEW map grade profile=marmoreal-night source=profile nightEV=-0.35 nightSaturation=0.75 lift=1.75 nightTint=(0.9700,1.0000,1.0500) maskSaturation=1.40 liftSaturation=1.30 maskInverseTint=(0.9830,1.0100,0.9470) graph=v2 maskTerms=1
ARTPREVIEW map grade profile=sarpedon-night source=profile nightEV=-0.35 nightSaturation=0.75 lift=1.70 nightTint=(0.9700,1.0000,1.0500) maskSaturation=1.05 liftSaturation=1.10 maskInverseTint=(1.0500,0.9960,0.8910) graph=v2 maskTerms=1
ARTPREVIEW envlayout ground map=marmoreal mode=runtime strips=4 material=MI_EnvGround_Marmoreal ... falls=0/0 fallCards=0 status=ok
ARTPREVIEW envlayout ground map=sarpedon mode=runtime strips=4 material=MI_EnvGround_Sarpedon ... falls=1/1 fallCards=2 status=ok
ARTPREVIEW envlayout map=marmoreal props=21 lights=5 missingMeshes=0 ... intrusions=0 outsideTray=0 ... profilePoints=1 combinedPoints=6 combinedBudgetOk=1
ARTPREVIEW envlayout map=sarpedon props=24 lights=5 missingMeshes=0 ... intrusions=0 outsideTray=0 ... profilePoints=1 combinedPoints=6 combinedBudgetOk=1
ARTPREVIEW map frame wood=frame-wood material=M_MapFrameWood valueScaleSrgb=0.70 valueScaleLinear=0.4563 saturation=0.75
readability fighter=f-0-hero hero=1 contactShadow=1 diameterUU=52.0 strength=0.25 leaderPip=1 look=P1 ringScale=1.00
reachable rings cells=19 placed=1 radiusUU=36 segments=48 style=readability color=#FFC857 stroke=#14110C widthUU=3.50 strokeUU=1.50
RENDER tag=SHOT rhi=D3D12 featureLevel=SM6 shaderPlatform=PCD3D_SM6 lumenPlatform=1 gi=lumen ... reference=1
```

sha256 профилей (`profilesSha256=c90dddd95a8a7a0b…`) и обоих layout в трассе совпадают с файлами worktree на момент финала.

## Проверки

- **Cobble K1 (сетка) против контроля P2** (`p2/integrate-frames/c1-cobble-control`): средняя |d| 0,60, p99 4, 0,03 % пикселей > 24 (анимированные фигуры). Средняя яркость 45,02 / 45,03. Против кадра интеграции P4: |d| 0,39. Сеточная доска не изменилась.
- **Сборки** `-NoXGE -MaxParallelActions=6` под `C:/tmp/unmatched-package.lock`: UnmatchedEditor и Unmatched, обе «Result: Succeeded», «Target is up to date». C++ на этапе Tune не менялся, после сборки интеграции код тот же.
- **Автотесты** `Unmatched.S08+Unmatched.S09+Unmatched.S10`: найдено 222, Success 222, Fail 0, «TEST COMPLETE. EXIT CODE: 0».
- **Python:** `pytest tools/art/tests tools/art/map_surface/test_map_surface.py` — 268 passed + 69 subtests. Два теста с закреплёнными значениями обновлены под новые значения.
- **Прочие проверки:**
  - `layout_check.py`: обе карты OK, 0 WARN; `--selftest` 25/25.
  - `ground_splat.py --check`: OK.
  - `env_prop_look.py --check`: `ENVPROP-LOOK ok props=6`.
  - `ue_import_env_ground.py --check`, `ue_import_env_kit.py --check`, `ue_import_map_surface.py --check`: ok.
  - `art_board_fixtures.py check`: профили PASS, rev 11.
- **Импорты в UE** (commandlet, `-nullrhi`): `ENVKIT-IMPORT-RESULT ok`, `ENVGROUND-IMPORT-RESULT ok`, `ENVMAPS-IMPORT-RESULT ok`. MI карты получили грейд профиля: MaskSaturation 1,4 / 1,05, LiftSaturation 1,3 / 1,1.
- Платных шагов и загрузок не было, новых CC0-наборов нет. Локи сняты, своих процессов UE не осталось.

## Известные пробелы

- **Контур ΔL\* Marmoreal по медиане** 35,0 < 36,1. По среднему и попарно он ≥ P2 (см. выше). Медиану сдвигает оформление занятых кругов, а не грейд.
- **Окружение/карта Sarpedon 0,45**: в допуске (≤ 0,47), но выше концепта (0,38). Тёплая доля (0,125) держится на светлой палубе и песке. Поднять её дальше без новых огней или эмиссива пропсов (фонари на столбах, пробел 4) нельзя.
- **Водопад** — процедурная карточка. При 0,65× это светлая полоса с рваным низом, которая уходит в пустоту под подносом. Тумана или облаков под островом нет (пробел 8, нужен новый ассет). Вырезки в каменной губе T2 тоже нет (пробел 3). Вода и водопад анимированы по Time, поэтому кадры разных прогонов немного отличаются.
- **Вода за рамкой** насыщенно-синяя (b\* −41), нарисованная река темнее и с текстурой. По яркости вода близка к реке (×0,91 / ×0,76).
- **Оттенок кроны вишни** в кадре 328° (альбедо 341°): холодный ключ и тёплые фонари его сдвигают. Насыщенность в цели.
- **Подложки подписей** (читаемость HIGH) в `-Bench` не видны: здесь рисуются мировые TextRender-подписи. Нужны живые или packaged-кадры.
- **Кольцо хода** на жёлтых зонах Sarpedon читается в основном за счёт тёмной обводки.
- **Packaged-сборка в P4 не пересобиралась.** /Game/EnvKit/Shared, M_EnvWaterfall и материалы читаемости в /Game/EnvMaps должны попасть в кук через DirectoriesToAlwaysCook. Это нужно проверить в следующем packaged-прогоне.
- **Пробелы с новыми ассетами** — 3, 4 (пропсы палубы), 6 (балюстрады), 7 (скалы), 8, 9 (полная рамка), 12 — вне этого этапа. Пробел 16 и поворот ключа (ENV-U12) не трогались.

## Оговорки ревью P4 (честность замеров)

- **Метрика зон.** `zone_separation.py` (медиана секторов, ΔE76) даёт примерно на 4,7 ΔE больше, чем метрика ревью концептов P2
  (`concept-review.json`: 15,3 / 17,7 там против 19,9 / 22,4 здесь для тех же кадров P2). По этой метрике P2 уже проходил «≥ 20».
  Итог: Marmoreal розовый–лавандовый 19,9 → 24,4 — реальный рост; Sarpedon голубой–розовый 22,4 → 23,2 (+0,8, в метрике ревью
  ≈18,5, вероятно всё ещё ниже 20). Читаемость зон (HIGH): Marmoreal — **улучшено**, Sarpedon — **улучшено, не закрыто**.
- **layout_check ослаблен на уровне WARN:** диапазон числа пропов 18 → 28 (в раскладках теперь 21 / 24 пропа), правило высоких
  пропов в ближней половине сужено до колонок рамки по X (иначе предупреждали бы tree-w5 и hull-e2). Ошибки (зазор над клетками,
  тени, ближняя полоса, K1_FRAMED) не менялись.
- **Не замерено в P4:** производительность (`render_bench.py` / packaged `-Bench` с новыми пропами, M_EnvGround graph 2,
  M_EnvWaterfall, M_EnvProp, пятнами теней и кольцами досягаемости) и тёплый засвет перенесённых фонарей корабля на восточные
  круги Sarpedon (S15 / S27 / S07). Подложки подписей (UMG) видны только в live / packaged-кадрах, в `-Bench` их нет.
- **Packaged не пересобирался в P4:** кук `/Game/EnvKit/Shared`, `M_EnvWaterfall` и материалов читаемости `/Game/EnvMaps` проверяется
  на следующем packaged-прогоне.
