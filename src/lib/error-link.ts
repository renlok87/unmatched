import { ApolloLink, fromPromise, Observable, Operation, FetchResult } from '@apollo/client';
import { onError } from '@apollo/client/link/error';
import { useAuthStore } from '@/store/authStore';
import { tokenStorage } from '@/lib/token-storage';

/**
 * Проверка, является ли ошибка ошибкой аутентификации
 */
function isAuthError(error: readonly { message?: string; extensions?: Record<string, unknown> }[]): boolean {
  return error.some((err) => {
    const message = err.message?.toLowerCase() || '';
    const code = err.extensions?.code as string | undefined;

    return (
      code === 'UNAUTHENTICATED' ||
      code === 'AUTH_TOKEN_EXPIRED' ||
      code === 'AUTH_INVALID_TOKEN' ||
      message.includes('unauthenticated') ||
      message.includes('token expired') ||
      message.includes('invalid token')
    );
  });
}

/**
 * Error Link для обработки ошибок и автоматического refresh токенов
 *
 * При 401 (UNAUTHENTICATED) запускает flow обновления токена
 * и повторяет оригинальный запрос.
 */
export const errorLink = onError(({ graphQLErrors, networkError, operation, forward }) => {
  // Обработка GraphQL ошибок
  if (graphQLErrors) {
    // Проверяем на ошибки аутентификации
    if (isAuthError(graphQLErrors)) {
      return fromPromise(
        // Проверяем, есть ли refresh токен
        (async () => {
          const refreshToken = tokenStorage.getRefreshToken();

          if (!refreshToken) {
            // Нет refresh токена — разлогиниваемся
            await useAuthStore.getState().logout();
            throw new Error('No refresh token available');
          }

          // Вызываем refresh tokens
          try {
            await useAuthStore.getState().refreshTokens();
          } catch (refreshError) {
            // Refresh неудался — разлогиниваемся
            console.error('Token refresh failed:', refreshError);
            await useAuthStore.getState().logout();
            throw refreshError;
          }
        })()
      ).flatMap(() => {
        // Токен обновлён — повторяем оригинальный запрос
        return forward(operation);
      });
    }
  }

  // Обработка сетевых ошибок
  if (networkError) {
    // AbortError — намеренная отмена запроса (unmount компонента / новый запрос
    // отменяет предыдущий), а НЕ реальная сетевая ошибка. Не шумим в консоль и
    // не запускаем refresh-flow. В dev React StrictMode двойной mount/unmount
    // массово рвёт in-flight fetch'и — без этого фильтра консоль залита красным.
    const isAbort =
      networkError.name === 'AbortError' ||
      /\baborted?\b/i.test(networkError.message ?? '');
    if (isAbort) {
      return;
    }

    console.error('Network error:', networkError);

    // Если это 401, тоже пробуем refresh
    if ('statusCode' in networkError && networkError.statusCode === 401) {
      return fromPromise(
        (async () => {
          const refreshToken = tokenStorage.getRefreshToken();

          if (!refreshToken) {
            await useAuthStore.getState().logout();
            throw new Error('No refresh token available');
          }

          try {
            await useAuthStore.getState().refreshTokens();
          } catch (refreshError) {
            console.error('Token refresh failed:', refreshError);
            await useAuthStore.getState().logout();
            throw refreshError;
          }
        })()
      ).flatMap(() => forward(operation));
    }
  }
});

/**
 * Альтернативная реализация через ApolloLink для более тонкого контроля
 */
export class AuthErrorLink extends ApolloLink {
  request(operation: Operation, forward: () => Observable<FetchResult>): Observable<FetchResult> {
    return forward().map((response: any) => {
      const context = operation.getContext();

      // Проверяем статус ответа
      const responseStatus = context.response?.status as number | undefined;

      if (responseStatus === 401) {
        // 401 — запускаем refresh flow
        console.warn('Received 401, attempting token refresh');

        useAuthStore
          .getState()
          .refreshTokens()
          .catch(() => {
            // Refresh неудался — logout
            useAuthStore.getState().logout();
          });
      }

      return response;
    });
  }
}
