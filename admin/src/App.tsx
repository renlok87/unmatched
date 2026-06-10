import React from 'react';
import { Refine } from '@refinedev/core';
import { useNotificationProvider } from '@refinedev/antd';
import { dataProvider } from './providers/dataProvider';
import { authProvider } from './providers/authProvider';
import routerProvider, { DocumentTitleHandler, UnsavedChangesNotifier } from '@refinedev/react-router';
import { Routes, Route, Outlet, Navigate } from 'react-router-dom';
import { DashboardPage } from './pages/dashboard';
import { LoginPage } from './pages/login';
import { AdminLayout } from './components/layout/AdminLayout';
import { HeroList, HeroCreate, HeroEdit, HeroShow } from './pages/heroes';
import { CardList, CardCreate, CardEdit, CardShow } from './pages/cards';
import { BoardList, BoardCreate, BoardEdit, BoardShow } from './pages/boards';
import { UserList, UserEdit, UserShow } from './pages/users';
import { GamesList, GameShow } from './pages/games';
import { MatchmakingList } from './pages/matchmaking';
import { AuditLogsList } from './pages/audit-logs';
import { useIsAuthenticated } from '@refinedev/core';

// Компонент для защиты маршрутов
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: authData, isLoading } = useIsAuthenticated();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!authData?.authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Компонент-обёртка для лейаута с Outlet для детей
const LayoutWrapper: React.FC = () => {
  return (
    <ProtectedRoute>
      <AdminLayout>
        <Outlet />
      </AdminLayout>
    </ProtectedRoute>
  );
};

function App() {
  return (
    <Refine
      dataProvider={dataProvider}
      authProvider={authProvider}
      routerProvider={routerProvider}
      notificationProvider={useNotificationProvider}
      resources={[
        {
          name: 'heroes',
          list: '/heroes',
          show: '/heroes/show/:id',
          create: '/heroes/create',
          edit: '/heroes/edit/:id',
          meta: { canDelete: true },
        },
        {
          name: 'cards',
          list: '/cards',
          show: '/cards/show/:id',
          create: '/cards/create',
          edit: '/cards/edit/:id',
          meta: { canDelete: true },
        },
        {
          name: 'boards',
          list: '/boards',
          show: '/boards/show/:id',
          create: '/boards/create',
          edit: '/boards/edit/:id',
          meta: { canDelete: true },
        },
        {
          name: 'users',
          list: '/users',
          show: '/users/show/:id',
          edit: '/users/edit/:id',
          meta: { canDelete: false },
        },
        {
          name: 'games',
          list: '/games',
          show: '/games/show/:id',
          meta: { canDelete: false },
        },
        {
          name: 'matchmakingQueue',
          list: '/matchmaking',
          meta: { canDelete: false },
        },
        {
          name: 'auditLogs',
          list: '/audit-logs',
          meta: { canDelete: false },
        },
      ]}
      options={{
        syncWithLocation: true,
        warnWhenUnsavedChanges: true,
        projectId: 'unmached-admin',
        disableTelemetry: true,
      }}
    >
      <DocumentTitleHandler />
      <UnsavedChangesNotifier />
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route path="/" element={<LayoutWrapper />}>
          <Route index element={<DashboardPage />} />

          {/* Heroes Routes */}
          <Route path="heroes" element={<HeroList />} />
          <Route path="heroes/show/:id" element={<HeroShow />} />
          <Route path="heroes/create" element={<HeroCreate />} />
          <Route path="heroes/edit/:id" element={<HeroEdit />} />

          {/* Cards Routes */}
          <Route path="cards" element={<CardList />} />
          <Route path="cards/show/:id" element={<CardShow />} />
          <Route path="cards/create" element={<CardCreate />} />
          <Route path="cards/edit/:id" element={<CardEdit />} />

          {/* Boards Routes */}
          <Route path="boards" element={<BoardList />} />
          <Route path="boards/show/:id" element={<BoardShow />} />
          <Route path="boards/create" element={<BoardCreate />} />
          <Route path="boards/edit/:id" element={<BoardEdit />} />

          {/* Users Routes */}
          <Route path="users" element={<UserList />} />
          <Route path="users/show/:id" element={<UserShow />} />
          <Route path="users/edit/:id" element={<UserEdit />} />

          {/* Games Routes */}
          <Route path="games" element={<GamesList />} />
          <Route path="games/show/:id" element={<GameShow />} />

          {/* Matchmaking Route */}
          <Route path="matchmaking" element={<MatchmakingList />} />

          {/* Audit Logs Route */}
          <Route path="audit-logs" element={<AuditLogsList />} />
        </Route>
      </Routes>
    </Refine>
  );
}

export default App;
