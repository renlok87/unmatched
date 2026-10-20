## Оригинал Unmatched DE: сеть, платформа, клиент (часть orig-net-client)

Сокращения путей: **CS** = `DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/`, **ISIL** = `DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/`, **DATA** = `DuelEngine-transfer/test-targets/unmatched-data/`. Тела методов оригинала я не копировал. Выводы сделаны по сигнатурам, полям и по тем именам вызовов, которые ISIL смог разрешить. Exe не запускался, сетевой трафик не снимался.

### Вердикт по моей части
1. Онлайн оригинала — **авторитетный сервер, не lockstep**. Один и тот же движок Canis (C#) работает на сервере для онлайна и внутри клиента для офлайна: ИИ, туториал, испытания, pass-and-play. Клиент только показывает поток событий.
2. Наша модель совпадает с ним по сути: NestJS как единственный источник истины, проекция на зрителя, GraphQL WS. **Модель не меняем.** Схему «seed + список действий» из DuelEngine для сети не берём.
3. Брать стоит **идеи протокола и презентации, а не код** (приоритеты в §7):
   - поток display-событий с вложенными именованными последовательностями;
   - сервер сам перечисляет легальные цели;
   - счётчик выбора;
   - хвост показанных событий у каждого игрока;
   - синхронизация серверного времени;
   - ИИ доигрывает ход по таймауту.

### 1. Сетевая модель

**Где идёт симуляция.**
- В `Match` (CS/Canis/canis/Match.cs) есть чисто серверные обязанности:
  - рассылка сообщений по аккаунтам `messageDispatcher` (:1467);
  - блокировка `matchWriteLockObject` (:1458);
  - сейвы `WriteSaveData`/`WriteSimultaneousSaveData` (:1512);
  - push `PlayerNotifier` (:1514);
  - `RemoveIdlePlayer`;
  - `reconnectMessageQueue` (:1497);
  - `LastSelectionMessageV2` (:1517) — последний открытый вопрос игрока для повторной отправки;
  - таймеры `UseTurnTimers` (:1494) и `HandleIdleTurn` (:2253);
  - `StartAIvsAI` (:2482).
- Входящее сообщение обрабатывается так: `Match.Write` → под `Monitor` → `MessageRouter.Handle` (ISIL/Canis/Canis/Match.txt).
- Роутеры: Main, Timer, Resign, Connection (CS/Canis/canis/messageRouters/).
- Серверного бинаря в комплекте нет. Что сервер исполняет тот же Canis, я вывожу по этим признакам (уверенность средняя-высокая).

**Онлайн-клиент своего `Match` не держит.**
- `CanisOnlineMatch.Configure(gameID, accountID, CanisNetworkState, SequenceMessage sgs, isLive)` кладёт стартовое состояние в общий конвейер через `SessionProvider.DispatchOfflineMessage`. `Write` уходит в `CanisNetworkState.Write` (ISIL/boardgames/Canis/boardgames/CanisOnlineMatch.txt).
- Офлайн: `DBGCanisOfflineMatch.createMatch()` поднимает локальный `Match`, а `CanisMatch.MessageDispatcher(accountID, msg)` отбирает сообщения для локального игрока. Конвейер тот же (CS/dbg-client/boardgames/match/canis/DBGCanisOfflineMatch.cs, CS/boardgames/Canis/boardgames/CanisMatch.cs).
- Человек, ИИ и сеть пишут через один интерфейс `ISessionWriter`/`IAccountSessionWriter` (`WriteFromAccount`).

**Что идёт по проводу.**
- Снапшот `SerializedGameState{entities, playerAccounts, gameOptions}` — дерево `SerializedEntity{entityID, parentID, owningPlayerID, entityName, attributes, children}`.
- Затем события-дельты (CS/Networking/canis/messages/):
  - EntityAdded/Moved/Destroyed/Introduced;
  - AttributeModified/Removed;
  - Materialize/DematerializeEntity;
  - Shuffled, ActivePlayerSet, PlayFX;
  - Start/Stop/Suspend/ResumeSequence;
  - таймеры.
- Lockstep нет: ответы соперника клиенту для пересчёта не приходят. Хешей и проверки состояния тоже нет: поиск checksum/desync нашёл только checksum таблиц локализации (CS/Utils/Canis/utils/localization/ILocalizer.cs:154).

**Транспорт.**
- WebSocket (NativeWebSocket, CS/WebSocket/) и JSON DwdJson с подсказками типов.
- В строках бинаря (DATA/metadata_strings.txt:287–290) есть:
  - шаблон `ws(s)://{0}:{1}/{2}`;
  - адреса `wss://<id>.execute-api.us-west-2.amazonaws.com/{Prod,QA,ProdDuel,QADuel}`, то есть лобби и матчмейкинг идут через AWS API Gateway WebSocket.
- `DWDGameSession{GameSessionId, MaximumPlayerSessionCount, CurrentPlayerSessionCount, IpAddress, DnsName, Port, GameProperties, GameSessionData}` и `DWDPlayerSession{PlayerSessionId}` (CS/Networking/Networking/game/DWDGameSession.cs:13–27) совпадают с моделью AWS GameLift. Значит, матч — это выделенный процесс, к которому клиент подключается по адресу сессии (вывод по именам).
- Steam используется для тикета входа (→ `GetSteamPlatformToken`), статистики, оверлея, DLC и клавиатуры Steam Deck. Вызовов SteamNetworking/Matchmaking из игровых сборок нет — **это не P2P**.

**Надёжность канала** (CS/boardgames/boardgames/match/CanisNetworkState.cs):
- у каждого сообщения есть счётчик, клиент отвечает `AckMsg{counter}`;
- неподтверждённые сообщения хранятся (`ackMsg`, `GetUnackedMessages`, :187, :302) и отправляются повторно;
- сообщения не по порядку ждут в буфере `outOfOrderMessages` (:186);
- ping раз в 2 с (:156), порог реконнекта 18 с (:155), 3 попытки подключения к лобби (CS/dbg-client/boardgames/menus/OnlinePlaySessionProvider.cs:108);
- сообщения ходят пачками `MessageBundleMsg`, сжатые deflate+base64 (EventDeserialization.cs:12–20);
- реконнект — `ReJoinGameSession{token, fastReconnect, ackClientMessages}`;
- политика при обрыве `ReconnectBehaviour{ReturnToMainMenu, ReloadPlaymat}`.

**Повтор после возврата.**
- На каждого игрока сервер хранит `PlayerSaveData{lastState, displayActions}` (CS/Canis/canis/PlayerSaveData.cs:32–36): его последний снапшот и хвост показанных событий.
- `DispatchMessage(..., shouldStoreDisplayAction)` дописывает хвост через `PlayerSaveData.AddDisplayActions` (ISIL Match.txt). `ClearDisplayActionsForPlayer` сбрасывает хвост при новом снапшоте.
- Клиент проигрывает хвост ускоренно, с кнопкой пропуска: `SkipLiveReplay` (Match.cs:1842), `SkipReplayButtonBehaviour`, `FastForwardCommand`, `Delorean.SkipToResults`.
- Отдельного проигрывателя записей сыгранных партий не нашёл.

**Async и таймеры.**
- Режимы Live и Async описаны в DATA/localization.txt, en_US: 2787, 2893, 2935, 2719, 2754.
  - Live: 3 минуты на ход. По таймауту ход делает ИИ, после двух таймаутов подряд игрока снимают.
  - Async: 3 дня на ход, затем игрока заменяет ИИ.
- Опции `isPBM`, `isPassAndPlay`, `Headless`, `IsOptimization`, `AIPlayers` (CS/Canis/canis/data/TCGameOptions.cs:8–23).
- Для async есть сообщения `PBMMatchFound`/`PBMTurnReady` и push `PushNotificationDeviceData`.
- Таймеры серверные (CS/Canis/canis/actions/timers/): банк времени хода (`AddPlayerTurnTime`, Padding, Reset) и таймеры одновременных выборов.
- Клиент получает `DisplayTimer{startedAt, endsAt}` и `ServerTimeSync`, из них считает `ServerTimeOffset`.
- Константы Unmatched: 90/60/30 (CS/duel-canis/duel/canis/data/enums/TimerLengths.cs:5–7).

**Сохранение посреди выбора.**
- `PendingSelection{Selection, ResponseParser, Continuation, Completion, CreateUndo}` (CS/Canis/canis/data/PendingSelection.cs) и параллельная иерархия `Serialized*` действий позволяют сериализовать стек исполнения.
- Поэтому матч можно выгрузить посреди вопроса и поднять из `SaveData` (CS/Canis/canis/SaveData.cs). На этом держатся Async и офлайн-сейвы.

**Скрытая информация** прячется на сервере, отдельно для каждого получателя:
- `ObfuscatedMessageActionFactory.CreateMsgs` выдаёт пары (сообщение, игрок);
- видимость задаётся на контейнер: `Visibility.Public/DeckStyle/HandStyle(owner)` (CS/Canis/canis/obfuscation/Visibility.cs:7–22);
- переход «скрыто → видно» превращается в `MaterializeEntity`, обратный — в `DematerializeEntity` (CS/Canis/canis/messages/EntityMovedObfuscator.cs:93–95);
- снапшот проходит то же правило (`SerializedGameStateObfuscator`).
- Есть наблюдатели: `JoinGameSessionAsObserver`, `SetAllowObservers`, кик.

### 2. Selection/Prompt-протокол

**Вопрос.** `SelectionMessage{PlayerAccountID, Counter, Prompt, OfferLength, Attributes}` с методом `Validate(response)` (CS/Networking/Networking/selection/messages/SelectionMessage.cs:10–15). `Prompt` — ключ локализации плюс переменные.

Виды вопросов:
- `SelectionWithTargetsRequired{TargetMap: EntityID→TargetInformation[], TargetPreferences, Forced, SelectionParams, SourceID}` (SelectionWithTargetsRequired.cs:32–42) — «что выбрать и какие цели у него по шагам»;
- `CustomChoiceRequired`;
- `IntChoiceRequired`;
- `EntityPermutationRequired`.

Шаги целей — подклассы `TargetInformation`: EntityList (`validTargets`, `numberToSelect`, `minimumToSelect`, `hintTargetMap`), X, Knapsack, Composite, Reveal, Grouping, hex/square-сетки с ориентацией. Подсказки задаёт `TargetStrength {Strong, Weak, Negative, Forced, Enhanced, Depleted, Super, CanAutoSelect}`.

**Ответ.** `SelectionWithTargets{gameID, selection{entityID, targetResponses[]}, counter}`; выбор закрывает `SelectionFinished`. Устаревшие ответы отсекаются по счётчику (`Match.HasPendingResponse`).

**Клиент.**
- Строит из вопроса дерево узлов: `RootSelection`, `SelectionWithTargetsNode`, с действиями Advance/Cancel (CS/core-canis/dwd/core/match/selection/).
- Шаги проходит локально, наружу отправляет один атомарный ответ.
- `SimultaneousSelection` задаёт вопросы обоим игрокам одновременно.

**ИИ.** `AIProfileAbs.MakeChoice → ISelectionCounter` (CS/Canis/canis/entities/ai/AIProfileAbs.cs:154) возвращает тот же тип ответа, что и человек.

**Перемещение клиент не считает.** `MoveResolution` сам строит путь через `FindShortestPath` (ISIL/duel-canis/duel/canis/actions/phase/MoveResolution.txt). Сборку `pathfinding` вызывает только duel-canis.

### 3. Клиентская презентация

**Конвейер.**
- Сокет → `GameMessageQueue` → `Delorean`. `Delorean` раздаёт сообщения по очередям `SequenceQueue` и `SelectionQueue`, у каждой есть флаг `Blocking` (CS/boardgames/dwd/core/match/delorean/).
- `SequenceParser` собирает из Start/StopSequence дерево `MatchSequence` с именем, атрибутами и детьми (CS/core-commands/dwd/core/match/sequence/).
- `SequenceCommandFactory` превращает узел в команду. Обработчики регистрируются атрибутами:
  - именованные последовательности — `[SequenceCommandConstructor("StartCombat")]`, а также RevealCombat, CombatDamage, Reveal, Teleport (CS/duel-client/duel/sequences/*.cs:46–53);
  - атомарные сообщения — `[MessageCommandConstructor]`: VoodooEntityMoved, AttributeModified, PlayFX (CS/boardgames/boardgames/voodoo/);
  - неизвестная последовательность сворачивается в общую.
- Команды — корутины: Serial, Parallel, Wait, Until, Interruptable (CS/core-commands/dwd/core/commands/).
- Вопрос, видимо, ждёт, пока доиграет блокирующая последовательность (`ISequenceBlockage`, `DeloreanRules`; средняя уверенность).
- Клиентскую модель `Entities` меняют сами команды по ходу показа.
- Журнал действий формирует сервер: `SerializedGameLog{logText — ключ и переменные, parent, undo}`. Он приходит событием `GameLogEffect` в том же потоке (CS/Canis/canis/gameLogs/).

**Анимация и меню.**
- В `core-animation` есть `BlockingAnimation`/`TriggeredBlockingAnimation`: команда ждёт события аниматора.
- У `PathAnimator` есть отдельные `OnUnblock` и `OnComplete`: конвейер может идти дальше раньше конца клипа.
- Есть регулятор скорости анимаций и SkipToResults.
- **`core-prompter` — это модальные окна меню** (ConfirmOrDeny, Choice, Spinner, ModalScope), а не вопросы матча.

### 4. dbg-client
- **Это не headless-клиент.** Это общий клиентский фреймворк DWD для цифровых настольных игр, около 780 файлов: меню, лобби, промпты, камера, ввод, всплывающие подсказки «moz», туториалы, офлайн-сейвы, чат и эмоции, отрисовка выбора (`DBGSelectionResponder`), команды `PlayCanisOnlineMatch`, `FastForwardCommand`, `ObserveMatch`.
- Признаки headless-режима лежат в Canis: опции `Headless`/`IsOptimization`, `StartAIvsAI`, `AIConstantsVector` — это прогоны ИИ против ИИ для подбора констант ИИ.
- Есть флаг `GameInit.isBatchMode` (CS/dbg-client/lotus/GameInit.cs:216), но самого раннера нет.

### 5. boardgames
- Общая база тайтлов DWD поверх Canis:
  - сеть (`CanisMatch`, `CanisNetworkState`);
  - voodoo — представления сущностей, стопки, раскладки, пути, kabbage (модули движения и VFX);
  - delorean;
  - атрибут-провайдеры (привязка данных);
  - аналитика, новости DireBytes, лобби-чат, Steam.
- Специфика Unmatched в duel-client — примерно 100 файлов: камера боя, `DuelCombatManager`, 5 последовательностей.

### 6. Локализация, контент, аналитика, платформа
- **Локализация.** Сервер шлёт `LocalizableText{id}` и `LocalizableTextVariables{id, textVars}`, клиент подставляет текст из таблиц key=value. В DATA/localization.txt 15 локалей: 7 по 2226 строк и 8 по 415.
- **Контент.**
  - Каталог Addressables ссылается только на `{Addressables.RuntimePath}`: 215 ссылок, 0 http (DATA/catalog_strings.txt). Значит, бандлы лежат локально.
  - CDN DWD используется для удалённых флагов switchboard (DATA/metadata_strings.txt:68319+).
  - Правила карт — C#-код duel-canis, общий для клиента и сервера.
  - Есть принудительное обновление клиента (localization.txt:2653).
- **Аналитика — собственная.** Событие с параметрами → JSON → base64 → HTTP пачками, офлайн-очередь в файле, метрики производительности (CS/boardgames/zen/analytics/), серверные события матча.
- **Платформа.**
  - Отдельный platform-WebSocket для друзей, присутствия, чата и приглашений (CS/platform/dwd/core/platform/websocket/).
  - Вход: Steam-тикет → токен DWD.
  - Покупки: IAP через Steam DLC с проверкой на сервере, `RequireOwnership` в `MatchInitData`.

### 7. Что применимо к нашему стеку (NestJS/GraphQL/Redis + UE5)

| Решение оригинала | У нас | Вердикт |
|---|---|---|
| Авторитетный сервер, клиент только показывает | то же: `filterPrivateData` (backend/src/games/game-state.service.ts:828), GraphQL WS | **оставить** |
| Упорядоченный поток display-событий с именованными последовательностями и реестр обработчиков | снапшот, следы в metadata (`lastMovement`, `lastCombat`), named CUE с потерями (docs/game-design/16-network-contract.md:89–96), стейджинги S09 | **брать, высокий приоритет**: движок пишет типизированный список событий за seq с проекцией на зрителя и кладёт его в пейлоад снапшота. В UE — реестр «имя → стейдж» поверх `FS08CueDispatcher`. Снапшот остаётся истиной |
| Хвост событий у каждого игрока для повтора | «Replay не обещается» (16-network-contract.md:46) | **брать, средний**: хвост в Redis рядом со state и выдача по `since`. Нужен для показа хода ИИ после реконнекта и для async |
| Сервер перечисляет цели и строит путь | клиент считает reach и path, паритет-тесты (unreal/…/S08/S08MoveParityTests.cpp), типизированные `pendingEffects` | **брать постепенно**: `validTargets`/`validDestinations` в проекции; клиентский расчёт оставить только для превью |
| Счётчик вопроса в ответе | `PendingEffect.id` и seq-guard | закрепить правило «ответ несёт id вопроса» |
| Синхронизация серверного времени + `endsAt` | `TimeoutAt` без поправки часов (S08Contracts.h:128) | **брать, дёшево** |
| ИИ доигрывает ход по таймауту, таймер всего хода | только таймауты боя 30/10 с, BullMQ | решение дизайна — вынести пользователю |
| Async с push-уведомлениями, наблюдатели | нет; наблюдатели запрещены GD-025 | позже; архитектура это позволяет |
| ack/resend/bundle/deflate | graphql-transport-ws и барьер `since` | не брать: барьер решает ту же задачу |
| Процесс на матч (GameLift), API Gateway, отдельный platform-WS | один NestJS + Redis pub/sub | не брать |
| Тот же движок в клиенте для офлайна | движок только в TS-бэкенде | не брать: это был бы второй движок |
| Своя аналитика, Addressables, switchboard | трейсы, pak, флаги отката | не сейчас |

### 8. Сетевая часть DuelEngine
В `duel-engine/docs/rules-diff.md:127` сказано, что сетевых решений в дампе нет. Это неверно, см. §1. Сеть DuelEngine — TCP и построчный JSON, один сервер на один матч (UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:14–22). С оригиналом она не совпадает, брать оттуда нечего.

--- keyFacts
[F1](high) Онлайн оригинала — авторитетный сервер, не lockstep: онлайн-клиент не создаёт Match, стартовый снапшот (SequenceMessage) кладёт в общий конвейер через SessionProvider.DispatchOfflineMessage, а свои ответы шлёт через CanisNetworkState.Write. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/Canis/boardgames/CanisOnlineMatch.cs; DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/boardgames/Canis/boardgames/CanisOnlineMatch.txt:131; DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/boardgames/Canis/boardgames/CanisOnlineMatch.txt:766}
[F2](medium) Один и тот же движок Canis работает в клиенте для офлайна (DBGCanisOfflineMatch.createMatch, CanisMatch.MessageDispatcher). Серверные обязанности Match (сейвы, push, удаление неактивного, очередь реконнекта, таймеры) говорят о том, что этот же код исполняет и сервер. Серверного бинаря в комплекте нет. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1458; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1497; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1512; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1514; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/dbg-client/boardgames/match/canis/DBGCanisOfflineMatch.cs}
[F3](medium) Транспорт — WebSocket + JSON. Лобби идёт через AWS API Gateway WebSocket (стадии Prod/QA, отдельные *Duel). Игровая сессия описана полями модели AWS GameLift (GameSessionId, IpAddress, DnsName, Port, PlayerSessionId), клиент подключается по шаблону ws(s)://{0}:{1}/{2}. {DuelEngine-transfer/test-targets/unmatched-data/metadata_strings.txt:287; DuelEngine-transfer/test-targets/unmatched-data/metadata_strings.txt:290; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/game/DWDGameSession.cs:13; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/dbg-client/boardgames/menus/OnlinePlaySessionProvider.cs:110}
[F4](high) Steam P2P и лобби Steam из игрового кода не вызываются. Steam нужен для тикета входа, статистики, оверлея, DLC и клавиатуры Steam Deck. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/platform/dwd/core/platform/auth/GetSteamPlatformToken.cs; DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/InAppPurchasing-Steam; DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/boardgames}
[F5](high) Надёжный канал: счётчик на каждом сообщении, AckMsg от клиента, повторная отправка неподтверждённых, буфер сообщений не по порядку, ping каждые 2 с, порог реконнекта 18 с, пачки MessageBundleMsg, сжатие deflate+base64, ReJoinGameSession с fastReconnect. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/match/CanisNetworkState.cs:155; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/match/CanisNetworkState.cs:156; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/match/CanisNetworkState.cs:186; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/match/CanisNetworkState.cs:302; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/match/EventDeserialization.cs:12; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/service/ReJoinGameSession.cs}
[F6](high) На каждого игрока сервер хранит lastState и хвост показанных событий displayActions (DispatchMessage дописывает, ClearDisplayActionsForPlayer сбрасывает при новом снапшоте). Клиент проигрывает хвост ускоренно, с кнопкой пропуска. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/PlayerSaveData.cs:32; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1963; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1991; DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/Canis/Canis/Match.txt; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/dbg-client/SkipReplayButtonBehaviour.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/dbg-client/boardgames/match/commands/FastForwardCommand.cs}
[F7](high) Скрытая информация прячется на сервере отдельно для каждого получателя. Видимость задаётся на контейнер (Public / DeckStyle / HandStyle(owner)). Переход из скрытого в видимое порождает MaterializeEntity, обратный — DematerializeEntity. Снапшот проходит то же правило. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/actions/ObfuscatedMessageActionFactory.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/obfuscation/Visibility.cs:7; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/messages/EntityMovedObfuscator.cs:93; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/messages/SerializedGameStateObfuscator.cs}
[F8](high) Протокол выбора. Вопрос: SelectionMessage{Counter, Prompt — ключ и переменные, OfferLength, Attributes}. Основной вид — SelectionWithTargetsRequired с TargetMap EntityID→TargetInformation[], подсказками TargetStrength и флагом Forced. Ответ — SelectionWithTargets{entityID, targetResponses[], counter}. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/selection/messages/SelectionMessage.cs:10; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/selection/messages/SelectionWithTargetsRequired.cs:32; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/selection/messages/outgoing/SelectionWithTargets.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/selection/TargetStrength.cs}
[F9](high) Клиент строит из вопроса дерево узлов (RootSelection/SelectionNode, Advance/Cancel) и отправляет один атомарный ответ через IAccountSessionWriter — одинаково в онлайне и офлайне. ИИ отвечает через AIProfileAbs.MakeChoice тем же типом ответа, что и человек. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-canis/dwd/core/match/selection/RootSelection`1.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-canis/dwd/core/match/selection/SimultaneousSelection.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/entities/ai/AIProfileAbs.cs:154}
[F10](medium) Путь перемещения строит сервер (MoveResolution вызывает FindShortestPath). Сборку pathfinding вызывает только duel-canis, клиентский UI правила перемещения не дублирует. {DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/MoveResolution.txt; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/pathfinding/pathfinding/ShortestPath.cs}
[F11](high) Презентация. Поток событий со скобками StartSequence/StopSequence собирается SequenceParser в дерево MatchSequence. SequenceCommandFactory превращает узлы в корутинные команды по реестру атрибутов [SequenceCommandConstructor("StartCombat"|"CombatDamage"|"RevealCombat"|"Reveal"|"Teleport")] и [MessageCommandConstructor]. Delorean раздаёт события по очередям Sequence и Selection с флагом блокировки. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-commands/dwd/core/match/sequence/SequenceParser.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-commands/dwd/core/SequenceCommandFactory.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-client/duel/sequences/DuelStartCombatSequence.cs:49; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/dwd/core/match/delorean/SequenceQueue.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/voodoo/VoodooEntityMovedCommand.cs}
[F12](high) Режимы Live (3 минуты на ход; по таймауту ход делает ИИ, после двух подряд игрока снимают) и Async (3 дня на ход, затем замена ИИ). Таймеры серверные, с банком времени, DisplayTimer{startedAt, endsAt} и ServerTimeSync. Константы Unmatched 90/60/30. {DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2719; DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2754; DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2893; DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2935; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/TimerLengths.cs:5; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/canis/messages/timer/DisplayTimer.cs}
[F13](high) Стек исполнения сериализуемый: PendingSelection хранит Continuation и ResponseParser, у действий есть иерархия Serialized*. Матч можно сохранить посреди вопроса и поднять из SaveData — на этом держатся Async и офлайн-сейвы. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/data/PendingSelection.cs:14; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/SaveData.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/actions/continuations/SerializedExecuteStack.cs}
[F14](high) dbg-client — не headless-клиент, а общий UI-фреймворк DWD для цифровых настольных игр (около 780 файлов). Признаки headless-режима лежат в Canis: опции Headless/IsOptimization, StartAIvsAI, AIConstantsVector. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/dbg-client; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/data/TCGameOptions.cs:8; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/ai_sim; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/dbg-client/lotus/GameInit.cs:216}
[F15](high) Сервер шлёт ключи локализации и переменные (LocalizableText, LocalizableTextVariables, журнал SerializedGameLog), клиент подставляет текст из таблиц key=value. Каталог Addressables только локальный (215 ссылок на RuntimePath, 0 http). {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Utils/Canis/utils/localization/LocalizableTextVariables.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/gameLogs/SerializedGameLog.cs; DuelEngine-transfer/test-targets/unmatched-data/localization.txt; DuelEngine-transfer/test-targets/unmatched-data/catalog_strings.txt}
[F16](high) Аналитика собственная: событие с параметрами → JSON → base64 → HTTP пачками, офлайн-очередь в файле, метрики производительности и памяти. Плюс серверные события матча. {DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/analytics/analytics/IAnalyticsMessage.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/zen/analytics/AnalyticsManager.cs; DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/zen/analytics/OfflineMessage.cs}
[F17](high) У нас: сервер авторитетный и шлёт полный снапшот с проекцией на зрителя; named CUE теряются; повтор пропущенных событий не обещается; UE-клиент дублирует расчёт reach и path с паритет-тестами; TimeoutAt без синхронизации часов. {backend/src/games/game-state.service.ts:828; docs/game-design/16-network-contract.md:46; docs/game-design/16-network-contract.md:89; unreal/Unmatched/Source/Unmatched/S08/S08MoveParityTests.cpp:1; unreal/Unmatched/Source/Unmatched/S08/S08Contracts.h:128}
[F18](high) Утверждение DuelEngine «в оригинале сетевых решений нет» неверно. Сеть DuelEngine — TCP и построчный JSON, один сервер на матч; с оригиналом она не совпадает. {DuelEngine-transfer/duel-engine/docs/rules-diff.md:127; DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:14}

--- open
Выполняет ли сервер DWD именно сборку Canis/duel-canis (.NET)? Серверного бинаря нет, вывод косвенный: серверные поля Match, ZLogger, роутеры сообщений.
Как константы TimerLengths (90/60/30 с) соотносятся с «3 минутами на ход» в Live? Возможно, это банк времени плюс добавки или серверный конфиг; не проверено.
Точный порядок блокировки в Delorean: ждёт ли SelectionQueue окончания SequenceQueue? Виртуальные вызовы в ISIL не разрешены, вывод сделан по полям blocker/Blocking.
Видит ли наблюдатель перспективу (руку) наблюдаемого игрока: observedPlayerID и строка про «игрока, за которым вы следили»? Не проверено.
Как клиент получает путь перемещения: пошаговыми EntityMoved или одним событием? Не проверено.
Доступен ли undo онлайн в Unmatched DE? Есть кнопка Undo и SendUndoAnalytics, но условия не проверены.
Решение для пользователя: нужны ли нам таймер всего хода с «ИИ доигрывает ход», async-режим и наблюдатели. Сейчас есть только таймауты боя 30/10 с, наблюдатели запрещены GD-025.
Решение для главной сессии: брать ли в работу поток display-событий с хвостом для каждого игрока и серверное перечисление целей (validTargets/validDestinations) вместо клиентского расчёта reach и path.