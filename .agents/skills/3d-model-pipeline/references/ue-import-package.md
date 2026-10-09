# Этап 7. Упаковка, импорт в UE, подключение S08, кадры в игре

Этап 7 карты этапов скилла (SKILL.md, «Карта этапов 0–7»). Требование заказчика №5: «результат упакован и готов к
импорту в UE».

| | |
|---|---|
| Вход | принятый H2LD-набор этапа 3 (карточка этапа 4 с вердиктом `pass`), 4 клипа этапа 6 (все карточки клипов `pass`), звуки и FX этапа 6 |
| Выход | ассеты в `/Game/PipelineCandidates/<Key>/{<Stage>,Rig,H2Anim}`, правки C++ и конфигов из регистрации, кадры `-Bench` обеих досок, строки реестров, evidence |
| Критерий выхода | `ue-import-report.json` → `technically_imported` и все checks passed; автотесты `Unmatched.S08` PASS (в том числе `HeroesV2.Contact` и `HeroesV2.Dissolve`); кадры `-Bench` Marmoreal и Sarpedon открыты и осмотрены; трассы без отката; реестры обновлены |
| Исполнитель | запускающий агент |

Норма — `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (дальше HANDBOOK): §2 «Контракт», §4.6 «Импорт в UE», §4.7
«Подключение в игру S08», §5 «Статический пропс», §7.6 «Экспорт и UE», §8 «Сдача». Числа контракта (оси, масштаб,
текстуры, кости, длительности клипов, высоты) здесь не повторяются. Этот файл добавляет то, чего в хендбуке нет:
среду и блокировки, профили импорта и съёмки нового героя, обязательное подключение S08, кадры в игре, реестры и
ловушки, найденные при проверке 2026-10-09.

При расхождении с хендбуком выигрывает хендбук, кроме решений скилла из таблицы ниже. Обязательное подключение S08
(HANDBOOK §4.7), look-dev съёмка `ue_hero_lookdev.py review` (§4.6 п.6) и критерий реестра «новых ошибок нет» (§3.2
п.1, §8) с 2026-10-09 записаны в самом хендбуке (HANDBOOK §10, строка «Синхронизация со скиллом»): это уже норма, в
README evidence их не записывать. Отступлениями от хендбука остаются только решения из таблицы ниже; каждое записать в
раздел «Отступления от хендбука» README evidence (HANDBOOK §9):

| Решение скилла | Что в HANDBOOK | Почему иначе |
|---|---|---|
| В `03-asset-registry.csv` ставится «художественно принято, по делегированию» (§7.1) | §0 п.3: «Исполнитель ставит максимум „технически импортировано“» | делегированная приёмка по листу K1/K2 — решение пользователя ВР-17 (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`) и правило ВР-RG07 (`docs/game-design/visual/02-visual-design.md`); в `asset-registry.json` статус остаётся «технически импортировано» |
| Notify `Contact` ставится шагом `de010.py apply` (§5 п.3) | §4.6–4.7 этого шага нет | автотест `Unmatched.S08.HeroesV2.Contact` требует ровно один notify на LungeAttack (`S08HeroesV2Tests.cpp:537-540`) |
| `init` получает `--export-basename SK_<Key>_<Stage>` (§4.1 шаг 4) | §4.6 п.4 флаг не указан | так инициализированы все четыре принятых импорта (§4.1) |

Порядок этапа. Шаги 7.0–7.4 — подэтап 7a SKILL.md (открытый редактор, MCP), шаги 7.5–7.8 — подэтап 7b (без
GUI-редактора на этом checkout и без живой сессии Live Coding, §1 п.4):

| Шаг | Что | Раздел | Подэтап |
|---|---|---|---|
| 7.0 | проверить вход (пакет ассета) | §2 | 7a |
| 7.1 | поднять среду UE | §1 | 7a |
| 7.2 | написать профиль импорта и конфиг съёмки | §3 | 7a |
| 7.3 | импортировать: скелет, меш, клипы, замеры, сверка | §4.1–4.2 | 7a |
| 7.4 | look-dev съёмка в редакторе | §4.3 | 7a |
| 7.5 | подключить S08: de010/de011, C++, сборка, автотесты | §5 | 7b |
| 7.6 | упаковать один раз | §6.1 | 7b |
| 7.7 | снять кадры `-Bench` обеих досок, осмотреть, проверить трассы | §6.2–6.4 | 7b |
| 7.8 | обновить реестры и evidence, закоммитить, интегрировать | §7 | 7b |

Для пропа порядок другой, см. §8.

## 1. Среда UE (шаг 7.1)

Оболочка — Git Bash, корень текущего checkout (HANDBOOK §0.2). Переменные этапа:

```bash
export MSYS_NO_PATHCONV=1        # иначе /Game/... станет C:/Program Files/Git/Game/...
export PYTHONIOENCODING=utf-8
ROOT="$(pwd -W)"                                                    # корень текущего checkout в виде C:/...
T="python tools/tripo-pipeline/tripo_pipeline.py"                 # CLI 0.8.0 (tripo_pipeline.py:81)
L="python tools/art/material_library/ue_lock.py"                   # блокировка редактора
P=art/pipeline-candidates/<ASSET_ID>/build-profiles/<content-key>-h2ld-lookdev-ue-import.json   # профиль §3.1
R=art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-h2ld-ue-import    # run-каталог импорта (образец Medusa 20260929-h2ld-ue-import)
S=art/pipeline-candidates/<ASSET_ID>/build-profiles/<content-key>-h2anim.json                   # спека клипов этапа 6
V=art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-h2ld-ldc-ue       # look-dev съёмка в UE: review-config.json (§3.2) + review/<tag>/
E=docs/art-pipeline/evidence/<content-key>-<YYYYMMDD>             # evidence этапа (HANDBOOK §9)
W=C:/tmp/<ASSET_ID>-stage7                                         # логи и сырые PNG, вне git
netstat -ano | grep ':8123 .*LISTEN'                               # MCP редактора должен слушать
```

`<content-key>` — CONTENT_KEY заявки (`king-arthur`), `<Key>` — KEY (`KingArthur`), `<Stage>` — стадия из UE_NAMES
(`H2LD`, `H3LD` только у второго поколения). Имя каталога `$V` повторяет образцы
`ASSET-MEDUSA-001/20260930-h2ld-ldc-ue` и `ASSET-MERLIN-001/20260930-h2ld-ldc-ue`.

Правила среды:

1. **Предусловие MCP-шагов (7a)** — запущен GUI-редактор `unreal/Unmatched` с MCP `127.0.0.1:8123` (HANDBOOK §0.2).
   Редактор пользователя не закрывать и не перезапускать (AGENTS.md «Agent and process lifecycle»). Порт не слушает —
   агент запускает свой редактор командой HANDBOOK §0.2 и записывает PID. Закрывает он только этот PID и только при
   0 dirty-пакетов.
2. **Блокировка.** Каждая команда, которая ходит в редактор по MCP, запускается так:
   `$L --step "<шаг>" -- <команда>`. `ue_lock.py` держит `C:/tmp/ue-editor.lock`, ждёт чужую блокировку (опрос 20 с,
   устаревшей считается блокировка старше 25 мин) и возвращает код команды (`ue_lock.py:94-104`). На одну блокировку —
   один шаг одного героя (HANDBOOK §0.2). Скрипты `tools/tripo-pipeline/**` блокировку сами не берут (grep `ue_lock`
   там пуст), поэтому их надо оборачивать.
3. **Не оборачивать** `ue_hero_lookdev.py review` и `ue_hero_lookdev.py verify`: они берут ту же блокировку сами
   (`ue_hero_lookdev.py:335`, `:598`). Если обернуть, команда упрётся в собственную блокировку и простоит до её
   «устаревания» через 25 мин.
4. **Шаги без редактора (7b).** Это сборка `UnmatchedEditor` (`build-editor.cjs`), автотесты (`run-ue-tests.cjs`,
   `UnrealEditor-Cmd`), `de010.py apply` и `de011.py apply` (каждый запускает свой `UnrealEditor-Cmd` проекта своего
   checkout: `de010.py:33-35`, `:88`; `de011.py` — тот же раннер) и кук упаковки. Условия:
   - на этом checkout нет GUI-редактора: `UnrealEditor-Cmd` рядом с ним запрещён (HANDBOOK §0.1);
   - ни один `UnrealEditor.exe` движка не держит сессию Live Coding. Иначе сборка `UnmatchedEditor` падает во **всех**
     checkout с «Unable to build while Live Coding is active…» (`docs/unreal/UE-SESSION-DESIGN.md` F9). Игровой
     target `Unmatched` этим мьютексом не блокируется (там же), но автотестам и de010/de011 нужна собранная
     `UnmatchedEditor` с новой строкой `Specs()`.

   Порядок: сначала все MCP-шаги §4 (7a), затем `git add -f` новых `.uasset` и коммит (§7.3), затем шаги 7b.
   - Редактор свой — агент закрывает его по PID (0 dirty-пакетов) и выполняет 7b.
   - Открыт редактор пользователя — это гейт стопа SKILL.md §5 п.7. Worktree его не обходит: сборка `UnmatchedEditor`
     в worktree упирается в тот же мьютекс Live Coding, без неё автотесты проверяют старую таблицу `Specs()`, а
     `tools/git/safe-integrate.sh` при изменениях в `unreal/` отказывает, пока запущен UnrealEditor главного checkout
     (`safe-integrate.sh:52-57`, «UE/UBT processes of the main checkout are running»). Агент сохраняет и коммитит
     результат 7a и отдаёт пользователю пакет: «Закройте редактор (или разрешите агенту закрыть его при 0
     dirty-пакетов), чтобы продолжить шаги 7.5–7.8» и список этих шагов с командами. Дальше агент ждёт закрытия
     редактора (проверка — `netstat` из блока переменных и список процессов), сам редактор пользователя не закрывает.
