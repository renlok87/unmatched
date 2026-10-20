## Наш стек: карта для сравнения с оригиналом

### 0. Масштаб
- Бэкенд, игровая часть (`backend/src/game-engine`, `games`, `game`): около 25,3 тыс. строк кода без spec и около 33,3 тыс. строк spec. Одна только `game-engine/services/game-action-executor.service.ts` занимает 3172 строки (145 КБ).
- Клиент UE5 (`S08`+`S09`): около 172 тыс. строк, в том числе `S08/S08FlowGameMode.cpp` на 9284 строки (500 КБ) и `S08/S08FlowController.cpp` на 2798 строк.

### 1. Модель состояния и хранение
- Состояние — один неизменяемый документ `GameState` (`models/game-state.model.ts:40-65`): players, fighters, decks, discardPiles, handZones, boardState и большой `metadata` (`:324-378`). В `metadata` лежат combatInfo, combatResolutionProgress/Continuation (бой, поставленный на паузу), очередь `pendingEffects`, pendingManeuver, pendingHandDiscard, pendingTurnEnd, флаги текущего хода, heroStances, публичные записи `lastMovement`/`lastCombat`/`skippedEffects`.
- Источник истины — Postgres: таблица `GameState.state` (JSONB, одна строка на игру), сериализация в короткие ключи `v,g,s,p…` (`games/game-state.service.ts:50-160`). Redis служит кешем с TTL 600 с (`:172`). Запись из кеша принимается, только если `Game.version` совпадает с `sequenceNumber` (`:517-549`).
- Конкурентный доступ защищён двумя уровнями.
  - Redis-лок `game:${id}` (`common/services/distributed-lock.service.ts:197-213`; в резолвере ttl 10 с, retryCount 1 — `games/resolvers/game-actions.resolver.ts:270`).
  - Оптимистическая проверка в транзакции `saveState`: `existing.sequenceNumber === new-1` и условный `updateMany` по статусу IN_PROGRESS (`game-state.service.ts:189-247`). ELO и статистика начисляются в той же транзакции (`:244-246`).
- `sequenceNumber` получает ровно +1 за мутацию, даже если внутри неё сменился ход и сработали хуки (контракт описан в `docs/game-design/16-network-contract.md:7-20`).
- Таблицы `GameStateHistory`/`GameStateSnapshot` есть в схеме, но код их не использует (grep по `src` пуст).

### 2. Конвейер действия
GraphQL-мутация проходит такой путь (`game-actions.resolver.ts:154-281`):
1. Гарды: `GqlAuthGuard`, `GameInProgressGuard`, `GamePlayerGuard`, а также Phase/Combat-гарды.
2. Лок.
3. `loadState`.
4. `GameActionExecutorService.executeX`: валидация через `game-engine/validators/game-rules.validator.ts` и чистое вычисление нового состояния.
5. `saveState`: транзакция, затем кеш, затем публикация `STATE_UPDATED`.
6. Планирование дедлайнов боя в BullMQ.
7. Повторная публикация с конкретным eventType.
8. Запись в журнал `GameAction` через очередь BullMQ (best-effort).
9. Возврат отфильтрованного состояния строкой `JSON.stringify` (`:77-86`).
10. Fire-and-forget `aiTurnService.maybeRunAiTurns` (`:276`).

Рассылка: локальный PubSub плюс Redis broadcast между инстансами (`game-subscription.service.ts:158-182`). Каждая мутация публикует два события; `gameStateUpdated` пропускает только `STATE_UPDATED` (`game-subscription.resolver.ts:309-336`). При каждой доставке выполняется DB-проверка участия (`:180-187`). При подписке клиент сразу получает снапшот текущего состояния, без пропусков и дублей (`:208-303`).

Этот же конвейер (save, дедлайны, журнал, publish) продублирован ещё в двух местах: в ИИ (`games/services/ai-turn.service.ts:196-249`) и в таймауте (`combat-timeout.service.ts:360+`).

