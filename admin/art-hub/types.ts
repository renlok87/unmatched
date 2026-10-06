/**
 * Art-hub data model. Shared by the Node aggregator (aggregate.ts) and the
 * admin page (src/pages/art-hub). No Node imports here.
 *
 * All paths are repo-relative POSIX paths unless `root` says otherwise.
 * Status strings are copied verbatim from the project data; the hub never
 * upgrades a status on its own.
 */

export type FileKind =
  | 'glb'
  | 'gltf'
  | 'fbx'
  | 'bvh'
  | 'image'
  | 'video'
  | 'audio'
  | 'json'
  | 'markdown'
  | 'text'
  | 'blend'
  | 'archive'
  | 'ue-asset'
  | 'dir'
  | 'other';

export type ShaCheck = 'match' | 'mismatch' | 'skipped-large' | 'not-declared' | 'missing-file';

export interface FileRef {
  path: string;
  root: 'repo' | 'art-worktree' | 'ue';
  kind: FileKind;
  role?: string;
  /** null = existence not checked (e.g. external root unknown) */
  exists: boolean | null;
  bytes?: number;
  mtime?: string;
  /** sha256 declared in a registry/manifest (not computed) */
  sha256?: string;
  shaCheck?: ShaCheck;
  /** true when the dev endpoint /__art-hub/file may serve it (whitelist + exists) */
  servable: boolean;
  expect?: string;
  /** where the reference came from: registry, run:<id>, scan, clip-manifest… */
  origin?: string;
}

export interface StatusVocabItem {
  name: string;
  description: string;
}

export interface Vocabulary {
  status: StatusVocabItem[];
  statusRules: string[];
  stage: string[];
  /** clip-manifest status (en) → Russian label from the schema description */
  clipStatus: Record<string, string>;
}

export interface MemberEntry {
  id: string;
  name: string;
  category: string;
  status: string | null;
  stage: string | null;
  nextStep?: string;
  blocker?: string;
  doneCriteria?: string;
  instances: number;
}

export interface LayerView {
  entryId: string;
  layer: string;
  stage?: string;
  status?: string;
  statusLabel?: string;
  decision?: string;
  owner?: string;
  note?: string;
  files: FileRef[];
  extra?: Record<string, string>;
}

export interface ActView {
  file: FileRef;
  title?: string;
  /** first "**Решение…**" line of the act, verbatim (truncated) */
  decision?: string;
  entryId: string;
  acceptance: boolean;
}

export interface RunStage {
  name: string;
  status: string;
  finishedAt?: string;
  backend?: string;
  passed?: boolean;
}

export interface RunView {
  id: string;
  dir: string;
  assetDir: string;
  kind: string;
  schema?: string;
  createdAt?: string;
  lastModified?: string;
  toolVersion?: string;
  title?: string;
  stages: RunStage[];
  claims?: Record<string, string>;
  manifest?: FileRef;
  readme?: FileRef;
  reports: FileRef[];
  previews: FileRef[];
  models: FileRef[];
  textures: FileRef[];
  otherFiles: number;
  inRegistry: boolean;
  credits?: string;
}

export interface ModelsSection {
  sourceImages: FileRef[];
  models: FileRef[];
  previews: FileRef[];
  textures: FileRef[];
  runs: RunView[];
  /** newest frames from docs/game-design/evidence/<backlog>/ (live work in progress) */
  evidenceImages: FileRef[];
  evidenceImagesTotal: number;
  /** best default for the 3D viewer */
  defaultModel?: string;
}

export interface BoneView {
  name: string;
  parent: string | null;
  role?: string;
}

export interface DeformTest {
  test: string;
  bone?: string;
  deg?: number;
  status: string;
}

export interface DeformProbe {
  label: string;
  source?: string;
  family?: string;
  run: string;
  report: FileRef;
  sheet?: FileRef;
  tests: DeformTest[];
}

export interface RigSection {
  contract?: FileRef;
  contractDoc?: FileRef;
  contractStatus?: string;
  contractStatusNote?: string;
  revision?: string;
  skeletonKey?: string;
  appliesTo?: string[];
  armatureObject?: { name?: string; status?: string; rule?: string; legacyNames?: string[] };
  bones: BoneView[];
  weaponParent?: string | null;
  sockets: { name: string; bone?: string; offset?: number[]; note?: string }[];
  extensions: { key: string; status?: string; rule?: string }[];
  rootMotion?: Record<string, string>;
  axes?: Record<string, string>;
  retargetMaps: { key: string; status?: string }[];
  deformProbes: DeformProbe[];
  rigReports: FileRef[];
  rigLayers: LayerView[];
}

