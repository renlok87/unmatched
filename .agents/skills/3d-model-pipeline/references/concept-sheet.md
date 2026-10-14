# Этап 1. Концепт-лист в Codex: строгие правила, промпт-паки, приёмка

> Справочник скилла `3d-model-pipeline`. Этапы (номера только эти): 0 заявка → **1 концепт-лист (этот файл)** →
> 2 генерация Tripo H2 → 3 сборка в Blender (H2-bake, look-dev, TeamAccent) → 4 приёмка модели → 5 доработка в
> Blender → 6 анимация, VFX, SFX → 7 упаковка, импорт в UE, подключение S08.
>
> Норма производства — `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (дальше HANDBOOK): он главнее этого файла.
> Здесь только то, чего в HANDBOOK нет: строгие правила набора видов и сетки, готовые промпт-паки, запуск Codex,
> ретраи и приёмка листа с коэффициентом. Рецепт видов — HANDBOOK §3.1 (рецепт hero-quality-v1).
>
> Историческое, не образец: холст 1024×1024, фон `#808080`, линия земли y=917, нормализация `normalize-*.py` и
> `tools/tripo-pipeline/check_inputs.py` относятся к входам `art/imagegen/mvp-v1` (HANDBOOK §1 «Не использовать как
> образец», §3.1). На этапе 1 они не применяются.

## 1. Вход, выход, критерий

| | |
|---|---|
| Вход | `<ASSET_DIR>/asset-card.yaml` этапа 0 со всеми полями (раздел 9 этого файла перечисляет, какие поля нужны) |
| Выход | пакет `art/imagegen/concept-<CONTENT_KEY>-codex/` с видами `<key>-front.png`, `<key>-side.png`, `<key>-back.png` (набор пропа — раздел 4.1), лист `sheet-<key>.png`, `checks-report.json`, записи генераций; карточка приёмки листа |
| Критерий выхода | `check_concept_views.py` — 0 FAIL, коэффициент листа ≥ 8.0 без вето (раздел 11) |
| Исполнители | Codex — генерация (раздел 5); запускающий агент — шаг 1b, проверки, журнал, коммит; приёмщик «Opus xhigh» или «Sol 6.1 xhigh» — коэффициент (вызов — `acceptance-and-blender.md`). Приёмщик нужен уже на шаге 1a; его доступность проверена на этапе 0 пробой с командой и критерием (SKILL.md §6, этап 0 п.4: Workflow — объект `{"ok": true}` по схеме; Claude in Chrome — список вкладок и открытая Studio) |

Стоп этапа 1 с вопросом пользователю — только гейты стопа скилла (SKILL.md): Codex не запустился после попытки по
разделу 5; кредитов Tripo не хватает на черновик или две черновые генерации подряд неудачны; исчерпаны генерации или
циклы (раздел 10). Анатомия вне контракта рига (не гуманоид и не крылатый бипед) сюда не доходит: это стоп этапа 0.
Сбой инструмента или окружения (код 2 `check_concept_views.py`, сбой песочницы Codex, карточка «СБОЙ ОКРУЖЕНИЯ»,
раздел 11) — не вопрос пользователю, а разбор оркестратором: причина, фикс или опция инструмента, строка F в NOTES
(ДС-2, `docs/game-design/decisions/2026-10-14-skill-refinement-delegated-decisions.md`).

## 2. Схема этапа

| Шаг | Что | Кто | Выход |
|---|---|---|---|
| 1a | Дизайн-front: text→image с эталоном качества; подставка описана словами (раздел 6.2) | Codex по заданию `<ASSET_ID>-concept.codex.md` | `design/<key>-front.png` |
| 1a-приёмка | Коэффициент дизайна: S, Q, P; C по фиксированному правилу 1a = 1,5 (раздел 11); порог 8.0, вето < 1.0 | приёмщик | карточка `…/acceptance-concept/<YYYYMMDD>-front-r<N>/card.json` |
| 1b | Черновая модель Tripo по дизайн-front → ортопроекции | запускающий агент | `<YYYYMMDD>-draft-tripo/orthos/ortho_{front,left,right,back}.png` + `ortho-framing.json` |
| 1c | Виды поверх орто (style-transfer), лист-сетка, автопроверки | Codex по заданию `<ASSET_ID>-concept-views.codex.md` | `<key>-{front,side,back}.png`, `sheet-<key>.png`, `checks-report.json` |
| 1c-приёмка | Коэффициент листа: S, C, Q, P | приёмщик | карточка `…/acceptance-concept/<YYYYMMDD>-sheet-r<N>/card.json` |

Дизайн принимается до трат Tripo: шаг 1b не начинается без pass карточки 1a.

Проп с осевой симметрией (бочка, колонна) пропускает 1b: `<key>-front.png` — побайтовая копия принятого дизайна,
`<key>-side.png` рисуется ядром PROP-ROTATE (раздел 8.3). Асимметричный проп идёт через 1b.

## 3. Папки и файлы

Раскладка — договор пакета `docs/game-design/visual/07-prompt-templates.md` §1.1 с `{{set}}` = `concept-<CONTENT_KEY>`.

```text
docs/game-design/visual/06-tasks/prompts/
  <ASSET_ID>-concept.codex.md              задание 1a (пишет Claude)
  <ASSET_ID>-concept-views.codex.md        задание 1c (пишет Claude)
  <ASSET_ID>-concept[-views].fix<N>.codex.md   корректирующие запуски (образец AN-22.fix1.codex.md)

art/imagegen/concept-<CONTENT_KEY>-codex/  пакет Codex; Codex пишет только сюда и не коммитит
  palette.json                 палитра карточки; пишет Claude до первого запуска (раздел 4.5)
  README.md                    по-русски: что сделано, выбор по видам, что не вышло, статус «предложено»
  prompts.md                   по образцу art/imagegen/hero-quality-v1/<hero>/prompts.md
  prompts/concept-prompts.json ключ промпта → точный текст
  generation-records.json      каждая генерация (поля — блок B-CONCEPT-PACKAGE, раздел 5.4)
  concepts/<key>-<view>-g<N>.png   сырой результат каждой генерации, побайтно; не перезаписывается;
                               view = design-front (1a) | front | side | back (1c)
  checks/<view>-g<N>/checks-report.json   проверка каждого кандидата (--out этого каталога); не перезаписывается,
                               view и N — как у concepts/ (design-front-g1, front-g2, …)
  design/<key>-front.png       копия выбранного дизайна 1a
  design/checks-report.json    проверка ВЫБРАННОГО дизайна 1a (последний прогон шага 1a, с --min-top-pct 4)
  <key>-front.png, <key>-side.png, <key>-back.png   копии выбранных генераций 1c (побайтно из concepts/)
  checks-report.json, sheet-<key>.png   проверка ВЫБРАННОГО набора 1c (последний прогон, с --sheet)
  verification.json, manifest-sha256.json, source-hashes-before.json   по 07 §1.1–1.2

art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/   шаг 1b (пишет запускающий агент)
  source/<key>-draft-tripo-<task8>.glb   GLB черновика (в per-asset .gitignore этапа 0; имя — tripo3d-stages.md §5.2)
  orthos/ortho_<view>.png, orthos/ortho-framing.json   выход draft_orthos.py (в git)
art/pipeline-candidates/<ASSET_ID>/source-specs/tripo-<task8>-draft.json   source-spec черновика (tripo3d-stages.md §5.2)
art/pipeline-candidates/<ASSET_ID>/evidence/acceptance-concept/<YYYYMMDD>-front-r<N>/card.json   приёмка 1a
art/pipeline-candidates/<ASSET_ID>/evidence/acceptance-concept/<YYYYMMDD>-sheet-r<N>/card.json   приёмка 1c
```

Имена каталогов карточек — как в SKILL.md §9 (`<YYYYMMDD>-<front|sheet>-r<N>`). Орто лежат в каталоге черновика, не в
пакете Codex: Codex получает их как входы задания 1c (раздел 8.1).

Проверка кандидата пишет отчёт только в свой `checks/<view>-g<N>/`: без `--out` каждый прогон перезаписывал бы
`design/checks-report.json` (живой тест 2026-10-09), и отчёт выбранного вида терялся бы за отчётом последнего
кандидата. Отчёты выбранного дизайна и набора (`design/checks-report.json`, корневой `checks-report.json`) — это те,
что идут в карточку приёмки (раздел 11, `frames`, `reports`, гейт `G-CHECKS`).

**Кодировка.** Все текстовые файлы пакета (JSON, Markdown) — UTF-8 без BOM. Codex пишет их из Python
(`Path.write_text(…, encoding="utf-8")`, `json.dumps(…, ensure_ascii=False)`), а не перенаправлением PowerShell
(`>`, `Out-File`, `Set-Content`) и не пайпом с кириллицей: в живом тесте 2026-10-09 так кириллица `verification.json`
стала «??????????». Проверка — раздел 5.5 п.2.

`<key>` = `CONTENT_KEY`. Имя `side` в файле одно для левого и правого профиля; какой бок нарисован, записано в
`SIDE_VIEW` карточки, в `prompts.md` и в `generation-records.json` (`view: "side"`, `side_view: left|right`).
Шаблон `07 §3.1 T-CODEX-HEROVIEWS` («три вида на одном листе») в этом пайплайне не применяется: вид — отдельный файл.
Его id используется только в журнале трат (раздел 5.5).

## 4. Строгие правила набора

### 4.1 Виды и слоты Tripo

| ANATOMY / ROLE | Виды набора | Слоты Tripo на этапе 2 |
|---|---|---|
| humanoid, winged-biped | front, side, back | `front` ← front, слот `<SIDE_VIEW>` ← side, `back` ← back; второй боковой слот пуст |
| prop, осесимметричный | front, side (`SIDE_VIEW` = left) | `front`, `left` |
| prop, асимметричный | front, back | `front`, `back` |

**Правило слота (одно, без исключений): слот Tripo = бок, который фактически нарисован** (`SIDE_VIEW`). `left` —
собственный левый бок фигуры к камере, лицо к левому краю кадра; `right` — зеркально. Левый вид в слот RIGHT (и
наоборот) запрещён: Tripo строит фантомы. Доказательства: HANDBOOK §3.2 п. 3 (второй меч, вторая рука и лицо у
Arthur, двуликая голова у Harpy); `art/pipeline-candidates/ASSET-HARPY-001/source-specs/tripo-bca735a3-h3.json`
`slot_note` (левый вид в RIGHT у H2 330872a3 → двуликая голова; H3 с тем же видом в LEFT — без дефекта). Соглашение
«`left` = левый бок персонажа к камере» проверено на mvp-v1-комплектах четырёх героев
(`docs/art-pipeline/imagegen-inputs/CONSISTENCY-REVIEW.md:60`).

**Выбор SIDE_VIEW (канон скилла; этот файл — владелец правила).**
- Этап 0 ставит `SIDE_VIEW: left` (дефолт по делегированию). Это совпадает с HANDBOOK §3.2 п. 3 (side → LEFT,
  RIGHT пусто).
- Шаг 1b может сменить его на `right` ровно в одном случае: `WEAPON_HAND = right` и на `ortho_left.png` кисть с
  оружием и хват закрыты корпусом. Решает запускающий агент глазами по `ortho_left.png`, пишет новое значение в
  `asset-card.yaml` с `decided_by` и причиной. Дальше `SIDE_VIEW` не меняется: 1c рисует этот бок, этап 2 кладёт его в
  одноимённый слот.
- Случай `right` — **решение скилла, отступление от HANDBOOK §3.2 п. 3**. Основание — прецедент Merlin: правый вид в
  слоте RIGHT, без фантомов (`art/pipeline-candidates/ASSET-MERLIN-001/source-specs/tripo-de0654b5-h2.json` `slot_note`:
  «Боковой концепт — правый вид (prompts.md), подан в слот RIGHT: согласовано (как у прежнего H3.1 Merlin d9ff4260)»).
  Запрещено по HANDBOOK только несоответствие бока и слота; оно здесь исключено.
- Виды `three-quarter` и `top` не делаются.

### 4.2 Холст и размещение («сетка» в числах)

- Размер в пикселях не задаётся и не проверяется против числа: `image_gen` размер игнорирует (квадрат → 1254×1254,
  проверено 2026-10-09 и 109 сырыми PNG `art/imagegen/mvp-v1`). Аспект задаётся только текстом промпта, и инструмент
  его держит: принятые наборы — Medusa 1021×1540, Arthur и Merlin 1190×1322, Harpy 1470×1070 (HANDBOOK §3.1).
- Аспект набора (решение скилла): `3:4` портрет; `4:3` ландшафт для `winged-biped` (крылья вширь, как у Harpy).
  Этот же аспект получают ортопроекции 1b (`draft_orthos.py --aspect`).
