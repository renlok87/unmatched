import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './protected.route';
import { LobbyView } from '@/components/lobby/LobbyView';
import { MatchmakingView } from '@/components/matchmaking/MatchmakingView';

export const LobbyRoutes: React.FC = () => {
  return (
    <ProtectedRoute>
      <Routes>
        {/* Default lobby view */}
        <Route path="/" element={<LobbyView />} />

        {/* Matchmaking view */}
        <Route path="/matchmaking" element={<MatchmakingView />} />

        {/* Create game view (future feature) */}
        <Route path="/create" element={<LobbyView />} />

        {/* Redirect any unmatched routes to lobby */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProtectedRoute>
  );
};

export default LobbyRoutes;