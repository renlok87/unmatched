import { List } from '@refinedev/antd';
import { IResourceComponentsProps } from '@refinedev/core';
import { Table, Space, Tag, Image, Typography, Button, Modal, message } from 'antd';
import { EyeOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';

const { Text } = Typography;

const GET_BOARDS = gql`
  query GetBoards($page: Int!, $limit: Int!) {
    boardList(page: $page, limit: $limit) {
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
  const pageSize = 20;

  const fetchBoards = async (page: number = 1) => {
    setLoading(true);
    console.log('[BoardList] Fetching boards, page:', page);
    try {
      const result = await client.query(GET_BOARDS, { page, limit: pageSize }).toPromise();
      console.log('[BoardList] Result:', result);

      if (result.error) {
        console.error('[BoardList] GraphQL error:', result.error);
        throw result.error;
      }

      const data = result.data?.boardList;
      console.log('[BoardList] Parsed data:', data);

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
    console.log('[BoardList] Component mounted, fetching boards...');
    fetchBoards(1);
  }, []);

  const handlePageChange = (page: number) => {
    fetchBoards(page);
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
          console.log('[BoardList] Deleting board:', id);
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
          render={(url: string) => (
            <Image
              src={url || '/placeholder.png'}
              alt="Board"
              width={100}
              height={60}
              style={{ objectFit: 'cover', borderRadius: 4 }}
              fallback="/placeholder.png"
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
    </List>
  );
};
