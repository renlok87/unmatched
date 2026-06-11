/**
 * Game Execution Integration Tests
 *
 * Интеграционные тесты полного цикла игры.
 * Сценарии:
 * - Setup → Turn 1 (maneuver + attack) → Turn 2
 * - Combat с защитой → разрешение → урон → defeat
 * - Pass → recycle deck → continue
 * - Game Over → победитель определён
 */

import { Test, TestingModule } from '@nestjs/testing';
import { GameActionExecutorService } from '../services/game-action-executor.service';
import { TurnManagementService } from '../services/turn-management.service';
import { DeckManagementService } from '../services/deck-management.service';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import { CombatResolverService } from '../../engine/combat-resolver.service';
import { MovementService } from '../../engine/movement.service';
import { GameStateService } from '../../../games/game-state.service';
import { GamePhase, FighterType } from '../models';
import type { GameState, Fighter } from '../models';

// =============================================================================
// TEST UTILITIES
// =============================================================================

/**
 * Создаёт полное состояние игры для интеграционных тестов
 */
function createFullGameState(): GameState {
  return {
    gameId: 'integration-test-game',
    sequenceNumber: 0,
    phase: GamePhase.SETUP,
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
        heroId: 'daredevil',
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
        name: 'Ms. Marvel',
        type: FighterType.HERO,
        health: 14,
        maxHealth: 14,
        position: { x: 3, y: 5 },
        effects: [],
        hasSidekick: false,
      },
      {
        id: 'fighter2',
        ownerId: 'player2',
        heroId: 'daredevil',
        name: 'Daredevil',
        type: FighterType.HERO,
        health: 17,
        maxHealth: 17,
        position: { x: 16, y: 5 },
        effects: [],
        hasSidekick: false,
      },
    ],
    decks: {
      player1: ['card1', 'card2', 'card3', 'card4', 'card5', 'card6', 'card7'],
      player2: ['card8', 'card9', 'card10', 'card11', 'card12', 'card13', 'card14'],
    },
    discardPiles: {
      player1: [],
      player2: [],
    },
    handZones: {
      player1: { cards: ['card1', 'card2', 'card3', 'card4', 'card5'], maxSize: 5 },
      player2: { cards: ['card8', 'card9', 'card10', 'card11', 'card12'], maxSize: 5 },
    },
    boardState: {
      width: 20,
      height: 20,
      cells: [],
      doors: {
        '10:5': false, // Закрытая дверь в центре
      },
      fog: {},
      tokens: {},
    },
    metadata: {
      lastActionAt: new Date(),
      lastActionBy: 'system',
      version: 1,
      turn_actions: 0,
      turn_passed: false,
      turn_additional: 0,
    },
  };
}

/**
 * Создаёт мок-карту с указанными параметрами
 */
function createMockCard(id: string, attackValue: number, defenseValue: number) {
  return {
    id,
    name: `Card ${id}`,
    attackValue,
    defenseValue,
    effects: [],
  };
}

// =============================================================================
// INTEGRATION TESTS
// =============================================================================

