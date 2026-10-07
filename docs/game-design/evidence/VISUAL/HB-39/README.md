# HB-39 — журнал: `UUmHudLog` (шаг H11)

VS-4, шаг V2 (H5 + H11), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `6cdec6e1`.
Карточка — `hud.csv` HB-39; 04 §2.10 (с дельтой VS-4), §4.3, §5.2 (H11), §7.1; принятый макет HB-38
(`art/imagegen/hud-feed-v1-codex/`, ВР-VS2-HB38-05, -16, -20), ВР-H07, ВР-78. Тот же коммит — [HB-40](../HB-40/README.md)
(тосты), [HB-41](../HB-41/README.md) (субтитры), [HB-36](../HB-36/README.md) (тост-триггер).

**Статус:** блок, WBP, подключение, строка, тесты и лист галереи готовы, по делегированию. Живой кадр H11 из партии
(6 / 3 строки, скрыт в бою — check-trace живой трассы на обеих досках) — шаг «Кадры» (упаковка в этом шаге запрещена).
**Откат:** `-S08SlateHud=log` — три строки Slate над рукой, блок не строится.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. `UUmHudLog` | `S08/UI/UmHudLog.h/.cpp`, `/Game/S08/UI/Hud/WBP_UI_HUD_LOG`. BindWidget `Lines` (`UVerticalBox`, пул строк), `Scroll` (`UScrollBox`); ещё `Panel`, `Root`, `Title`, `Empty`. Вход — `Push(FUmLogEntry)` на каждую новую строку `FS09EventFeed` (хук `UmHudLogTrail` в `TickOpponentView`, одна строка) и `ApplyModel(TArray<FUmLogEntry>)`. |
| 2. Строка | 22 su: полоса команды 4 su у левого края (`team.p1.screen` / `team.p2.screen`), «Х{n}» `type.caption` `text.secondary` в 12 su, текст `type.body` с 48 su одной строкой с «…» (`ETextOverflowPolicy::Ellipsis`), полный текст — подсказка; последняя строка `text.primary`, остальные `text.secondary`. Чипа нет (ВР-78). Текст — `UmHudLog::DescribeTrail`: та же структура, что `FS09EventFeed::Describe` / `DescribeEffect`, но через `ms.log.*` на языке UI. Клик по строке, где карта известна, — инспектор этой карты. |
| 3. Бой | пока на экране бой (окно защиты или постановка) — скрыт за 150 мс (`hover.ms`), после боя появляется так же. |
| 4. Класс S | колонки нет; слот GAME `Log` в S — список 360 × 320 под TOP (левый край TOP, низ TOP + 8); «Журнал» (`UUmHudTop.LogButton`) открывает и закрывает его; закрывают клик вне списка и вне TOP, Esc, начало боя. Список может лежать над полем, пока открыт (04 §2.10). |
| 5. Строки | `hud.log.title`, `hud.log.empty`, `ms.log.*`; новый ключ `hud.log.turn` (RU «Х{n}», EN «T{n}») — `st-hud.csv`, `ST_Hud`, `Game.locres` пересобраны `hud_strings_build.py build`; 04 §2.10 теперь пишет ключ кодом. |
| 6. `SHOT widget` | `id=UI-HUD-LOG impl=umg state=lines=<n>|hidden … total=<k> class=L|S open=0|1 scroll=<su> atEnd=0|1` — без текста. Строки трассы: `HUD-LOG add seq= turn= team= card= total=`, `HUD-LOG shown= total= hidden= open= class=`, `HUD-TOP press=log target=UI-HUD-LOG open=0|1`, `HUD-LOG list close=input`. |
| 7. Slate | `AddEventFeedLines` рисует три строки над рукой только с `-S08SlateHud=log`. |
| 8. Тест | `Unmatched.S08.Hud.Log.Feed` (`S08/UI/UmHudFeedTests.cpp`): строка прогона I на RU со стрелкой, эффект и «без движения», буст и «и ещё 2», «Х3»; 60 строк → 50, последняя `text.primary`, подсказка — полный текст, полосы команд; автопрокрутка следует за новой строкой и ждёт, пока игрок листает (Slate-раскладка `UScrollBox` в тесте); бой — `state=hidden` и `Collapsed`; 6 / 3 / 12 строк; бюджет. |

## Геометрия

- 1080p: (24, 712, 300, 200), шапка (12, 8), строки с y + 40, 6 видимых, остальные — колесом.
- 720p: (24, 688, 300, 104), 3 строки с y + 38: 38 + 3 × 22 = 104 (ВР-VS4-24).
- Класс S: (16, 64, 360, 320) при 1080p 150 %, 12 строк с y + 40, дорожка прокрутки 4 su только при избытке.
- LOG не пересекает FIELD (`HUD-LAYOUT overlapField=0`, гейт check-trace) и фигуры: пересечение прямоугольника LOG с
  рамками шести фигур масок HB-07 (+ 4 px) — 0 px² на Marmoreal и Sarpedon, 1080p и 720p (VS-3 п. 15: прежняя лента
  Slate закрывала King Arthur на малом холсте; новая — в левой колонке).

