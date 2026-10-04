# M_UM_Figure v2 — мастер фигур на библиотеке материалов UM v1

Дата: 2026-09-29. Задача волны LD: **LD-master**. Статус: **технически импортировано и измерено** в живом редакторе
главного checkout (DX12/SM6 + Lumen, High). Это не приёмка K1–K3: кадры — диагностика редактора, без отпечатка RENDER.
Герои на v2 ещё не переведены — это задачи LD-<hero>. Мастера v1 (`/Game/UM/Materials/M_UM_*`) и их текстуры не
тронуты, байты проверены. Платных операций не было.

**v2.1 (2026-09-30, look-dev C, задача M): краситель по маске TeamAccent** — static switch `UseTeamAccent`, по
умолчанию включён. Решение пользователя «Акценты + кольцо»: цвет команды — только на акцентах одежды (кайма, пояс, кушак,
подкладка, лента) и на подставке, сам герой остаётся в цветах концепта. Путь v2.0 (TeamMask × `teamDyeAllowed`) оставлен
за выключенным свитчем. Подробности — §3 п. 7, §6.1, решения LDV-12…LDV-16.

Архитектура взята из [README библиотеки](README.md), §3–§7. Здесь описано, как она реализована и где от неё отступили.
Решения с номерами LDV-* записаны в [журнале решений LD](../../game-design/decisions/2026-09-29-lookdev-v2-decisions.md).

## 1. Что создано

| Ассет (UE) | Что это | Настройки |
|---|---|---|
| `/Game/UM/Materials/v2/M_UM_Figure_v2` | мастер: Opaque, Shading Model = From Material Expression, Use Material Attributes; usage: Skeletal Mesh, Instanced Static Meshes | v2.1: 71 узел, 85 связей (v2.0: 67 / 79); ядро — Custom-узел `UM_V2_Core` |
| `/Game/UM/Materials/v2/MI_UM_Figure_v2_Template` | MI-шаблон: все значения по умолчанию, MatID legacy | без MatID героя выглядит как v1 (§5) |
| `…/v2/Textures/T_UM_DetailN_Array` | Texture2DArray 16 × 1024², срез = класс | TC_Normalmap (BC5), sRGB off, WorldNormalMap, мипы из источника, Wrap |
| `…/v2/Textures/T_UM_DetailRMH_Array` | Texture2DArray 16 × 1024² | TC_BC7, sRGB off, World, мипы из источника, Wrap |
| `…/v2/Textures/T_UM_MatLUT_Global` | LUT 16 × 16 RGBA16F | TC_HDR, Nearest, без мипов, NeverStream, sRGB off |
| `…/v2/Textures/T_UM_MatID_Legacy` | MatID по умолчанию 4 × 4, всё = класс 0 | TC_Grayscale (G8), Nearest, без мипов, NeverStream, sRGB off |
| `…/v2/Test/*` | 66 тестовых MI и 4 тестовые текстуры (шахматка MatID, бейк шахматки, рампа кромки, v2.1: `T_UM_Test_AccentHalf` — TeamAccent = 1 при v < 0.5) | см. §6 |

Файлы в репозитории:

| Файл | Роль |
|---|---|
| `tools/art/material_library/build_ue_inputs.py` | хост: массивы деталей (DDS 2D array), LUT (глобальная и героя через `--hero --overrides`), тестовые текстуры, отчёт `art/material-library/v2-ue/ue-inputs-report.json` |
| `tools/art/material_library/ue_v2.py` | хост-драйвер живого редактора: `import [--only]`, `master`, `scene`, `accent --phase …`, `stats`, `v1check`. Каждый шаг в редакторе — под общей блокировкой `C:/tmp/ue-editor.lock` |
| `tools/art/material_library/ue_v2_accent.py` | v2.1: тест красителя по частям (`baseline`, `wall`, `gain`, `hero-merlin`, `hero-medusa`, `summary`), §6.1 |
| `tools/art/material_library/ue_lock.py` | эксклюзивная блокировка общего редактора (owner `look-dev-C`, ожидание 20 с, устаревшая — через 25 мин) |
| `tools/art/material_library/ue/um_v2_p17_cleanup.py` | аварийная уборка контрольного уровня P1.7 и выгрузка пробных пакетов без сохранения |
| `tools/art/material_library/ue_v2_master.py` | граф мастера и список MI (данные, сигнатура графа) |
| `tools/art/material_library/ue_v2_scene.py` | контрольная сцена, кадры, замеры |
| `tools/art/material_library/ue/um_v2_core.hlsl` | код ядра (Custom-узел) |
| `tools/art/material_library/ue/um_v2_import.py`, `um_v2_master.py`, `um_v2_scene_ue.py`, `um_v2_stats.py` | задачи, которые выполняются внутри редактора (через `tools/tripo-pipeline/review/ue_live.py`) |
| `tools/art/material_library/tests/test_build_ue_inputs.py` | 9 тестов раскладки LUT, DDS, декодирования MatID |
| `tools/art/material_library/tests/test_ue_v2_master.py` | v2.1: свитч и его умолчание, проводка маски, правило усиления, тестовые MI |
| `docs/art-pipeline/material-library/evidence/v2-master/` | отчёты и кадры (§6–§8) |

