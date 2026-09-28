import React from 'react';
import { Alert, Card, Collapse, Descriptions, Empty, List, Space, Steps, Table, Tag, Tooltip, Typography } from 'antd';
import type { AssetPage, LayerView } from '../../../../art-hub/types';
import { FileActions, FilePath, FileTable, LongText, StageTag, StatusTag, useArtHubUi, TWO_COLUMNS } from '../components/common';
import { formatTime, timeAgo } from '../format';

const { Text, Paragraph } = Typography;

const OWNER_LABEL: Record<string, string> = {
  existingFiles: 'существующие файлы',
  nextCandidates: 'следующие кандидаты',
  acceptance: 'приёмка',
};

export const LayersTable: React.FC<{ layers: LayerView[]; mainId: string }> = ({ layers, mainId }) => (
  <Table<LayerView>
    size="small"
    rowKey={(l) => `${l.entryId}:${l.layer}`}
    dataSource={layers}
    pagination={false}
    locale={{ emptyText: 'слоёв в реестре нет' }}
    scroll={{ x: 900 }}
    columns={[
      {
        title: 'Слой',
        key: 'layer',
        width: '30%',
        render: (_, l) => (
          <div>
            <Text strong>{l.layer}</Text>
            {l.entryId !== mainId ? (
              <div>
                <Tag style={{ marginTop: 4 }}>{l.entryId}</Tag>
              </div>
            ) : null}
          </div>
        ),
      },
      { title: 'Стадия', key: 'stage', width: 190, render: (_, l) => <StageTag stage={l.stage} /> },
      {
        title: 'Статус',
        key: 'status',
        width: 200,
        render: (_, l) => (
          <Space direction="vertical" size={2}>
            <StatusTag status={l.status} />
            {l.statusLabel ? <Text type="secondary" style={{ fontSize: 12 }}>{l.statusLabel}</Text> : null}
          </Space>
        ),
      },
      {
        title: 'Решение / заметка',
        key: 'note',
        render: (_, l) => (
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            {l.decision ? (
              <Alert type="warning" showIcon style={{ padding: '2px 8px' }} message={<span style={{ fontSize: 12 }}>Решение: {l.decision}</span>} />
            ) : null}
            <LongText text={l.note} rows={2} />
          </Space>
        ),
      },
      { title: 'Владелец', key: 'owner', width: 90, render: (_, l) => l.owner ?? '—' },
      { title: 'Файлы', key: 'files', width: 70, render: (_, l) => l.files.length },
    ]}
    expandable={{
      rowExpandable: (l) => l.files.length > 0 || Boolean(l.extra),
      expandedRowRender: (l) => (
        <Space direction="vertical" style={{ width: '100%' }}>
          {l.extra ? (
            <Descriptions size="small" column={1} bordered>
              {Object.entries(l.extra).map(([k, v]) => (
                <Descriptions.Item key={k} label={k}>
                  <LongText text={v} rows={3} />
                </Descriptions.Item>
              ))}
            </Descriptions>
          ) : null}
          <FileTable files={l.files} pageSize={20} />
        </Space>
      ),
    }}
  />
);

