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
| Оружие из нескольких частей Tripo | Tripo режет тонкое оружие (копьё Achilles = части 10 + 13, меч Angel = клинок с гардой + рукоять): одна часть — меш `weapon`, остальные — в меш `body` с правилом `rigid` 100 % на кости оружия (`profile.py:68` допускает одну часть `weapon`; решение П3-1, `docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md`) |
| Предмет в руке без своей кости (щит, фонарь) | `rigid` 100 % на `arm_lower` или `hand` своей стороны, новой кости нет (щит Achilles на `arm_lower.L` прошёл все пробы; решение П3-2). Новая кость — стоп (§0.3 п.7) |
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

Высота меряется от низа подставки (z = 0). **Верх бюджета** (`Specs()` BudgetUU и FigureTopUU) — верх головы с
прилегающим убором: шлем с гребнем (Achilles 0,55), корона (Arthur). Деталь, которая поднимается над головой (поднятый
клинок, посох, рога), — **верх bounds** (BoundsTopUU: меч Arthur 60,06, рога Ancient Leshen 73,58), она бюджет не
валит. Пометка в карточке — `FIGURE_HEIGHT_M` (бюджет) и `FIGURE_BOUNDS_TOP_M` (SKILL.md §7.2).

`prepare` ставит на `scale.figure_top_m` самую высокую вершину **любой** части, кроме подставки — оружие и рога
включительно (`st_prepare.py`, `profile.figure_top_source_z`). Поднятый меч Angel поставил бы голову на 0,541 м
(пилот 2026-10-13, F28; здесь и ниже F-номера — `docs/art-pipeline/evidence/skill-pilot-2026-10-13/NOTES.md`). Если
деталь выше головы — в профиле `scale.figure_top_part` = часть с верхом бюджета (голова, шлем). Тогда `figure_top_m` =
верх этой части, `prepare-report.json#figure_top_part` пишет её и верх bounds, а орто-кадры концепта строятся по верху
bounds (`profile.frame_top_m`: рамка концепта меряет весь силуэт). Профили без ключа (Medusa и др.) работают
по-старому, байт в байт. Прогоны пилота сделаны до ключа: `figure_top_m` подобран по разведке (Angel 0,55904 — кончик
клинка при голове 0,55; Leshen 0,7356 — рога при черепе 0,55003). Пробы деформации нормируют пороги высоты по полному
росту с рогами (F59, не исправлено): у фигуры с высоким украшением читать числа проб, а не только вердикт.

Подставка: Ø 0,30 × 0,06 м у Medusa/Arthur (5–6 uu высотой). Отношение высот помощник/герой = 0,78 ± 0,06 (автотест).

Треугольники (измерено, **не бюджет**): Medusa 43 054 (тело 38 054 + лук 5 000), Arthur 38 684, Merlin 33 967,
Harpy 37 177, Achilles 44 706 (тело 43 506 + копьё 1 200); подставки 864–2 240. Предложение 04: герой 15–25k,
помощник 8–15k — решение за GD-058. Практика H2: целиться в 30–45k на героя, 20–30k на Harpy-подобных, подставка
~1,2–2k. Считается **итог** тела и оружия на экспорте (`rig-report.json#meshes_pre_export.<меш>.triangles`, без
подставки): `retopo.target_tris` + крышки `close` (`close-report.json#cap_triangles`, у Achilles 4 908) + грани частей
`rig.cloth_shell` ещё раз и мост кромки (юбка Achilles: 2 399 граней, 315 рёбер кромки). Сумма `target_tris` под 45k не
гарантирует итог под 45k (F70): запас под крышки и оболочки закладывать в `target_tris`. Выход за 45k — записать в
отчёт, не резать молча.

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

1. Реестр: запись в `docs/art-pipeline/asset-registry.json`, `python tools/tripo-pipeline/validate_registry.py`
   до и после правки → новых ошибок нет (базовая линия 2026-10-09: `RESULT: FAIL (1 errors)` на чужой
   `sharedDependencies[UM-MASTERS]` sha256 `art/um-materials/um-masters.json` — не чинить, PASS без неё недостижим).
2. Сухой пакет входов в CLI run `<run>` (обычно `<date>-h2-tripo/generation-request/`). Сначала `init`, иначе
   `prepare-generation` на новом каталоге завершается кодом 2 «run is not initialised» (`tripo_pipeline.py:530-531`):
   `$T init --run-dir <run> --asset-id <ASSET-ID> --primary-source tripo-pending --primary-role h2-parts-glb`
   (источника ещё нет; прецедент — `ASSET-TABLE-BASE-001/20260928-table-base-tripo-h31/generation-request/`; у пропа
   роль `source-glb`), затем `$T prepare-generation --run-dir <run> --dry-run --service tripo-studio --mode multi-view
   --model-label "H3.1" --view front=<png> --view left=<png> --view back=<png>`. Код 3 = дубль → остановка. Код 3
   ловит дубль только среди источников **этого** run (`tripo_pipeline.py:3796-3805`), поэтому до клика сверить
   sha256 входов со всеми `<ASSET-ID>/source-specs/*.json`.
   Черновая модель для концептов (3.1, шаг 1) — отдельная дешёвая операция (single-image или multi-view без 8K и без
   «по частям»); её GLB и списание тоже записываются в журнал кредитов.
