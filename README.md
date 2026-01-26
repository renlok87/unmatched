# Unmatched Digital Edition

> Цифровая версия настольной карточной игры Unmatched

![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue)
![React](https://img.shields.io/badge/React-18-blue)
![Vite](https://img.shields.io/badge/Vite-6.0-purple)
![NestJS](https://img.shields.io/badge/NestJS-10-red)
![Prisma](https://img.shields.io/badge/Prisma-6-2D3748)
![pnpm](https://img.shields.io/badge/pnpm-monorepo-F69220)

## 🎮 О игре

**Unmatched** — это настольная карточная игра с асимметричными героями, уникальными колодами и тактическим боем. Каждый герой имеет свои способности и стиль игры.

## 🚀 Быстрый старт

### Полный запуск проекта (Frontend + Backend)

**⚠️ Важно**: На Windows убедитесь, что локальный PostgreSQL не использует порт 5432/5433, или измените порт в `.env` файлах.

```bash
# 1. Запуск Docker сервисов (PostgreSQL на порту 5433, Redis)
docker-compose up -d

# 2. Применение миграций Prisma
cd backend
npx prisma db push

# 3. Запуск Backend (NestJS) - в терминале 1
cd backend
npm run start:dev

# 4. Запуск Frontend (React + Vite) - в терминале 2
npm run dev
```

**Доступные сервисы:**
- 🎮 Frontend: [http://localhost:5173](http://localhost:5173)
- 🔧 Backend API: [http://localhost:3001](http://localhost:3001)
- 🐘 PostgreSQL: localhost:5433
- 🔴 Redis: localhost:6379

### Только Frontend (Hot-seat режим)

```bash
npm install
npm run dev
```

Откройте [http://localhost:5173](http://localhost:5173)

### Backend (Онлайн-мультиплеер)

**ВНИМАНИЕ**: Бэкенд в разработке. См. [QUICKSTART.md](QUICKSTART.md) для инструкций.

GraphQL Playground: [http://localhost:3001/graphql](http://localhost:3001/graphql)

**Статус реализации**: См. [TODO.md](TODO.md)

### Остановка проекта

```bash
# Остановка Docker сервисов
docker-compose down

# Остановка Docker с удалением данных
docker-compose down -v

# Остановка фоновых процессов (Ctrl+C в терминалах)
```

### Особенности реализации

- **Zone-based движение** — бойцы перемещаются по цветным зонам
- **Система боя** — атака и защита с одновременным вскрытием карт
- **Уникальные герои** — Ms. Marvel, Daredevil и другие
- **Hot-seat режим** — игра вдвоём на одном устройстве

## 📁 Структура проекта

```
unmached/
├── src/                         # Frontend (React + Vite)
│   ├── core/                    # Игровой движок (чистая логика)
│   │   ├── models/              # TypeScript типы и модели
│   │   ├── engine/              # Игровая логика
│   │   └── data/                # Данные героев и досок
│   ├── store/                   # Zustand state management
│   ├── components/              # React компоненты UI
│   └── hooks/                   # Custom React hooks
├── backend/                     # Backend (NestJS)
│   ├── src/                     # Исходный код
│   │   ├── auth/                # Auth модуль
│   │   ├── content/             # Content модуль
│   │   ├── game/                # Game модуль
│   │   ├── database/            # Prisma сервис
│   │   ├── redis/               # Redis модуль
│   │   └── graphql/             # GraphQL схема
│   ├── prisma/                  # Prisma схема и миграции
│   └── .env                     # Переменные окружения
├── docker-compose.yml           # Docker сервисы (PostgreSQL, Redis)
└── .env                         # Переменные окружения для Docker
```

## 🎯 Реализованные механики

- ✅ 2 действия за ход (Maneuver, Scheme, Attack)
- ✅ Zone-based перемещение по доске
- ✅ Система боя с атакой и защитой
- ✅ 2 героя: Ms. Marvel и Daredevil
- ✅ 1 доска: Cobble City

## 📋 TODO

См. [TODO.md](TODO.md) для полного списка задач.

## 🛠️ Технологии

### Frontend
- **React 18** — UI библиотека
- **TypeScript** — типизация
- **Vite** — сборщик
- **Zustand** — state management
- **CSS Modules** — стилизация

### Backend
- **NestJS** — фреймворк для создания API
- **GraphQL** — API с подписками (Apollo Server)
- **Prisma** — ORM для PostgreSQL
- **Redis** — кеширование, pub/sub и состояние игр
- **JWT** — аутентификация
- **Docker** — контейнеризация сервисов (PostgreSQL, Redis)

## 📄 Лицензия

MIT

## 👏 Acknowledgments

- [Restoration Games](https://restorationgames.com/) — создатели Unmatched
- [Unmatched Cards](https://unmatched.cards/) — база данных карт
