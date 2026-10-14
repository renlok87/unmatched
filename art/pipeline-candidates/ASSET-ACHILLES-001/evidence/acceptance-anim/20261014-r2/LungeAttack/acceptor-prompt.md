# Приёмка клипа AM_Achilles_LungeAttack, цикл r2 (этап 6 скилла 3d-model-pipeline)

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
- Кадры: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r2/LungeAttack/frames/ — открой КАЖДЫЙ файл из списка ["Achilles-LungeAttack-blender-sheet.jpg", "Achilles-LungeAttack-f04-front.jpg", "Achilles-LungeAttack-f04-q34.jpg", "Achilles-LungeAttack-f07-back.jpg", "Achilles-LungeAttack-f07-front.jpg", "Achilles-LungeAttack-f07-left.jpg", "Achilles-LungeAttack-f07-q34.jpg", "Achilles-LungeAttack-f07-q34b.jpg", "Achilles-LungeAttack-f07-q34r.jpg", "Achilles-LungeAttack-f09-q34r.jpg", "Achilles-LungeAttack-f00-front-ue-editor.jpg", "Achilles-LungeAttack-f00-q34-ue-editor.jpg", "Achilles-LungeAttack-f02-front-ue-editor.jpg", "Achilles-LungeAttack-f02-q34-ue-editor.jpg", "Achilles-LungeAttack-f04-front-ue-editor.jpg", "Achilles-LungeAttack-f04-q34-ue-editor.jpg", "Achilles-LungeAttack-f07-front-ue-editor.jpg", "Achilles-LungeAttack-f07-q34-ue-editor.jpg", "Achilles-LungeAttack-f09-front-ue-editor.jpg", "Achilles-LungeAttack-f09-q34-ue-editor.jpg", "Achilles-LungeAttack-f12-front-ue-editor.jpg", "Achilles-LungeAttack-f12-q34-ue-editor.jpg", "Achilles-LungeAttack-f14-front-ue-editor.jpg", "Achilles-LungeAttack-f14-q34-ue-editor.jpg", "Achilles-LungeAttack-f06-front-closeup-ue-editor.jpg", "Achilles-LungeAttack-f06-q34-closeup-ue-editor.jpg", "Achilles-LungeAttack-f07-front-closeup-ue-editor.jpg", "Achilles-LungeAttack-f07-q34-closeup-ue-editor.jpg", "Achilles-LungeAttack-f09-front-closeup-ue-editor.jpg", "Achilles-LungeAttack-f09-q34-closeup-ue-editor.jpg", "Achilles-H2Anim-ue-sheet.jpg"] в полном размере (1:1):
  Blender-лист `Achilles-LungeAttack-blender-sheet.jpg` (кадры key_frames [0, 2, 4, 7, 9, 12, 14], виды front / left / q34, кости
  поверх), крупные планы Blender (art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/preview/closeups-blender/: Achilles-LungeAttack-f04-q34.jpg и -f04-front.jpg (замах: кисть у правого бока, щит вперёд), -f07-front.jpg и -f07-q34r.jpg (хват на контакте), -f07-left.jpg (профиль укола), -f07-q34.jpg (вся фигура), -f07-back.jpg (ноги и плащ сзади), -f09-q34r.jpg (проводка, хват), -f07-q34b.jpg (кромка у правой подмышки сзади)), UE-кадры `Achilles-LungeAttack-fNN-{front,q34}-ue-editor.jpg` и крупный план кадров вокруг контакта `Achilles-LungeAttack-fNN-*-closeup-ue-editor.jpg`, лист
  `Achilles-H2Anim-ue-sheet.jpg`. Другие файлы каталога art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r2 (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_Achilles_LungeAttack, роль oneshot, 14 к. при 24 fps (0.583 с); кадр 0 = rest, последний кадр = rest.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim-r3.json):
  «подготовка (к. 0–4, как Merlin): пятка копья отрывается от подставки, кисть поднимается и уходит назад к правому боку, копьё наклоняется наконечником вперёд-вверх к цели (к. 2 — 20°, к. 4 — 48° от вертикали; пятка уходит назад-наружу мимо плаща), корпус разворачивается вправо и чуть откидывается, щит выходит вперёд (прикрытие), голова держит цель; короткий выброс (к. 4–7): корпус разворачивается влево и наклоняется вперёд, таз вперёд с опусканием 0,4 см (колени чуть сгибаются), правая рука выбрасывает копьё вперёд — к. 7 = Contact: рука почти прямая (локоть 129°), копьё наклонено вперёд на 55°, наконечник вперёд-внутрь на уровне плеча цели (+X, в 18 см перед наконечником rest), пятка позади-снаружи (y −18,7) мимо плаща; щит отходит к левому боку; проводка (к. 8–9): наконечник ещё на 1,3 см дальше и ниже; возврат (к. 10–13): копьё выпрямляется, пятка опускается и висит в 0,4–0,5 см над подставкой; к. 14 = rest (пятка на подставке). Копьё всё время жёстко в кулаке: кость weapon.R без ключей, направление копья — поворот кисти aim hand.R (from = ось копья в rest, from2 = ось кисти), рука — aim arm_upper.R/arm_lower.R полными базисами (from2/to2 — ось сгиба локтя), без скрутки предплечья; излом запястья ≤ 26° (к. 2), на контакте 13°».
