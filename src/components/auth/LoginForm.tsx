import { useState, FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

interface FormState {
  email: string;
  password: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  general?: string;
}

/**
 * LoginForm компонент
 *
 * Форма входа с валидацией email и password.
 * После успешного логина перенаправляет на return URL или на главную.
 */
export function LoginForm() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnUrl = searchParams.get('returnUrl') || '/';

  const { login, isAuthLoading, authError, clearError } = useAuthStore();

  const [form, setForm] = useState<FormState>({
    email: '',
    password: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Email validation
    if (!form.email) {
      newErrors.email = 'Email обязателен';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      newErrors.email = 'Некорректный формат email';
    }

    // Password validation
    if (!form.password) {
      newErrors.password = 'Пароль обязателен';
    } else if (form.password.length < 6) {
      newErrors.password = 'Пароль должен быть не менее 6 символов';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    clearError();
    setErrors({});

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      await login(form.email, form.password);
      // После успешного логина перенаправляем
      navigate(returnUrl, { replace: true });
    } catch (error) {
      // Ошибка уже записана в authStore.authError
      setErrors((prev) => ({
        ...prev,
        general: authError || 'Ошибка входа. Проверьте email и пароль.',
      }));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    // Очищаем ошибку поля при изменении
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

return (
    <div className="d-flex justify-center items-center min-h-screen p-4">
      <div className="bg-gray-800 rounded-2xl shadow-2xl p-6 w-full max-w-md">
        <h2 className="text-2xl font-bold text-white mb-6 text-center">Вход в систему</h2>

        <form onSubmit={handleSubmit} className="d-flex flex-column gap-4" noValidate>
          {/* Email field */}
          <div className="input-group">
            <label htmlFor="email" className="input-label">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className={`input ${errors.email ? 'input-error' : ''}`}
              value={form.email}
              onChange={handleChange('email')}
              disabled={isSubmitting || isAuthLoading}
            />
            {errors.email && <span className="input-error">{errors.email}</span>}
          </div>

          {/* Password field */}
          <div className="input-group">
            <label htmlFor="password" className="input-label">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className={`input ${errors.password ? 'input-error' : ''}`}
              value={form.password}
              onChange={handleChange('password')}
              disabled={isSubmitting || isAuthLoading}
            />
            {errors.password && <span className="input-error">{errors.password}</span>}
          </div>

          {/* General error */}
          {errors.general && (
            <div className="text-error text-sm">{errors.general}</div>
          )}

          {/* Submit button */}
          <button
            type="submit"
            className="btn btn-primary btn-md w-full"
            disabled={isSubmitting || isAuthLoading}
          >
            {isSubmitting || isAuthLoading ? 'Вход...' : 'Войти'}
          </button>
        </form>

        {/* Link to registration */}
        <div className="mt-4 text-center text-sm">
          Нет аккаунта?{' '}
          <a href="/register" className="text-accent cursor-pointer hover:underline">
            Зарегистрироваться
          </a>
        </div>
      </div>
    </div>
  );
}
