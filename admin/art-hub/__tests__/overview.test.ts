import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { ArtHubAggregator, aggregate } from '../aggregate';
import { parseVoScript, uePatternRe } from '../audio';
import { heroSlug, latestLayerOf, newestDate } from '../overview';
import type { ArtHubData, AssetPage, LayerView } from '../types';
import { AUDIO_LONG_NOTE, HERO, addAudioFixtures, addOverviewFixtures, makeFixtureRepo, type FixtureRepo } from './fixture-repo';

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

  it('counts VO lines per fighter: text rows, wordless rows, cry ranges', () => {
    const md = [
      '| ARTHUR-ATTACK-01 | For Camelot! | За Камелот! | [firm] |',
      '| ARTHUR-HURT-01 | — | — | [grunts] |',
      '| King Arthur | голос | пробы |',
      '| HARPY-ATTACK-01…03 | визг | коротко |',
      '| HARPY-HURT-01..02 | клёкот | 0,2 с |',
      '| HARPY-RETURN-01 | визг | 0,6 с |',
    ].join('\r\n');
    expect(parseVoScript(md)).toEqual([
      { fighter: 'ARTHUR', lines: 2, wordless: 1 },
      { fighter: 'HARPY', lines: 6, wordless: 6 },
    ]);
  });

  it('turns registry UE paths into asset patterns', () => {
    const star = uePatternRe('/Game/Audio/VO/Arthur/SW_VO_ARTHUR_ATTACK_*')!;
    expect(star.test('unreal/Unmatched/Content/Audio/VO/Arthur/SW_VO_ARTHUR_ATTACK_03.uasset')).toBe(true);
    expect(star.test('unreal/Unmatched/Content/Audio/VO/Arthur/sub/SW_VO_ARTHUR_ATTACK_03.uasset')).toBe(false);
    const exact = uePatternRe('/Game/Audio/UI/SW_UI_TOAST')!;
    expect(['SW_UI_TOAST', 'SW_UI_TOAST_01', 'SW_UI_TOAST_GO_01'].map((n) => exact.test(`unreal/Unmatched/Content/Audio/UI/${n}.uasset`))).toEqual([true, true, false]);
    expect(uePatternRe('C:/tmp/audio-src/MOT-DUEL.mid')).toBeUndefined();
    expect(uePatternRe(undefined)).toBeUndefined();
  });
});

