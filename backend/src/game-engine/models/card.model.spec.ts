/**
 * Card Model Tests — normalizeCardEffects
 *
 * Prisma Card.effects (Json) может содержать что угодно: валидный массив,
 * двойную сериализацию, мусор. Нормализатор никогда не бросает.
 */

import { EffectTiming, EffectType, normalizeCardEffects } from './card.model';

describe('normalizeCardEffects', () => {
  it('null/пусто → []', () => {
    expect(normalizeCardEffects(null, 'c1')).toEqual([]);
    expect(normalizeCardEffects(undefined, 'c1')).toEqual([]);
    expect(normalizeCardEffects('', 'c1')).toEqual([]);
    expect(normalizeCardEffects('[]', 'c1')).toEqual([]);
    expect(normalizeCardEffects([], 'c1')).toEqual([]);
  });

  it('валидный массив проходит как есть (id дополняется при отсутствии)', () => {
    const raw = [
      { type: 'DRAW_CARD', timing: 'AFTER_COMBAT', value: 2 },
      { id: 'my-id', type: 'SET_VALUE', timing: 'DURING_COMBAT', value: 4 },
    ];
    const result = normalizeCardEffects(raw, 'c1');
    expect(result).toHaveLength(2);
    expect(result[0].type).toBe(EffectType.DRAW_CARD);
    expect(result[0].timing).toBe(EffectTiming.AFTER_COMBAT);
    expect(result[0].value).toBe(2);
    expect(result[0].id).toBe('c1-e0');
    expect(result[1].id).toBe('my-id');
  });

  it('двойная сериализация (строка с JSON) парсится повторно', () => {
    const raw = JSON.stringify([{ type: 'HEAL', timing: 'AFTER_COMBAT', value: 1 }]);
    const result = normalizeCardEffects(raw, 'c1');
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe(EffectType.HEAL);
  });

  it('мусор → UNSUPPORTED с сырым текстом, не бросает', () => {
    const result = normalizeCardEffects('not a json {', 'c1');
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe(EffectType.UNSUPPORTED);
    expect(result[0].text).toBe('not a json {');
  });

  it('неизвестный type → UNSUPPORTED, неизвестный timing → AFTER_COMBAT', () => {
    const result = normalizeCardEffects(
      [{ type: 'TELEPORT', timing: 'SOMEDAY', value: 1 }],
      'c1',
    );
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe(EffectType.UNSUPPORTED);
    expect(result[0].timing).toBe(EffectTiming.AFTER_COMBAT);
  });

  it('элемент без type/timing → UNSUPPORTED, остальные живут', () => {
    const result = normalizeCardEffects(
      [{ value: 3 }, { type: 'DRAW_CARD', timing: 'AFTER_COMBAT', value: 1 }],
      'c1',
    );
    expect(result).toHaveLength(2);
    expect(result[0].type).toBe(EffectType.UNSUPPORTED);
    expect(result[1].type).toBe(EffectType.DRAW_CARD);
  });

  it('одиночный объект-эффект принимается', () => {
    const result = normalizeCardEffects(
      { type: 'GAIN_ACTION', timing: 'AFTER_COMBAT', value: 1 },
      'c1',
    );
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe(EffectType.GAIN_ACTION);
  });
});
