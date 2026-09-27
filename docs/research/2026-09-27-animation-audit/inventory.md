# Аудит 3D-ассетов персонажей MVP (Medusa, Harpy×3, King Arthur, Merlin)

Дата: 2026-09-27. Аудитор: аним-аудит 18. Репозиторий: `C:/Users/ren/WebstormProjects/unmached/unmached`, ветка `fix/admin-panel`.
Метод: перечисление файлов (`find`), чтение .blend через Blender 5.2.2 LTS CLI в `--background` (строго чтение, ничего не сохранено; вспомогательные скрипты лежат в `%TEMP%/anim-audit-18/`, вне репозитория), бинарное сканирование FBX (Python), чтение evidence-JSON и C++/Python-исходников, `git log`. UE-редактор и packaged-сборка в этом аудите НЕ запускались — все UE-факты ниже либо (а) наличие .uasset (проверено мной), либо (б) факты из tracked-доказательств (с указанием файла и строки), либо (в) чтение исходников.

## 1. Происхождение требований

| Требование | Статус | Доказательство |
|---|---|---|
| Лёгкий риг, 4 типа клипов (idle / выпад / вздрагивание / оседание), перемещение скольжением актора | УТВЕРЖДЕНО (D-11) | `docs/game-design/00-vision-and-scope.md:105` |
| Имена клипов Idle/LungeAttack/HitReact/DeathSettle; «4 клипа» — норматив для ART-004 | Имена — PROPOSAL; «4 клипа» — НОРМАТИВ | `docs/game-design/17-art-production-spec.md:889-890`; `docs/game-design/14-sprint-backlog.csv:63` (ART-004) |
| Длительности: Idle 2–3 с loop, HitReact 0.4 с, DeathSettle 0.9 с; LungeAttack без root-смещения | PROPOSAL | `docs/game-design/04-blender-production.md:111` |
| Шаблон скелета `blender/_shared/rig_template.blend` на всех персонажей (~15 костей + weapon) | PROPOSAL; файла нет | требование: `docs/game-design/04-blender-production.md:30`; отсутствие подтверждено `find blender -type f` (только S05 и _shared/s01-import); признано и доками: `docs/game-design/17-art-production-spec.md:893` («Файла нет. S05 строит риг скриптом») |
| LungeAttack 600 мс, HitReact-цифра 900 мс, DeathSettle 950 мс (CUE-длительности) | PROPOSAL | `docs/game-design/07-animation-vfx-audio.csv` строки CUE-008/CUE-011/CUE-013 |
| Текстуры 2K/1K (ART-005) | PROPOSAL, не начато | `docs/game-design/evidence/S05/art-references/art-visual-reference-report.md:101` («ART-005 untouched — OPEN») |
| Серийные модели A03 (Arthur/Merlin/Harpy) не начинать до GD-058 | PROPOSAL (план) | `docs/game-design/17-art-production-spec.md:771` |
| Манифест 06: все 4 персонажа `verificationStatus=planned` | ФАКТ документа (устарел относительно S05 по Medusa) | `docs/game-design/06-asset-manifest.csv:3-6` |

## 2. Фактическое состояние по персонажам

### Medusa — ЕДИНСТВЕННЫЙ персонаж с 3D-моделью; блокаут-эталон, НЕ финальное искусство

Модель (процедурный блокаут, строится скриптом):
- .blend: `blender/S05/s05-assets.blend` (298 КБ, mtime 2026-09-25 20:53; добавлен коммитом `192ae3e` от 2026-09-25, `git log --diff-filter=A`). Проверено мной в Blender 5.2.2: меши `Medusa_Body` (1846 verts / 1944 polys), `Medusa_Bow` (305/289), `Medusa_Base` (48/26), `Mannequin_Body`, `UCP_Medusa` (капсула-коллизия), 17 статик-мешей.
- Треугольники: тело 3568 + лук 582 + подставка 92 = 4242 tris — `blender/S05/build-report.json` (поле `tris`); подтверждено доками: `docs/game-design/17-art-production-spec.md` (строка «Фактические tris S05 Medusa … ИЗМЕРЕНО»). Это блокаут: бюджет героя 15–25k (PROPOSAL, `04-blender-production.md:109`), отчёт прямо: «draft blockout ~4.2k tris … ART-004 stays OPEN» — `art-visual-reference-report.md:50`.
- Габарит в UE: 38.7×53.5×55.0 uu, pivot min_z=0.00 — `docs/game-design/evidence/S05/art-references/s05-import-result.json:44-51`.
- Текстур НЕТ, материалы flat-color (3 слота M_S05_Base/Body/Accent) — `s05-import-result.json:108-110`; `art-visual-reference-report.md:101`.

