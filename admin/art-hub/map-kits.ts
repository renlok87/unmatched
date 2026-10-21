/**
 * «Карты» overview section of the art hub: map kits (a prop library per game map).
 *
 * Everything is read-only. Stages are copied verbatim from status.json; a prop without
 * a status entry is «listed». The hub never upgrades a stage on its own.
 *
 * Sources:
 *   docs/art-pipeline/map-kits/<map>/map.json     — the map: board, DE topology, heroes, mood, palette, concepts[]
 *   docs/art-pipeline/map-kits/<map>/props.json   — the prop list (key, names, role, zone, size, material, priority, symmetry)
 *   docs/art-pipeline/map-kits/<map>/status.json  — OPTIONAL progress per prop key (stage, views, tripo, preview, build, acceptance)
 *   art/imagegen/mapkit-<map>/                    — Gemini images (concepts, moodboards, bases, prop views)
 *   art/pipeline-candidates/ASSET-MAPKIT-<MAP>-001/ — Tripo/Blender runs of the kit asset (fingerprint only)
 *
 * Paths inside the json files are repo-relative; absolute paths and `..` become text-only refs.
 */
import path from 'node:path';
import { kindFromPath, listDirs, walkFiles, type WalkEntry } from './fs-utils';
import { refOrText, type OverviewHelpers } from './overview';
import type { FileRef, MapKitConceptView, MapKitPropView, MapKitPropViews, MapKitsOverview, MapKitView } from './types';

export const MAP_KIT_SOURCES = {
  root: 'docs/art-pipeline/map-kits',
  imagegen: 'art/imagegen',
  imagegenPrefix: 'mapkit-',
  candidates: 'art/pipeline-candidates',
  candidatesPrefix: 'ASSET-MAPKIT-',
} as const;

export const MAP_KIT_SCHEMAS = {
  map: 'unmatched.map-kit/1',
  props: 'unmatched.map-kit.props/1',
  status: 'unmatched.map-kit.status/1',
} as const;

/** Stage vocabulary of status.json in pipeline order (a prop without status is `listed`). */
export const MAP_KIT_STAGES = ['listed', 'views', 'tripo', 'built', 'accepted', 'ue', 'rework', 'rejected'] as const;
const PRIORITY_ORDER = ['P0', 'P1', 'P2'];
const ROLE_ORDER = ['hero', 'animated', 'dressing', 'backdrop'];
/** Game height = real height × this (MK-03). */
export const MAP_KIT_HEIGHT_FACTOR = 0.3;

const KIND_RU: Record<string, string> = { concept: 'концепт', moodboard: 'мудборд', base: 'основа', reference: 'референс' };
const MAX_PROBLEMS = 20;
const MAX_UNLISTED = 48;

type J = Record<string, unknown>;
const isObj = (v: unknown): v is J => typeof v === 'object' && v !== null && !Array.isArray(v);
const asObj = (v: unknown): J => (isObj(v) ? v : {});
const asArr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const asStr = (v: unknown): string | undefined => {
  if (typeof v === 'string') return v.trim() === '' ? undefined : v;
  return typeof v === 'number' && Number.isFinite(v) ? String(v) : undefined;
};
const asNum = (v: unknown): number | undefined => {
  if (typeof v === 'number') return Number.isFinite(v) ? v : undefined;
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v);
  return undefined;
};
const cut = (s: string | undefined, max: number): string | undefined =>
  s === undefined ? undefined : s.length > max ? `${s.slice(0, max - 1)}…` : s;
const round = (n: number, digits: number) => {
  const k = 10 ** digits;
  return Math.round(n * k) / k;
};
const rankOf = (order: string[], v: string) => {
  const i = order.indexOf(v);
  return i < 0 ? order.length : i;
};
const HEX_RE = /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
/** `props.json` / `status.json` names from map.json: a plain file name only. */
const safeJsonName = (v: unknown, fallback: string) => {
  const s = asStr(v);
  return s && /^[A-Za-z0-9][\w.-]*\.json$/.test(s) ? s : fallback;
};

