# Валидация тестового клипа: FBX/BVH/GLB → Blender → отчёт

Срез 2026-09-28, задача P1.6; дополнено 2026-09-29 (контракт рига v2, волна 4, W4-D — раздел «Контракт v2» ниже). Скрипт: [validate_clip.py](../../../tools/tripo-pipeline/anim/validate_clip.py). Контракт: [rig-contract.json](../rig/rig-contract.json). Прогон всех кейсов этой задачи: [run_p16_validation.py](../../../tools/tripo-pipeline/anim/run_p16_validation.py). Отчёты лежат в [validation/](validation/).

Валидатор только читает клип: он открывает его в пустой сцене headless Blender 5.2 и ничего не сохраняет. **PASS означает техническое соответствие контракту, а не художественную приёмку.** Пример из этого прогона: пресет Tripo на сломанном риге получил PASS, хотя визуально он неприемлем.

**Только headless.** `validate_clip.py`, `inspect_rig.py`, `rig_deform_probe.py` и `make_fixtures.py` запускаются только через `blender -b`. Причина: `read_factory_settings` в живом Blender выгружает аддон MCP (так 2026-09-28 упал :9877), а `os._exit` в `validate_clip.py` завершает весь процесс Blender вместе с чужой сценой.

Без `-b` скрипт бросает `RuntimeError` и ничего не делает (`if not bpy.app.background: raise RuntimeError(...)`, до импорта файлов и `read_factory_settings`). Аддон MCP ловит `Exception` и вернёт её клиенту как ошибку, Text Editor → Run Script покажет отчёт, процесс Blender останется жив. `SystemExit`, `sys.exit` и `os._exit` для такой защиты не годятся: в живом Blender они завершают весь процесс. `SystemExit` наследует `BaseException`, проходит мимо `except Exception` аддона MCP, и C-код Blender на нём вызывает выход. Проверено в headless Blender 5.2.2 с подменой `bpy.app.background=False` для исполняемого текста. Проверены два пути: exec в `try/except Exception` из C-колбэка, как у `execute_code` аддона, и `bpy.ops.text.run_script`. С `RuntimeError` оба пути дают код 0, процесс жив. С прежним `SystemExit` оба дают код 1. Таймер аддона в `-b` не выполняется, поэтому путь через него не проверялся; механизм тот же. Защита страхует только от случайного запуска. Выполнять эти скрипты в живом Blender по-прежнему нельзя.

## Запуск

```bash
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
"$B" -b --factory-startup --python tools/tripo-pipeline/anim/validate_clip.py -- \
    blender/ASSET-MEDUSA-001/export/AM_Medusa_Idle.fbx \
    --expect-duration=2.3333 --loop=true \
    --out=docs/art-pipeline/animation-library/validation/AM_Medusa_Idle.validation.json
# код выхода: 0 = нет FAIL, 1 = есть FAIL, 2 = ошибка запуска
```

Опции (все необязательные):

| Опция | Значение по умолчанию | Что задаёт |
| --- | --- | --- |
| `--skeleton=` | `contract.default_skeleton` = `UM_HUMANOID_17_v2` | ключ скелета в контракте; `UM_HUMANOID_17_v1` закрыт для новых клипов (WARN только файлам из `grandfathered_files`) |
| `--character=` | нет | `Medusa`, `Arthur`, `Merlin`, `Harpy`: какая кость оружия обязательна (`weapon.L` / `weapon.R` / нет) |
| `--kind=` | `clip` | `skeletal-mesh`: только арматура, кости, оружие и ref-поза (SK без action) |
| `--clip-role=` | `idle` при `--loop=true`, иначе `oneshot` | граница клипа: `idle`/`oneshot` — кадр 0 и последний = rest, `terminal` (DeathSettle) — только кадр 0 |
| `--expect-fps=` | 24 (контракт) | ожидаемый FPS |
| `--expect-duration=`, `--duration-tol=` | нет / 0,05 с | длительность клипа |
| `--loop=true` | false | включает проверку шва цикла |
| `--root-policy=` | `in_place` | `in_place`, `root_motion` (движение на объекте арматуры) или `any` |
| `--min-pose-change=` | 0,02 роста | порог видимого изменения позы |
| `--pose-change-mode=warn\|fail` | `warn` (контракт) | что давать ниже порога; `warn` до калибровки порога |
| `--retarget-map=` | нет | сравнивать скелет через карту из контракта (для внешних клипов) |
| `--bvh-up=Y\|Z` | Y | Y — стандартный mocap-BVH, Z — BVH, экспортированный из Blender |

