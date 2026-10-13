# Приёмка модели ASSET-ACHILLES-001, цикл r1 (этап 4 скилла 3d-model-pipeline)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — приёмщик. Ты НЕ исполнитель: ничего не правишь, не запускаешь Blender, скрипты и validate_card.py, не пишешь
файлы. Твоя единственная выдача — JSON-карточка по схеме tools/art/acceptance/asset-acceptance-2.schema.json; файл
card.json записывает и проверяет запускающий.
Текстовые файлы читай так, чтобы кириллица дошла целой. В песочнице codex PowerShell работает в Constrained
Language Mode и пишет вывод в OEM-кодировке: `Get-Content -Encoding UTF8` даёт кракозябры, смена
`[Console]::OutputEncoding` запрещена, `rg` нет. Рабочие способы (проверено пробой 2026-10-13): КАЖДЫЙ текстовый файл
(рубрику, JSON-отчёты, frames.json, tone.json, профиль) читай `Get-Content <файл> -Raw -Encoding OEM` (байты UTF-8
проходят без перекодировки и читаются верно) или `cmd /c type <файл>`. Кодовые точки (`[int[]][char[]]`) не нужны.
Если текст всё равно пришёл кракозябрами — не угадывай содержимое: перечитай файл вторым способом.
Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md,
разделы 3 (кадры, «полный рост» и «крупный план»), 4 (гейты), 5 (якоря и общие правила), 6 (формула и вердикт),
7 (поля карточки).

## Вход
- Кадры: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1/frames/ — открой КАЖДЫЙ файл из art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3), сетку —
  wire-front, wire-34 и wire-back. Кроме этих файлов открывай только эталоны и отчёты ниже. Другие файлы каталога
  art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-bake-2/reports/ и art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/reports/ (только JSON из §4 рубрики). Прогон art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-bake (без «-2») — неудачная история, его не открывай.
- TeamAccent: итоговый прогон art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-teamaccent-b (профиль art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-lookdev-teamaccent-b.json, отчёты art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-teamaccent-b/reports/). Его T_Achilles_H2LD_TeamAccent_2K.png побайтно совпадает с art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/textures/ (sha256 3e430523… = accepted_object), ld-team-accent-report.json обоих прогонов отличается только profile_id. Для строки G-TEX «TeamAccent_2K» решает art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-teamaccent-b/reports/ld-team-accent-report.json. Доля акцента 2,20 % и порог K2 5× снижены для этого героя действующим решением проекта П3-4/П3-4b (docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md): это норма для Achilles, не дефект и не повод снижать баллы. art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/reports/ld-team-report.json (passed false) — прогон до П3-4b, его заменяет art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-teamaccent-b/reports/ld-team-report.json; в гейты §4 ни тот ни другой не входят.
- Рост фигуры для G-NAMES п.(5): верх тела, а не наконечник копья — ld-fbx-report.json#roundtrip.ld.skeletal.meshes.SK_Achilles_H2_Body.bounds_m.max[2] (и rig-report.json#checks.unit_scale_1_and_height.measured.skeletal_top_cm). У Achilles верх тела — верх гребня шлема: заявка задаёт FIGURE_HEIGHT_M 0,55 м как верх гребня (решение П3-5 в asset-card.yaml); наконечник копья (SK_Achilles_H2_Spear, bounds_m.max[2]) ниже гребня и рост не задаёт.
- Заявка: роль hero; якоря spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak; палитра main: bronze #A9773A, crimson #8E2A23, olive skin #B98B66; accent: gold crest trim #E0B54A; оружие в right (щит — на левом предплечье);
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES {"stage": "H2LD", "skeletal_mesh": "SK_Achilles_H2LD", "base": "SM_Achilles_H2LD_Base", "textures": ["T_Achilles_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_Achilles_H2LD_Edge", "T_UM_MatLUT_Achilles"]} (отгружаемые файлы текстур — 2K: T_Achilles_H2LD_2K_{BC,N,ORM,MatID,Edge}.png, T_Achilles_H2LD_TeamAccent_2K.png); bake-профиль art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-bake-h2b.json (meshes, materials.atlas).
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
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-ACHILLES-001", date "2026-10-14",
   cycle "r1", previous_card null, accepted_object [{"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/export/SK_Achilles_H2LD.fbx", "sha256": "c12b967f20e118a210c6f10dc38fe283c943f75f24a95afc8901396c2d34f319"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/export/SM_Achilles_H2LD_Base.fbx", "sha256": "0014d3e2573561897b8ac926942fba343cc890c227fe959bb1b3bce83a9c2031"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/textures/T_Achilles_H2LD_2K_BC.png", "sha256": "c7b71c3f2e78065de10a371fe348c85401f626e037d6c6b80cdc9a46f2c2415c"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/textures/T_Achilles_H2LD_2K_N.png", "sha256": "8fb77a9cd93ba8fcd7042038971fdb83ef13c4a23a28c8f52f53a0099ba3b792"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/textures/T_Achilles_H2LD_2K_ORM.png", "sha256": "e2cef6f02089c43c7f1df55f9b60308b8a1533574e26e8d2525efdb00cf80072"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/textures/T_Achilles_H2LD_2K_MatID.png", "sha256": "e8979f2f15928a334e101c92b6e8583491b009e0fdf0d97d7617d6c23b54004b"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/textures/T_Achilles_H2LD_2K_Edge.png", "sha256": "5e16622ac8b59e0ad37cd61c3bbbebe8c49f863c4ce85a0b2d1ef62e0a9687ec"}, {"path": "art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-lookdev-2/textures/T_Achilles_H2LD_TeamAccent_2K.png", "sha256": "3e430523f4b063276d0feeae2810ea217d89491e4c4dc5f0d4442352479017b2"}],
   frames {"dir": "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "claude-code:e8429502-d3da-4eca-a8a6-748a200f3ed6/agent:stage3-achilles-r2", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
