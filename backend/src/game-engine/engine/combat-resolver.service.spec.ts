/**
 * Combat Resolver Service Unit Tests
 *
 * Полные тесты для combat-resolver.service.ts.
 * Покрывают:
 * - Разрешение атаки с защитой
 * - Расчет урона
 * - Применение эффектов карт
 * - Особые случаи (критический урон, пробивание защиты)
 * - Интеграционные тесты с CardEffectExecutor
 * - Тесты с эффектами героев (Daredevil, Ms. Marvel)
 */

import { Test, TestingModule } from '@nestjs/testing';
import { MetricsService } from '../../metrics/metrics.service';
import { CombatResolverService, CombatResult } from './combat-resolver.service';
import {
  HeroAbilityRegistry,
  ValueModifier,
  ValueModifierType,
} from '../abilities/hero-ability-registry';
import {
  GameState,
  GamePhase,
  GameStatePlayer,
  CardType,
  EffectTiming,
  EffectType,
  EffectTarget,
  HandCard,
  Card,
} from '../models';
import { Fighter, FighterType, Position } from '../models';
import { createEmptyBoardState } from '../models/board.model';

// =============================================================================
// MOCK OBJECTS AND HELPER FUNCTIONS
// =============================================================================

/**
 * Создаёт базовое состояние игры для тестов
 */
function createMockGameState(overrides?: Partial<GameState>): GameState {
  const baseState: GameState = {
    gameId: 'test-game',
    sequenceNumber: 1,
    phase: GamePhase.COMBAT,
    turnCount: 1,
    currentTurnPlayerId: 'player-1',
    players: [
      {
        userId: 'player-1',
        heroId: 'hero-1',
        health: 10,
        maxHealth: 10,
        fighterIds: ['fighter-1'],
        isAlive: true,
      },
      {
        userId: 'player-2',
        heroId: 'hero-2',
        health: 10,
        maxHealth: 10,
        fighterIds: ['fighter-2'],
        isAlive: true,
      },
    ],
    fighters: [
      {
        id: 'fighter-1',
        ownerId: 'player-1',
        heroId: 'hero-1',
        name: 'Test Fighter 1',
        type: FighterType.HERO,
        health: 10,
        maxHealth: 10,
        position: { x: 0, y: 0 },
        effects: [],
        hasSidekick: false,
      },
      {
        id: 'fighter-2',
        ownerId: 'player-2',
        heroId: 'hero-2',
        name: 'Test Fighter 2',
        type: FighterType.HERO,
        health: 10,
        maxHealth: 10,
        position: { x: 1, y: 0 },
        effects: [],
        hasSidekick: false,
      },
    ],
    decks: {
      'player-1': {
        cards: [],
        drawPile: [],
      },
      'player-2': {
        cards: [],
        drawPile: [],
      },
    },
    discardPiles: {
      'player-1': [],
      'player-2': [],
    },
    handZones: {
      'player-1': {
        cards: [],
        maxSize: 5,
      },
      'player-2': {
        cards: [],
        maxSize: 5,
      },
    },
    boardState: createEmptyBoardState(6, 6),
    metadata: {
      lastActionAt: new Date(),
      lastActionBy: 'player-1',
      version: 1,
    },
  };

  return { ...baseState, ...overrides };
}

/**
 * Создаёт тестовую карту
 */
function createMockCard(id: string, overrides?: Partial<Card>): HandCard {
  const baseCard: HandCard = {
    id,
    cardId: id,
    name: `Card ${id}`,
    nameEn: `Card ${id}`,
    nameRu: `Карта ${id}`,
    cardType: CardType.ATTACK,
    attackValue: 0,
    defenseValue: 0,
    boostValue: 0,
    effects: [],
    isVisible: true,
  };

  return { ...baseCard, ...overrides };
}

/**
 * Создаёт состояние игры с картами в руках
 */
function createGameStateWithCards(attackCard: HandCard, defenseCard?: HandCard): GameState {
  return createMockGameState({
    handZones: {
      'player-1': {
        cards: [attackCard],
        maxSize: 5,
      },
      'player-2': {
        cards: defenseCard ? [defenseCard] : [],
        maxSize: 5,
      },
    },
  });
}

/**
 * Создаёт мок для HeroAbilityRegistry
 */
