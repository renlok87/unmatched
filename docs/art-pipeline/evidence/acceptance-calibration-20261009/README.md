# Калибровка приёмки модели 2026-10-09

Набор для проверки рубрики этапа 4 скилла `.agents/skills/3d-model-pipeline/` (приёмка модели с коэффициентом,
`references/acceptance-and-blender.md` §12) на ассетах проекта. Здесь лежат кадры, снятые штатным инструментом
`tools/art/acceptance/capture_acceptance_set.py`, и листы концептов, по которым приёмщик ставит S. Цель — убедиться, что
рубрика, инструменты и приёмщики дают ожидаемый вердикт и что S ловит чужой концепт (негативный контроль).

Каталог в репозитории, а не во временной папке: в карточке `frames.dir`, `reports` и `previous_card` — пути от корня
репозитория (схема запрещает `C:/…`), и `validate_card.py --check-files` ищет их от корня. Исходники (FBX, текстуры,
виды листа) сюда не копируются: их пути и sha256 записаны в `frames.json` каждого прогона.

## Что здесь

| Путь | Что | Источник |
|---|---|---|
| `concept-medusa/sheet-medusa.png`, `checks-report.json` | лист Medusa (front/side/back) и автопроверки (код 0, PASS 28 / WARN 5 / FAIL 0) | `art/imagegen/hero-quality-v1/medusa/` |
| `concept-king-arthur/sheet-king-arthur.png`, `checks-report.json` | лист King Arthur (код 0, PASS 32 / WARN 1 / FAIL 0) | `art/imagegen/hero-quality-v1/king-arthur/` |
| `medusa-r1/frames/` (32 файла) | Medusa H2LD против листа Medusa: 8 `turn-*`, 9 `close-*`, 3 `wire-*`, 5 поз, `uv-layout.png`, `sheet.png`, 3 `compare-*`, `tone.json`, `frames.json` | `art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev` (генерический `h2_bake`) |
| `king-arthur-r1/frames/` (31 файл) | King Arthur H2LD против листа King Arthur; без `tone.json` (форк старше `ld_measure`, `--allow-no-tone`) | `art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-lookdev` (форк `h2_bake_arthur`) |
| `king-arthur-neg-r1/frames/` (31 файл) | **негативный контроль**: те же кадры King Arthur, но `sheet.png` и `compare-*` — по листу Medusa (`frames.json#sheet.key_match: false`) | то же |
| `<прогон>/card.json`, `acceptor-prompt.md`, при паре `card-2.json`, `final.json` | карточки приёмщиков повторного прогона (шаг 3 ниже) | — |
| `medusa-r1/round3-sol/` | карточка «Sol 6.1 xhigh» раунда 3 (`card-2.json`, без правок), её промпт, первое событие `--json` (`thread_id`) и карточка-заглушка первой попытки со сломанной песочницей | `codex exec`, 2026-10-09 |

Кадры раунда 3 (после разбора 44 замечаний трёх приёмщиков раунда 2): крупные планы со спины и ног
(`close-head-back`, `close-torso-back`, `close-legs`, `close-legs-back`), `compare-front/side/back` (вид листа и кадр в
одном росте, направляющие через 10 % роста), лист и `uv-layout.png` не больше 2000 px, `frames.json#pose_checks` —
3D-зазоры оружие–голова и оружие–тело во всех четырёх позах, `frames.json#accepted_object` — готовое поле карточки.
Раунд 4: ещё `wire-back.jpg` (сетка сзади, az 180) и `frames.json#render.shadows`; наборы пересняты, прочие кадры
совпадают с кадрами раунда 3 (разница пикселей ≤ 4 из 255 у 7 JPEG, остальные побайтно).

## Как снять заново

Из корня репозитория (Git Bash; Blender 5.2 headless, около 20 с на прогон, процессы завершаются сами):

