# Приёмка модели ASSET-MEDUSA-001, цикл r1 (этап 4 скилла 3d-model-pipeline)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).

Ты — приёмщик. Ты НЕ исполнитель: ничего не правишь, не запускаешь Blender, скрипты и validate_card.py, не пишешь
файлы. Твоя единственная выдача — JSON-карточка по схеме tools/art/acceptance/asset-acceptance-2.schema.json; файл
card.json записывает и проверяет запускающий.
Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md,
разделы 3 (кадры, «полный рост» и «крупный план»), 4 (гейты), 5 (якоря и общие правила), 6 (формула и вердикт),
7 (поля карточки).

## Вход
- Кадры: docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/ — открой КАЖДЫЙ файл из docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/frames.json#files в полном размере (1:1), не только имена.
  Вырезки и увеличения не нужны: каждую зону модели показывают close-* спереди и сзади (таблица зон §3). Другие файлы
  каталога docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1 (card*.json, final.json, acceptor-*) не открывай.
- Лист концепта: docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/sheet.png и compare-front/side/back.jpg (вид листа и кадр в одном росте, направляющие
  через 10 %). Сторона side-вида: left (compare-side сделан с turn-090.jpg).
  Палитра: frames.json#sheet.compare_palette_by — swatches (по свотчам) или views (по видам листа).
- Тон классов: docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/tone.json, если он есть (t_cap — потолок T; y_ratio_loo — яркость основного класса
  относительно фигуры; family_changed_main — смена семейства цвета, это S; классы status floor T не снижают).
- Зазоры оружия в позах: frames.json#pose_checks (D не снижают, касание — в known_issues, §5.4).
- Эталон качества: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png; эталон рендера:
  docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg.
- Отчёты: art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake/reports/ и art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/ (только JSON из §4 рубрики).
- Заявка: роль hero; якоря 1 змеи вместо волос (семь голов), 2 золотая лавровая диадема, 3 платье угольно-сливовое с золотым меандром по краям, 4 золотые браслеты и поножи со змеями, 5 золотой змеиный лук в левой руке, 6 колчан со стрелами за спиной на ремне через грудь; палитра слоновая кость (кожа), угольно-сливовый (платье), античное золото (металл), оливково-чёрный (змеи), коричневая кожа (колчан, ремни, сандалии), тёмный камень (подставка); оружие в left;
  POLY_BUDGET {"figure_tris_max": 45000, "base_tris_max": 2500} (figure_tris_max — фигура с оружием, base_tris_max — подставка);
  UE_NAMES файлы SK_Medusa_H2LD.fbx, SM_Medusa_H2LD_Base.fbx, T_Medusa_H2LD_2K_{BC,N,ORM,MatID,Edge}.png, T_Medusa_H2LD_TeamAccent_2K.png; меши в FBX SK_Medusa_H2_Body, SK_Medusa_H2_Bow, SM_Medusa_H2_Base; слот M_Medusa_H2_Atlas; скелет SKEL_UM_Humanoid, 17 костей; bake-профиль art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json (meshes, materials.atlas).
- Предыдущая карточка: null (null на r1). Проверь, закрыт ли её rework_fix_list,
  но баллы ставь заново по свежим кадрам.

## Порядок
1. Гейты G-TOPO, G-UV, G-TEX, G-RIG, G-NAMES — только по отчётам, по таблице §4 (G-TOPO решает ld-fbx-report).
   Нет отчёта или ключа = FAIL. Запись гейта: {"status": ..., "source": "<путь от корня к решающему отчёту, без #>",
   "note": "<файл#ключ = значение; ...>"}. Если гейт FAIL из-за дефекта исходника Tripo (нет части, фантом,
   слитые части) — добавь "source_defect": true и опиши дефект в note. Других ключей у гейта нет.
