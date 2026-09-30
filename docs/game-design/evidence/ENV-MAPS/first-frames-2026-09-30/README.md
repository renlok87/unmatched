# ENV-MAPS: первые кадры диорам на оригинальных картах (2026-09-30)

Статус: **первые технические кадры, не арт-приёмка.** Сняты без бэкенда в режиме `-Bench` в редакторе в игровом режиме (`UnrealEditor.exe -game`, некукнутый контент worktree `C:/tmp/wt-envmaps`, ветка `feat/env-original-maps`). Упакованный клиент не собирался: `-Bench` работает и в редакторе, упаковка не понадобилась.

В кадре: оригинальная карта (map-image, 4K BC + маска, M_MapBoard) на каменном подносе-заглушке T1 (SM_TableBase), окружение по периметру (env kit по `Config/ArtBoards/EnvLayouts/<map>.layout.json`) и 6 фигурок heroes v2: Medusa и 3 Harpies (P1, золото) против King Arthur и Merlin (P2, серо-синие).

| Карта | K1 (камера по умолчанию, 1872 uu) | Отдаление 0,65× (2880 uu, дальний предел колеса) | Приближение 1,6× на Medusa (1170 uu) |
|---|---|---|---|
| Marmoreal | [marmoreal/bench-K1-1920x1080.png](marmoreal/bench-K1-1920x1080.png) | [marmoreal/bench-K1x0p65-1920x1080.png](marmoreal/bench-K1x0p65-1920x1080.png) | [marmoreal/bench-K2x1p6-1920x1080.png](marmoreal/bench-K2x1p6-1920x1080.png) |
| Sarpedon | [sarpedon/bench-K1-1920x1080.png](sarpedon/bench-K1-1920x1080.png) | [sarpedon/bench-K1x0p65-1920x1080.png](sarpedon/bench-K1x0p65-1920x1080.png) | [sarpedon/bench-K2x1p6-1920x1080.png](sarpedon/bench-K2x1p6-1920x1080.png) |

На кадре 1,6× Medusa выбрана: видно кольцо выбора и кольца досягаемых пространств (Marmoreal 8, Sarpedon 19 при движении 3). Кольца выбора и досягаемости включаются только в виде K2.

## Сцена: bench-фикстуры

`unreal/Unmatched/Config/Bench/S08BenchMarmoreal.json` и `S08BenchSarpedon.json` построены по формату снятой фикстуры `S08BenchCobble.json` (ответ `gameState(gameId)`):

- Игроки, id, имена и статы бойцов, колоды и руки взяты из Cobble-фикстуры как есть. Поэтому `-ArtPreviewHeroesV2` подставляет те же фигурки, и зритель тот же (seat 0).
- `benchBoardId` равен `boardId` топологической фикстуры (Marmoreal `c121b47f8d6eb28daccb76d05`, Sarpedon `c7fa64a26c29a0835f2383e63`). По нему подхватываются map-image профиль `<map>-original` и env layout.
- `boardState` и стартовые позиции бойцов вычислены не вручную. Скрипт запускает серверный `GameInitializationService.initializeGameState` на строке Board, которую строит `prisma/seed-env-map-boards.ts` из `backend/prisma/fixtures/boards/<map>.topology.json`; Prisma подменена заглушкой, БД не нужна.
- В `boardState` лежат клетки решётки W×H: `links`, `layout`, `start`, `spaceId`, `zones`, `zone`; непроходимые клетки имеют `type: obstacle`.
- Правило расстановки: seat 0 ставится на старт 1, seat 1 на старт 2; сайдкики занимают ближайшие по BFS по линиям пространства в зонах героя.
- Генератор: `tools/art/render/env_bench_fixtures.cts`. С `--check` он пересобирает фикстуры в памяти и сверяет с закоммиченными (сейчас `ok`).

