# План развития Admin Panel для Unmatched

Детальный план реализации админ-панели с использованием **Refine.dev** + **shadcn/ui**.

---

## Справочная информация

### Tech Stack
- **Backend**: NestJS + GraphQL + Prisma + PostgreSQL
- **Frontend**: React + Vite + Refine.dev + Ant Design
- **Admin Port**: 5480
- **API Port**: 3000 (GraphQL)

### Учетные данные по умолчанию
- **Admin**: admin@unmached.local / Admin123!
- **Moderator**: moderator@unmached.local / Moderator123!

---

## 1. UI Библиотека: Ant Design + Refine.dev

### Почему Ant Design?
- Полнофункциональная библиотека с богатым набором компонентов
- Нативная интеграция с Refine.dev через `@refinedev/antd`
- Табличные компоненты с сортировкой, фильтрацией, пагинацией из коробки
- Формовые компоненты с валидацией
- Много встроенных компонентов (DatePicker, Upload, Select, etc.)

### Установка зависимостей
```bash
cd admin
npm install @refinedev/antd @tanstack/react-query
```

### Конфигурация
Не требует дополнительной настройки тем - Ant Design имеет встроенные темы.

**Дополнительные компоненты для редактора досок:**
```bash
npm install react-monaco-editor  # JSON редактор с подсветкой
npm install @uiw/react-json-view  # Просмотр JSON
```

---

## 2. Админские Коллекции (Resources)

### 2.1 Dashboard (Главная страница)

**Назначение:** Обзор системной статистики и быстрые действия

**Компоненты:**
| Компонент | Описание |
|-----------|----------|
| Stat Cards | Всего пользователей, героев, карт, досок, активных игр |
| Activity Feed | Последние 10 игр |
| Quick Actions | Кнопки быстрого создания |
| System Health | Индикаторы состояния |

**GraphQL Query:**
```graphql
query GetDashboardStats {
  adminStats {
    totalUsers
    totalHeroes
    totalCards
    totalBoards
    totalGames
    activeGames
  }
}
```

---

### 2.2 Heroes (Герои)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| imageUrl | Image | Аватар героя |
| name | Text | Отображаемое имя |
| nameEn | Text | Английское название |
| nameRu | Text | Русское название |
| set | Tag | Выпуск (бокс) |
| health | Number | Очки здоровья |
| fighterType | Badge | HERO/MINION/HUGE |
| createdAt | Date | Дата создания |
| actions | - | Edit, Delete, View |

**Фильтры:**
- Поиск по имени (nameEn/nameRu)
- Выпуск (dropdown)
- Тип бойца (dropdown)
- Диапазон здоровья

**Create/Edit Form - поля:**
| Поле | Тип | Обязательно | Валидация |
|------|-----|-------------|-----------|
| name | Text | Да | Уникальное |
| nameEn | Text | Да | - |
| nameRu | Text | Да | - |
| set | Select | Да | Предопределённые выпуски |
| health | Number | Да | Min: 1, Max: 30 |
| fighterType | Select | Да | HERO/MINION/HUGE |
| ability | JSON Editor | Нет | Schema validated |
| deckCards | JSON Editor | Нет | Array of card references |
| properties | JSON Editor | Нет | Schema validated |
| imageUrl | URL/Upload | Нет | Valid URL |
| avatarUrl | URL/Upload | Нет | Valid URL |

**Действия:**
- Создать героя
- Редактировать героя
- Удалить героя (с подтверждением и cascade для карт)
- Дублировать героя
- Экспорт в JSON

---

### 2.3 Cards (Карты)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| name | Text | Название карты |
| nameEn | Text | Английское название |
| nameRu | Text | Русское название |
| hero | Relation | Имя героя (кликабельно) |
| cardType | Badge | ATTACK/DEFENSE/SCHEME/MANEUVER |
| subType | Text | Подтип (например "Journey") |
| attackValue | Number | Значение атаки |
| defenseValue | Number | Значение защиты |
| boostValue | Number | Значение усиления |
| count | Number | Количество в колоде |
| actions | - | Edit, Delete |

**Фильтры:**
- Поиск по имени
- Герой (dropdown с поиском)
- Тип карты (multi-select)
- Диапазоны значений

