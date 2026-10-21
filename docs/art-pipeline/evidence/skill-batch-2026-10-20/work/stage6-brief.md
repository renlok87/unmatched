# Бриф этапа 6 (анимация) — волна A мини-пачки 2026-10-20

Исполнитель — субагент оркестратора (`claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe`), по одному на фигуру.

## Полномочия (дословно)

- Пользователь 2026-10-21: «Хорошо, использую Opus High вместо Z-код для приемщика. Вот, и продолжай без меня, делай
  все сам. Касательно сетов тоже и 3D модели героев.»
- Главная сессия: «Also overlap wherever you can: run stages 4–6 of different figures concurrently, and do not wait for a
  whole wave between stages.»
- Траты: в этом этапе без трат. SYNTX, stiva.ai, Tripo не вызывать. Пароли не вводить.

## Что сделать

Этап 6 скилла `.agents/skills/3d-model-pipeline/SKILL.md` (§6, «Этап 6») по `references/animation-vfx-sfx.md`
§5–§9, без приёмки клипов (она в 7a.2):

1. Источник движения — паттерн библиотеки по классу оружия (§6.1, ДС-6). Выбор и причину записать в `MOTION_SOURCE`
   заявки.
2. Спека `art/pipeline-candidates/<ASSET_ID>/build-profiles/<content-key>-h2anim.json` (§6.2). Четыре клипа D-11:
   Idle, LungeAttack, HitReact, DeathSettle. Длины и кадр контакта — из заявки: `IDLE_SECONDS`,
   `LUNGE_CONTACT_FRAME`.
3. Прогон `python tools/tripo-pipeline/anim/h2anim_run.py <spec>` → код 0. Внутри идут validate и contact.
4. Затем:
   - `grip_check.py`, если у фигуры есть оружие;
   - `clip_closeups.py` с парой шва Idle (§6.3, §10.3);
   - осмотр каждого листа и крупного плана глазами.
5. Заготовки промптов приёмки клипов — `evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md` по шаблону §10
   (с блоком OEM).
6. SFX и FX — слоты по §8–§9 и `docs/game-design/audio/02-audio-design.md` §8.1. `HIT_TYPE` берётся из заявки. Новые
   звуки в этом прогоне не генерировать: что нужно, записать в `STAGE6` заявки как открытое.

## Общие файлы — не трогать (один шаг регистрации у оркестратора)

Не править:
- `tools/tripo-pipeline/anim/clip_manifest.py` (`CHARS`, `H2ANIM`);
- `docs/art-pipeline/animation-library/clip-manifest.schema.json`;
- `docs/game-design/visual/06-tasks/anim.csv`;
- `tools/art/anim/clip_review_sheet.py` (`HEROES`).

Вместо этого написать готовые строки в `<run>/REGISTRATION.md`:
- строки `CHARS` / `H2ANIM`;
- значение enum;
- четыре строки CSV карточек с выданными номерами AN по образцу AN-145…148 Beowulf;
- строку `Hero(...)`.

Оркестратор вносит их одним шагом и запускает `clip_manifest.py build`.

Номера AN выдал оркестратор:

| Фигура | Idle | LungeAttack | HitReact | DeathSettle |
|---|---|---|---|---|
| Bruce Lee | AN-156 | AN-157 | AN-158 | AN-159 |
| Sherlock Holmes | AN-160 | AN-161 | AN-162 | AN-163 |
| Dr. Watson | AN-164 | AN-165 | AN-166 | AN-167 |

## Правила

- Blender на машине — не больше 2 процессов. Перед каждым запуском Blender считать `blender.exe` в `tasklist`. При 2
  ждать: Monitor с until-циклом или короткий цикл проверки. Свой процесс останавливать в конце.
- Писать только в репозиторий (папки своей фигуры и свой run) и в `C:/tmp/<своя папка>`. Никаких корневых папок вроде
  `C:/pb`, в том числе для путей вывода Blender.
- Не запускать команд, которым нужен запрос разрешения.
- Без git: коммитит оркестратор.
- Код инструментов не править. Если без правки не обойтись, остановиться и описать предложение в отчёте.
- Модель не трогать. Дефект модели, вскрытый клипом, — в отчёт, это поздний фикс (§5 п.4).

## Отчёт (последнее сообщение)

- спека, run, источник движения;
- по каждому клипу: длина, кадр контакта, результаты validate / contact / grip, что видно на крупных планах;
- открытое;
- путь к `REGISTRATION.md`;
- блок `STAGE6` в заявке (§7.2).