2. Баллы S, F, T, D — только по кадрам, по якорям §5 и общим правилам §5 п.1–9 (шаг 0,5; при смешанных признаках —
   нижний якорь). Порядок для каждого признака: дефект ли это (нет на листе в этом месте) → измерение (S / F геометрия
   / T без следа на wire-* / D только деформация) → где виден (полный рост = turn-* или pose-* 1:1, ≥ 8 px или
   пересекает силуэт; иначе только крупный план) → зона (§3). Считай зоны, а не кадры: F и T — только крупный план
   1,5; полный рост в одной зоне 1,0; в двух и более зонах 0,5. S — только контур, пропорции, якоря и раскладка
   цветов (термины §5.1); орнамент и детализация — только T. T не выше tone.json#t_cap.
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
6. Константы: schema "unmatched.asset-acceptance/2", kind "model", asset_id "ASSET-MEDUSA-001", date "2026-10-09",
   cycle "r1", previous_card null, accepted_object [{"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/export/SK_Medusa_H2LD.fbx", "sha256": "f5a49a34610d0d872fe77b2c24e4039e15efc89c54f0a68ea39cf4846fcddcc3"}, {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/export/SM_Medusa_H2LD_Base.fbx", "sha256": "9c776780ae1b9df1cd5ee025cb3b6f309367cc557301053bd0b38fe98667a133"}, {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/textures/T_Medusa_H2LD_2K_BC.png", "sha256": "b6fa3077e7c953dcc1a42e3624cc8493647880f05c9f51ee2a3de8d28acbeda2"}, {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/textures/T_Medusa_H2LD_2K_N.png", "sha256": "11112739e6d8bbe1341a0fc4a573e2e43fcaaa4a0d1920fe7ae1f339b5345313"}, {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/textures/T_Medusa_H2LD_2K_ORM.png", "sha256": "885706567c123a9c15a3d9306bb0d90e89709af16f4d9e2b1896ca10dcbab5c4"}, {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/textures/T_Medusa_H2LD_2K_MatID.png", "sha256": "0436f845f3c91528806759a3e31fa359a1077369ad32b66d0c238bbfebadc5ea"}, {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/textures/T_Medusa_H2LD_2K_Edge.png", "sha256": "aadada7e5a023ce4e6c11a8ab5b6a38eb669d8f278ed837d01cc0194088cdfa4"}, {"path": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/textures/T_Medusa_H2LD_TeamAccent_2K.png", "sha256": "40f2db9aaafef3cac50f8b41b48edce7b1ffcf93401491e1e993bf2cad971be0"}],
   frames {"dir": "docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames", "files": ["close-base.jpg", "close-hands.jpg", "close-head-back.jpg", "close-head.jpg", "close-legs-back.jpg", "close-legs.jpg", "close-torso-back.jpg", "close-torso.jpg", "close-weapon.jpg", "compare-back.jpg", "compare-front.jpg", "compare-side.jpg", "frames.json", "pose-01.jpg", "pose-02.jpg", "pose-03.jpg", "pose-03b.jpg", "pose-04.jpg", "sheet.png", "tone.json", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-front.jpg"]}, reports — пути от корня ко всем отчётам из note
   гейтов, acceptor {"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"},
   executor_session_id "history:ASSET-MEDUSA-001/20260929-h2-lookdev", decided_by "delegated (ВР-реестр 2026-10-06)".
   При pass status_note = "художественно принято, по делегированию
   (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)", иначе status_note = "".
   Других полей верхнего уровня нет (схема: additionalProperties false).

## Запрещено
- Ставить балл по отчёту вместо кадра (кроме потолка T из tone.json) или гейт по кадру вместо отчёта.
- Учитывать что-либо, кроме перечисленного во «Входе» (чат, git log, отчёты исполнителя в свободной форме, другие
  карточки этого цикла).
- Смягчать якоря «потому что исправимо» или ужесточать «на всякий случай»: балл — это то, что видно.

Ответ — только JSON карточки, без текста вокруг.
