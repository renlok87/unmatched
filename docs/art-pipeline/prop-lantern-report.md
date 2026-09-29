# Фонарь · ASSET-DECOR-KIT-001.LANTERN — Tripo и Blender-кандидат

**Статус: измерено.** Художественной приёмки нет. UE не запускался, этот шаг отложен.

## Итог

- **Tripo.** Этап выполнил оркестратор 2026-09-29 с 05:32 до 05:44: задание `26bb832e`, 130 кредитов Studio, баланс 24 335 → 24 205.
- **Blender.** Собран `SM_Decor_Lantern.fbx` (UM_FBX_v1): высота 95 uu, 4 484 треугольника, 2 слота, текстуры BC/N/ORM 1K. Сетка замкнута. Все 12 проверок кандидата пройдены, readback независимо подтверждает результат.
- **Фурнитура.** Петли стоят слева по кадру, защёлка справа, как на front. На боках и сзади фурнитуры нет. Это видно на превью и подтверждено замером по FBX.
- **Стекло.** Решение: второй слот `M_Decor_LanternGlow`, как `M_Decor_FacadeGlow` у фасадов.
- **Инструменты.** `static_prop_candidate.py` получил `front_check`, `glow_slot`, ремонт `tripo_cracks` и учёт `baseColorFactor`. Пересборка бочки побайтно та же.

## 1. Этап Tripo

Этап выполнил оркестратор лично в Chrome. Исполнитель записал его по трём источникам: тексту задания, журналу кредитов и замерам GLB. Числа из UI (2 538 граней, заполнение UV 77 %) исполнитель сам не видел. Они помечены в [tripo-run.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/reports/tripo-run.json) как `reported_by_orchestrator`.

| Время (история Studio) | Операция | Цена = списание | Баланс |
|---|---|---:|---|
| 05:32 | H3.1, несколько видов (front + back v3, боковые слоты пустые), «Приватный» | 55 | 24 335 → 24 280 |
| 05:37 | Ретопология Quad, Smart Mesh, цель 2 500 (получено 2 538 граней) | 40 | 24 280 → 24 240 |
| 05:39 | Smart UV (заполнение 77 %; по GLB 0,7705) | 20 | 24 240 → 24 220 |
| 05:41 | Текстура 2K, front/back, удалить освещение | 10 | 24 220 → 24 210 |
| 05:44 | PBR | 5 | 24 210 → 24 205 |
| | **Итого** | **130** (план 130, потолок 250) | |

Файлы (целостность GLB проверена: длина в заголовке равна размеру файла, обход чанков доходит до конца):

- `source/decor-lantern-tripo-h31-26bb832e-source.glb`: 68 146 168 байт, sha256 `ab8a9a07…c8cac2`, 1 992 294 треугольника, текстуры 4096². **Хранится локально и не коммитится**, как сырые исходники героев. Он добавлен в `.gitignore` декор-кита, в git остаётся только sha256 в source-spec.
- `source/decor-lantern-tripo-26bb832e-smartuv-tex2k-pbr.glb`: 13 180 092 байта, sha256 `085d062e…467bb`, 4 486 треугольников, 1 материал, BC/RM/N 2048². Это основной вход Blender-этапа.

Промежуточные GLB (после ретопологии и после текстуры без PBR) не выгружались.

**Осмотр результата Tripo** (Blender 5.2.2 headless, орто-виды четырёх сторон и крупный план головы фонаря):

- петли на той стороне, что на front;
- фурнитура на боках не продублирована;
- стёкла на всех сторонах целы;
- шпиль цел.

Перегенерация не нужна. У сетки есть дефекты ретопологии, они описаны в §2.1.

**Source spec и CLI.** Spec: [source-specs/tripo-26bb832e.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-26bb832e.json), роли `source-glb` и `smartuv-tex2k-pbr-glb`. Регистрация через `tools/tripo-pipeline/tripo_pipeline.py`:

- `init` + `register-source` в `$R/ue-passthrough`: exit 0, «registered tripo-26bb832e (2 files, historical spend 130; this command spent 0)». Регистрировал `tripo-pipeline 0.5.0` (так записано в manifest). Сейчас в рабочем дереве `tripo_pipeline.py` 0.6.0: его правит параллельная сессия, к фонарю эти правки не относятся;
- повторный `register-source`: no-op;
- preflight, import, verify и export: в состоянии `pending`, прогон отложен (§4).

Два следствия регистрации:

- **`tripo-run.json` больше не правится.** Его sha256 `bd8d9560…0aea` закреплён как evidence в `ue-passthrough/manifest.json`. `register-source` сравнивает запись целиком. После правки файла повтор откажет с `EXIT_CONFLICT`, и понадобится новый `source_id` или новый run-каталог. Поэтому поле `credits.ledger_summary_note` в `tripo-run.json` описывает журнал кредитов до пересчёта (§4 п. 4).
- **Чистый checkout.** Manifest регистрирует и сырой GLB, а он git-ignored. Без этого файла preflight прогона `ue-passthrough` падает на `source_files_present`. Восстановить файл можно по sha256 `ab8a9a07…c8cac2` из source-spec. Сборка кандидата читает только PBR GLB.

## 2. Blender-кандидат

Запуск: Blender 5.2.2 LTS, headless, `--factory-startup`. Живые Blender на портах :9876 и :9877 не использовались. Параметры: [candidate-params.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/reports/candidate-params.json), отчёт: [candidate-report.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/reports/candidate-report.json). Две пересборки дали побайтно одинаковые FBX и PNG.

| Замер | Значение |
|---|---|
| Высота / габарит в UE, uu | 95,0 / 26,59 × 26,21 (X — глубина с фурнитурой) — 95 внутри 04 (90–110) и гейта S05 (90–100), предложено |
| Pivot | центр основания, min Z = 0 (строка UM_FBX_v1 — да) |
| Треугольники | 4 484 (M_Decor_Lantern 4 338 + M_Decor_LanternGlow 146); кит 30–60k — предложено |
| Слоты | 2 (≤ 2 по 04) |
| Замкнутость после сварки 1 мкм (Blender и readback FBX) | 0 открытых / 0 немногообразных / 0 несогласованных |
| Текстуры | 1024², BC sRGB, N Linear DirectX, ORM Linear (R = AO Cycles 64 сэмпла, 0,04 м) |
| FBX | `SM_Decor_Lantern.fbx` 169 788 байт, sha256 `d72e5edf…70880`; round-trip: 1 меш, 4 484 tris, 2 слота, UVMap, без арматуры |
| Коллизия | нет (декор, 04) |

### 2.1 Первый прогон и ремонт сетки

Первый прогон с `geometry_repair: null` упал на `require_closed_manifold`, как и предупреждал план. После сварки на 1e-6 м в сетке Tripo было:

- 13 открытых рёбер;
- 1 немногообразное ребро;
- 1 вырожденный треугольник;
- 5 граней с несогласованной ориентацией.

После очистки открытых рёбер стало 16, потому что `clean_mesh` удаляет вырожденный треугольник. Разбор этих рёбер по одному:

- **Три T-стыка**: щели нулевой площади. Одна у низа дверцы со стороны петель (z = 0,603 до масштаба), две у верха боковых стёкол (z = 0,762). Длинное ребро с одной стороны щели, два коллинеарных с другой.
- **Коллинеарный треугольник** на углу столба (z = 0,563). Он замкнут. После удаления на его месте остаётся такой же T-стык.
- **«Плавник» из 5 граней** площадью ≈ 9,8 см² до масштаба. Это тонкая вывернутая пластина вдоль рамы дверцы со стороны петель. Она крепится немногообразным ребром, и именно её грани давали 5 несогласованных.

Решение — новый метод `geometry_repair: {"method": "tripo_cracks"}`:

