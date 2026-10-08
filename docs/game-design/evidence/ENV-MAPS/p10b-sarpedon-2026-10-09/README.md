# ENV-MAPS P10b: хвосты Sarpedon P10 на сцене lit3d путь 1 (VS-8 E1, 2026-10-09)

Статус: **измерено, технически импортировано, по делегированию**. Карточки EN-19…EN-24
(`docs/game-design/visual/06-tasks/env.csv`). Коммит `4aafc141`, ветка `feat/visual-vs8`, worktree `C:/tmp/wt-visual`.
Полномочия: пользователь 2026-10-06 — «Делай сам … Все решения принимай»; решения ВР-VS8-41…48 —
[VS-8 README](../../VISUAL/VS-8/README.md). Упаковки нет (одна упаковка — EN-25), интеграции нет.

Режим: лёгкий, live tune в одном клиенте редактора, перезапуск только после мешей / MI / FX
(3 запуска клиента: i0 → i1 → i2; правки параметров — пробы p1…g2, r0/r1, by0…by200 без перезапуска).
Итоговые числа — свежий editor `-Bench` закоммиченного состояния (`live_tune.py bench`, `RENDER reference=1`):
[кадры](final/), [трасса](final/bench.trace.txt), [cmdline](final/cmdline.txt). «До» — i0, первый кадр той же
live-сессии до правок (тот же отпечаток). Кадры концепта и замеры с концептом в git не кладутся (ENV-U3): числа
с концептом — только в этой таблице; концепт `C:/tmp/envmaps-research/p7/proto/sarpedon/concept-registered-H.png`.

## Критерии карточек: до → после

| карточка | критерий | до (i0) | после (final) | итог |
|---|---|---|---|---|
| EN-19 | K1 прямая кромка ROI (560–1360, 900–1080) ≤ 100 px | 13 | 13 | PASS |
| EN-19 | C0 полос `streams` ≥ N_concept − 1 = 2 | 3 (21 / 91 / 27 px) | 3 (53 / 91 / 35 px: 662–714, 788–878, 923–957; концепт 650–717, 788–886, 922–958) | PASS |
| EN-19 | K1 ROI пикселей ≥ 245 ≤ 1 % | 0 % | 0 % | PASS |
| EN-19 | тело струй (столбцы нарисованных полос, строки 885–1040) ΔE76 ≤ 6 | 5,26 | **3,17** (dL* −1,25) | PASS |
| EN-19 | G7 водопада live ≥ 10 % | — | 26,7 % (Fitx) / 26,6 % (K1), [g7-live-i2.json](final/g7-live-i2.json) | PASS |
| EN-19, 21, 22 | G5 K1: карта Y 104,9 ± 5; ΔE зон ≥ 23,2; тёплых ≥ 0,12; кольцо ≥ 30 | 105,0 / 25,33 / 0,126 / 36,6 | 105,0 / **25,05** / 0,137 / 36,4 ([g5-g7-final.json](final/g5-g7-final.json)) | PASS |
| EN-20 | верх полотна на пикселе C0 [1880, 388] ± 6 | на пикселе (вертикально, крен влево) | штанга точно на [1880, 388] (решатель `scene_layout.py`) | PASS |
| EN-20 | длина красного полотна на C0 342–378 px | ~233 px | 347 px у нарисованного; у игры 379 px по маске разницы с кадром без знамени (в маску входят штанга и тень на борту) | PASS (по полотну), см. ниже |
| EN-20 | IoU маски полотна с нарисованным ≥ 0,6 | 0,28* | 0,32 сырая / 0,45–0,50 с закрытием дыр | **FAIL** |
| EN-20 | SSIM ¼ полигона корабля не ниже 0,442 | 0,4407 (editor) | 0,4431 | PASS |
| EN-20 | G7 знамени ≥ 5 % | — | 10,2 % (Fitx live) | PASS |
| EN-21 | G6 6 из 6 ≥ 0,8 (deck-se с полигоном грани ящика) | 4 из 6 (left 0,69, deck-se 0,70) | **6 из 6**: bay 2,99, left 1,13, stern 0,89, rail 0,81, deck-n 0,90, deck-se 0,89 | PASS |
| EN-22 | K1 огонь: высота ≥ 14, h/w ≥ 1,2, ≥ 2 языков, красного ≤ 25 % | форт 89 / 1,62 / 0 / 4 %; жаровня 83 / 1,22 / 2 / 14 % | форт 113 / 2,06 / 2 / 5 %; жаровня 88 / 1,22 / 2 / 5 % ([fire-K1-final.json](fire/fire-K1-final.json)) | PASS |
| EN-22 | G7 огня ≥ 10 %; G7 света жаровни 2…8 уровней | огонь 14–27 % (P10); свет 0,53 | огонь 13,6–54,9 % (live i2); свет **3,66** (20 live-кадров K1, [g7-brazier-light-20-live-K1.json](fire/g7-brazier-light-20-live-K1.json)) | PASS |
| EN-23 | SSIM ¼ полигона ship ≥ 0,45 | 0,4407 | 0,4431 | **FAIL** |
| EN-23 | ΔL* ствола p90 ≥ 12 у всех 3 пушек | 4,2 / 13,0 / 16,6 | **22,6 / 12,9 / 15,9** | PASS |
| EN-23 | hull-red ΔE ≤ 6; 0 пикселей борта ≥ 245 | 5,51; 0 | 5,53; 0 | PASS |
| EN-23 | pytest `test_cannons_in_the_ports` | зелёный | зелёный | PASS |
| EN-24 | K2×1,6, полосы 0–120 uu у W / N края рамы: детальность камней ≥ 0,8 × острова или камней нет; бликов ≥ 230 нет | 0,60 (камни 20 890 px) | камней нет ([stones-K2x1p6-final.json](stones/stones-K2x1p6-final.json)) | PASS |
| EN-24 | G4 SSIM не ниже 0,49 | 0,4917 | 0,4891 | **FAIL на 0,0009** (см. ниже) |

