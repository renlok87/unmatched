import { GameResolver } from './game.resolver';
import { ABILITY_CONFIGS } from '../game-engine/abilities/ability-config';

/**
 * Юнит-тест для query `heroStances(heroSlug)` — маппинг StanceConfig из
 * ABILITY_CONFIGS в StanceOptionDto {id,label,isDefault}. Сервисы (GameService /
 * GameStateService) этой query не нужны, поэтому резолвер инстанцируется с
 * заглушками.
 */
describe('GameResolver.heroStances', () => {
  let resolver: GameResolver;

  beforeEach(() => {
    resolver = new GameResolver({} as any, {} as any);
  });

  it('returns [] for a hero without stances', () => {
    expect(resolver.heroStances('king-arthur')).toEqual([]);
  });

  it('returns [] for an unknown hero slug', () => {
    expect(resolver.heroStances('does-not-exist')).toEqual([]);
  });

  it('maps alice big/small with the default flag set on big', () => {
    expect(resolver.heroStances('alice')).toEqual([
      { id: 'big', label: 'Big', isDefault: true },
      { id: 'small', label: 'Small', isDefault: false },
    ]);
  });

  it('maps muhammad-ali float/sting with the default flag set on float', () => {
    expect(resolver.heroStances('muhammad-ali')).toEqual([
      { id: 'float', label: 'Float Like a Butterfly', isDefault: true },
      { id: 'sting', label: 'Sting Like a Bee', isDefault: false },
    ]);
  });

  it('exposes exactly id/label/isDefault for every stance config (no leaked fields)', () => {
    for (const config of ABILITY_CONFIGS) {
      if (!config.stances?.length) continue;
      for (const option of resolver.heroStances(config.heroId)) {
        expect(Object.keys(option).sort()).toEqual(['id', 'isDefault', 'label']);
      }
    }
  });

  it('marks at most one stance as default per hero (mirrors backend default rule)', () => {
    for (const config of ABILITY_CONFIGS) {
      if (!config.stances?.length) continue;
      const defaults = resolver.heroStances(config.heroId).filter((o) => o.isDefault);
      expect(defaults.length).toBeLessThanOrEqual(1);
    }
  });
});
