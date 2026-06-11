import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { FriendsList } from '@/components/social';

export const SocialRoutes: React.FC = () => {
  return (
    <AuthGuard>
      <Routes>
        <Route path="/friends" element={<FriendsList />} />
      </Routes>
    </AuthGuard>
  );
};