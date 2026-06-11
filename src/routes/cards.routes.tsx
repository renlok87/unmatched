import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { CardShow } from '@/components/cards/CardShow';

export const CardsRoutes: React.FC = () => {
  useEffect(() => {
    console.log('CardsRoutes mounted');
  }, []);

  return (
    <Routes>
      <Route path="show/:cardId" element={<CardShow />} />
      <Route path="*" element={<Navigate to="/lobby" replace />} />
    </Routes>
  );
};

export default CardsRoutes;
