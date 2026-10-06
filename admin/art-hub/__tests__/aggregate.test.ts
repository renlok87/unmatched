import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { ArtHubAggregator, aggregate } from '../aggregate';
import { csvToObjects, mdDecision, mdTableAfterHeading, pathTokens } from '../fs-utils';
import type { ArtHubData, AssetPage } from '../types';
import { BARREL, HERO, makeFixtureRepo, sha, type FixtureRepo } from './fixture-repo';

const REAL_REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

function page(data: ArtHubData, id: string): AssetPage {
  const p = [...data.characters, ...data.props].find((x) => x.id === id);
  if (!p) throw new Error(`page ${id} not found`);
  return p;
}

describe('fs-utils', () => {
  it('parses quoted CSV fields', () => {
    const rows = csvToObjects('a,b\n"x, y","he said ""hi"""\n');
    expect(rows).toEqual([{ a: 'x, y', b: 'he said "hi"' }]);
  });
  it('extracts the decision line of an act', () => {
    expect(mdDecision('# T\n\n**Решение: доработать (v3.1).** Текст')).toBe('Решение: доработать (v3.1). Текст');
    expect(mdDecision('# T\n\nбез решения')).toBeUndefined();
  });
  it('reads a markdown table after a heading', () => {
    const rows = mdTableAfterHeading('## 6. X\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n## 7', /^##\s*6\b/);
    expect(rows).toEqual([
      ['a', 'b'],
      ['1', '2'],
    ]);
  });
  it('finds path tokens in free text', () => {
    expect(pathTokens('art/x/run.json (balance 11:13) и docs/a/b/')).toEqual(['art/x/run.json', 'docs/a/b']);
  });
});

describe('aggregate on a fixture repo', () => {
  let repo: FixtureRepo;
  let data: ArtHubData;

  beforeAll(() => {
    repo = makeFixtureRepo();
    data = aggregate(repo.root);
  });
  afterAll(() => repo.cleanup());

  it('builds characters (registry + stub from animation-refs) and props', () => {
    expect(data.schema).toBe('unmatched.art-hub/1');
    expect(data.characters.map((c) => c.id)).toEqual([HERO, 'ASSET-NEW-001']);
    const stub = page(data, 'ASSET-NEW-001');
    expect(stub.inRegistry).toBe(false);
    expect(stub.status).toBeNull();
    expect(data.props.map((p) => p.id)).toEqual([BARREL, 'ASSET-DECOR-KIT-001.LANTERN']);
  });

  it('keeps registry statuses verbatim and flags unproven acceptance', () => {
    const hero = page(data, HERO);
    expect(hero.status).toBe('измерено');
    expect(hero.members.map((m) => m.id)).toEqual([`${HERO}.WEAPON`]);
    expect(hero.layers[0]?.decision).toBe('доработать v2');
    const lantern = page(data, 'ASSET-DECOR-KIT-001.LANTERN');
    expect(lantern.status).toBe('художественно принято');
    expect(lantern.statusWarnings.join(' ')).toMatch(/без acceptanceEvidence/);
  });

  it('extracts acts, reports and evidence frames', () => {
    const hero = page(data, HERO);
    expect(hero.acts[0]?.decision).toBe('Решение: доработать (v2).');
    expect(hero.acceptanceEvidence).toHaveLength(0);
    expect(hero.reports.map((r) => r.path)).toContain('docs/art-pipeline/hero-candidate-report.md');
    expect(hero.models.evidenceImages.map((r) => r.path)).toContain('docs/game-design/evidence/ART-100/frame-k2.png');
    expect(data.pipelineHealth.missingReferenced.map((m) => m.path)).toContain('docs/art-pipeline/missing-report.md');
  });

  it('collects models with sha checks, previews, textures and runs', () => {
    const hero = page(data, HERO);
    const sk = hero.models.models.find((m) => m.path.endsWith('SK_Hero.fbx'));
    expect(sk?.shaCheck).toBe('match');
    expect(sk?.servable).toBe(true);
    const layerAm = hero.layers[0]?.files.find((f) => f.path.endsWith('AM_Hero_Idle.fbx'));
    expect(layerAm?.shaCheck).toBe('mismatch');
    const ue = hero.layers[0]?.files.find((f) => f.kind === 'ue-asset');
    expect(ue?.exists).toBe(false);
    expect(ue?.servable).toBe(false);
    expect(hero.models.previews.map((p) => p.path)).toEqual(
      expect.arrayContaining([`blender/${HERO}/preview/rig-idle.png`, `art/pipeline-candidates/${HERO}/20260101-run/preview/front.png`]),
    );
    expect(hero.models.textures.map((t) => t.path)).toContain(`blender/${HERO}/textures/T_Hero_BC.png`);
    const run = hero.models.runs.find((r) => r.id === '20260101-run');
    expect(run?.kind).toBe('tripo-pipeline');
    expect(run?.stages[0]).toMatchObject({ name: 'build', status: 'completed' });
    expect(run?.inRegistry).toBe(true);
    expect(hero.models.runs.find((r) => r.id === '20260102-broken')?.inRegistry).toBe(false);
    expect(hero.discoveredNotes.join(' ')).toMatch(/20260102-broken/);
  });

  it('reports a half-written JSON as a warning instead of failing', () => {
    expect(data.warnings.some((w) => w.includes('20260102-broken/manifest.json'))).toBe(true);
  });

  it('attributes the barrel run and default GLB to the barrel page', () => {
    const barrel = page(data, BARREL);
    expect(barrel.models.runs.map((r) => r.id)).toEqual(['20260101-barrel']);
    expect(barrel.models.defaultModel).toMatch(/barrel\.glb$/);
    expect(barrel.models.models[0]?.shaCheck).toBe('match');
    expect(barrel.rig).toBeNull();
  });

  it('builds rig, clips and deform probes', () => {
    const hero = page(data, HERO);
    expect(hero.rig?.skeletonKey).toBe('UM_HUMANOID_17_v1');
    expect(hero.rig?.weaponParent).toBe('hand.R');
    expect(hero.rig?.deformProbes[0]?.tests.map((t) => t.status)).toEqual(['plausible', 'wrong_region']);
    expect(hero.rig?.deformProbes[0]?.sheet?.servable).toBe(true);
    const slots = hero.clips?.slots ?? [];
    expect(slots.map((s) => [s.id, s.statusLabel])).toEqual([
      ['HERO-Idle', 'предложено'],
      ['HERO-Idle-draft', 'черновой тестовый файл'],
    ]);
    expect(slots[1]?.validation.checks.map((c) => c.status)).toEqual(['pass', 'warn']);
    expect(hero.clips?.animationFiles.map((f) => f.path)).toContain(`blender/${HERO}/export/AM_Hero_Idle.fbx`);
    expect(hero.clips?.validationCases).toHaveLength(1);
  });

  it('builds video references with takes, costs and suitability', () => {
    const cue = page(data, HERO).videoRefs?.cues.find((c) => c.cue === 'HERO-Idle');
    expect(cue?.suitability?.verdict).toBe('ограниченно пригоден');
    expect(cue?.takes.map((t) => t.take)).toEqual(['take1', 'take2']);
    const [t1, t2] = cue!.takes;
    expect(t1?.video?.shaCheck).toBe('match');
    expect(t1?.keyframes).toHaveLength(1);
    expect(t1?.analysis?.frames).toBe(121);
    expect(t1?.prompt).toMatch(/hero breathes/);
    expect(t2?.model).toBe('Seedance 1.5 Pro');
    expect(t2?.cost?.tokens).toBe(7.5);
  });

  it('computes the video→skeleton pipeline per slot with a blocker', () => {
    const v2m = page(data, HERO).videoToMotion!;
    expect(v2m.dependencies.map((d) => d.status)).toEqual(['не создан', 'не написано']);
    expect(v2m.harpyNote).toMatch(/Harpy/);
    const slot = v2m.slots[0]!;
    expect(slot.cue).toBe('HERO-Idle');
    expect(slot.stages.map((s) => s.state)).toEqual(['done', 'not-started', 'not-started', 'not-started', 'not-started']);
    expect(slot.currentStage).toBe('Извлечение движения');
    expect(slot.blocker).toMatch(/Rokoko/);
    expect(slot.stages[1]?.detail).toMatch(/HERO-Idle-draft/);
  });

  it('shows sounds as «не начато» with planned cues', () => {
    const s = page(data, HERO).sounds!;
    expect(s.status).toBe('не начато');
    expect(s.files).toHaveLength(0);
    expect(s.cues.map((c) => [c.cueId, c.via])).toEqual([
      ['CUE-017', 'слот клипа'],
      ['CUE-014', 'упоминание персонажа'],
    ]);
  });

  it('attributes credits per asset and keeps units separate', () => {
    const hero = page(data, HERO);
    expect(hero.credits.tripoSpent).toBe(40);
    expect(hero.credits.syntxSpent).toBe(13.5);
    expect(page(data, BARREL).credits.tripoSpent).toBe(15);
    expect(data.credits.unattributed.map((e) => e.op)).toEqual(['Неизвестная трата']);
    expect(data.credits.tripo.spent).toBe(55);
  });

  it('builds pipeline health', () => {
    const h = data.pipelineHealth;
    expect(h.registry.total).toBe(4);
    expect(h.registry.byStatus.map((s) => s.status)).toEqual(['предложено', 'измерено', 'художественно принято']);
    expect(h.runs.length).toBe(3);
    expect(h.recentFiles.length).toBeGreaterThan(5);
    expect(h.clipCoverage).toEqual([{ assetId: HERO, character: 'Hero', required: 1, filled: 0, total: 1 }]);
    expect(h.sources.find((s) => s.path.endsWith('asset-registry.json'))?.exists).toBe(true);
  });

  it('picks up new files live and reuses the cache when nothing changed', () => {
    const agg = new ArtHubAggregator(repo.root);
    const first = agg.get();
    const second = agg.get();
    expect(second.fingerprint).toBe(first.fingerprint);
    expect(second.generatedAt).toBe(first.generatedAt);
    repo.write(`art/audio/${HERO}/hero_attack.wav`, 'RIFF....WAVE');
    const third = agg.get();
    expect(third.fingerprint).not.toBe(first.fingerprint);
    const s = page(third, HERO).sounds!;
    expect(s.files.map((f) => f.path)).toEqual([`art/audio/${HERO}/hero_attack.wav`]);
    expect(s.status).toBeNull();
    fs.rmSync(path.join(repo.root, 'art', 'audio'), { recursive: true, force: true });
  });

  it('survives a repo without any sources', () => {
    const empty = fs.mkdtempSync(path.join(path.dirname(repo.root), 'art-hub-empty-'));
    try {
      const d = aggregate(empty);
      expect(d.characters).toEqual([]);
      expect(d.props).toEqual([]);
      expect(d.warnings.join(' ')).toMatch(/asset-registry\.json/);
      expect(d.audio).toMatchObject({ docs: [], tables: [], registry: { units: [] }, vo: { total: 0 }, ue: { found: null } });
    } finally {
      fs.rmSync(empty, { recursive: true, force: true });
    }
  });
});

describe('video-ref manifest: assets[] and retakes[] shapes', () => {
  let repo: FixtureRepo;
  let data: ArtHubData;
  const heroCue = `art/animation-refs/${HERO}/HERO-Idle`;
  const newCue = 'art/animation-refs/ASSET-NEW-001/NEW-Idle';
  const video = Buffer.from('0123456789abcdefghij');

  beforeAll(() => {
    repo = makeFixtureRepo();
    repo.write(`${newCue}/NEW-Idle_kling25_ref.mp4`, video);
    repo.write(`${heroCue}/take3/HERO-Idle_kling25_take3_ref.mp4`, video); // on disk, no record yet
    repo.write(`art/animation-refs/${HERO}/HERO-HitReact/HERO-HitReact_kling25_ref.mp4`, video); // cue without a record
    repo.write(
      'docs/art-pipeline/animation-refs/manifest.json',
      JSON.stringify({
        assetId: HERO,
        overallStatus: 'референсы, не анимация',
        budget: { spentSyntxTokens: 6 },
        clips: [
          {
            cue: 'HERO-Idle',
            cueRef: 'CUE-017',
            status: 'референс, не анимация',
            suitabilityVideoToMotion: { verdict: 'непригоден (take1)', status: 'оценка по кадрам' },
            output: { path: `${heroCue}/HERO-Idle_kling25_ref.mp4`, sha256: sha(video) },
            retakes: { see: 'retakes[HERO-Idle]', takes: [2, 5], selectedTake: 2 },
          },
        ],
        retakes: [
          {
            cue: 'HERO-Idle',
            selectedTake: 2,
            retakeOf: 'clips[HERO-Idle]',
            takes: [
              {
                cue: 'HERO-Idle',
                take: 2,
                selected: true,
                status: 'референс, не анимация',
                suitabilityVideoToMotion: { verdict: 'пригоден (take2)', status: 'оценка по кадрам' },
                briefFit: { status: 'оценка по кадрам', text: 'вздрагивание есть' },
                whyThisTake: 'take1 дал кровь',
                modelLabel: 'Seedance 1.5 Pro 720p',
                output: { path: `${heroCue}/take2/HERO-Idle_seedance15pro_take2_ref.mp4`, sha256: sha(video) },
              },
              {
                cue: 'HERO-Idle',
                take: 5,
                selected: false,
                suitabilityVideoToMotion: { verdict: 'непригоден (take5)' },
                output: { path: `${heroCue}/take5/HERO-Idle_kling25_take5_ref.mp4` },
                cost: { syntxTokens: 6, balanceBefore: 50, balanceAfter: 44 },
              },
            ],
          },
        ],
        assets: [
          {
            assetId: 'ASSET-NEW-001',
            status: 'референсы героя',
            budget: { spentSyntxTokens: 6, generations: 1, status: 'измерено' },
            clips: [
              {
                cue: 'NEW-Idle',
                selectedTake: 1,
                requiredMvp: true,
                takes: [
                  {
                    cue: 'NEW-Idle',
                    take: 1,
                    selected: true,
                    cueRef: 'CUE-017',
                    status: 'референс, не анимация',
                    suitabilityVideoToMotion: { verdict: 'пригоден как референс тайминга' },
                    modelLabel: 'Kling 2.5 std, 5 с',
                    output: { path: `${newCue}/NEW-Idle_kling25_ref.mp4`, sha256: sha(video) },
                    cost: { syntxTokens: 6, balanceBefore: 94, balanceAfter: 88 },
                  },
                ],
              },
            ],
          },
        ],
        budgetAll: { p1: 6, heroSeries: 19.5, total: 25.5 },
        heroSeries: {
          nextSteps: { status: 'предложено', items: ['HERO-Idle: взять take2', 'NEW-Idle: ставить ключами', 'Импорт в UE не начат', 'ZZZ-Idle: чужой шаг'] },
        },
      }),
    );
    data = aggregate(repo.root);
  });
  afterAll(() => repo.cleanup());

  it('takes the clip verdict from the selected retake, keeps per-take verdicts', () => {
    const vr = page(data, HERO).videoRefs!;
    expect(vr.manifestScopes).toEqual(['верхний уровень (assetId, clips[])', 'retakes[] (HERO-Idle)']);
    expect(vr.budgetAll?.total).toBe(25.5);
    expect(vr.seriesNextSteps).toEqual(['HERO-Idle: взять take2', 'Импорт в UE не начат']);
    const cue = vr.cues.find((c) => c.cue === 'HERO-Idle')!;
    expect(cue.manifestRecords).toEqual(['clips[HERO-Idle]', 'retakes[HERO-Idle]']);
    expect(cue.selectedTake).toBe('take2');
    expect(cue.suitability?.verdict).toBe('пригоден (take2)');
    expect(cue.suitabilityFrom).toBe('take2 — выбранный дубль');
    expect(cue.takes.map((t) => t.take)).toEqual(['take1', 'take2', 'take3', 'take5']);
    const [t1, t2, t3, t5] = cue.takes;
    expect([t1?.selected, t2?.selected, t3?.selected, t5?.selected]).toEqual([false, true, false, false]);
    expect(t1?.suitability?.verdict).toBe('непригоден (take1)');
    expect(t2?.suitability?.verdict).toBe('пригоден (take2)');
    expect(t2?.manifestRecord).toBe('retakes[HERO-Idle].takes[take2]');
    expect(t2?.briefFit).toBe('вздрагивание есть');
    expect(t2?.whyThisTake).toBe('take1 дал кровь');
    expect(t2?.video?.shaCheck).toBe('match');
    expect(t2?.model).toBe('Seedance 1.5 Pro'); // ledger wins over the record label
    // take3 is on disk but not in the manifest; take5 is in the manifest but not on disk
    expect(t3?.video).toBeDefined();
    expect(t3?.manifestRecord).toBeUndefined();
    expect(t3?.suitability).toBeUndefined();
    expect(t5?.video).toBeUndefined();
    expect(t5?.missingVideo).toBe(`${heroCue}/take5/HERO-Idle_kling25_take5_ref.mp4`);
    expect(t5?.cost).toEqual({ tokens: 6, balanceBefore: 50, balanceAfter: 44, source: 'манифест' });

    const stage = page(data, HERO).videoToMotion!.slots.find((s) => s.cue === 'HERO-Idle')!.stages[0]!;
    expect(stage.detail).toMatch(/take2 \(выбран\)/);
    expect(stage.detail).toMatch(/Пригодность \(take2 — выбранный дубль\): пригоден \(take2\)/);
  });

  it('says «не оценена» only for videos without any record', () => {
    const hero = page(data, HERO);
    const hit = hero.videoRefs!.cues.find((c) => c.cue === 'HERO-HitReact')!;
    expect(hit.manifestRecords).toEqual([]);
    expect(hit.suitability).toBeUndefined();
    const notes = hero.discoveredNotes.join('\n');
    expect(notes).toMatch(/Ролики без записи в docs\/art-pipeline\/animation-refs\/manifest\.json.*HERO-Idle take3, HERO-HitReact take1/);
    expect(notes).not.toMatch(/нет манифеста/);
  });

  it('reads a character described only in assets[]', () => {
    const p = page(data, 'ASSET-NEW-001');
    const vr = p.videoRefs!;
    expect(vr.manifest?.path).toBe('docs/art-pipeline/animation-refs/manifest.json');
    expect(vr.manifestScopes).toEqual(['assets[ASSET-NEW-001]']);
    expect(vr.overallStatus).toBe('референсы героя');
    expect(vr.budget).toEqual({ spentSyntxTokens: 6, generations: 1, status: 'измерено' });
    expect(vr.budgetLabel).toMatch(/assets\[ASSET-NEW-001\]\.budget/);
    expect(vr.seriesNextSteps).toEqual(['NEW-Idle: ставить ключами', 'Импорт в UE не начат']);
    const cue = vr.cues.find((c) => c.cue === 'NEW-Idle')!;
    expect(cue.suitability?.verdict).toBe('пригоден как референс тайминга');
    expect(cue.requiredMvp).toBe(true);
    expect(cue.cueRef).toBe('CUE-017');
    const t1 = cue.takes[0]!;
    expect(t1.selected).toBe(true);
    expect(t1.video?.shaCheck).toBe('match');
    expect(t1.model).toBe('Kling 2.5 std, 5 с');
    expect(t1.cost).toEqual({ tokens: 6, balanceBefore: 94, balanceAfter: 88, source: 'манифест' });
    expect(p.discoveredNotes.join('\n')).not.toMatch(/пригодность не оценена/);
    const stage = p.videoToMotion!.slots.find((s) => s.cue === 'NEW-Idle')!.stages[0]!;
    expect(stage.detail).toMatch(/Пригодность \(take1 — выбранный дубль\): пригоден как референс тайминга/);
  });
});

describe('aggregate on the real repo', () => {
  const hasRegistry = fs.existsSync(path.join(REAL_REPO, 'docs', 'art-pipeline', 'asset-registry.json'));

  it.skipIf(!hasRegistry)('does not crash and finds Medusa, the barrel, videos and clips', () => {
    const d = aggregate(REAL_REPO);
    const medusa = d.characters.find((c) => c.id === 'ASSET-MEDUSA-001');
    expect(medusa).toBeDefined();
    expect(medusa!.models.models.some((m) => m.kind === 'glb' && m.servable)).toBe(true);
    expect(medusa!.models.defaultModel).toBeTruthy();
    const videos = medusa!.videoRefs!.cues.flatMap((c) => c.takes.filter((t) => t.video));
    expect(videos.length).toBeGreaterThanOrEqual(4);
    expect(medusa!.clips!.slots.some((s) => s.id === 'MED-Idle')).toBe(true);
    expect(medusa!.clips!.animationFiles.some((f) => /AM_Medusa_Idle\.fbx$/.test(f.path))).toBe(true);
    expect(medusa!.rig!.bones.length).toBeGreaterThanOrEqual(17);
    expect(medusa!.videoToMotion!.slots.length).toBeGreaterThanOrEqual(4);
    expect(medusa!.credits.entries.length).toBeGreaterThan(0);
    // statuses are copied, never upgraded
    expect(medusa!.status).not.toBe('художественно принято');

    const barrel = d.props.find((p) => p.id === 'ASSET-DECOR-KIT-001.BARREL');
    expect(barrel).toBeDefined();
    expect(barrel!.models.models.some((m) => m.path.endsWith('.glb'))).toBe(true);
    expect(barrel!.models.runs.length).toBeGreaterThanOrEqual(1);

    const ids = d.characters.map((c) => c.id);
    expect(ids).toEqual(expect.arrayContaining(['ASSET-KING-ARTHUR-001', 'ASSET-MERLIN-001', 'ASSET-HARPY-001']));
    expect(d.characters.find((c) => c.id === 'ASSET-HARPY-001')?.instances).toBe(3);
    // verdicts from assets[] / retakes[] reach the page (live data: only when the manifest has them)
    for (const id of ['ASSET-KING-ARTHUR-001', 'ASSET-MERLIN-001', 'ASSET-HARPY-001']) {
      const vr = d.characters.find((c) => c.id === id)?.videoRefs;
      if (vr?.manifestScopes.includes(`assets[${id}]`)) expect(vr.cues.some((c) => c.suitability?.verdict)).toBe(true);
    }
    for (const cue of medusa!.videoRefs!.cues) {
      if (cue.selectedTake && cue.suitability) expect(cue.suitabilityFrom).toBe(`${cue.selectedTake} — выбранный дубль`);
    }
    expect(d.pipelineHealth.registry.total).toBeGreaterThan(10);
  });
});
