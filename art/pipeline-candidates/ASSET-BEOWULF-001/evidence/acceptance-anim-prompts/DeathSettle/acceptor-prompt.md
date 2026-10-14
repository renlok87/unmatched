# Приёмка клипа AM_Beowulf_DeathSettle, цикл {{CYCLE}} (шаг 7a.2)

<!-- ЗАГОТОВКА этапа 6 (2026-10-14, фигура-проверка скилла), не запускалась. На шаге 7a.2 её заполняет
tools/tripo-pipeline/ue7a/prep_acceptance.py (--asset-dir art/pipeline-candidates/ASSET-BEOWULF-001 --key Beowulf --run art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim --spec art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2anim.json --cycle r1):
{{E}}, {{DATE}}, {{CYCLE}}, {{PREVIOUS_CARD_JSON}}, {{FRAMES_FILES_JSON}}, список пределов из
evidence/acceptance-anim-prompts/known-limits.md, заметка о меше-носителе UE-кадров; sha256 в accepted_object сверяются с
файлами. Профиль приёмщика — по выбору запускающего: при «Opus xhigh» заменить строку acceptor. Порядок — art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/README.md. -->

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
- Кадры: {{E}}/DeathSettle/frames/ — открой КАЖДЫЙ файл из списка {{FRAMES_FILES_JSON}} в полном размере (1:1):
  Blender-лист `Beowulf-DeathSettle-blender-sheet.jpg` (кадры key_frames [0, 3, 6, 9, 13, 16, 21], виды front / left / q34, кости поверх),
  крупные планы Blender (art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/preview/closeups-blender/: Beowulf-DeathSettle-f13-front.jpg, Beowulf-DeathSettle-f13-q34r.jpg, Beowulf-DeathSettle-f13-right.jpg, Beowulf-DeathSettle-f16-q34.jpg, Beowulf-DeathSettle-f17-q34b.jpg, Beowulf-DeathSettle-f21-front.jpg, Beowulf-DeathSettle-f21-left.jpg, Beowulf-DeathSettle-f21-q34.jpg, Beowulf-DeathSettle-f21-q34l.jpg, Beowulf-DeathSettle-f21-q34r-b.jpg, Beowulf-DeathSettle-f21-q34r.jpg, Beowulf-DeathSettle-f21-right.jpg; камера каждого кадра — в
  Beowulf-DeathSettle-closeups.json). UE-кадры `Beowulf-DeathSettle-fNN-{front,q34}-ue-editor.jpg`, лист
  `Beowulf-H2Anim-ue-sheet.jpg`. Другие файлы каталога {{E}} (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_Beowulf_DeathSettle, роль terminal, 21 к. при 24 fps (0.875 с); кадр 0 = rest, последний кадр держится.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2anim.json): «удар и отшатывание (к. 3); правая рука опускает меч вперёд и вниз (к. 6–9), к к. 12 рука висит почти прямо (локоть ≈ 152°), кисть опущена (излом запястья ≤ 28°), меч остаётся в кулаке в исходном хвате (кость weapon.R без ключей, гарда на кулаке) и ложится плашмя — клинок почти горизонтально вперёд над краем подставки (остриё ≈ 24 см вперёд, на высоте 30 см); Beowulf клонится вперёд и вправо (наклон spine 15→17°, крен 10→7°), голова падает, левая рука со щитом повисает (к. 12–21), финальная поза держится. Ноги прямые: без приседа и без подъёма бедра (таз опущен на 0,4 см)».
