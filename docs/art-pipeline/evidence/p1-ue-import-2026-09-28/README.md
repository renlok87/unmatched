# P1 в живом UE: бочка и тестовый клип (этап 3, волна 2, T2.1)

Дата: 2026-09-28. Редактор: живой UnrealEditor 5.8.2 (PID 19540), проект `unreal/Unmatched` главного checkout,
MCP 127.0.0.1:8123. UnrealEditor-Cmd не запускался. Blender :9876 использован только для запроса версии
(preflight CLI), сцена не менялась. Валидатор клипов и стадии нового passthrough-run работали в headless Blender
(`-b`). Второй круг (13:03–13:07 UTC) исправлял замечание ревью: passthrough вынесен из снимка `pipeline/` в новый run (§1).

**UE-контент только локальный.** Все ассеты этой задачи — `.uasset` в `unreal/Unmatched/Content/`. Этот каталог
в `.gitignore` (`unreal/Unmatched/.gitignore`, правило `Content/`). Часть ассетов других задач добавлена в git
принудительно, но ассетов этой задачи среди них нет: `git ls-files unreal/Unmatched/Content/PipelineCandidates`
пуст. Они существуют только в checkout, где открыт редактор (`C:/Users/ren/WebstormProjects/unmached/unmached`):
`/Game/PipelineCandidates/DecorBarrel/20260928-p15-barrel/{Candidate,Passthrough}` и
`/Game/PipelineCandidates/Medusa/DraftClips20260928/T4LocalPass`. В git лежат только run-каталоги, отчёты и этот
акт. В другом checkout ассеты воспроизводятся командами §1–§3 и [commands.txt](commands.txt).

**Статусы.** Бочка: «технически импортировано» (кандидат и passthrough). Клипы LungeAttack и HitReact:
«технически импортировано», замеры PASS. Idle — негативный контроль, пойман (FAIL, как ожидалось). Кадры —
**редакторные** (`-ue-editor-`, класс `editor-mcp-viewport`), диагностика, не приёмка K-1/K-2.
Художественной приёмки нет ни у чего.

## 0. Preflight и базовый снимок

- :8123 слушает PID 19540, проект — этот checkout, открыт `/Game/S08/S08Arena`, несохранённых пакетов 0,
  `Interchange.FeatureFlags.Import.FBX = true`
  ([snapshot-before.json](snapshot-before.json), раздел `editor`).
- `find_assets` до работы: `/Game/ART004` 17, `/Game/ArtPreview` 9, `/Game/PipelineCandidates` 18 ассетов;
  плюс SHA-256 всех файлов этих папок на диске.
- Команды и выводы: [commands.txt](commands.txt).

## 1. (а) Passthrough-контракт CLI

Итоговый прогон — **новый run** `art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel/ue-passthrough/`
(CLI 0.4.0, run id `20260928-p15-barrel-ue-passthrough`). Закоммиченный `20260928-p15-barrel/pipeline/` — снимок
регистрации CLI 0.3.0 (prop-barrel-report §3) — в итоге **не изменён**, его байты равны `git HEAD`.

```
T="python tools/tripo-pipeline/tripo_pipeline.py"; RUN=art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel/ue-passthrough
$T init --run-dir $RUN --asset-id ASSET-DECOR-KIT-001.BARREL --primary-source tripo-3f7a258f \
   --primary-role smartuv-tex2k-pbr-glb --export-basename SM_Decor_Barrel_TripoPassthrough --run-id 20260928-p15-barrel-ue-passthrough
$T register-source --run-dir $RUN --spec art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json
$T run --run-dir $RUN                                   # headless Blender: preflight, import, verify, export
$T --backend mcp ue-import --run-dir $RUN --ue-folder /Game/PipelineCandidates/DecorBarrel/20260928-p15-barrel/Passthrough
```

История (все шаги — в [commands.txt](commands.txt)):

- Первый круг запускал `ue-import` прямо на снимке `pipeline/`. `ue-import` не входит в запрещённый для снимка
  список, но стадия дописала в его `manifest.json` и `journal.jsonl` `config.ue` и стадию 0.4.0 рядом со стадиями
  0.3.0. По замечанию ревью это откатано: `manifest.json` и `journal.jsonl` возвращены к `git HEAD`, отчёты
  `pipeline/reports/ue-*.json` убраны из run. Копии откатанных файлов лежат вне git в
  `C:/tmp/t21fix/backup-pipeline-snapshot-ue-import/`.
