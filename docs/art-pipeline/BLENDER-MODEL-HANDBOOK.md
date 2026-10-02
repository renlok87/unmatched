# Хендбук исполнителя: модель в Blender для Unmatched (герой и пропс)

Срез 2026-10-02. Документ для модели-исполнителя, которая получает задачу «сделать модель» и доводит её от входных
картинок до проверенного импорта в Unreal. Он сводит в одно место правила, разбросанные по
[PIPELINE.md](PIPELINE.md), [ADDING-AN-ASSET.md](ADDING-AN-ASSET.md), [rig/RIG-CONTRACT.md](rig/RIG-CONTRACT.md),
[animation-library/README.md](animation-library/README.md), [material-library/](material-library/README.md) и коду
`tools/tripo-pipeline/`. Там, где эти источники расходятся, здесь указано, что действует сейчас (раздел 10).

Граница ответственности исполнителя: **Blender → FBX и текстуры → импорт в UE → технические проверки в редакторе**.
Художественная приёмка, кадры packaged-live для K1–K3/GD-058 и решения о бюджетах — не его зона.

---

## 0. Как работать по этому документу

1. **Выполнять буквально.** Каждый шаг даёт проверяемый результат (файл, отчёт, PASS). Нет результата — шаг не сделан.
   Любое отступление от текста записывается в отчёт с причиной.
2. **Останавливаться, а не обходить.** Правила остановки — раздел 0.3. Ослабить проверку, порог или профиль, чтобы
   «прошло», запрещено: упавшая проверка — это данные для решения, а не помеха.
3. **Статусы только такие:** предложено → измерено → технически импортировано → художественно принято. Исполнитель
   ставит максимум «технически импортировано». Слова «принято», «готово к игре», «art-approved» в отчётах не писать.
4. **Числа из отчётов — измерения, не бюджеты.** Бюджеты 04 §1 / 17 §4.5 остаются предложением до решения GD-058.
5. **Источник истины при расхождении** (по убыванию): код и машиночитаемые контракты
   (`docs/art-pipeline/rig/rig-contract.json`, `blender/_tools/presets/UM_FBX_v1.json`,
   `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp`) → профиль последнего успешного прогона того же вида →
   этот документ → `ADDING-AN-ASSET.md`/`PIPELINE.md` → старые стандарты `docs/game-design/04`, `17`.

### 0.1 Что запрещено всегда

- Тратить кредиты Tripo/SYNTX без явного лимита в задаче (цена — с кнопки **до** клика).
- Получать байты (FBX, PNG текстур, .blend для коммита) из живого Blender. Всё производственное — только headless.
- В живом Blender: `bpy.ops.wm.read_factory_settings`, `SystemExit`, `sys.exit`, `os._exit` — они выгружают аддон MCP
  или убивают Blender пользователя.
- Запускать `UnrealEditor-Cmd` на главном проекте, пока открыт GUI-редактор.
- Убивать редактор UE (особенно с dirty-пакетами), сохранять `/Game/S08/S08Arena`, менять class default objects.
- Трогать чужое: `/Game/ART004`, `/Game/ArtPreview`, `blender/ASSET-MEDUSA-001/` (старый путь, не переписывать),
  закоммиченные run-каталоги и профили других героев, сцены пользователя в Blender.
- Править закоммиченный профиль, по которому уже был прогон: новая версия — **новый файл** (`history.previous`).
- Править общий код пайплайна (`tools/tripo-pipeline/**`) так, что меняется поведение для уже собранных героев.
  Новое поведение — только опцией профиля со старым значением по умолчанию + повтор детерминизма на Medusa
  (`--compare-with`, раздел 4.5).
- `git add -A`, `git add .`, `git stash`, `git reset`, `git clean`, push.

### 0.2 Окружение

Рабочая оболочка — Git Bash, корень главного checkout `C:/Users/ren/WebstormProjects/unmached/unmached`:

```bash
export MSYS_NO_PATHCONV=1      # иначе /Game/... превращается в C:/Program Files/Git/Game/...
export PYTHONIOENCODING=utf-8  # отчёты содержат кириллицу и ≤/≈; cp1251-консоль падает на print
T="python tools/tripo-pipeline/tripo_pipeline.py"
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
"$B" --version | head -1        # ожидается: Blender 5.2.2 LTS
git -c core.longpaths=true status --short
python -c "import numpy, PIL, scipy; print('deps ok')"
```

| Что | Значение |
|---|---|
| Blender | 5.2.2 LTS, `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`. Код использует API 5.x (layered actions `action.layers→strips→channelbags`, `mesh.corner_normals`); на 4.x не запускать |
| Headless-вызов | `"$B" -b --factory-startup --python-exit-code 1 --python <script> -- <args>` |
| Blender MCP (живой) | `127.0.0.1:9876` (иногда `:9877`), клиент `C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py`. Только осмотр (раздел 6) |
| Unreal | UE 5.8.2, проект `unreal/Unmatched`, редактор с MCP `127.0.0.1:8123`. Проверка: `netstat -ano \| grep ':8123 .*LISTEN'`. Запуск (если задача разрешает): `UnrealEditor.exe <Unmatched.uproject> -ModelContextProtocolPort=8123 "-ExecCmds=ModelContextProtocol.StartServer 8123" -log`, записать PID |
| Блокировка редактора | `C:/tmp/ue-editor.lock` через `tools/art/material_library/ue_lock.py`; одна UE-операция (один герой или один клип) на одну блокировку |
| Python | 3.10+, numpy, Pillow, scipy (scipy нужен look-dev стадиям H2) |

### 0.3 Правила остановки

Остановиться, записать причину и числа в отчёт, ничего не обходить, если:

1. Цена операции Tripo выше остатка лимита задачи, или две неудачные генерации подряд.
2. `prepare-generation --dry-run` вернул код 3: такие входы уже генерировались.
3. Любая стадия завершилась с ошибкой, проверка дала FAIL, CLI вернул код 1 (проверка), 3 (конфликт), 4 (блокировка),
   5 (нужен `resume`). Сначала разобрать причину по разделу 7.
4. Нарушен контракт рига: не 17 костей (16 у Harpy), кость 0 не `SKEL_UM_Humanoid`, больше 4 влияний, масштаб кости ≠ 1.
5. В целевой папке UE чужие ассеты или дубли `Name_1`; что-то изменилось в `/Game/ART004` или `/Game/ArtPreview`.
6. Редактор упал или висит в модальном диалоге. Не повторять ту же операцию; прочитать
   `unreal/Unmatched/Saved/Crashes/*/Unmatched.log`, записать инцидент.
7. Задача требует решения, которого нет в документе: смена бюджета, новый класс MatID, иной цвет команды, новая кость,
   отказ от проверки. Это вопрос к владельцу, а не выбор исполнителя.

---

## 1. Какой путь выбрать

| Что делаем | Путь | Инструмент, который пишет байты |
|---|---|---|
| **Герой** (скинованная фигура на подставке, 4 клипа) | H2 bake → look-dev → TeamAccent → H2Anim → UE `skeletal-adopt` | `tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py` + `tools/tripo-pipeline/anim/h2anim_run.py` |
| **Оружие героя** | часть героя, не отдельный ассет: меш в скелетном FBX, 100 % на кости оружия | тот же H2 bake |
| **Статический пропс** (бочка, фонарь, ящик, декор) | `static_prop_candidate.py` → CLI `static-candidate` | `tools/tripo-pipeline/blender/static_prop_candidate.py` |
| Подставка героя | часть героя (`SM_<Hero>_<Stage>_Base`), отдельный статичный FBX без скина | H2 bake |
| Окружение/карты | **не этот документ** (отдельный трек ENV-MAPS, `tools/art/env_kit/`) | — |
| **Путь B (эксперимент):** модель с нуля в Blender по чертежам Codex, без Tripo | спецификация → сетка → виды `image_gen` → `build_<key>.py` → проекция текстур → риг/клипы/UE по этому документу | [SCRATCH-MODEL-PIPELINE.md](SCRATCH-MODEL-PIPELINE.md), инструменты `tools/scratch-model/` |

**Не использовать как образец для новых работ:**

- `blender/ASSET-MEDUSA-001/build_*.py` (Tier A): без поворота UM_FBX_v1 (фигура смотрит в +Y), арматура `SKEL_Medusa`,
  кость `weapon` без стороны, `nodes.get("Principled BSDF")` (ломается на локализованном UI). Только история.
- `art/pipeline-candidates/ASSET-*/scripts/build_*_candidate.py`: запись прогонов 2026-09-28, CLI их не вызывает.
- CLI-профиль `skeletal-candidate` (`flow seated-parts`, `*-segmented-skeletal-um-fbx-v1*.json`): рабочий, но даёт
  кандидатов поколения до H2 (2K атлас из сегментированной ретопологии Tripo). Новые герои идут через H2.
