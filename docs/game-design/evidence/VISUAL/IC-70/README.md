# IC-70 — галерея UE и G-ICON для новых значков (VR44, шаги A2 и A3)

Прогон 2026-10-06 (VS-2 шаг A3, worktree `C:/tmp/wt-visual`, ветка `feat/visual-vs2`): галерея `-S08IconGallery`
против эталона Python (`motion.py` по контракту `icon-motion-2026-10-06-vr44-a3`), 64 px, моменты 0 / 120 / 300 / 600
/ 1000 / 2000 мс, обычный режим и `-S08ReducedMotion`. В галерее 45 id контракта: 23 набора v3, 4 DE-012, кандидат
`marker-turn-ring-team` и все 17 id `accepted_vr44`.

**Решение:** G-ICON — PASS; галерея UE совпадает с эталоном по форме и движению. Художественно принято, по делегированию
(ВР-60; пользователь 2026-10-06: «Делай сам … Все решения принимай»).
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A3.
**Флаг отката:** вид значков — `-S08IconLegacy`; эта карточка вид клиента не меняет (только средство ревью).
**Решения по делегированию:** ВР-VS2-37, ВР-VS2-38, ВР-VS2-39 (ниже).

## Итог

| Режим | Растр эталона | Пар | Средняя \|Δ\| | Новые id (17): пар / средняя | Худший новый id | Трасса `ICONGALLERY ids` |
|---|---|---|---|---|---|---|
| normal | ue (G-ICON, ВР-VS2-37) | 270 | **0,026** | 102 / **0,011** | `action-end-turn` 0,028 | 45 id, все списки контракта — да |
| reduced | ue | 270 | **0,009** | 102 / **0,003** | `action-end-turn` 0,006 | 45 id — да |
| normal | ref (растр листов, как прогон I) | 270 | 0,364 | 102 / 0,299 | `action-end-turn` 0,940 | — |
| reduced | ref | 270 | 0,013 | 102 / 0,003 | `action-end-turn` 0,006 | — |

Порог 0,45 (02 §13.5) выполнен по всем парам и по каждому новому id. Худший id набора — `resource-connection-reconnecting`
0,21 (знак ↻ повёрнут: у повёрнутого квада Slate не ставит углы на пиксели, ВР-VS2-37).

### По каждому новому id (средняя \|Δ\| по 6 моментам)

| id | Карточка | normal, ue | reduced, ue | normal, ref | reduced, ref |
|---|---|---|---|---|---|
| `badge-order` | IC-38 (IC-39 — вариант p2) | 0,004 | 0,002 | 0,157 | 0,002 |
| `badge-refuse` | IC-40 | 0,016 | 0,001 | 0,360 | 0,001 |
| `badge-conflict` | IC-41 | 0,004 | 0,002 | 0,160 | 0,002 |
| `badge-ally` | IC-42 | 0,022 | 0,005 | 0,513 | 0,005 |
| `badge-attack-from` | IC-43 | 0,016 | 0,004 | 0,125 | 0,004 |
| `team-chip-p1` | IC-44 | 0,009 | 0,005 | 0,276 | 0,005 |
| `team-chip-p2` | IC-45 | 0,006 | 0,003 | 0,283 | 0,003 |
| `state-warning` | IC-47 | 0,015 | 0,003 | 0,244 | 0,003 |
| `marker-slot-scheme` | IC-50 | 0,003 | 0,002 | 0,124 | 0,002 |
| `marker-slot-boost` | IC-51 | 0,004 | 0,002 | 0,174 | 0,002 |
| `ui-menu` | IC-53 | 0,007 | 0,000 | 0,260 | 0,000 |
| `ui-close` | IC-54 | 0,006 | 0,002 | 0,134 | 0,002 |
| `ui-step` | IC-56 | 0,004 | 0,001 | 0,065 | 0,001 |
| `action-end-turn` | IC-46 | 0,028 | 0,006 | 0,940 | 0,006 |
| `card-drop` | IC-48 | 0,019 | 0,002 | 0,525 | 0,002 |
| `marker-slot-discard` | IC-52 | 0,003 | 0,002 | 0,145 | 0,002 |
| `ui-log` | IC-55 | 0,019 | 0,004 | 0,606 | 0,004 |

Курсоры IC-58…IC-61 вне контракта движения и галереи (строка карточки); IC-49, IC-57, IC-62…IC-69 — тем же способом
по готовности.

## Что сделано

- **Трасса перечисляет id.** `ICONGALLERY ids n=45 columns=7 list=<id,…>` после `ICONGALLERY start`
  (`US08IconGalleryWidget::IdList`, hook в `S08FlowGameModeIconGallery.cpp`). `compare_ue_gallery.py` сверяет строку
  со списками контракта `accepted_vr44`, `accepted_de012`, `candidates` (`summary.trace_ok`).
- **Сетка галереи помещается в кадр** (ВР-VS2-38): `US08IconGalleryWidget::ColumnsToFit` — 7 колонок × 7 рядов для
  45 значков. Прежние 6 колонок давали 8 рядов по 142 su = 1136 su > 1080 su: ряды сжимались до 135 su, ячейка
  130 su вставала в слот 123 su по центру со сдвигом полпикселя, подпись поднималась в окно значка. От этого прогон
  шага A3 до правки давал G-ICON 0,649 (`resource-connection-reconnecting` 4,02 — подпись в две строки в окне).
- **Растр эталона как у Slate** (ВР-VS2-37): `motion.compose(…, raster="ue")` и `compare_ue_gallery.py --raster ue`
  (по умолчанию). Прежний растр — `--raster ref`, его числа в таблице выше и в `compare-ref.json`.
