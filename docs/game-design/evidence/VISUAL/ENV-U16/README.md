# ENV-U16 — лист приёмки нарисованного Marmoreal (EN-16)

**Вердикт (по делегированию, 2026-10-08, VS-5 шаг E5, ветка `feat/visual-vs5`): технически PASS; художественно —
не принято.** Карточка разрешает «художественно принято, по делегированию» только при PASS всех пунктов; не прошли
G-READ кромки панелей HUD (9 из 11 панелей < 3 : 1), EN-09 (лепестки почти не видны), EN-08 п. 2 (размах мерцания у
двух фонарей < 6 %) и D1 света героев (0,93–0,97). Нарисованный задник остаётся видом по умолчанию (ВР-58: вклейка
держит читаемость поля и фигур на K2; lit3d для Marmoreal — только словом пользователя). Статусы реестра 03 не
повышались (ВР-VS5-50).

Сборка: packaged `b4938cab` (кадры, гейты, бенч), финальная упаковка `b68e21b4` = `b4938cab` + тест
`S08ArtTunerTests.cpp` + ветер `ampPx` 0,4 (ВР-VS5-47; проверена: кадры `-Bench` K1 / K2×1,6 те же, ветер G7 15,7–19,2 %).
ПК разработки, не D-07.

## Что проверено

| Пункт | Как | Результат |
|---|---|---|
| G-LOOK | Read PNG всех кадров листа и выходных кадров | настоящая карта Marmoreal original (Board `c121b47f8d6eb28daccb76d05`), нарисованная плита без 3D-окружения и без двойных фонарей (фонари только нарисованные, 3D-голов нет), шесть фигур v2 (3 гарпии с цифрами, Medusa, King Arthur, Merlin), слоя отладки нет; откат `-NoConceptPaste` — 3D P5c с подносом; Sarpedon — lit3d. **PASS** |
| Трассы | `data/trace-*.txt` | `ARTLOOK board=marmoreal-original backdrop=paste(default)`; `concept-paste mode=on … reason=default … kind=paste status=ok lights=5`; `concept-paste anim … synced=4 wind=0.40@0.25 mist=0.22`; откат `backdrop=p5c(flag-off)`; Sarpedon `backdrop=lit3d(default)`. Во всех 17 живых прогонах HUD шага — `backdrop=paste(default)` (16 строк) / `lit3d(default)` (7) |
| RENDER | `render_fingerprint.py check` | `reference=1` на 5 кадрах Marmoreal и 6 кадрах Sarpedon свежего packaged `-Bench` |
| H2 / G5 | `env_gates.py gates` ([data/gates-marm-bench.json](data/gates-marm-bench.json)) | ΔE76 смежных зон K1 **23,65** (≥ 23,2, PASS); K2×1,6 26,58, K2×2,5 27,84; K1×0,65 23,17 и Fitx1,45 23,41 (обзор, справочно). Кольцо ΔL* 36,2 / 33,4 / 34,5 / 43,1 / 53,9; яркость карты 107,9–114,3, задник/карта 0,60–0,73 |
| K2-тест (ВР-58, ENV-BACKDROP-RULES §2) | K2×1,6 и ×2,5 | T1 ΔE 26,6 / 27,8 ≥ 23,2; T2 кольцо 43,1 / 53,9 ≥ 30; T3 кромка фигуры D4 1,188 (K1, AN-36) ≥ 1,15; на глаз поле и фигуры читаются, задник не спорит с полем. **Вклейка держит K2 → остаётся** |
| G-GRAY | [sheet-gray.jpg](sheet-gray.jpg), [sheet-deutan.jpg](sheet-deutan.jpg) | в сером и при дейтеранопии фигуры (тёмная бронза) отделяются от светлых кругов поля; поле отделено от задника тёмной рамой; светлые кроны сакур у рамы в сером близки по яркости к белым кругам верхнего ряда, но рама их разделяет — слияний нет. **PASS** |
| G-READ, текст в панелях | 56 кадров HUD (pv-marm 1080p 100 % и 720p 150 %), p97 / p30 в bbox ([data/gread-e5.json](data/gread-e5.json)) | медианы: TOP 14,9 / 15,4, STATUS 14,9 / 15,4, SUB 15,2 / 15,4, DECKS 15,7 / 11,7, PENDING 11,5 / 13,0, OPP-HAND 6,2 / 7,4 (≥ 4,5); LOG 4,11 (1080p, приближение по антиалиасингу; минимум 3,3); OPP-HAND минимум 4,19. **Почти PASS**: LOG и один кадр OPP-HAND ниже 4,5 по приближённой мерке |
| G-READ, кромка `panel.edge` к медиане задника | модель 02 §10.6: хайрлайн `#F9EBDB` 0,45 поверх тела `#061623` 0,92, к медиане задника в кольце 3–15 px вокруг панели | ≥ 3 : 1 только у ACTIONS (3,68 / 3,91) и PANEL-LOC (3,61 / 3,66). Минимумы 1080p / 720p: TOP 2,09 / 2,10, STATUS 1,49 / 2,08, LOG 2,65, PANEL-OPP 2,53 / 2,26, OPP-HAND 1,81 / 1,85, DECKS 2,29 / 2,60, SUB 2,48 / 1,28, PENDING 1,64 / 2,63, TOAST 1,07. Задник под панелями — средние тона нарисованной плиты (освещённый камень колоннады `#30486A`…`#795456`, розовые кроны `#61476C`), где ни кромка, ни тело панели не дают 3 : 1. **FAIL** (ВР-VS5-48) |
| Reduced motion | живая партия `-S08ReducedMotion` (набор H) | трасса `concept-paste anim … mode=frozen … frozen=1 reason=reduced`, лепестки и светлячки `mode=off reason=reduced`; кадры через 2,5 с: изменено > 8 уровней 0–0,009 % в кронах (без флага 4,7–8,7 %) — [motion-reduced.jpg](motion-reduced.jpg), [motion-normal.jpg](motion-normal.jpg). **PASS** |
| Откат | `render_bench --client-args=-NoConceptPaste`, кадр K1 | [frames/marmoreal-NoConceptPaste-bench-K1.jpg](frames/marmoreal-NoConceptPaste-bench-K1.jpg): 3D P5c, поднос T2b; трасса `backdrop=p5c(flag-off)` |

