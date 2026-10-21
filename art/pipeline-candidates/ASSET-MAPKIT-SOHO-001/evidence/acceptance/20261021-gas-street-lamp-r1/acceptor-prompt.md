# Приёмка пропа кита карты (этап 4 скилла 3d-model-pipeline, ветка prop)

Делегирование пользователя дословно: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits). Трат нет. Ты — независимый приёмщик; файлов не пишешь, скриптов не
запускаешь. Верни карточку `unmatched.asset-acceptance/2` (kind model) структурированным выводом.

## Объект
- Карта: Soho (soho); проп `gas-street-lamp` — Газовый фонарь / Gas street lamp. Роль в сцене: animated; зона: streets and embankment; приоритет P0.
- Описание (то, что заказано): tall black cast-iron Victorian gas street lamp with fluted column, ladder bar and four-pane lantern. Материалы: cast iron, glass. Реальный размер ≈ 0.5×0.5×3.5 м; в игре высота 105.0 uu
  (фигура героя 55 uu). Стиль кита: stylized hand-painted tabletop miniature prop, Victorian London streets and Thames wharf, sooty brick, cast iron, weathered wood, canvas, clean readable silhouette, PBR friendly
- Генерация: Tripo «Умная сетка» P2.0 по двум видам Gemini/Tripo Image (front + left); сборка tools/art/env_kit.

## Входы (открой каждый Read-ом целиком)
- Кадры: `art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/evidence/acceptance/20261021-gas-street-lamp-r1/frames/` — все файлы из `frames.json#files`: turn-000…315 (8 ракурсов, 45°), wire-front/34/back,
  close-head (верх 22 %), close-weapon (верхняя часть), close-base (низ 22 %), uv-layout.png, sheet.png (виды, по
  которым генерировали: слева front, справа left).
- Отчёт сборки: `art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoGasStreetLamp.build.json` (числа топологии, UV, текстур — для гейтов уже посчитаны ниже).

## Гейты (посчитаны по отчёту, перенеси как есть)
{
 "G-TOPO": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoGasStreetLamp.build.json",
  "note": "5035 tris (бюджет env_kit 12000, проп 3500), single_mesh=True",
  "source_defect": null
 },
 "G-UV": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoGasStreetLamp.build.json",
  "note": "UV0 islands 1019, used 0.6008, overlap 0.0",
  "source_defect": null
 },
 "G-TEX": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoGasStreetLamp.build.json",
  "note": "T_Env_SohoGasStreetLamp_{BC,N,ORM}.png 2048, N DirectX, ORM.R=1 (без AO)",
  "source_defect": null
 },
 "G-RIG": {
  "status": "n/a",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoGasStreetLamp.build.json",
  "note": "статический проп без рига",
  "source_defect": null
 },
 "G-NAMES": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoGasStreetLamp.build.json",
  "note": "SM_Env_SohoGasStreetLamp, M_Env_SohoGasStreetLamp",
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
- schema `unmatched.asset-acceptance/2`, kind `model`, asset_id `ASSET-MAPKIT-SOHO-001` (кит карты; проп `gas-street-lamp` назови в
  status_note), clip null, cycle `r1`, date `2026-10-21`,
  previous_card null.
- accepted_object: [{"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/SM_Env_SohoGasStreetLamp.fbx", "sha256": "a7d7570e1892d7b372d6369bf7e31ed0cc6e4f18525565ff4fa9cc702c90fdff"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/T_Env_SohoGasStreetLamp_BC.png", "sha256": "b49cc160275c02fc47f2dceb9102dfefe5bb30899bd8af5355794c340b5a2584"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/T_Env_SohoGasStreetLamp_N.png", "sha256": "9a514c61c0764d72fa9391f9420dea558410cfb7146696b9f0a1eff9edb1b2d6"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/T_Env_SohoGasStreetLamp_ORM.png", "sha256": "24d7374efcd968be390b96d63b36682d8c55b6dbcb120319761804c09f194414"}]
- frames: {"dir": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/evidence/acceptance/20261021-gas-street-lamp-r1/frames", "files": ["close-base.jpg", "close-head.jpg", "close-weapon.jpg", "frames.json", "sheet.png", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}
- reports: ["art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoGasStreetLamp.build.json", "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/fbx-readback/SM_Env_SohoGasStreetLamp.json"]
- executor_session_id `claude-code:mapkits-session/env_kit`; decided_by `delegated: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits)`;
- status_note: короткая фраза по-русски о вердикте («проп принят по делегированию …» или что доработать).
- scores.D = {"value": null, "rationale": "статический проп без рига", "frames": []}.
- В scores.*.frames и known_issues[].frame — только имена из frames.files.
