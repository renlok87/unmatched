/**
 * Overview sections of the art hub that are not tied to a single registry
 * entry: plan status, look-dev + concepts, material library, decision logs,
 * and per-hero UE layers (/Game/PipelineCandidates/<Folder>/<Layer>).
 *
 * Everything is read-only. Statuses are copied verbatim; UE paths are shown as
 * text (the unreal/ tree is only stat-ed, never served).
 *
 * Sources:
 *   docs/art-pipeline/plan-status.json                       — plan track (unmatched-plan-status/v1)
 *   docs/art-pipeline/<hero>-lookdev*.md                     — look-dev reports
 *   art/imagegen/hero-quality-v1/<hero>/*                    — concepts (front/side/back, prompts.md)
 *   art/pipeline-candidates/<ASSET>/<run>/review/<iter>/*-lookdev-sheet-*.jpg — UE sheets «концепт | UE»
 *   art/pipeline-candidates/<ASSET>/<run>/preview/{ld_sheet_*,compare-ld-*,ld_concept_zones_*} — Blender sheets
 *   docs/art-pipeline/material-library/{*.md,um-material-presets-v1.json,sources.json,evidence/}
 *   art/material-library/v1/{tiles/<class>/*.png,preview/tiles-sheet.png}
 *   docs/game-design/decisions/*.md                          — decision logs
 *   unreal/Unmatched/Content/PipelineCandidates/<Folder>/<Layer>/ — existence + .uasset count only
 */
import fs from 'node:fs';
import path from 'node:path';
import { FileCache, kindFromPath, mdTitle, stripMd, type WalkEntry } from './fs-utils';
import type {
  DecisionView,
  DocView,
  FileRef,
  LatestLayerView,
  LayerView,
  LookdevHeroView,
  LookdevOverview,
  LookdevSheet,
  MaterialLibraryView,
  MaterialSetView,
  PlanTaskView,
  PlanView,
  UeLayerView,
  UeLayersSection,
} from './types';

export const OVERVIEW_SOURCES = {
  planStatus: 'docs/art-pipeline/plan-status.json',
  conceptRoot: 'art/imagegen/hero-quality-v1',
  materialLibrary: 'docs/art-pipeline/material-library',
  materialPresets: 'docs/art-pipeline/material-library/um-material-presets-v1.json',
  materialSources: 'docs/art-pipeline/material-library/sources.json',
  materialTiles: 'art/material-library/v1/tiles',
  materialTilesSheet: 'art/material-library/v1/preview/tiles-sheet.png',
  decisions: 'docs/game-design/decisions',
  ueContent: 'unreal/Unmatched/Content',
  uePipelineCandidates: 'unreal/Unmatched/Content/PipelineCandidates',
} as const;

/** Standard hero layers in UE, in pipeline order. */
export const STANDARD_UE_LAYERS = ['H2', 'H2LD', 'H3LD', 'Rig', 'H2Anim'] as const;

type J = Record<string, unknown>;
const isObj = (v: unknown): v is J => typeof v === 'object' && v !== null && !Array.isArray(v);
const asObj = (v: unknown): J => (isObj(v) ? v : {});
const asArr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const asStr = (v: unknown): string | undefined =>
  typeof v === 'string' ? v : typeof v === 'number' || typeof v === 'boolean' ? String(v) : undefined;
const asNum = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined);
const strList = (v: unknown): string[] => asArr(v).map(asStr).filter((s): s is string => s !== undefined);
const cut = (s: string | undefined, max: number): string | undefined =>
  s === undefined ? undefined : s.length > max ? `${s.slice(0, max - 1)}…` : s;

export interface OverviewHelpers {
  root: string;
  cache: FileCache;
  watched: WalkEntry[];
  warnings: string[];
  vocabNames: string[];
  makeRef: (p: string, o?: { role?: string; origin?: string }) => FileRef;
  readJson: (rel: string) => J | undefined;
}

function abs(h: OverviewHelpers, rel: string): string {
  return path.join(h.root, ...rel.split('/'));
}

/** Absolute or drive paths (C:/tmp/…) are outside the repo: shown as text only. */
function isOutsideRepo(p: string): boolean {
  return /^[A-Za-z]:[\\/]/.test(p) || p.startsWith('/') || p.startsWith('\\\\') || p.split(/[\\/]/).includes('..');
}

