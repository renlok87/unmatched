# Приёмка пропа кита карты (этап 4 скилла 3d-model-pipeline, ветка prop)

Делегирование пользователя дословно: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits). Трат нет. Ты — независимый приёмщик; файлов не пишешь, скриптов не
запускаешь. Верни карточку `unmatched.asset-acceptance/2` (kind model) структурированным выводом.

## Объект
- Карта: Soho (soho); проп `dock-bollard` — Причальная тумба / Cast-iron dock bollard. Роль в сцене: dressing; зона: embankment; приоритет P0.
- Описание (то, что заказано): squat black cast-iron mooring bollard with rope wrapped around it. Материалы: cast iron, rope. Реальный размер ≈ 0.5×0.5×0.8 м; в игре высота 24.0 uu
  (фигура героя 55 uu). Стиль кита: stylized hand-painted tabletop miniature prop, Victorian London streets and Thames wharf, sooty brick, cast iron, weathered wood, canvas, clean readable silhouette, PBR friendly
- Генерация: Tripo «Умная сетка» P2.0 по двум видам Gemini/Tripo Image (front + single); сборка tools/art/env_kit.

## Входы (открой каждый Read-ом целиком)
- Кадры (каталог `art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/evidence/acceptance/20261021-dock-bollard-r2/frames/`), открыть обязательно эти 10: sheet.png (картинка, по которой генерировали),
  turn-000.jpg, turn-045.jpg, turn-090.jpg, turn-180.jpg, turn-270.jpg, wire-34.jpg, close-head.jpg (верх 22 %),
  close-base.jpg (низ 22 %), uv-layout.png. Остальные кадры `frames.json#files` (turn-135/225/315, wire-front/back,
  close-weapon) — только если нужны для решения.
- Отчёт сборки: `art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoDockBollard.build.json` (числа топологии, UV, текстур — для гейтов уже посчитаны ниже).

## Гейты (посчитаны по отчёту, перенеси как есть)
{
 "G-TOPO": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoDockBollard.build.json",
  "note": "5226 tris (бюджет env_kit 12000, проп 2000), single_mesh=True",
  "source_defect": null
 },
 "G-UV": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoDockBollard.build.json",
  "note": "UV0 islands 64, used 0.6176, overlap 0.0",
  "source_defect": null
 },
 "G-TEX": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoDockBollard.build.json",
  "note": "T_Env_SohoDockBollard_{BC,N,ORM}.png 2048, N DirectX, ORM.R=1 (без AO)",
  "source_defect": null
 },
 "G-RIG": {
  "status": "n/a",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoDockBollard.build.json",
  "note": "статический проп без рига",
  "source_defect": null
 },
 "G-NAMES": {
  "status": "PASS",
  "source": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoDockBollard.build.json",
  "note": "SM_Env_SohoDockBollard, M_Env_SohoDockBollard",
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
- schema `unmatched.asset-acceptance/2`, kind `model`, asset_id `ASSET-MAPKIT-SOHO-001` (кит карты; проп `dock-bollard` назови в
  status_note), clip null, cycle `r2`, date `2026-10-21`,
  previous_card "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/evidence/acceptance/20261021-dock-bollard-r1/card.json".
- accepted_object: [{"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/SM_Env_SohoDockBollard.fbx", "sha256": "24515663f69b96d0abbe4f9451fa244e60bd497f6461b1c44832ef9176ea9174"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/T_Env_SohoDockBollard_BC.png", "sha256": "6836d0da2353212c3fc9d29e9c7b91fcb28e7af2346feb4e650d150fbb7f8248"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/T_Env_SohoDockBollard_N.png", "sha256": "965bfebda08c5ecc1ddc76b64fa2cfc97dd0ec8a2185a8f9f4884fe9012afc0f"}, {"path": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/export/T_Env_SohoDockBollard_ORM.png", "sha256": "a6c2ae7f6f88efefff6dcb4abdf099a4ff4935d2126c403508012bcd16b07339"}]
- frames: {"dir": "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/evidence/acceptance/20261021-dock-bollard-r2/frames", "files": ["close-base.jpg", "close-head.jpg", "close-weapon.jpg", "frames.json", "sheet.png", "turn-000.jpg", "turn-045.jpg", "turn-090.jpg", "turn-135.jpg", "turn-180.jpg", "turn-225.jpg", "turn-270.jpg", "turn-315.jpg", "uv-layout.png", "wire-34.jpg", "wire-back.jpg", "wire-front.jpg"]}
- reports: ["art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/assets/SM_Env_SohoDockBollard.build.json", "art/pipeline-candidates/ASSET-MAPKIT-SOHO-001/20261021-smartmesh/reports/fbx-readback/SM_Env_SohoDockBollard.json"]
- executor_session_id `claude-code:mapkits-session/env_kit`; decided_by `delegated: «Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits)`;
- status_note: короткая фраза по-русски о вердикте («проп принят по делегированию …» или что доработать).
- scores.D = {"value": null, "rationale": "статический проп без рига", "frames": []}.
- В scores.*.frames и known_issues[].frame — только имена из frames.files.
