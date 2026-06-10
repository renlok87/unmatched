import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Image, Descriptions, Divider } from 'antd';

const { Title, Text } = Typography;

export const HeroShow: React.FC<IResourceComponentsProps> = () => {
  const { query, result } = useShow();
  const data = result as any;

  return (
    <Show isLoading={query.isLoading}>
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

        {data?.cards && data.cards.length > 0 && (
          <>
            <Divider />
            <div>
              <Title level={4}>Cards ({data.cards.length})</Title>
              <Space direction="vertical" style={{ width: '100%' }}>
                {data.cards.map((card: any) => (
                  <div
                    key={card.id}
                    style={{
                      background: '#fafafa',
                      border: '1px solid #d9d9d9',
                      borderRadius: 6,
                      padding: 12,
                    }}
                  >
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text strong>{card.name}</Text>
                        <Tag color={card.cardType === 'ATTACK' ? 'red' : card.cardType === 'DEFENSE' ? 'blue' : card.cardType === 'SCHEME' ? 'green' : 'orange'}>
                          {card.cardType} x{card.count}
                        </Tag>
                      </div>
                      {(card.attackValue || card.defenseValue || card.boostValue) && (
                        <Text type="secondary">
                          {card.attackValue && `⚔️ ${card.attackValue}`}
                          {card.defenseValue && ` 🛡️ ${card.defenseValue}`}
                          {card.boostValue && ` ⬆️ ${card.boostValue}`}
                        </Text>
                      )}
                      {card.text && (
                        <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                          {card.text}
                        </Text>
                      )}
                    </Space>
                  </div>
                ))}
              </Space>
            </div>
          </>
        )}

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