# R4 — Движок и механики Unmatched (справочник для UE-клиента)

> Ридер: R4-engine-mechanics. Дата: 2026-09-02.
> Источники: `docs/backend-api/05-engine-and-content.md` (часть A), `docs/backend-api/10-mechanics-deep-dive.md`; точечная сверка с кодом `backend/src/**` (ссылки вида `файл:строка` — от корня репозитория). Всё, чего нет в источниках, помечено «не найдено».
> Формат ссылок: `05:NN` = `docs/backend-api/05-engine-and-content.md` строка NN; `10:NN` = `docs/backend-api/10-mechanics-deep-dive.md` строка NN; `04:NN` = `docs/backend-api/04-game-api.md`; прочие — путь к файлу кода.

---

## 1. Краткое резюме

Бэкенд — единственный источник истины по правилам: иммутабельный `GameState` мутируется только через `GameActionExecutorService` по схеме «валидация → выполнение → `ActionResult`», и каждая успешная мутация даёт ровно **+1 к `sequenceNumber`** (05:30-32). Ход = **ровно 2 действия** (`ACTIONS_PER_TURN = 2`: манёвр / атака / scheme / pass / moveFighter в любой комбинации), после второго — **автоматическая передача хода** без отдельного инкремента seq (05:33; 10:27-29). Формально есть 8 фаз `GamePhase`, но в продакшен-потоке используются только **`ACTION_MANEUVER` → `COMBAT` → `COMBAT_RESOLVE` → `ACTION_MANEUVER`/следующий ход → `GAME_OVER`** (`TURN_START`/`TURN_END`/`SETUP` пропускаются, `ACTION_ATTACK` — legacy-синоним action-фазы) (10:12-23).

Ключевые механики: 4-связная сетка, манхэттеновская смежность `=== 1`, BFS-достижимость с блокировкой чужими бойцами (10:78-81, 99); melee — только смежная цель, ranged — смежная или **та же зона по legacy-полю `Cell.zone`** (первая зона клетки, не пересечение `zones[]`) (`backend/src/game-engine/engine/adjacency.service.ts:214-218`); дальность расширяют способности/стойки (`canAttackAtRange`, только добавляет) (10:118). Бой: атака списывает действие в момент объявления, защитнику даётся окно **30 с** (BullMQ auto-resolve), затем 6-шаговый пайплайн `ON_REVEAL → DURING_COMBAT → 4 слоя модификаторов героев (аддитивно) → урон (ничья = защитник) → AFTER_COMBAT → итоги/хуки/game-over` (10:138-176). Эффекты карт, требующие выбора (MOVE/PLACE/CHOOSE_ONE), становятся `PendingEffect` и **не блокируют игру**; резолвятся мутацией `resolvePendingEffect` бесплатно и протухают при возврате хода владельцу (10:240-271). Стойки (`heroStances`, `setStance`, бесплатно), ауры (Oda), 26 data-driven героев в `ABILITY_CONFIGS` + 3 ручных хендлера (05:303). Колода: рука 5 на старте, максимум 7, добор 1 в начале хода и 1 после манёвра, сброс перетасовывается под колоду при опустошении (10:279-286). VS_AI-бот — greedy-эвристика, исполняется на сервере сразу после мутации человека (10:292-299).

Критичные для UE-клиента выводы: клиент **ничего не считает сам «по правилам» как истину** — он лишь подсвечивает кандидатов (по тем же алгоритмам: BFS, смежность, `zone`) и отправляет мутацию, а сервер отвечает отказом `BadRequestException` либо новым состоянием. Клиент обязан уметь: (1) показывать таймер 30 с локально (поле `timeoutAt` в `combatInfo` **никогда не заполняется** — не найдено ни одной записи в коде); (2) рендерить сброс/колоды не из подписки `gameStateUpdated` (в её payload **нет** `decks`/`discardPiles`), а из ответа мутации или `query gameState`; (3) не полагаться на «двери», «туман», «возвышенность» (мертвые/не реализованные механики); (4) учитывать, что при пустых `Board.cells` в БД игра идёт на **fallback-сетке 20×20 без зон** (`backend/src/games/services/game-initialization.service.ts:282-289`).

---

## 2. Факты по темам

### 2.1. Архитектура движка и контракт мутаций

| Факт | Источник |
|---|---|
| Движок в `backend/src/game-engine`: `models/`, `engine/` (бой, движение, смежность, модификаторы), `effects/` (исполнитель эффектов карт), `abilities/` (реестр + `ABILITY_CONFIGS`), `services/` (оркестратор `GameActionExecutorService`, колоды, ход, AI), `movement/` (A*, кэш путей), `validators/` (`GameRulesValidator`), `cache/` | 05:16-26 |
| `GameState` и вложенные структуры `readonly`; любое действие возвращает новое состояние (structural sharing) | 05:30 |
| Единая точка входа — `GameActionExecutorService` (~2000 строк): валидация → выполнение → `ActionResult` | 05:31; `backend/src/game-engine/services/game-action-executor.service.ts` (2000 строк) |
| Контракт `sequenceNumber`: **ровно +1 за одну мутацию**; вложенные хуки (способности, on-move реакции, auto-advance хода) seq отдельно не бампят | 05:32; 10:29 |
| Сигнатура действия: `(dto, context: { userId, gameId, currentState }) => Promise<ActionResult>`; `ActionResult = { success, gameState?, error?, metadata: { action, performedAt, performedBy, sequenceNumber, effectText?, appliedEffects?, manualEffects?, combatSummary? } }` | 05:147 |
| Ответ GraphQL-мутации — `GameMutationResult { state: String (JSON полного отфильтрованного GameState), sequenceNumber, timestamp, phase, currentTurnPlayerId, turnCount }`. `metadata.effectText/appliedEffects/manualEffects/combatSummary` из `ActionResult` **наружу через GraphQL не отдаются** (в `createMutationResult` только перечисленные поля) | `backend/src/games/dto/gameplay.dto.ts:437-455`; `backend/src/games/resolvers/game-actions.resolver.ts:72-80` |
| Обёртка `executeMutation`: distributed-lock `game:{gameId}` (ttl 10 с, 1 retry) → `loadState` → executor → `saveState` → планирование/отмена auto-resolve → `publishGameUpdate(eventType)` → журнал `GameAction` → при `GAME_OVER` дополнительно событие `GAME_ENDED` → `filterPrivateData` → ответ; после — fire-and-forget `AiTurnService.maybeRunAiTurns` | `backend/src/games/resolvers/game-actions.resolver.ts:140-236` |
| Ошибка валидации → `BadRequestException` с текстом `error` из `ActionResult` (`errors[0].message` в GraphQL) | `backend/src/games/resolvers/game-actions.resolver.ts:129-135`; 04:550 |
| Guards на мутациях: `GqlAuthGuard` (JWT), `GameInProgressGuard`, `GamePlayerGuard`, затем фазовый: `ActionPhaseGuard` = `ACTION_MANEUVER|ACTION_ATTACK` + «твой ход»; `DefensePlayGuard` = фаза `COMBAT` + `combatInfo.defenderId === userId` (атакующий не может); `CombatResolveGuard` = `COMBAT|COMBAT_RESOLVE` + участник боя (атакующий или защитник) | `backend/src/games/guards/game-turn.guard.ts:136-143, 160-221, 230-283` |
| Rate-limit мутаций (`@Throttle`): maneuver/moveFighter/resolvePendingEffect/endTurn/toggleDoor/setStance — 30/мин; attack/playDefense/playScheme/resolveCombat/pass — 20/мин | `backend/src/games/resolvers/game-actions.resolver.ts:257, 283, 310, 337, 363, 392, 413, 439, 464, 487, 517` |

### 2.2. Фазы и машина состояний

`enum GamePhase` (`backend/src/game-engine/models/game-state.model.ts:15-24`):

