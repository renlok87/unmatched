import React from 'react';
import { IResourceComponentsProps, useOne, useUpdate, useGo, useInvalidate } from '@refinedev/core';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button, Spin } from 'antd';
import { useParams } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { JsonEditor } from '../../components/common/JsonEditor';

const { Option } = Select;
const { TextArea } = Input;

const CARD_TYPES = ['ATTACK', 'DEFENSE', 'SCHEME', 'MANEUVER'];

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

const UPDATE_CARD_MUTATION = `
  mutation UpdateCard($id: String!, $input: UpdateCardInput!) {
    updateCard(id: $id, input: $input) {
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
  }
`;

export const CardEdit: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const go = useGo();
  const invalidate = useInvalidate();
  const { id } = useParams<{ id: string }>();
  const [cardData, setCardData] = React.useState<any>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const { mutate } = useUpdate();
  const [isUpdating, setIsUpdating] = React.useState(false);

  const [cardType, setCardType] = React.useState<string>('ATTACK');
  const [effectsValue, setEffectsValue] = React.useState('[]');

  // Fetch card data directly
  React.useEffect(() => {
    if (id) {
      console.log('[CardEdit] Fetching card with id:', id);
      setIsLoading(true);
      setError(null);

      client.query(GET_CARD, { id }).toPromise().then((result) => {
        console.log('[CardEdit] Fetch result:', result);
        setIsLoading(false);

        if (result.error) {
          console.error('[CardEdit] GraphQL error:', result.error);
          setError(result.error.message || 'Failed to fetch card');
        } else if (result.data?.adminCard) {
          const card = result.data.adminCard;
          console.log('[CardEdit] Card data:', card);
          setCardData(card);
          form.setFieldsValue(card);
          setCardType(card.cardType || 'ATTACK');
          setEffectsValue(card.effects ? JSON.stringify(card.effects, null, 2) : '[]');
        } else {
          setError('No card data returned');
        }
      }).catch((err) => {
        console.error('[CardEdit] Fetch error:', err);
        setError(err.message || 'Failed to fetch card');
        setIsLoading(false);
      });
    }
  }, [id, form]);

  const handleCardTypeChange = (value: string) => {
    setCardType(value);
  };

  const handleEffectsChange = (value: string | undefined) => {
    setEffectsValue(value || '[]');
  };

  const onFinish = (values: any) => {
    if (!id) {
      message.error('No card ID provided');
      return;
    }

    try {
      const effects = JSON.parse(effectsValue);

      setIsUpdating(true);

      // Direct mutation call
      client.mutation(UPDATE_CARD_MUTATION, {
        id,
        input: {
          ...values,
          effects,
        }
      }).toPromise().then((result) => {
        setIsUpdating(false);

        if (result.error) {
          console.error('[CardEdit] Update error:', result.error);
          message.error(`Error: ${result.error.message}`);
        } else {
          message.success('Card updated successfully');
          invalidate({ resource: 'cards', invalidates: ['list', 'detail'] });
        }
      }).catch((err) => {
        console.error('[CardEdit] Update mutation error:', err);
        message.error(`Error: ${err.message}`);
        setIsUpdating(false);
      });
    } catch (error) {
      message.error('Invalid JSON in effects field');
    }
  };

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (error && !cardData) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <h3>Error loading card</h3>
        <p>{error}</p>
        <Button onClick={() => go({ to: { resource: 'cards', action: 'list' } })}>
          Back to List
        </Button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Edit Card</h1>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item
          label="Name"
          name="name"
          rules={[{ required: true, message: 'Please input card name!' }]}
        >
          <Input placeholder="Enter card name" />
        </Form.Item>

        <Form.Item
          label="Name (English)"
          name="nameEn"
          rules={[{ required: true, message: 'Please input English name!' }]}
        >
          <Input placeholder="Enter English name" />
        </Form.Item>

        <Form.Item
          label="Name (Russian)"
          name="nameRu"
          rules={[{ required: true, message: 'Please input Russian name!' }]}
        >
          <Input placeholder="Enter Russian name" />
        </Form.Item>

        <Form.Item
          label="Hero"
          name="heroId"
          rules={[{ required: true, message: 'Please select a hero!' }]}
        >
          <Select placeholder="Select hero">
            <Option value="1">Daredevil</Option>
            <Option value="2">Ms. Marvel</Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="Card Type"
          name="cardType"
          rules={[{ required: true, message: 'Please select card type!' }]}
        >
          <Select placeholder="Select card type" onChange={handleCardTypeChange}>
            {CARD_TYPES.map((type) => (
              <Option key={type} value={type}>
                {type}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="Sub Type" name="subType">
          <Input placeholder="Enter sub type (optional)" />
        </Form.Item>

        {cardType === 'ATTACK' && (
          <Form.Item
            label="Attack Value"
            name="attackValue"
            rules={[{ required: true, message: 'Please input attack value!' }]}
          >
            <InputNumber min={1} max={20} style={{ width: '100%' }} placeholder="Enter attack value" />
          </Form.Item>
        )}

        {cardType === 'DEFENSE' && (
          <Form.Item
            label="Defense Value"
            name="defenseValue"
            rules={[{ required: true, message: 'Please input defense value!' }]}
          >
            <InputNumber min={1} max={20} style={{ width: '100%' }} placeholder="Enter defense value" />
          </Form.Item>
        )}

        <Form.Item label="Boost Value" name="boostValue">
          <InputNumber min={0} max={10} style={{ width: '100%' }} placeholder="Enter boost value (optional)" />
        </Form.Item>

        <Form.Item
          label="Count"
          name="count"
          rules={[{ required: true, message: 'Please input card count!' }]}
        >
          <InputNumber min={1} max={10} style={{ width: '100%' }} placeholder="Enter card count in deck" />
        </Form.Item>

        <Divider />

        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Typography.Text strong>Effects (JSON Array)</Typography.Text>
          <JsonEditor value={effectsValue} onChange={handleEffectsChange} height="300px" />
        </Space>

        <Divider />

        <Form.Item label="Description" name="text">
          <TextArea rows={4} placeholder="Enter card description" />
        </Form.Item>

        <Form.Item label="Description (English)" name="textEn">
          <TextArea rows={4} placeholder="Enter card description in English" />
        </Form.Item>

        <Form.Item label="Description (Russian)" name="textRu">
          <TextArea rows={4} placeholder="Enter card description in Russian" />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={isUpdating}>
              Save
            </Button>
            <Button onClick={() => go({ to: { resource: 'cards', action: 'list' } })}>
              Cancel
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};
