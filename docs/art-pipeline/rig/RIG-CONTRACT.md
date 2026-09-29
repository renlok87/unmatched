# Контракт рига `UM_HUMANOID_17` (v2)

Срез 2026-09-29, волна 4, задача W4-D (меморандум engine-gate §1 п.6). Первая редакция — 2026-09-28, P1.6 (скелет `UM_HUMANOID_17_v1`). Машиночитаемая версия: [rig-contract.json](rig-contract.json) (`unmatched.rig-contract/2`, скелет по умолчанию `UM_HUMANOID_17_v2`). Её читает валидатор клипов.

**Статус: предложено.** Скелет измерен на кандидате ASSET-MEDUSA-001, технически импортирован в UE (`/Game/ART004/Medusa`); Arthur, Merlin и Harpy собраны CLI в UM17 (run `20260928-cli-um-fbx-v1`). Художественно ни риг, ни клипы не приняты. Числа ниже получены на пробах и **не являются бюджетами**.

## 0. Что меняет v2 (2026-09-29)

Все пункты касаются того, что запекается в каждый клип и меш: их дорого менять после 16 клипов ART-006..008 (меморандум: 0,5–1 дня сейчас против 2–4 дней и повторной приёмки позже).

| # | Правило v2 | Проверка | Было в v1 |
| --- | --- | --- | --- |
| 1 | Кость 0 = объект арматуры `SKEL_UM_Humanoid` у всех. `SKEL_Medusa` и другие старые имена — **FAIL** для любого файла, проверяемого по v2 | `validate_clip.py` `armature_object_name` | WARN для старых имён |
| 2 | Скелет v1 закрыт для новых клипов: `--skeleton=UM_HUMANOID_17_v1` даёт WARN `skeleton_version` только файлам из `grandfathered_files` (4 черновика Medusa, `SK_Medusa.fbx`, BVH/GLB-фикстуры P1.6, по sha256), остальным — FAIL | `skeleton_version` | — |
| 3 | Оружие по стороне: `weapon.L` (родитель `hand.L`) или `weapon.R` (родитель `hand.R`), в UE `weapon_L` / `weapon_R`; у героя только своя (`characters`): Medusa — `weapon.L`, Arthur и Merlin — `weapon.R`, Harpy — нет. Одно имя `weapon` — FAIL | `weapon_side`, `skeleton_contract` с `--character` | одно имя `weapon`, родитель по персонажу |
| 4 | Ref-поза по UM_FBX_v1: SK и клипы экспортируются с поворотом +90° вокруг Z (жёстко, с roll); в FBX, открытом в Blender, лицо +X (yaw 0 ± 10°), ось X кости `root` = +Y | `ref_pose_facing` (FAIL), `ref_pose_root_axis` (WARN) | черновики без поворота (лицо −Y в Blender, +Y в UE) |
| 5 | Граница клипа: кадр 0 = rest у всех; последний кадр = rest у `idle` и `oneshot`; `terminal` (DeathSettle) заканчивается финальной позой | `clip_boundary_rest` (`--clip-role`) | не проверялось |
| 6 | Импорт клипа в UE: явная `FbxFactory`, для in place `bForceRootLock=true`, `bEnableRootMotion=false` (`ue_import.clip_import`) | `rig_rules.ue_clip_import_problems` по измеренным свойствам AnimSequence | не задано |
| 7 | Цепочки `ik_chains` для IK Rig / IK Retargeter (Root, Spine, Head, LeftArm, RightArm, LeftLeg, RightLeg, WeaponL/WeaponR), retarget root = `hips` | `tests/test_rig_rules.py` | нет |
| 8 | Профили героев `/4`: Arthur и Merlin с `weapon.R` (номер `/3` занят профилями um-master W4-B) | `tests/test_rig_rules.py`, пробная сборка CLI вне репозитория | `/2` с `weapon` |

Измерено 2026-09-29 (headless Blender 5.2.2): черновики Medusa смотрят в −Y (yaw −90°), ось X `root` = +X; SK Arthur (CLI) и `SK_Medusa_HeadTilt_v31a_UM_FBX_v1.fbx` — yaw 0°, ось X `root` = +Y. У Idle, LungeAttack и HitReact кадр 0 и последний совпадают с rest (0,0), у DeathSettle последний кадр отстоит на 0,512 роста (финальная поза). Прогоны: [validation-rig-v2/summary.json](../animation-library/validation-rig-v2/summary.json) (11 кейсов), пробные сборки профилей `/4` — [evidence/rig-contract-v2-2026-09-29](../evidence/rig-contract-v2-2026-09-29/README.md).