- Каталоги `h2_bake_arthur/`, `h2_bake_merlin/`, `h2_bake_harpy/`: ручные форки под конкретного героя. Читать как
  примеры решений (ремонт, крылья, посох), не запускать для нового героя.

---

## 2. Контракт: числа, которые нельзя нарушать

### 2.1 Единицы, оси, pivot

| Правило | Значение |
|---|---|
| Единицы в Blender | 1 unit = 1 м, Metric, Unit Scale 1.0. Клетка доски = 1 м = 100 uu |
| Лицо в Blender | **−Y**, Z вверх. Сторона `.L` персонажа = +X Blender (при взгляде в −Y) |
| Лицо в FBX и UE | **+X** (экспорт поворачивает на +90° вокруг Z). В FBX, открытом в Blender: yaw 0 ± 10°, ось X кости `root` = +Y |
| Зеркало UE | `ue(x, y, z) = blender_export(x, −y, z)` |
| Pivot | центр низа подставки = (0, 0, 0). Для пропса — центр основания, низ на z = 0 |
| Трансформы | rotation и scale применены; отрицательного масштаба нет |
| Масштаб импорта в UE | **1.0**. Ручной Scale при импорте — дефект. 100 даёт ×100 на кости 0 |

### 2.2 Экспорт UM_FBX_v1

Пресет `blender/_tools/presets/UM_FBX_v1.json` (проверен ART-001 на Blender 5.2.2 → UE 5.8.2). Исполнитель его не
пишет руками: его применяет `candidate_build/core.py` (`transform_for_fbx`, `export_fbx`, `patch_fbx_units`).

| Параметр | Значение |
|---|---|
| Поворот пространства экспорта | +90° вокруг Z; кости — `EditBone.transform(m, scale=False, roll=True)`, матрица поворота снапнута к точным целым (иначе cos 90° = 6e-17 переворачивает нормали тонких треугольников) |
| Масштаб данных | ×100 во временной копии, `apply_unit_scale=True`, `apply_scale_options="FBX_SCALE_UNITS"`, затем в заголовок FBX пишется `UnitScaleFactor = 1.0` |
| Оси | `axis_forward="-Y"`, `axis_up="Z"`, `primary_bone_axis="Y"`, `secondary_bone_axis="X"` |
| Меш | `use_triangles=True`, `mesh_smooth_type="FACE"`, `colors_type="SRGB"`, `use_custom_props=False` |
| Кости | `add_leaf_bones=False` |
| Анимация (только клипы) | `bake_anim=True`, `bake_anim_step=1.0`, `bake_anim_simplify_factor=0.0`, `bake_anim_use_all_bones=True`, `bake_anim_use_nla_strips=False`, `bake_anim_use_all_actions=False`, `bake_anim_force_startend_keying=True` |
| Пути | пресет говорит `AUTO`, сборка ставит **`STRIP`**, `embed_textures=False` (текстуры идут в UE отдельно; это записанное отклонение, не ошибка) |
| Детерминизм | время FBX = 2000-01-01, UUID через стабильный SHA-256-хеш, `bpy.data.filepath` пуст перед экспортом (иначе абсолютный путь .blend попадёт в `ApplicationNativeFile`) |

### 2.3 Имена

| Объект | Имя |
|---|---|
| contentKey (реестр, lowercase) | `medusa`, `king-arthur`, `merlin`, `harpy` |
| UE-ключ (PascalCase, без пробелов) | `Medusa`, `KingArthur`, `Merlin`, `Harpy` |
| Стадия | `H2LD` (у Harpy `H3LD`) |
| Объект арматуры | **`SKEL_UM_Humanoid`** у всех героев (становится костью 0 в UE) |
| Скелетный FBX | `SK_<Hero>_H2.fbx` (bake), после look-dev `SK_<Hero>_H2LD.fbx` |
| Подставка | `SM_<Hero>_H2_Base.fbx` / `SM_<Hero>_H2LD_Base` |
| Клипы | `AM_<Hero>_{Idle,LungeAttack,HitReact,DeathSettle}.fbx`, в UE без суффикса `_Anim` |
| Текстуры (bake) | `T_<Hero>_H2_{BC,N,N_OpenGL,ORM,TeamMask}` (4K) + `T_<Hero>_H2_2K_*` |
| Текстуры (look-dev) | `T_<Hero>_H2LD_2K_{BC,N,ORM,MatID,Edge}`, `T_<Hero>_H2LD_TeamAccent_2K.png`, `T_UM_MatLUT_<Hero>.dds` |
| Материал-слот | один на меш, например `M_Medusa_H2_Atlas` |
| MI в UE | `MI_<Key>_<Stage>_P1`, `_P2`, `MI_<Key>_<Stage>_Base_P1`, `_Base_P2` (+ `_Neutral`, `_DebugClass`) |
| Пропс | `SM_<Name>`, текстуры `T_<Name>_{BC,N,ORM}`, материал `M_<Name>` |

Запрещено: id из базы (cuid) в именах ассетов; суффикс `_RM` для текстур (см. 2.4); одно имя `weapon` для кости.

### 2.4 Текстуры

| Карта | Каналы | Цветовое пространство | UE: компрессия | Примечание |
|---|---|---|---|---|
| BC | RGB | sRGB | `TC_Default` | glTF `baseColorFactor ≠ 1` умножается в BC в линейном свете |
| N | tangent | linear | `TC_Normalmap`, `flip_green=false` | **DirectX** (G = 255 − G от OpenGL/glTF). `N_OpenGL` — служебная копия для Blender |
| ORM | R = AO, G = Roughness, B = Metallic | linear | `TC_Masks` | **не RM**: RM из glTF — промежуточная карта, перепаковывается в ORM с запечённым AO в R |
| MatID | 1 канал | linear | `TC_Grayscale`, Nearest, NoMipmaps, NeverStream | значение = класс × 16 + 8; классы 1–15 — `material-library/README.md`; 0 = «как запечено» |
| EdgeMask | 1 канал | linear | `TC_Grayscale` | |
| TeamAccent | 1 канал, 8 бит | linear | `TC_Grayscale`, обычные мипы | UV0; см. 2.9 |
| LUT | 16×16 RGBA16F | — | `TC_HDR`, Nearest, без мипов | `T_UM_MatLUT_<Hero>.dds` |

Размеры: герой — **4K master (локально, не в git) + 2K runtime (в git)**, 2K = точный 2×2 box-downsample.
Пропс — 1K–2K (`texture_size` в params; фонарь 1024). Blender пишет в PNG чанки sRGB/gAMA: для N и ORM их снимает
сборка, но решает всё равно настройка импорта в UE.

Материальные правила (С-3, библиотека материалов): roughness ≥ 0,6 на ≥ 90 % площади; metallic ровно 0 или 1;
металл BC = эталон F0 ± 0,02 при Y ≥ 0,45; диэлектрик BC: Y в [0,02; 0,9]. Tripo часто делает золото и сталь
неметаллом (metallic ≈ 0,07–0,095) — исправляется металл-маской (`textures` стадия: metallic 0,9–1, roughness
0,32–0,45 на металле).

### 2.5 Материалы и слоты

- Фигура: **1 слот** (тело и оружие делят атлас). Подставка: 1 слот. Пропс: 1 слот, максимум 2 (второй — свечение,
  `glow_slot`).
- В UE мастер фигуры `/Game/UM/Materials/v2/M_UM_Figure_v2` (v2.1), подставки `M_UM_BaseMarker`. Static switches
  `UseUV1Metres=true`, `UseTeamAccent=true`. Substrate выключен.
- UV: **UV0** = атлас, **UV1_m** = UV в метрах с центрами островов в (0, 0) (нужен детальным тайлам). У подставки в UE
  выключить Generate Lightmap UVs, иначе UV1 перезапишется.
- Коллизий `UCX_/UBX_/UCP_/USP_` в FBX **нет** (решение волны 4): выбор фигуры — капсула в коде по bounds меша.
- LOD: не генерируются, в FBX только LOD0.

### 2.6 Риг `UM_HUMANOID_17_v2`

Контракт — `docs/art-pipeline/rig/rig-contract.json` (его читает валидатор).

```
SKEL_UM_Humanoid (объект арматуры = кость 0 в UE, носитель root motion; pose-кости нет)
└─ root                    (опора, ключей нет никогда)
   └─ hips
      ├─ spine
      │  ├─ head
      │  ├─ arm_upper.L → arm_lower.L → hand.L [→ weapon.L]
      │  └─ arm_upper.R → arm_lower.R → hand.R [→ weapon.R]
      ├─ leg_upper.L → leg_lower.L → foot.L
      └─ leg_upper.R → leg_lower.R → foot.R
```

