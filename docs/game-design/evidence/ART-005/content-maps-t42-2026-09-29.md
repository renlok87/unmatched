# ART-005 · этап 3 T4.2 «Контент карт в UE» + калибровка неба Forest / Paddock (followup W4-A) — акт, 2026-09-29

**Статус:** контент — технически импортировано; калибровка неба — измерено (редактор + packaged). Художественной приёмки нет: палитра зон, форма глифов и свет остаются «предложено». Производительность в прогонах этой задачи **загрязнена фоном H2** (headless Blender/Cycles параллельной линии героев) — **не для ACC-022**. Коммитов нет — оркестратор коммитит по commit_manifest.

Рабочие копии: главный checkout (живой редактор PID 31756, DX12/SM6 + Lumen, MCP :8123) — только создание контента и сцены калибровки; арт-worktree `codex/medusa-shading-probe` — код, данные, сборки, packaged-прогоны. Каталог доказательств: [content-maps-t42/](content-maps-t42/).

## 0. Коротко

- **Контент зон (один раз через MCP в живом редакторе главного checkout, скрипт [`tools/art/t42_zone_content.py`](../../../../tools/art/t42_zone_content.py)):** в `/Game/ArtTests/ART005/Zones` (уже в `DirectoriesToAlwaysCook`, ini не менялся)
  - 12 MI `MI_ART005_Zone_<Key>` (11 ключей зон + Fallback) — дети мастера игрового слоя W4-B `/Game/UM/Materials/M_UM_GameLayer` (Unlit, EyeAdaptationInverse, ISM usage), `LayerColor = FLinearColor::FromSRGBColor(цвет зоны)` — тот же линейный цвет, что раньше клал в runtime-MID клиент;
  - 11 мешей глифов `SM_ART005_ZoneGlyph_<Glyph>` — ровно кубики `S08GlyphPieces`, слитые в один меш с пивотом в центре слота глифа (OBJ из того же скрипта → `StaticMeshTools.import_file`, коллизия снята, Nanite выкл., слот = `M_UM_GameLayer`); границы совпадают с кубиками до 5·10⁻⁵ uu;
  - `M_ART005H_IronCorner_Review` получил `bUsedWithInstancedStaticMeshes` (находка T3.2 §6: уголки всех арт-досок в cooked-сборке рисовались материалом по умолчанию). В клиентских логах предупреждение `missing usage flag` исчезло, уголки снова железные.
- `.uasset` скопированы в арт-worktree побайтно (sha256 сверены, [t42-cook-check.json](content-maps-t42/content/t42-cook-check.json)); все 24 пакета есть в `DevelopmentAssetRegistry` после кука P2.
- **Код/данные:** профили досок rev 3 — у каждого стиля зоны `materialInstance`, новый блок `glyphMeshes`; клиент грузит MI и меши по мягким путям, рисует глиф одним инстансом на слот, при отсутствии ассета — прежний tint-MID / кубики (трассируется). Пиксели зон не изменились: средний цвет синих/красных меток Cobble W4-A → T4.2 совпал до 0,1 байта.
- **Небо Forest / Paddock rev 2 откалибровано:** в редакторных сценах через MCP (метод W4-A: K1 luma доски против цели, 3 повтора, порог 2× шум и ≥ 0,5) → **12,0 / 14,4**; packaged-проверка тем же методом с живой камерой K1 показала +1,0 / +1,5 luma (редактор работает на Epic, эталон — High) → шаг уточнения в packaged → **11,8 / 14,1** (Δ −0,003 / −0,05 при пороге 0,5). Прежние 15,2 / 18,4 (×950/700, ×1150/700 от Cobble, W4-A) давали доску на +16 / +18 luma ярче цели.
- **Живой смок парой packaged-клиентов по 30 FPS** на Sherwood 8×5 и T. Rex 7×5 (+ контроль Cobble 5×6): все гейты `run-phase2-demo` с `-RequireRenderReference`, 6/6 кадров `packaged-live strict` с эталоном RENDER, `qa010 render` 6/6 = 0.
- **Найдено по ходу (не чинилось, решение за оркестратором/пользователем):** ключевой свет packaged горизонтален (`rotation [0,-55,30]` → FRotator Pitch 0), доску сверху он не освещает — см. §3.4; поверхность `tiles` на новом свете почти белая (K1 p50 186–188 против 134 у плиты Cobble) — см. §4.3.

