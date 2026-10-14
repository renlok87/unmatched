# Линза B · Инструменты и код — скилл 3d-model-pipeline после пилота

Исследование 2026-10-14 по `research-brief.md`, только чтение. Пилот — коммит `3528ae0b`, находки F1–F163 в `NOTES.md`.
Скрипты проверок и выводы прогонов лежат вне репо: `C:/tmp/skill-research-B/`. После всех прогонов `git status` тот же, что
до них.

## Как проверял
- **pytest** (`-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`): `h2_bake/tests` — 71 passed; `tools/tripo-pipeline/tests`
  — **3 failed** / 234 passed; `tools/art/{acceptance,anim,concept,material_library,visual}/tests` +
  `tools/s08/cue_contract` — **8 failed** / 341 passed; bench-фикстуры и `live_tune` — 61 passed.
- **Валидаторы** (только чтение): `clip_manifest.py check` PASS (35 клипов); `clip_review_sheet.py --check` PASS;
  `env_bench_fixtures.cts --check` ok (2 канонические + 6 вариантов); `cue_contract.py validate-table` PASS (18);
  `validate_registry.py` — 1 ERROR базовой линии (UM-MASTERS).
- **Код.** Прочитаны h2_bake (profile, st_rig, st_uv, st_lookdev, lookdev, run_h2_bake), anim (clip_manifest,
  clip_contact_check, rig_deform_probe, h2anim_run, h2anim_ue), acceptance (validate_card, _tone), de010/de011,
  clip_review_sheet, env_bench_fixtures, ledger, cue_contract, run-ue-tests/build-editor. В C++ — S08HeroesV2 (+Tests),
  S08AudioBank, S08FighterActor, UmWorldLayer.
- **Данные.** Профили и отчёты пилота, git-история коммитов пилота, 100 карточек этапа 0,
  `scraped-data/api/heroes` (ростер, помощники).

## Сводка
21 находка: **блокеров ростера 2** (RB-01, RB-02), **серьёзно 10** (RB-03…RB-12), **мелочей 9** (RB-13…RB-21).
Отдельно — 13 известных находок NOTES, которые в коде всё ещё открыты: таблица в конце.

## Блокеры ростера

**RB-01 · блокер (с 2026-10-29) · CONFIRMED · не исправлено — окно ВР-04 нельзя открыть одними данными.** Стык с RA-04.
- **Доказательство.**
  - `ledger.py:327-328`: при `today > until` предпроверка Tripo падает с ERROR. Для SYNTX то же — `:303-304`.
  - `limits_of` (`ledger.py:150`) пропускает `until: null` как `None`, и сравнение на `:327` падает с `TypeError`.
  - Без ключа срабатывает дефолт 2026-10-28 (`DEFAULT_LIMITS`, `:62-64`).
  - `credits-ledger.json:32-33`: `credits` 1 000 000, но `until` 2026-10-28.
  - Поэтому правка RA-04 «`until: null`» без кода сломает каждую предпроверку этапа 0 п.5 и шагов 1b/2.
- **Исправление.**
  - `ledger.py`: `until is None` — окно открыто (Tripo и SYNTX).
  - `test_visual_ledger.py`: тест на `null` и синтетические лимиты вместо копии живого журнала (см. RB-03).

**RB-02 · блокер для параллельных веток · CONFIRMED · не исправлено — каждый герой правит 23 общих файла: 7 правок в
одних и тех же строках и бинарный `.uasset`.** Стык с RA-15 и C.
- **Где герой правит общие файлы** (коммиты пилота `e897aaf1`…`3528ae0b`; каталоги героя, свои файлы в
  `validation-h2anim/`, `Config/Bench/*-<Key>.json`, `Dissolve/MI_<Key>_*` не в счёт): `clip-manifest.json` переписан
  6 раз; `clip_manifest.py`, `anim.csv` — по 4; `clip-manifest.schema.json`, `clip_review_sheet.py`, `cue-table.json`,
  `S08FighterNames.json`, `DefaultGame.ini` — по 3; ещё 15 файлов по разу: `S08HeroesV2.cpp`, `S08HeroesV2Tests.cpp`,
  `S08AudioBank.cpp`, `S08AudioTests.cpp`, `de010.py`, `de011.py`, `rig-contract.json`, `RIG-CONTRACT.md`,
  `test_rig_rules.py`, `asset-registry.json`, `03-asset-registry.csv`, `DIRECTORY-MAP.md`, `credits-ledger.json`,
  `team-accent.md`, `M_UM_Figure_v2.uasset`.
