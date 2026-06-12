import { List } from '@refinedev/antd';
import { IResourceComponentsProps } from '@refinedev/core';
import { Table, Space, Tag, Avatar, Typography, Badge, Button, Input } from 'antd';
import { EyeOutlined, EditOutlined, SearchOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';
import { useDebounce } from '../../hooks/useDebounce';

const { Text } = Typography;

const GET_USERS = gql`
  query GetUsers($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    userList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      users {
        id
        username
        email
        avatar
        role
        createdAt
        emailVerified
        stats {
          gamesPlayed
          gamesWon
          currentElo
        }
      }
      total
    }
  }
`;

export const UserList: React.FC<IResourceComponentsProps> = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<string>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const pageSize = 20;

  const debouncedSearch = useDebounce(search);

  const fetchUsers = async (page: number = 1) => {
    setLoading(true);
    try {
      const result = await client.query(GET_USERS, {
        page,
        limit: pageSize,
        search: debouncedSearch || undefined,
        sortBy,
        sortOrder,
      }).toPromise();

      if (result.error) {
        throw result.error;
      }

      const data = result.data?.userList;

      setUsers(data?.users || []);
      setTotal(data?.total || 0);
      setCurrentPage(page);
    } catch (error) {
      console.error('[UserList] Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers(1);
  }, [debouncedSearch, sortBy, sortOrder]);

  const handlePageChange = (page: number) => {
    fetchUsers(page);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setCurrentPage(1);
  };

  const handleTableChange = (_pagination: any, _filters: any, sorter: any) => {
    const activeSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    if (activeSorter?.field && activeSorter?.order) {
      setSortBy(String(activeSorter.field));
      setSortOrder(activeSorter.order === 'ascend' ? 'asc' : 'desc');
    } else {
      // Сортировка по колонке сброшена — возвращаемся к дефолту
      setSortBy('createdAt');
      setSortOrder('desc');
    }
  };

  const columnSortOrder = (field: string): 'ascend' | 'descend' | null =>
    sortBy === field ? (sortOrder === 'asc' ? 'ascend' : 'descend') : null;

  return (
    <List>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space>
          <Input
            placeholder="Search by username or email..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={handleSearchChange}
            allowClear
            style={{ width: 300 }}
          />
        </Space>
        <Table
          loading={loading}
          dataSource={users}
          rowKey="id"
          onChange={handleTableChange}
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            onChange: handlePageChange,
            showSizeChanger: false,
          }}
        >
          <Table.Column
            dataIndex="avatar"
            title="Avatar"
            render={(avatar: string, record: any) => (
              <Avatar src={avatar} size={40}>
                {record.username?.charAt(0).toUpperCase()}
              </Avatar>
            )}
          />
          <Table.Column
            dataIndex="username"
            title="Username"
            render={(text: string, record: any) => (
              <Space direction="vertical" size={0}>
                <Text strong>{text}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {record.email}
                </Text>
              </Space>
            )}
            sorter={true}
            sortOrder={columnSortOrder('username')}
          />
          <Table.Column
            dataIndex="role"
            title="Role"
            render={(role: string) => {
              const colors: Record<string, string> = {
                USER: 'default',
                ADMIN: 'red',
                MODERATOR: 'blue',
              };
              return <Tag color={colors[role] || 'default'}>{role}</Tag>;
            }}
            sorter={true}
            sortOrder={columnSortOrder('role')}
          />
          <Table.Column
            dataIndex="stats"
            title="Games Played"
            render={(stats: any) => <Tag>{stats?.gamesPlayed || 0}</Tag>}
          />
          <Table.Column
            dataIndex="stats"
            title="ELO Rating"
            render={(stats: any) => <Tag color="green">{stats?.currentElo || 1200}</Tag>}
          />
          <Table.Column
            dataIndex="emailVerified"
            title="Verified"
            render={(verified: boolean) => (
              <Badge status={verified ? 'success' : 'error'} text={verified ? 'Yes' : 'No'} />
            )}
          />
          <Table.Column
            dataIndex="createdAt"
            title="Created At"
            render={(date: string) => new Date(date).toLocaleDateString()}
            sorter={true}
            sortOrder={columnSortOrder('createdAt')}
          />
          <Table.Column
            title="Actions"
            dataIndex="actions"
            render={(_, record: any) => (
              <Space>
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/users/show/${record.id}`)}
                >
                  Show
                </Button>
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => navigate(`/users/edit/${record.id}`)}
                >
                  Edit
                </Button>
              </Space>
            )}
          />
        </Table>
      </Space>
    </List>
  );
};