5. **Живой Blender** (MCP `:9876`) на этом этапе нужен только для осмотра. Производственные байты из него не берутся
   (HANDBOOK §0.1, §6).
6. Свои процессы (headless Blender, клиенты `-Bench`, `UnrealEditor-Cmd`) после шага проверяются и останавливаются по
   PID. Командную строку сверять до остановки, по имени процессы не убивать (AGENTS.md «Agent and process lifecycle»).

## 2. Пакет ассета: проверка входа (шаг 7.0)

Пакет готов к импорту, когда в репозитории есть всё ниже и всё проверено. Без любого пункта импорт не начинать.

| Пункт | Где | Проверка |
|---|---|---|
| Вердикт модели `pass` | `art/pipeline-candidates/<ASSET_ID>/evidence/acceptance/<YYYYMMDD>-r<N>/card.json` (при неустойчивом pass — ещё `card-2.json` и `final.json`) | `python tools/art/acceptance/validate_card.py <card.json> --print-verdict` → код 0, вердикт `pass`. Код 3 (`needs_second_acceptor`, `score` 8,0–8,4) — входом служит итог пары: `validate_card.py card.json --second card-2.json --final-json final.json` → код 0 и `verdict: pass` в `final.json` (`references/acceptance-and-blender.md` §8.5) |
| Вердикты 4 клипов `pass` | `art/pipeline-candidates/<ASSET_ID>/evidence/acceptance-anim/<YYYYMMDD>-r<N>/<Clip>/card.json` × 4 (`references/animation-vfx-sfx.md`, путь карточки клипа) | то же для каждой из четырёх карточек |
| Look-dev run | `<YYYYMMDD>-h2-lookdev/export/SK_<Key>_H2LD.fbx`, `SM_<Key>_H2LD_Base.fbx`, `textures/T_<Key>_H2LD_2K_*`, `T_<Key>_H2LD_TeamAccent_2K.png`, LUT `.dds` | отчёты `reports/ld-*`, `ld-team-*` есть (HANDBOOK §4.4) |
| Bake run | `<YYYYMMDD>-h2-bake/export/SK_<Key>_H2.fbx` | нужен для канонического скелета (§4.1 шаг 3) |
| Клипы | `<YYYYMMDD>-h2anim/export/AM_<Key>_{Idle,LungeAttack,HitReact,DeathSettle}.fbx` | validate PASS (HANDBOOK §4.5) |
| Source-spec этапа 2 | `art/pipeline-candidates/<ASSET_ID>/source-specs/tripo-<task8>-h2.json`, `source_id` = `tripo-<task8>-h2` (`references/tripo3d-stages.md`, шаг «Source-spec») | файл есть, `source_id` совпадает с `--primary-source` §4.1 шаг 4 |
| Экспорт | все FBX — только пресет `UM_FBX_v1` через `candidate_build/core.py` | HANDBOOK §2.2; FBX из `blender/ASSET-MEDUSA-001/build_tripo_medusa.py` (не в git, `SKEL_Medusa`, кость `weapon`) не принимать (HANDBOOK §1) |
| Имя слота | `materials.atlas` профиля H2 bake (`st_rig.py:219-220`), например `M_Medusa_H2_Atlas` | ue-import сверяет слоты с отчётом сборки (`tripo_pipeline.py:2731`, check `skeletal_material_slots`); шаблон для нового — `M_<Key>_H2_Atlas` (решение скилла) |
| Подставка без просвета | — | `python tools/tripo-pipeline/review/base_seethrough.py --out $E/base-seethrough.json <Key>=<lookdev run>/export/SM_<Key>_H2LD_Base.fbx,<lookdev run>/export/SK_<Key>_H2LD.fbx` → `with_figure` в пороге HANDBOOK §8 |
| Регистрация этапов 3 и 6 | `references/new-character-registration.md` §3 (Р3-1…Р3-4) и §4 (Р6-1…Р6-4) | проверки этих таблиц PASS |
| Реестр этапа 0 | запись `<ASSET_ID>` в `docs/art-pipeline/asset-registry.json` | см. §7.1 |

Текстуры в UE — по таблице HANDBOOK §2.4 (BC sRGB; N DirectX, `flip_green=false`; ORM = R AO / G Roughness /
B Metallic, не RM; MatID, Edge, TeamAccent, LUT). Факты по существующим героям, которых нет в хендбуке (проверено
`ls Content/PipelineCandidates/*/*/Textures` и профилями 2026-10-09):

- суффикс `_2K` в имени uasset опускается: `T_Medusa_H2LD_BC`;
- карта кромки называется по-разному: `T_Medusa_H2LD_Edge` и `T_Harpy_H3LD_Edge`, но `T_KingArthur_H2LD_EdgeMask` и
  `T_Merlin_H2LD_EdgeMask`; имя берётся из профиля импорта и сверяется `ls` папки;
- LUT назван коротким ключом: `T_UM_MatLUT_Arthur` (не `KingArthur`);
- 2048² — только для карт фигуры. Подставка Harpy имеет свои карты `T_Harpy_H3LD_Base_{BC,N,ORM}` 1024²
  (`harpy-h3ld-lookdev-ue-import.json:248`, `"px": [1024, 1024]`);
- у Merlin есть отладочные `T_Merlin_H2LD_ZoneID_Debug`, `ZoneLUT_Debug` и `MI_Merlin_H2LD_DebugZones`. Это
  история look-dev, новому герою они не нужны.

## 3. Профили (шаг 7.2)

Оба файла новые. Закоммиченный профиль не правится, новая версия — новый файл (HANDBOOK §0.1). Каждый ключ надо
пройти вручную: значение «как у Medusa» без проверки — дефект.

### 3.1 Профиль импорта `$P`

Профиль `skeletal-adopt` — копия
`art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2ld-lookdev-ue-import.json`.

