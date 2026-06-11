#!/bin/bash

echo "Starting test environment..."

# Запуск Docker контейнеров для тестов
docker-compose -f docker-compose.test.yml up -d

# Ожидание запуска БД
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Запуск миграций
echo "Running database migrations..."
npx prisma migrate reset --force --skip-generate

# Запуск E2E тестов
echo "Running E2E tests..."
npm run test:e2e

# Остановка контейнеров
echo "Stopping test containers..."
docker-compose -f docker-compose.test.yml down

echo "Tests completed!"