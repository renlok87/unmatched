# План: оставшиеся фичи Unmatched (подробная версия)

> **For Claude:** REQUIRED SUB-SKILL: superpowers:executing-plans — исполнять позадачно, с верификацией после каждой фазы и коммитом (`--no-verify`, pre-commit hook сломан).

**Goal:** Довести игру до полноценно играбельной: карты исполняют свои эффекты (тексты → механика), BOOST работает во всех трёх местах (манёвр/атака/защита), основной фронт (5174) играет против реального API.

**Architecture:** Расширяем существующее — `CardEffect`/executor в game-engine дочиняются (никаких параллельных «EffectV2»), источник структурированных эффектов — Prisma `Card.effects` Json (парсер текстов + ручная правка через админку), фронт подключается адаптером wire→локальный формат без переписывания Phaser-сцены (1178 строк остаются как есть, патчится 2 функции).

**Tech Stack:** NestJS + GraphQL code-first + Prisma/PostgreSQL (бэк в docker, **bind mount** `./backend:/app` — деплой `docker exec unmatched-backend npm run build && docker compose restart backend`, образ НЕ пересобирать); React + Apollo Client (HTTP+WS split, graphql-ws) + Phaser 3 + zustand (фронт); jest юниты + e2e node-скрипты через GraphQL + Game Tester в админке (5480).

---

## Контекст и факты разведки

### Что уже работает (e2e PASS)
Полный игровой цикл: лобби (create→join→selectHero×2→ready×2→start) → `GameInitializationService` (колоды из `hero.cards ×count`, рука 5, бойцы с movement/attackType, доска из `Board.cells`) → ходы по 2 действия (`metadata.actionsRemaining`, `consumeAction`, авто-`advanceTurn` при 0 с добором 1 карты) → BFS-валидация движения → melee/ranged бои (ranged = смежно ИЛИ та же зона) → `playScheme` → GAME_OVER. Realtime: PubSub-подписки, event-лог `GameAction`, лобби-события. Optimistic lock: `sequenceNumber` строго +1 на мутацию.

### Состояние данных (проверено SQL по живой БД)
- 880 карт: VERSATILE 348, ATTACK 267, SCHEME 151, DEFENSE 114.
- **`Card.effects` (Json) пуст у всех 880** — структурированных эффектов 0.
- Тексты эффектов лежат в отдельных колонках: `effectDuring` у 200 карт, `effectAfter` у 452, `effectImmediately` у 126, `effectBoost` у 6, `effectOngoing` у 7. Всего 778 текстов, 576 уникальных.
- 84 героя: attackType melee 53 / range 17 / null 14. Сайдкики у 68. `Hero.ability` Json `{type: CUSTOM|VILLAIN|MINION, timing: PASSIVE, effect: <текст>}`.
- `Board.cells` забэкфилнуты у 30/30 досок, формат `{x, y, zones: ["blue", ...]}` — **массив зон**, но engine-модель `Cell.zone` хранит одну строку (мультизонность теряется в `buildBoardState`).
- Админ-API `updateCard` уже принимает `effects` как JSON-строку — `backend/src/admin/admin.service.ts:371`.

### Подтверждённые чтением кода дефекты (чинятся в A0 / B2)
1. **Реестр способностей героев мёртв.** Handlers регистрируются по слагам: `daredevil.handler.ts` → `heroId = 'daredevil'`, `ms-marvel.handler.ts:52` → `'ms-marvel'`. Но `Fighter.heroId` получает Prisma cuid (`cmq7d4b840010wi20x98gdv27`). `combatResolver.applyCombatModifiers(attacker.heroId, ...)` → `registry.get(cuid)` → handler никогда не находится. BLIND BOOST Daredevil и ability Arthur не работают вообще.
2. **resolveCombat бьёт не ту цель.** `executeAttack` пишет `defenderId: target.ownerId` (id ИГРОКА — `game-action-executor.service.ts:498`), а `executeResolveCombat` берёт `fighters.find(f => f.ownerId === combatInfo.defenderId)` (`:758`) — **первого** бойца владельца, не атакованного сайдкика. Атака по гарпии ранит Медузу.
3. **Подписка фронта мертва.** `src/hooks/useGameSync.ts:112` шлёт `since: Date.now()/1000` (timestamp), бэк сравнивает `since` с `sequenceNumber` (`game-subscription.resolver.ts:163`) → фильтр отсекает ВСЕ события.
4. **remoteGameStore не парсит wire.** `src/store/remoteGameStore.ts:239-244` типизирует ответ `gameState` как уже распарсенный объект, а реально приходит `{ state: string }` → стор никогда не работал с реальными данными.
5. **GameScene показывает чужую руку.** `createCards()/drawCardArea()` рендерят руку игрока, чей сейчас ход (`getCurrentPlayer`), а не локального — в мультиплеере при ходе соперника показалась бы его рука (она и так скрыта бэком, но UI сломается).
6. **В `src/graphql/mutations/game.graphql` нет операции `PlayScheme`** — типы в `src/gql/graphql.ts` есть, документа нет.
7. `executeCombatEffects`/`executeAfterCombatEffects` в `card-effect-executor.service.ts` вызываются **только из spec-файлов** — в прод-потоке боя участвует лишь combat-resolver. `executeOnPlayEffects` подключён к playScheme, но спит (effects пусты).
8. Внутри executor методы `drawCards`/`discardCards` — заглушки-TODO, HEAL реализован как бессмысленный отрицательный attack-модификатор. Рабочие draw/discard живут в `DeckManagementService` — их и надо инжектить.

### Принятые решения
- **Порядок: блок A (бэкенд-логика) → блок B (фронт)** — продолжение линии «сначала проработка логики».
- **MVP-герои:** волна 1 — **Medusa vs King Arthur**, волна 1.5 — **Daredevil**, **Ms. Marvel отложена**.

| Герой | Почему |
|---|---|
| Medusa (11 карт, 9 с эффектами) | Все тексты ложатся на базовый DSL: Draw 1/2, opponent discards, «If you won the combat, deal 8 damage» (Gaze of Stone), «You may BOOST», Move up to 3, Feint-cancel. Ranged + сайдкики-гарпии → реально тестирует banner-валидацию (Clutching Claws — banner Harpy) и фикс targetFighterId |
| King Arthur (16 карт, 11 с эффектами) | Handler уже есть (`arthur.handler.ts`), ability = BOOST атаки → тестирует boostCardId в атаке. Тексты: draw, move, prevent all damage, place, heal-conditional |
| Daredevil (волна 1.5) | Handler BLIND BOOST уже написан — оживает после фикса слагов (A0); 8 карт: value-replace при пустой колоде, cancel, lose-combat damage |
| Ms. Marvel — отложить | 6 из 11 карт завязаны на «shares no zones» — мультизонность потеряна в engine (блок C) |

