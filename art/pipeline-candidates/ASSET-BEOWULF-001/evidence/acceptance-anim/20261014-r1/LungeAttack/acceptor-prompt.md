# Приёмка клипа AM_Beowulf_LungeAttack, цикл r1 (шаг 7a.2)

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
- Кадры: art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance-anim/20261014-r1/LungeAttack/frames/ — открой КАЖДЫЙ файл из списка ["Beowulf-LungeAttack-blender-sheet.jpg", "Beowulf-LungeAttack-f04-front.jpg", "Beowulf-LungeAttack-f04-q34.jpg", "Beowulf-LungeAttack-f04-q34b.jpg", "Beowulf-LungeAttack-f07-back.jpg", "Beowulf-LungeAttack-f07-front.jpg", "Beowulf-LungeAttack-f07-left.jpg", "Beowulf-LungeAttack-f07-q34.jpg", "Beowulf-LungeAttack-f07-q34b.jpg", "Beowulf-LungeAttack-f07-q34l.jpg", "Beowulf-LungeAttack-f07-q34r.jpg", "Beowulf-LungeAttack-f09-q34r.jpg", "Beowulf-LungeAttack-f10-front.jpg", "Beowulf-LungeAttack-f00-front-ue-editor.jpg", "Beowulf-LungeAttack-f00-q34-ue-editor.jpg", "Beowulf-LungeAttack-f02-front-ue-editor.jpg", "Beowulf-LungeAttack-f02-q34-ue-editor.jpg", "Beowulf-LungeAttack-f04-front-ue-editor.jpg", "Beowulf-LungeAttack-f04-q34-ue-editor.jpg", "Beowulf-LungeAttack-f07-front-ue-editor.jpg", "Beowulf-LungeAttack-f07-q34-ue-editor.jpg", "Beowulf-LungeAttack-f09-front-ue-editor.jpg", "Beowulf-LungeAttack-f09-q34-ue-editor.jpg", "Beowulf-LungeAttack-f12-front-ue-editor.jpg", "Beowulf-LungeAttack-f12-q34-ue-editor.jpg", "Beowulf-LungeAttack-f14-front-ue-editor.jpg", "Beowulf-LungeAttack-f14-q34-ue-editor.jpg", "Beowulf-LungeAttack-f00-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f00-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f02-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f02-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f04-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f04-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f07-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f07-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f09-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f09-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f12-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f12-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f14-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f14-q34-closeup-ue-editor.jpg", "Beowulf-H2Anim-ue-sheet.jpg"] в полном размере (1:1):
  Blender-лист `Beowulf-LungeAttack-blender-sheet.jpg` (кадры key_frames [0, 2, 4, 7, 9, 12, 14], виды front / left / q34, кости поверх),
  крупные планы Blender (art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/preview/closeups-blender/: Beowulf-LungeAttack-f04-front.jpg, Beowulf-LungeAttack-f04-q34.jpg, Beowulf-LungeAttack-f04-q34b.jpg, Beowulf-LungeAttack-f07-back.jpg, Beowulf-LungeAttack-f07-front.jpg, Beowulf-LungeAttack-f07-left.jpg, Beowulf-LungeAttack-f07-q34.jpg, Beowulf-LungeAttack-f07-q34b.jpg, Beowulf-LungeAttack-f07-q34l.jpg, Beowulf-LungeAttack-f07-q34r.jpg, Beowulf-LungeAttack-f09-q34r.jpg, Beowulf-LungeAttack-f10-front.jpg; камера каждого кадра — в
  Beowulf-LungeAttack-closeups.json). UE-кадры `Beowulf-LungeAttack-fNN-{front,q34}-ue-editor.jpg`, крупный план кадров вокруг контакта `Beowulf-LungeAttack-fNN-*-closeup-ue-editor.jpg`, лист
  `Beowulf-H2Anim-ue-sheet.jpg`. Другие файлы каталога art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance-anim/20261014-r1 (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_Beowulf_LungeAttack, роль oneshot, 14 к. при 24 fps (0.583 с); кадр 0 = rest, последний кадр = rest.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2anim.json): «замах: кисть с мечом у правого бока (hand_follow anchor к spine, IK, локоть вниз), корпус разворачивается вправо и откидывается, клинок вверх-назад над правым плечом (к. 2–4); рубящий удар по диагонали сверху справа вниз-влево поперёк корпуса: плечо поднято вбок, локоть ~130°, кисть перед правой стороной груди, клинок вперёд-влево-вниз (к. 7 = Contact), корпус наклоняется вперёд и доворачивается влево, таз вперёд; проводка — клинок уходит дальше влево-вниз (к. 9), возврат в rest (к. 12–14); меч всё время жёстко в кулаке (кость weapon.R без ключей, направление клинка задаёт поворот кисти aim hand.R); левая рука со щитом уравновешивает, отведена наружу (к. 7–9), щит не входит в корпус; стопы на месте, мантия и подол идут с тазом».