export interface ValidationCheck {
  check: string;
  status: string;
  note?: string;
  value?: string;
}

export interface ClipSlotView {
  id: string;
  clip: string;
  role: string;
  requiredMvp: boolean;
  status: string;
  statusLabel: string;
  cue: string[];
  sourceType: string;
  sourceTool?: string;
  sourceReference?: string;
  files: FileRef[];
  license?: Record<string, string>;
  fpsTarget?: number | string;
  fpsMeasured?: number | null;
  durationTarget?: number | string;
  durationTargetStatus?: string;
  durationMeasured?: number | null;
  loop?: boolean;
  rootMotion?: string;
  skeleton?: string;
  ueTargetPath?: string;
  ueStatus?: string;
  ueStatusLabel?: string;
  ueEvidence?: FileRef;
  validation: {
    result: string;
    report?: FileRef;
    fails: string[];
    warnings: string[];
    date?: string;
    checks: ValidationCheck[];
  };
  notes?: string;
  acceptanceEvidence?: FileRef;
}

export interface ClipSection {
  manifest?: FileRef;
  revision?: string;
  notes: string[];
  slots: ClipSlotView[];
  animationFiles: FileRef[];
  validationCases: {
    case: string;
    clip: string;
    result: string;
    expectationMet?: boolean;
    fails: string[];
    warnings: string[];
    fps?: number;
    durationS?: number;
  }[];
}

export interface VideoSuitability {
  verdict?: string;
  status?: string;
  basis?: string;
}

export interface VideoTakeView {
  /** `take1` = files directly in the cue dir, `takeN` = subdir takeN/ */
  take: string;
  takeNo: number;
  dir: string;
  video?: FileRef;
  /** video path named by the manifest record but not found on disk */
  missingVideo?: string;
  contactSheet?: FileRef;
  keyframes: FileRef[];
  prompt?: string;
  promptFile?: FileRef;
  analysis?: Record<string, string | number>;
  analysisFile?: FileRef;
  model?: string;
  cost?: { tokens?: number; balanceBefore?: number; balanceAfter?: number; source: string };
  lastModified?: string;
  /** where this take is described in the manifest, e.g. `retakes[MED-HitReact].takes[take4]`; undefined = no record */
  manifestRecord?: string;
  /** true = the manifest selects this take; false = it selects another take; undefined = no selection recorded */
  selected?: boolean;
  manifestStatus?: string;
  suitability?: VideoSuitability;
  briefFit?: string;
  whyThisTake?: string;
  motionSummary?: string;
  assessment?: Record<string, string>;
  briefDeviation?: string;
  retryProposal?: string;
}

export interface VideoCueView {
  cue: string;
  cueRef?: string;
  requiredMvp?: boolean;
  takes: VideoTakeView[];
  /** manifest records merged for this cue, e.g. `clips[MED-HitReact]`, `retakes[MED-HitReact]` */
  manifestRecords: string[];
  /** take selected in the manifest (selectedTake / takes[].selected) */
  selectedTake?: string;
  /** status of the take the clip-level verdict comes from */
  manifestStatus?: string;
  /** clip-level verdict = verdict of the selected take (or of the only take with a record) */
  suitability?: VideoSuitability;
  /** which take the clip-level verdict comes from, e.g. `take4 — выбранный дубль` */
  suitabilityFrom?: string;
  /** why there is no clip-level verdict although the manifest has records for the cue */
  suitabilityNote?: string;
}

export interface VideoRefSection {
  manifest?: FileRef;
  /** parts of the manifest that describe this asset: top level, assets[ID], retakes[] */
  manifestScopes: string[];
  overallStatus?: string;
  budget?: Record<string, string | number>;
  budgetLabel?: string;
  /** manifest-wide total (budgetAll) */
  budgetAll?: Record<string, string | number>;
  nextSteps: string[];
  /** heroSeries.nextSteps that are general or name this character's cues */
  seriesNextSteps: string[];
  cues: VideoCueView[];
}

export type V2MState = 'done' | 'partial' | 'not-started' | 'n/a';

export interface V2MStage {
  key: 'reference' | 'extraction' | 'retarget' | 'validation' | 'ue';
  label: string;
  state: V2MState;
  detail: string;
}

export interface V2MSlot {
  cue: string;
  clip: string;
  requiredMvp: boolean;
  slotStatus?: string;
  slotStatusLabel?: string;
  stages: V2MStage[];
  currentStage: string;
  blocker: string;
}

export interface V2MSection {
  doc?: FileRef;
  dependencies: { dependency: string; neededFor: string; status: string; who: string }[];
  recommendation: string[];
  harpyNote?: string;
  slots: V2MSlot[];
}

