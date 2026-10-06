# CP-19 — сброс по лимиту руки

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-19; 02 §6.3, §5.5, §2.4;
04 §2.6, §2.8, §2.5; SD-42. Общее — [README CP-15](../CP-15/README.md). Коммит `67a57467`.

**Статус:** API виджета, тест и лист движения готовы. Кадр D «сброс по лимиту» в партии (Marmoreal original, 1080p
100 % и 720p 150 %) — после HB-24, шаг «Кадры». Счётчик «выбрано h/n» и «Подтвердить» с `why.discard.count` — блок
PENDING (H10). Отмены у лимита нет (04 §2.8).
**Откат:** `-S08SlateHud=hand` (у владельца).

## Что сделано

- `SetDiscardCandidate(bool)`: кромка `card.frame.warning` (`state.warning` 2 su), смена кисти в кадр события.
- `SetMarkedForDiscard(bool)`:
  - сдвиг вниз на 16 su за 150 мс (render transform, ease-out-quad);
  - значок `card-drop` 24 su по центру верхнего края: появление 180 мс, уход 120 мс;
  - снятие отметки — обратно за 150 мс;
  - reduced motion — сдвиг без твина, значок по прозрачности за 100 мс.
- Отмеченная отличается от кандидата формой (сдвиг и значок), не только цветом.
- Трасса `state=discard`, у отмеченной — `state=discard+marked`.
- UE `Unmatched.S08.Hud.Card.Discard` проверяет: кромка кандидата; 75 мс — по пути; 150 мс — 16 su; значок на 180 мс;
  снятие отметки; reduced.

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-19/motion-normal.png` — sha256 `d6628515f9f75cc3…`
- `CP-19/motion-reduced.png` — sha256 `83fc1b9bbae82d0f…`
- `CP-19/rest-1080-100.png` — sha256 `470a7c9c53642674…`

Что видно (Read): рука Medusa из 8 карт, все — кромка `state.warning` 2 su; Snipe и Regroup отмечены — опускаются на
16 su к 150 мс, над ними значок `card-drop`; в сером отмеченные отличаются сдвигом и значком, кромка кандидата светлее
idle. Reduced: сдвиг сразу, значок по прозрачности.