export const SummarySection: React.FC<{ page: AssetPage }> = ({ page }) => {
  const { vocab } = useArtHubUi();
  const stageIdx = page.stage ? vocab.stage.indexOf(page.stage) : -1;
  const accepted = vocab.status[vocab.status.length - 1]?.name;
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {page.statusWarnings.map((w) => (
        <Alert key={w} type="error" showIcon message={w} />
      ))}
      {page.discoveredNotes.length ? (
        <Alert
          type="info"
          showIcon
          message="Найдено на диске (живые данные workflow)"
          description={
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {page.discoveredNotes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          }
        />
      ) : null}

      <Card size="small" title="Сводка реестра">
        <Descriptions size="small" column={TWO_COLUMNS} bordered>
          <Descriptions.Item label="Статус">
            <Space wrap>
              <StatusTag status={page.status} />
              {page.status !== accepted ? <Text type="secondary" style={{ fontSize: 12 }}>художественно не принято</Text> : null}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="Стадия">
            <StageTag stage={page.stage} />
          </Descriptions.Item>
          <Descriptions.Item label="Категория">{page.category}</Descriptions.Item>
          <Descriptions.Item label="Экземпляров">{page.instances}</Descriptions.Item>
          <Descriptions.Item label="Бэклог">{page.backlog.length ? page.backlog.map((b) => <Tag key={b}>{b}</Tag>) : '—'}</Descriptions.Item>
          <Descriptions.Item label="Файлы менялись">
            {page.lastModified ? <Tooltip title={formatTime(page.lastModified)}>{timeAgo(page.lastModified)}</Tooltip> : '—'}
          </Descriptions.Item>
          {page.ownership ? (
            <Descriptions.Item label="Владение" span={2}>
              <Space wrap>
                {Object.entries(page.ownership).map(([k, v]) => (
                  <Tag key={k}>
                    {OWNER_LABEL[k] ?? k}: {v}
                  </Tag>
                ))}
              </Space>
            </Descriptions.Item>
          ) : null}
        </Descriptions>
        {page.inRegistry ? (
          <Steps
            size="small"
            style={{ marginTop: 16, overflowX: 'auto' }}
            current={stageIdx}
            items={vocab.stage.map((s, i) => ({ title: <span style={{ fontSize: 11 }}>{s}</span>, status: i < stageIdx ? 'finish' : i === stageIdx ? 'process' : 'wait' }))}
          />
        ) : (
          <Alert style={{ marginTop: 12 }} type="warning" showIcon message="Записи в asset-registry.json нет — стадия и статус не определены реестром." />
        )}
      </Card>

      <Card size="small" title="Следующий шаг и блокер">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text type="secondary">Следующий шаг</Text>
            <Paragraph style={{ marginBottom: 0 }}>{page.nextStep ?? '—'}</Paragraph>
          </div>
          <Alert type="warning" showIcon message="Блокер" description={page.blocker ?? '—'} />
          <div>
            <Text type="secondary">Критерий готовности</Text>
            <Paragraph style={{ marginBottom: 0 }}>{page.doneCriteria ?? '—'}</Paragraph>
          </div>
        </Space>
      </Card>

      {page.members.length ? (
        <Card size="small" title="Составные части (записи-потомки реестра)">
          <Table
            size="small"
            rowKey="id"
            pagination={false}
            dataSource={page.members}
            scroll={{ x: 900 }}
            columns={[
              { title: 'Запись', key: 'id', render: (_, m) => <div><Text strong>{m.name}</Text><div><Text type="secondary" style={{ fontSize: 11 }}>{m.id}</Text></div></div> },
              { title: 'Статус', key: 'st', width: 200, render: (_, m) => <StatusTag status={m.status} /> },
              { title: 'Стадия', key: 'stage', width: 190, render: (_, m) => <StageTag stage={m.stage} /> },
              { title: 'Следующий шаг', key: 'next', render: (_, m) => <LongText text={m.nextStep} rows={2} /> },
              { title: 'Блокер', key: 'bl', render: (_, m) => <LongText text={m.blocker} rows={2} /> },
            ]}
          />
        </Card>
      ) : null}

      <Card size="small" title={`Слои (${page.layers.length})`}>
        <LayersTable layers={page.layers} mainId={page.id} />
      </Card>

      <Card
        size="small"
        title={`Акты и доказательства (${page.acts.length})`}
        extra={
          page.acceptanceEvidence.length ? (
            <Tag color="green">актов приёмки: {page.acceptanceEvidence.length}</Tag>
          ) : (
            <Tag>актов приёмки (acceptanceEvidence) нет</Tag>
          )
        }
      >
        {page.acts.length ? (
          <List
            size="small"
            dataSource={page.acts}
            renderItem={(a) => (
              <List.Item actions={[<FileActions key="a" file={a.file} />]}>
                <List.Item.Meta
                  title={
                    <Space wrap>
                      <span>{a.title ?? a.file.path.split('/').pop()}</span>
                      {a.acceptance ? <Tag color="green">acceptanceEvidence</Tag> : null}
                      {a.file.role ? <Tag>{a.file.role}</Tag> : null}
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <FilePath file={a.file} showDir />
                      {a.decision ? <Text italic>«{a.decision}»</Text> : <Text type="secondary">строки «Решение…» в акте нет</Text>}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="актов в реестре нет" />
        )}
      </Card>

      {page.reports.length ? (
        <Card size="small" title="Отчёты пайплайна">
          <FileTable files={page.reports} />
        </Card>
      ) : null}

      {page.manifest06 ? (
        <Collapse
          size="small"
          items={[
            {
              key: 'm06',
              label: '06-asset-manifest: статус и расхождения',
              children: (
                <Descriptions size="small" column={1} bordered>
                  {Object.entries(page.manifest06).map(([k, v]) => (
                    <Descriptions.Item key={k} label={k}>
                      <LongText text={v} rows={4} />
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              ),
            },
          ]}
        />
      ) : null}
    </Space>
  );
};
