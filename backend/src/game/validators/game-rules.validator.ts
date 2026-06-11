/**
 * GameRulesValidator - валидатор игровых действий для Unmatched
 *
 * Проверяет:
 * - validateManeuver() - выполнение манёвра
 * - validateMove() - перемещение
 * - validateAttack() - атака
 * - validateDefense() - защита
 * - validateTurn() - валидность хода
 * - isAdjacent() - смежность с контекстом
 * - canPlaceFighter() - размещение бойца
 * - canPlayCardAsAttack() / canPlayCardAsDefense()
 * - getHighGroundBonus() - бонус возвышенности (0 или 1)
 */

import { Injectable, Logger } from '@nestjs/common';
import { Position } from '../../game-engine/models';
import {
  ValidationResult,
  ValidationStatus,
  ValidationErrorCode,
  validResult,
  invalidResult,
  createError,
} from './validation-result';

// Типы из GameState
interface Fighter {
  id: string;
  ownerId: string;
  heroId: string;
  name: string;
  type: 'HERO' | 'MINION' | 'HUGE';
  health: number;
  maxHealth: number;
  position: Position;
  effects: any[];
}

interface Card {
  id: string;
  cardId: string;
  name: string;
  nameEn: string;
  nameRu: string;
  cardType: 'ATTACK' | 'DEFENSE' | 'SCHEME' | 'UNIVERSAL';
  attackValue?: number;
  defenseValue?: number;
  boostValue?: number;
  effects?: any[];
}

interface GameStatePlayer {
  userId: string;
  heroId: string;
  health: number;
  maxHealth: number;
  fighterIds: string[];
  isAlive: boolean;
}

interface GameState {
  gameId: string;
  sequenceNumber: number;
  phase: string;
  turnCount: number;
  currentTurnPlayerId: string;
  boardId?: string;
  players: GameStatePlayer[];
  fighters: Fighter[];
  decks: Record<string, any>;
  discardPiles: Record<string, any>;
  handZones: Record<string, any>;
  boardState: any;
  metadata: any;
}

// DTO для валидации
interface ManeuverDto {
  playerId: string;
  maneuverCardId: string;
  targets?: string[];
}

interface MoveDto {
  playerId: string;
  fighterId: string;
  to: Position;
  cardId?: string;
}

interface AttackDto {
  playerId: string;
  attackerId: string;
  defenderId: string;
  attackCardId: string;
}

interface DefenseDto {
  playerId: string;
  defenderId: string;
  defenseCardId: string;
}

/**
 * Зона героя для начального размещения
 */
interface PlacementZone {
  heroId: string;
  positions: Position[];
}

@Injectable()
export class GameRulesValidator {
  private readonly logger = new Logger(GameRulesValidator.name);

  // Хранилище зон размещения для героев
  private placementZones: Map<string, PlacementZone> = new Map();

  constructor() {
    this.initializePlacementZones();
  }

  /**
   * Валидировать выполнение манёвра
   */
  validateManeuver(state: GameState, dto: ManeuverDto): ValidationResult {
    const errors: any[] = [];

    // Проверяем, что это ход игрока
    const player = state.players.find((p) => p.userId === dto.playerId);
    if (!player) {
      errors.push(createError(ValidationErrorCode.PLAYER_NOT_FOUND, 'Игрок не найден'));
    }

    // Проверяем, что игрок жив
    if (player && !player.isAlive) {
      errors.push(createError(ValidationErrorCode.INVALID_STATE, 'Игрок выбыл'));
    }

    // Проверяем фазу
    if (state.phase !== 'ACTION') {
      errors.push(
        createError(
          ValidationErrorCode.INVALID_PHASE,
          'Манёвры можно выполнять только в фазу действий',
        ),
      );
    }

    // Проверяем наличие карты в руке
    const handZone = state.handZones[dto.playerId];
    if (!handZone) {
      errors.push(createError(ValidationErrorCode.CARD_NOT_IN_HAND, 'Карта не найдена в руке'));
    }

    // Проверяем, что карта действительно является манёвром
    if (handZone) {
      const card = handZone.cards.find((c: any) => c.id === dto.maneuverCardId);
      if (!card) {
        errors.push(createError(ValidationErrorCode.CARD_NOT_IN_HAND, 'Карта не найдена в руке'));
      } else if (card.cardType !== 'SCHEME') {
        errors.push(
          createError(ValidationErrorCode.INVALID_CARD_TYPE, 'Эта карта не является манёвром'),
        );
      }
    }

    return errors.length > 0 ? invalidResult(errors) : validResult();
  }

