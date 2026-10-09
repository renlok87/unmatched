# tools/art/acceptance — кадры приёмки и карточка с вердиктом

Инструменты этапов 1, 4 и 6 скилла `.agents/skills/3d-model-pipeline/` (DECISIONS Р-6, Р-7.2, Р-9). Норма производства
модели — `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (дальше HANDBOOK); числа гейтов берутся из его отчётов, здесь они
не дублируются.

| Файл | Что делает |
|---|---|
| `capture_acceptance_set.py` | кадры приёмки модели (этап 4) из отгружаемого FBX + текстур, Blender headless |
| `_blender_capture.py` | Blender-часть (рендер, позы, UV-данные); запускается только обёрткой |
| `_framing.py` | кадрирование и геометрия кадров (только numpy): масштаб по проекции, крупный план кисти, зазор оружие–голова |
| `_tone.py` | тон классов против концепта из `measure-report.json` look-dev → `frames/tone.json` и потолок T |
| `validate_card.py` | проверка карточки по схеме, пересчёт score, детерминированный вердикт |
| `asset-acceptance-2.schema.json` | JSON Schema (Draft 2020-12) карточек `kind`: `concept` \| `model` \| `anim` |
| `asset-acceptance-2.output-{model,concept,anim}.schema.json`, `_output_schema.py` | строгие схемы вывода приёмщика для `codex exec --output-schema` (производные от полной; `--write` пересобирает, `--check` — код 1 при устаревших) |
| `tests/` | pytest: правила вердикта, сверки полей, встроенный валидатор = jsonschema, помощники кадров |

## 1. Кадры приёмки модели

```bash
python tools/art/acceptance/capture_acceptance_set.py \
    --fbx art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-h2-lookdev/export/SK_<Key>_H2LD.fbx \
    --textures art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-h2-lookdev/textures \
    --out art/pipeline-candidates/<ASSET_ID>/evidence/acceptance/<YYYYMMDD>-r<N>/frames \
    --key <Key> --side-view left|right --sheet art/imagegen/concept-<content-key>-codex/sheet-<content-key>.png \
    [--measure <run>/reports/measure-report.json] [--allow-no-tone] \
    [--blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"] [--base <SM_*.fbx> | --no-base]
```

- Вход — FBX UM_FBX_v1 (HANDBOOK §2.2: лицо +X). Скрипт поворачивает его на −90° вокруг Z обратно в авторский кадр
  (лицо −Y, сторона `.L` = +X), как `tools/tripo-pipeline/blender/h2_bake/st_preview.py`.
- Текстуры: `*_BC.png` (sRGB), `*_N.png` (Non-Color, DirectX — HANDBOOK §2.4; для превью зелёный канал инвертируется,
  Blender ждёт OpenGL), `*_ORM.png` (Non-Color: G → Roughness, B → Metallic; R/AO в шейдер не подаётся, как в
  st_preview). Имена `T_<Key>_H2LD_2K_BC.png` (генерический look-dev) и `T_<Key>_H2LD_BC_2K.png` (форки Arthur и
  Merlin) — оба; из нескольких кандидатов берётся 2K (рантайм-набор героя), 4K — только если 2K нет; `--key`
  оставляет только `T_<Key>_*`. Неоднозначность — код 1.
- `frames.json#accepted_object` — SK, SM и 2K-карты `BC`, `N`, `ORM`, `MatID`, `Edge` (у форков `EdgeMask`),
  `TeamAccent` с sha256: готовое поле `accepted_object` карточки. У героя без какой-то карты — WARN.
- Лист концепта: `--sheet` копирует его в `frames/sheet.png`; лист шире 2000 px уменьшается до 2000 (Read показывает
  картинку больше 2000 px уменьшенной, а приёмщик смотрит 1:1). Если рядом с листом лежит `checks-report.json`
  (`check_concept_views.py`), в `frames.json#sheet` пишутся свотчи (`compare_palette_by`), ключ листа (`content_key`,
  `key_match` против `--key`: `false` — WARN «не тот лист или негативный контроль») и виды; по видам строятся
  `compare-front/side/back.jpg`. `--side-view` (поле `SIDE_VIEW` заявки) выбирает `turn-090` (`left`) или `turn-270`
  (`right`) для `compare-side`; без флага — `turn-090` и WARN. Без `--sheet` — WARN: `validate_card.py` требует лист
  в `frames.files`.
- Тон: `--measure`, иначе `<run>/reports/measure-report.json`, если FBX лежит в `<run>/export/` (стадия `ld_measure`
  генерического look-dev). Рядом берётся `ld-maps-report.json` (классы у пола альбедо). Результат — `frames/tone.json`
  (`_tone.py`, раздел 1.1). У героя (есть арматура) без отчёта — **код 1**; `--allow-no-tone` — только ассет старше
  `ld_measure` (форки Arthur/Merlin/Harpy, калибровка): WARN, `tone.json` нет. У пропа — WARN.
- Подставка: соседний `SM_<имя SK без SK_>_Base.fbx` подхватывается сам (атлас общий); `--no-base` — без неё.
- Blender: `--blender`, иначе env `BLENDER`, иначе путь выше. Запуск `-b --factory-startup`, процесс завершается сам,
  окно не открывается. Medusa H2LD: ~20 с на весь набор.

Выход (имена фиксированы, Р-6.1; JPEG 1200×1200, качество 92, фон ровный серый RGB 72,72,72):

| Файл | Камера | Содержание |
|---|---|---|
| `turn-000.jpg` … `turn-315.jpg` | орто, шаг 45°, возвышение 0 | текстуры BC+N+ORM, EEVEE, AgX. 000 = спереди, 090 = левый бок фигуры (`.L`), 180 = сзади, 270 = правый бок |
| `close-head.jpg`, `close-head-back.jpg` | орто, az 25° / 205°, el 10° | рамка по вершинам группы `head` (вес ≥ 0,5); нет группы — верх 22 % роста (WARN); `-back` — только при арматуре |
| `close-weapon.jpg` | орто, az ±35° (сторона оружия), el 10° | крупный план **хвата**: центр между головой кости `weapon.L`/`weapon.R` (точка хвата, HANDBOOK §2.6) и кистью той же стороны, рамка 3 габарита кисти в пределах 12–25 % роста; нет группы кисти — 12 % роста (WARN); нет кости — верхняя часть фигуры (WARN) |
| `close-hands.jpg` | две панели 600×1200: hand.R (az −35°) слева, hand.L (az +35°) справа, el 10° | только при арматуре; рамка панели — 3 габарита кисти (12–25 % роста) по группе `hand.R`/`hand.L`; нет группы — голова кости (WARN). В `frames.json#frames` — одна запись `close-hands.jpg` с `panels` |
| `close-torso.jpg`, `close-torso-back.jpg` | орто, az 20° / 200°, el 5° | только при арматуре; рамка по вершинам группы `spine` (20–45 % роста); `-back` — спина, задняя сторона плеч, колчан, верх плаща; нет группы — 62 % роста (WARN) |
| `close-legs.jpg`, `close-legs-back.jpg` | орто, az 340° / 160°, el 5° | только при арматуре; ноги и низ одежды по группам `hips`, `leg_upper.*`, `leg_lower.*`, `foot.*` (рамка 25–60 % роста); нет групп — нижние 55 % роста (WARN) |
| `close-base.jpg` | орто, az 30°, el 25° | подставка из `--base`/соседнего `SM_*_Base.fbx` целиком со стопами; без подставки — нижние 22 % модели (WARN) |
| `wire-front.jpg`, `wire-34.jpg`, `wire-back.jpg` | спереди; az 45°, el 15°; сзади (az 180°, раунд 4: затылок, спина, плащ) | сетка треугольников 1 px на глине |
| `uv-layout.png` | — | UV0 всех мешей (1600 px) поверх затемнённого BC: острова залиты цветом, границы островов жёлтые; подпись внизу; не больше 2000 px по любой стороне |
| `pose-01.jpg` … `pose-04.jpg`, `pose-03b.jpg` | см. ниже | только при арматуре |
| `sheet.png` | — | копия `--sheet`, не шире 2000 px |
| `compare-front.jpg`, `compare-side.jpg`, `compare-back.jpg` | — | вид листа слева и `turn-000` / `turn-090`\|`turn-270` / `turn-180` справа, обе фигуры одного роста (1000 px от верха фигуры до низа подставки, рамки — `checks-report.json#measurements.<view>.mask.bbox_px` и альфа кадра), низ на одной линии, жёлтые направляющие через 10 % роста; не шире 2000 px; только если у листа есть `checks-report.json` с видами |
| `tone.json` | — | `unmatched.acceptance-tone/1`, если есть `measure-report.json` (раздел 1.1) |
| `frames.json` | — | `unmatched.acceptance-frames/1`: входы с sha256, `accepted_object`, параметры рендера, габарит, меши, позы, `pose_checks`, `sheet`, `compare`, `side_view`, `tone`, проверки кадров (с рамкой фигуры `bbox_px`), предупреждения, `files` |

Позы — тесты `tools/tripo-pipeline/anim/rig_deform_probe.py` (определения `FAMILIES`/`TESTS` читаются из файла через
`ast`, без импорта: модуль при импорте сразу запускает `main()`), повороты применяются последовательно:

| Кадр | Тесты | Ракурс |
|---|---|---|
| `pose-01` | `arm_l_raise` + `forearm_l_bend` | спереди |
| `pose-02` | `arm_r_raise` | спереди |
| `pose-03` | `spine_bend_fwd` + `head_turn` | az 60°, el 10° |
| `pose-04` | `thigh_l_flex` | az 70°, el 5° |
| `pose-03b` | та же поза, что `pose-03` | az из 0, 30, …, 330, на котором проекции группы оружия и группы `head` дальше всего друг от друга, el 10° |

`frames.json#pose_checks.<pose>` — в **каждой** позе (калибровка 2026-10-09, раунд 3): `weapon_head_min_distance_m`
(оружие против группы `head`: лицо, волосы, змеи, корона) и `weapon_body_min_distance_m` (оружие против тела: меши без
подставки, вершины, чья главная группа не оружие, не `head`, не кисть и не предплечье руки с оружием), флаги
`weapon_head_contact` / `weapon_body_contact` (зазор < 3 мм). Расстояние — точное минимальное между вершинами
(KD-дерево `mathutils`, все вершины). У `pose-03` ещё азимут и зазор проекций `pose-03b`. На орто-кадре не понять,
перед лицом оружие или сквозь него — число решает (рубрика §5.4: столкновение оружия D не снижает, касание — в
`known_issues`). Medusa H2LD: `pose-01` касание лука и змей 0,44 мм, `pose-03` 0,077 м (az 150); Arthur H2LD: касаний
нет, `pose-02` 0,028 м, `pose-03` 0,070 м (az 30).

Кадрирование: `turn-*`, `wire-front` и `wire-back` — общий масштаб `max(рост, 2 × радиус) × 1,10`; `wire-34` и `pose-*` — не меньше
проекции модели на свой ракурс с запасом 10 % (`_framing.py`; иначе широкий проп, например бочка, на el 15° обрезан).

Крупные планы (`close-*`) — увеличение примерно ×2 (голова, ноги) … ×7 (хват) против `turn-*` (Medusa: рамка turn
0,61 м, хват 0,084 м). Так приёмщик видит мелкие дефекты на кадре 1:1 без вырезок и увеличений; каждая зона героя
(рубрика §3) есть на крупном плане спереди и сзади.

Автопроверки (код 1 при нарушении): все кадры есть, 1200×1200; доля фигуры по альфе ≥ 2 %; фигура не касается края
в `turn-*`, `wire-*`, `pose-*` (крупные планы обрезаны намеренно); покрытие UV ≥ 0,5 % (ниже 5 % — WARN: часть общего
атласа, например подставка); герой без `measure-report.json` без `--allow-no-tone`. Повторный запуск в тот же `--out`
удаляет только файлы с фиксированными именами. Тени EEVEE от key/fill/rim включены (`frames.json#render.shadows`):
контактная тень стоп на подставке — свет, AO в ORM (канал R) не подаётся. Кадры — для глаз приёмщика; гейты PASS/FAIL берутся из отчётов
h2-bake/look-dev, не из кадров.

### 1.1 Тон классов (`tone.json`)

Кадры EEVEE + AgX + свет key/fill/rim заметно светлее живописи концепта, поэтому тон класса против листа на глаз не
оценивается. `_tone.py` читает `measure-report.json#zones.<class>.delta_ld_vs_concept` (экспозиция уже нормирована
стадией `ld_measure`, `tools/tripo-pipeline/blender/h2_bake/lookdev.py:run_measure`) и `ld-maps-report.json#grade.
median_floor_applied` (классы, поднятые к полу альбедо: концепт темнее физического пола, остаток — свет).

| Поле строки `classes[]` | Смысл |
|---|---|
| `y_ratio` | `Y_ratio_exposure_normalised`: яркость класса H2LD / концепт после нормировки экспозиции; 1 = как в концепте |
| `y_ratio_loo` | только у основного класса: яркость относительно экспозиции по **остальным** классам (leave-one-out: без проверяемого, без `floor` и `legacy_bake`), `k_loo / k_класса`, где `k = Y(концепт) / Y(H2LD)`; `null`, если у остальных классов вместе меньше 10 % пикселей (WARN `loo_unavailable`) |
| `anchor` | `true` у якорного класса нормировки (`measure-report.json#exposure.class` при `mode: anchor_class`): его `y_ratio` = 1 по построению, яркость проверяет только `y_ratio_loo` |
| `d_hue_deg`, `d_sat` | сдвиг тона и насыщенности медианы |
| `family` | `same` \| `changed`: обе медианы хроматические (насыщенность ≥ 0,15) и \|dHue\| > 30°, или нейтральная ↔ хроматическая с \|dSat\| ≥ 0,20 — смена семейства цвета (это S рубрики); иначе `same` (светлота и насыщенность — T) |
| `share`, `role` | доля пикселей рендера; `main` при доле ≥ 10 %, иначе `secondary` |
| `status` | `ok`; `out` — `y_ratio` (а у основного класса и `y_ratio_loo`) вне 0,80–1,25 или \|`d_hue_deg`\| > 15°; `floor` — класс у пола альбедо (T не снижает) |

Поля верхнего уровня: `t_cap`, `anchor_class`, `out_of_tolerance`, `floor_limited`, `family_changed_main` (основные
классы другого семейства, без `floor`), `warnings`, `framing`.

`t_cap` (потолок T): 1,0 — вне допуска основной класс; 1,5 — только второстепенные; 2,0 — все в допуске. Допуски —
решение скилла, калибровка Medusa H2LD (`20260929-h2-lookdev`): классы вне пола 0,965–1,203, \|dHue\| ≤ 3,8°, якорь
`linen` по leave-one-out 1,01, пол — `leather_smooth`, `stone_base` (1,58), `wood` (1,47) → `t_cap` 2,0.
`validate_card.py --check-files` проверяет `scores.T.value ≤ t_cap`, если `tone.json` есть в `frames.files`.

Почему leave-one-out (калибровка 2026-10-09, раунд 3). Нормировка по якорному классу делает его яркость
непроверяемой: у Medusa платье (36 % пикселей) — якорь, и сдвиг его яркости не попадал ни в S (там без яркости), ни в
T. Абсолютная экспозиция не годится: у живописи концепта свой свет, и отношение Y(концепт)/Y(кадр) несёт экспозицию
целиком. Экспозиция по остальным классам сохраняет смысл ld_measure («отношения тонов классов как в концепте») и
проверяет каждый основной класс, якорь в том числе.

`tone.json` годится как потолок T только при орто-кадрах look-dev, выровненных по концепту. С h2-bake 0.6.1 рамку
задаёт look-dev профиль `frame` (`tools/tripo-pipeline/blender/h2_bake/framing.py`; новый персонаж —
`{"checks_report": "<checks-report.json набора концепта>", "side": "<SIDE_VIEW>"}`). Без `frame` действует канон
Medusa 1021 × 1540, и `ld_measure` отказывается работать, если аспект концепта отличается от прохода ID больше чем на
1 % (сжатие концепта дало бы медианы классов не из тех областей). `measure-report.json#framing` есть только у
профиля с `frame`.

## 2. Карточка и вердикт

```bash
python tools/art/acceptance/validate_card.py <card.json> [--print-verdict] [--check-files] [--no-jsonschema]
python tools/art/acceptance/validate_card.py <card.json> --second <card-2.json> [--same-profile-ok] \
    [--final-json <final.json>] [--print-verdict] [--check-files]
```

- Код 0 — карточка (пара) валидна и `verdict` согласован с правилами; 1 — нет (ошибки `FAIL: …` в stderr, применённое
  правило `rule: …` в stderr); **3** — карточка (любого kind) валидна, но `pass` неустойчив (score 8,0–8,4): нужен
  второй приёмщик (ниже).
- `--print-verdict` печатает в stdout вычисленный вердикт одной строкой; если правило оставляет выбор —
  `return_to_stage_1|return_to_stage_2`; при коде 3 — `needs_second_acceptor`; с `--second` — итог пары. Печатается и
  для невалидной карточки, если вердикт вычислим.
- `--check-files` — файлы `accepted_object` существуют и sha256 совпадает; `frames.dir/<files>`, `reports`,
  `previous_card` и пути-источники гейтов существуют (пути от корня репо); T модели ≤ `t_cap` из `tone.json`. У
  модели с `frames.json` в кадрах ещё сверка входа: `frames.files` = `frames.json#files`, `frames.json#inputs.fbx.sha256`
  есть в `accepted_object` (кадры сняты с принимаемого FBX), `sheet.png` = `frames.json#sheet.sha256` (лист не
  подменён); `frames.json#sheet.key_match = false` — `WARN:` (лист другого ассета: стоп запускающего или негативный
  контроль калибровки), код не меняет.
- **Устойчивый pass** (все три kind — model, concept, anim; решение скилла — защита от разброса приёмщиков ±0,5 на
  одном измерении, раунд 3 распространил его на лист и клип): pass со score ≥ 8,0 и < 8,5 одной карточкой не
  окончателен (у героя, листа и клипа это 8,1, у пропа 8,3). Второй приёмщик **другим профилем** на
  тех же кадрах пишет `card-2.json`; `--second` проверяет обе карточки и пару (одинаковы `asset_id`, `cycle`,
  `previous_card`, `accepted_object`, `frames`, `executor_session_id` и статусы гейтов; профили и `session_id`
  разные). Итог: score — минимум двух; вердикт — карточки с меньшим score (при равенстве — более строгий), но если у
  другой карточки маршрут строже (возврат, FAIL-гейт, вето), побеждает он; маршрут и `rework_fix_list` берутся из
  `source_card`. `--same-profile-ok` — только когда второй профиль не запустился после пробы (в `final.json`
  `same_profile_fallback: true`). `--final-json` пишет `unmatched.acceptance-final/1`.
- Пакет `jsonschema` есть — проверка им (Draft 2020-12); нет — встроенной проверкой того же подмножества ключевых слов
  (`--no-jsonschema` включает её принудительно; тесты сверяют оба пути).
- Строгий вывод приёмщика «Sol 6.1 xhigh»: `codex exec --output-schema` требует строгую схему (у каждого объекта
  `additionalProperties: false`, все свойства обязательны, без `allOf`/`if`/`then`, `propertyNames`,
  `minProperties`, `minLength`, `uniqueItems`). Полная схема так не может, поэтому приёмщику даётся
  `asset-acceptance-2.output-<kind>.schema.json`: kind фиксирован, гейты и измерения — фиксированные свойства,
  необязательные поля (`clip` не у клипа, `verdict_reason`, `gates.*.note`, `gates.*.source_defect`) — `null`.
  `validate_card.py` читает `null` в этих полях как «поля нет» (`strip_output_nulls`; файл не меняется) и остаётся
  судьёй: правила вердикта, `verdict_reason` при не-pass и `clip` у клипа проверяет полная схема.
  Живой вызов 2026-10-09 (калибровка, `medusa-r1`): строгая схема модели принята, карточка прошла валидатор с
  `--check-files`. Команда и флаги (`windows.sandbox="unelevated"`, `--ignore-user-config`, кодировки PowerShell) —
  рубрика `references/acceptance-and-blender.md` §8.4.

Виды карточек (один файл схемы, поле `kind`):

| kind | schema | Измерения 0–2, шаг 0,5 | Гейты | Циклы | Путь карточки |
|---|---|---|---|---|---|
| `concept` (этап 1) | `unmatched.concept-acceptance/1` | S силуэт/читаемость, C согласованность видов, Q детализация против QUALITY_REFERENCE, P палитра/якоря | `G-CHECKS` (`check_concept_views.py` 0 FAIL) | r1…r4 | рядом с листом концепта |
| `model` (этап 4) | `unmatched.asset-acceptance/2` | S силуэт/пропорции/палитра, F форма и шейдинг, T текстуры, D деформация (`null` у пропа) | `G-TOPO`, `G-UV`, `G-TEX`, `G-RIG` (`n/a` у пропа), `G-NAMES` | r1…r3 | `art/pipeline-candidates/<ASSET_ID>/evidence/acceptance/<YYYYMMDD>-r<N>/card.json` |
| `anim` (этап 6, на клип, поле `clip`) | `unmatched.anim-acceptance/1` | R читаемость и тайминг, C контакт/удар, D деформация в движении, L оседание/цикл | `G-VALIDATE` (`validate_clip.py`), `G-CONTACT` (`clip_contact_check.py`), `G-MANIFEST` | r1…r3 | `…/evidence/acceptance-anim/<YYYYMMDD>-r<N>/card.json` |

`score = round(sum / (2 × n) × 10, 1)`, n — измерения с числовым баллом (округление half-up). Порог — `score >= 8.0`.

Правила вердикта (проверяются по порядку):

| kind | Условие | Вердикт |
|---|---|---|
| model | S = 0 (другой персонаж: нет половины и больше якорей листа) | `return_to_stage_1` (концепт не тот); `--print-verdict` печатает только его |
| model | S 0,5 или 1,0 (независимо от суммы) | `return_to_stage_1` (дефект есть на листе в том же месте) или `return_to_stage_2` (лист верен, Tripo отклонился) — выбор обосновать в `verdict_reason` |
| model | любой гейт FAIL | `rework_blender`; если у FAIL-гейта `source_defect: true` (нет части, фантом в исходнике Tripo) — `return_to_stage_2` |
| model, anim | любое измерение < 1,0 (вето) или score < 8,0 | `rework_blender` |
| concept | G-CHECKS FAIL, вето < 1,0 или score < 8,0 | `return_to_stage_1` (следующий цикл листа) |
| все | иначе | `pass` |
| все | последний цикл (model/anim r3, concept r4) и вердикт не `pass` | `escalate_user` |

Сверки полей: `verdict_reason` (≥ 10 символов) обязателен при любом вердикте, кроме `pass`; `D = null` ⇔ `G-RIG = n/a`;
`n/a` допустим только у `G-RIG`; у модели в `frames.files` есть все фиксированные кадры (`close-hands`, `close-torso`,
`close-head-back`, `close-torso-back`, `close-legs`, `close-legs-back`, позы и `pose-03b` — если риг есть) и лист концепта (`sheet.png` или прежнее `sheet-<key>.png`); кадры, на которые
ссылаются баллы и `known_issues`, есть в `frames.files`; `rework_fix_list` содержит только измерения < 2 и FAIL-гейты
(у модели никогда `S`: силуэт в Blender не правится; при S < 1,5 список пуст — модель перегенерируют, F/T/D идут в
`known_issues`), а при `rework_blender` покрывает каждый FAIL-гейт, каждое
измерение < 1,0, а у модели при score < 8,0 — каждое из F, T, D ниже 2,0; `known_issues[]` — необязательные замечания
`{item, frame, note}` при любом вердикте; у r2+ есть `previous_card`, у r1 — `null`;
`acceptor.session_id ≠ executor_session_id` (приёмщик не принимает свою работу); при `pass` с `decided_by` «delegated…»
`status_note` содержит «по делегированию» (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`).
Все пути — от корня репозитория, прямые слэши.

Пример карточки модели (pass; Medusa H2LD — набор, на котором проверен инструмент кадров):

```json
{
  "schema": "unmatched.asset-acceptance/2",
  "kind": "model",
  "asset_id": "ASSET-MEDUSA-001",
  "cycle": "r1",
  "date": "2026-10-09",
  "previous_card": null,
  "accepted_object": [
    {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/export/SK_Medusa_H2LD.fbx",
     "sha256": "f5a49a34610d0d872fe77b2c24e4039e15efc89c54f0a68ea39cf4846fcddcc3"}
  ],
  "frames": {
    "dir": "art/pipeline-candidates/ASSET-MEDUSA-001/evidence/acceptance/20261009-r1/frames",
    "files": ["turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg",
              "turn-270.jpg", "turn-315.jpg", "close-head.jpg", "close-head-back.jpg", "close-weapon.jpg",
              "close-hands.jpg", "close-torso.jpg", "close-torso-back.jpg", "close-legs.jpg", "close-legs-back.jpg",
              "close-base.jpg", "wire-front.jpg", "wire-34.jpg", "wire-back.jpg", "uv-layout.png", "pose-01.jpg",
              "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "frames.json", "sheet.png", "compare-front.jpg",
              "compare-side.jpg", "compare-back.jpg", "tone.json"]
  },
  "reports": ["art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/ld-fbx-report.json"],
  "gates": {
    "G-TOPO":  {"status": "PASS", "source": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/ld-fbx-report.json"},
    "G-UV":    {"status": "PASS", "source": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/ld-fbx-report.json"},
    "G-TEX":   {"status": "PASS", "source": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/ld-maps-report.json"},
    "G-RIG":   {"status": "PASS", "source": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/ld-fbx-report.json"},
    "G-NAMES": {"status": "PASS", "source": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/ld-fbx-report.json"}
  },
  "scores": {
    "S": {"value": 2,   "rationale": "силуэт и палитра совпадают с концептом во всех 8 ракурсах", "frames": ["turn-000.jpg", "turn-090.jpg", "sheet.png"]},
    "F": {"value": 2,   "rationale": "сетка ровная, артефактов шейдинга нет", "frames": ["wire-front.jpg", "wire-34.jpg"]},
    "T": {"value": 1.5, "rationale": "детализация на уровне эталона, мелкий шов на голени", "frames": ["close-head.jpg", "turn-180.jpg"]},
    "D": {"value": 2,   "rationale": "позы без разрывов и заломов", "frames": ["pose-01.jpg", "pose-03.jpg"]}
  },
  "score": 9.4,
  "verdict": "pass",
  "rework_fix_list": [],
  "known_issues": [{"item": "T", "frame": "close-base.jpg", "note": "подставка светлее листа: stone_base status floor в tone.json"}],
  "acceptor": {"profile": "Opus xhigh", "session_id": "wf-accept-0001"},
  "executor_session_id": "wf-exec-0001",
  "decided_by": "delegated (ВР-реестр 2026-10-06)",
  "status_note": "художественно принято, по делегированию"
}
```

Баллы и обоснования в примере — иллюстрация формы, не результат приёмки. Пункт `rework_fix_list`:
`{"item": "T", "frame": "close-head.jpg", "fix": "что исправить", "tool": "чем (профиль h2_bake/lookdev, стадия)"}`.

## 3. Тесты

```bash
python -m pytest tools/art/acceptance/tests -q
```

Blender для тестов не нужен (Blender-часть проверяется прогоном на реальном ассете, раздел 1).

## 4. Решения скилла в этих инструментах

- Свет key/fill/rim — позиции и мощности `st_preview.py` (фигура 0,55 м), масштабируются по росту и вращаются вместе с
  камерой: все 8 ракурсов освещены одинаково (как Material Preview). Тональная кривая AgX, как в st_preview.
- Фон кадров RGB 72,72,72: рендер с прозрачной плёнкой, кадр кладётся на фон обёрткой; та же альфа — маска проверок.
- Набор поз pose-01…04 — 4 сочетания из 7 тестов `rig_deform_probe.py` (обе руки, корпус+голова, бедро).
- Концепт: до r4 (Р-5.8 «≤ 3 цикла после первой приёмки»); модель и клип: до r3 (Р-1 этап 5, Р-7.2).
- Выбор `rework_blender` / `return_to_stage_2` при FAIL-гейте детерминирован флагом гейта `source_defect`.
- Крупные планы кисти и хвата: 3 габарита кисти, рамка 12–25 % роста; `close-hands` — две портретные панели в одном
  квадратном кадре (фиксированное имя, одна ссылка в баллах).
- `pose-03b`: азимут с наибольшим зазором проекций оружия и головы (шаг 30°).
- Тон: потолок T по `measure-report.json` (раздел 1.1), а не по сравнению кадра с листом на глаз.
- Устойчивый pass: полоса 8,0–8,4 и второй приёмщик — для всех `kind` (модель, лист концепта, клип; раунд 3).
- Раунд 3 калибровки 2026-10-09: крупные планы со спины и ног (`close-head-back`, `close-torso-back`, `close-legs`,
  `close-legs-back`) — у каждой зоны модели есть крупный план; `compare-*` — вид листа и кадр в одном росте с
  направляющими через 10 % (пропорции S без глазомера); лист и `uv-layout.png` не больше 2000 px (Read показывает 1:1);
  `pose_checks` во всех позах (оружие–голова и оружие–тело, точное KD-расстояние); `accepted_object` и ключ листа в
  `frames.json` (сверка входа в `validate_card.py --check-files`); герой без `measure-report.json` — код 1
  (`--allow-no-tone` для ассетов старше `ld_measure`); тон: leave-one-out для основных классов и семейство цвета.
- Набор калибровки рубрики снят этим инструментом в репозиторий:
  `docs/art-pipeline/evidence/acceptance-calibration-20261009/` (`README.md` там; проверяется
  `tests/test_rules_round3.py`).
