import React from 'react';
import { Alert, Button, Card, Col, Collapse, Empty, Row, Space, Tag, Typography } from 'antd';
import type { LookdevHeroView, LookdevOverview, LookdevSheet } from '../../../../art-hub/types';
import { DocList } from '../components/DocList';
import { FileActions, Gallery, useArtHubUi } from '../components/common';

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
    </Card>
  );
};

export const LookdevSection: React.FC<{ lookdev?: LookdevOverview }> = ({ lookdev }) => {
  if (!lookdev) return <Empty />;
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
          </span>
        }
      />
      {lookdev.references.length ? (
        <Card size="small" title="Эталон качества">
          <Gallery images={lookdev.references} size={240} fit="contain" aspect={1} />
        </Card>
      ) : null}
      {lookdev.heroes.length ? lookdev.heroes.map((h) => <HeroLookdev key={h.key} hero={h} />) : <Empty description="look-dev данных нет" />}
    </Space>
  );
};