  /**
   * Валидировать перемещение
   */
  validateMove(state: GameState, dto: MoveDto): ValidationResult {
    const errors: any[] = [];

    // Проверяем, что это ход игрока
    if (state.currentTurnPlayerId !== dto.playerId) {
      errors.push(createError(ValidationErrorCode.NOT_YOUR_TURN, 'Сейчас не ваш ход'));
    }

    // Проверяем существование бойца
    const fighter = state.fighters.find((f) => f.id === dto.fighterId);
    if (!fighter) {
      errors.push(createError(ValidationErrorCode.FIGHTER_NOT_FOUND, 'Боец не найден'));
      return invalidResult(errors);
    }

    // Проверяем, что боец принадлежит игроку
    if (fighter.ownerId !== dto.playerId) {
      errors.push(
        createError(ValidationErrorCode.INVALID_MOVE_TARGET, 'Вы не управляете этим бойцом'),
      );
    }

    // TODO: Проверить валидность позиции через MovementService

    return errors.length > 0 ? invalidResult(errors) : validResult();
  }

  /**
   * Валидировать атаку
   */
  validateAttack(state: GameState, dto: AttackDto): ValidationResult {
    const errors: any[] = [];

    // Проверяем, что это ход игрока
    if (state.currentTurnPlayerId !== dto.playerId) {
      errors.push(createError(ValidationErrorCode.NOT_YOUR_TURN, 'Сейчас не ваш ход'));
    }

    // Проверяем существование атакующего
    const attacker = state.fighters.find((f) => f.id === dto.attackerId);
    if (!attacker) {
      errors.push(createError(ValidationErrorCode.FIGHTER_NOT_FOUND, 'Атакующий не найден'));
      return invalidResult(errors);
    }

    // Проверяем, что атакующий принадлежит игроку
    if (attacker.ownerId !== dto.playerId) {
      errors.push(
        createError(ValidationErrorCode.INVALID_ATTACK_TARGET, 'Вы не управляете этим бойцом'),
      );
    }

    // Проверяем существование защищающегося
    const defender = state.fighters.find((f) => f.id === dto.defenderId);
    if (!defender) {
      errors.push(createError(ValidationErrorCode.FIGHTER_NOT_FOUND, 'Защищающийся не найден'));
      return invalidResult(errors);
    }

    // Проверяем, что защищающийся не союзник
    if (attacker.ownerId === defender.ownerId) {
      errors.push(
        createError(ValidationErrorCode.INVALID_ATTACK_TARGET, 'Нельзя атаковать союзника'),
      );
    }

    // Проверяем смежность (Manhattan distance = 1)
    const distance =
      Math.abs(attacker.position.x - defender.position.x) +
      Math.abs(attacker.position.y - defender.position.y);
    if (distance > 1) {
      errors.push(
        createError(ValidationErrorCode.NOT_ADJACENT, 'Цель атаки должна быть на смежной позиции'),
      );
    }

    // Проверяем наличие карты атаки в руке
    const handZone = state.handZones[dto.playerId];
    if (!handZone) {
      errors.push(createError(ValidationErrorCode.CARD_NOT_IN_HAND, 'Карта не найдена в руке'));
      return invalidResult(errors);
    }

    const attackCard = handZone.cards.find((c: any) => c.id === dto.attackCardId);
    if (!attackCard) {
      errors.push(
        createError(ValidationErrorCode.CARD_NOT_IN_HAND, 'Карта атаки не найдена в руке'),
      );
    } else if (!this.canPlayCardAsAttack(state, attackCard)) {
      errors.push(
        createError(
          ValidationErrorCode.CANNOT_PLAY_AS_ATTACK,
          'Эту карту нельзя использовать для атаки',
        ),
      );
    }

    return errors.length > 0 ? invalidResult(errors) : validResult();
  }

