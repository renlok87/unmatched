# Карта каталогов и владения 3D-ассетов

Срез: 2026-09-28. Машиночитаемый реестр: [asset-registry.json](asset-registry.json). Проверка: `python tools/tripo-pipeline/validate_registry.py` (только чтение; `--paths` выводит все проверенные пути, `--json` даёт машинный отчёт).

Реестр описывает только файлы и то, что по ним проверено. Художественных решений он не принимает. Статусы разделены строго: **предложено → измерено → технически импортировано → художественно принято**. На момент среза ни один ассет не имеет статуса «художественно принято»: GD-058 открыт ([акт](../game-design/evidence/GD-058/acceptance-review-2026-09-28.md)). Числа (55 uu, 21 176 tris, 2K) измерены на кандидате. Бюджетами они не являются; бюджеты 04 §1 и 17 §7.6 остаются в статусе ПРЕДЛОЖЕНИЕ.

Срез обновлён 2026-09-28 после P0 (T3, T4, A1) и ревью верификатора: добавлены слои пайплайна T3/T4, решение A1 по v3, кость 0 `SKEL_Medusa`, UE-путь v3; валидатор проверяет акты приёмки и порядок статусов родитель → потомок.

## Владельцы

| Код | Кто | Правило |
| --- | --- | --- |
| `art-chat` | Арт-трек и его рабочая копия `C:/Users/ren/.codex/worktrees/art-foundation/unmached` | Пайплайн только читает эти файлы и ничего в них не пишет |
| `pipeline` | Пайплайн-трек | Пишет только в собственные каталоги (ниже) |
| `shared` | Нормативы автора и общие входы | Изменения — только через владельца документа или предложенный diff |
| `user-untracked` | Чужие неотслеживаемые файлы главного checkout | Не читать как источники, не трогать |

## Каталоги

| Путь | Владелец | Что лежит | В git |
| --- | --- | --- | --- |
| `docs/art-pipeline/` | pipeline | реестр, карта, инструкции и отчёты пайплайна, `imagegen-inputs/` (T2), `evidence/` прогонов | да (пока untracked, до интеграции) |
| `tools/tripo-pipeline/` | pipeline | CLI пайплайна, валидатор реестра, `check_inputs.py`, тесты `tests/` | да (пока untracked) |
| `art/pipeline-candidates/<ASSET-ID>/<run-id>/` | pipeline | изолированные прогоны: `ASSET-MEDUSA-001/20260928-t3-scaffold`, `20260928-t4-local-pass`, `20260928-t4-headless-compare`; `ASSET-DECOR-KIT-001/20260928-p15-barrel` (P1.5) | частично: `work/` исключён `art/pipeline-candidates/.gitignore` (`*/*/work/`, а также `.staging/`, `run.lock`, `*.tmp-*`, `*.blend1`), `logs/*.log` — корневым правилом `*.log`; у бочки свой `.gitignore`. Остальное (manifest, journal, export, textures, reports) — в git после интеграции |
| `/Game/PipelineCandidates/*` | pipeline | UE-ассеты кандидатов: `Medusa/T4LocalPass` (9 uasset T4) | нет (Content gitignored), воспроизводится `tripo_pipeline.py ue-import` |
| `art/imagegen/mvp-v1/` | shared, только чтение | входы ImageGen; выбор комплектов — `generation-inputs.json` (revision correction-v4) | да |
| `docs/game-design/*.md`, `*.csv` | shared (автор) | нормативы 03/04/06/13/14/17/18 | да |
| `docs/game-design/evidence/ART-00x/`, `GD-058/` | art-chat | акты, отчёты, кадры, Tripo `run.json` | да |
| `blender/ASSET-MEDUSA-001/` (отслеживаемое) | art-chat | Tripo-источники `tripo-source/{d562f057,b6253e58}/`, `medusa.blend`, `export/`, варианты v1/v2 | да |
| `blender/ASSET-MEDUSA-001/` (неотслеживаемое: `build_tripo_medusa.py`, `textures/T_Medusa_*.jpg/png`, `preview/*`, `*.blend1`, `*-inspect.json`, `export/*.fbm/`) | user-untracked | чужая работа в главном checkout | нет |
| `blender/ASSET-BOARD-COBBLE-001/`, `blender/ASSET-MARKERS-001/`, `blender/A01/` | art-chat | Cobble ART-005, кит маркеров, блок-ауты ART-003 | да |
| `blender/S05/` | shared (история) | блок-ауты S05 | да |
| `blender/_shared/`, `blender/_tools/` | shared | шаблон рига, пресет `UM_FBX_v1`, общие скрипты | да |
| `tools/art/*.py`, `*.ps1` (отслеживаемое) | art-chat | импорт/кадры/проверки арт-трека | да |
| `tools/art/{art004_capture,art004_inspect_component,art004_inspect_pose_api,inspect_medusa_animation_api,inspect_medusa_sockets}.py` | user-untracked | чужие неотслеживаемые скрипты | нет |
| `/Game/ART004/Medusa/*` | art-chat | Blender-кандидат Medusa | нет, воспроизводится `tools/art/import_medusa_candidate.py` |
| `/Game/ArtPreview/Medusa/*` | art-chat | визуальный кандидат v2 | **да**, добавлен принудительно |
| `/Game/ArtTests/{ART003,ART005*,ARTMarkers}/*` | art-chat | редакторные пробы | да, добавлены принудительно |
| `/Game/ArtTests/{ART004,ART004Face}/*` | art-chat | сцена клипов, пробы лица | нет |
| `/Game/ArtTests/ART004_V3Review/*` | art-chat | 5 временных ревью-ассетов A1 (v2/v3 и подставка) в главном checkout | нет; сохранить или удалить — решение пользователя |
| `/Game/ArtPreview/Medusa/Meshes/SK_Medusa_HeadTilt_v3Candidate` (арт-worktree) | art-chat | визуальный кандидат v3 | нет: лежит в gitignored `Content/` арт-worktree; при интеграции нужен force-add (как 9 uasset v2) или повторный импорт скриптом |
| `/Game/S01`, `/Game/S05`, `/Game/S08` | shared (история) | S-спринты | да |
| `unreal/Unmatched/Artifacts/` | владелец запуска | логи и кадры запусков | нет; кадры для доказательств копировать в `evidence/` |
| `scraped-data/` | shared | скрап-.glb только как референс формы (D-06) | нет |

