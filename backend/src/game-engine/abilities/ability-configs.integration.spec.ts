/**
 * ABILITY_CONFIGS — интеграционные тесты конкретных героев.
 *
 * Для КАЖДОГО зашитого в ABILITY_CONFIGS героя берём его РЕАЛЬНУЮ декларацию
 * (по слагу), строим из неё GenericHeroAbilityHandler с реальными deps-стабами
 * и проверяем, что способность действительно производит ожидаемый эффект против
 * минимального GameState. Это прогон конкретных конфигов через настоящий
 * интерпретатор (не моки логики) + проверка реального пути регистрации в
 * HeroAbilityRegistry.
 *
 * Слаги героев подтверждены через slugifyHeroName(displayName):
 *  'Luke Cage'→luke-cage, 'Annie Christmas'→annie-christmas, 'Eredin'→eredin,
 *  'Bloody Mary'→bloody-mary, 'Philippa'→philippa, 'T. Rex'→t-rex,
 *  'Bigfoot'→bigfoot — ровно так heroSlug проставляется на game-init.
 */

import { GenericHeroAbilityHandler, GenericHeroAbilityDeps } from './generic-hero-ability.handler';
import { ABILITY_CONFIGS, AbilityConfig } from './ability-config';
import {
  HeroAbilityRegistry,
  ValueModifierType,
  CombatState,
  AfterCombatContext,
} from './hero-ability-registry';
import { GameState, GamePhase, getActionsRemaining } from '../models/game-state.model';
import { Fighter, FighterType } from '../models/fighter.model';

// ===================== ТЕСТОВЫЕ ХЕЛПЕРЫ =====================

/** Реальная декларация героя из ABILITY_CONFIGS по слагу (или undefined). */
function configFor(slug: string): AbilityConfig | undefined {
  return ABILITY_CONFIGS.find((c) => c.heroId === slug);
}

/** drawCards-стаб: кладёт N помеченных карт в руку игрока. */
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
            [userId]: { ...hand, cards: [...hand.cards, ...(drawn as any)] },
          },
        };
      },
    ),
  };
}

/** zone-стаб: настраиваемый ответ isInSameZone. */
function makeZoneStub(sameZone = false) {
  return { isInSameZone: jest.fn(() => sameZone) };
}

function makeDeps(overrides?: Partial<GenericHeroAbilityDeps>): GenericHeroAbilityDeps {
  return { deck: makeDeckStub(), zone: makeZoneStub(), ...overrides };
}

/** Построить handler из РЕАЛЬНОГО конфига героя; падает, если конфиг не найден. */
function handlerFor(slug: string, deps?: GenericHeroAbilityDeps): GenericHeroAbilityHandler {
  const config = configFor(slug);
  if (!config) {
    throw new Error(`ABILITY_CONFIGS не содержит героя '${slug}'`);
  }
  return new GenericHeroAbilityHandler(config, deps ?? makeDeps());
}

