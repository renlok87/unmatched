# Merlin (ASSET-MERLIN-001) H2.1: импорт в UE (W5c-A)

Срез: 2026-09-29. Статус: **технически импортировано**. Это не художественная приёмка (её делает волна 6) и не
бюджет: GD-058 открыт, все лимиты ниже — предложение. Платных операций не было: Tripo и SYNTX не вызывались, Blender
не запускался (только `blender --version` в preflight). Редактор общий (UnrealEditor PID 31756, DX12/SM6 + Lumen,
MCP :8123). Он не перезапускался, чужие пакеты не сохранялись, `/Game/UM/Materials/*` только читались.

Вход — H2.1 из [merlin-h2-report.md](merlin-h2-report.md) §11: бейк `merlin-h2-bake/2`, папка
`art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-bake/`. В UE попали `export/SK_Merlin_H2.fbx` (`b1db49c6…`),
`export/SM_Merlin_H2_Base.fbx` (`79132631…`) и четыре рантайм-карты 2K: BC, N, ORM, TeamMask. 4K-мастера и
`TeamMaskRGBA` не импортировались.

## Итог

- В `/Game/PipelineCandidates/Merlin/H2` лежат 13 uasset. Меши: `SK_Merlin_H2`, `SK_Merlin_H2_Skeleton`,
  `SM_Merlin_H2_Base`. Текстуры: `T_Merlin_H2_{BC,N,ORM,TeamMask}`. Материалы: `MI_Merlin_H2` (родитель
  `M_UM_Figure`), `MI_Merlin_H2_Base` (родитель `M_UM_BaseMarker`) и командные `MI_Merlin_H2[_Base]_{Blue,Red}`.
- CLI-стадия `ue-import` прошла **24 из 24 проверок**. `adopt` прошёл **14 из 14**.
- Повторный запуск даёт `skipped`. Импорт на занятое имя отказывает с «already exists». `--force` удаляет свои
  13 ассетов и создаёт те же 13 имён, без `Name_1`.
- Кадры сняты в редакторе на свету Cobble (контрольная сцена P1.7): вид спереди, сбоку, сзади, игровой ракурс K2
  (1,6× и 5×), командные цвета синий и красный.
- Потерь металла и шероховатости нет: ORM читается линейно, металл есть только на пряжке. Нормали не инвертированы:
  A/B с зелёным каналом подтверждает DirectX.
- Копия uasset в арт-worktree совпадает побайтно (sha256 13 из 13).

## 1. Как воспроизвести (CLI, профиль импорта H2)

Новый профиль прогона в `tools/tripo-pipeline/tripo_pipeline.py` 0.7.0 называется `skeletal-adopt`. Логика лежит в
модуле [`skeletal_adopt.py`](../../tools/tripo-pipeline/skeletal_adopt.py). Стадии: `preflight → adopt → ue-import`.

- `adopt` ничего не копирует. Он сверяет sha256 FBX и 2K-карт с отчётами бейка (`reports/build-report.json`,
  `reports/textures-report.json`) и проверяет, что все карты уровня `runtime_2k`. Ещё он проверяет конвенции карт
  (N — DirectX, ORM — R AO / G roughness / B metallic, TeamMask линейная), экспорт по UM_FBX_v1 (задокументированные
  отклонения `path_mode`/`bake_anim` допустимы) и скелет UM_HUMANOID_17_v2 (имена и родители всех 17 костей, объект
  `SKEL_UM_Humanoid`). Кроме того, сверяются масштаб round trip 1, лицо +X, слоты, треугольники и прогнозы сокетов.
- Отчёты бейка разных героев устроены по-разному. `adopt` приводит их к «видам» `build` и `atlas`, которые читает
  та же функция импорта, что у skeletal-candidate (`exec_ue_candidate`): текстуры, MI от UM-мастеров, legacy
  FbxFactory, сокеты, проверки. Формат отчёта задаёт профиль (`candidate.report_format`, JSON-указатели RFC 6901).
- В этой волне добавлен замер в редакторе: число LOD и треугольников через GeometryScript (`UE_PY_MEASURE_SKELETAL`).
  Его включает флаг профиля `ue.measure_skeletal_triangles`. У маршрута skeletal-candidate без флага поведение
  прежнее.

