/** S02 deterministic in-process gameplay harness. No database, HTTP, credentials or seed.
 * Real action/effect/deck/validator/ability services; only metrics are inert.
 * Fixtures enter the production resolve action after both cards have been revealed.
 */
import { writeFileSync } from 'node:fs';
import { GameActionExecutorService, ActionResult } from './game-action-executor.service';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import { DeckManagementService } from './deck-management.service';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { HeroAbilityRegistry } from '../abilities/hero-ability-registry';
import { Card, CardEffect, CardType, EffectTarget as Target, EffectTiming as Timing,
  EffectType as Effect, FighterType, GamePhase, GameState } from '../models';

const effect = (id: string, type: Effect, extra: Partial<CardEffect> = {}): CardEffect => ({
  id, type, timing: Timing.AFTER_COMBAT, ...extra,
});
const card = (id: string, value: number, effects: CardEffect[] = []): Card => ({
  id, cardId: id, name: id, nameEn: id, nameRu: id,
  cardType: CardType.VERSATILE, attackValue: value, defenseValue: value, effects,
});
function fixture(attack = 2, defense: number | null = 5,
  attackEffects: CardEffect[] = [], defenseEffects: CardEffect[] = []): GameState {
  const a = card('attack::1', attack, attackEffects);
  const d = card('defense::1', defense ?? 0, defenseEffects);
  return {
    gameId: 's02-fixture', sequenceNumber: 10, phase: GamePhase.COMBAT_RESOLVE,
    turnCount: 1, currentTurnPlayerId: 'p1',
    players: ['p1', 'p2'].map((userId, i) => ({ userId, heroId: `h${i + 1}`,
      health: 10, maxHealth: 12, fighterIds: i ? ['f2', 's2'] : ['f1'], isAlive: true })),
    fighters: [['f1', 'p1', FighterType.HERO], ['f2', 'p2', FighterType.HERO],
      ['s2', 'p2', FighterType.MINION]].map(([id, ownerId, type], i) => ({
      id, ownerId, heroId: ownerId === 'p1' ? 'h1' : 'h2', name: id,
      type, health: 10, maxHealth: 12, position: { x: i, y: 0 }, effects: [], hasSidekick: false,
    })),
    decks: { p1: { cards: [], drawPile: [card('draw1', 1)] },
      p2: { cards: [], drawPile: [card('draw2', 1)] } },
    handZones: { p1: { cards: [], maxSize: 7 }, p2: { cards: [], maxSize: 7 } },
    discardPiles: { p1: [a], p2: defense === null ? [] : [d] },
    boardState: { width: 5, height: 5,
      cells: Array.from({ length: 5 }, (_, y) => Array.from({ length: 5 }, (_, x) => ({ x, y, type: 'normal' }))),
      doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date('2026-09-18T00:00:00Z'), lastActionBy: 'p1',
      version: 1, actionsRemaining: 1, combatInfo: {
        attackerId: 'f1', defenderId: 'p2', targetFighterId: 'f2',
        attackerCardId: a.id, defenderCardId: defense === null ? undefined : d.id,
        attackValue: attack, defenseValue: defense ?? 0, startedAt: new Date('2026-09-18T00:00:00Z'),
      } },
  } as GameState;
}

