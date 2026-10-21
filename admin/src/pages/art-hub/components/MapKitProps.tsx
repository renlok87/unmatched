/**
 * Props of a map kit: stage/role/priority tags and the filterable props table.
 *
 * Usage (comments only, the section is wired in ArtHubPage):
 *   <MapKitPropsTable map={mapKitView} />
 */
import React, { useMemo, useState } from 'react';
import { Empty, Image, Input, Select, Space, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { FileRef, MapKitPropView, MapKitView } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { formatNumber } from '../format';
import { FileActions } from './common';

const { Text } = Typography;

/** Game height = real height × this (same factor as in the builder; MK-03). */
export const GAME_HEIGHT_FACTOR = 0.3;

// ------------------------------------------------------------------ vocabularies (display only)

/** Stage vocabulary of status.json in pipeline order. Labels and hints are display only; the stage itself is verbatim. */
export const MAP_KIT_STAGE: Record<string, { label: string; color: string; hint: string }> = {
  listed: { label: 'в списке', color: 'default', hint: 'пропс записан в props.json, видов для Tripo ещё нет' },
  views: { label: 'виды готовы', color: 'blue', hint: 'виды для слотов Tripo (front + left или front + back) готовы, модель ещё не запрошена' },
  tripo: { label: 'в Tripo', color: 'cyan', hint: 'модель сгенерирована в Tripo (GLB), в Blender ещё не собрана' },
  built: { label: 'собран', color: 'gold', hint: 'собран в Blender (FBX, число треугольников), приёмки ещё нет' },
  accepted: { label: 'принят', color: 'green', hint: 'прошёл приёмку' },
  ue: { label: 'в UE', color: 'purple', hint: 'импортирован в Unreal' },
  rework: { label: 'доработка', color: 'orange', hint: 'возвращён на доработку после приёмки' },
  rejected: { label: 'отклонён', color: 'red', hint: 'отклонён, в набор не идёт' },
};
export const MAP_KIT_STAGE_ORDER = Object.keys(MAP_KIT_STAGE);

const ROLE: Record<string, { label: string; color: string }> = {
  hero: { label: 'главный', color: 'gold' },
  animated: { label: 'анимированный', color: 'purple' },
  dressing: { label: 'декор', color: 'default' },
  backdrop: { label: 'задник', color: 'blue' },
};
export const roleLabel = (r: string) => ROLE[r]?.label ?? r;

const PRIORITY_COLOR: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'default' };
const SYMMETRY_LABEL: Record<string, string> = { axial: 'осевая', asymmetric: 'асимметричная' };

export const MapKitStageTag: React.FC<{ stage: string; count?: number; active?: boolean; onClick?: () => void }> = ({ stage, count, active, onClick }) => {
  const s = MAP_KIT_STAGE[stage];
  return (
    <Tooltip title={s ? `${s.label}: ${s.hint}` : `стадия «${stage}» вне словаря — показана как есть`}>
      <Tag
        color={s?.color ?? 'default'}
        onClick={onClick}
        style={{ cursor: onClick ? 'pointer' : undefined, borderStyle: s ? undefined : 'dashed', outline: active ? '2px solid #1677ff' : undefined }}
      >
        {s?.label ?? stage}
        {count !== undefined ? ` · ${count}` : ''}
      </Tag>
    </Tooltip>
  );
};

export const PriorityTag: React.FC<{ priority: string }> = ({ priority }) => <Tag color={PRIORITY_COLOR[priority] ?? 'default'}>{priority}</Tag>;

export const RoleTag: React.FC<{ role: string }> = ({ role }) => (
  <Tooltip title={role}>
    <Tag color={ROLE[role]?.color ?? 'default'}>{roleLabel(role)}</Tag>
  </Tooltip>
);

// ------------------------------------------------------------------ formatting

const dim = (n: number) => n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });

/** 1 пропс, 2 пропса, 5 пропсов */
const propsWord = (n: number) => {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return 'пропс';
  return m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? 'пропса' : 'пропсов';
};

/** `w×d×h м` of a real size in metres. */
export const formatSizeM = (s?: number[]) => (s && s.length === 3 ? `${s.map(dim).join('×')} м` : '—');

/** The thumbnail of a prop: the render of the built prop, else the front view. */
export function propThumb(p: MapKitPropView): FileRef | undefined {
  const f = [p.preview, p.views.front].find((r) => r && r.servable && r.kind === 'image');
  return f;
}

