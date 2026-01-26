# ФАЗА 6: Game Module - Часть 2 (Engine + Rules)

> **ВАЖНО**: Эта фаза является самой сложной и критичной. Уделите ей особое внимание.

## Задача 6.1 - Типы для игровых механик

Создать типы для эффектов, модификаторов и перемещения.

### Действия:
1. Создать enum для типов эффектов карт:
   - `EffectTiming.DURING_COMBAT` - ВО ВРЕМЯ БОЯ
   - `EffectTiming.AFTER_COMBAT` - ПОСЛЕ БОЯ
   - `EffectTiming.IMMEDIATE` - НЕМЕДЛЕННО
   - `EffectTiming.ON_DEFEAT` - при повержении

2. Создать типы для модификаторов значений:
   - `ValueModifierType.SET` - "становится равным"
   - `ValueModifierType.ADD` - "увеличьте/уменьшите"
   - `ValueModifierType.IGNORE` - "игнорируйте"

3. Создать типы для перемещения:
   - `MovementType.MOVE` - соблюдать правила движения
   - `MovementType.PLACE` - телепортация

### Файлы:
```
backend/src/game/engine/types/
├── effects.ts
├── modifiers.ts
└── movement.ts
```

### Типы:
```typescript
// effects.ts
export enum EffectTiming {
  DURING_COMBAT = 'DURING_COMBAT',
  AFTER_COMBAT = 'AFTER_COMBAT',
  IMMEDIATE = 'IMMEDIATE',
  ON_DEFEAT = 'ON_DEFEAT',
  ON_PLAY = 'ON_PLAY',
}

export enum EffectType {
  MODIFY_ATTACK = 'MODIFY_ATTACK',
  MODIFY_DEFENSE = 'MODIFY_DEFENSE',
  DAMAGE = 'DAMAGE',
  HEAL = 'HEAL',
  MOVE = 'MOVE',
  PLACE = 'PLACE',
  DRAW_CARD = 'DRAW_CARD',
  DISCARD = 'DISCARD',
}

export interface CardEffect {
  id: string
  timing: EffectTiming
  type: EffectType
  value?: number
  condition?: string
  target: EffectTarget
}

// modifiers.ts
export enum ValueModifierType {
  SET = 'SET',
  ADD = 'ADD',
  IGNORE = 'IGNORE',
}

export interface ValueModifier {
  type: ValueModifierType
  value: number
  source: string // cardId или abilityId
  timestamp: number // для определения порядка
  ownerId: string // attacker или defender
}

// movement.ts
export enum MovementType {
  MOVE = 'MOVE',
  PLACE = 'PLACE',
}

export interface MovementAction {
  type: MovementType
  fighterId: string
  from: Position
  to: Position
  path?: Position[]
}
```

---

## Задача 6.2 - CombatResolver (КРИТИЧНО)

Создать ключевую систему боя с правильным порядком эффектов.

### Действия:
1. Создать `CombatResolverService` с методом `resolveCombat()`
2. Реализовать полный цикл боя по правилам Unmatched:

```
1. Проверяем смежность/зону (isAdjacent с context)
2. Защищающийся может сыграть карту защиты
3. Собираем эффекты ВО ВРЕМЯ БОЯ с обеих карт
4. Сортируем одновременные эффекты:
   - Эффекты защищающегося → первыми
   - Эффекты атакующего → вторыми
   - Один владелец → по timestamp
5. Применяем эффекты по порядку
6. Применяем способности героев (поверх модификаторов)
7. Вычисляем итоговые значения (applyValueModifiers)
8. Определяем победителя (Атака - Защита)
9. Наносим боевой урон
10. Применяем эффекты ПОСЛЕ БОЯ (сначала защищающийся!)
11. Обрабатываем дополнительные атаки
```

3. Реализовать правила:
   - Если два эффекта одновременно - первым защищающийся
   - Атака = 0 → побеждает защищающийся
   - Доп. атаки: цель сохраняется

### Файлы:
```
backend/src/game/engine/
├── combat-resolver.service.ts
└── combat-state.ts
```

