# ART-005B · самоприёмка B-атласа в Unreal, 2026-09-27

**Решение:** технический импорт кандидата и сравнительный кадр K1 **приняты как проба**. Художественный материал ART-005 и визуальный эталон GD-058 **не приняты**. Эта проверка не меняет статусы задач.

| Проверка | Доказательство | Вывод |
|---|---|---|
| Источник и масштаб | [Манифест FBX](export/export-manifest.json), [отчёт UE](ue-import-report.json) | SHA-256 FBX и атласа совпали. Импортирован один декоративный меш 656×556×36 uu, три секции/слота; размер и поворот сохранены как в старом ART-005. |
| Отделение игрового слоя | [Отчёт UE](ue-import-report.json), уровень `/Game/ArtTests/ART005B/L_ART005_BAtlasProbe` | В копии старого стенда осталось 30 отдельных hit surfaces, 15 blue и 15 red обзорных меток из S04, шесть серых фигур. Декоративный меш имеет `NoCollision`. Цветные метки — данные зон, **не световые секции**. Живой `boardState` и клик не подключены. |
| Вид покрытия | [Исходный UE K1](ue-art005b-k1.png), [вариант с value scale 0,70](ue-art005b-k1-toned.png), [старый K1](../../preview/ue-art005-cobble-k1.png) | Повтор одного и того же рисунка на 30 клетках устранён. Но на обоих новых UE-кадрах крупные светлые пятна камня конкурируют с шестью серыми фигурками; затемнение повышает различимость фигур, не делает материал утверждённым. |
| Материал | [Новая сцена UE](../../../../unreal/Unmatched/Content/ArtTests/ART005B/L_ART005_BAtlasProbe.umap), [скрипт импорта](../../../../tools/art/art005b_import_verify.py) | Новый камень использует только atlas Base Color, roughness 0,86 и временный множитель 0,70. Подходящих к новому рисунку normal/ORM нет. Дерево и нижний блок унаследованы от ART-005; старый шов дерева не устранён. |
| Режим проверки | [Скрипт K1](../../../../tools/art/art005b_capture.py) | Кадр 1920×1080 снят в отдельном Unreal Editor с `t.MaxFPS 30` и `-RenderOffScreen`. Это не packaged 60 FPS и не замер на D-07. HUD, маркеры выбора/цели и K2/K3 отсутствуют. |

**Следующая правка:** спокойнее сгруппировать светлоту камня и убрать его конкуренцию с миниатюрами на K1, закрыть стык дерева, подготовить карты материала, согласованные с новым атласом. Проверить в одной сцене финальную Medusa и маркеры с `boardState`/HUD, затем серые и deuteranopia кадры, K2/K3 и отдельные схемы света Sherwood Forest и T. Rex Paddock. Последние две карты не являются Cobble City: их цветовые зоны и локальный свет нельзя выводить из полос текущего S04-стенда. Закрытие GD-058 требует отдельного packaged-прогона и полного акта по [критериям](../../../../docs/game-design/evidence/GD-058/acceptance-review-2026-09-27.md).

Абсолютные пути для следующего агента:

- `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/ue-art-review-2026-09-27.md`
- `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/ue-import-report.json`
- `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/ue-art005b-k1-toned.png`
- `C:/Users/ren/WebstormProjects/unmached/unmached/tools/art/art005b_import_verify.py`
- `C:/Users/ren/WebstormProjects/unmached/unmached/tools/art/art005b_capture.py`
