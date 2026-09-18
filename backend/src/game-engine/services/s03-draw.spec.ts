import { MetricsService } from '../../metrics/metrics.service';
import { GameStateFactory } from '../../test/fixtures/game-state.factory';
import { GenericHeroAbilityHandler } from '../abilities/generic-hero-ability.handler';
import { TurnEffect } from '../abilities/ability-config';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { EffectTiming, EffectType, FighterType, GamePhase, GameState } from '../models';
import { DeckManagementService } from './deck-management.service';

const card = (id: string) => GameStateFactory.createCard({ id, cardId: id });

function fixture(drawCount = 0, heroHp = 10): GameState {
  const drawPile = Array.from({ length: drawCount }, (_, i) => card(`draw-${i}`));
  return GameStateFactory.create({
    sequenceNumber: 21,
    phase: GamePhase.ACTION_MANEUVER,
    fighters: [
      GameStateFactory.createFighter({ id: 'hero', ownerId: 'player-1', health: heroHp }),
      GameStateFactory.createFighter({ id: 'helper', ownerId: 'player-1', type: FighterType.MINION, health: 7 }),
      GameStateFactory.createFighter({ id: 'fragile', ownerId: 'player-1', type: FighterType.MINION, health: 1 }),
      GameStateFactory.createFighter({ id: 'defeated', ownerId: 'player-1', type: FighterType.MINION, health: 4, isDefeated: true }),
      GameStateFactory.createFighter({ id: 'enemy', ownerId: 'player-2', position: { x: 1, y: 0 } }),
    ],
    decks: { 'player-1': { cards: drawPile, drawPile, topCard: drawPile[0] } },
    handZones: {
      'player-1': { cards: Array.from({ length: 7 }, (_, i) => ({ ...card(`hand-${i}`), isVisible: true })), maxSize: 7 },
    },
    discardPiles: { 'player-1': [card('discarded')] },
    metadata: { version: 1, lastActionAt: new Date(0), lastActionBy: 'player-1', actionsRemaining: 1 },
  });
}

function health(state: GameState): Record<string, number> {
  return Object.fromEntries(state.fighters.map(f => [f.id, f.health]));
}

