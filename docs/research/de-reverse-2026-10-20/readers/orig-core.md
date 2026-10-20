## Ядро Canis в оригинале Unmatched DE: устройство и что из него переносить

**Метод.** Я читал сигнатуры типов из `test-targets/cpp2il-cs/DiffableCs/{Canis,Attributes,Networking,core-canis,core-commands,DwdJson,Logging,Canis.Command}`. По ключевым методам (`ExecuteStack`, `HasExecutionStack`, `ChangeAttribute`, `Move`, `ScriptEventReactor`, `Match.Configure`) я восстанавливал граф вызовов из ISIL (`cpp2il-isil/IsilDump/Canis/Canis/...`). Целиком тела методов не читал. Код оригинала не копирую: ниже только имена и короткие сигнатуры. Файлы `Attributes` и `Networking` формально не входят в мою часть, но без них модель сущностей не понять.

**Карта модулей.** Из `metadata_strings.txt` я вытащил 4405 путей `Assets\lib\canis\...` (логика как в `extract_paths.mjs`, сам скрипт не запускал). Распределение: duel-canis 1370, dbg-client 729, **Canis 661**, boardgames 414, core-canis 390, Networking 170, core-commands 51, DwdJson 29, Logging 2. Самые крупные разделы внутри Canis:

| Раздел | Файлов |
|---|---|
| `actions` (+ continuations, staged, timers, responseparsers) | ≈175 |
| `DSL` (ActionBuilders, Grammar, ScriptBuilders, Queries, Quantifiers, Events, Activation, TargetPickerBuilders) | 167 |
| `entities` | 56 |
| `ai` (choice, evaluators, value, standard) | 44 |
| `context` | 30 |
| `obfuscation`, `events`, `undo`, `triggers`, `gameLogs` | остальное |

Canis — общий фреймворк Dire Wolf для разных игр, не только Unmatched. На это указывают гексагональные и квадратные сетки в `Networking/.../targetinformation/HexGridWithOrientationTargetInformation.cs` и `SquareGrid...`, режимы PBM, Pass&Play, DailyChallenge, Skirmish в `Canis/canis/Match.cs`, а также 13 классов с суффиксом `V2` рядом со старыми версиями.

### 1. Модель сущностей и состояния
- **Дерево сущностей с мешками атрибутов, не ECS.** `Entity : ObjectAttributes` (`Canis/canis/entities/Entity.cs`) хранит `Parent`, `children`, `EntityID`, `OwningPlayer` и `Match`. Зоны — тоже сущности: `Pile` (`entities/Pile.cs`), `Playmat`, `PlayerEntity`. Колода и рука — это просто дети нужной кучи. Перемещение карты делается методом `MoveTo(newParent, position?)`, перемешивание — `Shuffle`.
- **Способности тоже живут в дереве.** `AbilityInstance : Entity` и `ActiveAbility : Entity` — это стек разыгрываемых способностей со стадиями Targeting=0, Costing=1, Executing=2 (`entities/ActiveAbilityStates.cs:5`). Отменённые и подготовленные действия тоже хранятся в атрибутах. Следствие: снимок дерева содержит и стек способностей.
- **Атрибуты** заданы типизированными ключами `AttributeDefinition<V>` с int-ключом (`Attributes/.../AttributeDefinition\`1.cs`). Значение лежит в `MutableAttribute<V>` с полями `BaseValue`, списком `Mod<V>` (`AddMod`, `ReplaceMod`, `ConcatMod`, `AppendMod` с `ModID` и `SortOrder`) и вычисляемым `Value` (`MutableAttribute\`1.cs:19-32`).
- **Прототипы.** `ObjectAttributes.parentAttributes` (`attributes/ObjectAttributes.cs:8`) указывает на `Archetype`. Статические данные карты общие, у сущности хранятся только переопределения.
- **Глобальный словарь атрибутов.** `CoreAttributes` содержит 214 определений (`attributes/CoreAttributes.cs`): игровые, UI, туториал, ИИ, аналитика вперемешку.
- **Состояние изменяемое** (на `ConcurrentDictionary`). Неизменяемости нет. Прогоны одного матча сериализует блокировка `matchWriteLockObject` (`Match.cs:1458`) с `Monitor.Enter` в `HasExecutionStack.Run` (по ISIL).