| Ключ | Что задать |
|---|---|
| `profile_id`, `asset_id`, `status: "proposed"`, `status_note`, `derived_from` | свои; в `derived_from` — профиль Medusa и свои профили bake/look-dev |
| `candidate.dir`, `bake_profile`, `bake_profile_id` | look-dev run и его профиль |
| `candidate.fbx.skeletal`, `candidate.fbx.base` | `export/SK_<Key>_H2LD.fbx`, `export/SM_<Key>_H2LD_Base.fbx` |
| `candidate.textures` | 2K-карты look-dev run (BC, N, ORM, TeamMask, MatID, Edge) |
| `candidate.library_inputs.LUT`, `.TeamAccent` | `path` + `sha256` LUT и `T_<Key>_H2LD_TeamAccent_2K.png`. Первый импорт — LUT look-dev run как есть (итерация 0) |
| `armature.bones` | 16 базовых костей + кость оружия своей стороны (WEAPON_BONE заявки) или без неё при `null` (HANDBOOK §2.6) |
| `scale.figure_height_m`, `top_part` | FIGURE_HEIGHT_M заявки; часть с верхом фигуры (не оружие) |
| `meshes.base` | объект подставки, `footprint_m`, pivot |
| `axes` | `blender_front -Y`, `expected_ue_front +X`, сторона оружия по WEAPON_HAND |
| `sockets` | `Head` на `head`, `location_uu: null`; `Weapon` на кости оружия `(0,0,0)`. При `WEAPON_BONE: null` сокет `Weapon` ставится на кость точки удара из поля `WEAPON_SOCKET_BONE` заявки и записывается в профиль: у Harpy это `foot.R` (`harpy-h3ld-lookdev-ue-import.json:123-126`), а контракт говорит про кисть (`rig-contract.json` → `skeletons.UM_HUMANOID_17_v2.characters.Harpy.note`) — расхождение открыто (HANDBOOK §2.7). Сокет `Head` обязателен: без него фигура выпадает из evidence-съёмки (`S08FlowGameMode.cpp:5071-5074`, `DoesSocketExist(TEXT("Head"))`). Сокет `Weapon` нужен и проверке `verify` (§3.2: клип без сокета `Weapon` не проходит) |
| `expectations` | треугольники по частям и кости из `ld-fbx-report.json` look-dev run |
| `ue.skeletal_asset`, `base_asset` | `SK_<Key>_<Stage>`, `SM_<Key>_<Stage>_Base` (UE_NAMES) |
| `ue.target_skeleton` | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton` |
| `ue.masters` | фигура `/Game/UM/Materials/v2/M_UM_Figure_v2` в текущей ревизии (история — `docs/art-pipeline/material-library/m-um-figure-v2.md` и `git log`), подставка `/Game/UM/Materials/M_UM_BaseMarker` |
| `ue.figure_instance`, `base_instance`, `team_instances` | `MI_<Key>_<Stage>`, `MI_<Key>_<Stage>_Base`, `MI_<Key>_<Stage>_{team}`, `MI_<Key>_<Stage>_Base_{team}`. Игра грузит `MI_<Key>_<Stage>_P1/_P2` и `…_Base_P1/_P2` (`S08HeroesV2.cpp:138-145` `BodyMaterialPath`, `PedestalMaterialPath`; `S08Team.h:21`) |
| `ue.teams`, `team_color_mode` | палитра P1/P2 HANDBOOK §2.9; `none` (краситель — TeamAccent) |
| `ue.figure_parameters` | `TeamDyeGain`, `TeamDyeCeiling` по правилу `docs/art-pipeline/material-library/team-accent.md` из `ld-team-accent-report.json` своего run |
| `ue.folder_note` | `run with: ue-import --ue-folder /Game/PipelineCandidates/<Key>/<Stage>` |
| `ue.reimport_*` | **не копировать.** Это история look-dev Medusa, CLI эти блоки не читает (grep `reimport_` по `tripo_pipeline.py` пуст) |

### 3.2 Конфиг съёмки и сверки `$V/review-config.json`

Его читают `ue_hero_lookdev.py verify` (§4.1 шаг 6) и `ue_hero_lookdev.py review` (§4.3). Образцы:
`art/pipeline-candidates/ASSET-MEDUSA-001/20260930-h2ld-ldc-ue/review-config.json` (оружие слева) и
`art/pipeline-candidates/ASSET-MERLIN-001/20260930-h2ld-ldc-ue/review-config.json` (оружие справа). Формат описан в
docstring `tools/art/material_library/ue_hero_lookdev.py:22-37`. Блок `verify` обязателен: `cmd_verify` читает его
без проверки (`ue_hero_lookdev.py:581-610`), без блока команда падает с `KeyError`.

| Ключ | Что задать |
|---|---|
| `hero` | KEY |
| `note` | своя строка: что за съёмка, дата |
| `run_dir` | `$R` (run импорта §4.1 шаг 4) |
| `concept.front\|side\|back` | принятые виды этапа 1 `art/imagegen/concept-<content-key>-codex/<content-key>-<view>.png` |
| `concept_zones` | медианы концепта по классам: `<lookdev run>/reports/measure-report.json` (образец Medusa) или файл команды `ue_hero_lookdev.py concept` (образец Merlin, `concept-classes.json`) |
| `side_camera` | `"+X"`, если на виде side лицо смотрит влево; `"-X"`, если вправо (`ue_hero_lookdev.py:242-246`) |
| `teams` | `["P1", "P2"]` |
| `variants`, `base_mi` | свои MI: `neutral`, `P1`, `P2` (и отладочный `debug`, если есть) из `/Game/PipelineCandidates/<Key>/<Stage>/Materials/` |
| `zones` | классы MatID своего героя: значения `lookdev.zones.class_of` профиля look-dev (HANDBOOK §4.4) |
| `key_zones`, `tolerance_zones`, `never_dye_zones`, `anchor_zone` | подмножества `zones` своего героя. `anchor_zone` задать обязательно: без него берётся `"linen"` — класс Medusa (`ue_hero_lookdev.py:831`). `never_dye_zones` — классы, которые TeamAccent не красит (`team_accent` профиля look-dev) |
| `render_gates` | гейты своих классов или `null` (у Merlin `null`; у Medusa гейт класса `legacy_bake`) |
| `tolerance` | образец HANDBOOK §4.6 п.6: `luma_ratio 0.15`, `hue_deg 12.0`, `sat 0.1` |
| `min_px`, `reading_bias_ev`, `restore_level` | как у образцов (`150`, `-0.75`, `/Game/S08/S08Arena`) — это настройки съёмки, не героя |
| `verify.skeleton`, `folder`, `hero_root`, `clips_folder` | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton`, `/Game/PipelineCandidates/<Key>/<Stage>`, `/Game/PipelineCandidates/<Key>`, `/Game/PipelineCandidates/<Key>/H2Anim` |
| `verify.height_uu` | знаменатель доли смещения клипа (`measure_clips.py:117`). Образцы расходятся: Medusa `55.0`, Merlin `49.42` (= его `BoundsTopUU`). Решение скилла: верх bounds меша из `ue-import-report.json` |
| `verify.default_mi_key` | `team:figure:P1` |
| `verify.expect.bones`, `bone_names` | 18 имён UE с костью 0 и костью оружия (`weapon_L` у Medusa, `weapon_R` у Merlin) или 17 без кости оружия при `WEAPON_BONE: null`; сверка с `armature.bones` §3.1 (HANDBOOK §2.6) |
| `verify.expect.triangles` | треугольники LOD0 фигуры из `ld-fbx-report.json` своего look-dev run (у Medusa 43 054, у Merlin 33 967 — не копировать) |
| `verify.expect.base_uv_channels`, `clips` | `2`, `4` |
| `verify.textures` | настройки карт по HANDBOOK §2.4; имя ключа кромки — `Edge` (как в образцах) |
| `verify.instances` | обязателен (`ue_hero_lookdev.py:643`): родитель, текстуры, скаляры и переключатели своих MI — пути `<Key>/<Stage>`, свои `T_UM_MatLUT_<короткий ключ>`, `T_<Key>_<Stage>_Edge` или `_EdgeMask` (§2), `TeamDyeGain`/`TeamDyeCeiling` из §3.1, цвета P1/P2 по HANDBOOK §2.9 |
| `verify.clips_reference` | `<h2anim run>/reports/ue-measure-clips.json` — его пишет §4.1 шаг 5 (`h2anim_ue.py:166`) |

## 4. Импорт (шаг 7.3) — HANDBOOK §4.6 с блокировкой

### 4.1 Команды

```bash
mkdir -p "$E" "$W" "$V"
# 1. Мастер-материалы (повтор ничего не меняет; PASS для figure, base_marker, game_layer)
$L --step "<Key> um_masters" -- python tools/tripo-pipeline/um_masters.py --backend mcp build --report $E/um-masters-report.json
# 2. Снимок до: открытый уровень записан, 0 dirty-пакетов
$L --step "<Key> snapshot before" -- python tools/tripo-pipeline/review/ue_content_snapshot.py $E/snapshot-before.json \
    --extra-folder /Game/ArtTests --extra-folder /Game/S08
# 3. Канонический скелет из SK_<Key>_H2.fbx спеки → /Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton (+ SK_<Key>)
$L --step "<Key> skeleton" -- python tools/tripo-pipeline/anim/h2anim_ue.py skeleton $S
# 4. Меш на канонический скелет (CLI 0.8.0, профиль skeletal-adopt)
$T init --run-dir $R --asset-id <ASSET_ID> --primary-source tripo-<task8>-h2 \
    --primary-role h2-parts-glb --export-basename SK_<Key>_<Stage> \
    --profile skeletal-adopt --build-profile $P --run-id <YYYYMMDD>-h2ld-ue-import
$T register-source --run-dir $R --spec art/pipeline-candidates/<ASSET_ID>/source-specs/tripo-<task8>-h2.json
$T run --run-dir $R                                                   # preflight + adopt, без UE
$L --step "<Key> ue-import" -- $T --backend mcp ue-import --run-dir $R --ue-folder /Game/PipelineCandidates/<Key>/<Stage>
$L --step "<Key> ue-import repeat" -- $T --backend mcp ue-import --run-dir $R   # повтор → skipped (идемпотентность)
python -c "import json,sys; r=json.load(open(sys.argv[1],encoding='utf-8')); print(r['status'], r['passed'], [k for k,v in r['checks'].items() if not v.get('passed')])" $R/reports/ue-import-report.json
#    ожидается: technically_imported True []
# 5. Клипы (animation-only, старый клип удаляется) и замеры → <h2anim run>/reports/ue-import-clips.json, ue-measure-clips.json
$L --step "<Key> clips import" -- python tools/tripo-pipeline/anim/h2anim_ue.py import $S
$L --step "<Key> clips measure" -- python tools/tripo-pipeline/anim/h2anim_ue.py measure $S
# 6. Сверка импорта: скелет, кости, LOD/треугольники/UV, слоты, текстуры, MI, дубли, клипы на меше (блокировку берёт сам)
python tools/art/material_library/ue_hero_lookdev.py verify --config $V/review-config.json --out $V/review/verify --tag v1
# 7. Снимок после
$L --step "<Key> snapshot after" -- python tools/tripo-pipeline/review/ue_content_snapshot.py $E/snapshot-after.json \
    --compare $E/snapshot-before.json --extra-folder /Game/ArtTests --extra-folder /Game/S08
```

