/**
 * «Арт-хаб»: read-only dashboard over the art pipeline files of the repo
 * (models, rig, skeletal clips, video references, video→skeleton, sounds,
 * credits) and the game-audio track. Data comes from the dev-only Vite plugin (admin/art-hub).
 */
import React, { Suspense, useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Alert, Badge, Button, Card, Col, Empty, Menu, Modal, Result, Row, Space, Spin, Switch, Tabs, Tag, Tooltip, Typography } from 'antd';
import type { MenuProps } from 'antd';
import { BgColorsOutlined, BookOutlined, DashboardOutlined, EyeOutlined, ProjectOutlined, ReloadOutlined, SoundOutlined } from '@ant-design/icons';
import type { ArtHubData, AssetPage, FileRef, LookdevHeroView } from '../../../art-hub/types';
import { IS_DEV, useArtHubData } from './api';
import { ArtHubUiContext, StageTag, StatusTag, type ArtHubUi } from './components/common';
import { TextPreview } from './components/TextPreview';
import { formatTime, timeAgo } from './format';
import { AudioSection } from './sections/AudioSection';
import { ClipsSection } from './sections/ClipsSection';
import { DecisionsSection } from './sections/DecisionsSection';
import { HeroLookdev, LookdevSection } from './sections/LookdevSection';
import { MaterialsSection } from './sections/MaterialsSection';
import { PlanSection } from './sections/PlanSection';
import { UeLayersTable } from './sections/UeLayersSection';
import { LazyModelViewer, ModelsSection } from './sections/ModelsSection';
import { PipelineHealthSection } from './sections/PipelineHealthSection';
import { RigSection } from './sections/RigSection';
import { CreditsSectionView, SoundsSection } from './sections/SoundsCreditsSections';
import { SummarySection } from './sections/SummarySection';
import { VideoRefsSection } from './sections/VideoRefsSection';
import { VideoToMotionSection } from './sections/VideoToMotionSection';

const { Title, Text } = Typography;
const HEALTH = 'health';

/** Overview pages (not tied to one asset). */
const OVERVIEW: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: HEALTH, label: 'Состояние пайплайна', icon: <DashboardOutlined /> },
  { key: 'plan', label: 'План и задачи', icon: <ProjectOutlined /> },
  { key: 'lookdev', label: 'Look-dev и концепты', icon: <EyeOutlined /> },
  { key: 'materials', label: 'Библиотека материалов', icon: <BgColorsOutlined /> },
  { key: 'audio', label: 'Звук', icon: <SoundOutlined /> },
  { key: 'decisions', label: 'Решения', icon: <BookOutlined /> },
];

/**
 * Status shown for a page: the freshest registry layer when it differs from the
 * entry status (the entry status stays visible; nothing is upgraded).
 */
const PageStatus: React.FC<{ page: AssetPage; compact?: boolean }> = ({ page, compact }) => {
  const l = page.latestLayer;
  if (!l?.status || l.status === page.status) return <StatusTag status={page.status} />;
  return (
    <Tooltip title={`Статус самого свежего слоя реестра${l.date ? ` (${l.date})` : ''}: «${l.layer}». Статус записи в реестре: «${page.status ?? '—'}».`}>
      <span data-testid={`art-hub-latest-${page.id}`}>
        <StatusTag status={l.status} label={compact ? l.status : `${l.status} (свежий слой${l.date ? ` ${l.date}` : ''})`} />
        <Text type="secondary" style={{ fontSize: 11 }}>
          {compact ? <br /> : ' '}запись: {page.status ?? '—'}
        </Text>
      </span>
    </Tooltip>
  );
};

const NavLabel: React.FC<{ page: AssetPage }> = ({ page }) => (
  <div data-testid={`art-hub-nav-${page.id}`} style={{ lineHeight: 1.25, whiteSpace: 'normal', padding: '4px 0' }}>
    <div style={{ fontWeight: 500 }}>
      {page.shortName}
      {page.instances > 1 ? <Text type="secondary"> ×{page.instances}</Text> : null}
    </div>
    <div style={{ marginTop: 2 }}>
      <PageStatus page={page} compact />
    </div>
  </div>
);

const OverviewView: React.FC<{ item: string; data: ArtHubData }> = ({ item, data }) => {
  switch (item) {
    case 'plan':
      return <PlanSection data={data} />;
    case 'lookdev':
      return <LookdevSection lookdev={data.lookdev} />;
    case 'materials':
      return <MaterialsSection materials={data.materials} />;
    case 'audio':
      return <AudioSection audio={data.audio} />;
    case 'decisions':
      return <DecisionsSection decisions={data.decisions} />;
    default:
      return <PipelineHealthSection data={data} />;
  }
};

