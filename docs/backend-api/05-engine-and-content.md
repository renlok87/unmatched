# 05. Игровой движок и контентная подсистема

Документ описывает две части бэкенда:

1. **Игровой движок** (`backend/src/game-engine`) — иммутабельная машина состояний Unmatched: ходы, бой, эффекты карт, способности героев, ауры, стойки, хуки.
2. **Контентная подсистема** (`backend/src/content`) — хранение и выдача героев/карт/бордов через GraphQL, статические ассеты.

Аудитория: интеграция клиента на Unreal (и любой другой), бэкенд-разработчики.

---

# Часть A. Игровой движок (`backend/src/game-engine`)

## A.1. Архитектура и принципы

```
game-engine/
├── models/          # Контракт данных: GameState, Fighter, Card, Board
├── engine/          # Низкоуровневые сервисы: бой, движение, смежность, модификаторы
├── effects/         # CardEffectExecutorService — исполнение эффектов карт
├── abilities/       # Реестр способностей героев + data-driven конфиги (ABILITY_CONFIGS)
├── services/        # GameActionExecutorService (оркестратор), turn/deck-management, AI
├── movement/        # A*, path-cache
├── validators/      # GameRulesValidator — валидация каждого действия
└── cache/           # Кэш значений карт
```

Ключевые принципы:

- **Иммутабельность.** `GameState` и вложенные структуры `readonly`; любое действие возвращает НОВОЕ состояние (structural sharing), старое не мутируется.
- **Единая точка входа.** Все игровые действия выполняются через `GameActionExecutorService` (файл `services/game-action-executor.service.ts`, ~2000 строк) по паттерну: *валидация (`GameRulesValidator`) → выполнение (engine-сервисы) → результат `ActionResult`*.
- **`sequenceNumber` — контракт saveState.** Ровно **+1 к sequenceNumber за одну мутацию**. Вложенные хуки (способности героев, on-move реакции) «прицепляются» к инкременту вызывающего действия и seq отдельно не бампят.
- **Экономика действий: 2 действия за ход** (`ACTIONS_PER_TURN = 2`). Манёвр / атака / scheme в любой комбинации; после второго действия ход завершается автоматически (`consumeAction` → `advanceTurn` без доп. инкремента seq).
- **Фазы `GamePhase`** формально включают SETUP/TURN_START/…/GAME_OVER, но в продакшен-потоке ход начинается сразу с `ACTION_MANEUVER` (фаза TURN_START пропускается; хуки начала хода встроены в `advanceTurn`).

## A.2. Ключевые модели (`models/`)

### `GameState` (`models/game-state.model.ts`)

```ts
interface GameState {
  gameId: string;
  sequenceNumber: number;          // версия состояния (для saveState/подписок)
  phase: GamePhase;                // SETUP | TURN_START | ACTION_MANEUVER | ACTION_ATTACK
                                   // | COMBAT | COMBAT_RESOLVE | TURN_END | GAME_OVER
  turnCount: number;
  currentTurnPlayerId: string;
  players: GameStatePlayer[];      // { userId, heroId, health, maxHealth, fighterIds, isAlive }
  fighters: Fighter[];             // все бойцы на доске (герои + сайдкики)
  decks: Record<string, DeckState>;        // по userId
  discardPiles: Record<string, Card[]>;    // по userId
  handZones: Record<string, HandZone>;     // по userId
  boardState: BoardState;
  metadata: GameStateMetadata;
}
```

`GameStateMetadata` — рабочие данные движка:

| Поле | Назначение |
|---|---|
| `combatInfo?: CombatState` | Текущий бой (между `executeAttack` и `executeResolveCombat`): attackerId, defenderId (userId защитника), targetFighterId (боец-цель), id карт, attackValue/defenseValue, таймауты |
| `actionsRemaining?` | Остаток действий хода (дефолт 2 через `getActionsRemaining`) |
| `heroStances?` | Текущая стойка каждого игрока: `Record<userId, stanceId>` (см. A.7) |
| `pendingEffects?` | Отложенные эффекты, требующие выбора игрока (MOVE/PLACE/CHOOSE_ONE), см. A.6 |
| `turnStartPositions?` | Снапшот позиций на начало хода — для условия `MOVED_THIS_TURN` |
| `maneuveredThisTurn / attackedThisTurn / lostCombatThisTurn` | Per-turn флаги для условий способностей; сбрасываются в `advanceTurn` |
| `winnerId?` | Победитель (ставится при GAME_OVER) |

### `Fighter` (`models/fighter.model.ts`)

Боец на доске (герой, сайдкик или huge):

```ts
interface Fighter {
  id: string;                 // instance id
  ownerId: string;            // userId владельца
  heroId: string;
  name: string;
  type: FighterType;          // HERO | MINION | HUGE
  health: number; maxHealth: number;
  position: Position;         // { x, y }
  effects: FighterEffect[];   // временные эффекты (duration: 'turn' | 'round' | 'permanent')
  hasSidekick: boolean; sidekickIds?: string[];
  isDefeated?: boolean;
  movement?: number;          // очки движения (default 2, getFighterMovement)
  attackType?: 'melee' | 'ranged';  // ranged = та же зона или смежная (getFighterAttackType)
  heroSlug?: string;          // слаг героя для реестра способностей ('daredevil', 'ms-marvel')
}
```

Важные хелперы: `slugifyHeroName('Ms. Marvel') → 'ms-marvel'` (единственная точка нормализации слага), `normalizeAttackType` (БД хранит `'range'`, движок — `'ranged'`), `positionDistance` (Manhattan).

### `Card` / `CardEffect` (`models/card.model.ts`)

