# Frontend Задачи: Unmatched Карточная Игра

## Обзор

Документ содержит задачи по реализации Frontend компонентов для карточной игры Unmatched.

**Текущий статус:**
- ✅ Backend полностью реализован (Auth, Games, Matchmaking, Presence, Leaderboard)
- ✅ Базовые компоненты (Card, BoardView, HandView, GameControls)
- ✅ Auth компоненты (LoginForm, RegisterForm, AuthGuard)
- ✅ Фаза 1: Lobby + Matchmaking — **полностью реализовано с edge cases**
- ⏳ Фаза 2-7: Hero Selection, Room Setup, GameView, Combat UI, Social, Profile — нужно реализовать

---

## Структура задач

| # | Файл | Описание | Статус | Приоритет |
|---|------|----------|--------|-----------|
| 1 | [01-lobby-matchmaking.md](./01-lobby-matchmaking.md) | Главный экран лобби и поиск игры | ✅ **100%** | 🔴 Критический |
| 2 | [02-hero-selection.md](./02-hero-selection.md) | Выбор героя перед игрой | ❌ Не начато | 🔴 Критический |
| 3 | [03-room-setup.md](./03-room-setup.md) | Комната ожидания и размещение бойцов | ❌ Не начато | 🟡 Важный |
| 4 | [04-game-view.md](./04-game-view.md) | Главный игровой экран | ⚠️ Частично | 🔴 Критический |
| 5 | [05-combat-ui.md](./05-combat-ui.md) | Боевой UI (атака, защита) | ❌ Не начато | 🔴 Критический |
| 6 | [06-social.md](./06-social.md) | Чат и эмодзи | ❌ Не начато | 🟢 Желательный |
| 7 | [07-profile-leaderboard.md](./07-profile-leaderboard.md) | Профиль и таблица лидеров | ❌ Не начато | 🟡 Важный |
| 8 | [ARCHITECTURE_REVIEW.md](./ARCHITECTURE_REVIEW.md) | Архитектурное ревью и edge cases | ✅ Готово | 🔴 Критический |
| 9 | [08-edge-cases.md](./08-edge-cases.md) | Детальное описание edge cases | ✅ Готово | 🔴 Критический |

---

## Порядок реализации

### Этап 1: MVP (минимально играбельная версия)
1. **LobbyView** — вход в приложение
2. **MatchmakingView** — поиск игры
3. **HeroSelection** — выбор героя
4. **GameView** — основной игровой экран
5. **CombatPanel** — боевой UI

### Этап 2: UX улучшения
6. **RoomView** — комната ожидания
7. **FighterPlacement** — размещение бойцов
8. **GameOverModal** — результаты игры
9. **TurnIndicator** — индикатор хода

### Этап 3: Социальные функции
10. **GameChat** — общение в игре
11. **LeaderboardView** — рейтинги
12. **ProfileView** — профили

---

## Технический стек

- **React 18** + TypeScript
- **Vite** + React Router v7
- **Zustand** — state management
- **Apollo Client** — GraphQL (queries, mutations, subscriptions)
- **CSS Custom Properties** — дизайн-система

---

## Полезные референсы

### Существующие компоненты (изучить паттерны)
| Файл | Для чего |
|------|----------|
| [src/components/cards/Card.tsx](../../src/components/cards/Card.tsx) | Паттерн компонента карты |
| [src/components/board/BoardView.tsx](../../src/components/board/BoardView.tsx) | Визуализация доски |
| [src/store/remoteGameStore.ts](../../src/store/remoteGameStore.ts) | Синхронизация с сервером |
| [src/hooks/useGameSync.ts](../../src/hooks/useGameSync.ts) | WebSocket подписки |

### Backend GraphQL резолверы (интеграция)
| Файл | Операции |
|------|----------|
| `backend/src/matchmaking/matchmaking.resolver.ts` | joinQueue, leaveQueue |
| `backend/src/games/game.resolver.ts` | game CRUD, state |
| `backend/src/users/users.resolver.ts` | profile, leaderboard |

---

## Детальный статус реализации

### ✅ Фаза 1: Lobby & Matchmaking (100% готово)

| Компонент | Файл | Статус | Заметки |
|-----------|------|--------|---------|
| LobbyView | [src/components/lobby/LobbyView.tsx](../../src/components/lobby/LobbyView.tsx) | ✅ | Фильтры, список игр, навигация |
| GameList | [src/components/lobby/GameList.tsx](../../src/components/lobby/GameList.tsx) | ✅ | Polling каждые 30с, пустое состояние |
| GameCard | [src/components/lobby/GameCard.tsx](../../src/components/lobby/GameCard.tsx) | ✅ | Аватары, статусы, индикатор героя |
| CreateGameDialog | [src/components/lobby/CreateGameDialog.tsx](../../src/components/lobby/CreateGameDialog.tsx) | ✅ | Выбор режима и доски |
| MatchmakingView | [src/components/matchmaking/MatchmakingView.tsx](../../src/components/matchmaking/MatchmakingView.tsx) | ✅ | Кнопки join/leave, подписка на матч |
| QueueStatus | [src/components/matchmaking/QueueStatus.tsx](../../src/components/matchmaking/QueueStatus.tsx) | ✅ | Круговой прогресс, таймер, статистика |
| MatchFound | [src/components/matchmaking/MatchFound.tsx](../../src/components/matchmaking/MatchFound.tsx) | ✅ | Авто-accept через 5с, VS экран |

