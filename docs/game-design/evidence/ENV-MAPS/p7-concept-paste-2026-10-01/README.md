# ENV-MAPS P7: концепт вклеен вокруг поля карты Sarpedon (ENV-U15) — интеграция, настройка, кадры, packaged (2026-10-01)

Статус: **предложено, измерено, технически импортировано**. «Художественно принято» решает только пользователь.

Описание сцены одобрено пользователем: `docs/art-pipeline/ENV-CONCEPT-PASTE.md` («. Делай.»). Решение ENV-U15: поле карты
(оригинальная карта с кругами и связями внутри рамки) остаётся настоящим, всё вокруг — из концепта, мелкие детали — 3D
с анимацией. Sarpedon: вклейка включена по умолчанию, прежняя композиция P5c — `-EnvLayoutVariant=p5c` (или
`-ConceptPaste=0`). Marmoreal принят: по умолчанию не изменился, вклейка только по флагу `-ConceptPaste` (или
`-EnvLayoutVariant=concept`), для сравнения. Cobble и сетки не затронуты.

## Как устроено

| Слой | Что | Откуда |
|---|---|---|
| A — настоящее | оригинальная карта, круги, связи, фигуры, подсветка, 3D-рама frame-002 | как в P5c |
| B — рисунок | концепт `sarpedon-v2`: чистая плита ×2 + достройка краёв (imagegen, вне git), спроецирован из камеры концепта C0 (HFOV 35, наклон −55°, 2714,6 uu) на «лист глубины» (рельеф: земля, кроны, бухта, обрыв, вертикальные плоскости у фортов, столбов, ящиков и борта), плоскость моря Z −300 и цилиндр неба (48 сегментов) | `S08ConceptPaste`, `M_ConceptPaste` (unlit, masked), текстуры и листы из `tools/art/concept_paste/` (P7a/A/B) |
| C — 3D-детали | 6 фонарей (только голова с крюком, `SM_EnvCP_LanternHead`, стекло светится), 3 пушки, знамя, 2 огня (`NS_Env_ConceptFire`), 6 огоньков в фонарях, светлячки над лесом; 5 точечных светов у огней и фонарей | `EnvLayouts/sarpedon.concept.layout.json`, блок `conceptPaste` профиля |

Что нарисовано (в плите): небо и луна, руины форта, бухта с лодкой и сваями, лес и частокол, борт корабля с вантами,
бочками и ящиками, передний обрыв с водопадом, скалы и море. Что 3D: фонари, огни, пушки, знамя, светлячки, а также
течение воды по рисунку (водопад, прибой в бухте, море). Скрыто в режиме вклейки: поднос T2b, полосы земли, кольцо моря,
3D-водопады, фон-луна, туман, все 54 пропса P5c и их огни, 5 светов раскладки.

Рисованный слой не освещается движком. Его яркость задаётся измеренной кривой тонмаппера (см. «Настройка»). Срез
проходит на 2 uu под внешней ногой рамы frame-002, поэтому шва в кадре нет. Свет: 1 ключевой (−55, 30, 0, без изменений)
+ 6 точек (лунный свет профиля + 5 точек вклейки; `combinedPoints=6 combinedBudgetOk=1`).

## Интеграция (сборка, импорт, тесты)

- UnmatchedEditor и Unmatched Win64 Development: «Result: Succeeded» (`-NoXGE`, `-MaxParallelActions=6` и `=4` для игры).
  Ошибки трека B исправлены:
  - в `S08ConceptPasteTests.cpp` локальная переменная `PI` совпадала с макросом UE (C2664);
  - C4701 (`Ndc` не инициализирована);
  - тест сетки 3×2 под `-nullrhi` ждал включённого арта, а без материалов плиток доска остаётся серой. Проверка
    сведена к «не карта», как в тестах BoardArt;
  - допуск `Right()` 1e-9 → 1e-6.
