/**
 * DE-016 (W-11 server spike; D-DE-11 / F-11, SD-10, SD-16): a choice without
 * a legal target is never left waiting for input.
 *
 *  - PLACE without an eligible fighter / without a free space is not opened;
 *  - MOVE whose fighters cannot reach any free space other than their own is
 *    not opened (the zero step is applied without input);
 *  - a later choice of the queue is checked when it becomes the head (the
 *    drain), so an EACH move blocked only by an earlier mover is kept;
 *  - hero hooks (Leonardo's pending move at turn start) obey the same rule;
 *  - the reason reaches the client: metadata.skippedEffects (reason
 *    NO_VALID_TARGETS → why.effect.no.targets), survives save/load (key `se`)
 *    and the opponent's projection.
 * Engine-level: production executor (s03Engine) + real serializer.
 */
import type { CardEffect, GameState, PendingEffect, SkippedEffect } from '../models';
import { CardType, EffectTarget, EffectTiming, EffectType, FighterType, SKIPPED_EFFECTS_KEPT } from '../models';
import { s03Engine, s03Fixture } from '../../test/fixtures/s03-engine.fixture';
import { GameStateService } from '../../games/game-state.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { DeckManagementService } from '../services/deck-management.service';
import { GenericHeroAbilityHandler } from '../abilities/generic-hero-ability.handler';
import { ABILITY_CONFIGS } from '../abilities/ability-config';
import { NO_VALID_TARGETS_MESSAGE, pendingHasValidTarget, withSkippedEffect } from './pending-targets';

const { executor, registry } = s03Engine();
const zone = new AdjacencyService();
registry.registerExtended(new GenericHeroAbilityHandler(
  ABILITY_CONFIGS.find((c) => c.heroId === 'leonardo')!,
  { deck: new DeckManagementService(), zone } as never,
));

const ctx = (state: GameState, userId = 'a') =>
  ({ userId, gameId: state.gameId, currentState: state }) as never;

/**
 * s03 board 8×2: a (hero, p a) (0,0), helper (minion, p a) (0,1), b (hero, p b) (7,0).
 * `boxed` adds two more p b fighters so that neither a nor helper can reach a free space:
 * b at (1,0), b2 at (1,1) — enemies block, the ally's space is no endpoint.
 */
function base(opts: { boxed?: boolean; hand?: CardEffect[] } = {}): GameState {
  const state = s03Fixture(0, 2);
  let fighters = state.fighters;
  if (opts.boxed) {
    fighters = [
      ...fighters.map((f) => (f.id === 'b' ? { ...f, position: { x: 1, y: 0 } } : f)),
      { ...fighters.find((f) => f.id === 'b')!, id: 'b2', name: 'b2', type: FighterType.MINION,
        position: { x: 1, y: 1 } },
    ];
  }
  const card = opts.hand
    ? [{ id: 's1', cardId: 's1', name: 'Scheme', nameEn: 'Scheme', nameRu: 'Scheme',
        cardType: CardType.SCHEME, effects: opts.hand, isVisible: true }]
    : [];
  return {
    ...state,
    fighters,
    handZones: { ...state.handZones, a: { cards: card as never, maxSize: 7 } },
  };
}

const effect = (over: Partial<CardEffect>): CardEffect =>
  ({ id: 's1-e1', timing: EffectTiming.ON_PLAY, value: 1, text: 'printed text', ...over }) as CardEffect;

async function playScheme(state: GameState) {
  const r = await executor.executePlayScheme({ gameId: state.gameId, cardId: 's1' } as never, ctx(state));
  expect(r.error).toBeUndefined();
  expect(r.success).toBe(true);
  return r;
}

const notes = (s: GameState): readonly SkippedEffect[] => s.metadata.skippedEffects ?? [];

