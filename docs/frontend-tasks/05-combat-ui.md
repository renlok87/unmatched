# ФАЗА 5: Combat UI

## Задача 5.1 - CombatPanel

Панель боя при атаке — главный компонент боевой системы.

### Компоненты для создания:
```
src/components/combat/
├── CombatPanel.tsx         # Главная панель боя
├── AttackerView.tsx        # Атакующий боец
├── DefenderView.tsx        # Защищающийся боец
├── AttackCardDisplay.tsx   # Карта атаки
├── DefenseCardDisplay.tsx  # Карта защиты
├── DamageIndicator.tsx     # Индикатор урона
└── CombatTimer.tsx         # Таймер защиты
```

---

### CombatPanel.tsx

**Функциональность:**
- Отображение при начале боя (phase === COMBAT)
- Показывает атакующего и защищающегося бойцов
- Отображает сыгранные карты
- Счёт боя (attack value vs defense value)
- Таймер для защиты (30 сек)
- Индикатор модификаторов (boosts, effects)
- Кнопка "Разрешить бой" для атакующего

**GraphQL подписка:**
```graphql
subscription CombatUpdates($gameId: ID!) {
  gameUpdates(gameId: $gameId) {
    gameState {
      phase
      combat {
        attackerId
        defenderId
        attackCard { ... }
        defenseCard { ... }
        attackValue
        defenseValue
        modifiers { ... }
        startedAt
      }
    }
  }
}
```

**Пропсы:**
```typescript
interface CombatPanelProps {
  combat: CombatState;
  currentUserId: string;
  isAttacker: boolean;
  isDefender: boolean;
  onResolveCombat: () => void;
}
```

---

### AttackerView.tsx

**Функциональность:**
- Изображение атакующего бойца
- Имя и тип (hero/sidekick)
- Текущее здоровье
- Сыгранная карта атаки
- Значение атаки (с модификаторами)
- Анимация атаки

**Пропсы:**
```typescript
interface AttackerViewProps {
  fighter: Fighter;
  attackCard: Card;
  attackValue: number;
  modifiers: ValueModifier[];
}
```

---

### DefenderView.tsx

**Функциональность:**
- Изображение защищающегося бойца
- Имя и тип
- Текущее здоровье
- Сыгранная карта защиты (если есть)
- Значение защиты (с модификаторами)
- Placeholder если защита не сыграна

**Пропсы:**
```typescript
interface DefenderViewProps {
  fighter: Fighter;
  defenseCard: Card | null;
  defenseValue: number;
  modifiers: ValueModifier[];
  isHidden: boolean;  // Скрыть для атакующего
}
```

---

### AttackCardDisplay.tsx

**Функциональность:**
- Отображение карты атаки (используем существующий Card.tsx)
- Подсветка типа атаки (красный для ATTACK)
- Значение карты (base + boost)
- Эффекты карты
- Анимация при розыгрыше

---

### DefenseCardDisplay.tsx

**Функциональность:**
- Отображение карты защиты (если есть)
- Рубашка карты если ещё не сыграна (для атакующего)
- Полная карта для защищающегося
- Значение защиты (с модификаторами)
- Placeholder "Нет защиты"

**Пропсы:**
```typescript
interface DefenseCardDisplayProps {
  card: Card | null;
  defenseValue: number;
  isHidden: boolean;  // Скрыть для атакующего
}
```

---

### DamageIndicator.tsx

**Функциональность:**
- Анимация урона
- Попап с числом урона
- Эффекты (shake, flash red)
- Звуковые эффекты (опционально)
- Позиционирование над бойцом

**Пропсы:**
```typescript
interface DamageIndicatorProps {
  damage: number;
  target: 'attacker' | 'defender';
  onAnimationComplete: () => void;
}
```

**Анимация:**
```css
@keyframes damage-flash {
  0% { opacity: 0; transform: scale(0.5); }
  50% { opacity: 1; transform: scale(1.2); }
  100% { opacity: 0; transform: scale(1) translateY(-50px); }
}

.damage-indicator {
  animation: damage-flash 1s ease-out forwards;
}
```

---

### CombatTimer.tsx

**Функциональность:**
- Обратный отсчёт 30 секунд на защиту
- Круговой прогресс-бар
- Красный цвет когда < 10 секунд
- Анимация пульсации