### CombatResolverService:
```typescript
@Injectable()
class CombatResolverService {
  resolveCombat(
    state: GameState,
    attackerId: string,
    defenderId: string,
    attackCard: Card,
    defenseCard?: Card,
  ): CombatResult {
    // 1. Проверка смежности
    // 2. Сбор эффектов ВО ВРЕМЯ БОЯ
    // 3. Сортировка эффектов
    // 4. Применение эффектов
    // 5. Применение способностей героев
    // 6. Вычисление итоговых значений
    // 7. Определение победителя
    // 8. Нанесение урона
    // 9. Эффекты ПОСЛЕ БОЯ
    // 10. Дополнительные атаки
  }

  private resolveDuringCombatEffects(
    attackEffects: CardEffect[],
    defenseEffects: CardEffect[],
  ): void
  // Защищающийся первым!

  private resolveAfterCombatEffects(
    attackEffects: CardEffect[],
    defenseEffects: CardEffect[],
  ): void
  // Защищающийся первым!
}
```

---

## Задача 6.3 - ValueModifierSystem

Создать систему модификаторов значений карт.

### Действия:
1. Создать сервис для применения модификаторов:
   - SET ("становится равным") - сбрасывает предыдущие
   - ADD ("увеличьте/уменьшите") - суммируется
   - IGNORE ("игнорируйте") - не учитывается

2. Обработка специальных случаев:
   - "Невидимый противник": значение = 0, эффекты карт не отменяются
   - Способности героев (Артур) работают поверх "игнорирования"
   - "Последний SET выигрывает" - применяется последний SET по timestamp

### Файлы:
```
backend/src/game/engine/
└── value-modifier.service.ts
```

### Алгоритм:
```typescript
@Injectable()
class ValueModifierService {
  applyValueModifiers(
    baseValue: number,
    modifiers: ValueModifier[],
    heroAbility?: HeroAbility,
  ): number {
    // 1. Найти последний SET-модификатор по timestamp
    const lastSet = modifiers
      .filter(m => m.type === ValueModifierType.SET)
      .sort((a, b) => b.timestamp - a.timestamp)[0]

    // 2. Если есть SET → baseValue = setValue
    let value = lastSet ? lastSet.value : baseValue

    // 3. Применить все ADD-модификаторы
    const addModifiers = modifiers.filter(m => m.type === ValueModifierType.ADD)
    value += addModifiers.reduce((sum, m) => sum + m.value, 0)

    // 4. IGNORE - пропустить при подсчёте (обрабатывается вызывающим кодом)
    // 5. Применить способности героев (поверх всех модификаторов)
    if (heroAbility) {
      value = this.applyHeroAbility(value, heroAbility)
    }

    return value
  }
}
```

---

## Задача 6.4 - AdjacencySystem

Создать систему смежности с учётом специальных полей.

### Действия:
1. Создать `AdjacencyService`:
   - `isAdjacent(pos1, pos2, context)` - проверка смежности
   - Учесть потайные ходы: смежны только для movement
   - Учесть двери: проверять статус (открыта/закрыта)
   - Учесть возвышенность: проверять бонус к атаке

### Файлы:
```
backend/src/game/engine/
├── adjacency.service.ts
└── board-features/
    ├── secret-passage.ts
    ├── door.ts
    └── high-ground.ts
```

### AdjacencyService:
```typescript
@Injectable()
class AdjacencyService {
  isAdjacent(
    state: GameState,
    pos1: Position,
    pos2: Position,
    context: 'movement' | 'attack' | 'effect',
  ): boolean {
    const board = state.board

    // Потайные ходы: смежны только для movement
    if (this.hasSecretPassage(board, pos1, pos2)) {
      return context === 'movement'
    }

    // Двери: проверять статус
    if (this.hasDoor(board, pos1, pos2)) {
      return this.isDoorOpen(board, pos1, pos2)
    }

    // Стандартная смежность
    return this.isStandardAdjacent(pos1, pos2)
  }

  getHighGroundBonus(
    state: GameState,
    attackerPos: Position,
    defenderPos: Position,
  ): number {
    // +1 если:
    // - атакующий на возвышенности
    // - защищающийся ниже
    // - смежны
    // - есть стрелка
    // Бонус НЕ суммируется (максимум +1)
    return 0 // или 1
  }
}
```

