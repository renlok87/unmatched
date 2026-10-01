# ENV-MAPS P5c: деревья, декор, VFX и вода из паков Fab на диорамах Marmoreal и Sarpedon — настройка и финальные кадры (2026-10-01)

Статус: **предложено, измерено, технически импортировано**. Художественная приёмка — только решение пользователя.

## Как сняты кадры

Кадры сняты в редакторе в игровом режиме: `UnrealEditor.exe -game -Bench`, некукнутый контент worktree `C:/tmp/wt-envmaps`, ветка `feat/env-original-maps`. Бэкенд не запускался. Настройки: High, SP 100, DX12/SM6 + Lumen.

Все 9 кадров на эталоне рендера. `tools/art/render_fingerprint.py check` для каждого SHOT вернул код 0, `reference: true`, `reasons: []` (`render-fingerprint.json`, `<map>/render-fingerprint.json`). `profilesSha256` в трассах равен sha256 итогового `S08ArtBoardProfiles.json` (rev 14): `f7e257ee…`.

Это кадры редактора, а не packaged-сборки (см. «Пробелы»).

## Ограничения, которые соблюдены

- Только вариант раскладки по умолчанию (`envlayout variant=none`). Паки NoAI (`Megaplant_Library`, `StyleHex_Studio`) в основной раскладке и в кадрах отсутствуют; их текстуры, превью и кадры не открывались.
- Ключевой свет (−55, 30, 0) не менялся (ENV-U12). Бюджет света: 1 ключ + 5 точек раскладки + 1 точка профиля = 6 на карту (`combinedBudgetOk=1`). Новых источников нет; у Niagara нет световых рендереров (`skippedLightRenderer=0`, у всех систем свет отключён при импорте).
- Платных шагов (Tripo, SYNTX, Fab/Epic) не было. Новых загрузок не было.
- Паки в `Content/<Pack>/` не изменялись. Всё производное лежит в `/Game/EnvKit/Fab/…` и `/Game/EnvKit/FX/…`.
- Глубина юбки подноса, ширина рамы и камера K1 не менялись (ENV-U14: отложено до приёмки).

## Кадры

| Карта | K1 (2340 uu) | 0,65× (дальний предел) | 1,6× на Medusa | 2,5× крупно |
|---|---|---|---|---|
| Marmoreal | [K1](marmoreal/bench-K1-1920x1080.png) | [0,65×](marmoreal/bench-K1x0p65-1920x1080.png) | [K2×1,6](marmoreal/bench-K2x1p6-1920x1080.png) | [K2×2,5](marmoreal/bench-K2x2p5-1920x1080.png) |
| Sarpedon | [K1](sarpedon/bench-K1-1920x1080.png) | [0,65×](sarpedon/bench-K1x0p65-1920x1080.png) | [K2×1,6](sarpedon/bench-K2x1p6-1920x1080.png) | [K2×2,5](sarpedon/bench-K2x2p5-1920x1080.png) |
| Cobble (регрессия) | [K1](cobble/bench-K1-1920x1080.png) | – | – | – |

- [montage-p5b-vs-p5c.jpg](montage-p5b-vs-p5c.jpg) — до и после. Слева финал P5b, справа финал P5c; K1 и 0,65× обеих карт.
- [details-before-after.jpg](details-before-after.jpg) — крупные планы, P5b против P5c:
  - вишни W;
  - задняя стена и верхняя полоса K1;
  - луна;
  - цветы у клумбы W;
  - лес и костёр Sarpedon, куст и костёр на K2×1,6;
  - море, пена и водопад;
  - палуба.

## Что пришло из какого пака Fab

Реестр и лицензии — `docs/art-pipeline/CREDITS-fab.md`. Все паки «только для личного и локального использования» (ENV-U13). В git ничего из паков не попадает: ни меши, ни текстуры. В git идут только кадры.

