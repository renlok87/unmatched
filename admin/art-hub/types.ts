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
  warnings: string[];
}
