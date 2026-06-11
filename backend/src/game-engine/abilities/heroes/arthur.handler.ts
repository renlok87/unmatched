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
  heroId: 'arthur',
  name: 'Righteous Fury',
  description: 'Arthur всегда имеет минимум +1 к атаке',

  applyCombatModifier(
    _combatState: CombatState,
    fighter: Fighter,
    role: CombatRole,
  ): readonly ValueModifier[] {
    // Артур получает бонус к атаке только когда атакует
    if (role === 'attacker') {
      return [
        {
          type: ValueModifierType.ADD,
          value: 1,
          source: 'hero-ability-arthur',
          timestamp: Date.now() + 1000, // Героические способности применяются последними
          ownerId: 'attacker',
        },
      ];
    }

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