| Пак (папка) | Издатель, лицензия | Что в P5c | Производные ассеты |
|---|---|---|---|
| Stylized Environment - Forest (`StylizedForest`) | SilverSet Studios, Fab Standard «Личное» | 4 розовых дерева вместо вишен Marmoreal (Twisted ×2, Birch Thin ×2); 3 тёмных дуба и 2 куста на Sarpedon | `SM_EnvFab_Sakura{Twisted,Birch}`, `SM_EnvFab_OakDark`, `SM_EnvFab_Bush`; обёртки листвы `M_EnvFab_{PinkLeaves,DarkGreenLeaves,FlowerBush}` + ночные MI |
| Fantasy_Forest (`Fantasy_Forest`) | Gairisa, Fab Standard «Личное» | 5 деревьев леса Sarpedon, 2 тёмных мокрых камня | `SM_EnvFab_Forest{Narrow,Round,Small}`, `SM_EnvFab_RockWet`, `MI_EnvFab_ForestNight`, `MI_EnvFab_RockWet` |
| Vine_Plants (`Vine_Plants`) | Gairisa, Fab Standard «Личное» | 13 лиан на задней стене и аркаде Marmoreal, 7 на частоколе и руине форта Sarpedon | `SM_EnvFab_Vine*`, `MI_EnvFab_Vine0{1,2,3}Night` (двусторонние) |
| Stylized Flowers Pots (`Flowers_Pots`) | Gairisa, Fab Standard «Личное» | 2 букета в вазонах, 6 кустов у клумб, 2 лаванды у боковых фонарей | `SM_EnvFab_Flower{Urn,Bed,BedB,Lavender}`, `M_EnvFab_Jug`, `MI_EnvFab_FlowersNight`, `MI_EnvFab_LavenderNight` |
| Stylish Fire VFX (`Stylish_Fire_VFX`) | VfxSTOCK, Fab Standard «Личное» | огонь двух костров Sarpedon, пламя в 7 фонарях | `NS_Env_Campfire`, `NS_Env_LanternFlame` |
| Free Niagara Particles (`FreeParticle_SoftTofu`) | SoftTofuVFX, **CC BY 4.0** | лепестки под 4 вишнями, светлячки (2 группы в саду Marmoreal, 3 на Sarpedon) | `NS_Env_CherryPetals`, `NS_Env_Fireflies` (CPU, детерминированные) |
| Water Materials (`WaterMaterials`) | tharlevfx, **CC BY 4.0** | текстуры пены и нормалей моря и водопада Sarpedon | `M_EnvSea` graph 2, `M_EnvWaterfall` graph 3 (жёсткие ссылки на `T_Ocean_Foam`, `T_Water_Normal`, `T_Water_Normal_Large`, `T_Waterfall_Foam`) |

Particles and Wind Control System не используется: эффекты там Cascade, а Blueprint-ы добавляют точечный свет.

### Атрибуция CC BY 4.0

- «Free Niagara Particles» © SoftTofuVFX, CC BY 4.0, https://www.fab.com/listings/183732bc-c2fb-465c-9453-f70a1ce7ba2c — используется с изменениями (CPU-симуляция, размер, цвет и частота под ночную сцену).
- «Water Materials» © tharlevfx, CC BY 4.0, https://www.fab.com/listings/063155ea-d9d2-4f29-b09f-33270b0bc861 — используется с изменениями (текстуры пака в наших материалах моря и водопада).

## Пробелы ревью P5b и что с ними сделано

Треки F (пропсы Fab), V (VFX и варианты раскладки) и W (вода, мох, луна) и интеграция описаны в своих отчётах:
- `art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/README-track-F.md`;
- `art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/README-fx.md`;
- `tools/art/env_kit/README.md`.

Tune прошёл 4 итерации (t0–t3) и два финальных прогона. Лог: `C:/tmp/envmaps-research/p5c/tune/log.md`, вне git.