describe('DE-016: PLACE without a legal target', () => {
  it('does not open a PLACE for a fighter that is not in play and notes the skip', async () => {
    const state = base({ hand: [effect({ type: EffectType.PLACE, fighterName: 'Ghost', text: 'Place Ghost' })] });
    const r = await playScheme(state);
    const after = r.gameState!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(notes(after)).toEqual([{
      n: 1, seq: 10, reason: 'NO_VALID_TARGETS', playerId: 'a', effectId: 's1-e1-p0', kind: 'PLACE',
      text: 'Place Ghost',
    }]);
    expect(r.metadata?.appliedEffects).toEqual([
      expect.objectContaining({ success: false, effectId: 's1-e1', message: NO_VALID_TARGETS_MESSAGE }),
    ]);
    // The action is spent and the turn goes on: nothing waits for input.
    expect(after.sequenceNumber).toBe(11);
    expect(after.metadata.actionsRemaining).toBe(1);
  });

  it('does not open a PLACE for a defeated named fighter', async () => {
    const state = base({ hand: [effect({ type: EffectType.PLACE, fighterName: 'helper' })] });
    const defeated = { ...state, fighters: state.fighters.map((f) =>
      (f.id === 'helper' ? { ...f, health: 0, isDefeated: true } : f)) };
    const after = (await playScheme(defeated)).gameState!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(notes(after).map((n) => n.kind)).toEqual(['PLACE']);
  });

  it('keeps a PLACE that has an eligible fighter and a free space', async () => {
    const after = (await playScheme(base({ hand: [effect({ type: EffectType.PLACE, fighterName: 'helper' })] })))
      .gameState!;
    expect(after.metadata.pendingEffects).toEqual([expect.objectContaining({ type: 'PLACE', fighterName: 'helper' })]);
    expect(after.metadata.skippedEffects).toBeUndefined();
  });

  it('checks the zone of a revive PLACE (no free space in the zone → skipped)', () => {
    const state = base();
    const zoned: GameState = {
      ...state,
      boardState: {
        ...state.boardState,
        cells: state.boardState.cells.map((row) => row.map((c) => ({ ...c, zones: c.x <= 1 ? ['z1'] : ['z2'] }))),
      },
      fighters: [
        ...state.fighters,
        { ...state.fighters.find((f) => f.id === 'helper')!, id: 'harpy', name: 'Harpy 2', health: 0,
          isDefeated: true, position: { x: 5, y: 1 } },
        { ...state.fighters.find((f) => f.id === 'b')!, id: 'b2', position: { x: 1, y: 0 } },
        { ...state.fighters.find((f) => f.id === 'b')!, id: 'b3', position: { x: 1, y: 1 } },
      ],
    };
    const revive: PendingEffect = { id: 'r1', type: 'PLACE', playerId: 'a', fighterIds: ['harpy'],
      zoneFighterName: 'a', restoreFullHealth: true, optional: true };
    // z1 = x 0..1: a, helper, b2, b3 fill all four spaces
    expect(pendingHasValidTarget(zoned, revive, zone)).toBe(false);
    const freed = { ...zoned, fighters: zoned.fighters.filter((f) => f.id !== 'b3') };
    expect(pendingHasValidTarget(freed, revive, zone)).toBe(true);
  });
});

describe('DE-016: MOVE without a reachable space', () => {
  it('does not open a MOVE when no own fighter can reach a free space', async () => {
    const after = (await playScheme(base({ boxed: true,
      hand: [effect({ type: EffectType.MOVE, value: 2, text: 'Move up to 2 spaces' })] }))).gameState!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(notes(after)).toEqual([expect.objectContaining({ kind: 'MOVE', reason: 'NO_VALID_TARGETS', n: 1 })]);
    // The zero step: nobody moved, no trail of an effect move.
    expect(after.fighters.find((f) => f.id === 'a')!.position).toEqual({ x: 0, y: 0 });
    expect(after.metadata.lastMovement).toBeUndefined();
  });

  it('keeps the MOVE when one eligible fighter can move', async () => {
    const boxed = base({ boxed: true, hand: [effect({ type: EffectType.MOVE, value: 2 })] });
    const loose = { ...boxed, fighters: boxed.fighters.filter((f) => f.id !== 'b2') };
    const after = (await playScheme(loose)).gameState!;
    expect(after.metadata.pendingEffects).toEqual([expect.objectContaining({ type: 'MOVE', value: 2 })]);
  });

  it('checks a later EACH move when it becomes the head, after the earlier mover', async () => {
    // a (0,0) can step to (1,0); helper (0,1) is blocked by enemy b2 (1,1) and
    // can only reach a's space — legal once a has moved away.
    const state0 = base({ hand: [effect({ type: EffectType.MOVE, target: EffectTarget.EACH_OWN_FIGHTER, value: 1 })] });
    const state = { ...state0, fighters: [...state0.fighters,
      { ...state0.fighters.find((f) => f.id === 'b')!, id: 'b2', position: { x: 1, y: 1 } }] };
    const played = (await playScheme(state)).gameState!;
    const queue = played.metadata.pendingEffects!;
    expect(queue.map((p) => p.fighterIds)).toEqual([['a'], ['helper']]);

    const moved = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: queue[0].id, fighterId: 'a', x: 1, y: 0 }, ctx(played));
    expect(moved.success).toBe(true);
    expect(moved.gameState!.metadata.pendingEffects!.map((p) => p.id)).toEqual([queue[1].id]);
    expect(moved.gameState!.metadata.skippedEffects).toBeUndefined();

    // a stays (zero step): helper has nowhere to go → dropped by the drain.
    const stayed = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: queue[0].id, fighterId: 'a', x: 0, y: 0 }, ctx(played));
    expect(stayed.success).toBe(true);
    expect(stayed.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(notes(stayed.gameState!)).toEqual([expect.objectContaining({
      effectId: queue[1].id, kind: 'MOVE', playerId: 'a', seq: played.sequenceNumber + 1,
    })]);
  });

  it('the drain drops a dead head and resumes the deferred turn transfer exactly once', async () => {
    const state = s03Fixture(0, 0);
    const ok: PendingEffect = { id: 'pe1', type: 'MOVE', playerId: 'a', fighterIds: ['a'], value: 1, text: 'Move 1' };
    const dead: PendingEffect = { id: 'pe2', type: 'PLACE', playerId: 'a', fighterName: 'Ghost', text: 'Place Ghost' };
    const queued: GameState = { ...state, metadata: { ...state.metadata,
      pendingEffects: [ok, dead], pendingTurnEnd: { playerId: 'a', endEffectsApplied: true } } };
    const r = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 1, y: 0 }, ctx(queued));
    expect(r.success).toBe(true);
    const after = r.gameState!;
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(after.metadata.pendingTurnEnd).toBeUndefined();
    expect(after.currentTurnPlayerId).toBe('b');
    expect(after.sequenceNumber).toBe(11);
    expect(notes(after).map((n) => [n.effectId, n.kind])).toEqual([['pe2', 'PLACE']]);
  });
});