### 2. Действия: корутины на сериализуемом стеке
- База — `abstract class Action` с методами `IEnumerable<Action> execute()`, `undo(Context)` и `Serialize(Match)→SerializedAction` (`actions/Action.cs:93,118,134`). Действие порождает под-действия через `yield`.
- `ExecuteStack` устроен как неизменяемый связный список пар `(Action, IEnumerator<Action>)` (`continuations/ExecuteStackContainer.cs:58-60`). Метод `RunStep`, судя по ISIL, двигает верхний перечислитель и затем делает одно из трёх:
  - кладёт под-действие на стек (`PushSubAction`);
  - если выпало `PendSelection`, останавливается на выборе (`HaltAtSelection`);
  - если действие закончилось, снимает его и вызывает `HandleReturningAction` у родителя (`PopToParent`).
- `HasExecutionStack` держит именованные стеки "match", "timer", "resign", "connection", "cheats". В нём есть защита от бесконечного цикла `MaxRunIterations = 25000` (`hasExecutionStack/HasExecutionStack.cs:161`), а результат прогона — `MatchPauseTypes` (ждём человека, ждём ИИ, конец матча, ошибка).
- Почти у каждого действия есть сериализуемый двойник: 56 файлов `Serialized*` в `actions/`. Это и делает стек сохраняемым. Длинные действия выражены явными автоматами состояний (`StateMachineActionV2` с `CurrentState`, `WrappedAction` с состояниями Pre/Run/Post = 100/200/300).
- Каждая мутация — это действие, и оно же рассылает сообщение. По ISIL `ChangeAttribute.execute` создаёт запись отмены (`CreateChildUndoEntry` / `AddUndoEffect`), меняет атрибут и отправляет `ActionDecorators.Send` (сообщение `AttributeModified`). `Move` ведёт себя так же и отправляет `EntityMoved`.
- **Подготовка и фиксация.** `IStagedAction` с методами `Stage`, `Commit`, `Rollback` и шагами `Preview`, `MoveToMutation`, `Mutation` (`actions/staged/`): ход показывается заранее и откатывается до подтверждения.
- **Отмена** — это дерево `UndoNode : Entity` с обратным `SerializedAction`, а также атрибуты `UndoStack` и `UndoEffects` (`entities/UndoNode.cs`, `CoreAttributes.cs:231`). Правило «отменять можно» задаётся через `CreateUndoCriteria`.
- **Проверка ввода.** У выбора есть `SelectionMessage.Counter` (`Networking/.../SelectionMessage.cs:10`). Ответ со старым счётчиком отбрасывается: в логе `IsValidSelection` пишется «attempted stale selection». Ответ разбирает `ResponseParser`, а `TargetInformation.Validate(TargetResponse)` сверяет его с предложенными целями.

### 3. Протокол выбора и пауза
- `PendSelection` порождает `PendingSelection` с полями `Selection`, `ResponseParser`, `Continuation`, `Completion`, `CreateUndo` (`data/PendingSelection.cs:16-31`).
- Продолжение `ContinueExecuteStack` хранит **сериализованный остаток стека** (`SerializedExecuteStack`). Сам `PendingSelection` лежит в атрибуте игрока `PendingSelections` (`CoreAttributes.cs:219`).
- `ConsumeCounter` (по ISIL) делает следующее: проверка счётчика → разбор ответа → при необходимости отмена → `GenerateContinuationAction` → `SerializedExecuteStack.Deserialize` → `RunActionWithTargets` → снова в стек.
- Предложение хода — дерево допустимых вариантов: `SelectionWithTargetsRequired.TargetMap: Dictionary<EntityID, TargetInformation[]>` (`SelectionWithTargetsRequired.cs:32`). Человек, ИИ (`AIProfileAbs.MakeChoice`) и сеть отвечают на одно и то же сообщение. Есть запасной случайный ответ `PlayerEntity.DefaultRandomChoice`.
- Одновременные выборы и перехваты: `SimultaneousAction`, `SlapjackSimultaneousAction` (кто ответит первым), `ParallelResponseAction`, `JumpIn`.