- Коммандлеты (редактор закрыт):
  - `ue_concept_material.py` — `M_ConceptPaste` graph 3;
  - `ue_import_concept_paste.py --maps sarpedon,marmoreal` — 7 текстур, 4 меша, `MI_EnvCP_LanternHead`. Границы мешей
    совпадают с отчётом сборки (≤ 0,005 uu);
  - `ue_import_fab_fx.py --only NS_Env_ConceptFire`.
- `node tools/s08/run-ue-tests.cjs "Unmatched.S08+Unmatched.S09+Unmatched.S10"` — **244/244**, EXIT CODE 0. Среди них 7
  тестов `Unmatched.S08.ConceptPaste.*`; Actor проходит по настоящему пути Sarpedon (ассеты импортированы, предупреждений нет).
- `python -m pytest tools/art/tests tools/art/map_surface -q` — **451 passed, 2 skipped**, 91 subtests.
- Все `--check` дают ok (список в «Команды»).

## Настройка (5 итераций, лог `C:/tmp/envmaps-research/p7/tune/log.md`, вне git)

Новый вид бенча `Fitx1.45`: центр, дистанция = fit × 1,45 = 2714,6 uu, то есть ровно камера концепта C0
(`FS08CameraZoom::BenchDistance`, `S08FlowGameMode.cpp`). Кадр игры совпадает с концептом с точностью 0 px по фазовой
корреляции.

Отступления от контракта P7a и их измеренные причины:

1. **Вместо LUT-текстуры — измеренная кривая тонмаппера.**
   - Таблица 256×1 в `.hdr` импортируется в UE 5.8 (Interchange) как TextureCube, и задать ей адресацию нельзя.
   - Калибровочная карта `-ConceptPasteCalib` для тёмных ночных уровней непригодна: одинаковые ячейки расходятся на
     2–6 уровней из-за свечения (bloom) от ярких рядов и виньетки.
   - Поэтому кривая снята прямо с кадра C0: там каждый пиксель листа показывает известный тексель плиты A.
   - Модель по каналам: display = sRGB(ACES(k × V × E)^p). Подгонка: k = 0,330 / 0,346 / 0,315, p = 1,058 / 1,070 /
     1,040; остаток по корзинам ≤ 1,6 уровня.
   - В профиле это `grade.fitScale` = 1/k и `grade.fitPower` = p (режим aces-inverse, `emissiveScale` 1). Путь через LUT
     остался в коде, но не используется.
2. **Виньетка движка снимается с рисованного слоя** (`grade.devignette 0.4`). Это cos⁴-виньетка UE (интенсивность 0,4
   по умолчанию). Без компенсации углы рисунка выходили на 19–31 % темнее плиты (отношение кадр/плита 0,69–0,81 при
   r ≥ 0,9). Карта и фигуры по-прежнему проходят под виньеткой.
3. **Свет у левого края карты.** `lantern-left` стоит в 120 uu от карты, на высоте 154. С ним синие клетки теплели
   (b −7,2 → −4,1), и ΔE пары синий–пурпурный падала до 22,95 (порог 23,2). Изменение: 80 → **30 кд**, радиус
   400 → 300; `fire-brazier` 55 → **45 кд**.
4. **Размер деталей.** На кадре C0 нарисованные фонари в 1,6–1,9 раза крупнее 3D-голов, пушки — в ~1,35 раза.
   - Добавлен `sizeMul` в `sarpedon.paste.json`: фонари 1,6, пушки 1,35.
   - Центр стекла фонаря и ось ствола пушки остаются на своих точках дизайна (тест: 0,05 uu).
   - Новый `MI_EnvCP_LanternHead`: стекло ×8, цвет (1; 0,42; 0,1). С ×7,6 у `MI_Env_LanternPost` стекло было тёмным,
     а ×14–22 выжигали его в белый.
