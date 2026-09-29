# King Arthur (ASSET-KING-ARTHUR-001) H2.1: импорт в UE (W5c-A)

Срез 2026-09-29. Статус: **технически импортировано**.
- Это не художественная приёмка: её делает волна 6.
- Это не бюджет: GD-058 открыт, все лимиты ниже — предложение.
- Платных операций не было: Tripo и SYNTX не вызывались. Blender запускался только как `blender --version` в preflight.
- Редактор общий: UnrealEditor PID 31756, DX12/SM6 + Lumen, MCP :8123. Он не перезапускался, чужие пакеты не сохранялись, `/Game/UM/Materials/*` только читались.
- Harpy и Medusa не импортировались.

Вход — H2.1 из [king-arthur-h2-report.md](king-arthur-h2-report.md) (раздел «H2.1»): бейк `king-arthur-h2-bake/1`, папка `art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-bake/`. В UE попали:
- `export/SK_KingArthur_H2.fbx` (`9f347812…`);
- `export/SM_KingArthur_H2_Base.fbx` (`dc75338c…`);
- четыре рантайм-карты 2K из `textures/runtime_2k/`: BC, N (DirectX), ORM, TeamMask.

Не импортировались 4K-мастера и `T_KingArthur_H2_N_OpenGL.png`.

## Итог

- В `/Game/PipelineCandidates/KingArthur/H2` лежат **13 uasset**:
  - меши: `SK_KingArthur_H2`, `SK_KingArthur_H2_Skeleton`, `SM_KingArthur_H2_Base`;
  - текстуры: `T_KingArthur_H2_{BC,N,ORM,TeamMask}`;
  - материалы: `MI_KingArthur_H2` (родитель `M_UM_Figure`), `MI_KingArthur_H2_Base` (родитель `M_UM_BaseMarker`) и командные `MI_KingArthur_H2_{Blue,Red}`, `MI_KingArthur_H2_Base_{Blue,Red}`.
- Стадия adopt: **13/13** проверок. Стадия ue-import: **25/25** проверок, статус `technically_imported`.
- Повторный импорт новых ассетов не создаёт (см. «Идемпотентность»).
- Кадры редактора на свету Cobble (High): 14 кадров Blue/Red, 2 обзора G-буфера, 2 листа сравнения с Blender H2.1. Кадры — `editor-mcp-viewport`, диагностика, не K1/K2-приёмка.
- Честная оценка кадров — в разделе «Сравнение с Blender H2.1». Главное: **металл в UE металл**, ORM читается верно. Но сталь в свете Cobble почти белая, заметно светлее Blender-кадров.

## Как повторить

```bash
R=art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-ue-import
P=art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2-ue-import.json
T=tools/tripo-pipeline/tripo_pipeline.py
python $T init --run-dir $R --asset-id ASSET-KING-ARTHUR-001 --primary-source tripo-c24eeff0-h2 \
  --primary-role h2-parts-glb --profile skeletal-adopt --build-profile $P --run-id 20260929-h2-ue-import
python $T register-source --run-dir $R --spec art/pipeline-candidates/ASSET-KING-ARTHUR-001/source-specs/tripo-c24eeff0-h2.json
python $T run --run-dir $R                      # preflight + adopt (headless, без UE и Blender MCP)
python $T --backend mcp ue-import --run-dir $R --ue-folder /Game/PipelineCandidates/KingArthur/H2
# кадры (живой редактор; уровень контрольной сцены загружается в память и не сохраняется)
python tools/tripo-pipeline/review/h2_ue_review.py --run-dir $R \
  --out docs/art-pipeline/evidence/w5c-arthur-h2-ue-2026-09-29 \
  --blender-frames art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-bake/preview/frames --tag r3
```

В Git Bash перед путями `/Game/...` нужен `MSYS_NO_PATHCONV=1`. Без него MSYS превращает папку в `C:/Program Files/Git/Game/...`, и CLI отказывает: папка вне `/Game/PipelineCandidates/`.