### 3. RNG, детерминизм, журнал, реплей
- Seed нет, везде используется `Math.random`:
  - тасовка при старте (`games/services/game-initialization.service.ts:48-55,247`);
  - `deck-management.service.ts:30-37` (shuffle), `:192` (случайный сброс);
  - `effects/card-effect-executor.service.ts:1380-1385` (тасовка после поиска), `:1446` (случайный буст из руки соперника).
- Первый игрок не случаен: это seat 0 (`game-initialization.service.ts:275,290`). Id экземпляров карт детерминированы (`${cardId}::n`, `:219-245`).
- Журнал `GameAction` хранит только имя мутации и входной DTO (`game-actions.resolver.ts:106-130`). Результатов и RNG в нём нет. Пишется он асинхронно через BullMQ и может теряться (`game-action.service.ts:18-48`, `processors/game-action.processor.ts`). `eventsSince` отдаёт этот журнал, а не состояние (`game-state.service.ts:1280-1340`).
- `ReplayService` (build/save в `GameReplay`) зарегистрирован, но нигде не вызывается (`games/services/replay.service.ts`, используется только в `games.module.ts:114,146`).
- **Вывод: воспроизвести партию по журналу нельзя.** Детерминизм есть только в тестах, которые подменяют `Math.random` на LCG (`games/services/s06-full-games.spec.ts:7,195-196`; `s09-card-instance-dup.spec.ts:251`).

### 4. Протокол выборов игрока
- Глобальная FIFO-очередь `metadata.pendingEffects` (`game-state.model.ts:385-456`). Типы: MOVE, PLACE, CHOOSE_ONE, TARGET_FIGHTER, DISCARD_CARDS, BOOST_CHOICE, CHOOSE_SPACE, DECK_TOP_PICK. Флаг `optional` разрешает отказ.
- Отдельные «ресурсные» выборы: `pendingManeuver` и `pendingHandDiscard`.
- Мутации `resolvePendingEffect`/`declinePendingEffect` (seq +1, действие не тратится).
- После каждого выбора `drainAfterChoice` либо продолжает бой, поставленный на паузу, либо выполняет отложенную передачу хода (`executor :230-251`, `:202-216`).
- Голова очереди без легальной цели снимается и записывается в `skippedEffects` (`effects/pending-targets.ts`).
- Бой на паузе сериализуется как continuation: стадия, оставшиеся эффекты, флаги отмены (`game-state.model.ts:144-153`, `card-effect-executor.service.ts:209-240`).
- Таймауты существуют только для боя: защита 30 с, ручной резолв 10 с (`game-state.model.ts:19-20`). Источник дедлайна — `combatInfo.timeoutAt`, после рестарта работает recovery sweep (`combat-timeout.service.ts:1-12,121`). Выборы внутри боя по дедлайну закрываются системой: decline для optional, иначе детерминированный fallback (первая опция, первая цель, первые N карт; `executor :897-979`, `combat-timeout.service.ts:525-588`).
- **Таймера хода и таймаута выборов вне боя нет** (grep по TURN_TIMEOUT/afk пуст).
- ИИ отвечает на те же вопросы теми же мутациями executor: смотрит голову очереди, чужой выбор не трогает, свой optional без пользы отклоняет (`ai-decision.service.ts:58-68,118+`).

### 5. Эффекты и способности
- Карты. `effect-text-parser.ts` (PARSER_VERSION 9, около 59 regex-матчеров) переводит английский текст полей effectImmediately/During/After в `CardEffect[]`. Нераспознанное становится `UNSUPPORTED` и попадает в `manualEffects`, то есть не исполняется (`:1-17`).
  - Разбор выполняется при backfill в БД и повторно при старте игры: `upgradeStaleParserEffects`, плюс fallback для SCHEME, ATTACK-during и DEFENSE-after (`game-initialization.service.ts:317-360`).
  - Бойцы привязываются к эффектам по имени из текста с нормализацией множественного числа (`effects/fighter-name.ts`).
  - Хрупко: точные `^…$`-шаблоны английских фраз, имена как строки. `effectBoost`/`effectOngoing` всегда UNSUPPORTED (`parser :9`).
  - Покрытие по 880 картам я не измерил: в backend нет `node_modules`, а парсер нужно запускать.
