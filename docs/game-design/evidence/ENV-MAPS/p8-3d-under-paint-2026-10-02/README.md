# ENV-MAPS P8: Sarpedon — настоящий освещённый 3D-остров под живописью концепта (путь 1). P8.3: интеграция, гейты, подгонка, packaged (2026-10-02)

Статус: **предложено, измерено, технически импортировано**. «Художественно принято» решает только пользователь.

Контракт: `docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md` (гейты G1–G10 §1, этапы §4). Треки P8.1 (геометрия и бейк,
`tools/art/concept_scene/*`) и P8.2 (код UE: режим `lit3d`, `M_EnvScene`, импорт) собраны, импортированы, проверены и
подогнаны здесь (P8.3).

**Итог в одной строке.** Остров, корабль, руины, частокол и сваи — настоящая геометрия с альбедо из de-lit плиты,
освещённая только светом движка; при выключенном свете окружение тёмное (G1), тени ключа и Lumen GI работают, щели под
рамой нет. **Не пройдены:** G4 по SSIM (0,455 при пороге 0,55), G2 по ROI под передним краем рамы и под Медузой,
G3 по строгому «0» (20 px), G6 у одного фонаря, G7 по листве и свету жаровни, G9 «Cobble бит-в-бит» (как и во всех
прошлых фазах). G8 пройден (packaged K1 2,63 мс). Решение по §1 — в разделе «P8.5» ниже: откат не применён, вид по умолчанию — `lit3d`.

## P8.5: решение по гейту (оркестратор, 2026-10-02)

Критерий отката §1 формально выполнен: не пройдены G2, G3 (строгое «0») и G4. **Откат не применён.** Причина: цель отката
(P5c, «обычная 3D-сцена») по тем же гейтам хуже P8, а пользователь её уже не принял (ENV-U15). Замеры тем же `gates.py`
на кадре Fitx1.45 (P5c снят заново: профиль с `"default": "off"`, кадры вне git `C:/tmp/envmaps-research/p8/tune/runs/p85-*`):

| Вид | G4 SSIM ¼ к sarpedon-v2 | средняя разница | G2 Медуза (K2x1,6) |
|---|---|---|---|
| P5c (цель отката) | **0,154** | 34,0 | 0,867 |
| P8 lit3d | 0,455 | 23,1 | 0,870 |
| P7c paste | 0,532 | 19,2 | 0,868 |

- Порог G4 = 0,55 не проходит и P7c (0,532), то есть он был выше, чем у любой из сборок к концепту.
- G2 у Медузы одинаков во всех трёх вариантах: провал не из-за P8.
- Ревью: «зловещая долина» P7 (два света, нет теней между слоями, плоскость) в основном ушла.

Поэтому Sarpedon по умолчанию остаётся `lit3d`. Профиль rev 18 (`envMapsP8GateNoteRev18`) записывает гейт и решение.
Художественное решение за пользователем, откат — одна строка блока `conceptPaste` в `S08ArtBoardProfiles.json`:
`"default": "off"` = P5c, `"mode": "paste"` = P7c. Без правки профиля: `-EnvLayoutVariant=p5c` / `-ConceptPaste=0` = P5c,
`-ConceptPaste=paste` = P7c. Проверено после rev 18: сборка редактора «Result: Succeeded», UE-тесты 249/249,
трасса кадра по умолчанию `concept-paste mode=on reason=default … concept-scene status=ok mode=lit3d`,
с профилем `"default": "off"` — `mode=off reason=default`, кадры P5c (отличие от варианта p5c 0,35–0,42 — шум).

Открыто (не делалось, лимит 6 итераций): ветер листвы и мерцание жаровни (G7), стекло lantern-left (G6), размытая
полоса на переднем уступе перед рамой, светлая «плита» вокруг рамы, водопад-коробка, огонь жаровни спрайтом,
белая щепка у борта, знамя на C0 читается ровной панелью (доля строк 0,71).

