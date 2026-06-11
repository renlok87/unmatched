# ФАЗА 1: Lobby & Matchmaking UI

## Задача 1.1 - LobbyView

Главный экран приложения с списком игр и кнопками действий.

### Компоненты для создания:
```
src/components/lobby/
├── LobbyView.tsx           # Главный компонент
├── GameList.tsx            # Список доступных игр
├── GameCard.tsx            # Карточка игры в списке
└── CreateGameDialog.tsx    # Диалог создания игры
```

### LobbyView.tsx

**Функциональность:**
- Загрузка списка доступных игр при монтировании
- Отображение GameList
- Кнопка "Создать игру" → открывает CreateGameDialog
- Кнопка "Найти игру" → переход к MatchmakingView
- Отображение статуса пользователя (онлайн/в очереди)
- Автообновление списка игр (polling или subscription)

**GraphQL операции:**
```graphql
query AvailableGames($status: GameStatus) {
  availableGames(status: $status) {
    id
    status
    mode
    host { id username }
    opponent { id username }
    createdAt
    board { name }
  }
}

subscription GameListUpdates {
  gameCreated {
    ...GameFragment
  }
  gameUpdated {
    ...GameFragment
  }
}
```

**Состояние (Zustand):**
```typescript
interface LobbyStore {
  games: Game[]
  loading: boolean
  error: string | null
  isSearching: boolean
  fetchGames: () => Promise<void>
  createGame: (input: CreateGameInput) => Promise<Game>
}
```

---

### GameList.tsx

**Функциональность:**
- Список карточек игр
- Фильтрация по статусу (доступные/в процессе)
- Пустое состояние (нет доступных игр)
- Клик на карточку → открытие деталей или присоединение

---

### GameCard.tsx

**Функциональность:**
- Отображение информации об игре:
  - Название хоста
  - Режим игры (1v1, 2v2)
  - Статус (LOBBY, IN_PROGRESS)
  - Название доски
  - Время создания
- Кнопка "Присоединиться" (если LOBBY)
- Индикатор заполненности слотов

**Пропсы:**
```typescript
interface GameCardProps {
  game: Game;
  onJoin: (gameId: string) => void;
}
```

---

### CreateGameDialog.tsx

**Функциональность:**
- Выбор режима игры (1v1, 2v2, Free-for-All)
- Выбор доски из доступных
- Настройка приватности (публичная/приватная)
- Генерация invite-ссылки для приватной комнаты
- Предварительный выбор героя (опционально)

**GraphQL мутация:**
```graphql
mutation CreateGame($input: CreateGameInput!) {
  createGame(input: $input) {
    id
    code
    mode
    board { ... }
  }
}
```

**Пропсы:**
```typescript
interface CreateGameDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (game: Game) => void;
}
```

---

## Задача 1.2 - MatchmakingView

Экран поиска игры с визуальной обратной связью.

### Компоненты для создания:
```
src/components/matchmaking/
├── MatchmakingView.tsx     # Главный компонент
├── QueueStatus.tsx         # Статус очереди
└── MatchFound.tsx          # Игра найдена
```

---

### MatchmakingView.tsx

**Функциональность:**
- Спиннер загрузки
- Таймер ожидания
- Отображение количества игроков в очереди
- Анимация "поиск соперника"
- Кнопка "Отменить поиск"
- Автоматический переход при нахождении игры

**GraphQL операции:**
```graphql
mutation JoinQueue($input: JoinQueueInput!) {
  joinQueue(input: $input) {
    id
    mode
    status
    estimatedWaitTime
    playersInQueue
  }
}

mutation LeaveQueue {
  leaveQueue
}

subscription QueueStatus($userId: ID!) {
  queueStatus(userId: $userId) {
    status
    position
    estimatedWaitTime
    playersInQueue
  }
}

subscription MatchFound($userId: ID!) {
  matchFound(userId: $userId) {
    game {
      id
      mode
      players { ... }
    }
  }
}
```

**Состояние (Zustand):**
```typescript
interface MatchmakingStore {
  inQueue: boolean;
  status: 'searching' | 'found' | 'error';
  position: number | null;
  estimatedWaitTime: number | null;
  playersInQueue: number;
  joinedGame: Game | null;
  joinQueue: (mode: GameMode) => Promise<void>;
  leaveQueue: () => Promise<void>;
}
```

---

### QueueStatus.tsx

**Функциональность:**
- Визуализация статуса очереди
- Круговой прогресс-бар
- Текст статуса ("Поиск соперника...", "Осталось ~X минут")
- Количество игроков в очереди
- Ваша позиция в очереди

---

### MatchFound.tsx

**Функциональность:**
- Анимация "Игра найдена!"
- Отображение найденной игры
- Информация о соперниках
- Кнопка "Перейти к комнате"
- Автоматический переход через 5 секунд

---

## Задача 1.3 - Роутинг

Настройка маршрутов React Router.

### Файлы:
```
src/
├── routes/
│   ├── index.tsx            # Главный роутер
│   ├── lobby.routes.tsx     # Лобби роуты
│   └── protected.route.tsx  # HOC для защищённых роутов
```

### Маршруты:
```typescript
const routes = [
  { path: '/', component: LobbyView, protected: true },
  { path: '/login', component: LoginForm },
  { path: '/register', component: RegisterForm },
  { path: '/matchmaking', component: MatchmakingView, protected: true },
  { path: '/room/:id', component: RoomView, protected: true },
  { path: '/game/:id', component: GameView, protected: true },
];
```

---

## Результат ФАЗЫ 1

- ✅ Пользователь видит список доступных игр
- ✅ Пользователь может создать новую игру
- ✅ Пользователь может присоединиться к игре
- ✅ Пользователь может искать игру через matchmaking
- ✅ Визуальная обратная связь во время поиска
- ✅ Автоматический переход при нахождении игры

---

## Следующие шаги

→ [ФАЗА 2: Hero Selection](./02-hero-selection.md)