```bash
export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8
C=docs/art-pipeline/evidence/acceptance-calibration-20261009
python tools/art/concept/check_concept_views.py --set art/imagegen/hero-quality-v1/medusa --key medusa \
    --views front,side,back --role hero --sheet --out $C/concept-medusa
python tools/art/concept/check_concept_views.py --set art/imagegen/hero-quality-v1/king-arthur --key king-arthur \
    --views front,side,back --role hero --sheet --out $C/concept-king-arthur
M=art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev
K=art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-lookdev
python tools/art/acceptance/capture_acceptance_set.py --fbx $M/export/SK_Medusa_H2LD.fbx --textures $M/textures \
    --key Medusa --side-view left --sheet $C/concept-medusa/sheet-medusa.png --out $C/medusa-r1/frames
python tools/art/acceptance/capture_acceptance_set.py --fbx $K/export/SK_KingArthur_H2LD.fbx --textures $K/textures \
    --key KingArthur --side-view left --allow-no-tone \
    --sheet $C/concept-king-arthur/sheet-king-arthur.png --out $C/king-arthur-r1/frames
python tools/art/acceptance/capture_acceptance_set.py --fbx $K/export/SK_KingArthur_H2LD.fbx --textures $K/textures \
    --key KingArthur --side-view left --allow-no-tone \
    --sheet $C/concept-medusa/sheet-medusa.png --out $C/king-arthur-neg-r1/frames
python -m pytest tools/art/acceptance/tests tools/art/concept/tests -q
```

Ожидаемый вывод съёмки (2026-10-09): все три — код 0. Medusa: WARN «свотчей палитры нет» и WARN `framing` (для Medusa
канон 1021 × 1540 верен — не дефект), `t_cap` 2,0. Arthur: WARN «свотчей нет» и «нет measure-report». Негатив: ещё WARN
«лист sheet-medusa.png (ключ medusa) не похож на лист ключа KingArthur». Без `--allow-no-tone` съёмка Arthur — код 1
(герою без `measure-report.json` тон не проверить). Повторная съёмка в тот же каталог заменяет только файлы с
фиксированными именами; карточки и промпты прогона не трогает.

Числа наборов (`frames.json`):

| | Medusa | King Arthur |
|---|---|---|
| `tone.json` | `t_cap` 2,0; якорь нормировки `linen`, `y_ratio_loo` 1,01; `floor`: `leather_smooth`, `stone_base`, `wood`; `family_changed_main` пуст | нет |
| `pose_checks` оружие–голова | `pose-01` 0,44 мм (касание лука и змей), `pose-02`/`pose-04` 0,099 м, `pose-03` 0,077 м (`pose-03b` az 150) | 0,028 м (`pose-02`, клинок перед глазом только в проекции) … 0,070 м (`pose-03b` az 30), касаний нет |
| `pose_checks` оружие–тело | 0,006–0,043 м | 0,005–0,009 м |
| лист | 2009 × 1138 → `sheet.png` 2000 × 1133 | 2645 × 1138 → `sheet.png` 2000 × 860 |
| `accepted_object` | 8 файлов (SK, SM, `2K_{BC,N,ORM,MatID,Edge}`, `TeamAccent_2K`) | 8 файлов (SK, SM, `{BC,N,ORM,MatID,EdgeMask}_2K`, `TeamAccent_2K`) |

## Прогон приёмщиков и ожидания

Шаги — `references/acceptance-and-blender.md` §12.1 п.3–6, поля заявки — §12.2 (у негатива объект — King Arthur:
гейты, отчёты, `UE_NAMES`, `accepted_object`; лист — Medusa: `ANCHORS`, `PALETTE`, `WEAPON_HAND`, `SIDE_VIEW`). Для
каждого прогона `E=$C/<прогон>`: промпт §8.2 → `$E/acceptor-prompt.md`, приёмщик «Opus xhigh» (§8.3,
`label: "acceptor-<ASSET_ID>-calib-<прогон>"`), ответ без правок → `$E/card.json`, затем

```bash
python tools/art/acceptance/validate_card.py $E/card.json --print-verdict --check-files
```

Код 3 (`needs_second_acceptor`, pass 8,0–8,4) — второй приёмщик «Sol 6.1 xhigh» (§8.5) → `$E/card-2.json` и
`validate_card.py $E/card.json --second $E/card-2.json --final-json $E/final.json --print-verdict --check-files`.

