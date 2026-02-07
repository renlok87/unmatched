import { List } from '@refinedev/antd';
import { IResourceComponentsProps } from '@refinedev/core';
import { Table, Space, Tag, Image, Typography, Button, Modal, message } from 'antd';
import { EyeOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';

const { Text } = Typography;

const GET_HEROES = gql`
  query GetHeroes($page: Int!, $limit: Int!) {
    heroList(page: $page, limit: $limit) {
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
  const pageSize = 20;

  const fetchHeroes = async (page: number = 1) => {
    setLoading(true);
    console.log('[HeroList] Fetching heroes, page:', page);
    try {
      const result = await client.query(GET_HEROES, { page, limit: pageSize }).toPromise();
      console.log('[HeroList] Result:', result);

      if (result.error) {
        console.error('[HeroList] GraphQL error:', result.error);
        throw result.error;
      }

      const data = result.data?.heroList;
      console.log('[HeroList] Parsed data:', data);

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
    console.log('[HeroList] Component mounted, fetching heroes...');
    fetchHeroes(1);
  }, []);

  const handlePageChange = (page: number) => {
    fetchHeroes(page);
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
          console.log('[HeroList] Deleting hero:', id);
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
            <Image
              src={url || '/placeholder.png'}
              alt="Hero"
              width={50}
              height={50}
              style={{ objectFit: 'cover', borderRadius: 6 }}
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
    </List>
  );
};