| Правило | Значение |
|---|---|
| Кости | 16 базовых + 1 кость оружия своей стороны: Medusa `weapon.L`, Arthur и Merlin `weapon.R`, Harpy — нет (16). В UE `.` → `_` и плюс кость 0: 18 костей (17 у Harpy) |
| Запрещено | пальцы, twist, clavicle, neck; одно имя `weapon`; масштаб кости ≠ 1; leaf-кости |
| Rest pose | = поза миниатюры (как смоделирована фигура), **не** T/A-поза |
| Веса | ≤ 4 влияния, нормализованы, невзвешенных вершин нет, веса < 0,01 удаляются, затем снап к сетке 1/255 |
| Жёсткие части | оружие 100 % на кости оружия; подставка не скинится и уходит отдельным FBX |
| Голова кости оружия | в точке хвата: туда встанет сокет `Weapon` (0, 0, 0) |
| Расширения (только по решению) | `crown_snake.NN` (≤ 4, ≤ 15°), `cloth_front/back`, `wing_tip.L/R` |
| Harpy | крылья = цепочка `arm_upper → arm_lower → hand` |
| Новый H2LD-меш | точно та же иерархия, что у существующего канонического скелета героя в UE |

### 2.7 Сокеты

Сокеты создаёт UE-импорт, **в Blender их не делать**.

| Сокет | Кость | Смещение |
|---|---|---|
| `Weapon` | `weapon_L` / `weapon_R` (у Harpy по профилю — `foot.R`, удар когтями; контракт говорит про кисть — расхождение открыто) | (0, 0, 0) |
| `Head` | `head` | прогноз сборки (`location_uu: null`); UE bone-space = (x, −y, z) от Blender bone-space × 100 |

Проверка: живой `get_socket_location` против цели ± 0,05 uu. Фигура без сокета `Head` выпадает из evidence-съёмки
(`S08FlowGameMode.cpp`).

### 2.8 Клипы

| Клип | Кадры (N, 24 fps) | Длительность | Роль | Последний кадр |
|---|---|---|---|---|
| Idle | на героя: Medusa 56, Arthur 60, Merlin 72, Harpy 48 | 2–3 с | idle (петля) | = rest, шов петли гладкий |
| LungeAttack | 14 | 0,583 с | oneshot | = rest |
| HitReact | 10 | 0,417 с (длительность открыта) | oneshot | = rest |
| DeathSettle | 21 | 0,875 с (открыта) | terminal | финальная поза |

Общее: кадр 0 = rest у всех; клипы **in place** (объект арматуры и pose-кость `root` не ключуются, дрейф ≤ 0,5 %
роста); ключи `rotation_quaternion` на всех костях кроме `root`, `location` только на `hips`; интерполяция LINEAR;
один FBX на клип, **обязательно с узлом меша** (без меша legacy-импортёр не создаёт AnimSequence); допуск длительности
±0,05 с в Blender и ±0,02 с в автотесте UE. Длины LungeAttack/HitReact/DeathSettle зашиты в C++ одинаковыми для всех
героев (`S08HeroesV2.cpp`, `ExpectedClipSeconds`).

### 2.9 TeamColor (решение пользователя 2026-09-29: «акценты + кольцо»)

- Герой остаётся в цветах концепта. Цвет команды — только на кольце/подставке и на **акцентах одежды** (кант, пояс,
  кушак, подкладка, лента). Старая маска «вся одежда» (`TeamMask`) устарела, её место занял `TeamAccent`.
- Покрытие TeamAccent: 5–12 % площади фигуры (исключение Arthur 3,56 %). На каждой части основного цвета ≤ 20 %.
- Никогда не красить: металл, камень, дерево, кожу персонажа, рога и когти, узорную отделку (кант — снаружи узора с
  зазором ≥ 3 мм).
- Палитра: P1 `#E8C06A`, P2 `#5A7F9F` (в С-11 всё ещё `#9FC2D8` — устарело). Hex → linear только
  `FLinearColor::FromSRGBColor` / `um_masters.hex_to_linear`; `hex/255` запрещён.
- Номер экземпляра (Harpy ×3) — на подставке (вершинная маска + `InstanceIndex`), не на фигуре.

### 2.10 Высоты и бюджеты

Высоты зашиты в `S08HeroesV2.cpp` (таблица `Specs()`); автотест требует, чтобы масштаб коррекции был в пределах 1 %,
то есть верх фигуры из Blender должен попасть в бюджет с точностью 1 %.

| Герой | Бюджет, uu | Допустимо | Верх фигуры (без оружия) | Верх bounds | Idle, с |
|---|---|---|---|---|---|
| King Arthur | 55 | 52–56 | 55,0 | 60,06 (меч) | 2,5 |
| Merlin | 45 | 40–48 | 44,986 | 49,42 (посох) | 3,0 |
| Medusa | 55 | 50–55 | 55,009 | 55,01 | 56/24 |
| Harpy | 42 | 35–42 | 42,0 | 42,0 | 2,0 |

Высота меряется от низа подставки (z = 0) до верха фигуры по профильной части (`scale.figure_top_m`, например 0,55);
оружие выше фигуры проверку не валит. Подставка: Ø 0,30 × 0,06 м у Medusa/Arthur (5–6 uu высотой). Отношение высот
помощник/герой = 0,78 ± 0,06 (автотест).

Треугольники (измерено, **не бюджет**): Medusa 43 054 (тело 38 054 + лук 5 000), Arthur 38 684, Merlin 33 967,
Harpy 37 177; подставки 864–2 240. Предложение 04: герой 15–25k, помощник 8–15k — решение за GD-058. Практика H2:
целиться в 30–45k на героя, 20–30k на Harpy-подобных, подставка ~1,2–2k. Выход за 45k — записать в отчёт, не резать
молча.

---

## 3. Входы: концепт и Tripo

### 3.1 Концепт-виды

Концепт — входной комплект для Tripo **и** эталон всех сравнений (look-dev по зонам, превью «концепт | модель»).
Пайплайн его не рисует: концепты делаются генератором изображений до Tripo.

**Где лежат и какого формата (герои H2/H3).** `art/imagegen/hero-quality-v1/<hero>/<hero>-{front,side,back}.png` +
`prompts.md`. PNG RGB без альфы, портретный (или широкий у крылатых) кадр одного размера внутри комплекта (Medusa
1021×1540, Arthur/Merlin 1190×1322, Harpy 1470×1070), ровный тёмно-серый фон, вся фигура с подставкой, без обрезки,
текста и перспективы. Требование «1024×1024, `#808080`, базовая линия y = 917» и `check_inputs.py` относятся к старым
входам `art/imagegen/mvp-v1` (эпоха CLI): скрипт проверяет только манифест mvp-v1, на hero-quality-v1 его не запускать.

**Как делались (рецепт hero-quality-v1, 2026-09-29).** Инструмент — встроенный `image_gen.imagegen` в Codex
(`transparent_background: false`, один вызов на изображение, PNG копируется без правки пикселей). Computer use не
нужен. Виды рисуются **поверх ортопроекций черновой модели**, иначе front/side/back расходятся по силуэту и Tripo
строит фантомы:

1. Черновая модель: дешёвая генерация Tripo (или кандидат прошлого поколения) → headless-рендеры
   `ortho_front`, `ortho_left`/`ortho_right`, `ortho_back` (ортокамера, нейтральный свет, тот же кадр).
2. **front**: image_gen, режим style-transfer/edit. Изображение 1 — `ortho_front` черновика (цель редактирования:
   сохранить силуэт, позу, пропорции, хват оружия, подставку); изображение 2 — эталон качества
   `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` (уровень детализации расписанной миниатюры,
   фон, свет, размещение подставки).
3. **side** и **back**: то же, изображение 1 — `ortho_left`/`ortho_back` черновика, изображение 2 — уже готовый
   `<hero>-front.png` (личность, костюм, цвета), для back можно третьим добавить side.
4. В промпте явно: строгий профиль/вид сзади, «no three-quarter», тот же фон, тот же масштаб и место подставки в кадре
   (в процентах кадра), «no perspective, text, watermark, cropping or added anatomy», оружие не придумывать заново.
5. `prompts.md`: дата, инструмент, для каждого вида — файл, `referenced_image_paths` по порядку, **точный** отправленный
   промпт, раздел «Проверка и ограничения» (что совпало, что изменилось между видами). Образцы — `prompts.md` четырёх
   героев.

Если у исполнителя нет `image_gen` (не Codex): SYNTX MCP `generate-image` с референс-изображениями (сервисы с
редактированием по образцу, например banana/seedream; стоимость и лимит — по задаче) по тому же рецепту. Нет ни того,
ни другого — остановка: концепты даёт пользователь.

