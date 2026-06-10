import { List } from '@refinedev/antd';
import { IResourceComponentsProps } from '@refinedev/core';
import { Table, Space, Tag, Typography, Button, Modal, message, Input, Select, Avatar } from 'antd';
import { EyeOutlined, EditOutlined, DeleteOutlined, SearchOutlined, PictureOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';
import { useDebounce } from '../../hooks/useDebounce';

const { Text } = Typography;

const GET_CARDS = gql`
  query GetCards($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    cardList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        name
        nameEn
        nameRu
        cardType
        subType
        attackValue
        defenseValue
        boostValue
        count
        imageUrl
        imageUrlRu
        createdAt
      }
      total
    }
  }
`;

const DELETE_CARD = gql`
  mutation DeleteCard($id: String!) {
    deleteCard(id: $id)
  }
`;

const CardImage: React.FC<{ imageUrl?: string; name: string }> = ({ imageUrl, name }) => {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [imageUrl]);

  if (!imageUrl || failed) {
    return (
      <Avatar
        shape="square"
        icon={<PictureOutlined />}
        alt={name}
        style={{ width: 60, height: 84, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      />
    );
  }

  return (
    <img
      src={imageUrl}
      alt={name}
      style={{
        width: 60,
        height: 84,
        objectFit: 'cover',
        borderRadius: 4,
        border: '1px solid #d9d9d9',
      }}
      onError={() => setFailed(true)}
    />
  );
};

export const CardList: React.FC<IResourceComponentsProps> = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [cards, setCards] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<string>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const debouncedSearch = useDebounce(search);
  const pageSize = 20;

  const fetchCards = async (page: number = 1) => {
    setLoading(true);
    try {
      const result = await client.query(GET_CARDS, {
        page,
        limit: pageSize,
        search: debouncedSearch || undefined,
        sortBy,
        sortOrder,
      }).toPromise();

      if (result.error) {
        throw result.error;
      }

      const data = result.data?.cardList;

      setCards(data?.items || []);
      setTotal(data?.total || 0);
      setCurrentPage(page);
    } catch (error) {
      console.error('[CardList] Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCards(1);
  }, [debouncedSearch, sortBy, sortOrder]);

  const handlePageChange = (page: number) => {
    fetchCards(page);
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

  const handleTableChange = (_pagination: any, _filters: any, sorter: any) => {
    const activeSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    if (activeSorter?.field && activeSorter?.order) {
      setSortBy(String(activeSorter.field));
      setSortOrder(activeSorter.order === 'ascend' ? 'asc' : 'desc');
    } else if (activeSorter && !activeSorter.order) {
      // Сортировка по колонке сброшена — возвращаемся к дефолту
      setSortBy('createdAt');
      setSortOrder('desc');
    }
  };

  const columnSortOrder = (field: string): 'ascend' | 'descend' | null =>
    sortBy === field ? (sortOrder === 'asc' ? 'ascend' : 'descend') : null;

  const handleDelete = (id: string, name: string) => {
    Modal.confirm({
      title: 'Delete Card',
      content: `Are you sure you want to delete "${name}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          const result = await client.mutation(DELETE_CARD, { id }).toPromise();

          if (result.error) {
            console.error('[CardList] Delete error:', result.error);
            message.error(`Failed to delete: ${result.error.message}`);
          } else {
            message.success('Card deleted successfully');
            // Refresh the list
            fetchCards(currentPage);
          }
        } catch (error: any) {
          console.error('[CardList] Delete error:', error);
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
            placeholder="Search by name..."
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
            <Select.Option value="cardType">Type</Select.Option>
            <Select.Option value="attackValue">Attack</Select.Option>
            <Select.Option value="defenseValue">Defense</Select.Option>
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
          dataSource={cards}
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
            title="Image"
            dataIndex="imageUrl"
            render={(imageUrl: string, record: any) => (
              <CardImage imageUrl={imageUrl || record.imageUrlRu} name={record.name} />
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
            sorter={true}
            sortOrder={columnSortOrder('name')}
          />
          <Table.Column
            dataIndex="cardType"
            title="Type"
            render={(type: string) => {
              const colors: Record<string, string> = {
                ATTACK: 'red',
                DEFENSE: 'blue',
                SCHEME: 'purple',
                MANEUVER: 'green',
              };
              return <Tag color={colors[type] || 'default'}>{type}</Tag>;
            }}
            sorter={true}
            sortOrder={columnSortOrder('cardType')}
          />
          <Table.Column
            dataIndex="subType"
            title="Sub Type"
            render={(subType: string) => subType || '-'}
          />
          <Table.Column
            dataIndex="attackValue"
            title="Attack"
            align="center"
            render={(value: number, record: any) => {
              if (record.cardType !== 'ATTACK') return '-';
              return <Tag color="red">{value}</Tag>;
            }}
            sorter={true}
            sortOrder={columnSortOrder('attackValue')}
          />
          <Table.Column
            dataIndex="defenseValue"
            title="Defense"
            align="center"
            render={(value: number, record: any) => {
              if (record.cardType !== 'DEFENSE') return '-';
              return <Tag color="blue">{value}</Tag>;
            }}
            sorter={true}
            sortOrder={columnSortOrder('defenseValue')}
          />
          <Table.Column
            dataIndex="boostValue"
            title="Boost"
            align="center"
            render={(value: number) => {
              if (!value) return '-';
              return <Tag color="orange">{value}</Tag>;
            }}
          />
          <Table.Column
            dataIndex="count"
            title="Count"
            align="center"
            render={(count: number) => <Tag>{count}</Tag>}
          />
          <Table.Column
            title="Actions"
            dataIndex="actions"
            render={(_, record: any) => (
              <Space>
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/cards/show/${record.id}`)}
                >
                  Show
                </Button>
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => navigate(`/cards/edit/${record.id}`)}
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
