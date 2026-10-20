# Z-Code calibration C2 — приёмка 1c sheet ASSET-ANCIENT-LESHEN-001 (повтор принятого листа)

Калибровка побочной модели Z-Code для скилла 3d-model-pipeline проекта unmached. Это уже принятый лист; твоя карточка
сравнивается с карточкой другого приёмщика, которую ты не видишь.
Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
Задача пользователя (2026-10-20, дословно): «Заодно проверим работу с генерацией ассетов Gemini. И ревью ассетов с помощью Z-Code.»
Траты: нет. Ты — отдельный приёмщик «Z-Code GLM-5.3-Flash», не исполнитель. Файлы не правишь, ничего не генерируешь, не
запускаешь git, validate_card.py, Blender, Unreal, браузер или других агентов. Не открывай никакие файлы и папки, кроме
папки `docs/art-pipeline/evidence/skill-batch-2026-10-20/zcode-calibration/c2-leshen-sheet/in/` (и не читай карточки, NOTES и evidence других приёмок).
Объект: 1c виды ancient-leshen-front/side/back.png и лист sheet-ancient-leshen.png. Открой каждый файл как картинку
(они же приложены к сообщению). Файлы в `docs/art-pipeline/evidence/skill-batch-2026-10-20/zcode-calibration/c2-leshen-sheet/in/`:
- `ancient-leshen-front.png`, `ancient-leshen-side.png`, `ancient-leshen-back.png` — принимаемые виды 1c;
- `sheet-ancient-leshen.png` — лист приёмки (цвет, серое, силуэт на белом, свотчи);
- `design-ancient-leshen-front.png` — утверждённый дизайн-front 1a;
- `ortho_front.png`, `ortho_left.png`, `ortho_back.png` — ортопроекции черновой модели 1b (силуэт и поза неприкосновенны);
- `medusa-quality-reference.png` — эталон качества QUALITY_REFERENCE;
- `checks-report.json` — автопроверки (гейт G-CHECKS: summary.FAIL = 0 → PASS).

Выдержка карточки ассета (DESCRIPTION_EN, ANCHORS_EN, PALETTE, ANATOMY, WEAPON_HAND, SIDE_VIEW):
# asset-card.yaml — 3d-model-pipeline, этап 0 (поля этапа 1). Записан пакетно 2026-10-13.
# Реестр asset-registry.json, строка 06-tasks/anim.csv и пробы исполнителей этапов 2+ отложены
# (пользователь 2026-10-13: «Все остальные этапы нужно будет отложить»).
ASSET_ID: ASSET-ANCIENT-LESHEN-001
CONTENT_KEY: ancient-leshen
KEY: AncientLeshen
ROLE: hero
ANATOMY: humanoid
GAME_ROLE: hero
WEAPON_HAND: none
SIDE_VIEW: left
DESCRIPTION_EN: "The Ancient Leshen from The Witcher (Unmatched: Steel and Silver): tall gaunt forest spirit with a deer skull head and large antlers, body of twisted roots and branches, long clawed arms, crows perched on it."
ANCHORS_EN: "deer skull head with large antlers; body of twisted roots; long clawed arms; crows"
PALETTE:
  main:
    - {name: bark brown, hex: "#5A4030"}
    - {name: bone, hex: "#D9CFB8"}
    - {name: moss green, hex: "#4E5A36"}
  accent: {name: crow black, hex: "#141414"}
QUALITY_REFERENCE:
  - art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png
ASSET_DIR: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001
decided_by: delegated (ВР-реестр 2026-10-06)
NOTES: ростер после MVP вне объёма ВР-18 — запуск по запросу пользователя 2026-10-13 (волна 1a).
POLY_BUDGET: {figure_tris_max: 45000, base_tris_max: 2500}
CREDITS:
  ledger: "docs/game-design/visual/credits-ledger.json"
  tripo_limit: "нет лимита (решение пользователя 2026-10-13; граница — баланс Studio)"
  planned: "черновик ≈ 30 + H2 95"
VISUAL_CARD_ID: "AN-38"