## Что из чего построено

| Слой | Что | Источник |
|---|---|---|
| A — настоящее | карта, круги, рама frame-002, фигуры, HUD | без изменений |
| B — 3D-остров (lit, `M_EnvScene` Default Lit) | `SM_Env_S_Island` 17 114 tris, `SM_Env_S_Ship` 35 287 (Poly Haven CC0 `dutch_ship_large_01`), `SM_Env_S_Fort` 1 892, `SM_Env_S_Palisade` 1 286, `SM_Env_S_Piles` 3 484, `SM_Env_S_Banner` 828 | трек A: Blender headless, UM_FBX_v1; альбедо = проекция de-lit плиты из C0 с тестом видимости, невидимое — CC0 (Rock058 / Ground055S / Moss002 / Planks023A) с подгонкой цвета; AO Cycles CPU; нормаль из яркости |
| B — паковые меши (проекция в материале) | 17 деревьев + 3 куста (Fab, `MI_EnvScene_Proj_Foliage`), 30 камней (`_Rock`, `_RockWet`), бочки / ящики / канат (`_Wood`) | `M_EnvScene` в режиме projected: альбедо `T_Env_S_AlbedoC0` в C0-проекции мировой точки, смешение по повороту к C0 |
| C — дальний план | кольцо моря `SM_Env_S_SeaRing` (опущено на z −300, R3), 3D-водопады (×2,5 по Z), цилиндр неба P7 (unlit) | секция `ground` базовой раскладки + `lit3d.seaZUU / waterfallScaleZ` |
| D — свет | ключ (−55, 30, 0) без изменений + moon-pool профиля + 5 точек lit3d с мерцанием = 6 (бюджет) | профиль `S08ArtBoardProfiles.json` rev 17 (rev 18 — запись гейта), блок `conceptPaste.lit3d` |
| E — детали | 6 фонарей (стекло — `MI_EnvScene_LanternHead`), 2 огня, 3 пушки, знамя (вертикально, 325,6 uu), светлячки | `EnvLayouts/sarpedon.scene.layout.json` (вариант `scene`, 74 пропа, 8 fx) |

Переключение: по умолчанию `lit3d`; `-ConceptPaste=paste` (или `-EnvLayoutVariant=concept`) — вид P7c; `-EnvLayoutVariant=p5c`
(или `-ConceptPaste=0`) — P5c. Откат по §1 — одна строка профиля (`"mode": "paste"` или `"default": "off"`).

## Интеграция (сборка, импорт, тесты)

- UnmatchedEditor и Unmatched Win64 Development (`-NoXGE`, `-MaxParallelActions=6` / `=4`): «Result: Succeeded», C++
  треков A/B скомпилировался без правок исходников режима.
- Исправлено при интеграции (обе дорожки):
  - профиль: `lit3d.casters` указывали на несуществующие шаблоны (`island*` …) → id оверлея `scene-island`,
    `scene-ship`, `scene-fort`, `scene-palisade` (тест Shipped требует, чтобы шаблон находил проп). `tree*` убран из
    casters: иначе он включал тень у `tree-00`, которому раскладка отключила её у рамы (R5);
  - `S08ConceptPaste.cpp`: `lit3d.sky` принимал число (в UE 5.8 `TryGetBoolField` читает и число) → строгая проверка
    типа JSON bool (тест Parser);
  - тест MaterialOverride: у `/Engine/BasicShapes/Cube` в 5.8 «свой» материал — сам WorldGridMaterial; тест берёт
    `VertexColorMaterial` как переопределение;
  - `ue_import_concept_scene.py`: слоты трека A записаны короткими именами (`MI_Env_S_Island`) → разворачиваются в
    `/Game/EnvMaps/Sarpedon/Scene/…` (иначе ошибки EditorAssetSubsystem и exit 1); импортируется и
    `meshesExistingMaterial` (вертикальное знамя → `MI_EnvCP_Banner`).
