# Приёмка модели ASSET-SHERLOCK-HOLMES-001, цикл r3 (этап 4 скилла 3d-model-pipeline)

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
- Кадры: art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r3/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r3/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны, отчёты и предыдущую карточку ниже.
  Другие файлы каталога art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r3 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r3/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r3/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-bake-r3/reports/ и art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/reports/ (только JSON из §4 рубрики).
- TeamAccent снят в том же look-dev прогоне: art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/reports/ld-team-accent-report.json — для строки G-TEX «TeamAccent_2K» решает этот отчёт (его outputs.T_SherlockHolmes_H2LD_TeamAccent_2K.png.sha256 = sha256 принимаемой карты art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/textures/T_SherlockHolmes_H2LD_TeamAccent_2K.png).
- Рост для G-NAMES п.(5) — верх ТЕЛА без оружия: art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/reports/ld-fbx-report.json#roundtrip.ld.skeletal.meshes.SK_SherlockHolmes_H2_Body.bounds_m.max[2] = 0.54984 м против FIGURE_HEIGHT_M заявки 0.55 м ± 1 %; art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-bake-r3/reports/rig-report.json#checks.unit_scale_1_and_height.measured.skeletal_top_cm = 54.984 — верх всей фигуры с оружием, справка.
- Заявка: роль hero; якоря magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe; палитра main: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20; accent: brass lens #C9A24A; оружие в right;
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_SherlockHolmes_H2LD", "base": "SM_SherlockHolmes_H2LD_Base", "materials": ["MI_SherlockHolmes_H2LD", "MI_SherlockHolmes_H2LD_Base", "MI_SherlockHolmes_H2LD_P1", "MI_SherlockHolmes_H2LD_P2", "MI_SherlockHolmes_H2LD_Base_P1", "MI_SherlockHolmes_H2LD_Base_P2"], "dissolve": "/Game/UM/Materials/v2/Dissolve/MI_SherlockHolmes_H2LD_{P1,P2}_Dissolve", "skeleton": "/Game/PipelineCandidates/SherlockHolmes/Rig/SK_SherlockHolmes_Skeleton", "clips": "/Game/PipelineCandidates/SherlockHolmes/H2Anim/AM_SherlockHolmes_{Idle,LungeAttack,HitReact,DeathSettle}", "textures": ["T_SherlockHolmes_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_SherlockHolmes_H2LD_Edge", "T_UM_MatLUT_SherlockHolmes"], "prop_name": null} (файлы текстур принимаемого объекта: T_SherlockHolmes_H2LD_2K_BC.png, T_SherlockHolmes_H2LD_2K_Edge.png, T_SherlockHolmes_H2LD_2K_MatID.png, T_SherlockHolmes_H2LD_2K_N.png, T_SherlockHolmes_H2LD_2K_ORM.png, T_SherlockHolmes_H2LD_TeamAccent_2K.png); ключи bake-профиля {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/build-profiles/sherlock-holmes-h2-bake-h2-r3.json", "meshes": {"body": "SK_SherlockHolmes_H2_Body", "base": "SM_SherlockHolmes_H2_Base"}, "materials.atlas": "M_SherlockHolmes_H2_Atlas", "exports.fbx_preset": "blender/_tools/presets/UM_FBX_v1.json", "scale.figure_top_m": 0.55} — выдержка, сам профиль не открывай (его
  текстовые поля — записи исполнителя).
- Предыдущая карточка: art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r2/card.json (null на r1); баллы ставь заново по свежим кадрам.
  Пункты прежнего цикла: - r2 rework_fix_list п.1 · F · close-base.jpg — Светлые зубчатые обрывки кромки выреза крышки подставки вокруг обеих подошв (у левой подошвы слева, у правой справа на крышке); те же зубцы у пяток на close-legs-back и wire-back. Закрыть вырез крышками по точной кромке подошв и сгладить кромку.