### 4. DSL — встроенный в C#, не данные
- Карта — это класс-наследник `Archetype`, который в конструкторе задаёт атрибуты через `ObjectAttributes.Has(...)`. В duel-canis 558 таких классов. Пример по ISIL — `TheHolyGrail.ctor`: ключи локализации и тайминг.
- Поведение — отдельный класс-скрипт `[ScriptBuilderFactory(id, method)]`, таких 285. Пример — `TheHolyGrailScript.Script()`: `TriggeredScriptBuilder` с условием на событие, затем `.Then(...)` с запросами `First.From`, `IsLessThan`, `LogAction`.
- Словарь DSL (`Canis/canis/DSL`):
  - **Откуда брать** — `FromPhrase` с методами `Where`, `Or`, `Children`, `OrderedBy`, `Count`, `Any`.
  - **Фильтры** — `PropertiesPhrase` с `And` и `Or`.
  - **Квантификаторы** — `All`, `First`, `FirstN`, `Random`, `Repeat`.
  - **Выбор целей** — `SelectedTargetBuilder` с `WithMin/Max/Forced/Prompt/Evaluator/AutoCreateUndo`.
  - **Запросы** — `ScriptQuery<T>`.
  - **Действия** — `ActionBuilder`: Move, ChangeAttribute, FireEvent, CreateEntities, ChooseX, SelectChoice и др.
  - **Автомат скрипта** — `ScriptBuilder.Then`, `TransitionIf`, `RepeatWhile`, `CancelWhen`. Состояния берутся из enum (`ScriptStateDefinition`), данные состояний — из `StateDataMap`.
  - **Активация** — `ActivationCondition` и флаги `OutOfPlay` / `Global`.
- Скрипт компилируется в `GenericStateMachineAction`. Его можно продолжить с состояния по имени: `ContinueFromState(stateName, stateData, …)` (`ScriptBuilders/ScriptBuilder.cs:250`). Лямбды внутри скрипта не сериализуются, но это и не нужно: при загрузке скрипт пересобирается по `ScriptBuilderID` и продолжает работу с указанного состояния.

### 5. События, триггеры и окна
- Событие — это имя плюс `Context` (`events/Event.cs`, `ScriptEventDefinition` — просто имя). Предикат `EventPredicate` строится через `Source`, `Target`, `Player`, `Owner`, `Ability` (`DSL/Events/EventPredicateGrammar.cs`).
- `ScriptEventReactor` держит подписки двух видов: срабатывающие скрипты способностей по имени события и **until-скрипты** — эффект с действием снятия, которое выполняется, когда сработает предикат (`events/ScriptEventReactor.cs:338,350`). Оба вида сериализуются (`SerializedUntilResponse`, а также `SaveData.eventReactor`, `SaveData.cs:54`).
- `FireEvent` ничего не исполняет сразу. Он возвращает действие (пакет `RunEventBatch`), которое ложится на стек; срабатывания запускаются через `RunUsableAbilityForPlayer.WithoutCosts` (ISIL `SerializableEventReactor.MakeRunTriggeredAbility`).
- Конкретные боевые окна (до боя, при раскрытии, после боя) определены в duel-canis, а не в ядре.

### 6. RNG и детерминизм
- `CanisRandom : System.Random`. В нём есть стек `NotSoRandomValues` и метод `Push(int)` для подстановки значений в тестах и туториалах (`CanisRandom.cs:98`). Есть методы `WeightedElement`, `Subset`, `NormalValue`.
- `Match.Configure` создаёт `CanisRandom` и отдельный `SelectionRandom` из `MatchInitData.randomSeed` (`MatchInitData.cs:93`; в ISIL — чтение поля 0xB8 и вызов конструктора Random).
- Внутреннее состояние RNG **не входит** в `SaveData` (поля в `SaveData.cs:32-54`). Значит, повторяемость гарантирована только внутри одного процесса, а перезапуска по «seed + журнал» нет. Уверенность средняя.

