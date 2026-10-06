# CP-17 — наведение, выбор, фокус

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-17; 02 §6.3, §4.3, §11.2;
04 §2.6, §3.4; SD-26; UI-INP-003, UI-INP-011. Общее — [README CP-15](../CP-15/README.md). Коммит `67a57467`.

**Статус:** API виджета, тест и лист движения готовы. Подъём на всю высоту + 24 su, подъём выбранной на 32 su, порядок
над соседями, клавиши 1–9 и Tab, коридор между PANEL-LOC и ACTIONS — у владельца HAND (HB-24). Поэтому кадры набора A
«наведение на карту» и «выбрана атака» в партии — шаг «Кадры» после HB-24.
**Откат:** `-S08SlateHud=hand` (у владельца).

## Что сделано

- `SetHover(bool)`:
  - scale 1 → 1,5 за `hover.ms` 150, ease-out-quad; render transform с опорой внизу по центру, без перекладки (ВР-VS3-08);
  - рамка `card.frame.hover` (кромка `card.cream` 1,0);
  - кэп ВР-CP04: scale ≤ 1,6 / scale скана (`HoverScaleFor`); при 2160p 150 % — 1,077 вместо 1,5;
  - reduced motion — масштаб без твина.
- `SetSelected(bool)`:
  - `card.frame.selected` (`state.pending` 3 su);
  - выбранная и наведённая одновременно — тоже кромка выбора.
- `SetFocus(bool)`:
  - кольцо `card.frame.focus` снаружи keyline: зазор 2 su, кольцо 2 su (отрицательный отступ слоя 4 su);
  - появление за 100 мс; кромка рамки при этом не меняется.
- `SetLowered(bool)` (SD-26): в опущенной руке наведение не даёт превью. Мини-показы превью не дают тоже.
- Курсор `Hand`. Нажатие — на отпускании (`FS09HudPressArbiter`). `Unmatched.S09.HudPress.Card`:
  - n = 24, удержание 0 и 50 мс, повторный `ApplyModel` во время удержания — 0 потерь;
  - увод указателя — без действия;
  - неиграбельная карта — 24 отказа с `why.*`.
- UE `Unmatched.S08.Hud.Card.Hover` проверяет:
  - в покое 1, на 75 мс — между 1 и 1,5, на 150 мс — 1,5;
  - кромки hover / selected / idle;
  - фокус 50 / 100 мс;
  - lowered, кэп при 3 px/su, reduced, мини.

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-17/motion-normal.png` — sha256 `ffe0e81bfc308b36…`
- `CP-17/motion-reduced.png` — sha256 `43e0e4d069e17dc1…`
- `CP-17/rest-1080-100.png` — sha256 `94c4f673c6579a71…`

Что видно (Read):
- 0 / 75 / 150 / 500 мс: normal, hover (рост от низа по центру до 1,5), selected (teal 3 su), selected+hover, focus
  (белое кольцо снаружи с зазором, не совпадает ни с hover, ни с selected), lowered+hover (без превью), flash
  (белая кромка гаснет к 500 мс).
- В галерее наведённая карта ложится под соседнюю справа: порядок над соседями задаёт владелец HAND (CP-17 `do`).
  Это отметка для HB-24, не дефект виджета.
- Reduced: масштаб сразу, без твина.
