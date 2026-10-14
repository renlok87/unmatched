# Приёмка модели ASSET-BEOWULF-001, цикл r1 (этап 4 скилла 3d-model-pipeline)

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
- Кадры: art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны, отчёты и предыдущую карточку ниже.
  Другие файлы каталога art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-bake-t4/reports/ и art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/reports/ (только JSON из §4 рубрики).
- TeamAccent снят в том же look-dev прогоне: art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/reports/ld-team-accent-report.json — для строки G-TEX «TeamAccent_2K» решает этот отчёт (его outputs.T_Beowulf_H2LD_TeamAccent_2K.png.sha256 = sha256 принимаемой карты art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/textures/T_Beowulf_H2LD_TeamAccent_2K.png).
- Рост для G-NAMES п.(5) — верх ТЕЛА без оружия: art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/reports/ld-fbx-report.json#roundtrip.ld.skeletal.meshes.SK_Beowulf_H2_Body.bounds_m.max[2] = 0.55015 м против FIGURE_HEIGHT_M заявки 0.55 м ± 1 %; рост не задают другие меши (оружие): SK_Beowulf_H2_Sword bounds_m.max[2] = 0.54684 м; art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-bake-t4/reports/rig-report.json#checks.unit_scale_1_and_height.measured.skeletal_top_cm = 55.015 — верх всей фигуры с оружием, справка.
- Заявка: роль hero; якоря longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard; палитра main: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43; accent: gold torc #C99A35; оружие в right;
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_Beowulf_H2LD", "base": "SM_Beowulf_H2LD_Base", "materials": ["MI_Beowulf_H2LD", "MI_Beowulf_H2LD_Base", "MI_Beowulf_H2LD_P1", "MI_Beowulf_H2LD_P2", "MI_Beowulf_H2LD_Base_P1", "MI_Beowulf_H2LD_Base_P2"], "dissolve": "/Game/UM/Materials/v2/Dissolve/MI_Beowulf_H2LD_{P1,P2}_Dissolve", "skeleton": "/Game/PipelineCandidates/Beowulf/Rig/SK_Beowulf_Skeleton", "clips": "/Game/PipelineCandidates/Beowulf/H2Anim/AM_Beowulf_{Idle,LungeAttack,HitReact,DeathSettle}", "textures": ["T_Beowulf_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_Beowulf_H2LD_Edge", "T_UM_MatLUT_Beowulf"], "prop_name": null} (файлы текстур принимаемого объекта: T_Beowulf_H2LD_2K_BC.png, T_Beowulf_H2LD_2K_Edge.png, T_Beowulf_H2LD_2K_MatID.png, T_Beowulf_H2LD_2K_N.png, T_Beowulf_H2LD_2K_ORM.png, T_Beowulf_H2LD_TeamAccent_2K.png); ключи bake-профиля {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2-bake-h2-t4.json", "meshes": {"body": "SK_Beowulf_H2_Body", "weapon": "SK_Beowulf_H2_Sword", "base": "SM_Beowulf_H2_Base"}, "materials.atlas": "M_Beowulf_H2_Atlas", "exports.fbx_preset": "blender/_tools/presets/UM_FBX_v1.json", "scale.figure_top_m": 0.55} — выдержка, сам профиль не открывай (его
  текстовые поля — записи исполнителя).
- Предыдущая карточка: null (null на r1); баллы ставь заново по свежим кадрам.
  Пункты прежнего цикла: нет (r1 или у прежней карточки пустые rework_fix_list и known_issues)
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
   validate_card.py. Вердикт — первое сработавшее правило таблицы §6 (cycle = r1; на r3 любой не-pass =
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
   `item` — только S, F, T, D или id гейта (G-TOPO, G-UV, G-TEX, G-RIG, G-NAMES); пустое поле — JSON null, не строка.
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-BEOWULF-001", date "2026-10-14",
   cycle "r1", previous_card null, accepted_object [{"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/export/SK_Beowulf_H2LD.fbx", "sha256": "0a63bfc05cbe96280a3d450c0d8b387cd449b81d3c28a3fba8651c6ce982068a"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/export/SM_Beowulf_H2LD_Base.fbx", "sha256": "e57edc1fea17c63eb6f60779dbfa719ae48296c87255dc98adb0082eb8d98ea8"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/textures/T_Beowulf_H2LD_2K_BC.png", "sha256": "a37cf19c47c6b5e13aa60bfeab82ef21e9456236e22fce4e7e7ae163d6dc1b73"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/textures/T_Beowulf_H2LD_2K_N.png", "sha256": "a445248df1248b6d72eeced0c374fff068ec22cb33b43e8ed6e9dc13560b729f"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/textures/T_Beowulf_H2LD_2K_ORM.png", "sha256": "491fa0ec7e12d344e21d231cabad53b3e7bab1bb3b600dc2dcb4ac64203e7da4"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/textures/T_Beowulf_H2LD_2K_MatID.png", "sha256": "74a18068ccce034623c325ed26edaebdb711e0841179ef65fa340aa068f91f58"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/textures/T_Beowulf_H2LD_2K_Edge.png", "sha256": "7e522c9b52d102cbeb0e642fd993435f61d2480a13b2896f7203596459910f9f"}, {"path": "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/textures/T_Beowulf_H2LD_TeamAccent_2K.png", "sha256": "9c0364d7b742300438a0b08632f72f661d2a6b805ea2f00edaca7c81bb2c9353"}],
   frames {"dir": "art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "pose-04b.jpg", "pose-05.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Opus xhigh", "session_id": "workflow:acceptor2-ASSET-BEOWULF-001-r1"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:beowulf-stage3", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла, bake-профиль целиком, acceptor-inputs.json, SKILL.md и другие файлы скилла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
