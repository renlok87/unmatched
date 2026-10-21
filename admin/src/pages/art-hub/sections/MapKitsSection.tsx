/**
 * «Карты»: map kits (a prop library per game map). Landing = one card per map; `?item=maps&map=<id>`
 * opens a map: description, palette, concept images and the props table.
 *
 * Usage: <MapKitsSection mapKits={data.mapKits} />
 */
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { Alert, Button, Card, Col, Collapse, Descriptions, Empty, Row, Space, Statistic, Tag, Tooltip, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import type { MapKitConceptView, MapKitsOverview, MapKitView } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { FileTable, Gallery, LongText } from '../components/common';
import { MAP_KIT_STAGE, MapKitPropsTable, MapKitStageTag } from '../components/MapKitProps';
import { formatNumber, formatTime } from '../format';

const { Text, Title } = Typography;

/** Concept groups in display order; unknown kinds go last under their own name. */
const KIND_TITLE: Record<string, string> = {
  concept: 'Концепты',
  moodboard: 'Мудборды',
  base: 'Основы (базовые картинки)',
  reference: 'Референсы',
};

const Swatches: React.FC<{ colors: string[] }> = ({ colors }) =>
  colors.length ? (
    <Space size={8} wrap>
      {colors.map((c) => (
        <Tooltip key={c} title={c}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: 40, height: 40, borderRadius: 6, border: '1px solid #d9d9d9', background: c }} />
            <Text type="secondary" copyable={{ text: c }} style={{ fontSize: 10 }}>
              {c}
            </Text>
          </div>
        </Tooltip>
      ))}
    </Space>
  ) : (
    <Text type="secondary">—</Text>
  );

const Topology: React.FC<{ map: MapKitView }> = ({ map }) =>
  map.topology ? (
    <Tooltip title={map.topology.field ? `поле DE: ${map.topology.field}` : undefined}>
      <Tag color="geekblue">
        клеток {map.topology.cells ?? '—'} · рёбер {map.topology.edges ?? '—'}
      </Tag>
    </Tooltip>
  ) : (
    <Tag>топологии DE нет</Tag>
  );

const StageCounts: React.FC<{ map: MapKitView }> = ({ map }) => (
  <Space size={[2, 4]} wrap>
    {map.counts.byStage.length ? map.counts.byStage.map((s) => <MapKitStageTag key={s.stage} stage={s.stage} count={s.count} />) : <Text type="secondary">пропсов нет</Text>}
  </Space>
);

// ------------------------------------------------------------------ landing

const MapCard: React.FC<{ map: MapKitView; onOpen: () => void }> = ({ map, onOpen }) => (
  <Card
    hoverable
    size="small"
    onClick={onOpen}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onOpen();
      }
    }}
    tabIndex={0}
    role="link"
    aria-label={`Открыть карту ${map.boardNameRu ?? map.boardName}`}
    data-testid={`art-hub-map-card-${map.id}`}
    cover={
      map.thumb ? (
        <img src={fileUrl(map.thumb)} alt={map.thumb.role ?? map.boardName} loading="lazy" style={{ width: '100%', height: 160, objectFit: 'cover', borderRadius: '8px 8px 0 0' }} />
      ) : (
        <div style={{ height: 160, display: 'flex', flexDirection: 'column', borderRadius: '8px 8px 0 0', overflow: 'hidden', background: '#fafafa' }}>
          <div style={{ display: 'flex', flex: 1 }}>
            {map.paletteHex.map((c) => (
              <div key={c} style={{ flex: 1, background: c }} />
            ))}
          </div>
          <Text type="secondary" style={{ fontSize: 12, textAlign: 'center', padding: '4px 0' }}>
            концептов пока нет
          </Text>
        </div>
      )
    }
  >
    <Space direction="vertical" size={6} style={{ width: '100%' }}>
      <div>
        <Title level={5} style={{ margin: 0 }}>
          {map.boardNameRu ?? map.boardName}
        </Title>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {map.boardName}
        </Text>
      </div>
      <Space size={[4, 4]} wrap>
        {map.set ? <Tag color="purple">{map.set}</Tag> : null}
        <Topology map={map} />
        <Tag color="blue">пропсов {map.counts.total}</Tag>
      </Space>
      {map.heroes.length ? (
        <Space size={[2, 2]} wrap>
          {map.heroes.map((h) => (
            <Tag key={h} style={{ marginInlineEnd: 0 }}>
              {h}
            </Tag>
          ))}
        </Space>
      ) : null}
      <StageCounts map={map} />
      <Text style={{ fontSize: 12 }}>
        Tripo: {map.credits.spent > 0 ? `${formatNumber(map.credits.spent)} кр. (${map.credits.tasks} задач)` : 'кредиты не тратились'}
        {map.concepts.length ? ` · концептов ${map.concepts.length}` : ''}
      </Text>
      {map.error ? <Alert type="error" showIcon message={map.error} /> : null}
      {map.problems.length ? <Tag color="warning">замечаний: {map.problems.length}</Tag> : null}
    </Space>
  </Card>
);