Скелет:
- `SKEL_S05_Medusa`, 17 костей: root, hips, spine, head, arm_upper.L/R, arm_lower.L/R, hand.L/R, leg_upper.L/R, leg_lower.L/R, foot.L/R, weapon — проверено мной Blender CLI (вывод аудита `armatures`), совпадает с `build-report.json` (поле `medusa_bone_names`). В UE кости переименовываются `.`→`_` (17 имён) + bone-0 узел арматуры → 18 в рантайме (`run-summary.json:17` `bones=18`).
- UE: `unreal/Unmatched/Content/S05/Meshes/SK_Medusa.uasset` (1.7 МБ), `SK_Medusa_Skeleton.uasset`, `SK_Medusa_PhysicsAsset.uasset` — наличие проверено мной (`find`, mtime 2026-09-25 23:59). Импорт-проверка костей: `s05-import-result.json:52-54`.

Оружие/сокеты:
- Лук: меш `Medusa_Bow` привязан rigid к кости `hand.L` — `blender/S05/build_medusa.py:518`. Змеи-волосы: `SNAKE_COUNT = 6` — `build_medusa.py:426`. Стрела — отдельный статик `SM_S05_Arrow` (не в скелете).
- Сокеты UE: `Weapon`→hand_L (0,2,0), `Head`→head (0,0,8) — редактор: `s05-import-result.json:112-114`; работа в cooked-сборке (трансформы сокетов следуют за позами LungeAttack/HitReact): `run-summary.json:17-18`, `art-visual-reference-report.md:46-47`.

Клипы (сцена Blender 24 fps — проверено мной, `bpy.context.scene.render.fps`=24):
- Генерация: процедурная, `build_medusa.py:522-550` (keyframe-таблицы) + экспорт отдельным FBX на клип `build_medusa.py:812-816`. В СОХРАНЁННОМ .blend из Action'ов остаются только `DeathSettle` (1–22) и `RM_Test` (1–30, на манекене) — проверено мной Blender CLI (`bpy.data.actions`); Idle/LungeAttack/HitReact каждый раз пересоздаются скриптом и в файле не хранятся.
- Root motion: у всех 4 клипов Medusa нулевой (требование ART-004) — код проверки: `unreal/Unmatched/Source/Unmatched/SmokeGameMode.cpp:210-236`; факт packaged-прогона: `run-summary.json:5` (`S05_MEDUSA_RM … все (0.00,0.00,0.00)`); `art-visual-reference-report.md:31`.
- Loop: в референс-сцене K1 Idle играется с loop=True на всех 6 фигурках — `tools/s05/s05_import_scene.py:664`; в K3 LungeAttack/HitReact — PlayAnimation(Seq,false) + SetPlayRate(0) (заморозка в позе) — `SmokeGameMode.cpp:198-205`. Флаг loop внутри самих .uasset мною не вскрывался (бинарный формат) — ограничение.
- Воспроизведение в packaged-сборке подтверждено: packaged smoke PASS 2026-09-25T15:37:32Z, exit 0 — `run-summary.json:2,25`; K3-позы: LungeAttack@0.290 и HitReact@0.160 — `run-summary.json:17-18`; пиксельные гейты силуэтов — `art-visual-reference-report.md:27,94`. Idle реально анимирует в packaged (между прогонами пиксели «плывут» от idle-анимации) — `art-visual-reference-report.md:5` («idle-animation noise only»),`:4`.

### Harpy (×3 экземпляра), King Arthur, Merlin — 3D-МОДЕЛЕЙ НЕТ

