# 🎴 Unmatched Card Game - Design System & Digital Edition

> Полный Design System и цифровая версия настольной карточной игры Unmatched

![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue)
![React](https://img.shields.io/badge/React-18-blue)
![Vite](https://img.shields.io/badge/Vite-6.0-purple)
![NestJS](https://img.shields.io/badge/NestJS-10-red)
![Prisma](https://img.shields.io/badge/Prisma-6-2D3748)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![Figma](https://img.shields.io/badge/Design%20System-Figma-purple)

---

## 📋 Обзор проекта

Этот проект содержит:
1. **🎨 Полный Design System** для создания карточной игры (88 героев, ~1,550+ ассетов)
2. **💻 Цифровая версия** игры на React + NestJS

### 📊 Статистика Design System

| Показатель | Значение |
|------------|----------|
| **Героев** | 88 |
| **Изображений** | ~1,550+ |
| **Фракций** | 5+ |
| **Шаблонов карточек** | 2+ |
| **Цветов в палитре** | 16+ |

---

## 🎨 Design System (Новое!)

### 📁 Документация и файлы

```
unmached/
├── DESIGN_SYSTEM.md              # 📖 Полная спецификация Design System
├── design-system-preview.html    # 🎨 Интерактивный HTML-прототип
├── FIGMA_SETUP_GUIDE.md          # 🎨 Инструкция по настройке Figma
├── figma-automation-script.js    # ⚡ Скрипт автоматизации Figma
└── ASSETS_MANIFEST.md            # 📦 Манифест всех ассетов
```

### 🚀 Быстрый старт с Design System

**Вариант 1: Просмотр (Простой)**
```bash
# Откройте в браузере
open design-system-preview.html
```

**Вариант 2: Работа в Figma (Рекомендуется)**
1. Откройте `FIGMA_SETUP_GUIDE.md` — пошаговая инструкция
2. Включите MCP сервер: `Figma → Preferences → Enable Dev Mode MCP Server`
3. Следуйте инструкциям для создания компонентов

### 🎨 Ключевые элементы

| Элемент | Значение |
|---------|----------|
| **Размер карточки** | 300 × 420 px (1:1.4) |
| **Основные цвета** | `#FFD700`, `#6B4C9A`, `#DC143C`, `#1E3A8A` |
| **Шрифты** | Impact (заголовки), Arial (текст) |
| **Отступы** | 4, 8, 16, 24, 32 px |

### 👥 Топ-5 героев для примеров

1. **Oda Nobunaga** 🇯🇵 — Самурай, японская эстетика
2. **Ms. Marvel** 💪 — Супергероиня, энергетические способности
3. **Geralt of Rivia** ⚔️ — Ведьмак, знаки, мечи
4. **Sun Wukong** 🐒 — Обезьяна-король, китайская мифология
5. **Dracula** 🧛 — Вампир, готический хоррор

Подробнее в [`ASSETS_MANIFEST.md`](./ASSETS_MANIFEST.md)

---

## 🎮 О игре

**Unmatched** — это настольная карточная игра с асимметричными героями, уникальными колодами и тактическим боем. Каждый герой имеет свои способности и стиль игры.

## 🚀 Быстрый старт

### Запуск через WSL/Docker (рекомендуется)

Все сервисы (Backend + PostgreSQL + Redis) запускаются одной командой:

```bash
# Запуск всех контейнеров
npm run docker:start

# Проверка статуса
npm run docker:ps

# Просмотр логов
npm run docker:logs

# Перезапуск
npm run docker:restart

# Остановка
npm run docker:stop
```

**Доступные сервисы после запуска:**
- 🔧 GraphQL API: [http://localhost:3000/graphql](http://localhost:3000/graphql)
- ❤️ Health Check: [http://localhost:3000/health](http://localhost:3000/health)
- 🐘 PostgreSQL: `localhost:5433` (внутри контейнера: 5432)
- 🔴 Redis: `localhost:6379`

### Запуск Frontend

Откройте отдельный терминал для Frontend:

```bash
npm run dev
```

Frontend будет доступен по адресу: [http://localhost:5173](http://localhost:5173)

### 👤 Тестовые аккаунты

Для быстрого тестирования используйте готовые аккаунты:

| Email | Username | Пароль | ELO |
|-------|----------|--------|-----|
| `test1@unmatched.com` | TestPlayer1 | `password123` | 1200 |
| `test2@unmatched.com` | TestPlayer2 | `password123` | 1200 |

> **Примечание:** Аккаунты созданы через SQL. Их можно пересоздать командой:
> ```bash
> # Пересоздание тестовых пользователей
> docker exec unmatched-postgres psql -U unmatched -d unmatched -f scripts/create-test-users.sql
> ```

### Ручной запуск (для разработки)

```bash
# 1. Запуск Docker сервисов (PostgreSQL, Redis)
docker-compose up -d

# 2. Применение миграций Prisma
cd backend
npx prisma db push

# 3. (Опционально) Заполнение БД тестовыми данными
cd backend
npx prisma db seed

# 4. Запуск Backend (NestJS) - в терминале 1
cd backend
npm run start:dev

# 5. Запуск Frontend (React + Vite) - в терминале 2
npm run dev
```

> **Примечание по портам:**
> - PostgreSQL проброшен на хост как `localhost:5433` (чтобы избежать конфликтов на Windows)
> - Внутри docker-сети backend подключается к postgres через порт 5432
> - В `backend/.env` указан `localhost:5433` для локальной разработки

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
│   │   ├── auth/                # Auth модуль (JWT)
│   │   ├── users/               # Users модуль
│   │   ├── games/               # Games модуль
│   │   ├── game-engine/         # Игровой движок
│   │   ├── lobby/               # Лобби
│   │   ├── content/             # Content модуль (герои)
│   │   ├── database/            # Prisma сервис
│   │   ├── redis/               # Redis модуль
│   │   ├── graphql/             # GraphQL схема
│   │   └── health/              # Health checks
│   ├── prisma/                  # Prisma схема и миграции
│   └── Dockerfile               # Docker образ для backend
├── scripts/                     # Скрипты для WSL/Docker
│   ├── start-wsl.sh             # Запуск проекта
│   ├── stop-wsl.sh              # Остановка проекта
│   └── restart-wsl.sh           # Перезапуск проекта
├── docker-compose.yml           # Docker сервисы (PostgreSQL, Redis)
└── package.json                 # NPM скрипты
```

## 🎯 Реализованные механики

- ✅ 2 действия за ход (Maneuver, Scheme, Attack)
- ✅ Zone-based перемещение по доске
- ✅ Система боя с атакой и защитой
- ✅ 2 героя: Ms. Marvel и Daredevil
- ✅ 1 доска: Cobble City

## 🛠️ Технологии

### Frontend
- **React 18** — UI библиотека
- **TypeScript** — типизация
- **Vite** — сборщик
- **Zustand** — state management
- **CSS Modules** — стилизация

### Backend
- **NestJS** — фреймворк для создания API
- **GraphQL** — API с подписками (Apollo Server + @as-integrations/express5)
- **Prisma** — ORM для PostgreSQL
- **Redis** — кеширование, pub/sub и состояние игр
- **BullMQ** — очереди задач для фоновых операций
- **JWT** — аутентификация
- **Docker** — контейнеризация сервисов

## 📋 NPM скрипты

| Команда | Описание |
|---------|----------|
| `npm run dev` | Запуск Frontend (Vite) |
| `npm run build` | Сборка Frontend |
| `npm run test` | Запуск тестов (Vitest) |
| `npm run docker:start` | Запуск Docker контейнеров |
| `npm run docker:stop` | Остановка Docker контейнеров |
| `npm run docker:restart` | Перезапуск Docker контейнеров |
| `npm run docker:logs` | Просмотр логов контейнеров |
| `npm run docker:ps` | Статус контейнеров |

## 📄 Лицензия

MIT

## 👏 Acknowledgments

- [Restoration Games](https://restorationgames.com/) — создатели Unmatched
- [Unmatched Cards](https://unmatched.cards/) — база данных карт
