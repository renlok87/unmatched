# W4-B: мастер-материалы M_UM_*, TeamColor на одежде, AO в ORM.R, явная FbxFactory (волна 4)

Дата: 2026-09-29. Главный checkout `fix/admin-panel` (база 4a1cad9a; при refix HEAD 8c4cd805), живой UnrealEditor 5.8.2 (PID 46136, MCP
127.0.0.1:8123), рендер редактора — DX11 (решение пользователя «DX12 + Lumen сейчас» внедряет оркестратор отдельно; в
главном checkout на момент съёмки `DefaultGraphicsRHI_DX11`). Blender — только headless (`-b`: AO-запекание и сборки
CLI); живые Blender :9876/:9877 не использовались. UnrealEditor-Cmd не запускался, packaged-сборок не было. Tripo и
SYNTX не вызывались: **потрачено 0 кредитов**.

**Основание.** Меморандум engine-gate §1 п. 4–5 (`C:/tmp/p0-review/engine-gate-memo.md`, вне репозитория) и решения
пользователя 2026-09-28, выбранные им в чате (U-1 «DX12 + Lumen сейчас», U-2 «эталон High», U-3 «TeamColor: ещё и на
одежде» — AD-CNF-58 = b, U-4 «гибрид UMG сейчас»). Журнал этих решений ведёт W4-D
(`docs/game-design/decisions/2026-09-29-render-ui-user-decisions.md` — коммитится вместе с W4-D, поэтому здесь без ссылки).

**Исправление по ревью (refix, 2026-09-29 08:50–10:35).** Ревью W4-B подтвердило два дефекта; оба устранены, все
зависимые проверки перезапущены:

1. **Merlin не получал TeamColor на одежде (U-3 не выполнено для него).** Маска T3.3 покрывала только бронзовую
   отделку (8,5 % ячейки мантии, 2,1 % атласа): в кадрах мантия одинакова у обеих команд, 89 % суммарного ΔE
   (deuteranopia) давала полоса подставки, различие фигуры — на уровне шума повторных прогонов. Теперь маска —
   синяя ткань: мантия, капюшон, рукава (§2), краситель `TeamDye 1 / gain 5,5`. Фигура Merlin: серый 0,32 → 3,32,
   deuteranopia ΔE 0,47 → 28,05 при шуме 0,30 / 0,31 (§6).
2. **AO головы Harpy запекалось с гранями «внутрь».** `bake_ao.py` переворачивал только целые части
   (`expected_inside_out_parts`) и не делал пограничного исправления `orientation.per_face_reference` головы
   `tripo_part_2` со смешанной намоткой: 40 % площади головы запекались с нормалью внутрь (AO 0,51, 26 % площади
   < 0,25), гейт диапазона этого не видел. Теперь запекание повторяет исправление build тем же кодом (те же 1 506
   граней), новый гейт `ao_bake_parts_face_outward` проверяет каждую запечённую ячейку; AO этих граней 0,82 (§3).
   Пересобраны ORM Harpy, стадии atlas/build и UE-импорт всех четырёх (FBX и остальные байты не изменились, §4).

Числа и утверждения первого прохода, которые ревью опровергло, ниже исправлены (в первом варианте акта: «Arthur и
Merlin: маски T3.3 пересобраны и проверены» в разделе U-3; рост deuteranopia «в 1,6–9 раз» с Merlin ×9 — это рост
за счёт полосы подставки, не одежды).

**Статусы.** Мастера `M_UM_*`, MI кандидатов, бочка: «технически импортировано» (все проверки CLI и `um_masters.py`
прошли). Маски одежды, dye-ручки, AO-параметры, палитра и её предложение: «предложено». Числа различимости:
«измерено» на **редакторных** кадрах (`editor-mcp-viewport`, 48 кадров и листов, 0 отклонённых —
[classify-evidence.json](classify-evidence.json)): диагностика, не K1/K2-приёмка и не QA-010. «Художественно принято»
не ставится ничему.

## 1. Мастер-материалы (скрипт `tools/tripo-pipeline/um_masters.py`)

