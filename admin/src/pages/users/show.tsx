import { Show } from '@refinedev/antd';
import { IResourceComponentsProps, useShow } from '@refinedev/core';
import { Typography, Space, Tag, Descriptions, Divider, Avatar, Badge } from 'antd';

const { Title, Text } = Typography;

const formatDate = (value?: string | number | null): string => {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const parsed = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : value;
  const date = new Date(parsed);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
};

export const UserShow: React.FC<IResourceComponentsProps> = () => {
  const { query, result } = useShow();
  const userData = result as any;

  return (
    <Show isLoading={query?.isLoading}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Avatar src={userData?.avatar} size={80}>
            {userData?.username?.charAt(0).toUpperCase()}
          </Avatar>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              {userData?.username}
            </Title>
            <Text type="secondary">{userData?.email}</Text>
          </div>
        </div>

        <Descriptions bordered column={1}>
          <Descriptions.Item label="ID">{userData?.id}</Descriptions.Item>
          <Descriptions.Item label="Email">{userData?.email}</Descriptions.Item>
          <Descriptions.Item label="Role">
            <Tag color={userData?.role === 'ADMIN' ? 'red' : userData?.role === 'MODERATOR' ? 'blue' : 'default'}>
              {userData?.role}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Email Verified">
            <Badge status={userData?.emailVerified ? 'success' : 'error'} text={userData?.emailVerified ? 'Yes' : 'No'} />
          </Descriptions.Item>
          <Descriptions.Item label="Status">
            <Badge status={userData?.deletedAt ? 'error' : 'success'} text={userData?.deletedAt ? 'Banned' : 'Active'} />
          </Descriptions.Item>
          <Descriptions.Item label="Created At">
            {formatDate(userData?.createdAt)}
          </Descriptions.Item>
          <Descriptions.Item label="Updated At">
            {formatDate(userData?.updatedAt)}
          </Descriptions.Item>
          {userData?.deletedAt && (
            <Descriptions.Item label="Banned At">
              {formatDate(userData.deletedAt)}
            </Descriptions.Item>
          )}
        </Descriptions>

        {userData?.stats && (
          <>
            <Divider />
            <div>
              <Title level={4}>Statistics</Title>
              <Descriptions bordered column={1}>
                <Descriptions.Item label="Games Played">{userData.stats.gamesPlayed || 0}</Descriptions.Item>
                <Descriptions.Item label="Games Won">{userData.stats.gamesWon || 0}</Descriptions.Item>
                <Descriptions.Item label="Current ELO">
                  <Tag color="green">{userData.stats.currentElo || 1200}</Tag>
                </Descriptions.Item>
              </Descriptions>
            </div>
          </>
        )}
      </Space>
    </Show>
  );
};
