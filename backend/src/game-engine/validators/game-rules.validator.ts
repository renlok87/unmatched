/**
 * Game Rules Validator
 *
 * Проверяет соответствие действий правилам игры Unmatched.
 */

import { Injectable, Logger } from '@nestjs/common';
import type { GameState, Fighter, Position } from '../models';
import { getFighterMovement, positionEqual } from '../models';
import { AdjacencyService } from '../engine/adjacency.service';

export interface ValidationResult {
  readonly valid: boolean;
  readonly error?: string;
  readonly code?: string;
}

export interface MoveAction {
  readonly fighterId: string;
  readonly from: Position;
  readonly to: Position;
  readonly cost: number;
}

export interface AttackAction {
  readonly attackerId: string;
  readonly targetId: string;
  readonly cardId: string;
}

@Injectable()
export class GameRulesValidator {
  private readonly logger = new Logger(GameRulesValidator.name);

  constructor(private readonly adjacency: AdjacencyService) {}

  /**
   * Проверить валидность хода
   */
  validateMove(state: GameState, action: MoveAction): ValidationResult {
    const fighter = state.fighters.find((f) => f.id === action.fighterId);

    if (!fighter) {
      return { valid: false, error: 'Fighter not found', code: 'FIGHTER_NOT_FOUND' };
    }

    // Проверяем, что это ход текущего игрока
    const currentPlayer = state.players.find((p) => p.userId === state.currentTurnPlayerId);
    if (!fighter.ownerId.includes(state.currentTurnPlayerId)) {
      return { valid: false, error: 'Not your turn', code: 'NOT_YOUR_TURN' };
    }

    // Проверяем фазу игры
    if (state.phase !== 'ACTION_MANEUVER') {
      return {
        valid: false,
        error: 'Can only move during maneuver phase',
        code: 'INVALID_PHASE',
      };
    }

    // Проверяем, что боец жив
    if (fighter.health <= 0) {
      return { valid: false, error: 'Fighter is dead', code: 'FIGHTER_DEAD' };
    }

    // Проверяем валидность позиции
    if (!this.isValidPosition(state, action.to)) {
      return { valid: false, error: 'Invalid target position', code: 'INVALID_POSITION' };
    }

    // Проверяем, что целевая клетка не занята
    const occupied = state.fighters.some(
      (f) =>
        f.id !== action.fighterId && f.position.x === action.to.x && f.position.y === action.to.y,
    );
    if (occupied) {
      return { valid: false, error: 'Target position is occupied', code: 'POSITION_OCCUPIED' };
    }

    return { valid: true };
  }

  /**
   * Проверить валидность атаки
   */
  validateAttack(state: GameState, action: AttackAction): ValidationResult {
    const attacker = state.fighters.find((f) => f.id === action.attackerId);
    const target = state.fighters.find((f) => f.id === action.targetId);

    if (!attacker) {
      return { valid: false, error: 'Attacker not found', code: 'ATTACKER_NOT_FOUND' };
    }

    if (!target) {
      return { valid: false, error: 'Target not found', code: 'TARGET_NOT_FOUND' };
    }

    // Проверяем фазу игры
    if (state.phase !== 'ACTION_ATTACK') {
      return {
        valid: false,
        error: 'Can only attack during attack phase',
        code: 'INVALID_PHASE',
      };
    }

    // Проверяем, что атакующий жив
    if (attacker.health <= 0) {
      return { valid: false, error: 'Attacker is dead', code: 'ATTACKER_DEAD' };
    }

    // Проверяем, что цель жива
    if (target.health <= 0) {
      return { valid: false, error: 'Target is dead', code: 'TARGET_DEAD' };
    }

    // Проверяем, что цель в радиусе атаки
    const distance =
      Math.abs(attacker.position.x - target.position.x) +
      Math.abs(attacker.position.y - target.position.y);
    if (distance > 1) {
      return { valid: false, error: 'Target out of range', code: 'OUT_OF_RANGE' };
    }

    // Проверяем, что карта есть в руке
    // TODO: Добавить проверку карты

    return { valid: true };
  }