Порядок сборки (воспроизводимо):

```bash
python tools/art/material_library/build_ue_inputs.py            # массивы, LUT, тестовые текстуры (байты повторяются)
python tools/art/material_library/ue_v2.py import  --report docs/art-pipeline/material-library/evidence/v2-master/import
python tools/art/material_library/ue_v2.py master  --report docs/art-pipeline/material-library/evidence/v2-master/master
python tools/art/material_library/ue_v2.py scene   --report docs/art-pipeline/material-library/evidence/v2-master/scene-r3 --tag r3
python tools/art/material_library/ue_v2.py stats   --report docs/art-pipeline/material-library/evidence/v2-master/stats
python tools/art/material_library/ue_v2.py v1check --report …/v1-after --v1-baseline …/v1-before/um-v2-v1check-report.json
python -m unittest discover -s tools/art/material_library/tests  # 29 тестов, включая 9 новых
```

v2.1 (порядок прогона 2026-09-30; каталог отчётов `evidence/v2.1-accent/`, кадры без потерь — в `C:/tmp/ldc-m/frames`):

```bash
python tools/art/material_library/build_ue_inputs.py
python tools/art/material_library/ue_v2.py v1check --report …/v2.1-accent/v1-before
python tools/art/material_library/ue_v2.py import  --report …/v2.1-accent/import --only T_UM_Test_AccentHalf
python tools/art/material_library/ue_v2.py accent  --phase baseline --report …/v2.1-accent/baseline   # до пересборки (v2.0)
python tools/art/material_library/ue_v2.py master  --report …/v2.1-accent/master --tag v2.1
python tools/art/material_library/ue_v2.py accent  --phase wall        --report …/v2.1-accent/wall
python tools/art/material_library/ue_v2.py accent  --phase gain        --report …/v2.1-accent/gain
python tools/art/material_library/ue_v2.py accent  --phase hero-merlin --report …/v2.1-accent/hero-merlin
python tools/art/material_library/ue_v2.py accent  --phase hero-medusa --report …/v2.1-accent/hero-medusa
python tools/art/material_library/ue_v2.py accent  --phase summary     --report …/v2.1-accent/summary  # без редактора
python -m pytest -q tools/art/material_library/tests                   # 46 тестов
```

Массивы DDS (по 64 МБ) не коммитятся (`art/material-library/v2-ue/.gitignore`): скрипт пересобирает их из тайлов v1
байт-в-байт, sha256 записаны в отчёте. LUT, тестовые PNG и отчёт коммитятся.

`master` пересобирает граф на месте: выражения удаляются по одному и создаются заново. Поэтому ассет не меняет
идентичность, и MI героев сохраняют родителя. `MaterialEditingLibrary.delete_all_material_expressions` оставлял около
трети узлов (замер: 100 выражений после пересборки графа из 67), поэтому он не используется.

## 2. Граф

```
текстуры героя (имена и умолчания v1) + EdgeMaskTexture ─┐
MatIDTexture, MatLUT (TextureObjectParameter, Load) ─────┤
массивы DetailN / DetailRMH (TextureObject, SampleGrad) ─┼─> Custom UM_V2_Core ─> BC, roughness, metallic, specular,
PreSkinnedPosition/Normal через VertexInterpolator ──────┤                        AO, normal, Cloth, Fuzz, IsCloth,
UV0; UV1 (StaticSwitch UseUV1Metres); ручки; TeamColor ──┤                        отладочный emissive
маска красителя: StaticSwitch UseTeamAccent (v2.1) ──────┘
    true (по умолчанию) -> TeamAccentTexture.R, UseAccent = 1;  false -> TeamMaskTexture.R, UseAccent = 0
цепочка CUE v1 (CPD FxFlash / Rim / Fade) поверх BC ядра; If(IsCloth > 0.5) -> ShadingModel Cloth | DefaultLit
всё -> MakeMaterialAttributes (пин ClearCoat = CustomData0 = Cloth, пин SubsurfaceColor = Fuzz Color)
```

