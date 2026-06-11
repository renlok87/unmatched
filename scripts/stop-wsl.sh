#!/bin/bash
# Скрипт для остановки проекта в WSL

# Проверяем, запущены ли мы внутри WSL
if grep -qi microsoft /proc/version 2>/dev/null; then
    # Мы внутри WSL — определяем путь автоматически
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
else
    # Мы в Windows — перенаправляем в WSL
    WIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR=$(wsl -e bash -c "echo \$(wslpath '$(dirname "$WIN_DIR")' 2>/dev/null || echo '/mnt/c/Users/ren/WebstormProjects/unmached/unmached')")

    echo "🔄 Перенаправление в WSL..."
    wsl -d Ubuntu -e bash -c "cd '$PROJECT_DIR' && bash '$(basename "$0")'"
    exit $?
fi

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Ошибка: Директория проекта не найдена: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR" || exit 1

echo "🛑 Остановка проекта unmatched..."
docker compose down

echo ""
echo "✅ Проект остановлен!"