| Пробел | После интеграции (i1) | Что сделал Tune | Замер (P5b → i1 → **P5c**) |
|---|---|---|---|
| Marmoreal: задняя стена ярче карты | средняя 103,4, окна плоские, насыщенные | камень ×0,86 → **×0,52**, яркие тексели ×0,7 → ×0,45, свечение ×2,1 → **×1,2** (`env-prop-look.json` P5) | средняя яркость стены K1: 121,1 → 103,4 → **88,7** (цель < ~105); верхняя полоса K1 (строки 0–60): 138,6 → 113,8 → **96,0** (P4 91,9); перегоревшие пиксели стены 7,4 % → 6,7 % → **6,7 %** — теперь это центральная дверь и ступени под светом `portal-glow`, окна больше не перегорают |
| Marmoreal: луна — жёсткий плоский диск | мягче, но диск ещё плоский | `discSoftness` 0,5 → **0,9**, `discLimb` 0,5 → **0,9** | яркость на 0 / 0,5 / 1 / 1,5 радиуса диска: 169,7 / 169,4 / 146,2 / 133,2 → 169,2 / 163,8 / 139,6 / 133,1 → **165,0 / 153,2 / 137,8 / 133,1**: край спадает плавно |
| Sarpedon: фон — почти плоский тёмный синий | 17,8, σ 5,05 | море: `sky.intensity` 1,0 → **1,8** (`ground-params.json`) | фон в полосе 60 px у подноса, 0,65×: 12,3 → 17,8 → **20,9** (цель ~20–26, P4 25,5); σ фона 2,15 → 5,05 → **5,2** |
| Sarpedon: у моря нет волн и прибоя, пена — серый туман | волны, линии прибоя, белая пена (трек W) | без изменений | виден прибой у скал и белая кромка пены (details, 0,65×) |
| Sarpedon: нижний водопад — крупные штрихи и жёсткий прямоугольный контур | полупрозрачный, мягкий край | без изменений | доля «водных» пикселей листа 0,94 → 0,967 → **0,971**, нижняя половина 0,998 → **1,0** |
| Sarpedon: жёлто-зелёная линия мха по кромке T2b | MossAmount 0,38 (трек W) | без изменений | доля зелёного (тон 60–140°, S > 0,3) на южной кромке, 0,65×, строки 930–965: **0,266 → 0,0** |
| Sarpedon: фонари у костров, длинные тени, стекло почти не светится | фонари в 195/204 uu от огней, стекло ×7,6 (трек F) | пламя в фонаре ×2,5 по цвету | теней-полос нет (у точечных огней `castShadow=false`); на земле в кольце 20–120 uu вокруг lantern-w / lantern-n p10/p50 = 0,36 / 0,48 |
| Sarpedon: бочки и ящики в одну колонну, коричневое на коричневом | кучки, ящики светлее бочек в 1,47 раза (трек F) | без изменений | группы читаются на K1 (details, палуба) |
| Sarpedon: бледные камни | тёмный мокрый камень (трек F) | без изменений | `MI_EnvFab_RockWet`, Fab-камни K1: средняя яркость в боксе 21 |

## Новые элементы P5c

| Элемент | После интеграции (i1) | Что сделал Tune | Замер (i1 → **P5c**) |
|---|---|---|---|
| Вишни Marmoreal (розовые деревья Forest) | под тёплыми фонарями лососевые и оранжевые | код: `ue_import_fab_picks.py` envfab-2 добавляет вектор `NightTint` после узла `EnvFabNight`. Сакура: V 0,78 → 0,7, `NightTint` (0,85; 0,78; 1,25), ветер `Intensity` / `Weight` 0 | доля розового в кроне (тон > 290° или < 8°): 0,65 → **0,79**; лососевого (8–40°): 0,35 → **0,21**; медиана тона 4,6° → **352°**; яркость кроны / карта 0,56 → **0,49** (не ярче карты) |
| Кусты цветов у клумб W/E (Sm_Flower_019 / 022) | лаймовые «звёзды» | `MI_EnvFab_FlowersNight`: V 0,72 → 0,55, S 0,75 → 0,7, `NightTint` (1,0; 0,72; 0,95) | листья тёмно-оливковые, цветы розово-фиолетовые (details) |
| Лаванда у боковых фонарей | пересвечена: в 36 uu от точечного света | свой `MI_EnvFab_LavenderNight`: V 0,45, S 0,6, фиолетовый оттенок | фиолетовая, без лайма |
| Куст Sarpedon | ярко-лаймовый шар с белыми точками | V 0,7 → 0,35, S 0,8 → 0,55, `NightTint` (0,75; 0,9; 1,0) | доля лайма в боксе 0,098 → **0,0**, медиана тона 62° → 54° |
| Лес Sarpedon | кроны сине-чёрные рядом с рыжими стволами | дуб: V 0,85 → 1,0, `NightTint` (0,95; 1,05; 0,8), ветер 0; Fantasy_Forest: Brightness 0,5 → 0,65, Tint (0,6; 0,8; 0,55) | яркость в боксе: дуб 16,2 → **18,6**, ForestRound 19,8 → **21,4**; лес остаётся тёмным (концепт ~26) |
| Огонь костров | на K2 бледный язычок внутри пятна своего света | k 0,3 → **0,4**, `Color.Scale Color` ×**3** | читается как пламя на углях (K2×1,6) |
| Пламя в фонарях | только ядро свечения | `Color.Scale Color` ×**2,5** | тёплое ядро в стекле |
| Светлячки | спрайт не масштабировался: правило ни с чем не совпало | правило убрано, user-параметр размера 3–6 → **8–14 uu** | редкие тёплые точки; эффект сдержанный |
| Лепестки | — | без изменений | отдельно не замерялись; источник у крон, вне карты (`skippedInsideMap=0`, `nearBand=0`) |

