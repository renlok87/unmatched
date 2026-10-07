# EN-11 — светлячки над садом Marmoreal (Niagara)

**Статус: технически готово, по делегированию (2026-10-07, VS-5 шаг E2, ветка `feat/visual-vs5`).** Вклейка за флагом
`-ConceptPaste` до EN-13. Кадры — live tune editor `-game`.

## Что сделано

- **Новая производная система** `/Game/EnvKit/FX/NS_Env_FirefliesDot`: `ue_import_fab_fx.py`, запись `FX_SPECS`,
  источник SoftTofu `NS_Sparkling_Animate_2`, CC BY 4.0.
  - CPU, детерминизм, Light/Component-рендереры выключены.
  - Эффект-тип Z-2 `NET_UM_Board` (поле `effectType`).
  - Спрайт рисует новый `MI_EnvFx_FireflyDot`.
- **`MI_EnvFx_FireflyDot`** (`FX_MATERIALS`, `build_materials`) — дочерний MI печатного мастера Z-2 `M_FX_Print`:
  - SDF-диск;
  - тело, кромка и кейлайн одного цвета `turn.flash.yellow` (#F2C14E), поэтому кольца нет;
  - обратная тоновая кривая `conceptPaste.grade`: токен выходит на кадр своим hex.
  - Импорт: коммандлет, `ENVFX-IMPORT-RESULT ok`, `compiled=1`, проверка CPU / без света пройдена.
- **Раскладка** `marmoreal.concept.layout.json`, `fx.add`:
  - `fireflies-garden-w` (−580,8; 135,5; 37) и `-e` (580,8; 135,5; 37) — нарисованные кусты у боковых тумб,
    C0 (290, 670) / (1630, 670), земля z −3 + 40;
  - `user`: SpawnRate 3, Lifetime 4–6 с (≈ 15 частиц), сфера 22 uu, шум 6, спрайт 3,5–4,6 uu;
  - `reducedMotion off`.
- **Подбор.** Одна итерация размера: 8–14 uu давали на K1 до 16 px, взято 3,5–4,6 uu.

## Приёмка карточки

| п. | критерий | результат |
|---|---|---|
| 1 | трасса fx: ≤ 24 частиц, `mode=frozen` в `-Bench`, `mode=off` с `-S08ReducedMotion` | `particles=10` на систему (после прогрева 3,5 с; установившееся ≈ 15), `mode=frozen deterministic=1`; с `-S08ReducedMotion`: `fireflies-garden-w/-e … mode=off reason=reduced` |
| 2 | кроп K2×1,6 ×4: диск с жёсткой кромкой, ореол > 10 % пика вне диска ≤ 1 px | [кроп ×4 цвет / серый](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/fireflies/bench-clock-K2x1p6-x4-colour-grey.png): плоские диски 3–9,5 px, ореола нет. Пикселей > 10 % пика дальше 1 px от диска — 0–2, у одного соседа 6: это соседний светлячок ([fireflies-metrics.json](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/fireflies/fireflies-metrics.json)) |
| 3 | пипетка ядра: ΔE76 к #F2C14E ≤ 10 | 4,9–8,0 (ядро ≈ (240, 181, 63)) |
| 4 | 10 живых кадров: над полем и рамой 0 частиц | 9 пар живых K1: внутри рамы 0 изменённых пятен; `-Bench` fx вкл / выкл: 20 пятен светлячков, внутри рамы 0 ([fx-metrics.json](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/petals/fx-metrics.json)) |

Кадр K1 ×3 у западной тумбы: [bench-clock-K1-x3.png](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/fireflies/bench-clock-K1-x3.png).
Я открыл кропы и полные K1 / K2×1,6 / K2×2,5: точки маленькие, не похожи на кольца команд и подложки, у
фонаря не стоят.

## Решения по делегированию

- **ВР-VS5-13.** Светлячки вклейки сделаны отдельной копией `NS_Env_FirefliesDot`. `NS_Env_Fireflies` используют
  базовая раскладка Sarpedon (lit3d) и откат P5c, они не меняются.
  - Печатный диск — от мастера Z-2, эффект-тип `NET_UM_Board` (ВР-25). Компоненты окружения спавнятся с
    `SetAllowScalability(false)`: тип их не гасит, и они не занимают слоты боевых fx.
  - Точка спавна сдвинута от «≈ (264, 620)» карточки к (290, 670) / (1630, 670). Так сфера держит ≥ 80 uu до стекла
    фонаря: 81 / 87 uu при радиусе 22.
  - Размер взят по пиксельному правилу карточки «на K1 4–6 px»: 3,5–4,6 uu. Указанные 8–14 uu дают 10–18 px.

## Остатки

- Мигание 0,5–1,2 Гц и рампы альфы 400 мс берутся из модулей пака, отдельно не настраивались. Печатный мастер
  отсекает альфу по 0,5, поэтому точка загорается и гаснет без полутонов.
- `NS_Env_FirefliesDot.uasset` и `MI_EnvFx_FireflyDot.uasset` закоммичены `git add -f` (как ВР-VS5-09). Перед
  `safe-integrate.sh --apply` в основной копии этих путей нет.
- ΔGPU ≤ 0,03 мс меряет EN-15.
