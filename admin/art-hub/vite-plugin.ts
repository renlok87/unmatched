/**
 * Vite dev-server plugin for the admin "Арт-хаб" page.
 *
 *   GET /__art-hub/data                      → fresh aggregation (cached by mtime/size fingerprint)
 *   GET /__art-hub/file?path=<repo-rel>      → whitelisted repo file (Range for video/seek, ETag)
 *   GET /__art-hub/texture?model=<rel>&name=<file>
 *        → texture next to a model (same dir, <model>.fbm/, ../textures/, textures/);
 *          a 1×1 grey PNG with `X-Art-Hub-Missing: 1` when not found (no console noise)
 *
 * `apply: 'serve'` — the plugin exists only on the dev server; production builds
 * contain no endpoint and the page shows a stub.
 */
import fs from 'node:fs';
import type { IncomingMessage, ServerResponse } from 'node:http';
import path from 'node:path';
import type { Plugin } from 'vite';
import { ArtHubAggregator } from './aggregate';
import { mimeFor, normalizeRelPath, parseRange, resolveSafePath, type GuardSuccess } from './path-guard';

export const ART_HUB_PREFIX = '/__art-hub';

/** 1×1 grey RGBA PNG (valid chunk CRCs; checked in tests). */
export const PLACEHOLDER_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGOYNX/ZfwAGlQLf/49hiQAAAABJRU5ErkJggg==',
  'base64',
);

const FILE_CSP = "default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'; sandbox";

type Next = (err?: unknown) => void;

function sendJson(res: ServerResponse, status: number, body: unknown) {
  const text = JSON.stringify(body);
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Content-Length', Buffer.byteLength(text));
  res.end(text);
}

function sendFile(req: IncomingMessage, res: ServerResponse, file: GuardSuccess, download: boolean) {
  const etag = `W/"${file.size.toString(16)}-${Math.floor(file.mtimeMs).toString(16)}"`;
  res.setHeader('Accept-Ranges', 'bytes');
  res.setHeader('ETag', etag);
  res.setHeader('Last-Modified', new Date(file.mtimeMs).toUTCString());
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Content-Security-Policy', FILE_CSP);
  res.setHeader('Content-Type', mimeFor(file.abs));
  const name = encodeURIComponent(path.basename(file.abs));
  res.setHeader('Content-Disposition', `${download ? 'attachment' : 'inline'}; filename*=UTF-8''${name}`);
  if (req.headers['if-none-match'] === etag) {
    res.statusCode = 304;
    res.end();
    return;
  }
  const range = parseRange(req.headers.range, file.size);
  if (range === 'unsatisfiable') {
    res.statusCode = 416;
    res.setHeader('Content-Range', `bytes */${file.size}`);
    res.end();
    return;
  }
  const start = range ? range.start : 0;
  const end = range ? range.end : file.size - 1;
  res.statusCode = range ? 206 : 200;
  if (range) res.setHeader('Content-Range', `bytes ${start}-${end}/${file.size}`);
  res.setHeader('Content-Length', file.size === 0 ? 0 : end - start + 1);
  if (req.method === 'HEAD' || file.size === 0) {
    res.end();
    return;
  }
  const stream = fs.createReadStream(file.abs, { start, end });
  stream.on('error', () => {
    if (!res.headersSent) res.statusCode = 500;
    res.destroy();
  });
  res.on('close', () => stream.destroy());
  stream.pipe(res);
}

/**
 * Candidate repo-relative texture paths for a texture referenced by a model file:
 * the model dir, `<stem>.fbm/`, then `textures/`, `source/textures/` and `export/` of every
 * ancestor down to the asset folder. Only the basename of `name` is used, so `../` in FBX
 * texture paths cannot escape; every candidate still goes through resolveSafePath.
 */
export function textureCandidates(modelRel: string, name: string): string[] {
  const base = name.replace(/\\/g, '/').split('/').pop() ?? '';
  if (!base || base === '.' || base === '..') return [];
  const dir = path.posix.dirname(modelRel);
  const stem = path.posix.basename(modelRel).replace(/\.[^.]+$/, '');
  const out = [`${dir}/${base}`, `${dir}/${stem}.fbm/${base}`];
  // Walk up to the asset folder: blender/<ASSET> (2 segments) or art/pipeline-candidates/<ASSET> (3).
  const parts = dir.split('/');
  const minDepth = parts[0] === 'blender' ? 2 : parts[0] === 'art' ? 3 : parts.length;
  for (let depth = parts.length; depth >= minDepth; depth--) {
    const anc = parts.slice(0, depth).join('/');
    out.push(`${anc}/textures/${base}`, `${anc}/source/textures/${base}`, `${anc}/export/${base}`);
  }
  return [...new Set(out)];
}

export interface ArtHubMiddlewareOptions {
  repoRoot: string;
  aggregator?: ArtHubAggregator;
}

/** Connect-style middleware mounted at /__art-hub (req.url has the prefix stripped). */
export function createArtHubMiddleware(opts: ArtHubMiddlewareOptions) {
  const repoRoot = path.resolve(opts.repoRoot);
  const aggregator = opts.aggregator ?? new ArtHubAggregator(repoRoot);
  return (req: IncomingMessage, res: ServerResponse, next: Next) => {
    let url: URL;
    try {
      url = new URL(req.url ?? '/', 'http://art-hub.local');
    } catch {
      sendJson(res, 400, { error: 'bad url' });
      return;
    }
    const route = url.pathname.replace(/^\/+/, '').replace(/\/+$/, '');
    if (!['data', 'file', 'texture', ''].includes(route)) {
      next();
      return;
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      res.setHeader('Allow', 'GET, HEAD');
      sendJson(res, 405, { error: 'method not allowed' });
      return;
    }
    try {
      if (route === 'data' || route === '') {
        sendJson(res, 200, aggregator.get());
        return;
      }
      if (route === 'file') {
        const guard = resolveSafePath(repoRoot, url.searchParams.get('path'));
        if (!guard.ok) {
          sendJson(res, guard.status, { error: guard.reason });
          return;
        }
        sendFile(req, res, guard, url.searchParams.get('download') === '1');
        return;
      }
      // texture resolver
      const model = normalizeRelPath(url.searchParams.get('model'));
      const name = url.searchParams.get('name') ?? '';
      if (model === null) {
        sendJson(res, 400, { error: 'invalid model path' });
        return;
      }
      for (const cand of textureCandidates(model, name)) {
        const guard = resolveSafePath(repoRoot, cand);
        if (guard.ok) {
          sendFile(req, res, guard, false);
          return;
        }
      }
      res.statusCode = 200;
      res.setHeader('Content-Type', 'image/png');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('X-Art-Hub-Missing', '1');
      res.setHeader('Content-Length', PLACEHOLDER_PNG.length);
      res.end(req.method === 'HEAD' ? undefined : PLACEHOLDER_PNG);
    } catch (err) {
      sendJson(res, 500, { error: err instanceof Error ? err.message : String(err) });
    }
  };
}

export interface ArtHubPluginOptions {
  /** Repo root; default = parent of the Vite root (admin/ → repo). */
  repoRoot?: string;
}

export function artHubPlugin(options: ArtHubPluginOptions = {}): Plugin {
  return {
    name: 'unmatched-art-hub',
    apply: 'serve',
    configureServer(server) {
      const repoRoot = options.repoRoot ?? path.resolve(server.config.root, '..');
      server.middlewares.use(ART_HUB_PREFIX, createArtHubMiddleware({ repoRoot }));
    },
  };
}