| Фаза | Реальная роль в продакшен-потоке | Источник |
|---|---|---|
| `SETUP` | Только при создании состояния (`GameStateService.createInitialState`); `GameInitializationService` сразу ставит `ACTION_MANEUVER` | 10:16; `backend/src/games/services/game-initialization.service.ts:242-244` |
| `TURN_START` | **Исключена**: ход начинается сразу с `ACTION_MANEUVER` + добор 1 карты; turn-start-хуки встроены в `advanceTurn` | 10:17; 05:34 |
| `ACTION_MANEUVER` | Единственная «рабочая» action-фаза: манёвр, атака, scheme, pass, moveFighter, toggleDoor, setStance, endTurn | 10:18; 10:120 |
| `ACTION_ATTACK` | Legacy старых сейвов; валидна для всех тех же действий (guard'ы/валидаторы принимают обе) | 10:19; `backend/src/game-engine/validators/game-rules.validator.ts:309-315` |
| `COMBAT` | Ставится `executeAttack` — «окно защиты»; ждёт `playDefense`, `resolveCombat` или таймаут 30 с | 10:20; `…executor.service.ts:1105` |
| `COMBAT_RESOLVE` | Ставится `executePlayDefense` (и auto-resolve по таймауту); здесь ожидается `resolveCombat` | 10:21; `…executor.service.ts:1234`; `backend/src/games/services/combat-timeout.service.ts:265` |
| `TURN_END` | Промежуточная legacy-фаза; `advanceTurn` сразу ставит `ACTION_MANEUVER` следующему; `validateEndTurn` её принимает | 10:22; `…validator.ts:476-480` |
| `GAME_OVER` | Ставится `checkAndApplyGameOver`; `metadata.winnerId` заполнен, `combatInfo` очищен | 10:23; `…executor.service.ts:657-671` |

Фактический граф переходов (по коду):

```
[init] → ACTION_MANEUVER
ACTION_MANEUVER --maneuver/moveFighter/playScheme/pass (осталось >0)--> ACTION_MANEUVER (seq+1)
ACTION_MANEUVER --maneuver/moveFighter/playScheme/pass (осталось 0)--> advanceTurn → ACTION_MANEUVER (другой игрок, тот же seq+1)
ACTION_MANEUVER --endTurn--> advanceTurn → ACTION_MANEUVER (другой игрок)
ACTION_MANEUVER --attack--> COMBAT (действие списано сразу)
COMBAT --playDefense (защитник)--> COMBAT_RESOLVE
COMBAT --30 с без защиты--> COMBAT_RESOLVE (auto-resolve: только смена фазы, defenseValue 0, урон НЕ применён)
COMBAT | COMBAT_RESOLVE --resolveCombat (любой участник)--> ACTION_MANEUVER (если у атакующего остались действия) | advanceTurn | GAME_OVER
ACTION_MANEUVER --toggleDoor/setStance/resolvePendingEffect--> ACTION_MANEUVER (действие не тратится, seq+1)
любая точка проверки game-over --> GAME_OVER
```
Источники: 05:161-171; 10:63-65; `…executor.service.ts:1637-1668`; `backend/src/games/services/combat-timeout.service.ts:260-282`.

### 2.3. Экономика действий

| Факт | Источник |
|---|---|
| `ACTIONS_PER_TURN = 2`; атаковать можно дважды за ход | `backend/src/game-engine/models/game-state.model.ts:161-165`; 10:27 |
| Остаток — `metadata.actionsRemaining`; чтение `getActionsRemaining(state)`: мусор (null/NaN/отрицательное/строка) → 2 | `…game-state.model.ts:172-175`; 10:28 |
| `consumeAction`: списывает 1; при остатке ≤ 0 → `advanceTurn(…, incrementSeq=false)` (авто-завершение хода в той же мутации) | `…executor.service.ts:680-690`; 10:29 |
| Атака списывает действие **в момент объявления**: `actionsRemaining = max(0, remaining − 1)` (не через `consumeAction`, ход не завершается) | `…executor.service.ts:1117`; 10:37 |
| После резолва боя: `getActionsRemaining > 0` → фаза `ACTION_MANEUVER` (ход атакующего продолжается), иначе `advanceTurn`. `GAIN_ACTION`/`END_TURN` из after-эффектов карт меняют остаток до этой проверки | `…executor.service.ts:1651-1668`; 10:65 |
| `GAIN_ACTION` (эффект карты): `actionsRemaining += value || 1`; `END_TURN`: `actionsRemaining = 0` | `backend/src/game-engine/effects/card-effect-executor.service.ts:538-555` |
| `gainAction` из способностей героев (Bloody Mary, Raphael): `actionsRemaining += N` | `backend/src/game-engine/abilities/generic-hero-ability.handler.ts:900-908` |

Что тратит действие (10:31-44, сверено с кодом):

| Мутация | Тратит действие | Примечание | Код |
|---|---|---|---|
| `maneuver` | да (`consumeAction`) | двигает всех своих бойцов, BOOST каждому, добор 1 | `…executor.service.ts:864` |
| `moveFighter` | да | через `movementService.executeMovement` | `…executor.service.ts:948` |
| `attack` | да, при объявлении | `max(0, remaining−1)` | `…executor.service.ts:1117` |
| `playScheme` | да | карта всегда в сброс | `…executor.service.ts:1360` |
| `pass` | да | **не сбрасывает никакой карты** (TODO в коде), только `passCount + 1` | `…executor.service.ts:1791-1803` |
| `endTurn` | нет — передаёт ход | валидна из `ACTION_MANEUVER`/`ACTION_ATTACK`/`TURN_END` | `…validator.ts:471-490` |
| `toggleDoor` | **нет** | бесплатно; в текущих данных всегда `DOOR_NOT_FOUND` (см. 2.6.6) | `…executor.service.ts:1827-1893` |
| `setStance` | **нет** | бесплатно, seq+1 | `…executor.service.ts:1898-1960` |
| `resolvePendingEffect` | **нет** | эффект уже оплачен картой, seq+1 | `…executor.service.ts:432-437` |
| `playDefense` | нет | действие не активного игрока | 10:44 |

### 2.4. Передача хода — `advanceTurn` (точный порядок)

Приватный метод executor'а (`…executor.service.ts:168-262`; 10:46-59):

1. `triggerHeroTurnEnd` — extended-хук `onTurnEnd` героя **завершающего** игрока (до снятия turn-эффектов и до смены `currentTurnPlayerId`).
2. Следующий живой игрок по кругу `(idx+1) % players.length`, пропуск `!isAlive`, максимум `players.length` попыток. Если следующий == текущий — `turnCount` не растёт, иначе `+1`.
3. **Добор 1 карты** следующему игроку (`deckManagement.drawCards`); ошибки (legacy без колоды) не блокируют.
4. Снятие эффектов `duration: 'turn'` со всех бойцов (например `immobilized`).
5. Снапшот `metadata.turnStartPositions` (для условия `MOVED_THIS_TURN`).
6. `actionsRemaining = 2`; `maneuveredThisTurn/attackedThisTurn/lostCombatThisTurn = false`.
7. Чистка `pendingEffects`: удаляются только те, у кого `playerId === nextPlayerId` (протухание при **возврате** хода владельцу, а не при любой передаче — иначе pending от атаки вторым действием стирался бы до резолва).
8. `triggerHeroTurnStart` — extended-хук `onTurnStart` нового игрока.
9. `checkAndApplyGameOver` (turn-start-способность могла добить).
10. Фаза `ACTION_MANEUVER`, `sequenceNumber + 1` (если `incrementSeq`).

Legacy `TurnManagementService` (`turn_actions/turn_passed/turn_additional`, `DEFAULT_ACTIONS_PER_TURN = 2`) в продакшен-потоке executor'ом **не используется** (10:61; grep по `games/` и executor — ссылок нет).

### 2.5. Модели данных и что реально видит клиент

#### 2.5.1. `GameState` и `metadata`

`GameState { gameId, sequenceNumber, phase, turnCount, currentTurnPlayerId, players[], fighters[], decks: Record<userId, DeckState>, discardPiles: Record<userId, Card[]>, handZones: Record<userId, HandZone>, boardState, metadata }` (05:40-55; `…game-state.model.ts:30-55`).

`GameStatePlayer { userId, heroId, health, maxHealth, fighterIds[], isAlive }` (`…game-state.model.ts:60-67`).

`GameStateMetadata` (`…game-state.model.ts:90-125`; 05:60-68):

| Поле | Назначение |
|---|---|
| `lastActionAt`, `lastActionBy`, `version` | служебные |
| `combatInfo?: CombatState` | текущий бой между `attack` и `resolveCombat` |
| `passCount?` | счётчик pass |
| `winnerId?` | победитель при `GAME_OVER` |
| `actionsRemaining?` | остаток действий (дефолт 2) |
| `turnStartPositions?: Record<fighterId, {x,y}>` | позиции на начало хода — `MOVED_THIS_TURN` |
| `pendingEffects?: PendingEffect[]` | отложенные выборы игрока |
| `maneuveredThisTurn?`, `attackedThisTurn?`, `lostCombatThisTurn?` | per-turn флаги активного игрока для условий способностей |
| `heroStances?: Record<userId, stanceId>` | текущая стойка героя каждого игрока; при инициализации **не заполняется** (handler фолбэчит на `default: true` / первую) |

Инициализация: `sequenceNumber: 1`, `phase: ACTION_MANEUVER`, `turnCount: 1`, первым ходит хост (seatOrder 0), `metadata = { lastActionAt, lastActionBy: 'system', version: 1, actionsRemaining: 2 }` (`backend/src/games/services/game-initialization.service.ts:240-256`).

#### 2.5.2. `CombatState` (`metadata.combatInfo`)

`{ attackerId (fighter id), defenderId (userId владельца цели), targetFighterId? (боец-цель; legacy-фолбэк — первый боец защитника), attackerCardId (instance id), defenderCardId?, attackValue, defenseValue, startedAt, timeoutAt? }` (`…game-state.model.ts:73-85`).

**`timeoutAt` никогда не пишется** — ни `executeAttack` (пишет `startedAt` только: `…executor.service.ts:1093-1101`), ни таймаут-сервис; grep по `backend/src` находит поле только в модели/сериализации/DTO. Пример в 04:411-413 с `timeoutAt` — иллюстративный.

Внимание: GraphQL-тип `CombatState` в `gameplay.dto.ts:416-431` (`attackerId, targetId, attackCardId, defenseCardId, timeoutAt`) — **другой** контракт, чем `metadata.combatInfo` в JSON состояния; в игровых ответах используется JSON-форма из модели движка.

#### 2.5.3. `Fighter`

`{ id, ownerId, heroId, name, type: HERO|MINION|HUGE, health, maxHealth, position {x,y}, effects: FighterEffect[] ({ type, duration?: 'permanent'|'turn'|'round', source? }), hasSidekick, sidekickIds?, isDefeated?, movement?, attackType?: 'melee'|'ranged', heroSlug? }` (05:74-89; `backend/src/game-engine/models/fighter.model.ts:27-56`).

- `DEFAULT_FIGHTER_MOVEMENT = 2`; `getFighterMovement(f)` — единственная точка чтения, мусор → 2 (`…fighter.model.ts:65-73`; 10:73-74).
- `normalizeAttackType`: БД хранит `'range'`, движок — `'ranged'`; любой мусор → `'melee'`; `getFighterAttackType(f)` (`…fighter.model.ts:96-105`).
- `slugifyHeroName('Ms. Marvel') → 'ms-marvel'` — единственная нормализация слага; `heroSlug` проставляется на game-init (05:92, 282; `…game-initialization.service.ts:144`).
- Ид бойцов на старте: герой `f-{seat}-hero`, сайдкики `f-{seat}-sk{i}` (`…game-initialization.service.ts:140, 154`).
- Сайдкики: тип MINION, hp/движение из БД с дефолтами (hp 1, движение 2), размещение по `SIDEKICK_OFFSETS = [(1,0),(0,1),(1,1),(−1,0),(0,−1)]` от героя с клампом в границы (`…game-initialization.service.ts:49-55, 146-168`; 10:217).

#### 2.5.4. `Card` / `CardEffect`

- `enum CardType { ATTACK, DEFENSE, SCHEME, UNIVERSAL (legacy), VERSATILE, MANEUVER }`; VERSATILE играется и как атака, и как защита (`backend/src/game-engine/models/card.model.ts:10-19`; 05:97-98).
- `Card { id: instance id вида "${cardId}::n", cardId (cuid), name/nameEn/nameRu, cardType, attackValue?/defenseValue?/boostValue?, effects?: CardEffect[], text?, bannerName? ('Any' | имя бойца) }` (05:100-109).
- `HandCard = Card + isVisible`; `DeckState { cards (полный список), drawPile, topCard = drawPile[0] }`; `HandZone { cards, maxSize }` (`…card.model.ts:282-300`; 10:281).
- `CardEffect`: `type: EffectType` (MODIFY_ATTACK, MODIFY_DEFENSE, DAMAGE, HEAL, MOVE, PLACE, DRAW_CARD, DISCARD, MODIFY_VALUE, SET_VALUE, VALUE_PER_COUNT, BOOST, CANCEL_EFFECTS, OPPONENT_DISCARD, RETURN_TO_HAND, IMMOBILIZE, GAIN_ACTION, PREVENT_DAMAGE, END_TURN, CHOOSE_ONE, UNSUPPORTED); `timing: EffectTiming` (BEFORE_COMBAT, DURING_COMBAT, AFTER_COMBAT, ON_PLAY, ON_DISCARD, TURN_START, TURN_END, ON_REVEAL); `target: EffectTarget` (ATTACKER, DEFENDER, SELF, ALL_ENEMIES, ALL_ALLIES, OPPOSING_FIGHTER, ENEMIES_ADJACENT_TO_SELF, ADJACENT_ENEMY, NAMED_FIGHTER, OPPONENT_PLAYER); `when: EffectCondition`; `count: CountSpec`; `boostSource: PLAYER_CHOICE_HAND | SELF_DECK_TOP | OPPONENT_RANDOM_HAND`; `options + chooseCount` для CHOOSE_ONE (05:112-120; `…card.model.ts:153-221`).
- `normalizeCardEffects(raw, cardId)` никогда не бросает: мусор → массив или один UNSUPPORTED (05:122).

#### 2.5.5. `BoardState` / `Cell`

`BoardState { width, height, cells[y][x], doors: Record<'x:y', boolean>, fog: Record<'x:y', boolean>, tokens }`; `Cell { type: 'normal'|'wall'|'obstacle'|'door'|'zone-line', x, y, zone? (legacy = первая зона), zones?: string[] (1–2 зоны), isOpen?, isHighGround? }`; `getCellZones(cell)` — `zones` → фолбэк `[zone]` → `[]` (`backend/src/game-engine/models/board.model.ts:12-45`; 05:126-143). `cellKey(x,y) = "x:y"` (`…board.model.ts:110-112`).

#### 2.5.6. Что реально приходит клиенту (важно для UE)

| Канал | Содержимое | Источник |
|---|---|---|
| Ответ любой игровой мутации `GameMutationResult.state` | `JSON.stringify(filterPrivateData(state, userId))` — **полный** GameState, включая `decks` и `discardPiles` | `backend/src/games/resolvers/game-actions.resolver.ts:72-80, 216-220` |
| `query gameState(gameId)` → `GameStateResponse { id, gameId, state: JSON, sequenceNumber, currentTurnPlayerId, phase, turnCount, updatedAt }` | тот же полный JSON | `backend/src/games/game.resolver.ts:63-87` |
| `subscription gameStateUpdated(gameId, since)` → `GameState { gameId, sequenceNumber, phase, turnCount, currentTurnPlayerId, players: JSON, fighters: JSON, handZones: JSON, boardState: JSON, metadata: JSON }` — **без `decks` и `discardPiles`** | `backend/src/games/resolvers/game-subscription.resolver.ts:44-63`; `backend/src/games/dto/gameplay.dto.ts:461-491` |
| Событийные подписки `attackInitiated/defensePlayed/combatResolved/gameEnded/playerJoined/playerLeft` → `GameEvent { type, gameId, sequenceNumber, timestamp, payload: JSON {phase, turnCount, currentTurnPlayerId} }` — без состояния | `…game-subscription.resolver.ts:66-97` |
| `subscription turnChanged` → `TurnState { playerId, turnCount, phase }`; срабатывает на `TURN_ENDED`/`TURN_CHANGED` (т.е. только на явный `endTurn`, **не** на авто-передачу хода после 2-го действия) | `…game-subscription.resolver.ts:246-261`; `gameplay.dto.ts:380-389`; 04:564 |
| `filterPrivateData`: чужая рука — карты с `name:'???', nameEn:'Hidden', nameRu:'Скрыто', isVisible:false`, без `attackValue/defenseValue/boostValue/effects/text` (но `id`, `cardId`, `cardType`, `bannerName` остаются); у чужой колоды удалён только `topCard` (**`drawPile` чужой колоды в JSON остаётся**); `discardPiles` не фильтруются (в Unmatched сброс открыт) | `backend/src/games/game-state.service.ts:494-541`; 04:427-432 |
| `saveState` публикует внутренний `STATE_UPDATED` → ровно один `gameStateUpdated` на мутацию | `backend/src/games/game-state.service.ts:215`; 04:570 |

### 2.6. Движение

#### 2.6.1. Геометрия

| Факт | Источник |
|---|---|
| Соседство — **4-связность** (N/S/E/W), шаг стоит 1; диагонали есть в API (`includeDiagonal`, стоимость 1.5), но по умолчанию выключены и валидаторами не используются | `backend/src/game-engine/engine/adjacency.service.ts:35-49, 75`; 10:80-81 |
| `isAdjacent` = манхэттен `=== 1` (диагональ не смежна) | `…adjacency.service.ts:201-204`; 10:115 |
| Непроходимость `isCellBlocked`: `wall`, `obstacle`, `door` при `!isOpen` | `…adjacency.service.ts:146-150`; 10:79 |
| BFS `getReachableCells(board, start, maxCost, { blockedPositions })`: возвращает Map `"x:y" → {position, cost}` без стартовой клетки; клетки из `blockedPositions` (занятые живыми бойцами) непроходимы и не расширяются | `…adjacency.service.ts:90-141`; 10:81 |
| `isInSameZone(a,b)`: `cells[a.y][a.x].zone === cells[b.y][b.x].zone`, оба non-null — **читает legacy `zone` (первая зона клетки), а не пересечение `zones[]`** | `…adjacency.service.ts:214-218`; 10:117 |
| Очки движения: `getFighterMovement(f)` (дефолт 2). Герой — `Hero.movement` из БД (Prisma default 2); контентный `HeroDto.movement` **захардкожен 3** — для игры использовать `Fighter.movement` из состояния | `…game-initialization.service.ts:185`; 05:396; 10:73 |

#### 2.6.2. Манёвр — `mutation maneuver(input: ManeuverDto)`

DTO (`backend/src/games/dto/gameplay.dto.ts:82-137`): `{ gameId, moves?: [{ fighterId, path: [{x,y}] }], boostCardId?, fighterId? (legacy), path? (legacy), cardId? (legacy = boost) }`. `PositionInput.x/y` — `@Min(0) @Max(19)`.

Правила (05:173-179; 10:83-95; сверено с кодом):

1. Двигаются **все свои бойцы** через `moves[]`; каждый боец не более одного раза (`uniqueFighters`) (`…executor.service.ts:770-774`).
2. Ходы применяются последовательно; валидация каждого — на состоянии после предыдущего (`…executor.service.ts:776-812`).
3. `validateManeuver`: боец свой, жив, не `immobilized` (`FIGHTER_IMMOBILIZED`), фаза action, boost-карта в руке (`CARD_NOT_IN_HAND`), путь непустой (`EMPTY_PATH`), каждая клетка пути в границах и не `wall/obstacle` (`INVALID_POSITION`), `path.length ≤ movement + boostValue` (`NOT_ENOUGH_MOVEMENT`), каждый шаг — манхэттен 1 от предыдущей (`INVALID_STEP`) (`…validator.ts:278-372`).
4. Конечная клетка не занята живым бойцом («Клетка (x, y) занята»); **промежуточные клетки проверяются только на wall/obstacle** — занятость промежуточных клеток и закрытые двери (`door` + `!isOpen`) в манёвре **не проверяются** (`…validator.ts:235-249`; `…executor.service.ts:800-812`). См. противоречие с 10:93 в §4.
5. Единый +1 к seq за весь манёвр → реактивные on-move хуки (`applyMoveReactions`) → BOOST-карта в сброс → **добор 1 карты** → `maneuveredThisTurn = true` → `consumeAction` (`…executor.service.ts:815-864`).
6. Манёвр без карты валиден (чистые «добор 1 + движение»); BOOST добавляет `boostValue` **каждому** движимому бойцу (`gameplay.dto.ts:107-109, 117-118`; 10:87).
7. Путь — это список клеток **после** старта (стартовая не включается): проверка первого шага идёт от `fighter.position` (`…validator.ts:356-366`).

#### 2.6.3. Простое перемещение — `mutation moveFighter(input: MoveFighterDto)`

DTO `{ gameId, fighterId, x, y }` (`gameplay.dto.ts:143-164`). Цель должна быть **BFS-достижима** за `getFighterMovement(fighter)` шагов (занятые живыми бойцами клетки — `blockedPositions`, закрытые двери — блок); перемещение в свою клетку — no-op с валидным ответом; `immobilized` запрещает; `executeMovement` дополнительно проверяет занятость цели, делает +1 seq; затем on-move реакции и `consumeAction` (`…validator.ts:374-438`; `backend/src/game-engine/engine/movement.service.ts:176-235`; `…executor.service.ts:895-960`; 10:97-101). BOOST здесь не поддержан, добора карты нет.

#### 2.6.4. Отложенные перемещения (MOVE/PLACE)

См. §2.10: дистанция `pending.value ?? 1`, BFS по проходимым клеткам с блокировкой чужими живыми бойцами; PLACE — любая свободная проходимая клетка (10:103-105, 262-267).

#### 2.6.5. Доска и размещение на старте

| Факт | Источник |
|---|---|
| `BoardState` собирается из `Board.cells` БД: плоский массив `[{x, y, isObstacle?, zones?: string[]}]` в grid-координатах; `zones` → `zones[]` и `zone = zones[0]`; `isObstacle` → `'obstacle'`; дыры → `normal`; **`doors: {}`, `fog: {}`, `tokens: {}` всегда** | `…game-initialization.service.ts:270-349` |
| Невалидность (нет доски, `cells=[]`, кривой JSON, пиксельные координаты, размер вне 2..50) → fallback `createEmptyBoardState(20, 20)` (все клетки normal, без зон) | `…game-initialization.service.ts:43-46, 279-315`; `…board.model.ts:82-105`; 10:190 |
| Комментарий кода: «Штатная ситуация для текущих данных (у всех досок cells=[])» → в текущей БД игра идёт на **пустой сетке 20×20**; ranged деградирует до смежности | `…game-initialization.service.ts:282-289` |
| Стартовые позиции по seatOrder: `(2,2)`, `(w−3,h−3)`, `(w−3,2)`, `(2,h−3)` с клампом; если занято/непроходимо — ближайшая свободная по манхэттен-скану | `…game-initialization.service.ts:366-423` |
| Единственный статический борд: **Cobble City 6×4**, 5 зон (blue/green/yellow/purple/red), мультизонные клетки (1,1) blue+green, (3,1) green+yellow, (1,2) purple+red; все клетки проходимы, дверей/тумана нет; `getDefaultBoardId() = 'cobble-city'` | 10:200-213; `backend/src/content/data/boards/cobble-city.ts:14-53` |
| Карта зон Cobble City (y\x): y0: blue blue green green yellow yellow; y1: blue blue+green green green+yellow yellow yellow; y2: purple purple+red red red red red; y3: purple purple red red red red | 10:206-211 |

#### 2.6.6. Двери — `mutation toggleDoor(input: { gameId, x, y })`

`validateToggleDoor`: ход игрока, action-фаза, ключ `"x:y"` **существует** в `boardState.doors` (`DOOR_NOT_FOUND`); эффект — инверсия `doors['x:y']`, seq+1, действие не тратится; комментарий кода — «специальная способность Bjorn» (`…validator.ts:519-556`; `…executor.service.ts:1827-1893`; 10:192-194). Поскольку `doors` всегда `{}` и клетки типа `door` нигде не создаются (grep по `content/`, `games/`, `game-engine/` — 0 совпадений вне модели/сервисов проверки), **мутация в текущих данных всегда отклоняется**. Также состояние `isOpen` клетки и `doors['x:y']` — две несвязанные структуры: BFS читает `cell.isOpen`, а toggle меняет `doors` (`…adjacency.service.ts:148`; `…executor.service.ts:1849-1860`).

#### 2.6.7. Туман и возвышенность

- `fog: Record<'x:y', boolean>` — только хранение/транспорт (ключ `fg` в компактной сериализации); **игровой логики, читающей fog, нет**; инициализация `{}` (10:196-198; `backend/src/games/game-state.service.ts:139`).
- `isHighGround` — в движке **не используется** (10:189; grep по `game-engine/` и `games/` вне модели — 0 совпадений). Утверждение 04:548 «бонус возвышенности ±1» кодом не подтверждается.

### 2.7. Атака и окно защиты

#### 2.7.1. `mutation attack(input: AttackDto)`

DTO `{ gameId, attackerId (fighter id), cardId (instance id или базовый cardId), targetId (fighter id), boostCardId? }` (`gameplay.dto.ts:170-196`).

Валидация `validateAttackWithParams` (`…validator.ts:135-217`; 10:120): `canPlayerAct` (твой ход + `isAlive`), атакующий/цель существуют, атакующий свой (`NOT_YOUR_FIGHTER`), фаза `ACTION_MANEUVER|ACTION_ATTACK` (`INVALID_PHASE`), оба живы (`ATTACKER_DEAD`/`TARGET_DEAD`), карта в руке (`CARD_NOT_IN_HAND`), тип `ATTACK|VERSATILE|UNIVERSAL` (`INVALID_CARD_TYPE`), `validateBanner` (`BANNER_MISMATCH`).

Геометрия достижения (`…executor.service.ts:1008-1058`; 10:111-118):

1. `adjacent = manhattan(attacker, target) === 1`.
2. `melee` (дефолт): достижима **только если смежна**.
3. `ranged`: смежна **или** `isInSameZone` (legacy `zone` обоих клеток совпадает и не null). На 20×20 fallback — только смежность.
4. Если не достигнута — `abilityRegistry.canAttackAtRange(slug, attackerId, targetId, manhattanRange, heroStances[attacker.ownerId])`; хук **только добавляет** разрешение. Generic: `effectiveRange = stance.attackRange ?? config.attackRange`, `true ⟺ range ≤ effectiveRange` (`backend/src/game-engine/abilities/generic-hero-ability.handler.ts:635-645`). Ms. Marvel — ручной хендлер, `range ≤ 2` (`backend/src/game-engine/abilities/heroes/ms-marvel.handler.ts:22, 72-75`). Примеры из конфигов: T-Rex 2, Bullseye 5, Muhammad Ali FLOAT 2 (`backend/src/game-engine/abilities/ability-config.ts:510, 722, 890`).
5. Ошибки: `'Melee attack: target must be adjacent to attacker'` / `'Ranged attack: target must be adjacent or in the same zone as attacker'`.

Эффект: карта атаки (и boost-карта) уходят в сброс **сразу**; `combatInfo = { attackerId, defenderId: target.ownerId, targetFighterId: target.id, attackerCardId: instance id, attackValue: card.attackValue + boost.boostValue, defenseValue: 0, startedAt }`; фаза `COMBAT`; действие списано; seq+1 (`…executor.service.ts:1086-1120`; 10:124-127). **Атака по сайдкику бьёт именно сайдкика** (10:126).

#### 2.7.2. BOOST (все три контекста)

- `boostAllowed(playedCard, fighter, role)`: истинно, если у играемой карты есть эффект `BOOST` с `boostSource === 'PLAYER_CHOICE_HAND'` или `null`, **или** хендлер героя имеет `allowsAttackBoost`/`allowsDefenseBoost` (King Arthur: `heroId: 'king-arthur'`, `allowsAttackBoost: true`) (`…executor.service.ts:136-154`; `backend/src/game-engine/abilities/heroes/arthur.handler.ts:22-30`; 05:183).
- Нельзя бустить той же картой (`'Нельзя BOOST-ить атаку/защиту той же картой'`); boost-карта должна быть в руке (`'Boost card not in hand'`) (`…executor.service.ts:1066-1084, 1202-1217`).
- Манёвр: BOOST разрешён любой картой из руки без ограничений (`validateManeuver` читает только `boostValue`) (`…validator.ts:320-330`).
- Авто-источники в бою (`DURING_COMBAT`, эффект `BOOST`): `SELF_DECK_TOP` — «blind boost», сброс верха своей колоды + его `boostValue` (Daredevil); `OPPONENT_RANDOM_HAND` — противник сбрасывает случайную карту, + её `boostValue`; `PLAYER_CHOICE_HAND` в executor'е эффектов — no-op (выбор через `boostCardId` мутации) (`backend/src/game-engine/effects/card-effect-executor.service.ts:475-486`; 10:180).
- Ручной хендлер Daredevil (`executeBlindBoost`, `isBlindBoostAvailable`) в продакшен-потоке **не вызывается**: grep по `game-engine/services`, `effects`, `games` — совпадений нет; blind boost работает через парсер текста карт → `BOOST/SELF_DECK_TOP` (`backend/src/game-engine/effects/effect-text-parser.ts:181, 462`).

#### 2.7.3. Защита — `mutation playDefense(input: { gameId, cardId, boostCardId? })`

`DefensePlayGuard` + `executePlayDefense` (`…executor.service.ts:1150-1260`; 10:131-132): фаза `COMBAT` (`'Not in combat phase'`), `combatInfo.defenderId === userId` (`'Only defender can play defense'`), карта в руке типа `DEFENSE|VERSATILE|UNIVERSAL` (`…validator.ts:440-466`), banner против **атакованного бойца** (`targetFighterId`, фолбэк — первый боец защитника), BOOST по тем же правилам (`allowsDefenseBoost`). Обе карты в сброс; `defenseValue = card.defenseValue + boost.boostValue`; `defenderCardId` = instance id; фаза `COMBAT_RESOLVE`; seq+1. Защита без карты не предусмотрена — если защитник не хочет/не может играть, кто-то из участников вызывает `resolveCombat` (defenseValue 0).

#### 2.7.4. Таймер auto-resolve

| Факт | Источник |
|---|---|
| При `attack` резолвер планирует BullMQ-задачу `auto-resolve` в очереди `combat-timeout` с задержкой **30 с** (жёстко `30` в вызове; константа `DEFAULT_DEFENSE_TIMEOUT = 30`; есть `DEFAULT_RESOLVE_TIMEOUT = 10`, нигде не применяется), jobId `combat:scheduled:{gameId}`, `attackSequenceNumber = seq после атаки` | `backend/src/games/resolvers/game-actions.resolver.ts:173-178`; `backend/src/games/services/combat-timeout.service.ts:59, 64, 90-128` |
| `playDefense` и `resolveCombat` отменяют задачу (`cancelAutoResolve`) | `…game-actions.resolver.ts:179-182` |
| Processor под locком `game:{gameId}`: если фаза всё ещё `COMBAT` и `sequenceNumber` не ушёл вперёд — `performAutoResolve`: **только** `phase = COMBAT_RESOLVE`, seq+1, `lastActionBy = currentTurnPlayerId`; урон **не применяется** (TODO в коде); состояние сохраняется через `saveState` → уходит `gameStateUpdated` | `…combat-timeout.service.ts:199-282`; `backend/src/games/processors/combat-timeout.processor.ts:34-64` |
| После таймаута бой висит в `COMBAT_RESOLVE` до вызова `resolveCombat` любым участником (защита 0) | следствие из `CombatResolveGuard` (`…game-turn.guard.ts:230-283`) и `executeResolveCombat` (фаза `COMBAT|COMBAT_RESOLVE`) |
| `getTimeUntilResolve(gameId)` существует в сервисе, но **не выставлен** в GraphQL (не найдено в резолверах) | `…combat-timeout.service.ts:171-193` |

#### 2.7.5. Banner-мэтчинг (`bannerAllows`)

`Harpy` = `Harpy 2` (срез числового суффикса); `Arthur` = слово в `King Arthur`; множественное число: `harpies → harpy`, `wolves → wolf`, `dogs → dog`; регистронезависимо; `'Any'`/пусто — разрешено всем; банер, не матчащий никого в игре, — warn + разрешить (`…validator.ts:559-604`; 10:134). Для scheme: нужен живой свой боец, подходящий под банер (`…executor.service.ts:1309-1322`).

### 2.8. Пайплайн резолва боя — `mutation resolveCombat(input: { gameId })`

Вход: фаза `COMBAT` или `COMBAT_RESOLVE`; вызвать может атакующий **или** защитник (`CombatResolveGuard`) — в том числе атакующий в фазе `COMBAT` до того, как защитник сыграл карту (проверки таймаута в guard'е **нет**, несмотря на комментарий «после истечения таймаута») (`…game-turn.guard.ts:225-283`; `…executor.service.ts:1403`).

Карты боя ищутся «где угодно» по instance id: руки → сбросы → полные списки колод (`findCardAnywhere`) (`…executor.service.ts:1430-1433, 1985`; 05:221).

| Шаг | Что происходит | Источник |
|---|---|---|
| 1. ON_REVEAL | `executeRevealEffects`: эффекты `timing: ON_REVEAL` сначала атакующего, затем защитника. `CANCEL_EFFECTS` на карте атакующего → `defenderCardCancelled = true` (и наоборот); отменённая карта не исполняет reveal/during/after-эффекты, **печатное значение сохраняется**; отменённый защитник не отменяет в ответ | 10:142-143; `…executor.service.ts:1447-1456` |
| 2. DURING_COMBAT | `executeCombatEffects` для не-отменённых карт в порядке `SET_VALUE → MODIFY_VALUE/MODIFY_ATTACK/MODIFY_DEFENSE → VALUE_PER_COUNT → прочее`. `SET_VALUE` заменяет (последний выигрывает), MODIFY — дельта, `VALUE_PER_COUNT = count × per` (счётчики `CARDS_IN_HAND`, `FRIENDLY_ADJACENT_TO_OPPONENT`, `DISCARD_NAME_PREFIX`, `DAMAGE_DEALT`, `DAMAGE_TAKEN`); `PREVENT_DAMAGE` гасит урон стороне. Итог: `calc.finalAttack/finalDefense` | 10:145-146; `…executor.service.ts:1459-1465` |
| 3. Модификаторы героев (4 слоя, аддитивно) | `finalAttack = calc.finalAttack + heroMods.attackModifier + statefulAttack + auraAttack`; `finalDefense = calc.finalDefense + heroMods.defenseModifier + statefulDefense + auraDefense`. **heroMods** — классический `applyCombatModifier` (суммируются только `ADD`); **stateful** — `getStatefulCombatModifiers` с доступом к `GameState` (видит `attackedThisTurn` **до** установки: первая атака — false, вторая — true); **aura** — `getAuraCombatModifiers` по всем handler'ам. Отрицательные итоги не зажимаются в executor-пайплайне (зажим `max(0, …)` есть только в legacy `CombatResolverService.resolveCombat`) | 10:148-157; `…executor.service.ts:1469-1513` |
| 4. Урон | `finalAttack > finalDefense` → `defenderDamage = finalAttack − finalDefense` (если не `preventDamageToDefender`); `finalDefense > finalAttack` → `attackerDamage = finalDefense − finalAttack` (если не `preventDamageToAttacker`); **равенство — победа защитника, урона нет**; `health = max(0, health − damage)`; `attackerWon = finalAttack > finalDefense` | 10:159-164; `…executor.service.ts:1517-1536` |
| 5. AFTER_COMBAT | `executeAfterCombatEffects`: сначала **все** эффекты атакующего, затем защитника; контекст `{ attackerWon, attackerDamage, defenderDamage }` → условия `WON_COMBAT`, `LOST_COMBAT`, `IS_ATTACKING/DEFENDING`, `DECK_EMPTY`, `HAND_COUNT_AT_MOST/AT_LEAST`, `HEALTH_AT_MOST`, `ADJACENT_TO_OPPONENT` (+NOT), `SHARES_ZONE_WITH_OPPONENT` (+NOT, по мультизонам), `MOVED_THIS_TURN` (vs `turnStartPositions`), `OPPONENT_IS_HERO` | 10:166-167; `…executor.service.ts:1539-1546` |
| 6. Итоги | `health <= 0 && !isDefeated` → `isDefeated = true` (вычисляются **ново-павшие**); `player.isAlive = есть боец с health > 0` (смерть сайдкика игрока не убивает); флаги: `firstLossThisTurn = !attackerWon && !lostCombatThisTurn` (до установки), затем `attackedThisTurn = true`, `lostCombatThisTurn ||= !attackerWon` | 10:169-173; `…executor.service.ts:1561-1601` |
| 7. Хуки | `onAfterCombat` атакующего → `onAfterCombat` защитника (defender-side, тот же `AfterCombatContext = { playerId, defenderPlayerId, attackerFighterId, defenderFighterId, won, damageDealt, firstLossThisTurn }`) → `onFighterDefeated` героя **владельца** каждого ново-павшего | 10:174; 05:213-215, 268-269; `…executor.service.ts:1603-1629` |
| 8. Game-over | `checkAndApplyGameOver`: живых ≤ 1 → `GAME_OVER`, `winnerId = alivePlayers[0]?.userId` (0 живых → undefined), `combatInfo = undefined` | 10:175; `…executor.service.ts:657-671` |
| 9. Продолжение | не окончена: `combatInfo = undefined`; `actionsRemaining > 0` → `ACTION_MANEUVER` (seq+1), иначе `advanceTurn` (seq+1 внутри). Остаток/следующий игрок считаются от `currentTurnPlayerId` (атакующего), даже если мутацию вызвал защитник | 10:176; `…executor.service.ts:1637-1668` |

`metadata.combatSummary` в `ActionResult`: `{ finalAttack, finalDefense, attackerDamage, defenderDamage, attackerWon, attackerCardCancelled, defenderCardCancelled }` — **не экспортируется** в `GameMutationResult` (см. 2.1) (`…executor.service.ts:1680-1690`; 05:221).

Числовой пример (по формулам выше): атака 5 (карта 4 + boost 1) + Alice в стойке BIG (+2 attack) = 7; защита 3 + Luke Cage (+2 defense) = 5 → защитнику 2 урона. При 5 vs 5 — урона нет, атакующий проиграл (`lostCombatThisTurn = true`).

### 2.9. Эффекты карт (`CardEffectExecutorService`)

| Факт | Источник |
|---|---|
| Точки исполнения: `executeRevealEffects` (ON_REVEAL + cancel), `executeCombatEffects` (DURING_COMBAT → `{ state, finalAttack, finalDefense, appliedEffects, manualEffects, preventDamageTo* }`), `executeAfterCombatEffects` (AFTER_COMBAT), `executeOnPlayEffects` (scheme, best-effort), `executeChosenEffects` (опция CHOOSE_ONE) | 05:229-233 |
| Каждый вызов возвращает `appliedEffects` (авто) и `manualEffects` (MOVE/PLACE/UNSUPPORTED — требуют ручного применения); `UNSUPPORTED` не исполняется, игра не блокируется | 05:114, 235; 10:180 |
| Scheme: `executePlayScheme` принимает только `cardType === SCHEME` (VERSATILE — нет), banner — нужен живой боец; эффекты best-effort («в БД effects почти всегда пустые»); карта всегда в сброс; `effectText = card.text ?? card.name` — клиенту через GraphQL **не приходит** | `…executor.service.ts:1286-1392`; 05:232 |
| `IMMOBILIZE` → `fighter.effects += { type: 'immobilized', duration: 'turn', source }`; снимается в `advanceTurn`; запрещает манёвр/moveFighter | `…card-effect-executor.service.ts:560-580`; `…validator.ts:300-305, 395-400` |
| `GAIN_ACTION` / `END_TURN` — см. 2.3 | `…card-effect-executor.service.ts:538-555` |
| `ADJACENT_ENEMY` с несколькими кандидатами → первый + warn (MVP) | `…card-effect-executor.service.ts:863-883`; 10:180 |
| Полный список боевых эффектов и целей | 10:180 |

### 2.10. Отложенные эффекты — `PendingEffect`

Модель (`…game-state.model.ts:132-159`; 10:244-252):

```ts
{ id, type: 'MOVE'|'PLACE'|'CHOOSE_ONE', playerId, value? (шаги MOVE), fighterName? («Move Daredevil…»),
  targetsOpponent? («Place the opposing fighter…»), text? (исходный текст для лога),
  // CHOOSE_ONE:
  options?: [{ index, label }], chooseCount? (default 1), optionEffects?: CardEffect[][], card? }
```

Порождение (`…card-effect-executor.service.ts:588-645`; 10:254-256): `MOVE/PLACE` → `{ id: "${effect.id}-p${n}", type, playerId, value: value || undefined, fighterName: effect.fighterName, targetsOpponent: target === OPPOSING_FIGHTER, text }`; `CHOOSE_ONE` → `{ id, type, playerId, chooseCount: effect.chooseCount ?? 1, options: [{index, label}], optionEffects, card, text }`; без распознанных опций — сразу в `manualEffects`. Игру **не блокируют**. Способности героев (Robin Hood, Leonardo, Bruce Lee) порождают `MOVE`-pending той же формы: `id: "ability-{heroId}-move-p{n}"`, `value: maxSpaces`, `fighterName` = имя атакующего (`target: 'attacker'`) / героя (`'own-hero'`) / отсутствует (`'any-own'`), `targetsOpponent: false`, `text: "{abilityName} — move"` (`…generic-hero-ability.handler.ts:826-875`).

Резолв — `mutation resolvePendingEffect(input: ResolvePendingEffectDto)` = `{ gameId, effectId, fighterId?, x?, y?, optionIndex? }` (`gameplay.dto.ts:244-277`); guard'ы: только auth/in-progress/participant (**без** `ActionPhaseGuard` — можно резолвить не в свой ход и в любой фазе) (`…game-actions.resolver.ts:383-407`). Логика (`…executor.service.ts:432-640`; 10:258-271):

| Тип | Обязательные поля | Проверки | Эффект |
|---|---|---|---|
| MOVE | `fighterId, x, y` | pending существует и `playerId === userId`; боец жив; владелец: свой (или чужой при `targetsOpponent`); `bannerAllows(fighterName, fighter)`; клетка в границах, не `obstacle/wall`, не занята живым; цель BFS-достижима за `value ?? 1` шагов (чужие живые — `blockedPositions`) | телепорт бойца, pending удаляется, on-move реакции, пере-проверка game-over; seq+1; действие не тратится |
| PLACE | `fighterId, x, y` | те же, кроме BFS — любая валидная свободная клетка (зонные ограничения — TODO) | то же |
| CHOOSE_ONE | `optionIndex` (0..len−1) | валидный индекс | `executeChosenEffects` выбранной опции (вне боя; боевые эффекты → manual); при `chooseCount > 1` pending остаётся с `chooseCount − 1` и опциями без выбранной (индексы перенумеровываются); вложенные MOVE/PLACE из опции создают новые pending |

Тексты ошибок: `'Отложенный эффект не найден (протух или уже резолвлен)'`, `'Этот выбор принадлежит другому игроку'`, `'MOVE/PLACE требует fighterId, x, y'`, `'Боец не найден или повержен'`, `'Эффект двигает не этого бойца'`, `'Эффект двигает только «…»'`, `'Клетка вне доски'`, `'Клетка непроходима'`, `'Клетка занята'`, `'До клетки (x, y) не добраться за N шаг(ов)'`, `'Нужен валидный optionIndex (0..N)'`.

Протухание: в `advanceTurn` удаляются pending с `playerId === nextPlayerId` (при возврате хода владельцу) (`…executor.service.ts:250-256`; 10:271). Пример последствий: атака вторым действием создала pending → ход ушёл сопернику → pending жив весь ход соперника, стирается в начале следующего хода владельца.

### 2.11. Способности героев: интерфейсы, реестр, конфиги

#### 2.11.1. Хуки `ExtendedHeroAbilityHandler` (рабочий контракт)

Все хуки мутируют `GameState`, ошибки перехватываются реестром (исходный state / пустой массив) (05:261, 281). Таблица хуков и точек вызова (05:263-275, 321-331; `backend/src/game-engine/abilities/hero-ability.interface.ts:154-270`):

| Хук | Кто | Точка вызова |
|---|---|---|
| `onTurnStart(state, playerId)` | герой нового игрока | `advanceTurn` после добора/сброса флагов |
| `onTurnEnd(state, playerId)` | герой завершающего | `advanceTurn`, в самом начале, до снятия turn-эффектов |
| `onCombat(state, ctx)` | generic-путь | во время боя |
| `onAfterCombat(state, AfterCombatContext)` | атакующий, затем защитник (defender-side) | конец `executeResolveCombat`, до передачи хода |
| `onFighterDefeated(state, fighter)` | герой **владельца** павшего | после after-combat хуков и `isDefeated` |
| `onFighterMoved(state, moved, from, to)` | **все** handler'ы (кросс-героевый) | `applyMoveReactions` после `executeManeuver`, `executeMoveFighter`, `resolvePendingEffect`: дифф позиций до/после + пере-проверка game-over |
| `canAttackAtRange(attackerId, defenderId, range, stance?)` | герой атакующего | `executeAttack`, если melee/ranged не достали |
| `getStanceIds()` | — | валидация `setStance` |
| `getCombatModifiers`, `getStatefulCombatModifiers(state, ctx, fighter, role)`, `getAuraCombatModifiers(state, beneficiary, role)` | герой бойца / все | шаг 3 резолва |

Классический `HeroAbilityHandler` (`applyCombatModifier`, «мёртвые» `onMove/onDefeat/onTurnStart/onTurnEnd` для логирования; `ValueModifier = { type: ADD|SET|IGNORE|MULTIPLY, value, source, timestamp, ownerId }`) — legacy (05:259). Слаг: `fighter.heroSlug ?? fighter.heroId` (05:282).

#### 2.11.2. Data-driven конфиги `ABILITY_CONFIGS`

`AbilityConfig { heroId (слаг), abilityName, description, rules: [{ trigger, condition?, effect, whenStance? }], attackRange?, stances?: StanceConfig[] }` (05:289-296; `…ability-config.ts:347-422`).

- Триггеры: `combat-passive`, `turn-start`, `turn-end`, `after-attack`, `after-defense`, `sidekick-defeated`, `enemy-hero-left-my-zone` (`…ability-config.ts:45-52`).
- Условия: `always`, `attacking`, `defending`, `self-health-below-defender`, `all-own-sidekicks-defeated`, `no-enemy-in-own-zone`, `won-combat`, `lost-combat`, `has-not-maneuvered-this-turn`, `has-attacked-this-turn`, `first-lost-combat-this-turn`, `won-combat-and-all-sidekicks-defeated`, `{ handSizeEquals: N }` (`…ability-config.ts:92-104`).
- Эффекты (`kind`): `combat-modifier { appliesTo, value }`, `combat-modifier-per-count { appliesTo, valuePer, countOf: 'own-fighters-adjacent-to-defender-excl-self' }`, `aura-combat-modifier { appliesTo, value, scope: 'allies-in-my-zone' }`, `turn-effect { draw?, drawToHandSize?, heal?, gainAction? }` (порядок: добор → лечение → действие), `discard-random { count }`, `reactive-damage { value }`, `pending-move { target: 'attacker'|'own-hero'|'any-own', maxSpaces }`, `turn-damage { targetScope: 'enemy-in-zone'|'enemy-adjacent', value, thenDraw? }` (авто-выбор первого подходящего врага; `thenDraw` только после попадания), `set-stance { to: id | 'toggle' }`, `cycle-stance` (`…ability-config.ts:110-345`; `…generic-hero-ability.handler.ts:712-810`).

Все 26 героев (`…ability-config.ts:436-905`; описание: 05:303):

| heroId | Способность | Правило |
|---|---|---|
| luke-cage | Skin Like Titanium | combat-passive, always: +2 defense |
| annie-christmas | Long Shot | combat-passive, self-health-below-defender: +2 attack |
| eredin | Unyielding Hordes | combat-passive, all-own-sidekicks-defeated: +1 both |
| bloody-mary | Infinity Mirror | turn-start, handSizeEquals 3: +1 действие |
| philippa | Spellbreaker | turn-end: добор до 4 карт |
| t-rex | Reckless Lunge | `attackRange: 2`; turn-end: добор 1 |
| bigfoot | It's Just Your Imagination | turn-end, no-enemy-in-own-zone: добор 1 |
| chupacabra | Blood Frenzy | after-attack: добор 1 |
| deadpool | Regeneration | after-attack: лечение 1 |
| michelangelo | Party Dude | after-attack: добор 1 |
| angel | Fallen Grace | after-attack, lost-combat: добор 1 |
| golden-bat | The First Superhero | combat-passive, has-not-maneuvered-this-turn: +2 attack |
| ancient-leshen | Heart of the Forest | combat-passive, has-attacked-this-turn: +3 attack |
| raphael | Anger Issues | after-attack, first-lost-combat-this-turn: +1 действие |
| robin-hood | Trick Shot | after-attack: pending MOVE атакующего до 2 |
| leonardo | Tactical Genius | turn-start: pending MOVE любого своего до 1 |
| dracula | Children of the Night | turn-start: 1 урон смежному врагу, затем добор 1 |
| medusa | Petrifying Gaze | turn-start: 1 урон врагу в зоне |
| bullseye | Bullseye | `attackRange: 5` |
| bruce-lee | Be Like Water | turn-end: pending MOVE героя до 1 |
| raptors | Pack Tactics | combat-passive, attacking: +1 attack за каждого своего бойца, смежного с защитником (кроме себя) |
| oda-nobunaga | Banner of the Demon King | аура: +1 both союзникам в зоне Оды |
| achilles | Grief of Achilles | combat-passive, all-own-sidekicks-defeated: +2 attack; after-attack, won-combat-and-all-sidekicks-defeated: добор 1; sidekick-defeated: сброс 2 |
| tomoe-gozen | Unwavering Resolve | enemy-hero-left-my-zone: 1 урон |
| alice | Big / Small | стойки `big` (default), `small`; BIG: +2 attack; SMALL: +1 defense |
| muhammad-ali | Float Like a Butterfly / Sting Like a Bee | стойки `float` (default, `attackRange: 2`), `sting`; STING: +2 attack; after-attack, won-combat: `set-stance toggle` |

Ручные хендлеры-классы (`backend/src/game-engine/abilities/heroes/`): `arthur` (`king-arthur`, `allowsAttackBoost`), `daredevil` (blind boost — в потоке не вызывается, см. 2.7.2), `ms-marvel` (range ≤ 2) (05:303).

#### 2.11.3. Реализация ключевых реактивных хуков (generic)

- `onAfterCombat`: правила `after-attack` (цель — атакующий) и `after-defense` (цель — `ctx.defenderPlayerId`), только эффекты `turn-effect`/`pending-move`/`set-stance`, гейт `whenStance` по стойке цели (`…generic-hero-ability.handler.ts:389-430`).
- `onFighterDefeated` (`sidekick-defeated` + `discard-random`): только гибель **своего не-HERO** бойца; сбрасываются **первые `count` карт руки** (детерминированно, не случайно, несмотря на имя) (`…generic-hero-ability.handler.ts:452-470`).
- `onFighterMoved` (Tomoe): реагирует, если двигался **вражеский HERO**, был в зоне реактора (`isInSameZone` по legacy `zone`) и покинул её → урон `value`; game-over пере-проверяется в `applyMoveReactions` (`…generic-hero-ability.handler.ts:500-530`; `…executor.service.ts:395-425`).

### 2.12. Ауры

Аура (`aura-combat-modifier`, Oda) → `getAuraCombatModifiers(state, beneficiary, role)`: гранитель — герой-владелец ауры; бенефициар — дружественный боец, **делящий зону** с гранителем, во время его боя; реестр опрашивает **все** зарегистрированные handler'ы и суммирует только `ADD`-модификаторы поверх карт, heroMods и stateful (05:305-307; 10:230-236; `backend/src/game-engine/abilities/hero-ability-registry.ts:685-705`; `…executor.service.ts:1503-1508`).

### 2.13. Стойки (STANCE)

| Факт | Источник |
|---|---|
| `StanceConfig { id, label, default?, attackRange?, combat? }`; стоечный `attackRange` **переопределяет** `config.attackRange`; правило с `whenStance` активно только в этой стойке | `…ability-config.ts:372-380`; 05:315-318 |
| Хранение `metadata.heroStances[userId] = stanceId`; дефолт — стойка с `default: true` или первая; на game-init поле не заполняется | `…game-state.model.ts:117-124`; `…generic-hero-ability.handler.ts:100-111` |
| `mutation setStance(input: { gameId, stanceId })`: guard `ActionPhaseGuard` (свой ход, action-фаза); у игрока есть HERO-боец; герой stance-aware (`getStances(slug)` непуст); `stanceId` в списке; эффект — запись + seq+1; **действие не тратится** | `gameplay.dto.ts:337-348`; `…executor.service.ts:1898-1960`; `…game-actions.resolver.ts:512-534` |
| Ошибки: `'У игрока нет героя на доске'`, `'У этого героя нет стоек'`, `'Неизвестная стойка «…» (доступны: …)'` | `…executor.service.ts:1912-1925` |
| Авто-смена: `set-stance { to: id | 'toggle' }` (Ali после выигранной атаки — toggle), `cycle-stance` (следующая по кругу, для будущего 3-стоечного Moon Knight) — из turn-start/turn-end/after-attack правил | 05:314; `…generic-hero-ability.handler.ts:676-710` |
| Влияние: дальность атаки (`canAttackAtRange` получает `heroStances[attacker.ownerId]`), combat-модификаторы `whenStance` | 10:226; `…executor.service.ts:1030-1046` |
| Справочник: `query heroStances(heroSlug: String!) → [StanceOption { id, label, isDefault }]`, `@Public`, читается из `ABILITY_CONFIGS` (не из БД), для не-стоечных героев `[]` | `backend/src/games/game.resolver.ts:96-111`; 05:422, 598-608 |
| Событие мутации `setStance` — `SPECIAL_ABILITY` | `…game-actions.resolver.ts:531` |

### 2.14. Колоды, рука, добор, сброс

| Факт | Источник |
|---|---|
| `STARTING_HAND_SIZE = 5`, `MAX_HAND_SIZE = 7` (`HandZone.maxSize`) | `…game-initialization.service.ts:39-40, 217-226`; 10:279 |
| Колода = карты героя из БД × `count`, instance id `"${cardId}::${copy}"`, Fisher-Yates; верхние 5 — рука (`isVisible: false` при раздаче; при доборе `true`) | 10:280; `…deck-management.service.ts:98-101` |
| `drawCards(state, userId, n)`: по 1 карте; рука ≥ `maxSize` → стоп; `drawPile` пуст → `recycleDeck` (сброс перетасовывается и кладётся **под** текущий drawPile, сброс очищается); всё пусто → выход; `topCard = drawPile[0]`; seq не трогает | `…deck-management.service.ts:53-128`; 10:285 |
| Добор происходит: в `advanceTurn` (1 карта новому игроку), после манёвра (1), из эффектов `DRAW_CARD` и способностей (`draw`, `drawToHandSize`, `thenDraw`) | `…executor.service.ts:203, 837-842`; `…generic-hero-ability.handler.ts:712-745` |
| `discardCard(instanceId)`: из руки в `discardPiles` (`isVisible: false`); `discardRandomCard` — для эффектов DISCARD (в `executePass` **не используется**) | `…deck-management.service.ts:137-179, 187`; 10:286 |
| Сыгранные карты атаки/защиты/буста уходят в сброс **в момент розыгрыша** | 10:288-290 |
| `mutation pass(input: { gameId })`: валидна в action-фазе, только `passCount + 1` и `consumeAction`; GraphQL-описание «Сбросить карту и получить дополнительное действие» коду не соответствует | `…executor.service.ts:1772-1822`; `…game-actions.resolver.ts:463` |

### 2.15. Конец игры

`checkAndApplyGameOver` — единая точка: `players.filter(isAlive).length <= 1` → `GAME_OVER`, `winnerId`, `combatInfo = undefined`; вызывается после резолва боя, после turn-start хуков в `advanceTurn` и после on-move реакций (`…executor.service.ts:657-671`; 05:171; 10:175). Резолвер дополнительно публикует `GAME_ENDED` (подписка `gameEnded`) и пишет журнал (`…game-actions.resolver.ts:198-214`). `isAlive` игрока пересчитывается в резолве боя (`есть боец с health > 0`) и в `applyReactiveDamage` (`…executor.service.ts:1571-1577`; `…generic-hero-ability.handler.ts:533`).

### 2.16. VS_AI — бот

| Факт | Источник |
|---|---|
| `AiTurnService.maybeRunAiTurns(gameId)` — fire-and-forget после **каждой** мутации человека; no-op, если `game.mode !== 'VS_AI'`, нет `opponentId`, статус не `IN_PROGRESS`; до `MAX_STEPS = 40` шагов подряд, каждый под locком `game:{gameId}`, с `saveState` + `publishGameUpdate` (реальные `eventType`); стоп, если seq не вырос | `backend/src/games/services/ai-turn.service.ts:14-24, 36-90` |
| Задержек между шагами бота **нет** (не найдено) — клиент получит серию `gameStateUpdated` практически мгновенно | `…ai-turn.service.ts:46-50` |
| `AiDecisionService.decide` (чистая greedy-эвристика): 1) `GAME_OVER` → null; 2) свои `pendingEffects` первыми: CHOOSE_ONE — ранг `HEAL(3) > DRAW_CARD(2) > GAIN_ACTION(1) > первая`; MOVE — BFS-шаг к ближайшему врагу ≤ `value ?? movement`; PLACE своего — шаг к врагу; `targetsOpponent` — «двигаем» врага в его же клетку; 3) бой: `COMBAT_RESOLVE` → `resolveCombat`; бот-защитник в `COMBAT`: если защита уже сыграна → resolve, иначе лучшая защита (`max defenseValue`, при равенстве DEFENSE > VERSATILE, только `defenseValue > 0`, banner-совместимая), нет карт → resolve; бот-атакующий: resolve, как только человек сыграл защиту, иначе ждёт; 4) свой ход: `actionsRemaining ≤ 0` → endTurn; ближайший враг (приоритет HERO) от своего героя; досягаемость: melee — манхэттен 1, ranged — смежность **или пересечение зон по `zones[]`** (`shareZone`) — шире, чем `isInSameZone` executor'а; лучшая атака (`max attackValue`, ATTACK > VERSATILE, banner); иначе манёвр строго ближе к врагу в пределах `movement`; иначе endTurn | `backend/src/game-engine/services/ai-decision.service.ts:31-121`; 10:294-299 |
| Следствие: против бота человек-атакующий обычно **не должен** вызывать `resolveCombat` сам — бот сыграет защиту и тут же резолвит (COMBAT_RESOLVE → resolve); человек-защитник после `playDefense` также получит резолв от бота-атакующего | `…ai-decision.service.ts:45-56` |