**Проверка комплекта перед Tripo** (глазами + записать в `prompts.md`): одна фигура и одна подставка на кадр; ракурсы
строгие; фон ровный; оружие и его сторона совпадают во всех видах; на side видна та же рука с оружием, что и на
front; нет лишних конечностей и голов. Риск: серый камень на сером фоне — Tripo срезает край.

### 3.2 Генерация в Tripo Studio (только при лимите в задаче)

Пропустить целиком, если исходники уже оплачены и лежат в `source-spec` (0 кредитов).

1. Реестр: запись в `docs/art-pipeline/asset-registry.json`, `python tools/tripo-pipeline/validate_registry.py` →
   `RESULT PASS`.
2. Сухой пакет входов: `$T prepare-generation --run-dir <run> --dry-run --service tripo-studio --mode multi-view
   --model-label "H3.1" --view front=<png> --view left=<png> --view back=<png>`. Код 3 = дубль → остановка.
   Черновая модель для концептов (3.1, шаг 1) — отдельная дешёвая операция (single-image или multi-view без 8K и без
   «по частям»); её GLB и списание тоже записываются в журнал кредитов.
3. Настройки **героя** (H2/H3): «Приватный», multi-view (не batch), H3.1;
   - FRONT = front, **LEFT = side**, BACK = back, RIGHT пусто. Side в слот RIGHT → Tripo зеркалит вид и строит
     фантомы (второй меч, вторая рука и лицо у Arthur, двуликая голова у Harpy);
   - «по частям» Balance, ultra mesh 2M, triangles, без текстуры (60 кредитов);
   - затем текстура 8K с «убрать освещение» (30), затем PBR (5).
4. Настройки **пропса**: multi-view, H3.1, текстура 2K, PBR, Triangle, 8K и «по частям» выключены.
5. После каждой операции — баланс и строка истории в `evidence/<asset>-<дата>/tripo-run.json` и в журнал кредитов
   (`tools/art/syntx_video_refs/ledger_append.py`).
6. Загрузка GLB: Chrome оставляет `C:/Users/ren/Downloads/<guid>.tmp`. Проверить длину из заголовка GLB = размер файла,
   пройти все чанки; скопировать в `art/pipeline-candidates/<ASSET-ID>/<date>-h2-tripo/source/` как
   `<asset>-tripo-<task8>-parts<N>.glb` и `<asset>-tripo-<task8>-tex8k-pbr.glb`. Свой Save-диалог закрыть до передачи
   браузера. Одна загрузка за раз.
7. Вернуть настройки Studio (они сохраняются на аккаунт) и закрыть вкладку.

Tripo-авториг **не использовать** (5/7 и 7/7 деформационных проб в неверной зоне; подставка на бедре).

### 3.3 Source spec

`art/pipeline-candidates/<ASSET-ID>/source-specs/tripo-<task8>.json`, схема `unmatched.tripo-pipeline.source-spec/1`
(образец — соседние spec героев; поля — PIPELINE.md, «Source spec»): задача, модель, режим, операции со списаниями,
файлы с `role` и `expected_sha256`. Оригиналы лежат **вне** run-каталога CLI. Сырые GLB героев (45–79 МБ) в git не
коммитятся — в чистом checkout `preflight` их прогонов падает; это известно, не чинить.

---

## 4. Герой: H2 bake → look-dev → TeamAccent → H2Anim → UE

Образец всех профилей — Medusa (`art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/`). Генерический `h2_bake`
профильный: имя героя в коде встречается только в метках проб (`medusa-h2-blend`/`medusa-h2-fbx` в
`run_h2_bake.py:102`, косметика имён отчётов) и в примерах.

### 4.1 Каталоги и имена прогонов

```
art/pipeline-candidates/<ASSET-ID>/
  source-specs/tripo-<task8>.json
  build-profiles/<hero>-h2-bake-h2.json, <hero>-h2-lookdev.json, <hero>-h2-lookdev-teamaccent.json,
                 <hero>-h2anim.json, <hero>-h2ld-lookdev-ue-import.json
  <YYYYMMDD>-h2-bake/      export/ textures/ preview/ reports/ (в git) + work/ logs/ (не в git)
  <YYYYMMDD>-h2-lookdev/
  <YYYYMMDD>-h2anim/
  <YYYYMMDD>-h2ld-<...>-ue/
```

Новый прогон — всегда **новый** run-каталог. Закоммиченный каталог под другой конфиг не переиспользовать.

### 4.2 Профиль H2 bake

Скопировать `medusa-h2-bake-h2.json` в `<hero>-h2-bake-h2.json` и пройти каждый ключ. Ничего не оставлять «как у
Medusa» без проверки, что это верно для нового героя.

| Ключ | Что задать | Подводные камни |
|---|---|---|
| `profile_id`, `asset_id`, `status`, `history` | свой id `<hero>-h2-bake/1`; `status: "предложено"`; `history.previous_profiles` | — |
| `sources` | `source_spec`, `parts_glb`, `tex_glb` (пути и sha256 из spec) | две GLB должны иметь **одинаковую** геометрию по частям; prepare это проверяет |
| `expected_part_count`, `parts` | число частей Tripo и роль каждой (тело, лицо, кисти, оружие, подставка) | части нумеруются Tripo произвольно — роли определять по превью, а не по номеру |
| `scale` | `figure_top_m` = бюджет / 100 (0,55 для 55 uu), `base_diameter_m`, `base_height_m` | высота — по фигуре, не по оружию |
| `orientation` | `method` ray-escape, `samples_per_part 4000`, `seed 0`, `flip_below_score -0.5`, `min_score_after_fix 0.5`, `expected_inside_out_parts` — **пустой до первого прогона** | первый prepare перечислит вывернутые части и откажет; список переносится в **новый** файл профиля, порог не ослабляется |
| `retopo` | `method` COLLAPSE, `target_tris` по частям (крупные части первыми), `dense_regions` (лицо ~1 600 tris), `cleanup`, `caps` | сумма → 30–45k на героя; лицо, кисти, оружие получают приоритет |
| `closure` | `contact_caps` по петлям, которые открываются в позах | у Medusa 19 крышек; видимость крышек в rest ≤ 0,01 % и ≤ 9 px |
| `uv` | `atlas_px 4096`, `runtime_px 2048`, `min_gap_px 8`, `pack_margin_fraction 0.0013`, `max_overlap_px 0`, `texel_priority` (лицо ×2, кисти ×1,75, оружие ×1,5, подставка ×0,45) | Smart UV запрещён (5 402 острова у Medusa); только charts (Voronoi + MINIMUM_STRETCH) |
| `bake` | `device`, `resolution 4096`, AO (128 samples, distance 0,044 м = 0,08 × рост), `cage` (1,5 × p99 отклонения, 0,6–4 мм, `max_ray_factor 2.5`), `ao_exclusions` (AO части без загораживающей части, которая в анимации отходит — кулак Medusa у пояса) | `device: "GPU"` (Medusa): FBX повторяются байт в байт, а N/ORM расходятся в 1–3 пикселях на 1–2 уровня; `CPU` (Merlin) бит-стабилен, но медленнее. Выбор записать в отчёт |
| `textures` | `prefix T_<Hero>_H2`, `maps`, `ao_gate`, металл-маска, `edge_extend_px 16` | — |
| `rig` | `skeleton UM_HUMANOID_17_v2`, `armature_object SKEL_UM_Humanoid`, `character <Hero>`, `max_influences 4`, `clean_below 0.01`, `bones` (голова/хвост каждой кости по геометрии героя), `weights` (`chain`, `zblend`, `cloth`, `rigid`), `junctions`, `seam_pairs` | кости ставить по геометрии нового героя; копия координат Medusa = гарантированный FAIL проб |
| `sockets` | `Weapon` на кости оружия, `Head` на `head`, `location_uu: null` | — |
| `exports` | `fbx_preset blender/_tools/presets/UM_FBX_v1.json`, `skeletal_fbx SK_<Hero>_H2.fbx`, `base_fbx SM_<Hero>_H2_Base.fbx` | — |
| `meshes`, `materials` | какие части → body/weapon/base; один слот | — |
| `axes` | `blender_front -Y`, `expected_ue_front +X`, сторона оружия | — |
| `preview` | `concepts` (пути концепта), камеры K2 | — |

Оружие: если Tripo не смоделировал рукоять внутри кулака (Arthur) или древко (Merlin), нужен мост-цилиндр или сборка из
частей (`split-from-part` / `parts` в CLI-пути). В генерическом `h2_bake` такого режима нет — если оружие героя без
хвата, это остановка с описанием (решения — в `h2_bake_arthur/repairs.py`, `h2_bake_merlin/`).