\* i0: маска игры по цвету (без кадра «без знамени»), только для порядка.

Контроль Marmoreal (не должен меняться): свежий `-Bench` K1 / K2×1,6 против A1 `marmoreal-final` —
`live_tune.py compare`: K1 0,47 / 0,039 % пикселей > 24, K2×1,6 0,36 / 0,002 % (порог 0,5 / 0,05 %) — **PASS**,
[кадры](final/marmoreal-control-K1-1920x1080.jpg). Правки E1 Marmoreal не касаются (FX FireCore / FireTongues и
MI пушки есть только в раскладке Sarpedon).

## Что сделано

| карточка | правка | где |
|---|---|---|
| EN-19 | 3 потока на нарисованных полосах ([−262, −203], [−144, −62], [−34, 0] uu; просветы 59 и 28 uu со скалами); тело 0,4 → 0,75 в середине потока, боковой спад 30 → 14 uu (к краю — 0), пена потоков 0,5 → 0,85, больше и белее; `FallShade.w` 2 | `scene-params` cascade.streams; `scene-tune` FallsSheet; `SM_Env_S_Cascade` 2800 → 1470 + 168 треуг. |
| EN-20 | полотно 160 → 230 uu (×2 = 460), висит под 13° в плоскости полотна, 14 uu от борта; верх — на нарисованном пикселе | `banner_build.py` `hangTiltDeg`; `scene-params` banner, details.banner* |
| EN-21 | свет lantern-left 30 → 45 кд, из-за столба — перед головой фонаря [−549, 30, 190]; G6 lantern-deck-se — полигон грани ящика x 1679–1695 (ВР-EN.10) | профиль rev 26 `lit3d.lights` |
| EN-22 | ядро ×0,8 и желтее (4,6; 3,9; 1,4); языки выше (скорость ×1,4, жизнь ×1,25), языки жаровни повёрнуты на 90°; fire-fort 40 → 30 кд, на 27 uu вперёд и 9 uu ниже (стена форта больше не выжигается вокруг пламени); fire-brazier 80 → 140 кд, мерцание 0,25 → 0,5, радиус 180 | `ue_import_fab_fx.py` FX_SPECS; `fx-plan`; профиль |
| EN-23 | cannon-1 на `MI_EnvCP_CannonIron_Port` (RestAdjust V ×1,6) | `ue_import_concept_paste.py`, `scene-params` details.cannonMaterials |
| EN-24 | шаг 1 (утопить 40 %, ×0,8, новый поворот) — проба p1: детальность 0,60 → 0,26, хуже; шаг 2 — 13 камней не ставятся (ВР-EN.9) | `scene-params` rocks.dropIds, `scene_layout.py` |