/** FileRef for a repo path, or a text-only ref for a path outside the repo. */
export function refOrText(h: OverviewHelpers, p: string, role?: string): FileRef {
  if (isOutsideRepo(p)) return { path: p.replace(/\\/g, '/'), root: 'repo', kind: kindFromPath(p), exists: null, servable: false, role: role ?? 'вне репозитория' };
  return h.makeRef(p, { role });
}

// ---------------------------------------------------------------- dates

const DATE_RE = /(?<!\d)(20\d{2})-?(0[1-9]|1[0-2])-?([0-2]\d|3[01])(?!\d)/g;

/** Newest YYYY-MM-DD found in the given strings (run ids 20260929-…, ISO dates). */
export function newestDate(texts: (string | undefined)[]): string | undefined {
  let best: string | undefined;
  for (const t of texts) {
    if (!t) continue;
    for (const m of t.matchAll(DATE_RE)) {
      const d = `${m[1]}-${m[2]}-${m[3]}`;
      if (!best || d > best) best = d;
    }
  }
  return best;
}

// ---------------------------------------------------------------- latest layer

/**
 * Freshest layer of an entry: the newest date in the layer name or its paths,
 * ties (and layers without a date) resolved by the later position in layers[].
 */
export function latestLayerOf(layers: LayerView[], entryId: string, entryStatus: string | null): LatestLayerView | undefined {
  let best: { l: LayerView; date?: string; index: number } | undefined;
  layers
    .filter((l) => l.entryId === entryId)
    .forEach((l, index) => {
      const date = newestDate([l.layer, ...l.files.map((f) => f.path)]);
      const better = !best || (date ?? '') > (best.date ?? '') || ((date ?? '') === (best.date ?? '') && index > best.index);
      if (better) best = { l, date, index };
    });
  if (!best) return undefined;
  const b = best as { l: LayerView; date?: string; index: number };
  return { entryId, layer: b.l.layer, status: b.l.status, stage: b.l.stage, date: b.date, index: b.index, entryStatus };
}

// ---------------------------------------------------------------- docs

export function docView(h: OverviewHelpers, rel: string, role?: string): DocView {
  const file = h.makeRef(rel, { role });
  const text = file.exists ? h.cache.readText(abs(h, rel), 64 * 1024) : undefined;
  const headings: string[] = [];
  let statusLine: string | undefined;
  let date = newestDate([path.posix.basename(rel)]);
  if (text) {
    let inFence = false;
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (line.startsWith('```')) inFence = !inFence;
      if (inFence) continue;
      const hm = /^##\s+(.+)$/.exec(line);
      if (hm && headings.length < 40) headings.push(cut(stripMd(hm[1]!), 140)!);
      if (!statusLine && /^(\*\*)?Дата:?(\*\*)?\s*/.test(line)) {
        statusLine = cut(stripMd(line), 400);
        date ??= newestDate([line]);
      }
    }
  }
  return { file, title: text ? mdTitle(text) : undefined, date, statusLine, headings };
}

// ---------------------------------------------------------------- plan