### 4.3 Прогон стадий

Запускать **по одной стадии** и читать отчёт после каждой. `all` — только для повтора уже отлаженного профиля.

```bash
P=art/pipeline-candidates/<ASSET-ID>/build-profiles/<hero>-h2-bake-h2.json
R=art/pipeline-candidates/<ASSET-ID>/<YYYYMMDD>-h2-bake
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --profile $P --run-dir $R --stages prepare
# затем retopo, close, uv, bake, aux, textures, rig, probes, seams, preview, compose, manifest
```

Каждая Blender-стадия — отдельный процесс `blender -b --factory-startup --python-exit-code 1 --python
h2_bake/blender_entry.py -- work/params/<stage>.json`, лог в `logs/<stage>.log`, маркер успеха
`H2_BAKE_STAGE_OK <stage>`. **Успех = код 0 + маркер в логе + нет `Traceback`.** Blender 5.2.2 может напечатать при
выходе 0–20 строк `Windows fatal exception: access violation` с кодом 0 — это шум, если маркер есть.

| Стадия | Что делает | Что проверить в результате | Типичный отказ → действие |
|---|---|---|---|
| `prepare` | импорт двух GLB (`HPG_*` геометрия, `HPT_*` текстура), идентичность частей, перевод в кадр фигуры, ray-escape ориентация, `work/hp.blend` | `reports/prepare*.json`: части совпали, высота, список вывернутых | вывернутые части не в профиле → новый профиль с `expected_inside_out_parts`; геометрия GLB различается → неверная пара файлов, остановка |
| `retopo` | Decimate COLLAPSE по частям на нетекстурном двойнике, плотные зоны, очистка (merge 1e-6, dissolve 1e-7, острова < 2e-7 м²), крышки следов, `work/lp.blend` | треугольники по частям, двустороннее отклонение в мм | QuadriFlow/voxel не использовать; маска vertex group в Decimate — жёсткая, не «смещение»; швить крышки в рваные петли нельзя (33 дубля) — только отдельные утопленные веера |
| `close` | contact caps по открывающимся петлям | инвентарь петель, число крышек | новая открытая петля → добавить крышку в профиль (новый файл) |
| `uv` | charts + unwrap MINIMUM_STRETCH + pack_islands (CONCAVE, rotate ANY) | 0 перекрытий, зазор ≥ 8 px на 4K, плотность по приоритетам | — |
| `bake` | Cycles selected-to-active по частям: NORMAL (OpenGL tangent), AO 128, BC/RM/HIT через EMIT | карта HIT без дыр, AO не константа | чёрные пятна AO = вывернутая часть или смешанная намотка → ориентация, не порог |
| `aux` | AO без загораживающих частей, карта rest-позиций | — | — |
| `textures` | паддинг, N DirectX + N_OpenGL, ORM = (AO, R, M), металл, TeamMask; 4K + 2K | гейты AO: p99 − p1 ≥ 32, ≥ 2 % текселей < 250; «внутрь» ≤ 0,02 на ячейку | — |
| `rig` | арматура, веса по позиции, экспорт UM_FBX_v1, `work/sk_authored.blend` | треугольники, 17 костей, 1 слот, ≤ 4 влияния, лицо +X | — |
| `probes` | `rig_deform_probe.py` на .blend и на FBX (7 поворотов), `validate_clip.py --kind=skeletal-mesh` | `reports/probes-report.json`: 7/7 plausible в обоих, validate PASS | неверная зона → координаты костей/правила весов; **не** сглаживать веса (растяжение 1,46× → 3,10×) |
| `seams` | позы-пробы, доля открытого обода (> 1,5 мм, ≤ 5 % периметра), сквозные лучи | нет новых дыр | дыра в позе → крышка или вес у стыка |
| `preview` | Cycles, K2-камера (FOV 35°, pitch −55°), 1920×1080 | смотреть глазами: лицо, кисти, оружие, ноги на подставке | — |
| `compose`, `manifest` | листы `preview/*.jpg`, `reports/run-manifest.json` | — | — |

Повтор для детерминизма: второй прогон в другой каталог (например `C:/tmp/<task>/repro`) и `--compare-with <первый
run>` → `reports/determinism-report.json`. Ожидается: FBX (`export/*`), BC, TeamMask, UV-лист и отчёты стадий
`identical` (rig-report — `identical after run-path normalisation`); при `device: GPU` у N/ORM допустимо
`different` в единицах пикселей с `max_abs_diff` ≤ 2; превью-JPEG (Cycles с denoise) и `compose-report` отличаются
всегда и не сравниваются. Любое другое расхождение — недетерминизм сборки, остановка.

### 4.4 Look-dev и TeamAccent

```bash
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --mode lookdev \
    --profile <hero>-h2-lookdev.json --run-dir <ASSET>/<date>-h2-lookdev          # ld_maps ld_fbx ld_preview ld_measure ld_compose ld_manifest
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --mode teamaccent \
    --profile <hero>-h2-lookdev-teamaccent.json --run-dir <ASSET>/<date>-h2-lookdev  # ta_maps ta_render ta_report ta_manifest
```

- Look-dev читает готовый H2-прогон только по sha256 и даёт: MatID, LUT, EdgeMask, UV1_m, тона под концепт,
  `SK_<Hero>_H2LD.fbx`. Образцы: `medusa-h2-lookdev.json`, отчёты `*-lookdev-v2.md`.
- Классы MatID — только существующие (`material-library/README.md`). Нужен новый класс (как маховые перья Harpy) —
  остановка, это решение.
- TeamAccent пишет только новые файлы (`textures/<prefix>_TeamAccent_{2K,4K}.png`, `reports/ld-team-*.json`).
  Проверить по отчёту: покрытие 5–12 %, ≤ 20 % на часть, 0 на металле, коже, камне, дереве, когтях.
- Тона под концепт — предсказание; решение по материалу принимается только по съёмке в UE (4.6, `ue_h5cb1.py review`),
  не по прогнозу `lookdev_r2.py forecast`.

### 4.5 Анимации H2Anim

1. Скопировать `medusa-h2anim.json` в `<hero>-h2anim.json` (схема `unmatched.h2anim-spec/1`):
   - `target`: `sk_fbx` = `<run h2-bake>/export/SK_<Hero>_H2.fbx`, `base_fbx`, `sha256`, `rest_generation`
     (`H2`; у Harpy `H3`). Клипы авторятся на bake-меше: look-dev не меняет риг и rest, поэтому они ложатся и на H2LD;
   - `meshes` (имена тела и оружия в FBX), `weapon` (`bone`, `side`), `run_dir`, `ue` (`skeleton`, `clips_folder`),
     `fps 24`;
   - `clips`: роль, N кадров, ключи, волны, IK стоп, `hand_pin`. Движение — по видео-референсам
     `art/animation-refs/<ASSET>/`, а не из головы.
2. Прогон (всё headless, по одному процессу):
   ```bash
   python tools/tripo-pipeline/anim/h2anim_run.py art/pipeline-candidates/<ASSET>/build-profiles/<hero>-h2anim.json
   ```
   Внутри: `clip_author.py` → `validate_clip.py --skeleton=UM_HUMANOID_17_v2 --character=<Hero>` →
   `clip_contact_check.py` → листы поз (`clip_pose_probe.py`, `overlay_bones.py`).
3. PASS-условия:
   - validate: имя арматуры, кости по стороне, лицо +X, fps 24, длительность N/24 ± 0,05 с, in place (≤ 0,5 % роста),
     кадр 0 = rest (и последний для idle/oneshot), пиковый сдвиг ≥ 2 % (меньше — WARN);
   - контакты: скольжение стопы ≤ 0,5 % роста; `skin_stretch` (ребро > 5× rest и > 2 % роста, видимое хоть с одного
     из 24 направлений) = FAIL; `limb_body` > 3× + 20 пар = FAIL; подол ниже верха подставки ≤ 1,5 % (WARN);
     `weapon_tip` ± 0,2 % роста;
   - read-back: rest клипа = rest SK покостно ≤ 1e-4 см, fps = 24.
4. Известные пределы (не «чинить» в клипе — описать в отчёте): подол скинен жёстко, поэтому смерть «на коленях»
   рвёт подол — смерть делается поклоном корпуса; плечо Arthur выше ~18° рвёт наплечник; поворот головы Harpy ≤ ~15°;
   двухзвенная IK не всегда достигает цели. `skin_stretch` не ловит щели без растяжения — нужен крупный план UE.

### 4.6 Импорт в UE

Все UE-шаги — под блокировкой `C:/tmp/ue-editor.lock` (`ue_lock.py`), по одному герою/клипу на блокировку, только в
`/Game/PipelineCandidates/<Key>/...`.