- Типы эффектов перечислены в `models/card.model.ts:170-234`; тайминги — ON_REVEAL, DURING, AFTER, ON_PLAY, TURN_START/END.
- Герои. Декларативный `ABILITY_CONFIGS` покрывает 26 слагов (`abilities/ability-config.ts:458+`; комментарий «пуст» на `:8` устарел). Ещё 3 героя реализованы вручную: arthur, daredevil, ms-marvel (`game-engine.module.ts:46,58,70,140-141`). Итого 29 из примерно 84 героев в БД.
  - `executeBlindBoost` (Daredevil) и `executeTurnStartMove` (Ms. Marvel) не подключены ни к одной мутации (grep пуст).
  - В Ms. Marvel зашита доска 6×6 (`heroes/ms-marvel.handler.ts:240-242`).
  - Medusa помечена «provisional» (`ability-config.ts:727-739`).
- Существуют три параллельных интерфейса обработчиков: `HeroAbilityHandler`, `ExtendedHeroAbilityHandler` и `IHeroAbilityHandler` (`hero-ability-registry.ts:70,155`, `hero-ability.interface.ts:55`). Тип CombatState продублирован (`registry:54` и модель).
- Не поддержано:
  - жетоны (`boardState.tokens` объявлено, но нигде не используется — `models/board.model.ts:18`);
  - ongoing/boost-тексты карт;
  - движение чужих бойцов способностями;
  - «random» у Achilles (вместо случайного сброса — детерминированный);
  - лимит руки Michelangelo;
  - большие фигуры (T. Rex);
  - Spider-Sense.

  Список приближений: `docs/backend-api/08-heroes-abilities.md:242-250`. Стойки (stances) есть: мутация `setStance`, `metadata.heroStances`.

### 6. ИИ
`ai-decision.service.ts`: чистая жадная эвристика без случайности.
- Если цель в досягаемости — атака героем лучшей картой, иначе манёвр в сторону ближайшего врага (BFS); защита лучшей картой (`:40-114`).
- Схем, буста и действий сайдкиков нет.
- Запускается после хода человека и при переподключении (`ai-turn.service.ts:176-193`, `game-subscription.resolver.ts:350`).

### 7. Тесты
- Бэкенд: 83 spec-файла в `games` и `game-engine` (1216 it/test; всего в `src` 108 файлов и 1391 кейс) плюс 7 e2e в `backend/test`.
- Прогон без внешних сервисов есть:
  - `s06-full-games.spec.ts` — два полных матча Medusa против Arthur через реальный executor с LCG. Но на синтетической Cobble City 5×6 (`docs/game-design/evidence/S01/content-board.json`), которая по правилам проекта выведена из оборота.
  - property-тест паритета движения на 500 состояний (`movement/move-parity.property.spec.ts`).
- Нужен живой Postgres/Redis: `s10-vs-ai-full-match.spec.ts` (без `S10_TEST_DB_URL` пропускается) и ещё 3 postgres-spec.
- Клиент: 96 test-файлов, 562 automation-теста.

