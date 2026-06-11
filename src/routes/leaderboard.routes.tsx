import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { LeaderboardView } from '@/components/leaderboard';

export const LeaderboardRoutes: React.FC = () => {
  return (
    <AuthGuard>
      <Routes>
        <Route path="/" element={<LeaderboardView />} />
      </Routes>
    </AuthGuard>
  );
};