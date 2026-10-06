import React, { useMemo } from 'react';
import { Empty, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { AudioUnitView, CharacterAudioUnit } from '../../../../art-hub/types';
import { LongText } from './common';

const { Text } = Typography;

/** Registry status vocabulary of 03-sound-registry.csv (labels and hints are display only). */
export const AUDIO_STATUS: Record<string, { label: string; color: string; hint: string }> = {
  'in-game': { label: 'в игре', color: 'green', hint: 'ассет в UE и подключён к событию игры' },
  'in-bank': { label: 'в банке', color: 'gold', hint: 'ассет в UE, триггера нет — причина в заметке' },
  'done-source': { label: 'исходник готов', color: 'blue', hint: 'исходник готов (мотив: MIDI/WAV вне git), в игре звучит внутри других единиц' },
  template: { label: 'шаблон', color: 'default', hint: 'шаблон для будущих героев и карт; путь в UE не записан' },
  'none-by-design': { label: 'нет по замыслу', color: 'default', hint: 'звука нет намеренно — причина в заметке' },
};

const CATEGORY_LABEL: Record<string, string> = {
  vo: 'реплики',
  ui: 'интерфейс',
  combat: 'бой',
  fx: 'эффекты',
  sting: 'стинги',
  ambience: 'окружение',
  cards: 'карты',
  music: 'музыка',
  death: 'гибель',
  board: 'поле',
  motif: 'мотивы',
};

export const categoryLabel = (c: string) => CATEGORY_LABEL[c] ?? c;

/** Registry status, verbatim, with the Russian meaning in the tooltip. */
export const AudioStatusTag: React.FC<{ status: string; count?: number; active?: boolean; onClick?: () => void }> = ({ status, count, active, onClick }) => {
  const s = AUDIO_STATUS[status];
  return (
    <Tooltip title={s ? `${s.label}: ${s.hint}` : 'статус вне словаря реестра — показан как есть'}>
      <Tag
        color={s?.color ?? 'default'}
        onClick={onClick}
        style={{ cursor: onClick ? 'pointer' : undefined, borderStyle: s ? undefined : 'dashed', outline: active ? '2px solid #1677ff' : undefined }}
      >
        {status}
        {count !== undefined ? ` · ${count}` : ''}
      </Tag>
    </Tooltip>
  );
};

/** Number of SoundWaves in UE that match the unit's `file` path. */
export const UeAssetsTag: React.FC<{ unit: AudioUnitView }> = ({ unit }) => {
  if (unit.ueAssets === undefined) {
    return (
      <Tooltip title={unit.file ? `не путь UE: ${unit.file}` : 'путь в UE не записан'}>
        <Text type="secondary">—</Text>
      </Tooltip>
    );
  }
  return (
    <Tooltip title={`${unit.file ?? ''} — SoundWave в unreal/Unmatched/Content (только подсчёт)`}>
      <Tag color={unit.ueAssets === 0 ? 'error' : 'default'}>{unit.ueAssets === 0 ? 'нет в UE' : unit.ueAssets}</Tag>
    </Tooltip>
  );
};

export type AudioFilters = { status: string[] | null; category: string[] | null };

/** Registry units with status/category filters (used on the overview and on a character tab). */
export const AudioUnitsTable: React.FC<{
  units: (AudioUnitView | CharacterAudioUnit)[];
  filters?: AudioFilters;
  onFilters?: (f: AudioFilters) => void;
  showVia?: boolean;
  pageSize?: number;
}> = ({ units, filters, onFilters, showVia, pageSize = 50 }) => {
  const statuses = useMemo(() => [...new Set(units.map((u) => u.status))], [units]);
  const categories = useMemo(() => [...new Set(units.map((u) => u.category))].sort(), [units]);
  const columns: ColumnsType<AudioUnitView | CharacterAudioUnit> = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 210,
      render: (v: string, u) => (
        <div>
          <Tag color="geekblue" style={{ marginInlineEnd: 0 }}>
            {v}
          </Tag>
          {u.owner ? (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>
                владелец: {u.owner}
              </Text>
            </div>
          ) : null}
        </div>
      ),
    },
    {
      title: 'Категория',
      dataIndex: 'category',
      width: 110,
      filters: categories.map((c) => ({ text: `${categoryLabel(c)} (${c})`, value: c })),
      filteredValue: filters ? filters.category : undefined,
      onFilter: (v, u) => u.category === v,
      render: (v: string) => (
        <Tooltip title={v}>
          <Tag>{categoryLabel(v)}</Tag>
        </Tooltip>
      ),
    },
    {
      title: 'Название',
      key: 'name',
      render: (_, u) => (
        <div>
          <Text>{u.nameRu ?? '—'}</Text>
          {u.event || u.trigger ? (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }} ellipsis={{ tooltip: [u.event, u.trigger].filter(Boolean).join(' · ') }}>
              {[u.event, u.trigger].filter(Boolean).join(' · ')}
            </Text>
          ) : null}
        </div>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      width: 140,
      filters: statuses.map((s) => ({ text: AUDIO_STATUS[s] ? `${s} — ${AUDIO_STATUS[s]!.label}` : s, value: s })),
      filteredValue: filters ? filters.status : undefined,
      onFilter: (v, u) => u.status === v,
      render: (v: string) => <AudioStatusTag status={v} />,
    },
    { title: 'UE', key: 'ue', width: 80, render: (_, u) => <UeAssetsTag unit={u} /> },
    ...(showVia
      ? [
          {
            title: 'Связь',
            key: 'via',
            width: 120,
            render: (_: unknown, u: AudioUnitView | CharacterAudioUnit) => (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {'via' in u ? u.via : '—'}
              </Text>
            ),
          },
        ]
      : []),
    { title: 'Заметка', dataIndex: 'notes', width: 320, render: (v?: string) => <LongText text={v} rows={2} /> },
  ];
  return (
    <Table<AudioUnitView | CharacterAudioUnit>
      size="small"
      rowKey="id"
      dataSource={units}
      columns={columns}
      onChange={(_, f) =>
        onFilters?.({ status: (f.status as string[] | null | undefined) ?? null, category: (f.category as string[] | null | undefined) ?? null })
      }
      pagination={units.length > pageSize ? { pageSize, size: 'small', showSizeChanger: false } : false}
      tableLayout="fixed"
      scroll={{ x: showVia ? 1220 : 1100 }}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="единиц нет" /> }}
    />
  );
};
