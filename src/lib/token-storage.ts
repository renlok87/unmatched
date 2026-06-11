/**
 * Безопасное хранилище токенов аутентификации.
 * Использует localStorage с префиксом для избежания коллизий.
 */

const STORAGE_PREFIX = 'unmached_';
const ACCESS_TOKEN_KEY = `${STORAGE_PREFIX}access_token`;
const REFRESH_TOKEN_KEY = `${STORAGE_PREFIX}refresh_token`;
const TOKEN_EXPIRY_KEY = `${STORAGE_PREFIX}token_expiry`;

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

/**
 * Получить сохранённые токены
 */
export function getTokens(): AuthTokens | null {
  try {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    const expiresAtStr = localStorage.getItem(TOKEN_EXPIRY_KEY);

    if (!accessToken || !refreshToken || !expiresAtStr) {
      return null;
    }

    const expiresAt = parseInt(expiresAtStr, 10);

    // Проверяем истечение срока действия
    if (Date.now() >= expiresAt) {
      clearTokens();
      return null;
    }

    return { accessToken, refreshToken, expiresAt };
  } catch {
    // localStorage может быть недоступен (private mode и т.д.)
    return null;
  }
}

/**
 * Сохранить токены
 */
export function setTokens(tokens: AuthTokens): void {
  try {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
    localStorage.setItem(TOKEN_EXPIRY_KEY, tokens.expiresAt.toString());
  } catch (error) {
    console.error('Failed to save tokens to localStorage:', error);
  }
}

/**
 * Очистить токены (logout)
 */
export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
  } catch (error) {
    console.error('Failed to clear tokens from localStorage:', error);
  }
}

/**
 * Получить access токен
 */
export function getAccessToken(): string | null {
  const tokens = getTokens();
  return tokens?.accessToken ?? null;
}

/**
 * Получить refresh токен
 */
export function getRefreshToken(): string | null {
  const tokens = getTokens();
  return tokens?.refreshToken ?? null;
}

/**
 * Проверить, токен скоро истечёт (в течение 5 минут)
 */
export function isTokenExpiringSoon(): boolean {
  const tokens = getTokens();
  if (!tokens) return false;

  const fiveMinutes = 5 * 60 * 1000;
  return tokens.expiresAt - Date.now() < fiveMinutes;
}

/**
 * Проверить валидность токена
 */
export function isTokenValid(): boolean {
  return getTokens() !== null;
}

/**
 * Вычислить время истечения токена (по умолчанию 1 час)
 */
export function calculateExpiry(expiresInMs: number = 60 * 60 * 1000): number {
  return Date.now() + expiresInMs;
}

/**
 * Объект tokenStorage для совместимости с существующим кодом
 */
export const tokenStorage = {
  getTokens,
  setTokens,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  isTokenExpiringSoon,
  isTokenValid,
  calculateExpiry,
} as const;