- **Одна и та же строка у каждого героя** — у двух параллельных веток конфликт гарантирован:
  - `rig-contract.json`: `:3-4` (`revision`/`previous_revision`), `:17` (`applies_to` — массив в одну строку),
    `:237` (`bone_by_character` — тоже в одну строку);
  - `RIG-CONTRACT.md:72` и `:128`;
  - `clip-manifest.schema.json:36` — `character.enum`;
  - проза «28 слотов… 7 персонажей» в `clip_manifest.py:7` и `:285`;
  - `S08HeroesV2Tests.cpp`: `:102-103` (имена), `:111` («seven heroes», 7), `:200` (список помощников), `:515-518`
    (`WantMs`), `:724-727` (`WantSeconds`);
  - `de011.py:40-42` (`CAPTURE_LOOKS`).
- **Подъём `revision` контракта на каждого героя.** `contract_revision()` (`clip_manifest.py:101-102`) пишется в
  `skeleton.version` каждого слота (`:169`, `:189`), и `build` переписывает все 28 слотов, а не 4 новых.
- **Бинарник.**
  - `de010/de011 apply` пересохраняют `M_UM_Figure_v2.uasset` при том же графе: в `3528ae0b` размер Bin 117358 → 117358
    байт, но файл другой.
  - Пересохраняются и `AM_*_LungeAttack`/MIC всех героев из `HEROES` (F157).
  - Текстом такой конфликт не слить, нужен повторный прогон в UE.
- **C++.** `Specs()` — статическая таблица (`S08HeroesV2.cpp:104-117`): на каждого героя пересборка C++ и перезапуск
  редактора. Из дублей `Specs` в тестах (`WantMs` = кадр × 1000 / 24, `WantSeconds` = 0,5 / 0,4 по `bHero`) новой
  проверки не возникает.
- **Исправление.**
  1. Один файл регистрации на героя: `<ASSET_DIR>/registration.json` с полями Character, Key, FighterName, PRE,
     AUDIO_KEY, HIT_TYPE, рост, Idle, кадр контакта, карточки AN, пути CUE.
  2. `clip_manifest`, `clip_review_sheet`, `de010`, `de011` и `env_bench` читают регистрации глобом, а не свои списки.
  3. `Specs()` — из `Config/Heroes/*.json`; `CharacterKey`/`HitType` — оттуда же, точным ключом вместо подстроки.
     Тесты обходят `Specs()` и выводят ожидания из него: без счётчика и списков имён.
  4. Схема: `pattern` вместо `enum`. Для нового персонажа не поднимать `revision` контракта, массивы контракта —
     по строке на элемент.
  5. `de010/de011 --only <Key>` и не сохранять мастер при неизменной `graph_signature`.
  6. Строки cook и `cue-table` генерирует один писатель при интеграции.

## Серьёзно

**RB-03 · серьёзно · CONFIRMED · не исправлено — тесты красные на HEAD и привязаны к живым данным.**
- **Что падает.**
  - `test_skeletal_adopt_lookdev.py:57` (Merlin) и `test_skeletal_adopt_lookdev_c.py:47` (Arthur): проверка
    нормализатора `ue_inputs_current`. Файл `um-material-presets-v1.json` сменился в `1e1d7e44` (2026-10-04, ART-016) —
    после того как их look-dev закрепил его sha.
  - `test_validate_registry.py:211` — UM-MASTERS базовой линии.
  - `test_clip_review_sheet.py` ×5: тесты ждут ровно 4 героя MVP в `HEROES`. После записей пилота: 28 карточек,
    `unique_idle_keys` = {Harpy, Merlin}, `run` по умолчанию даёт 14 запусков вместо 8.
  - `test_visual_ledger.py` ×3: тест копирует живой журнал и ждёт лимит 3000, а его сняли (F5).
- **Последствия.**
  - Регрессию нового героя в красном наборе не видно.
  - Каждая новая запись `HEROES` добавляет красных тестов.
  - Скилл гоняет только `test_rig_rules` и `--check`.
- **Исправление.**
  - Тесты — на фикстурах: monkeypatch `HEROES` (4 MVP), синтетические лимиты.
  - 3 MVP-теста перезакрепить или `xfail` с причиной.
  - В SKILL этапы 3/6/7: перед коммитом эти наборы pytest зелёные.