Частиц на карту (строка трассы `envlayout fx`): Marmoreal **317** (10 fx: 4 пламени, 4 облака лепестков, 2 группы светлячков); Sarpedon **316** (8 fx: 2 костра, 3 пламени, 3 группы светлячков). Во всех строках `gpuEmitters=0`, `nonDeterministic=0`, `mode=frozen`.

Треугольники инстансов LOD0 (по `layout_check.py`):

| Карта | P5b | P5c | из них паки Fab |
|---|---|---|---|
| Marmoreal | 275 773 | 278 185 | 42 568 |
| Sarpedon | 249 740 | 264 462 | 77 050 |

## Код и данные, изменённые на этапе Tune

Код (параметра не было):
- `tools/art/env_kit/ue_import_fab_picks.py` (envfab-2) — Custom-узел `EnvFabNightTint`: умножение на вектор `NightTint`, по умолчанию (1, 1, 1). Обёртки envfab-1 обновляются на месте. Без него сакура не уходила из лососевого: обёртка умела только яркость и насыщенность.
- `tools/art/env_kit/ue_import_fab_fx.py` — проверка разрешает множитель до ×6 для правил `*.Color.*`. Для размеров и сил предел прежний, ×2.

Данные:
- `fab-picks.json` — ночные MI, новый `MI_EnvFab_LavenderNight`;
- `ue_import_fab_fx.py` FX_SPECS — огонь, светлячки;
- `env-prop-look.json` P5 — BackWall;
- `ground-params.json` — `sea.sky.intensity` 1,8;
- `S08ArtBoardProfiles.json` (rev 14, заметка `envMapsP5cTuneNoteRev14`):
  - луна `discSoftness` / `discLimb` 0,9 / 0,9;
  - `mapGrade.maskSaturation`: marmoreal-night 1,4 → **1,44**, sarpedon-night 1,05 → **1,07**;
- `tools/art/map_surface/manifest.{marmoreal,sarpedon}.json` — `k1.grade_b_c` обновлён `build_map_textures.py --refresh-k1`, MI карт переимпортированы. Иначе тест `BoardArt.MapAssets` видит MI 1,4 против профиля 1,44.

Почему `maskSaturation`. После замены деревьев, оттенка сакуры и затемнения стены минимальная ΔE76 смежных зон (без округления) упала до 23,16 (Marmoreal, коричневый–красный) и 23,13 (Sarpedon, синий–пурпурный). У P4 было 23,28 / 23,16. +3 % / +2 % хромы внутри маски вернули 23,36 / 23,39. Яркость карты не изменилась.

Тесты:
- `tools/art/tests/test_env_fab_p5c.py` — `NightTint`, куст и цветы, верхняя граница стены;
- `tools/art/tests/test_env_fx_p5c.py` — огонь и светлячки, предел `*.Color.*`;
- `tools/art/tests/test_env_kit_p5.py` — отношение свечения стены к стеклу фонаря: нижняя граница 0,5 → 0,25 (×1,2 вместо ×2,1).

## Замеры (P5b → интеграция → P5c)

Инструменты:
- P4: `measure.py`, `measure_extra.py`, `zone_separation.py`;
- P5b: `measure_p5b.py`, добавлены кольца луны r1 / r1,5;
- новые: `measure_p5c.py` (кроны Fab, верхняя полоса, группы Fab-пропсов, кромка, земля у фонарей) и `zone_precise.py` (ΔE зон без округления).

Скрипты лежат вне git: `C:/tmp/envmaps-research/p5c/tune`. Числа: `measure.json` (сводка) и `<map>/measure.json`, `zones-extra.json`, `p5b-checks.json`, `p5c-checks.json`.

