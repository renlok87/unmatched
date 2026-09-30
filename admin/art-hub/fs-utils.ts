/**
 * File-system helpers for the art-hub aggregator: bounded directory walk,
 * mtime-keyed caches for JSON/text/sha256, a small CSV parser and markdown
 * helpers. Everything is synchronous and read-only.
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import type { FileKind } from './types';

export interface WalkEntry {
  rel: string;
  bytes: number;
  mtimeMs: number;
}

/** Directory names never descended into (transient/foreign/binary side folders). */
const SKIP_DIR_NAMES = new Set(['work', 'node_modules', '__pycache__', '.git', '.staging', 'logs']);

export function shouldSkipDir(name: string): boolean {
  return SKIP_DIR_NAMES.has(name) || name.startsWith('.') || name.endsWith('.fbm');
}

/**
 * Walks `relDir` (repo-relative) and returns regular files. Symlinks and
 * junctions are not followed. Missing directories yield an empty list.
 */
export function walkFiles(repoRoot: string, relDir: string, maxFiles = 20000): WalkEntry[] {
  const out: WalkEntry[] = [];
  const stack: string[] = [relDir.replace(/\/+$/, '')];
  while (stack.length > 0 && out.length < maxFiles) {
    const rel = stack.pop()!;
    const abs = path.join(repoRoot, ...rel.split('/'));
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(abs, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      if (e.isSymbolicLink()) continue;
      const childRel = `${rel}/${e.name}`;
      if (e.isDirectory()) {
        if (!shouldSkipDir(e.name)) stack.push(childRel);
      } else if (e.isFile()) {
        if (e.name.startsWith('.')) continue;
        try {
          const st = fs.statSync(path.join(abs, e.name));
          out.push({ rel: childRel, bytes: st.size, mtimeMs: st.mtimeMs });
        } catch {
          /* file vanished while walking — ignore */
        }
      }
    }
  }
  return out;
}

export function listDirs(repoRoot: string, relDir: string): string[] {
  try {
    return fs
      .readdirSync(path.join(repoRoot, ...relDir.split('/')), { withFileTypes: true })
      .filter((e) => e.isDirectory() && !e.isSymbolicLink() && !e.name.startsWith('.'))
      .map((e) => e.name)
      .sort();
  } catch {
    return [];
  }
}

export interface StatInfo {
  exists: boolean;
  isFile: boolean;
  isDir: boolean;
  bytes?: number;
  mtimeMs?: number;
}

type CacheSlot<T> = { key: string; value: T };

/** mtime+size keyed caches, shared across aggregation runs. */
export class FileCache {
  private jsonCache = new Map<string, CacheSlot<{ value?: unknown; error?: string }>>();
  private textCache = new Map<string, CacheSlot<string | undefined>>();
  private shaCache = new Map<string, CacheSlot<string>>();
  private derivedCache = new Map<string, CacheSlot<unknown>>();
  private statMemo = new Map<string, StatInfo>();

  /** Clears the per-run stat memo (call at the start of each aggregation). */
  beginRun(): void {
    this.statMemo.clear();
  }

  stat(abs: string): StatInfo {
    const memo = this.statMemo.get(abs);
    if (memo) return memo;
    let info: StatInfo;
    try {
      const st = fs.statSync(abs);
      info = { exists: true, isFile: st.isFile(), isDir: st.isDirectory(), bytes: st.size, mtimeMs: st.mtimeMs };
    } catch {
      info = { exists: false, isFile: false, isDir: false };
    }
    this.statMemo.set(abs, info);
    return info;
  }

  private key(abs: string): string | null {
    const st = this.stat(abs);
    if (!st.exists || !st.isFile) return null;
    return `${st.mtimeMs}:${st.bytes}`;
  }

  /** Parses JSON; returns {error} for missing files or partial writes instead of throwing. */
  readJson(abs: string): { value?: unknown; error?: string } {
    const key = this.key(abs);
    if (key === null) return { error: 'missing' };
    const hit = this.jsonCache.get(abs);
    if (hit && hit.key === key) return hit.value;
    let result: { value?: unknown; error?: string };
    try {
      const raw = fs.readFileSync(abs, 'utf8').replace(/^﻿/, '');
      result = { value: JSON.parse(raw) };
    } catch (err) {
      result = { error: err instanceof Error ? err.message : String(err) };
    }
    this.jsonCache.set(abs, { key, value: result });
    return result;
  }

  readText(abs: string, maxBytes = 256 * 1024): string | undefined {
    const key = this.key(abs);
    if (key === null) return undefined;
    const hit = this.textCache.get(abs);
    if (hit && hit.key === key) return hit.value;
    let value: string | undefined;
    try {
      const fd = fs.openSync(abs, 'r');
      try {
        const buf = Buffer.alloc(Math.min(maxBytes, this.stat(abs).bytes ?? maxBytes));
        const n = fs.readSync(fd, buf, 0, buf.length, 0);
        value = buf.subarray(0, n).toString('utf8').replace(/^﻿/, '');
      } finally {
        fs.closeSync(fd);
      }
    } catch {
      value = undefined;
    }
    this.textCache.set(abs, { key, value });
    return value;
  }

  /**
   * Value derived from a text file (e.g. regex matches), cached by mtime/size.
   * Only the derived value is kept, not the text itself.
   */
  derive<T>(abs: string, tag: string, fn: (text: string) => T, maxBytes = 1024 * 1024): T | undefined {
    const key = this.key(abs);
    if (key === null) return undefined;
    const slotKey = `${tag}\0${abs}`;
    const hit = this.derivedCache.get(slotKey);
    if (hit && hit.key === key) return hit.value as T;
    let value: T | undefined;
    try {
      const fd = fs.openSync(abs, 'r');
      try {
        const buf = Buffer.alloc(Math.min(maxBytes, this.stat(abs).bytes ?? maxBytes));
        const n = fs.readSync(fd, buf, 0, buf.length, 0);
        value = fn(buf.subarray(0, n).toString('utf8'));
      } finally {
        fs.closeSync(fd);
      }
    } catch {
      value = undefined;
    }
    this.derivedCache.set(slotKey, { key, value });
    return value;
  }

