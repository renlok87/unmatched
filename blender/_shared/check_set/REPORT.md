# ART-001 — проверочный набор Blender → Unreal Engine

> Сформировано автоматически на Blender 5.2.2 LTS и Unreal Engine 5.8.2. Результат подтверждает технический импортный контракт; художественные размеры серийных моделей остаются открыты до GD-058.

| Проверка | Ожидаемое | Получено | Вывод |
|---|---|---|---|
| Размер куба | 100×100×100 uu | `[100.0, 100.0, 100.0]` | **PASS** |
| Pivot куба | нижний центр | `[-50.0, -50.0, 0.0]` | **PASS** |
| Направление стрелки | наконечник +X, метка +Z | `{'min': [-0.0, -16.0, 0.0], 'max': [100.0, 16.0, 10.0], 'dims': [100.0, 32.0, 10.0]}` | **PASS** |
| Масштаб фигурки | 50 uu ±2 | `[24.0, 24.0, 50.0]` | **PASS** |
| Pivot фигурки | опора, центр клетки | `[-12.0, -12.0, 0.0]` | **PASS** |
| Импорт материала | 1 слот, TeamColor задаётся | `{'slots': 1, 'TeamColor': [0.16, 0.48, 0.95]}` | **PASS** |
| Коллизия выбора | 1 UCX и трассировка попадает | `{'simple_shapes': 1, 'trace_hit': True, 'trace': 'hit'}` | **PASS** |
| Клип: ориентация | без разворота/наклона | `{'bones': ['root', 'hips', 'spine', 'leg_upper_L', 'leg_upper_R', 'leg_lower_R', 'foot_R', 'leg_lower_L', 'foot_L', 'head', 'arm_upper_L', 'arm_upper_R', 'arm_lower_R', 'hand_R', 'weapon', 'arm_lower_L', 'hand_L'], 'count': 17}` | **PASS** |
| Клип: root-движение | 100 uu вдоль +X | `[100.0, 0.0, 0.0]` | **PASS** |
| Нормаль-карта | DirectX, без flip green | `{'compression': '<TextureCompressionSettings.TC_NORMALMAP: 1>', 'srgb': False, 'flip_green': False}` | **PASS** |

## Воспроизводимость

- Исходник: `blender/_shared/check_set.blend`.
- Шаблон скелета: `blender/_shared/rig_template.blend`.
- Пресет: `blender/_tools/presets/UM_FBX_v1.json`.
- Экспорт: `blender/_tools/batch_export.py`.
- Проверка геометрии: `blender/_tools/mesh_report.py`.
- UE-импорт: `tools/art/art001_import_verify.py`.
- Полный прогон: `tools/art/run-art001.ps1`.
- Уровень: `/Game/ArtTests/ART001/L_ART001_Check`.
- Кадр уровня: `preview/ue-art001-overview.png`.
- Визуализация normal buffer: `preview/ue-art001-normal-probe.png`.

Полный машинный результат: `ue-import-report.json`; экспортные хэши: `export/export-manifest.json`. Это редакторный технический gate Q-311; packaged-проверка серийных ассетов остаётся частью QA-009.
