/** GD-018: sequential pending-choice queue (ACC-008 server side).
 * Head-of-queue enforcement everywhere (not only in combat), ownership,
 * optional-only decline, action/turn gates while the chain is open,
 * deferred turn transfer persisted as pendingTurnEnd and resumed exactly once
 * when the queue drains. Engine-level: production executor + real serializer. */
import { GameState, GamePhase, PendingEffect } from '../models';
import { CardType, EffectType, EffectTiming } from '../models';
import { s03Fixture, s03Engine } from '../../test/fixtures/s03-engine.fixture';
import { GameStateService } from '../../games/game-state.service';

const { executor } = s03Engine();
const ctx = (state: GameState, userId = 'a') =>
  ({ userId, gameId: state.gameId, currentState: state }) as any;

function withQueue(hand = 0, actions = 2, pendings?: PendingEffect[]): GameState {
  const state = s03Fixture(hand, actions);
  const pe1: PendingEffect = { id: 'pe1', type: 'MOVE', playerId: 'a', value: 2,
    optional: false, text: 'Move up to 2 spaces' };
  const pe2: PendingEffect = { id: 'pe2', type: 'MOVE', playerId: 'a', value: 1,
    optional: true, text: 'You may move 1 space' };
  return { ...state, metadata: { ...state.metadata,
    pendingEffects: pendings ?? [pe1, pe2] } };
}