`--ue-folder` обязателен. Без него CLI кладёт ассеты в `/Game/PipelineCandidates/<Asset>/<run_id>` (справка
`ue-import --help`), а игра ищет `/Game/PipelineCandidates/<Key>/<Stage>` (`S08HeroesV2.cpp:126` `StageRoot`).

`--primary-source`, `--primary-role` и `--export-basename` повторяют все четыре принятых импорта (`config` в их
`manifest.json`): Medusa `tripo-40c4d1cd-h2`, `h2-parts-glb`, `SK_Medusa_H2LD`; King Arthur `tripo-c24eeff0-h2`,
`SK_KingArthur_H2LD`; Merlin `tripo-de0654b5-h2`, `SK_Merlin_H2LD`; Harpy (второе поколение) `tripo-bca735a3-h3`,
`h3-parts-glb`, `SK_Harpy_H3LD`. `--primary-source` равен `source_id` source-spec этапа 2, файл source-spec
называется так же (`ASSET-MEDUSA-001/source-specs/tripo-40c4d1cd-h2.json`; `references/tripo3d-stages.md`). Без
`--export-basename` CLI подставит `<ASSET_ID>_h2-parts-glb` (`tripo_pipeline.py:3542`). Если `register-source`
получит не тот файл, `run` откажет: «source … is not registered» (`tripo_pipeline.py:931-934`).

Параметры импорта (legacy `FbxFactory`, `ImportNormals`, Nanite выкл., `import_uniform_scale 1.0`,
`import_materials=false`, без physics asset, morph targets, LOD и коллизий, Generate Lightmap UVs у подставки
выкл.) ставит CLI по профилю. Руками их не менять (HANDBOOK §2.1, §2.5, §4.6).

### 4.2 Что проверить после импорта

- [ ] `ue-import-report.json`: `status = technically_imported`, `passed = true`, список непрошедших checks пуст. Среди
      checks: `bone0_is_armature_object_node`, `skeleton_is_canonical_target`, `front_axis_as_fbx_preset`,
      `figure_height_as_profile`, `skeletal_material_slots`, `sockets_weapon_head`, `uv_channels_as_profile`,
      `textures_size_colour_space_compression`, `um_instances_parent_textures_values`, `no_numbered_duplicates`.
- [ ] Скелет: число костей в UE и имена `_L/_R` по HANDBOOK §2.6 (кость 0 = `SKEL_UM_Humanoid`; кость оружия
      по WEAPON_BONE или её нет).
- [ ] Клипы (`reports/ue-*.json` от `measure`): кадр 0 = ref pose, кость 0 неподвижна, масштаб 1,0, длительности по
      HANDBOOK §2.8 (Idle — IDLE_SECONDS заявки), сокеты `Weapon`/`Head` против цели ± 0,05 uu.
- [ ] `ue_hero_lookdev.py verify`: `verify-v1.json` → `passed: true` (все checks, включая
      `h2anim_clips_play_on_mesh` и `nothing_dirty`).
- [ ] Снимок после: `protected_unchanged: true`, добавлены только ассеты этого героя.
- [ ] Папка совпадает с UE_NAMES заявки: `ls unreal/Unmatched/Content/PipelineCandidates/<Key>/<Stage>/{Meshes,Materials,Textures}`,
      `…/<Key>/Rig`, `…/<Key>/H2Anim`.
- [ ] Редакторные кадры (по желанию, для глаз):
      `$L --step "<Key> frames" -- python tools/tripo-pipeline/anim/h2anim_ue.py frames $S --clips=Idle` (по клипу за
      вызов), затем `python tools/tripo-pipeline/anim/h2anim_ue.py sheet $S` (без редактора). Это диагностика,
      а не приёмка K1/K2 (`h2anim_ue.py:28`).

### 4.3 Look-dev съёмка в редакторе (шаг 7.4)

```bash
python tools/art/material_library/ue_hero_lookdev.py review --config $V/review-config.json --out $V/review/r1 --tag r1
```

Конфиг — §3.2. Инструмент генерический: имя героя и все пути берутся из конфига, а не из списка в коде. Почему не
`ue_h5cb1.py review` — HANDBOOK §4.6 п.6: его `--hero` берёт только четырёх зашитых героев (`ue_h5cb1.py:655`).

Кадры редактора не несут отпечатка RENDER и в приёмку не идут (`ue_hero_lookdev.py:37`). Они нужны для решения по
материалу. Если зоны вне допуска, итерация идёт через новую LUT
(`ue_hero_lookdev.py lut --overrides <json> --out <dds>`), новый файл профиля `$P` (с новым `sha256` LUT) и повторный
импорт по §4.4. По лёгкому режиму AGENTS.md («Iteration speed») итераций не больше 3; съёмка каждой — новым `--tag`
(`r2`, `r3`). Силуэт, пропорции и палитра здесь не правятся: это возврат на этап 1 или 2
(`references/acceptance-and-blender.md`).

### 4.4 Повторный импорт после доработки

Новый run-каталог CLI откажет импортировать в папку, где лежат ассеты прежнего run: код 3, «holds assets this run did
not create… use another --ue-folder» (`tripo_pipeline.py:2035-2040`). Другая папка сломает пути `Specs()`. Поэтому
ассеты прежнего run удаляются скриптом, без ручных кликов, тем же MCP-вызовом `asset delete`, которым CLI удаляет
свои ассеты (`ue_delete_owned`, `tripo_pipeline.py:1993-2016`; клиент `tools/tripo-pipeline/review/ue_live.py`,
`Ue().call`). Порядок (на новом герое не проверялся):

1. Снимок до удаления:
   `$L --step "<Key> snapshot before re-import" -- python tools/tripo-pipeline/review/ue_content_snapshot.py $E/snapshot-before-r<N>.json --extra-folder /Game/ArtTests --extra-folder /Game/S08`.
2. Удалить под `$L` только ассеты из списка `stages["ue-import"].ue_owned_assets` в `manifest.json` прежнего run и
   только внутри `/Game/PipelineCandidates/<Key>/<Stage>/`. Канонический скелет `Rig/` и клипы `H2Anim/` в этот список
   не входят и остаются. Сначала MI (дети раньше родителя), потом меши, потом текстуры — как ранги `UE_DELETE_RANK`
   (`tripo_pipeline.py:1989-1990`):

```bash
OLD=art/pipeline-candidates/<ASSET_ID>/<прежний run импорта>
$L --step "<Key> delete previous import" -- python -c "
import json, sys
sys.path.insert(0, 'tools/tripo-pipeline/review')
from ue_live import Ue
root = '/Game/PipelineCandidates/<Key>/<Stage>/'
own = json.load(open(sys.argv[1] + '/manifest.json', encoding='utf-8'))['stages']['ue-import']['ue_owned_assets']
own = [a for a in own if a.startswith(root)]
rank = lambda a: (0 if '/Materials/' in a else 1 if '/Meshes/' in a else 2, -len(a))
ue = Ue()
for a in sorted(own, key=rank):
    if not ue.call('asset', 'delete', {'path': a}):
        sys.exit('UE refused to delete ' + a)
    print('deleted', a)
print('left', ue.call('asset', 'find_assets', {'folder_path': root.rstrip('/'), 'name': '', 'recursive': True}))
" "$OLD"
```

   Ожидается: `left` без ассетов. Что-то осталось — это чужие ассеты в целевой папке, стоп по HANDBOOK §0.3 п.5.
3. Новый run-каталог `<YYYYMMDD>-h2ld-ue-import-r<N>` с новым профилем, затем шаги 4, 6 и 7 §4.1 (снимок после — с
   `--compare $E/snapshot-before-r<N>.json`). Шаг 5 (клипы) — только если менялись клипы.
4. Последствия для шагов 7b:
   - MIC растворения `MI_<Key>_<Stage>_P{1,2}_Dissolve` — дети удалённых `MI_<Key>_<Stage>_P1/_P2`, у них пропал
     родитель. `de011.py apply` ставит родителя заново (`tools/art/de011/de011_apply_ue.py:68-80`). Если 7b ещё
     впереди, это делает обычный шаг §5 п.1; если 7b уже пройден — повторить `de011.py apply` и автотесты §5 п.4.
     Пока у MIC нет родителя, редактор может пометить его dirty (не проверено): вручную не сохранять, записать в
     README evidence; `de011.py apply` восстанавливает связь и сохраняет MIC.
   - Если шаг 5 повторялся, `h2anim_ue.py import` удалил клипы вместе с notify `Contact` (`h2anim_ue.py:13-15`).
     Тогда повторить `de010.py apply` и автотесты §5 п.4.

## 5. Подключение S08 (шаг 7.5) — обязательно для героя и помощника

Без подключения игра молча показывает старую фигуру. `AS08FighterActor::ApplyHeroV2` (`S08FighterActor.cpp:849-889`)
грузит меш, подставку, MI тела и подставки команды и 4 клипа на скелете меша. Откат на старую фигуру с трассой
`ARTPREVIEW heroesV2 fighter=<id> missing=<путь> fallback=legacy` (`:882`) вызывает только отсутствие меша (или его
скелета), подставки, MI команды или клипа Idle (`:862-874`). Пропавший LungeAttack, HitReact или DeathSettle отката не
даёт: фигура стоит, а трасса пишет `clips=N/4` (`:911`) и `ARTPREVIEW anim fighter=<id> clip=… missing=1` (`:934`).
Поэтому чек-лист требует `clips=4/4`.

