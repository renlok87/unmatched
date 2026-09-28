import React from 'react';
import { Alert, Card, Empty, Space, Steps, Table, Tag, Typography } from 'antd';
import type { V2MSection, V2MState } from '../../../../art-hub/types';
import { ClipStatusTag, FileActions } from '../components/common';

const { Text } = Typography;

const STEP_STATUS: Record<V2MState, 'finish' | 'process' | 'wait' | 'error'> = {
  done: 'finish',
  partial: 'process',
  'not-started': 'wait',
  'n/a': 'wait',
};

const STATE_LABEL: Record<V2MState, string> = {
  done: 'готово',
  partial: 'частично',
  'not-started': 'не начато',
  'n/a': 'не применимо',
};

export const VideoToMotionSection: React.FC<{ v2m: V2MSection }> = ({ v2m }) => (
  <Space direction="vertical" size={16} style={{ width: '100%' }}>
    <Alert
      type="info"
      showIcon
      message="Конвейер «видео → скелет» по слотам: референс → извлечение движения → ретаргет → validate_clip → импорт в UE"
      description="Этапы вычислены из clip-manifest.json, файлов art/animation-refs и VIDEO-TO-MOTION.md. «Готово» здесь — только техническое состояние; художественная приёмка фиксируется актом."
      action={v2m.doc ? <FileActions file={v2m.doc} /> : undefined}
    />
    {v2m.slots.length ? (
      v2m.slots.map((s) => (
        <Card
          key={s.cue}
          size="small"
          title={
            <Space wrap>
              <Text strong>{s.cue}</Text>
              {s.requiredMvp ? <Tag color="volcano">MVP</Tag> : <Tag>условный</Tag>}
              {s.slotStatus ? <ClipStatusTag status={s.slotStatus} /> : null}
              <Text type="secondary" style={{ fontSize: 12 }}>
                текущий этап: {s.currentStage}
              </Text>
            </Space>
          }
        >
          <Steps
            size="small"
            items={s.stages.map((st) => ({
              title: st.label,
              status: STEP_STATUS[st.state],
              description: (
                <div style={{ fontSize: 11 }}>
                  <Tag style={{ marginBottom: 2 }} color={st.state === 'done' ? 'green' : st.state === 'partial' ? 'orange' : undefined}>
                    {STATE_LABEL[st.state]}
                  </Tag>
                  <div>{st.detail}</div>
                </div>
              ),
            }))}
          />
          <Alert style={{ marginTop: 12 }} type="warning" showIcon message="Блокер" description={s.blocker} />
        </Card>
      ))
    ) : (
      <Empty description="слотов клипов нет" />
    )}

    <Card size="small" title="Внешние зависимости (VIDEO-TO-MOTION.md §6)">
      <Table
        size="small"
        rowKey="dependency"
        pagination={false}
        dataSource={v2m.dependencies}
        locale={{ emptyText: 'таблица §6 не найдена' }}
        columns={[
          { title: 'Зависимость', dataIndex: 'dependency' },
          { title: 'Нужна для', dataIndex: 'neededFor' },
          { title: 'Статус', dataIndex: 'status', render: (v: string) => <Tag color={/не |нет|отложено/i.test(v) ? 'orange' : 'default'}>{v}</Tag> },
          { title: 'Кто решает', dataIndex: 'who' },
        ]}
      />
    </Card>
    {v2m.recommendation.length ? (
      <Card size="small" title="Рекомендация документа (§5)">
        <ol style={{ margin: 0, paddingLeft: 18 }}>
          {v2m.recommendation.map((r) => (
            <li key={r} style={{ marginBottom: 6 }}>
              {r}
            </li>
          ))}
        </ol>
      </Card>
    ) : null}
  </Space>
);
