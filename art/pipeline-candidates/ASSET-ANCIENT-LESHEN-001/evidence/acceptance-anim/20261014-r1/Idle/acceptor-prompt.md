# Приёмка клипа AM_AncientLeshen_Idle, цикл r1 (этап 6 скилла 3d-model-pipeline)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — приёмщик. Ты НЕ исполнитель: ничего не правишь, не запускаешь Blender, Unreal, скрипты и validate_card.py, не
пишешь файлы. Твоя единственная выдача — JSON-карточка kind anim по схеме
tools/art/acceptance/asset-acceptance-2.schema.json; файл card.json записывает и проверяет запускающий.
Текстовые файлы читай так, чтобы кириллица дошла целой. В песочнице codex PowerShell работает в Constrained
Language Mode и пишет вывод в OEM-кодировке: `Get-Content -Encoding UTF8` даёт кракозябры, смена
`[Console]::OutputEncoding` запрещена, `rg` нет. Рабочие способы (проверено пробой 2026-10-13):
`Get-Content <файл> -Raw -Encoding OEM` (байты UTF-8 проходят без перекодировки и читаются верно) или
`cmd /c type <файл>`.
Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/animation-vfx-sfx.md §2.1,
§2.3, §10 (гейты §10.2, кадры §10.3, измерения и якоря §10.4, вердикт §10.5); механика формулы, вердикта и полей
карточки — .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md §6 и §7 (где они расходятся с §10 —
прав §10 и схема).

## Вход
- Кадры: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance-anim/20261014-r1/Idle/frames/ — открой КАЖДЫЙ файл из списка ["AncientLeshen-Idle-blender-sheet.jpg", "AncientLeshen-Idle-f14-front.jpg", "AncientLeshen-Idle-f14-q34.jpg", "AncientLeshen-Idle-f42-q34.jpg", "AncientLeshen-Idle-f00-front-ue-editor.jpg", "AncientLeshen-Idle-f00-q34-ue-editor.jpg", "AncientLeshen-Idle-f14-front-ue-editor.jpg", "AncientLeshen-Idle-f14-q34-ue-editor.jpg", "AncientLeshen-Idle-f28-front-ue-editor.jpg", "AncientLeshen-Idle-f28-q34-ue-editor.jpg", "AncientLeshen-Idle-f42-front-ue-editor.jpg", "AncientLeshen-Idle-f42-q34-ue-editor.jpg", "AncientLeshen-H2Anim-ue-sheet.jpg"] в полном размере (1:1):
  Blender-лист `AncientLeshen-Idle-blender-sheet.jpg` (кадры key_frames [0, 14, 28, 42], виды front / left / q34, кости
  поверх), крупные планы Blender (art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/preview/closeups-blender/: AncientLeshen-Idle-f14-q34.jpg, AncientLeshen-Idle-f42-q34.jpg (череп, рога и ворона на левом плече при повороте головы), AncientLeshen-Idle-f14-front.jpg (низ ствола и корни)), UE-кадры `AncientLeshen-Idle-fNN-{front,q34}-ue-editor.jpg`, лист
  `AncientLeshen-H2Anim-ue-sheet.jpg`. Другие файлы каталога art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance-anim/20261014-r1 (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_AncientLeshen_Idle, роль idle (петля), 56 к. при 24 fps (2.333 с); кадр 0 = rest, последний кадр = rest.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2anim.json):
  «древний лесной дух в покое: медленное тяжёлое дыхание ствола (грудь вперёд-назад, пик в середине цикла), ствол чуть кренится из стороны в сторону от таза при неподвижных корнях, череп с рогами медленно обводит поле (поворот ≤ 6°) и чуть кивает, длинные руки на вдохе слегка отходят от ствола, когти медленно сжимаются и разжимаются (двойная частота); вороны едут на плече и предплечьях».
