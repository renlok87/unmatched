# Unmatched Admin Panel

Документация по админ-панели для управления контентом игры Unmatched.

## Обзор

Админ-панель построена на **Refine.dev v5** с интеграцией **Shadcn/ui** и использует GraphQL API бэкенда для CRUD операций.

## Структура проекта

```
backend/src/admin/
├── admin.module.ts           # Admin модуль
├── admin.resolver.ts         # GraphQL mutations для CRUD
├── admin.service.ts          # Бизнес-логика админки
├── dto/
│   └── admin.dto.ts          # DTO для GraphQL операций
└── guards/
    └── admin.guard.ts        # Guards для защиты эндпоинтов

admin/                        # Отдельное Vite приложение
├── src/
│   ├── pages/               # Страницы (Dashboard, Login)
│   ├── providers/           # Auth и Data providers
│   ├── resources/           # CRUD ресурсы (TODO)
│   ├── graphql/             # GraphQL queries/mutations
│   └── App.tsx              # Главный компонент
└── package.json

scripts/
└── import-content.ts        # Импорт данных из scraped-data
```

## Учетные данные

| Роль | Email | Пароль |
|------|-------|--------|
| Администратор | admin@unmached.local | Admin123! |
| Модератор | moderator@unmached.local | Moderator123! |

## GraphQL API

### Admin Stats

```graphql
query {
  adminStats {
    totalUsers
    totalHeroes
    totalCards
    totalBoards
    totalGames
  }
}
```

### Heroes CRUD

```graphql
# Создать героя
mutation CreateHero($input: CreateHeroInput!) {
  createHero(input: $input) {
    id
    name
    health
    set
  }
}

# Обновить героя
mutation UpdateHero($id: ID!, $input: UpdateHeroInput!) {
  updateHero(id: $id, input: $input) {
    id
    name
  }
}

# Удалить героя
mutation DeleteHero($id: ID!) {
  deleteHero(id: $id)
}
```

### Cards CRUD

```graphql
mutation CreateCard($input: CreateCardInput!) {
  createCard(input: $input) {
    id
    name
    cardType
  }
}

mutation UpdateCard($id: ID!, $input: UpdateCardInput!) {
  updateCard(id: $id, input: $input) {
    id
    name
  }
}

mutation DeleteCard($id: ID!) {
  deleteCard(id: $id)
}
```

### Boards CRUD

```graphql
mutation CreateBoard($input: CreateBoardInput!) {
  createBoard(input: $input) {
    id
    name
    width
    height
  }
}

mutation UpdateBoard($id: ID!, $input: UpdateBoardInput!) {
  updateBoard(id: $id, input: $input) {
    id
    name
  }
}

mutation DeleteBoard($id: ID!) {
  deleteBoard(id: $id)
}
```

### Users Management

```graphql
# Получить список пользователей
query UsersList($page: Int, $limit: Int, $search: String) {
  usersList(page: $page, limit: $limit, search: $search) {
    users {
      id
      email
      username
      role
      createdAt
    }
    total
    totalPages
  }
}

# Обновить пользователя
mutation UpdateUser($id: ID!, $input: UpdateUserInput!) {
  updateUser(id: $id, input: $input) {
    id
    email
    role
  }
}

# Забанить пользователя
mutation BanUser($id: ID!) {
  banUser(id: $id)
}

# Разбанить пользователя
mutation UnbanUser($id: ID!) {
  unbanUser(id: $id)
}
```

## Импорт данных из scraped-data

Для импорта данных из папки `scraped-data/api/normalized/`:

```bash
cd backend
npx tsx src/scripts/import-content.ts
```

Скрипт выполнит:
1. Парсинг JSON файлов героев
2. Создание записей в БД (Heroes, Cards)
3. Дедупликацию по имени

## Запуск

### Backend

```bash
cd backend
npm run start:dev
```

GraphQL Playground: http://localhost:3000/graphql

### Admin Panel

```bash
cd admin
npm install
npm run dev
```

Админ-панель: http://localhost:5174

## Создание админской учетки

Если учетка еще не создана:

```bash
cd backend
npx tsx prisma/seed-admin.ts
```

## Модель данных в БД

### Hero
- `id` - уникальный идентификатор
- `name` - имя героя (уникальное)
- `nameEn` - английское название
- `nameRu` - русское название
- `set` - выпуск (набор)
- `health` - здоровье
- `fighterType` - тип бойца
- `ability` - способность (JSON)
- `deckCards` - карты колоды (JSON)
- `properties` - дополнительные свойства (JSON)
- `imageUrl` - URL изображения
- `avatarUrl` - URL аватара

### Card
- `id` - уникальный идентификатор
- `name` - название карты
- `heroId` - ID героя
- `cardType` - тип карты (ATTACK, DEFENSE, SCHEME, UNIVERSAL)
- `attackValue` - значение атаки
- `defenseValue` - значение защиты
- `boostValue` - значение усиления
- `effects` - эффекты (JSON)

### Board
- `id` - уникальный идентификатор
- `name` - название доски (уникальное)
- `width` - ширина
- `height` - высота
- `cells` - ячейки (JSON)
- `features` - особенности (JSON)

## TODO

- [ ] Полностью реализовать CRUD ресурсы в admin/
- [ ] Добавить валидацию форм
- [ ] Добавить загрузку изображений
- [ ] Добавить страницу импорта данных в админке
- [ ] Добавить real-time обновления через subscriptions
- [ ] Добавить аналитику и дашборды