export interface SoundCue {
  cueId: string;
  event: string;
  sound: string;
  durationMs?: string;
  object?: string;
  via: string;
}

export interface SoundSection {
  status: string | null;
  files: FileRef[];
  cues: SoundCue[];
  cueSource?: FileRef;
  searchedRoots: string[];
  /** units of docs/game-design/audio/03-sound-registry.csv that belong to the character (owner column or key in the id) */
  units: CharacterAudioUnit[];
  /** 03-sound-registry.csv (missing → exists: false) */
  registry?: FileRef;
  /** the character's lines in 04-vo-script.md (undefined = no lines for this fighter) */
  vo?: { fighter: string; lines: number; wordless: number; script?: FileRef; log?: FileRef };
}

// ------------------------------------------------------------------ audio (docs/game-design/audio)

export interface AudioUnitView {
  id: string;
  category: string;
  nameRu?: string;
  event?: string;
  trigger?: string;
  bus?: string;
  priority?: string;
  loop?: string;
  scope?: string;
  /** owner column: Arthur / Medusa / Marmoreal / … («-» → undefined) */
  owner?: string;
  sourcePlan?: string;
  license?: string;
  /** registry status, verbatim: in-game / in-bank / template / done-source / none-by-design */
  status: string;
  /** `file` column verbatim (UE path or pattern /Game/Audio/…/SW_*_*, or a path outside git) */
  file?: string;
  /**
   * SoundWave assets in unreal/Unmatched/Content that match `file` (only counted, never served);
   * undefined = `file` is not a /Game/ path or the UE project is not found.
   */
  ueAssets?: number;
  /** notes column, cut to ~200 characters */
  notes?: string;
}

export interface CharacterAudioUnit extends AudioUnitView {
  /** how the unit was attributed to the character: owner column or the character key in the id */
  via: string;
}

export interface AudioVoFighter {
  /** first token of the line id: ARTHUR, MERLIN, MEDUSA, HARPY… */
  fighter: string;
  lines: number;
  /** lines without words (EN «—», or cries in a table without a text column) */
  wordless: number;
}

export interface AudioMixRow {
  map: string;
  /** host / joiner (from <map>-<client>-mix.json) */
  client: string;
  file: FileRef;
  I?: number;
  LRA?: number;
  TP?: number;
  sMax?: number;
  nearPeakShare?: number;
  seconds?: number;
  correctionDb?: number;
  okI?: boolean;
  okTP?: boolean;
  /** the json could not be parsed */
  error?: string;
}

export interface AudioEvidenceFolder {
  /** folder name under docs/game-design/evidence/AUDIO/ (a date) */
  date: string;
  dir: string;
  fileCount: number;
  mixCount: number;
}

export interface AudioOverview {
  root: string;
  docs: DocView[];
  /** 03-sound-registry.csv, 06-task-cards.csv and other tables of the audio folder */
  tables: FileRef[];
  registry: {
    file: FileRef;
    error?: string;
    units: AudioUnitView[];
    byStatus: { status: string; count: number }[];
    byCategory: { category: string; count: number }[];
    /** units with a /Game/ path and status in-game / in-bank but no matching SoundWave in UE */
    missingInUe: string[];
  };
  /** «## 0. Итог» table of 07-production-log.md (first row = header) */
  summary?: { file: FileRef; rows: string[][] };
  vo: { script: FileRef; log: FileRef; total: number; wordless: number; fighters: AudioVoFighter[] };
  ue: {
    contentRoot: string;
    /** null = UE project not found */
    found: boolean | null;
    soundWaves: number;
    /** SoundWaves not covered by any `file` path of the registry (e.g. templates without a path), first 100 */
    unregistered: string[];
    byFolder: { folder: string; count: number }[];
  };
  mix: {
    evidenceRoot: string;
    /** newest evidence folder with *-mix.json */
    latest?: AudioEvidenceFolder & { rows: AudioMixRow[]; targets?: Record<string, string>; files: FileRef[] };
    /** all evidence folders, newest first */
    folders: AudioEvidenceFolder[];
  };
  spends: {
    ledger?: FileRef;
    unit: string;
    /** sum of −Δ over AUC-* entries with Δ < 0 */
    spent: number;
    /** sum of Δ > 0 (refunds) */
    refunds: number;
    balanceStart?: number;
    balanceEnd?: number;
    entries: LedgerEntry[];
  };
}

