# Визуал: инвентаризация (фаза 1)

Дата: 2026-10-05. Фаза 1 визуального чата ([00-VISUAL-BRIEF.md](00-VISUAL-BRIEF.md) §1 п. 1, §3, §7). Устроено как
[опись звука](../audio/01-inventory.md).

**Срез.** Ветка `fix/admin-panel`, HEAD `d964027c` (2026-10-05 21:22). Упакованный клиент на момент записи — штамп
`2420dda7` (2026-10-05 19:01, `unreal/Unmatched/Saved/StagedBuilds/Windows/BuildStamp.json`).

**Поправка ревью (2026-10-05 ≈21:40).** Пока шла опись, основной чат сделал коммит `9c8f92b7` (21:34, R-04, MS-AT-41:
подложки одной ISM; `S08MoveHighlight.*`, `M_UM_MovePlate.uasset`, `ue_move_plate_material.py`) и перепаковал клиент:
`BuildStamp.json` — `9c8f92b7`, `builtAt` 21:37, `skipBuild: true`, exe собран 21:35. R-02, R-03 и R-04 теперь в
упаковке. Живых кадров с этой упаковкой нет. `S08FlowGameMode.cpp` коммит не менял: номера строк ниже верны.

**Что изучено.** Все области §3 брифа: HUD и экраны, поле, значки, карты и портреты, герои и анимации, VFX и CUE,
окружение и рендер, изучение Digital Edition (DE), арт-дирекшн, реестры и инструменты.

**Как.**
- 10 агентов-читателей, по одному на область. Каждый читал код, документы и `git log`.
- 218 просмотров кадров и листов глазами (Read PNG/JPG). Часть кадров смотрели две-три области. Список — §12.
- Спорные места я перепроверил сам: `git log` и `git status`, `BuildStamp.json`, трассы `concept-paste`, номера
  строк, счётчики. Что решил сам — в конце §10.
- Ревью (один проход, 2026-10-05): сверено ≈60 утверждений с первоисточниками (цитаты, коммиты, флаги в коде,
  счётчики), открыто 10 кадров и листов, добавлены пропущенные пункты брифа. Что не подтвердилось — помечено «не
  проверено».
- Номера строк кода даны на HEAD `d964027c`. В `S08FlowGameMode.cpp` они сдвигаются с каждым коммитом основного
  чата, поэтому рядом стоит имя функции.

**Статусы** (словарь проекта):
- «предложено» — документ, концепт или значение без приёмки;
- «измерено» — есть замер или тест, приёмки нет;
- «технически импортировано» — ассет или код в игре и работает, вид не принят;
- «художественно принято» — вид принят.

Вспомогательные пометки: **прототип** — работает, но вид отладочный (Slate, текст); **нет** — отсутствует;
**отклонено**; **заменено**.

**Кто принял:**
- **лично** — есть слова пользователя с датой (цитата в «»);
- **по делегированию** — решили агент, советник или панель по полномочиям «делай все без меня» (2026-09-29),
  «сам реши все вопросы» (2026-10-03), «Я хочу, чтобы эти решения ты принял после второго пункта, после изучения
  игры.» (2026-10-04). Личного просмотра пользователем не было.

## 0. Коротко

- **Финального HUD нет.** Весь HUD партии и все экраны — Slate-прототип внутри `AS08FlowGameMode`: `RefreshHud`
  пересобирает панели на каждое событие. На UMG только слой над фигурами (4 WBP) и портреты DE-023 (нативный виджет
  без WBP).
- **Решение U-4 «HUD: гибрид UMG сейчас»** (лично, 2026-09-28) в коде не выполнено. Набор DE 2026-10-05 добавил новые
  Slate-панели (колода, слот, результат, карты боя, баннер) вопреки U-4 и HUD-RULES П1, П3, П5.
- **Набор DE работает функционально** (32 из 39 задач), принят по делегированию. Вид — текст: рука из текстовых
  кнопок, карты боя текстовыми плашками, монограммы вместо аватаров, всё на английском. Игрок видит отладку: 13
  неоновых маркеров пиксельных гейтов, «seq= phase=», эхо команд.
- **Лично пользователь по визуалу решил немного:** D-02, D-09, D-10 (2026-09-18); U-1…U-4 (2026-09-28); «Акценты +
  кольцо» (2026-09-29); ENV-U0…U16 и «только настоящие доски» (2026-09-30…10-04); язык DE для значков (2026-10-03);
  DE-012 и AB-5…AB-8 (2026-10-05). Из ассетов «художественно принято» лично стоят только формы глифов DE-012 от Codex.
- **Принятое лично 2026-10-05 в коде выключено.** Кольцо хода только с `-S08TurnRingIcon=`, ореол только с
  `-S08HeartGlow`, трекер v3, сердца павшего и штампа X нет. Формы Codex не перенесены в движок v3 и UE. Это нарушает
  правило AGENTS.md «принятый арт по умолчанию». «Прогон I» не спланирован, владельца нет.
  **Обновление 2026-10-05:** закрыто прогоном I
  ([I-2026-10-05.md](../de-footage/task/runs/I-2026-10-05.md)):
  - I-01 перенёс формы Codex в движок v3 и UE;
  - I-02 включил AB-5…AB-8 по умолчанию; откаты — `-S08TurnRingLegacy`, `-S08HeartGlowLegacy`, `-S08TrackerLegacy`, `-S08CrossLegacy`.
- **Marmoreal по умолчанию — 3D P5c,** а не нарисованный задник ENV-U16 (`conceptPaste.default "off"`). Нарисованный
  есть только флагом `-ConceptPaste`: сырой концепт без чистой плиты и без анимации. `0f2bdb9a` сделал P5c видом без
  флагов, но нарисованного Marmoreal по умолчанию не было и раньше: корень — трактовка ENV-U15 п. 5 от 2026-10-01.
- **Проверка кадров по AGENTS.md «Look before you report» (ревью, кадры открыты).**
  - Вид без флагов, Marmoreal: настоящая доска, шесть фигур v2, но вокруг 3D P5c (дворец, 3D-сакуры, фонари на
    тумбах). Кадры: ART-DEFAULT 2026-10-04, дуэль F 2026-10-05 (`concept-paste mode=off reason=default`). Задник
    нарушает ENV-U16.
  - Вид без флагов, Sarpedon: настоящая доска, lit3d (`mode=on reason=default`), шесть фигур v2. Соответствует.
  - Все демо-прогоны DE на Marmoreal (B, C, D, E, F, G, FINAL-PKG) сняты с `-ConceptPaste` (`reason=flag-on`). Это
    сырая вклейка по флагу, не вид по умолчанию.
- **Фигуры v2 и 16 клипов включены по умолчанию,** но приняты только по делегированию (GD-058 final). Гарпии H1–H3 в
  виде по умолчанию неразличимы: теги без имени, у всех «1/1».
- **Боевых Niagara нет ни одного.** У 8 CUE с колонкой vfx — `missing`. В бою игрок видит красную заливку всей
  фигуры (DE-010, вид пользователю не показывали), «−N», жетон цели и растворение fade.
- **Значки v3** приняты по делегированию (ART-011). В UE 336 текстур, в живом HUD работают 3 id из 23. Размера 16 px
  в UE нет.
- **Подложки хода и кольца-кандидаты V-17** закрыты флагом `-S08MovePlates`. По умолчанию — старое кольцо ENV P4.
  V-17 того же золота, что кольцо команды P1, и с ним сливается.
- **Карт и портретов в UE нет:** ни лица карты, ни рубашки, ни аватара. Исходники маленькие (EN 250×349), WebP UE не
  читает, лицензия скрапа не подтверждена, копия скрапа лежит в git (`docs/figma/figma-ready`).
- **Палитра P2 `#5A7F9F`, шрифт Roboto Bold Condensed, кольца команд** выбраны по делегированию. Q-304, AD-OPEN-06,
  -23, -28, -34 открыты. Токены «предложено», значения продублированы вручную минимум в 8 файлах C++.
- **Упаковка.** Штамп `2420dda7` (19:01) был старше R-02 и R-03; CLOSEOUT:15 «клиент актуален» тогда устарела. В
  21:37 клиент перепакован на `9c8f92b7` (R-02…R-04 внутри). Кадров с новой упаковкой нет.
- **Главные расхождения статусов:** значки v3 «приняты пользователем» в 01-decisions против делегирования в акте;
  DE-012 «кандидаты» в шести документах против личной приёмки; Marmoreal «принят» в профиле и реестре против ENV-U16;
  P2 «принято» в брифе против открытого Q-304.
- **Процесса нет:** общего документа о цикле «Codex/SYNTX → ревью → коммит → UE → кадр» нет; журналов трат два,
  60 токенов SYNTX за музыку не записаны.

## 1. HUD и экраны

