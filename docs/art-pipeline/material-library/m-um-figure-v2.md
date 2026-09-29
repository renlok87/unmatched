# M_UM_Figure v2 — мастер фигур на библиотеке материалов UM v1

Дата: 2026-09-29. Задача волны LD: **LD-master**. Статус: **технически импортировано и измерено** в живом редакторе
главного checkout (DX12/SM6 + Lumen, High). Это не приёмка K1–K3: кадры — диагностика редактора, без отпечатка RENDER.
Герои на v2 ещё не переведены — это задачи LD-<hero>. Мастера v1 (`/Game/UM/Materials/M_UM_*`) и их текстуры не
тронуты, байты проверены. Платных операций не было.

Архитектура взята из [README библиотеки](README.md), §3–§7. Здесь описано, как она реализована и где от неё отступили.
Решения с номерами LDV-* записаны в [журнале решений LD](../../game-design/decisions/2026-09-29-lookdev-v2-decisions.md).

## 1. Что создано

| Ассет (UE) | Что это | Настройки |
|---|---|---|
| `/Game/UM/Materials/v2/M_UM_Figure_v2` | мастер: Opaque, Shading Model = From Material Expression, Use Material Attributes; usage: Skeletal Mesh, Instanced Static Meshes | 67 узлов, 79 связей; ядро — Custom-узел `UM_V2_Core` |
| `/Game/UM/Materials/v2/MI_UM_Figure_v2_Template` | MI-шаблон: все значения по умолчанию, MatID legacy | без MatID героя выглядит как v1 (§5) |
| `…/v2/Textures/T_UM_DetailN_Array` | Texture2DArray 16 × 1024², срез = класс | TC_Normalmap (BC5), sRGB off, WorldNormalMap, мипы из источника, Wrap |
| `…/v2/Textures/T_UM_DetailRMH_Array` | Texture2DArray 16 × 1024² | TC_BC7, sRGB off, World, мипы из источника, Wrap |
| `…/v2/Textures/T_UM_MatLUT_Global` | LUT 16 × 16 RGBA16F | TC_HDR, Nearest, без мипов, NeverStream, sRGB off |
| `…/v2/Textures/T_UM_MatID_Legacy` | MatID по умолчанию 4 × 4, всё = класс 0 | TC_Grayscale (G8), Nearest, без мипов, NeverStream, sRGB off |
| `…/v2/Test/*` | 36 тестовых MI и 3 тестовые текстуры (шахматка MatID, бейк шахматки, рампа кромки) | см. §6 |

Файлы в репозитории:

| Файл | Роль |
|---|---|
| `tools/art/material_library/build_ue_inputs.py` | хост: массивы деталей (DDS 2D array), LUT (глобальная и героя через `--hero --overrides`), тестовые текстуры, отчёт `art/material-library/v2-ue/ue-inputs-report.json` |
| `tools/art/material_library/ue_v2.py` | хост-драйвер живого редактора: `import`, `master`, `scene`, `stats`, `v1check` |
| `tools/art/material_library/ue_v2_master.py` | граф мастера и список MI (данные, сигнатура графа) |
| `tools/art/material_library/ue_v2_scene.py` | контрольная сцена, кадры, замеры |
| `tools/art/material_library/ue/um_v2_core.hlsl` | код ядра (Custom-узел) |
| `tools/art/material_library/ue/um_v2_import.py`, `um_v2_master.py`, `um_v2_scene_ue.py`, `um_v2_stats.py` | задачи, которые выполняются внутри редактора (через `tools/tripo-pipeline/review/ue_live.py`) |
| `tools/art/material_library/tests/test_build_ue_inputs.py` | 9 тестов раскладки LUT, DDS, декодирования MatID |
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
UV0; UV1 (StaticSwitch UseUV1Metres); ручки; TeamColor ──┘                        отладочный emissive
цепочка CUE v1 (CPD FxFlash / Rim / Fade) поверх BC ядра; If(IsCloth > 0.5) -> ShadingModel Cloth | DefaultLit
всё -> MakeMaterialAttributes (пин ClearCoat = CustomData0 = Cloth, пин SubsurfaceColor = Fuzz Color)
```

MakeMaterialAttributes используется потому, что в Python-перечислении `MaterialProperty` 5.8 нет `MP_CustomData0` и
`MP_ShadingModel`: к этим выходам напрямую из Python не подключиться. Пины атрибутов дают те же входы.

### Параметры MI

| Группа | Параметры | По умолчанию |
|---|---|---|
| Textures | `BaseColorTexture`, `NormalTexture`, `ORMTexture`, `TeamMaskTexture` (как в v1), **`EdgeMaskTexture`** | текстуры v1; EdgeMask = `T_UM_Mask_Black` (износа нет) |
| Library | **`MatIDTexture`**, **`MatLUT`**, `DetailStrength` 1, `WearStrength` 1, `SheenStrength` 1, `MetresPerLocalUnit` 0.01, static switch `UseUV1Metres` false | MatID legacy, LUT глобальная |
| Team | `TeamColor`, `TeamDye`, `TeamDyeGain` (как в v1) | как v1 |
| Knobs | `RoughnessMin/Max`, `NormalStrength`, `AOToBaseColor`, `Saturation`, `ValueLift`, `EmissiveIntensity`, `RimColor` (как в v1) | нейтральные, как v1 |
| CustomPrimitiveData | `CPD_TeamColor` 0–3, `CPD_FxFlash` 5–8, `CPD_RimIntensity` 9, `CPD_RimWidth` 10, `CPD_Fade` 11 (раскладка v1) | 0 |
| Debug | `DebugView` (0 выкл.; 1 класс, 2 roughness, 3 metallic, 4 нормаль детали, 5 износ, 6 итоговая нормаль, 7 альбедо, 8 fuzz, 9 RMH тайла; вывод в emissive, поверхность чёрная), `DebugMatIDOverride` (−1 = из текстуры; 0–15 = весь материал один класс), `DebugBakeFromLUT` (1 = бейк заменён типичным цветом класса) | 0 / −1 / 0 |

Имена и раскладка CPD совпадают с v1, поэтому MI героя переносится сменой родителя и добавлением трёх текстур:
MatID, LUT героя и EdgeMask.

## 3. Ядро `UM_V2_Core` (ue/um_v2_core.hlsl)

1. **Класс.** `id = floor(MatID.Load(frac(UV0)·size).r · 255/16)`, значение = index·16 + 8. Размер MatID любой:
   1K, 2K или 4K (Merlin и Medusa берут 2K — LDM-4, LDD-10).
2. **Параметры класса.** 10 чтений `Load` из LUT: строки 0–9, столбец = класс (раскладка — §4).
3. **Класс 0 (legacy_bake)** повторяет граф v1 один в один: roughness = lerp(RoughnessMin, RoughnessMax, ORM.G),
   metallic = ORM.B, AO = ORM.R, нормаль героя, краситель через TeamMask. Деталь не читается — это ветка `[branch]`.
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
7. **TeamColor** = TeamMask.R × `teamDyeAllowed` класса. По пресетам краситель разрешён двум видам кожи, шерсти, льну,
   шёлку и перьям. Металлы, камень, дерево и кожа персонажа не красятся никогда — это правило пользователя из 5c-A.
   Формула красителя — как в v1 (`TeamDye`, `TeamDyeGain`).
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

Остаток регрессии в освещённом кадре — 0.7 уровня сверх шума при одинаковом G-buffer. Значит, разница возникает в
проходах освещения, а не в материале. Вероятные причины: история Lumen/TSR при смене материала или захват карточек
surface cache. Причина не доказана, записана как остаток.

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
- Перевод героев на v2 — задачи LD-<hero>. MI героя = шаблон + MatID + LUT героя (формат §4) + EdgeMask (R, linear
  grayscale; у Merlin EdgeMask лежит в TeamMask.A — перед импортом вынести в отдельную текстуру, LDV-8).