**RB-04 · серьёзно · CONFIRMED · не исправлено — нет проверки полноты регистрации, пропуск даёт тихий откат.**
- **Тихие откаты.**
  - `S08HeroesV2.cpp:120-124`: `Find` возвращает `nullptr`, в игре legacy-фигура.
  - `S08AudioBank.cpp:54-63` даёт пустой ключ; `HitType` по умолчанию `"BLUNT"` (`:74`), банка `CMB-LUNGE-BLUNT` нет,
    и выпад молчит (`S08FlowGameModeAudio.cpp:526-527`).
  - `cue_contract.py:79-89` — `missing`.
  - Нет строк cook — ассетов нет в паке.
- **Чего не проверяют тесты.** `Specs()` обходят только Scale, Assets, Contact и Dissolve (`S08HeroesV2Tests.cpp:181`,
  `:264`, `:520`, `:728`). Не проверяются аудио-ключ и тип удара, ключи CUE-011/013, строки cook, `S08FighterNames`,
  de010/de011, CHARS/H2ANIM, HEROES и `rig-contract` по каждому `Key`. Звук не ловит ни один гейт.
- **Исправление.** `tools/art/registration_check.py` для каждого героя `Specs`/регистрации проверяет все пункты выше
  (с резолвом спеки и FBX). Запуск — в 7b и в `safe-integrate`.

**RB-05 · серьёзно · CONFIRMED (код), PLAUSIBLE (влияние) · не исправлено — `validate_card` не пересчитывает гейты
G-\* по отчётам.**
- **Как сейчас.**
  - `validate_card.py:227` — статусы `FAIL` берутся из карточки приёмщика.
  - `file_errors` (`:387-425`) проверяет только существование `gates.*.source`.
  - `ld-fbx-report`, `probes-report`, `uv-report` и `textures-report` не читаются (grep пуст).
  - `pair_errors` (`:487-490`) сверяет двух приёмщиков только между собой.
- **Риск.** Машинные гейты отданы LLM: разнобой G-NAMES (F78) и разброс приёмщиков (F141, F151).
- **Исправление.** `--check-files` считает гейты сам, расхождение с карточкой — ошибка:
  - G-TOPO — сумма треугольников против `POLY_BUDGET`;
  - G-RIG — `probes-report` и `rig-report` passed;
  - G-UV и G-TEX — свои отчёты passed;
  - G-NAMES — `UE_NAMES` против отчётов, верх по телу без оружия.

**RB-06 · серьёзно · CONFIRMED · не исправлено — потолок T режет нейтральные классы по оттенку.**
- `_tone.py:128` выносит класс за допуск при `|dHue| > 15` без проверки насыщенности. `family()` (`:63`) при этом
  считает цвет с sat < 0,15 нейтральным, а оттенок медианы почти серого цвета — шум.
- **Воспроизведено.** Angel `20261013-h2-lookdev/reports/measure-report.json`, класс `metal_forged`: sat 0,020/0,043,
  dHue −114,3°, статус `out` (скрипт `tone_audit.py`).
- **Риск.** Основной класс — сталь, чёрная кожа или белый лён — получит `t_cap` 1,0, и модель уйдёт в
  `rework_blender` без дефекта тона. По F72 такой цикл стоил героям пилота полной доработки.
- **Исправление.** Критерий `dHue` — только когда обе медианы хроматические (`sat ≥ CHROMA_SAT`). Тест на сером классе.

**RB-07 · серьёзно · CONFIRMED · не исправлено — `clip_manifest`: ошибка в H2ANIM даёт пустой слот и `MANIFEST_CHECK
PASS`.**
- `clip_manifest.py:107-109` и `:115-116` возвращают `None`, на `:280` слот подменяется `slot()`
  (`proposed`/`none`/`not_run`), и `check()` (`:296-322`) его принимает.
- **Воспроизведено.** `sim_manifest_fallback.py`: спека Achilles `-r9` даёт ACH-LungeAttack `proposed`.
- **Последствие.** Шаг Р6-3 «готово», а дефект всплывает на приёмке клипа как FAIL G-MANIFEST (F43, F103) и съедает
  цикл клипа (лимит 2).
- **Исправление.** В `check()` каждый герой с H2ANIM даёт 4 записи h2anim (спека, FBX, отчёт); иначе ошибка с именем
  героя.

