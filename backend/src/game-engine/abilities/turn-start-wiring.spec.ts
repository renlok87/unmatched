/**
 * TURN_START Ability Wiring Tests (TASK A — infra only)
 *
 * Проверяют, что расширенные onTurnStart-хуки героев (ExtendedHeroAbilityHandler,
 * triggerOnTurnStartExtended → возвращает мутированный GameState) реально
 * вызываются в продакшен-потоке начала хода.
 *
 * Фаза TURN_START исключена из потока (ход сразу с ACTION_MANEUVER), поэтому
 * хук должен встраиваться в advanceTurn — единственную точку, где у игрока
 * начинается ход. Тест:
 *  1. Регистрирует ФЕЙКОВЫЙ extended-handler с onTurnStart, мутирующим
 *     детектируемое поле (metadata.fakeOnTurnStartMarker).
 *  2. Гоняет начало хода через продакшен-путь (executeEndTurn → advanceTurn).
 *  3. Утверждает, что мутация произошла И что ход всё ещё переходит в
 *     ACTION_MANEUVER (поток хода не сломан).
 */

import { Test, TestingModule } from '@nestjs/testing';
import {
  GameActionExecutorService,
  ActionContext,
} from '../services/game-action-executor.service';
import { GameRulesValidator } from '../validators/game-rules.validator';
import { CombatResolverService } from '../engine/combat-resolver.service';
import { MovementService } from '../engine/movement.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { MetricsService } from '../../metrics/metrics.service';
import { DeckManagementService } from '../services/deck-management.service';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import {
  HeroAbilityRegistry,
  ExtendedHeroAbilityHandler,
} from './hero-ability-registry';
import { GamePhase } from '../models';
import type { GameState } from '../models';
import { EndTurnDto } from '../../games/dto/gameplay.dto';

describe('TURN_START ability wiring (advanceTurn → triggerOnTurnStartExtended)', () => {
  let service: GameActionExecutorService;
  let registry: HeroAbilityRegistry;

  const createMockGameState = (overrides?: Partial<GameState>): GameState =>
    ({
      gameId: 'test-game-1',
      sequenceNumber: 1,
      phase: GamePhase.ACTION_MANEUVER,
      turnCount: 1,
      currentTurnPlayerId: 'player1',
      players: [
        {
          userId: 'player1',
          heroId: 'ms-marvel',
          health: 14,
          maxHealth: 14,
          fighterIds: ['fighter1'],
          isAlive: true,
        },
        {
          userId: 'player2',
          heroId: 'fake-hero',
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
          heroId: 'ms-marvel',
          heroSlug: 'ms-marvel',
          name: 'Ms. Marvel',
          type: 'HERO' as any,
          health: 14,
          maxHealth: 14,
          position: { x: 5, y: 5 },
          effects: [],
          hasSidekick: false,
        },
        {
          id: 'fighter2',
          ownerId: 'player2',
          heroId: 'fake-hero',
          heroSlug: 'fake-hero',
          name: 'Fake Hero',
          type: 'HERO' as any,
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
          .map(() =>
            Array(20)
              .fill(null)
              .map(() => ({ type: 'normal' as const, x: 0, y: 0 })),
          ) as any,
        doors: {} as any,
        fog: {} as any,
        tokens: {} as any,
      } as any,
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: 'player1',
        version: 1,
        actionsRemaining: 0,
      },
      ...overrides,
    }) as any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameActionExecutorService,
        // Реальный реестр — регистрируем фейковый handler руками
        HeroAbilityRegistry,
        {
          provide: GameRulesValidator,
          useValue: {
            validateEndTurn: jest.fn().mockReturnValue({ valid: true }),
          },
        },
        {
          provide: CombatResolverService,
          useValue: {
            getHeroCombatModifiers: jest
              .fn()
              .mockReturnValue({ attackModifier: 0, defenseModifier: 0 }),
          },
        },
        { provide: MovementService, useValue: {} },
        { provide: ValueModifierService, useValue: {} },
        {
          provide: AdjacencyService,
          useValue: {
            isAdjacent: jest.fn().mockResolvedValue(true),
            isInSameZone: jest.fn().mockReturnValue(false),
          },
        },
        {
          provide: MetricsService,
          useValue: {
            measureServiceDuration: jest.fn((_n: string, _c: string, fn: () => any) => fn()),
            measureValidation: jest.fn((_n: string, fn: () => any) => fn()),
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
          useValue: {},
        },
      ],
    }).compile();

    service = module.get(GameActionExecutorService);
    registry = module.get(HeroAbilityRegistry);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('вызывает extended onTurnStart нового игрока И сохраняет переход в ACTION_MANEUVER', async () => {
    // Фейковый handler героя player2 (fake-hero): мутирует metadata-маркер
    let calledWith: { playerId: string } | undefined;
    const fakeHandler: ExtendedHeroAbilityHandler = {
      heroId: 'fake-hero',
      abilityName: 'Fake Turn Start',
      abilityDescription: 'mutates a detectable marker at turn start',
      async onTurnStart(state: GameState, playerId: string): Promise<GameState> {
        calledWith = { playerId };
        return {
          ...state,
          metadata: {
            ...state.metadata,
            fakeOnTurnStartMarker: `started:${playerId}`,
          } as any,
        };
      },
    };
    registry.registerExtended(fakeHandler);

    const dto: EndTurnDto = { gameId: 'test-game-1' };
    const context: ActionContext = {
      userId: 'player1',
      gameId: 'test-game-1',
      currentState: createMockGameState(),
    };

    const result = await service.executeEndTurn(dto, context);

    expect(result.success).toBe(true);
    // 1. Хук вызван для НОВОГО игрока (player2)
    expect(calledWith).toEqual({ playerId: 'player2' });
    // 2. Мутация состояния сохранилась в финальном GameState
    expect((result.gameState!.metadata as any).fakeOnTurnStartMarker).toBe(
      'started:player2',
    );
    // 3. Поток хода не сломан — фаза по-прежнему ACTION_MANEUVER, ход у player2
    expect(result.gameState!.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(result.gameState!.currentTurnPlayerId).toBe('player2');
  });

  it('no-op для героя без onTurnStart (ms-marvel зарезервирован — состояние неизменно, поток цел)', async () => {
    // Ничего не регистрируем для player1's hero; передаём ход player1 → player2,
    // у которого зарегистрирован НИЧЕГО (handler отсутствует) → no-op.
    const dto: EndTurnDto = { gameId: 'test-game-1' };
    const context: ActionContext = {
      userId: 'player1',
      gameId: 'test-game-1',
      currentState: createMockGameState(),
    };

    const result = await service.executeEndTurn(dto, context);

    expect(result.success).toBe(true);
    // Нет маркера — хук не подменил состояние
    expect((result.gameState!.metadata as any).fakeOnTurnStartMarker).toBeUndefined();
    // Поток хода целый
    expect(result.gameState!.phase).toBe(GamePhase.ACTION_MANEUVER);
    expect(result.gameState!.currentTurnPlayerId).toBe('player2');
  });
});
