# Приёмка клипа AM_BruceLee_Idle, цикл {{CYCLE}} (шаг 7a.2)

<!-- ЗАГОТОВКА этапа 6 (2026-10-21, мини-пачка 2026-10-20, волна A), не запускалась. На шаге 7a.2 её заполняет
tools/tripo-pipeline/ue7a/prep_acceptance.py (--asset-dir art/pipeline-candidates/ASSET-BRUCE-LEE-001 --key BruceLee --run art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim --spec art/pipeline-candidates/ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2anim.json --cycle r1):
{{E}}, {{DATE}}, {{CYCLE}}, {{PREVIOUS_CARD_JSON}}, {{FRAMES_FILES_JSON}}, список пределов из
evidence/acceptance-anim-prompts/known-limits.md, заметка о меше-носителе UE-кадров; sha256 в accepted_object сверяются с
файлами (клип перепечён — --refresh-sha). Профиль и session_id приёмщика переписывает
tools/tripo-pipeline/ue7a/run_clip_acceptors.py («Opus xhigh», второй — «Opus high»). -->

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
  Blender-лист `BruceLee-Idle-blender-sheet.jpg` (кадры key_frames [0, 10, 20, 30, 45, 50], виды front / left / q34, кости поверх),
  крупные планы Blender (art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/preview/closeups-blender/: BruceLee-Idle-f10-front-b.jpg, BruceLee-Idle-f10-front.jpg, BruceLee-Idle-f10-q34.jpg, BruceLee-Idle-f13-back.jpg, BruceLee-Idle-f13-q34b.jpg, BruceLee-Idle-f13-topb.jpg, BruceLee-Idle-f29-q34bl.jpg, BruceLee-Idle-f30-q34.jpg, BruceLee-Idle-f30-q34b.jpg, BruceLee-Idle-f30-q34r.jpg; камера каждого кадра — в
  BruceLee-Idle-closeups.json), пара шва цикла `BruceLee-Idle-seam-f60-f00-{front,q34}.jpg` (слева последний кадр, справа кадр 0). UE-кадры `BruceLee-Idle-fNN-{front,q34}-ue-editor.jpg`, лист
  `BruceLee-H2Anim-ue-sheet.jpg`. Другие файлы каталога {{E}} (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_BruceLee_Idle, роль idle (петля), 60 к. при 24 fps (2.500 с); кадр 0 = rest, последний кадр = rest.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2anim.json): «боевая стойка Jeet Kune Do (rest миниатюры): лёгкое пружинящее покачивание на месте — три мягких «пружины» за цикл (таз опускается на 0,4 см к. 10, 30, 50 и возвращается к rest к. 0, 20, 40, колени чуть сгибаются, стопы стоят), вес чуть переходит к левой ноге (к. 10) и к правой (к. 30); корпус медленно «качает маятник» (поворот ±2,5°) и дышит; передняя правая кисть-«коготь» описывает малые круги перед корпусом (финты, 2 круга за цикл), задняя левая — в противофазе меньше; кисти чуть сжимаются; голова держит цель (противоповорот), взгляд вперёд».
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_BruceLee_Idle.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/contact-Idle.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись BRUC-Idle, G-MANIFEST), art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/author-Idle.json (журнал автора; ноги — aim-ключи каждого кадра, IK стоп инструмента выключен, ik_unreached_frames пуст).
  Оружия нет: grip-отчёта нет.
- WARN контактов: нет (все проверки контактов PASS или info).
- Референс движения: образец библиотеки D-11 — спека Achilles r3 (art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim-r3.json, clips.Idle: дыхание и перенос веса с опусканием таза на прямых ногах) по клипу King Arthur; art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-Idle/contact-sheet-2fps.png. Пружина стойки Jeet Kune Do — авторский слой поверх образца. Своего видео-референса у Bruce Lee нет (ДС-6: паттерн библиотеки); это ориентир
  тайминга и поз, не цель.
- Характер героя: лист концепта art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r2/frames/sheet.png (и
  art/imagegen/concept-bruce-lee-codex/bruce-lee-front.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Bruce Lee — герой ближнего боя без оружия, правосторонняя стойка Jeet Kune Do: обе кисти подняты «когтями» перед грудью, правая (передняя) впереди; жёлтый комбинезон с чёрными лампасами, чёрные туфли; карточка задачи AN-156
  (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale и known_issues, не в rework_fix_list и не
  ниже 1,0, если кадр не показывает видимый разрыв, дыру или отрыв части; один список на все 4 клипа):
{{KNOWN_LIMITS}}
- Предыдущая карточка: {{PREVIOUS_CARD_JSON}} (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи BRUC-Idle в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора; D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: C — стопы не едут при пружине таза, шов петли (пара seam f60/f00) без скачка; L — шов Idle невидим, пружина и дыхание живые, не механические; R — собранная боевая стойка Брюса Ли (обе кисти-«когти» перед грудью, малые круги передней кисти, голова держит цель), спиной к камере нет; D — колени и пах на низах пружины (к.10, 30, 50). В rationale назови кадры и видимый признак; frames — имена файлов из
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
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-BRUCE-LEE-001", clip "Idle",
   date "{{DATE}}", cycle "{{CYCLE}}", previous_card {{PREVIOUS_CARD_JSON}},
   accepted_object [{"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/export/AM_BruceLee_Idle.fbx", "sha256": "0ecc7bf681db6ce7b19230cb533ee5cfb8f0f6c5b9ff1e601e0a2297ee4e262f"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2anim.json", "sha256": "f569f090b7d07a782756408e764ff97a03cb50e75c665a8661851985d35997f1"}],
   frames {"dir": "{{E}}/Idle/frames", "files": {{FRAMES_FILES_JSON}}},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_BruceLee_Idle.validation.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/contact-Idle.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/author-Idle.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Opus xhigh", "session_id": "workflow:pending"},
   executor_session_id "claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe/agent:stage6-bruce",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
