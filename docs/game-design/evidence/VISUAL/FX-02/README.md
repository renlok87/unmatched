# FX-02 — лист приёмки

**Статус: технически импортировано.** Художественную приёмку делает визуальный чат.

Материал `M_FX_Print` (+ twin `M_FX_Print_Overlay`, ВР-Z2-02), 7 MI карточки + 4 MI плашки, текстура-флипбук
`T_FX_HitStar` (процедурная заготовка, ВР-Z2-03). Сборка: `python tools/art/fx/fx_import.py`
(отчёт `C:/tmp/z2-fx/fx-import.json`: compile_errors [], PS-инструкций 191 у обоих мастеров).

## Критерии карточки и результат

| критерий | результат | доказательство (путь) |
|---|---|---|
| тест-плашка (звезда-флипбук и три SDF-формы) в кадры packaged -Bench, RENDER | 4 фигуры в ряд над центром доски, обе карты, K1+K2×1,6 | кадры `C:/tmp/visual/Z-2/bench/{marmoreal,sarpedon}-placard-1/bench-K1-1920x1080.png`; трасса `FX bench placard star=registered sdf=3` (bench.trace.log тех же папок) |
| пипетка тела/кромки ΔE76 ≤ 6 при обеих экспозициях | **не достигнуто**: тело диска/шеврона dE76 18.3–18.6 (RGB 231,192,164 против #F9EBDB); ромб dE76 49.6 — замер по кластеру диффа смешан с SDF-кромками при 30 px | замер по кропам `C:/tmp/visual/Z-2/_placard-final.png`; MI несут профильный fit (`C:/tmp/z2-fx/mi-grade.json`: GradeScale 3.0302/2.8923/3.1758), кривая та же, что у M_ConceptPaste (`tools/art/fx/fx_import.py` FLIPBOOK_HLSL); остаточное отклонение — движковая цепочка translucent-unlit против откалиброванного opaque-паста (ВР-Z2-10, калибровка — ревью визуального чата) |
| G-TOKENS PASS (литералов цвета нет) | в графе мастеров нет hex-литералов (цвета только в MI из hud-style-tokens.json) | генератор `tools/art/fx/fx_import.py` (MI_PLAN + tokens()); G-TOKENS сканирует S08/UI — не задет |
| бюджет ≤ 40 инструкций пикселя | **191** (Stats мастера; M_ConceptPaste — 334 для сравнения) | `C:/tmp/z2-fx/fx-import.json` statistics; ВР-Z2-05 |
| 1 draw call на эмиттер | плашка: 1 спрайт-эмиттер + 3 квада | describe `C:/tmp/z2-fx/fx-systems.json` (1 emitter, 1 sprite renderer) |

## Глазами (кропы ×4)

`C:/tmp/visual/Z-2/_placard-diff-crop.png`: диск (крем тело/светлая кромка/тонкий тёмный контур), ромб, шеврон,
звезда (тёплая, тёмный контур) — плоские печатные формы с жёсткой кромкой, без свечения и градиентов.
Серые ряды — в листе sheet-01..03.

## Входы (sha256-16)

- bench/marmoreal-placard-1/bench-K1: 431e2cabd37e373d · K2x1p6: eeb9ba09bb311f5a
- bench/sarpedon-placard-1/bench-K1: 644b398301a84d51

Пакет stamp `0ad05d0c…` (после всех фиксов), `RENDER reference=1` в каждом прогоне.