```ts
enum CardType { ATTACK, DEFENSE, SCHEME, UNIVERSAL, VERSATILE, MANEUVER }
// VERSATILE играется и как атака, и как защита; MANEUVER — карта движения

interface Card {
  id: string;              // instance id вида `${cardId}::n`
  cardId: string;          // базовый id (Prisma cuid)
  name / nameEn / nameRu;
  cardType: CardType;
  attackValue? / defenseValue? / boostValue?;
  effects?: CardEffect[];
  text?: string;           // текст эффекта из БД (для ручного применения)
  bannerName?: string;     // кто может играть карту ('Any' / имя бойца, напр. 'Medusa')
}
```

`CardEffect` — декларативный эффект, заполняемый парсером текстов карт (`effects/effect-text-parser.ts`) и вручную через админку:

- **`type` (`EffectType`)**: MODIFY_ATTACK, MODIFY_DEFENSE, DAMAGE, HEAL, MOVE, PLACE, DRAW_CARD, DISCARD, MODIFY_VALUE, SET_VALUE, VALUE_PER_COUNT, BOOST, CANCEL_EFFECTS, OPPONENT_DISCARD, RETURN_TO_HAND, IMMOBILIZE, GAIN_ACTION, PREVENT_DAMAGE, END_TURN, CHOOSE_ONE, UNSUPPORTED (нераспознанный текст — не исполняется, едет в `manualEffects` результата).
- **`timing` (`EffectTiming`)**: BEFORE_COMBAT, DURING_COMBAT, AFTER_COMBAT, ON_PLAY, ON_DISCARD, TURN_START, TURN_END, ON_REVEAL (при вскрытии карт в резолве боя).
- **`target` (`EffectTarget`)**: ATTACKER, DEFENDER, SELF, ALL_ENEMIES, ALL_ALLIES, OPPOSING_FIGHTER, ENEMIES_ADJACENT_TO_SELF, ADJACENT_ENEMY, NAMED_FIGHTER, OPPONENT_PLAYER.
- **`when` (`EffectCondition`)**: WON_COMBAT, LOST_COMBAT, IS_ATTACKING/IS_DEFENDING, ADJACENT_TO_OPPONENT, DECK_EMPTY, HAND_COUNT_*, HEALTH_AT_MOST, MOVED_THIS_TURN, OPPONENT_IS_HERO, SHARES_ZONE_WITH_OPPONENT и др.
- **`count` (`CountSpec`)**: динамическое значение («+1 за каждого…»): FRIENDLY_ADJACENT_TO_OPPONENT, CARDS_IN_HAND, DISCARD_NAME_PREFIX, DAMAGE_DEALT, DAMAGE_TAKEN, множитель `per`.
- **`boostSource`**: PLAYER_CHOICE_HAND (сброс из руки), SELF_DECK_TOP (blind boost, Daredevil), OPPONENT_RANDOM_HAND.
- **`options` + `chooseCount`**: для интерактивного «Choose one: …».

`normalizeCardEffects(raw, cardId)` — безопасная нормализация Prisma `Card.effects` (Json): двойная сериализация, мусор, одиночный объект — всё сводится к валидному массиву или одному UNSUPPORTED-эффекту; никогда не бросает.

### `BoardState` (`models/board.model.ts`)

```ts
interface BoardState {
  width: number; height: number;
  cells: Cell[][];                      // cells[y][x]
  doors: Record<string, boolean>;       // "x:y" -> открыта
  fog: Record<string, boolean>;
  tokens: Record<string, any>;
}
interface Cell {
  type: 'normal' | 'wall' | 'obstacle' | 'door' | 'zone-line';
  x: number; y: number;
  zones?: string[];   // клетка может быть в 1–2 зонах (мультизонность)
  zone?: string;      // legacy
  isOpen?, isHighGround?: boolean;
}
```

`getCellZones(cell)` — единственная точка чтения зон (учёт мультизонности/legacy). Зоны определяют дальность ranged-атак и зонные условия эффектов.

## A.3. Выполнение хода (жизненный цикл)

Все действия — методы `GameActionExecutorService` c сигнатурой `(dto, context: ActionContext) => Promise<ActionResult>`, где `ActionContext = { userId, gameId, currentState }`. Результат: `{ success, gameState?, error?, metadata: { action, performedAt, performedBy, sequenceNumber, effectText?, appliedEffects?, manualEffects?, combatSummary? } }`.

### Поток хода

1. **Начало хода** (`advanceTurn`, вызывается из endTurn / авто-завершения после 2-го действия):
   - onTurnEnd-хук героя ЗАВЕРШАЮЩЕГО игрока (extended, мутирует state);
   - выбор следующего живого игрока по кругу;
   - **добор 1 карты** следующему игроку;
   - снятие эффектов `duration: 'turn'` (immobilize и т.п.);
   - снапшот `turnStartPositions`;
   - сброс per-turn флагов, `actionsRemaining = 2`;
   - чистка протухших `pendingEffects` владельца (при полном круге);
   - onTurnStart-хук героя нового игрока; пере-проверка game-over (способность могла добить).

2. **Действия (фаза ACTION_MANEUVER, 2 шт.)** — любой микс:
   - `executeManeuver(dto)` — манёвр;
   - `executeAttack(dto)` + `executePlayDefense(dto)` + `executeResolveCombat(dto)` — бой (атака списывает действие в момент объявления);
   - `executePlayScheme(dto)` — scheme-карта;
   - `executePass(dto)`, `executeMoveFighter(dto)` — вспомогательные;
   - `executeToggleDoor(dto)` — дверь (не тратит действие);
   - `executeSetStance(dto)` — смена стойки (бесплатно);
   - `executeResolvePendingEffect(dto)` — резолв отложенного эффекта (действие не тратится, seq +1);
   - `executeEndTurn(dto)` — досрочная передача хода.

