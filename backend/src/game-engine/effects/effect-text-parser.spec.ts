/**
 * Effect Text Parser Tests
 *
 * Фикстуры — РЕАЛЬНЫЕ тексты карт из БД (Medusa, King Arthur, Daredevil и
 * частые паттерны по всей базе).
 */

import { EffectTiming, EffectType, EffectTarget } from '../models/card.model';
import { parseCardEffectTexts, parseFieldText, PARSER_VERSION } from './effect-text-parser';

const after = (text: string) => parseFieldText(text, EffectTiming.AFTER_COMBAT);
const during = (text: string) => parseFieldText(text, EffectTiming.DURING_COMBAT);

describe('effect-text-parser', () => {
  // ------------------------------------------------- Medusa
  describe('Medusa', () => {
    it('Snipe: «Draw 1 card.»', () => {
      const { drafts, unsupported } = after('Draw 1 card.');
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.DRAW_CARD, value: 1 });
    });

    it('Gaze of Stone: «If you won the combat, deal 8 damage to the opposing fighter.»', () => {
      const { drafts, unsupported } = after(
        'If you won the combat, deal 8 damage to the opposing fighter.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DAMAGE,
        value: 8,
        target: EffectTarget.OPPOSING_FIGHTER,
        when: { kind: 'WON_COMBAT' },
      });
    });

    it('Hiss and Slither / Clutching Claws: «Your opponent discards 1 card.»', () => {
      const { drafts, unsupported } = after('Your opponent discards 1 card.');
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.OPPONENT_DISCARD,
        value: 1,
      });
    });

    it('Regroup (компаунд): «Draw 1 card. If you won the combat, draw 2 cards instead.»', () => {
      const { drafts, unsupported } = after(
        'Draw 1 card. If you won the combat, draw 2 cards instead.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(2);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DRAW_CARD,
        value: 1,
        when: { kind: 'LOST_COMBAT' },
      });
      expect(drafts[1].draft).toMatchObject({
        type: EffectType.DRAW_CARD,
        value: 2,
        when: { kind: 'WON_COMBAT' },
      });
    });

    it('Feint: «Cancel all effects on your opponent\'s card.»', () => {
      const { drafts, unsupported } = parseFieldText(
        "Cancel all effects on your opponent's card.",
        EffectTiming.ON_REVEAL,
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.CANCEL_EFFECTS });
    });

    it('Second Shot: «You may BOOST this attack.»', () => {
      const { drafts, unsupported } = during('You may BOOST this attack.');
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.BOOST,
        boostSource: 'PLAYER_CHOICE_HAND',
        optional: true,
      });
    });

    it('Dash: «Move your fighter up to 3 spaces.» → MOVE SELF (manual)', () => {
      const { drafts, unsupported } = after('Move your fighter up to 3 spaces.');
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.MOVE,
        value: 3,
        target: EffectTarget.SELF,
      });
    });

    it('The Hounds of Mighty Zeus: «Move each Harpy up to 3 spaces.» → NAMED', () => {
      const { drafts } = after('Move each Harpy up to 3 spaces.');
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.MOVE,
        value: 3,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'Harpy',
      });
    });
  });

  // ------------------------------------------------- King Arthur
  describe('King Arthur', () => {
    it('The Aid of Morgana: «Draw 2 cards.»', () => {
      const { drafts, unsupported } = after('Draw 2 cards.');
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.DRAW_CARD, value: 2 });
    });

    it('Aid the Chosen One: «If you won the combat, draw 2 cards.»', () => {
      const { drafts, unsupported } = after('If you won the combat, draw 2 cards.');
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DRAW_CARD,
        value: 2,
        when: { kind: 'WON_COMBAT' },
      });
    });

    it('Momentous Shift: условный SET_VALUE по MOVED_THIS_TURN', () => {
      const { drafts, unsupported } = during(
        'If your fighter started this turn in a different space, the value of this card is 5 instead.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.SET_VALUE,
        value: 5,
        when: { kind: 'MOVED_THIS_TURN' },
      });
    });

    it('Bewilderment: «Prevent all damage»', () => {
      const { drafts, unsupported } = during('Prevent all damage');
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.PREVENT_DAMAGE });
    });

    it('Noble Sacrifice: BOOST со скобочным пояснением', () => {
      const { drafts, unsupported } = during(
        'You may BOOST this attack. (This is in addition to any boost from your ability.)',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.BOOST,
        boostSource: 'PLAYER_CHOICE_HAND',
      });
    });

    it('Divine Intervention: «Move King Arthur up to 5 spaces.»', () => {
      const { drafts } = after('Move King Arthur up to 5 spaces.');
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.MOVE,
        value: 5,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'King Arthur',
      });
    });
  });

  // ------------------------------------------------- Daredevil
  describe('Daredevil', () => {
    it('Man Without Fear: «You may BLIND BOOST this attack. (…)»', () => {
      const { drafts, unsupported } = during(
        'You may BLIND BOOST this attack. (This is in addition to anything else.)',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.BOOST,
        boostSource: 'SELF_DECK_TOP',
        blind: true,
      });
    });

    it("Devil of Hell's Kitchen: SET_VALUE при пустой колоде", () => {
      const { drafts, unsupported } = during(
        'If you have no cards in your deck, the value of this card is 6 instead.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.SET_VALUE,
        value: 6,
        when: { kind: 'DECK_EMPTY' },
      });
    });

    it('Son Of A Boxer: «If you lost the combat, deal 2 damage to a fighter adjacent to Daredevil.»', () => {
      const { drafts, unsupported } = after(
        'If you lost the combat, deal 2 damage to a fighter adjacent to Daredevil.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DAMAGE,
        value: 2,
        target: EffectTarget.ADJACENT_ENEMY,
        when: { kind: 'LOST_COMBAT' },
      });
    });

    it('Grappling Hook: «Move Daredevil up to 2 spaces.»', () => {
      const { drafts } = after('Move Daredevil up to 2 spaces.');
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.MOVE,
        value: 2,
        fighterName: 'Daredevil',
      });
    });
  });

  // ------------------------------------------------- Частые паттерны базы
  describe('частые паттерны по всей базе', () => {
    it('«If you won the combat, return this card to your hand.»', () => {
      const { drafts, unsupported } = after(
        'If you won the combat, return this card to your hand.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.RETURN_TO_HAND,
        when: { kind: 'WON_COMBAT' },
      });
    });

    it('«Gain 1 action.» / «Gain 1 action unless 🪙» (второе — UNSUPPORTED)', () => {
      const ok = after('Gain 1 action.');
      expect(ok.unsupported).toEqual([]);
      expect(ok.drafts[0].draft).toMatchObject({ type: EffectType.GAIN_ACTION, value: 1 });

      const bad = after('Gain 1 action unless 🪙');
      expect(bad.unsupported).toHaveLength(1);
      expect(bad.drafts[0].draft.type).toBe(EffectType.UNSUPPORTED);
    });

    it('«The opposing fighter cannot leave their space this turn.»', () => {
      const { drafts, unsupported } = parseFieldText(
        'The opposing fighter cannot leave their space this turn.',
        EffectTiming.ON_REVEAL,
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.IMMOBILIZE,
        target: EffectTarget.OPPOSING_FIGHTER,
      });
    });

    it('«Add +1 to this card\'s value for each other friendly fighter adjacent to the opposing fighter.»', () => {
      const { drafts, unsupported } = during(
        "Add +1 to this card's value for each other friendly fighter adjacent to the opposing fighter.",
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.VALUE_PER_COUNT,
        count: { source: 'FRIENDLY_ADJACENT_TO_OPPONENT', per: 1 },
      });
    });

    it('компаунд BOOST с верха колоды', () => {
      const { drafts, unsupported } = during(
        "Discard the top card of your deck. Add its BOOST value to this card's value.",
      );
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.BOOST,
        boostSource: 'SELF_DECK_TOP',
      });
    });

    it('«If Dr. Watson is adjacent to Holmes…» — Dr. не рвёт предложение', () => {
      const { drafts } = after(
        'If Dr. Watson is adjacent to Holmes, they each recover 1 health.',
      );
      // условие пока не поддержано → ровно ОДИН UNSUPPORTED (не два обрывка)
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft.type).toBe(EffectType.UNSUPPORTED);
    });

    it('«Deal 1 damage to each opposing fighter adjacent to your fighter.»', () => {
      const { drafts, unsupported } = after(
        'Deal 1 damage to each opposing fighter adjacent to your fighter.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DAMAGE,
        value: 1,
        target: EffectTarget.ENEMIES_ADJACENT_TO_SELF,
      });
    });

    it('«Winter Soldier recovers 2 health.» → HEAL NAMED', () => {
      const { drafts, unsupported } = after('Winter Soldier recovers 2 health.');
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.HEAL,
        value: 2,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'Winter Soldier',
      });
    });
  });

  // ------------------------------------------------- parseCardEffectTexts
  describe('parseCardEffectTexts (по полям карты)', () => {
    it('тайминги от поля-источника + метаданные парсера', () => {
      const { effects, unsupported } = parseCardEffectTexts(
        {
          immediately: "Cancel all effects on your opponent's card.",
          during: 'You may BOOST this attack.',
          after: 'Draw 1 card.',
        },
        'card-1',
      );
      expect(unsupported).toEqual([]);
      expect(effects).toHaveLength(3);
      expect(effects[0]).toMatchObject({
        type: EffectType.CANCEL_EFFECTS,
        timing: EffectTiming.ON_REVEAL,
        source: 'parser',
        parserVersion: PARSER_VERSION,
      });
      expect(effects[1].timing).toBe(EffectTiming.DURING_COMBAT);
      expect(effects[2].timing).toBe(EffectTiming.AFTER_COMBAT);
      expect(effects.every((e) => e.id.startsWith('card-1-'))).toBe(true);
      expect(effects.every((e) => typeof e.text === 'string' && e.text.length > 0)).toBe(true);
    });

    it('ongoing/boost-тексты уходят в UNSUPPORTED (отложено)', () => {
      const { effects, unsupported } = parseCardEffectTexts(
        { ongoing: 'While this card is in play, something complex happens.' },
        'card-2',
      );
      expect(effects).toHaveLength(1);
      expect(effects[0].type).toBe(EffectType.UNSUPPORTED);
      expect(unsupported).toHaveLength(1);
    });

    it('пустые поля → пусто', () => {
      const { effects } = parseCardEffectTexts({}, 'card-3');
      expect(effects).toEqual([]);
    });
  });
});
