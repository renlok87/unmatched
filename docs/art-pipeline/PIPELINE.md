# tripo-pipeline: исполнимый каркас пайплайна (P0.3 / T3)

Срез: 2026-09-29. Инструмент: `tools/tripo-pipeline/tripo_pipeline.py`, версия 0.6.0.

- T4 добавил профиль `skeletal-candidate` (раздел [Профиль skeletal-candidate](#профиль-skeletal-candidate-t4)).
- Этап 3, T2.1 добавил профиль `static-candidate` для статических пропсов (раздел [Профиль static-candidate](#профиль-static-candidate-этап-3-t21)).
- После P0-ревью каждый FBX инструмента пишется по пресету **UM_FBX_v1** (раздел [Оси и FBX-пресет UM_FBX_v1](#оси-и-fbx-пресет-um_fbx_v1)).
- Этап 3, T3.3 (0.5.0): сборка skeletal-candidate целиком задаётся профилем (`build.flow`: `whole-figure` — Medusa T4,
  `seated-parts` — герои). Medusa, King Arthur, Merlin и Harpy собираются CLI без собственных скриптов, `build` в manifest —
  `completed`, FBX и атлас байт в байт равны прежним кандидатам (раздел [Сборка по профилю](#сборка-по-профилю-050-этап-3-t33)).
- Этап 3, T3.1: UE-стадия кандидата `ue-candidate/6` (сокеты на костях с точкой, вершинные цвета подставки vertex-mask),
  герои импортированы в живой UE, контрольная сцена P1.7 и пошаговая инструкция
  [ADDING-AN-ASSET.md](ADDING-AN-ASSET.md) (проверена сухим повтором на бочке).
- Волна 4, W4-B (0.6.0, 2026-09-29): мастер-материалы `M_UM_Figure` / `M_UM_BaseMarker` / `M_UM_GameLayer` строятся
  скриптом `um_masters.py` (раздел [Мастер-материалы M_UM_*](#мастер-материалы-m_um-060-волна-4-w4-b)); UE-маршрут
  `um-master` (MI от мастеров, цвета команд hex → `FLinearColor::FromSRGBColor`), TeamColor на одежде по `TeamMask`
  (решение пользователя 2026-09-28, AD-CNF-58 = b), запечённый AO в `ORM.R` (`atlas.ao_bake`, гейт «не константа»),
  импорт мешей и клипов с явной legacy `FbxFactory`, проверки `nanite == false`, метода нормалей, родителя MI
  (`ue-candidate/7`, `ue-static-candidate/2`).

Нужны Python 3.10+ (stdlib) и Blender 5.2 для стадий `import`/`export`/`build`.

Статусы в этом документе и в файлах инструмента разделены строго:

| Статус | Что значит | Кто ставит |
|---|---|---|
| предложено | план, норматив или параметр без проверки | документ/человек |
| измерено | число получено инструментом из файла | `verify`, `export`, `ue-import` |
| технически импортировано | файл прочитан/записан без ошибок, проверенные контракты прошли | `export` (`technically_exported_not_art_accepted`), `ue-import` (`technically_imported`) |
| художественно принято | решение арт-трека по кадрам и акту | **никогда не этот инструмент** |

Никакое число из отчётов (треугольники, размеры, число слотов) не является бюджетом: бюджеты
04 §1 / 17 §4.5 остаются предложением до решения GD-058.

## Что делает и чего не делает

Делает:

- регистрирует **уже существующий** результат Tripo (task id, Studio или API, версия модели,
  параметры, наблюдённый расход кредитов, SHA-256 каждого файла) без сетевых вызовов;
- проводит локальные стадии профиля (`preflight → import → verify → export` или `… → atlas → build`) и (только через
  MCP) `ue-import`; все FBX — по пресету UM_FBX_v1;
- хранит run manifest, журнал стадий, хеши входов и выходов, версии Blender и инструмента;
- повторный запуск ничего не пересобирает и не переписывает, если отпечатки стадии и хеши выходов не
  изменились; экспорт с теми же байтами не создаёт второй записи;
- продолжает прерванный прогон (`resume`) с первой незавершённой стадии.

Не делает:

- не обращается к Tripo (нет API-клиента, нет автоматизации Studio; `preflight` проверяет, что в
  `tripo_pipeline.py` нет сетевых импортов). Генерация представлена только **пакетом входов**
  `prepare-generation --dry-run`; без `--dry-run` команда отказывает;
- не ставит «художественно принято», не объявляет бюджеты, не принимает Medusa;
- не пишет в `blender/ASSET-MEDUSA-001/`, `/Game/ART004`, `/Game/ArtPreview`; исходники Tripo
  только читаются и хешируются;
- не запускает `UnrealEditor-Cmd` (пока пользовательский редактор держит проект, это запрещено);
  UE-стадия работает только через живой редактор по MCP.

## Оси и FBX-пресет UM_FBX_v1

**Стандарт** — 04-blender-production.md §1 «Оси» и §1.1. Это проверенный пресет
`blender/_tools/presets/UM_FBX_v1.json` (ART-001 PASS 2026-09-27: стрелка +X, root motion +100 uu по X), а не предложение.
Правило: в Blender лицо смотрит в −Y, в UE — в +X.

С версии 0.4.0 так пишутся оба FBX-выхода инструмента:

- `export` (passthrough);
- `build` (skeletal-candidate).

Что делает экспорт:

- копия данных в памяти поворачивается на `export_space_rotation_z_degrees` = +90° вокруг Z; поворот снапится к точной перестановке осей;
- данные умножаются на 100, экспорт с `FBX_SCALE_UNITS`, −Y вперёд, Z вверх, **Triangulate**, сглаживание FACE, без leaf bones;
- `UnitScaleFactor` патчится в 1.0.

UE отображает кадр экспорта Blender как `(x, −y, z)` (ART-001). Поэтому авторское −Y становится +X в UE, а авторское +X
(у Medusa — лук, левая рука) становится −Y.

- Путь к пресету — поле `fbx_preset` профиля сборки (обязательно для `skeletal-candidate`). Passthrough всегда берёт
  `blender/_tools/presets/UM_FBX_v1.json`.
- SHA-256 пресета входит в отпечатки `export`/`build`: правка пресета пересобирает стадию.
- `preflight` проверяет пресет (`fbx_preset_is_um_fbx_v1`: имя, +90°, Triangulate). Профиль без `fbx_preset` не проходит preflight.
- Кости `build` поворачивает через `EditBone.transform(roll=True)`: rest-поза жёстко поворачивается вместе с мешем, поэтому
  локальные оси костей и смещения сокетов относительно фигуры не меняются. `batch_export.py` из ART-001 двигает только
  head/tail. Для вертикальных костей это разные локальные X/Z. Конвенцию нужно закрепить в контракте рига P1.6.
- Round-trip меряется дважды:
  - в кадре экспорта: нормаль лица должна смотреть вдоль повёрнутого фронта (`export_frame_face_points_along_rotated_front`);
  - после обратного поворота — в авторском кадре: все прежние проверки и сравнение с неповёрнутым эталоном v2.
- Записанные отклонения от пресета:
  - `build`: `path_mode=STRIP` вместо `AUTO` (в FBX только имена текстур; текстуры идут в UE из стадии atlas); без `bake_anim`, клипов нет;
  - `export` (passthrough): `path_mode=COPY` + `embed_textures`, потому что passthrough переносит собственные текстуры Tripo.
- Известное отклонение ассетов: производственные `SK_Medusa` / `SK_Medusa_Atlas`, v2 и v3 собраны без поворота и смотрят в
  UE в **+Y**. Код S08 (`S08FighterActor.cpp`) рассчитан на +Y. Это задача арт-задачи 2 (поворот в игре или переэкспорт),
  см. [medusa-local-pass-report.md](medusa-local-pass-report.md#оси-стандарт-измерение-отклонение-производственного-ассета).

## Профиль skeletal-candidate (T4)

Профиль прогона задаётся при `init`:

- `--profile passthrough` — по умолчанию, T3: статический FBX геометрии Tripo как есть (оси — UM_FBX_v1);
- `--profile skeletal-candidate --build-profile <JSON>` — T4: игровой кандидат.
- `--profile static-candidate --build-profile <JSON>` — этап 3, T2.1: статический пропс, собранный вне CLI.

От профиля зависит набор стадий:

| Профиль | Стадии |
|---|---|
| passthrough | preflight → import → verify → export [→ ue-import] |
| skeletal-candidate | preflight → import → verify → atlas → build [→ ue-import] |
| static-candidate | preflight → adopt [→ ue-import] |

Стадия чужого профиля отказывает с кодом 2 (`stage export is not part of profile skeletal-candidate`).

### Профиль сборки

Схема `unmatched.tripo-pipeline.build-profile/1`, статус «предложено». Всё, что для Medusa было зашито в код,
здесь записано данными:

- части тела, лука и подставки;
- высота фигуры и габарит подставки;
- кости (голова и хвост в метрах);
- правила весов по частям: `bone`, `blend`, `split_z`;
- ожидаемые вывернутые части и порог оценки ориентации;
- лицевой слот и сокеты;
- имена ассетов и текстур в UE, инстансы TeamColor;
- `fbx_preset` — FBX-пресет (UM_FBX_v1), обязателен;
- `axes.expected_ue_front` — ожидаемый фронт в UE (+X по 04 §1). Это проверка, а не сравнение;
- эталоны только для чтения:
  - FBX v2 и закоммиченный атлас;
  - UE-ассет для сверки осей: `ue.reference_skeletal_for_axes`, где указаны `asset` и `ue_front`
    (для Medusa — производственный `/Game/ART004/Medusa/Meshes/SK_Medusa_Atlas`, `ue_front` +Y);
- «предложенные пределы» — они попадают в отчёт как сравнение, а не как проверка.

Профили:

- Medusa — `art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-segmented-skeletal-um-fbx-v1.json` (`/2`,
  flow `whole-figure`);
- `medusa-segmented-skeletal.json` (`/1`) — запись исторического прогона `20260928-t4-local-pass`. В нём нет `fbx_preset`,
  поэтому инструмент (с 0.4.0) его не принимает. Профили, по которым уже прошёл прогон, не правятся: новая версия — новый файл;
- герои — `<hero>-segmented-skeletal-um-fbx-v1-cli.json` (`/2`, flow `seated-parts`) в `build-profiles/` King Arthur,
  Merlin и Harpy. Их `/1` (`*-um-fbx-v1.json`) — запись прогонов `20260928-blender-um-fbx-v1`, собранных собственными
  скриптами героев; `/1` оставлены без изменений, CLI их не принимает (ключ `builder`, preflight `build_profile_schema`);
- исключение из правила: в Medusa `/2` в 0.5.0 **добавлены** ключи `build`, `anatomy` (`face`, `neck`) и
  `reference.parts_fixed_in_reference`. Они только называют части, которые 0.4.0 держал в коде (лицо `tripo_part_10`, шея
  `tripo_part_14`); контракт и `profile_id` не изменились, пересборка даёт те же байты FBX (T3.3). Отпечатки стадий
  прогона `20260928-t4-um-fbx-v1` от этого устарели: следующий `run` там переисполнит atlas/build с теми же байтами.

Хеш профиля входит в отпечатки стадий `atlas`, `build` и `ue-import`. Правка профиля пересобирает эти стадии,
но файлы с теми же байтами не дублируются.

### Стадия atlas

Работает в Python с Pillow и numpy (`candidate/atlas.py`, отдельный процесс). Это порт
`pack_segmented_atlas.py`: текстуры частей GLB упаковываются в атлас 2048.

- BC умножается на baseColorFactor.
- Normal пишется в двух вариантах: OpenGL и DirectX (с инвертированным G).
- ORM: R — заливка AO, G — roughness, B — metallic.

Проверки:

- ячейки не пересекаются, зазор ≥ 2·inset;
- DirectX = OpenGL с инвертированным G;
- длина векторов нормалей;
- R = заливка AO;
- побайтовое сравнение с эталонным атласом.

Опции профиля (0.5.0; без них — поведение 0.4.0, те же байты):

- `atlas.exclude_parts {part: причина}` — части вне атласа (Harpy: подставка Tripo заменена параметрической, иначе 9 частей не
  входят в 2K без уменьшения);
- `atlas.normal_renormalise: true` — нормали перенормируются к единичной длине после ресайза (карты Tripo единичны на
  97,6–99,9 %, LANCZOS при увеличении выходит за 1); почти нулевые тексели → (0, 0, 1);
- `team_color.mask` — необязательная маска TeamColor (8 бит, линейная) по BC-атласу, выход атласа `TeamMask`:
  `hsv-hard-gaussian` (Arthur: красная ткань, оттенок ≥ 340° или ≤ 10°, размытие Гаусса) или `hsv-smooth-box` (Merlin:
  бронза, плавные пороги, только внутренние прямоугольники указанных ячеек, blur 3×3). Статус — предложено (AD-CNF-58).
- (0.6.0) `team_color.mask.method: hsv-band-cells` — произведение необязательных плавных полос `hue_deg`, `s_min`/`s_max`,
  `v_min`/`v_max` (рампа `ramp`) внутри внутренних прямоугольников ячеек `cells`, blur 3×3. Medusa: платье — ячейка
  `tripo_part_0`, `v ≤ 0,3`, `s ≤ 0,4` (бронзовые вкрапления с `s > 0,45` отпадают; покрытие ячейки 98 %); Harpy (ткани
  нет): тёмные маховые перья ячеек крыльев `tripo_part_0/1`, `v ≤ 0,22`; Merlin (исправление ревью W4-B): синяя ткань —
  мантия `tripo_part_0`, капюшон `tripo_part_2` (без лица и бороды), рукава `tripo_part_4/5`, оттенок 205–250°, `s ≥ 0,12`
  (покрытие ячеек 75 / 59 / 95 / 98 %; бронзовая отделка остаётся бронзой). Маска Arthur (T3.3) пересобрана тем же
  правилом — байт в байт; маска Merlin T3.3 (только бронзовая отделка, 8,5 % ячейки мантии) одежду не покрывала и в
  профиле `/3` заменена. AD-CNF-58 закрыт решением пользователя (b): база, кольцо и одежда.
- (0.6.0) `atlas.ao_bake {samples, distance_rel, margin_px, seed, gate}` — `ORM.R` = ambient occlusion, запечённый
  Cycles на CPU (`blender/bake_ao.py`, всегда отдельный headless-процесс, и при `--backend mcp`: он даёт байты) в
  собственный UV каждой части, размер = размер BC части; вся фигура — окклюдер (рука над плащом, ступни на подставке),
  `meshes.drop_parts` из окклюдеров убираются. Ориентация граней при запекании — та же, что в build, и в том же порядке
  (грань, смотрящая внутрь, запекается затенённой: её лучи AO начинаются внутри фигуры): (1)
  `orientation.per_face_reference` (часть со смешанной намоткой — голова Harpy `tripo_part_2`): голоса граней против
  high-poly GLB, сглаживание ICM на сваренной копии части в кадре посадки build (дистанция `weld.distance_m`, масштаб
  фигуры как во flow seated-parts), переворот тех же граней, что в build (код `candidate_build.orientation`,
  `mesh_ops.weld_part`, `core.flip_polygons`; для Harpy — те же 1 506 из 1 918 граней, 5 несогласованных рёбер, как в
  build-report); (2) части `orientation.expected_inside_out_parts` переворачиваются целиком (без этого вывернутая часть
  запекается чёрной — Medusa, рука `tripo_part_8`: 0,12 вместо 0,71). После переворотов тест ray-escape build
  (`measure.orientation_scores`) идёт по сцене запекания с плоскостью «пола» под фигурой только для теста (без неё
  лучи из открытых подошв ступней Harpy уходили вниз и давали ложные 4–7 % «внутрь»); доля площади «внутрь» каждой
  запечённой части — в `ao-bake-report.json → orientation_after_flips`. Тексели вне UV-островов (дальше `margin_px`)
  остаются 1,0 (чёрный фон подмешивался бы в края на мипах). ORM-тайл части строится в размере AO (RM ресайзится
  LANCZOS). Проверку `orm_occlusion_channel_filled` заменяют два гейта: `orm_occlusion_baked_not_constant` (внутри ячеек:
  `p99 − p1 ≥ 32` и доля `< 250` не меньше 2 %) и `ao_bake_parts_face_outward` (у каждой запечённой ячейки доля площади
  «внутрь» ≤ `gate.max_inward_area_fraction`, по умолчанию 0,02). Пороги — `atlas.ao_bake.gate`, предложено. Находка
  ревью W4-B: первый гейт диапазона пропустил голову Harpy, запечённую на 40 % площади «внутрь» (AO этих граней 0,50,
  26 % площади ниже 0,25; после исправления 0,82 и 2 %) — поэтому второй гейт. Отчёт `reports/ao-bake-report.json` (хеш
  каждой части, исправление по эталону, ориентация), в отпечатке atlas — хеш `bake_ao.py`, модулей библиотеки build,
  которые он импортирует, эталонного GLB и версия Blender. Повторный прогон даёт те же байты (Cycles CPU, фиксированные
  seed и samples, измерено). ORM.R действует только на непрямой свет и SkyLight (критика меморандума G03): в сцене без
  SkyLight кадр от него не меняется.

Выход: `textures/*.png`, `reports/atlas-report.json` [+ `reports/ao-bake-report.json`].

### Стадия build

Работает в Blender (`blender/build_candidate.py` + библиотека `blender/candidate_build/`), headless или live. Алгоритм
выбирает профиль (`build.flow`, раздел [Сборка по профилю](#сборка-по-профилю-050-этап-3-t33)); ниже — flow `whole-figure`
(Medusa T4, поведение 0.4.0).

Сборка:

1. Импорт GLB, перенос UV частей в ячейки атласа, масштаб к высоте фигуры.
2. Объединение тела; подставка приводится к габариту.
3. **Оценка ориентации каждой части (ray-escape)**: вывернутые части разворачиваются (winding и инверсия
   угловых нормалей), их список сверяется с профилем.
4. Арматура, веса, лук на кость оружия, лицевой слот.
5. Детерминированные FBX скелета и подставки по UM_FBX_v1: поворот +90° по Z (кости с `roll=True`), данные ×100,
   `FBX_SCALE_UNITS`, −Y/Z, Triangulate, `UnitScaleFactor` = 1.0, `path_mode=STRIP`.

Проверки:

- кадр экспорта: лицо вдоль повёрнутого фронта, лук на повёрнутой стороне;
- Triangulate не меняет геометрию (полигонов = треугольников);
- round-trip обоих FBX после обратного поворота: кости, rest-позиции, треугольники, слоты, UV0, веса, ориентация, масштаб 1,0;
- UV0 лежит в своей ячейке; растровое перекрытие и плотность текселей;
- почти вырожденные треугольники (< 1e-4 см²);
- сравнение с эталонным FBX по полигонам: позиции 1e-4 м, UV 1e-5, индекс материала, winding, угловые нормали.
  Угловые нормали сверяются проверкой (|dot| > 0,999). Исключение — углы у вершин почти вырожденных треугольников: их
  нормаль численно не определена и меняется при повороте. Такие углы перечисляются поимённо.

Выход: `export/<skeletal>.fbx`, `export/<base>.fbx`, `work/*-candidate.blend`, `reports/build-report.json`.

### Сборка по профилю (0.5.0, этап 3, T3.3)

До 0.5.0 стадия build умела только Medusa (лук — целая часть GLB на +X, лицо `tripo_part_10`, шея `tripo_part_14`), и
Arthur, Merlin и Harpy собирались собственными скриптами `art/pipeline-candidates/ASSET-*/scripts/build_*_candidate.py`
(их manifest оставлял build `pending`, ue-import не запускался). В 0.5.0 алгоритм этих скриптов перенесён в общую
библиотеку `tools/tripo-pipeline/blender/candidate_build/`, а всё, что в них было зашито, стало ключами профиля.
Скрипты героев остались в своих каталогах как запись прогонов `20260928-blender-um-fbx-v1`; CLI их не вызывает.

Библиотека: `core` (пресет, детерминизм FBX, экспорт, round-trip), `measure`, `mesh_ops`, `weapon`, `closure`, `rig`,
`orientation`, `base`, `anatomy` и `profile_schema` (оба без bpy, их же использует CLI и тесты), `flow_whole_figure`,
`flow_seated`. `build_candidate.py` загружает свежую копию библиотеки на каждый запуск (путь — `params.lib_dir`), поэтому
живой Blender не держит устаревших модулей. Хеши всех модулей входят в отпечаток build; preflight проверяет профиль той
же схемой (`build_profile_schema`) до любой работы Blender.

Ключи профиля flow `seated-parts` (герои):

| Ключ | Что задаёт | Arthur / Merlin / Harpy |
|---|---|---|
| `build.flow` | алгоритм: `whole-figure` (по умолчанию) или `seated-parts` | seated-parts |
| `materials.atlas` | имя Blender-материала атласа (имя слота в FBX) | `M_KingArthur_Atlas` / … |
| `scale.top_part`, `scale.figure_height_m` | высота фигуры = верх этой части над низом подставки; оружие может быть выше | 5 / 2 / 2 |
| `meshes.base.mode` | `normalise-part` (подставка Tripo к габариту отдельно от фигуры) или `parametric` (часть `source_part` выбрасывается, строится `base_parametric`) | normalise / normalise / parametric |
| `meshes.weapon.mode` | `split-from-part` (вырезать из кулака: `weapon_split`), `parts` (собрать из частей: `weapon_assembly`), `part` (целая часть) или `meshes.weapon: null` | split / parts / нет |
| `meshes.drop_parts` | выбрасываемые части | part_14 / — / part_4 |
| `closure` | крышки: `base_top` (дыры под ступнями в верхе подставки), `soles`, `see_through`, `diagnostic_weld_m` | Arthur |
| `open_loop_caps` | веерные крышки перечисленных открытых петель | Harpy |
| `orientation.per_face_reference` | голосование граней по high-poly (источник `source_id`/`role` из manifest) + ICM | Harpy (голова) |
| `armature.bones` | `[name, parent, head, tail]` в финальных метрах или `[…, "source"]` в кадре исходника Tripo | final / source / source |
| `weights.coordinates_frame`, `weights.groups` | кадр рамп и `axis_blend` (`final`/`source`); группы `rigid`, `heat`, `wing_span`, `axis_blend`; рампы, капы | final / source / source |
| `anatomy` | роли частей: `head`, `feet {L, R}`, `weapon_hand`, `feet_sink_m`, признаки фронта (`front`), сторон (`side_indicators`), кадра экспорта (`export_frame_indicators`), `tail`, `capsule_exclude_parts` | все |
| `axes.blender_weapon_side` | сторона оружия в Blender (`-X` — правая рука) | -X / -X / — |
| `sockets[].target` | цель сокета: `bone_head`, `part_bbox_centre`, `foot_tip`; `tip_proposal` — точка на оружии | Head: bbox головы |
| `sockets[].location_uu` | смещение в UE bone space; `null` — берётся прогноз build | Head: null |
| `team_color.mask` | маска TeamColor в стадии atlas | Arthur, Merlin |
| `ue.team_color_mode` | материал фигуры: `multiply` (BC×TeamColor), `mask` (lerp по TeamMask), `none` | mask / mask / none |
| `ue.base_material_mode` | подставка: `atlas-instance` или `vertex-mask` (материал по вершинной маске, инстансы TeamColor — его дети) | — / — / vertex-mask |

Роли частей (`anatomy`) build ещё и определяет по геометрии (голова — часть с самой высокой вершиной; ступни — самая
низкая часть на каждой стороне; рука с оружием — наименьшая часть, в границах которой голова кости оружия; шея — часть
внутри горизонтального контура головы у её нижней половины). В отчёте `anatomy.used/auto/disagreements`: у трёх героев
профиль и геометрия совпали; у Medusa автоопределение лица даёт голову `tripo_part_1`, профиль называет открытую часть
лица `tripo_part_10` (так и задумано).

Высота фигуры отделена от верха меша: отчёт build пишет `figure.figure_top_m` (верх `scale.top_part`) и
`figure.skeletal_top_m` (верх тела и оружия: меч Arthur 60,8 uu, кристалл Merlin 49,7 uu). Сокеты: build пишет цель в
Blender, смещение в пространстве кости Blender и прогноз для UE bone space `(x, −y, z)` (UM_FBX_v1 не корректирует оси
костей, импорт FBX в UE зеркалит Y; согласуется с живым замером Medusa `(0, 0, 4)` → 4 uu вперёд). Прогноз — не замер:
знак вдоль кости проверяется живым `get_socket_location` по `target_ue_component_uu` (задача UE-этапа).

Доказательство (T3.3): четыре прогона `art/pipeline-candidates/<ASSET>/20260928-cli-um-fbx-v1` (CLI 0.5.0, headless) —
FBX и атлас (с TeamMask) байт в байт равны прежним кандидатам, числа геометрии/UV/весов/костей в build-отчётах без
расхождений: [evidence/t33-cli-build-2026-09-28/comparison.json](evidence/t33-cli-build-2026-09-28/comparison.json)
(`review/compare_candidate_runs.py`).

Воспроизводимость из чистого checkout: Medusa — все зарегистрированные исходники в git. Прогоны героев регистрируют все
файлы своих `source-specs/`, в том числе сырой исходник Tripo `20260928-tripo-h31/source/*-h31-*-source.glb`
(61,97–64,63 МБ, по одному на героя). По решению коммита de252a25 эти три файла хранятся локально (sha256 — в
source-specs) и в git не входят, поэтому без них `preflight` (`source_files_present`) в чистом checkout не пройдёт — так
же, как у прогонов `20260928-blender-um-fbx-v1`. Сборка их не читает: import/atlas/build берут `segmented-retopo-glb`,
Harpy ещё `segmented-9-glb` для голосования ориентации; оба в git. Решение (коммит, LFS или отметка «только локально»
в preflight) — за владельцем.

### Стадия ue-import для кандидата

Работает в живом UE через MCP.

Маршрут материала — `ue.material_route` (0.6.0): `own-material` (по умолчанию, поведение 0.5.0: собственный материал
атласа, п. 3 ниже) или `um-master` (W4-B): в папке прогона не строится ни одного Material, создаются

- `ue.figure_instance` — MI от `/Game/UM/Materials/M_UM_Figure`: `BaseColorTexture`/`NormalTexture`/`ORMTexture` атласа,
  `TeamMaskTexture` по `ue.team_color_mode` (`mask` — `TeamMask` атласа, `multiply` — белая `T_UM_Mask_White`, `none` —
  чёрная `T_UM_Mask_Black`), скалярные ручки `ue.figure_parameters` (например `TeamDye 1`, `TeamDyeGain 6` для тёмной ткани);
- `ue.base_instance` — MI от `M_UM_BaseMarker`: текстуры атласа (`base_marker.textures`, у Tripo-подставок) или плоский
  цвет (`vertex-mask`, Harpy), `base_marker.parameters` (`SideBandWeight 1` — полоса команды на боковой стенке,
  `VertexMaskWeight 1` — полоса и метки по вершинной маске), `base_marker.vectors`;
- по одной командной MI на каждую команду `ue.teams` под каждой из двух: `ue.team_instances.figure|base` с `{team}`,
  `TeamColor` = `FLinearColor::FromSRGBColor(hex)` (правило AD-OPEN-39; hex/255 как linear запрещён). Слоты фигуры и
  подставки получают MI команды `ue.default_team`.

Меши (0.6.0, `ue-candidate/7`) импортирует editor-Python-скрипт `UE_PY_IMPORT_FBX` (через консоль редактора, как
`review/ue_live.py`): `task.factory = FbxFactory()` + свой `FbxImportUI`, `normal_import_method = ImportNormals`
(FBX UM_FBX_v1 несут нормали, слоя тангентов нет — UE строит MikkTSpace), `import_uniform_scale 1.0`, Nanite выключен,
вершинные цвета — `Replace` только у подставки `vertex-mask`. MCP `import_file` этих опций не принимает (у SK
по умолчанию был `ComputeNormals`, у производственной ArtPreview Medusa — нормали из FBX: два контракта). Явная
фабрика не даёт AssetTools уйти в Interchange (он включается только у задачи без фабрики), глобальный CVar не трогается.
Исключение измерено на клипах (2026-09-29): импорт **поверх существующего** ассета идёт путём reimport и использовал
Interchange (`InterchangeAssetImportData`) даже с явной фабрикой; поэтому `import_clips.py` удаляет свой прежний клип и
импортирует заново (`legacy_fbx_import` в отчёте), а стадия ue-import всегда удаляет свои ассеты до импорта.
Консоль печатает не надёжно (раздел «Ловушки» ADDING-AN-ASSET §8): команда запускает лаунчер `UE_PY_LAUNCHER`, который
первым делом пишет `<out>.started`; нет файла за 20 с (`TRIPO_PIPELINE_CONSOLE_GRACE_S`) — команда печатается снова (до
5 раз), запущенная — никогда. Созданные ассеты пишутся в manifest сразу после каждого создания: упавшая посреди стадия
не оставляет в папке «чужих» для следующей попытки ассетов.

Действия:

1. Удаляет только свои прежние ассеты: материал-инстансы → меши → скелет → материал → текстуры.
2. Импортирует текстуры профиля с настройками sRGB, компрессии и flip (необязательная `TeamMask` — только если её
   выпустила стадия atlas).
3. Создаёт собственный материал атласа + N + ORM; BaseColor по `ue.team_color_mode`: BC×TeamColor (`multiply`, Medusa),
   lerp(BC, BC×TeamColor, TeamMask.R) (`mask`), BC (`none`). При `ue.base_material_mode: vertex-mask` — ещё материал
   подставки по вершинной маске (полоса команды R, метки G/B по параметру InstanceIndex); инстансы TeamColor тогда
   его дети, фигура получает сам материал атласа. Граф материала подставки собран через MCP, живым кадром не проверен.
4. Импортирует скелетный и статический меши (`import_materials=false`), назначает материалы слотам.
5. Добавляет сокеты: `location_uu` профиля, а если он `null` — прогноз build (`sockets[].location_uu_for_ue`).
   Кость сокета — UE-имя (`foot.R` → `foot_R`; с `ue-candidate/4`, до этого `add_socket` Harpy падал). Сохраняет ассеты.
6. Подставка `vertex-mask` импортируется с вершинными цветами (`ue-candidate/6`). У MCP `StaticMeshTools.import_file`
   такой опции нет (`FbxImportUI` с `VertexColorImportOption = Ignore`): цвета терялись, и подставка Harpy рисовалась
   целиком «горящей» (белая, метки экземпляров не видны; живой кадр T3.1). Поэтому подставку импортирует скрипт
   `UE_PY_IMPORT_STATIC_VERTEX_COLOURS` (с 0.6.0 — общий `UE_PY_IMPORT_FBX` для обоих мешей; те же настройки `FbxImportUI` + `Replace`), который CLI пишет в `.staging/` и
   запускает в живом редакторе командой `py` в консоли (MCP `SlateInspectorToolset` Snapshot/Type, как `review/ue_live.py`).
   Промежуточная версия `/5` меняла class default `Default__FbxStaticMeshImportData` через `ObjectTools.set_properties` —
   это пометило dirty все загруженные StaticMesh (47 пакетов, включая производственный `SM_Medusa_Base`), пакеты
   перезагружены с диска без сохранения; путь отклонён.

Проверки:

- в папке ровно запланированные ассеты, нет `*_N`, классы верные;
- текстуры, граф материала, инстансы (маршрут `own-material`);
- (0.6.0, маршрут `um-master`) `um_masters_current` — у `M_UM_Figure`/`M_UM_BaseMarker` есть все параметры спецификации,
  Opaque, односторонний, без WPO (граф узел за узлом проверяет `um_masters.py verify`);
  `um_instances_parent_textures_values` — родитель каждой MI, её текстуры, скаляры и `TeamColor` (±1e-4 от
  `FromSRGBColor(hex)`), прочитанные из редактора;
- (0.6.0, оба маршрута) `import_legacy_fbx_factory` (фабрика `FbxFactory`, `AssetImportData` — `Fbx*ImportData`),
  `normal_import_method` (`FBXNIM_ImportNormals` у SK и подставки), `nanite_disabled` (`is_nanite_enabled` подставки,
  `NaniteSettings.bEnabled` SK), у `vertex-mask` — `base_vertex_colors_imported_for_mask`;
- 17 костей профиля + кость 0 = узел арматуры; иерархия;
- оси:
  - карта осей Blender→UE по границам, фронт = `axes.expected_ue_front` (`front_axis_as_fbx_preset`). Фигура, симметричная
    слева-направо в пределах допуска (крылья Harpy), совпадает с картой и её зеркалом: границы их не различают, но все
    подходящие карты обязаны вести фронт в одну ось (`skeletal_bounds_match_build_front_unambiguous`);
  - границы UE = предсказание build-отчёта по UM_FBX_v1;
  - единственная карта границ эталонного UE-ассета на границы кандидата переводит фронт эталона во фронт кандидата
    (`reference_front_lands_on_candidate_front`);
- высота по профилю: верх меша в UE = верх скелета из build (`skeletal_top_as_build`), верх `scale.top_part` =
  `scale.figure_height_m` (`figure_height_as_profile`); меч или посох выше фигуры проверку не валят;
- подставка `vertex-mask`: `AssetImportData.VertexColorImportOption = Replace` (`base_vertex_colors_imported`);
- слоты, сокеты (с источником смещения: профиль или прогноз build);
- треугольники и габарит подставки (с учётом вырожденных);
- ассеты не dirty.

Сравнение с предложенными пределами вынесено в отдельный раздел отчёта. Ось лица туда больше не входит: это стандарт 04 §1.

В `config.ue` для этого профиля пишутся фактические флаги импорта мешей `import_materials=false`, `import_textures=false`
(в прогоне T4 там ошибочно стояло `true`: ветка кандидата эти флаги не использовала).

Выход: `reports/ue-import-report.json`, `reports/ue-mcp-calls.json`.

### Поведение UE 5.8 MCP (измерено в T4 и при исправлении)

Фейк в тестах повторяет это поведение.

- `import_file` на занятое имя **отказывает** с ошибкой `import_asset: <Name> at <folder> already exists` и `Name_1` не создаёт.
  - Стенограмма запроса и ответа из живого редактора, снятая в scratch-папке, которая потом удалена:
    [evidence/t4-um-fbx-v1-2026-09-28/ue-import-already-exists-transcript.json](evidence/t4-um-fbx-v1-2026-09-28/ue-import-already-exists-transcript.json).
    Скрипт — `review/ue_already_exists_probe.py`.
  - T3 исходил из обратного допущения: фейк создавал `Name_1`. Это не было проверено и оказалось неверным.
- `AssetTools.delete` удаляет и ассет, на который ссылаются (ссылка обнуляется). Поэтому стадия удаляет только
  свои ассеты, и сначала те, что ссылаются на другие.
- `get_referencers` и `get_dependencies` падают на несохранённых ассетах; стадия их не использует.
- `find_assets` возвращает пакетные пути без `.Name`.
- Ответы приходят в `structuredContent`; короткие имена инструментов работают.
- FBX-импорт превращает объект арматуры Blender в кость 0 (у Medusa 18 костей).
- Треугольники площадью ~1e-7 см² UE выбрасывает при сборке статического меша.
- `ActorTools.set_actor_transform` принимает трансформ в ключе `xform`, не `transform`.
- (T3.1) `StaticMeshTools.import_file` — legacy `FbxFactory` + новый `FbxImportUI` (исходник плагина
  `EditorToolset/Content/Python/editor_toolset/toolsets/static_mesh.py`); вершинные цвета по умолчанию не импортируются
  (`FbxStaticMeshImportData.VertexColorImportOption = Ignore`). Менять class default (`Default__…`) через
  `ObjectTools.set_properties` нельзя: помечает dirty все загруженные ассеты класса.
- (T3.1) UE переименовывает кости с точкой (`foot.R` → `foot_R`); `add_socket` на имя с точкой отказывает
  (`Bone "foot.R" not found`).

### Редакторные кадры

Это не стадия и не приёмка. Скрипты в `tools/tripo-pipeline/review/`:

- `capture_blender_review.py` — живой Blender: исходный GLB рядом с кандидатом, backface culling. Viewport
  восстанавливается, временные данные удаляются.
- `capture_ue_review.py` — живой UE:
  - ставит временных актёров на свободные клетки уровня `L_ART004_MedusaAnimationReview` и снимает
    `CaptureViewport`, потом удаляет актёров и возвращает исходный уровень;
  - отказывает, если открытый уровень не сохранён;
  - использует собственный HTTP-клиент, потому что `unreal_mcp.py` обрезает вывод до 200 000 символов.
  - схема камер рассчитана на меш, смотрящий в +Y (как T4 и производственный ассет); кандидат UM_FBX_v1 смотрит в +X,
    для него есть `--candidate-yaw 90` (поворачивается актёр, не ассет).
- `ue_listing.py` — только чтение: список ассетов папки, сокеты, слоты.
- `capture_ue_axes.py` — живой UE: измеряет, куда смотрит лицо кандидата.
  - Временный актёр стоит с yaw 0 и снимается с +X/−X/+Y/−Y дважды: с обычным материалом и с лицевым слотом, чёрным через
    `OverrideMaterials` компонента (ассет не меняется).
  - Потемневшие пиксели — это видимое с этой стороны лицо.
  - Плюс парные кадры с эталоном только для чтения, в том числе эталон с yaw −90.
  - Scratch-материал создаётся в `/Game/PipelineCandidates/_<Run>AxesProbe` и удаляется вместе с папкой.
- `ue_already_exists_probe.py` — стенограмма `import_file` на занятое имя в scratch-папке (папка удаляется).
- `control_scene.py` (+ `ue_py/control_scene_ue.py`) — контрольная сцена P1.7 (этап 3, T3.1): уровень
  `/Game/ArtTests/P17ControlScene/L_P17ControlScene` собирается с нуля (актёры Cobble из `L_ART005H_CornerReview`
  копируются данными, **не** `duplicate_asset` уровня — он уронил редактор), кандидаты на клетках S04, камера
  UpdateBoardCamera, экспозиция EV100 1,3 объёмом постобработки (откалиброван по вьюпорту), кадры K1/K2 1,6×/5×,
  спереди/сзади, маски силуэтов (в том числе 5× «подставка без фигуры» для сквозных дыр), своп командного MI, тест
  Lunge 0–100 %. Декор (`place_on_surface`) ставится на верх поверхности под своим нижним контуром (лучи GeometryScript
  по видимым статическим мешам; борт Cobble — 5,0 uu), замер — `build.decor_support`. `control_scene_analyze.py` —
  шум E2 по повторам, идемпотентность отчёта, силуэты, командный цвет в сером, анимация, сокеты, посадка декора,
  просветы подставок в кадрах. `repro_compare.py` — сверка
  повторного прогона ассета с исходным (байты, отчёты после нормализации имени прогона), `frames_to_jpeg.py` — PNG-кадры
  с sidecar в JPEG 1200 px для `evidence/`. Порядок — ADDING-AN-ASSET.md.
- (0.6.0) `control_scene.py --asset-set w4b|t31`: `w4b` (по умолчанию) — прогоны `20260929-w4b-um-master` на MI мастеров
  (своп команды меняет все слоты фигуры и подставку), плюс кадр `team-prop-k2-1p6-<имя>` с предложением палитры
  `c11_value_split_proposal` (MI сцены, `TeamColor = FromSRGBColor`); `t31` — ассеты T3.1, для повторной съёмки «до».
  `team_contrast.py --run <cs>/<tag> --out <json> [--derive-dir <dir>]` — команда в сером и при deuteranopia по
  формулам QA-010 (`qa010lib.color`: Y′ Rec.709, Machado 2009) внутри силуэта K2 1,6×: средний и p90 `|ΔY′|`, доля
  пикселей с `|ΔY′| ≥ 8`, ΔE76 после deuteranopia.
- `base_seethrough.py` — сквозные дыры в верхе подставки (headless Blender по FBX подставки и фигуры, 0 кредитов):
  лучи сверху и из камеры −55° с четырёх сторон через диск верха; `base_only` (меш подставки) и `with_figure` (что
  видно при стоящей фигуре), порог-предложение `with_figure` ≤ 0,1 uu². Build-report такие дыры не ловит.

Формат кадров. `capture_ue_axes.py` сразу пишет JPEG 1200 px, q92 (Pillow LANCZOS). `capture_blender_review.py` и
`capture_ue_review.py` пишут PNG: Blender до 1600 px, UE — в разрешении захвата. Такие PNG весят около 1 МБ на кадр.
Перед коммитом в `evidence/` их переводят в тот же JPEG 1200 px, q92 отдельным шагом (сами скрипты этого не делают).
Хэш, размер и разрешение исходного PNG записываются в метаданные кадра (`png_before_jpeg`). Так переведены
22 исторических кадра T4: 20,9 МБ → 2,2 МБ.

### Git Bash и пути /Game

В Git Bash аргументы вида `/Game/...` передавайте с `MSYS_NO_PATHCONV=1`. Иначе MSYS превратит их в
`C:/Program Files/Git/Game/...`: стадия откажет с кодом 2, в редакторе ничего не изменится.

Результат на Medusa: [medusa-local-pass-report.md](medusa-local-pass-report.md) и
[medusa-local-pass-report.json](medusa-local-pass-report.json).

## Мастер-материалы M_UM_* (0.6.0, волна 4, W4-B)

Меморандум engine-gate §1 п. 4 (вне репозитория: `C:/tmp/p0-review/engine-gate-memo.md`). Статус мастеров — «технически
импортировано»; значения ручек и палитра — «предложено». Решения пользователя 2026-09-28: TeamColor ещё и на одежде
(AD-CNF-58 = b), DX12 + Lumen, эталон High — мастерам без разницы (Opaque DefaultLit / Unlit, без Substrate).

| Мастер | Модель | Для чего | Параметры (нейтральные значения по умолчанию) |
|---|---|---|---|
| `/Game/UM/Materials/M_UM_Figure` | DefaultLit, Opaque, односторонний; usage SkeletalMesh + ISM | фигуры, статичный декор | `BaseColorTexture`/`NormalTexture`/`ORMTexture`/`TeamMaskTexture` (белая), `TeamColor` (1), `TeamDye` 0, `TeamDyeGain` 1, `RoughnessMin/Max` 0/1, `NormalStrength` 1, `AOToBaseColor` 0, `Saturation` 1, `ValueLift` 0, `EmissiveIntensity` 1, `RimColor` (1) |
| `M_UM_BaseMarker` | DefaultLit, Opaque; usage ISM | подставки | текстуры (белые/плоские), `BaseColor` (1), `PipColor`, `PipEmissive` 0,35, `VertexMaskWeight` 0, `SideBandWeight` 0, `SideBandNormalZMax` 0,35, `BandKeepsTexture` 0, `InstanceIndex` 0 + ручки Figure |
| `M_UM_GameLayer` | Unlit, Opaque; usage ISM; `EyeAdaptationInverse` | кольца, подсветки, маркеры | `LayerColor` (1), `UseTeamColor` 0, `EmissiveIntensity` 1, `ExposureCompensationAlpha` 1 |

Граф `M_UM_Figure` при нейтральных ручках повторяет граф кандидатов: `BaseColor = lerp(BC, BC × TeamColor, TeamMask.R)`,
DirectX N, `ORM` R/G/B → AO/Roughness/Metallic. `TeamDye 1` меняет `BC × TeamColor` на «краситель»
`TeamColor × luminance(BC) × TeamDyeGain` — для тёмной ткани, где умножение цвета не видно (платье Medusa, перья
Harpy). Полоса команды `M_UM_BaseMarker`: вершинная маска R × `VertexMaskWeight` (Harpy) или боковая стенка
(`|z|` локальной вершинной нормали < `SideBandNormalZMax`) × `SideBandWeight` (Tripo-подставки); метки G/B горят по
`InstanceIndex` 1: G, 2: B, 3: G + B (0 — ни одной).

Custom Primitive Data (одинаково во всех трёх; примитив без CPD читает 0, и 0 везде нейтрален): 0–3 `CPD_TeamColor`
(rgb + a = вес над `TeamColor` MI), 4 `CPD_InstanceIndex` (0 — значение MI), 5–8 `CPD_FxFlash` (rgb + интенсивность),
9 `CPD_RimIntensity`, 10 `CPD_RimWidth` (экспонента Френеля `lerp(8, 1, width)`), 11 `CPD_Fade` (базовый цвет → яркость ×
0,25, без Masked). Masked, Translucent и WPO не используются (проверяется).

Данные — `art/um-materials/um-masters.json` (пути, параметры, CPD, дефолтные текстуры `art/um-materials/textures/*.png`,
палитра `team_palette`: С-11 `#E8C06A`/`#9FC2D8` и предложение `c11_value_split_proposal` `#5A7F9F`). Цвет — только hex
sRGB → `FLinearColor::FromSRGBColor` (`um_masters.hex_to_linear` = таблица `sRGBToLinearTable` движка, расхождение
≤ 3,2e-8).

```bash
python tools/tripo-pipeline/um_masters.py --backend mcp build  --report <report.json> [--force] [--role figure ...]
python tools/tripo-pipeline/um_masters.py --backend mcp verify --report <report.json>
python tools/tripo-pipeline/um_masters.py hex "#E8C06A"        # linear, без редактора
python tools/tripo-pipeline/um_masters.py signature           # SHA-256 канонических графов
```

- `build` импортирует отсутствующие текстуры по умолчанию (`/Game/UM/Materials/Textures`, сохраняет), создаёт
  отсутствующие мастера через MCP MaterialTools (add_expression / set_properties / connect / recompile / save) и сразу
  проверяет их; мастер, чей граф уже равен плану, пропускается (`skipped`). Мастер с другим графом без `--force`
  — отказ (код 3); с `--force` граф перестраивается **на месте** (выражения удаляются и добавляются заново): ассет
  остаётся тем же, MI кандидатов и сцен не теряют родителя (удаление ассета обнулило бы ссылки, ловушка §8).
- `verify` сверяет редактор с планом узел за узлом: класс и позиция в графе (у каждого узла своя), свойства, связи
  (`get_expression_inputs`, с учётом особенности чтения: при двух входах от одного источника UE сообщает выход первого),
  выходы, параметры, раскладку CPD, Opaque/односторонность/usage, отсутствие WPO/Opacity, «не dirty».
- `.uasset` мастеров и текстур лежат в `unreal/Unmatched/Content/UM/**` — Content в `.gitignore`, в коммит только
  `git add -f` (перечисляются в commit_manifest поимённо).

## Профиль static-candidate (этап 3, T2.1)

Кандидат статического пропса собирает `blender/static_prop_candidate.py` (P1.5, бочка), а не CLI. Профиль
`static-candidate` фиксирует готовые файлы и импортирует их в UE по контракту 04 §1.

Профиль сборки (`schema` как у skeletal-candidate, `kind: "static-candidate"`), пример:
[decor-barrel-static-um-fbx-v1.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/build-profiles/decor-barrel-static-um-fbx-v1.json).

- `candidate`: каталог кандидата, FBX, BC/N/ORM, `candidate-report.json` (схема
  `unmatched.tripo-pipeline.static-prop-candidate/1`) и `fbx-readback.json` (`check_static_prop_fbx.py`);
- `ue`: имена ассетов, `collision: "none"`, `two_sided: false`, нейтральный `team_color`, текстуры
  (BC — sRGB, `TC_Default`; N — linear, `TC_Normalmap`, `flip_green: false`, DirectX; ORM — linear, `TC_Masks`),
  `shared_master` (`/Game/S05/M_DioramaMaster` и имена текстурных параметров);
- `axes.protrusion_axis_ue` — ось выступа (у бочки пробка), по габаритам видна только ось, знак — по кадру.

Стадия **adopt** ничего не копирует. Она пересчитывает SHA-256 файлов кандидата и сверяет их с отчётом кандидата.
Проверяет, что все проверки отчёта прошли, что исходник кандидата равен зарегистрированной первичной роли и что
настройки экспорта равны пресету UM_FBX_v1. По read-back сверяет треугольники, одну сетку без арматуры, замкнутость и
число слотов. Пишет `reports/adopt-report.json` с ожиданиями для UE: треугольники, размеры, предсказанные границы
UE как (x, −y, z) от read-back, размер текстур.

Стадия **ue-import** этого профиля:

- заново хеширует файлы из adopt-отчёта и отказывает, если они изменились;
- импортирует три PNG и выставляет sRGB, сжатие и flip green;
- материал: если `shared_master` существует и у него есть все текстурные параметры, MI создаётся от него. Иначе
  создаётся свой `M_<...>_Candidate` (BC × TeamColor, нормаль, ORM: R→AO, G→Roughness, B→Metallic, TwoSided=false),
  а отклонение пишется в `deviations` отчёта. На 2026-09-28 `M_DioramaMaster` существует, но в нём только
  векторные и скалярные параметры, текстурных нет (измерено), поэтому бочка идёт по второй ветке. С 0.6.0 профиль
  `decor-barrel-static-um-fbx-v1-um-master.json` (`/2`) называет общим мастером `/Game/UM/Materials/M_UM_Figure`
  (текстурные параметры есть) — бочка идёт по первой ветке: MI от мастера, `TeamColor` белый (декор не командный);
- импортирует меш с `import_materials=false`, `import_textures=false`, снимает коллизию (`remove_collisions`) и
  назначает MI на единственный слот;
- проверяет: папка пуста перед импортом, ассеты ровно по плану, нет `Name_1`, классы, свойства текстур,
  граф и односторонность материала, родитель и TeamColor MI, слот, треугольники LOD0, размеры ±1 %, pivot в центре
  основания, границы по UM_FBX_v1 (±0,05 uu), ось выступа, нет простой коллизии, всё сохранено;
  (0.6.0, `ue-static-candidate/2`) `nanite_disabled`, `normal_import_method_read_back` (метод нормалей `AssetImportData`
  меша записывается и проверяется: у MCP static import — `FBXNIM_ImportNormals` из настроек проекта), при общем мастере
  — `shared_master_parameters_current` (все параметры спецификации `um-masters.json` у мастера).

Повторный `ue-import` пропускается, если в папке ровно свои ассеты. `--force` удаляет свои ассеты и импортирует
заново, `Name_1` не появляется. Проверено вживую на бочке:
[evidence/p1-ue-import-2026-09-28/](evidence/p1-ue-import-2026-09-28/README.md).

### Поведение UE 5.8 MCP (измерено в T2.1)

- `StaticMeshTools.import_file` (legacy `FbxFactory` + `FbxImportUI`, не Interchange: исходник плагина EditorToolset,
  `static_mesh.py`; до 0.6.0 здесь ошибочно стояло «Interchange») возвращает только меш. Материалы и текстуры, созданные импортёром рядом,
  в ответ не попадают. Поэтому проверка passthrough `folder_contains_only_this_import` теперь требует пустую
  папку перед импортом и допускает рядом только побочные продукты импорта (Material, MaterialInstanceConstant,
  Texture2D). Первая живая попытка passthrough на бочке упала именно здесь; отчёт сохранён.
- Статический импорт через MCP создаёт 1 выпуклый элемент коллизии (`BodySetup.AggGeom.convexElems`).
- В MCP нет инструмента консоли и полноценного Python: sandbox `ProgrammaticToolset` разрешает только
  json/math/re/… Для FBX-анимаций, консольных переменных и замеров AnimSequence используется `py "<файл>"` в поле
  Cmd редактора, через `review/ue_live.py` (SlateInspector → Type).

## Схема каталогов

```
tools/tripo-pipeline/
  tripo_pipeline.py            CLI (этот документ)
  blender/import_source.py     стадия import (Blender; режимы process/live)
  blender/export_fbx.py        стадия export (Blender; режимы process/live)
  blender/build_candidate.py   стадия build профиля skeletal-candidate (Blender; process/live): грузит библиотеку
  blender/candidate_build/     алгоритм build по профилю (flow whole-figure / seated-parts; anatomy и profile_schema без bpy)
  candidate/atlas.py           стадия atlas профиля skeletal-candidate (Python + Pillow/numpy; exclude_parts,
                               normal_renormalise, team_color.mask, ao_bake → ORM.R)
  blender/bake_ao.py           подшаг atlas.ao_bake: Cycles AO по частям (всегда headless)
  um_masters.py                мастер-материалы M_UM_* (build/verify через MCP; спецификация art/um-materials/)
  review/                      редакторные кадры Blender/UE и список UE-папки (не стадии)
  check_inputs.py              T2: автопроверки ImageGen-входов (отдельный инструмент)
  validate_registry.py         T1: проверка реестра ассетов (отдельный инструмент)
  review/                      capture_blender_review.py, capture_ue_review.py, capture_ue_axes.py,
                               ue_listing.py, ue_already_exists_probe.py (редакторные кадры и evidence, не стадии),
                               compare_candidate_runs.py (сверка двух прогонов: FBX/атлас по байтам, числа build-отчётов)
  tests/                       python -m unittest (фейки Blender/MCP + интеграция с настоящим Blender)

art/pipeline-candidates/
  .gitignore                   work/, .staging/, run.lock, *.tmp-*
  <ASSET-ID>/source-specs/     описания уже оплаченных Tripo-задач (вход register-source)
  <ASSET-ID>/build-profiles/   профили сборки skeletal-candidate и static-candidate
  <ASSET-ID>/<run-id>/         один изолированный прогон кандидата:
    manifest.json              состояние прогона (схема ниже)
    journal.jsonl              журнал событий (append-only)
    reports/                   preflight.json, import-report.json, verify-report.json,
                               export-report.json | atlas-report.json + build-report.json,
                               ue-import-report.json, ue-mcp-calls.json
    export/*.fbx               детерминированные FBX по UM_FBX_v1 (байт в байт при тех же входах)
    textures/*.png             атлас BC/N/N_OpenGL/ORM [+ TeamMask] (skeletal-candidate)
    logs/<stage>.log           лог последнего выполнения стадии (<stage>.failed.log при ошибке;
                               в git не идёт — корневое правило *.log)
    work/*.blend               рабочие сцены import/build (не детерминированы; в git не идут —
                               art/pipeline-candidates/.gitignore)
    generation-requests/       dry-run пакеты prepare-generation
    .staging/, run.lock        только во время выполнения (после сбоя остаются до resume)

docs/art-pipeline/
  PIPELINE.md                  этот документ
  medusa-local-pass-report.md/.json      отчёт T4 и исправления осей
  evidence/t3-idempotency-2026-09-28/   доказательства прогона T3 на Medusa (см. ниже)
  evidence/t4-medusa-local-pass-2026-09-28/  T4 (исторический прогон, лицо +Y; кадры в JPEG, см. «Формат кадров»)
  evidence/t4-um-fbx-v1-2026-09-28/     исправление: UM_FBX_v1, лицо +X, стенограмма «already exists»
  evidence/t33-cli-build-2026-09-28/    T3.3: сверка CLI-пересборки Medusa и трёх героев с прежними кандидатами
```

Оригиналы Tripo лежат вне run-каталога (для Medusa: `blender/ASSET-MEDUSA-001/tripo-source/`).
`register-source` отказывает, если файл-оригинал находится внутри run-каталога.

## Source spec (вход `register-source`)

Схема `unmatched.tripo-pipeline.source-spec/1`. Пример — две оплаченные задачи Medusa:
`art/pipeline-candidates/ASSET-MEDUSA-001/source-specs/tripo-d562f057.json` и `tripo-b6253e58.json`.

| Поле | Смысл |
|---|---|
| `source_id`, `asset_id` | идентификатор источника в прогоне и ID ассета из реестра |
| `service` | `tripo-studio` или `tripo-api` — учитываются раздельно |
| `task_id`, `parent_task_id`, `task_url`, `date` | задача Tripo; клон/сегментация ссылаются на родителя |
| `model_version` | подпись модели в UI; backend-версия, если известна (для Studio не проверена) |
| `generation` | `mode`: `multi-view` (одна модель по ≥2 видам одного объекта), `single-image`, `text`; `batch` запрещён — это несколько независимых задач, каждая регистрируется отдельно; `views` с путями и SHA-256 входных изображений |
| `operations[]` | операции (generate, retopology, segment…) с `credits.unit` = `studio-credits` для Studio и `api-credits` для API; USD не смешивается с кредитами; `observed_debit`, `quoted`, баланс до/после |
| `files[]` | роль, путь, `expected_sha256`/`expected_bytes` из evidence, `produced_by`, `origin` |
| `expectations` | ожидаемые числа по GLB из evidence (меши, треугольники, материалы, изображения, скины) |
| `evidence[]` | файлы evidence; их SHA-256 записывается при регистрации |

Повторная регистрация того же spec с теми же хешами — no-op; другой контент под тем же `source_id` —
отказ (код 3). Несовпадение хеша файла с evidence — отказ.

## Run manifest

Схема `unmatched.tripo-pipeline.run/1` (`manifest.json`):

- `tool` — версия инструмента, создавшего прогон; каждая выполненная стадия пишет свои
  `tool_version` и `backend`;
- `claims` — всегда `art_accepted: false`, `game_ready: false`, `budgets_declared: false`;
- `network` — `tripo_calls: 0`, `paid_tasks_created: 0`;
- `config` — основной источник/роль, базовое имя экспорта, допуск потери треугольников (0,1 %),
  опционально `ue` (папка, имя ассета, импорт материалов, допуск размеров 1 %; для `skeletal-candidate` —
  фактические `import_materials=false`, `import_textures=false` и пояснение `import_note`);
- `sources` — зарегистрированные источники: spec целиком, хеши файлов, структура GLB,
  `historical_credits_observed` (исторический расход, не расход этого прогона);
- `stages.<name>` — `status` (`pending`/`running`/`completed`/`failed`/`interrupted`), `attempts`,
  `fingerprint` (SHA-256 входов стадии: версия логики, скрипт Blender, версия Blender, бэкенд, хеши
  входных файлов), `outputs` (путь → SHA-256, байты), `summary`, `interruptions`; для `ue-import`
  ещё `ue_owned_assets` — ассеты, созданные этим прогоном в редакторе;
- `exports[]` — индекс экспортов по хешу: те же байты второй раз не добавляются, заменённый файл
  помечается `superseded_by`;
- `generation_requests[]` — dry-run пакеты.

## Идемпотентность и возобновление

- Стадия пропускается (`skipped`), если она `completed`, её отпечаток не изменился и все её выходы
  на месте с теми же хешами. `preflight` выполняется всегда, но при тех же результатах ничего не
  переписывает (`revalidated`).
- Выходы стадии пишутся в `.staging/<stage>/` и переносятся на место только после успеха;
  файл с теми же байтами не переписывается (`unchanged` в журнале, mtime не меняется).
- Перед работой стадия помечается `running`. Если процесс убит, в manifest остаётся `running`, а
  `run`/отдельные стадии отказывают с кодом 5 и требуют `resume`. `resume` помечает стадию
  `interrupted`, чистит `.staging/`, снимает устаревшую блокировку (PID мёртв) и идёт по стадиям:
  готовые пропускаются, прерванная и следующие выполняются.
- `run.lock` с живым PID блокирует второй процесс (код 4).
- Для `ue-import` дубли в редакторе исключаются так:
  - папка должна быть внутри `/Game/PipelineCandidates/`;
  - если в ней есть ассеты, которые прогон не создавал, стадия отказывает (код 3) и ничего не удаляет;
  - свои прежние ассеты удаляются перед импортом. Живой UE 5.8 MCP `import_file` на занятое имя отказывает
    («already exists», стенограмма выше). Другой способ импорта UE может вместо отказа создать `Name_1` (на этом проекте не измерялось). Удаление перед импортом закрывает оба случая;
  - список созданных ассетов пишется в manifest сразу после импорта, до проверок, поэтому прерванный импорт убирается
    следующей попыткой;
  - пропуск завершённой UE-стадии дополнительно требует, чтобы редактор всё ещё содержал ровно эти ассеты
    (`exists` + `find_assets`).

Коды выхода: 0 — успех, 1 — проверка/стадия не прошла, 2 — неверный вызов или неподходящий бэкенд,
3 — конфликт (другой контент, чужие ассеты, дубль генерации), 4 — прогон заблокирован живым
процессом, 5 — нужен `resume`, 75 — диагностическое прерывание `--interrupt-at`.

## Бэкенды: headless и mcp

`--backend headless` (по умолчанию): каждая Blender-стадия — отдельный процесс
`blender -b --factory-startup --python-exit-code 1 --python <script> -- <params.json>`
(режим изоляции `process`: сцена сбрасывается в пустую). UE-стадия с этим бэкендом отказывает (код 2).

`--backend mcp`: работа в уже запущенных оркестратором приложениях, через внешние CLI-клиенты
(сам `tripo_pipeline.py` сетевого кода не содержит):

- Blender — `C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py exec <wrapper.py>` (аддон
  blender-mcp, сокет 127.0.0.1:9876, `execute_code`). В `.staging/<stage>/<stage>.mcp.py` пишется
  скрипт стадии без изменений с двумя строками-заголовками (`TRIPO_PIPELINE_PARAMS`,
  `TRIPO_PIPELINE_ISOLATION = "live"`). Режим `live`: файл пользователя не сбрасывается, не
  открывается и не сохраняется; GLB импортируется во временную сцену `tripo_pipeline_import`,
  сцена пишется в `work/*.blend` через `bpy.data.libraries.write`, export подгружает её копию
  (`libraries.load`), экспортирует и делает round-trip во временной сцене
  `tripo_pipeline_roundtrip`; все созданные этой стадией датаблоки (включая Library) удаляются,
  патчи FBX-экспортёра откатываются, сцена окна временно переключается и восстанавливается
  (на время `execute_code` интерфейс не перерисовывается). Если такая временная сцена уже
  существует (остаток сбоя), стадия отказывает и ничего не трогает.
- Если имена объектов/мешей/материалов/изображений совпали с данными живой сессии, Blender добавит
  суффикс `.001`. Отчёт import записывает канонические имена (как в headless) и список
  `live_name_collisions`; в FBX остаются суффиксные имена, поэтому байты FBX тогда отличаются от
  headless и экспорт станет новой записью индекса (дубля не будет, но и совпадения тоже).
- UE — `C:/Users/ren/.claude/mcp-servers/clients/unreal_mcp.py call <toolset> <tool> <json>`
  (плагин ModelContextProtocol, 127.0.0.1:8123/mcp). Используются
  `editor_toolset.toolsets.asset.AssetTools` (`find_assets`, `exists`, `delete`, `get_asset_class`,
  `save_assets`), `...static_mesh.StaticMeshTools` (`import_file`, `get_triangle_count`,
  `get_vertex_count`, `get_bounds`, `get_material_slots`) и `...skeletal_mesh.SkeletalMeshTools`
  (`import_file`, `get_bone_names`, `get_socket_names`, `get_bounds`, `get_material_slots`,
  `get_vertex_count`). Формат имени инструмента (короткое или полное) определяется по первому
  успешному вызову и пишется в отчёт.
  - Проверено на живом редакторе игрового проекта: профиль `skeletal-candidate` импортирован в T4
    (`/Game/PipelineCandidates/Medusa/T4LocalPass`) и при исправлении (`.../T4UmFbxV1`). Сработали короткие имена
    инструментов, ответы пришли в `structuredContent`.
  - Ветка passthrough на живом UE проверена в этапе 3, T2.1: бочка, run
    `art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel/ue-passthrough` (экспорт UM_FBX_v1, размеры по
    осям UE X, Y, Z совпали с export-отчётом, `--force` без `Name_1`), см.
    [evidence/p1-ue-import-2026-09-28/](evidence/p1-ue-import-2026-09-28/README.md). До этого её проверки основывались
    на фейке и на карте осей ART-001.

Пути клиентов переопределяются `--blender-mcp-client`, `--unreal-mcp-client` или (для тестов)
переменными `TRIPO_PIPELINE_BLENDER_MCP_CMD` / `TRIPO_PIPELINE_UNREAL_MCP_CMD` (JSON-список команды).
Бэкенд входит в отпечаток Blender-стадий: смена бэкенда переисполняет стадии, но FBX с теми же
байтами остаётся одной записью.

## Контракты стадий

| Стадия | Проверяет | Результат |
|---|---|---|
| preflight | Python ≥ 3.10; бэкенд; Blender отвечает и сообщает версию; клиенты MCP (для `mcp`); git-checkout; скрипты стадий; источники зарегистрированы, файлы на месте и не изменились с регистрации; оригиналы вне run-каталога; нет сетевых импортов; при настроенной UE-стадии — папка внутри `/Game/PipelineCandidates/` | `reports/preflight.json` |
| import | хеш основного GLB до и после; импорт в изолированную сцену; меши, треугольники, UV-слои, слоты материалов, изображения (цветовое пространство, упаковка), границы в метрах, открытые/неманифолдные рёбра после диагностической сварки 1e-7 | `work/*.blend`, `reports/import-report.json` |
| verify | совпадение с evidence (число мешей, треугольники, материалы, изображения, скины); потеря треугольников Blender-импортом ≤ 0,1 % по каждому мешу; UV0 на каждом меше; арматуры как ожидалось; невырожденные границы | `reports/verify-report.json` (`status: measured`) |
| export | пресет UM_FBX_v1: поворот +90° по Z, данные ×100 (метры → сантиметры), `FBX_SCALE_UNITS`, −Y вперёд, Z вверх, Triangulate, `UnitScaleFactor` = 1.0 (UE импортирует в масштабе 1.0); текстуры встраиваются (записанное отклонение от пресета); зафиксированы время и UUID FBX → детерминированные байты; round-trip: размеры в кадре экспорта = авторские, повёрнутые пресетом; после обратного поворота — те же меши и треугольники, UV, нет арматуры, коэффициент размеров 1.0; `expected_ue_dimensions_uu_at_import_scale_1` — по осям UE X, Y, Z | `export/*.fbx`, `reports/export-report.json` |
| ue-import (только mcp) | папка кандидата; нет чужих ассетов; нет `Name_N`-дублей; папка содержит ровно этот импорт; класс ассета; число слотов = число материалов после round-trip; размеры = ожидаемые ±1 % по каждой оси UE X, Y, Z; треугольники LOD0 = round-trip ±0,1 % (static); кости и сокеты записываются (skeletal); сохранение. На живом UE для passthrough проверено в этапе 3, T2.1 (бочка). | `reports/ue-import-report.json` (`status: technically_imported`), `reports/ue-mcp-calls.json` |

Таблица выше описывает профиль passthrough. В нём не проверяются нормали и winding, BC/Normal/ORM и TeamColor,
pivot и root, кости и сокеты — всё это проверяет профиль skeletal-candidate (раздел выше).

Ни один профиль не проверяет силуэт в игровой камере, свет и деформацию в анимации — это задачи арт-трека.
Собственной ретопологии пайплайн не делает: он переиспользует ретопологию Tripo. Проход `export` — технический passthrough геометрии Tripo, а не
игровой ассет: FBX-экспортёр Blender переносит только текстуры, подключённые к поддерживаемым
входам Principled (на Medusa: 45 изображений до экспорта → 15 после round-trip, измерено).

## Команды

Из корня репозитория (`C:/Users/ren/WebstormProjects/unmached/unmached`):

```bash
T="python tools/tripo-pipeline/tripo_pipeline.py"
R=art/pipeline-candidates/ASSET-MEDUSA-001/<run-id>

# 1. новый прогон кандидата
$T init --run-dir $R --asset-id ASSET-MEDUSA-001 \
    --primary-source tripo-b6253e58 --primary-role segmented-retopo-glb

# 2. регистрация уже оплаченных задач Tripo (без сети; повтор = no-op)
$T register-source --run-dir $R --spec art/pipeline-candidates/ASSET-MEDUSA-001/source-specs/tripo-d562f057.json
$T register-source --run-dir $R --spec art/pipeline-candidates/ASSET-MEDUSA-001/source-specs/tripo-b6253e58.json

# 3. стадии (по одной или все)
$T preflight --run-dir $R
$T import    --run-dir $R
$T verify    --run-dir $R
$T export    --run-dir $R
$T run       --run-dir $R            # preflight -> import -> verify -> export [-> ue-import]

# 4. живые приложения (только когда задача это явно разрешает; Blender/UE уже запущены)
$T --backend mcp run --run-dir $R
$T --backend mcp ue-import --run-dir $R --ue-folder /Game/PipelineCandidates/Medusa/<run_id>

# 5. сбой / продолжение
$T resume  --run-dir $R
$T status  --run-dir $R
$T snapshot --run-dir $R --out <файл вне run-каталога>   # хеши всех файлов прогона

# 6. пакет входов для будущей генерации (ничего не отправляет)
$T prepare-generation --run-dir $R --dry-run --service tripo-studio --mode multi-view \
    --model-label "<подпись модели>" --view front=<png> --view left=<png> --view back=<png>
#    те же хеши входов + mode + service уже сгенерированы → отказ (код 3) при любой подписи модели;
#    осознанный повтор: добавить --allow-duplicate --duplicate-reason "<почему>" (причина пишется в пакет и журнал)

# 7. игровой кандидат (профиль skeletal-candidate, T4); в Git Bash — export MSYS_NO_PATHCONV=1
$T init --run-dir $R --asset-id ASSET-MEDUSA-001 --primary-source tripo-b6253e58 \
    --primary-role segmented-retopo-glb --profile skeletal-candidate \
    --build-profile art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-segmented-skeletal-um-fbx-v1.json
$T --backend mcp run --run-dir $R        # preflight -> import -> verify -> atlas -> build
$T --backend mcp ue-import --run-dir $R --ue-folder /Game/PipelineCandidates/Medusa/<Run>
$T --backend mcp ue-import --run-dir $R --force   # повторный импорт: те же ассеты, без дублей
python tools/tripo-pipeline/review/capture_blender_review.py --run-dir $R --out <каталог>   # редакторные кадры

# 7a. (0.6.0) мастера до ue-import по маршруту um-master
python tools/tripo-pipeline/um_masters.py --backend mcp build --report docs/art-pipeline/evidence/<задача>/um-masters-report.json

# 8. герой (flow seated-parts, 0.5.0): профиль *-cli.json; второй source-spec — high-poly/доп. задачи Tripo
H=art/pipeline-candidates/ASSET-HARPY-001; RH=$H/<run-id>
$T init --run-dir $RH --asset-id ASSET-HARPY-001 --primary-source tripo-d500fc84 \
    --primary-role segmented-retopo-glb --profile skeletal-candidate \
    --build-profile $H/build-profiles/harpy-segmented-skeletal-um-fbx-v1-cli.json
$T register-source --run-dir $RH --spec $H/source-specs/tripo-c756522c.json
$T register-source --run-dir $RH --spec $H/source-specs/tripo-d500fc84.json
$T run --run-dir $RH                     # preflight -> import -> verify -> atlas -> build (build: completed)
python tools/tripo-pipeline/review/compare_candidate_runs.py --pair $RH $H/20260928-blender-um-fbx-v1   # сверка
python tools/tripo-pipeline/review/capture_ue_review.py --run-dir $R --out <каталог>   # схема камер T4 (лицо +Y)
(cd tools/tripo-pipeline/review && python capture_ue_axes.py --run-dir ../../../$R --out <каталог>)   # ось лица: пиксели + кадры
```

`--force` у стадии переисполняет её, но выходы с теми же байтами не переписываются и не
добавляются в индекс экспортов. `--interrupt-at <stage>` — диагностика: процесс завершается с
кодом 75 после работы стадии, до фиксации результата (как при сбое).

Добавление нового ассета — пошагово в [ADDING-AN-ASSET.md](ADDING-AN-ASSET.md) (профили static / skeletal / оружие,
правила остановки, ловушки, сухой повтор T3.1). Кратко: описать уже полученный результат Tripo в
`art/pipeline-candidates/<ASSET-ID>/source-specs/<source_id>.json` (хеши из evidence), создать
новый `<run-id>`, выполнить шаги 1–3. Для игрового кандидата — ещё профиль сборки в
`art/pipeline-candidates/<ASSET-ID>/build-profiles/`. В нём нужны части, кости и веса, ожидаемые вывернутые части
(сначала прогнать build: стадия перечислит найденные части и откажет, пока профиль с ними не совпадёт), сокеты и
имена в UE. После этого — шаг 7. Повторять генерацию не нужно и нельзя без отдельного решения:

- `prepare-generation` отказывает (код 3), если хеши тех же входов, режим и сервис уже зарегистрированы.
- Подпись модели при этом не сравнивается: это свободный текст UI («H3.1» и «H3.1 - Макс.кач. …» — одна модель).
- Обход — только `--allow-duplicate --duplicate-reason "..."`.

## Тесты

```bash
python -m unittest discover -s tools/tripo-pipeline/tests -v
```

Тестов пайплайна 100 (2026-09-29, версия 0.5.0 / `ue-candidate/6`; 67 до T3.3, 21 от T3.3, 2 от T3.1 в
`test_seated_candidate.py`: сокет на кости с точкой, подставка vertex-mask без вершинных цветов, и 10 от исправлений
ревью T3.1 в `test_control_scene.py`: декор на поверхности, проверка посадки, счёт просветов подставки). В том же
каталоге лежат ещё 27 тестов T1/T2 (`test_check_inputs.py`, `test_validate_registry.py`); за них отвечают их
владельцы. С Blender все 127 проходят без пропусков (≈5 мин).

0.6.0 (W4-B) добавил `test_um_master.py` (25 тестов, из них 6 — исправление ревью): правило цвета (`hex_to_linear` = таблица `sRGBToLinearTable`
движка, hex/255 — не правило, С-11 почти изолюминантны, предложение — нет); графы мастеров (раскладка CPD меморандума,
0 нейтрален, нет WPO/Masked/Opacity, Figure = граф кандидатов при нейтральных ручках, у каждого узла своя позиция,
модель особенности чтения связей); build/verify мастера на фейковом редакторе (создан → `skipped` → изменённая
спецификация без `--force` — отказ 3, с `--force` — перестройка на месте, MI не теряет родителя; удалённая связь
валит `links_match_plan`); маршрут `um-master` (AO-гейт и маска `hsv-band-cells` на настоящей стадии atlas,
константный AO валит atlas, MI и их родители/текстуры/`TeamColor`, контракт импорта, неверный метод нормалей валит
стадию, отсутствующий мастер останавливает до MI, потерянная консольная команда печатается снова); профили `/3`
добавляют к `/2` только ключи atlas/TeamMask/UE; статика на `M_UM_Figure`; исправление ревью: запекание получает
пограничное исправление ориентации Harpy (эталон, сварка, посадка — те же числа, что у build), вне flow seated-parts
оно запрещено, у героев без смешанной намотки параметры прежние, код запекания — модули `candidate_build` (и они в
отпечатке atlas), зарегистрированный эталонный GLB доходит до запекания, ячейка с гранями «внутрь» валит гейт
`ao_bake_parts_face_outward`. В `test_control_scene.py` — разделение «фигура / подставка» `team_contrast.py`, шум
повторов и пересчёт из закоммиченных входов (числа те же). Фейки: `fake_unreal_mcp.py` записывает графы материалов,
связи, параметры, MI, опции FBX-импорта editor-Python и лаунчер; `fake_blender.py` — двойник `bake_ao.py` (ориентация
после переворотов, `FAKE_AO_INWARD`). Весь каталог — 174 теста, зелёные (≈11 мин, с Blender); из них 21 — чужие
`test_rig_rules.py` (W4-D), на долю W4-B без них — 153.

- `test_pipeline.py` — регистрация (no-op, конфликт, хеши evidence, Studio/API-кредиты, batch,
  multi-view, оригиналы вне run-каталога), идемпотентность (второй прогон не меняет ни одного файла,
  `--force` без дубля экспорта, потерянный work-файл), прерывание и `resume` (`--interrupt-at` на
  verify и export, убитый процесс, живая блокировка, упавшая стадия), dry-run генерации:
  - отказ при тех же входах, режиме и сервисе при любой подписи модели;
  - разные входы, сервис или режим — не дубль;
  - `--allow-duplicate` только с `--duplicate-reason`, причина пишется в пакет.

  Blender заменён `tests/fake_blender.py`; во временный репозиторий кладётся копия настоящего UM_FBX_v1;
- `test_mcp_backend.py` — бэкенд `mcp` на фейковых клиентах с тем же JSON-контрактом
  (`fake_blender.py --mcp`; `fake_unreal_mcp.py`, который, как живой UE 5.8 MCP, отказывает «already exists» при
  занятом имени, а с `FAKE_UE_ON_EXISTING=number` моделирует импорт с `Name_1`):
  живые Blender-стадии, смена бэкенда без дубля FBX, недоступный Blender, ошибка стадии и resume;
  UE — отказ headless, запрет папок вне `/Game/PipelineCandidates/`, двойной импорт без дублей,
  `--force`, чужие ассеты, прерывание и resume, удалённый в редакторе ассет, провал контракта и
  чистый повтор, полные имена инструментов, смена цели;
- `test_candidate.py` — профиль skeletal-candidate:
  - настоящая стадия atlas на синтетическом GLB с текстурами, фейковый build;
  - повторный прогон без изменений, отказ стадии чужого профиля, правка профиля без дубля FBX;
  - сбой проверки build и повтор;
  - UE-кандидат: 9 ассетов, лицо +X по UM_FBX_v1, фактические флаги импорта в `config.ue`, пропуск по проверке
    редактора, `--force` без дублей и без двойных сокетов;
  - эталон с фронтом +Y переводится картой границ во фронт кандидата +X;
  - профиль без `fbx_preset` отказывает на preflight; правка пресета пересобирает build;
  - отказ UE при импорте на занятое имя, чужой ассет, провал контракта и чистый повтор;
- `test_static_candidate.py` — профиль static-candidate (этап 3, T2.1): adopt, ue-import с 6 ассетами и снятой
  коллизией, пропуск повтора, `--force` без `Name_1`, ветка общего мастера с текстурными параметрами и без них
  (отклонение), отказ adopt при расхождении байт с отчётом кандидата, отказ ue-import после правки кандидата,
  провал контракта треугольников, чужой ассет в папке, `--build-profile` только для профилей, которые его читают;
- `test_candidate_integration.py` — настоящий Blender headless на исходнике Medusa во временном run-каталоге:
  - все контракты build проходят, второй прогон ничего не меняет;
  - экспорт по UM_FBX_v1: лицо +X в кадре экспорта, Triangulate без изменения геометрии, угловые нормали и кости
    совпадают с v2 после обратного поворота;
  - FBX байт в байт равны прогону `20260928-t4-um-fbx-v1`, который лежит в run-каталоге (untracked до интеграции);
  - стадия build в режиме live (как `execute_code`) оставляет сессию нетронутой и даёт те же байты;
  - герои (0.5.0): King Arthur, Merlin и Harpy собираются CLI целиком во временные run-каталоги — build `completed`,
    FBX и атлас байт в байт равны `20260928-blender-um-fbx-v1`, второй прогон ничего не меняет, ue-import (фейковый UE
    на настоящем build-отчёте) принимает прогон; Merlin ещё и в режиме live (сессия нетронута, те же байты);
- `test_seated_candidate.py` — сборка по профилю (0.5.0), фейковые Blender/UE, настоящая стадия atlas:
  - схема профиля: четыре профиля репозитория валидны, `/1` героев с `builder` отказывают, правила seated-профиля;
  - анатомия: голова, ступни (плащ через обе стороны не считается), рука с оружием, шея; профиль важнее, расхождения
    перечисляются;
  - Harpy-подобный профиль: `exclude_parts`, перенормировка нормалей, TeamMask, подставка `vertex-mask` (с T3.1 —
    импорт с вершинными цветами через консоль редактора; без цветов стадия падает), сокет по прогнозу build,
    сокет на кости с точкой (`foot.R` → `foot_R`), высота по профилю в ue-import; оружие выше фигуры не валит проверку высоты;
  - неверный профиль останавливается на preflight до Blender; источник `per_face_reference` проверяется и передаётся в build;
- `test_blender_integration.py` — настоящий Blender 5.2 headless:
  - двойной прогон без изменений файлов;
  - passthrough по UM_FBX_v1 на GLB с неквадратным основанием: размеры X/Y в FBX переставлены, после обратного поворота равны авторским;
  режим `live` в сессии с пользовательскими данными ровно так, как его выполняет `execute_code`
  (`tests/blender_live_harness.py`): сессия не изменилась (все коллекции `bpy.data`, активная сцена,
  патчи FBX), FBX байт в байт равен headless; при совпадении имён — канонические имена в отчёте и
  список коллизий. Пропускается, если Blender не установлен.
- `test_control_scene.py` — контрольная сцена P1.7 без редактора (исправления ревью T3.1): декор задаётся без z и с
  `place_on_surface`, фигуры на клетках z 0; проверка посадки декора (бочка на z 0 в борту 5 uu — провал, на верхе
  борта — годно, неровная опора — провал); счёт просветов подставки по кадрам без доски (дыры, закрытые фигурой, и
  чёрные пиксели фигуры вне дыр не считаются).

## Проверка на Medusa (T3, 2026-09-28, headless)

Run-каталог: `art/pipeline-candidates/ASSET-MEDUSA-001/20260928-t3-scaffold/`
(начат прерванным прогоном версии 0.1.0 и продолжен версией 0.2.0, не создан заново).
Доказательства: `docs/art-pipeline/evidence/t3-idempotency-2026-09-28/`
(`commands.txt`, `snapshot-0…4-*.json`, `tripo-source-before/after.json`, `summary.json`).

Измерено:

- зарегистрированы `tripo-d562f057` (H3.1 multi-view front/left/back, 55 + 40 Studio-кредитов,
  исторически) и `tripo-b6253e58` (сегментация 0 + segmented-retopo 40 Studio-кредитов,
  исторически); 4 GLB совпали с SHA-256 и размерами из evidence, 3 текстуры исходника
  (`source_basecolor/normal/rm`) захешированы при регистрации — в evidence их хешей нет
  (`hash_check: measured_at_registration_no_evidence_hash`);
- основной вход `medusa-segmented-retopo.glb`: 15 мешей, 21 177 треугольников по GLB, 21 176 после
  Blender-импорта (−1 в `tripo_part_3`, в допуске), 15 материалов, 45 изображений, UV0 на всех
  мешах; размеры 0,560 × 0,486 × 0,980 м → ожидаемо 56,0 × 48,6 × 98,0 uu при импорте в UE
  в масштабе 1.0 (это исходный масштаб Tripo, не игровой; нормализация к 55 uu — задача кандидата T4);
- первый прогон 0.2.0 переисполнил import/export (изменились скрипты), `import-report.json`
  остался байт в байт прежним (verify пропущен), FBX изменился один раз (новый поток экспорта),
  прежняя запись индекса помечена `superseded_by`;
- второй прогон: ни один файл прогона не переписан (snapshot 1 = snapshot 2). Snapshot по построению не включает
  `journal.jsonl`: журнал дописывается при каждом запуске, это не перезапись;
- `run --force import --interrupt-at import` → код 75; `run` → отказ, код 5; `resume` → import и
  export переисполнены, FBX и все отчёты `unchanged`, в индексе экспортов по-прежнему одна текущая
  запись; следующий `run` — без изменений;
- `prepare-generation --dry-run` с теми же входами Medusa v5 и подписью H3.1 → отказ (код 3),
  дубль задачи d562f057;
- `ue-import` с бэкендом headless → отказ (код 2);
- 19 файлов `blender/ASSET-MEDUSA-001/tripo-source/` до и после: те же SHA-256, размеры и mtime;
- внешняя стоимость прогона: 0 (Tripo-вызовов 0, платных задач 0).

В T3 не проверялось: живые приложения в T3 не использовались по условию задачи. Позже в T4 (см.
[medusa-local-pass-report.md](medusa-local-pass-report.md)) проверено:

- бэкенд `mcp` на живых Blender (9876) и UnrealEditor (8123);
- реальный формат ответов `call_tool` на игровом проекте;
- фактические размеры, треугольники и слоты в UE — только для профиля `skeletal-candidate`.

Ветка passthrough в живой UE в T3 и T4 так и не импортировалась (впервые — в этапе 3, T2.1, на бочке).

**FBX этого прогона сделан до UM_FBX_v1** (инструмент 0.2.0: без поворота и Triangulate, лицо было бы +Y). Прогон
оставлен как есть, как доказательство идемпотентности. Следующий `run` инструментом 0.4.0 переэкспортирует его по
пресету: новая запись индекса, старая помечается `superseded_by`.

Проверка passthrough 0.4.0 на том же GLB Medusa (headless, временный run-каталог):
[passthrough-um-fbx-v1-check.json](evidence/t4-um-fbx-v1-2026-09-28/passthrough-um-fbx-v1-check.json):

- все проверки прошли;
- размеры в кадре экспорта 0,486 × 0,560 × 0,980 м (X и Y переставлены) → ожидаемо 48,6 × 56,0 × 98,0 uu в UE;
- 21 176 треугольников.