export function buildPlan(h: OverviewHelpers): PlanView {
  const rel = OVERVIEW_SOURCES.planStatus;
  const file = h.makeRef(rel, { role: 'статус плана (трек plan)' });
  const view: PlanView = { file, exists: file.exists === true, sources: [], tasks: [], waves: [], statusCounts: [] };
  if (!view.exists) return view;
  const res = h.cache.readJson(abs(h, rel));
  if (res.error || !isObj(res.value)) {
    view.error = res.error ?? 'ожидался JSON-объект';
    h.warnings.push(`Не удалось разобрать ${rel}: ${view.error} (файл, возможно, дописывается)`);
    return view;
  }
  const d = res.value;
  view.schema = asStr(d.schema);
  view.generated = asStr(d.generated);
  view.head = asStr(d.head);
  if (view.schema && !/^unmatched-plan-status\//.test(view.schema)) {
    h.warnings.push(`${rel}: неизвестная схема «${view.schema}» — показано как есть`);
  }
  for (const s of asArr(d.sources).filter(isObj)) {
    const p = asStr(s.path);
    view.sources.push({
      id: asStr(s.id) ?? p ?? '?',
      path: p ?? '',
      title: asStr(s.title),
      file: p ? refOrText(h, p, asStr(s.title)) : undefined,
    });
  }
  const accepted = h.vocabNames[h.vocabNames.length - 1];
  const counts = new Map<string, number>();
  for (const t of asArr(d.tasks).filter(isObj)) {
    const id = asStr(t.id) ?? '?';
    const status = asStr(t.status) ?? '—';
    const artStatus = asStr(t.art_status) ?? null;
    const evidence = strList(t.evidence).map((p) => refOrText(h, p));
    const warnings: string[] = [];
    if (artStatus && h.vocabNames.length && !h.vocabNames.includes(artStatus)) warnings.push(`арт-статус «${artStatus}» вне словаря реестра`);
    if (artStatus && artStatus === accepted && !evidence.some((e) => /^docs\/game-design\/evidence\/(ART|GD)-/.test(e.path) && /\.md$/i.test(e.path) && e.exists)) {
      warnings.push(`«${accepted}» без акта приёмки docs/game-design/evidence/(ART|GD)-…/*.md — не считать принятым`);
    }
    const missing = evidence.filter((e) => e.exists === false).map((e) => e.path);
    if (missing.length) warnings.push(`нет файлов доказательств: ${missing.slice(0, 5).join(', ')}${missing.length > 5 ? ` и ещё ${missing.length - 5}` : ''}`);
    const task: PlanTaskView = {
      id,
      title: asStr(t.title) ?? id,
      track: asStr(t.track),
      source: asStr(t.source),
      status,
      artStatus,
      evidence,
      next: asStr(t.next),
      blocker: asStr(t.blocker) ?? null,
      assets: strList(t.assets),
      updated: asStr(t.updated),
      warnings,
    };
    view.tasks.push(task);
    counts.set(status, (counts.get(status) ?? 0) + 1);
  }
  const order = ['in_progress', 'blocked', 'open', 'done', 'superseded'];
  view.statusCounts = [...counts.entries()]
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => (order.indexOf(a.status) + 1 || 99) - (order.indexOf(b.status) + 1 || 99));
  for (const w of asArr(d.waves).filter(isObj)) {
    view.waves.push({ id: asStr(w.id) ?? '?', title: asStr(w.title), status: asStr(w.status), tasks: strList(w.tasks) });
  }
  return view;
}

// ---------------------------------------------------------------- decisions

export function buildDecisions(h: OverviewHelpers): DecisionView[] {
  const prefix = `${OVERVIEW_SOURCES.decisions}/`;
  const out: DecisionView[] = [];
  for (const f of h.watched) {
    if (!f.rel.startsWith(prefix) || !/\.md$/i.test(f.rel) || f.rel.slice(prefix.length).includes('/')) continue;
    const dv: DecisionView = docView(h, f.rel, 'журнал решений');
    const text = h.cache.readText(abs(h, f.rel), 64 * 1024);
    const origin = text
      ?.split(/\r?\n/)
      .map((l) => l.trim())
      .find((l) => /^\*\*Происхождение\.?\*\*/.test(l) || /^Происхождение[.:]/.test(l));
    if (origin) dv.origin = cut(stripMd(origin), 500);
    out.push(dv);
  }
  return out.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.file.path.localeCompare(b.file.path));
}

// ---------------------------------------------------------------- material library

