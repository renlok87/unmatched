# HB-27 — фишки колоды и сброса: UUmHudDecks (шаг H8)

VS-3, шаг U3, 2026-10-07, ветка `feat/visual-vs3` (worktree `C:/tmp/wt-visual`). Карточка — `hud.csv` HB-27; 04 §2.9,
§1.6, §7.1, ВР-H16; принятый макет HB-26 `art/imagegen/hud-decks-v1-codex/` (D6, ВР-VS2-HB26-06 / -09, «Дельта 04»).
Панель колоды — [HB-28](../HB-28/README.md) (там же листы, кадры, проверки и решения общего кода).

**Статус:** блок, WBP, трасса, тесты, лист галереи и живая проверка на одном клиенте готовы. Код — коммит `4a3ca23b`
(вместе с HB-28). Приёмочные кадры в партии (обе доски; idle и stale через `tools/s10/drop-graphql-reply-proxy.cjs`) — шаг
«Кадры» VS-3. Приёмка — «по делегированию», в едином проходе ревью VS-3.
**Откат:** `-S08SlateHud=decks` — блок не строится, в Slate-боковой панели снова кнопки «BROWSE DISCARD PILES (D)» и
«YOUR DECK (K) / OPP DECK (Shift+K)»; трасса `HUD-DECKS-UMG impl=slate`.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. `UUmHudDecks`, BindWidget `DeckChip`, `DiscardChip` (`UUmButton` Normal, высота 56 / 48), `DeckCount`, `DiscardCount`; `ApplyModel` | `S08/UI/UmHudDecks.{h,cpp}`. Дерево: `Row` (Canvas) > `DeckChip`, `DiscardChip`; поверх (не ловят указатель) `DeckMiniBox` > `DeckMiniScale` > `DeckMini` (`UUmCardWidget`), `DiscardMini…`, `DiscardIcon`, `DeckCount`, `DiscardCount`. Модель `FUmDecksModel` собирает `UmHudDecks::Gather(ViewerPanel(), слаг своего героя)`: `DeckCount`, `bDeckCountStale`, `Discard` (верх — последняя запись), `bDiscardStale`. `/Game/S08/UI/Hud/WBP_UI_HUD_DECKS` сгенерирован из того же дерева, `git add -f`. |
| 2. Мини-рубашка и верхняя карта сброса | `UUmCardWidget` показ `MiniChip` 32×45 (CP-15): колода — рубашка своего героя лицом вниз (CP-05 / CP-06), сброс — скан верхней карты (лицом вниз, если запись закрыта). Класс S — тот же виджет в `UScaleBox` 18×25,3 su (HB-26 fix1). Пустой сброс — значок v3 `resource-card` (IC-19). |
| 3. Клики | колода — `ToggleDeckPanel(Own)` (панель «Ваша»); сброс — та же панель с фильтром «Только сброс» (`OpenUmDeckDiscard`, ВР-VS3-43). Нажатие — арбитр (`hud.decks.deck` / `hud.decks.discard`, DE-014), ответ CUE-003 в кадре отпускания. |
| 4. Строки | `hud.decks.deck` «Колода {n}», `hud.decks.discard` «Сброс {n}», `hud.decks.stale` «≈{n}» (подставляется вместо числа); в классе S — только число. Шрифт 20 su Roboto Bold Condensed, не капс, табличные цифры. |
| 5. Центры фишек → `FUmHudLayout` | `UmHudLayout::DeckChipRect` (L RU 156 / 124, EN 144 / 136 × 56 su; S 64 × 48; зазор 8), `FUmHudLayout::bEnglishChips` по языку UI; `DeckChipCentreSu` / `DiscardChipCentreSu` — центры этих фишек: добор HB-24 летит от фишки колоды (1080p RU — (1686, 948)), карты боя (HB-32) — к фишке сброса. |
| 6. `SHOT widget` | `SHOT widget id=UI-HUD-DECKS impl=umg state=idle\|stale … class=L\|S deck= discard= deckStale= discardStale= top=face\|back\|none chips=<w>x<h>,<w>x<h> lang=ru\|en icon=<su>` — без имени карты. |
| 7. Slate-кнопки | «YOUR DECK (K)», «BROWSE DISCARD PILES (D)» строятся только при `-S08SlateHud=decks` (`S08FlowGameMode.cpp`, +2 условия). K / Shift+K / D работают в обоих видах. |
| 8. Тест | `Unmatched.S08.Hud.Decks.Counts` и `.Tree` (`S08/UI/UmHudDecksTests.cpp`). |
| 9. Значок стопки ≥ 24 px | `UmHudDecks::IconSuFor`: 32 su при DPI × масштаб UI < 1 (720p 100 % — 24 px), иначе 24 su (IC-34 П-1); тест проверяет оба. |

