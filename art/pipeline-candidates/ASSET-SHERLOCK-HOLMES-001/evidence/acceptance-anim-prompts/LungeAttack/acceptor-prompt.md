# Приёмка клипа AM_SherlockHolmes_LungeAttack, цикл {{CYCLE}} (шаг 7a.2)

<!-- ЗАГОТОВКА этапа 6 (2026-10-21, волна A мини-пачки 2026-10-20), не запускалась; собрана скриптом
C:/tmp/sherlock-holmes-stage6/gen_prompts.py по спеке и отчётам прогона. На шаге 7a.2 её заполняет
tools/tripo-pipeline/ue7a/prep_acceptance.py (--asset-dir art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001 --key SherlockHolmes --run art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2 --spec art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/build-profiles/sherlock-holmes-h2anim.json --cycle r1):
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
- Кадры: {{E}}/LungeAttack/frames/ — открой КАЖДЫЙ файл из списка {{FRAMES_FILES_JSON}} в полном размере (1:1):
  Blender-лист `SherlockHolmes-LungeAttack-blender-sheet.jpg` (кадры key_frames [0, 2, 4, 7, 9, 12, 14], виды front / left / q34, кости поверх),
  крупные планы Blender (art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/preview/closeups-blender/: SherlockHolmes-LungeAttack-f02-left.jpg, SherlockHolmes-LungeAttack-f04-front.jpg, SherlockHolmes-LungeAttack-f04-left.jpg, SherlockHolmes-LungeAttack-f04-q34r.jpg, SherlockHolmes-LungeAttack-f07-front.jpg, SherlockHolmes-LungeAttack-f07-left.jpg, SherlockHolmes-LungeAttack-f07-q34.jpg, SherlockHolmes-LungeAttack-f07-q34r.jpg, SherlockHolmes-LungeAttack-f08-back.jpg, SherlockHolmes-LungeAttack-f08-q34.jpg, SherlockHolmes-LungeAttack-f08-q34b-b.jpg, SherlockHolmes-LungeAttack-f08-q34b.jpg, SherlockHolmes-LungeAttack-f08-q34r.jpg, SherlockHolmes-LungeAttack-f08-topb.jpg, SherlockHolmes-LungeAttack-f09-q34b.jpg, SherlockHolmes-LungeAttack-f09-q34bl.jpg; камера каждого кадра — в
  SherlockHolmes-LungeAttack-closeups.json). UE-кадры `SherlockHolmes-LungeAttack-fNN-{front,q34}-ue-editor.jpg`, крупный план кадров вокруг контакта `SherlockHolmes-LungeAttack-fNN-*-closeup-ue-editor.jpg`, лист
  `SherlockHolmes-H2Anim-ue-sheet.jpg`. Другие файлы каталога {{E}} (card*.json, final.json, acceptor-*) не открывай.
