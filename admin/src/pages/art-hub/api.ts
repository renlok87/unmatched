import { useCallback, useEffect, useRef, useState } from 'react';
import type { ArtHubData, FileRef } from '../../../art-hub/types';

export const ART_HUB_API = '/__art-hub';
export const AUTO_REFRESH_MS = 30_000;

/** True only on the Vite dev server, where the art-hub plugin is mounted. */
export const IS_DEV = Boolean(import.meta.env.DEV);

type RefLike = Pick<FileRef, 'path'> & Partial<Pick<FileRef, 'mtime'>>;

/** URL of a whitelisted repo file; `v` busts the cache when the file changes. */
export function fileUrl(ref: RefLike | string, opts: { download?: boolean } = {}): string {
  const r = typeof ref === 'string' ? { path: ref } : ref;
  const q = new URLSearchParams({ path: r.path });
  if (r.mtime) q.set('v', r.mtime);
  if (opts.download) q.set('download', '1');
  return `${ART_HUB_API}/file?${q.toString()}`;
}

/** Rewrites texture requests of a model loader to the dev texture resolver. */
export function textureUrl(modelPath: string, requested: string): string {
  const name = decodeURIComponent(requested.split('?')[0]!.replace(/\\/g, '/').split('/').pop() ?? '');
  return `${ART_HUB_API}/texture?${new URLSearchParams({ model: modelPath, name }).toString()}`;
}

export interface ArtHubState {
  data?: ArtHubData;
  error?: string;
  loading: boolean;
  lastFetched?: Date;
  refresh: () => void;
}

export function useArtHubData(autoRefresh: boolean): ArtHubState {
  const [data, setData] = useState<ArtHubData>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(IS_DEV);
  const [lastFetched, setLastFetched] = useState<Date>();
  const inflight = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    if (!IS_DEV) return;
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;
    setLoading(true);
    fetch(`${ART_HUB_API}/data`, { cache: 'no-store', signal: ctrl.signal })
      .then(async (res) => {
        const type = res.headers.get('content-type') ?? '';
        if (!res.ok || !type.includes('application/json')) {
          throw new Error(`эндпоинт ${ART_HUB_API}/data ответил ${res.status}${type.includes('json') ? '' : ' (не JSON — плагин арт-хаба не подключён?)'}`);
        }
        return (await res.json()) as ArtHubData;
      })
      .then((d) => {
        setData(d);
        setError(undefined);
        setLastFetched(new Date());
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (inflight.current === ctrl) {
          inflight.current = null;
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    refresh();
    return () => inflight.current?.abort();
  }, [refresh]);

  useEffect(() => {
    if (!autoRefresh || !IS_DEV) return undefined;
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') refresh();
    }, AUTO_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [autoRefresh, refresh]);

  return { data, error, loading, lastFetched, refresh };
}