## Критерии EN-08 … EN-12 и EN-14 (итог)

| Карточка | Критерий | Результат | Итог |
|---|---|---|---|
| EN-08 мерцание | зоны ΔE ≥ 23,2; D3 ≤ 0,5 %; размах свечения 6–16 % | 23,65 (packaged K1); D3 0,005–0,015 % (E2); размах nw / e 6,0 / 7,5 %, w / ne 5,8 / 4,6 % (E2). Packaged — [motion-flicker.jpg](motion-flicker.jpg) | п. 2 частично |
| EN-09 лепестки | видны вне поля, ≤ 40 частиц, reduced — без частиц | 23 частицы на систему (E2), reduced — off; на packaged-полосе [motion-petals.jpg](motion-petals.jpg) падающие лепестки почти не видны на фоне крон | **FAIL (видимость)** |
| EN-10 ветер | G7 крон 3–20 %, вне крон ≤ 0,1 % | при 0,5 packaged 23,5–24,7 % → **0,4**: 15,7–19,2 % (финальная упаковка), вне крон 0,037–0,047 %; кромки крон целы — [motion-wind-0p4.jpg](motion-wind-0p4.jpg), [data/wind-g7-0p4-final-package.json](data/wind-g7-0p4-final-package.json) | PASS (ВР-VS5-47) |
| EN-11 светлячки | точки `turn.flash.yellow`, ≤ 24 частиц, без ореола, вне поля | 10 частиц, ΔE 4,9–8,0, ореол ≤ 1 px (E2); packaged — [motion-fireflies.jpg](motion-fireflies.jpg): жёлтые диски у кустов, над полем нет | PASS |
| EN-12 туман | ΔL* 2–8 на K1×0,65, кромка панели не хуже | ΔL* 2,53 (E2); packaged — [motion-mist.jpg](motion-mist.jpg): слабый синий туман у подошвы обрыва | PASS |
| EN-14 свет героев P9c | D1–D6, H2 | D2 1,005–1,013, D3 0–0,003 %, D4 +16,8 % / 1,188, D5 1,134 / 1,119, D6 4/4, H2 23,63 — PASS; **D1 0,93–0,97 < 0,986** (E3, live tune; packaged-маски не снимались) | D1 FAIL |