3. Настройки **героя** (H2/H3): «Приватный», multi-view (не batch), H3.1;
   - FRONT = front, **LEFT = side**, BACK = back, RIGHT пусто. Side в слот RIGHT → Tripo зеркалит вид и строит
     фантомы (второй меч, вторая рука и лицо у Arthur, двуликая голова у Harpy);
   - «по частям» Balance, ultra mesh 2M, triangles, без текстуры (60 кредитов);
   - затем текстура 8K с «убрать освещение» (30), затем PBR (5).
4. Настройки **пропса**: multi-view, H3.1, текстура 2K, PBR, Triangle, 8K и «по частям» выключены.
5. После каждой операции — баланс и строка истории в `evidence/<asset>-<дата>/tripo-run.json` и строка в единый
   журнал визуала `docs/game-design/visual/credits-ledger.json` через `python tools/art/visual/ledger.py add`
   (`docs/game-design/visual/07-prompt-templates.md` §4.1, ВР-PR06; нужна карточка `--task` в
   `docs/game-design/visual/06-tasks/`, команда и поля — `.agents/skills/3d-model-pipeline/references/tripo3d-stages.md`).
   `tools/art/syntx_video_refs/ledger_append.py` пишет только старый журнал s3-baseline — в него не писать.
6. Загрузка GLB: Chrome оставляет `C:/Users/ren/Downloads/<guid>.tmp`. Проверить длину из заголовка GLB = размер файла,
   пройти все чанки; скопировать в `art/pipeline-candidates/<ASSET-ID>/<date>-h2-tripo/source/` как
   `<key>-h2-tripo-<task8>-parts<N>.glb` и `<key>-h2-tripo-<task8>-tex8k-pbr.glb` (`<key>` — slug героя, как
   `medusa-h2-tripo-40c4d1cd-parts17.glb`; у поколения H3 — `-h3-`). Свой Save-диалог закрыть до передачи
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
| `expected_part_count`, `parts` | число частей Tripo и роль каждой (тело, лицо, кисти, оружие, подставка) | части нумеруются Tripo произвольно — роли определять по рендеру частей в своих цветах, а не по номеру и не по габаритам (у Achilles по габаритам вышли «голова» = гребень, F17); оружие из нескольких частей — §2.6 (П3-1) |
| `scale` | `figure_top_m` = бюджет / 100 (0,55 для 55 uu), `base_diameter_m`, `base_height_m`; необязательный `figure_top_part` | `prepare` берёт самую высокую вершину не-подставки, оружие и рога включительно; деталь выше головы — `figure_top_part` (§2.10) |
| `orientation` | `method` ray-escape, `samples_per_part 4000`, `seed 0`, `flip_below_score -0.5`, `min_score_after_fix 0.5`, `expected_inside_out_parts` — **пустой до первого прогона** | первый prepare перечислит вывернутые части и откажет; список переносится в **новый** файл профиля, порог не ослабляется |
| `retopo` | `method` COLLAPSE, `target_tris` по частям (крупные части первыми), `dense_regions` (лицо ~1 600 tris), `cleanup`, `caps` | итог с крышками и оболочками → 30–45k на героя (§2.10); лицо, кисти, оружие получают приоритет. Регион `name: "face"` обязателен: его `part` — часть с лицом, по ней `rig` и `ld_fbx` меряют фронт лица (`profile.face_part_key`; без региона — `tripo_part_1` Medusa, у Achilles это подставка: rig FAIL, 0 граней лица, F12) |
| `closure` | `contact_caps` по петлям, которые открываются в позах | у Medusa 19 крышек; видимость крышек в rest ≤ 0,01 % и ≤ 9 px; выбор крышка / стык весов / оболочка — «Новый герой» ниже |
| `uv` | `atlas_px 4096`, `runtime_px 2048`, `min_gap_px 8`, `pack_margin_fraction 0.0013`, `max_overlap_px 0`, `texel_priority` (лицо ×2, кисти ×1,75, оружие ×1,5, подставка ×0,45), `density_reference_part`, `charts.chart_area_cm2` | Smart UV запрещён (5 402 острова у Medusa); только charts (Voronoi + MINIMUM_STRETCH). `density_reference_part` — крупная часть тела, с которой сравнивается плотность лица (без ключа `tripo_part_0` = платье Medusa). Острова, прошедшие проверку на 512 px, на 4K перекрывались на 7–17 px (`uv-report.json#checks.raster_overlap_px`, F30, F56): рукавам и клинкам — меньший `chart_area_cm2` (по части или `charts.regions`) |
| `bake` | `device`, `resolution 4096`, AO (128 samples, distance 0,044 м = 0,08 × рост), `cage` (1,5 × p99 отклонения, 0,6–4 мм, `max_ray_factor 2.5`), `ao_exclusions` (AO части без загораживающей части, которая в анимации отходит — кулак Medusa у пояса) | `device: "GPU"` (Medusa): FBX повторяются байт в байт, а N/ORM расходятся в 1–3 пикселях на 1–2 уровня; `CPU` (Merlin) бит-стабилен, но медленнее. Выбор записать в отчёт |
| `textures` | `prefix T_<Hero>_H2`, `maps`, `ao_gate`, `team_mask`, металл-маска `materials.metal`, `edge_extend_px 16` | `team_mask.cloth_hsv` и `base_band.part` — значения Medusa, перенастроить (чек-лист ниже). Металл есть — блок `materials.metal` обязателен (look-dev читает маску). Металла нет — без блока: стадия пишет нулевую `work/uv/metal_mask.npy` и `textures-report.json#metal_mask` (F51) |
| `rig` | `skeleton UM_HUMANOID_17_v2`, `armature_object SKEL_UM_Humanoid`, `character <Hero>`, `max_influences 4`, `clean_below 0.01`, `bones` (голова/хвост каждой кости по геометрии героя), `weights` (`chain`, `zblend`, `cloth`, `rigid`), `junctions`, `seam_pairs`, необязательный `cloth_shell` | кости ставить по геометрии нового героя (разведка, ниже); копия координат Medusa = гарантированный FAIL проб |
| `seams` | `raycast` (`pitch_m 0.0015`, `margin_m 0.1`, `posed_clearance_m 0.005`), `max_new_blob_px 8`, `frames`, `k2_frames` под свою фигуру | сетка лучей одна на все позы: rest + `margin_m`, сторона, которую поза покидает, отодвигается до позы + `posed_clearance_m` (`profile.seams_grid_bounds`, F55/F65). Обход пилота `margin_m 0.2` больше не нужен; расширение пишется в `seams-report.json#see_through.<blend\|fbx>.grid_extended_by_posed_bounds_m` |
| `sockets` | `Weapon` на кости оружия, `Head` на `head`, `location_uu: null` | — |
| `exports` | `fbx_preset blender/_tools/presets/UM_FBX_v1.json`, `skeletal_fbx SK_<Hero>_H2.fbx`, `base_fbx SM_<Hero>_H2_Base.fbx` | — |
| `meshes`, `materials` | какие части → body/weapon/base; один слот | — |
| `axes` | `blender_front -Y`, `expected_ue_front +X`, сторона оружия | — |
| `preview` | `concepts` (пути концепта), камеры K2 (`k2`), `closeups` / `pose_closeups` / `channel_views` под геометрию нового героя (`pose_closeups` — позы `st_seams.pose`, можно `[]`), `frame` = `{"checks_report": "<папка видов>/checks-report.json", "side": "<SIDE_VIEW>"}` (h2-bake 0.6.1, `h2_bake/framing.py`: орто-кадры по кадрированию своего концепта) | **удалить** `previous_candidate` (прежний кандидат W4-B Medusa: иначе в `compare-*.jpg` рядом с новым героем встанет Medusa) и `baseline` (sha256 текстур H2 Medusa до H2.1 — `preview` упадёт на `sha256 mismatch`). Оба ключа необязательны с 0.6.1; без `frame` — канон Medusa 1021 × 1540 |

