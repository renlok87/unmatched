#!/bin/bash
# Скрипт для запуска проекта в WSL через Docker Compose

# Проверяем, запущены ли мы внутри WSL
if grep -qi microsoft /proc/version 2>/dev/null; then
    # Мы внутри WSL — определяем путь автоматически
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
else
    # Мы в Windows — перенаправляем в WSL
    # Определяем путь к текущей директории в Windows
    WIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # Конвертируем путь Windows в WSL
    PROJECT_DIR=$(wsl -e bash -c "echo \$(wslpath '$(dirname "$WIN_DIR")' 2>/dev/null || echo '/mnt/c/Users/ren/WebstormProjects/unmached/unmached')")

    # Перенаправляем выполнение в WSL
    echo "🔄 Перенаправление в WSL..."
    wsl -d Ubuntu -e bash -c "cd '$PROJECT_DIR' && bash '$(basename "$0")'"
    exit $?
fi

# Проверяем, существует ли директория
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Ошибка: Директория проекта не найдена: $PROJECT_DIR"
    exit 1
fi

# Переходим в директорию проекта
cd "$PROJECT_DIR" || exit 1

echo "🚀 Запуск проекта unmatched в Docker..."
echo "📂 Директория: $PROJECT_DIR"

# Запускаем docker compose
docker compose up -d

# Проверяем статус
echo ""
echo "📊 Статус контейнеров:"
docker compose ps

echo ""
echo "✅ Проект запущен!"
echo ""
echo "🌐 Доступные сервисы:"
echo "   - GraphQL API:    http://localhost:3000/graphql"
echo "   - Health Check:   http://localhost:3000/health"
echo "   - PostgreSQL:     localhost:5432"
echo "   - Redis:          localhost:6379"
echo ""
echo "Для остановки проекта используйте: npm run docker:stop"
