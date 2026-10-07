# HB-35 — выбор, модаль: `UUmHudPending` (варианты, DECK_TOP_PICK, число ▲▼, очередь)

VS-4, шаг V1 (H10), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`). Карточка — `hud.csv` HB-35;
04 §2.8, §3.1, §3.4, §4.3, §5.2 (H10), §7.1; принятый макет HB-34 (`art/imagegen/hud-pending-v1-codex/`,
ВР-VS2-HB34-01…19), ВР-HB11, ВР-HB12. Тот же коммит кода — [HB-37](../HB-37/README.md) (слот) и правки VS-3 п. 2, 3, 6,
12, 13 (см. «Правки VS-3»).

**Статус:** виджет, WBP, подключение к режиму игры, строки, тесты и листы галереи готовы. Живые кадры набора D
(`tools/s09/run-pending-demo.ps1`, Prophecy на Marmoreal original) и `check-trace` живой трассы — шаг «Кадры» (упаковка
в этом шаге запрещена). **Откат:** `-S08SlateHud=pending` (Slate-блоки командной панели, виджет не строится).

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. `UUmHudPending` | `S08/UI/UmHudPending.h/.cpp`, `/Game/S08/UI/Hud/WBP_UI_HUD_PENDING`. BindWidget: Header, SourceName, Body (`UScrollBox`), Options (`UVerticalBox`, пул из 6 `UUmButton`), Picker (`UUmNumberPicker`), CollapseButton, BackButton, DeclineButton, QueueChip. Вместо `ApplyModel(FS09PendingPresenter, FS09PendingStep)` — чистая модель: `UmHudPending::Gather(FUmPendingInput)` (команда, презентер, снимок) → `FUmPendingModel` → `Plan(Model, Frame, Keys, Measure)` → `ApplyModel` (ВР-VS4-03: форма считается без UObject и проверяется тестами на 4 холстах). |
| 2. `UUmNumberPicker` | `S08/UI/UmNumberPicker.h/.cpp`: «▲» — глиф `ui-step` (IC-56), «▼» — он же, повёрнут на 180°; значение `type.title`; «Подтвердить», «Отмена», плашка результата; `Stepped` держит Min…Max. Ширина кнопки — max(120, текст + 40). Источника данных в MVP нет (ВР-HB11): тесты и лист. |
| 3. DECK_TOP_PICK | ряд `UUmCardWidget` 150×208 (S 120×166) по `PendingRevealedCards`; клик — `TogglePendingCard` (`SetSelected` CP-17, подъём 16 su), счётчик «Выбрано {k}/{n}» (`hud.pending.pick.count`); шаг порядка — только выбранные карты по центру, клик ставит следующий номер на чип 24 su над картой; ответ — прежний `PendingCardIds` в порядке кликов. Правый клик — инспектор. |
| 4. Кнопки | вариант → одна главная «Подтвердить» (отказ с `why.pick.count`, пока выбор неполный); «Свернуть (C)»; «Назад» — только CHOOSE_ONE и число после выбора, пока команда не ушла (ВР-VS4-07); «Отказаться (X)» — только у необязательного; Esc — «Назад» или `why.choice.required` у обязательного (`UmPendingEscape`). |
| 5. Бой | модаль не открывается поверх боя: серый компакт «{карта}» / «Выполните после боя» (`hud.pending.after.combat`, вид `after-combat`). |
| 6. Строки | новые ключи `hud.pending.back`, `.pick.count`, `.discard.count`, `hud.key.decline`, `hud.slot.owner`, `hud.combat.nodefense` + причина `why.pick.count` (ВР-VS4-08, -09): `st-hud.csv`, `why-reasons.json`, 02 §4.2, 04 §2.8; таблицы ST_Hud / ST_Why и `Game.locres` пересобраны `hud_strings_build.py build`. |
| 7. `SHOT widget` | `id=UI-HUD-PENDING impl=umg state=modal|compact|collapsed|toast|opp kind= body= tone= wait= queue= pick= sel= buttons= scroll= class= w= h=` — без имени карты и текста; смена шага — `HUD-PENDING view=… kind=… head=…`. |
| 8. Slate-панель | при UMG-выборе командная панель не рисует блоки выбора, сброса, способности и ожидания, а у черновика атаки и окна разрешения — только кнопки (строки «ATTACK DRAFT», «COMBAT RESOLVE WINDOW», «RESOLVE blocked» ушли из вида по умолчанию, VS-3 п. 3); с `-S09Markers` панель целиком (гейты, ВР-VS4-02). Маркеры `#4080FF` / `#8040FF` / `#FF40B0` — как были, только `-S09Markers`. |
| 9. Тесты | `Unmatched.S08.Hud.Pending.Modal` (Prophecy 4/2 и порядок — фикстуры `gd035-deckpick-owner-view`, `gd035-deckorder-owner-view`; CHOOSE_ONE; число; влезает на 4 холстах; бюджет), `.Keys` (C через презентер, «Отказаться» только у необязательного, «Назад» только после выбора), `.Tree`, `.Forms`, `.Source` (`S08/UI/UmHudPendingTests.cpp`). |