Источники:
- [бриф 18 §9, §10, §12](../../game-design/18-animation-production-brief.md);
- [04-blender-production.md](../../game-design/04-blender-production.md);
- `blender/ASSET-MEDUSA-001/build_segmented_medusa.py` (`make_armature`) и `export/SK_Medusa.fbx`;
- [tools/art/import_medusa_candidate.py](../../../tools/art/import_medusa_candidate.py);
- проба авторига Tripo: [tripo-rig-20260928-p16](../../../art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/README.md).

## 1. Выбор пути: Tripo-риг или Blender-риг

По решению пользователя Tripo — основной путь, поэтому его авториг проверили первым. Проверка шла на уже готовой модели, в трёх вариантах:
1. риг Mixamo, уже бывший в истории сегментированного клона b6253e58;
2. новый принудительный риг UE5 Mannequin на b6253e58;
3. такой же риг на цельной Quad-ретопологии d562f057.

Studio каждый раз предупреждала, что модель не готова к авторигу (нужна T-поза). В исходниках Medusa стоит в позе миниатюры: лук в руке, плащ до земли, корона змей.

| Критерий | Tripo UE5 (b6253e58 / d562f057) | Blender, 17 костей |
| --- | --- | --- |
| Разбор позы | Ноги уходят в корону, голова лежит в корпусе, L/R перепутаны | Соответствует телу |
| Санитарная проба «кость двигает свою часть» | 5 из 7 / 7 из 7 в неверной зоне | 7 из 7 правдоподобны |
| Подставка | Взвешена на бедро и двигается | Отдельный статичный меш |
| Лук | Взвешен на плечо и предплечье, гнётся и отрывается | 100 % на `weapon`, жёстко следует за кистью |
| Кости | 61 (пальцы, twist, clavicle) / 34 в skin | 17, как в брифе и 04 |
| Влияний на вершину | до 6 / до 4 | до 2 |

**Решение (предложено).** Производственная основа — Blender-скелет `UM_HUMANOID_17_v1`. Tripo-авториг для Medusa отклонён по деформациям, а не из предпочтения. Для новых гуманоидов (Arthur, Merlin) Tripo остаётся кандидатом только при условии, описанном в §8.

## 2. Кости и иерархия

Имена в Blender пишутся с суффиксами `.L/.R`. Импортёр UE заменяет `.` на `_`, а объект арматуры становится костью 0, поэтому в UE получается **18 костей**. Позиции ниже измерены на Medusa (голова кости, Blender, см). Фигура 51 см без подставки, в UE 55 uu с подставкой.

**Объект арматуры и кость 0 (предложено).** Имя объекта арматуры одно для всех персонажей скелета: `SKEL_UM_Humanoid` (поле `skeletons.UM_HUMANOID_17_v2.armature_object.name` в [rig-contract.json](rig-contract.json); в v1 то же имя). Legacy FBX-импортёр UE делает из этого объекта кость 0, и она же несёт root motion (§4). Если назвать арматуры по персонажам (`SKEL_Medusa`, `SKEL_Arthur`), кость 0 будет называться по-разному, а это ломает общий UE Skeleton и ретаргет. Версия скелета в имя не входит.

Сейчас имена разные (измерено): `SKEL_Medusa` у ART004 `SK_Medusa.fbx`, его четырёх клипов и кандидата T4 (в UE кость 0 = `SKEL_Medusa`, [отчёт T4](../medusa-local-pass-report.md), находка 2), `SKEL_S05_Medusa` и `SKEL_S05_Mannequin` у S05 ([аудит 2026-09-27, inventory.md](../../research/2026-09-27-animation-audit/inventory.md)). Это старые тестовые ассеты. По v2 `validate_clip.py` (проверка `armature_object_name`) даёт для этих имён **FAIL**; WARN остаётся только при явной проверке старого файла против закрытого v1 (`--skeleton=UM_HUMANOID_17_v1`, файл в `grandfathered_files`). Для BVH и внешних клипов с `--retarget-map` проверка информационная: имя задаётся при перекладке. Переименование Medusa — при её пересборке (решение пользователя о пересборке — меморандум §3 п.5).