- UE-кадры (`*-ue-editor.jpg`, лист `AncientLeshen-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` на меше-носителе `/Game/PipelineCandidates/AncientLeshen/Rig/SK_AncientLeshen` (геометрия H2 без look-dev материалов, поэтому фигура серая — так снимаются все герои библиотеки D-11) на подставке `SM_AncientLeshen_H2LD_Base`; цвет и материал в этой приёмке не оцениваются. Свет — закреплённый cobble-probe rev 5 (`--light-pinned ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), High, редактор: это диагностические кадры, не K1/K2. Верх рогов на части кадров обрезан рамкой камеры — это кадрирование, не дефект клипа.
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_AncientLeshen_Idle.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/contact-Idle.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись LESH-Idle, G-MANIFEST), art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/author-Idle.json (ik_log), art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/roots-planted.json (сдвиг корней).
- Референс движения: образец библиотеки D-11 — art/animation-refs/ASSET-MEDUSA-001/MED-Idle/contact-sheet-2fps.png (Medusa Idle той же длины 56 к.; тяжёлое дыхание — по Merlin Idle). Своего видео-референса у Ancient Leshen нет (решение
  оркестратора 2026-10-14: видео SYNTX не масштабируются на ростер); это ориентир тайминга и поз, не цель.
- Характер героя: лист концепта art/imagegen/concept-ancient-leshen-codex/sheet-ancient-leshen.png, эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Ancient Leshen (The Witcher) — герой
  дальнего боя без оружия, удар — когти ПРАВОЙ кисти (сокет Weapon на hand.R), череп оленя с высокими рогами, ствол из
  скрученных корней вместо ног, три вороны (левое плечо, оба предплечья); карточка задачи AN-137
  (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale, не в rework_fix_list, если кадр не показывает видимый разрыв): ног нет — низ фигуры ствол из корней; кости ног живут внутри ствола (leg_upper берёт до 50 % половин ствола, голень и стопа весов не имеют), корни у подставки держит стык roots_planted профиля h2-bake. Поэтому foot_slide в contact-<Clip>.json проходит при foot_vertices 0 и ничего не проверяет — сдвиг корней измерен отдельно: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/roots-planted.json (внешние корни r > 6 см ≤ 0,5 % роста во всех клипах). Таз не сдвигается: у этого рига голова hips лежит на оси root, импорт FBX делает hips connected и выбрасывает location — движение ствола только поворотом hips. Кадры ik_unreached в author-<Clip>.json (Idle, DeathSettle) — прямая цепь ног внутри ствола (дефицит ≤ 0,1 см, стопы без весов), а не скольжение. Вороны жёстко на костях (левое плечо — spine, предплечья — arm_lower.L/R, решение этапа 3): при поднятом правом предплечье ворона на нём висит вниз головой — это следствие жёсткой посадки, оценивай только пересечения и разрывы. Рога высокие (верх bounds 73,6 uu при верхе черепа 55): руки не должны входить в рога.
- Предыдущая карточка: null (null на r1). Проверь, закрыт ли её rework_fix_list, но баллы
  ставь заново по свежим кадрам.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи LESH-Idle в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора (корни и подставка); D — деформация на пике амплитуды на крупном плане; L — оседание и цикл (шов петли к.56 = к.0).
   Для этого клипа особенно: C — опора: корни на подставке (reports/roots-planted.json), ствол гнётся выше корней; L — шов петли к.56 = к.0. В rationale назови кадры и видимый признак; frames — имена файлов из
   frames.files.
3. score = round((R + C + D + L) / 8 × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт по §10.5: любой гейт FAIL, любое измерение < 1,0 или score < 8,0 → rework_blender;
   иначе pass; на r3 любой не-pass → escalate_user. При любом вердикте, кроме pass, заполни verdict_reason
   (≥ 10 символов): какое правило сработало.
4. rework_fix_list — при pass []. При rework_blender список покрывает каждый FAIL-гейт и каждое измерение < 1,0;
   пункт строго {"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и на каком кадре
   клипа>", "tool": "<ключ спеки clips.Idle: keys | waves | key_frames | ik_feet | hand_follow | template |
   amplitude_scale; или «h2_bake профиль (веса), этап 5 модели»; для G-MANIFEST — «этап 7: h2anim_ue.py import +
   clip_manifest.py build»>"}, других ключей нет. Длину клипа, fps и кадр контакта не предлагать менять (§10.6).
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до этапа 7 (лист K1/K2):
   [{"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-ANCIENT-LESHEN-001", clip "Idle",
   date "2026-10-14", cycle "r1", previous_card null,
   accepted_object [{"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/export/AM_AncientLeshen_Idle.fbx", "sha256": "2c0220bc9bc26ae7ed0b183cb348ca4e54dbd529281fb3ee588fbb12f097b0a4"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2anim.json", "sha256": "0443032fa68dac48abfde878ddc4fc701c2f9951f8ebb23b26136fda8cddfe8f"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance-anim/20261014-r1/Idle/frames", "files": ["AncientLeshen-Idle-blender-sheet.jpg", "AncientLeshen-Idle-f14-front.jpg", "AncientLeshen-Idle-f14-q34.jpg", "AncientLeshen-Idle-f42-q34.jpg", "AncientLeshen-Idle-f00-front-ue-editor.jpg", "AncientLeshen-Idle-f00-q34-ue-editor.jpg", "AncientLeshen-Idle-f14-front-ue-editor.jpg", "AncientLeshen-Idle-f14-q34-ue-editor.jpg", "AncientLeshen-Idle-f28-front-ue-editor.jpg", "AncientLeshen-Idle-f28-q34-ue-editor.jpg", "AncientLeshen-Idle-f42-front-ue-editor.jpg", "AncientLeshen-Idle-f42-q34-ue-editor.jpg", "AncientLeshen-H2Anim-ue-sheet.jpg"]},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_AncientLeshen_Idle.validation.json", "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/contact-Idle.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2anim/reports/roots-planted.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage6-leshen",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
