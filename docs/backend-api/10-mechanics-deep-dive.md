# 10. Игровые механики: разбор по коду движка

> Источники: `backend/src/game-engine/**` (services, validators, effects, engine), `backend/src/games/services/*` (инициализация, combat-timeout, AI), `backend/src/content/data/boards/*`, `src/core/data/boards/*`.
> Все числа и правила ниже извлечены из кода; ссылки на файлы — абсолютные пути от корня репозитория.

---

## 1. Структура хода

### 1.1. Фазы `GamePhase`

`backend/src/game-engine/models/game-state.model.ts` (enum `GamePhase`):

| Фаза | Значение | Комментарий из кода |
|---|---|---|
| `SETUP` | Подготовка, размещение бойцов | Используется только при создании состояния |
| `TURN_START` | Начало хода | **Исключена из продакшен-потока** — ход начинается сразу с `ACTION_MANEUVER` + добор карты |
| `ACTION_MANEUVER` | Манёвр | Основная «рабочая» фаза действия |
| `ACTION_ATTACK` | Атака | Legacy-фаза старых сейвов; валидна для атаки/манёвра/pass/endTurn |
| `COMBAT` | Бой (окно защиты) | Ставится `executeAttack`, ждёт `playDefense` или таймаут |
| `COMBAT_RESOLVE` | Разрешение боя | Ставится `executePlayDefense`; здесь работает `executeResolveCombat` |
| `TURN_END` | Конец хода | Промежуточная legacy-фаза; в реальном потоке `advanceTurn` сразу ставит `ACTION_MANEUVER` следующему игроку |
| `GAME_OVER` | Игра окончена | Ставится `checkAndApplyGameOver`, `metadata.winnerId` заполнен |

### 1.2. Экономика «2 действия за ход»

- Константа `ACTIONS_PER_TURN = 2` (`game-state.model.ts`) — ровно 2 действия: манёвр / атака / scheme в любой комбинации, атаковать можно дважды.
- Остаток хранится в `metadata.actionsRemaining`; чтение — `getActionsRemaining(state)`: легаси-мусор (null/NaN/отрицательное/строка) → дефолт `2`.
- `consumeAction(state, userId)` (`game-action-executor.service.ts`): списывает 1 действие; **при остатке 0 — авто-завершение хода** через `advanceTurn` без дополнительного инкремента `sequenceNumber` (контракт saveState: ровно +1 к seq за мутацию).

**Что тратит действие:**

| Действие | Тратит действие? | Где |
|---|---|---|
| Манёвр (`executeManeuver`) | Да (`consumeAction`) | Двигает ВСЕХ своих бойцов (`moves[]`), BOOST-карта каждому, добор 1 карты |
| Простое перемещение (`executeMoveFighter`) | Да (`consumeAction`) | Через `movementService.executeMovement` |
| Атака (`executeAttack`) | Да — **в момент объявления**: `actionsRemaining = max(0, remaining - 1)` | Не через `consumeAction` (ход не завершаем, бой не разрешён) |
| Scheme (`executePlayScheme`) | Да (`consumeAction`) | Карта всегда в сброс |
| Pass (`executePass`) | Да (`consumeAction`) | Также инкрементирует `metadata.passCount` |
| `endTurn` (`executeEndTurn`) | Нет — просто передаёт ход | Валидна из `ACTION_MANEUVER`/`ACTION_ATTACK`/`TURN_END` |
| `toggleDoor` (`executeToggleDoor`) | **Нет** (не вызывает `consumeAction`) | Переключение двери бесплатно |
| `setStance` (`executeSetStance`) | **Нет** (смена стойки бесплатна) | |
| `resolvePendingEffect` | **Нет** (эффект уже оплачен картой), seq +1 | |
| `playDefense` | Нет (это не действие активного игрока) | |

### 1.3. Передача хода — `advanceTurn` (приватный метод executor'а)

Точный порядок (код `game-action-executor.service.ts`):

