import React from 'react';
import { IResourceComponentsProps, useShow, useUpdate, useGo } from '@refinedev/core';
import { useParams } from 'react-router-dom';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button } from 'antd';
import { JsonEditor } from '../../components/common/JsonEditor';
import { client, gql } from '../../providers/dataProvider';

const { Option } = Select;
const { TextArea } = Input;

const CARD_TYPES = ['ATTACK', 'DEFENSE', 'VERSATILE', 'SCHEME', 'MANEUVER'];

const GET_HEROES_OPTIONS = gql`
  query GetHeroesOptions($page: Int!, $limit: Int!, $sortBy: String, $sortOrder: String) {
    heroList(page: $page, limit: $limit, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        name
      }
    }
  }
`;

export const CardEdit: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const go = useGo();
  const { id } = useParams();
  const { result: cardData } = useShow();
  const { mutate } = useUpdate();
  const [isMutating, setIsMutating] = React.useState(false);

  const [cardType, setCardType] = React.useState<string>(cardData?.cardType || 'ATTACK');
  const [effectsValue, setEffectsValue] = React.useState(() => {
    if (!cardData?.effects) return '[]';
    // Если effects уже строка (JSON), парсим и форматируем
    if (typeof cardData.effects === 'string') {
      try {
        const parsed = JSON.parse(cardData.effects);
        return JSON.stringify(parsed, null, 2);
      } catch {
        return cardData.effects; // Если не парсится, возвращаем как есть
      }
    }
    // Если это уже объект, сериализуем
    return JSON.stringify(cardData.effects, null, 2);
  });
  const [heroOptions, setHeroOptions] = React.useState<{ value: string; label: string }[]>([]);
  const [heroesLoading, setHeroesLoading] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    const fetchHeroes = async () => {
      setHeroesLoading(true);
      try {
        const result = await client
          .query(GET_HEROES_OPTIONS, { page: 1, limit: 100, sortBy: 'name', sortOrder: 'asc' })
          .toPromise();

        if (result.error) {
          throw result.error;
        }

        if (!cancelled) {
          setHeroOptions(
            (result.data?.heroList?.items || []).map((hero: { id: string; name: string }) => ({
              value: hero.id,
              label: hero.name,
            }))
          );
        }
      } catch (error) {
        console.error('[CardEdit] Error fetching heroes:', error);
      } finally {
        if (!cancelled) {
          setHeroesLoading(false);
        }
      }
    };
    fetchHeroes();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (cardData) {
      form.setFieldsValue(cardData);
      setCardType(cardData.cardType || 'ATTACK');
      // Обрабатываем effects - может быть строкой или объектом
      if (cardData.effects) {
        if (typeof cardData.effects === 'string') {
          try {
            const parsed = JSON.parse(cardData.effects);
            setEffectsValue(JSON.stringify(parsed, null, 2));
          } catch {
            setEffectsValue(cardData.effects);
          }
        } else {
          setEffectsValue(JSON.stringify(cardData.effects, null, 2));
        }
      } else {
        setEffectsValue('[]');
      }
    }
  }, [cardData, form]);

  const handleCardTypeChange = (value: string) => {
    setCardType(value);
  };

  const handleEffectsChange = (value: string | undefined) => {
    setEffectsValue(value || '[]');
  };

  const onFinish = (values: any) => {
    if (!id) {
      message.error('Card ID is missing');
      return;
    }

    try {
      // Парсим effects для валидации JSON
      const effectsParsed = JSON.parse(effectsValue);
      // Отправляем как строку JSON (как ожидает сервис)
      const effectsString = JSON.stringify(effectsParsed);

      setIsMutating(true);
      mutate(
        {
          resource: 'cards',
          id,
          values: {
            ...values,
            effects: effectsString,
          },
        },
        {
          onSuccess: () => {
            message.success('Card updated successfully');
            setIsMutating(false);
          },
          onError: (error: any) => {
            setIsMutating(false);
            message.error(`Error: ${error.message}`);
          },
        }
      );
    } catch (error) {
      message.error('Invalid JSON in effects field');
    }
  };

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
          <Select
            placeholder="Select hero"
            showSearch
            loading={heroesLoading}
            options={heroOptions}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
          />
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

        <Form.Item label="Banner Name" name="bannerName">
          <Input placeholder="Enter banner name (e.g., Daredevil, Any, Actor)" />
        </Form.Item>

        {(cardType === 'ATTACK' || cardType === 'VERSATILE') && (
          <Form.Item
            label="Attack Value"
            name="attackValue"
            rules={[{ required: true, message: 'Please input attack value!' }]}
          >
            <InputNumber min={0} max={20} style={{ width: '100%' }} placeholder="Enter attack value" />
          </Form.Item>
        )}

        {(cardType === 'DEFENSE' || cardType === 'VERSATILE') && (
          <Form.Item
            label="Defense Value"
            name="defenseValue"
            rules={[{ required: true, message: 'Please input defense value!' }]}
          >
            <InputNumber min={0} max={20} style={{ width: '100%' }} placeholder="Enter defense value" />
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

        <Form.Item label="Image URL (EN)" name="imageUrl">
          <Input placeholder="Enter English image URL" />
        </Form.Item>

        <Form.Item label="Image URL (RU)" name="imageUrlRu">
          <Input placeholder="Enter Russian image URL" />
        </Form.Item>

        <Divider />

        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Typography.Text strong>Effects (JSON Array)</Typography.Text>
          <JsonEditor value={effectsValue} onChange={handleEffectsChange} height="300px" />
        </Space>

        <Divider />

        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Typography.Text strong>Detailed Effects (Optional)</Typography.Text>

          <Form.Item label="Effect Immediately" name="effectImmediately">
            <TextArea rows={2} placeholder="Enter immediate effect text" />
          </Form.Item>

          <Form.Item label="Effect During Combat" name="effectDuring">
            <TextArea rows={2} placeholder="Enter during combat effect text" />
          </Form.Item>

          <Form.Item label="Effect After Attack/Defense" name="effectAfter">
            <TextArea rows={2} placeholder="Enter after attack/defense effect text" />
          </Form.Item>

          <Form.Item label="Effect Ongoing" name="effectOngoing">
            <TextArea rows={2} placeholder="Enter ongoing effect text" />
          </Form.Item>

          <Form.Item label="Effect Boost" name="effectBoost">
            <TextArea rows={2} placeholder="Enter boost effect text" />
          </Form.Item>
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
            <Button type="primary" htmlType="submit" loading={isMutating}>
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