function abs(h: OverviewHelpers, rel: string): string {
  return path.join(h.root, ...rel.split('/'));
}

// ---------------------------------------------------------------- walking (cache fingerprint)

/**
 * Roots whose files feed the map-kit section: the data folder, the Gemini images and the Tripo
 * kit-asset runs. They are walked on their own (like audio) instead of relying on the shared
 * `art/` walk, which is capped and could drop the newest images.
 */
export function mapKitRoots(repoRoot: string): string[] {
  const roots: string[] = [MAP_KIT_SOURCES.root];
  for (const d of listDirs(repoRoot, MAP_KIT_SOURCES.imagegen)) {
    if (d.startsWith(MAP_KIT_SOURCES.imagegenPrefix)) roots.push(`${MAP_KIT_SOURCES.imagegen}/${d}`);
  }
  for (const d of listDirs(repoRoot, MAP_KIT_SOURCES.candidates)) {
    if (d.toUpperCase().startsWith(MAP_KIT_SOURCES.candidatesPrefix)) roots.push(`${MAP_KIT_SOURCES.candidates}/${d}`);
  }
  return roots;
}

export function walkMapKits(repoRoot: string): WalkEntry[] {
  return mapKitRoots(repoRoot).flatMap((r) => walkFiles(repoRoot, r));
}

// ---------------------------------------------------------------- build

interface Problems {
  list: string[];
  total: number;
  add: (msg: string, warn?: boolean) => void;
}

function problemsFor(h: OverviewHelpers, id: string): Problems {
  const p: Problems = {
    list: [],
    total: 0,
    add(msg, warn = true) {
      p.total++;
      if (p.list.length < MAX_PROBLEMS) {
        p.list.push(msg);
        if (warn) h.warnings.push(`Карты/${id}: ${msg}`);
      }
    },
  };
  return p;
}

function countBy<T>(items: T[], pick: (x: T) => string, order: string[]): { key: string; count: number }[] {
  const m = new Map<string, number>();
  for (const x of items) m.set(pick(x), (m.get(pick(x)) ?? 0) + 1);
  return [...m.entries()]
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => rankOf(order, a.key) - rankOf(order, b.key) || a.key.localeCompare(b.key));
}