const Landing: React.FC<{ kits: MapKitsOverview; onOpen: (id: string) => void }> = ({ kits, onOpen }) => (
  <Space direction="vertical" size={16} style={{ width: '100%' }}>
    <Alert
      type="info"
      showIcon
      message="Наборы пропсов карт"
      description={
        <span>
          Данные — <Text code>{kits.root}/&lt;карта&gt;/&#123;map,props,status&#125;.json</Text> и картинки в <Text code>art/imagegen/mapkit-&lt;карта&gt;/</Text>.
          Пропс без записи в <Text code>status.json</Text> считается «в списке». Объём работы — подготовка ассетов: доски в игру этим разделом не
          включаются.
        </span>
      }
    />
    {!kits.found ? (
      <Empty description={<span>Папки <Text code>{kits.root}</Text> нет — раздел заполнится, когда она появится</span>} />
    ) : kits.maps.length === 0 ? (
      <Empty description="карт нет" />
    ) : (
      <>
        <Card size="small">
          <Row gutter={[24, 12]} align="middle">
            <Col>
              <Statistic title="Карт" value={kits.totals.maps} />
            </Col>
            <Col>
              <Statistic title="Пропсов" value={kits.totals.props} />
            </Col>
            <Col>
              <Statistic title="Кредитов Tripo" value={kits.totals.credits} formatter={(v) => formatNumber(Number(v))} />
            </Col>
            <Col flex="auto">
              <Text type="secondary" style={{ fontSize: 12 }}>По стадиям</Text>
              <div>
                <Space size={[2, 4]} wrap>
                  {kits.totals.byStage.map((s) => (
                    <MapKitStageTag key={s.stage} stage={s.stage} count={s.count} />
                  ))}
                </Space>
              </div>
            </Col>
          </Row>
        </Card>
        <Row gutter={[16, 16]}>
          {kits.maps.map((m) => (
            <Col key={m.id} xs={24} md={12} xxl={8}>
              <MapCard map={m} onOpen={() => onOpen(m.id)} />
            </Col>
          ))}
        </Row>
        <Card size="small" title="Стадии пропса">
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
            {Object.entries(MAP_KIT_STAGE).map(([k, s]) => (
              <li key={k}>
                <Text code style={{ fontSize: 11 }}>{k}</Text> — {s.label}: {s.hint}
              </li>
            ))}
          </ul>
        </Card>
      </>
    )}
  </Space>
);

// ------------------------------------------------------------------ detail

const ConceptGroups: React.FC<{ concepts: MapKitConceptView[] }> = ({ concepts }) => {
  const kinds = [...new Set(concepts.map((c) => c.kind))].sort((a, b) => {
    const order = Object.keys(KIND_TITLE);
    const ra = order.indexOf(a) < 0 ? order.length : order.indexOf(a);
    const rb = order.indexOf(b) < 0 ? order.length : order.indexOf(b);
    return ra - rb || a.localeCompare(b);
  });
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      {kinds.map((k) => {
        const list = concepts.filter((c) => c.kind === k);
        return (
          <div key={k}>
            <Text strong>
              {KIND_TITLE[k] ?? k} ({list.length})
            </Text>
            <div style={{ marginTop: 6 }}>
              <Gallery images={list.map((c) => c.file)} size={240} aspect={0.62} fit="contain" />
            </div>
            {list.some((c) => c.status) ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {list.filter((c) => c.status).map((c) => `${c.title}: ${c.status}`).join(' · ')}
              </Text>
            ) : null}
          </div>
        );
      })}
    </Space>
  );
};