Рубрика: concept-sheet.md §11, полный раздел:
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
   остальное — команда `references/acceptance-and-blender.md` §8.4, с `windows.sandbox="unelevated"`).
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
| `acceptor` | `{profile: "Opus xhigh"\|"Sol 6.1 xhigh", session_id}` |
| `executor_session_id` | сессия запускающего агента (≠ `acceptor.session_id`) |
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
Объект: <1a: дизайн-front design/<key>-front.png | 1c: виды <key>-front/side/back.png и лист sheet-<key>.png>.
Открой каждый файл как картинку. Прочитай checks-report.json и generation-records.json.
Выдержка карточки ассета: DESCRIPTION, ANCHORS, PALETTE, ANATOMY, WEAPON_HAND, SIDE_VIEW (<значения>).
Эталон качества: <QUALITY_REFERENCE> (открой). Для 1c — ещё дизайн design/<key>-front.png и ортопроекции 1b.
Рубрика: references/concept-sheet.md раздел 11 (таблица S, C, Q, P). На 1a C = 1,5 по фиксированному правилу
раздела 11, в rework_fix_list C на 1a не включай. T- или A-поза = S 0. Балл — по якорям, шаг 0,5; обоснование с
именами файлов из frames.files. Гейт один — G-CHECKS по checks-report.json (код 0 → PASS); WARN не гейт, учитывай их
в C. rework_fix_list — только измерения < 2 и G-CHECKS при FAIL; у пункта: item, frame (вид), fix (одна английская
строка для CORRECTION), tool (Codex 1c CORRECTION | Tripo 1b черновик | Codex 1a). Вердикт посчитай по правилам
раздела 11; при не-pass заполни verdict_reason. Заполни все поля таблицы «Карточка» раздела 11 (date, previous_card,
frames как {dir, files} с именами без пути). Верни только JSON карточки.
```


Применяй рубрику 1c, четыре числовых измерения S,C,Q,P. C здесь оценивается по согласованности всех трёх видов; фиксированный C 1.5 относится только к 1a.
T- или A-поза = S 0. Балл по якорям, шаг 0.5; обоснование с именами файлов из frames.files. G-CHECKS единственный гейт: checks-report.json#summary.FAIL = 0; source строго art/imagegen/concept-ancient-leshen-codex/checks-report.json. WARN не гейт, учитывай их в C.
rework_fix_list — только измерения <2 и G-CHECKS при FAIL; пункт item, frame (имя вида из frames.files), fix (одна английская строка для CORRECTION), tool (Codex 1c CORRECTION | Tripo 1b черновик | Codex 1a). При не-pass список должен покрывать каждое измерение ниже 2 и FAIL гейта. При pass [] и замечания в known_issues. known_issues.item только S,C,Q,P,G-CHECKS.
Причину, уже присутствующую в орто, направляй tool Tripo 1b черновик; ошибку в самом approved design — Codex 1a. Для поверхностной детали, рамки или ракурса одного вида — Codex 1c CORRECTION. Укажи конкретный дефектный вид, не назначай слепую перегенерацию.
score half-up: sum(S,C,Q,P)/8*10. Гейт FAIL, любое значение <1 или score <8 => return_to_stage_1, иначе pass; r4 без pass => escalate_user. При не-pass заполни verdict_reason.

Заполни все поля таблицы «Карточка» §11. Обязательные константы (скопировать без изменения):
{"schema": "unmatched.concept-acceptance/1", "kind": "concept", "asset_id": "ASSET-ANCIENT-LESHEN-001", "clip": null,
 "cycle": "r1", "date": "2026-10-20", "previous_card": null,
 "frames": {"dir": "art/imagegen/concept-ancient-leshen-codex", "files": ["sheet-ancient-leshen.png", "ancient-leshen-front.png", "ancient-leshen-side.png", "ancient-leshen-back.png", "checks-report.json"]},
 "acceptor": {"profile": "Z-Code GLM-5.3-Flash", "session_id": "zcode:calibration-c2"},
 "executor_session_id": "launcher:calibration-20261020", "decided_by": "delegated (ВР-реестр 2026-10-06)"}
Поля accepted_object и reports можно опустить (их подставит запускающий).

Выдача: запиши ТОЛЬКО JSON карточки (UTF-8, без Markdown-обёртки) в файл
`docs/art-pipeline/evidence/skill-batch-2026-10-20/zcode-calibration/c2-leshen-sheet/card-zcode.json`. Больше ничего не создавай и не меняй, не коммить. Первым ключом JSON добавь
"model_seen": "<точное имя модели, которой ты работаешь>", вторым "images_seen": true|false (видел ли ты пиксели всех
изображений). Баллы S, C, Q, P — числа 0–2 с шагом 0,5, у каждого rationale (по-русски, с именами файлов) и frames.
