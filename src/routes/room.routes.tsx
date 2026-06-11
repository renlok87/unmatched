import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { RoomView } from '@/components/room/RoomView';

export const RoomRoutes: React.FC = () => {
  return (
    <Routes>
      <Route
        path="/:gameId"
        element={
          <AuthGuard>
            <RoomView />
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

export default RoomRoutes;