Формы HB-36 (компакт L / S, сброс по лимиту, BOOST King Arthur, серый выбор соперника, после боя, свёрнутый, тост)
собраны здесь же, потому что Slate-панель уходит из вида по умолчанию и каждый отложенный выбор должен рисоваться
(ВР-VS4-03). Приёмка HB-36 остаётся своей: тост — в `UUmToastStack` (HB-40), тесты `.Compact/.Toast/.Opp/.Discard` под
именами карточки, кадры набора D.

## Геометрия (сверка с HB-34)

Из `SHOT` галереи и `AddInfo` теста `.Modal`: модаль 1080p 100 % — 640×396 (порядок 640×408), 720p 100 % — 640×380 с
прокруткой 16 / 28 su (кап 380), класс S — 560×354 (порядок с прокруткой 6 su); компакт L 720×60 (с очередью и
переносом подсказки — 720×84), S — 560 одной строкой (до 720 с очередью и двумя кнопками); свёрнутый 320×44; серый
соперника L 320×60, S ~384×48; тост 560 / 520 / 440 × 48; BOOST King Arthur 571…588 × 56. Совпадает с пакетом HB-34.
Бюджет (`.Modal`): та же модель p95 0,0002 мс (≤ 0,05), новый шаг p95 0,037 мс (≤ 2).

## Решения по делегированию (шаг V1)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-02 | Slate-панель команд при UMG-выборе не рисует блоки выбора / сброса / способности / ожидания и строки черновика атаки и окна разрешения; кнопки черновика и «R» остаются до HB-43 (ACTIONS); с `-S09Markers` — целиком | VS-3 п. 3: блок закрывал свою карту боя в S; гейты пикселей держатся на маркерах |
| ВР-VS4-03 | Формы HB-36 строятся в `UUmHudPending` сейчас; приёмка HB-36 (тост в стек HB-40, тесты и кадры D) — своя | иначе после ухода Slate-панели выбор без вида |
| ВР-VS4-04 | Имя карты-источника: префикс id эффекта (`<cardId>-<поле>-<i>-p<n>`, `discard-choice-…`, `ability-<герой>` → герой) по спискам колод снимка (самый длинный `CardId` / `InstanceId`), иначе из текста; то же имя — в STATUS «выбор {choice}» | в данных выбора имени карты нет, id эффекта его несёт |
| ВР-VS4-05 | Серый компакт соперника — строка «Соперник делает выбор» только когда STATUS её не говорит; без известного источника — не показывать | один текст один раз (ВР-VS2-HB34-12) |
| ВР-VS4-06 | Компакт / серый — под показанным центром боя + 8 su (и не выше низа STATUS + 8) | не закрывать центр боя |
| ВР-VS4-07 | «Назад» — только CHOOSE_ONE и число после выбора, пока команда не ушла; Esc = «Назад», у обязательного без выбора — `why.choice.required` | DECK_TOP_PICK снимается повторным кликом |
| ВР-VS4-08 | Причина `why.pick.count` «Сделайте выбор: нужно {need}, выбрано {have}» у «Подтвердить» неполного выбора | отказ без причины запрещён (DE-014) |
| ВР-VS4-09 | Ключи строк, которых не было в пакете HB-34 («строки без ключа»): `hud.pending.back`, `.pick.count`, `.discard.count`, `hud.key.decline`, `hud.slot.owner` | И-7, всё через ST |
| ВР-VS4-14 | Slate-панель команд сдвигается вправо от показанного UMG-слота (`HUD-CMD shift… shiftX`) | слот и панель делили левый верх |
| ВР-VS4-19 | Тост рисует `UUmHudPending` на месте тоста по правилу стека, пока нет `UUmToastStack` (HB-40) | ВР-H06 считает место, владелец — HB-40 |
| ВР-VS4-20 | Текст меряется шрифтом в масштабе рендера (`FSlateFontMeasure::Measure(…, Scale)`), запас 6 su на строку, заглавные — ICU `FText::ToUpper` | при 150 % подписи кнопок обрезались; правило «не резать» |
| ВР-VS4-21 | Компакт L: из «текст слева» и «имя во всю ширину, подсказка у кнопок» берётся более низкий | длинное EN-имя («The Hounds of Mighty Zeus») рядом с двумя кнопками |
| ВР-VS4-22 | Слоты GAME: PENDING — весь холст (форма сама ставит себя), SOURCE SLOT — SLOT + лента (+56 su, ширина ≥ 190) | модаль, компакт и тост в разных местах; лента под картой |

