import { RetryLink } from '@apollo/client/link/retry';

/**
 * Retry Link с экспоненциальным backoff
 *
 * Повторяет запросы при сетевых ошибках и retryable GraphQL ошибках.
 */
export const retryLink = new RetryLink({
  /**
   * Задержка между попытками с экспоненциальным backoff
   */
  delay: {
    initial: 300, // 300ms для первой попытки
    max: 10000, // Максимум 10 секунд
    jitter: true, // Случайный разброс для предотвращения thundering herd
  },

  /**
   * Условия повтора
   */
  attempts: {
    max: 3, // Максимум 3 попытки
    retryIf: (error, operation) => {
      // Не повторяем мутации (кроме особых случаев)
      if (operation.operationName === 'Mutation') {
        return false;
      }

      // Повторяем при сетевых ошибках
      if (!error) return false;
      if (error.networkError) return true;

      // Проверяем GraphQL errors на retryable коды
      const graphQLErrors = error.graphQLErrors;
      if (!graphQLErrors?.length) return false;

      return graphQLErrors.some((err: any) => {
        const message = err.message?.toLowerCase() || '';
        const extensions = err.extensions as Record<string, unknown> | undefined;

        // Retryable ошибки
        const retryableCodes = [
          'SERVICE_UNAVAILABLE',
          'NETWORK_ERROR',
          'TIMEOUT',
          'INTERNAL_SERVER_ERROR',
          'DATABASE_ERROR',
        ];

        const code = extensions?.code as string | undefined;

        return (
          retryableCodes.includes(code || '') ||
          message.includes('timeout') ||
          message.includes('network') ||
          message.includes('service unavailable')
        );
      });
    },
  },
});