- Четыре ассета, которые создал импорт снимка, удалены из папки `Passthrough` до нового импорта. Перед удалением
  проверено, что листинг равен `ue_owned_assets` снимка
  ([barrel-passthrough-snapshot-assets-deleted.json](barrel-passthrough-snapshot-assets-deleted.json)).
- **Первая попытка первого круга упала** на `folder_contains_only_this_import`
  ([barrel-passthrough-ue-import-report-0-failed-first-attempt.json](barrel-passthrough-ue-import-report-0-failed-first-attempt.json),
  run `pipeline/`). Причина измерена: `StaticMeshTools.import_file` в UE 5.8 возвращает только меш. Материал и две
  текстуры, которые импортёр создаёт рядом, в ответ не попадают, а проверка ждала их в ответе (фейк теста их
  возвращал).
- Исправление CLI: проверка требует пустую папку перед вызовом и допускает рядом только побочные продукты импорта
  (Material, MaterialInstanceConstant, Texture2D). Фейк UE теперь возвращает только меш, как живой редактор.

Результат нового run:

- `run`: регистрация 11 файлов, потрачено 0; preflight, import, verify, export выполнены. FBX
  `export/SM_Decor_Barrel_TripoPassthrough.fbx` `ee656a70…` (4 393 260 байт) — тот же хеш, что предсказан в
  prop-barrel-report §7 для CLI 0.4.0. Экспорт по UM_FBX_v1 (поворот +90° по Z), у снимка 0.3.0 FBX `f9c9042a…`
  без этого поворота.
- `ue-import`: `technically_imported`, 4 ассета (меш, материал Tripo, 2 текстуры), папка перед импортом пуста,
  3837 треугольников LOD0, 1 слот, **80,704 × 80,472 × 97,974 uu** по осям UE X, Y, Z = ожидание export-отчёта
  (80,7037 × 80,4718 × 97,9736) ±1 % по каждой оси
  ([report-1](barrel-passthrough-ue-import-report-1-import.json), [listing-1](barrel-passthrough-ue-listing-1-after-import.json)).
  X и Y переставлены относительно импорта снимка 0.3.0 (80,472 × 80,704, см. report-0): это поворот UM_FBX_v1, и живой UE его
  подтвердил. Значит, на живом UE проверен passthrough-экспорт текущего CLI, а не только снимок 0.3.0.
- Повторный `ue-import`: `skipped`. Повторный headless `run`: import/verify/export `skipped`, `ue-import` не
  запускается без `--backend mcp`. `--force`: свои 4 ассета удалены и импортированы заново, листинг тот же,
  `Name_1` нет; отчёт отличается от первого только списком `previous_assets_deleted`
  ([report-2](barrel-passthrough-ue-import-report-2-forced.json), [listing-2](barrel-passthrough-ue-listing-2-after-force.json)).
  После `--force` ещё один `ue-import` — `skipped`.
- Отчёты в run (`ue-passthrough/reports/ue-import-report.json` и `ue-mcp-calls.json`) побайтно равны `report-2` и
  `mcp-calls-2` этого каталога, их SHA-256 совпадают с записью стадии в `ue-passthrough/manifest.json`.
- Побочный эффект: импортёр извлекает встроенные текстуры FBX в `<run>/export/SM_Decor_Barrel_TripoPassthrough.fbm/`.
  Каталог вынесен из checkout, а в `.gitignore` пропса есть `*.fbm/`. Там же добавлены правила
  `*/ue-*/{work,.staging,run.lock,*.tmp-*}` для run-каталогов `ue-passthrough` и `ue-candidate`
  (`work/*.blend` 7,3 МБ не коммитится, как у `pipeline/`).

## 2. (б) Кандидат `export/SM_Decor_Barrel.fbx`: профиль `static-candidate`

