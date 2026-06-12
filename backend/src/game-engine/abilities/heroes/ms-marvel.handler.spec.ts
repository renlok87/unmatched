/**
 * Ms. Marvel Handler Unit Tests
 *
 * Тесты для обработчика способности Ms. Marvel - Stretchy
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import { MsMarvelHandler, TurnStartMoveResult } from './ms-marvel.handler';
import type { GameState } from '../../models/game-state.model';
import type { Fighter } from '../../models/fighter.model';
import { GamePhase } from '../../models/game-state.model';
import { FighterType } from '../../models/fighter.model';
import { createEmptyBoardState } from '../../models/board.model';

describe('MsMarvelHandler', () => {
  let handler: MsMarvelHandler;
  let mockState: GameState;
  const playerId = 'player-ms-marvel';
  const enemyId = 'player-enemy';

  beforeEach(() => {
    handler = new MsMarvelHandler();

    // Создаём mock состояние игры
    mockState = {
      gameId: 'test-game',
      sequenceNumber: 1,
      phase: GamePhase.TURN_START,
      turnCount: 1,
      currentTurnPlayerId: playerId,
      players: [
        {
          userId: playerId,
          heroId: 'ms-marvel',
          health: 14,
          maxHealth: 14,
          fighterIds: ['fighter-ms-marvel'],
          isAlive: true,
        },
        {
          userId: enemyId,
          heroId: 'some-hero',
          health: 15,
          maxHealth: 15,
          fighterIds: ['fighter-enemy'],
          isAlive: true,
        },
      ],
      fighters: [
        {
          id: 'fighter-ms-marvel',
          ownerId: playerId,
          heroId: 'ms-marvel',
          name: 'Ms. Marvel',
          type: FighterType.HERO,
          health: 14,
          maxHealth: 14,
          position: { x: 2, y: 2 },
          effects: [],
          hasSidekick: false,
        } as Fighter,
        {
          id: 'fighter-enemy',
          ownerId: enemyId,
          heroId: 'some-hero',
          name: 'Enemy',
          type: FighterType.HERO,
          health: 15,
          maxHealth: 15,
          position: { x: 3, y: 2 },
          effects: [],
          hasSidekick: false,
        } as Fighter,
      ],
      decks: {
        [playerId]: {
          cards: [],
          drawPile: [],
        },
        [enemyId]: {
          cards: [],
          drawPile: [],
        },
      },
      discardPiles: {
        [playerId]: [],
        [enemyId]: [],
      },
      handZones: {
        [playerId]: {
          cards: [],
          maxSize: 5,
        },
        [enemyId]: {
          cards: [],
          maxSize: 5,
        },
      },
      boardState: createEmptyBoardState(),
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: playerId,
        version: 1,
      },
    } as GameState;
  });

  describe('Свойства обработчика', () => {
    it('должен иметь правильный heroId', () => {
      expect(handler.heroId).toBe('ms-marvel');
    });

    it('должен иметь правильное название способности', () => {
      expect(handler.abilityName).toBe('Stretchy');
    });

    it('должен иметь описание способности', () => {
      expect(handler.abilityDescription).toContain('переместиться');
      expect(handler.abilityDescription).toContain('переместиться');
      expect(handler.abilityDescription).toContain('атаковать');
    });
  });

  describe('getAttackRange', () => {
    it('должен возвращать расширенный радиус атаки', () => {
      expect(handler.getAttackRange()).toBe(2);
    });
  });

  describe('canAttackAtRange', () => {
    it('должен возвращать true для дистанции 1', () => {
      expect(handler.canAttackAtRange('attacker', 'defender', 1)).toBe(true);
    });

    it('должен возвращать true для дистанции 2', () => {
      expect(handler.canAttackAtRange('attacker', 'defender', 2)).toBe(true);
    });

    it('должен возвращать false для дистанции 3', () => {
      expect(handler.canAttackAtRange('attacker', 'defender', 3)).toBe(false);
    });

    it('должен возвращать false для дистанции 0', () => {
      expect(handler.canAttackAtRange('attacker', 'defender', 0)).toBe(true);
    });
  });

  describe('canTrigger', () => {
    it('должен возвращать true для живого игрока с Ms. Marvel', () => {
      expect(handler.canTrigger(mockState, playerId)).toBe(true);
    });

    it('должен возвращать false для другого героя', () => {
      expect(handler.canTrigger(mockState, enemyId)).toBe(false);
    });

    it('должен возвращать false когда игрок мёртв', () => {
      const deadState = {
        ...mockState,
        players: mockState.players.map((p) =>
          p.userId === playerId ? { ...p, isAlive: false } : p,
        ),
      };
      expect(handler.canTrigger(deadState, playerId)).toBe(false);
    });
  });

  describe('canAttackTarget', () => {
    it('должен возвращать true для соседнего бойца (расстояние 1)', () => {
      expect(handler.canAttackTarget(mockState, 'fighter-ms-marvel', 'fighter-enemy')).toBe(true);
    });

    it('должен возвращать true для бойца на расстоянии 2', () => {
      // Перемещаем врага на расстояние 2
      const stateWithDistantEnemy = {
        ...mockState,
        fighters: mockState.fighters.map((f) =>
          f.id === 'fighter-enemy' ? { ...f, position: { x: 4, y: 2 } } : f,
        ),
      };
      expect(handler.canAttackTarget(stateWithDistantEnemy, 'fighter-ms-marvel', 'fighter-enemy')).toBe(true);
    });

    it('должен возвращать false для бойца на расстоянии 3', () => {
      // Перемещаем врага на расстояние 3
      const stateWithDistantEnemy = {
        ...mockState,
        fighters: mockState.fighters.map((f) =>
          f.id === 'fighter-enemy' ? { ...f, position: { x: 5, y: 2 } } : f,
        ),
      };
      expect(handler.canAttackTarget(stateWithDistantEnemy, 'fighter-ms-marvel', 'fighter-enemy')).toBe(false);
    });

    it('должен возвращать false когда атакующий не Ms. Marvel', () => {
      expect(handler.canAttackTarget(mockState, 'fighter-enemy', 'fighter-ms-marvel')).toBe(false);
    });
  });

  describe('executeTurnStartMove', () => {
    it('должен успешно переместить бойца на 1 клетку', async () => {
      const targetPosition = { x: 3, y: 2 };
      const newState = await handler.executeTurnStartMove(mockState, playerId, targetPosition);

      const fighter = newState.fighters.find((f) => f.id === 'fighter-ms-marvel');
      expect(fighter?.position).toEqual(targetPosition);
    });

    it('не должен перемещать бойца более чем на 1 клетку', async () => {
      const targetPosition = { x: 4, y: 2 };
      const newState = await handler.executeTurnStartMove(mockState, playerId, targetPosition);

      const fighter = newState.fighters.find((f) => f.id === 'fighter-ms-marvel');
      // Позиция не должна измениться
      expect(fighter?.position).toEqual({ x: 2, y: 2 });
    });

    it('не должен перемещать когда условие не выполнено', async () => {
      const targetPosition = { x: 3, y: 2 };
      const newState = await handler.executeTurnStartMove(mockState, enemyId, targetPosition);

      // Состояние не должно измениться
      expect(newState).toEqual(mockState);
    });
  });

  describe('getAvailableTurnStartPositions', () => {
    it('должен возвращать 4 соседние позиции', () => {
      const positions = handler.getAvailableTurnStartPositions(mockState, playerId);

      // клетка (3,2) занята врагом из фикстуры — валидных соседей 3
      expect(positions).toHaveLength(3);
      expect(positions).toContainEqual({ x: 1, y: 2 });
      // (3,2) занята врагом — не возвращается
      expect(positions).toContainEqual({ x: 2, y: 1 });
      expect(positions).toContainEqual({ x: 2, y: 3 });
    });

    it('не должен возвращать позиции занятые другими бойцами', () => {
      const positions = handler.getAvailableTurnStartPositions(mockState, playerId);

      // Позиция (3, 2) занята врагом
      expect(positions).not.toContainEqual({ x: 3, y: 2 });
    });

    it('должен возвращать пустой массив когда боец не найден', () => {
      const positions = handler.getAvailableTurnStartPositions(mockState, enemyId);
      expect(positions).toEqual([]);
    });
  });

  describe('onTurnStart', () => {
    it('должен возвращать исходное состояние (способность активируется отдельно)', async () => {
      const newState = await handler.onTurnStart(mockState, playerId);
      expect(newState).toEqual(mockState);
    });
  });

  describe('onCombat', () => {
    it('должен возвращать исходное состояние (радиус атаки проверяется отдельно)', async () => {
      const context = {
        attackerId: 'fighter-ms-marvel',
        defenderId: 'fighter-enemy',
        isBlindBoostAvailable: false,
      };
      const newState = await handler.onCombat(mockState, context);
      expect(newState).toEqual(mockState);
    });
  });

  describe('getAbilityDescription', () => {
    it('должен возвращать описание способности', () => {
      const description = handler.getAbilityDescription();
      expect(description).toBe(handler.abilityDescription);
    });
  });

  describe('getAttackMechanicsDescription', () => {
    it('должен возвращать описание механики атаки', () => {
      const description = handler.getAttackMechanicsDescription();
      expect(description).toContain('2');
      expect(description).toContain('зон');
    });
  });

  describe('Проверка границ доски', () => {
    it('не должен возвращать позиции за границей доски', () => {
      // Размещаем Ms. Marvel в углу (0, 0)
      const cornerState = {
        ...mockState,
        fighters: mockState.fighters.map((f) =>
          f.id === 'fighter-ms-marvel' ? { ...f, position: { x: 0, y: 0 } } : f,
        ),
      };

      const positions = handler.getAvailableTurnStartPositions(cornerState, playerId);

      // Только позиции (1, 0) и (0, 1) валидны
      expect(positions.length).toBeLessThanOrEqual(2);
      expect(positions).not.toContainEqual({ x: -1, y: 0 });
      expect(positions).not.toContainEqual({ x: 0, y: -1 });
    });
  });
});