### 7. Клонирование, сериализация, снимки
- Механизма «клонировать матч для поиска» нет. `SimulationEntity` и `SimulationLookup` в ISIL упоминаются только в `EntityHierarchyExtensions`, то есть фактически не используются.
- Сохранение — полный снимок на каждой паузе: `SaveOnPause` → `SaveData{currentState: SerializedGameState (дерево SerializedEntity), playerStates{lastState, displayActions}, eventReactor}`. Восстановление — `DeserializeMatch`.
- Ориентир — снимок, а не журнал действий. Журнал для игроков отдельный: `GameLogBuilder` → `SerializedGameLog{id, logText, parent, undo, attributes}`.
- JSON строится через свой `DwdJson` с полиморфизмом по полю-подсказке (`TypeHintingAttribute.HintingField`) поверх JsonFx.

### 8. Скрытая информация
- Сервер хранит полное состояние, а **каждое сообщение маскируется отдельно для каждого игрока**. Видимость задают атрибут `Hidden: Visibility` на сущности и `DescendantsHidden` на куче (`CoreAttributes.cs:199-200`) в трёх стилях:
  - `DeckStyle` — скрыто от всех;
  - `HandStyle(owner)` — видно только владельцу;
  - `Public` — видно всем.
- Маскировщики `MessageObfuscator<T>` переписывают сообщения. Например, `EntityMovedObfuscator.FilteredMove(…, wasHiddenInSource, isHiddenInDestination)` превращает перемещение в `MaterializeEntity`, `DematerializeEntity` или `EntityMovedWithoutID` (`messages/EntityMovedObfuscator.cs:93`). Похожие маскировщики есть для `AttributeModified` и `SerializedGameState`. Раскрытие карты идёт через `EntityIntroduced`.

### 9. ИИ в ядре
- **Жадная оценка одного выбора, без перебора наперёд.**
  - На выбор или способность вешается оценщик `AISelectionEvaluator → AIChoice{rank}`; есть варианты `SelectFromTargetsEvaluator`, `ArchetypeChoiceEvaluator`, `XChoiceEvaluator`.
  - Ценность карты задаётся атрибутами `ValueForPlay` / `ValueForPlayOn` (`AIValuationFunction`, `CoreAttributes.cs:228`), а `AIStrategy` и `IntentFitness` задают общие намерения.
- **Объяснимые оценки.** `AIValueSummer<T>` — сумма с причинами `ValueReason{Value, Reason}` и методом `Breakdown()` (`ai/value/`).
- **Сложность** — набор констант на тип и уровень ИИ (`AIConstants.GetConstants(aiType, level)`, файлы `docs/original-ai/DuelAIConstants-{0,1,2}.json`) плюс шум `InjectNoise` и `SelectionNoiseMin`.
- **Утилиты** — `Roller`/`WeightedDistribution`, `KnapsackSolver`, `BestRankTimeout` (`entities/ai/AIAlgorithmUtil.cs`).
- В `ai_sim/AIConstantsVector.CloneWithReplacementAt` есть заготовка под офлайн-подбор констант, но сам подбор в клиенте отсутствует.

### 10. Клиентская часть ядра (core-canis, core-commands)
- Клиентское зеркало дерева: `Entities` / `EntityComponent` с версиями (`dwd/core/match/`). Входящие сообщения → `Delorean.Process/Enqueue` → очереди исполнения (анимации).
- Предсказание с откатом: `PrescienceAuthority`, `IPrediction.GetRewindCommand`.
- UI выбора — дерево узлов `ISelectionNode` / `ISelectionRoot`. `Command` — корутины для анимаций.
- `Logging.Debug` — обёртка над ZLogger с отдельным логгером для ИИ.
- Для нашего бэкенда всё это не нужно, это аналог клиента UE (S08).

### 11. Зрелость
Каркас промышленный и многолетний. Сильные стороны:
- единый механизм паузы и продолжения;
- отмена и подготовка ходов;
- маскировка скрытого по каждому игроку;
- защита от зацикливания;
- таймеры, переподключение, асинхронная игра (PBM);
- общий для всех игроков протокол выбора.