```bash
python tools/tripo-pipeline/um_masters.py --backend mcp build --report <report.json>   # 1-й раз: created, 14 мин
python tools/tripo-pipeline/um_masters.py --backend mcp build --report <report.json>   # повтор: skipped, 13 мин
```

| Мастер | Узлов / связей | graph_signature | Модель |
|---|---|---|---|
| `/Game/UM/Materials/M_UM_Figure` | 48 / 51 | `d49f75d3471a…` | DefaultLit, Opaque, односторонний, usage SkeletalMesh + ISM |
| `/Game/UM/Materials/M_UM_BaseMarker` | 87 / 97 | `2892a04818bf…` | DefaultLit, Opaque, usage ISM |
| `/Game/UM/Materials/M_UM_GameLayer` | 16 / 17 | `1f0cd35d0a98…` | Unlit, Opaque, `EyeAdaptationInverse`, usage ISM |

- Проверка `verify` (узел за узлом, [um-masters-report.json](um-masters-report.json)): класс и позиция каждого
  выражения, свойства, 165 связей, выходы, параметры, раскладка Custom Primitive Data, Opaque/односторонность/usage,
  нет WPO/Opacity/OpacityMask, не dirty — **3 × PASS** и при создании ([um-masters-report-first-build.json](um-masters-report-first-build.json)),
  и при повторе (`skipped: the editor graph already equals the plan`).
- CPD (одинаково во всех трёх; 0 — нейтрален): 0–3 `CPD_TeamColor` (rgb + вес над `TeamColor` MI), 4
  `CPD_InstanceIndex`, 5–8 `CPD_FxFlash`, 9 `CPD_RimIntensity`, 10 `CPD_RimWidth`, 11 `CPD_Fade`. Параметр с
  `bUseCustomPrimitiveData` читает CPD примитива, а не своё значение по умолчанию (исходник `MaterialExpressions.cpp`),
  поэтому нейтральность держится на «0 = из MI».
- Нейтральные ручки Figure: `TeamDye 0`, `RoughnessMin/Max 0/1`, `NormalStrength 1`, `AOToBaseColor 0`, `Saturation 1`,
  `ValueLift 0`, `EmissiveIntensity 1`, `RimColor` (1) — при них граф = граф кандидатов
  (`lerp(BC, BC × TeamColor, TeamMask.R)`, DirectX N, ORM R/G/B → AO/Roughness/Metallic).
- Правило цвета (AD-OPEN-39): hex sRGB в данных → `FLinearColor::FromSRGBColor` (`um_masters.hex_to_linear`,
  расхождение с таблицей `sRGBToLinearTable` движка ≤ 3,2e-8). Прочитано из редактора: Gold `#E8C06A` →
  (0,806952; 0,527115; 0,144128), Silver `#9FC2D8` → (0,346704; 0,539479; 0,686685) у всех командных MI.
- Спецификация — [art/um-materials/um-masters.json](../../../../art/um-materials/um-masters.json), дефолтные текстуры
  `art/um-materials/textures/*.png` (`/Game/UM/Materials/Textures`, 5 шт.). `.uasset` (`unreal/Unmatched/Content/UM/**`,
  8 файлов) — в коммит только `git add -f`.
- Особенность чтения, найденная вживую: `get_expression_inputs` при двух входах узла от одного источника сообщает выход
  первого (`lerp(TeamColor, CPD.rgb, CPD.a)` → оба `RGB`); соединение при этом верное — `verify` это учитывает.

## 2. TeamColor на одежде (маски атласа) и на подставке