Уточнение к вводным советника: `/Game/ArtPreview/Medusa/*` отслеживается в git (9 uasset), а не только воспроизводится скриптом. Скриптом воспроизводится только `/Game/ART004`.

## Слои Medusa (ASSET-MEDUSA-001)

| Слой | Где | Статус |
| --- | --- | --- |
| Tripo-источники | `blender/ASSET-MEDUSA-001/tripo-source/d562f057/` (H3.1, 1 883 819 tris, 55 кред.; Quad-retopo 10 485 faces, 40 кред.), `tripo-source/b6253e58/` (segmented-15 и segmented-retopo 21 177 tris, 40 кред.) | измерено; SHA-256 сверены с `run.json` |
| Blender-кандидат | `blender/ASSET-MEDUSA-001/export/SK_Medusa.fbx` → `/Game/ART004/Medusa` | технически импортировано |
| Визуальный кандидат v2 | `variants/face-section-neck-v2/` → `/Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate` | технически импортировано; художественно не принято; после A1 остаётся изолированным игровым кандидатом |
| Визуальный кандидат v3 | `variants/head-tilt-v3/` → `/Game/ArtPreview/Medusa/Meshes/SK_Medusa_HeadTilt_v3Candidate`, только в арт-worktree, не закоммичен | измерено / технически импортировано; художественно не принято; **решение A1: доработать v3.1** (просвет шеи спереди, зазор корона–колчан 1,07 → 0,31 см, сокет `Head` расходится с головой на 1,04 см) |
| Каркас пайплайна T3 | `art/pipeline-candidates/ASSET-MEDUSA-001/20260928-t3-scaffold` (passthrough, headless) | измерено; в UE не импортировался |
| Кандидат пайплайна T4 | `art/pipeline-candidates/ASSET-MEDUSA-001/20260928-t4-local-pass` → `/Game/PipelineCandidates/Medusa/T4LocalPass` (9 ассетов) | технически импортировано; не художественная приёмка, не бюджет, не замена `SK_Medusa`/ArtPreview |

Измерено на всех импортах Medusa (производственный, v2, кандидат T4): в UE **18 костей** — 17 костей рига (поддерево `root`) и кость 0 `SKEL_Medusa`, узел объекта арматуры. Прежнее «17 костей» считало только поддерево `root`. Для root motion и контракта рига P1.6 это важно: UE читает кость 0. Лицо во всех импортах смотрит в UE в +Y. Это отклонение от проверенного пресета `UM_FBX_v1` / 04 §1 (ART-001 PASS: −Y Blender → +X UE), а не спор с предложением; решение — исправлять экспорт/ассеты Medusa или сознательно принять +Y — за пользователем. Части `tripo_part_8` (рука с луком и наруч) и `tripo_part_13` (правая кисть) вывернуты в `SK_Medusa.fbx`, v2 и v3; исправлены только в кандидате T4.

Черновые клипы (`export/AM_Medusa_*.fbx`) используются только как тестовые файлы. Расширение короны на 28% отклонено, повторять его не нужно.

## Сверка git-состояния

Срез T1 (до изменений):

- `fix/admin-panel` c43826d и `codex/medusa-shading-probe` 3950132 имеют одинаковое дерево `7aed58c3…`.
- В арт-worktree не закоммичены: `variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx` (sha `b9cea0fe…`), `evidence/ART-004/head-tilt-v3-game-import-report.json` и правки трёх `tools/art/art004_*.py` (+76/−11).
- T1 добавила только новые файлы: `docs/art-pipeline/asset-registry.json`, `docs/art-pipeline/DIRECTORY-MAP.md`, `tools/tripo-pipeline/validate_registry.py`.