### 8. Правила в нашей реализации
| Правило | Как сделано | Где |
|---|---|---|
| Действий за ход | Ровно 2 (манёвр, атака или схема), обязательные; pass запрещён; после второго ход завершается автоматически | `game-state.model.ts:462`; `executor :1666-1678, :2962-2970`; `validator :496-520` |
| Авто-добор в начале или конце хода | Нет («Turn transfer itself never draws») | `executor :312` |
| Добор при манёвре | Сначала добор 1 и списание действия (`beginManeuver`), затем по выбору буст и движение | `executor :1733-1758, :1783-1976` |
| Буст манёвра | Одна карта из руки, +boost к движению каждого бойца, карта уходит в сброс | `validator :318-345`; `executor :1898-1900` |
| Лимит руки | 7, проверка в конце хода, игрок сам выбирает сброс (`discardToLimit`); 7 зашито в код | `executor :285-294, :1761-1780` |
| Стартовая рука | 5 карт, без муллигана | `game-initialization :41,247-250` |
| Истощение | Каждый недобор наносит 2 урона каждому своему живому бойцу; сброс в колоду не замешивается | `deck-management :73-85` |
| Порядок боя | Атака: карта атаки и Arthur-буст лицом вниз. Затем ON_REVEAL («immediately»), потом DURING (SET → MODIFY → PER_COUNT), затем модификаторы героев/stateful/ауры, урон, AFTER. На каждой стадии первым ходит защитник. После карт: способность after-defense, затем after-attack, затем on-defeat | `card-effect-executor :180-203`; `executor :2572-2782` |
| Cancel | `CANCEL_EFFECTS` ставит флаг отмены карты соперника; у отменённой карты остаётся печатное значение, буст пропадает | `executor :2586-2605` |
| Победа в бою | `attackerWon = defenderDamage > 0`; урон наносит только атака; PREVENT обнуляет урон | `executor :2665-2671` |
| Победа в партии | Герой (HERO или HUGE) повержен — проигрыш; одновременная гибель — ничья (winnerId пуст) | `engine/terminal-state.ts:4-29` |
| Дальний бой | melee — только смежные (по линиям графа); ranged — смежные или общая зона (пересечение `Cell.zones`); плюс `canAttackAtRange` способностей | `executor :2047-2100`; `adjacency.service.ts:282-286` |
| Движение сквозь бойцов | Через союзника можно, через живого врага нельзя, конечная клетка свободна, павшие не мешают | `movement/traversal.ts:1-10` |
| Расстановка | Автоматическая на сервере, отдельной фазы SETUP нет | `game-initialization :144-194` |

Фазы SETUP, TURN_START и ACTION_ATTACK в боевом потоке не используются: весь ход проходит в ACTION_MANEUVER, а TURN_END возникает только при сбросе до лимита.

### 9. Клиент UE5
- Сеть:
  - HTTP GraphQL (`S08/S08GraphqlClient.h`);
  - graphql-transport-ws с подпиской только на `gameStateUpdated` (`S08/S08GraphqlWs.h`);
  - версия протокола 1 (`S08Protocol.h`).
- Модель приёма: полный снапшот для каждого зрителя. Поля состояния приходят JSON-строками и декодируются вторым этапом (`S08Contracts.h:73-92`).
- Seq-guard: меньший seq игнорируется, равный сливается, больший применяется (`S08FlowController.cpp:1685-1724`).
- Анимации строятся из **диффа соседних снапшотов** (local+1) плюс публичных записей `lastMovement`/`lastCombat`. На разрывах и барьер-снапшотах они подавляются.
  - Таймлайн боя: `S09/S09CombatStage.h`.
  - Диспетчер cue (дубли, устаревание, прерывания): `S08/S08CueDispatcher.h`.
  - Догоняющая политика hurry/cut: `S09/S09PresentationCatchup.h`.
- Выборы: `S09/S09PendingPresent.h` (модальное окно, тост или компактная панель, лента skippedEffects).
- Переподключение:
  - backoff от 1 до 15 с (`S08FlowController.cpp:1099-1110`);
  - повторная подписка с `since-1` (`:1155-1165`);
  - перезапрос `gameState` по HTTP;
  - защита от повторной отправки команды при потерянном ответе (`:1732+`).
- Клиент дублирует правила (достижимость, зоны, баннер) и сверяет их с сервером тестами паритета (`S08MoveParityTests.cpp`, `S08BoardModel.h:222`, `S09ManeuverUi.h:288`).

