# Unmatched Admin Panel

Админ-панель для управления контентом игры Unmatched на базе **Refine.dev**.

## Установка

```bash
cd admin
npm install
```

## Запуск

```bash
npm run dev
```

Админ-панель будет доступна по адресу: http://localhost:5174

## Учетные данные для входа

- **Email**: admin@unmached.local
- **Password**: Admin123!

## Функционал

### Heroes (Герои)
- Просмотр списка всех героев
- Создание новых героев
- Редактирование характеристик
- Удаление героев

### Cards (Карты)
- Просмотр всех карт
- Создание новых карт
- Редактирование параметров
- Удаление карт

### Boards (Доски)
- Просмотр игровых досок
- Создание новых досок
- Редактирование конфигурации
- Удаление досок

### Users (Пользователи)
- Просмотр списка пользователей
- Редактирование ролей
- Бан/разбан пользователей

## Архитектура

```
admin/
├── src/
│   ├── pages/           # Страницы приложения
│   ├── providers/       # Auth и Data providers
│   ├── resources/       # CRUD ресурсы (TODO)
│   ├── graphql/         # GraphQL queries/mutations
│   ├── App.tsx          # Главный компонент
│   ├── main.tsx         # Точка входа
│   └── index.css        # Глобальные стили
├── public/              # Статические файлы
├── index.html           # HTML шаблон
├── vite.config.ts       # Vite конфигурация
├── tailwind.config.js   # Tailwind конфигурация
└── package.json         # Зависимости
```

## GraphQL API

Админ-панель использует GraphQL API бэкенда на `http://localhost:3000/graphql`.

### Основные queries

```graphql
query GetHeroes {
  heroes {
    id
    name
    health
    set
  }
}

query GetAdminStats {
  adminStats {
    totalUsers
    totalHeroes
    totalCards
    totalBoards
  }
}
```

### Основные mutations

```graphql
mutation CreateHero($input: CreateHeroInput!) {
  createHero(input: $input) {
    id
    name
    health
  }
}

mutation UpdateHero($id: ID!, $input: UpdateHeroInput!) {
  updateHero(id: $id, input: $input) {
    id
    name
  }
}

mutation DeleteHero($id: ID!) {
  deleteHero(id: $id)
}
```

## Разработка

### Генерация GraphQL типов

```bash
npm run codegen
```

### Сборка для продакшна

```bash
npm run build
```

### Локальный превью сборки

```bash
npm run preview
```

## TODO

- [ ] Полностью реализовать CRUD ресурсы для Heroes
- [ ] Полностью реализовать CRUD ресурсы для Cards
- [ ] Полностью реализовать CRUD ресурсы для Boards
- [ ] Полностью реализовать CRUD ресурсы для Users
- [ ] Добавить страницу импорта данных из scraped-data
- [ ] Добавить валидацию форм
- [ ] Добавить обработку ошибок
- [ ] Добавить загрузку изображений
- [ ] Улучшить UI/UX