1. Мастер-материалы (один раз на редактор, повтор ничего не меняет):
   `python tools/tripo-pipeline/um_masters.py --backend mcp build --report <evidence>/um-masters-report.json` → PASS для
   `figure`, `base_marker`, `game_layer`.
2. Снимок до: `python tools/tripo-pipeline/review/ue_content_snapshot.py <evidence>/snapshot-before.json --extra-folder
   /Game/ArtTests --extra-folder /Game/S08`. Записать открытый уровень, 0 dirty-пакетов.
3. Канонический скелет: `MSYS_NO_PATHCONV=1 python tools/tripo-pipeline/anim/h2anim_ue.py skeleton <spec>` →
   `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton`.
4. Меш на скелет — CLI 0.8.0, профиль `skeletal-adopt` (образец `king-arthur-h2-ue-import.json`,
   `medusa-h2ld-lookdev-ue-import.json`; в профиле `ue.target_skeleton`):
   ```bash
   $T init --run-dir $R --asset-id <ASSET-ID> --primary-source tripo-<task8>-h2 \
       --primary-role h2-parts-glb --profile skeletal-adopt --build-profile $P --run-id <run-id>
   $T register-source --run-dir $R --spec <source-spec>
   $T run --run-dir $R                                      # preflight + adopt, без UE
   $T --backend mcp ue-import --run-dir $R --ue-folder /Game/PipelineCandidates/<Key>/<Stage>
   $T --backend mcp ue-import --run-dir $R                  # повтор → skipped
   ```
   Импорт идёт legacy `FbxFactory` (не Interchange), `ImportNormals`, Nanite выкл., `import_uniform_scale 1.0`,
   `import_materials=false`, без physics asset и morph targets. `reports/ue-import-report.json` →
   `technically_imported`, все checks passed (кость 0, нет лишних костей, фронт +X, bounds = прогноз ± 0,05 uu, высота,
   треугольники, LOD = 1, сокеты, подставка по центру с низом в z = 0, UV-каналов 2, MI от мастеров, не dirty).
5. Клипы: `h2anim_ue.py import <spec>` (внутри `review/ue_py/import_clips.py`: animation-only, `FbxFactory`,
   `bForceRootLock=true`, `bEnableRootMotion=false`, старый клип удаляется перед импортом), затем
   `h2anim_ue.py measure <spec>`: кадр 0 = ref pose (0, 0 uu), кость 0 неподвижна, масштаб 1,0.
6. Кадры для глаз (редакторные, **не приёмка**): `h2anim_ue.py frames <spec> --clips=Idle` (по клипу за вызов),
   крупный план атаки `--clips=LungeAttack --frames=3,4,5 --closeup`, лист `h2anim_ue.py sheet <spec>`.
   Look-dev съёмка: `python tools/art/material_library/ue_h5cb1.py review --hero <hero> --tag b3.N` (EV100 2,05 и 1,3;
   зоны против концепта: яркость ± 15 %, тон ± 12°, насыщенность ± 0,10).
7. Снимок после с `--compare <evidence>/snapshot-before.json`: `protected_unchanged: true`, добавлены только свои ассеты.

### 4.7 Подключение в игру S08 (только если задача это включает)

Новый или переименованный герой требует трёх правок, иначе игра молча откатится на старую фигуру
(`S08FighterActor.cpp:521-547`: нет меша, скелета, подставки, MI или Idle → fallback):

1. Строка в таблице `Specs()` `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp`: имя бойца с сервера, ключ,
   стадия, бюджет высоты, диапазон, измеренный верх фигуры, верх bounds, длина Idle.
2. Три строки `+DirectoriesToAlwaysCook` в `unreal/Unmatched/Config/DefaultGame.ini` (`<Key>/<Stage>`, `<Key>/Rig`,
   `<Key>/H2Anim`): `LoadObject` — мягкая ссылка, кукер иначе выбросит ассеты. Проверять по `UnrealPak -List` пака.
3. `.uasset` в git только `git add -f` поимённо (Content игнорируется).

Сборка: `Build.bat` возвращает 0 даже при ошибке компиляции — искать `Result: Failed` в логе (UTF-16). Никогда
`-NoLiveCoding` для игрового target. Автотесты `Unmatched.S08.HeroesV2.*` должны пройти (масштаб в 1 %, bounds ±
0,5 uu, длины клипов ± 0,02 с, клипы на скелете меша).

---

## 5. Статический пропс

1. **Params**: скопировать `reports/candidate-params.json` прогона того же вида (бочка, фонарь —
   `art/pipeline-candidates/ASSET-DECOR-KIT-001/<run>/reports/`) в `$R/reports/candidate-params.json`, поменять
   `out_dir`, `source_glb`, `asset_name` (`SM_*`), `texture_prefix` (`T_*`), `material_name` (`M_*`),
   `target_height_m` (из карточки 04 — предложение), `texture_size` (1024/2048), `bake_ao`, `ao_samples`,
   `ao_distance_m` (детали одного абсолютного размера → не масштабировать с высотой).
   Поля с префиксом `_` — пояснения: писать туда, **почему** выбрано значение.
2. **Ремонт геометрии** (`geometry_repair`): `null`, если ремонтировать нечего. Первый прогон с
   `require_closed_manifold: true` покажет открытые/неманифолдные рёбра; по их числам выбрать:
   - `{"method": "tripo_cracks", ...}` — сварка T-стыков, удаление мелких вывернутых плавников; падает, если что-то
     осталось открытым (фонарь);
   - диск-ремонт `{centre_xy_m_prescale, radius_m_prescale, z_min_m_prescale, small_island_max_faces}` — удалить и
     закрыть плоско область крышки (бочка).
   Ничего не «заливать» вслепую; `require_closed_manifold: false` — только для замерного прогона.
3. **Фронт** (`front_check`): по умолчанию «самый выступающий элемент на полувысоте смотрит в −Y» (пробка бочки).
   Если перед несимметричный (дверца фонаря) — `{"method": "axis_extent", "z_band_frac": [lo, hi],
   "expected_axis": "-Y", "min_margin_m": m}`, полосу и запас измерить **до** прогона на GLB.
4. **Свечение** (`glow_slot`, опционально): второй слот для стекла/огня, грани выбираются по цвету BC; эмиссия в
   Blender — только превью, в UE это параметр MI.
5. Сборка и проверка read-back:
   ```bash
   "$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/static_prop_candidate.py -- $R/reports/candidate-params.json
   "$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/check_static_prop_fbx.py -- $R/export/<SM_Name>.fbx $R/reports/fbx-readback.json 0.5
   python -c "import json,sys; r=json.load(open(sys.argv[1],encoding='utf-8')); print([k for k,v in r['checks'].items() if v is not True], r['checks_passed'])" $R/reports/candidate-report.json
   # ожидается: [] True
   ```
6. Build-профиль `<name>-static-um-fbx-v1[-<run>].json` — копия профиля того же вида; общий мастер
   `ue.shared_master.asset = /Game/UM/Materials/M_UM_Figure` + `texture_parameters` (образец
   `decor-barrel-static-um-fbx-v1-um-master.json`), `collision: none`, `two_sided: false`, TeamColor белый (декор не
   командный).
7. CLI: `$T init ... --profile static-candidate --build-profile <профиль>`, `register-source`, `run` (preflight +
   adopt), затем `$T --backend mcp ue-import --run-dir $R/ue-candidate --ue-folder
   /Game/PipelineCandidates/<Asset>/<run>/Candidate` (папка должна быть новой).
8. Посадка: декор стоит на поверхности, а не на z = 0 (борт доски — на z = 5,0 uu). В контрольной сцене
   `"location": [x, y, None], "place_on_surface": True`; проверить `decor_support.on_surface` и кадр 5× (низ не срезан).

---

## 6. Живой Blender через MCP: только осмотр и разведка

Что можно: открыть `work/*.blend` прогона на просмотр, снять скриншот вьюпорта, измерить габариты, проверить веса,
найти номера частей Tripo для профиля. Что нельзя: экспортировать FBX/PNG для коммита, сохранять файлы пользователя,
делать ремонт, который потом не воспроизводит headless-скрипт.

Порядок:
1. `get_addon_status()` (версия Blender) и `get_scene_info()` (что уже есть в сцене пользователя). Чужую сцену не
   менять: свои объекты — в отдельной сцене или коллекции, после работы удалить только свои.
2. Код для `execute_blender_code`:
   - шейдерные узлы искать по типу: `next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")`, не по имени
     (имена локализуются);
   - значения enum читать из RNA, не хардкодить: `[i.identifier for i in
     scene.render.image_settings.bl_rna.properties["file_format"].enum_items]`;
   - `scene.render.engine` менять в `try/except TypeError` (движки аддонов не видны в RNA);
   - цвет материала — на входах узла, `material.diffuse_color` влияет только на вьюпорт;
   - индексы vertex groups читать **до** удаления групп (иначе обращение к освобождённой памяти и падение).