5. **Огонь вклейки.** `NS_Env_Campfire` (цвет ×3) поверх тлеющих углей чистой плиты читался как красное пятно. Сделана
   копия `NS_Env_ConceptFire` (k 0,5, цвет ×5): у неё появилось жёлтое ядро. `NS_Env_Campfire` (P5c) не изменён.

| Итерация | Что менялось | ΔE76 зон (син.–пурп.) | Карта Y K1 | Кадр/плита по радиусу | Детали |
|---|---|---|---|---|---|
| i0 (как сдано) | aces-приближение × экспозиция 4,14 | 22,95 | 108,9 | 1,11 … 0,69 | мелкие тёмные фонари, красные пятна огня |
| i1 | измеренная кривая + devignette; lantern-left 40 кд | 23,19 | 107,9 | 0,97–0,99 (углы 0,93–0,95) | то же |
| i2 | lantern-left 30 кд; sizeMul; стекло ×22 | 23,31 | 107,7 | то же | размер как на рисунке; стекло белое |
| i3 | NS_Env_ConceptFire (цвет ×1,6); стекло ×14 | 23,29 | 107,7 | то же | огонь тёмно-красный |
| i4 = финал | огонь ×5; стекло ×8, оранжевое | 23,27–23,31 | 107,7 | то же | стекло тёплое, у огня жёлтое ядро |

## Кадры (редактор, `-game -Bench`, High / SP100 / DX12 Lumen; все SHOT на эталоне, `fingerprints/*.json`)

`profilesSha256` в трассах = sha256 итогового `S08ArtBoardProfiles.json`: `6dc72c34…`. `overlaySha256` вклейки:
`8a43f7bf…`.

| Набор | Кадры |
|---|---|
| Sarpedon по умолчанию (вклейка) | [C0 = Fitx1.45](sarpedon/bench-Fitx1p45-1920x1080.png), [K1](sarpedon/bench-K1-1920x1080.png), [K1x0,65](sarpedon/bench-K1x0p65-1920x1080.png), [K2x1,6 на Медузе](sarpedon/bench-K2x1p6-1920x1080.png), [K2x1,6 по центру (K1x1.6)](sarpedon/bench-K1x1p6-1920x1080.png), [K2x2,5](sarpedon/bench-K2x2p5-1920x1080.png) |
| Sarpedon `-EnvLayoutVariant=p5c` | [K1](sarpedon-p5c-variant/bench-K1-1920x1080.png) + `vs-p5c.json` (все 4 вида) |
| Marmoreal по умолчанию | [K1](marmoreal/bench-K1-1920x1080.png) + `vs-p5c.json` (все 4 вида) |
| Marmoreal `-ConceptPaste` (сравнение) | [C0](marmoreal-concept-flag/bench-Fitx1p45-1920x1080.png), [K1](marmoreal-concept-flag/bench-K1-1920x1080.png) |
| Cobble (регрессия) | [K1](cobble/bench-K1-1920x1080.png) + `vs-p5c.json` |
| Живые анимации (`-EnvFxLive`) | [K1](sarpedon-live-anim/bench-K1-1920x1080.png), [разница двух кадров через 15 с](sarpedon-live-anim/diff-live-K1.png) |
| packaged `-Bench` | [Sarpedon K1](packaged-sarpedon/bench-K1-1920x1080.png) |

Монтажи в git (только кадры UE):
- [montage-sarpedon-p5c-vs-p7.jpg](montage-sarpedon-p5c-vs-p7.jpg) — P5c и вклейка на K1, K1x0,65 и K2x1,6;
- [montage-marmoreal-default-vs-flag.jpg](montage-marmoreal-default-vs-flag.jpg) — P5c, Marmoreal по умолчанию сегодня и
  с флагом.