Слабые стороны:
- `Match` — объект-бог: 279 методов (`Match.cs`);
- 214 глобальных атрибутов в одном словаре;
- много рефлексии;
- контент — это код (правка карты требует новой сборки);
- состояние RNG не сохраняется;
- ИИ только жадный.

### 12. Сравнение с нашим бэкендом и вывод
У нас (`backend/src/game-engine`, около 15,3 тыс. строк):
- неизменяемый типизированный `GameState` (`models/game-state.model.ts`);
- контент как данные: `CardEffect` из `effect-text-parser.ts` и `ABILITY_CONFIGS`;
- точечные паузы: `PendingEffect` с 8 типами, `CombatEffectContinuation`, `pendingTurnEnd`, `pendingManeuver`, `pendingHandDiscard`;
- закрытый список из 7 триггеров `AbilityTrigger` (`abilities/ability-config.ts:45`);
- скрытие через снимок `filterPrivateData` (`games/game-state.service.ts:828`);
- `Math.random` в 5 местах (`deck-management.service.ts:33,192`, `card-effect-executor.service.ts:1383,1446`, `game-initialization.service.ts:51`);
- `ValueModifierService` хранит модификаторы во внутренней памяти процесса и **нигде не вызывается** (`engine/value-modifier.service.ts`; grep `this.valueModifier` пуст).

**Вердикт по ядру: движок не переносить и на Canis не переписываться.** Встроенный C#-DSL и сериализуемые корутины плохо подходят к нашему контенту из БД (84 героя, ~880 карт) и к админке. Генераторы в JS не сериализуются, поэтому прямой аналог `ExecuteStack` в TypeScript потребовал бы двойника на каждое действие. Это ровно та цена, которую платит оригинал. Стоит забрать **идеи**, по приоритету:

1. **Одна сущность «ожидаемое решение».** Вместо россыпи pending-полей — одна запись `PendingDecision{id, counter, playerId, offer, parser, continuation}`, где `continuation` — сериализуемая очередь оставшихся шагов как **данные**, а не генераторы. Это закрывает рост числа особых случаев с каждым новым героем.
2. **Общее предложение допустимых ходов.** Движок выдаёт дерево допустимых ответов (аналог `TargetMap`), на него отвечают и человек, и ИИ, и Game Tester. Новый выбор карты сразу становится доступен ИИ (с запасным случайным ответом), и ИИ не может сделать незаконный ход. Сейчас `ai-decision.service.ts` перечисляет варианты сам.
3. **Модификаторы в состоянии.** Хранить `{base, mods[{id, op, value, order, source}]}` в `GameState` вместо неработающего `ValueModifierService`. Вместе с этим — until-эффекты: «предикат события → снятие», сериализуемые как в `ScriptEventReactor`.
4. **Открытые события.** Имена событий плюс предикаты Source/Target/Owner вместо закрытого union. Окна боя выразить событиями.
5. **Детерминированный RNG.** Seed и состояние генератора хранить в `GameState` — лучше, чем в оригинале. Добавить подстановку значений для тестов (аналог `NotSoRandomValues`).
6. **Объяснимые оценки ИИ** (значение плюс причина) и константы уровня в JSON с шумом. Дёшево и сильно помогает отладке в админке.
7. Защита от зацикливания резолвера и счётчик выбора против повторных и устаревших ответов. Частично это уже есть (`sequenceNumber`, `PendingEffect.id`).
8. Позже, если понадобится: подготовка, фиксация и откат хода; маскировка дельта-сообщений по игрокам, если уйдём от рассылки полных снимков.

Чего не брать: дерево сущностей с прототипами и `ConcurrentDictionary`, DSL как C#-код, `DwdJson`, клиентские Delorean и Command (для них есть UE).

### 13. Расхождения README DuelEngine с оригиналом
В `duel-engine/README.md` (строки 27-35) оригиналу приписаны три принципа, которых в ядре нет:
- «партия = seed + список действий» — на деле снимок на каждой паузе, состояние RNG не сохраняется;
- «контент = данные, не код» — на деле 558 классов `Archetype` и 285 фабрик скриптов;
- «клоны состояния» в ИИ — на деле клонирования нет, оценка жадная.