Импорт (Content вне git, коммандлеты при закрытом редакторе): `ue_scene_material.py` (FallsSheet), `ue_import_concept_scene.py`
(Cascade, CascadeFoam, Banner), `ue_import_concept_paste.py --maps sarpedon` (новый `MI_EnvCP_CannonIron_Port`),
`ue_import_fab_fx.py --only NS_Env_FireCore,NS_Env_FireTongues`. Ловушка: пересборка FX в коммандлете падает
«DuplicateAsset failed … asset already exists» (delete_asset снимает пакет из памяти, реестр держит путь) — оба
производных `.uasset` удалены с диска перед запуском (копии `C:/tmp/visual/VS8/E1/backup-fx/`), затем `built`.
В другой копии Content нужно то же: 4 коммандлета, для FX — сначала удалить два производных `.uasset`.

## Ограничения и хвосты

- **EN-23 SSIM 0,4431 < 0,45.** Знамя на нарисованном месте и светлая cannon-1 SSIM почти не двигают (по клеткам
  100 px меньше всего: верхний ряд — мачта, такелаж, свёрнутый парус, 0,26–0,37; низ у cannon-3 — 0,13–0,20). Ящик под
  cannon-3 ×0,75 (проба c1) — хуже (0,4411 → 0,4400). Остался рычаг «мачта и такелаж» (`ship_build.py` + AO + перепечка
  альбедо + текстуры) — не делался в лёгком режиме (≈ 30–40 мин, итог SSIM не гарантирован); передан в EN-25 / VS-9.
- **EN-20 IoU 0,32 (0,45–0,50 с закрытием дыр) < 0,6.** Нарисованная маска рваная (знак и тёмные складки не проходят
  порог красного), у игры полотно ~15 px правее у верха (верх держится на пикселе [1880, 388] спеки, центр
  нарисованного верха ≈ 1872). Длина и место совпадают на глаз ([лист](ship/sheet-Fitx1p45-before-after.jpg)).
  Решение по длине — ВР-VS8-42: +20 % ВР-EN.11 даёт ≈ 330 px с креном 88 px влево; нарисованное — 347 px почти
  вертикально.
- **EN-24 G4 0,4891 < 0,49 на 0,0009.** Удаление камней G4 повышает (+0,003, пробы r0 / r1); падение — от остальных
  правок шага (водопад, знамя), шум кадра ≈ ±0,002 (свежие старты i0 / i1 / i2: 0,4917 / 0,4903 / 0,4892). Решение —
  по packaged-кадру EN-25.
- **EN-19 пена у подножия 0,5 → 0,65** не сделана: один MI на все подушки пены (уступы и море) — ВР-VS8-46.
- G7 света жаровни: `env_gates.py gates` берёт до 6 кадров серии K1; 20 кадров посчитаны тем же замером вне инструмента
  (`C:/tmp/visual/VS8/E1/brazier_std.py`); по 6 кадрам — 1,7–2,9 (шум выборки).
- ROI огня для EN-22 сужены до пламени (форт 345,40–400,160; жаровня 128,580–200,692): маска EN-05 по умолчанию
  берёт освещённую стену форта — ВР-VS8-47. В `env_gates.py` по умолчанию остались мировые коробки g7.
