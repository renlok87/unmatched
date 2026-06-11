import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { HeroSelection } from '@/components/heroes/HeroSelection';

export const HeroRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/:gameId" element={<HeroSelection />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default HeroRoutes;