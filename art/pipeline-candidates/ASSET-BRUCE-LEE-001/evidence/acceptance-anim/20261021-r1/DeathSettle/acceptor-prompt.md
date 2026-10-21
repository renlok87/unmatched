# Приёмка клипа AM_BruceLee_DeathSettle, цикл r1 (шаг 7a.2)

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
- Кадры: art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/ — открой КАЖДЫЙ файл из списка ["BruceLee-DeathSettle-blender-sheet.jpg", "BruceLee-DeathSettle-f10-q34b.jpg", "BruceLee-DeathSettle-f13-q34.jpg", "BruceLee-DeathSettle-f15-q34bl.jpg", "BruceLee-DeathSettle-f16-back.jpg", "BruceLee-DeathSettle-f16-q34b.jpg", "BruceLee-DeathSettle-f16-topb.jpg", "BruceLee-DeathSettle-f17-front-b.jpg", "BruceLee-DeathSettle-f17-front.jpg", "BruceLee-DeathSettle-f17-left-b.jpg", "BruceLee-DeathSettle-f17-left.jpg", "BruceLee-DeathSettle-f17-top34.jpg", "BruceLee-DeathSettle-f21-back.jpg", "BruceLee-DeathSettle-f21-q34.jpg", "BruceLee-DeathSettle-f21-q34b.jpg", "BruceLee-DeathSettle-f21-q34bl.jpg", "BruceLee-DeathSettle-f21-topb.jpg", "BruceLee-DeathSettle-f00-front-ue-editor.jpg", "BruceLee-DeathSettle-f00-q34-ue-editor.jpg", "BruceLee-DeathSettle-f03-front-ue-editor.jpg", "BruceLee-DeathSettle-f03-q34-ue-editor.jpg", "BruceLee-DeathSettle-f08-front-ue-editor.jpg", "BruceLee-DeathSettle-f08-q34-ue-editor.jpg", "BruceLee-DeathSettle-f13-front-ue-editor.jpg", "BruceLee-DeathSettle-f13-q34-ue-editor.jpg", "BruceLee-DeathSettle-f17-front-ue-editor.jpg", "BruceLee-DeathSettle-f17-q34-ue-editor.jpg", "BruceLee-DeathSettle-f21-front-ue-editor.jpg", "BruceLee-DeathSettle-f21-q34-ue-editor.jpg", "BruceLee-H2Anim-ue-sheet.jpg"] в полном размере (1:1):
  Blender-лист `BruceLee-DeathSettle-blender-sheet.jpg` (кадры key_frames [0, 3, 8, 13, 17, 21], виды front / left / q34, кости поверх),
  крупные планы Blender (art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/preview/closeups-blender/: BruceLee-DeathSettle-f10-q34b.jpg, BruceLee-DeathSettle-f13-q34.jpg, BruceLee-DeathSettle-f15-q34bl.jpg, BruceLee-DeathSettle-f16-back.jpg, BruceLee-DeathSettle-f16-q34b.jpg, BruceLee-DeathSettle-f16-topb.jpg, BruceLee-DeathSettle-f17-front-b.jpg, BruceLee-DeathSettle-f17-front.jpg, BruceLee-DeathSettle-f17-left-b.jpg, BruceLee-DeathSettle-f17-left.jpg, BruceLee-DeathSettle-f17-top34.jpg, BruceLee-DeathSettle-f21-back.jpg, BruceLee-DeathSettle-f21-q34.jpg, BruceLee-DeathSettle-f21-q34b.jpg, BruceLee-DeathSettle-f21-q34bl.jpg, BruceLee-DeathSettle-f21-topb.jpg; камера каждого кадра — в
  BruceLee-DeathSettle-closeups.json). UE-кадры `BruceLee-DeathSettle-fNN-{front,q34}-ue-editor.jpg`, лист
  `BruceLee-H2Anim-ue-sheet.jpg`. Другие файлы каталога art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1 (card*.json, final.json, acceptor-*) не открывай.