MakeMaterialAttributes используется потому, что в Python-перечислении `MaterialProperty` 5.8 нет `MP_CustomData0` и
`MP_ShadingModel`: к этим выходам напрямую из Python не подключиться. Пины атрибутов дают те же входы.

### Параметры MI

| Группа | Параметры | По умолчанию |
|---|---|---|
| Textures | `BaseColorTexture`, `NormalTexture`, `ORMTexture`, `TeamMaskTexture` (как в v1), **`EdgeMaskTexture`**, **`TeamAccentTexture`** (v2.1, R, linear grayscale) | текстуры v1; EdgeMask и TeamAccent = `T_UM_Mask_Black` (износа нет, красителя нет) |
| Library | **`MatIDTexture`**, **`MatLUT`**, `DetailStrength` 1, `WearStrength` 1, `SheenStrength` 1, `MetresPerLocalUnit` 0.01, static switch `UseUV1Metres` false | MatID legacy, LUT глобальная |
| Team | static switch **`UseTeamAccent`** (v2.1), `TeamColor`, `TeamDye`, `TeamDyeGain` (как в v1), **`TeamDyeCeiling`** (v2.1) | `UseTeamAccent` true; `TeamDyeCeiling` 0 (= только `TeamDyeGain`); остальное как v1 |
| Knobs | `RoughnessMin/Max`, `NormalStrength`, `AOToBaseColor`, `Saturation`, `ValueLift`, `EmissiveIntensity`, `RimColor` (как в v1) | нейтральные, как v1 |
| CustomPrimitiveData | `CPD_TeamColor` 0–3, `CPD_FxFlash` 5–8, `CPD_RimIntensity` 9, `CPD_RimWidth` 10, `CPD_Fade` 11 (раскладка v1); **`CPD_HitTint` 12** (v2.2, только v2) | 0 |
| Cue | **`HitTintColor`** (0.85, 0.03, 0.02), **`HitTintStrength`** 0.7, **`HitTintEmissive`** 0.35 (v2.2) | как указано |
| Debug | `DebugView` (0 выкл.; 1 класс, 2 roughness, 3 metallic, 4 нормаль детали, 5 износ, 6 итоговая нормаль, 7 альбедо, 8 fuzz, 9 RMH тайла, 10 вес красителя (v2.1); вывод в emissive, поверхность чёрная), `DebugMatIDOverride` (−1 = из текстуры; 0–15 = весь материал один класс), `DebugBakeFromLUT` (1 = бейк заменён типичным цветом класса) | 0 / −1 / 0 |

Имена и раскладка CPD совпадают с v1, поэтому MI героя переносится сменой родителя и добавлением трёх текстур:
MatID, LUT героя и EdgeMask.

## 3. Ядро `UM_V2_Core` (ue/um_v2_core.hlsl)

1. **Класс.** `id = floor(MatID.Load(frac(UV0)·size).r · 255/16)`, значение = index·16 + 8. Размер MatID любой:
   1K, 2K или 4K (Merlin и Medusa берут 2K — LDM-4, LDD-10).
2. **Параметры класса.** 10 чтений `Load` из LUT: строки 0–9, столбец = класс (раскладка — §4).
3. **Класс 0 (legacy_bake)** повторяет граф v1 один в один: roughness = lerp(RoughnessMin, RoughnessMax, ORM.G),
   metallic = ORM.B, AO = ORM.R, нормаль героя, краситель через маску красителя (п. 7: TeamAccent или TeamMask).
   Деталь не читается — это ветка `[branch]`.
4. **Деталь.** Экранные производные считаются до ветвления, в ветке используется `SampleGrad`.
   - `UseUV1Metres = false` (по умолчанию: у героев пока нет UV1) — трипланар по `PreSkinnedLocalPosition` в метрах
     (`× MetresPerLocalUnit`) с UDN-смешиванием, веса |N|⁴. Позиция и нормаль до скиннинга приходят через
     `VertexInterpolator`: деталь не плывёт при анимации. Цена — 6 выборок массивов.
   - `UseUV1Metres = true` — UV1 × tilesPerMeter. Касательная UV1 строится по производным (кокасательный базис,
     Schüler 2013), поэтому **острова UV1 можно поворачивать** относительно UV0: волокно дерева вдоль U (LDM-8)
     поддерживается без доработки. Цена — 2 выборки.
   - Возмущённая нормаль в пространстве до скиннинга переводится в касательное пространство героя. Базис UV0 строится
     по производным: X = ∇u0, Y = **+∇v0**, Грам — Шмидт по интерполированной нормали. Конвенция Y проверена в движке
     (§6, зонд). Затем нормаль смешивается с нормалью героя через reoriented normal blend
     (`BlendAngleCorrectedNormals`). Результат не зависит от скиннинга: в пространство скинированного касательного
     базиса переводит движок.