## Проверки

| Проверка | Как считается | FAIL, если |
| --- | --- | --- |
| `import`, `single_armature`, `action` | импорт FBX/BVH/GLB, одна арматура, у неё есть action | импорт упал, арматур не одна, action нет |
| `skeleton_version` | закрыт ли скелет для новых клипов (`closed_for_new_clips`) и есть ли sha256 файла в `grandfathered_files` | v1 и файл не в списке — FAIL; в списке — WARN; v2 — PASS |
| `armature_object_name` | имя объекта арматуры (= кость 0 в UE) против `armature_object.name` контракта (`SKEL_UM_Humanoid`) | имя другое; старые имена из `legacy_names` (`SKEL_Medusa`, `SKEL_S05_*`) — по `legacy_policy`: v2 FAIL, v1 WARN; для BVH и `--retarget-map` — info |
| `weapon_side` | кость оружия по стороне (v2): `weapon.L` под `hand.L`, `weapon.R` под `hand.R`, не больше одной; с `--character` — именно своя | одно имя `weapon`, две кости оружия, чужая сторона, неверный родитель, оружие у Harpy; для v1 — info |
| `ref_pose_facing` | анатомический yaw ref-позы: боковой вектор `.L − .R` (головы `arm_upper`, `leg_upper`) × Z, угол от +X | вне 0 ± 10° (UM_FBX_v1: лицо +X); для BVH и `--retarget-map` — info |
| `ref_pose_root_axis` | направление оси X кости `root` в плоскости XY | WARN вне 90 ± 10° (жёсткий поворот UM_FBX_v1 с roll) |
| `clip_boundary_rest` | макс. расстояние голов и хвостов pose-костей от rest-позы на первом и последнем кадре (в мире того же кадра), доля роста | больше 0,5 % роста на кадре 0 или (для `idle`/`oneshot`) на последнем |
| `bone_length_plausible` | самая длинная кость в мировых координатах, доля роста | WARN, если длиннее роста: эвристика длин импортёра сломана, сдвиги по хвостам недостоверны |
| `fps` | `scene.render.fps / fps_base` после импорта | отклонение больше 0,001 |
| `duration` | (frame_end − frame_start) / fps | вне допуска (если задано ожидание) |
| `skeleton_contract` | имена и родители против контракта | не хватает костей или неверный родитель (лишние кости дают WARN) |
| `skeleton_via_retarget_map` | покрытие костей контракта картой ретаргета | часть костей контракта не покрыта |
| `bones_move` | макс. угол поворота каждой pose-кости относительно первого кадра | ни одна кость не повернулась больше 0,5° |
| `bone_scale_unit` | отклонение scale от 1 | WARN при отклонении больше 0,001 |
| `root_in_place` | путь объекта арматуры (кость 0 UE) и pose-кости `root` | смещение или размах больше 0,5 % роста |
| `visible_pose_change` | пиковый сдвиг головы или хвоста любой кости относительно первого кадра, в долях роста | ниже 2 % роста — **WARN** (порог — предложение, не откалиброван; FAIL только с `--pose-change-mode=fail`) |
| `loop_seam` | средний сдвиг суставов между первым и последним кадром | больше 0,5 % роста (только при `--loop=true`) |

Рост берётся из габарита **скиненных** мешей клипа (с модификатором Armature на эту арматуру). Служебные объекты импортёра glTF (Icosphere формы костей в коллекции `glTF_not_exported`) не учитываются. Если скиненного меша нет (BVH), рост считается по головам и хвостам костей.

