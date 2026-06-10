import React from 'react';
import { Show } from '@refinedev/antd';
import { useShow } from '@refinedev/core';
import { Descriptions, Card, Tag, Space, Avatar, Table, Typography, Divider } from 'antd';
import { UserOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

interface AdminGamePlayer {
  id: string;
  playerId: string;
  heroId?: string | null;
  status: string;
  username?: string | null;
  avatar?: string | null;
}

interface AdminGame {
  id: string;
  code?: string | null;
  mode: string;
  status: string;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  boardId: string;
  boardName?: string | null;
  gamePlayers: AdminGamePlayer[];
}

// Реальный enum GameStatus из backend/prisma/schema.prisma
const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    PENDING: 'default',
    LOBBY: 'cyan',
    IN_PROGRESS: 'processing',
    PAUSED: 'orange',
    FINISHED: 'success',
    ABORTED: 'error',
  };
  return colors[status] || 'default';
};

const formatDate = (date?: string | null) =>
  date ? new Date(date).toLocaleString() : '—';

export const GameShow: React.FC = () => {
  const { query } = useShow<AdminGame>();
  const game = query?.data?.data;

  const playerColumns = [
    {
      title: 'Player',
      key: 'player',
      render: (_: unknown, gp: AdminGamePlayer) => (
        <Space>
          <Avatar src={gp.avatar || undefined} icon={<UserOutlined />} />
          <Text>{gp.username || gp.playerId}</Text>
        </Space>
      ),
    },
    {
      title: 'Hero ID',
      dataIndex: 'heroId',
      key: 'heroId',
      render: (heroId: string | null | undefined) =>
        heroId ? <code>{heroId}</code> : <Text type="secondary">—</Text>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag>{status}</Tag>,
    },
  ];

  return (
    <Show isLoading={query?.isLoading}>
      {game && (
        <Card>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div>
              <Title level={3}>Game {game.code ? `#${game.code}` : ''}</Title>
              <Text type="secondary">ID: {game.id}</Text>
            </div>

            <Descriptions column={2} bordered>
              <Descriptions.Item label="Code">
                <code>{game.code || '—'}</code>
              </Descriptions.Item>
              <Descriptions.Item label="Mode">
                <Tag color="geekblue">{game.mode}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                <Tag color={getStatusColor(game.status)}>{game.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Board">
                {game.boardName || game.boardId || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Created">
                {formatDate(game.createdAt)}
              </Descriptions.Item>
              <Descriptions.Item label="Started">
                {formatDate(game.startedAt)}
              </Descriptions.Item>
              <Descriptions.Item label="Finished">
                {formatDate(game.finishedAt)}
              </Descriptions.Item>
            </Descriptions>

            <Divider />

            <div>
              <Title level={4}>Players</Title>
              <Table
                dataSource={game.gamePlayers || []}
                columns={playerColumns}
                rowKey="id"
                pagination={false}
                size="small"
              />
            </div>
          </Space>
        </Card>
      )}
    </Show>
  );
};
