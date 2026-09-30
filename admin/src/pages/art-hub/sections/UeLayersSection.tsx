import React from 'react';
import { Alert, Button, Card, Empty, Space, Table, Tag, Tooltip, Typography } from 'antd';
import type { AssetPage, UeLayerView, UeLayersSection as UeLayersData } from '../../../../art-hub/types';
import { ClipStatusTag, FileTable, StageTag, StatusTag, useArtHubUi } from '../components/common';

const { Text } = Typography;

const hasEvidence = (l: UeLayerView) => Boolean(l.onDisk || l.registry.length || l.clipStatuses || l.mentionsTotal);

const DiskTag: React.FC<{ l: UeLayerView }> = ({ l }) => {
  if (l.onDisk === null) return <Tag>UE-проект не найден</Tag>;
  if (!l.onDisk) return <Tag>папки нет</Tag>;
  return (
    <Tooltip title="Папка есть в unreal/Unmatched/Content (проверено по диску; файлы не отдаются)">
      <Tag color="success">есть · {l.uassetCount ?? 0} uasset</Tag>
    </Tooltip>
  );
};

/** Status cell: registry layers first, then clip-manifest ue.status; nothing is inferred. */
const LayerStatus: React.FC<{ l: UeLayerView; compact?: boolean }> = ({ l, compact }) => (
  <Space direction="vertical" size={2}>
    {compact
      ? [...new Set(l.registry.map((r) => r.status ?? ''))].map((st) => {
          const rows = l.registry.filter((r) => (r.status ?? '') === st);
          return (
            <Tooltip key={st} title={rows.map((r) => r.layer).join('\n')}>
              <span>
                <StatusTag status={st || null} label={rows.length > 1 ? `${st} ×${rows.length}` : undefined} />
              </span>
            </Tooltip>
          );
        })
      : l.registry.map((r) => (
          <Tooltip key={`${r.entryId}:${r.layer}`} title={`слой реестра (${r.entryId}): ${r.layer}`}>
            <span>
              <StatusTag status={r.status} />
              <StageTag stage={r.stage} />
            </span>
          </Tooltip>
        ))}
    {l.clipStatuses
      ? Object.entries(l.clipStatuses).map(([st, n]) => (
          <span key={st}>
            <ClipStatusTag status={st} /> <Text type="secondary" style={{ fontSize: 12 }}>клипов: {n}</Text>
          </span>
        ))
      : null}
    {!l.registry.length && !l.clipStatuses ? (
      <Tooltip title="Слой не записан в asset-registry.json и не описан в clip-manifest: статус не присваивается (см. документы-упоминания)">
        <Tag color="orange">в реестре нет</Tag>
      </Tooltip>
    ) : null}
  </Space>
);