Монтажи с пикселями концепта и моков P7a лежат **вне git** (ENV-U3/U7) в `C:/tmp/envmaps-research/p7/evidence-montages/`:
- `montage-sarpedon-concept-mock-vs-game.jpg` — концепт и кадр C0, мок и кадр на K1, K1x0,65, K2x1,6 (Медуза и центр);
- `montage-marmoreal-concept-vs-flag.jpg`;
- `sarpedon-details-c0.jpg`, `sarpedon-details-k1.jpg` — 12 деталей: рисунок против 3D;
- `i1-details-concept-vs-game.jpg` — те же детали до настройки.

Полные наборы кадров всех прогонов — `C:/tmp/envmaps-research/p7/tune/runs/` (i0–i4, f*, f2*, f3*).

## Замеры

### Совпадение с концептом в позе C0 (Sarpedon, вне поля и рамы; `sarpedon/cmp-concept.json`, `concept-scale-ssim.json`, `de-plate.json`)

| Сравнение | Средняя \|разница\| (0–255), p50 | SSIM (яркость) | SSIM при ¼ разрешения |
|---|---|---|---|
| кадр — концепт `sarpedon-v2` | 19,3 (10,7) | 0,477 | 0,632 |
| кадр — концепт, чистая плита | 16,9 (8,0) | 0,567 | – |
| плита A (×2 imagegen) — концепт | 21,9 | 0,382 | 0,597 |
| **кадр — плита A** (точность конвейера) | **8,3** | **0,837** | – |
| кадр — мок P7a в позе концепта | 9,7 (4,7) | 0,758 | – |
| Marmoreal с флагом: кадр — концепт `marmoreal-v1` (сырой концепт, без ×2) | 13,3 | 0,750 | 0,789 |

Вывод: движок воспроизводит заданную плиту близко.
- На ровных участках листа ΔE76 кадр — плита: **медиана 0,80**, p90 2,2 (r < 0,9: 0,59 / 1,67). Цель дизайна — ΔE < 2.
- Отличие от самого концепта задаёт плита ×2: imagegen перерисовал мелкую фактуру при той же композиции.
- Без ×2 (Marmoreal) кадр ближе к концепту: SSIM 0,75 против 0,48.

Швы и растяжение:
- **Шов у края маски острова.** Градиент кадра на краю маски / вдали от края = 1,18; у концепта 1,06. Это лишние 12 %
  контраста на краю. На кадрах шва не видно: проверены края острова при K1x0,65 и K2.
- **Шов у поля карты.** Его нет: срез на 2 uu под ногой рамы.
- **Растяжение на K2.** Резкость окружения против мока: K2x1,6 на Медузе 0,94, K2x1,6 по центру 1,02. Плита A даёт
  2,1 текселя на пиксель концепта, мыла при приближении нет. Сдвиг кадра K2 относительно мока ≤ 2 px. Фонарь у левого
  края висит под нарисованной перекладиной.

### Поле карты и окружение (P5c `measure.py` / `zone_precise.py`; `sarpedon/measure.json`)

| Метрика | Цель | P5c | Вклейка C0 | K1 | K1x0,65 | K2x1,6 (Медуза) | K2x1,6 (центр) | K2x2,5 |
|---|---|---|---|---|---|---|---|---|
| Яркость карты Y | 106,6 ± 5 | 106,6 | 109,0 | **107,7** | 109,3 | 108,7 | 101,0 | 113,0 |
| Окружение / карта | ≈ 0,36 (мок 0,355, концепт 0,345) | 0,450 | 0,373 | **0,396** | 0,372 | 0,44 | 0,51 | 0,35 |
| Доля тёплых в окружении | ≥ 0,12 | 0,145 | 0,12 | **0,13** | 0,12 | 0,22 | 0,23 | 0,12 |
| Мин. ΔE76 смежных зон | ≥ 23,2 | 23,39 | – | **23,28–23,31** (5 прогонов) | – | – | – | – |
| Контур круга ΔL*, медиана | ≥ P4 33,8 | 33,7 | 32,7 | 34,0 | 33,8 | 49,6 | 45,2 | 53,4 |