function makeFighter(overrides?: Partial<Fighter>): Fighter {
  return {
    id: 'hero-fighter-1',
    ownerId: 'player1',
    heroId: 'cuid-1',
    heroSlug: 'test-hero',
    name: 'Hero',
    type: FighterType.HERO,
    health: 10,
    maxHealth: 18,
    position: { x: 1, y: 1 },
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
      { userId: 'player1', heroId: 'cuid-1', health: 10, maxHealth: 18, fighterIds: ['hero-fighter-1'], isAlive: true },
      { userId: 'player2', heroId: 'cuid-2', health: 12, maxHealth: 18, fighterIds: ['enemy-fighter-1'], isAlive: true },
    ],
    fighters: [
      makeFighter(),
      makeFighter({
        id: 'enemy-fighter-1',
        ownerId: 'player2',
        heroId: 'cuid-2',
        heroSlug: 'enemy-hero',
        name: 'Enemy',
        health: 12,
        position: { x: 9, y: 9 },
      }),
    ],
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

/** Хелпер: рука player1 заданного размера. */
function handOf(n: number): any {
  return {
    player1: { cards: Array.from({ length: n }, (_, i) => ({ id: `c${i}`, isVisible: true })), maxSize: 5 },
    player2: { cards: [], maxSize: 5 },
  };
}

const COMBAT: CombatState = { attackerId: 'hero-fighter-1', defenderId: 'enemy-fighter-1' };

// ===================== СЛАГИ ПОПАЛИ В РЕЕСТР =====================

describe('ABILITY_CONFIGS — присутствие героев', () => {
  const expected = [
    'luke-cage',
    'annie-christmas',
    'eredin',
    'bloody-mary',
    'philippa',
    't-rex',
    'bigfoot',
    'chupacabra',
    'deadpool',
    'michelangelo',
    'angel',
    'golden-bat',
    'ancient-leshen',
    'raphael',
    'robin-hood',
    'leonardo',
  ];
  it.each(expected)('содержит конфиг для слага %s', (slug) => {
    expect(configFor(slug)).toBeDefined();
  });

  it('реальная регистрация в HeroAbilityRegistry проходит для всех конфигов', () => {
    const registry = new HeroAbilityRegistry();
    const deps = makeDeps();
    for (const config of ABILITY_CONFIGS) {
      registry.registerExtended(new GenericHeroAbilityHandler(config, deps));
    }
    for (const slug of expected) {
      expect(registry.getExtended(slug)).toBeDefined();
    }
  });
});

// ===================== COMBAT-PASSIVE =====================

describe('luke-cage (combat-passive: always +2 defense)', () => {
  it('защитник получает +2 ADD к защите', () => {
    const handler = handlerFor('luke-cage');
    const defender = makeFighter({ heroSlug: 'luke-cage' });
    const mods = handler.getStatefulCombatModifiers(makeState(), COMBAT, defender, 'defender');

    expect(mods).toHaveLength(1);
    expect(mods[0]).toMatchObject({ type: ValueModifierType.ADD, value: 2, ownerId: 'player1' });
  });

  it('атакующий НЕ получает модификатор (appliesTo: defense)', () => {
    const handler = handlerFor('luke-cage');
    const attacker = makeFighter({ heroSlug: 'luke-cage' });
    const mods = handler.getStatefulCombatModifiers(makeState(), COMBAT, attacker, 'attacker');
    expect(mods).toHaveLength(0);
  });
});

describe('annie-christmas (combat-passive: +2 attack when self-health < defender)', () => {
  it('даёт +2 к атаке, когда здоровье ниже защитника', () => {
    const handler = handlerFor('annie-christmas');
    // hero hp 10 < enemy hp 12
    const attacker = makeState().fighters.find((f) => f.id === 'hero-fighter-1')!;
    const mods = handler.getStatefulCombatModifiers(makeState(), COMBAT, attacker, 'attacker');

    expect(mods).toHaveLength(1);
    expect(mods[0]).toMatchObject({ type: ValueModifierType.ADD, value: 2 });
  });

  it('no-op: здоровье НЕ ниже защитника', () => {
    const handler = handlerFor('annie-christmas');
    const state = makeState({
      fighters: [
        makeFighter({ health: 18 }),
        makeFighter({ id: 'enemy-fighter-1', ownerId: 'player2', health: 12, position: { x: 9, y: 9 } }),
      ],
    });
    const attacker = state.fighters.find((f) => f.id === 'hero-fighter-1')!;
    const mods = handler.getStatefulCombatModifiers(state, COMBAT, attacker, 'attacker');
    expect(mods).toHaveLength(0);
  });
});

describe('eredin (combat-passive: +1 both when all own sidekicks defeated)', () => {
  /** State, где у player1 есть один НЕ-герой (sidekick) с заданным статусом. */
  const stateWithSidekick = (defeated: boolean): GameState =>
    makeState({
      fighters: [
        makeFighter({ heroSlug: 'eredin' }),
        makeFighter({
          id: 'sk-1',
          ownerId: 'player1',
          type: FighterType.MINION,
          name: 'Red Rider',
          isDefeated: defeated,
        }),
        makeFighter({ id: 'enemy-fighter-1', ownerId: 'player2', health: 12, position: { x: 9, y: 9 } }),
      ],
    });

  it('атакующий +1, когда все сайдкики повержены', () => {
    const handler = handlerFor('eredin');
    const state = stateWithSidekick(true);
    const hero = state.fighters.find((f) => f.id === 'hero-fighter-1')!;
    const mods = handler.getStatefulCombatModifiers(state, COMBAT, hero, 'attacker');
    expect(mods).toHaveLength(1);
    expect(mods[0]).toMatchObject({ type: ValueModifierType.ADD, value: 1 });
  });

  it('защитник тоже +1 (appliesTo: both), когда сайдкики повержены', () => {
    const handler = handlerFor('eredin');
    const state = stateWithSidekick(true);
    const hero = state.fighters.find((f) => f.id === 'hero-fighter-1')!;
    const mods = handler.getStatefulCombatModifiers(state, COMBAT, hero, 'defender');
    expect(mods).toHaveLength(1);
    expect(mods[0]).toMatchObject({ value: 1 });
  });

  it('no-op: сайдкик ещё жив', () => {
    const handler = handlerFor('eredin');
    const state = stateWithSidekick(false);
    const hero = state.fighters.find((f) => f.id === 'hero-fighter-1')!;
    const mods = handler.getStatefulCombatModifiers(state, COMBAT, hero, 'attacker');
    expect(mods).toHaveLength(0);
  });
});

// ===================== TURN-START =====================

describe('bloody-mary (turn-start: gainAction +1 when hand size == 3)', () => {
  it('+1 действие, когда в руке ровно 3 карты', async () => {
    const handler = handlerFor('bloody-mary');
    const state = makeState({
      handZones: handOf(3) as any,
      metadata: { ...makeState().metadata, actionsRemaining: 2 },
    });
    const next = await handler.onTurnStart(state, 'player1');
    expect(getActionsRemaining(next)).toBe(3);
  });

  it('no-op: в руке не 3 карты', async () => {
    const handler = handlerFor('bloody-mary');
    const state = makeState({
      handZones: handOf(2) as any,
      metadata: { ...makeState().metadata, actionsRemaining: 2 },
    });
    const next = await handler.onTurnStart(state, 'player1');
    expect(getActionsRemaining(next)).toBe(2);
    expect(next).toBe(state); // чистый no-op
  });
});

// ===================== TURN-END =====================

describe('philippa (turn-end: drawToHandSize 4)', () => {
  it('добирает руку до 4 карт', async () => {
    const deps = makeDeps();
    const handler = handlerFor('philippa', deps);
    const state = makeState({ handZones: handOf(1) as any });
    const next = await handler.onTurnEnd(state, 'player1');

    // дефицит = 4 - 1 = 3
    expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 3);
    expect(next.handZones['player1'].cards).toHaveLength(4);
  });

  it('no-op: рука уже >= 4 (drawCards не зовётся)', async () => {
    const deps = makeDeps();
    const handler = handlerFor('philippa', deps);
    const state = makeState({ handZones: handOf(4) as any });
    const next = await handler.onTurnEnd(state, 'player1');
    expect(deps.deck.drawCards).not.toHaveBeenCalled();
    expect(next).toBe(state);
  });
});

