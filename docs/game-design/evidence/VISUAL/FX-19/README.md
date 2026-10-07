# FX-19 — лист приёмки

**Статус: технически импортировано** (ревью 2026-10-07: длительности исправлены, откат -S08FxLegacy работает; живой кадр самой вспышки не пойман — ниже).

`AS08FighterActor::PlayHitFx(WindowMs, bDamage)`: вспышка PlayFlash(70 мс) + обод с C+70 (1.0/0.35, спад к
C+370); PresentHit идёт через PlayFighterHitFx; `-S08HitTintLegacy` возвращает красную заливку
(ARTLOOK `hitFx=`); трасса `ARTPREVIEW hit-fx fighter=… flash=70 rim=300 legacy=<0|1>`; поле `tint=` строки
stage=hit не менялось (окно 450/550).

## Критерии и результат

| критерий | результат | доказательство |
|---|---|---|
| удар по Arthur (красный плащ) и по Medusa, кадры C+0/+35 (вспышка) / C+70..C+200 (обод) / C+370 (спад) | статические состояния: flash a=1 (luma маски 0.81), rim 1.0, rimout 0.5 — обе фигуры обеих карт | `C:/tmp/visual/Z-2/bench/{map}-hit-{flash,rim,rimout}-*/bench-K1…png`; кропы `C:/tmp/visual/Z-2/_fx-hit-stack.png`, `C:/tmp/visual/Z-2/_flash-arthur-eai.png` |
| красной заливки фигуры нет (default) | нет — на кадрах демо фигура без красной заливки, кремовый обод | `C:/tmp/visual/Z-2/demo/marmoreal/combat-20261007-135815/host/s09-damage-combat.png`; трио `C:/tmp/visual/Z-2/_demo-damage-trio.png` |
| -S08HitTintLegacy возвращает прежний вид (пара кадров) | да: тот же кадр урона с красной заливкой фигуры | `C:/tmp/visual/Z-2/demo/marmoreal-legacy/combat-20261007-140036/host/s09-damage-combat.png`; ARTLOOK `hitFx=legacy(-S08HitTintLegacy)`; `ARTPREVIEW hit-fx … legacy=1` в trace.log |
| C5 и G-CUE PASS | PASS (окна 450/550 не менялись; totals 2592–3933) | `C:/tmp/visual/Z-2/demo/*/combat-*/combat-client-{host,joiner}.trace.log` |
| Lumen: поле вокруг фигуры в кадр вспышки светлеет не больше ΔE76 3 | **не мерялось отдельно**: дифф flash-vs-rim ограничен маской фигуры (1488 px при площади фигуры ~5000 px у Артура) — поле за пределами маски не меняется | замер `C:/tmp/visual/Z-2/bench/marmoreal-hit-{flash,rim}-arthur/bench-K1-1920x1080.png` |

Входы (sha256-16): flash-arthur a318dc5067a9eab6 · rim-arthur b91eb27ce69fc7f6 · rimout-arthur 8f4c41dcabb7837a ·
flash-medusa(sarp) f7fadb3e349939cc · demo damage 31daf3b9a0328511 · legacy damage 9c41849c5aa38093.

## Ревью и доработка 2026-10-07

Ложные утверждения Z-2 исправлены (правка 13 обзора): «97 Success / 0 Fail» — набор S08 падал на CueFx.Determinism и обрывался; «Determinism PASS» — тест падал; «трассы ms=300» — в демо было ms=0 (секунды вместо мс); хит-трио демо не доказывало FX-19 (вспышка жила один кадр). Таблицы ниже старой версии оставлены как история и в этих местах недействительны.

- Длительности в мс, всё от одного момента удара (`2b5278b4`): вспышка C+0…C+70, обод C+70…C+370 (жёсткий старт,
  спад с C+270). Трасса пишет фактические значения: `hit-fx … flash=70 rim=300 rimAt=70 peak=1.00 legacy=0`.
- Откат: `-S08HitTintLegacy` или `-S08FxLegacy` → красная заливка (`hit-tint … ms=450`, `legacy=1`), проверено живыми
  прогонами пакета (`C:/tmp/visual/Z-2/review/demo/marmoreal-{hittintlegacy,fxlegacy}`); под -S08FxLegacy нет и обода защиты.
- Бенч-состояния (кропы ×4, sheet-01/02): вспышка — белый силуэт, средняя яркость 0,860–0,868; обод 1,0; спад 0,5.
- Живой кадр: кадр демо через ~170 мс после удара показывает фазу обода (sheet-03, кроп поля без HUD). Кадр
  самой вспышки (70 мс) снимок демо не ловит; нужен хук захвата — остаток (ВР-Z2R-03).
- Поле вокруг фигуры в кадр вспышки (статичный бенч, Lumen сошёлся): кольцо 6–20 px ΔE76 2,57–3,26, кольцо 3–12 px
  (с подставкой и ореолом сглаживания) 3,76–4,32. Порог 3 выдержан не везде; в живой вспышке 70 мс Lumen не успевает
  накопить отражение — ВР-Z2R-13.
- Окна 450 / 550 и `tint=` не тронуты; G-CUE PASS.