## 1. Контент зон в UE

Скрипт `tools/art/t42_zone_content.py` (`plan` офлайн, `build`/`verify` через MCP, `copy` в арт-worktree). Отчёт: [content/t42-zone-content-report.json](content-maps-t42/content/t42-zone-content-report.json) (preflight: мастер Unlit + ISM usage + параметр `LayerColor`; действия; сохранённые пакеты; sha256 каждого `.uasset` главного checkout; результат копирования). Исходники глифов — [content/glyph-obj/](content-maps-t42/content/glyph-obj/) (генерируются тем же скриптом, детерминированно).

| Ассет | Сколько | Проверка |
|---|---|---|
| `MI_ART005_Zone_{Blue,BlueGreen,Brown,Gray,Green,LightGray,LightGreen,Orange,Purple,Red,Yellow,Fallback}` | 12 | родитель `M_UM_GameLayer`, `LayerColor` = `hex_to_linear` (правило цвета AD-OPEN-39, `um_masters.py`), чтение обратно ≤ 1e-5 |
| `SM_ART005_ZoneGlyph_{Diamond,Bar1,Bars2,Bars3,HBars2,Square,Cross,X,Tee,Chevron,Ring}` | 11 | границы = объединение кубиков (макс. ошибка 5·10⁻⁵ uu), треугольники = 12 × кубиков, Nanite выкл. |
| `M_ART005H_IronCorner_Review` (отслеживаемый) | 1 | `bUsedWithInstancedStaticMeshes` false → true, перекомпиляция, сохранение |

Ловушки импорта, найденные и закрытые скриптом: OBJ в UE 5.8 идёт через FBX SDK и зеркалит Y (OBJ (x,y,z) → UE (x,−y,z), 1 uu на единицу — проверено асимметричным пробником и удалённым после), поэтому писатель хранит (x,−y,z) с внешней правой намоткой; без UV импорт даёт вырожденные касательные (MikkTSpace) — в OBJ добавлены UV единичного квадрата; остаётся только безвредное предупреждение «нет групп сглаживания» (нормали заданы по граням, материал unlit). MCP `import_file` не перезаписывает пакет: `--force` удаляет меш только если на него никто не ссылается.

## 2. Код и данные (арт-worktree)

| Файл | Изменение |
|---|---|
| `unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json` | rev 2 → **rev 3**: `materialInstance` у 11 стилей и fallback, блок `glyphMeshes` (11), `contentNote`; небо forest 15,2 → **11,8**, paddock 18,4 → **14,1** с полем `calibration`. Cobble, доски, палитра, точки света — без изменений. sha256 `750f4936…f330` (= `profilesSha256` в трассах живых прогонов) |
| `S08BoardArt.h/.cpp` | `FS08ZoneStyle::MaterialInstancePath`, `FS08BoardArtData::GlyphMeshPaths`, `S08GlyphAnchor(Slot)`, `FS08ZoneMarkLayout::GlyphAnchors` (один на зону клетки); парсер отвергает путь не из `/Game/` и неизвестный глиф |
| `S08BoardActor.h/.cpp` | загрузка MI/мешей (не в `-S08LegacyRender`), MI вместо MID в `ZoneMaterialFor`, ISM глифа на ключ зоны; трассы `ARTPREVIEW zone content instances=N/N glyphMeshes=M/M`, `ARTPREVIEW board glyph meshes instances=… cubePieces=…`, в строке `board zone key=…` добавлены `mi= glyphMesh= glyphInstances=` перед `fallback=` (старые гейты совместимы) |
| `S08BoardArtTests.cpp` | Parser (+4 случая T4.2), Shipped (MI у всех стилей, меш у всех глифов), новые `BoardArt.GlyphAnchors` и `BoardArt.ZoneContent` (MI: родитель, `LayerColor == FLinearColor(FColor)`, ISM usage; меши: границы = кубики) |
| `tools/art/art_board_fixtures.py` (+ тест) | `check_content_blocks` |
| `tools/s08/run-phase2-demo.ps1` | гейты T4.2 (MI + число инстансов глифа по каждой зоне = клеткам зоны; `zone content` загружен полностью); порог освещённости кадра масштабируется долей проходимых клеток (§4.2) |
| `tools/art/check_art_preview_shot.py` | `--min-board-lit` (по умолчанию 0,75 — прежнее значение) |

