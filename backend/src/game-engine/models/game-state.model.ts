/**
 * GameState Model
 *
 * Основная структура состояния игры Unmatched.
 * Используется во всём game-engine модуле.
 */

import type { Fighter } from './fighter.model';
import type { Card, DeckState, HandZone } from './card.model';
import type { BoardState } from './board.model';

/**
 * Фазы игры
 */
export enum GamePhase {
  SETUP = 'SETUP', // Подготовка (размещение бойцов)
  TURN_START = 'TURN_START', // Начало хода (способности в начале хода)
  ACTION_MANEUVER = 'ACTION_MANEUVER', // Манёвр
  ACTION_ATTACK = 'ACTION_ATTACK', // Атака
  COMBAT = 'COMBAT', // Бой (ожидание защиты)
  COMBAT_RESOLVE = 'COMBAT_RESOLVE', // Разрешение боя
  TURN_END = 'TURN_END', // Конец хода
}

/**
 * Полное состояние игры
 * Использует readonly для иммутабельности
 */
export interface GameState {
  readonly gameId: string;
  readonly sequenceNumber: number;
  readonly phase: GamePhase;
  readonly turnCount: number;
  readonly currentTurnPlayerId: string;

  // Игроки
  readonly players: readonly GameStatePlayer[];

  // Бойцы на доске
  readonly fighters: readonly Fighter[];

  // Колоды и сброс
  readonly decks: Readonly<Record<string, DeckState>>;
  readonly discardPiles: Readonly<Record<string, readonly Card[]>>;

  // Зоны ручек
  readonly handZones: Readonly<Record<string, HandZone>>;

  // Двери и туман войны
  readonly boardState: BoardState;

  // Метаданные
  readonly metadata: GameStateMetadata;
}

/**
 * Игрок в состоянии игры
 */
export interface GameStatePlayer {
  readonly userId: string;
  readonly heroId: string;
  readonly health: number;
  readonly maxHealth: number;
  readonly fighterIds: readonly string[];
  readonly isAlive: boolean;
}

/**
 * Метаданные состояния
 */
export interface GameStateMetadata {
  readonly lastActionAt: Date;
  readonly lastActionBy: string;
  readonly version: number;
  readonly compressed?: boolean; // Опционально: сжатие для оптимизации
}
