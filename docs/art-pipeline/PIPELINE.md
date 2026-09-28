# tripo-pipeline: исполнимый каркас пайплайна (P0.3 / T3)

Срез: 2026-09-28. Инструмент: `tools/tripo-pipeline/tripo_pipeline.py`, версия 0.4.0.

- T4 добавил профиль `skeletal-candidate` (раздел [Профиль skeletal-candidate](#профиль-skeletal-candidate-t4)).
- После P0-ревью каждый FBX инструмента пишется по пресету **UM_FBX_v1** (раздел [Оси и FBX-пресет UM_FBX_v1](#оси-и-fbx-пресет-um_fbx_v1)).

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

От профиля зависит набор стадий:

| Профиль | Стадии |
|---|---|
| passthrough | preflight → import → verify → export [→ ue-import] |
| skeletal-candidate | preflight → import → verify → atlas → build [→ ue-import] |

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

Профили Medusa:

- текущий — `art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-segmented-skeletal-um-fbx-v1.json` (`/2`);
- `medusa-segmented-skeletal.json` (`/1`) — запись исторического прогона `20260928-t4-local-pass`. В нём нет `fbx_preset`,
  поэтому инструмент 0.4.0 его не принимает. Профили, по которым уже прошёл прогон, не правятся: новая версия — новый файл.

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

Выход: `textures/*.png`, `reports/atlas-report.json`.

### Стадия build

Работает в Blender (`blender/build_candidate.py`), headless или live.

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

### Стадия ue-import для кандидата

Работает в живом UE через MCP.

Действия:

1. Удаляет только свои прежние ассеты: материал-инстансы → меши → скелет → материал → текстуры.
2. Импортирует 3 текстуры с настройками sRGB, компрессии и flip.
3. Создаёт собственный материал BC×TeamColor + N + ORM и 2 инстанса TeamColor.
4. Импортирует скелетный и статический меши (`import_materials=false`), назначает инстанс слотам.
5. Добавляет сокеты по профилю и сохраняет ассеты.

Проверки:

- в папке ровно запланированные ассеты, нет `*_N`, классы верные;
- текстуры, граф материала, инстансы;
- 17 костей профиля + кость 0 = узел арматуры; иерархия;
- оси:
  - единственная карта осей Blender→UE по границам, фронт = `axes.expected_ue_front` (`front_axis_as_fbx_preset`);
  - границы UE = предсказание build-отчёта по UM_FBX_v1;
  - единственная карта границ эталонного UE-ассета на границы кандидата переводит фронт эталона во фронт кандидата
    (`reference_front_lands_on_candidate_front`);
- верх меша = высота фигуры; слоты, сокеты;
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

## Схема каталогов

```
tools/tripo-pipeline/
  tripo_pipeline.py            CLI (этот документ)
  blender/import_source.py     стадия import (Blender; режимы process/live)
  blender/export_fbx.py        стадия export (Blender; режимы process/live)
  blender/build_candidate.py   стадия build профиля skeletal-candidate (Blender; process/live)
  candidate/atlas.py           стадия atlas профиля skeletal-candidate (Python + Pillow/numpy)
  review/                      редакторные кадры Blender/UE и список UE-папки (не стадии)
  check_inputs.py              T2: автопроверки ImageGen-входов (отдельный инструмент)
  validate_registry.py         T1: проверка реестра ассетов (отдельный инструмент)
  review/                      capture_blender_review.py, capture_ue_review.py, capture_ue_axes.py,
                               ue_listing.py, ue_already_exists_probe.py (редакторные кадры и evidence, не стадии)
  tests/                       python -m unittest (фейки Blender/MCP + интеграция с настоящим Blender)

art/pipeline-candidates/
  .gitignore                   work/, .staging/, run.lock, *.tmp-*
  <ASSET-ID>/source-specs/     описания уже оплаченных Tripo-задач (вход register-source)
  <ASSET-ID>/build-profiles/   профили сборки skeletal-candidate
  <ASSET-ID>/<run-id>/         один изолированный прогон кандидата:
    manifest.json              состояние прогона (схема ниже)
    journal.jsonl              журнал событий (append-only)
    reports/                   preflight.json, import-report.json, verify-report.json,
                               export-report.json | atlas-report.json + build-report.json,
                               ue-import-report.json, ue-mcp-calls.json
    export/*.fbx               детерминированные FBX по UM_FBX_v1 (байт в байт при тех же входах)
    textures/*.png             атлас BC/N/N_OpenGL/ORM (skeletal-candidate)
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
  - **Ветка passthrough на живом UE не проверялась**: её `ue-import` ни разу не запускался против редактора. Её проверки
    основаны на фейке и на карте осей ART-001.

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
| ue-import (только mcp) | папка кандидата; нет чужих ассетов; нет `Name_N`-дублей; папка содержит ровно этот импорт; класс ассета; число слотов = число материалов после round-trip; размеры = ожидаемые ±1 % по каждой оси UE X, Y, Z; треугольники LOD0 = round-trip ±0,1 % (static); кости и сокеты записываются (skeletal); сохранение. **На живом UE для passthrough не проверялось.** | `reports/ue-import-report.json` (`status: technically_imported`), `reports/ue-mcp-calls.json` |

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
python tools/tripo-pipeline/review/capture_ue_review.py --run-dir $R --out <каталог>   # схема камер T4 (лицо +Y)
(cd tools/tripo-pipeline/review && python capture_ue_axes.py --run-dir ../../../$R --out <каталог>)   # ось лица: пиксели + кадры
```

`--force` у стадии переисполняет её, но выходы с теми же байтами не переписываются и не
добавляются в индекс экспортов. `--interrupt-at <stage>` — диагностика: процесс завершается с
кодом 75 после работы стадии, до фиксации результата (как при сбое).

Добавление нового ассета: описать уже полученный результат Tripo в
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

Тестов пайплайна 59 (2026-09-28, версия 0.4.0: все прошли, включая настоящий Blender). В том же каталоге лежат ещё
27 тестов T1/T2 (`test_check_inputs.py`, `test_validate_registry.py`); за них отвечают их владельцы.

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
- `test_candidate_integration.py` — настоящий Blender headless на исходнике Medusa во временном run-каталоге:
  - все контракты build проходят, второй прогон ничего не меняет;
  - экспорт по UM_FBX_v1: лицо +X в кадре экспорта, Triangulate без изменения геометрии, угловые нормали и кости
    совпадают с v2 после обратного поворота;
  - FBX байт в байт равны прогону `20260928-t4-um-fbx-v1`, который лежит в run-каталоге (untracked до интеграции);
  - стадия build в режиме live (как `execute_code`) оставляет сессию нетронутой и даёт те же байты;
- `test_blender_integration.py` — настоящий Blender 5.2 headless:
  - двойной прогон без изменений файлов;
  - passthrough по UM_FBX_v1 на GLB с неквадратным основанием: размеры X/Y в FBX переставлены, после обратного поворота равны авторским;
  режим `live` в сессии с пользовательскими данными ровно так, как его выполняет `execute_code`
  (`tests/blender_live_harness.py`): сессия не изменилась (все коллекции `bpy.data`, активная сцена,
  патчи FBX), FBX байт в байт равен headless; при совпадении имён — канонические имена в отчёте и
  список коллизий. Пропускается, если Blender не установлен.

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

Ветка passthrough в живой UE так и не импортировалась.

**FBX этого прогона сделан до UM_FBX_v1** (инструмент 0.2.0: без поворота и Triangulate, лицо было бы +Y). Прогон
оставлен как есть, как доказательство идемпотентности. Следующий `run` инструментом 0.4.0 переэкспортирует его по
пресету: новая запись индекса, старая помечается `superseded_by`.

Проверка passthrough 0.4.0 на том же GLB Medusa (headless, временный run-каталог):
[passthrough-um-fbx-v1-check.json](evidence/t4-um-fbx-v1-2026-09-28/passthrough-um-fbx-v1-check.json):

- все проверки прошли;
- размеры в кадре экспорта 0,486 × 0,560 × 0,980 м (X и Y переставлены) → ожидаемо 48,6 × 56,0 × 98,0 uu в UE;
- 21 176 треугольников.
