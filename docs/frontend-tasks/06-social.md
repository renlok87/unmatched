# ФАЗА 6: Social Features

## Задача 6.1 - GameChat

Игровой чат для общения во время игры.

### Компоненты для создания:
```
src/components/chat/
├── GameChat.tsx            # Главный компонент чата
├── ChatMessage.tsx         # Сообщение чата
├── ChatInput.tsx           # Поле ввода
└── EmotePicker.tsx         # Эмоции
```

---

### GameChat.tsx

**Функциональность:**
- Отображение сообщений игроков
- Системные сообщения (x connected, y played card)
- Автопрокрутка вниз
- Пагинация истории (опционально)
- Сворачиваемая панель

**GraphQL операции:**
```graphql
query ChatMessages($gameId: ID!, $limit: Int) {
  chatMessages(gameId: $gameId, limit: $limit) {
    id
    type
    content
    user { id username avatar }
    timestamp
  }
}

mutation SendChatMessage($gameId: ID!, $content: String!) {
  sendChatMessage(gameId: $gameId, content: $content) {
    id
    ...ChatMessageFragment
  }
}

subscription ChatUpdates($gameId: ID!) {
  chatUpdates(gameId: $gameId) {
    ...ChatMessageFragment
  }
}
```

**Пропсы:**
```typescript
interface GameChatProps {
  gameId: string;
  collapsible?: boolean;
}
```

---

### ChatMessage.tsx

**Функциональность:**
- Отображение одного сообщения
- Разные стили для:
  - User messages (белый фон)
  - System messages (серый/жёлтый)
  - Emotes (центрированные)
- Аватар и имя отправителя
- Время отправки
- Hover эффекты

**Пропсы:**
```typescript
interface ChatMessageProps {
  message: ChatMessage;
  isOwn: boolean;
}
```

**Типы сообщений:**
```typescript
type ChatMessageType =
  | 'user'         // Обычное сообщение
  | 'system'       // Системное уведомление
  | 'emote'        // Эмоция/быстрая фраза
  | 'combat'       // Событие боя
  | 'game';        // Событие игры
```

---

### ChatInput.tsx

**Функциональность:**
- Поле ввода текста
- Кнопка отправки (Enter)
- Кнопка эмодзи/эмотов
- Автофокус при открытии чата
- Очистка после отправки

**Пропсы:**
```typescript
interface ChatInputProps {
  onSend: (message: string) => void;
  onEmoteClick: () => void;
  disabled?: boolean;
}
```

---

### EmotePicker.tsx

**Функциональность:**
- Предустановленные фразы ("Good game!", "Well played")
- Эмодзи реакции
- Категории (Greetings, Combat, Fun)
- Анимация появления на экране

**Предустановленные фразы:**
```typescript
const QUICK_PHRASES = {
  greetings: [
    { id: 'gg', text: 'Good game!' },
    { id: 'hf', text: 'Have fun!' },
    { id: 'gl', text: 'Good luck!' },
  ],
  combat: [
    { id: 'wp', text: 'Well played!' },
    { id: 'nic', text: 'Nice attack!' },
    { id: 'oops', text: 'My mistake!' },
  ],
  fun: [
    { id: 'lol', text: '😂' },
    { id: 'wow', text: '😮' },
    { id: 'think', text: '🤔' },
  ],
};
```

---

## Задача 6.2 - Emote Reactions

Быстрые эмоции на экране.

### Компонент:
```
src/components/chat/
└── EmoteReaction.tsx       # Реакция на экране
```

**Функциональность:**
- Плавающее изображение эмодзи
- Анимация появления и исчезновения
- Позиция рандомная или у игрока
- Несколько эмодзи одновременно

**Пропсы:**
```typescript
interface EmoteReactionProps {
  emote: string;
  playerId: string;
  onComplete: () => void;
}
```

**Анимация:**
```css
@keyframes float-up {
  0% {
    opacity: 0;
    transform: translateY(0) scale(0.5);
  }
  20% {
    opacity: 1;
    transform: translateY(-20px) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateY(-100px) scale(1);
  }
}

.emote-reaction {
  animation: float-up 2s ease-out forwards;
}
```

---

## Задача 6.3 - System Messages

Системные уведомления в чате.

### Типы системных сообщений:

| Тип | Описание | Пример |
|-----|----------|--------|
| `PLAYER_CONNECTED` | Игрок подключился | "X joined the game" |
| `PLAYER_DISCONNECTED` | Игрок отключился | "X disconnected" |
| `PLAYER_READY` | Игрок готов | "X is ready!" |
| `HERO_SELECTED` | Герой выбран | "X selected Daredevil" |
| `COMBAT_START` | Начало боя | "X attacks Y!" |
| `DAMAGE_DEALT` | Урон нанесён | "X dealt 5 damage to Y" |
| `FIGHTER_DEFEATED` | Боец повержен | "X's Daredevil was defeated!" |
| `TURN_START` | Начало хода | "X's turn" |
| `GAME_OVER` | Конец игры | "Game Over! X wins!" |

**Форматирование:**
```typescript
function formatSystemMessage(msg: SystemMessage): string {
  switch (msg.type) {
    case 'PLAYER_CONNECTED':
      return `${msg.playerName} joined the game`;
    case 'COMBAT_START':
      return `${msg.attackerName} attacks ${msg.defenderName}!`;
    // ...
  }
}
```

---

## Задача 6.4 - Chat Commands

Команды чата для быстрых действий.

### Поддерживаемые команды:

| Команда | Описание |
|---------|----------|
| `/gg` | Отправить "Good game!" |
| `/wp` | Отправить "Well played!" |
| `/concede` | Сдаться (закончить игру) |
| `/draw [card]` | Нарисовать карту (cheat, только для dev) |
| `/pause` | Попросить паузу |

**Реализация:**
```typescript
function parseChatCommand(input: string): ParsedCommand | null {
  if (input.startsWith('/')) {
    const [command, ...args] = input.slice(1).split(' ');
    return { command, args };
  }
  return null;
}

async function handleCommand(command: ParsedCommand) {
  switch (command.command) {
    case 'gg':
      sendQuickPhrase('gg');
      break;
    case 'concede':
      await concedeGame();
      break;
    // ...
  }
}
```

---

## Задача 6.5 - Chat Moderation (будущее)

Базовая модерация чата.

### Функции (опционально):
- Фильтр нецензурной лексики
- Лимит частоты сообщений (rate limit)
- Репорт сообщений
- Игнор игрока

---

## Результат ФАЗЫ 6

- ✅ Пользователь может отправлять сообщения
- ✅ Пользователь видит сообщения соперника
- ✅ Системные уведомления в чате
- ✅ Быстрые фразы и эмодзи
- ✅ Реакции на экране

---

## Следующие шаги

→ [ФАЗА 7: Profile & Leaderboard](./07-profile-leaderboard.md)