- Клип: AM_SherlockHolmes_LungeAttack, роль oneshot, 14 к. при 24 fps (0.583 с); кадр 0 = rest, последний кадр = rest.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/build-profiles/sherlock-holmes-h2anim.json): «короткий прямой тычок кулаком с лупой (бартицу), не взмах: подготовка (к. 0–4) — корпус скручивается вправо и чуть откидывается, кулак с лупой отходит назад к правому плечу, лупа взведена назад, голова держит цель; короткий выброс (к. 4–7): корпус разворачивается влево и наклоняется вперёд, таз доворачивается вперёд (поворот, без сдвига), правая рука выпрямляется вперёд (локоть ≈ 125–135°, плечо поднято вперёд, не вбок), кисть доворачивает лупу к цели (излом запястья ≤ 20°) — к. 7 = Contact: кулак перед корпусом на уровне груди цели; проводка (к. 9) — кулак ещё чуть дальше; возврат (к. 12–14) в rest; лупа всё время жёстко в кулаке (кость weapon.R без ключей), левая рука уравновешивает (к. 4 вперёд, к. 7–9 назад); стопы на месте, пальто и пелерина идут с корпусом».
- Контакт: LUNGE_CONTACT_FRAME = 7 (к.7 = 292 мс при 24 fps); C — удар точно в к.7 и с весом.
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_SherlockHolmes_LungeAttack.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/contact-LungeAttack.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись SHER-LungeAttack, G-MANIFEST), art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/author-LungeAttack.json (ik_log), art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/grip-LungeAttack.json (машинный замер по FBX клипа): поворот weapon.R (лупы) в кулаке ≤ 0.0° на всех кадрах, излом правого запястья ≤ 19.4°, локоть правой руки 72.1–135.7°, уход плоскости сгиба локтя ≤ 0.0°, колени не ниже 175.0°, пересечений лупы с телом 0.
- WARN контактов: skin_stretch — рёбра растяжения только в закрытых местах (видимых рваных рёбер 0; к.8,9; области arm_lower.R|hand.R).
- Референс движения: образец библиотеки D-11 — спека Achilles r3 (art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim-r3.json, clips.LungeAttack: длинная подготовка, короткий выпад-укол к цели, контакт к.7) ← Merlin LungeAttack; art/animation-refs/ASSET-MERLIN-001/MER-LungeAttack/contact-sheet-2fps.png. Укол копьём стал коротким прямым тычком кулаком с лупой: Шерлок не мечник, рубящий удар меча (паттерн Beowulf) рвал ему запястье на дымовом прогоне этапа 3; это ориентир тайминга и поз, не цель. Своего видео-референса у Шерлока нет (ДС-6, траты 0).
- Характер героя: лист концепта art/imagegen/concept-sherlock-holmes-codex/sherlock-holmes-front.png (и кадры модели
  art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/<цикл принятой модели>/frames/sheet.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Sherlock Holmes — детектив, герой
  ближнего боя (кулачный удар, HIT_TYPE CLAW), высокий худой, кепи-охотничья, пальто Инвернесс с пелериной поверх
  твидового костюма, изогнутая трубка во рту (жёстко на голове), лупа в ПРАВОЙ руке (оружие — кость weapon.R);
  карточка задачи AN-161
  (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale и known_issues, не в rework_fix_list и не
  ниже 1,0, если кадр не показывает видимый разрыв, дыру или отрыв части; один список на все 4 клипа):
{{KNOWN_LIMITS}}
- Предыдущая карточка: {{PREVIOUS_CARD_JSON}} (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи SHER-LungeAttack в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора; D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: R — читается короткий прямой тычок кулаком с лупой (подготовка к.2–4 → выброс к.7 → проводка к.9 → возврат), а не взмах; характер — точный, экономный; C — удар точно в к.7 и с весом (корпус доворачивается влево и наклоняется вперёд, таз доворачивается), стопы на месте; D — запястье и локоть правой руки на подготовке (к.4) и на контакте (к.7–9) на крупном плане, кромка рукава и пелерины пальто справа-сзади (q34b) — пелерина не задирается за рукой; лупа жёстко в кулаке и не входит в голову, козырёк и трубку на подготовке. В rationale назови кадры и видимый признак; frames — имена файлов из
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
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-SHERLOCK-HOLMES-001", clip "LungeAttack",
   date "{{DATE}}", cycle "{{CYCLE}}", previous_card {{PREVIOUS_CARD_JSON}},
   accepted_object [{"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/export/AM_SherlockHolmes_LungeAttack.fbx", "sha256": "a66787adcf42225cab851381092f8114318bd208194281c9e43d1617fea7e5bb"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/build-profiles/sherlock-holmes-h2anim.json", "sha256": "b8cd7099343c70a32db99ff24c46c6c1748d71f93f37ddb68e923025bcc33d8a"}],
   frames {"dir": "{{E}}/LungeAttack/frames", "files": {{FRAMES_FILES_JSON}}},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_SherlockHolmes_LungeAttack.validation.json", "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/contact-LungeAttack.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2anim-r2/reports/grip-LungeAttack.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Opus xhigh", "session_id": "<сессия приёмщика>"},
   executor_session_id "claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe/agent:stage6-sherlock",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
