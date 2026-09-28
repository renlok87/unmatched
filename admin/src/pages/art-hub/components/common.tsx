import React, { createContext, useContext } from 'react';
import { Button, Empty, Image, Space, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  CodeSandboxOutlined,
  DownloadOutlined,
  ExportOutlined,
  FileSearchOutlined,
} from '@ant-design/icons';
import type { FileRef, Vocabulary } from '../../../../art-hub/types';
import { fileUrl } from '../api';
import { basename, formatBytes, formatTime, timeAgo } from '../format';

const { Text } = Typography;

// ------------------------------------------------------------------ context

export interface ArtHubUi {
  vocab: Vocabulary;
  previewText: (f: FileRef) => void;
  view3D: (f: FileRef, title?: string) => void;
  openPage: (id: string, tab?: string) => void;
}

export const ArtHubUiContext = createContext<ArtHubUi | null>(null);

export function useArtHubUi(): ArtHubUi {
  const ctx = useContext(ArtHubUiContext);
  if (!ctx) throw new Error('ArtHubUiContext is missing');
  return ctx;
}

/** Explicit breakpoint maps: antd fills missing breakpoints with 3 columns. */
export const TWO_COLUMNS = { xs: 1, sm: 1, md: 2, lg: 2, xl: 2, xxl: 2 } as const;
export const ONE_TWO_COLUMNS = { xs: 1, sm: 1, md: 1, lg: 1, xl: 1, xxl: 2 } as const;

// ------------------------------------------------------------------ status tags

const STATUS_COLORS = ['default', 'blue', 'cyan', 'gold'];

/** Project status (registry vocabulary). Only the last vocabulary item is green. */
export const StatusTag: React.FC<{ status?: string | null; label?: string }> = ({ status, label }) => {
  const { vocab } = useArtHubUi();
  if (!status) return <Tag>нет статуса</Tag>;
  const idx = vocab.status.findIndex((s) => s.name === status);
  if (idx < 0) {
    return (
      <Tooltip title="Статус вне словаря проекта — показан как есть">
        <Tag style={{ borderStyle: 'dashed' }}>{label ?? status}</Tag>
      </Tooltip>
    );
  }
  const last = idx === vocab.status.length - 1;
  const color = last ? 'green' : STATUS_COLORS[Math.min(idx, STATUS_COLORS.length - 1)];
  return (
    <Tooltip title={vocab.status[idx]!.description || undefined}>
      <Tag color={color}>{label ?? status}</Tag>
    </Tooltip>
  );
};

const CLIP_COLORS: Record<string, string> = {
  proposed: 'blue',
  draft_test: 'purple',
  measured: 'cyan',
  technically_imported: 'gold',
  artistically_accepted: 'green',
  rejected: 'red',
};

/** clip-manifest status (en) shown with its Russian label from the schema. */
export const ClipStatusTag: React.FC<{ status?: string }> = ({ status }) => {
  const { vocab } = useArtHubUi();
  if (!status) return <Tag>—</Tag>;
  return (
    <Tooltip title={`clip-manifest: ${status}`}>
      <Tag color={CLIP_COLORS[status] ?? 'default'}>{vocab.clipStatus[status] ?? status}</Tag>
    </Tooltip>
  );
};

export const StageTag: React.FC<{ stage?: string | null }> = ({ stage }) => {
  const { vocab } = useArtHubUi();
  if (!stage) return <Tag>стадия —</Tag>;
  const idx = vocab.stage.indexOf(stage);
  return (
    <Tooltip title={idx >= 0 ? `стадия ${idx + 1} из ${vocab.stage.length}` : 'стадия вне словаря'}>
      <Tag color="geekblue">{idx >= 0 ? `${idx + 1}/${vocab.stage.length} ` : ''}{stage}</Tag>
    </Tooltip>
  );
};

export const ValidationTag: React.FC<{ result?: string }> = ({ result }) => {
  if (result === 'pass') return <Tag color="green">validate_clip: pass</Tag>;
  if (result === 'fail') return <Tag color="red">validate_clip: fail</Tag>;
  return <Tag>validate_clip: не запускался</Tag>;
};