| Метрика (K1, если не указано) | Цель | Marmoreal P5b → i1 → **P5c** | Sarpedon P5b → i1 → **P5c** |
|---|---|---|---|
| Яркость карты Y | 117,8 / 106,6 ± 5 | 117,9 → 117,7 → **117,6** | 106,7 → 106,6 → **106,6** |
| Окружение / карта | 0,59 / 0,45 ± 0,08 | 0,595 → 0,576 → **0,557** | 0,447 → 0,449 → **0,450** |
| Тёплые в окружении | ≥ 0,18 / ≥ 0,12 | 0,22 → 0,247 → **0,213** | 0,139 → 0,144 → **0,145** |
| Мин. смежная ΔE76 зон (округл.; без округления) | ≥ 23,3 / 23,2 | 23,3 (23,34) → 23,2 (23,17) → **23,4 (23,36)** | 23,2 (23,16) → 23,1 (23,10) → **23,4 (23,39)** |
| Хрома зон / оригинал | против «плаката» | 1,24 → 1,24 → **1,25** | 1,10 → 1,09 → **1,11** |
| Контур круга ΔL\*, медиана | ≥ P4 (35,0 / 33,8) | 34,9 → 34,9 → **34,9** | 33,8 → 33,6 → **33,7** |
| Блики у lamp-nw: p50 / p99 / max | без «призраков» | 89,4 / 177,3 / 220,5 → 83,1 / 159,7 / 203,1 → **79,7 / 158,5 / 187,5** | – |
| Вода за рамкой / река (сев., юж.) | без «дыр» | – | ×0,92 / ×0,76 → ×0,92 / ×0,77 → **×0,92 / ×0,77** |
| Фон у краёв подноса, 0,65× | M: не ярче P4 26,5; S: ~20–26 | 21,3 → 21,2 → **21,2** | 12,3 → 17,8 → **20,9** |
| Новые пропсы против кругов и подписей | `layout_check` 0 ERROR / 0 WARN | 64 пропа, OK | 54 пропа, OK |
| Cobble K1 против P5b | без изменений | средняя \|разница\| **0,123**, пикселей > 24 — **0,0008 %**, max 59 (`cobble/cobble-vs-p5b.json`). Трасса Cobble отличается только ревизией профилей (13 → 14) и её sha; строк fx, рамки и фона нет | |

Пояснения к таблице:
- Окружение / карта на Marmoreal снизилось (0,595 → 0,557): задняя стена темнее, сакура приглушена. Значение в коридоре 0,51–0,67.
- Тёплые в окружении на Marmoreal: 0,213. Это ниже i1 (0,247), но выше цели 0,18.

## Детерминизм: два прогона одного дерева

Данные: `determinism.json`, прогоны `final` и `final2`.
- Строки трассы fx одинаковы: частицы заморожены после фиксированного прогрева в тиках 1/30 с.
- Метрики совпадают до 0,1. ΔE зон Marmoreal 23,36 / 23,32.
- Marmoreal: средняя \|разница\| 0,10–0,16, пикселей > 24 не больше 0,0001 %.
  - Первый финальный прогон различался по всей кроне cherry-w. У пака `WPO` и так 0, ветром управляют `Intensity` / `Weight`. После `Intensity 0` / `Weight 0` у MI сакуры и дуба различие ушло.
- Sarpedon: средняя \|разница\| 0,29–0,35, пикселей > 24 — 0,002–0,09 %.
  - Различия только там, где материал анимируется нодой `Time`: пламя костров, вода водопада, линии прибоя.
  - Частицы при этом заморожены. Для попиксельного совпадения нужны бенч-MI с нулевой скоростью (см. «Пробелы»).

## Команды

