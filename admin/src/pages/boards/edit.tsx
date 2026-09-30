import React from 'react';
import { IResourceComponentsProps, useGo, useInvalidate } from '@refinedev/core';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button, Spin, Tabs, Alert } from 'antd';
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

const UPDATE_BOARD_MUTATION = `
  mutation UpdateBoard($id: String!, $input: UpdateBoardInput!) {
    updateBoard(id: $id, input: $input) {
      id
      name
      nameEn
      nameRu
      set
      width
      height
      imageUrl
      imageUrlDark
      createdAt
    }
  }
`;

// JSON-поля приходят с бэкенда сериализованными строками — парсим и
// форматируем для редактора; null/невалидное значение -> fallback.
const toPretty = (value: unknown, fallback: string): string => {
  if (value === null || value === undefined) return fallback;
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value) : value;
    return JSON.stringify(parsed, null, 2);
  } catch {
    return typeof value === 'string' ? value : fallback;
  }
};

/**
 * ENV-MAPS: доска с топологией оригинальной карты (хотя бы одна клетка несёт
 * массив links — граф пространств, по которому играет движок). Её клетки
 * генерируются tools/art/board_topology.py и сидятся
 * backend/prisma/seed-env-map-boards.ts; ручная правка в этом редакторе
 * (шаблон, width/height, JSON) рвёт граф — такая доска только для чтения.
 */
const boardHasTopology = (cells: unknown): boolean => {
  let value: unknown = cells;
  for (let i = 0; i < 2 && typeof value === 'string'; i++) {
    try {
      value = JSON.parse(value);
    } catch {
      return false;
    }
  }
  return (
    Array.isArray(value) &&
    value.some((cell) => cell !== null && typeof cell === 'object' && Array.isArray((cell as { links?: unknown }).links))
  );
};

export const BoardEdit: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const go = useGo();
  const invalidate = useInvalidate();
  const { id } = useParams<{ id: string }>();
  const [boardData, setBoardData] = React.useState<any>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [isUpdating, setIsUpdating] = React.useState(false);

  const [cellsValue, setCellsValue] = React.useState('[]');
  const [featuresValue, setFeaturesValue] = React.useState('{}');
  // ENV-MAPS: топологическая доска — только чтение (см. boardHasTopology)
  const topologyLocked = boardHasTopology(boardData?.cells);

  // Fetch board data directly
  React.useEffect(() => {
    if (id) {
      setIsLoading(true);
      setError(null);

      client.query(GET_BOARD, { id }).toPromise().then((result) => {
        setIsLoading(false);

        if (result.error) {
          console.error('[BoardEdit] GraphQL error:', result.error);
          setError(result.error.message || 'Failed to fetch board');
        } else if (result.data?.adminBoard) {
          const board = result.data.adminBoard;
          setBoardData(board);
          form.setFieldsValue(board);
          setCellsValue(toPretty(board.cells, '[]'));
          setFeaturesValue(toPretty(board.features, '{}'));
        } else {
          setError('No board data returned');
        }
      }).catch((err) => {
        console.error('[BoardEdit] Fetch error:', err);
        setError(err.message || 'Failed to fetch board');
        setIsLoading(false);
      });
    }
  }, [id, form]);

  const handleCellsChange = (value: string | undefined) => {
    setCellsValue(value || '[]');
  };

  const handleFeaturesChange = (value: string | undefined) => {
    setFeaturesValue(value || '{}');
  };

  const onFinish = (values: any) => {
    if (!id) {
      message.error('No board ID provided');
      return;
    }
    if (topologyLocked) {
      message.error('Original-map topology board is read-only');
      return;
    }

    // JSON-поля бэкенд принимает строками (String в UpdateBoardInput) —
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

    setIsUpdating(true);

    // Direct mutation call
    client.mutation(UPDATE_BOARD_MUTATION, {
      id,
      input: {
        ...values,
        cells,
        features,
      }
    }).toPromise().then((result) => {
      setIsUpdating(false);

      if (result.error) {
        console.error('[BoardEdit] Update error:', result.error);
        message.error(`Error: ${result.error.message}`);
      } else {
        message.success('Board updated successfully');
        invalidate({ resource: 'boards', invalidates: ['list', 'detail'] });
      }
    }).catch((err) => {
      console.error('[BoardEdit] Update mutation error:', err);
      message.error(`Error: ${err.message}`);
      setIsUpdating(false);
    });
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

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (error && !boardData) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <h3>Error loading board</h3>
        <p>{error}</p>
        <Button onClick={() => go({ to: { resource: 'boards', action: 'list' } })}>
          Back to List
        </Button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Edit Board</h1>
      {topologyLocked && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="Original-map topology board — read-only"
          description="Cells carry links (the graph of spaces the game engine plays on). Editing here would break the graph: regenerate the fixture with tools/art/board_topology.py and reseed with backend/prisma/seed-env-map-boards.ts."
        />
      )}
      <Form form={form} layout="vertical" onFinish={onFinish} disabled={topologyLocked}>
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
                        <button type="button" onClick={loadTemplate} disabled={topologyLocked}>
                          Load Template
                        </button>
                      </div>
                      <JsonEditor
                        value={cellsValue}
                        onChange={handleCellsChange}
                        height="400px"
                        readOnly={topologyLocked}
                      />
                    </div>

                    <div>
                      <Typography.Text strong>Features (JSON)</Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <JsonEditor
                          value={featuresValue}
                          onChange={handleFeaturesChange}
                          height="300px"
                          readOnly={topologyLocked}
                        />
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
            <Button type="primary" htmlType="submit" loading={isUpdating} disabled={topologyLocked}>
              Save
            </Button>
            <Button disabled={false} onClick={() => go({ to: { resource: 'boards', action: 'list' } })}>
              Cancel
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};