5. **Roughness** = clamp(rTyp + (RMH.r − 0.5)·2·variation·DetailStrength, lo, hi). **AO** = ORM.R · lerp(1, RMH.g, 0.5).
6. **BaseColor.**
   - Металл: F0 пресета × clamp(Y(бейк)/Ymed_class_hero, 1 ± m) × полость (cavityDarken). При Ymed = 0 (глобальная
     LUT) модуляции нет.
   - Диэлектрик: бейк зажат в полосу яркости класса и потолок каналов, × lerp(1, RMH.g, 0.35). У кожи полости
     тонируются красным (строка 9, `subsurfaceApprox` пресета).
7. **TeamColor.** Формула красителя — как в v1: `dyed = lerp(BC · Team, Team · Y(BC) · gain, TeamDye)`,
   `BC = lerp(BC, dyed, w)`. Вес `w` и `gain` задаёт static switch `UseTeamAccent` (v2.1, LDV-12):
   - **`UseTeamAccent = true`** (по умолчанию): `w = TeamAccentTexture.R` для **любого** класса, включая класс 0.
     `teamDyeAllowed` в шейдере не участвует: это правило разметки маски (team-accent.md), а не затвор шейдера.
     Усиление `gain = min(TeamDyeGain, TeamDyeCeiling / maxChannel(Team))` при `TeamDyeCeiling > 0`, иначе
     `TeamDyeGain` (LDV-13). Так один MI героя даёт каждому цвету команды (P1, P2, `CPD_TeamColor`) своё усиление по
     правилу team-accent.md: `TeamDyeGain = 0.8 / Y_p50`, `TeamDyeCeiling = 0.9 / Y_p95` (Y — яркость BC под маской).
   - **`UseTeamAccent = false`** — путь v2.0 без изменений: `w = TeamMask.R × teamDyeAllowed` класса (класс 0 — только
     TeamMask), `gain = TeamDyeGain`, `TeamDyeCeiling` игнорируется. По пресетам краситель разрешён двум видам кожи,
     шерсти, льну, шёлку и перьям.
   Что красится, решает маска: при чёрной маске (умолчание `T_UM_Mask_Black`) не красится ничего. Если маска попадёт на
   металл, краска ляжет на его F0 (metallic не меняется) — такие пиксели маска акцентов не должна содержать.
8. **Износ** = sat(EdgeMask · wearStrength · 2 − (1 − RMH.b)) · WearStrength · smoothstep(0.3, 0.8, AO): в полостях износа
   нет. Изношенный цвет: у металлов — абсолютный (голый металл), у диэлектриков — BC × scale. Roughness изношенного
   места — абсолютная или со сдвигом. Metallic не меняется.
9. **Ручки v1** применяются ко всем пикселям: AO → BC, насыщенность, подъём значения.
10. **Ткань.** IsCloth = строка 3.A, Cloth = clothAmount, Fuzz Color = sheenI · SheenStrength · lerp(1, BC/Y, tint) ·
    √Y. Fuzz считается от итогового альбедо, поэтому блик крашеной ткани тоже в цвет команды.

## 4. LUT: 16 × 16 RGBA16F (отступление от README §4 — LDV-1)

| Строка | R | G | B | A |
|---|---|---|---|---|
| 0 | BC typical r | g | b | metallic |
| 1 | roughness typical | lo | hi | variation |
| 2 | specular | clothAmount | bakeLuminanceModulation | bcMode (1 = F0 пресета) |
| 3 | sheen intensity | sheen tint | sheenRoughness (резерв Substrate) | shadingModel (1 = Cloth) |
| 4 | tilesPerMeter (для тайла 512 — ÷2) | normalStrength | срез массива | cavityDarken |
| 5 | wear strength | wornRoughness (−1 = нет) | wornRoughnessDelta | wornBCScale |
| 6 | worn BC r | g | b | wornBCMode |
| 7 | luminance min | luminance max | maxChannel | teamDyeAllowed |
| **8** | **ymedClassHero** (0 = нет данных) | резерв | резерв | резерв |
| **9** | cavity tint r (кожа) | g | b | strength |
| 10–15 | резерв (0) | | | |

LUT хранится в DDS `R16G16B16A16_FLOAT`, максимальная ошибка half — 0.0016. LUT героя пишет тот же скрипт:
`build_ue_inputs.py --hero <Имя> --overrides <json>`, формат переопределений — `{"classes": {"<класс>": {"<поле>":
значение, "bc": [r, g, b]}}}`. Так уже работает Medusa (LDD-6). Merlin положил Ymed в строку 7.R EXR 16 × 8 (LDM-7): эту
LUT при импорте в UE нужно пересобрать этим генератором со строкой 8, иначе строка 7.R (luminance min) будет испорчена.

