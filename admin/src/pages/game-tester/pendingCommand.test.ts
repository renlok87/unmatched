import { describe, expect, it, vi } from 'vitest';
import { buildPendingResolve } from './pendingCommand';

const fighters = [
  { id: 'f-merlin', name: 'Merlin' },
  { id: 'f-harpy', name: 'Harpies 1' },
];
const hand = [
  { id: 'hand-boost', name: 'Boost card' },
  { id: 'hand-other', name: 'Other card' },
];
const revealed = [
  { id: 'prophecy::1', name: 'Prophecy A' },
  { id: 'prophecy::2', name: 'Prophecy B' },
  { id: 'prophecy::3', name: 'Prophecy C' },
  { id: 'prophecy::4', name: 'Prophecy D' },
];
const ctx = {
  pendingEffects: [
    { id: 'pe-prophecy', type: 'DECK_TOP_PICK', revealedCards: revealed },
    { id: 'pe-restless', type: 'CHOOSE_SPACE' },
  ],
  resolveCard: vi.fn((ref: string) => {
    const m = ref.match(/^c(\d+)$/i);
    const c = m ? hand[Number(m[1])] : hand.find((x) => x.id === ref || x.id?.startsWith(ref));
    if (!c) throw new Error(`Нет карты ${ref} в руке`);
    return c;
  }),
  resolveFighter: vi.fn((ref: string) => {
    const f = fighters.find((x) => x.id === ref || x.id?.startsWith(ref) || x.name === ref);
    if (!f) throw new Error(`Боец «${ref}» не найден`);
    return f;
  }),
};

describe('game-tester peffect: buildPendingResolve', () => {
  it('S06 CHOOSE_SPACE: «peffect <id> 2,1» → клетка без бойца', () => {
    expect(buildPendingResolve(['peffect', 'pe-restless', '2,1'], ctx)).toEqual({
      label: 'resolvePendingEffect(pe-restless, space 2,1)',
      input: { effectId: 'pe-restless', x: 2, y: 1 },
    });
  });

  it('S06 DECK_TOP_PICK: «card c0 c2» индексирует revealedCards (не руку)', () => {
    const r = buildPendingResolve(['peffect', 'pe-prophecy', 'card', 'c0', 'c2'], ctx);
    expect(r.input).toEqual({ effectId: 'pe-prophecy', cardIds: ['prophecy::1', 'prophecy::3'] });
    expect(ctx.resolveCard).not.toHaveBeenCalled();
  });

  it('S06 DECK_TOP_PICK: ORDER — полный порядок в порядке аргументов', () => {
    const r = buildPendingResolve(['peffect', 'pe-prophecy', 'card', 'c3', 'c1', 'c0', 'c2'], ctx);
    expect(r.input).toEqual({
      effectId: 'pe-prophecy',
      cardIds: ['prophecy::4', 'prophecy::2', 'prophecy::1', 'prophecy::3'],
    });
  });

  it('S06 DECK_TOP_PICK: revealed ref по id-префиксу тоже работает; вне диапазона — ошибка', () => {
    const r = buildPendingResolve(['peffect', 'pe-prophecy', 'card', 'prophecy::4'], ctx);
    expect(r.input).toEqual({ effectId: 'pe-prophecy', cardIds: ['prophecy::4'] });
    expect(() => buildPendingResolve(['peffect', 'pe-prophecy', 'card', 'c9'], ctx))
      .toThrow('Нет карты c9 в revealed pe-prophecy (карт: 4)');
  });

  it('card без revealed-эффекта → карты руки (DISCARD_CARDS/BOOST_CHOICE)', () => {
    const r = buildPendingResolve(['peffect', 'pe-discard', 'card', 'c0'], ctx);
    expect(r.input).toEqual({ effectId: 'pe-discard', cardIds: ['hand-boost'] });
    expect(ctx.resolveCard).toHaveBeenCalledWith('c0');
  });

  it('MOVE/PLACE: боец + клетка; TARGET_FIGHTER: боец без клетки', () => {
    expect(buildPendingResolve(['peffect', 'pe1', 'f-harpy', '3,0'], ctx).input)
      .toEqual({ effectId: 'pe1', fighterId: 'f-harpy', x: 3, y: 0 });
    expect(buildPendingResolve(['peffect', 'pe1', 'f-merlin'], ctx).input)
      .toEqual({ effectId: 'pe1', fighterId: 'f-merlin' });
  });

  it('плохие аргументы — внятные ошибки', () => {
    expect(() => buildPendingResolve(['peffect', 'pe1'], ctx))
      .toThrow('peffect <effectId> <f> [x,y] | <x>,<y> | card <c0> [...]');
    expect(() => buildPendingResolve(['peffect', 'pe1', 'card'], ctx))
      .toThrow('peffect <effectId> card <c0> [<c1> ...]');
    expect(() => buildPendingResolve(['peffect', 'pe1', 'f-merlin', 'x,y'], ctx))
      .toThrow('Плохая клетка: x,y');
  });
});
