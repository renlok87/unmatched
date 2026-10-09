# Регистрация нового персонажа в коде и конфигах (этапы 3, 6, 7)

Единый список мест, где сейчас перечислены четыре существующих персонажа (Medusa, King Arthur, Merlin, Harpy), и того,
что дописать для нового. Без этих правок новый персонаж падает с `KeyError` на этапе 3 (пробы рига), на этапе 6 (клипы),
а в игре молча откатывается на серую коробку. Источники: grep по `Medusa`, `Harpy`, `Merlin` и `Arthur` в `tools/`,
`unreal/Unmatched/Source/`, `unreal/Unmatched/Config/`, `docs/art-pipeline/rig/` и `docs/unreal/contracts/`. Сверка
выполнена 2026-10-09 после коммита `f634d660` и повторена после раунда 2 переписывания скилла (доработки Д-1…Д-3 в
рабочей копии): номера строк даны на это состояние. Перед правкой место находится тем же grep, номер строки только
помогает.

Норма производства — `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (далее HANDBOOK). HANDBOOK §4.7 («обязательно для героя и
помощника») называет три правки (Specs, DefaultGame.ini, `git add -f`), и этого недостаточно: автотесты `Unmatched.S08.HeroesV2.*` проверяют больше.
Ниже приведён полный список. Числа и ограничения HANDBOOK он не меняет.

Этапы — по карте этапов 0–7 из `SKILL.md`: 3 = сборка в Blender (до первого прогона `run_h2_bake.py`), 6 = анимация,
VFX и SFX, 7 = упаковка, импорт в UE и подключение S08. Разделы 3–5 обязательны для каждого героя и помощника. Раздел 6
нужен только при условии из его первой колонки (способность, FX, свой звук, тюнинг).

## 0. Когда это рутина, а когда стоп

- **Рутина, без вопросов пользователю:** прямоходящий гуманоид или крылатый бипед, у которого кости только из
  `UM_HUMANOID_17_v2` (16 базовых костей и не больше одной кости оружия `weapon.L`/`weapon.R`, HANDBOOK §2.6). Для такого
  персонажа все строки ниже — пополнение данных: доработки инструментов раздела 2 уже сделаны (раунд 2, 2026-10-09).
- **Стоп с вопросом пользователю (гейт стопа `SKILL.md`):** нужна новая кость или расширение из
  `rig-contract.json` → `optional_extensions` (`crown_snakes`, `cloak`, `harpy_wings`: `crown_snake.NN`,
  `cloth_front/back`, `wing_tip.L/R`; все со статусом «предложено, не реализовано», `rig-contract.json:169-184`). Тот же
  стоп — при новом классе MatID (HANDBOOK §4.4, §0.3 п.7) и при негуманоидной анатомии.
- Окружение и задники досок к этому файлу не относятся (трек ENV-MAPS, AGENTS.md «Board scenes and heroes»).
- **Имя бойца в автотестах — до правки `Specs()`.** Автотесты берут имена вне ростера как «незнакомый герой»:
  `S08AudioTests.cpp:49` — `Robin Hood`, `S08HeroesV2Tests.cpp:107` и `:489` — `Sinbad`. Если `FIGHTER_NAME` нового
  персонажа совпадает с таким именем, его строка `Specs()` ломает эти тесты, и этап 7 не проходит (`EXIT CODE` ≠ 0).
  Поэтому до Р7-3 — `grep -n '"<FighterName>"' unreal/Unmatched/Source/Unmatched/S08/*Tests.cpp` (без учёта
  регистра: `grep -in`). Каждое совпадение вне строк, которые добавляет сам персонаж (Р7-4, Р7-5), — замена имени в
  тесте на имя не из ростера и не из `scraped-data/api/heroes` (решение скилла: `Unknown Fighter`). Это рутина, не стоп.
- **Помощник без нового героя** (например, `ASSET-SIR-GAWAIN-001`; `GAME_ROLE` sidekick, владелец — уже подключённый
  герой). Правило скилла: в заявке `OWNER_HERO_SLUG` — слаг героя-владельца (из заявки пользователя; не задан —
  решение по делегированию, ближайший по сюжету герой ростера, `decided_by: delegated (ВР-реестр 2026-10-06)`);
  `HERO_SLUG` = `OWNER_HERO_SLUG`. Персонажа нет в `scraped-data/api/heroes` и эталонной БД — `DESCRIPTION`, `ANCHORS`
  и `FIGHTER_NAME` пишутся по заявке пользователя с тем же `decided_by` (это не гейт стопа). Вариант bench-фикстуры —
  Д-2 «Только помощник», `S08FighterNames.json` — Р7-8 «Только помощник».

## 1. Обозначения: откуда берутся значения

Все значения берутся из заявки `ASSET_DIR/asset-card.yaml` (этап 0, `SKILL.md`). В примерах ниже взят правша-герой с
мечом (King Arthur), во второй колонке примеров — лучник с луком в левой руке (как Medusa).

| Обозначение | Из поля заявки | Пример (правша) | Пример (лук в левой) | Где используется |
|---|---|---|---|---|
| `<Character>` | `CHARACTER` (правило ниже) | `Arthur` | `Medusa` | ключ `rig-contract.json` characters, `--character` валидаторов, `clip_manifest.py` CHARS/H2ANIM, `rig.character` профиля h2-bake, `character` спеки h2anim, `clip_review_sheet.py` HEROES |
| `<Key>` | `KEY` | `KingArthur` | `Medusa` | папка `/Game/PipelineCandidates/<Key>/`, `FHeroSpec::Key`, `ue_hero` спеки h2anim, de010/de011, cue-table, ключ `clip_review_sheet.py` HEROES |
| `<FighterName>` | `FIGHTER_NAME` | `King Arthur` | `Medusa` | `FHeroSpec::FighterName` (сравнение без учёта регистра), поле `name` бойца в bench-фикстуре |
| `<Stage>` | `UE_NAMES` | `H2LD` | `H2LD` | `FHeroSpec::Stage`, папка `/Game/PipelineCandidates/<Key>/<Stage>/` (`H3LD` только для второго поколения) |
| `<ASSET_ID>` | `ASSET_ID` | `ASSET-KING-ARTHUR-001` | `ASSET-MEDUSA-001` | `rig-contract.json`, `clip_manifest.py` CHARS, de010 |
| `bHero` | `GAME_ROLE` (hero → true, sidekick → false) | `true` | `true` | Specs(); длина dissolve 0,5 / 0,4 с (`S08HeroesV2.h:202-204`); тест «каждый герой выше каждого помощника» |
| `<weapon_bone>` | `WEAPON_BONE` (из `WEAPON_HAND`) | `weapon.R` | `weapon.L` | `rig-contract.json` characters; `null` у персонажа без оружия |
| `<ue_weapon_bone>` | из `WEAPON_BONE`: точка → подчёркивание | `weapon_R` | `weapon_L` | `rig-contract.json` characters и `sockets_v2`; у персонажа без оружия поля нет |
| `<IdleSeconds>` | `IDLE_SECONDS` | `2.5` | `56/24` | Specs(), `clip_review_sheet.py` HEROES; длина клипа Idle = N/24; совпадение с чужим Idle допустимо (Д-3) |
| `<ContactFrame>` | `LUNGE_CONTACT_FRAME` | `7` | `8` | Specs(), de010, тест Contact |
| `<BudgetUU>`, `<MinUU>`, `<MaxUU>` | `FIGURE_HEIGHT_M` × 100, `FIGURE_HEIGHT_RANGE_M` × 100 | `55`, `52`, `56` | `55`, `50`, `55` | Specs(); `figure_height_m` профиля ue-import |
| `<PRE>` | `CLIP_PREFIX` (решение скилла: 3–4 заглавные буквы от `<Character>`) | `ARTH` | `MED` | префикс id клипа в манифесте (`^[A-Z]{3,4}-…`, `clip-manifest.schema.json:35`), `clip_review_sheet.py` HEROES; не должен совпадать с `MED`, `HAR`, `ARTH`, `MER` |
| `<AUDIO_KEY>` | `AUDIO_KEY` (решение скилла: `<Character>` заглавными) | `ARTHUR` | `MEDUSA` | банк звука `DTH-<AUDIO_KEY>`, `VO-<AUDIO_KEY>-…`; совпадает с правилом у всех четырёх существующих |
| `<HIT_TYPE>` | `HIT_TYPE` (слот `hit_type`, этап 6, `references/animation-vfx-sfx.md` §9) | `BLADE` | `ARROW` | `S08AudioBank::HitType` |
| `<owner_slug>` | `OWNER_HERO_SLUG` (только помощник без нового героя; иначе `null`) | — | — | `--hero-slug` варианта bench-фикстуры (Д-2 «Только помощник»), ключ владельца в `S08FighterNames.json` (Р7-8) |
| `<owner_name>` | `FighterName` героя-владельца из `Specs()` (`S08HeroesV2.cpp:105-108`; у `king-arthur` — `King Arthur`) | — | — | `--hero-name` варианта bench-фикстуры (Д-2 «Только помощник») |
| `<slug>` | `HERO_SLUG` | `king-arthur` | `medusa` | ключ `S08FighterNames.json` (Р7-8), `heroSlug` бойца в варианте bench-фикстуры (Д-2) |
| `<имя по-русски>` | `FIGHTER_NAME_RU` | `Король Артур` | `Медуза` | `S08FighterNames.json` (Р7-8) |
| `<socket_bone>` | `WEAPON_SOCKET_BONE` (только при `WEAPON_BONE` = `null`) | — | — | сокет `Weapon` в профиле ue-import (Harpy — `foot.R`), запись `sockets_v2` (Р3-1) |

**Правило `CHARACTER`** (решение оркестратора 2026-10-09; живой тест этапа 0 колебался между `Robin` и `RobinHood`).
Имя персонажа без титула, PascalCase, только ASCII-буквы, уникальное среди ключей
`docs/art-pipeline/rig/rig-contract.json` → `skeletons.UM_HUMANOID_17_v2.characters`:
- титулы и звания отбрасываются: King, Queen, Prince, Princess, Sir, Lady, Lord, Doctor, Captain, Saint и подобные;
- остальное имя остаётся целиком, прозвище-фамилия — не титул: `King Arthur` → `Arthur` (`KEY` `KingArthur`),
  `Sir Gawain` → `Gawain`, `Robin Hood` → `RobinHood`, `Little John` → `LittleJohn`, `Medusa` → `Medusa`;
- имя уже занято — к нему добавляется отличительное слово из `FIGHTER_NAME` (решение по делегированию, строка в
  `NOTES`), а не цифра.

Занятые имена (вывод — список; нового имени в нём быть не должно):

```bash
python -c "import json;print(sorted(json.load(open('docs/art-pipeline/rig/rig-contract.json',encoding='utf-8'))['skeletons']['UM_HUMANOID_17_v2']['characters']))"
#   2026-10-09: ['Arthur', 'Harpy', 'Medusa', 'Merlin']
```

От `CHARACTER` выводятся `AUDIO_KEY` (заглавными: `ROBINHOOD`) и `CLIP_PREFIX` (3–4 заглавные, не `MED`, `HAR`,
`ARTH`, `MER`: `ROB`).

Значения существующих персонажей выписаны из `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp:105-108`:

| Персонаж | bHero | Бюджет, uu (диапазон) | Верх фигуры / bounds, uu | Idle, с | Кадр контакта |
|---|---|---|---|---|---|
| King Arthur | да | 55 (52–56) | 55,0 / 60,06 | 2,5 | 7 (рубящий удар) |
| Merlin | нет | 45 (40–48) | 44,986 / 49,42 | 3,0 | 8 (тычок посохом) |
| Medusa | да | 55 (50–55) | 55,009 / 55,01 | 56/24 | 8 (выпуск стрелы) |
| Harpy | нет | 42 (35–42) | 42,0 / 42,0 | 2,0 | 7 (удар когтями, окно к.7–9) |

## 2. Доработки инструментов Д-1…Д-3: сделаны, для нового персонажа — только данные

На 2026-10-09 три инструмента были зашиты на Medusa или на четырёх героев. Раунд 2 переписывания скилла (2026-10-09)
снял эти ограничения в коде: Д-1 — `tools/tripo-pipeline/blender/h2_bake/` (версия `h2-bake/0.6.0`; 0.6.1 — без прежнего кандидата и
H2.1-базы в `preview`, рамка концепта `frame`, TeamAccent без `hem` или `ribbon`: SKILL.md этап 3 п.2–3), Д-2 —
`tools/art/render/env_bench_fixtures.cts` и `tools/art/render/live_tune.py`, Д-3 — `tools/art/anim/clip_review_sheet.py`.
Разовых доработок больше нет: новый персонаж требует только строк данных ниже (профиль, файлы вариантов фикстуры,
строка `HEROES`, карточки `anim.csv`). Проверка, что доработки на месте в текущем checkout:

```bash
python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q    # Д-1: 22 passed (test_weapon_side.py 12,
                                                                   #   test_new_character_stages.py 10; Blender-тест
                                                                   #   без Blender 5.2 — skipped)
python tools/art/render/live_tune.py bench --help | grep -- --fixture         # Д-2: флаг есть
python tools/art/anim/clip_review_sheet.py run --help | grep -- --fixture     # Д-3: флаг есть
python tools/art/anim/clip_review_sheet.py --check                # Д-3: "check": "PASS", "fails": []
```

Если любой из флагов не находится — checkout старше раунда 2: перейти на свежий `fix/admin-panel`, а не дописывать
инструмент заново.

### Д-1. h2_bake: сторона оружия и персонаж без оружия (этап 3)

Сторона и наличие оружия берутся из профиля, а не из образца Medusa. Новый обязательный ключ профиля не нужен:
`profile.weapon_bone()` (`tools/tripo-pipeline/blender/h2_bake/profile.py`) ищет кость оружия по порядку:
1. необязательный `rig.weapon_bone` профиля (`"weapon.L"` | `"weapon.R"` | `null`);
2. контракт: `docs/art-pipeline/rig/rig-contract.json` → `skeletons.<rig.skeleton>.characters.<rig.character>.weapon_bone`
   (поэтому Р3-1 идёт до первого прогона);
3. единственная кость `weapon.L`/`weapon.R` в `rig.bones` — только для персонажа, которого нет в контракте.

Явный `rig.weapon_bone`, противоречащий контракту, — `ValueError` (стоп HANDBOOK §0.3). `profile.validate()` отвергает
больше одной части-оружия, отсутствие `meshes.body`/`meshes.base`/`meshes.weapon` при соответствующих частях, две кости
`weapon.*` и `rig.weapon_bone`, которого нет в `rig.bones`.

Что писать в профиле `<content-key>-h2-bake-h2.json` нового персонажа (образец — `medusa-h2-bake-h2.json`):

| `WEAPON_HAND` | Части и меши | Кости | Сокет `Weapon` (`sockets`) | Проверка стороны в `rig-report.json` |
|---|---|---|---|---|
| `left` (как Medusa) | одна часть `mesh: "weapon"`, `meshes.weapon` = `SK_<Key>_H2_<Оружие>` | `weapon.L` под `hand.L` | `"bone": "weapon.L"` | `weapon_bone_by_side_v2`, `export_frame_bow_on_rotated_left` |
| `right` | то же | `weapon.R` под `hand.R` | `"bone": "weapon.R"` | `weapon_bone_by_side_v2`, `export_frame_bow_on_rotated_right` (знак проверки обратный: оружие на −Y кадра экспорта, UE +Y) |
| `none` | части `mesh: "weapon"` нет, ключа `meshes.weapon` нет | ни одной кости `weapon.*` | своя кость персонажа (`hand.R`/`hand.L`; у Harpy в профиле ue-import — `foot.R`, поле заявки `WEAPON_SOCKET_BONE`) | `weapon_bone_by_side_v2` с пустым `measured` (PASS), проверка кадра экспорта пропускается, `bow_centroid` = `null` |

Блок `axes` профиля (`blender_bow_side`, `expected_ue_bow_side`) код не читает (grep по `h2_bake/*.py` пуст): он
описательный, у правши пишется `"-X"` / `"+Y"` (решение скилла, для читаемости профиля).

Метки проб в `reports/deform/` и `probes-report.json` теперь `<content_key>-h2-blend` / `<content_key>-h2-fbx`, где
`content_key` выводится из `asset_id` (`ASSET-KING-ARTHUR-001` → `king-arthur`; `profile.content_key()`,
`run_h2_bake.py:102-103`). У Medusa метки прежние (`medusa-h2-*`).

Регресс (выполнен в раунде 2 на рабочей копии, повторять только после новой правки `h2_bake`): Medusa в режимах `h2`
и `lookdev` против `art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake` и `20260929-h2-lookdev` — FBX и отчёты
стадий `identical` (rig-report — после нормализации путей), N/N_OpenGL в пределах GPU-шума `max_abs_diff` ≤ 2;
синтетические правша (Arthur, `weapon.R`) и персонаж без оружия (Harpy) проходят `rig` и `probes` 7/7. Команды
регресса для новой правки:

```bash
R=C:/tmp/ASSET-MEDUSA-001-regress-h2bake
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py \
    --profile art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json \
    --run-dir $R/h2 --compare-with art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --mode lookdev \
    --profile art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-lookdev.json \
    --run-dir $R/lookdev --compare-with art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev
```

Ловушки регресса: стадия `preview` читает `work/h2-baseline/` (ручной вход при заданном `preview.baseline`; ни одна
стадия его не создаёт — скопировать из принятого прогона); `reports/validate-skeletal-mesh-v2.json` отличается полем
`contract_revision`, если Р3-1 уже подняла `revision`, — сравнивать без него:

```bash
python -c "import json,sys;a,b=(json.load(open(p,encoding='utf-8')) for p in sys.argv[1:3]);[d.pop('contract_revision',None) for d in (a,b)];print('same' if a==b else 'DIFFERENT');sys.exit(a!=b)" \
    $R/h2/reports/validate-skeletal-mesh-v2.json \
    art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake/reports/validate-skeletal-mesh-v2.json
```

`--mode teamaccent` Medusa на HEAD падает по своей причине: `medusa-h2-lookdev-teamaccent.json` закрепляет sha256
прежних look-dev текстур (их поменяли коммиты `ee96aaf6`, `1d0e6f20`). Это не регресс `h2_bake`; для нового персонажа
профиль TeamAccent пишется со своими sha256 после его look-dev.

Образец для нового персонажа — общий `h2_bake/` с профилем Medusa. Каталоги
`tools/tripo-pipeline/blender/h2_bake_arthur/`, `h2_bake_merlin/`, `h2_bake_harpy/` — драйверы под одного героя,
образцом не служат.

### Д-2. Bench-сцена с новым персонажем (этап 7)

Генератор вариантов: каноническая фикстура доски, собранная тем же серверным путём, в которой новый герой занимает
место `f-1-hero` (King Arthur), новый помощник — `f-1-sk0` (Merlin). Меняются только `name` и `heroSlug` этих двух
бойцов; `id`, позиции, статы, колоды и `boardState` прежние. Корневое поле `benchVariant` записывает параметры
(клиент его не читает). Без `--sidekick-name` Merlin остаётся статистом под своим именем, его `heroSlug` всё равно
становится новым (слаг владельца).

```bash
node backend/node_modules/ts-node/dist/bin.js --transpile-only -P backend/tsconfig.json \
    tools/art/render/env_bench_fixtures.cts --variant <Key> --hero-name "<FighterName>" --hero-slug <slug> \
    [--sidekick-name "<FighterName помощника>"]
#   → unreal/Unmatched/Config/Bench/S08BenchMarmoreal-<Key>.json и S08BenchSarpedon-<Key>.json
#   (--maps marmoreal,sarpedon по умолчанию; --out-dir <dir> — другой каталог); ошибка использования — код 2, файлов нет
node backend/node_modules/ts-node/dist/bin.js --transpile-only -P backend/tsconfig.json \
    tools/art/render/env_bench_fixtures.cts --check
#   канонические — ok; каждый S08Bench<Map>-<Key>.json в Config/Bench пересобирается из benchVariant — ok | DRIFT
```

- `--hero-name` и `--sidekick-name` обязаны точно совпасть с `FighterName` новых строк `Specs()` (Р7-3): клиент
  выбирает v2-фигуру по имени бойца (`S08HeroesV2::Find`), `heroSlug` задаёт только портрет и рубашку.
- Вариант сохраняет статы King Arthur (здоровье 18, движение 2, ближний бой) — для кадров этого достаточно.
- Файлы вариантов коммитятся вместе с персонажем: без них `--check` их не видит, а кадры не воспроизводятся.
- **Только помощник** (новый помощник уже подключённого героя, `OWNER_HERO_SLUG` задан). Генератор требует
  `--hero-name`/`--hero-slug` всегда: передаётся текущий владелец, новый боец — только `--sidekick-name`:
  ```bash
  node backend/node_modules/ts-node/dist/bin.js --transpile-only -P backend/tsconfig.json       tools/art/render/env_bench_fixtures.cts --variant <Key> --hero-name "<owner_name>" --hero-slug <owner_slug>       --sidekick-name "<FighterName>"
  ```
  На месте `f-1-hero` стоит владелец со своей v2-фигурой, на месте `f-1-sk0` — новый помощник. Если у владельца нет
  строки `Specs()` (нет v2-фигуры), берётся `--hero-name "King Arthur" --hero-slug king-arthur`: место `f-1-hero` и
  так его, кадр остаётся на готовых фигурах (AGENTS.md «Board scenes and heroes»). Причина — в NOTES заявки.

Кадры: `live_tune.py bench --fixture <файл>` (и `start --fixture`). Значение — имя файла в
`unreal/Unmatched/Config/Bench/` или путь; `benchBoardId` файла обязан совпасть с доской `--map`, путь — без пробелов
(иначе код 2). `-BenchFixture=` внутри `--extra` запрещён (код 2): движок читает первое вхождение параметра.

```bash
python tools/art/render/live_tune.py bench --map marmoreal --fixture S08BenchMarmoreal-<Key>.json \
    --views K1+K2x1.6+K2x2.5 --out <dir> --packaged --extra=-BenchFocusFighter=<Key> --dry-run
#   печатает командную строку и {fixture, source pak|loose|worktree, variant}; ничего не запускает
```

Откуда клиент читает вариант (`source` в выводе и в JSON результата `bench`):
- редактор (без `--packaged`) — абсолютный путь файла в checkout (`worktree`), сборка не нужна;
- packaged — копия из пака (`pak`), если `Saved/StagedBuilds/Windows/Manifest_UFSFiles_Win64.txt` содержит
  `Unmatched/Config/Bench/<файл>`; иначе абсолютный путь файла в checkout (`loose`), **без перепаковки**. Чтение
  loose-файла packaged-клиентом живым прогоном ещё не подтверждено (основание — UE 5.8 `IsNonPakFilenameAllowed` не
  запрещает `.json`, прецедент `-BenchMoveDraft=<abs json>` в `docs/game-design/evidence/DE-FOOTAGE/2026-10-04/B/bench/`).
  Если в `bench.trace.log` есть `BENCH FAILED fixture load <path>` — путь пака ниже.

Путь пака (только при отказе loose или если вариант нужен в паке надолго): строка
`RuntimeDependencies.Add("$(ProjectDir)/Config/Bench/S08Bench<Map>-<Key>.json", StagedFileType.UFS);` на каждый файл
рядом с `unreal/Unmatched/Source/Unmatched/Unmatched.Build.cs:47-48` (правка `Build.cs` сама перегенерирует makefile),
сборка игрового target с `-MaxParallelActions=4`, одна упаковка (AGENTS.md «Packaging trap»). После неё `live_tune.py`
сам находит файл в манифесте и передаёт путь пака.

K2 центрирует героя зрителя фикстуры (seat 0 — Medusa), а новый герой стоит на seat 1. Поэтому для K2 нужен
`--extra=-BenchFocusFighter=<Key>` (принимает `Key` из `Specs()` или id бойца `f-1-hero`; трасса
`BENCH focus fighter=<id> (<Key>)`, `references/ue-import-package.md` §6.2).

### Д-3. Лист игровых кадров клипов AN-18 (`clip_review_sheet.py`, этапы 6–7)

Номера карточек больше не вычисляются: каждый персонаж — одна запись `HEROES` с явными карточками в порядке клипов
Idle, LungeAttack, HitReact, DeathSettle (шаблон — комментарий над `HEROES` в `tools/art/anim/clip_review_sheet.py`):

```python
"<Key>": Hero("<Character>", "<PRE>", <IdleSeconds>, ("AN-<idle>", "AN-<lunge>", "AN-<hit>", "AN-<death>")),
```

- Четыре карточки клипов — новые строки `docs/game-design/visual/06-tasks/anim.csv` (area `anim`) со следующими
  свободными номерами (на 2026-10-09 занято до `AN-36`; карточка этапа 0 `VISUAL_CARD_ID` берёт свой номер раньше).
  Образец — `AN-01…AN-04` King Arthur: `title` содержит `(<Clip>)` («King Arthur — выпад (LungeAttack), клип D-11»),
  `keyframes` — строки `<мс> мс к.<N>: …`, `timing` — длина и кадры при 24 fps.
- Страж реестра (`--check`, `run`, `sheet`): каждая карточка из `HEROES` есть в `06-tasks/*.csv` и её `title`
  называет свой клип; карточка с чужим клипом или со старым вычисленным номером `AN-17…AN-20` — ошибка до листа.
- Кадры K1 = объединение `UNION` (AN-17) и кадров `к.N` из `keyframes` карточек всех персонажей `HEROES`: ключевые
  кадры нового клипа попадают в K1 сами.
- Боец трассы опознаётся по фокусу запуска (`BENCH clip-pose … fighter=<id>` в каталоге `<frames>/<map>/<Key>`).
  Длина Idle — запасной признак и только когда она уникальна среди `HEROES`: совпадение Idle с чужим героем лист не
  ломает, уникальность Idle больше не требование заявки.
- K1 снимает первый ключ `--heroes`; если K1 и K2 сняты на разных `-BenchFixture`, `sheet` пишет проблему (тот же id
  бойца может быть другой фигурой). Поэтому новый персонаж идёт первым ключом и со своим вариантом Д-2.

```bash
python tools/art/anim/clip_review_sheet.py --check        # "check": "PASS", "fails": [] (AN-01…AN-16 прежние)
python tools/art/anim/clip_review_sheet.py run --packaged --heroes <Key> \
    --fixture marmoreal=S08BenchMarmoreal-<Key>.json,sarpedon=S08BenchSarpedon-<Key>.json
python tools/art/anim/clip_review_sheet.py sheet --cards <AN-… четырёх клипов через запятую>
```

`run --fixture FILE` годится только с одной доской (`--maps marmoreal`); для двух досок — пары `map=FILE`. Значение
уходит в `live_tune.py bench --fixture`. `-BenchFocusFighter` `run` не добавляет и добавлять не нужно: фокус клипа задаёт
`-BenchClipPoseFighter` (а `S08FxBenchFocus` выполняется после разбора поз и перезаписал бы фокус). Пробный запуск —
после этапа 7 (Specs, упаковка). Лист открыть и осмотреть: в каждой строке фигура нового персонажа.

## 3. Обязательно: этап 3 (до первого `run_h2_bake.py`)

Стадия `probes` вызывает `validate_clip.py --character=<rig.character>` (`run_h2_bake.py:114`), а `rig_rules.py:33` на
незнакомом персонаже бросает `KeyError`. Поэтому запись в контракте должна появиться до прогона.

| № | Файл:строка | Что добавить (по образцу) | Проверка |
|---|---|---|---|
| Р3-1 | `docs/art-pipeline/rig/rig-contract.json:56-61` (`skeletons.UM_HUMANOID_17_v2.characters`) | с оружием: `"<Character>": {"asset_id": "<ASSET_ID>", "weapon_bone": "<weapon_bone>", "weapon": "<что и в какой руке>", "ue_weapon_bone": "<ue_weapon_bone>"}` (образцы: Medusa `:57` — `weapon.L`/`weapon_L`, Arthur `:58` — `weapon.R`/`weapon_R`); без оружия: `"weapon_bone": null`, без `ue_weapon_bone`, с `"note"` о точке удара, как у Harpy (`:60`) | тест Р3-3 |
| Р3-1 | там же `:3` `revision` и `:4` `previous_revision` | решение скилла: `"revision": "v2-<YYYY-MM-DD>"`, в `previous_revision` — прежнее значение и пометка «добавлен персонаж <Character>, кости не менялись». Значение попадает в манифест клипов при `clip_manifest.py build` (`clip_manifest.py:93-94`) и в отчёт `validate-skeletal-mesh-v2.json` (поле `contract_revision`, см. регресс Д-1) | — |
| Р3-1 | там же `:17` (`applies_to`), `:234` (`sockets_v2` → `Weapon.bone_by_character`) | `"<ASSET_ID>"` в `applies_to`; `"<Character>": "<ue_weapon_bone>"` (без оружия — «профиль (…)», как у Harpy). Код эти поля не читает, правка нужна для согласованности | — |
| Р3-2 | `docs/art-pipeline/rig/RIG-CONTRACT.md:72`, `:128` | персонаж и его кость оружия в строках `weapon.L / weapon.R (v2)` и `Weapon` | — |
| Р3-3 | `tools/tripo-pipeline/tests/test_rig_rules.py:83-88` (`test_characters`) | с оружием: `self.assertEqual(chars["<Character>"]["weapon_bone"], "<weapon_bone>")`; без оружия: `self.assertIsNone(chars["<Character>"]["weapon_bone"])` | `python -m unittest tools/tripo-pipeline/tests/test_rig_rules.py` → `OK` (на 2026-10-09: 21 тест) |
| Р3-4 | новые профили `art/pipeline-candidates/<ASSET_ID>/build-profiles/*.json` | `profile_id` каждого профиля уникален среди всех `build-profiles/*.json`; в профиле h2-bake `rig.character` = `<Character>`, `rig.skeleton` = `UM_HUMANOID_17_v2` (образец `medusa-h2-bake-h2.json`); часть и меш оружия, кости `weapon.*` и сокет `Weapon` — по `WEAPON_HAND` (таблица Д-1, раздел 2). Содержание профилей — `references/acceptance-and-blender.md` и HANDBOOK §4.2 | тот же прогон: `test_profile_ids_unique`; стадия `rig` — `weapon_bone_by_side_v2` PASS |

## 4. Обязательно: этап 6 (анимация, VFX, SFX)

Спека h2anim (`<content-key>-h2anim.json`, образец `art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json`):
`"character": "<Character>"`, `"ue_hero": "<Key>"` — у Arthur это разные значения (`Arthur` и `KingArthur`). Длины клипов
жёстко заданы в игре (`S08HeroesV2.cpp:157-165`, ± 0,02 с в тесте `S08HeroesV2Tests.cpp:310`): Idle = `<IdleSeconds>`,
LungeAttack 14 кадров, HitReact 10, DeathSettle 21 при 24 fps (HANDBOOK §2.8). `<ContactFrame>` должен быть одним из
`key_frames` LungeAttack: иначе `de010.py` откажет (`tools/art/de010/de010.py:65-74`).

| № | Файл:строка | Что добавить (по образцу) | Проверка |
|---|---|---|---|
| Р6-1 | `tools/tripo-pipeline/anim/clip_manifest.py:41-42` (`CHARS`) | `"<Character>": ("<PRE>", "<ASSET_ID>")` | Р6-3 |
| Р6-1 | там же `:44-47` (`H2ANIM`) | `"<Character>": "art/pipeline-candidates/<ASSET_ID>/build-profiles/<content-key>-h2anim.json"` | Р6-3 |
| Р6-1 | там же `:5-6`, `:277` (текст «16 слотов = 4 клипа × 4 персонажа») | число слотов в тексте: 4 × число персонажей | — |
| Р6-2 | `docs/art-pipeline/animation-library/clip-manifest.schema.json:36` (`character.enum`) | `"<Character>"` в перечисление `["Medusa", "Harpy", "Arthur", "Merlin"]` | Р6-3 |
| Р6-3 | `docs/art-pipeline/animation-library/clip-manifest.json` (генерируется) | пересборка: 4 новых слота `<PRE>-Idle/LungeAttack/HitReact/DeathSettle`, заполненные клипами H2Anim | `python tools/tripo-pipeline/anim/clip_manifest.py build` → `MANIFEST_CHECK PASS` (build сам вызывает check) |
| Р6-4 | `tools/art/anim/clip_review_sheet.py:65-70` (`HEROES`) и `docs/game-design/visual/06-tasks/anim.csv` | запись `"<Key>": Hero("<Character>", "<PRE>", <IdleSeconds>, ("AN-…", "AN-…", "AN-…", "AN-…"))` и 4 карточки клипов (Д-3, раздел 2). Сам лист строится на этапе 7 | `python tools/art/anim/clip_review_sheet.py --check` → `"fails": []` (ловит и карточку, не совпадающую со своим клипом) |

`validate_clip.py`, `h2anim_run.py`, `clip_contact_check.py`, `h2anim_ue.py` читают персонажа из спеки и контракта,
отдельной регистрации они не требуют. Строка в docstring `validate_clip.py:19` (`--character=Medusa|Arthur|Merlin|Harpy`) —
только описание.

## 5. Обязательно: этап 7 (импорт и подключение S08)

Порядок: импорт меша, MI и клипов (`references/ue-import-package.md`) → de010/de011 → C++ и тесты → cue-table → конфиги →
кадры в игре. Всё ниже обязательно для героя и помощника: подключение S08 входит в выход этапа 7. Логи и сырые кадры —
в `$W` = `C:/tmp/<ASSET_ID>-stage7` (блок «Среда UE» в `references/ue-import-package.md`).

### 5.1 Ассеты UE, которые создают инструменты de010/de011

`de010.py apply` ставит notify `Contact` на LungeAttack каждого героя из своего списка `HEROES`. `de011.py apply` создаёт
для каждого героя из того же списка (`de011.py:58-63` итерирует `de010.HEROES`) Masked-MIC
`MI_<Key>_<Stage>_{P1,P2}_Dissolve` (дочерние к MI тела). Без notify тест `HeroesV2.Contact` падает
(`S08HeroesV2Tests.cpp:540`). Без MIC тест `HeroesV2.Dissolve` падает (`:735`), а фигура при смерти пропадает рывком
(`S08FighterActor.cpp:1269`, трасса `death … mi=missing`, `:1286-1289`).

| № | Файл:строка | Что добавить (по образцу) | Проверка |
|---|---|---|---|
| Р7-1 | `tools/art/de010/de010.py:39-42` (`HEROES`) | `("<Key>", "<Stage>", "<ASSET_ID>/build-profiles/<content-key>-h2anim.json", <ContactFrame>),`. Строка нужна всегда: по ней `de011.py apply` создаёт MIC, а каждый следующий `de010.py apply` переставляет notify и этому герою | `$W/de010/apply.json`: у клипа `<Key>` одна notify `Contact` в `time` = `<ContactFrame>`/24, длина и число кадров до/после равны |
| Р7-2 | `tools/art/de011/de011.py:40` (`CAPTURE_LOOKS`) | `"<Key>": "P1"` (или `P2`, чтобы в съёмке были оба цвета). Без этой строки `de011.py capture` падает с `KeyError`, `apply` её не читает | `de011.py capture --tag after --dissolve` без ошибки |

**Основной путь — headless, шаг 7b `SKILL.md`.** Оба `apply` запускают свой `UnrealEditor-Cmd` проекта этого чекаута и
сохраняют ассеты (`de010.py:79-107`). GUI-редактор этого чекаута в это время должен быть закрыт: так требует однотипный
инструмент `tools/art/fx/fx_ability.py:4`, и так HANDBOOK §0.1 ограничивает шаги `UnrealEditor-Cmd`. Если открыт редактор
пользователя, агент его не закрывает: это гейт стопа `SKILL.md` §5 п.7, worktree его не обходит
(`references/ue-import-package.md` §1 п.4).

```bash
# после импорта клипов (h2anim_ue.py import) и MI тела. Повторный импорт клипов удаляет клип вместе с notify
# (h2anim_ue.py:13-14), тогда de010 apply повторить.
python tools/art/material_library/ue_lock.py --step "de010 apply <Key>" -- \
    python tools/art/de010/de010.py apply --frames $W/de010
python tools/art/material_library/ue_lock.py --step "de011 apply <Key>" -- \
    python tools/art/de011/de011.py apply --frames $W/de011
```

**Запасной путь только для notify — задача живого редактора** из `references/animation-vfx-sfx.md` §7 (через
`ue_live`, под `ue_lock.py`). Он ставит notify одного клипа без пересборки материала. Применять, когда notify нужен
сразу после импорта клипов в открытом редакторе (например, перед UE-кадрами приёмки клипов этапа 6), а шаг 7b ещё
впереди. Строку Р7-1 он не заменяет, и `de011.py apply` для MIC нужен всё равно.

Ограничения инструментов:

- `de010.py apply` пересобирает `M_UM_Figure_v2` текущим графом `tools/art/material_library/ue_v2_master.py`
  (`figure_v2_graph`, `de010.py:120-130`) и заново ставит notify всем героям списка. `de011.py apply` тоже пересобирает
  `M_UM_Figure_v2` (`de011.py:99-108`) и создаёт MIC всех героев; notify он не трогает. Обе операции идемпотентны. После
  них обязательны тесты `HeroesV2.HitTint`, `HeroesV2.FxChannels`, `HeroesV2.Dissolve` (5.3).
- Пока notify нет, рантайм берёт кадр контакта из `LungeContactFrame` (`S08HeroesV2.cpp:167-181`, `ContactSeconds`), и
  тайминг удара не ломается. Тест Contact при этом всё равно падает, поэтому шаг обязателен.

### 5.2 C++: таблица героев и автотесты

| № | Файл:строка | Что добавить (по образцу) | Проверка |
|---|---|---|---|
| Р7-3 | `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp:104-109` (`Specs()`) | `{TEXT("<FighterName>"), TEXT("<Key>"), TEXT("<Stage>"), <bHero>, <BudgetUU>f, <MinUU>f, <MaxUU>f, <FigureTopUU>f, <BoundsTopUU>f, <IdleSeconds>f, <ContactFrame>},` — все 11 полей `FHeroSpec` (`S08HeroesV2.h:99-119`); `FigureTopUU` и `BoundsTopUU` — измеренные в UE после импорта (`ue-import-report.json` / отчёт look-dev), не прогноз | тесты 5.3 |
| Р7-4 | `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2Tests.cpp:110` | `TestEqual("five heroes", Specs().Num(), 5);` (число = новое число строк) | `HeroesV2.Mapping` |
| Р7-4 | там же `:102` (цикл имён Mapping) | `TEXT("<FighterName>")` в список `{TEXT("King Arthur"), …}` | `HeroesV2.Mapping` |
| Р7-4 | там же `:199` (цикл отношения помощник/герой) | только для помощника: `TEXT("<FighterName>")` в `{TEXT("Merlin"), TEXT("Harpies")}`. Правило 0,78 ± 0,06 (HANDBOOK §2.10) иначе для нового помощника не проверяется | `HeroesV2.Scale` |
| Р7-4 | там же `:514-515` (`WantMs`) | `{TEXT("<Key>"), <ContactFrame> × 1000 / 24 f}` (к.7 → `291.667f`, к.8 → `333.333f`) | `HeroesV2.Contact` |
| Р7-4 | там же `:107` (`FS08HeroesV2MappingTest`) и `:489` (`FS08HeroesV2ActorTest`) — `Sinbad` как незнакомый герой | только если `<FighterName>` = `Sinbad` (или другое имя из `grep -in '"<FighterName>"' …/S08/*Tests.cpp`, раздел 0): заменить имя-образец в обоих местах на `Unknown Fighter` (решение скилла: имени нет в ростере и в `scraped-data/api/heroes`) | `HeroesV2.Mapping`, `HeroesV2.Actor` |
| Р7-4 | там же `:721-722` (`WantSeconds`) | `{TEXT("<Key>"), 0.5f}` для героя, `0.4f` для помощника (`S08HeroesV2.h:202-203`) | `HeroesV2.Dissolve` |
| Р7-5 | `unreal/Unmatched/Source/Unmatched/S08/S08AudioBank.cpp:54-60` (`CharacterKey`) | `if (Name.Contains(TEXT("<подстрока имени>"), ESearchCase::IgnoreCase)) return TEXT("<AUDIO_KEY>");`. Правило подстрочное: имя с «harp», «arthur», «merlin», «medusa» перехватит чужой ключ. Новую строку ставить выше пересекающейся | `Unmatched.S08.Audio` |
| Р7-5 | там же `:62-68` (`HitType`) | `if (Key == TEXT("<AUDIO_KEY>")) return TEXT("<HIT_TYPE>");`. Без строки тип BLUNT: удар звучит `CMB-HIT-BLUNT`, а выпад молчит, потому что банка `CMB-LUNGE-BLUNT` нет (`S08FlowGameModeAudio.cpp:526-527`). Слот `hit_type` обязателен по `docs/game-design/audio/02-audio-design.md` §8.1 | `Unmatched.S08.Audio` |
| Р7-5 | `unreal/Unmatched/Source/Unmatched/S08/S08AudioTests.cpp:47-51` | `TestEqual("<имя> key", S08AudioBank::CharacterKey(TEXT("<FighterName>")), FString(TEXT("<AUDIO_KEY>")));` и такой же для `HitType`. Тест `:49` берёт `"Robin Hood"` как незнакомого героя: если новый персонаж — Robin Hood, заменить имя в этом тесте | `Unmatched.S08.Audio` |

`S08FlowGameModeFigures.cpp` своей таблицы не держит: `-BenchClipPoseFighter=<Key>` разрешается по `Specs()`
(`S08FlowGameModeFigures.cpp:84-92`). Блок `heroMaterials` профилей света (`S08BoardArt.cpp:171-172`) и
`S08AbilityFx::HeroKeyOfName` (`S08AbilityFx.cpp:51-56`) тоже читают `Specs()`.

### 5.3 Сборка и автотесты

```bash
# сборка редактора (Build.bat отдаёт 0 и при ошибке компиляции: в выводе искать "Result: Succeeded")
node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development \
    -Project=<абсолютный путь>/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=4
node tools/s08/run-ue-tests.cjs "Unmatched.S08" $W/ue-tests-s08.log   # весь набор (references/ue-import-package.md §5 п.4)
```

Выход: `TEST COMPLETE. EXIT CODE: 0`, ни одной строки `Result={Fail}`; в логе PASS у наборов `HeroesV2`, `Audio` и
(если правился раздел 6) `CueFx`. Ограничения, которые проверяют тесты (`S08HeroesV2Tests.cpp`), выбирать при заполнении Specs:

| Тест | Строка | Ограничение |
|---|---|---|
| Scale | `:186`, `:189` | видимая высота = бюджет; отношение `BudgetUU / FigureTopUU` отличается от 1 меньше чем на 1 %: верх фигуры из Blender попадает в бюджет с точностью 1 % |
| Scale | `:187` | `MinUU ≤ BudgetUU ≤ MaxUU` |
| Scale | `:191` | `BoundsTopUU + 0,01 ≥ FigureTopUU` |
| Scale | `:196` | каждый герой выше каждого помощника: сейчас новый герой выше 45 uu (Merlin), новый помощник ниже 55 uu (Medusa, Arthur) |
| Scale | `:204` | помощник / Medusa = 0,78 ± 0,06 (после правки `:199`) |
| Assets | `:277`, `:280` | верх bounds SK = `BoundsTopUU` ± 0,5 uu; низ bounds в 0…8 uu |
| Assets | `:310` | длины четырёх клипов ± 0,02 с; клипы на скелете меша `Rig/SK_<Key>_Skeleton` |
| Assets | — | MI тела и подставки P1/P2 на `M_UM_Figure_v2` |
| Contact | `:537`, `:540` | один `Contact` (`US08ContactAnimNotify`) только на LungeAttack, в `<ContactFrame>`/24 ± полкадра |
| Dissolve | `:725`, `:735` | длина 0,5 / 0,4 с; MIC — дочерний к MI тела, Masked |

### 5.4 Контракт CUE

Строки `cue-table.json` добавляются после импорта: `validate-table` проверяет, что `.uasset` лежит в
`unreal/Unmatched/Content/` (`tools/s08/cue_contract/cue_contract.py:257-260`). Без ключа персонажа гейт трассы для его
HitReact и смерти выдаёт `missing` (`cue_contract.py:342-345`). Ключ сопоставляется с субъектом трассы по буквам
(`cue_contract.py:80-89`: равенство, ключ оканчивается субъектом или субъект начинается с ключа), поэтому ключ —
ровно `<Key>`.

| № | Файл:строка | Что добавить (по образцу) | Проверка |
|---|---|---|---|
| Р7-6 | `docs/unreal/contracts/cue-dispatcher/cue-table.json:560-565` (CUE-011 `clip.sequence_by_fighter`) | `"<Key>": "/Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_HitReact.AM_<Key>_HitReact"` | `python tools/s08/cue_contract/cue_contract.py validate-table` → `CUE_TABLE PASS`; `python -m pytest tools/s08/cue_contract/test_cue_contract.py -q` → все PASS (на 2026-10-09: 75 passed) |
| Р7-6 | там же `:691-696` (CUE-013) | то же с `AM_<Key>_DeathSettle` | то же |

### 5.5 Конфиги, реестр, git

| № | Файл:строка | Что добавить (по образцу) | Проверка |
|---|---|---|---|
| Р7-7 | `unreal/Unmatched/Config/DefaultGame.ini:33-44` | `+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/<Key>/<Stage>")`, `…/<Key>/Rig`, `…/<Key>/H2Anim`. MIC (`/Game/UM/Materials/v2`, `:45`), FX (`/Game/S08`, `:17`) и звук (`/Game/Audio`, `:18`) уже в списке | листинг `.utoc` содержит ассеты (`references/ue-import-package.md` §6.1; `.pak` даёт 0 строк — IoStore) |
| Р7-8 | `unreal/Unmatched/Config/Cards/S08FighterNames.json:5-6` (`heroes`, ключ — `heroSlug` героя-владельца с сервера) | для героя: `"<slug>": {"hero": {"en": "<FighterName>", "ru": "<имя по-русски>"}, "sidekick": {…}}`. **Только помощник** (`OWNER_HERO_SLUG`): формат держит одного помощника на героя (`"sidekick"` — объект), поэтому запись не добавляется и чужая не перезаписывается (иначе у владельца в реальной игре сменится табличка его помощника, например Merlin у `king-arthur`); строка в NOTES заявки «S08FighterNames: формат на одного помощника, табличка — серверное имя». Без записи табличка показывает серверное имя (`:3`). Файл уже в пак-списке (`Unmatched.Build.cs:61`): touch не нужен | табличка при наведении на кадре показывает русское имя |
| Р7-9 | `docs/game-design/visual/03-asset-registry.csv` | строки по образцу `SK_Merlin_H2LD` и `AM_Merlin_<Clip>`: `SK_<Key>_<Stage>` (area `hero`, `ue_path` `/Game/PipelineCandidates/<Key>/<Stage>/Meshes/SK_<Key>_<Stage>`, `rollback_flag` «-S08HeroesLegacy (серый Body: блок-аута ART-003 у нового персонажа нет)» — блок-ауты есть только у трёх имён, `S08FighterActor.cpp:347-353`), 4 строки `AM_<Key>_<Clip>` (area `anim`), строки звука и FX из раздела 6. Всего 13 колонок | `PYTHONIOENCODING=utf-8 python -c "import csv;r=list(csv.DictReader(open('docs/game-design/visual/03-asset-registry.csv',encoding='utf-8-sig')));print(len(r),{len(x) for x in r})"` → множество `{13}` |
| Р7-10 | `.uasset` новых ассетов | `git add -f` поимённо: `unreal/Unmatched/.gitignore:8` игнорирует `Content/`. Касается `/Game/PipelineCandidates/<Key>/…`, `/Game/UM/Materials/v2/Dissolve/MI_<Key>_*`, перезаписанных `AM_<Key>_LungeAttack` и `M_UM_Figure_v2` | `git status --short --ignored` по этим путям |

### 5.6 Кадры в игре

Канонические фикстуры содержат только четырёх нынешних бойцов, поэтому кадры нового персонажа снимаются на его
вариантах (Д-2, раздел 2). Порядок:

1. Р7-11: варианты фикстуры обеих досок — `env_bench_fixtures.cts --variant <Key> --hero-name "<FighterName>"
   --hero-slug <slug> [--sidekick-name "…"]` (только помощник — `--hero-name "<owner_name>" --hero-slug <owner_slug>
   --sidekick-name "<FighterName>"`, Д-2) → `unreal/Unmatched/Config/Bench/S08Bench{Marmoreal,Sarpedon}-<Key>.json`;
   проверка `env_bench_fixtures.cts --check` (канонические и оба варианта `ok`); файлы коммитятся с персонажем. Можно
   ещё в 7a: сборки не требует.
2. Одна упаковка (`tools/s08/package-client.ps1`, AGENTS.md «One package per change»). Вариант в пак не добавляется:
   packaged-клиент читает его loose-файлом, перепаковка не нужна (Д-2; живым прогоном ещё не подтверждено — при
   `BENCH FAILED fixture load` путь пака Д-2).
3. `-Bench` на Marmoreal и Sarpedon: `live_tune.py bench --map <доска> --fixture S08Bench<Map>-<Key>.json
   --extra=-BenchFocusFighter=<Key> …` (полная команда — `references/ue-import-package.md` §6.2).
4. Осмотр PNG глазами (AGENTS.md «Look before you report»).
5. Проверка трассы. Нет `BENCH FAILED fixture load` (`S08FlowGameMode.cpp:8916`; тогда путь пака Д-2). Нет
   `ARTPREVIEW heroesV2 fighter=… missing=… fallback=legacy` (`S08FighterActor.cpp:882`). Нет `death … mi=missing`
   (`:1286-1289`). Нет `anim … missing=1` (`:934`, функция `PlayHeroClip`).
6. Лист клипов AN-18: `clip_review_sheet.py run --packaged --heroes <Key> --fixture marmoreal=…,sarpedon=…`, затем
   `sheet --cards …` (Д-3, раздел 2).

## 6. Только если нужно: способность, FX, свой звук, тюнинг

| Условие | Файл:строка | Что добавить | Этап | Проверка |
|---|---|---|---|---|
| FX способности (CUE-014) | `tools/art/fx/fx_ability.py` + `ue_fx_ability.py:461-466` | новая маска, Niagara-система `NS_FX_<…>` по рецепту существующих (`NS_FX_ArthurArc`, `NS_FX_MedusaVortex`). Инструмент собирает только эти две, а новая система — новый код в нём (`fx_ability.py:1-20`); редактор чекаута закрыт (`:4`) | 6 | отчёт `C:/tmp/visual/vs6-f3/fx-ability.json` |
| то же | `docs/unreal/contracts/cue-dispatcher/cue-table.json:740-751` (CUE-014 `vfx.by_hero`) | `"<Key>": {"system": "/Game/S08/FX/Combat/NS_FX_<…>.NS_FX_<…>", "socket": "Weapon" \| "Root", "fx_row": "FX-<NN>"}`; `fx_row` должен быть в `docs/game-design/visual/06-tasks/vfx.csv` | 7 | `cue_contract.py validate-table` |
| то же | `unreal/Unmatched/Source/Unmatched/S08/Fx/S08CueFx.cpp:69-72` | `Make(TEXT("CUE-014"), TEXT("/Game/S08/FX/Combat/NS_FX_<…>"), CombatEffectType, true, TEXT("<socket>"), <бюджет спрайтов>, true, TEXT("<Key>")),` — реестр зеркалит cue-table | 7 | `Unmatched.S08.CueFx` (`S08CueFxTests.cpp:97-98` проверяет две нынешние системы; для новой — добавить проверку) |
| то же | `tools/art/fx/fx_audit.py:34-37` (`BUDGETS`) | `"NS_FX_<…>": <бюджет>` | 7 | `fx_audit.py` (команда в его docstring) |
| то же | `unreal/Unmatched/Source/Unmatched/S08/Fx/S08AbilityFx.h:66-71`, `S08AbilityFx.cpp:51-60`, `Fx/S08FlowGameModeAbilityFx.cpp` | условие срабатывания способности героя — по образцу `IsArthurAbilityBoost` / `MedusaPendingPrefix`; это игровая логика, а не строка данных | 7 | `Unmatched.S08` (тесты способностей) |
| Свой звук смерти | `tools/audio/sfx_build.py:653-679` | `@recipe("DTH-<AUDIO_KEY>", "death")` по образцу; цепочка `sfx_build.py → ue_bank.py → ue_import_audio.py → ue_verify_audio.py` — в `references/animation-vfx-sfx.md`. Без него звучит `DTH-TEMPLATE` (`S08FlowGameModeAudio.cpp:628-629`) | 6 | `S08AudioBankData.inl` пересоздан `ue_bank.py`; `Unmatched.S08.Audio` |
| Карты-сигнатуры героя со своим звуком | `unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeAudio.cpp:62-80` (`FindSignature`) | `{TEXT("<имя карты>"), TEXT("<AUDIO_KEY>"), TEXT("CARD-<…>"), TEXT("<банк эффекта>")},` по образцу карт Arthur/Medusa; без строки карта играет общий звук | 6–7 | `Unmatched.S08.Audio` |
| VO, субтитры | `docs/game-design/audio/04-vo-script.md`, `tools/audio/vo_batch.py`, `S08FlowGameModeAudio.cpp:47-53` (`SpeakerName`), ответ союзника `:606` (`ALLY-LOW` → `MERLIN`) | реплики `VO-<AUDIO_KEY>-<EVENT>`; имя говорящего EN/RU. Тест `S08AudioTests.cpp:42` считает 101 реплику — обновить число. Без VO герой молчит, остальное работает (02-audio-design.md §8.1) | 6–7 | `Unmatched.S08.Audio` |
| Лейтмотив, стинги | `STG-SELECT/WIN/LOSE-<AUDIO_KEY>`, `STG-SIDEKICK-DOWN-<AUDIO_KEY>` (`S08FlowGameModeAudio.cpp:641`, `:991`) | стинги по 02-audio-design.md §8.1; фолбэк — общие | 6 | то же |
| Тюнинг материала (Fix, ВР-16) | `unreal/Unmatched/Config/ArtTuner/S08ArtTunerParams.json:114-137` | 6 строк `<Key>.FixClassA…FixSpecB` по образцу `KingArthur.*`; если тест должен их считать — героя в список `S08HeroMaterialsTests.cpp:216` и число в `:224` | 7 | `Unmatched.S08.ArtTuner` |
| то же | `unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json:76` (`heroMaterials`) | `"<Key>": {"*": {…}}` только по итогам live tune; ключ должен быть в `Specs()`, иначе запись отбрасывается с ошибкой (`S08BoardArt.cpp:174-178`) | 7 | трасса без `unknown hero key` |
| Видео-референсы движения | `tools/art/syntx_video_refs/build_manifest.py:16` (зашит на `ASSET-MEDUSA-001`) | решает `references/animation-vfx-sfx.md`; для нового персонажа нужен свой каталог `art/animation-refs/<ASSET_ID>/` | 6 | — |
| Фикстура трассы CUE с новым героем | `unreal/Unmatched/Source/Unmatched/S08/S08CueDispatcherTests.cpp:48` (`FighterClip`, зеркало `cue_contract.fighter_clip`) | `TEXT("<Key>")` в список ключей — только если в фикстуры `tools/s08/cue_contract` добавлен бой с новым героем | 7 | `Unmatched.S08.CueDispatcher` |

## 7. Проверено: правка не нужна

| Файл | Почему |
|---|---|
| `tools/tripo-pipeline/anim/rig_rules.py`, `validate_clip.py`, `h2anim_run.py`, `h2anim_ue.py`, `clip_author.py`, `clip_contact_check.py` | персонаж берётся из спеки и контракта; имена героев только в комментариях |
| `tools/tripo-pipeline/tripo_pipeline.py` | имена героев только в комментариях и docstring |
| `tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py:102-103` | метки проб берутся из `asset_id` профиля: `<content_key>-h2-blend` / `<content_key>-h2-fbx` (`reports/deform/<content_key>-h2-*-deform.json`; у Medusa прежние `medusa-h2-*`), отдельной строки не нужно |
| `tools/tripo-pipeline/blender/h2_bake/*.py` (`st_rig`, `st_seams`, `st_preview`, `st_lookdev`, `st_team`) | сторона оружия и его наличие — из профиля и контракта (Д-1, раздел 2); имена героев только в комментариях |
| `tools/art/render/live_tune.py`, `env_bench_fixtures.cts` | вариант фикстуры — флаги `--variant` / `--fixture` (Д-2), строк регистрации нет; новые данные — только файлы `S08Bench<Map>-<Key>.json` (Р7-11) |
| `tools/art/material_library/ue_h5cb1.py` (HEROES, `review --hero`), `lookdev_5cb0.py`, `ue_v2_accent.py` | разовые инструменты волн 5c-B1 и v2.1. Съёмка look-dev нового героя: `python tools/art/material_library/ue_hero_lookdev.py review --config <review json> --out <dir> --tag <tag>`, образец конфига `art/pipeline-candidates/ASSET-MERLIN-001/20260930-h2ld-ldc-ue/review-config.json` |
| `tools/art/de011/de011_capture_ue.py` | имена в docstring; съёмку задаёт `CAPTURE_LOOKS` (Р7-2) |
| `S08FlowGameModeFigures.cpp`, `S08AbilityFx.cpp:51` `HeroKeyOfName`, `S08BoardArt.cpp:171-172` | читают `Specs()` |
| `tools/art/render/render_bench.py` | правка кода не нужна: сцена задаётся флагом `run --bench-fixture` (для варианта Д-2 — то значение `-BenchFixture`, которое печатает `live_tune.py bench --dry-run --fixture …`). Новый персонаж добавляет меши и материалы, поэтому замер нужен ровно один — на этапе 7b, на варианте фикстуры Д-2; команда — `references/ue-import-package.md` §6.5, правило «записать число, править только превышение» — `SKILL.md` §8 «Режим» (AGENTS.md «Iteration speed», «No cost optimizations within budget») |
| `tools/tripo-pipeline/blender/candidate_build/*`, `candidate/atlas.py`, `review/control_scene.py`, `review/control_scene_analyze.py`, `review/team_contrast.py`, `tests/test_candidate_integration.py`, `run_rig_v2_validation.py`, `check_inputs.py`, `tools/art/art003_*`, `art005_*`, `t5*`, `move_selection/build_mockups.py`, `tools/s08/run-phase2-demo.ps1`, `tools/s09/*` | история прежних волн (W4-B, mvp-v1, 5c), тесты кандидатов или демо; имена в комментариях и фикстурах |
| Тесты на фиксированных фикстурах боя (`S08FacingTests.cpp`, `Fx/S08AbilityFxTests.cpp`, `S08BoardGraphTests.cpp`, `S08MoveHighlightTests.cpp`, `S09/S09CombatStageTests.cpp`, `S09/S09ResultTests.cpp`) | проверяют механику на четырёх нынешних бойцах; новый персонаж их не ломает |
| UI-галереи, заголовки и их тесты (`UmHudGallery.cpp`, `UmWorldGallery.cpp`, `UmPendingGallery.cpp`, `UmWorldLayerTests.cpp`, `S08ArtHudTests.cpp`, `S08ArtHudUmgTests.cpp`, `UmHudPanelsTests.cpp`, `UmPortraitTests.cpp`, `UmHeroCard.h`, `UmHudPlayerPanel.h`, `S08VoDirector.h` и др.) | стенды HUD на фиксированных данных; в заголовках имена только в комментариях |

## 8. Вне этого скилла (другие треки)

- **Данные сервера.** Боец с именем `<FighterName>` и его `heroSlug` должны быть в эталонной БД, иначе в живой игре фигура не
  появится. Для `-Bench` хватает фикстуры (Д-2).
- **Игровая логика способности:** `unreal/Unmatched/Source/Unmatched/S09/S09ManeuverUi.cpp:1856` (`BoostHeroes`, усиление
  атаки, сейчас только `king-arthur`).
- **Карты, портреты, рубашки:** `unreal/Unmatched/Config/Cards/S08CardMedia.json`, портреты по `heroSlug` (`UmPortrait.h:87-89`,
  без записи — монограмма). Отдельный конвейер `tools/art/cards/`.
- **Этап 0** (делает `SKILL.md`). Запись в `docs/art-pipeline/asset-registry.json` и проверка
  `python tools/tripo-pipeline/validate_registry.py`. `contentKey` — ключ из `docs/game-design/05-content-matrix.csv` или
  `null`, если ключа там нет (`SKILL.md` этап 0); валидатор проверяет только не-`null` значение
  (`validate_registry.py:295-297`). `manifest06Row` — `null` без строки в `docs/game-design/06-asset-manifest.csv`
  (`:290-291`). Отсутствие персонажа в 05 и 06 — не стоп. На 2026-10-09 валидатор уже выдаёт одну старую ошибку: sha256
  `art/um-materials/um-masters.json`, `RESULT: FAIL (1 errors)`. Критерий для нового персонажа — новых ошибок 0.

## 9. Короткий чек-лист регистрации

```text
[ ] этап 3: rig-contract.json characters (<weapon_bone>/<ue_weapon_bone> из заявки) + revision; RIG-CONTRACT.md;
            test_rig_rules.py OK; profile_id уникальны; профиль h2-bake по WEAPON_HAND (таблица Д-1)
[ ] этап 6: clip_manifest.py CHARS/H2ANIM + schema enum; clip_manifest.py build → MANIFEST_CHECK PASS;
            длины клипов 14/10/21 кадр и Idle = IDLE_SECONDS; кадр контакта среди key_frames;
            clip_review_sheet.py HEROES (Hero с 4 карточками) + 4 карточки anim.csv → --check PASS
[ ] этап 7: de010.HEROES + de011.CAPTURE_LOOKS → de010/de011 apply (шаг 7b, под ue_lock, редактор чекаута закрыт);
            grep имени бойца в S08/*Tests.cpp (Robin Hood :49, Sinbad :107/:489 → Unknown Fighter);
            Specs() (11 полей) + S08HeroesV2Tests (счётчик, имена, ratio, WantMs, WantSeconds);
            S08AudioBank CharacterKey/HitType + S08AudioTests; сборка + HeroesV2/Audio PASS;
            cue-table CUE-011/013 → validate-table PASS, pytest PASS; DefaultGame.ini ×3; S08FighterNames.json;
            03-asset-registry.csv; git add -f; варианты фикстуры Р7-11 → -Bench обеих досок (--fixture),
            кадры осмотрены, трассы чистые; лист AN-18 (run --fixture) осмотрен
[ ] по условию: CUE-014/FX, свой DTH/VO/стинги/карты-сигнатуры, Art Tuner, heroMaterials, фикстура CUE
```