## 5. Массивы деталей и правки тайлов v1

DDS 2D array (DX10, 16 срезов по 1024², RGBA8) импортируется в UE сразу как `Texture2DArray`. Отдельные ассеты
Texture2D под каждый срез не нужны. Исходник внутри uasset весит 20.7 МБ (N) и 31.8 МБ (RMH). Срез 0 плоский. Тайлы
512 px (лён, шёлк, кожа персонажа) повторены 2 × 2, их `tilesPerMeter` в LUT поделён на 2.

Известные мелочи v1 исправлены при сборке срезов. PNG тайлов v1 не меняются; все правки и их числа записаны в
`ue-inputs-report.json`.

| Проблема v1 | Правка | Результат |
|---|---|---|
| DetailN `gold_antique` и `stone_base` почти плоские (RMS xy 0.006 = уровень квантования 8 бит) | нормаль строится по собственной высоте тайла (B): периодические центральные разности, предварительное периодическое размытие σ = 1.0 / 1.5 px | RMS xy 0.045 (рельеф ручной ковки) и 0.035 (шлифованный камень) — арт-значения |
| `brass`: нормаль плоская и высота постоянная (B = 0.5) | рельеф взять неоткуда | **остаток**: латунь без детали нормали; героям v1 латунь не назначена |
| наклон нормали: среднее xy до 0.009 у бронзы, клинков и кованого металла | среднее xy вычтено у всех срезов | среднее 0 |
| R-вариация процедурных тайлов не центрирована: кожа 0.588, шёлк 0.538, перья 0.468 | R сдвинут к среднему 0.5 | средняя roughness класса равна typical пресета |

## 6. Проверки

| Проверка | Результат | Где |
|---|---|---|
| Компиляция в редакторе (PCD3D_SM6), `MaterialEditingLibrary.recompile_material` | ошибок нет | `evidence/v2-master/master/um-v2-master-report.json` |
| **SM5-фолбэк и SM6 в cook**: копия `/Game/UM/Materials` в отдельном контент-проекте `C:/tmp` (конфиг рендера и `D3D12TargetedShaderFormats` SM6 + SM5 из `unreal/Unmatched`), `-run=cook -targetplatform=Windows -cookall` | `Success - 0 error(s), 0 warning(s)`. Шейдеры мастера и MI с UV1-перестановкой скомпилированы для PCD3D_SM5 и PCD3D_SM6. Повторный cook не нашёл их недостающими — оба лежат в DDC | `evidence/v2-master/sm5-cook/cook-summary.txt` |
| Статистика (редактор, SM6) | v1: PS 417 инструкций, VS 313, 7 сэмплеров. **v2: PS 695, VS 315, 10 сэмплеров** (лимит SM5 — 16), 6 скаляров интерполяторов. MI с UV1: PS 691, 4 UV-скаляра | `evidence/v2-master/stats/` |
| Касательный базис ядра против `Transform(Local → Tangent)` движка (зонд на сфере) | ошибка при Y = +∇v — **0.3** уровня sRGB (p95 0), при Y = −∇v — 185.6: конвенция верна | `scene-r3/um-v2-probe.jpg`, отчёт `measurements.probe` |
| Краситель только на разрешённых классах (TeamColor красный на всех пикселях) | **16/16** верно: изменились legacy, обе кожи, шерсть, лён, шёлк, перья. Золото, латунь, бронза, стали, камень, дерево и кожа персонажа не изменились (Δ ≤ 3 уровня — шум) | `scene-r3/um-v2-sheet-wall.jpg`, `dye_check` |
| Шахматка MatID (реальный Load, 1K на UV0) | границы классов резкие, по ячейкам; перестановка UV1 рендерит деталь | `um-v2-checkers.jpg`, `um-v2-checker-close*.jpg` |
| Модель затенения по пикселям | в G-buffer у шерсти, льна и шёлка — Cloth, у остальных — DefaultLit; Fuzz есть только у ткани | `um-v2-wall-front-buffers.jpg` |
| **Нулевая регрессия v1** | файлы v1 (3 мастера + 5 текстур) совпадают по sha256 до и после, в редакторе не грязные. Merlin H2 с MI v1 и те же значения на v2 (MatID legacy): **G-buffer совпадает** — base colour, нормаль, roughness, metallic, модель затенения, AO и subsurface одинаковы до бита JPEG; specular — среднее 0.0006, максимум 2 уровня. Кадр со светом: v1↔v2 — 2.0 уровня против шума v1↔v1 1.31 | `v1-before/`, `v1-after/`, `scene-r3/um-v2-merlin-legacy-*.jpg`, `regression_legacy*` |
| Тесты | 29/29 (20 старых и 9 новых), `validate_library.py` — все проверки PASS | — |

