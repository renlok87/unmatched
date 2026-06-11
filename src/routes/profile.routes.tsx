import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { ProfileView } from '@/components/profile';

export const ProfileRoutes: React.FC = () => {
  return (
    <AuthGuard>
      <Routes>
        <Route path="/" element={<ProfileView isOwnProfile />} />
        <Route path="/:userId" element={<ProfileView />} />
      </Routes>
    </AuthGuard>
  );
};