- UE-кадры (`*-ue-editor.jpg`, лист `BruceLee-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` на меше-носителе `/Game/PipelineCandidates/BruceLee/Rig/SK_BruceLee` (геометрия H2 без look-dev материалов, поэтому фигура серая — так снимаются все герои библиотеки D-11) на подставке `SM_BruceLee_H2LD_Base`; цвет и материал в этой приёмке не оцениваются. Свет — закреплённый cobble-probe rev 5 (`--light-pinned art/pipeline-candidates/ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), High, редактор: это диагностические кадры, не K1/K2. Крупные планы Blender лежат и в art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/<клип>/frames/ (копии файлов из preview/closeups-blender/).
- Клип: AM_BruceLee_DeathSettle, роль terminal, 21 к. при 24 fps (0.875 с); кадр 0 = rest, последний кадр держится.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2anim.json): «удар и отшатывание назад, кисти взлетают (к. 3); стойка рассыпается: корпус складывается вперёд (таз 6° + корпус 24,5°) с лёгким креном вправо, колени подгибаются (таз −0,6 см, чуть назад), голова падает на грудь (к. 8–17), пустые руки безвольно повисают вниз и чуть вперёд-наружу, локти мягко согнуты; финальная поза держится до растворения (к. 17–21 почти одинаковы). Без падения на колени (ВР-14), стопы на месте».
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_BruceLee_DeathSettle.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/contact-DeathSettle.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись BRUC-DeathSettle, G-MANIFEST), art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/author-DeathSettle.json (журнал автора; ноги — aim-ключи каждого кадра, IK стоп инструмента выключен, ik_unreached_frames пуст).
  Оружия нет: grip-отчёта нет.
- WARN контактов: нет (все проверки контактов PASS или info).
- Референс движения: образец библиотеки D-11 — спека Ancient Leshen r3 (art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2anim-r3.json, clips.DeathSettle: поклон корпусом без падения на колени, пустые руки повисают) ← Medusa DeathSettle; art/animation-refs/ASSET-MEDUSA-001/MED-DeathSettle/contact-sheet-2fps.png. Своего видео-референса у Bruce Lee нет (ДС-6: паттерн библиотеки); это ориентир
  тайминга и поз, не цель.
- Характер героя: лист концепта art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3/frames/sheet.png (и
  art/imagegen/concept-bruce-lee-codex/bruce-lee-front.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Bruce Lee — герой ближнего боя без оружия, правосторонняя стойка Jeet Kune Do: обе кисти подняты «когтями» перед грудью, правая (передняя) впереди; жёлтый комбинезон с чёрными лампасами, чёрные туфли; карточка задачи AN-159
  (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale и known_issues, не в rework_fix_list и не
  ниже 1,0, если кадр не показывает видимый разрыв, дыру или отрыв части; один список на все 4 клипа):
- Ноги в rest прямые и широко расставлены (цепь бедро–голень 17,67/17,66 см при расстоянии таз–лодыжка 17,63/17,60 см, запас 0,05 см), колено rest на 0,5 см позади линии бедро–лодыжка. Поэтому таз только опускается (0,25–0,62 см) и колени лишь подгибаются (не ниже 146°); подъёма таза и шага нет. Ноги авторены aim-ключами каждого кадра (IK стоп инструмента выключен: его плоскость колена на этом риге скручивала бедро и голень), стопы держат rest-поворот, скольжение подошв ≤ 0,13 % H во всех клипах.
- Кисти — неподвижные «когти» модели (костей пальцев в риге нет): удар идёт раскрытой кистью-«когтем», кулак не сжимается; это форма модели, а не клипа.
- Тонкие тёмные щели по швам рукавов у плеча и у ворота сзади (кромки частей Tripo) видны уже около rest (Idle к.13, topb) и в клипах не растут.
- Открытая кромка манжет рукавов: при отсечении задних граней сзади видна рваная изнанка манжеты (HitReact к.2, q34b) — геометрия модели.
- Засветка кончиков ногтей правой кисти и рельеф канта лампасов — текстура и форма исходника (этапы 3/5); цвет и материал в приёмке клипа не оцениваются.
- Предыдущая карточка: null (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи BRUC-DeathSettle в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора; D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: C — опора: стопы держат подставку, без падения на колени (ВР-14), колени лишь подгибаются; L — финальная поза к.17–21 держится без дрожи; R — стойка рассыпается в поклон, голова падает, пустые руки повисают; D — пах и ягодицы сзади при наклоне таза (крупный план left @hips к.17), плечи и ворот сзади сверху на к.21. В rationale назови кадры и видимый признак; frames — имена файлов из
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
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-BRUCE-LEE-001", clip "DeathSettle",
   date "2026-10-21", cycle "r1", previous_card null,
   accepted_object [{"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/export/AM_BruceLee_DeathSettle.fbx", "sha256": "ed8a1f226c75b44ed9ea811dd3a3bd5eb3bf1b926faf3610112980cbe82f27da"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2anim.json", "sha256": "f569f090b7d07a782756408e764ff97a03cb50e75c665a8661851985d35997f1"}],
   frames {"dir": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames", "files": ["BruceLee-DeathSettle-blender-sheet.jpg", "BruceLee-DeathSettle-f10-q34b.jpg", "BruceLee-DeathSettle-f13-q34.jpg", "BruceLee-DeathSettle-f15-q34bl.jpg", "BruceLee-DeathSettle-f16-back.jpg", "BruceLee-DeathSettle-f16-q34b.jpg", "BruceLee-DeathSettle-f16-topb.jpg", "BruceLee-DeathSettle-f17-front-b.jpg", "BruceLee-DeathSettle-f17-front.jpg", "BruceLee-DeathSettle-f17-left-b.jpg", "BruceLee-DeathSettle-f17-left.jpg", "BruceLee-DeathSettle-f17-top34.jpg", "BruceLee-DeathSettle-f21-back.jpg", "BruceLee-DeathSettle-f21-q34.jpg", "BruceLee-DeathSettle-f21-q34b.jpg", "BruceLee-DeathSettle-f21-q34bl.jpg", "BruceLee-DeathSettle-f21-topb.jpg", "BruceLee-DeathSettle-f00-front-ue-editor.jpg", "BruceLee-DeathSettle-f00-q34-ue-editor.jpg", "BruceLee-DeathSettle-f03-front-ue-editor.jpg", "BruceLee-DeathSettle-f03-q34-ue-editor.jpg", "BruceLee-DeathSettle-f08-front-ue-editor.jpg", "BruceLee-DeathSettle-f08-q34-ue-editor.jpg", "BruceLee-DeathSettle-f13-front-ue-editor.jpg", "BruceLee-DeathSettle-f13-q34-ue-editor.jpg", "BruceLee-DeathSettle-f17-front-ue-editor.jpg", "BruceLee-DeathSettle-f17-q34-ue-editor.jpg", "BruceLee-DeathSettle-f21-front-ue-editor.jpg", "BruceLee-DeathSettle-f21-q34-ue-editor.jpg", "BruceLee-H2Anim-ue-sheet.jpg"]},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_BruceLee_DeathSettle.validation.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/contact-DeathSettle.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2anim/reports/author-DeathSettle.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Opus xhigh", "session_id": "workflow:acceptor-ASSET-BRUCE-LEE-001-DeathSettle-r1"},
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

## Изображения приёмщику
Открой каждый файл как картинку инструментом Read, каждый целиком (к промпту изображения не приложены):
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-blender-sheet.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f00-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f00-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f03-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f03-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f08-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f08-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f10-q34b.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f13-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f13-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f13-q34.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f15-q34bl.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f16-back.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f16-q34b.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f16-topb.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f17-front-b.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f17-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f17-front.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f17-left-b.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f17-left.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f17-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f17-top34.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f21-back.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f21-front-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f21-q34-ue-editor.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f21-q34.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f21-q34b.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f21-q34bl.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-DeathSettle-f21-topb.jpg
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance-anim/20261021-r1/DeathSettle/frames/BruceLee-H2Anim-ue-sheet.jpg
- art/animation-refs/ASSET-MEDUSA-001/MED-DeathSettle/contact-sheet-2fps.png
- art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3/frames/sheet.png
- art/imagegen/concept-bruce-lee-codex/bruce-lee-front.png
- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png