Оружие: если Tripo не смоделировал рукоять внутри кулака (Arthur) или древко (Merlin), нужен мост-цилиндр или сборка из
частей (`split-from-part` / `parts` в CLI-пути). В генерическом `h2_bake` такого режима нет — если оружие героя без
хвата, это остановка с описанием (решения — в `h2_bake_arthur/repairs.py`, `h2_bake_merlin/`). Оружие, которое Tripo
разрезал на части, и предмет в руке без кости — §2.6 (П3-1, П3-2).

#### Новый герой: разведка и чек-лист профиля (пилот 2026-10-13)

**Разведка до профиля** (F19). Координаты Medusa не переносятся, поэтому профиль пишется по замерам своей фигуры.
Сначала черновой профиль (роли частей, `scale`, `orientation`) и стадии `prepare`, `retopo`, `close` в scratch-каталоге
вне репо (`C:/tmp/<key>-scout`). Из них:

1. Габариты частей в финальной рамке — `prepare-report.json#parts.<part>.final_bounds_m`, вывернутые части —
   `#orientation`; роли частей — по рендеру частей в своих цветах (F17).
2. Положение костей: сечения частей по высоте (шея, плечи, локти, запястья, таз, колени, щиколотки) по `work/lp.blend` —
   своим bpy-скриптом или осмотром в живом Blender (§6, только чтение). Голова кости оружия — в точке хвата.