1. сварка на 1e-6 м;
2. удаление групп вывернутых граней у открытых или немногообразных рёбер: не больше 8 граней и 20 см² на группу, иначе прогон падает;
3. вставка T-вершины в длинное ребро со сваркой и перетриангуляцией BEAUTY.

Ничего не заливается вслепую: если после этого остаётся открытое ребро, прогон падает.

Результат: удалён 1 плавник (5 граней), сварено 4 T-стыка, треугольников 4 486 → 4 484. Открытых, немногообразных и вырожденных рёбер и граней: 0. Нормали углов Tripo сохранены: отклонение после перезаписи не больше 0,41°.

### 2.2 Стекло: решение

**Второй слот `M_Decor_LanternGlow`.** Маску в альфе BC отклонили по трём причинам:

- у фасадов уже есть образец с тем же приёмом: второй слот `M_Decor_FacadeGlow` на тех же BC/N/ORM;
- BC остаётся RGB без альфы, и конвейер adopt/UE не меняется;
- по 08 §6.2 эмиссию нужно выключать на минимальных настройках, а отдельный MI со слотом это позволяет.

Грани выбираются замером, а не вручную. Условие: B − R ≥ 15 на 8-битных значениях исходного BC хотя бы в половине из 28 барицентрических точек грани. Сине-серое стекло даёт 19–21, железо 5–9, бронза < 0.

| Что выбрано | Значение |
|---|---|
| Грани | 146, из них 99 чисто стеклянных и 47 смешанных при пороге 0,5 |
| Отвергнуто | 54 смешанные грани |
| Площадь | 13,4 % меша |
| По ориентации | 4 стекла (±X, ±Y), подоконники (+Z) и перемычки (−Z) проёма, всё в голове фонаря |

BC стекла не перекрашивался и остаётся сине-серым, как у Tripo. Тёплый цвет даёт эмиссия. В Blender это превью-значение: #FFC27A из диапазона 03 С-6, сила 3. Значение для UE задаётся параметром MI и пока отложено. Граница свечения идёт по граням. На игровой камере отклонение от нарисованной кромки стекла не больше одной грани, это ~1 px.

### 2.3 Фронт и фурнитура

Старая строка «Front (bung) along −Y» у фонаря неприменима: на 0,5 высоты больше всего выступают углы столба. Readback по старой мере даёт −45°, то есть угол.

Новый `front_check: axis_extent` смотрит полосу 0,62–0,76 высоты. Там вершины есть только у фурнитуры дверцы:

| Ось (.blend) | Экстент, м |
|---|---:|
| −Y | 0,1181 |
| +X (второй по величине) | 0,0902 |
| **Запас** | **0,0279** (порог 0,01) |

Итог: фронт = −Y, строка соответствует. Readback по FBX даёт то же в кадре экспорта: +X 11,805 uu, запас 2,789 uu.

[lantern_hardware_readback.py](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/lantern_hardware_readback.py) проверяет FBX в кадре экспорта: фронт +X, слева по кадру −Y. Отчёт: [lantern-hardware-readback.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/reports/lantern-hardware-readback.json).

- **Сектора.** Все 195 вершин полосы лежат в переднем секторе. В боковых и заднем секторах их 0, позади половины переднего выступа тоже 0. Значит, **фурнитура на боках и сзади не продублирована**.
- **Кластеры по высоте** (разрыв больше 3 % высоты):

  | Сторона | Высота (доля) | Боковое смещение Y, uu | Что это |
  |---|---|---:|---|
  | −Y (слева по кадру) | 0,620–0,660 | ≈ −6,0 | нижняя петля |
  | +Y (справа по кадру) | 0,679–0,712 | ≈ +6,6 | защёлка |
  | −Y (слева по кадру) | 0,718–0,759 | ≈ −7,5 | верхняя петля |

  Схема совпадает с `tripo-stage-plan.json`: `hinge_latch_pattern_matches_plan: true`. В UE ось Y отражается (x, −y, z), поэтому петли окажутся на UE +Y. Если смотреть на фронт, это по-прежнему левый край кадра.

