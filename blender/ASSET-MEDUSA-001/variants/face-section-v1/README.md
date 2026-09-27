# Medusa · face-section-v1

Статус: **изолированный кандидат**, не производственный `SK_Medusa.fbx` и не приёмка ART-004/GD-058. [FBX](SK_Medusa_FaceSection_v1.fbx) получен из неизменённого [`medusa.blend`](../../medusa.blend) скриптом [`art004_face_skeletal_export.py`](../../../../tools/art/art004_face_skeletal_export.py) с `ART004_FACE_RESTORE_NORMALS=1` и `ART004_FACE_SLOT=1`. Скрипт разворачивает 587 полигонов `tripo_part_10`, инвертирует их сохранённые угловые нормали и выделяет второй слот. В FBX — 18 199 tris тела, 1 197 tris лука, 17 костей и 2 слота; основание остаётся отдельным ассетом. Анимации не экспортируются и не оцениваются.

Оба слота в UE-пробе получают один и тот же `/Game/ART004/Medusa/Materials/MI_Medusa_Blue`, **односторонний** PBR-материал с тем же 2K BC/N/ORM. Отдельный лицевой шейдер не выбран. [Проверка повторного импорта обоих FBX](../../../../tools/art/art004_compare_face_fbx.py) в Blender показала равные позиции всех 22 206 вершин тела, угловые нормали, UV и индексы вершин треугольников; отличаются лишь индексы материала ровно у 587 полигонов лица. Позиции/UV округлялись до `1e-5`, нормали до `1e-4`. Это сравнение геометрии, не доказательство идентичного поведения в UE.

SHA-256 именно сохранённого FBX: `574460D431D53C4893E23867067AC0F23D13BD0E779596C3110928D66729BD5E` (1 169 836 байт). SHA-256 исходного `.blend`: `2A2534F89093E2A296D34E5B4DA41290F1549109D6BC2EF4B1BA29CA978ED903`. Повторный Blender-экспорт может дать другой байтовый хеш; проверять структуру и рендер, а не равенство его SHA.

[UE-скрипт контрольного кадра](../../../../tools/art/art004_face_static_ue_capture.py) для режима `ART004_FACE_SLOT=1`, `ART004_FACE_RESTORE_NORMALS=1`, `ART004_FACE_SKELETAL=1` импортирует этот сохранённый FBX в тестовую область `/Game/ArtTests/ART004Face`. Он не заменяет производственный `/Game/ART004/Medusa`.

[Акт сравнения в Blender и UE](../../../../docs/game-design/evidence/ART-004/face-section-evaluation-2026-09-28.md) содержит фронтальный, задний и обзорный кадры, а также ограничения. При базовом Cobble лицо слишком тёмное; умеренный перенос существующего общего источника света улучшает чтение, но его позиция не утверждена и в сохранённый уровень не внесена. Настоящие другие карты, игровая камера/HUD и packaged D-07 не проверены.

Для повторного экспорта из корня репозитория на Blender 5.2.2:

```powershell
$env:ART004_FACE_RESTORE_NORMALS='1'
$env:ART004_FACE_SLOT='1'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup 'blender/ASSET-MEDUSA-001/medusa.blend' --python 'tools/art/art004_face_skeletal_export.py'
```

Результат тестового экспорта появится в игнорируемом `unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_FaceFixNormalsSlot.fbx`. Для проверки различий с однослотовым FBX из того же исходника:

```powershell
$env:ART004_FACE_SLOT='0'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup 'blender/ASSET-MEDUSA-001/medusa.blend' --python 'tools/art/art004_face_skeletal_export.py'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python 'tools/art/art004_compare_face_fbx.py'
```

Проверка завершается `ART004_FACE_FBX_COMPARE_OK`, иначе останавливается с ошибкой. Производственный FBX и клипы не перезаписываются. На заднем ракурсе остаётся [унаследованный зазор у шеи](../../../../docs/game-design/evidence/ART-004/face-section-evaluation-2026-09-28.md); вариант не закрывает визуальную приёмку.

Абсолютные пути для следующего агента: `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/variants/face-section-v1/SK_Medusa_FaceSection_v1.fbx` и `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/face-section-evaluation-2026-09-28.md`.