### 2.17. Сводные константы

| Константа | Значение | Файл |
|---|---|---|
| `ACTIONS_PER_TURN` | 2 | `backend/src/game-engine/models/game-state.model.ts:165` |
| `DEFAULT_FIGHTER_MOVEMENT` | 2 | `backend/src/game-engine/models/fighter.model.ts:65` |
| `DEFAULT_DEFENSE_TIMEOUT` | 30 с (в резолвере жёстко 30) | `backend/src/games/services/combat-timeout.service.ts:59`; `…game-actions.resolver.ts:175` |
| `DEFAULT_RESOLVE_TIMEOUT` | 10 с (не используется) | `…combat-timeout.service.ts:64` |
| `STARTING_HAND_SIZE` / `MAX_HAND_SIZE` | 5 / 7 | `…game-initialization.service.ts:39-40` |
| `FALLBACK_BOARD_SIZE`, `MIN_GRID_SIZE`, `MAX_GRID_SIZE` | 20, 2, 50 | `…game-initialization.service.ts:43-46` |
| `PositionInput/MoveFighterDto/ToggleDoorDto` x,y | `@Min(0) @Max(19)` | `backend/src/games/dto/gameplay.dto.ts:63-75, 153-163, 318-328` |
| Сайдкик по умолчанию | hp 1, движение 2 | 10:217 |
| Смежность | манхэттен === 1 (4-связность) | `…adjacency.service.ts:201-204` |
| Диагональ (API, не используется) | стоимость 1.5 | `…adjacency.service.ts:75` |
| `MAX_STEPS` бота | 40 | `…ai-turn.service.ts:24` |
| Lock мутации | ttl 10 с, 1 retry / 100 мс (AI: 2 retry / 150 мс) | `…game-actions.resolver.ts:222`; `…ai-turn.service.ts:86` |
| Throttle | 20 или 30 запросов/мин на мутацию | см. 2.1 |
| Cobble City | 6×4, 24 клетки, 5 зон, 3 мультизонные клетки | `backend/src/content/data/boards/cobble-city.ts` |
| `MS_MARVEL_EXTENDED_RANGE` | 2 | `…heroes/ms-marvel.handler.ts:22` |