| Ассет | Маска (`team_color.mask`) | Покрытие ячеек ≥ 0,5 | Ручки MI фигуры | Подставка (`M_UM_BaseMarker`) |
|---|---|---|---|---|
| Medusa | **новая**: платье `tripo_part_0`, `hsv-band-cells` v ≤ 0,3, s ≤ 0,4 (бронза s > 0,45 отпадает) | part_0 98,3 % | `TeamDye 1`, `TeamDyeGain 6` (тёмная ткань v 0,11–0,25) | полоса команды на боковой стенке (`SideBandWeight 1`) |
| Arthur | T3.3 (красная ткань, `hsv-hard-gaussian`) — **байт в байт** та же | part_0 98,7 %, 11 82,7 %, 13 84,2 %, 8 23,1 % | `TeamDye 0` (multiply) | боковая стенка |
| Merlin | **новая (refix)**: синяя ткань — мантия `tripo_part_0`, капюшон `tripo_part_2` (без лица и бороды), рукава `tripo_part_4/5`; `hsv-band-cells` оттенок 205–250°, s ≥ 0,12; бронзовая отделка остаётся бронзой | part_0 74,5 %, 2 59,4 %, 4 95,2 %, 5 97,8 % (атлас 33,6 %) | `TeamDye 1`, `TeamDyeGain 5,5` (тёмно-синяя ткань, linear-яркость 0,027) | боковая стенка |
| Harpy | **новая**: ткани нет — тёмные маховые перья крыльев `tripo_part_0/1`, `hsv-band-cells` v ≤ 0,22 | 60,6 % / 51,9 % | `TeamDye 1`, gain 6 | вершинная маска (полоса R, метки G/B по `InstanceIndex` 1–3 / CPD 4) |

Merlin (refix): маска T3.3 (бронзовая отделка, `hsv-smooth-box`, sha `94e6dcf9…`) одежду не покрывала — в первом проходе
она была записана как «пересобрана и проверена», и это было неверно для решения U-3. В профиле `/3` она заменена синей
тканью. Умножение (`TeamDye 0`) на тёмно-синей ткани даёт почти чёрное у обеих команд, поэтому краситель; gain 5,5
подобран так, чтобы окрашенная ткань Merlin выходила той же яркости, что у Medusa (0,0245 × 6 × 0,534 = 0,0785;
0,0785 / (0,0269 × 0,534) = 5,46). Маска и gain — предложение.

Отступление от подсказки задачи «Harpy — vertex/instance»: номер экземпляра у Harpy остаётся на подставке (вершинная
маска + `InstanceIndex`/CPD 4), а командный цвет фигуры — маской атласа по тёмным перьям крыльев (самая большая площадь
фигуры в K1 сверху). Вершинная маска на скелетном меше потребовала бы менять сборку и байты FBX; атласная маска даёт тот
же результат без правки геометрии. Выбор перьев — предложение арт-треку.

## 3. AO в ORM.R (`atlas.ao_bake`, гейты «не константа» и «грани наружу»)

Cycles CPU, 128 samples, seed 0, расстояние 0,08 × высоты фигуры, вся фигура — окклюдер, `margin 8 px`, фон 1,0;
повторный прогон — те же байты (Cycles CPU детерминирован; измерено дважды на Medusa, отдельно — вторым `run` всех
четырёх). Ориентация граней при запекании — та же, что в build, в том же порядке: (1) пограничное исправление
`orientation.per_face_reference` (голоса граней против high-poly GLB, сглаживание ICM на сваренной копии части в кадре
посадки build; код `candidate_build.orientation`, `mesh_ops.weld_part`, `core.flip_polygons`), (2) целые части
`expected_inside_out_parts`. Затем тест ray-escape build (`measure.orientation_scores`) по сцене запекания — с плоскостью
«пола» под фигурой только для теста; доля площади «внутрь» каждой запечённой ячейки — в `ao-bake-report.json →
orientation_after_flips`, гейт `ao_bake_parts_face_outward` (≤ 0,02). Замеры внутри ячеек атласа
([cli-and-ue-runs.json](cli-and-ue-runs.json), после refix):