- Нет .blend/FBX/GLB/OBJ, нет UE-ассетов, нет скриптов сборки. Поиск: `find . -iname *harpy*|*arthur*|*merlin*|*excalibur*` вне node_modules — 3D-файлов ноль (только 2D-референсы `art/imagegen/mvp-v1/characters/ref-harpy*.png`, `ref-king-arthur*.png`, `ref-merlin*.png`, бэкенд-код `backend/src/game-engine/abilities/heroes/arthur.handler.ts`, скрап `scraped-data/api/heroes/king-arthur.json`). UE Content содержит только S01/S05/S08 (проверено `find unreal/Unmatched/Content -type f`, 60 файлов).
- В S05-сцене Arthur и все гарпии — ЗАГЛУШКИ из меша Medusa: `s05-import-result.json:124-127` («figures=6 (all SK_Medusa instances, labeled)») и список фигурок с ярлыками «H2 ARTHUR», «S1..S4 HARPY» — `s05-import-result.json:177-327`; прямо в отчёте: «Arthur/harpy are labeled Medusa stand-ins» — `art-visual-reference-report.md:102`; сцена строится из `medusa` для всех мест — `tools/s05/s05_import_scene.py:655-664`.
- Требования к ним существуют только как карточки PROPOSAL: Harpy `04-blender-production.md:118-140` (крылья = кости рук шаблона, ≤80 uu размах), Arthur `:142-164` (сокет Weapon под Excalibur/Holy Avenger CUE-014), Merlin `:166-188` (посох выше фигурки на голову). Меч/посох/крылья как ассеты — отсутствуют (см. §3 MISSING).
- Коммиты «Harpy alignment» (5328354) и «sword and staff placement» (909b9e1) касаются ТОЛЬКО 2D-референсов imagegen — проверено `git log --name-only`: изменялись `art/imagegen/mvp-v1/characters/ref-harpy-*.png`, `ref-king-arthur-v7-right*.png`, `ref-merlin-v5-left*.png` и JSON/тексты промптов. Это правки 2D-картинок для генерации изображений, не 3D.

### Манекен (не персонаж MVP, но skeletal-ассет в репо)

- `SM_S05_Mannequin` — skeletal-версия (вопреки PROPOSAL `04-blender-production.md:290` о статичном манекене), свой скелет `SKEL_S05_Mannequin` (17 костей, тот же набор — проверено мной в .blend), UE: `SM_S05_Mannequin.uasset` + `_Skeleton` + `_PhysicsAsset`.
- Клип `RM_Test` (ART-001 тест root motion): 30 кадров @24fps; кривые уровня объекта (location x/y/z) + поворот arm_upper.R — проверено мной Blender CLI (probe3: 6 fcurves, kf на кадрах 1/15/30); root motion 1 м. В UE: `AM_RM_Test_Anim.uasset`, `enable_root_motion=True` — `tools/s05/s05_import_scene.py:490`; packaged-результат `delta=(0,100,0)` (100uu по +Y; ось +X из QA-009 НЕ подтверждена — открыто) — `run-summary.json:7-8`; `17-art-production-spec.md` (строка «Тестовый root-клип ART-001 … В S05 измерено (0, 100, 0)»).

## 3. Таблица 1. Инвентаризация клипов и моделей

Верно (существование файла проверено мной в этом аудите; «доказательство воспроизведения» — по tracked-отчётам packaged-прогонов, UE-редактор я не открывал):

