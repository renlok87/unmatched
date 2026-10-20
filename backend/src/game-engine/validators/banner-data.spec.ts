/**
 * DATA-01 / DATA-02 (разбор DE 2026-10-20): банер каждой карты принадлежит
 * герою или его помощнику.
 *
 * Правила в двух частях: нормализация bannerAllows (написание) и BANNER_FIXES
 * (настоящие опечатки источника). Скан всего скрейпа идёт, только если
 * scraped-data рядом (папка в .gitignore); иначе он пропускается с
 * пометкой — остальные проверки работают на синтетике.
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  applyBannerFix,
  BANNER_FIXES,
  findBannerMismatches,
} from '../../../prisma/card-banner-fixes';
import { parseHeroData } from '../../../prisma/scraped-hero-parser';

const SCRAPED_HEROES = path.join(__dirname, '../../../../scraped-data/api/heroes');

describe('card-banner-fixes', () => {
  it('BANNER_FIXES правит опечатки только своего героя', () => {
    expect(applyBannerFix('Alice', 'Allice')).toBe('Alice');
    expect(applyBannerFix('Sinbad', 'The Potter')).toBe('The Porter');
    expect(applyBannerFix('Philippa', 'Djkstra')).toBe('Dijkstra');
    expect(applyBannerFix('Medusa', 'Allice')).toBe('Allice');
    expect(applyBannerFix('Alice', 'Any')).toBe('Any');
    expect(applyBannerFix('Alice', null)).toBeNull();
  });

  it('каждая правка ведёт к бойцу, которого bannerAllows узнаёт, а исходная опечатка — нет', () => {
    for (const fix of BANNER_FIXES) {
      expect(findBannerMismatches({ name: fix.heroName, sidekicks: [{ name: fix.to }] }, [
        { name: 'x', bannerName: fix.to },
      ])).toEqual([]);
      expect(findBannerMismatches({ name: fix.heroName, sidekicks: [{ name: fix.to }] }, [
        { name: 'x', bannerName: fix.from },
      ])).toHaveLength(1);
    }
  });

  it('findBannerMismatches: Any и пустой банер не проверяются, пустое имя помощника не матчит', () => {
    const hero = { name: 'Chupacabra', sidekicks: [{ name: '' }] };
    expect(findBannerMismatches(hero, [
      { name: 'a', bannerName: 'Any' },
      { name: 'b', bannerName: null },
      { name: 'c', bannerName: 'Chupacabra' },
    ])).toEqual([]);
    expect(findBannerMismatches(hero, [{ name: 'd', bannerName: 'Jackalope' }])).toEqual([
      { heroName: 'Chupacabra', cardName: 'd', bannerName: 'Jackalope' },
    ]);
  });

  const scan = fs.existsSync(SCRAPED_HEROES) ? it : it.skip;
  scan('скрейп: после BANNER_FIXES у всех 880 карт банер принадлежит герою или помощнику', () => {
    const files = fs.readdirSync(SCRAPED_HEROES).filter((f) => f.endsWith('.json'));
    const mismatches: string[] = [];
    const raw: string[] = [];
    let cards = 0;
    for (const file of files) {
      const hero = parseHeroData(JSON.parse(fs.readFileSync(path.join(SCRAPED_HEROES, file), 'utf-8')));
      if (!hero) continue;
      cards += hero.deck.length;
      const sidekicks = (hero.sidekicks ?? []).map((s: { name?: string }) => ({ name: s.name }));
      raw.push(
        ...findBannerMismatches(
          { name: hero.name, sidekicks },
          hero.deck.map((c) => ({ name: c.title, bannerName: c.bannerName })),
        ).map((m) => `${m.heroName}: ${m.bannerName}`),
      );
      mismatches.push(
        ...findBannerMismatches(
          { name: hero.name, sidekicks },
          hero.deck.map((c) => ({ name: c.title, bannerName: applyBannerFix(hero.name, c.bannerName) })),
        ).map((m) => `${m.heroName} — ${m.cardName}: «${m.bannerName}»`),
      );
    }
    expect(cards).toBeGreaterThan(800);
    // без правок остаются ровно опечатки BANNER_FIXES (Allice ×8, The Potter, Djkstra)
    expect(raw).toHaveLength(10);
    expect(mismatches).toEqual([]);
  });
});
