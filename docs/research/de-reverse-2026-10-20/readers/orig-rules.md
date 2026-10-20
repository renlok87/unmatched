## orig-rules: игровой слой оригинала (duel-canis) и проверка правил DuelEngine

Сокращения путей (от корня репозитория `C:/Users/ren/WebstormProjects/unmached/unmached`):
- `CS/` = `DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/`
- `ISIL/` = `DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/`
- `UD/` = `DuelEngine-transfer/test-targets/unmatched-data/`
- `DEc/` = `DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/`

Номер ISIL-инструкции дан как «#N», номер строки файла как «:L». Код оригинала здесь не копируется, только имена и смысл.

### Главное (TL;DR)
1. **Правила оригинала совпадают с правилами настольной игры.** У DuelEngine (Unity-проект другого агента) несколько ключевых правил «сверены с оригиналом» неверно, и при «исправлениях» агент удалил правильное поведение:
   - **Добор 2 в начале хода: опровергнуто.** На ISIL #198, на которую ссылается rules-diff, стоит `ChangeAttribute(TotalActions, 2)`, то есть 2 действия за ход, а не добор. Вызовов Draw в начале и в конце хода нет вообще.
   - **«Fatigue: урона нет»: опровергнуто.** В оригинале есть exhaustion: на каждую карту, которую нельзя взять из пустой колоды, каждый активный боец получает `Damage(2)`. Сброс в колоду НЕ замешивается. Агент искал слово «fatigue», а в оригинале механика называется «exhaust».
   - **«Первым бустит защитник» и «буст любой картой в бою»: опровергнуто как механика.** Общего шага бустов в бою нет. DefenderDuring/AttackerDuring — это окна эффектов «во время боя», которые написаны на картах. Буст атаки возможен только по тексту карты (Second Shot, Noble Sacrifice) или пассивкой Артура (Conviction).
   - **«Схема — 1 за ход, бесплатно, до или после действия»: опровергнуто.** Схема — одно из 2 действий, и счётчик ActionsTaken для неё растёт так же, как для манёвра или атаки.
   - **«Манёвр двигает до 2 бойцов»: опровергнуто.** Двигаться может каждый боец.
2. **Наш backend по этим пунктам уже совпадает с оригиналом:** exhaustion 2, без замешивания сброса; 2 действия; схема тратит действие; манёвр = добор 1, затем движение и буст; лимит 7 в конце хода с выбором сброса.
3. **Наши карты Marmoreal и Sarpedon с точностью до нумерации совпадают с данными оригинала.** Проверка через изоморфизм графов с метками-зонами: 31 клетка и 42 связи у Marmoreal, 38 клеток и 61 связь у Sarpedon, наборы цветов зон совпадают.
4. Из 189 карт 14 героев у нас расходится одна: What Big Eyes You Have, значение у нас 2, в оригинале 3. Возможно, это errata DE.