## CLI: профиль skeletal-adopt и формат отчётов Arthur

Параллельно (W5c, Merlin) в CLI 0.7.0 появился профиль `skeletal-adopt`. Он работает так:
- стадия `adopt` сверяет внешний бейк;
- `ue-import` идёт тем же кодом, что `skeletal-candidate`: MI от мастеров, явная FbxFactory, сокеты, проверки контрактов;
- добавлен замер треугольников LOD в редакторе через GeometryScript.

Второй механизм импорта я не делал. Отчёты бейка Arthur устроены иначе, чем у Merlin, поэтому я добавил **нормализатор формата**.

Что сделано:
- **`tools/tripo-pipeline/skeletal_adopt_formats.py`** (новый). Формат `h2-bake-arthur/1`, функция `arthur_h2`. Она переводит `reports/rig-report.json` (`unmatched.h2-bake.rig/1`) и `reports/textures-report.json` (`unmatched.h2-bake.textures/2`) в раскладку `h2-bake-rig/1`, которую читает `skeletal_adopt.adopt()`:
  - у объектов read-back снят суффикс `.001`. Бейк читает FBX обратно в сессию, где ещё лежат авторские объекты, поэтому Blender их переименовывает;
  - границы мешей переведены из кадра экспорта в авторский кадр (поворот −90° вокруг Z);
  - `scale_ratio` измерен: read-back тела против `geometry.bounds_body_m` → [1,0; 1,0; 1,0];
  - конвенции карт берутся **по файлу, на который указывает профиль**. Если профиль укажет N на `*_N_OpenGL.png`, его конвенция будет «OpenGL/Blender (+Y)», и adopt провалит требование «DirectX».
  - Проверки, для которых в целевой раскладке нет места, входят в общий `passed` и видны в `adopt-report.json → bake.normalised.checks`:
    - все 18 проверок rig-report прошли, `failed` пуст;
    - `manifest-h2.json` перечисляет ровно эти байты FBX и карт; sha256 профиля бейка совпадает;
    - `validate-skeletal-mesh-v2.json`: `pass`, скелет `UM_HUMANOID_17_v2`, sha FBX тот же.
- **`skeletal_adopt.py`**: минимальные врезки.
  - формат `h2-bake-arthur/1` в `REPORT_FORMATS`: указатели `h2-bake-rig/1`, кроме `figure_top_uu`;
  - функция `normaliser()` и вызов нормализатора в `adopt()`;
  - `candidate.extra_reports` и профиль бейка — закреплённые входы. Их изменение перезапускает adopt и блокирует устаревший ue-import.
- **Профиль** [`king-arthur-h2-ue-import.json`](../../art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2-ue-import.json) (`king-arthur-h2-ue-import/1`, kind `skeletal-adopt`):
  - файлы бейка, 17 костей v2 с родителями;
  - рост 0,55 м (верх короны `tripo_part_6`), габарит подставки из read-back;
  - сокеты `Weapon` (на `weapon.R`, 0,0,0) и `Head` (смещение — предсказание бейка);
  - маршрут `um-master`, команды Blue `#3F6FD8` / Red `#D0453A` — та же тестовая пара, что у Merlin.
- **Тесты** [`tests/test_skeletal_adopt_arthur.py`](../../tools/tripo-pipeline/tests/test_skeletal_adopt_arthur.py), 10 шт.:
  - нормализатор на синтетическом бейке в раскладке Arthur;
  - провалы: манифест не перечисляет байты; validate `fail`; OpenGL-нормаль вместо N; чужая схема;
  - CLI-цикл init → register → run → ue-import ×2 → `--force` на фейковом редакторе, 13 ассетов без `_1`;
  - изменённая текстура после adopt блокирует UE-стадию;
  - adopt на **настоящем** бейке H2.1 этого репозитория, с совпадением предсказанных границ UE.
  - `fake_unreal_mcp.py` для такого бейка строит границы UE **независимо**: прямо из read-back в кадре экспорта, (x, −y, z) × 100, а не через нормализатор.