**Create/Edit Form - поля:**
| Поле | Тип | Обязательно | Валидация |
|------|-----|-------------|-----------|
| name | Text | Да | - |
| nameEn | Text | Да | - |
| nameRu | Text | Да | - |
| heroId | Select | Да | Должен существовать |
| cardType | Select | Да | ATTACK/DEFENSE/SCHEME/MANEUVER |
| subType | Text | Нет | - |
| attackValue | Number | Условно | Обязательно для ATTACK |
| defenseValue | Number | Условно | Обязательно для DEFENSE |
| boostValue | Number | Нет | - |
| effects | JSON Editor | Нет | Array of effects |
| text | Textarea | Нет | Описание карты |
| textEn | Textarea | Нет | Описание на английском |
| textRu | Textarea | Нет | Описание на русском |
| count | Number | Да | Min: 1, Max: 10 |

---

### 2.4 Boards (Доски)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| name | Text | Название доски |
| nameEn | Text | Английское название |
| nameRu | Text | Русское название |
| set | Tag | Выпуск |
| width | Number | Ширина (клетки) |
| height | Number | Высота (клетки) |
| imageUrl | Image | Превью доски |
| actions | - | Edit, Delete |

**Create/Edit Form - поля:**
| Поле | Тип | Обязательно | Валидация |
|------|-----|-------------|-----------|
| name | Text | Да | Уникальное |
| nameEn | Text | Да | - |
| nameRu | Text | Да | - |
| set | Select | Да | - |
| width | Number | Да | Min: 3, Max: 10 |
| height | Number | Да | Min: 3, Max: 10 |
| cells | JSON Editor | Да | Grid definition |
| features | JSON Editor | Нет | Special features |
| imageUrl | URL/Upload | Нет | - |
| imageUrlDark | URL/Upload | Нет | Вариант для dark mode |

**Спец. компонент:** Визуальный редактор доски (2D grid) + JSON редактор с переключением
- **Visual Board Editor**: Drag-and-drop клеток, zones, obstacles
- **JSON Editor**: Monaco Editor с подсветкой синтаксиса для точного редактирования
- Переключение между режимами вкладкой "Visual" / "JSON"

---

### 2.5 Users (Пользователи)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| avatar | Image | Аватар пользователя |
| username | Text | Имя пользователя |
| email | Text | Email |
| role | Badge | USER/ADMIN/MODERATOR |
| stats.gamesPlayed | Number | Игр сыграно |
| stats.gamesWon | Number | Побед |
| stats.currentElo | Number | Текущий ELO |
| emailVerified | Boolean | Статус верификации |
| createdAt | Date | Дата регистрации |
| deletedAt | Date | Дата бана (если есть) |
| actions | - | Edit, Ban/Unban, View Stats |

**Фильтры:**
- Поиск по email или username
- Роль (multi-select)
- Email verified (yes/no)
| Бanned status | (yes/no) |
| ELO range | Слайдер |
| Registration date | Диапазон |

**Edit Form - поля:**
| Поле | Тип | Редактируемо | Заметки |
|------|-----|--------------|---------|
| username | Text | Да | Уникальное |
| email | Text | Да | Уникальное |
| role | Select | Да | USER/ADMIN/MODERATOR |
| avatar | URL/Upload | Да | - |
| deletedAt | DateTime | Да (ban) | Null = active |

**Действия:**
- Просмотр профиля пользователя
- Редактирование
- Бан (soft delete)
| Разбан
| Сброс пароля
| Просмотр истории игр
| Просмотр audit logs

**Read-only секции:**
- Статистика (UserStats relation)
| Настройки (UserSettings relation)

---

### 2.6 Games (Игры - read-only мониторинг)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | Text | ID игры |
| code | Text | Код приглашения |
| status | Badge | PENDING/LOBBY/IN_PROGRESS/FINISHED/ABORTED |
| mode | Badge | ONE_V_ONE/TWO_V_TWO/VS_AI |
| host | Relation | Host username |
| opponent | Relation | Opponent username |
| board | Relation | Board name |
| createdAt | Date | Время создания |
| startedAt | Date | Время начала |
| endedAt | Date | Время окончания |
| winner | Relation | Победитель |
| actions | - | View Details, Replay |

**Действия:**
- Просмотр деталей игры
| Просмотр лога действий
| Скачать реплей
| Прервать игру (admin action)

---

### 2.7 Game Actions (Действия в игре - read-only)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | Text | Action ID |
| game | Relation | Game ID |
| type | Badge | Тип действия (enum) |
| sequenceNumber | Number | Порядок |
| player | Relation | Игрок |
| payload | JSON | Данные (раскрываемый) |
| timestamp | Date | Время |

---

### 2.8 Auth Audit Logs (read-only)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | Text | Log ID |
| user | Relation | User |
| action | Text | Тип действия |
| success | Badge | Success/Failure |
| ipAddress | Text | IP адрес |
| errorMessage | Text | Ошибка |
| createdAt | Date | Timestamp |

---

### 2.9 Matchmaking Queue (Очередь матчмейкинга - read-only)

