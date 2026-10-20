# Этап 0: шаблоны заявки — запись реестра, стоп rig-contract/3, `.gitignore` ассета

> **С 2026-10-20 (SKILL.md §0):** упоминания Codex и Sol ниже — история; исполнители — Gemini и Z-Code.

Справочник этапа 0 скилла (SKILL.md §6 «Этап 0», §3, §9). Шаблон самой заявки `asset-card.yaml` и дерево evidence
остаются в SKILL.md (§7.2, §9); здесь — длинные шаблоны, которые нужны один раз на ассет. Норма производства —
`docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (далее HANDBOOK).

| Раздел | Когда | Кто проверяет |
|---|---|---|
| §1 запись `docs/art-pipeline/asset-registry.json` | этап 0, шаг 2 (герой, помощник, существо, проп) | `python tools/tripo-pipeline/validate_registry.py` — новых ошибок нет (HANDBOOK §3.2 п.1) |
| §2 `STOP-RIG-CONTRACT-3.md` | этап 0, ветка `non-humanoid` (гейт SKILL.md §5 п.1) | пользователь |
| §3 `.gitignore` ассета | этап 0, шаг 1 | гейт этапа 0: `git check-ignore -v` на путь сырого GLB (§3, F2); после первого прогона этапа 3 — ещё 4K-мастер и 2K-карта |

## 1. Запись `docs/art-pipeline/asset-registry.json` (этап 0)

Все 21 ключ `ASSET_REQUIRED` (`tools/tripo-pipeline/validate_registry.py:70-74`). Проверено 2026-10-09: запись
по этому шаблону, добавленная в копию реестра, не даёт ни одного ERROR (`validate_registry.py --registry <копия>`).
`ownership.*` — из `OWNERS` (`art-chat`, `pipeline`, `shared`, `user-untracked`); `stage` — `planned`; `category` —
`hero` | `sidekick` | `creature` | `prop`; у пропа набора `ASSET-DECOR-KIT-001` — `parent` и `id` вида
`ASSET-DECOR-KIT-001.<NAME>`. `backlog` — только id из `docs/game-design/14-sprint-backlog.csv`, иначе `[]`.
`nextStep`, `blocker`, `doneCriteria` — непустые строки.

Запись этапа 0 стоит «предложено» / `planned` до шага 7b: этапы 1–7a её не обновляют, первый писатель после этапа 0 —
7b (F161). Кто и когда меняет статусы во всех реестрах — таблица `references/new-character-registration.md` §10.

```json
{
  "id": "<ASSET_ID>",
  "name": "<имя> (<герой|помощник|существо|проп>), новая фигура скилла 3d-model-pipeline",
  "category": "hero",
  "contentKey": null,
  "manifest06Row": null,
  "backlog": [],
  "parent": null,
  "instances": 1,
  "status": "предложено",
  "stage": "planned",
  "ownership": {"existingFiles": "pipeline", "nextCandidates": "pipeline", "acceptance": "pipeline"},
  "sourceImages": {"recommended": []},
  "source3d": [],
  "layers": [],
  "manifest06": {"verificationStatusIn06": null, "drift": null, "proposedChange": null},
  "nextStep": "Этап 1 скилла 3d-model-pipeline: концепт-лист в Codex (art/imagegen/concept-<key>-codex/).",
  "blocker": "Нет: заявка этапа 0 заполнена (asset-card.yaml), гейты стопа не сработали.",
  "doneCriteria": "Этапы 0–7 скилла 3d-model-pipeline: ue-import-report passed, автотесты S08 PASS, кадры -Bench обеих досок осмотрены.",
  "acceptanceEvidence": [],
  "evidence": [
    {"path": "art/pipeline-candidates/<ASSET_ID>/asset-card.yaml", "root": "repo", "kind": "file", "expect": "exists", "role": "заявка этапа 0"}
  ],
  "plannedPaths": [
    {"path": "art/imagegen/concept-<key>-codex", "root": "repo", "kind": "file", "expect": "planned", "role": "концепт-лист этапа 1"},
    {"path": "/Game/PipelineCandidates/<Key>/H2LD", "root": "repo", "kind": "ue-asset", "expect": "planned", "role": "импорт этапа 7"}
  ]
}
```

## 2. `STOP-RIG-CONTRACT-3.md` (ветка `non-humanoid`, гейт SKILL.md §5 п.1)

Файл `<ASSET_DIR>/STOP-RIG-CONTRACT-3.md` пишет запускающий агент и отдаёт его пользователю вместе с
`asset-card.yaml`. Заполнить каждый раздел; оценку — по числу затронутых файлов, без обещаний сроков.

```markdown
# <ASSET_ID>: нужна схема рига rig-contract/3 (стоп этапа 0 скилла 3d-model-pipeline)

## Анатомия и якоря
<число ног, голов, хвостов, крыльев; что держит идентичность; ссылка на описание из scraped-data/БД>

