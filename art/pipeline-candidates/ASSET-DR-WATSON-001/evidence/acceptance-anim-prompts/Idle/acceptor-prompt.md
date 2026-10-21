# Приёмка клипа AM_DrWatson_Idle, цикл {{CYCLE}} (шаг 7a.2)

<!-- ЗАГОТОВКА этапа 6 (2026-10-21, волна A мини-пачки 2026-10-20), не запускалась; собрана скриптом
C:/tmp/dr-watson-stage6/gen_prompts.py по спеке и отчётам прогона. На шаге 7a.2 её заполняет
tools/tripo-pipeline/ue7a/prep_acceptance.py (--asset-dir art/pipeline-candidates/ASSET-DR-WATSON-001 --key DrWatson --run art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2 --spec art/pipeline-candidates/ASSET-DR-WATSON-001/build-profiles/dr-watson-h2anim.json --cycle r1):
{{E}}, {{DATE}}, {{CYCLE}}, {{PREVIOUS_CARD_JSON}}, {{FRAMES_FILES_JSON}}, список пределов из
evidence/acceptance-anim-prompts/known-limits.md, заметка о меше-носителе UE-кадров; sha256 в accepted_object сверяются с
файлами (новый прогон модели — --refresh-sha или пересборка заготовок тем же скриптом). Профиль приёмщика —
«Opus xhigh» (первый), второй в полосе 8,0–8,4 — «Opus high» (SKILL.md §0, §4). -->

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — приёмщик. Ты НЕ исполнитель: ничего не правишь, не запускаешь Blender, Unreal, скрипты и validate_card.py, не
пишешь файлы. Твоя единственная выдача — JSON-карточка kind anim по схеме
tools/art/acceptance/asset-acceptance-2.schema.json; файл card.json записывает и проверяет запускающий.
   Текстовые файлы читай так, чтобы кириллица дошла целой. В песочнице codex PowerShell работает в Constrained
   Language Mode и пишет вывод в OEM-кодировке: `Get-Content -Encoding UTF8` даёт кракозябры, смена
   `[Console]::OutputEncoding` запрещена, `rg` нет. Рабочие способы (проверено пробой 2026-10-13): читай КАЖДЫЙ
   текстовый файл (рубрику, JSON-отчёты, предыдущую карточку) командой
   `Get-Content <файл> -Raw -Encoding OEM` (байты UTF-8 проходят без перекодировки и читаются верно) или
   `cmd /c type <файл>`. Кодовые точки (`[int[]][char[]]`) не нужны. Если кириллица рубрики всё равно пришла
   кракозябрами — это сбой окружения: не оценивай по догадкам, верни карточку, где verdict_reason начинается со слов
   «СБОЙ ОКРУЖЕНИЯ: кириллица не читается».
   Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/animation-vfx-sfx.md §2.1,
   §2.3, §10 (гейты §10.2, кадры §10.3, измерения и якоря §10.4, вердикт §10.5); механика формулы, вердикта и полей
   карточки — .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md §6 и §7 (где они расходятся с §10 —
   прав §10 и схема). Рубрика — ТОЛЬКО эти два файла: SKILL.md и другие файлы скилла (.agents/skills/**, кроме
   animation-vfx-sfx.md и acceptance-and-blender.md) не открывай и не учитывай.

## Вход
- Кадры: {{E}}/Idle/frames/ — открой КАЖДЫЙ файл из списка {{FRAMES_FILES_JSON}} в полном размере (1:1):
  Blender-лист `DrWatson-Idle-blender-sheet.jpg` (кадры key_frames [0, 14, 28, 42], виды front / left / q34, кости поверх),
  крупные планы Blender (art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/preview/closeups-blender/: DrWatson-Idle-f28-q34.jpg, DrWatson-Idle-f28-q34b.jpg, DrWatson-Idle-f28-q34bl.jpg, DrWatson-Idle-f28-q34l.jpg, DrWatson-Idle-f42-back.jpg, DrWatson-Idle-f42-q34b.jpg, DrWatson-Idle-f42-q34r.jpg, DrWatson-Idle-f42-topb.jpg, DrWatson-Idle-seam-f56-f00-front.jpg, DrWatson-Idle-seam-f56-f00-q34.jpg; камера каждого кадра — в
  DrWatson-Idle-closeups.json). UE-кадры `DrWatson-Idle-fNN-{front,q34}-ue-editor.jpg`, лист
  `DrWatson-H2Anim-ue-sheet.jpg`. Другие файлы каталога {{E}} (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_DrWatson_Idle, роль idle (петля), 56 к. при 24 fps (2.333 с); кадр 0 = rest, последний кадр = rest (петля).
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-DR-WATSON-001/build-profiles/dr-watson-h2anim.json): «спокойная стойка отставного военного врача: ровное дыхание (грудь и плечи поднимаются вместе на вдохе), голова медленно и коротко обводит поле, взгляд вперёд; револьвер поднят у плеча стволом вверх, на вдохе чуть поднимается (локоть сгибается на своём шарнире на 4,5°), револьвер жёстко в кулаке; саквояж в левой руке висит у бока и на вдохе чуть отходит наружу — не входит в полу пальто; таз едва поворачивается (±1°) без сдвига, стопы на месте; пальто идёт с корпусом».
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_DrWatson_Idle.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/contact-Idle.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись WAT-Idle, G-MANIFEST), art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/author-Idle.json (ik_log), art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/grip-Idle.json (машинный замер по FBX клипа): поворот weapon.R (револьвера) в кулаке ≤ 0.0° на всех кадрах, излом правого запястья ≤ 0.0°, локоть правой руки 91.3–95.8°, уход плоскости сгиба локтя ≤ 0.1°, колени не ниже 173.8°, пересечений револьвера и саквояжа с телом 0.
- Референс движения: образец библиотеки D-11 — спека Medusa (art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json, clips.Idle: дыхание корпусом, голова обводит поле, 56 к.) и art/animation-refs/ASSET-MEDUSA-001/MED-Idle/contact-sheet-2fps.png; зеркально на правую руку. Лук и покачивание лука образца заменены поднятым у плеча револьвером, саквояж в левой руке — у бока; это ориентир тайминга и поз, не цель. Своего видео-референса у Ватсона нет (ДС-6, траты 0).
- Характер героя: лист концепта art/imagegen/concept-dr-watson-codex/dr-watson-front.png (и кадры модели
  art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/<цикл принятой модели>/frames/sheet.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png и art/imagegen/hero-quality-v1/merlin/. Заявка:
  Dr. Watson — помощник Sherlock Holmes, дальний бой (выстрел из револьвера, HIT_TYPE ARROW), крепкий джентльмен с
  усами в котелке, длинное коричневое пальто поверх жилета, револьвер в ПРАВОЙ руке (оружие — кость weapon.R),
  докторский саквояж в левой (жёстко на hand.L); карточка задачи AN-164
  (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale и known_issues, не в rework_fix_list и не
  ниже 1,0, если кадр не показывает видимый разрыв, дыру или отрыв части; один список на все 4 клипа):
{{KNOWN_LIMITS}}
- Предыдущая карточка: {{PREVIOUS_CARD_JSON}} (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи WAT-Idle в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора; D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: R — живое ровное дыхание и короткий взгляд по полю (спокойный отставной военный врач), без мёртвой статики; C — стопы на месте при повороте таза; L — шов петли (пара seam fNN/f00) невидим; D — револьвер в кулаке не проворачивается, саквояж не уходит в полу пальто, кромки рукавов у пройм целы. В rationale назови кадры и видимый признак; frames — имена файлов из
   frames.files.
3. score = round((R + C + D + L) / 8 × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт по §10.5: любой гейт FAIL, любое измерение < 1,0 или score < 8,0 → rework_blender;
   иначе pass; на r3 любой не-pass → escalate_user. При любом вердикте, кроме pass, заполни verdict_reason
   (≥ 10 символов): какое правило сработало.
4. rework_fix_list — при pass []. При rework_blender список покрывает каждый FAIL-гейт и каждое измерение < 1,0;
   пункт строго {"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и на каком кадре
   клипа>", "tool": "<ключ спеки clips.Idle: keys | waves | key_frames | ik_feet | hand_follow | template |
   amplitude_scale; или «этап 5 модели: <ключ профиля bake или стадия>» для дефекта модели (§10.5); для G-MANIFEST —
   «этап 7: h2anim_ue.py import + clip_manifest.py build»>"}, других ключей нет. Длину клипа, fps и кадр контакта не
   предлагать менять (§10.6).
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до этапа 7 (лист K1/K2):
   [{"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-DR-WATSON-001", clip "Idle",
   date "{{DATE}}", cycle "{{CYCLE}}", previous_card {{PREVIOUS_CARD_JSON}},
   accepted_object [{"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/export/AM_DrWatson_Idle.fbx", "sha256": "48fd85e9cdc096f8e4c02dbbd6977cfc9cbbf4c33dec26f8719ee5ecb79fa5b7"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/build-profiles/dr-watson-h2anim.json", "sha256": "2fc8549daf37c6becd2aeeb1cb137437bfd2d25ae49e3cfaf7968209d7231194"}],
   frames {"dir": "{{E}}/Idle/frames", "files": {{FRAMES_FILES_JSON}}},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_DrWatson_Idle.validation.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/contact-Idle.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/grip-Idle.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Opus xhigh", "session_id": "<сессия приёмщика>"},
   executor_session_id "claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe/agent:stage6-watson",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
