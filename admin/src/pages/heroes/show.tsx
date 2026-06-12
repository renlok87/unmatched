import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Image, Descriptions, Divider, Card as AntCard, Row, Col } from 'antd';

const { Title, Text, Paragraph } = Typography;

const parseJson = (value: unknown): any => {
  if (value == null) return null;
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

const cardTypeColor = (type?: string) =>
  type === 'ATTACK' ? 'red' : type === 'DEFENSE' ? 'blue' : type === 'VERSATILE' ? 'purple' : type === 'SCHEME' ? 'green' : 'orange';

export const HeroShow: React.FC<IResourceComponentsProps> = () => {
  const { query, result } = useShow();
  const data = result as any;

  const ability = parseJson(data?.ability);
  const sidekicks = parseJson(data?.sidekicks);
  const additionalMinis = parseJson(data?.additionalMinis);
  const deckCards = parseJson(data?.deckCards);
  const properties = parseJson(data?.properties);

  return (
    <Show isLoading={query.isLoading}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <div>
          <Title level={3} style={{ marginBottom: 0 }}>{data?.name || 'Hero'}</Title>
          <Text type="secondary">
            {data?.nameEn} / {data?.nameRu}
          </Text>
        </div>

        <Space size="large" align="start" wrap>
          {data?.imageUrl && (
            <div>
              <Text type="secondary">Image</Text>
              <br />
              <Image src={data.imageUrl} alt={data.name} style={{ maxWidth: 300, borderRadius: 8 }} />
            </div>
          )}
          {data?.characterCardUrl && (
            <div>
              <Text type="secondary">Character Card</Text>
              <br />
              <Image src={data.characterCardUrl} alt={`${data.name} character card`} style={{ maxWidth: 300, borderRadius: 8 }} />
            </div>
          )}
          {data?.avatarUrl && (
            <div>
              <Text type="secondary">Avatar</Text>
              <br />
              <Image src={data.avatarUrl} alt={`${data.name} avatar`} width={100} style={{ borderRadius: 50 }} />
            </div>
          )}
        </Space>

        <Descriptions bordered column={1} size="small">
          <Descriptions.Item label="ID">{data?.id || '-'}</Descriptions.Item>
          <Descriptions.Item label="Set">
            <Tag color="blue">{data?.set || '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Health">
            <Tag color={data?.health > 20 ? 'green' : data?.health > 10 ? 'orange' : 'red'}>
              {data?.health ?? '-'} HP
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Movement">{data?.movement ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="Fighter Type">
            <Tag color={data?.fighterType === 'HERO' ? 'purple' : data?.fighterType === 'MINION' ? 'blue' : 'orange'}>
              {data?.fighterType || '-'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Color">
            {data?.color ? (
              <Space>
                <span
                  style={{
                    display: 'inline-block',
                    width: 16,
                    height: 16,
                    borderRadius: 4,
                    background: data.color,
                    border: '1px solid #d9d9d9',
                    verticalAlign: 'middle',
                  }}
                />
                <Text code>{data.color}</Text>
              </Space>
            ) : (
              '-'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Has Tokens">
            <Tag color={data?.hasTokens ? 'green' : 'default'}>{data?.hasTokens ? 'Yes' : 'No'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Mini Model (3D)">
            {data?.miniModelUrl ? (
              <a href={data.miniModelUrl} target="_blank" rel="noreferrer">
                {data.miniModelUrl}
              </a>
            ) : (
              '-'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Created At">
            {data?.createdAt ? new Date(data.createdAt).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Updated At">
            {data?.updatedAt ? new Date(data.updatedAt).toLocaleString() : '-'}
          </Descriptions.Item>
        </Descriptions>

        {ability && (
          <>
            <Divider />
            <div>
              <Title level={4}>Ability</Title>
              {typeof ability === 'object' ? (
                <AntCard size="small">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {ability.name && <Text strong>{ability.name}</Text>}
                    <Space size="small" wrap>
                      {ability.type && <Tag color="purple">{ability.type}</Tag>}
                      {ability.timing && <Tag color="cyan">{ability.timing}</Tag>}
                    </Space>
                    {(ability.description || ability.text) && (
                      <Paragraph style={{ marginBottom: 0 }}>{ability.description || ability.text}</Paragraph>
                    )}
                    {ability.effect &&
                      typeof ability.effect === 'string' &&
                      ability.effect !== (ability.description || ability.text) && (
                        <Text type="secondary">{ability.effect}</Text>
                      )}
                    <details>
                      <summary style={{ cursor: 'pointer', color: '#888' }}>Raw JSON</summary>
                      <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, overflow: 'auto' }}>
                        {JSON.stringify(ability, null, 2)}
                      </pre>
                    </details>
                  </Space>
                </AntCard>
              ) : (
                <Paragraph>{String(ability)}</Paragraph>
              )}
            </div>
          </>
        )}

        {Array.isArray(sidekicks) && sidekicks.length > 0 && (
          <>
            <Divider />
            <div>
              <Title level={4}>Sidekicks ({sidekicks.length})</Title>
              <Row gutter={[12, 12]}>
                {sidekicks.map((sk: any, i: number) => (
                  <Col key={i} xs={24} sm={12} md={8}>
                    <AntCard size="small">
                      <Space align="start">
                        {sk.avatarUrl && (
                          <Image src={sk.avatarUrl} alt={sk.name} width={48} style={{ borderRadius: 24 }} />
                        )}
                        <Space direction="vertical" size={2}>
                          <Text strong>{sk.name || `Sidekick ${i + 1}`}</Text>
                          <Space size="small" wrap>
                            {sk.health != null && <Tag color="red">{sk.health} HP</Tag>}
                            {sk.movement != null && <Tag color="blue">Move {sk.movement}</Tag>}
                            {sk.attackType && <Tag color="orange">{sk.attackType}</Tag>}
                            {sk.count != null && <Tag>x{sk.count}</Tag>}
                          </Space>
                        </Space>
                      </Space>
                    </AntCard>
                  </Col>
                ))}
              </Row>
            </div>
          </>
        )}

        {Array.isArray(additionalMinis) && additionalMinis.length > 0 && (
          <>
            <Divider />
            <div>
              <Title level={4}>Additional Minis ({additionalMinis.length})</Title>
              <Space size="middle" wrap>
                {additionalMinis.map((mini: any, i: number) => (
                  <Space key={i} direction="vertical" size={2}>
                    {mini.imageUrl && (
                      <Image src={mini.imageUrl} alt={`Mini ${i + 1}`} width={100} style={{ borderRadius: 8 }} />
                    )}
                    {mini.modelUrl && (
                      <a href={mini.modelUrl} target="_blank" rel="noreferrer">
                        3D model
                      </a>
                    )}
                  </Space>
                ))}
              </Space>
            </div>
          </>
        )}

        {data?.cards && data.cards.length > 0 && (
          <>
            <Divider />
            <div>
              <Title level={4}>
                Cards ({data.cards.length} unique, {data.cards.reduce((sum: number, c: any) => sum + (c.count || 0), 0)} total)
              </Title>
              <Row gutter={[12, 12]}>
                {data.cards.map((card: any) => (
                  <Col key={card.id} xs={24} md={12}>
                    <AntCard
                      size="small"
                      style={{ height: '100%', cursor: 'pointer' }}
                      onClick={() => window.open(`/cards/show/${card.id}`, '_blank')}
                    >
                      <Space align="start" style={{ width: '100%' }}>
                        {(card.imageUrlRu || card.imageUrl) && (
                          <span onClick={(e) => e.stopPropagation()}>
                            <Image
                            src={card.imageUrlRu || card.imageUrl}
                            alt={card.name}
                            width={70}
                            style={{ borderRadius: 4 }}
                            />
                          </span>
                        )}
                        <Space direction="vertical" size={2} style={{ flex: 1 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                            <Text strong>{card.name}</Text>
                            <Tag color={cardTypeColor(card.cardType)}>
                              {card.cardType} x{card.count}
                            </Tag>
                          </div>
                          {card.bannerName && <Text type="secondary">{card.bannerName}</Text>}
                          {(card.attackValue != null || card.defenseValue != null || card.boostValue != null) && (
                            <Text type="secondary">
                              {card.attackValue != null && `⚔️ ${card.attackValue} `}
                              {card.defenseValue != null && `🛡️ ${card.defenseValue} `}
                              {card.boostValue != null && `⬆️ ${card.boostValue}`}
                            </Text>
                          )}
                          {(card.textRu || card.text || card.textEn) && (
                            <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                              {card.textRu || card.text || card.textEn}
                            </Text>
                          )}
                        </Space>
                      </Space>
                    </AntCard>
                  </Col>
                ))}
              </Row>
            </div>
          </>
        )}

        {deckCards && (
          <>
            <Divider />
            <div>
              <Title level={4}>Deck Cards (raw)</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto' }}>
                {typeof deckCards === 'string' ? deckCards : JSON.stringify(deckCards, null, 2)}
              </pre>
            </div>
          </>
        )}

        {properties && (
          <>
            <Divider />
            <div>
              <Title level={4}>Properties</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto' }}>
                {typeof properties === 'string' ? properties : JSON.stringify(properties, null, 2)}
              </pre>
            </div>
          </>
        )}
      </Space>
    </Show>
  );
};