| | p1 | p99 | среднее | доля < 250 | не константа | макс. доля «внутрь» по ячейкам | перевёрнуто по эталону |
|---|---|---|---|---|---|---|---|
| Medusa | 3 | 255 | 179,4 | 67 % | PASS | 0,0083 (`tripo_part_10`) — PASS | — |
| Arthur | 8 | 255 | 182,8 | 69 % | PASS | 0,0012 — PASS | — |
| Merlin | 8 | 255 | 193,0 | 61 % | PASS | 0,0008 — PASS | — |
| Harpy | 11 | 255 | 190,2 (первый проход 180,9) | 73 % (75 %) | PASS | 0,0031 (`tripo_part_7`) — PASS | `tripo_part_2`: 1 506 из 1 918 граней |

Три находки (исправлены в `bake_ao.py`, записаны в ADDING §8):

- вывернутые части Tripo запекались почти чёрными (рука Medusa `tripo_part_8`: 0,12 → после переворота как в build 0,71);
- невыпеченный фон был чёрным (теперь 1,0);
- **(ревью)** голова Harpy `tripo_part_2` со смешанной намоткой запекалась без пограничного исправления build: в сцене
  запекания 40,3 % площади головы смотрели внутрь, 16,6 % наружу. Проба `probes/harpy_head_ao_faces.py`
  ([harpy-head-ao-faces.json](harpy-head-ao-faces.json); классы граней — тест ray-escape build в сцене запекания до
  исправления, AO — `ORM.R` атласа в UV-центре грани, взвешено площадью):

  | Класс граней головы (доля площади) | AO первого прохода (ORM `f28a2603…`, не коммитился) | AO после refix (ORM `2f397561…`) |
  |---|---|---|
  | «внутрь» (40,3 %) | 0,509; 25,9 % площади < 0,25 | **0,822; 1,5 %** |
  | «наружу» (16,6 %) | 0,693; 3,0 % | 0,693; 3,4 % |
  | не определено (43,1 %: гребень перьев, вогнутости) | 0,426; 27,5 % | 0,473; 18,7 % |

  Исправление в запекании повторяет build точно: 1 506 перевёрнутых граней, 1 917 граней после сварки,
  5 несогласованных рёбер — те же числа, что `build-report.json → orientation.reference_vote`. Байты AO остальных
  частей Harpy и всех частей Medusa, Arthur, Merlin не изменились (сравнено по sha). Тест ray-escape без «пола» дал
  ложные 4,4 / 6,6 % «внутрь» у ступней Harpy `tripo_part_7/8` (подставка Tripo из сцены убрана, подошвы открыты —
  луч «−нормаль» верхних граней когтей уходил вниз; «+нормаль» упиралась в ногу); с плоскостью — 0,3 / 0,2 %.

**Не измерено:** влияние AO на кадр. `ORM.R` действует только на непрямой свет и SkyLight (критика
меморандума G03); в контрольной сцене SkyLight нет, поэтому кадры «до/после» разницы от AO не показывают — проверка
вместе с профилем света и Lumen (оркестратор).

## 4. Прогоны CLI 0.6.0 (headless) и импорт в живой UE

Профили `/3` (`*-um-fbx-v1-um-master.json`) = `/2` + `atlas.ao_bake` + `team_color.mask` + `ue.*` маршрута
`um-master` (тест `RepoProfilesTests`: ключи сборки те же). Прогоны `art/pipeline-candidates/<ASSET>/20260929-w4b-um-master`:

- import → verify → atlas → build: **FBX обоих мешей байт в байт = 20260928-cli-um-fbx-v1** у всех четырёх, BC/N/N_OpenGL
  тоже; меняются только ORM (AO) и новые TeamMask Medusa/Harpy/Merlin; второй `run` — все стадии `skipped`;
- refix: изменение `bake_ao.py` и модулей библиотеки build в отпечатке atlas перезапустило atlas → build → ue-import у
  всех четырёх без `--force` (отпечатки изменились). Против первого прохода изменились только
  `T_Harpy_Candidate_Atlas_ORM.png` (`f28a2603…` → `2f397561…`) и `T_Merlin_Candidate_Atlas_TeamMask.png`
  (`94e6dcf9…` → `7135a816…`); ORM Medusa/Arthur/Merlin, все BC/N и все FBX — те же байты; отчёты atlas/AO — с новым
  гейтом. UE: `executed` (22/22 Arthur, Merlin; 23/23 Medusa, Harpy; импорт взял новые PNG — хеши во `inputs`
  ue-import-report) → повтор `skipped`; MI Merlin прочитаны обратно с `TeamDye 1`, `TeamDyeGain 5,5` и новой маской;
  бочка — `skipped` (её отпечаток не менялся);