Устаревшие review-материалы `M_ART005_{Blue,Red}Section_Review`, `M_ART005_ZoneGlyph_Review` без ISM usage не трогались: они живут только в эмуляции `-S08LegacyRender` (пре-W4 бенч).

## 3. Калибровка неба Forest / Paddock

### 3.1 Метод (как у Cobble в W4-A)

Цель W4-A для Cobble — кадр P17 (DX11-редактор, стенд P17: fill 700 cd в (0,100,500), ключ pitch −55, EV100 1,3), K1 luma доски 131,2; сравнивалась p50 Rec.709 luma в прямоугольнике x 600–1360, y 700–940. Для Forest / Paddock DX11-кадров на стенде P17 нет, поэтому цель строится тем же стендом с их пробами ART-005I:

- **сцена** — скретч-копии ревью-уровней ART-005 (`/Game/ArtTests/T42Calib` в главном checkout, gitignored: сохраняется только эта папка, в git не попадает; после прогона убрана — §6 п. 4): Cobble ← `ART005H/L_ART005H_CornerReview`, Forest/Paddock ← `ART005I/L_ART005I_*ReferenceLight` (та же плита 5×6, фигуры, метки и уголки; отличается только свет);
- **цель («legacy»)** — пробный свет уровня как есть (ключ pitch −55 yaw 30, fill в канделах, тёплые/вторичные точки, цвета в байтах пробы), fill перенесён на стенд P17 (0,100,500), GI и отражения выключены (override `None` = DX11-редактор), экспозиция EV100 1,3;
- **кандидат («rev2»)** — ревью-свет удалён, риг профиля rev 2 поставлен ровно как это делает packaged-клиент (`ApplyArtLights`/`S08PlaceLights` на доске 5×6: ключ `FRotator(rotation[0..2])` в люксах с CSM профиля, точки в канделах, цвета через `ToFColor(sRGB)` как `SetLightColor`, Movable SkyLight `TC_S08_AmbientDome` с перебираемой интенсивностью), Lumen включён;
- **кадр** — `EditorAppToolset.CaptureViewport` с направления камеры доски (pitch −55, yaw −90). У вьюпорта MCP горизонтальный FOV фиксирован 90° (пилотная камера требует editor Python, которым я не пользовался — ввод в консоль редактора через Slate требует фокуса окна, а пользователь работает на соседнем столе), поэтому дистанция пересчитана на то же горизонтальное кадрирование в фокусе (1931 × tan 17,5° / tan 45° = 609 uu); спрайты света спрятаны; центральный кроп 16:9 → 1920×1080; повтор = увод камеры и сходимость, пока p50 трёх последних захватов не уложится в 0,2.

Два пробных прогона только на Cobble (1–2 повтора; до замены правила сходимости «пиксельная разница < 0,05» — под Lumen/TSR она не достигается — и до переноса fill на стенд P17) заменены итоговым и лежат вне git (`C:/tmp/t42/calib-test*`). Скрипт: [`tools/art/t42_sky_calib_editor.py`](../../../../tools/art/t42_sky_calib_editor.py); отчёт [calibration/t42-sky-calib-editor.json](content-maps-t42/calibration/t42-sky-calib-editor.json) (все кадры с sha256, состояние сходимости, считанные обратно свойства ригов); листы: [calibration/editor-target-vs-rev2.jpg](content-maps-t42/calibration/editor-target-vs-rev2.jpg). Кадры класса `editor-mcp-viewport` — диагностика, не K1.

### 3.2 Редактор (DX12 + Lumen, вьюпорт на Epic)