Правки без сборки C++ — CUE-таблица, `DefaultGame.ini`, `S08FighterNames.json`, варианты фикстур (Р7-11), `git add -f` —
можно сделать ещё в 7a (SKILL.md, 7a п.3). Всё остальное в разделе — подэтап 7b (§1 п.4).

1. **Строки этапа 7 из `references/new-character-registration.md`** (§5 там) — все, с их проверками:
   - `de010.py` `HEROES` (Р7-1) и `de011.py` `CAPTURE_LOOKS` (Р7-2), затем оба `apply` под `$L` (команды — там же,
     §5.1). Порядок: после импорта клипов и MI тела (§4);
   - таблица `Specs()` и автотесты `S08HeroesV2Tests.cpp` (счётчик «four heroes» `:110`, имена, отношение
     помощник/герой, `WantMs`, `WantSeconds`), `S08AudioBank` и его тесты (Р7-3…Р7-5);
   - CUE-таблица (Р7-6), три строки `+DirectoriesToAlwaysCook` (`<Key>/<Stage>`, `<Key>/Rig`, `<Key>/H2Anim` в
     `unreal/Unmatched/Config/DefaultGame.ini`; у Harpy стадия `H3LD`, анимации в `H2Anim`), `S08FighterNames.json`
     (Р7-7, Р7-8), `git add -f` (Р7-10);
   - варианты bench-фикстур обеих досок (Р7-11, генератор Д-2; без них нового бойца нет на кадрах — §6.2) и запись
     `HEROES` листа клипов (Р6-4, Д-3).
2. **Строка `Specs()` — все 11 полей `FHeroSpec`** (`unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h:99-119`):

   | Поле | Откуда |
   |---|---|
   | `FighterName` | FIGHTER_NAME заявки (`Find()` сравнивает без учёта регистра; «Harpies» — имя бойца, `Harpy` — ключ) |
   | `Key`, `Stage` | KEY, стадия UE_NAMES |
   | `bHero` | GAME_ROLE: hero → `true`, sidekick → `false`. От него зависят растворение 0,5/0,4 с (`S08HeroesV2.h:202-204`) и автотест «герой выше помощника» (HANDBOOK §2.10, отношение помощник/герой) |
   | `BudgetUU`, `BudgetMinUU`, `BudgetMaxUU` | FIGURE_HEIGHT_M × 100 и FIGURE_HEIGHT_RANGE_M × 100 |
   | `FigureTopUU` | верх фигуры без оружия, измеренный в UE (`figure_height_as_profile` / `skeletal_top_as_build` отчёта ue-import) |
   | `BoundsTopUU` | верх bounds меша с оружием (тот же отчёт) |
   | `IdleSeconds` | IDLE_SECONDS заявки = длина `AM_<Key>_Idle` |
   | `LungeContactFrame` | LUNGE_CONTACT_FRAME заявки = кадр контакта спеки h2anim |

   `FigureScale = BudgetUU / FigureTopUU` зажат в [0,5; 2] (`S08HeroesV2.cpp:121-124`). Автотест требует, чтобы верх
   фигуры попадал в бюджет с точностью 1 % (HANDBOOK §2.10).
3. **Клипы и notify `Contact`.** Клипы играются кодом напрямую (`AS08FighterActor::PlayHeroClip`,
   `S08FighterActor.cpp:929`). AnimMontage, BlendSpace и ABP в проекте нет, их не добавлять. Notify `Contact`
   **обязателен** для автотеста `Unmatched.S08.HeroesV2.Contact`: он требует ровно один `US08ContactAnimNotify` на
   LungeAttack каждого героя из `Specs()` и ни одного на остальных клипах (`S08HeroesV2Tests.cpp:507-548`, проверка
   «one Contact notify» — `:540`). Notify ставит `de010.py apply` (регистрация Р7-1). Рантайм без notify не ломается:
   время контакта берётся из `ProfileContactSeconds` (`S08HeroesV2.cpp:167`, `:178-180` `ContactSeconds`), но тест
   падает и этап не проходит. Каждый повторный импорт клипов удаляет клип вместе с notify — тогда `de010.py apply`
   повторить (§4.4 п.4). Для кадров редактора в 7a notify можно поставить задачей живого редактора
   (`references/animation-vfx-sfx.md`, раздел «Notify `Contact` для нового героя»); шаг `de010.py apply` в 7b это не
   отменяет.
4. **Сборка и автотесты:**

   ```bash
   node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development \
       -Project="$ROOT/unreal/Unmatched/Unmatched.uproject" -WaitMutex -NoXGE -MaxParallelActions=4
   #   EXIT=0 ничего не доказывает: в выводе искать "Result: Succeeded", нет "Result: Failed" (HANDBOOK §4.7).
   #   "Unable to build while Live Coding is active" — гейт §1 п.4, не обходить
   node tools/s08/run-ue-tests.cjs "Unmatched.S08" $W/ue-tests-s08.log
   #   ожидается "TEST COMPLETE. EXIT CODE: 0" и ни одной строки "Test Completed. Result={Fail}";
   #   в логе PASS у HeroesV2.Contact (notify на LungeAttack) и HeroesV2.Dissolve (MIC растворения)
   python tools/s08/cue_contract/cue_contract.py validate-table      # если регистрация меняла cue-table.json
   ```

   `$ROOT` — корень текущего checkout (§1): в worktree это worktree, а не главный checkout. C++ изменился, поэтому
   UE-тесты обязательны и в лёгком режиме (AGENTS.md «Iteration speed»). Прогоняется весь набор `Unmatched.S08`, а не
   только `HeroesV2`: новый боец меняет и другие наборы (ArtLook, Audio, bench-фикстуры).

## 6. Упаковка и кадры в игре (шаги 7.6–7.7)

### 6.1 Одна упаковка на изменение

```bash
# только если регистрация добавила или переименовала Config/**.json (AGENTS.md «Packaging trap»):
touch unreal/Unmatched/Source/Unmatched/Unmatched.Build.cs
node tools/s08/build-editor.cjs Unmatched Win64 Development \
    -Project="$ROOT/unreal/Unmatched/Unmatched.uproject" -WaitMutex -NoXGE -MaxParallelActions=4
# упаковка (Development, cook + stage + pak; ставит BuildStamp.json):
powershell -NoProfile -ExecutionPolicy Bypass -File tools/s08/package-client.ps1 -Log $W/package.log
#   -SkipBuild — если сборку UnmatchedEditor внутри BuildCookRun блокирует Live Coding чужого редактора
#   (package-client.ps1:2-4). Тогда сначала собрать игровой target командой build-editor.cjs Unmatched … выше
#   (она нужна и без нового JSON), затем package-client.ps1 -SkipBuild. Автотесты §5 п.4 это не заменяет.
#   Игровой target никогда не собирать с -NoLiveCoding: пакет падает при старте (package-client.ps1:40-52, HANDBOOK §4.7)
```

Упаковка делается один раз на изменение (AGENTS.md «One package per change»). Повторные пакеты и бенчи ради
стоимости запрещены: стоимость меряется только там, где её требует карточка, одним прогоном. Если она в пороге,
число записывается и работа идёт дальше (AGENTS.md «No cost optimizations within budget»).

Проверка, что кукер взял ассеты. Ассеты лежат в IoStore-контейнере, поэтому листинг берётся из `.utoc`, а не из
`.pak`: на `.pak` grep даёт 0 строк, на `.utoc` — пути (проверено 2026-10-09 на Medusa):

```bash
"C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealPak.exe" \
    "$(cygpath -w unreal/Unmatched/Saved/StagedBuilds/Windows/Unmatched/Content/Paks/Unmatched-Windows.utoc)" -List \
    | grep -E "PipelineCandidates/<Key>/(<Stage>|Rig|H2Anim)/|Dissolve/MI_<Key>_"
```

### 6.2 Кадры `-Bench`: только реальные доски

Приёмочные кадры дают только свежий `-Bench` packaged-клиента на Marmoreal и Sarpedon original (AGENTS.md «Board
scenes and heroes»; синтетические доски не считаются).

Канонические фикстуры (`tools/art/render/live_tune.py` `FIXTURES`) содержат только нынешних бойцов, поэтому новый
боец снимается на своих вариантах фикстуры — файлах `unreal/Unmatched/Config/Bench/S08Bench{Marmoreal,Sarpedon}-<Key>.json`
(регистрация Р7-11, генератор и правила — `references/new-character-registration.md` §2 Д-2). Их выбирает флаг
`bench --fixture` (`live_tune.py bench --help`). Сначала сухой прогон: он печатает командную строку и откуда клиент
возьмёт файл, ничего не запуская:

