/**
 * Path guard for the art-hub dev file endpoint.
 *
 * Only repo-relative paths inside a fixed whitelist of roots are served.
 * Rejected: empty paths, NUL bytes, absolute paths (POSIX, Windows drive,
 * UNC), any `..` segment, dot-segments starting with "." (hidden files),
 * paths outside the whitelist and symlinks/junctions that resolve outside
 * the whitelist.
 */
import fs from 'node:fs';
import path from 'node:path';

/**
 * Whitelisted roots (repo-relative, POSIX). Keep in sync with README.md.
 * `docs/game-design/decisions/` — decision logs (markdown only, see ALLOWED_EXT_BY_PREFIX).
 * `docs/game-design/audio/` — audio docs 00…07 and the sound registry (markdown and csv only).
 */
export const ALLOWED_PREFIXES = [
  'art/',
  'docs/art-pipeline/',
  'docs/game-design/evidence/',
  'docs/game-design/decisions/',
  'docs/game-design/audio/',
] as const;

/** Prefixes that serve only the listed extensions (everything else under them → 403). */
const ALLOWED_EXT_BY_PREFIX: Record<string, RegExp> = {
  'docs/game-design/decisions/': /\.md$/i,
  'docs/game-design/audio/': /\.(md|csv)$/i,
};

/** blender/<ASSET>/<subdir>/… — only these subdirectories of blender asset folders are served. */
export const ALLOWED_BLENDER_SUBDIRS = ['preview', 'export', 'textures', 'variants', 'tripo-source'] as const;

const BLENDER_RE = new RegExp(`^blender/[^/]+/(${ALLOWED_BLENDER_SUBDIRS.join('|')})/.+`);

export type GuardFailure = { ok: false; status: 400 | 403 | 404; reason: string };
export type GuardSuccess = { ok: true; abs: string; rel: string; size: number; mtimeMs: number };
export type GuardResult = GuardSuccess | GuardFailure;

/**
 * Normalises a user supplied path into a repo-relative POSIX path or returns
 * null when the path is structurally unsafe (absolute, `..`, NUL, hidden).
 */