Решения слота (ВР-VS4-10…13, -17) — в [HB-37](../HB-37/README.md); правки VS-3 (ВР-VS4-15, -16, -18) — ниже.

## Правки VS-3 (тот же коммит)

- п. 2 — `UUmHudHand::CollectShotLines`: `visible = shown && rect valid && area > 0` — пустая опущенная рука пишет
  `visible=0` ([HB-24](../HB-24/README.md)).
- п. 3 — ВР-VS4-02 выше.
- п. 6 — строка CP-18 в `06-tasks/cards-portraits.csv` приведена к ВР-VS3-65 (у защитника рубашка без чипа).
- п. 12 — ВР-VS4-15: правый чип «+N» на углу нарисованной карты, 8 su на рамке, 4 su от правого края
  (`ChipCornerInsetSu`; раньше 4 su над верхом коробки) ([CP-18](../CP-18/README.md), [HB-25](../HB-25/README.md)).
- п. 13 — ВР-VS4-16: под штампом X «нет защиты» текст «Нет защиты» (`hud.combat.nodefense`, `text.primary`), SHOT
  `stampText=1` — по 04 §3.8 («штамп X + текст»), в 04 §2.7 добавлен ключ `.nodefense` ([HB-30](../HB-30/README.md)).
- Z-1 — ВР-VS4-18: `UmHudPanel::SidekickNumber` берёт номер у `S08HeroesV2::HarpyNumber` (метка с цифрой после имени);
  без цифры — 0 (бейджа нет).
- Тест `Unmatched.S08.Hud.Fixes.Vs3`.

## Проверки

- Сборка UnmatchedEditor в worktree — `Result: Succeeded` (`C:/tmp/visual/VS4-V1/build-13.log`), игровая цель
  `Unmatched Win64 Development` — `Succeeded` (`build-game-2.log`).
- UE: новые тесты 8 из 8 (`Unmatched.S08.Hud.Pending.*`, `.Slot.*`, `.Fixes.Vs3`); `Unmatched.S08.Hud.*` — 80 из 80
  (`ue-tests-hud-1.log`); полный `Unmatched.S08 + S09 + S10` на последнем коде — 482 из 482 (`ue-tests-full-2.log`).
  Строки `LogAutomationTest: Error: Condition failed` в кадре 0 — шум старта движка (есть и в логах VS-3).
- `hud_contract.py validate` — PASS (G-TOKENS: литералов цвета нет); `hud_strings_build.py check` — PASS (ST_Hud 95,
  ST_Ms 85, ST_Why 50); `hud_tokens_codegen.py --check` — FRESH; pytest `tools/s08` — 133 passed (`hud_contract` 68).