### 1. Как описан контент
- **Карта, герой, сайдкик и колода — это классы-архетипы с пустыми сигнатурами** (`CS/data/Heroes/Medusa/Cards/GazeofStone.cs`, `Medusa.cs`, `Harpy.cs`, `MedusaDeck.cs`). Данные задаются в конструкторе цепочкой `ObjectAttributes.Has(attr, value)` по статическим `AttributeDefinition` (`CS/data/DuelAttributes.cs`, около 150 атрибутов). Пример — `ISIL/data/Heroes/Medusa/Cards/GazeofStone.txt` #101–#338: тип, количество копий, значение, буст, хозяин-боец, ключи локализации `action.gazeofstone.*`, список AbilityID (VictorDamage8Ability), класс оценки ИИ `PlayGazeofStoneValue`. Итого это «данные в виде скомпилированного кода», а не внешний JSON или DSL-файл.
- **Как подключается способность.** `AbilityArchetype` с GUID несёт параметры (например, `DrawAmount=1`) и ScriptBuilderID общего скрипта (`ISIL/data/Heroes/Shared/Abilities/Draw1AfterAbility.txt` #73–#96 → `DrawAfterScript`).
- **Скрипт** — класс с атрибутом `[ScriptBuilderFactory(guid)]` и enum состояний (`CS/scripts/actions/DrawAfterScript.cs`, `DrawAfterStates.cs`). Он собирается DSL-билдером: `ScriptBuilder.Then / TransitionIf / RepeatWhile`, триггер `When(EventPredicate)` на события из `CS/events/Events.cs` (36 событий). Глаголы — `DuelGrammar.get_Draw / get_Damage / get_Move…` (`CS/DSL/ActionBuilders/*`, около 80 билдеров).
- **Объём.**
  - 30 папок героев. У 14 есть полный контент (карты, способности, ИИ): Alice, Beowulf, Bigfoot, BruceLee, Dracula, InvisibleMan, JekyllAndHyde, KingArthur, LittleRed, Medusa, MuhammadAli, RobinHood, SherlockHolmes, Sinbad. У 16 есть только архетипы бойцов (Achilles и другие). Вдобавок есть Shared.
  - 189 типов карт (`UD/cards-full-summary.txt`).
  - 186 архетипов способностей, из них 36 в Shared.
  - 146 скриптов действий (`CS/scripts/actions`) и 30 скриптов пассивок бойцов (`CS/scripts/fighters`).
  - 210 классов оценки ИИ по героям.
  - 11 полей-карт (`CS/data/Battlefields`).

### 2. Структура хода и боя
- **Ход** (`CS/scripts/phases/PlayerTurnStates.cs`): PrePlayerTurn → TakeActions(100) → ResolveAction(200) → PostResolveAction(300) → ConfirmEndTurn(400) → PostPlayerTurn(500) → CleanupPlayerTurn(600).
  - В `ISIL/scripts/phases/PlayerTurnScript.txt` цепочка такая: BeginPlayerTurn → InitiateAction («ChooseAction») → ResolveAction → CompleteAction → TransitionIf (вернуться к шагу 100, пока остались действия) → CompletePlayerTurn → подтверждение → CleanupPlayerTurn.
- **Начало хода, `InitializeTurn`** (`ISIL/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt`):
  - `RemoveAllAttributeMods(TotalActions)` (:1662);
  - `ChangeAttribute(TotalActions=0x200, 2)` (:1694–1703);
  - `ActionsTaken=0`;
  - сброс счётчиков 0x1F8, 0x228, 0x230, 0x238;
  - log `log.player.turn`;
  - TurnStartSpace бойцов;
  - FX и стингер. Draw нет.
- **Действие** (`ISIL/actions/phase/InitiateAction_NestedType__execute_d__1.txt`): номер действия = `ActionsTaken+1` (:1432). Тип выбирается по карте: схема (:1461, `SchemeScript` :1760), атака или манёвр. Затем `ChangeAttribute(ActionsTaken 0x1F0)` (:1895) — для ЛЮБОГО типа действия.
- **Конец хода** (`CS/actions/phase/CompletePlayerTurnStates.cs`): EmitEvent(EndOfTurn)=10 → DiscardExtras=20. Сброс считается как `Max(0, hand − MaxHandSize)` (`ISIL/actions/phase/CompletePlayerTurn_NestedType__DiscardExtras_d__7.txt`:567–569), где `MaxHandSize` — константа 7 (`ISIL/entities/DuelPlayerExtensions.txt`:822).
  - Дальше идут CleanupPlayerTurn(EmitEvent CleanupTurn, CleanupState) и EndPlayerTurn(ClearUndoStack, PadPlayerTiming, AdvancePlayer) (`CS/scripts/phases/EndPlayerTurnState.cs`).
- **Атака** (`CS/scripts/phases/AttackStates.cs`): ChooseAttacker → EmitStinger → Attack → StageToActive → ApplyPassiveAttackBonuses → PostAttack → BeginCombat → ResolveCombat.
- **Бой** (`CS/scripts/phases/CombatStates.cs`, 24 состояния; тела в `ISIL/scripts/phases/CombatScript.txt`):
  1. PreDefense → защитник выбирает карту закрытой или пасует (`ResolveDefender` / `SkipResolveDefender`).
  2. PostDefense → пассивные бонусы защиты.
  3. Вскрытие карт: `Reveal…ForCombat`.
  4. Шаг 20: Immediate защитника (:1603, событие 0x78), затем TransitionIf(IsGameOver → Cleanup=22) (:1626).
  5. Шаг 30: Immediate атакующего, затем снова TransitionIf.
  6. Шаг 40: During защитника (0x80), шаг 50: During атакующего.
  7. DealCombatDamage (:1726).
  8. Шаг 70: After защитника (0x88), шаг 80: After атакующего.
  9. CleanupCombat (:1779) → AfterCombat.

  Значит, в каждом окне защитник идёт раньше, а карты боя уходят в сброс ПОСЛЕ after-эффектов. Окна — это 3 пары шагов `CombatSteps` (`CS/data/enums/CombatSteps.cs`).
- **Формула урона** (`ISIL/data/CombatInformation.txt`, метод GetTotalDamageBeforePrevention):
  - diff = атака (0, если IgnoreAttackCard) − защита (0, если IgnoreDefenseCard или нет карты);
  - если diff > 0, урон = ExtraCombatDamage + diff;
  - дальше `Math.Min` с CombatDamageCap;
  - `GetTotalDamage` обнуляет урон при IgnoreDamage.
- **Применение урона** (`ISIL/actions/Damage_NestedType__DealDamage_d__19.txt`): принятый урон = `min(dmg, Health−MinHealth)`.
- **Победитель боя.** Атакующий побеждает, если нанёс ≥1 урона; иначе побеждает защитник (`UD/localization.txt`:4786).
- **Cancel** (`CS/scripts/actions/CancelStates.cs`: CancelEffects, EmitCancelledEvent) гасит эффекты карты соперника, но бой продолжается («I still took 1 damage», `UD/localization.txt`:4748–4750).

### 3. Правила: доказательства
- **2 действия.** TotalActions=2 (выше), плюс текст «On each turn, you take two actions» (`UD/localization.txt`:4723).
- **Манёвр.** `ManeuverStates`: Initialize → PreManeuver → DrawCard → DefaultFirst → Resolve → Confirm → Cleanup (`CS/scripts/phases/ManeuverStates.cs`). В ISIL `get_Draw` (:1283) стоит до выбора бойцов, а `RepeatWhile` повторяет выбор, пока есть недвинутые бойцы (:1449).
  - Буст: в `ManeuverResolution.HandleOtherTarget` можно взять любую играбельную карту; её BoostValue добавляется к движению, карта идёт в Discard, пишется log `log.maneuver.boost` (`ISIL/actions/phase/ManeuverResolution_NestedType__HandleOtherTarget_d__3.txt`:652, :673, :821). То же говорят тексты: `UD/localization.txt`:4725–4726, :4772.
- **Стартовая рука 5.** `StartingDrawAmount`, по умолчанию 5 (`DEPATH: test-targets/cpp2il-isil/IsilDump/duel-canis/duel_canis/actions/DrawOpeningHand_NestedType__execute_d__1.txt`:353–356).
- **Пустая колода** (`ISIL/actions/Draw_NestedType__execute_d__10.txt`):
  - ShuffleWithLogs самой колоды вызывается только при флаге `shufflePreDraw` (:1379, :1407);
  - если карты нет: `ActiveFighters` (:1651), log `log.exhaust` (:1670), отчёт `exhausted_draw` (:1547), `new Damage` (:1552) с `_amount=2` (:1565, поле 0x40 в `CS/actions/Damage.cs`:248) каждому бойцу;
  - тексты `UD/localization.txt`:4804, :4814;
  - ИИ учитывает это константой `ExhaustDamagePerTurn = 2` (`DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/DuelAIClockExtensions.cs`:21).
- **Лимит руки 7** — только в конце хода (выше; `UD/localization.txt`:4805).
- **Победа.** Игрок выбывает, если его герой не в игре ИЛИ у него нет активных бойцов (`ISIL/data/enums/EliminationConditionsExtensions.txt`, CheckStandardConditionEliminate). Есть спец-режимы Team, AllFightersExceptWatson, LastSidekick. Сайдкиков убивать не обязательно (`UD/localization.txt`:4789).
- **Дальний бой.** Цель — смежный боец или боец в той же зоне (`UD/localization.txt`:4834). Зона — это цвет клетки, клетка может входить в несколько зон (:4743–4744), закрытая дверь делит зону (:4809). Атрибуты `AttackType` и `MeleeRange` (Bruce Lee бьёт с 2 клеток).
- **Движение.** Сквозь своих можно, сквозь врагов нельзя (`UD/localization.txt`:4790). `PathCosting.Cost` проверяет закрытую дверь и вражеского бойца, а `MovesThroughEnemies` (0x1C8) это отменяет (`ISIL/entities/battlefield/BattlefieldPathfindingData_NestedType_PathCosting.txt`). На клетке стоит один боец (`CS/entities/DuelSpaceExtensions.cs`:23).

### 4. Доска и поиск пути
- **Описание поля** (`CS/data/battlefield/*`):
  - `DuelSpaceDefinition(index, string[] zones)` с StartPlayer;
  - `DuelLineDefinition(a, b)` с флагом IsSecretPassage;
  - `DuelDoorDefinition` с комнатами.
- **Граф и поиск пути.**
  - `BattlefieldGraphData` хранит `GraphNode(Index, Edges)`.
  - `BattlefieldPathfindingData` держит предрасчитанные кратчайшие расстояния и граф путей.
  - Есть `PathCosting` по фигуре и эвристика по предрасчёту (A*).
  - API: `FindShortestPath`, `SpacesInMovementRange`, `EnemyFightersInZone`, `IsSpaceSameZoneAsSpace` (`CS/entities/DuelBattlefieldPathfindingExtensions.cs`). У Невидимки свой граф «в тумане» (`InTheMistBattlefieldExtensions`).
- **Сверка с нашими картами.** Скрипт `scratchpad/tools/board_cmp.py` разобрал конструктор Marmoreal и Sarpedon из ISIL и проверил изоморфизм с метками-зонами против `backend/prisma/fixtures/boards/*.topology.json`.
  - Marmoreal: 31 клетка, 42 связи, зоны Blue/Brown/Gray/Green/Purple/Red/Violet/Yellow. Изоморфизм найден (нумерация зеркальная: 1→M06 …).
  - Sarpedon: 38 клеток, 61 связь, изоморфизм найден.
  - Стартовые клетки не сверялись.

### 5. ИИ игрового слоя
- **Эвристика по каждому решению, без поиска.**
  - Каждый тип выбора имеет свой evaluator (`CS/ai/evaluators/*`: PlayerTurnEvaluator, ChooseDefenseEvaluator, ManeuverEvaluator, MoveEvaluator, BoostAttackEvaluator…).
  - Значения собираются в `AIValueSummer<double>` с причинами (`ValueReason`).
  - Основу дают функции `GetValueForDrawing / Moving / ChangingAttack / Recovering…`; по счётчику вызовов в ISIL `GetValueForDrawing` встречается 61 раз.
  - Каждая карта несёт рукописный класс оценки как атрибут: `CombatEffectValue` (0x2C0) и `ModifyPositionValue` (0x2C8), например `CS/data/Heroes/Medusa/AI/Valuation/*`.
  - Есть «часы гонки» (`DuelAIClockExtensions`: ClockEdge, IsInDanger, TurnsToExhaust) и кэши стратегии (`CS/ai/DuelAIStrategy.cs`: GoalSpaces, ValueForMove, MoveDistance).
- **Клонов и симуляции в `duel-canis/ai` нет** (grep по Clone/Simulat даёт 0). Слой Canis-core не проверялся.
- **Уровни сложности.** Три набора констант `UD/textassets/DuelAIConstants-{0,1,2}.json`.
  - Уровни 0 и 1 переопределяют 6 значений, в том числе `SelectionNoiseMin` 0.75/0.9 и `HeroDefeatValue` 100/200.
  - Уровень 2 — полный набор: 180 ключей, в enum `DuelAIConstantNames` 181 имя.
  - Уровень задаётся игроку в матче: `DuelPlayerMatchInitData(int ail)`.

### 6. Проверка заявлений rules-diff.md и README DuelEngine
| Заявление | Вердикт |
|---|---|
| Порядок окон боя: Immediate → During → Damage → After, защитник раньше | ПОДТВЕРЖДЕНО (CombatScript :1603–:1779) |
| «Первым бустит защитник», DefenderBoostPhase/AttackerBoostPhase (`DEc/Actions.cs`:352, :364) | ОПРОВЕРГНУТО: общего буста в бою нет; `StageBoost` встречается только в `ConvictionBoostScript`; буст атаки идёт через `BoostAttackAbility` у SecondShot и NobleSacrifice (`UD/cards-full.json`) |
| Буст любой картой (в бою) | ОПРОВЕРГНУТО для боя; любой картой можно бустить только МАНЁВР |
| Защита закрыта, можно пасовать; порядок AttackStates | ПОДТВЕРЖДЕНО |
| 2 действия за ход | ПОДТВЕРЖДЕНО, но в rules-diff доказательство взято из своего кода, а не из оригинала |
| Формула урона, Ignore-флаги, MinHealth, победитель боя | ПОДТВЕРЖДЕНО |
| Сброс карт боя на CleanupCombat после after-окон | ПОДТВЕРЖДЕНО |
| Добор 2 в начале хода (`DEc/Actions.cs`:587) | ОПРОВЕРГНУТО (#198 — это TotalActions) |
| Добор 1 за манёвр до движения | ПОДТВЕРЖДЕНО |
| Буст манёвра есть в оригинале, у DuelEngine нет | ПОДТВЕРЖДЕНО |
| Манёвр «до 2 бойцов» | ОПРОВЕРГНУТО (двигаются все, по очереди; реализация DuelEngine здесь верна) |
| Стартовая рука 5; лимит 7 в конце хода с выбором | ПОДТВЕРЖДЕНО |
| Пустая колода: сброс замешивается (`DEc/Actions.cs`:31–41) | ОПРОВЕРГНУТО |
| Колода и сброс пусты: урона нет | ОПРОВЕРГНУТО (exhaustion 2 каждому бойцу за каждую недобранную карту) |
| Победа: герой мёртв / нет бойцов / спец-условия | ПОДТВЕРЖДЕНО |
| Схема: 1 за ход, до или после действия (`DEc/Actions.cs`:140, `DEc/Engine.cs`:236) | ОПРОВЕРГНУТО: схема — действие |
| Ranged через зоны-группы {0-2},{3-5},{6-7} (`DEc/Board.cs`:38) | ПРАВИЛО ВЕРНО, МОДЕЛЬ ВЫДУМАНА: в оригинале зоны = цвета клеток на графе |
| Линейная доска из 8 зон, сквозь врагов можно ходить | РАСХОЖДЕНИЕ: в оригинале граф, враги блокируют путь, на клетке один боец |
| «Cancel: бой отменяется, карты возвращаются» (README) | ОПРОВЕРГНУТО; при этом код `DEc/Events.cs`:1477 гасит только способности — документация устарела |
| «Excalibur нет в данных» | ОПРОВЕРГНУТО: `CS/data/Heroes/KingArthur/Cards/Excalibur.cs`, Attack 6 / boost 3 / ×1 |
| ИИ «на клонах состояния» | Для duel-canis не подтверждается (функции ценности) |

### 7. Сверка с нашим проектом и что можно взять
- **Наш backend на ключевых правилах совпадает с оригиналом:**
  - exhaustion без замешивания сброса: `backend/src/game-engine/services/deck-management.service.ts`:75–84;
  - 2 действия: `backend/src/game-engine/models/game-state.model.ts`:462;
  - добор при манёвре: `backend/src/game-engine/services/game-action-executor.service.ts`:1750;
  - схема тратит действие: там же, :2439;
  - сброс до 7 в конце хода: там же, :1761;
  - лимит и стартовая рука: `backend/src/games/services/game-initialization.service.ts`:41–42.
- **Брать правила из DuelEngine нельзя:** они хуже наших и в 5 пунктах противоречат оригиналу.
- **Что полезно взять из оригинала как эталон и идеи:**
  1. **Эталонные данные для проверки:**
     - `UD/cards-full.json` (189 карт: значение, буст, копии, тип, способности). Наш scraped расходится только на What Big Eyes You Have (у нас 2, в оригинале 3); у Into the Woods три варианта A/B/C ×1 против нашего ×3 — это равноценно.
     - Тексты правил и подсказок в `UD/localization.txt`.
     - Графы полей (наши уже совпадают).
  2. **Идеи архитектуры:**
     - явная машина шагов боя: пары «защитник/атакующий» по трём окнам плюс короткое замыкание IsGameOver после Immediate;
     - общие параметризуемые скрипты способностей (Draw1/Draw2After → один DrawAfterScript с DrawAmount) — по сути то же, что наш ABILITY_CONFIGS;
     - события Pre/Post (36 штук) как точки подписки;
     - для ИИ: оценки с причинами (AIValueSummer), рукописные оценщики ценности для каждой карты, «часы гонки» с учётом exhaustion, уровни сложности как наборы констант с шумом выбора;
     - UX-предупреждение `duel.warning.exhaustion` перед манёвром при пустой колоде.
  3. **Код Canis/duel-canis переносить нельзя:** это IL2CPP-дамп чужого кода, а контент там скомпилирован в C#-классы и с нашей моделью «84 героя в БД» не совместим.

--- keyFacts
[F1](high) В начале хода оригинал НЕ добирает карты: на ISIL #198, которую rules-diff выдаёт за Draw(m,2), стоит ChangeAttribute(TotalActions=0x200, 2), то есть 2 действия за ход. В InitializeTurn, CompletePlayerTurn, CleanupPlayerTurn, AdvancePlayerTurn и EndTurn нет ни одного вызова Draw. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt:1694;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt:1697;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt:1703;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:587}
[F2](high) Exhaustion в оригинале есть. Если колода пуста, на каждую недобранную карту каждый активный боец получает Damage(_amount=2, не боевой); пишутся лог log.exhaust и отчёт exhausted_draw. Сброс в колоду не замешивается: ShuffleWithLogs тасует саму колоду и только при флаге shufflePreDraw. Утверждение DuelEngine «fatigue-урона нет, сброс тасуется» неверно. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1379;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1407;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1552;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1565;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1651;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/actions/Damage.cs:248;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4804;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4814;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:31}
[F3](high) Общего шага бустов в бою в оригинале нет. Шаги CombatSteps 40/50 (DefenderDuring/AttackerDuring) — это окна эффектов «во время боя», написанных на картах. Буст атаки возможен только по тексту карты (SecondShot, NobleSacrifice → BoostAttackAbility/BoostAttackScript) и пассивкой Артура (StageBoost встречается только в ConvictionBoostScript). Поэтому фазы DefenderBoostPhase/AttackerBoostPhase с «бустом любой картой» в DuelEngine выдуманы. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1603;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1693;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/actions/BoostAttackStates.cs;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/ConvictionBoostScript.txt;DuelEngine-transfer/test-targets/unmatched-data/cards-full.json;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:352;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:364}
[F4](high) Порядок боя в оригинале: PreDefense → защита закрытой картой или пас → PostDefense → пассивные бонусы → вскрытие → Immediate (сначала защитник, потом атакующий, после каждого проверка IsGameOver с переходом в Cleanup) → During (защитник, потом атакующий) → DealCombatDamage → After (защитник, потом атакующий) → CleanupCombat (сброс карт) → AfterCombat. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/phases/CombatStates.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/CombatSteps.cs;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1603;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1626;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1726;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1779;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/events/Events.cs}
[F5](high) Схема в оригинале — одно из 2 действий. InitiateAction для схемы так же увеличивает ActionsTaken (0x1F0) и создаёт SchemeInformation/SchemeScript; ограничения «1 схема за ход» нет. Модель DuelEngine «бесплатная схема 1 раз до или после действия» неверна. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/InitiateAction_NestedType__execute_d__1.txt:1432;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/InitiateAction_NestedType__execute_d__1.txt:1461;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/InitiateAction_NestedType__execute_d__1.txt:1760;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/InitiateAction_NestedType__execute_d__1.txt:1895;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4752;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:140;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Engine.cs:236}
[F6](high) Манёвр в оригинале: событие PreManeuver → добор 1 ДО движения → по очереди двигается КАЖДЫЙ боец (RepeatWhile, пока есть недвинутые), на расстояние до значения Move. Можно бустить движение сбросом любой играбельной карты на её BoostValue (log.maneuver.boost). Утверждение rules-diff «до 2 бойцов» неверно; буста манёвра в DuelEngine нет. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/phases/ManeuverStates.cs;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/ManeuverScript.txt:1283;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/ManeuverScript.txt:1449;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/ManeuverResolution_NestedType__HandleOtherTarget_d__3.txt:652;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/ManeuverResolution_NestedType__HandleOtherTarget_d__3.txt:673;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4726;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4772}
[F7](high) Лимит руки 7 (MaxHandSize — константа). Проверяется только в конце хода: сначала событие EndOfTurn, затем DiscardExtras, где сбросить нужно Max(0, рука−7) карт по выбору игрока. Стартовая рука — 5 карт (StartingDrawAmount, по умолчанию 5). {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/entities/DuelPlayerExtensions.txt:822;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/actions/phase/CompletePlayerTurnStates.cs;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/CompletePlayerTurn_NestedType__DiscardExtras_d__7.txt:567;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel_canis/actions/DrawOpeningHand_NestedType__execute_d__1.txt:353;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4805}
[F8](high) Формула урона: diff = атака − защита (каждая сторона = 0 при IgnoreAttackCard/IgnoreDefenseCard или если карты нет). Если diff > 0, урон = ExtraCombatDamage + diff, затем ограничение CombatDamageCap через Math.Min; IgnoreDamage обнуляет урон. Принятый урон = min(dmg, Health−MinHealth). Атакующий побеждает в бою, если нанёс ≥1 урона. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/CombatInformation.txt;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/CombatInformation.cs;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Damage_NestedType__DealDamage_d__19.txt;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4786}
[F9](high) Условие поражения (Standard): у игрока герой не в игре ИЛИ нет активных бойцов. Есть спец-режимы Team, AllFightersExceptWatson, LastSidekick. Cancel гасит эффекты карты соперника, но бой продолжается; в README DuelEngine написано «бой отменяется», хотя код DuelEngine уже гасит только способности. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/enums/EliminationConditionsExtensions.txt;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/EliminationConditions.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/actions/CancelStates.cs;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4750;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Events.cs:1477}
[F10](high) Контент оригинала — скомпилированные C#-архетипы. Конструктор карты задаёт атрибуты через ObjectAttributes.Has: тип, значение, буст, копии, хозяина-бойца, ключи локализации, список AbilityID и класс оценки ИИ. Способность — AbilityArchetype с параметрами (например, DrawAmount) и ScriptBuilderID общего DSL-скрипта, который срабатывает по событию через When(EventPredicate). {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/Heroes/Medusa/Cards/GazeofStone.txt;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/Heroes/Shared/Abilities/Draw1AfterAbility.txt;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/actions/DrawAfterScript.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs}
[F11](high) Объём контента в клиенте: 30 папок героев, полный контент только у 14 (Alice, Beowulf, Bigfoot, BruceLee, Dracula, InvisibleMan, JekyllAndHyde, KingArthur, LittleRed, Medusa, MuhammadAli, RobinHood, SherlockHolmes, Sinbad), у 16 — только архетипы бойцов. Всего 189 типов карт, 186 архетипов способностей (36 из них в Shared), 146 скриптов действий, 30 скриптов пассивок бойцов, 11 полей. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/Heroes;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/actions;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/fighters;DuelEngine-transfer/test-targets/unmatched-data/cards-full-summary.txt}
[F12](high) Наши топологии Marmoreal (31 клетка, 42 связи) и Sarpedon (38 клеток, 61 связь) с точностью до нумерации совпадают с данными оригинала: проверен изоморфизм графов с метками-наборами цветов зон. Стартовые клетки не сверялись. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/Battlefields/Marmoreal/Marmoreal.txt;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/Battlefields/Sarpedon/Sarpedon.txt;backend/prisma/fixtures/boards/marmoreal.topology.json;backend/prisma/fixtures/boards/sarpedon.topology.json;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/2b6a7e70-a9a9-4f0e-bd48-9f26a5894d1b/scratchpad/tools/board_cmp.py}
[F13](high) Доска в оригинале — произвольный граф: клетки с несколькими зонами-цветами, линии (могут быть тайными проходами) и двери; есть предрасчёт кратчайших путей и PathCosting для каждой фигуры. Закрытая дверь и вражеский боец блокируют путь (если нет MovesThroughEnemies), сквозь своих ходить можно, на клетке один боец. У DuelEngine доска линейная из 8 зон, зоны-группы считаются как zone/3, блокировки врагами нет. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/battlefield/DuelSpaceDefinition.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/entities/DuelBattlefieldPathfindingExtensions.cs;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/entities/battlefield/BattlefieldPathfindingData_NestedType_PathCosting.txt;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/entities/DuelSpaceExtensions.cs:23;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4790;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4834;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Board.cs:38}
[F14](medium) ИИ игрового слоя — эвристика по каждому решению: evaluator на каждый тип выбора, функции GetValueFor* с суммированием в AIValueSummer (с причинами), рукописные оценщики CombatEffectValue/ModifyPositionValue для каждой карты, «часы гонки» с ExhaustDamagePerTurn=2. Клонирования или симуляции в duel-canis/ai не найдено. Уровни 0/1/2 — наборы констант DuelAIConstants: 0 и 1 переопределяют 6 значений (шум выбора 0.75/0.9), уровень 2 содержит 180 ключей. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/ai/evaluators;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/ai/DuelAIStrategy.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/DuelAIClockExtensions.cs:21;DuelEngine-transfer/test-targets/unmatched-data/textassets/DuelAIConstants-0.json;DuelEngine-transfer/test-targets/unmatched-data/textassets/DuelAIConstants-2.json;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/match/DuelPlayerMatchInitData.cs:24}
[F15](high) Наш backend на ключевых правилах уже совпадает с оригиналом: exhaustion 2 каждому бойцу без замешивания сброса, 2 действия за ход, схема тратит действие, манёвр = добор 1 + движение и буст, лимит 7 со сбросом в конце хода, стартовая рука 5. {backend/src/game-engine/services/deck-management.service.ts:75;backend/src/game-engine/models/game-state.model.ts:462;backend/src/game-engine/services/game-action-executor.service.ts:1750;backend/src/game-engine/services/game-action-executor.service.ts:1761;backend/src/game-engine/services/game-action-executor.service.ts:2439;backend/src/games/services/game-initialization.service.ts:41}
[F16](medium) Сверка 189 карт 14 героев из cards-full.json (значение, буст, копии) с нашим scraped-data: расходится одна карта — What Big Eyes You Have (у нас 2, в оригинале 3). Into the Woods в оригинале — три карты-варианта A/B/C по 1 копии, у нас одна запись ×3; это эквивалентно. {DuelEngine-transfer/test-targets/unmatched-data/cards-full.json;scraped-data/api/heroes/little-red.json;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/2b6a7e70-a9a9-4f0e-bd48-9f26a5894d1b/scratchpad/tools/cards_cmp.py}
[F17](high) Утверждение README DuelEngine «Excalibur нет в данных» неверно: карта есть в оригинале (Attack 6, boost 3, 1 копия). {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/Heroes/KingArthur/Cards/Excalibur.cs;DuelEngine-transfer/test-targets/unmatched-data/cards-full.json;DuelEngine-transfer/duel-engine/README.md:100}

