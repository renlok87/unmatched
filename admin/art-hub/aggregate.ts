/**
 * Art-hub aggregator: builds a read-only view of the 3D/animation art
 * pipeline from files in the repo (no database, no network).
 *
 * Sources (all optional; missing or half-written files become warnings):
 *   docs/art-pipeline/asset-registry.json               — assets, statuses, layers, next step/blocker
 *   docs/art-pipeline/animation-refs/*.json             — video reference manifests (per asset)
 *   art/animation-refs/<ASSET>/<CUE>/[takeN/]           — mp4, contact sheets, keyframes, analysis.json
 *   docs/art-pipeline/animation-library/clip-manifest.json + validation/*.json
 *   docs/art-pipeline/animation-library/VIDEO-TO-MOTION.md
 *   docs/art-pipeline/rig/rig-contract.json
 *   docs/art-pipeline/evidence/<any>/credits-ledger.json (latest)
 *   art/pipeline-candidates/<ASSET>/<run>/              — manifest.json, reports/, preview/, export/, source/
 *   docs/art-pipeline/*-report.{md,json}, docs/game-design/evidence/ART-* acts
 *   blender/<ASSET>/{preview,export,textures,variants,tripo-source}
 *   docs/game-design/07-animation-vfx-audio.csv         — planned sound cues
 * Overview sections (plan, look-dev, material library, decisions, UE layers): see overview.ts.
 * Audio section (docs/game-design/audio, evidence/AUDIO, AUC-* spends): see audio.ts.
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {
  AUDIO_EXTS,
  FileCache,
  csvToObjects,
  isoTime,
  kindFromPath,
  listDirs,
  mdDecision,
  mdListAfterHeading,
  mdTableAfterHeading,
  mdTitle,
  pathTokens,
  shouldSkipDir,
  stripMd,
  walkFiles,
  type WalkEntry,
} from './fs-utils';
import { AUDIO_SOURCES, audioForCharacter, audioRoots, buildAudio } from './audio';
import {
  OVERVIEW_SOURCES,
  buildDecisions,
  buildLookdev,
  buildMaterials,
  buildMentionIndex,
  buildPlan,
  buildUeLayers,
  latestLayerOf,
  newestDate,
  ueTreeFingerprint,
  type OverviewHelpers,
} from './overview';
import { isAllowedRelPath } from './path-guard';
import type {
  ActView,
  ArtHubData,
  AudioOverview,
  AssetPage,
  ClipSection,
  ClipSlotView,
  CreditsOverview,
  CreditsSection,
  DeformProbe,
  FileKind,
  FileRef,
  LayerView,
  LedgerEntry,
  MemberEntry,
  ModelsSection,
  PipelineHealth,
  RecentFile,
  RigSection,
  RunView,
  SoundSection,
  V2MSection,
  V2MSlot,
  V2MStage,
  VideoCueView,
  VideoRefSection,
  VideoSuitability,
  VideoTakeView,
  Vocabulary,
} from './types';

// ---------------------------------------------------------------- constants

export const SOURCES = {
  registry: 'docs/art-pipeline/asset-registry.json',
  animationRefsManifests: 'docs/art-pipeline/animation-refs',
  clipManifest: 'docs/art-pipeline/animation-library/clip-manifest.json',
  clipSchema: 'docs/art-pipeline/animation-library/clip-manifest.schema.json',
  validationSummary: 'docs/art-pipeline/animation-library/validation/summary.json',
  videoToMotion: 'docs/art-pipeline/animation-library/VIDEO-TO-MOTION.md',
  rigContract: 'docs/art-pipeline/rig/rig-contract.json',
  rigContractDoc: 'docs/art-pipeline/rig/RIG-CONTRACT.md',
  ledgerDir: 'docs/art-pipeline/evidence',
  cueTable: 'docs/game-design/07-animation-vfx-audio.csv',
  pipelineCandidates: 'art/pipeline-candidates',
  animationRefs: 'art/animation-refs',
  artPipelineDocs: 'docs/art-pipeline',
  evidence: 'docs/game-design/evidence',
} as const;

/** The hub's own snapshot output; excluded from the watched set to avoid self-reference. */
export const SNAPSHOT_REL = 'docs/art-pipeline/art-hub-snapshot.json';
const CHARACTER_CATEGORIES = new Set(['hero', 'sidekick']);
const BLENDER_SUBDIRS = ['preview', 'export', 'textures', 'variants', 'tripo-source'];
const RUN_META_DIRS = new Set(['source-specs', 'build-profiles', 'scripts', 'tools']);
/** A directory under art/pipeline-candidates/<ASSET>/ counts as a run only with one of these. */
const RUN_MARKER_FILES = ['manifest.json', 'run.json', 'journal.jsonl', 'README.md', 'pipeline/manifest.json', 'reports/tripo-run.json'];
const RUN_MARKER_DIRS = ['export', 'source', 'preview', 'reports', 'textures', 'fixtures', 'pipeline'];
const STANDARD_CLIPS = ['Idle', 'LungeAttack', 'HitReact', 'DeathSettle'];
/** Extra roots searched for audio files (read-only, bounded). */
const SOUND_SCAN_ROOTS = ['art', 'public', 'src', 'scraped-data', 'unreal/Unmatched/Content', 'docs/art-pipeline'];

const FALLBACK_STATUS_VOCAB = [
  'не начато',
  'предложено',
  'измерено',
  'технически импортировано',
  'художественно принято',
];
const FALLBACK_STAGES = [
  'planned',
  'reference-images',
  'blockout',
  'tripo-source',
  'blender-candidate',
  'ue-editor-import',
  'ue-editor-frames',
  'live-packaged-probe',
];

// ---------------------------------------------------------------- json helpers

type J = Record<string, unknown>;
const isObj = (v: unknown): v is J => typeof v === 'object' && v !== null && !Array.isArray(v);
const asObj = (v: unknown): J => (isObj(v) ? v : {});
const asArr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const asStr = (v: unknown): string | undefined =>
  typeof v === 'string' ? v : typeof v === 'number' || typeof v === 'boolean' ? String(v) : undefined;
const asNum = (v: unknown): number | undefined => {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v);
  return undefined;
};
const strList = (v: unknown): string[] => asArr(v).map(asStr).filter((s): s is string => s !== undefined);

function short(v: unknown, max = 160): string | undefined {
  if (v === undefined || v === null) return undefined;
  const s = typeof v === 'string' ? v : JSON.stringify(v);
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

function flatStrings(o: unknown, max = 600): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(asObj(o))) {
    const s = short(v, max);
    if (s !== undefined) out[k] = s;
  }
  return out;
}