Геометрия фишки (HB-26 «Дельта 04»): класс L — мини-карта 32×45 в 9 su от левого края (кромка на 8), текст с 50 su, по
центру высоты 56; класс S — мини-карта 18×25,3 в 5 su, число с 28 su, высота 48. Вся пара заполняет DECKS (288 su в L,
136 в S): 1080p `bbox=(1608,920,1896,976)`.

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS3-35 | Ширины фишек — числа HB-26 по языку UI (RU 156 / 124, EN 144 / 136), а не замер текста: пара всегда заполняет DECKS, ширина не прыгает при «≈» и двузначном числе | ВР-VS2-HB26-09 приняты для «Колода ≈24» и EN «Discard 2» без уменьшения кегля |

Общие решения панели и фишек — ВР-VS3-36…48 в [HB-28](../HB-28/README.md).

## Проверки

- Тесты: `Unmatched.S08.Hud.Decks.Counts` — RU «Колода 23» / «Сброс 2», stale «Колода ≈24» / «Сброс ≈2», класс S «23» / «2»,
  верх сброса Feint лицом вверх, закрытый верх — рубашка, пустой сброс — значок 32 su на 720p 100 % и 24 su на 1080p,
  прямоугольники HB-26 на четырёх холстах RU и EN, центры полётов на фишках, строка SHOT (idle, bbox DECKS, без имени
  карты), по одному нажатию на фишку через арбитр, тот же снимок — без работы. `ApplyModel` при меняющемся снимке
  p50 0,0033 / p95 0,0044 мс (бюджет 0,02 мс GT p95). Все UE-тесты шага — в [HB-28](../HB-28/README.md#проверки).
- Живой клиент (`-Bench -BenchDeckPanel`, Marmoreal): `SHOT widget id=UI-HUD-DECKS … state=idle … bbox=(1608,920,1896,976)
  geom=painted … deck=25 discard=0 top=none`, кадр `bench-own-1080-100`: «Колода 25» с рубашкой Medusa, «≡ Сброс 0».
- Галерея: «Колода 23» / «Сброс 2» с рубашкой и сканом Feint (Marmoreal), «Колода 25» / «Сброс 2» с рубашкой King Arthur
  и сканом Swift Strike (Sarpedon), stale «≈24» / «≈25», класс S — числа, EN «Deck 25» / «Discard 2»
  (`scraped-data/derived/visual-evidence/HB-28/*`, хэши в README HB-28; в git — `plain-legacy-*` HB-28).

## Что не сделано в этом шаге

- Кадр набора E со stale в живой партии через `drop-graphql-reply-proxy.cjs` — шаг «Кадры».
- Полёт карт боя к фишке сброса — HB-32 (H9); центр фишки уже в раскладке.

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/HB-27/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: фишки «Колода n» / «Сброс n» при 1080p 100 % и 75 %, 720p 100 %, класс S (1080p 150 %, 720p 150 %: «≈25», «0» со значком resource-card); «≈» у устаревшего числа есть на живых кадрах (трасса `stale` 635 строк). Мини-карта сброса — верхняя карта.

**Вердикт: художественно принято, по делегированию (2026-10-07).**