- r2 rework_fix_list п.2 · F · pose-04b.jpg — Под поднятой левой стопой (справа на крышке подставки) виден контур выреза крышки — тёмный след подошвы со светлыми точками (также pose-04); крышка base_hole должна закрывать вырез по кромке подошвы.
- r2 rework_fix_list п.3 · T · close-hands.jpg — Левая кисть (правая панель): голубоватые кончики большого пальца и ногтей, телесная полоса на клапане манжеты вместо белой ткани; правая кисть (левая панель, также close-weapon): тёмные мазки на костяшке указательного пальца и у основания ладони. Перекрасить полосы стыка кисть|манжета и убрать пятна переноса на коже.
- r2 rework_fix_list п.4 · T · close-weapon.jpg — Торец рукояти лупы внизу светлый пятнистый; внутренняя кромка линзы по кругу зубчатая голубовато-белая. На листе тёмная деревянная рукоять с латунным наконечником и ровная кромка стекла.
- r2 rework_fix_list п.5 · T · close-base.jpg — Светлые разводы в центре крышки подставки и тонкая светлая линия между стопами.
- r2 rework_fix_list п.6 · D · pose-01.jpg — Плащ левой стороны тянется за поднятой левой рукой клином от подмышки до бедра, примерно 130 px за контуром покоя, фактура растянута; слабее под правой рукой на pose-02 и pose-05. Перевести веса нижней части плаща с arm_upper.L/R на spine, задать стыки рука|плащ.
- r2 known_issues п.1 · F · pose-04b.jpg — Закрытие контакта, открытое позой пробы: под поднятой левой стопой контур выреза крышки подставки (также pose-04); по п.5 — только крупный план. Этап 6: клип, уводящий стопу с контакта, проверяет крышку.
- r2 known_issues п.2 · F · turn-180.jpg — У пяток на краю крышки светлые точки около 8 px (также turn-315, pose-03b); на полном росте сливаются с краем крышки — учтены как крупный план (close-base).
- r2 known_issues п.3 · T · close-weapon.jpg — Внутри линзы у шейки рукояти светлый прозрачный выступ (продолжение шейки в стекле) — сомнение: форма или рисунок; балл не снижен.
- r2 known_issues п.4 · T · pose-04.jpg — Светлые пятна на внутренней стороне правой брючины, открытой поднятым левым бедром — сомнение: пятно или узор ёлочки; балл не снижен.
- r2 known_issues п.5 · S · turn-180.jpg — Чаша трубки видна за головой слева; на back листа её нет, но на front листа чаша так же выступает за щёку — естественное перекрытие, S не снижает.
- r2 known_issues п.6 · T · tone.json — Классы leather_smooth, silk, stone_base, wood — status floor (концепт темнее пола альбедо), T не снижают; этап 7: тон по UE-съёмке.
- r2 known_issues п.7 · T · tone.json — warnings loo_unavailable: wool_coarse (71 % пикселей, якорный класс) — яркость основного класса относительно фигуры не проверена; этап 7: тон по UE-съёмке.
- r2 known_issues п.8 · G-TOPO · wire-front.jpg — 2 почти вырожденных треугольника в SK_SherlockHolmes_H2_Body (0,006 %, ld-fbx-report.json); UE их отбросит.
- r2 known_issues п.9 · T · uv-layout.png — Справочно: покрытие атласа 46,2 %, 708 островов тела и 107 подставки; лицо плотнее платья в 2 раза (uv-report.json#checks.priority_face_denser_than_body: 79,0 против 39,5).
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
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-SHERLOCK-HOLMES-001", date "2026-10-21",
   cycle "r3", previous_card "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r2/card.json", accepted_object [{"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/export/SK_SherlockHolmes_H2LD.fbx", "sha256": "9a3a35f8d6563c65af7820bfb5763cf0bef5a7267c82d50860c90f585f5be0e7"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/export/SM_SherlockHolmes_H2LD_Base.fbx", "sha256": "0bfb8853c4be9132f126be7c19bb8c1b92ad123202e894b41cb802aeb3fe0fe6"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/textures/T_SherlockHolmes_H2LD_2K_BC.png", "sha256": "63669f3b0632b67bd7676366ff24e809b66162998e9e3dc8cca42188b60e678c"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/textures/T_SherlockHolmes_H2LD_2K_N.png", "sha256": "433f6e7b808d5bb922a467088a888c20c1c1673af92208e51de3fe396b5fcbab"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/textures/T_SherlockHolmes_H2LD_2K_ORM.png", "sha256": "f9b8b7115f01a34e24e9e99fdc8a9ffd80b8b668aec65a226077c5731fb98fdb"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/textures/T_SherlockHolmes_H2LD_2K_MatID.png", "sha256": "67200283965eefd5073e9896c2654dd3504ccd7e72f383e62380f09379ae9b9e"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/textures/T_SherlockHolmes_H2LD_2K_Edge.png", "sha256": "f8bc4c1ca1ef26b6fb3c6302da792009b020a560a37d1833c14bb2c98525a256"}, {"path": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-lookdev-r3/textures/T_SherlockHolmes_H2LD_TeamAccent_2K.png", "sha256": "0bff07718ad19352a02c6c1ae1cb64a1e76e550a3a35975e559428c5a9c614f4"}],
   frames {"dir": "art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/evidence/acceptance/20261021-r3/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "pose-04b.jpg", "pose-05.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Opus xhigh", "session_id": "workflow:acceptor-ASSET-SHERLOCK-HOLMES-001-r3"},
   executor_session_id "claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла, bake-профиль целиком, acceptor-inputs.json, SKILL.md и другие файлы скилла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
