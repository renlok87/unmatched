# MS-AT-41: плашки ходов в одной ISM (прогон H, R-04, 2026-10-05)

Журнал — [H-2026-10-05.md](../../../de-footage/task/runs/H-2026-10-05.md), раздел R-04. Код — коммит `9c8f92b7`.

## Условия замера

Те же, что у прогона B ([B/README.md](../2026-10-04/B/README.md), «Стоимость подсветки»): упакованный Development
(пакет `9c8f92b7`, `-SkipBuild` после сборки игровой цели, sha256 внутреннего exe `44f57459…`), `render_bench.py run`,
без ограничения FPS, RTX 4090, виды K1 и K2x1,6, флаги клиента как у B (`-ArtPreview -Bench … -ArtPreviewHeroesV2
-ArtPreviewDiorama`, без `-ConceptPaste`). Под замком `C:/tmp/unmatched-gpu.lock`, других клиентов UE и игр не было.

```
render_bench.py run --variant dx12-lumen-high-v2 --repeats 2 --views K1+K2x1.6 --bench-fixture ../../../Unmatched/Config/Bench/S08Bench<Map>.json
render_bench.py run --variant dx12-lumen-high-v2-moveplates --repeats 2 … --move-draft tools/s08/fixtures/move-draft/<map>-2-draft-conflict-needboost.json
render_bench.py run --variant dx12-lumen-high-v2-moveplates --repeats 1 … --move-draft tools/s08/fixtures/move-draft/<map>-0-candidates.json
```

Сводка — [ms-at-41.json](ms-at-41.json) (скрипт [dc_summary.py](dc_summary.py): среднее `RHI/DrawCalls` и разбивка
`DrawCall/*` по CSV профайлера). Тем же скриптом пересчитаны CSV прогона B — [ms-at-41-run-b-recomputed.json](ms-at-41-run-b-recomputed.json).

## Итог

| Карта, вид | Draw calls: база → плашки (сцена 2) | Δ, прогон H | Δ, прогон B | Δ GPU, мс |
|---|---|---|---|---|
| Marmoreal K1 | 435,8 → 437,5 | **+1,7** (Translucency +1,0, BeginOcclusionTests +1,1) | +8 | −0,010 |
| Marmoreal K2x1,6 | 347,5 → 313,4 | −34,1 | −28,5 | −0,015 |
| Sarpedon K1 | 478,8 → 482,8 | **+2,0** к базе r2 (+4,0 к среднему, см. ниже) | +8 | +0,025 |
| Sarpedon K2x1,6 | 471,8 → 394,7 | −77,1 | −74,0 | −0,005 |

- Порог MVP 7 + 4 × S (S = 0): **пройдено**. В проходах прибавка — по одному вызову в Translucency и в
  `BeginOcclusionTests` (было по четыре).
- Sarpedon K1: повтор r1 базы нарисовал на ~4 вызова меньше в Basepass/RenderVelocities, чем r2 и база прогона B
  (480,77). Это шум сцены, к плашкам он не относится. Против r2 прибавка +2,0 (Translucency +0,97, окклюзия +0,71).
- GPU в шуме, как и у B (порог +0,30 мс).
- Кадры сцены 0 (кольца-кандидаты) — 437,5 / 482,8 вызова, как в сцене 2.

## Вид

[marmoreal-plates2-K1-B-vs-H.jpg](marmoreal-plates2-K1-B-vs-H.jpg), [sarpedon-plates2-K1-B-vs-H.jpg](sarpedon-plates2-K1-B-vs-H.jpg):
слева прогон B (четыре ISM), справа R-04 (одна ISM). Кадры открыты и просмотрены: доски — Marmoreal original и
Sarpedon original, шесть фигур v2 (`heroesV2 summary … v2=6`, `ARTLOOK … heroes=v2`), задник Sarpedon — lit3d.
Marmoreal без `-ConceptPaste`, как в бенче B, поэтому вокруг поля 3D P5c (ENV-U16 открыт). Плашки сцены 2
(цель, NeedBoost, Conflict с «!», ярусы) совпадают. Попиксельно кадры плашек отличаются от B на 0,7–0,9 из 255
(средняя), столько же, сколько базовые кадры двух пакетов между собой (0,8–0,9).

Трассы ([marmoreal](marmoreal-plates2-r1.trace-excerpt.txt), [sarpedon](sarpedon-plates2-r1.trace-excerpt.txt)):
`MS-HL assets plate=M_UM_MovePlate … ready=1`, `MS-HL build … channels=4 isms=1 instances=124|152`, `MS-HL geom … ok=1`.
