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
    it('Feint атакующего отменяет карту защитника; защитник не отменяет в ответ', async () => {
      const atk = card('atk', [
        eff({ type: EffectType.CANCEL_EFFECTS, timing: EffectTiming.ON_REVEAL }),
      ]);
      const def = card('def', [
        eff({ type: EffectType.CANCEL_EFFECTS, timing: EffectTiming.ON_REVEAL }),
      ], { cardType: CardType.DEFENSE });
      const reveal = await service.executeRevealEffects(makeState(), atk, def, combat);
      expect(reveal.defenderCardCancelled).toBe(true);
      expect(reveal.attackerCardCancelled).toBe(false);
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

    it('OPPONENT_DISCARD сбрасывает случайную карту оппонента', async () => {
      const atk = card('atk', [eff({ type: EffectType.OPPONENT_DISCARD, value: 1 })]);
      const after = await service.executeAfterCombatEffects(makeState(), atk, null, combat, {
        attackerWon: true, attackerDamage: 0, defenderDamage: 1,
      });
      expect(after.state.handZones.p2.cards).toHaveLength(0);
      expect(after.state.discardPiles.p2).toHaveLength(1);
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
      expect(after.manualEffects).toEqual([
        'Move your fighter up to 3 spaces.',
        'Something weird.',
      ]);
      const pending = after.state.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({ type: 'MOVE', playerId: 'p1', value: 3 });
      expect(after.state.fighters).toEqual(state.fighters);
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
    it('исполняет AFTER_COMBAT-тексты scheme-карты и собирает manualEffects', async () => {
      const scheme = card('sch', [
        eff({ type: EffectType.DRAW_CARD, value: 1 }),
        eff({ type: EffectType.MOVE, value: 4, text: 'Move Daredevil up to 4 spaces.' }),
      ], { cardType: CardType.SCHEME });
      const result = await service.executeOnPlayEffects(makeState(), scheme, 'p1');
      expect(result.state.handZones.p1.cards).toHaveLength(1);
      expect(result.manualEffects).toEqual(['Move Daredevil up to 4 spaces.']);
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
      // эффект отложен — текст в manualEffects, бойцы не изменены
      expect(after.manualEffects).toContain('Choose one');
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
});
