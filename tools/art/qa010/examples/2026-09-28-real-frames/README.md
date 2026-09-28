# Пример прогона QA-010-инструментов на кадрах 2026-09-28

**Это пример работы инструментов, а не приёмка QA-010 и не решение GD-058.** Пороги — «предложено» (`../../thresholds.proposed.json`). Кадры не классифицированы `classify_evidence` (T0), поэтому чек-лист честно помечает происхождение как подсказку по пути.

Входы (packaged-live прогоны, только чтение; SHA-256 до и после прогона совпали):

| Кадр | Файл | Трасса |
|---|---|---|
| K1 | `docs/game-design/evidence/ART-003/live-selection-run/run-20260928-061853/phase2-board-host-1920x1080.png` | `phase2-client-host.trace.log` того же каталога |
| K2 (1,6×) | `docs/game-design/evidence/ART-004/live-k2-label-probe-1p6/run-20260928-064001/phase2-board-host-1920x1080.png` | `phase2-client-host.trace.log` того же каталога |
| K3 | `docs/game-design/evidence/ART-003/live-combat-icon-damage-run/combat-20260928-073145/joiner/s09-combat-resolve-revealed.png` | `combat-client-joiner.trace.log` каталога прогона |

Производные PNG записаны в `C:/tmp/qa010-examples/derived/` и не коммитятся; их SHA-256 есть в `derive-manifest.json`. Все выводы перегенерированы версией `qa010-tools 1.1.0`.

## Команды (из корня репозитория)

```bash
Q="python tools/art/qa010/qa010.py"; E=docs/game-design/evidence; O=tools/art/qa010/examples/2026-09-28-real-frames
K1=$E/ART-003/live-selection-run/run-20260928-061853/phase2-board-host-1920x1080.png
K1T=$E/ART-003/live-selection-run/run-20260928-061853/phase2-client-host.trace.log
K2=$E/ART-004/live-k2-label-probe-1p6/run-20260928-064001/phase2-board-host-1920x1080.png
K2T=$E/ART-004/live-k2-label-probe-1p6/run-20260928-064001/phase2-client-host.trace.log
K2X=$E/ART-004/live-k2-label-probe-5x/run-20260928-063853/phase2-client-host.trace.log
K3=$E/ART-003/live-combat-icon-damage-run/combat-20260928-073145/joiner/s09-combat-resolve-revealed.png
K3T=$E/ART-003/live-combat-icon-damage-run/combat-20260928-073145/combat-client-joiner.trace.log
$Q derive $K1 $K2 $K3 --out C:/tmp/qa010-examples/derived --json $O/derive-manifest.json
$Q luma $K1 $K2 $K3 --json $O/luma-frames.json
$Q luma $K1 --trace $K1T --region board=trace-cells:all --region tray_proxy=trace-ring:0.05,0.35 \
   --region hud_top_left=bbox:0,0,610,140 --json $O/luma-k1-regions.json
$Q c9 $K1 --trace $K1T --game board=trace-cells:all --decor tray_proxy=trace-ring:0.05,0.35 \
   --exclude hud_tl=bbox:0,0,610,140 --exclude hud_tr=bbox:1425,0,1920,120 \
   --exclude hud_hand=bbox:330,975,1590,1080 --json $O/c9-k1.json                                 # exit 3: декор — прокси
$Q plate --trace $K2T --frame $K2 --json $O/plate-k2-1p6.json                                   # exit 3
$Q plate --trace tools/art/qa010/fixtures/new-trace-k2-plate.trace.txt --shot k2-plate-overlap.png \
   --json $O/plate-fixture-overlap.json                                                          # exit 1
$Q plate --trace tools/art/qa010/fixtures/new-trace-k2-plate.trace.txt --shot k2-plate-zero-bbox.png \
   --json $O/plate-fixture-zero-bbox.json                                                        # exit 3
$Q icon $K3 --bbox 975,483,1013,521 --json $O/icon-k3.json
$Q icon $K3 --trace $K3T --json $O/icon-k3-from-trace.json                                       # exit 3
$Q project --trace $K2X --json $O/project-k2-5x.json
$Q project --trace $K1T --frame $K1 --json $O/project-k1.json
$Q checklist --config $O/checklist-config.json --out-md $O/qa010-checklist.md --out-json $O/qa010-checklist.json
```

## Что получилось (измерено, не оценено)

| Проверка | Результат | Оговорка |
|---|---|---|
| Проекция K1 | остаток 1,34 px против `SHOT fighter` (камера трассы) | Модель подтверждена на 669 блоках трасс evidence |
| Проекция K2 5× | 3,45 px → 0,46 px после подгонки позиции камеры | Трасса печатает камеру с округлением до 1 uu |
| Luma кадра, p50 / p90 | K1 0,0 / 92,0; K2 61,7 / 98,0; K3 22,0 / 94,1 | Весь кадр, stride 1; для сравнения с S05 нужен `--stride 4` |
| С-9, K1 | `result_normative: proxy`, код 3. Замер на прокси (не норматив): ΔEV = +0,876, «ярче» было бы pass; диапазон +0,3..+0,7 — fail; «насыщеннее» — fail (ΔC\*ab −2,91); декор не холодный (b\* +5,0) | Декор = **прокси**: кольцо 0,05–0,35 клетки вокруг доски — деревянный поднос, слой L4 (фон), а не декор L3 (03 §4.1). Фасадов и фонаря в кадре нет, stencil-масок нет (17 §11.10). В чек-листе: «нет данных: декор — прокси (нужна stencil- или ручная маска L3)» |
| Плашка, K2 1,6× | `requires_new_trace` | В трассах нет bbox плашки и списка достижимых клеток; есть только `reachable=14` |
| Плашка, фикстура | fail: клетка (3,1) перекрыта на 5623,84 px² (12,7 %) | Синтетические строки нового формата |
| Плашка, фикстура `bbox=(0,0,0,0)` | `insufficient_input`, код 3: нулевая площадь плашки | Свёрнутый UMG-виджет: клиент тоже пишет `overlapReachable=0`, сверка совпала бы; это ошибка трассы, а не pass |
| Иконка K3 | 24 px 4,48:1; 32 px 4,63:1; 48 px 4,66:1 (увеличение с 38 px); ΔY′ ≈ +115…+119 | bbox `975,483,1013,521` снят вручную по кадру; маска авто (Otsu). Против кольца вокруг bbox 3,83:1 |
| Иконка из трассы | `requires_new_trace` | Строки `SHOT icon` в клиенте нет |
