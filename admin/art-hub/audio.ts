/**
 * «Звук» overview section of the art hub and the per-character audio units.
 *
 * Everything is read-only. Registry statuses are copied verbatim; UE assets are
 * only counted (names come from the existing sound scan), never served.
 *
 * Sources:
 *   docs/game-design/audio/NN-*.md                       — audio docs 00…07 (brief … production log)
 *   docs/game-design/audio/03-sound-registry.csv         — one row per sound unit (status, owner, UE path, notes)
 *   docs/game-design/audio/04-vo-script.md               — hero lines `| ARTHUR-ATTACK-01 | EN | RU | [tags] |`,
 *                                                          cries `| HARPY-ATTACK-01…03 | что | направление |`
 *   docs/game-design/audio/07-production-log.md          — «## 0. Итог» table
 *   docs/game-design/evidence/AUDIO/<date>/<map>-<client>-mix.json — loudness of recorded matches
 *   docs/art-pipeline/evidence/<any>/credits-ledger.json — SYNTX entries with cue AUC-* (already parsed)
 *   unreal/Unmatched/Content/Audio/**\/SW_*.uasset       — from the sound scan (names only)
 */
import path from 'node:path';
import { csvToObjects, kindFromPath, mdTableAfterHeading, stripMd, type WalkEntry } from './fs-utils';
import { docView, type OverviewHelpers } from './overview';
import type {
  AudioEvidenceFolder,
  AudioMixRow,
  AudioOverview,
  AudioUnitView,
  AudioVoFighter,
  CharacterAudioUnit,
  LedgerEntry,
  SoundSection,
} from './types';

export const AUDIO_SOURCES = {
  docs: 'docs/game-design/audio',
  registry: 'docs/game-design/audio/03-sound-registry.csv',
  voScript: 'docs/game-design/audio/04-vo-script.md',
  productionLog: 'docs/game-design/audio/07-production-log.md',
  evidence: 'docs/game-design/evidence/AUDIO',
  ueContent: 'unreal/Unmatched/Content',
  ueAudio: 'unreal/Unmatched/Content/Audio',
} as const;

/** Registry status vocabulary in pipeline order (unknown statuses go last, verbatim). */
export const AUDIO_STATUS_ORDER = ['in-game', 'in-bank', 'done-source', 'template', 'none-by-design'] as const;

/** Statuses whose unit must have a SoundWave in UE. */
const STATUSES_WITH_UE_ASSET = new Set(['in-game', 'in-bank']);

const TABLE_ROLES: Record<string, string> = {
  '03': 'реестр единиц звука',
  '06': 'карточки задач производства',
};

/** Hero line with a text column: `| ARTHUR-ATTACK-01 | EN | RU | [tags] |` (tools/audio/vo_batch.py, any fighter). */
const VO_LINE_RE = /^\| ([A-Z]+-[A-Z-]+-\d\d) \| ([^|]*?) \| ([^|]*?) \| ([^|]*?) \|$/;
/** Cry without a text column: `| HARPY-ATTACK-01…03 | что | направление |` (range or single number). */
const VO_CRY_RE = /^\| ([A-Z]+-[A-Z-]+)-(\d\d)(?:(?:…|\.{2,3})(\d\d))? \| ([^|]*?) \| ([^|]*?) \|$/;
const MIX_RE = /^(.+?)-(host|joiner|client\d*)-mix\.json$/i;

const cut = (s: string | undefined, max: number): string | undefined =>
  !s ? undefined : s.length > max ? `${s.slice(0, max - 1)}…` : s;
const dash = (s: string | undefined): string | undefined => (s === undefined || s === '' || s === '-' || s === '—' ? undefined : s);
const num = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined);
const bool = (v: unknown): boolean | undefined => (typeof v === 'boolean' ? v : undefined);
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function abs(h: OverviewHelpers, rel: string): string {
  return path.join(h.root, ...rel.split('/'));
}

/**
 * `/Game/Audio/VO/Arthur/SW_VO_ARTHUR_ATTACK_*` → regex over scanned repo paths of .uasset files.
 * A name without `*` also matches its numbered variants (`SW_UI_TOAST` → `SW_UI_TOAST_01`).
 */
export function uePatternRe(file: string | undefined): RegExp | undefined {
  const m = /^\/Game\/(\S+)$/.exec((file ?? '').trim());
  if (!m) return undefined;
  const body = m[1]!
    .split('/')
    .map((seg) => seg.split('*').map(escapeRe).join('[^/]*'))
    .join('/');
  const variants = m[1]!.includes('*') ? '' : '(?:_\\d+)?';
  return new RegExp(`^${escapeRe(AUDIO_SOURCES.ueContent)}/${body}${variants}\\.uasset$`, 'i');
}