- UE-тест `Unmatched.S08.IconMotion.GalleryIds`: сетка = порядок контракта, ряды помещаются в 1080 su (45 → 7 колонок,
  28 → 6), `IdList` содержит каждый id `accepted_vr44` / `accepted_de012` / `candidates` (22).
- pytest `tools/s08/hud_contract/test_icon_motion.py`: `GalleryRasterTests` (покой одинаков в обоих растрах, снап квада,
  линейный свет светлее гамма-смеси на краю), `GalleryCompareSummaryTests` (сверка трассы).

## Решения по делегированию

- **ВР-VS2-37.** G-ICON считается против эталона с растром Slate: у осевого преобразования (масштаб, сдвиг) углы
  квада текстуры стоят на целых пикселях, sRGB-текстура читается билинейно в линейном свете; смешение слоёв — в sRGB,
  как в листах. Замер: на покое растры совпадают байт в байт, а на масштабе ≠ 1 (выход 1,026 на 120 мс, наведение
  1,06) прежний растр (билинейно в sRGB, без снапа) отличался от UE на краях на 1–5 \|Δ\| при совпадающих позах
  (тест `Unmatched.S08.IconMotion.Golden`, 1e-3). С растром Slate те же кадры совпали до 0,03. Так гейт мерит форму и
  позу, а не разницу растров. Он стал строже: прежний шум 1–3 скрывал бы реальную ошибку позы такого же размера.
  Прежний растр остаётся `--raster ref`, листы и GIF `motion.py` рисуются им, как раньше.
- **ВР-VS2-38.** Галерея выбирает число колонок так, чтобы ряды поместились в 1080 su (не меньше 6 колонок). Это
  средство ревью, вид клиента не меняется.
- **ВР-VS2-39.** Галерея снята на сборке редактора в режиме `-game` (`UnrealEditor.exe Unmatched.uproject -game …`,
  те же бинарники и текстуры, что пойдут в пак, без кука): шаг A3 идёт без упаковки (одна упаковка — шаг «Кадры»
  VS-2). Подтверждение на упаковке — той же командой на `Saved/StagedBuilds/Windows/Unmatched.exe` в шаге «Кадры».

## Команда

```
UnrealEditor.exe <wt>/unreal/Unmatched/Unmatched.uproject -game -windowed -ResX=1920 -ResY=1080 -ForceRes
  -RenderOffScreen -nosound -unattended -nosplash -S08IconGallery -S08IconGallerySize=64
  -S08IconGalleryShots=<dir> -S08IconGalleryTimes=0,120,300,600,1000,2000 -S08Trace=<dir>/gallery.trace.log
  [-S08ReducedMotion]
python art/imagegen/hud-icons-v3/_tools/compare_ue_gallery.py <dir> [--reduced] --size 64            # G-ICON, raster ue
python art/imagegen/hud-icons-v3/_tools/compare_ue_gallery.py <dir> [--reduced] --size 64 --raster ref \
  --json <dir>/compare-ref.json --out <png>                                                          # для сравнения
```

Каждый прогон 12–13 с, процесс выходит сам после последнего кадра (`ICONGALLERY done`, exit 0); других процессов
шаг не оставил.

## Файлы

- `gallery/normal/`, `gallery/reduced/`: `icon-gallery-<mode>-<t>.png` (6 кадров), `gallery.trace.log`,
  `compare.json` (G-ICON, растр ue, `summary`), `compare.png` (лист «UE | эталон | \|Δ\|×4»), `compare-ref.json`
  (растр ref). PNG в git — 3,3 МБ (бюджет ≤ 5 МБ). Листы растра ref — вне git (`C:/tmp/visual/IC-70/`).

## Проверка глазами

- Открыты все 12 PNG галереи (Read): 45 ячеек 7 × 7, подписи под значками, ничего не налезает. В normal видны выход
  (0 мс — бледные, 120 мс — выход), наведение и выбор (600 / 1000 мс: импульсы глифа, вспышка кольца, заливка слота DE),
  уход (2000 мс: часть значков ушла по сценарию). В reduced на 0 мс почти все значки ещё не появились (видны только стартовые
  состояния связи lost и сердца павшего), дальше — только прозрачность и статика; движение формы — только ступени спиннера (контракт IC-16, reduced 250 мс на ступень).
- Открыт `compare.png` normal целиком (три части): столбцы «UE» и «эталон» совпадают по форме, цвету и позе, столбец
  \|Δ\|×4 чёрный; слабый след — только у повёрнутого знака ↻ и у ступеней спиннера.
- Reduced у новых id: по сценарию demo с шагом 5 мс у всех 17 id нет масштаба, сдвига и поворота — только прозрачность.

## Тесты

- UE `Unmatched.S08.IconMotion.*` — 11/11 (Load, Golden, Reduced, Textures, Widget, Semantics, CombatView, DefaultToken,
  TurnPortrait, TurnHudRollbacks, GalleryIds).
- pytest `tools/s08/hud_contract` — 62 passed.

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

- **G-ICON на упаковке** (`StagedBuilds/Windows/Unmatched.exe`, ВР-VS2-39 закрыт).
  - normal: \|Δ\| 0,026, новые id — 0,011 (худший `action-end-turn` 0,028);
  - reduced: 0,009 и 0,003;
  - трасса перечисляет все 45 id.
  Числа совпали с прогоном A3 в editor `-game`. Открыты 12 PNG галереи и оба листа сравнения. Данные — `VS-2/data/gicon-compare-*.json`.
