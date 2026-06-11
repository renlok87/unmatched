import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { GameView } from '@/components/game/GameView';

export const GameRoutes: React.FC = () => {
  return (
    <Routes>
      <Route
        path="/:gameId"
        element={
          <AuthGuard>
            <GameView />
          </AuthGuard>
        }
      />
      {/* Redirect root to lobby */}
      <Route path="/" element={<Navigate to="/lobby" replace />} />
      {/* 404 - Redirect to lobby */}
      <Route path="*" element={<Navigate to="/lobby" replace />} />
    </Routes>
  );
};

export default GameRoutes;