/** Lines per fighter in 04-vo-script.md (ids are de-duplicated). */
export function parseVoScript(text: string): AudioVoFighter[] {
  const ids = new Map<string, boolean>(); // id → wordless
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const v = VO_LINE_RE.exec(line);
    if (v) {
      const en = v[2]!.trim();
      ids.set(v[1]!, en === '' || en === '—' || en === '-');
      continue;
    }
    const c = VO_CRY_RE.exec(line);
    if (c) {
      const from = Number(c[2]);
      const to = c[3] ? Number(c[3]) : from;
      for (let n = from; n <= Math.max(from, to) && n - from < 99; n++) ids.set(`${c[1]}-${String(n).padStart(2, '0')}`, true);
    }
  }
  const byFighter = new Map<string, AudioVoFighter>();
  for (const [id, wordless] of ids) {
    const fighter = id.split('-')[0]!;
    const f = byFighter.get(fighter) ?? { fighter, lines: 0, wordless: 0 };
    f.lines++;
    if (wordless) f.wordless++;
    byFighter.set(fighter, f);
  }
  return [...byFighter.values()];
}

function statusRank(s: string): number {
  const i = (AUDIO_STATUS_ORDER as readonly string[]).indexOf(s);
  return i < 0 ? 99 : i;
}

function evidenceFolders(files: WalkEntry[]): Map<string, WalkEntry[]> {
  const prefix = `${AUDIO_SOURCES.evidence}/`;
  const out = new Map<string, WalkEntry[]>();
  for (const f of files) {
    if (!f.rel.startsWith(prefix)) continue;
    const parts = f.rel.slice(prefix.length).split('/');
    if (parts.length < 2) continue; // loose files in AUDIO/ are not a dated folder
    out.set(parts[0]!, [...(out.get(parts[0]!) ?? []), f]);
  }
  return out;
}

function mixRow(h: OverviewHelpers, rel: string): AudioMixRow {
  const base = path.posix.basename(rel);
  const m = MIX_RE.exec(base);
  const row: AudioMixRow = {
    map: m ? m[1]! : base.replace(/-mix\.json$/i, ''),
    client: m ? m[2]!.toLowerCase() : '—',
    file: h.makeRef(rel, { role: 'замер громкости' }),
  };
  const d = h.readJson(rel);
  if (!d) {
    row.error = 'не разобран';
    return row;
  }
  row.I = num(d.I);
  row.LRA = num(d.LRA);
  row.TP = num(d.TP);
  row.sMax = num(d.S_max);
  row.nearPeakShare = num(d.near_peak_share);
  row.seconds = num(d.seconds);
  row.correctionDb = num(d.correction_db);
  row.okI = bool(d.ok_I);
  row.okTP = bool(d.ok_TP);
  return row;
}

function targetsOf(h: OverviewHelpers, rel: string): Record<string, string> | undefined {
  const t = h.readJson(rel)?.targets;
  if (typeof t !== 'object' || t === null || Array.isArray(t)) return undefined;
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(t)) {
    if (v !== null && v !== undefined) out[k] = typeof v === 'object' ? JSON.stringify(v) : String(v);
  }
  return Object.keys(out).length ? out : undefined;
}

