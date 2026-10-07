# EN-07 — запекание и импорт плиты Marmoreal

**Статус: технически импортировано, кадры приняты по делегированию (2026-10-07, VS-5 шаг E1, ветка
`feat/visual-vs5`).** Вклейка — за флагом `-ConceptPaste` до EN-13. Кадры ниже — live tune editor `-game` с пометкой
`-ConceptPaste`. Приёмочные packaged `-Bench` будут в EN-15.

## Что сделано

- **`marmoreal.paste.json`** (статус ENV-U16, ВР-EN.2 записан в `status`):
  - `plates.dir` = `scraped-data/derived/env-u16-marmoreal-codex`, относительный; если копии в checkout нет, берётся
    копия основной копии;
  - `colour` = `marmoreal-extended-2x.png` 4680×2634, `conceptRectPx` [668, 376, 3344, 1882], sha256 `df4fd262…`,
    `registration: "concept"`;
  - `colourFallback` = `marmoreal-clean.png`;
  - `overlays` += `lanterns` (`paint-overlay`, `marmoreal-lanterns-2x.png`, alpha);
  - `anim` = `marmoreal-anim-2x.png` (R lantern-glow, G sakura-wind, B ground-mist, A petal-area — только офлайн);
  - `details` += 7 × `paint-lantern` из `lanterns.json`, без меша: 4 фонаря на земле с `heightUU` 100, бра и дверь на
    колоннаде;
  - `bake.outsideFrame` выключен, слоя моря нет.

  Входы совпадают с принятым пакетом: sha256 = `art/imagegen/env-u16-marmoreal-codex/manifest-sha256.json`.
- **`cp_bake.py`:**
  - производная плита регистрируется гомографией тега `concept`; `registration.json` не менялся;
  - `paint-overlay` накладывается на цвет до ресемплинга (straight alpha);
  - новая текстура `Anim` (`kind: anim`, RGBA 2048×1024 над rect B, linear) идёт через то же отображение C0
    (полоса рамы, регистрация, Lanczos-3).

  `manifest.marmoreal.json` пересчитан:

  | текстура | sha256 |
  |---|---|
  | PlateA 4096×2048 | `dfe732e9…` |
  | PlateB 2048×1024 | `bc7de887…` |
  | Anim 2048×1024 | `e1f6dbb7…` |

  Покрытие Anim > 0,5: R 0,2 %, G 5,3 %, B 5,9 %.
  Sarpedon перепечён для проверки: все 4 выхода побайтно прежние, в `manifest.sarpedon.json` сменился только хэш
  генератора (ВР-VS5-10).
- **`cp_layout.py`:**
  - `paint-lantern` — только мировая точка: в `conceptPaste.paintLanterns` и в опорные точки света оверлея;
  - `layout.fxRemoveBase` убирает все fx базы, в том числе `fireflies-garden-w/-e`;
  - в `marmoreal.concept.layout.json` убраны 64 пропа и все fx.
- **Профиль** `marmoreal-original.conceptPaste`:
  - `outside: "clip"` (плита покрывает rect B), `hide` += `layoutLights`;
  - 5 точек на мировых точках paint-lantern (moon-pool + 5 = 6);
  - блок `anim` (EN-06); `default` остаётся off.
- **Импорт** (`ue_import_concept_paste.py --maps marmoreal`, коммандлет, редактор закрыт):
  - `T_Marmoreal_ConceptPlateA` и `T_Marmoreal_ConceptPlateB` переимпортированы: sRGB, BC7, clamp;
  - `T_Marmoreal_ConceptAnim` новый: sRGB off, TC_Masks, мипы, clamp.

  Новых `Config/**.json` нет. Старый `T_Marmoreal_ConceptSea.uasset` больше не нужен; он вне git, не тронут.

## Приёмка карточки