### 6.1. v2.1 — краситель по TeamAccent (2026-09-30)

Кадры — диагностика редактора (DX12/SM6 + Lumen, High, SP 100, свет Cobble, уровень P1.7), не приёмка K1–K3. Каждая
часть — под общей блокировкой редактора; после каждой открыт прежний уровень (`/Game/S08/S08Arena`, не грязный), пробные
пакеты `_probe` удалены без сохранения. Сводка: `evidence/v2.1-accent/summary/um-v2-accent-report.json` — `all_ok`
true, 8/8 проверок.

| Проверка | Результат | Где |
|---|---|---|
| Компиляция в редакторе (SM6) | ошибок нет; 71 узел, 85 связей, сигнатура графа `432b36b4…`, ядро `95358edf…` | `master/` |
| SM5 и SM6 в cook (копия `/Game/UM/Materials` в `C:/tmp`, конфиг `unreal/Unmatched`) | `Success - 0 error(s), 0 warning(s)`, 665 пакетов; повторный cook — недостающих шейдер-карт v2 нет. Байты мастера и MI в копии = в checkout (sha256) | `sm5-cook/cook-summary.txt` |
| Статистика | PS 698 инструкций (v2.0: 695), VS 315, 10 сэмплеров (свитч оставляет один сэмплер маски) | `master/` |
| **Путь v2.0 не изменился** (`UseTeamAccent = false`, стена `_Red`) против мастера v2.0 (кадры `baseline`, без потерь) | G-buffer: base colour, metallic, roughness, нормаль, модель затенения — **максимум 0**; specular — среднее 0.014, максимум 2. Краситель v2.0 16/16 классов как в LDV-7. Освещённые диски классов ≤ 5.8 уровня при шуме пары кадров 2.4 (среднее по кадру) | `wall/` → `legacy_regression_vs_v20`, `dye_check_v20` |
| **Краска только под маской, любой класс** (TeamAccent = 1 на верхней половине сферы, TeamColor красный) | 16/16: альбедо (DebugView 7) маскированной половины меняется на 17–201 уровень, свободной — ≤ 0.52 (золото 0.15, латунь 0.19, бронза 0.11, кожа персонажа 0.18, камень 0.24, дерево 0.16) | `wall/um-v2-acc-wall-albedo-*.jpg`, `acc-sheet-wall.jpg`, `dye_check_accent` |
| Вес красителя (DebugView 10) на шахматке MatID | с TeamAccent: верх 223, низ ≤ 1.1 (не зависит от класса); путь v2.0 — по `teamDyeAllowed` ячеек | `gain/um-v2-acc-checkers.jpg` |
| Правило усиления (одна сфера, MI меняются) | 8/8 пар: чёрная маска = без красителя (0.01), потолок срабатывает / не срабатывает / игнорируется в v2.0 (0.01), Merlin P1 11.175 и P2 26.01 = MI с готовым усилением (0.01); чувствительность: усиление 10 против 20 — 43 уровня | `gain/` → `gain_rule` |
| **Герои (Merlin, Medusa H2LD, настоящая маска TeamAccent 2K, C-11 P1/P2, несохранённые пробные MI от `_Neutral`)**, front и back | вес 0: > 6 уровней меняются ≤ 0.2 % пикселей (Merlin 0.01–0.20 %, Medusa 0.03–0.11 %), смещение в тоне команды ≤ 0.02 уровня — металлы, золото, бронза, кожа персонажа, дерево, legacy не меняются; высокий вес: ≥ 99.96 % пикселей меняются > 6, и P1 ≠ P2 на ≥ 99.99 % | `hero-merlin/`, `hero-medusa/`, листы `acc-sheet-<hero>-{front,back}.jpg` |
| v1 | 3 мастера и 5 текстур v1 — sha256 до = после, в редакторе не грязные | `v1-before/`, `v1-after/` |
| Тесты | 50/50 (`test_ue_v2_master.py`: свитч, проводка, правило усиления, тестовые MI, анализ зон героя) | — |

