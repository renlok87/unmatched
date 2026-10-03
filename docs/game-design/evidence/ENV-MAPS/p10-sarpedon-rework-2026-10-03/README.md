# ENV-MAPS P10: доработка вида Sarpedon по решению РД-3 — водопад, форт, борт корабля (2026-10-03)

Статус: **измерено, технически импортировано**. Обязательные критерии вердикта выполнены (таблица ниже); приёмка
оформлена **по делегированию** в акте [GD-058/sarpedon-2026-10-03](../../GD-058/sarpedon-2026-10-03/README.md).
«Художественно принято» по делегированию не ставится.

Полномочия: пользователь 2026-10-03 — «сам реши все вопросы»; ранее, 2026-09-29 — «делай все без меня». Решения записаны
в [2026-10-03-delegated-decisions.md](../../../decisions/2026-10-03-delegated-decisions.md) (РД-3, РД-7). Приёмочная
панель РД-3 вынесла вердикт **(В)**: короткая доработка вида lit3d + P9b, не более 3 итераций лёгкого режима, без
отката на P5c. Вердикт с точными правками, числовыми критериями и правилом остановки — спецификация этой работы
(файлы панели вне git: `C:/Users/ren/AppData/Local/Temp/claude/.../scratchpad/acceptance-sarpedon/VERDICT.md`).

**Итог в одной строке.** На кадре K1 по умолчанию больше нет «водопада-коробки»: прямая яркая кромка 206 → 20 px.
Тело водопада на C0 стало ближе к концепту (ΔE76 10,9 → 3,8), стена форта тоже (ΔE76 11,6 → 5,9). Борт корабля
теплее, в пределах критерия В-4: ΔE пятна корпуса 5,5 ≤ 6, пересвета нет. Пушки читаются как чугунные стволы в портах.
Не выполнен строгий критерий В-3: SSIM полигона корабля 0,442 < 0,45, третья пушка (cannon-1) остаётся тёмной.
Стоимость не изменилась: K1 2,60 мс (было 2,62).

## Критерии вердикта: до → после

«До» — кадры, по которым судила панель:
- K1 — эталон packaged 2026-10-03 (`fe12eb7c`, rev 20, `C:/tmp/envmaps-research/lightcheck/sarpedon/`);
- C0 = Fitx1,45 — кадр P9 ([p9-fixes…/sarpedon/bench-Fitx1p45](../p9-fixes-hero-light-2026-10-02/sarpedon/bench-Fitx1p45-1920x1080.png)).

«После» — свежий packaged `-Bench` сборки со штампом `8f524d8b` ([sarpedon-packaged/](sarpedon-packaged/),
`RENDER reference=1`, профиль rev 20 из pak, оверлей сцены `34742d7d…`).

Замеры повторяют числа панели на её же кадрах: 206 px @ строка 984, тело водопада 10,86 / dL* +10,52, форт 11,62.
JSON: [criteria-before.json](criteria-before.json), [criteria-after-packaged.json](criteria-after-packaged.json).

| Правка | Критерий (VERDICT §5) | До | После | Итог |
|---|---|---|---|---|
| В-1 водопад | K1 ROI (560–1360, 900–1080): самая длинная прямая горизонтальная кромка с перепадом > 35 уровней ≤ 100 px | 206 px | **20 px** | **PASS** |
| В-1 | C0 пятно тела (660–980, 870–1000) к концепту: ΔE76 ≤ 6, dL* ≤ +4 | 10,86 / +10,52; sRGB (66, 73, 88) | **3,84 / +1,57**; sRGB (46, 53, 66), концепт (38, 50, 67) | **PASS** |
| В-1 | G7: водопад live ≥ 10 % | 42 / 48 % (P9) | **29,3 % (Fitx) / 23,5 % (K1)** | **PASS** |
| В-2 форт | C0 пятно `fort` ΔE76 ≤ 7; G5 без изменений | 11,62 (dL* +8,2) | **5,93** (dL* +0,9) | **PASS** |
| В-4 тон борта | пятно корпуса `hull-red` ΔE ≤ 6; ни одного пикселя борта ≥ 245 | 4,14; 0 px | **5,52; 0 px** | **PASS** |
| В-3 пушки | F1: SSIM ¼ полигона корабля на C0 ≥ 0,45 | 0,431 | 0,442 | FAIL |
| В-3 | **или**: ΔL* ствола к стенке корпуса ≥ 12 у всех 3 пушек (патч 20×20) | среднее −3,7 / −3,9 / −2,5 | среднее −2,5 / +0,5 / +3,2; 90-й перцентиль 4,3 / 13,0 / 16,7 | FAIL (2 из 3 по перцентилю) |
| — | `hull-red` ΔE ≤ 6 сохраняется (условие В-3) | 4,14 | 5,52 | PASS |

