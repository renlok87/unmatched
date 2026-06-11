import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

interface FormState {
  email: string;
  username: string;
  password: string;
  confirmPassword: string;
}

interface FormErrors {
  email?: string;
  username?: string;
  password?: string;
  confirmPassword?: string;
  general?: string;
}

/**
 * RegisterForm компонент
 *
 * Форма регистрации с валидацией.
 * Пароль должен быть не менее 8 символов, содержать буквы и цифры.
 */
export function RegisterForm() {
  const navigate = useNavigate();
  const { register, isAuthLoading, authError, clearError } = useAuthStore();

  const [form, setForm] = useState<FormState>({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
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

    // Username validation
    if (!form.username) {
      newErrors.username = 'Имя пользователя обязательно';
    } else if (form.username.length < 3) {
      newErrors.username = 'Имя пользователя должно быть не менее 3 символов';
    } else if (form.username.length > 20) {
      newErrors.username = 'Имя пользователя должно быть не более 20 символов';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(form.username)) {
      newErrors.username = 'Только буквы, цифры, дефис и подчёркивание';
    }

    // Password validation
    if (!form.password) {
      newErrors.password = 'Пароль обязателен';
    } else if (form.password.length < 8) {
      newErrors.password = 'Пароль должен быть не менее 8 символов';
    } else if (!/[a-zA-Z]/.test(form.password)) {
      newErrors.password = 'Пароль должен содержать хотя бы одну букву';
    } else if (!/[0-9]/.test(form.password)) {
      newErrors.password = 'Пароль должен содержать хотя бы одну цифру';
    }

    // Confirm password validation
    if (!form.confirmPassword) {
      newErrors.confirmPassword = 'Подтвердите пароль';
    } else if (form.password !== form.confirmPassword) {
      newErrors.confirmPassword = 'Пароли не совпадают';
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
      await register(form.email, form.username, form.password);
      // После успешной регистрации перенаправляем
      navigate('/', { replace: true });
    } catch (error) {
      // Ошибка уже записана в authStore.authError
      const message = authError || 'Ошибка регистрации. Возможно, такой email уже занят.';
      setErrors((prev) => ({ ...prev, general: message }));
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
    <div className="auth-form-container">
      <div className="auth-form-card auth-form-card--register">
        <h2 className="auth-form-title">Регистрация</h2>

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {/* Email field */}
          <div className="form-field">
            <label htmlFor="reg-email" className="form-label">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              autoComplete="email"
              className={`form-input ${errors.email ? 'form-input--error' : ''}`}
              value={form.email}
              onChange={handleChange('email')}
              disabled={isSubmitting || isAuthLoading}
            />
            {errors.email && <span className="form-error">{errors.email}</span>}
          </div>

          {/* Username field */}
          <div className="form-field">
            <label htmlFor="reg-username" className="form-label">
              Имя пользователя
            </label>
            <input
              id="reg-username"
              type="text"
              autoComplete="username"
              className={`form-input ${errors.username ? 'form-input--error' : ''}`}
              value={form.username}
              onChange={handleChange('username')}
              disabled={isSubmitting || isAuthLoading}
            />
            {errors.username && <span className="form-error">{errors.username}</span>}
          </div>

          {/* Password field */}
          <div className="form-field">
            <label htmlFor="reg-password" className="form-label">
              Пароль
            </label>
            <input
              id="reg-password"
              type="password"
              autoComplete="new-password"
              className={`form-input ${errors.password ? 'form-input--error' : ''}`}
              value={form.password}
              onChange={handleChange('password')}
              disabled={isSubmitting || isAuthLoading}
            />
            {errors.password && <span className="form-error">{errors.password}</span>}
          </div>

          {/* Confirm password field */}
          <div className="form-field">
            <label htmlFor="reg-confirm-password" className="form-label">
              Подтвердите пароль
            </label>
            <input
              id="reg-confirm-password"
              type="password"
              autoComplete="new-password"
              className={`form-input ${errors.confirmPassword ? 'form-input--error' : ''}`}
              value={form.confirmPassword}
              onChange={handleChange('confirmPassword')}
              disabled={isSubmitting || isAuthLoading}
            />
            {errors.confirmPassword && (
              <span className="form-error">{errors.confirmPassword}</span>
            )}
          </div>

          {/* General error */}
          {errors.general && (
            <div className="form-error form-error--general">{errors.general}</div>
          )}

          {/* Submit button */}
          <button
            type="submit"
            className="form-submit"
            disabled={isSubmitting || isAuthLoading}
          >
            {isSubmitting || isAuthLoading ? 'Регистрация...' : 'Зарегистрироваться'}
          </button>
        </form>

        {/* Link to login */}
        <div className="auth-form-footer">
          Уже есть аккаунт?{' '}
          <a href="/login" className="auth-link">
            Войти
          </a>
        </div>
      </div>
    </div>
  );
}