1. **`triggerHeroTurnEnd`** — extended-хук `onTurnEnd` героя ЗАВЕРШАЮЩЕГО игрока (фаза TURN_END исключена из потока, хук встроен сюда).
2. Поиск следующего живого игрока по кругу: `(currentIndex + 1) % players.length`, пропуск мёртвых (`!isAlive`), максимум `players.length` попыток. Если следующий == текущий (остался один) — `turnCount` не растёт, иначе `turnCount + 1`.
3. **Добор 1 карты** следующему игроку (`deckManagement.drawCards`); ошибки (легаси без deck) не блокируют передачу.
4. **Снятие эффектов `duration: 'turn'`** со всех бойцов (например `immobilized`).
5. **Снапшот `metadata.turnStartPositions`** — позиции всех бойцов на начало нового хода (условие `MOVED_THIS_TURN`).
6. Сброс `actionsRemaining = ACTIONS_PER_TURN (2)`, per-turn флагов `maneuveredThisTurn / attackedThisTurn / lostCombatThisTurn = false`.
7. Чистка `pendingEffects`: удаляются только эффекты, чей `playerId === nextPlayerId` (выборы «протухают» при возврате хода их владельцу — полный круг).
8. **`triggerHeroTurnStart`** — extended-хук `onTurnStart` нового игрока (no-op для героев без хука).
9. **`checkAndApplyGameOver`** — turn-start-способность могла добить соперника.
10. Фаза нового состояния: `ACTION_MANEUVER`, `sequenceNumber +1` (при `incrementSeq=true`).

Существует и **legacy-сервис** `turn-management.service.ts` (`TurnManagementService`) со своим протоколом (`turn_actions`/`turn_passed`/`turn_additional` в metadata, `DEFAULT_ACTIONS_PER_TURN = 2`, pass блокирует дальнейшие действия в ходу, +additionalActions) — продакшен-поток идёт через executor, этот сервис вспомогательный.

### 1.4. Auto-advance (авто-завершение хода)

Ход завершается автоматически, когда `actionsRemaining` достигает 0 после: манёвра, перемещения, scheme, pass — через `consumeAction`; после резолва боя — `executeResolveCombat` проверяет остаток: `> 0` → фаза `ACTION_MANEUVER` (ход атакующего продолжается), `0` → `advanceTurn`. `GAIN_ACTION`/`END_TURN` из after-эффектов карт меняют `actionsRemaining` до этой проверки.

---

## 2. Передвижение

### 2.1. Очки движения

- `Fighter.movement` (опционально); дефолт `DEFAULT_FIGHTER_MOVEMENT = 2` (`fighter.model.ts`, Prisma `Hero.movement` default 2). Грязные значения (0/null/NaN/строка) → 2.
- `getFighterMovement(f)` — единственная точка чтения.

### 2.2. Геометрия доски и мультизоны

- Клетка `Cell` (`board.model.ts`): `type: 'normal' | 'wall' | 'obstacle' | 'door' | 'zone-line'`, `zone` (legacy) и `zones: string[]` — **клетка может принадлежать 1–2 зонам** (`getCellZones(cell)` — читает `zones`, фолбэк на `zone`, иначе `[]`).
- Непроходимость (`AdjacencyService.isCellBlocked`): `wall`, `obstacle`, или `door` при `!isOpen`.
- Соседство: **4-связность** (N/S/E/W). Диагонали поддержаны API (`includeDiagonal`, диагональный шаг стоит `1.5`), но по умолчанию выключены и в валидаторах движения не используются.
- Стоимость шага: `1` (ортогональный). В表征 BFS `getReachableCells(boardState, start, maxCost, {blockedPositions})` — стоимость в клетках; клетки, занятые живыми бойцами, передаются как `blockedPositions` (блокируют путь, но **промежуточные клетки можно проходить, если они свободны** — конечная обязана быть свободной).

### 2.3. Манёвр (`executeManeuver` + `validateManeuver`)

Правила из кода:

