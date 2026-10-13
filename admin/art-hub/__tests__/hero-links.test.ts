import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { aggregate } from '../aggregate';
import type { ArtHubData } from '../types';
import { heroFigures, heroLinkSummary } from '../vite-plugin';
import { HERO, makeFixtureRepo, type FixtureRepo } from './fixture-repo';

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3]);

describe('hero-links: art-hub figures ↔ admin Heroes', () => {
  let repo: FixtureRepo;
  let data: ArtHubData;

  beforeAll(() => {
    repo = makeFixtureRepo();
    const w = repo.write;
    w(`art/pipeline-candidates/${HERO}/asset-card.yaml`, `ASSET_ID: ${HERO}\nCONTENT_KEY: hero\nKEY: Hero\nROLE: hero\n`);
    w('art/imagegen/concept-hero-codex/design/hero-front.png', PNG);
    w('art/imagegen/concept-pal-codex/design/pal-front.png', PNG);
    w('art/imagegen/concept-loner-codex/design/loner-front.png', PNG);
    w(
      'docs/art-pipeline/hero-links.json',
      JSON.stringify({
        links: {
          pal: { hero: 'The Hero', role: 'sidekick', note: 'в БД помощник — Pals' },
          hero: { hero: 'The Hero', role: 'hero' },
          broken: { role: 'hero' },
        },
      }),
    );
    data = aggregate(repo.root);
  });
  afterAll(() => repo.cleanup());

  it('attaches heroLink to linked figures only', () => {
    const byKey = new Map(data.lookdev.heroes.map((h) => [h.key, h]));
    expect(byKey.get('hero')?.heroLink).toEqual({ hero: 'The Hero', role: 'hero', note: undefined });
    expect(byKey.get('pal')?.heroLink?.role).toBe('sidekick');
    expect(byKey.get('loner')?.heroLink).toBeUndefined();
    expect(data.lookdev.heroLinksFile?.path).toBe('docs/art-pipeline/hero-links.json');
  });

  it('groups figures by Hero.name, hero before sidekicks', () => {
    const { heroes } = heroLinkSummary(data);
    expect(Object.keys(heroes)).toEqual(['the hero']);
    expect(heroes['the hero']!.map((f) => [f.key, f.role])).toEqual([
      ['hero', 'hero'],
      ['pal', 'sidekick'],
    ]);
    expect(heroes['the hero']![1]!.note).toBe('в БД помощник — Pals');
  });

  it('returns full views for one hero, case-insensitive; unknown name → empty', () => {
    const one = heroFigures(data, 'THE HERO');
    expect(one.figures.map((f) => f.key)).toEqual(['hero', 'pal']);
    expect(one.summary[0]!.thumb?.path).toMatch(/hero-front\.png$/);
    expect(heroFigures(data, 'Nobody').figures).toEqual([]);
    expect(heroFigures(data, '').figures).toEqual([]);
  });
});
