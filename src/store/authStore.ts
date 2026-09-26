import { create } from 'zustand';
import { apolloClient } from '@/lib/apolloClient';
import * as gql from '@/gql/graphql';
import * as tokenStorage from '@/lib/token-storage';

/**
 * Пользовательские данные
 */
export interface User {
  id: string;
  email: string;
  username: string;
  avatar: string | null;
  createdAt?: string;
  settings?: UserSettings;
}

export interface UserSettings {
  theme: string;
  soundEnabled: boolean;
  musicEnabled: boolean;
  language: string;
  profileVisible: boolean;
}

/**
 * Auth response от сервера
 */
interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: {
    id: string;
    email: string;
    username: string;
  };
}

/**
 * Состояние аутентификации
 */
interface AuthState {
  // State
  user: User | null;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  authError: string | null;
  accessToken: string | null;

  // Internal
  _isRefreshing: boolean;
  _refreshPromise: Promise<void> | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshTokens: () => Promise<void>;
  setUser: (user: User | null) => void;
  clearError: () => void;
  fetchMe: () => Promise<void>;
}

/**
 * Auth Store с Zustand
 *
 * Управляет состоянием аутентификации и токенами.
 * Инициализируется из localStorage при создании.
 */
const createAuthStore = () => {
  // Инициализация из localStorage
  const tokens = tokenStorage.getTokens();
  const initialState = {
    user: null as User | null,
    isAuthenticated: false,
    isAuthLoading: !!tokens, // Загрузка если есть токены
    authError: null as string | null,
    accessToken: tokens?.accessToken ?? null,
    _isRefreshing: false,
    _refreshPromise: null as Promise<void> | null,
  };

  return create<AuthState>((set, get) => ({
    ...initialState,

    /**
     * Логин пользователя
     */
    login: async (email: string, password: string) => {
      set({ isAuthLoading: true, authError: null });

      try {
        const { data, errors } = await apolloClient.mutate<{
          login: AuthResponse;
        }>({
          mutation: gql.LoginDocument,
          variables: {
            input: { email, password },
          },
        });

        if (errors?.length) {
          throw new Error(errors[0].message);
        }

        if (!data?.login) {
          throw new Error('Login failed');
        }

        const { accessToken, refreshToken, user } = data.login;

        // Сохраняем токены
        tokenStorage.setTokens({
          accessToken,
          refreshToken,
          expiresAt: tokenStorage.calculateExpiry(),
        });

        set({
          user: {
            ...user,
            avatar: null,
          },
          isAuthenticated: true,
          isAuthLoading: false,
          accessToken,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Login failed';
        set({
          authError: message,
          isAuthLoading: false,
          isAuthenticated: false,
        });
        throw error;
      }
    },

    /**
     * Регистрация пользователя
     */
    register: async (email: string, username: string, password: string) => {
      set({ isAuthLoading: true, authError: null });

      try {
        const { data, errors } = await apolloClient.mutate<{
          register: AuthResponse;
        }>({
          mutation: gql.RegisterDocument,
          variables: {
            input: { email, username, password },
          },
        });

        if (errors?.length) {
          throw new Error(errors[0].message);
        }

        if (!data?.register) {
          throw new Error('Registration failed');
        }

        const { accessToken, refreshToken, user } = data.register;

        // Сохраняем токены
        tokenStorage.setTokens({
          accessToken,
          refreshToken,
          expiresAt: tokenStorage.calculateExpiry(),
        });

        set({
          user: {
            ...user,
            avatar: null,
          },
          isAuthenticated: true,
          isAuthLoading: false,
          accessToken,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Registration failed';
        set({
          authError: message,
          isAuthLoading: false,
          isAuthenticated: false,
        });
        throw error;
      }
    },

    /**
     * Логаут
     */
    logout: async () => {
      try {
        // Вызываем мутацию logout на сервере (для инвалидации токена)
        await apolloClient.mutate({
          mutation: gql.LogoutDocument,
        });
      } catch (error) {
        console.error('Logout mutation failed:', error);
      } finally {
        // Очищаем локальное состояние независимо от результата мутации
        tokenStorage.clearTokens();
        set({
          user: null,
          isAuthenticated: false,
          authError: null,
          accessToken: null,
        });
      }
    },

    /**
     * Обновление токенов (refresh flow)
     *
     * Использует паттерн "single flight" — только один refresh одновременно.
     */
    refreshTokens: async () => {
      const state = get();

      // Если уже идёт refresh, возвращаем существующий promise
      if (state._isRefreshing && state._refreshPromise) {
        return state._refreshPromise;
      }

      const refreshToken = tokenStorage.getRefreshToken();
      if (!refreshToken) {
        // Нет refresh токена — разлогиниваемся
        get().logout();
        return;
      }

      // Создаём promise для refresh
      const refreshPromise = (async () => {
        set({ _isRefreshing: true });

        try {
          const { data, errors } = await apolloClient.mutate<{
            refreshTokens: {
              accessToken: string;
              refreshToken: string;
            };
          }>({
            mutation: gql.RefreshTokensDocument,
            variables: { refreshToken },
          });

          if (errors?.length || !data?.refreshTokens) {
            throw new Error('Token refresh failed');
          }

          const { accessToken, refreshToken: newRefreshToken } = data.refreshTokens;

          // Сохраняем новые токены
          tokenStorage.setTokens({
            accessToken,
            refreshToken: newRefreshToken,
            expiresAt: tokenStorage.calculateExpiry(),
          });

          set({ _isRefreshing: false, _refreshPromise: null, accessToken });
        } catch (error) {
          // Refresh неудался — разлогиниваемся
          console.error('Token refresh failed:', error);
          tokenStorage.clearTokens();
          set({
            user: null,
            isAuthenticated: false,
            accessToken: null,
            _isRefreshing: false,
            _refreshPromise: null,
          });
          throw error;
        }
      })();

      set({ _refreshPromise: refreshPromise });
      return refreshPromise;
    },

    /**
     * Установить пользователя (используется при инициализации)
     */
    setUser: (user: User | null) => {
      set({
        user,
        isAuthenticated: !!user,
        isAuthLoading: false,
      });
    },

    /**
     * Очистить ошибку аутентификации
     */
    clearError: () => {
      set({ authError: null });
    },

    /**
     * Получить данные текущего пользователя
     */
    fetchMe: async () => {
      set({ isAuthLoading: true });

      try {
        const { data, errors } = await apolloClient.query<{
          me: User;
        }>({
          query: gql.MeDocument,
          fetchPolicy: 'network-only',
        });

        if (errors?.length) {
          throw new Error(errors[0].message);
        }

        if (data?.me) {
          set({
            user: data.me,
            isAuthenticated: true,
            isAuthLoading: false,
          });
        }
      } catch (error) {
        console.error('Failed to fetch user:', error);
        set({
          user: null,
          isAuthenticated: false,
          isAuthLoading: false,
        });
      }
    },
  }));
};

export const useAuthStore = createAuthStore();

/**
 * Selector хуки для оптимизации ререндеров
 */
export const useUser = () => useAuthStore((state) => state.user);
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);
export const useIsAuthLoading = () => useAuthStore((state) => state.isAuthLoading);
export const useAuthError = () => useAuthStore((state) => state.authError);

/**
 * Инициализация auth store при старте приложения
 *
 * Должен вызываться в main.tsx перед рендером.
 */
export async function initAuthStore(): Promise<void> {
  const tokens = tokenStorage.getTokens();

  if (tokens) {
    // Есть токены — пробуем получить данные пользователя
    try {
      await useAuthStore.getState().fetchMe();
    } catch {
      // Токен невалиден — очищаем
      tokenStorage.clearTokens();
    }
  } else {
    useAuthStore.getState().setUser(null);
  }
}