| Кость | Родитель | UE-имя | Medusa, голова (x, y, z) | Роль |
| --- | --- | --- | --- | --- |
| объект арматуры `SKEL_UM_Humanoid` (кость 0 в UE) | — | `SKEL_UM_Humanoid` (у Medusa сейчас `SKEL_Medusa`) | 0, 0, 0 | носитель root motion; pose-кости нет, в Blender это объект |
| `root` | объект арматуры (в UE — кость 0) | `root` | 0, 0, 0 | опора на полу; pose-ключи всегда 0 |
| `hips` | root | `hips` | 0, 0, 18 | таз; основной вес плаща/юбки |
| `spine` | hips | `spine` | 0, 0, 24.5 | корпус |
| `head` | spine | `head` | 0, 0, 38.5 | голова и корона |
| `arm_upper.L` / `.R` | spine | `arm_upper_L/R` | ±4.5, 0, 35.5 | плечо (у Harpy — крыло) |
| `arm_lower.L` / `.R` | arm_upper | `arm_lower_L/R` | ±6.8, −1.3…−1.8, 30.5 | предплечье |
| `hand.L` / `.R` | arm_lower | `hand_L/R` | 10, −4.5, 29 / −5, −4.5, 30.5 | кисть без пальцевых костей |
| `leg_upper.L` / `.R` | hips | `leg_upper_L/R` | ±3, 0, 19 | бедро |
| `leg_lower.L` / `.R` | leg_upper | `leg_lower_L/R` | ±3.8, −1.2, 12 | голень |
| `foot.L` / `.R` | leg_lower | `foot_L/R` | ±4, −1.5, 6.5 | стопа |
| `weapon.L` / `weapon.R` (v2) | `hand.L` / `hand.R`; у героя только своя: Medusa `weapon.L`, Arthur и Merlin `weapon.R`, у Harpy нет | `weapon_L` / `weapon_R` | 11.2, −6, 27.5 (Medusa, `weapon.L`) | оружие, жёсткий вес 100 %. В v1 было одно имя `weapon` с разными родителями — в v2 запрещено (§0 п.3) |

Сторона: `.L` — левая сторона персонажа. При взгляде персонажа в −Y это +X в Blender. У Medusa на этой стороне лук.

Пальцев, twist-костей, clavicle и neck в базе **нет** (D-11: «лёгкий риг»). Масштаб всех костей единичный, ключей scale нет. Leaf-кости не экспортируются (`add_leaf_bones=False`).

## 3. Rest pose

Rest pose = bind pose = **поза, в которой смоделирована миниатюра**, а не T/A-поза. Все клипы авторятся относительно неё.

Внешние клипы из Tripo, Mixamo, DeepMotion или SMPL сняты от T/A-позы. Перед ретаргетом им нужна поза соответствия: в Blender это снимок rest-позы целевого рига, в UE — Retarget Pose в IK Retargeter. Иначе вся анимация будет смещена на разницу поз. Это главная причина, по которой внешние клипы требуют ручной доводки (бриф §10).

## 4. Root и root motion

- Носитель root motion — **объект арматуры** `SKEL_UM_Humanoid` (§2). Legacy FBX-импортёр UE превращает его в кость 0. Pose-кость `root` не ключуется (память `ue-pipeline-traps` п.2; измерено в S05: delta pose-кости `root` = 0).
- Политика по умолчанию — **in place**. Смещение объекта арматуры и pose-кости `root` за клип не больше 0,5 % роста. Эту проверку делает `validate_clip.py`.
- Все четыре клипа D-11 делаются in place (бриф §10, ART-004). Перемещение по клетке — скольжение актора (CUE-007), это не клип.
- **Импорт in-place клипа в UE (v2):** явная `FbxFactory`, `bForceRootLock = true`, `bEnableRootMotion = false` (`ue_import.clip_import.by_root_policy.in_place`). Случайный ключ на кости 0 тогда не сдвинет фигуру с клетки и её ClickCapsule. Root motion для отдельного клипа — только по решению: `enable_root_motion=true`, `force_root_lock=false` и `ConsumeRootMotion` в акторе (S08 не ACharacter). Проверка измеренных свойств — `rig_rules.ue_clip_import_problems`; реализация в `import_clips.py` и CLI — задача пайплайна (волна 4, W4-B).