Профиль: [`merlin-h2-ue-import.json`](../../art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-h2-ue-import.json)
(`merlin-h2-ue-import/1`). Прогон:
[`20260929-h2-ue-import/`](../../art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-ue-import/).

```bash
RUN=art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-ue-import
TP="python tools/tripo-pipeline/tripo_pipeline.py"
$TP init --run-dir $RUN --asset-id ASSET-MERLIN-001 --primary-source tripo-de0654b5-h2 --primary-role h2-parts-glb \
    --profile skeletal-adopt --build-profile art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-h2-ue-import.json \
    --export-basename SK_Merlin_H2
$TP register-source --run-dir $RUN --spec art/pipeline-candidates/ASSET-MERLIN-001/source-specs/tripo-de0654b5-h2.json
$TP preflight --run-dir $RUN && $TP adopt --run-dir $RUN          # headless: Blender :9876 не трогается
MSYS_NO_PATHCONV=1 $TP --backend mcp ue-import --run-dir $RUN --ue-folder /Game/PipelineCandidates/Merlin/H2
```

`MSYS_NO_PATHCONV=1` нужен только в Git Bash: иначе `/Game/...` превращается в путь `C:/Program Files/Git/Game/...`
и CLI отказывает (проверка корня папки). Preflight и adopt идут с `--backend headless`: при `--backend mcp` preflight
опрашивает живой Blender :9876, а его трогать нельзя.

Тесты: `python -m unittest discover -s tools/tripo-pipeline/tests`. Новый файл
[`test_skeletal_adopt.py`](../../tools/tripo-pipeline/tests/test_skeletal_adopt.py) (12 тестов) покрывает указатели,
кадры UM_FBX_v1, полосу треугольников и компиляцию встроенных скриптов редактора. Он проверяет полный путь
adopt → ue-import → skipped → `--force` без `_1` на фейковом редакторе. Проверены и отказы: чужие байты FBX,
OpenGL-нормаль или 4K-уровень, неверный родитель кости, файл, изменённый после adopt, недостача треугольников,
неизвестный формат отчёта. `fake_unreal_mcp.py` научился читать отчёт H2-бейка и эмулировать замер треугольников.

## 2. Проверки в UE (MCP, отчёт `reports/ue-import-report.json`, прогон `--force`)

