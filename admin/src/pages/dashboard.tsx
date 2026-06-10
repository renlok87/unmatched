import { useState, useEffect } from 'react';
import { Alert, Card, Row, Col, Statistic, Button, List, Typography, Space, Badge } from 'antd';
import { useLogout, useGetIdentity } from '@refinedev/core';
import { useNavigate } from 'react-router-dom';
import {
  UserOutlined,
  IdcardOutlined,
  AppstoreOutlined,
  TeamOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { client } from '../providers/dataProvider';
import { gql } from 'urql';

const { Title, Text } = Typography;

interface UserIdentity {
  username?: string;
  email?: string;
}

interface AdminStats {
  totalUsers: number;
  totalHeroes: number;
  totalCards: number;
  totalBoards: number;
  totalGames: number;
}

interface GamePlayer {
  username?: string;
  avatar?: string;
}

interface GameItem {
  id: string;
  code?: string;
  mode?: string;
  status: string;
  createdAt: string;
  boardId?: string;
  boardName?: string;
  gamePlayers: GamePlayer[];
}

const GET_ADMIN_STATS = gql`
  query GetAdminStats {
    adminStats {
      totalUsers
      totalHeroes
      totalCards
      totalBoards
      totalGames
    }
  }
`;

const GET_RECENT_GAMES = gql`
  query GetRecentGames {
    gameList(page: 1, limit: 5) {
      items {
        id
        code
        mode
        status
        createdAt
        boardId
        boardName
        gamePlayers {
          username
          avatar
        }
      }
      total
    }
  }
`;

export const DashboardPage = () => {
  const { mutate: logout } = useLogout();
  const { data: identity } = useGetIdentity<UserIdentity>();
  const navigate = useNavigate();

  const [statsData, setStatsData] = useState<AdminStats | null>(null);
  const [recentGames, setRecentGames] = useState<GameItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsResult, gamesResult] = await Promise.all([
          client.query(GET_ADMIN_STATS, {}).toPromise(),
          client.query(GET_RECENT_GAMES, {}).toPromise(),
        ]);

        const errors = [statsResult.error, gamesResult.error].filter(Boolean);
        if (errors.length > 0) {
          console.error('Failed to fetch dashboard data:', errors);
          setError(errors.map((e) => e!.message).join('; '));
        } else {
          setError(null);
        }

        if (statsResult.data?.adminStats) {
          setStatsData(statsResult.data.adminStats);
        }

        if (gamesResult.data?.gameList) {
          setRecentGames(gamesResult.data.gameList.items);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
        setError(error instanceof Error ? error.message : 'Failed to fetch dashboard data');
      }
    };

    fetchData();
  }, []);

  const statsCards = [
    {
      title: 'Total Users',
      value: statsData?.totalUsers || 0,
      icon: <TeamOutlined style={{ fontSize: 24, color: '#1890ff' }} />,
      color: '#1890ff',
    },
    {
      title: 'Total Heroes',
      value: statsData?.totalHeroes || 0,
      icon: <UserOutlined style={{ fontSize: 24, color: '#52c41a' }} />,
      color: '#52c41a',
    },
    {
      title: 'Total Cards',
      value: statsData?.totalCards || 0,
      icon: <IdcardOutlined style={{ fontSize: 24, color: '#faad14' }} />,
      color: '#faad14',
    },
    {
      title: 'Total Boards',
      value: statsData?.totalBoards || 0,
      icon: <AppstoreOutlined style={{ fontSize: 24, color: '#722ed1' }} />,
      color: '#722ed1',
    },
    {
      title: 'Total Games',
      value: statsData?.totalGames || 0,
      icon: <PlayCircleOutlined style={{ fontSize: 24, color: '#eb2f96' }} />,
      color: '#eb2f96',
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>Dashboard</Title>
        <Text type="secondary">
          Welcome back, {identity?.username || 'Admin'}! Here's what's happening today.
        </Text>
      </div>
      {error && (
        <Alert
          type="error"
          showIcon
          message="Failed to load dashboard data"
          description={error}
          style={{ marginBottom: 24 }}
        />
      )}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {statsCards.map((stat) => (
          <Col xs={24} sm={12} lg={6} key={stat.title}>
            <Card>
              <Statistic
                title={stat.title}
                value={stat.value}
                prefix={stat.icon}
                valueStyle={{ color: stat.color }}
              />
            </Card>
          </Col>
        ))}
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space>
                <PlayCircleOutlined />
                <span>Recent Games</span>
              </Space>
            }
            extra={
              <Button type="link" onClick={() => navigate('/games')}>
                View All
              </Button>
            }
          >
            <List
              itemLayout="horizontal"
              dataSource={recentGames}
              renderItem={(item: GameItem) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Badge status={item.status === 'FINISHED' ? 'success' : 'processing'} />}
                    title={<Text strong>{`Game #${item.code || item.id}`}</Text>}
                    description={
                      <Space direction="vertical" size={0}>
                        <Text type="secondary">
                          {[item.mode?.replace(/_/g, ' '), item.boardName || 'Unknown Board']
                            .filter(Boolean)
                            .join(' • ')}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {new Date(item.createdAt).toLocaleString()}
                        </Text>
                      </Space>
                    }
                  />
                  <Badge
                    text={item.status?.replace(/_/g, ' ')}
                    status={item.status === 'FINISHED' ? 'success' : item.status === 'IN_PROGRESS' ? 'processing' : 'default'}
                  />
                </List.Item>
              )}
            />
            {recentGames.length === 0 && (
              <div style={{ textAlign: 'center', padding: '24px' }}>
                <Text type="secondary">No recent games found</Text>
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <PlusOutlined />
                <span>Quick Actions</span>
              </Space>
            }
          >
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Button type="primary" icon={<UserOutlined />} block href="/heroes/create">
                Create New Hero
              </Button>
              <Button icon={<IdcardOutlined />} block href="/cards/create">
                Create New Card
              </Button>
              <Button icon={<AppstoreOutlined />} block href="/boards/create">
                Create New Board
              </Button>
              <Button danger block onClick={() => logout()}>
                Logout
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;