describe('t-rex (turn-end: draw 1)', () => {
  it('добирает ровно 1 карту', async () => {
    const deps = makeDeps();
    const handler = handlerFor('t-rex', deps);
    const state = makeState({ handZones: handOf(2) as any });
    const next = await handler.onTurnEnd(state, 'player1');
    expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    expect(next.handZones['player1'].cards).toHaveLength(3);
  });

  it('turn-start ничего не делает (только turn-end правило)', async () => {
    const deps = makeDeps();
    const handler = handlerFor('t-rex', deps);
    const state = makeState();
    const next = await handler.onTurnStart(state, 'player1');
    expect(deps.deck.drawCards).not.toHaveBeenCalled();
    expect(next).toBe(state);
  });
});

describe('bigfoot (turn-end: draw 1 when no enemy in own zone)', () => {
  it('добирает 1, когда враг НЕ в зоне героя', async () => {
    const deps = makeDeps({ zone: makeZoneStub(false) });
    const handler = handlerFor('bigfoot', deps);
    const state = makeState({ handZones: handOf(1) as any });
    const next = await handler.onTurnEnd(state, 'player1');
    expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    expect(next.handZones['player1'].cards).toHaveLength(2);
  });

  it('no-op: враг в зоне героя', async () => {
    const deps = makeDeps({ zone: makeZoneStub(true) });
    const handler = handlerFor('bigfoot', deps);
    const state = makeState({ handZones: handOf(1) as any });
    const next = await handler.onTurnEnd(state, 'player1');
    expect(deps.deck.drawCards).not.toHaveBeenCalled();
    expect(next).toBe(state);
  });
});

// ===================== AFTER-ATTACK =====================