- `check-trace` — PASS на всех 10 трассах галереи (106 строк SHOT widget в каждой).
- WBP: `C:/tmp/visual/VS4-V1/um-hud-wbp-report.json` — `WBP_UI_HUD_PENDING`, `WBP_UI_HUD_SLOT` created, up-to-date;
  остальные WBP не перезаписаны (`UM_HUD_WBP_OVERWRITE=0`).

## Листы

Галерея `-S08IconGallery -S08IconGalleryPending=marmoreal|sarpedon` (editor `-game`, один клиент, `t.MaxFPS 30`,
`-RenderOffScreen`; других клиентов UE в это время не было): 20 состояний — modal-pick, modal-order, choose-one, number,
compact-move, compact-place, compact-target, compact-space, toast, collapsed, discard, boost, opp, after-combat,
slot-opp-fly, -hold, -show, -fade, slot-boost, slot-discard; холсты 1080p 100 / 150 %, 720p 100 / 150 %; данные карт —
колоды S01 (name, nameRu, textEn, значения), фон — кадр bench K1 доски.

- В git (без доски, сканов и аватаров: `-S08IconGalleryHandPlain -S08CardArtLegacy`, запасные лица карт):
  `plain-1080-100-contact-colour.png`, `-grey.png`, `plain-720-150-contact-colour.png`, `-grey.png` — sha256 в
  [`sheets-sha.json`](sheets-sha.json).
- Вне git (кадр доски и сканы — `scraped-data/`, gitignored, ВР-VS4-01): `scraped-data/derived/visual-evidence/HB-35/`
  в worktree — контакт 20 состояний на 8 холстах (цвет, серый) и вырезки модали / компакта в родных пикселях по доскам;
  путь, sha256, размер и что показано — [`visual-evidence-index.json`](visual-evidence-index.json). Кадры прогонов —
  `C:/tmp/visual/VS4-V1/gallery/b5-<run>` (build-12; build-13 менял только разбор данных галереи), `b6-plain-*` (build-13).

Что видно (Read: оба plain-листа, контакт Marmoreal 1080p 100 % и вырезки модали обеих досок):
- Prophecy: 4 скана, две отмечены и подняты, «Выбрано 2/2», «Подтвердить» жёлтая, «Свернуть (C)»; порядок — две карты по
  центру с чипами 1 и 2; при 720p 100 % тело прокручивается, подвал виден.
- CHOOSE_ONE — три варианта во всю ширину, второй выбран, «Назад / Подтвердить / Свернуть (C)»; число — ▲ 2 ▼,
  «Подтвердить / Отмена», плашка результата.
- Компакты: «The Hounds of Mighty Zeus» с чипом «ещё 2», «Оставить на месте», «Свернуть (C)»; PLACE с «Отказаться (X)»;
  сброс «Hiss and Slither» с «Подтвердить»; BOOST — только две кнопки; серые «Соперник делает выбор» и «Выполните после
  боя»; свёрнутый «Prophecy: выбор ждёт» с C; тост «Medusa / В прошлый раз: King Arthur» с Enter, X, C.
- Ни одна подпись не обрезана ни на одном холсте; в классе S длинное имя переносится, плашка растёт.

## Что не сделано в этом шаге

- Живые кадры набора D (`run-pending-demo.ps1`, Marmoreal original, 1080p 100 % и 720p 150 %), `check-trace` живой
  трассы `state=modal` и синтетические клики (0 потерь) — шаг «Кадры» (упаковка).
- Кнопки черновика атаки и окна разрешения пока Slate — ACTIONS (HB-43).
- `UUmNumberPicker` без источника в данных MVP (ВР-HB11).
- Имена и тексты карт King Arthur в данных — EN (задача данных); живой STATUS выбора соперника — `why.wait.opponent.choice`.
- VS-3 п. 14 (обрывает ли новый черновик атаки постановку боя) — не трогался, кадры A — HB-49.