- Контакт: LUNGE_CONTACT_FRAME героя = 7 (к.7 = 292 мс выпада); у этого клипа контакта нет — C судит опору и реакцию по §10.4.
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_Beowulf_DeathSettle.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/contact-DeathSettle.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись BEO-DeathSettle, G-MANIFEST), art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/author-DeathSettle.json (ik_log), art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/grip-DeathSettle.json (машинный замер по FBX клипа): поворот weapon.R в кулаке ≤ 0.0° на всех кадрах (меч в исходном хвате), щит относительно предплечья ≤ 0.000 см, излом правого запястья ≤ 28.4°, локоть правой руки 128.3–152.5°, колени не ниже 154.0°, пересечений меча с телом 0, щита с телом 0; art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/rider-gap.json (рукоять щита к кисти во всех кадрах).
- WARN контактов: skin_stretch — рёбра растяжения только в закрытых местах (видимых рваных рёбер 0; к.11,12,13,14,15,16,17,18,19,20,21; области arm_lower.R|arm_upper.R, foot.L|leg_lower.L, foot.R|leg_lower.R).
- Референс движения: образец библиотеки D-11 — спека Angel r2 (art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2anim-r2.json, все 4 клипа приняты на 7a.2) по клипам меча King Arthur; art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-DeathSettle/contact-sheet-2fps.png. Своего видео-референса у Beowulf нет (ДС-6: меч в правой руке — стандартное движение); это ориентир тайминга и поз, не цель.
- Характер героя: лист концепта art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames/sheet.png (и art/imagegen/concept-beowulf-codex/beowulf-front.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Beowulf — герой ближнего боя, длинный меч
  в ПРАВОЙ руке, круглый деревянный щит на ЛЕВОЙ руке, меховая мантия, кольчужная туника, железный шлем, борода с
  косами; карточка задачи AN-148 (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale и known_issues, не в rework_fix_list и не
  ниже 1,0, если кадр не показывает видимый разрыв, дыру или отрыв части; один список на все 4 клипа):
{{KNOWN_LIMITS}}
- Предыдущая карточка: {{PREVIOUS_CARD_JSON}} (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи BEO-DeathSettle в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора; D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: C — опора стоп и оседание без приседа, меч опускается и ложится плашмя в исходном хвате (без опоры острием); D — кисть с мечом (гарда на кулаке, меч не проворачивается; -f21-front, -f13-q34r), сгиб правого локтя при почти прямой руке (-f21-q34r-b) и кромка рукава и мантии у правого плеча сзади (-f17-q34b) на крупном плане; L — финальная поза держится без дрожи; R — поклон, не похожий на HitReact. В rationale назови кадры и видимый признак; frames — имена файлов из
   frames.files.
3. score = round((R + C + D + L) / 8 × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт по §10.5: любой гейт FAIL, любое измерение < 1,0 или score < 8,0 → rework_blender;
   иначе pass; на r3 любой не-pass → escalate_user. При любом вердикте, кроме pass, заполни verdict_reason
   (≥ 10 символов): какое правило сработало.
4. rework_fix_list — при pass []. При rework_blender список покрывает каждый FAIL-гейт и каждое измерение < 1,0;
   пункт строго {"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и на каком кадре
   клипа>", "tool": "<ключ спеки clips.DeathSettle: keys | waves | key_frames | ik_feet | hand_follow | template |
   amplitude_scale; или «этап 5 модели: <ключ профиля bake или стадия>» для дефекта модели (§10.5); для G-MANIFEST —
   «этап 7: h2anim_ue.py import + clip_manifest.py build»>"}, других ключей нет. Длину клипа, fps и кадр контакта не
   предлагать менять (§10.6).
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до этапа 7 (лист K1/K2):
   [{"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-BEOWULF-001", clip "DeathSettle",
   date "{{DATE}}", cycle "{{CYCLE}}", previous_card {{PREVIOUS_CARD_JSON}},
   accepted_object [{"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/export/AM_Beowulf_DeathSettle.fbx", "sha256": "8c9b9af7c68a857f7d37bcb902494edf689b8c4f60ab8fed5b7c7ecf2288595a"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2anim.json", "sha256": "d3227542f85e141749221a977578acade57ab756c9df5f651c39b489f70b9660"}],
   frames {"dir": "{{E}}/DeathSettle/frames", "files": {{FRAMES_FILES_JSON}}},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_Beowulf_DeathSettle.validation.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/contact-DeathSettle.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim/reports/grip-DeathSettle.json"] (только те, что существуют, плюс другие из note гейтов),
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
