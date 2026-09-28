import React from 'react';
import { Alert, Card, Col, Empty, List, Row, Space, Statistic, Table, Tag, Typography } from 'antd';
import type { CreditsSection, LedgerEntry, SoundSection } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { FileActions, FilePath, StatusTag } from '../components/common';

const { Text } = Typography;

export const SoundsSection: React.FC<{ sounds: SoundSection }> = ({ sounds }) => (
  <Space direction="vertical" size={16} style={{ width: '100%' }}>
    {sounds.files.length === 0 ? (
      <Alert
        type="info"
        showIcon
        message={
          <Space>
            <span>Звуковые ассеты персонажа:</span>
            <StatusTag status={sounds.status} />
          </Space>
        }
        description={`Аудиофайлов персонажа не найдено. Искали: ${sounds.searchedRoots.join(', ')} (wav/mp3/ogg/flac/m4a/aac/opus и SoundWave-uasset в папках audio/sound/sfx). Раздел заполнится сам, когда файлы появятся.`}
      />
    ) : (
      <Card size="small" title={`Звуковые файлы (${sounds.files.length})`}>
        <List
          dataSource={sounds.files}
          renderItem={(f) => (
            <List.Item actions={[<FileActions key="a" file={f} />]}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <FilePath file={f} />
                {f.servable && f.kind === 'audio' ? <audio controls preload="none" src={fileUrl(f)} style={{ width: '100%' }} /> : null}
              </Space>
            </List.Item>
          )}
        />
      </Card>
    )}
    <Card
      size="small"
      title="Запланированные звуковые CUE (07-animation-vfx-audio.csv)"
      extra={sounds.cueSource ? <Text type="secondary" style={{ fontSize: 12 }}>{sounds.cueSource.path}</Text> : null}
    >
      <Table
        size="small"
        rowKey="cueId"
        pagination={false}
        dataSource={sounds.cues}
        locale={{ emptyText: 'CUE для персонажа не найдены' }}
        columns={[
          { title: 'CUE', dataIndex: 'cueId', width: 90, render: (v: string) => <Tag>{v}</Tag> },
          { title: 'Событие', dataIndex: 'event' },
          { title: 'Звук (план)', dataIndex: 'sound' },
          { title: 'мс', dataIndex: 'durationMs', width: 60 },
          { title: 'Связь', dataIndex: 'via', width: 150, render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text> },
        ]}
      />
    </Card>
  </Space>
);

export const LedgerTable: React.FC<{ entries: LedgerEntry[]; pageSize?: number; onOpenPage?: (id: string) => void }> = ({ entries, pageSize = 15 }) => (
  <Table<LedgerEntry>
    size="small"
    rowKey={(e) => `${e.service}:${e.time ?? ''}:${e.op ?? ''}:${e.delta}:${e.ref ?? ''}:${e.cue ?? ''}`}
    dataSource={entries}
    pagination={entries.length > pageSize ? { pageSize, size: 'small' } : false}
    scroll={{ x: 1000 }}
    locale={{ emptyText: 'списаний нет' }}
    columns={[
      { title: 'Время', dataIndex: 'time', width: 170, render: (v?: string) => <Text style={{ fontSize: 12 }}>{v ?? '—'}</Text> },
      {
        title: 'Сервис',
        dataIndex: 'service',
        width: 110,
        render: (v: string, e) => (
          <Space size={2} direction="vertical">
            <Tag color={v === 'tripo' ? 'purple' : 'cyan'}>{v === 'tripo' ? 'Tripo Studio' : 'SYNTX'}</Tag>
            {e.window === 'pre' ? <Text type="secondary" style={{ fontSize: 11 }}>до окна</Text> : null}
          </Space>
        ),
      },
      {
        title: 'Операция',
        key: 'op',
        render: (_, e) => (
          <div>
            <Text style={{ fontSize: 12 }}>{e.op ?? '—'}</Text>
            {e.model ? <div><Text type="secondary" style={{ fontSize: 11 }}>{e.model}</Text></div> : null}
            {e.note ? <div><Text type="secondary" style={{ fontSize: 11 }}>{e.note}</Text></div> : null}
          </div>
        ),
      },
      {
        title: 'Δ',
        dataIndex: 'delta',
        width: 70,
        render: (v: number) => <Text type={v < 0 ? 'danger' : v > 0 ? 'success' : undefined}>{v > 0 ? `+${v}` : v}</Text>,
      },
      {
        title: 'Баланс',
        key: 'bal',
        width: 130,
        render: (_, e) => (e.balanceBefore !== undefined || e.balanceAfter !== undefined ? `${e.balanceBefore ?? '—'} → ${e.balanceAfter ?? '—'}` : '—'),
      },
      { title: 'Кому', dataIndex: 'owner', width: 180, render: (v?: string) => <Text style={{ fontSize: 12 }}>{v ?? '—'}</Text> },
      { title: 'Ссылка', dataIndex: 'ref', render: (v?: string) => <Text type="secondary" style={{ fontSize: 11, wordBreak: 'break-all' }}>{v ?? '—'}</Text> },
    ]}
  />
);

export const CreditsSectionView: React.FC<{ credits: CreditsSection }> = ({ credits }) => (
  <Space direction="vertical" size={16} style={{ width: '100%' }}>
    <Row gutter={16}>
      <Col xs={24} md={8}>
        <Card size="small">
          <Statistic title={`Tripo: ${credits.tripoUnit}`} value={credits.tripoSpent} />
        </Card>
      </Col>
      <Col xs={24} md={8}>
        <Card size="small">
          <Statistic title={`SYNTX: ${credits.syntxUnit}`} value={credits.syntxSpent} precision={credits.syntxSpent % 1 ? 1 : 0} />
        </Card>
      </Col>
      <Col xs={24} md={8}>
        <Card size="small">
          <Statistic title="Записей в журнале" value={credits.entries.length} />
          <Text type="secondary" style={{ fontSize: 11 }}>единицы сервисов не суммируются</Text>
        </Card>
      </Col>
    </Row>
    <Card size="small" title="Списания и пополнения, отнесённые к ассету">
      {credits.entries.length ? <LedgerTable entries={credits.entries} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="в журнале нет записей по этому ассету" />}
    </Card>
  </Space>
);