### 2.4 UV, нормали, текстуры

**UV0** — Smart UV от Tripo, в Blender не менялся:

- 61 остров (у Tripo 62, минус плавник);
- вне 0–1 ничего нет;
- перекрытий между островами 0;
- покрытие 0,769;
- плотность 1 085 px/м, это 10,8 px/uu;
- анизотропия p95 1,57;
- минимальный зазор ≈ 3 px при 1K и 6 px при 2K; при растре 1K зазор меньше 1 текселя с mip 2.

5 треугольников UV перевёрнуты против своего острова, внутри островов 18 px перекрытия. Всё это уже есть в исходном GLB Tripo, ремонт этого не вносил.

**Нормали.** Сохранены пользовательские нормали Tripo. 119 углов смотрят внутрь поверхности, в исходнике было 125. N записан в DirectX: G перевёрнут относительно glTF. Кромки, которые Tripo оставил чёрными, расширены на 32 px.

**BC.** `baseColorFactor` 0,8 из GLB умножен в BC в линейном свете. Стадия atlas CLI делает так же для героев. Средний BC: 0,242 / 0,230 / 0,224.

**ORM.** R — AO: медиана 0,953, 756 текселей < 0,05. G — roughness: среднее 0,546, значение ≥ 0,6 только на 37,8 % покрытых текселей. B — metallic: среднее 0,10, доля > 0,5 — 3,5 %. Предложение 03 С-3 — roughness ≥ 0,6 на ≥ 90 % площади, металл только акцентом. Фонарь — разрешённый металлический акцент, но roughness у Tripo ниже предложения. Нужен взгляд арта: не сдвинуть ли roughness в MI (§4).

### 2.5 Превью

Все превью просмотрены через Read.

- **Игровая камера** (перспектива, горизонтальный FOV 35, pitch −55; [game_camera_preview.py](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/game_camera_preview.py)):
  - [yaw 0](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/preview/SM_Decor_Lantern_game-fov35-pitch55-yaw0.jpg);
  - [yaw 45](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/preview/SM_Decor_Lantern_game-fov35-pitch55-yaw45.jpg).

  Сверху читаются крыша и светящиеся стёкла. При yaw 45 петли видны у левого ребра фронта, защёлка у общего угла. На правом боковом стекле фурнитуры нет.
- **Орто:**
  - [фронт +X](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/preview/SM_Decor_Lantern_ortho-front-plusX.jpg): дверца к камере, петли слева, защёлка справа;
  - [бок +Y](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/preview/SM_Decor_Lantern_ortho-side-plusY.jpg): чистое стекло, фурнитура видна только в профиле у переднего ребра.
- **Рендеры `static_prop_candidate.py`** (орто, 900 px): `SM_Decor_Lantern_{front,side,top,game-3q-55deg}.png` и развёртка `SM_Decor_Lantern_uv0_layout.png`.

Свет превью не игровой, эмиссия — превью-значение.

## 3. Изменения инструментов

- **[static_prop_candidate.py](../../tools/tripo-pipeline/blender/static_prop_candidate.py)**, sha256 LF `b1e67b69…28af6` (было `6f703427…`). Новые необязательные параметры:
  - `front_check`: `protrusion` по умолчанию, это прежняя мера бочки; `axis_extent` — новая;
  - `glow_slot`;
  - `geometry_repair.method = tripo_cracks`.

  Кроме того, `baseColorFactor` ≠ 1 теперь умножается в BC. Без этих параметров поведение прежнее.

  **Пересборка бочки** на её params (вывод в `C:/tmp`):
  - FBX `80153e4c…`, BC `393b0b50…`, N `33f91b4d…`, ORM `9a66a558…` побайтно равны закоммиченным;
  - `candidate-report.json` отличается только полями `script_sha256_lf` и `out_dir`;
  - превью совпадают по пикселям с точностью ±1, так же как при прогоне старого скрипта: байты PNG от прогона к прогону не стабильны и раньше.

  Функции, которые берут crate/facades/mannequin/table-base (`build_material`, `export_fbx`, `uv_analysis` и другие), не менялись: изменены только `main()` и docstring, остальное — новые функции. Загрузка через `exec` без `main()` проверена.
