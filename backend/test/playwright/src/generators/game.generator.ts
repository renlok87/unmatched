/**
 * Game Generator
 *
 * Генератор тестовых данных для игр и состояний.
 * Создаёт mock GameState для тестов без необходимости запускать полный backend.
 */

import { GAME_PHASES, HEROES, HERO_STATS, BOARD } from '../../fixtures/data';
import type { Position } from '../services/api.service';

// ============================================================
// Types
// ============================================================

export interface GameState {
  gameId: string;
  sequenceNumber: number;
  phase: string;
  turnCount: number;
  currentTurnPlayerId: string;
  players: GamePlayer[];
  fighters: Fighter[];
  decks: Record<string, Deck>;
  discardPiles: Record<string, DiscardPile>;
  handZones: Record<string, HandZone>;
  boardState: BoardState;
  metadata: GameMetadata;
  winnerId?: string;
}

export interface GamePlayer {
  userId: string;
  heroId: string;
  health: number;
  maxHealth: number;
  fighterIds: string[];
  isAlive: boolean;
}

export interface Fighter {
  id: string;
  ownerId: string;
  heroId: string;
  name: string;
  type: 'hero' | 'sidekick';
  health: number;
  maxHealth: number;
  position: Position;
  effects: FighterEffect[];
  hasSidekick: boolean;
}

export interface FighterEffect {
  id: string;
  type: string;
  value?: number;
  duration?: number;
  source?: string;
}

export interface Deck {
  cards: Card[];
}

export interface DiscardPile {
  cards: Card[];
}

export interface HandZone {
  cards: InHandCard[];
  maxSize: number;
}

export interface Card {
  id: string;
  cardId: string;
  name: string;
  cardType: string;
  value?: number;
  effects?: unknown[];
}

export interface InHandCard extends Card {
  instanceId: string;
}

export interface BoardState {
  width: number;
  height: number;
  cells: Cell[][];
  doors: Record<string, boolean>;
  fog: Record<string, boolean>;
  tokens: Record<string, BoardToken[]>;
}

export interface Cell {
  type: 'normal' | 'obstacle' | 'hazard';
  x: number;
  y: number;
}

export interface BoardToken {
  id: string;
  type: string;
  value?: number;
}

export interface GameMetadata {
  lastActionAt: Date;
  lastActionBy: string;
  version: number;
  startedAt?: Date;
  endedAt?: Date;
}

// ============================================================
// Game Generator
// ============================================================

export class GameGenerator {
  private static idCounter = 0;

  /**
   * Генерирует уникальный ID
   */
  static generateId(prefix: string): string {
    return `${prefix}-${Date.now()}-${++this.idCounter}`;
  }