```
node backend/node_modules/ts-node/dist/bin.js --transpile-only -P backend/tsconfig.json tools/art/render/env_bench_fixtures.cts [--check]
ENV-BENCH-FIXTURE marmoreal ok S08BenchMarmoreal.json f-0-hero=M13 f-0-sk0=M07 f-0-sk1=M20 f-0-sk2=M01 f-1-hero=M31 f-1-sk0=M23
ENV-BENCH-FIXTURE sarpedon ok S08BenchSarpedon.json f-0-hero=S20 f-0-sk0=S19 f-0-sk1=S18 f-0-sk2=S23 f-1-hero=S32 f-1-sk0=S25
```

Зоны:

- Marmoreal: Medusa на M13 [red, yellow], старт 1. Harpies на M07 [green, red, yellow], M20 [red, yellow] и M01 [gray, yellow]. Arthur на M31 [violet, brown], старт 2. Merlin на M23 [violet].
- Sarpedon: Medusa на S20 [blue], старт 1. Harpies на S19, S18 и S23 [blue]. Arthur на S32 [purple], старт 2. Merlin на S25 [yellow, brown, purple].

## Изменения кода

- `S08FlowGameMode.cpp` RunRenderBench: новый вид `K1x<z>` с z < 1. Это отдаление обзора нотчами колеса, тем же путём, что у игрока, до запрошенного зума или дальнего предела (overview / OverviewOutRatio = 0,65×). В трассе появляется строка `BENCH view=K1x0.65 zoom-out wanted=0.65 target=2880.2 zoom=0.65 limit=far`. Раньше любой вид с z ≤ 1 превращался в обзор. Файл фикстуры выбирается уже существующим флагом `-BenchFixture=<json>`, отдельный `-BenchState` не понадобился.
- `Unmatched.Build.cs`: обе новые фикстуры добавлены в RuntimeDependencies (UFS), как и Cobble. Упакованный `-Bench` сможет читать их из пака. Проверено: они есть в `Binaries/Win64/Unmatched.target`.
- Сборки прошли с 0 ошибок и 0 предупреждений по изменённым файлам: UnmatchedEditor (fb1, fb2) и игровая цель Unmatched (fg2), `-NoXGE -MaxParallelActions=6`. Логи лежат в `C:/tmp/envmaps-research/p1b-ue/build/build-{fb1,fb2,fg2}.*`, вне git.

## Командная строка

Полная строка каждого прогона лежит в `<map>/cmdline.txt`. Marmoreal:

```
UnrealEditor.exe C:\tmp\wt-envmaps\unreal\Unmatched\Unmatched.uproject /Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode
  -game -windowed -resx=1920 -resy=1080 -ForceRes -RenderOffScreen -nosplash -unattended -NoSound
  -ArtPreview -ArtPreviewDiorama -ArtPreviewHeroesV2
  -Bench -BenchFixture=<wt>\unreal\Unmatched\Config\Bench\S08BenchMarmoreal.json -BenchOut=<dir>
  -BenchViews=K1+K1x0.65+K2x1.6 -BenchWarmup=60 -BenchSettle=6 -BenchMeasure=5 -BenchNoProfileGPU -BenchFps=60
  -S08RenderPreset=High -S08Trace=<dir>\bench.trace.log -abslog=<dir>\client.log -ExecCmds=DisableAllScreenMessages
```

У Sarpedon то же с `S08BenchSarpedon.json` и `-BenchWarmup=45`. Прогоны длились 114,8 и 100,0 с и завершились сами с EXIT=0 (`<map>/exit.txt`). Кадры снимает сам bench через `FScreenshotRequest`, 1920×1080, с HUD.

## Строки трассы

Полные трассы: `<map>/bench.trace.log`. Логи клиента: `<map>/client.log`.

Marmoreal:

```
ARTPREVIEW map-image assets map=Marmoreal mi=MI_Marmoreal_MapBoard material=M_MapBoard bc=T_Marmoreal_Map_BC_4K mask=T_Marmoreal_Map_GameMask_4K boundBc=1 boundMask=1 sdf=1 id=1
ARTPREVIEW board profile=marmoreal-original match=boardId board=7x6 boardId=c121b47f8d6eb28daccb76d05 surface=map-image light=marmoreal-night artFixture=0 map=Marmoreal
ARTPREVIEW board active profile=marmoreal-original 7x6 surface=map-image map=Marmoreal spaces=31 links=42 starts=4 zoneKeys=8 multizone=21 triple=7 obstacles=11 size=891.3x577.3 src=1337x866 uuPerPx=0.6666667 frameUU=24 surfaceParts=4 corners=4 zoneMarks=0 lattice=0 pick=445.7x288.7 mi=MI_Marmoreal_MapBoard wood=1 expectOk=1
ARTPREVIEW envlayout map=marmoreal props=17 lights=5 missingMeshes=0 layoutProps=17 layoutLights=5 skippedMissing=0 skippedInsideMap=0 intrusions=0 outsideTray=0 outsideKit=0 shadowCasters=17 profilePoints=1 combinedPoints=6 combinedBudgetOk=1 tray=layout trayApronMismatch=0 profile=marmoreal-original ... status=ok
ARTPREVIEW envlayout tray map=marmoreal source=layout outerHalf=729.7x442.7 offsetY=-40.0 frameHalf=469.7x312.7 fitBoardHalf=679.7x352.7 anisotropy=1.430
ARTPREVIEW diorama tray=/Game/PipelineCandidates/TableBase/.../SM_TableBase.SM_TableBase mi=MI_TableBase_Candidate surface=map-image yaw=0.0 scale=1.930x1.350x1.000 bounds=(-729.7,-482.7,-153.0)..(729.7,402.7,-3.0) size=1459.3x885.3x150.0 topZ=-3.0 boardHalf=679.7x352.7 rimUU=50.0 collision=none offset=(0.0,-40.0) anisotropy=1.430 waiver=T1-placeholder
CAMERA extents source=map-image half=445.7x288.7 dist=1872.2
CAMERA dist=1872 loc=(0,1074,1534) pitch=-55 yaw=-90
CAMERA config overview=1872.2 nearest=300.0 farthest=2880.2 zoomRange=0.65-6.24 ...
BOARD topology spaces=31 links=42 starts=3:M03,4:M11,1:M13,2:M31 frame=1337x866px uuPerPx=0.6667 radius=42.0uu (default)
ARTPREVIEW heroesV2 summary fighters=6 mapped=6 v2=6
FIGHTERS synced n=6 alive=6 own=4 enemy=2
BENCH scene fixture=S08BenchMarmoreal.json board=7x6 fighters=6 viewer=cmukie55u0000wiao06h107t9 hero=f-0-hero art=1 profile=marmoreal-original views=K1+K1x0.65+K2x1.6 ...
```

Sarpedon:

```
ARTPREVIEW map-image assets map=Sarpedon mi=MI_Sarpedon_MapBoard material=M_MapBoard bc=T_Sarpedon_Map_BC_4K mask=T_Sarpedon_Map_GameMask_4K boundBc=1 boundMask=1 sdf=1 id=1
ARTPREVIEW board profile=sarpedon-original match=boardId board=9x6 boardId=c7fa64a26c29a0835f2383e63 surface=map-image light=sarpedon-night artFixture=0 map=Sarpedon
ARTPREVIEW board active profile=sarpedon-original 9x6 surface=map-image map=Sarpedon spaces=38 links=61 starts=4 zoneKeys=6 multizone=4 triple=2 obstacles=16 size=891.3x577.3 src=1337x866 uuPerPx=0.6666667 frameUU=24 ... expectOk=1
ARTPREVIEW envlayout map=sarpedon props=18 lights=4 missingMeshes=0 ... intrusions=0 outsideTray=0 outsideKit=0 shadowCasters=18 profilePoints=1 combinedPoints=5 combinedBudgetOk=1 tray=layout trayApronMismatch=0 ... status=ok
ARTPREVIEW envlayout tray map=sarpedon source=layout outerHalf=769.7x462.7 offsetY=-50.0 frameHalf=469.7x312.7 fitBoardHalf=719.7x362.7 anisotropy=1.443
ARTPREVIEW diorama tray=... surface=map-image yaw=0.0 scale=2.036x1.411x1.000 bounds=(-769.7,-512.7,-153.0)..(769.7,412.7,-3.0) ... anisotropy=1.443 waiver=T1-placeholder
CAMERA extents source=map-image half=445.7x288.7 dist=1872.2
CAMERA dist=1872 loc=(0,1074,1534) pitch=-55 yaw=-90
BOARD topology spaces=38 links=61 starts=3:S03,4:S14,1:S20,2:S32 frame=1337x866px uuPerPx=0.6667 radius=42.0uu (default)
ARTPREVIEW heroesV2 summary fighters=6 mapped=6 v2=6
```

