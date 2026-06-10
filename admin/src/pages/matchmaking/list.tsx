import React from 'react';
import { List } from '@refinedev/antd';
import { Table, Card, Statistic, Row, Col, Tag, Space, Avatar, Progress, Badge, Input, Select, Button } from 'antd';
import { UserOutlined, ClockCircleOutlined, TeamOutlined, HourglassOutlined, SearchOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';
import { useDebounce } from '../../hooks/useDebounce';

const GET_MATCHMAKING_QUEUE = gql`
  query GetMatchmakingQueue {
    matchmakingQueue {
      items {
        id
        userId
        username
        avatar
        mode
        elo
        joinedAt
        position
      }
      total
      activeQueues
    }
  }
`;

interface QueuedPlayer {
  id: string;
  userId: string;
  username: string;
  avatar?: string;
  mode: string;
  elo: number;
  joinedAt: string;
  position: number;
}

export const MatchmakingList: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [players, setPlayers] = useState<QueuedPlayer[]>([]);
  const [total, setTotal] = useState(0);
  const [activeQueues, setActiveQueues] = useState(0);
  const [searchText, setSearchText] = useState('');
  const debouncedSearch = useDebounce(searchText);
  const [modeFilter, setModeFilter] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('joinedAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const result = await client.query(GET_MATCHMAKING_QUEUE, {}).toPromise();

      if (result.error) {
        console.error('[MatchmakingList] GraphQL error:', result.error);
        throw result.error;
      }

      const data = result.data?.matchmakingQueue;

      setPlayers(data?.items || []);
      setTotal(data?.total || 0);
      setActiveQueues(data?.activeQueues || 0);
    } catch (error) {
      console.error('[MatchmakingList] Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchQueue, 10000);
    return () => clearInterval(interval);
  }, []);

  const avgWaitTime = players.length > 0
    ? Math.round(players.reduce((sum, p) => sum + (Date.now() - new Date(p.joinedAt).getTime()) / 1000, 0) / players.length)
    : 0;

  const getQueueTypeColor = (mode: string) => {
    const colors: Record<string, string> = {
      ONE_V_ONE: 'gold',
      TWO_V_TWO: 'blue',
      FREE_FOR_ALL: 'purple',
      VS_AI: 'green'
    };
    return colors[mode] || 'default';
  };

  const getWaitProgress = (joinedAt: string) => {
    const waitTime = (Date.now() - new Date(joinedAt).getTime()) / 1000;
    const maxWaitTime = 300; // 5 minutes
    const percentage = Math.min((waitTime / maxWaitTime) * 100, 100);
    return percentage;
  };

  const getWaitTime = (joinedAt: string) => {
    return Math.round((Date.now() - new Date(joinedAt).getTime()) / 1000);
  };

  const handleSortChange = (value: string) => {
    if (value === sortBy) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(value);
      setSortOrder('asc');
    }
  };

  // Apply client-side filtering and sorting
  const filteredPlayers = players
    .filter((player: QueuedPlayer) => {
      const matchesSearch = !debouncedSearch ||
        player.username.toLowerCase().includes(debouncedSearch.toLowerCase()) ||
        player.userId.toLowerCase().includes(debouncedSearch.toLowerCase());

      const matchesMode = !modeFilter || player.mode === modeFilter;

      return matchesSearch && matchesMode;
    })
    .sort((a: QueuedPlayer, b: QueuedPlayer) => {
      let aVal: any = a[sortBy as keyof QueuedPlayer];
      let bVal: any = b[sortBy as keyof QueuedPlayer];

      if (sortBy === 'joinedAt') {
        aVal = new Date(a.joinedAt).getTime();
        bVal = new Date(b.joinedAt).getTime();
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortOrder === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
      }

      return 0;
    });

  const columns = [
    {
      title: 'Player',
      key: 'player',
      width: 200,
      render: (_: any, record: QueuedPlayer) => (
        <Space>
          <Avatar
            size={40}
            src={record.avatar}
            icon={<UserOutlined />}
          />
          <Space direction="vertical" size={0}>
            <span style={{ fontWeight: 'bold' }}>{record.username}</span>
            <Tag color="green">ELO: {record.elo}</Tag>
          </Space>
        </Space>
      )
    },
    {
      title: 'Queue Type',
      dataIndex: 'mode',
      key: 'mode',
      width: 120,
      render: (type: string) => <Tag color={getQueueTypeColor(type)}>{type}</Tag>
    },
    {
      title: 'Position',
      dataIndex: 'position',
      key: 'position',
      width: 100,
      render: (position: number) => <Tag color="blue">#{position}</Tag>
    },
    {
      title: 'Wait Time',
      key: 'waitTime',
      width: 200,
      render: (_: any, record: QueuedPlayer) => (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <ClockCircleOutlined />
            <span>{getWaitTime(record.joinedAt)}s</span>
          </Space>
          <Progress
            percent={getWaitProgress(record.joinedAt)}
            size="small"
            showInfo={false}
            status={getWaitTime(record.joinedAt) > 180 ? 'exception' : 'active'}
          />
        </Space>
      )
    },
    {
      title: 'Joined At',
      dataIndex: 'joinedAt',
      key: 'joinedAt',
      width: 180,
      render: (date: string) => new Date(date).toLocaleString()
    }
  ];

  return (
    <List>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Players in Queue"
              value={total}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Active Queues"
              value={activeQueues}
              prefix={<HourglassOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Avg Wait Time"
              value={avgWaitTime}
              suffix="seconds"
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: avgWaitTime > 60 ? '#ff4d4f' : '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Games (Last Hour)"
              value={0}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <Badge count={total} showZero>
              <span>Queued Players</span>
            </Badge>
          </Space>
        }
        extra={
          <Space>
            <Input
              placeholder="Search player..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
              style={{ width: 200 }}
            />
            <Select
              placeholder="Mode"
              value={modeFilter || undefined}
              onChange={setModeFilter}
              allowClear
              style={{ width: 120 }}
            >
              <Select.Option value="ONE_V_ONE">1 vs 1</Select.Option>
              <Select.Option value="TWO_V_TWO">2 vs 2</Select.Option>
              <Select.Option value="FREE_FOR_ALL">Free for All</Select.Option>
              <Select.Option value="VS_AI">vs AI</Select.Option>
            </Select>
            <Select
              placeholder="Sort by"
              value={sortBy}
              onChange={handleSortChange}
              style={{ width: 120 }}
            >
              <Select.Option value="joinedAt">Joined</Select.Option>
              <Select.Option value="username">Name</Select.Option>
              <Select.Option value="elo">ELO</Select.Option>
              <Select.Option value="position">Position</Select.Option>
              <Select.Option value="mode">Mode</Select.Option>
            </Select>
            <Button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            >
              {sortOrder === 'asc' ? '↑' : '↓'}
            </Button>
          </Space>
        }
      >
        <Table
          loading={loading}
          dataSource={filteredPlayers}
          rowKey="id"
          columns={columns}
          scroll={{ x: 900 }}
          pagination={false}
        />
      </Card>
    </List>
  );
};