Ветка GLB импортирует с `bone_heuristic="TEMPERANCE"` и `disable_bone_shape=True`. Эвристика по умолчанию (`BLENDER`) при масштабе объекта арматуры 0,01 завышает длины костей в 100 раз: хвосты улетают. Старая версия валидатора на GLB-фикстуре давала рост 2,0 (с Icosphere) и пик сдвига 1,257 роста; исправленная — рост 0,512 и пик 0,106, как у FBX.

## Результаты на старых клипах Medusa (только тестовые файлы, не приняты)

Команда: `python tools/tripo-pipeline/anim/run_p16_validation.py` (сводка в [validation/summary.json](validation/summary.json)). Все 9 кейсов дали ожидаемый код выхода и ожидаемые предупреждения, перекрёстная проверка GLB против FBX прошла; раннер вернул 0.

Раннер возвращает **1**, если кейс не выполнен (нет входного файла — `skipped_missing_input`, нет отчёта — `no_report`), если код выхода или список WARN не совпал с ожиданием, или если перекрёстная проверка GLB не прошла. Фикстуры лежат в отслеживаемом каталоге [fixtures/](../../../art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/fixtures/), без перевода строк (`.gitattributes`: `* -text`).

У FBX- и GLB-файлов Medusa объект арматуры называется `SKEL_Medusa`, поэтому у них есть WARN `armature_object_name` (старое имя, см. RIG-CONTRACT §2). У BVH-фикстуры и у пресета Tripo с картой ретаргета эта проверка информационная. В таблице WARN по имени не повторяется.

| Клип | fps | Длительность, с | Двигаются кости | Пик сдвига, доля роста | root | Итог |
| --- | --- | --- | --- | --- | --- | --- |
| AM_Medusa_Idle (loop) | 24 | 2,333 (57 кадров) | spine 2,5°, head 3° | **0,012** | 0 | PASS с **WARN** `visible_pose_change`: ниже предложенного порога 2 %, визуально не проверено; шов цикла 0 |
| AM_Medusa_LungeAttack | 24 | 0,583 | arm_upper.R 35°, arm_upper.L 17°, spine 12° | 0,109 | 0 | PASS |
| AM_Medusa_HitReact | 24 | 0,375 | spine 10°, head 10° | 0,133 | 0 | PASS; длительность в допуске ±0,05 с от 0,4 с (04), вне 0,9 с (CUE-011) |
| AM_Medusa_DeathSettle | 24 | 0,875 | spine 48°, head 25° | 0,512 | 0 | PASS |
| BVH-фикстура LungeAttack (round-trip, `--bvh-up=Z`) | 23,9998 | 0,583 | те же | 0,109 | 0 | PASS: ветка BVH даёт те же числа, что FBX |
| GLB-фикстура LungeAttack (round-trip) | 24 | 0,583 | те же | 0,106 | 0 | PASS: рост 0,512 (только `SK_Medusa_Body` и `SK_Medusa_Bow`, без Icosphere); от FBX пик отличается на 2,7 % (допуск раннера 25 %), рост — на 0 % (допуск 2 %) |
| Tripo «стоя_отдых» (d562f057, `--retarget-map=tripo_ue5_mannequin_to_um17`) | 24 | 17,583 | 51 кость, head 34° | 0,089 | 0 (in place) | PASS технически. Статус в манифесте — `rejected`: риг сломан, длина 17,6 с вместо 2–3 |
| Негатив: SK_Medusa.fbx без анимации | — | — | — | — | — | FAIL `action` (ожидалось) |
| Негатив: клип Tripo без карты ретаргета | 24 | 17,583 | — | — | — | FAIL `skeleton_contract` и `armature_object_name` (объект `Armature`) (ожидалось) |

Вывод по черновым клипам: у всех root неподвижен, FPS 24, длительности совпадают с README кандидата. У Idle пиковый сдвиг 1,2 % роста (около 0,7 uu на фигурке 55 uu). Это ниже **предложенного** порога 2 %, но порог не откалиброван, а клип визуально на K2/K3 не проверялся. Поэтому это WARN, а не вывод «движение не видно»: бриф требует от Idle лёгкого дыхания, и тонкий Idle может быть нормой. HitReact 0,375 с попадает в допуск ±0,05 с от 0,4 с (04) и не попадает в 0,9 с (CUE-011); какая длительность нужна, остаётся открытым.