Окружение / карта на K1 = 0,396. Это выше мока 0,355: мок не учитывает свечение (bloom) от яркой карты и 3D-огней.
На ровных участках кадр равен плите. Глобальное усиление на это почти не влияет: средняя |разница| с концептом при
усилении 0,8–1,0 меняется только 18,5 → 19,3.

### Регрессии (`*/vs-p5c.json`)

| Что | Средняя \|разница\| к кадрам P5c | Пикселей > 24 | Комментарий |
|---|---|---|---|
| Marmoreal по умолчанию, 4 вида | 0,29–0,34 | ≤ 0,010 % | Трасса совпадает с P5c, кроме ревизии и sha профиля и строки `concept-paste mode=off`. Отличия только у фигур: снимок сделан на 2–3 кадра раньше (4415–4416 против 4418), поза idle в другой фазе. Повтор того же дерева сегодня: 0,10–0,15. ΔE зон 23,36 (P5c 23,36 / 23,32), карта Y 117,6, окружение / карта 0,557 — как в P5c. |
| Cobble K1 | 0,196 | 0,0003 % | Отличия у фигур. |
| Sarpedon `-EnvLayoutVariant=p5c`, 4 вида | 0,34–0,43 | 0,007–0,18 % | Отличия только в материалах костров, анимированных нодой `Time` (как в замечании о детерминизме P5c). ΔE зон 23,36, карта Y 106,6, окружение / карта 0,450 — значения P5c. |

### Анимированные детали (`sarpedon-live-anim/`, `-EnvFxLive`)

- В трассе: `concept-paste anim mode=live flickers=5 sways=1 missingProps=0` (мерцают 5 светов, качается
  `lantern-rail`), `flowFrozen=0` (течёт вода по рисунку), `envlayout fx … mode=live particles=450`.
- Два кадра K1 с разницей 15 с различаются на 1,73 % пикселей (> 8 уровней), и только в местах анимаций:
  - огонь форта 15,3 %;
  - жаровня 11,6 %;
  - прибой в бухте 8,9 %;
  - водопад 15,5 %;
  - фонарь на поручне 5,0 %.
- В `-Bench` всё заморожено (`mode=frozen flickers=0 sways=0 flowFrozen=1`), поэтому кадры доказательств воспроизводимы.

### packaged: сборка и стоимость (`bench-summary.json`)

- `tools/s08/package-client.ps1 -SkipBuild` после сборки игры: «BUILD SUCCESSFUL». Кук 1126 / 1126 пакетов (P6: 1112;
  +14 — ассеты вклейки), «Success - 0 error(s), 0 warning(s)».
- Packaged `-Bench` Sarpedon. В трассе: `concept-paste mode=on`, `status=ok`, `sheet=1 sea=49 lights=5`,
  `budget combinedPoints=6`. SHOT на эталоне.
- `render_bench.py run --variant dx12-lumen-high-v2 --repeats 3 --views K1+K1x0.65+K2x1.6+K2x2.5`, Sarpedon и Cobble,
  все 6 прогонов exit 0. GPU до замера простаивал: 0 %. Замер снят на сборке, побайтно совпадающей по профилю
  (`6dc72c34…`) и раскладке вклейки (`8a43f7bf…`) с итоговыми файлами. Промежуточная сборка с пробным переносом жаровни
  дала те же числа: 2,04–2,06 мс на K1. Её прогоны лежат вне git, в `C:/tmp/envmaps-research/p7/bench-sarpedon-brazier-offset`.