// ------------------------------------------------------------------ table

const rank = (order: string[], v: string) => {
  const i = order.indexOf(v);
  return i < 0 ? order.length : i;
};

const Dash = () => <Text type="secondary">—</Text>;

const SummaryCount: React.FC<{ items: { label: string; count: number }[] }> = ({ items }) => (
  <Text style={{ fontSize: 12 }}>{items.length ? items.map((i) => `${i.label} ${i.count}`).join(' · ') : '—'}</Text>
);

export const MapKitPropsTable: React.FC<{ map: MapKitView }> = ({ map }) => {
  const [priority, setPriority] = useState<string[]>([]);
  const [stage, setStage] = useState<string[]>([]);
  const [role, setRole] = useState<string[]>([]);
  const [query, setQuery] = useState('');

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return map.props.filter(
      (p) =>
        (!priority.length || priority.includes(p.priority)) &&
        (!stage.length || stage.includes(p.stage)) &&
        (!role.length || role.includes(p.role)) &&
        (!q || [p.key, p.nameRu, p.nameEn, p.zone, p.material].some((s) => s?.toLowerCase().includes(q))),
    );
  }, [map.props, priority, stage, role, query]);

  const columns: ColumnsType<MapKitPropView> = [
    {
      title: 'Превью',
      key: 'preview',
      width: 80,
      render: (_, p) => {
        const t = propThumb(p);
        return t ? (
          <Image src={fileUrl(t)} width={56} height={56} loading="lazy" style={{ objectFit: 'contain', borderRadius: 4, background: '#f5f5f5' }} alt={p.nameRu} />
        ) : (
          <Dash />
        );
      },
    },
    {
      title: 'Имя',
      key: 'name',
      width: 200,
      sorter: (a, b) => a.nameRu.localeCompare(b.nameRu, 'ru'),
      render: (_, p) => (
        <div>
          <Text strong>{p.nameRu}</Text>
          {p.nameEn ? (
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>{p.nameEn}</Text>
            </div>
          ) : null}
          <Text type="secondary" code copyable={{ text: p.key }} style={{ fontSize: 11 }}>
            {p.key}
          </Text>
        </div>
      ),
    },
    {
      title: 'Описание',
      key: 'desc',
      width: 260,
      render: (_, p) =>
        p.descRu || p.descEn ? (
          <Tooltip title={p.descEn ? <span style={{ fontSize: 12 }}>{p.descEn}</span> : undefined} placement="topLeft">
            <Text style={{ fontSize: 12 }}>{p.descRu ?? p.descEn}</Text>
          </Tooltip>
        ) : (
          <Dash />
        ),
    },
    {
      title: 'Роль',
      key: 'role',
      width: 120,
      sorter: (a, b) => a.role.localeCompare(b.role),
      render: (_, p) => <RoleTag role={p.role} />,
    },
    { title: 'Зона', dataIndex: 'zone', key: 'zone', width: 150, render: (v?: string) => (v ? <Text style={{ fontSize: 12 }}>{v}</Text> : <Dash />) },
    {
      title: 'Размер',
      key: 'size',
      width: 150,
      sorter: (a, b) => (a.sizeM?.[2] ?? 0) - (b.sizeM?.[2] ?? 0),
      render: (_, p) =>
        p.sizeM ? (
          <div>
            <Text>{formatSizeM(p.sizeM)}</Text>
            <div>
              <Tooltip title={`Высота в игре = реальная × ${GAME_HEIGHT_FACTOR}${map.scale ? ` (${map.scale})` : ''}. Деревья и крупные постройки могут сжиматься сильнее (MK-03).`}>
                <Text type="secondary" style={{ fontSize: 11 }}>в игре ≈ {dim(p.gameHeightM ?? p.sizeM[2]! * GAME_HEIGHT_FACTOR)} м</Text>
              </Tooltip>
            </div>
          </div>
        ) : (
          <Dash />
        ),
    },
    { title: 'Материал', dataIndex: 'material', key: 'material', width: 150, render: (v?: string) => (v ? <Text style={{ fontSize: 12 }}>{v}</Text> : <Dash />) },
    {
      title: 'Приор.',
      key: 'priority',
      width: 80,
      sorter: (a, b) => rank(['P0', 'P1', 'P2'], a.priority) - rank(['P0', 'P1', 'P2'], b.priority),
      render: (_, p) => <PriorityTag priority={p.priority} />,
    },
    {
      title: 'Симметрия → слоты Tripo',
      key: 'symmetry',
      width: 170,
      render: (_, p) => {
        const views = (['front', 'side', 'sheet'] as const).filter((k) => p.views[k]);
        const mismatch = p.views.heightMismatchPct;
        return (
          <div>
            <Text style={{ fontSize: 12 }}>{p.symmetry ? SYMMETRY_LABEL[p.symmetry] ?? p.symmetry : '—'}</Text>
            <div>
              {p.slots.length ? (
                <Space size={2} wrap>
                  {p.slots.map((s) => (
                    <Tag key={s} style={{ marginInlineEnd: 0 }}>{s}</Tag>
                  ))}
                </Space>
              ) : (
                <Dash />
              )}
            </div>
            {views.length ? (
              <Text type="secondary" style={{ fontSize: 11 }}>
                виды: {views.join(', ')}
                {p.views.slot ? ` · side → ${p.views.slot}` : ''}
              </Text>
            ) : null}
            {mismatch ? (
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>разница высот видов {dim(mismatch)} %</Text>
              </div>
            ) : null}
          </div>
        );
      },
    },
    {
      title: 'Стадия',
      key: 'stage',
      width: 150,
      sorter: (a, b) => rank(MAP_KIT_STAGE_ORDER, a.stage) - rank(MAP_KIT_STAGE_ORDER, b.stage),
      render: (_, p) => (
        <div>
          <MapKitStageTag stage={p.stage} />
          {p.note ? (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>{p.note}</Text>
            </div>
          ) : null}
        </div>
      ),
    },
    {
      title: 'Треугольники',
      key: 'tris',
      width: 140,
      render: (_, p) => {
        const tris = p.build?.tris;
        const over = tris !== undefined && p.trisMax !== undefined && tris > p.trisMax;
        return (
          <div>
            <Text type={over ? 'danger' : undefined}>
              {tris !== undefined ? formatNumber(tris) : '—'} / {p.trisMax !== undefined ? formatNumber(p.trisMax) : '—'}
            </Text>
            {p.build?.fbx ? <FileActions file={p.build.fbx} title={p.nameRu} /> : null}
            {p.build?.report ? <FileActions file={p.build.report} title="отчёт сборки" /> : null}
          </div>
        );
      },
    },
    {
      title: 'Tripo',
      key: 'tripo',
      width: 150,
      sorter: (a, b) => (a.tripo?.credits ?? 0) - (b.tripo?.credits ?? 0),
      render: (_, p) =>
        p.tripo ? (
          <Space direction="vertical" size={0}>
            {p.tripo.taskId ? (
              <Tooltip title={`задача Tripo ${p.tripo.taskId}`}>
                <Text code copyable={{ text: p.tripo.taskId }} style={{ fontSize: 11 }}>
                  {p.tripo.taskId.slice(0, 8)}
                </Text>
              </Tooltip>
            ) : null}
            {p.tripo.credits !== undefined ? <Text>{formatNumber(p.tripo.credits)} кр.</Text> : null}
            {p.tripo.route ? <Text type="secondary" style={{ fontSize: 11 }}>{p.tripo.route}</Text> : null}
            {p.tripo.ops.map((o, i) => (
              <Text key={`${o.op}-${i}`} type="secondary" style={{ fontSize: 11 }}>
                {o.op}
                {o.status ? ` ${o.status}` : ''}
                {o.quoted !== undefined ? ` · ${formatNumber(o.quoted)}` : ''}
              </Text>
            ))}
            {p.tripo.run ? <Text type="secondary" style={{ fontSize: 11, wordBreak: 'break-all' }}>{p.tripo.run}</Text> : null}
            {p.tripo.glb ? <FileActions file={p.tripo.glb} title={p.nameRu} /> : null}
          </Space>
        ) : (
          <Dash />
        ),
    },
    {
      title: 'Приёмка',
      key: 'acceptance',
      width: 150,
      render: (_, p) =>
        p.acceptance ? (
          <Space direction="vertical" size={0}>
            {p.acceptance.score !== undefined ? <Text strong>{p.acceptance.score}</Text> : null}
            {p.acceptance.verdict ? <Tag style={{ marginInlineEnd: 0, whiteSpace: 'normal' }}>{p.acceptance.verdict}</Tag> : null}
            {p.acceptance.card ? <FileActions file={p.acceptance.card} title="карточка приёмки" /> : null}
          </Space>
        ) : (
          <Dash />
        ),
    },
  ];

  const sum = (pick: (p: MapKitPropView) => number | undefined) => rows.reduce((n, p) => n + (pick(p) ?? 0), 0);
  const tally = (pick: (p: MapKitPropView) => string, order: string[], label: (k: string) => string) => {
    const m = new Map<string, number>();
    for (const p of rows) m.set(pick(p), (m.get(pick(p)) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => rank(order, a[0]) - rank(order, b[0])).map(([k, count]) => ({ label: label(k), count }));
  };

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }} data-testid={`art-hub-map-props-${map.id}`}>
      <Space wrap size={[8, 8]}>
        <Input.Search
          allowClear
          placeholder="имя, ключ, зона, материал"
          style={{ width: 240 }}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Поиск по пропсам"
        />
        <Select
          mode="multiple"
          allowClear
          placeholder="Приоритет"
          style={{ minWidth: 150 }}
          value={priority}
          onChange={setPriority}
          maxTagCount="responsive"
          options={map.counts.byPriority.map((c) => ({ value: c.priority, label: `${c.priority} · ${c.count}` }))}
        />
        <Select
          mode="multiple"
          allowClear
          placeholder="Стадия"
          style={{ minWidth: 190 }}
          value={stage}
          onChange={setStage}
          maxTagCount="responsive"
          options={map.counts.byStage.map((c) => ({ value: c.stage, label: `${MAP_KIT_STAGE[c.stage]?.label ?? c.stage} · ${c.count}` }))}
        />
        <Select
          mode="multiple"
          allowClear
          placeholder="Роль"
          style={{ minWidth: 190 }}
          value={role}
          onChange={setRole}
          maxTagCount="responsive"
          options={map.counts.byRole.map((c) => ({ value: c.role, label: `${roleLabel(c.role)} · ${c.count}` }))}
        />
        <Text type="secondary">
          показано {rows.length} из {map.props.length}
        </Text>
      </Space>
      <Table<MapKitPropView>
        size="small"
        rowKey="key"
        columns={columns}
        dataSource={rows}
        scroll={{ x: 1950 }}
        pagination={rows.length > 50 ? { pageSize: 50, size: 'small', showSizeChanger: false } : false}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={map.props.length ? 'нет пропсов под фильтры' : 'список пропсов пуст'} /> }}
        summary={() =>
          rows.length ? (
            <Table.Summary fixed>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={3}>
                  <Text strong>Итого: {rows.length} {propsWord(rows.length)}</Text>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={3} colSpan={1}>
                  <SummaryCount items={tally((p) => p.role, ['hero', 'animated', 'dressing', 'backdrop'], roleLabel)} />
                </Table.Summary.Cell>
                <Table.Summary.Cell index={4} colSpan={3} />
                <Table.Summary.Cell index={7} colSpan={1}>
                  <SummaryCount items={tally((p) => p.priority, ['P0', 'P1', 'P2'], (k) => k)} />
                </Table.Summary.Cell>
                <Table.Summary.Cell index={8} colSpan={1} />
                <Table.Summary.Cell index={9} colSpan={1}>
                  <SummaryCount items={tally((p) => p.stage, MAP_KIT_STAGE_ORDER, (k) => MAP_KIT_STAGE[k]?.label ?? k)} />
                </Table.Summary.Cell>
                <Table.Summary.Cell index={10} colSpan={1}>
                  <Text style={{ fontSize: 12 }}>
                    лимит Σ {formatNumber(sum((p) => p.trisMax))}
                    {rows.some((p) => p.build?.tris !== undefined) ? `, собрано ${formatNumber(sum((p) => p.build?.tris))}` : ''}
                  </Text>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={11} colSpan={1}>
                  <Text strong>{formatNumber(sum((p) => p.tripo?.credits))} кр.</Text>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={12} colSpan={1}>
                  <Text style={{ fontSize: 12 }}>оценок {rows.filter((p) => p.acceptance?.score !== undefined).length}</Text>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            </Table.Summary>
          ) : null
        }
      />
    </Space>
  );
};