Фикстуры пересоздаются из отслеживаемых исходников; исходный FBX и zip не меняются. BVH, GLB и FBX пресета, созданные скриптом, побайтно совпадают с лежащими в `fixtures/` (проверено двумя прогонами):

```bash
"$B" -b --factory-startup --python tools/tripo-pipeline/anim/make_fixtures.py -- all
# bvh   -> fixtures/AM_Medusa_LungeAttack.bvh  (export_anim.bvh из AM_Medusa_LungeAttack.fbx)
# glb   -> fixtures/AM_Medusa_LungeAttack.glb  (export_scene.gltf, без картинок и материалов)
# tripo -> fixtures/tripo-preset-stoya-otdyh-d562/*.fbx  (из source/*-stoya-otdyh-*.zip, без .fbm)
```

## Контракт v2 (2026-09-29)

Контракт: [rig-contract.json](../rig/rig-contract.json) `unmatched.rig-contract/2`, описание — [RIG-CONTRACT.md §0](../rig/RIG-CONTRACT.md). Правила, которые не требуют Blender, вынесены в `tools/tripo-pipeline/anim/rig_rules.py` и покрыты юнит-тестами `tools/tripo-pipeline/tests/test_rig_rules.py` (21 тест: вердикты, самосогласованность `ik_chains`, sha256 старых файлов, профили героев `/4`, уникальность `profile_id`).

Прогон файлов: `python tools/tripo-pipeline/anim/run_rig_v2_validation.py` — 11 кейсов с ожидаемым кодом выхода и **точным** набором FAIL; отчёты — [validation-rig-v2/](validation-rig-v2/summary.json). Позитивная фикстура — синтетический клип `fixtures/rig-contract-v2/AM_RigV2_LungeAttack_weaponL.fbx` (`make_fixtures.py rigv2`: объект `SKEL_UM_Humanoid`, `weapon.L`, rest и меш повёрнуты на +90° как в UM_FBX_v1; побайтно повторяется двумя прогонами, sha256 `1945533a…646b`). Это фикстура проверки, не клип для игры.

| Кейс | Ожидание | Что показывает |
| --- | --- | --- |
| `pos-rigv2-Medusa-oneshot` | PASS | все проверки v2 проходят на правильном файле |
| `neg-rigv2-as-Arthur` | FAIL `skeleton_contract`, `weapon_side` | у Arthur оружие `weapon.R` |
| `neg-draft-Lunge-v2` | FAIL `armature_object_name`, `weapon_side`, `ref_pose_facing` | черновик Medusa как новый клип: `SKEL_Medusa`, одно имя `weapon`, лицо −Y |
| `legacy-draft-Lunge-v1-grandfathered` | PASS, WARN `skeleton_version` | старый черновик допущен на закрытом v1 по sha256 |
| `neg-rigv2-on-closed-v1` | FAIL `skeleton_version`, `skeleton_contract` | новый файл на закрытом v1 |
| `neg-draft-DeathSettle-v1-as-oneshot` / `legacy-…-terminal` | FAIL `clip_boundary_rest` / PASS | финальная поза допустима только для `terminal` |
| `neg-sk-Arthur-cli-v1-as-v2`, `neg-sk-Merlin-cli-v1-as-v2` | FAIL `skeleton_contract`, `weapon_side` | SK CLI 20260928 требуют пересборки с `weapon.R` (профили `/4`) |
| `ext-tripo-preset-retarget-map-v2` | PASS | внешний клип: имя кости 0, ref-поза и граница — info |
| `err-unknown-character` | код 2 | неверная опция — ошибка запуска |

Черновые клипы P1.6 проверяются явно против закрытого v1: `run_p16_validation.py` передаёт `--skeleton=UM_HUMANOID_17_v1` и роль (`DeathSettle` — `terminal`). Повтор 2026-09-29 в `--out-dir` (без перезаписи отчётов P1.6 от 2026-09-28): 9/9 кейсов с ожидаемым итогом, перекрёстная проверка GLB — PASS (рост 0 %, пик 2,652 %); добавился только WARN `skeleton_version`.

