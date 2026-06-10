import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Descriptions, Divider, Image } from 'antd';

const { Title, Text, Paragraph } = Typography;

export const CardShow: React.FC<IResourceComponentsProps> = () => {
  const { query, result } = useShow();
  const cardData = result;

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
    <Show isLoading={query.isLoading}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* Изображения карты */}
        {(cardData?.imageUrl || cardData?.imageUrlRu) && (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {cardData.imageUrl && (
              <div>
                <Title level={5}>Image (EN)</Title>
                <Image
                  src={cardData.imageUrl}
                  alt={cardData.name}
                  width={200}
                  style={{ borderRadius: 8 }}
                />
              </div>
            )}
            {cardData.imageUrlRu && (
              <div>
                <Title level={5}>Image (RU)</Title>
                <Image
                  src={cardData.imageUrlRu}
                  alt={cardData.name}
                  width={200}
                  style={{ borderRadius: 8 }}
                />
              </div>
            )}
          </div>
        )}

        <div>
          <Title level={3}>{cardData?.name || 'Card'}</Title>
          <Text type="secondary">
            {cardData?.nameEn} / {cardData?.nameRu}
          </Text>
        </div>

        <Descriptions bordered column={2}>
          <Descriptions.Item label="ID" span={2}>{cardData?.id}</Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag color={getCardTypeColor(cardData?.cardType)}>
              {cardData?.cardType || 'Unknown'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Sub Type">
            {cardData?.subType || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Banner Name" span={2}>
            {cardData?.bannerName || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Attack Value">
            <Tag>{cardData?.attackValue ?? '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Defense Value">
            <Tag>{cardData?.defenseValue ?? '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Boost Value">
            <Tag>{cardData?.boostValue ?? '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Count">
            <Tag>{cardData?.count ?? 0}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Hero ID" span={2}>
            {cardData?.heroId || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Created At">
            {cardData?.createdAt ? new Date(cardData.createdAt).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Updated At">
            {cardData?.updatedAt ? new Date(cardData.updatedAt).toLocaleString() : '-'}
          </Descriptions.Item>
        </Descriptions>

        {cardData?.text && (
          <>
            <Divider />
            <div>
              <Title level={4}>Description</Title>
              <Paragraph>{cardData.text}</Paragraph>
            </div>
          </>
        )}

        {cardData?.textEn && (
          <div>
            <Title level={4}>Description (English)</Title>
            <Paragraph>{cardData.textEn}</Paragraph>
          </div>
        )}

        {cardData?.textRu && (
          <div>
            <Title level={4}>Description (Russian)</Title>
            <Paragraph>{cardData.textRu}</Paragraph>
          </div>
        )}

        {cardData?.effects && (
          <>
            <Divider />
            <div>
              <Title level={4}>Effects</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto' }}>
                {typeof cardData.effects === 'string'
                  ? cardData.effects
                  : JSON.stringify(cardData.effects, null, 2)}
              </pre>
            </div>
          </>
        )}

        {(cardData?.effectImmediately || cardData?.effectDuring || cardData?.effectAfter ||
          cardData?.effectOngoing || cardData?.effectBoost) && (
          <>
            <Divider />
            <div>
              <Title level={4}>Detailed Effects</Title>
              {cardData.effectImmediately && (
                <>
                  <Title level={5}>Immediately</Title>
                  <Paragraph>{cardData.effectImmediately}</Paragraph>
                </>
              )}
              {cardData.effectDuring && (
                <>
                  <Title level={5}>During Combat</Title>
                  <Paragraph>{cardData.effectDuring}</Paragraph>
                </>
              )}
              {cardData.effectAfter && (
                <>
                  <Title level={5}>After Attack/Defense</Title>
                  <Paragraph>{cardData.effectAfter}</Paragraph>
                </>
              )}
              {cardData.effectOngoing && (
                <>
                  <Title level={5}>Ongoing</Title>
                  <Paragraph>{cardData.effectOngoing}</Paragraph>
                </>
              )}
              {cardData.effectBoost && (
                <>
                  <Title level={5}>Boost</Title>
                  <Paragraph>{cardData.effectBoost}</Paragraph>
                </>
              )}
            </div>
          </>
        )}

        {/* Изображения */}
        {(cardData?.imageUrl || cardData?.imageUrlRu) && (
          <>
            <Divider />
            <div>
              <Title level={4}>Images</Title>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {cardData.imageUrl && (
                  <div>
                    <div style={{ marginBottom: 8 }}>English</div>
                    <img
                      src={cardData.imageUrl}
                      alt={`${cardData.name} (EN)`}
                      style={{ maxWidth: 250, borderRadius: 8, border: '1px solid #d9d9d9' }}
                    />
                  </div>
                )}
                {cardData.imageUrlRu && (
                  <div>
                    <div style={{ marginBottom: 8 }}>Русский</div>
                    <img
                      src={cardData.imageUrlRu}
                      alt={`${cardData.name} (RU)`}
                      style={{ maxWidth: 250, borderRadius: 8, border: '1px solid #d9d9d9' }}
                    />
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </Space>
    </Show>
  );
};