| Прогон | Ожидание |
|---|---|
| `medusa-r1` | гейты PASS по §4, S ≥ 1,5, вето нет, `score` ≥ 8,0, итог `pass` (при 8,0–8,4 — после второго приёмщика) |
| `king-arthur-r1` | гейты PASS по таблице форка §12.2, S ≥ 1,5; `pass` или `rework_blender` с пунктами F/T/D (ключи генерического профиля, §9.1) — оба допустимы; возврат (S < 1,5) — нет |
| `king-arthur-neg-r1` | S = 0 (другой персонаж, 0 из 6 якорей Medusa) → `return_to_stage_1` по правилу 1а, `rework_fix_list` = [], F/T/D — в `known_issues`; `--check-files` — код 0 и `WARN: … не совпадает с ключом ассета` (это и есть сверка входа) |

Ожидание не выполнено — порог 8,0 не снижается; разбор по §12.1 п.5. Итоги (вердикт, баллы, итог пары, разброс
профилей Opus/Sol) дописываются в таблицу ниже.

## Итог калибровки, раунд 3 (2026-10-09, кадры этого каталога до `wire-back`)

Приёмщики: три «Opus xhigh» (агенты Workflow, по одному на прогон) и «Sol 6.1 xhigh» (`codex exec`) на `medusa-r1` —
второй приёмщик по коду 3 и замер разброса профилей. Карточки Opus в каталог не записаны (итог оркестратора хранит
только `score`, вердикт и замечания к рубрике), поэтому для Opus дана сумма баллов, восстановленная из `score`.
Карточка Sol — `medusa-r1/round3-sol/card-2.json` без правок.

| Прогон | Профиль | S | F | T | D | score | вердикт | итог пары | ожидание |
|---|---|---|---|---|---|---|---|---|---|
| `medusa-r1` | Opus xhigh | сумма 6,5 | | | | 8,1 | `pass` → код 3 | — | |
| `medusa-r1` | Sol 6.1 xhigh | 1,5 | 1,0 | 1,0 | 1,5 | 6,3 | `rework_blender` (правило 3: G-TEX FAIL; без него — правило 4, 6,3 < 8,0) | `rework_blender` 6,3 (минимум пары) | **не выполнено** (ждали `pass`) |
| `king-arthur-r1` | Opus xhigh | сумма 4,0 (S ≥ 1,5: вердикт не возврат) | | | | 5,0 | `rework_blender` | — | выполнено (`rework_blender` с пунктами F/T/D допустим) |
| `king-arthur-neg-r1` | Opus xhigh | 0 (правило 1а, нет 5–6 из 6 якорей Medusa); сумма 2,5 | | | | 3,1 | `return_to_stage_1` | — | выполнено (S = 0 → правило 1а) |

Совпадение с ожиданием: 2 из 3. Негатив S = 0 ловит чужой лист (S действительно сравнивает с листом); Arthur в
допустимой полосе. Позитив Medusa не прошёл из-за второго приёмщика. Ожидание негатива в задаче оркестратора было
записано шире рубрики («S < 1,5 → `return_to_stage_1|2`»); по рубрике и валидатору при S = 0 допустим только
`return_to_stage_1` — ожидание этого README (S = 0, правило 1а) верно и выполнено.

**Разброс Opus и Sol на Medusa.** Opus 8,1 `pass`, Sol 6,3 `rework_blender`: по полушагу в S, F и T сразу (в раунде 2
у Opus было S 2,0 / F 1,5 / T 1,5 / D 1,5; разбивку раунда 3 оркестратор не сохранил, сумма та же). Порог §12.1 п.5
(> 0,5 в одном измерении) не превышен, но три полушага вместе переворачивают вердикт. Каждое расхождение сведено к
правилу, которое его допускало:

