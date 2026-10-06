# HB-15 — строка статуса и глагол соперника: UUmHudStatusLine (шаг H5)

VS-2 шаг B1, 2026-10-06, ветка `feat/visual-vs2`. Карточка — `06-tasks/hud.csv` HB-15; спецификация — 04 §2.5, §2.11,
§7.1, ВР-H09; макет — CX-08 (`art/imagegen/hud-topstrip-v1-codex/`, принят по делегированию). Решения шага —
ВР-VS2-41…50 в [README HB-14](../HB-14/README.md) (для этой карточки — 41, 46, 47, 48, 50).

**Статус:** код, WBP, тесты, лист галереи готовы; кадры packaged — шаг «Кадры» VS-2.
**Флаг отката:** `-S08SlateHud=status` — прежняя строка в панели руки (`AddTurnStatusLine`) и заголовки «OPPONENT'S TURN»,
«AFTER COMBAT» командной панели.

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. UUmHudStatusLine: Body (T_Skin_Capsule), StatusText, PulseDot, KeyChip; ApplyModel(FS09TurnStatusInput) | `S08/UI/UmHudStatusLine.{h,cpp}`: `S09TurnStatus::Line` → ключ `ms.*` / `why.*` и аргументы → RU / EN из ST_Ms / ST_Why (`UmHudStatus::LineText`; глагол соперника — `ms.opp.phase.*`); `/Game/S08/UI/Hud/WBP_UI_HUD_STATUS` |
| 2. Чип клавиши — только при UI-ACC-017 | `FUmStatusFrame::bKeyHints` (режим даёт HB-43, до него выкл.); чипы 20 su и шире по клавише, `UmHudStatus::KeyHints` |
| 3. Ширина по тексту ≤ 880 / 720 / 600; перенос | `UmHudStatus::Fit` (2 строки, 24 → 20 → 16 su, «…» + подсказка), `BodyHeightSu` (48 / 78 su), ВР-VS2-46 |
| 4. Строка держит последний текст | новый вход меняет текст только при смене ключа / текста; пустая строка — блок скрыт |
| 5. SHOT widget | `SHOT widget id=UI-HUD-STATUS state=own|opp|defend|discard|choice|sync … key=<ключ> lines=<n> size=<su> ellipsis=0|1 keys=<…> width=<su>` (bbox — капсула) |
| 6. Slate-строка и заголовки — только при `-S08SlateHud=status` | `S08FlowGameModeOpponent.cpp` `AddTurnStatusLine` → `ApplyUmHudStatus` (трасса `MS-STATUS` прежняя); `S08FlowGameMode.cpp` — два `AddHeader` под `UmHudBlockOnSlate("status")` |
| 7. Тесты | `Unmatched.S08.Hud.Status.Tree`, `Unmatched.S08.Hud.Status.Keys` |

## Проверки

- `Status.Keys`: 16 входов 04 §2.5 (действие, конец хода, боец, клетка, атакующий, цель, карта атаки, атака, схема,
  защита, сброс, выбор, соперник, ИИ, ждём защитника, синхронизация) → свой ключ и состояние, все шесть состояний
  §7.1; ни в RU, ни в EN нет «(M)», «(A)», «(G)», «(E)», «(N)», «(R)», «(Enter)», «(1–9)»; защита — одна строка 608 su
  в L (1080p и 720p), две строки 78 su без «…» в S, «Без защиты» целиком; длинный выбор — 16 su, две строки, «…»,
  полный текст в подсказке; пульс 1 / 0,35, reduced статичен; проявление 0,15 → 1 за 120 мс.
- Лист галереи — [HB-14/gallery](../HB-14/gallery/) (шесть состояний на ширине класса каждого холста, цвет и серый).

## Отложено (шаг «Кадры»)

- Все 6 состояний в трассах прогонов боя и выбора на обеих досках; кадры 1080p 100 / 150 %, 720p 100 / 150 %: строка не
  пересекает `FIELD` и баннер; RU «Вас атакуют…» — 2 строки на 720p 150 % без «…»; цвет и серый.
- RU-имена героев в `{player}` — данные БД (`Hero.nameRu` = EN), см. ревью CX-08.

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

Кадры выхода и гейты — [VS-2](../VS-2/README.md). Прогоны `run-combat-demo -PlayerView -S08ExitShots` на Marmoreal original (`-ConceptPaste` до EN-13) и Sarpedon original, шесть фигур v2, 1080p 75 / 100 / 150 %, 720p 100 / 150 %; vs-ai `-PlayerView`. Листы цвет / серый / дейтеранопия — `sheet-0*.png` (`sheet.py`, вырезки по трассовым bbox). Все кадры и листы открыты (Read).

- **Решение:** художественно принято, по делегированию (2026-10-07).
- В трассах встретились все шесть состояний: own, opp, defend, discard, choice, sync.
- Строка соперника «King Arthur — Соперник выбирает действие» / «… манёвр» и «T. Rex — Соперник выбирает карту» (VS_AI) с точкой.
- RU «Вас атакуют: выберите карту защиты или «Без защиты»» на 720p 150 % — две строки, без «…».
- **Не прошло:** эта двухстрочная строка один раз закрыла тег гарпии; STATUS закрывает шапку Slate-панели колоды на 720p 150 % (VS-2, «Открыто», п. 2–3).
- Слова «YOUR TURN / actions left / phase» убраны из Slate-панели (ВР-VS2-74).
