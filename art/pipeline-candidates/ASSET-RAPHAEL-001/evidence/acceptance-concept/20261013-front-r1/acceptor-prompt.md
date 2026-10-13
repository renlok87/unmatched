# Приёмка ASSET-RAPHAEL-001, stage 1a design-front, цикл r1
Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
Пользователь 2026-10-13 поручил принять концепты каждого персонажа игровой таблицы Hero. Траты Tripo/SYNTX: нет.
Ты отдельный независимый приёмщик Sol 6.1 xhigh, не исполнитель. Только чтение; ничего не генерируй, не меняй,
не запускай Blender, браузер, git, validate_card.py или другие производственные скрипты. Ответ только JSON карточки.
Читай текст в UTF-8. В КАЖДОЙ PowerShell-команде чтения сначала выполни
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false);
затем Get-Content -Raw -Encoding UTF8. Без установки Console.OutputEncoding вывод повреждается.
Файлы не переписывай. Рубрики читай только по указанным разделам, а не остальные этапы целиком.
Если shell искажает кириллицу несмотря на Console.OutputEncoding, надёжное чтение — Python:
import json; from pathlib import Path; print(json.dumps(Path(path).read_text(encoding='utf-8-sig'),ensure_ascii=True))
Это выдаёт ASCII с Unicode escapes без потери содержания; можно сразу использовать этот способ.
Обязательная рубрика: .agents/skills/3d-model-pipeline/references/concept-sheet.md §11 целиком;
общие правила независимости, формула half-up и запись карточки из acceptance-and-blender.md §6, §7, §8.4.
Это kind=concept, НЕ model: модельные S/F/T/D и возврат по S с пустым fix-list здесь не применяются.

Входы и изображения:
- Изображение 1: art/imagegen/concept-raphael-codex/design/raphael-front.png — принимай только этот 1a front, открой как изображение в полном размере.
- Эталон(ы) качества, приложенные после front: ["art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"]; открой каждое изображение.
- Карточка ассета art/pipeline-candidates/ASSET-RAPHAEL-001/asset-card.yaml — прочитай. KEY и DESCRIPTION_EN происходят из Hero.name игровой БД.
  S оценивает узнаваемость ИМЕННО ЭТОГО персонажа, а не произвольной подходящей миниатюры и не персонажа эталона.
- Палитра art/imagegen/concept-raphael-codex/palette.json; отчёт art/imagegen/concept-raphael-codex/design/checks-report.json; записи art/imagegen/concept-raphael-codex/generation-records.json; проверка art/imagegen/concept-raphael-codex/verification.json.
- Только эти входы, рубрики и схема; не читай чужие ассеты, другие карточки текущего цикла, чат, git или сеть.
- Предыдущая карточка null; на r2+ прочитай её fix-list, затем оцени свежий front заново.
- Исчерпанные пункты CHECKLIST этого запуска: [{"view": "design-front", "failed_items": ["No weapon or held object. (both arms clearly apart from the torso, not a T-pose, not an A-pose);"], "failed_ids": ["CHECKLIST-04"]}]; оцени по рубрике.

Правила концепта §11:
1. Только гейт G-CHECKS по design/checks-report.json: summary.FAIL=0 и verdict=PASS => PASS;
   FAIL => return_to_stage_1. WARN не гейт, его видимые последствия учитывай в S/Q/P, C фиксирован.
2. S,C,Q,P числа 0/0.5/1/1.5/2. S — читаемость и идентичность DB героя; Q — детализация против QUALITY_REFERENCE;
   P — палитра и видимые якоря. Недоступные с front задние якоря не выдумывай и не требуй невозможного вида.
   T- или A-поза => S=0. Оцени то, что видно, без смягчения или ужесточения.
3. C ВСЕГДА 1.5 на 1a, rationale «1a: один вид, C не оценивается; фиксированное значение concept-sheet.md §11».
   C.frames=["raphael-front.png"]. C НЕ включать в rework_fix_list.
4. score=sum(S,C,Q,P)/8*10, округление half-up (8.125=>8.1, 8.75=>8.8, 6.25=>6.3).
   G-CHECKS FAIL или любое измерение<1 или score<8 => return_to_stage_1; иначе pass.
   На r4 не-pass => escalate_user. Pass 8.0–8.4 всё равно записывай pass: второго приёмщика маршрутизирует запускающий.
5. При не-pass verdict_reason >=10 символов. rework_fix_list только S/Q/P ниже 2 и FAIL G-CHECKS;
   покрыть все измерения<2 (кроме фиксированного C), если score<8, и FAIL-гейт. Каждая fix — одна английская строка
   для CORRECTION, frame из frames.files, tool="Codex 1a". При pass rework_fix_list=[]; замечания в known_issues.
   Не назначай Tripo, Blender, 1b или 1c в этой 1a приёмке.

Константы карточки (остальные поля строго по output-concept.schema.json):
schema="unmatched.concept-acceptance/1", kind="concept", clip=null, asset_id="ASSET-RAPHAEL-001", date="2026-10-13",
cycle="r1", previous_card=null, accepted_object=[{"path": "art/imagegen/concept-raphael-codex/design/raphael-front.png", "sha256": "53ae19762bc777d34a0b4e4985ce465ba627ec61d5e469ebd2be30d92ec1ddd7"}],
frames={"dir":"art/imagegen/concept-raphael-codex/design","files":["raphael-front.png","checks-report.json"]},
reports=["art/imagegen/concept-raphael-codex/design/checks-report.json", "art/imagegen/concept-raphael-codex/generation-records.json", "art/imagegen/concept-raphael-codex/verification.json"],
gates={"G-CHECKS":{"status":"PASS или FAIL по отчёту","source":"art/imagegen/concept-raphael-codex/design/checks-report.json","note":"файл#ключ=значение","source_defect":null}},
acceptor={"profile":"Sol 6.1 xhigh","session_id":"codex:pending"},
executor_session_id="codex:01a1347b-2867-7140-8e26-fb0695ade613", decided_by="delegated (ВР-реестр 2026-10-06)".
status_note при pass="художественно принято, по делегированию (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)";
иначе пустая строка. verdict_reason при pass=null. rationale.frames и known_issues.frame — имена из frames.files.
Верни только JSON карточки, все поля строгой схемы, без текста вокруг.
