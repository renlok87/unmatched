import { Card, CardType, EffectType, EffectTiming, GamePhase, GameState } from '../models';
import { s03Card, s03Fixture, s03Engine } from '../../test/fixtures/s03-engine.fixture';
import { DeckManagementService } from './deck-management.service';

const context = (state: GameState, userId = 'a') => ({ gameId: state.gameId, userId, currentState: state });

describe('S03 turn and persistent choices: real production executor', () => {
  let service: any;
  beforeEach(() => { service = s03Engine().executor; });
  async function begin(state: GameState) {
    const r = await service.executeBeginManeuver({ gameId: state.gameId, expectedSequenceNumber: state.sequenceNumber }, context(state));
    expect(r.success).toBe(true);
    return r.gameState as GameState;
  }
  async function complete(state: GameState, moves: any[] = [], boostCardId?: string) {
    const r = await service.executeManeuver({ gameId: state.gameId,
      maneuverId: (state.metadata as any).pendingManeuver.id, moves, boostCardId }, context(state));
    expect(r.success).toBe(true);
    return r.gameState as GameState;
  }
  it.each(['executePass', 'executeEndTurn'])('rejects %s while mandatory actions remain', async method => {
    const state = s03Fixture();
    const r = await service[method]({ gameId: state.gameId }, context(state));
    expect(r.success).toBe(false);
    expect(state.sequenceNumber).toBe(10);
    expect(state.metadata.actionsRemaining).toBe(2);
  });
  it('two draw-only maneuvers spend two actions and do not draw for the next player', async () => {
    let state = await begin(s03Fixture());
    expect(state.handZones.a.cards.map(c => c.id)).toEqual(['a-new']);
    expect(state.metadata.actionsRemaining).toBe(1);
    state = await complete(state);
    expect(state.currentTurnPlayerId).toBe('a');
    state = await begin(state);
    expect(state.metadata.actionsRemaining).toBe(0);
    expect(state.currentTurnPlayerId).toBe('a');
    state = await complete(state);
    expect(state.currentTurnPlayerId).toBe('b');
    expect(state.sequenceNumber).toBe(14);
    expect(state.handZones.a.cards).toHaveLength(2);
    expect(state.handZones.b.cards).toHaveLength(0);
    expect(state.decks.b.drawPile).toHaveLength(2);
  });
  it('drawn boost is available before choosing movement, then discarded once', async () => {
    let state = await begin(s03Fixture());
    state = await complete(state, [{ fighterId: 'a', path: [1, 2, 3, 4, 5].map(x => ({ x, y: 0 })) }], 'a-new');
    expect(state.fighters[0].position).toEqual({ x: 5, y: 0 });
    expect(state.handZones.a.cards).toHaveLength(0);
    expect(state.discardPiles.a.map(c => c.id)).toEqual(['a-new']);
    expect(state.decks.a.drawPile.map(c => c.id)).toEqual(['a-next']);
    expect(state.metadata.actionsRemaining).toBe(1);
  });
  it('persists the stage through JSON reload; rejects replay of both stages', async () => {
    const start = s03Fixture();
    const pending = JSON.parse(JSON.stringify(await begin(start)));
    const request = { gameId: start.gameId, expectedSequenceNumber: start.sequenceNumber };
    expect((await service.executeBeginManeuver(request, context(pending))).success).toBe(false);
    const dto = { gameId: start.gameId, maneuverId: pending.metadata.pendingManeuver.id, moves: [] };
    const done = await complete(pending);
    expect((await service.executeManeuver(dto, context(done))).success).toBe(false);
    expect((await service.executeBeginManeuver(request, context(done))).success).toBe(false);
    expect(done.decks.a.drawPile).toHaveLength(1);
  });
  it('rejects forged/foreign choice and invalid movement without undoing the draw', async () => {
    const state = await begin(s03Fixture());
    const dto = { gameId: state.gameId, maneuverId: (state.metadata as any).pendingManeuver.id, moves: [] };
    expect((await service.executeManeuver(dto, context(state, 'b'))).success).toBe(false);
    expect((await service.executeManeuver({ ...dto, maneuverId: 'old' }, context(state))).success).toBe(false);
    expect((await service.executeManeuver({ ...dto, moves: [{ fighterId: 'a', path: [{ x: 5, y: 0 }] }] }, context(state))).success).toBe(false);
    expect((await service.executeManeuver({ ...dto, boostCardId: 'definition' }, context(state))).success).toBe(false);
    expect(state.handZones.a.cards.map(c => c.id)).toEqual(['a-new']);
    expect((await complete(state)).metadata.actionsRemaining).toBe(1);
  });
  it('blocks ordinary actions while maneuver completion is pending', async () => {
    const state = await begin(s03Fixture());
    for (const method of ['executeAttack', 'executePlayScheme', 'executeEndTurn', 'executePass', 'executeMoveFighter', 'executeSetStance', 'executeToggleDoor']) {
      const r = await service[method]({ gameId: state.gameId }, context(state));
      expect(r.success).toBe(false);
    }
  });
  it('rejects raw movement as a bypass of maneuver draw', async () => {
    const state = s03Fixture();
    const r = await service.executeMoveFighter({ gameId: state.gameId, fighterId: 'a', x: 1, y: 0 }, context(state));
    expect(r.success).toBe(false);
  });
  it('lethal maneuver draw ends the game without creating a movement choice', async () => {
    const base = s03Fixture();
    const state = { ...base, decks: { ...base.decks, a: { ...base.decks.a, drawPile: [] } },
      fighters: base.fighters.map(f => f.id === 'a' ? { ...f, health: 1 } : f) };
    const done = await begin(state);
    expect(done.phase).toBe(GamePhase.GAME_OVER);
    expect((done.metadata as any).pendingManeuver).toBeUndefined();
    expect(done.fighters.find(f => f.id === 'helper')!.health).toBe(8);
  });
  it('allows excess cards within the turn and requires owner-selected instance IDs at its end', async () => {
    let state = await complete(await begin(s03Fixture(7)));
    expect(state.handZones.a.cards).toHaveLength(8);
    expect(state.currentTurnPlayerId).toBe('a');
    state = await complete(await begin(state));
    expect(state.phase).toBe(GamePhase.TURN_END);
    expect(state.currentTurnPlayerId).toBe('a');
    const pending = (state.metadata as any).pendingHandDiscard;
    expect(pending).toMatchObject({ playerId: 'a', count: 2 });
    const dto = { gameId: state.gameId, pendingId: pending.id, cardIds: ['h1', 'a-next'] };
    for (const cardIds of [['h1'], ['h1', 'h1'], ['definition', 'a-next'], ['b-new', 'a-next']]) {
      expect((await service.executeDiscardToLimit({ ...dto, cardIds }, context(state))).success).toBe(false);
    }
    expect((await service.executeDiscardToLimit(dto, context(state, 'b'))).success).toBe(false);
    expect((await service.executeEndTurn({ gameId: state.gameId }, context(state))).success).toBe(false);
    const r = await service.executeDiscardToLimit(dto, context(JSON.parse(JSON.stringify(state))));
    expect(r.success).toBe(true);
    expect(r.gameState.handZones.a.cards).toHaveLength(7);
    expect(r.gameState.discardPiles.a.map((c: Card) => c.id)).toEqual(['h1', 'a-next']);
    expect(r.gameState.currentTurnPlayerId).toBe('b');
    expect(r.gameState.turnCount).toBe(2);
    expect((await service.executeDiscardToLimit(dto, context(r.gameState))).success).toBe(false);
  });
  it('honors an explicit END_TURN scheme after its effects', async () => {
    const base = s03Fixture();
    const scheme = { ...s03Card('scheme'), cardType: CardType.SCHEME,
      effects: [{ id: 'end', type: EffectType.END_TURN, timing: EffectTiming.ON_PLAY }] };
    const state = { ...base, handZones: { ...base.handZones, a: { ...base.handZones.a,
      cards: [{ ...scheme, isVisible: true }] } } };
    const r = await service.executePlayScheme({ gameId: state.gameId, cardId: 'scheme', fighterId: 'a' }, context(state));
    expect(r.success).toBe(true);
    expect(r.gameState.currentTurnPlayerId).toBe('b');
    expect(r.gameState.handZones.b.cards).toHaveLength(0);
  });

  it('keeps an explicitly granted extra action available until it is spent', async () => {
    const base = s03Fixture();
    const scheme = { ...s03Card('scheme'), cardType: CardType.SCHEME,
      effects: [{ id: 'gain', type: EffectType.GAIN_ACTION, timing: EffectTiming.ON_PLAY, value: 1 }] };
    const initial = { ...base, handZones: { ...base.handZones, a: { ...base.handZones.a,
      cards: [{ ...scheme, isVisible: true }] } } };
    const r = await service.executePlayScheme({ gameId: initial.gameId, cardId: 'scheme' }, context(initial));
    expect(r.success).toBe(true);
    expect(r.gameState.metadata.actionsRemaining).toBe(2);
    let state = await complete(await begin(r.gameState));
    expect(state.currentTurnPlayerId).toBe('a');
    expect(state.metadata.actionsRemaining).toBe(1);
    state = await complete(await begin(state));
    expect(state.currentTurnPlayerId).toBe('b');
    expect(state.handZones.b.cards).toHaveLength(0);
  });

  it.each([0, 2])('rejects a scheme outside its action budget/turn (%s actions)', async actions => {
    const base = s03Fixture(0, actions);
    const state = { ...base, currentTurnPlayerId: actions === 2 ? 'b' : 'a', handZones: { ...base.handZones,
      a: { ...base.handZones.a, cards: [{ ...s03Card('scheme'), cardType: CardType.SCHEME, isVisible: true }] } } };
    expect((await service.executePlayScheme({ gameId: state.gameId, cardId: 'scheme' }, context(state))).success).toBe(false);
  });

  it('rejects an attack after the action budget is exhausted', async () => {
    const base = s03Fixture(1, 0);
    const state = { ...base, fighters: base.fighters.map(f => f.id === 'b' ? { ...f, position: { x: 1, y: 0 } } : f) };
    expect((await service.executeAttack({ gameId: state.gameId, attackerId: 'a', targetId: 'b', cardId: 'h0' }, context(state))).success).toBe(false);
  });

  it('moves multiple friendly fighters with a single draw and action', async () => {
    const pending = await begin(s03Fixture());
    const result = await complete(pending, [
      { fighterId: 'a', path: [{ x: 1, y: 0 }] },
      { fighterId: 'helper', path: [{ x: 1, y: 1 }] },
    ]);
    expect(result.fighters[0].position).toEqual({ x: 1, y: 0 });
    expect(result.fighters[2].position).toEqual({ x: 1, y: 1 });
    expect(result.metadata.actionsRemaining).toBe(1);
    expect(result.handZones.a.cards).toHaveLength(1);
  });

  it('turn-end hooks run once when discard resumes', async () => {
    const engine = s03Engine();
    service = engine.executor;
    engine.registry.registerExtended({ heroId: 'a', abilityName: 'end draw', description: 'test',
      onTurnEnd: async (state: GameState, id: string) => new DeckManagementService().drawCards(state, id, 1),
    } as any);
    const state = await complete(await begin(s03Fixture(7, 1)));
    expect(state.handZones.a.cards).toHaveLength(9);
    const pending = state.metadata.pendingHandDiscard!;
    const r = await service.executeDiscardToLimit({ gameId: state.gameId, pendingId: pending.id, cardIds: ['h0', 'h1'] }, context(state));
    expect(r.success).toBe(true);
    expect(r.gameState.fighters[0].health).toBe(10);
    expect(r.gameState.handZones.a.cards).toHaveLength(7);
    expect(r.gameState.currentTurnPlayerId).toBe('b');
  });

  it('a defender finishing the second combat leaves excess-card selection with the attacker', async () => {
    const base = s03Fixture(8, 0);
    const state: GameState = { ...base, phase: GamePhase.COMBAT_RESOLVE,
      discardPiles: { a: [{ ...s03Card('attack'), attackValue: 2 }], b: [{ ...s03Card('defense'), defenseValue: 5 }] },
      metadata: { ...base.metadata, combatInfo: { attackerId: 'a', defenderId: 'b', targetFighterId: 'b',
        attackerCardId: 'attack', defenderCardId: 'defense', attackValue: 2, defenseValue: 5, startedAt: new Date(0) } } };
    const r = await service.executeResolveCombat({ gameId: state.gameId }, context(state, 'b'));
    expect(r.success).toBe(true);
    expect(r.gameState.phase).toBe(GamePhase.TURN_END);
    expect(r.gameState.currentTurnPlayerId).toBe('a');
    expect(r.gameState.metadata.pendingHandDiscard).toMatchObject({ playerId: 'a', count: 1 });
    const dto = { gameId: state.gameId, pendingId: r.gameState.metadata.pendingHandDiscard.id, cardIds: ['h0'] };
    expect((await service.executeDiscardToLimit(dto, context(r.gameState, 'b'))).success).toBe(false);
    const done = await service.executeDiscardToLimit(dto, context(r.gameState));
    expect(done.success).toBe(true);
    expect(done.gameState.currentTurnPlayerId).toBe('b');
    expect(done.gameState.handZones.b.cards).toHaveLength(0);
  });
});