// ------------------------------------------------------------------ files

const SHA_TAG: Record<string, { color: string; text: string; tip: string }> = {
  match: { color: 'green', text: 'sha ✓', tip: 'sha256 файла совпадает с заявленным' },
  mismatch: { color: 'red', text: 'sha ✗', tip: 'sha256 файла НЕ совпадает с заявленным (файл изменён или дописывается)' },
  'skipped-large': { color: 'default', text: 'sha: не проверен', tip: 'файл больше 16 МБ — хэш не пересчитывается' },
  'missing-file': { color: 'red', text: 'sha: нет файла', tip: 'хэш заявлен, файла нет' },
};

export const ShaTag: React.FC<{ file: FileRef }> = ({ file }) => {
  if (!file.sha256) return <Text type="secondary">—</Text>;
  const t = file.shaCheck ? SHA_TAG[file.shaCheck] : undefined;
  return (
    <Tooltip title={<span style={{ wordBreak: 'break-all' }}>{t?.tip ?? 'заявленный sha256'}: {file.sha256}</span>}>
      <Space size={4}>
        {t ? <Tag color={t.color}>{t.text}</Tag> : null}
        <Text code copyable={{ text: file.sha256 }} style={{ fontSize: 11 }}>
          {file.sha256.slice(0, 10)}
        </Text>
      </Space>
    </Tooltip>
  );
};

export const ExistsTag: React.FC<{ file: FileRef }> = ({ file }) => {
  const extra = [];
  if (file.root === 'art-worktree') extra.push(<Tag key="wt" color="purple">арт-worktree</Tag>);
  if (file.kind === 'ue-asset') extra.push(<Tag key="ue" color="magenta">UE-ассет</Tag>);
  if (file.expect === 'planned') extra.push(<Tag key="pl">план</Tag>);
  let main: React.ReactNode;
  if (file.exists === true) main = <Tag color="success">есть</Tag>;
  else if (file.exists === false) main = <Tag color={file.expect === 'planned' ? 'default' : 'error'}>нет</Tag>;
  else main = <Tag>не проверено</Tag>;
  return (
    <Space size={2} wrap>
      {main}
      {extra}
      {file.exists && !file.servable && file.kind !== 'ue-asset' && file.kind !== 'dir' ? (
        <Tooltip title="Файл вне белого списка /__art-hub/file (или вне репо) — не отдаётся в браузер">
          <Tag>не отдаётся</Tag>
        </Tooltip>
      ) : null}
    </Space>
  );
};

const TEXT_KINDS = new Set(['json', 'markdown', 'text', 'bvh']);

export const FileActions: React.FC<{ file: FileRef; title?: string }> = ({ file, title }) => {
  const ui = useArtHubUi();
  if (!file.servable) return null;
  return (
    <Space size={0} wrap>
      {file.kind === 'glb' || file.kind === 'fbx' || file.kind === 'gltf' ? (
        <Tooltip title="3D-просмотр в браузере">
          <Button size="small" type="link" icon={<CodeSandboxOutlined />} onClick={() => ui.view3D(file, title)}>
            3D
          </Button>
        </Tooltip>
      ) : null}
      {TEXT_KINDS.has(file.kind) ? (
        <Button size="small" type="link" icon={<FileSearchOutlined />} onClick={() => ui.previewText(file)}>
          текст
        </Button>
      ) : null}
      <Tooltip title="Открыть в новой вкладке">
        <Button size="small" type="link" icon={<ExportOutlined />} href={fileUrl(file)} target="_blank" rel="noreferrer" />
      </Tooltip>
      <Tooltip title="Скачать">
        <Button size="small" type="link" icon={<DownloadOutlined />} href={fileUrl(file, { download: true })} />
      </Tooltip>
    </Space>
  );
};

export const FilePath: React.FC<{ file: FileRef; showDir?: boolean }> = ({ file, showDir = true }) => (
  <div style={{ minWidth: 0 }}>
    <Text strong style={{ wordBreak: 'break-all' }}>
      {basename(file.path)}
    </Text>
    {showDir ? (
      <div>
        <Text type="secondary" copyable={{ text: file.path }} style={{ fontSize: 11, wordBreak: 'break-all' }}>
          {file.path}
        </Text>
      </div>
    ) : null}
  </div>
);

