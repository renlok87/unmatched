import React from 'react';
import { Alert, Card, Descriptions, Empty, Image, Space, Table, Tag, Tooltip, Typography } from 'antd';
import type { MaterialClassView, MaterialLibraryView, MaterialSetView } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { DocList } from '../components/DocList';
import { FileActions, Gallery, LongText } from '../components/common';

const { Text } = Typography;

/** Linear sRGB → CSS rgb() (display only). */
export function linearToCss(rgb: number[]): string {
  const enc = (c: number) => {
    const v = Math.min(1, Math.max(0, c));
    const s = v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(v, 1 / 2.4) - 0.055;
    return Math.round(s * 255);
  };
  return `rgb(${enc(rgb[0] ?? 0)}, ${enc(rgb[1] ?? 0)}, ${enc(rgb[2] ?? 0)})`;
}

const Swatch: React.FC<{ rgb?: number[] }> = ({ rgb }) =>
  rgb ? (
    <Tooltip title={`typicalLinear ${rgb.map((v) => v.toFixed(3)).join(', ')}`}>
      <div style={{ width: 28, height: 28, borderRadius: 4, border: '1px solid #d9d9d9', background: linearToCss(rgb) }} />
    </Tooltip>
  ) : (
    <Text type="secondary">—</Text>
  );

