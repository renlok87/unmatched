# Приёмка модели ASSET-ANGEL-001, цикл r1 (этап 4 скилла 3d-model-pipeline)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — приёмщик. Ты НЕ исполнитель: ничего не правишь, не запускаешь Blender, скрипты и validate_card.py, не пишешь
файлы. Твоя единственная выдача — JSON-карточка по схеме tools/art/acceptance/asset-acceptance-2.schema.json; файл
card.json записывает и проверяет запускающий.
Текстовые файлы читай так, чтобы кириллица дошла целой. В песочнице codex PowerShell работает в Constrained
Language Mode и пишет вывод в OEM-кодировке: `Get-Content -Encoding UTF8` даёт кракозябры, смена
`[Console]::OutputEncoding` запрещена, `rg` нет. Рабочие способы (проверено пробой 2026-10-13): 
`Get-Content <файл> -Raw -Encoding OEM` (байты UTF-8 проходят без перекодировки и читаются верно) или
`cmd /c type <файл>`. Кодовые точки (`[int[]][char[]]`) не нужны.
Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md,
разделы 3 (кадры, «полный рост» и «крупный план»), 4 (гейты), 5 (якоря и общие правила), 6 (формула и вердикт),
7 (поля карточки).

## Вход
- Кадры: art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны и отчёты ниже. Другие файлы каталога
  art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-bake/reports/ и art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/reports/ (только JSON из §4 рубрики).
- TeamAccent: итоговый прогон art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev-teamaccent-b (профиль art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2-lookdev-teamaccent-b.json, отчёты art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev-teamaccent-b/reports/). Его T_Angel_H2LD_TeamAccent_2K.png побайтно совпадает с art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/textures/ (sha256 7cba44c8… = accepted_object), ld-team-accent-report.json обоих прогонов отличается только profile_id. Доля акцента 0,73 % и порог K2 5× снижены для этого героя действующим решением проекта П3-4/П3-4a (docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md): это норма для Angel, не дефект. art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/reports/ld-team-report.json (passed false) — первый прогон до П3-4a, его заменяет art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev-teamaccent-b/reports/ld-team-report.json; в гейты §4 ни тот ни другой не входят.
- Заявка: роль hero; якоря broadsword in the RIGHT hand; long black leather coat; spiky dark hair; dark shirt; палитра main: coat black #1C1A1C, shirt grey #4A4A50, skin pale #D9BFA8; accent: blade steel #B8BEC4; оружие в right;
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_Angel_H2LD", "base": "SM_Angel_H2LD_Base", "textures": ["T_Angel_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_Angel_H2LD_Edge (или _EdgeMask)", "T_UM_MatLUT_Angel"]} (отгружаемые файлы текстур — 2K: T_Angel_H2LD_2K_{BC,N,ORM,MatID,Edge}.png, T_Angel_H2LD_TeamAccent_2K.png); bake-профиль art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2-bake-h2.json (meshes, materials.atlas).
- Предыдущая карточка: null (null на r1). Проверь, закрыт ли её rework_fix_list,
  но баллы ставь заново по свежим кадрам.

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
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-ANGEL-001", date "2026-10-13",
   cycle "r1", previous_card null, accepted_object [{"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/export/SK_Angel_H2LD.fbx", "sha256": "0bacddf1e1231df4c89b4b81523b40bddff6a634bb0a6c200b4e4d799e048c94"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/export/SM_Angel_H2LD_Base.fbx", "sha256": "8f7d70bb54bfca4536e12f1a3c1a31402f91e951321936e7cb00be59d7e59a7e"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/textures/T_Angel_H2LD_2K_BC.png", "sha256": "7bdf0094662a44b4f7344be96b16cd7ce3f9f33c514734ee6021486532aae89a"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/textures/T_Angel_H2LD_2K_N.png", "sha256": "80da03e4b36ad23a24d3bea583d155ed0cc1792cb3e35965c81bb6373a32f5e8"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/textures/T_Angel_H2LD_2K_ORM.png", "sha256": "4dccb5b18f7722e6492b4cbd3333fdb67716f5d4d5d337e9b2d66ee104acfb95"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/textures/T_Angel_H2LD_2K_MatID.png", "sha256": "725f1531e01dd5e25eac8b56b71aba0e4d17beb13ba3110973d3ca97298ec221"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/textures/T_Angel_H2LD_2K_Edge.png", "sha256": "37d97307a433a61ca916ea059bb89fe8a4c84f2ed67915ff56b5c237ee8e4871"}, {"path": "art/pipeline-candidates/ASSET-ANGEL-001/20261013-h2-lookdev/textures/T_Angel_H2LD_TeamAccent_2K.png", "sha256": "7cba44c8ce6947cfbfd1fcfcab89a247dd9abff887d928556d515784388a9c86"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage3-angel", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.