Это решения самого DuelEngine, а не заимствования у Canis.

### Главные типы
- **Состояние:** `Canis.entities.Entity`, `PlayerEntity`, `Pile`, `AbilityInstance`, `ActiveAbility`, `UndoNode`; `Canis.attributes.ObjectAttributes`, `IEntity`, `CoreAttributes`; `Attributes: AttributeDefinition<V>`, `MutableAttribute<V>`, `Mod<V>`, `ModID`.
- **Исполнение:** `Canis.actions.Action`, `StateMachineActionV2`, `WrappedAction`, `TargetPicker<T>`, `PendSelection`, `CostAction`, `IStagedAction`; `continuations.ExecuteStack`, `ExecuteStackContainer`, `SerializedExecuteStack`, `ContinueExecuteStack`, `ActionAcrossTargets`; `hasExecutionStack.HasExecutionStack`; `context.Context`, `SerializedContext`.
- **Выбор:** `data.PendingSelection`, `SelectionMessage`, `SelectionWithTargetsRequired`, `TargetInformation`, `TargetResponse`, `ResponseParser`, `SelectionCompletion`.
- **DSL:** `ScriptBuilder`, `TriggeredScriptBuilder`, `ActivatedScriptBuilder`, `ActionBuilder`, `FromPhrase`, `PropertiesPhrase`, `Quantifier`, `ScriptQuery<T>`, `SelectedTargetBuilder`, `EventPredicate`, `ActivationCondition`, `GenericStateMachineAction`, `StateData`.
- **События:** `Event`, `ScriptEvent`, `ScriptEventDefinition`, `EventReactor`, `SerializableEventReactor`, `ScriptEventReactor`, `RunEventBatch`.
- **Сохранение и скрытое:** `SaveData`, `SerializedGameState`, `SerializedEntity`, `Visibility`, `DescendantsHidden`, `MessageObfuscator<T>`, `IMessageActionFactory`.
- **ИИ:** `AIProfileAbs`, `AISelectionEvaluator`, `AIChoice`, `AIChoiceContext`, `AIValuationFunction`, `AIValueSummer<T>`, `AIConstants`, `Roller<T>`.
- **RNG:** `CanisRandom`, `MatchInitData.randomSeed`.

