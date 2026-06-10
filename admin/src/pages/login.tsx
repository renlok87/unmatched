import { useLogin, useIsAuthenticated } from '@refinedev/core';
import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Alert } from 'antd';

export const LoginPage = () => {
  const { mutate: login, isPending, error, data } = useLogin();
  const { data: isAuthenticated } = useIsAuthenticated();

  const [email, setEmail] = useState(import.meta.env.DEV ? 'admin@unmached.local' : '');
  const [password, setPassword] = useState(import.meta.env.DEV ? 'Admin123!' : '');

  if (isAuthenticated?.authenticated) {
    return <Navigate to="/" />;
  }

  const loginError =
    error ?? (data && data.success === false ? data.error : undefined);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login({ email, password });
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f5f5f5' }}>
      <div style={{ background: 'white', padding: '40px', borderRadius: '8px', boxShadow: '0 2px 10px rgba(0,0,0,0.1)', width: '100%', maxWidth: '400px' }}>
        <h1 style={{ textAlign: 'center', marginBottom: '30px' }}>Admin Login</h1>

        {loginError && (
          <Alert
            type="error"
            showIcon
            message={loginError.name || 'Login failed'}
            description={loginError.message || 'Invalid email or password'}
            style={{ marginBottom: '20px' }}
          />
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '14px', fontWeight: '500' }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '4px', fontSize: '14px' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '14px', fontWeight: '500' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '4px', fontSize: '14px' }}
            />
          </div>

          <button
            type="submit"
            disabled={isPending}
            style={{
              padding: '12px',
              background: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              fontSize: '16px',
              fontWeight: '500',
              cursor: isPending ? 'not-allowed' : 'pointer',
              opacity: isPending ? 0.7 : 1,
            }}
          >
            {isPending ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        {import.meta.env.DEV && (
          <div style={{ marginTop: '20px', padding: '15px', background: '#f0f9ff', borderRadius: '4px', fontSize: '13px', color: '#1e40af' }}>
            <strong>Demo credentials:</strong><br />
            Email: admin@unmached.local<br />
            Password: Admin123!
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginPage;