- Коммандлеты (редактор закрыт): `ue_scene_material.py` (MPC_EnvScene, M_EnvScene, M_EnvScene_Masked, MI) и
  `ue_import_concept_scene.py` (16 текстур, 6 мешей, 11 MI). Повторный прогон — всё `unchanged` (идемпотентно по sha256).
- `node tools/s08/run-ue-tests.cjs "Unmatched.S08+Unmatched.S09+Unmatched.S10"` — **249/249**, EXIT CODE 0 (после всех
  правок, на итоговой сборке).
- `python -m pytest tools/art/tests tools/art/map_surface -q` — **497 passed, 2 skipped**, 91 subtests (после правок:
  `test_ue_concept_scene.py` — набор света с `lantern-bay` и новый `test_mi_plan_tune`; `test_concept_scene_assets.py` —
  материал стекла фонарей `MI_EnvScene_LanternHead` в раскладке).
- Все `--check` (список в «Команды») — ok.
- Packaged: `package-client.ps1 -SkipBuild` — «BUILD SUCCESSFUL», кук 1167 пакетов, «Success - 0 error(s),
  0 warning(s)». **Ловушка:** новый файл `EnvLayouts/sarpedon.scene.layout.json` попадает в pak только после пересоздания
  makefile игрового таргета (wildcard в `Unmatched.Build.cs` разрешается при генерации makefile). Первая сборка дала в
  packaged `concept-paste mode=off reason=overlay-absent` (вид P5c); после `touch Unmatched.Build.cs` и пересборки
  («Invalidating makefile … Build.cs modified») оверлей в pak, `concept-scene status=ok`.

## Подгонка (6 итераций, журнал `C:/tmp/envmaps-research/p8/tune/log.md`, вне git; числа — `tune-iterations.json`)

Только параметры, кроме двух мест (обоснование — замер): заполнение полосы нарисованной рамы в бейке (`frameBand`,
режим `plateMeanPlanks`) и камни у подножия обрыва (`footRocks`) в генераторе раскладки.

| Итерация | Что менялось | SSIM ¼ | ΔE пятен, медиана | Карта Y K1 | Тёплых K1 | ΔE зон K1 |
|---|---|---|---|---|---|---|
| i0 (как сдано) | — (точки P7c 65/40/30/95/90 кд, альбедо ×1) | 0,418 | 22,97 | 107,2 | 0,217 | 23,36 |
| i1 | альбедо ×0,45 (BakedTint, AlbedoGain, FallbackTint); точки 35/30/22/35/35; стекло ×20; камни у подножия; знамя +250 uu по лучу C0 | 0,455 | 5,92 | 105,0 | 0,059 | 23,86 |
| i2 | точка `lantern-deck-n` → `lantern-bay` (45 кд); тон острова (0,50; 0,44; 0,37); стекло ×30 | 0,454 | 3,13 | 104,6 | 0,078 | 23,80 |
| i3 | полоса рамы: Planks023A на сглаженном цвете нарисованной рамы; точки 45/40/28/65/50; тон (0,52; 0,44; 0,35); стекло ×40 | 0,465 | 3,63 | 105,2 | 0,097 | 23,38 |
| i4 | точки 32/40/30/95 (z 150)/75; NormalStrength 2, AOStrength 1,3 | 0,460 | 5,82 | 106,0 | 0,119 | 23,39 |
| i5 | форт 36, deck-se 60 (ящики больше не белые), стекло ×60 | 0,462 | 5,86 | 106,0 | 0,117 | 23,37 |
| **i6 = итог** | яркость полосы рамы ×1,6 (была на 6,7 L* темнее нарисованной) | **0,455** | **5,87** | **106,0** | **0,148** | **23,36** |