| Что | Измерено в UE | Ожидание | Итог |
|---|---|---|---|
| Кость 0 | `SKEL_UM_Humanoid` (объект арматуры), 18 костей = 17 v2 + кость 0 | legacy FBX-импорт (ue-pipeline-traps п. 2) | pass |
| Кости v2 | 17 из 17, иерархия совпадает; `weapon_R` под `hand_R` | rig-contract UM_HUMANOID_17_v2 (Merlin: weapon.R) | pass |
| Сокеты | `Weapon` → `weapon_R` (0, 0, 0); `Head` → `head` (−0,121; −1,448; 2,588) | прогноз бейка | pass |
| Сокеты вживую (актёр в сцене) | Weapon (0,732; 8,048; 32,937), Head (2,666; 0,124; 36,712) в пространстве компонента | цели бейка (0,732; 8,048; 32,937) / (2,666; 0,124; 36,712) | Δ < 0,001 uu |
| Лицо +X | границы UE min (−10,302; −12,118; 4,759), max (7,896; 11,504; 49,422); единственная карта осей «−Y Blender → +X» | UM_FBX_v1: +X | pass (ошибка 0,0004 uu) |
| Посох | сторона +Y UE (max y 11,50 против −10,30 спереди) | `expected_ue_weapon_side` +Y | pass |
| Рост | верх капюшона 44,986 uu (профиль 45,0); верх скелетного меша (кристалл) 49,422 uu | допуск 0,05 uu | pass |
| Подставка | 24 × 24 × 5 uu, pivot в центре низа, 2 240 tris, 1 слот | профиль | pass |
| LOD / треугольники | 1 LOD, 1 секция; LOD0 **33 967** tris (GeometryScript) = 30 047 + 3 920 бейка | полоса 33 964–33 967 (минус 3 вырожденных) | pass |
| Слоты | 1 слот `M_Merlin_H2_Atlas` → `MI_Merlin_H2_Blue` | 1 | pass |
| Импорт | FbxFactory, `FBXNIM_ImportNormals`, Nanite выкл., без материалов и текстур импортёра | memo §1 п. 5 | pass |
| Текстуры | все 2048²; BC sRGB, TC_Default; N sRGB выкл., TC_Normalmap, `bFlipGreenChannel` false; ORM sRGB выкл., TC_Masks; TeamMask sRGB выкл., TC_Grayscale | профиль | pass |
| MI | `MI_Merlin_H2`: родитель `M_UM_Figure`, BC/N/ORM/TeamMask свои, TeamDye 1, TeamDyeGain 5,5; `MI_Merlin_H2_Base`: `M_UM_BaseMarker`, SideBandWeight 1; Blue (0,0497; 0,1590; 0,6867), Red (0,6308; 0,0595; 0,0423) = FromSRGBColor(#3F6FD8 / #D0453A) | ±1e-4 | pass |
| Мастера | параметры спеки есть, Opaque, one-sided, без WPO | `um_masters_current` | pass |
| Сохранено | 13 ассетов, ни один не dirty | — | pass |

TeamMask остался одноканальным (L8). Сжатие TC_Grayscale хранит его без потерь (G8), канал R, который читает
`M_UM_Figure`, не теряется. Так же было в W4-B. RGBA-вариант не нужен: полосу подставки `M_UM_BaseMarker` берёт из
нормали боковой стенки. TeamDyeGain оставлен 5,5. Средняя яркость ткани H2.1 (линейный BC, маска ≥ 0,5) — 0,0263
против 0,0269 у атласа W4-B, а формула W4-B дала бы 5,58 (+1,5 %).

Сравнение с предложенными лимитами (не бюджет): фигура 33 967 tris (с подставкой 36 207) при предложении 30–45 k,
1 слот при предложенном максимуме 2, 2K, рост 45 uu в пределах 40–48.

Лог LogFbx этой стадии содержит и чужие строки: параллельная волна импортировала OBJ-глифы в тот же редактор. Эти
строки не относятся к Merlin.

## 3. Повторный импорт без дублей

Подробности — в [ue-import-idempotency.json](evidence/w5c-merlin-h2-ue-2026-09-29/ue-import-idempotency.json).

0. Первый запуск упал на 2 новых проверках замера (22 остальные прошли). Во встроенный скрипт замера попал
   настоящий перевод строки внутри строкового литерала, и редактор выдал SyntaxError. Скрипт исправлен, добавлен
   тест `test_embedded_editor_scripts_compile`.
1. `ue-import` → **executed**: свои 13 ассетов удалены, импорт выполнен заново, 24 из 24.
2. `ue-import` → **skipped** (отпечаток и листинг редактора не изменились).
3. Проба на занятые имена ([already-exists-probe.json](evidence/w5c-merlin-h2-ue-2026-09-29/already-exists-probe.json)).
   Импорт FBX через редактор: `RuntimeError: import_asset: SK_Merlin_H2 at …/Meshes already exists`. MCP
   `TextureTools.import_file`: `… T_Merlin_H2_BC … already exists`. Листинг не изменился, нумерованных копий нет.
4. `ue-import --force` → executed: удалены те же 13, созданы те же 13, 24 из 24.
5. `ue-import` → **skipped**. Листинги после шагов 1, 2, 4 и 5 совпадают (13 ассетов).

## 4. Кадры (редактор, свет Cobble)

Скрипт: [`review/h2_ue_frames.py`](../../tools/tripo-pipeline/review/h2_ue_frames.py). Он загружает сохранённую
контрольную сцену `/Game/ArtTests/P17ControlScene/L_P17ControlScene` (доска Cobble, её свет, фиксированная
экспозиция EV100 1,3) и ничего в ней не меняет. Фигура W4-B на клетке 3:3 скрывается в памяти, H2 ставится на ту же
клетку временными актёрами. После съёмки открыт прежний уровень (`/Game/S08/S08Arena`, dirty = false), сцена тоже не
dirty. Отчёт съёмки: [h2-ue-frames-report.json](evidence/w5c-merlin-h2-ue-2026-09-29/h2-ue-frames-report.json).

Это **редакторные кадры** (editor-mcp-viewport, `CaptureViewport`, кадрирование 16:9 → 1920×1080, JPEG 1200 px
в evidence). Они не K1/K2-приёмка. RENDER-отпечатка нет: он есть только у packaged-клиента. Скалябилити редактора
(`sg.*`) скрипт не записывал. Редактор работает на DX12/SM6 + Lumen после волны 5a
([w5-editor-dx12-2026-09-29.md](evidence/w5-editor-dx12-2026-09-29.md)), но то, что это эталон High, этими
кадрами не доказано.

- K2 по правилу S08 для клетки 3:3 (ближняя половина, фигура спиной к камере): `k2-1p6-{blue,red}`, `k2-5x-{blue,red}`.
- Игровая камера 5×, фигура повёрнута: `turn-5x-{front,side,back}-{blue,red}`.
- Горизонтальная камера (pitch −8°) для сравнения с Blender: `eye-{front,side,back}-{blue,red}`.
- Крупные планы (синие): `close-{crystal,face,belt-buckle,robe-front,back-hood}`.
- Листы: [blender-vs-ue-front-right-back.jpg](evidence/w5c-merlin-h2-ue-2026-09-29/sheets/blender-vs-ue-front-right-back.jpg),
  [blender-vs-ue-closeups.jpg](evidence/w5c-merlin-h2-ue-2026-09-29/sheets/blender-vs-ue-closeups.jpg),
  [k2-grid.jpg](evidence/w5c-merlin-h2-ue-2026-09-29/sheets/k2-grid.jpg) (K2 1,6×, K2 5×, 5× спереди синий и красный),
  `normal-ab-*.jpg`.

### 4.1 Сравнение с кадрами Blender H2.1 (§11.3 отчёта бейка)

Blender-кадры сняты ортокамерой в EEVEE со светом превью, UE-кадры — перспективой в Lumen на свету Cobble. Поэтому
сравнивается только характер материалов, а не яркость.

- **Металл и шероховатость сохранились.** В редакторе снят обзор буферов (`ShowFlag.VisualizeBuffer`; редактор
  игнорирует `r.BufferVisualizationTarget` и показывает сетку 4×4). Калибровка: Specular 0,5 даёт 186, то есть тайл
  = линейное значение в sRGB-кодировке. Результаты — в
  [material-channels.json](evidence/w5c-merlin-h2-ue-2026-09-29/material-channels.json):
  - roughness кристалла: медиана тайла 112 при ожидании 116 для линейного ORM (0,176). Если бы ORM ошибочно
    читался как sRGB, было бы 45;
  - roughness пряжки: 181 (ожидание 178, при sRGB-ошибке было бы 114);
  - roughness мантии: 248 (ожидание 250);
  - Metallic: 784 пикселя одного пятна (> 0,5) в рамке пряжки, медиана 246; по остальной фигуре p99 32 (≈ 0,014
    линейно). Металл есть только там, где его поставил класс H2.1.
- **Кристалл** в UE глянцевый, с узкими бликами по граням, «молочной» плёнки нет — как H2.1 в EEVEE. Свечения и
  прозрачности нет (рекомендация бейка §11.4 не реализовывалась).
- **Пряжка** даёт бронзовые блики на фоне матовой кожи. **Вышивка** — ткань с лёгким блеском, металлом не стала.
- **Лицо под капюшоном** читается и в крупном плане, и при 5× спереди. На K2 1,6× оно — несколько пикселей, как и в
  Blender.
- **TeamColor**: синий и красный окрашивают мантию, капюшон и рукава (маска одежды) и боковую ленту подставки. Кожа,
  борода, посох, кристалл и башмаки не меняются. В красном варианте часть золотой вышивки тоже слегка розовеет: у
  мягких краёв маски R она лежит поверх ткани. Это наблюдение для арт-трека, не дефект импорта.

### 4.2 Нормали (DirectX, A/B)

Импортированная N имеет `TC_Normalmap`, `bFlipGreenChannel` false, в отчёте бейка — DirectX. Для A/B у текстуры в
памяти включили `bFlipGreenChannel` (прочтение OpenGL) и пересняли пять крупных планов. Потом значение вернули
(прочитано: false) и текстуру пересохранили. Средняя разница кадров — 3–18 единиц на канал. Листы
[normal-ab-back-hood.jpg](evidence/w5c-merlin-h2-ue-2026-09-29/sheets/normal-ab-back-hood.jpg),
[normal-ab-face.jpg](evidence/w5c-merlin-h2-ue-2026-09-29/sheets/normal-ab-face.jpg),
[normal-ab-belt-buckle.jpg](evidence/w5c-merlin-h2-ue-2026-09-29/sheets/normal-ab-belt-buckle.jpg): слева
импорт, справа перевёрнутый зелёный.

На импортированном варианте звезда на спине и кайма капюшона выпуклые, свет сверху падает на их верхние грани,
складки гладкие. У перевёрнутого света на верхних гранях звезды нет, по спине идёт тёмная «складка», на кайме
капюшона и по швам UV видны изломы освещения. Значит, импорт читает нормали верно, инверсии нет. Это визуальная
оценка по кадрам, численной метрики для рельефа нет.

## 5. Копия в арт-worktree

13 файлов из `unreal/Unmatched/Content/PipelineCandidates/Merlin/H2/` скопированы в
`C:/Users/ren/.codex/worktrees/art-foundation/unmached/unreal/Unmatched/Content/PipelineCandidates/Merlin/H2/`.
sha256 совпадают по всем 13 (например, `SK_Merlin_H2.uasset` `48974c54…`, `T_Merlin_H2_N.uasset` `d7c47215…` — после
пересохранения в A/B). Мастера `/Game/UM/Materials/M_UM_*` в арт-worktree уже есть. Content игнорируется git,
поэтому uasset добавляются через `git add -f`.

## 6. Что не делалось и что открыто

- Художественная приёмка, K1–K3 с HUD и boardState, packaged-кадры с RENDER-отпечатком, ACC-022 — не делались.
- Клипы анимации и деформация в UE не проверялись: в прогон клипы не импортировались. Риг проверен бейком
  (`rig_deform_probe` 7/7).
- LOD не создавались (1 LOD, предложение). Капсула выбора не проверялась.
- Палитра Blue/Red диагностическая, Q-304 открыт. Сокет StaffTip не создан (AD-CNF-59 открыт).
- Свечение кристалла и тёмная античная бронза пряжки — решения арт-трека (отчёт бейка §11.4, §11.6).
- `/Game/PipelineCandidates` не кукается (нет в `DirectoriesToAlwaysCook`).

## 7. Состав коммита и зависимости

Манифест коммита самодостаточен: если коммит W5c-A идёт раньше или отдельно, в дереве не остаётся ссылок на
незакоммиченные файлы.

- **Бейк H2.1 Merlin (зависимость).** `adopt-report.json` и `ue-import-report.json` фиксируют sha256 восьми файлов бейка:
  `20260929-h2-bake/export/SK_Merlin_H2.fbx`, `SM_Merlin_H2_Base.fbx`, `textures/T_Merlin_H2_{BC,N,ORM,TeamMask}_2K.png`,
  `reports/build-report.json`, `reports/textures-report.json`. Перепроверено 2026-09-29: байты совпадают, 8/8.
  Чтобы папка бейка не оказалась в полусостоянии (новые FBX при старых превью и отчётах), в манифест включён весь
  набор H2.1 Merlin — 58 файлов, тот же список, что у задачи H2.1 (`C:/tmp/h21_merlin/manifest.sorted`). Если набор
  H2.1 уже закоммичен, повторный `git add` этих файлов ничего не меняет.
- **Общий с Arthur (W5c) код.** `skeletal_adopt.py` содержит формат `h2-bake-arthur/1` и на каждом adopt импортирует
  `skeletal_adopt_formats.py`; `tests/fake_unreal_mcp.py` умеет rig-report Arthur. Эти файлы коммитятся одной версией
  вместе с тестом `tests/test_skeletal_adopt_arthur.py`. Тест работает на синтетической фикстуре, а проверка
  настоящего бейка Arthur пропускается, если его файлов нет в checkout. Второй манифест должен ссылаться на те же
  байты; менять эти файлы между двумя коммитами нельзя.
- **Кадры.** `docs/art-pipeline/evidence/w5c-merlin-h2-ue-2026-09-29/` — 69 файлов, 6,7 МБ, самый крупный 432 КБ.
  В манифесте они перечислены поимённо.
- **uasset.** 13 файлов `unreal/Unmatched/Content/PipelineCandidates/Merlin/H2/**` в главном checkout и в арт-worktree
  (`git add -f`: `Content/` игнорируется `unreal/Unmatched/.gitignore:8`). sha256 совпадают 13/13.