- Манёвр = **движение + добор 1 карты** (правила Unmatched); опционально сбрасывается BOOST-карта (`boostCardId` или legacy `cardId`) — она уходит в сброс, её `boostValue` добавляется к очкам движения **каждому** движимому бойцу.
- **Двигаются все свои бойцы**: DTO `moves[]` (несколько ходов) либо legacy `fighterId + path` (один). Каждый боец — не более одного раза за манёвр (`uniqueFighters`).
- Ходы применяются последовательно, валидация каждого — на состоянии после предыдущего.
- Лимит: `path.length ≤ getFighterMovement(fighter) + boostValue` (`NOT_ENOUGH_MOVEMENT`).
- Каждый шаг пути — на **смежную** клетку: `|dx| + |dy| === 1` (`INVALID_STEP`); одновременно отсекаются дубли позиций.
- Все клетки пути — проходимые (не wall/obstacle, в границах).
- Конечная клетка не занята живым бойцом (`Клетка (x, y) занята`); промежуточные занятые — также отклоняются этим же циклом валидации (клетка должна быть проходимой и свободной).
- Эффект `immobilized` на бойце запрещает манёвр (`FIGHTER_IMMOBILIZED`).
- После движения: единый +1 к seq, реактивные on-move хуки героев (`applyMoveReactions`), сброс BOOST-карты, **добор 1 карты**, флаг `maneuveredThisTurn = true`, `consumeAction`.

### 2.4. Простое перемещение (`executeMoveFighter` + `validateMovement`)

- Цель обязана быть **BFS-достижимой** за `getFighterMovement(fighter)` шагов по проходимым клеткам, занятые живыми бойцами клетки блокируют путь (не просто дистанция по сетке!).
- Перемещение в свою клетку — no-op (дистанция 0), очки не тратятся.
- `immobilized` запрещает. Действие тратится.

### 2.5. Отложенные перемещения (MOVE/PLACE-эффекты карт)

См. §8: дистанция эффекта (`pending.value`, дефолт 1) — тоже BFS по проходимым клеткам с блокировкой чужими бойцами.

---

## 3. Атака

### 3.1. Геометрия достижения (точная)

`executeAttack` (`game-action-executor.service.ts`):

1. **Смежность**: `isAdjacent` = **манхэттеновское расстояние строго `=== 1`** (`AdjacencyService.manhattanDistance(a,b) === 1`). Диагональ НЕ смежна.
2. **Melee** (`getFighterAttackType(attacker) === 'melee'`, дефолт; БД-значение `'range'` нормализуется в `'ranged'` через `normalizeAttackType`): цель достижима **только если смежна**.
3. **Ranged**: смежная **ИЛИ** в той же зоне доски — `isInSameZone`: `cells[a.y][a.x].zone === cells[b.y][b.x].zone` (legacy-поле `zone`, обе non-null). На fallback-доске 20×20 зоны undefined → ranged работает только по смежности. Заметка: модель поддерживает мультизоны `zones[]` (пересечение зон), но `isInSameZone` движка читает legacy-поле `zone`.
4. **Extended-range способность героя**: если обычные правила не достают, спрашивается `abilityRegistry.canAttackAtRange(slug, attackerId, targetId, manhattanRange, attackerStance)` — хук **только добавляет** разрешение (например Ms. Marvel range ≤ 2; Muhammad Ali: стойка FLOAT — range 2, STING — дальней атаки нет). Стоитйка берётся из `metadata.heroStances[attacker.ownerId]`.

Валидация `validateAttackWithParams`: ход игрока (`canPlayerAct`), фаза `ACTION_MANEUVER`/`ACTION_ATTACK`, атакующий/цель живы, атакующий свой, карта в руке типа `ATTACK`/`VERSATILE` (legacy `UNIVERSAL`), именная карта (`bannerName`) — только бойцом с совпадающим именем (`validateBanner`, см. §3.3).

### 3.2. Инициирование и окно защиты

- После валидации: карта атаки уходит в сброс (в `combatInfo` пишется её instance id `${cardId}::n`), BOOST-карта (если `boostCardId`) — тоже в сброс.
- **BOOST атаки**: нельзя бустить той же картой; разрешён если у играемой карты есть эффект `BOOST` с `boostSource === 'PLAYER_CHOICE_HAND'` (или null), ЛИБО способность героя разрешает (`allowsAttackBoost`, например King Arthur) — метод `boostAllowed`.
- Формируется `metadata.combatInfo` (`CombatState`): `attackerId`, `defenderId` (userId владельца цели), `targetFighterId` (**атака по сайдкику бьёт именно сайдкика**), `attackerCardId`, `attackValue = attackValue карты + boostValue буст-карты`, `defenseValue: 0`, `startedAt`, опц. `timeoutAt`.
- Фаза → **`COMBAT`** («окно защиты»), действие списывается сразу.

