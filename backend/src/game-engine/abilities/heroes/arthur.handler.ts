/**
 * Arthur Hero Ability Handler
 *
 * Способность King Arthur (R-15/R-16): «When King Arthur attacks, you may
 * BOOST that attack…» — see description below.
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
  // PROVISIONAL label: в захвате (content-king-arthur.json) у способности НЕТ
  // поля name — только текст. Имя не каноническое, игроку не предъявляется.
  name: 'King Arthur attack boost (provisional)',
  description:
    'When King Arthur attacks, you may BOOST that attack. Play the BOOST card, face down, along with ' +
    'your attack card. If your opponent cancels the effects on your attack card, the BOOST is discarded ' +
    'without effect. (GD-017/R-15/R-16: бустятся только атаки King Arthur — никогда Merlin и не защита.)',

  // Реальная способность Артура по правилам Unmatched: BOOST атаки.
  // (Старый выдуманный «+1 к атаке всегда» удалён.)
  // Р-16: отменённый атакой Feint'ом boost не добавляется к значению —
  // см. executeResolveCombat (cancelled → печатное значение карты).
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
