/**
 * Ability Configs — REAL-PATH integration spec (консолидация)
 *
 * Гоняет КАЖДЫЙ герой из ABILITY_CONFIGS через РЕАЛЬНЫЙ HeroAbilityRegistry +
 * РЕАЛЬНЫЙ GameActionExecutorService (продакшен-метод, который реально дёргает
 * соответствующий хук), с замоканной только персистентностью (deck/cardEffect/
 * movement/metrics/validator). Это та проводка, которую НЕ покрывают
 * handler/config-юнит-тесты:
 *   - ловит несовпадение слага (fighter.heroSlug != config.heroId → реестр мимо);
 *   - ловит незарегистрированного героя / пропуск в цикле регистрации;
 *   - ловит ситуацию «executor перестал звать хук»;
 *   - ловит баги суммирования stateful combat-модификаторов.
 *
 * Регистрация повторяет game-engine.module.ts onModuleInit ОДИН-В-ОДИН:
 * registry.registerExtended(new GenericHeroAbilityHandler(cfg, { deck, zone }))
 * для каждого ABILITY_CONFIGS + 3 хардкодных handler'а (daredevil/ms-marvel/
 * king-arthur) для зеркальности.
 *
 * Сетап модуля скопирован из game-action-executor.abilities-wiring.spec.ts с
 * ДВУМЯ отличиями: (1) draw-моки наблюдаемы (контракт добора), (2) после
 * compile() — цикл регистрации ABILITY_CONFIGS.
 */

import { Test, TestingModule } from '@nestjs/testing';
import { GameActionExecutorService, ActionContext } from '../services/game-action-executor.service';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { MovementService } from '../engine/movement.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { MetricsService } from '../../metrics/metrics.service';
import { DeckManagementService } from '../services/deck-management.service';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import { HeroAbilityRegistry } from './hero-ability-registry';
import { GenericHeroAbilityHandler } from './generic-hero-ability.handler';
import { ABILITY_CONFIGS } from './ability-config';
import { daredevilHandler, msMarvelHandler, arthurAbilityHandler } from './heroes';
import { FighterType, GamePhase } from '../models';
import type { GameState } from '../models';
import { ResolveCombatDto, EndTurnDto, AttackDto } from '../../games/dto/gameplay.dto';