- Выход `image_gen` не правится: ни ресайза, ни обрезки, ни перекраски, ни пересохранения. Нормализации нет.
- Все виды набора — один размер и аспект; один ровный нейтральный тёмно-серый фон; фигура с подставкой целиком.
- Размещение в % кадра одинаково во всех видах: центр подставки по x, низ подставки по y, верхняя точка по y. На 1a —
  фиксированные числа ядра: подставка по центру, низ на y 93 %, верхняя точка не выше y 4 %, то есть её y ≥ 4 %
  (не ближе 4 % высоты к верхнему краю; нарушение — WARN `view.frame_top` проверки с `--min-top-pct 4`, раздел 4.3;
  живой тест 2026-10-09 дал 3,3 %) (решение скилла по
  принятым наборам `hero-quality-v1/*/prompts.md`: верх меча Arthur y 3–4,2 %; низ подставки от y 90,2 % у Harpy до
  y 96,8 % у Medusa). На 1c — числа из `ortho-framing.json` шага 1b (маппинг — раздел 7, п. 5): все орто сняты одной
  камерой и одним масштабом, поэтому y-числа и центр подставки у всех видов общие, по видам различается только ширина
  подставки.
- Рост в пикселях не нормируется. Проверяется разброс роста между видами: > 3 % — WARN, > 5 % — FAIL (раздел 4.3).
  Рост = низ подставки − верх маски по всей маске, включая оружие. Верхняя точка жёсткой фигуры в горизонтальной
  ортопроекции одна и та же во всех видах, поэтому оружие выше головы (лук, посох) измерение не ломает.
- Сетки в файлах видов нет. Сетка — на листе приёмки `sheet-<key>.png`, который рисует `check_concept_views.py --sheet`:
  виды в ряд по общей линии земли, направляющие `#00C8FF` через все виды, линейка в % высоты кадра, свотчи палитры с
  hex. Сетка scratch-потока (1 см / 5 см, `docs/art-pipeline/SCRATCH-MODEL-PIPELINE.md:137`) сюда не переносится: там
  сетка нужна для чертежа по сантиметрам, здесь виды рисуются поверх ортопроекции и сетка в виде не нужна.

### 4.3 Автопроверки и допуски

```bash
export PYTHONIOENCODING=utf-8   # страховка для чтения кириллицы; инструмент сам переключает вывод на UTF-8
python tools/art/concept/check_concept_views.py --set art/imagegen/concept-<key>-codex --key <key> \
    --views front,side,back --role hero --palette art/imagegen/concept-<key>-codex/palette.json --sheet
# читает <set>/<key>-<view>.png (не меняет); пишет <set>/checks-report.json (unmatched.concept-checks/1)
# и <set>/sheet-<key>.png; код 0 = 0 FAIL, 1 = есть FAIL, 2 = ошибка входа или сбой инструмента
```

Код 2 — не FAIL набора: виды не перегенерируются, текст ошибки (stderr) идёт в `verification.json`, разбирает
запускающий агент. Пайп cp1251 (Codex через PowerShell, Git Bash агента) инструмент не роняет: `main()` переключает
stdout/stderr на UTF-8, непойманный сбой даёт код 2 (тесты `tools/art/concept/tests`, `test_cli_cp1251_*`).

`--role`: `hero` (humanoid), `creature` (winged-biped), `prop`. `--views`: набор из раздела 4.1. Для одного вида
(дизайн 1a, проверка кандидата 1c) — `--views <вид>` с `--set` папки этого вида. `--out <каталог>` — куда писать отчёт
(кандидат — `checks/<view>-g<N>/`, перепроверка запускающего — вне пакета; раздел 3, 5.5). `--min-top-pct 4` — только
на 1a: рамка ядра CORE-1A, WARN `view.frame_top` (`tools/art/concept/README.md`).

Допуски двухступенчатые (решение скилла): исходное число — порог WARN, FAIL — наблюдаемый максимум четырёх принятых наборов
`art/imagegen/hero-quality-v1/` плюс запас (калибровка 2026-10-09; все четыре набора дают 0 FAIL). Источник чисел —
`TOLERANCES` в `tools/art/concept/check_concept_views.py:36` и таблица проверок `tools/art/concept/README.md`; при
расхождении с этой таблицей действует инструмент (`tolerances` в `checks-report.json`).

| Проверка (`id` в отчёте) | WARN | FAIL |
|---|---|---|
| Размер видов (`set.size`, `set.size_exact`) | различие хоть на 1 px | различие > 0,5 % по стороне |
| Рамка 2 % короткой стороны (`view.border_uniform`) | < 99 % рамки в ±12 от медианы | < 99 % рамки в ±20 |
| Фон нейтральный (`view.bg_neutral`) | — | \|R−G\| или \|G−B\| медианы рамки > 6 |
| Фон тёмно-серый (`view.bg_dark`) | яркость медианы > 96 | — |
| Один фон на набор (`set.bg_same`) | — | медианы фона видов различаются > 12 |
| Поля (`view.top_margin`, `view.bottom_margin`, `view.side_margin`) | — | верх < 1 % высоты; низ подставки > 99 %; маска ближе 1 % ширины к боку |
| Рамка 1a (`view.frame_top`, только с `--min-top-pct 4`) | верх маски < 4 % высоты | — |
| Маска (`view.mask`) | — | вне 2–90 % кадра |
| Низ подставки между видами (`set.base_bottom`) | > 1,5 % высоты | > 3,5 % |
| Центр подставки между видами (`set.base_center`) | > 2,0 % ширины | > 6,5 % |
| Рост между видами (`set.height`) | > 3,0 % | > 5,0 % |
| Связность (`view.single_component`) | прочая компонента ≥ 0,5 % кадра | — |
| Прозрачность (`view.alpha`) | есть альфа | — |
| Ракурс side (`view.facing`, только с `--side-ortho <orthos>/ortho_<SIDE_VIEW>.png`, шаг 1c) | разница IoU прямо/зеркало < 0,05 или оба IoU < 0,5 | IoU с зеркалом орто больше прямого на 0,05 (вид нарисован с другой стороны, F8) |

**WARN — не повод для ретрая и не CORRECTION.** WARN видит приёмщик на листе и в отчёте и учитывает в измерении C.
Перегенерация по автопроверкам — только при FAIL (раздел 10). Пример: канон Medusa имеет центр подставки с разбросом
5,61 % и рост 4,10 % — это WARN, не FAIL (`tools/art/concept/README.md`, «Разброс между видами»).

Ориентир, не гейт: IoU силуэта front против зеркального back (у mvp-v1-комплектов четырёх героев 0,89–0,94,
`CONSISTENCY-REVIEW.md:54`; там же — «ориентир на перспективных изображениях»). Высокий IoU не доказывает одну
3D-форму; решают глаза приёмщика.

### 4.4 Поза и сторона оружия

Поза — НЕ T и НЕ A: rest-поза рига = поза миниатюры, в которой смоделирован меш (`docs/art-pipeline/rig/rig-contract.json`
`rest_pose`: «не T/A-поза»; HANDBOOK §2.6). Меш из A-позного концепта стал бы позой фигуры на доске.

| ANATOMY | `{{POSE_EN}}` (дословно) |
|---|---|
| humanoid | `Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose.` |
| winged-biped | `Stable standing pose on the pedestal. The wings are the arms: exactly two wings, spread sideways and swept back, each clearly separated from the body; no separate human arms or hands; not a T-pose.` |
| prop | `Upright, in its natural resting orientation; all hardware such as hinges, latches and handles is visible from the front.` |

Крыло = цепочка руки (HANDBOOK §2.6, «Harpy: крылья = цепочка arm_upper → arm_lower → hand»). Крылья и отдельные руки
одновременно — новая кость, гейт стопа этапа 0. Позы четвероногих и многоголовых (все лапы на подставке, спина
горизонтальна, число голов — якорь всех видов) действуют только после принятия rig-contract/3; до того такой ассет
останавливается на этапе 0.

Колчан и ножны по умолчанию — на стороне, противоположной `WEAPON_HAND` (натягивающая или свободная рука;
правило — раздел 9, `{{ANCHORS_EN}}`).

Сторона оружия — параметр `WEAPON_HAND` во всех формулировках (`rig-contract.json:57-60`: Medusa лук `weapon.L`,
Arthur и Merlin `weapon.R`, Harpy без оружия):

| WEAPON_HAND | `{{WEAPON_SIDE_EN}}` | `{{BACK_WEAPON_EN}}` |
|---|---|---|
| right | `The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.` | `The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.` |
| left | `The weapon is held in the figure's own LEFT hand, which appears on the viewer's RIGHT in the front view.` | `The weapon in the figure's own LEFT hand appears on the viewer's LEFT.` |
| none | `No weapon or held object.` | пусто |

Проверено на mvp-v1-наборах: меч Arthur в правой руке — слева в кадре на front, справа на back; лук Medusa в левой —
справа на front, слева на back (`CONSISTENCY-REVIEW.md:71,86`; срез 2026-09-28, ни один из этих комплектов не принят
художественно). То же в принятых наборах hero-quality-v1: «sword on viewer RIGHT» на back Arthur, «bow on viewer
LEFT» на back Medusa, посох Merlin «on viewer LEFT» на front и «on viewer RIGHT» на back
(`art/imagegen/hero-quality-v1/{king-arthur,medusa,merlin}/prompts.md`).

### 4.5 Свет, фон, палитра, запреты

- Фон: ровный нейтральный тёмно-серый, без градиента, виньетки, пола и падающей тени на фон. Свет мягкий ровный
  студийный, без сильного контрового и без глубины резкости. Тёмно-серый — по канону hero-quality-v1 (HANDBOOK §3.1).
  Риск: серый камень подставки на сером фоне — Tripo срезает край (HANDBOOK §3.1, «Проверка комплекта»).
