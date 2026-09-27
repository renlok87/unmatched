# ART-005C · самоприёмка совместного K1, 2026-09-27

**Вердикт:** техническая компоновочная проба в Unreal **принята**; игровой K1, ART-004, ART-005 и GD-058 **не приняты**. Проверка сделана на отдельном уровне `/Game/ArtTests/ART005C/L_ART005C_CombinedReview`, без замены сцены S05 или основной игры.

| Вопрос | Доказательство | Решение |
|---|---|---|
| Одна сцена | [Машинный отчёт](combined-scene-report.json), [сборщик](../../../../tools/art/art005c_scene.py) | На B-атласе стоят одна производственная Medusa, пять серых блок-аутов, 30 отдельных hit surfaces и обзорные 15 blue/15 red меток из текущего S04-контракта. Декоративный меш не перехватывает коллизию. |
| Выбор и цель | [Первый K1](combined-k1-editor-2026-09-27.png), [K1 с контрастными пробными материалами](combined-k1-editor-markers-v2-2026-09-27.png) | Первый тёмный вариант колец почти исчезал на камне. Во втором золотое сплошное кольцо вокруг Medusa и разомкнутый коралловый прицел под Arthur различимы на обзорном кадре. Цвет/эмиссия — предложение для проверки, не утверждённые токены HUD или TeamColor. |
| Статус | Те же K1 и [отчёт позиций](combined-scene-report.json) | Стела, поднятая на 45 uu и сдвинутая на 25 uu от Merlin, стала видна, но выглядит оторванным знаком без иконки и связи с бойцом. Как игровая обратная связь **не принята**; нужен экранный или привязанный к модели знак с проверяемым смыслом. |
| Читаемость модели/поля | [K1 v2](combined-k1-editor-markers-v2-2026-09-27.png), [акт B-атласа](../../../../blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/ue-art-review-2026-09-27.md) | Medusa и её круглая база выделяются на фоне пяти блок-аутов, но крупные светлые камни всё ещё спорят с миниатюрами. Этот кадр не доказывает, что семь змеиных голов, оружие и материалы читаются на K1; для них нужен K2. |
| Игровое поведение | [Скрипт сцены](../../../../tools/art/art005c_scene.py) | Все три маркера поставлены по `fighterId` из зафиксированной фикстуры, но не обновляются из живого `boardState`. В этой композиционной пробе их коллизия отключена; отдельный [UE hit-test прицела](../../../../blender/ASSET-MARKERS-001/ue-hit-report.json) прошёл. Здесь нет клика, HUD, боевого K3, проверки анимации и packaged 1080p/60 на D-07. |

Blue/red линии в этом стенде — **игровые зоны**, полученные из `cells[].zones`, а не источники света. Cobble City здесь имеет один набор редакторных светильников. Референсы других полей показывают иные локальные световые секции; для Sherwood Forest и T. Rex Paddock нужны отдельные кадры с теми же миниатюрами и маркерами. Значения света этого K1 и цвета маркеров остаются пробными.

Следующий проход для художественной приёмки: приглушить камень относительно фигур, решить стык дерева и согласованные N/ORM, разработать статусный знак и HUD, заменить пять блок-аутов или явно зафиксировать разрешение на копии Medusa для раннего gate, затем снять K1/K2/K3 одной сцены с игровыми данными. Работа над анимациями Medusa остаётся остановленной по решению пользователя до нового пайплайна с видео-референсами; кадры текущих клипов не засчитываются как их приёмка. Полный список условия GD-058 — в [акте](../GD-058/acceptance-review-2026-09-27.md).

Для воспроизведения из чистой рабочей копии сначала выполнить [импорт и сборку сцены Medusa](../../../../blender/ASSET-MEDUSA-001/README.md), [импорт B-атласа](../../../../blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/README.md) и [импорт маркеров](../../../../blender/ASSET-MARKERS-001/README.md). UE-ассеты Medusa лежат в игнорируемом `Content/` и восстанавливаются её скриптом. Затем из корня проекта запустить:

```powershell
$repo = 'C:/Users/ren/WebstormProjects/unmached/unmached'
& 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' "$repo/unreal/Unmatched/Unmatched.uproject" -run=pythonscript "-script=$repo/tools/art/art005c_scene.py" -unattended -nosplash -nullrhi -DisablePlugins=Tripo3DUEBridge '-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False'
& 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' "$repo/unreal/Unmatched/Unmatched.uproject" "-ExecutePythonScript=$repo/tools/art/art005c_capture.py" -unattended -nosplash -RenderOffScreen -DisablePlugins=Tripo3DUEBridge '-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False'
```

Абсолютные пути для следующего агента:

- `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-005/combined-acceptance-2026-09-27.md`
- `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-005/combined-k1-editor-markers-v2-2026-09-27.png`
- `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-005/combined-scene-report.json`
- `C:/Users/ren/WebstormProjects/unmached/unmached/tools/art/art005c_scene.py`
- `C:/Users/ren/WebstormProjects/unmached/unmached/tools/art/art005c_capture.py`