```bash
python tools/art/render/live_tune.py bench --map marmoreal --fixture S08BenchMarmoreal-<Key>.json \
    --views K1+K2x1.6+K2x2.5 --out $W/bench-marmoreal --packaged --extra=-BenchFocusFighter=<Key> --dry-run
#   fixture.source: pak (файл в манифесте staged-сборки) | loose (абсолютный путь checkout, без перепаковки)
python tools/art/render/live_tune.py bench --map marmoreal --fixture S08BenchMarmoreal-<Key>.json \
    --views K1+K2x1.6+K2x2.5 --out $W/bench-marmoreal --packaged --extra=-BenchFocusFighter=<Key>
python tools/art/render/live_tune.py bench --map sarpedon  --fixture S08BenchSarpedon-<Key>.json \
    --views K1+K2x1.6+K2x2.5 --out $W/bench-sarpedon  --packaged --extra=-BenchFocusFighter=<Key>
```

- `--fixture` с доской другой карты, несуществующий файл, путь с пробелом и `-BenchFixture=` внутри `--extra` дают
  код 2 до запуска. Трасса `BENCH FAILED fixture load <path>` (`S08FlowGameMode.cpp:8916`) — packaged-клиент не
  прочитал loose-файл (это чтение живым прогоном ещё не подтверждено): путь пака из регистрации Д-2 (строка
  `RuntimeDependencies`, сборка игрового target, одна упаковка).

- `--views` и `--out` обязательны (`live_tune.py bench --help`). Каждый запуск ждёт `C:/tmp/unmatched-gpu.lock`.
  Пока открыта сессия live tune, `bench` ждёт её `stop`.
- В `--out` появятся `bench-<View>-1920x1080.png`, `bench.trace.log`, `cmdline.txt`, `exit.txt`
  (`tools/art/render/LIVE-TUNE.md`). В имени файла точка вида заменяется на `p` (`S08LiveTune.cpp:307`,
  тест `S08LiveTuneTests.cpp:169-170`): `bench-K1-1920x1080.png`, `bench-K2x1p6-1920x1080.png`,
  `bench-K2x2p5-1920x1080.png`.
- Без флага фокуса K2 наводится на героя зрителя фикстуры (`S08FlowGameMode.cpp:8926`,
  `F.OwnerId == BenchViewerId && F.bIsHero`); в канонических фикстурах это Medusa. Флаг `-BenchFocusFighter=<Key>`
  (`S08FlowGameMode.cpp:8960`) находит бойца по `Key` через `Specs()` и `FighterName`
  (`Fx/S08FlowGameModeAbilityFx.cpp:333-349`) и пишет трассу `BENCH focus fighter=<id> (<Key>)`. Если бойца на доске
  нет, трасса `BENCH focus error=fighter '<Key>' not on this board`, и K2 остаётся на прежнем герое — кадр не
  считается. K1 от фокуса не зависит. Флаг `-BenchClipPose` для этой цели не брать: он замораживает все фигуры в позе
  и меняет имена PNG на `bench-<View>-<clip>-f<NN>-1920x1080.png` (`S08FlowGameModeFigures.cpp:128-130`).
- Растворение без смерти в бою проверяется отдельным запуском с `--extra=-BenchDissolve=0.5`. Это проверка, не
  приёмочный кадр.
- Игровые листы клипов K1/K2 строит
  `python tools/art/anim/clip_review_sheet.py run --packaged --heroes <Key> --fixture marmoreal=S08BenchMarmoreal-<Key>.json,sarpedon=S08BenchSarpedon-<Key>.json`
  и потом `sheet --cards <AN-… клипов героя>`. Нужна запись героя в `HEROES` этого инструмента (Р6-4, Д-3); новый
  герой — первым ключом `--heroes`, иначе K1 снимется на чужой фикстуре и `sheet` запишет проблему. Приёмка клипов
  описана в `references/animation-vfx-sfx.md` §11.

### 6.3 Проверки кадров и трасс

- [ ] **Каждый PNG открыт и осмотрен глазами** (Read). Доска — реальная карта. Задник: Marmoreal — нарисованный,
      Sarpedon — lit3d путь 1. Все фигуры — v2-модели, новый боец — новая модель, а не серая болванка, и на K2 крупно
      именно он. Подставка стоит на клетке и не проваливается (AGENTS.md «Look before you report»). Одних трасс мало.
- [ ] Отпечаток RENDER каждого кадра совпадает с эталоном. Аргумент `--shot` — имя файла с заменой точки на `p`:
      `python tools/art/render_fingerprint.py check --trace $W/bench-marmoreal/bench.trace.log --shot bench-K2x1p6-1920x1080.png`
      (так же для `bench-K1-…`, `bench-K2x2p5-…` и для Sarpedon) → код 0. Код 1 — кадр вне эталона
      `docs/art-pipeline/render-reference.json`, код 3 — для этого имени нет отпечатка (`render_fingerprint.py:33`,
      `EXIT_OK, EXIT_OFF, EXIT_MISSING = 0, 1, 3`). Такой кадр не считается (AGENTS.md «Unreal GPU load»). Сама
      команда `bench` отпечаток не проверяет (`live_tune.py` `cmd_bench`).
- [ ] `grep ARTLOOK bench.trace.log`. Ожидается `ARTLOOK art=1 source=default heroes=v2 …` и строка доски:
      `ARTLOOK board=marmoreal-original backdrop=paste(default)` или
      `ARTLOOK board=sarpedon-original backdrop=lit3d(default)` (`S08ArtLook.cpp:129`, `:145`).
- [ ] `grep "BENCH focus" bench.trace.log` → `BENCH focus fighter=<id> (<Key>)`, нет `focus error`.
- [ ] `grep "ARTPREVIEW heroesV2" bench.trace.log`. Для нового бойца должна быть строка
      `fighter=<id> mesh=…/SK_<Key>_<Stage> … clips=4/4 …` (`S08FighterActor.cpp:911`). Строк `missing=` и
      `fallback=legacy` нет ни у одного бойца (`:882`); нет `ARTPREVIEW anim fighter=<id> clip=… missing=1` (`:934`).
- [ ] Запуск с `-BenchDissolve`: `ARTPREVIEW dissolve bench fighter=<id> … mi=MI_<Key>_<Stage>_P<n>_Dissolve`, не
      `mi=missing` (`S08FighterActor.cpp:843-845`). Без MIC фигура исчезает рывком: трасса
      `death dissolve=missing fallback=hide` (`:1308-1311`).
- [ ] Лист для делегированной приёмки (ВР-17): K1 и K2 обеих досок, в цвете и в сером:
      `python tools/art/visual/sheet.py <ASSET_ID> --inputs <PNG обеих досок> --out $E/game-sheet`
      (цвет, серый Rec.709, дейтеранопия). Лист открыть и осмотреть.

### 6.4 Evidence

- PNG остаются в `$W` (вне git). В `$E` идут JPEG 1200 px q92 и `*.evidence.json`:
  `python tools/tripo-pipeline/review/frames_to_jpeg.py --src $W/bench-marmoreal --out $E/bench-marmoreal --png-kept-at $W/bench-marmoreal`,
  то же для Sarpedon (HANDBOOK §8). Туда же — `bench.trace.log` (в git `*.log` игнорируется, поэтому копия как `.txt`,
  `tools/art/render/LIVE-TUNE.md`).
- `$E/README.md` — по шаблону HANDBOOK §9. В нём числа из отчётов, что не проверялось, отступления (таблица решений
  скилла во вступлении этого файла).

### 6.5 Замер стоимости: один прогон

Новый ассет добавляет меши и материалы, а это случай, когда замер цены нужен (AGENTS.md «Iteration speed», лёгкий
режим: «no render_bench cost run, unless the change adds lights, meshes, materials or FX»). Ровно один прогон на шаге
7.7 после упаковки, на варианте фикстуры Marmoreal с новым бойцом. Значение `--bench-fixture` — то, что сухой прогон
`live_tune.py bench --dry-run --fixture S08BenchMarmoreal-<Key>.json` напечатал в `-BenchFixture=` (абсолютный путь
при `source: loose`; путь `../../../Unmatched/Config/Bench/<файл>` относительно `Binaries/Win64` — только для файла
в паке, как в подсказке `render_bench.py run --help`):

```bash
python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --name <content-key>-stage7 \
    --out $E/bench --bench-fixture <значение -BenchFixture из сухого прогона>
```

Число записать в `$E/README.md`. Правка — только при превышении порога (ACC-022 60 FPS) или поломке; оптимизации в
пределах бюджета запрещены, повторных бенчей нет (AGENTS.md «No cost optimizations within budget»). Правка одного
параметра после приёмки — лёгкий режим, без бенча.

## 7. Реестры, статус, коммит, интеграция (шаг 7.8)

### 7.1 Два реестра — разведены