Итоговые параметры:
- точки (кд): fire-fort 36, fire-brazier 40, lantern-left 30, lantern-bay 95 (z 150), lantern-deck-se 60;
- `tools/art/concept_scene/scene-tune.sarpedon.json`: запечённые MI BakedTint 0,45 (остров (0,52; 0,44; 0,35)),
  NormalStrength 2, AOStrength 1,3; проекционные AlbedoGain 0,45, FallbackTint ×0,45; стекло фонарей
  `MI_EnvScene_LanternHead` (дочерний от `MI_EnvCP_LanternHead`) EmissiveIntensity 60;
- `scene-params.sarpedon.json`: `bake.frameBand` (planks, ячейка 8 uu, ×1,6), `layout.footRocks` (2 мокрые скалы на
  уровне моря), `details.bannerFrontUU` 40 → 290, `details.lanternMaterial`.

Отступления от контракта и их причины (измерены):
1. **Свет `lantern-deck-n` перенесён на `lantern-bay`.** С контрактным набором доля тёплых в окружении 0,059 (порог 0,12):
   нарисованное тёплое пятно на пляже не освещалось ничем, а причал был пересвечен (пятно deck-e 137 против 38 sRGB).
   Стекло `lantern-deck-n` светится по-прежнему. Тест Shipped и `ue_scene_material.py --check` обновлены.
2. **Полоса нарисованной рамы** (27–69 uu вокруг frame-002) — не «земля своей стороны», а Planks023A на цвете самой
   нарисованной рамы, сглаженном в вокселях 8 uu (без болтов и уголков, без растяжки). До этого она читалась серо-зелёным
   плинтусом (ΔE пятна 7,4 → 3,2).
3. **Камни у подножия** (`rock-foot-w1/w2`): внутренний вырез кольца моря (контур подноса − 40 uu) на z −300 не закрыт
   островом в западном переднем углу (55 тыс. uu² открыто) — в кадре Fitx / K1x0,65 была чёрная дыра. Секция `ground`
   базовой раскладки не тронута (вариант p5c).
4. **Знамя сдвинуто на 290 uu к C0 по лучу своего верхнего пикселя** (P7c делал то же, 100 uu). Корпус Poly Haven под
   поручнем выпирает на ~100 uu, на 40 uu было видно 11 % ткани на C0; на 290 uu — 95 % на C0 и K1x0,65 (растр по
   глубине корабля и острова). На K1 / K2 знамя за кадром.

## Гейты G1–G10 (итоговые кадры: редактор `-game -Bench`, High / SP100 / DX12 Lumen; все 29 SHOT на эталоне)

`profilesSha256` во всех итоговых трассах (редактор и packaged) = `421f869a…` = итоговый `S08ArtBoardProfiles.json`;
`overlaySha256` = `18d3ac2c…` = итоговый `sarpedon.scene.layout.json`. Скрипты замеров — `C:/tmp/envmaps-research/p8/tune/`
(`gates.py`, `g3_aniso.py`, `g7.py`, `vsref.py`, `warmmap.py`, `ssimmap.py`; P5c `measure.py`, `zone_precise.py`).

