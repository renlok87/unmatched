/**
 * GenericHeroAbilityHandler — unit-тесты в изоляции.
 *
 * Проверяем интерпретатор декларативных AbilityConfig против вручную
 * собранного GameState и stub DeckManagementService:
 *  - combat-modifier с условием (срабатывает / no-op при ложном условии),
 *  - turn-start gainAction,
 *  - turn-end drawToHandSize,
 * а также чистый no-op (state без изменений), когда условие не выполнено.
 */

import { GenericHeroAbilityHandler, GenericHeroAbilityDeps } from './generic-hero-ability.handler';
import { AbilityConfig } from './ability-config';
import { ValueModifierType, CombatState, AfterCombatContext } from './hero-ability-registry';
import { GameState, GamePhase, getActionsRemaining } from '../models/game-state.model';
import { Fighter, FighterType } from '../models/fighter.model';

/** Минимальный stub DeckManagementService.drawCards: кладёт N карт в руку. */
function makeDeckStub() {
  return {
    drawCards: jest.fn(
      async (state: GameState, userId: string, count: number): Promise<GameState> => {
        const hand = state.handZones[userId];
        const drawn = Array.from({ length: count }, (_, i) => ({
          id: `drawn-${userId}-${hand.cards.length + i}`,
          isVisible: true,
        }));
        return {
          ...state,
          handZones: {
            ...state.handZones,
            [userId]: {
              ...hand,
              cards: [...hand.cards, ...(drawn as any)],
            },
          },
        };
      },
    ),
  };
}

/** Stub зон: по умолчанию НИКТО не в одной зоне (no-enemy → true). */
function makeZoneStub(sameZone = false) {
  return {
    isInSameZone: jest.fn(() => sameZone),
  };
}

function makeDeps(overrides?: Partial<GenericHeroAbilityDeps>): GenericHeroAbilityDeps {
  return {
    deck: makeDeckStub(),
    zone: makeZoneStub(),
    ...overrides,
  };
}

function heroFighter(overrides?: Partial<Fighter>): Fighter {
  return {
    id: 'hero-fighter-1',
    ownerId: 'player1',
    heroId: 'cuid-1',
    heroSlug: 'test-hero',
    name: 'Test Hero',
    type: FighterType.HERO,
    health: 10,
    maxHealth: 18,
    position: { x: 1, y: 1 },
    effects: [],
    hasSidekick: false,
    ...overrides,
  };
}

function enemyFighter(overrides?: Partial<Fighter>): Fighter {
  return {
    id: 'enemy-fighter-1',
    ownerId: 'player2',
    heroId: 'cuid-2',
    heroSlug: 'enemy-hero',
    name: 'Enemy Hero',
    type: FighterType.HERO,
    health: 12,
    maxHealth: 18,
    position: { x: 9, y: 9 },
    effects: [],
    hasSidekick: false,
    ...overrides,
  };
}

function makeState(overrides?: Partial<GameState>): GameState {
  return {
    gameId: 'g1',
    sequenceNumber: 1,
    phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1,
    currentTurnPlayerId: 'player1',
    players: [
      {
        userId: 'player1',
        heroId: 'cuid-1',
        health: 10,
        maxHealth: 18,
        fighterIds: ['hero-fighter-1'],
        isAlive: true,
      },
      {
        userId: 'player2',
        heroId: 'cuid-2',
        health: 12,
        maxHealth: 18,
        fighterIds: ['enemy-fighter-1'],
        isAlive: true,
      },
    ],
    fighters: [heroFighter(), enemyFighter()],
    decks: {} as any,
    discardPiles: {} as any,
    handZones: {
      player1: { cards: [], maxSize: 5 },
      player2: { cards: [], maxSize: 5 },
    } as any,
    boardState: { width: 10, height: 10, cells: [] } as any,
    metadata: {
      lastActionAt: new Date(),
      lastActionBy: 'player1',
      version: 1,
      actionsRemaining: 2,
    },
    ...overrides,
  };
}

