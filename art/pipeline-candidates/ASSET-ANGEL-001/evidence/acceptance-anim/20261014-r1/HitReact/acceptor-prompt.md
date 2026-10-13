# Приёмка клипа AM_Angel_HitReact, цикл r1 (этап 6 скилла 3d-model-pipeline)

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
- Кадры: art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance-anim/20261014-r1/HitReact/frames/ — открой КАЖДЫЙ файл из списка ["Angel-HitReact-blender-sheet.jpg", "Angel-HitReact-f00-front-ue-editor.jpg", "Angel-HitReact-f00-q34-ue-editor.jpg", "Angel-HitReact-f02-front-ue-editor.jpg", "Angel-HitReact-f02-q34-ue-editor.jpg", "Angel-HitReact-f04-front-ue-editor.jpg", "Angel-HitReact-f04-q34-ue-editor.jpg", "Angel-HitReact-f07-front-ue-editor.jpg", "Angel-HitReact-f07-q34-ue-editor.jpg", "Angel-HitReact-f10-front-ue-editor.jpg", "Angel-HitReact-f10-q34-ue-editor.jpg", "Angel-H2Anim-ue-sheet.jpg"] в полном размере (1:1):
  Blender-лист `Angel-HitReact-blender-sheet.jpg` (кадры key_frames [0, 2, 4, 7, 10], виды front / left / q34, кости
  поверх), UE-кадры `Angel-HitReact-fNN-{front,q34}-ue-editor.jpg`, лист `Angel-H2Anim-ue-sheet.jpg`. Другие файлы каталога art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance-anim/20261014-r1
  (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_Angel_HitReact, роль oneshot, 10 к. при 24 fps (0.417 с); кадр 0 = rest, последний кадр = rest.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2anim.json):
  «отдача корпуса назад с доворотом, голова мотнулась, меч откачнулся и вернулся, левая рука отлетает назад; стопы на месте, без приседа».
- Реакция на удар спереди (атакующий перед фигурой, +X): отдача назад; C — сторона реакции.
- UE-кадры (`*-ue-editor.jpg`) сняты инструментом `h2anim_ue.py frames` на меше-носителе `/Game/PipelineCandidates/Angel/Rig/SK_Angel` (геометрия H2 без look-dev материалов, поэтому фигура серая и без подставки — так снимаются все герои библиотеки D-11); цвет и материал в этой приёмке не оцениваются. Свет — cobble-probe rev 5 (из отчёта `ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), High, редактор: это диагностические кадры, не K1/K2.
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_Angel_HitReact.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2anim/reports/contact-HitReact.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись ANG-HitReact, G-MANIFEST), art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2anim/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2anim/reports/author-HitReact.json (ik_log, weapon_tip).
- Референс движения: образец библиотеки D-11 — видео-референс King Arthur того же клипа
  art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-HitReact/contact-sheet-2fps.png (тот же тип оружия: меч в правой руке).
  Своего видео-референса у Angel нет (решение оркестратора 2026-10-14); это ориентир тайминга и поз, не цель.
- Характер героя: лист концепта art/imagegen/concept-angel-codex/sheet-angel.png, эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Angel — герой ближнего боя, широкий
  меч в ПРАВОЙ руке (weapon.R), длинное чёрное кожаное пальто нараспашку, острые тёмные волосы; карточка задачи
  AN-135 (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы (HANDBOOK §4.5 п.4 и этот герой; учитываются как ограничение — в rationale, не в rework_fix_list, если кадр не показывает видимый разрыв): пальто скинено на hips/spine и до 0,55 на бёдра к подолу, поэтому клипы без приседа; ноги Angel в rest почти прямые (таз–лодыжка 21,8 см = длина ноги), таз в клипах почти не поднимается и не уходит вперёд. Приёмка модели (этап 4 r1, known_issues F, pose-04.jpg): подъём левого бедра открывает плоскую гранёную крышку верхнего контакта брюк — проверь кадры, где левое бедро уходит из положения покоя. В DeathSettle левая рука висит наружу от корпуса: ближе к телу она входит в широкое пальто (проба исполнителя 2026-10-14: limb_body_L FAIL, 80 пар).
- Предыдущая карточка: null (null на r1). Проверь, закрыт ли её rework_fix_list, но баллы
  ставь заново по свежим кадрам.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи ANG-HitReact в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора (стопы, подол, подставка); D — деформация на пике
   амплитуды на крупном плане; L — оседание и цикл. В rationale
   назови кадры и видимый признак; frames — имена файлов из frames.files.
3. score = round((R + C + D + L) / 8 × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт по §10.5: любой гейт FAIL, любое измерение < 1,0 или score < 8,0 → rework_blender;
   иначе pass; на r3 любой не-pass → escalate_user. При любом вердикте, кроме pass, заполни verdict_reason
   (≥ 10 символов): какое правило сработало.
4. rework_fix_list — при pass []. При rework_blender список покрывает каждый FAIL-гейт и каждое измерение < 1,0;
   пункт строго {"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и на каком кадре
   клипа>", "tool": "<ключ спеки clips.HitReact: keys | waves | key_frames | ik_feet | hand_follow | template |
   amplitude_scale; или «h2_bake профиль (веса), этап 5 модели»; для G-MANIFEST — «этап 7: h2anim_ue.py import +
   clip_manifest.py build»>"}, других ключей нет. Длину клипа, fps и кадр контакта не предлагать менять (§10.6).
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до этапа 7 (лист K1/K2):
   [{"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-ANGEL-001", clip "HitReact",
   date "2026-10-14", cycle "r1", previous_card null,
   accepted_object [{"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2anim/export/AM_Angel_HitReact.fbx", "sha256": "6a66844d1cb7dd07873a9a4e0219f2c761aed4040ffebcc7117809669e46c7a0"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2anim.json", "sha256": "b7ab2708b2722733a2a17b973d454b44f706b2ce96353f4440b01cd18b93b293"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance-anim/20261014-r1/HitReact/frames", "files": ["Angel-HitReact-blender-sheet.jpg", "Angel-HitReact-f00-front-ue-editor.jpg", "Angel-HitReact-f00-q34-ue-editor.jpg", "Angel-HitReact-f02-front-ue-editor.jpg", "Angel-HitReact-f02-q34-ue-editor.jpg", "Angel-HitReact-f04-front-ue-editor.jpg", "Angel-HitReact-f04-q34-ue-editor.jpg", "Angel-HitReact-f07-front-ue-editor.jpg", "Angel-HitReact-f07-q34-ue-editor.jpg", "Angel-HitReact-f10-front-ue-editor.jpg", "Angel-HitReact-f10-q34-ue-editor.jpg", "Angel-H2Anim-ue-sheet.jpg"]},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_Angel_HitReact.validation.json", "art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2anim/reports/contact-HitReact.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2anim/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2anim/reports/ue-measure-clips.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage6-angel",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