- **Интерактивные эффекты** («Move up to 3», PLACE — требуют выбора игрока): в MVP распознаются парсером, но уходят в `ActionResult.metadata.manualEffects: string[]` — точный паритет с текущим playScheme→effectText поведением Game Tester. Механика pendingEffects + мутация выбора — блок C.
- **Нераспознанный текст** → эффект `{type: UNSUPPORTED, text: <raw>}` + warn-лог + метрика. Игра никогда не блокируется.
- **Инвариант seq:** стадии эффектов НЕ трогают `sequenceNumber` (как DeckManagementService); ровно +1 на мутацию делает executor действия. Закрывается юнитом ДО рефакторинга боя.

---

# Блок A — Бэкенд: система эффектов карт (~2 недели)

## A0. Багфиксы-энейблеры (день)

**Files:**
- Modify: `backend/src/game-engine/models/game-state.model.ts` (CombatState)
- Modify: `backend/src/game-engine/models/fighter.model.ts` (heroSlug)
- Modify: `backend/src/game-engine/services/game-action-executor.service.ts` (:498, :567, :758)
- Modify: `backend/src/game-engine/engine/combat-resolver.service.ts` (lookup heroSlug)
- Modify: `backend/src/games/services/game-initialization.service.ts` (запись heroSlug)
- Modify: `backend/src/games/game-state.service.ts` (serialize/deserialize heroSlug, targetFighterId)

**Шаги:**
1. `CombatState` + `targetFighterId?: string` (optional — легаси-сейвы живы). `executeAttack` пишет `targetFighterId: target.id` рядом с `defenderId` (defenderId-userId оставить — на нём guard «кто играет защиту»). `executeResolveCombat` и `executePlayDefense` ищут цель так: `targetFighterId` есть → по нему; нет (легаси) → старый путь по `ownerId`.
2. `Fighter` + `heroSlug?: string`. В `game-initialization.service.ts` писать `slugify(hero.name)` ('Ms. Marvel' → 'ms-marvel', lowercase, пробелы/точки → дефис). Юнит на slugify с реальными именами героев из handlers.
3. `hero-ability-registry.ts` ничего не меняет; правится **вызывающая сторона**: `combat-resolver.service.ts` — `registry.applyCombatModifiers(fighter.heroSlug ?? fighter.heroId, ...)` (двойной lookup heroId→heroSlug допустим внутри registry.getAny, выбрать одно место).
4. serialize/deserialize: новые wire-ключи `f[].hs` (heroSlug), `m.combatInfo.tf` (targetFighterId) — по образцу существующих `mv`/`at`/`ar`.

**Верификация:**
```bash
docker exec unmatched-backend npx jest --testPathPattern="game-engine"   # старые зелёные
# новые юниты: атака по сайдкику ранит сайдкика (не героя владельца);
# registry находит daredevil-handler у Fighter{heroId: cuid, heroSlug: 'daredevil'}
docker exec unmatched-backend npm run build && docker compose -f "C:/Users/ren/WebstormProjects/unmached/unmached/docker-compose.yml" restart backend
```
E2e руками в Game Tester: сетап с героем-с-сайдкиком, `attack f0 f3 c1` по сайдкику → урон именно сайдкику.

**Коммит:** `fix(engine): targetFighterId в бою + heroSlug для реестра способностей`

## A1. Модель/DSL (день)

**Files:**
- Modify: `backend/src/game-engine/models/card.model.ts`
- Modify: `backend/src/games/services/game-initialization.service.ts`