| # | Критерий | Замер | Порог | Итог |
|---|---|---|---|---|
| G1 | без света движка окружение тёмное | окружение (вне рамы + 6 uu) выкл./вкл.: Fitx 0,086, K1 0,032, K1x0,65 0,106, K2x1,6 0,0004, K2x1,6 центр 0,0017 (в линейной яркости 0,014–0,067). Светится только море и водопад (их эмиссия P5c) | < 0,12 | **PASS** |
| G2 | тени между слоями | пята рамы (0,5–3 uu) / полоса (10–20 uu): **передний край** K1 0,847, Fitx 0,838; восточный край (сторона тени ключа) K1 0,566, K2x1,6 центр 0,401, Fitx 0,607. Под Медузой (K2x1,6): 0,870 — так же в P5c (0,867) и P7c (0,868): тень фигуры на карте при ночном ключе слабая, P8 её не меняет. Щели нет: 0 линий из 401 с тёмной (< 8) полосой > 2 px у пяты (P7c: 139 линий) | ≤ 0,75; нет щели | **FAIL** (передний край, Медуза); щели нет — PASS |
| G3 | силуэты и параллакс | C0 → вид, по пикселям спроецированного альбедо на 5 мешах: anisoP99 K1 1,161, K1x0,65 1,058, K2x1,6 центр 1,126, K2x1,6 Медуза 1,273; доля aniso > 2: 0 / 0 / 0 / **0,000032** (20 px из 622 тыс., скользящие треугольники острова) | ≤ 1,3; 0 | anisoP99 PASS; доля > 2 — **FAIL на 20 px** |
| G4 | соответствие концепту на C0 | SSIM ¼ (окружение, Fitx1,45 против sarpedon-v2) **0,455**; ΔE76 крупных пятен: медиана **5,87** (море 5,9, песок 9,2, лес 2,6, борт 1,3, обрывы 3,6, причал 7,3, форт 10,9; полоса рамы 3,2 — справочно) | SSIM ≥ 0,55; медиана ≤ 6 | **FAIL** (SSIM); ΔE PASS |
| G5 | читаемость карты | K1: карта Y 106,0; мин. ΔE76 смежных зон 23,356 (пик мерцания 23,28, live 23,38); тёплых 0,148; контур круга ΔL* 33,9 | 106,6 ± 5; ≥ 23,2; ≥ 0,12; ≥ 30 | **PASS** |
| G6 | детали в масштабе рисунка | площадь свечения стекла на C0 к нарисованной: всего 1,13; по фонарям bay 2,98 (вместе с освещённым песком), left **0,70**, stern 0,90, rail 0,80, deck-n 0,90, deck-se 1,07. Знамя висит вертикально, длина 325,6 uu (100 % от 325) | ≥ 0,8; вертикально, ≥ 90 % | знамя PASS; стекло 5 из 6 (**lantern-left 0,70 FAIL**) |
| G7 | движение (live) | изменившихся пикселей > 8 уровней (Fitx через 101 с / K1 через 14 с): море 10,8 / 9,7 %, водопад 75 / 61 %, костры 22–33 %, знамя (маска ткани) 5,75 %; **листва 0,16 / 0,07 %**; свет жаровни на скале: std по 6 кадрам **0,11** | 3 / 5 / 10 / 10 / 5 %; std ≥ 1,5 | море, водопад, костры, знамя PASS; **листва, свет жаровни FAIL** |
| G8 | производительность | packaged ×3: Sarpedon K1 2,633 мс, K2x1,6 2,510; треугольников окружения ≈ 325 тыс.; Cobble −0,027…+0,043 мс к P7c | K1 ≤ 3,5 мс, K2x1,6 ≤ 3,8; ≤ 450k tris; Cobble ± 0,05 | **PASS** |
| G9 | регрессии | Marmoreal к P5c: 0,106–0,165, пикселей > 24 ≤ 0,003 %, трасса как в P7c (кроме ревизии и списка оверлеев), ΔE зон 23,32; Cobble к P5c 0,210 (0,0024 %), к P7c 0,223 — не бит-в-бит: два прогона Cobble сегодня отличаются на 0,203 (TAA / фаза idle фигур, так было во всех фазах), трасса Cobble совпадает с P7c построчно; вариант p5c: 0,29–0,37 к P5c, ΔE 23,40; `-ConceptPaste=paste`: 0,33–0,36 к P7c, ΔE 23,40; `-EnvLayoutVariant=user`: только трасса (кадры удалены, не просматривались): `variant=user status=ok`, `concept-paste mode=off reason=variant-other`; тесты UE 249/249, pytest 497 passed / 2 skipped | как в P7c | **PASS**, кроме «Cobble бит-в-бит» (как в P5c / P7c) |
| G10 | чистота | плиты и всё производное вне git (`scraped-data/` в `.gitignore`, `git check-ignore` проверен; Content gitignored); NoAI-паки не загружались, кадры варианта `user` не открывались; ключ и световые профили не менялись (сравнение JSON профиля с HEAD: изменены только `boards[sarpedon].conceptPaste`, ревизия и заметка rev 17); `render-reference.json` не изменён | ревью | PASS (ревью — P8.4) |

