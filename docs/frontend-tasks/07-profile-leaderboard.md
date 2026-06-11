# ФАЗА 7: Profile & Leaderboard UI

## Задача 7.1 - LeaderboardView

Таблица лидеров с рейтингами игроков.

### Компоненты для создания:
```
src/components/leaderboard/
├── LeaderboardView.tsx    # Главный компонент
├── LeaderboardTable.tsx   # Таблица рейтинга
├── LeaderboardTabs.tsx    # Табы (Global, Friends, Weekly)
└── PlayerRow.tsx          # Строка игрока
```

---

### LeaderboardView.tsx

**Функциональность:**
- Табы: Global, Friends, Weekly
- Таблица с позициями, игроками, рейтингом, win rate
- Пагинация
- Фильтр по режиму игры
- Поиск по имени
- Подсветка текущего пользователя

**GraphQL операции:**
```graphql
query Leaderboard($options: LeaderboardOptions!) {
  leaderboard(options: $options) {
    players {
      rank
      user { id username avatar }
      rating
      gamesPlayed
      wins
      winRate
      streak
    }
    totalCount
    yourRank {
      rank
      rating
    }
  }
}

query FriendsLeaderboard($options: LeaderboardOptions!) {
  friendsLeaderboard(options: $options) {
    ...LeaderboardFragment
  }
}
```

**Пропсы:**
```typescript
interface LeaderboardViewProps {
  defaultTab?: 'global' | 'friends' | 'weekly';
}

interface LeaderboardOptions {
  mode?: GameMode;
  period?: 'all' | 'weekly' | 'monthly';
  limit?: number;
  offset?: number;
  search?: string;
}
```

---

### LeaderboardTable.tsx

**Функциональность:**
- Заголовки таблицы (Rank, Player, Rating, Win Rate, Games)
- Сортировка по колонкам
- Пагинация (внизу)
- Пустое состояние
- Loading skeleton

**Колонки:**
| Колонка | Описание |
|---------|----------|
| Rank | Позиция с иконкой (🥇🥈🥉 для топ-3) |
| Player | Аватар, имя, флаг страны |
| Rating | ELO рейтинг |
| Win Rate | Процент побед |
| Games | Количество игр |
| Streak | Текущая серия побед/поражений |

---

### PlayerRow.tsx

**Функциональность:**
- Отображение одной строки таблицы
- Подсветка если это текущий пользователь
- Hover эффект с preview профиля
- Клик для перехода к профилю

**Пропсы:**
```typescript
interface PlayerRowProps {
  player: LeaderboardEntry;
  isCurrentUser: boolean;
  onClick: (playerId: string) => void;
}
```

---

### LeaderboardTabs.tsx

**Функциональность:**
- Переключение между табами
- Индикатор активного таба
- Badge с количеством для Friends

---

## Задача 7.2 - ProfileView

Профиль игрока со статистикой.

### Компоненты для создания:
```
src/components/profile/
├── ProfileView.tsx         # Главный компонент
├── ProfileHeader.tsx       # Шапка профиля
├── ProfileStats.tsx        # Статистика
├── MatchHistory.tsx        # История матчей
└── RatingChart.tsx         # График рейтинга
```

---

### ProfileView.tsx

**Функциональность:**
- Аватар, имя, рейтинг
- Статистика (игры, победы, победы/поражения)
- История матчей
- Любимый герой
- График рейтинга за время
- Редактирование профиля (если свой)

**GraphQL операции:**
```graphql
query Profile($userId: ID!) {
  profile(userId: $userId) {
    user {
      id
      username
      avatar
      country
      bio
      createdAt
    }
    stats {
      gamesPlayed
      wins
      losses
      winRate
      currentStreak
      bestStreak
      favoriteHero { id name thumbnailUrl }
    }
    rating {
      current
      peak
      rank
    }
  }
}

query MatchHistory($userId: ID!, $options: HistoryOptions!) {
  matchHistory(userId: $userId, options: $options) {
    games {
      id
      mode
      result
      heroes { ... }
      playedAt
      ratingChange
    }
    totalCount
  }
}

query RatingHistory($userId: ID!, $period: Period!) {
  ratingHistory(userId: $userId, period: $period) {
    date
    rating
    gameId
  }
}
```

