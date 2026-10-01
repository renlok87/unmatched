# ENV-MAPS P5c: вариант раскладки «для пользователя» (NoAI), 2026-10-01

Статус: предложено, технически импортировано, проверено по трассе. Художественную оценку даёт только пользователь.
По правилу NoAI (ENV-U14) агенты кадры этого варианта не смотрят.

## Правило NoAI и как оно соблюдено

Паки `Megaplant_Library` (Megaplants: Yoshino Cherry) и `StyleHex_Studio` (FREE Stylized Rocks Pack) запрещено
показывать ИИ. Агенты работали с ними только как с путями ассетов и техническими данными UE: класс, габариты,
треугольники, зависимости, нужные плагины, текстовый T3D-экспорт (узлы сборки Nanite, граф материала), строки
трассы. Текстуры, превью и кадры с этими ассетами никто не открывал, не читал и не анализировал. Кадры
варианта лежат вне git: `C:/tmp/envmaps-research/p5c/user-variant-for-user/` (README.txt для пользователя,
SHA256SUMS.txt).

NoAI-ассеты стоят только в оверлеях `Config/ArtBoards/EnvLayouts/<карта>.user.layout.json`. Оверлей включается
флагом `-EnvLayoutVariant=user`. В `<карта>.layout.json` их нет; это проверяют `ue_import_user_fab.py --check`,
`layout_check.py` (проверка 11) и тест `test_env_user_fab.py`.

## Состав

| Файл | Что делает |
|---|---|
| `scripts/user-fab.json` | Спецификация производных ассетов `/Game/EnvKit/UserFab/` (схема `unmatched.env-user-fab/1`). Блоки `measured` содержат замеры из отчёта UE |
| `tools/art/env_kit/ue_import_user_fab.py` | Идемпотентный импорт (коммандлет). Также `--check` без UE и `--adopt-report` (переносит замеры в спецификацию) |
| `scripts/p5c_user_overlays.py` | Генератор оверлеев: подбор масштаба, `layout_check`, правила fx, `--check` |
| `reports/p5c-user-fab-import-report.json` | Отчёт импорта: действия, габариты, треугольники, аудит зависимостей |
| `reports/p5c-user-overlays-report.json` | Масштабы, треугольники на доску, сводка `layout_check` |
| `tools/art/tests/test_env_user_fab.py` | 9 тестов: спецификация, разбор T3D, оверлеи, «двойник» MergeOverlay |

## Yoshino Cherry без новых плагинов

Деревья пака — скелетные сборки Nanite (Nanite assemblies), по 1 LOD. Им нужны:

- экспериментальные плагины ProceduralVegetationEditor и DynamicWind;
- read-only переменные `r.Nanite.Foliage` / `r.Nanite.AllowAssemblies` на весь проект.

Мастер-материал `MA_Foliage_Trees` лежит в контенте плагина, поэтому без него MI грузятся без родителя.

В `Unmatched.uproject` плагины **не включались**. Сделано так:

1. **Своё дерево.** `SM_UserFab_YoshinoC` / `SM_UserFab_YoshinoD` — статический меш с Nanite, «запечённый» из
   исходной позы скелетного меша `Tree_Yoshino_Cherry_01_C/D`:
   - ствол взят через GeometryScript `copy_mesh_from_skeletal_mesh`;
   - веточки сборки стоят на своих Local-трансформах: 239 у C и 82 у D. Узлы читаются из T3D-текста ассета:
     массив `Nodes` в Python не виден;
   - сами веточки — статические двойники пака `Twig_Yoshino_Cherry_0N` в виде Nanite-fallback (RenderData LOD0);
   - у C они дополнительно упрощены до бюджета 900 тыс. треугольников (получилось 899 778), у D — 448 665 без
     упрощения;
   - материалы: id 0 — кора, id 1 — цвет (у C 136 893 / 762 885 треугольников).
2. **Свой мастер.** `M_UserFab_Tree`: текстура пака × `Tint` → ночной узел (насыщенность, яркость) → BaseColor.
   Карты нормалей и просвечивания нет. Ночные значения скопированы с сакуры основного варианта
   (V 0,7, S 0,85, тон 0,85/0,78/1,25). По кадрам они не подбирались.
