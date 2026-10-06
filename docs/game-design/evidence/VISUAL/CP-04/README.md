# CP-04 — колода Medusa: 11 карт (30 копий), RU- и EN-сканы

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-04; 02 §3.4, §6.1; 04 §6.2;
ВР-CP16. Общее — [README CP-15](../CP-15/README.md); импорт и проверка ключей — как в [CP-03](../CP-03/README.md).

**Статус:** технически импортировано (оригинальный арт как есть). Коммит `f24ca3c1`. Кадр набора A в партии (рука
Medusa) — после HB-24, шаг «Кадры».
**Откат:** `-S08CardArtLegacy`.

## Что сделано

| Пункт `do` | Где |
|---|---|
| 1. Прогон `--cards medusa` | `CARD-MEDIA-IMPORT PASS mode=cards textures=60 imported=0 reimported=0 unchanged=22 kept=38`. Текстуры `/Game/S08/UI/Cards/medusa/T_Card_medusa_<card>_{RU,EN}` вне git. EN-скан Dash — из WebP (CP-01). |
| 2–3. 11 ключей = колода бэкенда, 30 копий | pytest `test_card_decks.py`; UE `Card.Key`: 22 текстуры находятся и грузятся. |
| 4. ВР-CP16 в отчёт импорта | `ruNames`: `medusa:second-shot` — данные / скрап «Двойной выстрел», на скане «Второй выстрел» (`scan-differs`); у всех 11 `Card.nameRu` в эталонной БД — EN-текст (`nameRu-is-en`; RU есть в скрапе у всех 11). |
| 5. Строки `ASSET-CARDART-MEDUSA-*` → imported | 11 строк манифеста 06. |

Самое длинное название — «The Hounds of Mighty Zeus» / «Гончие могучего Зевса»: на скане целиком при 150×208 и
225×312 (лист ниже), в фолбэке — два переноса строки при 150×208 (лист CP-15).

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-04/compare-medusa-ru-1to1.png` — sha256 `44b1fccff822c723…`
- `CP-04/compare-medusa-en-1to1.png` — sha256 `c1e17297ed0973be…`
- `CP-04/deck-medusa-ru-150x208.png` — sha256 `31988911828164a9…`
- `CP-04/deck-medusa-ru-225x312.png` — sha256 `bf17265701c95320…`
- `CP-04/deck-medusa-en-150x208.png` — sha256 `9e70aaa157fd6f7a…`
- `CP-04/deck-medusa-en-225x312.png` — sha256 `8a4c4ebe47f06c5c…`

Что видно (Read): 11 карт RU и EN, целиком, исходник 1 : 1 рядом; «Гончие могучего Зевса» и «The Hounds of Mighty Zeus»
не обрезаны; в сером Medusa и гарпии различимы по блоку героя. Трассы: 22 строки на страницу, scale ≤ 0,868, ошибок 0.