| ТОЧНО | Character | Clip | Blender Action | FBX | UE asset | Verified | Status | Evidence |
|---|---|---|---|---|---|---|---|---|
| 2026-09-25 | Medusa | модель (SK) | SKEL_S05_Medusa, 17 костей (в .blend, проверено CLI) | SK_Medusa.fbx 204 КБ | SK_Medusa.uasset + _Skeleton + _PhysicsAsset | импорт 40/40 + packaged smoke PASS exit 0 | EXISTS_AND_VERIFIED (блокаут; текстур нет) | find; Blender CLI; s05-import-result.json:52-54,124-127; run-summary.json:25 |
| 2026-09-25 | Medusa | Idle | НЕ сохранён в .blend (генерится build_medusa.py:522-526, кадры 1/29/57) | AM_Medusa_Idle.fbx 290 КБ | AM_Medusa_Idle_Anim.uasset + _PhysicsAsset | длительность UE 2.333s (ожид. 2.375s); loop=true в сцене; S05_MEDUSA_RM=0 | EXISTS_AND_VERIFIED (Action живёт только в скрипте) | Blender CLI (actions: только DeathSettle/RM_Test); build-report.json clips[1,57]; s05-import-result.json:60-63; s05_import_scene.py:664; run-summary.json:5 |
| 2026-09-25 | Medusa | LungeAttack | НЕ сохранён в .blend (build_medusa.py:527-538, кадры 1/7/11/15) | AM_Medusa_LungeAttack.fbx 290 КБ | AM_Medusa_LungeAttack_Anim.uasset + _PhysicsAsset | UE 0.583s; K3: играется замороженно @0.290, сокеты следуют; RM=0 | EXISTS_AND_VERIFIED | build-report.json [1,15]; s05-import-result.json:72-75; run-summary.json:17; SmokeGameMode.cpp:190-205 |
| 2026-09-25 | Medusa | HitReact | НЕ сохранён в .blend (build_medusa.py:539-543, кадры 1/4/10) | AM_Medusa_HitReact.fbx 289 КБ | AM_Medusa_HitReact_Anim.uasset + _PhysicsAsset | UE 0.375s; K3 @0.160; RM=0 | EXISTS_AND_VERIFIED | build-report.json [1,10]; s05-import-result.json:84-87; run-summary.json:18 |
| 2026-09-25 | Medusa | DeathSettle | Сохранён: 22 кадра, 9 fcurves (hips.loc, spine/head.rot), CONSTANT | AM_Medusa_DeathSettle.fbx 289 КБ | AM_Medusa_DeathSettle_Anim.uasset + _PhysicsAsset | UE 0.875s; RM=0 | EXISTS_AND_VERIFIED | Blender CLI probe3; build-report.json [1,22]; s05-import-result.json:96-99 |
| 2026-09-25 | (манекен) | RM_Test (root motion тест, не игровой клип) | Сохранён: 30 кадров, 6 fcurves (object location + arm_upper.R) | AM_RM_Test.fbx 168 КБ | AM_RM_Test_Anim.uasset + _PhysicsAsset | UE 1.208s; enable_root_motion=True; packaged delta=(0,100,0) | EXISTS_AND_VERIFIED | Blender CLI probe3; s05-import-result.json:40-43; s05_import_scene.py:490; run-summary.json:7-8 |
| — | Harpy (все 3 экз.) | модель + Idle/LungeAttack/HitReact/DeathSettle | нет | нет | нет | — | MISSING | поиск find по *harpy* (0 3D-файлов); UE Content только S01/S05/S08; карточка-требование 04:118-140; манифест 06:5 planned; в S05-сцене — SK_Medusa-заглушка с ярлыком (s05-import-result.json:204-327) |
| — | King Arthur | модель (Excalibur) + 4 клипа + сокет Weapon | нет | нет | нет | — | MISSING | тот же поиск (*arthur* — только backend-код и 2D-референсы); 04:142-164; 06:6 planned; S05-заглушка «H2 ARTHUR» на Medusa-меше (s05-import-result.json:279-301) |
| — | Merlin | модель (посох) + 4 клипа | нет | нет | нет | — | MISSING | тот же поиск (*merlin* — только 2D-референсы); 04:166-188; 06:7 planned |
| 2026-09-25 | Medusa | текстуры 2K (ART-005) | — | — | — | flat-color MI (MI_S05_MedusaBody/Accent и др.) | PLACEHOLDER_ONLY | art-visual-reference-report.md:50,101 |
| — | Все | walk/run-циклы перемещения | — | — | — | — | NOT_APPLICABLE | D-11: перемещение скольжением актора (00-vision-and-scope.md:105; 07-animation-vfx-audio.csv CUE-007) |

Примечание к Verified для Medusa-клипов: «воспроизведение в UE» подтверждено отчётами packaged-прогонов (run-summary.json, пиксельные гейты K3) — сам UE в аудите не запускался, это ограничение, а не догадка.

## 4. Полный список FBX/GLB/OBJ вне node_modules

