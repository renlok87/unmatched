import React, { useMemo } from 'react';
import { Alert, Card, Col, Descriptions, Empty, Image, Row, Space, Table, Tag, Tree, Typography } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { AssetPage, BoneView, RigSection as Rig } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { FileActions, FileTable, LongText, StatusTag, TWO_COLUMNS } from '../components/common';
import { LayersTable } from './SummarySection';

const { Text } = Typography;

function boneTree(bones: BoneView[], weaponParent?: string | null): DataNode[] {
  const byParent = new Map<string | null, BoneView[]>();
  for (const b of bones) byParent.set(b.parent, [...(byParent.get(b.parent) ?? []), b]);
  const build = (parent: string | null): DataNode[] =>
    (byParent.get(parent) ?? []).map((b) => ({
      key: b.name,
      title: (
        <span>
          <Text code>{b.name}</Text>
          {b.role ? <Text type="secondary" style={{ fontSize: 12 }}> — {b.role}</Text> : null}
          {b.name === 'weapon' ? (
            <Tag style={{ marginLeft: 6 }} color={weaponParent === null ? 'default' : 'blue'}>
              {weaponParent === undefined ? 'родитель по контракту' : weaponParent === null ? 'у персонажа нет оружия' : `у персонажа: ${weaponParent}`}
            </Tag>
          ) : null}
        </span>
      ),
      children: build(b.name),
    }));
  return build(null);
}

const probeColor = (s: string) => (s === 'plausible' ? 'green' : s === 'wrong_region' ? 'red' : 'default');