| п. | критерий | результат |
|---|---|---|
| 1 | `cp_bake.py check marmoreal` ok; pytest `tools/art/tests` зелёный; `ue_import_concept_paste.py --check` ok | ok / 590 passed (1 тест сравнения с HEAD — после коммита) / ok; `cp_layout.py --check` ok |
| 2 | live tune `-ConceptPaste`, K1, K1×0,65, Fitx1,45, K2×1,6: плита чистая, фонари из накладки, края без растяжки; вне плиты на K1×0,65 = 0 | кадры ниже, `RENDER reference=1`. Граница rect B листа на K1×0,65 лежит за кадром со всех сторон: верх ≤ −170 px, низ ≥ 1245, лево ≤ −294, право ≥ 2214 (проекция `sheet_points`), значит доля вне плиты = 0. Почти чёрные пиксели кадра (0,9 %) — нарисованные тёмные трещины обрыва и листва, не дыры |
| 3 | `ARTPREVIEW concept-paste status=ok profile=marmoreal-original …` без missing | `status=ok … sheet=1 sea=0 lights=5 … homography=identity`, строк `missing` нет; `budget … combinedPoints=6 combinedBudgetOk=1` |
| 4 | Fitx1,45 против C0 концепта вне масок удаления: медиана ΔE76 ≤ 3 | **1,01** (p75 1,83, p90 3,56; 437 тыс. пикселей; без remove-mask, поля и кольца 200 uu вокруг карты) — [fitx1p45-dE76.json](fitx1p45-dE76.json), карта [fitx1p45-dE76-map.png](fitx1p45-dE76-map.png) |

**Бюджет VRAM** (оценка по форматам; замер — EN-15):

- PlateA BC7 4096×2048 ≈ 11 МБ с мипами — как раньше;
- PlateB BC7 2048×1024 ≈ 2,8 МБ;
- Anim TC_Masks 2048×1024 ≤ 2,8 МБ;
- шум 256² G8 ≈ 0,09 МБ.

Прибавка к сырой вклейке — Anim и шум, ≤ +3 МБ (бюджет ≤ +4 МБ).

## Кадры (я открыл каждый)

- [K1](live-conceptpaste-K1-1920x1080.png):
  - настоящая карта Marmoreal, шесть фигур v2;
  - чистая нарисованная плита, 4 фонаря и 2 бра горят из накладки;
  - дверь светится ровно, двойных огней нет.
- [K1×0,65](live-conceptpaste-K1x0p65-1920x1080.png): небо, колоннада, сакуры и обрыв доходят до краёв кадра, растяжки
  края нет (было ≈ 11 %).
- [Fitx1,45](live-conceptpaste-Fitx1p45-1920x1080.png): кадр C0 совпадает с концептом (п. 4).
- [K2×1,6](live-conceptpaste-K2x1p6-1920x1080.png): фонарь `lantern-w` и сакура чёткие, ×2 не мылится сильнее поля.

## Решения по делегированию

- **ВР-VS5-06.** Плита ×2 — производная концепта: оригинальная область пиксельно на месте (EN-02, затем EN-03 ×2).
  Поэтому cp_bake берёт гомографию тега `concept`, а свой sha256 плиты хранит в `paste.json`. `registration.json` не
  меняется (dont карточки).
- **ВР-VS5-07.** Концептный оверлей убирает все fx базы (EN-07, п. 3). Лепестки и светлячки вклейки добавят EN-09 и
  EN-11. До них в режиме вклейки fx окружения нет.
- **ВР-VS5-08.** `outside: "clip"` по контракту cp_bake (outsideFrame off). PlateB оставлен 2048×1024, как в карточке.
- **ВР-VS5-09.** Принятые uasset (`T_Marmoreal_ConceptPlateA/B/Anim`, `M_ConceptPaste`, `MI_ConceptPaste_Anim`,
  `T_ConceptPaste_Noise`) коммитятся `git add -f` по путям задачи (ВР-PL08, задание шага). Пункт dont «плиты и маски не
  в git» относится к PNG-исходникам в `scraped-data`: они остаются вне git.
- **ВР-VS5-10.** Хэш генератора в `manifest.sarpedon.json` обновлён после побайтно одинакового перепекания Sarpedon.
  Спецификация и ассеты Sarpedon не менялись.

## Остатки

- `portal-glow` стоит на плоскости колоннады на z 260,7, свет P5c был на z 120. Высоту и интенсивность подбирает EN-08
  (`heightUU`, ±25 %).
- Перед `safe-integrate.sh --apply` нужна копия: в основной копии лежат игнорируемые `M_ConceptPaste.uasset` и
  `T_Marmoreal_ConceptPlateA/B.uasset` по тем же путям. Их сохранить в `C:/tmp/visual-backup/<дата>/` (ВР-PL08).
- Статусы `env.csv` правятся в основной копии после интеграции.
