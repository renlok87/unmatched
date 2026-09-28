import React from 'react';
import { Alert, Card, Col, Collapse, Descriptions, Empty, Image, Row, Space, Tabs, Tag, Tooltip, Typography } from 'antd';
import type { VideoCueView, VideoRefSection, VideoTakeView } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { FileActions, Gallery, LongText, ONE_TWO_COLUMNS } from '../components/common';
import { formatTime, timeAgo } from '../format';

const { Text } = Typography;

const ANALYSIS_LABELS: Record<string, string> = {
  frames: 'кадров',
  width: 'ширина',
  height: 'высота',
  border_mad_max: 'фон MAD max',
  base_center_x_range_px: 'размах центра подставки, px',
  base_bottom_y_range_px: 'размах низа подставки, px',
  motion_mad_max: 'энергия движения max',
  fg_touches_edge_frames: 'кадров с касанием края',
};

const BUDGET_LABELS: Record<string, string> = {
  limitSyntxTokens: 'лимит, токенов SYNTX',
  spentSyntxTokens: 'потрачено, токенов SYNTX',
  spentStatus: 'статус суммы',
  balanceEnd: 'баланс в конце',
  clipLimit: 'лимит роликов',
  clipsGenerated: 'роликов сгенерировано',
  generations: 'генераций',
  status: 'статус',
  note: 'примечание',
  p1Medusa: 'P1 Medusa',
  heroSeries: 'серия героев',
  total: 'всего, токенов SYNTX',
};

const BudgetTags: React.FC<{ budget: Record<string, string | number> }> = ({ budget }) => (
  <Space wrap size={[6, 6]}>
    {Object.entries(budget).map(([k, v]) => (
      <Tooltip key={k} title={k}>
        <Tag>
          {BUDGET_LABELS[k] ?? k}: {String(v)}
        </Tag>
      </Tooltip>
    ))}
  </Space>
);

const TakeSuitability: React.FC<{ take: VideoTakeView; hasManifest: boolean }> = ({ take, hasManifest }) => {
  if (take.suitability) {
    return (
      <Alert
        type={take.selected ? 'success' : 'info'}
        showIcon
        message={
          <Space wrap size={6}>
            <span>Пригодность дубля {take.take}: {take.suitability.verdict ?? '—'}</span>
            {take.selected ? <Tag color="green">выбран в манифесте</Tag> : null}
            {take.selected === false ? <Tag>не выбран</Tag> : null}
          </Space>
        }
        description={
          <Text type="secondary" style={{ fontSize: 12 }}>
            {[take.suitability.status, take.suitability.basis, take.manifestRecord].filter(Boolean).join(' · ')}
          </Text>
        }
      />
    );
  }
  if (take.manifestRecord) {
    return <Alert type="warning" showIcon message={`В записи ${take.manifestRecord} нет оценки пригодности`} />;
  }
  return (
    <Alert
      type="warning"
      showIcon
      message={
        hasManifest
          ? `Дубль ${take.take} не описан в манифесте видео-референсов — пригодность не оценена`
          : 'Пригодность не оценена: манифеста видео-референсов нет'
      }
    />
  );
};

const TakeAssessment: React.FC<{ take: VideoTakeView }> = ({ take }) =>
  take.motionSummary || take.assessment || take.briefDeviation || take.retryProposal ? (
    <Collapse
      size="small"
      items={[
        {
          key: 'a',
          label: `Оценка дубля ${take.take} из манифеста (визуальная, pose-трекинг не запускался)`,
          children: (
            <Descriptions size="small" column={1} bordered>
              {take.motionSummary ? <Descriptions.Item label="Движение">{take.motionSummary}</Descriptions.Item> : null}
              {Object.entries(take.assessment ?? {}).map(([k, v]) => (
                <Descriptions.Item key={k} label={k}>
                  <LongText text={v} rows={3} />
                </Descriptions.Item>
              ))}
              {take.briefDeviation ? (
                <Descriptions.Item label="Отклонение от брифа">
                  <LongText text={take.briefDeviation} rows={3} />
                </Descriptions.Item>
              ) : null}
              {take.retryProposal ? (
                <Descriptions.Item label="Предложение ретейка">
                  <LongText text={take.retryProposal} rows={3} />
                </Descriptions.Item>
              ) : null}
            </Descriptions>
          ),
        },
      ]}
    />
  ) : null;