export interface LedgerEntry {
  service: 'tripo' | 'syntx';
  window: 'pre' | 'window';
  time?: string;
  op?: string;
  delta: number;
  owner?: string;
  ref?: string;
  cue?: string;
  asset?: string;
  model?: string;
  balanceBefore?: number;
  balanceAfter?: number;
  note?: string;
}

export interface CreditsSection {
  tripoUnit: string;
  syntxUnit: string;
  tripoSpent: number;
  syntxSpent: number;
  entries: LedgerEntry[];
}

export interface AssetPage {
  id: string;
  kind: 'character' | 'prop';
  name: string;
  shortName: string;
  category: string;
  inRegistry: boolean;
  instances: number;
  status: string | null;
  stage: string | null;
  backlog: string[];
  parent: string | null;
  group: string;
  nextStep?: string;
  blocker?: string;
  doneCriteria?: string;
  ownership?: Record<string, string>;
  manifest06?: Record<string, string>;
  cuePrefix?: string;
  members: MemberEntry[];
  layers: LayerView[];
  acts: ActView[];
  /** docs/art-pipeline/*-report.* and other pipeline docs for this asset */
  reports: FileRef[];
  acceptanceEvidence: FileRef[];
  statusWarnings: string[];
  discoveredNotes: string[];
  models: ModelsSection;
  rig: RigSection | null;
  clips: ClipSection | null;
  videoRefs: VideoRefSection | null;
  videoToMotion: V2MSection | null;
  sounds: SoundSection | null;
  credits: CreditsSection;
  lastModified?: string;
  /**
   * Freshest registry layer of the page's own entry (by the date in the layer
   * name/paths, ties → later in the list). Its status is shown next to the
   * entry status; the entry status itself is never changed.
   */
  latestLayer?: LatestLayerView;
  /** UE layers /Game/PipelineCandidates/<Folder>/{H2,H2LD,H3LD,Rig,H2Anim,…} (characters only; text only). */
  ueLayers: UeLayersSection | null;
}

export interface LatestLayerView {
  entryId: string;
  layer: string;
  status?: string;
  stage?: string;
  /** YYYY-MM-DD taken from the layer text/paths (run id), when present */
  date?: string;
  /** position in the entry's layers[] */
  index: number;
  /** entry status in the registry (for comparison) */
  entryStatus: string | null;
}

export interface UeLayerView {
  /** folder name under /Game/PipelineCandidates/<Folder>/ (H2, H2LD, Rig…) */
  key: string;
  gamePath: string;
  /** one of the standard hero layers H2 / H2LD / H3LD / Rig / H2Anim */
  standard: boolean;
  /** folder exists in unreal/Unmatched/Content (only checked, never served); null = UE project not found */
  onDisk: boolean | null;
  uassetCount?: number;
  /** registry layers that name this UE path (status copied verbatim) */
  registry: { entryId: string; layer: string; status?: string; stage?: string }[];
  /** clip-manifest slots whose ue.target_path is inside this folder: status → count */
  clipStatuses?: Record<string, number>;
  /** repo documents/reports that mention this UE path */
  mentions: FileRef[];
  mentionsTotal: number;
  /** runs (art/pipeline-candidates/<ASSET>/<run>) whose manifest/reports mention it */
  runs: string[];
}

export interface UeLayersSection {
  folder: string;
  /** how the folder was found: registry / clip-manifest / name */
  folderSource: string;
  layers: UeLayerView[];
}

// ------------------------------------------------------------------ overview sections

export interface DocView {
  file: FileRef;
  title?: string;
  /** YYYY-MM-DD from the file name or a «Дата:» line */
  date?: string;
  /** first «Дата: … Статус: …» line, verbatim (cut) */
  statusLine?: string;
  headings: string[];
}

export interface PlanTaskView {
  id: string;
  title: string;
  track?: string;
  source?: string;
  status: string;
  artStatus: string | null;
  evidence: FileRef[];
  next?: string;
  blocker?: string | null;
  assets: string[];
  updated?: string;
  /** problems with the task record (art status outside vocabulary, acceptance without evidence…) */
  warnings: string[];
}

export interface PlanView {
  file: FileRef;
  exists: boolean;
  error?: string;
  schema?: string;
  generated?: string;
  head?: string;
  sources: { id: string; path: string; title?: string; file?: FileRef }[];
  tasks: PlanTaskView[];
  waves: { id: string; title?: string; status?: string; tasks: string[] }[];
  statusCounts: { status: string; count: number }[];
}

export interface LookdevSheet {
  run: string;
  /** review iteration (i0, c1…) or «preview» for Blender sheets */
  iteration: string;
  file: FileRef;
}

