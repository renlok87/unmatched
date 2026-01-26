# Unmatched Backend

Backend сервис для игры Unmatched на NestJS + GraphQL + PostgreSQL + Redis.

## 🚀 Быстрый старт

### Требования
- Node.js 18+
- Docker & Docker Compose
- pnpm или npm

### 1. Запуск Docker сервисов

```bash
# Запуск PostgreSQL и Redis
docker-compose up -d

# С PgAdmin и Redis Commander (для разработки)
docker-compose --profile admin up -d
```

Доступные сервисы:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- PgAdmin: `http://localhost:5050` (admin@unmatched.local / admin)
- Redis Commander: `http://localhost:8081`

### 2. Установка зависимостей

```bash
cd backend
npm install
```

### 3. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env` при необходимости.

### 4. Запуск в режиме разработки

```bash
npm run start:dev
```

GraphQL Playground будет доступен по адресу: `http://localhost:3001/graphql`

## 📁 Структура проекта

```
backend/
├── src/
│   ├── config/          # Конфигурация приложения
│   ├── database/        # Prisma сервисы
│   ├── redis/           # Redis модуль
│   ├── graphql/         # GraphQL настройки
│   ├── auth/            # Auth модуль
│   ├── users/           # Users модуль
│   ├── game/            # Game модуль
│   ├── matchmaking/     # Matchmaking модуль
│   ├── content/         # Content модуль
│   ├── presence/        # Presence модуль
│   ├── history/         # History/Replay модуль
│   ├── leaderboard/     # Leaderboard модуль
│   └── common/          # Общая функциональность
│       ├── guards/
│       ├── decorators/
│       ├── interceptors/
│       ├── filters/
│       └── pipes/
├── prisma/
│   └── schema.prisma    # Prisma схема
├── test/                # E2E тесты
└── package.json
```

## 🔧 Доступные скрипты

| Команда | Описание |
|---------|----------|
| `npm run start:dev` | Запуск в режиме разработки |
| `npm run build` | Сборка проекта |
| `npm run start:prod` | Запуск продакшн версии |
| `npm run lint` | Проверка кода ESLint |
| `npm run format` | Форматирование кода Prettier |
| `npm run test` | Запуск unit тестов |
| `npm run test:e2e` | Запуск E2E тестов |
| `npm run prisma:generate` | Генерация Prisma Client |
| `npm run prisma:migrate` | Применение миграций |
| `npm run prisma:push` | Push схемы в БД |
| `npm run prisma:studio` | Prisma Studio |

## 🛠️ Технологии

- **Framework**: NestJS 11
- **Language**: TypeScript 5
- **Database**: PostgreSQL 15 + Prisma ORM
- **Cache**: Redis 7
- **API**: GraphQL (Apollo Server)
- **Auth**: JWT + Passport
- **Validation**: class-validator + class-transformer
- **Testing**: Jest

## 📝 Правила коммитов

Husky + lint-staged настроены для автоматической проверки кода перед коммитом.

## 🐳 Docker

### Остановка сервисов

```bash
docker-compose down
```

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f postgres
docker-compose logs -f redis
```

### Перезапуск сервисов

```bash
docker-compose restart
```
