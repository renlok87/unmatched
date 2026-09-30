import React, { useMemo } from 'react';
import { Alert, Button, Card, Descriptions, Empty, Space, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ArtHubData, PlanTaskView } from '../../../../art-hub/types';
import { FileActions, FileTable, LongText, StatusTag, useArtHubUi } from '../components/common';
import { formatTime, timeAgo } from '../format';

const { Text } = Typography;

const TASK_STATUS: Record<string, { label: string; color: string }> = {
  done: { label: 'готово', color: 'green' },
  in_progress: { label: 'в работе', color: 'processing' },
  open: { label: 'открыто', color: 'default' },
  blocked: { label: 'заблокировано', color: 'red' },
  superseded: { label: 'заменено', color: 'default' },
};

export const TaskStatusTag: React.FC<{ status?: string; count?: number }> = ({ status, count }) => {
  const s = status ? TASK_STATUS[status] : undefined;
  return (
    <Tooltip title={`status: ${status ?? '—'}`}>
      <Tag color={s?.color ?? 'default'} style={status === 'superseded' ? { textDecoration: 'line-through' } : undefined}>
        {s?.label ?? status ?? '—'}
        {count !== undefined ? ` · ${count}` : ''}
      </Tag>
    </Tooltip>
  );
};

const TRACK_LABEL: Record<string, string> = { pipeline: 'пайплайн', art: 'арт', tech: 'тех', closing: 'закрытие' };

