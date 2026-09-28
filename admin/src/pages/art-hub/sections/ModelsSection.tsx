import React, { Suspense, useEffect, useMemo, useState } from 'react';
import { Alert, Card, Col, Collapse, Descriptions, Empty, Row, Select, Space, Spin, Tag, Tooltip, Typography } from 'antd';
import type { AssetPage, RunView } from '../../../../art-hub/types';
import { FileActions, FileTable, Gallery, TWO_COLUMNS } from '../components/common';
import { basename, formatBytes, formatTime, timeAgo } from '../format';

const { Text } = Typography;
export const LazyModelViewer = React.lazy(() => import('../components/ModelViewer'));

const RunPanel: React.FC<{ run: RunView }> = ({ run }) => (
  <Space direction="vertical" style={{ width: '100%' }} size={12}>
    <Descriptions size="small" column={TWO_COLUMNS} bordered>
      <Descriptions.Item label="Каталог">
        <Text copyable style={{ fontSize: 12 }}>{run.dir}</Text>
      </Descriptions.Item>
      <Descriptions.Item label="Тип / схема">
        <Space wrap>
          <Tag>{run.kind}</Tag>
          {run.schema ? <Text type="secondary" style={{ fontSize: 12 }}>{run.schema}</Text> : null}
          {run.toolVersion ? <Tag>v{run.toolVersion}</Tag> : null}
        </Space>
      </Descriptions.Item>
      {run.title ? (
        <Descriptions.Item label="Задача" span={2}>
          {run.title}
        </Descriptions.Item>
      ) : null}
      <Descriptions.Item label="Создан">{run.createdAt ? formatTime(run.createdAt) : '—'}</Descriptions.Item>
      <Descriptions.Item label="Последнее изменение">{run.lastModified ? `${formatTime(run.lastModified)} (${timeAgo(run.lastModified)})` : '—'}</Descriptions.Item>
      {run.credits ? (
        <Descriptions.Item label="Кредиты прогона" span={2}>
          {run.credits}
        </Descriptions.Item>
      ) : null}
      {run.stages.length ? (
        <Descriptions.Item label="Этапы прогона" span={2}>
          <Space wrap>
            {run.stages.map((s) => (
              <Tooltip key={s.name} title={`${s.status}${s.backend ? `, backend ${s.backend}` : ''}${s.finishedAt ? `, ${formatTime(s.finishedAt)}` : ''}`}>
                <Tag color={s.status === 'completed' ? (s.passed === false ? 'orange' : 'geekblue') : s.status === 'failed' ? 'red' : 'default'}>
                  {s.name}: {s.status}
                  {s.passed === false ? ' (проверки не пройдены)' : ''}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        </Descriptions.Item>
      ) : null}
      {run.claims ? (
        <Descriptions.Item label="Заявления прогона" span={2}>
          <Space wrap>
            {Object.entries(run.claims).map(([k, v]) => (
              <Tag key={k}>
                {k}: {v}
              </Tag>
            ))}
          </Space>
        </Descriptions.Item>
      ) : null}
    </Descriptions>
    <Space wrap>
      {run.manifest ? (
        <span>
          манифест <FileActions file={run.manifest} />
        </span>
      ) : (
        <Text type="secondary">манифеста прогона нет</Text>
      )}
      {run.readme ? (
        <span>
          README <FileActions file={run.readme} />
        </span>
      ) : null}
      {run.otherFiles ? <Text type="secondary">прочих файлов: {run.otherFiles}</Text> : null}
    </Space>
    {run.previews.length ? <Gallery images={run.previews} size={130} /> : null}
    {run.models.length ? <FileTable files={run.models} showRole={false} /> : null}
    {run.reports.length ? (
      <Collapse size="small" items={[{ key: 'r', label: `Отчёты (${run.reports.length})`, children: <FileTable files={run.reports} showRole={false} /> }]} />
    ) : null}
  </Space>
);

export const ModelsSection: React.FC<{ page: AssetPage }> = ({ page }) => {
  const m = page.models;
  const viewable = useMemo(() => m.models.filter((f) => f.servable && (f.kind === 'glb' || f.kind === 'fbx' || f.kind === 'gltf')), [m.models]);
  const [selected, setSelected] = useState<string | undefined>(m.defaultModel);
  useEffect(() => {
    setSelected((cur) => (cur && viewable.some((v) => v.path === cur) ? cur : m.defaultModel ?? viewable[0]?.path));
  }, [page.id, m.defaultModel, viewable]);
  const file = viewable.find((v) => v.path === selected);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col xs={24} xl={15}>
          <Card
            size="small"
            title="3D-просмотр"
            extra={
              viewable.length ? (
                <Select
                  size="small"
                  style={{ width: 380, maxWidth: '60vw' }}
                  value={selected}
                  onChange={setSelected}
                  showSearch
                  optionFilterProp="label"
                  options={viewable.map((v) => ({ value: v.path, label: `${basename(v.path)} · ${formatBytes(v.bytes)}` }))}
                />
              ) : null
            }
          >
            {file ? (
              <Suspense fallback={<Spin />}>
                <LazyModelViewer file={file} height={440} />
                <div style={{ marginTop: 6 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {file.path}
                    {file.role ? ` — ${file.role}` : ''}
                  </Text>
                </div>
              </Suspense>
            ) : (
              <Empty description="Нет моделей GLB/FBX, доступных для просмотра" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card size="small" title={`Входные изображения (${m.sourceImages.length})`}>
              <Gallery images={m.sourceImages} size={110} emptyText="референсов в реестре нет" />
            </Card>
            <Card size="small" title={`Текстуры (${m.textures.length})`}>
              <Gallery images={m.textures.slice(0, 12)} size={80} caption={false} emptyText="текстур не найдено" />
              {m.textures.length > 12 ? <Text type="secondary" style={{ fontSize: 12 }}>показаны 12 из {m.textures.length} — полный список в таблице ниже</Text> : null}
            </Card>
          </Space>
        </Col>
      </Row>

      <Card size="small" title={`Превью (${m.previews.length})`}>
        <Gallery images={m.previews} emptyText="превью нет" />
      </Card>

      {m.evidenceImagesTotal ? (
        <Card
          size="small"
          title={`Свежие кадры из evidence (${m.evidenceImages.length} из ${m.evidenceImagesTotal})`}
          extra={<Text type="secondary" style={{ fontSize: 12 }}>папки docs/game-design/evidence по бэклогу ассета, новые первыми</Text>}
        >
          <Gallery images={m.evidenceImages} size={130} />
        </Card>
      ) : null}

      <Card size="small" title={`Файлы моделей (${m.models.length})`}>
        <FileTable files={m.models} pageSize={12} />
      </Card>

      <Card size="small" title={`Прогоны пайплайна art/pipeline-candidates (${m.runs.length})`}>
        {m.runs.length ? (
          <Collapse
            size="small"
            items={m.runs.map((r) => ({
              key: r.dir,
              label: (
                <Space wrap>
                  <Text strong>{r.id}</Text>
                  <Tag>{r.kind}</Tag>
                  {r.inRegistry ? <Tag color="blue">в реестре</Tag> : <Tag color="orange">нет в реестре</Tag>}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    моделей {r.models.length} · превью {r.previews.length} · отчётов {r.reports.length}
                    {r.lastModified ? ` · изменён ${timeAgo(r.lastModified)}` : ''}
                  </Text>
                </Space>
              ),
              children: <RunPanel run={r} />,
            }))}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="прогонов нет" />
        )}
      </Card>

      {m.textures.length ? (
        <Collapse size="small" items={[{ key: 't', label: `Таблица текстур (${m.textures.length})`, children: <FileTable files={m.textures} /> }]} />
      ) : null}
      {!viewable.length && m.models.length ? (
        <Alert type="info" showIcon message="Файлы моделей есть, но ни один не отдаётся в браузер (вне белого списка или вне репо)." />
      ) : null}
    </Space>
  );
};