| Профиль | цель (3 повтора, шум) | кривая небо → K1 p50 | итог (3 повтора) | Δ / порог |
|---|---|---|---|---|
| cobble (контроль) | 132,65 (0,00) | 8 → 107,1; 11,2 → 131,7; 11,4 → 133,1; 12 → 137,1; 16 → 158,3 | 11,4 → 132,97 (0,07); отгружено 11,2 → 131,73 | +0,32 / 0,5 |
| forest | 140,50 (0,00) | 8 → 114,7; 11,9 → 140,1; 12 → 140,6; 15,2 → 156,4; 16 → 159,9 | **12,0** → 140,58 (0,00) | +0,08 / 0,5 |
| paddock | 144,01 (0,04) | 8 → 102,9; 12 → 130,9; 14,4 → 144,1; 16 → 151,7; 18,4 → 161,6 | **14,4** → 144,11 (0,06) | +0,10 / 0,5 |

Контроль: тем же методом Cobble получает 11,3–11,4 против отгруженного W4-A 11,2 — редакторная сцена воспроизводит калибровку W4-A с точностью ~0,1–0,2 единицы неба. Чувствительность к стенду: с fill на месте уровня (0,−100,550) цели ниже (104,1 / 110,3 / 112,8), поэтому стенд P17 выбран ради общей базы с Cobble. DX11-кадры ART-005/ART-005I (134,15 / 136,01 / 139,19) сняты другой камерой и экспозицией — сопоставимы только их отношения (порядок cobble < forest < paddock совпадает).

### 3.3 Packaged-подтверждение (бенч, живая камера K1, High)

Скрипт [`tools/art/t42_bench_confirm.py`](../../../../tools/art/t42_bench_confirm.py): W4-A `-Bench` (фикстура Cobble 5×6, FOV 35 на 1931 uu, 1920×1080, SP 100, `-S08RenderPreset=High`) с диагностическими override-профилями (fingerprint `profilesSource=override`, `reference=0` — не эталонные кадры). `legacy-<p>` — та же проба, эмулированная в packaged (свет уровня из отчёта редактора, fill на стенде P17, без неба, GI/отражения выкл. через `-ExecCmds`); `rev2-<p>@<s>` — риг профиля с небом `s`, Lumen. 3 повтора, чередование вариантов. Сводка: [bench/bench-confirm-summary.json](content-maps-t42/bench/bench-confirm-summary.json), лист [bench/bench-target-vs-rev2.jpg](content-maps-t42/bench/bench-target-vs-rev2.jpg).

| Вариант | K1 p50 (3 повтора) | шум | против цели | вердикт (порог max(2×шум, 0,5)) |
|---|---|---|---|---|
| legacy-cobble (эмуляция P17) | 132,08 | 0,00 | реальный P17 131,2 → эмуляция +0,9 | — |
| rev2-cobble@11,2 (отгружено W4-A) | 134,39 | 0,06 | +2,31 | вне порога (решение W4-A, не менялось) |
| legacy-forest | 138,51 | 0,02 | — | — |
| rev2-forest@12,0 (из редактора) | 139,52 | 0,00 | +1,01 | вне порога |
| rev2-forest@11,9 | 138,80 | 0,01 | +0,29 | в пороге |
| **rev2-forest@11,8** | **138,51** | 0,01 | **−0,003** | **совпало** |
| legacy-paddock | 141,76 | 0,01 | — | — |
| rev2-paddock@14,4 (из редактора) | 143,23 | 0,03 | +1,47 | вне порога |
| rev2-paddock@14,2 | 142,29 | 0,07 | +0,52 | вне порога |
| **rev2-paddock@14,1** | **141,71** | 0,07 | **−0,05** | **совпало** |

Вывод: редакторная калибровка подтверждена по порядку величины, но систематически на +1,0…+1,5 luma ярче packaged-цели (вьюпорт редактора работает на Epic, эталон — High; менять пользовательскую масштабируемость редактора я не стал). В профиль записаны packaged-значения **11,8 / 14,1** (поле `calibration` хранит обе ступени). Cobble 11,2 оставлен как решение W4-A; его остаток +2,3 к эмулированной цели (точное совпадение ≈ 10,9) — на решение оркестратора.

