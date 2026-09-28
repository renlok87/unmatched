import React from 'react';
import { Alert, Card, Descriptions, Empty, Space, Table, Tag, Tooltip, Typography } from 'antd';
import type { ClipSection, ClipSlotView } from '../../../../art-hub/types';
import { ClipStatusTag, FileActions, FileTable, LongText, ValidationTag, TWO_COLUMNS } from '../components/common';

const { Text } = Typography;

const checkColor = (s: string) => (s === 'pass' ? 'green' : s === 'warn' ? 'orange' : s === 'fail' ? 'red' : 'default');

const SlotDetails: React.FC<{ slot: ClipSlotView }> = ({ slot }) => (
  <Space direction="vertical" style={{ width: '100%' }}>
    <Descriptions size="small" column={TWO_COLUMNS} bordered>
      <Descriptions.Item label="Источник">
        {slot.sourceType}
        {slot.sourceTool ? ` · ${slot.sourceTool}` : ''}
      </Descriptions.Item>
      <Descriptions.Item label="Ссылка">
        <Text style={{ fontSize: 12, wordBreak: 'break-all' }}>{slot.sourceReference ?? '—'}</Text>
      </Descriptions.Item>
      <Descriptions.Item label="Лицензия">
        {slot.license ? Object.entries(slot.license).map(([k, v]) => <Tag key={k}>{k}: {v}</Tag>) : '—'}
      </Descriptions.Item>
      <Descriptions.Item label="Скелет">{slot.skeleton ?? '—'}</Descriptions.Item>
      <Descriptions.Item label="UE">
        <Space wrap>
          {slot.ueStatus ? <ClipStatusTag status={slot.ueStatus} /> : null}
          <Text style={{ fontSize: 12 }}>{slot.ueTargetPath ?? '—'}</Text>
          {slot.ueEvidence ? <FileActions file={slot.ueEvidence} /> : null}
        </Space>
      </Descriptions.Item>
      <Descriptions.Item label="Отчёт валидатора">
        {slot.validation.report ? (
          <Space>
            <Text style={{ fontSize: 12 }}>{slot.validation.report.path.split('/').pop()}</Text>
            <FileActions file={slot.validation.report} />
          </Space>
        ) : (
          '—'
        )}
      </Descriptions.Item>
      <Descriptions.Item label="Заметки" span={2}>
        <LongText text={slot.notes} rows={3} />
      </Descriptions.Item>
    </Descriptions>
    {slot.files.length ? <FileTable files={slot.files} showRole /> : null}
    {slot.validation.checks.length ? (
      <Table
        size="small"
        rowKey="check"
        pagination={false}
        dataSource={slot.validation.checks}
        columns={[
          { title: 'Проверка validate_clip', dataIndex: 'check' },
          { title: 'Итог', dataIndex: 'status', width: 90, render: (s: string) => <Tag color={checkColor(s)}>{s}</Tag> },
          { title: 'Значение', dataIndex: 'value', render: (v?: string) => <Text style={{ fontSize: 12 }}>{v ?? ''}</Text> },
          { title: 'Заметка', dataIndex: 'note', render: (v?: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v ?? ''}</Text> },
        ]}
      />
    ) : null}
  </Space>
);

