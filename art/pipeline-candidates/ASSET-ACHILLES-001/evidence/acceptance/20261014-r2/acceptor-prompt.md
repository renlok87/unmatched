# Приёмка модели ASSET-ACHILLES-001, цикл r2 (этап 4 скилла 3d-model-pipeline)

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
- Кадры: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны, отчёты и предыдущую карточку ниже.
  Другие файлы каталога art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-bake-r2/reports/ и art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/reports/ (только JSON из §4 рубрики).
  TeamAccent снят в том же look-dev прогоне: art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/reports/ld-team-accent-report.json (отдельного прогона TeamAccent
  в этом цикле нет; профиль art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-lookdev-teamaccent-r2.json).
  Для строки G-TEX «TeamAccent_2K» решает этот отчёт. Доля акцента около 2,2 % и сниженный порог K2 у этого героя —
  действующее решение проекта П3-4/П3-4b (docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md;
  латы и плащ главного цвета не дают 5 % разрешённой площади): это норма для Achilles, не дефект и не повод снижать
  баллы. Прогоны 20261013-* (bake, bake-2, lookdev-2, lookdev-teamaccent-b) — история r1, их не открывай.
- Рост фигуры для G-NAMES п.(5): верх ТЕЛА, а не наконечник копья — ld-fbx-report.json#roundtrip.ld.skeletal.meshes.SK_Achilles_H2_Body.bounds_m.max[2]
  (и rig-report.json#checks.unit_scale_1_and_height.measured.skeletal_top_cm). У Achilles верх тела — верх гребня
  шлема (около 0,5499 м): заявка задаёт FIGURE_HEIGHT_M 0,55 м как верх гребня (решение П3-5 в asset-card.yaml);
  наконечник копья (SK_Achilles_H2_Spear, bounds_m.max[2]) ниже гребня и рост не задаёт.
- Заявка: роль hero; якоря (поле ANCHORS_EN заявки — это ANCHORS): spear upright in the figure's own RIGHT hand;
  round bronze shield on the LEFT arm; tall horsehair crest; red cloak; палитра main: bronze #A9773A, crimson #8E2A23,
  olive skin #B98B66; accent: gold crest trim #E0B54A; оружие в right (WEAPON_HAND right, кость weapon.R; щит — на
  левом предплечье, без своей кости);
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_Achilles_H2LD", "base": "SM_Achilles_H2LD_Base", "textures": ["T_Achilles_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_Achilles_H2LD_Edge", "T_UM_MatLUT_Achilles"]} (отгружаемые файлы текстур — 2K: T_Achilles_H2LD_2K_{BC,N,ORM,MatID,Edge}.png, T_Achilles_H2LD_TeamAccent_2K.png; MatLUT — T_UM_MatLUT_Achilles.dds); bake-профиль art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-bake-h2-r2.json (meshes, materials.atlas).
- Предыдущая карточка: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1/card.json (цикл r1, verdict rework_blender, score 6,9). Проверь, закрыт ли её
  rework_fix_list, но баллы ставь заново по свежим кадрам r2 (§2.3 п.5 рубрики).

## Список доработки r1 — проверить каждый пункт
Пункты rework_fix_list карточки r1 и статус, который заявил исполнитель доработки. Заявление — не доказательство:
каждый пункт проверь сам по свежим кадрам r2 (и по tone.json, где пункт касается тона). Заявление не смягчает и не
ужесточает балл: оценивай то, что видно, по рубрике.
1. F, close-legs-back.jpg (и close-legs.jpg): треугольные зазубрины нижней кромки подошв, особенно у пяток.
   Заявлено исполнителем: «не закрыто» (форма кромки идёт из high-poly исходника Tripo; нужна опция сглаживания
   кромки при closure, которой в h2_bake нет).
2. T, tone.json: относительная яркость основного класса bronze вне допуска (r1: y_ratio_loo 0,717, t_cap 1,0).
   Заявлено исполнителем: закрыто (проверь по tone.json r2; исполнитель предупреждает, что бронза может читаться
   немного бледнее, чем на r1 — это проверяется по кадрам и листу, как любой признак).
3. T, turn-000.jpg: верх металлического наконечника копья читался коричневым и матовым. Заявлено: закрыто.
4. T, close-head.jpg: центральный участок носовой пластины шлема выглядел телесным и матовым. Заявлено: закрыто.
5. T, close-torso.jpg: оливково-бежевые пятна на красном вороте у правой фибулы и у шеи. Заявлено: закрыто
   (полоса ткани перекрашена; полоса за шеей гладкая, складки — в нормали).
6. D, pose-01.jpg: угловатый залом кожи внутри сгиба левого локтя (arm_l_raise + forearm_l_bend). Заявлено: закрыто
   (мягче складка на pose-01).
В rationale своего измерения (пункт 1 — в scores.F.rationale, пункты 2–5 — в scores.T.rationale, пункт 6 — в
scores.D.rationale) запиши для каждого пункта «r1 п.N: закрыт» или «r1 п.N: не закрыт — <что видно, кадр>».
Незакрытый пункт, который по рубрике снижает балл, снова идёт в rework_fix_list (если вердикт его требует).

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
   `item` — только S, F, T, D или id гейта (G-TOPO, G-UV, G-TEX, G-RIG, G-NAMES); пустое поле — JSON null, не строка.
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-ACHILLES-001", date "2026-10-14",
   cycle "r2", previous_card "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1/card.json", accepted_object [{"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/export/SK_Achilles_H2LD.fbx", "sha256": "a6eea62d77b9b34832781efb91df7f1d650e75d6b655c8c1acf6adbc123f566f"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/export/SM_Achilles_H2LD_Base.fbx", "sha256": "2df7459219b63aad62e3662a6cfc2a2fb3bcbb3a7b55b63bde6673ac9680d934"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/textures/T_Achilles_H2LD_2K_BC.png", "sha256": "2a43d86db2d62b4b9c753d7833f0b76a795ecd29373f552dc39a9fc6d296f6c1"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/textures/T_Achilles_H2LD_2K_N.png", "sha256": "6c8deba25ebd209a0fe5a180af5cf684b913fad55b4727cab1f69b04d3baef1a"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/textures/T_Achilles_H2LD_2K_ORM.png", "sha256": "3956feceae535a2ebbd290e58c068f6576880c49fdb6b835c93f180c9f38191f"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/textures/T_Achilles_H2LD_2K_MatID.png", "sha256": "de7b7a7d732d5049d7660c49e67291e63a2f4e7007e42823636ee8e4ec55ba3e"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/textures/T_Achilles_H2LD_2K_Edge.png", "sha256": "8b138687eb0779a0a00edbd3aa9b4a3a410736030ab700e72eff3c89ce2304b5"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r2/textures/T_Achilles_H2LD_TeamAccent_2K.png", "sha256": "05ac5d86348fe1406a2aa95361a3d30d7a3dba0268b26154847c61689aa4b3f5"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage5-achilles", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» и в «Списке доработки r1» (чат, git log, отчёты исполнителя в
  свободной форме, другие карточки этого цикла, файлы скилла кроме рубрики).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
