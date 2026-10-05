/**
 * R-01 (run H, RESEARCH-2026-10-05 findings 5–6; DE-018 tail, F-01): the
 * snapshot carries the public log of the effects the last combat fired —
 * metadata.lastCombat.appliedEffects — so the client can show one line per
 * fired effect (+600 ms each) without guessing from snapshot differences.
 *
 *  - a combat with effects gives the log in order, with stage, side, source
 *    card, value, public targets and printed text; seq = the resolving state;
 *  - a combat without effects gives an empty list;
 *  - an option chosen in a combat CHOOSE_ONE points at the CHOOSE_ONE (parent);
 *    a combat paused for the choice has no new record until it ends;
 *  - privacy: owner-only details (`hidden`) reach only the effect's owner,
 *    the opponent's raw JSON names no hidden card;
 *  - save/load keeps it (key `lcr`); old saves read as "no record".
 * Production executor and effect services (as the S02 harness); real serializer.
 */
import { GameActionExecutorService } from '../services/game-action-executor.service';
import { CardEffectExecutorService, type EffectResult } from './card-effect-executor.service';
import { DeckManagementService } from '../services/deck-management.service';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { HeroAbilityRegistry } from '../abilities/hero-ability-registry';
import { GameStateService } from '../../games/game-state.service';
import { buildCombatEffectLog, projectLastCombat } from './combat-effect-log';
import {
  Card, CardEffect, CardType, EffectTarget as Target, EffectTiming as Timing, EffectType as Effect,
  FighterType, GamePhase, GameState, LastCombat,
} from '../models';

const effect = (id: string, type: Effect, extra: Partial<CardEffect> = {}): CardEffect => ({
  id, type, timing: Timing.AFTER_COMBAT, ...extra,
});
const card = (id: string, value: number, effects: CardEffect[] = []): Card => ({
  id, cardId: `cat-${id}`, name: `Card ${id}`, nameEn: `Card ${id}`, nameRu: id,
  cardType: CardType.VERSATILE, attackValue: value, defenseValue: value, effects,
});

/** p1 (f1) attacks p2 (f2) after both cards are revealed; p2 has a secret card in hand. */
function fixture(attack = 5, defense: number | null = 2,
  attackEffects: CardEffect[] = [], defenseEffects: CardEffect[] = []): GameState {
  const a = card('attack-1', attack, attackEffects);
  const d = card('defense-1', defense ?? 0, defenseEffects);
  return {
    gameId: 'r01', sequenceNumber: 10, phase: GamePhase.COMBAT_RESOLVE,
    turnCount: 1, currentTurnPlayerId: 'p1',
    players: ['p1', 'p2'].map((userId, i) => ({ userId, heroId: `h${i + 1}`,
      health: 10, maxHealth: 12, fighterIds: [i ? 'f2' : 'f1'], isAlive: true })),
    fighters: [['f1', 'p1'], ['f2', 'p2']].map(([id, ownerId], i) => ({
      id, ownerId, heroId: ownerId === 'p1' ? 'h1' : 'h2', name: id,
      type: FighterType.HERO, health: 10, maxHealth: 12, position: { x: i, y: 0 }, effects: [], hasSidekick: false,
    })),
    decks: { p1: { cards: [], drawPile: [card('p1-deck-top', 1)] },
      p2: { cards: [], drawPile: [{ ...card('p2-secret-draw', 1), name: 'Excalibur', nameEn: 'Excalibur' }] } },
    handZones: { p1: { cards: [], maxSize: 7 },
      p2: { cards: [{ ...card('p2-secret-hand', 3), isVisible: true }], maxSize: 7 } },
    discardPiles: { p1: [a], p2: defense === null ? [] : [d] },
    boardState: { width: 5, height: 5,
      cells: Array.from({ length: 5 }, (_, y) => Array.from({ length: 5 }, (_, x) => ({ x, y, type: 'normal' }))),
      doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date('2026-10-05T00:00:00Z'), lastActionBy: 'p1',
      version: 1, actionsRemaining: 1, combatInfo: {
        attackerId: 'f1', defenderId: 'p2', targetFighterId: 'f2',
        attackerCardId: a.id, defenderCardId: defense === null ? undefined : d.id,
        attackValue: attack, defenseValue: defense ?? 0, startedAt: new Date('2026-10-05T00:00:00Z'),
      } },
  } as GameState;
}