export interface LookdevHeroView {
  /** folder name under art/imagegen/hero-quality-v1/ (medusa, king-arthur…) */
  key: string;
  name: string;
  pageId?: string;
  concepts: FileRef[];
  conceptPrompts?: FileRef;
  docs: DocView[];
  /** UE look-dev sheets «концепт | UE» (review/<iter>/*-lookdev-sheet-*.jpg), newest first */
  ueSheets: LookdevSheet[];
  /** Blender look-dev sheets / comparisons (preview/ld_sheet_*, compare-ld-*, ld_concept_zones_*) */
  blenderSheets: LookdevSheet[];
  /** sheets from docs/art-pipeline/evidence/<…hero…>/ */
  evidenceSheets: FileRef[];
}

export interface LookdevOverview {
  conceptRoot: string;
  references: FileRef[];
  heroes: LookdevHeroView[];
}

export interface MaterialClassView {
  index?: number;
  id: string;
  nameRu?: string;
  family?: string;
  metallic?: number;
  shadingModel?: string;
  baseColorLinear?: number[];
  roughness?: number;
  teamDyeAllowed?: string;
  extension: boolean;
  /** CC0 sets mapped to the class in sources.json */
  sets: string[];
  /** procedural generator when no CC0 set exists */
  procedural?: string;
  tiles: FileRef[];
}

export interface MaterialSetView {
  id: string;
  status?: string;
  class?: string | null;
  license?: string;
  page?: string;
  reason?: string;
  cc0: boolean;
}

export interface MaterialLibraryView {
  root: string;
  docs: DocView[];
  presets?: { file: FileRef; version?: string; date?: string; status?: string };
  classes: MaterialClassView[];
  sources?: { file: FileRef; note?: string; licenseNote?: string; allCC0: boolean };
  sets: MaterialSetView[];
  procedural: { class: string; generator?: string; reason?: string }[];
  tilesSheet?: FileRef;
  evidenceGroups: { group: string; count: number }[];
  evidenceImages: FileRef[];
  evidenceTotal: number;
}

export interface DecisionView extends DocView {
  /** «Происхождение» paragraph (who decided), cut */
  origin?: string;
}

export interface CreditsOverview {
  ledger?: FileRef;
  status?: string;
  tripo: {
    unit: string;
    plan?: string;
    balanceStart?: number;
    balanceEnd?: number;
    spent?: number;
    limit?: number;
    remaining?: number;
    preWindowSpent: number;
    byTask: { task: string; credits: number }[];
    limitNote?: string;
  };
  syntx: {
    unit: string;
    plan?: string;
    balanceStart?: number;
    balanceEnd?: number;
    spent?: number;
    limit?: number;
    remaining?: number;
    limitNote?: string;
  };
  recent: LedgerEntry[];
  unattributed: LedgerEntry[];
}

export interface RecentFile {
  path: string;
  mtime: string;
  bytes: number;
  page?: string;
  servable: boolean;
  kind: FileKind;
}

export interface PipelineHealth {
  registry: {
    file: FileRef;
    snapshotDate?: string;
    /** mtime of asset-registry.json */
    fileMtime?: string;
    /** newest date named by any registry layer (YYYY-MM-DD) */
    latestLayerDate?: string;
    total: number;
    byStatus: { status: string; count: number }[];
    byStage: { stage: string; count: number }[];
    entries: { id: string; name: string; status: string | null; stage: string | null; page: string; nextStep?: string; blocker?: string }[];
  };
  runs: (RunView & { page?: string })[];
  recentFiles: RecentFile[];
  validation: { file?: FileRef; pass: number; fail: number; expectationMet: number; total: number };
  clipCoverage: { assetId: string; character: string; required: number; filled: number; total: number }[];
  reports: FileRef[];
  missingReferenced: { entryId: string; path: string; role?: string }[];
  sources: { path: string; exists: boolean; mtime?: string; error?: string }[];
}

export interface ArtHubData {
  schema: 'unmatched.art-hub/1';
  generatedAt: string;
  /** time of the request that returned this (possibly cached) result */
  checkedAt?: string;
  durationMs: number;
  fingerprint: string;
  vocab: Vocabulary;
  characters: AssetPage[];
  props: AssetPage[];
  credits: CreditsOverview;
  pipelineHealth: PipelineHealth;
  /** docs/art-pipeline/plan-status.json (written by the plan track) */
  plan: PlanView;
  lookdev: LookdevOverview;
  materials: MaterialLibraryView;
  /** game audio: docs/game-design/audio, evidence/AUDIO, AUC-* spends, UE SoundWaves */
  audio: AudioOverview;
  decisions: DecisionView[];
  warnings: string[];
}