| Реестр | Когда | Что |
|---|---|---|
| `docs/art-pipeline/asset-registry.json` | запись создаётся на этапе 0, на этапе 7 обновляется | `status: "технически импортировано"`, `stage: "live-packaged-probe"` (словарь `vocabularies.stage`), слои и пути по образцу записи `ASSET-MEDUSA-001`. Проверка — `python tools/tripo-pipeline/validate_registry.py`. На 2026-10-09 он уже даёт FAIL на чужой ошибке (`sharedDependencies[UM-MASTERS]` sha256 `um-masters.json`), поэтому критерий такой: вывод до и после правки сравнён, новых ошибок нет (HANDBOOK §3.2 п.1, §8) |
| `docs/game-design/visual/03-asset-registry.csv` | этап 7 | строки по образцу `SK_Merlin_H2LD` и `AM_Merlin_<Clip>` (регистрация Р7-9; колонки `00-VISUAL-BRIEF.md` §4.7): `area=hero`, `ue_path=/Game/PipelineCandidates/<Key>/<Stage>/Meshes/SK_<Key>_<Stage>`, `rollback_flag=-S08HeroesLegacy` (общий флаг отката фигур v2, AGENTS.md «Rollback flags»; у нового персонажа блок-аута ART-003 нет, откат даёт серый Body — пометка из Р7-9), `link=<ASSET_ID>; AN-…`; 4 строки `AM_<Key>_<Clip>` (`area=anim`) |

Статус в 03 CSV задают правила ВР-RG07 и ВР-17 (`docs/game-design/visual/02-visual-design.md`, серия ВР-RG;
`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`):

- пока лист K1/K2 §6.3 не осмотрен — `status=технически импортировано`, `acceptance=нет`;
- когда карточки этапа 4 и всех клипов этапа 6 дали `pass`, а лист K1/K2 обеих досок в цвете и в сером осмотрен, —
  `status=художественно принято`, `acceptance=по делегированию <дата> (ВР-17): <путь листа>; <пути card.json>`.
  Формулировка «художественно принято, по делегированию» обязательна, без пометки этот статус ставит только
  пользователь. Это отступление от HANDBOOK §0 п.3 (вступление).

В `asset-registry.json` «художественно принято» ставить нельзя: валидатор требует акт
`docs/game-design/evidence/(ART|GD)-NNN/…/*.md` со строкой «Решение: принято» (`vocabularies.status`). Скилл такой акт
не пишет, поэтому запись остаётся «технически импортировано».

Если появились новые каталоги — строка в `docs/art-pipeline/DIRECTORY-MAP.md` (HANDBOOK §8).

### 7.2 Чек-лист сдачи этапа 7

```markdown
# <ASSET_ID> — этап 7 (UE и игра), <YYYYMMDD>

Run импорта: art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-h2ld-ue-import/
Профили (новые файлы): build-profiles/<content-key>-h2ld-lookdev-ue-import.json, <YYYYMMDD>-h2ld-ldc-ue/review-config.json
Карточки pass: evidence/acceptance/<…>/card.json; evidence/acceptance-anim/<YYYYMMDD>-r<N>/<Clip>/card.json ×4

- [ ] Вход §2: вердикты pass (validate_card.py код 0; у модели с кодом 3 — final.json пары с pass), FBX UM_FBX_v1, слот = materials.atlas, base_seethrough в пороге,
      source-spec tripo-<task8>-h2.json
- [ ] Среда: MCP :8123, каждая MCP-команда под ue_lock.py (ue_hero_lookdev — без обёртки), свои PID записаны
- [ ] init с --export-basename SK_<Key>_<Stage>; ue-import-report.json: technically_imported, passed, непрошедших
      checks нет; повтор → skipped
- [ ] Скелет Rig/SK_<Key>_Skeleton; кости по HANDBOOK §2.6; сокеты Weapon/Head ± 0,05 uu (или Weapon на кости удара при WEAPON_BONE null)
- [ ] Клипы H2Anim ×4: measure — кадр 0 = ref pose, кость 0 неподвижна, масштаб 1,0, длительности HANDBOOK §2.8
- [ ] review-config.json: каждый ключ пройден (verify-блок, zones, anchor_zone, side_camera — свои, не Medusa)
- [ ] ue_hero_lookdev verify: passed true; review — зоны в допусках (≤ 3 итерации, повторный импорт по §4.4)
- [ ] Снимок до/после: protected_unchanged: true
- [ ] 7b начат без GUI-редактора на checkout и без Live Coding; иначе — гейт SKILL.md §5 п.7, пакет пользователю
- [ ] Регистрация этапа 7 (references/new-character-registration.md) — все строки и их проверки PASS
- [ ] de010.py apply (notify Contact) и de011.py apply (MIC растворения) — после последнего импорта клипов и MI
- [ ] Specs(): 11 полей FHeroSpec из заявки и замеров; DefaultGame.ini: 3 строки cook
- [ ] Сборка UnmatchedEditor: "Result: Succeeded"; Unmatched.S08: EXIT CODE 0, нет Result={Fail};
      HeroesV2.Contact PASS (notify на LungeAttack), HeroesV2.Dissolve PASS
- [ ] Одна упаковка; listing .utoc содержит <Key>/<Stage>, Rig, H2Anim, MIC растворения
- [ ] Варианты фикстуры Р7-11 (env_bench_fixtures.cts --check ok); bench --packaged --fixture Marmoreal и Sarpedon
      с -BenchFocusFighter=<Key>: PNG осмотрены (новый боец на K2), нет BENCH FAILED fixture load;
      RENDER код 0 (--shot с p вместо точки); ARTLOOK heroes=v2 + backdrop доски; BENCH focus без error;
      ARTPREVIEW heroesV2 … clips=4/4; нет missing= / fallback=legacy / anim … missing=1; dissolve mi= не missing
- [ ] Лист K1/K2 обеих досок, цвет + серый — $E/game-sheet, осмотрен
- [ ] Evidence $E: JPEG 1200 q92 + *.evidence.json, трасса, README по HANDBOOK §9 с отступлениями
- [ ] asset-registry.json: технически импортировано / live-packaged-probe; validate_registry — новых ошибок нет
- [ ] 03-asset-registry.csv: строки по ВР-RG07/ВР-17 с пометкой делегирования
- [ ] Свои процессы остановлены по PID; редактор пользователя не тронут; 0 dirty-пакетов
- [ ] В git НЕ идут: work/, .staging/, logs/*.log, run.lock, *.fbm/, PNG кадров, 4K-мастера, сырые GLB (per-asset .gitignore этапа 0)
```

### 7.3 Коммит

- Только `git commit --no-verify` (AGENTS.md «Commits without hooks»). Файлы добавляются списком путей:
  `git -c core.longpaths=true add --dry-run -- <пути>`, затем `add` (HANDBOOK §8). Без `git add -A`, `.`, `stash`,
  `reset`, `clean` и push.
- `.uasset` — только `git add -f` поимённо: `Content/` в `unreal/Unmatched/.gitignore`. Это ассеты
  `<Key>/<Stage>/**`, `<Key>/Rig/**`, `<Key>/H2Anim/**` (включая `AM_<Key>_LungeAttack` с notify после `de010.py
  apply`), `/Game/UM/Materials/v2/Dissolve/MI_<Key>_<Stage>_P{1,2}_Dissolve` и пересобранный `M_UM_Figure_v2`
  (регистрация Р7-10). Образец того, что лежит в git, — `git ls-files unreal/Unmatched/Content/PipelineCandidates/Medusa`.
- Исключения из коммита задаёт per-asset `.gitignore`, созданный на этапе 0 (шаблон —
  `references/intake-and-evidence.md` §3).

### 7.4 Интеграция

Работа в worktree интегрируется только так (AGENTS.md «Integration workflow»):

1. `tools/git/safe-integrate.sh <branch>` — сухой прогон.
2. `tools/git/safe-integrate.sh <branch> --apply`. Ветка должна уже содержать свежий `fix/admin-panel`, и на ней
   должны пройти сборка и тесты. При изменениях в `unreal/` скрипт откажет, пока запущены UnrealEditor, UBT или
   клиент главного checkout (`safe-integrate.sh:52-57`): это тот же гейт SKILL.md §5 п.7 (§1 п.4).
3. В главном checkout: пересобрать UnmatchedEditor до открытия редактора — команду с путём главного checkout печатает
   сам скрипт после `--apply` (`safe-integrate.sh:71`).
4. `powershell -NoProfile -ExecutionPolicy Bypass -File tools/s08/sync-staged-build.ps1 -From <worktree>` вместо
   повторной упаковки. Скрипт откажет, если хеш исходников в `BuildStamp.json` не совпадает с главным checkout.
   Gitignored `Content` синхронизировать до него (`sync-staged-build.ps1:10`).

## 8. Проп: статический импорт (HANDBOOK §5)

У пропа этап 7 — это статический путь, без скелета, клипов, `Specs()` и регистрации героя.

1. Вход — `candidate-report.json` (все checks истинны, `um_fbx_v1_conforms`) и `fbx-readback.json` из этапа 3
   (HANDBOOK §5 п.5), вердикт этапа 4 `pass` (`D = null`, `G-RIG = n/a`, `references/acceptance-and-blender.md`).
