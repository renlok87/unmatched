# CP-16 — состояния покоя: обычная, можно / нельзя сыграть, новая

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-16; 02 §6.3, §4.3, §11.2;
04 §2.6. Общее — [README CP-15](../CP-15/README.md). Коммит `67a57467`.

**Статус:** API виджета, тест и лист движения готовы. Кадры набора A в партии (рука 7 карт, защиты недоступны вне боя,
одна новая после добора; обе доски; 1080p и 720p) — после HB-24 (HAND решает «можно / нельзя», ведёт таймер 10 с и
«первое наведение», показывает `why.*` по наведению), шаг «Кадры».
**Откат:** `-S08SlateHud=hand` (у владельца).

## Что сделано

- `UUmCardWidget::SetPlayable(bool, FS09Reason)`:
  - MID `Desaturation` 0 → 0,6 и `Opacity` 1 → 0,7 за `hover.ms` 150 (линейно);
  - при reduced motion — за 100 мс (`reduced.max_ms`);
  - рамка не меняется (`panel.edge`);
  - курсор `SlashedCircle`;
  - `GetWhyText()` — текст причины из ST_Why для подсказки HAND;
  - нажатие на неиграбельную карту отвечает `Refused` с этой причиной.
- `SetNew(bool)`:
  - точка `card.frame.new` (8 su `card.glyph` + keyline 1 su), центр в 10 su от правого и верхнего края рамки;
  - появление — ключи icon-motion `appear`: 0 мс — 0,80 / 0,15; 72 мс — 1,04; 120 мс — opacity 1; 180 мс — 1,00;
  - уход — 120 мс: opacity → 0, scale → 0,92;
  - reduced motion — только прозрачность за 100 мс.
- Трасса: `state=unplayable`, `state=new`, вместе — `state=unplayable+new`.
- UE `Unmatched.S08.Hud.Card.States` проверяет:
  - 75 мс — на полпути; 150 мс — 0,6 / 0,7;
  - рамка прежняя, курсор, `why.*`;
  - точка по ключам 0 / 72 / 120 / 180 и уход за 120 мс;
  - reduced: 0,5 на 50 мс без масштаба.

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-16/motion-normal.png` — sha256 `431161e8aa0b8c20…`
- `CP-16/motion-reduced.png` — sha256 `00c16529e7898012…`
- `CP-16/rest-1080-100.png` — sha256 `7d8b22b7b0fa5462…`

Что видно (Read; точка ×4 — `C:/tmp/visual/VS3-U1/view-newdot-x4.png`):
- Рука 7 карт King Arthur; Bewilderment и The Holy Grail недоступны вне боя. Их скан на 150 мс бледный и прозрачный,
  рамка прежняя; в сером они явно тусклее.
- Причина под рукой: «Карта защиты — ждите атаки» (`why.defense.only.in.combat`, ST_Why).
- Точка у Swift Strike: 0 мс — бледная и малая, 72 мс — 1,04, 120 мс — полная, 180 мс — в покое. Белая точка с тёмной
  keyline видна на кремовой кромке скана.
- Reduced: 0 / 50 / 100 мс — только прозрачность.