3. **Конец игры** (`checkAndApplyGameOver`): остался один живой игрок → `phase = GAME_OVER`, `winnerId`, `combatInfo` очищается. Проверяется после резолва боя, после хуков начала хода и после on-move реакций.

### Манёвр (`executeManeuver`)

- Двигает **всех своих бойцов**: `moves: [{ fighterId, path }]` (каждый боец — не более одного раза); legacy-путь `fighterId + path` тоже принят.
- Ходы применяются последовательно, валидация каждого — на состоянии после предыдущего (учёт освободившихся/занятых клеток). Промежуточные клетки пути можно проходить, конечная должна быть свободна.
- BOOST-карта (`boostCardId`, legacy `cardId`) уходит в сброс, её boostValue добавляется к движению каждого бойца.
- После движения — **добор 1 карты** (правила Unmatched: манёвр = добор + движение).
- Тратит 1 действие (`consumeAction`).

### BOOST

BOOST картой из руки разрешён, если играемая карта имеет эффект `BOOST` (`boostSource: PLAYER_CHOICE_HAND` или null) **или** способность героя это явно разрешает (`allowsAttackBoost` / `allowsDefenseBoost`, например King Arthur — буст атаки). Нельзя бустить той же картой.

## A.4. Система боя

### Объявление атаки (`executeAttack`)

1. Валидация (`validateAttackWithParams`): ход игрока, боец жив, карта в руке, banner-ограничение.
2. **Дальность**: `melee` — только смежная цель; `ranged` — смежная ИЛИ та же зона доски (пересечение зон клеток). Если цель не достаётся — расширенный запрос к реестру способностей `canAttackAtRange(slug, attackerId, targetId, range, stance)` (Ms. Marvel растяжка; Muhammad Ali — стойка FLOAT range 2). Хук **только добавляет** разрешение, никогда не отнимает.
3. Сыгранная карта (и boost-карта) сбрасываются из руки; в `metadata.combatInfo` пишется `attackValue = attackValue + boostValue`; фаза → `COMBAT`; **действие списывается сразу**.

### Защита (`executePlayDefense`)

Защитник (только он) играет карту защиты (+ опц. boost). Banner проверяется против атакованного бойца (`targetFighterId`, legacy — первый боец защитника). `defenseValue = defenseValue + boostValue`; фаза → `COMBAT_RESOLVE`. Без защиты — резолв с defenseValue 0.

### Резолв боя (`executeResolveCombat`) — пайплайн

```
1. ON_REVEAL   — эффекты «при вскрытии» (атакующий → защитник); cancel-флаги карт
2. DURING_COMBAT — карточные эффекты (SET/MODIFY/VALUE_PER_COUNT/BOOST/PREVENT…)
                 → finalAttack/finalDefense от карт
3. Модификаторы способностей, ПОСЛЕ карточных (аддитивно):
     heroMods        — классический applyCombatModifier (CombatState+fighter+role)
     statefulAttack/Defense — getStatefulCombatModifiers (с доступом к GameState)
     auraAttack/Defense     — getAuraCombatModifiers (аура ДРУГОГО героя-гранителя)
   finalAttack  = calc.finalAttack  + heroMods + stateful + aura
   finalDefense = calc.finalDefense + heroMods + stateful + aura
4. Урон: attack > defense → разница защитнику; defense > attack → атакующему;
   НИЧЬЯ = победа защитника, урона нет. PREVENT_DAMAGE гасит урон стороне.
5. AFTER_COMBAT — сначала ВСЕ эффекты атакующего, затем защитника
6. Итоги: health<=0 → isDefeated; isAlive игрока = есть живые бойцы
7. Хуки способностей: onAfterCombat атакующего → onAfterCombat защитника
   (defender-side, напр. Spider-Sense) → onFighterDefeated героя владельца
   каждого НОВО-павшего (Achilles → discard 2 при гибели сайдкика)
8. checkAndApplyGameOver
9. Остаток действий > 0 → фаза ACTION_MANEUVER (ход продолжается),
   иначе advanceTurn (авто-передача хода)
```

В `metadata.combatSummary` результата возвращаются `finalAttack`, `finalDefense`, урон обеих сторон, `attackerWon`, cancel-флаги. Ссылки на карты в `combatInfo` — instance id, поэтому резолв ищет карты «где угодно» (`findCardAnywhere`: руки → сбросы → полные списки колод).

Низкоуровневый `CombatResolverService` (`engine/combat-resolver.service.ts`) содержит `resolveCombat` (легаси-путь), `getHeroCombatModifiers` (классические модификаторы героя) и `checkGameOver`; значения карт кэшируются (`cache/card-value-cache.service.ts`).

## A.5. Эффекты карт (`effects/card-effect-executor.service.ts`)

`CardEffectExecutorService` исполняет `CardEffect[]` по таймингам:

- `executeRevealEffects(state, attackerCard, defenderCard, combatCtx)` — ON_REVEAL + cancel-флаги (`CANCEL_EFFECTS` — «Cancel all effects on your opponent's card»);
- `executeCombatEffects(...)` — DURING_COMBAT → `{ state, finalAttack, finalDefense, appliedEffects, manualEffects, preventDamageTo* }`;
- `executeAfterCombatEffects(...)` — AFTER_COMBAT (условия WON/LOST_COMBAT и т.д.);
- `executeOnPlayEffects(state, card, userId)` — scheme-розыгрыш (best-effort; в БД effects почти всегда пустые — текст едет клиенту через `effectText` для ручного применения);
- `executeChosenEffects(state, effects, userId, card)` — выбранная опция CHOOSE_ONE.

Каждый вызов возвращает `appliedEffects` (авто-применённые) и `manualEffects` (требующие ручного применения: MOVE/PLACE/UNSUPPORTED) — клиент показывает их в логе.

## A.6. Отложенные эффекты (`PendingEffect`)

Эффекты MOVE/PLACE/CHOOSE_ONE, требующие выбора игрока, не блокируют игру: вместо мгновенного исполнения в `metadata.pendingEffects` кладётся заявка:

```ts
interface PendingEffect {
  id: string;
  type: 'MOVE' | 'PLACE' | 'CHOOSE_ONE';
  playerId: string;            // кому принадлежит выбор
  value?: number;              // дистанция MOVE
  fighterName?: string;        // именное ограничение («Move Daredevil…»)
  targetsOpponent?: boolean;   // двигается боец противника
  options?, chooseCount?, optionEffects?, card?;  // для CHOOSE_ONE
}
```

Резолв — мутация `resolvePendingEffect` (`executeResolvePendingEffect`): для MOVE — BFS-достижимость (`AdjacencyService.getReachableCells`) за `value` шагов; для PLACE — любая свободная проходимая клетка; для CHOOSE_ONE — исполнение эффектов выбранной опции (при `chooseCount > 1` pending остаивается с остатком опций). Действие НЕ тратится; заявки протухают при возврате хода владельцу.

## A.7. Способности героев, ауры, стойки (`abilities/`)

### Два уровня интерфейсов

**Классический `HeroAbilityHandler`** (легаси, в проде почти не используется): `applyCombatModifier(combatState, fighter, role): ValueModifier[]`, а также «мёртвые» GameEvent-хуки `onMove/onDefeat/onTurnStart/onTurnEnd` (остались для логирования). `ValueModifier = { type: ADD|SET|IGNORE|MULTIPLY, value, source, timestamp, ownerId }`.

**Расширенный `ExtendedHeroAbilityHandler`** — рабочий контракт (все хуки мутируют `GameState`, ошибки перехватываются реестром и не роняют поток):

| Хук | Когда вызывается |
|---|---|
| `onTurnStart?(state, playerId)` | В `advanceTurn` — у героя нового игрока |
| `onTurnEnd?(state, playerId)` | В `advanceTurn` — у завершающего игрока, ДО снятия turn-эффектов |
| `onCombat?(state, context)` | Во время боя (generic-путь) |
| `onAfterCombat?(state, ctx: AfterCombatContext)` | После резолва боя — для атакующего И отдельно для защитника (defender-side). `AfterCombatContext = { playerId, defenderPlayerId, attackerFighterId, defenderFighterId, won, damageDealt, firstLossThisTurn }` |
| `onFighterDefeated?(state, defeatedFighter)` | На каждого НОВО-павшего бойца; диспетчеризуется герою ВЛАДЕЛЬЦА (реакция на гибель сайдкика) |
| `onFighterMoved?(state, movedFighter, fromPos, toPos)` | Кросс-героевый реактивный: после ЛЮБОГО перемещения (дифф позиций) консультируются ВСЕ handler'ы — реагирует ДРУГОЙ герой (Tomoe Gozen: «вражеский герой покинул мою зону → 1 урон») |
| `canAttackAtRange?(attackerId, defenderId, range, stance?)` | Расширение дальности атаки (только additive) |
| `getStanceIds?()` | Список id стоек (валидация setStance) |
| `getCombatModifiers?(context, fighter, role)` | Комбат-модификаторы (упрощённый контракт) |
| `getStatefulCombatModifiers?(state, context, fighter, role)` | Модификаторы с доступом к GameState (ADD-семантика) |
| `getAuraCombatModifiers?(state, beneficiary, role)` | АУРА: герой-ГРАНИТЕЛЬ баффает дружественного бойца, делящего его зону; консультируются ВСЕ handler'ы |

### Реестр `HeroAbilityRegistry`

- Хранение: `Map<slug, HeroAbilityHandler>` + `Map<slug, ExtendedHeroAbilityHandler>`.
- Диспетчеры: `applyCombatModifiers`, `triggerOnTurnStart/EndExtended`, `triggerOnAfterCombat`, `triggerOnFighterDefeated`, `triggerOnFighterMoved` (цепочка всех extended-handler'ов с протягиванием state), `triggerOnCombat`, `getStatefulCombatModifiers`, `getAuraCombatModifiers`, `canAttackAtRange`, `getStances`.
- Каждый вызов обёрнут в try/catch: ошибка одного handler'а → исходный state / пустой массив, поток игры не рвётся.
- Слаг героя берётся с бойца: `fighter.heroSlug ?? fighter.heroId` (heroSlug проставляется на game-init как `slugifyHeroName(name)`).

### Data-driven конфиги (`ability-config.ts`, `ABILITY_CONFIGS`)

Вместо хендлера-класса на каждого героя способность описывается декларативно и интерпретируется `GenericHeroAbilityHandler`:

```ts
interface AbilityConfig {
  heroId: string;              // слаг героя
  abilityName: string;
  description: string;
  rules: AbilityRule[];        // { trigger, condition?, effect, whenStance? }
  attackRange?: number;        // пассивная дальность атаки (Ms. Marvel — 2)
  stances?: StanceConfig[];    // стойки (см. ниже)
}
```

- **Триггеры (`AbilityTrigger`)**: `combat-passive`, `turn-start`, `turn-end`, `after-attack`, `after-defense`, `sidekick-defeated`, `enemy-hero-left-my-zone`.
- **Условия (`AbilityCondition`)**: `always`, `attacking/defending`, `self-health-below-defender`, `all-own-sidekicks-defeated`, `no-enemy-in-own-zone`, `won-combat / lost-combat / first-lost-combat-this-turn`, `has-not-maneuvered-this-turn`, `has-attacked-this-turn`, `won-combat-and-all-sidekicks-defeated`, `{ handSizeEquals: N }`.
- **Эффекты (`AbilityEffect`, по `kind`)**: `combat-modifier` (+N атака/защита/обе), `combat-modifier-per-count` (масштабируемый, Raptors), `aura-combat-modifier` (аура Oda-style), `turn` (draw/heal/gainAction/drawToHandSize), `pending-move`, `turn-damage` (авто-урон врагу в зоне/смежному + опц. thenDraw), `discard-random`, `reactive-damage`, `set-stance`, `cycle-stance`.

В `ABILITY_CONFIGS` описано **26 героев**: luke-cage, annie-christmas, eredin, bloody-mary, philippa, t-rex, bigfoot, chupacabra, deadpool, michelangelo, angel, golden-bat, ancient-leshen, raphael, robin-hood, leonardo, dracula, medusa, bullseye, bruce-lee, raptors, oda-nobunaga, achilles, tomoe-gozen, alice, muhammad-ali. Хендлеры-классы вручную реализованы только для части героев (`abilities/heroes/`: arthur, daredevil blind-boost, ms-marvel); остальные — через generic.

### Ауры

Аура (Oda-style) реализуется эффектом `aura-combat-modifier` → хуком `getAuraCombatModifiers`. Аура исходит от героя-ГРАНТИТЕЛЯ и применяется к дружественному бойцу-БЕНЕФИЦИАРУ, **делящему его зону**, во время боя бенефициара. Так как гранитель — другой герой, реестр консультирует ВСЕ зарегистрированные handler'ы; вклад суммируется аддитивно (только ADD) поверх карточных значений, heroMods и stateful-модификаторов.

### Стойки (STANCE-подсистема)

Стойка — постоянный режим героя, переключаемый в течение партии:

- Хранится в `metadata.heroStances[userId] = stanceId`. Дефолт — стойка с `default: true` (или первая).
- **Смена**: мутация `setStance` (бесплатная, seq +1) — при размещении, в начале хода, картами «Change size»; авто-эффекты `set-stance` (`to: '<id>' | 'toggle'`) и `cycle-stance` (следующая по циклу — для 3-стоечного Moon Knight).
- **Влияние**:
  - `StanceConfig.attackRange` — пассивная дальность атаки В ЭТОЙ стойке (переопределяет `config.attackRange`): Muhammad Ali FLOAT — range 2, STING — дальней атаки нет;
  - `StanceConfig.combat` — фиксированный combat-модификатор пока стойка текущая;
  - `AbilityRule.whenStance` — правило активно только в указанной стойке (Alice: атака-бонус в BIG, защита-бонус в SMALL).
- **GraphQL**: статичный справочник стоек — query `heroStances(heroSlug)` (см. B.3).

### Хуки: сводка точек вызова

| Хук | Кто диспетчеризуется | Точка в executor |
|---|---|---|
| `onTurnStart` | герой нового игрока | `advanceTurn`, после сброса флагов/добора |
| `onTurnEnd` | герой завершающего игрока | `advanceTurn`, в самом начале |
| `onAfterCombat` (attacker) | герой атакующего | конец `executeResolveCombat`, до передачи хода |
| `onAfterCombat` (defender) | герой защитника | сразу после атакующего, тот же ctx |
| `onFighterDefeated` | герой ВЛАДЕЛЬЦА павшего | после after-combat хуков и установки isDefeated |
| `onFighterMoved` | ВСЕ герои (кросс-реактивный) | `applyMoveReactions` — после executeManeuver, executeMoveFighter, resolvePendingEffect: дифф позиций ДО/ПОСЛЕ + пере-проверка game-over |
| `canAttackAtRange` | герой атакующего | `executeAttack`, если melee/ranged не достали |

## A.8. Вспомогательные сервисы

- **`engine/movement.service.ts`** — `executeMovement(state, fighterId, path)` (валидация пути + перемещение, seq +1).
- **`engine/adjacency.service.ts`** — `isAdjacent`, `isInSameZone` (пересечение зон), `manhattanDistance`, `getReachableCells(board, from, steps, { blockedPositions })` (BFS по проходимым клеткам).
- **`movement/astar.service.ts` + `path-cache.service.ts`** — A* и кэш путей.
- **`engine/value-modifier.service.ts`** — применение `ValueModifier[]` (ADD/SET/IGNORE/MULTIPLY) к значению боя.
- **`services/deck-management.service.ts`** — `drawCards` (добор, рефлеш колоды из сброса), `discardCard` (instance id); не трогают sequenceNumber.
- **`services/turn-management.service.ts`**, **`services/ai-decision.service.ts`** — менеджмент хода и AI-противник.
- **`validators/game-rules.validator.ts`** — валидация maneuver/movement/attack/defense/endTurn/pass/toggleDoor + `bannerAllows(bannerName, fighter)` (именные карты).

---

# Часть B. Контентная подсистема (`backend/src/content`)

## B.1. Хранение: Prisma-модели (PostgreSQL)

Схема: `backend/prisma/schema.prisma`. Три контентные модели:

### `Hero` (id — Prisma cuid)

| Поле | Тип | Описание |
|---|---|---|
| `name` (unique), `nameEn`, `nameRu` | String | Названия |
| `set` | String | Выпуск/дополнение (индекс) |
| `health` | Int | Здоровье |
| `fighterType` | String | HERO / MINION / HUGE |
| `movement` | Int (default 2) | Очки движения |
| `color` | String? | hex для UI |
| `ability` | Json | Способность(и) `{ type, timing, effect, description }` или массив |
| `deckCards` | Json | Стартовый состав колоды `[{cardId, count}]` |
| `properties` | Json? | `{ sidekickCount, sidekickHealth, ... }` |
| `sidekicks` | Json? | Сайдкики `[{ name, health, movement, attackType, avatarUrl }]` |
| `imageUrl`, `avatarUrl`, `characterCardUrl`, `miniModelUrl` | String? | Медиа (miniModelUrl — .glb) |
| `cards` | Card[] | Связь 1-N |

### `Card` (id — cuid)

`name/nameEn/nameRu`, `cardType` (ATTACK/DEFENSE/SCHEME/UNIVERSAL/VERSATILE/MANEUVER), `subType`, `attackValue/defenseValue/boostValue` (nullable), `bannerName` (кто может играть), `effects` (Json — `CardEffect[]`, см. A.2), текстовые поля эффекта по таймингам (`effectAfter/effectDuring/effectBoost/effectImmediately/effectOngoing`), `text/textEn/textRu`, `heroId` (FK), `count` (сколько экземпляров в колоде), `imageUrl`/`imageUrlRu`.

### `Board` (id — cuid)

`name` (unique)/`nameEn`/`nameRu`, `set`, `width`/`height`, `cells` (Json: `[{x, y, type, zone/zones, connections, isObstacle, ...}]`), `features` (Json: двери, тайные проходы, high ground), `imageUrl`/`imageUrlDark`.

### Сиды и заливки (`backend/prisma/`)

- `seed.ts`, `seed-heroes.ts`, `seed-all-scraped.ts` / `seed-scraped.ts` — базовый сид и заливка скрейпнутых данных.
- `update-card-images.ts`, `update-all-cards-images.ts`, `update-hero-images.ts`, `update-all-heroes.ts` — проставление URL картинок (`imageUrl`/`imageUrlRu` из скрейп-данных `image`/`imageRu`, только если поле ещё не заполнено).
- `backfill-card-effects.ts` — backfill `Card.effects` парсером текстов (`effect-text-parser`).
- `backfill-attack-type.ts`, `backfill-board-cells.ts` — нормализация типа атаки и клеток бордов.

## B.2. Сервисный слой

### `ContentDbService` (`content-db.service.ts`)

Единственный источник контента — БД (статические definition-файлы `content/data/` — локальный fallback). Redis-кэш (TTL 1 час, отключается `DISABLE_CACHE=true`, ключи `content:heroes:*`, `content:boards:*`, …). Версия контента — константа `CONTENT_VERSION = '2.0.0'` (query `contentVersion` — для инвалидации клиентского кэша; `getContentDiff(oldVersion)` — примитивный diff «всё изменилось»).

Методы: `getAllHeroes()`, `getHeroesPaginated(page, limit, set?)`, `getHeroById/Slug` (slug = cuid ИЛИ имя, case-insensitive), `getHeroesBySet(set)`, `getCardsByHero(heroId)` (через hero.deckCards), `getCardById(id)`, `getAllBoards()`, `getBoardsPaginated`, `getBoardById/Slug`, `getDefaultBoard()` (борд `cobble-city`), `getAllSets()` (distinct по Hero.set), `getContentSummary()`, `clearCache()`.

### `ContentMapper` (`mappers/content.mapper.ts`)

Prisma → DTO. Важные особенности контракта:

- **`HeroDto.id = hero.name`** (имя как публичный ID — совместимость с фронтом); Prisma cuid наружу не светится в hero-запросах.
- `movement` при маппинге героя захардкожен `3` (TODO в коде) — фактическое значение в движке берётся из `Fighter.movement` (default 2).
- Способности парсятся из `Hero.ability` (Json/string) в `[{ id, name, text, trigger }]`, trigger нормализуется к snake_case (`passive`, `start_of_turn`, `during_combat`, `when_attacked`, `when_defending`, `end_of_turn`).
- `CardDto`: `title = card.name`, `type` — нормализованный `CardType` (universal → VERSATILE), `value = attackValue ?? defenseValue ?? boostValue ?? 0`, `boost = boostValue`, `quantity = count`, `characterName`, `effects` (timing в snake_case, text с fallback на `Card.text`).
- `BoardDto`: `spaces` из `Board.cells`; зоны нормализуются через `ZONE_ALIASES` (violet→PURPLE, biege→BEIGE, blue-dark→BLUE и т.д.) — неизвестные ключи дропаются, иначе GraphQL-сериализация enum падала бы на весь boards-запрос.
- `HeroUrls { avatar, mini, cardCover }` собирается из `avatarUrl`/`imageUrl` героя.

## B.3. Контентные GraphQL-запросы

Резолверы: `ContentResolver` / `HeroResolver` (`content.resolver.ts`) — все `@Public()` (без авторизации). Админские `cardList`/`cardsList`/`heroList` — в `admin.resolver.ts` и требуют JWT. Query `heroStances` — в `games/game.resolver.ts`, тоже `@Public()`.

### Сводка query

| Query | Аргументы | Возврат | Auth |
|---|---|---|---|
| `heroes` | — | `[Hero]` | public |
| `heroesPaginated` | `page?, limit?, set?` | `PaginatedHeroes { items, pagination }` | public |
| `hero` | `id` (cuid **или** имя) | `Hero` (nullable) | public |
| `heroesBySet` | `set` | `[Hero]` | public |
| `cards` | `heroId` | `[Card]` | public |
| `card` | `id` (cuid) | `Card` (nullable) | public |
| `boards` | — | `[Board]` | public |
| `boardsPaginated` | `page?, limit?` | `PaginatedBoards` | public |
| `board` | `id` (имя, insensitive) | `Board` (nullable) | public |
| `sets` | — | `[String]` | public |
| `contentSummary` | — | `ContentSummary { version, heroesCount, boardsCount, setsCount, sets }` | public |
| `contentVersion` | — | `String` | public |
| `heroStances` | `heroSlug` (слаг, напр. `muhammad-ali`) | `[StanceOption { id, label, isDefault }]` (для не-стоечных героев `[]`) | public |
| `cardList` / `cardsList` | `page?, limit?, heroId?, search?, sortBy?, sortOrder?` | `CardsPaginated` | **JWT** |
| `clearContentCache` | — | `Boolean` | public (admin-инструмент) |

### Типы (DTO, `content.dto.ts`)

```graphql
type Hero {
  id: String!          # = имя героя
  name: String!
  nameEn: String
  nameRu: String
  health: Int!
  movement: Int!
  set: String!
  abilities: [HeroAbility!]!   # { id, name, text, trigger }
  cards: [Card!]!              # nested, резолвится HeroResolver.getCards
  fighterType: FighterType!    # HERO | SIDEKICK
  sidekickCount: Int
  sidekickHealth: Int
  urls: HeroUrls               # { avatar, mini, cardCover }
  imageUrl: String             # админ-поля (Prisma-совместимость)
  avatarUrl: String
  createdAt: DateTime
  updatedAt: DateTime
}

type Card {
  id: String!          # Prisma cuid
  title: String!       # = Card.name
  type: CardType!      # ATTACK | DEFENSE | SCHEME | VERSATILE
  value: Int!          # attack ?? defense ?? boost ?? 0
  boost: Int!
  quantity: Int!       # = count
  characterName: String!
  effects: [CardEffect!]!  # { id, timing (snake_case), text }
  imageUrl: String
  imageUrlRu: String
}

type Board {
  id: String!          # = имя борда
  name: String!
  width: Int!
  height: Int!
  recommendedPlayers: Int!
  spaces: [BoardSpace!]!   # { position {x,y}, zones: [Zone], isObstacle }
  imageUrl: String
}
# Zone enum: BLUE GREEN YELLOW RED PURPLE BROWN GRAY ORANGE PINK WHITE GOLD BEIGE
```

Замечание: поле `cards` внутри `Hero` резолвится отдельным field-resolver'ом (`HeroResolver.getCards` → `getHeroBySlug(hero.id).deckCards`), поэтому при query `heroes { cards { … } }` выполняется N+1 запросов к БД/кэшу — для массовой загрузки предпочтительнее `hero(id) { cards }` по одному.

## B.4. Статические ассеты (`public/assets/**`)

Ассеты лежат в **`public/assets/`** на фронте (Vite `publicDir: 'public'`, см. `vite.config.ts`); URL, хранящиеся в БД (`imageUrl` и т.д.), — корневые пути вида `/assets/…`, т.е. клиент резолвит их относительно хоста фронтенда/CDN (бэкенд Nest сам их не раздаёт). Манифест соответствий — `public/assets/decks/card-assets.generated.json` (`{ heroes: { <slug>: { cards: [{ id, title, imageUrl, imageUrlRu }] } } }`).

### Структура и именование

```
public/assets/
├── boards/
│   └── hells-kitchen.webp                          # борд по слагу: /assets/boards/<slug>.webp
├── decks/<hero-slug>/                              # карты колоды героя
│   ├── <card-slug>.webp                            # EN: /assets/decks/daredevil/grappling-hook.webp
│   └── ru/<card-slug>-ru.png                       # RU: /assets/decks/daredevil/ru/grappling-hook-ru.png
│       (hero-slug: daredevil, ms-marvel, blackbeard, deadpool, muhammad-ali, yennefer-triss, …)
├── heroes/<hero-slug>/                             # медиа героя
│   ├── avatar.webp                                 # /assets/heroes/daredevil/avatar.webp
│   ├── mini.webp
│   └── card-cover.webp
├── ui/                                             # HUD/эффекты
│   ├── hud/    (hand-tray.png, deck-slot.png, player-panel-*.png, …)
│   └── effects/ (move-highlight.png, attack-highlight.png, defense-shield.png, …)
└── phaser/      (README)
```

**URL-паттерны:**

| Ассет | Паттерн |
|---|---|
| Карта EN | `/assets/decks/<heroSlug>/<cardSlug>.webp` |
| Карта RU | `/assets/decks/<heroSlug>/ru/<cardSlug>-ru.png` |
| Аватар героя | `/assets/heroes/<heroSlug>/avatar.webp` |
| Миниатюра героя | `/assets/heroes/<heroSlug>/mini.webp` |
| Обложка карты героя | `/assets/heroes/<heroSlug>/card-cover.webp` |
| Изображение борда | `/assets/boards/<boardSlug>.webp` |

Канонический источник URL карты — `Card.imageUrl` / `Card.imageUrlRu` из GraphQL-ответа (проставлены сидами `update-*-images.ts`); манифест `card-assets.generated.json` — альтернатива/дублирующий справочник, если нужно скачать всё пачкой.

## B.5. Примеры GraphQL-запросов для загрузки контента в Unreal

Все запросы — публичные (кроме `cardList`). Endpoint GraphQL — стандартный (см. `docs/backend-api` overview, обычно `POST /graphql`).

### 1. Список всех героев (легковесный каталог)

```graphql
query AllHeroes {
  heroes {
    id            # имя героя — публичный ключ
    name
    nameEn
    nameRu
    health
    movement
    set
    fighterType
    sidekickCount
    sidekickHealth
    urls { avatar mini cardCover }
    imageUrl
    avatarUrl
  }
}
```

### 2. Полные данные героя (включая колоду и способности)

```graphql
query HeroDetails($id: String!) {
  hero(id: $id) {          # $id — имя героя или Prisma cuid
    id
    name
    health
    movement
    set
    fighterType
    sidekickCount
    sidekickHealth
    urls { avatar mini cardCover }
    abilities { id name text trigger }
    cards {
      id
      title
      type        # ATTACK | DEFENSE | SCHEME | VERSATILE
      value
      boost
      quantity
      characterName
      imageUrl
      imageUrlRu
      effects { id timing text }
    }
  }
}
```

### 3. Карты конкретного героя (без остального hero-объекта)

```graphql
query HeroCards($heroId: String!) {
  cards(heroId: $heroId) {
    id title type value boost quantity
    characterName imageUrl imageUrlRu
    effects { id timing text }
  }
}
```

### 4. Все борды (геометрия досок)

```graphql
query AllBoards {
  boards {
    id
    name
    width
    height
    recommendedPlayers
    imageUrl
    spaces { position { x y } zones isObstacle }
  }
}
```

### 5. Справочник стоек героя (STANCE HUD)

```graphql
query HeroStanceOptions($heroSlug: String!) {
  heroStances(heroSlug: $heroSlug) {   # напр. "muhammad-ali"
    id
    label
    isDefault
  }
}
# Для героев без стоек вернётся [] — HUD ничего не рендерит.
```

### 6. Версия контента и сводка (инвалидация кэша клиента)

```graphql
query ContentMeta {
  contentVersion          # "2.0.0" — изменилась → перезагрузить контент
  contentSummary {
    version
    heroesCount
    boardsCount
    setsCount
    sets                  # список дополнений
  }
}
```

### 7. Пагинированные списки

```graphql
query HeroesPage($page: Int!, $limit: Int!, $set: String) {
  heroesPaginated(page: $page, limit: $limit, set: $set) {
    items { id name health set urls { avatar } }
    pagination { total page limit totalPages hasNextPage hasPreviousPage }
  }
}
```

### Рекомендуемый порядок загрузки в Unreal

1. `contentVersion` / `contentSummary` — сверить с локальным кэшем; совпало → ничего не качать.
2. `AllHeroes` — каталог + URL ассетов (avatars).
3. `HeroDetails` для выбранных героев (или всех) — колоды, способности, ссылки на карты.
4. `AllBoards` — геометрия досок.
5. `HeroStanceOptions` для stance-героев.
6. Скачать webp/png по URL-паттернам из B.4 (`/assets/decks/<slug>/…`, `/assets/heroes/<slug>/…`, `/assets/boards/<slug>.webp`) — с хоста фронтенда/CDN.
8. В процессе матча — игровые мутации и подписки (`game.graphql`) поверх этого контента.

---

## Приложение: соответствие файлов

| Тема | Файл |
|---|---|
| GameState/фазы/PendingEffect | `backend/src/game-engine/models/game-state.model.ts` |
| Card/CardEffect/EffectType/EffectTiming | `backend/src/game-engine/models/card.model.ts` |
| Fighter/attackType/слаги | `backend/src/game-engine/models/fighter.model.ts` |
| Board/Cell/зоны | `backend/src/game-engine/models/board.model.ts` |
| Оркестратор действий (ходы, бой, хуки) | `backend/src/game-engine/services/game-action-executor.service.ts` |
| Реестр способностей + интерфейсы хуков | `backend/src/game-engine/abilities/hero-ability-registry.ts` |
| Data-driven конфиги способностей/стоек | `backend/src/game-engine/abilities/ability-config.ts` |
| Generic-интерпретатор ABILITY_CONFIGS | `backend/src/game-engine/abilities/generic-hero-ability.handler.ts` |
| Исполнитель эффектов карт | `backend/src/game-engine/effects/card-effect-executor.service.ts` |
| Парсер текстов карт в эффекты | `backend/src/game-engine/effects/effect-text-parser.ts` |
| Бой (низкий уровень) | `backend/src/game-engine/engine/combat-resolver.service.ts` |
| Смежность/зоны/достижимость | `backend/src/game-engine/engine/adjacency.service.ts` |
| Валидация правил | `backend/src/game-engine/validators/game-rules.validator.ts` |
| Контент: сервис | `backend/src/content/content-db.service.ts` |
| Контент: резолверы | `backend/src/content/content.resolver.ts` |
| Контент: DTO (GraphQL-схема) | `backend/src/content/dto/content.dto.ts` |
| Контент: маппинг Prisma→DTO | `backend/src/content/mappers/content.mapper.ts` |
| heroStances query | `backend/src/games/game.resolver.ts` |
| cardList/cardsList (auth) | `backend/src/admin/admin.resolver.ts` |
| Prisma-схема Hero/Card/Board | `backend/prisma/schema.prisma` |
| GraphQL-документы фронта | `src/graphql/queries/cards.graphql`, `src/graphql/queries/heroes.graphql` |
| Манифест ассетов колод | `public/assets/decks/card-assets.generated.json` |
