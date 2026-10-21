# Бриф этапа 7a (UE, редактор-слот на героя): волна A мини-пачки 2026-10-20

Исполнитель — субагент оркестратора (`claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe`). Один агент на героя, у
каждого свой слот.

## Полномочия (дословно)

- Пользователь 2026-10-21: «Хорошо, использую Opus High вместо Z-код для приемщика. Вот, и продолжай без меня, делай
  все сам. Касательно сетов тоже и 3D модели героев.»
- Пользователь через главную сессию: «Просто продолжай работу».
- Главная сессия 2026-10-21: параллельный 7a влит (ДС-3a, `docs/game-design/decisions/2026-10-21-parallel-7a-editor-slots.md`).
  Схема: по слоту на героя, общие файлы — одним шагом регистратора после закрытия всех слотов.
- Траты: в 7a трат нет. Пароли не вводить.

## Что сделать

Сделать этап 7a скилла `.agents/skills/3d-model-pipeline/SKILL.md` §6 «Этап 7 — 7a» по
`references/ue-import-package.md` §1–§4.5. Работать только в своём слоте N. Слот поднимает и закрывает оркестратор.

- **Среда.** Перед каждым шагом с редактором выполнить
  `eval "$(python tools/tripo-pipeline/ue7a/editor_slot.py env <N> --workdir <W> --hero <Key>)"`. Каждую MCP-команду
  оборачивать в `python tools/art/material_library/ue_lock.py --step "<шаг>" -- <команда>`. Команды
  `ue_hero_lookdev.py review|verify|apply-mi` блокировку берут сами.
- **7a.1 Импорт**, по порядку:
  1. профили `ue7a/write_import_profile.py` и `write_review_config.py`;
  2. `um_masters.py verify` (только verify; `um_masters build` и `control_scene.py` при втором открытом редакторе
     запрещены);
  3. `skeletal-adopt`;
  4. клипы: `h2anim_ue.py import` и `measure`;
  5. `ue_hero_lookdev.py verify`;
  6. `clip_manifest.py build` только так:
     `python tools/art/material_library/ue_lock.py --lock C:/tmp/clip-manifest.lock --step "manifest <Key>" -- python tools/tripo-pipeline/anim/clip_manifest.py build`;
  7. look-dev съёмка `ue_hero_lookdev.py review` и подстройка `apply-mi --update-verify`, не больше 3 итераций.
     Переимпорт — только при новом FBX, текстуре или структуре.
- **7a.2 UE-кадры и приёмка 4 клипов** (§4.5): `h2anim_ue.py frames --light-pinned <review report>` по клипу за вызов,
  затем `closeup`, `sheet`; каталог цикла — `ue7a/prep_acceptance.py`.
  - Приёмщики: `ue7a/run_clip_acceptors.py --evidence <цикл> --executor-session-id <id исполнителя клипов из STAGE6>`.
    Workflow `second-acceptor` запускает **оркестратор**: агент пишет путь к `<цикл>/acceptor-args.json` в отчёт и
    останавливается. Агент не может запускать Workflow.
  - Вывод приёмщика, `--finish` и `--second` при коде 3 — следующим сообщением оркестратора.
- **Витрина** (AGENTS.md «Hero showcase high-poly»), в том же слоте после клипов:
  - чистую хайполи `art/pipeline-candidates/<ASSET_ID>/<run>-h2-tripo/source/*-tex8k-pbr-clean.glb` (её делает
    `tools/art/showcase/clean_hipoly.py`) импортировать так же, как `tools/art/showcase/import_hipoly.py` для
    KingArthur: один комбинированный Nanite static mesh со своими glTF-материалами, в
    `/Game/PipelineCandidates/<Key>/HP2/`;
  - `import_hipoly.py` не править: код импорта выполнить через Python своего слота;
  - путь ассета записать в отчёт. `UmShowcase::HiPolyPath` и `DirectoriesToAlwaysCook` — 7b у оркестратора.
- **Выход 7a:**
  - 4 карточки клипов `pass`;
  - блок `STAGE7A` в заявке (§7.2);
  - 0 dirty-пакетов перед закрытием (`ue7a/discard_master.py` при грязном `M_UM_Figure_v2`);
  - новые `.uasset` — список путей в отчёт (оркестратор сделает `git add -f`).

## Не трогать (один шаг регистратора у оркестратора)

`cue-table.json`, `DefaultGame.ini`, `S08FighterNames.json`, `anim.csv`, `HEROES` в de010/de011, bench-фикстуры,
C++ (`S08HeroesV2.cpp`, `S08AudioBank.cpp`, `UmHeroShowcase.cpp`), `asset-registry.json`, `03-asset-registry.csv`. Нужные
строки — в `<W>/REGISTRATION-7.md`.

## Правила

- Только свой слот. Редакторы не стартовать и не закрывать.
- Без git.
- Код инструментов не править. Если упёрлись — остановиться и описать в отчёте.
- Не запускать команд, которым нужен запрос разрешения.
- Писать только в репозиторий (папки своего героя, `unreal/Unmatched/Content/PipelineCandidates/<Key>/`) и в `<W>`.
- Каждый PNG, о котором пишете, открыть глазами.

## Отчёт (последнее сообщение)

- шаги и коды;
- что видно на look-dev и UE-кадрах;
- пути `acceptor-args.json`;
- список новых `.uasset`;
- путь `REGISTRATION-7.md`;
- открытое.