const observations: unknown[] = [];
describe('S02 real executor regression harness (R-08…R-13)', () => {
  let service: GameActionExecutorService;
  let registry: HeroAbilityRegistry;
  beforeEach(() => {
    const metrics = { measureServiceDuration: async (_a: string, _b: string, run: () => unknown) => run(),
      incrementGameAction: () => {}, incrementError: () => {} } as any;
    const adjacency = new AdjacencyService();
    const values = new ValueModifierService();
    const decks = new DeckManagementService();
    registry = new HeroAbilityRegistry();
    service = new GameActionExecutorService(new GameRulesValidator(adjacency),
      new CombatResolverService(registry, metrics), undefined as any, values, adjacency, metrics,
      decks, new CardEffectExecutorService(values, metrics, adjacency, decks), registry);
  });
  afterAll(() => {
    if (process.env.S02_REPORT) writeFileSync(process.env.S02_REPORT,
      JSON.stringify({ scope: 'in-process production executor; synthetic deterministic cards; no HTTP/UE',
        observations }, null, 2) + '\n');
  });
  const hp = (state: GameState) => state.fighters.map(f => f.health);
  const snapshot = (state: GameState) => ({ hp: hp(state), phase: state.phase,
    sequenceNumber: state.sequenceNumber,
    fighters: state.fighters.map(f => ({ id: f.id, hp: f.health, position: f.position })),
    handCounts: Object.fromEntries(Object.entries(state.handZones).map(([id, hand]) => [id, hand.cards.length])),
    pendingChoices: (state.metadata.pendingEffects ?? []).map(p => ({ id: p.id, type: p.type, playerId: p.playerId })),
  });
  function observe(id: string, before: GameState, result: ActionResult) {
    observations.push({ id, before: snapshot(before),
      after: result.gameState ? { ...snapshot(result.gameState),
        winnerId: result.gameState.metadata.winnerId ?? null,
        combat: result.metadata?.combatSummary ?? null,
        effects: result.metadata?.appliedEffects?.map(e => e.effectId) ?? [] } : null,
      success: result.success, error: result.error ?? null });
    expect(result.success).toBe(true);
    return result.gameState!;
  }
  async function resolve(id: string, state: GameState) {
    const result = await service.executeResolveCombat({ gameId: state.gameId } as any,
      { gameId: state.gameId, userId: 'p1', currentState: state });
    return { result, state: observe(id, state, result) };
  }

  it.each([[2, 5, 0, false], [4, 4, 0, false], [5, 2, 3, true], [3, null, 3, true]])(
    'clean attack %s / defense %s', async (a, d, damage, won) => {
      const { state, result } = await resolve(`clean-${a}-${d}`, fixture(a!, d));
      expect(hp(state)).toEqual([10, 10 - damage!, 10]);
      expect(result.metadata?.combatSummary).toMatchObject({ attackerDamage: 0, defenderDamage: damage, attackerWon: won });
    });
  const reward = (id: string) => effect(id, Effect.HEAL, { target: Target.SELF, value: 1, when: { kind: 'WON_COMBAT' } });
  it('prevented attack loses; only defender WON_COMBAT effect executes', async () => {
    const { state, result } = await resolve('prevent-winner', fixture(5, 2, [reward('attack-win')],
      [effect('prevent', Effect.PREVENT_DAMAGE, { timing: Timing.DURING_COMBAT }), reward('defense-win')]));
    expect(hp(state)).toEqual([10, 11, 10]);
    expect(result.metadata?.combatSummary?.attackerWon).toBe(false);
  });
  it('effect damage does not turn a lost attack into a won combat', async () => {
    const { state, result } = await resolve('effect-damage-not-win', fixture(2, 5,
      [effect('after-damage', Effect.DAMAGE, { target: Target.OPPOSING_FIGHTER, value: 2 }), reward('attack-win')], [reward('defense-win')]));
    expect(hp(state)).toEqual([10, 9, 10]);
    expect(result.metadata?.combatSummary?.attackerWon).toBe(false);
  });
  it('defender Feint cancels immediate/during/after effects, retaining printed attack', async () => {
    const { state, result } = await resolve('feint', fixture(5, 2, [
      effect('reveal-hit', Effect.DAMAGE, { timing: Timing.ON_REVEAL, target: Target.OPPOSING_FIGHTER, value: 1 }),
      effect('during-add', Effect.MODIFY_VALUE, { timing: Timing.DURING_COMBAT, value: 3 }), reward('after-heal'),
    ], [effect('feint', Effect.CANCEL_EFFECTS, { timing: Timing.ON_REVEAL })]));
    expect(hp(state)).toEqual([10, 7, 10]);
    expect(result.metadata?.combatSummary).toMatchObject({ finalAttack: 5, attackerCardCancelled: true });
  });
  it('Feint removes precommitted attack boost while retaining printed value and spent cards', async () => {
    const base = fixture(5, 2, [], [effect('boost-feint', Effect.CANCEL_EFFECTS, { timing: Timing.ON_REVEAL })]);
    const input = { ...base,
      discardPiles: { ...base.discardPiles, p1: [...base.discardPiles.p1, card('spent-boost', 3)] },
      metadata: { ...base.metadata, combatInfo: { ...base.metadata.combatInfo!, attackValue: 8 } },
    };
    const { state, result } = await resolve('feint-boost', input);
    expect(hp(state)).toEqual([10, 7, 10]);
    expect(result.metadata?.combatSummary).toMatchObject({ finalAttack: 5, attackerCardCancelled: true });
    expect(state.discardPiles).toEqual(input.discardPiles);
    expect(state.handZones).toEqual(input.handZones);
  });
  it('hero combat death ends duel despite living sidekick; cannot heal after death or act again', async () => {
    const input = fixture(12, 2, [], [effect('revive', Effect.HEAL, { target: Target.SELF, value: 8 })]);
    const { state } = await resolve('hero-death', input);
    expect(hp(state)).toEqual([10, 0, 10]);
    expect(state.phase).toBe(GamePhase.GAME_OVER);
    expect(state.metadata.winnerId).toBe('p1');
    const beforeRejectedActions = JSON.stringify(state);
    for (const action of [service.executeManeuver, service.executeMoveFighter, service.executeAttack,
      service.executePlayDefense, service.executePlayScheme, service.executeResolveCombat,
      service.executeEndTurn, service.executePass, service.executeToggleDoor, service.executeSetStance,
      service.executeResolvePendingEffect]) {
      const rejected = await action.call(service, { gameId: state.gameId } as any,
        { gameId: state.gameId, userId: 'p1', currentState: state });
      expect(rejected.success).toBe(false);
      expect(rejected.error).toMatch(/over|заверш/i);
      expect(rejected.gameState).toBeUndefined();
      expect(JSON.stringify(state)).toBe(beforeRejectedActions);
    }
  });
  it('sidekick combat death preserves duel and allows after-combat draw', async () => {
    const base = fixture(12, 2, [], [effect('draw', Effect.DRAW_CARD, { value: 1 })]);
    const input = { ...base, metadata: { ...base.metadata, combatInfo: { ...base.metadata.combatInfo!, targetFighterId: 's2' } } };
    const { state } = await resolve('sidekick-death', input);
    expect(hp(state)).toEqual([10, 10, 0]);
    expect(state.phase).not.toBe(GamePhase.GAME_OVER);
    expect(state.handZones.p2.cards).toHaveLength(1);
  });
  it.each([Timing.ON_REVEAL, Timing.DURING_COMBAT, Timing.AFTER_COMBAT])(
    '%s: defender resolves first and hero death stops the attacking effect', async timing => {
      const hit = (id: string) => effect(id, Effect.DAMAGE,
        { timing, target: Target.OPPOSING_FIGHTER, value: 10 });
      const { state, result } = await resolve(`defender-first-${timing}`,
        fixture(2, 2, [hit('attacker-hit')], [hit('defender-hit')]));
      expect(hp(state)).toEqual([0, 10, 10]);
      expect(state.phase).toBe(GamePhase.GAME_OVER);
      expect(state.metadata.winnerId).toBe('p2');
      expect(result.metadata?.appliedEffects?.map(e => e.effectId)).toEqual(['defender-hit']);
    });
  it('pauses for defender after-combat move, then reevaluates attacker target without replaying damage/draw', async () => {
    const input = fixture(4, 2,
      [effect('adjacent-hit', Effect.DAMAGE, { target: Target.ADJACENT_ENEMY, value: 3 })],
      [effect('before-move-draw', Effect.DRAW_CARD, { value: 1 }),
        effect('defender-move', Effect.MOVE, { target: Target.SELF, value: 2 })]);
    const { state: paused } = await resolve('move-paused', input);
    expect(paused.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(paused.sequenceNumber).toBe(11);
    expect(hp(paused)).toEqual([10, 8, 10]);
    expect(paused.handZones.p2.cards).toHaveLength(1);
    const pending = paused.metadata.pendingEffects![0];
    expect(pending.playerId).toBe('p2');
    const beforeWrongFighter = JSON.stringify(paused);
    const wrongFighter = await service.executeResolvePendingEffect({ gameId: input.gameId,
      effectId: pending.id, fighterId: 's2', x: 2, y: 1 },
      { gameId: input.gameId, userId: 'p2', currentState: paused });
    expect(wrongFighter.success).toBe(false);
    expect(JSON.stringify(paused)).toBe(beforeWrongFighter);
    const blocked = await service.executeResolveCombat({ gameId: input.gameId } as any,
      { gameId: input.gameId, userId: 'p1', currentState: paused });
    expect(blocked.success).toBe(false);
    const result = await service.executeResolvePendingEffect({ gameId: input.gameId,
      effectId: pending.id, fighterId: 'f2', x: 1, y: 2 },
      { gameId: input.gameId, userId: 'p2', currentState: paused });
    const resumed = observe('move-resumed', paused, result);
    expect(resumed.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(resumed.sequenceNumber).toBe(12);
    expect(resumed.metadata.actionsRemaining).toBe(1);
    expect(hp(resumed)).toEqual([10, 8, 10]);
    expect(resumed.fighters.find(f => f.id === 'f2')?.position).toEqual({ x: 1, y: 2 });
    expect(resumed.handZones.p2.cards).toHaveLength(1);
    expect(resumed.metadata.pendingEffects ?? []).toHaveLength(0);
    const replay = await service.executeResolvePendingEffect({ gameId: input.gameId,
      effectId: pending.id, fighterId: 'f2', x: 1, y: 2 },
      { gameId: input.gameId, userId: 'p2', currentState: resumed });
    expect(replay.success).toBe(false);
  });
  it.each([Timing.ON_REVEAL, Timing.DURING_COMBAT])(
    '%s: defender choice resumes with combat cancellation/prevent context', async timing => {
      const input = fixture(5, 2,
        [effect('attack-modifier', Effect.MODIFY_VALUE, { timing: Timing.DURING_COMBAT, value: 3 })],
        [effect('defender-choice', Effect.CHOOSE_ONE, { timing, options: [{ label: 'Protect', effects: [
          effect('selected-protect', timing === Timing.ON_REVEAL ? Effect.CANCEL_EFFECTS : Effect.PREVENT_DAMAGE,
            { timing }),
        ] }] })]);
      const { state: paused } = await resolve(`choice-paused-${timing}`, input);
      expect(paused.phase).toBe(GamePhase.COMBAT_RESOLVE);
      expect(paused.sequenceNumber).toBe(11);
      expect(hp(paused)).toEqual([10, 10, 10]);
      const pending = paused.metadata.pendingEffects![0];
      const result = await service.executeResolvePendingEffect({ gameId: input.gameId,
        effectId: pending.id, optionIndex: 0 },
        { gameId: input.gameId, userId: 'p2', currentState: paused });
      const resumed = observe(`choice-resumed-${timing}`, paused, result);
      expect(resumed.sequenceNumber).toBe(12);
      expect(resumed.phase).toBe(GamePhase.ACTION_MANEUVER);
      expect(hp(resumed)).toEqual([10, timing === Timing.ON_REVEAL ? 7 : 10, 10]);
      expect(resumed.metadata.pendingEffects ?? []).toHaveLength(0);
      expect(result.metadata?.appliedEffects?.filter(e => e.effectId === 'selected-protect')).toHaveLength(1);
    });
  it('terminal move reaction stops the remaining after-combat effects', async () => {
    registry.registerExtended({ heroId: 'h1', abilityName: 'Lethal reaction fixture', abilityDescription: 'Synthetic terminal reaction', onFighterMoved: async state => ({
      ...state, fighters: state.fighters.map(f => f.id === 'f2' ? { ...f, health: 0 } : f),
    }) });
    const input = fixture(2, 2, [effect('must-not-draw', Effect.DRAW_CARD, { value: 1 })],
      [effect('reaction-move', Effect.MOVE, { target: Target.SELF, value: 2 })]);
    const { state: paused } = await resolve('reaction-paused', input);
    expect(paused.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(paused.handZones.p1.cards).toHaveLength(0);
    const result = await service.executeResolvePendingEffect({ gameId: input.gameId,
      effectId: paused.metadata.pendingEffects![0].id, fighterId: 'f2', x: 1, y: 2 },
      { gameId: input.gameId, userId: 'p2', currentState: paused });
    const ended = observe('reaction-terminal', paused, result);
    expect(ended.phase).toBe(GamePhase.GAME_OVER);
    expect(ended.metadata.winnerId).toBe('p1');
    expect(ended.sequenceNumber).toBe(12);
    expect(hp(ended)).toEqual([10, 0, 10]);
    expect(ended.handZones.p1.cards).toHaveLength(0);
    expect(ended.metadata.pendingEffects ?? []).toHaveLength(0);
  });
  it('lethal scheme stops subsequent effects and keeps living sidekick from preserving duel', async () => {
    const input = fixture();
    const scheme = { ...card('scheme', 0, [
      effect('kill-hero', Effect.DAMAGE, { timing: Timing.ON_PLAY, target: Target.ADJACENT_ENEMY, value: 10 }),
      effect('later-draw', Effect.DRAW_CARD, { timing: Timing.ON_PLAY, value: 1 }),
    ]), cardType: CardType.SCHEME };
    const ready = { ...input, phase: GamePhase.ACTION_MANEUVER,
      handZones: { ...input.handZones, p1: { cards: [{ ...scheme, isVisible: false }], maxSize: 7 } } } as GameState;
    const result = await service.executePlayScheme({ gameId: input.gameId, cardId: scheme.id } as any,
      { gameId: input.gameId, userId: 'p1', currentState: ready });
    const state = observe('scheme-hero-death', ready, result);
    expect(hp(state)).toEqual([10, 0, 10]);
    expect(state.phase).toBe(GamePhase.GAME_OVER);
    expect(state.handZones.p1.cards).toHaveLength(0);
  });
});
