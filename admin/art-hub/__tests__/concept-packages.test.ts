import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { aggregate } from '../aggregate';
import { ALLOWED_PREFIXES, isAllowedRelPath } from '../path-guard';
import type { ArtHubData } from '../types';
import { HERO, makeFixtureRepo, type FixtureRepo } from './fixture-repo';

const PKG = 'art/imagegen/concept-hero-codex';
const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3]);
const report = (verdict: string, pass: number, warn: number, fail: number) => ({
  schema: 'unmatched.concept-checks/1',
  verdict,
  summary: { PASS: pass, WARN: warn, FAIL: fail },
  checks: [
    { id: 'set.size', result: 'PASS' },
    { id: 'view.frame_top', result: warn ? 'WARN' : 'PASS' },
    { id: 'view.border', result: fail ? 'FAIL' : 'PASS' },
  ],
});

describe('concept packages (3d-model-pipeline stage 1) on a fixture repo', () => {
  let repo: FixtureRepo;
  let data: ArtHubData;

  beforeAll(() => {
    repo = makeFixtureRepo();
    const w = repo.write;
    w(`art/pipeline-candidates/${HERO}/asset-card.yaml`, `ASSET_ID: ${HERO}\nCONTENT_KEY: hero\nKEY: Hero\nROLE: hero\n`);
    w(`${PKG}/palette.json`, JSON.stringify({ main: [{ name: 'bronze', hex: '#A9773A' }], accent: { name: 'gold', hex: '#E0B54A' } }));
    w(`${PKG}/concepts/hero-design-front-g1.png`, PNG);
    w(`${PKG}/concepts/hero-design-front-g2.png`, PNG);
    w(`${PKG}/checks/design-front-g1/checks-report.json`, JSON.stringify(report('FAIL', 10, 1, 2)));
    w(`${PKG}/checks/design-front-g2/checks-report.json`, JSON.stringify(report('PASS', 12, 1, 0)));
    w(`${PKG}/design/hero-front.png`, PNG);
    w(`${PKG}/design/checks-report.json`, JSON.stringify(report('PASS', 12, 1, 0)));
    w(
      `${PKG}/generation-records.json`,
      JSON.stringify([
        { id: 'a', saved_path: `${PKG}/concepts/hero-design-front-g1.png`, selected: false },
        { id: 'b', saved_path: `${PKG}/concepts/hero-design-front-g2.png`, selected: true },
      ]),
    );
    w(
      `${PKG}/verification.json`,
      JSON.stringify({ source_unchanged: true, outside_folder: [], limit_reached: [{ view: 'side', failed_items: ['pose'] }], checklist: [{ passed: false }, { passed: true }] }),
    );
    w(`${PKG}/README.md`, '# Hero\n\nСтатус: предложено, этап 1a.\n');
    // half-written files must only warn
    w(`${PKG}/checks/design-front-g3/checks-report.json`, '{ "verdict": ');
    w(`${PKG}/concepts/hero-design-front-g3.png`, PNG);
    // 1c views and sheet appear later
    w(`${PKG}/hero-front.png`, PNG);
    w(`${PKG}/hero-side.png`, PNG);
    w(`${PKG}/hero-back.png`, PNG);
    w(`${PKG}/sheet-hero.png`, PNG);
    w(`${PKG}/checks-report.json`, JSON.stringify(report('WARN', 9, 3, 0)));
    // package without a card: bound by folder name
    w('art/imagegen/concept-orphan-codex/palette.json', '{ broken');
    // later stages: draft-tripo / h2-bake runs and acceptance cards
    w(`art/pipeline-candidates/${HERO}/20261013-draft-tripo/source/hero-draft-tripo-abcd1234.glb`, 'glb');
    w(`art/pipeline-candidates/${HERO}/20261013-draft-tripo/orthos/ortho_front.png`, PNG);
    w(`art/pipeline-candidates/${HERO}/20261014-h2-bake/reports/bake.json`, '{}');
    w(
      `art/pipeline-candidates/${HERO}/evidence/acceptance-concept/20261013-front-r1/card.json`,
      JSON.stringify({ kind: 'concept', cycle: 'r1', verdict: 'pass', scores: { S: { value: 2 }, Q: { value: 1.5 }, P: { value: 2 } }, gates: { size: { status: 'PASS' } } }),
    );
    w(`art/pipeline-candidates/${HERO}/evidence/acceptance/20261015-r1/card.json`, '{ "kind": "model", ');
    data = aggregate(repo.root);
  });
  afterAll(() => repo.cleanup());

  const hero = () => data.lookdev.heroes.find((h) => h.key === 'hero')!;

  it('maps the package to the asset via asset-card CONTENT_KEY', () => {
    const pkg = hero().conceptPackage!;
    expect(hero().pageId).toBe(HERO);
    expect(pkg).toMatchObject({ dir: PKG, assetId: HERO, contentKey: 'hero', generationRecords: 2, stage: '1c' });
    expect(pkg.palette).toEqual([
      { name: 'bronze', hex: '#A9773A' },
      { name: 'gold', hex: '#E0B54A' },
    ]);
    expect(pkg.readmeStatus).toBe('Статус: предложено, этап 1a.');
  });

  it('lists the selected design, all candidates with check verdicts and the selection flag', () => {
    const pkg = hero().conceptPackage!;
    expect(pkg.designFront?.path).toBe(`${PKG}/design/hero-front.png`);
    expect(pkg.designFront?.servable).toBe(true);
    expect(pkg.designChecks).toMatchObject({ verdict: 'PASS', pass: 12, warn: 1, fail: 0 });
    expect(pkg.candidates.map((c) => [c.label, c.verdict, c.fail, c.selected])).toEqual([
      ['design-front-g1', 'FAIL', 2, undefined],
      ['design-front-g2', 'PASS', 0, true],
      ['design-front-g3', undefined, undefined, undefined],
    ]);
    expect(pkg.designChecks?.problems.length).toBe(1);
  });

  it('shows limit_reached, 1c views, sheet and its checks', () => {
    const pkg = hero().conceptPackage!;
    expect(pkg.verification).toMatchObject({ sourceUnchanged: true, checklistFailed: 1, limitReached: [{ view: 'side', failedItems: ['pose'] }] });
    expect(pkg.views.map((f) => f.path.split('/').pop())).toEqual(['hero-front.png', 'hero-side.png', 'hero-back.png']);
    expect(pkg.sheet?.path).toBe(`${PKG}/sheet-hero.png`);
    expect(pkg.sheetChecks).toMatchObject({ verdict: 'WARN', warn: 3 });
  });

  it('turns half-written files into warnings without crashing', () => {
    expect(hero().conceptPackage!.warnings.some((w) => w.includes('design-front-g3'))).toBe(true);
    const orphan = data.lookdev.heroes.find((h) => h.key === 'orphan')!;
    expect(orphan.conceptPackage!.warnings.some((w) => w.includes('asset-card.yaml'))).toBe(true);
    expect(orphan.conceptPackage!.palette).toBeUndefined();
  });

  it('collects acceptance cards of any group, newest first, tolerating broken cards', () => {
    const cards = hero().acceptance;
    expect(cards.map((c) => [c.group, c.folder])).toEqual([
      ['acceptance', '20261015-r1'],
      ['acceptance-concept', '20261013-front-r1'],
    ]);
    expect(cards[1]).toMatchObject({ kind: 'concept', verdict: 'pass', cycle: 'r1', score: 9.2 });
    expect(cards[0]!.verdict).toBeUndefined();
    expect(data.warnings.some((w) => w.includes('20261015-r1/card.json'))).toBe(true);
  });

  it('picks up draft-tripo and h2-bake runs of the asset without extra code', () => {
    const page = data.characters.find((c) => c.id === HERO)!;
    const ids = page.models.runs.map((r) => r.id);
    expect(ids).toContain('20261013-draft-tripo');
    expect(ids).toContain('20261014-h2-bake');
  });

  it('serves package files and acceptance cards through the path guard', () => {
    expect(ALLOWED_PREFIXES).toContain('art/');
    expect(isAllowedRelPath(`${PKG}/concepts/hero-design-front-g1.png`)).toBe(true);
    expect(isAllowedRelPath(`${PKG}/checks/design-front-g1/checks-report.json`)).toBe(true);
    expect(isAllowedRelPath(`art/pipeline-candidates/${HERO}/evidence/acceptance-concept/20261013-front-r1/card.json`)).toBe(true);
    expect(isAllowedRelPath(`${PKG}/../../../.env`)).toBe(false);
  });
});
