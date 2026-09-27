# ASSET-MEDUSA-001 · Medusa, кандидат для UE

Состояние 2026-09-27: игровая модель собрана из [платной сегментированной Quad-ретопологии Tripo](../../docs/game-design/evidence/ART-004/tripo-production-20260927/README.md) и проверена в Blender 5.2.2 и Unreal 5.8. Это **кандидат**, а не принятый ART-004: визуальные K1/K2/K3 с HUD, коллизия/выбор на карте и packaged-проверка не проведены. [Диагностика 2026-09-28](../../docs/game-design/evidence/ART-004/face-winding-diagnostic-2026-09-28.md) обнаружила, что видимая лицевая геометрия отсекается в UE односторонним материалом. Исправленный изолированный скелетный FBX показывает лицо, но остаётся слишком контрастным; исходный `SK_Medusa.fbx` не заменён.

По решению пользователя дальнейшая работа над анимациями остановлена до нового пайплайна с видео референсами. [Изолированная сцена Unreal](../../tools/art/art004_scene.py) построена, а четыре текущих AnimSequence численно [проверены](ue-animation-report.json) на движение костей и неподвижный root. Их движение, качество и игровые переходы остаются **непринятыми**; старые кадры UE не служат доказательством качества анимаций.

| Компонент | Проверенный результат |
| --- | --- |
| Геометрия | `SK_Medusa_Body` 18 199 tris, `SK_Medusa_Bow` 1 197, `SM_Medusa_Base` 1 780; сумма **21 176**. Из исходных 15 частей 13 объединены в тело; лук и подставка независимы. |
| Размер | Полная высота 55 uu. Подставка центрирована по XY, Ø30×6 uu. |
| Материал | По одному слоту на меш, единый 2048² атлас BaseColor, DirectX Normal и ORM (R=AO 1.0, G=roughness, B=metallic). `M_Medusa_Atlas` умножает цвет на параметр `TeamColor`; есть синий/красный инстансы. |
| Риг | 17 костей; максимум два влияния на вершину. Лук привязан к `weapon`, подставка статическая. Сокеты `Weapon` и `Head` созданы в UE. |
| Клипы | `Idle` 2,333 с, `LungeAttack` 0,583 с, `HitReact` 0,375 с, `DeathSettle` 0,875 с; смещение root между началом и концом равно 0. |
| UE | Изолированный путь `/Game/ART004/Medusa`; скрипт импорта создаёт текстуры, материал, инстансы, скелетный/статический меш и 4 AnimSequence. `Content/` игнорируется Git, поэтому он воспроизводится скриптом из сохранённых исходников. |

## Воспроизведение

Из корня репозитория:

```powershell
python blender/ASSET-MEDUSA-001/pack_segmented_atlas.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python blender/ASSET-MEDUSA-001/build_segmented_medusa.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python blender/ASSET-MEDUSA-001/verify_segmented_medusa.py
$project = (Resolve-Path 'unreal/Unmatched/Unmatched.uproject').Path
$script = (Resolve-Path 'tools/art/import_medusa_candidate.py').Path
& 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' $project '-run=pythonscript' "-script=$script" '-unattended' '-nosplash' '-nullrhi' '-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False'
```

`pack_segmented_atlas.py` читает неизменённый `tripo-source/b6253e58/medusa-segmented-retopo.glb`, размещает исходные UV-острова в ячейках атласа и сохраняет [раскладку](atlas-report.json). `build_segmented_medusa.py` создаёт [редактируемую сцену](medusa.blend), 6 FBX и [четыре рендера](preview/segmented-Idle.png); [параметры сборки](build-report.json). Повторный импорт каждого FBX в пустой Blender-сеанс записывает [проверку](verify-report.json). Импорт UE сохраняет [результат](ue-import-result.json). Blender переинтерпретирует сантиметровые координаты FBX в метры, а Unreal читает их как uu; обе проверки необходимы.

Текущий лог UE дал **0 ошибок, 2 предупреждения** о близких к нулю тангентах и бинормалях `SM_Medusa_Base`. Внешний вид нормалей и материалов в игровом освещении ещё нужно оценить перед приёмкой. Изолированный рендер Blender показывает текстуры и силуэт, но не доказывает поведение UE. Автоматическая сегментация Tripo сохранила стыки исходных частей; веса назначены по семантическим частям, поэтому сгибы рук/ног и шея требуют отдельного просмотра в анимации крупным планом.

Первое Blender-превью было ошибочно пересвечено: два Area Light стояли на **220/130 Вт** вблизи миниатюры и сделали кожу, ткань и бронзу бледными. Сравнение при неизменных [BaseColor-атласе](textures/T_Medusa_Atlas_BC.png), геометрии, материале и камере показало, что **45/12 Вт** возвращают исходный контраст Tripo. Эти значения сохранены в `.blend` и четырёх превью. Текстуры при исправлении света не перекрашивались; вопрос их читаемости под игровым освещением UE остаётся открытым.

## Следующий контроль ART-004

Разместить кандидата на Cobble City и второй карте; показать K1 обзор, K2 крупный план змей/кистей/лука и K3 выделение, атаку, реакцию и смерть с HUD. Проверить, что `TeamColor` читается для обеих команд, подставка не двигается вместе с ригом, лук следует кисти, коллизия позволяет выбрать фигурку. Затем сделать packaged-замер по GD-058/ACC-022. До этих проверок не подменять рабочую S05-модель автоматически.