В CLI добавлен профиль `static-candidate` (стадии `preflight → adopt → ue-import`), 8 новых тестов
(описание — [PIPELINE.md](../../PIPELINE.md#профиль-static-candidate-этап-3-t21)). Профиль сборки:
[decor-barrel-static-um-fbx-v1.json](../../../../art/pipeline-candidates/ASSET-DECOR-KIT-001/build-profiles/decor-barrel-static-um-fbx-v1.json).
Run: `art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel/ue-candidate/`. Папка UE:
`/Game/PipelineCandidates/DecorBarrel/20260928-p15-barrel/Candidate`.

`adopt` ([adopt-report.json](../../../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel/ue-candidate/reports/adopt-report.json)):
байты FBX и BC/N/ORM равны candidate-report, все проверки кандидата прошли, исходник = первичная роль
`smartuv-tex2k-pbr-glb`, настройки экспорта = UM_FBX_v1. По read-back: 3790 треугольников, 1 меш без арматуры,
0 открытых и 0 неманифолдных рёбер, 0 несогласованных граней. Из candidate-report (Blender, без изменений):
0 перевёрнутых UV-треугольников, минимальный зазор 3 px @1K (риск мипов §4.3 остаётся открытым).

Измерено в UE ([ue-import-report](barrel-candidate-ue-import-report-1-import.json)):

| Контракт | Ожидание | Измерено |
|---|---|---|
| Ассеты | 6 по плану, `Name_1` нет | SM, M, MI, 3 × Texture2D |
| Масштаб импорта | 1,0 (у MCP `import_file` другого нет) | размеры совпали при 1,0 |
| Габариты | 21,417 × 21,355 × 26,0 uu ±1 % | 21,417 × 21,3554 × 26,0 |
| Pivot | центр основания | min Z 0, центр XY 0 |
| Границы по UM_FBX_v1 | read-back как (x, −y, z), ±0,05 uu | совпали |
| Треугольники LOD0 | 3790 | 3790 (вершин 2430, LOD 1, Nanite выкл.) |
| Коллизия | нет | импорт создал 1 выпуклый элемент, `remove_collisions` → 0 простых элементов |
| BC | sRGB, TC_Default | SRGB true, TC_Default, 1024² |
| N | linear, TC_Normalmap, без flip green (DirectX) | SRGB false, TC_Normalmap, flip false |
| ORM | linear, TC_Masks | SRGB false, TC_Masks |
| Материал | односторонний, Opaque | TwoSided false, BLEND_Opaque, у MI нет override TwoSided |
| MI | TeamColor нейтральный | (1, 1, 1, 1) |
| Слот | 1, назначен MI | `M_Decor_Barrel` → `MI_Decor_Barrel_Candidate` |
| Пробка | ось +X | по габаритам ось X (21,417 > 21,355); знак +X виден на кадре `barrel-side-plusX-close` |

**Отклонение: `M_DioramaMaster`.** Мастер существует (`/Game/S05/M_DioramaMaster`), но в нём только параметры
`BaseColor`, `TeamColor`, `Emissive` (вектор) и `Roughness` (скаляр). Текстурных параметров нет (измерено через
`list_parameters`). MI от него потерял бы BC/N/ORM, поэтому кандидат получил свой `M_Decor_Barrel_Candidate`
(BC × TeamColor, DirectX-нормаль, ORM: R→AO, G→Roughness, B→Metallic) и MI от него. Мастер не менялся.
Отклонение записано в `deviations` отчёта; решение (добавить в мастер текстурные параметры или оставить свой
материал) — за арт-треком.

Идемпотентность: повторный `ue-import` и `run` — `skipped`. `--force` удалил 6 своих ассетов и создал их заново,
листинги до и после совпадают, `Name_1` нет
([report-2](barrel-candidate-ue-import-report-2-forced.json), [listing-1](barrel-candidate-ue-listing-1-after-import.json),
[listing-2](barrel-candidate-ue-listing-2-after-force.json)).

## 3. Тестовый клип

### Совместимость скелета (проверено)

Референсные позы: [skeleton-refpose.json](skeleton-refpose.json), только чтение.

- **T4UmFbxV1 несовместим с черновыми клипами.** UM_FBX_v1 запекает экспортный поворот +90° в референсную позу
  кости `root` (yaw −90). Черновые клипы экспортированы `build_segmented_medusa.py` без этого поворота. Проба
  (LungeAttack на скелет T4UmFbxV1) дала на кадре 0 расхождение `root` 90° и смещение суставов до 17,97 uu
  против референса: фигура разворачивается лицом в +Y вместо +X. Проба удалена после замера.
- **T4LocalPass совместим.** 18 костей и референсная поза те же, что у рига клипов и у `/Game/ART004`.
  Кадр 0 каждого трека совпадает с референсом: 0° и 0 uu.
- Поэтому клипы импортированы на `/Game/PipelineCandidates/Medusa/T4LocalPass/Meshes/SK_Medusa_Candidate_Skeleton`,
  в отдельную папку `/Game/PipelineCandidates/Medusa/DraftClips20260928/T4LocalPass`. Анимации внутри
  `.../T4LocalPass/` сломали бы рекурсивную проверку владения того run: CLI отказал бы из-за чужих ассетов.

### Импорт

- Путь импорта: legacy FBX. `Interchange.FeatureFlags.Import.FBX` переключён true → false только на время импорта
  и возвращён в true; все три значения записаны в [ue-anim-import-1.json](ue-anim-import-1.json).
- FbxImportUI как в VALIDATION.md, шаг 2: FBXIT_ANIMATION, `import_mesh` false, без материалов и текстур.
- **Масштаб импорта (измерено).** По умолчанию `import_uniform_scale` = 1,0. При 1,0 компонентный масштаб позы
  на кадре 0 равен референсу (1,0), масштаб кости 0 равен 1.
  - Проба с 100: масштаб кости 0 = (100, 100, 100), фигура в 100 раз больше
    ([ue-anim-import-probes.json](ue-anim-import-probes.json)). Проба удалена.
  - Вывод: для этих FBX (FBX_SCALE_UNITS и UnitScaleFactor, пропатченный в 1,0) верен контракт 1,0. Значение 100
    из S05 относится к экспорту FBX_SCALE_NONE (ue-pipeline-traps, п. 3).
- Повторный импорт тех же трёх клипов (replace_existing) не изменил листинг, `Name_1` нет. Скелет и меш T4LocalPass
  не стали dirty ([ue-anim-listing-reimport.json](ue-anim-listing-reimport.json)).

### Замеры ([ue-anim-report.json](ue-anim-report.json), сырые данные — [ue-anim-measure-raw.json](ue-anim-measure-raw.json))

Headless-валидатор: [clip-validator-report.json](clip-validator-report.json) и [clip-validator/](clip-validator/).

| Клип | Роль | fps UE | Длина UE / источник, с | Ключей | Кость 0, max \|Δ\| uu | Пик сдвига суставов | Сокеты на 3 кадрах | Итог |
|---|---|---|---|---|---|---|---|---|
| MED-LungeAttack-draft | позитив | 24 | 0,5833 / 0,5833 | 15 | 0 / 0 / 0 | 2,93 uu (5,3 %) | кадры 0/6/14: Weapon–hand_L 2,4372, Head–head 4,0 | **PASS** |
| MED-HitReact-draft | позитив | 24 | 0,375 / 0,375 | 10 | 0 / 0 / 0 | 2,44 uu (4,4 %) | кадры 0/3/9: 2,4372–2,4373 и 4,0 | **PASS** |
| MED-Idle-draft | негативный контроль | 24 | 2,3333 / 2,3333 | 57 | 0 / 0 / 0 | 0,61 uu (1,1 % < 2 %) | кадры 0/28/56: 2,4372 и 4,0 | **FAIL, как ожидалось** |

- Порог 2 % — предложение контракта, он не откалиброван.
- Валидатор дал тот же результат: Lunge и HitReact — pass; Idle с `--pose-change-mode=fail` — fail по
  `visible_pose_change`.
- У всех клипов WARN `armature_object_name` (`SKEL_Medusa` вместо `SKEL_UM_Humanoid`, RIG-CONTRACT §2).
- `root_motion_enabled` = false; кость 0 и `root` неподвижны на всех ключах.

## 4. Кадры (редакторные, диагностика)

Каталог [editor-frames/](editor-frames/), метаданные — [editor-frames.json](editor-frames/editor-frames.json).
Каждый кадр — JPEG 1200×675 q92 из PNG 1920×1080 с sidecar `*.evidence.json`; хеши PNG записаны в sidecar,
сами PNG лежат вне git. Классификатор: 16 кадров, все `editor-mcp-viewport`, 0 отклонённых
([classify-evidence.json](editor-frames/classify-evidence.json)).

- Камера — модель UpdateBoardCamera: горизонтальный FOV 35° (пилотируемый временный CameraActor), pitch −55,
  yaw −90, цель = актёр + 28 uu. K-1 — 1931 uu, K-2 (1,6×) — 1207 uu, crop 16:9 по центру.
- Уровень `L_ART004_MedusaAnimationReview`, его свет, без HUD и boardState.
- Бочка: `barrel-{k1,k2-1p6,close300}-ue-editor-cobble`, плюс `barrel-side-plusX-close-ue-editor` (вид с +X,
  пробка смотрит в камеру).
- Позы клипа на T4LocalPass: `clip-lungeattack-f{00,06,14}-…` и `clip-hitreact-f{00,03,09}-…`, по K-2 и close 300.
  Кадры 0 и последний у каждого клипа побайтно равны (поза покоя), средний отличается.
- Ловушка (измерено): если перепозировать существующего single-node актёра, он показывает **предыдущую** позу, и
  сокеты тоже отстают на один вызов. Скрипт ставит нового актёра на каждую позу. Показания сокетов в sidecar
  совпадают с замером AnimPose.
- Временные актёры удалены, пилот снят, возвращён `/Game/S08/S08Arena`. Уровни не сохранялись и dirty не стали.

## 5. После работы

[snapshot-after.json](snapshot-after.json) против `snapshot-before.json` (снят в 13:06:58 UTC, после второго круга; снимок
первого круга заменён, его копия вне git в `C:/tmp/t21fix/backup-evidence/`):

- `/Game/ART004` и `/Game/ArtPreview` не изменились: ни новых, ни удалённых ассетов, все файлы на диске побайтно
  те же (`protected_unchanged: true`).
- В `/Game/PipelineCandidates` добавлено 13 ассетов: кандидат 6, passthrough 4, клипы 3. Файлы T4 не изменились.
- Редактор: открыт `/Game/S08/S08Arena`, 0 dirty map- и content-пакетов, `Interchange.FeatureFlags.Import.FBX` = true.
- Второй круг отдельно: [snapshot-fix-round-after.json](snapshot-fix-round-after.json) против
  [snapshot-fix-round-before.json](snapshot-fix-round-before.json). Ассеты не добавлены и не удалены; изменились
  только 4 файла `Passthrough/*.uasset`, которые импорт пересоздал. Кандидат, клипы, `/Game/ART004` и
  `/Game/ArtPreview` побайтно те же, редактор чистый.
- `snapshot_baseline.py check` (production baseline T0): 62 файла, 0 расхождений.

## 6. Инструменты (новые)

- `tools/tripo-pipeline/tripo_pipeline.py`: профиль `static-candidate` (стадии `adopt` и UE); исправлена
  passthrough-проверка папки.
- `tools/tripo-pipeline/tests/test_static_candidate.py` (8 тестов) и дополнения в `fake_unreal_mcp.py`.
- `tools/tripo-pipeline/review/ue_live.py`: MCP-клиент и `py` через поле Cmd редактора (SlateInspector);
  `run_task` возвращает исключение UE-скрипта как ошибку, а не ждёт до таймаута.
- `review/ue_py/`:
  - `_run.py`, `editor_state.py`, `skeleton_refpose.py`, `import_clips.py`, `measure_clips.py`, `frames_scene.py`
    — UE-сторона.
- `review/`:
  - `ue_content_snapshot.py` — снимки до и после;
  - `p1_anim_report.py` — сборка ue-anim-report;
  - `p1_editor_frames.py` — кадры.

## 7. Открыто и следующие шаги

1. `M_DioramaMaster` без текстурных параметров: добавить `BaseColorTexture/NormalTexture/ORMTexture` в мастер или
   узаконить собственный материал пропса. Нужно решение арт-трека. Мастер используют 22 MI S05.
2. Клипы для скелета UM_FBX_v1 (T4UmFbxV1 и игровой +X) нужно переэкспортировать с поворотом UM_FBX_v1. Сейчас
   черновые клипы совместимы только со скелетами +Y (T4LocalPass, ART004).
3. Швы UV на мипах ≥ 2 и тёмные пазы бочки (prop-barrel-report §4.3–4.4): редакторных кадров для решения мало,
   нужна контрольная сцена T3.1 и K-кадры packaged.
4. Реестр (`asset-registry.json`): у бочки теперь есть UE-слой «технически импортировано», а у клипов —
   `ue.status`. Реестр не правился. Предложение для T7.2: добавить пути этого каталога, run `ue-candidate` и
   `ue-passthrough`. UE-папки записать с пометкой, что они **только в локальном checkout** (`Content/` в
   `.gitignore`), а не в git.
5. Снимок `pipeline/` (CLI 0.3.0) остаётся как есть. Пересоздать его или вынести errata `tripo-run.json` решает
   оркестратор (prop-barrel-report §3). Passthrough-импорт в UE от него больше не зависит.
