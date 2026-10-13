# Independent concept acceptance: ASSET-MARTIAN-INVADER-001, stage 1a, r2
User delegation (2026-10-13, verbatim): «начинай делать все остальные параллельно согласно скиллу».
Credits: none. This is independent read-only acceptance; other stages are deferred.
You are Sol 6.1 xhigh, a fresh acceptor session separate from the executor.
Do not edit files or generate images; do not run agents, git, Unreal, Blender, browsers, Tripo, SYNTX or validate_card.py.
Only the CLI writes the returned JSON card. Use UTF-8 for reads (PowerShell Get-Content -Raw -Encoding UTF8).
Review the two attached images at their original dimensions: first art/imagegen/concept-martian-invader-codex/design/martian-invader-front.png, then
art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. These are the only image inputs.
Read art/imagegen/concept-martian-invader-codex/design/checks-report.json, art/imagegen/concept-martian-invader-codex/generation-records.json,
art/imagegen/concept-martian-invader-codex/verification.json, art/imagegen/concept-martian-invader-codex/palette.json and
art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/asset-card.yaml. Do not read any earlier acceptance card or final.json:
previous_card is a provenance link only; assess current images independently.
Figure identity is the database Hero.name recorded as KEY and DESCRIPTION_EN, not a generic alien costume.

Asset card (description, anchors, palette, anatomy, weapon side):
# asset-card.yaml — 3d-model-pipeline, этап 0 (поля этапа 1). Записан пакетно 2026-10-13.
# Реестр asset-registry.json, строка 06-tasks/anim.csv и пробы исполнителей этапов 2+ отложены
# (пользователь 2026-10-13: «Все остальные этапы нужно будет отложить»).
ASSET_ID: ASSET-MARTIAN-INVADER-001
CONTENT_KEY: martian-invader
KEY: MartianInvader
ROLE: hero
ANATOMY: humanoid
GAME_ROLE: hero
WEAPON_HAND: right
SIDE_VIEW: left
DESCRIPTION_EN: "The Martian Invader, a pulp-era villain (Unmatched: Tales to Amaze): big-brained alien with a large exposed head inside a glass dome helmet, slim body in a silver space suit with fins, ray gun in his RIGHT hand."
ANCHORS_EN: "ray gun in the RIGHT hand; glass dome helmet; big exposed brain; silver space suit with fins"
PALETTE:
  main:
    - {name: suit silver, hex: "#B8BEC4"}
    - {name: skin green, hex: "#7AA65A"}
    - {name: fin red, hex: "#B3202A"}
  accent: {name: ray cyan, hex: "#4AD9E0"}
QUALITY_REFERENCE:
  - art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png
ASSET_DIR: art/pipeline-candidates/ASSET-MARTIAN-INVADER-001
decided_by: delegated (ВР-реестр 2026-10-06)
NOTES: ростер после MVP вне объёма ВР-18 — запуск по запросу пользователя 2026-10-13 (волна 1a).


Official concept rubric (concept-sheet.md section 11):
 Приёмка: гейты, рубрика, вердикт, карточка

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



Fixed metadata for your output (fill the other schema fields from the evidence and independent judgement):
{
  "schema": "unmatched.concept-acceptance/1",
  "kind": "concept",
  "asset_id": "ASSET-MARTIAN-INVADER-001",
  "clip": null,
  "cycle": "r2",
  "date": "2026-10-13",
  "previous_card": "art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/evidence/acceptance-concept/20261013-front-r1/card.json",
  "accepted_object": [
    {
      "path": "art/imagegen/concept-martian-invader-codex/design/martian-invader-front.png",
      "sha256": "d5698b947f2bc320e4430b817a0f3c7e52088b9ab8e33f507f54c09431d07904"
    }
  ],
  "frames": {
    "dir": "art/imagegen/concept-martian-invader-codex/design",
    "files": [
      "martian-invader-front.png",
      "checks-report.json"
    ]
  },
  "reports": [
    "art/imagegen/concept-martian-invader-codex/design/checks-report.json",
    "art/imagegen/concept-martian-invader-codex/generation-records.json",
    "art/imagegen/concept-martian-invader-codex/verification.json"
  ],
  "acceptor": {
    "profile": "Sol 6.1 xhigh",
    "session_id": "codex:pending"
  },
  "executor_session_id": "codex:01a135fc-5aff-7093-b885-c121cca5f11d",
  "decided_by": "delegated (ВР-реестр 2026-10-06)"
}

Stage 1a uses S,C,Q,P only. C must be exactly 1.5 with rationale
"1a: один вид, C не оценивается; фиксированное значение concept-sheet.md §11"
and frames ["martian-invader-front.png"]. Never include C in rework_fix_list. WARN cannot change fixed C.
G-CHECKS is the sole gate, with status from checks-report.json summary.FAIL: zero => PASS, otherwise FAIL.
Its source is art/imagegen/concept-martian-invader-codex/design/checks-report.json. Describe source keys in its note.
S,Q,P use 0..2 in 0.5 steps; score is half-up sum(S,C,Q,P)/8*10. Judge independently; do not infer quality from code exit.
FAIL gate, any dimension below 1, or score below 8 => return_to_stage_1; otherwise pass.
At non-pass, rework_fix_list covers each S/Q/P below 2 and each FAIL gate, with one English correction sentence,
item, frame and tool "Codex 1a". At pass rework_fix_list is []. known_issues uses only S,C,Q,P,G-CHECKS.
Frames in rationales and lists are only filenames from frames.files. No model scores or model gates.
At pass, status_note contains "художественно принято, по делегированию" and cites docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md.
Acceptor session_id stays codex:pending; the launcher replaces it with this CLI thread_id afterwards.
Executor limit_reached is []; assess any failed checklist items by the rubric.
Return only the JSON card conforming to tools/art/acceptance/asset-acceptance-2.output-concept.schema.json.
