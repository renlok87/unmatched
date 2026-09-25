/**
 * Разбор команды `peffect` game-tester'а в input мутации
 * resolvePendingEffect. Чистая функция (без React/gql) — покрыта юнит-тестом
 * pendingCommand.test.ts; GameTester только подставляет gameId.
 */
export interface PendingResolveCtx {
  pendingEffects: Array<{ id: string; revealedCards?: any[] }>;
  resolveCard: (ref: string) => any;
  resolveFighter: (ref: string) => any;
}

export interface PendingResolve {
  label: string;
  input: Record<string, unknown>;
}

const CELL = /^\d+\s*,\s*\d+$/;

export function buildPendingResolve(parts: string[], ctx: PendingResolveCtx): PendingResolve {
  const [, effId, fRef, posRef] = parts;
  if (!effId || !fRef) {
    throw new Error('peffect <effectId> <f> [x,y] | <x>,<y> | card <c0> [...]');
  }
  if (fRef === 'card') {
    const refs = parts.slice(3);
    if (refs.length === 0) throw new Error('peffect <effectId> card <c0> [<c1> ...]');
    // DECK_TOP_PICK: карты сняты с колоды в pending — их нет в руке;
    // refs индексируют revealedCards самого эффекта
    const revealed = ctx.pendingEffects.find((p) => p.id === effId)?.revealedCards;
    const cards = revealed
      ? refs.map((ref) => {
          const m = ref.match(/^c(\d+)$/i);
          const c = m ? revealed[Number(m[1])] : revealed.find((x) => x.id === ref || x.id?.startsWith(ref));
          if (!c) throw new Error(`Нет карты ${ref} в revealed ${effId} (карт: ${revealed.length})`);
          return c;
        })
      : refs.map((ref) => ctx.resolveCard(ref));
    return {
      label: `resolvePendingEffect(${effId}, card ${cards.map((c) => c.id).join(', ')})`,
      input: { effectId: effId, cardIds: cards.map((c) => c.id) },
    };
  }
  // CHOOSE_SPACE (S06): клетка без бойца — «peffect <id> 2,1»
  if (CELL.test(fRef)) {
    const [x, y] = fRef.split(',').map(Number);
    return { label: `resolvePendingEffect(${effId}, space ${x},${y})`, input: { effectId: effId, x, y } };
  }
  const f = ctx.resolveFighter(fRef);
  if (!posRef) {
    return { label: `resolvePendingEffect(${effId}, ${f.name})`, input: { effectId: effId, fighterId: f.id } };
  }
  const [x, y] = posRef.split(',').map(Number);
  if (Number.isNaN(x) || Number.isNaN(y)) throw new Error(`Плохая клетка: ${posRef}`);
  return {
    label: `resolvePendingEffect(${effId}, ${f.name} → ${x},${y})`,
    input: { effectId: effId, fighterId: f.id, x, y },
  };
}
