# FX-19 — лист приёмки

**Статус: технически импортировано.**

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
