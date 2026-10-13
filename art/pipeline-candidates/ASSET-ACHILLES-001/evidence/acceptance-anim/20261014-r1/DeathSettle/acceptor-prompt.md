# Приёмка клипа AM_Achilles_DeathSettle, цикл r1 (этап 6 скилла 3d-model-pipeline)

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
- Кадры: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r1/DeathSettle/frames/ — открой КАЖДЫЙ файл из списка ["Achilles-DeathSettle-blender-sheet.jpg", "Achilles-DeathSettle-f13-left.jpg", "Achilles-DeathSettle-f21-back.jpg", "Achilles-DeathSettle-f21-front.jpg", "Achilles-DeathSettle-f21-q34.jpg", "Achilles-DeathSettle-f21-q34b.jpg", "Achilles-DeathSettle-f21-q34r.jpg", "Achilles-DeathSettle-f21-right.jpg", "Achilles-DeathSettle-f00-front-ue-editor.jpg", "Achilles-DeathSettle-f00-q34-ue-editor.jpg", "Achilles-DeathSettle-f03-front-ue-editor.jpg", "Achilles-DeathSettle-f03-q34-ue-editor.jpg", "Achilles-DeathSettle-f07-front-ue-editor.jpg", "Achilles-DeathSettle-f07-q34-ue-editor.jpg", "Achilles-DeathSettle-f11-front-ue-editor.jpg", "Achilles-DeathSettle-f11-q34-ue-editor.jpg", "Achilles-DeathSettle-f14-front-ue-editor.jpg", "Achilles-DeathSettle-f14-q34-ue-editor.jpg", "Achilles-DeathSettle-f17-front-ue-editor.jpg", "Achilles-DeathSettle-f17-q34-ue-editor.jpg", "Achilles-DeathSettle-f21-front-ue-editor.jpg", "Achilles-DeathSettle-f21-q34-ue-editor.jpg", "Achilles-H2Anim-ue-sheet.jpg"] в полном размере (1:1):
  Blender-лист `Achilles-DeathSettle-blender-sheet.jpg` (кадры key_frames [0, 3, 7, 11, 14, 17, 21], виды front / left / q34, кости
  поверх), крупные планы Blender (art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/preview/closeups-blender/: Achilles-DeathSettle-f21-front.jpg, -f21-q34r.jpg, -f21-right.jpg (хват и опорная рука в финале), -f21-back.jpg (ноги и плащ сзади), -f21-q34.jpg и -f13-left.jpg (вся фигура), -f21-q34b.jpg (кромка плаща у правой подмышки — известный предел)), UE-кадры `Achilles-DeathSettle-fNN-{front,q34}-ue-editor.jpg`, лист
  `Achilles-H2Anim-ue-sheet.jpg`. Другие файлы каталога art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r1 (card*.json, final.json, acceptor-*) не открывай.