/** AfterCombatContext атакующего player1 с заданным исходом боя. */
function afterCtx(won: boolean): AfterCombatContext {
  return {
    playerId: 'player1',
    attackerFighterId: 'hero-fighter-1',
    defenderFighterId: 'enemy-fighter-1',
    won,
    damageDealt: won ? 2 : 0,
    // первый проигрыш хода (для проигранных боёв); при won — всегда false
    firstLossThisTurn: !won,
  };
}

describe('chupacabra (after-attack: always draw 1)', () => {
  it('добирает 1 карту после ПОБЕДЫ в бою', async () => {
    const deps = makeDeps();
    const handler = handlerFor('chupacabra', deps);
    const state = makeState({ handZones: handOf(2) as any });
    const next = await handler.onAfterCombat(state, afterCtx(true));
    expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    expect(next.handZones['player1'].cards).toHaveLength(3);
  });

  it('добирает 1 карту и после ПРОИГРЫША (condition always)', async () => {
    const deps = makeDeps();
    const handler = handlerFor('chupacabra', deps);
    const state = makeState({ handZones: handOf(2) as any });
    const next = await handler.onAfterCombat(state, afterCtx(false));
    expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    expect(next.handZones['player1'].cards).toHaveLength(3);
  });
});

describe('deadpool (after-attack: always heal 1)', () => {
  it('лечит 1 хп после ПОБЕДЫ в бою', async () => {
    const handler = handlerFor('deadpool');
    const state = makeState({
      fighters: [
        makeFighter({ heroSlug: 'deadpool', health: 10, maxHealth: 18 }),
        makeFighter({ id: 'enemy-fighter-1', ownerId: 'player2', health: 12, position: { x: 9, y: 9 } }),
      ],
    });
    const next = await handler.onAfterCombat(state, afterCtx(true));
    expect(next.fighters.find((f) => f.id === 'hero-fighter-1')!.health).toBe(11);
  });

  it('лечит 1 хп и после ПРОИГРЫША (condition always)', async () => {
    const handler = handlerFor('deadpool');
    const state = makeState({
      fighters: [
        makeFighter({ heroSlug: 'deadpool', health: 10, maxHealth: 18 }),
        makeFighter({ id: 'enemy-fighter-1', ownerId: 'player2', health: 12, position: { x: 9, y: 9 } }),
      ],
    });
    const next = await handler.onAfterCombat(state, afterCtx(false));
    expect(next.fighters.find((f) => f.id === 'hero-fighter-1')!.health).toBe(11);
  });

  it('хил не превышает maxHealth', async () => {
    const handler = handlerFor('deadpool');
    const state = makeState({
      fighters: [
        makeFighter({ heroSlug: 'deadpool', health: 18, maxHealth: 18 }),
        makeFighter({ id: 'enemy-fighter-1', ownerId: 'player2', health: 12, position: { x: 9, y: 9 } }),
      ],
    });
    const next = await handler.onAfterCombat(state, afterCtx(true));
    expect(next.fighters.find((f) => f.id === 'hero-fighter-1')!.health).toBe(18);
    expect(next).toBe(state); // capped → no-op (тот же объект)
  });
});

