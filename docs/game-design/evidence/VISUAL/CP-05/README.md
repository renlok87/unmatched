# CP-05 — рубашка King Arthur во всех показах

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-05; 02 §6.2, §6.4; 04 §2.3,
§2.7, §2.9, §1.7; ВР-50, ВР-CP05 (уточнено ВР-VS2-CP-03), ВР-CP06. Общее — [README CP-15](../CP-15/README.md).

**Статус:** технически импортировано. Коммит `f24ca3c1` (импорт), показ — `67a57467` (виджет). Кадры B (OPP-HAND с
рубашками King Arthur 48×67 у соперника) и C (CardBack 230×319 у защитника) в партии — шаг «Кадры» после H9;
OPP-HAND рисует ту же текстуру с VS-2 (HB-21).
**Откат:** `-S08CardArtLegacy` — плашка card.navy с `resource-card` 24 su.

## Что сделано

| Пункт `do` | Где |
|---|---|
| 1. `--backs` → `/Game/S08/UI/CardBacks/T_CardBack_king_arthur`, pad 1024×2048, mip, BC7 | Импорт CP-02; повторный прогон `--backs`: `unchanged=2`. Вне git. |
| 2. Обрезка боков ≤ 1,4 %, затем contain; логотип цел | По ВР-VS2-CP-03 «cover по высоте» снят: `UmCardWidget::UvRect` режет 5 px с каждой стороны из 768 (1,30 %), затем contain в окне. Тест `Card.Fit`: UV 5/1024 … 763/1024. |
| 3. Тот же материал и рамка, мини — radius.s | `M_UmCardFace`, рамка CP-13: мини 48×67 и 32×45 — `card.frame.mini` (radius.s 4, полоса 2 su). |
| 4. Реестр `back:king-arthur` | `Config/Cards/S08CardMedia.json` (CP-02). |
| 5. Одна рубашка на колоду (и для карт Merlin) | Ключ рубашки — герой владельца колоды (`FUmCardState::HeroSlug`). |
| 6. Откат | `IsLegacy()`: плашка и значок вместо рубашки (лист CP-15, ячейка «legacy back»). |

Трасса: `CARD-ART key=back:king-arthur lang=back tex=/Game/S08/UI/CardBacks/T_CardBack_king_arthur.… show=…` (страница
9 галереи).

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-05/back-king-arthur-row.png` — sha256 `aba16492d0317efc…`
- `CP-05/back-king-arthur-48x67.png` — sha256 `60e8a9d06170303a…`
- `CP-05/back-king-arthur-32x45.png` — sha256 `d937fdc91b17b5ea…`
- `CP-05/back-king-arthur-150x208.png` — sha256 `45b95ac68039d4a2…`
- `CP-05/back-king-arthur-230x319.png` — sha256 `c4541fd3eebb71bc…`
- `CP-05/back-king-arthur-inspector.png` — sha256 `6e450f49fbc75268…`

Что видно (Read, мини ×4 nearest — `C:/tmp/visual/VS3-U1/view-backs-mini-x4.png`):
- Пять показов: 48×67, 32×45, 150×208, 230×319, инспектор.
- Логотип UNMATCHED и подпись «KING ARTHUR | MERLIN» целы во всех показах.
- Обрезка боков 1,30 % — рамка рисунка у краёв видна.
- При 48×67 читаются корона и меч, при 32×45 — силуэт короны.
- В сером рубашки King Arthur и Medusa различимы по рисунку: корона и меч на чёрном против змей в круге.
- Перекраски нет. Рамка — `card.frame.mini` у мини, `card.frame.idle` у остальных.
- Трасса: `key=back:king-arthur lang=back`, scale от 0,037 (32×45) до 0,596 (инспектор).