const AssetView: React.FC<{ page: AssetPage; tab: string; onTab: (t: string) => void; lookdev?: LookdevHeroView }> = ({ page, tab, onTab, lookdev }) => {
  const ueFound = page.ueLayers?.layers.filter((l) => l.onDisk || l.registry.length || l.clipStatuses).length ?? 0;
  const videoCount = page.videoRefs?.cues.reduce((n, c) => n + c.takes.filter((t) => t.video).length, 0) ?? 0;
  const items = [
    { key: 'summary', label: 'Сводка', children: <SummarySection page={page} /> },
    { key: 'models', label: `Модели (${page.models.models.length})`, children: <ModelsSection page={page} /> },
    ...(page.kind === 'character'
      ? [
          { key: 'ue', label: `UE-слои (${ueFound})`, children: page.ueLayers ? <UeLayersTable ue={page.ueLayers} /> : <Empty description="нет записи в реестре" /> },
          {
            key: 'lookdev',
            label: 'Look-dev и концепт',
            children: lookdev ? <HeroLookdev hero={lookdev} showTitle={false} /> : <Empty description="look-dev данных нет" />,
          },
          { key: 'rig', label: 'Риг', children: page.rig ? <RigSection page={page} rig={page.rig} /> : <Empty /> },
          {
            key: 'clips',
            label: `Скелетные анимации (${page.clips?.slots.length ?? 0})`,
            children: page.clips ? <ClipsSection clips={page.clips} /> : <Empty />,
          },
          { key: 'video', label: `Видео-референсы (${videoCount})`, children: page.videoRefs ? <VideoRefsSection refs={page.videoRefs} /> : <Empty /> },
          { key: 'v2m', label: 'Видео → скелет', children: page.videoToMotion ? <VideoToMotionSection v2m={page.videoToMotion} /> : <Empty /> },
          {
            key: 'sounds',
            label: (
              <span>
                Звуки {page.sounds?.status ? <Tag style={{ marginLeft: 4 }}>{page.sounds.status}</Tag> : <Badge count={page.sounds?.files.length ?? 0} />}
              </span>
            ),
            children: page.sounds ? <SoundsSection sounds={page.sounds} /> : <Empty />,
          },
        ]
      : []),
    { key: 'credits', label: 'Кредиты', children: <CreditsSectionView credits={page.credits} /> },
  ];
  const active = items.some((i) => i.key === tab) ? tab : 'summary';
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }} data-testid={`art-hub-page-${page.id}`}>
      <Card size="small">
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Space wrap align="center">
            <Title level={4} style={{ margin: 0 }}>
              {page.name}
            </Title>
            {page.instances > 1 ? <Tag color="purple">экземпляров: {page.instances}</Tag> : null}
            {!page.inRegistry ? <Tag color="orange">нет в реестре</Tag> : null}
          </Space>
          <Space wrap>
            <Text type="secondary" copyable>
              {page.id}
            </Text>
            <PageStatus page={page} />
            <StageTag stage={page.stage} />
            {page.backlog.map((b) => (
              <Tag key={b}>{b}</Tag>
            ))}
            {page.lastModified ? <Text type="secondary" style={{ fontSize: 12 }}>файлы менялись {timeAgo(page.lastModified)}</Text> : null}
          </Space>
        </Space>
      </Card>
      <Tabs activeKey={active} onChange={onTab} items={items} destroyOnHidden />
    </Space>
  );
};