describe('audio section on a fixture repo', () => {
  let repo: FixtureRepo;
  let data: ArtHubData;

  beforeAll(() => {
    repo = makeFixtureRepo();
    addAudioFixtures(repo);
    data = aggregate(repo.root);
  });
  afterAll(() => repo.cleanup());

  it('counts registry units by status and category, matches UE SoundWaves', () => {
    const r = data.audio.registry;
    expect(r.file).toMatchObject({ exists: true, servable: true });
    expect(r.error).toBeUndefined();
    expect(r.byStatus).toEqual([
      { status: 'in-game', count: 4 },
      { status: 'in-bank', count: 1 },
      { status: 'done-source', count: 1 },
      { status: 'template', count: 1 },
      { status: 'none-by-design', count: 1 },
    ]);
    expect(r.byCategory.map((c) => [c.category, c.count])).toEqual([
      ['fx', 2],
      ['ui', 2],
      ['vo', 2],
      ['combat', 1],
      ['motif', 1],
    ]);
    const byId = new Map(r.units.map((u) => [u.id, u]));
    // each asset counts once, for the most specific pattern; a name without * takes its _NN variants
    expect(['VO-HERO-ATTACK', 'VO-HERO-ATTACK-BIG', 'FX-HERO-SLASH', 'FX-GLARE', 'UI-BTN-HOVER', 'CMB-HIT-BLUNT', 'MOT-DUEL'].map((id) => byId.get(id)!.ueAssets)).toEqual([
      2, 1, 1, 0, 1, undefined, undefined,
    ]);
    expect(r.missingInUe).toEqual(['FX-GLARE']);
    expect(byId.get('UI-BTN-HOVER')).toMatchObject({ status: 'in-bank', owner: undefined, notes: 'AU-S5: не звучит, нет события "hover"' });
    expect(byId.get('MOT-DUEL')!.file).toBe('C:/tmp/audio-src/sketches/MOT-DUEL.mid|.wav (вне git)');
    const note = byId.get('VO-HERO-ATTACK')!.notes!;
    expect(AUDIO_LONG_NOTE.length).toBeGreaterThan(200);
    expect(note).toHaveLength(200);
    expect(note.endsWith('…')).toBe(true);
    const ue = data.audio.ue;
    expect(ue).toMatchObject({ found: true, soundWaves: 6, unregistered: ['unreal/Unmatched/Content/Audio/Combat/SW_CMB_HIT_BLUNT_01.uasset'] });
    expect(ue.byFolder).toEqual([
      { folder: 'Combat', count: 1 },
      { folder: 'FX', count: 1 },
      { folder: 'UI', count: 1 },
      { folder: 'VO/Hero', count: 3 },
    ]);
  });

  it('reads VO counts, the 07 summary, docs and tables', () => {
    const a = data.audio;
    expect(a.vo).toMatchObject({ total: 7, wordless: 5 });
    expect(a.vo.fighters).toEqual([
      { fighter: 'HERO', lines: 3, wordless: 1 },
      { fighter: 'HARPY', lines: 4, wordless: 4 },
    ]);
    expect(a.vo.script.servable).toBe(true);
    expect(a.summary?.rows).toEqual([
      ['Слой', 'Статус', 'Где'],
      ['Реплики', 'в игре', '/Game/Audio/VO/'],
    ]);
    expect(a.docs.map((d) => [d.file.path.split('/').pop(), d.title])).toEqual([
      ['00-AUDIO-BRIEF.md', 'Звук: бриф'],
      ['04-vo-script.md', '04 — Реплики'],
      ['07-production-log.md', '07 — Журнал производства'],
    ]);
    expect(a.docs[0]).toMatchObject({ date: '2026-01-03', headings: ['1. Цель', '2. Объём'] });
    expect(a.docs.every((d) => d.file.servable)).toBe(true);
    expect(a.tables.map((t) => [t.path.split('/').pop(), t.role, t.servable])).toEqual([
      ['03-sound-registry.csv', 'реестр единиц звука', true],
      ['06-task-cards.csv', 'карточки задач производства', true],
    ]);
    const src = data.pipelineHealth.sources.find((s) => s.path === 'docs/game-design/audio/03-sound-registry.csv');
    expect(src).toMatchObject({ exists: true });
  });

  it('shows the newest mix evidence; a half-written mix json is a warning', () => {
    const mix = data.audio.mix;
    expect(mix.folders.map((f) => [f.date, f.fileCount, f.mixCount])).toEqual([
      ['2026-01-04', 4, 3],
      ['2026-01-03', 1, 0],
    ]);
    const latest = mix.latest!;
    expect(latest.date).toBe('2026-01-04');
    expect(latest.rows.map((r) => [r.map, r.client, r.I, r.TP, r.sMax, r.seconds, r.okI, r.okTP, r.error])).toEqual([
      ['arena', 'host', -19.8, -1.5, -16.8, 60.5, true, true, undefined],
      ['arena', 'joiner', -23.1, -2, -19, 58, false, true, undefined],
      ['broken', 'host', undefined, undefined, undefined, undefined, undefined, undefined, 'не разобран'],
    ]);
    expect(latest.targets).toEqual({ I: '-20.0 ±2.0', TP_max: '-1' });
    expect(latest.files[0]).toMatchObject({ kind: 'image', servable: true });
    expect(data.warnings.join('\n')).toMatch(/broken-host-mix\.json/);
  });

  it('sums AUC-* spends and takes them out of the unattributed list', () => {
    const s = data.audio.spends;
    expect(s.entries.map((e) => e.cue)).toEqual(['AUC-V01', 'AUC-M01', 'AUC-M01']);
    expect(s).toMatchObject({ unit: 'токены SYNTX', spent: 12.5, refunds: 1, balanceStart: 86.5, balanceEnd: 75 });
    expect(s.ledger?.path).toBe('docs/art-pipeline/evidence/baseline/credits-ledger.json');
    expect(data.credits.unattributed.map((e) => e.op)).toEqual(['Неизвестная трата']);
    expect(page(data, HERO).credits.syntxSpent).toBe(13.5);
  });

  it('adds the character units and VO lines to the «Звуки» tab', () => {
    const s = page(data, HERO).sounds!;
    expect(s.units.map((u) => [u.id, u.via])).toEqual([
      ['VO-HERO-ATTACK', 'владелец (owner)'],
      ['VO-HERO-ATTACK-BIG', 'владелец (owner)'],
      ['FX-HERO-SLASH', 'ключ в id'],
      ['FX-GLARE', 'владелец (owner)'],
    ]);
    expect(s.vo).toMatchObject({ fighter: 'HERO', lines: 3, wordless: 1 });
    expect(s.registry?.exists).toBe(true);
    // the file scan and the CUE table stay
    expect(s.files.map((f) => f.path)).toContain('unreal/Unmatched/Content/Audio/VO/Hero/SW_VO_HERO_ATTACK_01.uasset');
    expect(s.cues.map((c) => c.cueId)).toEqual(['CUE-017', 'CUE-014']);
    const stub = page(data, 'ASSET-NEW-001').sounds!;
    expect([stub.units, stub.vo]).toEqual([[], undefined]);
  });

  it('rebuilds when new mix evidence appears (audio files are part of the fingerprint)', () => {
    const agg = new ArtHubAggregator(repo.root);
    const first = agg.get();
    expect(agg.get().fingerprint).toBe(first.fingerprint);
    const rel = 'docs/game-design/evidence/AUDIO/2026-01-05/arena-host-mix.json';
    repo.write(rel, JSON.stringify({ I: -20.1, TP: -1.2, ok_I: true, ok_TP: true }));
    const second = agg.get();
    expect(second.fingerprint).not.toBe(first.fingerprint);
    expect(second.audio.mix.latest?.date).toBe('2026-01-05');
    expect(second.audio.mix.latest?.rows.map((r) => r.I)).toEqual([-20.1]);
    // audio files stay out of the art «recent files»
    expect(second.pipelineHealth.recentFiles.some((f) => /^docs\/game-design\/(audio|evidence\/AUDIO)\//.test(f.path))).toBe(false);
    fs.rmSync(path.join(repo.root, 'docs', 'game-design', 'evidence', 'AUDIO', '2026-01-05'), { recursive: true, force: true });
  });
});

describe('audio section without audio files', () => {
  let repo: FixtureRepo;

  beforeAll(() => {
    repo = makeFixtureRepo();
  });
  afterAll(() => repo.cleanup());

  it('gives an empty section and no warnings', () => {
    const d = aggregate(repo.root);
    const a = d.audio;
    expect(a.registry).toMatchObject({ units: [], byStatus: [], missingInUe: [] });
    expect(a.registry.file.exists).toBe(false);
    expect(a.vo).toMatchObject({ total: 0, fighters: [] });
    expect([a.mix.latest, a.mix.folders, a.docs, a.tables, a.summary]).toEqual([undefined, [], [], [], undefined]);
    expect(a.ue).toMatchObject({ found: false, soundWaves: 0, unregistered: [] });
    expect(a.spends).toMatchObject({ spent: 0, entries: [] });
    expect(d.warnings.join('\n')).not.toMatch(/audio|звук/i);
    expect(d.pipelineHealth.sources.find((s) => s.path.endsWith('03-sound-registry.csv'))?.error).toBe('нет файла');
    expect(page(d, HERO).sounds).toMatchObject({ units: [], vo: undefined });
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

  const hasAudio = fs.existsSync(path.join(REAL_REPO, 'docs', 'game-design', 'audio', '03-sound-registry.csv'));

  it.skipIf(!hasAudio)('builds the audio section: registry, VO, mix evidence, spends, character units', () => {
    const d = aggregate(REAL_REPO);
    const a = d.audio;
    expect(a.registry.units.length).toBeGreaterThan(100);
    expect(a.registry.byStatus.find((s) => s.status === 'in-game')?.count).toBeGreaterThan(100);
    expect(a.registry.byStatus.reduce((n, s) => n + s.count, 0)).toBe(a.registry.units.length);
    expect(a.vo.fighters.map((f) => f.fighter)).toEqual(expect.arrayContaining(['ARTHUR', 'MERLIN', 'MEDUSA', 'HARPY']));
    expect(a.vo.total).toBeGreaterThan(100);
    expect(a.docs.length).toBeGreaterThanOrEqual(6);
    expect(a.docs.every((x) => x.file.servable)).toBe(true);
    expect(a.summary?.rows.length).toBeGreaterThan(2);
    const latest = a.mix.latest!;
    expect(latest.rows.length).toBeGreaterThanOrEqual(4);
    expect(latest.rows.every((r) => r.I !== undefined && r.TP !== undefined && !r.error)).toBe(true);
    expect(latest.targets?.I).toBeTruthy();
    expect(a.spends.entries.length).toBeGreaterThan(0);
    expect(a.spends.spent).toBeGreaterThan(0);
    expect(d.credits.unattributed.some((e) => /^AUC-/.test(e.cue ?? ''))).toBe(false);
    if (a.ue.found) expect(a.ue.soundWaves).toBeGreaterThan(100);
    for (const id of ['ASSET-MEDUSA-001', 'ASSET-KING-ARTHUR-001', 'ASSET-MERLIN-001', 'ASSET-HARPY-001']) {
      const s = page(d, id).sounds!;
      expect(s.units.length).toBeGreaterThan(5);
      expect(s.vo?.lines).toBeGreaterThan(5);
    }
    expect(d.warnings.filter((w) => /audio|AUDIO|звук/.test(w))).toEqual([]);
  });
});