| Путь | Что это | Чьё | Дата (mtime) | Доказательство |
|---|---|---|---|---|
| blender/S05/export/*.fbx (22 файла: 5 AM_*, SK_Medusa, 16 SM_*) | Medusa-клипы + скелетный меш + статики диорамы | S05 эталон | 2026-09-25 20:53 | find + ls; коммит 192ae3e (2026-09-25) |
| blender/_shared/s01-import/SM_S01_Cube.fbx | куб 100uu проверочного набора | S01 (ART-001 статик-часть) | 2026-09-18 13:20 | find; docs/game-design/evidence/S01/ue/import-result.json (куб 100×100, 1 материал) |
| scraped-data/images/heroes/models/*.glb (6 файлов) | мини-модели оригинальной игры Unmatched (скрап CDN) | сторонние, ТОЛЬКО референс формы (D-06), производством не используются | 2026-01-26 09:30-31 | ls; 00-vision-and-scope.md:100 (D-06); привязка: 04:100 (Medusa=3eR7yPmdggV…), 04:148 (Arthur=xfdrwhmlwG…); URL в scraped-data/api/heroes/*.json |
| unreal/Unmatched/Intermediate/…/*.obj (29 файлов) | ЛОЖНЫЕ попадания: объектные файлы компилятора C++, не 3D | — | — | find; расширение совпало |

art/: 3D-моделей НЕТ — 528 файлов, все PNG/JSON/скрипты imagegen (find art -type f). «Sword and staff placement» (909b9e1) и «Harpy alignment» (5328354) — правки 2D-референсов: git log --name-only показывает только art/imagegen/**.png/.json/.txt/.md.

## 5. Искал и не нашёл (список)

1. `blender/_shared/rig_template.blend` — шаблонный скелет из 04:30. Нет (в blender/_shared только s01-import/). Подтверждено доками: 17-art-production-spec.md:893.
2. `blender/_tools/` (normalize_names.py, batch_export.py, mesh_report.py, preview_render.py, manifest_build.py из 04 §4) — каталога нет; фактический пайплайн — единый `blender/S05/build_medusa.py`.
3. Каталоги `blender/ASSET-MEDUSA-001/`, `ASSET-HARPY-001/`, `ASSET-KING-ARTHUR-001/`, `ASSET-MERLIN-001/` со структурой medusa.blend/textures/preview/REPORT.md (04 §3) — не существуют.
4. Любые SK_Harpy / SK_KingArthur / SK_Merlin .fbx/.uasset; файлы *harpy*/*arthur*/*merlin*/*excalibur* 3D-форматов по всему репо (вне node_modules) — 0.
5. Textures/T_Medusa_* (2K/1K) — нет; в Content/S05 нет каталога Textures (find).
6. Сведения о LungeAttack/Holy Avenger VFX (CUE-014) как ассетах — нет (клип/VFX не создавались; сокет Weapon под это есть только у Medusa-заглушки).
7. Animation Blueprint / AnimMontage / Blend Space в UE Content — нет (только AnimSequence в S05/Anims; find unreal/Unmatched/Content).
8.Walk/run-циклы — не должны существовать по D-11 (NOT_APPLICABLE), и их нет.

## 6. Расхождения документации с фактом (для отчёта)

- `06-asset-manifest.csv:3` (ASSET-MEDUSA-001) — `verificationStatus=planned`, пути `blender/ASSET-MEDUSA-001/…`, `/Game/Meshes/SK/SK_Medusa`; фактически Medusa собрана и лежит в `blender/S05/…`, `/Game/S05/Meshes/SK_Medusa` (импортирована, packaged-проверена). Манифест не обновлён после S05.
- `14-sprint-backlog.csv:63` (ART-004) — статус planned, но S05 уже сдал прототип; сам отчёт честно держит ART-004 OPEN (нет текстур, блокаут, нужна человеческая приёмка GD-058) — art-visual-reference-report.md:50,120.
- 04 §3.10 предлагал СТАТИЧНЫЙ манекен; фактически SM_S05_Mannequin — skeletal (нужен для RM_Test). Отклонение от PROPOSAL, не от решения.

## 7. Ограничения проверки

- UE-редактор/packaged-сборку не запускал: все UE-факты — из tracked evidence (s05-import-result.json, run-summary.json, отчёты) и чтения исходников (SmokeGameMode.cpp, s05_import_scene.py). Наличие .uasset проверено файловым листингом; ВНУТРЕННОСТИ .uasset (флаги loop, настройки сжатия) не вскрывались — бинарный формат.
- Имена take внутри двоичных FBX не извлекаются простым сканированием (секции сжаты); соответствие «файл↔клип» доказано цепочкой: build_medusa.py:812-816 (экспорт по одному Action на файл) → build-report.json (frame-диапазоны) → s05-import-result.json:60-107 (длительности каждого клипа после импорта). В самих FBX подтверждено наличие узлов AnimStack/Takes и ссылок на SKEL_S05_Medusa/Medusa_Body/Bow/Base (Python-скан бинарников).
- `build_medusa.py` намеренно не выполнялся: он перезаписал бы .blend/FBX в репозитории (запрещено правилом 1). Поэтому Action'ы Idle/LungeAttack/HitReact проверены через код+build-report, а не через живой запуск.
- Происхождение 4 из 6 .glb в scraped-data (чьи именно мини-модели, кроме Medusa/Arthur по 04:100,148) — не устанавливал: для аудита достаточно D-06 (референс только).
- Даты коммитов брал из `git log` (локальная история ветки fix/admin-panel); mtime файлов могли обновиться при checkout.
