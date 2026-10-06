# CP-09 — портрет King Arthur (общий отчёт шага B3: CP-09…CP-12)

VS-2, шаг B3, 2026-10-06, ветка `feat/visual-vs2` (worktree `C:/tmp/wt-visual`). Карточки —
`docs/game-design/visual/06-tasks/cards-portraits.csv` CP-09, CP-10, CP-11, CP-12; 02 §6.4, §6.5; 04 §1.4, §1.5, §1.10,
§2.2, §2.3; ВР-47, ВР-71, ВР-72. Здесь описано общее для четырёх карточек: реестр, код, решения ВР-VS2-63…69, проверки.
README CP-10, CP-11 и CP-12 ссылаются сюда и добавляют своё.

**Статус:** круги всех четырёх портретов взяты из принятого листа кадрирования CP-07 (`165c3be7 art(visual): CP-07
portrait-crop-v1 - accepted by delegation`, вариант B). Код, реестр, тесты, трасса и листы галереи готовы. Приёмочные
кадры packaged (Marmoreal original и Sarpedon original, шесть фигур v2, `-Bench` с отпечатком RENDER) — шаг «Кадры»
VS-2: упаковки в этом шаге нет. Показы ROOM, загрузка, GAMEOVER и LOBBY проверены на листе всех размеров. Самих экранов
на UMG ещё нет, их подключат шаги SC и H15.
**Флаг отката:** `-S08PortraitLegacy` (ВР-CP08). Он возвращает диск цвета команды с монограммой у героя, а мини-портреты
помощников показывают фолбэк: монограмму или цифру гарпии, без бейджа. Трасса — `tex=legacy`.

## Что сделано (CP-09, общее для CP-09…CP-12)

| Пункт `do` | Где |
|---|---|
| 1. Импорт `--portraits` → `T_Portrait_king_arthur`, pad 1024² | Текстура уже импортирована в CP-02. Повторный прогон `ue_import_card_media.py --portraits` (коммандлет, worktree) дал `CARD-MEDIA-IMPORT PASS mode=portraits unchanged=4`: sha256 исходников совпадают, настройки на месте, отчёт `art/cards-v1/ue-import-report.json` не изменился. Текстуры вне git (GAP-019 / ENV-U3). |
| 2. Реестр `portraits.king-arthur`: src 800², pad 1024², disc — вариант CP-07 | `tools/art/cards/ue_import_card_media.py` читает `art/imagegen/portrait-crop-v1-codex/portrait-crops.json` (CP-07). Числа ВР-CP01 остаются только запасом на случай, если файла нет. `Config/Cards/S08CardMedia.json`: King Arthur (0,49; 0,39; 0,54), Medusa (0,44; 0,29; 0,50), Merlin и гарпии (0,50; 0,48; 0,69), `discSource` = «CP-07 B (portrait-crop-v1, accepted by delegation 165c3be7)» |
| 3. Проверить все показы на листе и в кадрах | Новый лист галереи `-S08IconGallery -S08IconGalleryPanels=3`: настоящий `M_UmPortraitDisc` во всех размерах 32 / 64 / 80 / 120 / 160 su, а также проигравший 120, павший 80 и фолбэк «KA». Лист снят при 720p / 1080p / 1080p 150 % / 2160p / 2160p 150 % (×0,75 / ×1 / ×1,5 / ×2 / ×3). Числа круга не правились: глаза внутри центральных 60 % проверены на листе CP-07, а кадр UV тот же. |

Общий код шага (CP-10 и CP-12 используют его же):

- `S08/UI/UmPortrait.{h,cpp}`: `FUmPortraitShown` (что показано — ключ, текстура, размер показа и нарисованный размер,
  круг источника, состояние, номер), `UmPortrait::MakeDisc` (круг любого размера: аватар в материале с кэпом ВР-CP04 по
  центру, кромкой и состоянием, либо фолбэк на card.navy), `UmPortrait::MakeNumberBadge` (бейдж гарпии, CP-12).
  Кромка круга — 1 su mark.keyline + 1 su panel.edge (ВР-VS2-63). Трасса `PORTRAIT … capped=0|1 [n=1…3]`.
- `US08TurnPortraitWidget::PortraitShotLine` передаёт размер показа, и трасса пишет `capped`. `IsPortraitLegacy()` — для
  мини-портретов.
