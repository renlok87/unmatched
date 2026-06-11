# Архитектурное ревью: Frontend Tasks

**Автор:** Claude Opus
**Дата:** 2025-01-31
**Статус:** Черновик

---

## Общая оценка

Документация хорошо структурирована и покрывает основные UI компоненты. Однако есть критические архитектурные пробелы, особенно в области:
1. **Offline-first архитектуры**
2. **Конфликтов состояния при race conditions**
3. **Безопасности и авторизации**
4. **Accessibility (a11y)**
5. **Производительности на больших списках**

---

## Критические проблемы (Blocker)

### 1. Race Conditions в Matchmaking

**Файл:** `01-lobby-matchmaking.md`

**Проблема:** При быстром переключении между экранами возможны race conditions:

```typescript
// СЦЕНАРИЙ: Пользователь быстро кликает "Найти игру" → "Отмена" → "Найти"
// БЕЗ ПРОПУСКА ОЧЕРЕДИ НА СЕРВЕРЕ

useEffect(() => {
  const joinMatchmaking = async () => {
    await joinQueue({ mode: '1v1' });
  };
  joinMatchmaking();
}, []);

// ❌ ПРОБЛЕМА: Если пользователь размонтирует компонент до завершения,
// подписка может быть создана на размонтированном компоненте
```

**Решение:**

```typescript
// Добавляем AbortController pattern
const useMatchmaking = () => {
  const abortControllerRef = useRef<AbortController | null>(null);

  const joinQueue = useCallback(async (mode: GameMode) => {
    // Отменяем предыдущие запросы
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    try {
      const { data } = await apolloClient.mutate({
        mutation: JOIN_QUEUE_MUTATION,
        context: {
          fetchOptions: {
            signal: abortControllerRef.current.signal,
          },
        },
      });
      // ...
    } catch (error) {
      if (error.name !== 'AbortError') {
        // Обрабатываем только реальные ошибки
      }
    }
  }, []);

  return { joinQueue };
};
```

### 2. Optimistic Updates Conflicts

**Файл:** `04-game-view.md`, `05-combat-ui.md`

**Проблема:** Отсутствует обработка конфликтов при одновременных действиях:

```typescript
// СЦЕНАРИЙ: Оба игрока атакуют одновременно
// Игрок A атакует → optimistic update
// Игрок B атакует → optimistic update
// Сервер подтверждает только B, отклоняет A
// ❌ UI показывает неверное состояние
```

**Решение:**

```typescript
// Добавляем sequence-based conflict resolution
interface PendingAction {
  id: string;
  sequenceNumber: number;
  mutation: DocumentNode;
  variables: unknown;
  predictedState: GameState;
  rollbackState: GameState;
  status: 'pending' | 'confirmed' | 'rejected' | 'expired';
  timestamp: number;
}

interface OptimisticState {
  pendingActions: PendingAction[];
  conflicts: ActionConflict[];
}

// При получении серверного обновления:
function resolveConflicts(
  serverState: ServerGameState,
  pendingActions: PendingAction[]
): ResolvedState {
  const confirmed = pendingActions.filter(
    a => a.sequenceNumber <= serverState.sequenceNumber
  );

  const rejected = pendingActions.filter(a =>
    serverState.rejectedSequences?.includes(a.sequenceNumber)
  );

  // Rollback rejected actions
  rejected.forEach(action => {
    applyRollback(action.rollbackState);
  });

  return {
    state: serverState,
    confirmed: confirmed.map(a => a.id),
    rejected: rejected.map(a => a.id),
  };
}
```

### 3. Hero Selection — Double Confirm Bug

**Файл:** `02-hero-selection.md`

**Проблема:** Пользователь может дважды отправить confirm:

```typescript
// СЦЕНАРИЙ: Задержка сети + быстрый пользователь
// Клик "Подтвердить" → mutation отправлена
// Клик ещё раз "Подтвердить" → вторая mutation
// ❌ Два confirm, возможно разные герои
```

**Решение:**

```typescript
// Добавляем idempotency key и локальный lock
interface HeroSelectionStore {
  selectedHero: Hero | null;
  confirming: boolean;
  confirmIdempotencyKey: string | null;
  selectHero: (heroId: string) => Promise<void>;
  confirmSelection: () => Promise<void>;
}

const confirmSelection = async () => {
  if (confirming || confirmIdempotencyKey) return;

  const idempotencyKey = crypto.randomUUID();
  set({ confirming: true, confirmIdempotencyKey: idempotencyKey });

  try {
    await apolloClient.mutate({
      mutation: CONFIRM_HERO_MUTATION,
      variables: {
        gameId,
        idempotencyKey, // Сервер должен дедуплицировать
      },
    });
  } finally {
    set({ confirming: false });
  }
};
```

