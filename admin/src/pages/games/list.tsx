import React from 'react';
import { List } from '@refinedev/antd';
import { Table, Badge, Space, Button, Input, Select, Tag } from 'antd';
import { EyeOutlined, SearchOutlined } from '@ant-design/icons';
import { useGo } from '@refinedev/core';
import { useState, useEffect } from 'react';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';
import { useDebounce } from '../../hooks/useDebounce';

const GET_GAMES = gql`
  query GetGames($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    gameList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
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

interface GameWithPlayers {
  id: string;
  code?: string;
  mode: string;
  status: string;
  createdAt: string;
  boardId: string;
  boardName?: string;
  gamePlayers: Array<{
    username?: string;
    avatar?: string;
  }>;
}

// Реальный enum GameStatus из backend/prisma/schema.prisma
const GAME_STATUSES = ['PENDING', 'LOBBY', 'IN_PROGRESS', 'PAUSED', 'FINISHED', 'ABORTED'];

export const GamesList: React.FC = () => {
  const go = useGo();
  const [loading, setLoading] = useState(true);
  const [games, setGames] = useState<GameWithPlayers[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<string>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const pageSize = 20;

  const debouncedSearch = useDebounce(search);

  const fetchGames = async (page: number = 1) => {
    setLoading(true);
    try {
      const result = await client.query(GET_GAMES, {
        page,
        limit: pageSize,
        search: debouncedSearch || undefined,
        sortBy,
        sortOrder,
      }).toPromise();

      if (result.error) {
        console.error('[GamesList] GraphQL error:', result.error);
        throw result.error;
      }

      let items = result.data?.gameList?.items || [];

      // Client-side filtering for status (since backend doesn't support it yet)
      if (statusFilter) {
        items = items.filter((game: GameWithPlayers) => game.status === statusFilter);
      }

      setGames(items);
      setTotal(result.data?.gameList?.total || 0);
      setCurrentPage(page);
    } catch (error) {
      console.error('[GamesList] Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGames(1);
  }, [debouncedSearch, sortBy, sortOrder, statusFilter]);

  const handlePageChange = (page: number) => {
    fetchGames(page);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setCurrentPage(1);
  };

  const handleSortChange = (value: string) => {
    if (value === sortBy) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(value);
      setSortOrder('asc');
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      PENDING: 'default',
      LOBBY: 'warning',
      IN_PROGRESS: 'processing',
      PAUSED: 'warning',
      FINISHED: 'success',
      ABORTED: 'error',
    };
    return colors[status] || 'default';
  };

  const handleView = (id: string) => {
    go({ to: { resource: 'games', action: 'show', id } });
  };

  const columns = [
    {
      title: 'Game',
      dataIndex: 'code',
      key: 'code',
      width: 120,
      render: (code: string | undefined, record: GameWithPlayers) => (
        <code>{code || record.id.slice(0, 8)}</code>
      )
    },
    {
      title: 'Mode',
      dataIndex: 'mode',
      key: 'mode',
      width: 130,
      render: (mode: string) => <Tag color="geekblue">{mode}</Tag>
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => (
        <Badge
          status={getStatusColor(status) as any}
          text={status}
        />
      )
    },
    {
      title: 'Board',
      dataIndex: 'boardName',
      key: 'board',
      width: 150
    },
    {
      title: 'Players',
      key: 'players',
      width: 200,
      render: (_: any, record: GameWithPlayers) => (
        <Space direction="vertical" size="small">
          {record.gamePlayers?.map((player, index: number) => (
            <Space key={index} size="small">
              <span style={{ fontWeight: 'bold' }}>P{index + 1}:</span>
              <span>{player.username}</span>
            </Space>
          ))}
        </Space>
      )
    },
    {
      title: 'Created',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (date: string) => new Date(date).toLocaleString()
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      fixed: 'right' as const,
      render: (_: any, record: GameWithPlayers) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => handleView(record.id)}
        >
          View
        </Button>
      )
    }
  ];

  return (
    <List>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space wrap>
          <Input
            placeholder="Search by game code..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={handleSearchChange}
            allowClear
            style={{ width: 300 }}
          />
          <Select
            placeholder="Status"
            value={statusFilter || undefined}
            onChange={setStatusFilter}
            allowClear
            style={{ width: 160 }}
          >
            {GAME_STATUSES.map((status) => (
              <Select.Option key={status} value={status}>
                {status}
              </Select.Option>
            ))}
          </Select>
          <Select
            placeholder="Sort by"
            value={sortBy}
            onChange={handleSortChange}
            style={{ width: 150 }}
          >
            <Select.Option value="createdAt">Created</Select.Option>
            <Select.Option value="status">Status</Select.Option>
            <Select.Option value="code">Code</Select.Option>
            <Select.Option value="mode">Mode</Select.Option>
          </Select>
          <Button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
          >
            {sortOrder === 'asc' ? '↑ Asc' : '↓ Desc'}
          </Button>
        </Space>
        <Table
          loading={loading}
          dataSource={games}
          rowKey="id"
          columns={columns}
          scroll={{ x: 1100 }}
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            onChange: handlePageChange,
            showSizeChanger: false,
          }}
        />
      </Space>
    </List>
  );
};
