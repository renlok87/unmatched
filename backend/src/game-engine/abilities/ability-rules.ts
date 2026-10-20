/**
 * Ability Rules — чистые запросы к ABILITY_CONFIGS для мест движка вне
 * HeroAbilityRegistry: исполнителя эффектов карт (CANCEL_EFFECTS, CHANGE_SIZE),
 * сборки партии (размер руки) и мутации setStance.
 *
 * Конфиги — статические данные, поэтому реестр (пустой в тестовых харнессах)
 * здесь не нужен: ответ одинаков в проде и в спеках.
 */

import type { Card } from '../models/card.model';
import type { GameState } from '../models/game-state.model';
import { FighterType } from '../models/fighter.model';
import { bannerAllows } from '../validators/game-rules.validator';
import { isUncancellableCardText } from '../effects/effect-text-parser';
import { ABILITY_CONFIGS, AbilityConfig } from './ability-config';

/** Конфиг способности по слагу героя (fighter.heroSlug). */
export function abilityConfigFor(slug: string | undefined): AbilityConfig | undefined {
  if (!slug) return undefined;
  return ABILITY_CONFIGS.find((c) => c.heroId === slug);
}

/** Конфиг способности героя игрока (по его HERO-бойцу). */
export function abilityConfigOfPlayer(state: GameState, playerId: string): AbilityConfig | undefined {
  const hero = state.fighters.find((f) => f.ownerId === playerId && f.type === FighterType.HERO);
  return abilityConfigFor(hero?.heroSlug ?? hero?.heroId);
}

/**
 * RULE-01: нельзя ли отменить эффекты карты, которую разыграл боец fighterId.
 *  - печатное «This card's effects cannot be canceled» в тексте карты
 *    (isUncancellableCardText: Card.text едет в state, так что работает и в
 *    уже идущих партиях);
 *  - способность героя бойца (uncancellableCards): карты с банером героя, а для
 *    'hero-and-sidekicks' — и помощника. Карты 'Any' отменить можно.
 */
export function isCardUncancellable(
  state: GameState,
  card: Pick<Card, 'bannerName' | 'text'> | null | undefined,
  fighterId: string | undefined,
): boolean {
  if (!card) return false;
  if (isUncancellableCardText(card.text)) return true;
  const fighter = state.fighters.find((f) => f.id === fighterId);
  if (!fighter) return false;
  const config = abilityConfigOfPlayer(state, fighter.ownerId);
  if (!config?.uncancellableCards) return false;
  const banner = card.bannerName?.trim();
  if (!banner || banner.toLowerCase() === 'any') return false;
  const own = state.fighters.filter((f) => f.ownerId === fighter.ownerId);
  const protectedFighters =
    config.uncancellableCards === 'hero' ? own.filter((f) => f.type === FighterType.HERO) : own;
  return protectedFighters.some((f) => bannerAllows(banner, f));
}

/**
 * CHANGE_SIZE / смена стойки: перевести героя игрока в СЛЕДУЮЩУЮ стойку
 * (у Alice — BIG ↔ SMALL). Текущая — metadata.heroStances[playerId], иначе
 * стойка по умолчанию. Герой без стоек → тот же объект state.
 */
export function toggleHeroStance(state: GameState, playerId: string): GameState {
  const stances = abilityConfigOfPlayer(state, playerId)?.stances ?? [];
  if (stances.length === 0) return state;
  const current =
    state.metadata.heroStances?.[playerId] ?? (stances.find((s) => s.default) ?? stances[0]).id;
  const index = stances.findIndex((s) => s.id === current);
  const next = stances[((index >= 0 ? index : 0) + 1) % stances.length].id;
  return {
    ...state,
    metadata: {
      ...state.metadata,
      heroStances: { ...(state.metadata.heroStances ?? {}), [playerId]: next },
    },
  };
}

/** Стартовая рука и максимум руки героя (общие 5/7, Michelangelo 3/3). */
export function handSizeLimitsFor(
  slug: string | undefined,
  defaults: { starting: number; max: number },
): { starting: number; max: number } {
  const config = abilityConfigFor(slug);
  return {
    starting: config?.startingHandSize ?? defaults.starting,
    max: config?.maxHandSize ?? defaults.max,
  };
}