### 2.18. Сводная таблица «механика → что клиент показывает / выбирает → мутация → событие»

| Механика | Когда доступно (клиентская проверка) | Что показать / подсветить / дать выбрать | Мутация (DTO) | eventType |
|---|---|---|---|---|
| Манёвр | мой ход; `phase ∈ {ACTION_MANEUVER, ACTION_ATTACK}`; `actionsRemaining > 0`; боец жив и не `immobilized` | для каждого своего бойца — клетки на расстоянии ≤ `movement + boost` по 4-связным шагам через не-wall/obstacle клетки (конечная свободна); опциональный выбор карты BOOST из руки (любая, показать `boostValue`); напоминание «+1 карта после манёвра» | `maneuver { gameId, moves: [{fighterId, path}], boostCardId? }` | `MANEUVER` |
| Простое перемещение | как манёвр | BFS-достижимые клетки за `movement` (занятые/закрытые двери блокируют) | `moveFighter { gameId, fighterId, x, y }` | `FIGHTER_MOVED` |
| Атака | мой ход; action-фаза; `actionsRemaining > 0` | карты `ATTACK/VERSATILE` в руке (учитывая `bannerName` ↔ выбранный боец); цели: живые вражеские бойцы, для melee — смежные, для ranged — смежные или с тем же `cell.zone`; плюс цели в радиусе `attackRange` стойки/героя (T-Rex 2, Bullseye 5, Ms. Marvel 2, Ali FLOAT 2); опц. BOOST-карта, если у карты есть эффект `BOOST` или герой `king-arthur` | `attack { gameId, attackerId, cardId, targetId, boostCardId? }` | `ATTACK_INITIATED` (+ таймер 30 с) |
| Защита | `phase === COMBAT` и `combatInfo.defenderId === me` | карты `DEFENSE/VERSATILE` (banner против `combatInfo.targetFighterId`); опц. BOOST; локальный таймер 30 с от момента получения `ATTACK_INITIATED`/`combatInfo.startedAt`; показать открытую карту атаки (`attackerCardId` — найти в сбросе атакующего) и `attackValue` | `playDefense { gameId, cardId, boostCardId? }` | `DEFENSE_PLAYED` (отменяет таймер) |
| Резолв боя | `phase ∈ {COMBAT, COMBAT_RESOLVE}`, я участник | кнопка «Разрешить бой» — рекомендуется показывать атакующему только в `COMBAT_RESOLVE` (после защиты или auto-resolve), защитнику — как «пропустить защиту»; после — анимация вскрытия по разнице health до/после (`combatSummary` в GraphQL не приходит) | `resolveCombat { gameId }` | `COMBAT_RESOLVED` (отменяет таймер) |
| Scheme | мой ход; action-фаза; `actionsRemaining > 0` | карты `SCHEME` (banner: есть живой свой боец); текст карты показать игроку — эффекты в основном ручные | `playScheme { gameId, cardId }` | `CARD_PLAYED` |
| Отложенный эффект | есть `pendingEffects` с `playerId === me` (в любой фазе, не только свой ход) | MOVE: выбор бойца (свой/чужой по `targetsOpponent`, фильтр `fighterName`) и клетки в BFS-радиусе `value ?? 1`; PLACE: любая свободная проходимая клетка; CHOOSE_ONE: список `options[].label`, `chooseCount` раз; показать `text` | `resolvePendingEffect { gameId, effectId, fighterId?, x?, y?, optionIndex? }` | `CARD_PLAYED` |
| Конец хода | мой ход; action-фаза | кнопка «Завершить ход» (даже при остатке действий) | `endTurn { gameId }` | `TURN_ENDED` (→ `turnChanged`) |
| Pass | мой ход; action-фаза | кнопка «Пас» (тратит действие, ничего не сбрасывает) | `pass { gameId }` | `CARD_PLAYED` (журнал `PASSED`) |
| Дверь | есть ключ в `boardState.doors` | в текущих данных не показывать | `toggleDoor { gameId, x, y }` | `DOOR_TOGGLED` |
| Стойка | мой ход; action-фаза; `heroStances(heroSlug)` непуст | переключатель стоек с `label`, текущая — `metadata.heroStances[me]` или `isDefault`; бесплатно | `setStance { gameId, stanceId }` | `SPECIAL_ABILITY` |
| Авто-передача хода | после 2-го действия / резолва при 0 действий | смена `currentTurnPlayerId` в `gameStateUpdated` (без `turnChanged`) | — | `MANEUVER`/`COMBAT_RESOLVED`/… |
| Auto-resolve | 30 с без защиты | `gameStateUpdated` с `phase: COMBAT_RESOLVE`, `defenseValue 0`; далее нужен `resolveCombat` | — | `STATE_UPDATED` только |
| Game over | `phase === GAME_OVER` | `metadata.winnerId` | — | `GAME_ENDED` |

