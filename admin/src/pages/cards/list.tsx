import { List } from '@refinedev/antd';
import { IResourceComponentsProps } from '@refinedev/core';
import { Table, Space, Tag, Typography, Button, Modal, message } from 'antd';
import { EyeOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';

const { Text } = Typography;

const GET_CARDS = gql`
  query GetCards($page: Int!, $limit: Int!) {
    cardList(page: $page, limit: $limit) {
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
        heroId
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
  query GetCards($page: Int!, $limit: Int!) {
    cardList(page: $page, limit: $limit) {
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
        heroId
        createdAt
      }
      total
    }
  }
`;

export const CardList: React.FC<IResourceComponentsProps> = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [cards, setCards] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  const fetchCards = async (page: number = 1) => {
    setLoading(true);
    console.log('[CardList] Fetching cards, page:', page);
    try {
      const result = await client.query(GET_CARDS, { page, limit: pageSize }).toPromise();
      console.log('[CardList] Result:', result);

      if (result.error) {
        console.error('[CardList] GraphQL error:', result.error);
        throw result.error;
      }

      const data = result.data?.cardList;
      console.log('[CardList] Parsed data:', data);

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
    console.log('[CardList] Component mounted, fetching cards...');
    fetchCards(1);
  }, []);

  const handlePageChange = (page: number) => {
    fetchCards(page);
  };

  const handleDelete = (id: string, name: string) => {
    Modal.confirm({
      title: 'Delete Card',
      content: `Are you sure you want to delete "${name}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          console.log('[CardList] Deleting card:', id);
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
      <Table
        loading={loading}
        dataSource={cards}
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
        />
        <Table.Column
          dataIndex="defenseValue"
          title="Defense"
          align="center"
          render={(value: number, record: any) => {
            if (record.cardType !== 'DEFENSE') return '-';
            return <Tag color="blue">{value}</Tag>;
          }}
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
    </List>
  );
};
