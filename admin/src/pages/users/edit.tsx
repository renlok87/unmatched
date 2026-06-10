import React from 'react';
import { IResourceComponentsProps, useOne, useUpdate, useGo, useInvalidate } from '@refinedev/core';
import { Form, Input, Select, Divider, message, Space, Button, Popconfirm, Spin, Tag } from 'antd';
import { useParams } from 'react-router-dom';
import { client, gql } from '../../providers/dataProvider';

const { Option } = Select;

const ROLES = ['USER', 'ADMIN', 'MODERATOR'];

const BAN_USER = gql`
  mutation BanUser($id: String!) {
    banUser(id: $id)
  }
`;

const UNBAN_USER = gql`
  mutation UnbanUser($id: String!) {
    unbanUser(id: $id)
  }
`;

export const UserEdit: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const go = useGo();
  const invalidate = useInvalidate();

  const { id } = useParams<{ id: string }>();
  const userId = id ?? '';

  const queryResult = useOne({
    resource: 'users',
    id: userId,
    queryOptions: { enabled: !!userId },
  });

  const { mutate } = useUpdate();
  const [isUpdating, setIsUpdating] = React.useState(false);
  const [isBanning, setIsBanning] = React.useState(false);

  const user = queryResult?.result as any;
  const isBanned = Boolean(user?.deletedAt);

  React.useEffect(() => {
    if (user) {
      form.setFieldsValue({
        username: user.username,
        email: user.email,
        role: user.role,
        avatar: user.avatar,
      });
    }
  }, [user, form]);

  const onFinish = (values: any) => {
    setIsUpdating(true);
    mutate(
      {
        resource: 'users',
        id: userId,
        values,
      },
      {
        onSuccess: () => {
          message.success('User updated successfully');
          invalidate({ resource: 'users', invalidates: ['list', 'detail'], id: userId });
          setIsUpdating(false);
        },
        onError: (error: any) => {
          message.error(`Error: ${error.message}`);
          setIsUpdating(false);
        },
      }
    );
  };

  const handleBanToggle = async () => {
    setIsBanning(true);
    try {
      const result = await client
        .mutation(isBanned ? UNBAN_USER : BAN_USER, { id: userId })
        .toPromise();

      if (result.error) {
        throw result.error;
      }

      message.success(isBanned ? 'User unbanned successfully' : 'User banned successfully');
      invalidate({ resource: 'users', invalidates: ['list', 'detail'], id: userId });
      await queryResult?.query?.refetch();
    } catch (error: any) {
      message.error(`Error: ${error.message}`);
    } finally {
      setIsBanning(false);
    }
  };

  if (queryResult?.query?.isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Edit User</h1>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item
          label="Username"
          name="username"
          rules={[{ required: true, message: 'Please input username!' }]}
        >
          <Input placeholder="Enter username" />
        </Form.Item>

        <Form.Item
          label="Email"
          name="email"
          rules={[
            { required: true, message: 'Please input email!' },
            { type: 'email', message: 'Please enter a valid email!' },
          ]}
        >
          <Input placeholder="Enter email" />
        </Form.Item>

        <Form.Item
          label="Role"
          name="role"
          rules={[{ required: true, message: 'Please select a role!' }]}
        >
          <Select placeholder="Select role">
            {ROLES.map((role) => (
              <Option key={role} value={role}>
                {role}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="Avatar URL" name="avatar">
          <Input placeholder="Enter avatar URL" />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={isUpdating}>
              Save
            </Button>
            <Button onClick={() => go({ to: { resource: 'users', action: 'list' } })}>
              Cancel
            </Button>
          </Space>
        </Form.Item>
      </Form>

      <Divider />

      <Space align="center">
        <span>Status:</span>
        <Tag color={isBanned ? 'red' : 'green'}>{isBanned ? 'Banned' : 'Active'}</Tag>
        <Popconfirm
          title={isBanned ? 'Unban this user?' : 'Ban this user?'}
          description={
            isBanned
              ? 'The user will regain access to the platform.'
              : 'The user will lose access to the platform.'
          }
          onConfirm={handleBanToggle}
          okText="Yes"
          cancelText="No"
        >
          <Button danger={!isBanned} loading={isBanning}>
            {isBanned ? 'Unban' : 'Ban'}
          </Button>
        </Popconfirm>
      </Space>
    </div>
  );
};
