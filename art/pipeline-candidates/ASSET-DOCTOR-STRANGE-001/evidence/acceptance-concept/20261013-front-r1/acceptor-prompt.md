# Stage 1a concept acceptance ASSET-DOCTOR-STRANGE-001, r1
Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
No credits are spent. You are a separate acceptor, Sol 6.1 xhigh, not the executor. Read-only: no generation, writes,
agents, git, browser, Unreal, Blender, Tripo, SYNTX, or validate_card.py. Return only the JSON card. CLI writes it.
Read text as UTF-8 (PowerShell Get-Content -Raw -Encoding UTF8; Python -X utf8).
Image 1 is art/imagegen/concept-doctor-strange-codex/design/doctor-strange-front.png, image 2 is the QUALITY_REFERENCE art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Inspect both at original resolution.
Identity comes from the GAME DATABASE Hero.name: KEY=DoctorStrange; DESCRIPTION_EN=Doctor Strange from the Marvel comics (Unmatched: Brains and Brawn): sorcerer in a dark blue tunic, red Cloak of Levitation with a high collar, golden Eye of Agamotto amulet, yellow gloves, grey temples and goatee, one hand raised in a mystic gesture..
S judges recognisability of THAT character, including its named identity, not just a generic matching costume.
Read only these text inputs: art/pipeline-candidates/ASSET-DOCTOR-STRANGE-001/asset-card.yaml, art/imagegen/concept-doctor-strange-codex/palette.json, art/imagegen/concept-doctor-strange-codex/design/checks-report.json,
art/imagegen/concept-doctor-strange-codex/generation-records.json, art/imagegen/concept-doctor-strange-codex/verification.json. Previous card: None.
Asset card:
# asset-card.yaml — 3d-model-pipeline, этап 0 (поля этапа 1). Записан пакетно 2026-10-13.
# Реестр asset-registry.json, строка 06-tasks/anim.csv и пробы исполнителей этапов 2+ отложены
# (пользователь 2026-10-13: «Все остальные этапы нужно будет отложить»).
ASSET_ID: ASSET-DOCTOR-STRANGE-001
CONTENT_KEY: doctor-strange
KEY: DoctorStrange
ROLE: hero
ANATOMY: humanoid
GAME_ROLE: hero
WEAPON_HAND: none
SIDE_VIEW: left
DESCRIPTION_EN: "Doctor Strange from the Marvel comics (Unmatched: Brains and Brawn): sorcerer in a dark blue tunic, red Cloak of Levitation with a high collar, golden Eye of Agamotto amulet, yellow gloves, grey temples and goatee, one hand raised in a mystic gesture."
ANCHORS_EN: "red high-collared cloak; Eye of Agamotto amulet; yellow gloves; grey temples and goatee"
PALETTE:
  main:
    - {name: tunic blue, hex: "#22305E"}
    - {name: cloak red, hex: "#A3242A"}
    - {name: glove yellow, hex: "#D9B23A"}
  accent: {name: amulet gold, hex: "#D4AE45"}
QUALITY_REFERENCE:
  - art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png
ASSET_DIR: art/pipeline-candidates/ASSET-DOCTOR-STRANGE-001
decided_by: delegated (ВР-реестр 2026-10-06)
NOTES: ростер после MVP вне объёма ВР-18 — запуск по запросу пользователя 2026-10-13 (волна 1a).

The complete concept rubric follows; use concept rules, not model rules:
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


Required constants (copy without modifications):
{
  "schema": "unmatched.concept-acceptance/1",
  "kind": "concept",
  "asset_id": "ASSET-DOCTOR-STRANGE-001",
  "clip": null,
  "cycle": "r1",
  "date": "2026-10-13",
  "previous_card": null,
  "accepted_object": [
    {
      "path": "art/imagegen/concept-doctor-strange-codex/design/doctor-strange-front.png",
      "sha256": "6a14c00f2c022333e0bcca9a658373edef0451b0e48bab5e54dbdb57c64aff20"
    }
  ],
  "frames": {
    "dir": "art/imagegen/concept-doctor-strange-codex/design",
    "files": [
      "doctor-strange-front.png",
      "checks-report.json"
    ]
  },
  "reports": [
    "art/imagegen/concept-doctor-strange-codex/design/checks-report.json",
    "art/imagegen/concept-doctor-strange-codex/generation-records.json",
    "art/imagegen/concept-doctor-strange-codex/verification.json"
  ],
  "acceptor": {
    "profile": "Sol 6.1 xhigh",
    "session_id": "codex:pending"
  },
  "executor_session_id": "history:ASSET-DOCTOR-STRANGE-001-1a-design-front-g3",
  "decided_by": "delegated (ВР-реестр 2026-10-06)"
}
C must equal 1.5 with rationale «1a: один вид, C не оценивается; фиксированное значение concept-sheet.md §11»
and frames ["doctor-strange-front.png"]. Never include C in rework_fix_list. WARN cannot change fixed C.
G-CHECKS uses checks-report.json#summary.FAIL: 0 means PASS, otherwise FAIL. Cite the actual key and value in note.
Scores S,Q,P: inspect images yourself, steps of 0.5. score = sum(S,C,Q,P)/8*10, rounded half-up to one decimal.
FAIL gate, any score <1, or score <8 => return_to_stage_1; otherwise pass; r4 without pass => escalate_user.
For non-pass rework_fix_list covers S/Q/P below 2 and G-CHECKS if FAIL: item, frame, one precise English fix line,
tool "Codex 1a". For pass the list is empty. known_issues items only S,C,Q,P,G-CHECKS; no model dimensions.
status_note for pass: «художественно принято, по делегированию (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)».
acceptor.session_id stays codex:pending; launcher alone replaces it with the actual thread_id. No other card edits.
Executor checklist limit_reached: [].
Return only JSON matching tools/art/acceptance/asset-acceptance-2.output-concept.schema.json.
