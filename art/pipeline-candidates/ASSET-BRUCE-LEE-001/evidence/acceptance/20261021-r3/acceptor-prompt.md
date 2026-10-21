# Приёмка модели ASSET-BRUCE-LEE-001, цикл r3 (этап 4 скилла 3d-model-pipeline)

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
- Кадры: art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны, отчёты и предыдущую карточку ниже.
  Другие файлы каталога art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-bake-r3/reports/ и art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/reports/ (только JSON из §4 рубрики).
- TeamAccent снят в том же look-dev прогоне: art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/reports/ld-team-accent-report.json — для строки G-TEX «TeamAccent_2K» решает этот отчёт (его outputs.T_BruceLee_H2LD_TeamAccent_2K.png.sha256 = sha256 принимаемой карты art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/textures/T_BruceLee_H2LD_TeamAccent_2K.png).
- Рост для G-NAMES п.(5) — верх ТЕЛА без оружия: art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/reports/ld-fbx-report.json#roundtrip.ld.skeletal.meshes.SK_BruceLee_H2_Body.bounds_m.max[2] = 0.54999 м против FIGURE_HEIGHT_M заявки 0.55 м ± 1 %; art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-bake-r3/reports/rig-report.json#checks.unit_scale_1_and_height.measured.skeletal_top_cm = 54.999 — верх всей фигуры с оружием, справка.
- Заявка: роль hero; якоря yellow jumpsuit with black side stripes; bare-handed fighting stance; short black hair; палитра main: suit yellow #E0B830, stripe black #141414, skin tan #C49A74; accent: shoe black #1E1C1C; оружие в none;
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_BruceLee_H2LD", "base": "SM_BruceLee_H2LD_Base", "materials": ["MI_BruceLee_H2LD", "MI_BruceLee_H2LD_Base", "MI_BruceLee_H2LD_P1", "MI_BruceLee_H2LD_P2", "MI_BruceLee_H2LD_Base_P1", "MI_BruceLee_H2LD_Base_P2"], "dissolve": "/Game/UM/Materials/v2/Dissolve/MI_BruceLee_H2LD_{P1,P2}_Dissolve", "skeleton": "/Game/PipelineCandidates/BruceLee/Rig/SK_BruceLee_Skeleton", "clips": "/Game/PipelineCandidates/BruceLee/H2Anim/AM_BruceLee_{Idle,LungeAttack,HitReact,DeathSettle}", "textures": ["T_BruceLee_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_BruceLee_H2LD_Edge", "T_UM_MatLUT_BruceLee"], "prop_name": null} (файлы текстур принимаемого объекта: T_BruceLee_H2LD_2K_BC.png, T_BruceLee_H2LD_2K_Edge.png, T_BruceLee_H2LD_2K_MatID.png, T_BruceLee_H2LD_2K_N.png, T_BruceLee_H2LD_2K_ORM.png, T_BruceLee_H2LD_TeamAccent_2K.png); ключи bake-профиля {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2-bake-h2-r3.json", "meshes": {"body": "SK_BruceLee_H2_Body", "base": "SM_BruceLee_H2_Base"}, "materials.atlas": "M_BruceLee_H2_Atlas", "exports.fbx_preset": "blender/_tools/presets/UM_FBX_v1.json", "scale.figure_top_m": 0.55} — выдержка, сам профиль не открывай (его
  текстовые поля — записи исполнителя).
- Предыдущая карточка: art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r2/card.json (null на r1); баллы ставь заново по свежим кадрам.
  Пункты прежнего цикла: - r2 rework_fix_list п.1 · T · turn-270.jpg — Лампас правой стороны: на правом рукаве у локтя и манжеты тёмная полоса разорвана жёлтыми вставками и пятнами (turn-270, turn-315, turn-225, pose-03b, close-weapon, pose-05, close-attack панель спины), на правой штанине — рваные края, ржавые крапины и светлая линия внутри полосы (turn-270, turn-315, close-legs, close-weapon). Перекрасить весь лампас сплошным цветом класса лампаса (одна чёрная полоса, как на листе), без жёлтого внутри и рваной кромки