3. После изменений — `get_viewport_screenshot()` и `get_scene_info()`.
4. Headless-скрипты пайплайна (`validate_clip.py`, `rig_deform_probe.py`, `clip_author.py` и др.) в живом Blender
   бросают `RuntimeError` по `not bpy.app.background` — это защита, не баг. Для живого просмотра рига есть только
   `tools/tripo-pipeline/anim/live_view_rig.py`.
5. Через CLI с `TRIPO_PIPELINE_BACKEND=mcp` стадия исполняется в живом Blender (обёртка `.staging/<stage>/<stage>.mcp.py`);
   живой режим откажет, если от прошлого сбоя осталась временная сцена — удалить её руками только после проверки,
   что она своя.

---

## 7. Каталог edge-кейсов

Формат: симптом → причина → что делать. Сначала искать здесь, потом в §8 `ADDING-AN-ASSET.md` и таблицах ловушек
`PIPELINE.md`.

### 7.1 Входы и Tripo

| Симптом | Причина | Действие |
|---|---|---|
| Второй меч/рука/лицо, двуликая голова | side-вид в слоте RIGHT | перегенерация с side в **LEFT** (по лимиту) |
| Край серого камня срезан | серый на сером фоне `#808080` | отметить до генерации; решение художника |
| Нет рукояти внутри кулака, нет древка | Tripo не моделирует скрытую геометрию | мост-цилиндр (перекрытие ~2 мм, 8 сторон) или сборка из частей; в генерическом h2_bake — остановка |
| Золото/сталь выглядят пластиком | Tripo PBR даёт metallic 0,07–0,095 | металл-маска в `textures` |
| Скачанный GLB битый | Chrome оставил `<guid>.tmp` недописанным | сверить длину заголовка GLB с размером, пройти чанки |
| `preflight` падает в чистом checkout | сырые GLB героев не в git | известно; не коммитить 60+ МБ без решения владельца |

### 7.2 Геометрия

| Симптом | Причина | Действие |
|---|---|---|
| Часть чёрная в AO, нормали внутрь | часть Tripo вывернута | ray-escape флип + `expected_inside_out_parts` (новый профиль) |
| Часть не флипается целиком, 40 % площади «внутрь» | смешанная намотка (голова Harpy) | голосование по граням против high-poly + ICM-сглаживание; гейт `ao_bake_parts_face_outward` ≤ 0,02 |
| Ложное «внутрь» у подошв | тест без подставки | тест с плоскостью пола только для теста |
| Нулевые corner normals | вырожденные треугольники | удалить треугольники < 1,1e-7 м² до переноса нормалей; UE сам выбросит < 1e-4 см² |
| Дыры при сгибе в позе | Tripo режет части по линиям контакта | contact caps (`closure`) |
| Дыры-следы в верхе подставки | контур стоп вырезан шире стоп | `base_seethrough.py`: `with_figure` ≤ 0,1 uu² в каждом направлении |
| Decimate по маске «не слушается» | маска vertex group в Decimate жёсткая | плотные зоны — двухшаговым коллапсом по маске (`dense_regions`) |
| 33 дубля треугольников у крышек | крышка вшита в рваную петлю | отдельные утопленные веер-крышки (`sink_m 0.0003`) |
| QuadriFlow падает | рёбра < 1e-4 у Tripo | не использовать; только COLLAPSE |
| Вершины дублируются по UV-швам | текстурный GLB режет вершины | децимировать **нетекстурный** двойник |

### 7.3 UV, бейк, текстуры

| Симптом | Причина | Действие |
|---|---|---|
| Тысячи островов | Smart UV Project | charts + MINIMUM_STRETCH |
| Байты N/ORM меняются между прогонами | GPU-бейк Cycles | ≤ 2 уровня в единицах пикселей допустимо (4.3); нужна бит-стабильность — `device: CPU`; seed фикс., без denoise и adaptive sampling в бейке |
| Тёмные края на мипах | невыпеченный фон чёрный | фон 1,0 для AO, паддинг/pull-push (`edge_extend_px 16`) |
| BC темнее/светлее источника | в Blender 5.2 glTF BC идёт через умножение на `baseColorFactor` | учитывать фактор (сборка умножает в линейном свете) |
| Нормали «вывернуты» в UE | OpenGL-нормаль без флипа G | в UE идёт DirectX `N`, `flip_green=false` |
| AO-гейт прошёл, а пятна видны | гейт диапазона не ловит часть, смотрящую внутрь | смотреть `ao_bake_parts_face_outward` и превью |
| В репо ищут `T_<Hero>_RM` | старое имя из Tier A | сдавать ORM |

### 7.4 Риг и веса

| Симптом | Причина | Действие |
|---|---|---|
| Проба двигает не ту зону | кости не по геометрии героя / неверные правила весов | правка `rig.bones`/`weights` в новом профиле |
| Растяжения выросли после сглаживания | edge smoothing весов | не сглаживать (1,46× → 3,10×) |
| Шум весов, несовпадение байтов | bone heat | снап к сетке 1/255, `clean_below 0.01` |
| Подставка двигается с бедром | авториг / heat захватил подставку | подставка не скинится, отдельный FBX |
| `armature_object_name` FAIL | старое имя (`SKEL_Medusa`) | только `SKEL_UM_Humanoid` |
| `weapon_side` FAIL | одно имя `weapon` | `weapon.L`/`weapon.R` по герою |
| Кость в 100 раз длиннее после glTF-импорта | эвристика костей glTF-импортёра | `TEMPERANCE` при импорте |

### 7.5 Анимация

| Симптом | Причина | Действие |
|---|---|---|
| Клип не появился в UE | FBX клипа без узла меша | экспорт клипа с мешем |
| Фигура уезжает с клетки | ключ на объекте арматуры (кость 0) или на `root` | не ключевать; в UE `bForceRootLock=true` |
| Расхождение root 90° / до 18 uu | клип экспортирован без поворота UM_FBX_v1 | только экспорт UM_FBX_v1; `ref_pose_facing` отвергнет |
| Кадры смещены на +1 при чтении | старые клипы авторены с кадра 1 | кадры 0..N, кадр 0 = rest |
| Подол рвётся при приседе | подол скинен жёстко | поклон корпусом, ноги почти прямые |
| Наплечник рвётся | плечо Arthur > ~18° | ограничить угол |
| Пиковый сдвиг Idle < 2 % | слишком тихий Idle | WARN, не FAIL; поднять амплитуду волн |

### 7.6 Экспорт и UE

| Симптом | Причина | Действие |
|---|---|---|
| Фигура смотрит в +Y | экспорт без +90° (Tier A) | только `candidate_build/core.py` |
| Кость 0 ×100 | импорт scale 100 или нет патча `UnitScaleFactor` | импорт 1,0, патч обязателен |
| Абсолютный путь в FBX | `bpy.data.filepath` не пуст | очищать перед экспортом |
| Повторный импорт ушёл в Interchange | импорт поверх существующего ассета | сначала удалить свой ассет (CLI `--force` / `import_clips.py`) |
| `already exists` / дубли `Name_1` | импорт на занятое имя | новая папка или `--force` для своих |
| `foot.R` не найден в UE | UE переименовал в `foot_R` | использовать UE-имена |
| Подставка Harpy «горит» целиком | MCP static import игнорирует вершинные цвета | путь CLI с `Replace` (`base_vertex_colors_imported`) |
| 47 dirty-пакетов | правка CDO через ObjectTools | CDO не менять; `reload_packages`, не сохранять |
| Редактор висит на Restore Packages | редактор убит с dirty-пакетами | если диск = HEAD — перенести `Saved/Autosaves/PackageRestoreData.json` в `C:/tmp/ue-restore-backup/`, перезапустить свой PID |
| Поворот «не туда» в Python UE | порядок `Rotator` = (roll, pitch, yaw) | только ключевые аргументы |
| `/Game/...` превратился в путь Git | MSYS-конверсия | `MSYS_NO_PATHCONV=1` |
| Ассет есть в редакторе, нет в игре | мягкая ссылка не закуклена | `+DirectoriesToAlwaysCook` |
| Кадр 888×500 | `-RenderOffscreen` клампит | `HighResShot` 1920×1080 |

### 7.7 Процессы, git, детерминизм