- UE-кадры (`*-ue-editor.jpg`, лист `Beowulf-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` на меше-носителе `/Game/PipelineCandidates/Beowulf/Rig/SK_Beowulf` (геометрия H2 без look-dev материалов, поэтому фигура серая — так снимаются все герои библиотеки D-11) на подставке `SM_Beowulf_H2LD_Base`; цвет и материал в этой приёмке не оцениваются. Свет — закреплённый cobble-probe rev 5 (`--light-pinned art/pipeline-candidates/ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), High, редактор: это диагностические кадры, не K1/K2. Крупные планы Blender лежат и в art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance-anim/20261014-r1/<клип>/frames/ (копии файлов из preview/closeups-blender/).
- Контакт: LUNGE_CONTACT_FRAME = 7 (к.7 = 292 мс при 24 fps); C — удар точно в к.7 и с весом.
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_Beowulf_LungeAttack.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/contact-LungeAttack.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись BEO-LungeAttack, G-MANIFEST), art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/author-LungeAttack.json (ik_log), art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/grip-LungeAttack.json (машинный замер по FBX клипа): поворот weapon.R в кулаке ≤ 0.0° на всех кадрах, щит относительно предплечья ≤ 0.000 см, излом правого запястья ≤ 23.9°, локоть правой руки 112.2–131.1°, колени не ниже 158.5°, пересечений меча с телом 0, щита с телом 0; art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/rider-gap.json (рукоять щита к кисти во всех кадрах).
- WARN контактов: skin_stretch — рёбра растяжения только в закрытых местах (видимых рваных рёбер 0; к.7,8,9; области foot.L|leg_lower.L).
- Референс движения: образец библиотеки D-11 — спека Angel r2 (art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2anim-r2.json, все 4 клипа приняты на 7a.2) по клипам меча King Arthur; art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-LungeAttack/contact-sheet-2fps.png. Своего видео-референса у Beowulf нет (ДС-6: меч в правой руке — стандартное движение); это ориентир тайминга и поз, не цель.
- Характер героя: лист концепта art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames/sheet.png (и art/imagegen/concept-beowulf-codex/beowulf-front.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Beowulf — герой ближнего боя, длинный меч
  в ПРАВОЙ руке, круглый деревянный щит на ЛЕВОЙ руке, меховая мантия, кольчужная туника, железный шлем, борода с
  косами; карточка задачи AN-146 (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale и known_issues, не в rework_fix_list и не
  ниже 1,0, если кадр не показывает видимый разрыв, дыру или отрыв части; один список на все 4 клипа):
- Щит без своей кости: щит и умбон 100 % на arm_lower.L (П3-2), кисть hand.L ключей не имеет, поэтому хват ручки щита не смещается (rider_gap: зазор 0,00 мм, проникновение 0,12 мм в rest и во всех 4 клипах). Между щитом и предплечьем постоянный зазор 5,6 мм: щит держит кисть, ремня на предплечье у модели нет (этап 3); в клипах он не меняется.
- Меч из двух частей Tripo: клинок, гарда и рукоять над кулаком — меш оружия; низ рукояти и навершие — часть меша тела, 100 % на weapon.R (П3-1). Обе жёстко на кости оружия.
- Ноги в rest прямые (таз–лодыжка 16,328 см при длине цепи 16,329 см): любое смещение таза идёт с опусканием 0,03–0,4 см, отсюда небольшой сгиб колен в выпаде, отдаче и смерти (колено не ниже 154°, подъём бедра не больше 16°).
- Скрытое растяжение кожи у щиколоток внутри сапог (skin_stretch WARN: LungeAttack к.6–10, DeathSettle к.11–21, видимых рваных рёбер 0) — закрыто сапогом со всех 24 направлений обзора. В DeathSettle ещё натяжение на сгибе правого локтя при почти прямой руке (152°): 4 ребра > 3× rest, WARN, видимых рваных рёбер 0.
- Idle и HitReact: меч слегка покачивается в кулаке волной и ключом образца (до 2,5° в Idle и 8° в HitReact); в LungeAttack и DeathSettle меч в кулаке неподвижен (0°).
- Предыдущая карточка: null (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи BEO-LungeAttack в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора; D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: C — рубящий удар точно в к.7 и с весом (корпус доворачивается влево и наклоняется вперёд, таз вперёд, клинок вперёд-вниз-влево), стопы на месте; D — хват меча (меч не проворачивается в кулаке), плечо и локоть правой руки на замахе (к.4) и контакте (к.7–9) на крупном плане, кромка рукава и мантии сзади-справа (-q34b); щит не входит в корпус. В rationale назови кадры и видимый признак; frames — имена файлов из
   frames.files.
3. score = round((R + C + D + L) / 8 × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт по §10.5: любой гейт FAIL, любое измерение < 1,0 или score < 8,0 → rework_blender;
   иначе pass; на r3 любой не-pass → escalate_user. При любом вердикте, кроме pass, заполни verdict_reason
   (≥ 10 символов): какое правило сработало.
4. rework_fix_list — при pass []. При rework_blender список покрывает каждый FAIL-гейт и каждое измерение < 1,0;
   пункт строго {"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и на каком кадре
   клипа>", "tool": "<ключ спеки clips.LungeAttack: keys | waves | key_frames | ik_feet | hand_follow | template |
   amplitude_scale; или «этап 5 модели: <ключ профиля bake или стадия>» для дефекта модели (§10.5); для G-MANIFEST —
   «этап 7: h2anim_ue.py import + clip_manifest.py build»>"}, других ключей нет. Длину клипа, fps и кадр контакта не
   предлагать менять (§10.6).
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до этапа 7 (лист K1/K2):
   [{"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-BEOWULF-001", clip "LungeAttack",
   date "2026-10-14", cycle "r1", previous_card null,
   accepted_object [{"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/export/AM_Beowulf_LungeAttack.fbx", "sha256": "01e689d072cb55bb529eb4bfc361b312f01ae0f0706d6368c15b62baebf91013"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2anim.json", "sha256": "d3227542f85e141749221a977578acade57ab756c9df5f651c39b489f70b9660"}],
   frames {"dir": "art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance-anim/20261014-r1/LungeAttack/frames", "files": ["Beowulf-LungeAttack-blender-sheet.jpg", "Beowulf-LungeAttack-f04-front.jpg", "Beowulf-LungeAttack-f04-q34.jpg", "Beowulf-LungeAttack-f04-q34b.jpg", "Beowulf-LungeAttack-f07-back.jpg", "Beowulf-LungeAttack-f07-front.jpg", "Beowulf-LungeAttack-f07-left.jpg", "Beowulf-LungeAttack-f07-q34.jpg", "Beowulf-LungeAttack-f07-q34b.jpg", "Beowulf-LungeAttack-f07-q34l.jpg", "Beowulf-LungeAttack-f07-q34r.jpg", "Beowulf-LungeAttack-f09-q34r.jpg", "Beowulf-LungeAttack-f10-front.jpg", "Beowulf-LungeAttack-f00-front-ue-editor.jpg", "Beowulf-LungeAttack-f00-q34-ue-editor.jpg", "Beowulf-LungeAttack-f02-front-ue-editor.jpg", "Beowulf-LungeAttack-f02-q34-ue-editor.jpg", "Beowulf-LungeAttack-f04-front-ue-editor.jpg", "Beowulf-LungeAttack-f04-q34-ue-editor.jpg", "Beowulf-LungeAttack-f07-front-ue-editor.jpg", "Beowulf-LungeAttack-f07-q34-ue-editor.jpg", "Beowulf-LungeAttack-f09-front-ue-editor.jpg", "Beowulf-LungeAttack-f09-q34-ue-editor.jpg", "Beowulf-LungeAttack-f12-front-ue-editor.jpg", "Beowulf-LungeAttack-f12-q34-ue-editor.jpg", "Beowulf-LungeAttack-f14-front-ue-editor.jpg", "Beowulf-LungeAttack-f14-q34-ue-editor.jpg", "Beowulf-LungeAttack-f00-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f00-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f02-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f02-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f04-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f04-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f07-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f07-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f09-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f09-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f12-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f12-q34-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f14-front-closeup-ue-editor.jpg", "Beowulf-LungeAttack-f14-q34-closeup-ue-editor.jpg", "Beowulf-H2Anim-ue-sheet.jpg"]},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_Beowulf_LungeAttack.validation.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/contact-LungeAttack.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/grip-LungeAttack.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage6-beowulf",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
