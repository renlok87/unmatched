# Приёмка пропа кита карты (этап 4 скилла 3d-model-pipeline, ветка prop)

Делегирование пользователя дословно: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits). Трат нет. Ты — независимый приёмщик; файлов не пишешь, скриптов не
запускаешь. Верни карточку `unmatched.asset-acceptance/2` (kind model) структурированным выводом.

## Объект
- Карта: Sherwood Forest (sherwood-forest); проп `wanted-post` — Столб с объявлением / Wanted notice post. Роль в сцене: dressing; зона: road edge; приоритет P1.
- Описание (то, что заказано): wooden post with a nailed parchment wanted notice and an arrow pinning it. Материалы: wood, parchment. Реальный размер ≈ 0.4×0.3×1.8 м; в игре высота 54.0 uu
  (фигура героя 55 uu). Стиль кита: stylized hand-painted tabletop miniature prop, ancient English greenwood of Robin Hood's outlaws, gnarled oak bark, moss, ferns, leather, rough timber, clean readable silhouette, PBR friendly
- Генерация: Tripo «Умная сетка» P2.0 по двум видам Gemini/Tripo Image (front + single); сборка tools/art/env_kit.

## Входы (открой каждый Read-ом целиком)
- Кадры (каталог `art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/evidence/acceptance/20261021-wanted-post-r1/frames/`), открыть обязательно эти 10: sheet.png (картинка, по которой генерировали),
  turn-000.jpg, turn-045.jpg, turn-090.jpg, turn-180.jpg, turn-270.jpg, wire-34.jpg, close-head.jpg (верх 22 %),
  close-base.jpg (низ 22 %), uv-layout.png. Остальные кадры `frames.json#files` (turn-135/225/315, wire-front/back,
  close-weapon) — только если нужны для решения.
- Отчёт сборки: `art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodWantedPost.build.json` (числа топологии, UV, текстур — для гейтов уже посчитаны ниже).

## Гейты (посчитаны по отчёту, перенеси как есть)
{
 "G-TOPO": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodWantedPost.build.json",
  "note": "4845 tris (бюджет env_kit 12000, проп 2000), single_mesh=True",
  "source_defect": null
 },
 "G-UV": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodWantedPost.build.json",
  "note": "UV0 islands 154, used 0.5798, overlap 0.0",
  "source_defect": null
 },
 "G-TEX": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodWantedPost.build.json",
  "note": "T_Env_SherwoodWantedPost_{BC,N,ORM}.png 2048, N DirectX, ORM.R=1 (без AO)",
  "source_defect": null
 },
 "G-RIG": {
  "status": "n/a",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodWantedPost.build.json",
  "note": "статический проп без рига",
  "source_defect": null
 },
 "G-NAMES": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodWantedPost.build.json",
  "note": "SM_Env_SherwoodWantedPost, M_Env_SherwoodWantedPost",
  "source_defect": null
 }
}

## Рубрика пропа (D = null, G-RIG = n/a)
- **S — силуэт и пропорции против sheet.png и описания.** 2,0: предмет тот, что заказан, пропорции и главные части
  совпадают с видами (≤ 5 % высоты), лишних и пропавших частей нет, узнаётся со всех 8 ракурсов; 1,5: одно
  второстепенное отличие (деталь контура); 1,0: два и более отличий, или заметно сбита пропорция главной части (> 10 %),
  или основное пятно цвета другого семейства; 0,5: пропала или другая главная часть, фантомная часть (выступ/оболочка на
  turn-090/270, wire-*), узнаётся только спереди; 0,0: другой предмет.
- **F — форма и шейдинг.** 2,0: на полном росте и крупных планах нет дыр, просветов, рваных краёв, чёрных пятен,
  вывернутых частей, мусорной геометрии, оплывших бесформенных масс; тонкие элементы целы; сетка на wire-* следует
  форме; 1,5: дефекты видны только на крупном плане; 1,0: дефект на полном росте в одной зоне или оплывшая форма
  главной части; 0,5: дефекты на полном росте в двух и более зонах; 0,0: сетка разрушена.
- **T — текстуры.** 2,0: материалы читаются как в описании и на видах (дерево — дерево, металл — металл), нет
  запечённого света и теней в цвете (освещение снималось), нет размытых пятен, швов и растяжек, детализация не беднее
  эталона рендера пропов (`art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5/` — уровень кита Sarpedon);
  1,5: дефекты только крупного плана; 1,0: дефект на полном росте в одной зоне (мыло, шов, чужой цвет, запечённый
  блик); 0,5: две и более зоны; 0,0: текстура разрушена.
- score = round((S+F+T) / 6 × 10, 1). pass — score ≥ 8,0 и ни одно измерение < 1,0 и все гейты PASS/n/a;
  S < 1,5 — `return_to_stage_2` (перегенерация Tripo, rework_fix_list пуст, F/T < 2 — в known_issues); иначе
  `rework_blender` с пунктами rework_fix_list для каждого F/T < 2 и FAIL-гейта (tool — «env_kit params» или «исходник
  Tripo: форма/текстура»).
- Это фоновый проп настольной диорамы: читаемость на игровой дистанции важнее микродеталей; стилизация допустима.

## Константы карточки (перенеси дословно)
- schema `unmatched.asset-acceptance/2`, kind `model`, asset_id `ASSET-MAPKIT-SHERWOOD-FOREST-001` (кит карты; проп `wanted-post` назови в
  status_note), clip null, cycle `r1`, date `2026-10-21`,
  previous_card null.
- accepted_object: [{"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/SM_Env_SherwoodWantedPost.fbx", "sha256": "0a0e96a026c191cb0d83a1097806b3171638fca551c66996893f0e52ac859b0e"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/T_Env_SherwoodWantedPost_BC.png", "sha256": "8b95fd50bda40d1affb652d2896282708028392a2d26ec8b2817bb41ac7afa67"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/T_Env_SherwoodWantedPost_N.png", "sha256": "a8499c79410b9758c899fddcc5c7ac1716313f79036f74cc89b8aabbc1f00671"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/T_Env_SherwoodWantedPost_ORM.png", "sha256": "eea3bf5052f21b8f7f64b4637577e77a1f117da0abf9d02f87eab4bd6dc4b85d"}]
- frames: {"dir": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/evidence/acceptance/20261021-wanted-post-r1/frames", "files": ["close-base.jpg", "close-head.jpg", "close-weapon.jpg", "frames.json", "sheet.png", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}
- reports: ["art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodWantedPost.build.json", "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/fbx-readback/SM_Env_SherwoodWantedPost.json"]
- executor_session_id `claude-code:mapkits-session/env_kit`; decided_by `delegated: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits)`;
- status_note: короткая фраза по-русски о вердикте («проп принят по делегированию …» или что доработать).
- scores.D = {"value": null, "rationale": "статический проп без рига", "frames": []}.
- В scores.*.frames и known_issues[].frame — только имена из frames.files.