**Пропсы:**
```typescript
interface ProfileViewProps {
  userId: string;
  isOwnProfile?: boolean;
}
```

---

### ProfileHeader.tsx

**Функциональность:**
- Большой аватар
- Имя пользователя
- Страна (флаг)
- Рейтинг (крупно)
- Ранг в мире
- Кнопка "Редактировать" (если свой профиль)
- Кнопка "Добавить в друзья" (если чужой)

---

### ProfileStats.tsx

**Функциональность:**
- Сетка статистики
- Карточки с метриками:
  - Игры сыграно
  - Победы / Поражения
  - Win Rate (круговая диаграмма)
  - Текущая серия
  - Лучший герой
  - Пиковый рейтинг

**Layout:**
```
┌─────────────┬─────────────┬─────────────┐
│  Games      │   Win Rate  │   Streak    │
│    123      │     58%     │    +5       │
└─────────────┴─────────────┴─────────────┘
┌─────────────┬─────────────┬─────────────┐
│   Wins      │  Losses     │ Best Hero   │
│     71      │     52      │ Daredevil   │
└─────────────┴─────────────┴─────────────┘
```

---

### MatchHistory.tsx

**Функциональность:**
- Список последних игр
- Каждая игра показывает:
  - Результат (победа/поражение)
  - Режим игры
  - Использованные герои
  - Дата
  - Изменение рейтинга (+15, -12)
- Пагинация
- Клик для просмотра деталей/реплея

**Пропсы:**
```typescript
interface MatchHistoryProps {
  games: GameSummary[];
  onLoadMore: () => void;
  onGameClick: (gameId: string) => void;
}
```

---

### RatingChart.tsx

**Функциональность:**
- График рейтинга за время
- Периоды: неделя, месяц, всё время
- Hover показывает детали точки
- Подсветка пикового рейтинга

**Библиотека:** Можно использовать Recharts, Chart.js или простой SVG

**Пропсы:**
```typescript
interface RatingChartProps {
  data: RatingHistoryPoint[];
  period: 'week' | 'month' | 'all';
}
```

---

## Задача 7.3 - Profile Editing

Редактирование профиля (для своего профиля).

### Компонент:
```
src/components/profile/
└── EditProfileModal.tsx    # Модальное окно редактирования
```

**Функциональность:**
- Загрузка аватара
- Изменение имени
- Изменение страны
- Редактирование bio
- Сохранение изменений

**GraphQL мутация:**
```graphql
mutation UpdateProfile($input: UpdateProfileInput!) {
  updateProfile(input: $input) {
    user { ... }
  }
}

input UpdateProfileInput {
  username?: String
  avatar?: Upload
  country?: String
  bio?: String
}
```

---

## Задача 7.4 - Friends System (будущее)

Система друзей (опционально).

### Компоненты:
```
src/components/social/
├── FriendsList.tsx         # Список друзей
├── FriendRequest.tsx       # Запрос в друзья
└── OnlineStatus.tsx        # Онлайн статус
```

**Функциональность:**
- Список друзей с онлайн статусом
- Отправка запроса в друзья
- Принятие/отклонение запросов
- Удаление из друзей
- Приглашение друга в игру

---

## Задача 7.5 - Achievements (будущее)

Система достижений (опционально).

### Компоненты:
```
src/components/profile/
└── Achievements.tsx        # Достижения
```

**Функциональность:**
- Список достижений
- Прогресс по каждому
- Иконки и названия
- Скрытые достижения (???)

**Примеры достижений:**
- 🏆 Первая победа
- ⚔️ 100 игр
- 🔥 10 побед подряд
- 🎯 Победить с полным HP
- 👑 Достичь топ-100

---

## Результат ФАЗЫ 7

- ✅ Пользователь видит таблицу лидеров
- ✅ Пользователь видит профиль игрока
- ✅ Пользователь видит историю матчей
- ✅ Пользователь видит график рейтинга
- ✅ Пользователь может редактировать свой профиль

---

## Все фазы завершены! 🎉

Frontend готов к реализации. Ознакомьтесь с README.md для общего обзора.