export function buildMaterials(h: OverviewHelpers): MaterialLibraryView {
  const root = OVERVIEW_SOURCES.materialLibrary;
  const view: MaterialLibraryView = { root, docs: [], classes: [], sets: [], procedural: [], evidenceGroups: [], evidenceImages: [], evidenceTotal: 0 };
  for (const f of h.watched) {
    if (f.rel.startsWith(`${root}/`) && /\.md$/i.test(f.rel) && !f.rel.slice(root.length + 1).includes('/')) view.docs.push(docView(h, f.rel));
  }
  view.docs.sort((a, b) => (/README\.md$/i.test(a.file.path) ? -1 : /README\.md$/i.test(b.file.path) ? 1 : a.file.path.localeCompare(b.file.path)));

  const presets = h.readJson(OVERVIEW_SOURCES.materialPresets);
  if (presets) {
    view.presets = {
      file: h.makeRef(OVERVIEW_SOURCES.materialPresets, { role: 'пресеты классов' }),
      version: asStr(presets.version),
      date: asStr(presets.date),
      status: asStr(presets.status),
    };
  }
  const sources = h.readJson(OVERVIEW_SOURCES.materialSources);
  const setsByClass = new Map<string, string[]>();
  const proceduralByClass = new Map<string, string>();
  if (sources) {
    for (const s of asArr(sources.sets).filter(isObj)) {
      const license = asStr(s.license);
      const set: MaterialSetView = {
        id: asStr(s.id) ?? '?',
        status: asStr(s.status),
        class: asStr(s.class) ?? null,
        license,
        page: asStr(s.page),
        reason: cut(asStr(s.reason), 600),
        cc0: /\bCC0\b/i.test(license ?? ''),
      };
      view.sets.push(set);
      if (set.class) setsByClass.set(set.class, [...(setsByClass.get(set.class) ?? []), set.id]);
    }
    for (const p of asArr(sources.procedural).filter(isObj)) {
      const cls = asStr(p.class) ?? '?';
      view.procedural.push({ class: cls, generator: asStr(p.generator), reason: cut(asStr(p.reason), 600) });
      if (asStr(p.generator)) proceduralByClass.set(cls, asStr(p.generator)!);
    }
    view.sources = {
      file: h.makeRef(OVERVIEW_SOURCES.materialSources, { role: 'CC0-наборы и лицензии' }),
      note: cut(asStr(sources.note), 800),
      licenseNote: cut(asStr(sources.licenseNote), 800),
      allCC0: view.sets.length > 0 && view.sets.every((s) => s.cc0),
    };
    const notCc0 = view.sets.filter((s) => !s.cc0).map((s) => s.id);
    if (notCc0.length) h.warnings.push(`material-library/sources.json: наборы без лицензии CC0: ${notCc0.join(', ')}`);
  }

  const tilesByClass = new Map<string, FileRef[]>();
  const tilePrefix = `${OVERVIEW_SOURCES.materialTiles}/`;
  for (const f of h.watched) {
    if (!f.rel.startsWith(tilePrefix) || kindFromPath(f.rel) !== 'image') continue;
    const cls = f.rel.slice(tilePrefix.length).split('/')[0]!;
    tilesByClass.set(cls, [...(tilesByClass.get(cls) ?? []), h.makeRef(f.rel, { role: `тайл ${cls}` })]);
  }
  const addClass = (c: J, extension: boolean) => {
    const id = asStr(c.id);
    if (!id) return;
    const bc = asObj(c.baseColor);
    const typical = asArr(bc.typicalLinear).map(asNum).filter((n): n is number => n !== undefined);
    view.classes.push({
      index: asNum(c.index),
      id,
      nameRu: asStr(c.nameRu),
      family: asStr(c.family),
      metallic: asNum(c.metallic),
      shadingModel: asStr(c.shadingModel),
      baseColorLinear: typical.length === 3 ? typical : undefined,
      roughness: asNum(asObj(c.roughness).typical),
      teamDyeAllowed: c.teamDyeAllowed === undefined ? undefined : cut(typeof c.teamDyeAllowed === 'object' ? JSON.stringify(c.teamDyeAllowed) : asStr(c.teamDyeAllowed), 200),
      extension,
      sets: setsByClass.get(id) ?? [],
      procedural: proceduralByClass.get(id),
      tiles: tilesByClass.get(id) ?? [],
    });
  };
  asArr(presets?.classes).filter(isObj).forEach((c) => addClass(c, false));
  asArr(presets?.extensionClasses).filter(isObj).forEach((c) => addClass(c, true));

  const sheet = h.makeRef(OVERVIEW_SOURCES.materialTilesSheet, { role: 'контактный лист тайлов' });
  if (sheet.exists) view.tilesSheet = sheet;

  const evPrefix = `${root}/evidence/`;
  const groups = new Map<string, number>();
  const images: WalkEntry[] = [];
  for (const f of h.watched) {
    if (!f.rel.startsWith(evPrefix)) continue;
    const parts = f.rel.slice(evPrefix.length).split('/');
    const group = parts.length > 2 ? `${parts[0]}/${parts[1]}` : parts[0]!;
    groups.set(group, (groups.get(group) ?? 0) + 1);
    if (kindFromPath(f.rel) === 'image') images.push(f);
  }
  view.evidenceGroups = [...groups.entries()].map(([group, count]) => ({ group, count })).sort((a, b) => a.group.localeCompare(b.group));
  view.evidenceTotal = images.length;
  const sheetFirst = (f: WalkEntry) => (/sheet/i.test(path.posix.basename(f.rel)) ? 0 : 1);
  view.evidenceImages = images
    .sort((a, b) => sheetFirst(a) - sheetFirst(b) || b.mtimeMs - a.mtimeMs)
    .slice(0, 36)
    .map((f) => h.makeRef(f.rel, { origin: 'material-library' }));
  return view;
}

