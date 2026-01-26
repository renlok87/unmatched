# ФАЗА 0: Infrastructure Setup

## Задача 0.1 - Структура репозитория

Создать структуру для monorepo или отдельного backend репозитория.

### Действия:
1. Определить структуру: monorepo (frontend + backend) или отдельные репозитории
2. Если monorepo - создать директорию `backend/`
3. Создать базовую структуру папок

### Файлы:
- `backend/` (если monorepo)

---

## Задача 0.2 - Docker Compose

Настроить Docker Compose для локальной разработки.

### Требуемые сервисы:
- PostgreSQL 15
- Redis 7
- Backend (NestJS)
- PgAdmin (опционально)
- Redis Commander (опционально)

### Файлы:
- `docker-compose.yml`
- `.env.docker` (пример переменных)

### Переменные окружения:
```
POSTGRES_DB=unmatched
POSTGRES_USER=unmatched
POSTGRES_PASSWORD=password
REDIS_PORT=6379
```

---

## Задача 0.3 - ESLint, Prettier, Husky

Настроить инструменты для форматирования и проверки кода.

### Действия:
1. Установить ESLint для TypeScript + NestJS
2. Установить Prettier
3. Настроить Husky для pre-commit hooks
4. Настроить lint-staged

### Файлы:
- `.eslintrc.js`
- `.prettierrc`
- `.husky/pre-commit`
- `package.json` (скрипты)

---

## Задача 0.4 - .env.example

Создать пример файла переменных окружения с описанием всех переменных.

### Переменные:
```bash
# Database
DATABASE_URL=

# Redis
REDIS_HOST=
REDIS_PORT=

# JWT
JWT_SECRET=
JWT_EXPIRES_IN=
REFRESH_TOKEN_SECRET=
REFRESH_TOKEN_EXPIRES_IN=

# App
PORT=3000
NODE_ENV=

# CORS
FRONTEND_URL=
```

### Файл:
- `.env.example`