**RB-08 · серьёзно · CONFIRMED (код) · не исправлено — пробы «7/7» не трогают правую руку, колени, стопы, кисти и
оружие.**
- `rig_deform_probe.py:55-63` проверяет head, spine, обе `arm_upper`, **только** `arm_lower.L` (рука лука Medusa) и оба
  бедра. Проба пройдена, если хоть что-то сдвинулось в нужной зоне (`:220-234`).
- **Почему важно.** У 46 карточек оружие в правой руке. Дефекты весов в непроверенных зонах пилот нашёл на этапе 6:
  F122 (локоть Angel > 141°), F48 (стопы), F53 (ствол без ног).
- **Исправление.** Пробы `forearm_r_bend`, `shin_l/r_bend`, `foot_l/r`, `hand_<сторона оружия>_twist` и поворот
  `weapon.*`; нормировать по росту тела без оружия (F59); число проб брать из списка.

**RB-09 · серьёзно · CONFIRMED · не исправлено — два оружия, двуручное или оружие в body: контактные проверки слепы.**
- **Ограничения кода.**
  - `profile.py:69-70` — не больше одной части оружия; `:85-87` — не больше одной кости.
  - `clip_contact_check.py:156`: оружие — один меш `meshes.weapon`; `weapon_body` (`:402-421`) и
    `weapon_below_base_top_outside` (`:484-490`) проверяют только его.
- **Масштаб.** В 52 из 100 карточек этапа 0 `WEAPON_HAND: none`. Среди них парное и двуручное оружие: Daredevil,
  Elektra, Leonardo, Raphael, Michelangelo, Donatello, Dracula, Bloody Mary, Pandora (12 карточек упоминают пару или
  два оружия). Их оружие уходит в body (П3-1/П3-2), и пересечение оружия с телом не проверяется — та же дыра, что
  F127.
- **Исправление.** В спеке h2anim `weapon.extra_parts` (часть или кость). `clip_contact_check` считает вершины body с
  жёстким весом ≥ 0,95 на этих костях отдельным оружием. В профиле — `rig.extra_weapon_parts` в `rig-report`. В
  скилле — правило для двуручного и парного оружия.

**RB-10 · серьёзно · CONFIRMED · не исправлено — номер помощника зашит на Harpy и ≤ 3.** F135 закрывает только табличку
и bench.
- **Код.**
  - Цифра на подставке рисуется только при `Key == "Harpy"` (`S08FighterActor.cpp:1013`).
  - `HarpyNumber` (`S08HeroesV2.cpp:287-296`) берёт последнюю цифру метки и ограничивает её 1..3.
  - Любой `numbered`-помощник получает строку `hud.plate.harpy_name` (`UmWorldLayer.cpp:107-110`).
- **Ростер** (`scraped-data`): 13 героев с 2–8 одинаковыми помощниками — ×2 Leshen, Blackbeard, Oda, Pandora, Yennenga;
  ×3 Dracula, Muldoon, Shakespeare, Sun Wukong; ×4 Elektra, Eredin, Robin Hood; ×8 Squirrel Girl. Номер 4+ не показать;
  метка «Squirrel 10» даёт цифру 0, после ограничения — 1.
- **Исправление.** В записи `sidekick` (`S08FighterNames`) — `count` и ключ таблички; цифра по `NumberedSidekick()`, а
  не по `Key`; метку читать целым числом и ограничивать по `count`.

**RB-11 · серьёзно · CONFIRMED · F47 в коде не исправлен — cp1251 в трубе Bash: падения и кракозябры.**
- **Кодировка.** В Bash-инструменте агента `sys.stdout.encoding` = cp1251, в PowerShell — utf-8 (воспроизведено).
- **Где нет `reconfigure`.** `run_h2_bake`, `h2anim_run`, `h2anim_ue`, `clip_manifest`, `tripo_pipeline`,
  `base_seethrough`, `de010`, `de011`, `ledger`, `ue_hero_lookdev`, `ue_lock`, `cue_contract`, `render_fingerprint`.
- **Падение.** `h2anim_run.py:107-113` печатает словари проверок. В 11 из 14 warn/fail проверок контактов пилота есть
  «×» (например, `ASSET-ACHILLES-001/20261014-h2anim/reports/contact-DeathSettle.json`, `skin_stretch`). Отсюда
  `UnicodeEncodeError` до записи отчёта на `:131`; мой скрипт упал так же.
