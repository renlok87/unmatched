/**
 * DATA-06 (разбор DE 2026-10-20): каталог героя отдаёт Move из БД, а не 3.
 * Партия берёт Move из Hero.movement, и content-API (heroes, heroBySlug)
 * должен показывать то же число.
 */
import type { Card, Hero } from '@prisma/client';
import { ContentMapper } from './content.mapper';

const hero = (movement: number): Hero & { cards: Card[] } =>
  ({
    id: 'h1',
    name: 'Medusa',
    nameEn: 'Medusa',
    nameRu: 'Медуза',
    set: 'Battle of Legends Vol. 1',
    health: 16,
    movement,
    ability: null,
    properties: null,
    fighterType: 'HERO',
    sidekicks: [],
    cards: [],
  }) as unknown as Hero & { cards: Card[] };

describe('ContentMapper: movement героя', () => {
  const mapper = new ContentMapper();

  it('HeroDto и HeroDefinition берут movement из БД', () => {
    expect(mapper.prismaHeroToHeroDto(hero(2)).movement).toBe(2);
    expect(mapper.prismaHeroToHeroDefinition(hero(1)).movement).toBe(1);
  });
});
