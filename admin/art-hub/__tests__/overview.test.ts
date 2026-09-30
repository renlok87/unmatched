import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { ArtHubAggregator, aggregate } from '../aggregate';
import { heroSlug, latestLayerOf, newestDate } from '../overview';
import type { ArtHubData, AssetPage, LayerView } from '../types';
import { HERO, addOverviewFixtures, makeFixtureRepo, type FixtureRepo } from './fixture-repo';

const REAL_REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

function page(data: ArtHubData, id: string): AssetPage {
  const p = [...data.characters, ...data.props].find((x) => x.id === id);
  if (!p) throw new Error(`page ${id} not found`);
  return p;
}

describe('overview helpers', () => {
  it('finds the newest date in run ids and ISO dates', () => {
    expect(newestDate(['20260928-cli-um-fbx-v1', 'x 2026-09-29 y', 'sha 9f20261399aa'])).toBe('2026-09-29');
    expect(newestDate(['без даты'])).toBeUndefined();
  });

  it('picks the freshest layer by date, ties by position', () => {
    const l = (layer: string, status: string, files: string[] = []): LayerView => ({
      entryId: 'A',
      layer,
      status,
      files: files.map((p) => ({ path: p, root: 'repo', kind: 'other', exists: true, servable: false })),
    });
    const layers = [
      l('blockout', 'технически импортировано'),
      l('cli 20260928-cli', 'измерено'),
      l('w4b', 'измерено', ['art/pipeline-candidates/A/20260929-w4b/manifest.json']),
      l('ue 20260929-h2-ue-import', 'технически импортировано'),
      { ...l('other entry 20261231', 'предложено'), entryId: 'B' },
    ];
    const latest = latestLayerOf(layers, 'A', 'предложено')!;
    expect(latest.layer).toBe('ue 20260929-h2-ue-import');
    expect(latest).toMatchObject({ status: 'технически импортировано', date: '2026-09-29', index: 3, entryStatus: 'предложено' });
    expect(latestLayerOf([], 'A', null)).toBeUndefined();
  });

  it('maps asset ids to concept folder slugs', () => {
    expect(heroSlug('ASSET-KING-ARTHUR-001')).toBe('king-arthur');
    expect(heroSlug('ASSET-MEDUSA-001')).toBe('medusa');
  });
});

