#!/bin/sh
set -e

echo "🔄 Checking Prisma schema synchronization..."

# Применяем изменения схемы БД (безопасная операция)
npx prisma db push --skip-generate --accept-data-loss

echo "✅ Database schema synchronized"

# Генерируем Prisma Client на случай изменений
npx prisma generate

echo "🚀 Starting application..."

# Запускаем основное приложение (заменяет текущий процесс)
exec npm run start:prod
