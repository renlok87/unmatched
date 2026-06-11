import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { LoginForm } from '@/components/auth/LoginForm';

export const AuthRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginForm />} />
      {/* Add register route when RegisterForm is created */}
      {/* <Route path="/register" element={<RegisterForm />} /> */}
    </Routes>
  );
};

export default AuthRoutes;