describe('overview sections on a fixture repo', () => {
  let repo: FixtureRepo;
  let data: ArtHubData;

  beforeAll(() => {
    repo = makeFixtureRepo();
    addOverviewFixtures(repo);
    data = aggregate(repo.root);
  });
  afterAll(() => repo.cleanup());

  it('shows the freshest layer status next to the unchanged entry status', () => {
    const hero = page(data, HERO);
    expect(hero.status).toBe('измерено');
    expect(hero.latestLayer).toMatchObject({ status: 'технически импортировано', date: '2026-01-02', entryStatus: 'измерено' });
    const reg = data.pipelineHealth.registry;
    expect(reg.snapshotDate).toBe('2026-01-01');
    expect(reg.latestLayerDate).toBe('2026-01-02');
    expect(reg.fileMtime).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it('builds UE layers from the registry, clip-manifest, docs and the UE folder', () => {
    const ue = page(data, HERO).ueLayers!;
    expect(ue.folder).toBe('Hero');
    expect(ue.folderSource).toBe('реестр');
    const byKey = new Map(ue.layers.map((l) => [l.key, l]));
    expect(byKey.get('H2LD')).toMatchObject({ onDisk: true, uassetCount: 1, standard: true, gamePath: '/Game/PipelineCandidates/Hero/H2LD' });
    expect(byKey.get('H2LD')!.registry.map((r) => r.status)).toEqual(['технически импортировано']);
    expect(byKey.get('H2LD')!.mentions.map((m) => m.path)).toContain('docs/art-pipeline/hero-lookdev-v2.md');
    expect(byKey.get('Rig')).toMatchObject({ onDisk: true, registry: [] });
    expect(byKey.get('H2Anim')).toMatchObject({ onDisk: false, clipStatuses: { technically_imported: 1 } });
    const h3 = byKey.get('H3LD')!;
    expect([h3.onDisk, h3.registry.length, h3.mentionsTotal, h3.clipStatuses]).toEqual([false, 0, 0, undefined]);
    // UE paths are text: nothing under unreal/ is servable
    for (const l of ue.layers) for (const m of l.mentions) expect(m.path.startsWith('unreal/')).toBe(false);
    // props get no UE layer section
    expect(data.props.every((p) => p.ueLayers === null)).toBe(true);
  });

  it('collects look-dev docs, concepts and sheets per hero', () => {
    const hero = data.lookdev.heroes.find((h) => h.key === 'hero')!;
    expect(hero.pageId).toBe(HERO);
    expect(hero.concepts.map((c) => c.path)).toEqual(['art/imagegen/hero-quality-v1/hero/hero-front.png']);
    expect(hero.concepts[0]!.servable).toBe(true);
    expect(hero.conceptPrompts?.path).toBe('art/imagegen/hero-quality-v1/hero/prompts.md');
    expect(hero.docs[0]).toMatchObject({ title: 'Hero look-dev v2', date: '2026-01-02' });
    expect(hero.docs[0]!.statusLine).toMatch(/^Дата: 2026-01-02\. Статус: измерено/);
    expect(hero.docs[0]!.headings).toEqual(['1. Что выпущено', '2. UE']);
    expect(hero.ueSheets.map((s) => [s.run, s.iteration])).toEqual([['20260101-run', 'i1']]);
    expect(hero.ueSheets[0]!.file.servable).toBe(true);
    expect(hero.blenderSheets).toHaveLength(1);
    expect(data.lookdev.references.map((r) => r.path)).toEqual(['art/imagegen/hero-quality-v1/reference/quality-reference.png']);
  });

  it('reads the material library: classes, CC0 sets, procedural classes, tiles, evidence', () => {
    const m = data.materials;
    expect(m.presets).toMatchObject({ version: 'v1', date: '2026-01-02', status: 'предложено' });
    expect(m.classes.map((c) => [c.id, c.extension])).toEqual([
      ['steel', false],
      ['silk', false],
      ['horn', true],
    ]);
    const steel = m.classes[0]!;
    expect(steel).toMatchObject({ sets: ['Metal001'], metallic: 1, roughness: 0.3, baseColorLinear: [0.5, 0.5, 0.5] });
    expect(steel.tiles.map((t) => t.path)).toEqual(['art/material-library/v1/tiles/steel/steel_DetailN.png']);
    expect(m.classes[1]!.procedural).toBe('procedural:satin5');
    expect(m.sets.map((s) => [s.id, s.cc0])).toEqual([
      ['Metal001', true],
      ['Bad001', false],
    ]);
    expect(m.sources?.allCC0).toBe(false);
    expect(data.warnings.join('\n')).toMatch(/без лицензии CC0: Bad001/);
    expect(m.docs.map((d) => d.title)).toEqual(['Библиотека материалов']);
    expect(m.evidenceTotal).toBe(1);
    expect(m.evidenceGroups).toEqual([{ group: 'v2/master', count: 2 }]);
    expect(m.tilesSheet).toBeUndefined();
  });

  it('lists decision logs with date, headings and origin; markdown is servable', () => {
    expect(data.decisions).toHaveLength(1);
    const d = data.decisions[0]!;
    expect(d).toMatchObject({ title: 'Журнал решений: герой', date: '2026-01-02', headings: ['D-1. Первое', 'D-2. Второе'] });
    expect(d.origin).toMatch(/^Происхождение\. Решения принял оркестратор/);
    expect(d.file.servable).toBe(true);
  });

  it('shows a placeholder until plan-status.json exists, then parses it (cache follows the file)', () => {
    const agg = new ArtHubAggregator(repo.root);
    const before = agg.get();
    expect(before.plan.exists).toBe(false);
    expect(before.plan.tasks).toEqual([]);
    expect(before.pipelineHealth.sources.find((s) => s.path.endsWith('plan-status.json'))?.error).toMatch(/нет файла/);

    repo.write(
      'docs/art-pipeline/plan-status.json',
      JSON.stringify({
        schema: 'unmatched-plan-status/v1',
        generated: '2026-01-03T10:00:00Z',
        head: 'abc1234',
        sources: [
          { id: 'stage3', path: 'C:/tmp/p0-review/stage3-final.md', title: 'План этапа 3' },
          { id: 'registry', path: 'docs/art-pipeline/asset-registry.json', title: 'Реестр' },
        ],
        tasks: [
          { id: 'P0-1', title: 'CLI', track: 'pipeline', source: 'stage3', status: 'done', art_status: 'технически импортировано', evidence: ['docs/art-pipeline/hero-lookdev-v2.md'], next: null, blocker: null, assets: [HERO], updated: '2026-01-03T10:00:00Z' },
          { id: 'ART-1', title: 'Приёмка', track: 'art', status: 'in_progress', art_status: 'художественно принято', evidence: ['docs/art-pipeline/missing.md', 'C:/tmp/outside.md'], next: 'акт', blocker: null, assets: [] },
          { id: 'W5c-B', title: 'Волна', track: 'tech', status: 'open', art_status: 'готово', evidence: [], assets: [] },
        ],
        waves: [{ id: 'W5c-B', title: 'Волна 5c-B', status: 'open', tasks: ['W5c-B', 'P0-1', 'X-404'] }],
      }),
    );
    const after = agg.get();
    expect(after.fingerprint).not.toBe(before.fingerprint);
    const plan = after.plan;
    expect(plan).toMatchObject({ exists: true, schema: 'unmatched-plan-status/v1', head: 'abc1234' });
    expect(plan.tasks.map((t) => t.id)).toEqual(['P0-1', 'ART-1', 'W5c-B']);
    expect(plan.tasks[0]!.warnings).toEqual([]);
    expect(plan.tasks[0]!.evidence[0]).toMatchObject({ exists: true, servable: true });
    const art1 = plan.tasks[1]!;
    expect(art1.warnings.join(' ')).toMatch(/без акта приёмки/);
    expect(art1.warnings.join(' ')).toMatch(/нет файлов доказательств: docs\/art-pipeline\/missing\.md/);
    expect(art1.evidence[1]).toMatchObject({ path: 'C:/tmp/outside.md', exists: null, servable: false });
    expect(plan.tasks[2]!.warnings.join(' ')).toMatch(/вне словаря/);
    expect(plan.statusCounts).toEqual([
      { status: 'in_progress', count: 1 },
      { status: 'open', count: 1 },
      { status: 'done', count: 1 },
    ]);
    expect(plan.sources[0]!.file).toMatchObject({ exists: null, servable: false });
    expect(plan.sources[1]!.file?.exists).toBe(true);
    expect(plan.waves[0]!.tasks).toEqual(['W5c-B', 'P0-1', 'X-404']);

    repo.write('docs/art-pipeline/plan-status.json', '{ "schema": "unmatched-plan-status/v1", ');
    const broken = agg.get();
    expect(broken.plan.exists).toBe(true);
    expect(broken.plan.error).toBeTruthy();
    expect(broken.warnings.join('\n')).toMatch(/plan-status\.json/);
    fs.rmSync(path.join(repo.root, 'docs', 'art-pipeline', 'plan-status.json'));
  });

  it('rebuilds when a UE layer folder appears (UE tree is part of the fingerprint)', () => {
    const agg = new ArtHubAggregator(repo.root);
    const first = agg.get();
    expect(agg.get().fingerprint).toBe(first.fingerprint);
    repo.write('unreal/Unmatched/Content/PipelineCandidates/Hero/H3LD/SK_Hero_H3LD.uasset', 'uasset-h3ld');
    const second = agg.get();
    expect(second.fingerprint).not.toBe(first.fingerprint);
    expect(page(second, HERO).ueLayers!.layers.find((l) => l.key === 'H3LD')).toMatchObject({ onDisk: true, uassetCount: 1 });
    fs.rmSync(path.join(repo.root, 'unreal', 'Unmatched', 'Content', 'PipelineCandidates', 'Hero', 'H3LD'), { recursive: true, force: true });
  });
});

describe('overview sections on the real repo', () => {
  const hasRegistry = fs.existsSync(path.join(REAL_REPO, 'docs', 'art-pipeline', 'asset-registry.json'));

  it.skipIf(!hasRegistry)('takes the registry date from the file and finds heroes, look-dev, materials and decisions', () => {
    const d = aggregate(REAL_REPO);
    const reg = d.pipelineHealth.registry;
    const raw = JSON.parse(fs.readFileSync(path.join(REAL_REPO, 'docs', 'art-pipeline', 'asset-registry.json'), 'utf8')) as { snapshotDate?: string; assets: unknown[] };
    expect(reg.snapshotDate).toBe(raw.snapshotDate);
    expect(reg.total).toBe(raw.assets.length);
    for (const id of ['ASSET-MEDUSA-001', 'ASSET-KING-ARTHUR-001', 'ASSET-MERLIN-001', 'ASSET-HARPY-001']) {
      const p = page(d, id);
      expect(p.ueLayers?.layers.map((l) => l.key)).toEqual(expect.arrayContaining(['H2', 'H2LD', 'H3LD', 'Rig', 'H2Anim']));
      // never upgraded beyond the registry vocabulary; no artistic acceptance from layers
      expect(p.latestLayer?.status).not.toBe('художественно принято');
      expect(d.lookdev.heroes.some((h) => h.pageId === id)).toBe(true);
    }
    expect(d.materials.classes.length).toBeGreaterThan(5);
    expect(d.materials.sets.length).toBeGreaterThan(0);
    expect(d.decisions.length).toBeGreaterThan(0);
    expect(d.decisions.every((x) => x.file.servable)).toBe(true);
  });
});