const TakeView: React.FC<{ take: VideoTakeView; hasManifest: boolean }> = ({ take, hasManifest }) => (
  <Row gutter={16}>
    <Col xs={24} lg={10}>
      {take.video?.servable ? (
        <video
          data-testid="art-hub-video"
          src={fileUrl(take.video)}
          controls
          preload="metadata"
          loop
          muted
          style={{ width: '100%', maxHeight: 420, background: '#000', borderRadius: 6 }}
        />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            take.video
              ? 'видео не отдаётся'
              : take.missingVideo
                ? `ролик из манифеста не найден на диске: ${take.missingVideo.split('/').pop()}`
                : 'ролика нет (только материалы)'
          }
        />
      )}
      {take.video ? (
        <Space style={{ marginTop: 4 }} wrap>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {take.video.path.split('/').pop()}
          </Text>
          <FileActions file={take.video} />
        </Space>
      ) : null}
    </Col>
    <Col xs={24} lg={14}>
      <Space direction="vertical" style={{ width: '100%' }} size={10}>
        <TakeSuitability take={take} hasManifest={hasManifest} />
        <Descriptions size="small" column={ONE_TWO_COLUMNS} bordered>
          <Descriptions.Item label="Модель">{take.model ?? <Text type="secondary">не указана</Text>}</Descriptions.Item>
          <Descriptions.Item label="Стоимость">
            {take.cost?.tokens !== undefined ? (
              <Tooltip title={`источник: ${take.cost.source}; баланс ${take.cost.balanceBefore ?? '—'} → ${take.cost.balanceAfter ?? '—'}`}>
                {take.cost.tokens} токенов SYNTX
              </Tooltip>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          {take.manifestStatus ? <Descriptions.Item label="Статус (манифест)">{take.manifestStatus}</Descriptions.Item> : null}
          {take.briefFit ? <Descriptions.Item label="Соответствие брифу">{take.briefFit}</Descriptions.Item> : null}
          {take.whyThisTake ? (
            <Descriptions.Item label="Зачем этот дубль" span={ONE_TWO_COLUMNS}>
              {take.whyThisTake}
            </Descriptions.Item>
          ) : null}
          <Descriptions.Item label="Обновлено">
            {take.lastModified ? <Tooltip title={formatTime(take.lastModified)}>{timeAgo(take.lastModified)}</Tooltip> : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Замеры">
            {take.analysisFile ? <FileActions file={take.analysisFile} /> : <Text type="secondary">analysis.json нет</Text>}
          </Descriptions.Item>
        </Descriptions>
        {take.analysis ? (
          <Space wrap size={[6, 6]}>
            {Object.entries(take.analysis).map(([k, v]) => (
              <Tag key={k}>
                {ANALYSIS_LABELS[k] ?? k}: {v}
              </Tag>
            ))}
          </Space>
        ) : null}
        <TakeAssessment take={take} />
        {take.prompt ? (
          <div>
            <Text type="secondary">Промпт</Text>
            <LongText text={take.prompt} rows={2} />
          </div>
        ) : null}
        {take.contactSheet?.servable ? (
          <div>
            <Text type="secondary">Контакт-лист 2 fps</Text>
            <Image src={fileUrl(take.contactSheet)} style={{ maxHeight: 220, objectFit: 'contain' }} />
          </div>
        ) : null}
        {take.keyframes.length ? (
          <div>
            <Text type="secondary">Ключевые кадры ({take.keyframes.length})</Text>
            <Gallery images={take.keyframes} size={96} />
          </div>
        ) : null}
      </Space>
    </Col>
  </Row>
);

const CueSuitability: React.FC<{ cue: VideoCueView; manifestPath?: string }> = ({ cue, manifestPath }) => {
  if (cue.suitability) {
    return (
      <Alert
        type="info"
        showIcon
        data-testid="art-hub-cue-suitability"
        message={
          <span>
            Пригодность для video-to-motion{cue.suitabilityFrom ? ` (${cue.suitabilityFrom})` : ''}: {cue.suitability.verdict ?? '—'}
          </span>
        }
        description={
          <Text type="secondary" style={{ fontSize: 12 }}>
            {[cue.suitability.status, cue.suitability.basis, cue.manifestRecords.length ? `записи: ${cue.manifestRecords.join(', ')}` : undefined]
              .filter(Boolean)
              .join(' · ')}
          </Text>
        }
      />
    );
  }
  if (cue.manifestRecords.length) {
    return (
      <Alert
        type="warning"
        showIcon
        data-testid="art-hub-cue-suitability"
        message={`Общая оценка пригодности не выведена: ${cue.suitabilityNote ?? 'в записи манифеста нет оценки'}`}
        description={<Text type="secondary" style={{ fontSize: 12 }}>записи: {cue.manifestRecords.join(', ')}</Text>}
      />
    );
  }
  return (
    <Alert
      type="warning"
      showIcon
      data-testid="art-hub-cue-suitability"
      message={
        manifestPath
          ? `Пригодность не оценена: в ${manifestPath} нет записи для ${cue.cue} (проверены clips[], assets[].clips[], retakes[])`
          : 'Пригодность не оценена: манифеста видео-референсов для персонажа нет'
      }
    />
  );
};

const CueCard: React.FC<{ cue: VideoCueView; manifestPath?: string }> = ({ cue, manifestPath }) => {
  const withVideo = cue.takes.filter((t) => t.video).length;
  const hasManifest = Boolean(manifestPath);
  return (
    <Card
      size="small"
      title={
        <Space wrap>
          <Text strong>{cue.cue}</Text>
          {cue.cueRef ? <Text type="secondary" style={{ fontSize: 12 }}>{cue.cueRef}</Text> : null}
          <Tag>{withVideo} ролик(ов)</Tag>
          {cue.selectedTake ? <Tag color="green">выбран {cue.selectedTake}</Tag> : null}
          {cue.requiredMvp !== undefined ? <Tag color={cue.requiredMvp ? 'gold' : 'default'}>{cue.requiredMvp ? 'нужен для MVP' : 'не обязателен для MVP'}</Tag> : null}
          {cue.manifestStatus ? <Tag color="blue">{cue.manifestStatus}</Tag> : null}
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <CueSuitability cue={cue} manifestPath={manifestPath} />
        {cue.takes.length > 1 ? (
          <Tabs
            size="small"
            defaultActiveKey={cue.selectedTake && cue.takes.some((t) => t.take === cue.selectedTake) ? cue.selectedTake : undefined}
            items={cue.takes.map((t) => ({
              key: t.take,
              label: `${t.take}${t.selected ? ' · выбран' : ''}${t.model ? ` · ${t.model.split(',')[0]}` : ''}`,
              children: <TakeView take={t} hasManifest={hasManifest} />,
            }))}
          />
        ) : cue.takes[0] ? (
          <TakeView take={cue.takes[0]} hasManifest={hasManifest} />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="файлов нет" />
        )}
      </Space>
    </Card>
  );
};

export const VideoRefsSection: React.FC<{ refs: VideoRefSection }> = ({ refs }) => (
  <Space direction="vertical" size={16} style={{ width: '100%' }}>
    {refs.manifest ? (
      <Alert
        type="warning"
        showIcon
        message={refs.overallStatus ?? 'Манифест видео-референсов'}
        description={
          <Space direction="vertical" size={6}>
            {refs.manifestScopes.length ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                Записи персонажа в манифесте: {refs.manifestScopes.join('; ')}
              </Text>
            ) : null}
            {refs.budget && Object.keys(refs.budget).length ? (
              <div>
                <Text type="secondary">{refs.budgetLabel ?? 'Бюджет'}:</Text>
                <BudgetTags budget={refs.budget} />
              </div>
            ) : null}
            {refs.budgetAll && Object.keys(refs.budgetAll).length ? (
              <div>
                <Text type="secondary">Всего по манифесту (budgetAll):</Text>
                <BudgetTags budget={refs.budgetAll} />
              </div>
            ) : null}
            {refs.nextSteps.length ? (
              <div>
                <Text type="secondary">Следующие шаги (манифест):</Text>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {refs.nextSteps.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {refs.seriesNextSteps.length ? (
              <div>
                <Text type="secondary">Следующие шаги серии героев (heroSeries — общие и по CUE этого персонажа):</Text>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {refs.seriesNextSteps.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </Space>
        }
        action={<FileActions file={refs.manifest} />}
      />
    ) : (
      <Alert type="info" showIcon message="Манифеста видео-референсов для персонажа нет — показаны файлы из art/animation-refs." />
    )}
    {refs.cues.length ? refs.cues.map((c) => <CueCard key={c.cue} cue={c} manifestPath={refs.manifest?.path} />) : <Empty description="видео-референсов нет" />}
  </Space>
);
