import { GameActionExecutorService } from './game-action-executor.service';
import { DeckManagementService } from './deck-management.service';
import { GenericHeroAbilityHandler } from '../abilities/generic-hero-ability.handler';
import { GamePhase, FighterType, GameState } from '../models';

function fixture(hp = 1): GameState {
  return {
    gameId: 'terminal-fixture', sequenceNumber: 10, turnCount: 1,
    phase: GamePhase.ACTION_MANEUVER, currentTurnPlayerId: 'a',
    players: ['a', 'b'].map(userId => ({userId, heroId: userId, health: 10, maxHealth: 10, isAlive: true, fighterIds: [userId]})),
    fighters: [
      ...['a', 'b'].map(id => ({id, ownerId: id, heroId: id, name: id, type: FighterType.HERO, health: id === 'b' ? hp : 10, maxHealth: 10, effects: [], hasSidekick: true, position: {x: 0, y: 0}})),
      {id: 'helper', ownerId: 'b', heroId: 'b', name: 'helper', type: FighterType.MINION, health: 7, maxHealth: 7, effects: [], hasSidekick: false, position: {x: 1, y: 0}},
    ],
    decks: {b: {drawPile: [], heroId: 'b', userId: 'b'}},
    handZones: {b: {cards: [], maxSize: 7}}, discardPiles: {b: []},
    boardState: {width: 2, height: 1, cells: [], doors: {}, fog: {}, tokens: {}},
    metadata: {version: 1, lastActionAt: new Date(0), lastActionBy: 'a', actionsRemaining: 1, pendingEffects: []},
  } as unknown as GameState;
}

describe('S02 terminal damage boundaries', () => {
  it('derives defeat from the hero even with stale player flags and a live helper', () => {
    const executor = Object.create(GameActionExecutorService.prototype);
    const result = executor.checkAndApplyGameOver(fixture(0));
    expect(result.phase).toBe(GamePhase.GAME_OVER);
    expect(result.metadata.winnerId).toBe('a');
    expect(result.fighters.find(f => f.id === 'helper').health).toBe(7);
    expect(result.players.find(p => p.userId === 'b').isAlive).toBe(false);
  });

  it('exhaustion kills the hero and stops a second missing draw', async () => {
    const result = await new DeckManagementService().drawCards(fixture(), 'b', 2);
    expect(result.phase).toBe(GamePhase.GAME_OVER);
    expect(result.metadata.winnerId).toBe('a');
    expect(result.fighters.find(f => f.id === 'b')!.health).toBe(0);
    expect(result.fighters.find(f => f.id === 'helper')!.health).toBe(5);
    expect(result.sequenceNumber).toBe(10);
  });

  it('does not recycle discard and applies each nonlethal missing draw', async () => {
    const base = fixture(10);
    const discarded = { id: 'discarded', cardId: 'discarded' } as any;
    const state = { ...base, discardPiles: { b: [discarded] } };
    const result = await new DeckManagementService().drawCards(state, 'b', 2);
    expect(result.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(result.fighters.find(f => f.id === 'b')!.health).toBe(6);
    expect(result.fighters.find(f => f.id === 'helper')!.health).toBe(3);
    expect(result.decks.b.drawPile).toHaveLength(0);
    expect(result.handZones.b.cards).toHaveLength(0);
    expect(result.discardPiles.b).toEqual([discarded]);
    expect(state.fighters.find(f => f.id === 'b')!.health).toBe(10);
  });

  it('stops draw-then-heal abilities at lethal exhaustion', async () => {
    const handler = new GenericHeroAbilityHandler({
      heroId: 'b', rules: [{ trigger: 'turn-start', effect: { kind: 'turn-effect', draw: 2, heal: 10, gainAction: 1 } }],
    } as any, { deck: new DeckManagementService(), zone: {isInSameZone: () => true, manhattanDistance: () => 1} });
    const result = await handler.onTurnStart(fixture(), 'b');
    expect(result.phase).toBe(GamePhase.GAME_OVER);
    expect(result.fighters.find(f => f.id === 'b')!.health).toBe(0);
    expect(result.metadata.actionsRemaining).toBe(1);
  });

  it('lethal ability damage stops thenDraw and subsequent healing rules', async () => {
    const handler = new GenericHeroAbilityHandler({
      heroSlug: 'a', rules: [
        {trigger: 'turn-start', effect: {kind: 'turn-damage', value: 1, targetScope: 'enemy-in-zone', thenDraw: 1}},
        {trigger: 'turn-start', effect: {kind: 'turn-effect', heal: 5}},
      ],
    } as any, {deck: {drawCards: async () => {throw new Error('draw after terminal');}}, zone: {isInSameZone: () => true, manhattanDistance: () => 1}});
    const result = await handler.onTurnStart(fixture(), 'a');
    expect(result.phase).toBe(GamePhase.GAME_OVER);
    expect(result.metadata.winnerId).toBe('a');
    expect(result.fighters.find(f => f.id === 'helper')!.health).toBe(7);
  });
});