---

## Задача 6.5 - MovementSystem

Создать систему перемещения.

### Действия:
1. Создать `MovementService`:
   - Различать MOVE (соблюдать правила) и PLACE (телепорт)
   - Проверять: дистанция 0 включается в "до N"
   - Нельзя двигаться сквозь врагов
   - Жетоны тумана считаются свободными

### Файлы:
```
backend/src/game/engine/
└── movement.service.ts
```

### MovementService:
```typescript
@Injectable()
class MovementService {
  canMove(
    state: GameState,
    fighterId: string,
    from: Position,
    to: Position,
    maxDistance: number,
  ): boolean {
    // 1. Проверить расстояние (0 включается)
    // 2. Проверить путь на препятствия
    // 3. Нельзя сквозь врагов
    // 4. Жетоны тумана = свободные
  }

  getValidMoves(
    state: GameState,
    fighterId: string,
    maxDistance: number,
  ): Position[] {
    // Вернуть все допустимые позиции
  }

  placeFighter(
    state: GameState,
    fighterId: string,
    position: Position,
  ): GameState {
    // Телепортация - игнорирует правила
  }
}
```

---

## Задача 6.6 - GameRulesValidator

Создать валидатор игровых действий.

### Действия:
1. Создать GameRulesValidator:
   - `validateManeuver()`, `validateMove()`, `validateAttack()`
   - `isAdjacent()` с контекстом (movement/attack/effect)
   - `canPlaceFighter()` - зона героя, жетоны тумана
   - `canPlayCardAsAttack()`, `canPlayCardAsDefense()`
   - `getHighGroundBonus()` - 0 или 1

### Файлы:
```
backend/src/game/validators/
├── game-rules.validator.ts
└── validation-result.ts
```

### GameRulesValidator:
```typescript
@Injectable()
class GameRulesValidator {
  validateManeuver(state: GameState, dto: ManeuverDto): ValidationResult
  validateMove(state: GameState, dto: MoveDto): ValidationResult
  validateAttack(state: GameState, dto: AttackDto): ValidationResult
  validateDefense(state: GameState, dto: DefenseDto): ValidationResult
  validateTurn(state: GameState, playerId: string): ValidationResult

  isAdjacent(
    state: GameState,
    pos1: Position,
    pos2: Position,
    context: 'movement' | 'attack' | 'effect',
  ): boolean

  canPlaceFighter(state: GameState, fighterId: string, pos: Position): boolean
  // - Зона героя для стартового размещения
  // - Если зона забита: смежные ячейки
  // - Жетоны тумана = свободные

  canPlayCardAsAttack(state: GameState, card: Card): boolean
  canPlayCardAsDefense(state: GameState, card: Card): boolean

  getHighGroundBonus(
    state: GameState,
    attackerPos: Position,
    defenderPos: Position,
  ): number
}
```

---

## Задача 6.7 - DistributedLockService

Создать сервис распределённых блокировок.

### Действия:
1. Создать DistributedLockService:
   - `acquireGameLock(gameId: string, ttl: number)`
   - `releaseLock(lock: Lock)`
   - `withLock<T>(gameId: string, fn: () => Promise<T>)`

### Файлы:
```
backend/src/common/services/
└── distributed-lock.service.ts
```

### DistributedLockService:
```typescript
@Injectable()
class DistributedLockService {
  // TTL увеличен до 10 сек для защиты от GC pause
  async acquireGameLock(gameId: string, ttl: number = 10000): Promise<Lock | null>

  async releaseLock(lock: Lock): Promise<void>

  async withLock<T>(
    gameId: string,
    fn: () => Promise<T>,
  ): Promise<T>

  async isGameLocked(gameId: string): Promise<boolean>
}

interface Lock {
  key: string
  token: string
  acquiredAt: number
  ttl: number
}
```

### Результат:
- Игровая логика соответствует правилам Unmatched
- Боевая система работает корректно
- Все специальные случаи обработаны
