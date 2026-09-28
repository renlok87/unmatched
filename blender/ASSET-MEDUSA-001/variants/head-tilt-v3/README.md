# Medusa · head-tilt-v3

**Статус:** измерен и технически импортирован в изолированные пути, **художественно не принят**. Решение по [акту самоприёмки](../../../../docs/game-design/evidence/ART-004/head-tilt-v3-self-acceptance-2026-09-28.md) — доработать (v3.1). Этот FBX не заменяет изолированный игровой кандидат [v2](../face-section-neck-v2/README.md) и производственный `export/SK_Medusa.fbx`, не закрывает ART-004/GD-058. Клипы не перерабатывались и не оценивались как анимации.

[Сохранённый FBX](SK_Medusa_HeadTilt_v3.fbx) получен из неизменённого `medusa.blend` (SHA-256 `2A2534F89093E2A296D34E5B4DA41290F1549109D6BC2EF4B1BA29CA978ED903`). SHA-256 FBX — `B9CEA0FE05071B07732B8D72ECC75B074C366BC665679C378CD4E397E1F822A2`, размер 1 176 284 байт. Тестовый экспорт в игнорируемом `unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_HeadTiltProbe.fbx` и этот файл совпали по SHA-256. Повторный экспорт может дать другой побайтовый хеш.

**Что изменено относительно v2.** Экспорт идёт тем же путём, что v2: восстановленные нормали, отдельный слот лица, развёрнутая задняя шея. Дополнительно функция `tilt_head` в [art004_face_skeletal_export.py](../../../../tools/art/art004_face_skeletal_export.py) поворачивает на −15° вокруг X с опорой z = 38,5 см (начало кости `head`) три части вместе с их угловыми нормалями: корону `tripo_part_1` (2 633 полигона), лицо с горлом `tripo_part_10` (587) и заднюю шею `tripo_part_14` (480), всего 4 717 вершин. Воротник `tripo_part_3`, колчан, лук и кисти не тронуты; общих вершин у повёрнутых и неподвижных полигонов нет. Кости и поза покоя не менялись, поэтому сокет `Head` (кость `head` + (0, 0, 4)) за головой не следует: расхождение 1,04 см. Тело — 18 199 треугольников, лук — 1 197, 2 слота тела, 17 костей; UV, winding и индексы материалов как у v2. Высота 55,0 → 54,39 см; это измерение, а не бюджет.

**Итог проверки (измерено, редакторные кадры).** В K2 видно больше лица: пикселей черт лица +54 %. Средний градиент яркости на пиксель вырос только на 4…8 %, то есть выигрыш в площади, а не в детализации. Дефекты:

- P1 — сквозной просвет у основания шеи спереди, 23 → 82 мм² в орто-виде;
- P2 — зазор корона → колчан 1,07 → 0,31 см, в черновом HitReact до 40 пересекающихся пар;
- P2 — сокет `Head` не следует за наклоном.

Сзади новых дыр нет. Пороги для v3.1 и диагностическая проба плавного перехода описаны в акте.

**Импорт в UE.** Изолированный кандидат `/Game/ArtPreview/Medusa/Meshes/SK_Medusa_HeadTilt_v3Candidate` со своим Skeleton создан [UE-скриптом](../../../../tools/art/art004_import_v2_game_candidate.py) при `ART004_GAME_VARIANT=head-tilt-v3` в Content арт-worktree ([отчёт импорта](../../../../docs/game-design/evidence/ART-004/head-tilt-v3-game-import-report.json)). Подставка берётся уже сохранённая `SM_Medusa_Base_v2Candidate` без реимпорта. Проверочные ассеты `/Game/ArtTests/ART004_V3Review` лежат только в Content главного checkout.

**Решение A1 по uasset v3 (2026-09-28): в git не добавлять, force-add не делать.** `Content/` в `.gitignore`. Девять uasset `/Game/ArtPreview/Medusa` (кандидат v2, его Skeleton, подставка, материалы, текстуры) добавлены принудительно, потому что их загружает режим `-ArtPreview` в `S08BoardActor.cpp` для живого packaged-превью ([live-artpreview-run](../../../../docs/game-design/evidence/ART-004/live-artpreview-run/)). На v3 в `unreal/Unmatched/Source` и `Config` ничего не ссылается; из скриптов путь uasset задан только в скрипте импорта. `DefaultGame.ini` всегда кукает весь `/Game/ArtPreview/Medusa` (`DirectoriesToAlwaysCook`), поэтому закоммиченный v3 попал бы в каждую packaged-сборку. v3 художественно не принят и будет заменён v3.1, а FBX и скрипт импорта лежат в git. Поэтому 5,3 МБ бинарников отклонённой пробы в историю не идут. Локальные файлы в Content арт-worktree, для опознания:

| Файл | Байт | SHA-256 |
| --- | --- | --- |
| `SK_Medusa_HeadTilt_v3Candidate.uasset` | 5 268 450 | `CB8E421EBE048BF4673EFCBE108E4824915E72AB7DBAC18C3F6DDA7C1465BEDF` |
| `SK_Medusa_HeadTilt_v3Candidate_Skeleton.uasset` | 5 267 | `9F53CB6E98354A998735400995918ABAA906F06CC4979A3825411950D0B8B1F8` |

После удаления арт-worktree этих файлов больше нигде не будет. Если v3 понадобится в главном checkout, его импортируют заново тем же скриптом, в отдельном процессе при закрытом редакторе этого проекта:

```powershell
$env:ART004_GAME_VARIANT='head-tilt-v3'
& 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' "$PWD/unreal/Unmatched/Unmatched.uproject" -run=pythonscript "-script=$PWD/tools/art/art004_import_v2_game_candidate.py" -unattended -nosplash -nullrhi -stdout -FullStdOutLogOutput -DisablePlugins=Tripo3DUEBridge '-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False'
Remove-Item Env:ART004_GAME_VARIANT
```

Это те же аргументы, что в журнале импорта арт-чата. Скрипт проверяет SHA-256 FBX, берёт материалы из `/Game/ArtPreview/Medusa` и перезаписывает [отчёт импорта](../../../../docs/game-design/evidence/ART-004/head-tilt-v3-game-import-report.json). Побайтное совпадение нового uasset с прежним не проверялось, сравнивать нужно по отчёту импорта (кости, сокеты, слоты, размеры подставки). После импорта нужно проверить `git status`: в прошлый раз у закоммиченного `SM_Medusa_Base_v2Candidate.uasset` изменилось время записи, но содержимое совпало с git-блобом `39e31b74`.

Для воспроизведения из корня репозитория:

```powershell
$env:ART004_FACE_RESTORE_NORMALS='1'
$env:ART004_FACE_SLOT='1'
$env:ART004_FACE_NECK_BACK='1'
$env:ART004_HEAD_TILT_DEG='-15'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup 'blender/ASSET-MEDUSA-001/medusa.blend' --python 'tools/art/art004_face_skeletal_export.py'
Remove-Item Env:ART004_HEAD_TILT_DEG
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python 'tools/art/art004_head_tilt_v3_measure.py'
```

Экспорт пишет в игнорируемый `unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_HeadTiltProbe.fbx`; в этот каталог файл копируется вручную. Скрипт измерений проверяет SHA-256 входов и то, что сохранённый FBX совпадает с поворотом исходника (расхождение не больше 0,01 uu, измерено 1·10⁻⁵).

Абсолютные пути для следующего агента: `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx` и `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/head-tilt-v3-self-acceptance-2026-09-28.md`.