### 3.3. Окно защиты и auto-resolve 30 секунд

- Защиту играет только `combatInfo.defenderId` (`playDefense`): карта в руке типа `DEFENSE`/`VERSATILE`/`UNIVERSAL`; banner-проверка против **атакованного бойца** (`targetFighterId`, фолбэк — первый боец защитника). BOOST защиты — те же правила (`boostAllowed(..., 'defense')`, `allowsDefenseBoost`).
- `defenseValue = defenseValue карты + boostValue буст-карты`; обе карты в сброс; фаза → **`COMBAT_RESOLVE`**.
- **Auto-resolve** (`backend/src/games/services/combat-timeout.service.ts`): BullMQ-очередь `combat-timeout`, задача `auto-resolve` планируемая при атаке с задержкой **`DEFAULT_DEFENSE_TIMEOUT = 30` секунд** (есть также `DEFAULT_RESOLVE_TIMEOUT = 10` сек на подтверждение резолва). Processor под distributed-локом `game:{gameId}`: если фаза всё ещё `COMBAT` и `sequenceNumber` не ушёл вперёд — выполняется `performAutoResolve` (переход в `COMBAT_RESOLVE`; **интеграция с CombatResolver помечена TODO** — урон при чистом таймауте не применяется в этой ветке). Любое действие игрока раньше (защита) делает задачу неактуальной по seq-проверке.
- Banner-мэтчинг (`bannerAllows`): «Harpy» = «Harpy 2» (срез числового суффикса), «Arthur» = слово в «King Arthur», нормализация множественного числа (harpies → harpy, wolves → wolf, dogs → dog), регистронезависимо. Неизвестный банер (не матчит никого в игре) не блокирует — warn + разрешить.

---

## 4. Пошаговый бой (`executeResolveCombat`)

Входные фазы: `COMBAT` или `COMBAT_RESOLVE`; мутацию может вызвать и защитник (CombatResolveGuard). Пайплайн:

### Шаг 1. Раскрытие карт — ON_REVEAL
`cardEffectExecutor.executeRevealEffects(state, attackerCard, defenderCard, combatCtx)`: эффекты с `timing: ON_REVEAL` применяются **сначала атакующим, затем защитником**. `CANCEL_EFFECTS` на атакующей карте отменяет карту защитника (`defenderCardCancelled = true`) и наоборот; **отменённая карта не исполняет ни reveal-, ни during-, ни after-эффекты; её печатное значение сохраняется; отменённый защитник не отменяет в ответ** (его reveal уже не исполняется).

### Шаг 2. DURING_COMBAT — модификаторы значений карт
`executeCombatEffects`: для каждой не-отменённой карты эффекты `timing: DURING_COMBAT` в порядке **`SET_VALUE` → `MODIFY_VALUE`/`MODIFY_ATTACK`/`MODIFY_DEFENSE` → `VALUE_PER_COUNT` → прочее**. `SET_VALUE` заменяет значение (последний выигрывает), MODIFY добавляет дельту, `VALUE_PER_COUNT` = `count × per` (счётчики: `CARDS_IN_HAND`, `FRIENDLY_ADJACENT_TO_OPPONENT`, `DISCARD_NAME_PREFIX`, `DAMAGE_DEALT`, `DAMAGE_TAKEN`). `PREVENT_DAMAGE` гасит урон соответствующей стороне. Результат — `finalAttack`/`finalDefense` этапа карт.

### Шаг 3. Модификаторы героев (4 слоя, аддитивно поверх карт)

```
finalAttack = calc.finalAttack + heroMods.attackModifier + statefulAttack + auraAttack
finalDefense = calc.finalDefense + heroMods.defenseModifier + statefulDefense + auraDefense
```

- **heroMods** — `CombatResolverService.getHeroCombatModifiers`: `abilityRegistry.applyCombatModifiers(slug, ...)` (ValueModifier; суммируются только `type === ADD`; SET/MULTIPLY/IGNORE в этой точке игнорируются). В изолированном `CombatResolverService.resolveCombat` значения дополнительно зажимаются `Math.max(0, ...)`; в executor-пайплайне модификаторы просто прибавляются.
- **stateful** — `abilityRegistry.getStatefulCombatModifiers(slug, GameState, combatInfo, fighter, role)`: те же ADD-модификаторы, но с доступом к `GameState` (условия вида «первая атака в ходу» читают `attackedThisTurn` **до** его установки в этом резолве: первая атака видит false, вторая — true).
- **auras** — `abilityRegistry.getAuraCombatModifiers(state, fighter, role)`: консультируются **ВСЕ зарегистрированные handler'ы** для каждого бойца-бенефициара (аура исходит от ДРУГОГО героя-гранителя, см. §7).

