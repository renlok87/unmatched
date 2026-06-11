/**
 * GameState Fixture Factory
 *
 * Создаёт тестовые состояния игр для unit тестов.
 * Позволяет быстро создавать состояния с нужными параметрами.
 */

import {
  GamePhase,
  GameState,
  Fighter,
  Card,
  Position,
  FighterType,
  CardType,
  BoardState,
  createEmptyBoardState,
  DeckState,
  HandZone,
} from '../../game-engine/models';

/**
 * Factory для создания тестовых состояний игр
 */
export class GameStateFactory {
  /**
   * Создать базовое состояние игры
   *
   * @param overrides Переопределения полей
   */
  static create(overrides?: Partial<GameState>): GameState {
    return {
      gameId: 'test-game-1',
      sequenceNumber: 1,
      phase: GamePhase.SETUP,
      turnCount: 0,
      currentTurnPlayerId: 'player-1',
      players: [
        this.createPlayer({ userId: 'player-1', heroId: 'arthur' }),
        this.createPlayer({ userId: 'player-2', heroId: 'robin-hood' }),
      ],
      fighters: [],
      decks: {
        'player-1': this.createDeck(),
        'player-2': this.createDeck(),
      },
      discardPiles: {
        'player-1': [],
        'player-2': [],
      },
      handZones: {
        'player-1': this.createHandZone(),
        'player-2': this.createHandZone(),
      },
      boardState: this.createBoardState(),
      metadata: this.createMetadata(),
      ...overrides,
    };
  }

  /**
   * Создать состояние с бойцами рядом друг с другом
   */
  static withAdjacentFighters(overrides?: Partial<GameState>): GameState {
    return this.create({
      fighters: [
        this.createFighter({ id: 'f1', ownerId: 'player-1', position: { x: 5, y: 5 } }),
        this.createFighter({ id: 'f2', ownerId: 'player-2', position: { x: 6, y: 5 } }),
      ],
      phase: GamePhase.ACTION_ATTACK,
      currentTurnPlayerId: 'player-1',
      ...overrides,
    });
  }

  /**
   * Создать состояние в фазе боя
   */
  static inCombatPhase(overrides?: Partial<GameState>): GameState {
    return this.create({
      phase: GamePhase.COMBAT,
      fighters: [
        this.createFighter({ id: 'f1', ownerId: 'player-1', position: { x: 5, y: 5 } }),
        this.createFighter({ id: 'f2', ownerId: 'player-2', position: { x: 6, y: 5 } }),
      ],
      ...overrides,
    });
  }

  /**
   * Создать состояние с побеждённым бойцом
   */
  static withDefeatedFighter(overrides?: Partial<GameState>): GameState {
    return this.create({
      fighters: [
        this.createFighter({ id: 'f1', ownerId: 'player-1', position: { x: 5, y: 5 }, health: 0 }),
        this.createFighter({ id: 'f2', ownerId: 'player-2', position: { x: 6, y: 5 } }),
      ],
      ...overrides,
    });
  }

  /**
   * Создать игрока
   */
  static createPlayer(overrides?: Partial<GameState['players'][0]>): GameState['players'][0] {
    return {
      userId: 'test-user-id',
      heroId: 'test-hero',
      health: 10,
      maxHealth: 10,
      fighterIds: ['f1'],
      isAlive: true,
      ...overrides,
    };
  }

  /**
   * Создать бойца
   */
  static createFighter(overrides?: Partial<Fighter>): Fighter {
    return {
      id: 'test-fighter-id',
      ownerId: 'test-owner-id',
      heroId: 'test-hero',
      name: 'Test Fighter',
      type: FighterType.HERO,
      health: 10,
      maxHealth: 10,
      position: { x: 0, y: 0 },
      effects: [],
      hasSidekick: false,
      ...overrides,
    };
  }

  /**
   * Создать колоду
   */
  static createDeck(overrides?: Partial<DeckState>): DeckState {
    return {
      cards: [],
      drawPile: [],
      topCard: undefined,
      ...overrides,
    };
  }

  /**
   * Создать зону руки
   */
  static createHandZone(overrides?: Partial<HandZone>): HandZone {
    return {
      cards: [],
      maxSize: 5,
      ...overrides,
    };
  }

  /**
   * Создать состояние доски
   */
  static createBoardState(overrides?: Partial<BoardState>): BoardState {
    const base = createEmptyBoardState(20, 20);
    return {
      ...base,
      ...overrides,
    };
  }

  /**
   * Создать метаданные
   */
  static createMetadata(overrides?: Partial<any>): any {
    return {
      lastActionAt: new Date(),
      lastActionBy: 'test-user',
      version: 1,
      ...overrides,
    };
  }

  /**
   * Создать карту
   */
  static createCard(overrides?: Partial<Card>): Card {
    return {
      id: 'test-card-id',
      cardId: 'test-card',
      name: 'Test Card',
      nameEn: 'Test Card',
      nameRu: 'Тестовая Карта',
      cardType: CardType.ATTACK,
      attackValue: 5,
      defenseValue: 3,
      effects: [],
      ...overrides,
    };
  }

  /**
   * Создать атакующую карту
   */
  static createAttackCard(value: number = 5): Card {
    return this.createCard({
      cardId: `attack-${value}`,
      name: `Attack ${value}`,
      nameEn: `Attack ${value}`,
      nameRu: `Атака ${value}`,
      cardType: CardType.ATTACK,
      attackValue: value,
      defenseValue: undefined,
    });
  }

  /**
   * Создать защищающую карту
   */
  static createDefenseCard(value: number = 3): Card {
    return this.createCard({
      cardId: `defense-${value}`,
      name: `Defense ${value}`,
      nameEn: `Defense ${value}`,
      nameRu: `Защита ${value}`,
      cardType: CardType.DEFENSE,
      attackValue: undefined,
      defenseValue: value,
    });
  }

  /**
   * Создать позицию
   */
  static createPosition(x: number, y: number): Position {
    return { x, y };
  }
}