- Прогон `python -m unittest discover -s tools/tripo-pipeline/tests`: 195 тестов.
  - 194 прошли;
  - `test_pipeline.ResumeTests.test_killed_process_is_resumable` упал один раз под нагрузкой. Этот тест убивает процесс по таймингу, профиль passthrough; к изменениям отношения не имеет. Отдельный повтор — OK.

## Проверки импорта (ue-import-report.json, прогон `--force`)

| Что | Измерено в UE | Ожидание |
|---|---|---|
| Кости | 18: кость 0 `SKEL_UM_Humanoid`, затем 17 костей v2 с иерархией (`weapon_R` под `hand_R`) | 17 костей профиля + узел арматуры = кость 0 (ловушка ue-pipeline-traps №2) |
| Импорт | `FbxFactory`, `FbxSkeletalMeshImportData` / `FbxStaticMeshImportData`, нормали `FBXNIM_ImportNormals`, Nanite выкл. | контракт волны 4 |
| Лицо | карта осей единственная: «Blender −Y → UE +X» (ошибка 0,0004 uu). В сцене по плечам и бёдрам лицо смотрит на **+2,13°** от +X (в FBX у бейка −2,13°: UE зеркалит Y), меч справа (+Y 7,67 uu) | +X ± 10° |
| Границы SK, uu | min (−8,018; −16,018; 5,807), max (12,683; 14,432; 60,058) | предсказание бейка ±0,05 uu — совпало до 0,001 |
| Рост | верх короны 55,0 uu (профиль 0,55 м); верх SK 60,058 uu (острие меча) | 52–56 uu (предложено); меч в рост не входит |
| Треугольники | LOD0 **38 684** = 36 469 тело + 2 215 меч (GeometryScript); подставка 1 500. Всего 40 184 | ориентир H2 30–45k (предложено) |
| LOD / секции / слоты | 1 LOD, 1 секция, 1 слот `M_KingArthur_H2` (SK) и 1 слот (подставка) | 1 LOD (FBX несёт только LOD0), ≤ 2 слотов |
| Подставка | min (−14,766; −15,018; 0), max (14,747; 14,993; 6,030) | габарит read-back ±0,05 uu. Центр смещён на 0,1–1,3 мм; по окружности стенки 29,68 × 6,03 uu |
| Текстуры | все 2048×2048. BC: sRGB, `TC_Default`. N: не sRGB, `TC_Normalmap`, `bFlipGreenChannel` false. ORM: не sRGB, `TC_Masks`. TeamMask: не sRGB, `TC_Grayscale` | задание: BC sRGB; N — DirectX; ORM и TeamMask линейные |
| MI | родители и значения прочитаны обратно. `MI_KingArthur_H2`: BC/N/ORM/TeamMask, `TeamDye 1`, `TeamDyeGain 5,65`. Командные: `TeamColor` = FromSRGBColor(hex), синий (0,0497; 0,1590; 0,6867) | раскладка волны 4 |
| Сокеты (живая сцена, T-поза) | `Weapon` → `weapon_R`, в пространстве компонента (6,642; 7,671; 37,332). `Head` → `head`, (−0,304; −0,028; 50,057) | цели бейка (6,642; 7,671; 37,332) и (−0,304; −0,028; 50,057) — совпали до 0,001 uu |
| Мастера | `M_UM_Figure` / `M_UM_BaseMarker`: параметры спецификации есть, Opaque, односторонние, без WPO | `um_masters_current` |

**Почему TeamMask в `TC_Grayscale`, а не `TC_Masks`.** Задание допускало «Masks / без потерь каналов». Но сэмплер `TeamMaskTexture` в `M_UM_Figure` имеет тип `LinearGrayscale` (волна 4). Текстура `TC_Masks` дала бы несовпадение типа сэмплера. `TC_Grayscale` хранит G8 без сжатия. При переводе RGBA → G8 UE берёт канал **R**, а не яркость: это строка в `Engine/Source/Runtime/ImageCore/Private/ImageCore.cpp` («blit from RGBA to G8 does NOT grab the gray, it just take the R»). То есть канал ткани, который читает мастер, сохраняется без потерь. G (полоса подставки) мастер не читает: подставка красится по боковой стенке.