**List Page - колонки таблицы:**
| Колонка | Тип | Описание |
|---------|-----|----------|
| userId | Text | User ID |
| user | Relation | Username |
| mode | Badge | Game mode |
| heroPref | Text | Предпочтительный герой |
| rating | Number | ELO |
| joinedAt | Date | Время входа |
| waitTime | Calculated | Время ожидания |

---

## 3. Система Seeding (Наполнения БД)

### 3.1 Структура файлов

```
backend/prisma/
├── seed.ts                    # Основной seed (test users + sample content)
├── seed-admin.ts              # Admin/moderator accounts (EXISTS)
├── seed-content/              # Контент для наполнения (NEW)
│   ├── index.ts               # Точка входа
│   ├── heroes/                # Данные героев
│   │   ├── index.ts
│   │   ├── daredevil.ts       # (EXISTS)
│   │   ├── ms-marvel.ts       # (EXISTS)
│   │   ├── bullseye.ts        # TO ADD
│   │   └── ...
│   ├── cards/                 # Карты по героям
│   └── boards/                # Описания досок
│       ├── index.ts
│       ├── cobble-city.ts     # TO ADD
│       └── ...
└── migrations/                # Миграции БД
```

### 3.2 Категории Seed данных

**Essential Seeds (запускаются на каждом новом БД):**
1. Admin user (seed-admin.ts) ✅ EXISTS
2. Moderator user (seed-admin.ts) ✅ EXISTS
3. 2-3 полных героя с картами
4. 1 доска
5. Test users для разработки

**Development Seeds:**
- Полный список героев из scraped-data
- Все карты
- Все доски
| Тестовые игры с различными состояниями
| Примеры audit logs

**Production Seeds:**
- Только admin
| Базовый контент (опционально)

### 3.4 JSON структура для Heroes

```typescript
// backend/prisma/seed-content/heroes/hero-template.ts
export const heroTemplate = {
  name: "hero-name",           // Уникальный ID
  nameEn: "Hero Name",
  nameRu: "Имя Героя",
  set: "Битва легенд. Том первый",
  health: 15,
  fighterType: "HERO",         // HERO | MINION | HUGE
  ability: {
    type: "passive",
    timing: "start_of_turn",
    effect: "description",
    value: null
  },
  deckCards: [
    { cardName: "Strike", count: 3 },
    { cardName: "Defend", count: 3 }
  ],
  properties: {
    hasSidekick: false,
    sidekickCount: 0,
    specialRules: []
  },
  imageUrl: "https://example.com/hero.png",
  avatarUrl: "https://example.com/avatar.png"
};
```

### 3.5 JSON структура для Cards

```typescript
// backend/prisma/seed-content/cards/card-template.ts
export const cardTemplate = {
  name: "card-name",
  nameEn: "Card Name",
  nameRu: "Название Карты",
  cardType: "ATTACK",          // ATTACK | DEFENSE | SCHEME | MANEUVER
  subType: null,               // e.g. "Journey"
  attackValue: 5,
  defenseValue: null,
  boostValue: null,
  effects: [
    {
      timing: "on_play",
      type: "damage",
      value: 5,
      condition: null
    }
  ],
  text: "Deal 5 damage.",
  textEn: "Deal 5 damage.",
  textRu: "Наносит 5 урона.",
  count: 3                     // Количество в колоде
};
```

### 3.6 JSON структура для Boards

```typescript
// backend/prisma/seed-content/boards/board-template.ts
export const boardTemplate = {
  name: "board-name",
  nameEn: "Board Name",
  nameRu: "Название Доски",
  set: "Битва легенд. Том первый",
  width: 6,
  height: 6,
  cells: [
    { x: 0, y: 0, type: "normal", zone: "p1-start", connections: ["right"] },
    { x: 1, y: 0, type: "normal", zone: "p1-start", connections: ["left", "right"] },
    // ... остальные ячейки
  ],
  features: {
    secretPassages: [],
    doors: [],
    highGround: []
  },
  imageUrl: "https://example.com/board.png",
  imageUrlDark: "https://example.com/board-dark.png"
};
```

---

## 4. Автоматическое наполнение при старте проекта

### 4.1 npm scripts

Добавить в `package.json` (root):

```json
{
  "scripts": {
    "db:setup": "cd backend && npx prisma migrate deploy && npm run prisma:seed:all",
    "db:reset": "cd backend && npx prisma migrate reset && npm run prisma:seed:all",
    "db:seed": "cd backend && npm run prisma:seed:all",
    "dev:all": "concurrently \"npm run dev:backend\" \"npm run dev:admin\"",
    "dev:backend": "cd backend && npm run start:dev",
    "dev:admin": "cd admin && npm run dev"
  }
}
```