Обновление после P0 (HEAD обоих checkout не изменился): в арт-worktree добавились неотслеживаемые файлы A1 — акт `head-tilt-v3-self-acceptance-2026-09-28.md`, каталог `head-tilt-v3-probe-2026-09-28/`, скрипты `tools/art/art004_head_tilt_v3_mcp_review/`, `art004_head_tilt_v3_measure.py` и `art004_head_tilt_v3_followup.py`, `variants/head-tilt-v3/README.md`. A1 также дописала по две строки в `evidence/ART-004/README.md` и `evidence/GD-058/acceptance-review-2026-09-28.md`. Каталог пробы A1 сократила с ~54 до ≈14 МБ (14 466 696 байт, 69 файлов). Остались кадры K2 Cobble из UE MCP, сравнения, ID-рендеры Blender и JSON; удалённые файлы с SHA-256 перечислены в `head-tilt-v3-review-measurements.json` → `probe_dir_pruning_2026-09-28`. В главном checkout — каталоги пайплайна (`art/pipeline-candidates/`, `docs/art-pipeline/`, `tools/tripo-pipeline/`) и чужие неотслеживаемые файлы, перечисленные в `baseline.mainCheckout.untrackedAfterT1` реестра.

После интеграции v3 в `fix/admin-panel` пути слоя v3 нужно перевести с `root: art-worktree` на `repo`. Исключение — два gitignored файла из `Artifacts/ART004Face/`: CLI-кадр и patch. Они в интеграцию не попадут; их оставить на `art-worktree` или убрать из слоя. Кадр K2 v3 в слое теперь указывает на сохранённый полный кадр UE MCP `evidence/ART-004/head-tilt-v3-probe-2026-09-28/ue-mcp-live/ue-mcp-cobble-d10-k2-d300-v3.png` и сравнение `compare-ue-k2-front-three-lights.png`. Копию CLI-кадра арт-чата из `ue-cli-headtiltprobe/` A1 удалила при сокращении. Исходный CLI-кадр остаётся только в gitignored `unreal/Unmatched/Artifacts/ART004Face/` арт-worktree. В реестре он указан с пометкой gitignored и с SHA-256 `b06e86f0…`, тем же, что в measurements.json. Кадры CLI (SceneCapture) и MCP-вьюпорта не смешиваются: в области головы они расходятся в среднем на 14/255. Ассет `SK_Medusa_HeadTilt_v3Candidate.uasset` лежит в gitignored `Content/`: при интеграции он в главный checkout не попадёт сам. Нужен force-add, как у 9 uasset v2, или повторный импорт `ART004_GAME_VARIANT=head-tilt-v3` скриптом `tools/art/art004_import_v2_game_candidate.py`.

## Предложения к 06-asset-manifest.csv (не применены)

Нормативный файл принадлежит автору, поэтому ниже только предложения:

1. `ASSET-MEDUSA-001`: `sourceReference` заменить на Tripo d562f057/b6253e58 со ссылками на `run.json`; в `sourceHash` записать sha256 `SK_Medusa.fbx`; `verificationStatus` сменить с `planned` на `imported`. Статус `verified` ставить только после GD-058.
2. `ASSET-BOARD-COBBLE-001`: `blocked` → `in_progress`. Причина «6x4 vs 5x6» снята S04/GD-014 (AD-CNF-36). Статус «принят» не ставить.
3. `ASSET-DECOR-KIT-001`, `ASSET-MARKERS-001`, `ASSET-PROPS-CARDS-001`: решить AD-CNF-19 (один FBX или файл на объект). Кандидаты пайплайна экспортируются файлом на объект.

## Как добавить ассет в реестр

1. Добавить объект в `assets[]` со всеми обязательными полями (см. `ASSET_REQUIRED` в валидаторе). Каждый путь записывается объектом `{path, root, kind, expect, role[, sha256]}`.
2. Для существующих файлов указывать `expect: "exists"`, для целевых путей по 04/06 — `"planned"`. UE-пути записываются как `kind: "ue-asset"` и `/Game/...`.
3. Статус «художественно принято» ставить только вместе с `acceptanceEvidence`. Валидатор принимает только акт в главном checkout (`root: "repo"`, `kind: "file"`, `expect: "exists"`) по пути `docs/game-design/evidence/(ART|GD)-NNN/…/*.md`. В акте должна быть явная строка решения, где сразу после двоеточия стоит «принято», например `**Решение: принято.**`, `**Решение:** принято` или `Решение: художественно принято`. Строки «Решение: не принят…», «Решение: доработать…» и технические решения вида «Решение: FBX v2 принят как технический кандидат» не засчитываются. README, отчёты JSON, акты из арт-worktree и `planned`-пути отклоняются.
4. Дочерняя запись (`parent` — id записи реестра) не может иметь статус выше родителя: не начато < предложено < измерено < технически импортировано < художественно принято. Слой (`layers[]`) не может иметь статус «художественно принято». Решение арт-трека по слою пишется в поле `decision`, статус слоя остаётся техническим.
5. Запустить валидатор. Ожидается `RESULT: PASS`, код выхода 0. Негативные тесты правил: `python -m unittest tools/tripo-pipeline/tests/test_validate_registry.py` (и `test_check_inputs.py` для покрытия выбора ImageGen).