- `ue-import` (`ue-candidate/7`) → `/Game/PipelineCandidates/<Hero>/20260929-w4b-um-master`, 13 ассетов (SK, Skeleton,
  SM, 4 текстуры, MI фигуры + MI подставки + 4 командные MI, **без своего Material**); проверки 22/22 (Arthur, Merlin) и
  23/23 (Medusa: эталон осей; Harpy: вершинные цвета подставки); `executed` → повтор `skipped` → `--force` `executed`
  → `skipped`, `Name_1` нет;
- контракт импорта, прочитанный из редактора: фабрика `FbxFactory`, `AssetImportData` — `FbxSkeletalMeshImportData` /
  `FbxStaticMeshImportData`, `NormalImportMethod = FBXNIM_ImportNormals` у SK и подставки, Nanite выкл., у подставки
  Harpy `VertexColorImportOption = Replace`;
- бочка: профиль `decor-barrel-static-um-fbx-v1-um-master.json` (`/2`), прогон `ASSET-DECOR-KIT-001/20260929-w4b-um-master/ue-candidate`
  → MI от `M_UM_Figure` (отклонений нет, `shared_master_parameters_current`, `nanite_disabled`,
  `normal_import_method_read_back` PASS), идемпотентность та же.

**Инцидент I1 (исправлен).** Первый импорт Medusa: командный скрипт импорта SK в консоли редактора выполнился, но в логе
не оказалось строки `Cmd: py …`; проверка по логу сочла команду потерянной и напечатала её снова (5 раз, повторы
отказали на «already exists»), стадия упала, созданные ассеты не числились в manifest, следующая попытка отказала
(«чужие ассеты»). Исправлено: лаунчер пишет `<out>.started` (так же `ue_py/_run.py` для `ue_live.py`), повтор
печати — только без этого файла; владение ассетами пишется в manifest после каждого создания. 12 сирот своей папки
удалены `ue_delete_owned`, прогон повторён. Причина исходной неустойчивости — общий рабочий стол с параллельной
сессией (SlateInspector: пустое дерево и «Could not focus widget for typing»), тест
`test_lost_console_command_is_typed_again`.

## 5. Клипы: явная FbxFactory, без CVar, bForceRootLock

`tools/tripo-pipeline/review/ue_py/import_clips.py`, живая проверка ([clips-import.json](clips-import.json)): черновой
`AM_Medusa_LungeAttack.fbx` на скелет T4LocalPass → `/Game/PipelineCandidates/Medusa/DraftClipsW4B/T4LocalPass`, дважды.
Оба раза `FbxAnimSequenceImportData` (legacy), `bForceRootLock = true` прочитан обратно, `Interchange.FeatureFlags.Import.FBX`
до/после `True` (не переключался), `Name_1` нет. **Находка:** в первой версии повторный импорт поверх существующего клипа
пошёл путём reimport и дал `InterchangeAssetImportData` даже с явной фабрикой
([clips-import-first-replace-interchange.json](clips-import-first-replace-interchange.json)); теперь скрипт удаляет
свой прежний клип и импортирует заново (`legacy_fbx_import` в отчёте).

## 6. Контрольная сцена P1.7: до и после, команда в сером и при deuteranopia

- Прогоны сцены: «до» — `control_scene.py --asset-set t31` (ассеты T3.1, до этой задачи; тег `before`); первый проход
  W4-B — `--asset-set w4b`, теги `after-r1`, `after-r2` (шум E2 0,243, [analyze-after/](analyze-after/)); после
  исправления ревью — `refix-r1`, `refix-r2` (шум E2 0,257 → порог 0,513, отчёты сцены идемпотентны,
  [analyze-refix/](analyze-refix/)); сокеты Head/Weapon в пределах 0,0006 uu от целей build (FBX те же), бочка на борту
  (z 5,0, `on_surface`). С refix сцена снимает ещё маску «одна подставка» при K2 1,6× (`mask-k2-1p6-base-<name>`).