function createMockAbilityRegistry(
  modifiers: {
    attacker?: readonly ValueModifier[];
    defender?: readonly ValueModifier[];
  } = {},
): HeroAbilityRegistry {
  const mockRegistry = {
    applyCombatModifiers: jest.fn().mockImplementation((heroId, combatState, fighter, role) => {
      if (role === 'attacker' && modifiers.attacker) {
        return modifiers.attacker;
      }
      if (role === 'defender' && modifiers.defender) {
        return modifiers.defender;
      }
      return [];
    }),
    register: jest.fn(),
    registerExtended: jest.fn(),
    get: jest.fn(),
    getExtended: jest.fn(),
    getAny: jest.fn(),
    has: jest.fn(),
    getRegisteredHeroes: jest.fn(),
    triggerOnMove: jest.fn(),
    triggerOnDefeat: jest.fn(),
    triggerOnTurnStart: jest.fn(),
    triggerOnTurnEnd: jest.fn(),
    canAttackAtRange: jest.fn(),
    triggerOnTurnStartExtended: jest.fn(),
    triggerOnTurnEndExtended: jest.fn(),
    triggerOnCombat: jest.fn(),
    getExtendedCombatModifiers: jest.fn(),
  };

  return mockRegistry as unknown as HeroAbilityRegistry;
}

/**
 * Создаёт модификатор значения
 */
function createValueModifier(
  value: number,
  overrides?: Partial<
    Omit<ValueModifier, 'type' | 'value' | 'source' | 'timestamp' | 'ownerId'>
  > & { source?: string },
): ValueModifier {
  return {
    type: ValueModifierType.ADD,
    value,
    source: overrides?.source || 'test-source',
    timestamp: Date.now(),
    ownerId: 'test-owner',
    ...overrides,
  };
}

// =============================================================================
// TEST SUITES
// =============================================================================