- **[check_static_prop_fbx.py](../../tools/tripo-pipeline/blender/check_static_prop_fbx.py).** Третьим аргументом теперь можно передать params JSON: тогда применяется его `front_check`, а `axis_extent` пересчитывается в кадр экспорта. С числом или без аргумента вывод прежний: readback бочки равен закоммиченному.
- **[game_camera_preview.py](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/game_camera_preview.py):**
  - слот `*Glow*` получает превью-эмиссию;
  - пути сделаны абсолютными. Первый запуск с относительным `out` записал 4 JPG в `C:\art\…`. Этот каталог создал сам запуск, файлы и каталог удалены.
- **Новый скрипт [lantern_hardware_readback.py](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/lantern_hardware_readback.py).**
- **Юнит-тесты** `tools/tripo-pipeline/tests`, 2026-09-29, прогон по модулям (`unittest discover -p <модуль>`):
  - 164 теста за ≈ 555 с. Один прогон `discover` целиком близок к лимиту 600 с, поэтому запуск разбит на модули;
  - 163 OK, 1 падение: `RealHarpyCandidateTests.test_ue_import_accepts_the_run` («fake editor: unknown script ue_import_fbx.launch.py»). Во время прогона параллельная сессия меняла `tripo_pipeline.py` (sha256 `457884de…` → `b8eea7cf…`, 06:50) и `tests/fake_unreal_mcp.py` (06:48). После этого повтор класса `RealHarpyCandidateTests` прошёл: 3 теста, OK;
  - `test_static_candidate`: 8 OK. Эти тесты проверяют стадию static-candidate CLI на синтетических данных, а `static_prop_candidate.py` не запускают. Изменения скриптов проверены пересборкой бочки (побайтно, см. выше);
  - в числе 164 есть неотслеживаемые `test_rig_rules.py` и `test_um_master.py` параллельных сессий. Рабочее дерево — не состояние коммита этого прогона.

## 4. Отложено и подготовка коммита

1. **UE не запускался.** Отложены шаги ADDING-AN-ASSET §4.1:
   - шаг 1: прогон passthrough (`run` в `$R/ue-passthrough`; init и register уже сделаны). Для preflight нужен локальный сырой GLB `decor-lantern-tripo-h31-26bb832e-source.glb` (git-ignored, §1);
   - шаг 3: build-профиль `decor-lantern-static-um-fbx-v1.json` с `collision: none`, N `flip_green: false`, `protrusion_axis_ue: "+X"` (по габаритам X длиннее Y на 0,37 uu из-за фурнитуры);
   - шаг 4: CLI adopt;
   - §5: импорт в `/Game/PipelineCandidates/DecorLantern/20260928-lantern-tripo-h31/{Passthrough,Candidate}`.
2. **UE-материал свечения.** Стадия static-candidate ставит один MI на все слоты. Для `M_Decor_LanternGlow` нужен свой MI: эмиссия тёплого цвета (03 С-6), параметр интенсивности, выключение на минимальных настройках (08 §6.2). Плюс тёплый point-свет без теней в голове фонаря (03 С-8).
3. **Взгляд арта:**
   - roughness Tripo против 03 С-3 (§2.4);
   - сине-серое стекло в BC при выключенной эмиссии;
   - силуэт на игровой камере.
