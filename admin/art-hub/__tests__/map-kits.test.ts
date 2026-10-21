import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { ArtHubAggregator, aggregate } from '../aggregate';
import { mapKitRoots, walkMapKits } from '../map-kits';
import type { ArtHubData, MapKitView } from '../types';
import { addMapKitFixtures, makeFixtureRepo, type FixtureRepo } from './fixture-repo';

const REAL_REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

const mapOf = (d: ArtHubData, id: string): MapKitView => {
  const m = d.mapKits.maps.find((x) => x.id === id);
  if (!m) throw new Error(`map ${id} not found`);
  return m;
};

describe('map kits section on a fixture repo', () => {
  let repo: FixtureRepo;
  let data: ArtHubData;

  beforeAll(() => {
    repo = makeFixtureRepo();
    addMapKitFixtures(repo);
    data = aggregate(repo.root);
  });
  afterAll(() => repo.cleanup());

  it('lists the map folders in name order and ignores folders without json', () => {
    const k = data.mapKits;
    expect(k).toMatchObject({ root: 'docs/art-pipeline/map-kits', found: true });
    expect(k.maps.map((m) => m.id)).toEqual(['alpha', 'beta', 'broken', 'gamma']);
    expect(k.totals).toMatchObject({ maps: 4, props: 4 + 2 + 1, credits: 235 });
  });

  it('reads the map description: names, topology, heroes, palette, scope', () => {
    const m = mapOf(data, 'alpha');
    expect(m).toMatchObject({
      boardName: 'Alpha Manor',
      boardNameRu: 'Усадьба Альфа',
      set: 'Cobble & Fog',
      boardId: 'cboard-alpha',
      topology: { field: 'AlphaManor', cells: 32, edges: 52 },
      heroes: ['Hero One', 'Hero Two'],
      whyChosenRu: 'почему выбрана',
      moodRu: 'настроение',
      lightingRu: 'свет',
      backdropRu: 'задник',
      scopeNoteRu: 'границы работы',
      styleEn: 'stylized miniature',
      scale: 'game height = real height x 0.3',
      statusUpdatedAt: '2026-10-21T10:00:00+05:00',
    });
    // only real colours reach the page (they go into inline styles)
    expect(m.paletteHex).toEqual(['#112233', '#abc']);
    expect(m.files.map).toMatchObject({ path: 'docs/art-pipeline/map-kits/alpha/map.json', exists: true, servable: true });
    expect(m.files.status).toMatchObject({ exists: true });
  });

  it('keeps concepts with their kind and title; the thumbnail is the first servable «concept» image', () => {
    const m = mapOf(data, 'alpha');
    expect(m.concepts.map((c) => [c.kind, c.title, c.status, c.file.exists, c.file.servable])).toEqual([
      ['moodboard', 'Мудборд', undefined, true, true],
      ['concept', 'Общий вид', 'принят', true, true],
      ['base', 'Нет файла', undefined, false, false],
    ]);
    expect(m.concepts[1]!.file.role).toBe('концепт: Общий вид');
    expect(m.thumb?.path).toBe('art/imagegen/mapkit-alpha/concept-1.png');
    expect(mapOf(data, 'beta').thumb).toBeUndefined();
  });

  it('sorts props by priority then key and derives game height and Tripo slots', () => {
    const m = mapOf(data, 'alpha');
    expect(m.props.map((p) => p.key)).toEqual(['cab', 'lamp', 'crate', 'tree']);
    const by = new Map(m.props.map((p) => [p.key, p]));
    expect(by.get('lamp')).toMatchObject({ nameRu: 'Фонарь', nameEn: 'Gas lamp', descRu: 'Уличный фонарь', descEn: 'tall lamp', role: 'animated', zone: 'streets', material: 'iron', trisMax: 3500, symmetry: 'axial' });
    expect([by.get('lamp')!.slots, by.get('cab')!.slots]).toEqual([['front', 'left'], ['front', 'back']]);
    expect([by.get('lamp')!.gameHeightM, by.get('cab')!.gameHeightM, by.get('crate')!.gameHeightM]).toEqual([1.05, 0.78, 0.3]);
    // a size that is not [w, d, h] is dropped, not guessed
    expect(by.get('tree')).toMatchObject({ sizeM: undefined, gameHeightM: undefined });
    expect(mapOf(data, 'beta').props.map((p) => [p.key, p.slots])).toEqual([
      ['log', []],
      ['stump', ['front', 'left']],
    ]);
  });

  it('counts props by stage, priority and role', () => {
    const c = mapOf(data, 'alpha').counts;
    expect(c.total).toBe(4);
    expect(c.byStage).toEqual([
      { stage: 'listed', count: 1 },
      { stage: 'tripo', count: 1 },
      { stage: 'accepted', count: 1 },
      { stage: 'weird', count: 1 },
    ]);
    expect(c.byPriority).toEqual([
      { priority: 'P0', count: 2 },
      { priority: 'P1', count: 1 },
      { priority: 'P2', count: 1 },
    ]);
    expect(c.byRole).toEqual([
      { role: 'hero', count: 1 },
      { role: 'animated', count: 1 },
      { role: 'dressing', count: 1 },
      { role: 'backdrop', count: 1 },
    ]);
    expect(data.mapKits.totals.byStage.map((s) => [s.stage, s.count])).toEqual([
      ['listed', 4], // alpha tree + beta ×2 + broken rock
      ['tripo', 1],
      ['accepted', 1],
      ['weird', 1],
    ]);
  });

  it('merges status.json: stages, views, Tripo, preview, build and acceptance; no entry = «listed»', () => {
    const m = mapOf(data, 'alpha');
    const by = new Map(m.props.map((p) => [p.key, p]));
    const lamp = by.get('lamp')!;
    expect(lamp).toMatchObject({ stage: 'accepted', stageKnown: true, inStatus: true, note: 'первый пропс' });
    expect(lamp.views.front?.path).toBe('art/imagegen/mapkit-alpha/props/lamp/front.png');
    expect(lamp.views.side?.servable).toBe(true);
    expect(lamp.views.sheet).toBeUndefined();
    // `slot` is the Tripo slot name of the side view, not a file
    expect([lamp.views.slot, lamp.views.heightMismatchPct]).toEqual(['left', 1.5]);
    expect(lamp.tripo?.ops).toEqual([
      { op: 'generate', status: 'ok', quoted: 100, before: 1000, after: 900 },
      { op: 'texture', status: undefined, quoted: undefined, before: undefined, after: undefined },
    ]);
    expect(lamp.preview).toMatchObject({ path: 'art/pipeline-candidates/ASSET-MAPKIT-ALPHA-001/20261021-run/preview/lamp.png', servable: true });
    expect(lamp.tripo).toMatchObject({ taskId: '0123456789abcdef', route: 'Умная сетка P2.0', credits: 115, run: '20261021-run' });
    expect(lamp.tripo?.glb).toMatchObject({ kind: 'glb', servable: true });
    expect(lamp.build).toMatchObject({ tris: 3200 });
    expect(lamp.build?.fbx).toMatchObject({ kind: 'fbx', exists: true });
    expect(lamp.acceptance).toMatchObject({ score: 8.4, verdict: 'принят' });
    expect(lamp.acceptance?.card?.exists).toBe(true);

    // number-like values are accepted; a path outside the repo stays text only; a missing file is not servable
    const cab = by.get('cab')!;
    expect(cab).toMatchObject({ stage: 'tripo', tripo: { taskId: '77', credits: 120, ops: [] } });
    expect(cab.views.front).toMatchObject({ path: 'C:/tmp/cab-front.png', exists: null, servable: false });
    expect(cab.preview).toMatchObject({ exists: false, servable: false });

    expect(by.get('crate')).toMatchObject({ stage: 'weird', stageKnown: false });
    expect(by.get('tree')).toMatchObject({ stage: 'listed', stageKnown: true, inStatus: false });
    const beta = mapOf(data, 'beta');
    expect(beta.files.status.exists).toBe(false);
    expect(beta.props.every((p) => p.stage === 'listed' && !p.inStatus)).toBe(true);
    expect(beta.counts.byStage).toEqual([{ stage: 'listed', count: 2 }]);
    expect(beta.statusUpdatedAt).toBeUndefined();
  });

  it('sums Tripo credits per map and keeps the declared total next to it', () => {
    expect(mapOf(data, 'alpha').credits).toEqual({ spent: 235, tasks: 2, declared: 235 });
    expect(mapOf(data, 'beta').credits).toEqual({ spent: 0, tasks: 0, declared: undefined });
  });

  it('lists images of the Gemini folder that no json mentions', () => {
    const im = mapOf(data, 'alpha').images;
    // referenced: two concepts and two views of the lamp; extra-1.png is not mentioned, notes.txt is not an image
    expect(im).toMatchObject({ dir: 'art/imagegen/mapkit-alpha', exists: true, total: 5, unlistedTotal: 1 });
    expect(im.unlisted.map((f) => f.path)).toEqual(['art/imagegen/mapkit-alpha/raw/extra-1.png']);
    expect(mapOf(data, 'beta').images).toMatchObject({ exists: false, total: 0, unlisted: [] });
  });

  it('reports data defects as map problems and hub warnings', () => {
    const alpha = mapOf(data, 'alpha');
    expect(alpha.problems).toEqual(
      expect.arrayContaining([
        'map.json: у концепта №4 нет path',
        'концепт «Нет файла»: нет файла art/imagegen/mapkit-alpha/missing.png',
        'props.json: у пропса №5 нет key',
        'props.json: повтор ключа «lamp» — второй пропс пропущен',
        'tree: sizeM должен быть [ширина, глубина, высота] в метрах',
        'cab: превью: нет файла art/missing-preview.png',
        'status.json: стадия вне словаря (weird) — показана как есть',
        'status.json: записи без пропса в props.json: ghost',
      ]),
    );
    const w = data.warnings.join('\n');
    expect(w).toContain('Карты/alpha: status.json: записи без пропса в props.json: ghost');
    expect(mapOf(data, 'beta').problems).toEqual([]);
    expect(w).not.toMatch(/Карты\/beta/);
  });

  it('a half-written map.json breaks only its own map', () => {
    const b = mapOf(data, 'broken');
    expect(b).toMatchObject({ id: 'broken', boardName: 'broken', error: 'map.json не разобран', heroes: [], concepts: [] });
    expect(b.props.map((p) => p.key)).toEqual(['rock']);
    expect(data.warnings.join('\n')).toMatch(/Не удалось разобрать docs\/art-pipeline\/map-kits\/broken\/map\.json/);
    // the other maps and the rest of the hub are intact
    expect(mapOf(data, 'alpha').error).toBeUndefined();
    expect(data.characters.length).toBeGreaterThan(0);
  });

  it('no map.json, broken props.json and a status.json that is not an object are shown, not thrown', () => {
    const g = mapOf(data, 'gamma');
    expect(g).toMatchObject({ error: 'нет map.json', props: [] });
    expect(g.problems.join('\n')).toMatch(/нет map\.json/);
    expect(g.problems.join('\n')).toMatch(/props\.json не разобран/);
    expect(g.problems.join('\n')).toMatch(/status\.json не разобран/);
    expect(data.warnings.join('\n')).toMatch(/map-kits\/gamma\/status\.json: ожидался JSON-объект/);
  });

  it('adds the data files to the health sources', () => {
    const src = (p: string) => data.pipelineHealth.sources.find((s) => s.path === p);
    expect(src('docs/art-pipeline/map-kits/alpha/map.json')).toMatchObject({ exists: true });
    expect(src('docs/art-pipeline/map-kits/alpha/status.json')).toMatchObject({ exists: true });
    expect(src('docs/art-pipeline/map-kits/beta/status.json')).toBeUndefined();
    expect(src('docs/art-pipeline/map-kits/gamma/map.json')).toMatchObject({ exists: false, error: 'нет файла' });
  });
});