// ---------------------------------------------------------------- look-dev + concepts

/** ASSET-KING-ARTHUR-001 → king-arthur */
export function heroSlug(assetId: string): string {
  return assetId.replace(/^ASSET-/, '').replace(/-\d+$/, '').toLowerCase();
}

const UE_SHEET_RE = /^art\/pipeline-candidates\/([^/]+)\/([^/]+)\/review\/([^/]+)\/[^/]*lookdev-sheet[^/]*\.(jpg|jpeg|png)$/i;
const BLENDER_SHEET_RE = /^art\/pipeline-candidates\/([^/]+)\/([^/]+)\/preview\/((ld_sheet|compare-ld|ld_concept_zones)[^/]*)\.(jpg|jpeg|png)$/i;

export function buildLookdev(h: OverviewHelpers, pages: { id: string; shortName: string }[]): LookdevOverview {
  const conceptRoot = OVERVIEW_SOURCES.conceptRoot;
  const conceptFiles = h.watched.filter((f) => f.rel.startsWith(`${conceptRoot}/`));
  const conceptDirs = new Set(conceptFiles.map((f) => f.rel.slice(conceptRoot.length + 1).split('/')[0]!).filter((d) => d && d !== 'reference'));
  const view: LookdevOverview = {
    conceptRoot,
    references: conceptFiles
      .filter((f) => f.rel.startsWith(`${conceptRoot}/reference/`) && kindFromPath(f.rel) === 'image')
      .map((f) => h.makeRef(f.rel, { role: 'эталон качества' })),
    heroes: [],
  };
  const keys = new Map<string, { name: string; pageId?: string }>();
  for (const p of pages) keys.set(heroSlug(p.id), { name: p.shortName, pageId: p.id });
  for (const d of conceptDirs) if (!keys.has(d)) keys.set(d, { name: d });

  const ueSheets = new Map<string, LookdevSheet[]>();
  const blenderSheets = new Map<string, LookdevSheet[]>();
  const mtimeOf = new Map(h.watched.map((f) => [f.rel, f.mtimeMs]));
  for (const f of h.watched) {
    const u = UE_SHEET_RE.exec(f.rel);
    if (u) {
      const key = heroSlug(u[1]!);
      ueSheets.set(key, [...(ueSheets.get(key) ?? []), { run: u[2]!, iteration: u[3]!, file: h.makeRef(f.rel, { role: `${u[2]} · ${u[3]}` }) }]);
      continue;
    }
    const b = BLENDER_SHEET_RE.exec(f.rel);
    if (b) {
      const key = heroSlug(b[1]!);
      blenderSheets.set(key, [...(blenderSheets.get(key) ?? []), { run: b[2]!, iteration: 'preview', file: h.makeRef(f.rel, { role: `${b[2]} · ${b[3]}` }) }]);
    }
  }
  const newestFirst = (a: LookdevSheet, b: LookdevSheet) =>
    b.run.localeCompare(a.run) || (mtimeOf.get(b.file.path) ?? 0) - (mtimeOf.get(a.file.path) ?? 0) || b.iteration.localeCompare(a.iteration);

  for (const [key, meta] of keys) {
    const tokens = [key, ...key.split('-')].filter((t) => t.length >= 4);
    const concepts = conceptFiles
      .filter((f) => f.rel.startsWith(`${conceptRoot}/${key}/`) && kindFromPath(f.rel) === 'image')
      .map((f) => h.makeRef(f.rel, { role: `концепт ${path.posix.basename(f.rel).replace(/\.[^.]+$/, '')}` }));
    const promptsRel = `${conceptRoot}/${key}/prompts.md`;
    const docs = h.watched
      .filter((f) => new RegExp(`^docs/art-pipeline/${key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}-lookdev[^/]*\\.md$`, 'i').test(f.rel))
      .map((f) => docView(h, f.rel, 'отчёт look-dev'));
    const evidenceSheets = h.watched
      .filter((f) => {
        const m = /^docs\/art-pipeline\/evidence\/([^/]+)\//.exec(f.rel);
        return m && tokens.some((t) => m[1]!.toLowerCase().includes(t)) && /sheet/i.test(f.rel) && kindFromPath(f.rel) === 'image';
      })
      .sort((a, b) => b.mtimeMs - a.mtimeMs)
      .slice(0, 24)
      .map((f) => h.makeRef(f.rel, { origin: 'evidence' }));
    const hero: LookdevHeroView = {
      key,
      name: meta.name,
      pageId: meta.pageId,
      concepts,
      conceptPrompts: mtimeOf.has(promptsRel) ? h.makeRef(promptsRel, { role: 'промпты концепта' }) : undefined,
      docs,
      ueSheets: (ueSheets.get(key) ?? []).sort(newestFirst),
      blenderSheets: (blenderSheets.get(key) ?? []).sort(newestFirst),
      evidenceSheets,
    };
    const empty = !concepts.length && !docs.length && !hero.ueSheets.length && !hero.blenderSheets.length && !evidenceSheets.length;
    if (!empty) view.heroes.push(hero);
  }
  return view;
}

