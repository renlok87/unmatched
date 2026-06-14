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

/** Stub зон: по умолчанию НИКТО не в одной зоне (no-enemy → true).
 * manhattanDistance — реальный расчёт (для 'enemy-adjacent' таргетинга). */
function makeZoneStub(sameZone = false) {
  return {
    isInSameZone: jest.fn(() => sameZone),
    manhattanDistance: jest.fn(
      (a: { x: number; y: number }, b: { x: number; y: number }) =>
        Math.abs(a.x - b.x) + Math.abs(a.y - b.y),
    ),
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

  // ---- 1a) combat-passive: has-not-maneuvered-this-turn ----
  describe('getStatefulCombatModifiers (has-not-maneuvered-this-turn)', () => {
    const config: AbilityConfig = {
      heroId: 'test-hero',
      abilityName: 'FreshAssault',
      description: '+2 к атаке, если в этом ходу ещё не маневрировал',
      rules: [
        {
          trigger: 'combat-passive',
          condition: 'has-not-maneuvered-this-turn',
          effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 2 },
        },
      ],
    };

    const combat: CombatState = {
      attackerId: 'hero-fighter-1',
      defenderId: 'enemy-fighter-1',
    };

    it('срабатывает +2, когда maneuveredThisTurn falsy', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState(); // metadata без maneuveredThisTurn → falsy
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, attacker, 'attacker');

      expect(mods).toHaveLength(1);
      expect(mods[0]).toMatchObject({ type: ValueModifierType.ADD, value: 2, ownerId: 'player1' });
    });

    it('no-op, когда maneuveredThisTurn === true', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({
        metadata: { ...makeState().metadata, maneuveredThisTurn: true },
      });
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, attacker, 'attacker');
      expect(mods).toHaveLength(0);
    });
  });

  // ---- 1b) combat-passive: has-attacked-this-turn ----
  describe('getStatefulCombatModifiers (has-attacked-this-turn)', () => {
    const config: AbilityConfig = {
      heroId: 'test-hero',
      abilityName: 'Momentum',
      description: '+3 к атаке, если в этом ходу уже атаковал',
      rules: [
        {
          trigger: 'combat-passive',
          condition: 'has-attacked-this-turn',
          effect: { kind: 'combat-modifier', appliesTo: 'attack', value: 3 },
        },
      ],
    };

    const combat: CombatState = {
      attackerId: 'hero-fighter-1',
      defenderId: 'enemy-fighter-1',
    };

    it('срабатывает +3, когда attackedThisTurn === true', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState({
        metadata: { ...makeState().metadata, attackedThisTurn: true },
      });
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, attacker, 'attacker');

      expect(mods).toHaveLength(1);
      expect(mods[0]).toMatchObject({ type: ValueModifierType.ADD, value: 3, ownerId: 'player1' });
    });

    it('no-op, когда attackedThisTurn falsy', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState(); // metadata без attackedThisTurn → falsy
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, attacker, 'attacker');
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
      // первый проигрыш хода (для проигранных боёв); при won — всегда false
      firstLossThisTurn: !won,
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

    it('first-lost-combat-this-turn: gainAction только при won===false && firstLossThisTurn', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'SecondWind',
        description: 'при ПЕРВОМ проигрыше хода — +1 действие',
        rules: [
          {
            trigger: 'after-attack',
            condition: 'first-lost-combat-this-turn',
            effect: { kind: 'turn-effect', gainAction: 1 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const baseMeta = () => makeState().metadata;

      // 1) won===false && firstLossThisTurn===true → срабатывает
      const stateA = makeState({ metadata: { ...baseMeta(), actionsRemaining: 2 } });
      const firedA = await handler.onAfterCombat(stateA, {
        playerId: 'player1',
        attackerFighterId: 'hero-fighter-1',
        defenderFighterId: 'enemy-fighter-1',
        won: false,
        damageDealt: 0,
        firstLossThisTurn: true,
      });
      expect(getActionsRemaining(firedA)).toBe(3);

      // 2) won===false но НЕ первый проигрыш → no-op
      const stateB = makeState({ metadata: { ...baseMeta(), actionsRemaining: 2 } });
      const noopB = await handler.onAfterCombat(stateB, {
        playerId: 'player1',
        attackerFighterId: 'hero-fighter-1',
        defenderFighterId: 'enemy-fighter-1',
        won: false,
        damageDealt: 0,
        firstLossThisTurn: false,
      });
      expect(getActionsRemaining(noopB)).toBe(2);
      expect(noopB).toBe(stateB);

      // 3) won===true (firstLossThisTurn неактуально) → no-op
      const stateC = makeState({ metadata: { ...baseMeta(), actionsRemaining: 2 } });
      const noopC = await handler.onAfterCombat(stateC, {
        playerId: 'player1',
        attackerFighterId: 'hero-fighter-1',
        defenderFighterId: 'enemy-fighter-1',
        won: true,
        damageDealt: 2,
        firstLossThisTurn: false,
      });
      expect(getActionsRemaining(noopC)).toBe(2);
      expect(noopC).toBe(stateC);
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

  // ---- 8) after-defense trigger (defender-side, напр. Spider-Sense) ----
  describe('onAfterCombat (after-defense trigger)', () => {
    // Spider-Man — защитник player1, атакует player2. Эффект → defenderPlayerId.
    const defenseCtx = (won: boolean): AfterCombatContext => ({
      playerId: 'player2', // атакующий
      defenderPlayerId: 'player1', // защитник (Spider-Man) — цель эффекта
      attackerFighterId: 'enemy-fighter-1',
      defenderFighterId: 'hero-fighter-1',
      won,
      damageDealt: won ? 2 : 0,
      firstLossThisTurn: !won,
    });

    // Атакующая-сторона ctx БЕЗ defenderPlayerId — для проверки no-op.
    const attackerOnlyCtx = (won: boolean): AfterCombatContext => ({
      playerId: 'player1',
      attackerFighterId: 'hero-fighter-1',
      defenderFighterId: 'enemy-fighter-1',
      won,
      damageDealt: won ? 2 : 0,
      firstLossThisTurn: !won,
    });

    const config: AbilityConfig = {
      heroId: 'test-hero',
      abilityName: 'SpiderSenseLike',
      description: 'после боя в защите — добор 1 карты',
      rules: [
        { trigger: 'after-defense', condition: 'always', effect: { kind: 'turn-effect', draw: 1 } },
      ],
    };

    it('добор уходит ЗАЩИТНИКУ (ctx.defenderPlayerId), а не атакующему', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      const next = await handler.onAfterCombat(state, defenseCtx(true));

      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
      expect(next.handZones['player1'].cards).toHaveLength(1);
      expect(next.handZones['player2'].cards).toHaveLength(0);
    });

    it('срабатывает независимо от исхода боя (condition always, won===false)', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      const next = await handler.onAfterCombat(state, defenseCtx(false));

      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
      expect(next.handZones['player1'].cards).toHaveLength(1);
    });

    it('no-op: after-defense правило, но ctx без defenderPlayerId → нечего применять', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      // attackerOnlyCtx (атакующая-сторона) не несёт defenderPlayerId
      const next = await handler.onAfterCombat(state, attackerOnlyCtx(true));

      expect(deps.deck.drawCards).not.toHaveBeenCalled();
      expect(next).toBe(state);
    });

    it("no-op: 'after-attack' правило НЕ срабатывает от defender-side диспетчера на defenderPlayerId", async () => {
      // Конфиг с after-attack: эффект уходит атакующему (ctx.playerId), не защитнику.
      const attackConfig: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'AttackerSide',
        description: 'after-attack draw',
        rules: [
          { trigger: 'after-attack', condition: 'always', effect: { kind: 'turn-effect', draw: 1 } },
        ],
      };
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(attackConfig, deps);
      const state = makeState();

      // Даже при наличии defenderPlayerId, after-attack таргетит ctx.playerId
      const next = await handler.onAfterCombat(state, defenseCtx(true));

      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player2', 1);
      expect(next.handZones['player2'].cards).toHaveLength(1);
      expect(next.handZones['player1'].cards).toHaveLength(0);
    });
  });

  // ---- 9) pending-move effect (spawns MOVE PendingEffect via C2 flow) ----
  describe('pending-move effect', () => {
    const afterCtx = (won: boolean): AfterCombatContext => ({
      playerId: 'player1',
      attackerFighterId: 'hero-fighter-1',
      defenderFighterId: 'enemy-fighter-1',
      won,
      damageDealt: won ? 2 : 0,
      firstLossThisTurn: !won,
    });

    // (a) after-attack pending-move 'attacker' → MOVE pending для атакующего бойца
    it("after-attack 'attacker' добавляет MOVE pending с именем атакующего бойца", async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Reposition',
        description: 'после атаки можно сдвинуть атаковавшего бойца',
        rules: [
          {
            trigger: 'after-attack',
            condition: 'always',
            effect: { kind: 'pending-move', target: 'attacker', maxSpaces: 1 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState();

      const next = await handler.onAfterCombat(state, afterCtx(true));

      const pending = next.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({
        type: 'MOVE',
        playerId: 'player1',
        value: 1,
        fighterName: 'Test Hero', // имя бойца из ctx.attackerFighterId
        targetsOpponent: false,
      });
      expect(pending[0].id).toBe('ability-test-hero-move-p0');
      // sequenceNumber НЕ меняется (pendingEffects никогда не бампят seq)
      expect(next.sequenceNumber).toBe(state.sequenceNumber);
      // исходный state не мутирован
      expect(state.metadata.pendingEffects).toBeUndefined();
    });

    // (b) turn-start pending-move 'any-own' → MOVE pending БЕЗ fighterName
    it("turn-start 'any-own' добавляет MOVE pending без fighterName", async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Mobilize',
        description: 'в начале хода можно сдвинуть любого своего бойца',
        rules: [
          {
            trigger: 'turn-start',
            condition: 'always',
            effect: { kind: 'pending-move', target: 'any-own', maxSpaces: 2 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState();

      const next = await handler.onTurnStart(state, 'player1');

      const pending = next.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({
        type: 'MOVE',
        playerId: 'player1',
        value: 2,
        targetsOpponent: false,
      });
      expect(pending[0].fighterName).toBeUndefined(); // any own fighter
      expect(pending[0].id).toBe('ability-test-hero-move-p0');
    });

    // turn-end pending-move 'own-hero' → MOVE pending с именем HERO-бойца
    it("turn-end 'own-hero' добавляет MOVE pending с именем HERO-бойца", async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Retreat',
        description: 'в конце хода можно сдвинуть своего героя',
        rules: [
          {
            trigger: 'turn-end',
            condition: 'always',
            effect: { kind: 'pending-move', target: 'own-hero', maxSpaces: 3 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState();

      const next = await handler.onTurnEnd(state, 'player1');

      const pending = next.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(1);
      expect(pending[0]).toMatchObject({
        type: 'MOVE',
        playerId: 'player1',
        value: 3,
        fighterName: 'Test Hero', // имя HERO-бойца игрока
        targetsOpponent: false,
      });
    });

    // (c) condition gating — after-attack 'won-combat' только при победе
    it("after-attack 'won-combat' pending-move создаётся только при win", async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Pursue',
        description: 'после победы можно сдвинуть атаковавшего бойца',
        rules: [
          {
            trigger: 'after-attack',
            condition: 'won-combat',
            effect: { kind: 'pending-move', target: 'attacker', maxSpaces: 1 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());

      // win → создаётся pending
      const won = await handler.onAfterCombat(makeState(), afterCtx(true));
      expect(won.metadata.pendingEffects ?? []).toHaveLength(1);

      // loss → no-op (тот же state, без pending)
      const lostState = makeState();
      const lost = await handler.onAfterCombat(lostState, afterCtx(false));
      expect(lost).toBe(lostState);
      expect(lost.metadata.pendingEffects).toBeUndefined();
    });

    // 'attacker' target существует только для after-attack — turn-триггер его не создаёт
    it("turn-start 'attacker' target → no-op (имеет смысл лишь для after-attack)", async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Misplaced',
        description: "'attacker' target без after-attack контекста",
        rules: [
          {
            trigger: 'turn-start',
            condition: 'always',
            effect: { kind: 'pending-move', target: 'attacker', maxSpaces: 1 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState();

      const next = await handler.onTurnStart(state, 'player1');
      expect(next).toBe(state);
    });

    // (d) no-op — нет pending-move правила
    it('no-op (=== тот же state), когда нет pending-move правила', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'NoMove',
        description: 'нет pending-move',
        rules: [
          { trigger: 'turn-end', effect: { kind: 'turn-effect', draw: 1 } },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = makeState();

      const nextStart = await handler.onTurnStart(state, 'player1');
      expect(nextStart).toBe(state);

      const nextAfter = await handler.onAfterCombat(state, afterCtx(true));
      expect(nextAfter).toBe(state);
    });

    // несколько pending подряд → корректная индексация id (-p0, -p1)
    it('инкрементирует индекс id pending при нескольких pending-move', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'DoubleMove',
        description: 'два pending-move в начале хода',
        rules: [
          {
            trigger: 'turn-start',
            condition: 'always',
            effect: { kind: 'pending-move', target: 'own-hero', maxSpaces: 1 },
          },
          {
            trigger: 'turn-start',
            condition: 'always',
            effect: { kind: 'pending-move', target: 'any-own', maxSpaces: 2 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const next = await handler.onTurnStart(makeState(), 'player1');

      const pending = next.metadata.pendingEffects ?? [];
      expect(pending).toHaveLength(2);
      expect(pending[0].id).toBe('ability-test-hero-move-p0');
      expect(pending[1].id).toBe('ability-test-hero-move-p1');
    });
  });

  // ---- 10) turn-damage effect (auto-target ping, no pending/UI) ----
  describe('turn-damage effect', () => {
    // (a) enemy-in-zone: наносит N урона врагу В ЗОНЕ героя + thenDraw
    it("enemy-in-zone наносит value урона врагу в зоне + добирает thenDraw", async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Aura of Decay',
        description: 'в начале хода: урон 2 врагу в зоне + добор 1',
        rules: [
          {
            trigger: 'turn-start',
            condition: 'always',
            effect: { kind: 'turn-damage', targetScope: 'enemy-in-zone', value: 2, thenDraw: 1 },
          },
        ],
      };
      // zone-стаб: враг В ЗОНЕ героя (isInSameZone → true)
      const deps = makeDeps({ zone: makeZoneStub(true) });
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState(); // enemy hp 12

      const next = await handler.onTurnStart(state, 'player1');

      const enemy = next.fighters.find((f) => f.id === 'enemy-fighter-1')!;
      expect(enemy.health).toBe(10); // 12 - 2
      expect(enemy.isDefeated).toBeFalsy();
      // thenDraw сработал (попадание было)
      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
      expect(next.handZones['player1'].cards).toHaveLength(1);
      // исходный state не мутирован
      expect(state.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });

    // (b) lethal: health->0 ставит isDefeated + пересчёт isAlive у владельца
    it('летальный урон повергает врага (isDefeated) и пересчитывает isAlive владельца', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Execute',
        description: 'в начале хода: урон 20 врагу в зоне',
        rules: [
          {
            trigger: 'turn-start',
            condition: 'always',
            effect: { kind: 'turn-damage', targetScope: 'enemy-in-zone', value: 20 },
          },
        ],
      };
      const deps = makeDeps({ zone: makeZoneStub(true) });
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState(); // enemy hp 12, единственный боец player2

      const next = await handler.onTurnStart(state, 'player1');

      const enemy = next.fighters.find((f) => f.id === 'enemy-fighter-1')!;
      expect(enemy.health).toBe(0); // max(0, 12 - 20)
      expect(enemy.isDefeated).toBe(true);
      // player2 остался без живых бойцов → isAlive false
      const player2 = next.players.find((p) => p.userId === 'player2')!;
      expect(player2.isAlive).toBe(false);
      // game-over здесь НЕ ставим (WIRE recheck это делает в advanceTurn)
      expect(next.phase).toBe(GamePhase.ACTION_MANEUVER);
      // исходный state не мутирован
      expect(state.fighters.find((f) => f.id === 'enemy-fighter-1')!.isDefeated).toBeFalsy();
      expect(state.players.find((p) => p.userId === 'player2')!.isAlive).toBe(true);
    });

    // (c) enemy-adjacent: бьёт ТОЛЬКО смежного врага
    it('enemy-adjacent бьёт только смежного врага (manhattan === 1)', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Cleave',
        description: 'в конце хода: урон 3 смежному врагу',
        rules: [
          {
            trigger: 'turn-end',
            condition: 'always',
            effect: { kind: 'turn-damage', targetScope: 'enemy-adjacent', value: 3 },
          },
        ],
      };

      // герой на (1,1); смежный враг на (2,1) → distance 1
      const adjacentEnemy = enemyFighter({ id: 'enemy-fighter-1', position: { x: 2, y: 1 } });
      const handlerAdj = new GenericHeroAbilityHandler(config, makeDeps());
      const stateAdj = makeState({ fighters: [heroFighter(), adjacentEnemy] });

      const nextAdj = await handlerAdj.onTurnEnd(stateAdj, 'player1');
      expect(nextAdj.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(9); // 12 - 3

      // дальний враг на (9,9) → distance > 1 → no-op
      const farHandler = new GenericHeroAbilityHandler(config, makeDeps());
      const stateFar = makeState(); // enemy at (9,9)
      const nextFar = await farHandler.onTurnEnd(stateFar, 'player1');
      expect(nextFar).toBe(stateFar);
      expect(nextFar.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });

    // (d) нет подходящей цели → чистый no-op, БЕЗ добора
    it('нет цели в зоне → === тот же state, thenDraw НЕ применяется', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Aura of Decay',
        description: 'урон 2 врагу в зоне + добор 1',
        rules: [
          {
            trigger: 'turn-start',
            condition: 'always',
            effect: { kind: 'turn-damage', targetScope: 'enemy-in-zone', value: 2, thenDraw: 1 },
          },
        ],
      };
      // zone-стаб: никто НЕ в одной зоне (isInSameZone → false)
      const deps = makeDeps({ zone: makeZoneStub(false) });
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState();

      const next = await handler.onTurnStart(state, 'player1');

      expect(next).toBe(state); // чистый no-op
      expect(deps.deck.drawCards).not.toHaveBeenCalled(); // thenDraw НЕ сработал
    });

    // условие гейтит turn-damage (handSizeEquals)
    it('условие гейтит turn-damage: при несовпадении руки — no-op', async () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Conditional Burn',
        description: 'урон 2 врагу в зоне, если в руке ровно 3 карты',
        rules: [
          {
            trigger: 'turn-start',
            condition: { handSizeEquals: 3 },
            effect: { kind: 'turn-damage', targetScope: 'enemy-in-zone', value: 2 },
          },
        ],
      };
      const deps = makeDeps({ zone: makeZoneStub(true) });
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = makeState(); // рука player1 пуста (0 != 3)

      const next = await handler.onTurnStart(state, 'player1');
      expect(next).toBe(state); // условие ложно → no-op
      expect(next.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });
  });

  // ---- 11) canAttackAtRange (declarative passive attack-range) ----
  describe('canAttackAtRange (passive attackRange config field)', () => {
    it('config с attackRange:2 → true для range 1 и 2, false для 3', () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'Reach',
        description: 'может атаковать на расстоянии до 2 клеток',
        attackRange: 2,
        rules: [],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());

      expect(handler.canAttackAtRange('hero-fighter-1', 'enemy-fighter-1', 1)).toBe(true);
      expect(handler.canAttackAtRange('hero-fighter-1', 'enemy-fighter-1', 2)).toBe(true);
      expect(handler.canAttackAtRange('hero-fighter-1', 'enemy-fighter-1', 3)).toBe(false);
    });

    it('config без attackRange → всегда false', () => {
      const config: AbilityConfig = {
        heroId: 'test-hero',
        abilityName: 'NoReach',
        description: 'нет пассивной дальности атаки',
        rules: [],
      };
      const handler = new GenericHeroAbilityHandler(config, makeDeps());

      expect(handler.canAttackAtRange('hero-fighter-1', 'enemy-fighter-1', 1)).toBe(false);
      expect(handler.canAttackAtRange('hero-fighter-1', 'enemy-fighter-1', 2)).toBe(false);
      expect(handler.canAttackAtRange('hero-fighter-1', 'enemy-fighter-1', 0)).toBe(false);
    });
  });

  // ---- 12) combat-modifier-per-count (Raptors-style dynamic modifier) ----
  // +valuePer к атаке/защите за КАЖДОГО другого дружественного бойца,
  // СМЕЖНОГО с защитником боя (countOf = own-fighters-adjacent-to-defender-excl-self).
  describe('getStatefulCombatModifiers (combat-modifier-per-count)', () => {
    const config: AbilityConfig = {
      heroId: 'raptors',
      abilityName: 'Pack Tactics',
      description: '+1 к атаке за каждого другого своего бойца, смежного с защитником',
      rules: [
        {
          trigger: 'combat-passive',
          condition: 'attacking',
          effect: {
            kind: 'combat-modifier-per-count',
            appliesTo: 'attack',
            valuePer: 1,
            countOf: 'own-fighters-adjacent-to-defender-excl-self',
          },
        },
      ],
    };

    // combatInfo: targetFighterId — боец-защитник (на нём считаем смежность).
    const combat: CombatState = {
      attackerId: 'hero-fighter-1',
      defenderId: 'player2',
      targetFighterId: 'enemy-fighter-1',
    };

    // Защитник-боец на (5,5); два СВОИХ бойца player1 смежны с ним; герой-атакующий
    // тоже свой, но он сам исключается из подсчёта (excl-self), даже если смежен.
    function packState(): GameState {
      const defender = enemyFighter({ id: 'enemy-fighter-1', position: { x: 5, y: 5 } });
      const attacker = heroFighter({ id: 'hero-fighter-1', position: { x: 5, y: 6 } }); // смежен, но self
      const ally1 = heroFighter({
        id: 'raptor-1',
        type: FighterType.MINION,
        name: 'Raptor 1',
        position: { x: 4, y: 5 }, // смежен с (5,5)
      });
      const ally2 = heroFighter({
        id: 'raptor-2',
        type: FighterType.MINION,
        name: 'Raptor 2',
        position: { x: 6, y: 5 }, // смежен с (5,5)
      });
      return makeState({ fighters: [attacker, defender, ally1, ally2] });
    }

    it('2 других своих бойца смежны с защитником → +2 (valuePer 1 * count 2)', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = packState();
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, attacker, 'attacker');

      expect(mods).toHaveLength(1);
      expect(mods[0]).toMatchObject({
        type: ValueModifierType.ADD,
        value: 2,
        ownerId: 'player1',
        source: 'hero-ability:raptors:Pack Tactics',
      });
      expect(typeof mods[0].timestamp).toBe('number');
    });

    it('атакующий боец сам НЕ считается (excl-self), даже будучи смежным', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      // только атакующий смежен с защитником, союзников рядом нет
      const defender = enemyFighter({ id: 'enemy-fighter-1', position: { x: 5, y: 5 } });
      const attacker = heroFighter({ id: 'hero-fighter-1', position: { x: 5, y: 6 } }); // смежен (self)
      const state = makeState({ fighters: [attacker, defender] });
      const atk = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, atk, 'attacker');
      expect(mods).toHaveLength(0); // self исключён → count 0 → нет модификатора
    });

    it('0 смежных своих бойцов → нет модификатора', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      // защитник один, союзники далеко (герой на (1,1), защитник на (9,9))
      const state = makeState();
      const atk = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, atk, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('только СВОИ бойцы считаются; вражеские смежные не учитываются', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const defender = enemyFighter({ id: 'enemy-fighter-1', position: { x: 5, y: 5 } });
      const attacker = heroFighter({ id: 'hero-fighter-1', position: { x: 1, y: 1 } });
      const ownAlly = heroFighter({
        id: 'raptor-1',
        type: FighterType.MINION,
        position: { x: 4, y: 5 }, // свой, смежен → считается
      });
      const enemyAlly = enemyFighter({
        id: 'enemy-fighter-2',
        position: { x: 6, y: 5 }, // вражеский, смежен → НЕ считается
      });
      const state = makeState({ fighters: [attacker, defender, ownAlly, enemyAlly] });
      const atk = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, atk, 'attacker');
      expect(mods).toHaveLength(1);
      expect(mods[0].value).toBe(1); // только 1 свой смежный
    });

    it('повергнутые свои бойцы не считаются', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const defender = enemyFighter({ id: 'enemy-fighter-1', position: { x: 5, y: 5 } });
      const attacker = heroFighter({ id: 'hero-fighter-1', position: { x: 1, y: 1 } });
      const liveAlly = heroFighter({
        id: 'raptor-1',
        type: FighterType.MINION,
        position: { x: 4, y: 5 },
      });
      const deadAlly = heroFighter({
        id: 'raptor-2',
        type: FighterType.MINION,
        position: { x: 6, y: 5 },
        isDefeated: true, // повержен → не считается
      });
      const state = makeState({ fighters: [attacker, defender, liveAlly, deadAlly] });
      const atk = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, atk, 'attacker');
      expect(mods).toHaveLength(1);
      expect(mods[0].value).toBe(1); // только живой союзник
    });

    it('appliesTo/role: appliesTo attack не срабатывает для роли defender', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = packState();
      const fighter = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const mods = handler.getStatefulCombatModifiers(state, combat, fighter, 'defender');
      expect(mods).toHaveLength(0);
    });

    it('condition гейтит: attacking при роли defender → no-op даже при appliesTo both', () => {
      const bothConfig: AbilityConfig = {
        heroId: 'raptors',
        abilityName: 'Pack Tactics',
        description: 'both, но условие attacking',
        rules: [
          {
            trigger: 'combat-passive',
            condition: 'attacking',
            effect: {
              kind: 'combat-modifier-per-count',
              appliesTo: 'both',
              valuePer: 1,
              countOf: 'own-fighters-adjacent-to-defender-excl-self',
            },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(bothConfig, makeDeps());
      const state = packState();
      const fighter = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      // appliesTo both пропускает sideMatchesRole, но condition 'attacking' гейтит роль defender
      const mods = handler.getStatefulCombatModifiers(state, combat, fighter, 'defender');
      expect(mods).toHaveLength(0);
    });

    it('защитник-боец не найден (нет targetFighterId/defenderId матча) → no-op', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = packState();
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;
      // combat без targetFighterId, defenderId — id игрока, не бойца → fighter.find не найдёт
      const badCombat: CombatState = { attackerId: 'hero-fighter-1', defenderId: 'player2' };

      const mods = handler.getStatefulCombatModifiers(state, badCombat, attacker, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('фолбэк на defenderId, когда targetFighterId отсутствует, но defenderId — id бойца', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = packState();
      const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;
      // нет targetFighterId, но defenderId напрямую указывает на бойца-защитника
      const combatByFighter: CombatState = {
        attackerId: 'hero-fighter-1',
        defenderId: 'enemy-fighter-1',
      };

      const mods = handler.getStatefulCombatModifiers(state, combatByFighter, attacker, 'attacker');
      expect(mods).toHaveLength(1);
      expect(mods[0].value).toBe(2);
    });
  });

  // ---- 13) getAuraCombatModifiers (aura-combat-modifier) ----
  // Герой-АУРА (Oda-style) баффает ДРУГИХ дружественных бойцов, делящих его
  // зону, во время ИХ боя. Аура исходит ОТ этого handler'а, а beneficiary —
  // отдельный боец (не сам герой-гранитель).
  describe('getAuraCombatModifiers (aura-combat-modifier)', () => {
    const config: AbilityConfig = {
      heroId: 'oda-nobunaga',
      abilityName: 'Banner of the Demon King',
      description: '+1 другим дружественным бойцам в зоне Oda',
      rules: [
        {
          trigger: 'combat-passive',
          condition: 'always',
          effect: {
            kind: 'aura-combat-modifier',
            appliesTo: 'both',
            value: 1,
            scope: 'allies-in-my-zone',
          },
        },
      ],
    };

    // Герой-гранитель ауры (Oda) — HERO-боец player1, heroSlug === config.heroId.
    function granterHero(overrides?: Partial<Fighter>): Fighter {
      return heroFighter({
        id: 'oda-hero',
        ownerId: 'player1',
        heroSlug: 'oda-nobunaga',
        name: 'Oda Nobunaga',
        position: { x: 5, y: 5 },
        ...overrides,
      });
    }

    // Союзный сайдкик player1 — потенциальный beneficiary ауры.
    function allyFighter(overrides?: Partial<Fighter>): Fighter {
      return heroFighter({
        id: 'ally-1',
        ownerId: 'player1',
        type: FighterType.MINION,
        heroSlug: 'some-sidekick',
        name: 'Ashigaru',
        position: { x: 5, y: 6 },
        ...overrides,
      });
    }

    it('грантит +1 союзнику в зоне Oda во время его атаки', () => {
      // zone-стаб: все в одной зоне (isInSameZone → true)
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: makeZoneStub(true) }));
      const ally = allyFighter();
      const state = makeState({ fighters: [granterHero(), ally, enemyFighter()] });

      const mods = handler.getAuraCombatModifiers(state, ally, 'attacker');

      expect(mods).toHaveLength(1);
      expect(mods[0]).toMatchObject({
        type: ValueModifierType.ADD,
        value: 1,
        ownerId: 'player1',
        source: 'hero-ability:oda-nobunaga:Banner of the Demon King',
      });
      expect(typeof mods[0].timestamp).toBe('number');
    });

    it('грантит +1 союзнику в зоне Oda и во время его защиты (appliesTo both)', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: makeZoneStub(true) }));
      const ally = allyFighter();
      const state = makeState({ fighters: [granterHero(), ally, enemyFighter()] });

      const mods = handler.getAuraCombatModifiers(state, ally, 'defender');
      expect(mods).toHaveLength(1);
      expect(mods[0].value).toBe(1);
    });

    it('НЕ баффает самого Oda (гранитель не получает свою ауру)', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: makeZoneStub(true) }));
      const granter = granterHero();
      const state = makeState({ fighters: [granter, allyFighter(), enemyFighter()] });

      // beneficiary === сам герой-гранитель → исключается
      const mods = handler.getAuraCombatModifiers(state, granter, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('НЕ баффает союзника ВНЕ зоны Oda (isInSameZone → false)', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: makeZoneStub(false) }));
      const ally = allyFighter({ position: { x: 1, y: 1 } });
      const state = makeState({ fighters: [granterHero(), ally, enemyFighter()] });

      const mods = handler.getAuraCombatModifiers(state, ally, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('НЕ баффает вражеского бойца (другой ownerId), даже если он в той же зоне', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: makeZoneStub(true) }));
      const enemy = enemyFighter({ id: 'enemy-fighter-1' });
      const state = makeState({ fighters: [granterHero(), allyFighter(), enemy] });

      const mods = handler.getAuraCombatModifiers(state, enemy, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('no-op, когда герой-гранитель повержен (isDefeated)', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: makeZoneStub(true) }));
      const ally = allyFighter();
      const state = makeState({
        fighters: [granterHero({ isDefeated: true }), ally, enemyFighter()],
      });

      const mods = handler.getAuraCombatModifiers(state, ally, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('no-op, когда герой-гранитель отсутствует на доске', () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: makeZoneStub(true) }));
      const ally = allyFighter();
      // нет HERO-бойца с heroSlug oda-nobunaga
      const state = makeState({ fighters: [ally, enemyFighter()] });

      const mods = handler.getAuraCombatModifiers(state, ally, 'attacker');
      expect(mods).toHaveLength(0);
    });

    it('no-op для handler без aura-правил (обычный combat-modifier)', () => {
      const plain: AbilityConfig = {
        heroId: 'luke-cage',
        abilityName: 'Skin Like Titanium',
        description: '+2 защита',
        rules: [
          {
            trigger: 'combat-passive',
            condition: 'always',
            effect: { kind: 'combat-modifier', appliesTo: 'defense', value: 2 },
          },
        ],
      };
      const handler = new GenericHeroAbilityHandler(plain, makeDeps({ zone: makeZoneStub(true) }));
      const ally = allyFighter();
      const state = makeState({ fighters: [granterHero(), ally, enemyFighter()] });

      const mods = handler.getAuraCombatModifiers(state, ally, 'attacker');
      expect(mods).toHaveLength(0);
    });
  });

  // ---- 14) onFighterDefeated (sidekick-defeated → discard-random) ----
  // Когда сайдкик ЭТОГО героя повержен — сбросить N карт из руки владельца.
  describe('onFighterDefeated (sidekick-defeated → discard-random)', () => {
    const config: AbilityConfig = {
      heroId: 'achilles',
      abilityName: 'Grief and Rage',
      description: 'когда сайдкик повержен — сбросить 2 карты',
      rules: [
        {
          trigger: 'sidekick-defeated',
          effect: { kind: 'discard-random', count: 2 },
        },
      ],
    };

    /** State, где у player1 есть HERO (achilles) + сайдкик; рука заданного размера. */
    const stateWithHand = (handCount: number): GameState =>
      makeState({
        fighters: [
          heroFighter({ heroSlug: 'achilles' }),
          heroFighter({
            id: 'sidekick-1',
            ownerId: 'player1',
            type: FighterType.MINION,
            name: 'Patroclus',
            heroSlug: 'patroclus',
            position: { x: 2, y: 2 },
          }),
          enemyFighter(),
        ],
        handZones: {
          player1: {
            cards: Array.from({ length: handCount }, (_, i) => ({ id: `c${i}`, isVisible: true })),
            maxSize: 5,
          },
          player2: { cards: [], maxSize: 5 },
        } as any,
        discardPiles: { player1: [], player2: [] } as any,
      });

    it('сбрасывает 2 карты из руки владельца, когда повержен СВОЙ сайдкик', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = stateWithHand(4);
      const sidekick = state.fighters.find((f) => f.id === 'sidekick-1')!;

      const next = await handler.onFighterDefeated(state, sidekick);

      expect(next.handZones['player1'].cards).toHaveLength(2); // 4 - 2
      // карты ушли в сброс (count добавлен в discardPile)
      expect(next.discardPiles['player1']).toHaveLength(2);
      // исходный state не мутирован
      expect(state.handZones['player1'].cards).toHaveLength(4);
    });

    it('сбрасывает столько, сколько есть, если в руке меньше count', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = stateWithHand(1);
      const sidekick = state.fighters.find((f) => f.id === 'sidekick-1')!;

      const next = await handler.onFighterDefeated(state, sidekick);
      expect(next.handZones['player1'].cards).toHaveLength(0);
      expect(next.discardPiles['player1']).toHaveLength(1);
    });

    it('no-op: повержен ВРАЖЕСКИЙ боец (не наш сайдкик)', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = stateWithHand(4);
      const enemy = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      const next = await handler.onFighterDefeated(state, enemy);
      expect(next).toBe(state); // чистый no-op
      expect(next.handZones['player1'].cards).toHaveLength(4);
    });

    it('no-op: повержен HERO-боец владельца (не сайдкик)', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = stateWithHand(4);
      const hero = state.fighters.find((f) => f.id === 'hero-fighter-1')!;

      const next = await handler.onFighterDefeated(state, hero);
      expect(next).toBe(state);
      expect(next.handZones['player1'].cards).toHaveLength(4);
    });

    it('no-op: handler без sidekick-defeated правила', async () => {
      const plain: AbilityConfig = {
        heroId: 'achilles',
        abilityName: 'NoReact',
        description: 'нет реакции на смерть сайдкика',
        rules: [{ trigger: 'turn-end', effect: { kind: 'turn-effect', draw: 1 } }],
      };
      const handler = new GenericHeroAbilityHandler(plain, makeDeps());
      const state = stateWithHand(4);
      const sidekick = state.fighters.find((f) => f.id === 'sidekick-1')!;

      const next = await handler.onFighterDefeated(state, sidekick);
      expect(next).toBe(state);
    });

    it('no-op: пустая рука → нечего сбрасывать (тот же state)', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps());
      const state = stateWithHand(0);
      const sidekick = state.fighters.find((f) => f.id === 'sidekick-1')!;

      const next = await handler.onFighterDefeated(state, sidekick);
      expect(next).toBe(state);
    });
  });

  // ---- 15) after-attack: won-combat-and-all-sidekicks-defeated ----
  // Эффект срабатывает ТОЛЬКО когда ctx.won === true И все сайдкики
  // действующего героя (ctx.playerId) повержены.
  describe('onAfterCombat (won-combat-and-all-sidekicks-defeated)', () => {
    const config: AbilityConfig = {
      heroId: 'achilles',
      abilityName: 'Avenging Strike',
      description: 'после победы, если все сайдкики повержены — добор 1',
      rules: [
        {
          trigger: 'after-attack',
          condition: 'won-combat-and-all-sidekicks-defeated',
          effect: { kind: 'turn-effect', draw: 1 },
        },
      ],
    };

    const afterCtx = (won: boolean): AfterCombatContext => ({
      playerId: 'player1',
      attackerFighterId: 'hero-fighter-1',
      defenderFighterId: 'enemy-fighter-1',
      won,
      damageDealt: won ? 2 : 0,
      firstLossThisTurn: !won,
    });

    /** State с сайдкиком player1 заданного статуса (defeated?). */
    const stateWithSidekick = (defeated: boolean): GameState =>
      makeState({
        fighters: [
          heroFighter({ heroSlug: 'achilles' }),
          heroFighter({
            id: 'sidekick-1',
            ownerId: 'player1',
            type: FighterType.MINION,
            name: 'Patroclus',
            isDefeated: defeated,
            position: { x: 2, y: 2 },
          }),
          enemyFighter(),
        ],
      });

    it('добор, когда won && все сайдкики повержены', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = stateWithSidekick(true);

      const next = await handler.onAfterCombat(state, afterCtx(true));
      expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
      expect(next.handZones['player1'].cards).toHaveLength(1);
    });

    it('no-op: won, но сайдкик ещё жив', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = stateWithSidekick(false);

      const next = await handler.onAfterCombat(state, afterCtx(true));
      expect(deps.deck.drawCards).not.toHaveBeenCalled();
      expect(next).toBe(state);
    });

    it('no-op: все сайдкики повержены, но бой ПРОИГРАН (won===false)', async () => {
      const deps = makeDeps();
      const handler = new GenericHeroAbilityHandler(config, deps);
      const state = stateWithSidekick(true);

      const next = await handler.onAfterCombat(state, afterCtx(false));
      expect(deps.deck.drawCards).not.toHaveBeenCalled();
      expect(next).toBe(state);
    });
  });

  // ---- 16) onFighterMoved (enemy-hero-left-my-zone → reactive-damage) ----
  // Tomoe-style: когда вражеский ГЕРОЙ покидает зону этого героя — наносит ему
  // value урона. Реактивный кросс-героевый хук: реактор (этот герой) отличен от
  // двигающегося (вражеский герой).
  describe('onFighterMoved (enemy-hero-left-my-zone → reactive-damage)', () => {
    const config: AbilityConfig = {
      heroId: 'tomoe-gozen',
      abilityName: 'Unwavering Resolve',
      description: 'когда вражеский герой покидает зону Tomoe — 1 урон',
      rules: [
        {
          trigger: 'enemy-hero-left-my-zone',
          effect: { kind: 'reactive-damage', value: 1 },
        },
      ],
    };

    /**
     * Zone-стаб с явной картой зон: возвращает true, если ОБЕ точки попадают в
     * одну «зону» по предикату. Здесь зона Tomoe — клетки с x <= 2; всё, что
     * x > 2 — снаружи. Tomoe (реактор) стоит в (1,1) ∈ зоне.
     */
    const zoneByX = () => ({
      isInSameZone: jest.fn(
        (_s: unknown, a: { x: number; y: number }, b: { x: number; y: number }) =>
          a.x <= 2 && b.x <= 2,
      ),
      manhattanDistance: jest.fn(
        (a: { x: number; y: number }, b: { x: number; y: number }) =>
          Math.abs(a.x - b.x) + Math.abs(a.y - b.y),
      ),
    });

    /** State: Tomoe-герой (player1) в (1,1) + вражеский герой (player2). */
    const tomoeState = (enemyOverrides?: Partial<Fighter>): GameState =>
      makeState({
        fighters: [
          heroFighter({ heroSlug: 'tomoe-gozen', position: { x: 1, y: 1 } }),
          enemyFighter({ id: 'enemy-fighter-1', position: { x: 2, y: 1 }, ...enemyOverrides }),
        ],
      });

    it('наносит 1 урон вражескому герою, ПОКИНУВШЕМУ зону Tomoe', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: zoneByX() }));
      const state = tomoeState(); // enemy hp 12 в (2,1) ∈ зоне
      const moved = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      // (2,1) ∈ зоне → (5,1) вне зоны: ПОКИНУЛ
      const next = await handler.onFighterMoved(state, moved, { x: 2, y: 1 }, { x: 5, y: 1 });

      expect(next.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(11); // 12 - 1
      // исходный state не мутирован
      expect(state.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });

    it('no-op: враг ОСТАЛСЯ в зоне Tomoe (from в зоне И to в зоне)', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: zoneByX() }));
      const state = tomoeState();
      const moved = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      // (2,1) ∈ зоне → (1,2) тоже ∈ зоне (x<=2): не покидал
      const next = await handler.onFighterMoved(state, moved, { x: 2, y: 1 }, { x: 1, y: 2 });

      expect(next).toBe(state); // чистый no-op
      expect(next.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });

    it('no-op: враг ВОШЁЛ в зону (from вне зоны → to в зоне), а не покинул', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: zoneByX() }));
      const state = tomoeState({ position: { x: 5, y: 1 } });
      const moved = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      // (5,1) вне зоны → (2,1) ∈ зоне: вошёл, не покинул
      const next = await handler.onFighterMoved(state, moved, { x: 5, y: 1 }, { x: 2, y: 1 });

      expect(next).toBe(state);
      expect(next.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });

    it('no-op: сдвинувшийся боец — вражеский САЙДКИК (не HERO)', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: zoneByX() }));
      const state = makeState({
        fighters: [
          heroFighter({ heroSlug: 'tomoe-gozen', position: { x: 1, y: 1 } }),
          enemyFighter({
            id: 'enemy-fighter-1',
            type: FighterType.MINION,
            position: { x: 2, y: 1 },
          }),
        ],
      });
      const moved = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      // покидает зону, но это сайдкик — реакции нет (триггер только на opposing HERO)
      const next = await handler.onFighterMoved(state, moved, { x: 2, y: 1 }, { x: 5, y: 1 });

      expect(next).toBe(state);
      expect(next.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });

    it('no-op: сдвинувшийся боец — СВОЙ герой (тот же владелец, что и Tomoe)', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: zoneByX() }));
      // свой второй HERO player1 покидает зону Tomoe — реакции нет (не вражеский)
      const state = makeState({
        fighters: [
          heroFighter({ id: 'hero-fighter-1', heroSlug: 'tomoe-gozen', position: { x: 1, y: 1 } }),
          heroFighter({
            id: 'own-hero-2',
            ownerId: 'player1',
            heroSlug: 'some-ally-hero',
            name: 'Ally Hero',
            health: 12,
            position: { x: 2, y: 1 },
          }),
        ],
      });
      const moved = state.fighters.find((f) => f.id === 'own-hero-2')!;

      const next = await handler.onFighterMoved(state, moved, { x: 2, y: 1 }, { x: 5, y: 1 });

      expect(next).toBe(state);
      expect(next.fighters.find((f) => f.id === 'own-hero-2')!.health).toBe(12);
    });

    it('no-op: герой-реактор (Tomoe) повержен', async () => {
      const handler = new GenericHeroAbilityHandler(config, makeDeps({ zone: zoneByX() }));
      const state = makeState({
        fighters: [
          heroFighter({ heroSlug: 'tomoe-gozen', position: { x: 1, y: 1 }, isDefeated: true }),
          enemyFighter({ id: 'enemy-fighter-1', position: { x: 2, y: 1 } }),
        ],
      });
      const moved = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      const next = await handler.onFighterMoved(state, moved, { x: 2, y: 1 }, { x: 5, y: 1 });

      expect(next).toBe(state);
      expect(next.fighters.find((f) => f.id === 'enemy-fighter-1')!.health).toBe(12);
    });

    it('летальный реактивный урон: health→0 ставит isDefeated + пересчёт isAlive владельца', async () => {
      const config1: AbilityConfig = {
        heroId: 'tomoe-gozen',
        abilityName: 'Unwavering Resolve',
        description: 'урон 1 покинувшему зону врагу',
        rules: [{ trigger: 'enemy-hero-left-my-zone', effect: { kind: 'reactive-damage', value: 1 } }],
      };
      const handler = new GenericHeroAbilityHandler(config1, makeDeps({ zone: zoneByX() }));
      // вражеский герой с 1 hp — единственный боец player2
      const state = tomoeState({ health: 1 });
      const moved = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      const next = await handler.onFighterMoved(state, moved, { x: 2, y: 1 }, { x: 5, y: 1 });

      const enemy = next.fighters.find((f) => f.id === 'enemy-fighter-1')!;
      expect(enemy.health).toBe(0);
      expect(enemy.isDefeated).toBe(true);
      // player2 без живых бойцов → isAlive false
      expect(next.players.find((p) => p.userId === 'player2')!.isAlive).toBe(false);
      // game-over НЕ ставим (WIRE recheck это делает)
      expect(next.phase).toBe(GamePhase.ACTION_MANEUVER);
    });

    it('no-op: handler без enemy-hero-left-my-zone правила (другой триггер)', async () => {
      const plain: AbilityConfig = {
        heroId: 'tomoe-gozen',
        abilityName: 'NoReact',
        description: 'нет on-move реакции',
        rules: [{ trigger: 'turn-end', effect: { kind: 'turn-effect', draw: 1 } }],
      };
      const handler = new GenericHeroAbilityHandler(plain, makeDeps({ zone: zoneByX() }));
      const state = tomoeState();
      const moved = state.fighters.find((f) => f.id === 'enemy-fighter-1')!;

      const next = await handler.onFighterMoved(state, moved, { x: 2, y: 1 }, { x: 5, y: 1 });
      expect(next).toBe(state);
    });
  });
});
