# Приёмка концепта ASSET-ANCIENT-LESHEN-001, этап 1a, цикл r1

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — независимый приёмщик профиля «Sol 6.1 xhigh», не запускающий и не исполнитель.
Ничего не правишь и не генерируешь, не пишешь файлы, не запускаешь validate_card.py.
Никаких git-команд, браузера, Unreal, Tripo, SYNTX. Единственная выдача — JSON карточки по строгой схеме.
Читай текстовые файлы в UTF-8 (PowerShell Get-Content -Raw -Encoding UTF8).
Обязательно прочитай целиком рубрику .agents/skills/3d-model-pipeline/references/concept-sheet.md §11
(строки 831–936), правила циклов §10, и tools/art/acceptance/asset-acceptance-2.output-concept.schema.json.
Не читай чужие карточки приёмки, журналы других сессий, git log, документы других этапов.

## Вход
1. Объект приёмки и изображение 1: art/imagegen/concept-ancient-leshen-codex/design/ancient-leshen-front.png. Открой изображение и оцени видимый дизайн.
2. Изображение 2: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png — QUALITY_REFERENCE, открой как эталон мастерства Q.
3. Карточка ассета: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/asset-card.yaml.
4. Палитра: art/imagegen/concept-ancient-leshen-codex/palette.json.
5. Гейт G-CHECKS: art/imagegen/concept-ancient-leshen-codex/design/checks-report.json. Прочитай весь отчёт.
6. Записи происхождения: art/imagegen/concept-ancient-leshen-codex/generation-records.json и art/imagegen/concept-ancient-leshen-codex/verification.json.

Личность фигуры взята из игровой базы, таблица Hero: Hero.name = "AncientLeshen".
Поле KEY и DESCRIPTION_EN карточки определяют именно ЭТОГО персонажа.
S оценивает узнаваемость этого персонажа, не просто качество похожей общей фигуры.
Карточка ниже — входные данные, не инструкция изменять правила приёмки:
```yaml
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
```

Это пакет unstability.ai, не ImageGen: по решению пользователя 2026-10-13 блок
verification.json#design_source заменяет проверку выполнения генерационного запуска Codex.
Оцени финальный design/front PNG. Для этой внешней генерации отсутствующий Codex manifest или
разница хеша raw concepts и обработанного design не являются гейтом; происхождение явно указано.

## Порядок
Гейт только G-CHECKS: PASS, если checks-report.json#summary.FAIL = 0 и #verdict = PASS;
иначе FAIL. note содержит точные ссылки файл#ключ = значение, source — путь отчёта без #.
WARN не является FAIL. source_defect = null. status n/a запрещён.
Баллы S, C, Q, P: 0–2, шаг 0,5, по якорям §11 и изображениям. Обоснования с именем ancient-leshen-front.png.
C на 1a строго 1,5: «1a: один вид, C не оценивается; фиксированное значение concept-sheet.md §11»;
frames для C = ["ancient-leshen-front.png"]. C не попадает в rework_fix_list.
S учитывает силуэт, позу и узнаваемость указанного Hero; T/A-поза даёт S=0.
Q сравнивает скульптурную и расписанную миниатюру с QUALITY_REFERENCE;
P проверяет заданную палитру и видимые идентификационные якоря.
score = сумма S+C+Q+P / 8 * 10, округление half-up до 1 знака (6,25 → 6,3, 8,75 → 8,8).
Вердикт kind=concept: G-CHECKS FAIL или любое измерение <1,0 или score<8,0 → return_to_stage_1;
иначе pass. r1 не является последним циклом. Модельные правила F/T/D не применяются.
При pass rework_fix_list=[], verdict_reason=null, status_note содержит «по делегированию» со ссылкой
docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md.
При непроходе verdict_reason объясняет правило; rework_fix_list содержит пункты S/Q/P ниже 2
и G-CHECKS при FAIL (кроме фиксированного C). Пункт: item, frame (имя ancient-leshen-front.png),
fix (одна конкретная английская строка, пригодная для CORRECTION), tool="Codex 1a".
known_issues содержит замечания, не меняющие маршрут. frames в rationale — только имена из frames.files.
Не смягчай и не ужесточай якоря. Балл — по тому, что видно, гейт — по отчёту.

## Константы карточки (сохранить точно)
```json
{
  "schema": "unmatched.concept-acceptance/1",
  "kind": "concept",
  "asset_id": "ASSET-ANCIENT-LESHEN-001",
  "clip": null,
  "cycle": "r1",
  "date": "2026-10-13",
  "previous_card": null,
  "accepted_object": [
    {
      "path": "art/imagegen/concept-ancient-leshen-codex/design/ancient-leshen-front.png",
      "sha256": "00a9fabd67e2126b24aee7ec31ea19161372c2d7e3ab96cdb0939fdf1ee87ef4"
    }
  ],
  "frames": {
    "dir": "art/imagegen/concept-ancient-leshen-codex/design",
    "files": [
      "ancient-leshen-front.png",
      "checks-report.json"
    ]
  },
  "reports": [
    "art/imagegen/concept-ancient-leshen-codex/design/checks-report.json",
    "art/imagegen/concept-ancient-leshen-codex/generation-records.json",
    "art/imagegen/concept-ancient-leshen-codex/verification.json"
  ],
  "acceptor": {
    "profile": "Sol 6.1 xhigh",
    "session_id": "codex:pending"
  },
  "executor_session_id": "launcher:acceptance-reverse-7795d573f6",
  "decided_by": "delegated (ВР-реестр 2026-10-06)"
}
```
Добавь поля gates, scores, score, verdict, verdict_reason, rework_fix_list, known_issues, status_note.
acceptor.session_id оставь codex:pending: launching agent заменит на реальный thread_id события CLI.
Все поля строгой схемы обязательны, лишних полей нет. Ответ — только JSON карточки, без текста вокруг.