3. Инвентарь петель — `close-report.json#loops_before.<part>`: каждая петля с периметром ≥
   `closure.inventory_min_perimeter_cm`, ближайшая часть и медиана расстояния до неё. Это кандидаты крышек и стыков.
4. Толщина ткани: луч снаружи насквозь через часть (bpy `ray_cast`). Две стенки с зазором — замкнутая оболочка (вырез
   изнутри закрывается крышкой: плащ Achilles, петля 92 см). Одна стенка — одинарный лист (юбка Achilles), ему нужна
   `rig.cloth_shell`. Посылка «плащ Achilles — лист» оказалась ложной (F63); лист от оболочки отличает и инвентарь
   петель: у листа петля идёт по всей кромке (F35).

Готового инструмента разведки в `tools/` нет: скрипты пилота остались в `C:/tmp` и в репо не переносились. Разведка —
разовые скрипты исполнителя, а её числа идут в профиль с пометкой `note`.

**Значения Medusa, которые надо перенастроить.** Скопированные как есть, они дают FAIL или меряют чужую часть.

| Ключ | У Medusa | Что поставить |
|---|---|---|
| `retopo.dense_regions[name=face].part`, `box_m` | `tripo_part_1` | часть и рамка своего лица (голова, шлем; F12) |
| `uv.density_reference_part` | нет ключа = `tripo_part_0` (платье) | крупная часть тела |
| `textures.team_mask.cloth_parts`, `cloth_hsv` | платье; `v_max 0.4`, `s_max 0.34` (тёмная ткань) | своя ткань по замеру BC: на красном плаще Achilles `team_mask_cloth_share` падал (F20). Ткани нет — `cloth_parts: []`, тогда проверка «не применима» (`not_applicable`, F52; вороны Leshen как обход больше не нужны). `TeamMask` устарел, но проверка стадии `textures` осталась |
| `textures.team_mask.base_band.part` | `tripo_part_2` | часть подставки (у Angel `tripo_part_2` — штанина, F29) |
| `textures.materials` | металл Medusa (золото), `ao_exclusions`, `rim_filters` | свой металл по частям (§4.4) или без блока; `ao_exclusions`/`rim_filters` — только свои контакты |
| `rig.*`, `sockets`, `seams.frames`, `seams.k2_frames`, `preview.*` | Medusa | по разведке и под свою фигуру |

**Закрытие стыков: что выбрать.**

| Ситуация | Средство | Прецедент |
|---|---|---|
| петля части уходит из-под соседа в позе (плечо под плащом, бедро под юбкой, подошва) | крышка `closure.contact_caps` | Medusa 19, Achilles 13 |
| штаны из двух частей Tripo: верх штанины открывается при сгибе бедра | крышки на верх каждой штанины; стык весов там складывал бедро | Angel (F31) |
| седловидный вырез плеча: крышка видна в покое (216 px) | стык весов `rig.junctions` (полоса `band_m` берёт веса соседа) | Leshen, плечи ствола, полоса 2,5 см (F61) |
| конец оружия у подставки (пятка копья, петля 1,4 см) | своя крышка с `min_perimeter_cm` ниже общего `closure.min_perimeter_cm` (по умолчанию 3 см: короче — пропуск) | `spear_butt`, 1,0 (F16) |
| одинарный лист ткани показывает изнанку в позах (пятна > `seams.max_new_blob_px`) | сначала веса и стыки, затем `rig.cloth_shell` | юбка Achilles (П3-3, F64) |
| толстая оболочка с вырезом изнутри | крышка на вырез | плащ Achilles, `cloak_back` (F63) |

`rig.cloth_shell = {"parts": [...], "offset_mm": 0.3}` (0 < `offset_mm` ≤ 1). Стадия `rig` после весов добавляет каждой
части внутреннюю копию её реальных граней: обратная намотка, тот же UV0, веса копируются, смещение против нормали, по
кромке — мост. Атлас и бейк не меняются, а треугольники части удваиваются (§2.10). Без ключа FBX Medusa совпадает байт
в байт (`tests/test_cloth_shell.py`). Перед ключом — инвентарь петель (лист или оболочка, п.4 разведки).

