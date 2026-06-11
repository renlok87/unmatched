# Портовая схема Unmatched

Все порты зафиксированы и не должны изменяться.

## Схема

| Сервис | Порт | URL | Конфигурация |
|--------|------|-----|--------------|
| **Backend** | 3000 | http://localhost:3000 | `backend/.env: PORT=3000` |
| **GraphQL API** | 3000 | http://localhost:3000/graphql | `backend/.env: GRAPHQL_PATH=/graphql` |
| **Frontend** | 5173 | http://localhost:5173 | `vite.config.ts: server.port=5173` (strictPort) |
| **Admin Panel** | 5174 | http://localhost:5174 | `admin/vite.config.ts: server.port=5174` (strictPort) |
| **PostgreSQL** | 5432 | localhost:5432 | Docker/системная установка |
| **Redis** | 6379 | localhost:6379 | Docker/системная установка |

## CORS Origins

Backend разрешает запросы только с:
- `http://localhost:5173` - Main frontend
- `http://localhost:5174` - Admin panel

## Запуск сервисов

```bash
# Backend (порт 3000)
cd backend
npm run start:dev

# Frontend (порт 5173)
npm run dev

# Admin Panel (порт 5174)
cd admin
npm run dev
```

## Изменение портов

Если нужно изменить порт - обновите:
1. `.env` файл сервиса
2. `vite.config.ts` (для фронтенда)
3. CORS настройки в `backend/src/main.ts`
4. Этот документ
