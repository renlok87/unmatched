import { ApolloClient, InMemoryCache, HttpLink, split, ApolloLink } from '@apollo/client';
import { getMainDefinition } from '@apollo/client/utilities';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { createClient as createWsClient } from 'graphql-ws';
import { APOLLO_URI, APOLLO_WS_URI } from '@/env';
import { retryLink } from './retry-link';
import { authLink } from './auth-link';
import { errorLink } from './error-link';
import { tokenStorage } from './token-storage';

/**
 * WebSocket клиент для real-time подписок (game updates, matchmaking, presence)
 *
 * Поддерживает динамическое обновление токена через connectionParams.
 */
const wsClient = createWsClient({
  url: APOLLO_WS_URI,
  connectionParams: () => {
    // Получаем токен из localStorage (authStore может быть недоступен в момент создания)
    const token = tokenStorage.getAccessToken();
    return {
      authorization: token ? `Bearer ${token}` : '',
    };
  },
  on: {
    connected: () => console.log('🟢 WebSocket connected'),
    error: (error) => console.error('🔴 WebSocket error:', error),
    closed: () => console.log('⚫ WebSocket closed'),
  },
  // Lazy reconnect для лучшей обработки потери соединения
  lazy: true,
  // Количество попыток переподключения
  retryAttempts: 5,
  // Задержка между попытками
  onNonLazyError: () => console.warn('WebSocket non-lazy error'),
});

const wsLink = new GraphQLWsLink(wsClient);

/**
 * HTTP клиент для queries и mutations
 */
const httpLink = new HttpLink({
  uri: APOLLO_URI,
  credentials: 'include',
});

/**
 * Split-линк: используем WebSocket для подписок, HTTP для остального
 */
const splitLink = split(
  ({ query }) => {
    const definition = getMainDefinition(query);
    return (
      definition.kind === 'OperationDefinition' &&
      definition.operation === 'subscription'
    );
  },
  wsLink,
  httpLink,
);

/**
 * Полная цепочка Apollo Links
 *
 * Порядок критичен:
 * 1. retryLink — сначала повторяем неудачные запросы
 * 2. authLink — добавляем токен к каждому запросу
 * 3. errorLink — обрабатываем ошибки и запускаем refresh
 * 4. splitLink — роутинг между HTTP и WebSocket
 *
 * Поток при 401 ошибке:
 * 1. errorLink перехватывает ошибку
 * 2. Запускает refreshTokens() в authStore
 * 3. authLink получает новый токен
 * 4. retryLink повторяет оригинальный запрос
 */
const linkChain = ApolloLink.from([
  retryLink,
  authLink,
  errorLink,
  splitLink,
]);

/**
 * Apollo Client с поддержкой:
 * - Queries & Mutations через HTTP
 * - Subscriptions через WebSocket
 * - Автоматический retry с backoff
 * - Token refresh на 401
 * - Автоматическая кэшизация с типизацией
 */
export const apolloClient = new ApolloClient({
  link: linkChain,
  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          // Оптимистичные обновления для игр
          games: {
            merge(_, incoming) {
              return incoming;
            },
          },
          game: {
            merge(_, incoming) {
              return incoming;
            },
          },
          gameState: {
            merge(_, incoming) {
              return incoming;
            },
          },
        },
      },
    },
  }),
  defaultOptions: {
    watchQuery: {
      errorPolicy: 'all',
      fetchPolicy: 'cache-and-network',
    },
    query: {
      errorPolicy: 'all',
    },
    mutate: {
      errorPolicy: 'all',
    },
  },
  // Логирование в development
  ...(import.meta.env.DEV && {
    devtools: { enabled: true },
  }),
});

/**
 * Хук для получения токена из Apollo context (для авторизованных запросов)
 * @deprecated Используйте authLink для автоматической инъекции токена
 */
export function getAuthHeader(): { authorization?: string } {
  const token = tokenStorage.getAccessToken();
  return token ? { authorization: `Bearer ${token}` } : {};
}

/**
 * Переподключение WebSocket с новым токеном
 *
 * Используется после успешного refresh токена.
 */
export function reconnectWebSocket(): void {
  // graphql-ws автоматически переподключается при вызове connectionParams
  // Достаточно вызвать terminate чтобы закрыть текущее соединение
  wsClient.terminate();
}

/**
 * Экспорт wsClient для использования в hooks (например, useGameSync)
 */
export { wsClient };