### Шаг 4. Урон и ничья

- `finalAttack > finalDefense` → `defenderDamage = finalAttack - finalDefense` (если не `preventDamageToDefender`).
- `finalDefense > finalAttack` → `attackerDamage = finalDefense - finalAttack` (если не `preventDamageToAttacker`).
- **Ничья (равенство) — победа защитника, урона нет никому.**
- Урон применяется с зажимом `health = max(0, health - damage)`.

### Шаг 5. AFTER_COMBAT эффекты карт
`executeAfterCombatEffects`: **сначала ВСЕ эффекты атакующего, затем защитника**. Контекст каждой стороны дополнен `wonCombat`, `damageDealt`, `damageTaken`. Условия `when`: `WON_COMBAT`, `LOST_COMBAT`, `IS_ATTACKING/DEFENDING`, `DECK_EMPTY`, `HAND_COUNT_AT_MOST/AT_LEAST`, `HEALTH_AT_MOST`, `ADJACENT_TO_OPPONENT` (+NOT), `SHARES_ZONE_WITH_OPPONENT` (+NOT, по мультизонам), `MOVED_THIS_TURN` (сравнение с `turnStartPositions`), `OPPONENT_IS_HERO`.

### Шаг 6. Итоги: смерть сайдкиков, game-over, хуки

- Бойцы с `health <= 0` получают `isDefeated = true` (вычисляются **ново-павшие** — дифф от снапшота до боя).
- `player.isAlive = true` если у игрока есть хоть один живой боец (`health > 0`), иначе false. **Смерть сайдкика сама по себе игрока не убивает** — только если и герой повержен.
- Per-turn флаги: `firstLossThisTurn = !attackerWon && !lostCombatThisTurn` (до установки); затем `attackedThisTurn = true`, `lostCombatThisTurn ||= !attackerWon`.
- **After-combat хук атакующего героя** (`triggerHeroAfterCombat`) → **defender-side хук** (`triggerHeroAfterDefense`, напр. Spider-Sense) → **on-defeat хук владельца каждого ново-павшего** (`triggerHeroFighterDefeated` — герой реагирует на гибель сайдкика, слаг берётся с HERO-бойца владельца).
- **Game-over** (`checkAndApplyGameOver`, единая точка): `players.filter(isAlive).length <= 1` → `phase = GAME_OVER`, `metadata.winnerId = alivePlayers[0].userId`, `combatInfo = undefined`. Победитель — единственный живой; если живых 0 — `winnerId` undefined.
- Если игра не окончена: остаток действий атакующего `> 0` → фаза `ACTION_MANEUVER` (ход продолжается), `0` → `advanceTurn`.

### Эффекты карт, применимые в бою (CardEffectExecutorService)

`SET_VALUE`, `MODIFY_*`, `VALUE_PER_COUNT`, `BOOST` (авто-источники: `SELF_DECK_TOP` — «BLIND BOOST», сброс верха своей колоды и + его boostValue; `OPPONENT_RANDOM_HAND` — противник сбрасывает случайную карту руки, + её boostValue; `PLAYER_CHOICE_HAND` — через `boostCardId` в мутации), `CANCEL_EFFECTS`, `PREVENT_DAMAGE`, `DAMAGE`, `HEAL`, `DRAW_CARD`, `DISCARD`, `OPPONENT_DISCARD`, `GAIN_ACTION`, `END_TURN`, `RETURN_TO_HAND`, `IMMOBILIZE` (накладывает `immobilized` с `duration: 'turn'`), `CHOOSE_ONE`/`MOVE`/`PLACE` → pendingEffects, `UNSUPPORTED` → manualEffects (ручное применение, игра не блокируется). Цели: `SELF`, `OPPOSING_FIGHTER`, `ATTACKER`, `DEFENDER`, `ALL_ENEMIES`, `ALL_ALLIES`, `ENEMIES_ADJACENT_TO_SELF`, `ADJACENT_ENEMY` (несколько кандидатов → первый + warn), `NAMED_FIGHTER`, `OPPONENT_PLAYER`.

