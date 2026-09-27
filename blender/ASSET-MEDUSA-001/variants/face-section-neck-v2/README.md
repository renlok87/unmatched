# Medusa · face-section-neck-v2

**Статус:** изолированный технический кандидат для следующего игрового K2. Он продолжает [v1](../face-section-v1/README.md), но не заменяет производственный `export/SK_Medusa.fbx` и не закрывает ART-004/GD-058. Четыре клипа не перерабатывались и не оценивались.

[Сохранённый FBX](SK_Medusa_FaceSectionNeck_v2.fbx) получен из неизменённого `medusa.blend` (SHA-256 `2A2534F89093E2A296D34E5B4DA41290F1549109D6BC2EF4B1BA29CA978ED903`). SHA-256 FBX — `BD125C6BBEB2559B28F6FC4908A1790E0D05FD572B128BD9188C2DAEEA046592`, размер 1 170 156 байт. Тестовый экспорт в игнорируемом `Artifacts` и этот файл совпали по SHA-256. Повторный экспорт может дать другой побайтовый хеш.

Как и v1, модель разворачивает 587 полигонов лица `tripo_part_10` и сохраняет отдельный лицевой слот. Дополнительно развёрнуты 480 полигонов задней поверхности шеи `tripo_part_14` с инверсией их угловых нормалей. Для шеи **не** добавлен материал или слот: оба слота тела в UE используют один и тот же односторонний `MI_Medusa_Blue` с прежними 2K BC/N/ORM. По сравнению с v1 позиции 22 206 вершин тела, UV, индексы материалов и набор из 18 199 треугольников сохранены; изменены только порядок вершин и нормали этих 480 треугольников. Лук — 1 197 треугольников без изменений, риг — 17 костей. Подставка остаётся отдельным ассетом.

[Проверка структуры](../../../../tools/art/art004_verify_neck_candidate.py) сравнивает исходник и оба FBX в Blender 5.2.2; [акт визуальной пробы](../../../../docs/game-design/evidence/ART-004/neck-winding-evaluation-2026-09-28.md) содержит UE-кадры до/после и ограничения. Задний V-образный просвет в диагностическом UE-кадре закрыт; игровой ракурс, HUD, база, другие реальные карты и packaged-проверка ещё не приняты.

Для воспроизведения из корня репозитория:

```powershell
$env:ART004_FACE_RESTORE_NORMALS='1'
$env:ART004_FACE_SLOT='1'
$env:ART004_FACE_NECK_BACK='1'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup 'blender/ASSET-MEDUSA-001/medusa.blend' --python 'tools/art/art004_face_skeletal_export.py'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python 'tools/art/art004_verify_neck_candidate.py'
```

Экспорт пишет в игнорируемый `unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_FaceFixNormalsSlotNeck.fbx`. [UE-скрипт](../../../../tools/art/art004_face_static_ue_capture.py) при `ART004_FACE_NECK_BACK=1` читает сохранённый кандидат из этого каталога вариантов и импортирует его только в `/Game/ArtTests/ART004Face`.

Абсолютные пути для следующего агента: `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx` и `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/neck-winding-evaluation-2026-09-28.md`.