  sha256(abs: string): string | undefined {
    const key = this.key(abs);
    if (key === null) return undefined;
    const hit = this.shaCache.get(abs);
    if (hit && hit.key === key) return hit.value;
    try {
      const hash = crypto.createHash('sha256').update(fs.readFileSync(abs)).digest('hex');
      this.shaCache.set(abs, { key, value: hash });
      return hash;
    } catch {
      return undefined;
    }
  }
}

const EXT_KIND: Record<string, FileKind> = {
  '.glb': 'glb',
  '.gltf': 'gltf',
  '.fbx': 'fbx',
  '.bvh': 'bvh',
  '.png': 'image',
  '.jpg': 'image',
  '.jpeg': 'image',
  '.webp': 'image',
  '.gif': 'image',
  '.svg': 'image',
  '.mp4': 'video',
  '.m4v': 'video',
  '.webm': 'video',
  '.mov': 'video',
  '.wav': 'audio',
  '.mp3': 'audio',
  '.ogg': 'audio',
  '.oga': 'audio',
  '.flac': 'audio',
  '.m4a': 'audio',
  '.aac': 'audio',
  '.opus': 'audio',
  '.json': 'json',
  '.jsonl': 'text',
  '.md': 'markdown',
  '.txt': 'text',
  '.log': 'text',
  '.csv': 'text',
  '.py': 'text',
  '.patch': 'text',
  '.diff': 'text',
  '.blend': 'blend',
  '.blend1': 'blend',
  '.zip': 'archive',
  '.uasset': 'ue-asset',
};

export const AUDIO_EXTS = ['.wav', '.mp3', '.ogg', '.oga', '.flac', '.m4a', '.aac', '.opus'];

export function kindFromPath(p: string): FileKind {
  const ext = path.posix.extname(p.split('#')[0] ?? p).toLowerCase();
  return EXT_KIND[ext] ?? 'other';
}

/** Minimal RFC 4180 CSV parser (quoted fields, escaped quotes, CRLF). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i]!;
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else quoted = false;
      } else field += c;
      continue;
    }
    if (c === '"') quoted = true;
    else if (c === ',') {
      row.push(field);
      field = '';
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else field += c;
  }
  if (field !== '' || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.some((f) => f.trim() !== ''));
}

export function csvToObjects(text: string): Record<string, string>[] {
  const rows = parseCsv(text.replace(/^﻿/, ''));
  const header = rows[0];
  if (!header) return [];
  return rows.slice(1).map((r) => Object.fromEntries(header.map((h, i) => [h.trim(), (r[i] ?? '').trim()])));
}

/** First markdown H1. */
export function mdTitle(md: string): string | undefined {
  const m = /^#\s+(.+)$/m.exec(md);
  return m?.[1]?.trim();
}

/** First bold "Решение…" line of an act, stripped of markdown emphasis. */
export function mdDecision(md: string, max = 420): string | undefined {
  for (const line of md.split(/\r?\n/)) {
    const t = line.trim();
    if (/^\*\*Решение[^*]*\*\*/.test(t) || /^Решение[^:]*:/.test(t)) {
      const clean = t.replace(/\*\*/g, '').replace(/\s+/g, ' ').trim();
      return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
    }
  }
  return undefined;
}

/** Rows of the first pipe table after a heading matching `headingRe`. */
export function mdTableAfterHeading(md: string, headingRe: RegExp): string[][] {
  const lines = md.split(/\r?\n/);
  const start = lines.findIndex((l) => headingRe.test(l));
  if (start < 0) return [];
  const rows: string[][] = [];
  let inTable = false;
  for (let i = start + 1; i < lines.length; i++) {
    const l = lines[i]!.trim();
    if (/^#{1,6}\s/.test(l)) break;
    if (l.startsWith('|')) {
      inTable = true;
      const cells = l
        .replace(/^\|/, '')
        .replace(/\|$/, '')
        .split('|')
        .map((c) => c.trim());
      if (cells.every((c) => /^:?-{2,}:?$/.test(c))) continue;
      rows.push(cells);
    } else if (inTable && l === '') break;
  }
  return rows;
}

/** Numbered list items ("1. …") of the section after a heading. */
export function mdListAfterHeading(md: string, headingRe: RegExp): string[] {
  const lines = md.split(/\r?\n/);
  const start = lines.findIndex((l) => headingRe.test(l));
  if (start < 0) return [];
  const items: string[] = [];
  for (let i = start + 1; i < lines.length; i++) {
    const l = lines[i]!.trim();
    if (/^#{1,6}\s/.test(l)) break;
    const m = /^\d+\.\s+(.*)$/.exec(l);
    if (m) items.push(stripMd(m[1]!));
  }
  return items;
}

export function stripMd(s: string): string {
  return s
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .trim();
}

/** Extracts repo-path-like tokens from free text (ledger refs, notes). */
export function pathTokens(text: string | undefined): string[] {
  if (!text) return [];
  const out = new Set<string>();
  for (const m of text.matchAll(/[A-Za-z0-9_.\-]+(?:\/[A-Za-z0-9_.\-]+)+\/?/g)) {
    out.add(m[0].replace(/\/+$/, ''));
  }
  return [...out];
}

export function isoTime(ms: number | undefined): string | undefined {
  return ms === undefined ? undefined : new Date(ms).toISOString();
}