--- keyFacts
[F1](high) Состояние в Canis — изменяемое дерево Entity (родитель и дети) с мешками типизированных атрибутов. Зоны, колоды и руки — сущности-кучи (Pile); перемещение карты — MoveTo(newParent, position). {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/entities/Entity.cs; Canis/canis/entities/Pile.cs; Canis/canis/attributes/ObjectAttributes.cs:8}
[F2](high) Атрибуты: AttributeDefinition<V> с int-ключом; MutableAttribute<V> хранит BaseValue, список Mod<V> (AddMod/ReplaceMod/ConcatMod/AppendMod с ModID и SortOrder) и вычисляемое Value. Сущность наследует атрибуты своего Archetype как прототипа. {DiffableCs/Attributes/Canis/attributes/MutableAttribute`1.cs:19-32; Attributes/Canis/attributes/Mod`1.cs; Attributes/Canis/attributes/AddMod`1.cs; Canis/canis/archetypes/Archetype.cs}
[F3](high) Действие (Action) — корутина: execute() возвращает IEnumerable<Action>, есть undo(Context) и Serialize(). ExecuteStack — неизменяемый список пар (Action, IEnumerator); RunStep кладёт под-действие на стек, останавливается на PendSelection или снимает завершённое действие. {DiffableCs/Canis/canis/actions/Action.cs:93,118,134; Canis/canis/actions/continuations/ExecuteStackContainer.cs:58-60; cpp2il-isil/IsilDump/Canis/Canis/actions/continuations/ExecuteStack.txt (RunStep)}
[F4](high) Пауза на выборе сохраняет сериализованный остаток стека (ContinueExecuteStack.SerializedStack) внутри PendingSelection в атрибуте игрока PendingSelections. Ответ проверяется по Counter, затем разбирается и продолжает стек через SerializedExecuteStack.Deserialize. {DiffableCs/Canis/canis/data/PendingSelection.cs:16-31; Canis/canis/actions/continuations/ContinueExecuteStack.cs; Canis/canis/attributes/CoreAttributes.cs:219; IsilDump/Canis/Canis/hasExecutionStack/HasExecutionStack.txt (ConsumeCounter)}
[F5](high) Почти у каждого действия есть сериализуемый двойник (56 файлов Serialized* в actions/); длинные действия — явные автоматы (StateMachineActionV2, WrappedActionState 100/200/300). {DiffableCs/Canis/canis/actions/ (Serialized*.cs); Canis/canis/actions/StateMachineActionV2.cs; Canis/canis/actions/WrappedActionState.cs}
[F6](high) Защита от зацикливания: MaxRunIterations = 25000; именованные стеки match/timer/resign/connection/cheats; результат прогона — MatchPauseTypes; прогоны одного матча сериализуются блокировкой matchWriteLockObject. {DiffableCs/Canis/canis/hasExecutionStack/HasExecutionStack.cs:161; Canis/canis/matchThread/MatchPauseTypes.cs; Canis/canis/Match.cs:1458}
[F7](high) DSL встроен в C# (лямбды и fluent-построители): FromPhrase/PropertiesPhrase/Quantifier/ScriptQuery/ActionBuilder/ScriptBuilder.Then/TransitionIf. Карта — класс-наследник Archetype (558 штук в duel-canis), поведение — класс-скрипт с ScriptBuilderFactory (285 штук). {DiffableCs/Canis/canis/DSL/ScriptBuilders/ScriptBuilder.cs; Canis/canis/DSL/FromPhrase.cs; DiffableCs/duel-canis/duel/canis/data/Heroes/KingArthur/Cards/TheHolyGrail.cs; IsilDump/duel-canis/duel/canis/scripts/actions/TheHolyGrailScript.txt}
[F8](high) Скрипт компилируется в GenericStateMachineAction и продолжается с состояния по имени (ContinueFromState) плюс сериализованные StateData, а не через сериализацию лямбд. {DiffableCs/Canis/canis/DSL/ScriptBuilders/ScriptBuilder.cs:250; Canis/canis/DSL/StateData.cs}
[F9](high) События — имя плюс Context; FireEvent возвращает действие RunEventBatch на стек. ScriptEventReactor хранит срабатывающие скрипты и until-скрипты (предикат и действие снятия); оба вида сериализуются в SaveData.eventReactor. {DiffableCs/Canis/canis/events/ScriptEventReactor.cs:338,350; Canis/canis/events/RunEventBatch.cs; Canis/canis/events/SerializedUntilResponse.cs; Canis/canis/SaveData.cs:54}
[F10](medium) RNG: CanisRandom наследует System.Random и имеет стек подстановки NotSoRandomValues; создаётся из MatchInitData.randomSeed в Match.Configure. Состояние RNG в SaveData не сохраняется. {DiffableCs/Canis/canis/CanisRandom.cs:98,102; Canis/canis/MatchInitData.cs:93; IsilDump/Canis/Canis/Match.txt (Configure, чтение поля 0xB8 и конструктор Random); Canis/canis/SaveData.cs:32-54}
[F11](high) Сохранение — полный снимок на каждой паузе (SaveOnPause → SaveData с currentState SerializedGameState, displayActions по игрокам, eventReactor), а не журнал «seed + действия». {DiffableCs/Canis/canis/SaveData.cs:32; Canis/canis/PlayerSaveData.cs; IsilDump/Canis/Canis/Match.txt (SaveOnPause, DeserializeMatch)}
[F12](high) Скрытая информация: сервер хранит полное состояние; каждое сообщение маскируется для каждого игрока (Visibility, DescendantsHidden в стилях DeckStyle/HandStyle/Public, MessageObfuscator<T>); перемещение превращается в Materialize/Dematerialize/EntityMovedWithoutID. {DiffableCs/Canis/canis/obfuscation/Visibility.cs; Canis/canis/obfuscation/DescendantsHidden.cs; Canis/canis/messages/EntityMovedObfuscator.cs:93; Canis/canis/attributes/CoreAttributes.cs:199-200}
[F13](high) Протокол выбора общий для человека, ИИ и сети: SelectionWithTargetsRequired.TargetMap (EntityID → TargetInformation[]); ИИ отвечает на то же сообщение через AIProfileAbs.MakeChoice; есть запасной DefaultRandomChoice. {DiffableCs/Networking/Networking/selection/messages/SelectionWithTargetsRequired.cs:32; Canis/canis/entities/ai/AIProfileAbs.cs; Canis/canis/entities/PlayerEntity.cs}
[F14](high) ИИ в ядре жадный, без перебора наперёд: оценщики выбора, функции ценности карт ValueForPlay/ValueForPlayOn, AIValueSummer с причинами, константы по уровню из JSON плюс шум. Клонирование состояния не используется (SimulationEntity упоминается только в EntityHierarchyExtensions). {DiffableCs/Canis/canis/ai/value/AIValueSummer`1.cs; Canis/canis/ai/value/ValueReason`1.cs:8; Canis/canis/ai/AIConstants.cs; Canis/canis/ai/value/AIValueSummerExtensions.cs:13; Canis/canis/attributes/CoreAttributes.cs:226-228; grep SimulationEntity по IsilDump}
[F15](high) Отмена: дерево UndoNode с обратным SerializedAction и атрибуты UndoStack/UndoEffects; ChangeAttribute и Move сами пишут записи отмены. Подготовка ходов: IStagedAction со Stage/Commit/Rollback и шагами Preview. {DiffableCs/Canis/canis/entities/UndoNode.cs; Canis/canis/undo/MatchWithUndoableActionsUtils.cs; Canis/canis/actions/staged/IStagedAction.cs; IsilDump/Canis/Canis/actions/ChangeAttribute`1_NestedType__execute_d__5.txt}
[F16](high) Признаки зрелости и тяжести: Match — 279 методов, CoreAttributes — 214 глобальных определений, 13 классов с суффиксом V2; ядро общее для разных игр (гексагональные и квадратные сетки, PBM, Pass&Play). {DiffableCs/Canis/canis/Match.cs; Canis/canis/attributes/CoreAttributes.cs; DiffableCs/Networking/Networking/selection/targetinformation/HexGridWithOrientationTargetInformation.cs}
[F17](high) У нас: неизменяемый GameState с точечными паузами (8 типов PendingEffect, CombatEffectContinuation и другие pending-поля), закрытый список из 7 AbilityTrigger, Math.random в 5 местах; ValueModifierService держит модификаторы в памяти процесса и нигде не вызывается. {backend/src/game-engine/models/game-state.model.ts:144,385; backend/src/game-engine/abilities/ability-config.ts:45; backend/src/game-engine/services/deck-management.service.ts:33; backend/src/game-engine/effects/card-effect-executor.service.ts:1383; backend/src/game-engine/engine/value-modifier.service.ts}
[F18](medium) README DuelEngine приписывает оригиналу «seed + журнал действий», «контент = данные» и «клоны состояния» в ИИ — в ядре Canis этого нет. {DuelEngine-transfer/duel-engine/README.md:27-35}

--- open
Серверного кода оригинала в дампе нет: работает ли в онлайн-матчах на сервере тот же Canis Match (по устройству Match — вероятно), не проверено.
Как пересоздаётся RNG при загрузке из SaveData (повторно из randomSeed или иначе)? Тело DeserializeMatch разобрано только по вызовам.
Что происходит, если в момент паузы на стеке лежит действие без сериализуемого двойника: FallbackSerializedAction и ActionDeserializationException существуют, но их поведение не разобрано.
Откуда берутся данные архетипов (Archetypes.CreateArchetypesFromSheet: таблицы?) и насколько статы карт задаются данными, а не кодом — не проверено.
Использует ли наш ai-decision.service.ts те же перечислители допустимых ходов, что и валидатор? Если нет, это аргумент за общий протокол предложения ходов (F13).