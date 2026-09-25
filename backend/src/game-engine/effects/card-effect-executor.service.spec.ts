/**
 * Card Effect Executor Tests (A3)
 *
 * Ключевые инварианты:
 * - эффекты НЕ меняют sequenceNumber
 * - порядок during: SET_VALUE → MODIFY → VALUE_PER_COUNT
 * - cancel гасит эффекты карты, но не её печатное значение
 * - after: исход по роли (ничья — победа защитника)
 */

import { Test, TestingModule } from '@nestjs/testing';
import { CardEffectExecutorService, CombatContext } from './card-effect-executor.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { DeckManagementService } from '../services/deck-management.service';
import { MetricsService } from '../../metrics/metrics.service';
import {
  Card,
  CardEffect,
  CardType,
  EffectTiming,
  EffectType,
  EffectTarget,
  FighterType,
  GamePhase,
} from '../models';
import type { GameState } from '../models';

const card = (id: string, effects: CardEffect[], extra: Partial<Card> = {}): Card => ({
  id,
  cardId: id,
  name: id,
  nameEn: id,
  nameRu: id,
  cardType: CardType.ATTACK,
  effects,
  ...extra,
});

let effSeq = 0;
const eff = (partial: Partial<CardEffect> & { type: EffectType }): CardEffect => ({
  id: `e-${partial.type}-${effSeq++}`,
  timing: EffectTiming.AFTER_COMBAT,
  ...partial,
});

const makeState = (overrides: Partial<GameState> = {}): GameState =>
  ({
    gameId: 'g1',
    sequenceNumber: 7,
    phase: GamePhase.COMBAT_RESOLVE,
    turnCount: 1,
    currentTurnPlayerId: 'p1',
    players: [
      { userId: 'p1', heroId: 'h1', health: 10, maxHealth: 10, fighterIds: ['f1'], isAlive: true },
      { userId: 'p2', heroId: 'h2', health: 10, maxHealth: 10, fighterIds: ['f2'], isAlive: true },
    ],
    fighters: [
      {
        id: 'f1', ownerId: 'p1', heroId: 'h1', name: 'Hero One', type: FighterType.HERO,
        health: 10, maxHealth: 12, position: { x: 1, y: 1 }, effects: [], hasSidekick: false,
      },
      {
        id: 'f2', ownerId: 'p2', heroId: 'h2', name: 'Hero Two', type: FighterType.HERO,
        health: 10, maxHealth: 12, position: { x: 2, y: 1 }, effects: [], hasSidekick: false,
      },
    ],
    decks: {
      p1: {
        cards: [],
        drawPile: [card('p1-top', [], { boostValue: 3 }), card('p1-next', [])],
        topCard: undefined,
      },
      p2: { cards: [], drawPile: [card('p2-top', []), card('p2-top2', [])], topCard: undefined },
    },
    discardPiles: { p1: [], p2: [] },
    handZones: {
      p1: { cards: [], maxSize: 7 },
      p2: { cards: [{ ...card('p2-hand', [], { boostValue: 2 }), isVisible: false }], maxSize: 7 },
    },
    boardState: { width: 5, height: 5, cells: [], doors: {}, fog: {}, tokens: {} },
    metadata: { lastActionAt: new Date(), lastActionBy: 'p1', version: 1, actionsRemaining: 1 },
    ...overrides,
  }) as GameState;

const combat: CombatContext = {
  attackerFighterId: 'f1',
  targetFighterId: 'f2',
  attackerPlayerId: 'p1',
  defenderPlayerId: 'p2',
  attackCardId: 'atk',
  defenseCardId: 'def',
  attackValue: 4,
  defenseValue: 2,
};

