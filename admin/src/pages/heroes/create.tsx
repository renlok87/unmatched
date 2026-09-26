import React from 'react';
import { IResourceComponentsProps, useCreate, useGo } from '@refinedev/core';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button } from 'antd';
import { JsonEditor } from '../../components/common/JsonEditor';

const { Option } = Select;

const FIGHTER_TYPES = ['HERO', 'MINION', 'HUGE'];

export const HeroCreate: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const { mutate, mutation: {
    isPending
  } } = useCreate();
  const go = useGo();

  const [abilityValue, setAbilityValue] = React.useState('{}');
  const [deckCardsValue, setDeckCardsValue] = React.useState('[]');
  const [propertiesValue, setPropertiesValue] = React.useState('{}');

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
    // JSON-поля бэкенд принимает строками — валидируем парсингом, отправляем строку как есть
    const jsonFields: Array<[string, string]> = [
      ['Ability', abilityValue],
      ['Deck Cards', deckCardsValue],
      ['Properties', propertiesValue],
    ];
    for (const [label, value] of jsonFields) {
      try {
        JSON.parse(value);
      } catch {
        message.error(`Invalid JSON in "${label}" field`);
        return;
      }
    }

    mutate(
      {
        resource: 'heroes',
        values: {
          ...values,
          ability: abilityValue,
          deckCards: deckCardsValue,
          properties: propertiesValue,
        },
      },
      {
        onSuccess: () => {
          message.success('Hero created successfully');
          go({ to: { resource: 'heroes', action: 'list' } });
        },
        onError: (error: any) => {
          message.error(`Error: ${error.message}`);
        },
      }
    );
  };

  return (
    <div style={{ padding: 24 }}>
      <h1>Create Hero</h1>
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
            <Button type="primary" htmlType="submit" loading={isPending}>
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