**Пропсы:**
```typescript
interface CombatTimerProps {
  timeRemaining: number;
  totalTime: number;
}
```

---

## Задача 5.2 - DefenseCardSelector

Быстрый выбор карты защиты для защищающегося.

### Компонент:
```
src/components/combat/
└── DefenseCardSelector.tsx
```

**Функциональность:**
- Отображение только DEFENSE карт в руке
- Подсветка playable карт
- Предпросмотр результата защиты (hover)
- Кнопка "Пропустить" (без защиты)
- Авто-закрытие после выбора

**GraphQL мутация:**
```graphql
mutation PlayDefense($gameId: ID!, $cardId: ID!) {
  playDefense(gameId: $gameId, cardId: $cardId) {
    state { ... }
    sequenceNumber
  }
}
```

**Пропсы:**
```typescript
interface DefenseCardSelectorProps {
  hand: Card[];
  onSelect: (cardId: string) => void;
  onPass: () => void;
  timeRemaining: number;
}
```

---

## Задача 5.3 - Combat Resolution

Визуализация разрешения боя.

### Компоненты:
```
src/components/combat/
├── CombatResolution.tsx    # Экран разрешения
└── CombatResult.tsx        # Результат боя
```

---

### CombatResolution.tsx

**Функциональность:**
- Анимация расчёта урона
- Отображение нанесённого урона
- Обновление здоровья бойцов
- Звуковые эффекты
- Переход к следующей фазе

**Состояния:**
```
1. COMBAT_IN_PROGRESS → ожидание защиты
2. COMBAT_RESOLVING → расчёт урона
3. COMBAT_COMPLETE → показ результата
```

---

### CombatResult.tsx

**Функциональность:**
- Отображение результата боя
- Нанесённый урон обоим бойцам (или одному)
- Побеждённый боец (если есть)
- Кнопка "Продолжить"

**GraphQL мутация:**
```graphql
mutation ResolveCombat($gameId: ID!) {
  resolveCombat(gameId: $gameId) {
    state { ... }
    sequenceNumber
  }
}
```

---

## Задача 5.4 - Attack Target Selector

Выбор цели для атаки.

### Компонент:
```
src/components/combat/
└── TargetSelector.tsx      # Выбор цели
```

**Функциональность:**
- Подсветка доступных целей на доске
- Показывает range атаки
- Клик на цель инициирует атаку

**Интеграция с BoardView:**
```typescript
// В BoardView добавить подсветку целей
const validTargets = getValidTargets(
  gameState,
  selectedFighterId,
  selectedCard
);

<BoardView
  highlightedTargets={validTargets}
  onTargetClick={handleAttack}
/>
```

---

## Задача 5.5 - Attack Flow

Полный поток атаки.

### Состояния:
```
1. SELECT_ATTACK_CARD → игрок выбирает карту атаки
2. SELECT_TARGET → игрок выбирает цель
3. COMBAT_PENDING → ожидание защиты соперника
4. COMBAT_RESOLVING → расчёт урона
5. COMBAT_COMPLETE → результат
```

### GraphQL мутация для атаки:
```graphql
mutation Attack($input: AttackInput!) {
  attack(input: $input) {
    state { ... }
    sequenceNumber
  }
}

input AttackInput {
  gameId: ID!
  attackerId: ID!
  cardId: ID!
  targetId: ID!
}
```

---

## Задача 5.6 - Combat Effects

Визуализация эффектов карт.

### Компоненты:
```
src/components/combat/
└── CombatEffects.tsx       # Эффекты боя
```

**Функциональность:**
- Отображение активных эффектов
- Иконки эффектов
- Tooltip с описанием
- Индикатор длительности

**Эффекты:**
- Boost value (усиление)
- Ignore defense (игнор защиты)
- Double damage (двойной урон)
- Shield (щит)

---

## Результат ФАЗЫ 5

- ✅ Пользователь видит панель боя
- ✅ Пользователь выбирает цель атаки
- ✅ Пользователь выбирает карту защиты
- ✅ Визуализация урона
- ✅ Результат боя с нанесённым уроном
- ✅ Авто-разрешение по таймеру

---

## Следующие шаги

→ [ФАЗА 6: Social](./06-social.md)
