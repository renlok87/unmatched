/**
 * Конфигурация окружения для фронтенда
 *
 * Значения по умолчанию для локальной разработки
 */

export const APOLLO_URI = import.meta.env.VITE_API_URL || 'http://localhost:3000/graphql';
export const APOLLO_WS_URI = import.meta.env.VITE_WS_URL || 'ws://localhost:3000/graphql';