- Палитра: 2–3 основных цвета + 1 акцент, hex из `PALETTE` карточки. Это **решение скилла, отступление от 07 §0.4**
  (`docs/game-design/visual/07-prompt-templates.md:98-103`: «Hex — только из 02 §2»; исключений для фигур там нет).
  Основание: поле `PALETTE` заявки (шаблон `asset-card.yaml` в SKILL.md: 2–3 hex + 1 акцент) и делегирование визуальных решений
  (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`). Токены 02 §2 для палитры фигуры не
  заводятся. Цвет команды на фигуре и кольцо на подставке не рисуются: команда — рантайм-маска TeamAccent и кольцо в
  UE (HANDBOOK §2.9).
- `palette.json` пишет запускающий агент до первого запуска Codex, в форме, которую понимает
  `check_concept_views.py` (`load_palette`, `tools/art/concept/README.md` «palette.json»):
  `{"asset_id": "<ASSET_ID>", "main": [{"name": "midnight blue", "hex": "#1F2A5A"}, {"name": "…", "hex": "#…"}], "accent": {"name": "…", "hex": "#…"}}`.
  Это копия поля `PALETTE` карточки (шаблон SKILL.md §7.2 хранит те же `name` и `hex`); английские имена — те же, что в
  `{{PALETTE_EN}}` (раздел 9).
- Тонкие элементы (тетива, древко, стрелы, посох): в промпте пожелание «clearly readable, not hair-thin»; в
  проверках это не FAIL и не повод для ретрая. Утолщающего режима в генерическом `h2_bake` нет
  (`tools/tripo-pipeline/blender/h2_bake/`; мосты есть только в ручных форках `h2_bake_merlin/`,
  `h2_bake_arthur/repairs.py`). Порядок — по HANDBOOK §4.2, абзац «Оружие», и SKILL.md, этап 3: тонкая или
  нечитаемая после Tripo деталь — запись в отчёт этапа 3 и балл F/T на этапе 4; если нужен мост-цилиндр или сборка
  из частей — это стоп с описанием, а не рутинная доработка.
- Запрещено в промптах: слова «Unmatched», «Digital Edition», имена художников и студий (07 §0.4, ВР-PR07); сканы
  карт, аватары и кадры DE как входы (ВР-PR08). Имя персонажа в `DESCRIPTION_EN` — только для фигур мифов, фольклора
  и общественного достояния; иначе — описание внешности словами (решение скилла).
- Запрещено в изображении: текст, буквы, цифры, логотипы, водяные знаки, рамки, коллаж, несколько видов на кадре,
  лишние фигуры, конечности, головы, крылья и оружие, перспектива, ракурс 3/4 вместо профиля.

## 5. Запуск Codex

### 5.1 Какой путь выбрать

На машине один пакет приложения (`/c/Program Files/WindowsApps/OpenAI.Codex_26.1002.7124.0_x64__2p2nqsd0c76g0/`,
2026-10-09): «exe соседней версии» больше нет. Приложение пользователя (`ChatGPT.exe`) агент не закрывает.
**Основной путь — `codex.exe exec` (5.2)**: он проверен живым тестом этапа 1a 2026-10-09 и даёт файл `-o` для проверки
результата. Приложение через управление рабочим столом (5.3) — только когда `exec` не проходит пробу.

| Состояние | Путь |
|---|---|
| `exec` проходит пробу (5.2, шаг 2 или 3) | 5.2, `codex.exe exec` — основной |
| `exec` занят и копией («used by another process») или проба не проходит, приложение открыто | 5.3, приложение через управление рабочим столом |
| `exec` недоступен, управление рабочим столом запрещено правами сессии | стоп SKILL.md §5 п.2, пакет пользователю |

### 5.2 `codex.exe exec`

```bash
REPO="C:/Users/ren/WebstormProjects/unmached/unmached"
# 1. Кандидаты. Приложение запускает свою копию из %LOCALAPPDATA%/OpenAI/Codex/bin/<hash>/codex.exe. Каталог и
#    версия меняются с обновлением (2026-10-09 — 9691020b…, 0.162.0-alpha.2; 2026-10-13 — 2e5e00daee91c61d,
#    0.162.0-alpha.17.2): путь только глобом, хэш и версию не закреплять (F37). npm-codex не работает (07 §1.1).
EXE=$(ls -t /c/Users/ren/AppData/Local/OpenAI/Codex/bin/*/codex.exe | head -1); echo "$EXE"   # самый свежий exe
# 2. Проба exec С КОМАНДОЙ (не «Reply OK»: модель ответит и без песочницы, сбой останется скрытым). Флаг
#    windows.sandbox="unelevated" обязателен на этой машине (ниже). Проба прошла, если в событиях есть
#    command_execution с "exit_code":0.
"$EXE" exec --ignore-user-config -m gpt-6.1-sol -c 'model_reasoning_effort="low"' -c 'windows.sandbox="unelevated"' \
    -s read-only --skip-git-repo-check -C "$REPO" --json \
    "Run exactly one shell command: Get-Content -TotalCount 1 AGENTS.md . Reply with its output only." </dev/null \
  | grep -q '"type":"command_execution".*"exit_code":0' && echo "PROBE OK" || echo "PROBE FAIL"
# 3. Ответ «used by another process» → копия exe вне каталога приложения и та же проба копией
mkdir -p C:/tmp/codex-bin && cp "$EXE" C:/tmp/codex-bin/codex.exe && EXE=C:/tmp/codex-bin/codex.exe
# 4. Рабочий запуск задания (в фоне; процесс по PID завершить, если он пережил свою задачу)
mkdir -p C:/tmp/skill-concept/<ASSET_ID>
"$EXE" exec -C "$REPO" -s workspace-write -c 'windows.sandbox="unelevated"' --skip-git-repo-check \
    -o C:/tmp/skill-concept/<ASSET_ID>/1a-last-message.txt - \
    < docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept.codex.md
```

**Песочница Windows** (проверено 2026-10-09: калибровка приёмки и живой тест этапа 1a). Пока открыто приложение
ChatGPT/Codex, `codex exec` без `-c 'windows.sandbox="unelevated"'` (и с `-s read-only`, и с `-s workspace-write`) не
запускает ни одной команды: каждый `command_execution` заканчивается `Failed to create unified exec process:
helper_unknown_error: setup refresh had errors` (`codex-windows-sandbox-setup.exe` не может сменить ACL файлов, которые
держит приложение, «os error 32», `~/.codex/.sandbox/sandbox.<дата>.log`). Код выхода при этом 0: задание этапа 1a дало
0 генераций, приёмщик — карточку-заглушку. С флагом: этап 1a — код 0, 2 из 2 генераций за 6 мин 13 с; чтение в
`read-only` работает, запись запрещена (`PermissionDenied`). Поэтому флаг стоит во всех трёх командах (проба, задание,
приёмщик `references/acceptance-and-blender.md` §8.4), а проба обязана выполнить команду.

**Код 0 — ещё не успех.** `codex exec` возвращает 0 и при сбое песочницы, и при остановке на блокере. Результат
задания проверяется по файлам пакета (5.5, п.0): есть новые `concepts/*.png`, файл `-o` (последнее сообщение) не
сообщает о блокере, `verification.json` записан.

`--ignore-user-config` в пробе отключает пользовательский `~/.codex/config.toml` (MCP-серверы, хуки, плагины —
шум в stderr); модель задаётся `-m`. В рабочем запуске этапа 1 флаг не ставится: `image_gen` и настройки задания идут
из конфига пользователя (так проверено). Приёмщику флаг нужен (§8.4 рубрики модели). Цена конфига пользователя —
его хуки: процесс генератора висит до 23 мин после ответа (пилот, 1c: +977…+1408 с; RC-11). Задание готово, когда
файл `-o` не пуст (5.5 п.0); свой процесс после этого гасить по PID (дерево процессов, не по имени). В пачке это
делает `codex_lane.py` (5.6).

Проверено 2026-10-09: `--version` exe из `%LOCALAPPDATA%` и из пакета → `codex-cli 0.162.0-alpha.2`, код 0; позиционный
`[PROMPT]` и `-` (stdin) — `codex.exe exec --help`; `exec` exe из `%LOCALAPPDATA%` **при открытом приложении работает**
(проба 12–15 с, шаг 3 с копией не понадобился, «used by another process» не было); `image_gen` в рабочем запуске —
~27 с на вызов (exe 0.160.1) и 2 генерации за 6 мин (exe 0.162.0, с флагом песочницы). Exe пакета 26.1002 при открытом
приложении — «used by another process». Из PowerShell: `Get-Content <prompt> -Raw -Encoding UTF8 | & $exe exec …` при
`$OutputEncoding` и `[Console]::OutputEncoding` = UTF-8 без BOM (иначе кириллица промпта уходит как «?»), запуск
`powershell -NoProfile`.

### 5.3 Приложение через управление рабочим столом

Приложение ChatGPT (пакет OpenAI.Codex) → Ctrl+N в проекте `unmached` → сообщение
«Прочитай `docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept.codex.md` и выполни задачу» (07 §1.1).
Инструмент — computer-use (`mcp__computer-use__*`: `request_access` на приложение ChatGPT, затем `key` ctrl+n, `type`,
`key` Return; отложенные инструменты подгружаются одним `ToolSearch` с запросом `computer-use`) или Windows-MCP
(`mcp__Windows-MCP__App`, `Shortcut`, `Type`). Результат проверяется по файлам пакета (раздел 5.5), не по окну.
Отказ в доступе или блок классификатора прав → стоп SKILL.md §5 п.2.

Codex недоступен после попытки обоими путями → стоп с пакетом пользователю (файл задания, команды 5.2 и их вывод).
Замена генератора (SYNTX по HANDBOOK §3.1) — только по ответу пользователя на этот стоп.

### 5.4 Блок B-CONCEPT-PACKAGE

Вставляется в каждое задание этапа 1 целиком. Это договор 07 §1.1 (`[[B-PACKAGE]]`) без строк про значки
`hud-icons-v3`, векторные финалы и серые листы — они относятся к UI, не к концептам.

```text
Package contract.
- Write ONLY inside art/imagegen/concept-{{CONTENT_KEY}}-codex/. Nothing else on disk changes. Files there that you
  did not create (palette.json, earlier runs) stay as they are unless this task says otherwise.
- No git commands at all (no add, commit, stash, reset, checkout, branch). Claude reviews and commits.
- Do not open, edit or build anything under unreal/. No Unreal, no Tripo, no SYNTX, no downloads.
- Inputs are only the files listed in this task. Card scans, hero avatars, card art and frames of commercial digital
  editions are never inputs.
- Before work, record sha256 of every input in source-hashes-before.json (a corrective run appends a new block and
  keeps the old one); after work, prove in verification.json that the inputs are unchanged.
- One image_gen call = one image = one view. Do not pass a size: the tool chooses the pixels; ask for the aspect ratio
  in the prompt text only.
- Never retouch, resize, crop, recolour or re-encode a generated image. image_gen saves its own copy outside the
  package: copy each result byte for byte into concepts/{{CONTENT_KEY}}-<view>-g<N>.png at once, leave the tool's copy
  where it is, and log both paths. Never overwrite a file in concepts/.
- Check every candidate into its own folder: check_concept_views.py ... --out
  art/imagegen/concept-{{CONTENT_KEY}}-codex/checks/<view>-g<N> (the same <view>-g<N> as its concepts/ file). Only
  the final run on the selected file(s) writes the report without --out.
- Log every generation in generation-records.json: id, card_id ({{ASSET_ID}}), stage (1a or 1c), view, side_view,
  attempt, tool, mode, references [{path, sha256}] in call order, prompt_key, correction (null or its lines),
  original_path, saved_path, sha256, width, height, date, selected.
- Every path you write into a record (references, saved_path, checks) is relative to the repository root with
  forward slashes (art/imagegen/concept-{{CONTENT_KEY}}-codex/concepts/...), except original_path, which is the
  absolute path where image_gen saved its own copy.
- Save the exact prompt of every generation in prompts/concept-prompts.json (prompt_key "<stage>/<view>/g<N>" -> text)
  and in prompts.md: date, tool, then per file the referenced_image_paths in order, the exact prompt, and a closing
  section "Проверка и ограничения" (what matches between views, what changed).
- README.md in Russian: what was done, which generation is selected per view and why, what failed, status
  "предложено". A limit you could not meet goes into verification.json, not hidden.
- verification.json: source_unchanged, outside_folder (must be []), checks [{view, generation, exit_code,
  report}] for every run of check_concept_views.py, checklist [{view, item, passed, note}] for the selected file of
  each view, generations per view, limit_reached [{view, failed_items}] (empty list when no view ran out of
  generations with a failed CHECKLIST item).
- Encoding: write every text file of the package (JSON, Markdown) from Python as UTF-8 without BOM
  (Path.write_text(text, encoding="utf-8"); json.dumps(data, ensure_ascii=False, indent=2)). Never write a package
  file through PowerShell redirection (>, Out-File, Set-Content) or pipe Cyrillic text through the shell: it turns
  into "????".
- Write manifest-sha256.json last: sha256 and bytes of every package file except itself.
- Small decisions are yours; write them in README.md. Stop only on blockers (login, captcha, payment, image_gen
  unavailable).
```

В задание блок вставляется уже заполненным: `{{ASSET_ID}}` и `{{CONTENT_KEY}}` подставлены, `<view>`, `<N>`,
`<stage>` остаются — это переменные рантайма, их значение выбирает Codex во время запуска (раздел 9, «Два вида
переменных»).

### 5.5 После каждого запуска Codex (запускающий агент)

0. **Результат, а не код выхода** (код 0 `codex exec` ничего не доказывает, 5.2). Прочитать файл `-o`
   (`C:/tmp/skill-concept/<ASSET_ID>/<шаг>-last-message.txt`): нет сообщения о блокере. В `concepts/` есть новые
   `*.png` этого запуска (сравнить со списком до запуска), `verification.json` записан. Нет новых PNG — запуск не
   состоялся: это не генерация и не цикл; разобрать причину (песочница — флаг 5.2; блокер — его текст), повторить
   запуск или перейти к 5.3. Путь 5.3 даёт тот же результат по файлам, без файла `-o`.
1. Открыть глазами (Read) каждый новый вид и лист; трассам и отчёту Codex не верить на слово.
2. **Перепроверка вне пакета.** Перезапустить `check_concept_views.py` с аргументами последнего прогона Codex, но
   с `--out` во временный каталог: прогон без `--out` перезаписал бы отчёт пакета (`generated_at`), и манифест п.3
   перестал бы совпадать (живой тест 2026-10-09: вечный fix-запуск). Сравнить с отчётом пакета без `generated_at` и
   путей — по sha256 входов, проверкам, сводке, вердикту и рамке:

```bash
K=<key>; P=art/imagegen/concept-$K-codex; T=C:/tmp/skill-concept/<ASSET_ID>/recheck
# 1a (выбранный дизайн)
python tools/art/concept/check_concept_views.py --set $P/design --key $K --views front --role <role> \
    --min-top-pct 4 --out $T/1a
# 1c (выбранный набор)
python tools/art/concept/check_concept_views.py --set $P --key $K --views <views> --role <role> \
    --palette $P/palette.json --sheet --out $T/1c
# сравнение (A — отчёт пакета, B — перепроверка): "same" и код 0
python -c "import json,sys;f=lambda p:(lambda d:([i['sha256'] for i in d['inputs']],d['checks'],d['summary'],d['verdict'],d.get('frame')))(json.load(open(p,encoding='utf-8')));a,b=map(f,sys.argv[1:3]);print('same' if a==b else 'DIFFERENT');sys.exit(a!=b)" \
    $P/design/checks-report.json $T/1a/checks-report.json      # 1c: $P/checks-report.json $T/1c/checks-report.json
```

   `DIFFERENT` — отчёт пакета не от выбранных файлов: корректирующий запуск на записи (п.3).

   **Ракурс side (1c, F8).** Отдельным прогоном вне пакета (в сравнение выше он не входит, иначе отчёты разойдутся):

```bash
python tools/art/concept/check_concept_views.py --set $P --key $K --views side --role <role> \
    --side-ortho art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/orthos/ortho_<SIDE_VIEW>.png --out $T/facing
# код 1 и FAIL view.facing — side нарисован зеркально (IoU с зеркалом орто больше прямого на 0,05; пилот 2026-10-14:
# прямо 0,96–0,97, зеркало 0,56–0,67): брак вида, корректирующий запуск 1c этого вида; на этап 2 не идёт
# (tripo3d-stages.md §5.5). WARN (разница меньше 0,05 или оба IoU < 0,5) — смотрит приёмщик
```

   Затем кодировка текстовых файлов пакета (раздел 3, «Кодировка») — `UTF8 OK` и код 0:

```bash
python -c "import pathlib,sys;bad=[str(p) for p in pathlib.Path(sys.argv[1]).rglob('*') if p.suffix in ('.json','.md') and (p.read_bytes()[:3]==b'\xef\xbb\xbf' or '????' in p.read_bytes().decode('utf-8','replace') or '\ufffd' in p.read_bytes().decode('utf-8','replace'))];print('\n'.join(bad) or 'UTF8 OK');sys.exit(bool(bad))" \
    art/imagegen/concept-<key>-codex
```

   Файл в списке — корректирующий запуск на записи (п.3): Codex переписывает его из Python в UTF-8. Изменения вне
   пакета за время прогона (`git status --porcelain` до и после; файлы параллельных сессий не в счёт) сверить с
   `verification.json.outside_folder`.
3. **Сверка записей (предусловие приёмки; гейтом карточки не является — раздел 11):** у каждого
   выбранного вида (`selected: true`) есть запись в `generation-records.json` с `prompt_key`, точным текстом в
   `prompts/concept-prompts.json`, ссылками по порядку (пути от корня репо) и sha256; файл вида побайтно равен своему
   `concepts/…` (sha256 совпадает); у каждого кандидата есть `checks/<view>-g<N>/checks-report.json`;
   `manifest-sha256.json` совпадает с файлами пакета. Хоть одно расхождение — приёмщика не звать: корректирующий
   запуск Codex только на записи (`…fix<N>.codex.md`, без генераций), затем повторить п. 0–3.
4. Строка журнала трат (07 §4; Codex — одна строка на пакет-запуск, балансы null):

```bash
python tools/art/visual/ledger.py add --task <VISUAL_CARD_ID> --template T-CODEX-HEROVIEWS --service Codex \
    --model "codex exec gpt-6.1-sol" --image-gen <N> \
    --prompt-file docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept.codex.md \
    --result art/imagegen/concept-<key>-codex/
python tools/art/visual/ledger.py check
```

`--task` — поле `VISUAL_CARD_ID` карточки: id строки `docs/game-design/visual/06-tasks/anim.csv`, заведённой на этапе 0
(SKILL.md §6, этап 0 п. 3). `ledger.py add` отклоняет id, которого нет в таблицах задач (`tools/art/visual/ledger.py:409`).
`--model` — путь и модель этого запуска. Основной путь 5.2: `"codex exec <модель>"`, модель рабочего запуска берётся
из `~/.codex/config.toml` (`model`; 2026-10-09 — `gpt-6.1-sol`, отсюда `"codex exec gpt-6.1-sol"`). Путь через
приложение (5.3): `"Codex app"`.
5. **Генерации запуска исчерпаны, пункт CHECKLIST провален** (`verification.json#limit_reached` не пуст). Если
   проверка `check_concept_views.py` дала 0 FAIL — лист всё равно идёт к приёмке (п.6): провал чек-листа — осмотр
   самого Codex, решает приёмщик. Запускающий добавляет к промпту приёмщика строку «Codex исчерпал генерации запуска;
   проваленные пункты CHECKLIST: <view: пункты из limit_reached>; оцени их по рубрике». Пункт, который приёмщик
   подтвердит, вернётся строкой `rework_fix_list` → CORRECTION следующего цикла (раздел 10). Если же проверка дала
   FAIL (код 1) — приёмщика не звать (гейт `G-CHECKS` FAIL предрешён): корректирующий запуск `…fix<N>.codex.md` на
   этот вид с CORRECTION из FAIL-проверки, пока у вида есть генерации (≤ 4 за этап); нет — раздел 10, `escalate_user`.
6. Приёмка (раздел 11).

### 5.6 Пачка фигур: полосы Codex и пакетная приёмка

Инструменты пачки — `tools/art/pipeline_batch/` (W2-a, ee301065; были `C:/tmp/concept-wave/*`, RA-12, RC-15). Рабочий
каталог пачки — вне git (`W=C:/tmp/concept-wave-<YYYYMMDD>`).

```bash
# 1a: поля этапа 1 asset-card.yaml, palette.json и файлы заданий из файла ростера
python tools/art/pipeline_batch/make_tasks.py --roster <roster.json> --tasks-out $W/tasks-1a.txt [--dry-run]
# полоса Codex: берёт задание по claim-файлу <logs>/<id>.claim, запускает codex exec (команда 5.2, шаг 4);
# 4–5 полос — каждая отдельным фоновым процессом со своим --name; остановка всех — файл <logs>/STOP
python tools/art/pipeline_batch/codex_lane.py --tasks $W/tasks-1a.txt --name d1 --logs $W/logs [--once] [--grace 10]
# 1c: задания по орто 1b; лицензионные фигуры с решением пользователя — в отдельный список (сначала Codex, F7/F8)
python tools/art/pipeline_batch/make_1c.py --tasks-out $W/tasks-1c.txt --ust-out $W/tasks-1c-ust.txt [--only …]
# приёмка листов 1c пачкой (Sol): предпроверка пакета, промпт по разделу 11, codex exec, validate_card
python tools/art/pipeline_batch/sheet_acceptance.py all --work $W --date YYYY-MM-DD [--workers 3] \
    --user-quote "<дословная цитата задачи пользователя>"
# второй приёмщик Opus: сохранённый workflow second-acceptor (acceptance-and-blender.md §8.3) со схемой
# …output-concept…; его вывод {"result": [...]} → снять строки "null" (F6) и посчитать пару validate_card --second
python tools/art/pipeline_batch/finish_second.py <workflow-output.json> [--dry-run]
```

- **Число полос — 4–5** (RC-24). Пилот: 2 полосы — 30 фронтов за 108 мин (3,6 мин на фигуру), 8 полос — 33 за 70 мин
  (2,1 мин на фигуру при задержке втрое больше).
- **Готовность задания** (RC-11). `codex_lane.py` считает задание готовым, когда файл `-o` не пуст и в выводе есть
  «tokens used», и через `--grace` гасит своё дерево процессов по PID. Отдельный `CODEX_HOME` без хуков
  (`--codex-home`) пробой не проверен: перед боевой волной одна проба, что `image_gen` в нём работает.
- **Квота Codex общая** для генерации и приёмщика Sol (RC-12): пилот — 11–15 сессий Codex на фигуру (1a, 1c, приёмки
  листа, модели и клипов). Перед волной — остаток лимита; строка журнала `ledger.py add --service Codex` на каждый
  пакет-запуск и на каждую приёмку (5.5 п.4). Квоты не хватает — приёмщик Opus (другая квота).
- **Шаблоны читаются из этого файла дословно.** `make_tasks.py` и `make_1c.py` берут блоки 5.4, 6.1, 6.2, 8.1, 8.2 по
  заголовкам. После правки этих блоков или заголовков — `--dry-run` обоих: новый плейсхолдер без значения — код 2.
- Промпт пакетной приёмки несёт блок чтения кириллицы раздела 11 (OEM, `cmd /c type`, «СБОЙ ОКРУЖЕНИЯ»):
  `sheet_acceptance.py` исправлен в dd69be64 (был `Get-Content -Encoding UTF8`, сбой RA-03); рубрика вставлена в
  промпт целиком. После правки блока в разделе 11 — сверить его копию в `sheet_acceptance.py`.

## 6. Промпт-пак 1a — дизайн-front

### 6.1 Файл задания `<ASSET_ID>-concept.codex.md`

Пишет запускающий агент: подставляет каждый `{{…}}` (раздел 9) и пишет файл из Python в UTF-8. Переменные рантайма
`<N>`, `<view>`, `<stage>` остаются как есть — их заполняет Codex (раздел 9, «Два вида переменных»). Незаполненный
`{{…}}` — карточка возвращается на этап 0, значение не выдумывается (07 §0.2). Проверка готового файла —
`grep -n '{{' docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept.codex.md` → пусто. Задание — по-английски
(07 §0.4).

Эталона подставки среди входов 1a нет (решение оркестратора 2026-10-09): `ref-base-hero-p1.png` — коллаж трёх
ракурсов под углом сверху, и в живом тесте он тянул камеру вверх (видна верхняя плоскость подставки, пункт «strict
front orthographic» провален в обеих генерациях). Вида подставки строго сбоку в репо нет (`ref-table-base-*-side.png` —
стол доски, не подставка фигуры), поэтому подставка описана словами в `{{PEDESTAL_EN}}` с требованием «seen exactly
edge-on».

````markdown
# {{ASSET_ID}} concept 1a - Codex task (design front)

Written by Claude from {{ASSET_DIR}}/asset-card.yaml by the 3d-model-pipeline skill (references/concept-sheet.md).
The task to execute is the text in the section **Task**. The header is provenance only.

| field | value |
|---|---|
| id | {{ASSET_ID}}-concept (stage 1a) |
| date | {{DATE}} |
| template | concept-sheet.md 1a (ledger template id T-CODEX-HEROVIEWS) |
| package | `art/imagegen/concept-{{CONTENT_KEY}}-codex/` |
| asset card | `{{ASSET_DIR}}/asset-card.yaml`, sha256 {{ASSET_CARD_SHA256}} |
| image generations allowed in this run | {{GENERATIONS_ALLOWED}} |

## Inputs

| # | path | what | sha256 |
|---|---|---|---|
| 1 | `{{QUALITY_REFERENCE}}` | craftsmanship reference (image 1, the only image input) | {{QUALITY_REFERENCE_SHA256}} |
| 2 | `art/imagegen/concept-{{CONTENT_KEY}}-codex/palette.json` | palette of the asset card (not an image input) | {{PALETTE_SHA256}} |

## Task

```text
Task {{ASSET_ID}} concept 1a - one front design of a new collectible miniature (stage 1a of the 3D model pipeline).
{{B_CONCEPT_PACKAGE}}
Run every command from the repository root. PowerShell: set $env:PYTHONIOENCODING='utf-8' first; bash: export
PYTHONIOENCODING=utf-8.
Steps.
1. Generation <N>: call image_gen once with referenced_image_paths = [input 1] and the CORE below exactly as written
   (plus a CORRECTION block only on a retry, step 3). Copy the result to
   concepts/{{CONTENT_KEY}}-design-front-g<N>.png (view design-front, prompt_key 1a/design-front/g<N>).
2. Copy that candidate byte for byte to design/{{CONTENT_KEY}}-front.png and check it into its own folder:
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-{{CONTENT_KEY}}-codex/design --key {{CONTENT_KEY}} --views front --role {{ROLE_ARG}} --min-top-pct 4 --out art/imagegen/concept-{{CONTENT_KEY}}-codex/checks/design-front-g<N>
   Exit 0 = no FAIL (WARN, including view.frame_top, is allowed). Exit 1 = a FAIL check. Exit 2 = input or tool error,
   NOT a FAIL: do not generate again; write the error text into verification.json and stop. Then check the CHECKLIST
   with your eyes.
3. Only if the script exits 1 or a CHECKLIST item fails, and generations remain in this run: generate again with the
   CORE followed by exactly this block, at most 3 lines, each line naming the failed check id or CHECKLIST item, only
   what to fix, never against the CORE:
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate (selected = true in generation-records.json) and copy it byte for byte to
   design/{{CONTENT_KEY}}-front.png. Run the step 2 command on it once more WITHOUT --out: this final run writes
   design/checks-report.json, the report of the selected design.
5. If the generations of this run are used up and a CHECKLIST item still fails, keep the best candidate, record the
   view and the failed items in verification.json limit_reached and in README.md, and finish normally: the acceptor
   decides. This is not a blocker.
6. Write prompts.md, prompts/concept-prompts.json, README.md, verification.json, manifest-sha256.json last.
CHECKLIST (each item passed/failed with a note in verification.json):
- one subject, {{ONE_BASE_EN}}, no collage, no second view, no text, letters, logo or watermark;
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; {{EDGE_ON_CHECK_EN}};
- the whole subject{{AND_PEDESTAL_EN}} visible, nothing cropped; plain flat dark gray background;
- {{WEAPON_SIDE_EN}} {{POSE_CHECK_EN}};
- every identity anchor is visible: {{ANCHORS_EN}};
- main colours and the accent of the palette are present; no team colour, no coloured ring or band on the base.
CORE:
{{CORE_1A}}
Return: at most 10 lines: the selected generation, generations used, the final script exit code, what failed.
```
````

### 6.2 Ядро CORE-1A (отправлять в image_gen дословно; менять только плейсхолдеры)

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: {{DESCRIPTION_EN}}
IDENTITY ANCHORS, each clearly visible: {{ANCHORS_EN}}.
PALETTE: {{PALETTE_EN}}. These are the main colours plus one accent; no other strong colours.
POSE: {{POSE_EN}} {{WEAPON_SIDE_EN}}
{{PEDESTAL_EN}}
VIEW: strict front orthographic view, camera exactly level with the subject at its mid-height (zero elevation, not
looking down), no perspective, no three-quarter turn, the subject faces the camera.
FRAMING: {{ASPECT_EN}}; one isolated subject; the pedestal, or the bottom of the object if it has no pedestal,
centred at x50% with its bottom at y93%; the highest point of the subject or of anything it holds no higher than y4%
(y >= 4%: at least 4% of the image height below the top edge); the whole subject and the whole pedestal visible,
nothing cropped.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background, no gradient, no vignette, no floor, no cast
shadow on the background; soft even studio lighting, no strong rim light, no depth of field.
READABILITY: large clear shapes; arms, wings and held objects separated from the body by visible gaps; thin parts such
as strings, shafts and staffs clearly readable, not hair-thin; fine detail stays inside the silhouette.
FORBIDDEN: text, letters, numbers, logos, watermark, frame, collage or several views, extra figures, extra limbs,
heads, wings or weapons, team colours, a coloured ring or metal band on the pedestal.
Output one single image.
```

## 7. Шаг 1b — черновая модель и ортопроекции

Выполняет запускающий агент после pass карточки 1a.

1. Черновик Tripo — маршрут «Черновик» в `tripo3d-stages.md`: single-image по `design/<key>-front.png`, без 8K и без
   «по частям»; цена с кнопки до клика; перед кликом
   `python tools/art/visual/ledger.py check --service tripo --next-cost <цена с кнопки> --balance <баланс> --model "Tripo Studio H3.1"`
   → код 0 (лимит и срок — из журнала `credits-ledger.json`, решение 2026-10-13 «На триппо нет лимита»; `until: null`
   = окно открыто, поддерживается `ledger.py`; граница — баланс Studio; строка условий Tripo есть —
   `tripo3d-stages.md` §1); после операции — строка журнала и source-spec по тому же файлу. GLB выгружается сразу
   (`tripo3d-stages.md` §5.2 п.11, RC-20) →
   `art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/source/<key>-draft-tripo-<task8>.glb`. Пачка
   черновиков — `prep_1b.py` → `tripo_log.py` → `post_1b.py` (`tripo3d-stages.md` §5.2).
2. Ортопроекции (Blender headless; аспект — раздел 4.2):

```bash
python tools/art/concept/draft_orthos.py \
    --glb art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/source/<key>-draft-tripo-<task8>.glb \
    --out art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/orthos \
    --views front,left,back,right --aspect 3:4
# winged-biped: --aspect 4:3; → orthos/ortho_<view>.png + orthos/ortho-framing.json; код 0 = виды записаны, 1 = ошибка
# (печать в пайп cp1251 инструмент не роняет — вывод переключается на UTF-8)
```

3. Осмотр глазами (Read всех четырёх PNG) против дизайна: `ortho_front` смотрит лицом в камеру; число частей то же;
   оружие в нужной руке (раздел 4.4); нет второй головы, лишней руки, второго оружия; руки отделены от корпуса.
   Дефект черновика → ещё одна черновая генерация. Две неудачные генерации подряд → стоп (гейт кредитов).
4. `SIDE_VIEW` — по правилу раздела 4.1 (смена `left` → `right` только там описанным случаем), запись в карточку.
5. Числа рамки для ядер 1c — из `ortho-framing.json` (`tools/art/concept/_blender_orthos.py:179-205`): блок
   `placement_pct` один на все виды (одна камера, один масштаб, центр подставки всегда x 50 %), по видам — только
   `views.<view>.base_width_pct`. Маппинг (в % кадра, одна цифра после запятой):

| Плейсхолдер | Поле `ortho-framing.json` |
|---|---|
| `{{BASE_X0}}` | `50 − views.<view>.base_width_pct / 2` |
| `{{BASE_X1}}` | `50 + views.<view>.base_width_pct / 2` |
| `{{BASE_TOP_Y}}` | `placement_pct.base_top_y_est` (оценка: пустые слои низкополигональной подставки пропускаются, `_blender_orthos.py:106-126`; осмотр `ortho_left.png` подтверждает) |
| `{{BASE_BOTTOM_Y}}` | `placement_pct.base_bottom_y` |
| `{{TOP_Y}}` | `placement_pct.figure_top_y` |

   `<view>` — ключ ортопроекции: `front`, `back` или значение `SIDE_VIEW` (`left` | `right`). Готовая строка y-чисел
   есть в поле `prompt_hint` (`tools/art/concept/draft_orthos.py:141-144`); x-края по видам считаются по таблице.

## 8. Промпт-пак 1c — виды поверх ортопроекций

### 8.1 Файл задания `<ASSET_ID>-concept-views.codex.md`

Пишется как 6.1: каждый `{{…}}` подставлен, файл — из Python в UTF-8, `grep -n '{{' <файл>` → пусто. Шапка и
таблица входов — как в 6.1 (id `{{ASSET_ID}}-concept-views (stage 1c)`; строка лимита — по каждому виду:
`front 2, side 2, back 2` = `min(2, 4 − генераций вида в generation-records.json)`). Входы — пути от корня репо и
sha256: `{{ORTHO_DIR}}/ortho_front.png`, `{{ORTHO_DIR}}/ortho_{{SIDE_VIEW}}.png`, `{{ORTHO_DIR}}/ortho_back.png`,
`{{ORTHO_DIR}}/ortho-framing.json`, `art/imagegen/concept-{{CONTENT_KEY}}-codex/design/{{CONTENT_KEY}}-front.png`,
`art/imagegen/concept-{{CONTENT_KEY}}-codex/palette.json`; `{{ORTHO_DIR}}` =
`art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/orthos` (шаг 1b).

```text
Task {{ASSET_ID}} concept 1c - {{VIEWS}} views painted over the draft orthographic renders.
{{B_CONCEPT_PACKAGE}}
Run every command from the repository root. PowerShell: set $env:PYTHONIOENCODING='utf-8' first; bash: export
PYTHONIOENCODING=utf-8.
Order: {{VIEWS}}, one view after the other. Per view: at most 2 generations in this run and never more than 4 for the
view in the whole of generation-records.json.
Per view <view>:
1. Call image_gen once with the CORE of that view (plus a CORRECTION block only on a retry, step 3) and its
   references in this order:
   front: [{{ORTHO_DIR}}/ortho_front.png, art/imagegen/concept-{{CONTENT_KEY}}-codex/design/{{CONTENT_KEY}}-front.png]
   side:  [{{ORTHO_DIR}}/ortho_{{SIDE_VIEW}}.png, art/imagegen/concept-{{CONTENT_KEY}}-codex/design/{{CONTENT_KEY}}-front.png]
   back:  [{{ORTHO_DIR}}/ortho_back.png, art/imagegen/concept-{{CONTENT_KEY}}-codex/design/{{CONTENT_KEY}}-front.png, art/imagegen/concept-{{CONTENT_KEY}}-codex/{{CONTENT_KEY}}-side.png]  (a prop without a side view: no third image)
   Copy the result to concepts/{{CONTENT_KEY}}-<view>-g<N>.png (prompt_key 1c/<view>/g<N>) and byte for byte to
   art/imagegen/concept-{{CONTENT_KEY}}-codex/{{CONTENT_KEY}}-<view>.png.
2. Check the candidate into its own folder:
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-{{CONTENT_KEY}}-codex --key {{CONTENT_KEY}} --views <view> --role {{ROLE_ARG}} --out art/imagegen/concept-{{CONTENT_KEY}}-codex/checks/<view>-g<N>
   Exit 0 = no FAIL, 1 = a FAIL check, 2 = input or tool error, NOT a FAIL: on 2 do not generate again; write the
   error text into verification.json and stop. Then check the CHECKLIST of the view with your eyes.
3. Only if the script exits 1 or a CHECKLIST item fails for the view, and generations of the view remain in this run:
   generate the view again with its CORE followed by exactly this block, at most 3 lines, each line naming the
   failed check id or CHECKLIST item, only what to fix, never against the CORE:
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate of the view (selected = true) and copy it byte for byte to art/imagegen/concept-{{CONTENT_KEY}}-codex/{{CONTENT_KEY}}-<view>.png
   before the next view starts (the back view uses the selected side view as image 3).
5. If the generations of the view in this run are used up and a CHECKLIST item still fails, keep the best candidate,
   record the view and the failed items in verification.json limit_reached and in README.md, and go on: the acceptor
   decides. This is not a blocker.
After all views, one final run WITHOUT --out on the selected files (it writes art/imagegen/concept-{{CONTENT_KEY}}-codex/checks-report.json and the sheet):
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-{{CONTENT_KEY}}-codex --key {{CONTENT_KEY}} --views {{VIEWS}} --role {{ROLE_ARG}} --palette art/imagegen/concept-{{CONTENT_KEY}}-codex/palette.json --sheet
   Exit 1 here (a set check such as set.height or set.base_center) with generations left: regenerate the view the
   failed check points to, as in step 3, then repeat this final run. Exit 2: as in step 2.
Then write prompts.md, prompts/concept-prompts.json, README.md, verification.json, manifest-sha256.json last.
CHECKLIST (per view, passed/failed with a note in verification.json):
- the view is exactly the one asked for: front, a strict profile of the {{SIDE_VIEW}} side, or a strict back view;
  camera exactly level; no three-quarter, no perspective, no collage, no text or watermark;
- silhouette, pose, arm and weapon positions follow image 1 (the draft render); no added anatomy, no new weapon;
- identity, costume, colours and materials follow the approved design; every anchor visible from this side is there;
- weapon side: front and side - {{WEAPON_SIDE_EN}}; back - {{BACK_WEAPON_EN}};
- framing as in image 1: {{FRAME_CHECK_EN}}; the same highest point; the whole subject visible;
- the same plain flat dark gray background in every view.
CORE-FRONT:
{{CORE_1C_FRONT}}
CORE-SIDE:
{{CORE_1C_SIDE}}
CORE-BACK:
{{CORE_1C_BACK}}
Return: at most 10 lines: selected generation per view, generations used per view, the final script exit code, what
failed.
```

Строки CORE-SIDE (и у пропа без вида side — строки `side` в шаге 1) удаляются, если вида нет в `{{VIEWS}}`.
`{{FRAME_CHECK_EN}}`: фигура — `the same pedestal position and size`; проп — `the same bottom position, no pedestal
added`.

### 8.2 Ядро CORE-1C (одно для трёх видов; менять только плейсхолдеры)

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, {{VIEW_NAME_EN}}
orthographic render. Paint directly over it. Keep exactly its {{KEEP_EN}}.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
{{IMAGE3_EN}}
SUBJECT: {{DESCRIPTION_EN}}
IDENTITY ANCHORS, where visible from this side: {{ANCHORS_EN}}.
PALETTE: {{PALETTE_EN}}. {{WEAPON_SIDE_EN}}
VIEW: {{VIEW_BLOCK_EN}}
FRAMING: the same {{ASPECT_EN}} and the same framing as image 1, uniform scale only: {{FRAMING_BASE_EN}}, highest point
y{{TOP_Y}}%. {{WHOLE_EN}}
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

| Вид | `{{VIEW_NAME_EN}}` | `{{VIEW_BLOCK_EN}}` (фигура) | `{{IMAGE3_EN}}` |
|---|---|---|---|
| front | `FRONT` | `FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.` | пусто (строка удаляется) |
| side, `SIDE_VIEW` = left | `LEFT SIDE` | `LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.` | пусто |
| side, `SIDE_VIEW` = right | `RIGHT SIDE` | `RIGHT SIDE: strict profile, the figure's OWN right side faces the camera, its face toward the right edge of the image, no three-quarter view.` | пусто |
| back | `BACK` | `BACK: camera directly behind, no face visible, no three-quarter view. {{BACK_WEAPON_EN}}` | `Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.` |

Блоки видов пропа (асимметричный проп, через 1b): front — `FRONT: strict front orthographic view of the object's front
side with all its hardware.`; back — `BACK: camera directly behind the object, strict orthographic view.`

Блоки, которые зависят от `ROLE` (у пропа подставки нет: слово «pedestal» в его промпте заставляет генератор
дорисовать подставку):

| Плейсхолдер | фигура (`hero`, `creature`) | `prop` |
|---|---|---|
| `{{KEEP_EN}}` | `silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing` | `silhouette, proportions, positions of handles and hardware, scale and framing` |
| `{{FRAMING_BASE_EN}}` | `pedestal x{{BASE_X0}}%-{{BASE_X1}}%, pedestal top y{{BASE_TOP_Y}}%, pedestal bottom y{{BASE_BOTTOM_Y}}%` | `the bottom of the object x{{BASE_X0}}%-{{BASE_X1}}% at y{{BASE_BOTTOM_Y}}%, no pedestal` |
| `{{WHOLE_EN}}` | `The whole subject and the whole pedestal visible.` | `The whole object visible.` |

У пропа `{{BASE_TOP_Y}}` не используется: `base_top_y_est` — верх широкого нижнего слоя, у пропа это не подставка.

### 8.3 Ядро PROP-ROTATE (осесимметричный проп без 1b, только вид side)

Ссылки: `[<key>-front.png]` (копия принятого дизайна). Задание — тот же файл `<ASSET_ID>-concept-views.codex.md`:
шаг 0 — Codex копирует `design/<key>-front.png` побайтно в `<key>-front.png`, затем один вид `side` с этим ядром
(`{{IMAGE3_EN}}` и числа рамки не нужны), проверка `--views front,side --role prop`.

```text
Use case: edit. Image 1 is the APPROVED FRONT of this object. Draw the SAME rigid object rotated 90 degrees around its
vertical axis: LEFT SIDE: the side that is on the viewer's RIGHT in image 1 now faces the camera, strict orthographic
view, no three-quarter view. Do not redesign or mirror it. Keep exact proportions, height, width, colours, materials
and painted detail level.
SUBJECT: {{DESCRIPTION_EN}}
IDENTITY ANCHORS, where visible from this side: {{ANCHORS_EN}}.
PALETTE: {{PALETTE_EN}}.
FRAMING: the same {{ASPECT_EN}}, scale and position as image 1: centred, the bottom of the object at the same height,
the same overall height. The whole object visible.
BACKGROUND AND LIGHT: the same plain flat neutral dark charcoal gray background and soft even studio lighting as image
1, no cast shadow on the background.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## 9. Плейсхолдеры и их источники

**Два вида переменных.**
- `{{NAME}}` — подставляет Claude (запускающий агент), когда пишет файл задания или ядро. В готовом файле задания
  не остаётся ни одного `{{`: проверка `grep -n '{{' <файл задания>` → пусто. Незаполненное значение — возврат на этап 0.
- `<name>` — переменная рантайма: её значение выбирает Codex во время запуска (`<N>` — номер генерации по
  `generation-records.json`, `<view>` — текущий вид, `<stage>` — 1a или 1c) или запускающий агент в своих командах
  этого справочника (`<ASSET_ID>`, `<key>`, `<VISUAL_CARD_ID>` в командах 5.2, 5.5, 7 — его собственные шаги, не
  текст для Codex). В тексте задания для Codex `<…>` бывают только рантаймовые: `<N>`, `<view>`, `<stage>` и форма
  строки CORRECTION (`<failed check id or CHECKLIST item>`, `<what is wrong>`, `<how it must be>`).

Каждый `{{…}}` берётся из поля карточки `<ASSET_DIR>/asset-card.yaml` (поля этапа 0), из выхода шага 1b или из
этого справочника.

| Плейсхолдер | Источник | Правило |
|---|---|---|
| `{{ASSET_ID}}`, `{{CONTENT_KEY}}`, `{{ASSET_DIR}}` | `ASSET_ID`, `CONTENT_KEY`, `ASSET_DIR` | как есть; `{{CONTENT_KEY}}` — это и `<key>` в именах файлов |
| `{{DATE}}` | дата записи задания | `YYYY-MM-DD` |
| `{{ASSET_CARD_SHA256}}`, `{{QUALITY_REFERENCE_SHA256}}`, `{{PALETTE_SHA256}}` и sha256 входов 1c | файлы входов | sha256 на момент записи задания |
| `{{GENERATIONS_ALLOWED}}` | `generation-records.json` | 1a: `min(2, 4 − генераций design-front)`; 1c: по каждому виду, раздел 8.1 |
| `{{B_CONCEPT_PACKAGE}}` | раздел 5.4 | блок целиком, `{{ASSET_ID}}` и `{{CONTENT_KEY}}` в нём подставлены |
| `{{CORE_1A}}` | раздел 6.2 | ядро с подставленными плейсхолдерами |
| `{{CORE_1C_FRONT}}`, `{{CORE_1C_SIDE}}`, `{{CORE_1C_BACK}}` | раздел 8.2 (проп без 1b — 8.3) | ядро каждого вида с подставленными плейсхолдерами |
| `{{DESCRIPTION_EN}}` | `DESCRIPTION_EN` | 1–3 предложения по-английски: кто, возраст и сложение, костюм, материалы, оружие и рука, сторона колчана или ножен; запреты раздела 4.5 |
| `{{ANCHORS_EN}}` | `ANCHORS_EN` | 3–6 видимых признаков через `; `, со стороной и числом: `longbow in the figure's own LEFT hand; quiver over the RIGHT shoulder; exactly three feathers on the hood`. **Сторона колчана и ножен** (решение оркестратора 2026-10-09): не задана заявкой — на стороне натягивающей или свободной руки, то есть противоположной `WEAPON_HAND`: лук в левой → колчан за ПРАВЫМ плечом или на правом бедре; меч в правой → ножны на ЛЕВОМ бедре. `WEAPON_HAND: none` — сторона из заявки, иначе не упоминается. Сторона пишется в `DESCRIPTION_EN` и в якорь |
| `{{PALETTE_EN}}` | `PALETTE` | `<name> #RRGGBB` через `, `, акцент последним с префиксом `accent `: `midnight blue #1F2A5A, antique gold #B08A3E, accent sapphire blue #2F5FD0`; имена — `PALETTE.main[].name`, `PALETTE.accent.name` |
| `{{POSE_EN}}` | `ANATOMY` | таблица раздела 4.4 |
| `{{WEAPON_SIDE_EN}}`, `{{BACK_WEAPON_EN}}` | `WEAPON_HAND` | таблица раздела 4.4 |
| `{{POSE_CHECK_EN}}` | `ANATOMY` | humanoid — `(both arms clearly apart from the torso, not a T-pose, not an A-pose)`; winged-biped — `(exactly two wings, clearly apart from the body, no separate human arms)`; prop — `(upright, in its natural resting orientation)` |
| `{{ASPECT_EN}}`; `--aspect` | `ANATOMY` | `portrait aspect ratio 3:4`; winged-biped — `landscape aspect ratio 4:3` |
| `{{PEDESTAL_EN}}` | `ROLE` | фигура: `PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not visible, its front edge is a straight horizontal line.` (Ø 0,30 м при росте 0,55 м — HANDBOOK §2.10; точный масштаб задаёт этап 3); prop: `PEDESTAL: none; the object stands on its own flat bottom, seen exactly edge-on.` |
| `{{ONE_BASE_EN}}`, `{{AND_PEDESTAL_EN}}`, `{{EDGE_ON_CHECK_EN}}` | `ROLE` | фигура: `one pedestal`, ` and pedestal`, `the pedestal is seen exactly edge-on, its top surface is not visible`; prop: `one object, no pedestal`, пусто, `the bottom of the object is seen exactly edge-on` |
| `{{QUALITY_REFERENCE}}` | `QUALITY_REFERENCE` | первый файл поля, путь от корня репо; дефолт ВР-08 — `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`. Единственное изображение-вход 1a |
| `{{ROLE_ARG}}` (`--role`) | `ANATOMY` | humanoid → `hero`, winged-biped → `creature`, prop → `prop` |
| `{{VIEWS}}` (`--views`) | `ROLE` + симметрия | раздел 4.1: `front,side,back`; проп осесимметричный — `front,side`; асимметричный — `front,back` |
| `{{SIDE_VIEW}}` | `SIDE_VIEW` | `left` (дефолт этапа 0) или `right` по правилу раздела 4.1 |
| `{{ORTHO_DIR}}` | шаг 1b | `art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/orthos`, путь от корня репо |
| `{{VIEW_NAME_EN}}`, `{{VIEW_BLOCK_EN}}`, `{{IMAGE3_EN}}` | вид + `SIDE_VIEW` | таблица раздела 8.2 |
| `{{KEEP_EN}}`, `{{FRAMING_BASE_EN}}`, `{{WHOLE_EN}}`, `{{FRAME_CHECK_EN}}` | `ROLE` | таблица ролей раздела 8.2 и строка под шаблоном 8.1 (у пропа без слова «pedestal») |
| `{{BASE_X0}}`, `{{BASE_X1}}`, `{{BASE_TOP_Y}}`, `{{BASE_BOTTOM_Y}}`, `{{TOP_Y}}` | `ortho-framing.json` шага 1b | маппинг полей — раздел 7, п. 5; в % кадра, одна цифра после запятой |

Не плейсхолдеры задания, а значения команд запускающего агента: `<VISUAL_CARD_ID>` — id строки `06-tasks/anim.csv`
(`AN-<NN>`), `--task` журнала трат (раздел 5.5); `<role>`, `<views>` в его командах 5.5 — те же значения, что
`{{ROLE_ARG}}`, `{{VIEWS}}`.

Эталон подставки (`art/imagegen/mvp-v1/markers/ref-base-{hero,sidekick}-p1.png`) с 2026-10-09 во входы 1a не идёт
(раздел 6.1): подставку задаёт `{{PEDESTAL_EN}}`. Плейсхолдеров `<BASE_REFERENCE>` и `{{PEDESTAL_REF_EN}}` больше нет.

`FIGURE_HEIGHT_M`, `POLY_BUDGET`, `UE_NAMES` на этапе 1 не используются: концепт держит пропорции, абсолютный
масштаб задаёт этап 3 (`scale.figure_top_m`, HANDBOOK §4.2).

## 10. Ретраи, CORRECTION, циклы

- **Генерации:** на вид не больше 4 за весь этап 1 (дизайн-front 1a — отдельный вид), счёт — по
  `generation-records.json`; в одном запуске Codex — не больше 2 на вид (решение скилла: оставить генерации на
  исправления после приёмки). Возврат к 1a или 1b счётчики не обнуляет.
- **CORRECTION** — единственный канал исправления, для любого вида, включая front и дизайн 1a. Дописывается после
  ядра, ядро не меняется:

```text
CORRECTION (fix only this; everything above still applies):
- <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
- <…>
- <…>
```

  Этот блок дословно стоит в шагах шаблонов 1a и 1c (6.1 п.3, 8.1 п.3) и в каждом `…fix<N>.codex.md`; первая строка
  `CORRECTION (fix only this; everything above still applies):` не меняется. Не больше 3 строк, по-английски.
  Источники строк — только эти три:
  1. FAIL-проверка `checks-report.json` (по `id`, раздел 4.3). WARN — не источник: его оценивает приёмщик;
  2. проваленный пункт CHECKLIST задания Codex (запись `checklist` с `passed: false` в `verification.json`) — это
     осмотр самого Codex внутри запуска, до приёмки;
  3. пункт `rework_fix_list` карточки приёмки (после приёмки).

  Строка называет вид, что не так и как должно быть (`The bow must be in the figure's own LEFT hand, on the viewer's
  RIGHT.`). Новые детали дизайна и противоречие ядру запрещены.
- **Цикл** = одна приёмка: 1a и 1c считаются раздельно (каталоги `…-front-r<N>` и `…-sheet-r<N>`), у каждого r1–r4
  (схема карточки `kind: concept` допускает `cycle` r1–r4). После первой приёмки — не больше 3 циклов. Корректирующий
  запуск — отдельный файл задания `…fix<N>.codex.md` (образец `docs/game-design/visual/06-tasks/prompts/AN-22.fix1.codex.md`):
  ссылается на базовое задание, перечисляет только перегенерируемые виды и их CORRECTION.
- **Что перегенерировать** (по полю «инструмент» пунктов `rework_fix_list`):

| Причина | Куда | Что переделывается |
|---|---|---|
| деталь, цвет, ракурс или рамка одного вида | 1c | только этот вид; после нового side приёмщик заново оценивает согласованность back |
| силуэт, поза или части из черновика (ошибка орто) | 1b | новый черновик → новые орто → все три вида 1c |
| личность, палитра или дизайн ошибочны уже в дизайн-front | 1a | дизайн → 1b → 1c |

- Противоречие видов не доказано (неясно, какой вид дефектный) — сначала определить дефектный вид, вслепую не
  перегенерировать (прецедент Harpy: `CONSISTENCY-REVIEW.md:115,121`).
- **Генерации запуска исчерпаны, пункт CHECKLIST провален** (лимит 2 на вид в запуске; `verification.json#limit_reached`)
  — не стоп и не повод для ещё одной генерации в обход лимита: при 0 FAIL автопроверок лист идёт к приёмке с пометкой,
  решает приёмщик; при FAIL — корректирующий запуск без приёмки (раздел 5.5, п.5).
- Исчерпаны все 4 генерации вида, а нужна ещё одна (FAIL автопроверки или пункт `rework_fix_list`), или после 4-й
  приёмки нет pass → вердикт `escalate_user`, стоп: пользователю лист, все карточки, числа автопроверок по циклам и
  что решать.

## 11. Приёмка: гейты, рубрика, вердикт, карточка

Механика и вызов приёмщика — общие с этапом 4 (`acceptance-and-blender.md`: профили «Opus xhigh» / «Sol 6.1 xhigh»,
сессия приёмщика ≠ сессии исполнителя, приёмщик не правит). Здесь — то, что относится к концепту.

**Гейт (PASS/FAIL из отчёта, не балл) — один:** `G-CHECKS` — `check_concept_views.py` с кодом 0 (`source` — путь
`checks-report.json` от корня репо). Схема `tools/art/acceptance/asset-acceptance-2.schema.json` для `kind: concept`
разрешает только его (`gates.propertyNames: ["G-CHECKS"]`; `validate_card.py` `GATES["concept"]`), статус `n/a` для
него запрещён. Сверка записей генераций — не гейт карточки, а предусловие вызова приёмщика (раздел 5.5, п. 3).

**Измерения** (0–2, шаг 0,5):

| Балл | S — силуэт и читаемость | C — согласованность видов (1c) | Q — детализация против QUALITY_REFERENCE | P — палитра и якоря |
|---|---|---|---|---|
| 0 | не тот персонаж; лишние или недостающие части (вторая голова, вторая рука с оружием); T- или A-поза (раздел 4.4) | разные персонажи или позы; оружие зеркально | плоско, мультяшно или фото; не миниатюра | палитра чужая; якорей нет |
| 0,5 | главные признаки (оружие, головной убор) теряются в силуэте | поза или костюм заметно расходятся на одном виде | грубые детали, материалы не различимы | часть основных цветов не та |
| 1 | читается, но один главный признак слит с корпусом | якоря совпадают, форма плаща, головного убора или масштаб заметно расходятся | материалы различимы, детализация явно ниже эталона | основные цвета верны, акцент или один якорь потерян |
| 1,5 | читается на всех видах, мелкие слияния (кисть с оружием), руки близко к корпусу | мелкие расхождения орнамента и складок (уровень принятых наборов hero-quality-v1, их «Проверка и ограничения») | близко к эталону, отдельные зоны беднее | все цвета и якоря есть, отклонение тона |
| 2 | ясный силуэт на каждом виде, руки отделены, поза по разделу 4.4, тонкие части читаются или помечены в обосновании для этапов 3–4 | поза, пропорции, якоря и сторона оружия совпадают; профиль и вид сзади строгие | уровень эталона: расписанная коллекционная миниатюра, детали внутри силуэта | палитра = `PALETTE` (свотчи листа совпадают с фигурой), все якоря на месте там, где видимы |

`score = round(sum / (2 × n_applicable) × 10, 1)`, n = 4 всегда (схема требует числовые S, C, Q, P; null у
концепта не допускается). Сравнение `score >= 8.0`.

**C на 1a — фиксированное правило (решение скилла).** На 1a один вид, согласованность видов не оценивается, но схема
требует число. Приёмщик ставит `C = 1,5` с обоснованием «1a: один вид, C не оценивается; фиксированное значение
concept-sheet.md §11» и `frames: ["<key>-front.png"]`; в `rework_fix_list` C на 1a не попадает. Почему 1,5: при шаге
0,5 условие pass `(S + Q + P + 1,5) / 8 × 10 ≥ 8,0` равносильно `S + Q + P ≥ 5,0`, то есть ровно порогу 8,0 по трём
оцениваемым измерениям (`5,0 / 6 × 10 = 8,3`, `4,5 / 6 × 10 = 7,5`); 1,5 не срабатывает как вето (< 1,0). Проверено
`validate_card.py` на пробных карточках 1a: S 1,5 + C 1,5 + Q 1,5 + P 2 → 8,1 `pass` (код 3: второй приёмщик, «Устойчивый pass листа» ниже); S 1 + C 1,5 + Q 1,5 + P 2 → 7,5
`return_to_stage_1`.

**Вердикт** (детерминированно, проверяет `validate_card.py`): гейт `G-CHECKS` FAIL → `return_to_stage_1`; любое
измерение < 1,0 → `return_to_stage_1` при любой сумме; `score < 8.0` → `return_to_stage_1`; иначе `pass`. Цикл `r4`
без pass → `escalate_user` (`validate_card.py` `LAST_CYCLE["concept"] = 4`). Запрещённая поза (T или A) — S = 0, то
есть вето: лист не проходит при любой сумме.

**Устойчивый pass листа** (решение оркестратора по калибровке 2026-10-09, раунд 3; то же правило, что у модели,
`references/acceptance-and-blender.md` §6, §8.5, §13). `pass` со `score` 8,0–8,4 одной карточкой не окончателен:
`validate_card.py` даёт код **3** и печатает `needs_second_acceptor`. На 1a это любой pass с `S + Q + P` = 5,0 (C = 1,5
фиксировано), то есть 8,1. Порядок:

1. Второй приёмщик — **другой профиль** («Sol 6.1 xhigh» при первом «Opus xhigh» и наоборот), тот же промпт ниже, те
   же файлы, новый контекст; первую карточку он не видит. Ответ — `card-2.json` рядом с `card.json` (для Sol —
   `--output-schema tools/art/acceptance/asset-acceptance-2.output-concept.schema.json -o <каталог>/card-2.json`;
   остальное — команда `references/acceptance-and-blender.md` §8.4, с `windows.sandbox="unelevated"`). Opus — сохранённый
   workflow `second-acceptor` (там же §8.3) со схемой `…output-concept…`; его ответ (страховка от строк `"null"`, F6/F102) — через
   `python tools/art/pipeline_batch/finish_second.py <workflow-output.json>`: он чистит карточку, пишет `card-2.json` и
   сразу считает пару (п.2).
2. Итог пары:
   ```bash
   python tools/art/acceptance/validate_card.py <каталог>/card.json --second <каталог>/card-2.json \
       --final-json <каталог>/final.json --print-verdict --check-files
   ```
   `score` — минимум двух; вердикт — карточки с меньшим `score` (при равенстве — более строгий), но строгий маршрут
   другой карточки (`return_to_stage_1`, FAIL `G-CHECKS`, вето) побеждает. Маршрут и `rework_fix_list` (пункты
   CORRECTION) — из карточки `final.json#source_card`.
3. Второй `pass` в той же полосе — итог `pass`; третий приёмщик не нужен. Другой профиль не запускается после пробы
   (§5.2) — второй приёмщик того же профиля в новом контексте и `--same-profile-ok`.

**Карточка** (форма — схема `tools/art/acceptance/asset-acceptance-2.schema.json`, ветка `kind: concept`; поля:)

| Поле | Значение на этапе 1 |
|---|---|
| `schema`, `kind` | `"unmatched.concept-acceptance/1"`, `"concept"` |
| `asset_id` | `ASSET_ID` |
| `cycle` | `r1`–`r4` (1a и 1c считаются раздельно, раздел 10) |
| `date` | дата приёмки `YYYY-MM-DD` (обязательно) |
| `previous_card` | `null` у r1; у r2+ — путь от корня репо к `card.json` предыдущего цикла того же шага (обязательно, `validate_card.py:308-311`) |
| `accepted_object` | `[{path, sha256}]`, пути от корня репо: 1a — `art/imagegen/concept-<key>-codex/design/<key>-front.png`; 1c — `<key>-front.png`, `<key>-side.png`, `<key>-back.png` пакета |
| `frames` | объект `{dir, files}`: `dir` — каталог от корня репо, `files` — только имена без `/` (шаблон `^[A-Za-z0-9._-]+\.(jpg\|png\|json)$`). 1a: `dir` = `art/imagegen/concept-<key>-codex/design`, `files` = [`<key>-front.png`, `checks-report.json`]. 1c: `dir` = `art/imagegen/concept-<key>-codex`, `files` = [`sheet-<key>.png`, `<key>-front.png`, `<key>-side.png`, `<key>-back.png`, `checks-report.json`] |
| `reports` | пути от корня репо: `checks-report.json` этого шага, `generation-records.json`, `verification.json` |
| `gates` | `{"G-CHECKS": {"status": "PASS"\|"FAIL", "source": "<путь checks-report.json>", "note": "…"}}` — и больше ничего |
| `scores` | `S`, `C`, `Q`, `P`: `{value: 0–2 шаг 0,5, rationale, frames}`; `frames` — имена из `frames.files` |
| `score`, `verdict` | по формуле и правилам выше |
| `verdict_reason` | обязательно при `verdict` ≠ `pass` (≥ 10 символов): какое правило сработало |
| `rework_fix_list` | `[{item, frame, fix, tool}]`: `item` — измерение < 2 или `G-CHECKS` при FAIL; `frame` — вид/файл; `fix` — одна английская строка, пригодная для CORRECTION; `tool` — `Codex 1c CORRECTION` \| `Tripo 1b черновик` \| `Codex 1a` |
| `acceptor` | `{profile: "Opus xhigh"\|"Sol 6.1 xhigh", session_id}` — профиль фактического запуска: явный выбор запускающего важнее `ACCEPTOR_PROFILE` заявки, в карточку пишется то, что запущено (F76, F119) |
| `executor_session_id` | сессия запускающего агента (≠ `acceptor.session_id`); исполнитель-субагент — `claude-code:<uuid>/agent:<name>` (F40) |
| `decided_by` | `"delegated (ВР-реестр 2026-10-06)"` или `"user"` |
| `status_note` | при pass по делегированию — содержит «по делегированию» (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`) |

Путь: `art/pipeline-candidates/<ASSET_ID>/evidence/acceptance-concept/<YYYYMMDD>-front-r<N>/card.json` (1a) и
`…/<YYYYMMDD>-sheet-r<N>/card.json` (1c). Пустой каталог `frames/` не нужен: кадры — файлы пакета.

```bash
python tools/art/acceptance/validate_card.py \
    art/pipeline-candidates/<ASSET_ID>/evidence/acceptance-concept/<YYYYMMDD>-<front|sheet>-r<N>/card.json \
    --print-verdict --check-files
# код 0 = схема валидна и вердикт согласован с правилами; 1 = нет. --check-files сверяет sha256 accepted_object
# и наличие frames/reports/previous_card; запуск из корня репо
```

**Промпт приёмщика** (на вход только файлы, отчёты, выдержка карточки и рубрика; ответ — JSON карточки по схеме):

```text
Ты — приёмщик этапа 1 скилла 3d-model-pipeline (концепт-лист). Файлы не правишь, ничего не генерируешь.
Текстовые файлы читай так, чтобы кириллица дошла целой. В песочнице codex PowerShell работает в Constrained
Language Mode и пишет вывод в OEM-кодировке: `Get-Content -Encoding UTF8` даёт кракозябры, смена
`[Console]::OutputEncoding` запрещена, `rg` нет. Рабочие способы (проверено пробой 2026-10-13): читай КАЖДЫЙ
текстовый файл (рубрику, checks-report.json, generation-records.json, verification.json, предыдущую карточку)
командой `Get-Content <файл> -Raw -Encoding OEM` (байты UTF-8 проходят без перекодировки и читаются верно) или
`cmd /c type <файл>`. Кодовые точки (`[int[]][char[]]`) не нужны. Если кириллица рубрики всё равно пришла
кракозябрами — это сбой окружения: не оценивай по догадкам, верни карточку, где verdict_reason начинается со слов
«СБОЙ ОКРУЖЕНИЯ: кириллица не читается».
Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/concept-sheet.md, раздел 11
(таблица S, C, Q, P). Рубрика — ТОЛЬКО этот файл: SKILL.md и другие файлы скилла (.agents/skills/**, кроме
concept-sheet.md) не открывай и не учитывай.
Объект: <1a: дизайн-front design/<key>-front.png | 1c: виды <key>-front/side/back.png и лист sheet-<key>.png>.
Открой каждый файл как картинку. Прочитай checks-report.json и generation-records.json.
Выдержка карточки ассета: DESCRIPTION, ANCHORS, PALETTE, ANATOMY, WEAPON_HAND, SIDE_VIEW (<значения>).
Эталон качества: <QUALITY_REFERENCE> (открой). Для 1c — ещё дизайн design/<key>-front.png и ортопроекции 1b.
На 1a C = 1,5 по фиксированному правилу раздела 11, в rework_fix_list C на 1a не включай. T- или A-поза = S 0.
Балл — по якорям, шаг 0,5; обоснование с
именами файлов из frames.files. Гейт один — G-CHECKS по checks-report.json (код 0 → PASS); WARN не гейт, учитывай их
в C. rework_fix_list — только измерения < 2 и G-CHECKS при FAIL; у пункта: item, frame (вид), fix (одна английская
строка для CORRECTION), tool (Codex 1c CORRECTION | Tripo 1b черновик | Codex 1a). Вердикт посчитай по правилам
раздела 11; при не-pass заполни verdict_reason. Заполни все поля таблицы «Карточка» раздела 11 (date, previous_card,
frames как {dir, files} с именами без пути). Верни только JSON карточки.
```

Блок чтения кириллицы и строка «рубрика — только этот файл» обязательны в каждом промпте приёмщика Sol (RA-03). Без
них Sol читал рубрику кракозябрами при коде 0 (F36, приёмка модели Angel r1) и открывал SKILL.md вне входов (F75); образец —
`art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/acceptor-prompt.md:9-20`. Карточка, где
`verdict_reason` начинается со «СБОЙ ОКРУЖЕНИЯ», — сбой окружения, а не приёмка: цикл (раздел 10) не тратится, балл не
пишется; разбор оркестратором (ДС-2), затем тот же вызов заново (`acceptance-and-blender.md` §8.4).

## 12. Выход этапа 1 → этап 2

- Карточка 1c с `pass`, `validate_card.py` код 0, `checks-report.json` 0 FAIL, лист осмотрен глазами.
- Входы этапа 2 (multi-view H2, `tripo3d-stages.md`): `art/imagegen/concept-<key>-codex/<key>-front.png`,
  `<key>-side.png` → слот `<SIDE_VIEW>`, `<key>-back.png` (проп — раздел 4.1). Те же файлы — эталон всех сравнений
  «концепт | модель» на этапах 3–4 (HANDBOOK §3.1) и `preview.concepts` профиля H2-bake (HANDBOOK §4.2).
- Коммит пакета, заданий, орто, карточек — запускающим агентом после приёмки (`git commit --no-verify`, AGENTS.md).
  GLB черновика в git не идёт.
- **Ждёт решения пользователя (RC-16):** пакет 1a (выбранный фронт, `generation-records.json`, проверки,
  `verification.json`) коммитится вместе с записью реестра ещё до 1b, а не после 1c. Причина: волны 2026-10-13 оставили
  96 из 100 пакетов (756 МБ) вне git — worktree их не видит, потеря = повтор 1a за квоту Codex. Правило упирается в
  вес репозитория (SUMMARY исследования, «Решения пользователя» п.4–5); до ответа действует строка выше.

## 13. Снятые неоднозначности прогона 2026-10-09

Прогон старого пакета в Codex (`C:/tmp/skill-review-codex/robin-hood/AMBIGUITIES.md`, 15 пунктов) → где снято:

| № | Неоднозначность | Решение в этом файле |
|---|---|---|
| 1 | первому front нечего «перерисовывать» | отдельное ядро CORE-1A text→image (6.2); перерисовка — только на 1c поверх орто |
| 2 | описанию и позе нет места в ядре | блоки SUBJECT, IDENTITY ANCHORS, PALETTE, POSE в обоих ядрах (6.2, 8.2) |
| 3 | чек-лист не вложен в пакет | CHECKLIST внутри текста задания (6.1, 8.1) |
| 4 | нормализатор привязан к чужим героям | нормализации нет: выход не правится, рамка задаётся промптом и орто (4.2) |
| 5 | реестра сета нет | `generation-records.json` пакета по 07 §1.1, поля в B-CONCEPT-PACKAGE (5.4) |
| 6 | метаданных этапа 0 нет | все плейсхолдеры с источником в карточке (9); пустое поле → возврат на этап 0 |
| 7 | размер 1024 невыполним | размер не задаётся и не проверяется числом; только аспект и единый размер набора (4.2) |
| 8 | «не править пиксели» против нормализации | только побайтные копии; правок нет совсем (4.2, 5.3) |
| 9 | поле 10 % против 2 %/9,5 % | поля не нормируются; допуски `check_concept_views.py` (4.3) |
| 10 | нет проверочного скрипта | `tools/art/concept/check_concept_views.py` (4.3); межвидовые проверки — на полном наборе |
| 11 | что сдавать при остановке | лист рисует инструмент по имеющимся видам; статус — в README и карточке `escalate_user` (10) |
| 12 | как править на ретрае | блок CORRECTION ≤ 3 строк для любого вида (10) |
| 13 | y=920 против 917 | абсолютных пиксельных линий нет; места в % кадра из ядра 1a и `ortho-framing.json` (4.2) |
| 14 | рост «без оружия» неизмерим при луке над головой | рост по всей маске, только разброс между видами: > 3 % WARN, > 5 % FAIL (4.2, 4.3) |
| 15 | image_gen сохраняет файл вне пакета | сразу побайтная копия в `concepts/`, оригинал на месте, оба пути в записи (5.4) |

### 13.1 Живой тест этапов 0 + 1a (Robin Hood, 2026-10-09)

Прогон `C:/tmp/skill-live-test/robin-hood/`: 2 из 2 генераций, `check_concept_views.py` 0 FAIL; замечания → где снято
(п. 1–3 — флаг песочницы, проба с командой, «код 0 ≠ успех» — сняты раундом 3 в 5.2):

| № | Замечание | Решение |
|---|---|---|
| 4 | перепроверка в 5.5 перезаписывала `checks-report.json` → манифест не совпадал | перепроверка с `--out` вне пакета, сравнение без `generated_at` (5.5 п.2) |
| 5 | в шаблонах нет точного блока CORRECTION | блок дословно в 6.1 п.3, 8.1 п.3 (раздел 10) |
| 6 | `design/checks-report.json` перезаписывался каждым кандидатом | `checks/<view>-g<N>/` в раскладке (3), `--out` в шагах 6.1, 8.1 |
| 7 | кириллица `verification.json` стала «????» | UTF-8 из Python в B-CONCEPT-PACKAGE (5.4), «Кодировка» (3), проверка 5.5 п.2 |
| 8 | какие пути в `references` | от корня репо, кроме `original_path` (5.4) |
| 9 | «y4% or lower» двусмысленно, рамку 1a никто не проверял (вышло 3,3 %) | «no higher than y4% (y >= 4%)» в CORE-1A; WARN `view.frame_top` (`--min-top-pct 4`, 4.3) |
| 10 | генерации исчерпаны при проваленном чек-листе; эталон подставки тянул камеру вверх | к приёмке с `limit_reached` (5.5 п.5, 10); подставка словами, «seen exactly edge-on», без image 2 (6.1, 9) |
| 13 | сторона колчана | против `WEAPON_HAND` (натягивающая/свободная рука), раздел 9 `{{ANCHORS_EN}}` |
| 15 | `--model` и «запасной» путь | основной — exec (5.1); `--model` по пути запуска (5.5 п.4) |
| 17 | нет пробы приёмщика и Claude in Chrome | SKILL.md §6, этап 0 п.4 (команды и критерии) |
| 19 | подставляемые и рантаймовые переменные смешаны | `{{…}}` — подставляет Claude, `<…>` — рантайм (9, «Два вида переменных») |

Пункты 11, 12, 14, 16, 18 — в SKILL.md (этап 0, §7.2) и `new-character-registration.md` §1.

### 13.2 Ростер из БД и пилот (2026-10-13)

Волны 1a по таблице `Hero` (84 фигуры) и пилот 1c → этап 2 (Achilles, Angel, Ancient Leshen). Полный список
находок — `docs/art-pipeline/evidence/skill-pilot-2026-10-13/NOTES.md`. Скрипты волн перенесены из
`C:/tmp/concept-wave/` в `tools/art/pipeline_batch/` с тестами (ee301065): скрипты из `C:/tmp` больше не запускать.

| № | Замечание | Решение |
|---|---|---|
| 20 | Лицензионные персонажи (Marvel, The Witcher): Codex image_gen, SYNTX (Seedream, Nano Banana) и Gemini на 1a отказывают (`moderation_blocked`); обходные формулировки промпта — не путь | 1a — сервис по подписке пользователя, который такие фигуры рисует (unstability.ai, Recraft v4, промпт из карточки: `DESCRIPTION_EN`, `ANCHORS_EN`, палитра), фон приводится к ровному тёмно-серому (`python tools/art/pipeline_batch/rebg.py <in.png> <out.png> [tone] [grad]`, сырой кадр — `design/<key>-front-raw.png`), `verification.json` с `design_source`. Recraft не берёт эталон качества картинкой → Q/P ниже 8,0 → `escalate_user` (§10); решение пользователя — `evidence/acceptance-concept/<run>/user-decision.json` и запись в `docs/game-design/decisions/` (прецедент `2026-10-13-licensed-concepts-user-accepted.md`). Фигуру, которую не рисует ни один сервис (Alice), — фронт от пользователя |
| 21 | 1c для лицензионного персонажа: Codex рисует виды поверх орто черновика, хотя отдельные вызовы дают `moderation_blocked` (Ancient Leshen: лист 8,1/8,1, пара pass) | 1c сначала обычным заданием Codex; unstability — только если Codex отказал во всём виде после ретраев |
| 22 | Зеркальный side (лицом не в ту сторону) автопроверки не ловили | `check_concept_views.py --side-ortho <orthos>/ortho_<SIDE_VIEW>.png` (ee301065): FAIL `view.facing`, когда IoU силуэта side с зеркалом орто больше прямого на 0,05 (пилот 2026-10-14: прямо 0,96–0,97, зеркало 0,56–0,67); прогон запускающего до приёмки — 5.5 п.2; приёмщик всё равно сверяет side с `ortho_<SIDE_VIEW>` глазами (8.1, 11). FAIL — брак вида, на этап 2 не идёт (`tripo3d-stages.md` §5.5) |
| 23 | Пакетный запуск: несколько полос `codex exec` по одному файлу-очереди; без захвата задания две полосы берут одно | `tools/art/pipeline_batch/codex_lane.py --tasks --name --logs [--stop-file] [--grace]` (claim-файл `<logs>/<id>.claim`, остановка — файл STOP), задания — `make_tasks.py` (1a) и `make_1c.py` (1c), приёмка листов — `sheet_acceptance.py` (5.6) |

## 14. Источники

Репозиторий: HANDBOOK §1, §2.6, §2.9, §2.10, §3.1, §3.2, §4.2; `docs/game-design/visual/07-prompt-templates.md` §0.2,
§0.4, §1.1, §1.2, §3.1, §4; `art/imagegen/hero-quality-v1/{harpy,king-arthur,medusa,merlin}/prompts.md` (образец
формулировок style-transfer и записи `prompts.md`); `docs/art-pipeline/imagegen-inputs/CONSISTENCY-REVIEW.md`;
`docs/art-pipeline/rig/rig-contract.json`; source-specs H2/H3 героев (`art/pipeline-candidates/ASSET-*/source-specs/`,
поле `slot_note`); `tools/art/visual/ledger.py`; `docs/game-design/visual/06-tasks/prompts/AN-22.codex.md`,
`AN-22.fix1.codex.md`; `art/imagegen/mvp-v1/markers/ref-base-{hero,sidekick}-p1.png` (до 2026-10-09 — эталон
подставки 1a; снят, раздел 6.1).
Живые проверки 2026-10-09: `codex.exe exec` и `image_gen` (размер игнорируется, ~27 с на вызов); прогон старого пакета
`C:/tmp/skill-review-codex/robin-hood/` (`RUN-REPORT.md`, `AMBIGUITIES.md`).
Инструменты скилла (CLI и калибровка — `tools/art/concept/README.md`): `tools/art/concept/draft_orthos.py`,
`tools/art/concept/check_concept_views.py`, `tools/art/acceptance/validate_card.py`,
`tools/art/acceptance/asset-acceptance-2.schema.json`; пачка — `tools/art/pipeline_batch/` (5.6).
Решения по итогам пилота — `docs/game-design/decisions/2026-10-14-skill-refinement-delegated-decisions.md` (ДС-1…ДС-8).
