# ФАЗА 3: Room Setup UI

## Задача 3.1 - RoomView

Комната ожидания перед началом игры.

### Компоненты для создания:
```
src/components/room/
├── RoomView.tsx            # Главный компонент
├── PlayerSlots.tsx         # Слоты игроков
├── ReadyStatus.tsx         # Статус готовности
├── RoomChat.tsx            # Чат комнаты
└── InviteLink.tsx          # Пригласительная ссылка
```

---

### RoomView.tsx

**Функциональность:**
- Отображение информации о комнате
- Список подключённых игроков
- Статус готовности каждого
- Чат комнаты
- Кнопка "Начать игру" (только для хоста)
- Возможность покинуть комнату
- Отображение кода комнаты / invite link

**GraphQL операции:**
```graphql
query RoomInfo($gameId: ID!) {
  game(id: $gameId) {
    id
    code
    status
    mode
    host { id username }
    players {
      user { id username avatar }
      hero { id name thumbnailUrl }
      isReady
    }
    board { name imageUrl }
  }
}

subscription RoomUpdates($gameId: ID!) {
  gameUpdates(gameId: $gameId) {
    gameState {
      players {
        user { id }
        isReady
      }
    }
  }
}

mutation SetReady($gameId: ID!, $ready: Boolean!) {
  setReady(gameId: $gameId, ready: $ready) {
    id
    players { ... }
  }
}

mutation LeaveRoom($gameId: ID!) {
  leaveGame(gameId: $gameId)
}

mutation StartGame($gameId: ID!) {
  startGame(gameId: $gameId) {
    id
    status
  }
}
```

**Состояние (Zustand):**
```typescript
interface RoomStore {
  game: Game | null;
  isHost: boolean;
  allReady: boolean;
  loading: boolean;
  setReady: (ready: boolean) => Promise<void>;
  leaveRoom: () => Promise<void>;
  startGame: () => Promise<void>;
}
```

---

### PlayerSlots.tsx

**Функциональность:**
- Отображение слотов игроков (2 для 1v1, 4 для 2v2)
- Каждое слот показывает:
  - Аватар игрока
  - Имя пользователя
  - Выбранного героя
  - Статус готовности (✓ или иконка)
- Пустые слоты показывают "Ожидание игрока..."
- Подсветка текущего пользователя

**Пропсы:**
```typescript
interface PlayerSlotsProps {
  players: GamePlayer[];
  mode: GameMode;
  currentUserId: string;
}
```

---

### ReadyStatus.tsx

**Функциональность:**
- Кнопка переключения статуса готовности
- Текст "Я готов" / "Не готов"
- Индикатор всех готовы
- Анимация при изменении статуса

**Пропсы:**
```typescript
interface ReadyStatusProps {
  isReady: boolean;
  onToggle: () => void;
  disabled?: boolean;
}
```

---

### RoomChat.tsx

**Функциональность:**
- Сообщения игроков в комнате
- Системные сообщения (X присоединился, Y готов)
- Поле ввода сообщений
- Автопрокрутка вниз

**Пропсы:**
```typescript
interface RoomChatProps {
  gameId: string;
  messages: ChatMessage[];
}
```

---

### InviteLink.tsx

**Функциональность:**
- Отображение кода комнаты
- Кнопка "Копировать ссылку"
- Кнопка "Поделиться"
- QR-код (опционально)

---

## Задача 3.2 - FighterPlacement

Размещение бойцов на доске перед началом игры.

### Компоненты для создания:
```
src/components/room/
└── FighterPlacement.tsx    # Размещение бойцов
```

---

### FighterPlacement.tsx

**Функциональность:**
- Отображение доски с валидными зонами размещения
- Drag & drop бойцов на доску
- Подсветка доступных стартовых зон (по цвету игрока)
- Предпросмотр размещения
- Кнопка "Подтвердить размещение"
- Отображение размещений соперника (скрыто до подтверждения)

**GraphQL операции:**
```graphql
query ValidSpawnZones($gameId: ID!, $playerId: ID!) {
  validSpawnZones(gameId: $gameId, playerId: $playerId) {
    position { x y }
    zone
  }
}

mutation PlaceFighter($gameId: ID!, $input: PlaceFighterInput!) {
  placeFighter(gameId: $gameId, input: $input) {
    id
    state { ... }
  }
}

mutation ConfirmPlacement($gameId: ID!) {
  confirmPlacement(gameId: $gameId) {
    id
    state { ... }
  }
}
```

**Интерфейс:**
```typescript
interface PlaceFighterInput {
  fighterId: string;
  position: { x: number; y: number };
}

interface Fighter {
  id: string;
  type: 'hero' | 'sidekick';
  heroId: string;
  health: number;
  maxHealth: number;
}
```

**Паттерн размещения:**
1. Игрок видит своих бойцов слева
2. Игрок видит доступные зоны на доске (подсвечены)
3. Drag & drop бойца на зону
4. При клике на зону — показываем превью
5. Кнопка "Подтвердить" когда все бойцы размещены

---

## Задача 3.3 - Game Countdown

Обратный отсчёт перед началом игры.

### Компонент:
```
src/components/room/
└── GameCountdown.tsx       # Обратный отсчёт
```

**Функциональность:**
- Большое число отсчёта (3, 2, 1...)
- Анимация для каждого числа
- Текст "Игра начинается!"
- Использует существующий Countdown из game-controls

---

## Задача 3.4 - Роутинг

### Переходы между экранами:
```
LobbyView → MatchmakingView
     ↓            ↓
RoomView ← ─ ─ ─ ─ ─
     ↓
FighterPlacement
     ↓
GameCountdown
     ↓
GameView
```

---

## Результат ФАЗЫ 3

- ✅ Пользователь видит комнату ожидания
- ✅ Пользователь видит всех подключённых игроков
- ✅ Пользователь может менять статус готовности
- ✅ Хост может начинать игру когда все готовы
- ✅ Пользователь может размещать бойцов на доске
- ✅ Пользователь может приглашать друзей по ссылке
- ✅ Плавный переход к игровому экрану

---

## Следующие шаги

→ [ФАЗА 4: Game View](./04-game-view.md)