describe('Game Execution Integration Tests', () => {
  let actionExecutor: GameActionExecutorService;
  let turnManagement: TurnManagementService;
  let deckManagement: DeckManagementService;
  let cardEffectExecutor: CardEffectExecutorService;
  let combatResolver: CombatResolverService;
  let movementService: MovementService;
  let gameStateService: GameStateService;

  let gameState: GameState;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameActionExecutorService,
        TurnManagementService,
        DeckManagementService,
        CardEffectExecutorService,
        CombatResolverService,
        MovementService,
        {
          provide: GameStateService,
          useValue: {
            getGameState: jest.fn().mockResolvedValue(null),
            saveGameState: jest.fn().mockResolvedValue(undefined),
            updateGameState: jest.fn().mockResolvedValue(undefined),
          },
        },
        {
          provide: 'ContentService',
          useValue: {
            getHeroById: jest.fn().mockResolvedValue({
              id: 'ms-marvel',
              name: 'Ms. Marvel',
              health: 14,
              movement: 2,
              abilities: [],
              deckCards: [],
            }),
            getCardById: jest.fn().mockImplementation((id) => createMockCard(id, 3, 2)),
          },
        },
        {
          provide: 'HeroAbilityRegistry',
          useValue: {
            triggerOnTurnStart: jest.fn().mockReturnValue([]),
            triggerOnTurnEnd: jest.fn().mockReturnValue([]),
            triggerOnMove: jest.fn().mockReturnValue([]),
            triggerOnDefend: jest.fn().mockReturnValue([]),
            triggerOnAttack: jest.fn().mockReturnValue([]),
          },
        },
      ],
    }).compile();

    actionExecutor = module.get<GameActionExecutorService>(GameActionExecutorService);
    turnManagement = module.get<TurnManagementService>(TurnManagementService);
    deckManagement = module.get<DeckManagementService>(DeckManagementService);
    cardEffectExecutor = module.get<CardEffectExecutorService>(CardEffectExecutorService);
    combatResolver = module.get<CombatResolverService>(CombatResolverService);
    movementService = module.get<MovementService>(MovementService);
    gameStateService = module.get<GameStateService>(GameStateService);

    gameState = createFullGameState();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // =========================================================================
  // SCENARIO 1: Полный цикл игры (Setup → Turn 1 → Turn 2 → Game Over)
  // =========================================================================

  describe('Scenario 1: Complete Game Flow', () => {
    it('should execute complete game from setup to game over', async () => {
      // 1. SETUP: Инициализация колод
      gameState = await deckManagement.initializeDeck(gameState, 'player1', 'ms-marvel');
      gameState = await deckManagement.initializeDeck(gameState, 'player2', 'daredevil');

      expect(gameState.decks.player1).toBeDefined();
      expect(gameState.decks.player2).toBeDefined();

      // 2. TURN 1 START: Начало хода player1
      const turn1Result = await turnManagement.startTurn(gameState, 'player1');
      gameState = turn1Result.state;

      expect(gameState.phase).toBe(GamePhase.TURN_START);
      expect(gameState.currentTurnPlayerId).toBe('player1');

      // 3. TURN 1 MANEUVER: Player1 перемещается
      const maneuverResult = await actionExecutor.executeManeuver(
        { fighterId: 'fighter1', cardId: 'card1', path: [{ x: 4, y: 5 }, { x: 5, y: 5 }] },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(maneuverResult.success).toBe(true);
      if (maneuverResult.gameState) {
        gameState = maneuverResult.gameState;
      }

      // 4. TURN 1 ATTACK: Player1 атакует
      const attackResult = await actionExecutor.executeAttack(
        { attackerId: 'fighter1', targetId: 'fighter2', cardId: 'card2' },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(attackResult.success).toBe(true);
      if (attackResult.gameState) {
        gameState = attackResult.gameState;
      }

      expect(gameState.phase).toBe(GamePhase.COMBAT);

      // 5. COMBAT DEFENSE: Player2 защищается
      const defenseResult = await actionExecutor.executePlayDefense(
        { combatId: gameState.gameId, cardId: 'card8' },
        { userId: 'player2', gameId: gameState.gameId, currentState: gameState }
      );

      expect(defenseResult.success).toBe(true);
      if (defenseResult.gameState) {
        gameState = defenseResult.gameState;
      }

      // 6. RESOLVE COMBAT: Разрешение боя
      const resolveResult = await actionExecutor.executeResolveCombat(
        { gameId: gameState.gameId },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(resolveResult.success).toBe(true);
      if (resolveResult.gameState) {
        gameState = resolveResult.gameState;
      }

      // Проверяем, что урон нанесён
      const fighter1 = gameState.fighters.find(f => f.id === 'fighter1');
      const fighter2 = gameState.fighters.find(f => f.id === 'fighter2');
      expect(fighter1?.health).toBeLessThan(14);
      expect(fighter2?.health).toBeLessThan(17);

      // 7. END TURN: Завершение хода
      const endTurnResult = await actionExecutor.executeEndTurn(
        { gameId: gameState.gameId, playerId: 'player1' },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(endTurnResult.success).toBe(true);
      if (endTurnResult.gameState) {
        gameState = endTurnResult.gameState;
      }

      expect(gameState.currentTurnPlayerId).toBe('player2');
      expect(gameState.turnCount).toBe(1); // Ещё первый раунд

      // 8. TURN 2: Ход player2
      const turn2Result = await turnManagement.startTurn(gameState, 'player2');
      gameState = turn2Result.state;

      expect(gameState.currentTurnPlayerId).toBe('player2');
    });

    it('should detect game over when all fighters defeated', async () => {
      // Устанавливаем состояние где почти все бойцы повержены
      gameState.fighters = [
        {
          id: 'fighter1',
          ownerId: 'player1',
          heroId: 'ms-marvel',
          name: 'Ms. Marvel',
          type: FighterType.HERO,
          health: 14,
          maxHealth: 14,
          position: { x: 3, y: 5 },
          effects: [],
          hasSidekick: false,
        },
        {
          id: 'fighter2',
          ownerId: 'player2',
          heroId: 'daredevil',
          name: 'Daredevil',
          type: FighterType.HERO,
          health: 0, // Повержен
          maxHealth: 17,
          position: { x: 16, y: 5 },
          effects: [],
          hasSidekick: false,
        },
      ];

      const endTurnResult = await actionExecutor.executeEndTurn(
        { gameId: gameState.gameId, playerId: 'player1' },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(endTurnResult.success).toBe(true);
      expect(endTurnResult.gameState?.phase).toBe(GamePhase.GAME_OVER);
      expect((endTurnResult.gameState?.metadata as any)?.winnerId).toBe('player1');
    });
  });

  // =========================================================================
  // SCENARIO 2: Combat с защитой
  // =========================================================================

  describe('Scenario 2: Combat with Defense', () => {
    it('should resolve combat with both attack and defense cards', async () => {
      // Настраиваем состояние боя
      gameState.phase = GamePhase.COMBAT;
      (gameState.metadata as any).combatInfo = {
        attackerId: 'fighter1',
        defenderId: 'player2',
        attackerCardId: 'card2',
        attackValue: 5,
        defenseValue: 0,
        startedAt: new Date(),
      };

      // Player2 играет защиту
      const defenseResult = await actionExecutor.executePlayDefense(
        { combatId: 'combat1', cardId: 'card8' },
        { userId: 'player2', gameId: gameState.gameId, currentState: gameState }
      );

      expect(defenseResult.success).toBe(true);
      expect(defenseResult.gameState?.phase).toBe(GamePhase.COMBAT_RESOLVE);

      gameState = defenseResult.gameState!;

      // Разрешаем бой
      const resolveResult = await combatResolver.resolveCombat(
        gameState,
        'fighter1',
        'fighter2',
        'card2',
        'card8'
      );

      expect(resolveResult.defenderDamage).toBeGreaterThan(0);
      expect(resolveResult.attackerDamage).toBeGreaterThanOrEqual(0);
    });

    it('should apply full damage when no defense played', async () => {
      gameState.phase = GamePhase.COMBAT;
      (gameState.metadata as any).combatInfo = {
        attackerId: 'fighter1',
        defenderId: 'player2',
        attackerCardId: 'card2',
        attackValue: 5,
        defenseValue: 0,
        startedAt: new Date(),
      };

      // Сразу переходим к разрешению (без защиты)
      const resolveResult = await actionExecutor.executeResolveCombat(
        { gameId: gameState.gameId },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(resolveResult.success).toBe(true);

      const fighter2 = resolveResult.gameState?.fighters.find(f => f.id === 'fighter2');
      expect(fighter2?.health).toBeLessThan(17); // Должен получить урон
    });
  });

  // =========================================================================
  // SCENARIO 3: Pass и recycle deck
  // =========================================================================

  describe('Scenario 3: Pass and Deck Recycle', () => {
    it('should execute pass and draw from recycle', async () => {
      // Заполняем сброс для тестирования recycle
      gameState.discardPiles.player1 = ['card10', 'card11', 'card12'];
      gameState.handZones.player1.cards = ['card1', 'card2'];

      const passResult = await actionExecutor.executePass(
        { gameId: gameState.gameId, playerId: 'player1' },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(passResult.success).toBe(true);

      // Проверяем, что сброс увеличился
      const newMetadata = passResult.gameState?.metadata as any;
      expect(newMetadata?.passCount).toBeGreaterThan(0);
    });

    it('should recycle deck when draw pile is empty', async () => {
      // Опустошаем колоду
      gameState.decks.player1 = [];
      gameState.discardPiles.player1 = ['card10', 'card11', 'card12', 'card13'];

      const shouldRecycle = await deckManagement.shouldRecycleDeck(gameState, 'player1');
      expect(shouldRecycle).toBe(true);

      // Перетасовываем
      const recycledState = await deckManagement.recycleDeck(gameState, 'player1');

      expect(recycledState.decks.player1?.length).toBe(3);
      expect(recycledState.discardPiles.player1?.length).toBe(0);
    });
  });

  // =========================================================================
  // SCENARIO 4: Game Over условия
  // =========================================================================

  describe('Scenario 4: Game Over Conditions', () => {
    it('should detect victory when all enemy fighters defeated', async () => {
      gameState.fighters = [
        {
          id: 'fighter1',
          ownerId: 'player1',
          heroId: 'ms-marvel',
          name: 'Ms. Marvel',
          type: FighterType.HERO,
          health: 14,
          maxHealth: 14,
          position: { x: 3, y: 5 },
          effects: [],
          hasSidekick: false,
        },
        {
          id: 'fighter2',
          ownerId: 'player2',
          heroId: 'daredevil',
          name: 'Daredevil',
          type: FighterType.HERO,
          health: 0, // Повержен
          maxHealth: 17,
          position: { x: 16, y: 5 },
          effects: [],
          hasSidekick: false,
        },
      ];

      const endTurnResult = await turnManagement.endTurn(gameState, 'player1');

      expect(endTurnResult.gameOver).toBe(true);
      expect(endTurnResult.winnerId).toBe('player1');
    });

    it('should handle draw when both players have no fighters', async () => {
      gameState.fighters = [
        {
          id: 'fighter1',
          ownerId: 'player1',
          heroId: 'ms-marvel',
          name: 'Ms. Marvel',
          type: FighterType.HERO,
          health: 0,
          maxHealth: 14,
          position: { x: 3, y: 5 },
          effects: [],
          hasSidekick: false,
        },
        {
          id: 'fighter2',
          ownerId: 'player2',
          heroId: 'daredevil',
          name: 'Daredevil',
          type: FighterType.HERO,
          health: 0,
          maxHealth: 17,
          position: { x: 16, y: 5 },
          effects: [],
          hasSidekick: false,
        },
      ];

      const endTurnResult = await turnManagement.endTurn(gameState, 'player1');

      // Определяется победитель по здоровью героя или ничья
      expect(endTurnResult.gameOver).toBe(true);
    });
  });

  // =========================================================================
  // SCENARIO 5: Action economy
  // =========================================================================

  describe('Scenario 5: Action Economy', () => {
    it('should track actions taken during turn', async () => {
      // Первое действие
      let result = await turnManagement.spendAction(gameState, 'player1');
      gameState = result;

      let metadata = gameState.metadata as any;
      expect(metadata.turn_actions).toBe(1);

      // Второе действие
      result = await turnManagement.spendAction(gameState, 'player1');
      gameState = result;

      metadata = gameState.metadata as any;
      expect(metadata.turn_actions).toBe(2);

      // Третье действие должно провалиться (лимит 2)
      await expect(turnManagement.spendAction(gameState, 'player1')).rejects.toThrow();
    });

    it('should allow additional actions from pass', async () => {
      (gameState.metadata as any).turn_actions = 2; // Максимум
      (gameState.metadata as any).turn_additional = 1; // +1 от pass

      const canTake = turnManagement.canTakeAction(gameState, 'player1');
      expect(canTake).toBe(true); // Может взять 3-е действие
    });

    it('should not allow actions after pass', async () => {
      const passResult = await turnManagement.pass(gameState, 'player1');
      gameState = passResult.state;

      expect((gameState.metadata as any).turn_passed).toBe(true);

      const canTake = turnManagement.canTakeAction(gameState, 'player1');
      expect(canTake).toBe(false);
    });
  });

  // =========================================================================
  // SCENARIO 6: Двери и взаимодействие с доской
  // =========================================================================

  describe('Scenario 6: Door Interaction', () => {
    it('should toggle door state', async () => {
      const doorKey = '10:5';
      const initialState = gameState.boardState.doors[doorKey];

      const toggleResult = await actionExecutor.executeToggleDoor(
        { gameId: gameState.gameId, x: 10, y: 5 },
        { userId: 'player1', gameId: gameState.gameId, currentState: gameState }
      );

      expect(toggleResult.success).toBe(true);
      expect(toggleResult.gameState?.boardState.doors[doorKey]).toBe(!initialState);
    });

    it('should block movement through closed doors', async () => {
      gameState.boardState.doors['10:5'] = false; // Закрыта

      const path = [{ x: 10, y: 5 }];
      const validationResult = await movementService.validatePath(
        gameState,
        'fighter1',
        path
      );

      // Валидация должна провалиться для закрытой двери
      expect(validationResult.valid).toBe(false);
    });
  });

  // =========================================================================
  // SCENARIO 7: Мульплеер (3+ игрока)
  // =========================================================================

  describe('Scenario 7: Multiplayer Game', () => {
    it('should handle turn order with 3 players', async () => {
      gameState.players = [
        { userId: 'player1', heroId: 'h1', health: 10, maxHealth: 10, fighterIds: ['f1'], isAlive: true },
        { userId: 'player2', heroId: 'h2', health: 10, maxHealth: 10, fighterIds: ['f2'], isAlive: true },
        { userId: 'player3', heroId: 'h3', health: 10, maxHealth: 10, fighterIds: ['f3'], isAlive: true },
      ];
      gameState.currentTurnPlayerId = 'player1';

      // Player1 заканчивает ход
      let result = await turnManagement.endTurn(gameState, 'player1');
      gameState = result.state;

      expect(gameState.currentTurnPlayerId).toBe('player2');

      // Player2 заканчивает ход
      result = await turnManagement.endTurn(gameState, 'player2');
      gameState = result.state;

      expect(gameState.currentTurnPlayerId).toBe('player3');

      // Player3 заканчивает ход -> обратно к player1
      result = await turnManagement.endTurn(gameState, 'player3');
      gameState = result.state;

      expect(gameState.currentTurnPlayerId).toBe('player1');
    });

    it('should skip dead players in turn order', async () => {
      gameState.players = [
        { userId: 'player1', heroId: 'h1', health: 10, maxHealth: 10, fighterIds: ['f1'], isAlive: true },
        { userId: 'player2', heroId: 'h2', health: 0, maxHealth: 10, fighterIds: ['f2'], isAlive: false }, // Мёртв
        { userId: 'player3', heroId: 'h3', health: 10, maxHealth: 10, fighterIds: ['f3'], isAlive: true },
      ];
      gameState.currentTurnPlayerId = 'player1';

      const result = await turnManagement.endTurn(gameState, 'player1');
      gameState = result.state;

      // Должен пропустить мёртвого player2 и перейти к player3
      expect(gameState.currentTurnPlayerId).toBe('player3');
    });
  });
});