## Кадры листа (открыты: Read)

- Свежий packaged `-Bench` `b4938cab`: [frames/](frames/) K1, K1×0,65, Fitx1,45, K2×1,6, K2×2,5; откат K1; Sarpedon K1.
- [sheet-color.jpg](sheet-color.jpg), [sheet-gray.jpg](sheet-gray.jpg), [sheet-deutan.jpg](sheet-deutan.jpg) — те же 7 кадров.
- Полосы движения (packaged live tune, `--live --clock free`): мерцание и светлячки — 6 кадров K2×1,6 через 0,7–0,8 с
  (инструмент кадра не снимает чаще 0,45 с; 100 мс карточки недостижимы), лепестки — 10 кадров K1 через 0,5–0,6 с,
  ветер — 2 кадра Fitx1,45 через 1 с (0,5 и 0,4), туман — 2 кадра K1×0,65 через 2 с. Live-кадры packaged-сессии с
  профилем из ворктри — `reference=0`, годятся для полос и метрик, не для эталона.
- Live-tune `--live` снимает заморозку и под `-S08ReducedMotion` (инструмент), поэтому reduced motion доказан живой
  партией, а не live tune (ВР-VS5-49).
- Кадры HUD (наборы A и C на Marmoreal 1080p 100 % и 720p 150 %, сканы и аватары) — вне git,
  [data/visual-evidence-index.json](data/visual-evidence-index.json); сводка — [VS-5](../VS-5/README.md).

## Флаги отката

`-NoConceptPaste` / `-ConceptPaste=0` / `-EnvLayoutVariant=p5c` — 3D P5c с подносом T2b (AGENTS.md «Rollback flags»);
`-ArtPreviewNoFx` — без частиц (A/B); `-S08ReducedMotion` — всё статично.

## Решения (по делегированию)

| № | Решение | Почему |
|---|---|---|
| ВР-VS5-47 | Ветер Marmoreal `ampPx` 0,5 → 0,4 (одна итерация live reload на packaged-сборке) и финальная упаковка `b68e21b4` | packaged G7 23,5–24,7 % > 20 %; E2 оставил запас 0,45; 0,4 даёт 15,7–19,2 % на финальной упаковке; `-Bench` не меняется |
| ВР-VS5-48 | G-READ кромки — FAIL записан, HUD не правится в этом шаге; предложение для владельца HUD: тёмный внешний кант `mark.keyline` 1 su вокруг панелей или прозрачность `panel.edge` ≥ 0,65 с пересъёмкой наборов A / C | модель 02 §10.6 не даёт 3 : 1 на средних тонах плиты; правка токена меняет весь принятый HUD (новая упаковка и все гейты HUD) — отдельная карточка H-шага |
| ВР-VS5-49 | Reduced motion доказывается живой партией (`h-marm-1080-100`), не live tune | live tune `--live` снимает заморозку и под флагом |
| ВР-VS5-50 | Статусы реестра 03 по ENV-U16 не повышаются до «художественно принято»: плита, маски и анимации — «технически импортировано» | карточка: «Не повышать статус при любом FAIL» |

## Файлы `data/`

`trace-*.txt` (строки ARTLOOK / concept-paste / RENDER / fx), `gates-marm-bench.json`, `gates-sarp-bench.json`,
`gread-e5.json`, `en15.json` (цена, [README EN-15](../../ENV-MAPS/env-u16-marmoreal-2026-10-08/bench/README.md)),
`wind-g7-*.json`, `compare-marmoreal-b4938cab-vs-b68e21b4.json`, `visual-evidence-index.json`.
