# ART-004 · самостоятельная приёмка пробы змеиной короны

**Вердикт: пробу расширения короны отклонить.** Изолированный FBX успешно импортирован в UE и отрисован в фиксированной перспективной камере D-10 при трёх условиях света. Корона стала шире, но перекрытие змеиных голов осталось, а верхний силуэт стал чрезмерно горизонтальным. Исходный кандидат Medusa v2 остаётся игровым кандидатом; ART-004, K2 и GD-058 этой проверкой не закрыты. Пользователь делегировал художественный выбор и приёмку, поэтому это решение принято без ожидания отдельного утверждения.

## Что проверено

| Условие | Кадр K2, 1920×1080 | Наблюдение |
| --- | --- | --- |
| Cobble | [Раскрытая корона](crown-spread-probe-2026-09-28/cobble-k2.png), [метаданные](crown-spread-probe-2026-09-28/cobble-report.json), [исходный v2 при тех же настройках](medusa-frozen-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-ue-editor-2026-09-28.png) | Боковые головы разошлись, но центральные и правые по-прежнему сливаются. Лицо, лук и база не стали заметно яснее. |
| Зелёно-янтарный стресс-свет | [Кадр](crown-spread-probe-2026-09-28/forest-probe-k2.png), [метаданные](crown-spread-probe-2026-09-28/forest-probe-report.json) | Силуэт верхней части остаётся плоским веером, отдельные головы пересекаются. |
| Сине-индиговый стресс-свет | [Кадр](crown-spread-probe-2026-09-28/paddock-probe-k2.png), [метаданные](crown-spread-probe-2026-09-28/paddock-probe-report.json) | Читаемость голов не восстановилась сменой светового профиля. |

Это один и тот же участок Cobble City 5×6, три варианта освещения. Два цветных профиля — [проверенные стресс-условия ART-005I](../ART-005/lighting-stress-review-2026-09-28.md), **не** сцены Sherwood Forest или T. Rex Paddock. Цветные полосы обозначают игровые зоны, а не секции освещения.

Скрипт [пробы исходных частей](../../../../tools/art/art004_probe_parts.py) измерил в исходном .blend: корона `tripo_part_1` — 2633 полигона, 3555 вершин, диапазон X от −10,413 до +6,301 см, Z от 40,576 до 55 см; все её вершины привязаны к кости `head`. Лицо `tripo_part_10` — 587 полигонов, X от −4,723 до +0,505 см, Z от 38,483 до 47,662 см. Корона топологически соединена после сопоставления совпадающих позиций; семи независимых островов, которые можно было бы безопасно просто раздвинуть, нет. Это объясняет, почему равномерная деформация не заменяет адресной правки каждой змеи.

Экспортёр [art004_face_skeletal_export.py](../../../../tools/art/art004_face_skeletal_export.py) применил к короне пробное горизонтальное расширение 28% с плавным переходом от Z=40,5 до 47,5 см. Лицо и шея получили уже проверенную правку нормалей v2; UV, веса и скелет скрипт не редактировал. Отчёт экспортёра: тело 18 199 треугольников, лук 1197, 17 костей, два слота тела. FBX сохранился только в игнорируемом `unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_CrownSpreadProbe.fbx` (SHA-256 `F72B52D434408BF85A19106A187183E801691E7C384D3334466FB070A7646A62`); после очистки Artifacts его нужно воспроизвести скриптом. Исходный `medusa.blend` остался с SHA-256 `2A2534F89093E2A296D34E5B4DA41290F1549109D6BC2EF4B1BA29CA978ED903`, сохранённый FBX v2 — `BD125C6BBEB2559B28F6FC4908A1790E0D05FD572B128BD9188C2DAEEA046592`.

Кадры получены [скриптом UE](../../../../tools/art/art004_face_static_ue_capture.py): FOV 35°, Pitch −55°, Yaw −90°, дистанция 300 uu, отключённая автоэкспозиция, исходные PBR-материалы, отдельная подставка. Экспорт воспроизводится с `ART004_FACE_RESTORE_NORMALS=1`, `ART004_FACE_SLOT=1`, `ART004_FACE_NECK_BACK=1`, `ART004_CROWN_SPREAD=0.28`; захват — с теми же первыми тремя флагами, `ART004_FACE_CROWN_PROBE=1`, `ART004_FACE_SKELETAL=1`, `ART004_FACE_ADD_BASE=1`, `ART004_FACE_VIEW=d10-k2`, `ART004_FACE_D10_DISTANCE=300`, `ART004_FACE_REPOSITION_AMBIENT=1`, `ART004_FACE_AMBIENT_Y=100`, `ART004_FACE_AMBIENT_Z=500`, `ART004_FACE_AMBIENT_SCALE=1`; `ART004_FACE_LIGHT_PROFILE` меняется между `cobble`, `forest-probe`, `paddock-probe`. Три запуска UnrealEditor-Cmd завершились кодом 0 и маркером `ART004_FACE_STATIC_UE_CAPTURE_COMPLETE`. Это **редакторная** проверка статической позы в контрольном уровне без живого HUD и `boardState`; анимации не проверялись.

## Следующая правка модели

Нужна адресная перепостановка или перескульпт отдельных голов и оснований змей с отрицательным пространством между ними в проекции D-10. Сохранить широкую «змеиную» корону, лицо, лук и подставку как главные признаки Medusa. Не требовать буквального пересчёта семи голов в K1: [производственная карточка](../../04-blender-production.md) требует читаемую корону, а не семь независимых пиктограмм. Число семь остаётся свойством текущего концепта и полезным контролем на крупном виде.

Новый кандидат проверить в такой последовательности:

1. Чёрные силуэты спереди, сбоку, сзади и из D-10 при K1 и K2: верх отличим от шлема Arthur и крыльев Harpy; в K2 у голов есть зазоры без слияния в горизонтальную полосу.
2. UE PBR и подставка при Cobble, зелёно-янтарном и сине-индиговом свете: лицо, лук, кисти и змеи читаются без персонального источника света или запечённых цветов игровых зон.
3. Тот же кандидат в живой packaged K1/K2 с HUD и `boardState`, затем QA-009/010 и D-07 на целевом классе ПК перед пересмотром GD-058.

Зум 300 uu и параметры света здесь — **условия диагностики**, не утверждённый финальный масштаб/свет. Производственный FBX, игровой кандидат v2, материалы, клипы и игровая сцена не заменены.

Абсолютные пути после интеграции в `fix/admin-panel`:

- Акт: `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/crown-spread-self-acceptance-2026-09-28.md`
- Cobble K2: `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/crown-spread-probe-2026-09-28/cobble-k2.png`
- Зелёно-янтарный K2: `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/crown-spread-probe-2026-09-28/forest-probe-k2.png`
- Сине-индиговый K2: `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/crown-spread-probe-2026-09-28/paddock-probe-k2.png`
- Исходный кандидат v2: `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx`
- Скрипты: `C:/Users/ren/WebstormProjects/unmached/unmached/tools/art/art004_probe_parts.py`, `C:/Users/ren/WebstormProjects/unmached/unmached/tools/art/art004_face_skeletal_export.py`, `C:/Users/ren/WebstormProjects/unmached/unmached/tools/art/art004_face_static_ue_capture.py`