**И-1** (В-1 + В-2) выполнен. **И-2** выполнен по критерию В-4. Правило остановки §5 требует «(В-3 или В-4-критерий)».
Критерий В-3 не выполнен. Подробности ниже: «Как мерили» и «Ограничения».

### Как мерили (скрипты вне git: `C:/tmp/envmaps-research/p10/tools/`)

- **Прямая кромка** (`edgerun.py`). Яркость Y = 0,2126 R + 0,7152 G + 0,0722 B. В каждой строке ROI берётся
  |Y(y+1) − Y(y)| > 35. Затем ищется самая длинная непрерывная серия столбцов. Определение восстановлено по числам
  панели и совпало со всеми четырьмя (K1 эталон 206 @ 984, C0 P9 81 @ 918, P8 70 @ 820, концепт 70 @ 822).
  Метрика зависит от фазы текстуры водопада. На тех же данных 10-03 редактор дал 90–94 px, packaged — 206 px.
  Поэтому итог взят только с packaged-кадра: 20 px.
- **Пятна ΔE76** (`crit.py`, `patch.py`): средний sRGB прямоугольника против `concept-registered-H.png` (C0), Lab D65.
  Это те же пятна, что `gates.py` G4.
- **F1 SSIM**: `fixes.py` P9 — SSIM яркости на ¼ разрешения внутри полигона `ship.targetC0Px`.
- **Пушки.** Патч 20×20 px взят в середине нарисованного ствола: между дулом `ports.muzzlePx` и точкой детали
  `sarpedon.paste.json` `cannon-N`. L* патча сравнивается с L* пятна `hull-red`.
  - По среднему критерий не выполняет и сам концепт: 7,5 / 10,2 / 14,4. Нарисованные стволы тёмные, читаются за счёт
    светлого обода.
  - Поэтому в таблицу добавлен и 90-й перцентиль L* патча. У концепта он 19,7 / 26,5 / 32,8.
- **Пиксели ≥ 245 на борту**: полигон корабля ниже планширя (y ≥ 250, x ≥ 1560). Исключены стекло трёх фонарей и
  чугун пушек. Блик на ободе дула cannon-3 — 2 px со значением 251. Это железо, а не борт; в JSON он записан отдельно.

## Итерации (лёгкий режим, live tune в одном клиенте редактора; использовано 2 из 3)

| | Что менялось | K1 кромка | тело водопада ΔE / dL* | форт ΔE | SSIM корабля | hull-red ΔE | ΔL* пушек p90 |
|---|---|---|---|---|---|---|---|
| i0 | как есть (rev 20) | 94* | 10,87 / +10,34 | 12,13 | 0,431 | 4,13 | −0,8 / −2,0 / 2,9 |
| i1 | водопад (меш + MI), форт 0,62, ящики причала ≤ 2,3, пушки (поворот +18°, светлый чугун) | 20 | 4,01 / +1,41 | 6,28 | 0,437 | 4,68 | 2,7 / 2,9 / 2,9 |
| i2 | тон борта (В-4), пушки ×1,25 вокруг нарисованного дула и +6 uu наружу, без поворота | 20 | 4,02 / +1,41 | 6,32 | 0,441 | 5,50 | 4,2 / 13,0 / 16,6 |
| **packaged** | итог (`8f524d8b`) | **20** | **3,84 / +1,57** | **5,93** | **0,442** | **5,52** | 4,3 / 13,0 / 16,7 |

\* Редактор; тот же вид в packaged — 206 (см. «Как мерили»). Журнал: [iterations.json](iterations.json).

Пробы внутри итераций, чтобы выбрать значение (кадр C0 за ~20 с, без перезапуска):
- i1, строки тюнера:
  - `materials.Fort.gain`: 0,75 → ΔE 8,1; 0,62 → 5,9; 0,55 → 5,2.
  - `materials.Ship.gain` / `tint`: ×1,45 с [1,1; 1; 0,9] из вердикта → `hull-red` 6,6 > 6; ×1,45 с [1,03; 1; 0,97] →
    5,8; ×1,6 нейтрально → 6,1. Нарисованный борт — нейтрально-тёмный красный, тёплый оттенок его пересыщает.
    Взято ×1,4 с [1,03; 1; 0,97].
- i2:
  - поворот пушек вокруг дула на +25° и +12° выдавил колёса лафета сквозь борт рядом с портом, поэтому поворот 0;
  - ящики ≤ 1,8 не изменили SSIM (0,441), а `hull-red` ухудшили до 6,45; оставлено 2,3.