describe('GenericHeroAbilityHandler', () => {
  // ---- 1) combat-modifier с условием ----
  describe('getStatefulCombatModifiers (conditional combat-modifier)', () => {
    const config: AbilityConfig = {
      heroId: 'test-hero',
      abilityName: 'Underdog',
      description: '+3 к атаке, когда здоровье ниже защитника',
      rules: [
        {
          trigger: 'combat-passive',
          condition: 'self-health-below-defender',
          effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 3 },
        },
      ],
    };

    const combat: CombatState = {
      attackerId: 'hero-fighter-1',
      defenderId: 'enemy-fighter-1',
    };

    it('возвращает ADD +3 для атакующего, когда условие выполнено', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState(); // hero hp 10 < enemy hp 12
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, attacker, 'attacker');

      expect(mods).toHaveLength(1);
      expect(mods[0]).toMatchObject({
        type: ValueModifierType.ADD,
        value: 3,
        ownerId: 'player1',
        source: 'hero-ability:test-hero:Underdog',
      });
      expect(typeof mods[0].timestamp).toBe('number');
    });

    it('no-op: условие не выполнено (здоровье не ниже защитника)', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({
        fighters: [heroFighter({ health: 18 }), enemyFighter({ health: 12 })],
      });
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, attacker, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('no-op: роль не совпадает с appliesTo (attack vs defender)', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState();
      const fighter = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, fighter, 'defender');
      expect(mods).toHaveLength(0);
    });
  });

  // ---- 2) turn-start gainAction ----
  describe('onTurnStart (gainAction)', () => {
    const config: AbilityConfig = {
      heroId: 'test-hero',
      abilityName: 'Momentum',
      description: '+1 действие в начале хода',
      rules: [
        {
          trigger: 'turn-start',
          condition: 'always',
          effect: { kind: 'turn-effect', gainAction: 1 },
        },
      ],
    };

    it('увеличивает actionsRemaining на 1', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({ metadata: { ...makeState().metadata, actionsRemaining: 2 } });

      const next = await handler.onTurnStart(state, 'player1');

      expect(getActionsRemaining(next)).toBe(3);
      expect(getActionsRemaining(state)).toBe(2); // исходный не мутирован
    });
  });

  // ---- 3) turn-end drawToHandSize ----
  describe('onTurnEnd (drawToHandSize)', () => {
    const config: AbilityConfig = {
      heroId: 'test-hero',
      abilityName: 'Refill',
      description: 'добор до 5 карт в конце хода',
      rules: [
        {
          trigger: 'turn-end',
          effect: { kind: 'turn-effect', drawToHandSize: 5 },
        },
      ],
    };

    it('добирает карты до размера руки 5', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState({
        handZones: {
          player1: { cards: [{ id: 'c1', isVisible: true }] as any, maxSize: 5 },
          player2: { cards: [], maxSize: 5 },
        } as any,
      });

      const next = await handler.onTurnEnd(state, 'player1');

      // дефицит = 5 - 1 = 4
      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 4);
      expect(next.handZones['player1'].cards).toHaveLength(5);
    });

    it('no-op: рука уже >= целевого размера (drawCards не вызывается)', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const fullHand = Array.from({ length: 5 }, (_, i) => ({ id: `c${i}`, isVisible: true }));
      const state = makeState({
        handZones: {
          player1: { cards: fullHand as any, maxSize: 5 },
          player2: { cards: [], maxSize: 5 },
        } as any,
      });

      const next = await handler.onTurnEnd(state, 'player1');

      expect(deps.deck.drawCards).not.toHaveBeenCalled();
      expect(next).toBe(state); // полный no-op — тот же объект
    });
  });

  // ---- 4) no-op для несоответствующего триггера ----
  describe('no-op when no rule matches trigger', () => {
    it('onTurnStart с только turn-end правилом не трогает state', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'EndOnly',
        description: 'эффект только в конце хода',
        rules: [
          { trigger: 'turn-end', effect: { kind: 'turn-effect', draw: 1 } },
        ],
      };
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      const next = await handler.onTurnStart(state, 'player1');

      expect(next).toBe(state);
      expect(deps.deck.drawCards).not.toHaveBeenCalled();
    });
  });

  // ---- 5) heal turn-effect ----
  describe('onTurnStart (heal, capped at maxHealth)', () => {
    it('лечит героя, не превышая maxHealth', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Regen',
        description: 'хил 5 в начале хода',
        rules: [{ trigger: 'turn-start', effect: { kind: 'turn-effect', heal: 5 } }],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({
        fighters: [heroFighter({ health: 16, maxHealth: 18 }), enemyFighter()],
      });

      const next = await handler.onTurnStart(state, 'player1');
      const hero = next.fighters.find((f) => f.id === 'hero-fighter-1')!;
      expect(hero.health).toBe(18); // 16 + 5 = 21, capped to 18
    });
  });

  // ---- 6) condition no-enemy-in-own-zone ----
  describe('turn condition no-enemy-in-own-zone', () => {
    const config: AbilityConfig = {
      heroId: 'test-hero',
      abilityName: 'SafeDraw',
      description: 'добор 1, если в зоне нет врагов',
      rules: [
        {
          trigger: 'turn-start',
          condition: 'no-enemy-in-own-zone',
          effect: { kind: 'turn-effect', draw: 1 },
        },
      ],
    };

    it('срабатывает, когда враг НЕ в зоне героя', async () => {
      const deps = makeDeps({ zone: makeZoneStub(false) });
      const handler = new GenericHeroAbilityHandler(config, deps);
      const next = await handler.onTurnStart(makeState(), 'player1');
      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    });

    it('no-op, когда враг в зоне героя', async () => {
      const deps = makeDeps({ zone: makeZoneStub(true) });
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();
      const next = await handler.onTurnStart(state, 'player1');
      expect(deps.deck.drawCards).not.toHaveBeenCalled();
      expect(next).toBe(state);
    });
  });

  // ---- 7) after-attack trigger ----
  describe('onAfterCombat (after-attack trigger)', () => {
    const afterCtx = (won: boolean): AfterCombatContext => ({
      playerId: 'player1',
      attackerFighterId: 'hero-fighter-1',
      defenderFighterId: 'enemy-fighter-1',
      won,
      damageDealt: won ? 2 : 0,
    });

    it('after-attack always draw → добор для атакующего игрока', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Relentless',
        description: 'после атаки всегда добор 1',
        rules: [
          { trigger: 'after-attack', condition: 'always', effect: { kind: 'turn-effect', draw: 1 } },
        ],
      };
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      const next = await handler.onAfterCombat(state, afterCtx(true));

      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
      expect(next.handZones['player1'].cards).toHaveLength(1);
    });

    it("won-combat: срабатывает только когда ctx.won === true", async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Bloodlust',
        description: 'после победы в бою — хил 3',
        rules: [
          { trigger: 'after-attack', condition: 'won-combat', effect: { kind: 'turn-effect', heal: 3 } },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({
        fighters: [heroFighter({ health: 10, maxHealth: 18 }), enemyFighter()],
      });

      const after = await handler.onAfterCombat(state, afterCtx(true));
      expect(after.fighters.find((f) => f.id === 'hero-fighter-1')!.health).toBe(13);
    });

    it('won-combat: no-op когда ctx.won === false', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Bloodlust',
        description: 'после победы в бою — хил 3',
        rules: [
          { trigger: 'after-attack', condition: 'won-combat', effect: { kind: 'turn-effect', heal: 3 } },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({
        fighters: [heroFighter({ health: 10, maxHealth: 18 }), enemyFighter()],
      });

      const after = await handler.onAfterCombat(state, afterCtx(false));
      expect(after).toBe(state); // полный no-op
      expect(after.fighters.find((f) => f.id === 'hero-fighter-1')!.health).toBe(10);
    });

    it('lost-combat: срабатывает только когда ctx.won === false', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Vengeance',
        description: 'после проигрыша в бою — +1 действие',
        rules: [
          { trigger: 'after-attack', condition: 'lost-combat', effect: { kind: 'turn-effect', gainAction: 1 } },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({ metadata: { ...makeState().metadata, actionsRemaining: 2 } });

      const fired = await handler.onAfterCombat(state, afterCtx(false));
      expect(getActionsRemaining(fired)).toBe(3);

      const noop = await handler.onAfterCombat(state, afterCtx(true));
      expect(getActionsRemaining(noop)).toBe(2);
      expect(noop).toBe(state);
    });

    it('no-op: нет after-attack правила (только turn-end)', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'EndOnly',
        description: 'эффект только в конце хода',
        rules: [{ trigger: 'turn-end', effect: { kind: 'turn-effect', draw: 1 } }],
      };
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      const next = await handler.onAfterCombat(state, afterCtx(true));
      expect(next).toBe(state);
      expect(deps.deck.drawCards).not.toHaveBeenCalled();
    });

    it('skip: combat-only условие на after-attack правиле безопасно игнорируется', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Misconfigured',
        description: 'некорректное условие для after-attack',
        rules: [
          { trigger: 'after-attack', condition: 'attacking', effect: { kind: 'turn-effect', draw: 1 } },
        ],
      };
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      const next = await handler.onAfterCombat(state, afterCtx(true));
      expect(next).toBe(state);
      expect(deps.deck.drawCards).not.toHaveBeenCalled();
    });
  });
});