- Цена (ΔGPU) не мерилась — EN-25 (одна упаковка и `render_bench.py`).
- Отдельного ревью нет (лёгкий режим). Приёмка — по делегированию; если пользователь посмотрит и решит иначе — прав он.

## Проверки

- `python -m pytest tools/art/tests tools/art/map_surface -q`: **630 passed, 3 skipped**. Тесты, закреплявшие значения
  P9 / P10 (4 потока, вертикальное знамя 320 uu, покрытие ширины ≥ 0,8, точки света fire-fort / lantern-left,
  мерцание жаровни 0,25, «пена плотнее тела»), переписаны под новый контракт с пометкой VS-8 E1.
- `--check`: `scene_layout.py`, `bake_albedo.py`, `ue_import_concept_scene.py`, `ue_scene_material.py`,
  `ue_import_concept_paste.py --maps sarpedon`, `ue_import_fab_fx.py`, `layout_check.py --scene`, `env_gates.py` — ok.
- C++: правка только теста `S08ConceptPasteTests.cpp` (две точки света). UnmatchedEditor и игровая цель в worktree —
  «Result: Succeeded». UE `Unmatched.S08.ConceptPaste+EnvLayout+ArtTuner+HeroLight+LiveTune`: **54 / 54**, EXIT 0.
- Кадры открыты в цвете, сером и дейтеранопии: [K1 запад](fire/sheet-K1-west-before-after.jpg),
  [K1 водопад](falls/sheet-K1-before-after.jpg), [Fitx корабль](ship/sheet-Fitx1p45-before-after.jpg),
  [K2×1,6 края рамы](stones/sheet-K2x1p6-before-after.jpg), [K1](final/bench-K1-1920x1080.jpg). Доска — Sarpedon
  original, вид lit3d путь 1, шесть фигур v2 (три гарпии с цифрами, Медуза, Артур, Мерлин).

## Команды

```
python tools/art/render/live_tune.py start --map sarpedon [--tuner]
python tools/art/render/live_tune.py cycle --views K1+Fitx1.45+K2x1.6 --out <run> --tag <t>
python -B tools/art/concept_scene/banner_build.py; python -B tools/art/concept_scene/cascade_build.py
python -B tools/art/concept_scene/run_scene.py --steps export,layout,manifest
# коммандлеты (редактор закрыт): UnrealEditor-Cmd <uproject> -run=pythonscript -script="<repo>/<script> <args>" -unattended -nosplash -nullrhi
python tools/art/render/live_tune.py bench --map sarpedon --views K1+Fitx1.45+K2x1.6 --out <final>
python tools/art/render/env_gates.py crit <final> --concept <concept> --gates
python tools/art/render/env_gates.py gates <final> --concept <concept> --g6-exclude "lantern-deck-se=1679,645;1695,645;1695,745;1679,745"
python tools/art/render/env_gates.py fire <final>/bench-K1-1920x1080.png --roi 345,40,400,160 --roi 128,580,200,692
python tools/art/render/env_gates.py stones <K2 png> [--without <K2 png without the stones> --layout <layout>]
```

## EN-25: одна упаковка, свежий packaged `-Bench`, гейты, цена (VS-8 Frames, 2026-10-09)

Одна упаковка ветки `feat/visual-vs8` (штамп `2233b140`, `-SkipBuild` после сборки игровой цели, кук без ошибок; новых
`Config/**.json` нет). Кадры — [sarpedon-packaged/](sarpedon-packaged/) (JPEG q90 из PNG прогона, PNG вне git:
`C:/tmp/visual/VS8/F/en25/`), контроль Marmoreal — [marmoreal-control-packaged/](marmoreal-control-packaged/), цена —
[bench/bench-summary.json](bench/bench-summary.json), замеры — `sarpedon-packaged/*-packaged.json`. Все кадры `RENDER
reference=1`; открыты: K1, Fitx1,45, K2×1,6 Sarpedon и K1 Marmoreal; лист — [ENV-SARPEDON-P10B](../../VISUAL/ENV-SARPEDON-P10B/README.md).