| Измерение | Sol | Причина расхождения | Правило раунда 4 |
|---|---|---|---|
| гейт G-TEX | FAIL | `ld-maps-report.json#outputs.T_Medusa_H2LD_2K_N.png` без `px` (N скопирована из bake) — буквальное «нет ключа = FAIL». Opus поставил PASS по мосту `pins` | §4: размер N — `textures-report.json#outputs.T_<Key>_H2_2K_N.png.px` через мост `pins.2K_N.sha256`; TeamAccent — `ld-team-accent-report.json#outputs` (тест `test_gtex_bridge_for_copied_normal_map`) |
| S | 1,5 | подставка шире листа (одно второстепенное отличие) | §5.1: размер подставки — норма HANDBOOK §2.10, в S не сравнивается; все пороги S — в % роста |
| F | 1,0 | `pose-02` открыл «плоскую крышку под поясом» на месте кулака (≈ 40 px) — это `closure.contact_caps` `dress_under_fist`; Sol счёл её F полного роста | §5 п.5: закрытие контакта, открытое позой пробы, — F только крупного плана (1,5) + `known_issues` «этап 6» |
| T | 1,0 | бурые пятна на задней стороне правого плеча на `turn-225` > 8 px | §5 п.6: «полный рост» — дефект **узнаётся сам** на `turn-*`/`pose-*` и больше 8 px; найденный на `close-*` и не узнаваемый на полном росте — только крупный план |

Ожидаемый итог повтора по правилам раунда 4 (прикидка фиксера рубрики, не оценка приёмщика): у Sol S 2,0, F 1,5, T 1,0–1,5,
D 1,5 → 8,1–8,8; гейты PASS. Проверить повтором пары — следующий шаг.

**Замечания Opus к рубрике (раунд 3) и что с ними сделано** (`references/acceptance-and-blender.md`, раунд 4):

- Medusa (15): пороги S в % роста, длина главной части; вид листа `front` — канон, расхождение видов — дефект листа
  (`known_issues`); якорь из нескольких носителей; порог полного роста «узнаётся сам и > 8 px» с примерами Medusa
  (губа, подошвы, пятно у плеча); D — один критерий контура, своя/чужая зона ткани (подол за бедром — своя); толщина
  тонкого элемента не S; основное пятно цвета ≥ 10 % пикселей, мелкая часть другого семейства — T своей зоны (подошвы —
  зона ног); эталон рендера для самой Medusa (мягкость на уровне эталона — не мыло); G-TEX N и TeamAccent; тень с
  оттенком другого семейства — пятно переноса; высота G-NAMES (5) — `scale.figure_top_m` против HANDBOOK §2.10; граница
  8 px исключающая, как в `seams-report`; верх головы под головным убором.
- Arthur (11): рельеф, похожий на лицо (пара глаз + нос + рот; рельеф — F, текстура — T); кадр `wire-back`; закрытие
  контакта и вырез подставки, открытые позой; чёрное пятно F против T; границы зон по высоте и половинам, плащ на
  профиле, дефект через границу зон; «крупная зона» переноса — половина видимой площади зоны; тоновые слова якоря;
  F 2,0 — плотность по кривизне; G-TEX форка — `textures-report.json#textures` look-dev; `tool` форка — ключи профиля
  Medusa; строки §9.3 для вырезов подставки и растянутой ткани.
- Негатив (15): F/T/D в негативе — только безусловные дефекты, `score` справочный; правило 1а: карточка всегда
  `return_to_stage_1`, вход решает только маршрут; якорь другой формы считается отсутствующим в счёте 1а; ступенька со
  смазанной текстурой — один дефект F; рельеф без выступа; `wire-back`; дефект через границу зон; бока плаща; мыло —
  «не читается там, где соседний участок читается»; сомнение «растяжение или разрыв» — якорь, признаки которого видны
  точно, + `known_issues`; разрыв = сквозной просвет; тени EEVEE включены (`frames.json#render.shadows`), AO против
  тени — проверка по поднятой стопе `pose-04`; G-NAMES (3) форка — `ld-export-report.json#checks.bones_equal_h2.
  measured.armature_objects`; эталон рендера разрешён приёмщику явно (§2.3 п.1).

