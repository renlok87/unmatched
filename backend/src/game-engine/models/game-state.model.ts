/**
 * GameState Model
 *
 * Основная структура состояния игры Unmatched.
 * Используется во всём game-engine модуле.
 */

import type { Fighter } from './fighter.model';
import type { Card, CardEffect, DeckState, HandZone } from './card.model';
import type { BoardState } from './board.model';
import type { CombatResolutionProgress } from '../engine/combat-progress';

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
 * Контекст боя для эффектов. Бойцы и игроки — РАЗНЫЕ id:
 * attackerFighterId/targetFighterId — из fighters, *PlayerId — userId.
 */
export interface CombatContext {
  readonly attackerFighterId: string;
  readonly targetFighterId: string;
  readonly attackerPlayerId: string;
  readonly defenderPlayerId: string;
  readonly attackCardId: string;
  readonly defenseCardId?: string;
  readonly attackValue: number;
  readonly defenseValue: number;
}

/**
 * Контекст выполнения эффекта (одна сторона)
 */
export interface EffectContext {
  readonly playerId: string;
  readonly card: Card;
  /** Боец, который играет карту (атакующий или цель атаки) */
  readonly fighterId?: string;
  /** Боец-противник в бою */
  readonly opposingFighterId?: string;
  readonly combat?: CombatContext;
  /** Исход боя (известен только в AFTER_COMBAT): победила ли ЭТА сторона */
  readonly wonCombat?: boolean;
  /** Урон, нанесённый/полученный этой стороной (для count DAMAGE_*) */
  readonly damageDealt?: number;
  readonly damageTaken?: number;
}

/** A serializable, ordered combat stage paused for a player choice. */
export interface CombatEffectContinuation {
  readonly stage: 'ON_REVEAL' | 'DURING_COMBAT' | 'AFTER_COMBAT';
  readonly remaining: readonly { effect: CardEffect; context: EffectContext; isAttacker: boolean }[];
  readonly attackerCardCancelled: boolean;
  readonly defenderCardCancelled: boolean;
  readonly finalAttack: number;
  readonly finalDefense: number;
  readonly preventDamageToAttacker: boolean;
  readonly preventDamageToDefender: boolean;
}

/**
 * Метаданные состояния
 */
export interface GameStateMetadata {
  /** Maneuver has drawn and spent its action; movement/boost still await the owner. */
  readonly pendingManeuver?: { readonly id: string; readonly playerId: string };
  /** End-turn effects have completed; selected excess instances must be discarded. */
  readonly pendingHandDiscard?: { readonly id: string; readonly playerId: string; readonly count: number };
  readonly lastActionAt: Date;
  readonly lastActionBy: string;
  readonly version: number;
  readonly compressed?: boolean; // Опционально: сжатие для оптимизации
  // Фактический контракт executor'а/guard'ов (раньше писался через "as any"):
  readonly combatResolutionProgress?: CombatResolutionProgress;
  readonly combatEffectContinuation?: CombatEffectContinuation;
  readonly combatInfo?: CombatState; // Текущий бой (между attack и resolveCombat)
  readonly passCount?: number; // Счётчик pass-действий
  readonly winnerId?: string; // Победитель (заполняется при GAME_OVER)
  /** Оставшиеся действия текущего игрока в этом ходу (легаси-сейвы без поля → дефолт в getActionsRemaining) */
  readonly actionsRemaining?: number;
  /** Позиции бойцов на начало хода (пишет advanceTurn) — для условия
   *  MOVED_THIS_TURN («started this turn in a different space») */
  readonly turnStartPositions?: Readonly<Record<string, { x: number; y: number }>>;
  /** Эффекты, ждущие выбора игрока (MOVE/PLACE из карт) — резолвятся
   *  мутацией resolvePendingEffect; протухают при передаче хода */
  readonly pendingEffects?: readonly PendingEffect[];
  /** Per-turn флаги действий текущего игрока (TASK): нужны combat-условиям
   *  способностей («сделал ли манёвр / атаковал ли / первый ли проигрыш в этом
   *  ходу»). Выставляются в executor'е, сбрасываются в advanceTurn при передаче
   *  хода. Легаси-сейвы без полей → undefined (трактуется как false). */
  /** Игрок выполнил MANEUVER в этом ходу (executeManeuver) */
  readonly maneuveredThisTurn?: boolean;
  /** Игрок завершил хотя бы одну атаку в этом ходу (конец executeResolveCombat) */
  readonly attackedThisTurn?: boolean;
  /** Игрок проиграл хотя бы один бой в этом ходу (executeResolveCombat, won===false) */
  readonly lostCombatThisTurn?: boolean;
  /**
   * STANCE-подсистема: текущая стойка героя КАЖДОГО игрока (id стойки из
   * AbilityConfig.stances), ключ — userId. Меняется мутацией setStance
   * (выбор при размещении / «Change size»-карты) и авто-эффектами способностей
   * (set-stance/cycle-stance). Легаси-сейвы без поля → undefined: handler
   * фолбэчит на стойку с default:true (или первую в config.stances).
   */
  readonly heroStances?: Readonly<Record<string, string>>;
}

/**
 * Эффект карты, требующий выбора игрока (C2).
 * During combat the pending choice blocks the remaining combat chain and actions.
 * Other legacy pending effects retain their existing turn-expiry behavior.
 */
export interface PendingEffect {
  readonly id: string;
  /** Combat choices retain exact participants and effect context across resume. */
  readonly fighterIds?: readonly string[];
  readonly effectContext?: EffectContext;
  /**
   * 'MOVE' (до value шагов) | 'PLACE' (любая свободная клетка) |
   * 'CHOOSE_ONE' (игрок выбирает chooseCount опций из options)
   */
  readonly type: 'MOVE' | 'PLACE' | 'CHOOSE_ONE';
  /** Кому принадлежит выбор */
  readonly playerId: string;
  /** Дистанция для MOVE */
  readonly value?: number;
  /** Ограничение бойца: имя из текста карты («Move Daredevil…») */
  readonly fighterName?: string;
  /** Двигается боец противника («Place the opposing fighter…») */
  readonly targetsOpponent?: boolean;
  /** Исходный текст — для лога/тестера */
  readonly text?: string;

  // --- CHOOSE_ONE («Choose one: …») ---
  /** Варианты выбора для UI: индекс + текст опции */
  readonly options?: ReadonlyArray<{ readonly index: number; readonly label: string }>;
  /** Сколько опций выбрать (default 1; «choose 2 different effects» = 2) */
  readonly chooseCount?: number;
  /** Эффекты каждой опции (параллельно options) — исполняются при резолве */
  readonly optionEffects?: ReadonlyArray<readonly CardEffect[]>;
  /** Карта-источник CHOOSE_ONE — контекст для исполнения эффектов опции */
  readonly card?: Card;
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