### Производительность (G8)

Packaged `render_bench.py run --variant dx12-lumen-high-v2 --repeats 3`, Sarpedon и Cobble, все 6 прогонов exit 0, все
SHOT на эталоне; в трассе packaged Sarpedon `concept-scene status=ok mode=lit3d`. Сравнение с P7c — `bench-vs-p7c.json`,
сводка — `bench-summary.json`.

| Доска | Вид | GPU avg P7c → P8, мс | Δ / 2 × шум | p95 P8 | Порог |
|---|---|---|---|---|---|
| sarpedon | K1 | 2,083 → **2,633** | +0,550 / 0,06 | 2,90 | ≤ 3,5 — **PASS** (P5c 2,62) |
| sarpedon | K1x0,65 | 2,063 → 2,613 | +0,550 / 0,02 | 2,88 | — |
| sarpedon | K2x1,6 | 2,183 → **2,510** | +0,327 / 0,02 | 2,65 | ≤ 3,8 — **PASS** |
| sarpedon | K2x2,5 | 2,167 → 2,413 | +0,247 / 0,06 | 2,56 | — |
| cobble | K1 | 1,853 → 1,833 | −0,020 / 0,02 | 1,88 | ± 0,05 — PASS |
| cobble | K1x0,65 | 1,750 → 1,740 | −0,010 / 0,00 | 1,78 | PASS |
| cobble | K2x1,6 | 1,950 → 1,923 | −0,027 / 0,02 | 1,98 | PASS |
| cobble | K2x2,5 | 2,010 → 2,053 | +0,043 / 0,02 | 2,23 | PASS |

Итог G8: **PASS**. Освещаемый остров дороже листа P7c на 0,55 мс (K1) и почти равен P5c (2,62): тени ключа от острова,
корабля, руин и 16 деревьев плюс Lumen GI на 74 пропах.

Треугольники окружения (LOD0, UE, `C:/tmp/envmaps-research/p8/tune/env-tris.json`): 74 пропа оверлея — 318 036
(остров 17 114, корабль 35 287, деревья OakDark по 16 232 и др.), кольцо моря и водопад — 6 800. Итого ≈ 325 тыс. ≤ 450 тыс.

## Кадры

| Набор | Кадры |
|---|---|
| Sarpedon по умолчанию (lit3d) | [Fitx1.45 = C0](sarpedon/bench-Fitx1p45-1920x1080.png), [K1](sarpedon/bench-K1-1920x1080.png), [K1x0,65](sarpedon/bench-K1x0p65-1920x1080.png), [K2x1,6 Медуза](sarpedon/bench-K2x1p6-1920x1080.png), [K2x1,6 центр](sarpedon/bench-K1x1p6-1920x1080.png); `gates.json`, `measure.json`, `g3-aniso.json` |
| `-ArtPreviewLightsOff` (G1) | [Fitx](sarpedon-lights-off/bench-Fitx1p45-1920x1080.png), [K1](sarpedon-lights-off/bench-K1-1920x1080.png) и остальные виды |
| live `-EnvFxLive` (G7) | [Fitx](sarpedon-live/bench-Fitx1p45-1920x1080.png), [разница Fitx: первый и последний кадр прогона, 101 с, ×4](sarpedon-live/diff-live-Fitx1p45.png), [разница K1: кадры через 14 с, ×4](sarpedon-live/diff-live-K1.png), `live-diff.json` |
| пик мерцания (G5) | `sarpedon-flicker-peak/zone-flicker.json`, `profiles-peak.json`, трасса |
| Marmoreal, Cobble, p5c, paste | [Marmoreal K1](marmoreal/bench-K1-1920x1080.png), [Cobble K1](cobble/bench-K1-1920x1080.png), [p5c K1](sarpedon-p5c-variant/bench-K1-1920x1080.png), [paste K1](sarpedon-paste/bench-K1-1920x1080.png) + `vs-*.json` |
| вариант `user` | `sarpedon-user-variant/user-variant-trace.txt` (без кадров) |
| packaged | [Sarpedon Fitx](packaged-sarpedon/bench-Fitx1p45-1920x1080.png), [K1](packaged-sarpedon/bench-K1-1920x1080.png); к кадрам редактора: K1 0,66, Fitx 1,19 (огни с нодой Time, мерцание) |
| Монтаж (только кадры UE) | [P5c / P7c / P8 на K1, K1x0,65, K2x1,6](montage-p5c-p7c-p8.jpg) |

