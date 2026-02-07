import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Image, Descriptions, Divider } from 'antd';
import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { client } from '../../providers/dataProvider';

const { Title, Text } = Typography;

const GET_HERO = `
  query GetHero($id: String!) {
    adminHero(id: $id) {
      id
      name
      nameEn
      nameRu
      set
      health
      fighterType
      ability
      deckCards
      properties
      imageUrl
      avatarUrl
      createdAt
      updatedAt
    }
  }
`;

export const HeroShow: React.FC<IResourceComponentsProps> = () => {
  const { query } = useShow();
  const heroData = query?.data as any;
  const { id } = useParams();
  const [directData, setDirectData] = useState<any>(null);

  console.log('[HeroShow] useParams id:', id);
  console.log('[HeroShow] query:', query);
  console.log('[HeroShow] heroData:', heroData);

  // Загружаем данные напрямую, если Refine не справляется
  useEffect(() => {
    if (id) {
      console.log('[HeroShow] Fetching hero directly, id:', id);
      client.query(GET_HERO, { id }).toPromise().then((result) => {
        console.log('[HeroShow] Direct fetch result:', result);
        if (result.error) {
          console.error('[HeroShow] GraphQL error:', result.error);
        } else {
          console.log('[HeroShow] Hero data:', result.data);
          setDirectData(result.data?.adminHero);
        }
      });
    }
  }, [id]);

  // Используем данные либо из directData, либо из heroData
  const data = directData || heroData;

  return (
    <Show>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <div>
          <Title level={3}>{data?.name || 'Hero'}</Title>
          <Text type="secondary">
            {data?.nameEn} / {data?.nameRu}
          </Text>
        </div>

        {data?.imageUrl && (
          <Image
            src={data.imageUrl}
            alt={data.name}
            style={{ maxWidth: 400, borderRadius: 8 }}
          />
        )}

        <Descriptions bordered column={1}>
          <Descriptions.Item label="ID">{data?.id || '-'}</Descriptions.Item>
          <Descriptions.Item label="Set">
            <Tag color="blue">{data?.set || '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Health">
            <Tag color={data?.health > 20 ? 'green' : data?.health > 10 ? 'orange' : 'red'}>
              {data?.health ?? '-'} HP
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Fighter Type">
            <Tag color={data?.fighterType === 'HERO' ? 'purple' : data?.fighterType === 'MINION' ? 'blue' : 'orange'}>
              {data?.fighterType || '-'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Created At">
            {data?.createdAt ? new Date(data.createdAt).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Updated At">
            {data?.updatedAt ? new Date(data.updatedAt).toLocaleString() : '-'}
          </Descriptions.Item>
        </Descriptions>

        {data?.ability && (
          <>
            <Divider />
            <div>
              <Title level={4}>Ability</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto' }}>
                {typeof data.ability === 'string' ? data.ability : JSON.stringify(data.ability, null, 2)}
              </pre>
            </div>
          </>
        )}

        {data?.deckCards && (
          <>
            <Divider />
            <div>
              <Title level={4}>Deck Cards</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto' }}>
                {typeof data.deckCards === 'string' ? data.deckCards : JSON.stringify(data.deckCards, null, 2)}
              </pre>
            </div>
          </>
        )}

        {data?.properties && (
          <>
            <Divider />
            <div>
              <Title level={4}>Properties</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto' }}>
                {typeof data.properties === 'string' ? data.properties : JSON.stringify(data.properties, null, 2)}
              </pre>
            </div>
          </>
        )}

        {data?.avatarUrl && (
          <>
            <Divider />
            <div>
              <Title level={4}>Avatar</Title>
              <Image
                src={data.avatarUrl}
                alt={`${data.name} Avatar`}
                width={100}
                style={{ borderRadius: 50 }}
              />
            </div>
          </>
        )}
      </Space>
    </Show>
  );
};