## Что сделано (коммит `8f524d8b`)

| Правка | Где | Значения |
|---|---|---|
| В-1 рваный верх каскада | `cascade_build.py` `ragged_top_dip`, `scene-params` `cascade.rag` | 4 выемки [x, глубина, полуширина]: [−229, 17, 9], [−152, 14, 8], [−80, 18, 10], [−6, 15, 8] uu + шум 0..4 uu (масштаб 11 uu): верх воды под балкой — не прямая |
| В-1 ярусы смещены по потокам | `column_phase` → `ribbon(phase=…)`, `cascade.phase` | фаза яруса по потокам 0 / 0,2 / 0,07 / 0,27 + шум 0,1 (≈ 0–20 uu): полосы пены четырёх потоков не совпадают |
| В-1 пена не сплошной полосой | `cascade.foamJitter` | глубина подушек пены × 0,45–1, внутренний край ± 4 uu |
| В-1 цвет и прозрачность | `scene-tune` `materials.FallsSheet` / `FallsFoam` → `MI_EnvScene_Falls*` | тело 0,5 → 0,4, пена 0,96 → 0,5; подушки 0,85 / 1,0 → 0,5 / 0,5; самосвечение родителя `FallShade.w` 4 → 2 (ночью водопад светился); пена 0,85 → 0,65 и чуть синее |
| В-2 форт | `scene-tune` `baked.Fort` → `MI_Env_S_Fort` | `BakedTint` 0,45 → 0,279 (= `tintGain` 0,62 тюнера). Огонь форта 40 кд не менялся. В профиль `materialOverrides` не вносился: тест `ArtTuner.MaterialOverrides` требует, чтобы этого блока там не было |
| В-4 борт | `scene-tune` `baked.Ship` → `MI_Env_S_Ship` | `BakedTint` 1,3 → 1,4 × [1,03; 1; 0,97] |
| В-3 чугун | `ue_import_concept_paste.py` `CANNON_LOOK` → `MI_EnvCP_CannonIron` | `RestAdjust` V × 0,55 → 1,2; шероховатость 0,18–0,5 → 0,12–0,35 (блик на ободе); отдельный тег `CANNON_MI_VERSION` 3, копия меша не трогалась |
| В-3 пушки | `scene_layout.py`, `layout.details` | `cannonScaleMul` 1,25 и `cannonOutUU` 6 вокруг нарисованного дула (оно остаётся на своём пикселе); лафет — в пределах рамы порта (тест `test_cannons_in_the_ports`); `cannonYawOffsetDeg` 0 |
| В-3 ящики / бочки причала | `layout.props` | `scaleRange` 3,0 → 2,3 у `crate-deck-n` / `-mid` / `-se`, `barrel-dock-1` / `-2` |

Не трогались:
- ключ (−55, 30, 0), бюджет света (1 + 5 + moon-pool), камера K1, рама, поле карты;
- `S08ArtBoardProfiles.json` (rev 20, sha `23e4ebed…` — тот же в pak), `render-reference.json`;
- виды Marmoreal и Cobble.

Файлов `S08ArtTuner.overrides*.json` в `Config/ArtBoards` нет (VERDICT §6): ни один кадр не снят с демо-оттенками 10-03.
Кадры с тюнером (пробы i1) помечены `profilesSource=tuner`, итог по ним не считался.

Импорт в Content этой копии (Content вне git, коммандлеты при закрытом редакторе):
- `ue_scene_material.py`, i1: перестроены `MI_Env_S_Fort`, `MI_EnvScene_FallsSheet`, `MI_EnvScene_FallsFoam`,
  `MI_EnvScene_Proj_Wood` (сдвиг `FallbackTint` после смены масштаба ящиков) и `MI_EnvScene_Proj_RockWet`.
  - RockWet в Content этой копии не совпадал с закоммиченным планом; значения P10 его не затрагивают.
- `ue_scene_material.py`, i2: `MI_Env_S_Ship`.
- `ue_import_concept_scene.py`: `SM_Env_S_Cascade`, `SM_Env_S_CascadeFoam`.
- `ue_import_concept_paste.py --maps sarpedon`: только `MI_EnvCP_CannonIron`.
- Повторный прогон перед упаковкой: 43 / 43 «unchanged».

## Гейты (только затронутые)