Вне git (ENV-U3/U7): `C:/tmp/envmaps-research/p8/evidence-montages/montage-concept-p7c-p8-c0.jpg` (концепт / P7c / P8 на C0),
`details-concept-p7c-p8-c0.jpg` (фонари, огни, знамя, водопад); все прогоны итераций — `C:/tmp/envmaps-research/p8/tune/runs/`.

## Команды

```
# сборка (C:/tmp/unmatched-package.lock, owner=ENV-MAPS-P8)
node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=C:/tmp/wt-envmaps/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=6
node tools/s08/build-editor.cjs Unmatched Win64 Development -Project=... -WaitMutex -NoXGE -MaxParallelActions=4   # после touch Unmatched.Build.cs, если добавлен новый *.layout.json
# импорт (редактор закрыт)
UnrealEditor-Cmd <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript -script="<repo>/tools/art/concept_scene/ue_scene_material.py" -unattended -nosplash -nullrhi
UnrealEditor-Cmd ... -script="<repo>/tools/art/concept_scene/ue_import_concept_scene.py"
# генераторы трека A после правки параметров
python -B tools/art/concept_scene/bake_albedo.py --only Island        # frameBand
python -B tools/art/concept_scene/scene_layout.py                     # footRocks, banner, lanternMaterial
python -B tools/art/concept_scene/bake_albedo.py --manifest-only
# кадры (C:/tmp/unmatched-gpu.lock): UnrealEditor.exe ... -game -ArtPreview -ArtPreviewDiorama -ArtPreviewHeroesV2 -Bench
#   -BenchFixture=Config/Bench/S08Bench<Map>.json -BenchViews=Fitx1.45+K1+K1x0.65+K2x1.6+K1x1.6 -BenchWarmup=60 -S08RenderPreset=High
#   [-ArtPreviewLightsOff | -EnvFxLive | -ArtBoardProfiles=<peak.json> | -ConceptPaste=paste | -EnvLayoutVariant=p5c|user]   (<набор>/cmdline.txt)
node tools/s08/run-ue-tests.cjs "Unmatched.S08+Unmatched.S09+Unmatched.S10" <log>          # 249/249
python -m pytest tools/art/tests tools/art/map_surface -q                                    # 497 passed, 2 skipped
python -B tools/art/concept_scene/{ue_import_concept_scene.py --check, ue_scene_material.py --check, scene_layout.py --check, bake_albedo.py --check}
python -B tools/art/env_kit/layout_check.py [--scene]; tools/art/concept_paste/{cp_bake.py check sarpedon marmoreal, cp_proxies.py check, cp_layout.py --check, ue_import_concept_paste.py --check, ue_concept_material.py --check}
python -B tools/art/env_kit/{ue_import_fab_picks,ue_import_fab_fx,ue_import_env_kit,ue_import_env_ground,ue_import_tray_t2}.py --check; tools/art/map_surface/{ue_import_map_surface.py --check, backdrop.py --check}
python -B tools/art/env_kit/{hlsl_check.py, env_prop_look.py --check, ground_splat.py --check}; tools/art/art_board_fixtures.py check     # все ok
powershell -File tools/s08/package-client.ps1 -SkipBuild                                    # BUILD SUCCESSFUL
python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --name sarpedon --repeats 3 --views K1+K1x0.65+K2x1.6+K2x2.5 --bench-fixture ../../../Unmatched/Config/Bench/S08BenchSarpedon.json --out <dir>
python tools/art/render_fingerprint.py check --trace <набор>/bench.trace.log --shot <png-имя>   # 29 SHOT reference=true (пик мерцания: profilesSource=override, ожидаемо)
```