---

## 3. Следствия для UE-клиента

1. **Сервер — единственный арбитр.** Клиент дублирует правила лишь для подсветки кандидатов и должен корректно обрабатывать отказ любой мутации (`BadRequestException`, текст в `errors[0].message`), откатываясь к последнему снапшоту (04:550; `…game-actions.resolver.ts:129-135`).
2. **Машина состояний UI** должна опираться на 5 реальных фаз: `ACTION_MANEUVER` (+ legacy `ACTION_ATTACK` как синоним), `COMBAT`, `COMBAT_RESOLVE`, `GAME_OVER`; `SETUP/TURN_START/TURN_END` в потоке не встречаются, но enum их содержит — обрабатывать как «неизвестная/переходная» (10:12-23).
3. **Счётчик действий и авто-передача хода.** Показывать `metadata.actionsRemaining` (дефолт 2 при отсутствии). После 2-го действия (или резолва боя при 0) ход переходит **в той же мутации**; `turnChanged` при этом **не** приходит — детектировать смену хода по `currentTurnPlayerId`/`turnCount` в `gameStateUpdated` (`…executor.service.ts:680-690`; `…game-subscription.resolver.ts:246-261`).
4. **Атака тратит действие сразу.** UI должен уменьшать счётчик при `ATTACK_INITIATED`, а не при резолве; если атака была вторым действием, после резолва ход уйдёт сопернику (`…executor.service.ts:1117, 1651-1668`).
5. **Подсветка движения.** Реализовать BFS по 4-связной сетке с `isCellBlocked` (wall/obstacle/закрытая door) и `blockedPositions` (клетки живых бойцов) — как `AdjacencyService.getReachableCells`. Для манёвра сервер проверяет только длину пути, шаги (манхэттен 1), wall/obstacle и занятость **конечной** клетки; клиенту стоит быть строже сервера (не прокладывать путь через занятые клетки) — но знать, что сервер такое примет (`…validator.ts:278-372`; `…executor.service.ts:800-812`).
6. **Подсветка целей атаки.** melee — манхэттен 1; ranged — плюс совпадение legacy `cell.zone` (первая зона, **не** пересечение `zones[]`); плюс `attackRange` героя/стойки по манхэттену (T-Rex 2, Bullseye 5, Ms. Marvel 2, Ali FLOAT 2). Таблицу дальностей брать из `ABILITY_CONFIGS` — через GraphQL она **не** экспортируется (только `heroStances`), т.е. придётся захардкодить/синхронизировать вручную или показывать «пробную» подсветку и полагаться на отказ сервера (`…adjacency.service.ts:214-218`; `…executor.service.ts:1030-1046`).
7. **Геометрия доски — только из `boardState` состояния** (`width/height/cells[y][x]`), не из контентного `boards` и не из статического Cobble City: при пустых `Board.cells` в БД партия идёт на 20×20 без зон, старты (2,2)/(17,17) (`…game-initialization.service.ts:279-289, 366-378`). DTO координат ограничены `0..19` — доска шире 20 клеток не адресуема мутациями (`gameplay.dto.ts:63-75`).
8. **Таймер защиты — локальный.** `combatInfo.timeoutAt` не заполняется; отсчитывать 30 с от `combatInfo.startedAt` (или от прихода `ATTACK_INITIATED`) с поправкой на рассинхрон часов; по истечении ожидать `gameStateUpdated` с `COMBAT_RESOLVE` и предлагать участникам `resolveCombat` (`…combat-timeout.service.ts:260-282`).
9. **Кнопка «Разрешить бой».** Сервер позволяет атакующему резолвить уже в `COMBAT` (до защиты). Для честной игры UE-клиент атакующего должен показывать кнопку только в `COMBAT_RESOLVE`; защитнику — как «не защищаться» в `COMBAT` (`…game-turn.guard.ts:230-283`).
10. **Источники данных для рендера.** `gameStateUpdated` не содержит `decks`/`discardPiles`: для сброса, счётчика колоды и поиска открытых карт боя (`attackerCardId`/`defenderCardId` лежат в сбросе) использовать `state` из ответа мутации (для инициатора) и `query gameState` (для второго игрока) после событий `ATTACK_INITIATED`/`DEFENSE_PLAYED`/`COMBAT_RESOLVED`/`MANEUVER` (`gameplay.dto.ts:461-491`; `…game.resolver.ts:63-87`). Альтернатива — вести локальную модель сброса по диффу рук (ненадёжно при рециклинге колоды).
11. **Приватность.** Чужая рука приходит как «???» с `id/cardId/cardType/bannerName`; чужой `drawPile` приходит целиком (кроме `topCard`). Клиент **не должен** отображать или использовать `cardId`/`drawPile` соперника — показывать только рубашки и счётчики (`…game-state.service.ts:494-541`).
12. **Числа боя.** `combatSummary`, `effectText`, `appliedEffects`, `manualEffects` не экспортируются в GraphQL — итоги боя выводить из диффа `fighters[].health` и `isDefeated`, а лог эффектов — из текста карт (`Card.text`, `effects[].text` из контента) (`…game-actions.resolver.ts:72-80`).
13. **PendingEffect — неблокирующие модалки.** Показывать очередь `pendingEffects` с `playerId === me` в любой фазе и не только в свой ход; предупреждать, что они протухнут в начале моего следующего хода; поддержать три типа (MOVE с фильтром бойца по `fighterName`/`targetsOpponent`, PLACE, CHOOSE_ONE с `chooseCount`) (`…executor.service.ts:432-640`).
14. **Стойки.** При выборе героя запросить `heroStances(heroSlug)` (слаг = `Fighter.heroSlug` из состояния); текущая стойка — `metadata.heroStances[userId]` с фолбэком на `isDefault`; кнопки активны только в свой ход в action-фазе; учитывать авто-флипы (Ali после победы) — перерисовывать по каждому снапшоту (`…game.resolver.ts:96-111`; `…generic-hero-ability.handler.ts:100-111`).
15. **Эффекты бойцов.** Рендерить `fighter.effects[]` (`immobilized`, `duration: 'turn'`) как статус-иконки; блокировать выбор такого бойца для движения (`…card-effect-executor.service.ts:560-580`).
16. **Двери/туман/возвышенность** — не реализовывать UI до появления данных в БД/движке (`…game-initialization.service.ts:349`; 10:196-198).
17. **Pass** — показывать как «пропустить действие» без сброса карты (`…executor.service.ts:1791-1803`).
18. **Ручные эффекты.** В БД `Card.effects` почти всегда пусты — большинство текстов карт не автоматизировано; UI должен позволять игрокам читать текст карты и (при необходимости) договариваться, а движок применит только распознанные эффекты (05:232; `…executor.service.ts:1286-1300`).
19. **VS_AI.** Ожидать пачку `gameStateUpdated` без задержек сразу после своей мутации; для плавности буферизовать снапшоты по `sequenceNumber` и проигрывать анимации последовательно (`…ai-turn.service.ts:36-90`).
20. **Идемпотентность/дедупликация.** Сравнивать `sequenceNumber` (строго возрастающий, +1 на мутацию); при реконнекте — `gameState` + `eventsSince`/`gameStateUpdated(since)` (04:525; `…game-subscription.resolver.ts:156-170`).
21. **Движение героя** брать из `Fighter.movement` (обычно 2), а не из контентного `Hero.movement` (захардкожено 3) (05:396).
22. **Оценка урона для превью** (опционально): `finalAttack = card.attackValue + boost + модификаторы героя`, `finalDefense` аналогично; ничья — защитник; но stateful/aura-модификаторы зависят от состояния (первая/вторая атака, стойка, зона) — превью только приблизительное (10:148-164).

