import type { HeroDefinition } from '../../interfaces';
import { CardType, EffectTiming, AbilityTrigger } from '../../interfaces';

/**
 * Daredevil (Matt Murdock)
 * Hell's Kitchen Expansion
 *
 * Health: 17
 * Movement: 3
 * Special Ability: Blind Boost - During combat with 2 or fewer cards in hand:
 *                 You may BLIND BOOST (discard top card of deck, add its BOOST value)
 */
export const daredevil: HeroDefinition = {
  id: 'daredevil',
  name: 'Daredevil',
  health: 17,
  movement: 3,
  set: 'hells-kitchen',
  abilities: [
    {
      id: 'blind-boost',
      name: 'Blind Boost',
      text: 'During combat with 2 or fewer cards in hand: You may BLIND BOOST (discard top card of deck, add its BOOST value to your attack or defense value)',
      trigger: AbilityTrigger.DURING_COMBAT,
    },
  ],
  deckCards: [
    {
      id: 'billy-club',
      title: 'Billy Club',
      type: CardType.VERSATILE,
      value: 3,
      boost: 2,
      quantity: 3,
      characterName: 'DAREDEVIL',
      effects: [
        {
          id: 'billy-club-effect',
          timing: EffectTiming.DURING_COMBAT,
          text: 'If you have exactly 1 card in hand, BOOST this card.',
        },
      ],
    },
    {
      id: 'radar-sense',
      title: 'Radar Sense',
      type: CardType.ATTACK,
      value: 4,
      boost: 1,
      quantity: 3,
      characterName: 'DAREDEVIL',
      effects: [
        {
          id: 'radar-sense-effect',
          timing: EffectTiming.DURING_COMBAT,
          text: "If Daredevil's space shares no zones with the opposing fighter, BOOST this card.",
        },
      ],
    },
    {
      id: 'mania',
      title: 'Mania',
      type: CardType.ATTACK,
      value: 2,
      boost: 3,
      quantity: 3,
      characterName: 'DAREDEVIL',
      effects: [
        {
          id: 'mania-effect',
          timing: EffectTiming.AFTER_COMBAT,
          text: 'If this card deals damage, draw 2 cards.',
        },
      ],
    },
    {
      id: 'grappling-hook',
      title: 'Grappling Hook',
      type: CardType.VERSATILE,
      value: 2,
      boost: 2,
      quantity: 3,
      characterName: 'DAREDEVIL',
      effects: [
        {
          id: 'grappling-hook-effect',
          timing: EffectTiming.AFTER_COMBAT,
          text: 'After combat, you may move Daredevil up to 2 spaces.',
        },
      ],
    },
    {
      id: 'daredevil',
      title: 'Daredevil',
      type: CardType.DEFENSE,
      value: 4,
      boost: 1,
      quantity: 3,
      characterName: 'DAREDEVIL',
      effects: [
        {
          id: 'daredevil-effect',
          timing: EffectTiming.DURING_COMBAT,
          text: 'If you have 2 or fewer cards in hand, BOOST this card.',
        },
      ],
    },
  ],
  urls: {
    avatar: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/avatars/kZQUve8tqIcvmVUC-bGge.webp',
    mini: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/minis/NgBt8ama_QbEh8TaPBIUf.webp',
    cardCover: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/card-covers/B0qnKxZyoG3KLwRNvKsrG.webp',
  },
};