describe('ABILITY_CONFIGS — real registry + real executor (consolidation)', () => {
  let service: GameActionExecutorService;
  let registry: HeroAbilityRegistry;
  // Наблюдаемый drawCards: один и тот же мок обслуживает И deps.deck handler'ов,
  // И deckManagement самого executor'а (advanceTurn добор следующему игроку).
  let drawCards: jest.Mock;

  /**
   * Наблюдаемый drawCards: добавляет N карт-болванок в руку игрока.
   * Может быть переопределён в тесте (bloody-mary — no-op, чтобы рука == 3).
   */
  const makeDrawCards = (): jest.Mock =>
    jest.fn(async (s: GameState, uid: string, n: number) => ({
      ...s,
      handZones: {
        ...s.handZones,
        [uid]: {
          ...s.handZones[uid],
          cards: [
            ...(s.handZones[uid]?.cards ?? []),
            ...Array.from({ length: n }, (_, i) => ({ id: `drawn-${uid}-${i}` })),
          ],
        },
      },
    }));

  /**
   * Базовое состояние с двумя ГЕРОЯМИ (FighterType.HERO — критично: hero/zone
   * предикаты GenericHeroAbilityHandler сравнивают с enum 'HERO', не 'hero').
   * heroSlug у бойцов проставляется per-test под нужный config.heroId.
   */
  const createMockGameState = (overrides?: Partial<GameState>): GameState =>
    ({
      gameId: 'test-game-1',
      sequenceNumber: 1,
      phase: GamePhase.TURN_START,
      turnCount: 1,
      currentTurnPlayerId: 'player1',
      players: [
        { userId: 'player1', heroId: 'cuid-hero-a', health: 14, maxHealth: 14, fighterIds: ['fighter1'], isAlive: true },
        { userId: 'player2', heroId: 'cuid-hero-b', health: 17, maxHealth: 17, fighterIds: ['fighter2'], isAlive: true },
      ],
      fighters: [
        {
          id: 'fighter1',
          ownerId: 'player1',
          heroId: 'cuid-hero-a',
          heroSlug: 'hero-a',
          name: 'Hero A',
          type: FighterType.HERO,
          health: 14,
          maxHealth: 14,
          position: { x: 5, y: 5 },
          effects: [],
          hasSidekick: false,
        },
        {
          id: 'fighter2',
          ownerId: 'player2',
          heroId: 'cuid-hero-b',
          heroSlug: 'hero-b',
          name: 'Hero B',
          type: FighterType.HERO,
          health: 17,
          maxHealth: 17,
          position: { x: 6, y: 5 },
          effects: [],
          hasSidekick: false,
        },
      ],
      decks: {},
      discardPiles: {},
      handZones: {
        player1: { cards: [], maxSize: 5 },
        player2: { cards: [], maxSize: 5 },
      },
      boardState: {
        width: 20,
        height: 20,
        cells: Array(20)
          .fill(null)
          .map(() => Array(20).fill(null).map(() => ({ type: 'normal' as const, x: 0, y: 0 }))) as any,
        doors: {} as any,
        fog: {} as any,
        tokens: {} as any,
      } as any,
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: 'player1',
        version: 1,
        actionsRemaining: 2,
      },
      ...overrides,
    }) as any;

  /** Удобный билдер контекста действия */
  const ctxFor = (userId: string, state: GameState): ActionContext => ({
    userId,
    gameId: 'test-game-1',
    currentState: state,
  });

  /** Проставить слаг герою-бойцу */
  const withHeroSlug = (state: GameState, fighterId: string, slug: string): GameState =>
    ({
      ...state,
      fighters: state.fighters.map((f) => (f.id === fighterId ? { ...f, heroSlug: slug } : f)),
    }) as GameState;

  beforeEach(async () => {
    drawCards = makeDrawCards();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameActionExecutorService,
        // РЕАЛЬНЫЙ реестр — на него вешаем РЕАЛЬНЫЕ GenericHeroAbilityHandler'ы
        HeroAbilityRegistry,
        // РЕАЛЬНЫЙ combat-resolver (классический combat-mods путь; конфиги идут
        // через stateful-путь, но держим реальный, как в wiring-спеке)
        CombatResolverService,
        {
          provide: GameRulesValidator,
          useValue: {
            validateManeuver: jest.fn().mockReturnValue({ valid: true }),
            validateMovement: jest.fn().mockReturnValue({ valid: true }),
            validateAttackWithParams: jest.fn().mockReturnValue({ valid: true }),
            validateDefense: jest.fn().mockReturnValue({ valid: true }),
            validateEndTurn: jest.fn().mockReturnValue({ valid: true }),
            validatePass: jest.fn().mockReturnValue({ valid: true }),
            validateToggleDoor: jest.fn().mockReturnValue({ valid: true }),
          },
        },
        { provide: MovementService, useValue: { executeMovement: jest.fn() } },
        { provide: ValueModifierService, useValue: { applyCardEffects: jest.fn() } },
        {
          provide: AdjacencyService,
          useValue: {
            isAdjacent: jest.fn().mockResolvedValue(true),
            // По умолчанию false (доска 20x20 без zone-меток): bigfoot «нет
            // врага в зоне» → TRUE, medusa «враг в зоне» → нет цели. Override→true.
            isInSameZone: jest.fn().mockReturnValue(false),
            manhattanDistance: jest.fn((a: { x: number; y: number }, b: { x: number; y: number }) =>
              Math.abs(a.x - b.x) + Math.abs(a.y - b.y),
            ),
            getReachableCells: jest.fn(),
          },
        },
        {
          provide: MetricsService,
          useValue: {
            measureServiceDuration: jest.fn((_n: string, _c: string, fn: () => any) => fn()),
            measureValidation: jest.fn((_n: string, fn: () => any) => fn()),
            measureCombat: jest.fn((_a: string, _d: string, fn: () => any) => fn()),
            incrementGameAction: jest.fn(),
            incrementError: jest.fn(),
          },
        },
        {
          provide: DeckManagementService,
          useValue: {
            // Наблюдаемый добор (контракт): и для executor.advanceTurn, и для
            // handler.deps.deck.drawCards. Переопределяется per-test через
            // drawCards.mockImplementation (bloody-mary — no-op).
            drawCards: (...args: [GameState, string, number]) => drawCards(...args),
            discardCard: jest.fn().mockImplementation((s: GameState) => Promise.resolve(s)),
          },
        },
        {
          provide: CardEffectExecutorService,
          useValue: {
            // Passthrough-пайплайн боя: финальные значения = значения из combatInfo,
            // base damage = attackValue - defenseValue.
            executeRevealEffects: jest.fn().mockImplementation((state: GameState) =>
              Promise.resolve({
                state,
                appliedEffects: [],
                manualEffects: [],
                attackerCardCancelled: false,
                defenderCardCancelled: false,
              }),
            ),
            executeCombatEffects: jest
              .fn()
              .mockImplementation((state: GameState, _a: unknown, _d: unknown, combat: any) =>
                Promise.resolve({
                  state,
                  finalAttack: combat.attackValue,
                  finalDefense: combat.defenseValue,
                  preventDamageToAttacker: false,
                  preventDamageToDefender: false,
                  appliedEffects: [],
                  manualEffects: [],
                }),
              ),
            executeAfterCombatEffects: jest.fn().mockImplementation((state: GameState) =>
              Promise.resolve({ state, appliedEffects: [], manualEffects: [] }),
            ),
          },
        },
      ],
    }).compile();

    service = module.get<GameActionExecutorService>(GameActionExecutorService);
    registry = module.get<HeroAbilityRegistry>(HeroAbilityRegistry);

    // === КОНСОЛИДАЦИЯ: повторяем цикл регистрации из onModuleInit ===
    const deck = module.get<DeckManagementService>(DeckManagementService);
    const zone = module.get<AdjacencyService>(AdjacencyService);
    for (const cfg of ABILITY_CONFIGS) {
      registry.registerExtended(new GenericHeroAbilityHandler(cfg, { deck, zone } as any));
    }
    // 3 хардкодных handler'а (НЕ из ABILITY_CONFIGS) — для зеркальности onModuleInit.
    registry.registerExtended(daredevilHandler);
    registry.registerExtended(msMarvelHandler);
    registry.register(arthurAbilityHandler);
  });

  afterEach(() => jest.clearAllMocks());

  // ====================================================================
  // САНИТИ: все 21 конфиг реально зарегистрированы под своими слагами
  // ====================================================================
  describe('registration', () => {
    it('каждый ABILITY_CONFIGS.heroId зарегистрирован в реестре под своим слагом', () => {
      for (const cfg of ABILITY_CONFIGS) {
        expect(registry.has(cfg.heroId)).toBe(true);
        expect(registry.getExtended(cfg.heroId)?.heroId).toBe(cfg.heroId);
      }
      expect(ABILITY_CONFIGS).toHaveLength(21);
    });
  });

  // ====================================================================
  // COMBAT-PASSIVE (executeResolveCombat; phase COMBAT_RESOLVE;
  // actionsRemaining:1 → ход НЕ авто-завершается, next-player turn-start не палит)
  // ====================================================================
  describe('combat-passive (getStatefulCombatModifiers через executeResolveCombat)', () => {
    const combatState = (
      overrides: { metadata?: any } & Partial<GameState>,
      combat: { attackValue: number; defenseValue: number },
    ): GameState => {
      const { metadata: metaOverride, ...rest } = overrides;
      return createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
        currentTurnPlayerId: 'player1',
        ...(rest as Partial<GameState>),
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 1,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a',
            defenderCardId: 'card-d',
            attackValue: combat.attackValue,
            defenseValue: combat.defenseValue,
            startedAt: new Date(),
          },
          ...(metaOverride ?? {}),
        } as any,
      });
    };

    it('luke-cage (defender, +2 defense): защитник получает на 2 урона меньше', async () => {
      // hero на ЗАЩИТНИКЕ (fighter2). atk5/def1 → база урона 4, +2 защиты → урон 2.
      let state = combatState({}, { attackValue: 5, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter2', 'luke-cage');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.metadata?.combatSummary?.finalDefense).toBe(3); // 1 + 2
      expect(result.metadata?.combatSummary?.defenderDamage).toBe(2); // 5 - 3
      const defender = result.gameState!.fighters.find((f) => f.id === 'fighter2')!;
      expect(defender.health).toBe(17 - 2);
    });

    // annie-christmas: REAL-PATH БАГ, НАЙДЕННЫЙ КОНСОЛИДАЦИЕЙ И ПОЧИНЕННЫЙ.
    // Раньше handler резолвил защитника как state.fighters.find(f.id ===
    // context.defenderId), а продакшен-combatInfo.defenderId = target.ownerId
    // (id ИГРОКА 'player2', не бойца) → defender не находился → +2 не применялся
    // в реальной игре. Фикс: handler берёт combatInfo.targetFighterId
    // ('fighter2') ?? defenderId; registry CombatState получил targetFighterId.
    // Теперь условие срабатывает через настоящий executeResolveCombat.
    it('annie-christmas (executor real-path): +2 attack когда hp < defender', async () => {
      let state = combatState({}, { attackValue: 4, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'annie-christmas');
      state = {
        ...state,
        fighters: state.fighters.map((f) => (f.id === 'fighter1' ? { ...f, health: 5 } : f)),
      } as GameState;

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      // annie hp 5 < defender (fighter2) hp 17 → +2 к атаке (4 → 6).
      expect(result.metadata?.combatSummary?.finalAttack).toBe(6);
    });

    it('annie-christmas (registry dispatch fallback): +2 attack когда defenderId = fighter id', () => {
      // Фолбэк: если targetFighterId не задан, handler берёт defenderId как id
      // бойца. atk hp 5 < def hp 17 → ADD +2.
      let state = combatState({}, { attackValue: 4, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'annie-christmas');
      state = {
        ...state,
        fighters: state.fighters.map((f) => (f.id === 'fighter1' ? { ...f, health: 5 } : f)),
      } as GameState;
      const attacker = state.fighters.find((f) => f.id === 'fighter1')!;

      const mods = registry.getStatefulCombatModifiers(
        'annie-christmas',
        state,
        { attackerId: 'fighter1', defenderId: 'fighter2' },
        attacker,
        'attacker',
      );

      const total = mods.reduce((s, m) => s + m.value, 0);
      expect(total).toBe(2);
    });

    it('eredin (attacker, +1 both если ВСЕ свои сайдкики повержены)', async () => {
      // ATTACKER fighter1 + один MINION player1 isDefeated:true → бонус +1/+1.
      let state = combatState({}, { attackValue: 4, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'eredin');
      state = {
        ...state,
        fighters: [
          ...state.fighters,
          {
            id: 'minion1',
            ownerId: 'player1',
            heroId: 'cuid-hero-a',
            heroSlug: 'eredin',
            name: 'Red Rider',
            type: FighterType.MINION,
            health: 0,
            maxHealth: 2,
            position: { x: 4, y: 5 },
            effects: [],
            hasSidekick: false,
            isDefeated: true,
          } as any,
        ],
      } as GameState;

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.metadata?.combatSummary?.finalAttack).toBe(5); // 4 + 1
    });

    it('eredin (negative): БЕЗ сайдкиков бонус не выдаётся (length===0 guard)', async () => {
      // У player1 только герой, сайдкиков нет → allOwnSidekicksDefeated=false.
      let state = combatState({}, { attackValue: 4, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'eredin');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.metadata?.combatSummary?.finalAttack).toBe(4); // без бонуса
    });

    it('golden-bat (attacker, +2 attack если ещё НЕ маневрировал в этом ходу)', async () => {
      // maneuveredThisTurn falsy → +2.
      let state = combatState({}, { attackValue: 4, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'golden-bat');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.metadata?.combatSummary?.finalAttack).toBe(6); // 4 + 2
    });

    it('golden-bat (negative): уже маневрировал → бонуса нет', async () => {
      let state = combatState({ metadata: { maneuveredThisTurn: true } as any }, { attackValue: 4, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'golden-bat');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.metadata?.combatSummary?.finalAttack).toBe(4); // без бонуса
    });

    it('ancient-leshen (attacker, +3 attack если уже атаковал в этом ходу)', async () => {
      // attackedThisTurn ПРЕД-выставлен → +3.
      let state = combatState({ metadata: { attackedThisTurn: true } as any }, { attackValue: 4, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'ancient-leshen');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.metadata?.combatSummary?.finalAttack).toBe(7); // 4 + 3
    });
  });

  // ====================================================================
  // TURN-START (executeEndTurn player1 → НОВЫЙ активный player2; hero на
  // player2 fighter2; actionsRemaining:0). advanceTurn добирает 1 карту
  // player2 ДО turn-start хука.
  // ====================================================================
  describe('turn-start (onTurnStart через executeEndTurn → новый активный игрок)', () => {
    const endTurnState = (overrides?: Partial<GameState>): GameState =>
      createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 0,
        } as any,
        ...overrides,
      });

    it('bloody-mary (+1 действие если в руке ровно 3 карты на момент хука)', async () => {
      // drawCards делаем no-op, чтобы advanceTurn не сломал размер руки player2 == 3.
      drawCards.mockImplementation(async (s: GameState) => s);
      let state = endTurnState({
        handZones: {
          player1: { cards: [], maxSize: 5 },
          player2: { cards: [{ id: 'h1' }, { id: 'h2' }, { id: 'h3' }], maxSize: 5 },
        } as any,
      });
      state = withHeroSlug(state, 'fighter2', 'bloody-mary');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.currentTurnPlayerId).toBe('player2');
      // ACTIONS_PER_TURN(2) + 1 (gainAction) = 3
      expect((result.gameState!.metadata as any).actionsRemaining).toBe(3);
    });

    it('leonardo (pending-move any-own value 1, без fighterName)', async () => {
      let state = endTurnState();
      state = withHeroSlug(state, 'fighter2', 'leonardo');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      const pending = (result.gameState!.metadata as any).pendingEffects ?? [];
      const move = pending.find((p: any) => p.type === 'MOVE' && p.playerId === 'player2');
      expect(move).toBeDefined();
      expect(move.value).toBe(1);
      expect(move.targetsOpponent).toBe(false);
      expect(move.fighterName).toBeUndefined(); // any-own → имя опущено
    });

    it('dracula (turn-damage смежному врагу 1 + добор 1)', async () => {
      // fighter2 (player2) HERO в (6,5); враг fighter1 в (5,5) → manhattan 1 (смежны).
      let state = endTurnState();
      state = withHeroSlug(state, 'fighter2', 'dracula');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      const victim = result.gameState!.fighters.find((f) => f.id === 'fighter1')!;
      expect(victim.health).toBe(14 - 1); // укус 1
      // добор: advanceTurn(+1 player2) + thenDraw(+1 player2) = 2 карты в руке player2
      expect(result.gameState!.handZones.player2.cards.length).toBe(2);
    });

    it('medusa (turn-damage врагу В ЗОНЕ 1 — при isInSameZone=true)', async () => {
      const adjacency = (service as any).adjacencyService;
      adjacency.isInSameZone.mockReturnValue(true);
      let state = endTurnState();
      state = withHeroSlug(state, 'fighter2', 'medusa');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      const victim = result.gameState!.fighters.find((f) => f.id === 'fighter1')!;
      expect(victim.health).toBe(14 - 1);
    });

    it('medusa (negative): isInSameZone=false → нет цели → no-op (урон не нанесён)', async () => {
      // default isInSameZone=false → в зоне нет врага.
      let state = endTurnState();
      state = withHeroSlug(state, 'fighter2', 'medusa');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      const victim = result.gameState!.fighters.find((f) => f.id === 'fighter1')!;
      expect(victim.health).toBe(14); // без урона
    });
  });

  // ====================================================================
  // TURN-END (executeEndTurn player1 → ЗАВЕРШАЮЩИЙ player1; hero на player1
  // fighter1; actionsRemaining:0). onTurnEnd бьёт у ЗАВЕРШАЮЩЕГО ДО переключения.
  // ====================================================================
  describe('turn-end (onTurnEnd через executeEndTurn → завершающий игрок)', () => {
    const endTurnState = (overrides?: Partial<GameState>): GameState =>
      createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 0,
        } as any,
        ...overrides,
      });

    it('philippa (drawToHandSize 4): рука player1 1→4', async () => {
      let state = endTurnState({
        handZones: {
          player1: { cards: [{ id: 'h1' }], maxSize: 5 },
          player2: { cards: [], maxSize: 5 },
        } as any,
      });
      state = withHeroSlug(state, 'fighter1', 'philippa');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      // онTurnEnd завершающего player1 добирает до 4 (дефицит 3) ДО передачи хода.
      expect(result.gameState!.handZones.player1.cards.length).toBe(4);
    });

    it('t-rex (draw 1 в конце хода): рука player1 +1', async () => {
      let state = endTurnState({
        handZones: {
          player1: { cards: [{ id: 'h1' }], maxSize: 5 },
          player2: { cards: [], maxSize: 5 },
        } as any,
      });
      state = withHeroSlug(state, 'fighter1', 't-rex');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.handZones.player1.cards.length).toBe(2); // 1 + 1
    });

    it('bigfoot (draw 1 если в зоне НЕТ врага — default isInSameZone=false)', async () => {
      let state = endTurnState({
        handZones: {
          player1: { cards: [{ id: 'h1' }], maxSize: 5 },
          player2: { cards: [], maxSize: 5 },
        } as any,
      });
      state = withHeroSlug(state, 'fighter1', 'bigfoot');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.handZones.player1.cards.length).toBe(2); // 1 + 1
    });

    it('bigfoot (negative): враг В ЗОНЕ (isInSameZone=true) → добора нет', async () => {
      const adjacency = (service as any).adjacencyService;
      adjacency.isInSameZone.mockReturnValue(true);
      let state = endTurnState({
        handZones: {
          player1: { cards: [{ id: 'h1' }], maxSize: 5 },
          player2: { cards: [], maxSize: 5 },
        } as any,
      });
      state = withHeroSlug(state, 'fighter1', 'bigfoot');

      const result = await service.executeEndTurn({ gameId: 'test-game-1' } as EndTurnDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.handZones.player1.cards.length).toBe(1); // без добора
    });
  });

  // ====================================================================
  // AFTER-ATTACK (executeResolveCombat; attacker player1 fighter1;
  // actionsRemaining:1 → ход продолжается, urgent next-turn-start не палит)
  // ====================================================================
  describe('after-attack (onAfterCombat через executeResolveCombat → атакующий)', () => {
    const afterAttackState = (
      combat: { attackValue: number; defenseValue: number },
      overrides?: { metadata?: any; fighter1?: Partial<any> },
    ): GameState => {
      let s = createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 1,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a',
            defenderCardId: 'card-d',
            attackValue: combat.attackValue,
            defenseValue: combat.defenseValue,
            startedAt: new Date(),
          },
          ...(overrides?.metadata ?? {}),
        } as any,
      });
      if (overrides?.fighter1) {
        s = {
          ...s,
          fighters: s.fighters.map((f) => (f.id === 'fighter1' ? { ...f, ...overrides.fighter1 } : f)),
        } as GameState;
      }
      return s;
    };

    it('chupacabra (draw 1 всегда после своей атаки)', async () => {
      let state = afterAttackState({ attackValue: 5, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'chupacabra');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.handZones.player1.cards.length).toBe(1); // +1 атакующему
    });

    it('deadpool (heal 1 всегда; atk==def → урона нет, проверяем чистый heal)', async () => {
      // fighter1 health 10/max14, atk==def (ничья, атакующий не получает урон) → heal 11.
      let state = afterAttackState({ attackValue: 3, defenseValue: 3 }, { fighter1: { health: 10 } });
      state = withHeroSlug(state, 'fighter1', 'deadpool');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      const hero = result.gameState!.fighters.find((f) => f.id === 'fighter1')!;
      expect(hero.health).toBe(11); // 10 + 1
    });

    it('michelangelo (draw 1 всегда после своей атаки)', async () => {
      let state = afterAttackState({ attackValue: 5, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'michelangelo');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.handZones.player1.cards.length).toBe(1);
    });

    it('angel (draw 1 ТОЛЬКО при проигрыше): atk1/def3 → проигрыш → +1', async () => {
      let state = afterAttackState({ attackValue: 1, defenseValue: 3 });
      state = withHeroSlug(state, 'fighter1', 'angel');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.handZones.player1.cards.length).toBe(1);
    });

    it('angel (negative): победа → добора нет', async () => {
      let state = afterAttackState({ attackValue: 5, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'angel');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect(result.gameState!.handZones.player1.cards.length).toBe(0); // без добора
    });

    it('raphael (+1 действие при ПЕРВОМ проигрыше хода): atk1/def3, lostCombatThisTurn unset', async () => {
      // actionsRemaining 1 → ход продолжается; gainAction +1 → видим прирост.
      let state = afterAttackState({ attackValue: 1, defenseValue: 3 });
      state = withHeroSlug(state, 'fighter1', 'raphael');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      // base actionsRemaining 1 + gainAction 1 = 2 (ход остался у player1, продолжается)
      expect((result.gameState!.metadata as any).actionsRemaining).toBe(2);
      expect(result.gameState!.currentTurnPlayerId).toBe('player1');
    });

    it('raphael (negative): НЕ первый проигрыш (lostCombatThisTurn=true) → без +действия', async () => {
      let state = afterAttackState({ attackValue: 1, defenseValue: 3 }, { metadata: { lostCombatThisTurn: true } });
      state = withHeroSlug(state, 'fighter1', 'raphael');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      expect((result.gameState!.metadata as any).actionsRemaining).toBe(1); // без прироста
    });

    it('robin-hood (pending-move атаковавшего бойца value 2 с fighterName)', async () => {
      let state = afterAttackState({ attackValue: 5, defenseValue: 1 });
      state = withHeroSlug(state, 'fighter1', 'robin-hood');

      const result = await service.executeResolveCombat({ gameId: 'test-game-1' } as ResolveCombatDto, ctxFor('player1', state));

      expect(result.success).toBe(true);
      const pending = (result.gameState!.metadata as any).pendingEffects ?? [];
      const move = pending.find((p: any) => p.type === 'MOVE' && p.playerId === 'player1');
      expect(move).toBeDefined();
      expect(move.value).toBe(2);
      expect(move.targetsOpponent).toBe(false);
      expect(move.fighterName).toBe('Hero A'); // имя атаковавшего (fighter1)
    });
  });

  // ====================================================================
  // ATTACK-RANGE (executeAttack; phase ACTION_MANEUVER; isAdjacent/isInSameZone
  // false; позиции по manhattan; actionsRemaining:2). canAttackAtRange.
  // ====================================================================
  describe('attackRange (canAttackAtRange через executeAttack)', () => {
    const placeAt = (state: GameState, f1: { x: number; y: number }, f2: { x: number; y: number }): GameState =>
      ({
        ...state,
        fighters: state.fighters.map((f) =>
          f.id === 'fighter1' ? { ...f, position: f1 } : f.id === 'fighter2' ? { ...f, position: f2 } : f,
        ),
      }) as GameState;

    const rangeState = (slug: string, dist: number): GameState => {
      let s = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 2,
        } as any,
      });
      s = withHeroSlug(s, 'fighter1', slug);
      // attacker (5,5); target (5+dist,5) → manhattan == dist
      s = placeAt(s, { x: 5, y: 5 }, { x: 5 + dist, y: 5 });
      return s;
    };

    const attackDto: AttackDto = {
      gameId: 'test-game-1',
      attackerId: 'fighter1',
      targetId: 'fighter2',
      cardId: 'card-a',
    } as AttackDto;

    beforeEach(() => {
      const adjacency = (service as any).adjacencyService;
      adjacency.isAdjacent.mockResolvedValue(false);
      adjacency.isInSameZone.mockReturnValue(false);
    });

    it('t-rex (range 2): дистанция 2 → атака РАЗРЕШЕНА (бой объявлен)', async () => {
      const result = await service.executeAttack(attackDto, ctxFor('player1', rangeState('t-rex', 2)));

      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
      expect(result.gameState!.phase).toBe(GamePhase.COMBAT);
      expect((result.gameState!.metadata as any).combatInfo?.attackerId).toBe('fighter1');
      expect((result.gameState!.metadata as any).combatInfo?.targetFighterId).toBe('fighter2');
    });

    it('t-rex (range 2): дистанция 3 → ОТКЛОНЕНО', async () => {
      const result = await service.executeAttack(attackDto, ctxFor('player1', rangeState('t-rex', 3)));

      expect(result.success).toBe(false);
      expect(result.gameState).toBeUndefined();
    });

    it('bullseye (range 5): дистанция 5 → атака РАЗРЕШЕНА', async () => {
      const result = await service.executeAttack(attackDto, ctxFor('player1', rangeState('bullseye', 5)));

      expect(result.success).toBe(true);
      expect(result.gameState!.phase).toBe(GamePhase.COMBAT);
      expect((result.gameState!.metadata as any).combatInfo?.attackerId).toBe('fighter1');
    });

    it('bullseye (range 5): дистанция 6 → ОТКЛОНЕНО', async () => {
      const result = await service.executeAttack(attackDto, ctxFor('player1', rangeState('bullseye', 6)));

      expect(result.success).toBe(false);
      expect(result.gameState).toBeUndefined();
    });
  });
});