### 3.4 Диагностика: горизонтальный ключевой свет

`rotation: [0, -55, 30]` профилей разбирается как `FRotator(Pitch 0, Yaw −55, Roll 30)` — ключ горизонтален и верх доски не освещает; в пробах ART-005/ART-005I и P17 ключ был Pitch −55, Yaw 30 (похоже на перестановку порядка осей редактора X/Y/Z = Roll/Pitch/Yaw; то же было в коде до T3.2: `FRotator(0, -55, 30)`). Небо rev 2 откалибровано с этим горизонтальным ключом, как и Cobble в W4-A. Замер в редакторе при итоговом небе, ключ Pitch −55: доска K1 +9,3 (cobble), +5,9 (forest), +4,3 (paddock) luma. Исправление меняет вид всех трёх досок и калибровку/кадры W4-A — не делал, в followups.

## 4. Живой смок парой packaged-клиентов

`tools/art/art004_live_k2.py run` → `run-phase2-demo.ps1 -ArtPreviewBoardId <фикстура> -ClientFps 30 -ClientPerf -ArtPreviewMedusaVariant face-neck-v2 -RequireRenderReference`, 50 с, снимок на 36 с; бэкенд арт-worktree :3120 на `codex-s09-*`; сборка G1 (exe `bc303863…`, `WITH_LIVE_CODING 1`), упаковка P2 (staged inner exe = Binaries exe). Все комнаты ABORTED (verified).

### 4.1 Трассы

| Доска | прогон | ключевые строки (хост и джойнер) |
|---|---|---|
| Sherwood 8×5 | [run-20260929-132312](content-maps-t42/live/sherwood-forest-8x5/run-20260929-132312/) | `BOARD 8x5`, `expectOk=1`, `zone content instances=12/12 glyphMeshes=11/11`, `board glyph meshes instances=47 keys=7/7 cubePieces=0`, у 7 зон `mi=MI_ART005_Zone_* glyphMesh=SM_ART005_ZoneGlyph_*` с числом инстансов = клеткам, `sky profile=forest-probe … intensity=11.8`, `multizone zonesListed=31 zonesMarked=31`, SHOT `reference=1` |
| T. Rex 7×5 | [run-20260929-132431](content-maps-t42/live/t-rex-paddock-7x5/run-20260929-132431/) | `BOARD 7x5`, `expectOk=1`, `zone content 12/12, 11/11`, `glyph meshes instances=39 keys=6/6 cubePieces=0`, `sky … paddock-probe intensity=14.1`, `zonesListed=26 zonesMarked=26`, SHOT `reference=1` |
| Cobble 5×6 (контроль) | [run-20260929-132548](content-maps-t42/live/cobble-5x6/run-20260929-132548/) | строки ART-005 побайтно (`Cobble active … blueMarks=15 redMarks=45`, `Cobble probe lights key=4.5 fill=0 warm=85`), `glyph meshes instances=30 cubePieces=0`, `mi=MI_ART005_Zone_Blue/Red`, sky 11.2, SHOT `reference=1` |

Классификация: [classify-live-strict-render-reference.json](content-maps-t42/classify-live-strict-render-reference.json) — 6/6 `packaged-live strict` (S1–S5, в т.ч. эталон RENDER); негатив — редакторный кадр калибровки отвергнут (код 3). `qa010 render` — 6/6 код 0 ([qa010-render/](content-maps-t42/qa010-render/)). В клиентских логах нет `missing usage flag`. Секции света ≠ игровые зоны: позиции точек не менялись, `art_board_fixtures.py check` — Jaccard ≤ 0,29 при пороге 0,5.

### 4.2 Гейт кадра и заменённая попытка

Первая попытка Sherwood упала на пиксельном гейте `check_art_preview_shot.py`: требование «75 % освещённых пикселей в прямоугольнике доски» — константа Cobble, а у Sherwood 10 из 40 клеток — намеренно тёмные пустоты, которые под рендером W4-A стали чёрными (71 % при целиком освещённой доске; трассы все зелёные). Запись: [superseded-attempt-20260929-132209.json](content-maps-t42/live/sherwood-forest-8x5/superseded-attempt-20260929-132209.json), сырой каталог вне git. Исправление: порог = 0,75 × доля проходимых клеток зарегистрированной доски (Sherwood 0,5625, T. Rex 0,5571; Cobble без препятствий — прежние 0,75), повтор прошёл.