| # | Замер | Порог | Итог |
|---|---|---|---|
| G5 | packaged K1: карта Y 104,9; мин. ΔE смежных зон 25,33; тёплых 0,126; кольцо ΔL* 33,6 (P9: 106,1 / 25,16 / 0,127 / 34,2) | 106,6 ± 5; ≥ 23,2; ≥ 0,12; ≥ 30 | **PASS** |
| G7 | live (`shot --live --clock free`, Fitx → Fitx через ~20 с, K1 → K1): водопад 29,3 / 23,5 %; огонь 14–27 %; кроны 16–17 %; знамя 7,0 % | 10 / 10 / 3 / 5 % | **PASS** (водопад). Знамя — для справки: интервал 20 с, в P9 было ~100 с; В-5 не делался |
| G8 | packaged `render_bench.py` v2, 3 повтора: K1 **2,60 мс** (шум 0,05), K1x0,65 2,58, K2x1,6 2,52, K2x2,5 2,44; треугольники каскада те же (2800 + 320) | K1 ≤ 3,5 и Δ к 2,62 ≤ +0,3; K2x1,6 ≤ 3,8 | **PASS** (Δ −0,02) |
| G9 | редактор `-Bench` против кадров P9b: Marmoreal K1 0,47 / 0,013 % пикселей > 24, K2x1,6 0,51 / 0,057 %; Cobble K1 0,25 / 0,0007 %, K2x1,6 0,39 / 0,002 % | на уровне шума бенч-бенч (0,24–0,48) | **PASS**. Правки P10 их не касаются: `SM_EnvCP_Cannon` есть только в раскладках Sarpedon |
| G4 | SSIM ¼ к концепту 0,490 (P9 0,474); медиана ΔE пятен 5,52 (P9 4,62: форт стал лучше, `hull-red` хуже на 1,4) | ≥ 0,55; ≤ 6 | SSIM FAIL (как в P8/P9), ΔE PASS |
| G6 | lantern-left 0,69 (без изменений); lantern-deck-se 0,82 → 0,69 | ≥ 0,8 | 4 из 6 (P9: 5 из 6). deck-se: фонарь не менялся. Раньше в маску «свечения» попадала освещённая грань ящика под ним, а ящик стал меньше (3,0 → 2,3) |

Стоимость контактных теней P9b (12 прожекторов героев), не измеренная в P9b, вошла в этот прогон: свет героев
включён в варианте v2, K1 2,60 мс.

## Тесты и проверки

- `python -m pytest tools/art/tests tools/art/map_surface -q`: **577 passed, 3 skipped**. Тест
  `test_cannons_in_the_ports` обновлён под P10: дуло на нарисованном пикселе + сдвиг наружу, лафет в раме порта.
- `--check`: `scene_layout.py` ok, `bake_albedo.py` ok, `ue_import_concept_scene.py` ok, `ue_scene_material.py` ok,
  `ue_import_concept_paste.py` ok; `layout_check.py --scene` OK.
- C++ не менялся, поэтому полный прогон UE не нужен. Выборочно запущено
  `Unmatched.S08.ConceptPaste+EnvLayout+ArtTuner+HeroLight+LiveTune`: **52/52**, EXIT CODE 0. Причина: тест ConceptPaste
  читает поставляемый оверлей сцены.
- Редактор и игру пересобирал оркестратор: коммит `f5d6d740`, «Result: Succeeded».
- Упаковка: `tools/s08/package-client.ps1` (полная, с `-build`) после коммита `8f524d8b`: «Result: Succeeded»,
  кук «Success - 0 error(s), 0 warning(s)», «BUILD SUCCESSFUL». Штамп `8f524d8b…`, sourceHash `13a9c773…`.
  Новых `Config/**.json` не было, ловушка makefile не сработала.
- `python tools/tripo-pipeline/validate_registry.py`: **PASS**. Статусы реестра не повышались.

## Кадры

| Набор | Файлы |
|---|---|
| После (packaged, эталонный отпечаток) | [K1](sarpedon-packaged/bench-K1-1920x1080.png), [C0 = Fitx1,45](sarpedon-packaged/bench-Fitx1p45-1920x1080.png), [K2x1,6](sarpedon-packaged/bench-K2x1p6-1920x1080.png), [трасса](sarpedon-packaged/bench.trace.log), [cmdline](sarpedon-packaged/cmdline.txt) |
| До | K1: эталон 10-03 (вне git, `C:/tmp/envmaps-research/lightcheck/sarpedon/`) и [P9b K1](../p9b-hero-light-detail-2026-10-02/sarpedon/bench-K1-1920x1080.png); C0: [P9 Fitx1,45](../p9-fixes-hero-light-2026-10-02/sarpedon/bench-Fitx1p45-1920x1080.png) |
| До / после (только кадры UE) | [K1, нижняя кромка](montage-k1-front-band.jpg), [C0: водопад и форт](montage-c0-falls-fort.jpg), [C0: борт](montage-c0-ship.jpg) |
| Метрики | [criteria-before.json](criteria-before.json), [criteria-after-packaged.json](criteria-after-packaged.json), [iterations.json](iterations.json), [g7-live.json](g7-live.json), [bench-summary.json](bench-summary.json) |

