import React from 'react';
import { IResourceComponentsProps, useOne, useUpdate, useGo, useInvalidate } from '@refinedev/core';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button, Spin } from 'antd';
import { useParams } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { JsonEditor } from '../../components/common/JsonEditor';

const { Option } = Select;

const SETS = [
  'Битва легенд. Том первый',
  'Битва легенд. Том второй',
  'Битва легенд. Том третий',
  'Спецвыпуск',
];

const FIGHTER_TYPES = ['HERO', 'MINION', 'HUGE'];

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

const UPDATE_HERO_MUTATION = `
  mutation UpdateHero($id: String!, $input: UpdateHeroInput!) {
    updateHero(id: $id, input: $input) {
      id
      name
      nameEn
      nameRu
      set
      health
      fighterType
      ability
      imageUrl
      avatarUrl
      createdAt
    }
  }
`;

export const HeroEdit: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const go = useGo();
  const invalidate = useInvalidate();
  const { id } = useParams<{ id: string }>();
  const [heroData, setHeroData] = React.useState<any>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const { mutate } = useUpdate();
  const [isUpdating, setIsUpdating] = React.useState(false);

  const [abilityValue, setAbilityValue] = React.useState('{}');
  const [deckCardsValue, setDeckCardsValue] = React.useState('[]');
  const [propertiesValue, setPropertiesValue] = React.useState('{}');

  // Fetch hero data directly
  React.useEffect(() => {
    if (id) {
      console.log('[HeroEdit] Fetching hero with id:', id);
      setIsLoading(true);
      setError(null);

      client.query(GET_HERO, { id }).toPromise().then((result) => {
        console.log('[HeroEdit] Fetch result:', result);
        setIsLoading(false);

        if (result.error) {
          console.error('[HeroEdit] GraphQL error:', result.error);
          setError(result.error.message || 'Failed to fetch hero');
        } else if (result.data?.adminHero) {
          const hero = result.data.adminHero;
          console.log('[HeroEdit] Hero data:', hero);
          setHeroData(hero);
          form.setFieldsValue(hero);
          setAbilityValue(hero.ability ? JSON.stringify(hero.ability, null, 2) : '{}');
          setDeckCardsValue(hero.deckCards ? JSON.stringify(hero.deckCards, null, 2) : '[]');
          setPropertiesValue(hero.properties ? JSON.stringify(hero.properties, null, 2) : '{}');
        } else {
          setError('No hero data returned');
        }
      }).catch((err) => {
        console.error('[HeroEdit] Fetch error:', err);
        setError(err.message || 'Failed to fetch hero');
        setIsLoading(false);
      });
    }
  }, [id, form]);

  const handleAbilityChange = (value: string | undefined) => {
    setAbilityValue(value || '{}');
  };

  const handleDeckCardsChange = (value: string | undefined) => {
    setDeckCardsValue(value || '[]');
  };

  const handlePropertiesChange = (value: string | undefined) => {
    setPropertiesValue(value || '{}');
  };

  const onFinish = (values: any) => {
    if (!id) {
      message.error('No hero ID provided');
      return;
    }

    try {
      const ability = JSON.parse(abilityValue);
      const deckCards = JSON.parse(deckCardsValue);
      const properties = JSON.parse(propertiesValue);

      setIsUpdating(true);

      // Direct mutation call
      client.mutation(UPDATE_HERO_MUTATION, {
        id,
        input: {
          ...values,
          ability,
          deckCards,
          properties,
        }
      }).toPromise().then((result) => {
        setIsUpdating(false);

        if (result.error) {
          console.error('[HeroEdit] Update error:', result.error);
          message.error(`Error: ${result.error.message}`);
        } else {
          message.success('Hero updated successfully');
          invalidate({ resource: 'heroes', invalidates: ['list', 'detail'] });
        }
      }).catch((err) => {
        console.error('[HeroEdit] Update mutation error:', err);
        message.error(`Error: ${err.message}`);
        setIsUpdating(false);
      });
    } catch (error) {
      message.error('Invalid JSON in one of the fields');
    }
  };

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (error && !heroData) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <h3>Error loading hero</h3>
        <p>{error}</p>
        <Button onClick={() => go({ to: { resource: 'heroes', action: 'list' } })}>
          Back to List
        </Button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Edit Hero</h1>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item
          label="Name"
          name="name"
          rules={[{ required: true, message: 'Please input hero name!' }]}
        >
          <Input placeholder="Enter hero name" />
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
          label="Set"
          name="set"
          rules={[{ required: true, message: 'Please select a set!' }]}
        >
          <Select placeholder="Select set">
            {SETS.map((set) => (
              <Option key={set} value={set}>
                {set}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          label="Health"
          name="health"
          rules={[{ required: true, message: 'Please input health!' }]}
        >
          <InputNumber min={1} max={30} style={{ width: '100%' }} placeholder="Enter health points" />
        </Form.Item>

        <Form.Item
          label="Fighter Type"
          name="fighterType"
          rules={[{ required: true, message: 'Please select fighter type!' }]}
        >
          <Select placeholder="Select fighter type">
            {FIGHTER_TYPES.map((type) => (
              <Option key={type} value={type}>
                {type}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Divider />

        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Typography.Text strong>Ability (JSON)</Typography.Text>
            <div style={{ marginTop: 8 }}>
              <JsonEditor value={abilityValue} onChange={handleAbilityChange} height="300px" />
            </div>
          </div>

          <div>
            <Typography.Text strong>Deck Cards (JSON Array)</Typography.Text>
            <div style={{ marginTop: 8 }}>
              <JsonEditor value={deckCardsValue} onChange={handleDeckCardsChange} height="300px" />
            </div>
          </div>

          <div>
            <Typography.Text strong>Properties (JSON)</Typography.Text>
            <div style={{ marginTop: 8 }}>
              <JsonEditor value={propertiesValue} onChange={handlePropertiesChange} height="300px" />
            </div>
          </div>
        </Space>

        <Divider />

        <Form.Item label="Image URL" name="imageUrl">
          <Input placeholder="Enter image URL" />
        </Form.Item>

        <Form.Item label="Avatar URL" name="avatarUrl">
          <Input placeholder="Enter avatar URL" />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={isUpdating}>
              Save
            </Button>
            <Button onClick={() => go({ to: { resource: 'heroes', action: 'list' } })}>
              Cancel
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};
