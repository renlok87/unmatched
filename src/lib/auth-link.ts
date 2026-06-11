import { setContext } from '@apollo/client/link/context';
import { useAuthStore } from '@/store/authStore';
import { tokenStorage } from '@/lib/token-storage';

/**
 * Auth Link для инъекции токена в заголовки
 *
 * Добавляет authorization header к каждому запросу.
 * Токен берётся из authStore или напрямую из localStorage.
 */
export const authLink = setContext((_, { headers }) => {
  // Пытаемся получить токен из authStore (для инициализованного состояния)
  const authState = useAuthStore.getState();

  // Если store не инициализирован или идёт refresh, берём из localStorage
  const token =
    authState?.accessToken ||
    tokenStorage.getAccessToken() ||
    '';

  return {
    headers: {
      ...headers,
      authorization: token ? `Bearer ${token}` : '',
    },
  };
});