### 4.3 Яркость (K1 p50, прямоугольник W4-A) — [live/live-k1-luma.json](content-maps-t42/live/live-k1-luma.json), лист [live/live-k1-t32-vs-t42.jpg](content-maps-t42/live/live-k1-t32-vs-t42.jpg)

| Доска | T3.2 (DX11, Unitless — G01) хост / джойнер | T4.2 (DX12 + Lumen High, rev 3) хост / джойнер |
|---|---|---|
| Sherwood 8×5 | 108,0 / 107,8 | 187,3 / 187,7 |
| T. Rex 7×5 | 87,6 / 87,0 | 185,7 / 186,8 |
| Cobble 5×6 | 82,0 / 82,0 | 134,3 / 134,4 |

Свет трёх профилей уравнен на одной поверхности (плита Cobble), а фикстуры рисуются поверхностью `tiles` с материалом `M_ART005_Stone_Probe` — он заметно светлее плиты Cobble (то же отношение было и в T3.2: 1,32 → 1,40). Клиппинга нет (p90 ≈ 203, пикселей ≥ 250 — 0), но светлые метки (yellow, light-gray, light-green) на почти белых плитках теряют контраст. Это вопрос материала поверхности `tiles`, а не калибровки света — вынесено в followups (T5.2).

## 5. Сборки и тесты

- `UnmatchedEditor` арт-worktree E1/E2 (`-WaitMutex -NoHotReloadFromIDE -NoXGE -NoUBA -MaxParallelActions=2`; свободного commit было 9–20 ГБ из-за H2): Succeeded ([build/E2-editor-build.txt](content-maps-t42/build/E2-editor-build.txt)). Первая E1 упала на C4456 (затенённая переменная) — исправлено.
- Игровой target `Unmatched` **без `-NoLiveCoding`**: G1 Succeeded, `WITH_LIVE_CODING 1`, exe `bc3038636e7f2497…` ([build/G1-build.json](content-maps-t42/build/G1-build.json)); первая попытка упала на `UStaticMesh::IsNaniteEnabled` (editor-only API в тесте) — обёрнуто в `WITH_EDITOR`, запись о неудаче вне git.
- `package-client.ps1 -SkipBuild`: P1 (профиль с небом 12,0/14,4 — под ним шёл бенч с override-профилями) и P2 (итог 11,8/14,1 — под ним живые пары); BUILD SUCCESSFUL, staged inner exe = Binaries exe.
- Автотесты UE (UnrealEditor-Cmd арт-worktree, `-nullrhi`, DLL E2, **итоговый** профиль `750f4936…`): `Unmatched.S08` **70/70** (в т.ч. `BoardArt` 8/8, из них 2 новых), `Unmatched.S09` **44/44**, `Unmatched.S10` **50/50** — [tests/](content-maps-t42/tests/).
- Python: `tools/art/tests` 72/72, `tools/art/qa010/tests` 116/116, `classify_evidence --self-test` PASS, `art_board_fixtures.py check` PASS, `pyflakes` чисто на новых/изменённых модулях; PS-парсер `run-phase2-demo.ps1` — 0 ошибок.
- `validate_registry.py` (главный checkout): PASS. `snapshot_baseline.py check` (главный checkout): 62 файла, 0 различий.
- Секрет-скан каталога доказательств (пароли/секреты из `backend/.env`, JWT, postgres-URL): 162 файла, 0 совпадений.
- Сырые кадры калибровки (PNG + sidecar) и бенча (PNG, `client.log`) вне git в `C:/tmp/t42`, там же резервная копия последнего скретч-уровня калибровки (§6 п. 4); sha256 — [raw-outside-git.json](content-maps-t42/raw-outside-git.json).

## 6. Открыто и followups

