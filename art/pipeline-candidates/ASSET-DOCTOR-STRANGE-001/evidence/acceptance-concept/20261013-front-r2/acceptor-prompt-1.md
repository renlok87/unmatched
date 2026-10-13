# Приёмка ASSET-DOCTOR-STRANGE-001, этап 1a, цикл r2

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
Траты: нет — кредиты Tripo/SYNTX не расходуются. Пользователь явно выбрал «Sol 6.1 xhigh».
Ты — отдельный приёмщик концепта, не исполнитель и не запускающий агент. Ничего не правь, не генерируй, не пиши.
Не запускай скрипты или validate_card.py. Не выполняй git-команды, не открывай браузер, Unreal, Tripo, SYNTX.
Разрешены команды только чтения входных текстовых файлов. Читай UTF-8 явно.

Рубрика, обязательная к прочтению: .agents/skills/3d-model-pipeline/references/concept-sheet.md §11 (полностью).
Общая механика: .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md §6, §7, §8.1, §8.2, §8.4, §8.5;
применяй к концепту именно S/C/Q/P и вердикты concept-sheet.md §11, а не правила модели S/F/T/D.
Строгая схема: tools/art/acceptance/asset-acceptance-2.output-concept.schema.json.

## Входы
- Объект и attached image 1: art/imagegen/concept-doctor-strange-codex/design/doctor-strange-front.png — НОВЫЙ Recraft дизайн r2.
- Эталон качества и attached image 2: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (и остальные перечисленные QUALITY_REFERENCE файлы).
- Заявка: art/pipeline-candidates/ASSET-DOCTOR-STRANGE-001/asset-card.yaml.
- Палитра: art/imagegen/concept-doctor-strange-codex/palette.json.
- Гейт G-CHECKS: art/imagegen/concept-doctor-strange-codex/design/checks-report.json. Его inputs.sha256 относится к текущему r2.
- Записи: art/imagegen/concept-doctor-strange-codex/generation-records.json, art/imagegen/concept-doctor-strange-codex/verification.json.
- История: art/pipeline-candidates/ASSET-DOCTOR-STRANGE-001/evidence/acceptance-concept/20261013-front-r1/card.json; проверь закрытие прежних замечаний, но оцени текущий дизайн заново.
Открой текущий front и QUALITY_REFERENCE как изображения. Оценка только по текущему front, не по старым PNG.
Старые записи verification относятся к r1; они не отдельный гейт. Внешняя генерация и историческая нормализация
задника заданы пользователем для этой волны. Не подменяй художественную оценку аудитом прошлых операций.

Идентичность фигуры взята из игровой БД, таблица Hero, поле Hero.name, отражённое в KEY / DESCRIPTION_EN заявки.
S оценивает узнаваемость ИМЕННО ЭТОГО персонажа, а не лишь похожего архетипа. KEY=DoctorStrange.
DESCRIPTION_EN: Doctor Strange from the Marvel comics (Unmatched: Brains and Brawn): sorcerer in a dark blue tunic, red Cloak of Levitation with a high collar, golden Eye of Agamotto amulet, yellow gloves, grey temples and goatee, one hand raised in a mystic gesture.
ANCHORS_EN: red high-collared cloak; Eye of Agamotto amulet; yellow gloves; grey temples and goatee
ANATOMY=humanoid; WEAPON_HAND=none; SIDE_VIEW=left.
PALETTE: {"main": [{"name": "tunic blue", "hex": "#22305E"}, {"name": "cloak red", "hex": "#A3242A"}, {"name": "glove yellow", "hex": "#D9B23A"}], "accent": {"name": "amulet gold", "hex": "#D4AE45"}}

## Правила
- S, Q, P — по визуальным якорям §11, числа 0/0.5/1/1.5/2. T- или A-поза = S 0.
- C РОВНО 1.5; rationale «1a: один вид, C не оценивается; фиксированное значение concept-sheet.md §11»;
  frames=["doctor-strange-front.png"]. Не включай C в rework_fix_list или в исправления.
- Единственный гейт G-CHECKS по текущему отчёту: summary.FAIL=0 и verdict PASS → PASS; иначе FAIL. n/a запрещено.
  source — путь самого отчёта без #; note содержит фактические summary.PASS/WARN/FAIL, а source_defect=null.
- score = (S+C+Q+P)/8*10 с half-up до одной цифры, не Python round().
- Любой FAIL-гейт / любое измерение <1.0 / score<8.0 → return_to_stage_1; иначе pass. Сейчас r2, не r4.
- При return_to_stage_1 заполни verdict_reason (>=10 символов) и rework_fix_list по каждому недостатку
  S/Q/P ниже 2 и G-CHECKS при FAIL: item, frame из frames.files, fix ОДНА английская строка для CORRECTION,
  tool="Codex 1a". Исправления будут переданы Claude для внешней перегенерации, сам ничего не запускай.
- При pass rework_fix_list=[], verdict_reason=null; замечания можно записать в known_issues.
- При pass status_note="художественно принято, по делегированию (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)";
  иначе status_note="". known_issues — массив, может быть []. Все frames в scores/known_issues — имена из frames.files.
- Баллы не смягчай и не ужесточай ради порога, сверяй видимое с рубрикой. На 1a C не меняется из-за WARN.

Константы карточки (копируй точно, баллы и вердикт поставь сам):
{
  "schema": "unmatched.concept-acceptance/1",
  "kind": "concept",
  "clip": null,
  "asset_id": "ASSET-DOCTOR-STRANGE-001",
  "cycle": "r2",
  "date": "2026-10-13",
  "previous_card": "art/pipeline-candidates/ASSET-DOCTOR-STRANGE-001/evidence/acceptance-concept/20261013-front-r1/card.json",
  "accepted_object": [
    {
      "path": "art/imagegen/concept-doctor-strange-codex/design/doctor-strange-front.png",
      "sha256": "507e2f853e78f6c3a724b9ed0bb7361c7fe82f3ff080da1dbb59721e015f1543"
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
  "executor_session_id": "codex:01a134fa-9511-76c2-a295-98ad709fec31",
  "decided_by": "delegated (ВР-реестр 2026-10-06)"
}

Верни ТОЛЬКО JSON-карточку строгой схемы, все её поля обязательны. Не добавляй stage или другие поля.