- r2 rework_fix_list п.2 · T · turn-135.jpg — Лампас левой штанины сзади читается двумя тонкими тёмными линиями с жёлтой серединой (turn-135, turn-180, close-legs-back) вместо одной сплошной чёрной полосы вида back листа: залить жёлтый промежуток цветом лампаса по всей длине от пояса до низа штанины
- r2 rework_fix_list п.3 · T · turn-045.jpg — Жёлтые полоски на кедах рваные, мазками, с тёмными и красноватыми прожилками (правая кеда turn-045, pose-03, pose-04, close-base; левая кеда close-legs): сделать ровные сплошные жёлтые полоски на чёрной коже, как на листе
- r2 rework_fix_list п.4 · T · close-base.jpg — Крышка подставки вокруг и между стоп — гладкое светлое пятно без зерна камня и светлая точка у носка правой кеды (r1 п.5 не закрыт; по wire-34 место совпадает с веером крышки под стопами): вернуть зерно камня stone_base на всю верхнюю плоскость
- r2 rework_fix_list п.5 · F · close-hands.jpg — Выпуклый лампас на боку корпуса и у манжеты рукава комковатый, «блоками» (close-hands панель hand.L внизу справа, close-torso оба бока, close-attack панель спины у манжеты; r1 п.6 не закрыт): нужна ровная плоская полоса, как на листе
- r2 known_issues п.1 · T · turn-000.jpg — волосы и кеды серо-графитовые вместо чёрных (#141414 / #1E1C1C листа): класс leather_smooth status floor (tone.json y_ratio 3,588) — T не снижает; этап 7: тон по UE-съёмке (r1 known_issues п.1 не закрыт)
- r2 known_issues п.2 · T · turn-090.jpg — лампасы тёмно-серые, а не чёрные: wool_coarse status floor (tone.json y_ratio 1,77) — T не снижает; этап 7: тон по UE-съёмке (r1 known_issues п.2)
- r2 known_issues п.3 · T · close-base.jpg — подставка светлее листа: stone_base — основной класс (share 0,29) на floor (tone.json y_ratio_loo 1,701) — T не снижает; этап 7: тон по UE-съёмке (r1 known_issues п.3)
- r2 known_issues п.4 · T · tone.json — WARN loo_unavailable: linen — яркость якорного класса относительно фигуры не проверена; комбинезон бледнее и бежевее насыщенного #E0B830 листа (linen d_sat −0,188; яркость и оттенок в допуске) — сверить на UE-съёмке этапа 7 (r1 known_issues п.4)
- r2 known_issues п.5 · T · close-head.jpg — тёмная полоса над верхней губой (тонкие усы), лицо старше листа (глубокие носогубные складки, опущенные углы рта), сине-зелёные кончики прядей чёлки у лба — только крупный план (r1 known_issues п.5 не закрыт)
- r2 known_issues п.6 · T · close-head-back.jpg — светлая дуга на шее над воротом сзади, жёлтый мазок на коже шеи слева над воротом, сине-зелёные кончики прядей на затылке — только крупный план (r1 known_issues п.6 не закрыт)
- r2 known_issues п.7 · T · close-hands.jpg — жёлтые пятна цвета комбинезона на ногте и кончике указательного пальца правой кисти (и close-attack, панель бок) — только крупный план (r1 known_issues п.7 не закрыт)
- r2 known_issues п.8 · F · pose-04b.jpg — под поднятой левой стопой на крышке подставки светлые точки (и pose-04) — возможно, край выреза крышки base_hole (сомнение в опознании); закрытие контакта, открытое позой пробы; этап 6: клип, уводящий стопу с контакта, проверяет крышку (r1 known_issues п.8)
- r2 known_issues п.9 · G-TOPO · wire-front.jpg — справочно: 1 почти вырожденный треугольник в SK_BruceLee_H2_Body (1 из 39659, 0,0025 %, UE его отбросит); retopo-report.json#checks.near_degenerate_faces = 0; у подставки 0 из 1413
- r2 known_issues п.10 · G-RIG · turn-000.jpg — справочно: validate-skeletal-mesh-v2.json ref_pose_facing 9,605° при допуске 10° (pass, у края)
- r2 known_issues п.11 · T · uv-layout.png — справка: покрытие атласа 52,0 %, 412 островов (311 тело + 101 подставка), острова подставки мелкие; след на кадрах — мыло на крышке подставки (в rework_fix_list)
- r2 known_issues п.12 · T · close-torso.jpg — тонкая оранжевая вертикальная линия по центру груди (нарисованный шов) от ворота до пояса; на листе её нет — только крупный план
- r2 known_issues п.13 · T · turn-270.jpg — светлый бежевый участок (носок или кожа) между низом штанины и задником кеды (turn-090, turn-270, close-legs-back); на виде side листа штанина лежит на кеде — мелкая деталь, сомнение в опознании
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
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-BRUCE-LEE-001", date "2026-10-21",
   cycle "r3", previous_card "art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r2/card.json", accepted_object [{"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/export/SK_BruceLee_H2LD.fbx", "sha256": "a7af9667172f38782155dc487172bfe4faffab9370da05e6255dcbe9b3d10b12"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/export/SM_BruceLee_H2LD_Base.fbx", "sha256": "11bba0d85961c03826d6f9ddffaa0a4ec611bb5225d8e63b527f6791540da9a4"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/textures/T_BruceLee_H2LD_2K_BC.png", "sha256": "d78dde2348c566c00349a7e633cf5b419ee580b8d1677dfc65dcaac9b4c1f97f"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/textures/T_BruceLee_H2LD_2K_N.png", "sha256": "02cdfc892a946ce9bbb61a6f31e97b4bdc2cecfbb1cbe0c9c50a371ae9091c2c"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/textures/T_BruceLee_H2LD_2K_ORM.png", "sha256": "d123a08106b2968b7e0a3029972da2fff01a0ca1742db7d70f95127ff48cc3d4"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/textures/T_BruceLee_H2LD_2K_MatID.png", "sha256": "a9ef86ebd2cdac178b49c1a38b762dc9eff50b27ab31a5990b05a0087118924f"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/textures/T_BruceLee_H2LD_2K_Edge.png", "sha256": "72a5def6fe69223ed0d655527a2849de95ed38ee40d54ce555de0a9702ed72dc"}, {"path": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-lookdev-r3/textures/T_BruceLee_H2LD_TeamAccent_2K.png", "sha256": "e22a485e15b3f7d137f67ed1b31356b97b1ac896cc1fb776201362e8a9630509"}],
   frames {"dir": "art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/acceptance/20261021-r3/frames", "files": ["close-attack.jpg", "close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "pose-04b.jpg", "pose-05.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Opus xhigh", "session_id": "workflow:acceptor-ASSET-BRUCE-LEE-001-r3"},
   executor_session_id "claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe/agent:stage3-bruce", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла, bake-профиль целиком, acceptor-inputs.json, SKILL.md и другие файлы скилла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
