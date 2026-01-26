import { ConflictException } from '@nestjs/common';

/**
 * Исключение при нарушении optimistic lock
 * Выбрасывается при concurrent modification
 */
export class ConcurrentModificationException extends ConflictException {
  constructor(expectedSequence: number, actualSequence: number) {
    super(
      `Concurrent modification detected. Expected sequence ${expectedSequence}, got ${actualSequence}. ` +
        `Please refresh and try again.`,
    );
    this.name = 'ConcurrentModificationException';
  }
}

/**
 * Исключение при отсутствии доступа к игре
 */
export class GameAccessDeniedException extends ConflictException {
  constructor(gameId: string) {
    super(`You do not have access to game ${gameId}`);
    this.name = 'GameAccessDeniedException';
  }
}

/**
 * Исключение при попытке недопустимого действия в текущем статусе игры
 */
export class InvalidGameStatusException extends ConflictException {
  constructor(currentStatus: string, requiredStatus: string[]) {
    super(`Invalid game status: ${currentStatus}. ` + `Required: ${requiredStatus.join(' or ')}`);
    this.name = 'InvalidGameStatusException';
  }
}

/**
 * Исключение при превышении лимита активных игр
 */
export class MaxActiveGamesException extends ConflictException {
  constructor(current: number, max: number) {
    super(`You have ${current} active games. Maximum allowed: ${max}`);
    this.name = 'MaxActiveGamesException';
  }
}
