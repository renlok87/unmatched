# CP-06 — рубашка Medusa во всех показах

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-06. Всё как у
[CP-05](../CP-05/README.md): обрезка боков 5 px из 768, contain, рамка CP-13, мини — `card.frame.mini`, откат
`-S08CardArtLegacy`. Общее — [README CP-15](../CP-15/README.md).

**Статус:** технически импортировано. Коммиты `f24ca3c1` (импорт: `--backs` → `unchanged`) и `67a57467` (показ). Кадры
B и C в партии — шаг «Кадры».

Трасса: `CARD-ART key=back:medusa lang=back tex=/Game/S08/UI/CardBacks/T_CardBack_medusa.…` (страница 10 галереи).

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-06/back-medusa-row.png` — sha256 `ad03761acecb404c…`
- `CP-06/back-medusa-48x67.png` — sha256 `6dee24bd4d629a13…`
- `CP-06/back-medusa-32x45.png` — sha256 `03592a4be45dd84b…`
- `CP-06/back-medusa-150x208.png` — sha256 `2e950ceaa0c9d1c3…`
- `CP-06/back-medusa-230x319.png` — sha256 `e9784f608ceeff1d…`
- `CP-06/back-medusa-inspector.png` — sha256 `369522828f91b922…`

Что видно (Read): логотип и «MEDUSA | HARPIES» целы; при 48×67 читаются зелёный круг и змеи, при 32×45 — круг; в сером
круг светлый, змеи тёмные — форма, не цвет, отличает от рубашки King Arthur.

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/CP-06/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: рубашки Medusa в OPP-HAND и на краю боя (закрытая карта атаки Medusa у защитника King Arthur).

Статус по правилу карточки — «технически импортировано»; кадры подтверждают.