function cleanPath(p: string): string {
  return p.replace(/\\/g, '/').split('#')[0]!.replace(/\/+$/, '').replace(/^\.\//, '');
}

/** Nested manifest value as one readable line: `k: v; k2: a; b`. */
function flatText(v: unknown, max = 1200): string | undefined {
  const walk = (x: unknown): string => {
    if (typeof x === 'string') return x;
    if (typeof x === 'number' || typeof x === 'boolean') return String(x);
    if (Array.isArray(x)) return x.map(walk).filter(Boolean).join('; ');
    if (isObj(x)) {
      return Object.entries(x)
        .map(([k, y]) => {
          const s = walk(y);
          return s ? `${k}: ${s}` : '';
        })
        .filter(Boolean)
        .join('; ');
    }
    return '';
  };
  const s = walk(v);
  if (!s) return undefined;
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/**
 * Declared sha256 of every `{ path, sha256 }` object inside a video-refs manifest
 * (clips[], assets[].clips[].takes[], retakes[].takes[]: output, keyframes, input).
 * A path already indexed from another source keeps its value.
 */
function indexManifestShas(ctx: Ctx, v: unknown, depth = 0): void {
  if (depth > 10) return;
  if (Array.isArray(v)) {
    for (const x of v) indexManifestShas(ctx, x, depth + 1);
    return;
  }
  if (!isObj(v)) return;
  const p = asStr(v.path);
  const sha = asStr(v.sha256);
  if (p && sha && /^[0-9a-f]{64}$/i.test(sha)) {
    const key = cleanPath(p);
    if (!ctx.shaIndex.has(key)) ctx.shaIndex.set(key, sha);
  }
  for (const x of Object.values(v)) if (typeof x === 'object' && x !== null) indexManifestShas(ctx, x, depth + 1);
}

/** Primitive fields of an object (all, or the listed keys); long strings are cut. */
function pickPrims(o: J, keys?: string[]): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  for (const k of keys ?? Object.keys(o)) {
    const v = o[k];
    if (typeof v === 'number' && Number.isFinite(v)) out[k] = v;
    else if (typeof v === 'string') out[k] = v.length > 240 ? `${v.slice(0, 239)}…` : v;
  }
  return out;
}

function commonPrefixLen(a: string, b: string): number {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
}

// ---------------------------------------------------------------- context

export interface AggregateOptions {
  /** Verify declared sha256 for files up to this size (bytes). 0 disables. Default 16 MiB. */
  shaMaxBytes?: number;
  /** Extra roots for the sound scan (tests). */
  soundScanRoots?: string[];
}

interface Ctx {
  root: string;
  cache: FileCache;
  warnings: string[];
  files: Map<string, WalkEntry>;
  shaIndex: Map<string, string>;
  shaMaxBytes: number;
  worktreeRoot?: string;
  sourcesMeta: PipelineHealth['sources'];
}

function absOf(ctx: Ctx, rel: string): string {
  return path.join(ctx.root, ...rel.split('/'));
}

function readJson(ctx: Ctx, rel: string, required = false): J | undefined {
  const res = ctx.cache.readJson(absOf(ctx, rel));
  if (res.error) {
    if (res.error !== 'missing') ctx.warnings.push(`Не удалось разобрать ${rel}: ${res.error} (файл, возможно, дописывается)`);
    else if (required) ctx.warnings.push(`Нет файла ${rel}`);
    return undefined;
  }
  if (!isObj(res.value)) {
    ctx.warnings.push(`${rel}: ожидался JSON-объект`);
    return undefined;
  }
  return res.value;
}

function trackSource(ctx: Ctx, rel: string, error?: string) {
  const st = ctx.cache.stat(absOf(ctx, rel));
  ctx.sourcesMeta.push({ path: rel, exists: st.exists, mtime: isoTime(st.mtimeMs), ...(error ? { error } : {}) });
}

interface RefOpts {
  role?: string;
  root?: string;
  kind?: string;
  sha256?: string;
  expect?: string;
  origin?: string;
}

function ueAssetCandidates(p: string): string[] {
  const rest = p.replace(/^\/Game\//, '');
  const base = `unreal/Unmatched/Content/${rest}`;
  return [`${base}.uasset`, `${base}.umap`, base];
}

function makeRef(ctx: Ctx, rawPath: string, o: RefOpts = {}): FileRef {
  const root: FileRef['root'] = o.root === 'art-worktree' ? 'art-worktree' : 'repo';
  const isUe = o.kind === 'ue-asset' || rawPath.startsWith('/Game/');
  const p = isUe ? rawPath : cleanPath(rawPath);
  let kind: FileKind = isUe ? 'ue-asset' : kindFromPath(p);
  let exists: boolean | null = null;
  let bytes: number | undefined;
  let mtimeMs: number | undefined;
  const baseRoot = root === 'repo' ? ctx.root : ctx.worktreeRoot;
  if (baseRoot) {
    const candidates = isUe ? ueAssetCandidates(p) : [p];
    exists = false;
    for (const c of candidates) {
      const st = ctx.cache.stat(path.join(baseRoot, ...c.split('/')));
      if (st.exists) {
        exists = true;
        if (st.isDir && !isUe) kind = 'dir';
        if (st.isFile) {
          bytes = st.bytes;
          mtimeMs = st.mtimeMs;
        }
        break;
      }
    }
  }
  const sha256 = o.sha256 ?? (isUe ? undefined : ctx.shaIndex.get(p));
  let shaCheck: FileRef['shaCheck'];
  if (!sha256) shaCheck = 'not-declared';
  else if (!exists || bytes === undefined || root !== 'repo') shaCheck = exists === false ? 'missing-file' : undefined;
  else if (ctx.shaMaxBytes <= 0 || bytes > ctx.shaMaxBytes) shaCheck = 'skipped-large';
  else {
    const actual = ctx.cache.sha256(absOf(ctx, p));
    shaCheck = actual === undefined ? undefined : actual === sha256.toLowerCase() ? 'match' : 'mismatch';
  }
  const servable = root === 'repo' && !isUe && kind !== 'dir' && exists === true && isAllowedRelPath(p);
  const ref: FileRef = { path: p, root, kind, exists, servable };
  if (o.role) ref.role = o.role;
  if (bytes !== undefined) ref.bytes = bytes;
  if (mtimeMs !== undefined) ref.mtime = isoTime(mtimeMs);
  if (sha256) ref.sha256 = sha256;
  if (shaCheck) ref.shaCheck = shaCheck;
  if (o.expect) ref.expect = o.expect;
  if (o.origin) ref.origin = o.origin;
  return ref;
}

function refFromObj(ctx: Ctx, o: unknown, origin: string): FileRef | undefined {
  const obj = asObj(o);
  const p = asStr(obj.path);
  if (!p) return undefined;
  return makeRef(ctx, p, {
    role: asStr(obj.role),
    root: asStr(obj.root),
    kind: asStr(obj.kind),
    sha256: asStr(obj.sha256),
    expect: asStr(obj.expect),
    origin,
  });
}

function dedupeRefs(refs: FileRef[]): FileRef[] {
  const map = new Map<string, FileRef>();
  for (const r of refs) {
    const key = `${r.root}:${r.path}`;
    const prev = map.get(key);
    if (!prev) map.set(key, r);
    else map.set(key, { ...r, ...prev, role: prev.role ?? r.role, sha256: prev.sha256 ?? r.sha256, shaCheck: prev.shaCheck ?? r.shaCheck });
  }
  return [...map.values()];
}

// ---------------------------------------------------------------- vocabulary

function buildVocab(ctx: Ctx, registry: J | undefined): Vocabulary {
  const vocab = asObj(registry?.vocabularies);
  const statusObj = asObj(vocab.status);
  const status = Object.keys(statusObj).length
    ? Object.entries(statusObj).map(([name, d]) => ({ name, description: asStr(d) ?? '' }))
    : FALLBACK_STATUS_VOCAB.map((name) => ({ name, description: '' }));
  const stage = strList(vocab.stage);
  const clipStatus: Record<string, string> = {
    proposed: 'предложено',
    draft_test: 'черновой тестовый файл',
    measured: 'измерено',
    technically_imported: 'технически импортировано',
    artistically_accepted: 'художественно принято',
    rejected: 'отклонено',
  };
  // Prefer labels from the clip-manifest schema description (project wording).
  const schema = readJson(ctx, SOURCES.clipSchema);
  const desc = asStr(schema?.description) ?? '';
  for (const m of desc.matchAll(/([a-z_]+) \(([^)]+)\)/g)) {
    const key = m[1]!;
    const text = m[2]!.split(',')[0]!.trim();
    const canonical = status.find((s) => text.startsWith(s.name));
    clipStatus[key] = canonical ? canonical.name : text;
  }
  const rej = /rejected\s+—\s+([^.]+)/.exec(desc);
  if (rej) clipStatus.rejected = rej[1]!.includes('отклон') ? 'отклонено' : rej[1]!.trim();
  return {
    status,
    statusRules: strList(vocab.statusRules),
    stage: stage.length ? stage : FALLBACK_STAGES,
    clipStatus,
  };
}

// ---------------------------------------------------------------- registry model

interface RegEntry {
  raw: J;
  id: string;
  name: string;
  category: string;
  parent: string | null;
  status: string | null;
  stage: string | null;
  instances: number;
}

interface PathObj {
  obj: J;
  where: string;
  entryId: string;
}

function parseEntries(registry: J | undefined): RegEntry[] {
  return asArr(registry?.assets)
    .filter(isObj)
    .filter((a) => typeof a.id === 'string')
    .map((a) => ({
      raw: a,
      id: a.id as string,
      name: asStr(a.name) ?? (a.id as string),
      category: asStr(a.category) ?? 'unknown',
      parent: asStr(a.parent) ?? null,
      status: asStr(a.status) ?? null,
      stage: asStr(a.stage) ?? null,
      instances: asNum(a.instances) ?? 1,
    }));
}

function entryPathObjs(e: RegEntry): PathObj[] {
  const out: PathObj[] = [];
  const add = (o: unknown, where: string) => {
    if (isObj(o) && typeof o.path === 'string') out.push({ obj: o, where, entryId: e.id });
  };
  const si = asObj(e.raw.sourceImages);
  add(si.selectionManifest, 'sourceImages.selectionManifest');
  asArr(si.recommended).forEach((o) => add(o, 'sourceImages.recommended'));
  asArr(si.excludedCandidates).forEach((o) => add(o, 'sourceImages.excluded'));
  asArr(e.raw.source3d).forEach((o) => add(o, 'source3d'));
  for (const l of asArr(e.raw.layers).filter(isObj)) {
    asArr(l.paths).forEach((o) => add(o, `layer:${asStr(l.layer) ?? '?'}`));
  }
  asArr(e.raw.evidence).forEach((o) => add(o, 'evidence'));
  asArr(e.raw.acceptanceEvidence).forEach((o) => add(o, 'acceptanceEvidence'));
  asArr(e.raw.plannedPaths).forEach((o) => add(o, 'plannedPaths'));
  return out;
}

function topAncestor(e: RegEntry, byId: Map<string, RegEntry>): RegEntry {
  let cur = e;
  const seen = new Set<string>();
  while (cur.parent && byId.has(cur.parent) && !seen.has(cur.id)) {
    seen.add(cur.id);
    cur = byId.get(cur.parent)!;
  }
  return cur;
}

// ---------------------------------------------------------------- page skeleton

interface PageBuild {
  page: AssetPage;
  entries: RegEntry[];
  pathObjs: PathObj[];
  refPaths: string[];
  charKey?: string;
  files: WalkEntry[];
  runs: RunView[];
}

function emptyModels(): ModelsSection {
  return { sourceImages: [], models: [], previews: [], textures: [], runs: [], evidenceImages: [], evidenceImagesTotal: 0 };
}

function emptyCredits(): CreditsSection {
  return { tripoUnit: 'Studio-кредиты', syntxUnit: 'токены SYNTX', tripoSpent: 0, syntxSpent: 0, entries: [] };
}

function shortNameOf(name: string): string {
  return name.replace(/\s*\(.*$/, '').replace(/,.*$/, '').trim() || name;
}

function newPage(id: string, kind: AssetPage['kind'], e?: RegEntry): AssetPage {
  const raw = e?.raw ?? {};
  return {
    id,
    kind,
    name: e?.name ?? id,
    shortName: shortNameOf(e?.name ?? id),
    category: e?.category ?? (kind === 'character' ? 'hero' : 'prop'),
    inRegistry: Boolean(e),
    instances: e?.instances ?? 1,
    status: e?.status ?? null,
    stage: e?.stage ?? null,
    backlog: strList(raw.backlog),
    parent: e?.parent ?? null,
    group: e?.parent ?? id.split('.')[0]!,
    nextStep: asStr(raw.nextStep),
    blocker: asStr(raw.blocker),
    doneCriteria: asStr(raw.doneCriteria),
    ownership: isObj(raw.ownership) ? flatStrings(raw.ownership) : undefined,
    manifest06: isObj(raw.manifest06) ? flatStrings(raw.manifest06, 2000) : undefined,
    members: [],
    layers: [],
    acts: [],
    reports: [],
    acceptanceEvidence: [],
    statusWarnings: [],
    discoveredNotes: [],
    models: emptyModels(),
    rig: null,
    clips: null,
    videoRefs: null,
    videoToMotion: null,
    sounds: null,
    credits: emptyCredits(),
    ueLayers: null,
  };
}

// ---------------------------------------------------------------- runs

function parseRun(ctx: Ctx, assetDir: string, runId: string, files: WalkEntry[], registryPaths: Set<string>): RunView {
  const dir = `${SOURCES.pipelineCandidates}/${assetDir}/${runId}`;
  const runFiles = files.filter((f) => f.rel.startsWith(`${dir}/`));
  const manifestCandidates = ['manifest.json', 'pipeline/manifest.json', 'run.json', 'reports/tripo-run.json'];
  let manifestRel: string | undefined;
  let manifest: J | undefined;
  for (const c of manifestCandidates) {
    const rel = `${dir}/${c}`;
    if (ctx.cache.stat(absOf(ctx, rel)).isFile) {
      manifest = readJson(ctx, rel);
      manifestRel = rel;
      if (manifest) break;
    }
  }
  const run: RunView = {
    id: runId,
    dir,
    assetDir,
    kind: 'run',
    stages: [],
    reports: [],
    previews: [],
    models: [],
    textures: [],
    otherFiles: 0,
    inRegistry: [...registryPaths].some((p) => p === dir || p.startsWith(`${dir}/`)),
  };
  if (manifest) {
    run.schema = asStr(manifest.schema);
    run.createdAt = asStr(manifest.created_at) ?? asStr(manifest.date) ?? asStr(manifest.created);
    run.toolVersion = asStr(asObj(manifest.tool).version) ?? asStr(manifest.tool_version);
    run.title = asStr(manifest.task) ?? asStr(manifest.title);
    const claims = asObj(manifest.claims);
    if (Object.keys(claims).length) run.claims = flatStrings(claims);
    const credits = manifest.credits_spent_by_this_run ?? manifest.credits_spent ?? manifest.credits;
    if (credits !== undefined) run.credits = short(credits, 120);
    const runPrefix = manifestRel!.slice(0, manifestRel!.lastIndexOf('/'));
    for (const [name, st] of Object.entries(asObj(manifest.stages))) {
      const s = asObj(st);
      const summary = asObj(s.summary);
      run.stages.push({
        name,
        status: asStr(s.status) ?? 'unknown',
        finishedAt: asStr(s.finished_at),
        backend: asStr(s.backend),
        passed: typeof summary.passed === 'boolean' ? summary.passed : undefined,
      });
      for (const [outPath, meta] of Object.entries(asObj(s.outputs))) {
        const sha = asStr(asObj(meta).sha256);
        if (sha) ctx.shaIndex.set(`${runPrefix}/${outPath}`, sha);
      }
    }
    for (const ex of asArr(manifest.exports).filter(isObj)) {
      const p = asStr(ex.path);
      const sha = asStr(ex.sha256);
      if (p && sha) ctx.shaIndex.set(`${runPrefix}/${p}`, sha);
    }
    if (run.schema?.includes('tripo-pipeline')) run.kind = 'tripo-pipeline';
    else if (run.schema?.includes('tripo-run')) run.kind = 'tripo-studio';
    else run.kind = 'manifest';
    run.manifest = makeRef(ctx, manifestRel!, { role: 'манифест прогона', origin: `run:${runId}` });
  }
  const readme = runFiles.find((f) => /\/README\.md$/i.test(f.rel) && f.rel.split('/').length === dir.split('/').length + 1);
  if (readme) {
    run.readme = makeRef(ctx, readme.rel, { role: 'README прогона', origin: `run:${runId}` });
    if (!run.title) run.title = mdTitle(ctx.cache.readText(absOf(ctx, readme.rel), 4096) ?? '');
  }
  let latest = 0;
  for (const f of runFiles) {
    latest = Math.max(latest, f.mtimeMs);
    const sub = f.rel.slice(dir.length + 1);
    const k = kindFromPath(f.rel);
    const origin = `run:${runId}`;
    const base = path.posix.basename(f.rel);
    if (k === 'glb' || k === 'gltf' || k === 'fbx' || k === 'bvh') {
      const folder = sub.split('/')[0];
      run.models.push(makeRef(ctx, f.rel, { role: `${folder === base ? '' : `${folder}/`}${base}`, origin }));
    } else if (k === 'image') {
      if (/(^|\/)textures\//.test(sub) || /^T_/.test(base)) run.textures.push(makeRef(ctx, f.rel, { origin }));
      else run.previews.push(makeRef(ctx, f.rel, { origin }));
    } else if (k === 'json' && /(^|\/)reports\//.test(sub)) {
      run.reports.push(makeRef(ctx, f.rel, { origin }));
    } else if (f.rel !== manifestRel && f.rel !== readme?.rel) {
      run.otherFiles++;
    }
  }
  if (latest) run.lastModified = isoTime(latest);
  // Re-resolve sha for refs created before the manifest indexed them.
  const fix = (r: FileRef) => (r.sha256 ? r : makeRef(ctx, r.path, { role: r.role, origin: r.origin }));
  run.models = run.models.map(fix);
  run.textures = run.textures.map(fix);
  return run;
}

// ---------------------------------------------------------------- main

export class ArtHubAggregator {
  private cache = new FileCache();
  private last?: { fingerprint: string; data: ArtHubData };

  constructor(
    private readonly repoRoot: string,
    private readonly opts: AggregateOptions = {},
  ) {}

  /** Returns fresh data; reuses the previous result when no watched file changed (mtime/size). */
  get(): ArtHubData {
    this.cache.beginRun();
    const started = Date.now();
    const watched = this.walkWatched();
    const audioFiles = this.walkAudio();
    const sounds = this.scanSounds();
    const fp = crypto.createHash('sha1');
    for (const f of watched) fp.update(`${f.rel}\0${f.mtimeMs}\0${f.bytes}\n`);
    for (const f of audioFiles) fp.update(`A${f.rel}\0${f.mtimeMs}\0${f.bytes}\n`);
    for (const s of sounds) fp.update(`S${s}\n`);
    const cueSt = this.cache.stat(path.join(this.repoRoot, ...SOURCES.cueTable.split('/')));
    fp.update(`C${cueSt.mtimeMs ?? 0}:${cueSt.bytes ?? 0}`);
    // UE layer folders are only stat-ed (not walked): two levels of directory mtimes
    fp.update(`U${ueTreeFingerprint(this.repoRoot)}`);
    const fingerprint = fp.digest('hex');
    if (this.last && this.last.fingerprint === fingerprint) {
      return { ...this.last.data, checkedAt: new Date().toISOString() } as ArtHubData;
    }
    const data = build(this.repoRoot, this.cache, watched, audioFiles, sounds, this.opts, fingerprint, started);
    this.last = { fingerprint, data };
    return data;
  }

  private walkWatched(): WalkEntry[] {
    const root = this.repoRoot;
    const out: WalkEntry[] = [];
    out.push(...walkFiles(root, 'art'));
    out.push(...walkFiles(root, SOURCES.artPipelineDocs).filter((f) => f.rel !== SNAPSHOT_REL));
    for (const d of listDirs(root, SOURCES.evidence)) {
      if (/^(ART|GD)-/.test(d)) out.push(...walkFiles(root, `${SOURCES.evidence}/${d}`));
    }
    out.push(...walkFiles(root, OVERVIEW_SOURCES.decisions).filter((f) => /\.md$/i.test(f.rel)));
    for (const asset of listDirs(root, 'blender')) {
      for (const sub of BLENDER_SUBDIRS) out.push(...walkFiles(root, `blender/${asset}/${sub}`));
    }
    return out.filter((f) => !f.rel.endsWith('.pyc'));
  }

  /**
   * Audio docs and evidence (docs/game-design/audio, docs/game-design/evidence/AUDIO). Kept apart from
   * `watched` (recent files, mentions, evidence attribution stay art-only) but part of the fingerprint.
   */
  private walkAudio(): WalkEntry[] {
    return audioRoots().flatMap((r) => walkFiles(this.repoRoot, r));
  }

  /** Paths of audio files in the sound roots (names only; no stat of every file). */
  private scanSounds(): string[] {
    const roots = this.opts.soundScanRoots ?? SOUND_SCAN_ROOTS;
    const found: string[] = [];
    for (const r of roots) findAudio(this.repoRoot, r, found, 0);
    return found.sort();
  }
}

function findAudio(repoRoot: string, rel: string, out: string[], depth: number) {
  if (depth > 12 || out.length > 2000) return;
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(path.join(repoRoot, ...rel.split('/')), { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    if (e.isSymbolicLink()) continue;
    const child = `${rel}/${e.name}`;
    if (e.isDirectory()) {
      if (!shouldSkipDir(e.name)) findAudio(repoRoot, child, out, depth + 1);
    } else if (e.isFile()) {
      const lower = e.name.toLowerCase();
      if (AUDIO_EXTS.some((x) => lower.endsWith(x))) out.push(child);
      else if (lower.endsWith('.uasset') && /^(sw|sc|ms|sfx|a)_/.test(lower) && /\/(audio|sound|sounds|sfx)\//i.test(child)) out.push(child);
    }
  }
}

export function aggregate(repoRoot: string, opts: AggregateOptions = {}): ArtHubData {
  return new ArtHubAggregator(repoRoot, opts).get();
}

function build(
  repoRoot: string,
  cache: FileCache,
  watched: WalkEntry[],
  audioFiles: WalkEntry[],
  soundFiles: string[],
  opts: AggregateOptions,
  fingerprint: string,
  started: number,
): ArtHubData {
  const ctx: Ctx = {
    root: repoRoot,
    cache,
    warnings: [],
    files: new Map(watched.map((f) => [f.rel, f])),
    shaIndex: new Map(),
    shaMaxBytes: opts.shaMaxBytes ?? 16 * 1024 * 1024,
    sourcesMeta: [],
  };

  // ---- sources
  const registry = readJson(ctx, SOURCES.registry, true);
  trackSource(ctx, SOURCES.registry, registry ? undefined : 'нет или не разобран');
  const worktree = asStr(asObj(asObj(registry?.vocabularies).pathRoots)['art-worktree']);
  const wtPath = worktree ? /([A-Za-z]:[\\/][^\s]+)/.exec(worktree)?.[1] : undefined;
  if (wtPath) ctx.worktreeRoot = wtPath;

  const clipManifest = readJson(ctx, SOURCES.clipManifest);
  trackSource(ctx, SOURCES.clipManifest, clipManifest ? undefined : 'нет или не разобран');
  const rigContract = readJson(ctx, SOURCES.rigContract);
  trackSource(ctx, SOURCES.rigContract, rigContract ? undefined : 'нет или не разобран');
  const validationSummary = readJson(ctx, SOURCES.validationSummary);
  trackSource(ctx, SOURCES.validationSummary);
  const v2mText = ctx.cache.readText(absOf(ctx, SOURCES.videoToMotion));
  trackSource(ctx, SOURCES.videoToMotion, v2mText ? undefined : 'нет файла');
  const cueCsv = ctx.cache.readText(absOf(ctx, SOURCES.cueTable), 1024 * 1024);
  trackSource(ctx, SOURCES.cueTable, cueCsv ? undefined : 'нет файла');

  // latest credits ledger under docs/art-pipeline/evidence/*/credits-ledger.json
  const ledgerRel = watched
    .filter((f) => f.rel.startsWith(`${SOURCES.ledgerDir}/`) && f.rel.endsWith('/credits-ledger.json'))
    .sort((a, b) => b.mtimeMs - a.mtimeMs)[0]?.rel;
  const ledger = ledgerRel ? readJson(ctx, ledgerRel) : undefined;
  if (ledgerRel) trackSource(ctx, ledgerRel, ledger ? undefined : 'не разобран');
  else ctx.warnings.push('Не найден журнал кредитов docs/art-pipeline/evidence/*/credits-ledger.json');

  // animation-refs manifests: docs/art-pipeline/animation-refs/*.json + art/animation-refs/<ID>/manifest.json
  const refManifests: { rel: string; data: J }[] = [];
  for (const f of watched) {
    const isDocManifest = f.rel.startsWith(`${SOURCES.animationRefsManifests}/`) && f.rel.endsWith('.json');
    const isAssetManifest = /^art\/animation-refs\/[^/]+\/manifest\.json$/.test(f.rel);
    if (isDocManifest || isAssetManifest) {
      const data = readJson(ctx, f.rel);
      if (data) refManifests.push({ rel: f.rel, data });
      trackSource(ctx, f.rel, data ? undefined : 'не разобран');
    }
  }
  // sha index from manifests: every {path, sha256} pair anywhere in the manifest
  // (clips[], assets[].clips[].takes[], retakes[].takes[], outputs, keyframes, inputs)
  for (const { data } of refManifests) indexManifestShas(ctx, data);
  const clips = asArr(clipManifest?.clips).filter(isObj);
  for (const c of clips) {
    for (const f of asArr(asObj(c.source).files).filter(isObj)) {
      if (asStr(f.path) && asStr(f.sha256)) ctx.shaIndex.set(cleanPath(f.path as string), f.sha256 as string);
    }
  }

  const vocab = buildVocab(ctx, registry);
  const vocabNames = vocab.status.map((s) => s.name);
  const rank = (s: string | null | undefined) => (s ? vocabNames.indexOf(s) : -1);

  // ---- registry entries → pages
  const entries = parseEntries(registry);
  const byId = new Map(entries.map((e) => [e.id, e]));
  const builds = new Map<string, PageBuild>();
  const characterIds: string[] = [];
  const propIds: string[] = [];
  const pageOfEntry = new Map<string, string>();

  for (const e of entries) {
    const top = topAncestor(e, byId);
    if (CHARACTER_CATEGORIES.has(top.category) && top.parent === null) {
      if (!builds.has(top.id)) {
        builds.set(top.id, { page: newPage(top.id, 'character', top), entries: [], pathObjs: [], refPaths: [], files: [], runs: [] });
        characterIds.push(top.id);
      }
      builds.get(top.id)!.entries.push(e);
      pageOfEntry.set(e.id, top.id);
    }
  }
  for (const e of entries) {
    if (pageOfEntry.has(e.id)) continue;
    const top = topAncestor(e, byId);
    const b: PageBuild = { page: newPage(e.id, 'prop', e), entries: [e], pathObjs: [], refPaths: [], files: [], runs: [] };
    b.page.group = top.id === e.id ? (e.parent ?? e.id.split('.')[0]!) : top.id;
    builds.set(e.id, b);
    propIds.push(e.id);
    pageOfEntry.set(e.id, e.id);
  }

  // character keys (clip-manifest "character"), cue prefixes
  const charKeyOf = new Map<string, string>();
  const cuePrefixOf = new Map<string, string>();
  for (const c of clips) {
    const a = asStr(c.asset_id);
    const id = asStr(c.id);
    if (!a) continue;
    if (asStr(c.character) && !charKeyOf.has(a)) charKeyOf.set(a, c.character as string);
    if (id && !cuePrefixOf.has(a)) cuePrefixOf.set(a, id.split('-')[0]!);
  }
  // stub character pages for animation assets missing from the registry
  const animAssetIds = new Set<string>([...charKeyOf.keys(), ...listDirs(repoRoot, SOURCES.animationRefs)]);
  for (const id of animAssetIds) {
    if (!/^ASSET-/.test(id) || builds.has(id) || pageOfEntry.has(id)) continue;
    const b: PageBuild = { page: newPage(id, 'character'), entries: [], pathObjs: [], refPaths: [], files: [], runs: [] };
    b.page.name = charKeyOf.get(id) ?? id;
    b.page.shortName = b.page.name;
    b.page.discoveredNotes.push('Записи в asset-registry.json нет: страница собрана только по файлам на диске.');
    builds.set(id, b);
    characterIds.push(id);
  }
  for (const d of listDirs(repoRoot, SOURCES.animationRefs)) {
    if (cuePrefixOf.has(d)) continue;
    const cueDir = listDirs(repoRoot, `${SOURCES.animationRefs}/${d}`).find((c) => /^[A-Z]{2,5}-[A-Za-z]+/.test(c));
    if (cueDir) cuePrefixOf.set(d, cueDir.split('-')[0]!);
  }

  // registry paths per page
  const allRegistryPaths = new Set<string>();
  for (const b of builds.values()) {
    for (const e of b.entries) b.pathObjs.push(...entryPathObjs(e));
    b.refPaths = b.pathObjs
      .filter((p) => (asStr(p.obj.root) ?? 'repo') === 'repo' && asStr(p.obj.kind) !== 'ue-asset')
      .map((p) => cleanPath(p.obj.path as string));
    b.refPaths.forEach((p) => allRegistryPaths.add(p));
    const id = b.page.id;
    b.charKey = charKeyOf.get(id) ?? (b.page.kind === 'character' ? b.page.shortName.split(' ').pop() : undefined);
    if (b.page.kind === 'character') b.page.cuePrefix = cuePrefixOf.get(id);
  }

  // ---- file attribution
  const characterSet = new Set(characterIds);
  const propPagesByGroupDir = new Map<string, string[]>();
  for (const id of propIds) {
    const b = builds.get(id)!;
    const dirs = new Set<string>([id, b.page.group, id.split('.')[0]!]);
    for (const d of dirs) propPagesByGroupDir.set(d, [...(propPagesByGroupDir.get(d) ?? []), id]);
  }

  function attributeByReference(rel: string, candidates: string[]): string | undefined {
    let best: { id: string; score: number } | undefined;
    const base = path.posix.basename(rel);
    for (const id of candidates) {
      for (const p of builds.get(id)!.refPaths) {
        let score = 0;
        if (p === rel) score = 1_000_000 + p.length;
        else if (rel.startsWith(`${p}/`)) score = 100_000 + p.length;
        else {
          const dir = path.posix.dirname(p);
          if (dir.split('/').length >= 3 && rel.startsWith(`${dir}/`)) score = dir.length * 100 + commonPrefixLen(base, path.posix.basename(p));
        }
        if (score > 0 && (!best || score > best.score)) best = { id, score };
      }
    }
    return best?.id;
  }

  const unassignedRuns: RunView[] = [];
  const pageOfFile = new Map<string, string>();
  for (const f of watched) {
    const parts = f.rel.split('/');
    let pageId: string | undefined;
    if (parts[0] === 'blender' && parts[1]) {
      if (characterSet.has(parts[1])) pageId = parts[1];
      else if (propPagesByGroupDir.has(parts[1])) {
        const cands = propPagesByGroupDir.get(parts[1])!;
        pageId = attributeByReference(f.rel, cands) ?? cands.find((c) => c === parts[1]) ?? (cands.length === 1 ? cands[0] : undefined);
      } else {
        pageId = attributeByReference(f.rel, [...builds.keys()].filter((id) => builds.get(id)!.refPaths.includes(f.rel)));
      }
    } else if (parts[0] === 'art' && (parts[1] === 'animation-refs') && parts[2]) {
      if (builds.has(parts[2]) && characterSet.has(parts[2])) pageId = parts[2];
    }
    if (pageId) {
      pageOfFile.set(f.rel, pageId);
      builds.get(pageId)!.files.push(f);
    }
  }

  // runs
  for (const assetDir of listDirs(repoRoot, SOURCES.pipelineCandidates)) {
    for (const runId of listDirs(repoRoot, `${SOURCES.pipelineCandidates}/${assetDir}`)) {
      if (RUN_META_DIRS.has(runId)) continue;
      const runRel = `${SOURCES.pipelineCandidates}/${assetDir}/${runId}`;
      const isRun =
        RUN_MARKER_FILES.some((m) => ctx.cache.stat(absOf(ctx, `${runRel}/${m}`)).isFile) ||
        RUN_MARKER_DIRS.some((m) => ctx.cache.stat(absOf(ctx, `${runRel}/${m}`)).isDir);
      if (!isRun) continue;
      const run = parseRun(ctx, assetDir, runId, watched, allRegistryPaths);
      let pageId: string | undefined;
      if (characterSet.has(assetDir)) pageId = assetDir;
      else {
        const cands = propPagesByGroupDir.get(assetDir) ?? [];
        const counts = cands
          .map((id) => ({ id, n: builds.get(id)!.refPaths.filter((p) => p === run.dir || p.startsWith(`${run.dir}/`)).length }))
          .filter((x) => x.n > 0)
          .sort((a, b) => b.n - a.n);
        pageId = counts[0]?.id;
        if (!pageId) {
          const lower = runId.toLowerCase();
          pageId = cands.find((id) => {
            const suffix = id.includes('.') ? id.split('.').pop()!.toLowerCase() : '';
            return suffix.length >= 3 && (lower.includes(suffix) || lower.includes(suffix.replace(/s$/, '')));
          });
        }
        if (!pageId && builds.has(assetDir)) pageId = assetDir;
      }
      if (pageId) {
        builds.get(pageId)!.runs.push(run);
        for (const f of watched) if (f.rel.startsWith(`${run.dir}/`)) pageOfFile.set(f.rel, pageId);
      } else unassignedRuns.push(run);
    }
  }

  // evidence folders by backlog id (ART-004 → Medusa …) and pipeline reports by name
  const pagesInOrder = [...characterIds, ...propIds].map((id) => builds.get(id)!);
  // An evidence folder belongs to a page only when its backlog id is unambiguous
  // (ART-004 → Medusa); shared ids (ART-003 blockouts/markers, ART-009 decor) are skipped
  // unless all candidates share one group whose root page carries the id (ART-005 → board).
  const evidenceOwner = new Map<string, PageBuild>();
  const backlogIds = new Set(pagesInOrder.flatMap((b) => b.page.backlog));
  for (const bl of backlogIds) {
    if (!/^ART-/.test(bl)) continue;
    const cands = pagesInOrder.filter((b) => b.page.backlog.includes(bl));
    if (cands.length === 1) evidenceOwner.set(bl, cands[0]!);
    else if (cands.length > 1 && cands.every((c) => c.page.group === cands[0]!.page.group)) {
      const rootPage = cands.find((c) => c.page.id === c.page.group);
      if (rootPage) evidenceOwner.set(bl, rootPage);
    }
  }
  const evidenceImages = new Map<PageBuild, WalkEntry[]>();
  for (const f of watched) {
    const m = /^docs\/game-design\/evidence\/([^/]+)\//.exec(f.rel);
    if (!m) continue;
    const owner = evidenceOwner.get(m[1]!);
    if (!owner) continue;
    if (!pageOfFile.has(f.rel)) pageOfFile.set(f.rel, owner.page.id);
    if (kindFromPath(f.rel) === 'image') evidenceImages.set(owner, [...(evidenceImages.get(owner) ?? []), f]);
  }
  for (const [owner, imgs] of evidenceImages) {
    const refPaths = new Set(owner.refPaths);
    const sorted = imgs.filter((f) => !refPaths.has(f.rel)).sort((x, y) => y.mtimeMs - x.mtimeMs);
    owner.page.models.evidenceImagesTotal = sorted.length;
    owner.page.models.evidenceImages = sorted.slice(0, 48).map((f) => makeRef(ctx, f.rel, { origin: 'evidence' }));
  }
  const reportFiles = watched.filter((f) => /^docs\/art-pipeline\/[^/]+\.(md|json)$/.test(f.rel) && /report/i.test(f.rel));
  for (const b of pagesInOrder) {
    const names = new Set<string>();
    const add = (s: string | undefined) => {
      if (s && s.length >= 4) names.add(s.toLowerCase().replace(/[\s_]+/g, '-'));
    };
    add(b.page.shortName);
    if (b.page.kind === 'character') add(b.charKey);
    add(asStr(b.entries[0]?.raw.contentKey));
    const suffix = b.page.id.includes('.') ? b.page.id.split('.').pop() : undefined;
    add(suffix);
    for (const f of reportFiles) {
      const base = path.posix.basename(f.rel).toLowerCase();
      const referenced = b.refPaths.includes(f.rel);
      if (referenced || [...names].some((n) => base.includes(n) || base.includes(n.replace(/s$/, '')))) {
        b.page.reports.push(makeRef(ctx, f.rel, { role: referenced ? 'в реестре' : 'по имени файла', origin: referenced ? 'registry' : 'scan' }));
        if (!pageOfFile.has(f.rel)) pageOfFile.set(f.rel, b.page.id);
      }
    }
  }

  // ---- ledger
  const ledgerEntries = parseLedger(ledger);
  const attributed = new Set<LedgerEntry>();

  // ---- sound cue table
  const cueRows = cueCsv ? csvToObjects(cueCsv) : [];

  // ---- overview helpers (plan, look-dev, materials, decisions, UE layers)
  const overviewHelpers: OverviewHelpers = {
    root: repoRoot,
    cache,
    watched,
    warnings: ctx.warnings,
    vocabNames,
    makeRef: (p, o) => makeRef(ctx, p, o ?? {}),
    readJson: (rel) => readJson(ctx, rel),
  };
  const mentionIndex = buildMentionIndex(overviewHelpers);

  // ---- audio (overview section + per-character units); AUC-* spends are explained there
  const audio: AudioOverview = buildAudio(overviewHelpers, {
    files: audioFiles,
    soundFiles,
    ledgerRel,
    ledgerEntries,
    syntxUnit: asStr(asObj(ledger?.syntx).unit),
  });
  for (const e of audio.spends.entries) attributed.add(e);
  trackSource(ctx, AUDIO_SOURCES.registry, audio.registry.file.exists ? audio.registry.error : 'нет файла');
  trackSource(ctx, AUDIO_SOURCES.voScript, audio.vo.script.exists ? undefined : 'нет файла');
  trackSource(ctx, AUDIO_SOURCES.productionLog, audio.vo.log.exists ? undefined : 'нет файла');

  // ---- per page sections
  for (const b of builds.values()) {
    const page = b.page;
    // members (children)
    page.members = b.entries
      .filter((e) => e.id !== page.id)
      .map<MemberEntry>((e) => ({
        id: e.id,
        name: e.name,
        category: e.category,
        status: e.status,
        stage: e.stage,
        nextStep: asStr(e.raw.nextStep),
        blocker: asStr(e.raw.blocker),
        doneCriteria: asStr(e.raw.doneCriteria),
        instances: e.instances,
      }));
    // layers
    for (const e of b.entries) {
      for (const l of asArr(e.raw.layers).filter(isObj)) {
        const extra: Record<string, string> = {};
        for (const [k, v] of Object.entries(l)) {
          if (!['layer', 'stage', 'status', 'statusLabel', 'decision', 'owner', 'note', 'paths'].includes(k)) {
            const s = short(v, 1200);
            if (s) extra[k] = s;
          }
        }
        const lv: LayerView = {
          entryId: e.id,
          layer: asStr(l.layer) ?? '?',
          stage: asStr(l.stage),
          status: asStr(l.status),
          statusLabel: asStr(l.statusLabel),
          decision: asStr(l.decision),
          owner: asStr(l.owner),
          note: asStr(l.note),
          files: asArr(l.paths)
            .map((o) => refFromObj(ctx, o, `registry:${e.id}`))
            .filter((r): r is FileRef => Boolean(r)),
        };
        if (Object.keys(extra).length) lv.extra = extra;
        page.layers.push(lv);
        if (lv.status === vocabNames[vocabNames.length - 1]) {
          page.statusWarnings.push(`Слой «${lv.layer}» (${e.id}) имеет статус «${lv.status}», а по правилам реестра слой не может быть художественно принят.`);
        }
        if (lv.status && !vocabNames.includes(lv.status)) page.statusWarnings.push(`Статус слоя «${lv.layer}» вне словаря: «${lv.status}».`);
      }
    }
    // acts & acceptance
    for (const po of b.pathObjs) {
      const p = asStr(po.obj.path)!;
      if (!/\.md$/i.test(p) || !p.startsWith(`${SOURCES.evidence}/`)) continue;
      const file = makeRef(ctx, p, { role: asStr(po.obj.role), origin: `registry:${po.entryId}` });
      const text = file.exists ? ctx.cache.readText(absOf(ctx, file.path), 64 * 1024) : undefined;
      const act: ActView = {
        file,
        title: text ? mdTitle(text) : undefined,
        decision: text ? mdDecision(text) : undefined,
        entryId: po.entryId,
        acceptance: po.where === 'acceptanceEvidence',
      };
      if (!page.acts.some((a) => a.file.path === act.file.path)) page.acts.push(act);
      if (act.acceptance) page.acceptanceEvidence.push(file);
    }
    // status checks
    const accepted = vocabNames[vocabNames.length - 1];
    for (const e of b.entries) {
      if (e.status && !vocabNames.includes(e.status)) page.statusWarnings.push(`Статус ${e.id} вне словаря: «${e.status}».`);
      if (e.status === accepted && asArr(e.raw.acceptanceEvidence).length === 0) {
        page.statusWarnings.push(`${e.id}: статус «${accepted}» без acceptanceEvidence — не считать принятым.`);
      }
      if (e.parent && byId.has(e.parent) && rank(e.status) > rank(byId.get(e.parent)!.status)) {
        page.statusWarnings.push(`${e.id}: статус выше родителя ${e.parent} (нарушение правила реестра).`);
      }
    }

    buildModels(ctx, b);
    if (page.kind === 'character') {
      page.rig = buildRig(ctx, b, rigContract);
      page.clips = buildClips(ctx, b, clips, vocab, clipManifest, validationSummary);
      page.videoRefs = buildVideoRefs(ctx, b, refManifests, ledgerEntries);
      page.videoToMotion = buildV2M(ctx, b, v2mText, vocab);
      page.sounds = buildSounds(ctx, b, soundFiles, cueRows, audio);
    }
    page.credits = buildPageCredits(b, ledgerEntries, attributed);
    page.latestLayer = latestLayerOf(page.layers, page.id, page.status);
    if (page.kind === 'character' && page.inRegistry) {
      page.ueLayers = buildUeLayers(overviewHelpers, {
        assetId: page.id,
        shortName: page.shortName,
        entriesRaw: b.entries.map((e) => e.raw),
        layers: page.layers,
        clips,
        mentions: mentionIndex,
      });
    }
    discoverNotes(b);
    const mt = Math.max(0, ...b.files.map((f) => f.mtimeMs), ...b.runs.map((r) => (r.lastModified ? Date.parse(r.lastModified) : 0)));
    if (mt > 0) page.lastModified = isoTime(mt);
  }

  const characters = characterIds.map((id) => builds.get(id)!.page);
  const props = propIds.map((id) => builds.get(id)!.page);

  // ---- overview
  const credits = buildCreditsOverview(ctx, ledger, ledgerRel, ledgerEntries, attributed);
  const health = buildHealth(ctx, {
    registry,
    entries,
    pageOfEntry,
    builds,
    unassignedRuns,
    watched,
    pageOfFile,
    validationSummary,
    clips,
    vocab,
  });

  const plan = buildPlan(overviewHelpers);
  trackSource(ctx, OVERVIEW_SOURCES.planStatus, plan.exists ? plan.error : 'нет файла (трек plan ещё не записал)');
  const materials = buildMaterials(overviewHelpers);
  trackSource(ctx, OVERVIEW_SOURCES.materialPresets, materials.presets ? undefined : 'нет или не разобран');
  trackSource(ctx, OVERVIEW_SOURCES.materialSources, materials.sources ? undefined : 'нет или не разобран');
  const lookdev = buildLookdev(
    overviewHelpers,
    characters.filter((c) => c.inRegistry).map((c) => ({ id: c.id, shortName: c.shortName })),
  );
  const decisions = buildDecisions(overviewHelpers);

  return {
    schema: 'unmatched.art-hub/1',
    generatedAt: new Date().toISOString(),
    checkedAt: new Date().toISOString(),
    durationMs: Date.now() - started,
    fingerprint,
    vocab,
    characters,
    props,
    credits,
    pipelineHealth: health,
    plan,
    lookdev,
    materials,
    audio,
    decisions,
    warnings: ctx.warnings,
  };
}

// ---------------------------------------------------------------- models

function buildModels(ctx: Ctx, b: PageBuild) {
  const m = b.page.models;
  const si = b.entries.flatMap((e) => {
    const s = asObj(e.raw.sourceImages);
    return [
      ...asArr(s.recommended).map((o) => refFromObj(ctx, o, `registry:${e.id}`)),
      ...asArr(s.excludedCandidates).map((o) => {
        const r = refFromObj(ctx, o, `registry:${e.id}`);
        return r ? { ...r, role: `${r.role ?? ''} (исключён)`.trim() } : undefined;
      }),
    ];
  });
  m.sourceImages = dedupeRefs(si.filter((r): r is FileRef => Boolean(r) && r!.kind === 'image'));

  const models: FileRef[] = [];
  const previews: FileRef[] = [];
  const textures: FileRef[] = [];
  const isModel = (k: FileKind) => k === 'glb' || k === 'gltf' || k === 'fbx' || k === 'bvh';
  const sourceImagePaths = new Set(m.sourceImages.map((r) => r.path));

  for (const po of b.pathObjs) {
    if (po.where.startsWith('sourceImages')) continue;
    const r = refFromObj(ctx, po.obj, `registry:${po.entryId}`);
    if (!r) continue;
    if (isModel(r.kind) && !/\/AM_[^/]+$/.test(r.path)) models.push(r);
    else if (r.kind === 'image' && !sourceImagePaths.has(r.path)) {
      if (/(^|\/)textures\//.test(r.path) || /\/T_[^/]+$/.test(r.path)) textures.push(r);
      else previews.push(r);
    }
  }
  for (const f of b.files) {
    if (!f.rel.startsWith('blender/')) continue;
    const k = kindFromPath(f.rel);
    const base = path.posix.basename(f.rel);
    if (isModel(k) && !/^AM_/.test(base)) models.push(makeRef(ctx, f.rel, { origin: 'scan' }));
    else if (k === 'image') {
      if (/\/textures\//.test(f.rel) || /^T_/.test(base)) textures.push(makeRef(ctx, f.rel, { origin: 'scan' }));
      else previews.push(makeRef(ctx, f.rel, { origin: 'scan' }));
    }
  }
  for (const run of b.runs) {
    models.push(
      ...run.models
        .filter((r) => !/\/AM_[^/]+$/.test(r.path) && r.kind !== 'bvh')
        .map((r) => ({ ...r, role: r.role ? `${run.id}: ${r.role}` : run.id })),
    );
    previews.push(...run.previews.filter((r) => !/\/deform\//.test(r.path)));
    textures.push(...run.textures);
  }
  m.models = dedupeRefs(models);
  m.previews = dedupeRefs(previews).sort((a, b) => (b.mtime ?? '').localeCompare(a.mtime ?? ''));
  m.textures = dedupeRefs(textures);
  m.runs = b.runs.sort((a, b) => (b.lastModified ?? '').localeCompare(a.lastModified ?? ''));

  const servable = m.models.filter((r) => r.servable);
  const glbs = servable.filter((r) => r.kind === 'glb' && (r.bytes ?? 0) < 24 * 1024 * 1024);
  const pick =
    glbs.find((r) => /вход/i.test(r.role ?? '')) ??
    glbs.filter((r) => /retopo/i.test(r.path)).sort((a, b) => (a.bytes ?? 0) - (b.bytes ?? 0))[0] ??
    glbs.sort((a, b) => (a.bytes ?? 0) - (b.bytes ?? 0))[0] ??
    servable.find((r) => r.kind === 'fbx');
  if (pick) m.defaultModel = pick.path;
}

// ---------------------------------------------------------------- rig

function buildRig(ctx: Ctx, b: PageBuild, contract: J | undefined): RigSection {
  const rig: RigSection = {
    bones: [],
    sockets: [],
    extensions: [],
    retargetMaps: [],
    deformProbes: [],
    rigReports: [],
    rigLayers: b.page.layers.filter((l) => /rig|риг/i.test(l.layer)),
  };
  if (contract) {
    rig.contract = makeRef(ctx, SOURCES.rigContract, { role: 'контракт рига (json)' });
    rig.contractDoc = makeRef(ctx, SOURCES.rigContractDoc, { role: 'контракт рига (md)' });
    rig.contractStatus = asStr(contract.status);
    rig.contractStatusNote = asStr(contract.status_note);
    rig.revision = asStr(contract.revision);
    const skeletons = asObj(contract.skeletons);
    const key = b.charKey ?? b.page.shortName;
    const match =
      Object.entries(skeletons).find(([, s]) =>
        strList(asObj(s).applies_to).some((a) => a.startsWith(b.page.id) || (key && a.toLowerCase().startsWith(key.toLowerCase()))),
      ) ?? Object.entries(skeletons)[0];
    if (match) {
      const [skKey, skRaw] = match;
      const sk = asObj(skRaw);
      rig.skeletonKey = skKey;
      rig.appliesTo = strList(sk.applies_to);
      const ao = asObj(sk.armature_object);
      rig.armatureObject = { name: asStr(ao.name), status: asStr(ao.status), rule: asStr(ao.rule), legacyNames: strList(ao.legacy_names) };
      for (const bone of asArr(sk.bones).filter(isObj)) {
        rig.bones.push({ name: asStr(bone.name) ?? '?', parent: asStr(bone.parent) ?? null, role: asStr(bone.role) });
        const byChar = asObj(bone.parent_by_character);
        if (asStr(bone.name) === 'weapon' && key && key in byChar) rig.weaponParent = asStr(byChar[key]) ?? null;
      }
    }
    for (const s of asArr(asObj(contract.ue_import).sockets).filter(isObj)) {
      rig.sockets.push({
        name: asStr(s.name) ?? '?',
        bone: asStr(s.bone),
        offset: asArr(s.offset).map(asNum).filter((n): n is number => n !== undefined),
        note: asStr(s.note),
      });
    }
    for (const [k, v] of Object.entries(asObj(contract.optional_extensions))) {
      rig.extensions.push({ key: k, status: asStr(asObj(v).status), rule: asStr(asObj(v).rule) });
    }
    rig.rootMotion = flatStrings(contract.root_motion);
    const axes = asObj(contract.axes);
    rig.axes = Object.fromEntries(
      Object.entries(axes).map(([k, v]) => [k, typeof v === 'string' ? v : Object.entries(asObj(v)).map(([a, b2]) => `${a}: ${asStr(b2)}`).join(', ')]),
    );
    for (const [k, v] of Object.entries(asObj(contract.retarget_maps))) {
      rig.retargetMaps.push({ key: k, status: asStr(asObj(v).status) });
    }
  }
  for (const run of b.runs) {
    for (const f of ctx.files.values()) {
      if (!f.rel.startsWith(`${run.dir}/`) || !/\/deform\/[^/]+-deform\.json$/.test(f.rel)) continue;
      const data = readJson(ctx, f.rel);
      if (!data) continue;
      const sheetRel = f.rel.replace(/-deform\.json$/, '-sheet.png');
      const probe: DeformProbe = {
        label: asStr(data.label) ?? path.posix.basename(f.rel),
        source: asStr(data.source),
        family: asStr(data.family),
        run: run.id,
        report: makeRef(ctx, f.rel, { origin: `run:${run.id}` }),
        sheet: ctx.files.has(sheetRel) ? makeRef(ctx, sheetRel, { origin: `run:${run.id}` }) : undefined,
        tests: asArr(data.tests)
          .filter(isObj)
          .map((t) => ({ test: asStr(t.test) ?? '?', bone: asStr(t.bone), deg: asNum(t.deg), status: asStr(t.status) ?? '?' })),
      };
      rig.deformProbes.push(probe);
    }
    rig.rigReports.push(...run.reports.filter((r) => /inspect|rig/i.test(path.posix.basename(r.path))));
  }
  return rig;
}

// ---------------------------------------------------------------- clips

function buildClips(
  ctx: Ctx,
  b: PageBuild,
  clips: J[],
  vocab: Vocabulary,
  manifest: J | undefined,
  summary: J | undefined,
): ClipSection {
  const label = (s: string | undefined) => (s ? vocab.clipStatus[s] ?? s : '—');
  const section: ClipSection = {
    manifest: manifest ? makeRef(ctx, SOURCES.clipManifest, { role: 'clip-manifest' }) : undefined,
    revision: asStr(manifest?.revision),
    notes: strList(manifest?.notes),
    slots: [],
    animationFiles: [],
    validationCases: [],
  };
  for (const c of clips.filter((c) => asStr(c.asset_id) === b.page.id)) {
    const src = asObj(c.source);
    const val = asObj(c.validation);
    const reportRel = asStr(val.report);
    const report = reportRel ? makeRef(ctx, reportRel, { role: 'отчёт validate_clip', origin: 'clip-manifest' }) : undefined;
    const checks =
      report?.exists && reportRel
        ? asArr(readJson(ctx, cleanPath(reportRel))?.checks)
            .filter(isObj)
            .map((ch) => ({
              check: asStr(ch.check) ?? '?',
              status: asStr(ch.status) ?? '?',
              note: asStr(ch.note),
              value: short(ch.value ?? ch.max_deviation ?? ch.moving_bones, 80),
            }))
        : [];
    const ue = asObj(c.ue);
    const dur = asObj(c.duration_s);
    const fps = asObj(c.fps);
    const slot: ClipSlotView = {
      id: asStr(c.id) ?? '?',
      clip: asStr(c.clip) ?? '?',
      role: asStr(c.role) ?? '?',
      requiredMvp: c.required_mvp === true,
      status: asStr(c.status) ?? '?',
      statusLabel: label(asStr(c.status)),
      cue: strList(c.cue),
      sourceType: asStr(src.type) ?? 'none',
      sourceTool: asStr(src.tool),
      sourceReference: asStr(src.reference),
      files: asArr(src.files)
        .filter(isObj)
        .filter((f) => Boolean(asStr(f.path)))
        .map((f) => makeRef(ctx, f.path as string, { sha256: asStr(f.sha256), role: asStr(f.format), origin: 'clip-manifest' })),
      license: isObj(c.license) ? flatStrings(c.license) : undefined,
      fpsTarget: asNum(fps.target),
      fpsMeasured: asNum(fps.measured) ?? null,
      durationTarget: (asNum(dur.target) ?? asStr(dur.target)) as number | string | undefined,
      durationTargetStatus: asStr(dur.target_status),
      durationMeasured: asNum(dur.measured) ?? null,
      loop: typeof c.loop === 'boolean' ? c.loop : undefined,
      rootMotion: asStr(c.root_motion),
      skeleton: asStr(asObj(c.skeleton).contract_key),
      ueTargetPath: asStr(ue.target_path),
      ueStatus: asStr(ue.status),
      ueStatusLabel: asStr(ue.status) ? label(asStr(ue.status)) : undefined,
      ueEvidence: asStr(ue.evidence) ? makeRef(ctx, ue.evidence as string, { role: 'доказательство импорта' }) : undefined,
      validation: {
        result: asStr(val.result) ?? 'not_run',
        report,
        fails: strList(val.fails),
        warnings: strList(val.warnings),
        date: asStr(val.date),
        checks,
      },
      notes: asStr(c.notes),
      acceptanceEvidence: asStr(c.acceptance_evidence) ? makeRef(ctx, c.acceptance_evidence as string) : undefined,
    };
    section.slots.push(slot);
    section.animationFiles.push(...slot.files);
  }
  for (const f of b.files) {
    const base = path.posix.basename(f.rel);
    if (/^AM_/.test(base) && ['fbx', 'glb', 'bvh'].includes(kindFromPath(f.rel))) section.animationFiles.push(makeRef(ctx, f.rel, { origin: 'scan' }));
  }
  for (const run of b.runs) section.animationFiles.push(...run.models.filter((r) => /\/AM_|\.bvh$|fixtures\//.test(r.path)));
  section.animationFiles = dedupeRefs(section.animationFiles).filter((r) => r.exists !== false || r.origin === 'clip-manifest');
  const key = (b.charKey ?? '').toLowerCase();
  for (const cs of asArr(summary?.cases).filter(isObj)) {
    const clip = asStr(cs.clip) ?? '';
    const name = asStr(cs.case) ?? '';
    if (!(clip.includes(`/${b.page.id}/`) || (key && name.toLowerCase().includes(`_${key}_`)))) continue;
    section.validationCases.push({
      case: name,
      clip,
      result: asStr(cs.result) ?? '?',
      expectationMet: typeof cs.expectation_met === 'boolean' ? cs.expectation_met : undefined,
      fails: strList(cs.fails),
      warnings: strList(cs.warnings),
      fps: asNum(cs.fps),
      durationS: asNum(cs.duration_s),
    });
  }
  return section;
}

// ---------------------------------------------------------------- video refs

/** A manifest record of one take. A flat clips[] entry (P1 shape) is take 1 of its cue. */
interface TakeRecord {
  n: number;
  rec: J;
  where: string;
}

/** Every manifest record of one cue, merged from clips[], assets[].clips[] and retakes[]. */
interface CueRecord {
  cue: string;
  takes: Map<number, TakeRecord>;
  /** explicit selection (selectedTake, clips[].retakes.selectedTake); later sources win */
  selectedTake?: number;
  requiredMvp?: boolean;
  where: string[];
}

const CUE_DIR = /^[A-Z]{2,5}-[A-Za-z0-9]+/;
const TAKE_DIR = /^take(\d+)$/i;
const CUE_TOKEN = /\b([A-Z]{2,5})-[A-Z][A-Za-z]+/g;
const TOP_BUDGET_KEYS = ['limitSyntxTokens', 'spentSyntxTokens', 'spentStatus', 'balanceEnd', 'clipLimit', 'clipsGenerated', 'note'];

/**
 * Accepts both manifest shapes:
 *  - flat clip (top-level clips[] of P1): the object itself is a take (take 1 unless `take` says otherwise),
 *    `retakes.selectedTake` points at the chosen retake;
 *  - clip with takes[] (assets[].clips[], retakes[]): `selectedTake`, takes[].take / selected.
 */
function ingestCueRecord(into: Map<string, CueRecord>, c: J, where: string): void {
  const cue = asStr(c.cue);
  if (!cue) return;
  let r = into.get(cue);
  if (!r) {
    r = { cue, takes: new Map(), where: [] };
    into.set(cue, r);
  }
  const label = `${where}[${cue}]`;
  if (!r.where.includes(label)) r.where.push(label);
  if (typeof c.requiredMvp === 'boolean') r.requiredMvp = c.requiredMvp;
  const sel = asNum(c.selectedTake) ?? asNum(asObj(c.retakes).selectedTake);
  if (sel !== undefined) r.selectedTake = sel;
  const takes = asArr(c.takes).filter(isObj);
  if (takes.length) {
    takes.forEach((t, i) => {
      const n = asNum(t.take) ?? i + 1;
      r!.takes.set(n, { n, rec: t, where: `${label}.takes[take${n}]` });
    });
  } else if (isObj(c.output) || isObj(c.suitabilityVideoToMotion) || isObj(c.assessment)) {
    const n = asNum(c.take) ?? 1;
    r.takes.set(n, { n, rec: c, where: label });
  }
}

function selectedTakeOf(r: CueRecord): number | undefined {
  if (r.selectedTake !== undefined) return r.selectedTake;
  const flagged = [...r.takes.values()].filter((t) => t.rec.selected === true).map((t) => t.n);
  return flagged.length ? Math.max(...flagged) : undefined;
}

function suitabilityOf(rec: J): VideoSuitability | undefined {
  const s = rec.suitabilityVideoToMotion;
  if (typeof s === 'string') return { verdict: s };
  if (!isObj(s) || !Object.keys(s).length) return undefined;
  return { verdict: asStr(s.verdict), status: asStr(s.status), basis: asStr(s.basis) };
}

function applyTakeRecord(take: VideoTakeView, tr: TakeRecord | undefined, sel: number | undefined): void {
  if (sel !== undefined) take.selected = take.takeNo === sel;
  if (!tr) return;
  const t = tr.rec;
  take.manifestRecord = tr.where;
  take.manifestStatus = asStr(t.status);
  take.suitability = suitabilityOf(t);
  take.briefFit = isObj(t.briefFit) ? (asStr(t.briefFit.text) ?? flatText(t.briefFit, 600)) : flatText(t.briefFit, 600);
  take.whyThisTake = flatText(t.whyThisTake, 600);
  take.motionSummary = flatText(t.motionSummary, 1200);
  if (isObj(t.assessment)) take.assessment = flatStrings(t.assessment, 1200);
  take.briefDeviation = flatText(t.briefDeviation, 1500);
  take.retryProposal = flatText(t.retryProposal, 1500);
}

function stepsOf(ns: unknown): string[] {
  return isObj(ns) ? strList(ns.items) : strList(ns);
}

function buildVideoRefs(ctx: Ctx, b: PageBuild, manifests: { rel: string; data: J }[], ledger: LedgerEntry[]): VideoRefSection {
  const id = b.page.id;
  const section: VideoRefSection = { manifestScopes: [], nextSteps: [], seriesNextSteps: [], cues: [] };
  const base = `${SOURCES.animationRefs}/${id}`;
  const cueDirs = listDirs(ctx.root, base).filter((d) => CUE_DIR.test(d));
  const records = new Map<string, CueRecord>();

  // retakes[] entries carry no assetId today: they belong to this page when their cue does
  const retakeBelongs = (r: J): boolean => {
    if (asStr(r.assetId)) return r.assetId === id;
    const cue = asStr(r.cue);
    if (!cue) return false;
    if (cueDirs.includes(cue) || records.has(cue)) return true;
    if (b.page.cuePrefix && cue.startsWith(`${b.page.cuePrefix}-`)) return true;
    return asArr(r.takes)
      .filter(isObj)
      .some((t) => (asStr(asObj(t.output).path) ?? '').includes(`/${id}/`));
  };

  const seriesSteps: string[] = [];
  for (const m of manifests) {
    const d = m.data;
    const scopes: string[] = [];
    if (asStr(d.assetId) === id || m.rel.includes(`/${id}/`)) {
      for (const c of asArr(d.clips).filter(isObj)) ingestCueRecord(records, c, 'clips');
      scopes.push('верхний уровень (assetId, clips[])');
      section.overallStatus ??= asStr(d.overallStatus);
      const budget = pickPrims(asObj(d.budget), TOP_BUDGET_KEYS);
      if (!section.budget && Object.keys(budget).length) {
        section.budget = budget;
        section.budgetLabel = 'бюджет верхнего уровня манифеста (budget)';
      }
      if (!section.nextSteps.length) section.nextSteps = stepsOf(d.nextSteps);
    }
    const asset = asArr(d.assets)
      .filter(isObj)
      .find((a) => asStr(a.assetId) === id);
    if (asset) {
      for (const c of asArr(asset.clips).filter(isObj)) ingestCueRecord(records, c, `assets[${id}].clips`);
      for (const r of asArr(asset.retakes).filter(isObj)) ingestCueRecord(records, r, `assets[${id}].retakes`);
      scopes.push(`assets[${id}]`);
      section.overallStatus ??= asStr(asset.status);
      const budget = pickPrims(asObj(asset.budget));
      if (!section.budget && Object.keys(budget).length) {
        section.budget = budget;
        section.budgetLabel = `бюджет персонажа (assets[${id}].budget)`;
      }
      if (!section.nextSteps.length) section.nextSteps = stepsOf(asset.nextSteps);
    }
    const retakes = asArr(d.retakes).filter(isObj).filter(retakeBelongs);
    for (const r of retakes) ingestCueRecord(records, r, 'retakes');
    if (retakes.length) scopes.push(`retakes[] (${retakes.map((r) => asStr(r.cue) ?? '?').join(', ')})`);
    if (!scopes.length) continue;

    if (!section.manifest) section.manifest = makeRef(ctx, m.rel, { role: 'манифест видео-референсов' });
    const own = section.manifest.path === m.rel;
    section.manifestScopes.push(...scopes.map((s) => (own ? s : `${m.rel}: ${s}`)));
    const all = pickPrims(asObj(d.budgetAll));
    if (!section.budgetAll && Object.keys(all).length) section.budgetAll = all;
    seriesSteps.push(...stepsOf(asObj(d.heroSeries).nextSteps));
  }

  // series-wide steps: keep general ones and those naming this character's cues
  const prefixes = new Set<string>([...cueDirs, ...records.keys()].map((c) => c.split('-')[0]!));
  if (b.page.cuePrefix) prefixes.add(b.page.cuePrefix);
  for (const s of seriesSteps) {
    const named = [...s.matchAll(CUE_TOKEN)].map((x) => x[1]!);
    if ((!named.length || named.some((p) => prefixes.has(p))) && !section.nextSteps.includes(s) && !section.seriesNextSteps.includes(s)) {
      section.seriesNextSteps.push(s);
    }
  }

  const cues = new Set<string>([...cueDirs, ...records.keys()]);
  for (const cue of [...cues].sort(cueOrder)) {
    const dir = `${base}/${cue}`;
    const rec = records.get(cue);
    const sel = rec ? selectedTakeOf(rec) : undefined;
    const cv: VideoCueView = { cue, takes: [], manifestRecords: rec?.where ?? [] };
    if (rec) {
      const recs = [...rec.takes.values()].sort((x, y) => x.n - y.n);
      cv.requiredMvp = rec.requiredMvp;
      cv.cueRef = recs.map((t) => asStr(t.rec.cueRef)).find(Boolean);
      if (sel !== undefined) cv.selectedTake = `take${sel}`;
      const verdictRec = sel !== undefined ? rec.takes.get(sel) : recs.length === 1 ? recs[0] : undefined;
      if (verdictRec) {
        cv.manifestStatus = asStr(verdictRec.rec.status);
        const s = suitabilityOf(verdictRec.rec);
        if (s) {
          cv.suitability = s;
          cv.suitabilityFrom = sel !== undefined ? `take${sel} — выбранный дубль` : `take${verdictRec.n} — единственный дубль с записью`;
        } else {
          cv.suitabilityNote = `в записи take${verdictRec.n} нет оценки пригодности (suitabilityVideoToMotion)`;
        }
      } else if (sel !== undefined) {
        cv.suitabilityNote = `в манифесте выбран take${sel}, но записи этого дубля нет`;
      } else if (recs.length > 1) {
        cv.suitabilityNote = 'выбранный дубль в манифесте не указан — оценки по дублям ниже';
      } else {
        cv.suitabilityNote = 'в записи манифеста нет ни одного дубля с оценкой';
      }
      cv.manifestStatus ??= recs.map((t) => asStr(t.rec.status)).find(Boolean);
    }

    const takeDirs = [
      { n: 1, dir },
      ...listDirs(ctx.root, dir)
        .map((d) => ({ d, m: TAKE_DIR.exec(d) }))
        .filter((x) => x.m)
        .map((x) => ({ n: Number(x.m![1]), dir: `${dir}/${x.d}` })),
    ];
    const seen = new Set<number>();
    for (const td of takeDirs) {
      if (seen.has(td.n)) continue;
      const own = [...ctx.files.values()].filter((f) => path.posix.dirname(f.rel) === td.dir);
      const kf = [...ctx.files.values()].filter((f) => path.posix.dirname(f.rel) === `${td.dir}/keyframes` && kindFromPath(f.rel) === 'image');
      const video = own.find((f) => kindFromPath(f.rel) === 'video');
      const sheet = own.find((f) => /contact-sheet/i.test(f.rel) && kindFromPath(f.rel) === 'image');
      const prompt = own.find((f) => /prompt\.txt$/i.test(f.rel));
      const analysis = own.find((f) => /analysis\.json$/i.test(f.rel));
      if (!video && !sheet && !prompt && !analysis && kf.length === 0) continue;
      seen.add(td.n);
      const take: VideoTakeView = {
        take: `take${td.n}`,
        takeNo: td.n,
        dir: td.dir,
        keyframes: kf.sort((x, y) => x.rel.localeCompare(y.rel)).map((f) => makeRef(ctx, f.rel)),
      };
      if (video) take.video = makeRef(ctx, video.rel, { role: 'видео-референс' });
      if (sheet) take.contactSheet = makeRef(ctx, sheet.rel, { role: 'контакт-лист' });
      if (prompt) {
        take.promptFile = makeRef(ctx, prompt.rel);
        take.prompt = ctx.cache.readText(absOf(ctx, prompt.rel), 8 * 1024)?.trim();
      }
      if (analysis) {
        take.analysisFile = makeRef(ctx, analysis.rel, { role: 'замеры analyze_video_ref.py' });
        const sum = asObj(readJson(ctx, analysis.rel)?.summary);
        const a: Record<string, string | number> = {};
        for (const k of ['frames', 'width', 'height', 'border_mad_max', 'base_center_x_range_px', 'base_bottom_y_range_px', 'motion_mad_max']) {
          const v = sum[k];
          if (typeof v === 'number' || typeof v === 'string') a[k] = v;
        }
        if (Array.isArray(sum.fg_touches_edge_frames)) a.fg_touches_edge_frames = sum.fg_touches_edge_frames.length;
        if (Object.keys(a).length) take.analysis = a;
      }
      const lm = Math.max(0, ...own.map((f) => f.mtimeMs));
      if (lm) take.lastModified = isoTime(lm);
      const tr = rec?.takes.get(td.n);
      applyTakeRecord(take, tr, sel);
      // model + cost: ledger entry whose ref points at this take dir, else the take's manifest record
      const le = ledger.find((e) => e.service === 'syntx' && e.ref && cleanPath(e.ref) === td.dir);
      if (le) {
        take.model = le.model;
        take.cost = { tokens: -le.delta, balanceBefore: le.balanceBefore, balanceAfter: le.balanceAfter, source: 'credits-ledger' };
      }
      if (tr) applyRecordModelCost(take, tr.rec);
      if (!take.model && video) {
        const m = /_(kling\d+|seedance[0-9a-z]+|hailuo[0-9a-z]*|veo[0-9a-z]*|wan[0-9a-z]*|runway[0-9a-z]*)_/i.exec(video.rel);
        if (m) take.model = `${m[1]} (по имени файла)`;
      }
      cv.takes.push(take);
    }
    // takes described in the manifest whose folder was not found (moved, not synced yet)
    for (const tr of rec?.takes.values() ?? []) {
      if (seen.has(tr.n)) continue;
      const outPath = asStr(asObj(tr.rec.output).path);
      const take: VideoTakeView = {
        take: `take${tr.n}`,
        takeNo: tr.n,
        dir: outPath ? path.posix.dirname(cleanPath(outPath)) : tr.n === 1 ? dir : `${dir}/take${tr.n}`,
        keyframes: asArr(tr.rec.keyframes)
          .filter(isObj)
          .map((k) => asStr(k.path))
          .filter((p): p is string => !!p)
          .map((p) => makeRef(ctx, p))
          .filter((r) => r.exists),
      };
      if (outPath) {
        const ref = makeRef(ctx, outPath, { role: 'видео-референс' });
        if (ref.exists) take.video = ref;
        else take.missingVideo = ref.path;
      }
      const sheet = asStr(tr.rec.contactSheet);
      if (sheet) {
        const ref = makeRef(ctx, sheet, { role: 'контакт-лист' });
        if (ref.exists) take.contactSheet = ref;
      }
      applyTakeRecord(take, tr, sel);
      applyRecordModelCost(take, tr.rec);
      cv.takes.push(take);
    }
    cv.takes.sort((x, y) => x.takeNo - y.takeNo);
    section.cues.push(cv);
  }
  return section;
}

/** Model label and cost from a take's manifest record, where the ledger gave none. */
function applyRecordModelCost(take: VideoTakeView, rec: J): void {
  if (!take.model) {
    const params = asObj(rec.parameters);
    take.model =
      asStr(rec.modelLabel) ??
      ([asStr(rec.service), asStr(params.version) ? `v${params.version}` : undefined, asStr(params.mode)].filter(Boolean).join(' ') || undefined);
  }
  if (!take.cost) {
    const cost = asObj(rec.cost);
    const tokens = asNum(cost.syntxTokens);
    if (tokens !== undefined || asNum(cost.balanceBefore) !== undefined) {
      take.cost = { tokens, balanceBefore: asNum(cost.balanceBefore), balanceAfter: asNum(cost.balanceAfter), source: 'манифест' };
    }
  }
}

/** «Пригодность …» line for the video→skeleton reference stage. */
function suitabilityLine(vc: VideoCueView): string {
  if (vc.suitability) {
    const from = vc.suitabilityFrom ? ` (${vc.suitabilityFrom})` : '';
    const st = vc.manifestStatus ? `; статус: ${vc.manifestStatus}` : '';
    return `Пригодность${from}: ${vc.suitability.verdict ?? '—'}${st}`;
  }
  const perTake = vc.takes.filter((t) => t.suitability?.verdict).map((t) => `${t.take} — ${t.suitability!.verdict}`);
  if (perTake.length) return `Пригодность по дублям (${vc.suitabilityNote ?? 'выбранный дубль не указан'}): ${perTake.join('; ')}`;
  if (vc.manifestRecords.length) return `Пригодность: ${vc.suitabilityNote ?? 'в записи манифеста нет оценки'}`;
  return 'Пригодность: не оценивалась (записи в манифесте видео-референсов нет)';
}

function cueOrder(a: string, b: string): number {
  const ia = STANDARD_CLIPS.findIndex((c) => a.endsWith(`-${c}`));
  const ib = STANDARD_CLIPS.findIndex((c) => b.endsWith(`-${c}`));
  return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
}

// ---------------------------------------------------------------- video → skeleton

function buildV2M(ctx: Ctx, b: PageBuild, doc: string | undefined, vocab: Vocabulary): V2MSection {
  const section: V2MSection = { dependencies: [], recommendation: [], slots: [] };
  if (doc) {
    section.doc = makeRef(ctx, SOURCES.videoToMotion, { role: 'VIDEO-TO-MOTION.md' });
    const table = mdTableAfterHeading(doc, /^##\s*6\b/);
    for (const row of table.slice(1)) {
      section.dependencies.push({
        dependency: stripMd(row[0] ?? ''),
        neededFor: stripMd(row[1] ?? ''),
        status: stripMd(row[2] ?? ''),
        who: stripMd(row[3] ?? ''),
      });
    }
    section.recommendation = mdListAfterHeading(doc, /^##\s*5\b/).map((s) => (s.length > 260 ? `${s.slice(0, 259)}…` : s));
    const harpy = doc.split(/\r?\n/).find((l) => /Harpy/.test(l) && /не применим/.test(l));
    if (harpy) section.harpyNote = stripMd(harpy);
  }
  const isHarpy = /HARPY/i.test(b.page.id) || /harpy/i.test(b.charKey ?? '');
  const cuePrefix = b.page.cuePrefix;
  const slots = b.page.clips?.slots.filter((s) => s.role === 'production') ?? [];
  const tests = b.page.clips?.slots.filter((s) => s.role === 'test') ?? [];
  const slotList: { cue: string; clip: string; slot?: ClipSlotView }[] = slots.length
    ? slots.map((s) => ({ cue: s.id, clip: s.clip, slot: s }))
    : cuePrefix
      ? STANDARD_CLIPS.map((c) => ({ cue: `${cuePrefix}-${c}`, clip: c }))
      : [];
  const openDeps = section.dependencies.filter((d) => /не |нет|отложено/i.test(d.status));
  for (const { cue, clip, slot } of slotList) {
    const vc = b.page.videoRefs?.cues.find((c) => c.cue === cue);
    const takesWithVideo = vc?.takes.filter((t) => t.video) ?? [];
    const stages: V2MStage[] = [];
    stages.push({
      key: 'reference',
      label: 'Видео-референс',
      state: takesWithVideo.length ? 'done' : vc?.takes.length ? 'partial' : 'not-started',
      detail: takesWithVideo.length
        ? `${takesWithVideo.length} ролик(ов): ${takesWithVideo.map((t) => `${t.take}${t.selected ? ' (выбран)' : ''}${t.model ? ` — ${t.model}` : ''}`).join('; ')}. ${suitabilityLine(vc!)}`
        : vc?.takes.length
          ? 'есть только промпт/материалы без ролика'
          : 'ролика нет',
    });
    const srcType = slot?.sourceType ?? 'none';
    const srcFilesOk = (slot?.files ?? []).some((f) => f.exists);
    const testClip = tests.find((t) => t.clip === clip);
    let extraction: V2MStage;
    if (isHarpy && srcType === 'none') {
      extraction = { key: 'extraction', label: 'Извлечение движения', state: 'n/a', detail: section.harpyNote ?? 'video-to-motion для крыльев не применим; клипы вручную' };
    } else if (srcType !== 'none') {
      extraction = {
        key: 'extraction',
        label: 'Извлечение движения',
        state: srcFilesOk ? 'done' : 'partial',
        detail: `источник: ${srcType}${slot?.sourceTool ? ` (${slot.sourceTool})` : ''}${srcFilesOk ? '' : ' — файл не найден'}`,
      };
    } else {
      extraction = {
        key: 'extraction',
        label: 'Извлечение движения',
        state: 'not-started',
        detail: `не начато (source.type = none)${testClip ? `; есть только тестовый клип ${testClip.id} (${testClip.statusLabel}, ${testClip.sourceType}) — не из видео` : ''}`,
      };
    }
    stages.push(extraction);
    const manualHarpy = isHarpy && srcType === 'none';
    const retargetDone = Boolean(slot?.skeleton) && srcFilesOk && (slot?.sourceType === 'blender_keyframed' || Boolean(slot?.validation.result === 'pass'));
    stages.push(
      manualHarpy
        ? { key: 'retarget', label: 'Ретаргет на скелет', state: 'n/a', detail: 'не нужен: клипы Harpy авторятся вручную прямо на скелете контракта' }
        : {
            key: 'retarget',
            label: 'Ретаргет на скелет',
            state: retargetDone ? 'done' : 'not-started',
            detail: retargetDone ? `скелет ${slot?.skeleton}` : `не выполнен (цель: ${slot?.skeleton ?? 'UM_HUMANOID_17_v1'})`,
          },
    );
    const vr = slot?.validation.result ?? 'not_run';
    stages.push({
      key: 'validation',
      label: 'Валидация validate_clip',
      state: vr === 'pass' ? 'done' : vr === 'fail' ? 'partial' : 'not-started',
      detail: vr === 'not_run' ? 'не запускалась' : `${vr}${slot?.validation.warnings.length ? `, предупреждения: ${slot.validation.warnings.join(', ')}` : ''}`,
    });
    const ueDone = slot?.ueStatus === 'technically_imported' || slot?.ueStatus === 'artistically_accepted';
    stages.push({
      key: 'ue',
      label: 'Импорт в UE',
      state: ueDone ? 'done' : 'not-started',
      detail: slot?.ueStatus ? `${vocab.clipStatus[slot.ueStatus] ?? slot.ueStatus}${slot.ueTargetPath ? ` → ${slot.ueTargetPath}` : ''}` : 'нет данных',
    });
    const current = stages.find((s) => s.state !== 'done' && s.state !== 'n/a');
    let blocker = 'Технические этапы пройдены; художественная приёмка — только актом.';
    if (manualHarpy) {
      blocker = `${section.harpyNote ?? 'Harpy: video-to-motion не применим, клипы вручную.'} Ручного клипа в слоте нет (source.type = none).`;
    } else if (current) {
      if (current.key === 'reference') blocker = `Нет видео-референса для ${cue}.`;
      else if (current.key === 'extraction')
        blocker = `Инструмент video-to-motion не выбран/не установлен${openDeps.length ? `: ${openDeps.map((d) => `${d.dependency} — ${d.status} (решает: ${d.who})`).slice(0, 3).join('; ')}` : ''}. Источник: VIDEO-TO-MOTION.md §5–6.`;
      else if (current.key === 'retarget') blocker = 'Ретаргет на скелет контракта не выполнен (VIDEO-TO-MOTION.md §4).';
      else if (current.key === 'validation') blocker = 'validate_clip.py для слота не запускался или дал fail.';
      else blocker = 'Импорт клипа в UE не выполнен.';
    } else if (stages.some((s) => s.state === 'n/a') && isHarpy) {
      blocker = section.harpyNote ?? 'Harpy: клипы вручную.';
    }
    section.slots.push({
      cue,
      clip,
      requiredMvp: slot?.requiredMvp ?? true,
      slotStatus: slot?.status,
      slotStatusLabel: slot?.statusLabel,
      stages,
      currentStage: manualHarpy ? 'Ручная анимация (не начата)' : current?.label ?? 'все технические этапы',
      blocker,
    } satisfies V2MSlot);
  }
  return section;
}

// ---------------------------------------------------------------- sounds

function buildSounds(ctx: Ctx, b: PageBuild, soundFiles: string[], cueRows: Record<string, string>[], audio: AudioOverview): SoundSection {
  const id = b.page.id.toLowerCase();
  const key = (b.charKey ?? b.page.shortName).toLowerCase();
  const prefix = b.page.cuePrefix ? `${b.page.cuePrefix.toLowerCase()}-` : undefined;
  const files = soundFiles
    .filter((f) => {
      const l = f.toLowerCase();
      return l.includes(id) || (key.length >= 4 && l.includes(key)) || (prefix !== undefined && path.posix.basename(l).startsWith(prefix));
    })
    .map((f) => makeRef(ctx, f, { role: 'звук', origin: 'scan' }));
  const slotCues = new Set((b.page.clips?.slots ?? []).flatMap((s) => s.cue).filter((c) => /^CUE-/.test(c)));
  const cues = cueRows
    .filter((r) => r.cueId && (slotCues.has(r.cueId) || new RegExp(`\\b${escapeRe(b.charKey ?? b.page.shortName)}\\b`, 'i').test(`${r.triggerCondition} ${r.object} ${r.animation} ${r.vfx}`)))
    .map((r) => ({
      cueId: r.cueId!,
      event: r.event ?? '',
      sound: r.sound ?? '',
      durationMs: r.durationMs,
      object: r.object,
      via: slotCues.has(r.cueId!) ? 'слот клипа' : 'упоминание персонажа',
    }));
  return {
    status: files.length ? null : 'не начато',
    files,
    cues,
    cueSource: makeRef(ctx, SOURCES.cueTable, { role: 'таблица CUE 07' }),
    searchedRoots: SOUND_SCAN_ROOTS,
    ...audioForCharacter(audio, b.charKey ?? b.page.shortName),
  };
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ---------------------------------------------------------------- credits

function parseLedger(ledger: J | undefined): LedgerEntry[] {
  if (!ledger) return [];
  const out: LedgerEntry[] = [];
  const push = (service: LedgerEntry['service'], window: LedgerEntry['window'], e: J) => {
    const delta = asNum(e.delta);
    if (delta === undefined) return;
    out.push({
      service,
      window,
      time: asStr(e.historyTime) ?? asStr(e.observedAt) ?? asStr(e.time),
      op: asStr(e.op) ?? (asStr(e.cue) ? `генерация ${e.cue}` : undefined),
      delta,
      owner: asStr(e.owner),
      ref: asStr(e.ref),
      cue: asStr(e.cue),
      asset: asStr(e.asset),
      model: asStr(e.model),
      balanceBefore: asNum(e.balanceBefore),
      balanceAfter: asNum(e.balanceAfter),
      note: asStr(e.note),
    });
  };
  const tripo = asObj(ledger.tripo);
  asArr(asObj(tripo.preWindow).entries).filter(isObj).forEach((e) => push('tripo', 'pre', e));
  asArr(asObj(tripo.window).entries).filter(isObj).forEach((e) => push('tripo', 'window', e));
  const syntx = asObj(ledger.syntx);
  asArr(asObj(syntx.preWindow).entries).filter(isObj).forEach((e) => push('syntx', 'pre', e));
  asArr(asObj(syntx.window).entries).filter(isObj).forEach((e) => push('syntx', 'window', e));
  return out;
}

function buildPageCredits(b: PageBuild, ledger: LedgerEntry[], attributed: Set<LedgerEntry>): CreditsSection {
  const c = emptyCredits();
  const id = b.page.id;
  const ids = new Set(b.entries.map((e) => e.id).concat(id));
  const prefix = b.page.cuePrefix ? `${b.page.cuePrefix}-` : undefined;
  const runDirs = b.runs.map((r) => r.dir);
  for (const e of ledger) {
    const tokens = pathTokens(e.ref);
    const hit =
      (e.asset && ids.has(e.asset)) ||
      (prefix && e.cue?.startsWith(prefix)) ||
      [...ids].some((x) => (e.ref ?? '').includes(x) || (e.owner ?? '').includes(x)) ||
      tokens.some((t) => b.refPaths.includes(t) || runDirs.some((d) => t === d || t.startsWith(`${d}/`)));
    if (!hit) continue;
    c.entries.push(e);
    attributed.add(e);
    if (e.delta < 0) {
      if (e.service === 'tripo') c.tripoSpent += -e.delta;
      else c.syntxSpent += -e.delta;
    }
  }
  c.entries.sort((a, b) => (a.time ?? '').localeCompare(b.time ?? ''));
  return c;
}

function buildCreditsOverview(ctx: Ctx, ledger: J | undefined, rel: string | undefined, entries: LedgerEntry[], attributed: Set<LedgerEntry>): CreditsOverview {
  const tripo = asObj(ledger?.tripo);
  const tw = asObj(tripo.window);
  const syntx = asObj(ledger?.syntx);
  const sw = asObj(syntx.window);
  const pre = asObj(tripo.preWindow);
  const syntxEntries = entries.filter((e) => e.service === 'syntx');
  const lastSyntx = [...syntxEntries].reverse().find((e) => e.balanceAfter !== undefined);
  return {
    ledger: rel ? makeRef(ctx, rel, { role: 'единый журнал кредитов' }) : undefined,
    status: asStr(ledger?.status),
    tripo: {
      unit: asStr(tripo.unit) ?? 'Studio-кредиты',
      plan: asStr(tripo.plan),
      balanceStart: asNum(tw.balanceStart),
      balanceEnd: asNum(tw.balanceEndUi) ?? asNum(tw.balanceEnd),
      spent: asNum(tw.spent),
      limit: asNum(tw.limit),
      remaining: asNum(tw.remaining),
      preWindowSpent: (asNum(pre.spentArt004) ?? 0) + (asNum(pre.spentUnattributed) ?? 0),
      byTask: Object.entries(asObj(tw.byTask)).map(([task, v]) => ({ task, credits: asNum(v) ?? 0 })),
      limitNote: asStr(tw.limitNote),
    },
    syntx: {
      unit: asStr(syntx.unit) ?? 'токены SYNTX',
      plan: asStr(syntx.plan),
      balanceStart: asNum(sw.balanceStart),
      balanceEnd: asNum(sw.balanceEnd) ?? lastSyntx?.balanceAfter,
      spent: asNum(sw.spent),
      limit: asNum(sw.limit),
      remaining: asNum(sw.remaining),
      limitNote: asStr(sw.limitNote),
    },
    recent: entries
      .filter((e) => e.delta < 0)
      .map((e, i) => ({ e, i }))
      .sort((a, b) => (b.e.time ?? '').localeCompare(a.e.time ?? '') || b.i - a.i)
      .slice(0, 15)
      .map((x) => x.e),
    unattributed: entries.filter((e) => e.delta < 0 && !attributed.has(e)),
  };
}

// ---------------------------------------------------------------- discovered notes

function discoverNotes(b: PageBuild) {
  const page = b.page;
  const unregisteredRuns = b.runs.filter((r) => !r.inRegistry);
  for (const r of unregisteredRuns) {
    page.discoveredNotes.push(
      `На диске есть прогон ${r.id} (${r.models.length} моделей, ${r.previews.length} превью${r.createdAt ? `, ${r.createdAt}` : ''}), которого нет в asset-registry.json — реестр ещё не обновлён${page.stage ? ` (стадия в реестре: ${page.stage})` : ''}.`,
    );
  }
  const vr = page.videoRefs;
  if (vr && vr.cues.some((c) => c.takes.some((t) => t.video)) && !page.layers.some((l) => /animation-refs|видео/i.test(l.layer))) {
    const n = vr.cues.reduce((s, c) => s + c.takes.filter((t) => t.video).length, 0);
    page.discoveredNotes.push(`Найдено видео-референсов: ${n}; слоя видео-референсов в реестре нет.`);
  }
  if (vr && !vr.manifest && vr.cues.some((c) => c.takes.some((t) => t.video))) {
    page.discoveredNotes.push('Для роликов этого персонажа нет манифеста видео-референсов — пригодность не оценена.');
  } else if (vr?.manifest) {
    const unrecorded = vr.cues.flatMap((c) => c.takes.filter((t) => t.video && !t.manifestRecord).map((t) => `${c.cue} ${t.take}`));
    if (unrecorded.length) {
      page.discoveredNotes.push(
        `Ролики без записи в ${vr.manifest.path} (пригодность не оценена): ${unrecorded.join(', ')} — манифест ещё не обновлён.`,
      );
    }
  }
}

// ---------------------------------------------------------------- health

function buildHealth(
  ctx: Ctx,
  a: {
    registry: J | undefined;
    entries: RegEntry[];
    pageOfEntry: Map<string, string>;
    builds: Map<string, PageBuild>;
    unassignedRuns: RunView[];
    watched: WalkEntry[];
    pageOfFile: Map<string, string>;
    validationSummary: J | undefined;
    clips: J[];
    vocab: Vocabulary;
  },
): PipelineHealth {
  const byStatus = new Map<string, number>();
  const byStage = new Map<string, number>();
  for (const e of a.entries) {
    byStatus.set(e.status ?? '—', (byStatus.get(e.status ?? '—') ?? 0) + 1);
    byStage.set(e.stage ?? '—', (byStage.get(e.stage ?? '—') ?? 0) + 1);
  }
  const order = a.vocab.status.map((s) => s.name);
  const runs: PipelineHealth['runs'] = [];
  for (const [pageId, b] of a.builds) for (const r of b.runs) runs.push({ ...r, page: pageId });
  runs.push(...a.unassignedRuns);
  runs.sort((x, y) => (y.lastModified ?? '').localeCompare(x.lastModified ?? ''));

  const recentFiles: RecentFile[] = [...a.watched]
    .sort((x, y) => y.mtimeMs - x.mtimeMs)
    .slice(0, 40)
    .map((f) => ({
      path: f.rel,
      mtime: isoTime(f.mtimeMs)!,
      bytes: f.bytes,
      page: a.pageOfFile.get(f.rel),
      servable: isAllowedRelPath(f.rel),
      kind: kindFromPath(f.rel),
    }));

  const cases = asArr(a.validationSummary?.cases).filter(isObj);
  const clipCoverage = new Map<string, { assetId: string; character: string; required: number; filled: number; total: number }>();
  for (const c of a.clips) {
    if (asStr(c.role) !== 'production') continue;
    const id = asStr(c.asset_id) ?? '?';
    const row = clipCoverage.get(id) ?? { assetId: id, character: asStr(c.character) ?? id, required: 0, filled: 0, total: 0 };
    row.total++;
    if (c.required_mvp === true) row.required++;
    if (asStr(c.status) !== 'proposed' || asStr(asObj(c.source).type) !== 'none') row.filled++;
    clipCoverage.set(id, row);
  }

  const reports = a.watched
    .filter((f) => /^docs\/art-pipeline\/[^/]+-report\.(md|json)$/.test(f.rel))
    .map((f) => makeRef(ctx, f.rel, { role: 'отчёт пайплайна' }));

  const missing: PipelineHealth['missingReferenced'] = [];
  for (const e of a.entries) {
    for (const po of entryPathObjs(e)) {
      if (asStr(po.obj.expect) !== 'exists') continue;
      const r = refFromObj(ctx, po.obj, `registry:${e.id}`);
      if (r && r.exists === false) missing.push({ entryId: e.id, path: r.path, role: r.role });
    }
  }

  return {
    registry: {
      file: makeRef(ctx, SOURCES.registry, { role: 'реестр ассетов' }),
      snapshotDate: asStr(a.registry?.snapshotDate),
      fileMtime: isoTime(ctx.cache.stat(absOf(ctx, SOURCES.registry)).mtimeMs),
      latestLayerDate: newestDate(
        a.entries.flatMap((e) =>
          asArr(e.raw.layers)
            .filter(isObj)
            .flatMap((l) => [asStr(l.layer), ...asArr(l.paths).map((p) => asStr(asObj(p).path))]),
        ),
      ),
      total: a.entries.length,
      byStatus: [...byStatus.entries()]
        .map(([status, count]) => ({ status, count }))
        .sort((x, y) => order.indexOf(x.status) - order.indexOf(y.status)),
      byStage: [...byStage.entries()].map(([stage, count]) => ({ stage, count })),
      entries: a.entries.map((e) => ({
        id: e.id,
        name: e.name,
        status: e.status,
        stage: e.stage,
        page: a.pageOfEntry.get(e.id) ?? e.id,
        nextStep: asStr(e.raw.nextStep),
        blocker: asStr(e.raw.blocker),
      })),
    },
    runs,
    recentFiles,
    validation: {
      file: a.validationSummary ? makeRef(ctx, SOURCES.validationSummary, { role: 'сводка validate_clip' }) : undefined,
      pass: cases.filter((c) => c.result === 'pass').length,
      fail: cases.filter((c) => c.result === 'fail').length,
      expectationMet: cases.filter((c) => c.expectation_met === true).length,
      total: cases.length,
    },
    clipCoverage: [...clipCoverage.values()],
    reports,
    missingReferenced: missing.slice(0, 80),
    sources: ctx.sourcesMeta,
  };
}
