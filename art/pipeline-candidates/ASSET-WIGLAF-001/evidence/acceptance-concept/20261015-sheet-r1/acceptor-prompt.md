# Приёмка 1c sheet ASSET-WIGLAF-001, цикл r1
Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
Задача пользователя (дословно): «сам составь список того чего в игре не хватает и генерируй и ревьювь».
Траты на приёмке: нет. Ты — отдельный приёмщик «Sol 6.1 xhigh», не исполнитель. Файлы не правишь, ничего не генерируешь, не запускаешь validate_card.py, Blender, git, Unreal, Tripo, SYNTX, браузер или других агентов.
Твоя единственная выдача — JSON-карточка. Её сохраняет CLI. Текстовые файлы читай так, чтобы кириллица дошла целой: песочница пишет вывод в OEM-кодировке, `Get-Content -Encoding UTF8` даёт кракозябры, смена `[Console]::OutputEncoding` запрещена. Читай каждый текстовый файл командой `Get-Content <файл> -Raw -Encoding OEM` или `cmd /c type <файл>`. Если кириллица всё равно пришла кракозябрами — это сбой окружения: не оценивай по догадкам, верни карточку, где verdict_reason начинается со слов «СБОЙ ОКРУЖЕНИЯ: кириллица не читается» (concept-sheet.md §11, RA-03). Не читай посторонние карточки, чаты или пакеты.
Ты — приёмщик этапа 1 скилла 3d-model-pipeline (концепт-лист). Объект: 1c виды wiglaf-front/side/back.png и лист sheet-wiglaf.png пакета art/imagegen/concept-wiglaf-codex.
Открой каждый файл как картинку: все изображения переданы отдельными -i. Порядок приложенных изображений:
[
  "art/imagegen/concept-wiglaf-codex/wiglaf-front.png",
  "art/imagegen/concept-wiglaf-codex/wiglaf-side.png",
  "art/imagegen/concept-wiglaf-codex/wiglaf-back.png",
  "art/imagegen/concept-wiglaf-codex/sheet-wiglaf.png",
  "art/imagegen/concept-wiglaf-codex/design/wiglaf-front.png",
  "art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_back.png",
  "art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_front.png",
  "art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_left.png",
  "art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_right.png",
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Для 1c — утверждённый дизайн art/imagegen/concept-wiglaf-codex/design/wiglaf-front.png и ортопроекции 1b art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos. ortho_right — дополнительный вид того же черновика; SIDE_VIEW заявки задаёт сторону принимаемого side.
Прочитай art/imagegen/concept-wiglaf-codex/checks-report.json, art/imagegen/concept-wiglaf-codex/generation-records.json, art/imagegen/concept-wiglaf-codex/verification.json, art/imagegen/concept-wiglaf-codex/palette.json, art/pipeline-candidates/ASSET-WIGLAF-001/asset-card.yaml и art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho-framing.json. Предыдущая карточка: None; на r2 проверь закрытие её списка, а баллы ставь заново.
Выдержка карточки ассета (DESCRIPTION_EN, ANCHORS_EN, PALETTE, ANATOMY, WEAPON_HAND, SIDE_VIEW):
# asset-card.yaml — 3d-model-pipeline, этап 0 (поля этапа 1). Записан пакетно 2026-10-13.
# Реестр asset-registry.json, строка 06-tasks/anim.csv и пробы исполнителей этапов 2+ отложены
# (пользователь 2026-10-13: «Все остальные этапы нужно будет отложить»).
ASSET_ID: ASSET-WIGLAF-001
CONTENT_KEY: wiglaf
KEY: Wiglaf
ROLE: hero
ANATOMY: humanoid
GAME_ROLE: sidekick
WEAPON_HAND: right
SIDE_VIEW: right
SIDE_VIEW_DECISION: "delegated: 2026-10-15, concept-sheet 4.1; ortho_left hides the right-hand axe grip behind the shield and torso, ortho_right exposes the grip."
DESCRIPTION_EN: "Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm."
ANCHORS_EN: "hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet"
PALETTE:
  main:
    - {name: leather, hex: "#7A5634"}
    - {name: moss green, hex: "#4E6B3A"}
    - {name: iron, hex: "#5E6266"}
  accent: {name: boar red, hex: "#9A3428"}
QUALITY_REFERENCE:
  - art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png
ASSET_DIR: art/pipeline-candidates/ASSET-WIGLAF-001
decided_by: delegated (ВР-реестр 2026-10-06)
NOTES: ростер после MVP вне объёма ВР-18 — запуск по запросу пользователя 2026-10-13 (волна 1a).
POLY_BUDGET: {figure_tris_max: 45000, base_tris_max: 2500}
CREDITS:
  ledger: "docs/game-design/visual/credits-ledger.json"
  tripo_limit: "нет лимита (решение пользователя 2026-10-13; граница — баланс Studio)"
  planned: "черновик ≈ 30 + H2 95"
VISUAL_CARD_ID: "AN-131"

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


Применяй рубрику 1c, четыре числовых измерения S,C,Q,P. C здесь оценивается по согласованности всех трёх видов; фиксированный C 1.5 относится только к 1a.
T- или A-поза = S 0. Балл по якорям, шаг 0.5; обоснование с именами файлов из frames.files. G-CHECKS единственный гейт: checks-report.json#summary.FAIL = 0; source строго art/imagegen/concept-wiglaf-codex/checks-report.json. WARN не гейт, учитывай их в C.
rework_fix_list — только измерения <2 и G-CHECKS при FAIL; пункт item, frame (имя вида из frames.files), fix (одна английская строка для CORRECTION), tool (Codex 1c CORRECTION | Tripo 1b черновик | Codex 1a). При не-pass список должен покрывать каждое измерение ниже 2 и FAIL гейта. При pass [] и замечания в known_issues. known_issues.item только S,C,Q,P,G-CHECKS.
Причину, уже присутствующую в орто, направляй tool Tripo 1b черновик; ошибку в самом approved design — Codex 1a. Для поверхностной детали, рамки или ракурса одного вида — Codex 1c CORRECTION. Укажи конкретный дефектный вид, не назначай слепую перегенерацию.
score half-up: sum(S,C,Q,P)/8*10. Гейт FAIL, любое значение <1 или score <8 => return_to_stage_1, иначе pass; r4 без pass => escalate_user. При не-pass заполни verdict_reason.
Заполни все поля таблицы Карточка §11; обязательные константы (скопировать без изменения):
{
  "schema": "unmatched.concept-acceptance/1",
  "kind": "concept",
  "asset_id": "ASSET-WIGLAF-001",
  "clip": null,
  "cycle": "r1",
  "date": "2026-10-15",
  "previous_card": null,
  "accepted_object": [
    {
      "path": "art/imagegen/concept-wiglaf-codex/wiglaf-front.png",
      "sha256": "b1d1b50becff40bf400cdd0814a76a267bd3fdd8cd86c4ea1c7185dcc34d4ab0"
    },
    {
      "path": "art/imagegen/concept-wiglaf-codex/wiglaf-side.png",
      "sha256": "4b6f5b59b504d36051e4d269ef0feba18bbaea27c7a1abd40f35139ae40ee2c5"
    },
    {
      "path": "art/imagegen/concept-wiglaf-codex/wiglaf-back.png",
      "sha256": "8d8cad77da69b922a464720a92d45ab1c45f6f94e182f8a63ed0f9406bdc12a7"
    }
  ],
  "frames": {
    "dir": "art/imagegen/concept-wiglaf-codex",
    "files": [
      "sheet-wiglaf.png",
      "wiglaf-front.png",
      "wiglaf-side.png",
      "wiglaf-back.png",
      "checks-report.json"
    ]
  },
  "reports": [
    "art/imagegen/concept-wiglaf-codex/checks-report.json",
    "art/imagegen/concept-wiglaf-codex/generation-records.json",
    "art/imagegen/concept-wiglaf-codex/verification.json"
  ],
  "acceptor": {
    "profile": "Sol 6.1 xhigh",
    "session_id": "codex:pending"
  },
  "executor_session_id": "codex-app:01a13e0b-a911-7190-9a60-c87273f3db77",
  "decided_by": "delegated (ВР-реестр 2026-10-06)"
}
При pass status_note содержит «художественно принято, по делегированию (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)».
В строгой схеме необязательные поля представлены null. Acceptor session_id codex:pending запускающий заменит на thread_id; другой правки не будет.
Верни только JSON карточки по tools/art/acceptance/asset-acceptance-2.output-concept.schema.json.
