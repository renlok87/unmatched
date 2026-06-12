import React from 'react';
import { Layout, Menu, Button, Dropdown, Space, Avatar } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import { useLogout, useGetIdentity } from '@refinedev/core';
import {
  DashboardOutlined,
  UserOutlined,
  IdcardOutlined,
  AppstoreOutlined,
  TeamOutlined,
  PlayCircleOutlined,
  ThunderboltOutlined,
  FileSearchOutlined,
  LogoutOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';

const { Sider, Header, Content } = Layout;

interface UserIdentity {
  username?: string;
  email?: string;
}

interface AdminLayoutProps {
  children?: React.ReactNode;
}

export const AdminLayout: React.FC<AdminLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { mutate: logout } = useLogout();
  const { data: user } = useGetIdentity<UserIdentity>();
  const [collapsed, setCollapsed] = React.useState(false);

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
    },
    {
      key: '/heroes',
      icon: <UserOutlined />,
      label: 'Heroes',
    },
    {
      key: '/cards',
      icon: <IdcardOutlined />,
      label: 'Cards',
    },
    {
      key: '/boards',
      icon: <AppstoreOutlined />,
      label: 'Boards',
    },
    {
      key: '/users',
      icon: <TeamOutlined />,
      label: 'Users',
    },
    {
      key: '/games',
      icon: <PlayCircleOutlined />,
      label: 'Games',
    },
    {
      key: '/game-tester',
      icon: <ExperimentOutlined />,
      label: 'Game Tester',
    },
    {
      key: '/matchmaking',
      icon: <ThunderboltOutlined />,
      label: 'Matchmaking',
    },
    {
      key: '/audit-logs',
      icon: <FileSearchOutlined />,
      label: 'Audit Logs',
    },
  ];

  // Подсветка пункта меню по префиксу pathname: /heroes/show/1 -> /heroes
  const selectedKey =
    location.pathname === '/'
      ? '/'
      : menuItems
          .map((item) => item.key)
          .filter((key) => key !== '/' && location.pathname.startsWith(key))
          .sort((a, b) => b.length - a.length)[0] ?? location.pathname;

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogout = () => {
    logout();
  };

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
      >
        <div
          style={{
            height: 32,
            margin: 16,
            background: 'rgba(255, 255, 255, 0.2)',
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 'bold',
            fontSize: collapsed ? 12 : 16,
          }}
        >
          {collapsed ? 'UM' : 'Unmatched'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[selectedKey]}
          mode="inline"
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,21,41,.08)',
          }}
        >
          <h1 style={{ fontSize: 20, margin: 0, fontWeight: 500 }}>
            Admin Panel
          </h1>
          <Space>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button type="text" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Avatar icon={<UserOutlined />} />
                <span>{user?.username || 'User'}</span>
              </Button>
            </Dropdown>
          </Space>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            background: '#fff',
            borderRadius: 8,
            minHeight: 280,
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};