- `UUmHudPlayerPanel`: мини-портреты помощников через `MakeDisc`, бейдж через `MakeNumberBadge`,
  `CollectPortraitLines` / `GetMiniPortraits`; `FUmPanels::CollectShotLines` дописывает строки PORTRAIT помощников к
  строкам SHOT панелей. Так работает кадр-доказательство без новых точек в горячем файле.
- `FS08BoardModel::DecodeFighters`: номер одноимённых бойцов считается для каждого владельца отдельно (ВР-VS2-65).
- Лист галереи: `UUmPanelsGalleryWidget::BuildPortraits` (`UmHudGallery.cpp`). Страницы 1 и 2 пишут строки PORTRAIT героя
  и помощников каждой панели.
- Горячий файл `S08FlowGameModeUmHud.cpp` изменён на одну строку: `Clamp(PanelsPage, 1, 3)`, страница 3.
- `tools/s08/hud_contract/hud_contract.py check-trace`: у гарпии в PANEL нужен `n=1…3` (ВР-72).

## Решения по делегированию (ВР-VS2-63…69, шаг B3)

- **ВР-VS2-63. Кромка круга по принятому CP-07:** снаружи mark.keyline 1 su, внутри panel.edge (card.cream с альфой 0,45)
  1 su. Это заменяет 1,5 su из ВР-VS2-31: CP-07 нарисовал и принял рамку с двумя линиями по 1 su.
- **ВР-VS2-64. Пределы увеличения карточек.** Пределы карточек (King Arthur ≤ 1,0; Merlin и гарпии ≤ 1,25) считались
  для стартовых кругов ВР-CP01. Круги B из CP-07 теснее: King Arthur 432 px вместо 480, помощники 88,32 px вместо 96.
  Во всех приёмочных кадрах (720p и 1080p при 100 и 150 %) пределы выполняются: King Arthur ≤ 0,556, помощники
  ≤ 0,679 (тест `Portrait.Crops`, трассы `trace/`). Выше предела только 2160p 150 % (×3): загрузка King Arthur 160 su —
  1,111×, ROOM помощника 40 su — 1,359×. Оба значения под кэпом 1,6 (ВР-CP04) и есть в перечне превышений CP-07
  (`magnification-limits.json`). Отдельный кап для карточек не вводится: детали не добавляются, исходник не апскейлится.
  У Medusa при ×3 показы 120 и 160 su держатся кэпом на 107,2 su (`capped=1`, CP-11).
- **ВР-VS2-65. Номер гарпии.** Номер — порядок бойцов сервера. Сервер (`game-initialization.service.ts`) ставит
  помощников в порядке `sidekicks[]` (`f-<seat>-sk<i>`). Павший остаётся в массиве с `isDefeated`, поэтому порядок не
  меняется всю партию. Счёт идёт по владельцу: в зеркальном матче (Medusa против Medusa) у каждой стороны 1–3, а не 4–6,
  как было раньше. Одна метка бойца (`FS08BoardFighter::Label`) кормит панель, тег (HB-45) и подставку (AN-31), так что
  номера совпадают по построению.
- **ВР-VS2-66. Фолбэк гарпии — без бейджа.** Если PNG нет или включён откат, круг сам показывает цифру (ВР-CP09). Второй
  цифры в бейдже нет.
- **ВР-VS2-67. Бейдж гарпии.** Диск card.navy 14 su с mark.keyline 1 su, цифра card.cream живым текстом (И-7). Шрифт —
  токен type.tag: Roboto Bold Condensed, em 14 su, высота прописной ≈ 10 su, то есть font.card cap 10 su из 02 §6.5.
  Место — по макету панели CX-09 (+21, +20 от угла круга 32 su), на кромке в правом нижнем углу. Оверлей CP-07 ставил
  бейдж в (18, 18), внутрь квадрата 32. Оба варианта — «правый нижний угол»; вариант CX-09 меньше закрывает лицо и уже
  принят в HB-17/HB-18.
- **ВР-VS2-68. Трасса PORTRAIT.** Добавлены поля `capped=0|1` (кэп ВР-CP04 сделал круг меньше показа) и `n=1…3` (номер
  гарпии). Строки помощников идут вместе со строками SHOT панелей (`show=panel`, `id=king-arthur/merlin`,
  `id=medusa/harpies`). Гейт `check-trace` не пропускает гарпию в PANEL без `n=1…3`.