export const MaterialsSection: React.FC<{ materials?: MaterialLibraryView }> = ({ materials: m }) => {
  if (!m) return <Empty />;
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid="art-hub-materials">
      <Card size="small" title="Библиотека материалов UM">
        <Descriptions size="small" column={{ xs: 1, md: 2, xl: 3 }}>
          <Descriptions.Item label="Пресеты">
            {m.presets ? (
              <Space size={2} wrap>
                <Text code style={{ fontSize: 11 }}>{m.presets.file.path}</Text>
                <FileActions file={m.presets.file} />
              </Space>
            ) : (
              <Tag color="error">нет файла</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Версия / дата">{m.presets ? `${m.presets.version ?? '—'} · ${m.presets.date ?? '—'}` : '—'}</Descriptions.Item>
          <Descriptions.Item label="Статус пресетов">{m.presets?.status ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="Источники">
            {m.sources ? (
              <Space size={2} wrap>
                <Text code style={{ fontSize: 11 }}>{m.sources.file.path}</Text>
                <FileActions file={m.sources.file} />
              </Space>
            ) : (
              <Tag color="error">нет файла</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Лицензии">
            {m.sources ? (
              m.sources.allCC0 ? (
                <Tag color="green">все {m.sets.length} наборов — CC0</Tag>
              ) : (
                <Tag color="red">есть наборы без CC0</Tag>
              )
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Классы">
            {m.classes.filter((c) => !c.extension).length} основных + {m.classes.filter((c) => c.extension).length} расширения
          </Descriptions.Item>
        </Descriptions>
        {m.sources?.licenseNote ? <Alert style={{ marginTop: 8 }} type="success" showIcon message="Лицензия" description={<LongText text={m.sources.licenseNote} rows={2} />} /> : null}
      </Card>

      <Card size="small" title="Документы библиотеки">
        <DocList docs={m.docs} />
      </Card>

      <Card size="small" title={`Классы материалов (${m.classes.length})`}>
        <Table<MaterialClassView>
          size="small"
          rowKey="id"
          pagination={false}
          dataSource={m.classes}
          scroll={{ x: 1000 }}
          columns={[
            { title: '#', dataIndex: 'index', width: 50, render: (v?: number) => v ?? '—' },
            { title: '', key: 'sw', width: 44, render: (_, c) => <Swatch rgb={c.baseColorLinear} /> },
            {
              title: 'Класс',
              key: 'id',
              render: (_, c) => (
                <div>
                  <Text strong>{c.id}</Text> {c.extension ? <Tag color="purple">расширение</Tag> : null}
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>{c.nameRu ?? '—'}</Text>
                  </div>
                </div>
              ),
            },
            { title: 'Семейство', dataIndex: 'family', width: 110, render: (v?: string) => (v ? <Tag>{v}</Tag> : '—') },
            { title: 'Metallic', dataIndex: 'metallic', width: 80, render: (v?: number) => v ?? '—' },
            { title: 'Roughness', dataIndex: 'roughness', width: 95, render: (v?: number) => v ?? '—' },
            { title: 'Shading', dataIndex: 'shadingModel', width: 100, render: (v?: string) => v ?? '—' },
            {
              title: 'Источник деталей',
              key: 'src',
              render: (_, c) =>
                c.sets.length ? (
                  <Space size={2} wrap>
                    {c.sets.map((s) => (
                      <Tag key={s} color="green">{s} · CC0</Tag>
                    ))}
                  </Space>
                ) : c.procedural ? (
                  <Tag color="blue">{c.procedural}</Tag>
                ) : (
                  <Text type="secondary">—</Text>
                ),
            },
            {
              title: 'Тайлы',
              key: 'tiles',
              width: 120,
              render: (_, c) =>
                c.tiles.filter((t) => t.servable).length ? (
                  <Image.PreviewGroup>
                    <Space size={4}>
                      {c.tiles
                        .filter((t) => t.servable)
                        .slice(0, 2)
                        .map((t) => (
                          <Image key={t.path} src={fileUrl(t)} width={44} height={44} style={{ objectFit: 'cover', borderRadius: 4 }} alt={t.path} loading="lazy" />
                        ))}
                    </Space>
                  </Image.PreviewGroup>
                ) : (
                  <Text type="secondary">—</Text>
                ),
            },
          ]}
        />
      </Card>

      <Card size="small" title={`CC0-наборы ambientCG (${m.sets.length})`}>
        <Table<MaterialSetView>
          size="small"
          rowKey="id"
          pagination={false}
          dataSource={m.sets}
          scroll={{ x: 900 }}
          columns={[
            { title: 'Набор', dataIndex: 'id', width: 110, render: (v: string) => <Text strong>{v}</Text> },
            {
              title: 'Статус',
              dataIndex: 'status',
              width: 130,
              filters: [...new Set(m.sets.map((s) => s.status ?? '—'))].map((s) => ({ text: s, value: s })),
              onFilter: (v, s) => (s.status ?? '—') === v,
              render: (v?: string) => <Tag color={v === 'используется' ? 'blue' : 'default'}>{v ?? '—'}</Tag>,
            },
            { title: 'Класс', dataIndex: 'class', width: 130, render: (v?: string | null) => v ?? '—' },
            { title: 'Лицензия', key: 'lic', width: 200, render: (_, s) => <Tag color={s.cc0 ? 'green' : 'red'}>{s.license ?? 'нет'}</Tag> },
            { title: 'Почему', dataIndex: 'reason', render: (v?: string) => <LongText text={v} rows={2} /> },
            {
              title: 'Страница',
              dataIndex: 'page',
              width: 90,
              render: (v?: string) =>
                v && /^https:\/\//i.test(v) ? (
                  <a href={v} target="_blank" rel="noreferrer noopener">
                    ambientCG
                  </a>
                ) : (
                  '—'
                ),
            },
          ]}
        />
        {m.procedural.length ? (
          <div style={{ marginTop: 12 }}>
            <Text strong>Процедурные классы (CC0-набора нет)</Text>
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
              {m.procedural.map((p) => (
                <li key={p.class}>
                  <Text code>{p.class}</Text> — {p.generator ?? '—'}. <Text type="secondary" style={{ fontSize: 12 }}>{p.reason}</Text>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      {m.tilesSheet ? (
        <Card size="small" title="Контактный лист тайлов деталей">
          <Gallery images={[m.tilesSheet]} size={520} fit="contain" aspect={0.6} />
        </Card>
      ) : null}

      <Card size="small" title={`Доказательства мастера (${m.evidenceTotal} изображений)`}>
        <Space wrap size={[4, 4]} style={{ marginBottom: 8 }}>
          {m.evidenceGroups.map((g) => (
            <Tag key={g.group}>
              {g.group} · {g.count}
            </Tag>
          ))}
        </Space>
        <Gallery images={m.evidenceImages} size={220} fit="contain" aspect={0.6} emptyText="кадров нет" />
      </Card>
    </Space>
  );
};