---

## 5. Доска

### 5.1. Модель (`board.model.ts`)

- `BoardState`: `width`, `height`, `cells[y][x]`, `doors: Record<'x:y', boolean>` (открыта/закрыта), `fog: Record<'x:y', boolean>`, `tokens`.
- Типы клеток: `normal`, `wall` (непроходима), `obstacle` (непроходима), `door` (непроходима пока `!isOpen`), `zone-line` (декоративная граница зон). Спец-поля клеток: `zones[]` (мультизона), `isHighGround` (в механиках движка не используется), `isOpen` (двери).
- `createEmptyBoardState(20, 20)` — fallback: все клетки normal, без зон → ranged деградирует до смежности.

### 5.2. Двери (`toggleDoor`)

- `executeToggleDoor`: валидация (`validateToggleDoor`) — ход игрока, фаза `ACTION_MANEUVER`/`ACTION_ATTACK`, дверь с ключом `x:y` существует в `boardState.doors` (`DOOR_NOT_FOUND`). Эффект: инверсия `doors['x:y']`. Закрытая дверь = блокирует путь (BFS) и непроходима. Действие **не тратится**. Комментарий кода: «специальная способность Bjorn».

### 5.3. Туман (fog)

- Поле `fog: Record<клетка, boolean>` присутствует в модели и (де)сериализуется в `game-state.service.ts` (ключ `fg` в компактном формате), но **никакой игровой логики, читающей fog, в движке нет** — только хранение/транспорт. Инициализация: `fog: {}`.

### 5.4. Реестр бордов

Единственный борд в данных: **cobble-city** (`backend/src/content/data/boards/cobble-city.ts` и дубль `src/core/data/boards/cobble-city.ts` — идентичная геометрия, различаются импортами enum Zone и полем `imageUrl` во фронтенд-копии). `BOARD_REGISTRY = { 'cobble-city': cobbleCity }`, `getDefaultBoardId() = 'cobble-city'`.

**Cobble City** — сетка **6×4** (24 клетки), 2 игрока, все клетки проходимые (normal), стен/препятствий/дверей/тумана нет. Раскладка зон (5 зон):

| y\x | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| **0** | blue | blue | green | green | yellow | yellow |
| **1** | blue | **blue+green** | green | **green+yellow** | yellow | yellow |
| **2** | purple | **purple+red** | red | red | red | red |
| **3** | purple | purple | red | red | red | red |

Мультизонные клетки: (1,1) blue+green, (3,1) green+yellow, (1,2) purple+red. Все прочие клетки однозонные. Следствие для ranged: атакующий и цель в одной зоне (по legacy-полю `zone`) достижимы без смежности; красная зона — самая большая (10 клеток), по 4 у blue/green/yellow, 4 у purple. В БД может лежать своя геометрия (реальная доска строится из БД, fallback 20×20 — см. `game-initialization.service.ts`).

### 5.5. Размещение при старте (`game-initialization.service.ts`)

- Герой + сайдкики (type MINION, health/movement из БД с дефолтами: сайдкик hp 1, движение 2), стартовые позиции — базовая точка места (seat) + офсеты, координаты зажимаются в границы доски, занятые клетки учитываются.
- `boardState` — реальная геометрия из БД либо fallback `createEmptyBoardState(20, 20)` (`doors: {}`, `fog: {}`).

---

## 6. Стойки (STANCE-подсистема)

- Хранение: `metadata.heroStances: Record<userId, stanceId>` — текущая стойка героя каждого игрока (id из `AbilityConfig.stances`).
- **Переключение**: мутация `executeSetStance({ stanceId })` — валидация: у игрока есть HERO-боец; герой stance-aware (`abilityRegistry.getStances(slug)` непуст); `stanceId` входит в список. Эффект: `heroStances[userId] = stanceId`, seq +1. **Выбор стойки бесплатен** — не тратит действие (комментарий: «размещение / начало хода / "Change size"-карты»). Также стойку меняют авто-эффекты способностей (`set-stance` / `cycle-stance`).
- **Что гейтят**: стойка передаётся в `canAttackAtRange(..., stance)` — стойка определяет допустимую дальность атаки (пример из кода: Muhammad Ali — FLOAT даёт range 2, STING запрещает дальнюю атаку). Легаси-сейвы без `heroStances` → handler фолбэчит на стойку с `default: true` (или первую).