export const ArtHubPage: React.FC = () => {
  const [auto, setAuto] = useState(true);
  const { data, error, loading, lastFetched, refresh } = useArtHubData(auto);
  const [params, setParams] = useSearchParams();
  const item = params.get('item') ?? HEALTH;
  const tab = params.get('tab') ?? 'summary';
  const [textFile, setTextFile] = useState<FileRef>();
  const [modelFile, setModelFile] = useState<{ file: FileRef; title?: string }>();

  const openPage = useCallback(
    (id: string, t?: string) => {
      const next = new URLSearchParams(params);
      next.set('item', id);
      if (t) next.set('tab', t);
      else next.delete('tab');
      setParams(next);
      window.scrollTo({ top: 0 });
    },
    [params, setParams],
  );
  const setTab = useCallback(
    (t: string) => {
      const next = new URLSearchParams(params);
      next.set('tab', t);
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const ui = useMemo<ArtHubUi | null>(
    () =>
      data
        ? {
            vocab: data.vocab,
            previewText: (f) => setTextFile(f),
            view3D: (f, title) => setModelFile({ file: f, title }),
            openPage,
          }
        : null,
    [data, openPage],
  );

  const pages = useMemo(() => (data ? [...data.characters, ...data.props] : []), [data]);
  const current = pages.find((p) => p.id === item);
  const overviewItem = OVERVIEW.some((o) => o.key === item) ? item : HEALTH;

  const menuItems: MenuProps['items'] = useMemo(() => {
    if (!data) return [];
    const itemStyle = { height: 'auto', lineHeight: 1.25, paddingTop: 4, paddingBottom: 4 };
    return [
      {
        type: 'group',
        key: 'g-overview',
        label: 'Обзор',
        children: OVERVIEW.map((o) => ({ key: o.key, icon: o.icon, label: <span data-testid={`art-hub-nav-${o.key}`}>{o.label}</span> })),
      },
      {
        type: 'group',
        key: 'g-chars',
        label: `Персонажи (${data.characters.length})`,
        children: data.characters.map((p) => ({ key: p.id, label: <NavLabel page={p} />, style: itemStyle })),
      },
      {
        type: 'group',
        key: 'g-props',
        label: `Пропсы и окружение (${data.props.length})`,
        children: data.props.map((p) => ({ key: p.id, label: <NavLabel page={p} />, style: itemStyle })),
      },
    ];
  }, [data]);

  if (!IS_DEV) {
    return (
      <Result
        status="info"
        title="Арт-хаб доступен только на dev-сервере админки"
        subTitle="Страница читает файлы репозитория через dev-эндпоинт /__art-hub, которого нет в production-сборке. Запустите `npm run dev` в каталоге admin/ и откройте http://localhost:5480/art-hub. Снимок данных без сервера: `npm run art-hub:snapshot` → docs/art-pipeline/art-hub-snapshot.json."
      />
    );
  }

  return (
    <div data-testid="art-hub">
      <Row justify="space-between" align="middle" gutter={[16, 8]} style={{ marginBottom: 12 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            Арт-хаб
          </Title>
          <Text type="secondary">
            Живое отражение файлов арт-пайплайна: план, модели, UE-слои, look-dev, материалы, риг, клипы, видео-референсы, звук (реестр,
            реплики, микс), кредиты, решения. Только чтение.
          </Text>
        </Col>
        <Col>
          <Space wrap>
            {data ? (
              <Tooltip title={`агрегация ${formatTime(data.generatedAt)} за ${data.durationMs} мс; проверено ${formatTime(data.checkedAt ?? data.generatedAt)}`}>
                <Tag>данные: {lastFetched ? lastFetched.toLocaleTimeString('ru-RU') : '—'}</Tag>
              </Tooltip>
            ) : null}
            <Tooltip title="Запрашивать свежие данные каждые 30 секунд">
              <Space size={4}>
                <Switch size="small" checked={auto} onChange={setAuto} data-testid="art-hub-auto" />
                <Text>авто 30 с</Text>
              </Space>
            </Tooltip>
            <Button icon={<ReloadOutlined />} loading={loading} onClick={refresh} data-testid="art-hub-refresh">
              Обновить
            </Button>
          </Space>
        </Col>
      </Row>

      {error ? (
        <Alert
          style={{ marginBottom: 12 }}
          type="error"
          showIcon
          message="Не удалось получить данные арт-хаба"
          description={error}
          action={
            <Button size="small" onClick={refresh}>
              повторить
            </Button>
          }
        />
      ) : null}
      {data?.warnings.length ? (
        <Alert
          style={{ marginBottom: 12 }}
          type="warning"
          showIcon
          message={`Предупреждения агрегатора: ${data.warnings.length}`}
          description={
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {data.warnings.slice(0, 10).map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          }
        />
      ) : null}

      {!data || !ui ? (
        <div style={{ padding: 48, textAlign: 'center' }}>{loading ? <Spin tip="Собираю данные…" size="large"><div style={{ height: 60 }} /></Spin> : <Empty />}</div>
      ) : (
        <ArtHubUiContext.Provider value={ui}>
          <Row gutter={16} wrap={false}>
            <Col flex="250px">
              <Card size="small" styles={{ body: { padding: 4 } }} style={{ position: 'sticky', top: 12 }}>
                <Menu
                  mode="inline"
                  selectedKeys={[current ? current.id : overviewItem]}
                  items={menuItems}
                  onClick={({ key }) => openPage(key)}
                  style={{ borderInlineEnd: 'none' }}
                />
              </Card>
            </Col>
            <Col flex="auto" style={{ minWidth: 0 }}>
              {current ? (
                <AssetView
                  key={current.id}
                  page={current}
                  tab={tab}
                  onTab={setTab}
                  lookdev={data.lookdev?.heroes.find((h) => h.pageId === current.id)}
                />
              ) : (
                <>
                  {item !== overviewItem ? <Alert style={{ marginBottom: 12 }} type="warning" message={`Раздел «${item}» не найден — показано состояние пайплайна`} /> : null}
                  <OverviewView item={overviewItem} data={data} />
                </>
              )}
            </Col>
          </Row>
          <TextPreview file={textFile} onClose={() => setTextFile(undefined)} />
          <Modal
            open={Boolean(modelFile)}
            onCancel={() => setModelFile(undefined)}
            footer={null}
            width="min(1200px, 94vw)"
            destroyOnHidden
            title={modelFile ? `3D: ${modelFile.file.path.split('/').pop()}${modelFile.title ? ` — ${modelFile.title}` : ''}` : ''}
          >
            {modelFile ? (
              <Suspense fallback={<Spin />}>
                <LazyModelViewer file={modelFile.file} height={560} />
              </Suspense>
            ) : null}
          </Modal>
        </ArtHubUiContext.Provider>
      )}
    </div>
  );
};

export default ArtHubPage;