describe('map kits cache', () => {
  let repo: FixtureRepo;

  beforeAll(() => {
    repo = makeFixtureRepo();
    addMapKitFixtures(repo);
  });
  afterAll(() => repo.cleanup());

  it('walks the kit roots on its own: data folder, Gemini folders and Tripo kit-asset runs', () => {
    expect(mapKitRoots(repo.root)).toEqual([
      'docs/art-pipeline/map-kits',
      'art/imagegen/mapkit-alpha',
      'art/pipeline-candidates/ASSET-MAPKIT-ALPHA-001',
    ]);
    const rels = walkMapKits(repo.root).map((f) => f.rel);
    expect(rels).toEqual(expect.arrayContaining(['docs/art-pipeline/map-kits/alpha/status.json', 'art/imagegen/mapkit-alpha/raw/extra-1.png', 'art/pipeline-candidates/ASSET-MAPKIT-ALPHA-001/20261021-run/export/lamp.glb']));
  });

  it('rebuilds when an image, a status or a props file changes', () => {
    const agg = new ArtHubAggregator(repo.root);
    const first = agg.get();
    expect(agg.get().fingerprint).toBe(first.fingerprint);
    expect(mapOf(first, 'alpha').images.unlistedTotal).toBe(1);

    repo.write('art/imagegen/mapkit-alpha/raw/extra-2.png', Buffer.from([0x89, 0x50, 0x4e, 0x47, 1]));
    const second = agg.get();
    expect(second.fingerprint).not.toBe(first.fingerprint);
    expect(mapOf(second, 'alpha').images.unlistedTotal).toBe(2);

    const statusRel = 'docs/art-pipeline/map-kits/alpha/status.json';
    const status = JSON.parse(fs.readFileSync(path.join(repo.root, ...statusRel.split('/')), 'utf8')) as { props: Record<string, { stage: string }> };
    status.props.crate!.stage = 'views';
    repo.write(statusRel, JSON.stringify(status));
    const third = agg.get();
    expect(third.fingerprint).not.toBe(second.fingerprint);
    expect(mapOf(third, 'alpha').props.find((p) => p.key === 'crate')).toMatchObject({ stage: 'views', stageKnown: true });

    repo.write('docs/art-pipeline/map-kits/beta/status.json', JSON.stringify({ props: { stump: { stage: 'ue' } } }));
    const fourth = agg.get();
    expect(fourth.fingerprint).not.toBe(third.fingerprint);
    expect(mapOf(fourth, 'beta').props.find((p) => p.key === 'stump')?.stage).toBe('ue');
    expect(mapOf(fourth, 'beta').files.status.exists).toBe(true);
  });
});

