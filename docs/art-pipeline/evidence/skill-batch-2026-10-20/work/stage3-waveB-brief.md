# Бриф этапа 3 (сборка в Blender): волна B (Muhammad Ali, Sinbad, The Porter)

Ты — исполнитель этапа 3 скилла 3d-model-pipeline для ОДНОЙ фигуры (её `ASSET_ID` дан в задании). Оркестратор — сессия
Claude, которая тебя запустила; он же единственный коммитер. Модель — Opus medium (правило AGENTS.md «Model and effort
for new agents»: авторская работа Blender этапов 3 и 5).

## Полномочия (дословно)

- Пользователь 2026-10-21: «Хорошо, использую Opus High вместо Z-код для приемщика. Вот, и продолжай без меня, делай
  все сам. Касательно сетов тоже и 3D модели героев.»
- Через главную сессию: «Просто продолжай работу».
- Делегирование визуальных решений (2026-10-06): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
- Трат на этом этапе нет (Tripo, SYNTX, Gemini не трогать).

## Что прочитать (в этом порядке)

1. `.agents/skills/3d-model-pipeline/SKILL.md` — §5 (гейты), §6 «Этап 3», §7.2 (блок `STAGE3`), §8, §9, §11.6.
2. `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` — §2.6, §2.10, §4.1–4.4, особенно «Новый герой: разведка и чек-лист
   профиля» и «Сдача модели (этапы 3 и 5)». HANDBOOK главнее скилла.
3. `docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md` (П3-1…П3-5) и
   `docs/game-design/decisions/2026-10-14-skill-refinement-delegated-decisions.md` (ДС-5, ДС-7).
4. Находки волны A: `docs/art-pipeline/evidence/skill-batch-2026-10-20/NOTES.md` — F11 (`leg_chains`), F12
   (`color_repaint`, `roughness_remap`), F15 (`clone_repaint`), F17/F17b (parts GLB) и разделы приёмок Bruce,
   Watson, Sherlock.
5. Образцы профилей, прошедших приёмку в волне A: `ASSET-BRUCE-LEE-001/build-profiles/`,
   `ASSET-DR-WATSON-001/build-profiles/`; канон ключей — `ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json`;
   оружие в правой руке — `ASSET-BEOWULF-001/build-profiles/beowulf-h2-bake-h2*.json`.
6. Свою заявку `<ASSET_DIR>/asset-card.yaml`, отчёт этапа 2 `<ASSET_DIR>/20261021-h2-tripo/reports/tripo-run.json`
   (`parts_roles_draft` — только черновик), превью `20261021-h2-tripo/preview/ortho_*.png` (открой и посмотри),
   source-spec `<ASSET_DIR>/source-specs/tripo-<task8>-h2.json`, лист концепта
   `art/imagegen/concept-<key>-codex/sheet-<key>.png`, `checks-report.json` и карточку приёмки листа
   `<ASSET_DIR>/evidence/acceptance-concept/20261021-sheet-r1/card.json` (known_issues — вход этапа 3).

## Что сделать

- Регистрация в `rig-contract.json` уже сделана оркестратором (bad8c547: Sinbad, ThePorter, MuhammadAli). Общие файлы
  (rig-contract, реестры, `anim.csv`, `clip_manifest.py`, код в `tools/`, `unreal/`) НЕ трогать.
- Источники: `20261021-h2-tripo/source/<key>-h2-tripo-<task8>-parts<N>.glb` (выгружен до текстуры без Pack UV, F17) и
  `...-tex8k-pbr.glb`. Если `prepare` всё же падает на `geometry_identical_parts_vs_textured` — стоп, вернуть
  оркестратору числа (не собирать сваренную копию самому).
- Разведка частей (роли по цветному рендеру частей, сечения, открытые петли), затем новые профили в
  `<ASSET_DIR>/build-profiles/`: `<key>-h2-bake-h2.json` (`profile_version: 2`, `preview.frame` с `checks_report` и
  `side`, без `previous_candidate`/`baseline`), `<key>-h2-lookdev.json`, `<key>-h2-lookdev-teamaccent.json`.
  `profile_id` уникален среди всех профилей репо.
- Прогоны `run_h2_bake.py` по стадиям в `<ASSET_DIR>/20261021-h2-bake` (повторы после сбоя или правки профиля — `-t2`,
  `-t3`, причина в отчёте), затем `--mode lookdev` → `20261021-h2-lookdev`, `--mode teamaccent`.
- Полный чек-лист HANDBOOK §4.4 «Сдача модели»: `_tone.py` (t_cap 2.0), `capture_acceptance_set.py` в
  `C:/tmp/<key>-stage3-check` и личный осмотр close-head, close-hands, close-torso, close-legs-back, close-weapon,
  pose-01…04 (каждый кадр открыть и посмотреть; найденное чинить средствами профиля до сдачи), `base_seethrough.py`
  (`with_figure` ≤ 0,1 uu²), зазор «наездников», дымовой прогон клипов на паттерне того же класса оружия
  (`references/animation-vfx-sfx.md` §6.6; каталог дыма временный, удалить после отчёта).