export const FileTable: React.FC<{
  files: FileRef[];
  emptyText?: string;
  pageSize?: number;
  showRole?: boolean;
  size?: 'small' | 'middle';
}> = ({ files, emptyText = 'файлов нет', pageSize = 10, showRole = true, size = 'small' }) => {
  const columns: ColumnsType<FileRef> = [
    { title: 'Файл', key: 'path', render: (_, f) => <FilePath file={f} />, width: '38%' },
    ...(showRole
      ? [{ title: 'Роль / источник', key: 'role', render: (_: unknown, f: FileRef) => <Text style={{ fontSize: 12 }}>{f.role ?? f.origin ?? '—'}</Text> }]
      : []),
    { title: 'Размер', key: 'bytes', width: 90, render: (_, f) => formatBytes(f.bytes), sorter: (a, b) => (a.bytes ?? 0) - (b.bytes ?? 0) },
    {
      title: 'Изменён',
      key: 'mtime',
      width: 110,
      render: (_, f) => (f.mtime ? <Tooltip title={formatTime(f.mtime)}>{timeAgo(f.mtime)}</Tooltip> : '—'),
      sorter: (a, b) => (a.mtime ?? '').localeCompare(b.mtime ?? ''),
    },
    { title: 'sha256', key: 'sha', width: 190, render: (_, f) => <ShaTag file={f} /> },
    { title: 'Наличие', key: 'exists', width: 150, render: (_, f) => <ExistsTag file={f} /> },
    { title: '', key: 'act', width: 170, render: (_, f) => <FileActions file={f} title={f.role} /> },
  ];
  return (
    <Table<FileRef>
      rowKey={(f) => `${f.root}:${f.path}`}
      size={size}
      columns={columns}
      dataSource={files}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} /> }}
      pagination={files.length > pageSize ? { pageSize, size: 'small', showSizeChanger: false } : false}
      scroll={{ x: 900 }}
    />
  );
};

// ------------------------------------------------------------------ gallery

export const Gallery: React.FC<{ images: FileRef[]; size?: number; emptyText?: string; caption?: boolean }> = ({
  images,
  size = 150,
  emptyText = 'изображений нет',
  caption = true,
}) => {
  const servable = images.filter((f) => f.servable);
  const hidden = images.length - servable.length;
  if (images.length === 0) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />;
  return (
    <div>
      <Image.PreviewGroup>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {servable.map((f) => (
            <div key={f.path} style={{ width: size }} data-testid="art-hub-thumb">
              <Image
                src={fileUrl(f)}
                loading="lazy"
                width={size}
                height={Math.round(size * 0.75)}
                style={{ objectFit: 'cover', borderRadius: 6, background: '#f5f5f5' }}
                alt={basename(f.path)}
              />
              {caption ? (
                <Tooltip title={`${f.path}${f.role ? ` — ${f.role}` : ''}`}>
                  <div style={{ fontSize: 11, lineHeight: 1.3, marginTop: 2, wordBreak: 'break-all', color: '#595959' }}>
                    {basename(f.path)}
                    {f.mtime ? <span style={{ color: '#8c8c8c' }}> · {timeAgo(f.mtime)}</span> : null}
                  </div>
                </Tooltip>
              ) : null}
            </div>
          ))}
        </div>
      </Image.PreviewGroup>
      {hidden > 0 ? (
        <Text type="secondary" style={{ fontSize: 12 }}>
          Ещё {hidden} изображ. вне белого списка или вне репо (например, арт-worktree) — пути есть в таблицах файлов.
        </Text>
      ) : null}
    </div>
  );
};

export const LongText: React.FC<{ text?: string; rows?: number }> = ({ text, rows = 3 }) =>
  text ? (
    <Typography.Paragraph ellipsis={{ rows, expandable: true, symbol: 'ещё' }} style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
      {text}
    </Typography.Paragraph>
  ) : (
    <Text type="secondary">—</Text>
  );
