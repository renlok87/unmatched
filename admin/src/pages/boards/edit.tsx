import React from 'react';
import { IResourceComponentsProps, useOne, useUpdate, useGo, useInvalidate } from '@refinedev/core';
import { Form, Input, InputNumber, Select, Divider, message, Typography, Space, Button, Spin, Tabs } from 'antd';
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

export const BoardEdit: React.FC<IResourceComponentsProps> = () => {
  const [form] = Form.useForm();
  const go = useGo();
  const invalidate = useInvalidate();
  const { id } = useParams<{ id: string }>();
  const [boardData, setBoardData] = React.useState<any>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const { mutate } = useUpdate();
  const [isUpdating, setIsUpdating] = React.useState(false);

  const [cellsValue, setCellsValue] = React.useState('[]');
  const [featuresValue, setFeaturesValue] = React.useState('{}');

  // Fetch board data directly
  React.useEffect(() => {
    if (id) {
      console.log('[BoardEdit] Fetching board with id:', id);
      setIsLoading(true);
      setError(null);

      client.query(GET_BOARD, { id }).toPromise().then((result) => {
        console.log('[BoardEdit] Fetch result:', result);
        setIsLoading(false);

        if (result.error) {
          console.error('[BoardEdit] GraphQL error:', result.error);
          setError(result.error.message || 'Failed to fetch board');
        } else if (result.data?.adminBoard) {
          const board = result.data.adminBoard;
          console.log('[BoardEdit] Board data:', board);
          setBoardData(board);
          form.setFieldsValue(board);
          setCellsValue(board.cells ? JSON.stringify(board.cells, null, 2) : '[]');
          setFeaturesValue(board.features ? JSON.stringify(board.features, null, 2) : '{}');
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

    try {
      const cells = JSON.parse(cellsValue);
      const features = JSON.parse(featuresValue);

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
    } catch (error) {
      message.error('Invalid JSON in one of the fields');
    }
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
            <Button type="primary" htmlType="submit" loading={isUpdating}>
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