Камера в кадрах, одинаково на обеих картах:

```
SHOT camera dist=1872.2 target=1872.2 overview=1872.2 errPct=0.000 focusErr=0.00 settled=1 zoom=1.00   (K1)
SHOT camera dist=2880.2 target=2880.2 overview=1872.2 errPct=0.000 focusErr=0.00 settled=1 zoom=0.65   (K1x0.65)
SHOT camera dist=1170.1 target=1170.1 overview=1872.2 errPct=0.000 focusErr=0.00 settled=1 zoom=1.60   (K2x1.6, фокус на f-0-hero)
```

RENDER-отпечаток у всех 6 кадров совпадает с эталоном. Проверка через `render_fingerprint.check` против `docs/art-pipeline/render-reference.json`: 6/6 `reference=True`, причин отказа нет.

```
RENDER tag=SHOT rhi=D3D12 featureLevel=SM6 shaderPlatform=PCD3D_SM6 lumenPlatform=1 gi=lumen giMethod=1 refl=lumen reflMethod=1 shadows=csm vsmEnable=0 sg.res=100 sg.view=2 sg.aa=2 sg.shadow=2 sg.gi=2 sg.refl=2 sg.pp=2 sg.tex=2 sg.fx=2 sg.foliage=2 sg.shading=2 sg.landscape=2 preset=High screenPct=100.0 screenPctMode=0 aa=TSR aaMethod=4 exposure=fixed-histogram expMin=4.14106 expMax=4.14106 expBias=0.000 ev100=2.05 lightUnits=candelas sky=1 skyIntensity=12.500 keyShadow=csm-3600uu-2c-contact0.000 shadowCasters=1 profile=marmoreal-night profilesSha256=0e8981d4...fe25b profilesSource=pak legacyRender=0 gameLayer=unlit-eyeadaptinv tMaxFPS=60.0 vsync=0 frameRateLimit=60.0 substrate=0 nanite=1 meshDF=1 viewport=1920x1080 reference=1
```

Производительность (справочно). Это сборка редактора с ограничением 60 FPS, а не замер `render_bench.py`. Все виды держат 60,00 FPS без хитчей, gpuMs avg 2,0–2,2, p95 ≤ 2,35. RTX 4090, «измерено», не бюджет.

## Что проверено глазами

- **Ориентация карты.** Карта не зеркальная и не повёрнута. Кадры сверены с исходниками (`scraped-data/images/maps/{marmoreal,sarpedon}.png`, вне git): у Marmoreal старт 3 сверху и колоннада слева, у Sarpedon лес слева, река посередине, корабль справа.
- **Фигурки на кружках.** Все 6 фигурок стоят в центрах нарисованных кружков. Под Medusa нарисованная метка «1», под King Arthur метка «2» (стартовые пространства). Harpies стоят в зоне Medusa, Merlin в зоне Arthur. Кольца досягаемости (r = 36 uu) лежат внутри нарисованных кружков (r = 42 uu), кольца команд тоже по центру.
- **Окружение.** Все пропы на месте: Marmoreal 17 пропов и 5 огней, Sarpedon 18 и 4, `missingMeshes=0`. Пропы стоят на верхе подноса (z = −3), не висят и не утоплены. Тёплые огни фонарей и костров видны.
- **Текстуры.** Отсутствующих текстур и дефолтных материалов нет. В логах только известные предупреждения, см. п. 5 ниже.