- Кадры: [frames/before](frames/before), [frames/after](frames/after) (= `refix-r1`: K1, K2 1,6× и 5× каждого героя, своп
  команды `team-alt`, `team-prop` — предложение палитры); листы «цвет / серый / deuteranopia / фигура-подставка» по
  героям для `before`, `after-r1` (первый проход) и `refix-r1` — [frames/derived](frames/derived), собраны из
  закоммиченных входов (sidecar называет их пути).
- Метрика ([team-contrast.json](team-contrast.json), `review/team_contrast.py`, формулы QA-010 `qa010lib.color`): кадры
  двух команд сравниваются внутри силуэта K2 1,6× и **отдельно в области фигуры** (пиксели, где видна сама фигура: кадр
  «фигура + подставка» против кадра «одна подставка») и в полосе подставки; серый — Y′ Rec.709, deuteranopia — Machado
  2009. Прогонам без кадра «одна подставка» (`before`, `after-r1`) разделение берётся из `refix-r1` — те же меши, клетки
  и камера (названо в `split_source`). Шум — те же команды в двух повторах `refix-r1` / `refix-r2`.
- **Воспроизводимость:** входы чисел в git — [team-contrast-inputs/](team-contrast-inputs/) (кропы кадров без потерь в
  одном окне на героя + маски силуэт / фигура / подставка, 3,6 МБ; полные PNG — вне git, их sha256 в `inputs.json`);
  `python tools/tripo-pipeline/review/team_contrast.py --from-inputs <этот каталог>/team-contrast-inputs --out <json>`
  даёт тот же team-contrast.json (проверено: числа совпадают с расчётом по полным кадрам).

Область **фигуры** (без подставки), K2 1,6×, пара С-11 (`#E8C06A` / `#9FC2D8`); «после» — `refix-r1` (`refix-r2` в
пределах 0,05):

| Субъект | Серый, средний \|ΔY′\| до → первый проход → refix | Доля \|ΔY′\| ≥ 8, refix | Deuteranopia ΔE76 до → первый проход → refix | Шум r1/r2 (серый / ΔE) | Предложение `#5A7F9F`: серый (доля ≥ 8) |
|---|---|---|---|---|---|
| Arthur | 2,00 → 3,62 → **3,60** | 4,1 % | 4,79 → 7,68 → **7,68** | 0,26 / 0,34 | 7,69 (49 %) |
| Harpy #2 | 0,28 → 1,29 → **1,24** | 0,1 % | 0,40 → 8,92 → **8,88** | 0,28 / 0,36 | 9,06 (38 %) |
| Medusa (до: Blue/Red T4) | 0,93 → 1,21 → **1,21** | 0,7 % | 6,27 → 8,49 → **8,48** | 0,33 / 0,39 | 9,11 (27 %) |
| Merlin | 0,24 → 0,32 → **3,32** | 0,8 % | 0,36 → 0,47 → **28,05** | 0,30 / 0,31 | 31,54 (87 %) |

Весь силуэт (фигура + подставка) и доля подставки в сумме ΔE (deuteranopia):

| Субъект | Серый \|ΔY′\| до → refix | ΔE76 до → refix | Доля подставки в сумме ΔE: первый проход → refix |
|---|---|---|---|
| Arthur | 1,60 → 3,10 | 3,73 → 8,67 | 32 % → 32 % |
| Harpy #2 | 0,59 → 1,34 | 4,03 → 10,87 | 34 % → 34 % |
| Medusa | 0,91 → 1,28 | 6,09 → 9,98 | 49 % → 49 % |
| Merlin | 0,24 → 2,80 | 0,34 → 23,67 | **89 % → 12 %** |

Вывод (измерено на редакторных кадрах, не приёмка):