export const ClipsSection: React.FC<{ clips: ClipSection }> = ({ clips }) => {
  const production = clips.slots.filter((s) => s.role === 'production');
  const filled = production.filter((s) => s.status !== 'proposed' || s.sourceType !== 'none').length;
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={`Производственные слоты: заполнено ${filled} из ${production.length} (обязательных для MVP: ${production.filter((s) => s.requiredMvp).length}); тестовых записей: ${clips.slots.length - production.length}`}
        description={
          clips.notes.length ? (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {clips.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : undefined
        }
        action={clips.manifest ? <FileActions file={clips.manifest} /> : undefined}
      />
      <Card size="small" title={`Слоты clip-manifest${clips.revision ? ` (ревизия ${clips.revision})` : ''}`}>
        <Table<ClipSlotView>
          size="small"
          rowKey="id"
          dataSource={clips.slots}
          pagination={false}
          scroll={{ x: 1100 }}
          locale={{ emptyText: 'слотов для персонажа нет' }}
          expandable={{ expandedRowRender: (s) => <SlotDetails slot={s} /> }}
          columns={[
            {
              title: 'Слот',
              key: 'id',
              render: (_, s) => (
                <div>
                  <Text strong>{s.id}</Text>
                  <div>
                    <Space size={4} wrap>
                      <Tag color={s.role === 'production' ? 'blue' : 'default'}>{s.role === 'production' ? 'производство' : 'тест'}</Tag>
                      {s.role === 'production' ? (
                        s.requiredMvp ? <Tag color="volcano">MVP</Tag> : <Tooltip title={s.notes}><Tag>условный</Tag></Tooltip>
                      ) : null}
                    </Space>
                  </div>
                </div>
              ),
            },
            { title: 'Статус', key: 'st', width: 170, render: (_, s) => <ClipStatusTag status={s.status} /> },
            { title: 'Источник', key: 'src', width: 150, render: (_, s) => <Text style={{ fontSize: 12 }}>{s.sourceType}</Text> },
            { title: 'CUE', key: 'cue', width: 140, render: (_, s) => s.cue.map((c) => <Tag key={c}>{c}</Tag>) },
            {
              title: 'Длительность, с',
              key: 'dur',
              width: 170,
              render: (_, s) => (
                <Tooltip title={`цель: ${s.durationTarget ?? '—'} (${s.durationTargetStatus ?? '—'}); измерено: ${s.durationMeasured ?? '—'}`}>
                  <Text style={{ fontSize: 12 }}>
                    цель {String(s.durationTarget ?? '—')}
                    {s.durationMeasured !== null && s.durationMeasured !== undefined ? ` · изм. ${s.durationMeasured}` : ''}
                  </Text>
                </Tooltip>
              ),
            },
            {
              title: 'FPS',
              key: 'fps',
              width: 80,
              render: (_, s) => `${s.fpsTarget ?? '—'}${s.fpsMeasured ? ` / ${s.fpsMeasured}` : ''}`,
            },
            { title: 'Loop / root', key: 'loop', width: 120, render: (_, s) => <Text style={{ fontSize: 12 }}>{s.loop ? 'loop' : 'разовый'} · {s.rootMotion ?? '—'}</Text> },
            {
              title: 'Валидация',
              key: 'val',
              width: 220,
              render: (_, s) => (
                <Space direction="vertical" size={2}>
                  <ValidationTag result={s.validation.result} />
                  {s.validation.warnings.length ? <Text type="warning" style={{ fontSize: 11 }}>warn: {s.validation.warnings.join(', ')}</Text> : null}
                  {s.validation.fails.length ? <Text type="danger" style={{ fontSize: 11 }}>fail: {s.validation.fails.join(', ')}</Text> : null}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card size="small" title={`Файлы анимаций (${clips.animationFiles.length})`} extra={<Text type="secondary" style={{ fontSize: 12 }}>кнопка «3D» проигрывает клип из FBX/GLB</Text>}>
        <FileTable files={clips.animationFiles} emptyText="файлов анимаций нет" />
      </Card>

      <Card size="small" title={`Сводка validate_clip по персонажу (${clips.validationCases.length})`}>
        {clips.validationCases.length ? (
          <Table
            size="small"
            rowKey="case"
            pagination={false}
            dataSource={clips.validationCases}
            columns={[
              { title: 'Случай', dataIndex: 'case' },
              { title: 'Итог', dataIndex: 'result', width: 80, render: (r: string) => <Tag color={r === 'pass' ? 'green' : 'red'}>{r}</Tag> },
              {
                title: 'Ожидание',
                dataIndex: 'expectationMet',
                width: 120,
                render: (v?: boolean) => (v === undefined ? '—' : v ? <Tag color="green">совпало</Tag> : <Tag color="red">не совпало</Tag>),
              },
              { title: 'FPS', dataIndex: 'fps', width: 70 },
              { title: 'Длит., с', dataIndex: 'durationS', width: 80 },
              { title: 'Предупреждения / отказы', key: 'w', render: (_, c) => <Text style={{ fontSize: 12 }}>{[...c.warnings, ...c.fails].join(', ') || '—'}</Text> },
              { title: 'Файл', dataIndex: 'clip', render: (v: string) => <Text type="secondary" style={{ fontSize: 11, wordBreak: 'break-all' }}>{v}</Text> },
            ]}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="валидатор по этому персонажу не запускался" />
        )}
      </Card>
    </Space>
  );
};
