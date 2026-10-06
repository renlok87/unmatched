import React, { useState } from 'react';
import { Alert, Card, Col, Collapse, Descriptions, Empty, Row, Space, Statistic, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { AudioMixRow, AudioOverview, AudioVoFighter } from '../../../../art-hub/types';
import { AUDIO_STATUS, AudioStatusTag, AudioUnitsTable, categoryLabel, type AudioFilters } from '../components/AudioUnits';
import { DocList } from '../components/DocList';
import { FileActions, FileTable, Gallery } from '../components/common';
import { formatNumber } from '../format';
import { LedgerTable } from './SoundsCreditsSections';

const { Text } = Typography;

const lufs = (v?: number) => (v === undefined ? '—' : v.toFixed(1));

const OkTag: React.FC<{ ok?: boolean; label: string }> = ({ ok, label }) =>
  ok === undefined ? <Tag>{label}: —</Tag> : <Tag color={ok ? 'green' : 'red'}>{`${label} ${ok ? '✓' : '✗'}`}</Tag>;

export const AudioSection: React.FC<{ audio?: AudioOverview }> = ({ audio: a }) => {
  const [filters, setFilters] = useState<AudioFilters>({ status: null, category: null });
  if (!a) return <Empty />;
  const reg = a.registry;
  const latest = a.mix.latest;
  const toggle = (key: keyof AudioFilters, value: string) =>
    setFilters((f) => ({ ...f, [key]: f[key]?.length === 1 && f[key]![0] === value ? null : [value] }));

  const mixColumns: ColumnsType<AudioMixRow> = [
    { title: 'Карта', dataIndex: 'map', width: 120, render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: 'Клиент', dataIndex: 'client', width: 90 },
    {
      title: 'I, LUFS',
      dataIndex: 'I',
      width: 90,
      render: (v: number | undefined, r) => <Text type={r.okI === false ? 'danger' : undefined}>{lufs(v)}</Text>,
    },
    {
      title: 'TP, dBTP',
      dataIndex: 'TP',
      width: 90,
      render: (v: number | undefined, r) => <Text type={r.okTP === false ? 'danger' : undefined}>{lufs(v)}</Text>,
    },
    { title: 'S max', dataIndex: 'sMax', width: 80, render: (v?: number) => lufs(v) },
    { title: 'LRA', dataIndex: 'LRA', width: 70, render: (v?: number) => lufs(v) },
    { title: 'Длит., с', dataIndex: 'seconds', width: 80, render: (v?: number) => lufs(v) },
    {
      title: 'Норма',
      key: 'ok',
      width: 150,
      render: (_, r) =>
        r.error ? (
          <Tag color="warning">файл {r.error}</Tag>
        ) : (
          <Space size={2}>
            <OkTag ok={r.okI} label="I" />
            <OkTag ok={r.okTP} label="TP" />
          </Space>
        ),
    },
    { title: '', key: 'f', width: 120, render: (_, r) => <FileActions file={r.file} /> },
  ];

  const voColumns: ColumnsType<AudioVoFighter> = [
    { title: 'Боец', dataIndex: 'fighter', render: (v: string) => <Tag color="geekblue">{v}</Tag> },
    { title: 'Реплик', dataIndex: 'lines', width: 100 },
    { title: 'С текстом', key: 'text', width: 110, render: (_, f) => f.lines - f.wordless },
    { title: 'Без слов', dataIndex: 'wordless', width: 100 },
  ];

  const images = latest?.files.filter((f) => f.kind === 'image') ?? [];
  const others = latest?.files.filter((f) => f.kind !== 'image') ?? [];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid="art-hub-audio">
      <Card size="small" title="Звук игры">
        <Descriptions size="small" column={{ xs: 1, md: 2, xl: 3 }}>
          <Descriptions.Item label="Реестр">
            <Space size={2} wrap>
              <Text code style={{ fontSize: 11 }}>{reg.file.path}</Text>
              {reg.file.exists ? <FileActions file={reg.file} /> : <Tag color="error">нет файла</Tag>}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="Единиц звука">{reg.units.length}</Descriptions.Item>
          <Descriptions.Item label="SoundWave в UE">
            {a.ue.found === null ? <Text type="secondary">проект UE не найден</Text> : a.ue.found ? a.ue.soundWaves : <Tag>нет папки {a.ue.contentRoot}</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="Реплики (04)">
            {a.vo.total} (без слов {a.vo.wordless})
          </Descriptions.Item>
          <Descriptions.Item label="Последний замер микса">{latest ? latest.date : '—'}</Descriptions.Item>
          <Descriptions.Item label={`Траты AUC-*, ${a.spends.unit}`}>{a.spends.entries.length ? formatNumber(a.spends.spent) : '—'}</Descriptions.Item>
        </Descriptions>
        {reg.error ? <Alert style={{ marginTop: 8 }} type="warning" showIcon message={`Реестр не разобран: ${reg.error}`} /> : null}
        {!reg.file.exists ? (
          <Alert
            style={{ marginTop: 8 }}
            type="info"
            showIcon
            message="Реестра звука нет"
            description={
              <span>
                Файла <Text code>{reg.file.path}</Text> нет — раздел заполнится сам, когда он появится.
              </span>
            }
          />
        ) : null}
      </Card>

      {reg.units.length ? (
        <Card size="small" title="Единицы реестра: статусы и категории">
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space wrap size={[4, 4]}>
              <Text type="secondary">Статус:</Text>
              {reg.byStatus.map((s) => (
                <AudioStatusTag key={s.status} status={s.status} count={s.count} active={filters.status?.includes(s.status)} onClick={() => toggle('status', s.status)} />
              ))}
            </Space>
            <Space wrap size={[4, 4]}>
              <Text type="secondary">Категория:</Text>
              {reg.byCategory.map((c) => (
                <Tooltip key={c.category} title={c.category}>
                  <Tag
                    onClick={() => toggle('category', c.category)}
                    style={{ cursor: 'pointer', outline: filters.category?.includes(c.category) ? '2px solid #1677ff' : undefined }}
                  >
                    {categoryLabel(c.category)} · {c.count}
                  </Tag>
                </Tooltip>
              ))}
            </Space>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
              {Object.entries(AUDIO_STATUS).map(([k, s]) => (
                <li key={k}>
                  <Text code style={{ fontSize: 11 }}>{k}</Text> — {s.hint}
                </li>
              ))}
            </ul>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Щелчок по метке фильтрует таблицу ниже. Статусы — как в реестре, хаб их не меняет.
            </Text>
            {reg.missingInUe.length ? (
              <Alert
                type="warning"
                showIcon
                message={`В UE не найден SoundWave для ${reg.missingInUe.length} единиц со статусом in-game / in-bank`}
                description={reg.missingInUe.join(', ')}
              />
            ) : a.ue.found ? (
              <Text type="success" style={{ fontSize: 12 }}>
                У всех единиц in-game / in-bank с путём /Game/ есть SoundWave в UE.
              </Text>
            ) : null}
          </Space>
        </Card>
      ) : null}

      {a.summary ? (
        <Card
          size="small"
          title="Итог производства (07, §0)"
          extra={<FileActions file={a.summary.file} />}
        >
          <Table
            size="small"
            pagination={false}
            rowKey={(r) => r.join('|')}
            dataSource={a.summary.rows.slice(1)}
            columns={(a.summary.rows[0] ?? []).map((h, i) => ({
              title: h,
              key: String(i),
              render: (_: unknown, r: string[]) => <Text style={{ fontSize: 12 }}>{r[i] ?? ''}</Text>,
            }))}
          />
        </Card>
      ) : null}

      <Card size="small" title={`Единицы реестра (${reg.units.length})`}>
        <AudioUnitsTable units={reg.units} filters={filters} onFilters={setFilters} />
      </Card>

      <Row gutter={16}>
        <Col xs={24} xl={12}>
          <Card
            size="small"
            title={`Реплики героев (04): ${a.vo.total}`}
            extra={<FileActions file={a.vo.script} title="реплики 04" />}
            style={{ height: '100%' }}
          >
            <Table<AudioVoFighter>
              size="small"
              rowKey="fighter"
              pagination={false}
              dataSource={a.vo.fighters}
              columns={voColumns}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={a.vo.script.exists ? 'реплик не найдено' : 'файла 04 нет'} /> }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Голоса и их выбор описаны текстом в <Text code style={{ fontSize: 11 }}>04-vo-script.md</Text> §1 и в журнале{' '}
              <Text code style={{ fontSize: 11 }}>07-production-log.md</Text> (§3, §8) — машиночитаемого списка голосов нет. Крики гарпий звучат в
              трёх высотах.
            </Text>
            {a.vo.log.exists ? (
              <Space size={4} style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Журнал 07:
                </Text>
                <FileActions file={a.vo.log} title="журнал производства" />
              </Space>
            ) : null}
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card size="small" title="SoundWave в UE по папкам" style={{ height: '100%' }}>
            {a.ue.byFolder.length ? (
              <Space wrap size={[4, 4]}>
                {a.ue.byFolder.map((f) => (
                  <Tag key={f.folder}>
                    {f.folder} · {f.count}
                  </Tag>
                ))}
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={a.ue.found === null ? 'проект UE не найден' : 'SoundWave не найдены'} />
            )}
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {a.ue.contentRoot}: только подсчёт имён (файлы unreal/ не отдаются).
              </Text>
            </div>
            {a.ue.unregistered.length ? (
              <Collapse
                size="small"
                ghost
                items={[
                  {
                    key: 'u',
                    label: (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        SoundWave без пути в колонке file реестра ({a.ue.unregistered.length}): шаблоны, голосовые слои эффектов
                      </Text>
                    ),
                    children: (
                      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11 }}>
                        {a.ue.unregistered.map((p) => (
                          <li key={p} style={{ wordBreak: 'break-all' }}>
                            {p.replace(`${a.ue.contentRoot}/`, '')}
                          </li>
                        ))}
                      </ul>
                    ),
                  },
                ]}
              />
            ) : null}
          </Card>
        </Col>
      </Row>

      <Card size="small" title={latest ? `Микс: последний замер ${latest.date}` : 'Микс: замеры громкости'}>
        {latest ? (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space wrap size={[8, 4]}>
              <Text>
                Цель: I {latest.targets?.I ?? '−20 ±2'} LUFS, TP ≤ {latest.targets?.TP_max ?? '−1'} dBTP
              </Text>
              {latest.targets?.S_peak_ref ? <Text type="secondary">S peak ref {latest.targets.S_peak_ref}</Text> : null}
              <Text type="secondary" copyable={{ text: latest.dir }} style={{ fontSize: 12 }}>
                {latest.dir}
              </Text>
            </Space>
            <Table<AudioMixRow>
              size="small"
              rowKey={(r) => r.file.path}
              pagination={false}
              dataSource={latest.rows}
              columns={mixColumns}
              scroll={{ x: 900 }}
            />
            {images.length ? <Gallery images={images} size={220} fit="contain" aspect={0.5625} /> : null}
            {others.length ? (
              <Collapse
                size="small"
                ghost
                items={[
                  {
                    key: 'f',
                    label: <Text type="secondary" style={{ fontSize: 12 }}>файлы замера ({others.length}): трассы, манифесты, шаги микса</Text>,
                    children: <FileTable files={others} pageSize={20} />,
                  },
                ]}
              />
            ) : null}
          </Space>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={`замеров *-mix.json в ${a.mix.evidenceRoot}/<дата>/ нет`}
          />
        )}
        {a.mix.folders.length > (latest ? 1 : 0) ? (
          <div style={{ marginTop: 12 }}>
            <Text strong>Папки доказательств</Text>
            <Table
              size="small"
              rowKey="dir"
              pagination={false}
              dataSource={a.mix.folders}
              columns={[
                { title: 'Дата', dataIndex: 'date', width: 120, render: (v: string) => <Tag>{v}</Tag> },
                { title: 'Файлов', dataIndex: 'fileCount', width: 90 },
                { title: 'Замеров микса', dataIndex: 'mixCount', width: 130, render: (v: number) => v || '—' },
                {
                  title: 'Путь',
                  dataIndex: 'dir',
                  render: (v: string) => (
                    <Text type="secondary" copyable style={{ fontSize: 12 }}>
                      {v}
                    </Text>
                  ),
                },
              ]}
            />
          </div>
        ) : null}
      </Card>

      <Card size="small" title={`Траты SYNTX на звук (записи AUC-*): ${a.spends.entries.length}`} extra={a.spends.ledger ? <FileActions file={a.spends.ledger} /> : null}>
        {a.spends.entries.length ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Row gutter={16}>
              <Col xs={24} md={8}>
                <Statistic title={`Списано, ${a.spends.unit}`} value={formatNumber(a.spends.spent)} />
              </Col>
              <Col xs={24} md={8}>
                <Statistic
                  title="Баланс до → после"
                  value={`${a.spends.balanceStart !== undefined ? formatNumber(a.spends.balanceStart) : '—'} → ${
                    a.spends.balanceEnd !== undefined ? formatNumber(a.spends.balanceEnd) : '—'
                  }`}
                />
              </Col>
              <Col xs={24} md={8}>
                <Statistic title="Возвраты" value={formatNumber(a.spends.refunds)} />
              </Col>
            </Row>
            <LedgerTable entries={a.spends.entries} pageSize={30} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Записи AUC-* отнесены к разделу «Звук» и не попадают в «не отнесённые» на странице состояния пайплайна.
            </Text>
          </Space>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="в журнале кредитов нет записей AUC-*" />
        )}
      </Card>

      <Card size="small" title={`Документы звука (${a.docs.length})`}>
        <DocList docs={a.docs} emptyText={`документов в ${a.root} нет`} />
        {a.tables.length ? (
          <div style={{ marginTop: 8 }}>
            <FileTable files={a.tables} />
          </div>
        ) : null}
      </Card>
    </Space>
  );
};