## Что сломано или требует работы

1. **Поднос T1: открыта «посадочная» зона SM_TableBase с чёрными рваными дырами.** Видно на всех кадрах, сильнее всего на отдалении 0,65×.
   - Tripo-меш подноса рассчитан на то, что его центр закрыт доской Cobble. Внутри каменной каймы у него размытая «облачная» плита, а по её краю рваные дыры в пустоту (так выглядит и превью `art/pipeline-candidates/ASSET-TABLE-BASE-001/.../preview/blender-04-textured-top.png`).
   - Env layout растягивает поднос до `outerHalf` 729,7×442,7 (Marmoreal) и 769,7×462,7 (Sarpedon), то есть в 1,93×1,35 и 2,04×1,41 раза. Посадочная зона выходит за раму карты (half 469,7×312,7): между рамой и каймой видны размытая плита и чёрные дыры.
   - Это не ошибка кода и не ошибка разметки. Заглушка T1 (`waiver=T1-placeholder`) не рассчитана на такой фартук. Без нового арта это не лечится, поэтому здесь не исправлялось (граница задачи: «не тюнить арт»).
   - Варианты: модульная юбка T2 (ENV-O8: углы и сегменты, Blender) или временная плоская плита-фартук поверх посадочной зоны, между верхом подноса −3 и плоскостью карты −0,5, с каменным материалом.
2. **Ночь не откалибрована.** Карта читается светлой, почти дневной. Профили `marmoreal-night` и `sarpedon-night` — заглушки: ключ 3 lux, EV100 2,05, грейд M_MapBoard NightEV −0,7. Калибровка идёт отдельным шагом через `render_bench.py` на ROI карты.
3. **HUD bench.** Маленькие тёмные квадраты в углах: `hud.command` (0,0), `hud.side` (1884,0) и `hud.hand` (950,1060). Это пустые панели HUD режима `-Bench`, как и в Cobble-бенче. На K1 подписи бойцов («Harpies 1 1/1») слегка наезжают на фигурки соседнего кружка. Это текущее поведение HUD, не карты.
4. **K1 обрезает высокие пропы дальнего края** (портал и колоннада Marmoreal, корпус корабля Sarpedon). Это ожидаемо: K1 кадрирует карту, окружение целиком видно на 0,65×.
5. **Лог.** `LoadErrors ... SK_Medusa_FaceNeck_v2Candidate_PhysicsAsset` — старая ошибка кандидата ArtPreview, фигурка v2 от неё не зависит. Остальное — ошибки Python-плагинов Toolsets движка и предупреждения EditorDataStorage редактора. Предупреждений, связанных с картой, env kit или фигурками, нет.
6. **Это редактор, а не упаковка.** Контент некукнутый, текстуры 4K строились в DDC при первом использовании. Упакованный прогон и живая пара клиентов с бэкендом ещё впереди. Для упакованного `-Bench` фикстуры уже подключены в Build.cs.

## Процессы

- Прогоны: UnrealEditor PID 58172 (Marmoreal) и 44612 (Sarpedon). Сборки: UBT через cmd.exe. Все завершились сами.
- После работы нет ни UnrealEditor, ни ShaderCompileWorker, ни UBT моих прогонов.
- GPU-токен `C:/tmp/unmatched-gpu.lock` снят.
- Редактор главного checkout и экземпляры Blender других сессий не трогались.

Файлы `*.log` попадают под `.gitignore` (`*.log`). Для коммита их нужно добавлять через `git add -f`, как в прошлых evidence.
