import type { HeroDefinition } from '../../interfaces';
import { msMarvel } from './ms-marvel';
import { daredevil } from './daredevil';

/**
 * Hero Registry
 * All available heroes for the game
 */
export const HERO_REGISTRY: Record<string, HeroDefinition> = {
  'ms-marvel': msMarvel,
  'daredevil': daredevil,
};

/**
 * Get a hero definition by ID
 */
export function getHeroDefinition(heroId: string): HeroDefinition {
  const hero = HERO_REGISTRY[heroId];
  if (!hero) {
    throw new Error(`Hero not found: ${heroId}`);
  }
  return hero;
}

/**
 * Get all available heroes
 */
export function getAllHeroes(): HeroDefinition[] {
  return Object.values(HERO_REGISTRY);
}

/**
 * Get heroes by set
 */
export function getHeroesBySet(set: string): HeroDefinition[] {
  return getAllHeroes().filter(h => h.set === set);
}