- в первом проходе фигура Merlin по командам не различалась: 0,32 / 0,47 — на уровне шума 0,30 / 0,31, почти вся
  разница — полоса подставки (89 % суммы ΔE); с маской синей ткани фигура различается при deuteranopia (ΔE 28,1, в 90
  раз выше шума) и в сером заметно выше шума (3,32 против 0,30), U-3 для Merlin выполнено технически;
- у остальных фигура различается при deuteranopia (ΔE 7,7–8,9 против шума 0,34–0,39), в сером — в 3,7–14 раз выше шума,
  но в абсолютных числах мало (≤ 3,6 из 255, доля заметных пикселей ≤ 4 %): пара `#E8C06A` / `#9FC2D8` почти
  изолюминантна (яркость 0,559 против 0,509 — 0,14 EV), собственный критерий С-11 «кольца различимы в градациях серого»
  на ней не выполняется;
- при более тёмном «серебристо-голубом» `#5A7F9F` (предложение `c11_value_split_proposal`, 1,5 EV) доля заметных в
  сером пикселей фигуры — 27–87 %;
- выбор пары цветов — Q-304 (автор); в профилях и MI оставлены hex С-11.

## 7. Защищённое содержимое и состояние редактора

[snapshot-before.json](snapshot-before.json) / [snapshot-after.json](snapshot-after.json) (`ue_content_snapshot.py`,
`protected_unchanged: true`): `/Game/ART004`, `/Game/ArtPreview`, `/Game/S08`, `/Game/UM` (после сборки мастеров) не
изменились; в `/Game/PipelineCandidates` добавлено 58 своих ассетов (4 × 13, бочка 5, клип 1), в `/Game/ArtTests/P17ControlScene`
— 8 MI предложения палитры (пакеты сцены). Редактор в конце: уровень `/Game/S08/S08Arena`, 0 dirty-пакетов,
Interchange-флаги без изменений.

Refix: [snapshot-refix-before.json](snapshot-refix-before.json) (до переимпорта) / [snapshot-refix-after.json](snapshot-refix-after.json)
(после импорта и двух прогонов сцены): `protected_unchanged: true`, `/Game/ART004`, `/Game/ArtPreview`, `/Game/S08`,
`/Game/UM` без изменений; в `/Game/PipelineCandidates` новых и удалённых ассетов нет, изменились файлы своих папок
`20260929-w4b-um-master` четырёх героев (переимпорт), в `/Game/ArtTests/P17ControlScene` — пакеты сцены (пересоздаются
скриптом); уровень `/Game/S08/S08Arena`, 0 dirty.

## 8. Что не делалось и не проверялось

- packaged-кадры, K1–K3, QA-010, GD-058; DX12 + Lumen и эталон High (решения U-1/U-2 — оркестратор), SkyLight/профиль света;
- переход S08 на CPD/MID из данных бойца (код), `M_UM_GameLayer` на реальных кольцах/подсветках (мастер собран и
  проверен, ассетов на нём пока нет), Rim/FxFlash/Fade вживую;
- `/Game/ArtPreview/Medusa` (живой S08) не переподчинена: задача запрещает трогать production;
- визуальный эффект AO (см. §3), художественная оценка масок и dye;
- покрытие масок (синяя ткань Merlin, тёмные перья Harpy как «одежда»), gain красителя — предложения; художественная
  оценка — по K1-кадрам;
- ORM головы Harpy исправлен, но его влияние на кадр по-прежнему не видно без SkyLight/Lumen (см. §3).

## 9. Процессы

Свои фоновые процессы (прогоны CLI, импорты, сцена) завершились; headless Blender закрывался после каждой стадии.
UnrealEditor PID 46136 (пользовательский, MCP :8123) и Blender :9876/:9877 — не мои, оставлены как были. Refix: так же —
свои headless Blender (пробы и запекание), прогоны CLI, импорты, две сцены и тесты завершились; прочие процессы
blender.exe в это время принадлежали параллельной сессии H2 (`tools/tripo-pipeline/blender/h2_bake*`) и не трогались.
