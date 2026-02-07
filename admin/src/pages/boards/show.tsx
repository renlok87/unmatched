import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Descriptions, Divider, Image } from 'antd';
import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { client } from '../../providers/dataProvider';

const { Title, Text } = Typography;

const GET_BOARD = `
  query GetBoard($id: String!) {
    adminBoard(id: $id) {
      id
      name
      nameEn
      nameRu
      set
      width
      height
      cells
      features
      imageUrl
      imageUrlDark
      createdAt
      updatedAt
    }
  }
`;

export const BoardShow: React.FC<IResourceComponentsProps> = () => {
  const { query } = useShow();
  const boardData = query?.data as any;
  const { id } = useParams();
  const [directData, setDirectData] = useState<any>(null);

  console.log('[BoardShow] useParams id:', id);
  console.log('[BoardShow] query:', query);
  console.log('[BoardShow] boardData:', boardData);

  // Загружаем данные напрямую, если Refine не справляется
  useEffect(() => {
    if (id) {
      console.log('[BoardShow] Fetching board directly, id:', id);
      client.query(GET_BOARD, { id }).toPromise().then((result) => {
        console.log('[BoardShow] Direct fetch result:', result);
        if (result.error) {
          console.error('[BoardShow] GraphQL error:', result.error);
        } else {
          console.log('[BoardShow] Board data:', result.data);
          setDirectData(result.data?.adminBoard);
        }
      });
    }
  }, [id]);

  // Используем данные либо из directData, либо из boardData
  const data = directData || boardData;

  return (
    <Show>
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
                {typeof data.cells === 'string' ? data.cells : JSON.stringify(data.cells, null, 2)}
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
                {typeof data.features === 'string' ? data.features : JSON.stringify(data.features, null, 2)}
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