**Безногий ствол** (Ancient Leshen, F53). Частей ног нет. Ствол — правило `cloth`: `hips`, выше талии `spine`, ниже
`leg_start_z` половины по сторонам на `leg_upper.L/R` до `leg_max`. У подставки — правило `rigid` на `root`: подставка
не скинится, правило нужно только стыку. Стык `rig.junctions` ствола с подставкой полосой 0,22 м держит корни на месте,
кости ног гнут середину ствола. Без стыка веса бедра поднимали корни (пятна 130–446 px). Этапу 6 записать в `NOTES`
карточки: ног нет, кости ног гнут ствол.

### 4.3 Прогон стадий

Запускать **по одной стадии** и читать отчёт после каждой. `all` — только для повтора уже отлаженного профиля. Нового
героя — только после разведки (4.2, «Новый герой»).

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
| `close` | contact caps по открывающимся петлям | инвентарь петель (`close-report.json#loops_before` / `loops_after`), число крышек, `checks.caps_hidden_at_rest` | новая открытая петля → добавить крышку в профиль (новый файл); крышка видна в покое (седловидный вырез) → стык весов (4.2) |
| `uv` | charts + unwrap MINIMUM_STRETCH + pack_islands (CONCAVE, rotate ANY) | 0 перекрытий, зазор ≥ 8 px на 4K, плотность по приоритетам | `raster_overlap_px` > 0 → меньший `charts.chart_area_cm2` части; отчёт не называет острова — искать по `uv-layout-1024.png` |
| `bake` | Cycles selected-to-active по частям: NORMAL (OpenGL tangent), AO 128, BC/RM/HIT через EMIT | карта HIT без дыр, AO не константа | чёрные пятна AO = вывернутая часть или смешанная намотка → ориентация, не порог |
| `aux` | AO без загораживающих частей, карта rest-позиций | — | — |
| `textures` | паддинг, N DirectX + N_OpenGL, ORM = (AO, R, M), металл, TeamMask; 4K + 2K; `work/uv/metal_mask.npy` (у героя без металла — нулевая) | гейты AO: p99 − p1 ≥ 32, ≥ 2 % текселей < 250; «внутрь» ≤ 0,02 на ячейку; `team_mask_cloth_share` 0,5–0,98 или `not_applicable` | `team_mask_cloth_share` FAIL → `cloth_hsv` под свою ткань (4.2) |
| `rig` | арматура, веса по позиции, `rig.cloth_shell` (если задан), экспорт UM_FBX_v1 в `work/rig/export-staging/`, read-back, `work/sk_authored.blend` | треугольники, 17 костей, 1 слот, ≤ 4 влияния, лицо +X | FBX попадают в `export/` только при PASS (пилот, F25); при FAIL `export/` не трогается, пара лежит в staging для разбора |
| `probes` | `rig_deform_probe.py` на .blend и на FBX (7 поворотов), `validate_clip.py --kind=skeletal-mesh` | `reports/probes-report.json`: 7/7 plausible в обоих, validate PASS | неверная зона → координаты костей/правила весов; **не** сглаживать веса (растяжение 1,46× → 3,10×) |
| `seams` | позы-пробы, доля открытого обода (> 1,5 мм, ≤ 5 % периметра), сквозные лучи | нет новых дыр; `seams-report.json#see_through.<blend\|fbx>.poses.<поза>.largest_new_blob_px` и `_view` | дыра в позе → крышка или вес у стыка (выбор — 4.2). Петля с большой `median_to_cover_mm` (свободный край плаща в 16,7 мм от торса, F15) — не контакт: её «раскрытие» не мерило, судят сквозные лучи. Ложные срабатывания лучей: строки 9–14 px вдоль плоской «земли» у подставки (F57), перевёрнутая реальная грань в 0,1 мм над крышкой своей части (F69) — проверить на `work/seams_raw`, записать в отчёт |
| `preview` | Cycles, K2-камера (FOV 35°, pitch −55°), 1920×1080 | смотреть глазами: лицо, кисти, оружие, ноги на подставке | чёрные пятна в крупном плане с отсечением задних граней, где слоёв много (корни Leshen), — предел отскоков прозрачности превью (F62), не дефект модели |
| `compose`, `manifest` | листы `preview/*.jpg`, `reports/run-manifest.json` | — | — |

Повтор для детерминизма: второй прогон в другой каталог (например `C:/tmp/<task>/repro`) и `--compare-with <первый
run>` → `reports/determinism-report.json`. Ожидается: FBX (`export/*`), BC, TeamMask, UV-лист и отчёты стадий
`identical` (rig-report — `identical after run-path normalisation`); при `device: GPU` у N, N_OpenGL, ORM (4K и 2K)
допустимо `different` в единицах пикселей с `max_abs_diff` ≤ 2, и вместе с ними `textures-report.json` (в нём sha256 и
статистика этих карт; пилот: 4 карты N по 1–6 пикселей, F24); превью-JPEG (Cycles с denoise) и `compose-report`
отличаются всегда и не сравниваются. Любое другое расхождение — недетерминизм сборки, остановка.