- **Кракозябры.** Вывод `cue_contract.py validate-table` и `ledger` в Bash агента показывает кириллицу как U+FFFD.
- **Исправление.** Строка `sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")` в каждой точке входа
  (образец — `validate_card.py:507-508`) или `PYTHONUTF8=1` в среде скилла. Плюс тест запуска с
  `PYTHONIOENCODING=cp1251`.

**RB-12 · серьёзно · CONFIRMED (код) · не исправлено — `clip_review_sheet`: разрушительные значения по умолчанию.**
- **Код.**
  - `:704`: `run --heroes` по умолчанию берёт всех из `HEROES` — сейчас 14 packaged-запусков, при 80 героях 160.
  - `:456`: `sheet` без `--cards` берёт все карточки.
  - `:555-572` пишет `sheet-*.jpg` и `frames.json` в `docs/game-design/evidence/VISUAL/<AN>/`; если кадров нет, в
    клетке «нет кадра» (`:424-426`). Так затираются 28 закоммиченных листов чужих героев.
  - `:231`: `run` пропускает запуск, если в общем `C:/tmp/visual/AN-18` есть `exit=0`. После доработки клипа без
    `--force` берутся старые кадры.
- **Исправление.**
  - `--heroes` и `--cards` обязательны.
  - `sheet` отказывается писать карточку без кадров.
  - Пропуск запуска — только при совпадении штампа сборки.

## Мелочи

**RB-13 · мелочь · CONFIRMED · исправление F25 неполное — look-dev FBX пишется до проверок.**
- `st_lookdev.py:199-202` пишет `export/SK_<Key>_H2LD.fbx` до проверок; исключение — только на `:268-269`.
- Это тот самый FBX, который принимает этап 4 и импортирует этап 7.
- **Исправление.** Staging, как в `st_rig.py:434-444` и `:518-522`.

**RB-14 · мелочь · CONFIRMED · не исправлено — у сравнения детерминизма нет вердикта.**
- `run_h2_bake.py:152-181` только раскладывает файлы на identical/different, а `:234-238` и `:332-336` всегда выходят с
  кодом 0. Допусков нет, решает агент (F24, F86).
- **Исправление.** Таблица допусков (PNG N `max_abs_diff ≤ 2`; рендерные отчёты исключены) и код 1 при остальном.

**RB-15 · мелочь · CONFIRMED · не исправлено — тихие дефолты Medusa в профилях.**
- **Где.**
  - `profile.py:252-255`: `uv.density_reference_part` по умолчанию `tripo_part_0`. Профили Achilles на него
    опираются, и не проверяется, что это часть body.
  - `st_uv.py:465`, `:490`: `team_mask.base_band.part` не проверяется как base (F29).
  - `framing.py:51`: без `frame` — канон Medusa, только WARN (`capture_acceptance_set.py:486`).
  - `ue_hero_lookdev.py:831`: `anchor_zone` по умолчанию `linen`.
- **Исправление.** `validate()` требует эти ключи у новых профилей и проверяет роль части.

**RB-16 · мелочь · CONFIRMED (код), PLAUSIBLE · не исправлено — `t_cap` можно обойти списком файлов.**
- `MODEL_FRAMES` (`validate_card.py:77-80`) не содержит `tone.json` и `frames.json`.
- Проверка `t_cap` (`:415-424`) и манифеста кадров (`:342`) идут, только если приёмщик сам перечислил эти файлы в
  `frames.files`. В пилоте их перечислили все 10 карточек.
- **Исправление.** Для модели всегда читать `frames.dir/tone.json` и `frames.json`.

**RB-17 · мелочь · PLAUSIBLE · не исправлено — v2-фигура ищется по отображаемому имени.**
- **Код.**
  - `S08HeroesV2.cpp:123` — точное сравнение без учёта регистра.
  - Вариант bench берёт `FIGHTER_NAME` из карточки, поэтому расхождение с сервером bench не ловит.
- **Ростер.** В именах `scraped-data` есть пунктуация: «Dr. Jill Trent», «T. Rex», «Ms. Marvel», «Jekyll & Hyde»,
  «She Hulk», «Cloak Dagger», «Spiderman». У 97 из 100 карточек `FIGHTER_NAME` ещё нет (F18).
