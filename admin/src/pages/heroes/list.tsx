import { List } from '@refinedev/antd';
import { IResourceComponentsProps } from '@refinedev/core';
import { Table, Space, Tag, Avatar, Typography, Button, Modal, message, Input, Select } from 'antd';
import { EyeOutlined, EditOutlined, DeleteOutlined, SearchOutlined, PictureOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';
import { useDebounce } from '../../hooks/useDebounce';

const { Text } = Typography;

const GET_HEROES = gql`
  query GetHeroes($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    heroList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        name
        nameEn
        nameRu
        set
        health
        fighterType
        imageUrl
        avatarUrl
        createdAt
      }
      total
    }
  }
`;

const DELETE_HERO = gql`
  mutation DeleteHero($id: String!) {
    deleteHero(id: $id)
  }
`;

export const HeroList: React.FC<IResourceComponentsProps> = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [heroes, setHeroes] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [sortBy, setSortBy] = useState<string>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const pageSize = 20;

  const fetchHeroes = async (page: number = 1) => {
    setLoading(true);
    try {
      const result = await client.query(GET_HEROES, {
        page,
        limit: pageSize,
        search: debouncedSearch || undefined,
        sortBy,
        sortOrder,
      }).toPromise();

      if (result.error) {
        console.error('[HeroList] GraphQL error:', result.error);
        throw result.error;
      }

      const data = result.data?.heroList;

      setHeroes(data?.items || []);
      setTotal(data?.total || 0);
      setCurrentPage(page);
    } catch (error) {
      console.error('[HeroList] Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHeroes(1);
  }, [debouncedSearch, sortBy, sortOrder]);

  const handlePageChange = (page: number) => {
    fetchHeroes(page);
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

  const handleDelete = (id: string, name: string) => {
    Modal.confirm({
      title: 'Delete Hero',
      content: `Are you sure you want to delete "${name}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          const result = await client.mutation(DELETE_HERO, { id }).toPromise();

          if (result.error) {
            console.error('[HeroList] Delete error:', result.error);
            message.error(`Failed to delete: ${result.error.message}`);
          } else {
            message.success('Hero deleted successfully');
            // Refresh the list
            fetchHeroes(currentPage);
          }
        } catch (error: any) {
          console.error('[HeroList] Delete error:', error);
          message.error(`Failed to delete: ${error.message}`);
        }
      },
    });
  };

  return (
    <List>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space>
          <Input
            placeholder="Search by name or set..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={handleSearchChange}
            allowClear
            style={{ width: 300 }}
          />
          <Select
            placeholder="Sort by"
            value={sortBy}
            onChange={handleSortChange}
            style={{ width: 150 }}
          >
            <Select.Option value="name">Name</Select.Option>
            <Select.Option value="set">Set</Select.Option>
            <Select.Option value="health">Health</Select.Option>
            <Select.Option value="fighterType">Type</Select.Option>
            <Select.Option value="createdAt">Created</Select.Option>
          </Select>
          <Button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
          >
            {sortOrder === 'asc' ? '↑ Asc' : '↓ Desc'}
          </Button>
        </Space>
        <Table
          loading={loading}
          dataSource={heroes}
          rowKey="id"
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            onChange: handlePageChange,
            showSizeChanger: false,
          }}
        >
          <Table.Column
            dataIndex="imageUrl"
            title="Avatar"
            render={(url: string) => (
              // Avatar сам показывает icon-заглушку при отсутствии/ошибке загрузки src
              <Avatar
                shape="square"
                size={50}
                src={url || undefined}
                icon={<PictureOutlined />}
                style={{ borderRadius: 6 }}
              />
            )}
          />
          <Table.Column
            dataIndex="name"
            title="Name"
            render={(text: string, record: any) => (
              <Space direction="vertical" size={0}>
                <Text strong>{text}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {record.nameEn} / {record.nameRu}
                </Text>
              </Space>
            )}
          />
          <Table.Column
            dataIndex="set"
            title="Set"
            render={(set: string) => <Tag color="blue">{set}</Tag>}
          />
          <Table.Column
            dataIndex="health"
            title="Health"
            align="center"
            render={(health: number) => (
              <Tag color={health > 20 ? 'green' : health > 10 ? 'orange' : 'red'}>
                {health} HP
              </Tag>
            )}
          />
          <Table.Column
            dataIndex="fighterType"
            title="Type"
            render={(type: string) => {
              const colors: Record<string, string> = {
                HERO: 'purple',
                MINION: 'blue',
                VILLAIN: 'red',
                HUGE: 'orange',
              };
              return <Tag color={colors[type] || 'default'}>{type}</Tag>;
            }}
          />
          <Table.Column
            dataIndex="createdAt"
            title="Created At"
            render={(date: string) => new Date(date).toLocaleDateString()}
          />
          <Table.Column
            title="Actions"
            dataIndex="actions"
            render={(_, record: any) => (
              <Space>
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/heroes/show/${record.id}`)}
                >
                  Show
                </Button>
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => navigate(`/heroes/edit/${record.id}`)}
                >
                  Edit
                </Button>
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDelete(record.id, record.name)}
                >
                  Delete
                </Button>
              </Space>
            )}
          />
        </Table>
      </Space>
    </List>
  );
};
