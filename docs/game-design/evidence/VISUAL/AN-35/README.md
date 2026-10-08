# AN-35 — Arthur P1: кант плаща сзади

**Статус: закрыто замером без правки (вариант 1), по делегированию (ВР-AN12, ВР-VS8-04), 2026-10-08, VS-8 шаг A1,
ветка `feat/visual-vs8`.**

В фикстурах бенча Arthur играет за P2 (`p2=f-1-hero,f-1-sk0`). Для Arthur P1 сделаны копии фикстур с обменом ростеров
`f-0-` ↔ `f-1-` (позиции те же; команда по префиксу id, `team mapping … p1=f-0-hero,f-0-sk0`): `S08BenchMarmoreal-ArthurP1.json`,
`S08BenchSarpedon-ArthurP1.json` (вне git, `C:/tmp/visual/VS8/A1/fixtures/`), прогон `live_tune.py bench` через обёртку
`lt_arthur.py` с `-BenchFocusFighter=KingArthur`, editor `-game`, K1 / K2×1,6 / K2×2,5.

| Карта | MI | FACING Arthur P1 | спина видна |
|---|---|---|---|
| Marmoreal original | `MI_KingArthur_H2LD_P1` | `src=spawn rest=145 cam=100 off=45` | нет |
| Sarpedon original | `MI_KingArthur_H2LD_P1` | `src=spawn rest=141 cam=96 off=45` | нет |

|off| = 45° ≤ 45° на обеих картах (поворот покоя ВР-06 ограничен 45° от камеры для любой команды), на K2×2,5 Arthur
вполоборота лицом к камере, плащ сзади не виден — правка `heroMaterials.KingArthur.P1` не нужна.

Кадры (цвет | серый): [K2×2,5 обеих карт](arthurP1-K2x2p5-marm-sarp.jpg), K1 — [Marmoreal](arthurP1-K1-marmoreal.jpg),
[Sarpedon](arthurP1-K1-sarpedon.jpg) (настоящие доски, вклейка / lit3d, шесть фигур v2; кольцо команды P1 золотое).