// ---------------------------------------------------------------- UE layers

const UE_PATH_RE = /\/Game\/PipelineCandidates\/([A-Za-z0-9_]+)\/([A-Za-z0-9_-]+)/g;
const MENTION_FILE_RES = [
  /^docs\/art-pipeline\/.+\.md$/i,
  /^docs\/game-design\/decisions\/[^/]+\.md$/i,
  /^art\/pipeline-candidates\/[^/]+\/[^/]+\/[^/]+\.(json|md)$/i,
  /^art\/pipeline-candidates\/[^/]+\/[^/]+\/reports\/[^/]+\.json$/i,
  /^art\/pipeline-candidates\/[^/]+\/build-profiles\/[^/]+\.json$/i,
];
const MENTION_EXCLUDE = new Set(['docs/art-pipeline/asset-registry.json', 'docs/art-pipeline/animation-library/clip-manifest.json']);

/** `Folder/Layer` → files that mention /Game/PipelineCandidates/Folder/Layer. */
export type MentionIndex = Map<string, { files: string[]; runs: Set<string> }>;

export function buildMentionIndex(h: OverviewHelpers): MentionIndex {
  const index: MentionIndex = new Map();
  for (const f of h.watched) {
    if (MENTION_EXCLUDE.has(f.rel) || !MENTION_FILE_RES.some((re) => re.test(f.rel))) continue;
    const keys = h.cache.derive(abs(h, f.rel), 'ue-paths', (text) => [...new Set([...text.matchAll(UE_PATH_RE)].map((m) => `${m[1]}/${m[2]}`))]);
    if (!keys?.length) continue;
    const parts = f.rel.split('/');
    // art/pipeline-candidates/<ASSET>/<run>/… → run id (build-profiles are not runs)
    const run = parts[0] === 'art' && parts.length >= 5 && parts[3] !== 'build-profiles' ? parts[3] : undefined;
    for (const k of keys) {
      const slot = index.get(k) ?? { files: [], runs: new Set<string>() };
      slot.files.push(f.rel);
      if (run) slot.runs.add(run);
      index.set(k, slot);
    }
  }
  return index;
}

function countUassets(dir: string, depth = 0, acc = { n: 0 }): number {
  if (depth > 6 || acc.n > 5000) return acc.n;
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return acc.n;
  }
  for (const e of entries) {
    if (e.isSymbolicLink()) continue;
    if (e.isDirectory()) countUassets(path.join(dir, e.name), depth + 1, acc);
    else if (e.isFile() && /\.(uasset|umap)$/i.test(e.name)) acc.n++;
  }
  return acc.n;
}