| Доска | Вид | GPU avg P6 → P7, мс | Δ / порог (2 × шум) | p95 P7 |
|---|---|---|---|---|
| sarpedon | K1 | 2,623 → **2,053** | **−0,570** / 0,040 | 2,16 |
| sarpedon | K1x0,65 | 2,617 → 2,050 | −0,567 / 0,040 | 2,15 |
| sarpedon | K2x1,6 | 2,507 → 2,143 | −0,363 / 0,040 | 2,23 |
| sarpedon | K2x2,5 | 2,397 → 2,170 | −0,227 / 0,020 | 2,23 |
| cobble | K1 | 1,823 → 1,857 | +0,033 / 0,020 | 1,92 |
| cobble | K1x0,65 | 1,733 → 1,753 | +0,020 / 0,020 | 1,83 |
| cobble | K2x1,6 | 1,930 → 1,960 | +0,030 / 0,000 | 2,03 |
| cobble | K2x2,5 | 2,063 → 2,010 | −0,053 / 0,020 | 2,07 |

Вывод:
- Вклейка **дешевле** P5c: −0,57 мс на K1.
- Основная экономия на K1:
  - DeferredLighting 0,435 → 0,200 (−0,24);
  - Basepass 0,193 → 0,097;
  - Translucency 0,155 → 0,098;
  - LumenReflections 0,186 → 0,126.
- Причина: вместо 54 освещаемых пропсов, моря и подноса — один unlit-лист.
- Cobble сдвинулся на ±0,02–0,05 мс: это фон машины, его контент не менялся.

## Команды

```
# сборка (C:/tmp/unmatched-package.lock, owner=ENV-MAPS-P7)
node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development "-Project=C:/tmp/wt-envmaps/unreal/Unmatched/Unmatched.uproject" -NoXGE -MaxParallelActions=6 -WaitMutex
node tools/s08/build-editor.cjs Unmatched Win64 Development "-Project=..." -NoXGE -MaxParallelActions=4 -WaitMutex
# импорт (редактор закрыт)
UnrealEditor-Cmd <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript -script="<repo>/tools/art/concept_paste/ue_concept_material.py" -unattended -nosplash -nullrhi
UnrealEditor-Cmd ... -script="<repo>/tools/art/concept_paste/ue_import_concept_paste.py --maps sarpedon,marmoreal"   # + MI_EnvCP_LanternHead
UnrealEditor-Cmd ... -script="<repo>/tools/art/env_kit/ue_import_fab_fx.py --only NS_Env_ConceptFire"
# кадры (C:/tmp/unmatched-gpu.lock): UnrealEditor.exe ... -game -ArtPreview -ArtPreviewDiorama -ArtPreviewHeroesV2 -Bench
#   -BenchFixture=Config/Bench/S08Bench<Map>.json -BenchViews=Fitx1.45+K1+K1x0.65+K2x1.6+K1x1.6+K2x2.5 -BenchWarmup=60
#   -S08RenderPreset=High [-EnvLayoutVariant=p5c | -ConceptPaste | -EnvFxLive]   (<набор>/cmdline.txt)
node tools/s08/run-ue-tests.cjs "Unmatched.S08+Unmatched.S09+Unmatched.S10" <log>          # 244/244
python -m pytest tools/art/tests tools/art/map_surface -q                                    # 451 passed, 2 skipped
python -B tools/art/concept_paste/{cp_bake.py check sarpedon marmoreal, cp_proxies.py check, cp_layout.py --check,
          ue_import_concept_paste.py --check, ue_concept_material.py --check}                 # ok
python -B tools/art/env_kit/{ue_import_fab_picks,ue_import_fab_fx,ue_import_env_kit,ue_import_env_ground,ue_import_tray_t2}.py --check
python -B tools/art/map_surface/ue_import_map_surface.py --check; tools/art/map_surface/backdrop.py --check; tools/art/env_kit/hlsl_check.py
python -B tools/art/env_kit/env_prop_look.py --check; tools/art/art_board_fixtures.py check; tools/art/env_kit/ground_splat.py --check
python -B tools/art/env_kit/layout_check.py; art/pipeline-candidates/ASSET-ENV-KIT-001/*/scripts/p5*_layout_*.py --check   # все ok
powershell -File tools/s08/package-client.ps1 -SkipBuild                                    # BUILD SUCCESSFUL
python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --name sarpedon --repeats 3 --views K1+K1x0.65+K2x1.6+K2x2.5 --bench-fixture ../../../Unmatched/Config/Bench/S08BenchSarpedon.json --out <dir>
python tools/art/render_fingerprint.py check --trace <набор>/bench.trace.log --shot <png>   # на эталоне (exit 0)
```