Отчёт пишется в каталог **того** прогона, который запущен с `--compare-with` (F33). Повтор пишет его в repro; чтобы
отчёт лёг в производственный прогон, после повтора выполнить
`run_h2_bake.py --profile $P --run-dir $R --stages manifest --compare-with C:/tmp/<task>/repro` (стадия `manifest`
только переписывает `run-manifest.json`, выходы не трогает). Look-dev — то же с `--mode lookdev --stages ld_manifest`.

### 4.4 Look-dev и TeamAccent

```bash
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --mode lookdev \
    --profile <hero>-h2-lookdev.json --run-dir <ASSET>/<date>-h2-lookdev          # ld_maps ld_fbx ld_preview ld_measure ld_compose ld_manifest
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --mode teamaccent \
    --profile <hero>-h2-lookdev-teamaccent.json --run-dir <ASSET>/<date>-h2-lookdev  # ta_maps ta_render ta_report ta_manifest
```

- Look-dev читает готовый H2-прогон только по sha256 и даёт: MatID, LUT, EdgeMask, UV1_m, тона под концепт,
  `SK_<Hero>_H2LD.fbx`. Образцы: `medusa-h2-lookdev.json`, отчёты `*-lookdev-v2.md`. Новый герой ставит в look-dev
  профиль `frame` (как `preview.frame` H2-профиля, 4.2): `ld_measure` берёт пиксели концепта под масками прохода ID и
  отказывает концепту, аспект которого отличается от кадра больше чем на 1 %.
- Входы нового героя (пилот 2026-10-13, F21). `source.files.baseline_BC` / `baseline_ORM` = его собственные
  `textures/T_<Key>_H2_{BC,ORM}.png`: у Medusa это `work/h2-baseline/` (текстуры до H2.1), у нового героя такого прогона
  нет. `work/uv/metal_mask.npy` look-dev читает всегда (`lookdev.py:328`). Металл есть — блок `textures.materials.metal`
  H2-профиля обязателен (проход металла: маска + металлик 0,9–1, §2.4). Металла нет — блок не нужен, стадия `textures`
  пишет нулевую маску (F51; Leshen писал её руками).
- Класс металла и кожи — по отделке **концепта**, а не по прецеденту героя: матовый клинок — `metal_forged`,
  полированный — `steel_polished` (`steel_polished` Arthur дал матовому клинку Angel почти чёрный тон, F34). Соседние
  вещи одного тёмного цвета (рубашка под пальто) держать разными классами с контрастом: усиления `ld_measure` прижимают
  обе к полу класса, и они сливаются (F34).
- Усиления металлических классов (`grade.gains`) — с демпфированием, не полный `gain_suggestion`: металл концепта —
  краска, а не PBR. Бронза Achilles: полная поправка тона дала бледную латунь, половина — тёмную бронзу (0,73), H2LD
  читается медной и глянцевой против матового золота концепта (F71). Почему усиление не полное — в `note` профиля;
  решает съёмка UE (4.6).
- Слота `horn_claw` в генерическом look-dev нет: череп, рога и когти уходят в `legacy_bake` (Leshen, F54) — записать в
  отчёт. Класс в библиотеке есть (Harpy, слот `brass`), но слот героя — новый режим инструмента, решение владельца.
- Классы MatID — только существующие (`material-library/README.md`). Нужен новый класс (как маховые перья Harpy) —
  остановка, это решение.