## 5. Оси, масштаб, экспорт

- Blender: 1 unit = 1 м, Z-up, персонаж смотрит в −Y.
- FBX-экспорт (как в `build_segmented_medusa.py`, измерено):

```
apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
axis_forward="-Y", axis_up="Z", add_leaf_bones=False,
bake_anim=True, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
bake_anim_force_startend_keying=True, mesh_smooth_type="FACE"
```

- После экспорта каждого FBX (SK и клипы) `patch_fbx_units()` в `build_segmented_medusa.py` записывает в заголовок `UnitScaleFactor = 1.0` (профиль T4: `data_scale 100`, `unit_scale_factor_patched 1.0`). Измерено на ART004 и T4.
- Один FBX на клип, **с узлом меша**: legacy-импортёр без меша не создаёт AnimSequence (бриф §12).
- UE: legacy FBX (`Interchange.FeatureFlags.Import.FBX=False`), **`import_uniform_scale = 1.0`**. Это измерено для текущего профиля экспорта (`FBX_SCALE_UNITS` + патч `UnitScaleFactor = 1.0`):
  - [tools/art/import_medusa_candidate.py](../../../tools/art/import_medusa_candidate.py) задаёт 1.0 для скелетного меша и подставки (`import_skeletal`, `import_base`); для клипов (`import_clip`) масштаб не задаётся, используется значение по умолчанию;
  - результат: верх `SK_Medusa_Atlas` 55,0 uu (`blender/ASSET-MEDUSA-001/ue-import-result.json`, `height_55uu`), `root_delta_uu = 0` у четырёх клипов (`ue-animation-report.json`); в T4 «коэффициент round-trip 1,0».
- **Конфликт (не применять):** в памяти S05 (`ue-pipeline-traps` п.3) рабочей связкой записано `FBX_SCALE_UNITS` + `import_uniform_scale=100`. Это другой профиль экспорта, без патча `UnitScaleFactor`. С измеренным ART004/T4 он расходится в 100 раз; проверить на UE-этапе. Там же: при `FBX_SCALE_NONE` и scale 1 у кости 0 получается масштаб ×100, и root motion тоже умножается на 100. Ручной Scale при импорте — дефект (04 §1).
- Остальные опции импорта анимаций (например `animation_length`) не проверялись. В контракт входят только те, что задаёт `import_medusa_candidate.py`.
- **Направление «вперёд» — стандарт UM_FBX_v1** ([04 §1](../../game-design/04-blender-production.md), строка «Оси»; решение оркестратора 2026-09-28): лицо −Y в Blender → **+X в UE**. Для статичной стрелки ART-001 это подтверждено (PASS).
- На скелетном Medusa (ART004 и кандидат T4) измерено **+Y**: `ue(x,y,z) = blender(x,−y,z)` ([отчёт T4](../medusa-local-pass-report.md), «Оси»). Это **отклонение от стандарта**, а не вторая норма. Причина установлена на этапе 3: UM_FBX_v1 поворачивает фигуру на +90° вокруг Z в пространстве экспорта (`export_space_rotation_z_degrees: 90`, `candidate_build/core.py` `transform_for_fbx`), а ART004/T4 и четыре черновых клипа экспортированы без этого поворота. Двойник `*_UM_FBX_v1.fbx` и CLI-кандидаты героев смотрят в +X.
- **Правило v2 (ref-поза).** SK и все клипы экспортируются только профилем UM_FBX_v1 с тем же поворотом, что у меша (`skeletons.UM_HUMANOID_17_v2.ref_pose`). В FBX, открытом в Blender, лицо +X: анатомический yaw 0 ± 10° (боковой вектор `.L − .R` по головам `arm_upper` и `leg_upper`), ось X кости `root` = +Y. Клип без поворота на скелете с поворотом даёт расхождение root 90° и до 17,97 uu (p1-evidence §3), поэтому `validate_clip.py` отвергает его (`ref_pose_facing` FAIL). Код S08 (`S08FighterActor.cpp:181–182`, yaw 0/180 в расчёте на +Y) переводится на +X вместе со сменой пути кандидата — отдельная задача, не этот контракт.
- FPS клипов 24 (измерено S05/ART004; в брифе это PROPOSAL, AD-OPEN-46). Допуск длительности ±0,05 с.