describe('GD-018: sequential pending queue', () => {
  it('enforces the head of the queue and ownership outside combat', async () => {
    const state = withQueue();
    const tailFirst = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe2', fighterId: 'a', x: 1, y: 0 }, ctx(state));
    expect(tailFirst.success).toBe(false);
    expect(tailFirst.error).toContain('first');
    const foreign = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'b', x: 2, y: 0 }, ctx(state, 'b'));
    expect(foreign.success).toBe(false);
    expect(foreign.error).toContain('другому игроку');
    const resolved = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 2, y: 0 }, ctx(state));
    expect(resolved.success).toBe(true);
    expect(resolved.gameState!.sequenceNumber).toBe(11);
    expect(resolved.gameState!.fighters.find(f => f.id === 'a')!.position).toEqual({ x: 2, y: 0 });
    expect(resolved.gameState!.metadata.pendingEffects!.map(p => p.id)).toEqual(['pe2']);
    const replay = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 2, y: 0 }, ctx(resolved.gameState!));
    expect(replay.success).toBe(false);
    expect(replay.error).toContain('не найден');
  });

  it('rejects invalid MOVE targets without mutation', async () => {
    const state = withQueue();
    const occupied = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 7, y: 0 }, ctx(state));
    expect(occupied.success).toBe(false);
    const unreachable = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 5, y: 0 }, ctx(state));
    expect(unreachable.success).toBe(false);
    const offBoard = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: -1, y: 0 }, ctx(state));
    expect(offBoard.success).toBe(false);
  });

  it('declines only an optional choice owned by the caller at the head', async () => {
    const state = withQueue();
    const notHead = await executor.executeDeclinePendingEffect(
      { gameId: state.gameId, effectId: 'pe2' }, ctx(state));
    expect(notHead.success).toBe(false);
    const mandatory = await executor.executeDeclinePendingEffect(
      { gameId: state.gameId, effectId: 'pe1' }, ctx(state));
    expect(mandatory.success).toBe(false);
    expect(mandatory.error).toContain('обязателен');
    const foreign = await executor.executeDeclinePendingEffect(
      { gameId: state.gameId, effectId: 'pe1' }, ctx(state, 'b'));
    expect(foreign.success).toBe(false);
    const resolved = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 2, y: 0 }, ctx(state));
    expect(resolved.success).toBe(true);
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: state.gameId, effectId: 'pe2' }, ctx(resolved.gameState!));
    expect(declined.success).toBe(true);
    expect(declined.gameState!.sequenceNumber).toBe(12);
    expect(declined.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('blocks attack, scheme, maneuver, end-turn, door and stance while the queue is open', async () => {
    const state = withQueue(1);
    const attack = await executor.executeAttack(
      { gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' } as any, ctx(state));
    expect(attack.success).toBe(false);
    const scheme = await executor.executePlayScheme(
      { gameId: state.gameId, cardId: 'h0' } as any, ctx(state));
    expect(scheme.success).toBe(false);
    const begin = await executor.executeBeginManeuver(
      { gameId: state.gameId, expectedSequenceNumber: 10 }, ctx(state));
    expect(begin.success).toBe(false);
    const end = await executor.executeEndTurn({ gameId: state.gameId } as any, ctx(state));
    expect(end.success).toBe(false);
    const door = await executor.executeToggleDoor(
      { gameId: state.gameId, x: 0, y: 0 } as any, ctx(state));
    expect(door.success).toBe(false);
    const stance = await executor.executeSetStance(
      { gameId: state.gameId, stanceId: 'x' }, ctx(state));
    expect(stance.success).toBe(false);
  });

  it('defers the turn transfer until the chain drains, then transfers exactly once', async () => {
    const card = { id: 's1', cardId: 's1', name: 'Scheme Move', nameEn: 'Scheme Move',
      nameRu: 'Scheme Move', cardType: CardType.SCHEME, effects: [
        { id: 's1-e1', type: EffectType.MOVE, timing: EffectTiming.ON_PLAY, value: 2, optional: true },
      ] } as any;
    const state = { ...withQueue(0, 1),
      handZones: { ...withQueue(0, 1).handZones,
        a: { cards: [{ ...card, isVisible: true }], maxSize: 7 } } };
    state.metadata = { ...state.metadata, pendingEffects: undefined };

    const played = await executor.executePlayScheme({ gameId: state.gameId, cardId: 's1' } as any, ctx(state));
    expect(played.success).toBe(true);
    const afterPlay = played.gameState!;
    expect(afterPlay.metadata.pendingEffects).toHaveLength(1);
    expect(afterPlay.metadata.pendingEffects![0].optional).toBe(true);
    // Second action of the turn has been spent; the transfer waits for the choice.
    expect(afterPlay.currentTurnPlayerId).toBe('a');
    expect(afterPlay.metadata.actionsRemaining).toBe(0);
    expect(afterPlay.metadata.pendingTurnEnd).toEqual({ playerId: 'a', endEffectsApplied: false });
    expect(afterPlay.sequenceNumber).toBe(11);

    const gated = await executor.executeAttack(
      { gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'nope' } as any, ctx(afterPlay));
    expect(gated.success).toBe(false);

    const pendingId = afterPlay.metadata.pendingEffects![0].id;
    const declined = await executor.executeDeclinePendingEffect(
      { gameId: state.gameId, effectId: pendingId }, ctx(afterPlay));
    expect(declined.success).toBe(true);
    const afterChain = declined.gameState!;
    // One mutation (+1) drained the queue and completed the deferred transfer.
    expect(afterChain.sequenceNumber).toBe(12);
    expect(afterChain.currentTurnPlayerId).toBe('b');
    expect(afterChain.metadata.actionsRemaining).toBe(2);
    expect(afterChain.metadata.pendingTurnEnd).toBeUndefined();
    expect(afterChain.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(afterChain.turnCount).toBe(2);
  });

  it('endTurn is rejected while the queue is open and never transfers', async () => {
    const state = withQueue(0, 2);
    const ended = await executor.executeEndTurn({ gameId: state.gameId } as any, ctx(state));
    expect(ended.success).toBe(false);
    expect(ended.error).toContain('pending choice');
    expect(ended.gameState).toBeUndefined();
  });

  it('keeps the queue, optional flags and pendingTurnEnd through save/load', async () => {
    const serializer = new GameStateService({} as any, {} as any);
    const card = { id: 's1', cardId: 's1', name: 'Scheme Move', nameEn: 'Scheme Move',
      nameRu: 'Scheme Move', cardType: CardType.SCHEME, effects: [
        { id: 's1-e1', type: EffectType.MOVE, timing: EffectTiming.ON_PLAY, value: 2, optional: true },
      ] } as any;
    const base = withQueue(0, 1);
    const state = { ...base, handZones: { ...base.handZones,
      a: { cards: [{ ...card, isVisible: true }], maxSize: 7 } },
      metadata: { ...base.metadata, pendingEffects: undefined } };
    const played = await executor.executePlayScheme({ gameId: state.gameId, cardId: 's1' } as any, ctx(state));
    expect(played.success).toBe(true);
    const roundtrip = serializer.deserialize(
      JSON.parse(JSON.stringify(serializer.serialize(played.gameState!))));
    expect(roundtrip.metadata.pendingEffects!.map(p => [p.id, p.optional]))
      .toEqual([[roundtrip.metadata.pendingEffects![0].id, true]]);
    expect(roundtrip.metadata.pendingTurnEnd).toEqual({ playerId: 'a', endEffectsApplied: false });
    const resumed = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: roundtrip.metadata.pendingEffects![0].id,
        fighterId: 'a', x: 1, y: 0 }, ctx(roundtrip));
    expect(resumed.success).toBe(true);
    // Reloaded deferral resumes: resolving the only choice completes the
    // deferred transfer exactly once.
    expect(resumed.gameState!.currentTurnPlayerId).toBe('b');
    expect(resumed.gameState!.metadata.pendingTurnEnd).toBeUndefined();
  });

  it('accepts a zero-step MOVE: "up to N" includes staying in place', async () => {
    const state = withQueue(); // pe1: mandatory MOVE value 2, боец 'a' на (0,0)
    const stays = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 0, y: 0 }, ctx(state));
    expect(stays.success).toBe(true);
    expect(stays.gameState!.fighters.find(f => f.id === 'a')!.position).toEqual({ x: 0, y: 0 });
    expect(stays.gameState!.sequenceNumber).toBe(11);
    expect(stays.gameState!.metadata.pendingEffects!.map(p => p.id)).toEqual(['pe2']);
  });

  it('resolves a mandatory MOVE when NO reachable free cell exists (no strand)', async () => {
    // Доска 2x1: 'a'(0,0), живой враг 'b'(1,0) —reachable пуст, занято всё.
    // Единственный легальный резолв mandatory «up to» — нулевой шаг.
    const base = s03Fixture(0, 2);
    const fighters = [
      { ...base.fighters.find(f => f.id === 'a')!, position: { x: 0, y: 0 } },
      { ...base.fighters.find(f => f.id === 'b')!, position: { x: 1, y: 0 } },
    ];
    const board = { width: 2, height: 1,
      cells: [[{ x: 0, y: 0, type: 'normal' }, { x: 1, y: 0, type: 'normal' }]],
      doors: {}, fog: {}, tokens: {} };
    const state: GameState = { ...base, fighters,
      boardState: board as any,
      metadata: { ...base.metadata, pendingEffects: [
        { id: 'pe1', type: 'MOVE', playerId: 'a', value: 2, optional: false } as PendingEffect,
      ] } };
    const anywhere = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 1, y: 0 }, ctx(state));
    expect(anywhere.success).toBe(false); // (1,0) занят живым врагом
    const stays = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 0, y: 0 }, ctx(state));
    expect(stays.success).toBe(true);
    expect(stays.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
  });

  it('rejects PLACE into a board hole and onto blocked cells without mutation', async () => {
    const base = s03Fixture(0, 2);
    const cells = base.boardState.cells.map(row => row.slice());
    (cells[1] as any)[3] = undefined; // дыра внутри границ
    (cells[1] as any)[4] = { x: 4, y: 1, type: 'obstacle' };
    const state: GameState = { ...base,
      boardState: { ...base.boardState, cells } as any,
      metadata: { ...base.metadata, pendingEffects: [
        { id: 'pp1', type: 'PLACE', playerId: 'a', optional: false } as PendingEffect,
      ] } };
    const hole = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pp1', fighterId: 'a', x: 3, y: 1 }, ctx(state));
    expect(hole.success).toBe(false);
    expect(hole.error).toContain('непроходима');
    expect(hole.gameState).toBeUndefined();
    const obstacle = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pp1', fighterId: 'a', x: 4, y: 1 }, ctx(state));
    expect(obstacle.success).toBe(false);
    expect(obstacle.error).toContain('непроходима');
  });

  it('a defeated-but-alive fighter does not block the endpoint (living-fighter predicate)', async () => {
    const base = s03Fixture(0, 2);
    const fighters = base.fighters.map(f =>
      f.id === 'helper' ? { ...f, isDefeated: true, health: 3 } : f);
    const state: GameState = { ...base, fighters,
      metadata: { ...base.metadata, pendingEffects: [
        { id: 'pe1', type: 'MOVE', playerId: 'a', value: 2, optional: false } as PendingEffect,
      ] } };
    const onto = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe1', fighterId: 'a', x: 1, y: 0 }, ctx(state));
    expect(onto.success).toBe(true);
    expect(onto.gameState!.fighters.find(f => f.id === 'a')!.position).toEqual({ x: 1, y: 0 });
  });

  it('system resolve never bypasses a NONEMPTY pending queue (GD-018 × GD-026)', async () => {
    // реальный путь: атака картой без effects → бой запаузен на mandatory
    // MOVE → истёкший дедлайн. Системный executeResolveCombat отклонён,
    // очередь НЕ тронута и НЕ сфабрикована: единственная легальная
    // прогрессия — production pending-резолвер (в бою его дергает
    // CombatTimeoutService.drainTimedOutPendingChoices с детерминированным
    // фолбэком).
    const atk = { id: 'atk-plain', cardId: 'cat-atk', name: 'Plain', nameEn: 'Plain', nameRu: 'Простая',
      cardType: CardType.VERSATILE, attackValue: 4, effects: [] } as any;
    const base = s03Fixture();
    const state: GameState = {
      ...base,
      fighters: base.fighters.map(f => f.id === 'b' ? { ...f, position: { x: 1, y: 0 } } : f),
      handZones: { a: { cards: [atk], maxSize: 7 }, b: { cards: [], maxSize: 7 } },
      metadata: { ...base.metadata, pendingEffects: [] },
    };
    const attacked = await executor.executeAttack(
      { gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'atk-plain' } as any,
      ctx(state));
    expect(attacked.success).toBe(true);
    const queue = [
      { id: 'pe-move', type: 'MOVE', playerId: 'a', value: 1, optional: false } as PendingEffect,
    ];
    const paused: GameState = {
      ...attacked.gameState!,
      phase: GamePhase.COMBAT_RESOLVE,
      metadata: { ...attacked.gameState!.metadata,
        combatInfo: { ...attacked.gameState!.metadata.combatInfo!, timeoutAt: new Date(Date.now() - 1000) },
        combatResolutionProgress: { defeatedBefore: [] } as any,
        pendingEffects: queue },
    };
    // системный резолв с непустой очередью — отказ, состояние нетронуто
    const rejected = await executor.executeResolveCombat(
      { gameId: state.gameId } as any,
      { userId: 'b', gameId: state.gameId, currentState: paused, systemInitiator: true });
    expect(rejected.success).toBe(false);
    expect(rejected.error).toBe('Resolve the pending choice first');
    expect(paused.metadata.pendingEffects).toHaveLength(1);
    expect(paused.metadata.pendingEffects![0].id).toBe('pe-move');
    expect(paused.sequenceNumber).toBe(attacked.gameState!.sequenceNumber);

    // детерминированный системный фолбэк для mandatory MOVE — нулевой шаг
    // (остаться на месте — легальный резолв «up to N»); применяется
    // production-резолвером и легально двигает очередь
    const fallback = await executor.buildSystemPendingFallback(queue[0], paused);
    expect(fallback).toEqual({ fighterId: 'a', x: 0, y: 0 });
    const drained = await executor.executeResolvePendingEffect(
      { gameId: state.gameId, effectId: 'pe-move', ...fallback! }, ctx(paused));
    expect(drained.success).toBe(true);
    expect(drained.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(drained.gameState!.metadata.pendingTurnEnd).toBeUndefined();
    // боец остался на месте (нулевая дистанция — валидный резолв)
    expect(drained.gameState!.fighters.find(f => f.id === 'a')!.position).toEqual({ x: 0, y: 0 });
    // входное состояние не мутировано
    expect(attacked.gameState!.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(paused.metadata.pendingEffects).toHaveLength(1);
  });
});