Вне git (ENV-U3/U7, пиксели концепта): `C:/tmp/envmaps-research/p10/montages-concept/concept-{falls-fort,ship}.jpg`.
Live-кадры итераций: `C:/tmp/envmaps-research/p10/runs/{i0,i1a,i1p*,i1,i2a..e,i2,i2-live}`.
Прогон бенча: `C:/tmp/envmaps-research/p10/bench/`.

## Команды

```
python tools/art/render/live_tune.py start --map sarpedon [--tuner]          # редактор, один клиент на итерацию
python tools/art/render/live_tune.py tune --set materials.Fort.gain=0.62 ...  # пробы (i1)
python tools/art/render/live_tune.py cycle --views K1+Fitx1.45+K2x1.6 --out C:/tmp/envmaps-research/p10/runs/<i> --tag <i>
python tools/art/render/live_tune.py shot --views Fitx1.45+K1+K1x1.0+Fitx1.450 --live --clock free --out .../i2-live
python tools/art/render/live_tune.py stop
python -B tools/art/concept_scene/cascade_build.py
python -B tools/art/concept_scene/run_scene.py --steps export,layout,manifest
# коммандлеты (редактор закрыт): UnrealEditor-Cmd <uproject> -run=pythonscript -script="<repo>/tools/art/concept_scene/ue_scene_material.py" -unattended -nosplash -nullrhi
#   затем tools/art/concept_scene/ue_import_concept_scene.py и "tools/art/concept_paste/ue_import_concept_paste.py --maps sarpedon"
powershell -File tools/s08/package-client.ps1
python tools/art/render/live_tune.py bench --packaged --map sarpedon --views K1+Fitx1.45+K2x1.6 --out .../final-pkg
python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --name sarpedon --repeats 3 --views K1+K1x0.65+K2x1.6+K2x2.5 --bench-fixture ../../../Unmatched/Config/Bench/S08BenchSarpedon.json --out C:/tmp/envmaps-research/p10/bench
python C:/tmp/envmaps-research/p10/tools/crit.py <run> --gates     # критерии P10 + G4 / G5 / G6
```

В другой копии Content нужно переимпортировать: каскад, пять MI сцены и `MI_EnvCP_CannonIron`. Коммандлеты те же, они
идемпотентны.

## Ограничения (VERDICT §5–6 и найденное здесь)

- **В-3 не выполнен.**
  - SSIM полигона корабля 0,442 < 0,45. Больше всего проигрывают знамя (смещено и короче нарисованного), низ у
    cannon-3, мачта и такелаж наверху.
  - cannon-1 тёмная: ΔL* по 90-му перцентилю 4,3 < 12. Она стоит в тени порта.
  - Пушки смотрят по нормали борта, а не влево, как на рисунке: поворот выдавливает колёса лафета сквозь борт.
  - И-2 закрыт критерием В-4.
- **Водопад** больше не «коробка», самосвечение вдвое слабее. Но читается полупрозрачной тёмной вуалью над нарисованными камнями, а
  не белыми струями между тёмными скалами, как в концепте. Прямые боковые стенки выреза острова (`island.nearLip`)
  не менялись: остров потребовал бы перепечь атлас.
- **В-5** (знамя, lantern-left) и **В-6 / И-3** (камни-«картофелины» у рамы) не делались. Итерация осталась, но
  обязательные критерии уже выполнены, а упаковка — одна.
- **G2** — тень под передним краем рамы и под Медузой, как в P5c–P9. **G4-SSIM** 0,49 < 0,55. **G7** — свет жаровни
  (std) не перемерялся. **D1** подсветки героев открыт. **G6**: lantern-left 0,69; lantern-deck-se 0,69 — объяснение в
  таблице гейтов.
- Более светлый `MI_EnvCP_CannonIron` меняет и пушки варианта `-ConceptPaste=paste`. Этот вариант не по умолчанию и
  не переснимался.
- Стоимость измерена на RTX 4090, не на D-07 (ACC-022 — пометка «не D-07»).
- Панель и эта работа смотрели статичные кадры `-Bench` и короткий live. Живую партию не запускали.
- Решение о приёмке принято по делегированию, без личного просмотра пользователя. Если он посмотрит и решит иначе —
  прав он.
- Отдельный агент ревью не запускался (лёгкий режим AGENTS.md).