**Вызов Sol (`codex exec`), найдено живым вызовом:** без `-c 'windows.sandbox="unelevated"'` при открытом приложении
песочница не запускает команд (`helper_unknown_error: setup refresh had errors`), код выхода 0, приёмщик возвращает
карточку-заглушку (`round3-sol/card-2-attempt1-sandbox-fail.json`: все баллы 0, `escalate_user`, 405 с); проба «Reply
OK» этого не ловит. С флагом — 732 с, около 2,9 млн входных токенов (2,66 млн из кэша), 17,5 тыс. выходных; строгая
схема принята; 5 событий `Reconnecting… n/5` и переход на HTTPS — безвредны. Пользовательский `~/.codex/config.toml`
тянет MCP, хуки и плагины (приёмщик прочитал чужой `SKILL.md` плагина) — в §8.4 добавлен `--ignore-user-config`
(проверен пробой, не полной приёмкой). `thread_id` попытки 2 — `01a11fba-9d99-7dd1-9d31-731f530c09d2`; в карточке
оставлен `codex:pending` (подстановка теперь разрешена §8.1 п.5 как единственная правка).

После раунда 4 карточка `round3-sol/card-2.json` с `--check-files` даёт код 1 (`frames.files` без `wire-back.jpg`):
это след старого набора, а не ошибка; повторный прогон пишет новые карточки в `<прогон>/`.

## Итог калибровки, раунд 4 (2026-10-09, правила и кадры раунда 4 — повтор по §12.1 п.5)

Три прогона «Opus xhigh» (Workflow `agent`, `model: opus`, `effort: xhigh`) и «Sol 6.1 xhigh» на `medusa-r1`
(`codex exec` по §8.4 с `--ignore-user-config` и `windows.sandbox="unelevated"`, 940 с). Карточки этого раунда в
каталог не сохранялись (вывод агентов калибровки); карточка Sol — во временном каталоге прогона.

| Прогон | Профиль | S | F | T | D | score | вердикт | итог пары |
|---|---|---|---|---|---|---|---|---|
| `medusa-r1` | Opus xhigh | 2,0 | 1,5 | 1,5 | 1,5 | 8,1 | `pass` → код 3 (второй приёмщик) | `pass` (min 8,1) |
| `medusa-r1` | Sol 6.1 xhigh | 2,0 | 1,5 | 1,5 | 1,5 | 8,1 | `pass`, все гейты PASS | — |
| `king-arthur-r1` | Opus xhigh | 1,0 | 1,0 | 1,5 | 1,5 | 6,3 | `return_to_stage_2` (профиль: плащ перед стопами, сабатоны ≈28 % против ≈16,5 % роста на compare-side) | — |
| `king-arthur-neg-r1` | Opus xhigh | 0,0 | 0,5 | 1,5 | 1,5 | 4,4 | `return_to_stage_1` (правило 1а) | — |

Вывод: позитив Medusa — ожидание выполнено, оба профиля совпали поизмерительно (разброс 0). Негатив — ожидание
выполнено. Arthur — строже ожидания «pass или обоснованный rework»: маршрут на этап 2 обоснован отличием профиля от
листа (S 1,0 по порогам 5/10 % роста §5.1). Принятый в проекте Arthur прошёл приёмку панелью на K1–K3 до появления
этой рубрики; скилл применяет рубрику только к новым ассетам, пересмотр Arthur не требуется. Остаточные
неоднозначности, которые назвали приёмщики (порог «узнаётся сам» для рельефа-лица, отнесение стоп к «главной части»,
зона дефекта у пояса), — открытые пункты следующей калибровки; на маршрут Medusa и негатива они не влияли.

История: раунд 1 (Medusa, «Opus xhigh») — `pass` 8,1; раунд 2 (три приёмщика «Opus xhigh» на кадрах во временном
каталоге `C:/tmp/skill-rewrite/r2-accept/`) — Medusa `pass` 8,1, Arthur `rework_blender` 6,9, негатив
`return_to_stage_2` 5,0 (S 0,0; по правилу 1а раунда 3 это `return_to_stage_1`); раунд 3 и раунд 4 — таблицы выше.