describe('R-01: public combat effect log in the snapshot (metadata.lastCombat)', () => {
  let service: GameActionExecutorService;
  const serializer = new GameStateService({} as never, {} as never);
  beforeEach(() => {
    const metrics = { measureServiceDuration: async (_a: string, _b: string, run: () => unknown) => run(),
      incrementGameAction: () => {}, incrementError: () => {} } as never;
    const adjacency = new AdjacencyService();
    const values = new ValueModifierService();
    const decks = new DeckManagementService();
    const registry = new HeroAbilityRegistry();
    service = new GameActionExecutorService(new GameRulesValidator(adjacency),
      new CombatResolverService(registry, metrics), undefined as never, values, adjacency, metrics,
      decks, new CardEffectExecutorService(values, metrics, adjacency, decks), registry);
  });
  async function resolve(state: GameState, userId = 'p1') {
    const result = await service.executeResolveCombat({ gameId: state.gameId } as never,
      { gameId: state.gameId, userId, currentState: state });
    expect(result.error).toBeUndefined();
    expect(result.success).toBe(true);
    return result.gameState!;
  }

  it('a combat with effects carries its fired effects in order, with stage, side, source and text', async () => {
    const state = await resolve(fixture(5, 2,
      [effect('atk-plus', Effect.MODIFY_VALUE, { timing: Timing.DURING_COMBAT, value: 2, text: 'Add 2 to the value.' }),
        effect('atk-hit', Effect.DAMAGE, { target: Target.OPPOSING_FIGHTER, value: 1, text: 'Deal 1 damage.' })],
      [effect('def-draw', Effect.DRAW_CARD, { value: 1, text: 'Draw 1 card.' })]));
    const lc = state.metadata.lastCombat!;
    expect(lc).toMatchObject({
      n: 1, seq: state.sequenceNumber, attackerFighterId: 'f1', targetFighterId: 'f2',
      attackerPlayerId: 'p1', defenderPlayerId: 'p2', attackerCardId: 'attack-1', defenderCardId: 'defense-1',
      finalAttack: 7, finalDefense: 2, defenderDamage: 5, attackerWon: true,
      attackerCardCancelled: false, defenderCardCancelled: false,
    });
    // DURING attacker, then AFTER: defender first, then attacker (rules order of the executor)
    expect(lc.appliedEffects).toEqual([
      { i: 0, timing: 'DURING', side: 'ATTACKER', playerId: 'p1',
        source: { kind: 'CARD', cardId: 'attack-1', catalogId: 'cat-attack-1', name: 'Card attack-1' },
        effectId: 'atk-plus', kind: 'MODIFY_VALUE', outcome: 'APPLIED', value: 2, targets: [],
        text: 'Add 2 to the value.' },
      { i: 1, timing: 'AFTER', side: 'DEFENDER', playerId: 'p2',
        source: { kind: 'CARD', cardId: 'defense-1', catalogId: 'cat-defense-1', name: 'Card defense-1' },
        effectId: 'def-draw', kind: 'DRAW_CARD', outcome: 'APPLIED', value: 1, targets: ['p2'],
        text: 'Draw 1 card.' },
      { i: 2, timing: 'AFTER', side: 'ATTACKER', playerId: 'p1',
        source: { kind: 'CARD', cardId: 'attack-1', catalogId: 'cat-attack-1', name: 'Card attack-1' },
        effectId: 'atk-hit', kind: 'DAMAGE', outcome: 'APPLIED', value: 1, targets: ['f2'],
        text: 'Deal 1 damage.' },
    ]);
    // the log is public: both players get it whole (no owner-only details here)
    for (const viewer of ['p1', 'p2']) {
      expect(serializer.filterPrivateData(state, viewer).metadata.lastCombat).toEqual(lc);
    }
  });

  it('a combat without effects carries an empty list; the record numbers combats', async () => {
    const base = fixture(5, 2);
    const prior: LastCombat = { n: 4, seq: 3, attackerFighterId: 'f2', targetFighterId: 'f1',
      attackerPlayerId: 'p2', defenderPlayerId: 'p1', attackerCardId: 'old', finalAttack: 1, finalDefense: 1,
      defenderDamage: 0, attackerWon: false, attackerCardCancelled: false, defenderCardCancelled: false,
      appliedEffects: [] };
    const state = await resolve({ ...base, metadata: { ...base.metadata, lastCombat: prior } });
    expect(state.metadata.lastCombat).toMatchObject({ n: 5, seq: 11, defenderDamage: 3, appliedEffects: [] });
  });

  it('a cancelled card fires nothing: only the cancelling effect is logged', async () => {
    const state = await resolve(fixture(5, 2,
      [effect('atk-hit', Effect.DAMAGE, { timing: Timing.ON_REVEAL, target: Target.OPPOSING_FIGHTER, value: 1 })],
      [effect('feint', Effect.CANCEL_EFFECTS, { timing: Timing.ON_REVEAL, text: 'Cancel all effects.' })]));
    const lc = state.metadata.lastCombat!;
    expect(lc.attackerCardCancelled).toBe(true);
    expect(lc.appliedEffects.map((e) => [e.timing, e.side, e.effectId, e.outcome]))
      .toEqual([['IMMEDIATELY', 'DEFENDER', 'feint', 'APPLIED']]);
  });

  it('the last combat of the game is logged too (GAME_OVER)', async () => {
    const state = await resolve(fixture(12, 2, [], [effect('def-draw', Effect.DRAW_CARD, { value: 1 })]));
    expect(state.phase).toBe(GamePhase.GAME_OVER);
    expect(state.metadata.lastCombat).toMatchObject({ seq: state.sequenceNumber, defenderDamage: 10 });
    // after-combat effects do not run once the duel is over
    expect(state.metadata.lastCombat!.appliedEffects).toEqual([]);
  });

  it('an option chosen in a combat CHOOSE_ONE points at the CHOOSE_ONE; no record while paused', async () => {
    const input = fixture(5, 2,
      [effect('atk-plus', Effect.MODIFY_VALUE, { timing: Timing.DURING_COMBAT, value: 3 })],
      [effect('def-choice', Effect.CHOOSE_ONE, { timing: Timing.DURING_COMBAT, text: 'Choose one.', options: [
        { label: 'Protect', effects: [effect('def-protect', Effect.PREVENT_DAMAGE, { timing: Timing.DURING_COMBAT })] },
      ] })]);
    const paused = await resolve(input);
    expect(paused.phase).toBe(GamePhase.COMBAT_RESOLVE);
    expect(paused.metadata.lastCombat).toBeUndefined();
    const pending = paused.metadata.pendingEffects![0];
    const result = await service.executeResolvePendingEffect({ gameId: input.gameId,
      effectId: pending.id, optionIndex: 0 },
      { gameId: input.gameId, userId: 'p2', currentState: paused });
    expect(result.success).toBe(true);
    const resumed = result.gameState!;
    const lc = resumed.metadata.lastCombat!;
    expect(lc).toMatchObject({ seq: resumed.sequenceNumber, defenderDamage: 0, attackerWon: false });
    expect(lc.appliedEffects.map((e) => ({ i: e.i, timing: e.timing, side: e.side, effectId: e.effectId,
      outcome: e.outcome, parent: e.parent }))).toEqual([
      { i: 0, timing: 'DURING', side: 'DEFENDER', effectId: 'def-choice', outcome: 'CHOICE', parent: undefined },
      { i: 1, timing: 'DURING', side: 'DEFENDER', effectId: 'def-protect', outcome: 'APPLIED', parent: 0 },
      { i: 2, timing: 'DURING', side: 'ATTACKER', effectId: 'atk-plus', outcome: 'APPLIED', parent: undefined },
    ]);
  });

  it('privacy: owner-only details reach only the owner; the opponent sees no hidden card', async () => {
    const state = await resolve(fixture(5, 2, [],
      [effect('def-search', Effect.SEARCH_ADD_TO_HAND, { searchCardName: 'Excalibur', text: 'Search your deck for Excalibur.' })]));
    const entry = state.metadata.lastCombat!.appliedEffects[0];
    expect(entry).toMatchObject({ playerId: 'p2', effectId: 'def-search', outcome: 'APPLIED', targets: ['p2'] });
    expect(entry.hidden?.note).toBeDefined();
    const own = serializer.filterPrivateData(state, 'p2').metadata.lastCombat!.appliedEffects[0];
    expect(own.hidden).toEqual(entry.hidden);
    const opponentView = serializer.filterPrivateData(state, 'p1');
    expect(opponentView.metadata.lastCombat!.appliedEffects[0]).not.toHaveProperty('hidden');
    expect(opponentView.metadata.lastCombat!.appliedEffects[0]).toEqual({ ...entry, hidden: undefined });
    // neither the card the search put into p2's hand nor the owner's note is in p1's raw view
    const raw = JSON.stringify(opponentView);
    expect(raw).not.toContain('p2-secret-draw');
    expect(raw).not.toContain(entry.hidden!.note!);
    expect(raw).not.toContain('p2-secret-hand');
    expect(raw).toContain('"lastCombat"');
  });

  it('privacy: a non-public target (a card instance) is an opaque owner-only ref', () => {
    const state = fixture();
    const results: EffectResult[] = [{
      success: true, effectId: 'e1', targetIds: ['f2', 'p2', 'card-instance-9'], valueApplied: 1, message: 'note',
      source: { playerId: 'p2', cardId: 'defense-1', catalogId: 'cat-defense-1', cardName: 'Card defense-1',
        kind: 'DISCARD' },
    }, {
      // a result saved before R-01 has no source: it is left out
      success: true, effectId: 'legacy', targetIds: [],
    }];
    const log = buildCombatEffectLog([{ timing: 'AFTER', results }], 'p1', state);
    expect(log).toEqual([{ i: 0, timing: 'AFTER', side: 'DEFENDER', playerId: 'p2',
      source: { kind: 'CARD', cardId: 'defense-1', catalogId: 'cat-defense-1', name: 'Card defense-1' },
      effectId: 'e1', kind: 'DISCARD', outcome: 'APPLIED', value: 1, targets: ['f2', 'p2'],
      hidden: { note: 'note', refs: ['card-instance-9'] } }]);
    const lc = { appliedEffects: log } as unknown as LastCombat;
    expect(JSON.stringify(projectLastCombat(lc, 'p1'))).not.toContain('card-instance-9');
    expect(projectLastCombat(lc, 'p2')).toBe(lc);
  });

  it('survives save/load (key `lcr`); old saves without it read as no record', async () => {
    const state = await resolve(fixture(5, 2, [],
      [effect('def-draw', Effect.DRAW_CARD, { value: 1, text: 'Draw 1 card.' })]));
    const wire = JSON.parse(JSON.stringify(serializer.serialize(state)));
    expect(wire.m.lcr.appliedEffects).toHaveLength(1);
    expect(serializer.deserialize(wire).metadata.lastCombat).toEqual(state.metadata.lastCombat);
    delete wire.m.lcr;
    expect(serializer.deserialize(wire).metadata.lastCombat).toBeUndefined();
  });
});
