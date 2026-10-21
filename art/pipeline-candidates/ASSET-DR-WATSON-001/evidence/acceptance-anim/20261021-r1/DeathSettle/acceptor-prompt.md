# Приёмка клипа AM_DrWatson_DeathSettle, цикл r1 (шаг 7a.2)

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
- Кадры: art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/ — открой КАЖДЫЙ файл из списка ["DrWatson-DeathSettle-blender-sheet.jpg", "DrWatson-DeathSettle-f10-q34b.jpg", "DrWatson-DeathSettle-f14-back.jpg", "DrWatson-DeathSettle-f14-q34b.jpg", "DrWatson-DeathSettle-f14-q34r.jpg", "DrWatson-DeathSettle-f14-topb.jpg", "DrWatson-DeathSettle-f16-q34bl.jpg", "DrWatson-DeathSettle-f16-q34l.jpg", "DrWatson-DeathSettle-f16-q34r.jpg", "DrWatson-DeathSettle-f16-right.jpg", "DrWatson-DeathSettle-f21-back.jpg", "DrWatson-DeathSettle-f21-left.jpg", "DrWatson-DeathSettle-f21-q34.jpg", "DrWatson-DeathSettle-f21-q34b.jpg", "DrWatson-DeathSettle-f21-q34bl.jpg", "DrWatson-DeathSettle-f21-topb.jpg", "DrWatson-DeathSettle-f00-front-ue-editor.jpg", "DrWatson-DeathSettle-f00-q34-ue-editor.jpg", "DrWatson-DeathSettle-f03-front-ue-editor.jpg", "DrWatson-DeathSettle-f03-q34-ue-editor.jpg", "DrWatson-DeathSettle-f06-front-ue-editor.jpg", "DrWatson-DeathSettle-f06-q34-ue-editor.jpg", "DrWatson-DeathSettle-f09-front-ue-editor.jpg", "DrWatson-DeathSettle-f09-q34-ue-editor.jpg", "DrWatson-DeathSettle-f12-front-ue-editor.jpg", "DrWatson-DeathSettle-f12-q34-ue-editor.jpg", "DrWatson-DeathSettle-f16-front-ue-editor.jpg", "DrWatson-DeathSettle-f16-q34-ue-editor.jpg", "DrWatson-DeathSettle-f21-front-ue-editor.jpg", "DrWatson-DeathSettle-f21-q34-ue-editor.jpg", "DrWatson-H2Anim-ue-sheet.jpg"] в полном размере (1:1):
  Blender-лист `DrWatson-DeathSettle-blender-sheet.jpg` (кадры key_frames [0, 3, 6, 9, 12, 16, 21], виды front / left / q34, кости поверх),
  крупные планы Blender (art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/preview/closeups-blender/: DrWatson-DeathSettle-f10-q34b.jpg, DrWatson-DeathSettle-f14-back.jpg, DrWatson-DeathSettle-f14-q34b.jpg, DrWatson-DeathSettle-f14-q34r.jpg, DrWatson-DeathSettle-f14-topb.jpg, DrWatson-DeathSettle-f16-q34bl.jpg, DrWatson-DeathSettle-f16-q34l.jpg, DrWatson-DeathSettle-f16-q34r.jpg, DrWatson-DeathSettle-f16-right.jpg, DrWatson-DeathSettle-f21-back.jpg, DrWatson-DeathSettle-f21-left.jpg, DrWatson-DeathSettle-f21-q34.jpg, DrWatson-DeathSettle-f21-q34b.jpg, DrWatson-DeathSettle-f21-q34bl.jpg, DrWatson-DeathSettle-f21-topb.jpg; камера каждого кадра — в
  DrWatson-DeathSettle-closeups.json). UE-кадры `DrWatson-DeathSettle-fNN-{front,q34}-ue-editor.jpg`, лист
  `DrWatson-H2Anim-ue-sheet.jpg`. Другие файлы каталога art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1 (card*.json, final.json, acceptor-*) не открывай.