| Симптом | Причина | Действие |
|---|---|---|
| Стадия «успешна», выходов нет | Blender вернул 0 после Python-ошибки | требовать маркер `*_STAGE_OK` и отсутствие `Traceback` |
| Стадия переисполняется без изменений | CRLF поменял хеш скрипта | не трогать концы строк; каталоги с хешами — `-text` в `.gitattributes` |
| `git add` падает на длинных путях | > 260 символов | `git -c core.longpaths=true ...` |
| sha в реестре не совпадает с диском | `autocrlf` переписал JSON | хешировать LF-байты |
| Второй агент в том же редакторе | общий редактор | `ue-editor.lock`, один герой/клип на блокировку |

---

## 8. Сдача: definition of done

Ассет считается «технически импортированным», когда выполнены все пункты. Пропуск любого — ассет не сдан.

**Герой:**
- [ ] source-spec с sha256 всех исходников; профиль bake/lookdev/teamaccent/h2anim/ue-import — новые файлы, ни один
      закоммиченный не изменён.
- [ ] H2 bake: все стадии с маркером; `probes-report.json` passed (7/7 на .blend и FBX, validate PASS);
      `determinism-report.json` по правилу раздела 4.3 (FBX и отчёты совпадают; при GPU у N/ORM ≤ 2 уровня).
- [ ] Числа в отчёте: треугольники по частям и сумма, высота фигуры и bounds, кости 17 (16), слоты 1, UV 2,
      влияний ≤ 4, фронт +X, AO-гейты, TeamAccent покрытие.
- [ ] Look-dev и TeamAccent: отчёты `ld-*`, `ld-team-*`.
- [ ] H2Anim: 4 клипа validate PASS, контакты без FAIL (WARN перечислены), листы поз.
- [ ] UE: снимок до/после (`protected_unchanged: true`), скелет, `ue-import-report.json` `technically_imported` со
      всеми checks, клипы импортированы и измерены, сокеты ± 0,05 uu, редакторные кадры с пометкой «EDITOR frame … not
      K1/K2 acceptance».
- [ ] `base_seethrough.py`: `with_figure` ≤ 0,1 uu².
- [ ] Реестр обновлён, `validate_registry.py` → PASS; `DIRECTORY-MAP.md` — если появились новые каталоги.
- [ ] Свои процессы (Blender headless, скрипты) остановлены по PID; редактор и живой Blender в исходном состоянии.

**Пропс:**
- [ ] `candidate-report.json` — все checks истинны, `checks_passed: true` (в том числе `um_fbx_v1_conforms`).
- [ ] `fbx-readback.json` (треугольники, одна сетка без арматуры, замкнутость, слоты).
- [ ] CLI `adopt-report.json` и `ue-import-report.json` без отказов; посадка на поверхность в контрольной сцене.

**Коммит** (главный checkout, ветка `fix/admin-panel`; из worktree — только `tools/git/safe-integrate.sh <branch>`
сначала сухим прогоном, затем `--apply`):
- добавлять **списком путей** (`git -c core.longpaths=true add --dry-run -- <пути>`, затем `add`);
- не коммитить: `work/`, `.staging/`, `logs/*.log`, `run.lock`, `*.fbm/`, PNG кадров, 4K-мастера, сырые GLB;
- кадры для доказательств — JPEG 1200 px q92 + `*.evidence.json`
  (`tools/tripo-pipeline/review/frames_to_jpeg.py`).

---

## 9. Отчёт исполнителя (шаблон)

Положить в `docs/art-pipeline/evidence/<asset>-<дата>/README.md`:

```markdown
# <ASSET-ID> — <что сделано>, <дата>

Статус: технически импортировано | измерено | остановлено (причина)
Исполнитель: <модель>; Blender 5.2.2; UE 5.8.2

## Входы
- source-spec: <путь>, sha256 исходников совпали: да/нет
- профили (новые файлы): <пути>

## Результаты (числа из отчётов)
| Проверка | Значение | Порог | Итог |
|---|---|---|---|
| треугольники (тело/оружие/подставка) | | 30–45k (практика H2, не бюджет) | |
| высота фигуры, uu | | бюджет ± 1 % | |
| пробы деформации | x/7 (.blend), x/7 (FBX) | 7/7 | |
| validate_clip (SK + 4 клипа) | | PASS | |
| контакты клипов | FAIL: …; WARN: … | без FAIL | |
| ue-import checks | n/n | все | |
| сокеты Weapon/Head | Δ uu | ± 0,05 | |
| base_seethrough with_figure | uu² | ≤ 0,1 | |
| детерминизм | совпало n/n файлов | все | |

## Отступления от хендбука
- <шаг> — <что сделано иначе> — <почему>

## Что не проверялось
- <например: packaged-live кадры, художественная приёмка>

## Открытые вопросы к владельцу
- …
```

---

## 10. Что устарело и где источники противоречат

| Тема | Старое (не применять) | Действует |
|---|---|---|
| Бюджет героя | 15–25k (04 §1, 17 §4.5) | предложение до GD-058; измерено 34–43k |
| Текстуры героя | 2K (04) | 4K master локально + 2K runtime в git |
| Источник модели | моделирование в Blender с нуля (04, 17) | Tripo → H2 bake; с нуля — только экспериментальный путь B ([SCRATCH-MODEL-PIPELINE.md](SCRATCH-MODEL-PIPELINE.md)), его бюджеты — по 04 |
| Коллизия | `UCX_` в FBX (04) | нет коллизии, капсула в коде |
| Масштаб импорта | `FBX_SCALE_UNITS` + import 100 (память S05) | патч `UnitScaleFactor 1.0` + import 1,0 |
| Фронт скелетного меша | +Y (ART004, Tier A Medusa) | +X (UM_FBX_v1) |
| Скелет | `UM_HUMANOID_17_v1`, «~15 костей» (04) | `UM_HUMANOID_17_v2`, 17 (16 у Harpy) |
| Кость оружия | `weapon` | `weapon.L` / `weapon.R` по герою |
| `path_mode` | `AUTO` (04, пресет) | `STRIP` в сборке (записанное отклонение) |
| Tripo для героя | 2K, «по частям» выкл. (ADDING §2, эпоха CLI) | «по частям» Balance, 2M, затем 8K + PBR |
| Карта RM | `T_Medusa_RM.png` (Tier A) | ORM |
| Формат концептов героя | 1024×1024, `#808080`, y = 917, `check_inputs.py` (mvp-v1) | hero-quality-v1: портретный кадр, рисуется поверх орто черновика (3.1) |
| TeamColor | вся одежда (`TeamMask`) | акценты (`TeamAccent`) + кольцо |
| Цвет P2 | `#9FC2D8` (С-11) | `#5A7F9F` |
| `17 §7` (2026-09-25) | «пресет и оси не подтверждены» | подтверждены ART-001 |
| Сокет `Weapon` Harpy | кисть (rig-contract) | `foot.R` (профиль) — расхождение открыто |
| CLI-версия | 0.6.0 в PIPELINE.md | 0.8.0 (`skeletal-adopt`, `ue.target_skeleton` описаны в `king-arthur-h2-ue-import.md`) |

---

## 11. Ссылки

- Порядок действий и правила остановки: [ADDING-AN-ASSET.md](ADDING-AN-ASSET.md)
- Инструмент CLI, стадии, UE-импорт, мастер-материалы: [PIPELINE.md](PIPELINE.md)
- Риг: [rig/RIG-CONTRACT.md](rig/RIG-CONTRACT.md), [rig/rig-contract.json](rig/rig-contract.json)
- Анимации: [animation-library/README.md](animation-library/README.md), [VALIDATION.md](animation-library/VALIDATION.md)
- Материалы и TeamAccent: [material-library/README.md](material-library/README.md),
  [team-accent.md](material-library/team-accent.md), [m-um-figure-v2.md](material-library/m-um-figure-v2.md)
- Отчёты сборок героев (лучшие примеры решений): [medusa-h2-report.md](medusa-h2-report.md),
  [king-arthur-h2-report.md](king-arthur-h2-report.md), [merlin-h2-report.md](merlin-h2-report.md),
  [harpy-h3-report.md](harpy-h3-report.md), `*-lookdev-v2.md`, [king-arthur-h2-ue-import.md](king-arthur-h2-ue-import.md)
- Пропсы: [prop-barrel-report.md](prop-barrel-report.md), [prop-lantern-report.md](prop-lantern-report.md),
  `tools/tripo-pipeline/blender/static_prop_candidate.py` (docstring — полное описание params)
- Каталоги и что в git: [DIRECTORY-MAP.md](DIRECTORY-MAP.md); статус ассетов:
  [SESSION-CLOSEOUT-2026-09-30.md](SESSION-CLOSEOUT-2026-09-30.md)
- Рендер-эталон кадров: [render-reference.json](render-reference.json)
- Код игры: `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp`, `S08FighterActor.cpp`,
  `unreal/Unmatched/Config/DefaultGame.ini`