**Цвет вершин.** У SK `VertexColorImportOption` = Replace (дефолт UE для скелетных мешей). У FBX атрибутов цвета нет (`color_attributes: []`), поэтому на результат это не влияет.

## Идемпотентность

[`ue-import-idempotency.json`](evidence/w5c-arthur-h2-ue-2026-09-29/ue-import-idempotency.json), журнал прогона:
1. `ue-import` → **executed**, создано 13 ассетов.
2. Повтор без флагов → **skipped**. Отпечаток тот же, листинг папки в редакторе = владеемые ассеты.
3. Прямой MCP `import_file` тех же имён ([already-exists-probe.json](evidence/w5c-arthur-h2-ue-2026-09-29/already-exists-probe.json)): `import_asset: T_KingArthur_H2_BC … already exists` и `SK_KingArthur_H2 … already exists`. Листинг не изменился (13).
4. `--force` → 13 прежних ассетов удалены по владению, 13 созданы заново. Набор тот же, `Name_1` нет, 25/25 проверок.
5. Повтор после `--force` → **skipped**.

Параллельно шёл `--force` Merlin в том же редакторе. Консольные команды не потерялись: перепечаток `editor_python_retype` 0. Оба импорта прошли.

## Кадры: сцена, свет, настройки

Скрипт [`review/h2_ue_review.py`](../../tools/tripo-pipeline/review/h2_ue_review.py) + [`review/ue_py/h2_review_ue.py`](../../tools/tripo-pipeline/review/ue_py/h2_review_ue.py), прогон r3, 13:34–13:39 UTC. Отчёт: [`h2-ue-review-report.json`](evidence/w5c-arthur-h2-ue-2026-09-29/h2-ue-review-report.json).

**Сцена.**
- Контрольный уровень P1.7 `/Game/ArtTests/P17ControlScene/L_P17ControlScene` (доска Cobble). Загружен **в память и не сохранялся**.
- Спрятаны 13 фигур P1.7. Arthur H2 поставлен на свою клетку (0; 50; 0).
- В конце открыт прежний `/Game/S08/S08Arena`. Он не dirty; контрольный уровень после перезагрузки не dirty; 13 ассетов H2 не dirty.

**Свет — профиль `cobble-probe` пакетного клиента** (`S08ArtBoardProfiles.json`, W4-A), применён в памяти:
- ключ 4,5 lux, CSM 3000 uu / 2 каскада, без контактных теней;
- Movable SkyLight из `TC_S08_AmbientDome`, 11,2 (нижняя полусфера не чёрная);
- тёплый точечный 85 cd;
- фиксированная экспозиция EV100 1,3 (объём контрольного уровня);
- точечный заполняющий 700 cd уровня (до W4) выключен.

**Поворот ключа — расхождение, найденное попутно.** Кадры сняты с поворотом ключа редакторного пробника: pitch −55, yaw 30.
- Профиль записывает ключ как `"rotation": [0, −55, 30]`.
- `S08BoardArt.cpp` строит из этого `FRotator(N[0], N[1], N[2])`, то есть Pitch 0, Yaw −55, Roll 30. В пакетном клиенте ключ, по всей видимости, **горизонтальный**.
- Тест `S08BoardArtTests` закрепляет это же прочтение.
- Здесь это только зафиксировано, не исправлено. Отдельная задача предложена оркестратору.

**Рендер.**
- Масштабируемость редактора на время съёмки — High (`sg.* = 2`, эталон приёмки). До съёмки было Epic (3), после восстановлено 3.
- Экранный процент 100, TSR (`r.AntiAliasingMethod 4`), GI и отражения Lumen (1/1).
- Сетка, спрайты и каркасы объёмов скрыты, потом восстановлены.
- Строки `RENDER` (fingerprint) у редакторных кадров нет: это не пакетные кадры.

