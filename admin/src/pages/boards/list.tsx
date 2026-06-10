import { List } from '@refinedev/antd';
import { IResourceComponentsProps } from '@refinedev/core';
import { Table, Space, Tag, Image, Typography, Button, Modal, message, Input, Select, Avatar } from 'antd';
import { EyeOutlined, EditOutlined, DeleteOutlined, SearchOutlined, PictureOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';
import { useDebounce } from '../../hooks/useDebounce';

const { Text } = Typography;

const GET_BOARDS = gql`
  query GetBoards($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    boardList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        name
        nameEn
        nameRu
        set
        width
        height
        imageUrl
        imageUrlDark
        createdAt
      }
      total
    }
  }
`;

const DELETE_BOARD = gql`
  mutation DeleteBoard($id: String!) {
    deleteBoard(id: $id)
  }
`;

export const BoardList: React.FC<IResourceComponentsProps> = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [boards, setBoards] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [sortBy, setSortBy] = useState<string>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const pageSize = 20;

  const fetchBoards = async (page: number = 1) => {
    setLoading(true);
    try {
      const result = await client.query(GET_BOARDS, {
        page,
        limit: pageSize,
        search: debouncedSearch || undefined,
        sortBy,
        sortOrder,
      }).toPromise();

      if (result.error) {
        console.error('[BoardList] GraphQL error:', result.error);
        throw result.error;
      }

      const data = result.data?.boardList;

      setBoards(data?.items || []);
      setTotal(data?.total || 0);
      setCurrentPage(page);
    } catch (error) {
      console.error('[BoardList] Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBoards(1);
  }, [debouncedSearch, sortBy, sortOrder]);

  const handlePageChange = (page: number) => {
    fetchBoards(page);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setCurrentPage(1);
  };

  const handleSortChange = (value: string) => {
    // Select.onChange не срабатывает при выборе того же значения,
    // направление переключается отдельной кнопкой Asc/Desc.
    setSortBy(value);
    setSortOrder('asc');
  };

  const handleDelete = (id: string, name: string) => {
    Modal.confirm({
      title: 'Delete Board',
      content: `Are you sure you want to delete "${name}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          const result = await client.mutation(DELETE_BOARD, { id }).toPromise();

          if (result.error) {
            console.error('[BoardList] Delete error:', result.error);
            message.error(`Failed to delete: ${result.error.message}`);
          } else {
            message.success('Board deleted successfully');
            // Refresh the list
            fetchBoards(currentPage);
          }
        } catch (error: any) {
          console.error('[BoardList] Delete error:', error);
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
            <Select.Option value="width">Width</Select.Option>
            <Select.Option value="height">Height</Select.Option>
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
          dataSource={boards}
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
            title="Preview"
            render={(url: string) =>
              url ? (
                <Image
                  src={url}
                  alt="Board"
                  width={100}
                  height={60}
                  style={{ objectFit: 'cover', borderRadius: 4 }}
                />
              ) : (
                <Avatar shape="square" size={60} icon={<PictureOutlined />} />
              )
            }
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
            dataIndex="width"
            title="Width"
            align="center"
            render={(width: number) => <Tag>{width} cells</Tag>}
          />
          <Table.Column
            dataIndex="height"
            title="Height"
            align="center"
            render={(height: number) => <Tag>{height} cells</Tag>}
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
                  onClick={() => navigate(`/boards/show/${record.id}`)}
                >
                  Show
                </Button>
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => navigate(`/boards/edit/${record.id}`)}
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