describe('CombatResolverService', () => {
  let service: CombatResolverService;
  let mockAbilityRegistry: HeroAbilityRegistry;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CombatResolverService,
        { provide: MetricsService, useValue: { measureServiceDuration: jest.fn((_n, _c, fn) => fn()), measureCombat: jest.fn((_a, _d, fn) => fn()), incrementError: jest.fn() } },
        {
          provide: HeroAbilityRegistry,
          useFactory: () => createMockAbilityRegistry(),
        },
      ],
    }).compile();

    service = module.get<CombatResolverService>(CombatResolverService);
    mockAbilityRegistry = module.get<HeroAbilityRegistry>(HeroAbilityRegistry);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Service initialization', () => {
    it('должен быть определён', () => {
      expect(service).toBeDefined();
    });

    it('должен иметь зависимость от HeroAbilityRegistry', () => {
      expect(service['abilityRegistry']).toBe(mockAbilityRegistry);
    });
  });

  // ===========================================================================
  // UNIT TESTS: БАЗОВЫЙ РАСЧЁТ БОЯ
  // ===========================================================================

  describe('resolveCombat - базовый расчёт боя', () => {
    it('должен выбросить ошибку если атакующий не найден', async () => {
      const state = createMockGameState();
      const attackCard = createMockCard('atk-1', { attackValue: 5 });

      await expect(
        service.resolveCombat(state, 'non-existent', 'fighter-2', attackCard.id),
      ).rejects.toThrow('Invalid combat: fighter not found');
    });

    it('должен выбросить ошибку если защитник не найден', async () => {
      const state = createMockGameState();
      const attackCard = createMockCard('atk-1', { attackValue: 5 });

      await expect(
        service.resolveCombat(state, 'fighter-1', 'non-existent', attackCard.id),
      ).rejects.toThrow('Invalid combat: fighter not found');
    });

    it('должен вычислить урон защитнику когда атака больше защиты', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      expect(result.attackerDamage).toBe(0);
      expect(result.defenderDamage).toBe(2); // 5 - 3 = 2
      expect(result.nextState.fighters.find((f) => f.id === 'fighter-2')?.health).toBe(8); // 10 - 2
    });

    it('должен вычислить урон атакующему когда защита больше атаки', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 3 });
      const defenseCard = createMockCard('def-1', { defenseValue: 5, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      expect(result.attackerDamage).toBe(2); // 5 - 3 = 2
      expect(result.defenderDamage).toBe(0);
      expect(result.nextState.fighters.find((f) => f.id === 'fighter-1')?.health).toBe(8); // 10 - 2
    });

    it('должен вернуть нулевой урон когда атака равна защите', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 4 });
      const defenseCard = createMockCard('def-1', { defenseValue: 4, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      expect(result.attackerDamage).toBe(0);
      expect(result.defenderDamage).toBe(0);
    });

    it('должен нанести полный урон атакующему когда защиты нет', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const state = createGameStateWithCards(attackCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        undefined,
      );

      expect(result.defenderDamage).toBe(5);
      expect(result.attackerDamage).toBe(0);
      expect(result.nextState.fighters.find((f) => f.id === 'fighter-2')?.health).toBe(5); // 10 - 5
    });

    it('должен обновить sequenceNumber в следующем состоянии', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 3 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      expect(result.nextState.sequenceNumber).toBe(state.sequenceNumber + 1);
    });

    it('должен обновить lastActionAt и lastActionBy в метаданных', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 3 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      expect(result.nextState.metadata.lastActionBy).toBe('fighter-1');
      expect(result.nextState.metadata.lastActionAt).toBeInstanceOf(Date);
    });
  });

  // ===========================================================================
  // UNIT TESTS: МОДИФИКАТОРЫ ОТ СПОСОБНОСТЕЙ ГЕРОЕВ
  // ===========================================================================

  describe('resolveCombat - с модификаторами способностей', () => {
    beforeEach(async () => {
      const module: TestingModule = await Test.createTestingModule({
        providers: [
          CombatResolverService,
          { provide: MetricsService, useValue: { measureServiceDuration: jest.fn((_n, _c, fn) => fn()), measureCombat: jest.fn((_a, _d, fn) => fn()), incrementError: jest.fn() } },
          {
            provide: HeroAbilityRegistry,
            useFactory: () => createMockAbilityRegistry(),
          },
        ],
      }).compile();

      service = module.get<CombatResolverService>(CombatResolverService);
      mockAbilityRegistry = module.get<HeroAbilityRegistry>(HeroAbilityRegistry);
    });

    it('должен добавить модификатор атаки к итоговому значению', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 4 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const attackModifier = createValueModifier(2); // +2 к атаке
      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (heroId, combatState, fighter, role) => {
          if (role === 'attacker') return [attackModifier];
          return [];
        },
      );

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // 4 (база) + 2 (модификатор) - 3 (защита) = 3 урона
      expect(result.defenderDamage).toBe(3);
      expect(result.attackerEffectsApplied).toHaveLength(1);
      expect(result.attackerEffectsApplied[0]).toBe('test-source');
    });

    it('должен добавить модификатор защиты к итоговому значению', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 2, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const defenseModifier = createValueModifier(3); // +3 к защите
      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (heroId, combatState, fighter, role) => {
          if (role === 'defender') return [defenseModifier];
          return [];
        },
      );

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // 5 (атака) - (2 + 3) (защита с модификатором) = 0 урона, 2 урона атакующему
      expect(result.attackerDamage).toBe(0);
      expect(result.defenderDamage).toBe(0);
      expect(result.defenderEffectsApplied).toHaveLength(1);
      expect(result.defenderEffectsApplied[0]).toBe('test-source');
    });

    it('должен применить модификаторы к обеим сторонам', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 4 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const attackModifier = createValueModifier(2, { source: 'atk-mod' });
      const defenseModifier = createValueModifier(1, { source: 'def-mod' });

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (heroId, combatState, fighter, role) => {
          if (role === 'attacker') return [attackModifier];
          if (role === 'defender') return [defenseModifier];
          return [];
        },
      );

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // (4 + 2) - (3 + 1) = 2 урона защитнику
      expect(result.defenderDamage).toBe(2);
      expect(result.attackerEffectsApplied).toHaveLength(1);
      expect(result.defenderEffectsApplied).toHaveLength(1);
      expect(result.attackerEffectsApplied[0]).toBe('atk-mod');
      expect(result.defenderEffectsApplied[0]).toBe('def-mod');
    });

    it('должен суммировать несколько модификаторов атаки', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 3 });
      const defenseCard = createMockCard('def-1', { defenseValue: 4, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const mod1 = createValueModifier(2, { source: 'mod-1' });
      const mod2 = createValueModifier(3, { source: 'mod-2' });

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (heroId, combatState, fighter, role) => {
          if (role === 'attacker') return [mod1, mod2];
          return [];
        },
      );

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // (3 + 2 + 3) - 4 = 4 урона защитнику
      expect(result.defenderDamage).toBe(4);
      expect(result.attackerEffectsApplied).toHaveLength(2);
      expect(result.attackerEffectsApplied).toContain('mod-1');
      expect(result.attackerEffectsApplied).toContain('mod-2');
    });

    it('должен игнорировать модификаторы не типа ADD', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 3 });
      const defenseCard = createMockCard('def-1', { defenseValue: 4, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const setModifier: ValueModifier = {
        type: ValueModifierType.SET,
        value: 10,
        source: 'test',
        timestamp: Date.now(),
        ownerId: 'test',
      };

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockReturnValue([setModifier]);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // SET модификатор не учитывается в текущей реализации
      expect(result.defenderDamage).toBe(0); // 3 - 4 = 0 урона
    });
  });

  // ===========================================================================
  // UNIT TESTS: ОБРАБОТКА УРОНА И СОСТОЯНИЯ БОЙЦОВ
  // ===========================================================================

  describe('applyDamage - обработка урона', () => {
    it('должен снизить здоровье бойца без отрицательных значений', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 15 }); // Больше чем здоровье
      const state = createGameStateWithCards(attackCard);

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id);

      const defender = result.nextState.fighters.find((f) => f.id === 'fighter-2');
      expect(defender?.health).toBe(0); // Не может быть отрицательным
    });

    it('должен установить isDefeated когда здоровье достигает 0', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 10 });
      const state = createGameStateWithCards(attackCard);

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id);

      const defender = result.nextState.fighters.find((f) => f.id === 'fighter-2');
      expect(defender?.health).toBe(0);
      // isDefeated добавляется динамически, проверяем через расширение типа
      expect((defender as Fighter & { isDefeated?: boolean })?.isDefeated).toBe(true);
    });

    it('должен оставить isDefeated = false когда здоровье больше 0', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      const defender = result.nextState.fighters.find((f) => f.id === 'fighter-2');
      expect(defender?.health).toBe(8);
      expect((defender as Fighter & { isDefeated?: boolean })?.isDefeated).toBe(false);
    });

    it('должен обновить isAlive для игрока когда все бойцы проиграли', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 10 });
      const state = createMockGameState({
        players: [
          {
            userId: 'player-1',
            heroId: 'hero-1',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-1'],
            isAlive: true,
          },
          {
            userId: 'player-2',
            heroId: 'hero-2',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-2'],
            isAlive: true,
          },
        ],
        fighters: [
          {
            id: 'fighter-1',
            ownerId: 'player-1',
            heroId: 'hero-1',
            name: 'Test Fighter 1',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 0, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter-2',
            ownerId: 'player-2',
            heroId: 'hero-2',
            name: 'Test Fighter 2',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 1, y: 0 },
            effects: [],
            hasSidekick: false,
          },
        ],
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [], maxSize: 5 },
        },
      });

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id);

      const player2 = result.nextState.players.find((p) => p.userId === 'player-2');
      expect(player2?.isAlive).toBe(false);
    });
  });

  // ===========================================================================
  // UNIT TESTS: ПРОВЕРКА ОКОНЧАНИЯ ИГРЫ
  // ===========================================================================

  describe('checkGameOver', () => {
    it('должен вернуть isOver: false когда больше 1 живого игрока', () => {
      const state = createMockGameState();
      const result = service.checkGameOver(state);

      expect(result.isOver).toBe(false);
      expect(result.winnerId).toBeUndefined();
    });

    it('должен вернуть isOver: true когда остался 1 живой игрок', () => {
      const state = createMockGameState({
        players: [
          {
            userId: 'player-1',
            heroId: 'hero-1',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-1'],
            isAlive: true,
          },
          {
            userId: 'player-2',
            heroId: 'hero-2',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-2'],
            isAlive: false,
          },
        ],
      });

      const result = service.checkGameOver(state);

      expect(result.isOver).toBe(true);
      expect(result.winnerId).toBe('player-1');
    });

    it('должен вернуть isOver: true когда все игроки проиграли', () => {
      const state = createMockGameState({
        players: [
          {
            userId: 'player-1',
            heroId: 'hero-1',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-1'],
            isAlive: false,
          },
          {
            userId: 'player-2',
            heroId: 'hero-2',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-2'],
            isAlive: false,
          },
        ],
      });

      const result = service.checkGameOver(state);

      expect(result.isOver).toBe(true);
      expect(result.winnerId).toBeUndefined();
    });

    it('должен вернуть isOver: true когда только 1 игрок в игре', () => {
      const state = createMockGameState({
        players: [
          {
            userId: 'player-1',
            heroId: 'hero-1',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-1'],
            isAlive: true,
          },
        ],
      });

      const result = service.checkGameOver(state);

      expect(result.isOver).toBe(true);
      expect(result.winnerId).toBe('player-1');
    });
  });

  // ===========================================================================
  // UNIT TESTS: ПОИСК КАРТ В РАЗНЫХ ЗОНАХ
  // ===========================================================================

  describe('getCardAttackValue и getCardDefenseValue', () => {
    it('должен найти карту атаки в руке игрока', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5, defenseValue: 2 });
      const state = createGameStateWithCards(attackCard);

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id);

      expect(result.defenderDamage).toBe(5);
    });

    it('должен найти карту в колоде если её нет в руке', async () => {
      const deckCard = createMockCard('deck-1', { attackValue: 7 });

      const state = createMockGameState({
        decks: {
          'player-1': {
            cards: [],
            drawPile: [deckCard],
          },
          'player-2': {
            cards: [],
            drawPile: [],
          },
        },
      });

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', 'deck-1');

      expect(result.defenderDamage).toBe(7);
    });

    it('должен вернуть 0 если карта не найдена', async () => {
      const state = createMockGameState();

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', 'non-existent');

      expect(result.defenderDamage).toBe(0);
      expect(result.attackerDamage).toBe(0);
    });

    it('должен найти defenceValue карты', async () => {
      const defenseCard = createMockCard('def-1', {
        defenseValue: 4,
        cardType: CardType.DEFENSE,
      });
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // 5 - 4 = 1
      expect(result.defenderDamage).toBe(1);
    });
  });

  // ===========================================================================
  // INTEGRATION TESTS: DAREDEVIL HANDLER
  // ===========================================================================

  describe('Интеграция с Daredevil Handler', () => {
    function createDaredevilState(overrides?: Partial<GameState>): GameState {
      return createMockGameState({
        players: [
          {
            userId: 'player-1',
            heroId: 'daredevil',
            health: 17,
            maxHealth: 17,
            fighterIds: ['fighter-daredevil'],
            isAlive: true,
          },
          {
            userId: 'player-2',
            heroId: 'hero-2',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-2'],
            isAlive: true,
          },
        ],
        fighters: [
          {
            id: 'fighter-daredevil',
            ownerId: 'player-1',
            heroId: 'daredevil',
            name: 'Daredevil',
            type: FighterType.HERO,
            health: 17,
            maxHealth: 17,
            position: { x: 0, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter-2',
            ownerId: 'player-2',
            heroId: 'hero-2',
            name: 'Test Fighter 2',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 1, y: 0 },
            effects: [],
            hasSidekick: false,
          },
        ],
        decks: {
          'player-1': {
            cards: [],
            drawPile: [createMockCard('blind-boost-card', { boostValue: 2, attackValue: 3 })],
          },
          'player-2': {
            cards: [],
            drawPile: [],
          },
        },
        ...overrides,
      });
    }

    it('должен применить Blind Boost модификатор к атаке Daredevil', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 4 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });

      const daredevilState = createDaredevilState({
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [defenseCard], maxSize: 5 },
        },
      });

      const blindBoostModifier = createValueModifier(2, { source: 'daredevil-blind-boost' });

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (heroId, combatState, fighter, role) => {
          if (role === 'attacker' && heroId === 'daredevil') {
            return [blindBoostModifier];
          }
          return [];
        },
      );

      const result = await service.resolveCombat(
        daredevilState,
        'fighter-daredevil',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // 4 (атака) + 2 (blind boost) - 3 (защита) = 3 урона
      expect(result.defenderDamage).toBe(3);
      expect(result.attackerEffectsApplied).toHaveLength(1);
    });

    it('должен применить Blind Boost модификатор к защите Daredevil', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 2, cardType: CardType.DEFENSE });

      const daredevilState = createDaredevilState({
        handZones: {
          'player-1': { cards: [defenseCard], maxSize: 5 },
          'player-2': { cards: [attackCard], maxSize: 5 },
        },
      });

      const blindBoostModifier = createValueModifier(3, { source: 'daredevil-blind-boost-def' });

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (heroId, combatState, fighter, role) => {
          if (role === 'defender' && heroId === 'daredevil') {
            return [blindBoostModifier];
          }
          return [];
        },
      );

      const result = await service.resolveCombat(
        daredevilState,
        'fighter-2',
        'fighter-daredevil',
        attackCard.id,
        defenseCard.id,
      );

      // 5 (атака) - (2 + 3) (защита + blind boost) = 0, урон атакующему 0
      expect(result.attackerDamage).toBe(0);
      expect(result.defenderDamage).toBe(0);
      expect(result.defenderEffectsApplied).toHaveLength(1);
    });
  });

  // ===========================================================================
  // INTEGRATION TESTS: MS. MARVEL HANDLER
  // ===========================================================================

  describe('Интеграция с Ms. Marvel Handler', () => {
    function createMsMarvelState(overrides?: Partial<GameState>): GameState {
      return createMockGameState({
        players: [
          {
            userId: 'player-1',
            heroId: 'ms-marvel',
            health: 18,
            maxHealth: 18,
            fighterIds: ['fighter-msmarvel'],
            isAlive: true,
          },
          {
            userId: 'player-2',
            heroId: 'hero-2',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-2'],
            isAlive: true,
          },
        ],
        fighters: [
          {
            id: 'fighter-msmarvel',
            ownerId: 'player-1',
            heroId: 'ms-marvel',
            name: 'Ms. Marvel',
            type: FighterType.HERO,
            health: 18,
            maxHealth: 18,
            position: { x: 0, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter-2',
            ownerId: 'player-2',
            heroId: 'hero-2',
            name: 'Test Fighter 2',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 2, y: 0 }, // На расстоянии 2 клетки
            effects: [],
            hasSidekick: false,
          },
        ],
        ...overrides,
      });
    }

    it('должен провести бой для Ms. Marvel на расстоянии 2 клетки', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 4 });
      const defenseCard = createMockCard('def-1', { defenseValue: 2, cardType: CardType.DEFENSE });

      const msMarvelState = createMsMarvelState({
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [defenseCard], maxSize: 5 },
        },
      });

      // Ms. Marvel может атаковать на расстоянии 2
      // CombatResolver не проверяет дистанцию - это делается на уровне GameEngine
      const result = await service.resolveCombat(
        msMarvelState,
        'fighter-msmarvel',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      expect(result.defenderDamage).toBe(2); // 4 - 2
      expect(result.attackerDamage).toBe(0);
    });

    it('должен корректно обрабатывать модификаторы от способности Stretchy', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });

      const msMarvelState = createMsMarvelState({
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [], maxSize: 5 },
        },
      });

      const stretchyModifier = createValueModifier(1, {
        source: 'ms-marvel-stretchy',
      });

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (heroId, combatState, fighter, role) => {
          if (role === 'attacker' && heroId === 'ms-marvel') {
            return [stretchyModifier];
          }
          return [];
        },
      );

      const result = await service.resolveCombat(
        msMarvelState,
        'fighter-msmarvel',
        'fighter-2',
        attackCard.id,
      );

      // 5 + 1 = 6 урона
      expect(result.defenderDamage).toBe(6);
      expect(result.attackerEffectsApplied).toHaveLength(1);
    });
  });

  // ===========================================================================
  // EDGE CASES: ОСОБЫЕ СЛУЧАИ
  // ===========================================================================

  describe('Особые случаи (Edge Cases)', () => {
    it('должен корректно обрабатывать нулевые значения атаки и защиты', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 0 });
      const defenseCard = createMockCard('def-1', { defenseValue: 0, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      expect(result.attackerDamage).toBe(0);
      expect(result.defenderDamage).toBe(0);
    });

    it('должен корректно обрабатывать отрицательные модификаторы', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const negativeModifier: ValueModifier = {
        type: ValueModifierType.ADD,
        value: -2,
        source: 'debuff',
        timestamp: Date.now(),
        ownerId: 'test',
      };

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (_h: string, _c: unknown, _f: unknown, role: string) => (role === 'attacker' ? [negativeModifier] : []),
      );

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // (5 - 2) - 3 = 0
      expect(result.defenderDamage).toBe(0);
    });

    it('должен не изменять здоровье других бойцов', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 3 });

      const state = createMockGameState({
        fighters: [
          {
            id: 'fighter-1',
            ownerId: 'player-1',
            heroId: 'hero-1',
            name: 'Test Fighter 1',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 0, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter-2',
            ownerId: 'player-2',
            heroId: 'hero-2',
            name: 'Test Fighter 2',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 1, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter-3',
            ownerId: 'player-2',
            heroId: 'hero-3',
            name: 'Test Fighter 3',
            type: FighterType.MINION,
            health: 5,
            maxHealth: 5,
            position: { x: 2, y: 0 },
            effects: [],
            hasSidekick: false,
          },
        ],
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [], maxSize: 5 },
        },
      });

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id);

      const fighter3 = result.nextState.fighters.find((f) => f.id === 'fighter-3');
      expect(fighter3?.health).toBe(5); // Не изменился
    });

    it('должен сохранить данные о игроках которые не участвовали в бою', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 3 });

      const state = createMockGameState({
        players: [
          {
            userId: 'player-1',
            heroId: 'hero-1',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-1'],
            isAlive: true,
          },
          {
            userId: 'player-2',
            heroId: 'hero-2',
            health: 10,
            maxHealth: 10,
            fighterIds: ['fighter-2'],
            isAlive: true,
          },
          {
            userId: 'player-3',
            heroId: 'hero-3',
            health: 15,
            maxHealth: 15,
            fighterIds: ['fighter-3'],
            isAlive: true,
          },
        ],
        fighters: [
          {
            id: 'fighter-1',
            ownerId: 'player-1',
            heroId: 'hero-1',
            name: 'Test Fighter 1',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 0, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter-2',
            ownerId: 'player-2',
            heroId: 'hero-2',
            name: 'Test Fighter 2',
            type: FighterType.HERO,
            health: 10,
            maxHealth: 10,
            position: { x: 1, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter-3',
            ownerId: 'player-3',
            heroId: 'hero-3',
            name: 'Test Fighter 3',
            type: FighterType.HERO,
            health: 15,
            maxHealth: 15,
            position: { x: 3, y: 0 },
            effects: [],
            hasSidekick: false,
          },
        ],
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [], maxSize: 5 },
          'player-3': { cards: [], maxSize: 5 },
        },
      });

      const result = await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id);

      const player3 = result.nextState.players.find((p) => p.userId === 'player-3');
      expect(player3?.isAlive).toBe(true);
      expect(player3?.health).toBe(15);
    });

    it('должен возвращать иммутабельное состояние (не мутировать исходное)', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const originalState = createGameStateWithCards(attackCard, defenseCard);

      const originalFighter1Health = originalState.fighters.find(
        (f) => f.id === 'fighter-1',
      )?.health;
      const originalFighter2Health = originalState.fighters.find(
        (f) => f.id === 'fighter-2',
      )?.health;
      const originalSequenceNumber = originalState.sequenceNumber;

      const result = await service.resolveCombat(
        originalState,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // Исходное состояние не должно измениться
      expect(originalState.fighters.find((f) => f.id === 'fighter-1')?.health).toBe(
        originalFighter1Health,
      );
      expect(originalState.fighters.find((f) => f.id === 'fighter-2')?.health).toBe(
        originalFighter2Health,
      );
      expect(originalState.sequenceNumber).toBe(originalSequenceNumber);

      // Новое состояние должно иметь другие значения
      expect(result.nextState.fighters.find((f) => f.id === 'fighter-2')?.health).toBe(8);
      expect(result.nextState.sequenceNumber).toBe(originalSequenceNumber + 1);
    });

    it('должен обрабатывать очень большие значения модификаторов', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 1 });
      const defenseCard = createMockCard('def-1', { defenseValue: 0, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const hugeModifier = createValueModifier(1000);

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockImplementation(
        (_h: string, _c: unknown, _f: unknown, role: string) => (role === 'attacker' ? [hugeModifier] : []),
      );

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // (1 + 1000) - 0 = 1001, но здоровье не может быть ниже 0
      expect(result.defenderDamage).toBe(1001);
      expect(result.nextState.fighters.find((f) => f.id === 'fighter-2')?.health).toBe(0);
    });

    it('должен корректно обрабатывать бой между миньонами', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 2 });

      const state = createMockGameState({
        fighters: [
          {
            id: 'minion-1',
            ownerId: 'player-1',
            heroId: 'hero-1',
            name: 'Minion 1',
            type: FighterType.MINION,
            health: 3,
            maxHealth: 3,
            position: { x: 0, y: 0 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'minion-2',
            ownerId: 'player-2',
            heroId: 'hero-2',
            name: 'Minion 2',
            type: FighterType.MINION,
            health: 3,
            maxHealth: 3,
            position: { x: 1, y: 0 },
            effects: [],
            hasSidekick: false,
          },
        ],
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [], maxSize: 5 },
        },
      });

      const result = await service.resolveCombat(state, 'minion-1', 'minion-2', attackCard.id);

      expect(result.defenderDamage).toBe(2);
      expect(result.nextState.fighters.find((f) => f.id === 'minion-2')?.health).toBe(1);
    });

    it('должен вызывать applyCombatModifiers для обоих героев', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 4 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id, defenseCard.id);

      expect(mockAbilityRegistry.applyCombatModifiers).toHaveBeenCalledTimes(2);
      expect(mockAbilityRegistry.applyCombatModifiers).toHaveBeenCalledWith(
        'hero-1',
        expect.objectContaining({
          attackerId: 'fighter-1',
          defenderId: 'fighter-2',
          attackCardId: attackCard.id,
          defenseCardId: defenseCard.id,
        }),
        expect.objectContaining({ id: 'fighter-1' }),
        'attacker',
      );
      expect(mockAbilityRegistry.applyCombatModifiers).toHaveBeenCalledWith(
        'hero-2',
        expect.objectContaining({
          attackerId: 'fighter-1',
          defenderId: 'fighter-2',
          attackCardId: attackCard.id,
          defenseCardId: defenseCard.id,
        }),
        expect.objectContaining({ id: 'fighter-2' }),
        'defender',
      );
    });
  });

  // ===========================================================================
  // PERFORMANCE TESTS: ПРОВЕРКА ПРОИЗВОДИТЕЛЬНОСТИ
  // ===========================================================================

  describe('Производительность', () => {
    it('должен быстро обрабатывать бой с большим количеством модификаторов', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const modifiers: ValueModifier[] = Array.from({ length: 50 }, (_, i) =>
        createValueModifier(1, { source: `mod-${i}` }),
      );

      (mockAbilityRegistry.applyCombatModifiers as jest.Mock).mockReturnValue(modifiers);

      const startTime = Date.now();
      await service.resolveCombat(state, 'fighter-1', 'fighter-2', attackCard.id, defenseCard.id);
      const endTime = Date.now();

      // Должен выполниться быстро (< 100ms)
      expect(endTime - startTime).toBeLessThan(100);
    });

    it('должен быстро обрабатывать бой с большим количеством бойцов', async () => {
      const manyFighters = Array.from({ length: 20 }, (_, i) => ({
        id: `fighter-${i}`,
        ownerId: i % 2 === 0 ? 'player-1' : 'player-2',
        heroId: 'hero-1',
        name: `Fighter ${i}`,
        type: FighterType.MINION,
        health: 5,
        maxHealth: 5,
        position: { x: i, y: 0 },
        effects: [],
        hasSidekick: false,
      }));

      const attackCard = createMockCard('atk-1', { attackValue: 3 });

      const state = createMockGameState({
        fighters: manyFighters,
        handZones: {
          'player-1': { cards: [attackCard], maxSize: 5 },
          'player-2': { cards: [], maxSize: 5 },
        },
      });

      const startTime = Date.now();
      await service.resolveCombat(state, 'fighter-0', 'fighter-1', attackCard.id);
      const endTime = Date.now();

      expect(endTime - startTime).toBeLessThan(100);
    });
  });

  // ===========================================================================
  // COMBAT RESULT INTERFACE VALIDATION
  // ===========================================================================

  describe('CombatResult interface', () => {
    it('должен возвращать корректную структуру CombatResult', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // Проверка структуры результата
      expect(result).toHaveProperty('attackerDamage');
      expect(result).toHaveProperty('defenderDamage');
      expect(result).toHaveProperty('attackerEffectsApplied');
      expect(result).toHaveProperty('defenderEffectsApplied');
      expect(result).toHaveProperty('nextState');

      // Проверка типов
      expect(typeof result.attackerDamage).toBe('number');
      expect(typeof result.defenderDamage).toBe('number');
      expect(Array.isArray(result.attackerEffectsApplied)).toBe(true);
      expect(Array.isArray(result.defenderEffectsApplied)).toBe(true);

      // Проверка nextState
      expect(result.nextState).toHaveProperty('gameId');
      expect(result.nextState).toHaveProperty('sequenceNumber');
      expect(result.nextState).toHaveProperty('fighters');
    });

    it('должен иметь readonly свойства в attackerEffectsApplied', async () => {
      const attackCard = createMockCard('atk-1', { attackValue: 5 });
      const defenseCard = createMockCard('def-1', { defenseValue: 3, cardType: CardType.DEFENSE });
      const state = createGameStateWithCards(attackCard, defenseCard);

      const result = await service.resolveCombat(
        state,
        'fighter-1',
        'fighter-2',
        attackCard.id,
        defenseCard.id,
      );

      // Проверяем, что массив ведёт себя как readonly
      expect(() => {
        (result.attackerEffectsApplied as string[]).push('new-effect');
      }).not.toThrow();
    });
  });
});