4. **Журнал кредитов: сделано перед коммитом.** Сводка `tripo.window` пересчитана по записям окна. Новых списаний нет. Запись шла под lock-файлом, концы строк CRLF сохранены.
   - `byTask`: добавлена строка фонаря на 130; сумма `byTask` 840 = `spent`;
   - `balanceEndUi`: 24 205 (было 24 335);
   - `balanceEndSource`: `balanceAfter` последней записи (PBR 05:44);
   - `arithmetic`: «25045 − 840 = 24205»;
   - добавлено поле `summaryNote`: что пересчитано и почему `tripo-run.json` не правился;
   - в `stage3Plan` у T7.1 добавлены `spent` 130 и `spentNote`. Это больше `maxCredits` 100 этого плана. План Tripo-этапа фонаря задавал 130 при потолке 250, основание траты указано в `owner` записей (писал оркестратор).
5. **Реестр: сделано перед коммитом.** Запись `ASSET-DECOR-KIT-001.LANTERN` в `asset-registry.json`:
   - статус «измерено», стадия `blender-candidate`;
   - вопрос о стороне петель закрыт для конвейера со ссылкой на `hingeSideDecision` и замер `lantern-hardware-readback.json`. Решение принял агент-планировщик, человек его отдельно не подтверждал. Взгляд человека на сторону петель остаётся в художественной проверке в UE;
   - добавлены source3d (PBR GLB с sha), слои `tripo-sources` и `blender-candidate SM_Decor_Lantern` (FBX и BC/N/ORM с sha), evidence (этот отчёт);
   - обновлены `nextStep` и `blocker`.

   `validate_registry.py`: RESULT PASS.
6. **Карта каталогов.** В [DIRECTORY-MAP.md](DIRECTORY-MAP.md) нет run-каталога фонаря (ADDING-AN-ASSET §7 п. 3). Сейчас этот файл правит параллельная сессия (волна 4), поэтому здесь он не менялся. Строку нужно внести отдельным изменением.
7. **Коммит** не делался, по условию задачи. Коммитить можно всё, кроме сырого GLB 68 МБ (он в `.gitignore`) и `work/*.blend`.
8. **Проработка героев** до уровня Medusa — просьба пользователя, пришедшая с этой задачей. В эту задачу про фонарь она не входит. Пользователь допустил перенос на следующую итерацию.

## 5. Команды

```bash
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"; R=art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31
T="python tools/tripo-pipeline/tripo_pipeline.py"
$T init --run-dir $R/ue-passthrough --asset-id ASSET-DECOR-KIT-001.LANTERN --primary-source tripo-26bb832e \
    --primary-role smartuv-tex2k-pbr-glb --export-basename SM_Decor_Lantern_TripoPassthrough --run-id 20260928-lantern-tripo-h31-ue-passthrough
$T register-source --run-dir $R/ue-passthrough --spec art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-26bb832e.json
"$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/static_prop_candidate.py -- $R/reports/candidate-params.json
"$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/check_static_prop_fbx.py -- $R/export/SM_Decor_Lantern.fbx $R/reports/fbx-readback.json $R/reports/candidate-params.json
"$B" -b --factory-startup --python-exit-code 1 --python art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/lantern_hardware_readback.py -- $R/export/SM_Decor_Lantern.fbx $R/reports/lantern-hardware-readback.json
"$B" -b --factory-startup --python-exit-code 1 --python art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/game_camera_preview.py -- $R/export/SM_Decor_Lantern.fbx $R/export/T_Decor_Lantern $R/preview
```

## История

До 2026-09-28 22:25 оба этапа стояли заблокированными: не было подтверждения траты, полученного напрямую от пользователя, и не было входного меша. В это время были подготовлены планы и превью входов:

- [tripo-stage-plan.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/reports/tripo-stage-plan.json): решение о стороне петель по front, слоты только front + back;
- [blender-stage-plan.json](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/reports/blender-stage-plan.json);
- превью входов: [четыре вида](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/preview/input-views-front-left-back-right.jpg), [фурнитура крупно](../../art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-lantern-tripo-h31/preview/input-views-door-hardware-zoom.jpg).

Статусы обоих планов обновлены. Шаблон params сохранён как история.