/** Most frequent /Game/PipelineCandidates/<Folder>/ in the given texts. */
function detectFolder(texts: string[]): string | undefined {
  const counts = new Map<string, number>();
  for (const t of texts) for (const m of t.matchAll(UE_PATH_RE)) counts.set(m[1]!, (counts.get(m[1]!) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
}

export function buildUeLayers(
  h: OverviewHelpers,
  a: { assetId: string; shortName: string; entriesRaw: J[]; layers: LayerView[]; clips: J[]; mentions: MentionIndex },
): UeLayersSection {
  const clips = a.clips.filter((c) => asStr(c.asset_id) === a.assetId);
  const clipPaths = clips.map((c) => asStr(asObj(c.ue).target_path)).filter((s): s is string => Boolean(s));
  let folder = detectFolder(a.entriesRaw.map((e) => JSON.stringify(e)));
  let folderSource = 'реестр';
  if (!folder) {
    folder = detectFolder(clipPaths);
    folderSource = 'clip-manifest';
  }
  if (!folder) {
    folder = a.shortName.replace(/[^A-Za-z0-9]/g, '');
    folderSource = 'по имени персонажа';
  }
  const contentRoot = abs(h, OVERVIEW_SOURCES.ueContent);
  const ueRoot = abs(h, `${OVERVIEW_SOURCES.uePipelineCandidates}/${folder}`);
  const ueProject = h.cache.stat(contentRoot).isDir;
  let onDiskDirs: string[] = [];
  if (ueProject) {
    try {
      onDiskDirs = fs.readdirSync(ueRoot, { withFileTypes: true }).filter((e) => e.isDirectory() && !e.isSymbolicLink()).map((e) => e.name);
    } catch {
      onDiskDirs = [];
    }
  }
  const esc = (v: string) => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const layerRe = (key: string) => new RegExp(`/Game/PipelineCandidates/${esc(folder)}/${esc(key)}(?![A-Za-z0-9_-])`);
  const registryKeys = new Set<string>();
  for (const e of a.entriesRaw) {
    for (const m of JSON.stringify(e).matchAll(UE_PATH_RE)) if (m[1] === folder) registryKeys.add(m[2]!);
  }
  const keys = [...STANDARD_UE_LAYERS] as string[];
  for (const k of [...registryKeys, ...onDiskDirs]) if (!keys.includes(k)) keys.push(k);

  const layers: UeLayerView[] = keys.map((key) => {
    const gamePath = `/Game/PipelineCandidates/${folder}/${key}`;
    const re = layerRe(key);
    const registry = a.layers
      .filter((l) => re.test(l.layer) || l.files.some((f) => re.test(f.path)) || Object.values(l.extra ?? {}).some((v) => re.test(v)))
      .map((l) => ({ entryId: l.entryId, layer: l.layer, status: l.status, stage: l.stage }));
    const clipStatuses: Record<string, number> = {};
    for (const c of clips) {
      const tp = asStr(asObj(c.ue).target_path);
      const st = asStr(asObj(c.ue).status);
      if (tp && st && tp.startsWith(`${gamePath}/`)) clipStatuses[st] = (clipStatuses[st] ?? 0) + 1;
    }
    const m = a.mentions.get(`${folder}/${key}`);
    const files = m?.files ?? [];
    const docFirst = [...files].sort((x, y) => Number(/\.md$/i.test(y)) - Number(/\.md$/i.test(x)) || x.localeCompare(y));
    const onDisk = ueProject ? onDiskDirs.includes(key) : null;
    const view: UeLayerView = {
      key,
      gamePath,
      standard: (STANDARD_UE_LAYERS as readonly string[]).includes(key),
      onDisk,
      registry,
      mentions: docFirst.slice(0, 12).map((p) => h.makeRef(p, { origin: 'упоминание' })),
      mentionsTotal: files.length,
      runs: [...(m?.runs ?? [])].sort(),
    };
    if (onDisk) view.uassetCount = countUassets(path.join(ueRoot, key));
    if (Object.keys(clipStatuses).length) view.clipStatuses = clipStatuses;
    return view;
  });
  return { folder, folderSource, layers };
}

/** Cheap fingerprint of the UE PipelineCandidates tree (two levels of directory mtimes). */
export function ueTreeFingerprint(root: string): string {
  const base = path.join(root, ...OVERVIEW_SOURCES.uePipelineCandidates.split('/'));
  const parts: string[] = [];
  let heroes: fs.Dirent[];
  try {
    heroes = fs.readdirSync(base, { withFileTypes: true });
  } catch {
    return 'no-ue';
  }
  for (const hd of heroes) {
    if (!hd.isDirectory() || hd.isSymbolicLink()) continue;
    let layers: fs.Dirent[];
    try {
      layers = fs.readdirSync(path.join(base, hd.name), { withFileTypes: true });
    } catch {
      continue;
    }
    for (const l of layers) {
      if (!l.isDirectory() || l.isSymbolicLink()) continue;
      try {
        parts.push(`${hd.name}/${l.name}:${fs.statSync(path.join(base, hd.name, l.name)).mtimeMs}`);
      } catch {
        /* vanished */
      }
    }
  }
  return parts.sort().join('|');
}