---

## Важные проблемы (High Priority)

### 4. WebSocket Reconnection State Loss

**Файл:** `04-game-view.md`, `src/hooks/useGameSync.ts`

**Проблема:** При переподключении теряется контекст действий:

```typescript
// СЦЕНАРИЙ: Игрок атакует → disconnect → reconnect
// useGameSync переподключается
// ❌ Игрок не знает, была ли атака применена
```

**Решение:**

```typescript
// Добавляем pending actions persistence
interface PendingActionsStore {
  actions: PersistedAction[];
  save: () => void;
  restore: () => void;
  clear: () => void;
}

// При переподключении
const handleReconnect = async () => {
  // 1. Загружаем свежее состояние
  const freshState = await fetchGameState(gameId);

  // 2. Сравниваем с pending actions
  const pending = pendingActionsStore.actions;

  // 3. Для каждого pending action проверяем статус
  for (const action of pending) {
    const wasApplied = await checkActionStatus(action.id);

    if (!wasApplied && Date.now() - action.timestamp < 30000) {
      // Повторяем действие если < 30 сек
      await retryAction(action);
    } else {
      // Откатываем оптимистичный update
      rollbackAction(action);
    }
  }

  pendingActionsStore.clear();
};
```

### 5. Room View — Host Migration

**Файл:** `03-room-setup.md`

**Проблема:** Не предусмотрен сценарий отключения хоста:

```typescript
// СЦЕНАРИЙ: Хост отключается
// ❌ Никто не может начать игру
// ❌ Комната "висит"
```

**Решение:**

```typescript
// Добавляем host migration
interface RoomState {
  hostId: string;
  players: Player[];
  hostPriority: string[]; // IDs по порядку миграции
}

subscription HostLeft($gameId: ID!) {
  hostLeft(gameId: $gameId) {
    newHostId
    reason
  }
}

// На клиенте
useEffect(() => {
  const sub = subscribeToHostEvents(gameId, {
    onHostLeft: (event) => {
      if (event.newHostId === currentUserId) {
        showNotification("Вы теперь хост комнаты!");
        set({ isHost: true });
      } else {
        showNotification(`${getPlayerName(event.newHostId)} теперь хост.`);
      }
    },
  });

  return () => sub.unsubscribe();
}, [gameId]);
```

### 6. Combat UI — Timeout Edge Cases

**Файл:** `05-combat-ui.md`

**Проблема:** Что происходит при истечении таймера защиты:

```typescript
// СЦЕНАРИЙ: Таймер защиты → 0
// ❌ Неясно: авто-проигрыш? авто-нет защиты?
// ❌ Нужно ли показывать результат если defending игрок offline?
```

**Решение:**

```typescript
// Добавляем чёткие состояния
enum CombatTimeoutAction {
  AUTO_PASS = 'AUTO_PASS',        // Автоматически пас
  AUTO_DEFEND = 'AUTO_DEFEND',    // Авто защита минимальной картой
  FORFEIT = 'FORFEIT',            // Проигрыш боя
}

interface CombatTimerProps {
  timeRemaining: number;
  onTimeout: (action: CombatTimeoutAction) => void;
  timeoutAction: CombatTimeoutAction; // Конфиг с сервера
}

// В компоненте
useEffect(() => {
  if (timeRemaining <= 0) {
    // Сервер решает, что делать
    onTimeout(timeoutAction);

    // Визуально показываем что произошло
    if (timeoutAction === 'AUTO_PASS') {
      showSystemMessage("Время истекло. Автоматический пас.");
    } else if (timeoutAction === 'FORFEIT') {
      showSystemMessage("Время истекло. Вы проиграли бой.");
    }
  }
}, [timeRemaining, timeoutAction]);
```

---

## Средние проблемы (Medium Priority)

### 7. Leaderboard — Infinite Scroll Performance

**Файл:** `07-profile-leaderboard.md`

**Проблема:** Пагинация может вызвать проблемы с производительностью:

```typescript
// СЦЕНАРИЙ: 10,000+ игроков в таблице
// ❌ Виртуализация не упомянута
// ❌ React ререндеры всего списка
```

**Решение:**

