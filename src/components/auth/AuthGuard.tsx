import { Navigate, useLocation } from 'react-router-dom';
import { useIsAuthenticated, useIsAuthLoading } from '@/store/authStore';

interface AuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  redirectTo?: string;
}

/**
 * AuthGuard компонент
 *
 * Защищает маршруты, требующие аутентификации.
 * Если пользователь не авторизован — перенаправляет на страницу логина.
 * Сохраняет текущий URL для возврата после успешного входа.
 *
 * @example
 * ```tsx
 * <AuthGuard>
 *   <DashboardPage />
 * </AuthGuard>
 * ```
 *
 * @example с кастомным fallback
 * ```tsx
 * <AuthGuard fallback={<CustomLoading />}>
 *   <DashboardPage />
 * </AuthGuard>
 * ```
 */
export function AuthGuard({
  children,
  fallback,
  redirectTo = '/login',
}: AuthGuardProps) {
  const isAuthenticated = useIsAuthenticated();
  const isLoading = useIsAuthLoading();
  const location = useLocation();

  // Сохраняем текущий путь для возврата после логина
  const returnUrl = encodeURIComponent(location.pathname + location.search);

  // Показываем loading пока проверяем auth
  if (isLoading) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" />
        <p>Загрузка...</p>
      </div>
    );
  }

  // Не авторизован — редирект на login
  if (!isAuthenticated) {
    return <Navigate to={`${redirectTo}?returnUrl=${returnUrl}`} replace />;
  }

  // Авторизован — рендерим дочерние компоненты
  return <>{children}</>;
}

/**
 * HOC версия AuthGuard для классовых компонентов или для использования в маршрутах
 *
 * @example
 * ```tsx
 * const ProtectedPage = withAuthGuard(DashboardPage);
 * ```
 */
export function withAuthGuard<P extends object>(
  Component: React.ComponentType<P>,
  options?: Omit<AuthGuardProps, 'children'>
) {
  return function ProtectedComponent(props: P) {
    return (
      <AuthGuard {...options}>
        <Component {...props} />
      </AuthGuard>
    );
  };
}

/**
 * Hook для использования AuthGuard логики внутри компонентов
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { canAccess, redirectToLogin } = useAuthGuard();
 *
 *   useEffect(() => {
 *     if (!canAccess) {
 *       redirectToLogin();
 *     }
 *   }, [canAccess, redirectToLogin]);
 *
 *   return <div>Protected content</div>;
 * }
 * ```
 */
export function useAuthGuard() {
  const isAuthenticated = useIsAuthenticated();
  const isLoading = useIsAuthLoading();
  const location = useLocation();

  const canAccess = isAuthenticated && !isLoading;

  const redirectToLogin = () => {
    const returnUrl = encodeURIComponent(location.pathname + location.search);
    window.location.href = `/login?returnUrl=${returnUrl}`;
  };

  return {
    canAccess,
    isLoading,
    isAuthenticated,
    redirectToLogin,
  };
}

/**
 * Обратный Guard — для маршрутов, доступных только НЕавторизованным пользователям
 * (например, страницы логина и регистрации)
 *
 * @example
 * ```tsx
 * <PublicOnlyGuard redirectTo="/">
 *   <LoginPage />
 * </PublicOnlyGuard>
 * ```
 */
export function PublicOnlyGuard({
  children,
  redirectTo = '/',
}: {
  children: React.ReactNode;
  redirectTo?: string;
}) {
  const isAuthenticated = useIsAuthenticated();
  const isLoading = useIsAuthLoading();

  if (isLoading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  return <>{children}</>;
}