- **Сдача этапа 3: тон и крупные планы** (пилот: обе приёмки вернули `rework_blender` — основной класс вне допуска тона,
  кость Leshen y_ratio 0,775, бронза Achilles 0,717, потолок T 1,0; плюс артефакты крупных планов, которых исполнитель
  этапа 3 не смотрел; F72, F79). До передачи на приёмку:
  1. Таблица тона — тем же кодом, что строит `frames/tone.json` съёмки
     (`tools/art/acceptance/capture_acceptance_set.py:470-482` → `tools/art/acceptance/_tone.py`
     `tone_table(measure, maps)`; отдельного CLI нет; запуск из корня репо):
     ```bash
     python -c "import json,sys; sys.path.insert(0,'tools/art/acceptance'); from _tone import tone_table; R=sys.argv[1]+'/reports/'; t=tone_table(json.load(open(R+'measure-report.json',encoding='utf-8')), json.load(open(R+'ld-maps-report.json',encoding='utf-8'))); print(t['t_cap'], t['out_of_tolerance'], t['floor_limited'], t['family_changed_main'])" <run look-dev>
     ```
     Нужен `t_cap` = 2.0: все классы в допуске `_tone.py` (основной класс ≥ 10 % пикселей; Y_ratio и у основного ещё
     `y_ratio_loo` в 0,80–1,25; |dHue| ≤ 15°). Иначе — ещё итерация grade: новый look-dev профиль, `grade.gains` вне
     допуска из `measure-report.json#gain_suggestion.<класс>.suggested_gain` (металл — демпфированно, причина в `note`),
     прогон `ld_maps` … `ld_measure`, таблица заново. Класс `floor` T не снижает (`known_issues`). Не дошли до 2.0 —
     причина и числа в отчёт этапа 3, а не молча на приёмку.
  2. Крупные планы приёмщика — снять в scratch-каталог и осмотреть самому (Read каждого JPEG):
     `python tools/art/acceptance/capture_acceptance_set.py --fbx <LD>/export/SK_<Key>_H2LD.fbx --textures <LD>/textures --out C:/tmp/<key>-stage3-check/frames --key <Key> --side-view <SIDE_VIEW> --sheet art/imagegen/concept-<key>-codex/sheet-<key>.png`
     → `close-head`, `close-hands`, `close-torso`, `close-legs-back`, `close-weapon`, `pose-01` … `pose-04`, `compare-*`
     (кадры не evidence: этап 4 снимает свои). Пилот пропустил: коричневый наконечник копья, наносник цвета кожи, мазки
     на вороте, защемление локтя (Achilles), гранёные когти и отростки рогов (Leshen). Найденное чинится средствами
     профиля до передачи (классы look-dev, `retopo.dense_regions`, веса).
- TeamAccent пишет только новые файлы (`textures/<prefix>_TeamAccent_{2K,4K}.png`, `reports/ld-team-*.json`).
  Проверить по отчёту: покрытие 5–12 %, ≤ 20 % на часть, 0 на металле, коже, камне, дереве, когтях.
- Компоненты `team_accent` (h2-bake 0.6.1) — каждый необязателен, нужен хотя бы один: `hem` — полоса ткани
  `cloth_class` шириной `width_m` вдоль кромки класса `band_class` ниже `band_z_max_m` (платье Medusa: linen у
  gold_antique); `ribbon` — ремень/перевязь класса `class` выше `z_min_m`. Костюм без каймы (латы, простая туника) —
  без `hem`, акцент на поясе, перевязи, лямке колчана или подкладке плаща; тогда `cloth_class` и `trim_class`
  верхнего уровня называют основную ткань (проверка `dress_parts`) и отделку (контраст `ta_report`). Классы акцента —
  только с `teamDyeAllowed`. Пустой компонент пропускается (`skipped` в отчёте), достаточность решает
  `area_share_range`; пустой акцент целиком — `ta_maps` падает, классы выбрать заново.
- `ribbon` берёт **один** класс: сандалии Achilles (`leather_worn`, 4,3 %) при ремнях `leather_smooth` остались в цвете
  концепта (F67). Тонкие ремни: `open_radius_px 3`, `min_component_opened_texels 1000` (у Medusa 8 / 5000 — полосы
  птеруг 4 мм стирались: 0,74 % вместо 1,47 %). Подкладку плаща (изнанка замкнутой оболочки) и полосу «N см от кромки»
  генерический TeamAccent не выделяет (F27).
- **Доля ниже 5 %** (решения П3-4, П3-4a, П3-4b,
  `docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md`; прецедент Arthur 3,56 %). Красятся только разрешённые зоны (отделка ткани, ремни, кожа снаряжения, перья; не металл,
  кожа персонажа, узорная кайма, не главный цвет одежды). Если их меньше 5 %: (а) `team_accent.area_share_range` опустить
  до замера (Achilles [0,02; 0,12] при 2,20 %; Angel [0,007; 0,12] при 0,73 %); (б) с ним
  `render.readability.screen_share_min` (K2 5× спереди/сзади, по умолчанию 0,01) — до измеренного минимума (Angel
  0,0003); (в) спину целиком закрывает неокрашиваемая вещь главного цвета (плащ Achilles) — `screen_share_min` 0,
  долю спереди записать; проверка «ткань вне акцента не меняется» на < 500 видимых пикселях — порог
  `dress_unchanged_share_min` до измеренного пола (Achilles 0,86 на 225 px); вид, где ткани < `dress_min_px` (100),
  — «нет замера», не провал. Каждое снижение — новый файл профиля (`…-teamaccent-b.json`) и новый run, числа и зоны — в
  разделе героя `material-library/team-accent.md`. Решает последний прогон TeamAccent.
- `ta_report` с проваленной проверкой останавливает драйвер, как `ta_maps`: код ≠ 0, `ta_manifest` не пишется (F32).
  Читать `ld-team-report.json#checks`. `ta_manifest` принимает профиль вне репо (путь пишется абсолютным, F60).
  Блок `frame` профилю TeamAccent не нужен: `ta_render` снимает только K2 (F24).