  /**
   * Проверить валидность атаки (с параметрами по отдельности)
   */
  validateAttackWithParams(
    state: GameState,
    attackerId: string,
    targetId: string,
    cardId: string,
    userId: string,
  ): ValidationResult {
    // Проверяем, что это ход игрока
    const canAct = this.canPlayerAct(state, userId);
    if (!canAct.valid) {
      return canAct;
    }

    const attacker = state.fighters.find((f) => f.id === attackerId);
    const target = state.fighters.find((f) => f.id === targetId);

    if (!attacker) {
      return { valid: false, error: 'Attacker not found', code: 'ATTACKER_NOT_FOUND' };
    }

    if (!target) {
      return { valid: false, error: 'Target not found', code: 'TARGET_NOT_FOUND' };
    }

    if (attacker.ownerId !== userId) {
      return { valid: false, error: 'Not your attacker', code: 'NOT_YOUR_FIGHTER' };
    }

    // Проверяем фазу игры: атака разрешена из любой action-фазы
    // (экономика «2 действия за ход» — атака может быть первым действием;
    // ACTION_ATTACK — валидная legacy-фаза старых сейвов)
    if (state.phase !== 'ACTION_MANEUVER' && state.phase !== 'ACTION_ATTACK') {
      return {
        valid: false,
        error: 'Can only attack during action phase',
        code: 'INVALID_PHASE',
      };
    }

    // Проверяем, что атакующий жив
    if (attacker.health <= 0) {
      return { valid: false, error: 'Attacker is dead', code: 'ATTACKER_DEAD' };
    }

    // Проверяем, что цель жива
    if (target.health <= 0) {
      return { valid: false, error: 'Target is dead', code: 'TARGET_DEAD' };
    }

    // Проверяем, что карта в руке
    const hand = state.handZones[userId];
    if (!hand) {
      return { valid: false, error: 'Hand not found', code: 'HAND_NOT_FOUND' };
    }

    const card = hand.cards.find((c) => c.id === cardId || c.cardId === cardId);
    if (!card) {
      return { valid: false, error: 'Card not in hand', code: 'CARD_NOT_IN_HAND' };
    }

    // Атаковать можно только ATTACK/VERSATILE (UNIVERSAL — легаси-синоним)
    if (
      card.cardType !== 'ATTACK' &&
      card.cardType !== 'VERSATILE' &&
      card.cardType !== 'UNIVERSAL'
    ) {
      return {
        valid: false,
        error: `Картой типа ${card.cardType} нельзя атаковать`,
        code: 'INVALID_CARD_TYPE',
      };
    }

    // bannerName: именная карта играется только СВОИМ бойцом
    // ('Clutching Claws' с банером Harpy — только гарпией)
    const bannerCheck = this.validateBanner(state, card, attacker);
    if (!bannerCheck.valid) return bannerCheck;

    return { valid: true };
  }

  /**
   * Проверить, может ли игрок совершить действие
   */
  canPlayerAct(state: GameState, playerId: string): ValidationResult {
    if (state.currentTurnPlayerId !== playerId) {
      return { valid: false, error: 'Not your turn', code: 'NOT_YOUR_TURN' };
    }

    const player = state.players.find((p) => p.userId === playerId);
    if (!player || !player.isAlive) {
      return { valid: false, error: 'Player is not in game', code: 'PLAYER_NOT_IN_GAME' };
    }

    return { valid: true };
  }

  /**
   * Проверить валидность позиции
   */
  private isValidPosition(state: GameState, pos: Position): boolean {
    if (pos.x < 0 || pos.x >= state.boardState.width) {
      return false;
    }
    if (pos.y < 0 || pos.y >= state.boardState.height) {
      return false;
    }

    const cell = state.boardState.cells[pos.y]?.[pos.x];
    if (!cell || cell.type === 'wall' || cell.type === 'obstacle') {
      return false;
    }

    return true;
  }

  /**
   * Проверить, может ли игра закончиться
   * Боец считается побеждённым, если его health <= 0
   * Игрок считается побеждённым, если все его бойцы побеждены
   */
  checkGameEnd(state: GameState): { ended: boolean; winnerId?: string } {
    // Проверяем здоровье бойцов для каждого игрока
    const alivePlayers = state.players.filter((player) => {
      const playerFighters = state.fighters.filter((f) => f.ownerId === player.userId);
      // Игрок жив, если у него есть хотя бы один боец с health > 0
      return playerFighters.some((f) => f.health > 0);
    });

    // Игра заканчивается, когда остаётся 0 или 1 живой игрок
    if (alivePlayers.length <= 1) {
      return {
        ended: true,
        winnerId: alivePlayers[0]?.userId,
      };
    }

    return { ended: false };
  }