describe('DE-016: hero hooks and automatic effects', () => {
  function leonardoTurn(boxed: boolean): GameState {
    const state = s03Fixture(0, 0);
    const fighters = state.fighters.map((f) => {
      if (f.id === 'b') return { ...f, heroSlug: 'leonardo' };
      if (boxed && f.id === 'a') return { ...f, position: { x: 6, y: 0 } };
      if (boxed && f.id === 'helper') return { ...f, position: { x: 7, y: 1 } };
      return f;
    });
    return { ...state, fighters };
  }

  it('drops Leonardo\'s turn-start move when his fighter is boxed in', async () => {
    const r = await executor.executeEndTurn({ gameId: 's03' } as never, ctx(leonardoTurn(true)));
    expect(r.error).toBeUndefined();
    const after = r.gameState!;
    expect(after.currentTurnPlayerId).toBe('b');
    expect(after.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(notes(after)).toEqual([expect.objectContaining({ playerId: 'b', kind: 'MOVE', reason: 'NO_VALID_TARGETS' })]);
  });

  it('keeps Leonardo\'s turn-start move when his fighter can step', async () => {
    const r = await executor.executeEndTurn({ gameId: 's03' } as never, ctx(leonardoTurn(false)));
    expect(r.gameState!.metadata.pendingEffects).toEqual([expect.objectContaining({ type: 'MOVE', playerId: 'b' })]);
    expect(r.gameState!.metadata.skippedEffects).toBeUndefined();
  });

  it('notes an automatic effect without targets (damage to adjacent enemies, none adjacent)', async () => {
    const after = (await playScheme(base({ hand: [effect({ type: EffectType.DAMAGE,
      target: EffectTarget.ENEMIES_ADJACENT_TO_SELF, value: 2, text: 'Deal 2 damage' })] }))).gameState!;
    expect(notes(after)).toEqual([expect.objectContaining({ effectId: 's1-e1', kind: 'DAMAGE', text: 'Deal 2 damage' })]);
    expect(after.fighters.every((f) => f.health === 10)).toBe(true);
  });
});

describe('DE-016: the reason reaches the client', () => {
  it('numbers notes monotonically and keeps the last SKIPPED_EFFECTS_KEPT', () => {
    let state = s03Fixture();
    for (let i = 0; i < SKIPPED_EFFECTS_KEPT + 3; i++) {
      state = withSkippedEffect(state, { playerId: 'a', effectId: `e${i}`, kind: 'MOVE' });
    }
    const kept = notes(state);
    expect(kept).toHaveLength(SKIPPED_EFFECTS_KEPT);
    expect(kept[0].n).toBe(4);
    expect(kept[kept.length - 1]).toMatchObject({ n: SKIPPED_EFFECTS_KEPT + 3, effectId: `e${SKIPPED_EFFECTS_KEPT + 2}` });
  });

  it('survives save/load (key `se`) and the opponent\'s projection; old saves read as none', async () => {
    const after = (await playScheme(base({ hand: [effect({ type: EffectType.PLACE, fighterName: 'Ghost' })] })))
      .gameState!;
    const serializer = new GameStateService({} as never, {} as never);
    const wire = JSON.parse(JSON.stringify(serializer.serialize(after)));
    expect(wire.m.se).toHaveLength(1);
    const loaded = serializer.deserialize(wire);
    expect(loaded.metadata.skippedEffects).toEqual(after.metadata.skippedEffects);
    expect(serializer.filterPrivateData(loaded, 'b').metadata.skippedEffects).toEqual(after.metadata.skippedEffects);
    delete wire.m.se;
    expect(serializer.deserialize(wire).metadata.skippedEffects).toBeUndefined();
  });
});