function buildMap(h: OverviewHelpers, id: string, files: WalkEntry[]): MapKitView | undefined {
  const dir = `${MAP_KIT_SOURCES.root}/${id}`;
  const mapRel = `${dir}/map.json`;
  const present = (rel: string) => h.cache.stat(abs(h, rel)).isFile;
  const hasAny = present(mapRel) || present(`${dir}/props.json`) || present(`${dir}/status.json`);
  if (!hasAny) return undefined; // an unrelated or empty folder

  const problems = problemsFor(h, id);

  // ---- map.json
  let error: string | undefined;
  let m: J = {};
  if (!present(mapRel)) {
    error = 'нет map.json';
    problems.add('нет map.json — карта показана без описания');
  } else {
    const parsed = h.readJson(mapRel); // a broken file is already a hub warning
    if (!parsed) {
      error = 'map.json не разобран';
      problems.add('map.json не разобран (файл, возможно, дописывается)', false);
    } else {
      m = parsed;
      const schema = asStr(m.schema);
      if (schema && schema !== MAP_KIT_SCHEMAS.map) problems.add(`map.json: схема «${schema}», ожидалась «${MAP_KIT_SCHEMAS.map}»`);
      const declared = asStr(m.map);
      if (declared && declared !== id) problems.add(`map.json: map «${declared}» не совпадает с папкой «${id}»`);
    }
  }
  const propsRel = `${dir}/${safeJsonName(m.propsFile, 'props.json')}`;
  const statusRel = `${dir}/${safeJsonName(m.statusFile, 'status.json')}`;

  const referenced = new Set<string>();
  const refOf = (p: unknown, role: string, what?: string): FileRef | undefined => {
    const s = asStr(p);
    if (!s) return undefined;
    const ref = refOrText(h, s, role);
    referenced.add(ref.path);
    // a file that is not there yet is shown on the map, not as a hub-wide warning
    if (what && ref.exists === false) problems.add(`${what}: нет файла ${ref.path}`, false);
    return ref;
  };

  // ---- concepts
  const concepts: MapKitConceptView[] = [];
  asArr(m.concepts).forEach((c, i) => {
    const o = asObj(c);
    const p = asStr(o.path);
    if (!p) {
      problems.add(`map.json: у концепта №${i + 1} нет path`);
      return;
    }
    const kind = asStr(o.kind) ?? 'concept';
    const title = asStr(o.title) ?? path.posix.basename(p);
    const file = refOf(p, `${KIND_RU[kind] ?? kind}: ${title}`, `концепт «${title}»`);
    if (file) concepts.push({ file, kind, title, status: asStr(o.status) });
  });
  const isImage = (c: MapKitConceptView) => c.file.kind === 'image' && c.file.servable;
  const thumb = (concepts.find((c) => c.kind === 'concept' && isImage(c)) ?? concepts.find(isImage))?.file;

  // ---- props.json
  const propsFile = h.makeRef(propsRel, { role: 'список пропсов' });
  const statusFile = h.makeRef(statusRel, { role: 'прогресс пропсов' });
  let propsDoc: J | undefined;
  if (!propsFile.exists) problems.add(`нет ${path.posix.basename(propsRel)} — список пропсов пуст`);
  else {
    propsDoc = h.readJson(propsRel);
    if (!propsDoc) problems.add(`${path.posix.basename(propsRel)} не разобран — список пропсов пуст`, false);
    else {
      const schema = asStr(propsDoc.schema);
      if (schema && schema !== MAP_KIT_SCHEMAS.props) problems.add(`props.json: схема «${schema}», ожидалась «${MAP_KIT_SCHEMAS.props}»`);
    }
  }

  // ---- status.json (optional)
  let statusDoc: J | undefined;
  if (statusFile.exists) {
    statusDoc = h.readJson(statusRel);
    if (!statusDoc) problems.add(`${path.posix.basename(statusRel)} не разобран — все пропсы показаны как «в списке»`, false);
    else {
      const schema = asStr(statusDoc.schema);
      if (schema && schema !== MAP_KIT_SCHEMAS.status) problems.add(`status.json: схема «${schema}», ожидалась «${MAP_KIT_SCHEMAS.status}»`);
    }
  }
  const statusProps = asObj(statusDoc?.props);

  const props: MapKitPropView[] = [];
  const seen = new Set<string>();
  const unknownStages = new Set<string>();
  asArr(propsDoc?.props).forEach((raw, i) => {
    const p = asObj(raw);
    const key = asStr(p.key)?.trim();
    if (!key) {
      problems.add(`props.json: у пропса №${i + 1} нет key`);
      return;
    }
    if (seen.has(key)) {
      problems.add(`props.json: повтор ключа «${key}» — второй пропс пропущен`);
      return;
    }
    seen.add(key);

    let sizeM: number[] | undefined;
    if (p.sizeM !== undefined) {
      const dims = asArr(p.sizeM).map(asNum);
      if (dims.length === 3 && dims.every((d): d is number => d !== undefined && d >= 0)) sizeM = dims;
      else problems.add(`${key}: sizeM должен быть [ширина, глубина, высота] в метрах`);
    }
    const symmetry = asStr(p.symmetry);
    const slots = symmetry === 'axial' ? ['front', 'left'] : symmetry === 'asymmetric' ? ['front', 'back'] : [];

    const stRaw = statusProps[key];
    const st = asObj(stRaw);
    const inStatus = isObj(stRaw);
    const stage = asStr(st.stage) ?? 'listed';
    const stageKnown = (MAP_KIT_STAGES as readonly string[]).includes(stage);
    if (!stageKnown) unknownStages.add(stage);

    const views: MapKitPropViews = {};
    const v = asObj(st.views);
    for (const k of ['front', 'side', 'sheet'] as const) {
      const ref = refOf(v[k], `вид ${k}: ${key}`, `${key}: вид ${k}`);
      if (ref) views[k] = ref;
    }
    // `slot` is the name of the Tripo slot the side view fills («left»/«back»), not a path
    const slot = asStr(v.slot);
    if (slot) views.slot = cut(slot, 40);
    const mismatch = asNum(v.heightMismatchPct);
    if (mismatch !== undefined) views.heightMismatchPct = mismatch;
    const preview = refOf(st.preview, `превью: ${key}`, `${key}: превью`);

    let tripo: MapKitPropView['tripo'];
    if (isObj(st.tripo)) {
      const t = st.tripo;
      tripo = {
        taskId: asStr(t.taskId),
        route: cut(asStr(t.route), 120),
        credits: asNum(t.credits),
        ops: asArr(t.ops)
          .filter(isObj)
          .slice(0, 20)
          .map((o) => ({ op: asStr(o.op) ?? '?', status: asStr(o.status), quoted: asNum(o.quoted), before: asNum(o.before), after: asNum(o.after) })),
        glb: refOf(t.glb, `GLB из Tripo: ${key}`, `${key}: GLB`),
        run: cut(asStr(t.run), 200),
      };
    }
    let build: MapKitPropView['build'];
    if (isObj(st.build)) {
      const b = st.build;
      build = {
        fbx: refOf(b.fbx, `FBX: ${key}`, `${key}: FBX`),
        tris: asNum(b.tris),
        report: refOf(b.report, `отчёт сборки: ${key}`, `${key}: отчёт сборки`),
      };
    }
    let acceptance: MapKitPropView['acceptance'];
    if (isObj(st.acceptance)) {
      const a = st.acceptance;
      acceptance = {
        score: asNum(a.score),
        verdict: cut(asStr(a.verdict), 200),
        card: refOf(a.card, `карточка приёмки: ${key}`, `${key}: карточка приёмки`),
      };
    }

    props.push({
      key,
      nameRu: asStr(p.nameRu) ?? asStr(p.nameEn) ?? key,
      nameEn: asStr(p.nameEn),
      descRu: cut(asStr(p.descRu), 600),
      descEn: cut(asStr(p.descEn), 800),
      role: asStr(p.role) ?? '—',
      zone: asStr(p.zone),
      sizeM,
      gameHeightM: sizeM ? round(sizeM[2]! * MAP_KIT_HEIGHT_FACTOR, 2) : undefined,
      material: cut(asStr(p.material), 200),
      priority: asStr(p.priority) ?? '—',
      symmetry,
      slots,
      trisMax: asNum(p.trisMax),
      stage,
      stageKnown,
      inStatus,
      views,
      preview,
      tripo,
      build,
      acceptance,
      note: cut(asStr(st.note), 400),
    });
  });
  props.sort((a, b) => rankOf(PRIORITY_ORDER, a.priority) - rankOf(PRIORITY_ORDER, b.priority) || a.key.localeCompare(b.key));

  if (unknownStages.size) problems.add(`status.json: стадия вне словаря (${[...unknownStages].join(', ')}) — показана как есть`);
  const orphans = Object.keys(statusProps).filter((k) => !seen.has(k));
  if (orphans.length) problems.add(`status.json: записи без пропса в props.json: ${orphans.slice(0, 8).join(', ')}${orphans.length > 8 ? '…' : ''}`);

  // ---- images of the Gemini folder that no json mentions
  const imagesDir = `${MAP_KIT_SOURCES.imagegen}/${MAP_KIT_SOURCES.imagegenPrefix}${id}`;
  const allImages = files.filter((f) => f.rel.startsWith(`${imagesDir}/`) && kindFromPath(f.rel) === 'image');
  const imageEntries = allImages.filter((f) => !referenced.has(f.rel)).sort((a, b) => a.rel.localeCompare(b.rel));

  const credits = props.reduce((s, p) => s + (p.tripo?.credits ?? 0), 0);
  const stageCounts = countBy(props, (p) => p.stage, [...MAP_KIT_STAGES]);
  const topology = isObj(m.deTopology)
    ? { field: asStr(m.deTopology.field), cells: asNum(m.deTopology.cells), edges: asNum(m.deTopology.edges) }
    : undefined;

  return {
    id,
    boardName: asStr(m.boardName) ?? id,
    boardNameRu: asStr(m.boardNameRu),
    set: asStr(m.set),
    boardId: asStr(m.boardId),
    topology,
    heroes: asArr(m.heroes).map(asStr).filter((s): s is string => s !== undefined),
    whyChosenRu: cut(asStr(m.whyChosenRu), 1500),
    moodRu: cut(asStr(m.moodRu), 1500),
    lightingRu: cut(asStr(m.lightingRu), 1000),
    backdropRu: cut(asStr(m.backdropRu), 1000),
    scopeNoteRu: cut(asStr(m.scopeNoteRu), 1000),
    paletteHex: asArr(m.paletteHex).map(asStr).filter((s): s is string => s !== undefined && HEX_RE.test(s)),
    styleEn: cut(asStr(propsDoc?.styleEn), 1500),
    scale: cut(asStr(propsDoc?.scale), 300),
    files: { map: h.makeRef(mapRel, { role: 'описание карты' }), props: propsFile, status: statusFile },
    statusUpdatedAt: asStr(statusDoc?.updatedAt),
    concepts,
    images: {
      dir: imagesDir,
      exists: h.cache.stat(abs(h, imagesDir)).isDir,
      total: allImages.length,
      unlisted: imageEntries.slice(0, MAX_UNLISTED).map((f) => h.makeRef(f.rel, { origin: 'папка карты' })),
      unlistedTotal: imageEntries.length,
    },
    thumb,
    props,
    counts: {
      total: props.length,
      byStage: stageCounts.map((c) => ({ stage: c.key, count: c.count })),
      byPriority: countBy(props, (p) => p.priority, PRIORITY_ORDER).map((c) => ({ priority: c.key, count: c.count })),
      byRole: countBy(props, (p) => p.role, ROLE_ORDER).map((c) => ({ role: c.key, count: c.count })),
    },
    credits: {
      spent: round(credits, 2),
      tasks: props.filter((p) => p.tripo?.credits !== undefined).length,
      declared: asNum(asObj(statusDoc?.totals).credits),
    },
    problems: problems.total > problems.list.length ? [...problems.list, `…и ещё ${problems.total - problems.list.length}`] : problems.list,
    error,
  };
}

export function buildMapKits(h: OverviewHelpers, a: { files: WalkEntry[] }): MapKitsOverview {
  const root = MAP_KIT_SOURCES.root;
  const found = h.cache.stat(abs(h, root)).isDir;
  const maps: MapKitView[] = [];
  if (found) {
    for (const id of listDirs(h.root, root)) {
      const view = buildMap(h, id, a.files);
      if (view) maps.push(view);
    }
  }
  const allStages = new Map<string, number>();
  for (const mp of maps) for (const s of mp.counts.byStage) allStages.set(s.stage, (allStages.get(s.stage) ?? 0) + s.count);
  return {
    root,
    found,
    maps,
    totals: {
      maps: maps.length,
      props: maps.reduce((n, mp) => n + mp.counts.total, 0),
      credits: round(
        maps.reduce((n, mp) => n + mp.credits.spent, 0),
        2,
      ),
      byStage: [...allStages.entries()]
        .map(([stage, count]) => ({ stage, count }))
        .sort((x, y) => rankOf([...MAP_KIT_STAGES], x.stage) - rankOf([...MAP_KIT_STAGES], y.stage) || x.stage.localeCompare(y.stage)),
    },
  };
}
