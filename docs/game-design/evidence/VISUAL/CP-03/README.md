# CP-03 — колода King Arthur: 16 карт (30 копий), RU- и EN-сканы

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-03; 04 §6.2, §7.4; 02 §3.4;
ВР-48, ВР-49, ВР-51, ВР-CP16. Виджет, показы и общие решения — [README CP-15](../CP-15/README.md). Medusa —
[CP-04](../CP-04/README.md) (там же раздел про RU-названия).

**Статус:** технически импортировано (оригинальный арт как есть; художественной приёмки строка не требует — рамка и
показ принимаются в CP-13 / CP-15). Коммит `f24ca3c1`. Кадр набора A в партии (рука Arthur, packaged `-Bench`, обе
доски, шесть фигур v2, трасса `CARD-ART lang=ru` у каждой карты руки) — после HB-24 (рука на `UUmCardWidget`), шаг
«Кадры».
**Откат:** `-S08CardArtLegacy` — фолбэк 02 §6.1 без сканов.

## Что сделано

| Пункт `do` | Где |
|---|---|
| 1. Прогон `--cards king-arthur` | Текстуры импортированы ещё в CP-02 (`--all`). Повторный прогон в worktree: `CARD-MEDIA-IMPORT PASS mode=cards textures=60 imported=0 reimported=0 unchanged=32 kept=28` (sha256 источников совпали, настройки на месте). Текстуры `/Game/S08/UI/Cards/king_arthur/T_Card_king_arthur_<card>_{RU,EN}` вне git (GAP-019 / ENV-U3). |
| 2. Ключ — slug героя владельца колоды и EN-имени карты | `king-arthur:<card>`; у карт Merlin герой — King Arthur. Тот же слаг в клиенте — `UmCardWidget::Slug` (ВР-VS3-13). |
| 3. 16 ключей = колода бэкенда, сумма копий 30 | pytest `tools/art/cards/test_card_decks.py::test_deck_keys_are_the_backend_decks`: ключи реестра = карты `docs/game-design/evidence/S01/content-king-arthur.json` (ответ контент-API S01 = `gameDeckLists`), 16 карт, 30 копий; у каждой RU и EN. Снимок эталонной БД `:5433` (`art/cards-v1/card-names-db.json`, только чтение): те же 16 карт, те же `count`. UE `Unmatched.S08.Hud.Card.Key`: 32 текстуры находятся по ключу и грузятся. Feint и Regroup Arthur — свои сканы (`test_feint_and_regroup_are_two_cards_each`). |
| 4. ВР-CP16: RU-названия — только из данных; расхождения — в отчёт импорта | `art/cards-v1/ue-import-report.json`, раздел `ruNames` (`tools/art/cards/card_deck_names.py`, его пишут и UE-прогон, и `--write-names`). Для Arthur: 14 карт без RU в скрапе (`no-ru-in-scrape`; есть только «Уловка» и «Передышка»), у всех 16 `Card.nameRu` в эталонной БД — EN-текст (`nameRu-is-en`); что напечатано на RU-скане — справкой (`nameRuScan`). Правка — в админке `:5480`, не в клиенте. |
| 5. Строки `ASSET-CARDART-KING-ARTHUR-*` манифеста 06 → imported | `docs/game-design/06-asset-manifest.csv`: 16 строк — `unrealAssetPath` `/Game/S08/UI/Cards/king_arthur/T_Card_…_EN` (RU — в `variant`), `sourceHash` — sha256 EN-PNG из реестра, `verificationStatus imported`. |

## Решение шага

- **ВР-VS3-02.** Данные для RU-названий:
  - снимок эталонной БД `art/cards-v1/card-names-db.json` (`docker exec unmatched-postgres psql`, только `SELECT`);
  - контент S01;
  - скрап (`i18n.ru.title`);
  - надпись на RU-скане — только справка.
  `nameRu`, равный EN-имени, считается «перевода нет»: фолбэк показывает EN с меткой «EN» (INT-018 п. 3).
  Причина: в эталонной БД у всех 27 карт MVP `nameRu` = EN-текст.

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-03/compare-king-arthur-ru-1to1.png` — sha256 `0cc890c2802df99a…`
- `CP-03/compare-king-arthur-en-1to1.png` — sha256 `b83c9e4ff02b210c…`
- `CP-03/deck-king-arthur-ru-150x208.png` — sha256 `fb80fb92f6d2f909…`
- `CP-03/deck-king-arthur-ru-225x312.png` — sha256 `6f22dcbd6a46fdbc…`
- `CP-03/deck-king-arthur-en-150x208.png` — sha256 `03c82ba2c3c3da4e…`
- `CP-03/deck-king-arthur-en-225x312.png` — sha256 `06018bc77480f780…`

Что видно (все листы открыты, Read):
- 16 карт в RU и EN при 150×208 и 225×312 su (1080p 100 %), рядом исходник 1 : 1.
- Скан целиком, без обрезки, муара и ступенек. Название, значение и BOOST читаются при 225×312. При 150×208 они
  читаются, а мелкий текст эффекта — нет (скан 0,495×, как в 02 §6.2; для этого есть наведение и инспектор).
- В сером тип и значения различимы по форме блока типа и цифре.
- Подписи ячеек: слаг и «×копий» — 30 копий.
- Трассы: 32 строки `CARD-ART lang=ru|en` на страницу, scale рука 0,495 (RU) / 0,568 (EN), наведение 0,756 / 0,868 —
  все ≤ 1,0 при 1080p 100 %; ошибок `check_card_art_line` — 0.

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/CP-03/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: рука King Arthur — сканы RU (`lang=ru` у каждой карты руки в `HUD-HAND`), 150×208 su при 1080p (scale 0,495), обе доски.

Статус по правилу карточки — «технически импортировано»; кадры подтверждают.
