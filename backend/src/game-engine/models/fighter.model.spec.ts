/**
 * Fighter Model Tests
 *
 * slugifyHeroName — ключ HeroAbilityRegistry: handlers регистрируются по
 * слагам, Fighter.heroId — Prisma cuid; связь даёт Fighter.heroSlug.
 */

import { slugifyHeroName } from './fighter.model';
import { daredevilHandler, msMarvelHandler, arthurAbilityHandler } from '../abilities/heroes';

describe('slugifyHeroName', () => {
  it('нормализует реальные имена героев из БД', () => {
    expect(slugifyHeroName('Daredevil')).toBe('daredevil');
    expect(slugifyHeroName('Ms. Marvel')).toBe('ms-marvel');
    expect(slugifyHeroName('King Arthur')).toBe('king-arthur');
    expect(slugifyHeroName('Medusa')).toBe('medusa');
  });

  it('срезает мусорные края и схлопывает разделители', () => {
    expect(slugifyHeroName('  T. Rex  ')).toBe('t-rex');
    expect(slugifyHeroName("Jekyll & Hyde")).toBe('jekyll-hyde');
  });

  // Гарантия связки: слаг имени героя из БД == ключ зарегистрированного
  // handler'а. Если разъедутся — способность молча умрёт (как было до A0)
  it('слаги совпадают с ключами handlers реестра способностей', () => {
    expect(daredevilHandler.heroId).toBe(slugifyHeroName('Daredevil'));
    expect(msMarvelHandler.heroId).toBe(slugifyHeroName('Ms. Marvel'));
    expect(arthurAbilityHandler.heroId).toBe(slugifyHeroName('King Arthur'));
  });
});
