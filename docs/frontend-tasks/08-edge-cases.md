# Edge Cases: Детальное описание

Дополнительный документ к `docs/frontend-tasks` с описанием всех corner cases и рекомендованными решениями.

---

## Содержание

1. [Фаза 1: Lobby & Matchmaking](#фаза-1-lobby--matchmaking)
2. [Фаза 2: Hero Selection](#фаза-2-hero-selection)
3. [Фаза 3: Room Setup](#фаза-3-room-setup)
4. [Фаза 4: Game View](#фаза-4-game-view)
5. [Фаза 5: Combat UI](#фаза-5-combat-ui)
6. [Фаза 6: Social Features](#фаза-6-social-features)
7. [Фаза 7: Profile & Leaderboard](#фаза-7-profile--leaderboard)
8. [Кросс-фазные сценарии](#кросс-фазные-сценарии)

---

## Фаза 1: Lobby & Matchmaking

### EC-1.1: Rapid Queue Join/Leave

**Сценарий:** Пользователь быстро нажимает "Найти игру" → "Отмена" → "Найти игру"

**Проблема:** Множественные pending запросы, состояние гонки

```typescript
// ❌ БЕЗ ОБРАБОТКИ
const MatchmakingView = () => {
  const joinQueue = async () => {
    await apolloClient.mutate({ mutation: JOIN_QUEUE });
  };

  return <button onClick={joinQueue}>Найти игру</button>;
};
```

**Решение:**

```typescript
// ✅ С ОБРАБОТКОЙ
interface MatchmakingState {
  status: 'idle' | 'joining' | 'queued' | 'leaving';
  pendingRequest: { abort: () => void } | null;
}

const useMatchmaking = () => {
  const [state, setState] = useState<MatchmakingState>({
    status: 'idle',
    pendingRequest: null,
  });

  const joinQueue = useCallback(async (mode: GameMode) => {
    // Отменяем предыдущий запрос если есть
    if (state.pendingRequest) {
      state.pendingRequest.abort();
    }

    setState({ status: 'joining', pendingRequest: null });

    try {
      const abortController = new AbortController();

      const promise = apolloClient.mutate({
        mutation: JOIN_QUEUE_MUTATION,
        variables: { mode },
        context: {
          fetchOptions: { signal: abortController.signal },
        },
      });

      setState(prev => ({ ...prev, pendingRequest: { abort: () => abortController.abort() } }));

      await promise;

      setState({ status: 'queued', pendingRequest: null });
    } catch (error) {
      if (error.name !== 'AbortError') {
        setState({ status: 'idle', pendingRequest: null });
        throw error;
      }
    }
  }, [state.pendingRequest]);

  const leaveQueue = useCallback(async () => {
    if (state.status !== 'queued') return;

    setState({ status: 'leaving', pendingRequest: null });

    try {
      await apolloClient.mutate({ mutation: LEAVE_QUEUE_MUTATION });
      setState({ status: 'idle', pendingRequest: null });
    } catch {
      setState({ status: 'queued', pendingRequest: null });
    }
  }, [state.status]);

  return {
    status: state.status,
    joinQueue,
    leaveQueue,
  };
};
```

---

### EC-1.2: Match Found During Unmount

**Сценарий:** Пользователь получает матч, но компонент уже размонтирован

**Проблема:** Memory leak, попытки обновить несуществующий компонент

```typescript
// ❌ БЕЗ ОБРАБОТКИ
useEffect(() => {
  const subscription = apolloClient.subscribe({ query: MATCH_FOUND_SUB }).subscribe({
    next: (data) => {
      navigate(`/room/${data.matchFound.game.id}`); // ❌ Может быть размонтирован
    },
  });

  return () => subscription.unsubscribe();
}, []);
```

**Решение:**

```typescript
// ✅ С ОБРАБОТКОЙ
const useMatchFoundSubscription = (gameId: string) => {
  const navigate = useNavigate();
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;

    const subscription = apolloClient
      .subscribe({ query: MATCH_FOUND_SUB, variables: { gameId } })
      .subscribe({
        next: (data) => {
          // Проверяем что компонент всё ещё смонтирован
          if (isMountedRef.current && data?.matchFound?.game) {
            navigate(`/room/${data.matchFound.game.id}`);
          }
        },
      });

    return () => {
      isMountedRef.current = false;
      subscription.unsubscribe();
    };
  }, [gameId, navigate]);
};
```

---

### EC-1.3: Create Game During Network Issues

**Сценарий:** Пользователь создаёт игру при нестабильном соединении

**Проблема:** Неясно, была ли игра создана или нет

**Решение:**

```typescript
const useCreateGame = () => {
  const [pendingGames, setPendingGames] = useState<Set<string>>(new Set());

  const createGame = useCallback(async (input: CreateGameInput) => {
    const clientGeneratedId = crypto.randomUUID();

    // Оптимистично добавляем в список
    setPendingGames(prev => new Set(prev).add(clientGeneratedId));

    try {
      const { data } = await apolloClient.mutate({
        mutation: CREATE_GAME_MUTATION,
        variables: {
          input: {
            ...input,
            clientId: clientGeneratedId, // Для идемпотентности
          },
        },
      });

      // Удаляем из pending при успехе
      setPendingGames(prev => {
        const next = new Set(prev);
        next.delete(clientGeneratedId);
        return next;
      });

      return data.createGame;
    } catch (error) {
      // При ошибке тоже удаляем из pending
      setPendingGames(prev => {
        const next = new Set(prev);
        next.delete(clientGeneratedId);
        return next;
      });
      throw error;
    }
  }, []);

  // Показываем pending игры в UI
  const gameListWithPending = useMemo(() => {
    return [
      ...games,
      ...Array.from(pendingGames).map(id => ({
        id,
        status: 'PENDING' as const,
        isPending: true,
      })),
    ];
  }, [games, pendingGames]);

  return { createGame, gameList: gameListWithPending };
};
```

---

## Фаза 2: Hero Selection

### EC-2.1: Double Confirm Bug

**Сценарий:** Пользователь дважды нажимает "Подтвердить выбор"

**Проблема:** Две мутации, возможны разные герои

```typescript
// ✅ РЕШЕНИЕ с idempotency
const useHeroConfirmation = (gameId: string) => {
  const [confirmState, setConfirmState] = useState<{
    isConfirming: boolean;
    idempotencyKey: string | null;
  }>({ isConfirming: false, idempotencyKey: null });

  const confirmSelection = useCallback(async () => {
    // Предотвращаем двойной клик
    if (confirmState.isConfirming) {
      return;
    }

    const idempotencyKey = crypto.randomUUID();
    setConfirmState({ isConfirming: true, idempotencyKey });

    try {
      await apolloClient.mutate({
        mutation: CONFIRM_HERO_MUTATION,
        variables: { gameId, idempotencyKey },
      });

      setConfirmState({ isConfirming: false, idempotencyKey: null });
    } catch (error) {
      setConfirmState({ isConfirming: false, idempotencyKey: null });
      throw error;
    }
  }, [gameId, confirmState.isConfirming]);

  return { confirmSelection, isConfirming: confirmState.isConfirming };
};
```

---

### EC-2.2: Hero Taken During Selection

**Сценарий:** Пользователь выбирает героя, но соперник его занял

**Проблема:** UI показывает героя как доступного

```typescript
// ✅ РЕШЕНИЕ с real-time updates
const useHeroSelection = (gameId: string) => {
  const [heroes, setHeroes] = useState<Hero[]>([]);
  const [takenHeroIds, setTakenHeroIds] = useState<Set<string>>(new Set());
  const [selectedHeroId, setSelectedHeroId] = useState<string | null>(null);

  // Подписка на обновления выбора героев
  useEffect(() => {
    const subscription = apolloClient
      .subscribe({
        query: HERO_SELECTION_SUB,
        variables: { gameId },
      })
      .subscribe({
        next: ({ data }) => {
          const taken = new Set(
            data.gameUpdates.gameState.players
              .filter((p: any) => p.heroConfirmed)
              .map((p: any) => p.hero.id)
          );

          setTakenHeroIds(taken);

          // Если наш выбранный герой был взят
          if (selectedHeroId && taken.has(selectedHeroId)) {
            setSelectedHeroId(null);
            showNotification('Этот герой был выбран другим игроком', 'warning');
          }
        },
      });

    return () => subscription.unsubscribe();
  }, [gameId, selectedHeroId]);

  const isHeroAvailable = useCallback((heroId: string) => {
    return !takenHeroIds.has(heroId);
  }, [takenHeroIds]);

  return {
    heroes,
    selectedHeroId,
    setSelectedHeroId,
    isHeroAvailable,
    takenHeroIds,
  };
};
```

---

### EC-2.3: Timer Expiration

**Сценарий:** Время выбора истекло, но UI не обновился

```typescript
// ✅ РЕШЕНИЕ с server authority
const useHeroSelectionTimer = (gameId: string, expiresAt: Date) => {
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    const calculateRemaining = () => {
      const now = Date.now();
      const expires = new Date(expiresAt).getTime();
      const remaining = Math.max(0, expires - now);

      setTimeRemaining(remaining);

      if (remaining === 0 && !isExpired) {
        setIsExpired(true);
        // Запрашиваем актуальное состояние с сервера
        apolloClient
          .query({ query: GAME_STATUS_QUERY, variables: { gameId } })
          .then(({ data }) => {
            // Сервер решает, что делать
            if (data.game.status === 'HERO_SELECTION_EXPIRED') {
              // Назначаем случайного героя или показываем ошибку
              handleSelectionExpired(data.game);
            }
          });
      }
    };

    calculateRemaining();
    const interval = setInterval(calculateRemaining, 100);

    return () => clearInterval(interval);
  }, [expiresAt, isExpired, gameId]);

  return { timeRemaining: Math.ceil(timeRemaining / 1000), isExpired };
};
```

---

## Фаза 3: Room Setup

### EC-3.1: Host Disconnect

**Сценарий:** Хост отключается, комната остаётся без управления

```typescript
// ✅ РЕШЕНИЕ с host migration
interface RoomStore {
  hostId: string;
  currentUserId: string;
  isHost: boolean;
  hostPriority: string[]; // Порядок миграции хоста
}

const useHostMigration = (gameId: string) => {
  const { hostId, currentUserId } = useRoomStore();

  useEffect(() => {
    const subscription = apolloClient
      .subscribe({
        query: HOST_MIGRATION_SUB,
        variables: { gameId },
      })
      .subscribe({
        next: ({ data }) => {
          const { newHostId, previousHostId } = data.hostMigration;

          if (previousHostId === hostId && newHostId !== hostId) {
            if (newHostId === currentUserId) {
              // Вы теперь хост!
              showNotification('Вы стали хостом комнаты', 'success');
              updateRoomState({ isHost: true, hostId: newHostId });
            } else {
              const newHostName = getPlayerName(newHostId);
              showNotification(`${newHostName} теперь хост комнаты`, 'info');
              updateRoomState({ isHost: false, hostId: newHostId });
            }
          }
        },
      });

    return () => subscription.unsubscribe();
  }, [gameId, hostId, currentUserId]);
};
```

---

### EC-3.2: Fighter Placement Validation

**Сценарий:** Игрок пытается разместить бойца в недопустимой зоне

```typescript
// ✅ РЕШЕНИЕ с client + server validation
const useFighterPlacement = (gameId: string, playerId: string) => {
  const [validZones, setValidZones] = useState<Position[]>([]);
  const [placedFighters, setPlacedFighters] = useState<Map<string, Position>>(new Map());
  const [pendingPlacements, setPendingPlacements] = useState<Map<string, Position>>(new Map());

  // Загружаем валидные зоны
  useEffect(() => {
    apolloClient
      .query({
        query: VALID_ZONES_QUERY,
        variables: { gameId, playerId },
      })
      .then(({ data }) => {
        setValidZones(data.validSpawnZones.map((z: any) => z.position)));
      });
  }, [gameId, playerId]);

  const placeFighter = useCallback(async (fighterId: string, position: Position) => {
    // 1. Клиентская валидация
    const isValid = validZones.some(
      z => z.x === position.x && z.y === position.y
    );

    if (!isValid) {
      showNotification('Недопустимая позиция для размещения', 'error');
      return;
    }

    // 2. Оптимистичный update
    setPendingPlacements(prev => new Map(prev).set(fighterId, position));

    try {
      // 3. Серверная валидация
      await apolloClient.mutate({
        mutation: PLACE_FIGHTER_MUTATION,
        variables: { gameId, input: { fighterId, position } },
      });

      // Подтверждаем размещение
      setPlacedFighters(prev => new Map(prev).set(fighterId, position));
      setPendingPlacements(prev => {
        const next = new Map(prev);
        next.delete(fighterId);
        return next;
      });
    } catch (error) {
      // Откатываем при ошибке
      setPendingPlacements(prev => {
        const next = new Map(prev);
        next.delete(fighterId);
        return next;
      });

      if (error.message.includes('Invalid position')) {
        showNotification('Эта позиция недоступна', 'error');
      } else {
        showNotification('Не удалось разместить бойца', 'error');
      }
    }
  }, [validZones, gameId]);

  const isPlacementValid = useCallback((position: Position) => {
    return validZones.some(
      z => z.x === position.x && z.y === position.y
    );
  }, [validZones]);

  return {
    placedFighters,
    pendingPlacements,
    placeFighter,
    isPlacementValid,
  };
};
```

---

### EC-3.3: All Ready But No Start Button

**Сценарий:** Все игроки готовы, но хост не нажимает "Начать"

```typescript
// ✅ РЕШЕНИЕ с auto-start
const useRoomAutoStart = (gameId: string) => {
  const { players, isHost, allReady } = useRoomStore();
  const [autoStartTime, setAutoStartTime] = useState<number | null>(null);

  useEffect(() => {
    if (!isHost || !allReady) {
      setAutoStartTime(null);
      return;
    }

    // Показываем уведомление что можно начать
    showNotification('Все игроки готовы! Начните игру или ожидайте автозапуск.', 'info');

    // Автозапуск через 30 секунд
    const timer = setTimeout(() => {
      if (allReady) {
        startGame(gameId);
      }
    }, 30000);

    setAutoStartTime(Date.now() + 30000);

    return () => clearTimeout(timer);
  }, [allReady, isHost, gameId]);

  // Для не-хостов показываем обратный отсчёт
  const timeUntilAutoStart = useMemo(() => {
    if (!autoStartTime) return null;
    return Math.max(0, Math.ceil((autoStartTime - Date.now()) / 1000));
  }, [autoStartTime]);

  return { timeUntilAutoStart };
};
```

---

## Фаза 4: Game View

### EC-4.1: Action During Opponent's Turn

**Сценарий:** Пользователь пытается совершить действие во время хода соперника

```typescript
// ✅ РЕШЕНИЕ с isYourTurn guard
const useGameActions = (gameId: string) => {
  const { currentTurnPlayerId, currentUserId } = useGameStore();
  const isYourTurn = currentTurnPlayerId === currentUserId;

  const endTurn = useCallback(async () => {
    if (!isYourTurn) {
      showNotification('Сейчас не ваш ход!', 'warning');
      return;
    }

    try {
      await apolloClient.mutate({
        mutation: END_TURN_MUTATION,
        variables: { gameId },
      });
    } catch (error) {
      if (error.message.includes('Not your turn')) {
        showNotification('Ход уже перешёл к другому игроку', 'info');
      }
    }
  }, [gameId, isYourTurn]);

  const playCard = useCallback(async (cardId: string) => {
    if (!isYourTurn) {
      showNotification('Подождите своего хода', 'warning');
      return;
    }

    // ... остальная логика
  }, [gameId, isYourTurn]);

  return {
    endTurn,
    playCard,
    isYourTurn,
  };
};
```

---

### EC-4.2: Reconnection During Action

**Сценарий:** Пользователь совершает действие, происходит disconnect, затем reconnect

```typescript
// ✅ РЕШЕНИЕ с pending actions recovery
interface PendingAction {
  id: string;
  type: string;
  variables: unknown;
  timestamp: number;
  retryCount: number;
}

const usePendingActions = () => {
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);

  const addPendingAction = useCallback((action: PendingAction) => {
    setPendingActions(prev => [...prev, action]);

    // Сохраняем в localStorage для восстановления
    localStorage.setItem(
      `pending_actions_${gameId}`,
      JSON.stringify([...pendingActions, action])
    );
  }, [gameId, pendingActions]);

  const recoverPendingActions = useCallback(async (gameId: string) => {
    const stored = localStorage.getItem(`pending_actions_${gameId}`);

    if (!stored) return;

    const actions: PendingAction[] = JSON.parse(stored);
    const now = Date.now();
    const staleThreshold = 30000; // 30 секунд

    for (const action of actions) {
      // Пропускаем устаревшие действия
      if (now - action.timestamp > staleThreshold) {
        continue;
      }

      try {
        // Проверяем статус действия на сервере
        const { data } = await apolloClient.query({
          query: ACTION_STATUS_QUERY,
          variables: { actionId: action.id },
        });

        if (data.actionStatus.status === 'PENDING') {
          // Повторяем запрос
          await retryAction(action);
        } else if (data.actionStatus.status === 'NOT_FOUND') {
          // Действие не дошло, повторяем
          if (action.retryCount < 3) {
            await retryAction({ ...action, retryCount: action.retryCount + 1 });
          }
        }
        // Если CONFIRMED или REJECTED - не делаем ничего
      } catch (error) {
        console.error('Failed to recover action:', action.id, error);
      }
    }

    // Очищаем после восстановления
    localStorage.removeItem(`pending_actions_${gameId}`);
    setPendingActions([]);
  }, []);

  const clearPendingActions = useCallback(() => {
    setPendingActions([]);
    localStorage.removeItem(`pending_actions_${gameId}`);
  }, [gameId]);

  return {
    pendingActions,
    addPendingAction,
    recoverPendingActions,
    clearPendingActions,
  };
};

// Интеграция с useGameSync
const useGameSync = (gameId: string | null) => {
  const { recoverPendingActions, clearPendingActions } = usePendingActions();

  useEffect(() => {
    if (connectionStatus === 'connected' && wasDisconnected) {
      // Только что переподключились
      recoverPendingActions(gameId);
    } else if (connectionStatus === 'disconnected') {
      // Только что отключились - сохраняем pending actions
      // (уже делается в addPendingAction)
    }
  }, [connectionStatus, gameId, recoverPendingActions]);
};
```

---

### EC-4.3: State Desynchronization

**Сценарий:** Локальное состояние рассинхронизировалось с серверным

```typescript
// ✅ РЕШЕНИЕ с periodic full sync
const useGameStateSync = (gameId: string) => {
  const { serverGameState, lastSequenceNumber } = useRemoteGameStore();
  const [needsFullSync, setNeedsFullSync] = useState(false);

  // Периодическая проверка целостности состояния
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        // Запрашиваем текущий sequence number
        const { data } = await apolloClient.query({
          query: GAME_STATE_META_QUERY,
          variables: { gameId },
          fetchPolicy: 'network-only',
        });

        // Если расхождение больше 10 - делаем полный sync
        if (Math.abs(data.gameState.sequenceNumber - lastSequenceNumber) > 10) {
          console.warn('[GameStateSync] Sequence gap detected, forcing full sync');
          setNeedsFullSync(true);
        }
      } catch (error) {
        console.error('[GameStateSync] Failed to check sequence:', error);
      }
    }, 10000); // Каждые 10 секунд

    return () => clearInterval(interval);
  }, [gameId, lastSequenceNumber]);

  // Полная синхронизация при необходимости
  useEffect(() => {
    if (!needsFullSync) return;

    const doFullSync = async () => {
      const { fetchGameState } = useRemoteGameStore.getState();

      try {
        await fetchGameState(gameId);
        setNeedsFullSync(false);
        showNotification('Игровое состояние обновлено', 'info');
      } catch (error) {
        console.error('[GameStateSync] Full sync failed:', error);
        // Пробуем снова через 5 секунд
        setTimeout(() => setNeedsFullSync(true), 5000);
      }
    };

    doFullSync();
  }, [needsFullSync, gameId]);

  return { needsFullSync, forceSync: () => setNeedsFullSync(true) };
};
```

---

## Фаза 5: Combat UI

### EC-5.1: Combat Timeout Behavior

**Сценарий:** Таймер защиты истёк, поведение не определено

```typescript
// ✅ РЕШЕНИЕ с явным timeout action
enum CombatTimeoutAction {
  AUTO_PASS = 'AUTO_PASS',
  AUTO_DEFEND_WEAK = 'AUTO_DEFEND_WEAK',
  FORFEIT = 'FORFEIT',
}

const useCombatTimer = (
  combat: CombatState,
  onTimeout: (action: CombatTimeoutAction) => void
) => {
  const [timeRemaining, setTimeRemaining] = useState(combat.timeRemaining || 30);
  const timeoutAction = combat.timeoutAction || CombatTimeoutAction.AUTO_PASS;

  useEffect(() => {
    if (timeRemaining <= 0) {
      // Выполняем действие при истечении времени
      onTimeout(timeoutAction);

      // Показываем уведомление
      switch (timeoutAction) {
        case CombatTimeoutAction.AUTO_PASS:
          showNotification('Время истекло. Автоматический пас.', 'warning');
          break;
        case CombatTimeoutAction.AUTO_DEFEND_WEAK:
          showNotification('Время истекло. Автозащита weakest card.', 'warning');
          break;
        case CombatTimeoutAction.FORFEIT:
          showNotification('Время истекло. Вы проиграли бой.', 'error');
          break;
      }

      return;
    }

    const interval = setInterval(() => {
      setTimeRemaining(prev => prev - 1);
    }, 1000);

    return () => clearInterval(interval);
  }, [timeRemaining, timeoutAction, onTimeout]);

  const getTimerColor = () => {
    if (timeRemaining <= 5) return 'red';
    if (timeRemaining <= 10) return 'orange';
    return 'green';
  };

  return {
    timeRemaining,
    timerColor: getTimerColor(),
    timeoutAction,
  };
};
```

---

### EC-5.2: Simultaneous Combat Initiation

**Сценарий:** Оба игрока инициируют атаку одновременно

```typescript
// ✅ РЕШЕНИЕ с server authority + optimistic rollback
const useCombatInitiation = (gameId: string) => {
  const [pendingAttacks, setPendingAttacks] = useState<Map<string, AttackInput>>(new Map());

  const initiateAttack = useCallback(async (input: AttackInput) => {
    const attackId = crypto.randomUUID();

    // Оптимистично показываем атаку
    setPendingAttacks(prev => new Map(prev).set(attackId, input));
    showAttackPreview(input);

    try {
      const { data } = await apolloClient.mutate({
        mutation: ATTACK_MUTATION,
        variables: { input },
      });

      if (data.attack.success) {
        // Успешная атака
        setPendingAttacks(prev => {
          const next = new Map(prev);
          next.delete(attackId);
          return next;
        });
      } else if (data.attack.conflict) {
        // Конфликт - другой игрок атаковал первым
        setPendingAttacks(prev => {
          const next = new Map(prev);
          next.delete(attackId);
          return next;
        });
        hideAttackPreview(input);
        showNotification(data.attack.conflict.reason, 'warning');
      }
    } catch (error) {
      // Ошибка - откатываем
      setPendingAttacks(prev => {
        const next = new Map(prev);
        next.delete(attackId);
        return next;
      });
      hideAttackPreview(input);
    }
  }, [gameId]);

  return { initiateAttack, pendingAttacks };
};
```

---

### EC-5.3: Damage Calculation Discrepancy

**Сценарий:** Рассчитанный урон отличается от серверного

```typescript
// ✅ РЕШЕНИЕ с server authority for damage
const useDamageCalculation = () => {
  const [localCalculation, setLocalCalculation] = useState<DamageResult | null>(null);
  const [serverResult, setServerResult] = useState<DamageResult | null>(null);

  const calculateDamage = useCallback((
    attackValue: number,
    defenseValue: number,
    modifiers: ValueModifier[]
  ) => {
    // Локальный расчёт для preview
    let damage = Math.max(0, attackValue - defenseValue);

    for (const mod of modifiers) {
      switch (mod.type) {
        case 'DOUBLE_DAMAGE':
          damage *= 2;
          break;
        case 'IGNORE_DEFENSE':
          damage = attackValue;
          break;
        // ...
      }
    }

    setLocalCalculation({ attackValue, defenseValue, damage, modifiers });
  }, []);

  // Когда приходит результат с сервера - всегда используем его
  useEffect(() => {
    if (serverResult && localCalculation) {
      if (serverResult.damage !== localCalculation.damage) {
        console.warn('[DamageCalculation] Discrepancy detected:', {
          local: localCalculation.damage,
          server: serverResult.damage,
        });
        // Показываем server result, игнорируем local
      }
    }
  }, [serverResult, localCalculation]);

  return {
    calculateDamage,
    displayedDamage: serverResult?.damage ?? localCalculation?.damage ?? 0,
    setServerResult,
  };
};
```

---

## Фаза 6: Social Features

### EC-6.1: Chat Message Ordering

**Сценарий:** Сообщения приходят не по порядку

```typescript
// ✅ РЕШЕНИЕ с sequence-based ordering
const useChatMessages = (gameId: string) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingMessages, setPendingMessages] = useState<Map<string, ChatMessage>>(new Map());

  const addMessage = useCallback((newMessage: ChatMessage) => {
    setMessages((prev) => {
      // Удаляем optimistic версию если есть
      const withoutOptimistic = prev.filter(
        m => m.clientId !== newMessage.clientId
      );

      // Проверяем на дубликаты по server ID
      if (withoutOptimistic.some(m => m.id === newMessage.id)) {
        return withoutOptimistic;
      }

      // Добавляем и сортируем по sequence number
      const withNew = [...withoutOptimistic, newMessage];
      return withNew.sort((a, b) => {
        if (a.sequenceNumber !== undefined && b.sequenceNumber !== undefined) {
          return a.sequenceNumber - b.sequenceNumber;
        }
        return a.timestamp - b.timestamp;
      });
    });
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    const clientId = crypto.randomUUID();
    const optimisticMessage: ChatMessage = {
      id: `pending-${clientId}`,
      clientId,
      content,
      userId: currentUserId,
      timestamp: Date.now(),
      status: 'pending',
    };

    // Оптимистично добавляем
    setPendingMessages(prev => new Map(prev).set(clientId, optimisticMessage));
    addMessage(optimisticMessage);

    try {
      const { data } = await apolloClient.mutate({
        mutation: SEND_MESSAGE_MUTATION,
        variables: { gameId, content, clientId },
      });

      // Заменяем optimistic на server version
      addMessage(data.sendChatMessage);
      setPendingMessages(prev => {
        const next = new Map(prev);
        next.delete(clientId);
        return next;
      });
    } catch (error) {
      // Отмечаем как failed
      setMessages(prev => prev.map(m =>
        m.clientId === clientId ? { ...m, status: 'failed' } : m
      ));
    }
  }, [gameId, currentUserId, addMessage]);

  return { messages, pendingMessages, sendMessage };
};
```

---

### EC-6.2: Emote Spam

**Сценарий:** Пользователь спамит эмotes

```typescript
// ✅ РЕШЕНИЕ с rate limiting
const useEmoteSender = (gameId: string) => {
  const [recentEmotes, setRecentEmotes] = useState<number[]>([]);

  const canSendEmote = useCallback(() => {
    const now = Date.now();
    const oneMinuteAgo = now - 60000;

    // Удаляем старые записи
    const recent = recentEmotes.filter(t => t > oneMinuteAgo);

    // Лимит: 10 emotов в минуту
    if (recent.length >= 10) {
      showNotification('Слишком много эмодзи. Подождите немного.', 'warning');
      return false;
    }

    return true;
  }, [recentEmotes]);

  const sendEmote = useCallback(async (emoteId: string) => {
    if (!canSendEmote()) return;

    const now = Date.now();
    setRecentEmotes(prev => [...prev, now]);

    try {
      await apolloClient.mutate({
        mutation: SEND_EMOTE_MUTATION,
        variables: { gameId, emoteId },
      });
    } catch (error) {
      // Сервер тоже должен валидировать
      if (error.message.includes('Rate limit exceeded')) {
        showNotification('Слишком быстро! Подождите.', 'warning');
      }
    }
  }, [gameId, canSendEmote]);

  return { sendEmote };
};
```

---

## Фаза 7: Profile & Leaderboard

### EC-7.1: Leaderboard Infinite Scroll Memory

**Сценарий:** Пользователь листает вниз, память растёт

```typescript
// ✅ РЕШЕНИЕ с windowing + pagination
const useLeaderboard = (options: LeaderboardOptions) => {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  // Храним только загруженные диапазоны
  const [loadedRanges, setLoadedRanges] = useState<Array<{start: number, end: number}>>([]);

  const loadRange = useCallback(async (start: number, end: number) => {
    // Проверяем, уже ли загружен этот диапазон
    const isLoaded = loadedRanges.some(r =>
      start >= r.start && end <= r.end
    );

    if (isLoaded) return;

    setIsLoading(true);

    try {
      const { data } = await apolloClient.query({
        query: LEADERBOARD_QUERY,
        variables: {
          ...options,
          offset: start,
          limit: end - start,
        },
      });

      // Заменяем диапазон в массиве
      setEntries(prev => {
        const newEntries = [...prev];
        for (let i = 0; i < data.leaderboard.players.length; i++) {
          newEntries[start + i] = data.leaderboard.players[i];
        }
        return newEntries;
      });

      setLoadedRanges(prev => [...prev, { start, end }]);
      setTotalCount(data.leaderboard.totalCount);
    } finally {
      setIsLoading(false);
    }
  }, [options, loadedRanges]);

  return {
    entries,
    totalCount,
    isLoading,
    loadRange,
  };
};

// С react-virtuoso
const LeaderboardTable = () => {
  const { entries, totalCount, loadRange, isLoading } = useLeaderboard(options);

  return (
    <Virtuoso
      style={{ height: 600 }}
      totalCount={totalCount}
      endReached={() => {
        const nextRange = {
          start: entries.length,
          end: Math.min(entries.length + 50, totalCount),
        };
        loadRange(nextRange.start, nextRange.end);
      }}
      itemContent={(index) => {
        const entry = entries[index];
        if (!entry) return <SkeletonRow />;
        return <PlayerRow entry={entry} />;
      }}
      components={{
        Footer: () => isLoading ? <LoadingMore /> : null,
      }}
    />
  );
};
```

---

## Кросс-фазные сценарии

### EC-CROSS-1: Session Expiry

**Сценарий:** JWT токен истекает во время игры

```typescript
// ✅ РЕШЕНИЕ с token refresh
const useAuthRefresh = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Перехватываем GraphQL ошибки
    const errorLink = onError(({ graphQLErrors, networkError, operation, forward }) => {
      if (graphQLErrors) {
        for (const error of graphQLErrors) {
          // JWT expired
          if (error.extensions?.code === 'AUTHENTICATION_ERROR') {
            // Пытаемся обновить токен
            return refreshToken().then(() => {
              // Повторяем исходный запрос с новым токеном
              return forward(operation);
            }).catch(() => {
              // Refresh failed - redirect to login
              const currentPath = window.location.pathname;
              sessionStorage.setItem('redirectAfterLogin', currentPath);
              navigate('/login');
            });
          }
        }
      }

      // Network error - возможно token expired
      if (networkError && networkError.statusCode === 401) {
        return refreshToken().then(() => forward(operation));
      }
    });

    return () => {
      // Cleanup при размонтировании
    };
  }, [navigate]);
};

// Добавляем предупреждение перед истечением
const useTokenExpiryWarning = () => {
  useEffect(() => {
    const token = parseJWT(getToken());
    if (!token) return;

    const expiresAt = token.exp * 1000;
    const now = Date.now();
    const timeUntilExpiry = expiresAt - now;

    // Предупреждаем за 5 минут до истечения
    const warningTime = 5 * 60 * 1000;

    if (timeUntilExpiry < warningTime && timeUntilExpiry > 0) {
      const timeout = setTimeout(() => {
        showNotification(
          'Сессия истекает скоро. Ваша игра будет сохранена.',
          'warning'
        );
      }, timeUntilExpiry - warningTime);

      return () => clearTimeout(timeout);
    }
  }, []);
};
```

---

### EC-CROSS-2: Browser Tab Visibility

**Сценарий:** Пользователь переключается на другую вкладку

```typescript
// ✅ РЕШЕНИЕ с visibility API
const useTabVisibility = (gameId: string) => {
  const [isVisible, setIsVisible] = useState(!document.hidden);
  const missedEventsRef = useRef<GameEvent[]>([]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      const nowVisible = !document.hidden;

      if (isVisible && !nowVisible) {
        // Вкладка скрылась - начинаем накапливать события
        console.log('[TabVisibility] Tab hidden, accumulating events');
      } else if (!isVisible && nowVisible) {
        // Вкладка стала видимой - применяем накопленные события
        console.log('[TabVisibility] Tab visible, applying missed events');
        applyMissedEvents(missedEventsRef.current);
        missedEventsRef.current = [];

        // Показываем уведомление о пропущенных событиях
        if (missedEventsRef.current.length > 0) {
          showNotification(
            `Произошло ${missedEventsRef.current.length} событий пока вас не было.`,
            'info'
          );
        }
      }

      setIsVisible(nowVisible);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isVisible, gameId]);

  // Подписка на события при активной вкладке
  useEffect(() => {
    if (!isVisible) return;

    const subscription = apolloClient
      .subscribe({ query: GAME_UPDATES_SUB, variables: { gameId } })
      .subscribe({
        next: (data) => {
          if (isVisible) {
            // Применяем сразу если вкладка активна
            applyGameEvent(data.gameUpdates);
          } else {
            // Накапливаем если вкладка скрыта
            missedEventsRef.current.push(data.gameUpdates);
          }
        },
      });

    return () => subscription.unsubscribe();
  }, [gameId, isVisible]);

  return { isVisible };
};
```

---

### EC-CROSS-3: Mobile Safari Back Button Cache

**Сценарий:** Пользователь нажимает "назад" на iOS, страница загружается из cache

```typescript
// ✅ РЕШЕНИЕ с page reload
const useBackButtonCacheFix = () => {
  useEffect(() => {
    // Для iOS Safari
    const onPageshow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        // Страница загружена из cache
        console.log('[BackButton] Page loaded from cache, reloading...');

        // Перезагружаем страницу для восстановления состояния
        window.location.reload();
      }
    };

    window.addEventListener('pageshow', onPageshow);

    return () => {
      window.removeEventListener('pageshow', onPageshow);
    };
  }, []);
};

// Или сохраняем состояние в sessionStorage
const useGameStatePersistence = (gameId: string) => {
  const STORAGE_KEY = `game_state_${gameId}`;

  // Сохраняем состояние периодически
  useEffect(() => {
    const interval = setInterval(() => {
      const state = useGameStore.getState();
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }, 5000);

    return () => clearInterval(interval);
  }, [STORAGE_KEY]);

  // Восстанавливаем при монтировании
  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);

    if (stored) {
      try {
        const state = JSON.parse(stored);
        // Проверяем валидность состояния
        if (state.gameState && state.gameState.id === gameId) {
          useGameStore.setState(state);
        }
      } catch (error) {
        console.error('[GameStatePersistence] Failed to restore:', error);
        sessionStorage.removeItem(STORAGE_KEY);
      }
    }

    return () => {
      // Очищаем при выходе из игры
      sessionStorage.removeItem(STORAGE_KEY);
    };
  }, [gameId, STORAGE_KEY]);
};
```

---

## Чек-лист для реализации

Перед началом реализации каждой фазы убедитесь, что:

- [ ] Все мутации имеют idempotency key
- [ ] Все подписки корректно отписываются при размонтировании
- [ ] Оптимистичные обновления могут быть откачены
- [ ] Таймауты имеют чёткое поведение
- [ ] Ошибки сети обрабатываются с retry
- [ ] WebSocket disconnect/reconnect покрыт
- [ ] Состояние валидируется на сервере
- [ ] UI показывает статус загрузки/ошибки
- [ ] Accessibility атрибуты добавлены
- [ ] Сообщения упорядочены по sequence number

---

**Конец документа**
