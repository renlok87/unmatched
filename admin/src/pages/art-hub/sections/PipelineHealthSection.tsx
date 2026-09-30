import React from 'react';
import { Alert, Button, Card, Col, Collapse, Empty, Progress, Row, Space, Statistic, Table, Tag, Tooltip, Typography } from 'antd';
import type { ArtHubData, RecentFile } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { FileActions, FileTable, LongText, StageTag, StatusTag, useArtHubUi } from '../components/common';
import { formatBytes, formatTime, timeAgo } from '../format';
import { LedgerTable } from './SoundsCreditsSections';
import { UeMatrix } from './UeLayersSection';

const { Text } = Typography;

export const PipelineHealthSection: React.FC<{ data: ArtHubData }> = ({ data }) => {
  const ui = useArtHubUi();
  const h = data.pipelineHealth;
  const c = data.credits;
  const pageName = (id?: string) => [...data.characters, ...data.props].find((p) => p.id === id)?.shortName ?? id;
  const pct = (spent?: number, limit?: number) => (spent !== undefined && limit ? Math.min(100, Math.round((spent / limit) * 100)) : 0);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid="art-hub-health">
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} xl={6}>
          <Card size="small">
            <Statistic title="Записей в реестре" value={h.registry.total} />
            <div data-testid="art-hub-registry-dates" style={{ fontSize: 12 }}>
              <Text type="secondary">
                срез в файле: {h.registry.snapshotDate ?? '—'}
                {h.registry.fileMtime ? ` · файл изменён ${formatTime(h.registry.fileMtime)}` : ''}
                {h.registry.latestLayerDate ? ` · свежий слой ${h.registry.latestLayerDate}` : ''}
              </Text>
              {h.registry.snapshotDate && h.registry.latestLayerDate && h.registry.latestLayerDate > h.registry.snapshotDate ? (
                <Tooltip title="Поле snapshotDate реестра старше самых свежих слоёв: слои дописаны, дата среза не обновлена">
                  <Tag color="orange" style={{ marginLeft: 4 }}>
                    срез старше слоёв
                  </Tag>
                </Tooltip>
              ) : null}
            </div>
            <Space wrap size={[4, 4]} style={{ marginTop: 8 }}>
              {h.registry.byStatus.map((s) => (
                <span key={s.status}>
                  <StatusTag status={s.status === '—' ? null : s.status} label={`${s.status} · ${s.count}`} />
                </span>
              ))}
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card size="small">
            <Statistic title={`Tripo окно, ${c.tripo.unit}`} value={c.tripo.spent ?? 0} suffix={c.tripo.limit ? `/ ${c.tripo.limit}` : undefined} />
            <Progress percent={pct(c.tripo.spent, c.tripo.limit)} size="small" status="normal" />
            <Text type="secondary" style={{ fontSize: 12 }}>
              баланс {c.tripo.balanceStart ?? '—'} → {c.tripo.balanceEnd ?? '—'}; до окна: {c.tripo.preWindowSpent}
            </Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card size="small">
            <Statistic title={`SYNTX окно, ${c.syntx.unit}`} value={c.syntx.spent ?? 0} precision={(c.syntx.spent ?? 0) % 1 ? 1 : 0} suffix={c.syntx.limit ? `/ ${c.syntx.limit}` : undefined} />
            <Progress percent={pct(c.syntx.spent, c.syntx.limit)} size="small" status="normal" />
            <Text type="secondary" style={{ fontSize: 12 }}>
              баланс {c.syntx.balanceStart ?? '—'} → {c.syntx.balanceEnd ?? '—'}
            </Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card size="small">
            <Statistic title="validate_clip (сводка)" value={h.validation.pass} suffix={`pass / ${h.validation.fail} fail`} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              ожидание совпало: {h.validation.expectationMet} из {h.validation.total} (fail — негативные тесты)
            </Text>
          </Card>
        </Col>
      </Row>
      {c.tripo.limitNote || c.syntx.limitNote ? (
        <Alert type="info" showIcon message="Лимиты" description={<LongText text={[c.tripo.limitNote, c.syntx.limitNote].filter(Boolean).join('\n')} rows={2} />} />
      ) : null}

      <UeMatrix characters={data.characters} />

      <Card size="small" title="Покрытие слотов клипов (clip-manifest, производство)">
        <Table
          size="small"
          rowKey="assetId"
          pagination={false}
          dataSource={h.clipCoverage}
          columns={[
            { title: 'Персонаж', key: 'c', render: (_, r) => <Button type="link" size="small" onClick={() => ui.openPage(r.assetId, 'clips')}>{r.character}</Button> },
            { title: 'Слотов', dataIndex: 'total', width: 80 },
            { title: 'Обязательных MVP', dataIndex: 'required', width: 140 },
            { title: 'Заполнено', key: 'f', render: (_, r) => <Progress percent={r.total ? Math.round((r.filled / r.total) * 100) : 0} format={() => `${r.filled}/${r.total}`} size="small" /> },
          ]}
        />
      </Card>

      <Card size="small" title={`Прогоны art/pipeline-candidates (${h.runs.length}), свежие первыми`}>
        <Table
          size="small"
          rowKey="dir"
          pagination={false}
          dataSource={h.runs}
          scroll={{ x: 900 }}
          columns={[
            { title: 'Прогон', key: 'id', render: (_, r) => <div><Text strong>{r.id}</Text><div><Text type="secondary" style={{ fontSize: 11 }}>{r.assetDir}</Text></div></div> },
            { title: 'Ассет', key: 'p', render: (_, r) => (r.page ? <Button size="small" type="link" onClick={() => ui.openPage(r.page!, 'models')}>{pageName(r.page)}</Button> : <Tag color="orange">не отнесён</Tag>) },
            { title: 'Тип', dataIndex: 'kind', width: 110, render: (v: string) => <Tag>{v}</Tag> },
            { title: 'Реестр', dataIndex: 'inRegistry', width: 110, render: (v: boolean) => (v ? <Tag color="blue">в реестре</Tag> : <Tag color="orange">нет</Tag>) },
            { title: 'Этапы', key: 's', render: (_, r) => <Text style={{ fontSize: 12 }}>{r.stages.map((s) => `${s.name}:${s.status}`).join(', ') || '—'}</Text> },
            { title: 'Изменён', key: 'm', width: 120, render: (_, r) => (r.lastModified ? <Tooltip title={formatTime(r.lastModified)}>{timeAgo(r.lastModified)}</Tooltip> : '—') },
          ]}
        />
      </Card>

      <Card size="small" title="Свежие изменения файлов (все отслеживаемые корни)">
        <Table<RecentFile>
          size="small"
          rowKey="path"
          dataSource={h.recentFiles}
          pagination={{ pageSize: 12, size: 'small' }}
          scroll={{ x: 900 }}
          columns={[
            { title: 'Когда', dataIndex: 'mtime', width: 120, render: (v: string) => <Tooltip title={formatTime(v)}>{timeAgo(v)}</Tooltip> },
            {
              title: 'Файл',
              dataIndex: 'path',
              render: (v: string, f) =>
                f.servable ? (
                  <a href={fileUrl({ path: v, mtime: f.mtime })} target="_blank" rel="noreferrer" style={{ wordBreak: 'break-all', fontSize: 12 }}>
                    {v}
                  </a>
                ) : (
                  <Text style={{ fontSize: 12, wordBreak: 'break-all' }}>{v}</Text>
                ),
            },
            { title: 'Ассет', dataIndex: 'page', width: 140, render: (v?: string) => (v ? <Button size="small" type="link" onClick={() => ui.openPage(v)}>{pageName(v)}</Button> : '—') },
            { title: 'Тип', dataIndex: 'kind', width: 80 },
            { title: 'Размер', dataIndex: 'bytes', width: 90, render: (v: number) => formatBytes(v) },
          ]}
        />
      </Card>

      <Card size="small" title="Реестр ассетов">
        <Table
          size="small"
          rowKey="id"
          dataSource={h.registry.entries}
          pagination={false}
          scroll={{ x: 1000 }}
          columns={[
            { title: 'Ассет', key: 'n', render: (_, e) => <div><Button type="link" size="small" style={{ padding: 0 }} onClick={() => ui.openPage(e.page)}>{e.name}</Button><div><Text type="secondary" style={{ fontSize: 11 }}>{e.id}</Text></div></div> },
            { title: 'Статус', dataIndex: 'status', width: 200, render: (v: string | null) => <StatusTag status={v} /> },
            { title: 'Стадия', dataIndex: 'stage', width: 190, render: (v: string | null) => <StageTag stage={v} /> },
            { title: 'Следующий шаг', dataIndex: 'nextStep', render: (v?: string) => <LongText text={v} rows={2} /> },
          ]}
        />
      </Card>

      <Row gutter={16}>
        <Col xs={24} xl={10}>
          <Card size="small" title="Tripo: траты окна по задачам">
            <Table
              size="small"
              rowKey="task"
              pagination={false}
              dataSource={c.tripo.byTask}
              columns={[
                { title: 'Задача', dataIndex: 'task' },
                { title: c.tripo.unit, dataIndex: 'credits', width: 110 },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card size="small" title="Последние списания (Tripo и SYNTX)" extra={c.ledger ? <FileActions file={c.ledger} /> : null}>
            <LedgerTable entries={c.recent} pageSize={8} />
          </Card>
        </Col>
      </Row>
      {c.unattributed.length ? (
        <Card size="small" title={`Списания, не отнесённые ни к одному ассету (${c.unattributed.length})`}>
          <LedgerTable entries={c.unattributed} />
        </Card>
      ) : null}

      <Collapse
        size="small"
        items={[
          { key: 'rep', label: `Отчёты пайплайна (${h.reports.length})`, children: <FileTable files={h.reports} /> },
          {
            key: 'miss',
            label: `Пути реестра с expect=exists, которых нет на диске (${h.missingReferenced.length})`,
            children: h.missingReferenced.length ? (
              <Table
                size="small"
                rowKey={(r) => `${r.entryId}:${r.path}`}
                pagination={false}
                dataSource={h.missingReferenced}
                columns={[
                  { title: 'Запись', dataIndex: 'entryId' },
                  { title: 'Путь', dataIndex: 'path' },
                  { title: 'Роль', dataIndex: 'role' },
                ]}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="все пути на месте" />
            ),
          },
          {
            key: 'src',
            label: `Источники данных (${h.sources.length})`,
            children: (
              <Table
                size="small"
                rowKey="path"
                pagination={false}
                dataSource={h.sources}
                columns={[
                  { title: 'Файл', dataIndex: 'path' },
                  { title: 'Есть', dataIndex: 'exists', width: 70, render: (v: boolean) => (v ? <Tag color="success">да</Tag> : <Tag color="error">нет</Tag>) },
                  { title: 'Изменён', dataIndex: 'mtime', width: 160, render: (v?: string) => formatTime(v) },
                  { title: 'Ошибка', dataIndex: 'error', render: (v?: string) => (v ? <Text type="danger">{v}</Text> : '—') },
                ]}
              />
            ),
          },
        ]}
      />
    </Space>
  );
};
