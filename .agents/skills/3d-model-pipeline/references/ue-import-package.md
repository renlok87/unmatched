# Этап 6. Упаковка ассета под импорт в Unreal Engine

Вход этапа: готовые FBX (меш + подставка + клипы) и текстуры из этапов 2–5. Выход: ассеты в
`/Game/PipelineCandidates/<Key>/...`, прошедшие `ue-import-report.json` и автотесты, плюс evidence-папка.
Верифицированная пара версий: Blender 5.2.2 LTS → UE 5.8.2 (пресет `UM_FBX_v1`, ART-001 PASS,
`blender/_tools/presets/UM_FBX_v1.json:4`).

Главный источник правил — `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (§2 «Контракт», §4.6 «Импорт в UE»,
§4.7 «Подключение в игру»). Этот документ — рабочая выжимка этапа 6; при расхождении выигрывает хендбук.

## 1. Экспорт FBX из Blender

### 1.1 Пресет UM_FBX_v1 — единственный путь

Исполнитель не выставляет настройки FBX руками: пресет `blender/_tools/presets/UM_FBX_v1.json` применяет
`tools/tripo-pipeline/blender/candidate_build/core.py` (`transform_for_fbx`, `export_fbx`, `patch_fbx_units`).
Параметры экспорта ниже — пресет (файл) ПЛЮС код сборки; в колонке указан источник (в самом файле пресета
ключей `colors_type`, `use_custom_props`, `bake_anim`, `bake_anim_step`, `bake_anim_simplify_factor` НЕТ):

| Параметр | Значение | Зачем |
|---|---|---|
| Единицы авторинга | 1 unit = 1 м, Metric, Unit Scale 1.0 (пресет) | клетка доски = 1 м = 100 uu (HANDBOOK §2.1) |
| Экспорт единиц | данные ×100 + `apply_unit_scale=true`, `apply_scale_options="FBX_SCALE_UNITS"`, затем `UnitScaleFactor=1.0` в заголовке FBX (пресет) | UE получает сантиметровые числа без двойного масштабирования |
| Оси | `axis_forward="-Y"`, `axis_up="Z"`, `primary_bone_axis="Y"`, `secondary_bone_axis="X"` (пресет) | лицо в Blender −Y → в UE +X |
| Поворот сцены | +90° вокруг Z до экспорта; матрица снапнута к целым (пресет `export_space_rotation_z_degrees`) | не снапнутая (cos 90° = 6e-17) переворачивает нормали тонких треугольников (HANDBOOK §2.2) |
| Меш | `use_triangles=true`, `mesh_smooth_type="FACE"` (пресет); `colors_type="SRGB"`, `use_custom_props=false` — код сборки (`core.py:273-274`, константы `COLORS_TYPE`/`PATH_MODE`, core.py:37-39) | триангуляция на стороне Blender; тангенты пересчитает UE |
| Кости | `add_leaf_bones=false` (пресет) | иначе UE получит лишние leaf-кости |
| Анимация (клипы) | `bake_anim_use_all_bones=true`, `bake_anim_use_nla_strips=false`, `bake_anim_use_all_actions=false`, `bake_anim_force_startend_keying=true` (пресет); `bake_anim=true`, `bake_anim_step=1.0`, `bake_anim_simplify_factor=0.0` — код клипа (`clip_author.py:660,665`); у меша `bake_anim=false` — код (`core.py:273`) | запекание всех костей в ключи, кадр 0 = rest |
| Пути | `path_mode=STRIP`, `embed_textures=false` — код сборки (`core.py:37,274`; в пресете записан `AUTO`, сборка осознанно перекрывает — комментарий core.py:337-340) | текстуры идут в UE отдельно, не внутри FBX (записанное отклонение, не ошибка) |
| Детерминизм | время FBX = 2000-01-01, стабильные UUID (код `make_fbx_deterministic`) | повторный прогон = те же байты |

Существует альтернативная школьная практика «Unit Scale 0.01 в Blender (1 BU = 1 см)» — она в проекте не
применяется и не проверялась (не проверено). Whatever approach, Import Uniform Scale в UE всегда 1.0; ручной
Scale при импорте — дефект (HANDBOOK §2.1).

### 1.2 Раздельные экспорты: один FBX на назначение

По образцу репозитория (`blender/ASSET-MEDUSA-001/export/` и прогонов `art/pipeline-candidates/ASSET-MEDUSA-001/`):

| Файл | Содержимое | bake_anim | Примечание |
|---|---|---|---|
| `SK_<Hero>_H2LD.fbx` | скелетный меш + арматура (скин) | false | после look-dev (этап 4.5); суффикс `H<N>LD` = номер последнего high-poly поколения ассета: первое H2 (Arthur/Merlin/Medusa), у Harpy второе — `H3LD`; фиксируется в UE_NAMES заявки |
| `SM_<Hero>_H2LD_Base.fbx` | подставка, статичный FBX без скина | false | отдельный FBX, не скинится (HANDBOOK §2.6) |
| `AM_<Hero>_<Clip>.fbx` | один клип: арматура **+ узел меша** | true | 4 клипа: `Idle`, `LungeAttack`, `HitReact`, `DeathSettle` |

Критично: клип экспортируется ОБЯЗАТЕЛЬНО с узлом меша — без него legacy-импортёр UE не создаёт
AnimSequence (HANDBOOK §2.8, §2.3). При экспорте выделяется меш + арматура (Limit to Selected Objects);
`use_selection=true` ставит сборка.

Рядом с каждым FBX Blender пишет медиа-папку `<имя>.fbm/` — служебная, в git и в UE не идёт.

### 1.3 Один прогон = один run-каталог

- Blender-сборка: новый run-каталог `art/pipeline-candidates/<ASSET-ID>/<YYYYMMDD>-<suffix>/` с
  `export/ textures/ preview/ reports/` (в git) и `work/ logs/` (не в git). Закоммиченный каталог под другой
  конфиг не переиспользовать (HANDBOOK §4.1).
- Профили (`build-profiles/*.json`) — только новые файлы; править закоммиченный профиль запрещено.
- Всё headless: `blender -b --factory-startup --python-exit-code 1`. Успех стадии = код 0 + маркер в логе
  (`H2_BAKE_STAGE_OK <stage>`) + нет `Traceback`.
- Риг: контракт `UM_HUMANOID_17_v2` (`docs/art-pipeline/rig/rig-contract.json`), объект арматуры
  `SKEL_UM_Humanoid` у всех героев (UE делает из него кость 0, носитель root motion). Арматура с другим именем
  (`SKEL_Medusa` из старого локального билда `blender/ASSET-MEDUSA-001/build_tripo_medusa.py`) в v2 = FAIL.
- Сокеты в Blender НЕ делать — их создаёт UE-импорт (HANDBOOK §2.7).

## 2. Текстуры

### 2.1 Прямо про каналы: ORM, не RM

Стандарт проекта для героев — карта **ORM**: R = AO, G = Roughness, B = Metallic. Карта `RM` из glTF/Tripo —
промежуточная (roughness/metallic без AO); она перепаковывается в ORM с запечённым AO в канале R. Суффикс
`_RM` в именах текстур запрещён (HANDBOOK §2.3–2.4, строки 154 и 162). Если видите `T_*_RM.png` — это
промежуточный артефакт стадии «текстуры», в UE его не импортируют.

| Карта | Имя (герой H2LD) | Каналы | Цвет. пространство | Компрессия UE | Примечание |
|---|---|---|---|---|---|
| Base Color | `T_<Hero>_H2LD_2K_BC` | RGB | **sRGB** | `TC_Default` | glTF `baseColorFactor ≠ 1` умножается в линейном свете |
| Normal | `T_<Hero>_H2LD_2K_N` | tangent | linear | `TC_Normalmap`, `flip_green=false` | **DirectX** (G = 255 − G от OpenGL); `N_OpenGL` — служебная копия для Blender, в UE не идёт |
| ORM | `T_<Hero>_H2LD_2K_ORM` | R=AO, G=Roughness, B=Metallic | linear | `TC_Masks` | не RM; AO запечён в R |
| MatID | `T_<Hero>_H2LD_2K_MatID` | 1 канал | linear | `TC_Grayscale`, Nearest, NoMipmaps, NeverStream | значение = класс × 16 + 8; классы 1–15 из `material-library/README.md` |
| EdgeMask | `T_<Hero>_H2LD_2K_Edge` | 1 канал | linear | `TC_Grayscale` | |
| TeamAccent | `T_<Hero>_H2LD_TeamAccent_2K` | 1 канал, 8 бит | linear | `TC_Grayscale`, обычные мипы | покрытие 5–12 % площади (HANDBOOK §2.9) |
| LUT | `T_UM_MatLUT_<Hero>.dds` | 16×16 RGBA16F | — | `TC_HDR`, Nearest, без мипов | |

Фактические имена в UE НЕ строго едины по героям (проверено `ls Content/PipelineCandidates/{Medusa,KingArthur}/H2LD/Textures`):
Medusa — `T_Medusa_H2LD_{BC,N,ORM,MatID,Edge,TeamAccent}`; Arthur — то же, но карта кромки
`T_KingArthur_H2LD_EdgeMask` (не `…_Edge`), LUT — `T_UM_MatLUT_Arthur` (короткий ключ, не KingArthur).
Суффикс `_2K` в имени uasset опускается. Точные имена нового ассета фиксируются в UE_NAMES заявки
этапа 0 и проверяются `ls` фактической папки на этапе 6; шаблон выше — канон, отклонения допустимы
только как зафиксированные в заявке.

### 2.2 Размеры и power-of-two

- Герой: 4K master локально вне git + 2K runtime в git; 2K = точный 2×2 box-downsample (HANDBOOK §2.4).
- Пропс: 1K–2K (`texture_size` в params; фонарь 1024).
- Power-of-two: у проекта все runtime-карты 2048/4096 — квадратные Po2. Общее правило «Po2 нужен для texture
  streaming, верхний mip кратен 4» — из доков Epic (не проверено). sRGB включается только на BC; на данных
  (N, ORM, маски) — выключен (фиксирует HANDBOOK §2.4; то же правило в доках Epic — не проверено).

### 2.3 Материалы

- Фигура: **1 материал-слот** на меш (тело и оружие делят атлас); подставка: 1 слот; пропс: 1, максимум 2
  (второй — свечение `glow_slot`).
- Мастер-материалы: фигура `/Game/UM/Materials/v2/M_UM_Figure_v2` (актуальная ревизия v2.2 —
  `S08FighterActor.h:107` «(CPD_HitTint, M_UM_Figure_v2.2)», вошла с коммитом `07f606bd`), подставка `M_UM_BaseMarker`
  (`um_masters.py build`). Static switches `UseUV1Metres=true`, `UseTeamAccent=true`.
- MI создаётся в UE от мастеров (в FBX материалы не едут: `import_materials=false`): `MI_<Key>_<Stage>_P1/_P2`,
  `MI_<Key>_<Stage>_Base_P1/_Base_P2`, `+ _Neutral`, `_DebugClass`; роспуск `MI_<Hero>_<Stage>_<Team>_Dissolve`
  в `/Game/UM/Materials/v2/Dissolve/`. Факт по Medusa: `Materials/MI_Medusa_H2LD_{P1,P2,Neutral,DebugClass,…}`.
- UV: UV0 = атлас, UV1_m = UV в метрах с центрами островов в (0,0). У подставки в UE выключить
  Generate Lightmap UVs, иначе UV1 перезапишется (HANDBOOK §2.5).

## 3. Структура Content и нейминг

Только `/Game/PipelineCandidates/<Key>/...`; сырые run-каталоги с датами (`20260929-w4b-um-master` и т.п.) —
история кандидатов, не образец для новых ассетов. `<Key>` — PascalCase без пробелов: `KingArthur`, `Merlin`,
`Medusa`, `Harpy`. Проверено `ls unreal/Unmatched/Content/PipelineCandidates/Medusa`:

```
/Game/PipelineCandidates/<Key>/            # <Key> = Medusa | KingArthur | Merlin | Harpy
  Rig/    SK_<Key>_Skeleton.uasset         # канонический скелет героя (+ SK_<Key> — импортированный меш)
  H2LD/   Meshes/    SK_<Key>_H2LD.uasset  # фигура (Harpy: H3LD)
                     SM_<Key>_H2LD_Base.uasset  # подставка
          Materials/ MI_<Key>_H2LD_<Team>.uasset (+ _Base, _Neutral, _DebugClass)
          Textures/  T_<Key>_H2LD_{BC,N,ORM,MatID,Edge,TeamAccent}.uasset, T_UM_MatLUT_<Key>.uasset
                     # имя карты кромки варьирует: Medusa …_Edge, Arthur …_EdgeMask; LUT — по короткому
                     # ключу (T_UM_MatLUT_Arthur); точные имена — из UE_NAMES заявки этапа 0
  H2Anim/ AM_<Key>_{Idle,LungeAttack,HitReact,DeathSettle}.uasset   # на каноническом скелете
```

| Префикс | Что | Пример |
|---|---|---|
| `SK_` | скелетный меш / скелет (`SK_<Key>_Skeleton`) | `SK_Medusa_H2LD` |
| `SM_` | статик-меш (подставка, пропс) | `SM_Medusa_H2LD_Base`, `SM_Decor_Barrel` |
| `AM_` | AnimSequence (клип) | `AM_Medusa_LungeAttack` |
| `T_` | текстура, суффикс-слот карты | `T_Medusa_H2LD_ORM` |
| `M_` / `MI_` | мастер-материал / инстанс | `M_UM_Figure_v2`, `MI_Medusa_H2LD_P1` |

Запрещено: id из базы (cuid) в именах; суффикс `_RM`; кость с одиночным именем `weapon` (HANDBOOK §2.3).

## 4. Импорт в UE: порядок и параметры

Все UE-шаги — под блокировкой `C:/tmp/ue-editor.lock` (`tools/art/material_library/ue_lock.py`), по одному герою/клипу на блокировку
(HANDBOOK §4.6). Порядок:

```bash
# 1. Мастер-материалы (один раз на редактор, повтор ничего не меняет)
python tools/tripo-pipeline/um_masters.py --backend mcp build --report <evidence>/um-masters-report.json
# 2. Снимок до (записать открытый уровень, 0 dirty-пакетов)
python tools/tripo-pipeline/review/ue_content_snapshot.py <evidence>/snapshot-before.json \
    --extra-folder /Game/ArtTests --extra-folder /Game/S08
# 3. Канонический скелет героя
MSYS_NO_PATHCONV=1 python tools/tripo-pipeline/anim/h2anim_ue.py skeleton <spec>
#    → /Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton
# 4. Меш на скелет: CLI, профиль skeletal-adopt (в профиле ue.target_skeleton; образец medusa-h2ld-lookdev-ue-import.json)
$T init --run-dir $R --asset-id <ASSET-ID> --primary-source tripo-<task8>-h2 \
    --primary-role h2-parts-glb --profile skeletal-adopt --build-profile $P --run-id <run-id>
$T register-source --run-dir $R --spec <source-spec>
$T run --run-dir $R                       # preflight + adopt, без UE
$T --backend mcp ue-import --run-dir $R --ue-folder /Game/PipelineCandidates/<Key>/<Stage>
$T --backend mcp ue-import --run-dir $R   # повтор → skipped (идемпотентность)
# 5. Клипы
python tools/tripo-pipeline/anim/h2anim_ue.py import <spec>   # затем measure
```

Причина skeletal-adopt: скелет-ассет в UE привязан к папке импорта, CLI-переимпорт удаляет свой Skeleton;
опция `ue.target_skeleton` сажает новый меш на существующий канонический скелет
(`docs/game-design/decisions/2026-09-29-anim-v2-decisions.md`).

### 4.1 Параметры импорта (меш SK_)

| Параметр | Значение | Источник |
|---|---|---|
| Importer | **legacy `FbxFactory`**, не Interchange | HANDBOOK §4.6 |
| Import Uniform Scale | **1.0** (ручной Scale — дефект) | HANDBOOK §2.1 |
| Normals | `ImportNormals` (импорт из FBX, не пересчёт) | HANDBOOK §4.6 |
| Nanite | выкл | HANDBOOK §4.6 |
| Import Materials | **false** — MI делаются от мастеров отдельно | HANDBOOK §4.6 |
| Physics Asset / Morph Targets | не создаются | HANDBOOK §4.6 |
| Skeleton | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton` | skeletal-adopt |
| Material slots | 1 на фигуру, 1 на подставку; назначаются MI | HANDBOOK §2.5 |
| Коллизия | **нет**: `UCX_/UBX_` в FBX отсутствуют, выбор фигуры — капсула в коде по bounds меша | HANDBOOK §2.5 |
| LOD | не генерируются, только LOD0 (отчёт ждёт LOD = 1) | HANDBOOK §2.5 |
| Подставка SM_ | Generate Lightmap UVs = off (иначе UV1 перезапишется) | HANDBOOK §2.5 |

### 4.2 Параметры импорта (клипы AM_)

`review/ue_py/import_clips.py` внутри `h2anim_ue.py import`: animation-only (Import Mesh off, Import
Animations on — как в Epic FBX Animation Pipeline, не проверено), legacy `FbxFactory`,
`bForceRootLock=true`, `bEnableRootMotion=false`, скелет — канонический `<Key>_Skeleton`; существующий клип
удаляется и импортируется заново (никогда не «обновлять поверх»). Клипы все in-place: арматура и `root` не
ключуются, дрейф ≤ 0,5 % роста.

## 5. Валидация после импорта

- [ ] `reports/ue-import-report.json` → `technically_imported`, все checks passed: кость 0, нет лишних костей,
      фронт +X, bounds = прогноз ± 0,05 uu, высота, треугольники, LOD = 1, сокеты, подставка по центру с низом
      в z = 0, UV-каналов 2, MI от мастеров, не dirty (HANDBOOK §4.6).
- [ ] Скелет совпадает с контрактом: 18 костей в UE (17 у Harpy) = кость 0 (`SKEL_UM_Humanoid`) + `root` +
      `hips` + …; имена `_L/_R` (Blender `.L/.R` → UE `_L/_R`); иерархия `UM_HUMANOID_17_v2` из
      `docs/art-pipeline/rig/rig-contract.json`.
- [ ] Материал-слоты: ровно 1 на фигуре, 1 на подставке; слот назначен на `MI_<Key>_<Stage>_<Team>`.
- [ ] Текстуры: размеры 2K runtime (2048×2048), sRGB только на BC, компрессия по таблице §2.1, суффикса `_RM` нет.
- [ ] Масштаб в меркам доски: 1 клетка доски = 1 м = 100 uu; высоты из `Specs()`
      (`S08HeroesV2.cpp:105-110`): Arthur 55 uu (52–56), Merlin 45 (40–48), Medusa 55 (50–55), Harpy 42
      (35–42); `FigureScale` зажат 0,5–2,0, автотест требует попадание в бюджет ±1 %. Бюджет НОВОГО героя
      приходит из `FIGURE_HEIGHT_M` заявки этапа 0 (SKILL.md §6, uu = м × 100) и прописывается в строку
      `Specs()` правкой подключения §6 п. 1 — другого источника высоты в скилле нет.
- [ ] Клипы: `h2anim_ue.py measure <spec>` — кадр 0 = ref pose (0, 0 uu), кость 0 неподвижна, масштаб 1,0;
      длительности: Idle из спеки героя, остальные 14/10/21 кадров / 24 fps (допуск автотеста ±0,02 с).
- [ ] Сокеты: `Weapon` на `weapon_L`/`weapon_R`, `Head` на `head`, offset (0,0,0); живой `get_socket_location`
      против цели ± 0,05 uu. Фигура без сокета `Head` выпадает из evidence-съёмки (`S08FlowGameMode.cpp:5044-5047`).
- [ ] Кадры и съёмка: редакторные кадры `h2anim_ue.py frames/sheet` — с пометкой «EDITOR frame … not K1/K2
      acceptance»; look-dev съёмка `python tools/art/material_library/ue_h5cb1.py review --hero <hero> --tag <bN>`
      (зоны против концепта: яркость ±15 %, тон ±12°, насыщенность ±0,10).
- [ ] Скриншот в evidence: кадры — JPEG 1200 px q92 + `*.evidence.json`
      (`tools/tripo-pipeline/review/frames_to_jpeg.py`), в `docs/art-pipeline/evidence/<asset>-<дата>/`;
      финальные приёмочные кадры — только свежий `-Bench` прогон, не редакторные.
- [ ] Снимок после: `ue_content_snapshot.py <evidence>/snapshot-after.json --compare <evidence>/snapshot-before.json`
      → `protected_unchanged: true`, добавлены только свои ассеты.
- [ ] Автотесты `Unmatched.S08.HeroesV2.*`: масштаб ±1 %, bounds ±0,5 uu, длины клипов ±0,02 с, клипы на
      скелете меша.
- [ ] Реестр обновлён, `validate_registry.py` → PASS (HANDBOOK §8).

Статусы этапа: предложено → измерено → технически импортировано → художественно принято. «Технически
импортировано» = все пункты чек-листа выше (HANDBOOK §8).

## 6. Подключение в игру S08 (если задача это включает)

Новый или переименованный герой требует трёх правок, иначе игра молча откатится на fallback
(`S08FighterActor.cpp:~845-880`: LoadObject меша/подставки/MI, проверка Idle-клипа; трейс
`ARTPREVIEW heroesV2 fighter=… missing=… fallback=legacy` на строке 877 — нет меша/скелета/подставки/MI/Idle →
старая фигура):

1. Строка в таблице `Specs()` `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp`: имя бойца с сервера,
   ключ, стадия, бюджет высоты, диапазон, верх фигуры, верх bounds, IdleSeconds, LungeContactFrame.
   `MeshPath`/`PedestalPath` собираются как `/Game/PipelineCandidates/<Key>/<Stage>/Meshes/SK_<Key>_<Stage>`
   (`S08HeroesV2.cpp:130-136`).
2. Три строки `+DirectoriesToAlwaysCook` в `unreal/Unmatched/Config/DefaultGame.ini`:
   `<Key>/<Stage>`, `<Key>/Rig`, `<Key>/H2Anim` (кукер не видит soft-ссылки `LoadObject`; проверять
   `UnrealPak -List`). Факт по текущему файлу: строки 33–44 для KingArthur/Merlin/Medusa/Harpy
   (у Harpy стадия `H3LD`, но анимации — `H2Anim`).
3. `.uasset` в git только `git add -f` поимённо (Content игнорируется).

Клипы играются напрямую кодом (`AS08FighterActor::PlayHeroClip`), AnimMontage/BlendSpace/ABP в проекте нет —
их не добавлять. Общий ретаргет/IK Retargeter на четверых не доказан; каждый клип авторится на своём риге.

## 7. Типовые ловушки

| Ловушка | Симптом | Правило |
|---|---|---|
| Масштаб ×100 | фигура гигантская/крошечная, кость 0 смещена | Import Uniform Scale = 1.0; ×100 уже зашит в данные FBX пресетом; ручной Scale при импорте — дефект |
| Ось Y | герой смотрит боком/спиной | зеркало координат `ue(x,y,z) = blender_export(x,−y,z)`; фронт проверяется в отчёте (+X); суффиксы костей `.L/.R` → `_L/_R` |
| Двойные трансформы | перекошенный меш, «плывущие» конечности | rotation и scale применены до экспорта, отрицательного масштаба нет (HANDBOOK §2.1); rest pose = поза миниатюры |
| Потеря материалов | серый меш | это норма: `import_materials=false`; MI назначаются от мастеров руками/скриптом. Слот один; имя слота `M_<Hero>_H2_Atlas`-стиль, не `Element_0` |
| `_RM` в UE | неверный метал/рафness | ORM = R AO / G Rough / B Metallic; RM — промежуточная карта Tripo/glTF |
| Нормали «вывернуты» | тёмные пятна на тонких деталях | матрица поворота +90°Z должна быть снапнута к целым (пресет делает); N импортируется DirectX, `flip_green=false` |
| Leaf-кости | лишние кости в UE-скелете | `add_leaf_bones=false` |
| Клип без меша | AnimSequence не создаётся | один FBX на клип обязательно с узлом меша |
| «Обновить» клип поверх | смешение старых ключей | старый ассет удаляется перед повторным импортом |
| Кукер выбросил ассеты | в паке нет фигуры | `+DirectoriesToAlwaysCook` три строки на героя; проверка `UnrealPak -List` |
| Переимпорт сломал скелет | ссылки клипов отвалились | меш сажается через skeletal-adopt `ue.target_skeleton` на канонический `SK_<Key>_Skeleton` |
| Арматура не `SKEL_UM_Humanoid` | риг-валидатор FAIL | контракт `UM_HUMANOID_17_v2`; старый `SKEL_Medusa`/`weapon` — только история |
| UV1 у подставки перезаписан | артефакты декалей/тайлов | Generate Lightmap UVs = off у `SM_*_Base` |

## 8. Шаблон: чек-лист сдачи этапа 6

```markdown
# <ASSET-ID> — упаковка под UE, <YYYYMMDD>

Run: art/pipeline-candidates/<ASSET-ID>/<YYYYMMDD>-<suffix>/
Профили: <hero>-h2ld-lookdev-ue-import.json, <hero>-h2anim.json (новые файлы, SHA в manifest)
Скелет: /Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton, костей в UE: 18 (17 Harpy)

- [ ] export/SK_<Hero>_H2LD.fbx, SM_<Hero>_H2LD_Base.fbx, AM_<Hero>_{4 клипа}.fbx (UM_FBX_v1, STRIP)
- [ ] Текстуры 2K: BC(sRGB)/N(DirectX)/ORM(R=AO,G=R,B=M)/MatID/Edge/TeamAccent + LUT .dds; _RM нет
- [ ] ue-import-report.json: technically_imported, checks: [...] → все True
- [ ] h2anim_ue.py measure: кадр 0 = (0, 0 uu), кость 0 неподвижна, масштаб 1.0
- [ ] Сокеты Weapon/Head: get_socket_location ± 0.05 uu
- [ ] Высота в бюджете Specs() ± 1 % (клетка доски = 100 uu)
- [ ] Снимок до/после: protected_unchanged: true
- [ ] Автотесты Unmatched.S08.HeroesV2.* — PASS
- [ ] Evidence: docs/art-pipeline/evidence/<asset>-<дата>/ — JPEG 1200 q92 + *.evidence.json
- [ ] (если подключение) 3 правки: Specs() + DefaultGame.ini (3 строки cook) + git add -f поимённо
- [ ] В git НЕ идут: work/, logs/*.log, *.fbm/, 4K-мастера, сырые GLB
```
