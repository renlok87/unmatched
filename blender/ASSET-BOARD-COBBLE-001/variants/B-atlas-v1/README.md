# ART-005 · B atlas v1 для Cobble City

**Статус: кандидат покрытия, не принятый материал UE.** После [проверки GD-058](../../../../docs/game-design/evidence/GD-058/acceptance-review-2026-09-27.md) подготовлена отдельная проба, устраняющая видимое повторение одного и того же фрагмента камня на всех 30 клетках. Исходный `cobble-city-probe.blend`, прежние FBX и UE-кадр не перезаписаны.

- [Новый обзорный рендер Blender](board-surface-k1-atlas-B-v1.png) — Cycles CPU, 960×540, 12 samples. На нём нет фигур, зонного слоя и HUD; это просмотр материала, не K1-приёмка.
- [Редактируемая сцена](cobble-city-atlas-B-v1.blend) и [машинный отчёт](build-report.json).
- [FBX-кандидат](export/SM_ART005_BoardCobbleAtlasB_v1.fbx) и [манифест экспорта](export/export-manifest.json): пресет `UM_FBX_v1`, UnitScaleFactor после патча 1.0, 35 частей. Экспорт повторно импортирован в отдельный пустой Blender-сеанс: 35 meshes, 1020 полигонов, UV на всех частях, габариты X=6.56 м, Y=5.56 м, Z=0.36 м. Результат совпадает с повторным импортом старого FBX по числу частей, полигонов и общему габариту; изменены stone diffuse и UV, не геометрия.
- [Один diffuse-атлас](../../textures/T_ART005_CobbleBoardAtlas_B_v1.png) для всей плоскости 5×6: PNG, RGB, 1254×1254, SHA-256 `dd718729bd433d137efb05260d16a768e2dc8856e242011b8cbdf52f6dc8e435`.
- [Скрипт построения](../../../_tools/build_art005_board_atlas_probe.py) изменяет только UV0 тридцати декоративных плиток и изображение stone Base Color в отдельной копии `.blend`. Сохранённая сцена повторно открыта в Blender 5.2.2; все 30 UV-прямоугольников различны, внешний PNG найден.
- [Скрипт FBX-экспорта](../../../_tools/export_art005_board_atlas_probe.py) использует тот же проверенный пресет, что и прежняя проба, и не перезаписывает её файлы.

Прежний стенд наносил разные четверти одного рисунка на каждую плитку и поэтому повторялся на K1. Здесь каждая плитка получает собственную область **одного** изображения по мировым координатам: `U=(X+2.5)/5`, `V=(Y+3)/6`. Игровые hit surfaces и `boardState.cells[].zones` остаются независимыми от декоративного меша. Новый atlas не обязан стыковаться сам с собой при тайлинге, потому что по полю применяется один раз. Каменные формы в новом рендере неповторяющиеся; окончательную читаемость с фигурками, зонной обводкой и светом требуется доказать в UE.

Атлас получен встроенным **ChatGPT imagegen** редактированием [старого stone diffuse](../../../../art/imagegen/mvp-v1/materials/export/T_cobblestone_D_2048.png) с [B · Painted Miniature](../../../../docs/game-design/evidence/ART-002/option-B-painted-miniature.png) только как стилевым референсом. Точный запрос:

> Use case: style-transfer / game environment material edit. Asset type: candidate base-color texture for the entire Cobble City tabletop battlefield, not a screenshot and not a single repeating cell. Input image 1 is the existing gray cobblestone diffuse map: retain the recognizable broad irregular cobblestone material but make a NEW continuous arrangement across the full canvas so that adjacent areas do not repeat the same stones. Input image 2 is the approved B · Painted Miniature style reference: use only its simplified large hand-painted stone planes and calm readable value grouping; do not copy its board, characters, colored blue/red gameplay zones, lights, wood frame, UI, or perspective. Deliver one edge-to-edge orthographic top-down flat albedo painting of weathered gray cobblestone and restrained mortar, suitable to UV-map ONCE across a 5-by-6-cell game board. Variation should be natural across the whole image; no visible 5x6 tile boundaries, no grid lines, no symbols, no text, no objects, no vignette. Neutral cool gray stone with subtle warm gray accents, medium-low micro-detail, clear broad stone forms. Uniform illumination, no cast shadows, no directional highlights, no baked blue/red tint, no reflection. The output is a whole-board unique atlas candidate, not necessarily a seamless repeating tile. Fill the entire image; no margins.

Сохранён только выбранный stone-кандидат. Дополнительная попытка imagegen исправить старое дерево **отвергнута**: после одинакового уменьшения до 1024² отношение скачка на границе к среднему соседнему скачку оказалось X/Y `1.636/3.056` против `1.448/2.289` у старого файла. Это не улучшение бесшовности; в репозитории остаётся прежняя wood-карта. Метод замера: среднее `abs(RGB_edge_A−RGB_edge_B)` / среднее `abs(RGB_neighbor_A−RGB_neighbor_B)`, отдельно по X и Y.

Ограничения перед ART-005/GD-058: атлас 1254², то есть примерно 251×209 исходных пикселей на клетку, и может оказаться недостаточно чётким в K2. Под него не изготовлены согласованные normal/ORM; карты старого повторяемого diffuse к нему **не подходят**. Новый вариант не импортирован в UE, не проверен с шестью фигурами, зонами, HUD, в grayscale/deuteranopia, на другом освещённом поле или на целевом D-07. Ни камера, ни палитра, ни геометрия финальной доски этим пробным рендером не утверждены.

Повторить из корня проекта без изменения старого стенда:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python blender/_tools/build_art005_board_atlas_probe.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python blender/_tools/export_art005_board_atlas_probe.py
```

Абсолютные пути для агента:

- `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/README.md`
- `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/cobble-city-atlas-B-v1.blend`
- `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-BOARD-COBBLE-001/textures/T_ART005_CobbleBoardAtlas_B_v1.png`
- `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/export/SM_ART005_BoardCobbleAtlasB_v1.fbx`