### 1.1 Код, контракты, архитектура

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| U-4: C++-база с `BindWidget` + WBP, Slate только F10, трассы и пробы, без CommonUI | решение действует, в коде выполнено частично | лично, 2026-09-28: «HUD: гибрид UMG сейчас» (запись вторичная, первичной записи чата нет) | — | [render-ui-user-decisions.md:5,12,44-48](../decisions/2026-09-29-render-ui-user-decisions.md) |
| HUD партии: `RefreshHud` делает `ClearChildren` трёх панелей и строит их заново на каждое событие (80 мест вызова в основном файле, 8 в частичных) и каждые 0,25 с в окнах защиты и резолва | прототип | — | единственный путь, отката нет | [S08FlowGameMode.cpp](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp) `RefreshHud` :5795 (8802 строки) |
| Постоянные слоты `BuildHudWidgets`: портреты, баннер, слот карты, панель колоды, модал результата, тост, карты боя | прототип (Slate, кроме портретов) | функция — по делегированию (ревью прогонов C–F) | по умолчанию | там же, `BuildHudWidgets` :5537; частичные `S08FlowGameMode{TurnHud,CardSlot,DeckPanel,Result,HandLimit,Opponent}.cpp` |
| Слой над фигурами: `WBP_S08ArtPlate`, `Tag`, `Damage`, `Icon` (единственные WBP проекта) | технически импортировано; паритет 0 px измерен только у плашки и только на Cobble | — (акт W4-C: «Художественно не принято») | по умолчанию с `0f2bdb9a` (`-ArtHudImpl=umg`); откат `-S08GreyBoard`, `-ArtPreviewNoPlate`, `-ArtHudImpl=slate`; `WBP_S08ArtIcon` — только при `-S08IconLegacy` | [hud-umg-w4c-2026-09-29.md:3](../evidence/ART-004/hud-umg-w4c-2026-09-29.md), [S08ArtHudUmgTests.cpp:612-655](../../../unreal/Unmatched/Source/Unmatched/S08/S08ArtHudUmgTests.cpp) |
| Портреты DE-023: `US08TurnPortraitWidget`, нативный UMG без WBP | технически импортировано; вид — прототип (монограммы, EN) | функция — по делегированию (ревью E `670c4bd4`) | по умолчанию в арт-виде; кольцо и ореол выключены | [S08TurnPortraitWidget.cpp:43-60](../../../unreal/Unmatched/Source/Unmatched/S08/S08TurnPortraitWidget.cpp) |
| 17 моделей `S09*`: HudModel, ManeuverUi, MoveInput, MoveDraftView, HudPress, TurnHud, TurnStatus, OpponentView, PendingPresent, CardSlot, HandLimit, DeckPanel, ResultScreen, DeathStage, CombatStage, CombatEffectLog, PresentationCatchup | технически импортировано (тесты UE) | по делегированию (ревью прогонов B–F); R-02 и R-03 — без приёмки | — | [S09/](../../../unreal/Unmatched/Source/Unmatched/S09/) |
| `S09HudPress` (DE-014): клики не теряются при пересборке Slate | технически импортировано (1440 нажатий, 0 потерь) | по делегированию | `MakeHudPress` по умолчанию; в UMG станет лишним | [S09HudPress.h](../../../unreal/Unmatched/Source/Unmatched/S09/S09HudPress.h) |
| HUD-RULES П1–П9, чек-лист W4-C | предложено; §0 описывает состояние до W4-C | — | П1–П5 нарушаются | [HUD-RULES.md:3,16,26-60](../../unreal/contracts/hud/HUD-RULES.md) |
| HUD-AND-ICONS: архитектура, реестр 99+15, HI-01…12, HD-01…11 | предложено («ПРЕДЛОЖЕНИЕ v2»), местами устарел | — (ревью Fable, 47 замечаний — не приёмка) | — | [HUD-AND-ICONS.md:3,601,660](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| `hud-style-tokens.json`, 80 токенов | 77 предложено, 2 измерено (`team.p*.screen`), 1 технически импортировано (`font.card`) | — | в UE не импортируется (HI-08); значения вручную минимум в 8 файлах C++ (`S08ArtHudStyle.h`, `S08Team.h`, `S08BoardArt.h`, `S08MoveHighlight.h`, `S08TurnPortraitWidget.cpp`, `S08AnimatedIconWidget.cpp`, `…TurnHud.cpp`, `…Result.cpp`) | [hud-style-tokens.json:4-5](../../unreal/contracts/hud/hud-style-tokens.json) |
| `why-reasons.json`, 40 ключей RU/EN | предложено | — | `ST_Why` нет; в коде `S08WhyText::En` | [why-reasons.json](../../unreal/contracts/hud/why-reasons.json) |
| Шрифт HI-07 Roboto Bold Condensed | технически импортировано | по делегированию, 2026-10-03: «Бери любой, который посчитаешь оптимальным» | портреты, баннер, слой над фигурами, часть результата и колоды; остальной Slate — 102 вызова `GetDefaultFontStyle` | [HUD-AND-ICONS.md:664](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| Отладка у игрока: 13 неоновых маркеров `SColorBlock` 220×14, 4-цветная полоса результата, «seq= phase=», «deck=24~», эхо команд, `AUTO maneuver: f-0-hero…` | прототип | — | всегда; флага `-S09Markers` (П4) нет | [S08FlowGameMode.cpp:5663-5694](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp), [S08FlowGameModeResult.cpp:11-12](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeResult.cpp) |
| Локализация RU/EN (GD-048, П5) | нет | — | 0 `LOCTEXT`, около 300 английских литералов | — |
| F10 (legacy root) и Shift+F10 (Art Tuner) | прототип, служебный инструмент | — | F10; Shift+F10 только с флагом Art Tuner | `S08FlowGameMode.cpp:2878-2886` (клавиши), `:5375-5388` (видимость) |
| План 01 ADR: `WBP_GameHUD` на CommonUI, модули UmClient/UmNet | заменено: план 2026-09-02, не реализован, противоречит U-4 | «принято» агентом-архитектором | — | [01-architecture-decision.md:3,148-152,270-282](../../unreal/01-architecture-decision.md) |
| `05-ui-screens.md` | заменено: обрывается на :374 внутри §3.5 | — | — | [05-ui-screens.md](../../unreal/05-ui-screens.md) |
| `02-ux-ui-spec.md` v0.1 и дельты DE | предложено; дельты DE — по делегированию | — | — | [02-ux-ui-spec.md:3-7,722-765](../02-ux-ui-spec.md) |

### 1.2 Блоки и экраны брифа §4.2

| Блок | Что есть и где | Статус | Источник |
|---|---|---|---|
| BOOT | только текст «stage: BOOT» в legacy root | нет | `S08FlowGameMode.cpp:6912-6917` |
| LOGIN | серая форма «UNMATCHED S08 grey flow (GD-028..031)», поля, полный моно-лог трассы | прототип | `S08FlowGameMode.cpp:5210-5373` |
| LOBBY | панель GD-036: CREATE ROOM, код, JOIN BY CODE, RECOVER MY ROOM; остальной экран чёрный | прототип (GD-036 in_progress) | `:5697-5783` |
| ROOM | та же форма legacy root. Выбора героя и доски нет: только `-S08Auto`, `-S08HeroId=`, `-S08BoardId=`. Нет колоды и отсчёта | прототип | `:423-431` |
| INSPECT | текст в правой панели 370 su с отладочными instance id; оверлея нет | прототип | `:2295`, `:6071-6101` |
| PAUSE и настройки | нет экрана. Esc пишет `pause.unavailable`. Настройки DE-025 меняются только консолью `s08.Settings` | нет (GD-047 planned) | `:2031`, [S08UserSettings.cpp:130-157](../../../unreal/Unmatched/Source/Unmatched/S08/S08UserSettings.cpp) |
| RECONNECT | коричневая Slate-строка «RECONNECTING: … input locked»; оверлея нет | прототип (GD-037 in_progress) | `:5869-5885` |
| GAMEOVER | Slate-модал DE-029: VICTORY/DEFEAT, «<HERO> WINS», причина, «Turn N · m:ss», монограммы, VIEW BOARD, RETURN TO LOBBY. «Сыграть ещё» нет | прототип; функция — по делегированию | [S08FlowGameModeResult.cpp](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeResult.cpp) |
| ABORTED | Slate-строки «MATCH INTERRUPTED» и RETURN TO LOBBY (L) в командной панели. Модала нет. Единственный кадр — 2026-09-27 на сетке 20×20 | прототип (GD-040 planned) | `:5837-5867` |
| Загрузка партии | нет | нет | — |
| TOP: ход, фаза, связь, настройки | нет. Ход и фаза — только отладочная строка и заголовок командной панели | нет | `:5972-5978` |
| PANEL-LOC, PANEL-OPP | обе карточки колонкой слева внизу: диск-монограмма, имя, статус, сердце HP, ромбы трекера v3 | технически импортировано; кольцо, ореол, трекер DE, сердце павшего выключены | [S08FlowGameModeTurnHud.cpp:52-103](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeTurnHud.cpp) |
| OPP-HAND | «hand=5(hidden)» в отладке; в панели колоды — красные квадраты | нет | `:5954-5969` |
| HAND | текстовые кнопки `"%d %s"` + `B%d`, `*NEW*`, `[BOOST]`, `[DROP]`, `[ATK]`, `[DEF]`, `[SCH]`, `[PICK%d]`, `[hidden]`. При выборе клетки панель опускается на 60 su (SD-26), на 1080p карты уходят за кадр | прототип | `:5887-5951` |
| DECKS | кнопки BROWSE DISCARD PILES (D), YOUR DECK (K), OPP DECK (Shift+K); боковая панель DE-030 ≈500 px — текстовый список | прототип; функция — по делегированию | [S08FlowGameModeDeckPanel.cpp](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeDeckPanel.cpp) |
| COMBAT | Slate-плашки 260 su у краёв, «X / NO DEFENSE», метка «A4 vs D2 / Merlin WINS - Medusa -2», слот защиты текстом `[shield]` или `[card back]`, блок EFFECTS (R-02) | прототип; DE-018 — по делегированию; R-02 и R-03 в упаковке с `9c8f92b7` (21:37), живых кадров с ними нет | `:1531-1640`, `:6345-6500` |
| PENDING | синяя полоса, «PENDING CHOICE - TYPE [MANDATORY]», «step n/m», CONFIRM, STAY IN PLACE, DECLINE, COLLAPSE | прототип; DE-020 — по делегированию | `:6501-6856` |
| LOG | 3 строки ленты манёвров над рукой; полного журнала нет | прототип | [S08FlowGameModeOpponent.cpp:264-278](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeOpponent.cpp) |
| CONN | значка нет; только «Syncing…» и плашка RECONNECTING | нет | `:5869-5885` |
| Баннер «ваш ход» (CUE-015) | SBorder `#161A28` α0,9, «YOUR TURN» 30 pt `#F2C14E`, 600 мс | прототип; по делегированию (D-DE-07) | `S08FlowGameModeTurnHud.cpp:83-99` |
| Строка «что делать сейчас», глагол соперника | Slate-текст над рукой и в правой панели | прототип; DE-022 — по делегированию | `S08FlowGameModeOpponent.cpp:247-262` |
| Тосты: статус, лимит руки, пропуски | тост статуса −150 su — эхо команд («attack sent»), в авто-прогоне «AUTO maneuver: …»; тост лимита DE-024 | прототип; по делегированию | `:5633-5646` |
| Слот карты-источника (DE-026) | текстовая карта под командной панелью; лента SCHEME синяя | прототип | [S08FlowGameModeCardSlot.cpp](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeCardSlot.cpp) |
| Командная панель | заголовки режимов, BEGIN MANEUVER (M), END TURN (E). Кнопок атаки и схемы нет, только клавиши A и G | прототип | `:6103-6900` |
| Над фигурами: плашка, тег, урон, жетон | 4 WBP; жетон рисует нативный `US08AnimatedIconWidget` | технически импортировано | §1.1 |
| Именные плашки HUD над фигурами | теги v2 без имени; имя — только в плашке и при hover или выделении (D-1) | открыто: решает пользователь (AGENTS.md «Still open») | [AGENTS.md](../../../AGENTS.md), [board-readability-decisions.md:13](../decisions/2026-09-29-board-readability-decisions.md) |
| Кнопки в 6 состояниях, курсоры, лоадеры, 9-slice (HI-04) | нет; панели — плоские кисти `#161A28` | нет | [HUD-AND-ICONS.md:661](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| Reduced motion | `-S08ReducedMotion`, CVar `s08.ReducedMotion`, сохранённая настройка (DE-025, MS-T-16) | технически импортировано | [S08MoveAnim.h:21](../../../unreal/Unmatched/Source/Unmatched/S08/S08MoveAnim.h), [S08IconMotion.h:103-105](../../../unreal/Unmatched/Source/Unmatched/S08/S08IconMotion.h) |
| Масштаб UI 75–150 %, проверка 720p (HI-02) | `ApplicationScale` нигде нет; кадров 720p/150 % на настоящих досках нет | нет | [HUD-AND-ICONS.md:196-200](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| Доступность: «не только цвет», контраст текста ≥ 4,5 : 1, значков ≥ 3 : 1 | команды различаются формой кольца (D-3), зоны — кромкой и штрихами (D-4); значок боя 16,3 : 1 (qa010, Cobble). Замера контраста текста HUD на настоящих досках не нашёл — не проверено | частично; по делегированию | [board-readability-decisions.md:16-17](../decisions/2026-09-29-board-readability-decisions.md) |
| Post-MVP экраны DE: шаги входа (DE-034), все столы лобби (DE-035), подсказки (DE-036), «История» (DE-037), 3D-победитель (DE-038, только по слову пользователя) | нет | planned, post-MVP | [07-sprint-backlog.csv:35-39](../de-footage/task/07-sprint-backlog.csv) |

### Чего нет
- `WBP_GameHUD` и C++-баз с `BindWidget` для 11 блоков и 9 экранов. Строк `SHOT widget` нет ни у одного блока.
- Экранов BOOT, PAUSE, загрузки партии; оверлеев INSPECT и RECONNECT; выбора героя и доски в ROOM; модала ABORTED и
  «Сыграть ещё».
- TOP, CONN, полного LOG, рубашек руки соперника, кнопок атаки и схемы.
- Ассета стиля (HI-08), флага `-S09Markers`, локализации, масштаба UI.
- Свежих кадров BOOT, LOGIN, ROOM и ABORTED на настоящих досках.

### Дефекты на кадрах
- Тост статуса накрывает ленту и верх руки. Тост «begin maneuver sent» лежит поверх тоста лимита руки.
- Карты прошлого боя висят у краёв в следующем ходу и под новым окном защиты. Должен лечить R-03: в упаковке с
  `9c8f92b7`, но живого кадра после него нет (не проверено).
- Панель колоды закрывает правый край поля вместе с фигурой и тегом HP (1080p и 720p).
- Опущенная рука уходит за нижний край. В одном кадре одновременно «AFTER COMBAT», «YOUR TURN» и «Syncing…».
- На de030 своя Medusa показывает «waiting», а Slate вверху пишет «YOUR TURN». Причина не проверена.
- HD-02 на настоящих досках выглядит иначе: плашка не закрывает Medusa, а уходит от неё к краю доски. HD-07: теги на
  швах. HD-08: у гарпий одинаковое «1/1». HD-01: отладка и `f-0-hero` в тосте. HD-09: неоновые полосы.

### Расхождения
- U-4 и HUD-RULES против кода: см. §10, строки 11–12.
- Слой над фигурами: в акте «не принято», в комментарии кода — «part of the accepted look». См. §10.

## 2. Поле: подсветки, кольца, значки зон

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| Пакет move-selection v2 (MS-D, MS-R, MS-T, MS-AT) | предложено; план утверждён | по делегированию (оркестратор, 2026-10-03); арт-приёмка оставлена пользователю | — | [10-approval.md:3-9,63-64](../move-selection/10-approval.md) |
| Язык подложек V-01…V-17 и V-04b, слои L0–L7 | предложено | — (03:197: «ПРЕДЛОЖЕНИЕ до арт-приёмки (MS-Q-04)») | — | [03-ux-spec.md:161-293](../move-selection/03-ux-spec.md) |
| Старое кольцо досягаемости ENV P4: `#FFC857`, обводка `#14110C`, актор на клетку | измерено, технически импортировано | отдельной приёмки нет; косвенно в приёмке Marmoreal 2026-10-01, которую заменил ENV-U16 | **по умолчанию** | [S08BoardActor.cpp:1780-1892](../../../unreal/Unmatched/Source/Unmatched/S08/S08BoardActor.cpp) |
| MS-T-08: подложки на ISM, `M_UM_MovePlate` (4 канала) | технически импортировано | G-LIVE прогона B — по делегированию | только `-S08MovePlates` | [S08MoveHighlight.cpp:34-38](../../../unreal/Unmatched/Source/Unmatched/S08/S08MoveHighlight.cpp) |
| MS-AT-41: стоимость подложек | измерено (прогон B, пакет `36a74fc5`): GPU +0,010…0,015 мс (порог 0,30) пройден; draw calls +8 при пороге 7 — не пройден | — | R-04: код `9c8f92b7` (одна ISM вместо четырёх); повторного замера нет, журнал H — «ждёт». Закрытие не проверено | [ms-at-41.json](../evidence/DE-FOOTAGE/2026-10-04/B/bench/ms-at-41.json) |
| DE-017: кольца-кандидаты V-17 и автовыбор | технически импортировано | по делегированию (D-DE-08, G-LIVE B) | логика по умолчанию; кольца только с флагом | [B-2026-10-04.md:370-373](../de-footage/task/runs/B-2026-10-04.md) |
| MS-T-12: pending V-11/V-12 и панель «YOUR CHOICE» | технически импортировано | по делегированию (G-LIVE C) | панель по умолчанию; подложки только с флагом | [05-implementation-plan.md:49](../move-selection/05-implementation-plan.md) |
| MS-T-17: последний ход соперника V-14/V-15, лента, стрелка у края | технически импортировано | по делегированию (G-LIVE D: «V-14 почти не видна на Marmoreal») | лента по умолчанию; контур только с флагом | [D/README.md:133,143](../evidence/DE-FOOTAGE/2026-10-04/D/README.md) |
| MS-T-09 путь и бейдж шагов; MS-T-10 призраки и бейджи порядка; MS-T-11 UMG-панель манёвра | нет (трасса `path=- ghost=-`; панель — Slate с полосой `#FF00FF`) | — | — | [05-implementation-plan.md:46-48](../move-selection/05-implementation-plan.md) |
| MS-T-13 подбор цвета и ΔE на экране; MS-T-27 приёмка и снятие флага | нет; `ms-thresholds.json` нет | — | — | [06-test-and-acceptance.md:18,64-65](../move-selection/06-test-and-acceptance.md) |
| MS-Q-04: цвет `#FFC857` или `#4CD2DC` | предложено, вопрос открыт | — | в профиле rev 22 обе карты `#FFC857` | [S08ArtBoardProfiles.json:97,124](../../../unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json) |
| Макеты MS-C v2 на реальных данных | предложено; устарели: нет V-17, Bahnschrift, глифы v2, pending фиолетовый | не показаны пользователю | PNG вне git | [move-selection-v2/README.md](../../../art/imagegen/move-selection-v2/README.md) |
| Макеты MS-C v1 (ImageGen) | отклонено | лично, 2026-10-03: «Используй реальные карты и изображения героев из бэкэнда. Они у нас уже есть в админке» | — | [move-selection-v2/README.md:8](../../../art/imagegen/move-selection-v2/README.md) |
| Кольца команд: P1 круг `#E8C06A`, P2 шестигранник `#5A7F9F` с разрывами | технически импортировано | место цвета — лично, 2026-09-29: «Акценты + кольцо (Recommended)»; форма и hex — по делегированию (D-2, D-3) | по умолчанию; откат `-S08GreyBoard`; A/B `-S08TeamColorMode=relative` | [board-readability-decisions.md:15-16,84-86](../decisions/2026-09-29-board-readability-decisions.md) |
| Кольцо выбора V-05 и ромб лидера | технически импортировано | — | по умолчанию | [S08FighterActor.cpp:160-164](../../../unreal/Unmatched/Source/Unmatched/S08/S08FighterActor.cpp) |
| Маркер цели: красные дуги и жетон v3 | технически импортировано; жетон — по делегированию (РД-1) | — | жетон по умолчанию, откат `-S08IconLegacy`; `-S08IconMotion` ничего не меняет | [S08IconMotion.cpp:268-270](../../../unreal/Unmatched/Source/Unmatched/S08/S08IconMotion.cpp) |
| Значки v3 для доски (`state-*`) | технически импортировано, к полю не подключены | по делегированию | — | [STYLE-v3.md:390-393](../../../art/imagegen/hud-icons-v3/STYLE-v3.md) |
| HI-06 значок зоны; HI-12 бейджи L6 у пространств | нет; HI-12 «мир или экран» не решено | — | — | [HUD-AND-ICONS.md:663,669](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| Кольцо хода на поле | нет (у DE тоже нет); AB-5 относится к портрету | — | — | [01-decisions.md:670](../de-footage/task/01-decisions.md) |

### Чего нет
- Линии пути, бейджа шагов, призраков, бейджей порядка, UMG-панели манёвра.
- Экранного замера ΔE подложек против зон карт. Внутриигрового A/B бирюзы: `#4CD2DC` есть только в 2D-макетах.
- Глифа «!» конфликта V-09 на виду: он рисуется в центре клетки и прячется под фигурой.
- Кадров MS-AT-30 с путями и худшего случая с 9 бойцами.

### Расхождения
- DE-017 «done, кольца по умолчанию» против флага `-S08MovePlates` в коде.
- B/README пишет, что V-17 лежит «снаружи командного кольца». Код и кадры показывают, что внутри (18,9 uu против
  22,0 uu). Верно второе.
- ΔE по hex топологии (`#FFC857` на жёлтой зоне 45,7) против кадров: на жёлтых зонах V-04b, V-11 и V-17 держатся
  только тёмной кромкой.
- MS-AT-31 проверяет V-01…V-16, а V-17 — самое спорное состояние.
- Докстринг `ue_move_plate_material.py:30` (на `9c8f92b7`) «Status: предложено (the look is accepted by the user,
  MS-Q-04 / MS-T-27)» читается как приёмка. Приёмки не было.

## 3. Значки и 2D

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| Направление: язык значков по DE | решение действует | лично, 2026-10-03: значки v2 «нарисованы криво», «топорно»; «возьми за основу существующую концепцию игры» (пересказ) | — | [PLAN-STATUS.md:20,178](../../art-pipeline/PLAN-STATUS.md) |
| Значки v3 «Жетон-эмблема»: 23 значка, маска, 3 варианта | технически импортировано | по делегированию, 2026-10-03 (`30529834`): «принято по делегированию (без личного просмотра пользователя)» | жетон цели по умолчанию с `f5d6d740`, откат `-S08IconLegacy`; в живом HUD 3 id из 23 | [ART-011 README.md:7](../evidence/ART-011/hud-icons-v3-2026-10-03/README.md) |
| STYLE-v3 (§1–§10) | по делегированию; §11 устарел | — | — | [STYLE-v3.md](../../../art/imagegen/hud-icons-v3/STYLE-v3.md) |
| Движок `draw_icons.py` | рабочий инструмент | — | — | [draw_icons.py](../../../art/imagegen/hud-icons-v3/_tools/draw_icons.py) |
| Текстуры `T_IV3_*` в UE: 336 = 84 базы × 24/32/48/64; импорт — `tools/art/icons_v3_import.py` | технически импортировано; 16, 21 и 96 px нет | — | — | [ue-import-report.json](../../../art/imagegen/hud-icons-v3/ue-import-report.json), [icons_v3_import.py](../../../tools/art/icons_v3_import.py) |
| Движение значков: контракт, эталон Python, рантайм | технически импортировано; UE против эталона \|Δ\| 0,393 (64 px), 0,726 (32 px) | по делегированию (ART-011) | анимируются жетон, сердце, трекер; галерея `-S08IconGallery` | [icon-motion.json:3-4](../../unreal/contracts/hud/icon-motion.json), [ICON-MOTION.md](../../unreal/contracts/hud/ICON-MOTION.md) |
| Живой жетон, qa010 icon pass | измерено на Cobble 5×6 в reduced motion; после 2026-10-04 доказательством не считается | — | — | [ART-011 README.md:63-75](../evidence/ART-011/hud-icons-v3-2026-10-03/README.md) |
| Формы DE-012 от Codex: кольцо хода (форма v3), сердце павшего, штамп X, слот DE | **художественно принято**; в движке и UE нет | лично, 2026-10-05: «приемку DE012 я одобряю» | — | [01-decisions.md:675-680](../de-footage/task/01-decisions.md), [hud-icons-de012-codex/README.md](../../../art/imagegen/hud-icons-de012-codex/README.md) |
| AB-5 тёплое кольцо хода | лично принято; включено по умолчанию в I-02 (откат `-S08TurnRingLegacy`) | лично, 2026-10-05: «тёплое» (пересказ) | только `-S08TurnRingIcon=marker-turn-ring` | [S08TurnPortraitWidget.h:36](../../../unreal/Unmatched/Source/Unmatched/S08/S08TurnPortraitWidget.h) |
| AB-6 ореол сердца | лично принято; включено по умолчанию в I-02 (откат `-S08HeartGlowLegacy`); цвет как в STYLE-v3 | лично, 2026-10-05: «вкл» (пересказ) | только `-S08HeartGlow` | [STYLE-v3.md:543,548](../../../art/imagegen/hud-icons-v3/STYLE-v3.md) |
| AB-7 трекер DE | лично принято; по умолчанию в I-02 (откат `-S08TrackerLegacy`) | лично, 2026-10-05: «DE» (пересказ) | трекер v3 | [01-decisions.md:672](../de-footage/task/01-decisions.md) |
| AB-8 сердце павшего и штамп X | лично принято; по умолчанию в I-02 (откат `-S08CrossLegacy`) | лично, 2026-10-05: «да», в форме Codex (пересказ) | сердце только чернеет | [01-decisions.md:673](../de-footage/task/01-decisions.md) |
| `marker-turn-ring-team` | отклонено выбором AB-5; из контракта и Content не удалён | лично, 2026-10-05 | опция `-S08TurnRingIcon=` | [ICON-MOTION.md:202-203](../../unreal/contracts/hud/ICON-MOTION.md) |
| Значки v2 (9 масок ImageGen + `compose_icons.py`) | отклонено | лично, 2026-10-03 | не используется | [hud-icons-v2/README.md:3](../../../art/imagegen/hud-icons-v2/README.md) |
| mvp-v1 UI: 99 PNG (из 304 в mvp-v1) | заменено: 72 «перерисовать», 19 «заменить», 8 «оставить» | — | чипы `T_UI_TeamShape_*` в плашках — по умолчанию | [HUD-AND-ICONS.md:417-534](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| Значки бейджей подбора хода: order, order-p2, refuse, conflict, ally, attack-from | предложено, только в макетах (`card_icons.py`); в v3 их нет | — | — | [HUD-AND-ICONS.md:394-415](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| HI-04 9-slice (~40 PNG); HI-06 значок зоны, «пас», «конец хода» | нет | — | — | [HUD-AND-ICONS.md:661,663](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| Веб-план HUD под Phaser 2026-06-11 | заменено | — | — | [imagegen-hud-asset-plan-2026-06-11.md](../../plans/imagegen-hud-asset-plan-2026-06-11.md) |

### Осмотр (область значков)
- v3 на 32 и 24 px чистый и цельный. Семейства различаются силуэтом, в сером набор держится.
- На 16 px разваливается: BOOST без цифры — пустое кольцо, звезда атаки — клякса, `state-pending-move` читается как
  «+», `resource-card` похож на «≡».
- Формы Codex на 24–32 px лучше кандидатов движка. На 16 px X на сердце — 2–3 пикселя и в сером почти пропадает.
- Тлеющий обод кольца (opacity 0,35) на navy-панели почти не виден. Ореол сердца читается как второй красный контур.

### Чего нет
- Размера 16 px в UE и экспорта `-light` для светлых панелей. Токенов `turn.flash.yellow` и `turn.flash.orange`.
- Подключения 20 id v3 к живому HUD: действия, фаза, связь, BOOST, бейджи.
- Звука на удары значков и состояний MS-T через API виджета.

### Расхождения
- Статус v3 записан по-разному в восьми местах: см. §10, строка 1.
- `e3fd3450` сделал анимацию `damage` у принятого `resource-hp-full` длиной 1000 мс со слоем glow. Это правка
  принятой записи без приёмки. После AB-6 она законна, но слой нужно включить по умолчанию, а флаг сделать откатом.

## 4. Карты в руке, портреты, данные

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| D-09: оригинальные 2D-арты карт как иллюстрации, подача новая | решение действует; метод подачи открыт (AD-OPEN-28) | лично, интервью 2026-09-18; дословной цитаты нет | — | [00-vision-and-scope.md:91,103](../00-vision-and-scope.md) |
| 27 карт MVP: EN 250×349 (26 PNG + 1 WebP), RU 287×398 WebP | измерено (наличие, sha256) | — | в UE нет | [reused-cardart.json](../../../art/imagegen/mvp-v1/reused-cardart.json) |
| `public/assets/decks`: 18 колод | к MVP не относится: веб-герои, Medusa и King Arthur там нет | — | — | `git ls-files public/assets/decks` (361 файл) |
| Копия скрапа в `docs/figma/figma-ready` | в git с `0641577c` (2026-06-11): 1575 карт, 70 аватаров, 69 рубашек, 77 миниатюр | — | — | [17-art-production-spec.md:1292](../17-art-production-spec.md) |
| Оригинальные рубашки по героям 768×1051 (логотип UNMATCHED) | измерено; в UE нет | — | — | `scraped-data/images/heroes/card-covers/` (вне git) |
| ImageGen-рамки и рубашки mvp-v1 (22 файла) | предложено; агент пометил «перерисовать» (сланец, бронза) | — | не используется | [HUD-AND-ICONS.md:470-491](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| Рука, инспектор, слот, карты боя, панель колоды | прототип: только текст; в `FS09CardView` нет полей изображения | — | по умолчанию | [S09HudModel.h:22-45](../../../unreal/Unmatched/Source/Unmatched/S09/S09HudModel.h) |
| Портреты DE-023 и диски DE-029 | прототип: монограммы, проигравший — тёмный силуэт | — | по умолчанию | [S08TurnPortraitWidget.h:7-8](../../../unreal/Unmatched/Source/Unmatched/S08/S08TurnPortraitWidget.h) |
| HI-05 аватары в HUD | нет. WebP UE 5.8 не читает (в `EImageFormat` WebP нет; известно с INT-016, 2026-09-18) | — | монограмма | [08-integration-decisions.md:164](../08-integration-decisions.md) |
| Аватары: Medusa 402², Arthur 800², помощники 128² (одна картинка на трёх гарпий) | измерено | — | — | `scraped-data/images/heroes/avatars`, `sidekicks` (вне git) |
| Правило «портреты = реальные `avatarUrl`» | неясно: слова пользователя 2026-10-03 о макетах, на HUD правило распространил агент; AD-OPEN-35 открыт | — | — | [HUD-AND-ICONS.md:374-375,650](../../unreal/contracts/hud/HUD-AND-ICONS.md), [17-art-production-spec.md:3101-3110](../17-art-production-spec.md) |
| Топология досок: `backend/prisma/fixtures/boards/{marmoreal,sarpedon}.topology.json`; иллюстрации карт — `scraped-data/images/maps/` (1337×866, вне git) | измерено (данные) | хранение иллюстраций — лично, ENV-U3: «Вне git, импорт скриптом» | — | [env-original-maps-decisions.md:28](../decisions/2026-09-30-env-original-maps-decisions.md) |
| Медиа-поля бэкенда | измерено: `Hero.imageUrl` — рубашка, `avatarUrl`, `sidekicks[].avatarUrl`, `Card.imageUrl`/`imageUrlRu`; у игровых досок `Board.imageUrl = null` | — | клиент UE не читает ни одного | [schema.prisma:399-521](../../../backend/prisma/schema.prisma) |
| Токены `card.*` (navy, cream, цвета типов) | предложено; замер на реальных картах совпадает | — | значки v3 используют; слот и панель колоды — свои литералы | [hud-style-tokens.json:29-36](../../unreal/contracts/hud/hud-style-tokens.json) |
| Лицензия скрапа (карты, аватары, рубашки, доски) | неясно; рабочее правило GAP-019 — «только внутренний прототип» | — | — | [08-integration-decisions.md:300](../08-integration-decisions.md) |
| 3D-карта как предмет (`ASSET-PROPS-CARDS-001`) | нет | — | — | [06-asset-manifest.csv](../06-asset-manifest.csv) |
| Art Hub: раздел 2D, карт и портретов | нет | — | — | [ArtHubPage.tsx:34-39,88-121](../../../admin/src/pages/art-hub/ArtHubPage.tsx) |

### Чего нет
- Ни одного лица карты, рубашки или аватара в UE; виджета карты; импорта с ключом `heroSlug:cardSlug` (INT-014).
- Исходников нужного размера. Иллюстрация на скане — около 195×215 px при инспекторе 520×720.
- Решений: метод подачи карты (AD-OPEN-28), одна рубашка или по героям, RU-сканы или EN с текстом поверх.
- Превью досок из БД (`imageUrl = null`).

### Расхождения
- Внутри HUD хитрость синяя в слоте (`#2E6CB4`) и жёлтая в панели колоды (`#D8B03C`). Токен — `#FDBE72`. В языке
  карт синий означает защиту.
- Фолбэк CUE-006 «рамка UI-CARD-FRAME» на деле текстовая панель: ассета рамки нет.
- Админка в списке героев под заголовком «Avatar» показывает `Hero.imageUrl`, то есть рубашку. В спецификации нужно
  называть поле `avatarUrl`, а не «как в админке».

## 5. Герои и анимации

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| ART-DEFAULT: готовые фигуры v2 и арт-вид по умолчанию | решение о показе | лично, 2026-10-04: «У нас же есть уже готовые модели для Артура и Мерлина и так далее.»; правило — «закрепи это в главных правилах проекта, как собираются сцены с героями» | по умолчанию; откат `-S08HeroesLegacy`, `-S08GreyBoard`, `-S08DioramaLegacy` | [S08ArtLook.h:3-4](../../../unreal/Unmatched/Source/Unmatched/S08/S08ArtLook.h), [AGENTS.md](../../../AGENTS.md) |
| ART-004/006/007/008: `SK_Medusa_H2LD`, `SK_KingArthur_H2LD`, `SK_Merlin_H2LD`, `SK_Harpy_H3LD` ×3 | технически импортировано | по делегированию: GD-058 final 2026-10-03, «без личного просмотра пользователя» | по умолчанию | [GD-058 final README.md:10-11,86](../evidence/GD-058/final-2026-10-03/README.md) |
| ART-012 (код героев v2: маппинг, масштаб, cook) | технически импортировано | — | по умолчанию | [S08HeroesV2.h:30-51](../../../unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h) |
| Поворот фигур (ветка `wip/art012-facing-2026-10-04`, `60c76cac`) | черновик: не собран, отстаёт на 138 коммитов (на `9c8f92b7`), документа FF-1 нет | — | сейчас правило полуполя: часть фигур стоит спиной к камере | [S08MoveAnim.h:49,67](../../../unreal/Unmatched/Source/Unmatched/S08/S08MoveAnim.h) |
| ART-013: проигрывание клипов | технически импортировано; кадры внутри Lunge и Death пиксельно не проверены | — | по умолчанию | [plan-status.json:1408-1430](../../art-pipeline/plan-status.json) |
| H2Anim: 16 клипов (Idle, LungeAttack, HitReact, DeathSettle), 24 fps | технически импортировано; WARN: skin_stretch у 11 клипов, limb_body_R у Arthur, подол ниже подставки | решения anim-v2 — по делегированию, 2026-09-29 | по умолчанию | [anim-v2-decisions.md:5-7,57-60](../decisions/2026-09-29-anim-v2-decisions.md), [clip-manifest.json](../../art-pipeline/animation-library/clip-manifest.json) |
| Риг `UM_HUMANOID_17_v2` | предложено (на деле на нём все клипы) | — | — | [RIG-CONTRACT.md:5](../../art-pipeline/rig/RIG-CONTRACT.md) |
| DE-010: notify `Contact` и `CPD_HitTint` (канал 12) | технически импортировано | по делегированию (ревью A04 `8001c317`) | по умолчанию | `07f606bd`, [S08HeroesV2.h:140-157](../../../unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h) |
| DE-011: растворение, 8 MIC | технически импортировано; вид — AB-4 без ответа | — | fade; «пепел» только `-S08DissolveAsh` | `002bfd01`, [S08HeroesV2.h:194-202](../../../unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h) |
| DE-019: смерть по этапам | измерено: удар → экран 3167 мс | по делегированию (прогон C: «принято (G-LIVE, G-COST)») | по умолчанию | [C/README.md:4,166](../evidence/DE-FOOTAGE/2026-10-04/C/README.md) |
| DE-021: поза хода (280 мс на ребро, наклон 10°) | измерено; AB-1…AB-3 без ответа | — | подскок 0, наклон 10°, ease выкл; A/B `-S08MoveHop`, `-S08MoveLean`, `-S08MoveEase` | `18593b2b`, [S08MoveAnim.h:44-50](../../../unreal/Unmatched/Source/Unmatched/S08/S08MoveAnim.h) |
| ART-016: маска Arthur, маховые Harpy r3.3 | измерено (done) | — | по умолчанию | [plan-status.json:1488-1516](../../art-pipeline/plan-status.json) |
| ART-014: свет героев P9b (key + rim на канале 1) | предложено, измерено; гейты D на Marmoreal FAIL | — (отзыв пользователя 2026-10-02: «Сейчас кажется, что они сильно пересвечены…») | по умолчанию; откат `-NoHeroLight` | [ENV-HERO-LIGHT.md:3,63-69](../../art-pipeline/ENV-HERO-LIGHT.md) |
| ART-018: длинный K2 и зумы Medusa | измерено только на Cobble — доказательством не считается | — | — | [plan-status.json:1541-1566](../../art-pipeline/plan-status.json) |
| Концепты `hero-quality-v1` (эталон look-dev) | предложено; эталоном назначены по делегированию | — | — | [lookdev-v2-decisions.md:14-15](../decisions/2026-09-29-lookdev-v2-decisions.md) |
| Видео-референсы SYNTX (24 ролика Kling и Seedance, 157,5 токена) | измерено; поля лицензии нет | — | — | [animation-refs/manifest.json](../../art-pipeline/animation-refs/manifest.json) |
| Mocap (video-to-motion, ретаргет на UM17) | нет: `retarget_to_um17.py` не написан, сервиса нет; документ ориентирован на риг v1 | — | — | [VIDEO-TO-MOTION.md:45-90](../../art-pipeline/animation-library/VIDEO-TO-MOTION.md) |
| AD-OPEN-06: нумерация гарпий H1–H3 | нет решения; в UE номеров нет | — | теги v2 компактные, без имени | [S08FlowGameMode.cpp:7819-7830](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp), [17-art-production-spec.md:2765](../17-art-production-spec.md) |
| Клипы сверх четырёх (ходьба, защита, способности, победа) | не в MVP | лично, 2026-09-18 (D-11, интервью; формулировка решения в 00, не дословная цитата): «лёгкий риг (idle, выпад при атаке, вздрагивание при уроне, оседание при смерти), перемещение плавным скольжением» | — | [00-vision-and-scope.md:105](../00-vision-and-scope.md), [18-animation-production-brief.md:199-213](../18-animation-production-brief.md) |
| 3D остальных героев (около 88 в данных) | нет; 3D только у 4 персонажей MVP | — | — | [PLAN-STATUS.md:23-24](../../art-pipeline/PLAN-STATUS.md) |
| Откатные фигуры (кандидат Medusa, блок-ауты ART-003) | заменено, только откат | — | `-S08HeroesLegacy` | — |

### Чего нет
- Личной арт-приёмки хотя бы одной фигуры или клипа. Шаблона акта приёмки героя.
- Различимости гарпий в виде по умолчанию: у блок-аутов были полные теги «Harpies 1/2/3», у v2 их нет.
- Позы рывка в пути (у DE есть) и смерти с колен (подол скинен жёстко, поэтому смерть — поклон корпусом).
- Живой смерти гарпии: её покрывает только тест `DeathStage.ResultGate`.
- Свежих кадров шести фигур v2 на нарисованном Marmoreal без флагов.

### Расхождения
- AGENTS.md и бриф 18 называют фигуры «принятым артом». Реестр и акт — «технически импортировано, по
  делегированию». Слово «accepted» в AGENTS.md означает право быть видом по умолчанию, а не арт-приёмку.
- `plan-status.json` держит блокер «GD-058 не принят» у ART-006…008, а GD-058 final снимает его по делегированию.
- Бриф 18 §0.1: «AnimNotify Contact в ассетах нет». Notify есть с `07f606bd`.
- Читаемость на K1: фигуры 35–55 px, лицо Medusa на K2 1,6× не читается (голова 17,8 px, GD-058 FAIL), тёмные маховые
  гарпий вне допуска, кант Arthur P1 сзади сливается с каймой.

## 6. VFX и постановка

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| `cue-table.json`, 18 CUE, ревизия `de-021-2026-10-05` | предложено | синхронизация DE-003 — по делегированию | в C++ встроены только CUE-008…011, 013, 014 | [cue-table.json:3-4](../../unreal/contracts/cue-dispatcher/cue-table.json) |
| `CUE-DISPATCHER.md`: правила Niagara §3, шкала боя и смерти §3.1 | предложено; §3.1 реализован, §3 нет | — | — | [CUE-DISPATCHER.md:3,47,57-103](../../unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md) |
| `07-animation-vfx-audio.csv` | предложено | — | — | [07-animation-vfx-audio.csv](../07-animation-vfx-audio.csv) |
| DE-018 и DE-019: постановка боя и смерти | технически импортировано; бой 3933 мс, удар → экран 3167 мс | по делегированию: прогон C — «DE-018 и DE-019 приняты целиком» | по умолчанию | [C/README.md:4,79,164](../evidence/DE-FOOTAGE/2026-10-04/C/README.md) |
| CUE-001 наведение (канал Rim) | нет | — | — | [cue-table.json:10-59](../../unreal/contracts/cue-dispatcher/cue-table.json) |
| CUE-002 выбор (`SM_Marker_SelectionRing`) | технически импортировано | — | по умолчанию | [S08FighterActor.cpp:157-163](../../../unreal/Unmatched/Source/Unmatched/S08/S08FighterActor.cpp) |
| CUE-003 подтверждение | прототип; таблица называет несуществующий `M_HighlightGameLayer` | — | золотые кольца | [cue-table.json:132](../../unreal/contracts/cue-dispatcher/cue-table.json) |
| CUE-006 свечение карты | нет; фолбэк — текстовый слот DE-026 | — | — | [cue-table.json:242-294](../../unreal/contracts/cue-dispatcher/cue-table.json) |
| CUE-007 перемещение | поза DE-021 есть; пыли нет | поза — по делегированию | по умолчанию | [cue-table.json:295-368](../../unreal/contracts/cue-dispatcher/cue-table.json) |
| CUE-008 объявление атаки | прототип: кольцо цели и жетон вместо вспышки направления | функция — по делегированию | по умолчанию | [S08FlowGameMode.cpp:606-618](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp) |
| CUE-009 защита | нет на фигуре; есть только слот в HUD | — | — | там же |
| CUE-010 раскрытие и резолв | прототип: Slate-плашки, метка исхода текстом; строки EFFECTS (R-02) вживую ещё не выпадали | шкала — по делегированию | по умолчанию | `c3a12838`, `aca0e84b` |
| CUE-011 урон | технически импортировано: HitReact, красная заливка всей фигуры 450/550 мс, «−N» +60 мс; всплеска нет | шкала — по делегированию; вид заливки пользователю не показывали | по умолчанию | [S08FighterActor.cpp:800-815](../../../unreal/Unmatched/Source/Unmatched/S08/S08FighterActor.cpp) |
| CUE-012 лечение | нет; событие не подаётся | — | — | [S08CueDispatcher.cpp:33-60](../../../unreal/Unmatched/Source/Unmatched/S08/S08CueDispatcher.cpp) |
| CUE-013 смерть | технически импортировано: DeathSettle и fade; частиц «пепла» нет | этапы — по делегированию; вид — AB-4 без ответа | fade; `-S08DissolveAsh` | [S08HeroesV2.h:159-212](../../../unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h) |
| CUE-014 способность | нет: строка есть, в игре не подаётся (0 строк в трассах) | — | — | [S08CueDispatcher.cpp:55-57](../../../unreal/Unmatched/Source/Unmatched/S08/S08CueDispatcher.cpp) |
| CUE-015 начало хода | баннер — прототип; тёплое кольцо (AB-5) принято лично, не включено | лично, 2026-10-05 | баннер по умолчанию | §3 |
| CUE-016 победа и поражение | прототип: UI-затемнение без грейда и виньетки | шлюз +1000 мс — по делегированию | по умолчанию | [cue-table.json:858](../../unreal/contracts/cue-dispatcher/cue-table.json) |
| CUE-017 разрыв связи; CUE-018 восстановление | 017 — постпроцесса нет; 018 — не проверялось | — | — | [cue-table.json:876-968](../../unreal/contracts/cue-dispatcher/cue-table.json) |
| Каналы материала фигуры | Rim (9–10) и FxFlash (5–8) кодом не пишутся; работают HitTint 12, Dissolve 13, DissolveStyle 14; Fade 11 — только у подставки | — | — | [S08HeroesV2.h:152-174](../../../unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h) |
| Niagara окружения: 10 `NS_Env_*` | технически импортировано; вне git | Sarpedon — по делегированию | по карте (§7) | `unreal/Unmatched/Content/EnvKit/FX/` |
| Сырьё паков: FreeParticle_SoftTofu (CC BY 4.0), Stylish_Fire_VFX (Fab Standard), Particles_Wind (не используется) | технически импортировано (только производные) | лично, 2026-10-01: «И все только для личного и локального использования в локальной сети.» | — | [CREDITS-fab.md:3-4,19-21](../../art-pipeline/CREDITS-fab.md) |
| `UNiagaraEffectType`, пул, прогрев, детерминизм и сид, адаптер спавна, `AssetResolver` в игре | нет | — | — | [CUE-DISPATCHER.md:57-61](../../unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md) |
| AD-OPEN-34: стиль VFX | нет решения | — | — | [17-art-production-spec.md:3087-3099](../17-art-production-spec.md) |
| ART-010: VFX и минимальный звук 18 CUE | planned; блокер GD-058 снят 2026-10-03 | — | — | [14-sprint-backlog.csv:69](../14-sprint-backlog.csv) |
| Концепты VFX mvp-v1 (26 файлов, 5 флипбуков) | предложено; дефекты альфы | — | — | `art/imagegen/mvp-v1/vfx/` |
| Концепты Codex DE-011: A «пепел» (рекомендован), B «дым» | предложено | — | — | [hud-icons-de012-codex/README.md:104-126](../../../art/imagegen/hud-icons-de012-codex/README.md) |
| `cue_contract.py` и 19 фикстур | измерено: PASS 18 / 19 / 55 тестов | — | — | [H-2026-10-05.md:171-172](../de-footage/task/runs/H-2026-10-05.md) |

### Чего нет
- Ни одной боевой системы Niagara и инфраструктуры для них. Нет бенча ΔGPU ≤ 1 мс на худшем наборе. Не проверено,
  попадают ли эмиссивные частицы в Lumen.
- Стиля VFX и правила «форма дублирует цвет» для урона и лечения.
- Записей реестра ассетов для заливки, MIC растворения, `M_UM_MovePlate`, жетона и будущих NS.
- Синхронизации кадров VFX со звуковыми точками DE-032: звук ведёт другой чат.

### Расхождения
- Контракт называет каналы FxFlash, Rim, Fade; код работает через CPD 12–14. Трасса пишет `mat=FxFlash` и `clip=missing`,
  хотя HitReact играет: `AssetResolver` в игре не задан.
- CUE-014 Medusa: контракт и 07 — «луч от Head», живое исследование DE — вихрь на модели без луча.
- AD-OPEN-34 описывает доску S04: «конфликт только с red». На обеих настоящих картах есть и красные зоны (Marmoreal 8,
  Sarpedon 12), и зелёные (28 и 16). Красный плащ Arthur сливается с заливкой удара на K1.
- DE-011 обещал «Материал/Niagara», сделан только материал.

## 7. Окружение и рендер

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| Рендер: DX12/SM6 + Lumen, эталон High, SP 100, отпечаток `RENDER` | технически импортировано | лично, 2026-09-28: «Графика: DX12 + Lumen сейчас»; «High как эталон» (запись вторичная) | по умолчанию; `RENDER reference=1` в кадрах 2026-10-05 | [render-reference.json](../../art-pipeline/render-reference.json), [render-ui-user-decisions.md:9-10](../decisions/2026-09-29-render-ui-user-decisions.md) |
| FPS: 60 по умолчанию, 30 на клиента в демо | измерено: ACC-022 60,00 FPS на 6/6 видах (ПК разработки RTX 4090, не D-07; Marmoreal на P5c, `-Bench` без HUD); на D-07 открыто | по делегированию (GD-058 final §5.1) | `FrameRateLimit=60` | [GD-058 final README.md:217-229](../evidence/GD-058/final-2026-10-03/README.md) |
| «Только настоящие доски» | исполнено | лично, 2026-10-04: «Давай оставим только доски, которые осуществлены на реальных досках из игры.» | Marmoreal по умолчанию | [real-boards-only.md:7](../decisions/2026-10-04-real-boards-only.md) |
| ENV-U0…U14: схема доски, вся иллюстрация + 3D вокруг, вне git, концепты v1/v2, K1 ×1,25, паки Fab | решения действуют; часть заменена U15/U16 | лично, 2026-09-30…10-01 («Вся иллюстрация + 3D вокруг», «Вне git, импорт скриптом», «v1», «v2») | — | [env-original-maps-decisions.md:9-188](../decisions/2026-09-30-env-original-maps-decisions.md) |
| ENV-U15: Marmoreal P5c «1 Принято» | заменено ENV-U16 | лично, 2026-10-01: «1 Принято»; п. 5: «Думаю Все проблемы уйдут когда мы вклеим задники из концептов» | — | [env-original-maps-decisions.md:192-210](../decisions/2026-09-30-env-original-maps-decisions.md) |
| ENV-U16: Marmoreal — нарисованный задник, Sarpedon — lit3d путь 1 | решение; для Sarpedon исполнено, для Marmoreal нет | лично, 2026-10-04: «Нарисованный задник», «lit3d — путь 1» | — | [env-original-maps-decisions.md:248-252](../decisions/2026-09-30-env-original-maps-decisions.md), [AGENTS.md](../../../AGENTS.md) |
| Marmoreal P5c: дворец, деревья Forest, фонари на тумбах, поднос T2b, туман и луна | технически импортировано; **по умолчанию вопреки ENV-U16** | — | `conceptPaste.default "off"`; отката на нарисованный нет, есть только флаг | [S08ArtBoardProfiles.json:99](../../../unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json) |
| Вклейка Marmoreal по `-ConceptPaste` | прототип: сырой `marmoreal-v1`, `details` и `overlays` пусты, живы 2 светлячка, 5 огней без мерцания | — | `-ConceptPaste`, `-EnvLayoutVariant=concept` | [marmoreal.paste.json:49-50](../../../tools/art/concept_paste/marmoreal.paste.json) |
| Sarpedon lit3d P10: остров, корабль, форт под de-lit живописью | технически импортировано; FAIL: SSIM корабля 0,442, G4 0,49, G2, G6; В-5, В-6 не делались; пушки статичны | направление — лично (2026-10-04); вид P10 — по делегированию (РД-3, «без личного просмотра пользователя») | по умолчанию (`default:on, mode:lit3d`); откат `-ConceptPaste=paste`, `-ConceptPaste=0` | [S08ArtBoardProfiles.json:126](../../../unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json), [GD-058 sarpedon README.md:6,57-77](../evidence/GD-058/sarpedon-2026-10-03/README.md) |
| Sarpedon P7c (плоская вклейка) | заменено; вариант | — | `-ConceptPaste=paste` | [ENV-CONCEPT-PASTE.md:63-72](../../art-pipeline/ENV-CONCEPT-PASTE.md) |
| Рама frame-002 | технически импортировано | ширина — лично, 2026-10-01: «4b оставить» | на обеих картах | [env-original-maps-decisions.md:197](../decisions/2026-09-30-env-original-maps-decisions.md) |
| Поднос `SM_TableBase_T2b` и земля CC0 | технически импортировано; в целевых видах скрыт | глубина — лично, 2026-10-01: «4a оставить» | виден только в P5c | [S08Diorama.h:27-43](../../../unreal/Unmatched/Source/Unmatched/S08/S08Diorama.h) |
| Профили `S08ArtBoardProfiles.json` rev 22 и 7 раскладок `EnvLayouts` | предложено | — | в паке | [S08ArtBoardProfiles.json:3-4](../../../unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json) |
| GD-058 final (эталон K1/K2 на Marmoreal P5c) | по делегированию; Marmoreal-часть опирается на заменённое решение | по делегированию, 2026-10-03 | — | [GD-058 final README.md:27,59](../evidence/GD-058/final-2026-10-03/README.md) |
| Worktree `C:/tmp/wt-envmaps` (`feat/env-original-maps` @ `a8a9d332`) | заменено: влит полностью, отстаёт на 213 коммитов (на `9c8f92b7`) | — | — | `git merge-base --is-ancestor` |
| Окружение вне git: EnvMaps, EnvKit, Fab, плиты Sarpedon и их промпты (только `C:/tmp/envmaps-research`) | технически импортировано только на этой машине | ENV-U3/U7 — лично | — | [manifest.sarpedon.json](../../../tools/art/concept_paste/manifest.sarpedon.json) |
| Инструменты: live tune, `render_bench.py`, Art Tuner, `concept_paste/*`, `concept_scene/*` | технически импортировано, измерено | процесс live tune — лично, 2026-10-02: «Конечно, делай и закрепи это в основном пайплайне.» | — | [LIVE-TUNE.md:3](../../../tools/art/render/LIVE-TUNE.md) |

### Чего нет
- Ассетов нарисованного Marmoreal: чистой плиты без нарисованных фонарей, достройки краёв (сейчас на K1×0,65 край
  растянут примерно на 11 %), плиты ×2, анимированных деталей.
- Отката на P5c для Marmoreal в списке откатов AGENTS.md. Механизм есть: `-NoConceptPaste`, `-ConceptPaste=0`.
- Решения по подносу T2b, который не виден ни в одном целевом виде.
- Замера цены нарисованного Marmoreal и пересъёмки эталона GD-058 после смены вида.
- Строки ENV-U16 в `plan-status.json`. Правила задника для будущих карт.

### Расхождения
- AGENTS.md верно пишет, что с `0f2bdb9a` P5c — вид без флагов. Но корень разрыва ENV-U16 старше — 2026-10-01: см.
  §10, строка 5.
- Блокеры реестра Sarpedon «решение за пользователем» устарели: направление выбрано лично 2026-10-04.
- AGENTS.md пишет «animated … cannons». Пушки — статичные пропсы. Анимированы огонь, знамя, листва, фонарь на леере,
  водопад.
- README прогонов DE пишут «нарисованный задник» о сыром прототипе по флагу. Это не реализация ENV-U16.

## 8. Изучение Digital Edition

Исследования:
- YouTube-стрим DE 2.1.0: [README.md](../de-footage/README.md), `timings.csv` (45 строк), A1–A7, `997ae85e`.
- Живая игра в купленном клиенте 2.2.1, серии s01–s05 (s04 — наш срез): [live-2026-10-04/README.md](../de-footage/live-2026-10-04/README.md),
  `timings-live.csv` (160 строк), [APPROXIMATION.md](../de-footage/live-2026-10-04/APPROXIMATION.md), `74208f43`.
- Кадры DE лежат только локально (`C:/tmp/de-footage`, `C:/tmp/de-live`). Все 467 картинок в
  `evidence/DE-FOOTAGE` — кадры нашего клиента.

| ID | Решение | Тайминг | Статус | Где сделано |
|---|---|---|---|---|
| F-01 / D-DE-01 | темп боя: удержание на чтение, строки эффекта, пауза «счёт», пропуск кликом, Space, Enter | 1000 мс (только при тексте эффекта), +600 на строку (подсветка 400 + 200), пауза 300; бой ≈3,9 с против ≈12,4 у DE | по делегированию; вживую 3933 мс | `c3a12838` (DE-018), `aca0e84b` (R-02) |
| F-02 / D-DE-02 | шаг | 280 мс на ребро линейно, подскок 0, наклон 10° (вход 60), разворот ≤50, доворот 120, возврат 150 | по делегированию; вид AB-1…AB-3 без ответа | `18593b2b` (DE-021) |
| F-03 / D-DE-03 | выпад в резолве | CUE-008 600 мс без клипа; Lunge после слэма +300; контакт по notify (Arthur 292, Merlin и Medusa 333, Harpy 292–375); заливка 450/550; «−N» +60; HP +80 | по делегированию | `07f606bd`, `c3a12838` |
| F-04 / D-DE-04 | «−N» всегда | 900 мс × скорость, от контакта +60 | по делегированию; вид не принят | DE-018 |
| F-05 / D-DE-05 | колода боковой панелью | открытие ≤100, закрытие 150, автозакрытие при вводе | по делегированию; вид — Slate-список | `00446e54` (DE-030) |
| F-06 / D-DE-06 | экран результата | вход 500, кроссфейд к доске 250, без автозакрытия; «Сыграть ещё» только VS_AI | по делегированию; «Сыграть ещё» и ABORTED не сделаны | `fc5318db`, `e5223022`, `00f8a1be` |
| F-07 / D-DE-07 | кольцо хода и баннер | кольцо: вспышка 1000, затем тлеет (≈0,35); баннер 600 только на свой ход, ввод открыт | поведение — по делегированию; кольцо выключено до прогона I | `e077974a` (DE-023) |
| F-08 / D-DE-08 | кольца-кандидаты V-17, автовыбор единственного бойца | в кадр открытия манёвра | по делегированию; кольца только с `-S08MovePlates` | `b691e78a` (DE-017) |
| F-09 / D-DE-09 | смерть по этапам | HitReact 450 → DeathSettle → неподвижность 300/0 → растворение 500/400; исчезновение ≈2125/1725; крест +1100; экран +1000 (удар → экран ≈3,1 с) | по делегированию; вживую 3167 мс; крест не рисуется | `38ca9f13`, `002bfd01`, `5e950d33` |
| F-10 / D-DE-10 | карта схемы соперника | прилёт 200, удержание 1500; своя 500; буст соперника в слоте ≥1000 | по делегированию; слот — Slate | `3f9661a3`, `d786188f`, `647e33ca`, `2c3ed515` |
| F-11 / D-DE-11 | выбор без целей пропускается | тост `why.effect.no.targets` | по делегированию | `4153bd2f`, `e7e27583` |
| F-12 / D-DE-12 | трекер действий: поведение | отметка при выборе, возврат при Undo; трекер соперника только в его ход (появление 150) | поведение — по делегированию; вид — AB-7 | `5b1b167a`, `e077974a` |
| AB-1…AB-4 | подскок, наклон, ease, fade или «пепел» | 0 / 10° / выкл / fade | предложено, ответа нет | [AB-SHEET/README.md:15-18](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/README.md) |
| AB-5 | тёплое кольцо хода | жёлтый → оранжевый → красный 1000, затем тлеющий обод | лично (2026-10-05); не включено | прогон I |
| AB-6 | ореол сердца при уроне | пульс 200–1000 | лично «вкл» (пересказ); цвет не решён; не включено | прогон I |
| AB-7 | трекер DE | заливка типом действия 300, пульс пустого слота 770 | лично «DE» (пересказ); не реализовано | прогон I |
| AB-8 | сердце павшего и штамп X | +1100 от контакта; штамп 200 | лично «да, в форме Codex» (пересказ); не реализовано | прогон I |
| SD-44 | «Пас» убран, ход кончается после двух действий | — | по делегированию | `5f8e6a3e` (DE-015) |
| SD-48 | бой без движения камеры, крупные карты у краёв поля | — | по делегированию; текстовые плашки | DE-018 |
| SD-26, SD-28 | рука опускается при выборе цели; слот карты-источника; ▲▼ | — | по делегированию; Slate | DE-026, DE-020 |
| SD-42, SD-43 | тост лимита руки 7 — один раз за партию | — | по делегированию; тосты накладываются | `070ae8aa`, `0fce04ae` |
| SD-15, SD-31 | строка «что делать сейчас», глагол соперника | — | по делегированию; плашка «ваш боец» вживую не выпала | `5b1b167a` (DE-022) |
| R-11 (CUE-014 Medusa) | вихрь на модели, вспышка сердца цели, луча нет | HP через ~534 мс от кольца | данные есть; не реализовано (GD-044) | [live README.md:492-512](../de-footage/live-2026-10-04/README.md) |
| Граница заимствования | только идеи, порядок, тайминги; не брать ассеты, тексты, звуки, файлы игры | — | лично, 2026-10-05: «Digital Edition — только идеи и тайминги. Её арт не копировать, файлы не распаковывать.» | в git DE-кадров нет |
| Прогон H (R-01…R-05) | журнал эффектов, строки эффектов, догон постановки, MS-AT-41, тест кликов | — | R-01…R-03 done; R-04 — код в `9c8f92b7` (21:34), журнал ещё «ждёт», замера нет; R-05 ждёт | `6115fb80`, `aca0e84b`, `1c3ce915`, `9c8f92b7`; [H-2026-10-05.md:15-23](../de-footage/task/runs/H-2026-10-05.md) |
| Прогон I | включить AB-5…AB-8 в форме Codex | — | нет: ни плана, ни журнала, владельца нет | [01-decisions.md:682](../de-footage/task/01-decisions.md) |

### Расхождения
- Шесть документов после `195352b4` всё ещё пишут «кандидаты» или «ждёт ответа»: бэклог DE (DE-012, DE-023, DE-028),
  CLOSEOUT §5, STYLE-v3 §11, HUD-AND-ICONS:604, ICON-MOTION, `icon-motion.json:52`, README пакета Codex.
- Таблица «Что сделать после ответа» листа AB не содержит переноса форм Codex в движок v3 и переимпорта в UE. Без
  этого флаг включит формы движка, а не принятые формы Codex.
- Раскладка панелей: у DE по диагонали (своя слева внизу, соперник справа вверху), в 02 соперник слева вверху, в коде
  обе колонкой слева внизу. Решения нет.
- STYLE-v3 правило 9 разрешает «мазок кисти и брызги туши DE» для баннеров ≥48 px, а бриф запрещает кляксу «COMBAT!».

## 9. Арт-дирекшн, реестры, инструменты и сервисы

| Пункт | Статус | Принято (кем, когда) | По умолчанию / флаг | Источник |
|---|---|---|---|---|
| D-02: стилизованная мрачноватая атмосферная диорама | решение действует | лично, 2026-09-18 (интервью) | — | [00-vision-and-scope.md:96](../00-vision-and-scope.md) |
| D-06: модели с нуля, скрап — только референс | решение действует; на деле Tripo по концептам (правка D-06 только в proposals) | лично, 2026-09-18 | — | [00-vision-and-scope.md:100](../00-vision-and-scope.md) |
| D-10: камера фиксированная, зум колесом | решение действует | лично, 2026-09-18 | по умолчанию | [00-vision-and-scope.md:104](../00-vision-and-scope.md) |
| `03-art-direction.md` v0.1: С-1…С-11, камера, К-1…К-3 | предложено, во многом устарел: «без Lumen», «за подносом тьма», P2 `#9FC2D8`, Cobble | — | — | [03-art-direction.md:3,30,38](../03-art-direction.md) |
| ART-002: направление B Painted Miniature | по делегированию, 2026-09-27; фигуры фактически сделаны по hero-quality-v1 (реалистичнее) | пользователь: «Сам реши» | — | [ART-002 README.md:3,79](../evidence/ART-002/README.md) |
| Цвет команды на фигуре: акценты одежды и кольцо | технически импортировано (`UseTeamAccent=true`) | лично, 2026-09-29: «Акценты + кольцо (Recommended)» (уточняет U-3 «TeamColor: ещё и на одежде») | по умолчанию | [lookdev-v2-decisions.md:10-12](../decisions/2026-09-29-lookdev-v2-decisions.md) |
| Палитра D-2: P1 `#E8C06A`, P2 `#5A7F9F`, абсолютно по месту | по делегированию; Q-304 открыт | советник по «делай все без меня» | по умолчанию; A/B `-S08TeamColorMode=relative` | [board-readability-decisions.md:15,86](../decisions/2026-09-29-board-readability-decisions.md), [S08Team.h:48](../../../unreal/Unmatched/Source/Unmatched/S08/S08Team.h) |
| AD-OPEN-23: палитра панелей, текста, кнопок; владелец токенов | нет решения | — | значения из `S08ArtHudStyle.h` | [17-art-production-spec.md:2960-2970](../17-art-production-spec.md) |
| Правило «принятый арт по умолчанию, флаг только откатывает; смотреть кадр перед отчётом» | действует | лично, 2026-10-04 | — | [AGENTS.md](../../../AGENTS.md) |
| Правило «макеты UI только на реальных данных» | действует | лично, 2026-10-03 (цитата в §2) | — | [move-selection-v2/README.md:5-9](../../../art/imagegen/move-selection-v2/README.md) |
| Агент генерирует сам по карточке, траты пишет, покупки — пользователь | действует; отменяет поле `syntxConfirmation` журнала и запрет в аудио-брифе | лично, 2026-10-05: «Агент должен э, генерировать сам все permissions у него есть.» | — | [00-VISUAL-BRIEF.md:12-15,472-476](00-VISUAL-BRIEF.md) |
| `17-art-production-spec.md`: AD-CNF, AD-OPEN, AD-AC | предложено (сводка 2026-09-25 с правками до 2026-10-03); основной реестр открытых вопросов арта | — | — | [17-art-production-spec.md:3-7](../17-art-production-spec.md) |
| `18-animation-production-brief.md` | предложено (черновик для автора) | — | — | [18-animation-production-brief.md:3-5](../18-animation-production-brief.md) |
| `18-third-party-tools-and-assets-decisions.md` | решение автора | лично, 2026-09-27 (утверждено по итогам ревью) | — | [18-third-party-tools-and-assets-decisions.md:3](../18-third-party-tools-and-assets-decisions.md) |
| `06-asset-manifest.csv` (50 строк) | заменено по сути: UI с путями `/Game/UI/*` в planned, карты blocked, хотя исходники есть | — | — | [06-asset-manifest.csv](../06-asset-manifest.csv) |
| `asset-registry.json` (33 записи, только 3D) | измерено; часть блокеров устарела | — | — | [asset-registry.json](../../art-pipeline/asset-registry.json) |
| `PLAN-STATUS.md` и `plan-status.json` | измерено (срез 2026-10-03T23:58Z); не знают ENV-U16, DE-010/011, DE-012 | — | читает Art Hub | [PLAN-STATUS.md:3-5](../../art-pipeline/PLAN-STATUS.md) |
| `DIRECTORY-MAP.md` | измерено; не знает hud-icons-v2/v3, Codex DE-012, hero-quality-v1, env-v1, move-selection | — | — | [DIRECTORY-MAP.md](../../art-pipeline/DIRECTORY-MAP.md) |
| 3D-пайплайн: PIPELINE, ADDING-AN-ASSET, BLENDER-MODEL-HANDBOOK, `tools/tripo-pipeline` 0.6.0 | измерено (герои, поднос, бочка); PIPELINE и ADDING ещё описывают TeamMask на всей одежде | — | — | [PIPELINE.md:17](../../art-pipeline/PIPELINE.md) |
| `CODEX-2D-PACKAGE-PROMPT.md` | предложено; шаблон пути B (чертежи для 3D), разрешает Codex коммитить | — | — | [CODEX-2D-PACKAGE-PROMPT.md:26-31,64-68](../../art-pipeline/CODEX-2D-PACKAGE-PROMPT.md) |
| Промпт DE-012 для Codex | прототип; сработал, лежит вне репо, ссылается на неверный путь HUD-AND-ICONS | результат принят лично 2026-10-05 | — | `C:/tmp/de-live/2026-10-04/codex-de012-prompt.md` |
| `IMAGEGEN-BRIEF-icons.md` (маски v2) | заменено | — | — | [IMAGEGEN-BRIEF-icons.md](../../unreal/contracts/hud/IMAGEGEN-BRIEF-icons.md) |
| Документ цикла «Codex/SYNTX → ревью → коммит → UE → кадр → приёмка» | нет | — | — | — |
| Журналы трат | измерено, неполно: основной (Tripo до 2026-09-30, баланс 23650; SYNTX до 2026-09-28, баланс 528) и ENV (Tripo −2310, баланс 21540 на 2026-10-01, не перенесён); 60 токенов SYNTX за музыку 2026-10-05 не записаны | — | — | [credits-ledger.json](../../art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json), [credits-ledger-env.json](../../art-pipeline/evidence/ENV-MAPS/credits-ledger-env.json) |
| Библиотека материалов UM v1 (22 CC0) и мастер `M_UM_Figure_v2.1` | технически импортировано | скачивание разрешено лично | у героев по умолчанию | [material-library/README.md](../../art-pipeline/material-library/README.md) |
| ImageGen-наборы: mvp-v1 (304 PNG), hero-quality-v1, env-v1, scratch-v1 Merlin | предложено; scratch-v1 заблокирован (IoU 0,42–0,59 при пороге 0,98) | env-v1: выбор концептов — лично (ENV-U8), это не приёмка | — | [env-v1/concepts/manifest.json](../../../art/imagegen/env-v1/concepts/manifest.json) |
| Art Hub в админке | измерено: 3D, клипы, видео, звук, кредиты; раздела 2D, HUD, VFX и карт нет | — | — | [ArtHubPage.tsx](../../../admin/src/pages/art-hub/ArtHubPage.tsx) |
| Сервисы: SYNTX (подписка PRO до 2026-10-28), UE MCP (порт 8123), исследование паков Fab | SYNTX PRO — только в брифе, первичного источника в репо нет: не проверено; UE MCP — рабочий инструмент; паки Fab — измерено | — | — | [00-VISUAL-BRIEF.md:274,281](00-VISUAL-BRIEF.md), [fab-free-assets-research-2026-10-01.md](../../art-pipeline/fab-free-assets-research-2026-10-01.md) |
| Права: SYNTX (пп. 9.1, 9.4, 3.3; п. 9.3 — запрет автоматизации) и провайдеры | измерено только для музыки; модели картинок и видео и image_gen Codex не исследованы | риск п. 9.3 принят лично 2026-10-05 | — | [RESEARCH-2026-10-05.md:119-137,222-227](../de-footage/task/runs/RESEARCH-2026-10-05.md) |

### Чего нет
- Действующего свода стиля: 03 не правился после 2026-09-28, правки лежат в `docs/art-pipeline/proposals/*.diff.md`.
- Правила о цветах зон настоящих карт (их задаёт иллюстрация) и об отношении HUD к двум задникам.
- Реестра 2D, HUD, VFX, экранов и курсоров. Реестр 3D — `asset-registry.json`; `03-asset-registry.csv` должен на него
  ссылаться, а не дублировать.
- Единого журнала трат и строки для генераций Codex.

### Расхождения
- На кадрах четыре разных языка: HUD — отладочный Slate, значки — плоская печать DE, фигуры — полуреалистичные
  статуэтки, поле — живописная карта, на Marmoreal вокруг неё 3D P5c. Документа, который сводит их, нет.
- Коллизии ID: ART-004 (эталон Medusa в бэклоге, HUD в `evidence/ART-004`), ART-011 (приёмка значков v3 и открытая
  задача «UI-семейства»), ART-012 (герои v2 в игре и поворот фигур).

## 10. Расхождения статусов

| Предмет | Что говорят источники (path:line) | Как на самом деле |
|---|---|---|
| 1. Кем приняты значки v3 | [01-decisions.md:186,563](../de-footage/task/01-decisions.md) и [APPROXIMATION.md:520](../de-footage/live-2026-10-04/APPROXIMATION.md): «принят пользователем 2026-10-03»; [AB-SHEET/README.md:21](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/README.md): «принятый набор»; [ART-011 README.md:7](../evidence/ART-011/hud-icons-v3-2026-10-03/README.md): «по делегированию (без личного просмотра)»; [hud-icons-v3/README.md:3](../../../art/imagegen/hud-icons-v3/README.md), [HUD-AND-ICONS.md:601](../../unreal/contracts/hud/HUD-AND-ICONS.md), [plan-status.json:2159](../../art-pipeline/plan-status.json), `ue-import-report.json:3`, `icon-motion.json:4`: «предложено» | Принято по делегированию 2026-10-03, в UE технически импортировано. Цитаты пользователя о приёмке v3 в репо нет. Строки 01-decisions:186/563 и APPROXIMATION:520 ошибочны |
| 2. DE-012 и AB-5…AB-8 | [01-decisions.md:670-680](../de-footage/task/01-decisions.md): приняты 2026-10-05, «по умолчанию включить»; [07-sprint-backlog.csv:13,24,29](../de-footage/task/07-sprint-backlog.csv), [CLOSEOUT:19,131-138](../de-footage/task/runs/CLOSEOUT-2026-10-04.md), [STYLE-v3.md:531](../../../art/imagegen/hud-icons-v3/STYLE-v3.md), [HUD-AND-ICONS.md:604](../../unreal/contracts/hud/HUD-AND-ICONS.md), [icon-motion.json:52](../../unreal/contracts/hud/icon-motion.json): «кандидаты», «ждёт ответа»; [S08TurnPortraitWidget.h:36,38](../../../unreal/Unmatched/Source/Unmatched/S08/S08TurnPortraitWidget.h): выключено | Принято лично. Код и документы отстают. Принятый арт стоит за opt-in флагами — нарушение AGENTS.md до прогона I |
| 3. Форма принятых глифов | [01-decisions.md:676-678](../de-footage/task/01-decisions.md): формы Codex; [draw_icons.py:1219,1225](../../../art/imagegen/hud-icons-v3/_tools/draw_icons.py): X 5,75 u, штамп 10,5 u; [AB-SHEET/04-icons-gallery.jpg](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/04-icons-gallery.jpg): формы движка | В UE лежат формы движка, не принятые. Нужен перенос в `draw_icons.py`, пересборка и переимпорт — новая арт-задача, не флаг |
| 4. Marmoreal: принят или заменён | [GD-058 marmoreal README.md:7](../evidence/GD-058/marmoreal-2026-10-01/README.md): «принято»; [S08ArtBoardProfiles.json:99](../../../unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json): «Marmoreal is artistically accepted»; [ENV-CONCEPT-PASTE.md:7,84](../../art-pipeline/ENV-CONCEPT-PASTE.md); [asset-registry.json:3057](../../art-pipeline/asset-registry.json); [AGENTS.md](../../../AGENTS.md): приёмка P5c «superseded» | Действует ENV-U16 (лично, 2026-10-04). Код, профиль, реестр, plan-status и ENV-CONCEPT-PASTE устарели |
| 5. Откуда разрыв ENV-U16 | [AGENTS.md](../../../AGENTS.md) и [бриф:254](00-VISUAL-BRIEF.md): «Since 0f2bdb9a»; [env-original-maps-decisions.md:198,208-210](../decisions/2026-09-30-env-original-maps-decisions.md): ответ п. 5 о вклейке, оркестратор применил её только к Sarpedon; кадр REAL-BOARDS 04:52: без флагов — серая доска в пустоте | Нарисованного Marmoreal по умолчанию не было никогда. `0f2bdb9a` только сделал P5c видом без флагов. Корень — трактовка ответа ENV-U15 п. 5 от 2026-10-01 |
| 6. Sarpedon | [asset-registry.json:2787,3201,3273](../../art-pipeline/asset-registry.json): «решение за пользователем»; [GD-058 sarpedon README.md:6](../evidence/GD-058/sarpedon-2026-10-03/README.md): делегирование; [env-original-maps-decisions.md:251](../decisions/2026-09-30-env-original-maps-decisions.md): «lit3d — путь 1» | Направление — лично; вид P10 — по делегированию, с FAIL. Блокеры реестра устарели |
| 7. Цвет P2 | [бриф:102](00-VISUAL-BRIEF.md): «принято» `#5A7F9F`; [03-art-direction.md:30](../03-art-direction.md) и [17:488](../17-art-production-spec.md): `#9FC2D8`; [hud-style-tokens.json:9](../../unreal/contracts/hud/hud-style-tokens.json): «ждёт подтверждения, Q-304 открыт»; [S08Team.h:48](../../../unreal/Unmatched/Source/Unmatched/S08/S08Team.h): `#5A7F9F` | В игре `#5A7F9F` по делегированию (D-2). Пользователь лично выбрал только место цвета |
| 8. Цвет команды на одежде | [PIPELINE.md:17](../../art-pipeline/PIPELINE.md): TeamMask на одежде; [lookdev-v2-decisions.md:10-12](../decisions/2026-09-29-lookdev-v2-decisions.md): «Акценты + кольцо» | Действуют акценты и кольцо. PIPELINE и ADDING-AN-ASSET устарели. В HUD цвет команды ещё на чипах и дисках портретов |
| 9. Фигуры v2 «принятый арт» | [AGENTS.md](../../../AGENTS.md), [18-animation-production-brief.md:21-22](../18-animation-production-brief.md): «принятый арт»; [plan-status.json:1225,1266,1285,1304](../../art-pipeline/plan-status.json): технически импортировано; [GD-058 final:86](../evidence/GD-058/final-2026-10-03/README.md): «Художественная приёмка пользователем — её нет» | Технически импортировано, по делегированию. «Accepted» в AGENTS.md — право быть видом по умолчанию |
| 10. Блокер GD-058 у ART-006…008 | [plan-status.json:1272,1291,1310](../../art-pipeline/plan-status.json): «не принят»; [GD-058 final:64](../evidence/GD-058/final-2026-10-03/README.md): снят по делегированию | Блокер снят. plan-status не обновлён с `e1aee681` |
| 11. U-4 против кода | [HUD-RULES.md:20-21,28-42](../../unreal/contracts/hud/HUD-RULES.md): UMG, без `GetDefaultFontStyle`, `-S09Markers`, StringTable; код: новые Slate-панели DE, 102 вызова, 0 `LOCTEXT` | Решение пользователя в коде не выполнено. HUD-RULES — «предложено», нарушается каждым прогоном |
| 12. Факты HUD-RULES §0 | [HUD-RULES.md:16,40](../../unreal/contracts/hud/HUD-RULES.md): «≈5,7 тыс. строк», «51 вызов `GetDefaultFontStyle`», «нет модуля UMG», «в Content нет WBP» (:16); маркеры :3821–3867 (:40) | Устарело: UMG подключён, 4 WBP в git, 102 вызова, маркеры :5663-5694, файл 8802 строки |
| 13. Слой над фигурами | [hud-umg-w4c-2026-09-29.md:3](../evidence/ART-004/hud-umg-w4c-2026-09-29.md): «Художественно не принято»; [S08FlowGameMode.cpp:7011-7012](../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp): «part of the accepted look: default on» | Технически импортировано, по умолчанию как часть вида GD-058 (делегирование). Личной приёмки нет |
| 14. Паритет 0 px у четырёх WBP | [бриф:113-116](00-VISUAL-BRIEF.md): у всех; [hud-umg-w4c:11,74](../evidence/ART-004/hud-umg-w4c-2026-09-29.md): плашка и иконка; [S08ArtHudUmgTests.cpp:612-655](../../../unreal/Unmatched/Source/Unmatched/S08/S08ArtHudUmgTests.cpp): паритет только у плашки | Паритет только у плашки (у иконки совпал bbox). Тег и урон сразу в UMG. `WBP_S08ArtIcon` по умолчанию не используется |
| 15. Число текстур значков | [бриф:168](00-VISUAL-BRIEF.md), [HUD-AND-ICONS.md:660](../../unreal/contracts/hud/HUD-AND-ICONS.md): 264; [HUD-AND-ICONS.md:618](../../unreal/contracts/hud/HUD-AND-ICONS.md): 336 | 336 (`git ls-files`): +72 кандидата DE-012 в `e3fd3450` |
| 16. Флаг жетона | [бриф:179](00-VISUAL-BRIEF.md), [HUD-AND-ICONS.md:660](../../unreal/contracts/hud/HUD-AND-ICONS.md): жетон за `-S08IconMotion`; [S08IconMotion.h:106-108](../../../unreal/Unmatched/Source/Unmatched/S08/S08IconMotion.h): v3 по умолчанию, флаг «changes nothing» | Жетон v3 по умолчанию, откат `-S08IconLegacy`. Открыт только qa010 на настоящей доске |
| 17. Актуальность упаковки | [CLOSEOUT:13-15](../de-footage/task/runs/CLOSEOUT-2026-10-04.md): «клиент актуален»; `BuildStamp.json` при записи описи: `2420dda7`, 19:01; `aca0e84b` (21:04), `1c3ce915` (21:20) | В 19:01–21:37 упаковка была без R-02 и R-03; кадры FINAL-PKG показывают поведение до них. С 21:37 штамп `9c8f92b7` (R-02…R-04 внутри), CLOSEOUT не обновлён |
| 18. Строки `S08FlowGameMode.cpp` | [бриф:107-109](00-VISUAL-BRIEF.md): 8763 строки, `RefreshHud` :5756 | Верно на `2ce939d2`. На HEAD — 8802 и :5795 |
| 19. Кольца V-17 «по умолчанию» | [01-decisions.md:32](../de-footage/task/01-decisions.md): «Подтверждено»; [07-sprint-backlog.csv:18](../de-footage/task/07-sprint-backlog.csv): done; [S08BoardActor.cpp:1910-1913](../../../unreal/Unmatched/Source/Unmatched/S08/S08BoardActor.cpp): только с флагом | По умолчанию только логика. Колец игрок без флага не видит |
| 20. Цвет pending | [03-ux-spec.md:212](../move-selection/03-ux-spec.md) и макеты v2: `#8A56C6`; [hud-style-tokens.json](../../unreal/contracts/hud/hud-style-tokens.json), [STYLE-v3.md:393](../../../art/imagegen/hud-icons-v3/STYLE-v3.md): `#0D7A89` | Действует бирюза v3 (по делегированию). 03 и макеты устарели. С бирюзовыми подложками два тона бирюзы будут значить разное |
| 21. Каналы материала CUE | [CUE-DISPATCHER.md:47](../../unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md), [cue-table.json:34,461,578,708](../../unreal/contracts/cue-dispatcher/cue-table.json): Rim (:34), FxFlash (:461, :578), Fade (:708); [S08HeroesV2.h:152-174](../../../unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h): CPD 12–14 | Истина — код. Контракт обновить в фазе 2 |
| 22. Клипы в трассе | [cue-table.json:568,698](../../unreal/contracts/cue-dispatcher/cue-table.json): `present`; трасса прогона C: `clip=missing` | Клипы играют. Трасса неверна: `AssetResolver` в игре не задан |
| 23. CUE-014 Medusa | [cue-table.json:750](../../unreal/contracts/cue-dispatcher/cue-table.json), [07-csv:15](../07-animation-vfx-audio.csv), [CUE-DISPATCHER.md:267](../../unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md): луч; [live README.md:497-512](../de-footage/live-2026-10-04/README.md): вихрь | Решения нет (бриф §8 п. 8). Контракт не обновлён после живого исследования |
| 24. Конфликт красного | [17-art-production-spec.md:1462,3097](../17-art-production-spec.md): «только red, green нет»; топология карт: red 8/12, green 28/16 | На обеих картах конфликтуют и урон, и лечение. AD-OPEN-34 описывает старую доску |
| 25. ART-010 | [PLAN-STATUS.md:105](../../art-pipeline/PLAN-STATUS.md): «Блокер: GD-058» | GD-058 закрыт по делегированию 2026-10-03. ART-010 не начат, блокера нет |
| 26. Пушки Sarpedon | [AGENTS.md](../../../AGENTS.md): «animated … cannons»; [S08ArtBoardProfiles.json:126](../../../unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json): `anims` — только `lantern-rail` | Пушки статичны |
| 27. Карты MVP | [06-asset-manifest.csv](../06-asset-manifest.csv): blocked, not_synced; [reused-cardart.json](../../../art/imagegen/mvp-v1/reused-cardart.json): 27/27 на месте; [бриф:191](00-VISUAL-BRIEF.md): `public/assets/decks` | Исходники есть локально и копией в `docs/figma/figma-ready`. «blocked» значит «не импортировано». В `public/assets/decks` их нет |
| 28. Скрап «вне git» | [бриф:191](00-VISUAL-BRIEF.md), `.gitignore:23` | Путь `scraped-data/` игнорируется, но копия скрапа в git с `0641577c`: 1794 файла, из них 1791 картинка (1575 карт, 216 картинок героев) и 3 служебных. Оригиналов карт досок в git нет (проверено по sha256) |
| 29. D-09 | [reused-cardart.json:3](../../../art/imagegen/mvp-v1/reused-cardart.json): «reuse original art; do not redraw with imagegen»; [00-vision-and-scope.md:103](../00-vision-and-scope.md): «существующие 2D-арты — иллюстрации, подача новая» | Источник — 00:103. Английская строка — пересказ агента 2026-09-26 |
| 30. Портреты | [бриф:194](00-VISUAL-BRIEF.md): решение пользователя 2026-10-03; [move-selection-v2/README.md:8](../../../art/imagegen/move-selection-v2/README.md): слова о макетах; [17:3101-3110](../17-art-production-spec.md): AD-OPEN-35 открыт | Прямого решения о HUD-портретах нет. Правило вывел агент |
| 31. Журнал трат | [бриф:279](00-VISUAL-BRIEF.md): один `credits-ledger.json`; ENV-журнал отдельно; [audio/01-inventory.md:160](../audio/01-inventory.md): 60 токенов | Журналов два, баланс Tripo не выше 21540, траты SYNTX после 2026-09-28 не записаны |
| 32. Право Codex коммитить | [CODEX-2D-PACKAGE-PROMPT.md:64-68](../../art-pipeline/CODEX-2D-PACKAGE-PROMPT.md): разрешено; запрос пользователя 2026-10-05: «Codex пишет только в свою папку и не коммитит» | Действует слово пользователя. Шаблон пути B нужно поправить |
| 33. Основа языка HUD | [бриф §4.1:295](00-VISUAL-BRIEF.md): «язык карт» navy/cream; [PLAN-STATUS.md:20](../../art-pipeline/PLAN-STATUS.md), [STYLE-v3.md:5](../../../art/imagegen/hud-icons-v3/STYLE-v3.md): волну «язык карт» пользователь отверг, основа — DE | Для значков основа — DE (лично, 2026-10-03), navy и cream — токены внутри неё. Для панелей вопрос открыт |
| 34. HD-04 контраст значка боя | [HUD-AND-ICONS.md:678](../../unreal/contracts/hud/HUD-AND-ICONS.md): открыт; [ART-011 README.md:63-71](../evidence/ART-011/hud-icons-v3-2026-10-03/README.md): qa010 pass 16,3 : 1 | Для вида по умолчанию закрыт жетоном v3, но замер на Cobble. Остаётся при `-S08IconLegacy` и у мирового спрайта mvp-v1 |
| 35. Трекер и кольцо в 02 | [02-ux-ui-spec.md:762,765](../02-ux-ui-spec.md): трекер v3, кольца по умолчанию нет | Устарело после AB-5 и AB-7 |
| 36. Дуги цели | [S08FighterActor.cpp:193](../../../unreal/Unmatched/Source/Unmatched/S08/S08FighterActor.cpp): красные; HI-11: «цель не красная» | Предложение HI-11 не применено и не решено |

**Конфликты, которые я разрешил сам (перепроверкой):**
1. **R-03.** Области VFX и DE видели `S08FlowGameMode.*` и `S09PresentationCatchup.*` незакоммиченными. Сейчас R-03
   в `1c3ce915` (21:20), журнал — `d964027c`. При записи описи в `unreal/` и `tools/` были незакоммичены
   `S08MoveHighlight.*`, `M_UM_MovePlate.uasset`, `ue_move_plate_material.py`. Ревью: это R-04 основного чата, он
   закоммичен в `9c8f92b7` (21:34). Сейчас в `unreal/` чужих незакоммиченных правок нет; в `tools/` — только
   неотслеживаемые `tools/art/art004_*.py`, `inspect_medusa_*.py`, `tools/audio/`.
2. **Упаковка.** При записи `BuildStamp.json` — `2420dda7`, 19:01, без R-02 и R-03. В 21:37 перештампован на
   `9c8f92b7`.
3. **Задник живых прогонов.** Области героев и значков сочли кадры прогона C и FINAL-PKG снятыми на 3D P5c. Трассы:
   у C demo и FINAL-PKG `concept-paste mode=on reason=flag-on` (сырая вклейка), у дуэли F `mode=off reason=default`
   (P5c). На P5c сняты только бенч-кадры C и A04, редакторные F/de029 и дуэль/vs-AI.
4. **Счётчики.** `RefreshHud` :5795, `BuildHudWidgets` :5537, 8802 строки; 336 текстур `T_IV3_*`; 102 вызова
   `GetDefaultFontStyle` (66 в основном файле и 36 в частичных); `conceptPaste.default "off"` у Marmoreal (:99).
5. **v3.** Строки 01-decisions:186 и :563 действительно говорят «принят пользователем». Верным считаю акт ART-011
   (делегирование): других источников с личной приёмкой нет.
6. **V-17.** Внутри кольца команды (радиус 18,9 uu против 22,0 uu кромки P1), как в коде и на кадрах; B/README ошибается.

## 11. Поправки к брифу

| § брифа | В брифе | На деле | Источник |
|---|---|---|---|
| §2 | SD-01…50 | SD-01…SD-56 | [02-spec-deltas.md:412-435,834-840](../de-footage/task/02-spec-deltas.md) |
| §2 | кадры `evidence/DE-FOOTAGE/2026-10-04/` — материалы изучения DE | это кадры нашего клиента; кадров DE в репо нет | [de-footage/README.md:10](../de-footage/README.md) |
| §2 | «Брать раскладку HUD» | сознательные отступления: неподвижная камера, колода боковой панелью, постоянная лента, видимый таймер, баннер 600 мс (в 2.2.1 баннера нет), бой ≈3,9 с; панели в коде колонкой слева внизу | [01-decisions.md](../de-footage/task/01-decisions.md) F-01…F-10 |
| §2, §5.3 | RESEARCH — права SYNTX и провайдеров | провайдеры исследованы только музыкальные | [RESEARCH-2026-10-05.md:119-188](../de-footage/task/runs/RESEARCH-2026-10-05.md) |
| §2 | «Не брать кляксу COMBAT!» | в коде кляксы нет, но STYLE-v3 правило 9 разрешает мазок кисти DE для баннеров ≥48 px | [STYLE-v3.md:48](../../../art/imagegen/hud-icons-v3/STYLE-v3.md) |
| §3.1 | D-DE-01: 1000 мс + 600 на строку | ещё пауза 300; удержание 1000 только при тексте эффекта; +600 вживую работает с R-02 | [01-decisions.md:275-299](../de-footage/task/01-decisions.md) |
| §3.1 | D-DE-01, 05, 06, 09, SD-44 — «Принято или действует по умолчанию» | все по делегированию; «Сыграть ещё» не сделано (GD-040) | [01-decisions.md:25-36](../de-footage/task/01-decisions.md) |
| §3.1 | DE-012: «В коде ещё не сделано — прогон I» | выборы AB записаны пересказом; формы Codex надо переносить в движок; прогон I не спланирован, владельца нет | [01-decisions.md:670-684](../de-footage/task/01-decisions.md) |
| §3.1 | палитра С-11 «принята» | P2 `#5A7F9F` — по делегированию, Q-304 открыт | [hud-style-tokens.json:9](../../unreal/contracts/hud/hud-style-tokens.json) |
| §3.1 | 8763 строки, `RefreshHud` :5756 | 8802 и :5795 на HEAD; плюс тик 0,25 с, 81 вызов, постоянные слоты в `BuildHudWidgets` | `S08FlowGameMode.cpp` |
| §3.1 | рука: `B%d *NEW* [BOOST] [ATK] [DEF] [SCH] [PICK]` | ещё `[DROP]`, `[PICK%d]`, `[hidden]` и строка-подсказка клавиш | `S08FlowGameMode.cpp:5899-5949` |
| §3.1 | отладка: seq, phase, MATCH INTERRUPTED, RECONNECTING | MATCH INTERRUPTED — экран ABORTED, RECONNECTING — плашка GD-037. Главная отладка — 13 неоновых маркеров, 4-цветная полоса, «deck=24~», эхо команд | `:5663-5694`, `:5832-5885` |
| §3.1 | BOOT → LOGIN → LOBBY → ROOM — серый поток GD-029/030/031 | один виджет legacy root с логом; выбора героя и доски нет; лобби — отдельная панель GD-036; GD-030 — серая доска, не экран | `:5210-5388`, [14-sprint-backlog.csv:30-33](../14-sprint-backlog.csv) |
| §3.1 | 4 WBP «паритет 0 px» | паритет только у плашки; `WBP_S08ArtIcon` только при откате | [S08ArtHudUmgTests.cpp:612-655](../../../unreal/Unmatched/Source/Unmatched/S08/S08ArtHudUmgTests.cpp) |
| §3.1 | токены «предложено» или «измерено», дубль в `S08ArtHudStyle.h` | `font.card` — технически импортировано; дубли минимум в 8 файлах; `#F2C14E` в коде есть, в JSON нет | [hud-style-tokens.json:48](../../unreal/contracts/hud/hud-style-tokens.json) |
| §3.1 | DE-015 и DE-017: кольца-кандидаты | кольца — только DE-017; DE-015 — ввод в начале хода, удаление «Паса», конец хода | [07-sprint-backlog.csv:16,18](../de-footage/task/07-sprint-backlog.csv) |
| §3.1 | подложки за `-S08MovePlates` | тем же флагом закрыты V-17, V-11/V-12 и V-14/V-15; по умолчанию — старое кольцо P4 | [S08BoardActor.cpp:1764,1910-1913](../../../unreal/Unmatched/Source/Unmatched/S08/S08BoardActor.cpp) |
| §3.1 | макеты v2 в `art/imagegen/move-selection-v2/` | там README и manifest; PNG в `scraped-data/derived/move-selection/` (вне git); макеты устарели | [move-selection-v2/README.md:24-31](../../../art/imagegen/move-selection-v2/README.md) |
| §3.1 | HD-02, HD-04, HD-08 | HD-02 на настоящих досках — плашка оторвана от владельца; HD-04 закрыт жетоном v3 (замер на Cobble); HD-08 стал хуже — у всех гарпий «1/1» | §1, §10 стр. 34 |
| §3.2 | 264 текстуры; 23 значка и маска | 336 текстур; 32 мастера (23 + маска + 3 варианта + 5 кандидатов DE-012) | `git ls-files` |
| §3.2 | живой бой жетона за `-S08IconMotion` | жетон v3 по умолчанию, флаг ничего не меняет; живой qa010 только на Cobble | [S08IconMotion.h:106-108](../../../unreal/Unmatched/Source/Unmatched/S08/S08IconMotion.h) |
| §3.2 | mvp-v1 — 99 PNG | в mvp-v1 304 PNG; 99 — подмножество UI и маркеров | [mvp-v1/README.md:11-16](../../../art/imagegen/mvp-v1/README.md) |
| §3.3 | `public/assets/decks` — 18 колод | веб-герои; колод Medusa и King Arthur там нет | `ls public/assets/decks` |
| §3.3 | скрап — вне git; D-09 «do not redraw» | копия скрапа в git (`docs/figma/figma-ready`); D-09 — пересказ агента | §4 |
| §3.3 | портреты — решение пользователя; WebP «затрагивает бэкенд» | слова пользователя о макетах; офлайн-конвертация WebP→PNG в пак по INT-014 и INT-016 бэкенд не трогает | [08-integration-decisions.md:152-164](../08-integration-decisions.md) |
| §3.4 | ART-004…008, 012…016 `in_progress` | ART-016 и ART-017 — done; ART-005 — участок Cobble, не герой | [plan-status.json:1238-1541](../../art-pipeline/plan-status.json) |
| §3.4 | хвост «маска акцента Arthur» | маска закрыта (ART-016); остаётся кант P1 сзади | [king-arthur-lookdev-v2.md:881](../../art-pipeline/king-arthur-lookdev-v2.md) |
| §3.4 | «Нет: бега, ходьбы, схем, способностей, победы, защиты» | это граница MVP по D-11, а не пропуск; расширение — только словом пользователя | [00-vision-and-scope.md:105](../00-vision-and-scope.md) |
| §3.4, §8 п. 6 | ART-012 — поворот фигур | в бэклоге ART-012 — «герои v2 в игре»; поворот живёт под тем же ID | [14-sprint-backlog.csv](../14-sprint-backlog.csv) |
| §3.5 | каналы `Rim`, `FxFlash`, `Fade`; `M_UM_MovePlate` — сделано | у v2 работают CPD 12–14; Rim и FxFlash не управляются; плиты за флагом | §6 |
| §3.6, §4.6 | «С `0f2bdb9a`»; нужно de-lit альбедо | с `0f2bdb9a` P5c стал видом без флагов, но корень — 2026-10-01; de-lit альбедо нужно только для lit3d | §10 стр. 5 |
| §3.6 | Sarpedon lit3d принят по делегированию | направление выбрал пользователь 2026-10-04; кроме SSIM FAIL ещё G2, G6; живой бой на lit3d уже есть | [GD-058 sarpedon README.md:57-71](../evidence/GD-058/sarpedon-2026-10-03/README.md) |
| §3.6 | «Почти весь Content вне git» | в git 735 файлов (UI, материалы, герои, маркеры); окружение — 0; плиты Sarpedon — только в `C:/tmp` | `git ls-files unreal/Unmatched/Content` |
| §3.7 | шаблон Codex — `CODEX-2D-PACKAGE-PROMPT.md`; DE-012 — первый полный цикл | шаблон пути B (3D-чертежи), разрешает коммиты; Codex использовался и раньше (mvp-v1, hero-quality-v1, env-v1, scratch-v1); DE-012 — первый пакет в своей папке с личной приёмкой | §9 |
| §3.7 | журнал трат — `credits-ledger.json`; Art Hub — 3D, клипы, материалы, звук | журналов два; Art Hub шире, но 2D нет | §9 |
| §4.1 | основа — «язык карт» и ДНК v3 | для значков основа — DE (лично, 2026-10-03) | [PLAN-STATUS.md:20](../../art-pipeline/PLAN-STATUS.md) |
| §4.3 | кольцо хода — элемент поля | на поле его нет (и у DE нет); кольцо хода — у портрета | [01-decisions.md:670](../de-footage/task/01-decisions.md) |
| §5.4 | цитата «ты не провел полноценного ревью» | встречается только в брифе; в других документах пересказ | [HUD-AND-ICONS.md:587](../../unreal/contracts/hud/HUD-AND-ICONS.md) |
| §6 | не трогать `S08FlowGameMode.*`, `S09CombatStage.*`, `cue_contract.py` | они закоммичены. `S08MoveHighlight.*`, `M_UM_MovePlate.uasset`, `ue_move_plate_material.py` тоже закоммичены (`9c8f92b7`, 21:34). Чужих незакоммиченных правок в `unreal/` на ≈21:40 нет; правило «не трогать чужое» действует для будущих | `git status` 2026-10-05 ≈21:40 |
| §6 против §8 п. 14 | UE — только по прямому разрешению; разрешение дано | бриф противоречит сам себе; действует запрос пользователя 2026-10-05 (UE в worktree). AGENTS.md и журнал ENV это не отражают | [AGENTS.md](../../../AGENTS.md) |

## 12. Просмотренные кадры

Пути из `docs/game-design/evidence/` даны относительными ссылками. `scraped-data` и `C:/tmp` — вне git.

**HUD и экраны** (живые упакованные прогоны 2026-10-05, Marmoreal со сырой вклейкой, если не сказано иное)
- [FINAL-PKG …/host/s09-turn-banner.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/host/s09-turn-banner.jpg) — 6 фигур v2; плашка «YOUR TURN»; отладка seq/phase; карты прошлого боя у краёв; рука обрезана; «AFTER COMBAT» + «YOUR TURN» + «Syncing…».
- [FINAL-PKG …/joiner/s09-combat-defense-open.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/joiner/s09-combat-defense-open.jpg) — красная панель окна защиты, `[shield]` текстом; карты прошлого боя под новым окном.
- [FINAL-PKG …/host/s09-result-screen.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/host/s09-result-screen.jpg), [joiner](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/joiner/s09-result-screen.jpg) — модал VICTORY/DEFEAT, 4-цветная полоса гейта, монограммы, грейда нет.
- [FINAL-PKG …/host/s09-result-board.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/host/s09-result-board.jpg) — итоговая доска чистая; сердце павшего без креста.
- [FINAL-PKG …/joiner/s09-deck-own.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/joiner/s09-deck-own.jpg), [s09-damage-number.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/joiner/s09-damage-number.jpg) — панель колоды ≈500 px закрывает правый край поля и Medusa.
- [FINAL-PKG …/host/s09-card-slot-own.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/host/s09-card-slot-own.jpg) — PENDING CHOICE; слот SCHEME текстом; рука за кадром.
- [FINAL-PKG …/joiner/s09-combat-resolve-window.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/joiner/s09-combat-resolve-window.jpg) — зелёная полоса, RESOLVE COMBAT (R); тост поверх ленты.
- [FINAL-PKG …/joiner/s09-damage-combat.jpg](../evidence/DE-FOOTAGE/2026-10-04/FINAL-PKG/marmoreal/combat-20261005-190326/joiner/s09-damage-combat.jpg) — «A2 vs D0 / Medusa WINS»; Arthur целиком красный; «NO DEFENSE» текстовой X; жетон v3.
- [F/accept …/s09-hand-limit-hint.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/accept/demo/marmoreal/combat-20261005-173556/host/s09-hand-limit-hint.jpg) — высокая панель руки закрывает нижний ряд клеток; метка исхода висит в следующем черновике.
- [F/accept …/s09-combat-resolve-revealed.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/accept/demo/marmoreal/combat-20261005-173556/joiner/s09-combat-resolve-revealed.jpg) — полосы `#7CFC00` и `#FF40B0` прямо в HUD игрока.
- [F/accept …/host-maneuver-draft.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/accept/phase2/sarpedon/run-20261005-173056/host-maneuver-draft.jpg) — Sarpedon lit3d; полоса `#FF00FF`; тост «AUTO maneuver: f-0-hero -> S10».
- [F/accept …/s09-card-slot-opp.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/accept/demo/sarpedon/combat-20261005-173408/host/s09-card-slot-opp.jpg) — Sarpedon; «COMBAT RESULT» и «YOUR TURN» в одной панели; лента DISCARDED.
- [F/accept …/s09-card-slot-own.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/accept/demo/marmoreal/combat-20261005-173307/host/s09-card-slot-own.jpg), [s09-combat-result.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/accept/demo/marmoreal/combat-20261005-173307/host/s09-combat-result.jpg) — слот SCHEME синей лентой; карты боя текстом.
- [F/live …/joiner/s09-combat-resolve-revealed.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/demo/marmoreal/combat-20261005-164124/joiner/s09-combat-resolve-revealed.jpg), [host/s09-result-screen.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/demo/marmoreal/combat-20261005-164124/host/s09-result-screen.jpg), [host/s09-turn-banner.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/demo/marmoreal/combat-20261005-164124/host/s09-turn-banner.jpg), [joiner/s09-deck-own.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/demo/marmoreal/combat-20261005-164124/joiner/s09-deck-own.jpg) — плашки боя отстают от панели; модал без «Сыграть ещё»; баннер при висящих плашках; колода списком.
- [F/live/duel …/host/s09-lobby-return.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/duel/duel-20261005-164841/host/s09-lobby-return.jpg) — лобби: чёрный экран, маленькая панель слева вверху, пустые рамки других панелей.
- [F/live/duel …/host/s09-result-board.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/duel/duel-20261005-164841/host/s09-result-board.jpg) — дуэль без флага: Marmoreal на 3D P5c.
- [F/live/defects/duel-720p-result-pkg3.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/defects/duel-720p-result-pkg3.jpg), [duel-720p-stripe-crop-pkg3.jpg](../evidence/DE-FOOTAGE/2026-10-04/F/live/defects/duel-720p-stripe-crop-pkg3.jpg) — 720p, полоса гейта в модале; диск KA почти не виден.
- [F/de029 results-victory](../evidence/DE-FOOTAGE/2026-10-04/F/de029/de029-results-victory-marmoreal.jpg), [board-defeat](../evidence/DE-FOOTAGE/2026-10-04/F/de029/de029-board-defeat-marmoreal.jpg) — бенч 720p на 3D P5c; строка клавиш ≈11 px; мировые подписи «Harpies 3».
- [F/de030 deck-opp](../evidence/DE-FOOTAGE/2026-10-04/F/de030/de030-deck-opp-marmoreal.jpg), [deck-own](../evidence/DE-FOOTAGE/2026-10-04/F/de030/de030-deck-own-marmoreal.jpg) — рубашки соперника — пустые красные квадраты; своя Medusa «waiting» при «YOUR TURN».
- [G/phase2-ui …/phase2-board-joiner-1920x1080.jpg](../evidence/DE-FOOTAGE/2026-10-04/G/phase2-ui/marmoreal/run-20261005-182703/phase2-board-joiner-1920x1080.jpg) — ход соперника: «seq=1 - waiting for the authoritative stream».
- [G/phase2/drafts marmoreal](../evidence/DE-FOOTAGE/2026-10-04/G/phase2/drafts/phase2-draft-marmoreal.jpg), [sarpedon](../evidence/DE-FOOTAGE/2026-10-04/G/phase2/drafts/phase2-draft-sarpedon.jpg) — полоса magenta; плашка Medusa далеко от фигуры; жёлтые кольца на жёлтых клетках; теги «1/1» ×3.
- [G …/s09-hand-limit-hint.jpg](../evidence/DE-FOOTAGE/2026-10-04/G/demo/sarpedon/combat-20261005-181804/host/s09-hand-limit-hint.jpg), [s09-opponent-move.jpg](../evidence/DE-FOOTAGE/2026-10-04/G/demo/sarpedon/combat-20261005-181804/host/s09-opponent-move.jpg) — тост поверх тоста лимита; панель колоды закрывает треть поля.
- [E/fix/marmoreal/joiner-s09-turn-banner.jpg](../evidence/DE-FOOTAGE/2026-10-04/E/fix/marmoreal/joiner-s09-turn-banner.jpg) — баннер Roboto Condensed; тост в полосе ленты.
- [E/fix/sarpedon-chain/joiner-s09-card-slot-opp.jpg](../evidence/DE-FOOTAGE/2026-10-04/E/fix/sarpedon-chain/joiner-s09-card-slot-opp.jpg) — слот схемы соперника текстом.
- [E/live/defect-portraits-over-hand.jpg](../evidence/DE-FOOTAGE/2026-10-04/E/live/defect-portraits-over-hand.jpg) — старый дефект: портреты на руке (исправлено `0fce04ae`).
- [REAL-BOARDS …/host/s09-maneuver-draft-open.png](../evidence/REAL-BOARDS/2026-10-04/hud/run-20261004-045507/host/s09-maneuver-draft-open.png), [joiner/s09-discard-open.png](../evidence/REAL-BOARDS/2026-10-04/hud/run-20261004-045507/joiner/s09-discard-open.png) — серый стенд `-S08GreyBoard`: доказательство логики, не арта.
- [S10 …/s10-aborted-screen.png](../evidence/S10/run/vsai-abort-20260927-190951/human/s10-aborted-screen.png) — единственный кадр ABORTED, сетка 20×20 (не годится).
- [ART-TUNER …/06-live-duel-tint-set-and-f10-operator-panel.jpg](../evidence/ART-TUNER/followup-2026-10-03/06-live-duel-tint-set-and-f10-operator-panel.jpg) — F10 legacy root: так же выглядят LOGIN и ROOM.

**Слой над фигурами и контракты**
- [ART-004 compare-1p6 joiner](../evidence/ART-004/hud-umg-w4c-2026-09-29/compare-1p6/run-20260929-103903/phase2-board-joiner-1920x1080.png), [compare-5x host](../evidence/ART-004/hud-umg-w4c-2026-09-29/compare-5x/run-20260929-101212/phase2-board-host-1920x1080.png) — W4-C на Cobble; плашка UMG; иконка mvp-v1 с низким контрастом.
- [ART-DEFAULT host](../evidence/ART-DEFAULT/2026-10-04/phase2-board-host-1920x1080.png), [joiner](../evidence/ART-DEFAULT/2026-10-04/phase2-board-joiner-1920x1080.png), [crop 2x](../evidence/ART-DEFAULT/2026-10-04/host-figures-crop-2x.png) — Marmoreal на 3D P5c; шесть v2; теги без имён; гарпии неразличимы.
- [REAL-BOARDS phase2 host](../evidence/REAL-BOARDS/2026-10-04/phase2/run-20261004-045238/phase2-board-host-1920x1080.png) — до `0f2bdb9a`: серые болванки, полные теги «Harpies 1/2/3».
- [GD-058 interim Cobble K1](../evidence/GD-058/interim-2026-09-30/fix-w7/packaged/k1/cobble-5x6/run-20260930-230721/phase2-board-host-1920x1080.png) — HD-02: плашка целиком закрывает Medusa.
- [ART-011 live-token](../evidence/ART-011/hud-icons-v3-2026-10-03/live-token/run-20261003-191204/phase2-board-host-1920x1080.png) — жетон v3 32 px на Cobble с болванками.
- [AB-SHEET 03 marmoreal](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/03-turnhud-marmoreal.jpg), [03 sarpedon](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/03-turnhud-sarpedon.jpg), [warm t400 K1](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/frames/marmoreal-hud-warm-t400-K1.jpg) — варианты кольца; тлеющий обод на тёмной панели почти не виден.
- [D/plate-follow-before-after.jpg](../evidence/DE-FOOTAGE/2026-10-04/D/plate-follow-before-after.jpg) — тег следует за фигурой; лежит на связи клеток (HD-07).
- [E/de023/de023-portrait-sheet.png](../evidence/DE-FOOTAGE/2026-10-04/E/de023/de023-portrait-sheet.png) — лист портретов 0–2000 мс; кольцо только в рядах с флагом.

**Поле**
- [de017 marmoreal K1](../evidence/MOVE-SEL/de017-editor-2026-10-04/marmoreal-0-candidates-K1.jpg), [crop](../evidence/MOVE-SEL/de017-editor-2026-10-04/marmoreal-0-candidates-crop.jpg), [sarpedon K1](../evidence/MOVE-SEL/de017-editor-2026-10-04/sarpedon-0-candidates-K1.jpg), [crop-after](../evidence/MOVE-SEL/de017-editor-2026-10-04/sarpedon-0-candidates-crop-after.jpg) — V-17 внутри кольца P1, на K1 почти не видно.
- [ms-t08 marmoreal-1](../evidence/MOVE-SEL/ms-t08-editor-2026-10-04/marmoreal-1-select-boost-K2x1.6.jpg), [marmoreal-2](../evidence/MOVE-SEL/ms-t08-editor-2026-10-04/marmoreal-2-draft-conflict-needboost-K1.jpg), [sarpedon-2](../evidence/MOVE-SEL/ms-t08-editor-2026-10-04/sarpedon-2-draft-conflict-needboost-K2x1.6.jpg) — V-01 хорошо на ночной карте; V-04b на песке держится кромкой; «!» V-09 не виден.
- [ms-t12 marmoreal](../evidence/MOVE-SEL/ms-t12-editor-2026-10-05/marmoreal-3-pending-move-crop.jpg), [sarpedon](../evidence/MOVE-SEL/ms-t12-editor-2026-10-05/sarpedon-3-pending-move-enemy-crop.jpg) — пунктир V-11 слабый на жёлтом и коричневом.
- [m1-live](../evidence/MOVE-SEL/m1-live-2026-10-04/run-20261004-035600/phase2-board-host-1920x1080.png), [ms-t-15](../evidence/MOVE-SEL/ms-t-15-2026-10-04/run-20261004-054311/phase2-board-joiner-1920x1080.png) — до правила v2: болванки, окружения нет.
- Макеты (вне git): [MS-C-01a](../../../scraped-data/derived/move-selection/MS-C-01a.png), [01b](../../../scraped-data/derived/move-selection/MS-C-01b.png), [01a-gray](../../../scraped-data/derived/move-selection/MS-C-01a-gray.png), [02a](../../../scraped-data/derived/move-selection/MS-C-02a.png), [03b](../../../scraped-data/derived/move-selection/MS-C-03b.png), [05](../../../scraped-data/derived/move-selection/MS-C-05.png), [06](../../../scraped-data/derived/move-selection/MS-C-06.png), [08](../../../scraped-data/derived/move-selection/MS-C-08.png), [09](../../../scraped-data/derived/move-selection/MS-C-09.png) — 17 состояний без V-17; бирюза заметнее золота; V-14 едва видна; глифы v2, Bahnschrift.
- [AB-SHEET 01 marmoreal](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/01-move-marmoreal.jpg), [01 sarpedon](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/01-move-sarpedon.jpg) — варианты позы почти не различаются; подскок поднимает подставку и кольцо.
- [B draft marmoreal](../evidence/DE-FOOTAGE/2026-10-04/B/demo/marmoreal/run-20261005-040857/draft-marmoreal-host-1920x1080.png), [B draft sarpedon](../evidence/DE-FOOTAGE/2026-10-04/B/demo/sarpedon/run-20261005-041533/draft-sarpedon-host-1920x1080.png), [candidates crop](../evidence/DE-FOOTAGE/2026-10-04/B/marmoreal-draft-candidates-crop.jpg) — V-17 неотличимы от колец команд; панель черновика с `#FF00FF`.
- [B sarpedon tiers crop](../evidence/DE-FOOTAGE/2026-10-04/B/sarpedon-draft-tiers-crop.jpg), [B bench plates2](../evidence/DE-FOOTAGE/2026-10-04/B/bench/sarpedon-plates2-K1-draft.jpg) — на жёлтом песке кольцо держится кромкой; заливка на зелени сереет.
- [D marmoreal joiner](../evidence/DE-FOOTAGE/2026-10-04/D/demo/marmoreal/combat-20261005-104451/joiner/s09-opponent-last-move.jpg), [D sarpedon host](../evidence/DE-FOOTAGE/2026-10-04/D/demo/sarpedon/combat-20261005-104620/host/s09-opponent-last-move.jpg) — V-14 почти не найти; тост накрывает ленту MS-LOG.

**Значки**
- [sheet-masters](../../../art/imagegen/hud-icons-v3/sheets/sheet-masters.png), [sheet-sizes](../../../art/imagegen/hud-icons-v3/sheets/sheet-sizes.png), [sheet-context-panel](../../../art/imagegen/hud-icons-v3/sheets/sheet-context-panel.png), [compare-v2-v3](../../../art/imagegen/hud-icons-v3/sheets/compare-v2-v3.png) — v3 чистый на 24–32 px; 16 px разваливается; на креме «пусто» читается как залитое.
- [v2 compare-gray-24px-x4](../../../art/imagegen/hud-icons-v2/compare-gray-24px-x4.png), [v2 state-immobilized](../../../art/imagegen/hud-icons-v2/state-immobilized.png), [v2 action-maneuver](../../../art/imagegen/hud-icons-v2/action-maneuver.png), [v3 action-maneuver](../../../art/imagegen/hud-icons-v3/masters/action-maneuver.png) — v2: кривые стыки, капли; v3: чистый вектор.
- [de012 sheet-candidates](../../../art/imagegen/hud-icons-v3/sheets/de012/sheet-candidates.png) — формы движка: крупный X ломает сердце, слот — мишень.
- Codex: [overview color](../../../art/imagegen/hud-icons-de012-codex/comparison/overview-1024-color.png), [gray](../../../art/imagegen/hud-icons-de012-codex/comparison/overview-1024-gray.png), [16 color](../../../art/imagegen/hud-icons-de012-codex/comparison/compare-16px-color.png), [16 gray](../../../art/imagegen/hud-icons-de012-codex/comparison/compare-16px-gray.png), [24 color](../../../art/imagegen/hud-icons-de012-codex/comparison/compare-24px-color.png), [24 gray](../../../art/imagegen/hud-icons-de012-codex/comparison/compare-24px-gray.png), [32 gray](../../../art/imagegen/hud-icons-de012-codex/comparison/compare-32px-gray.png), [state-reference](../../../art/imagegen/hud-icons-de012-codex/comparison/state-reference.png), [slot-1024](../../../art/imagegen/hud-icons-de012-codex/comparison/slot-1024-color.png), [hp-fallen 1024](../../../art/imagegen/hud-icons-de012-codex/vector-codex/1024/resource-hp-fallen.png) — формы Codex лучше на 24–32 px; на 16 px X на сердце пропадает.
- [ART-011 UE-галерея](../evidence/ART-011/hud-icons-v3-2026-10-03/ue-gallery/normal-32/icon-gallery-normal-00500.png), [compare](../evidence/ART-011/hud-icons-v3-2026-10-03/ue-gallery/normal-32/compare.png), [ICON-MOTION de012 compare](../evidence/ICON-MOTION/2026-10-04-de012/normal-32/compare.png) — UE совпадает с эталоном; кандидаты в форме движка.
- [AB-SHEET 04-icons-gallery](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/04-icons-gallery.jpg), [00-ab-sheet](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/00-ab-sheet.jpg) — лист показывал формы движка, не формы Codex.
- [mvp-v1 ui-action-maneuver-normal](../../../art/imagegen/mvp-v1/ui/actions/ui-action-maneuver-normal.png) — пергамент и бронза, не язык карт.

**Карты и портреты** (исходники вне git)
- EN-карты: [Gaze of Stone](../../../scraped-data/images/decks/dDKLFFrQCU3LSvzUl9bp4.png), [Excalibur](../../../scraped-data/images/decks/MUg5EqgEkpVO7BlZzLg2b.png), [Winged Frenzy](../../../scraped-data/images/decks/tMn-Qj6hEIQKIx9jQyklL.png), [Bewilderment](../../../scraped-data/images/decks/_VbQcT4mEpsnZhYTRfC_f.png) — язык карт: кремовая рамка, navy-лента, таб типа, BOOST, меандр; мелкий текст на 250 px.
- RU-карты: [Мимолётный взгляд](../../../scraped-data/images/decks/VLFvvPFkApvUG5VJWSL0j.webp), [Экскалибур](../../../scraped-data/images/decks/ZhF2FHoCOcQYZX7GRtSWQ.webp), [Благородная жертва](../../../scraped-data/images/decks/hbJVZdN2fflqWfr-qKidR.webp) — мыло WebP; подпись внизу по-английски.
- Аватары: [Medusa](../../../scraped-data/images/heroes/avatars/bI206lUtJUQru-FOD8A74.webp), [Arthur](../../../scraped-data/images/heroes/avatars/dgwIAej9v-Omrn0sSVs5i.webp), [Harpies](../../../scraped-data/images/heroes/sidekicks/G42WIKYZ1cmwACVwMggzM.webp), [Merlin](../../../scraped-data/images/heroes/sidekicks/4Rl9Oq9N82zhatbTShnXn.webp) — 402², 800², помощники 128².
- Рубашки: [Medusa | Harpies](../../../scraped-data/images/heroes/card-covers/ROSMO3sRi6Jh1o7S_riGI.png), [King Arthur | Merlin](../../../scraped-data/images/heroes/card-covers/WWzu16BEFGsEdu5NsMbMI.png) — 768×1051, логотип UNMATCHED.
- Карты досок: [marmoreal.png](../../../scraped-data/images/maps/marmoreal.png), [sarpedon.png](../../../scraped-data/images/maps/sarpedon.png) — 1337×866, логотип внизу слева; насыщенная красная зона на палубе.
- ImageGen mvp-v1: [портрет Medusa](../../../art/imagegen/mvp-v1/ui/portraits/ui-portrait-medusa.png), [рамка атаки](../../../art/imagegen/mvp-v1/ui/cards/ui-card-frame-attack-normal.png), [рубашка](../../../art/imagegen/mvp-v1/ui/cards/ui-card-back-normal.png) — камень и бронза, чужой стиль; красная бахрома альфы.
- [public/assets/ui/hud/hidden-card-back.png](../../../public/assets/ui/hud/hidden-card-back.png) — веб-заглушка рубашки.

**Герои и анимации**
- [AB-SHEET 02-dissolve marmoreal](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/02-dissolve-marmoreal.jpg), [sarpedon](../evidence/DE-FOOTAGE/2026-10-04/AB-SHEET/02-dissolve-sarpedon.jpg) — fade прозрачнеет; «пепел» прогорает с золотым фронтом.
- [C marmoreal host s09-damage-combat](../evidence/DE-FOOTAGE/2026-10-04/C/demo/marmoreal/combat-20261005-073908/host/s09-damage-combat.jpg), [s09-combat-result](../evidence/DE-FOOTAGE/2026-10-04/C/demo/marmoreal/combat-20261005-073908/host/s09-combat-result.jpg), [s09-result-screen](../evidence/DE-FOOTAGE/2026-10-04/C/demo/marmoreal/combat-20261005-073908/host/s09-result-screen.jpg), [joiner s09-damage-number](../evidence/DE-FOOTAGE/2026-10-04/C/demo/marmoreal/combat-20261005-073908/joiner/s09-damage-number.jpg) — сырая вклейка (по трассе); заливка всей фигуры; «−N» у тега; экран результата отладочный.
- [C sarpedon host s09-combat-result](../evidence/DE-FOOTAGE/2026-10-04/C/demo/sarpedon/combat-20261005-074029/host/s09-combat-result.jpg), [joiner s09-damage-combat](../evidence/DE-FOOTAGE/2026-10-04/C/demo/sarpedon/combat-20261005-074029/joiner/s09-damage-combat.jpg), [joiner s09-combat-resolve-revealed](../evidence/DE-FOOTAGE/2026-10-04/C/demo/sarpedon/combat-20261005-074029/joiner/s09-combat-resolve-revealed.jpg) — заливка Medusa рядом с красными зонами; вспышки направления нет.
- [de019 marmoreal-ash-K1](../evidence/DE-FOOTAGE/de019-editor-2026-10-05/marmoreal-ash-K1.jpg) — «пепел» на K1 заметен; подписи перекрывают фигуры.
- [ART-004 t43 кадр жалобы](../evidence/ART-004/t43-20261004-055419/demo/run-20261004-060344/phase2-board-host-1920x1080.png) — серые блок-ауты вместо готовых моделей (2026-10-04).
- [art016 harpies before-after](../../art-pipeline/evidence/art016-harpy-r3.3-2026-10-04/marmoreal-k2x2p5-harpies-before-after.jpg) — маховые почти чёрные; одна гарпия спиной к камере.
- [Harpy-H2Anim-ue-sheet](../../../art/pipeline-candidates/ASSET-HARPY-001/20260929-h2anim/preview/Harpy-H2Anim-ue-sheet.jpg), [Arthur clips](../../../art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260930-h2ld-5cb1-ue/game/s08v2-5cb1-clips-kingarthur.jpg) — Idle почти статичен; Lunge читается; HitReact слабый; смерть — поклон без колен.
- [ART-018 k2-medusa-zooms](../evidence/ART-018/long-k2-2026-09-30/k2-medusa-zooms-native.jpg) — лицо читается только с 3,5×.
- [ART-005 cobble contact sheet](../evidence/ART-005/art3-live-3boards-r3-2026-09-30/analysis/cobble-5x6/contact-k1-k3-color-gray-deuteranopia.jpg) — гейты читаемости сняты на синтетической доске.
- hero-quality-v1: [Arthur](../../../art/imagegen/hero-quality-v1/king-arthur/king-arthur-front.png), [Harpy](../../../art/imagegen/hero-quality-v1/harpy/harpy-front.png), [Medusa reference](../../../art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png) — полуреалистичные статуэтки; у гарпии золотая подставка.
- [Codex DE-011 ash-a-material](../../../art/imagegen/hud-icons-de012-codex/de011/ash-a-material.png) — Arthur на коленях, hex команд экранные; поза не наша.

**VFX**
- [de010 after-final-hit1](../../art-pipeline/evidence/de010-2026-10-04/after-final-hit1.jpg) — заливка: четыре фигуры целиком красно-оранжевые, без вспышки и контура.
- [de011 after-ash-p35](../../art-pipeline/evidence/de011-2026-10-04/after-ash-p35.jpg) — «пепел» пятнами, края цвета команды.
- [p9 details-p8-p9-c0](../evidence/ENV-MAPS/p9-fixes-hero-light-2026-10-02/details-p8-p9-c0.jpg), [p9 sarpedon K1](../evidence/ENV-MAPS/p9-fixes-hero-light-2026-10-02/sarpedon/bench-K1-1920x1080.png) — водопад — тёмная вуаль; огонь слоистый, но с дизером; Arthur красный уже без заливки.
- [mvp-v1 vfx-combat-impact](../../../art/imagegen/mvp-v1/vfx/vfx-combat-impact.png), [vfx-death-ash-flipbook](../../../art/imagegen/mvp-v1/vfx/vfx-death-ash-flipbook-4x4.png) — фэнтези-глянец; рваная кайма альфы.

**Окружение**
- [P10 sarpedon K1](../evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png), [K2×1,6](../evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K2x1p6-1920x1080.png), [C0](../evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-Fitx1p45-1920x1080.png), [montage falls-fort](../evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/montage-c0-falls-fort.jpg) — остров близок к концепту; зоны громче фигур; артефакты у краёв; гладкие камни у рамы.
- [ACC-022 marmoreal K1](../evidence/GD-058/final-2026-10-03/acc022/marmoreal/r1/bench-K1-1920x1080.png), [K2×2,5](../evidence/GD-058/final-2026-10-03/acc022/marmoreal/r1/bench-K2x2p5-1920x1080.png), [sarpedon K2×2,5](../evidence/GD-058/final-2026-10-03/acc022/sarpedon/r1/bench-K2x2p5-1920x1080.png) — эталон GD-058 на P5c.
- [live-tune montage sarpedon](../evidence/ENV-MAPS/live-tune-2026-10-02/montage-sarpedon.jpg) — окружение стабильно между live и `-Bench`.
- Концепты (вне git): [marmoreal-v1](../../../scraped-data/derived/concepts/env-v1/marmoreal-v1.png), [sarpedon-v2](../../../scraped-data/derived/concepts/env-v1/sarpedon-v2.png) — на marmoreal-v1 нарисованы фонари и две серые пешки на поле.
- [F/live/bench marmoreal-base-K1](../evidence/DE-FOOTAGE/2026-10-04/F/live/bench/marmoreal-base-K1.jpg) — вклейка плотнее и насыщеннее P5c; рама отделяет поле.
- [P7 montage default vs flag](../evidence/ENV-MAPS/p7-concept-paste-2026-10-01/montage-marmoreal-default-vs-flag.jpg), [P7 marmoreal concept C0](../evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-Fitx1p45-1920x1080.png) — вклейка почти один в один концепт; фонари не мерцают.
- [P8 montage p5c-p7c-p8](../evidence/ENV-MAPS/p8-3d-under-paint-2026-10-02/montage-p5c-p7c-p8.jpg) — почему для Sarpedon выбран lit3d.
- [P5c marmoreal K1×0,65](../evidence/ENV-MAPS/p5c-fab-2026-10-01/marmoreal/bench-K1x0p65-1920x1080.png) — поднос в пустоте, луна пятном; сцена «игрушечная».
- [P9b closeup marmoreal](../evidence/ENV-MAPS/p9b-hero-light-detail-2026-10-02/closeup-k2x2p5-marmoreal.jpg) — кожа Medusa оранжевая, гарпии темнее эталона.
- [A04 bench before-after-diff](../evidence/DE-FOOTAGE/2026-10-04/A04/bench/marmoreal-K1-before-after-diff.jpg) — бенч на P5c; вид не изменился.
- [user-diorama-concept-2026-09-30.webp](../../../art/imagegen/env-v1/reference/user-diorama-concept-2026-09-30.webp) (не в git) — концепт пользователя: ночь, луна, тёплые фонари, скальный поднос.

**Арт-дирекшн**
- [ART-002 option-B-painted-miniature](../evidence/ART-002/option-B-painted-miniature.png) — B на Cobble: фигуры проще и «игрушечнее» hero-quality-v1.
- [mvp-v1 arth-lunge-attack-keyposes-v1](../../../art/imagegen/mvp-v1/animation-concepts/v1/king-arthur/arth-lunge-attack-keyposes-v1.png) — ключевые позы в стиле упрощённой миниатюры.
- [scratch-v1 merlin-front-shaded](../../../art/imagegen/scratch-v1/merlin/views/merlin-front-shaded.png) — путь B: живописный Merlin на размерной сетке.

## 13. Что нужно от пользователя перед фазой 2

Вопросы сверх §8 брифа. Повторы §8 сюда не вошли.

**HUD и экраны**
1. Прогон I (AB-5…AB-8 по умолчанию, перенос форм Codex в движок v3, переимпорт) делает основной чат после прогона H
   или этот чат? Оба правят `S08TurnPortraitWidget`, `S08FlowGameModeTurnHud.cpp` и `Content/S08/UI/IconsV3`.
2. Неоновые маркеры гейтов и строки seq/phase/deck= убрать из вида игрока за флаг `-S09Markers`, а гейты `tools/s09`
   и `tools/s10` перевести на трассы `SHOT widget` (П4)? Счётчики руки и колоды оставить игроку в другом виде?
3. Перенос на UMG — по блокам, со старым Slate за флагом отката (например, `-S08SlateHud`)? Серый стенд
   `run-hud-demo` оставить на Slate?
4. Язык HUD: RU по умолчанию (UI-ACC-010) сразу при переносе на UMG или сначала EN, а RU отдельной задачей GD-048?
5. Входит ли в MVP экран ROOM, где человек сам выбирает героя и доску и смотрит колоду? Сейчас это только `-S08Auto`.
   Нужны ли регистрация и шаги входа?
6. К §8 п. 7: плашка бойца на настоящих досках уходит к краю доски. Оставить выноской у фигуры или убрать, раз HP и
   статус есть на портрете и в теге?
7. Подсказки клавиш («M begin maneuver | A attack…», «[1-9 inspect…]»): отключаемые подсказки (UI-ACC-012) или
   кнопки атаки и схемы вместо них?
8. Акцент «ваш ход»: `#F2C14E` (код, кольцо DE-012) или `accent.warm #FFB45C` (токены)?

**Палитра и стиль**
9. Q-304: подтверждаете P2 `#5A7F9F` (выбор советника) или вернуть `#9FC2D8`? Цвет абсолютно по месту или «свой и
   чужой» (`-S08TeamColorMode=relative`)?
10. К §8 п. 1: основа языка панелей — язык DE (как для значков по вашему слову 2026-10-03), «язык карт» navy/cream
    или материал? Бриф §4.1 и ваше решение расходятся.
11. Стиль фигур для ростера: «коллекционная статуэтка» hero-quality-v1 (как у v2) или B Painted Miniature (ART-002)?
    Эталоном вида героев остаётся hero-quality-v1 или делаем новый через Codex?
12. Мазок кисти и брызги туши DE: запрет только на кляксу «COMBAT!» или на весь приём?
13. Порог лицензий: сборка остаётся «лично и локально», как для паков Fab? Проверять ли коммерческие условия моделей
    картинок и видео SYNTX (Kling, Veo, Seedream, Flux и др.) перед генерацией или риск принят, как п. 9.3?

**Значки**
14. Ореол сердца (AB-6): красный, как сейчас, или светлый тон (STYLE-v3 §11)? Тлеющий обод кольца (opacity 0,35)
    почти не виден — поднять?
15. Минимальный размер значков HUD — 24 px (16 только с проверкой в виджете) или перерисовка под 16 px?
16. Перерисовать в язык v3 недостающие значки (бейджи подбора хода, значок зоны, чипы команд из mvp-v1) в объёме MVP?

**Поле**
17. V-17: сделать кольца-кандидаты другим цветом или формой, чем кольцо команды P1? У DE кандидаты синие.
18. Цвет pending: бирюза `#0D7A89` (v3) или фиолетовый `#8A56C6` (03-ux-spec)?
19. Последний ход соперника V-14/V-15 на Marmoreal почти не виден: усилить контур или заменить знаком (след, стрелка)?
20. Дуги цели красные: оставить или «цель не красная» (HI-11)?
21. Кольца команд (форма и hex — советник): принять лично или пересмотреть вместе с V-17?
22. Макеты подбора хода v2 пересобрать на значках v3, Roboto и с V-17 перед приёмкой или сразу смотреть кадры UE?

**Карты и портреты**
23. Подача лица карты (AD-OPEN-28): скан целиком в нашей рамке, кадр иллюстрации с нашим текстом из каталога RU/EN
    или гибрид (кадр в руке, скан в инспекторе)?
24. Апскейл оригинальных сканов (EN 250×349) и аватаров помощников (128 px) через SYNTX для инспектора 520×720 —
    разрешаете? Это производная от стороннего арта.
25. Рубашки: оригинальные по героям (с логотипом UNMATCHED) или одна своя в языке карт? Логотип на рубашках и картах
    досок оставляем или маскируем?
26. RU-сборка: RU-сканы (WebP с артефактами, подпись частично по-английски) или EN-сканы с RU-текстом поверх?
27. Копия скрапа в git (`docs/figma/figma-ready`, 1794 файла): оставить или вывести из отслеживания?

**Герои и анимации**
28. Гарпии H1–H3 (AD-OPEN-06): нужны ли номера (в DE их нет)? Формат «H1» или «Гарпия 1»; носитель — подставка,
    тег, портрет?
29. Личная арт-приёмка шести фигур v2 и 16 клипов: нужна ли и в каком виде (K1/K2 обеих карт, цвет и серый, лист
    клипов)?
30. D-11 остаётся или расширяем? Если расширяем — какие клипы: поза рывка в пути, защита, способность, победа,
    появление, возврат гарпии.
31. Смерть: поклон без приседа или падение на колени (переделка скина подолов)?
32. Лицо Medusa на K2 1,6× не читается, маховые гарпий тёмные на ночном Marmoreal: править или принять?
33. Ростер после MVP: кого первым, всем 3D или части 2D-жетоны?
34. Старые неотслеживаемые файлы Medusa v1 и GLB Tripo v1 (по 62 МБ): оставить вне git, удалить вручную или в
    `.gitignore`?

**VFX**
35. Заливка удара (вся фигура красно-оранжевая 450/550 мс) вам не показывалась и на K1 сливается с плащом Arthur и
    красными зонами. Оставить, сменить (например, белая вспышка 70 мс, затем красный) или вынести на лист A/B?
36. Урон и лечение против красных и зелёных зон обеих карт: вводим отдельный канал формы (силуэт-всплеск, значок)?
37. CUE-016: грейд сцены и виньетка или только UI-затемнение? CUE-017: десатурация 30 % сцены или только индикатор?
38. Бюджет VFX: ΔGPU ≤ 1 мс мерить на текущем ПК или на профиле D-07? Сколько эффектов одновременно?
39. Источник боевых VFX: производные из скачанных паков (CC BY с атрибуцией, Fab Standard) или только свои Niagara
    из генераций Codex и SYNTX?
40. Если AB-4 = «пепел»: только материал (Codex A) или с частицами-угольками? Нужен ли вариант B «дым»?
41. CUE-009: эффект на самой фигуре или достаточно слота в HUD со штампом X? CUE-006 и CUE-012 — в MVP или позже?

**Окружение**
42. Задник Marmoreal: неосвещённая вклейка (`kind=paste`, как по флагу) или освещённый рельеф, как lit3d Sarpedon
    (тогда нужно de-lit альбедо)?
43. Что анимировать на Marmoreal: мерцание фонарей (3D-головы или накладка), лепестки, ветер в сакурах, светлячки,
    туман? Нужна ли вода — в концепте её нет.
44. Основа плиты: композиция `marmoreal-v1` с чистой плитой от Codex (без нарисованных фонарей и пешек, outpaint,
    ×2) или новый концепт?
45. Поднос T2b и тематическая земля скрыты в обоих целевых видах: оставить откатом или убрать? Откат на P5c
    оформить `-NoConceptPaste` и вписать в AGENTS.md?
46. Sarpedon: доделывать остатки P10 (знамя, камни у рамы, белые струи водопада, огонь-пятно, SSIM корабля) в этом
    чате? Посмотрите ли вы кадры Sarpedon лично?
47. Свет героев P9b перенастроить под нарисованный Marmoreal и показать вам?
48. Правило задника для будущих карт: «вклейка по умолчанию, lit3d — если вклейка не держит K2» или решать по
    каждой карте?
49. Пересъёмка эталона GD-058 после смены вида Marmoreal: полный режим или лёгкий?

**Процесс**
50. Раздел 2D, HUD, VFX и карт в Art Hub для арт-приёмки или приёмка по листам в чате?
51. Можно собирать листы «наш ассет рядом с кадром DE» вне git, только для внутреннего ревью?
