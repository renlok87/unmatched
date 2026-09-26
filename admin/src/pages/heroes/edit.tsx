import React from 'react';
import { IResourceComponentsProps, useGo, useInvalidate } from '@refinedev/core';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button, Spin } from 'antd';
import { useParams } from 'react-router-dom';
import { client } from '../../providers/dataProvider';
import { JsonEditor } from '../../components/common/JsonEditor';

const { Option } = Select;

const FIGHTER_TYPES = ['HERO', 'MINION', 'HUGE'];

// JSON-поля приходят строками (или объектами до пересборки бэка) — приводим к pretty-строке для редактора
const toPrettyJson = (value: unknown, fallback: string): string => {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value) : value;
    if (parsed === null || parsed === undefined) return fallback;
    return JSON.stringify(parsed, null, 2);
  } catch {
    return typeof value === 'string' ? value : fallback;
  }
};

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
      characterCardUrl
      miniModelUrl
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
      characterCardUrl
      miniModelUrl
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

  const [isUpdating, setIsUpdating] = React.useState(false);

  const [abilityValue, setAbilityValue] = React.useState('{}');
  const [deckCardsValue, setDeckCardsValue] = React.useState('[]');
  const [propertiesValue, setPropertiesValue] = React.useState('{}');

  // Fetch hero data directly
  React.useEffect(() => {
    if (id) {
      setIsLoading(true);
      setError(null);

      client.query(GET_HERO, { id }).toPromise().then((result) => {
        setIsLoading(false);

        if (result.error) {
          console.error('[HeroEdit] GraphQL error:', result.error);
          setError(result.error.message || 'Failed to fetch hero');
        } else if (result.data?.adminHero) {
          const hero = result.data.adminHero;
          setHeroData(hero);
          form.setFieldsValue(hero);
          setAbilityValue(toPrettyJson(hero.ability, '{}'));
          setDeckCardsValue(toPrettyJson(hero.deckCards, '[]'));
          setPropertiesValue(toPrettyJson(hero.properties, '{}'));
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

  // Валидация + компактная JSON-строка для отправки (бэкенд принимает строки)
  const toCompactJson = (value: string, label: string): string | null => {
    try {
      return JSON.stringify(JSON.parse(value));
    } catch {
      message.error(`Invalid JSON in "${label}" field`);
      return null;
    }
  };

  const onFinish = (values: any) => {
    if (!id) {
      message.error('No hero ID provided');
      return;
    }

    const ability = toCompactJson(abilityValue, 'Ability');
    if (ability === null) return;
    const deckCards = toCompactJson(deckCardsValue, 'Deck Cards');
    if (deckCards === null) return;
    const properties = toCompactJson(propertiesValue, 'Properties');
    if (properties === null) return;

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
          rules={[{ required: true, message: 'Please input a set!' }]}
        >
          <Input placeholder="Enter set name" />
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

        <Form.Item label="Card Back URL" name="imageUrl">
          <Input placeholder="Enter card back image URL" />
        </Form.Item>

        <Form.Item label="Avatar URL" name="avatarUrl">
          <Input placeholder="Enter avatar URL" />
        </Form.Item>

        <Form.Item label="Character Card URL" name="characterCardUrl">
          <Input placeholder="Enter character card image URL" />
        </Form.Item>

        <Form.Item label="Mini Model URL" name="miniModelUrl">
          <Input placeholder="Enter mini model URL" />
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
