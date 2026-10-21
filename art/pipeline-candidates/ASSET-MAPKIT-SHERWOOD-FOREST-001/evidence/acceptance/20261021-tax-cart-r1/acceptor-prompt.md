# Приёмка пропа кита карты (этап 4 скилла 3d-model-pipeline, ветка prop)

Делегирование пользователя дословно: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits). Трат нет. Ты — независимый приёмщик; файлов не пишешь, скриптов не
запускаешь. Верни карточку `unmatched.asset-acceptance/2` (kind model) структурированным выводом.

## Объект
- Карта: Sherwood Forest (sherwood-forest); проп `tax-cart` — Обоз шерифа / Sheriff's tax cart. Роль в сцене: hero; зона: road; приоритет P1.
- Описание (то, что заказано): sturdy wooden two-wheeled cart with iron-banded strongbox and the Sheriff of Nottingham's red banner pole. Материалы: wood, iron, cloth. Реальный размер ≈ 1.6×2.8×1.8 м; в игре высота 54.0 uu
  (фигура героя 55 uu). Стиль кита: stylized hand-painted tabletop miniature prop, ancient English greenwood of Robin Hood's outlaws, gnarled oak bark, moss, ferns, leather, rough timber, clean readable silhouette, PBR friendly
- Генерация: Tripo «Умная сетка» P2.0 по двум видам Gemini/Tripo Image (front + single); сборка tools/art/env_kit.

## Входы (открой каждый Read-ом целиком)
- Кадры (каталог `art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/evidence/acceptance/20261021-tax-cart-r1/frames/`), открыть обязательно эти 10: sheet.png (картинка, по которой генерировали),
  turn-000.jpg, turn-045.jpg, turn-090.jpg, turn-180.jpg, turn-270.jpg, wire-34.jpg, close-head.jpg (верх 22 %),
  close-base.jpg (низ 22 %), uv-layout.png. Остальные кадры `frames.json#files` (turn-135/225/315, wire-front/back,
  close-weapon) — только если нужны для решения.
- Отчёт сборки: `art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodTaxCart.build.json` (числа топологии, UV, текстур — для гейтов уже посчитаны ниже).

## Гейты (посчитаны по отчёту, перенеси как есть)
{
 "G-TOPO": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodTaxCart.build.json",
  "note": "4456 tris (бюджет env_kit 12000, проп 7000), single_mesh=True",
  "source_defect": null
 },
 "G-UV": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodTaxCart.build.json",
  "note": "UV0 islands 1291, used 0.6831, overlap 0.0",
  "source_defect": null
 },
 "G-TEX": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodTaxCart.build.json",
  "note": "T_Env_SherwoodTaxCart_{BC,N,ORM}.png 2048, N DirectX, ORM.R=1 (без AO)",
  "source_defect": null
 },
 "G-RIG": {
  "status": "n/a",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodTaxCart.build.json",
  "note": "статический проп без рига",
  "source_defect": null
 },
 "G-NAMES": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodTaxCart.build.json",
  "note": "SM_Env_SherwoodTaxCart, M_Env_SherwoodTaxCart",
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
- schema `unmatched.asset-acceptance/2`, kind `model`, asset_id `ASSET-MAPKIT-SHERWOOD-FOREST-001` (кит карты; проп `tax-cart` назови в
  status_note), clip null, cycle `r1`, date `2026-10-21`,
  previous_card null.
- accepted_object: [{"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/SM_Env_SherwoodTaxCart.fbx", "sha256": "988a8694b4e3dfdf19a66ddb3fd090c6859be1675d63a58ba788f974433259a0"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/T_Env_SherwoodTaxCart_BC.png", "sha256": "b5ba3dbb736a04e9fad4c294654417429f19b46a38a99683389f3f393bc0b052"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/T_Env_SherwoodTaxCart_N.png", "sha256": "f21219234e629c16171bef535066da34d06733c7d3c42de3edc9b289581af821"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/export/T_Env_SherwoodTaxCart_ORM.png", "sha256": "2c6f34ec2c66a2a38d8e4069f1d1600b446ffba4c2ebead67294366b7e61edce"}]
- frames: {"dir": "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/evidence/acceptance/20261021-tax-cart-r1/frames", "files": ["close-base.jpg", "close-head.jpg", "close-weapon.jpg", "frames.json", "sheet.png", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}
- reports: ["art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/assets/SM_Env_SherwoodTaxCart.build.json", "art/pipeline-candidates/ASSET-MAPKIT-SHERWOOD-FOREST-001/20261021-smartmesh/reports/fbx-readback/SM_Env_SherwoodTaxCart.json"]
- executor_session_id `claude-code:mapkits-session/env_kit`; decided_by `delegated: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits)`;
- status_note: короткая фраза по-русски о вердикте («проп принят по делегированию …» или что доработать).
- scores.D = {"value": null, "rationale": "статический проп без рига", "frames": []}.
- В scores.*.frames и known_issues[].frame — только имена из frames.files.