- **ВР-VS2-69. Лист размеров — кадр движка, а не офлайн-композит.** Страница 3 галереи рисует настоящий материал
  (`M_UmPortraitDisc`, MID, кап, кромка) в editor `-game`. Листы — цвет | серый Rec.709 | дейтеранопия, по строке на
  персонажа. Масштабы: 720p 100 % даёт 0,75 px/su (кривая `UmHudScale`, не 0,667), 1080p — 1, 1080p 150 % — 1,5,
  2160p — 2, 2160p 150 % — 3.

## Проверки

- UE (worktree, `node tools/s08/run-ue-tests.cjs`): `Unmatched.S08.Hud` 31/31, новые `Portrait.Crops` и
  `Portrait.Sidekicks`; `Portrait.Cap` и `Portrait.Fallback` переведены на числа CP-07. `Unmatched.S08` + `Unmatched.S10`
  310/310, `Unmatched.S09` 108/108 (в том числе `Phase2.fighters decode: H1/H2/H3`).
- pytest: `tools/art/cards` 22/22 (`test_discs_are_the_cp07_crops`, `test_missing_crops_keep_the_start_numbers`),
  `tools/s08/hud_contract` 65/65 (`test_check_trace_portrait_sidekicks_cp10_12`); `ue_import_card_media.py --check` ok.
- Сборка UnmatchedEditor в worktree: `Result: Succeeded`, ошибок в логе нет.
- Трассы (`trace/`, только строки галереи; аватаров там нет): `portraits-<разрешение>.txt` — страница 3, 31 круг на
  каждом из пяти масштабов; `panels-<разрешение>-p1|p2.txt` — панели. `check-trace` на полных трассах: 0 ошибок PORTRAIT
  (scale ≤ 1,6, монограммы при ключе из реестра нет, у гарпий `n=1…3`). Падения SHOT на страницах 1–2 — пустые
  прямоугольники галереи, они были и в B2.
- Максимум scale King Arthur: 0,370 (1080p, 160 su), 0,556 (1080p 150 %), 0,741 (2160p), 1,111 (2160p 150 %, без кэпа).
- Листы с аватаром (вне git, ВР-CP12) — `scraped-data/derived/visual-evidence/CP-09/CP-09-{720-100,1080-100,1080-150,2160-100,2160-150}.png`,
  общие листы страницы 3 и панелей — `scraped-data/derived/visual-evidence/CP-09-12/`. Все открыты (Read), включая
  увеличения ×4 nearest для 32 su. King Arthur узнаётся от 32 su (шлем, борода; при 32 su — силуэтом, ВР-VS2-CP-10 из
  CP-07) до 160 su. Проигравший — серый с прозрачностью 0,6, без красного. Павший — серый. Фолбэк «KA» — text.primary на
  card.navy. В сером и в дейтеранопии круг отделён кромкой от фона листа и от panel.bg.

## Отложено (шаг «Кадры» VS-2, packaged)

- PANEL-LOC Arthur на Marmoreal original (свой ход) и PANEL-OPP Arthur на Sarpedon original (ход соперника), 1080p и
  720p 100 %, `-Bench` с отпечатком RENDER, шесть фигур v2. Marmoreal — вклейка после ENV-U16, до неё `-ConceptPaste` с
  пометкой. Трасса `PORTRAIT id=king-arthur scale ≤ 1,0` в кадре.
- GAMEOVER (победа и поражение Arthur) 1080p, ROOM и загрузка (фон Marmoreal) 1080p и 720p — вместе с экранами (SC, H15).
- Строка реестра 03 и статус карточки — в основной копии после интеграции (ВР-PL09).

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

Кадры выхода и гейты — [VS-2](../VS-2/README.md). Прогоны `run-combat-demo -PlayerView -S08ExitShots` на Marmoreal original (`-ConceptPaste` до EN-13) и Sarpedon original, шесть фигур v2, 1080p 75 / 100 / 150 %, 720p 100 / 150 %; vs-ai `-PlayerView`. Листы цвет / серый / дейтеранопия — `sheet-0*.png` (`sheet.py`, вырезки по трассовым bbox). Все кадры и листы открыты (Read).

- **Решение:** художественно принято, по делегированию (2026-10-07).
- King Arthur в PANEL-LOC (свой) и PANEL-OPP (соперник) на обеих досках, 1080p и 720p, 100 / 150 %. Лицо и шлем в центре круга, в сером читается.
