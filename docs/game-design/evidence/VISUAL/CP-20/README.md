# CP-20 — рубашкой вверх и переворот при раскрытии боя (CUE-010)

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-20; 07 CUE-010;
`S09CombatStage.h` `FS09CombatTiming`; 04 §2.7, §1.7; F-01; SD-04, SD-48; ВР-CP13. Общее —
[README CP-15](../CP-15/README.md). Коммит `67a57467`.

**Статус:** API виджета, тест и лист кадров по времени готовы. Владелец — `UUmHudCombatEdge` (HB-30…HB-33, H9): он
вызывает `Flip` по `FS09CombatStage` (атакующая — старт CUE-010, защитная — `ShowsDefenseFace`). Поэтому кадры C
обоих клиентов, трассы `CUE fx CUE-010` и `SHOT widget id=UI-HUD-COMBAT-EDGE state=back → reveal` и G-CUE — после H9,
шаг «Кадры».
**Откат:** `-S08SlateHud=combat` (у владельца).

## Что сделано

- `Flip(bool bToFace, float SpeedMul, const FS09CardView* Face)`:
  - render transform scaleX с опорой по оси x в центре: 80 мс до ребра (ease-in-quad), смена лица, 80 мс (ease-out-quad);
  - длительность × скорость боя (0 — мгновенно, 0,5 быстро, 1,5 медленно).
- Защитная карта начинает на `UmCardWidget::DefenseFlipDelayMs(speed)` = 120 × скорость позже. Переворот 160 +
  задержка 120 укладываются в `FlipMs` 620.
- Приватность (ВР-VS3-11):
  - до раскрытия в виджете только рубашка (`ApplyModel(…, bFaceDown)`);
  - лицо приходит в `Flip(true, …, Face)` и назначается в кадр ребра, когда карта не видна;
  - текстура может догружаться в первой половине переворота;
  - трасса до ребра — `key=back:<hero> lang=back`, без имени карты.
- После раскрытия — `state=reveal`; скан целиком 230×319 su (показ `Combat`).
- Reduced motion — кроссфейд лица 100 мс через подложку (ВР-VS3-10).
- Плоско, без 3D и перспективы (ВР-19), карта не двигается с места (SD-48 п. 4), без Niagara (ВР-74).
- UE `Unmatched.S08.Hud.Card.Flip` проверяет:
  - 40 мс — scaleX 0,75, ещё рубашка, лица в виджете нет;
  - 80 мс — ребро и смена; 120 мс — 0,75; 160 мс — лицо;
  - защитная: 199 мс — рубашка, 200 мс — лицо, 280 мс — конец;
  - задержка 60 / 120 / 180 при скорости 0,5 / 1 / 1,5;
  - скорость 0 — сразу; reduced — 25 / 50 / 100 мс.

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-20/motion-normal.png` — sha256 `09551340d624411c…`
- `CP-20/motion-reduced.png` — sha256 `a86985807754d943…`
- `CP-20/rest-1080-100.png` — sha256 `61f3e36a19b54d50…`

Что видно (Read):
- 0 мс: обе карты рубашкой (King Arthur — атака, Medusa — защита).
- 40 мс: атакующая сужена до 0,75.
- 80 мс: ребро — атакующей нет совсем, ни лица, ни рубашки.
- 120 мс: Экскалибур расширяется.
- 160 мс: Экскалибур целиком; защитная начала с 120 мс и сужается.
- 200 мс: ребро защитной.
- 280 мс: «Шипеть и извиваться» целиком.
- Карты с места не двигаются, перспективы нет.
- Reduced: кроссфейд 100 мс через подложку, защитная — с 120 мс.

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/CP-20/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: итог переворота — лица карт атаки и защиты на обоих краях у обоих клиентов; в кадре `s09-damage-combat` (Marmoreal 720p 150 %) правая карта снята посреди переворота (сжата по ширине). G-CUE CUE-010 — PASS.

**Вердикт: художественно принято, по делегированию (2026-10-07).**
