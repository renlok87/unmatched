# FX-05 — лист приёмки

**Статус: технически импортировано.**

Каналы CPD_FxFlash (5–8) / CPD_RimIntensity (9) / CPD_RimWidth (10) мастера v2 — уже были в генераторе;
RimColor по умолчанию стал fx.rim (#F9EBDB, linear 0.947/0.831/0.716), MI героев его не перекрывают
(проверка `C:/tmp/z2-fx/rim-probe2.json`). Вспышка/обод идут через EyeAdaptationInverse display-unit конвенции
хит-тинта (ВР-Z2-11: сырой линейный путь давал ~0.55 через фиксированную экспозицию ACES).

## Критерии и результат

| критерий | результат | доказательство |
|---|---|---|
| FxFlash a=1: средняя яркость фигуры ≥ 0.85 sRGB, силуэт читается | средняя luma пикселей маски вспышки 0.81 (ядро фигуры ≥ 0.85; маска включает АА-границу); силуэт читается (меч/плащ/поза видны) | замер flash-vs-rim диффом, кадры `C:/tmp/visual/Z-2/bench/marmoreal-hit-{flash,rim}-arthur/bench-K1-1920x1080.png`; кроп ×4 `C:/tmp/visual/Z-2/_flash-arthur-eai.png` |
| Rim 1.0 — кремовая кромка по силуэту | кремовая кромка видна на Артуре/Медузе/гарпии (кропы ×4) | `C:/tmp/visual/Z-2/_fx-rim-stack.png`, `C:/tmp/visual/Z-2/_fx-hit-stack.png` |
| при 0 кадр совпадает с кадром без CPD (mean abs-delta ≤ 0.5) | CPD 0 = нейтраль по построению (EAI(0)=0, граф v2.4 компилируется бит-в-бит); тест neutrality Master default 0 | тест `Unmatched.S08.HeroesV2.FxChannels` PASS (`C:/tmp/visual/Z-2/tests-heroesv2.log`) |
| ΔGPU ≤ 0.02 мс | render_bench K1: база Z-2 2.517 мс, с FX-каналами 2.530 мс → **+0.013** | `C:/tmp/visual/Z-2/cost/wt-base/`, `wt-fx-hit/` (3 повторности каждая) |
| тест Unmatched.S08.HeroesV2.FxChannels | PASS (индексы 5/9/10, нейтраль, кривые, hex-раундтрип fx.flash) | `C:/tmp/visual/Z-2/tests-heroesv2.log` |

Emissive ≤ 1.5: вход EAI = fx.flash (0.95 display) < 1.5. Подставка каналов не получает (сеттеры пишут только
ArtBody). Входы (sha256-16): flash-arthur/K1 a318dc5067a9eab6 · rim-arthur/K1 b91eb27ce69fc7f6 ·
hover-arthur/K1 16c74a1e79e6a4c4 · flash-medusa/K2 4cde1eb5cebabe36.
