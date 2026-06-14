/**
 * Game Action Executor — Abilities Wiring Tests (infra-фаза)
 *
 * Проверяет два продакшен-хука, которые нужны generic-фреймворку способностей:
 *
 *  1. STATEFUL combat modifiers: extended-handler может вернуть
 *     ValueModifier[] на основе GameState (которого классический
 *     applyCombatModifier не видит) — и их ADD-сумма попадает в урон боя.
 *
 *  2. TURN-END extended-хук: при передаче хода у ЗАВЕРШАЮЩЕГО игрока
 *     вызывается onTurnEnd ДО переключения currentTurnPlayerId, ход всё
 *     равно переходит следующему игроку в фазу ACTION_MANEUVER.
 *
 * Здесь намеренно используются РЕАЛЬНЫЕ HeroAbilityRegistry и
 * CombatResolverService (а не моки), чтобы проверить реальную проводку.
 */

import { Test, TestingModule } from '@nestjs/testing';
import { GameActionExecutorService, ActionContext } from './game-action-executor.service';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { MovementService } from '../engine/movement.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { MetricsService } from '../../metrics/metrics.service';
import { DeckManagementService } from './deck-management.service';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import {
  HeroAbilityRegistry,
  ExtendedHeroAbilityHandler,
  ValueModifier,
  ValueModifierType,
} from '../abilities/hero-ability-registry';
import { GamePhase } from '../models';
import type { GameState } from '../models';
import { ResolveCombatDto, EndTurnDto, ManeuverDto, AttackDto } from '../../games/dto/gameplay.dto';

