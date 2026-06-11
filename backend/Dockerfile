FROM node:20-alpine

WORKDIR /app

# Устанавливаем зависимости для сборки нативных модулей
RUN apk add --no-cache python3 make g++ git

# Копируем только package files сначала
COPY package*.json ./

# Устанавливаем зависимости
RUN npm ci

# Копируем исходный код
COPY . .

# Пересобираем нативные модули (важно!)
RUN npm rebuild

# Генерируем Prisma Client
RUN npx prisma generate

# Сборка TypeScript проекта
RUN npm run build

# Копируем entrypoint скрипт и конвертируем CRLF в LF
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port
EXPOSE 3000

# Запуск через entrypoint (автоматически применит Prisma изменения)
ENTRYPOINT ["docker-entrypoint.sh"]
