/**
 * Card Effect Executor Service Unit Tests
 *
 * Тесты для выполнения эффектов карт.
 */

import { Test, TestingModule } from '@nestjs/testing';
import { CardEffectExecutorService } from './card-effect-executor.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import {
  GameState,
  CardType,
  EffectTiming,
  EffectType,
  EffectTarget,
  GamePhase,
  FighterType,
} from '../models';
import { createEmptyBoardState } from '../models/board.model';

describe('CardEffectExecutorService', () => {
  let service: CardEffectExecutorService;
  let valueModifierService: ValueModifierService;

  const mockState: GameState = {
    gameId: 'test-game',
    sequenceNumber: 1,
    phase: GamePhase.ACTION_ATTACK,
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
        position: { x: 5, y: 5 },
        effects: [],
        hasSidekick: false,
      },
    ],
    decks: {},
    discardPiles: {},
    handZones: {
      'player-1': {
        cards: [
          {
            id: 'card-1',
            cardId: 'attack-card',
            name: 'Test Attack',
            nameEn: 'Test Attack',
            nameRu: 'Тестовая Атака',
            cardType: CardType.ATTACK,
            attackValue: 5,
            effects: [
              {
                id: 'effect-1',
                type: EffectType.MODIFY_ATTACK,
                timing: EffectTiming.DURING_COMBAT,
                target: EffectTarget.SELF,
                value: 2,
              },
            ],
            isVisible: true,
          },
        ],
        maxSize: 5,
      },
      'player-2': {
        cards: [],
        maxSize: 5,
      },
    },
    boardState: createEmptyBoardState(20, 20),
    metadata: {
      lastActionAt: new Date(),
      lastActionBy: 'player-1',
      version: 1,
    },
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CardEffectExecutorService,
        {
          provide: ValueModifierService,
          useValue: {
            addModifier: jest.fn(),
            removeModifier: jest.fn(),
            clearModifiers: jest.fn(),
            applyModifiers: jest.fn().mockReturnValue({
              baseValue: 5,
              modifiedValue: 7,
              modifiers: [],
            }),
          },
        },
      ],
    }).compile();

    service = module.get<CardEffectExecutorService>(CardEffectExecutorService);
    valueModifierService = module.get<ValueModifierService>(ValueModifierService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('executeEffect', () => {
    it('should execute MODIFY_ATTACK effect successfully', async () => {
      const effect = {
        id: 'effect-atk',
        type: EffectType.MODIFY_ATTACK,
        timing: EffectTiming.ON_PLAY,
        target: EffectTarget.SELF,
        value: 3,
      };

      const context = {
        playerId: 'player-1',
        card: mockState.handZones['player-1'].cards[0],
        fighterId: 'fighter-1',
      };

      const result = await service.executeEffect(mockState, effect, context);

      expect(result.success).toBe(true);
      expect(result.effectId).toBe('effect-atk');
      expect(result.valueApplied).toBe(3);
      expect(result.targetIds).toContain('fighter-1');
    });

    it('should fail when timing is invalid for current phase', async () => {
      const effect = {
        id: 'effect-turn-start',
        type: EffectType.DRAW_CARD,
        timing: EffectTiming.TURN_START,
        value: 1,
      };

      const context = {
        playerId: 'player-1',
        card: mockState.handZones['player-1'].cards[0],
      };

      const result = await service.executeEffect(mockState, effect, context);

      expect(result.success).toBe(false);
      expect(result.message).toContain('Invalid timing');
    });

    it('should resolve targets correctly for ALL_ENEMIES', async () => {
      const effect = {
        id: 'effect-damage-all',
        type: EffectType.DAMAGE,
        timing: EffectTiming.ON_PLAY,
        target: EffectTarget.ALL_ENEMIES,
        value: 2,
      };

      const context = {
        playerId: 'player-1',
        card: mockState.handZones['player-1'].cards[0],
      };

      const result = await service.executeEffect(mockState, effect, context);

      expect(result.success).toBe(true);
      expect(result.targetIds).toContain('fighter-2');
      expect(result.targetIds).not.toContain('fighter-1');
    });

    it('should handle DEFENDER target in combat context', async () => {
      const effect = {
        id: 'effect-weaken',
        type: EffectType.MODIFY_DEFENSE,
        timing: EffectTiming.DURING_COMBAT,
        target: EffectTarget.DEFENDER,
        value: -1,
      };

      const combat = {
        attackerId: 'fighter-1',
        defenderId: 'fighter-2',
        attackCardId: 'card-1',
        attackValue: 5,
        defenseValue: 3,
      };

      const context = {
        playerId: 'player-1',
        card: mockState.handZones['player-1'].cards[0],
        combat,
      };

      // Изменяем фазу на COMBAT для валидации тайминга
      const combatState = { ...mockState, phase: GamePhase.COMBAT };

      const result = await service.executeEffect(combatState, effect, context);

      expect(result.success).toBe(true);
      expect(result.targetIds).toContain('fighter-2');
    });
  });

  describe('executeOnPlayEffects', () => {
    it('should execute all ON_PLAY effects for a card', async () => {
      const card = {
        ...mockState.handZones['player-1'].cards[0],
        effects: [
          {
            id: 'effect-1',
            type: EffectType.DRAW_CARD,
            timing: EffectTiming.ON_PLAY,
            value: 1,
          },
          {
            id: 'effect-2',
            type: EffectType.HEAL,
            timing: EffectTiming.ON_PLAY,
            value: 2,
          },
        ],
      };

      const result = await service.executeOnPlayEffects(mockState, card, 'player-1');

      // DRAW_CARD и HEAL без цели должны выполниться успешно
      expect(result.appliedEffects).toHaveLength(2);
      expect(result.appliedEffects[0].success).toBe(true);
      expect(result.appliedEffects[1].success).toBe(true);
    });

    it('should return unchanged state when no ON_PLAY effects exist', async () => {
      const card = {
        ...mockState.handZones['player-1'].cards[0],
        effects: [
          {
            id: 'effect-1',
            type: EffectType.DAMAGE,
            timing: EffectTiming.AFTER_COMBAT,
            value: 1,
          },
        ],
      };

      const result = await service.executeOnPlayEffects(mockState, card, 'player-1');

      expect(result.appliedEffects).toHaveLength(0);
      expect(result.state).toEqual(mockState);
    });
  });

  describe('executeCombatEffects', () => {
    it('should calculate combat with modifiers', async () => {
      const attackerCard = {
        id: 'atk-card',
        cardId: 'strong-attack',
        name: 'Strong Attack',
        nameEn: 'Strong Attack',
        nameRu: 'Сильная Атака',
        cardType: CardType.ATTACK,
        attackValue: 5,
        effects: [
          {
            id: 'boost-atk',
            type: EffectType.MODIFY_ATTACK,
            timing: EffectTiming.DURING_COMBAT,
            target: EffectTarget.SELF,
            value: 3,
          },
        ],
        isVisible: true,
      };

      const defenderCard = {
        id: 'def-card',
        cardId: 'shield',
        name: 'Shield',
        nameEn: 'Shield',
        nameRu: 'Щит',
        cardType: CardType.DEFENSE,
        defenseValue: 3,
        effects: [
          {
            id: 'boost-def',
            type: EffectType.MODIFY_DEFENSE,
            timing: EffectTiming.DURING_COMBAT,
            target: EffectTarget.SELF,
            value: 2,
          },
        ],
        isVisible: true,
      };

      const combat = {
        attackerId: 'fighter-1',
        defenderId: 'fighter-2',
        attackCardId: 'atk-card',
        defenseCardId: 'def-card',
        attackValue: 5,
        defenseValue: 3,
      };

      // Используем состояние с фазой COMBAT для валидации тайминга
      const combatState = { ...mockState, phase: GamePhase.COMBAT };

      const result = await service.executeCombatEffects(
        combatState,
        attackerCard,
        defenderCard,
        combat,
      );

      expect(result.finalAttack).toBe(8); // 5 + 3
      expect(result.finalDefense).toBe(5); // 3 + 2
      expect(result.defenderDamage).toBe(3); // 8 - 5
      expect(result.attackerDamage).toBe(0);
      expect(result.appliedEffects).toHaveLength(2);
    });

    it('should handle null defender card', async () => {
      const attackerCard = {
        id: 'atk-card',
        cardId: 'attack',
        name: 'Attack',
        nameEn: 'Attack',
        nameRu: 'Атака',
        cardType: CardType.ATTACK,
        attackValue: 5,
        effects: [],
        isVisible: true,
      };

      const combat = {
        attackerId: 'fighter-1',
        defenderId: 'fighter-2',
        attackCardId: 'atk-card',
        attackValue: 5,
        defenseValue: 0,
      };

      const result = await service.executeCombatEffects(
        mockState,
        attackerCard,
        null,
        combat,
      );

      expect(result.finalAttack).toBe(5);
      expect(result.finalDefense).toBe(0);
      expect(result.defenderDamage).toBe(5);
    });
  });

  describe('executeAfterCombatEffects', () => {
    it('should apply damage to fighters', async () => {
      const combat = {
        attackerId: 'fighter-1',
        defenderId: 'fighter-2',
        attackCardId: 'card-1',
        attackValue: 5,
        defenseValue: 3,
      };

      const damage = {
        attackerDamage: 0,
        defenderDamage: 2,
      };

      const result = await service.executeAfterCombatEffects(mockState, combat, damage);

      const defender = result.state.fighters.find((f) => f.id === 'fighter-2');
      expect(defender?.health).toBe(8); // 10 - 2
    });

    it('should apply damage to both fighters when defense is higher', async () => {
      const combat = {
        attackerId: 'fighter-1',
        defenderId: 'fighter-2',
        attackCardId: 'card-1',
        attackValue: 3,
        defenseValue: 5,
      };

      const damage = {
        attackerDamage: 2,
        defenderDamage: 0,
      };

      const result = await service.executeAfterCombatEffects(mockState, combat, damage);

      const attacker = result.state.fighters.find((f) => f.id === 'fighter-1');
      expect(attacker?.health).toBe(8); // 10 - 2
    });
  });

  describe('executeTurnStartEffects', () => {
    it('should execute TURN_START effects for cards in hand', async () => {
      const cardWithTurnStart = {
        id: 'card-turn-start',
        cardId: 'start-card',
        name: 'Start Card',
        nameEn: 'Start Card',
        nameRu: 'Карта Начала',
        cardType: CardType.SCHEME,
        effects: [
          {
            id: 'draw-at-start',
            type: EffectType.DRAW_CARD,
            timing: EffectTiming.TURN_START,
            value: 1,
          },
        ],
        isVisible: true,
      };

      const stateWithCard = {
        ...mockState,
        handZones: {
          ...mockState.handZones,
          'player-1': {
            ...mockState.handZones['player-1'],
            cards: [...mockState.handZones['player-1'].cards, cardWithTurnStart],
          },
        },
      };

      const result = await service.executeTurnStartEffects(stateWithCard, 'player-1');

      // Эффект должен быть обработан
      expect(result).toBeDefined();
    });
  });

  describe('executeTurnEndEffects', () => {
    it('should execute TURN_END effects for cards in hand', async () => {
      const cardWithTurnEnd = {
        id: 'card-turn-end',
        cardId: 'end-card',
        name: 'End Card',
        nameEn: 'End Card',
        nameRu: 'Карта Конца',
        cardType: CardType.SCHEME,
        effects: [
          {
            id: 'discard-at-end',
            type: EffectType.DISCARD,
            timing: EffectTiming.TURN_END,
            value: 1,
          },
        ],
        isVisible: true,
      };

      const stateWithCard = {
        ...mockState,
        handZones: {
          ...mockState.handZones,
          'player-1': {
            ...mockState.handZones['player-1'],
            cards: [...mockState.handZones['player-1'].cards, cardWithTurnEnd],
          },
        },
      };

      const result = await service.executeTurnEndEffects(stateWithCard, 'player-1');

      // Эффект должен быть обработан
      expect(result).toBeDefined();
    });
  });
});