- Тона под концепт — предсказание; решение по материалу принимается только по съёмке в UE (4.6,
  `ue_hero_lookdev.py review`), не по прогнозу `lookdev_r2.py forecast`.

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
   Внутри: `clip_author.py` → `validate_clip.py --skeleton=UM_HUMANOID_17_v2 --character=<character>` (поле
   `character` spec — ключ `rig-contract.json`, например `Arthur`, а не `KingArthur`; `h2anim_run.py:89`) →
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
   Look-dev съёмка: `python tools/art/material_library/ue_hero_lookdev.py review --config <review-config.json> --out
   <dir> --tag <tag>` (образец конфига — `ASSET-MEDUSA-001/20260930-h2ld-ldc-ue/review-config.json`; допуски зон против
   концепта — блок `tolerance` конфига: яркость ± 15 %, тон ± 12°, насыщенность ± 0,10). Блокировку `ue_lock`
   команда берёт сама (`ue_hero_lookdev.py:335`) — в `ue_lock.py` не оборачивать, иначе ждёт сама себя.
   `ue_h5cb1.py review --hero` принимает только четырёх зашитых героев (`ue_h5cb1.py:655`), новый герой через него
   не проходит.
7. Снимок после с `--compare <evidence>/snapshot-before.json`: `protected_unchanged: true`, добавлены только свои ассеты.

### 4.7 Подключение в игру S08 (обязательно для героя и помощника)

Без подключения игра молча показывает старую фигуру, а приёмка героя идёт по кадрам в игре (скилл
`.agents/skills/3d-model-pipeline`, этап 7; решение скилла по делегированию пользователя 2026-10-06). Пропс в S08
не подключается.

Новый или переименованный герой требует трёх правок, иначе игра молча откатится на старую фигуру
(`S08FighterActor.cpp:521-547`: нет меша, скелета, подставки, MI или Idle → fallback):

1. Строка в таблице `Specs()` `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp`: имя бойца с сервера, ключ,
   стадия, бюджет высоты, диапазон, измеренный верх фигуры, верх bounds, длина Idle.
2. Три строки `+DirectoriesToAlwaysCook` в `unreal/Unmatched/Config/DefaultGame.ini` (`<Key>/<Stage>`, `<Key>/Rig`,
   `<Key>/H2Anim`): `LoadObject` — мягкая ссылка, кукер иначе выбросит ассеты. Проверять по `UnrealPak <…>.utoc
   -List`: ассеты лежат в IoStore, листинг `.pak` даёт 0 строк даже при успешном куке (проверено 2026-10-09).
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
- [ ] Реестр обновлён, `validate_registry.py` до и после правки — новых ошибок нет (базовая ошибка UM-MASTERS, 3.2
      п.1); `DIRECTORY-MAP.md` — если появились новые каталоги.
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
| Верх фигуры (§2.10 до 2026-10-14) | «по профильной части, оружие выше фигуры проверку не валит» | `prepare` берёт самую высокую вершину с оружием и рогами; верх бюджета — `scale.figure_top_part` |
| Сетка лучей `seams` | rest + `margin_m` (обход пилота — `margin_m 0.2`) | расширяется по позам сама (`posed_clearance_m`), `margin_m 0.1` |
| Цвет P2 | `#9FC2D8` (С-11) | `#5A7F9F` |
| `17 §7` (2026-09-25) | «пресет и оси не подтверждены» | подтверждены ART-001 |
| Сокет `Weapon` Harpy | кисть (rig-contract) | `foot.R` (профиль) — расхождение открыто |
| CLI-версия | 0.6.0 в PIPELINE.md | 0.8.0 (`skeletal-adopt`, `ue.target_skeleton` описаны в `king-arthur-h2-ue-import.md`) |
| Синхронизация со скиллом `3d-model-pipeline` (2026-10-09, по проверкам раунда 1) | 3.2: `prepare-generation` без `init`, журнал `ledger_append.py`, имена `<asset>-tripo-<task8>-…glb`, `validate_registry` → PASS; 4.5: `--character=<Hero>`; 4.6 п.6: `ue_h5cb1.py review`; 4.7: «только если задача включает», `UnrealPak -List` по `.pak`; 8: PASS реестра | 3.2: `init --primary-source tripo-pending` до `prepare-generation`, `tools/art/visual/ledger.py add` в `docs/game-design/visual/credits-ledger.json`, `<key>-h2-tripo-<task8>-…glb`, «новых ошибок нет» против базовой линии; 4.5: ключ `character` из spec; 4.6 п.6: `ue_hero_lookdev.py review --config`; 4.7: обязательно для героя и помощника, листинг `.utoc`; 8: то же правило реестра |

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