### 10. Слабые места и техдолг
1. Нет seed и журнала исходов, поэтому нет реплея и воспроизведения багов. `ReplayService` и таблицы истории мёртвые.
2. Одна мутация даёт один seq и один снапшот, атомарного потока событий нет. Клиент восстанавливает анимации диффами и вспомогательными записями (lastMovement, lastCombat, skippedEffects) — сложно и хрупко.
3. Эффекты карт держатся на regex-разборе английского текста, часть механик не исполняется. Способностями покрыто 29 из примерно 84 героев, есть неподключённые хендлеры.
4. Монолиты: executor на 3172 строки, `S08FlowGameMode.cpp` на 500 КБ. Конвейер commit/publish скопирован трижды.
5. Мёртвый код: `game/validators` (признан в `board-topology.guard.spec.ts:99-102`); `game/jobs/*.processor.ts` с TODO-заглушками; `GameJobsService`; `TurnManagementService`; `CombatResolverService.resolveCombat`; внедрены, но не вызываются `MovementService` и `ValueModifierService` (у последнего состояние в памяти процесса).
6. `GameStatePlayer.health` после старта не обновляется — дубль health бойца.
7. `playScheme` глотает ошибки эффектов (`executor :2417-2421`).
8. Нет таймера хода; выбор вне боя может повесить партию.
9. Весь снапшот, включая граф доски, отправляется при каждом обновлении. DB-проверка участия выполняется на каждую доставку.
10. `expectedSequenceNumber` есть только у `beginManeuver` (`games/dto/gameplay.dto.ts:98-108`). Остальные команды защищены id-токенами и экземплярами карт.
11. Полный матч без сервисов гоняется на выведенной Cobble City.

Сильные стороны: авторитарный сервер с чистым неизменяемым вычислением, строгая монотонность seq с двойной защитой от гонок, приватная проекция для каждого зрителя (`game-state.service.ts:828-947`), бой на паузе сериализуется и переживает рестарт, серверные дедлайны с recovery, большой набор тестов на контракты.