---

## 4. Открытые вопросы / несоответствия

1. **Ranged-зона: пересечение vs legacy `zone`.** 05:143, 05:190, 04:547 и `board.model.ts:30-31` говорят о пересечении `zones[]`; фактический `isInSameZone` читает только `cell.zone` (первую зону) (`…adjacency.service.ts:214-218`; 10:117 это признаёт). AI-бот использует пересечение (`ai-decision.service.ts:70-73`) — бот может попытаться атаковать, а executor откажет (шаг бота прервётся). Для клиента: подсвечивать по `zone`.
2. **Промежуточные клетки манёвра.** 10:93 утверждает, что занятые промежуточные клетки отклоняются; код (`…validator.ts:235-249`, `…executor.service.ts:800-812`) проверяет занятость только конечной клетки, а закрытые двери в манёвре не проверяются вовсе. 05:176 соответствует коду.
3. **Auto-resolve не наносит урон** (`…combat-timeout.service.ts:273-281`, TODO) — после таймаута требуется ручной `resolveCombat`. 10:133 это отмечает; 04:549 «таймаут 30 с → auto-resolve» может быть понято как полноценный резолв.
4. **`CombatResolveGuard` без проверки таймаута** — атакующий может резолвить в `COMBAT` до защиты (комментарий guard'а обещает «после истечения таймаута») (`…game-turn.guard.ts:225-283`).
5. **`combatInfo.timeoutAt` никогда не пишется**; пример 04:411-413 иллюстративный.
6. **Двери мертвы**: `doors` всегда `{}`, клетки `door` не создаются; `toggleDoor` всегда `DOOR_NOT_FOUND`; кроме того, BFS смотрит `cell.isOpen`, а toggle меняет `doors['x:y']` — две несвязанные структуры (`…game-initialization.service.ts:349`; `…adjacency.service.ts:148`; `…executor.service.ts:1849-1860`).
7. **Возвышенность**: 04:548 «бонус ±1» — в движке `isHighGround` не используется (10:189; grep).
8. **Pass**: описание мутации «Сбросить карту и получить дополнительное действие» (`…game-actions.resolver.ts:463`) и комментарий `discardRandomCard` «для действия Pass» (`…deck-management.service.ts:182`) vs код — ничего не сбрасывает, действие тратит (`…executor.service.ts:1791-1803`).
9. **`discard-random` детерминирован** — сбрасывает первые `count` карт руки, не случайные (`…generic-hero-ability.handler.ts:452-470`).
10. **Утечка приватных данных**: `filterPrivateData` оставляет `cardId`/`bannerName` чужих карт (по `cardId` можно узнать карту через контентный `card(id)`) и полный `drawPile` чужой колоды; комментарий метода обещает скрывать сброс — сброс не скрывается (`…game-state.service.ts:490-541`). Требует решения на бэкенде; клиент не должен использовать.
11. **Подписка без сброса/колод**: `GameState` GQL-тип не содержит `decks`/`discardPiles` (`gameplay.dto.ts:461-491`), тогда как 04:363-367 описывает их в JSON состояния (это про `query gameState`/ответ мутации). Нужен либо новый field, либо клиентский re-fetch.
12. **`combatSummary`/`effectText`/`appliedEffects`/`manualEffects`** есть в `ActionResult`, но не в `GameMutationResult` (05:147 vs `gameplay.dto.ts:437-455`) — клиент не получает итоговые числа боя и тексты для «ручного применения».
13. **Доска в текущей БД**: комментарий «у всех досок cells=[]» → игра на 20×20 без зон; 10:213 говорит «в БД может лежать своя геометрия». Реальное содержимое `Board.cells` для cobble-city в БД — не проверено (не найдено в источниках). Нужно проверить сид.
14. **DTO координат `@Max(19)`** vs `MAX_GRID_SIZE = 50` — доски > 20 клеток недоступны мутациям (`gameplay.dto.ts:63-75`; `…game-initialization.service.ts:46`).
15. **`MAX_HAND_SIZE`**: код 7 (`…game-initialization.service.ts:40`), пример 04:371 показывает `maxSize: 10`; legacy `GameStateService.createInitialState` — 5 (`…game-state.service.ts:576`).
16. **Hero.movement**: контентный DTO — 3 (05:396), движок — из БД/дефолт 2. Какое значение правильно по правилам для конкретных героев — не найдено.
17. **GraphQL `CombatState`** (`gameplay.dto.ts:416-431`: `targetId`, `attackCardId`, `defenseCardId`, `timeoutAt`) не совпадает с JSON `metadata.combatInfo` (`attackerId/defenderId/targetFighterId/attackerCardId/defenderCardId/...`); где используется GQL-тип — не найдено в игровых резолверах.
18. **Daredevil blind boost**: ручной хендлер (`executeBlindBoost`) не вызывается из потока; работает только парсерный `BOOST/SELF_DECK_TOP` — покрытие карт Daredevil эффектами в БД не проверено.
19. **Тексты ошибок** смешаны (русские/английские) — для локализации UE потребуется маппинг по подстрокам или кодам (`code` из `ValidationResult` наружу не идёт — только `error`).
20. **`DEFAULT_RESOLVE_TIMEOUT = 10`** объявлен, но не применяется; `getTimeUntilResolve` не экспортирован в GraphQL.
21. **`turnChanged`** не срабатывает на авто-передачу хода (только на явный `endTurn`) — комментарий в резолвере (`…game-subscription.resolver.ts:243-245`).
22. Список `EffectCondition`/`CountSpec` в коде (`card.model.ts:86-140`) подробно не сверялся с 05:117-118 — предполагается совпадение.

---

## 5. Источники

Документы:
- `docs/backend-api/05-engine-and-content.md` (часть A: строки 12-343; B.2-B.3: 396, 422, 598-608; приложение 649-674)
- `docs/backend-api/10-mechanics-deep-dive.md` (полностью, 1-316)
- `docs/backend-api/04-game-api.md` (точечно: 301, 340-432, 436-505, 525-570)

Код (сверка):
- `backend/src/game-engine/models/game-state.model.ts`, `fighter.model.ts`, `card.model.ts`, `board.model.ts`
- `backend/src/game-engine/services/game-action-executor.service.ts`, `deck-management.service.ts`, `ai-decision.service.ts`, `turn-management.service.ts`
- `backend/src/game-engine/engine/adjacency.service.ts`, `movement.service.ts`
- `backend/src/game-engine/validators/game-rules.validator.ts`
- `backend/src/game-engine/effects/card-effect-executor.service.ts`, `effect-text-parser.ts`
- `backend/src/game-engine/abilities/ability-config.ts`, `generic-hero-ability.handler.ts`, `hero-ability-registry.ts`, `hero-ability.interface.ts`, `heroes/arthur.handler.ts`, `heroes/ms-marvel.handler.ts`, `heroes/daredevil.handler.ts`
- `backend/src/games/resolvers/game-actions.resolver.ts`, `game-subscription.resolver.ts`; `backend/src/games/game.resolver.ts`
- `backend/src/games/dto/gameplay.dto.ts`; `backend/src/games/guards/game-turn.guard.ts`
- `backend/src/games/services/combat-timeout.service.ts`, `game-initialization.service.ts`, `ai-turn.service.ts`; `backend/src/games/processors/combat-timeout.processor.ts`
- `backend/src/games/game-state.service.ts`, `game-subscription.service.ts`
- `backend/src/content/data/boards/cobble-city.ts`
