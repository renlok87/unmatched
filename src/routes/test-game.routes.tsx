import { Routes, Route } from 'react-router-dom';
import { TestGamePage } from '@/pages/test-game/TestGamePage';

export const TestGameRoutes = () => (
  <Routes>
    <Route index element={<TestGamePage />} />
    <Route path="*" element={<TestGamePage />} />
  </Routes>
);
