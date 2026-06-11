import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { LobbyRoutes } from './lobby.routes';
import { AuthRoutes } from './auth.routes';
import { HeroRoutes } from './hero.routes';
import { CardsRoutes } from './cards.routes';
import { RoomRoutes } from './room.routes';
import { GameRoutes } from './game.routes';
import { LeaderboardRoutes } from './leaderboard.routes';
import { ProfileRoutes } from './profile.routes';
import { SocialRoutes } from './social.routes';
import { TestGameRoutes } from './test-game.routes';
import { CardShow } from '@/components/cards/CardShow';

const RouteDebugger: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  useEffect(() => {
    console.log('Current location:', location.pathname);
  }, [location]);
  return <>{children}</>;
};

export const AppRouter: React.FC = () => {
  return (
    <BrowserRouter>
      <RouteDebugger>
        <Routes>
          {/* Default redirect to lobby */}
          <Route path="/" element={<Navigate to="/lobby" replace />} />

          {/* Auth routes */}
          <Route path="/auth/*" element={<AuthRoutes />} />

          {/* Lobby and matchmaking routes */}
          <Route path="/lobby/*" element={<LobbyRoutes />} />

          {/* Hero selection routes */}
          <Route path="/heroes/*" element={<HeroRoutes />} />

          {/* Cards routes - прямые роуты для избежания проблем с вложенностью */}
          <Route path="/cards/show/:cardId" element={<CardShow />} />

          {/* Game room routes */}
          <Route path="/room/*" element={<RoomRoutes />} />

          {/* Game routes */}
          <Route path="/game/*" element={<GameRoutes />} />

          {/* Leaderboard routes */}
          <Route path="/leaderboard/*" element={<LeaderboardRoutes />} />

          {/* Profile routes */}
          <Route path="/profile/*" element={<ProfileRoutes />} />

          {/* Social routes */}
          <Route path="/social/*" element={<SocialRoutes />} />

          {/* Test game routes */}
          <Route path="/test-game/*" element={<TestGameRoutes />} />

          {/* 404 - Redirect to lobby */}
          <Route path="*" element={<Navigate to="/lobby" replace />} />
        </Routes>
      </RouteDebugger>
    </BrowserRouter>
  );
};

export default AppRouter;