export function buildAudio(
  h: OverviewHelpers,
  a: { files: WalkEntry[]; soundFiles: string[]; ledgerRel?: string; ledgerEntries: LedgerEntry[]; syntxUnit?: string },
): AudioOverview {
  const root = AUDIO_SOURCES.docs;
  const top = a.files.filter((f) => f.rel.startsWith(`${root}/`) && !f.rel.slice(root.length + 1).includes('/'));

  // ---- docs and tables
  const docs = top
    .filter((f) => /^\d\d-[^/]*\.md$/i.test(path.posix.basename(f.rel)))
    .sort((x, y) => x.rel.localeCompare(y.rel))
    .map((f) => docView(h, f.rel, 'документ звука'));
  const tables = top
    .filter((f) => /\.csv$/i.test(f.rel))
    .sort((x, y) => x.rel.localeCompare(y.rel))
    .map((f) => h.makeRef(f.rel, { role: TABLE_ROLES[path.posix.basename(f.rel).slice(0, 2)] ?? 'таблица' }));

  // ---- UE SoundWaves (names from the sound scan)
  const ueContentFound = h.cache.stat(abs(h, AUDIO_SOURCES.ueContent)).isDir;
  const ueFiles = a.soundFiles.filter((f) => f.startsWith(`${AUDIO_SOURCES.ueContent}/`) && /\.uasset$/i.test(f));
  const ueAudioPrefix = `${AUDIO_SOURCES.ueAudio}/`;
  const soundWaves = ueFiles.filter((f) => f.startsWith(ueAudioPrefix) && /^sw_/i.test(path.posix.basename(f)));
  const folderCounts = new Map<string, number>();
  for (const f of soundWaves) {
    const dir = path.posix.dirname(f.slice(ueAudioPrefix.length));
    const folder = dir === '.' ? '(корень)' : dir;
    folderCounts.set(folder, (folderCounts.get(folder) ?? 0) + 1);
  }

  // ---- registry
  const registryFile = h.makeRef(AUDIO_SOURCES.registry, { role: 'реестр единиц звука' });
  const units: AudioUnitView[] = [];
  const patterns: { unit: AudioUnitView; re: RegExp; specificity: number }[] = [];
  let registryError: string | undefined;
  if (registryFile.exists) {
    const text = h.cache.readText(abs(h, AUDIO_SOURCES.registry), 4 * 1024 * 1024);
    const rows = text ? csvToObjects(text) : [];
    if (!text) registryError = 'не прочитан';
    else if (!rows.length || !('id' in rows[0]!) || !('status' in rows[0]!)) registryError = 'нет колонок id/status';
    for (const r of rows) {
      const id = r.id?.trim();
      if (!id) continue;
      const file = dash(r.file);
      const re = uePatternRe(file);
      const unit: AudioUnitView = {
        id,
        category: dash(r.category) ?? '—',
        nameRu: dash(r.name_ru),
        event: dash(r.event_or_cue),
        trigger: cut(dash(r.trigger), 200),
        bus: dash(r.bus),
        priority: dash(r.priority),
        loop: dash(r.loop),
        scope: dash(r.scope),
        owner: dash(r.owner),
        sourcePlan: dash(r.source_plan),
        license: cut(dash(r.license), 200),
        status: dash(r.status) ?? '—',
        file,
        notes: cut(dash(r.notes), 200),
      };
      if (re && ueContentFound) {
        unit.ueAssets = 0;
        patterns.push({ unit, re, specificity: file!.replace(/\*/g, '').length });
      }
      units.push(unit);
    }
    if (registryError) h.warnings.push(`${AUDIO_SOURCES.registry}: ${registryError} — раздел «Звук» пуст`);
  }
  // Each asset counts once, for the most specific pattern (SW_VO_ARTHUR_HURT_* vs SW_VO_ARTHUR_HURT_BIG_*).
  const unregistered: string[] = [];
  for (const f of ueFiles) {
    let best: (typeof patterns)[number] | undefined;
    for (const p of patterns) if (p.re.test(f) && (!best || p.specificity > best.specificity)) best = p;
    if (best) best.unit.ueAssets = (best.unit.ueAssets ?? 0) + 1;
    else if (soundWaves.includes(f)) unregistered.push(f);
  }
  const statusCounts = new Map<string, number>();
  const categoryCounts = new Map<string, number>();
  for (const u of units) {
    statusCounts.set(u.status, (statusCounts.get(u.status) ?? 0) + 1);
    categoryCounts.set(u.category, (categoryCounts.get(u.category) ?? 0) + 1);
  }

  // ---- VO
  const voText = h.cache.readText(abs(h, AUDIO_SOURCES.voScript), 1024 * 1024);
  const fighters = voText ? parseVoScript(voText) : [];

  // ---- production log summary
  const logFile = h.makeRef(AUDIO_SOURCES.productionLog, { role: 'журнал производства звука' });
  let summary: AudioOverview['summary'];
  const logText = logFile.exists ? h.cache.readText(abs(h, AUDIO_SOURCES.productionLog), 1024 * 1024) : undefined;
  if (logText) {
    const rows = mdTableAfterHeading(logText, /^##\s*0[.\s]/).map((r) => r.map((c) => cut(stripMd(c), 400) ?? ''));
    if (rows.length > 1) summary = { file: logFile, rows };
  }

  // ---- mix evidence
  const folders = evidenceFolders(a.files);
  const folderViews: AudioEvidenceFolder[] = [...folders.entries()]
    .map(([date, list]) => ({
      date,
      dir: `${AUDIO_SOURCES.evidence}/${date}`,
      fileCount: list.length,
      mixCount: list.filter((f) => /-mix\.json$/i.test(f.rel)).length,
    }))
    .sort((x, y) => y.date.localeCompare(x.date));
  let latest: AudioOverview['mix']['latest'];
  const latestFolder = folderViews.find((f) => f.mixCount > 0);
  if (latestFolder) {
    const list = folders.get(latestFolder.date) ?? [];
    const mixRels = list.filter((f) => /-mix\.json$/i.test(f.rel)).map((f) => f.rel);
    const clientRank = (c: string) => (c === 'host' ? 0 : c === 'joiner' ? 1 : 2);
    const rows = mixRels.map((rel) => mixRow(h, rel)).sort((x, y) => x.map.localeCompare(y.map) || clientRank(x.client) - clientRank(y.client));
    const imageFirst = (f: WalkEntry) => (kindFromPath(f.rel) === 'image' ? 0 : 1);
    latest = {
      ...latestFolder,
      rows,
      targets: mixRels.map((rel) => targetsOf(h, rel)).find(Boolean),
      files: [...list]
        .sort((x, y) => imageFirst(x) - imageFirst(y) || x.rel.localeCompare(y.rel))
        .map((f) => h.makeRef(f.rel, { origin: 'evidence/AUDIO' })),
    };
  }

  // ---- AUC-* spends
  const entries = a.ledgerEntries
    .filter((e) => e.service === 'syntx' && /^AUC-/.test(e.cue ?? ''))
    .map((e, i) => ({ e, i }))
    .sort((x, y) => (x.e.time ?? '').localeCompare(y.e.time ?? '') || x.i - y.i)
    .map((x) => x.e);
  const round = (n: number) => Math.round(n * 100) / 100;
  const spent = round(entries.reduce((s, e) => s + (e.delta < 0 ? -e.delta : 0), 0));
  const refunds = round(entries.reduce((s, e) => s + (e.delta > 0 ? e.delta : 0), 0));

  return {
    root,
    docs,
    tables,
    registry: {
      file: registryFile,
      error: registryError,
      units,
      byStatus: [...statusCounts.entries()]
        .map(([status, count]) => ({ status, count }))
        .sort((x, y) => statusRank(x.status) - statusRank(y.status) || x.status.localeCompare(y.status)),
      byCategory: [...categoryCounts.entries()]
        .map(([category, count]) => ({ category, count }))
        .sort((x, y) => y.count - x.count || x.category.localeCompare(y.category)),
      missingInUe: units.filter((u) => u.ueAssets === 0 && STATUSES_WITH_UE_ASSET.has(u.status)).map((u) => u.id),
    },
    summary,
    vo: {
      script: h.makeRef(AUDIO_SOURCES.voScript, { role: 'реплики героев' }),
      log: logFile,
      total: fighters.reduce((s, f) => s + f.lines, 0),
      wordless: fighters.reduce((s, f) => s + f.wordless, 0),
      fighters,
    },
    ue: {
      contentRoot: AUDIO_SOURCES.ueAudio,
      found: ueContentFound ? h.cache.stat(abs(h, AUDIO_SOURCES.ueAudio)).isDir : null,
      soundWaves: soundWaves.length,
      unregistered: units.length ? unregistered.slice(0, 100) : [],
      byFolder:[...folderCounts.entries()].map(([folder, count]) => ({ folder, count })).sort((x, y) => x.folder.localeCompare(y.folder)),
    },
    mix: { evidenceRoot: AUDIO_SOURCES.evidence, latest, folders: folderViews },
    spends: {
      ledger: a.ledgerRel ? h.makeRef(a.ledgerRel, { role: 'единый журнал кредитов' }) : undefined,
      unit: a.syntxUnit ?? 'токены SYNTX',
      spent,
      refunds,
      balanceStart: entries.find((e) => e.balanceBefore !== undefined)?.balanceBefore,
      balanceEnd: [...entries].reverse().find((e) => e.balanceAfter !== undefined)?.balanceAfter,
      entries,
    },
  };
}

/**
 * Registry units and VO lines of one character. `key` is the clip-manifest
 * character (Arthur, Medusa…) or the last word of the short name. A unit
 * belongs to the character by its owner column or by the key as an id token
 * (VO-ARTHUR-ATTACK, DTH-MEDUSA, FX-ARTHUR-BOOST).
 */
export function audioForCharacter(audio: AudioOverview, key: string | undefined): Pick<SoundSection, 'units' | 'registry' | 'vo'> {
  const keys = new Set(
    [key, key?.split(/\s+/).pop()]
      .filter((k): k is string => Boolean(k && k.trim()))
      .map((k) => k.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '-')),
  );
  const units: CharacterAudioUnit[] = [];
  if (keys.size) {
    for (const u of audio.registry.units) {
      const owner = u.owner?.toUpperCase().replace(/[^A-Z0-9]+/g, '-');
      if (owner && keys.has(owner)) units.push({ ...u, via: 'владелец (owner)' });
      else if (u.id.split('-').some((t) => keys.has(t))) units.push({ ...u, via: 'ключ в id' });
    }
  }
  const f = audio.vo.fighters.find((x) => keys.has(x.fighter));
  return {
    units,
    registry: audio.registry.file,
    vo: f ? { fighter: f.fighter, lines: f.lines, wordless: f.wordless, script: audio.vo.script, log: audio.vo.log } : undefined,
  };
}

/** Audio files under the watched audio roots (docs + evidence), for the cache fingerprint. */
export function audioRoots(): string[] {
  return [AUDIO_SOURCES.docs, AUDIO_SOURCES.evidence];
}