3. **Плагин только для импорта.** GeometryScripting подключается лишь на время коммандлета
   (`-EnablePlugins=GeometryScripting`). Аудит зависимостей готовых ассетов: пакетов ProceduralVegetation,
   DynamicWind, GeometryScripting и PCG нет. Обе Yoshino ссылаются только на `EnvKit`, `Megaplant_Library`
   (две текстуры), `Engine` и `Script`.

Ветра нет: деревья статичные. Это не мешает детерминизму `-Bench`.

## Камни StyleHex

Шесть мешей пака продублированы в `/Game/EnvKit/UserFab/Sarpedon/SM_UserFab_Stone*`, от 602 до 1525
треугольников. Мастер пака `M_Environment_Basic` (граф прочитан из T3D-текста) умножает текстуру на
`Color Tint` только за статическим переключателем `Use Color Tint?`. В паке переключатель выключен, тон равен 0.
Ночные MI включают переключатель и ставят «мокрый» тон 0,42/0,42/0,45 — вслепую.

Камни с опорной точкой внутри меша приподняты так, что в поднос утоплено 30 % части ниже опорной точки.
Для поднятых камней генератор сам проверяет пересечение оснований: `layout_check` пропускает проверку 5 для
«навесных» Fab-пропсов.

## Оверлеи

| Карта | Замены | Масштаб |
|---|---|---|
| Marmoreal | cherry-nw/w/e → YoshinoC, cherry-se → YoshinoD; petals-* перенесены под новые кроны | 0,365 / 0,445 / 0,425 / 0,435 — площадь кроны равна площади сакуры основного варианта, `layout_check` чист без уменьшения |
| Sarpedon | rock-nw/ne → Cluster1, rock-w → Large1, rock-sw → Small3, rock-se → Small5, rockwet-w → Small1, rockwet-sw → Cluster2 | по площади основания прежнего камня |

Треугольников в экземплярах: Marmoreal 3,39 млн, из них 3,15 млн — Nanite-деревья; Sarpedon 0,24 млн.
`layout_check` по объединённой раскладке: 0 ошибок и 0 предупреждений. Правила fx: частиц ~322 / ~318, кольца карты
свободны.

## Проверки (2026-10-01)

- `ue_import_user_fab.py`: `USERFAB-IMPORT-RESULT ok`. Повторный запуск — `unchanged` (идемпотентно),
  запрещённых зависимостей нет.
- Редактор `-game -Bench`, `-EnvLayoutVariant=user`, K1 и K1x0.65, под GPU-lock. Два прогона на карту, по тексту
  трассы:
  - `envlayout variant=user ... status=ok errors=0`;
  - замены: Marmoreal props 4, fx 4; Sarpedon props 7;
  - `missingMeshes=0 outsideKit=0 intrusions=0`;
  - fx: `particles=317/316 gpuEmitters=0 mode=frozen`;
  - RENDER-отпечаток каждого SHOT совпадает с `render-reference.json` (8/8).
- Основной вариант без флага, два прогона Marmoreal и один Sarpedon:
  - строки `ARTPREVIEW envlayout` совпадают с финалом P5c. Единственное отличие — `overlays=...` в строке `enabled`,
    так задумано в Track V;
  - кадр K1 против финала P5c: Marmoreal 0,004 % пикселей с разницей > 24, Sarpedon 0,040 %. Это порядок разницы
    двух одинаковых прогонов: default против default2 — 0,006 %.
- UE-тесты S08+S09+S10: 237/237. `Shipped` сливает оба оверлея со `status=ok`.
- pytest `tools/art/tests` + `tools/art/map_surface`: 416 passed, 2 skipped.

## Открытые вопросы

- Внешний вид не оценён никем, кроме пользователя: плоская листва без нормалей, ночные тона вслепую,
  масштабы по площади.
- Кук: `/Game/EnvKit` всегда кукится. Если в копии проекта есть `UserFab`, packaged-сборка потянет NoAI-ассеты:
  ~57 МБ мешей Yoshino и текстуры 4K. Для личной локальной сборки (ENV-U13) это допустимо. Если нужен packaged
  без NoAI, придётся исключить `/Game/EnvKit/UserFab` из кука, но тогда вариант в packaged работать не будет.
- В основной ветке `UserFab` появится, только если оркестратор запустит импорт в той копии. Паки должны лежать в
  её Content. Без этого `-EnvLayoutVariant=user` даёт `missingMeshes>0`, а основной вариант не затронут.
- Yoshino — меши Nanite, первые в проекте. На SM6 (эталон) они рисуются Nanite, на SM5 — fallback-мешем.