**Stores (с edge cases protection):**
- [lobbyStore.ts](../../src/store/lobbyStore.ts) — ✅ AbortController, idempotency, mount/unmount
- [matchmakingStore.ts](../../src/store/matchmakingStore.ts) — ✅ AbortController, idempotency, mount/unmount, subscription cleanup

**✅ Реализованные Edge Cases:**
- ✅ [EC-1.1](./08-edge-cases.md#ec-11-rapid-queue-joinleave) — AbortController для rapid join/leave
- ✅ [EC-1.2](./08-edge-cases.md#ec-12-match-found-during-unmount) — isMountedRef в MatchFound
- ✅ [EC-1.3](./08-edge-cases.md#ec-13-create-game-during-network-issues) — Idempotency keys для всех мутаций
- ✅ Subscription cleanup при unmount
- ✅ Mount/unmount паттерн для state isolation

---

### ❌ Фаза 2: Hero Selection (0% готово)

| Компонент | Файл | Статус |
|-----------|------|--------|
| HeroSelection | — | ❌ Не создан |
| HeroGrid | — | ❌ Не создан |
| HeroCard | — | ❌ Не создан |
| HeroDetailsPanel | — | ❌ Не создан |
| HeroPicker | — | ❌ Не создан |

---

### ❌ Фаза 3: Room Setup (0% готово)

| Компонент | Файл | Статус |
|-----------|------|--------|
| RoomView | — | ❌ Не создан |
| PlayerSlots | — | ❌ Не создан |
| ReadyStatus | — | ❌ Не создан |
| RoomChat | — | ❌ Не создан |
| InviteLink | — | ❌ Не создан |
| FighterPlacement | — | ❌ Не создан |
| GameCountdown | — | ❌ Не создан |

---

### ⚠️ Фаза 4: Game View (30% готово)

| Компонент | Файл | Статус | Заметки |
|-----------|------|--------|---------|
| BoardView | [src/components/board/BoardView.tsx](../../src/components/board/BoardView.tsx) | ✅ | Grid, zones, fighters (локальный) |
| HandView | [src/components/cards/HandView.tsx](../../src/components/cards/HandView.tsx) | ✅ | Карточки, health bars (локальный) |
| GameControls | [src/components/controls/GameControls.tsx](../../src/components/controls/GameControls.tsx) | ✅ | (локальный) |
| GameView | — | ❌ Не создан (обёртка) |
| GameHeader | — | ❌ Не создан |
| TurnIndicator | — | ❌ Не создан |
| ActionButtons | — | ❌ Не создан |
| OpponentHandView | — | ❌ Не создан |
| DiscardPileView | — | ❌ Не создан |
| GameErrorBoundary | — | ❌ Не создан |

**Hooks:**
- [useGameSync.ts](../../src/hooks/useGameSync.ts) — ✅ WebSocket с reconnect
- [useOptimisticUpdate.ts](../../src/hooks/useOptimisticUpdate.ts) — ✅ Оптимистичные обновления
- [remoteGameStore.ts](../../src/store/remoteGameStore.ts) — ✅ Синхронизация состояния

---

### ❌ Фаза 5: Combat UI (0% готово)

| Компонент | Файл | Статус |
|-----------|------|--------|
| CombatPanel | — | ❌ Не создан |
| AttackerView | — | ❌ Не создан |
| DefenderView | — | ❌ Не создан |
| AttackCardDisplay | — | ❌ Не создан |
| DefenseCardDisplay | — | ❌ Не создан |
| DamageIndicator | — | ❌ Не создан |
| CombatTimer | — | ❌ Не создан |
| DefenseCardSelector | — | ❌ Не создан |
| TargetSelector | — | ❌ Не создан |

---

### ❌ Фаза 6: Social Features (0% готово)

| Компонент | Файл | Статус |
|-----------|------|--------|
| GameChat | — | ❌ Не создан |
| ChatMessage | — | ❌ Не создан |
| ChatInput | — | ❌ Не создан |
| EmotePicker | — | ❌ Не создан |
| EmoteReaction | — | ❌ Не создан |

---

### ❌ Фаза 7: Profile & Leaderboard (0% готово)

| Компонент | Файл | Статус |
|-----------|------|--------|
| LeaderboardView | — | ❌ Не создан |
| LeaderboardTable | — | ❌ Не создан |
| LeaderboardTabs | — | ❌ Не создан |
| PlayerRow | — | ❌ Не создан |
| ProfileView | — | ❌ Не создан |
| ProfileHeader | — | ❌ Не создан |
| ProfileStats | — | ❌ Не создан |
| MatchHistory | — | ❌ Не создан |
| RatingChart | — | ❌ Не создан |
| EditProfileModal | — | ❌ Не создан |

---

## Роутинг

| Маршрут | Компонент | Статус |
|---------|-----------|--------|
| `/` | → `/lobby` | ✅ |
| `/lobby` | LobbyView | ✅ |
| `/lobby/matchmaking` | MatchmakingView | ✅ |
| `/room/:id` | RoomView | ❌ (не создан) |
| `/game/:id` | GameView | ❌ (не создан) |
| `/profile/:id` | ProfileView | ❌ (не создан) |
| `/leaderboard` | LeaderboardView | ❌ (не создан) |

**Файлы:**
- [routes/index.tsx](../../src/routes/index.tsx) — ✅ базовая структура
- [routes/lobby.routes.tsx](../../src/routes/lobby.routes.tsx) — ✅ lobby роуты
- [routes/protected.route.tsx](../../src/routes/protected.route.tsx) — ✅ auth guard