**FOV.** Вьюпорт уровня рисует с горизонтальным FOV около 35° **независимо от FOV пилотируемой камеры**:
- проба [`fov-probe.json`](evidence/w5c-arthur-h2-ue-2026-09-29/fov-probe.json): камеры FOV 8 и FOV 35, вид сверху с 1500 uu, кадры совпали до шума;
- 5 клеток доски = 1068 px из 2033 → 35,2°;
- `CaptureViewport` лишь сообщает FOV камеры.

Поэтому все виды сняты с FOV 35 (FOV игровой камеры):
- «спереди / слева / сзади» — перспектива с 200 uu, а не орто, как в Blender;
- торс — с 85 uu;
- K2 5× — 386 uu, K2 1,6× — 1207 uu, pitch −55 (камера `UpdateBoardCamera`).

Фигура смотрит на камеру доски (+Y, yaw 90) либо спиной (yaw −90). Кадр — центральный 16:9 из вьюпорта 2033×1216, приведён к 1920×1080.

**Шум.** Прогрев не сошёлся ниже 0,05 (среднее |ΔRGB| между кадрами ≈ 2,2 — временной шум TSR/Lumen). Кадры не побайтные.

**Кадры** (`evidence/w5c-arthur-h2-ue-2026-09-29/`, JPEG q90, у каждого sidecar `*.evidence.json`):
- `arthur-h2-{front,left,back,torso,k2-5x-az0,k2-5x-az180,k2-1p6-az0}-{blue,red}-ue-editor.jpg`;
- `arthur-h2-{front,torso}-buffer-overview-ue-editor.jpg` — обзор G-буфера, команда Blue;
- листы `arthur-h2-sheet-views.jpg` и `arthur-h2-sheet-k2.jpg`: Blender H2.1 (`preview/frames/ortho_*`, `close_torso_az0`, `game_K2S05_az0/180`, `game_K2_az0`) | UE Blue | UE Red.

## Сравнение с Blender H2.1 (честно)

Свет разный:
- Blender: EEVEE, три солнца, тёмный мир;
- UE: небо Cobble 11,2 + ключ сзади-сверху для фигуры, повёрнутой к камере доски.

Поэтому сравнение — по каналам материала, а не по «картинке».

1. **Металл не потерян.** В обзоре G-буфера (`*-buffer-overview-*`): в нижнем ряду 3-я плитка — Metallic, 2-я — Roughness, 4-я — Shading Model. Подписи нижнего ряда срезаны кадрированием 16:9, плитки опознаны по стандартному порядку обзора UE и по содержимому. Плитка Metallic:
   - латы, наручи, поножи, латные кисти, клинок, гарда, корона и золотая отделка — белые (≈ 1);
   - ткань плаща и табарда, лицо, волосы, борода и кожа пояса — чёрные;
   - золотые каймы плаща — белые пятна по подолу (золотая нить, metallic 0,97).

   Это совпадает с классами H2.1 (`preview/h21/classes.jpg`: сталь 1,00, золото 0,98, ткань 0,003). Плитка Roughness: латы темнее ткани (глаже), как в ORM.G (сталь 0,38–0,55, ткань 0,79–0,90). ORM подключён линейно (sRGB off, `TC_Masks`). Ошибки sRGB на ORM нет: проверено и по свойствам, и по буферу.
2. **Сталь в UE почти белая, светлее Blender.** В кадрах спереди, в торсе и на K2 латы читаются как светлый «атласный» металл. В Blender это полированное серебро с тёмными отражениями. Причины:
   - F0 стали 0,52 (плитка Base Color: светло-серый);
   - шероховатость 0,38–0,55 размывает отражение **яркого равномерного неба** (купол 11,2);
   - ключ светит фигуре в спину.

   Это не ошибка текстур. Отчёт H2.1 уже отмечал, что сталь светлее концепта (п. 1 «Что недотягивает»). В UE эффект сильнее. Решение — за пользователем: `metal.steel.bc_target_linear` бейка, `RoughnessMin/Max` MI или свет доски. Сталь станет темнее и после исправления поворота ключа — это проверка для задачи о повороте.
