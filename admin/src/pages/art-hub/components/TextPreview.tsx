import React, { useEffect, useState } from 'react';
import { Alert, Button, Drawer, Spin, Typography } from 'antd';
import { ExportOutlined } from '@ant-design/icons';
import type { FileRef } from '../../../../art-hub/types';
import { fileUrl } from '../api';

const MAX_CHARS = 400_000;

/** Read-only text/JSON/markdown viewer for whitelisted files. */
export const TextPreview: React.FC<{ file?: FileRef; onClose: () => void }> = ({ file, onClose }) => {
  const [text, setText] = useState<string>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!file) return undefined;
    const ctrl = new AbortController();
    setText(undefined);
    setError(undefined);
    setLoading(true);
    fetch(fileUrl(file), { signal: ctrl.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        let body = await res.text();
        if (file.kind === 'json') {
          try {
            body = JSON.stringify(JSON.parse(body), null, 2);
          } catch {
            /* show raw */
          }
        }
        setText(body.length > MAX_CHARS ? `${body.slice(0, MAX_CHARS)}\n… (обрезано)` : body);
      })
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === 'AbortError')) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [file]);

  return (
    <Drawer
      open={Boolean(file)}
      onClose={onClose}
      width="min(1100px, 92vw)"
      title={<Typography.Text style={{ wordBreak: 'break-all' }}>{file?.path}</Typography.Text>}
      extra={
        file ? (
          <Button icon={<ExportOutlined />} href={fileUrl(file)} target="_blank" rel="noreferrer">
            открыть
          </Button>
        ) : null
      }
    >
      {loading ? <Spin /> : null}
      {error ? <Alert type="error" message={`Не удалось загрузить: ${error}`} /> : null}
      {text !== undefined ? (
        <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, lineHeight: 1.5, margin: 0 }}>{text}</pre>
      ) : null}
    </Drawer>
  );
};
