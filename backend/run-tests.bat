@echo off
echo Starting test environment...

REM Запуск Docker контейнеров для тестов
docker-compose -f docker-compose.test.yml up -d

REM Ожидание запуска БД
echo Waiting for PostgreSQL to be ready...
timeout /t 10 /nobreak

REM Запуск миграций
echo Running database migrations...
call npx prisma migrate reset --force --skip-generate

REM Запуск E2E тестов
echo Running E2E tests...
call npm run test:e2e

REM Остановка контейнеров
echo Stopping test containers...
docker-compose -f docker-compose.test.yml down

echo Tests completed!