Скрипты замеров (вне git, `C:/tmp/envmaps-research/p7/tune/`):
- `run_bench.py` — прогон с локом GPU;
- `cmp_concept.py` — кадр против концепта и моков;
- `selfcal.py` — кривая тонмаппера по кадру C0;
- `de_plate.py` — ΔE кадр — плита;
- `details_crops.py`, `cmp_ref.py`, `make_evidence.py`;
- из P5c: `C:/tmp/envmaps-research/p5c/tune/measure.py`, `zone_precise.py`.

## Ограничения и открытые вопросы

- **Огни — стилизованные спрайты.**
  - На C0 и K1 `NS_Env_ConceptFire` читается как оранжевое пятно с жёлтым ядром, а не как нарисованные языки пламени.
    В игре оно анимируется, в бенче заморожено.
  - **В packaged-клиенте второй огонь (`fire-brazier`) не виден**, хотя трасса пишет `particles=73`. Это не новая
    проблема: в packaged-кадрах P6 точно так же нет второго костра P5c `campfire-w`, а в кадрах редактора оба есть.
  - Проба: перенос огня на 30 uu к камере вдоль луча C0 не помог, она откачена (параметр `towardC0UU` остался в
    `cp_layout.py`, по умолчанию 0).
  - Нужен отдельный разбор Niagara в куке.
- **Точность против концепта** ограничена плитой ×2 (imagegen): SSIM плиты к концепту 0,38. Сам конвейер воспроизводит
  плиту с SSIM 0,84 и ΔE 0,8. Если нужна ближе к концепту фактура, можно взять плиту без ×2 (чистую 1672×941) и потерять
  резкость на K2. Это решение пользователя.
- **Окружение / карта на K1 = 0,396** против мока 0,355: свечение от карты и огней. На ровных участках кадр равен плите.
- Компенсация виньетки (0,4) жёстко рассчитана на её значение по умолчанию. Если пост-обработка поменяет интенсивность
  виньетки, нужно поменять `grade.devignette`. Крайние углы (r > 1) остаются на 5–7 % темнее плиты.
- Знамя статичное: у `MI_Env_Banner` нет ветра (WPO). Пушки бронзовые, а на рисунке они тёмный чугун. Огоньки внутри
  фонарей едва видны; свет даёт стекло.
- Растяжение у рамы: полоса нарисованной рамы шире frame-002 и залита растяжкой земли. Около огня форта и столбов
  переднего обрыва содержимое вытянуто до ~1,5×. Чище была бы imagegen-перерисовка полосы, но на неё нужно согласие
  пользователя.
- Marmoreal с флагом — только для сравнения. Сырой концепт, нарисованные лампы плюс свет раскладки, окружение / карта
  0,64 против принятых 0,557. Кадр по умолчанию не изменился.
- Калибровочная карта `-ConceptPasteCalib` и `--lut-from-calib` остались в коде трека B как инструмент, но для финала не
  использовались (см. п. 1 настройки).
- Вне git (ENV-U3/U7):
  - текстуры вклейки (`scraped-data/derived/concept-paste/`);
  - Content (`/Game/EnvMaps/*/ConceptPaste`, `/Game/EnvKit/ConceptPaste`, `NS_Env_ConceptFire`);
  - монтажи с концептом и моками;
  - сырые прогоны.
- Художественная приёмка (сцена, детали, огонь, яркость окружения) — за пользователем.