- UE-кадры (`*-ue-editor.jpg`, лист `Achilles-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` на меше-носителе `/Game/PipelineCandidates/Achilles/Rig/SK_Achilles` (геометрия H2 без look-dev материалов, поэтому фигура серая — так снимаются все герои библиотеки D-11) на подставке `SM_Achilles_H2LD_Base` (её MI по умолчанию — команда P1, поэтому борт подставки жёлтый); цвет и материал в этой приёмке не оцениваются. Свет — закреплённый cobble-probe rev 5 (`--light-pinned ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), High, редактор: это диагностические кадры, не K1/K2. Крупные планы Blender лежат и в art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r1/<клип>/frames/ (копии файлов из preview/closeups-blender/).
- Клип: AM_Achilles_DeathSettle, роль terminal, 21 к. при 24 fps (0.875 с); кадр 0 = rest.
  Замысел (design клипа в спеке art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim.json):
  «удар и отшатывание (к. 3, копьё качнулось назад вокруг пятки); затем Achilles оседает на копьё: колени подгибаются (таз −0,55 см, без падения на колени), корпус клонится вперёд на 22° и вправо на 8° к копью, голова повисает на 27° (к. 11–21); копьё остаётся пяткой на подставке и под весом уходит наконечником вперёд-вправо на 12,5° (наклон вокруг пятки), правая рука почти прямая и держит его (локоть 127–129° на к. 14–21: линия плечо–локоть–кисть — опора), кисть с копьём не проворачивается (weapon.R без ключей, излом запястья ≤ 19°); левая рука со щитом опускается и разгибается (локоть 143° → 154°) без касания бедра; финальная поза держится без дрожи (к. 17–21 почти одинаковы)».
- Отчёты: docs/art-pipeline/animation-library/validation-h2anim/AM_Achilles_DeathSettle.validation.json (G-VALIDATE), art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/contact-DeathSettle.json (G-CONTACT), docs/art-pipeline/animation-library/clip-manifest.json
  (запись ACH-DeathSettle, G-MANIFEST), art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/ue-import-clips.json и ue-measure-clips.json (UE-импорт и замер),
  art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/author-DeathSettle.json (ik_log), art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/grip-DeathSettle.json (своя проверка исполнителя, по FBX клипа): поворот weapon.R в кулаке ≤ 0.00° на всех кадрах, щит относительно предплечья ≤ 0.000 см, кисть щита (hand.L) к предплечью 0.00°, излом правого запястья ≤ 18.6°, локоть правой руки 97–129°, пятка копья в подставку не уходит (≤ 0.10 см при rest 0,06), пересечений копья и щита с телом 0.
- WARN контактов: skin_stretch — рёбра только в закрытых местах (видимых рваных рёбер 0), подол плаща у щиколоток и щиколотки при сгибе колен.
- Референс движения: образец библиотеки D-11 — art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-DeathSettle/contact-sheet-2fps.png (King Arthur: наклон к оружию, опора правой рукой, поклон без падения на колени) и art/animation-refs/ASSET-MERLIN-001/MER-DeathSettle/contact-sheet-2fps.png (Merlin: кисть держит посох-опору на подставке). Своего видео-референса у Achilles нет (решение
  оркестратора 2026-10-14: «No SYNTX spend … author from library patterns»); это ориентир тайминга и поз, не цель.
- Характер героя: лист концепта art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames/sheet.png (и art/imagegen/concept-achilles-codex/achilles-front.png), эталон качества
  art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png. Заявка: Achilles — герой ближнего боя, копьё
  вертикально в ПРАВОЙ руке пяткой на подставке, круглый бронзовый щит на ЛЕВОМ предплечье, красный плащ, шлем с
  гребнем; карточка задачи AN-144 (docs/game-design/visual/06-tasks/anim.csv).
- Известные пределы этой фигуры (учитываются как ограничение — в rationale, не в rework_fix_list, если кадр не показывает видимый разрыв): копьё из двух частей Tripo — наконечник с верхом древка (меш оружия) и низ древка с пяткой (часть меша тела, 100 % на weapon.R), обе жёстко на кости оружия; щит без своей кости — 100 % на arm_lower.L, кисть hand.L ключей не имеет, поэтому хват ручки щита не смещается; ноги в rest прямые (колено 177°), любое смещение таза идёт с опусканием 0,1–0,55 см, отсюда небольшой сгиб колен в выпаде, отдаче и смерти (колено ≥ 149°, подъём бедра ≤ 16° против 35° в pose-04 этапа 4: крышка контакта плаща за голенью не открывается); у правой подмышки сзади кромка плаща (стык частей рука/плащ, вырез плаща по кирасе этапа 3) при выносе правой руки вперёд открывается рваной полоской (LungeAttack к.4–10, DeathSettle к.7–21; виды сзади-справа -q34b/-right) — это кромка модели, а не растяжение клипом (skin_stretch: видимых рваных рёбер 0); виды front/q34 её не показывают; при строго фронтальном взгляде колющее копьё сокращается — укол читается с боков и с q34.
- Предыдущая карточка: null (null на r1). Если она есть — по каждому пункту её
  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не закрыт» с кадром;
  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.

## Порядок
1. Гейты G-VALIDATE, G-CONTACT, G-MANIFEST — только по отчётам, по таблице §10.2: validate и contact — `result`
   = pass; G-MANIFEST — у записи ACH-DeathSettle в clip-manifest.json `status` = technically_imported (validate PASS,
   контакты PASS и UE-импорт с тем же sha256 FBX). Нет отчёта или ключа = FAIL. Запись гейта: {"status": ...,
   "source": "<путь от корня к решающему отчёту, без #>", "note": "<файл#ключ = значение; ...>", "source_defect":
   null}. Других ключей у гейта нет; "n/a" для kind anim не допускается.
2. Баллы R, C, D, L (0–2, шаг 0,5) — только по кадрам, по якорям §10.4 (видны признаки и верхнего, и нижнего
   якоря — нижний). R — читаемость и тайминг с front и q34, характер героя, спиной к камере нет (ВР-06); C — контакт
   и опора (стопы, пятка копья и подставка); D — деформация на пике амплитуды на крупном плане; L — оседание и цикл.
   Для этого клипа особенно: C — опора: пятка копья стоит на подставке, корпус висит на почти прямой правой руке (локоть ≈ 127–129° на к.14–21), стопы на месте, без падения на колени; L — финальная поза держится без дрожи; R — поза читается как оседание (поклон, голова повисла), а не как HitReact. В rationale назови кадры и видимый признак; frames — имена файлов из
   frames.files.
3. score = round((R + C + D + L) / 8 × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт по §10.5: любой гейт FAIL, любое измерение < 1,0 или score < 8,0 → rework_blender;
   иначе pass; на r3 любой не-pass → escalate_user. При любом вердикте, кроме pass, заполни verdict_reason
   (≥ 10 символов): какое правило сработало.
4. rework_fix_list — при pass []. При rework_blender список покрывает каждый FAIL-гейт и каждое измерение < 1,0;
   пункт строго {"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и на каком кадре
   клипа>", "tool": "<ключ спеки clips.DeathSettle: keys | waves | key_frames | ik_feet | hand_follow | template |
   amplitude_scale; или «h2_bake профиль (веса), этап 5 модели»; для G-MANIFEST — «этап 7: h2anim_ue.py import +
   clip_manifest.py build»>"}, других ключей нет. Длину клипа, fps и кадр контакта не предлагать менять (§10.6).
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до этапа 7 (лист K1/K2):
   [{"item": "R"|"C"|"D"|"L"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
6. Константы: schema "unmatched.anim-acceptance/1", kind "anim", asset_id "ASSET-ACHILLES-001", clip "DeathSettle",
   date "2026-10-14", cycle "r1", previous_card null,
   accepted_object [{"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/export/AM_Achilles_DeathSettle.fbx", "sha256": "d2294ca0b4062c00fd9eac0b90ef5891049caa0861b4bfa9cf927953a8317bf9"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim.json", "sha256": "6ffd8436fbb1490a14a53f7c3771a2ffce4c6cc30906a7a66767b2b92e1b78ef"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r1/DeathSettle/frames", "files": ["Achilles-DeathSettle-blender-sheet.jpg", "Achilles-DeathSettle-f13-left.jpg", "Achilles-DeathSettle-f21-back.jpg", "Achilles-DeathSettle-f21-front.jpg", "Achilles-DeathSettle-f21-q34.jpg", "Achilles-DeathSettle-f21-q34b.jpg", "Achilles-DeathSettle-f21-q34r.jpg", "Achilles-DeathSettle-f21-right.jpg", "Achilles-DeathSettle-f00-front-ue-editor.jpg", "Achilles-DeathSettle-f00-q34-ue-editor.jpg", "Achilles-DeathSettle-f03-front-ue-editor.jpg", "Achilles-DeathSettle-f03-q34-ue-editor.jpg", "Achilles-DeathSettle-f07-front-ue-editor.jpg", "Achilles-DeathSettle-f07-q34-ue-editor.jpg", "Achilles-DeathSettle-f11-front-ue-editor.jpg", "Achilles-DeathSettle-f11-q34-ue-editor.jpg", "Achilles-DeathSettle-f14-front-ue-editor.jpg", "Achilles-DeathSettle-f14-q34-ue-editor.jpg", "Achilles-DeathSettle-f17-front-ue-editor.jpg", "Achilles-DeathSettle-f17-q34-ue-editor.jpg", "Achilles-DeathSettle-f21-front-ue-editor.jpg", "Achilles-DeathSettle-f21-q34-ue-editor.jpg", "Achilles-H2Anim-ue-sheet.jpg"]},
   reports ["docs/art-pipeline/animation-library/validation-h2anim/AM_Achilles_DeathSettle.validation.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/contact-DeathSettle.json", "docs/art-pipeline/animation-library/clip-manifest.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/ue-import-clips.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/ue-measure-clips.json", "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2anim/reports/grip-DeathSettle.json"] (только те, что существуют, плюс другие из note гейтов),
   acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage6-achilles",
   decided_by "delegated (ВР-реестр 2026-10-06)". При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