export function normalizeRelPath(input: unknown): string | null {
  if (typeof input !== 'string') return null;
  if (input.length === 0 || input.length > 1024) return null;
  if (input.includes('\0')) return null;
  const slashed = input.replace(/\\/g, '/');
  // absolute POSIX, UNC (//server), Windows drive (C:), device paths
  if (slashed.startsWith('/')) return null;
  if (/^[a-zA-Z]:/.test(slashed)) return null;
  if (slashed.includes(':')) return null; // NTFS alternate data streams, drive letters mid-path
  const segments = slashed.split('/');
  const out: string[] = [];
  for (const seg of segments) {
    if (seg === '' || seg === '.') continue;
    if (seg === '..') return null; // explicit ban, no resolution of parent segments
    if (seg.startsWith('.')) return null; // hidden files/dirs (.git, .env, .gitignore…)
    if (/[<>|?*"]/.test(seg)) return null;
    out.push(seg);
  }
  if (out.length === 0) return null;
  return out.join('/');
}

/** True when a normalised repo-relative POSIX path lies inside the whitelist. */
export function isAllowedRelPath(rel: string): boolean {
  const p = normalizeRelPath(rel);
  if (p === null) return false;
  const prefix = ALLOWED_PREFIXES.find((pre) => p.startsWith(pre) && p.length > pre.length);
  if (prefix) return ALLOWED_EXT_BY_PREFIX[prefix]?.test(p) ?? true;
  return BLENDER_RE.test(p);
}

function isInside(parent: string, child: string): boolean {
  const rel = path.relative(parent, child);
  return rel !== '' && !rel.startsWith('..') && !path.isAbsolute(rel);
}

function toPosixRel(root: string, abs: string): string {
  return path.relative(root, abs).split(path.sep).join('/');
}

/**
 * Resolves a requested path to an absolute file path inside the repo.
 * Performs lexical checks, whitelist checks and a realpath check so a
 * symlink/junction inside a whitelisted directory cannot escape it.
 */
export function resolveSafePath(repoRoot: string, requested: unknown): GuardResult {
  const rel = normalizeRelPath(requested);
  if (rel === null) return { ok: false, status: 400, reason: 'invalid path' };
  if (!isAllowedRelPath(rel)) return { ok: false, status: 403, reason: 'path outside whitelist' };

  const root = path.resolve(repoRoot);
  const abs = path.resolve(root, ...rel.split('/'));
  if (!isInside(root, abs)) return { ok: false, status: 403, reason: 'path escapes repo' };

  let real: string;
  let realRoot: string;
  try {
    realRoot = fs.realpathSync.native(root);
    real = fs.realpathSync.native(abs);
  } catch {
    return { ok: false, status: 404, reason: 'not found' };
  }
  if (!isInside(realRoot, real)) return { ok: false, status: 403, reason: 'symlink escapes repo' };
  const realRel = toPosixRel(realRoot, real);
  // Case-insensitive file systems may change the case of the path; compare lower-case on Windows.
  const cmpA = process.platform === 'win32' ? realRel.toLowerCase() : realRel;
  const allowed = isAllowedRelPath(realRel) || isAllowedRelPath(cmpA);
  if (!allowed) return { ok: false, status: 403, reason: 'symlink target outside whitelist' };

  let st: fs.Stats;
  try {
    st = fs.statSync(real);
  } catch {
    return { ok: false, status: 404, reason: 'not found' };
  }
  if (!st.isFile()) return { ok: false, status: 404, reason: 'not a file' };
  return { ok: true, abs: real, rel, size: st.size, mtimeMs: st.mtimeMs };
}

const MIME: Record<string, string> = {
  '.mp4': 'video/mp4',
  '.m4v': 'video/mp4',
  '.webm': 'video/webm',
  '.mov': 'video/quicktime',
  '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json',
  '.fbx': 'application/octet-stream',
  '.bvh': 'text/plain; charset=utf-8',
  '.obj': 'text/plain; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.wav': 'audio/wav',
  '.mp3': 'audio/mpeg',
  '.ogg': 'audio/ogg',
  '.oga': 'audio/ogg',
  '.flac': 'audio/flac',
  '.m4a': 'audio/mp4',
  '.aac': 'audio/aac',
  '.opus': 'audio/ogg',
  '.json': 'application/json; charset=utf-8',
  '.jsonl': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.log': 'text/plain; charset=utf-8',
  '.csv': 'text/csv; charset=utf-8',
  '.py': 'text/plain; charset=utf-8',
  '.sh': 'text/plain; charset=utf-8',
  '.patch': 'text/plain; charset=utf-8',
  '.diff': 'text/plain; charset=utf-8',
  // HTML is served as text so evidence files cannot run scripts on the dev origin.
  '.html': 'text/plain; charset=utf-8',
  '.htm': 'text/plain; charset=utf-8',
};

export function mimeFor(file: string): string {
  return MIME[path.extname(file).toLowerCase()] ?? 'application/octet-stream';
}

export type ByteRange = { start: number; end: number };

/**
 * Parses a single-range `Range: bytes=…` header.
 * Returns null when there is no (usable) header, 'unsatisfiable' for 416.
 */
export function parseRange(header: string | undefined, size: number): ByteRange | null | 'unsatisfiable' {
  if (!header) return null;
  const m = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!m) return null; // multi-range or malformed → ignore, send full body
  const [, s, e] = m;
  if (s === '' && e === '') return null;
  let start: number;
  let end: number;
  if (s === '') {
    const suffix = Number(e);
    if (!Number.isFinite(suffix) || suffix <= 0) return 'unsatisfiable';
    start = Math.max(0, size - suffix);
    end = size - 1;
  } else {
    start = Number(s);
    end = e === '' ? size - 1 : Math.min(Number(e), size - 1);
  }
  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || start >= size) return 'unsatisfiable';
  return { start, end };
}