  /**
   * Валидировать защиту
   */
  validateDefense(state: GameState, dto: DefenseDto): ValidationResult {
    const errors: any[] = [];

    // Проверяем существование защищающегося
    const defender = state.fighters.find((f) => f.id === dto.defenderId);
    if (!defender) {
      errors.push(createError(ValidationErrorCode.FIGHTER_NOT_FOUND, 'Боец не найден'));
      return invalidResult(errors);
    }

    // Проверяем, что защищающийся принадлежит игроку
    if (defender.ownerId !== dto.playerId) {
      errors.push(
        createError(ValidationErrorCode.INVALID_ATTACK_TARGET, 'Вы не управляете этим бойцом'),
      );
    }

    // Проверяем наличие карты защиты в руке
    const handZone = state.handZones[dto.playerId];
    if (!handZone) {
      errors.push(createError(ValidationErrorCode.CARD_NOT_IN_HAND, 'Карта не найдена в руке'));
      return invalidResult(errors);
    }

    const defenseCard = handZone.cards.find((c: any) => c.id === dto.defenseCardId);
    if (!defenseCard) {
      errors.push(
        createError(ValidationErrorCode.CARD_NOT_IN_HAND, 'Карта защиты не найдена в руке'),
      );
    } else if (!this.canPlayCardAsDefense(state, defenseCard)) {
      errors.push(
        createError(
          ValidationErrorCode.CANNOT_PLAY_AS_DEFENSE,
          'Эту карту нельзя использовать для защиты',
        ),
      );
    }

    return errors.length > 0 ? invalidResult(errors) : validResult();
  }

  /**
   * Валидировать ход игрока
   */
  validateTurn(state: GameState, playerId: string): ValidationResult {
    const errors: any[] = [];

    // Проверяем существование игрока
    const player = state.players.find((p) => p.userId === playerId);
    if (!player) {
      errors.push(createError(ValidationErrorCode.PLAYER_NOT_FOUND, 'Игрок не найден'));
      return invalidResult(errors);
    }

    // Проверяем, что игрок жив
    if (!player.isAlive) {
      errors.push(createError(ValidationErrorCode.INVALID_STATE, 'Игрок выбыл из игры'));
    }

    // Проверяем, что сейчас ход игрока
    if (state.currentTurnPlayerId !== playerId) {
      errors.push(createError(ValidationErrorCode.NOT_YOUR_TURN, 'Сейчас не ваш ход'));
    }

    return errors.length > 0 ? invalidResult(errors) : validResult();
  }

  /**
   * Проверить смежность с контекстом
   */
  isAdjacent(
    state: GameState,
    pos1: Position,
    pos2: Position,
    context: string = 'attack',
  ): boolean {
    const distance = Math.abs(pos1.x - pos2.x) + Math.abs(pos1.y - pos2.y);
    return distance === 1;
  }

  /**
   * Проверить, можно ли разместить бойца на позиции
   * - Зона героя для стартового размещения
   * - Если зона забита: смежные ячейки
   * - Жетоны тумана = свободные
   */
  canPlaceFighter(state: GameState, fighterId: string, pos: Position): boolean {
    const fighter = state.fighters.find((f) => f.id === fighterId);
    if (!fighter) return false;

    // Проверяем занятость позиции
    const occupant = state.fighters.find(
      (f) => f.position.x === pos.x && f.position.y === pos.y && f.id !== fighterId,
    );
    if (occupant) return false;

    // Проверяем зону героя
    const zone = this.placementZones.get(fighter.heroId);
    if (zone) {
      const inZone = zone.positions.some((zp) => zp.x === pos.x && zp.y === pos.y);
      if (inZone) return true;

      // Если зона забита, проверяем смежные позиции
      const zoneOccupied = zone.positions.every((zp) =>
        state.fighters.some((f) => f.position.x === zp.x && f.position.y === zp.y),
      );
      if (zoneOccupied) {
        // Проверяем смежность с зоной
        const isAdjacent = zone.positions.some((zp) => this.isAdjacent(state, zp, pos, 'movement'));
        return isAdjacent;
      }
    }

    return true;
  }