export const RigSection: React.FC<{ page: AssetPage; rig: Rig }> = ({ page, rig }) => {
  const tree = useMemo(() => boneTree(rig.bones, rig.weaponParent), [rig.bones, rig.weaponParent]);
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        size="small"
        title="Контракт рига"
        extra={
          <Space>
            {rig.contract ? <FileActions file={rig.contract} /> : null}
            {rig.contractDoc ? <FileActions file={rig.contractDoc} /> : null}
          </Space>
        }
      >
        {rig.contract ? (
          <Descriptions size="small" column={TWO_COLUMNS} bordered>
            <Descriptions.Item label="Статус контракта">
              <StatusTag status={rig.contractStatus} />
            </Descriptions.Item>
            <Descriptions.Item label="Ревизия">{rig.revision ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Скелет">
              <Text code>{rig.skeletonKey ?? '—'}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Применяется к">{rig.appliesTo?.map((a) => <Tag key={a}>{a}</Tag>) ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Пояснение" span={2}>
              <LongText text={rig.contractStatusNote} rows={2} />
            </Descriptions.Item>
            {rig.armatureObject ? (
              <Descriptions.Item label="Объект арматуры (кость 0 в UE)" span={2}>
                <Space direction="vertical" size={2}>
                  <Space wrap>
                    <Text code>{rig.armatureObject.name}</Text>
                    <StatusTag status={rig.armatureObject.status} />
                    {rig.armatureObject.legacyNames?.map((n) => (
                      <Tag key={n}>legacy: {n}</Tag>
                    ))}
                  </Space>
                  <LongText text={rig.armatureObject.rule} rows={2} />
                </Space>
              </Descriptions.Item>
            ) : null}
          </Descriptions>
        ) : (
          <Empty description="rig-contract.json не найден" />
        )}
      </Card>

      <Row gutter={16}>
        <Col xs={24} xl={12}>
          <Card size="small" title={`Кости (${rig.bones.length})`}>
            {tree.length ? <Tree treeData={tree} defaultExpandAll selectable={false} /> : <Empty />}
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card size="small" title="Сокеты (UE)">
              <Table
                size="small"
                rowKey="name"
                pagination={false}
                dataSource={rig.sockets}
                columns={[
                  { title: 'Сокет', dataIndex: 'name', render: (v: string) => <Text code>{v}</Text> },
                  { title: 'Кость', dataIndex: 'bone' },
                  { title: 'Смещение', key: 'o', render: (_, s) => (s.offset?.length ? `(${s.offset.join(', ')})` : '—') },
                  { title: 'Заметка', dataIndex: 'note' },
                ]}
              />
            </Card>
            <Card size="small" title="Расширения контракта">
              <Space direction="vertical" style={{ width: '100%' }}>
                {rig.extensions.map((e) => (
                  <div key={e.key}>
                    <Space wrap>
                      <Text strong>{e.key}</Text>
                      <Tag>{e.status ?? '—'}</Tag>
                    </Space>
                    <LongText text={e.rule} rows={2} />
                  </div>
                ))}
              </Space>
            </Card>
            <Card size="small" title="Карты ретаргета">
              <Space direction="vertical" size={4}>
                {rig.retargetMaps.map((r) => (
                  <div key={r.key}>
                    <Text code>{r.key}</Text> <Text type="secondary" style={{ fontSize: 12 }}>{r.status}</Text>
                  </div>
                ))}
              </Space>
            </Card>
          </Space>
        </Col>
      </Row>

      <Card size="small" title="Root motion и оси">
        <Descriptions size="small" column={1} bordered>
          {Object.entries(rig.rootMotion ?? {}).map(([k, v]) => (
            <Descriptions.Item key={`rm-${k}`} label={`root_motion.${k}`}>
              <LongText text={v} rows={2} />
            </Descriptions.Item>
          ))}
          {Object.entries(rig.axes ?? {}).map(([k, v]) => (
            <Descriptions.Item key={`ax-${k}`} label={`axes.${k}`}>
              <LongText text={v} rows={2} />
            </Descriptions.Item>
          ))}
        </Descriptions>
      </Card>

      <Card size="small" title={`Пробы деформации (deform-probe, ${rig.deformProbes.length})`}>
        {rig.deformProbes.length ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {rig.deformProbes.map((p) => {
              const ok = p.tests.filter((t) => t.status === 'plausible').length;
              return (
                <Card
                  key={p.report.path}
                  type="inner"
                  size="small"
                  title={
                    <Space wrap>
                      <Text strong>{p.label}</Text>
                      <Tag color={ok === p.tests.length ? 'green' : ok === 0 ? 'red' : 'orange'}>
                        правдоподобно {ok}/{p.tests.length}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        прогон {p.run}
                        {p.family ? ` · ${p.family}` : ''}
                      </Text>
                    </Space>
                  }
                  extra={<FileActions file={p.report} />}
                >
                  <Row gutter={16}>
                    <Col xs={24} lg={10}>
                      <Table
                        size="small"
                        rowKey="test"
                        pagination={false}
                        dataSource={p.tests}
                        columns={[
                          { title: 'Проба', dataIndex: 'test' },
                          { title: 'Кость', dataIndex: 'bone' },
                          { title: '°', dataIndex: 'deg', width: 50 },
                          { title: 'Итог', dataIndex: 'status', render: (s: string) => <Tag color={probeColor(s)}>{s}</Tag> },
                        ]}
                      />
                      {p.source ? (
                        <Text type="secondary" style={{ fontSize: 11, wordBreak: 'break-all' }}>
                          источник: {p.source}
                        </Text>
                      ) : null}
                    </Col>
                    <Col xs={24} lg={14}>
                      {p.sheet?.servable ? <Image src={fileUrl(p.sheet)} style={{ maxHeight: 320, objectFit: 'contain' }} /> : <Text type="secondary">листа деформации нет</Text>}
                    </Col>
                  </Row>
                </Card>
              );
            })}
          </Space>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="проб деформации для этого персонажа нет" />
        )}
      </Card>

      {rig.rigLayers.length ? (
        <Card size="small" title="Слои реестра, связанные с ригом">
          <LayersTable layers={rig.rigLayers} mainId={page.id} />
        </Card>
      ) : null}

      <Card size="small" title={`Отчёты инспекции рига (${rig.rigReports.length})`}>
        <FileTable files={rig.rigReports} emptyText="отчётов нет" />
      </Card>
      {!rig.bones.length ? <Alert type="warning" message="Скелет для персонажа в контракте не найден" /> : null}
    </Space>
  );
};
