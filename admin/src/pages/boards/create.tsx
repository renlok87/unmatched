import React from 'react';
import { IResourceComponentsProps, useCreate, useGo } from '@refinedev/core';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button, Tabs } from 'antd';
import { JsonEditor } from '../../components/common/JsonEditor';

const { Option } = Select;

const SETS = [
  'Битва легенд. Том первый',
  'Битва легенд. Том второй',
  'Битва легенд. Том третий',
  'Спецвыпуск',
];

export const BoardCreate: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const { mutate, mutation: {
    isPending
  } } = useCreate();
  const go = useGo();

  const [cellsValue, setCellsValue] = React.useState('[]');
  const [featuresValue, setFeaturesValue] = React.useState('{}');

  const handleCellsChange = (value: string | undefined) => {
    setCellsValue(value || '[]');
  };

  const handleFeaturesChange = (value: string | undefined) => {
    setFeaturesValue(value || '{}');
  };

  const onFinish = (values: any) => {
    // JSON-поля бэкенд принимает строками (String в CreateBoardInput) —
    // валидируем парсингом и отправляем компактную строку.
    let cells: string;
    let features: string;
    try {
      cells = JSON.stringify(JSON.parse(cellsValue));
    } catch {
      message.error('Invalid JSON in Cells field');
      return;
    }
    try {
      features = JSON.stringify(JSON.parse(featuresValue));
    } catch {
      message.error('Invalid JSON in Features field');
      return;
    }

    mutate(
      {
        resource: 'boards',
        values: {
          ...values,
          cells,
          features,
        },
      },
      {
        onSuccess: () => {
          message.success('Board created successfully');
          go({ to: { resource: 'boards', action: 'list' } });
        },
        onError: (error: any) => {
          message.error(`Error: ${error.message}`);
        },
      }
    );
  };

  const cellsTemplate = {
    cells: [
      {
        x: 0,
        y: 0,
        type: 'normal',
        zone: 'p1-start',
        connections: ['right', 'down'],
      },
    ],
    features: {
      secretPassages: [],
      doors: [],
      highGround: [],
    },
  };

  const loadTemplate = () => {
    setCellsValue(JSON.stringify(cellsTemplate.cells, null, 2));
    setFeaturesValue(JSON.stringify(cellsTemplate.features, null, 2));
  };

  return (
    <div style={{ padding: 24 }}>
      <h1>Create Board</h1>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item
          label="Name"
          name="name"
          rules={[{ required: true, message: 'Please input board name!' }]}
        >
          <Input placeholder="Enter board name" />
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
          label="Width"
          name="width"
          rules={[{ required: true, message: 'Please input board width!' }]}
        >
          <InputNumber min={3} max={10} style={{ width: '100%' }} placeholder="Enter width (3-10)" />
        </Form.Item>

        <Form.Item
          label="Height"
          name="height"
          rules={[{ required: true, message: 'Please input board height!' }]}
        >
          <InputNumber min={3} max={10} style={{ width: '100%' }} placeholder="Enter height (3-10)" />
        </Form.Item>

        <Divider />

        <Tabs
          defaultActiveKey="json"
          items={[
            {
              key: 'json',
              label: 'JSON Editor',
              children: (
                <>
                  <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <div>
                      <Typography.Text strong>Cells (JSON Array)</Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <button type="button" onClick={loadTemplate}>
                          Load Template
                        </button>
                      </div>
                      <JsonEditor value={cellsValue} onChange={handleCellsChange} height="400px" />
                    </div>

                    <div>
                      <Typography.Text strong>Features (JSON)</Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <JsonEditor value={featuresValue} onChange={handleFeaturesChange} height="300px" />
                      </div>
                    </div>
                  </Space>
                </>
              ),
            },
          ]}
        />

        <Divider />

        <Form.Item label="Image URL" name="imageUrl">
          <Input placeholder="Enter image URL" />
        </Form.Item>

        <Form.Item label="Image URL (Dark Mode)" name="imageUrlDark">
          <Input placeholder="Enter image URL for dark mode" />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={isPending}>
              Save
            </Button>
            <Button onClick={() => go({ to: { resource: 'boards', action: 'list' } })}>
              Cancel
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};
