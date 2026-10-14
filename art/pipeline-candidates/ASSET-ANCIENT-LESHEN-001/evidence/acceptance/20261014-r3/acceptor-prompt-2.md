# Приёмка модели ASSET-ANCIENT-LESHEN-001, цикл r3 (этап 4 скилла 3d-model-pipeline)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — приёмщик. Ты НЕ исполнитель: ничего не правишь, не запускаешь Blender, скрипты и validate_card.py, не пишешь
файлы. Твоя единственная выдача — JSON-карточка по схеме tools/art/acceptance/asset-acceptance-2.schema.json; файл
card.json записывает и проверяет запускающий.
Текстовые файлы читай в UTF-8 (инструмент Read; в Windows PowerShell — `Get-Content <файл> -Raw -Encoding UTF8`).
Если кириллица рубрики всё равно пришла кракозябрами — это сбой окружения: не оценивай по догадкам, верни
карточку, где verdict_reason начинается со слов «СБОЙ ОКРУЖЕНИЯ: кириллица не читается».
Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md,
разделы 3 (кадры, «полный рост» и «крупный план»), 4 (гейты), 5 (якоря и общие правила), 6 (формула и вердикт),
7 (поля карточки). Рубрика — ТОЛЬКО этот файл: SKILL.md и другие файлы скилла (.agents/skills/**, кроме
acceptance-and-blender.md) не открывай и не учитывай.

## Вход
- Кадры: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r3/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r3/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны, отчёты и предыдущую карточку ниже.
  Другие файлы каталога art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r3 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r3/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r3/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4). У этого героя оружия
  нет (WEAPON_HAND none, кости weapon.* нет): зазоры не считаются, а close-weapon.jpg снят как верхняя часть фигуры
  (frames.json#warnings) — это не дефект набора.
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-bake-r3/reports/ и art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/reports/ (только JSON из §4 рубрики).
  TeamAccent снят в том же look-dev прогоне: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/reports/ld-team-accent-report.json
  (отдельного прогона TeamAccent нет).
- Рост и рога (действующее решение пилота, записано в заявке asset-card.yaml, поле decided_by_stage3.FIGURE_HEIGHT_M):
  бюджет роста героя HANDBOOK §2.10 (55 uu) у этого героя — верх ЧЕРЕПА, а кончики рогов выше — верх габарита
  (bounds), как меч Arthur над короной. Поэтому в G-NAMES п.(5) «высота фигуры = бюджет роли ± 1 %» сверяется верх
  черепа: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-bake-r3/reports/prepare-report.json#parts.tripo_part_9.final_bounds_m
  (часть 9 — череп оленя: bake-профиль #parts.tripo_part_9.role = «череп оленя (голова)»; максимум z = 0,55003 м);
  а rig-report.json#checks.unit_scale_1_and_height (measured.skeletal_top_cm = expected) и bake-профиль
  #scale.figure_top_m 0,7356 — это верх рогов (верх габарита, справочно), их с бюджетом 55 uu не сравнивай.
  В S рост тоже меряется по направляющим compare-* (они идут от низа подставки до кончиков рогов, как на листе).
- Ноги (факт листа и рига, без оценки): на листе у фигуры нет раздельных ног — ниже пояса единый ствол из корней до
  подставки (известное замечание листа: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance-concept/20261013-sheet-r1/card-2.json#known_issues,
  item S). Кости ног контракта лежат внутри ствола (rig-report.json и bake-профиль #rig.bones). Зона §3 «ноги и низ
  одежды» у этой фигуры — ствол ниже пояса и корни (close-legs, close-legs-back). Позы проб — фиксированные углы
  тестов (§5.4); как оценивать то, что ими движется, решает рубрика §5.4.
- Заявка: роль hero; якоря (поле ANCHORS_EN заявки — это ANCHORS): deer skull head with large antlers; body of twisted
  roots; long clawed arms; crows; палитра main: bark brown #5A4030, bone #D9CFB8, moss green #4E5A36; accent: crow
  black #141414; оружие в none (WEAPON_HAND none, WEAPON_BONE null: скелет 16 костей по контракту героя без оружия);
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_AncientLeshen_H2LD", "base": "SM_AncientLeshen_H2LD_Base", "textures": ["T_AncientLeshen_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_AncientLeshen_H2LD_Edge", "T_UM_MatLUT_AncientLeshen"]} (отгружаемые файлы текстур — 2K: T_AncientLeshen_H2LD_2K_{BC,N,ORM,MatID,Edge}.png, T_AncientLeshen_H2LD_TeamAccent_2K.png; MatLUT — T_UM_MatLUT_AncientLeshen.dds); bake-профиль art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2-bake-h2-r3.json (meshes, materials.atlas).
- Предыдущая карточка: art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r2/card.json (цикл r2, verdict pass, score 8,1, rework_fix_list пуст). Баллы ставь заново по свежим кадрам r3 (§2.3 п.5 рубрики).

## Изменение r3
Изменение модели между r2 и r3: «r3: правая ворона посажена на предплечье».
У карточки r2 есть known_issues с item F и frame turn-225.jpg (вороны на предплечьях). Проверь его сам по свежим
кадрам r3 и запиши в scores.F.rationale «r2 known_issues F turn-225: закрыт» или «r2 known_issues F turn-225: не
закрыт — <что видно, кадр>».

## Порядок
1. Гейты G-TOPO, G-UV, G-TEX, G-RIG, G-NAMES — только по отчётам, по таблице §4 (G-TOPO решает ld-fbx-report).
   Нет отчёта или ключа = FAIL; где ключ лежит для каждой карты G-TEX (N — в bake-отчёте через мост pins,
   TeamAccent — в ld-team-accent-report), сказано в строке G-TEX и в «Уточнениях» §4. Запись гейта: {"status": ..., "source": "<путь от корня к решающему отчёту, без #>",
   "note": "<файл#ключ = значение; ...>"}. Если гейт FAIL из-за дефекта исходника Tripo (нет части, фантом,
   слитые части) — добавь "source_defect": true и опиши дефект в note. Других ключей у гейта нет.
2. Баллы S, F, T, D — только по кадрам, по якорям §5 и общим правилам §5 п.1–9 (шаг 0,5; видны признаки и верхнего,
   и нижнего якоря — нижний; сомнение в опознании — якорь, все признаки которого видны точно, сомнение — в
   known_issues). Порядок для каждого признака: дефект ли это (нет на листе в этом месте; пропорции — по виду front
   листа) → измерение (S / F геометрия, след на wire-* / T без следа на wire-* / D только деформация; закрытие контакта,
   открытое позой пробы, — F только крупного плана) → где виден (полный рост = на turn-* или pose-* 1:1 дефект узнаётся
   сам и больше 8 px или меняет силуэт; иначе только крупный план) → зона (§3, границы по телу). Считай зоны, а не
   кадры: F и T — только крупный план 1,5; полный рост в одной зоне 1,0; в двух и более зонах 0,5. S — только контур,
   пропорции (пороги в % роста; размер подставки не сравнивается), якоря и основные пятна цвета (термины §5.1);
   орнамент и детализация — только T. D — по контуру позы (§5.4). T не выше tone.json#t_cap.
   Для пропа D = {"value": null, "rationale": "проп без рига", "frames": []}. В rationale назови кадры, зону и
   видимый признак; frames — имена файлов из frames.files.
3. score = round(sum / (2 × n) × 10, 1) с округлением half-up (6,25 → 6,3; НЕ round() Python), как в
   validate_card.py. Вердикт — первое сработавшее правило таблицы §6 (cycle = r3; на r3 любой не-pass =
   escalate_user). При любом вердикте, кроме pass, заполни verdict_reason (≥ 10 символов): какое правило сработало,
   при return — 1а (S = 0, другой персонаж: какие якоря листа отсутствуют) или 1б (есть ли дефект на листе в том же
   месте: да — этап 1, нет — этап 2), при escalate_user — какой маршрут дали бы правила 1–4.
4. rework_fix_list — при возврате по S (правило 1) пустой [], замечания F, T, D ниже 2 — в known_issues.
   Иначе только F, T, D ниже 2 и FAIL-гейты (S никогда: в Blender не правится); пункт строго
   {"item": "F"|"T"|"D"|"G-…", "frame": "<имя кадра>", "fix": "<что исправить и где на кадре>",
   "tool": "<ключ профиля или стадия run_h2_bake.py по §9.3 рубрики>"}, других ключей нет. При rework_blender список
   покрывает каждый FAIL-гейт, каждое измерение < 1,0, а при score < 8,0 — каждое из F, T, D ниже 2. При pass — [].
5. known_issues — замечания, которые балл не снижают или уже учтены, но должны дойти до доработки и этапа 7
   (классы floor из tone.json, справочные числа отчётов, мелочи на close-* при pass, касание оружия в позах —
   pose_checks.*_contact, тон без tone.json, F/T/D при возврате по S):
   [{"item": "S"|"F"|"T"|"D"|"G-…", "frame": "<имя из frames.files>", "note": "<что видно>"}]; можно [].
   `item` — только `S`, `F`, `T`, `D` (модель) или id гейта (`G-TOPO`, `G-UV`, `G-TEX`, `G-RIG`, `G-NAMES`) — никакого
   свободного текста; пустое поле — JSON `null`, не строка "null". Лучше вовсе не писать необязательное поле: при
   pass нет ключа verdict_reason, у гейта без дефекта исходника нет ключа source_defect.
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-ANCIENT-LESHEN-001", date "2026-10-14",
   cycle "r3", previous_card "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r2/card.json", accepted_object [{"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/export/SK_AncientLeshen_H2LD.fbx", "sha256": "9ce406cfed6f9cbdfbc7c182c87c22dec7f7d387c0f91bbb4a5b9ef8c5993b1e"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/export/SM_AncientLeshen_H2LD_Base.fbx", "sha256": "8536bb8acac8eb27f4aaba6ea6d006b80c934f4bee0f59e0cf3c9768deacaf35"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/textures/T_AncientLeshen_H2LD_2K_BC.png", "sha256": "4a9e8c707d39fdc9be64ba98d409884045ac8006c562507ccaec032190648ce5"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/textures/T_AncientLeshen_H2LD_2K_N.png", "sha256": "3a204ce36a7117aacf3604114d7d18b7c14698fabcd188c80df1e9bda2864a3f"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/textures/T_AncientLeshen_H2LD_2K_ORM.png", "sha256": "070753eb9b9119f4023506c78acbf6b7cc6d07d179777cb45ad067fbd7d2a1dd"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/textures/T_AncientLeshen_H2LD_2K_MatID.png", "sha256": "9271d8deec305761d9a1af877c05b675c6f6ed249051c94d5f9a8b124737d4a0"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/textures/T_AncientLeshen_H2LD_2K_Edge.png", "sha256": "64eb67323aa1f4f59feee1947b0a97ca2cd83f46bf321b429ea81b929de19014"}, {"path": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-lookdev-r3/textures/T_AncientLeshen_H2LD_TeamAccent_2K.png", "sha256": "10c3d3059f1c961277e5fb2c87e779db3084ddc6f9da9994cc06e3abc6e2cf59"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r3/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Opus xhigh", "session_id": "workflow:acceptor2-ASSET-ANCIENT-LESHEN-001-r3"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage6r2-leshen", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» и в «Изменении r3» (чат, git log, отчёты исполнителя в
  свободной форме, другие карточки этого цикла, файлы скилла кроме рубрики).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