Как мерились герои: зоны — только пиксели, где DebugView 1 декодировал класс (тень фигуры на полу отличается от «плиты» и
иначе попадает в зону). Отладочные кадры снимаются с `ShowFlag.Bloom 0`: блум ярких окрашенных акцентов даёт аддитивную
дымку в тоне команды (Merlin P1 — до 0.8 уровня у акцента и 0.2 на 60 px), первый прогон принял её за утечку (LDV-16).
Средний модуль разницы P1 − Neutral на зоне веса 0 — 0.39–0.46 уровня без смещения (±1 уровень шума захвата после смены
материала); пара Neutral − Neutral — 0.0002–0.002. Освещённые кадры P1/P2 — справочно: отражения и отскок Lumen от
окрашенного акцента доходят до соседних пикселей.

Остаток регрессии в освещённом кадре — 0.7 уровня сверх шума при одинаковом G-buffer. Значит, разница возникает в
проходах освещения, а не в материале. Вероятные причины: история Lumen/TSR при смене материала или захват карточек
surface cache. Причина не доказана, записана как остаток.

### 6.2. v2.2 — заливка удара `CPD_HitTint` (DE-010, 2026-10-04)

Зачем: CUE-011 (01 F-03) красит цель красной заливкой в кадр контакта выпада — 450 мс, при смерти 550 мс. Кривую задаёт
код боя (DE-018); мастер даёт только параметр.

- **Слот.** CPD 12, скаляр `CPD_HitTint`, 0…1, по умолчанию 0. Раскладка v1 (CPD 0–11, `art/um-materials/um-masters.json`)
  не тронута: слот только у v2 (`V2_CPD` в `ue_v2_master.py`), мастера v1 и их тесты не меняются. C++ —
  `S08HeroesV2::HitTintCpdIndex`, `HitTintParamName`.
- **Граф.** После `Fade`: альбедо `lerp(x, HitTintColor, HitTint × HitTintStrength)`; к emissive добавляется
  `HitTintColor × HitTint × HitTintEmissive` через `EyeAdaptationInverse` (единицы экрана, не зависит от экспозиции).
  При 0 обе ветви дают ровно прежний результат (`lerp(x, c, 0) = x`, `+ 0`).
- **Ручки** (группа Cue, MI может переопределить): цвет (0.85, 0.03, 0.02) линейный, сила 0.7, свечение 0.35. Это
  предложение; вид заливки — кандидат до листа A/B (DE-028).
- **Сборка.** Тем же построителем `ue/um_v2_master.py` (граф пересобран на месте, личность ассета сохранена), но без MI:
  `instances` пуст, MI героев и тестовые MI не пересохранялись. Запуск — `tools/art/de010/de010.py apply`
  (UnrealEditor-Cmd без окна). Ошибок компиляции нет; 82 узла, 98 связей, сигнатура графа `8490f47c…`; PS 710
  инструкций (v2.1: 698), VS 315, сэмплеров 10.
- **Проверка** (`docs/art-pipeline/evidence/de010-2026-10-04/de010-report.json`, `all_ok`). Пустая карта, четыре v2-фигуры
  в MI P1, SceneCapture2D без Lumen GI и отражений, без TAA и блума, ручная экспозиция; кадр детерминирован (два запуска
  «до» совпали побайтно):
  - `CPD_HitTint` 0, до и после: освещённый и unlit-кадр совпадают побайтно (max 0);
  - старый мастер слот 12 не читал: 1 = 0 побайтно;
  - после: 1 меняет 92 тыс. пикселей фигур, «краснота» R − (G + B)/2 растёт с 32 до 173 уровней.
  Кадры редактора — проверка материала, не K1–K3 и не художественная приёмка. Packaged K1 до/после снимает агент приёмки
  прогона A04.

## 7. Как читаются классы (кадры `scene-r3`, свет Cobble, High)

Стена из 16 сфер (сфера движка × 0.2 = 20 см). Класс i стоит в столбце i % 4, строке i // 4. Бейк заменён типичным
цветом класса (`DebugBakeFromLUT`), по U идёт рампа кромки. Средняя яркость диска (sRGB luma) при экспозиции Cobble
(EV100 1.3):

| Класс | luma | p98 | | Класс | luma | p98 |
|---|---|---|---|---|---|---|
| steel_blued | 134 | 213 | | leather_smooth | 77 | 140 |
| steel_polished | 163 | 242 | | leather_worn | 81 | 145 |
| metal_forged | 187 | 238 | | wool_coarse | 178 | 210 |
| gold_antique | 175 | 245 | | linen | 190 | 218 |
| brass | 173 | 246 | | silk | 206 | 228 |
| bronze | 171 | 245 | | feathers | 94 | 161 |
| skin | 188 | 225 | | stone_base | 90 | 164 |
| wood | 85 | 156 | | legacy (белый бейк) | 235 | 245 |

