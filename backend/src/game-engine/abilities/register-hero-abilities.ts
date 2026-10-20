/**
 * The production set of hero ability handlers, in production order: the
 * hand-written handlers first, then one GenericHeroAbilityHandler per
 * declarative ABILITY_CONFIGS entry (registerExtended → the extended map
 * serves turn hooks and stateful combat through getAny).
 *
 * GameEngineModule calls it on init; headless harnesses that build the
 * executor without Nest (test/fixtures/s03-engine.fixture.ts, self-play) call
 * it too, so they play the same heroes the server plays (DET-3: an empty
 * registry plays every game without hero abilities).
 */
import { HeroAbilityRegistry } from './hero-ability-registry';
import { ABILITY_CONFIGS } from './ability-config';
import { GenericHeroAbilityHandler, type GenericHeroAbilityDeps } from './generic-hero-ability.handler';
import { arthurAbilityHandler, daredevilHandler, msMarvelHandler } from './heroes';

export function registerHeroAbilities(registry: HeroAbilityRegistry, deps: GenericHeroAbilityDeps): void {
  registry.registerExtended(daredevilHandler);
  registry.registerExtended(msMarvelHandler);
  registry.register(arthurAbilityHandler);
  for (const config of ABILITY_CONFIGS) {
    registry.registerExtended(new GenericHeroAbilityHandler(config, deps));
  }
}
