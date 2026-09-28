# Medusa · head-tilt-v3.1a (выбранный вариант v3.1)

**Статус:** измерен в Blender (без интерфейса и в живом Blender), FBX экспортирован детерминированно. Это **предложенный** кандидат для UE-проверки T4.1 (три света, игровой импорт). В UE не импортировался, **художественно не принят**. Изолированным игровым кандидатом до акта T4.1 остаётся [v2](../face-section-neck-v2/README.md). Производственный `export/SK_Medusa.fbx`, ART-004, K2 и GD-058 не затронуты. Решение и все числа — в [акте T1.2](../../../../docs/game-design/evidence/ART-004/head-tilt-v31-self-acceptance-2026-09-28.md).

| Файл | Байт | SHA-256 |
| --- | --- | --- |
| [`SK_Medusa_HeadTilt_v31a.fbx`](SK_Medusa_HeadTilt_v31a.fbx), игровой кадр (лицо +Y в UE, как v2/v3) | 1 176 892 | `cce200693c4985363caf85343ffa6a3220facf6a5d6716c733faf29ba5ab310c` |
| [`SK_Medusa_HeadTilt_v31a_UM_FBX_v1.fbx`](SK_Medusa_HeadTilt_v31a_UM_FBX_v1.fbx), двойник по стандарту осей 04 §1 (лицо +X) | 1 173 900 | `b49a2c1b6c2f9c4031b157a43464ab2333c55bbcbe4b4623c8c5cb2c1c151b84` |
| [`SK_Medusa_HeadTilt_v31a.json`](SK_Medusa_HeadTilt_v31a.json), отчёт экспорта (параметры, проверки) | — | `74b9759562fcbde482f7452d79fbbec9f9ce9fca85f0fbb5b0e03207b6545983` |

Источник — неизменённый `medusa.blend` (`2a2534f8…d903`), только чтение. Повторный экспорт, в том числе из другого каталога, даёт побайтно те же три файла (проверено).

## Что изменено относительно v2

Путь экспорта тот же, что у v2 (восстановленные нормали, отдельный слот лица, развёрнутая задняя шея). Дополнительно:

- **Winding частей 8 и 13** (рука с луком и наруч — 575 полигонов, правая кисть — 607) развёрнут, угловые нормали инвертированы, как в T4-кандидате (замечание A5). Ray-escape: −0,9997 → 0,9994 и −0,997 → 0,997.
- **Поле наклона** [art004_head_tilt_v31_field.py](../../../../tools/art/art004_head_tilt_v31_field.py), пресет `a`: поворот вокруг X с опорой в начале кости `head` (0; 0; 38,5 см). Угол лица, горла, задней шеи и короны нарастает smoothstep от 0 при z = 38,5 см до −16° при 42 см. Над 47 см угол плавно ослабевает к −10° у макушки 55 см, поэтому верх остаётся 54,72 см, а не 54,39, как у v3. Верхняя полоса воротника `tripo_part_3` поворачивается частично. Спереди, под пластиной горла, угол нарастает на 38–40,5 см, сзади — на 38,5–43 см; переход по y от −1 до +1,5 см. Плечи ниже 38 см не двигаются. Колчан `tripo_part_7` жёстко отклонён вокруг центра нижнего конца: −6° вокруг X (верх назад) и −4° вокруг Y (верх наружу).
- **Split-нормали по вершинам:** n' = normalize(J⁻ᵀ n), J — аналитический якобиан поля в вершине угла (сверка с центральными разностями: 3,9·10⁻⁶).
- **Экспорт по UM_FBX_v1** (−Y вперёд, Z вверх, `FBX_SCALE_UNITS`, данные ×100, `UnitScaleFactor` = 1,0, **Triangulate вкл.**: геометрия не меняется, всё уже треугольники). Отклонения от пресета:
  1. нет поворота +90° вокруг Z: игра ставит yaw 0/180 для меша, смотрящего в +Y (`S08FighterActor::ApplyFighter`); двойник `_UM_FBX_v1` лежит рядом;
  2. `path_mode = RELATIVE` вместо `AUTO`, иначе в FBX попадает абсолютный путь checkout;
  3. детерминированный писатель: фиксированное время, UUID от sha256, путь `ApplicationNativeFile` относительно репозитория.

Кости, веса, UV, индексы материалов, два слота тела, 18 199 + 1 197 треугольников — как у v2. Лук, кисти и руки не сдвинуты (0 вершин).

## Импорт в игру (T4.1, не выполнялся)

[`art004_import_v2_game_candidate.py`](../../../../tools/art/art004_import_v2_game_candidate.py) принимает только `face-neck-v2` и `head-tilt-v3`. Для v3.1 в T4.1 нужно добавить вариант `head-tilt-v3.1`: путь этого FBX, `EXPECTED_FBX_SHA256 = cce20069…310c`, имя меша (например `SK_Medusa_HeadTilt_v31Candidate`) и отчёт `head-tilt-v31-game-import-report.json`. Совместимость проверена без UE:

- те же имена объектов (`SKEL_Medusa`, `SK_Medusa_Body`, `SK_Medusa_Bow`);
- 17 костей с той же rest-позой;
- 2 слота тела;
- тот же масштаб и `UnitScaleFactor`;
- лицо −Y в данных FBX, в UE +Y, как у v2;
- подставка — прежний `SM_Medusa_Base`.

Слоя тангентов в FBX нет, как у v2 и у производственного FBX. Сокет `Head`: [предложение в контракте рига](../../../../docs/art-pipeline/rig/rig-contract.json) (`ue_import.socket_proposals`) — смещение, при котором сокет следует за наклоном, (0; 1,103; 3,845) в осях кости Blender. Цель в компоненте UE — (0; 3,845; 39,603). Смещение в осях кости UE подобрать и проверить в T4.1.

## Воспроизведение

Из корня репозитория, Blender 5.2.2 без интерфейса:

```powershell
$env:ART004_FACE_RESTORE_NORMALS='1'; $env:ART004_FACE_SLOT='1'; $env:ART004_FACE_NECK_BACK='1'
$env:ART004_HEAD_TILT_V31='a'; $env:ART004_V31_UM_FBX_V1='1'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup 'blender/ASSET-MEDUSA-001/medusa.blend' --python 'tools/art/art004_face_skeletal_export.py'
Remove-Item Env:ART004_HEAD_TILT_V31, Env:ART004_V31_UM_FBX_V1
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python 'tools/art/art004_head_tilt_v3_measure.py' -- --v31
```

Экспорт пишет прямо в этот каталог (FBX и JSON). Измерение проверяет SHA-256 входов и то, что сохранённый FBX совпадает с полем, применённым к исходнику: позиции — до 1·10⁻⁵ uu, нормали — p99,9 0,017°.

Абсолютные пути: `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/variants/head-tilt-v31-a/SK_Medusa_HeadTilt_v31a.fbx`, акт — `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-004/head-tilt-v31-self-acceptance-2026-09-28.md`.
