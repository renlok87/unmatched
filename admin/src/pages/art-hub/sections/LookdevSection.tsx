import React, { useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Alert, Button, Card, Col, Collapse, Empty, Image, Input, Row, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeftOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import type { LookdevHeroView, LookdevOverview, LookdevSheet } from '../../../../art-hub/types';
import { DocList } from '../components/DocList';
import { FileActions, Gallery, useArtHubUi } from '../components/common';
import { fileUrl } from '../api';
import { AcceptanceCards, ChecksTag, ConceptPackage } from './ConceptPackage';

const { Text } = Typography;

/** Sheets grouped by run; the newest run is open, older ones are collapsed. */
const SheetRuns: React.FC<{ sheets: LookdevSheet[]; size?: number; emptyText: string }> = ({ sheets, size = 300, emptyText }) => {
  if (!sheets.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />;
  const runs = [...new Set(sheets.map((s) => s.run))];
  return (
    <Collapse
      size="small"
      defaultActiveKey={[runs[0]!]}
      items={runs.map((run) => {
        const list = sheets.filter((s) => s.run === run);
        return {
          key: run,
          label: (
            <Space size={4} wrap>
              <Text strong>{run}</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                итерации: {[...new Set(list.map((s) => s.iteration))].join(', ')}
              </Text>
            </Space>
          ),
          children: <Gallery images={list.map((s) => s.file)} size={size} fit="contain" aspect={0.95} />,
        };
      })}
    />
  );
};

export const HeroLookdev: React.FC<{ hero: LookdevHeroView; showTitle?: boolean }> = ({ hero, showTitle = true }) => {
  const ui = useArtHubUi();
  return (
    <Card
      size="small"
      data-testid={`art-hub-lookdev-${hero.key}`}
      title={
        showTitle ? (
          <Space wrap>
            <span>{hero.name}</span>
            <Tag>{hero.key}</Tag>
            {hero.pageId ? (
              <Button size="small" type="link" onClick={() => ui.openPage(hero.pageId!, 'lookdev')}>
                страница героя
              </Button>
            ) : null}
          </Space>
        ) : undefined
      }
    >
      {hero.conceptPackage ? (
        <div style={{ marginBottom: 12 }}>
          <ConceptPackage pkg={hero.conceptPackage} />
        </div>
      ) : null}
      {hero.acceptance.length ? (
        <div style={{ marginBottom: 12 }}>
          <AcceptanceCards cards={hero.acceptance} />
        </div>
      ) : null}
      {hero.conceptPackage && !hero.concepts.length && !hero.docs.length && !hero.ueSheets.length && !hero.blenderSheets.length && !hero.evidenceSheets.length ? null : (
        <>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space wrap size={4}>
              <Text strong>Концепт hero-quality-v1</Text>
              {hero.conceptPrompts ? (
                <>
                  <Text type="secondary" style={{ fontSize: 12 }}>промпты</Text>
                  <FileActions file={hero.conceptPrompts} />
                </>
              ) : null}
            </Space>
            <Gallery images={hero.concepts} size={130} fit="contain" aspect={1.4} emptyText="концепта нет" />
          </Space>
        </Col>
        <Col xs={24} xl={14}>
          <Text strong>Отчёты look-dev</Text>
          <DocList docs={hero.docs} emptyText="отчёта look-dev нет" />
        </Col>
      </Row>
      <div style={{ marginTop: 12 }}>
        <Text strong>Листы «концепт | UE» ({hero.ueSheets.length})</Text>
        <div style={{ marginTop: 6 }}>
          <SheetRuns sheets={hero.ueSheets} emptyText="листов UE look-dev нет" />
        </div>
      </div>
      {hero.blenderSheets.length ? (
        <div style={{ marginTop: 12 }}>
          <Text strong>Blender: сравнения и зоны концепта ({hero.blenderSheets.length})</Text>
          <div style={{ marginTop: 6 }}>
            <SheetRuns sheets={hero.blenderSheets} size={260} emptyText="—" />
          </div>
        </div>
      ) : null}
      {hero.evidenceSheets.length ? (
        <Collapse
          style={{ marginTop: 12 }}
          size="small"
          items={[
            {
              key: 'ev',
              label: `Листы из docs/art-pipeline/evidence (${hero.evidenceSheets.length}, свежие первыми)`,
              children: <Gallery images={hero.evidenceSheets} size={260} fit="contain" aspect={0.5} />,
            },
          ]}
        />
      ) : null}
        </>
      )}
    </Card>
  );
};

const VERDICT_COLOR: Record<string, string> = {
  pass: 'green',
  rework: 'orange',
  rework_blender: 'orange',
  return_to_stage_1: 'red',
  return_to_stage_2: 'red',
  escalate_user: 'red',
};

/** Row of the look-dev table: what a reader needs to pick a hero without scrolling through every package. */
interface HeroRow {
  hero: LookdevHeroView;
  thumb?: LookdevHeroView['concepts'][number];
  stage: string;
  verdict?: string;
  score?: number;
  cards: number;
  /** stable-pass band 8.0–8.4 of the skill: a second acceptor of the other profile is required */
  secondAcceptor: boolean;
}

function toRow(hero: LookdevHeroView): HeroRow {
  const pkg = hero.conceptPackage;
  const last = hero.acceptance[0];
  const thumb = [pkg?.designFront, ...(pkg?.candidates.map((c) => c.file) ?? []), ...hero.concepts].find((f) => f?.servable);
  const stage = pkg ? pkg.stage : hero.ueSheets.length ? 'look-dev UE' : 'look-dev';
  return {
    hero,
    thumb,
    stage,
    verdict: last?.verdict,
    score: last?.score,
    cards: hero.acceptance.length,
    secondAcceptor: last?.verdict === 'pass' && last.score !== undefined && last.score < 8.5,
  };
}

const HeroTable: React.FC<{ rows: HeroRow[]; onOpen: (key: string) => void }> = ({ rows, onOpen }) => {
  const [query, setQuery] = useState('');
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? rows.filter((r) => r.hero.name.toLowerCase().includes(q) || r.hero.key.toLowerCase().includes(q)) : rows;
  }, [rows, query]);
  const uniq = (xs: (string | undefined)[]) => [...new Set(xs.map((x) => x ?? '—'))].sort().map((x) => ({ text: x, value: x }));
  const columns: ColumnsType<HeroRow> = [
    {
      title: '',
      key: 'thumb',
      width: 72,
      render: (_, r) =>
        r.thumb ? (
          <div onClick={(e) => e.stopPropagation()}>
            <Image src={fileUrl(r.thumb)} width={56} height={74} style={{ objectFit: 'contain', background: '#f5f5f5' }} alt={r.hero.name} />
          </div>
        ) : null,
    },
    {
      title: 'Фигура',
      key: 'name',
      sorter: (a, b) => a.hero.name.localeCompare(b.hero.name),
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.hero.name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {r.hero.conceptPackage?.assetId ?? r.hero.key}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Этап',
      key: 'stage',
      filters: uniq(rows.map((r) => r.stage)),
      onFilter: (v, r) => r.stage === v,
      render: (_, r) => <Tag color="blue">{r.stage}</Tag>,
    },
    {
      title: 'Приёмка',
      key: 'verdict',
      filters: [...uniq(rows.map((r) => r.verdict)), { text: 'нужен 2-й приёмщик', value: '__second' }],
      onFilter: (v, r) => (v === '__second' ? r.secondAcceptor : (r.verdict ?? '—') === v),
      render: (_, r) =>
        r.verdict ? (
          <Space size={4} wrap>
            <Tag color={VERDICT_COLOR[r.verdict] ?? 'default'}>{r.verdict}</Tag>
            {r.secondAcceptor ? <Tag color="gold">нужен 2-й приёмщик</Tag> : null}
          </Space>
        ) : (
          <Text type="secondary">—</Text>
        ),
    },
    {
      title: 'Коэфф.',
      key: 'score',
      width: 90,
      sorter: (a, b) => (a.score ?? -1) - (b.score ?? -1),
      render: (_, r) => (r.score !== undefined ? r.score.toFixed(1) : '—'),
    },
    {
      title: 'Проверки дизайна',
      key: 'checks',
      render: (_, r) => <ChecksTag c={r.hero.conceptPackage?.designChecks} />,
    },
    {
      title: 'Ген. / карт.',
      key: 'counts',
      width: 100,
      render: (_, r) => (
        <Text type="secondary">
          {r.hero.conceptPackage?.generationRecords ?? '—'} / {r.cards}
        </Text>
      ),
    },
  ];
  return (
    <Card
      size="small"
      title={`Фигуры (${shown.length}${shown.length !== rows.length ? ` из ${rows.length}` : ''})`}
      extra={<Input.Search allowClear placeholder="поиск по имени" style={{ width: 240 }} onChange={(e) => setQuery(e.target.value)} />}
    >
      <Table<HeroRow>
        data-testid="art-hub-lookdev-table"
        size="small"
        rowKey={(r) => r.hero.key}
        columns={columns}
        dataSource={shown}
        pagination={{ pageSize: 100, hideOnSinglePage: true, showSizeChanger: false }}
        onRow={(r) => ({ onClick: () => onOpen(r.hero.key), style: { cursor: 'pointer' } })}
      />
    </Card>
  );
};