  /**
   * Генерирует базовое состояние игры
   */
  static generateGameState(overrides?: Partial<GameState>): GameState {
    const gameId = this.generateId('game');
    const player1Id = this.generateId('player');
    const player2Id = this.generateId('player');
    const fighter1Id = this.generateId('fighter');
    const fighter2Id = this.generateId('fighter');

    return {
      gameId,
      sequenceNumber: 1,
      phase: GAME_PHASES.TURN_START,
      turnCount: 1,
      currentTurnPlayerId: player1Id,
      players: [
        {
          userId: player1Id,
          heroId: HEROES.DAREDEVIL,
          health: HERO_STATS[HEROES.DAREDEVIL].health,
          maxHealth: HERO_STATS[HEROES.DAREDEVIL].maxHealth,
          fighterIds: [fighter1Id],
          isAlive: true,
        },
        {
          userId: player2Id,
          heroId: HEROES.MS_MARVEL,
          health: HERO_STATS[HEROES.MS_MARVEL].health,
          maxHealth: HERO_STATS[HEROES.MS_MARVEL].maxHealth,
          fighterIds: [fighter2Id],
          isAlive: true,
        },
      ],
      fighters: [
        {
          id: fighter1Id,
          ownerId: player1Id,
          heroId: HEROES.DAREDEVIL,
          name: 'Daredevil',
          type: 'hero',
          health: HERO_STATS[HEROES.DAREDEVIL].health,
          maxHealth: HERO_STATS[HEROES.DAREDEVIL].maxHealth,
          position: { ...BOARD.START_POSITIONS.PLAYER1 },
          effects: [],
          hasSidekick: false,
        },
        {
          id: fighter2Id,
          ownerId: player2Id,
          heroId: HEROES.MS_MARVEL,
          name: 'Ms. Marvel',
          type: 'hero',
          health: HERO_STATS[HEROES.MS_MARVEL].health,
          maxHealth: HERO_STATS[HEROES.MS_MARVEL].maxHealth,
          position: { ...BOARD.START_POSITIONS.PLAYER2 },
          effects: [],
          hasSidekick: false,
        },
      ],
      decks: {
        [player1Id]: { cards: this.generateDeck(HEROES.DAREDEVIL) },
        [player2Id]: { cards: this.generateDeck(HEROES.MS_MARVEL) },
      },
      discardPiles: {
        [player1Id]: { cards: [] },
        [player2Id]: { cards: [] },
      },
      handZones: {
        [player1Id]: {
          cards: this.generateHand(5, HEROES.DAREDEVIL),
          maxSize: 5,
        },
        [player2Id]: {
          cards: this.generateHand(5, HEROES.MS_MARVEL),
          maxSize: 5,
        },
      },
      boardState: this.generateBoardState(),
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: player1Id,
        version: 1,
        startedAt: new Date(),
      },
      ...overrides,
    };
  }

  /**
   * Генерирует состояние для фазы атаки
   */
  static generateAttackPhaseState(overrides?: Partial<GameState>): GameState {
    return this.generateGameState({
      phase: GAME_PHASES.ACTION_ATTACK,
      ...overrides,
    });
  }

  /**
   * Генерирует состояние для фазы боя
   */
  static generateCombatPhaseState(overrides?: Partial<GameState>): GameState {
    const state = this.generateGameState({
      phase: GAME_PHASES.COMBAT,
      ...overrides,
    });

    // Сближаем бойцов для боя
    if (state.fighters[0] && state.fighters[1]) {
      state.fighters[1].position = { x: 6, y: 10 }; // Рядом с player1
    }

    return state;
  }

  /**
   * Генерирует состояние завершённой игры
   */
  static generateVictoryState(winnerId: string, loserId: string): GameState {
    const state = this.generateGameState({
      phase: GAME_PHASES.GAME_OVER,
      winnerId,
      metadata: {
        lastActionAt: new Date(),
        lastActionBy: winnerId,
        version: 1,
        startedAt: new Date(Date.now() - 300000), // 5 минут назад
        endedAt: new Date(),
      },
    });

    // Обновляем здоровье игроков
    state.players = state.players.map(p => ({
      ...p,
      isAlive: p.userId === winnerId,
      health: p.userId === winnerId ? 10 : 0,
    }));

    // Обновляем здоровье бойцов
    state.fighters = state.fighters.map(f => ({
      ...f,
      health: f.ownerId === winnerId ? 10 : 0,
    }));

    return state;
  }

  /**
   * Генерирует состояние с конкретным числом ходов
   */
  static generateStateWithTurns(turnCount: number): GameState {
    return this.generateGameState({
      turnCount,
      phase: GAME_PHASES.ACTION_MANEUVER,
    });
  }

  // ============================================================
  // Private Helpers
  // ============================================================

  /**
   * Генерирует колоду карт для героя
   */
  private static generateDeck(heroId: string): Card[] {
    const cards: Card[] = [];
    const cardCount = 30; // Стандартный размер колоды

    for (let i = 0; i < cardCount; i++) {
      const cardType = i % 3 === 0 ? 'ATTACK' : i % 3 === 1 ? 'DEFENSE' : 'EFFECT';
      cards.push({
        id: this.generateId(`card-${heroId}`),
        cardId: `${heroId}-card-${i}`,
        name: `${heroId} Card ${i}`,
        cardType,
        value: Math.floor(Math.random() * 5) + 1,
        effects: [],
      });
    }

    return cards;
  }

  /**
   * Генерирует руку карт
   */
  private static generateHand(size: number, heroId: string): InHandCard[] {
    const cards: InHandCard[] = [];

    for (let i = 0; i < size; i++) {
      const cardType = i % 3 === 0 ? 'ATTACK' : i % 3 === 1 ? 'DEFENSE' : 'EFFECT';
      cards.push({
        id: this.generateId(`card-${heroId}`),
        instanceId: this.generateId(`instance-${heroId}`),
        cardId: `${heroId}-card-${i}`,
        name: `${heroId} Card ${i}`,
        cardType,
        value: Math.floor(Math.random() * 5) + 1,
        effects: [],
      });
    }

    return cards;
  }

  /**
   * Генерирует состояние доски
   */
  private static generateBoardState(): BoardState {
    const { WIDTH, HEIGHT } = BOARD;
    const cells: Cell[][] = [];

    for (let y = 0; y < HEIGHT; y++) {
      const row: Cell[] = [];
      for (let x = 0; x < WIDTH; x++) {
        row.push({
          type: 'normal',
          x,
          y,
        });
      }
      cells.push(row);
    }

    return {
      width: WIDTH,
      height: HEIGHT,
      cells,
      doors: {
        '5:10': false,
        '10:5': false,
        '14:10': false,
        '10:15': false,
      },
      fog: {},
      tokens: {},
    };
  }
}

// ============================================================
// Helper Functions
// ============================================================

/**
 * Создаёт упрощённое DTO для манёвра
 */
export function createManeuverDto(
  gameId: string,
  fighterId: string,
  cardId: string,
  path: Position[],
): { gameId: string; fighterId: string; cardId: string; path: Position[] } {
  return { gameId, fighterId, cardId, path };
}

/**
 * Создаёт упрощённое DTO для атаки
 */
export function createAttackDto(
  gameId: string,
  attackerId: string,
  targetId: string,
  cardId: string,
): { gameId: string; attackerId: string; targetId: string; cardId: string } {
  return { gameId, attackerId: attackerId, targetId, cardId };
}

/**
 * Создаёт DTO для завершения хода
 */
export function createEndTurnDto(gameId: string): { gameId: string } {
  return { gameId };
}

/**
 * Генерирует путь между двумя точками
 */
export function generatePath(from: Position, to: Position): Position[] {
  const path: Position[] = [from];
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const steps = Math.max(Math.abs(dx), Math.abs(dy));

  for (let i = 1; i <= steps; i++) {
    path.push({
      x: from.x + (dx * i) / steps,
      y: from.y + (dy * i) / steps,
    });
  }

  return path;
}