**Полная схема расширения (расширяем существующие enum'ы, существующие 8 значений сохраняются):**

```ts
export enum EffectType {
  MODIFY_ATTACK = 'MODIFY_ATTACK',   // legacy, остаётся
  MODIFY_DEFENSE = 'MODIFY_DEFENSE', // legacy, остаётся
  DAMAGE = 'DAMAGE', HEAL = 'HEAL', MOVE = 'MOVE', PLACE = 'PLACE',
  DRAW_CARD = 'DRAW_CARD', DISCARD = 'DISCARD',
  // новые:
  MODIFY_VALUE = 'MODIFY_VALUE',       // +N к значению СВОЕЙ карты (роль атака/защита решается в бою — нужно для VERSATILE)
  SET_VALUE = 'SET_VALUE',             // «the value of this card is N instead»
  VALUE_PER_COUNT = 'VALUE_PER_COUNT', // +N за каждую сущность из count
  BOOST = 'BOOST',                     // добавить BOOST-значение карты из boostSource
  CANCEL_EFFECTS = 'CANCEL_EFFECTS',   // «Cancel all effects on your opponent's card»
  OPPONENT_DISCARD = 'OPPONENT_DISCARD',
  RETURN_TO_HAND = 'RETURN_TO_HAND',   // вернуть эту карту в руку
  IMMOBILIZE = 'IMMOBILIZE',           // «cannot leave their space this turn»
  GAIN_ACTION = 'GAIN_ACTION',
  PREVENT_DAMAGE = 'PREVENT_DAMAGE',   // «Prevent all damage»
  END_TURN = 'END_TURN',
  UNSUPPORTED = 'UNSUPPORTED',         // маркер нераспознанного текста
}

export enum EffectTiming {
  BEFORE_COMBAT = 'BEFORE_COMBAT', DURING_COMBAT = 'DURING_COMBAT',
  AFTER_COMBAT = 'AFTER_COMBAT', ON_PLAY = 'ON_PLAY', ON_DISCARD = 'ON_DISCARD',
  TURN_START = 'TURN_START', TURN_END = 'TURN_END',
  ON_REVEAL = 'ON_REVEAL',             // effectImmediately — при вскрытии карт в COMBAT_RESOLVE
}

export enum EffectTarget {
  ATTACKER = 'ATTACKER', DEFENDER = 'DEFENDER', SELF = 'SELF',
  ALL_ENEMIES = 'ALL_ENEMIES', ALL_ALLIES = 'ALL_ALLIES',
  OPPOSING_FIGHTER = 'OPPOSING_FIGHTER',                 // противник в текущем бою
  ENEMIES_ADJACENT_TO_SELF = 'ENEMIES_ADJACENT_TO_SELF', // «each opposing fighter adjacent to your fighter»
  ADJACENT_ENEMY = 'ADJACENT_ENEMY',                     // один смежный враг (MVP: первый валидный + warn)
  NAMED_FIGHTER = 'NAMED_FIGHTER',                       // «Move Daredevil…» — по fighterName
  OPPONENT_PLAYER = 'OPPONENT_PLAYER',                   // для OPPONENT_DISCARD
}

export type EffectConditionKind =
  | 'WON_COMBAT' | 'LOST_COMBAT'            // атакующий выиграл при finalAttack > finalDefense; ничья — за защитником
  | 'IS_ATTACKING' | 'IS_DEFENDING'
  | 'ADJACENT_TO_OPPONENT' | 'NOT_ADJACENT_TO_OPPONENT'
  | 'DECK_EMPTY' | 'HAND_COUNT_AT_MOST' | 'HAND_COUNT_AT_LEAST'
  | 'HEALTH_AT_MOST'
  | 'MOVED_THIS_TURN'                       // «started this turn in a different space» (Momentous Shift, 12 карт)
  | 'OPPONENT_IS_HERO';

export interface EffectCondition { readonly kind: EffectConditionKind; readonly value?: number; }

export type CountSource =
  | 'FRIENDLY_ADJACENT_TO_OPPONENT'  // «for each other friendly fighter adjacent to the opposing fighter»
  | 'CARDS_IN_HAND'                  // «equal to the number of cards in your hand» (с SET_VALUE 0)
  | 'DISCARD_NAME_PREFIX'            // «for each other VOYAGE card in your discard pile»
  | 'DAMAGE_DEALT' | 'DAMAGE_TAKEN'; // «Draw cards equal to the amount of combat damage…»

export interface CountSpec { readonly source: CountSource; readonly namePrefix?: string; readonly per?: number; }

export type BoostSource = 'PLAYER_CHOICE_HAND' | 'SELF_DECK_TOP' | 'OPPONENT_RANDOM_HAND';

export interface CardEffect {
  readonly id: string;
  readonly type: EffectType;
  readonly timing: EffectTiming;
  readonly target?: EffectTarget;
  readonly value?: number;
  readonly condition?: string;          // legacy-строка, остаётся для старых данных
  // новые поля (все optional — обратная совместимость сейвов):
  readonly when?: EffectCondition;      // структурное условие
  readonly count?: CountSpec;           // для VALUE_PER_COUNT / draw-per-damage
  readonly optional?: boolean;          // «You may …»
  readonly fighterName?: string;        // для NAMED_FIGHTER
  readonly boostSource?: BoostSource;   // для BOOST
  readonly blind?: boolean;             // BLIND BOOST (Daredevil)
  readonly text?: string;               // исходное предложение — для лога/manualEffects
  readonly source?: 'parser' | 'manual';
  readonly parserVersion?: number;
}

// Card: + readonly bannerName?: string
// (subType в БД пуст — НЕ переносить, YAGNI)
```

**Шаги:**
1. Расширить enum'ы/интерфейсы по схеме (старые значения не трогать).
2. `Card` + `bannerName?`.
3. `game-initialization.service.ts`: при сборке колод переносить `card.bannerName` и `normalizeCardEffects(prismaCard.effects)` — структурная валидация Json: валидный массив → как есть; строка с двойной сериализацией → JSON.parse повторно; мусор → один эффект `{type: UNSUPPORTED, text: String(raw)}`. Не падать никогда.
4. `game-state.service.ts` реэкспортирует engine-модели — новые поля доступны в games-модуле автоматически. serialize: `effects` карт сохранять в decks/руках (проверить что текущая сериализация карт пишет объект целиком; если поля перечислены явно — добавить).

**Верификация:** `npm run build` (в контейнере) зелёный; юниты `normalizeCardEffects` (валидный массив / двойная сериализация / мусор / null).

**Коммит:** `feat(engine): DSL эффектов карт — расширение CardEffect, bannerName, нормализация`

## A2. Парсер текстов + backfill (2–3 дня)

**Files:**
- Create: `backend/src/game-engine/effects/effect-text-parser.ts` — **чистый модуль без Nest DI** (импортируется из prisma-скрипта и тестов)
- Create: `backend/src/game-engine/effects/effect-text-parser.spec.ts`
- Create: `backend/prisma/backfill-card-effects.ts` (по образцу `backfill-attack-type.ts`)

**Архитектура парсера:** вход — `{ immediately?, during?, after?, boost?, ongoing? }` (текстовые поля карты). Тайминг от поля-источника: `effectImmediately→ON_REVEAL`, `effectDuring→DURING_COMBAT`, `effectAfter→AFTER_COMBAT`, `effectOngoing→UNSUPPORTED` (7 карт, отложено). Для каждого поля: сначала компаунд-матчеры по полному тексту, затем разбивка на предложения и по-предложенный матчинг; нераспознанное предложение → `UNSUPPORTED` с исходным текстом. Каждый результат: `text` = исходное предложение, `source:'parser'`, `parserVersion:1`.

**Таблица паттернов (регэкспы /i, покрытие — вхождений из 778 текстов):**

| # | Паттерн | → Эффект | Покрытие |
|---|---|---|---|
| 1 | `^cancel all effects on your opponent'?s card\.?$` | CANCEL_EFFECTS | 70 |
| 2 | `draw (\d+) cards?\.?$` | DRAW_CARD value=N | 106 |
| 3 | компаунд `^draw 1 card\. if you won the combat, draw 2 cards instead\.$` | DRAW 1 (when: LOST_COMBAT-или-ничья) + DRAW 2 (when: WON_COMBAT) | 17 |
| 4 | префикс-обёртка `^if you won the combat,?\s*(.+)$` → рекурсивный парс остатка с `when:{WON_COMBAT}` | wrap | 97 |
| 5 | `^if you lost (the\|a)? combat,?\s*(.+)$` → `when:{LOST_COMBAT}` | wrap | 20 |
| 6 | `deal (\d+) damage to (the opposing fighter\|an adjacent opposing fighter\|each opposing fighter adjacent to your fighter)` | DAMAGE + target по альтернативе | 88 |
| 7 | `move (your fighter\|the opposing fighter\|[A-Z][\w. ']+?\|one of your fighters) up to (\d+) spaces?` | MOVE → в MVP manualEffects | 93 |
| 8 | `(?:if (.+?), )?the value of this card is (\d+)( instead)?` | SET_VALUE + when (`started this turn in a different space`→MOVED_THIS_TURN, `no cards in your deck`→DECK_EMPTY, `opposing fighter is a hero`→OPPONENT_IS_HERO, `is not adjacent`→NOT_ADJACENT_TO_OPPONENT) | 58 |
| 9 | `value of this card is equal to the number of cards in your hand` | SET_VALUE 0 + VALUE_PER_COUNT{CARDS_IN_HAND} | 3 |
| 10 | `(add )?\+?(\d+) to this card'?s value for each (other friendly fighter adjacent to the opposing fighter\|other (\w+) card in your discard pile)` | VALUE_PER_COUNT | 21 |
| 11 | `you may BOOST this (attack\|card)` | BOOST{PLAYER_CHOICE_HAND, optional} | 36 |
| 12 | `you may BLIND BOOST this (attack\|card)` | BOOST{SELF_DECK_TOP, blind} | 6 |
| 13 | `discard the top card of your deck\. add its BOOST value…` / `your opponent discards 1 random card\. add its BOOST value…` | BOOST{SELF_DECK_TOP} / BOOST{OPPONENT_RANDOM_HAND} | 14 |
| 14 | `your opponent discards (\d+) (random )?cards?` | OPPONENT_DISCARD (не-random → MVP random + warn) | 28 |
| 15 | `([\w. ']+ )?recovers? (\d+) health` | HEAL (+NAMED_FIGHTER если имя) | 32 |
| 16 | `gain (\d+) actions?` | GAIN_ACTION | 34 |
| 17 | `return this card to your hand` | RETURN_TO_HAND | 8 |
| 18 | `cannot leave (her\|his\|their) spaces? (this\|for the rest of the) turn` | IMMOBILIZE | 4 |
| 19 | `^prevent all damage` | PREVENT_DAMAGE | 2 |
| 20 | `^end the turn\.?$` | END_TURN | 5 |
| 21 | `place (your fighter\|[A-Z][\w ']+) in any space( in … zone)?` | PLACE → manualEffects | 11 |

Суммарно ~60–70% всех вхождений авто; для Medusa/Arthur/Daredevil ~100% (остаток руками). **Осознанно отложено** (UNSUPPORTED + лог): зоны/мультизоны («shares no zones»), токены героев (Hellfire, Rage, cauldron), «choose one effect», «look at opponent's hand», «shuffle into deck», swap spaces.

**Backfill-скрипт:** флаги `--hero=<name>`, `--dry-run`, `--force`; печатает отчёт покрытия (parsed/unsupported по героям); **не перезаписывает эффекты с `source:'manual'`**; идемпотентен. Запуск:
```bash
docker exec unmatched-backend npx ts-node --transpile-only prisma/backfill-card-effects.ts -- --dry-run
docker exec unmatched-backend npx ts-node --transpile-only prisma/backfill-card-effects.ts -- --hero=Medusa
```

**Ручная доводка** остатка MVP-героев — через существующий админ-API `updateCard` (`admin.service.ts:371`, принимает effects JSON-строкой). Textarea для `effects` в админ-UI карточки (`admin/src/pages/cards/`) — мелкая подзадача в этой же фазе.

**Верификация:** jest-фикстуры на КАЖДЫЙ паттерн с реальными текстами из БД; dry-run по всей базе без исключений; SQL-проверка: у Medusa/Arthur/Daredevil 0 карт с непустым текстом эффекта и пустым `effects`.

**Коммит:** `feat(engine): парсер текстов эффектов + backfill-card-effects`

## A3. Доделка executor (2–3 дня)

**Files:**
- Modify: `backend/src/game-engine/effects/card-effect-executor.service.ts` (+spec)
- Modify: `backend/src/game-engine/game-engine.module.ts` (DI)
- Modify: `backend/src/game-engine/services/game-action-executor.service.ts` (advanceTurn — снапшот позиций)

**Шаги:**
1. Инжект `DeckManagementService` + `AdjacencyService`. Заглушки `drawCards`/`discardCards` внутри executor → реальные вызовы DeckManagementService. DAMAGE/HEAL — иммутабельные правки `state.fighters` (map по id), убрать HEAL-хак через отрицательный valueModifier.
2. `evaluateCondition` → структурный `when`: WON/LOST из расширенного `CombatContext {finalAttack, finalDefense, role}`; DECK_EMPTY/HAND_COUNT из состояния; ADJACENT через AdjacencyService; MOVED_THIS_TURN — сравнение с `metadata.turnStartPositions` (снапшот позиций писать в `advanceTurn`). Legacy-строка `condition` продолжает работать для старых данных.
3. `resolveTargets`: новые таргеты (OPPOSING_FIGHTER из combatInfo, ENEMIES_ADJACENT_TO_SELF через adjacency, NAMED_FIGHTER по `fighterName`, OPPONENT_PLAYER). ADJACENT_ENEMY при нескольких кандидатах — первый валидный + warn (MVP-упрощение, до pendingEffects).
4. Новый `executeRevealEffects(state, attackerCard, defenderCard, ctx)`: эффекты атакующего → защитника; `CANCEL_EFFECTS` выставляет cancel-флаг противоположной карте. Семантика отмены: отменённая карта не исполняет ни reveal-, ни during-, ни after-эффекты; печатное значение (attackValue/defenseValue) сохраняется; отменённый защитник не отменяет в ответ (его reveal уже не исполняется). `isTimingValid`: ON_REVEAL валиден в COMBAT_RESOLVE.
5. Порядок применения внутри during: `SET_VALUE` → `MODIFY_VALUE/MODIFY_ATTACK/MODIFY_DEFENSE` → `VALUE_PER_COUNT`. `PREVENT_DAMAGE` выставляет флаг в контекст.
6. UNSUPPORTED → `{success: false, manual: true}` → попадает в manualEffects + счётчик-метрика (warn-лог с текстом).

**Верификация (юниты):** инвариант «эффекты не меняют sequenceNumber»; порядок SET→MODIFY→PER_COUNT; отмена гасит SET_VALUE но не печатное значение; DAMAGE/HEAL иммутабельны; draw через DeckManagementService уважает maxSize и recycleDeck.

**Коммит:** `feat(engine): рабочий card-effect-executor — reveal/cancel, структурные условия, реальные draw/discard`

## A4. Интеграция в бой (2 дня)

**Files:**
- Modify: `backend/src/game-engine/services/game-action-executor.service.ts` (executeResolveCombat)
- Modify: `backend/src/game-engine/engine/combat-resolver.service.ts` (seq, повторный урон)
- Check: `backend/src/game-engine/game-execution.integration.spec.ts` (ожидания по seq)

**Пайплайн executeResolveCombat** (карты ищутся по instance-id из `combatInfo` — обе уже в сбросе, `findCardById` executor'а сбросы ищет):
1. **ON_REVEAL** — `executeRevealEffects`: атакующий → защитник, cancel-флаги.
2. **DURING_COMBAT** — расширенный `executeCombatEffects`: вход = базовые значения из combatInfo + boost (фаза A7) + hero-модификаторы из registry (ожили в A0) → выход `finalAttack/finalDefense`.
3. **Урон** — существующий `combat-resolver.applyDamage` с `targetFighterId` (A0) и учётом PREVENT_DAMAGE. **Инкремент seq из applyDamage убрать** — единый +1 остаётся в executor (иначе двойной инкремент ломает optimistic lock). Дубль-применение урона в executeResolveCombat убрать — использовать результат resolver'а.
4. **AFTER_COMBAT** — с исходом боя в контексте (`attackerWon = finalAttack > finalDefense`, ничья — за защитником): **сначала ВСЕ эффекты атакующего, затем защитника** (правило Unmatched), отменённые карты пропускаются. Реальные DRAW (DeckManagementService), DAMAGE/HEAL, OPPONENT_DISCARD (`discardRandomCard`), GAIN_ACTION (`metadata.actionsRemaining + N`), END_TURN (`actionsRemaining = 0`), RETURN_TO_HAND (из сброса в руку), IMMOBILIZE (→ `Fighter.effects` c duration 'turn'; movement-валидатор проверяет), MOVE/PLACE → manualEffects.
5. checkGameOver → GAME_OVER, иначе существующая ветка остатка действий (GAIN_ACTION/END_TURN влияют естественно).
6. `ActionResult.metadata`: `appliedEffects` + `manualEffects: string[]`. Game Tester (`admin/src/pages/game-tester/GameTester.tsx`) печатает оба списка в лог после resolve.

**Верификация (юнит-интеграция):** Feint отменяет during/after противника; «If you won the combat, deal 8 damage» (Gaze of Stone) срабатывает только при победе; ничья — победа защитника; Regroup даёт 1 или 2 карты по исходу; GAIN_ACTION продлевает ход; END_TURN завершает; seq за мутацию resolveCombat = ровно +1 (или +2 при авто-advanceTurn — сверить с текущим контрактом в game-execution.integration.spec.ts).

**Коммит:** `feat(engine): эффекты карт в бою — reveal→during→урон→after`

## A5. BOOST в манёвре (1–2 дня)

TODO уже стоит: `backend/src/game-engine/validators/game-rules.validator.ts:314` — «allowance = movement + card.boostValue».

**Files:**
- Modify: `backend/src/games/dto/gameplay.dto.ts` (ManeuverDto)
- Modify: `backend/src/game-engine/validators/game-rules.validator.ts`
- Modify: `backend/src/game-engine/services/game-action-executor.service.ts` (executeManeuver)
- Modify: `backend/src/game-engine/engine/value-modifier.service.ts` (удалить мёртвый стаб applyCardEffects)
- Modify: `admin/src/pages/game-tester/GameTester.tsx` + `admin/src/pages/game-tester/api.ts` (gql-документ MANEUVER)

**Шаги:**
1. `ManeuverDto` + `boostCardId?: string` (`@IsOptional() @IsString()`). Существующий `cardId` — deprecated: при отсутствии boostCardId трактовать legacy cardId как boost-карту (обратная совместимость GraphQL-схемы и текущей команды тестера). Манёвр без карты = чистые «добор 1 + движение» (по правилам Unmatched).
2. Валидатор: `allowance = getFighterMovement(fighter) + (boostCard?.boostValue ?? 0)`; boost-карта обязана быть в руке вызывающего; BFS-проверка пути против allowance.
3. Executor: сброс boost-карты (если передана) вместо безусловного сброса cardId; добор 1 карты сохраняется; удалить мёртвый вызов `valueModifier.applyCardEffects` из executeManeuver.
4. Game Tester: синтаксис `maneuver <f> [<boostCard>|-] <x,y>` + help; api.ts MANEUVER-документ с boostCardId.
5. MVP-ограничение зафиксировать комментарием в коде: один боец за манёвр; «двигать ВСЕХ бойцов одним манёвром» (полное правило) — блок C.

**Верификация e2e (Game Tester):** путь длины movement+boost проходит только с boost-картой; без неё — ошибка «Недостаточно очков движения»; boost-карта в сбросе; добор 1 карты есть; манёвр без карты работает.

**Коммит:** `feat(engine): BOOST в манёвре — boostCardId, манёвр без карты`

## A6. bannerName-валидация (день)

**Files:**
- Modify: `backend/src/game-engine/validators/game-rules.validator.ts` (bannerAllows + validateAttack)
- Modify: `backend/src/game-engine/services/game-action-executor.service.ts` (playDefense, playScheme)

**Шаги:**
1. Утилита `bannerAllows(card, fighter): boolean`: `'Any'`/пусто/null → true; иначе нормализованное сравнение `bannerName` с `fighter.name` со срезом числового суффикса («Harpy 2» → «Harpy», trim+lowercase). Неизвестный банер (не матчится ни с одним бойцом игры) → разрешить + warn — грязные данные не должны ломать игру.
2. `validateAttackWithParams`: банер vs атакующий боец. `executePlayDefense`: банер vs `combatInfo.targetFighterId` (из A0). `executePlayScheme`: именованный банер требует живого бойца с этим именем у игрока.

**Верификация (юниты):** Medusa не играет Clutching Claws (banner Harpy) при атаке Медузой; гарпия играет; 'Any' играется всеми; легаси-карта без bannerName играется.

**Коммит:** `feat(engine): bannerName-валидация — кто может играть карту`

## A7. BOOST атаки/защиты + BLIND BOOST + e2e MVP (2–3 дня)

**Files:**
- Modify: `backend/src/games/dto/gameplay.dto.ts` (AttackDto, PlayDefenseDto + boostCardId?)
- Modify: `backend/src/game-engine/services/game-action-executor.service.ts` (executeAttack, executePlayDefense)
- Modify: `backend/src/game-engine/abilities/heroes/daredevil.handler.ts` (если нужно — подгонка под ожившие вызовы)
- Modify: `admin/src/pages/game-tester/GameTester.tsx` (attack/defense с boost)
- Create: `backend/scripts/e2e-card-effects.mjs`

**Шаги:**
1. `boostCardId?` в атаке/защите: валидно, если играемая карта имеет BOOST-эффект (`{type: BOOST, boostSource: PLAYER_CHOICE_HAND}`) ИЛИ ability героя разрешает (Arthur — BOOST атаки всегда); boost-карта сбрасывается, `combatInfo.attackValue/defenseValue += boostCard.boostValue`.
2. BLIND BOOST (`BOOST{SELF_DECK_TOP, blind}`) — авто-применение в during-стадии: сброс топа колоды через DeckManagementService, +boostValue, событие в лог. Ability-вариант Daredevil — через оживший handler (`canTrigger`: рука ≤ 2).
3. e2e-скрипт (node, GraphQL http://localhost:3000/graphql, учётки admin@unmached.local/Admin123! + tester2@unmached.local/Tester123!, прибирание активных игр abort'ом — паттерн из C:/tmp/ws-lobby-test.cjs): сценарии Medusa vs King Arthur — Snipe→draw, Regroup→1/2 карты по исходу, Gaze of Stone→+8 урона при победе, Feint→cancel, атака Arthur с boostCardId, манёвр с boost; ассерты по `handZones/fighters/discardPiles/metadata` из распарсенного state.

**Верификация:** `node backend/scripts/e2e-card-effects.mjs` зелёный против docker-стенда; ручной прогон сценария в Game Tester.

**Коммит:** `feat(engine): BOOST атаки/защиты, BLIND BOOST, e2e эффектов`

## A8. Чистка + масштабирование (день + фон)

**Files:**
- Modify: `backend/src/game-engine/services/deck-management.service.ts` (удалить initializeDeck + createHeroCards)
- Modify: `backend/src/game-engine/services/deck-management.service.spec.ts`, `backend/src/game-engine/game-execution.integration.spec.ts:208` (фикстурный хелпер вместо initializeDeck)

**Шаги:**
1. Удалить `initializeDeck`/`createHeroCards` (hardcoded тестовые карты; реальные колоды раздаёт GameInitializationService). `drawCards`/`discardCard`/`discardRandomCard`/`recycleDeck` — живые, НЕ трогать.
2. Спеки перевести на локальный тест-хелпер с фикстурными колодами; поведенческие тесты draw/discard сохранить.
3. Полный backfill 880 карт (`--dry-run` → прогон); отчёт UNSUPPORTED → приоритизация следующих героев по доле авто-распознанного.
4. Счётчик unsupported-исполнений в логах — телеметрия для парсера v2.

**Коммит:** `chore(engine): чистка initializeDeck + полный backfill эффектов`

---

# Блок B — Фронт: подключение к реальному API (~1 неделя)

## Wire-контракты (справка для всех фаз B)

**Два представления серверного состояния (оба per-user отфильтрованы бэком):**
1. Query `gameState` и все gameplay-мутации → `state: string` — ОДНА JSON-строка полного состояния. После parse: `{ gameId, sequenceNumber, phase, turnCount, currentTurnPlayerId, players[], fighters[], decks{}, discardPiles{}, handZones{}, boardState{}, metadata{} }`.
2. Подписка `gameStateUpdated` → те же данные, но `players/fighters/handZones/boardState/metadata` — ПЯТЬ отдельных JSON-строк, и **без decks/discardPiles** (merge из предыдущего снапшота в сторе). Каждое событие — полный снапшот, не дельта.

**Типы wire:** player `{userId, heroId, health, maxHealth, fighterIds[], isAlive}`; fighter `{id, ownerId(=userId), heroId, name, type: HERO|MINION|HUGE, health, maxHealth, position{x,y}, effects[], movement?, attackType?, isDefeated?}`; hand card `{id(инстанс), cardId(дефиниция), name, nameRu, cardType, attackValue?, defenseValue?, boostValue?, text?, isVisible}` — карты соперника приходят с `name:'???'` без значений, но count виден; metadata `{actionsRemaining?, combatInfo?: {attackerId(=fighterId!), defenderId(=userId!), targetFighterId?, attackerCardId, defenderCardId?, attackValue, defenseValue}, winnerId?, passCount?}`; boardState `{width, height, cells[][], doors{}, fog{}, tokens{}}` — цветовые зоны для рендера брать из контентного запроса `Board(id)` (как testGameStore). Фазы: `SETUP|TURN_START|ACTION_MANEUVER|ACTION_ATTACK|COMBAT|COMBAT_RESOLVE|TURN_END|GAME_OVER`. После startGame бэк сам расставляет бойцов и ставит ACTION_MANEUVER — фаза расстановки на фронте не нужна.

**Архитектурное решение:** адаптер wire→локальный формат (`src/core/models/types.ts`), НЕ переписывание GameScene. Сцена потребляет локальный формат в ~30 точках и уже догружает текстуры по imageUrl в рантайме; маппинг однозначен. Заготовки `src/phaser/network/*` и `src/phaser/state/GameStateBridge.ts` (параллельный черновик с optimistic-rollback) — НЕ использовать; единый источник истины — remoteGameStore.

## B0. Контракты (полдня)

**Files:** Modify: `src/graphql/mutations/game.graphql`

```graphql
mutation PlayScheme($input: PlaySchemeDto!) {
  playScheme(input: $input) { state sequenceNumber phase currentTurnPlayerId turnCount timestamp }
}
```
→ `npm run codegen:build` (бэк на :3000 должен быть поднят — интроспекция по сети).

**Приёмка:** `PlaySchemeDocument` появился в `src/gql/graphql.ts`; vite build зелёный.

## B1. Лобби достроить (день)

**Files:** Modify: `src/components/room/RoomView.tsx`

**Шаги:**
1. Удалить мок-блок FighterPlacement (строки ~94-105, ~170-183) — расстановка серверная.
2. Секция выбора героя: список из `heroSelectionStore.loadHeroes()` (есть), по клику `heroSelectionStore.selectHeroOnServer(gameId, heroId)` (уже реализован — `src/store/heroSelectionStore.ts:204`, к UI не подключён), после успеха `loadRoom(gameId)`. Переиспользовать `HeroGrid`/`HeroCard` из `src/components/heroes/`.
3. Кнопка Ready недоступна, пока `currentPlayer.heroId == null`; показать выбранных героев и isReady обоих (данные уже в RoomInfo).
4. Автопереход: в существующем 3-сек поллинге (`RoomView.tsx:42`) — `game.status === 'IN_PROGRESS'` → `navigate('/game/' + gameId)`. Покрывает не-хоста без новых подписок (хост переходит после startGame — `RoomView.tsx:75`).

**Приёмка (2 окна: обычное + инкогнито; admin@unmached.local/Admin123! и tester2@unmached.local/Tester123!):** P1 создаёт → /room; P2 видит в списке, входит; оба выбирают героев (выбор второго виден ≤3с); оба Ready; хост стартует; **оба окна на /game/:gameId** (пока заглушка).

**Коммит:** `feat(front): выбор героя в комнате + автопереход в игру`

## B2. Адаптер + remoteGameStore v2 + живая доска read-only (2–3 дня, ядро)

**Files:**
- Create: `src/lib/gameStateAdapter.ts` (~200 строк, чистый модуль)
- Rewrite: `src/store/remoteGameStore.ts`
- Modify: `src/hooks/useGameSync.ts` (:112 — фикс since)
- Modify: `src/components/game/GameView.tsx`
- Patch: `src/phaser/scenes/GameScene.ts` (2 функции)

**gameStateAdapter.ts:**
- `parseWireState(json: string)` — для query/mutation.
- `parseSubscriptionState(payload)` — JSON.parse пяти полей; decks/discardPiles → undefined (merge в сторе).
- `adaptToLocal(wire, refs, localUserId)` → формат `src/core/models/types.ts`:
  - `players`: **локальный игрок всегда `players[0]`** (GameScene рисует index 0 нижней панелью); `id=userId`, `name` из GetGame.players, `fighters` по `ownerId`, `hand` из `handZones[userId].cards` → `CardInstance{id, ownerId, definition}`, `deck/discardPile` из wire или последние известные, `actionsRemaining` из metadata для ходящего;
  - fighter: `type: HERO→'hero', иначе 'sidekick'`; `isDefeated = isDefeated ?? health<=0`;
  - card definition: `id=cardId, title=nameRu||name, type=cardType.toLowerCase()`, `value=attackValue??defenseValue??0, boost=boostValue??0`, `imageUrl` из справочника героя (`refs.heroCards: Map<cardId→{imageUrl}>`); скрытые карты соперника (`isVisible:false`) → title '???';
  - `board.definition` из контентного Board(boardId) — зоны/арт (паттерн `testGameStore.mapBoardFromGraphQL`, `src/store/testGameStore.ts:269`);
  - `phase`: `GAME_OVER→game_over`, `COMBAT/COMBAT_RESOLVE→combat`, остальное → `action_selection`; `winner = metadata.winnerId ?? null`; `combatState` из `metadata.combatInfo`.

**remoteGameStore v2:** состояние `{wireState, adaptedState, lastSequenceNumber, refs{game, heroes: Map, board}, localUserId, selection, connectionStatus, actionError}`;
- `connectToGame(gameId)`: GetGame (boardId, players с username/heroId) → параллельно Board + Hero×2 (с cards{id,imageUrl,...}) → GetGameState → parse → adapt;
- `applyWireState(wire)`: guard `wire.sequenceNumber <= last → ignore`; merge decks/discardPiles из предыдущего; пересчёт adaptedState. Единая точка для query/mutation/subscription. `checkSequenceGaps`/`eventsSince`-логика упрощается: при дыре принять новейший снапшот (каждое событие полное — дельты не нужны, TODO-ветки убрать);
- мутации `maneuver/moveFighter/attack/playDefense/playScheme/resolveCombat/endTurn/pass`: `apolloClient.mutate`, на успех `applyWireState(parseWireState(result.state))` (мгновенный отклик; эхо подписки дедуплицируется по seq), на ошибку `actionError` + refetch при конфликте optimistic lock.

**useGameSync:** `since: lastSequenceNumber || undefined` (вместо `Date.now()/1000` — строка 112); событие → `parseSubscriptionState → applyWireState`; при reconnect — текущий lastSequenceNumber (сервер дошлёт состояние).

**GameView:** убрать мок-данные и gameStore-зависимые BoardView/HandView/GameControls/PhaserBoard; рендерить `PhaserGame` с `gameState={adaptedState}` + selection-пропсы (паттерн `TestGamePage.tsx:150-160`); GameHeader/TurnIndicator/OpponentHandView — на данные стора.

**GameScene patch:** в `updateGameState/createCards/drawCardArea` рука и счётчики deck/discard — от `state.players[0]` (контракт адаптера), не от `getCurrentPlayer`.

**Приёмка:** сетап через два окна (B1) → оба видят доску с зонами/артом, бойцов на серверных позициях с HP, свою руку (у соперника рубашки+count), ход/фазу. **Действия выполнять через Game Tester админки тем же gameId** (`move f0 3 2`, `attack…`) → оба окна обновляются live без F5. F5 восстанавливает состояние (initial load + since-реконнект).

**Коммит:** `feat(front): GameView на реальном API — адаптер, remoteGameStore v2, live-подписка`

## B3. Действия кликами (2 дня)

**Files:** Modify: `src/components/game/GameView.tsx` (+ хелперы в remoteGameStore), `src/main.tsx` (ToastProvider)

Диспетчер `onGameEvent` (паттерн `TestGamePage.tsx:67-81`) + хелперы `isMyTurn`/`actionsRemaining`/`phase`/`amIDefender = combatInfo?.defenderId === localUserId`:
- `FIGHTER_CLICKED`: свой боец + мой ход + actionsRemaining>0 → выбрать, подсветить клетки в радиусе movement (подсказка; истина — сервер); чужой боец при выбранной ATTACK/VERSATILE-карте → `attack(attackerId=выбранный свой, targetId, cardId)`;
- `SPACE_CLICKED`: выбран свой боец + мой ход → `moveFighter({gameId, fighterId, x, y})`; при выбранной boost-карте — `maneuver` с boostCardId (после A5);
- `CARD_CLICKED`: в COMBAT и я защитник + DEFENSE/VERSATILE → `playDefense({cardId})`; SCHEME в свой ход → `playScheme`; ATTACK/VERSATILE → выделить (ждём клик по цели);
- Кнопки: End Turn → `endTurn`, Pass → `pass` (активны при isMyTurn и фазе ACTION_*); в COMBAT_RESOLVE атакующему — Resolve → `resolveCombat`;
- Ошибки мутаций → toast (`src/design-system/components/Toast.tsx` — useToast/ToastProvider есть, смонтировать в main.tsx). Никакого локального предсказания правил.

**Приёмка:** P1 кликами двигает бойца (фишка переехала у обоих, пипсы действий списались), атакует картой бойца P2 → у P2 фаза COMBAT; действия в чужой ход заблокированы; серверная ошибка видна toast'ом.

**Коммит:** `feat(front): игровые действия кликами через GraphQL-мутации`

## B4. Боевой цикл + конец игры (1–2 дня)

**Files:** Modify: `src/components/game/GameView.tsx`, переиспользовать `src/components/combat/*`, `VictoryScreen`

- Панель боя по `combatInfo`: баннер «вас атакуют» защитнику + выбор карты защиты; после defensePlayed — Resolve у атакующего;
- урон/HP анимируются текущим перерендером сцены;
- `phase === GAME_OVER` (или подписка gameEnded) → VictoryScreen по `metadata.winnerId` относительно localUserId, выход в лобби;
- «Покинуть игру» → мутация leaveGame/abortGame вместо голого navigate.

**Приёмка:** полная партия двумя окнами до победы: атака → защита → resolve → урон синхронно → GAME_OVER → корректные экраны у победителя и проигравшего → возврат в лобби.

**Коммит:** `feat(front): полный боевой цикл и экран конца игры`

## B5. Судьба локальных store (полдня)

`/test-game` **оставить как песочницу** — `testGameStore`, `gameStore`, `src/core/engine/*`, `src/core/data/*` не трогать (используются только тест-страницей и старыми компонентами, отвязанными от /game в B2). Пометить `@deprecated`-комментами: `src/phaser/network/*`, `src/phaser/state/GameStateBridge.ts`, `src/phaser/components/PhaserGameWithBackend.tsx`, `src/hooks/useOptimisticUpdate.ts` — кандидаты на удаление отдельным PR после стабилизации. Убрать флаг `USE_PHASER` из GameView (Phaser безусловный). Починить рассинхрон `VITE_WS_URI`/`VITE_WS_URL` в `.env`/`src/env.ts`.

**Приёмка:** /test-game работает как раньше; production-путь /lobby→/room→/game не импортирует core/engine; vite build чистый.

**Коммит:** `chore(front): deprecated-маркировка локальных движков, чистка env`

---

# Блок C — Отложенное (следующие итерации, в этот заход НЕ входит)

1. **Мультизонность** `Cell.zone → zones[]` в engine (БД уже хранит массив; `buildBoardState` теряет) — разблокирует Ms. Marvel, зонные эффекты («shares no zones»), парсер v2.
2. **Интерактивные эффекты**: pendingEffects в metadata + мутация выбора игрока (выбор цели/клетки/«you may») — замена manualEffects.
3. **Манёвр по полным правилам**: движение ВСЕХ своих бойцов одним манёвром (сейчас один боец).
4. **Оригинальные раскладки досок** — геометрия сгенерирована backfill'ом; уточнять вручную через админку Boards (возможно мини-редактор сетки).
5. **VS_AI бот** — enum GameMode.VS_AI есть, AI-движка нет; большая отдельная фича.
6. **attackType null у 14 героев** — добить вручную/backfill'ом.
7. **Matchmaking e2e** — модуль полный (queue-manager/scheduler/confirmation/penalty), не проверен с новой игровой логикой.
8. **Токены героев** (Hellfire, Rage, cauldron), «choose one», «look at hand», swap spaces — парсер v2/v3.
9. Удаление deprecated фронт-кода из B5.

---

# Верификация (каждая фаза)

```bash
# деплой бэка (bind mount — образ НЕ пересобирать!)
docker exec unmatched-backend npm run build && docker compose -f "C:/Users/ren/WebstormProjects/unmached/unmached/docker-compose.yml" restart backend; sleep 10; curl -s http://localhost:3000/health
# юниты движка
docker exec unmatched-backend npx jest --testPathPattern="game-engine"
# backfill dry-run
docker exec unmatched-backend npx ts-node --transpile-only prisma/backfill-card-effects.ts -- --dry-run
# e2e эффектов
node backend/scripts/e2e-card-effects.mjs
```
- Фронт: vite dev 5174, два окна (обычное + инкогнито — общий localStorage иначе). Админка 5480.
- Текстовая проверка любой бэк-фазы — Game Tester в админке.
- После ребута машины стек лежит: `docker compose up -d` (postgres 5433, redis 6379), потом build+restart backend.
- Коммит после каждой фазы, `--no-verify` (pre-commit hook сломан — eslint не установлен в корне).

# Риски

- **sequenceNumber-контракт** — самое хрупкое место (двойной инкремент при интеграции A4: applyDamage + executor); закрывается юнитом-инвариантом ДО рефакторинга боя.
- **Легаси-сейвы**: все новые поля optional, дефолты централизованы (паттерн `getActionsRemaining`).
- **Лимит 5 активных игр** на юзера (MaxActiveGamesException) — e2e-скрипты прибирают активные игры abort'ом перед стартом (паттерн C:/tmp/ws-lobby-test.cjs).
- **Расхождение контента** (фронт): `cardId` руки должен матчиться с `Hero.cards[].id` для артов — проверка на B2, fallback-рендер карты без арта в GameScene уже есть.
- **HERO_VISUALS** в сцене захардкожен на ms-marvel/daredevil — другие герои падают в FALLBACK_HERO (визуальная деградация, не блокер).