--- open
What Big Eyes You Have: в DE значение 3, у нас в scraped-data 2. Это errata цифрового издания или ошибка скрейпа? БД не проверялась, Docker остановлен.
Можно ли в оригинале закончить ход с неиспользованными действиями (шаг ConfirmEndTurn в PlayerTurnStates)? По ISIL PlayerTurnScript видно только возвращение к TakeActions, пока выполняется некое условие Exists; точное условие не разобрано.
Есть ли в ядре Canis (вне duel-canis) поиск или симуляция на клонах состояния для ИИ? В duel-canis/ai вызовов Clone/Simulat нет. Ядро — зона другого агента.
Как уровни DuelAIConstants-0/1/2 соответствуют названиям сложности в UI? Уровень передаётся как int ail в DuelPlayerMatchInitData, но связь с UI не прослежена.
Стартовые клетки (StartPlayer) Marmoreal и Sarpedon не сверялись с нашими фикстурами, сверены только зоны и связи.
Прекращается ли exhaustion-урон в Draw оригинала после поражения героя посреди многокарточного добора (наш backend на этом останавливается)? В ISIL не проверено.
Точная механика ApplyPassiveAttackBonuses/ApplyPassiveDefenseBonuses (AddWithLog с условием IsGreaterThan) разобрана только поверхностно.