const MapDetail: React.FC<{ map: MapKitView; onBack: () => void }> = ({ map, onBack }) => {
  const files = [map.files.map, map.files.props, ...(map.files.status.exists ? [map.files.status] : [])];
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid={`art-hub-map-${map.id}`}>
      <Card size="small">
        <Space direction="vertical" size={6} style={{ width: '100%' }}>
          <Space wrap align="center">
            <Button icon={<ArrowLeftOutlined />} onClick={onBack} data-testid="art-hub-map-back">
              Все карты
            </Button>
            <Title level={4} style={{ margin: 0 }}>
              {map.boardNameRu ?? map.boardName}
            </Title>
            <Text type="secondary">{map.boardName}</Text>
            {map.set ? <Tag color="purple">{map.set}</Tag> : null}
            <Topology map={map} />
            <Tag color="blue">пропсов {map.counts.total}</Tag>
          </Space>
          <Space wrap size={[4, 4]}>
            <Text type="secondary">Герои набора:</Text>
            {map.heroes.length ? map.heroes.map((h) => <Tag key={h}>{h}</Tag>) : <Text type="secondary">—</Text>}
            {map.boardId ? (
              <Text type="secondary" copyable={{ text: map.boardId }} style={{ fontSize: 11 }}>
                Board {map.boardId}
              </Text>
            ) : null}
          </Space>
          <StageCounts map={map} />
        </Space>
      </Card>

      {map.error ? <Alert type="error" showIcon message={`Карта описана не полностью: ${map.error}`} /> : null}
      {map.problems.length ? (
        <Alert
          type="warning"
          showIcon
          message={`Замечания к данным карты: ${map.problems.length}`}
          description={
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {map.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          }
        />
      ) : null}

      <Card size="small" title="Описание карты">
        <Descriptions size="small" column={1} bordered styles={{ label: { width: 190 } }}>
          <Descriptions.Item label="Почему выбрана"><LongText text={map.whyChosenRu} rows={4} /></Descriptions.Item>
          <Descriptions.Item label="Настроение"><LongText text={map.moodRu} rows={4} /></Descriptions.Item>
          <Descriptions.Item label="Освещение"><LongText text={map.lightingRu} rows={3} /></Descriptions.Item>
          <Descriptions.Item label="Задник"><LongText text={map.backdropRu} rows={3} /></Descriptions.Item>
          <Descriptions.Item label="Палитра"><Swatches colors={map.paletteHex} /></Descriptions.Item>
          <Descriptions.Item label="Масштаб"><LongText text={map.scale} rows={2} /></Descriptions.Item>
          <Descriptions.Item label="Стиль для генерации"><LongText text={map.styleEn} rows={2} /></Descriptions.Item>
        </Descriptions>
        {map.scopeNoteRu ? <Alert style={{ marginTop: 8 }} type="info" showIcon message="Границы работы" description={map.scopeNoteRu} /> : null}
      </Card>

      <Card size="small" title={`Концепты и картинки Gemini (${map.concepts.length})`}>
        {map.concepts.length ? (
          <ConceptGroups concepts={map.concepts} />
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span>
                Концептов пока нет — пути появятся в <Text code>concepts</Text> файла <Text code>map.json</Text> (картинки в{' '}
                <Text code>{map.images.dir}/</Text>)
              </span>
            }
          />
        )}
        {map.images.unlistedTotal > 0 ? (
          <Collapse
            size="small"
            ghost
            style={{ marginTop: 8 }}
            items={[
              {
                key: 'unlisted',
                label: (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    В папке есть картинки, которых нет в map.json и status.json: {map.images.unlistedTotal} (всего изображений в папке {map.images.total})
                  </Text>
                ),
                children: (
                  <>
                    <Gallery images={map.images.unlisted} size={150} />
                    {map.images.unlistedTotal > map.images.unlisted.length ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Показаны первые {map.images.unlisted.length} из {map.images.unlistedTotal}.
                      </Text>
                    ) : null}
                  </>
                ),
              },
            ]}
          />
        ) : null}
      </Card>

      <Card
        size="small"
        title={`Пропсы (${map.counts.total})`}
        extra={map.statusUpdatedAt ? <Text type="secondary" style={{ fontSize: 12 }}>status.json: {formatTime(map.statusUpdatedAt)}</Text> : null}
      >
        {!map.files.status.exists ? (
          <Alert
            style={{ marginBottom: 8 }}
            type="info"
            showIcon
            message={
              <span>
                Файла <Text code>status.json</Text> ещё нет — все пропсы показаны как «в списке».
              </span>
            }
          />
        ) : null}
        <MapKitPropsTable map={map} />
      </Card>

      <Card size="small" title="Файлы карты">
        <FileTable files={files} showRole pageSize={10} />
      </Card>
    </Space>
  );
};

// ------------------------------------------------------------------ section

export const MapKitsSection: React.FC<{ mapKits?: MapKitsOverview }> = ({ mapKits: kits }) => {
  const [params, setParams] = useSearchParams();
  if (!kits) return <Empty />;
  const wanted = params.get('map');
  const selected = wanted ? kits.maps.find((m) => m.id === wanted) : undefined;

  const open = (id?: string) => {
    const next = new URLSearchParams(params);
    if (id) next.set('map', id);
    else next.delete('map');
    setParams(next);
    window.scrollTo({ top: 0 });
  };

  return (
    <div data-testid="art-hub-maps">
      {wanted && !selected ? (
        <Alert style={{ marginBottom: 12 }} type="warning" showIcon message={`Карта «${wanted}» не найдена — показан список карт`} />
      ) : null}
      {selected ? <MapDetail key={selected.id} map={selected} onBack={() => open()} /> : <Landing kits={kits} onOpen={open} />}
    </div>
  );
};
