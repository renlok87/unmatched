import type { AuthProvider } from '@refinedev/core';

const BACKEND_URL = (import.meta as any).env?.VITE_BACKEND_URL || 'http://localhost:3000';

interface LoginResponse {
  login: {
    accessToken: string;
    refreshToken: string;
    user: {
      id: string;
      email: string;
      username: string;
      role: string;
    };
  };
}

interface RefreshTokenResponse {
  refreshTokens: {
    accessToken: string;
    refreshToken: string;
  };
}

interface MeResponse {
  me: {
    id: string;
    email: string;
    username: string;
    role: string;
    avatar?: string;
  } | null;
}

const refreshToken = async (): Promise<string | null> => {
  const refreshTokenValue = localStorage.getItem('refreshToken');
  if (!refreshTokenValue) return null;

  try {
    const response = await fetch(`${BACKEND_URL}/graphql`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `
          mutation RefreshToken($refreshToken: String!) {
            refreshTokens(refreshToken: $refreshToken) {
              accessToken
              refreshToken
            }
          }
        `,
        variables: { refreshToken: refreshTokenValue },
      }),
    });

    const result = await response.json();
    const { data, errors } = result as {
      data?: RefreshTokenResponse;
      errors?: any[];
    };

    if (errors || !data?.refreshTokens) {
      throw new Error('Failed to refresh token');
    }

    localStorage.setItem('accessToken', data.refreshTokens.accessToken);
    localStorage.setItem('refreshToken', data.refreshTokens.refreshToken);

    return data.refreshTokens.accessToken;
  } catch {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    return null;
  }
};

const fetchMe = async (token: string): Promise<MeResponse['me']> => {
  try {
    const response = await fetch(`${BACKEND_URL}/graphql`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        query: `
          query Me {
            me { id email username role avatar }
          }
        `,
      }),
    });

    const result = await response.json();
    const data = result.data as MeResponse | undefined;
    return data?.me || null;
  } catch {
    return null;
  }
};

const getIdentity = async () => {
  const token = localStorage.getItem('accessToken');
  if (!token) return null;

  const me = await fetchMe(token);
  if (me) return me;

  const newToken = await refreshToken();
  if (newToken) {
    return fetchMe(newToken);
  }
  return null;
};

const getPermissions: AuthProvider['getPermissions'] = async () => {
  const identity = await getIdentity();
  if (identity && typeof identity === 'object' && 'role' in identity) {
    return (identity as { role: string }).role;
  }
  return null;
};

export const authProvider: AuthProvider = {
  login: async ({ email, password }) => {
    try {
      const response = await fetch(`${BACKEND_URL}/graphql`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `
            mutation Login($email: String!, $password: String!) {
              login(input: { email: $email, password: $password }) {
                accessToken
                refreshToken
                user { id email username role }
              }
            }
          `,
          variables: { email, password },
        }),
      });

      const result = await response.json();
      const { data, errors } = result as {
        data?: LoginResponse;
        errors?: any[];
      };

      if (errors || !data?.login) {
        return {
          success: false,
          error: {
            name: 'LoginError',
            message: errors?.[0]?.message || 'Invalid email or password',
          },
        };
      }

      localStorage.setItem('accessToken', data.login.accessToken);
      localStorage.setItem('refreshToken', data.login.refreshToken);

      return {
        success: true,
        redirectTo: '/',
      };
    } catch (error) {
      return {
        success: false,
        error: {
          name: 'NetworkError',
          message: 'Connection failed. Is the backend running?',
        },
      };
    }
  },

  logout: async () => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      try {
        await fetch(`${BACKEND_URL}/graphql`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            query: `
              mutation Logout {
                logout
              }
            `,
          }),
        });
      } catch (error) {
        console.error('Logout API call failed:', error);
      }
    }
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    return { success: true, redirectTo: '/login' };
  },

  check: async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
      return { authenticated: false, redirectTo: '/login' };
    }

    const me = await fetchMe(token);
    if (me) {
      return { authenticated: true };
    }

    const newToken = await refreshToken();
    if (newToken) {
      const refreshedMe = await fetchMe(newToken);
      if (refreshedMe) {
        return { authenticated: true };
      }
    }

    return { authenticated: false, redirectTo: '/login' };
  },

  getIdentity,
  getPermissions,

  onError: async (error) => {
    const isAuthError =
      error?.graphQLErrors?.some((e: any) =>
        ['UNAUTHENTICATED', 'FORBIDDEN'].includes(e?.extensions?.code),
      ) ||
      error?.response?.status === 401 ||
      error?.status === 401;

    if (isAuthError) {
      const newToken = await refreshToken();
      if (newToken) {
        return {};
      }
      return { logout: true };
    }
    return { error };
  },
};