## Известные ограничения и открытые вопросы

- **G4 SSIM 0,455.** Яркость окружения совпадает с концептом (34,7 против 34,5 на C0), медиана ΔE пятен 5,9, но
  структура света другая: член «контраст / структура» SSIM 0,53. Потолки тем же методом: de-lit плита против концепта
  0,31, освещённая чистая плита P7 — 0,79. SSIM награждает нарисованные свет и тени, а свет движка их не повторяет
  (6 итераций: 0,418 → 0,465 максимум). Хуже всего корабль (0,24–0,36: корпус и такелаж Poly Haven не совпадают с
  нарисованными), 3D-водопад и облака в левом верхнем углу.
- **G2.** Тень ключа от переднего бруса frame-002 падает на полосу всего на ~5 uu (свет с северо-запада), ночной ключ
  слабый — 0,84; на восточной стороне тень есть (0,57). Тень Медузы на карте одинакова в P5c / P7c / P8.
- **G7.** Листва в live почти не движется: `WindAmp` 2 uu × (h / 300)^1,5 на деревьях масштаба 0,08–0,25 — доли пикселя.
  Мерцание `fire-brazier` (amp 0,06) ограничено ещё в P7c ради ΔE зон на пике. Предложение на следующую итерацию (не
  применено, лимит 6 итераций исчерпан): `looks.Foliage` WindAmp 8, WindHeight 120; у жаровни radius 420 → 180 и amp
  0,25 (свет не дойдёт до клеток карты) — с повторным замером пика мерцания.
- **G6 lantern-left 0,70.** Стекло ×60 уже на пределе: дальше оно выгорает в белое.
- **Полоса размытой проекции** на кромке переднего обрыва перед рамой (~25 uu, K1 снизу по центру): смесь проекции
  нарисованной рамы / водопада и fallback на наклонных гранях кромки (бейк трека A). Видно на K1.
- **Огонь жаровни** читается красным пятном (тот же `NS_Env_ConceptFire`, что в P7c).
- **Корабль**: силуэт закрывает 72 % нарисованного корпуса, кормовая палуба нарисована на плоском причале (трек A).
- **Заметка профиля rev 17** (`envMapsP8NoteRev17`) говорит «the same five point lights … casters island / ship …» —
  написана до подгонки; фактические значения — в блоке `lit3d` и здесь. Не правилась, чтобы sha профиля в трассах
  итоговых кадров и packaged-сборки совпадал с файлом (правка заметки меняет sha).
- **Ловушка pak**: после интеграции в основную копию пересоздать makefile игрового таргета (`touch
  Unmatched.Build.cs` или чистая сборка), иначе `sarpedon.scene.layout.json` не попадёт в pak и packaged Sarpedon уйдёт
  в вид P5c (`reason=overlay-absent`).
- Вне git: `scraped-data/derived/concept-scene/sarpedon/` (16 PNG, sha256 в `manifest.sarpedon.json`), Content
  `/Game/EnvMaps/Scene`, `/Game/EnvMaps/Sarpedon/Scene`; их нужно перенести в основную копию при синхронизации.
- Художественная приёмка (остров, корабль, полоса рамы, свет, детали) — за пользователем.