export const UeLayersTable: React.FC<{ ue: UeLayersData }> = ({ ue }) => {
  const found = ue.layers.filter(hasEvidence);
  const standard = found.filter((l) => l.standard);
  const other = found.filter((l) => !l.standard);
  const absent = ue.layers.filter((l) => l.standard && !hasEvidence(l)).map((l) => l.key);
  const table = (rows: UeLayerView[]) => (
    <Table<UeLayerView>
      size="small"
      rowKey="key"
      pagination={false}
      dataSource={rows}
      scroll={{ x: 1000 }}
      columns={[
        {
          title: 'Слой UE',
          key: 'k',
          width: '28%',
          render: (_, l) => (
            <div>
              <Text strong>{l.key}</Text>
              <div>
                <Text code copyable={{ text: l.gamePath }} style={{ fontSize: 11, wordBreak: 'break-all' }}>
                  {l.gamePath}
                </Text>
              </div>
            </div>
          ),
        },
        { title: 'Папка в UE', key: 'd', width: 160, render: (_, l) => <DiskTag l={l} /> },
        { title: 'Статус (реестр / clip-manifest)', key: 's', width: 260, render: (_, l) => <LayerStatus l={l} /> },
        {
          title: 'Прогоны',
          key: 'r',
          render: (_, l) =>
            l.runs.length ? (
              <Space size={[2, 2]} wrap>
                {l.runs.map((r) => (
                  <Tag key={r}>{r}</Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary">—</Text>
            ),
        },
        { title: 'Упоминаний', key: 'm', width: 100, render: (_, l) => l.mentionsTotal },
      ]}
      expandable={{
        rowExpandable: (l) => l.mentions.length > 0 || l.registry.length > 0,
        expandedRowRender: (l) => (
          <Space direction="vertical" style={{ width: '100%' }}>
            {l.registry.length ? (
              <div>
                <Text strong style={{ fontSize: 12 }}>Слои реестра, где упомянут путь:</Text>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
                  {l.registry.map((r) => (
                    <li key={`${r.entryId}:${r.layer}`}>
                      {r.layer} — <Text type="secondary">{r.status ?? '—'}</Text>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <FileTable files={l.mentions} pageSize={12} emptyText="упоминаний нет" />
            {l.mentionsTotal > l.mentions.length ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                показано {l.mentions.length} из {l.mentionsTotal} (документы первыми)
              </Text>
            ) : null}
          </Space>
        ),
      }}
    />
  );
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }} data-testid="art-hub-ue-layers">
      <Alert
        type="info"
        showIcon
        message={
          <span>
            Папка героя в UE: <Text code>/Game/PipelineCandidates/{ue.folder}/</Text> <Text type="secondary">(найдена: {ue.folderSource})</Text>
          </span>
        }
        description="Пути UE показаны только текстом: каталог unreal/ не отдаётся в браузер, наличие папок проверено по диску. Статус берётся из asset-registry.json (слои) и clip-manifest (клипы) как есть и не повышается."
      />
      <Card size="small" title="Слои героя H2 / H2LD / H3LD / Rig / H2Anim">
        {standard.length ? table(standard) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="слоёв не найдено" />}
        {absent.length ? (
          <Text type="secondary" style={{ fontSize: 12 }}>
            Не найдено ни в UE, ни в реестре, ни в документах: {absent.join(', ')}
          </Text>
        ) : null}
      </Card>
      {other.length ? <Card size="small" title={`Другие папки героя в UE (${other.length})`}>{table(other)}</Card> : null}
    </Space>
  );
};

/** Hero × UE layer matrix for the pipeline overview. */
export const UeMatrix: React.FC<{ characters: AssetPage[] }> = ({ characters }) => {
  const ui = useArtHubUi();
  const heroes = characters.filter((c) => c.ueLayers);
  if (!heroes.length) return null;
  const keys = ['H2', 'H2LD', 'H3LD', 'Rig', 'H2Anim'];
  return (
    <Card size="small" title="Герои: статус по свежему слою и UE-слои" data-testid="art-hub-ue-matrix">
      <Table<AssetPage>
        size="small"
        rowKey="id"
        pagination={false}
        dataSource={heroes}
        scroll={{ x: 980 }}
        columns={[
          {
            title: 'Герой',
            key: 'n',
            render: (_, p) => (
              <Button type="link" size="small" style={{ padding: 0 }} onClick={() => ui.openPage(p.id, 'ue')}>
                {p.shortName}
              </Button>
            ),
          },
          {
            title: 'Свежий слой реестра',
            key: 'latest',
            width: 220,
            render: (_, p) =>
              p.latestLayer ? (
                <Tooltip title={p.latestLayer.layer}>
                  <Space direction="vertical" size={0}>
                    <StatusTag status={p.latestLayer.status} />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {p.latestLayer.date ?? 'без даты'} · запись: {p.status ?? '—'}
                    </Text>
                  </Space>
                </Tooltip>
              ) : (
                <StatusTag status={p.status} />
              ),
          },
          ...keys.map((k) => ({
            title: k,
            key: k,
            render: (_: unknown, p: AssetPage) => {
              const l = p.ueLayers?.layers.find((x) => x.key === k);
              if (!l || !hasEvidence(l)) return <Text type="secondary">—</Text>;
              return (
                <Space direction="vertical" size={2}>
                  {l.onDisk ? <Tag color="success">в UE · {l.uassetCount ?? 0}</Tag> : l.onDisk === false ? <Tag>нет папки</Tag> : null}
                  <LayerStatus l={l} compact />
                </Space>
              );
            },
          })),
        ]}
      />
    </Card>
  );
};