```typescript
// Используем react-virtuoso или react-window
import { Virtuoso } from 'react-virtuoso';

interface LeaderboardTableProps {
  players: LeaderboardEntry[];
  loadMore: (offset: number) => Promise<void>;
  totalCount: number;
  isCurrentUser: (id: string) => boolean;
}

const LeaderboardTable: React.FC<LeaderboardTableProps> = ({
  players,
  loadMore,
  totalCount,
  isCurrentUser,
}) => {
  return (
    <Virtuoso
      style={{ height: 600 }}
      data={players}
      endReached={(offset) => loadMore(offset)}
      overscan={200}
      itemContent={(index, player) => (
        <PlayerRow
          player={player}
          isCurrentUser={isCurrentUser(player.user.id)}
        />
      )}
      components={{
        Footer: () => {
          if (players.length < totalCount) {
            return <LoadingSpinner />;
          }
          return null;
        },
      }}
    />
  );
};
```

### 8. Chat — Message Ordering

**Файл:** `06-social.md`

**Проблема:** Сообщения могут прийти не по порядку:

```typescript
// СЦЕНАРИЙ: Network lag + delivery time diff
// Сообщение A отправлено в 12:00:00, пришло в 12:00:05
// Сообщение B отправлено в 12:00:01, пришло в 12:00:03
// ❌ Порядок: B, A (неверный)
```

**Решение:**

```typescript
// Добавляем server timestamp для сортировки
interface ChatMessage {
  id: string;
  content: string;
  userId: string;
  clientTimestamp: number;  // Время отправки
  serverTimestamp: number;  // Время получения на сервере (для сортировки)
  sequenceNumber: number;   // Порядковый номер
}

const useChatMessages = (gameId: string) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const addMessage = useCallback((newMessage: ChatMessage) => {
    setMessages((prev) => {
      // Удаляем optimistic версию если есть
      const withoutOptimistic = prev.filter(
        m => m.clientTimestamp !== newMessage.clientTimestamp
      );

      // Вставляем с правильной сортировкой
      const withNew = [...withoutOptimistic, newMessage];
      return withNew.sort((a, b) =>
        a.sequenceNumber - b.sequenceNumber
      );
    });
  }, []);

  return { messages, addMessage };
};
```

### 9. Network Status Detection

**Файл:** Все фазы

**Проблема:** Нет обработки offline/online переходов:

```typescript
// СЦЕНАРИЙ: Пользователь теряет соединение
// ❌ Нет визуального индикатора
// ❌ Действия продолжают выполняться с ошибками
```

**Решение:**

```typescript
// Добавляем network status hook
const useNetworkStatus = () => {
  const [isOnline, setIsOnline] = useState(
    navigator.onLine
  );

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      showNotification("Соединение восстановлено", "success");
    };

    const handleOffline = () => {
      setIsOnline(false);
      showNotification("Потеряно соединение с интернетом", "error");
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return { isOnline };
};

// Интеграция с GameView
const GameView = () => {
  const { isOnline } = useNetworkStatus();
  const { connectionStatus } = useConnectionStatus();

  const isFullyConnected = isOnline && connectionStatus === 'connected';

  return (
    <>
      {!isOnline && <OfflineBanner />}
      {isOnline && connectionStatus === 'reconnecting' && <ReconnectingBanner />}
      {/* ... */}
    </>
  );
};
```

---

## Низкие проблемы (Low Priority)

### 10. Accessibility

**Проблема:** Нет упоминаний о:
- Keyboard navigation
- Screen reader support
- Focus management
- ARIA labels

**Рекомендации:**

```typescript
// Добавляем ARIA к игровым элементам
<Card
  role="button"
  tabIndex={0}
  aria-label={`Карта ${card.name}, значение ${card.value}`}
  aria-selected={isSelected}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      onClick();
    }
  }}
  onClick={onClick}
>

// Для доски
<BoardView
  role="grid"
  aria-label="Игровая доска"
>
  {spaces.map(space => (
    <BoardSpace
      role="gridcell"
      aria-label={`Позиция ${space.position.x}, ${space.position.y}`}
      aria-occupied={!!fighter}
    />
  ))}
</BoardView>

// Focus trap в модалках
const CreateGameDialog = ({ open, onClose }) => {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      // Trap focus внутри диалога
      const focusableElements = dialogRef.current?.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements?.[0] as HTMLElement;
      firstElement?.focus();
    }
  }, [open]);
};
```

---

## Отсутствующие разделы в документации

### 1. Error Boundaries

Нужен единый подход к обработке ошибок:

```typescript
// src/components/errors/GameErrorBoundary.tsx
interface GameErrorBoundaryProps {
  gameId: string;
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error: Error; retry: () => void }>;
}

export const GameErrorBoundary: React.FC<GameErrorBoundaryProps> = ({
  gameId,
  children,
  fallback: Fallback = DefaultErrorFallback,
}) => {
  const [error, setError] = useState<Error | null>(null);

  const retry = useCallback(() => {
    setError(null);
    // Перезагружаем состояние игры
    window.location.reload();
  }, []);

  // Глобальный обработчик unhandledrejections
  useEffect(() => {
    const handler = (event: PromiseRejectionEvent) => {
      console.error('[GameErrorBoundary] Unhandled rejection:', event.reason);
      setError(new Error(event.reason?.message || 'Unknown error'));
    };

    window.addEventListener('unhandledrejection', handler);
    return () => window.removeEventListener('unhandledrejection', handler);
  }, []);

  if (error) {
    return <Fallback error={error} retry={retry} />;
  }

  return <>{children}</>;
};
```

### 2. Analytics Events

Нужно добавить трекинг для анализа UX:

```typescript
// Отслеживаемые события
interface AnalyticsEvent {
  // Matchmaking
  'matchmaking.joined': { mode: GameMode };
  'matchmaking.cancelled': { waitTime: number };
  'matchmaking.match_found': { waitTime: number };

  // Hero Selection
  'hero.selected': { heroId: string };
  'hero.confirm_time': { duration: number };

  // Game Flow
  'game.action': { type: string; duration: number };
  'game.turn_duration': { turn: number; duration: number };

  // Errors
  'error_occurred': { type: string; message: string };
}

const useAnalytics = () => ({
  track: <K extends keyof AnalyticsEvent>(
    event: K,
    properties: AnalyticsEvent[K]
  ) => {
    // Отправка в analytics service
  },
});
```

### 3. Feature Flags

Для постепенного внедрения новых функций:

```typescript
// src/lib/featureFlags.ts
interface FeatureFlags {
  'combat-auto-resolve': boolean;
  'chat-emotes': boolean;
  'leaderboard-friends': boolean;
  'replay-system': boolean;
}

declare const FEATURE_FLAGS: FeatureFlags;

export const isFeatureEnabled = (feature: keyof FeatureFlags): boolean => {
  return FEATURE_FLAGS[feature] ?? false;
};

// Использование
if (isFeatureEnabled('chat-emotes')) {
  return <EmotePicker />;
}
```

---

## Рекомендуемый порядок доработок

### Критические (Blocker)
1. ✅ Добавить idempotency keys для всех критичных мутаций
2. ✅ Реализовать conflict resolution для optimistic updates
3. ✅ Добавить cleanup для размонтированных компонентов

### Высокий приоритет
4. ✅ WebSocket reconnection с восстановлением состояния
5. ✅ Host migration для Room View
6. ✅ Таймауты с чётким поведением

### Средний приоритет
7. ✅ Виртуализация для длинных списков
8. ✅ Упорядочивание сообщений по sequence number
9. ✅ Network status detection

### Низкий приоритет
10. ✅ Accessibility улучшения
11. ✅ Error boundaries
12. ✅ Analytics integration

---

## GraphQL Schema дополнения

Рекомендуемые additions к существующим schema:

```graphql
# Добавить к существующим мутациям
input MutationInput {
  # Все мутации должны поддерживать idempotency
  idempotencyKey: String
  # Версия состояния для optimistic locking
  expectedSequence: Int
}

# Ответы мутаций должны включать
type MutationResponse {
  success: Boolean
  sequenceNumber: Int!
  rejectedSequences: [Int!]!
  conflictResolution: ConflictResolution
}

enum ConflictResolution {
  ACCEPTED
  REJECTED
  MERGED
  RETRY
}

# Расширенная информация о combat
type CombatState {
  # ... существующие поля
  timeoutAction: CombatTimeoutAction
  autoResolveAt: DateTime
}

enum CombatTimeoutAction {
  AUTO_PASS
  AUTO_DEFEND
  FORFEIT
}
```

---

## Заключение

Документация `docs/frontend-tasks` предоставляет хорошую базу для реализации, но требует доработок в следующих областях:

| Область | Статус | Приоритет |
|---------|--------|-----------|
| Race conditions | ❌ Не проработаны | 🔴 Критический |
| Optimistic updates | ⚠️ Частично | 🔴 Критический |
| Reconnection | ⚠️ Базовая | 🟡 Высокий |
| Host migration | ❌ Отсутствует | 🟡 Высокий |
| Performance | ⚠️ Не проработана | 🟢 Средний |
| Accessibility | ❌ Отсутствует | 🟢 Низкий |

**Рекомендуется:** Добавить отдельный документ `08-edge-cases.md` с детальным описанием всех corner cases и их решений.
