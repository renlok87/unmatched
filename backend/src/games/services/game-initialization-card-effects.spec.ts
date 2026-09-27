/**
 * Инжест эффектов карт в GameInitializationService.resolveCardEffects.
 *
 * S09-фикс: DEFENSE/VERSATILE-карты с пустым effects-JSON и печатным
 * effectAfter («Hiss and Slither» / «Clutching Claws»: " Your opponent
 * discards 1 card.") должны парситься в CardEffect на инжесте колоды,
 * а не инициализироваться нулём эффектов (блокер DISCARD_CARDS в S09).
 * Регресс: ATTACK effectDuring, SCHEME fullText, непустые effects
 * (без повторного парса), нераспознанный текст → UNSUPPORTED.
 */
import { GameInitializationService } from './game-initialization.service';
import {
  CardEffect,
  CardType,
  EffectTarget,
  EffectTiming,
  EffectType,
} from '../../game-engine/models';
import { PARSER_VERSION } from '../../game-engine/effects/effect-text-parser';

const svc = new GameInitializationService({} as any, {} as any);
const resolve = (card: Record<string, unknown>): CardEffect[] =>
  (svc as any).resolveCardEffects(card);

const baseCard = {
  id: 'card-1',
  effects: null,
  effectImmediately: null,
  effectDuring: null,
  effectAfter: null,
  effectBoost: null,
  effectOngoing: null,
};

describe('GameInitializationService.resolveCardEffects — инжест карт', () => {
  it('DEFENSE с печатным effectAfter парсится в OPPONENT_DISCARD (Hiss and Slither)', () => {
    // Реальная форма строки из БД: ведущий пробел, точка в конце
    const effects = resolve({
      ...baseCard,
      cardType: 'DEFENSE',
      effectAfter: ' Your opponent discards 1 card.',
    });

    expect(effects).toHaveLength(1);
    expect(effects[0]).toMatchObject({
      type: EffectType.OPPONENT_DISCARD,
      value: 1,
      target: EffectTarget.OPPONENT_PLAYER,
      timing: EffectTiming.AFTER_COMBAT,
      source: 'parser',
      parserVersion: PARSER_VERSION,
    });
  });

  it('VERSATILE с печатным effectAfter парсится в OPPONENT_DISCARD (Clutching Claws)', () => {
    const effects = resolve({
      ...baseCard,
      cardType: 'VERSATILE',
      effectAfter: 'Your opponent discards 1 card',
    });

    expect(effects).toHaveLength(1);
    expect(effects[0]).toMatchObject({
      type: EffectType.OPPONENT_DISCARD,
      value: 1,
      timing: EffectTiming.AFTER_COMBAT,
    });
  });

  it('VERSATILE с двумя предложениями в effectAfter даёт оба эффекта (Pin the Prey)', () => {
    const effects = resolve({
      ...baseCard,
      cardType: 'VERSATILE',
      effectAfter: 'Move the opposing fighter up to 4 spaces. Your opponent discards 1 card.',
    });

    expect(effects).toHaveLength(2);
    expect(effects[0]).toMatchObject({
      type: EffectType.MOVE,
      value: 4,
      target: EffectTarget.OPPOSING_FIGHTER,
      timing: EffectTiming.AFTER_COMBAT,
    });
    expect(effects[1]).toMatchObject({
      type: EffectType.OPPONENT_DISCARD,
      value: 1,
      timing: EffectTiming.AFTER_COMBAT,
    });
  });

  it('ATTACK effectDuring продолжает парситься (регресс S05/S06)', () => {
    const effects = resolve({
      ...baseCard,
      cardType: 'ATTACK',
      effectDuring: 'You may BOOST this attack',
    });

    expect(effects).toHaveLength(1);
    expect(effects[0]).toMatchObject({
      type: EffectType.BOOST,
      boostSource: 'PLAYER_CHOICE_HAND',
      timing: EffectTiming.DURING_COMBAT,
    });
  });

  it('SCHEME fullText продолжает парситься (регресс S05/GD-019)', () => {
    const effects = resolve({
      ...baseCard,
      cardType: 'SCHEME',
      text: 'Draw 1 card',
    });

    expect(effects).toHaveLength(1);
    expect(effects[0]).toMatchObject({
      type: EffectType.DRAW_CARD,
      value: 1,
      timing: EffectTiming.AFTER_COMBAT,
    });
  });

  it('непустые effects НЕ парсятся повторно (manual-эффекты нетронуты)', () => {
    const manual: CardEffect[] = [
      {
        id: 'card-1-manual-0',
        type: EffectType.DRAW_CARD,
        value: 2,
        timing: EffectTiming.AFTER_COMBAT,
        text: 'Draw 2 cards',
        source: 'manual',
      },
    ];
    const effects = resolve({
      ...baseCard,
      cardType: 'DEFENSE',
      effects: manual,
      effectAfter: 'Your opponent discards 1 card.',
    });

    expect(effects).toEqual(manual);
  });

  it('нераспознанный effectAfter честно даёт UNSUPPORTED, не пустоту', () => {
    const effects = resolve({
      ...baseCard,
      cardType: 'DEFENSE',
      effectAfter: 'Conjure a spirit of vengeance against them',
    });

    expect(effects).toHaveLength(1);
    expect(effects[0]).toMatchObject({
      type: EffectType.UNSUPPORTED,
      timing: EffectTiming.AFTER_COMBAT,
      source: 'parser',
    });
    expect(effects[0].text).toBe('Conjure a spirit of vengeance against them');
  });

  it('карта без текстов эффектов → пустой массив', () => {
    expect(resolve({ ...baseCard, cardType: 'DEFENSE' })).toEqual([]);
    expect(
      resolve({ ...baseCard, cardType: 'VERSATILE', effectAfter: '   ' }),
    ).toEqual([]);
  });
});