---

## 7. Ауры

Реализованы через `HeroAbilityRegistry.getAuraCombatModifiers(state, beneficiary, role)` (`hero-ability-registry.ts`):

- **Гранитель** — герой-владелец ауры (handler с хуком `getAuraCombatModifiers`); его handler отличает ауру от собственных модификаторов тем, что баффает **другого** дружественного бойца.
- **Бенефициар** — боец, участвующий в бою, получающий модификатор. По комментариям реестра: аура действует на дружественного бенефициара, **делящего зону с гранителем** (Oda-style), во время боя бенефициара.
- Вызов: реестр перебирает **все зарегистрированные handler'ы** (не только handler героя боец боя) и суммирует возвращённые `ValueModifier`; в executor суммируются только `ADD`-модификаторы (`sumAddModifiers`) и добавляются к финальным значениям атаки/защиты (см. §4 шаг 3). Аура аддитивна и не трогает математику heroMods/stateful.

---

## 8. Отложенные эффекты PendingEffect

### 8.1. Модель (`game-state.model.ts`, `PendingEffect`)

```ts
type: 'MOVE' | 'PLACE' | 'CHOOSE_ONE'
playerId      // кому принадлежит выбор
value?        // дистанция MOVE (шаги)
fighterName?  // именное ограничение («Move Daredevil…», «each Harpy»)
targetsOpponent? // двигается боец противника («Place the opposing fighter…»)
text?         // исходный текст для лога
// CHOOSE_ONE: options[] (index+label), chooseCount? (default 1), optionEffects[][], card
```

### 8.2. Порождение (`card-effect-executor.service.ts`, `applyOneEffect`)

Эффекты карт `MOVE`/`PLACE`/`CHOOSE_ONE` **не блокируют** игру (в Unmatched такие эффекты опциональны, «You may move…»): в `metadata.pendingEffects` добавляется запись, текст дублируется в `manualEffects`. `CHOOSE_ONE` без распознанных опций → сразу manual.

### 8.3. Резолв — `executeResolvePendingEffect(dto: { effectId, fighterId?, x?, y?, optionIndex? })`

Общие проверки: pending существует (иначе «протух или уже резолвлен»), `pending.playerId === userId`. **Действие НЕ тратится** (эффект оплачен картой), seq +1.

**MOVE/PLACE** (требуют `fighterId`, `x`, `y`):
1. Боец жив; владелец: свой — для обычных MOVE, чужой — если `targetsOpponent` (иначе «Эффект двигает не этого бойца»).
2. `fighterName`-ограничение: `bannerAllows(pending.fighterName, fighter)`.
3. Клетка в границах, не obstacle/wall, не занята живым бойцом.
4. **MOVE**: цель достижима BFS за `pending.value ?? 1` шагов по проходимым клеткам (чужие живые бойцы — `blockedPositions`); **PLACE**: любая валидная свободная клетка (зонные ограничения — TODO).
5. Телепорт бойца на клетку, pending удаляется, реактивные on-move хуки (`applyMoveReactions`) + пере-проверка game-over.

**CHOOSE_ONE** (`resolveChooseOne`): валидный `optionIndex` (0..len-1) → `cardEffectExecutor.executeChosenEffects` исполняет эффекты выбранной опции (вне боя; боевые эффекты уходят в manual). При `chooseCount > 1` («choose 2 different effects») pending остаётся с `chooseCount - 1` и опциями без выбранной. Вложенные MOVE/PLACE из опции порождают новые pending.

**Протухание**: в `advanceTurn` удаляются pending'ы, чей `playerId === nextPlayerId` (при возврате хода владельцу — полный круг).

---

## 9. Колоды

### 9.1. Стартовое состояние (`game-initialization.service.ts`)