## 6. Веса

- Не больше **4 влияний** на вершину, веса нормализованы, невзвешенных вершин нет. Сейчас у Medusa максимум 2.
- **Жёсткие части**: лук — 100 % на `weapon`; подставка **не скинится** и экспортируется отдельным статичным мешем (`SM_Medusa_Base`).
- **Тело Medusa сейчас**: 32 % веса на `hips` (почти весь плащ), 29 % на `head` (голова со змеями). Веса назначены по семантическим частям сегментации Tripo, поэтому при сгибе ноги под плащом возможны пересечения. Для клипов с шагом (LungeAttack, DeathSettle) нужна плавная растяжка, см. §9.3.
- Автоматические веса Tripo для Medusa не годятся: подставка на бедре, змеи на костях голени (§1).

## 7. Сокеты UE

Сокеты создаются скриптом импорта в UE, в Blender их нет.

| Сокет | Кость | Смещение | Примечание |
| --- | --- | --- | --- |
| `Weapon` | v2: `weapon_L` (Medusa) / `weapon_R` (Arthur, Merlin); у Harpy — точка удара когтей по профилю; v1: `weapon` | (0, 0, 0) | кандидат ART004. В S05 сокет был на `hand_L` (0, 2, 0). Сокет живёт на меше (`bAddToSkeleton=false`), общий скелет ему не мешает |
| `Head` | `head` | (0, 0, 4) | кандидат ART004. В S05 было (0, 0, 8) |

Смещение в пространстве кости UE (предложено, CLI 0.5.0, этап 3 T3.3). UM_FBX_v1 не корректирует оси костей (primary Y, secondary X), экспорт поворачивает rest-позу жёстко (`roll=True`), а импорт FBX в UE зеркалит Y каждой локальной трансформы. Поэтому смещение сокета в UE bone space = (x, −y, z) смещения в пространстве кости Blender. С живым замером Medusa это согласуется: UE (0, 0, 4) на вертикальной кости `head` дало точку в 4 uu впереди. Знак вдоль кости (y) пока не измерен. Build героев пишет цель, смещение в кости Blender и прогноз (`sockets[].offset_ue_bone_local_uu_predicted`); ue-import ставит прогноз, если в профиле `location_uu: null`. Head, uu: Arthur (-0,151; 4,127; 0,048) → (-0,151; -4,127; 0,048) (цель в UE (-0,169; 0,151; 49,921)); Merlin (0,019; 2,026; 0,255) → (0,019; -2,026; 0,255) (цель в UE (0,195; -0,019; 37,893)); Harpy (-0,406; 4,028; 2,226) → (-0,406; -4,028; 2,226) (цель в UE (5,232; 0,485; 33,063)). Проверка — живой `get_socket_location(Head)` против цели ±0,05 uu на UE-этапе героев.

## 8. Совместимость с UE Mannequin и автоматическими ригами

