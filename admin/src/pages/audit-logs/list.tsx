import React, { useEffect, useMemo, useState } from 'react';
import { List } from '@refinedev/antd';
import { Table, Card, Input, Select, DatePicker, Space, Tag, Drawer, Typography, Button } from 'antd';
import { SearchOutlined, EyeOutlined } from '@ant-design/icons';
import type { RangePickerProps } from 'antd/es/date-picker';
import dayjs from 'dayjs';
import { client } from '../../providers/dataProvider';
import { gql } from 'urql';

const { RangePicker } = DatePicker;
const { Text } = Typography;

const GET_AUDIT_LOGS = gql`
  query GetAuditLogs($page: Int!, $limit: Int!) {
    auditLogs(page: $page, limit: $limit) {
      items {
        id
        action
        userId
        ipAddress
        success
        timestamp
        metadata
      }
      total
    }
  }
`;

interface AuditLog {
  id: string;
  userId: string | null;
  action: string;
  ipAddress: string | null;
  success: boolean;
  timestamp: string;
  metadata: string | Record<string, any> | null;
}

// Реальные значения action из бэкенда (auth.service.ts): login, logout, register, password_reset
const actionColors: Record<string, string> = {
  login: 'gold',
  logout: 'default',
  register: 'green',
  password_reset: 'orange',
};

const formatMetadata = (metadata: AuditLog['metadata']): string | null => {
  if (metadata === null || metadata === undefined) {
    return null;
  }
  try {
    const parsed = typeof metadata === 'string' ? JSON.parse(metadata) : metadata;
    if (parsed === null || parsed === undefined) {
      return null;
    }
    return JSON.stringify(parsed, null, 2);
  } catch {
    return String(metadata);
  }
};