describe('michelangelo (after-attack: always draw 1)', () => {
  it('добирает 1 карту после боя (как при победе, так и при проигрыше)', async () => {
    const depsWon = makeDeps();
    const handlerWon = handlerFor('michelangelo', depsWon);
    const nextWon = await handlerWon.onAfterCombat(makeState({ handZones: handOf(1) as any }), afterCtx(true));
    expect(depsWon.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    expect(nextWon.handZones['player1'].cards).toHaveLength(2);

    const depsLost = makeDeps();
    const handlerLost = handlerFor('michelangelo', depsLost);
    const nextLost = await handlerLost.onAfterCombat(makeState({ handZones: handOf(1) as any }), afterCtx(false));
    expect(depsLost.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    expect(nextLost.handZones['player1'].cards).toHaveLength(2);
  });
});

describe('angel (after-attack: draw 1 only on lost-combat)', () => {
  it('добирает 1 карту ТОЛЬКО когда бой проигран (ctx.won === false)', async () => {
    const deps = makeDeps();
    const handler = handlerFor('angel', deps);
    const state = makeState({ handZones: handOf(2) as any });
    const next = await handler.onAfterCombat(state, afterCtx(false));
    expect(deps.deck.drawCards).toHaveBeenCalledWith(expect.anything(), 'player1', 1);
    expect(next.handZones['player1'].cards).toHaveLength(3);
  });

  it('no-op: бой выигран (ctx.won === true) — добора нет', async () => {
    const deps = makeDeps();
    const handler = handlerFor('angel', deps);
    const state = makeState({ handZones: handOf(2) as any });
    const next = await handler.onAfterCombat(state, afterCtx(true));
    expect(deps.deck.drawCards).not.toHaveBeenCalled();
    expect(next).toBe(state); // чистый no-op
  });
});

// ===================== НОВЫЕ ГЕРОИ (flag-gated) =====================

describe('golden-bat (combat-passive: +2 attack when has not maneuvered this turn)', () => {
  it('даёт +2 к атаке, когда maneuveredThisTurn falsy (манёвра в этом ходу не было)', () => {
    const handler = handlerFor('golden-bat');
    // makeState() без metadata.maneuveredThisTurn → falsy
    const attacker = makeFighter({ heroSlug: 'golden-bat' });
    const mods = handler.getStatefulCombatModifiers(makeState(), COMBAT, attacker, 'attacker');

    expect(mods).toHaveLength(1);
    expect(mods[0]).toMatchObject({ type: ValueModifierType.ADD, value: 2, ownerId: 'player1' });
  });

  it('no-op: maneuveredThisTurn === true (манёвр уже был в этом ходу)', () => {
    const handler = handlerFor('golden-bat');
    const state = makeState({
      metadata: { ...makeState().metadata, maneuveredThisTurn: true },
    });
    const attacker = makeFighter({ heroSlug: 'golden-bat' });
    const mods = handler.getStatefulCombatModifiers(state, COMBAT, attacker, 'attacker');
    expect(mods).toHaveLength(0);
  });

  it('защитник НЕ получает модификатор (appliesTo: attack)', () => {
    const handler = handlerFor('golden-bat');
    const fighter = makeFighter({ heroSlug: 'golden-bat' });
    const mods = handler.getStatefulCombatModifiers(makeState(), COMBAT, fighter, 'defender');
    expect(mods).toHaveLength(0);
  });
});

describe('ancient-leshen (combat-passive: +3 attack when already attacked this turn)', () => {
  it('даёт +3 к атаке, когда attackedThisTurn === true', () => {
    const handler = handlerFor('ancient-leshen');
    const state = makeState({
      metadata: { ...makeState().metadata, attackedThisTurn: true },
    });
    const attacker = makeFighter({ heroSlug: 'ancient-leshen' });
    const mods = handler.getStatefulCombatModifiers(state, COMBAT, attacker, 'attacker');

    expect(mods).toHaveLength(1);
    expect(mods[0]).toMatchObject({ type: ValueModifierType.ADD, value: 3, ownerId: 'player1' });
  });

  it('no-op: attackedThisTurn falsy (ещё не атаковал в этом ходу)', () => {
    const handler = handlerFor('ancient-leshen');
    // makeState() без metadata.attackedThisTurn → falsy
    const attacker = makeFighter({ heroSlug: 'ancient-leshen' });
    const mods = handler.getStatefulCombatModifiers(makeState(), COMBAT, attacker, 'attacker');
    expect(mods).toHaveLength(0);
  });

  it('защитник НЕ получает модификатор (appliesTo: attack)', () => {
    const handler = handlerFor('ancient-leshen');
    const state = makeState({
      metadata: { ...makeState().metadata, attackedThisTurn: true },
    });
    const fighter = makeFighter({ heroSlug: 'ancient-leshen' });
    const mods = handler.getStatefulCombatModifiers(state, COMBAT, fighter, 'defender');
    expect(mods).toHaveLength(0);
  });
});

describe('raphael (after-attack: gainAction +1 on first lost combat this turn)', () => {
  it('+1 действие при ПЕРВОМ проигрыше хода (won===false && firstLossThisTurn===true)', async () => {
    const handler = handlerFor('raphael');
    const state = makeState({
      metadata: { ...makeState().metadata, actionsRemaining: 2 },
    });
    const next = await handler.onAfterCombat(state, {
      playerId: 'player1',
      attackerFighterId: 'hero-fighter-1',
      defenderFighterId: 'enemy-fighter-1',
      won: false,
      damageDealt: 0,
      firstLossThisTurn: true,
    });
    expect(getActionsRemaining(next)).toBe(3);
  });

  it('no-op: бой выигран (ctx.won === true)', async () => {
    const handler = handlerFor('raphael');
    const state = makeState({
      metadata: { ...makeState().metadata, actionsRemaining: 2 },
    });
    const next = await handler.onAfterCombat(state, {
      playerId: 'player1',
      attackerFighterId: 'hero-fighter-1',
      defenderFighterId: 'enemy-fighter-1',
      won: true,
      damageDealt: 2,
      firstLossThisTurn: false,
    });
    expect(getActionsRemaining(next)).toBe(2);
    expect(next).toBe(state); // чистый no-op
  });

  it('no-op: проигрыш, но НЕ первый в этом ходу (firstLossThisTurn === false)', async () => {
    const handler = handlerFor('raphael');
    const state = makeState({
      metadata: { ...makeState().metadata, actionsRemaining: 2 },
    });
    const next = await handler.onAfterCombat(state, {
      playerId: 'player1',
      attackerFighterId: 'hero-fighter-1',
      defenderFighterId: 'enemy-fighter-1',
      won: false,
      damageDealt: 0,
      firstLossThisTurn: false,
    });
    expect(getActionsRemaining(next)).toBe(2);
    expect(next).toBe(state); // чистый no-op
  });
});

// ===================== PENDING-MOVE ГЕРОИ =====================

describe('robin-hood (after-attack: pending-move attacker, maxSpaces 2)', () => {
  it('после атаки добавляет MOVE pending для атаковавшего бойца (value 2, fighterName=имя атакующего, playerId)', async () => {
    const handler = handlerFor('robin-hood');
    const state = makeState();

    const next = await handler.onAfterCombat(state, afterCtx(true));

    const pending = next.metadata.pendingEffects ?? [];
    expect(pending).toHaveLength(1);
    expect(pending[0]).toMatchObject({
      type: 'MOVE',
      playerId: 'player1',
      value: 2,
      fighterName: 'Hero', // имя бойца из ctx.attackerFighterId (makeFighter().name === 'Hero')
      targetsOpponent: false,
    });
    // pendingEffects никогда не двигают seq; исходный state не мутирован
    expect(next.sequenceNumber).toBe(state.sequenceNumber);
    expect(state.metadata.pendingEffects).toBeUndefined();
  });

  it('после атаки добавляет MOVE pending и при проигрыше (condition always)', async () => {
    const handler = handlerFor('robin-hood');
    const next = await handler.onAfterCombat(makeState(), afterCtx(false));
    expect(next.metadata.pendingEffects ?? []).toHaveLength(1);
    expect((next.metadata.pendingEffects ?? [])[0]).toMatchObject({ value: 2, fighterName: 'Hero' });
  });

  it('turn-start ничего не делает (только after-attack правило)', async () => {
    const handler = handlerFor('robin-hood');
    const state = makeState();
    const next = await handler.onTurnStart(state, 'player1');
    expect(next).toBe(state);
  });
});

describe('leonardo (turn-start: pending-move any-own, maxSpaces 1)', () => {
  it('в начале хода добавляет MOVE pending без fighterName (value 1, playerId)', async () => {
    const handler = handlerFor('leonardo');
    const state = makeState();

    const next = await handler.onTurnStart(state, 'player1');

    const pending = next.metadata.pendingEffects ?? [];
    expect(pending).toHaveLength(1);
    expect(pending[0]).toMatchObject({
      type: 'MOVE',
      playerId: 'player1',
      value: 1,
      targetsOpponent: false,
    });
    // any-own → без ограничения по бойцу
    expect(pending[0].fighterName).toBeUndefined();
    expect(next.sequenceNumber).toBe(state.sequenceNumber);
    expect(state.metadata.pendingEffects).toBeUndefined();
  });

  it('after-combat ничего не делает (только turn-start правило)', async () => {
    const handler = handlerFor('leonardo');
    const state = makeState();
    const next = await handler.onAfterCombat(state, afterCtx(true));
    expect(next).toBe(state);
  });
});

// NB: 'after-defense' инфра (триггер + ctx.defenderPlayerId) покрыта synthetic-
// тестами в generic-hero-ability.handler.spec.ts. Конкретного героя пока нет
// (реальный Spider-Man = info-reveal, COMPLEX — не реализован).
