import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Descriptions, Divider } from 'antd';
import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { client } from '../../providers/dataProvider';

const { Title, Text, Paragraph } = Typography;

const GET_CARD = `
  query GetCard($id: String!) {
    adminCard(id: $id) {
      id
      name
      nameEn
      nameRu
      cardType
      subType
      attackValue
      defenseValue
      boostValue
      effects
      text
      textEn
      textRu
      heroId
      count
      createdAt
      updatedAt
    }
  }
`;

export const CardShow: React.FC<IResourceComponentsProps> = () => {
  const { query } = useShow();
  const cardData = query?.data as any;
  const { id } = useParams();
  const [directData, setDirectData] = useState<any>(null);

  console.log('[CardShow] useParams id:', id);
  console.log('[CardShow] query:', query);
  console.log('[CardShow] cardData:', cardData);

  // Загружаем данные напрямую, если Refine не справляется
  useEffect(() => {
    if (id) {
      console.log('[CardShow] Fetching card directly, id:', id);
      client.query(GET_CARD, { id }).toPromise().then((result) => {
        console.log('[CardShow] Direct fetch result:', result);
        if (result.error) {
          console.error('[CardShow] GraphQL error:', result.error);
        } else {
          console.log('[CardShow] Card data:', result.data);
          setDirectData(result.data?.adminCard);
        }
      });
    }
  }, [id]);

  // Используем данные либо из directData, либо из cardData
  const data = directData || cardData;

  // Определяем цвет тега для типа карты
  const getCardTypeColor = (type: string) => {
    switch (type) {
      case 'ATTACK':
      case 'attack':
        return 'red';
      case 'DEFENSE':
      case 'defense':
        return 'blue';
      case 'SCHEME':
      case 'scheme':
        return 'purple';
      default:
        return 'green';
    }
  };

  return (
    <Show>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <div>
          <Title level={3}>{data?.name || 'Card'}</Title>
          <Text type="secondary">
            {data?.nameEn} / {data?.nameRu}
          </Text>
        </div>

        <Descriptions bordered column={2}>
          <Descriptions.Item label="ID" span={2}>{data?.id}</Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag color={getCardTypeColor(data?.cardType)}>
              {data?.cardType || 'Unknown'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Sub Type">
            {data?.subType || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Attack Value">
            <Tag>{data?.attackValue ?? '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Defense Value">
            <Tag>{data?.defenseValue ?? '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Boost Value">
            <Tag>{data?.boostValue ?? '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Count">
            <Tag>{data?.count ?? 0}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Hero ID" span={2}>
            {data?.heroId || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Created At">
            {data?.createdAt ? new Date(data.createdAt).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Updated At">
            {data?.updatedAt ? new Date(data.updatedAt).toLocaleString() : '-'}
          </Descriptions.Item>
        </Descriptions>

        {data?.text && (
          <>
            <Divider />
            <div>
              <Title level={4}>Description</Title>
              <Paragraph>{data.text}</Paragraph>
            </div>
          </>
        )}

        {data?.textEn && (
          <div>
            <Title level={4}>Description (English)</Title>
            <Paragraph>{data.textEn}</Paragraph>
          </div>
        )}

        {data?.textRu && (
          <div>
            <Title level={4}>Description (Russian)</Title>
            <Paragraph>{data.textRu}</Paragraph>
          </div>
        )}

        {data?.effects && (
          <>
            <Divider />
            <div>
              <Title level={4}>Effects</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto' }}>
                {typeof data.effects === 'string' ? data.effects : JSON.stringify(data.effects, null, 2)}
              </pre>
            </div>
          </>
        )}
      </Space>
    </Show>
  );
};
