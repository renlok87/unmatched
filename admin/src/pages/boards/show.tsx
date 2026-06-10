import React from 'react';
import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Descriptions, Divider, Image } from 'antd';

const { Title, Text } = Typography;

// JSON-поля приходят с бэкенда сериализованными строками — форматируем для вывода.
const formatJson = (value: unknown): string => {
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  return JSON.stringify(value, null, 2);
};

export const BoardShow: React.FC<IResourceComponentsProps> = () => {
  const { result: data, query } = useShow();

  return (
    <Show isLoading={query?.isLoading}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <div>
          <Title level={3}>{data?.name || 'Board'}</Title>
          <Text type="secondary">
            {data?.nameEn} / {data?.nameRu}
          </Text>
        </div>

        {data?.imageUrl && (
          <Image
            src={data.imageUrl}
            alt={data.name}
            style={{ maxWidth: 600, borderRadius: 8 }}
          />
        )}

        <Descriptions bordered column={1}>
          <Descriptions.Item label="ID">{data?.id || '-'}</Descriptions.Item>
          <Descriptions.Item label="Set">
            <Tag color="blue">{data?.set || '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Width">
            <Tag>{data?.width ?? '-'} cells</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Height">
            <Tag>{data?.height ?? '-'} cells</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Created At">
            {data?.createdAt ? new Date(data.createdAt).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Updated At">
            {data?.updatedAt ? new Date(data.updatedAt).toLocaleString() : '-'}
          </Descriptions.Item>
        </Descriptions>

        {data?.cells && (
          <>
            <Divider />
            <div>
              <Title level={4}>Cells</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto', maxHeight: 400 }}>
                {formatJson(data.cells)}
              </pre>
            </div>
          </>
        )}

        {data?.features && (
          <>
            <Divider />
            <div>
              <Title level={4}>Features</Title>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, overflow: 'auto', maxHeight: 400 }}>
                {formatJson(data.features)}
              </pre>
            </div>
          </>
        )}

        {data?.imageUrlDark && (
          <>
            <Divider />
            <div>
              <Title level={4}>Dark Mode Image</Title>
              <Image
                src={data.imageUrlDark}
                alt={`${data.name} Dark Mode`}
                style={{ maxWidth: 600, borderRadius: 8 }}
              />
            </div>
          </>
        )}
      </Space>
    </Show>
  );
};