- UE-кадры (`*-ue-editor.jpg`, лист `DrWatson-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` на меше-носителе `/Game/PipelineCandidates/DrWatson/Rig/SK_DrWatson` (геометрия H2 без look-dev материалов, поэтому фигура серая — так снимаются все герои библиотеки D-11) на подставке `SM_DrWatson_H2LD_Base`; цвет и материал в этой приёмке не оцениваются. Свет — закреплённый cobble-probe rev 5 (`--light-pinned ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), High, редактор: это диагностические кадры, не K1/K2. Крупные планы Blender лежат и в art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/<клип>/frames/ (копии файлов из preview/closeups-blender/).
- Клип: AM_DrWatson_DeathSettle, роль terminal, 21 к. при 24 fps (0.875 с); кадр 0 = rest, последний кадр — финальная поза, держится.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-DR-WATSON-001/build-profiles/dr-watson-h2anim.json): «удар и отшатывание (к. 3): корпус назад, голова мотнулась, револьвер вздрагивает; с к. 6 доктор клонится вперёд и чуть вправо — поклон корпусом без падения на колени (таз наклоняется до 4,5°, корпус до 20°), голова клонится вниз вместе с корпусом (к корпусу не больше 4,5°: сильнее раскрывается шея над воротом сзади); правая рука опускается (к. 6–12) и повисает перед бедром, револьвер опущен стволом вперёд-вниз (жёстко в кулаке, кость weapon.R без ключей); левая рука с саквояжем остаётся у бедра (рука отходит назад относительно склонённого корпуса), саквояж держит место у полы и не входит в неё; финальная поза держится (к. 16–21). Ноги почти прямые, таз только наклоняется и чуть опускается».
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_DrWatson_DeathSettle.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/contact-DeathSettle.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись WAT-DeathSettle, G-MANIFEST), art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/author-DeathSettle.json (ik_log), art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/grip-DeathSettle.json (машинный замер по FBX клипа): поворот weapon.R (револьвера) в кулаке ≤ 0.0° на всех кадрах, излом правого запястья ≤ 26.5°, локоть правой руки 86.3–107.7°, уход плоскости сгиба локтя ≤ 0.0°, колени не ниже 172.9°, пересечений револьвера и саквояжа с телом 0.
- WARN контактов: skin_stretch — 8 рёбер растянуты больше 3× rest (максимум 5.2×) без разрыва: видимых рваных рёбер (> 5× и > 2 % H) 0; к.9,10,11,12,13,14,15,16,17,18,19,20,21; области arm_lower.R|hand.R, arm_lower.R|arm_upper.R.
- Референс движения: образец библиотеки D-11 — спека Medusa (art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json, clips.DeathSettle: удар и отшатывание к.3, тело складывается в поясе вперёд с креном, голова падает, руки повисают, финальная поза к.16–21 — «смерть стоя», поклон корпусом) и art/animation-refs/ASSET-MEDUSA-001/MED-DeathSettle/contact-sheet-2fps.png; зеркально, револьвер в правой руке опущен; это ориентир тайминга и поз, не цель. Своего видео-референса у Ватсона нет (ДС-6, траты 0).
- Характер героя: лист концепта art/imagegen/concept-dr-watson-codex/dr-watson-front.png (и кадры модели
  art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/<цикл принятой модели>/frames/sheet.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png и art/imagegen/hero-quality-v1/merlin/. Заявка:
  Dr. Watson — помощник Sherlock Holmes, дальний бой (выстрел из револьвера, HIT_TYPE ARROW), крепкий джентльмен с
  усами в котелке, длинное коричневое пальто поверх жилета, револьвер в ПРАВОЙ руке (оружие — кость weapon.R),
  докторский саквояж в левой (жёстко на hand.L); карточка задачи AN-167
  (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale и known_issues, не в rework_fix_list и не
  ниже 1,0, если кадр не показывает видимый разрыв, дыру или отрыв части; один список на все 4 клипа):
- Револьвер — отдельный меш, жёстко на weapon.R, низ рукояти — часть меша тела на weapon.R (П3-1); кость оружия
  относительно кисти не ключуется — револьвер в кулаке не проворачивается ни в одном клипе (0°). В rest он поднят у
  плеча стволом вверх (~55°), ось ствола на 39° от оси предплечья; направление ствола задают предплечье и сгиб
  кисти без скрутки.
- Скин правой руки: в rest локоть согнут на 91°; прогон этапа 6 (2026-10-21, риг r2; на риге r3 пределы проверены повторно) показал видимые рваные рёбра при
  разгибании локтя до 116,6° и сгибе кисти 34°, поэтому в клипах локоть не больше 108°, сгиб кисти не больше 27°,
  предплечье не скручивается. Отсюда прицел — на уровне груди с отведённым вбок локтем, ствол вдоль предплечья, а
  не вытянутая рука у глаз. На сгибе локтя и у запястья возможны растянутые рёбра без разрыва (skin_stretch WARN,
  видимых рваных рёбер 0) — натяжение рукава и манжеты.
- Саквояж жёстко на hand.L (П3-2) и в rest врезан в левую полу пальто (крышки coat_bag / bag_coat этапа 3, 324 пар
  пересечения в rest): видимое касание саквояжа и полы — состояние модели в rest, не дефект клипа. Клипы держат
  саквояж на его месте у полы в осях таза со сдвигом наружу: пересечений саквояжа с телом не больше, чем в rest
  (максимум 324 пар во всех клипах).
- Ноги в rest почти прямые (длина бедра и голени длиннее расстояния таз–щиколотка на 0,02 см): таз только
  поворачивается и смещается на миллиметры, колени не ниже 172.8°, без приседа; смерть — поклон корпусом без падения
  на колени (ВР-14).
- Пальто скинено жёстко (cloth_shell без симуляции ткани): полы идут с тазом и бёдрами, рукава — стык весов рукав←пола
  (r2, в r3 оставлен 0,025 м: верх рукава в 2,5 см от проймы на весах полы), поэтому при поднятой или отведённой руке верх рукава у проймы
  тянется вслед за корпусом, а не за рукой.
- Модель: тонкая тёмная щель между шеей и верхним краем воротника спереди и светлая полоса текстуры под полями
  котелка (этап 3, приняты с моделью) — видны и в rest, клипами не меняются. Щель между затылком и воротом пальто
  сзади есть уже в rest (этап 3: изнанка крышки neck_bottom, 40 px сзади) и раскрывается при наклоне головы вперёд:
  прогон этапа 6 (риг r2) с наклоном головы 22° к корпусу в DeathSettle показал тёмный провал на виде сзади сверху (при 9° — тонкая тёмная полоса), поэтому
  голова клонится к корпусу не больше 4,5° (поклон — корпусом и тазом); видимая полоска шеи над воротом на виде сзади
  в поклоне — этот предел, не разрыв.
- Предыдущая карточка: null (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи WAT-DeathSettle в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора; D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: R — смерть читается поклоном корпуса без падения на колени (ВР-14), голова клонится вниз, револьвер опущен; C — стопы держат подставку; D — правая рука с револьвером не входит в полу пальто и бедро, запястье и сгиб локтя на крупном плане, саквояж у бедра не входит в полу, кромка ворота и котелка сзади сверху (topb) на последнем кадре; L — финальная поза держится без дрожи. В rationale назови кадры и видимый признак; frames — имена файлов из
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
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-DR-WATSON-001", clip "DeathSettle",
   date "2026-10-21", cycle "r1", previous_card null,
   accepted_object [{"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/export/AM_DrWatson_DeathSettle.fbx", "sha256": "c9053a5ed9e8ec0cb5706155b940b1d20a83730a27ecfbfa72309d2a07314c2c"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/build-profiles/dr-watson-h2anim.json", "sha256": "2fc8549daf37c6becd2aeeb1cb137437bfd2d25ae49e3cfaf7968209d7231194"}],
   frames {"dir": "art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames", "files": ["DrWatson-DeathSettle-blender-sheet.jpg", "DrWatson-DeathSettle-f10-q34b.jpg", "DrWatson-DeathSettle-f14-back.jpg", "DrWatson-DeathSettle-f14-q34b.jpg", "DrWatson-DeathSettle-f14-q34r.jpg", "DrWatson-DeathSettle-f14-topb.jpg", "DrWatson-DeathSettle-f16-q34bl.jpg", "DrWatson-DeathSettle-f16-q34l.jpg", "DrWatson-DeathSettle-f16-q34r.jpg", "DrWatson-DeathSettle-f16-right.jpg", "DrWatson-DeathSettle-f21-back.jpg", "DrWatson-DeathSettle-f21-left.jpg", "DrWatson-DeathSettle-f21-q34.jpg", "DrWatson-DeathSettle-f21-q34b.jpg", "DrWatson-DeathSettle-f21-q34bl.jpg", "DrWatson-DeathSettle-f21-topb.jpg", "DrWatson-DeathSettle-f00-front-ue-editor.jpg", "DrWatson-DeathSettle-f00-q34-ue-editor.jpg", "DrWatson-DeathSettle-f03-front-ue-editor.jpg", "DrWatson-DeathSettle-f03-q34-ue-editor.jpg", "DrWatson-DeathSettle-f06-front-ue-editor.jpg", "DrWatson-DeathSettle-f06-q34-ue-editor.jpg", "DrWatson-DeathSettle-f09-front-ue-editor.jpg", "DrWatson-DeathSettle-f09-q34-ue-editor.jpg", "DrWatson-DeathSettle-f12-front-ue-editor.jpg", "DrWatson-DeathSettle-f12-q34-ue-editor.jpg", "DrWatson-DeathSettle-f16-front-ue-editor.jpg", "DrWatson-DeathSettle-f16-q34-ue-editor.jpg", "DrWatson-DeathSettle-f21-front-ue-editor.jpg", "DrWatson-DeathSettle-f21-q34-ue-editor.jpg", "DrWatson-H2Anim-ue-sheet.jpg"]},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_DrWatson_DeathSettle.validation.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/contact-DeathSettle.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-DR-WATSON-001/20261021-h2anim-r2/reports/grip-DeathSettle.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Opus xhigh", "session_id": "workflow:acceptor-ASSET-DR-WATSON-001-DeathSettle-r1"},
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

## Изображения приёмщику
Открой каждый файл как картинку инструментом Read, каждый целиком (к промпту изображения не приложены):
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-blender-sheet.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f00-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f00-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f03-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f03-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f06-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f06-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f09-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f09-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f10-q34b.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f12-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f12-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f14-back.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f14-q34b.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f14-q34r.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f14-topb.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f16-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f16-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f16-q34bl.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f16-q34l.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f16-q34r.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f16-right.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-back.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-left.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-q34.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-q34b.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-q34bl.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-DeathSettle-f21-topb.jpg
- art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/DrWatson-H2Anim-ue-sheet.jpg
- art/animation-refs/ASSET-MEDUSA-001/MED-DeathSettle/contact-sheet-2fps.png
- art/imagegen/concept-dr-watson-codex/dr-watson-front.png
- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png