function freeze<T>(value: T): T {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

describe('S03 shared draw/exhaustion contract (GD-011, ACC-004)', () => {
  const deck = new DeckManagementService();

  it('draws beyond seven in deck order and leaves the next top card', async () => {
    const state = freeze(fixture(3));
    const result = await deck.drawCards(state, 'player-1', 2);

    expect(result.handZones['player-1'].cards).toHaveLength(9);
    expect(result.handZones['player-1'].cards.slice(7)).toEqual([
      { ...card('draw-0'), isVisible: true }, { ...card('draw-1'), isVisible: true },
    ]);
    expect(result.decks['player-1'].drawPile).toEqual([card('draw-2')]);
    expect(result.decks['player-1'].topCard?.id).toBe('draw-2');
    expect(health(result)).toEqual({ hero: 10, helper: 7, fragile: 1, defeated: 4, enemy: 10 });
    expect(result.sequenceNumber).toBe(21);
    expect(state.handZones['player-1'].cards).toHaveLength(7);
    expect(state.decks['player-1'].drawPile).toHaveLength(3);
  });

  it('exhausts a full hand with an empty deck without recycling the discard', async () => {
    const state = freeze(fixture(0, 5));
    const result = await deck.drawCards(state, 'player-1', 1);

    expect(health(result)).toEqual({ hero: 3, helper: 5, fragile: 0, defeated: 4, enemy: 10 });
    expect(result.fighters.find(f => f.id === 'fragile')?.isDefeated).toBe(true);
    expect(result.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(result.handZones['player-1'].cards).toHaveLength(7);
    expect(result.decks['player-1'].drawPile).toEqual([]);
    expect(result.decks['player-1'].topCard).toBeUndefined();
    expect(result.discardPiles['player-1']).toEqual([card('discarded')]);
    expect(health(state)).toEqual({ hero: 5, helper: 7, fragile: 1, defeated: 4, enemy: 10 });
  });

  it('takes available cards first and applies each remaining exhaustion packet', async () => {
    const state = freeze(fixture(1));
    const result = await deck.drawCards(state, 'player-1', 3);

    expect(result.handZones['player-1'].cards).toHaveLength(8);
    expect(result.handZones['player-1'].cards[7].id).toBe('draw-0');
    expect(result.decks['player-1'].drawPile).toEqual([]);
    expect(health(result)).toEqual({ hero: 6, helper: 3, fragile: 0, defeated: 4, enemy: 10 });
    expect(result.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(result.sequenceNumber).toBe(21);
  });

  it.each([
    { heroHp: 1, helperHp: 5 },
    { heroHp: 3, helperHp: 3 },
  ])('stops immediately at hero defeat from $heroHp HP after a simultaneous packet', async ({ heroHp, helperHp }) => {
    const result = await deck.drawCards(freeze(fixture(1, heroHp)), 'player-1', 5);

    expect(health(result)).toEqual({ hero: 0, helper: helperHp, fragile: 0, defeated: 4, enemy: 10 });
    expect(result.phase).toBe(GamePhase.GAME_OVER);
    expect(result.metadata.winnerId).toBe('player-2');
    expect(result.players.find(p => p.userId === 'player-1')?.isAlive).toBe(false);
    expect(result.handZones['player-1'].cards).toHaveLength(8);
    expect(result.discardPiles['player-1']).toEqual([card('discarded')]);
    expect(result.sequenceNumber).toBe(21);
  });

  it('does not draw or apply another exhaustion packet after game over', async () => {
    const state = freeze({ ...fixture(1), phase: GamePhase.GAME_OVER });
    expect(await deck.drawCards(state, 'player-1', 3)).toBe(state);
    expect(deck.canDrawCard(state, 'player-1')).toBe(false);
  });

  it('permits an empty-deck draw request with a full hand so exhaustion can resolve', () => {
    expect(deck.canDrawCard(fixture(), 'player-1')).toBe(true);
  });

  it('applies card-effect exhaustion with a full hand and stops following effects', async () => {
    const effects = new CardEffectExecutorService(new ValueModifierService(), new MetricsService(), new AdjacencyService(), deck);
    const drawCard = GameStateFactory.createCard({ effects: [
      { id: 'draw', type: EffectType.DRAW_CARD, timing: EffectTiming.ON_PLAY, value: 3 },
      { id: 'action', type: EffectType.GAIN_ACTION, timing: EffectTiming.ON_PLAY, value: 1 },
    ] });
    const result = await effects.executeOnPlayEffects(freeze(fixture(0, 3)), drawCard, 'player-1');

    expect(result.state.phase).toBe(GamePhase.GAME_OVER);
    expect(health(result.state)).toEqual({ hero: 0, helper: 3, fragile: 0, defeated: 4, enemy: 10 });
    expect(result.state.metadata.actionsRemaining).toBe(1);
    expect(result.appliedEffects.map(e => e.effectId)).toEqual(['draw']);
  });

  it.each<TurnEffect>([
    { kind: 'turn-effect', draw: 3, heal: 10, gainAction: 1 },
    { kind: 'turn-effect', drawToHandSize: 10, heal: 10, gainAction: 1 },
  ])('applies generic ability exhaustion before healing or added actions: %j', async effect => {
    const handler = new GenericHeroAbilityHandler({
      heroId: 'arthur', abilityName: 'draw', description: 'draw then heal', rules: [{ trigger: 'turn-start', effect }],
    }, { deck, zone: new AdjacencyService() });
    const result = await handler.onTurnStart(freeze(fixture(0, 3)), 'player-1');

    expect(result.phase).toBe(GamePhase.GAME_OVER);
    expect(health(result)).toEqual({ hero: 0, helper: 3, fragile: 0, defeated: 4, enemy: 10 });
    expect(result.metadata.actionsRemaining).toBe(1);
  });

  it('applies thenDraw exhaustion after ability damage even with a full hand', async () => {
    const handler = new GenericHeroAbilityHandler({
      heroId: 'arthur', abilityName: 'hit then draw', description: 'damage then draw', rules: [{
        trigger: 'turn-start', effect: { kind: 'turn-damage', targetScope: 'enemy-adjacent', value: 1, thenDraw: 3 },
      }],
    }, { deck, zone: new AdjacencyService() });
    const result = await handler.onTurnStart(freeze(fixture(0, 1)), 'player-1');

    expect(result.phase).toBe(GamePhase.GAME_OVER);
    expect(health(result)).toEqual({ hero: 0, helper: 5, fragile: 0, defeated: 4, enemy: 9 });
    expect(result.metadata.winnerId).toBe('player-2');
  });
});