- Константы: `STARTING_HAND_SIZE = 5`, `MAX_HAND_SIZE = 7` (лимит руки `HandZone.maxSize`).
- Колода = карты героя из БД, развёрнутые по `count` (instance id `${cardId}::${copy}`), Fisher-Yates шаффл, верхние 5 — стартовая рука (`isVisible: false` при раздаче; при доборе карты в руку помечаются `isVisible: true`).
- `DeckState`: `cards` (полный список), `drawPile` (текущая стопка), `topCard = drawPile[0]`.

### 9.2. Добор (`DeckManagementService.drawCards`)

- По 1 карте за итерацию: рука полная (`≥ maxSize`) → стоп, добор прерывается; `drawPile` пуст → **recycleDeck** (сброс перетасовывается Fisher-Yates и кладётся ПОД текущий drawPile, сброс очищается); если и после этого пусто — добор невозможен, выход.
- `discardCard(instanceId)`: карта уходит из руки в `discardPiles` (`isVisible: false`). `discardRandomCard` — для Pass/эффектов DISCARD.

### 9.3. Движение карт в бою

Сыгранные карты атаки/защиты/буста сбрасываются **в момент розыгрыша**; резолв боя находит их по instance id «где угодно» (`findCardAnywhere`: руки → сбросы → полные списки колод).

### 9.4. VS_AI — поведение бота (`AiDecisionService` + AiTurnService)

Чистая greedy-эвристика без сайд-эффектов: `decide(state, aiUserId) → AiAction | null` (null = «ход за человеком»). Приоритет:

1. **GAME_OVER** → null.
2. **Свои pendingEffects** — резолвятся первыми: `CHOOSE_ONE` — опция с рангом `HEAL(3) > DRAW_CARD(2) > GAIN_ACTION(1) > первая`; `MOVE` — BFS-шаг к ближайшему врагу не дальше `pending.value ?? movement`; `PLACE` своего — шаг к врагу; `targetsOpponent` — «двигаем врага на месте» (нейтрально, лишь бы очистить pending).
3. **Бой**: `COMBAT_RESOLVE` → `resolveCombat`. Бот-защитник в `COMBAT`: если защита уже сыграна → resolve; иначе лучшая карта защиты (`bestDefenseCard`: максимум `defenseValue`, при равенстве предпочитает чистую DEFENSE перед VERSATILE; только карты с `defenseValue > 0`, banner-совместимые); нет карт → resolve (защита 0). Бот-атакующий: resolve сразу, как только человек сыграл защиту (иначе ждёт — null).
4. **Свой ход** (`ACTION_MANEUVER`/`ACTION_ATTACK`, `actionsRemaining > 0`, иначе `endTurn`): поиск ближайшего врага (приоритет HERO-бойцам) от своего героя. Досягаемость атаки: melee — манхэттен 1; ranged — смежность ИЛИ пересечение зон (`zones[]`/legacy `zone`, включая мультизоны). При досягаемости — лучшая карта атаки (`bestAttackCard`: максимум `attackValue`, при равенстве ATTACK > VERSATILE, banner-совместимая). Иначе — манёвр: BFS-клетка, строго ближе к врагу по манхэттену, в пределах `movement` (препятствия и чужие живые бойцы блокируют путь; выбирается минимум манхэттена). Нечего делать → `endTurn`.

---

## Приложение: сводные константы

| Константа | Значение | Файл |
|---|---|---|
| `ACTIONS_PER_TURN` | 2 | `game-engine/models/game-state.model.ts` |
| `DEFAULT_FIGHTER_MOVEMENT` | 2 | `game-engine/models/fighter.model.ts` |
| `DEFAULT_DEFENSE_TIMEOUT` | 30 с | `games/services/combat-timeout.service.ts` |
| `DEFAULT_RESOLVE_TIMEOUT` | 10 с | там же |
| `STARTING_HAND_SIZE` | 5 | `games/services/game-initialization.service.ts` |
| `MAX_HAND_SIZE` | 7 | там же |
| Fallback-доска | 20×20, все клетки normal, без зон | `game-engine/models/board.model.ts` |
| Cobble City | 6×4, 24 клетки, 5 зон, 3 мультизонных клетки | `content/data/boards/cobble-city.ts` |
| Смежность | манхэттен === 1 (4-связность) | `game-engine/engine/adjacency.service.ts` |
| Диагональ (API, не используется в валидаторах) | шаг 1.5 | там же |