- **Исправление.** Сопоставлять по `heroSlug` (и индексу помощника) или по нормализованному имени. На этапе 0 сверять
  имя со `scraped-data` и БД.

**RB-18 · мелочь · CONFIRMED · не исправлено — прототипы вне git.** Стык с RA-12.
- В `check_concept_views.py` проверки ракурса нет (grep mirror/facing пуст). Она живёт только в
  `C:/tmp/concept-wave/side_mirror_check.py`.
- `grip_check.py` — 3 копии двух разных версий (86 и 209 строк) в `C:/tmp/{angel-anim-r2,achilles-anim-s6,achilles-r3}`.
- **Исправление.** Перенести в `tools/` с тестами.

**RB-19 · мелочь · CONFIRMED · не исправлено — у потолка T нет CLI для выхода этапа 3.**
- SKILL требует `t_cap` 2,0 по `_tone.tone_table`, но в `_tone.py` нет `__main__`, и агенты пишут однострочник (F85).
- **Исправление.** CLI `python tools/art/acceptance/_tone.py <measure-report> [<ld-maps-report>]`, который печатает
  `t_cap`, классы `out` и `floor`.

**RB-20 · мелочь · CONFIRMED · известная эскалация — карта гуманоидных допущений для rig-contract/3.**
- На этапе 0 стоят 5 не-гуманоидов и 3 крылатых с руками.
- Кости гуманоида зашиты в `rig_deform_probe.py:40-63`, `clip_contact_check.py:69` (`LEGS`),
  `_blender_capture.py:39-46`, `clip_author.py` (5 имён), `validate_clip.py` (2), `st_seams.py` (3),
  `measure_clips.py` (1), `profile.py:22-24`; длины клипов — `S08HeroesV2.cpp:164-172`.
- **Исправление.** Список — в шаблон `STOP-RIG-CONTRACT-3.md` как объём работ.

**RB-21 · мелочь · CONFIRMED (код), PLAUSIBLE · не исправлено — `ue_lock` без heartbeat.**
- Блокировка считается устаревшей через 25 минут по `mtime` (`ue_lock.py:29-30`, `:45-72`) и не обновляется, пока
  держится. Шаг MCP длиннее 25 минут перехватит другой агент.
- В пилоте de010/de011 шли около 18 с.
- **Исправление.** Обновлять `mtime` каждые `POLL_S`.

## Известные находки NOTES, в коде всё ещё открыты (проверено, не дублирую)

| F | Где в коде | Что осталось |
|---|---|---|
| F8 | `check_concept_views.py` | нет проверки ракурса (RB-18) |
| F47 | `h2anim_run.py` | нет `reconfigure` (RB-11) |
| F59 | `rig_deform_probe.py:190-191` | нормировка по рамке с оружием (RB-08) |
| F66 | `lookdev.py:191-225` | `clean_labels` в один проход, читает `lab` |
| F96 | `h2anim_ue.py:449` | у `--base` нет дефолта |
| F103 | `clip_manifest.py:45-55` | одна спека на героя |
| F113 | `clip_contact_check.py:397-401` | `foot_slide` PASS при 0 вершин стопы |
| F117 | `clip_manifest.py:279-293` | `build` пересобирает всё |
| F127 | `clip_contact_check.py:156` | вторая часть оружия не проверяется (RB-09) |
| F130 | `clip_manifest.py:125` | дата 2026-09-29 |
| F136 | `h2anim_ue.py:231` | камера 200/31 uu |
| F145 | `h2anim_ue.py:103-118` | меш превью не обновляется |
| F157 | `de010.py:39-46`, `de011.py:58-65` | нет `--only` (RB-02) |

Исправленными подтверждены F12, F32, F45, F51/F52, F60, F80, F81, F124/F125 и F149. F25 закрыт только в `st_rig`
(RB-13).

## Не проверено
- Глубже grep не читал `tripo_pipeline.py` (3976 строк), `um_masters.py`, `skeletal_adopt*`.
- `st_close`, `st_retopo` и `st_seams` смотрел сверх известных F только частично.
- Цепочки звука и FX этапа 6 (`tools/audio`, `tools/art/fx`) не смотрел.
- Не смотрел `package-client.ps1`/`sync-staged-build.ps1` и `render_bench.py`.
- Пороги `check_concept_views` и съёмки приёмки на широких и высоких силуэтах (крылья, рога) не проверены.
- `tools/art/tests` прогнаны только частично.
