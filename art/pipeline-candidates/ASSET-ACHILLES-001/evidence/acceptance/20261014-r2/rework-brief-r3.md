# Доработка ASSET-ACHILLES-001: этап 7a → новый run r3 (этап 5 скилла 3d-model-pipeline, последний цикл модели)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Пилот (2026-10-13, дословно): «Сгенерировать модели можно все Но сначала чтобы полностью обкатать скилл и
итерационно его улучшить, можно это сделать на небольшой выборке». Траты: нет — кредиты Tripo/SYNTX, Unreal и упаковка
на этом шаге запрещены.

Ты — исполнитель доработки «Opus xhigh». Работаешь лично, не делегируешь, свою работу не принимаешь.
Норма — docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md (§4.2 «Новый герой», §4.4 «Сдача этапа 3»); правила этапа 5 —
.agents/skills/3d-model-pipeline/references/acceptance-and-blender.md §9. Решения пилота —
docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md. Находки — docs/art-pipeline/evidence/
skill-pilot-2026-10-13/NOTES.md (F104, F129, F141, F143, F144).

## Вход
- Модель принята r2 (8.8): art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/card.json.
- Профили r2: build-profiles/achilles-h2-{bake-h2,lookdev,lookdev-teamaccent}-r2.json; прогоны 20261014-h2-bake-r2,
  20261014-h2-lookdev-r2 (только чтение).
- Этап 7a (03ca3781): карточка клипа DeathSettle r1 evidence/acceptance-anim/20261014-r1/DeathSettle/card.json
  (7.5 rework_blender, D=0) и кадры UE 20261014-h2anim/preview/ue (f21-q34b, f21-right); отчёт подставки на просвет
  evidence/stage7a-20261014/ (base-seethrough*.json); look-dev UE 20261014-h2ld-ldc-ue/review/r3 (кольцо команды на
  подставке).

## Правки — только эти пункты
1. D · DeathSettle f21 q34b/right (и LungeAttack f4–10): рваная кромка проймы плаща за правой подмышкой открывается,
   когда правая рука уходит вперёд. Закрыть средствами профиля (closure: крышка/мост проймы; rig: веса кромки плаща к
   spine/плечу; cloth_shell, если это одинарный лист — проверить толщину лучом, HANDBOOK §4.2). Проверка — Blender
   close-ups тех же кадров клипов (переавторинг по п.4) и seams.
2. G · подставка на просвет: 0.98 uu² при пороге 0.1 — 8 открытых петель в верхе подставки под сандалиями и пяткой
   копья. Закрыть крышками отверстий подставки (closure base holes). Проверка — base_seethrough.py по HANDBOOK §8 на
   FBX (если инструмент требует UE — замер оставить этапу 7, но петли закрыть и показать инвентарь close).
3. T · кольцо цвета команды на двухъярусной подставке Tripo выходит рваными пятнами (white/P1/P2) —
   textures.team_mask.base_band и маска BaseMarker: подобрать полосу по геометрии подставки (одна ровная полоса по
   нижнему ярусу), чтобы кольцо было сплошным. Если чистое кольцо профилем недостижимо — «не закрыто: нужна опция …»
   с кадром.

## Границы
- Ничего вне списка. Силуэт, пропорции, палитру, якоря и новые детали не трогать (§9.4). Тон (t_cap 2.0) не ронять.
- Новые профили …-r3.json с history.previous_profiles; новые run-каталоги 20261014-h2-bake-r3 / 20261014-h2-lookdev-r3;
  прежние прогоны и закоммиченные профили не менять.
- Только headless run_h2_bake.py, по одной стадии. Перед первым запуском — `python -m pytest
  tools/tripo-pipeline/blender/h2_bake/tests -q` (другой агент добавляет опцию prepare.part_offsets_m; должна быть
  выключена по умолчанию — если тесты красные, стоп и отчёт).
- Общий код tools/** не менять (нужна опция → «не закрыто: нужна опция …»).
- Без кредитов, без Unreal, без коммитов, без git.

## Готово, если
- Все стадии r3 (bake, look-dev, TeamAccent) дали маркер и код 0, probes 7/7, seams, отчёты passed; детерминизм
  HANDBOOK §4.3; тон t_cap 2.0 (однострочник §4.4); capture_acceptance_set.py в C:/tmp/achilles-stage5-r3-check и
  осмотр close-* и pose-01…04 глазами.
- 4. Клипы: новый spec build-profiles/achilles-h2anim-r3.json (ключи без изменений, указывает на r3 bake), run
  20261014-h2anim-r3, h2anim_run.py (PYTHONIOENCODING=utf-8), validate_clip.py, clip_contact_check.py, свой
  grip-check; Blender close-ups DeathSettle f13–21 и LungeAttack f4–10 со спины/сбоку — кромка проймы закрыта.
  Строку H2ANIM Achilles в tools/tripo-pipeline/anim/clip_manifest.py перевести на r3-spec (разрешено оркестратором).
- Каждый пункт закрыт либо помечен «не закрыто: <причина>».

## Отчёт (последнее сообщение)
Пути профилей и прогонов; по пункту: ключ было → стало и подтверждающее число/кадр; тон; клипы; «не закрыто»;
SKILL FINDINGS. Баллы не ставь: повторная приёмка модели r3 и клипов — новые приёмщики.