2. Build-профиль `<name>-static-um-fbx-v1[-<run>].json` — копия профиля того же вида (образец
   `decor-barrel-static-um-fbx-v1-um-master.json`): общий мастер `/Game/UM/Materials/M_UM_Figure` +
   `texture_parameters`, `collision: none`, `two_sided: false`, TeamColor белый (HANDBOOK §5 п.6).
3. CLI, каждая UE-команда под `$L` (`docs/art-pipeline/ADDING-AN-ASSET.md` §4.1). Здесь `$R` — run-каталог
   сборки пропа этапа 3, а не run импорта героя:

   ```bash
   $T init --run-dir $R/ue-candidate --asset-id <ASSET_ID> --primary-source tripo-<task8> --primary-role <role> \
       --export-basename <SM_Name> --run-id <run>-ue-candidate --profile static-candidate --build-profile <build-профиль>
   $T register-source --run-dir $R/ue-candidate --spec <source-spec>
   $T run --run-dir $R/ue-candidate                                  # preflight, adopt (без UE)
   $L --step "<Asset> static ue-import" -- $T --backend mcp ue-import --run-dir $R/ue-candidate \
       --ue-folder /Game/PipelineCandidates/<Asset>/<run>/Candidate  # папка новая
   ```

   Образец в Content: `/Game/PipelineCandidates/DecorBarrel/20260928-p15-barrel/Candidate/`.
4. Посадку на поверхность проверяет контрольная сцена `python tools/tripo-pipeline/review/control_scene.py --out <dir>
   --tag r1 --barrel <SM asset>` (под `$L`; `decor_support.on_surface`, кадр 5×, HANDBOOK §5 п.8). Сцена построена на
   уровне Cobble и даёт редакторную диагностику, а не evidence: синтетические доски приёмкой не считаются (AGENTS.md).
5. В игру проп попадает только через env-layout доски. Это трек ENV-MAPS (AGENTS.md «Board scenes and heroes»), не
   этот скилл. Поэтому для пропа этап 7 кончается статусом «технически импортировано», записью в обоих реестрах
   (§7.1, `area` по `00-VISUAL-BRIEF.md` §4.7) и коммитом. Строку cook и bench-кадры добавляет трек ENV, когда
   размещает проп.

## 9. Ловушки (проверены 2026-10-09)

| Ловушка | Симптом | Правило |
|---|---|---|
| Правило памяти «`FBX_SCALE_UNITS` + import 100» | кость 0 ×100, фигура гигантская | для `UM_FBX_v1` **отменено**: патч `UnitScaleFactor 1.0` + import 1,0 (HANDBOOK §10, строка «Масштаб импорта»; `rig-contract.json` `ue_import.import_uniform_scale_conflict`). Ручной Scale при импорте — дефект |
| Двойная блокировка | `ue_hero_lookdev` висит до 25 мин | `review`/`verify` берут `ue-editor.lock` сами — не оборачивать в `ue_lock.py` (§1 п.3) |
| Конфиг съёмки скопирован у Medusa | `verify` сверяет чужие папки, 43 054 треугольника, кость `weapon_L`; без блока `verify` — `KeyError` | каждый ключ §3.2 пройти; `anchor_zone` по умолчанию `linen` — класс Medusa |
| `UnrealEditor-Cmd` при открытом GUI-редакторе | порча пакетов, конфликт с редактором пользователя | автотесты, кук, `de010.py apply` и `de011.py apply` — только без GUI-редактора на этом checkout (HANDBOOK §0.1, §1 п.4) |
| Мьютекс Live Coding | «Unable to build while Live Coding is active» в любом checkout, включая worktree | гейт SKILL.md §5 п.7 (§1 п.4); упаковка — `-SkipBuild` после сборки игрового target, но автотестам нужна собранная `UnmatchedEditor` |
| Обход через worktree при открытом редакторе пользователя | сборка падает на мьютексе, `safe-integrate.sh` отказывает («UE/UBT processes of the main checkout are running») | не обходить; пакет пользователю (§1 п.4) |
| Путь проекта главного checkout в worktree | собран и протестирован не тот проект | `-Project="$ROOT/unreal/Unmatched/Unmatched.uproject"` (§1) |
| `Build.bat` вернул 0 | «сборка прошла», а DLL старая | искать `Result: Succeeded` / `Result: Failed` в выводе (HANDBOOK §4.7) |
| `-NoLiveCoding` у игрового target | packaged-клиент падает при регистрации классов | не использовать (`package-client.ps1:40-52`) |
| Нет `--ue-folder` | ассеты в `/Game/PipelineCandidates/<Asset>/<run_id>`, игра их не видит → `fallback=legacy` | всегда `--ue-folder /Game/PipelineCandidates/<Key>/<Stage>` |
| Source-spec без суффикса `-h2` | `register-source` не находит файл или регистрирует не тот источник; `run` → «source … is not registered» | `--spec …/source-specs/tripo-<task8>-h2.json`, `--primary-source tripo-<task8>-h2` (§4.1) |
| Повторный импорт из нового run | код 3 «holds assets this run did not create» | скриптовое удаление своих ассетов прежнего run по §4.4, не ручные клики и не другая папка |
| Нет notify `Contact` | `HeroesV2.Contact` FAIL «LungeAttack has one Contact notify» | `de010.py apply` (Р7-1) после каждого импорта клипов (§5 п.3) |
| Имя слота | check `skeletal_material_slots` FAIL | слот = `materials.atlas` профиля H2 bake (`M_<Key>_H2_Atlas`), один на фигуру, один на подставку |
| Карта кромки и LUT | «нет текстуры» при сверке имён | `Edge` или `EdgeMask`, LUT по короткому ключу — из профиля, сверка `ls` (§2) |
| 2048 для всего | ложный FAIL размера подставки | 2048² — карты фигуры; у подставки бывают свои 1024² (Harpy) |
| Сокет без кости оружия | check `sockets_weapon_head` FAIL при `WEAPON_BONE: null` | `Weapon` — на кости удара из профиля (Harpy `foot.R`), `Head` обязателен (§3.1) |
| Новый `Config/**.json` | в паке нет профиля или файла, который должен лежать в паке | touch `Unmatched.Build.cs` + сборка игрового target до упаковки (AGENTS.md «Packaging trap»). Вариант bench-фикстуры в пак не нужен: packaged-клиент читает его loose-файлом (§6.2) |
| `UnrealPak -List` по `.pak` | 0 строк, «кукер всё выбросил» | ассеты в IoStore: листинг `.utoc` (§6.1) |
| Кукер не взял ассеты | в редакторе есть, в игре `fallback=legacy` | три строки `+DirectoriesToAlwaysCook` на героя; Dissolve покрывает `/Game/UM/Materials/v2` (`DefaultGame.ini:45`) |
| Нет MIC растворения | фигура исчезает рывком при смерти, `HeroesV2.Dissolve` FAIL | `de011.py apply` по регистрации, повтор после повторного импорта MI (§4.4); проверка `-BenchDissolve` (§6.3) |
| `bench` без проверки отпечатка | кадр вне эталона принят | `render_fingerprint.py check` на каждый PNG (§6.3); `profilesSource` должен быть `pak` |
| `--shot bench-K2x1.6-…` | код 3 «нет отпечатка» | точка вида в имени файла → `p`: `bench-K2x1p6-1920x1080.png` (§6.2) |
| Новый боец не на кадрах | на досках только нынешние бойцы | `bench --fixture S08Bench<Map>-<Key>.json` (варианты Р7-11); `-BenchFixture` в `--extra` — код 2 (§6.2) |
| K2 не на новом бойце | на K2 крупно Medusa | `--extra=-BenchFocusFighter=<Key>`, трасса `BENCH focus fighter=…` (§6.2) |
| Синтетическая доска | кадр «принят» на Cobble/ART FIXTURE | только `--map marmoreal` и `--map sarpedon` (AGENTS.md «Board scenes and heroes») |
| Отчёт по трассам без просмотра | серые болванки или не тот задник в отчёте | Read каждого PNG до отчёта (AGENTS.md «Look before you report») |
| Редакторные кадры как приёмка | в карточке кадры `h2anim_ue frames` / `ue_hero_lookdev` | это диагностика без RENDER; приёмка — только `-Bench` (§6.2) |
| `/Game/...` превратился в путь Git | «asset not found» | `export MSYS_NO_PATHCONV=1` |
| Клип без узла меша / клип «поверх» | AnimSequence не создан / смесь ключей | HANDBOOK §2.8, §7.5; `h2anim_ue.py import` удаляет старый клип сам — вместе с notify (§5 п.3) |
| Образец `build_tripo_medusa.py` | `SKEL_Medusa`, кость `weapon`, фигура смотрит в +Y | не в git, запрещён как образец (HANDBOOK §1); образцы — `tools/tripo-pipeline/blender/candidate_build/*`, `h2_bake/*` |
| Байты из живого Blender | невоспроизводимый FBX/PNG | только headless; MCP Blender — осмотр (HANDBOOK §0.1, §6) |
| Остальное | дубли `Name_1`, Interchange при переимпорте, 47 dirty-пакетов, Restore Packages, порядок `Rotator`, кадр 888×500 | HANDBOOK §7.6 |