- Полный повтор детерминизма на этом этапе НЕ делать (ДС-7: один раз, после pass приёмки, до 7a).
- Дописать блок `STAGE3` в свою `asset-card.yaml` (форма §7.2; `executor` — факт: `subagent`, модель, сессия) и
  `FIGURE_BOUNDS_TOP_M` по `rig-report.json#bounds_authored_m`.
- FAIL стадии или инструмента — разбор: сначала средствами профиля (≤ 3 итерации тюнинга). Если нужен фикс общего
  инструмента — НЕ правь его, остановись и верни оркестратору точную ошибку, файл:строку и предлагаемую правку. Новая
  кость, новый MatID-класс, мост-цилиндр — стоп §5 п.5, вернуть оркестратору.

## Чему научила волна A (приёмщик снимал баллы именно за это)

- **D — клин ткани под поднятой рукой** (Sherlock r2, D 1,0: клин плаща за поднятой левой рукой на pose-01). Длинные
  полы, плащи, свободные рукава и шаровары: веса ткани с плавным спадом к spine/pelvis, `leg_chains` для полос ткани
  между ног (F11); проверять на pose-01…04, не только в rest.
- **F — зубчатая кромка выреза крышки подставки у подошв** (Sherlock r2). Кромку отверстия под ногами проверять крупно
  на close-legs-back.
- **T — пятна Tripo** на кистях, манжетах, торце рукояти, кромке линзы. Инструменты: `textures.color_repaint` и
  `roughness_remap` (F12), узор ткани — `clone_repaint` (F15).
- **Look-dev тон:** у Watson шёлк вышел 1,62×, кожа 0,67× против концепта — сверять `_tone.py` по зонам.
- **Кольцо команды:** у Bruce кольцо на подставке вышло зубчатым — проверить на close-legs-back.

## Особенности фигур волны B

- **Muhammad Ali** (без оружия, `WEAPON_SOCKET_BONE` hand.R): кожа после PBR сильно блестит — `roughness_remap` по
  коже; кожа гладкая (шум «трещин» с вида сзади листа 1c — артефакт концепта); лицо и объём волос — по front; зазор
  предплечье–корпус сохранить, перчатки — отдельные части (8, 7). Тесный «гард» у лица: проверить, что перчатки не
  проходят сквозь голову на pose-01…04 и в дыме.
- **Sinbad** (сабля на weapon.R): тонкие острие и дужка гарды (сабля в 3 частях: клинок 7, гарда 16, навершие 17 —
  П3-1: одна часть `weapon`, остальное rigid на кость оружия); пустые ножны на левом бедре — rigid, без кости (П3-2);
  хвост тюрбана, бахрома кушака, широкие шаровары — ткань (F11). V-вырез рубахи по front (known issue листа).
- **The Porter** (помощник, 0,45 м, дубинка на weapon.R): корзина с тюками на спине — rigid на spine (П3-2), часть 0
  весит 524 тыс. tris — бюджет ≤ 45k всей фигуры с оружием на экспорте; голова на виде сзади закрыта тюком (так в
  концепте); туника до колен — ткань с `leg_chains`; дубинка в геометрии — пучок прутьев с обмоткой (F-B2-9, принять
  как есть).

## Blender: не больше двух процессов на машине

Параллельно работают другие исполнители. Каждый твой запуск Blender (`run_h2_bake.py`, `capture_acceptance_set.py`,
`base_seethrough.py`, дымовой прогон — всё, что стартует `blender.exe`) оборачивай в общую блокировку волны B:

```bash
python tools/art/material_library/ue_lock.py --lock C:/tmp/blender-waveB.lock --max-hold 0 --step "<key> <стадия>" -- <команда>
```

Блокировка ждёт сама, пока другой исполнитель волны B не закончит свой запуск. Без неё Blender не запускать. Живой
Blender (MCP) не использовать.

## Ограничения

- Пишешь только в `<ASSET_DIR>/` своей фигуры и в `C:/tmp/<key>-stage3*`. Без `git add/commit/stash/reset/checkout`.
- Без Unreal, без GUI, без Computer Use / Windows-MCP, без браузера.
- Не запускать команд, которым нужен запрос разрешения (упала на разрешении — не повторять, описать в отчёте).
- Свои процессы Blender по завершении проверить и остановить по PID.

## Ответ оркестратору (последнее сообщение, ≤ 40 строк)

Run-каталоги и профили; стадии и их коды; `probes.passed`; tris фигуры и подставки; числа «Сдачи модели» (t_cap,
with_figure, дым); найденные и исправленные дефекты кадров; открытые пункты; готов ли кандидат к этапу 4 (путь
`SK_<Key>_H2LD.fbx` и текстур).