Добавить в `backend/package.json`:

```json
{
  "scripts": {
    "prisma:seed": "ts-node prisma/seed.ts",
    "prisma:seed:admin": "ts-node prisma/seed-admin.ts",
    "prisma:seed:content": "ts-node prisma/seed-content/index.ts",
    "prisma:seed:all": "npm run prisma:seed:admin && npm run prisma:seed:content && npm run prisma:seed"
  }
}
```

### 4.2 Docker Compose конфигурация

Добавить в `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: unmached
      POSTGRES_PASSWORD: unmached
      POSTGRES_DB: unmached
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U unmached"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://unmached:unmached@postgres:5432/unmached
    depends_on:
      postgres:
        condition: service_healthy
    command: sh -c "npx prisma migrate deploy && npm run prisma:seed:all && npm run start:dev"

  admin:
    build: ./admin
    environment:
      VITE_BACKEND_URL: http://localhost:3000
    ports:
      - "5480:80"
    depends_on:
      - backend
```

### 4.3 Порядок запуска проекта

**Для локальной разработки:**

```bash
# 1. Клонировать репозиторий
git clone <repo>
cd unmached

# 2. Установить зависимости
npm install
cd backend && npm install
cd ../admin && npm install

# 3. Настроить .env файлы
cp backend/.env.example backend/.env
cp admin/.env.example admin/.env

# 4. Запустить БД и накатить миграции с сидами
npm run db:setup

# 5. Запустить все сервисы
npm run dev:all
```

**Для Docker:**

```bash
# 1. Запустить все сервисы
docker-compose up -d

# 2. Проверить логи
docker-compose logs -f
```

---

## 5. Backend Enhancements (новые GraphQL endpoints)

### 5.1 Новые Queries

```graphql
type Query {
  # Расширенный список пользователей с фильтрацией
  usersList(
    page: Int
    limit: Int
    search: String
    role: UserRole
    sortBy: String
  ): PaginatedUsersDto

  # Мониторинг игр
  gamesList(
    status: GameStatus
    mode: GameMode
    page: Int
    limit: Int
  ): PaginatedGamesDto

  gameDetails(id: ID!): GameDetailsDto

  # Audit логи
  auditLogs(
    userId: ID
    action: String
    success: Boolean
    page: Int
    limit: Int
  ): PaginatedAuditLogsDto

  # Matchmaking очередь
  matchmakingQueue: [MatchmakingQueueEntryDto]
}
```

### 5.2 Новые Mutations

```graphql
type Mutation {
  # Управление пользователями
  resetUserPassword(userId: ID!, newPassword: String!): Boolean

  # Бulk операции для контента
  importHeroes(json: String!): ImportResultDto
  importCards(json: String!): ImportResultDto

  # Управление играми
  abortGame(gameId: ID!): Boolean

  # Управление очередью
  removeFromQueue(userId: ID!): Boolean
  forceMatch(userIds: [ID!]!): GameDto
}
```

### 5.3 Subscriptions для real-time обновлений

```graphql
type Subscription {
  gameUpdated(gameId: ID!): GameDto
  queueUpdated: [MatchmakingQueueEntryDto]
  newAuditLog: AuthAuditLog
}
```

---

## 6. Структура файлов Admin Frontend

