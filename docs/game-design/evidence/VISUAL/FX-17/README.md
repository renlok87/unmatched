# FX-17 — лист приёмки

**Статус: технически импортировано.**

CUE-009 → `S08FxDefensePlayed` → `PlayRim(300, 1.0, 0.35, ramp-in 60, out 120)` у защитника (ВР-23); строка
CUE-009 уже несла mat=Rim (FX-01). Живой бой: обе карты, G-CUE PASS.

## Критерии и результат

| критерий | результат | доказательство |
|---|---|---|
| K2 на обеих картах, защищаются Medusa и гарпия | пик импульса (1.0/0.35) на обеих фигурах обеих карт | `C:/tmp/visual/Z-2/bench/{marmoreal,sarpedon}-rim-f-{0-hero,0-sk1}/bench-K2x1p6…png`; трейсы `FX bench rim … i=1.00 w=0.35` |
| кадры t0+60 / +180 / +300 | статические состояния бенча покрывают пик (+60/+180: rim=1.0) и спад (+300: rim=0.5); живые кривые — в юнит-тестах и демо | тесты RimIntensityAt (`tests-heroesv2.log`); демо-трейсы `ARTPREVIEW fig-fx fighter=… ch=rim ms=300 peak=1.00 width=0.35` |
| без защиты — обода нет, штамп есть | в демо оба состояния (штамп X в панели, обод только у сыгравшей карты) | `C:/tmp/visual/Z-2/demo/*/combat-*/host/s09-no-defense-stamp.png` |
| G-CUE PASS (G8) | PASS ×3 прогона | `C:/tmp/visual/Z-2/demo/*/combat-*/combat-client-host.trace.log` |

Входы (sha256-16): rim-medusa marmoreal K2 763d330163b96dde · rim-harpy marmoreal K1 482cd75ac382654e ·
rim-medusa sarpedon K2 487962474e380218.