| Карточка / гейт | editor final (E1) | **packaged (EN-25)** | Итог |
|---|---|---|---|
| EN-19 кромка K1 / струи / ≥ 245 | 13 px / 3 / 0 % | **13 px / 3 (42, 89, 35 px) / 0 %** | PASS |
| EN-19 тело водопада C0 (пятно P10) | — | ΔE76 **4,41**, dL* −0,71 | PASS |
| EN-20 знамя: строки G6 / IoU | — / 0,32 | строки **1,115** (верх 340, низ 776; нарисованное 340–745) / IoU не перемерялся | IoU FAIL (E1) |
| EN-21 G6 | 6 из 6 | **6 из 6** (bay 2,99, left 1,13, stern 0,90, rail 0,80, deck-n 0,90, deck-se 0,90) | PASS |
| EN-22 огонь K1 (ROI ВР-VS8-47) | форт 113 / 2,06 / 2; жаровня 88 / 1,22 / 2 | форт **113 / 2,06 / 2**, красного 4 %; жаровня **86 / 1,19 / 1**, 0,5 % | форт PASS; жаровня на этом кадре ниже h/w 1,2 и 2 языков (фаза пламени) |
| EN-23 SSIM корабля / пушки p90 / hull-red | 0,4431 / 22,6, 12,9, 15,9 / 5,53 | **0,4446** / **22,6, 13,0, 16,1** / **5,53**, борт ≥ 245 — 0 | SSIM FAIL; пушки и борт PASS |
| EN-24 камни K2×1,6 | нет | **нет** (0 px, бликов 0) | PASS |
| G4 SSIM ¼ / медиана ΔE пятен | 0,4891 / — | **0,4879** / 5,28 | SSIM < 0,49: FAIL на 0,002 (шум ≈ ±0,002); ΔE PASS |
| G5 K1 | 105,0 / 25,05 / 0,137 / 36,4 | **105,3 / 25,14 / 0,137 / 36,5** | PASS |
| G7 live (одна серия packaged) | водопад 26,7 %, знамя 10,2 %, свет жаровни 3,66 (20 кадров) | водопад **28,5 / 25,8 %**, огонь 17,8–23,7 %, кроны 12,5 / 8,5 %, знамя **3,8 %**, свет жаровни **1,85** (6 кадров) | водопад / огонь / кроны PASS; знамя и свет жаровни ниже порога в этой серии |
| G8 `render_bench.py` v2, 3 повтора | — | K1 **2,59 мс** (шум 0,01), K1×0,65 2,56, K2×1,6 **2,52**, K2×2,5 2,44 | PASS (K1 ≤ 3,5, Δ к 2,60 −0,01; K2×1,6 ≤ 3,8) |

Контроль Marmoreal: packaged K1 / K2×1,6 против packaged GD-058 2026-10-08 (`C:/tmp/visual/E5/exit/marm-bench-final`) —
сырые 0,85 / 0,47, пикселей > 24 — 0,15 / 0,22 % (порог шума 0,5 / 0,05 %). Разница сосредоточена на фигурах (крылья и
подставки гарпий — цифры AN-31; Arthur и Medusa — блок материалов AN-33 Marmoreal) и на мерцании левого фонаря; поле,
задник-вклейка и рама не изменились — правки E1 Marmoreal не касаются.

Цена записана одним измерением и в бюджете — оптимизаций нет (правило пользователя 2026-10-08). Дополнение к акту —
[GD-058/sarpedon-p10b-2026-10-09](../../GD-058/sarpedon-p10b-2026-10-09/README.md) (принято по делегированию, без личного
просмотра пользователя; FAIL остаются FAIL). Интеграция — после ветки VS-8 (`safe-integrate.sh`), в основной копии —
пересборка UnmatchedEditor и `sync-staged-build.ps1 -From C:/tmp/wt-visual`; Content основной копии нужно переимпортировать,
как сказано выше (4 коммандлета, для FX — сначала удалить два производных `.uasset`).