export const AuditLogsList: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [actionFilter, setActionFilter] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [sortBy, setSortBy] = useState<string>('timestamp');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);

  const fetchLogs = async (page: number = 1, limit: number = pageSize) => {
    setLoading(true);
    try {
      const result = await client.query(GET_AUDIT_LOGS, { page, limit }).toPromise();

      if (result.error) {
        throw result.error;
      }

      const data = result.data?.auditLogs;

      setLogs(data?.items || []);
      setTotal(data?.total || 0);
      setCurrentPage(page);
    } catch (error) {
      console.error('[AuditLogsList] Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePageChange = (page: number, size: number) => {
    if (size !== pageSize) {
      setPageSize(size);
    }
    fetchLogs(page, size);
  };

  const handleSearch = (value: string) => {
    setSearchText(value);
  };

  const handleDateRangeChange: RangePickerProps['onChange'] = (dates) => {
    setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null);
  };

  const handleSortChange = (value: string) => {
    if (value === sortBy) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(value);
      setSortOrder('asc');
    }
  };

  const handleViewDetails = (record: AuditLog) => {
    setSelectedLog(record);
    setDrawerVisible(true);
  };

  const columns = [
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (date: string) => (
        <Space direction="vertical" size={0}>
          <Text>{new Date(date).toLocaleDateString()}</Text>
          <Text type="secondary">{new Date(date).toLocaleTimeString()}</Text>
        </Space>
      )
    },
    {
      title: 'Action',
      dataIndex: 'action',
      key: 'action',
      width: 100,
      render: (action: string) => (
        <Tag color={actionColors[action?.toLowerCase()] || 'default'}>{action}</Tag>
      )
    },
    {
      title: 'User ID',
      dataIndex: 'userId',
      key: 'userId',
      width: 250,
      render: (userId: string | null) =>
        userId ? (
          <Text code style={{ fontSize: 11 }}>{userId.slice(0, 20)}...</Text>
        ) : (
          <Text type="secondary">—</Text>
        )
    },
    {
      title: 'IP Address',
      dataIndex: 'ipAddress',
      key: 'ipAddress',
      width: 140,
      render: (ip: string | null) =>
        ip ? <Text code>{ip}</Text> : <Text type="secondary">—</Text>
    },
    {
      title: 'Success',
      dataIndex: 'success',
      key: 'success',
      width: 80,
      render: (success: boolean) => (
        <Tag color={success ? 'green' : 'red'}>{success ? 'Yes' : 'No'}</Tag>
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 80,
      fixed: 'right' as const,
      render: (_: any, record: AuditLog) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => handleViewDetails(record)}
        >
          View
        </Button>
      )
    }
  ];

  // Клиентские фильтры/поиск действуют только в пределах загруженной страницы
  const hasActiveFilters = !!searchText || actionFilter.length > 0 || !!dateRange;

  const filteredData = useMemo(() => {
    const search = searchText.toLowerCase();

    return logs
      .filter((log: AuditLog) => {
        const matchesSearch = !searchText ||
          log.action.toLowerCase().includes(search) ||
          (log.userId ?? '').toLowerCase().includes(search) ||
          (log.ipAddress ?? '').toLowerCase().includes(search);

        const matchesAction =
          actionFilter.length === 0 || actionFilter.includes(log.action.toLowerCase());

        let matchesDate = true;
        if (dateRange) {
          const logDate = new Date(log.timestamp);
          matchesDate = logDate >= dateRange[0].toDate() && logDate <= dateRange[1].toDate();
        }

        return matchesSearch && matchesAction && matchesDate;
      })
      .sort((a: AuditLog, b: AuditLog) => {
        if (sortBy === 'timestamp') {
          const aTime = new Date(a.timestamp).getTime();
          const bTime = new Date(b.timestamp).getTime();
          return sortOrder === 'asc' ? aTime - bTime : bTime - aTime;
        }

        const aVal = a[sortBy as keyof AuditLog];
        const bVal = b[sortBy as keyof AuditLog];

        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return sortOrder === 'asc'
            ? aVal.localeCompare(bVal)
            : bVal.localeCompare(aVal);
        }

        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
        }

        return 0;
      });
  }, [logs, searchText, actionFilter, dateRange, sortBy, sortOrder]);

  const selectedMetadata = selectedLog ? formatMetadata(selectedLog.metadata) : null;

  return (
    <List>
      <Card style={{ marginBottom: 16 }}>
        <Space size="middle" wrap>
          <Input
            placeholder="Search logs..."
            prefix={<SearchOutlined />}
            style={{ width: 250 }}
            onChange={(e) => handleSearch(e.target.value)}
            allowClear
          />
          <Select
            mode="multiple"
            placeholder="Filter by action"
            style={{ width: 200 }}
            onChange={setActionFilter}
            allowClear
          >
            <Select.Option value="login">Login</Select.Option>
            <Select.Option value="logout">Logout</Select.Option>
            <Select.Option value="register">Register</Select.Option>
            <Select.Option value="password_reset">Password Reset</Select.Option>
          </Select>
          <RangePicker
            onChange={handleDateRangeChange}
            style={{ width: 300 }}
          />
          <Select
            placeholder="Sort by"
            value={sortBy}
            onChange={handleSortChange}
            style={{ width: 150 }}
          >
            <Select.Option value="timestamp">Timestamp</Select.Option>
            <Select.Option value="action">Action</Select.Option>
            <Select.Option value="userId">User ID</Select.Option>
            <Select.Option value="ipAddress">IP Address</Select.Option>
          </Select>
          <Button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
          >
            {sortOrder === 'asc' ? '↑ Asc' : '↓ Desc'}
          </Button>
        </Space>
      </Card>

      <Table
        loading={loading}
        dataSource={filteredData}
        rowKey="id"
        columns={columns}
        scroll={{ x: 1100 }}
        pagination={
          hasActiveFilters
            ? {
                // При активном фильтре серверная пагинация отключена:
                // фильтр работает только по загруженной странице
                pageSize,
                showTotal: (filteredTotal) => `${filteredTotal} logs (filtered, current page only)`
              }
            : {
                current: currentPage,
                pageSize: pageSize,
                total: total,
                onChange: handlePageChange,
                showSizeChanger: true,
                showTotal: (serverTotal) => `Total ${serverTotal} logs`
              }
        }
      />

      <Drawer
        title="Audit Log Details"
        placement="right"
        width={600}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {selectedLog && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Card size="small" title="Basic Information">
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <div>
                  <Text strong>ID:</Text> <Text code>{selectedLog.id}</Text>
                </div>
                <div>
                  <Text strong>Timestamp:</Text> {new Date(selectedLog.timestamp).toLocaleString()}
                </div>
                <div>
                  <Text strong>Action:</Text>{' '}
                  <Tag color={actionColors[selectedLog.action?.toLowerCase()] || 'default'}>
                    {selectedLog.action}
                  </Tag>
                </div>
                <div>
                  <Text strong>User ID:</Text>{' '}
                  {selectedLog.userId ? <Text code>{selectedLog.userId}</Text> : <Text type="secondary">—</Text>}
                </div>
                <div>
                  <Text strong>IP Address:</Text>{' '}
                  {selectedLog.ipAddress ? <Text code>{selectedLog.ipAddress}</Text> : <Text type="secondary">—</Text>}
                </div>
                <div>
                  <Text strong>Success:</Text> <Tag color={selectedLog.success ? 'green' : 'red'}>{selectedLog.success ? 'Yes' : 'No'}</Tag>
                </div>
              </Space>
            </Card>

            <Card size="small" title="Metadata">
              {selectedMetadata ? (
                <pre style={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  background: '#f5f5f5',
                  padding: 12,
                  borderRadius: 4,
                  maxHeight: 400,
                  overflow: 'auto'
                }}>
                  {selectedMetadata}
                </pre>
              ) : (
                <Text type="secondary">—</Text>
              )}
            </Card>
          </Space>
        )}
      </Drawer>
    </List>
  );
};
