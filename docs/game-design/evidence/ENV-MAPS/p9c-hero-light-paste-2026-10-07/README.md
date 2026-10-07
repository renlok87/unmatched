# ENV-MAPS P9c: свет героев P9b под нарисованный Marmoreal (2026-10-07)

Статус: **измерено, свет в профиле, по делегированию** (ВР-57; VS-5 шаг E3, карточки AN-36 + EN-14, ВР-PL04 — один
прогон, лист приёмки: [docs/game-design/evidence/VISUAL/AN-36/](../../VISUAL/AN-36/README.md)). Таблица гейтов,
решения ВР-VS5-18 / ВР-VS5-19 и остатки — там.

Сцена: Marmoreal original (`c121b47f8d6eb28daccb76d05`), вклейка по умолчанию после EN-13 (`8ea9c6c9`), шесть фигур
v2, фикстура `S08BenchMarmoreal.json`, editor `-game` High / SP100 / DX12 Lumen, live tune: каждый набор — первый кадр
свежей сессии (`reference=1` у `off`, `p9b`, `p9c`; маски и idle — override, `reference=0`). Ключ сцены (−55, 30, 0),
экспозиция, moon-pool и Sarpedon не менялись.

| Набор | Как снят | Файлы |
|---|---|---|
| off | `live_tune.py start --map marmoreal --extra=-NoHeroLight` | [off/](off/) K1, K2×1,6, K2×2,5 |
| p9b | профиль rev 23 до смены света (7 лк `#D8E2FF` / 3,5 лк `#A8C0FF`) | [p9b/](p9b/) K2×2,5 (K1 — [env-u16 default](../env-u16-marmoreal-2026-10-07/default/marmoreal-K1-default.jpg)) |
| **p9c** | итог: 5,5 лк `#FFF0E0` / 2,75 лк `#C8D8FF`, блик контра 1,0 | [p9c/](p9c/) K1, K2×1,6, K2×2,5 |
| маски, idle | `start --profiles` override: зелёный соосный свет (`maskbody`; `maskfig` c `litPedestal: true`), `activeMul` 1 | вне git (C:/tmp/visual/E3/runs); генератор — [metrics/mkprof.py](metrics/mkprof.py) |

Числа: [metrics/p9c.json](metrics/p9c.json), [metrics/p9b-paste.json](metrics/p9b-paste.json), итерации
[i1](metrics/i1.json) / [i2](metrics/i2.json) / [i3](metrics/i3.json), H2 зон карты — `metrics/h2-zones-*.json`
(`env_gates.py gates`). D6 — `--baseline` кадры P9 ([p9b-hero-light-detail-2026-10-02/marmoreal-p9](../p9b-hero-light-detail-2026-10-02/marmoreal-p9/),
ещё с 3D-садом: как ориентир «хуже некуда»; его сырой dE76 у гарпий завышен фоном) и
[d6-config.json](../p9b-hero-light-detail-2026-10-02/d6-config.json).

Крупный план K2×2,5 «эталон | без света | P9b | P9c»: [цвет](closeup-k2x2p5-ref-off-p9b-p9c-colour.jpg),
[серый](closeup-k2x2p5-ref-off-p9b-p9c-grey.jpg).

## Подгонка (лёгкий режим, 3 итерации + пересчёт к пределу)

| Прогон | Ключ / контр | K1: прирост / кромка / D1 / D2 / Y тела | D6 |
|---|---|---|---|
| P9b под вклейкой | 7 лк `#D8E2FF` / 3,5 лк `#A8C0FF`, блик 0,8 | +17,7 % / 1,196 / 0,965 / **0,951** / 73,4 | 4/4 |
| i1 | 7 лк `#E8EEFF` / 3,5 лк, блик контра 1,0 | +19,4 % / 1,212 / 0,961 / **0,961** / 74,4 | 4/4 |
| i2 | 7 лк `#FFF0E0` / 3,5 лк `#C8D8FF`, блик 1,0 | +20,8 % / 1,230 / 0,969 / 1,004 / **75,3** | 4/4 |
| i3 | 6 лк, наклон 35°, контакт 0,15 / 3,0 лк | +20,3 % / 1,225 / 0,957 / 1,006 / 75,0 | 4/4 |
| **P9c** = i2 × 0,79 | **5,5 лк `#FFF0E0` / 2,75 лк `#C8D8FF`, блик 1,0** | **+16,8 % / 1,188 / 0,968 / 1,005 / 72,9** | **4/4** |

i2 прошёл все гейты, кроме D1, но тело ярче P9b (75,3 > 73,4); i3 (ниже и слабее ключ, длиннее контактная тень) D1 не
поднял. Итог — i2 с люксами ×0,79: прирост в окне +15…+35 %, яркость не выше P9b.