export const PlanSection: React.FC<{ data: ArtHubData }> = ({ data }) => {
  const ui = useArtHubUi();
  const plan = data.plan;
  const pages = useMemo(() => new Map([...data.characters, ...data.props].map((p) => [p.id, p.shortName])), [data]);

  if (!plan?.exists) {
    return (
      <Space direction="vertical" size={12} style={{ width: '100%' }} data-testid="art-hub-plan">
        <Alert
          type="info"
          showIcon
          message="Статус плана ещё не записан"
          description={
            <span>
              Файла <Text code>{plan?.file.path ?? 'docs/art-pipeline/plan-status.json'}</Text> пока нет. Его пишет трек plan (схема{' '}
              <Text code>unmatched-plan-status/v1</Text>: задачи P0/P1, ART-1…5, волны 0–7 и 5c-B со статусами, доказательствами и
              следующим шагом). Раздел обновится сам, как только файл появится.
            </span>
          }
        />
        <Empty description="Задач нет" />
      </Space>
    );
  }

  const tracks = [...new Set(plan.tasks.map((t) => t.track).filter((t): t is string => Boolean(t)))];
  const statuses = [...new Set(plan.tasks.map((t) => t.status))];
  const columns: ColumnsType<PlanTaskView> = [
    {
      title: 'Задача',
      key: 'id',
      width: 260,
      render: (_, t) => (
        <div>
          <Space size={4} wrap>
            <Tag color="geekblue">{t.id}</Tag>
            {t.source ? <Text type="secondary" style={{ fontSize: 11 }}>{t.source}</Text> : null}
          </Space>
          <div>
            <Text strong>{t.title}</Text>
          </div>
          {t.warnings.map((w) => (
            <div key={w}>
              <Text type="danger" style={{ fontSize: 12 }}>⚠ {w}</Text>
            </div>
          ))}
        </div>
      ),
    },
    {
      title: 'Трек',
      dataIndex: 'track',
      width: 100,
      filters: tracks.map((t) => ({ text: TRACK_LABEL[t] ?? t, value: t })),
      onFilter: (v, t) => t.track === v,
      render: (v?: string) => (v ? <Tag>{TRACK_LABEL[v] ?? v}</Tag> : '—'),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      width: 130,
      filters: statuses.map((s) => ({ text: TASK_STATUS[s]?.label ?? s, value: s })),
      onFilter: (v, t) => t.status === v,
      render: (v: string) => <TaskStatusTag status={v} />,
    },
    { title: 'Арт-статус', dataIndex: 'artStatus', width: 190, render: (v: string | null) => (v ? <StatusTag status={v} /> : <Text type="secondary">—</Text>) },
    {
      title: 'Следующий шаг / блокер',
      key: 'next',
      width: 340,
      render: (_, t) => (
        <Space direction="vertical" size={2} style={{ width: '100%' }}>
          <LongText text={t.next} rows={2} />
          {t.blocker ? <Text type="danger" style={{ fontSize: 12 }}>Блокер: {t.blocker}</Text> : null}
        </Space>
      ),
    },
    {
      title: 'Ассеты',
      key: 'assets',
      width: 190,
      render: (_, t) =>
        t.assets.length ? (
          <Space size={2} wrap>
            {t.assets.slice(0, 3).map((a) =>
              pages.has(a) ? (
                <Button key={a} size="small" type="link" style={{ padding: 0 }} onClick={() => ui.openPage(a)}>
                  {pages.get(a)}
                </Button>
              ) : (
                <Tag key={a}>{a}</Tag>
              ),
            )}
            {t.assets.length > 3 ? (
              <Tooltip title={t.assets.slice(3).map((a) => pages.get(a) ?? a).join(', ')}>
                <Tag>+{t.assets.length - 3}</Tag>
              </Tooltip>
            ) : null}
          </Space>
        ) : (
          '—'
        ),
    },
    { title: 'Доказ.', key: 'ev', width: 70, render: (_, t) => t.evidence.length },
    { title: 'Обновлено', dataIndex: 'updated', width: 110, render: (v?: string) => (v ? <Tooltip title={formatTime(v)}>{timeAgo(v)}</Tooltip> : '—') },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid="art-hub-plan">
      <Card size="small" title="План и задачи">
        <Descriptions size="small" column={{ xs: 1, md: 2, xl: 4 }}>
          <Descriptions.Item label="Файл">
            <Space size={2}>
              <Text code style={{ fontSize: 11 }}>{plan.file.path}</Text>
              <FileActions file={plan.file} />
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="Сформирован">{plan.generated ? formatTime(plan.generated) : '—'}</Descriptions.Item>
          <Descriptions.Item label="HEAD">{plan.head ? <Text code>{plan.head.slice(0, 10)}</Text> : '—'}</Descriptions.Item>
          <Descriptions.Item label="Схема">{plan.schema ?? '—'}</Descriptions.Item>
        </Descriptions>
        <Space wrap size={[4, 4]}>
          {plan.statusCounts.map((s) => (
            <TaskStatusTag key={s.status} status={s.status} count={s.count} />
          ))}
          <Text type="secondary">всего задач: {plan.tasks.length}</Text>
        </Space>
        {plan.error ? <Alert style={{ marginTop: 8 }} type="warning" showIcon message={`Файл не разобран: ${plan.error}`} /> : null}
      </Card>

      {plan.waves.length ? (
        <Card size="small" title={`Волны (${plan.waves.length})`}>
          <Table
            size="small"
            rowKey="id"
            pagination={false}
            dataSource={plan.waves}
            columns={[
              { title: 'Волна', dataIndex: 'id', width: 100, render: (v: string) => <Tag color="purple">{v}</Tag> },
              { title: 'Название', dataIndex: 'title', render: (v?: string) => v ?? '—' },
              { title: 'Статус', dataIndex: 'status', width: 140, render: (v?: string) => <TaskStatusTag status={v} /> },
              {
                title: 'Задачи',
                key: 't',
                render: (_, w) => (
                  <Space size={[2, 2]} wrap>
                    {w.tasks.map((id) => {
                      const t = plan.tasks.find((x) => x.id === id);
                      return (
                        <Tooltip key={id} title={t ? `${t.title} — ${TASK_STATUS[t.status]?.label ?? t.status}` : 'задачи нет в списке tasks'}>
                          <Tag color={t ? TASK_STATUS[t.status]?.color : 'orange'}>{id}</Tag>
                        </Tooltip>
                      );
                    })}
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      ) : null}

      <Card size="small" title={`Задачи (${plan.tasks.length})`}>
        <Table<PlanTaskView>
          size="small"
          rowKey="id"
          dataSource={plan.tasks}
          columns={columns}
          pagination={plan.tasks.length > 40 ? { pageSize: 40, size: 'small' } : false}
          scroll={{ x: 1400 }}
          expandable={{
            rowExpandable: (t) => t.evidence.length > 0,
            expandedRowRender: (t) => <FileTable files={t.evidence} pageSize={20} emptyText="доказательств нет" />,
          }}
        />
      </Card>

      {plan.sources.length ? (
        <Card size="small" title="Источники плана">
          <Table
            size="small"
            rowKey="id"
            pagination={false}
            dataSource={plan.sources}
            columns={[
              { title: 'id', dataIndex: 'id', width: 120, render: (v: string) => <Tag>{v}</Tag> },
              { title: 'Название', dataIndex: 'title', render: (v?: string) => v ?? '—' },
              {
                title: 'Путь',
                key: 'p',
                render: (_, s) => (
                  <Space size={2} wrap>
                    <Text style={{ fontSize: 12, wordBreak: 'break-all' }}>{s.path}</Text>
                    {s.file && s.file.exists === null ? <Tag>вне репо</Tag> : null}
                    {s.file && s.file.exists === false ? <Tag color="error">нет</Tag> : null}
                    {s.file ? <FileActions file={s.file} /> : null}
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      ) : null}
    </Space>
  );
};