  /**
   * Проверить валидность манёвра (перемещение + карта)
   */
  validateManeuver(
    state: GameState,
    fighterId: string,
    boostCardId: string | undefined,
    path: readonly Position[],
    userId: string,
  ): ValidationResult {
    const fighter = state.fighters.find((f) => f.id === fighterId);

    if (!fighter) {
      return { valid: false, error: 'Fighter not found', code: 'FIGHTER_NOT_FOUND' };
    }

    if (fighter.ownerId !== userId) {
      return { valid: false, error: 'Not your fighter', code: 'NOT_YOUR_FIGHTER' };
    }

    if (fighter.health <= 0) {
      return { valid: false, error: 'Fighter is defeated', code: 'FIGHTER_DEFEATED' };
    }

    // IMMOBILIZE («cannot leave their space this turn»)
    if (fighter.effects.some((e) => e.type === 'immobilized')) {
      return {
        valid: false,
        error: 'Боец обездвижен до конца хода (эффект карты)',
        code: 'FIGHTER_IMMOBILIZED',
      };
    }

    // Проверяем фазу: манёвр разрешён из любой action-фазы (экономика
    // «2 действия за ход»; ACTION_ATTACK — валидная legacy-фаза старых сейвов)
    if (state.phase !== 'ACTION_MANEUVER' && state.phase !== 'ACTION_ATTACK') {
      return {
        valid: false,
        error: 'Can only maneuver during action phase',
        code: 'INVALID_PHASE',
      };
    }

    // BOOST-карта (опционально): обязана быть в руке, даёт +boostValue к ходам.
    // Манёвр БЕЗ карты — валиден (правила Unmatched: добор 1 + движение).
    const hand = state.handZones[userId];
    let boostValue = 0;
    if (boostCardId) {
      if (!hand) {
        return { valid: false, error: 'Hand not found', code: 'HAND_NOT_FOUND' };
      }
      const card = hand.cards.find((c) => c.id === boostCardId || c.cardId === boostCardId);
      if (!card) {
        return { valid: false, error: 'Boost card not in hand', code: 'CARD_NOT_IN_HAND' };
      }
      boostValue = card.boostValue ?? 0;
    }

    // Проверяем путь
    if (!path || path.length === 0) {
      return { valid: false, error: 'Path is empty', code: 'EMPTY_PATH' };
    }

    for (const pos of path) {
      if (!this.isValidPosition(state, pos)) {
        return { valid: false, error: 'Invalid position in path', code: 'INVALID_POSITION' };
      }
    }

    // Очки движения: movement бойца + BOOST сброшенной карты
    const allowance = getFighterMovement(fighter) + boostValue;
    if (path.length > allowance) {
      return {
        valid: false,
        error: `Путь длиной ${path.length} превышает очки движения бойца (${allowance})`,
        code: 'NOT_ENOUGH_MOVEMENT',
      };
    }

    // Пошаговая смежность: каждый шаг — на соседнюю клетку (manhattan === 1,
    // та же метрика, что isAdjacent в adjacency.service); заодно исключает дубли позиций
    let prev = fighter.position;
    for (const pos of path) {
      if (Math.abs(pos.x - prev.x) + Math.abs(pos.y - prev.y) !== 1) {
        return {
          valid: false,
          error: `Шаг (${prev.x},${prev.y})→(${pos.x},${pos.y}) не является ходом на соседнюю клетку`,
          code: 'INVALID_STEP',
        };
      }
      prev = pos;
    }

    return { valid: true };
  }

  /**
   * Проверить валидность простого перемещения
   */
  validateMovement(
    state: GameState,
    fighterId: string,
    target: Position,
    userId: string,
  ): ValidationResult {
    const fighter = state.fighters.find((f) => f.id === fighterId);

    if (!fighter) {
      return { valid: false, error: 'Fighter not found', code: 'FIGHTER_NOT_FOUND' };
    }

    if (fighter.ownerId !== userId) {
      return { valid: false, error: 'Not your fighter', code: 'NOT_YOUR_FIGHTER' };
    }

    if (fighter.health <= 0) {
      return { valid: false, error: 'Fighter is defeated', code: 'FIGHTER_DEFEATED' };
    }

    // IMMOBILIZE («cannot leave their space this turn») — снимается в advanceTurn
    if (fighter.effects.some((e) => e.type === 'immobilized')) {
      return {
        valid: false,
        error: 'Боец обездвижен до конца хода (эффект карты)',
        code: 'FIGHTER_IMMOBILIZED',
      };
    }

    if (!this.isValidPosition(state, target)) {
      return { valid: false, error: 'Invalid target position', code: 'INVALID_POSITION' };
    }

    // Перемещение в свою же клетку — no-op (дистанция 0), очки движения не тратятся
    if (positionEqual(target, fighter.position)) {
      return { valid: true };
    }

    // Проверка очков движения: цель должна быть достижима BFS по проходимым
    // клеткам (4-связно, как isAdjacent), занятые живыми бойцами клетки блокируют путь
    const allowance = getFighterMovement(fighter);
    const blockedPositions = new Set(
      state.fighters
        .filter((f) => f.id !== fighterId && f.health > 0)
        .map((f) => `${f.position.x}:${f.position.y}`),
    );
    const reachable = this.adjacency.getReachableCells(
      state.boardState,
      fighter.position,
      allowance,
      { blockedPositions },
    );
    if (!reachable.has(`${target.x}:${target.y}`)) {
      return {
        valid: false,
        error: `Недостаточно очков движения: до клетки (${target.x}, ${target.y}) не добраться за ${allowance} шаг(ов) по проходимым клеткам`,
        code: 'NOT_ENOUGH_MOVEMENT',
      };
    }

    return { valid: true };
  }