- Скелет **не совместим напрямую** с UE5 Mannequin (у Manny около 90 костей) и с Mixamo. Клипы оттуда переносятся только ретаргетом: IK Retargeter в UE или перекладка в Blender. Карты имён лежат в `rig-contract.json` → `retarget_maps` (`tripo_ue5_mannequin_to_um17`, `mixamo_to_um17`, `smpl_to_um17`). Лишние кости (spine_01/02, neck, clavicle, twist, пальцы) сворачиваются в родителя.
- Общий UE Skeleton на всех гуманоидов **не доказан** (бриф §9, п.3). До доказательства каждый персонаж получает свой Skeleton с одинаковыми именами. v2 снимает два известных препятствия: одинаковая кость 0 и оружие по стороне (родитель `weapon` больше не расходится между героями). Общий скелет или `CompatibleSkeletons` — после первого принятого клипа, по прототипу.
- **IK Rig / IK Retargeter (v2).** Автохарактеризация UE 5.8 имена UM17 не знает, поэтому IK Rig UM17 собирается скриптом из `ik_chains` (IKRigController): цепочки Root, Spine (`hips→spine`), Head, LeftArm/RightArm (`arm_upper→hand`, цель — кисть), LeftLeg/RightLeg (`leg_upper→foot`, цель — стопа), WeaponL/WeaponR (одна кость, только FK); retarget root = `hips`. Имена цепочек совпадают с IK Rig UE5 Manny, чтобы AutoMapChains сопоставил их без ручной карты (не проверено в UE). Rest UM17 — поза миниатюры, поэтому нужна retarget pose (AutoAlign). Retargeter — офлайн-инструмент оценки; клип из UE возвращается в FBX/.blend и проходит `validate_clip.py`.
- Правило для любого автоматического рига (Tripo, Mixamo, Meshy, AccuRIG): его нельзя считать универсальным. Он принимается только после `rig_deform_probe.py` (7 проб, все в своей зоне) и просмотра листа. Затем кости переименовываются или ретаргетятся в контракт.
- Условие, при котором Tripo-авториг стоит пробовать снова (предложено): отдельная **A-позная версия** персонажа без оружия. Её генерируют в Tripo ради рига и весов. Затем веса переносятся на меш в позе миниатюры (Data Transfer в Blender), а поза миниатюры становится ключом Idle. Для Medusa это не проверено; пробу стоит сделать на Arthur или Merlin, когда появится их меш.

## 9. Разделы по типам персонажей

### 9.1 Гуманоиды: Arthur, Merlin, торс Medusa

Базовые 16 костей без изменений плюс одна кость оружия по стороне (v2): у Arthur (меч) и Merlin (посох) — `weapon.R` под `hand.R`, у Medusa (лук) — `weapon.L` под `hand.L`. Профили `/4` Arthur и Merlin уже задают `weapon.R` (§12). Посох Merlin выше фигурки на голову, поэтому `weapon.R` у него длинный, но тоже жёсткий.

### 9.2 Harpy (крылья)

Отдельной цепочки крыла нет. Крылья = `arm_upper` / `arm_lower` / `hand` (04, бриф §9). Оружия нет: в v2 у Harpy 16 базовых костей (в v1-профиле CLI кость `weapon` оставлена невзвешенной только ради 17 имён v1 — убрать при пересборке). Имена костей из шаблона сохраняются. Предложенное расширение: листовые `wing_tip.L/R` (родитель `hand.L/R`) для складывания кончика. Гуманоидные клипы на Harpy не переносятся, их авторят отдельно (Cascadeur или Blender). Облачный авториг крыльев нигде не подтверждён (services.md). Физики и cloth нет.

### 9.3 Змеи короны Medusa

База: змеи жёстко на `head` (так сейчас: 29 % веса тела на `head`). На 55 uu змеи видны в основном на K2. Предложенное расширение: до 4 листовых костей `crown_snake.NN` (родитель `head`), только если клип требует вторичного движения. Повороты до 15°. В общий UE Skeleton такие листовые кости добавляются без поломки чужих клипов. Отклонённое ранее расширение короны на 28 % (ART-004) не повторять: это геометрия, а не риг.

### 9.4 Плащ и юбка

База: плащ на `hips`, с плавным переходом на `leg_upper.L/R` у подола (до 4 влияний). Сейчас переход жёсткий, при шаге возможны пробои. Предложенное расширение: `cloth_front` и `cloth_back` (родитель `hips`) — ключевые кости вторичного движения без физики. Chaos Cloth и симуляция вне D-11.

## 10. Проверка соответствия

Все скрипты ниже, кроме `overlay_bones.py` (обычный Python), запускаются **только headless** (`blender -b`): `read_factory_settings` в живом Blender выгружает аддон MCP (так упал :9877), а `os._exit` в `validate_clip.py` завершает весь процесс. Без `-b` скрипт бросает `RuntimeError` и ничего не делает (`if not bpy.app.background: raise RuntimeError(...)`). Аддон MCP вернёт ошибку клиенту, процесс останется жив. `SystemExit`, `sys.exit` и `os._exit` в живом Blender завершают весь процесс, поэтому для такой защиты не годятся (проверка — в [VALIDATION.md](../animation-library/VALIDATION.md)). Для живого Blender есть только `live_view_rig.py`.

