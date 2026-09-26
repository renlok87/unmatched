import type { HeroDefinition } from '../../interfaces';
import { CardType, EffectTiming, AbilityTrigger } from '../../interfaces';

/**
 * Ms. Marvel (Kamala Khan)
 * Teen Spirit Expansion
 *
 * Health: 14
 * Movement: 2
 * Special Ability: Stretchy - At the start of your turn, you may move Ms. Marvel 1 space.
 *                 Ms. Marvel can attack from up to 2 spaces away (ignoring zones).
 */
export const msMarvel: HeroDefinition = {
  id: 'ms-marvel',
  name: 'Ms. Marvel',
  health: 14,
  movement: 2,
  set: 'teen-spirit',
  abilities: [
    {
      id: 'stretchy',
      name: 'Stretchy',
      text: 'At the start of your turn, you may move Ms. Marvel 1 space. Ms. Marvel can attack from up to 2 spaces away (ignoring zones).',
      trigger: AbilityTrigger.START_OF_TURN,
    },
  ],
  deckCards: [
    {
      id: 'embiggen',
      title: 'Embiggen',
      type: CardType.ATTACK,
      value: 3,
      boost: 3,
      quantity: 3,
      characterName: 'MS. MARVEL',
      imageUrl: '/assets/decks/ms-marvel/embiggen.webp',
      imageUrlRu: '/assets/decks/ms-marvel/ru/embiggen-ru.webp',
      effects: [
        {
          id: 'embiggen-effect',
          timing: EffectTiming.DURING_COMBAT,
          text: 'If Ms. Marvel is in more zones than the opposing fighter, the value of this card is 6 instead.',
        },
      ],
    },
    {
      id: 'big-wind-up',
      title: 'Big Wind Up',
      type: CardType.ATTACK,
      value: 4,
      boost: 2,
      quantity: 3,
      characterName: 'MS. MARVEL',
      imageUrl: '/assets/decks/ms-marvel/big-wind-up.webp',
      imageUrlRu: '/assets/decks/ms-marvel/ru/big-wind-up-ru.webp',
      effects: [
        {
          id: 'big-wind-up-boost',
          timing: EffectTiming.DURING_COMBAT,
          text: "If Ms. Marvel's space shares no zones with the opposing fighter, you may BOOST this card.",
        },
      ],
    },
    {
      id: 'easy-peasy',
      title: 'Easy Peasy',
      type: CardType.ATTACK,
      value: 3,
      boost: 2,
      quantity: 3,
      characterName: 'MS. MARVEL',
      imageUrl: '/assets/decks/ms-marvel/easy-peasy.webp',
      imageUrlRu: '/assets/decks/ms-marvel/ru/easy-peasy-ru.webp',
      effects: [
        {
          id: 'easy-peasy-draw',
          timing: EffectTiming.AFTER_COMBAT,
          text: 'Draw 1 card. Then, if you have 4 or more cards in your hand, deal 1 damage to an adjacent fighter.',
        },
      ],
    },
    {
      id: 'feint',
      title: 'Feint',
      type: CardType.VERSATILE,
      value: 2,
      boost: 1,
      quantity: 3,
      characterName: 'MS. MARVEL',
      imageUrl: '/assets/decks/ms-marvel/feint.webp',
      imageUrlRu: '/assets/decks/ms-marvel/ru/feint-ru.webp',
      effects: [
        {
          id: 'feint-cancel',
          timing: EffectTiming.IMMEDIATELY,
          text: "Cancel all effects on your opponent's card.",
        },
      ],
    },
    {
      id: 'groovy',
      title: 'Groovy',
      type: CardType.DEFENSE,
      value: 3,
      boost: 2,
      quantity: 3,
      characterName: 'MS. MARVEL',
      effects: [],
    },
  ],
  urls: {
    avatar:
      'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/avatars/M61_bBineukElgyyqqSFu.webp',
    mini: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/minis/w-c5wvLOZYCYK0udNG-DV.webp',
    cardCover:
      'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/card-covers/MFiQb6grYsbNNYwR_hoh1.webp',
  },
};