## Почему UM_HUMANOID_17_v2 не подходит
<какие части не ложатся на 17 костей и на optional_extensions (docs/art-pipeline/rig/rig-contract.json:169-184)>

## Нужные кости (предложение)
<пример: 4 лапы × 3 кости, 3 головы × 2 кости, хвост × 4; родители; что из базового скелета сохраняется>

## Что менять
| Где | Что |
|---|---|
| `docs/art-pipeline/rig/rig-contract.json` | схема `/3`: новый скелет, правила, `characters`, `revision` |
| `tools/tripo-pipeline/anim/rig_rules.py`, `tools/tripo-pipeline/tests/test_rig_rules.py` | правила костей и тесты |
| `tools/tripo-pipeline/anim/validate_clip.py` | проверки клипа для нового скелета |
| `tools/tripo-pipeline/blender/h2_bake/st_rig.py`, `st_seams.py`, стадия `probes` (`run_h2_bake.py`) | риг, швы, пробы деформации |
| `tools/tripo-pipeline/anim/clip_manifest.py`, `docs/art-pipeline/animation-library/clip-manifest.schema.json` | персонаж и клипы |
| `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp` (`Specs()`), клипы D-11 | подключение и набор клипов |

## Оценка работ
<число файлов и тестов; что нужно проверить регрессом Medusa, Arthur, Merlin, Harpy>

## Вопрос пользователю
Принять схему rig-contract/3 в этом объёме и начать её отдельной задачей? До ответа ассет стоит на этапе 0:
реестр, `anim.csv` и траты не трогаются.
```

## 3. `.gitignore` ассета (этап 0)

Файл `<ASSET_DIR>/.gitignore` создаётся на этапе 0 до первого прогона. Строка `*-tripo/source/*.glb` закрывает и GLB
черновика шага 1b (`<YYYYMMDD>-draft-tripo/source/`). Родительский `art/pipeline-candidates/.gitignore` ловит только `*/*/work/`, `.staging/`,
`run.lock`, `*.tmp-*`, `*.blend1`. Генерический `h2_bake` кладёт 4K-мастера прямо в `textures/` без суффикса
(`T_<Key>_H2_BC.png` — 4096², `T_<Key>_H2_2K_BC.png` — 2048²; образец — `ASSET-MEDUSA-001/.gitignore`):

```
*/work/
*/.staging/
*/run.lock
*.fbm/
*-tripo/source/*.glb
*-h2-bake*/textures/T_*_H2_BC.png
*-h2-bake*/textures/T_*_H2_N.png
*-h2-bake*/textures/T_*_H2_N_OpenGL.png
*-h2-bake*/textures/T_*_H2_ORM.png
*-h2-bake*/textures/T_*_H2_TeamMask.png
*-h2-bake*/textures/master_4k/
*-h2-bake*/textures/*_4K.png
*-h2-lookdev*/textures/T_*_H2LD_BC.png
*-h2-lookdev*/textures/T_*_H2LD_N.png
*-h2-lookdev*/textures/T_*_H2LD_N_OpenGL.png
*-h2-lookdev*/textures/T_*_H2LD_ORM.png
*-h2-lookdev*/textures/T_*_H2LD_TeamMask.png
*-h2-lookdev*/textures/T_*_H2LD_Edge.png
*-h2-lookdev*/textures/*_4K.png
*-ue/review/*/frames/*.png
```

Строки `master_4k/` и `*_4K.png` — страховка от 4K-мастеров с суффиксом (так их пишет форк `h2_bake_arthur`:
`ASSET-KING-ARTHUR-001/20260929-h2-bake/textures/master_4k/`, `20260929-h2-lookdev/textures/T_KingArthur_H2LD_*_4K.png`,
9,5–12,9 МБ; Medusa `.gitignore` закрывает их так же). `*-h2-lookdev*/textures/*_4K.png` поглощает и
`*_TeamAccent_4K.png`.

В git идут 2K-набор (`*_2K_*`, `*_TeamAccent_2K.png`), MatID 4K и LUT, как у Medusa.

Проверки (F2: пакетная заявка 2026-10-13 файл не создала, сырые GLB по 45–79 МБ попали бы в коммит):
- **этап 0, гейт:** `git check-ignore -v <ASSET_DIR>/<YYYYMMDD>-draft-tripo/source/x.glb` печатает правило
  `*-tripo/source/*.glb` из `<ASSET_DIR>/.gitignore` (файла может ещё не быть: `check-ignore` проверяет путь);
- **после первого прогона этапа 3:** `git check-ignore -v <файл>` для 4K-мастера и для 2K-карты (вторая не
  игнорируется).

Сырые GLB и 4K-мастера — локально, sha256 в source-spec и отчётах; кадры — JPEG 1200 px q92 (HANDBOOK §8).
