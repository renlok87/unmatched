/**
 * Arthur Hero Ability Handler
 *
 * Способность Артура: "Righteous Fury"
 * Arthur всегда имеет минимум +1 к атаке.
 */

import {
  HeroAbilityHandler,
  ValueModifier,
  ValueModifierType,
  CombatState,
  CombatRole,
  Fighter,
} from '../hero-ability-registry';
import { Position } from '../../models';

/**
 * Обработчик способности Артура
 */
export const arthurAbilityHandler: HeroAbilityHandler = {
  // Ключ = slugifyHeroName(Hero.name) — в БД герой называется 'King Arthur'
  heroId: 'king-arthur',
  name: 'Holy Avenger',
  description:
    'King Arthur может BOOST-ить свои атаки картой из руки (в дополнение к BOOST-эффектам карт)',

  // Реальная способность Артура по правилам Unmatched: BOOST атаки.
  // (Старый выдуманный «+1 к атаке всегда» удалён.)
  allowsAttackBoost: true,

  applyCombatModifier(
    _combatState: CombatState,
    _fighter: Fighter,
    _role: CombatRole,
  ): readonly ValueModifier[] {
    return [];
  },
};

/**
 * Дополнительные способности Артура (расширяемые)
 */
export const arthurExtendedHandler: HeroAbilityHandler = {
  ...arthurAbilityHandler,

  // Артур может иметь дополнительные способности при перемещении
  onMove(_fighter: Fighter, _from: Position, to: Position) {
    // Здесь можно добавить логику для перемещения
    return [];
  },

  onDefeat(_fighter: Fighter) {
    // При поражении Артур может дать бонус союзнику
    return [
      {
        type: 'ally_bonus',
        description: 'Артур пал, но его вдохновение живёт!',
        sourceId: _fighter.id,
      },
    ];
  },
};
