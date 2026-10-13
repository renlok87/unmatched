# ASSET-ANT-QUEEN-001: нужна схема рига rig-contract/3 (стоп этапа 0 скилла 3d-model-pipeline)

## Анатомия и якоря
AntQueen (таблица `Hero` БД, fighterType из ростера): шесть ног, брюшко, усики, жвалы. Идентичность держит силуэт тела без человеческой
постановки; дизайн-front этапа 1a есть: `art/imagegen/concept-ant-queen-codex/design/ant-queen-front.png`.

## Почему UM_HUMANOID_17_v2 не подходит
17 костей базового скелета рассчитаны на вертикальное тело с двумя руками и двумя ногами. Части «шесть ног, брюшко, усики, жвалы» не ложатся ни на
них, ни на `optional_extensions` (`docs/art-pipeline/rig/rig-contract.json:169-184`: `crown_snakes`, `cloak`,
`harpy_wings` — только для гуманоида).

## Нужные кости (предложение)
шесть ног × 3 кости, брюшко × 2, голова с жвалами × 2; корень `root` и подставка сохраняются; родители — от таза-корпуса.

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
Около 10 файлов кода и 3–4 тестовых набора на один новый тип скелета; регресс Medusa, Arthur, Merlin, Harpy по
`run_h2_bake.py` probes и clip-тестам. Один контракт может покрыть сразу несколько существ этой волны (T. Rex и Raptors —
общий скелет ящера; Ant Queen и Tarantula — общий скелет членистоногого с параметром числа ног; Blob — отдельно).

## Вопрос пользователю
Принять схему rig-contract/3 в этом объёме и начать её отдельной задачей? До ответа ассет стоит на этапе 0:
реестр, `anim.csv` и траты не трогаются.
