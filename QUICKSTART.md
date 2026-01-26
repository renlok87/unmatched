# 🚀 Quick Start - Unmatched Backend

## Что сделано

✅ **ФАЗА 0: Infrastructure Setup** - Завершена
✅ **ФАЗА 1: Core Infrastructure** - Завершена

- ✅ Создана структура monorepo с backend директорией
- ✅ Настроен Docker Compose (PostgreSQL 15, Redis 7)
- ✅ Настроены ESLint, Prettier, Husky для кода
- ✅ Создан .env с переменными окружения
- ✅ Настроен ConfigModule с конфигурацией
- ✅ Создан полный Prisma schema с моделями User, Game, etc.
- ✅ Создан PrismaModule с автоматическим подключением
- ✅ Создан RedisModule с pub/sub, locks, sorted sets
- ✅ Настроен GraphQL Apollo Server с subscriptions
- ✅ Созданы кастомные скаляры (DateTime, JSON)

## 📋 Следующие шаги (ФАЗА 2: Auth Module)

### 1. Запуск Docker сервисов

```bash
# Базовый запуск (PostgreSQL + Redis)
docker-compose up -d

# С инструментами разработки (PgAdmin + Redis Commander)
docker-compose --profile admin up -d
```

### 2. Проверка статуса сервисов

```bash
# Проверить, что контейнеры запущены
docker ps

# Проверить логи
docker-compose logs -f
```

### 3. Инициализация Prisma

```bash
cd backend

# Создать .env файл
cp .env.example .env

# Инициализировать Prisma
npx prisma init

# (Опционально) Применить миграции
npm run prisma:push
```

### 4. Создание базовых модулей

```bash
# Config Module
nest g module config
nest g service config

# Database Module (Prisma)
nest g module database
nest g service prisma database

# Redis Module
nest g module redis
nest g service redis

# GraphQL Module
npm install --save @nestjs/graphql @apollo/server graphql
```

### 5. Тестовый запуск

```bash
npm run start:dev
```

API будет доступен по адресу: `http://localhost:3001`

## 📚 Полезные команды

```bash
# Docker
docker-compose up -d              # Запуск сервисов
docker-compose down               # Остановка сервисов
docker-compose logs -f postgres   # Логи PostgreSQL
docker-compose logs -f redis      # Логи Redis

# Backend
npm run start:dev                # Режим разработки
npm run build                    # Сборка
npm run lint                     # Проверка кода
npm run format                   # Форматирование

# Prisma
npm run prisma:generate          # Генерация клиента
npm run prisma:studio            # Prisma Studio GUI
```

## 🔗 Ссылки

- [TODO.md](TODO.md) - Полный план реализации
- [backend/README.md](backend/README.md) - Документация backend
- [.env.example](backend/.env.example) - Пример переменных окружения

## ⚠️ Возможные проблемы

### Docker не запускается
```bash
# Проверить статус Docker
docker --version
docker-compose --version

# Перезапустить Docker Desktop (Windows/Mac)
```

### Ошибки при npm install
```bash
# Очистить кэш и переустановить
cd backend
rm -rf node_modules package-lock.json
npm install
```

### Prisma ошибки подключения
```bash
# Проверить, что PostgreSQL запущен
docker ps | grep postgres

# Проверить подключение
docker exec -it unmatched-postgres psql -U unmatched -d unmatched
```