## Приём клипа в библиотеку

1. Положить FBX (или BVH) и записать источник и лицензию в [clip-manifest.json](clip-manifest.json). Для этого сначала добавить запись в `build()` файла `tools/tripo-pipeline/anim/clip_manifest.py` (по образцу `medusa_draft`/`tripo_test`), затем выполнить `build`.
2. Запустить `validate_clip.py` с ожиданиями слота (длительность, loop, root policy) и с `--character=<герой>` и `--clip-role=` (DeathSettle — `terminal`). Внешнему клипу на чужом скелете сначала нужен ретаргет в контракт. До ретаргета допускается только `--retarget-map`, и это не заменяет перекладку.
3. `python tools/tripo-pipeline/anim/clip_manifest.py check`: схема, наличие файлов, sha256, правило «measured и выше требуют PASS». Файлы клипа и фикстуры должны лежать в отслеживаемом каталоге (`source/`, `fixtures/`), а не в игнорируемом `work/`, иначе после checkout проверка упадёт.
4. Посмотреть клип глазами: в Blender или на листе. Технический PASS без просмотра не повышает статус выше `measured`.
5. Импорт в UE — отложен (ниже).

## Отложено до освобождения UE (UE в этой задаче не использовался)

Точные шаги для следующего этапа, когда редактор свободен:

1. Закрыть живой UnrealEditor или договориться с владельцем :8123. Если нужен headless-путь, запускать `UnrealEditor-Cmd` на **копии** проекта или после окончания работы T4.
2. Импортировать клип с опциями функции `import_clip` из `tools/art/import_medusa_candidate.py` (с ней на текущем экспорте получены 55 uu и `root_delta_uu = 0`):
   - legacy FBX (`-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False`);
   - `FbxImportUI`: `import_mesh=False`, `import_as_skeletal=True`, `mesh_type_to_import=FBXIT_ANIMATION`, `import_animations=True`, `import_materials=False`, `import_textures=False`, `skeleton=/Game/ART004/Medusa/Meshes/SK_Medusa_Atlas_Skeleton`;
   - масштаб импорта анимации **не задавать**, как в `import_clip` (значение по умолчанию); для меша — `import_uniform_scale=1.0`. Значение 100 из памяти S05 — конфликт с другим профилем экспорта (RIG-CONTRACT §5). Перед импортом прочитать фактическое значение по умолчанию `anim_sequence_import_data.import_uniform_scale` и записать его в отчёт;
   - другие опции (например `animation_length`) не задавать: они не проверялись;
   - назначение `/Game/PipelineCandidates/ASSET-MEDUSA-001/Animation/`.
3. Проверить в UE Python:
   - `AnimSequence.get_play_length()` = длительность из отчёта ±0,05 с;
   - `get_number_of_sampled_keys()` = `frames` из отчёта;
   - частота 24;
   - список треков костей совпадает с 17 именами (+ кость 0 от объекта арматуры; у текущих клипов Medusa это `SKEL_Medusa`, по контракту — `SKEL_UM_Humanoid`);
   - направление «вперёд»: стандарт UM_FBX_v1 — +X; на Medusa раньше измерено +Y (RIG-CONTRACT §5). Записать, что получилось.
4. Root motion: включить `EnableRootMotion`, снять позу кости 0 на первом и последнем кадре через `unreal.AnimPoseExtensions.get_anim_pose_at_time`. Для in place дельта должна быть 0 uu (так в `blender/ASSET-MEDUSA-001/ue-animation-report.json`).
5. Сокеты `Weapon`/`Head` на SK следуют позе на кадре пика (лук у кисти).
6. Визуально: проиграть клип на K2/K3 в изолированной сцене ART004 (`tools/art/art004_scene.py`) и сохранить кадры в `docs/game-design/evidence/ART-004/`. Художественная приёмка остаётся за автором.