```
# импорт (редактор закрыт, C:/tmp/unmatched-package.lock)
UnrealEditor-Cmd <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript -script="<repo>/tools/art/env_kit/ue_import_fab_picks.py" -unattended -nosplash -nullrhi   # envfab-2: NightTint, 10 MI
UnrealEditor-Cmd ... -script="<repo>/tools/art/env_kit/ue_import_fab_fx.py"     # перед пересборкой убрать устаревшие Content/EnvKit/FX/NS_Env_<X>.uasset (README-fx.md)
UnrealEditor-Cmd ... -script="<repo>/tools/art/env_kit/ue_import_env_kit.py --maps marmoreal --names BackWall_BayDoor,BackWall_BayWindows,BackWall_Centre"
UnrealEditor-Cmd ... -script="<repo>/tools/art/env_kit/ue_import_env_ground.py --maps sarpedon"   # MI_EnvSea_Sarpedon sky 1.8
python -B tools/art/map_surface/build_map_textures.py --refresh-k1                                # manifest k1.grade_b_c = профиль rev 14
UnrealEditor-Cmd ... -script="<repo>/tools/art/map_surface/ue_import_map_surface.py"            # MI карт: MaskSaturation 1.44 / 1.07
# сборка (-NoXGE -MaxParallelActions=6): UnmatchedEditor и Unmatched Win64 Development — Result: Succeeded
# кадры (C:/tmp/unmatched-gpu.lock, owner=ENV-MAPS-P5C): UnrealEditor.exe ... -game -ArtPreview -ArtPreviewDiorama -ArtPreviewHeroesV2 -Bench
#   -BenchFixture=Config/Bench/S08Bench<Map>.json -BenchViews=K1+K1x0.65+K2x1.6+K2x2.5 -BenchWarmup=60 -S08RenderPreset=High  (<map>/cmdline.txt)
node tools/s08/run-ue-tests.cjs "Unmatched.S08+Unmatched.S09+Unmatched.S10" <log>   # 237/237, EXIT CODE 0
python -m pytest tools/art/tests tools/art/map_surface -q                           # 407 passed, 2 skipped, 91 subtests
python -B tools/art/env_kit/{ue_import_fab_picks,ue_import_fab_fx,ue_import_env_kit,ue_import_env_ground,ue_import_tray_t2}.py --check   # ok
python -B tools/art/map_surface/ue_import_map_surface.py --check; python -B tools/art/map_surface/backdrop.py --check; python -B tools/art/env_kit/hlsl_check.py
python -B tools/art/env_kit/env_prop_look.py --check; python -B tools/art/art_board_fixtures.py check
python -B tools/art/env_kit/ground_splat.py --check; python -B tools/art/env_kit/layout_check.py (--selftest)
python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/{p5c_layout_props,p5c_layout_fx}.py --check
python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5/scripts/p5_layout_props.py --check
python tools/art/render_fingerprint.py check --trace <map>/bench.trace.log --shot <png>      # 9/9 на эталоне
```

## Пробелы и оговорки

- **Не packaged.**
  - Кадры сняты в редакторе. Packaged-сборка и `render_bench.py` не запускались, стоимость рендера не измерена.
  - Не проверено, что кукер подтягивает по жёстким ссылкам из `/Game/EnvKit` ассеты паков (меши, материалы, текстуры Water Materials, Niagara).
  - Прибавка треугольников: +2,4k (Marmoreal) и +14,7k (Sarpedon) против P5b. Около 320 частиц на карту, CPU-симуляция.
- **Окна задней стены без градиента.** Свечение больше не перегорает, но остаётся ровным: у `M_EnvProp` нет UV-члена, а окна в BC залиты одним цветом. Нужна новая функция мастер-материала (градиент по локальной высоте или UV окна) или градиент в `T_Env_BackWall_BC/_E`.
- **Верхняя полоса K1 — 96,0 против 91,9 у P4.** У P4 в арках колоннады было тёмное небо, теперь за ними стена. Остаток — мраморные колонны и дверь под светом `portal-glow`. Свет не менялся.
- **Сакура** — розовая, приглушённая и не ярче карты. Но листва пака крупная и гранёная, это геометрия меша. Деревья ниже и уже вишен P4. Как и тень в пурпурный от `NightTint`, это вопрос художественной приёмки.
- **Светлячки** почти незаметны: около 14 точек на группу. Это сознательно дёшево.
- **Огонь, водопад и прибой** анимируются нодой `Time` и на паузе частиц. Кадры двух прогонов Sarpedon отличаются в этих местах (до 0,09 % пикселей).
- **Пересборка Niagara-систем в коммандлете.** `delete_asset` в `ue_import_fab_fx.py` не удаляет пакет, и `duplicate_asset` падает. Обход — убрать устаревший `.uasset` перед импортом (README-fx.md). Сам инструмент не исправлен.
- **Метрика мха `mossRim` в `measure_p5c.py` не ловит линию.** Она меряет полосу на верхней плоскости подноса и показывает 0 и у P5b. Убирание мха подтверждено отдельным замером на южной кромке (0,266 → 0,0) и крупным планом.
- **Река на карте и в устьях** — насыщенно-синяя с белыми точками, как в P5b: отношение воды к реке ×0,92 / ×0,77. Не менялась.
- **Вариант пользователя** (`-EnvLayoutVariant=<name>`, паки NoAI) на этом этапе не собирался и не снимался.
- **Художественная приёмка** — решение пользователя. Все значения вида (сакура, лес, куст, цветы, стена, луна, море, огонь, светлячки) только предложены и измерены.