## Решения по делегированию (шаг V2)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-24 | 720p: первая строка с y + 38 вместо y + 40 макета | 3 строки по 22 su ровно в прямоугольник 104 su; при y + 40 нижние 2 su третьей строки выходят за панель |
| ВР-VS4-32 | «Х{n}» — счётчик хода последнего применённого снапшота с seq ≤ seq события в ход действовавшего игрока (иначе — любого снапшота ≤ seq); полоса — команда бойца по `S08TeamLook` (абсолютный или относительный режим доски) | MS-LOG приходит после снапшота, который уже передал ход (ВР-VS2-HB38-16); цвет команды — как на доске |
| ВР-VS4-33 | Текст строки — короткий список ходов (MS-E-106, «и ещё N»), подсказка — все ходы; имя карты на языке UI, если карта в открытом сбросе (`nameRu`); её id — для инспектора | многоточие режет только строку журнала, полный текст доступен |
| ВР-VS4-34 | LOG скрыт, пока на экране бой: окно защиты (`combatInfo`) и постановка | колонка краёв боя (24, 360…) накрывает LOG на 1080p |
| ВР-VS4-35 | Три строки Slate — только на откате, без исключения для `-S09Markers` | гейты читают `MS-LOG` из трассы, не пиксели ленты |

## Проверки

- Сборка UnmatchedEditor в worktree — `Result: Succeeded` (`C:/tmp/visual/vs4-v2/build-12.log`), игровая цель
  `Unmatched Win64 Development` — `Succeeded` (`build-game-2.log`).
- UE: новые тесты 9 из 9; `Unmatched.S08.Hud.*` — 89 из 89 (`ue-tests-hud-1.log`); `Unmatched.S08 + S09 + S10` — 491 из
  491 (`ue-tests-full-1.log`). Строки `Condition failed` в кадре 0 — шум старта движка (как в VS-3 / V1). Бюджет:
  тик журнала p95 0,0009 мс (≤ 0,03).
- `hud_strings_build.py check` — PASS (ST_Hud 96, ключей 04 — 151); `hud_contract.py validate` — PASS (G-TOKENS);
  `hud_tokens_codegen.py --check` — FRESH; pytest `tools/s08` — 133 passed.
- `check-trace` — PASS на 8 трассах галереи (63 строки SHOT widget в каждой): `lines=6` на 1080p, `lines=3` на 720p,
  `hidden` в бою, `lines=6` списка S.
- WBP: `C:/tmp/visual/vs4-v2/um-hud-wbp-report.json` — `WBP_UI_HUD_LOG` created, up-to-date (остальные не перезаписаны).

## Лист

Галерея `-S08IconGallery -S08IconGalleryFeed=marmoreal|sarpedon` (editor `-game`, один клиент, `t.MaxFPS 30`,
`-RenderOffScreen`), 9 состояний на 8 холстах, — см. [HB-40](../HB-40/README.md#лист). Журнал: состояние 0.

- В git (без доски и сканов): лист HB-40 `plain-*-contact-*.png` и `plain-crops-*.png` — журнал L 1080p и список S 720p
  150 %.
- Вне git (кадр доски, сканы в руке — ВР-VS4-01): `scraped-data/derived/visual-evidence/HB-39/` — вырезки колонки L
  (1080p и 720p обеих досок) и списка S (1080p 150 % и 720p 150 % обеих досок) в родных пикселях, цвет и серый; путь,
  sha256, размер — [`visual-evidence-index.json`](visual-evidence-index.json).

Что видно (Read: вырезки, контакт Marmoreal 720p 150 % и Sarpedon 1080p 100 %, plain-листы): «Журнал», шесть строк прогона
I на 1080p и три последние на 720p, полосы Medusa (жёлтая) и King Arthur (синяя), «Х1…Х4», последняя строка светлее,
многоточие в длинных строках; в списке S строка «Medusa: манёвр: Medusa M13→M25» целиком — **стрелка U+2192 рисуется**
составным шрифтом темы (`DroidSansFallback`, ВР-VS2-HB38-20). В бою (состояние 8) журнала нет.

## Что не сделано в этом шаге

- Живой кадр H11 из партии и check-trace живой трассы на обеих досках — шаг «Кадры».
- Строки журнала о бое и о событиях без `metadata.lastMovement`, пропуск при восстановлении (`eventsSince`) — источника,
  кроме `FS09EventFeed`, пока нет: журнал показывает то же, что MS-LOG (манёвры и эффекты со следом хода).