  /**
   * Проверить валидность защиты
   */
  validateDefense(state: GameState, cardId: string, userId: string): ValidationResult {
    const hand = state.handZones[userId];
    if (!hand) {
      return { valid: false, error: 'Hand not found', code: 'HAND_NOT_FOUND' };
    }

    const card = hand.cards.find((c) => c.id === cardId || c.cardId === cardId);
    if (!card) {
      return { valid: false, error: 'Card not in hand', code: 'CARD_NOT_IN_HAND' };
    }

    // VERSATILE — реальный тип из БД, играется и как атака, и как защита
    // (UNIVERSAL — легаси-синоним, в текущих данных не встречается)
    if (
      card.cardType !== 'DEFENSE' &&
      card.cardType !== 'UNIVERSAL' &&
      card.cardType !== 'VERSATILE'
    ) {
      return {
        valid: false,
        error: 'Card must be DEFENSE, VERSATILE or UNIVERSAL',
        code: 'INVALID_CARD_TYPE',
      };
    }

    return { valid: true };
  }

  /**
   * Проверить валидность конца хода
   */
  validateEndTurn(state: GameState, userId: string): ValidationResult {
    const canAct = this.canPlayerAct(state, userId);
    if (!canAct.valid) {
      return canAct;
    }

    // Можно закончить ход из любой action фазы
    if (
      state.phase !== 'ACTION_MANEUVER' &&
      state.phase !== 'ACTION_ATTACK' &&
      state.phase !== 'TURN_END'
    ) {
      return {
        valid: false,
        error: 'Cannot end turn in current phase',
        code: 'INVALID_PHASE',
      };
    }

    return { valid: true };
  }

  /**
   * Проверить валидность пасса
   */
  validatePass(state: GameState, userId: string): ValidationResult {
    const canAct = this.canPlayerAct(state, userId);
    if (!canAct.valid) {
      return canAct;
    }

    if (
      state.phase !== 'ACTION_MANEUVER' &&
      state.phase !== 'ACTION_ATTACK'
    ) {
      return {
        valid: false,
        error: 'Cannot pass in current phase',
        code: 'INVALID_PHASE',
      };
    }

    return { valid: true };
  }

  /**
   * Проверить валидность переключения двери
   */
  validateToggleDoor(
    state: GameState,
    x: number,
    y: number,
    userId: string,
  ): ValidationResult {
    const canAct = this.canPlayerAct(state, userId);
    if (!canAct.valid) {
      return canAct;
    }

    if (
      state.phase !== 'ACTION_MANEUVER' &&
      state.phase !== 'ACTION_ATTACK'
    ) {
      return {
        valid: false,
        error: 'Cannot toggle door in current phase',
        code: 'INVALID_PHASE',
      };
    }

    const doorKey = `${x}:${y}`;
    const doors = (state.boardState as any).doors || {};
    if (!(doorKey in doors)) {
      return {
        valid: false,
        error: `No door at (${x}, ${y})`,
        code: 'DOOR_NOT_FOUND',
      };
    }

    return { valid: true };
  }

  /**
   * bannerName-валидация: именная карта играется только своим бойцом.
   * Неизвестный банер (не матчит ни одного бойца игры — грязные данные)
   * НЕ блокирует: warn + разрешить.
   */
  validateBanner(
    state: GameState,
    card: { bannerName?: string; name?: string },
    fighter: Fighter,
  ): ValidationResult {
    const banner = card.bannerName?.trim();
    if (!banner || banner.toLowerCase() === 'any') return { valid: true };

    if (bannerAllows(banner, fighter)) return { valid: true };

    // Банер вообще известен в этой игре? (опечатки/грязные данные → разрешить)
    const known = state.fighters.some((f) => bannerAllows(banner, f));
    if (!known) {
      this.logger.warn(
        `bannerName «${banner}» не матчит ни одного бойца игры — карта разрешена (грязные данные?)`,
        { card: card.name },
      );
      return { valid: true };
    }

    return {
      valid: false,
      error: `Карту с банером «${banner}» может играть только этот боец (играет ${fighter.name})`,
      code: 'BANNER_MISMATCH',
    };
  }
}

/**
 * Матчит ли банер карты бойца: «Harpy» = «Harpy 2» (срез числового суффикса),
 * «Arthur» = «King Arthur» (банер — слово в полном имени). Регистронезависимо.
 */
export function bannerAllows(banner: string, fighter: { name: string }): boolean {
  const b = banner.trim().toLowerCase();
  const full = fighter.name.trim().toLowerCase();
  const base = full.replace(/\s+\d+$/, '');
  if (b === full || b === base) return true;
  // банер как целое слово внутри имени ('arthur' в 'king arthur')
  const words = base.split(/\s+/);
  return words.includes(b);
}