```
admin/src/
├── App.tsx                          # Main app with Refine provider
├── main.tsx                         # Entry point
├── index.css                        # Global styles + shadcn variables
│
├── components/
│   ├── ui/                          # Ant Design components (from @refinedev/antd)
│   ├── layout/
│   │   ├── Header.tsx               # Ant Design Layout.Header
│   │   ├── Sidebar.tsx              # Ant Design Layout.Sider
│   │   └── Layout.tsx               # Ant Design Layout wrapper
│   └── common/
│       ├── StatCard.tsx             # Custom stat card
│       ├── JsonEditor.tsx           # Monaco Editor for JSON
│       ├── JsonViewer.tsx           # View-only JSON viewer
│       ├── ImageUpload.tsx          # Ant Design Upload
│       ├── BoardVisualEditor.tsx    # 2D Grid board editor
│       └── Badge.tsx                # Ant Design Badge wrapper
│
├── pages/
│   ├── dashboard.tsx                # EXISTS - enhance
│   ├── login.tsx                    # EXISTS - enhance with shadcn
│   ├── heroes/
│   │   ├── list.tsx
│   │   ├── show.tsx
│   │   ├── create.tsx
│   │   └── edit.tsx
│   ├── cards/
│   │   ├── list.tsx
│   │   ├── show.tsx
│   │   ├── create.tsx
│   │   └── edit.tsx
│   ├── boards/
│   │   ├── list.tsx
│   │   ├── show.tsx
│   │   ├── create.tsx
│   │   ├── edit.tsx
│   │   └── BoardEditor.tsx          # Visual board editor
│   ├── users/
│   │   ├── list.tsx
│   │   ├── show.tsx
│   │   └── edit.tsx
│   ├── games/
│   │   ├── list.tsx
│   │   └── show.tsx
│   ├── audit-logs/
│   │   └── list.tsx
│   └── queue/
│       └── list.tsx
│
├── providers/
│   ├── authProvider.ts              # EXISTS - enhance
│   ├── dataProvider.ts              # EXISTS - keep
│   └── liveProvider.ts              # NEW - for subscriptions
│
├── graphql/
│   ├── queries.ts                   # GraphQL query definitions
│   ├── mutations.ts                 # GraphQL mutation definitions
│   ├── subscriptions.ts             # GraphQL subscriptions
│   └── schema.ts                    # Generated types
│
├── lib/
│   ├── utils.ts                     # Utility functions
│   └── constants.ts                 # App constants
│
└── types/
    └── index.ts                     # TypeScript type definitions
```

---

## 7. Порядок реализации (Prioritized)

### Фаза 1: Foundation (Неделя 1)

**Приоритет: Критически важно**

1. **Настройка Ant Design с Refine.dev**
   - Установка `@refinedev/antd`
   - Конфигурация темы Ant Design (темная/светлая)
   - Layout с Sidebar navigation (Ant Design Layout)
   - Настройка Monaco Editor для JSON полей

2. **Улучшение Auth Provider**
   - Role-based UI visibility
   - Обработка ошибок
   - Refresh token rotation

3. **Dashboard Page**
   - Stat cards с реальными данными
   - Recent activity feed
   - Quick actions

### Фаза 2: Content Management (Неделя 2)

**Приоритет: Высокий**

4. **Heroes Resource**
   - List, Create, Edit, Show страницы
   - JSON editor для ability/deckCards
   - Image upload
   - Фильтры и поиск

5. **Cards Resource**
   - List, Create, Edit, Show страницы
   - Hero selection dropdown
   - JSON editor для effects

6. **Boards Resource**
   - List, Create, Edit, Show страницы
   - Visual board editor (2D grid)

### Фаза 3: User Management (Неделя 3)

**Приоритет: Высокий**

7. **Users Resource**
   - List, Edit, Show страницы
   - Ban/Unban действия
   - Role management
   - User stats viewer

### Фаза 4: Monitoring (Неделя 4)

**Приоритет: Средний**

8. **Games Monitoring**
   - List active games
   - Game detail view
   - Real-time updates (subscriptions)

9. **Audit Logs**
   - Filterable log viewer
   - Security event highlighting

### Фаза 5: Advanced Features (Неделя 5)

**Приоритет: Низкий**

10. **Import/Export**
    - Bulk import from JSON
    - Export functionality

11. **Matchmaking Queue Monitor**
    - Real-time queue view

12. **Analytics Dashboard**
    - Game statistics
    - Hero popularity

---

## 8. Критические файлы для реализации

| Файл | Описание |
|------|----------|
| `admin/package.json` | Обновить зависимости для @refinedev/antd |
| `admin/src/App.tsx` | Core Refine configuration с Ant Design |
| `admin/src/components/common/BoardVisualEditor.tsx` | NEW - 2D grid редактор досок |
| `admin/src/components/common/JsonEditor.tsx` | NEW - Monaco Editor для JSON |
| `backend/src/admin/admin.resolver.ts` | Extend с новыми queries/mutations |
| `backend/src/admin/admin.service.ts` | Service методы для расширенного функционала |
| `backend/prisma/seed-content/index.ts` | NEW - Основной seed контента |
| `backend/prisma/seed-content/heroes/` | NEW - Данные героев |
| `backend/prisma/seed-content/cards/` | NEW - Данные карт |
| `backend/prisma/seed-content/boards/` | NEW - Данные досок |

---

## 9. Полезные ссылки

- [Refine Documentation](https://refine.dev/docs)
- [Refine + Ant Design Guide](https://refine.dev/docs/ui-integrations/ant-design/)
- [Ant Design Components](https://ant.design/components/overview/)
- [Monaco Editor](https://microsoft.github.io/monaco-editor/)
- [Prisma Seeding](https://www.prisma.io/docs/guides/database/seed-database)
- [GraphQL Code Generator](https://the-guild.dev/graphql/codegen)