describe('CardEffectExecutorService (A3)', () => {
  let service: CardEffectExecutorService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CardEffectExecutorService,
        DeckManagementService,
        { provide: ValueModifierService, useValue: {} },
        {
          provide: AdjacencyService,
          useValue: {
            // смежность по манхэттену == 1 (без доски)
            isAdjacent: jest.fn((_s: GameState, a: { x: number; y: number }, b: { x: number; y: number }) =>
              Promise.resolve(Math.abs(a.x - b.x) + Math.abs(a.y - b.y) === 1),
            ),
          },
        },
        {
          provide: MetricsService,
          useValue: {
            measureServiceDuration: jest.fn((_n: string, _c: string, fn: () => unknown) => fn()),
            incrementError: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get(CardEffectExecutorService);
  });

  it('ИНВАРИАНТ: стадии эффектов не меняют sequenceNumber', async () => {
    const state = makeState();
    const atk = card('atk', [
      eff({ type: EffectType.DRAW_CARD, value: 1 }),
      eff({ type: EffectType.DAMAGE, value: 2, target: EffectTarget.OPPOSING_FIGHTER }),
    ]);
    const reveal = await service.executeRevealEffects(state, atk, null, combat);
    const calc = await service.executeCombatEffects(reveal.state, atk, null, combat);
    const after = await service.executeAfterCombatEffects(calc.state, atk, null, combat, {
      attackerWon: true,
      attackerDamage: 0,
      defenderDamage: 2,
    });
    expect(after.state.sequenceNumber).toBe(7);
  });

  describe('DURING_COMBAT', () => {
    it('порядок SET_VALUE → MODIFY → VALUE_PER_COUNT', async () => {
      // печатная атака 4; SET 2, MODIFY +1, PER_COUNT (рука p1 пуста → +0)
      const atk = card('atk', [
        eff({ type: EffectType.VALUE_PER_COUNT, timing: EffectTiming.DURING_COMBAT, count: { source: 'CARDS_IN_HAND', per: 1 } }),
        eff({ type: EffectType.MODIFY_VALUE, timing: EffectTiming.DURING_COMBAT, value: 1 }),
        eff({ type: EffectType.SET_VALUE, timing: EffectTiming.DURING_COMBAT, value: 2 }),
      ]);
      const calc = await service.executeCombatEffects(makeState(), atk, null, combat);
      expect(calc.finalAttack).toBe(2 + 1 + 0);
      expect(calc.finalDefense).toBe(2);
    });

    it('отменённая карта: эффекты не исполняются, печатное значение остаётся', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.SET_VALUE, timing: EffectTiming.DURING_COMBAT, value: 9 }),
      ]);
      const calc = await service.executeCombatEffects(makeState(), atk, null, combat, {
        attacker: true,
        defender: false,
      });
      expect(calc.finalAttack).toBe(4); // печатное, без SET 9
    });

    it('BLIND BOOST (SELF_DECK_TOP): сброс верха колоды, += boostValue', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.BOOST, timing: EffectTiming.DURING_COMBAT, boostSource: 'SELF_DECK_TOP', blind: true }),
      ]);
      const state = makeState();
      const calc = await service.executeCombatEffects(state, atk, null, combat);
      expect(calc.finalAttack).toBe(4 + 3); // p1-top boostValue 3
      expect(calc.state.decks.p1.drawPile).toHaveLength(1);
      expect(calc.state.discardPiles.p1.map((c) => c.id)).toContain('p1-top');
    });

    it('PREVENT_DAMAGE защитника выставляет флаг', async () => {
      const def = card('def', [
        eff({ type: EffectType.PREVENT_DAMAGE, timing: EffectTiming.DURING_COMBAT }),
      ], { cardType: CardType.DEFENSE });
      const calc = await service.executeCombatEffects(makeState(), null, def, combat);
      expect(calc.preventDamageToDefender).toBe(true);
      expect(calc.preventDamageToAttacker).toBe(false);
    });

    it('when WON_COMBAT в during не срабатывает (исход неизвестен)', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.MODIFY_VALUE, timing: EffectTiming.DURING_COMBAT, value: 5, when: { kind: 'WON_COMBAT' } }),
      ]);
      const calc = await service.executeCombatEffects(makeState(), atk, null, combat);
      expect(calc.finalAttack).toBe(4);
    });
  });

  describe('ON_REVEAL / CANCEL_EFFECTS', () => {
    it('Feint защитника отменяет карту атакующего до его Feint', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.CANCEL_EFFECTS, timing: EffectTiming.ON_REVEAL }),
      ]);
      const def = card('def', [
        eff({ type: EffectType.CANCEL_EFFECTS, timing: EffectTiming.ON_REVEAL }),
      ], { cardType: CardType.DEFENSE });
      const reveal = await service.executeRevealEffects(makeState(), atk, def, combat);
      expect(reveal.defenderCardCancelled).toBe(false);
      expect(reveal.attackerCardCancelled).toBe(true);
    });
  });

  describe('S02 defender-first and terminal resolution', () => {
    const result = { attackerWon: false, attackerDamage: 0, defenderDamage: 0 };

    it.each([EffectTiming.ON_REVEAL, EffectTiming.DURING_COMBAT])(
      '%s preserves selected cancellation/prevention and combat context through resume', async (timing) => {
        const atk = card('atk', [eff({ type: EffectType.DRAW_CARD, timing, value: 1 })]);
        const def = card('def', [eff({ type: EffectType.CHOOSE_ONE, timing, options: [{
          label: 'Protect', effects: [eff({ timing,
            type: timing === EffectTiming.ON_REVEAL ? EffectType.CANCEL_EFFECTS : EffectType.PREVENT_DAMAGE,
          })],
        }] })]);
        const paused = timing === EffectTiming.ON_REVEAL
          ? await service.executeRevealEffects(makeState(), atk, def, combat)
          : await service.executeCombatEffects(makeState(), atk, def, combat);
        const pending = paused.state.metadata.pendingEffects![0];
        const selected = await service.executeChosenEffects({
          ...paused.state, metadata: { ...paused.state.metadata, pendingEffects: [] },
        }, pending.optionEffects![0], pending.playerId, pending.card, pending.effectContext);
        const resumed = await service.resumeCombatEffects(selected.state);
        expect(resumed.attackerCardCancelled).toBe(timing === EffectTiming.ON_REVEAL);
        expect(resumed.preventDamageToDefender).toBe(timing === EffectTiming.DURING_COMBAT);
        expect(resumed.state.handZones.p1.cards).toHaveLength(timing === EffectTiming.ON_REVEAL ? 0 : 1);
      },
    );

    it('during resume preserves previous modifiers and prevent without executing them twice', async () => {
      const def = card('def', [
        eff({ timing: EffectTiming.DURING_COMBAT, type: EffectType.MODIFY_VALUE, value: 3 }),
        eff({ timing: EffectTiming.DURING_COMBAT, type: EffectType.PREVENT_DAMAGE }),
        eff({ timing: EffectTiming.DURING_COMBAT, type: EffectType.MOVE, value: 1 }),
      ]);
      const paused = await service.executeCombatEffects(makeState(), null, def, combat);
      expect(paused.finalDefense).toBe(5);
      expect(paused.state.metadata.pendingEffects![0].fighterIds).toEqual(['f2']);
      const resumed = await service.resumeCombatEffects({
        ...paused.state, metadata: { ...paused.state.metadata, pendingEffects: [] },
      });
      expect(resumed.finalDefense).toBe(5);
      expect(resumed.preventDamageToDefender).toBe(true);
      expect(resumed.appliedEffects).toHaveLength(0);
    });

    it.each([EffectTiming.ON_REVEAL, EffectTiming.DURING_COMBAT, EffectTiming.AFTER_COMBAT])(
      '%s pauses at defender movement and reevaluates attacker targets after resume', async (timing) => {
        const atk = card('atk', [eff({ type: EffectType.DAMAGE, timing, value: 2,
          target: EffectTarget.ENEMIES_ADJACENT_TO_SELF })]);
        const def = card('def', [eff({ type: EffectType.MOVE, timing, value: 2, target: EffectTarget.SELF })]);
        const state = makeState();
        const paused = timing === EffectTiming.ON_REVEAL
          ? await service.executeRevealEffects(state, atk, def, combat)
          : timing === EffectTiming.DURING_COMBAT
            ? await service.executeCombatEffects(state, atk, def, combat)
            : await service.executeAfterCombatEffects(state, atk, def, combat, result);
        expect(paused.state.fighters[1].health).toBe(10);
        expect(paused.appliedEffects).toHaveLength(1);
        // JSON round-trip represents the persisted continuation; movement is applied by the action executor.
        const moved = JSON.parse(JSON.stringify(paused.state)) as GameState;
        const resumed = await service.resumeCombatEffects({
          ...moved,
          fighters: moved.fighters.map((f) => f.id === 'f2' ? { ...f, position: { x: 4, y: 1 } } : f),
          metadata: { ...moved.metadata, pendingEffects: [] },
        });
        expect(resumed.stage).toBe(timing);
        expect(resumed.paused).toBe(false);
        expect(resumed.state.fighters[1].health).toBe(10);
        expect(resumed.appliedEffects[0].success).toBe(false);
        expect(resumed.state.metadata.combatEffectContinuation).toBeUndefined();
      },
    );

    it.each([EffectTiming.ON_REVEAL, EffectTiming.DURING_COMBAT, EffectTiming.AFTER_COMBAT])(
      '%s resolves defender damage before checking attacker health condition', async (timing) => {
        const atk = card('atk', [eff({ type: EffectType.DRAW_CARD, timing, value: 1,
          when: { kind: 'HEALTH_AT_MOST', value: 8 } })]);
        const def = card('def', [eff({ type: EffectType.DAMAGE, timing, value: 2,
          target: EffectTarget.OPPOSING_FIGHTER })]);
        const state = makeState();
        const resolved = timing === EffectTiming.ON_REVEAL
          ? await service.executeRevealEffects(state, atk, def, combat)
          : timing === EffectTiming.DURING_COMBAT
            ? await service.executeCombatEffects(state, atk, def, combat)
            : await service.executeAfterCombatEffects(state, atk, def, combat, result);
        expect(resolved.state.fighters[0].health).toBe(8);
        expect(resolved.state.handZones.p1.cards).toHaveLength(1);
        expect(resolved.appliedEffects.map((e) => e.effectId)).toEqual([
          def.effects![0].id, atk.effects![0].id,
        ]);
      },
    );

    it('Feint cancels every attacker timing while preserving printed attack', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.DAMAGE, timing: EffectTiming.ON_REVEAL, value: 2, target: EffectTarget.OPPOSING_FIGHTER }),
        eff({ type: EffectType.SET_VALUE, timing: EffectTiming.DURING_COMBAT, value: 99 }),
        eff({ type: EffectType.DRAW_CARD, value: 1 }),
      ]);
      const def = card('def', [eff({ type: EffectType.CANCEL_EFFECTS, timing: EffectTiming.ON_REVEAL })]);
      const reveal = await service.executeRevealEffects(makeState(), atk, def, combat);
      const cancelled = { attacker: reveal.attackerCardCancelled, defender: reveal.defenderCardCancelled };
      const calc = await service.executeCombatEffects(reveal.state, atk, def, combat, cancelled);
      const after = await service.executeAfterCombatEffects(calc.state, atk, def, combat, result, cancelled);
      expect(calc.finalAttack).toBe(combat.attackValue);
      expect(after.state.fighters[1].health).toBe(10);
      expect(after.state.handZones.p1.cards).toHaveLength(0);
    });

    it('hero lethal stops remaining defender effects and attacker effects immediately', async () => {
      const atk = card('atk', [eff({ type: EffectType.DAMAGE, value: 99, target: EffectTarget.OPPOSING_FIGHTER })]);
      const def = card('def', [
        eff({ type: EffectType.DAMAGE, value: 10, target: EffectTarget.OPPOSING_FIGHTER }),
        eff({ type: EffectType.DRAW_CARD, value: 1 }),
      ]);
      const after = await service.executeAfterCombatEffects(makeState(), atk, def, combat, result);
      expect(after.state.phase).toBe(GamePhase.GAME_OVER);
      expect(after.state.fighters[1].health).toBe(10);
      expect(after.state.handZones.p2.cards).toHaveLength(1);
      expect(after.appliedEffects).toHaveLength(1);
    });

    it('defeated sidekick still draws, but cannot heal itself or attack from its old position', async () => {
      const state = makeState();
      const sidekick = { ...state.fighters[0], id: 's1', type: FighterType.MINION, health: 0, isDefeated: true };
      const atk = card('atk', [
        eff({ type: EffectType.HEAL, value: 2, target: EffectTarget.SELF }),
        eff({ type: EffectType.DAMAGE, value: 2, target: EffectTarget.ENEMIES_ADJACENT_TO_SELF }),
        eff({ type: EffectType.MOVE, value: 2, target: EffectTarget.SELF }),
        eff({ type: EffectType.DRAW_CARD, value: 1 }),
      ]);
      const after = await service.executeAfterCombatEffects(
        { ...state, fighters: [...state.fighters, sidekick] }, atk, null,
        { ...combat, attackerFighterId: 's1' }, result,
      );
      expect(after.state.phase).toBe(GamePhase.COMBAT_RESOLVE);
      expect(after.state.fighters.find((f) => f.id === 's1')!.health).toBe(0);
      expect(after.state.fighters[1].health).toBe(10);
      expect(after.state.handZones.p1.cards).toHaveLength(1);
      expect(after.state.metadata.pendingEffects ?? []).toHaveLength(0);
    });

    it('scheme lethal does not run subsequent gain-action or draw effects', async () => {
      const scheme = card('scheme', [
        eff({ type: EffectType.DAMAGE, timing: EffectTiming.ON_PLAY, value: 10, target: EffectTarget.ALL_ENEMIES }),
        eff({ type: EffectType.DRAW_CARD, timing: EffectTiming.ON_PLAY, value: 1 }),
        eff({ type: EffectType.GAIN_ACTION, timing: EffectTiming.ON_PLAY, value: 2 }),
      ]);
      const after = await service.executeOnPlayEffects(makeState(), scheme, 'p1');
      expect(after.state.phase).toBe(GamePhase.GAME_OVER);
      expect(after.state.handZones.p1.cards).toHaveLength(0);
      expect(after.appliedEffects).toHaveLength(1);
    });
  });

  describe('AFTER_COMBAT', () => {
    it('WON/LOST по роли: Regroup защитника при ничьей = победа защитника', async () => {
      const def = card('def', [
        eff({ type: EffectType.DRAW_CARD, value: 1, when: { kind: 'LOST_COMBAT' } }),
        eff({ type: EffectType.DRAW_CARD, value: 2, when: { kind: 'WON_COMBAT' } }),
      ], { cardType: CardType.DEFENSE });
      const state = makeState();
      // ничья → attackerWon false → защитник won → draw 2
      const after = await service.executeAfterCombatEffects(state, null, def, combat, {
        attackerWon: false,
        attackerDamage: 0,
        defenderDamage: 0,
      });
      expect(after.state.handZones.p2.cards).toHaveLength(1 + 2);
      expect(after.state.decks.p2.drawPile).toHaveLength(0);
    });

    it('«If you won the combat, deal 8 damage» только при победе', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.DAMAGE, value: 8, target: EffectTarget.OPPOSING_FIGHTER, when: { kind: 'WON_COMBAT' } }),
      ]);
      const lost = await service.executeAfterCombatEffects(makeState(), atk, null, combat, {
        attackerWon: false, attackerDamage: 0, defenderDamage: 0,
      });
      expect(lost.state.fighters.find((f) => f.id === 'f2')!.health).toBe(10);

      const won = await service.executeAfterCombatEffects(makeState(), atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 2,
      });
      expect(won.state.fighters.find((f) => f.id === 'f2')!.health).toBe(2);
    });

    it('OPPONENT_DISCARD (без «random») — сбрасывающий ОППОНЕНТ выбирает карту: pending DISCARD_CARDS', async () => {
      const atk = card('atk', [eff({ type: EffectType.OPPONENT_DISCARD, value: 1 })]);
      const after = await service.executeAfterCombatEffects(makeState(), atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      // Рука НЕ тронута движком: карту выберет владелец выбора (p2) через
      // resolvePendingEffect(cardIds) — движок не решает за игрока.
      expect(after.state.handZones.p2.cards).toHaveLength(1);
      expect(after.state.discardPiles.p2).toHaveLength(0);
      expect(after.state.metadata.pendingEffects).toEqual([
        expect.objectContaining({ type: 'DISCARD_CARDS', playerId: 'p2', value: 1 }),
      ]);
      // очередь паузит остаток боевой цепочки
      expect(after.paused).toBe(true);
    });

    it('OPPONENT_DISCARD: пустая рука оппонента — чистый no-op без pending', async () => {
      const atk = card('atk', [eff({ type: EffectType.OPPONENT_DISCARD, value: 1 })]);
      const empty: GameState = {
        ...makeState(),
        handZones: { ...makeState().handZones, p2: { cards: [], maxSize: 5 } },
      };
      const after = await service.executeAfterCombatEffects(empty, atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(after.state.metadata.pendingEffects ?? []).toHaveLength(0);
      expect(after.paused).toBeFalsy();
    });

    it('GAIN_ACTION увеличивает actionsRemaining, END_TURN обнуляет', async () => {
      const gain = card('atk', [eff({ type: EffectType.GAIN_ACTION, value: 1 })]);
      const g = await service.executeAfterCombatEffects(makeState(), gain, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(g.state.metadata.actionsRemaining).toBe(2);

      const end = card('atk', [eff({ type: EffectType.END_TURN })]);
      const e = await service.executeAfterCombatEffects(makeState(), end, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(e.state.metadata.actionsRemaining).toBe(0);
    });

    it('RETURN_TO_HAND возвращает карту из сброса', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.RETURN_TO_HAND, when: { kind: 'WON_COMBAT' } }),
      ]);
      const state = makeState({
        discardPiles: { p1: [atk], p2: [] },
      });
      const after = await service.executeAfterCombatEffects(state, atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(after.state.discardPiles.p1).toHaveLength(0);
      expect(after.state.handZones.p1.cards.map((c) => c.id)).toContain('atk');
    });

    it('RETURN_TO_HAND возвращает восьмую карту до проверки лимита в конце хода', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.RETURN_TO_HAND, when: { kind: 'WON_COMBAT' } }),
      ]);
      const hand = Array.from({ length: 7 }, (_, i) => ({ ...card(`hand-${i}`, []), isVisible: true }));
      const discarded = card('other-discard', []);
      const state = makeState({
        handZones: { ...makeState().handZones, p1: { cards: hand, maxSize: 7 } },
        discardPiles: { p1: [discarded, atk], p2: [] },
      });

      const after = await service.executeAfterCombatEffects(state, atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });

      expect(after.state.handZones.p1.cards).toEqual([...hand, { ...atk, isVisible: true }]);
      expect(after.state.discardPiles.p1).toEqual([discarded]);
      expect(after.state.sequenceNumber).toBe(state.sequenceNumber);
      expect(state.handZones.p1.cards).toHaveLength(7);
      expect(state.discardPiles.p1).toEqual([discarded, atk]);
    });

    it('HEAL не превышает maxHealth', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.HEAL, value: 99, target: EffectTarget.SELF }),
      ]);
      const after = await service.executeAfterCombatEffects(makeState(), atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(after.state.fighters.find((f) => f.id === 'f1')!.health).toBe(12);
    });

    it('MOVE → pendingEffects (выбор игрока), UNSUPPORTED → manual; бойцы не тронуты', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.MOVE, value: 3, text: 'Move your fighter up to 3 spaces.' }),
        eff({ type: EffectType.UNSUPPORTED, text: 'Something weird.' }),
      ]);
      const state = makeState();
      const after = await service.executeAfterCombatEffects(state, atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      // легитимный MOVE-pending ≠ manual: аудит ручных эффектов пуст
      expect(after.manualEffects).toEqual([]);
      const pending = after.state.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({ type: 'MOVE', playerId: 'p1', value: 3 });
      expect(after.state.fighters).toEqual(state.fighters);
      const resumed = await service.resumeCombatEffects({
        ...after.state, metadata: { ...after.state.metadata, pendingEffects: [] },
      });
      expect(resumed.manualEffects).toEqual(['Something weird.']);
    });

    it('when DECK_EMPTY: эффект не работает при непустой колоде', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.DRAW_CARD, value: 1, when: { kind: 'DECK_EMPTY' } }),
      ]);
      const notEmpty = await service.executeAfterCombatEffects(makeState(), atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(notEmpty.state.handZones.p1.cards).toHaveLength(0);
    });
  });

  describe('executeOnPlayEffects (scheme)', () => {
    it('исполняет AFTER_COMBAT-тексты scheme-карты; MOVE → pending, не manual', async () => {
      const scheme = card('sch', [
        eff({ type: EffectType.DRAW_CARD, value: 1 }),
        eff({ type: EffectType.MOVE, value: 4, text: 'Move Daredevil up to 4 spaces.' }),
      ], { cardType: CardType.SCHEME });
      const result = await service.executeOnPlayEffects(makeState(), scheme, 'p1');
      expect(result.state.handZones.p1.cards).toHaveLength(1);
      const pending = result.state.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({ type: 'MOVE', playerId: 'p1', value: 4 });
      // легитимный pending ≠ manual-эффект
      expect(result.manualEffects).toEqual([]);
    });
  });

  describe('CHOOSE_ONE (v3)', () => {
    const chooseEffect = (chooseCount = 1) =>
      eff({
        type: EffectType.CHOOSE_ONE,
        chooseCount,
        text: 'Choose one',
        options: [
          { label: 'Draw 1 card', effects: [eff({ type: EffectType.DRAW_CARD, value: 1 })] },
          {
            label: 'Recover 2 health',
            effects: [eff({ type: EffectType.HEAL, value: 2, target: EffectTarget.SELF })],
          },
        ],
      });

    it('CHOOSE_ONE → pendingEffect c options/optionEffects/chooseCount; бойцы не тронуты', async () => {
      const state = makeState();
      const after = await service.executeAfterCombatEffects(
        state,
        card('atk', [chooseEffect()]),
        null,
        combat,
        { attackerWon: true, attackerDamage: 0, defenderDamage: 1 },
      );
      const pending = after.state.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({ type: 'CHOOSE_ONE', playerId: 'p1', chooseCount: 1 });
      expect(pending[0].options).toEqual([
        { index: 0, label: 'Draw 1 card' },
        { index: 1, label: 'Recover 2 health' },
      ]);
      expect(pending[0].optionEffects).toHaveLength(2);
      // эффект отложен в легитимный pending — НЕ manual; бойцы не изменены
      expect(after.manualEffects).toEqual([]);
      expect(after.state.fighters).toEqual(state.fighters);
    });

    it('CHOOSE_ONE без распознанных опций → manual (как UNSUPPORTED)', async () => {
      const empty = eff({ type: EffectType.CHOOSE_ONE, text: 'Choose one', options: [] });
      const after = await service.executeAfterCombatEffects(
        makeState(),
        card('atk', [empty]),
        null,
        combat,
        { attackerWon: true, attackerDamage: 0, defenderDamage: 1 },
      );
      expect(after.state.metadata.pendingEffects ?? []).toHaveLength(0);
      expect(after.manualEffects).toContain('Choose one');
    });

    it('executeChosenEffects: опция DRAW добирает карту', async () => {
      const res = await service.executeChosenEffects(
        makeState(),
        [eff({ type: EffectType.DRAW_CARD, value: 1 })],
        'p1',
      );
      expect(res.state.handZones.p1.cards).toHaveLength(1);
    });

    it('executeChosenEffects: опция GAIN_ACTION добавляет действие', async () => {
      const res = await service.executeChosenEffects(
        makeState(),
        [eff({ type: EffectType.GAIN_ACTION, value: 1 })],
        'p1',
      );
      // makeState: actionsRemaining 1 → +1 = 2
      expect(res.state.metadata.actionsRemaining).toBe(2);
    });

    it('executeChosenEffects: вложенный MOVE порождает pendingEffect', async () => {
      const res = await service.executeChosenEffects(
        makeState(),
        [eff({ type: EffectType.MOVE, value: 2, text: 'Move your fighter up to 2 spaces.' })],
        'p1',
      );
      const pending = res.state.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({ type: 'MOVE', playerId: 'p1', value: 2 });
    });
  });

  // P2-2 (корректировка): ветки, создающие РЕАЛОБЫЧНЫЙ executable pending
  // (CHOOSE_ONE с опциями, фолбэк MOVE/PLACE, RETURN_DEFEATED), не должны
  // попадать в manualEffects аудита как «неисполненные». Manual — только
  // UNSUPPORTED-семантика (нет опций / нераспознанный текст).
  describe('легитимные pending ≠ manualEffects (аудит P2-2)', () => {
    it('CHOOSE_ONE: резолв опции (путь production resolveChooseOne) применяет эффект — manualEffects пуст', async () => {
      const choose = eff({
        type: EffectType.CHOOSE_ONE,
        chooseCount: 1,
        text: 'Choose one',
        options: [
          { label: 'Draw 1 card', effects: [eff({ type: EffectType.DRAW_CARD, value: 1 })] },
        ],
      });
      const after = await service.executeAfterCombatEffects(
        makeState(),
        card('atk', [choose]),
        null,
        combat,
        { attackerWon: true, attackerDamage: 0, defenderDamage: 1 },
      );
      const pending = (after.state.metadata.pendingEffects ?? [])[0];
      expect(pending?.type).toBe('CHOOSE_ONE');
      // резолв: ровно то, что делает resolveChooseOne в game-action-executor
      const chosen = await service.executeChosenEffects(
        { ...after.state, metadata: { ...after.state.metadata, pendingEffects: [] } },
        pending.optionEffects![0],
        'p1',
        pending.card,
        pending.effectContext,
      );
      expect(chosen.state.handZones.p1.cards).toHaveLength(1); // «Draw 1 card»
      expect(chosen.state.metadata.pendingEffects ?? []).toHaveLength(0);
      expect(chosen.manualEffects).toEqual([]);
    });

    it('RETURN_DEFEATED → optional PLACE-pending (revive), аудит manualEffects пуст', async () => {
      const defeated = {
        id: 'f1b', ownerId: 'p1', heroId: 'h1', name: 'Harpy', type: FighterType.MINION,
        health: 0, maxHealth: 1, isDefeated: true, position: { x: 0, y: 1 }, effects: [], hasSidekick: false,
      };
      const state = makeState({ fighters: [...makeState().fighters, defeated] });
      const atk = card('atk', [
        eff({
          type: EffectType.RETURN_DEFEATED,
          fighterName: 'Harpy',
          zoneFighterName: 'Hero One',
          text: "Then, return a defeated Harpy (if any) to any space in Medusa's zone",
        }),
      ]);
      const after = await service.executeAfterCombatEffects(state, atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      const pending = after.state.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({
        type: 'PLACE', playerId: 'p1', fighterIds: ['f1b'],
        zoneFighterName: 'Hero One', restoreFullHealth: true, optional: true,
      });
      expect(after.manualEffects).toEqual([]);
      // боец не тронут до легитимного резолва (резолв — s05-medusa GD-020)
      expect(after.state.fighters.find((f) => f.id === 'f1b')!.isDefeated).toBe(true);
    });

    it('RETURN_DEFEATED: нет поверженных («if any») → skip без pending и без manual', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.RETURN_DEFEATED, fighterName: 'Harpy', text: 'Return a defeated Harpy' }),
      ]);
      const after = await service.executeAfterCombatEffects(makeState(), atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(after.state.metadata.pendingEffects ?? []).toHaveLength(0);
      expect(after.manualEffects).toEqual([]);
    });
  });
});
