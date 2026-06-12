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
  GAME_OVER = 'GAME_OVER', // Игра окончена, победитель определён
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
 * Состояние текущего боя (атака объявлена, ждём защиту/разрешение).
 * Живёт в metadata.combatInfo между executeAttack и executeResolveCombat.
 */
export interface CombatState {
  readonly attackerId: string;
  readonly defenderId: string;
  /** Атакованный боец (id из fighters). Optional — легаси-сейвы без поля:
   *  fallback на первого бойца защитника (старое поведение). */
  readonly targetFighterId?: string;
  readonly attackerCardId: string;
  readonly defenderCardId?: string;
  readonly attackValue: number;
  readonly defenseValue: number;
  readonly startedAt: Date;
  readonly timeoutAt?: Date;
}

/**
 * Метаданные состояния
 */
export interface GameStateMetadata {
  readonly lastActionAt: Date;
  readonly lastActionBy: string;
  readonly version: number;
  readonly compressed?: boolean; // Опционально: сжатие для оптимизации
  // Фактический контракт executor'а/guard'ов (раньше писался через "as any"):
  readonly combatInfo?: CombatState; // Текущий бой (между attack и resolveCombat)
  readonly passCount?: number; // Счётчик pass-действий
  readonly winnerId?: string; // Победитель (заполняется при GAME_OVER)
  /** Оставшиеся действия текущего игрока в этом ходу (легаси-сейвы без поля → дефолт в getActionsRemaining) */
  readonly actionsRemaining?: number;
}

/**
 * Действий за ход по правилам Unmatched: ровно 2
 * (манёвр / атака / scheme в любой комбинации, атаковать можно дважды).
 */
export const ACTIONS_PER_TURN = 2;

/**
 * Оставшиеся действия текущего игрока. Единственная точка дефолта
 * (паттерн getFighterMovement): легаси-сейвы/мусор (null, NaN, отрицательное,
 * строка) → ACTIONS_PER_TURN.
 */
export function getActionsRemaining(state: GameState): number {
  const n = Number(state.metadata.actionsRemaining);
  return Number.isInteger(n) && n >= 0 ? n : ACTIONS_PER_TURN;
}
