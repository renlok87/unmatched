# Приёмка модели ASSET-DR-WATSON-001, цикл r2 (этап 4 скилла 3d-model-pipeline)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — приёмщик. Ты НЕ исполнитель: ничего не правишь, не запускаешь Blender, скрипты и validate_card.py, не пишешь
файлы. Твоя единственная выдача — JSON-карточка по схеме tools/art/acceptance/asset-acceptance-2.schema.json; файл
card.json записывает и проверяет запускающий.
Текстовые файлы читай так, чтобы кириллица дошла целой. В песочнице codex PowerShell работает в Constrained
Language Mode и пишет вывод в OEM-кодировке: `Get-Content -Encoding UTF8` даёт кракозябры, смена
`[Console]::OutputEncoding` запрещена, `rg` нет. Рабочие способы (проверено пробой 2026-10-13): читай КАЖДЫЙ
текстовый файл (рубрику, JSON-отчёты, frames.json, tone.json, предыдущую карточку) командой
`Get-Content <файл> -Raw -Encoding OEM` (байты UTF-8 проходят без перекодировки и читаются верно) или
`cmd /c type <файл>`. Кодовые точки (`[int[]][char[]]`) не нужны. Если кириллица рубрики всё равно пришла
кракозябрами — это сбой окружения: не оценивай по догадкам, верни карточку, где verdict_reason начинается со слов
«СБОЙ ОКРУЖЕНИЯ: кириллица не читается».
Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md,
разделы 3 (кадры, «полный рост» и «крупный план»), 4 (гейты), 5 (якоря и общие правила), 6 (формула и вердикт),
7 (поля карточки). Рубрика — ТОЛЬКО этот файл: SKILL.md и другие файлы скилла (.agents/skills/**, кроме
acceptance-and-blender.md) не открывай и не учитывай.

## Вход
- Кадры: art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r2/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r2/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны, отчёты и предыдущую карточку ниже.
  Другие файлы каталога art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r2 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r2/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r2/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-bake-r2/reports/ и art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/reports/ (только JSON из §4 рубрики).
- TeamAccent снят в том же look-dev прогоне: art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/reports/ld-team-accent-report.json — для строки G-TEX «TeamAccent_2K» решает этот отчёт (его outputs.T_DrWatson_H2LD_TeamAccent_2K.png.sha256 = sha256 принимаемой карты art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/textures/T_DrWatson_H2LD_TeamAccent_2K.png).
- Рост для G-NAMES п.(5) — верх ТЕЛА без оружия: art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/reports/ld-fbx-report.json#roundtrip.ld.skeletal.meshes.SK_DrWatson_H2_Body.bounds_m.max[2] = 0.45004 м против FIGURE_HEIGHT_M заявки 0.45 м ± 1 %; рост не задают другие меши (оружие): SK_DrWatson_H2_Revolver bounds_m.max[2] = 0.39568 м; art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-bake-r2/reports/rig-report.json#checks.unit_scale_1_and_height.measured.skeletal_top_cm = 45.004 — верх всей фигуры с оружием, справка.
- Заявка: роль hero; якоря revolver in the figure's own RIGHT hand; medical bag in the LEFT hand; bowler hat; thick moustache; палитра main: coat brown #5E4532, bowler black #1F1E1E, waistcoat tan #A08262; accent: watch chain gold #C9A24A; оружие в right;
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_DrWatson_H2LD", "base": "SM_DrWatson_H2LD_Base", "materials": ["MI_DrWatson_H2LD", "MI_DrWatson_H2LD_Base", "MI_DrWatson_H2LD_P1", "MI_DrWatson_H2LD_P2", "MI_DrWatson_H2LD_Base_P1", "MI_DrWatson_H2LD_Base_P2"], "dissolve": "/Game/UM/Materials/v2/Dissolve/MI_DrWatson_H2LD_{P1,P2}_Dissolve", "skeleton": "/Game/PipelineCandidates/DrWatson/Rig/SK_DrWatson_Skeleton", "clips": "/Game/PipelineCandidates/DrWatson/H2Anim/AM_DrWatson_{Idle,LungeAttack,HitReact,DeathSettle}", "textures": ["T_DrWatson_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_DrWatson_H2LD_Edge", "T_UM_MatLUT_Watson"], "prop_name": null} (файлы текстур принимаемого объекта: T_DrWatson_H2LD_2K_BC.png, T_DrWatson_H2LD_2K_Edge.png, T_DrWatson_H2LD_2K_MatID.png, T_DrWatson_H2LD_2K_N.png, T_DrWatson_H2LD_2K_ORM.png, T_DrWatson_H2LD_TeamAccent_2K.png); ключи bake-профиля {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/build-profiles/dr-watson-h2-bake-h2-r2.json", "meshes": {"body": "SK_DrWatson_H2_Body", "weapon": "SK_DrWatson_H2_Revolver", "base": "SM_DrWatson_H2_Base"}, "materials.atlas": "M_DrWatson_H2_Atlas", "exports.fbx_preset": "blender/_tools/presets/UM_FBX_v1.json", "scale.figure_top_m": 0.45} — выдержка, сам профиль не открывай (его
  текстовые поля — записи исполнителя).
- Предыдущая карточка: art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r1/card.json (null на r1); баллы ставь заново по свежим кадрам.
  Пункты прежнего цикла: - r1 rework_fix_list п.1 · T · turn-135.jpg — сине-фиолетовая линия в желобке центрального шва спинки пальто от воротника до пояса (на close-torso-back — кант слева от шва): перезапечь/перекрасить полосу шва цветом сукна пальто, без чужого оттенка в желобке
- r1 rework_fix_list п.2 · T · pose-03.jpg — размытое светлое пятно без узора на пальто слева от саквояжа ниже пояса (участок, закрытый саквояжем в покое) и размытый прямоугольник на пальто под правой кистью (close-weapon): заполнить текстурой сукна пальто
- r1 rework_fix_list п.3 · T · close-hands.jpg — пятна металла на указательном и среднем пальцах правой кисти у барабана, грязно-синие мазки на манжетах; голубоватые кромки по нижней стороне полей котелка и краям воротника/лацканов (close-head, close-torso); оранжевый ореол у подошв на крышке подставки (close-base)
- r1 rework_fix_list п.4 · F · close-weapon.jpg — комковатые, гранёные барабан и ствол револьвера; гранёный купол котелка на силуэте (close-head, close-head-back); обломок под днищем подставки (close-base)
- r1 rework_fix_list п.5 · D · pose-05.jpg — бок пальто под рукой оружия вперёд растянут, узор вытянут полосами; перепонка бока пальто под поднятой левой рукой (pose-01): перевести веса бока пальто ниже подмышки с плеча на spine, развести стык рука|пальто
- r1 known_issues п.1 · T · tone.json — leather_worn status floor (y_ratio 1,356, share 0,0735, второстепенный): концепт темнее пола альбедо, T не снижает; gold_antique вне допуска (y_ratio 0,328, 336 px, второстепенный) задаёт t_cap 1,5
- r1 known_issues п.2 · G-TOPO · wire-front.jpg — 6 почти вырожденных треугольников в SK_DrWatson_H2_Body из 42228 (0,014 %), UE их отбросит
- r1 known_issues п.3 · F · pose-04b.jpg — на крышке подставки под поднятой левой стопой светлый след подошвы (вырез крышки или текстура под стопой; тип по кадру не опознан, засчитано как закрытие контакта только крупного плана) — этап 6: клип, уводящий стопу с контакта, проверяет крышку
- r1 known_issues п.4 · D · pose-01.jpg — сомнение: перепонка пальто под поднятой левой рукой — растяжение в пределах контура покоя (1,5) или клин за контур (1,0); поставлен якорь растяжения
- r1 known_issues п.5 · T · close-legs-back.jpg — узор сукна на спинке и подоле сзади — извилистый «лабиринт», на рукавах и полах спереди — ёлочка, на листе — мелкий твид; как дефект не засчитан (сомнение: орнамент другого мотива)
- r1 known_issues п.6 · T · uv-layout.png — покрытие атласа 49,7 % (тело 459 островов, револьвер 187, подставка 27) — справка
- r1 known_issues п.7 · S · close-head.jpg — выражение лица модели нахмуренное и старше спокойного лица листа; в S не входит — для витрины и этапа 7
  Для каждого пункта в rationale его измерения: «rN <список> п.K: закрыт» или «не закрыт — что видно, кадр». Закрыт —
  только если это видно на кадре того же вида, что в пункте (close-* для close-*); слова исполнителя тебе не
  передаются.

## Порядок
1. Гейты G-TOPO, G-UV, G-TEX, G-RIG, G-NAMES — только по отчётам, по таблице §4 (G-TOPO решает ld-fbx-report).
   Нет отчёта или ключа = FAIL; где ключ лежит для каждой карты G-TEX (N — в bake-отчёте через мост pins,
   TeamAccent — в отчёте из строки TeamAccent входа), сказано в строке G-TEX и в «Уточнениях» §4. G-NAMES (5): рост —
   по строке «Рост для G-NAMES» входа (верх тела без оружия). Запись гейта: {"status": ..., "source": "<путь от корня к решающему отчёту, без #>",
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
   validate_card.py. Вердикт — первое сработавшее правило таблицы §6 (cycle = r2; на r3 любой не-pass =
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
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-DR-WATSON-001", date "2026-10-21",
   cycle "r2", previous_card "art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r1/card.json", accepted_object [{"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/export/SK_DrWatson_H2LD.fbx", "sha256": "ca8a8104d6c306eebe4700c79b4184b87917a33eea2c9d0d4831dd77facbae98"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/export/SM_DrWatson_H2LD_Base.fbx", "sha256": "3272976b5533781a4b1c44c1c1d548c50e5e91bc2d62a326d0b92578ff029ec2"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/textures/T_DrWatson_H2LD_2K_BC.png", "sha256": "5cea94d91fd734d4930529389a2997129aeb8bcef481a5959aa1c5f31a787c1a"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/textures/T_DrWatson_H2LD_2K_N.png", "sha256": "bb6a6f53586c7262974bee723cee80485364e4e16a3bc52cea8d111b4728752c"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/textures/T_DrWatson_H2LD_2K_ORM.png", "sha256": "5662f3f6def6a5fc5bfaa4203e21b00c575a8041e558d30b85de8d6c60f783dd"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/textures/T_DrWatson_H2LD_2K_MatID.png", "sha256": "ab80a62924ead7823193d0ca9fd1b774c50f5ccf83f193e3d700c808a8b00065"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/textures/T_DrWatson_H2LD_2K_Edge.png", "sha256": "b0ac68d831de221ba0146665dc7d9e34bfa226ab01057b6b8ba269aeb05b8c8b"}, {"path": "art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-lookdev-r2/textures/T_DrWatson_H2LD_TeamAccent_2K.png", "sha256": "34bfc571ae8c6902f070bf5170da0b9d46f3aa140309ee0c25eae510bc92c023"}],
   frames {"dir": "art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/acceptance/20261021-r2/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "pose-04b.jpg", "pose-05.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Opus xhigh", "session_id": "workflow:acceptor-ASSET-DR-WATSON-001-r2"},
   executor_session_id "claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe/agent:stage3-watson", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла, bake-профиль целиком, acceptor-inputs.json, SKILL.md и другие файлы скилла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
