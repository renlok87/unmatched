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

    it('random-различие (S05-фикс): «random cards» БЕЗ boost-фразы — НЕ выбор сбрасывающего', () => {
      // Чистый random-сброс (без «Add its BOOST value…») движком не исполняется
      // → UNSUPPORTED; ловил бы misclassification как OPPONENT_DISCARD-выбор.
      const plain = after('Your opponent discards 2 random cards.');
      expect(plain.drafts).toHaveLength(1);
      expect(plain.drafts[0].draft.type).toBe(EffectType.UNSUPPORTED);
      expect(plain.unsupported).toHaveLength(1);

      // множественный НЕ-random — по-прежнему выбор (value 2)
      const multi = after('Your opponent discards 2 cards.');
      expect(multi.unsupported).toEqual([]);
      expect(multi.drafts[0].draft).toMatchObject({ type: EffectType.OPPONENT_DISCARD, value: 2 });

      // random + boost-фраза — компаунд BOOST OPPONENT_RANDOM_HAND (не тронут)
      const compound = during('Your opponent discards 1 random card. Add its BOOST value to this card\'s value.');
      expect(compound.unsupported).toEqual([]);
      expect(compound.drafts[0].draft).toMatchObject({
        type: EffectType.BOOST,
        boostSource: 'OPPONENT_RANDOM_HAND',
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

  // ------------------------------------------------- MOVE без «up to»
  describe('MOVE без «up to» (точное число клеток)', () => {
    it('«Move Jill Trent 1 space» → MOVE NAMED value 1', () => {
      const { drafts } = after('Move Jill Trent 1 space');
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.MOVE,
        value: 1,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'Jill Trent',
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

    it('«Gain 1 action.» / «Gain 1 action unless 🪙» (второе — optional, parser v7)', () => {
      const ok = after('Gain 1 action.');
      expect(ok.unsupported).toEqual([]);
      expect(ok.drafts[0].draft).toMatchObject({ type: EffectType.GAIN_ACTION, value: 1 });

      // v7: «unless 🪙» больше НЕ UNSUPPORTED — базовый эффект как optional
      const opt = after('Gain 1 action unless 🪙');
      expect(opt.unsupported).toEqual([]);
      expect(opt.drafts[0].draft).toMatchObject({
        type: EffectType.GAIN_ACTION,
        value: 1,
        optional: true,
      });
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

    it("Ms. Marvel: «If Ms. Marvel's space shares no zones…» → NOT_SHARES_ZONE (C1)", () => {
      const { drafts, unsupported } = after(
        "If Ms. Marvel's space shares no zones with the opposing fighter, draw 2 cards.",
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DRAW_CARD,
        value: 2,
        when: { kind: 'NOT_SHARES_ZONE_WITH_OPPONENT' },
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

  // ------------------------------------------------- CHOOSE_ONE (парсер v3)
  describe('CHOOSE_ONE (v3)', () => {
    it('Utility Belt: «Choose one: -…, -…, -…» → 3 опции, label сохранён', () => {
      const { drafts } = after(
        'Choose one: -Jill Trent recovers 1 health, -Move Jill Trent 1 space, -Draw 1 card',
      );
      expect(drafts).toHaveLength(1);
      const d = drafts[0].draft;
      expect(d.type).toBe(EffectType.CHOOSE_ONE);
      expect(d.chooseCount).toBe(1);
      expect(d.optionDrafts).toHaveLength(3);
      expect(d.optionDrafts!.map((o) => o.label)).toEqual([
        'Jill Trent recovers 1 health',
        'Move Jill Trent 1 space',
        'Draw 1 card',
      ]);
      // распознанные под-эффекты
      expect(d.optionDrafts![0].drafts[0]).toMatchObject({
        type: EffectType.HEAL,
        value: 1,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'Jill Trent',
      });
      // «Move … 1 space» без «up to N» — теперь распознаётся (parser v4)
      expect(d.optionDrafts![1].drafts[0]).toMatchObject({
        type: EffectType.MOVE,
        value: 1,
      });
      expect(d.optionDrafts![2].drafts[0]).toMatchObject({
        type: EffectType.DRAW_CARD,
        value: 1,
      });
    });

    it('Technodrome: «Choose one:» с переносами строк → CANCEL_EFFECTS + UNSUPPORTED', () => {
      const { drafts } = parseFieldText(
        "Choose one:\n- cancel all effects on your opponent's card\n- activate a machine",
        EffectTiming.ON_REVEAL,
      );
      const d = drafts[0].draft;
      expect(d.type).toBe(EffectType.CHOOSE_ONE);
      expect(d.optionDrafts).toHaveLength(2);
      expect(d.optionDrafts![0].drafts[0].type).toBe(EffectType.CANCEL_EFFECTS);
      expect(d.optionDrafts![1].drafts[0].type).toBe(EffectType.UNSUPPORTED);
    });

    it('Shapershifter: «Choose one effect:» (during) → 2 опции, gain action распознан', () => {
      const { drafts } = during(
        "Choose one effect:\n- add +1 to this card's value for each card in your opponent's hand\n- gain 1 action",
      );
      const d = drafts[0].draft;
      expect(d.type).toBe(EffectType.CHOOSE_ONE);
      expect(d.optionDrafts).toHaveLength(2);
      expect(d.optionDrafts![1].drafts[0]).toMatchObject({
        type: EffectType.GAIN_ACTION,
        value: 1,
      });
    });

    it('Looking Glass: «Choose 2 different effects:» → chooseCount 2, 3 опции', () => {
      const { drafts } = after(
        'Choose 2 different effects: - draw 2 cards - Alice recovers 3 health - place Alice in any other space',
      );
      const d = drafts[0].draft;
      expect(d.type).toBe(EffectType.CHOOSE_ONE);
      expect(d.chooseCount).toBe(2);
      expect(d.optionDrafts).toHaveLength(3);
      expect(d.optionDrafts![0].drafts[0]).toMatchObject({ type: EffectType.DRAW_CARD, value: 2 });
      expect(d.optionDrafts![1].drafts[0]).toMatchObject({
        type: EffectType.HEAL,
        value: 3,
        fighterName: 'Alice',
      });
      // «place Alice in any other space» теперь PLACE (parser v5)
      expect(d.optionDrafts![2].drafts[0]).toMatchObject({
        type: EffectType.PLACE,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'Alice',
      });
    });

    it('PLACE «in any other space» → PLACE (не UNSUPPORTED, parser v5)', () => {
      const { drafts } = after('place Alice in any other space');
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.PLACE,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'Alice',
      });
    });

    it('PLACE «in any space» (без other) не сломан', () => {
      const { drafts } = after('place your fighter in any space');
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.PLACE,
        target: EffectTarget.SELF,
      });
    });

    it('Lurking: «Draw 1 card and choose 1 effect: - … - …» → [DRAW, CHOOSE_ONE]', () => {
      const { drafts } = after(
        'Draw 1 card and choose 1 effect: - move Invisible Man to a space with a fog token - move 1 fog token up to 3 spaces',
      );
      expect(drafts).toHaveLength(2);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.DRAW_CARD, value: 1 });
      const choose = drafts[1].draft;
      expect(choose.type).toBe(EffectType.CHOOSE_ONE);
      expect(choose.chooseCount).toBe(1);
      expect(choose.optionDrafts).toHaveLength(2);
    });

    it('НЕ матчит «Choose one of the fighters …» (выбор цели, не альтернатив)', () => {
      const { drafts } = after(
        'Choose one of the fighters in the combat and move them up to 2 spaces.',
      );
      expect(drafts[0].draft.type).not.toBe(EffectType.CHOOSE_ONE);
    });

    it('«Choose one of the fighters in the combat and move them up to 2 spaces.» → MOVE value 2 (parser v6)', () => {
      const { drafts, unsupported } = after(
        'Choose one of the fighters in the combat and move them up to 2 spaces.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.MOVE,
        value: 2,
        target: EffectTarget.SELF,
      });
    });

    it('«If you won the combat, choose one of the fighters … move them up to 2 spaces.» → MOVE value 2 + WON_COMBAT', () => {
      const { drafts, unsupported } = after(
        'If you won the combat, choose one of the fighters in the combat and move them up to 2 spaces.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.MOVE,
        value: 2,
        target: EffectTarget.SELF,
        when: { kind: 'WON_COMBAT' },
      });
    });

    it('НЕ матчит «… do both: …» (Shrink — оба эффекта, не выбор)', () => {
      const { drafts } = after(
        'Choose one effect. If Ms. Marvel\'s space shares no zones with the opposing fighter, do both: - your opponent discards 1 card - move the opposing fighter up to 3 spaces',
      );
      expect(drafts.every((x) => x.draft.type !== EffectType.CHOOSE_ONE)).toBe(true);
    });

    it('finalize: parseCardEffectTexts → options[] с id/label/effects + parserVersion', () => {
      const { effects } = parseCardEffectTexts(
        { after: 'Choose one: -Jill Trent recovers 1 health, -Draw 1 card' },
        'card-choose',
      );
      expect(effects).toHaveLength(1);
      const e = effects[0];
      expect(e.type).toBe(EffectType.CHOOSE_ONE);
      expect(e.parserVersion).toBe(PARSER_VERSION);
      expect(e.timing).toBe(EffectTiming.AFTER_COMBAT);
      expect(e.options).toHaveLength(2);
      expect(e.options![0].label).toBe('Jill Trent recovers 1 health');
      expect(e.options![0].effects[0]).toMatchObject({
        type: EffectType.HEAL,
        value: 1,
        timing: EffectTiming.AFTER_COMBAT,
      });
      // вложенные эффекты опций тоже получают id и метаданные парсера
      expect(e.options![0].effects[0].id).toBe('card-choose-after-0-opt0-0');
      expect(e.options![1].effects[0]).toMatchObject({ type: EffectType.DRAW_CARD, value: 1 });
    });
  });

  // ------------------------------------------------- «… unless …» (parser v7)
  // Blackbeard-механика: эффект происходит, ЕСЛИ оппонент НЕ заплатит дублоны
  // (unless 🪙). Платёжной механики в движке нет → моделируем как базовый
  // эффект с optional:true (оппонент может негировать). Лучше, чем UNSUPPORTED.
  describe('«… unless …» (v7)', () => {
    it('«Gain 1 action unless 🪙» → GAIN_ACTION optional (не UNSUPPORTED)', () => {
      const { drafts, unsupported } = after('Gain 1 action unless 🪙');
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.GAIN_ACTION,
        value: 1,
        optional: true,
      });
    });

    it('«Your opponent discards 1 random card unless 🪙» → UNSUPPORTED: random-база не выбор (S05-фикс)', () => {
      // Раньше «random» игнорировался и текст превращался в OPPONENT_DISCARD —
      // ВЫБОР сбрасывающего. Random-сброс двигком отдельно не исполняется →
      // честный UNSUPPORTED (misclassification-фикс, будущие карты).
      const { drafts, unsupported } = after('Your opponent discards 1 random card unless 🪙');
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft.type).toBe(EffectType.UNSUPPORTED);
      expect(unsupported).toHaveLength(1);
    });

    it('«Deal 3 damage to the opposing fighter unless 🪙 🪙» → DAMAGE optional', () => {
      const { drafts, unsupported } = after(
        'Deal 3 damage to the opposing fighter unless 🪙 🪙',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DAMAGE,
        value: 3,
        target: EffectTarget.OPPOSING_FIGHTER,
        optional: true,
      });
    });

    it('«… unless …» с нераспознаваемым базовым эффектом → UNSUPPORTED (не регресс)', () => {
      const { drafts, unsupported } = after('Conjure a storm unless 🪙');
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft.type).toBe(EffectType.UNSUPPORTED);
      expect(unsupported).toHaveLength(1);
    });
  });

  // ------------------------------------------------- «Do both:» / «X and Y» (v7)
  // Плоская последовательность под-эффектов (НЕ выбор). «Do both:» с буллетами
  // и инлайновое «X and Y» внутри предложения.
  describe('«Do both:» / «X and Y» (v7)', () => {
    it('«Do both: - draw 1 card - gain 1 action» → [DRAW, GAIN_ACTION]', () => {
      const { drafts, unsupported } = after('Do both: - draw 1 card - gain 1 action');
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(2);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.DRAW_CARD, value: 1 });
      expect(drafts[1].draft).toMatchObject({ type: EffectType.GAIN_ACTION, value: 1 });
    });

    it('«Do both: -your opponent discards 1 card -draw 1 card» → [OPP_DISCARD, DRAW]', () => {
      const { drafts, unsupported } = after(
        'Do both: -your opponent discards 1 card -draw 1 card',
      );
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(2);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.OPPONENT_DISCARD, value: 1 });
      expect(drafts[1].draft).toMatchObject({ type: EffectType.DRAW_CARD, value: 1 });
    });

    it('«draw 1 card and gain 1 action» (инлайн and) → [DRAW, GAIN_ACTION]', () => {
      const { drafts, unsupported } = after('Draw 1 card and gain 1 action.');
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(2);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.DRAW_CARD, value: 1 });
      expect(drafts[1].draft).toMatchObject({ type: EffectType.GAIN_ACTION, value: 1 });
    });

    it('«If you lost the combat, draw 1 card and gain 1 action.» → оба под WON/LOST', () => {
      const { drafts, unsupported } = after(
        'If you lost the combat, draw 1 card and gain 1 action.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(2);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.DRAW_CARD,
        value: 1,
        when: { kind: 'LOST_COMBAT' },
      });
      expect(drafts[1].draft).toMatchObject({
        type: EffectType.GAIN_ACTION,
        value: 1,
        when: { kind: 'LOST_COMBAT' },
      });
    });

    it('«X and Y» где Y не распознан → НЕ дробим, отдаём как одно (не регресс одиночек)', () => {
      // одиночный «and» внутри уже распознанного эффекта не должен ломаться:
      // «Move your fighter up to 3 spaces» содержит … но без второго глагола.
      const { drafts } = after('Move your fighter up to 3 spaces.');
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({ type: EffectType.MOVE, value: 3 });
    });
  });

  // ------------------------------------------------- Named-fighter adjacency (v7)
  describe('named-fighter adjacency heal (v7)', () => {
    it('«If Blackbeard is adjacent to an opposing fighter, he recovers 2 health.» → HEAL NAMED + ADJACENT', () => {
      const { drafts, unsupported } = after(
        'If Blackbeard is adjacent to an opposing fighter, he recovers 2 health.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts).toHaveLength(1);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.HEAL,
        value: 2,
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: 'Blackbeard',
        when: { kind: 'ADJACENT_TO_OPPONENT' },
      });
    });

    it('«If your fighter is adjacent to an opposing fighter, recover 1 health.» → HEAL SELF + ADJACENT', () => {
      const { drafts, unsupported } = after(
        'If your fighter is adjacent to an opposing fighter, recover 1 health.',
      );
      expect(unsupported).toEqual([]);
      expect(drafts[0].draft).toMatchObject({
        type: EffectType.HEAL,
        value: 1,
        target: EffectTarget.SELF,
        when: { kind: 'ADJACENT_TO_OPPONENT' },
      });
    });
  });
});
