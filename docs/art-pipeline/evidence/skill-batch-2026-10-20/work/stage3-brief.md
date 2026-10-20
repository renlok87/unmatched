# Бриф этапа 3 (сборка в Blender) — мини-пачка 3d-model-pipeline 2026-10-20

Ты — исполнитель этапа 3 скилла 3d-model-pipeline для ОДНОЙ фигуры (её `ASSET_ID` дан в задании). Оркестратор пачки —
сессия Claude, которая тебя запустила; он же единственный коммитер.

## Полномочия (дословно)

Пользователь, 2026-10-20: «Можем параллельно начать работу над остальными персонажами. У нас сейчас есть условно
работающий Артур и Медуза. Нужно прогнать скилл пайплайн для пары других персонажей. Заодно проверим работу с генерацией
ассетов Gemini. И ревью ассетов с помощью Z-Code.» Затем, на ночь: «Я пошел спать, меня нету у компа, делай все сам.»
Делегирование визуальных решений (2026-10-06): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
Трат на этом этапе нет (Tripo, SYNTX, Gemini — не трогать).

## Что прочитать (в этом порядке)

1. `.agents/skills/3d-model-pipeline/SKILL.md` — §5 (гейты), §6 «Этап 3», §7.2 (блок `STAGE3`), §8, §9, §11.6.
2. `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` — §2.6, §2.10, §4.1–4.4, особенно «Новый герой: разведка и чек-лист
   профиля» и «Сдача модели (этапы 3 и 5)». HANDBOOK главнее скилла.
3. `docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md` (П3-1…П3-5) и
   `docs/game-design/decisions/2026-10-14-skill-refinement-delegated-decisions.md` (ДС-5, ДС-7).
4. Образцы профилей: `art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json` (канон ключей) и
   последние прошедшие пилот фигуры: `ASSET-BEOWULF-001/build-profiles/beowulf-h2-bake-h2*.json`,
   `ASSET-ACHILLES-001/build-profiles/achilles-h2-bake-h2-r3.json`, их look-dev и teamaccent-профили.
5. Свою заявку `<ASSET_DIR>/asset-card.yaml`, отчёт этапа 2 `<ASSET_DIR>/<run>-h2-tripo/reports/tripo-run.json`
   (роли частей по рамкам — только черновик, F17), превью `<run>-h2-tripo/preview/ortho_*.png` (открой и посмотри),
   source-spec `<ASSET_DIR>/source-specs/tripo-<task8>-h2.json`, лист концепта
   `art/imagegen/concept-<key>-codex/sheet-<key>.png` и `checks-report.json`.

## Что сделать

- Регистрация в `rig-contract.json` уже сделана оркестратором (коммит f2eaceb9: BruceLee, SherlockHolmes, Watson).
  Общие файлы (rig-contract, реестры, `anim.csv`, `clip_manifest.py`, код в `tools/`, `unreal/`) НЕ трогать.
- Разведка частей (роли по цветному рендеру частей, сечения, открытые петли), затем новые профили в
  `<ASSET_DIR>/build-profiles/`: `<key>-h2-bake-h2.json` (`profile_version: 2`, `preview.frame` с
  `checks_report` и `side`, без `previous_candidate`/`baseline`), `<key>-h2-lookdev.json`,
  `<key>-h2-lookdev-teamaccent.json`. `profile_id` уникален среди всех профилей репо.
- Прогоны `run_h2_bake.py` по стадиям в `<ASSET_DIR>/20261020-h2-bake` (повторы после сбоя или правки профиля —
  `-t2`, `-t3`, причина в отчёте), затем `--mode lookdev` → `20261020-h2-lookdev`, `--mode teamaccent`.
  Не больше ОДНОГО твоего процесса Blender одновременно (в пачке параллельно работает второй исполнитель).
- Полный чек-лист HANDBOOK §4.4 «Сдача модели»: `_tone.py` (t_cap 2.0), `capture_acceptance_set.py` в
  `C:/tmp/<key>-stage3-check` и личный осмотр close-head, close-hands, close-torso, close-legs-back, close-weapon,
  pose-01…04 (каждый кадр открыть и посмотреть; чинить найденное средствами профиля до сдачи), `base_seethrough.py`
  (`with_figure` ≤ 0,1 uu²), зазор «наездников» (саквояж, лупа), дымовой прогон клипов на паттерне того же класса
  оружия (`references/animation-vfx-sfx.md` §6.6; каталог дыма — временный, удалить после отчёта).
- Полный повтор детерминизма на этом этапе НЕ делать (ДС-7: один раз, после pass приёмки, до 7a).
- Дописать блок `STAGE3` в свою `asset-card.yaml` (форма §7.2; `executor` — факт: `subagent`, модель, сессия) и
  `FIGURE_BOUNDS_TOP_M` по `rig-report.json#bounds_authored_m`.
- FAIL стадии или инструмента — разбор: сначала средствами профиля (≤ 3 итерации тюнинга). Если нужен фикс общего
  инструмента — НЕ правь его, остановись и верни оркестратору точную ошибку, файл:строку и предлагаемую правку. Новая
  кость, новый MatID-класс, мост-цилиндр — стоп §5 п.5, вернуть оркестратору.

## Ограничения

- Пишешь только в `<ASSET_DIR>/` своей фигуры и в `C:/tmp/<key>-stage3*`. Без `git add/commit/stash/reset/checkout`.
- Без Unreal, без GUI, без Computer Use / Windows-MCP, без браузера; живой Blender (MCP) — только осмотр.
- Свои процессы Blender по завершении проверить и остановить по PID.
- Ответ оркестратору (последнее сообщение, ≤ 40 строк): run-каталоги и профили; стадии и их коды; `probes.passed`;
  tris фигуры и подставки; числа «Сдачи модели» (t_cap, with_figure, дым); найденные и исправленные дефекты кадров;
  открытые пункты; готов ли кандидат к этапу 4 (путь `SK_<Key>_H2LD.fbx` и текстур).