  /**
   * Проверить, можно ли сыграть карту как атаку
   */
  canPlayCardAsAttack(state: GameState, card: Card): boolean {
    // UNIVERSAL карты можно играть как атаку
    if (card.cardType === 'UNIVERSAL') return true;

    // ATTACK карты можно играть как атаку
    if (card.cardType === 'ATTACK') return true;

    // SCHEME карты обычно нельзя использовать как прямую атаку
    if (card.cardType === 'SCHEME') return false;

    // DEFENSE карты нельзя использовать как атаку
    if (card.cardType === 'DEFENSE') return false;

    return false;
  }

  /**
   * Проверить, можно ли сыграть карту как защиту
   */
  canPlayCardAsDefense(state: GameState, card: Card): boolean {
    // UNIVERSAL карты можно играть как защиту
    if (card.cardType === 'UNIVERSAL') return true;

    // DEFENSE карты можно играть как защиту
    if (card.cardType === 'DEFENSE') return true;

    // ATTACK карты нельзя использовать как защиту
    if (card.cardType === 'ATTACK') return false;

    // SCHEME карты нельзя использовать как защиту
    if (card.cardType === 'SCHEME') return false;

    return false;
  }

  /**
   * Получить бонус возвышенности к атаке
   * Возвращает 0 или 1 (бонус НЕ суммируется)
   */
  getHighGroundBonus(state: GameState, attackerPos: Position, defenderPos: Position): number {
    // TODO: Реализовать проверку возвышенности через board features
    return 0;
  }

  /**
   * Валидировать размещение бойца на старте игры
   */
  validateInitialPlacement(
    state: GameState,
    playerId: string,
    fighterId: string,
    position: Position,
  ): ValidationResult {
    const errors: any[] = [];

    // Проверяем фазу
    if (state.phase !== 'SETUP') {
      errors.push(
        createError(ValidationErrorCode.INVALID_PHASE, 'Размещение возможно только в фазу SETUP'),
      );
    }

    // Проверяем, что можно разместить на позиции
    if (!this.canPlaceFighter(state, fighterId, position)) {
      errors.push(
        createError(
          ValidationErrorCode.INVALID_PLACEMENT_ZONE,
          'Невозможно разместить бойца на указанной позиции',
        ),
      );
    }

    return errors.length > 0 ? invalidResult(errors) : validResult();
  }

  /**
   * Инициализировать зоны размещения для героев
   */
  private initializePlacementZones(): void {
    // Зоны для каждого героя
    // В реальной конфигурации эти данные должны загружаться из БД

    // Пример: зона для Артура (верхний левый угол)
    this.placementZones.set('arthur', {
      heroId: 'arthur',
      positions: [
        { x: 0, y: 0 },
        { x: 1, y: 0 },
        { x: 0, y: 1 },
      ],
    });

    // Пример: зона для Робин Гуда (верхний правый угол)
    this.placementZones.set('robin-hood', {
      heroId: 'robin-hood',
      positions: [
        { x: 19, y: 0 },
        { x: 18, y: 0 },
        { x: 19, y: 1 },
      ],
    });

    // Другие герои...
  }

  /**
   * Добавить зону размещения
   */
  addPlacementZone(heroId: string, positions: Position[]): void {
    this.placementZones.set(heroId, {
      heroId,
      positions,
    });
  }

  /**
   * Получить зону размещения героя
   */
  getPlacementZone(heroId: string): PlacementZone | undefined {
    return this.placementZones.get(heroId);
  }
}