Металлы читаются как металлы: в них отражаются соседние сферы, у полированной стали зеркальный блик, у кованой —
матовый. Воронёная сталь темнее остальных сталей и с синим оттенком (hue 225°). Золото, латунь и бронза тёплые, их
оттенки различаются: 44°, 45° и 34°. Кожа, камень и дерево — тёмные диэлектрики. На шерсти, льне и шёлке виден рельеф
ткани, модель затенения — Cloth.

**Наблюдение о свете (не дефект материала).** SkyLight Cobble — купол-кубкарта × 11.2 — для отражений работает как
равномерно яркое окружение. При экспозиции EV100 1.3 яркие металлы упираются в потолок (p98 ≈ 245), а золото
бледнеет. Воронёная сталь с F0 ≈ 0.2 получает luma 134: светлее, чем «тёмная воронёная сталь» концепта Arthur. Кадры
`*-ev-1p5.jpg` (bias −1.5 EV) показывают, что физика материала верна: там воронёная сталь тёмная, золото насыщенное,
ткань не серая. Что с этим делать:

- если воронёная сталь в кадре героя останется светлой, **не менять F0 класса**. Варианты: переопределение героя в
  его LUT (Arthur, H2.2) или контраст окружения для отражений (кубкарта или reflection capture доски). Это вопрос
  света доски (волна 5b-R), а не мастера;
- приёмочные кадры героев снимать в свете Cobble, как требует render-reference. Кадры −1.5 EV — только для чтения
  материала.

## 8. Кадры и отчёты

`docs/art-pipeline/material-library/evidence/v2-master/`:

- `import/`, `master/`, `stats/` — отчёты: настройки текстур, ошибки компиляции, статистика, параметры, сигнатура
  графа `3b37e213…`;
- `scene-r3/` — кадры 1920 × 1080 с `.evidence.json` (sha256, камера, свет):
  - `wall-front`, `wall-top35`, `wall-rows01/23`, `checkers`, `checker-close`, `probe`, `wall-front-red`,
    `wall-front-buffers`;
  - `*-ev-1p5`;
  - `merlin-legacy-{v1,v2}{a,b}` и `merlin-legacy-buffers-*`;
  - сводный лист `um-v2-sheet-wall.jpg`;
- `sm5-cook/cook-summary.txt` — строки лога cook;
- `v1-before/`, `v1-after/` — sha256 файлов v1 и флаги dirty.

`docs/art-pipeline/material-library/evidence/v2.1-accent/` (v2.1): `v1-before/`, `import/` (`T_UM_Test_AccentHalf`),
`baseline/` (v2.0, до пересборки), `master/`, `sm5-cook/`, `wall/`, `gain/`, `hero-merlin/`, `hero-medusa/`, `v1-after/`,
`summary/`. Кадры JPEG 1920 × 1080 с `.evidence.json`; кадры без потерь (для сравнений) — вне репозитория,
`C:/tmp/ldc-m/frames/<часть>/`.

## 9. Остатки и следующие шаги

- Цена на пиксель в `render_bench.py` (packaged `-Bench`, BasePass) не замерена. Статистика редактора считает обе
  ветки. Реально исполняется: у класса 0 — путь v1 + 11 `Load`; у классов библиотеки — +6 выборок массивов
  (трипланар) или +2 (UV1). Замерить на первом переведённом герое.
- Стриминг Texture2DArray: массивы (~42 МБ BC5/BC7 с мипами) пока постоянно в памяти. На Medium/SM5 нужен LODBias 1
  (README §7), не проверено.
- У `brass` нет рельефа (§5).
- На полюсах UV-сферы движка базис UV0 из производных вырождается (зонд: полоса у южного полюса). У мешей героев
  полюсов UV нет. Вертикальный шов в центре тестовых сфер есть и у legacy-сферы (путь v1): это шов UV меша движка, а не
  деталь v2.
- В освещённом кадре регрессия 0.7 уровня сверх шума (§6).
- v2.1: MI героев без явного свитча наследуют `UseTeamAccent = true`. У Merlin и Medusa H2LD `TeamAccentTexture` ещё не
  назначен — их `_Red`/`_Blue` сейчас без красителя, до задачи H (LDV-15).
- v2.1: если TeamAccent попадёт на металл, краска ляжет на F0 (metallic не меняется). Шейдер это не запрещает (LDV-12) —
  следит разметка маски (team-accent.md).
- v2.1: цена на пиксель в `render_bench.py` не мерилась (статистика редактора +3 инструкции PS).
- Перевод героев на v2 — задачи LD-<hero>. MI героя = шаблон + MatID + LUT героя (формат §4) + EdgeMask (R, linear
  grayscale; у Merlin EdgeMask лежит в TeamMask.A — перед импортом вынести в отдельную текстуру, LDV-8).