describe('map kits without any data', () => {
  it('gives an empty section and no warnings', () => {
    const empty = fs.mkdtempSync(path.join(os.tmpdir(), 'art-hub-mapkits-empty-'));
    try {
      const d = aggregate(empty);
      expect(d.mapKits).toEqual({ root: 'docs/art-pipeline/map-kits', found: false, maps: [], totals: { maps: 0, props: 0, credits: 0, byStage: [] } });
      expect(d.warnings.join('\n')).not.toMatch(/Карты|map-kits/);
    } finally {
      fs.rmSync(empty, { recursive: true, force: true });
    }
  });

  it('an empty map-kits folder is found but has no maps', () => {
    const repo = makeFixtureRepo();
    try {
      repo.write('docs/art-pipeline/map-kits/README.md', '# карты\n');
      const d = aggregate(repo.root);
      expect(d.mapKits).toMatchObject({ found: true, maps: [] });
    } finally {
      repo.cleanup();
    }
  });
});

describe('map kits on the real repo', () => {
  const hasKits = fs.existsSync(path.join(REAL_REPO, 'docs', 'art-pipeline', 'map-kits', 'soho', 'map.json'));

  it.skipIf(!hasKits)('reads the real maps', () => {
    const d = aggregate(REAL_REPO);
    const k = d.mapKits;
    expect(k.maps.map((m) => m.id)).toEqual(expect.arrayContaining(['baskerville-manor', 'heorot', 'sherwood-forest', 'soho']));
    for (const m of k.maps) {
      expect(m.error).toBeUndefined();
      expect(m.props.length).toBeGreaterThan(20);
      expect(m.topology?.cells).toBeGreaterThan(0);
      expect(m.paletteHex.length).toBeGreaterThan(0);
      expect(m.heroes.length).toBeGreaterThan(0);
      expect(m.files.map.servable).toBe(true);
    }
    expect(k.totals.props).toBeGreaterThan(100);
    // the data is written by another track and may be mid-update: only a map that cannot be read at all fails here
    expect(d.warnings.filter((w) => /нет map\.json|ожидался JSON-объект/.test(w) && /map-kits/.test(w))).toEqual([]);
  });
});