3. **Золото** — тёплое металлическое, как в Blender: корона, гарда, львиные застёжки, ромб на кирасе, каймы.
4. **Нормали не инвертированы** (визуально; численной проверки нет):
   - N — DirectX-вариант бейка (зелёный инвертирован, конвенция в отчёте текстур), `TC_Normalmap`, без флипа;
   - на торсе драконы, узел табарда, кольчуга и чеканка наплечников освещены сверху, как и сама геометрия;
   - перевёрнутых фасок не видно;
   - плитка World Normal непрерывна.

   Инверсию зелёного на этих кадрах я бы увидел как «вдавленный» рельеф на кирасе. Её нет.
5. **TeamColor на одежде работает.** Краситель `TeamDye 1`, gain 5,65 ≈ 1 / яркость цвета. Меняются плащ (снаружи и изнутри), табард и красная подкладка ворота; латы, золото и лицо не меняются.
   - Доля кадра, изменившаяся между Blue и Red (|ΔRGB| > 24): спереди 7,6 %, слева 6,3 %, сзади 12,0 %, торс 7,4 %, K2 5× 2,1 % / 2,8 %, K2 1,6× 0,56 %.
   - Средний цвет изменившихся пикселей спереди: Blue (93; 114; 162), Red (161; 92; 82).
   - Яркость ткани в Red близка к исходному красному: краситель сохраняет яркость.
   - **Замечание:** золотые каймы и вышивка плаща в Blue светлеют до сиреневато-белого, в Red — до розово-оранжевого. Переходные тексели кайм частично входят в маску (R ≈ 0,5 на границе; отчёт H2.1: 1,1 % переходных текселей). Краситель берёт их яркое золото и красит в цвет команды. На K2 это видно как светлая кайма в цвет команды. Решение — сузить маску у кайм или ограничить краситель по яркости. Это предложение; волна 6.
6. **Полоса подставки** — боковая стенка, плоский TeamColor — ярко синяя / красная. На K2 1,6× (фигура ≈ 60 px) команду различает прежде всего она.
7. **Остатки H2.1 видны и в UE.** Щели складки и ровное пятно медальона на спине плаща (кадры back, K2 5× az180) — те же, что в отчёте H2.1. Новых дефектов UE (дыр, чёрных треугольников, мерцающих швов, растяжек UV) на этих кадрах не видно.

## Не проверено / ограничения

- Художественная приёмка, K1/K3, HUD, `boardState`, пакетная сборка и cook папки H2. Кадры — только редакторные.
- Поворот ключа пакетного клиента (см. выше). Кадры сняты с поворотом пробника, пакетный вид может отличаться.
- Анимации: клипов нет, стадия их не импортирует. Капсула выбора.
- Скриншоты редактора не побайтные: временной шум TSR/Lumen ≈ 2,2 уровня.
- Карта `N_OpenGL` и 4K-мастера в UE не попадали, и так должно быть.
- Цвета Blue/Red тестовые. Палитра команд не решена: Q-304, предложение С-11 Gold/Silver.

## Процессы

Остался только общий UnrealEditor PID 31756 (MCP :8123). Он не мой и не перезапускался. Уровень `S08Arena` открыт, как был. Масштабируемость Epic и флаги показа восстановлены. Мои python-процессы завершены. Blender :9876/:9877 и админка :5480 не трогались.

## Коммит

Индексировать строго по манифесту. uasset в `unreal/Unmatched/Content` игнорируются Git: добавлять через `git add -f`. 13 файлов папки `PipelineCandidates/KingArthur/H2` скопированы в арт-worktree байт в байт (sha256 всех 13 сверены).