--- keyFacts
[O1](high) Состояние — один JSONB-документ в Postgres (GameState.state, одна строка на игру), Redis — кеш с TTL 600 с, сверяемый с Game.version {backend/src/games/game-state.service.ts:172;backend/src/games/game-state.service.ts:477-549;backend/prisma/schema.prisma (model GameState)}
[O2](high) Конкурентный доступ: Redis-лок game:${id} плюс оптимистическая проверка seq-1 и условный updateMany в транзакции saveState {backend/src/games/resolvers/game-actions.resolver.ts:162,270;backend/src/games/game-state.service.ts:189-247}
[O3](high) Одна мутация = +1 sequenceNumber и один полный снапшот для каждого зрителя; поток атомарных событий отсутствует {docs/game-design/16-network-contract.md:7-20;backend/src/game-engine/services/game-action-executor.service.ts:197-200}
[O4](high) Каждая мутация публикует два события (STATE_UPDATED из saveState и eventType из резолвера); клиент подписан только на gameStateUpdated {backend/src/games/game-state.service.ts:296;backend/src/games/resolvers/game-actions.resolver.ts:216;backend/src/games/resolvers/game-subscription.resolver.ts:309-336;unreal/Unmatched/Source/Unmatched/S08/S08GraphqlWs.h}
[O5](high) RNG без seed: Math.random в тасовке при старте, в shuffle/случайном сбросе колоды и в тасовке и случайном бусте эффектов карт {backend/src/games/services/game-initialization.service.ts:48-55,247;backend/src/game-engine/services/deck-management.service.ts:30-37,192;backend/src/game-engine/effects/card-effect-executor.service.ts:1380-1385,1446}
[O6](high) Журнал GameAction хранит только имя мутации и входной DTO, пишется асинхронно и best-effort через BullMQ; реплея нет, ReplayService не вызывается, таблицы GameStateHistory/Snapshot не используются {backend/src/games/resolvers/game-actions.resolver.ts:106-130;backend/src/games/services/game-action.service.ts:18-48;backend/src/games/services/replay.service.ts;backend/src/games/games.module.ts:114}
[O7](high) Детерминированный полный матч есть только в тесте с подменой Math.random на LCG, причём на выведенной доске Cobble City 5x6 {backend/src/games/services/s06-full-games.spec.ts:7,195-196;docs/game-design/evidence/S01/content-board.json}
[O8](high) Выборы игрока — глобальная FIFO-очередь metadata.pendingEffects из 8 типов с флагом optional; бой на паузе хранится как сериализуемый continuation; голова без легальной цели снимается в skippedEffects {backend/src/game-engine/models/game-state.model.ts:144-153,385-456;backend/src/game-engine/effects/card-effect-executor.service.ts:209-240;backend/src/game-engine/effects/pending-targets.ts}
[O9](high) Таймауты есть только у боя (защита 30 с, резолв 10 с, BullMQ плюс recovery sweep); выбор внутри боя закрывается детерминированным fallback; таймера хода и таймаута выборов вне боя нет {backend/src/game-engine/models/game-state.model.ts:19-20;backend/src/games/services/combat-timeout.service.ts:1-12,525-588;backend/src/game-engine/services/game-action-executor.service.ts:897-979}
[O10](high) Эффекты карт получаются regex-разбором английского текста (PARSER_VERSION 9, ~59 матчеров); нераспознанное становится UNSUPPORTED и не исполняется; boost/ongoing всегда UNSUPPORTED; разбор повторяется при старте игры {backend/src/game-engine/effects/effect-text-parser.ts:1-27,62-80;backend/src/games/services/game-initialization.service.ts:317-360}
[O11](high) Способности: 26 героев в декларативном ABILITY_CONFIGS плюс 3 вручную (arthur, daredevil, ms-marvel); Blind Boost Daredevil и движение Ms. Marvel в начале хода не подключены к мутациям {backend/src/game-engine/abilities/ability-config.ts:458;backend/src/game-engine/game-engine.module.ts:46,58,70,140-141;backend/src/game-engine/abilities/heroes/ms-marvel.handler.ts:240-242}
[O12](high) Жетоны не поддержаны (boardState.tokens нигде не используется); есть три параллельных интерфейса обработчиков способностей {backend/src/game-engine/models/board.model.ts:18;backend/src/game-engine/abilities/hero-ability-registry.ts:70,155;backend/src/game-engine/abilities/hero-ability.interface.ts:55}
[O13](high) Порядок боя: ON_REVEAL, DURING (SET, затем MODIFY, затем PER_COUNT), модификаторы героев/stateful/аур, урон только от атаки, AFTER; на каждой стадии первым защитник; хуки способностей after-defense/after-attack/on-defeat — после эффектов карт {backend/src/game-engine/effects/card-effect-executor.service.ts:180-203;backend/src/game-engine/services/game-action-executor.service.ts:2572-2782}
[O14](high) Победа в бою: attackerWon = defenderDamage > 0; победа в партии — гибель героя, одновременная гибель даёт ничью {backend/src/game-engine/services/game-action-executor.service.ts:2665-2671;backend/src/game-engine/engine/terminal-state.ts:4-29}
[O15](high) Ход: 2 обязательных действия, pass запрещён; авто-добора в начале или конце хода нет; манёвр сначала добирает 1 карту (beginManeuver), потом буст ко всем бойцам и движение; лимит руки 7 проверяется в конце хода с выбором сброса {backend/src/game-engine/models/game-state.model.ts:462;backend/src/game-engine/services/game-action-executor.service.ts:285-312,1733-1780,2962-2970;backend/src/game-engine/validators/game-rules.validator.ts:318-345,496-520}
[O16](high) Истощение: каждый недобор наносит 2 урона каждому своему живому бойцу, сброс не замешивается; стартовая рука 5 {backend/src/game-engine/services/deck-management.service.ts:73-85;backend/src/games/services/game-initialization.service.ts:41-42}
[O17](high) Дальний бой: смежная цель или пересечение зон клеток; melee — только смежная по линиям графа; движение через союзников разрешено, через живых врагов нет, конечная клетка свободна {backend/src/game-engine/services/game-action-executor.service.ts:2047-2100;backend/src/game-engine/engine/adjacency.service.ts:282-286;backend/src/game-engine/movement/traversal.ts:1-10;backend/src/game-engine/engine/board-topology.ts:1-25}
[O18](high) ИИ — жадная эвристика без случайности, работает только героем, без схем и буста; использует те же мутации executor и тот же протокол выборов {backend/src/game-engine/services/ai-decision.service.ts:10-17,40-114;backend/src/games/services/ai-turn.service.ts:176-249}
[O19](high) Клиент UE5 применяет полные снапшоты через seq-guard и строит анимации из диффа соседних снапшотов плюс записей lastMovement/lastCombat; на разрывах и барьерах cue подавляются; есть политика догоняния и диспетчер cue {unreal/Unmatched/Source/Unmatched/S08/S08FlowController.cpp:1685-1724;unreal/Unmatched/Source/Unmatched/S09/S09CombatStage.h;unreal/Unmatched/Source/Unmatched/S09/S09PresentationCatchup.h;unreal/Unmatched/Source/Unmatched/S08/S08CueDispatcher.h}
[O20](high) Переподключение клиента: backoff 1-15 с, повторная подписка с since-1 (сервер шлёт барьер-снапшот), перезапрос gameState, защита от повторной отправки команды при потерянном ответе {unreal/Unmatched/Source/Unmatched/S08/S08FlowController.cpp:1099-1110,1155-1165,1732-1760;backend/src/games/resolvers/game-subscription.resolver.ts:208-303}
[O21](medium) Клиент дублирует правила движения, зон и баннеров и сверяет их с сервером тестами паритета {unreal/Unmatched/Source/Unmatched/S08/S08MoveParityTests.cpp;unreal/Unmatched/Source/Unmatched/S08/S08BoardModel.h:222;unreal/Unmatched/Source/Unmatched/S09/S09ManeuverUi.h:288}
[O22](high) Мёртвый код: game/validators, заглушки game/jobs, TurnManagementService, CombatResolverService.resolveCombat; MovementService и ValueModifierService внедрены, но не вызываются {backend/src/game-engine/engine/board-topology.guard.spec.ts:99-102;backend/src/game/jobs/combat.processor.ts:24-33;backend/src/game/jobs/game-state-persist.processor.ts;backend/src/game-engine/game-engine.module.ts:86}
[O23](medium) Тесты: в games и game-engine 83 spec-файла и 1216 кейсов (в backend/src всего 108 файлов и 1391 кейс), плюс 7 e2e; у клиента 562 automation-теста в 96 файлах; полный матч VS_AI требует живого Postgres {backend/src (find *.spec.ts);backend/test;backend/src/games/s10-vs-ai-full-match.spec.ts:1-14,37-39}
[O24](high) Конвейер commit/publish скопирован в резолвере, ИИ и таймауте; executor на 3172 строки и S08FlowGameMode.cpp на 9284 строки — монолиты {backend/src/games/resolvers/game-actions.resolver.ts:154-281;backend/src/games/services/ai-turn.service.ts:196-249;backend/src/games/services/combat-timeout.service.ts:360;unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp}
[O25](medium) GameStatePlayer.health после инициализации не обновляется (дубль health бойца); playScheme глотает ошибки эффектов {backend/src/game-engine/engine/terminal-state.ts:9-15;backend/src/game-engine/services/game-action-executor.service.ts:2417-2421}
[O26](high) Первый игрок — всегда seat 0; расстановка бойцов автоматическая на сервере, фазы SETUP с выбором игрока нет {backend/src/games/services/game-initialization.service.ts:144-194,275,290}

--- open
Покрытие effect-text-parser по ~880 картам не измерено: в backend нет node_modules, а запуск backfill-card-effects --dry-run требует Node/ts-node и БД. Нужна цифра «сколько карт целиком распознано»
Совпадает ли наше правило победы в бою (attackerWon = defenderDamage > 0, PREVENT_DAMAGE отдаёт победу защитнику) с логикой оригинала? Это стоит проверить по декомпиляции
Ничья при одновременной гибели героев (winnerId пуст): как это решает оригинал — победа активного игрока или ничья?
Порядок способностей героев относительно эффектов карт: у нас хуки after-combat срабатывают после всех AFTER-эффектов карт, а не в общей очереди с приоритетом защитника. Как в оригинале?
Выбор первого игрока и расстановка сайдкиков: у нас seat 0 и автоматическая расстановка. В оригинале это выбор игрока или случайность?
Число героев в живой БД (~84 по условию задачи) не проверено: docker остановлен, scraped-data/api/heroes содержит 88 записей вместе с наборами
Насколько клиенту реально мешает восстановление анимаций из диффов снапшотов (по трейсам S08), и окупится ли переход на поток атомарных событий в ответе мутации или подписки?