1. **Ключевой свет горизонтален** (§3.4): `rotation` профилей = FRotator(Pitch, Yaw, Roll) = (0, −55, 30), в пробах было Pitch −55 Yaw 30. Исправление (`[-55, 30, 0]`) даст +4…9 luma на доске и новые тени; потребует перекалибровки неба всех трёх профилей и пересъёмки эталонных кадров W4-A. Решение — оркестратор/пользователь.
2. **Поверхность `tiles` слишком светлая** (§4.3): K1 186–188 против 134 у плиты Cobble при одинаковом свете; вариант — плиточный материал/MI с альбедо плиты ART005E или тинт ≈ 0,7, проверить контраст меток в сером/deuteranopia (T5.2, QA-010 C-9).
3. **Cobble 11,2** на +2,3 luma выше эмулированной цели P17 (точное ≈ 10,9); оставлено как решение W4-A.
4. **Главный редактор (PID 31756)** работает на DLL 11:39 (до T4.2): после интеграции `AS08BoardActor` получает новые UPROPERTY — пересборка/перезапуск нужны до любого PIE с `-ArtPreview` в главном checkout. Скретч-уровень `/Game/ArtTests/T42Calib/L_T42_Paddock_f1` (gitignored) редактор удерживает в памяти: MCP `asset delete` (и папки, и самого ассета) возвращает true, но файл остаётся. Дескриптор файла редактор не держит, поэтому файл перенесён из главного checkout в `C:/tmp/t42/main-scratch-map-backup-20260929/` (sha256 `3dd7b4c9…627b` сверен до и после, запись в raw-outside-git.json), пустая папка `T42Calib` удалена. Реестр ассетов редактора после этого ассет не видит (`asset exists` = false), редактор отвечает и стоит на `/Game/S08/S08Arena`. Пакет живёт только в памяти до перезапуска; после перезапуска делать ничего не нужно.
5. **Вьюпорт редактора на Epic**: редакторные кадры калибровки на +1…1,5 luma ярче High-эталона; для будущих редакторных калибровок либо пилотная камера + `sg.*=2` через editor Python (в окне пользователя), либо сразу packaged-бенч.
6. Остальной игровой слой (подсветки, кольца, недопустимая клетка, подписи) по-прежнему на временном `M_S08_GameLayerUnlit` (followup W4-A); MI зон уже на `M_UM_GameLayer`.
7. `DIRECTORY-MAP.md`: добавить `/Game/ArtTests/ART005/Zones/*` (git add -f, строит `tools/art/t42_zone_content.py`), `tools/art/t42_*.py`, каталог `docs/game-design/evidence/ART-005/content-maps-t42/` — доля оркестратора.
8. Производительность прогонов (FPS ≈ 29,3–30, GPU пары) записана в `perf.json`, но **загрязнена фоном H2** (headless Blender/Cycles параллельной линии героев) — не для ACC-022.

## 7. Процессы

Запускал сам и остановил по PID после сверки командной строки: бэкенд `node -r dotenv/config dist/src/main.js` (PID 3640, :3120), контейнеры `codex-s09-postgres`/`codex-s09-redis` (были Exited — остановлены), Docker Desktop (PID 33396 и его дерево — `docker desktop stop`; каталог `run` после остановки перенесён в `%LOCALAPPDATA%/Docker/run.stale-20260929-t42`, ничего не удалено). UnrealEditor-Cmd (сборки, кук, тесты) и клиенты `Unmatched.exe` завершились сами; lock-файлы `C:/tmp/unmatched-package.lock` и `C:/tmp/unmatched-gpu.lock` сняты. Главный редактор 31756 (MCP :8123) оставлен работать (общая служба волны), текущий уровень возвращён на `/Game/S08/S08Arena`, несохранённых изменений нет; скретч-карта калибровки вынесена из главного checkout в `C:/tmp/t42` (§6 п. 4), уровень при этом не перезагружался. Blender :9876/:9877, H2-процессы, dev-сервер :5480 и процессы vmmem/WSL не трогались. Мышь/клавиатура/computer-use и ввод в консоль редактора не использовались; клиенты — `-RenderOffScreen`.
