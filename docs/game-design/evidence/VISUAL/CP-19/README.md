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

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/CP-19/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: кандидаты сброса (кромка card.frame.warning у всей руки 9/7) и отмеченная карта (опущена, значок card-drop) на DISCARD_CARDS; в сером отмеченная отличима формой (сдвиг и значок).

**Вердикт: художественно принято, по делегированию (2026-10-07).**