- `tools/tripo-pipeline/anim/inspect_rig.py` снимает кости, иерархию, влияния и доли весов.
- `tools/tripo-pipeline/anim/rig_deform_probe.py` + `overlay_bones.py` делают санитарные повороты и лист.
- `tools/tripo-pipeline/anim/validate_clip.py` проверяет клип (или скелетный меш с `--kind=skeletal-mesh`) против контракта: версию скелета, имя объекта арматуры, кости и оружие по стороне (`--character`), ref-позу, границы клипа (`--clip-role`) (см. [VALIDATION.md](../animation-library/VALIDATION.md)). Правила без Blender — `anim/rig_rules.py`, юнит-тесты — `tests/test_rig_rules.py`.
- `tools/tripo-pipeline/anim/run_rig_v2_validation.py` — 11 кейсов v2 (позитивная фикстура `make_fixtures.py rigv2` и негативы) с точным набором FAIL; `run_p16_validation.py` проверяет черновики P1.6 явно против закрытого v1 (`--out-dir` — повтор без перезаписи отчётов P1.6).

## 11. Открытые вопросы (к автору)

1. ~~Отклонение Medusa (+Y) от стандарта UM_FBX_v1 (+X)~~ — причина установлена (нет поворота UM_FBX_v1 при экспорте); правило v2 §5: только UM_FBX_v1. Остаётся перевод S08 на +X вместе со сменой пути кандидата.
2. ~~Родитель `weapon` для правшей~~ — v2: `weapon.R` под `hand.R` (Arthur, Merlin). Смещения сокетов Arthur/Merlin — проверка живым `get_socket_location` на UE-этапе героев.
3. Длительности HitReact (0,4 с в 04 против 0,9 с в CUE-011) и DeathSettle (0,9 против ≤0,95 с).
4. Нужны ли расширения `crown_snake`, `cloth_*`, `wing_tip`. Решать после видео-референсов и первого клипа (листовые кости добавляются постфактум без поломки клипов).
5. Общий UE Skeleton для гуманоидов: доказать на двух мешах (бриф §9, п.2–3; прототип L_AnimProbe меморандума).
6. Имя объекта арматуры `SKEL_UM_Humanoid` (кость 0) — закреплено v2; Medusa переименовать при пересборке (решение пользователя о пересборке — меморандум §3 п.5).

## 12. Переход на v2: что пересобрать (не выполнено в W4-D)

| Ассет | Что сейчас | Что нужно | Как проверить |
| --- | --- | --- | --- |
| ASSET-MEDUSA-001 | `SKEL_Medusa`, `weapon` под `hand.L`, экспорт без поворота UM_FBX_v1 (ART004, T4, 4 черновых клипа) | одна пересборка (меморандум §1 п.9): объект `SKEL_UM_Humanoid`, `weapon.L`, экспорт UM_FBX_v1; 4 черновика переэкспортировать из .blend тем же профилем или списать (клипы не правим). Требует решения пользователя о пересборке | `validate_clip.py --character=Medusa` (клипы) и `--kind=skeletal-mesh` (SK) = PASS |
| ASSET-KING-ARTHUR-001 | CLI `/2`: `weapon` под `hand.R` (кость 0 и ref-поза уже по v2) | новый run по профилю с `weapon.R`: `/4` (ветка W4-D от `/2`) или, после коммита W4-B, `/3` ветки W4-B (`*-um-master.json`) + `weapon.R` под следующим номером; пробная сборка `/4` вне репозитория: 44/44 проверок сборки, v2 PASS | кейс `neg-sk-Arthur-cli-v1-as-v2` → после пересборки PASS |
| ASSET-MERLIN-001 | CLI `/2`: `weapon` под `hand.R` | новый run по профилю с `weapon.R` (как у Arthur: `/4` или `/3` um-master + `weapon.R`); пробная сборка `/4`: 41/41, v2 PASS | кейс `neg-sk-Merlin-cli-v1-as-v2` → PASS |
| ASSET-HARPY-001 | CLI: невзвешенная `weapon` под `hand.L` ради 17 имён v1 | профиль без кости оружия (16 костей), сокет Weapon на `hand_L`/`hand_R` | `--character=Harpy --kind=skeletal-mesh` = PASS |
| UE-импорт клипов | глобальный CVar Interchange, `bForceRootLock` не задан | явная `FbxFactory`, `force_root_lock` по `clip_import` (W4-B) | `rig_rules.ue_clip_import_problems` = [] |