/** Look-dev overview: a table of all figures; a click opens one figure (URL param `hero`, linkable). */
export const LookdevSection: React.FC<{ lookdev?: LookdevOverview }> = ({ lookdev }) => {
  const [params, setParams] = useSearchParams();
  const heroKey = params.get('hero');
  const rows = useMemo(() => (lookdev ? lookdev.heroes.map(toRow) : []), [lookdev]);
  const open = useCallback(
    (key?: string) => {
      const next = new URLSearchParams(params);
      if (key) next.set('hero', key);
      else next.delete('hero');
      setParams(next);
      window.scrollTo({ top: 0 });
    },
    [params, setParams],
  );
  if (!lookdev) return <Empty />;
  const idx = heroKey ? lookdev.heroes.findIndex((h) => h.key === heroKey) : -1;
  if (idx >= 0) {
    const hero = lookdev.heroes[idx]!;
    const prev = lookdev.heroes[idx - 1];
    const next = lookdev.heroes[idx + 1];
    return (
      <Space direction="vertical" size={12} style={{ width: '100%' }} data-testid="art-hub-lookdev">
        <Space wrap>
          <Button icon={<ArrowLeftOutlined />} onClick={() => open()}>
            к таблице
          </Button>
          <Button icon={<LeftOutlined />} disabled={!prev} onClick={() => open(prev?.key)}>
            {prev?.name ?? 'назад'}
          </Button>
          <Button disabled={!next} onClick={() => open(next?.key)}>
            {next?.name ?? 'вперёд'} <RightOutlined />
          </Button>
          <Text type="secondary">
            {idx + 1} / {lookdev.heroes.length}
          </Text>
        </Space>
        <HeroLookdev hero={hero} />
      </Space>
    );
  }
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid="art-hub-lookdev">
      <Alert
        type="info"
        showIcon
        message="Look-dev и концепты"
        description={
          <span>
            Эталон сравнения — концепт <Text code>{lookdev.conceptRoot}/&lt;герой&gt;/</Text>. Листы «концепт | UE» — кадры редактора UE из
            прогонов look-dev (<Text code>review/&lt;итерация&gt;/</Text>). Статусы здесь не повышаются: художественная приёмка — только актом.
            Клик по строке открывает фигуру.
          </span>
        }
      />
      {heroKey ? <Alert type="warning" showIcon message={`Фигура «${heroKey}» не найдена — показана таблица`} /> : null}
      {rows.length ? <HeroTable rows={rows} onOpen={open} /> : <Empty description="look-dev данных нет" />}
      {lookdev.references.length ? (
        <Collapse
          size="small"
          items={[{ key: 'ref', label: 'Эталон качества', children: <Gallery images={lookdev.references} size={240} fit="contain" aspect={1} /> }]}
        />
      ) : null}
    </Space>
  );
};
