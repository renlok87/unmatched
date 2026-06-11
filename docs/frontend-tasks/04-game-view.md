# ФАЗА 4: Game View UI

## Задача 4.1 - GameView

Главный игровой экран для мультиплеерной игры.

### Компоненты для создания:
```
src/components/game/
├── GameView.tsx            # Главный компонент
├── GameHeader.tsx          # Шапка игры
├── TurnIndicator.tsx       # Индикатор хода
├── ActionButtons.tsx       # Кнопки действий
├── OpponentHandView.tsx    # Рука соперника
└── DiscardPileView.tsx     # Сброс
```

---

### GameView.tsx

**Функциональность:**
- Компоновка игрового экрана (layout)
- Интеграция существующих компонентов:
  - [BoardView.tsx](../../src/components/board/BoardView.tsx)
  - [HandView.tsx](../../src/components/cards/HandView.tsx)
  - [GameControls.tsx](../../src/components/controls/GameControls.tsx)
- Подписка на игровые события через WebSocket
- Обработка ошибок和网络 disconnects
- Переход к Game Over при завершении

**Layout структура:**
```
┌─────────────────────────────────────┐
│  GameHeader (номер хода, таймер)    │
├──────────┬──────────────────────────┤
│          │                           │
│ Opponent │      BoardView            │
│ Hand     │                           │
│          │                           │
├──────────┴──────────────────────────┤
│  HandView      │   ActionButtons     │
├─────────────────┴────────────────────┤
│  GameControls (фазы, действия)       │
└─────────────────────────────────────┘
```

**Подписка на обновления:**
```typescript
// Использует существующий useGameSync hook
const { gameState, error, reconnect } = useGameSync(gameId);

useEffect(() => {
  if (gameState?.status === 'FINISHED') {
    // Показать GameOverModal
  }
}, [gameState?.status]);
```

---

### GameHeader.tsx

**Функциональность:**
- Номер хода / раунда
- Общий таймер игры (опционально)
- Кнопка настроек
- Кнопка выхода из игры
- Индикатор соединения (online/reconnecting)

**Пропсы:**
```typescript
interface GameHeaderProps {
  turnNumber: number;
  roundNumber: number;
  isConnected: boolean;
  onSettings: () => void;
  onLeave: () => void;
}
```

---

### TurnIndicator.tsx

**Функциональность:**
- Отображение чей сейчас ход
- Имя текущего игрока
- Аватар текущего игрока
- Таймер хода (опционально)
- Анимация перехода хода

**Пропсы:**
```typescript
interface TurnIndicatorProps {
  currentPlayer: Player;
  isYourTurn: boolean;
  timeRemaining?: number;
}
```

**Стили:**
- Выделение когда ваш ход
- Иконка/аватар слева
- Имя по центру
- Таймер справа

---

### ActionButtons.tsx

**Пunctionональность:**
- Кнопка "Конец хода" (End Turn)
- Кнопка "Пас" (Pass) — сброс карты
- Индикация доступности действий
- Hotkey hints (Space для End Turn)
- Confirm диалог для критических действий

**Пропсы:**
```typescript
interface ActionButtonsProps {
  canEndTurn: boolean;
  canPass: boolean;
  onEndTurn: () => void;
  onPass: () => void;
}
```

**GraphQL мутации:**
```graphql
mutation EndTurn($gameId: ID!) {
  endTurn(gameId: $gameId) {
    state { ... }
    sequenceNumber
  }
}

mutation Pass($gameId: ID!, $cardId: ID!) {
  pass(gameId: $gameId, cardId: $cardId) {
    state { ... }
    sequenceNumber
  }
}
```

---

### OpponentHandView.tsx

**Функциональность:**
- Количество карт соперника (число)
- Рубашки карт (визуализация)
- Индикатор последних сброшенных карт
- Hover показывает количество

**Пропсы:**
```typescript
interface OpponentHandViewProps {
  cardCount: number;
  lastDiscarded?: Card;
}
```

**Визуализация:**
- Горизонтальный список рубашек карт
- Число посередине
- Максимум 7 рубашек отображается, остальные "+X"

---

### DiscardPileView.tsx

**Функциональность:**
- Отображение сброса
- Последняя карта сверху
- Клик для просмотра всех сброшенных
- Фильтр по игроку

**Пропсы:**
```typescript
interface DiscardPileProps {
  topCard: Card | null;
  discardCount: number;
  onExpand: () => void;
}
```

---

## Задача 4.2 - Optimistic Updates

Оптимистичные обновления UI для мгновенной обратной связи.

### Хук:
```
src/hooks/
└── useOptimisticAction.ts  # Существует, использовать
```

**Использование:**
```typescript
const { execute, rollback } = useOptimisticAction({
  mutation: END_TURN_MUTATION,
  onOptimistic: (cache) => {
    // Локально обновляем state
  },
  onError: (error) => {
    // Rollback + показываем ошибку
  }
});
```

---

## Задача 4.3 - Game State Sync

Синхронизация состояния с сервером.

### Использование существующих компонентов:
- [remoteGameStore.ts](../../src/store/remoteGameStore.ts) — Zustand store
- [useGameSync.ts](../../src/hooks/useGameSync.ts) — WebSocket подписки

**Интеграция:**
```typescript
function GameView({ gameId }: { gameId: string }) {
  const { gameState, loading, error, reconnect } = useGameSync(gameId);
  const localState = useGameStore();

  // Merge remote + local state
  const mergedState = useMemo(() => {
    return {
      ...gameState,
      // Local optimistic updates overlay
      ...localState.pendingUpdates,
    };
  }, [gameState, localState.pendingUpdates]);

  if (loading) return <LoadingScreen />;
  if (error) return <ErrorScreen error={error} onRetry={reconnect} />;

  return <GameBoard state={mergedState} />;
}
```

---

## Задача 4.4 - Error Handling

Обработка ошибок в игре.

### Компоненты:
```
src/components/game/
└── GameErrorBoundary.tsx   # Error boundary для игры
```

**Функциональность:**
- Ловит ошибки рендеринга
- Показывает fallback UI
- Кнопка "Переподключиться"
- Автоматический retry при network errors

---

## Задача 4.5 - Reconnection

Восстановление соединения.

### Логика:**
1. Обнаруживаем disconnect (WebSocket close)
2. Показываем индикатор "Переподключение..."
3. Пытаемся переподключиться с exponential backoff
4. При успехе — запрашиваем пропущенные события (`since` параметр)
5. Применяем пропущенные события

**GraphQL subscription с reconnect:**
```graphql
subscription GameUpdates($gameId: ID!, $since: Int) {
  gameUpdates(gameId: $gameId, since: $since) {
    sequenceNumber
    gameState { ... }
    eventType
  }
}
```

---

## Результат ФАЗЫ 4

- ✅ Пользователь видит игровой экран
- ✅ Пользователь видит доску, руку, соперника
- ✅ Пользователь может совершать действия (end turn, pass)
- ✅ UI обновляется в реальном времени
- ✅ Обработка network errors
- ✅ Автоматическое переподключение

---

## Следующие шаги

→ [ФАЗА 5: Combat UI](./05-combat-ui.md)