- UE-кадры (`*-ue-editor.jpg`, лист `Achilles-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` на меше-носителе `/Game/PipelineCandidates/Achilles/Rig/SK_Achilles` (геометрия H2 модели r3 — bake 20261014-h2-bake-r3, носитель переимпортирован из неё — без look-dev материалов, поэтому фигура серая — так снимаются все герои библиотеки D-11) на подставке `SM_Achilles_H2LD_Base` (её MI по умолчанию — команда P1, поэтому борт подставки жёлтый); цвет и материал в этой приёмке не оцениваются. Свет — закреплённый cobble-probe rev 5 (`--light-pinned ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), High, редактор: это диагностические кадры, не K1/K2. Крупные планы Blender лежат и в art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r2/<клип>/frames/ (копии файлов из preview/closeups-blender/).
- Контакт: LUNGE_CONTACT_FRAME = 7 (к.7 = 292 мс при 24 fps); C — укол точно в к.7 и с весом.
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_Achilles_LungeAttack.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/contact-LungeAttack.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись ACH-LungeAttack, G-MANIFEST), art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/author-LungeAttack.json (ik_log), art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/grip-LungeAttack.json (своя проверка исполнителя, по FBX клипа): поворот weapon.R в кулаке ≤ 0.00° на всех кадрах, щит относительно предплечья ≤ 0.000 см, кисть щита (hand.L) к предплечью 0.00°, излом правого запястья ≤ 26.1°, локоть правой руки 92–132°, пятка копья в подставку не уходит (≤ 0.06 см при rest 0,06), пересечений копья и щита с телом 0.
- WARN контактов: skin_stretch — рёбра только в закрытых местах (видимых рваных рёбер 0): подол плаща у щиколоток и щиколотки при сгибе колен (limb_body_R на модели r3 — pass).
- Референс движения: образец библиотеки D-11 — art/animation-refs/ASSET-MERLIN-001/MER-LungeAttack/contact-sheet-2fps.png (Merlin: длинная подготовка и короткий выброс древка к цели; у Achilles контакт к.7, как у King Arthur) и art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-LungeAttack/contact-sheet-2fps.png (King Arthur: ближний бой, контакт к.7). Своего видео-референса у Achilles нет (решение
  оркестратора 2026-10-14: «No SYNTX spend … author from library patterns»); это ориентир тайминга и поз, не цель.
- Характер героя: лист концепта art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames/sheet.png (и art/imagegen/concept-achilles-codex/achilles-front.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Achilles — герой ближнего боя, копьё
  вертикально в ПРАВОЙ руке пяткой на подставке, круглый бронзовый щит на ЛЕВОМ предплечье, красный плащ, шлем с
  гребнем; карточка задачи AN-142 (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale, не в rework_fix_list, если кадр не показывает видимый разрыв): копьё из двух частей Tripo — наконечник с верхом древка (меш оружия) и низ древка с пяткой (часть меша тела, 100 % на weapon.R), обе жёстко на кости оружия; щит без своей кости — 100 % на arm_lower.L, кисть hand.L ключей не имеет, поэтому хват ручки щита не смещается; ноги в rest прямые (колено 177°), любое смещение таза идёт с опусканием 0,1–0,55 см, отсюда небольшой сгиб колен в выпаде, отдаче и смерти (колено ≥ 149°, подъём бедра ≤ 16° против 35° в pose-04 этапа 4: крышка контакта плаща за голенью не открывается); при строго фронтальном взгляде колющее копьё сокращается — укол читается с боков и с q34.
- Предыдущая карточка: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r1/LungeAttack/card.json (цикл r1, verdict pass, score 9,4, rework_fix_list пуст). FBX клипа пересобран на модели r3 (веса стыков руки с плащом и кирасой у правой подмышки, bake 20261014-h2-bake-r3; ключи клипа те же), поэтому приёмка повторяется. Баллы ставь заново по свежим кадрам r2.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи ACH-LungeAttack в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора (стопы, пятка копья и подставка, укол в к.7); D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: C — укол точно в к.7 и с весом (корпус разворачивается влево и наклоняется вперёд, таз вперёд, рука почти прямая, наконечник вперёд у плеча цели), стопы на месте; D — хват копья (копьё не проворачивается в кулаке), плечо и локоть правой руки на замахе (к.4) и контакте (к.7–9) на крупном плане. В rationale назови кадры и видимый признак; frames — имена файлов из
   frames.files.
3. score = round((R + C + D + L) / 8 × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт по §10.5: любой гейт FAIL, любое измерение < 1,0 или score < 8,0 → rework_blender;
   иначе pass; на r3 любой не-pass → escalate_user. При любом вердикте, кроме pass, заполни verdict_reason
   (≥ 10 символов): какое правило сработало.
4. rework_fix_list — при pass []. При rework_blender список покрывает каждый FAIL-гейт и каждое измерение < 1,0;
   пункт строго {"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и на каком кадре
   клипа>", "tool": "<ключ спеки clips.LungeAttack: keys | waves | key_frames | ik_feet | hand_follow | template |
   amplitude_scale; или «h2_bake профиль (веса), этап 5 модели»; для G-MANIFEST — «этап 7: h2anim_ue.py import +
   clip_manifest.py build»>"}, других ключей нет. Длину клипа, fps и кадр контакта не предлагать менять (§10.6).
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до этапа 7 (лист K1/K2):
   [{"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-ACHILLES-001", clip "LungeAttack",
   date "2026-10-14", cycle "r2", previous_card "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r1/LungeAttack/card.json",
   accepted_object [{"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/export/AM_Achilles_LungeAttack.fbx", "sha256": "8ab06516bb2ac038e7810aad52a084178f1ecc2ac22781ae3f6285d1fce3a543"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim-r3.json", "sha256": "f73d4c434774033cf3f6ad1da917b4f9e0d10a8440b858da1d4b8ee9da646d78"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r2/LungeAttack/frames", "files": ["Achilles-LungeAttack-blender-sheet.jpg", "Achilles-LungeAttack-f04-front.jpg", "Achilles-LungeAttack-f04-q34.jpg", "Achilles-LungeAttack-f07-back.jpg", "Achilles-LungeAttack-f07-front.jpg", "Achilles-LungeAttack-f07-left.jpg", "Achilles-LungeAttack-f07-q34.jpg", "Achilles-LungeAttack-f07-q34b.jpg", "Achilles-LungeAttack-f07-q34r.jpg", "Achilles-LungeAttack-f09-q34r.jpg", "Achilles-LungeAttack-f00-front-ue-editor.jpg", "Achilles-LungeAttack-f00-q34-ue-editor.jpg", "Achilles-LungeAttack-f02-front-ue-editor.jpg", "Achilles-LungeAttack-f02-q34-ue-editor.jpg", "Achilles-LungeAttack-f04-front-ue-editor.jpg", "Achilles-LungeAttack-f04-q34-ue-editor.jpg", "Achilles-LungeAttack-f07-front-ue-editor.jpg", "Achilles-LungeAttack-f07-q34-ue-editor.jpg", "Achilles-LungeAttack-f09-front-ue-editor.jpg", "Achilles-LungeAttack-f09-q34-ue-editor.jpg", "Achilles-LungeAttack-f12-front-ue-editor.jpg", "Achilles-LungeAttack-f12-q34-ue-editor.jpg", "Achilles-LungeAttack-f14-front-ue-editor.jpg", "Achilles-LungeAttack-f14-q34-ue-editor.jpg", "Achilles-LungeAttack-f06-front-closeup-ue-editor.jpg", "Achilles-LungeAttack-f06-q34-closeup-ue-editor.jpg", "Achilles-LungeAttack-f07-front-closeup-ue-editor.jpg", "Achilles-LungeAttack-f07-q34-closeup-ue-editor.jpg", "Achilles-LungeAttack-f09-front-closeup-ue-editor.jpg", "Achilles-LungeAttack-f09-q34-closeup-ue-editor.jpg", "Achilles-H2Anim-ue-sheet.jpg"]},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_Achilles_LungeAttack.validation.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/contact-LungeAttack.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim-r3/reports/grip-LungeAttack.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage5r3-achilles",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла, кроме предыдущей карточки r1 этого клипа).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
