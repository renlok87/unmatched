# HB-16 — баннер «ВАШ ХОД»: UUmHudBanner (шаг H5)

VS-2 шаг B1, 2026-10-06, ветка `feat/visual-vs2`. Карточка — `06-tasks/hud.csv` HB-16; спецификация — 04 §2.4, §7.1;
02 §4.5; ВР-09, ВР-40, ВР-61; CUE-015; макет — CX-08 (принят по делегированию). Решения шага — ВР-VS2-41…50 в
[README HB-14](../HB-14/README.md) (для этой карточки — 41, 45, 49).

**Статус:** код, WBP, тест, лист галереи готовы; кадр +0,5 с от старта хода (набор A) packaged — шаг «Кадры» VS-2.
**Флаг отката:** `-S08SlateHud=banner` — прежний Slate `TurnBanner` (`#161A28`, 30 pt).

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. UUmHudBanner: Plate (T_Skin_Panel), Text (`hud.banner.own_turn`); ApplyModel(FS09TurnCue) | `S08/UI/UmHudBanner.{h,cpp}`: прозрачность = `FS09TurnCue::BannerAlpha`, своей анимации нет; текст `type.banner` 36 su `turn.flash.yellow`; `/Game/S08/UI/Hud/WBP_UI_HUD_BANNER` |
| 2. HitTestInvisible | при alpha > 0 — `HitTestInvisible`, иначе `Collapsed` (вне 600 мс нет ни тика, ни отрисовки) |
| 3. Центр, 420×64 | слот BANNER: L — y 144, S — y 72 (ВР-VS2-45, под однострочным STATUS; `UmHudLayout.cpp`) |
| 4. SHOT widget | `SHOT widget id=UI-HUD-BANNER state=shown … alpha=<a>` только пока alpha > 0 |
| 5. Slate TurnBanner — только при `-S08SlateHud=banner` | `S08FlowGameModeTurnHud.cpp` (одно условие) |
| 6. Тест | `Unmatched.S08.Hud.Banner.Alpha`: −1 / 100 / 450 / 600 мс → 0 / 1 / 1 / 0, 0 мс → 0,15 (ВР-VS2-49), reduced 100 мс статичен, в ход соперника не показывается, экран результата прячет, SHOT только при показе |

## Проверки

- `Banner.Alpha` зелёный; `Root.Layout`: баннер не пересекает `FIELD` Marmoreal / Sarpedon и STATUS на всех четырёх
  холстах.
- Лист галереи [HB-14/gallery](../HB-14/gallery/): плашка navy с кромкой, «ВАШ ХОД» жёлтым по центру; в сером текст
  читается; кляксы, мазка, `#161A28` нет.

## Отложено (шаг «Кадры»)

- G-WIDGET `UI-HUD-BANNER shown` на старте своего хода на обеих досках; G-CUE CUE-015 600 мс; кадр +0,5 с, 1080p и
  720p 150 %: плашка не пересекает клетки `FIELD` и STATUS.

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

Кадры выхода и гейты — [VS-2](../VS-2/README.md). Прогоны `run-combat-demo -PlayerView -S08ExitShots` на Marmoreal original (`-ConceptPaste` до EN-13) и Sarpedon original, шесть фигур v2, 1080p 75 / 100 / 150 %, 720p 100 / 150 %; vs-ai `-PlayerView`. Листы цвет / серый / дейтеранопия — `sheet-0*.png` (`sheet.py`, вырезки по трассовым bbox). Все кадры и листы открыты (Read).

- **Решение:** художественно принято, по делегированию (2026-10-07).
- «ВАШ ХОД» в кадре +0,25 с (run E) — полная непрозрачность, а в кадре +0,5 с — затухание (≈ 0,33, конец 600 мс), на обеих досках.
- Плашка не пересекает клетки FIELD и STATUS; в S баннер на y 72 (ВР-VS2-45).
- G-WIDGET `UI-HUD-BANNER shown`: строка первого кадра теперь в позднем блоке SHOT с нарисованной геометрией (ВР-VS2-77), ошибок 0.
- **Не прошло:** на 720p 150 % баннер ложится на Slate-строку итога боя в центре (VS-4, «Открыто», п. 9).

## Кадры выхода VS-4 (HB-49, упаковка `5a74a81e`, 2026-10-07)

Живые партии приёмочной упаковки, Marmoreal original (`-ConceptPaste` до EN-13, пометка) и Sarpedon original, шесть фигур v2, слоя отладки нет; прогоны, гейты и листы — [HB-49](../HB-49/README.md) (картинки со сканами и доской — вне git, `scraped-data/derived/visual-evidence/HB-49/`, ВР-VS4-01).

Баннер «ВАШ ХОД» при показанном центре боя встаёт на 8 su ниже центра (`pv-sarp-720-100 s09-exit-banner-combat`, `HUD-BANNER shift=96 under=combat`); кадра 720p 150 % с баннером при центре боя в прогонах не было — VS-2 п. 9 подтверждён на 720p 100 %, класс S — по правилу сдвига (ВР-VS3-56). **Вердикт: художественно принято, по делегированию (2026-10-07).**