describe('GameActionExecutorService — abilities wiring', () => {
  let service: GameActionExecutorService;
  let registry: HeroAbilityRegistry;

  /** Базовое тестовое состояние с двумя героями (слаги hero-a / hero-b) */
  const createMockGameState = (overrides?: Partial<GameState>): GameState =>
    ({
      gameId: 'test-game-1',
      sequenceNumber: 1,
      phase: GamePhase.TURN_START,
      turnCount: 1,
      currentTurnPlayerId: 'player1',
      players: [
        {
          userId: 'player1',
          heroId: 'cuid-hero-a',
          health: 14,
          maxHealth: 14,
          fighterIds: ['fighter1'],
          isAlive: true,
        },
        {
          userId: 'player2',
          heroId: 'cuid-hero-b',
          health: 17,
          maxHealth: 17,
          fighterIds: ['fighter2'],
          isAlive: true,
        },
      ],
      fighters: [
        {
          id: 'fighter1',
          ownerId: 'player1',
          heroId: 'cuid-hero-a',
          heroSlug: 'hero-a',
          name: 'Hero A',
          type: 'hero' as any,
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
          type: 'hero' as any,
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

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameActionExecutorService,
        // РЕАЛЬНЫЙ реестр — на него вешаем fake extended-handlers
        HeroAbilityRegistry,
        // РЕАЛЬНЫЙ combat-resolver — реальный путь getHeroCombatModifiers
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
        {
          provide: MovementService,
          useValue: { executeMovement: jest.fn() },
        },
        {
          provide: ValueModifierService,
          useValue: { applyCardEffects: jest.fn() },
        },
        {
          provide: AdjacencyService,
          useValue: {
            isAdjacent: jest.fn().mockResolvedValue(true),
            isInSameZone: jest.fn().mockReturnValue(false),
            // Реальная манхэттенская дистанция — нужна для extended-range gate
            manhattanDistance: jest.fn((a: { x: number; y: number }, b: { x: number; y: number }) =>
              Math.abs(a.x - b.x) + Math.abs(a.y - b.y),
            ),
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
            drawCards: jest.fn().mockImplementation((state: GameState) => Promise.resolve(state)),
            discardCard: jest.fn().mockImplementation((state: GameState) => Promise.resolve(state)),
          },
        },
        {
          provide: CardEffectExecutorService,
          useValue: {
            // Passthrough-пайплайн боя: финальные значения = значения из combatInfo
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
  });

  afterEach(() => jest.clearAllMocks());

  describe('1) stateful combat modifiers', () => {
    it('getStatefulCombatModifiers атакующего (+5 ADD) попадает в урон боя', async () => {
      // Fake extended-handler атакующего: +5 к атаке, читая GameState
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'Stateful +5',
        abilityDescription: 'тестовый stateful-модификатор',
        getStatefulCombatModifiers: (
          state: GameState,
          _context,
          _fighter,
          role,
        ): readonly ValueModifier[] => {
          // условие на GameState (которое классический хук увидеть не может)
          if (role === 'attacker' && state.fighters.length >= 2) {
            return [
              {
                type: ValueModifierType.ADD,
                value: 5,
                source: 'fake-stateful',
                timestamp: Date.now(),
                ownerId: 'player1',
              },
            ];
          }
          return [];
        },
      };
      registry.registerExtended(fakeHandler);

      // Бой: атака 4 vs защита 1 → база урона 3; +5 stateful → урон 8
      const state = createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
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
            attackValue: 4,
            defenseValue: 1,
            startedAt: new Date(),
          },
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as ResolveCombatDto,
        context,
      );

      expect(result.success).toBe(true);
      // finalAttack = 4 + 5(stateful) = 9, finalDefense = 1 → defenderDamage = 8
      expect(result.metadata?.combatSummary?.finalAttack).toBe(9);
      expect(result.metadata?.combatSummary?.defenderDamage).toBe(8);
      const defender = result.gameState!.fighters.find((f) => f.id === 'fighter2')!;
      expect(defender.health).toBe(17 - 8);
    });
  });

  describe('3) after-combat extended hook', () => {
    it('onAfterCombat атакующего срабатывает после резолва (won=true), бой и ход проходят нормально', async () => {
      // Fake extended-handler атакующего (player1 / hero-a): ставит маркер в
      // metadata с исходом боя, читая ctx.won
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'AfterCombat marker',
        abilityDescription: 'ставит маркер в metadata после боя',
        onAfterCombat: (state: GameState, ctx): Promise<GameState> =>
          Promise.resolve({
            ...state,
            metadata: {
              ...state.metadata,
              fakeAfterCombatMarker: ctx.won ? 'won' : 'lost',
              fakeAfterCombatDamage: ctx.damageDealt,
              fakeAfterCombatAttacker: ctx.attackerFighterId,
              fakeAfterCombatDefender: ctx.defenderFighterId,
              fakeAfterCombatPlayer: ctx.playerId,
            } as any,
          }),
      };
      registry.registerExtended(fakeHandler);

      // Бой: атака 5 vs защита 1 → атакующий побеждает, урон 4, ход
      // авто-завершается (actionsRemaining=0) → переходит player2
      const state = createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 0,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a',
            defenderCardId: 'card-d',
            attackValue: 5,
            defenseValue: 1,
            startedAt: new Date(),
          },
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as ResolveCombatDto,
        context,
      );

      expect(result.success).toBe(true);
      // after-combat хук атакующего сработал с won=true и корректным контекстом
      expect((result.gameState!.metadata as any).fakeAfterCombatMarker).toBe('won');
      expect((result.gameState!.metadata as any).fakeAfterCombatDamage).toBe(4);
      expect((result.gameState!.metadata as any).fakeAfterCombatAttacker).toBe('fighter1');
      expect((result.gameState!.metadata as any).fakeAfterCombatDefender).toBe('fighter2');
      expect((result.gameState!.metadata as any).fakeAfterCombatPlayer).toBe('player1');
      // бой разрешён нормально: урон применён, combatInfo очищен
      const defender = result.gameState!.fighters.find((f) => f.id === 'fighter2')!;
      expect(defender.health).toBe(17 - 4);
      expect((result.gameState!.metadata as any).combatInfo).toBeUndefined();
      // ход авто-завершился и перешёл следующему игроку
      expect(result.gameState!.currentTurnPlayerId).toBe('player2');
      expect(result.gameState!.phase).toBe(GamePhase.ACTION_MANEUVER);
    });

    it('onAfterCombat получает won=false на ничьей/проигрыше атакующего', async () => {
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'AfterCombat marker',
        abilityDescription: 'ставит маркер в metadata после боя',
        onAfterCombat: (state: GameState, ctx): Promise<GameState> =>
          Promise.resolve({
            ...state,
            metadata: {
              ...state.metadata,
              fakeAfterCombatMarker: ctx.won ? 'won' : 'lost',
            } as any,
          }),
      };
      registry.registerExtended(fakeHandler);

      // Ничья: атака 2 vs защита 2 → защитник побеждает (won=false), урона нет
      const state = createMockGameState({
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
            attackValue: 2,
            defenseValue: 2,
            startedAt: new Date(),
          },
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as ResolveCombatDto,
        context,
      );

      expect(result.success).toBe(true);
      expect((result.gameState!.metadata as any).fakeAfterCombatMarker).toBe('lost');
      // атакующий не выиграл → урона защитнику нет
      const defender = result.gameState!.fighters.find((f) => f.id === 'fighter2')!;
      expect(defender.health).toBe(17);
    });
  });

  describe('4) per-turn action flags', () => {
    it('после манёвра metadata.maneuveredThisTurn === true', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 2, // остаётся 1 действие после манёвра — ход не завершается
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeManeuver(
        {
          gameId: 'test-game-1',
          moves: [{ fighterId: 'fighter1', path: [{ x: 6, y: 6 }] }],
        } as ManeuverDto,
        context,
      );

      expect(result.success).toBe(true);
      // ход не завершился (осталось 1 действие) → флаг манёвра выставлен
      expect((result.gameState!.metadata as any).maneuveredThisTurn).toBe(true);
    });

    it('после передачи хода флаги сбрасываются в false для нового игрока', async () => {
      // у player1 уже выставлены все флаги — endTurn передаёт ход player2 и сбрасывает их
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 0,
          maneuveredThisTurn: true,
          attackedThisTurn: true,
          lostCombatThisTurn: true,
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeEndTurn(
        { gameId: 'test-game-1' } as EndTurnDto,
        context,
      );

      expect(result.success).toBe(true);
      expect(result.gameState!.currentTurnPlayerId).toBe('player2');
      expect((result.gameState!.metadata as any).maneuveredThisTurn).toBe(false);
      expect((result.gameState!.metadata as any).attackedThisTurn).toBe(false);
      expect((result.gameState!.metadata as any).lostCombatThisTurn).toBe(false);
    });

    it('после проигранного боя ctx.firstLossThisTurn === true (первый проигрыш хода)', async () => {
      let capturedFirstLoss: boolean | undefined;
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'AfterCombat firstLoss capture',
        abilityDescription: 'фиксирует ctx.firstLossThisTurn',
        onAfterCombat: (state: GameState, ctx): Promise<GameState> => {
          capturedFirstLoss = (ctx as any).firstLossThisTurn;
          return Promise.resolve(state);
        },
      };
      registry.registerExtended(fakeHandler);

      // Проигрыш атакующего: атака 1 vs защита 3 → won=false, первый проигрыш хода
      const state = createMockGameState({
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
            attackValue: 1,
            defenseValue: 3,
            startedAt: new Date(),
          },
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as ResolveCombatDto,
        context,
      );

      expect(result.success).toBe(true);
      expect(capturedFirstLoss).toBe(true);
      // флаг lostCombatThisTurn выставлен после боя
      expect((result.gameState!.metadata as any).lostCombatThisTurn).toBe(true);
    });

    it('второй проигрыш того же хода: ctx.firstLossThisTurn === false', async () => {
      let capturedFirstLoss: boolean | undefined;
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'AfterCombat firstLoss capture',
        abilityDescription: 'фиксирует ctx.firstLossThisTurn',
        onAfterCombat: (state: GameState, ctx): Promise<GameState> => {
          capturedFirstLoss = (ctx as any).firstLossThisTurn;
          return Promise.resolve(state);
        },
      };
      registry.registerExtended(fakeHandler);

      // lostCombatThisTurn УЖЕ true (был проигрыш ранее в этом ходу)
      const state = createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 1,
          lostCombatThisTurn: true,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a',
            defenderCardId: 'card-d',
            attackValue: 1,
            defenseValue: 3,
            startedAt: new Date(),
          },
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as ResolveCombatDto,
        context,
      );

      expect(result.success).toBe(true);
      expect(capturedFirstLoss).toBe(false);
    });

    it('второй атака того же хода видит attackedThisTurn===true на этапе сбора модификаторов', async () => {
      // getStatefulCombatModifiers фиксирует значение attackedThisTurn НА МОМЕНТ
      // сбора модификаторов. Первая атака должна видеть false, вторая — true.
      const seen: Array<boolean | undefined> = [];
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'records attackedThisTurn',
        abilityDescription: 'фиксирует флаг атаки на этапе модификаторов',
        getStatefulCombatModifiers: (state: GameState, _c, _f, role): readonly ValueModifier[] => {
          if (role === 'attacker') {
            seen.push((state.metadata as any).attackedThisTurn);
          }
          return [];
        },
      };
      registry.registerExtended(fakeHandler);

      const baseCombatInfo = {
        attackerId: 'fighter1',
        defenderId: 'player2',
        targetFighterId: 'fighter2',
        attackerCardId: 'card-a',
        defenderCardId: 'card-d',
        attackValue: 5,
        defenseValue: 1,
        startedAt: new Date(),
      };

      // Первая атака — attackedThisTurn ещё не выставлен
      const state1 = createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 1, // ход продолжается
          combatInfo: baseCombatInfo,
        } as any,
      });

      const r1 = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as ResolveCombatDto,
        { userId: 'player1', gameId: 'test-game-1', currentState: state1 },
      );
      expect(r1.success).toBe(true);
      // после первой атаки флаг выставлен в state
      expect((r1.gameState!.metadata as any).attackedThisTurn).toBe(true);

      // Вторая атака того же хода — флаг уже true на момент сбора модификаторов
      const state2 = createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 1,
          attackedThisTurn: true,
          combatInfo: baseCombatInfo,
        } as any,
      });

      const r2 = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as ResolveCombatDto,
        { userId: 'player1', gameId: 'test-game-1', currentState: state2 },
      );
      expect(r2.success).toBe(true);

      // seen[0] — первая атака (false/undefined), seen[1] — вторая (true)
      expect(seen[0]).toBeFalsy();
      expect(seen[1]).toBe(true);
    });
  });

  describe('2) turn-end extended hook', () => {
    it('onTurnEnd завершающего игрока срабатывает, ход переходит следующему', async () => {
      // Fake extended-handler завершающего игрока (player1 / hero-a)
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'TurnEnd marker',
        abilityDescription: 'ставит маркер в metadata при конце хода',
        onTurnEnd: (state: GameState, playerId: string): Promise<GameState> =>
          Promise.resolve({
            ...state,
            metadata: {
              ...state.metadata,
              // маркер с id игрока, у которого закончился ход
              fakeTurnEndMarker: playerId,
            } as any,
          }),
      };
      registry.registerExtended(fakeHandler);

      const state = createMockGameState({ phase: GamePhase.ACTION_MANEUVER });
      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeEndTurn(
        { gameId: 'test-game-1' } as EndTurnDto,
        context,
      );

      expect(result.success).toBe(true);
      // onTurnEnd завершающего (player1) сработал
      expect((result.gameState!.metadata as any).fakeTurnEndMarker).toBe('player1');
      // ход всё равно перешёл player2 в ACTION_MANEUVER
      expect(result.gameState!.currentTurnPlayerId).toBe('player2');
      expect(result.gameState!.phase).toBe(GamePhase.ACTION_MANEUVER);
    });
  });

  describe('5) turn-start ability deals lethal damage -> game over', () => {
    it('onTurnStart нового игрока добивает последнего героя противника -> phase GAME_OVER + winner', async () => {
      // Новый активный игрок после endTurn(player1) — player2 (hero-b).
      // Его onTurnStart наносит смертельный урон герою player1 (fighter1):
      // health=0 + isDefeated, player1.isAlive=false. advanceTurn должен
      // ПОСЛЕ хука пере-проверить game-over и завершить игру.
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-b',
        abilityName: 'TurnStart lethal',
        abilityDescription: 'добивает героя противника в начале хода',
        onTurnStart: (state: GameState, playerId: string): Promise<GameState> => {
          // playerId === 'player2' (новый активный); бьём чужого героя fighter1
          expect(playerId).toBe('player2');
          return Promise.resolve({
            ...state,
            fighters: state.fighters.map((f) =>
              f.id === 'fighter1' ? { ...f, health: 0, isDefeated: true } : f,
            ),
            players: state.players.map((p) =>
              p.userId === 'player1' ? { ...p, isAlive: false } : p,
            ),
          });
        },
      };
      registry.registerExtended(fakeHandler);

      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 0,
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeEndTurn(
        { gameId: 'test-game-1' } as EndTurnDto,
        context,
      );

      expect(result.success).toBe(true);
      // turn-start способность добила последнего героя player1 -> игра окончена
      expect(result.gameState!.phase).toBe(GamePhase.GAME_OVER);
      // победитель — единственный живой игрок (player2)
      expect((result.gameState!.metadata as any).winnerId).toBe('player2');
      // факт смерти зафиксирован
      const defeated = result.gameState!.fighters.find((f) => f.id === 'fighter1')!;
      expect(defeated.health).toBe(0);
      expect(defeated.isDefeated).toBe(true);
      expect(result.gameState!.players.find((p) => p.userId === 'player1')!.isAlive).toBe(false);
    });

    it('onTurnStart без смертей оставляет ход в ACTION_MANEUVER (нет ложного game-over)', async () => {
      // onTurnStart нового игрока (player2 / hero-b) ничего не убивает —
      // обычный переход хода должен завершиться ACTION_MANEUVER без GAME_OVER.
      const fakeHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-b',
        abilityName: 'TurnStart harmless',
        abilityDescription: 'лечит себя, никого не убивает',
        onTurnStart: (state: GameState): Promise<GameState> =>
          Promise.resolve({
            ...state,
            metadata: { ...state.metadata, fakeTurnStartMarker: 'ran' } as any,
          }),
      };
      registry.registerExtended(fakeHandler);

      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        currentTurnPlayerId: 'player1',
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 0,
        } as any,
      });

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeEndTurn(
        { gameId: 'test-game-1' } as EndTurnDto,
        context,
      );

      expect(result.success).toBe(true);
      // хук отработал, но игра НЕ окончена
      expect((result.gameState!.metadata as any).fakeTurnStartMarker).toBe('ran');
      expect(result.gameState!.phase).toBe(GamePhase.ACTION_MANEUVER);
      expect(result.gameState!.currentTurnPlayerId).toBe('player2');
      expect((result.gameState!.metadata as any).winnerId).toBeUndefined();
      // оба игрока живы
      expect(result.gameState!.players.every((p) => p.isAlive)).toBe(true);
    });
  });

  describe('6) extended attack range via registry.canAttackAtRange', () => {
    /**
     * Бойцы НЕ смежны и НЕ в одной зоне — обычный melee-герой атаковать не может.
     * AdjacencyService.isAdjacent → false, isInSameZone → false; дистанция = 3.
     * Атакующий fighter1 (5,5), цель fighter2 (8,5) → manhattan = 3.
     */
    const placeFarApart = (state: GameState): GameState =>
      ({
        ...state,
        fighters: state.fighters.map((f) =>
          f.id === 'fighter1'
            ? { ...f, position: { x: 5, y: 5 } }
            : f.id === 'fighter2'
              ? { ...f, position: { x: 8, y: 5 } }
              : f,
        ),
      }) as GameState;

    const attackState = (): GameState =>
      placeFarApart(
        createMockGameState({
          phase: GamePhase.ACTION_MANEUVER,
          currentTurnPlayerId: 'player1',
          metadata: {
            lastActionAt: new Date(),
            lastActionBy: 'player1',
            version: 1,
            actionsRemaining: 2,
          } as any,
        }),
      );

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

    it('герой с extended-range способностью (canAttackAtRange range<=3) АТАКУЕТ далёкую цель', async () => {
      // hero-a умеет бить на дистанцию <= 3
      const rangedHandler: ExtendedHeroAbilityHandler = {
        heroId: 'hero-a',
        abilityName: 'Extended range 3',
        abilityDescription: 'может атаковать на дистанции до 3 клеток',
        canAttackAtRange: (_attackerId: string, _defenderId: string, range: number): boolean =>
          range <= 3,
      };
      registry.registerExtended(rangedHandler);

      const result = await service.executeAttack(attackDto, {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: attackState(),
      });

      // Бой объявлен: нет ошибки «out of range», фаза COMBAT, combatInfo выставлен
      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
      expect(result.gameState!.phase).toBe(GamePhase.COMBAT);
      expect((result.gameState!.metadata as any).combatInfo?.attackerId).toBe('fighter1');
      expect((result.gameState!.metadata as any).combatInfo?.targetFighterId).toBe('fighter2');
    });

    it('обычный герой БЕЗ range-способности НЕ может атаковать далёкую цель (поведение сохранено)', async () => {
      // Никаких extended-handlers для hero-a не зарегистрировано
      const result = await service.executeAttack(attackDto, {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: attackState(),
      });

      expect(result.success).toBe(false);
      expect(result.error).toMatch(/adjacent/i);
      expect(result.gameState).toBeUndefined();
    });

    it('смежная melee-атака по-прежнему работает (extended gate ничего не ломает)', async () => {
      const adjacency = (service as any).adjacencyService;
      adjacency.isAdjacent.mockResolvedValue(true);

      const result = await service.executeAttack(attackDto, {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: attackState(),
      });

      expect(result.success).toBe(true);
      expect(result.gameState!.phase).toBe(GamePhase.COMBAT);
    });
  });
});
