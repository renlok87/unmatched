/**
 * GameTurnGuard
 *
 * Проверяет, что сейчас ход указанного игрока.
 * Используется для защиты мутаций, доступных только текущему игроку.
 */

import { Injectable, CanActivate, ExecutionContext, BadRequestException } from '@nestjs/common';
import { GamePhase } from '../dto';
import { GameStateService } from '../game-state.service';

/**
 * Опции для проверки очереди хода
 */
export interface TurnGuardOptions {
  /**
   * Требуемые фазы для действий
   */
  allowedPhases?: GamePhase[];

  /**
   * Проверять только фазу, не проверять playerId
   */
  phaseOnly?: boolean;
}

/**
 * Декоратор для указания требуемых фаз
 */
export const AllowedPhases =
  (...phases: GamePhase[]) =>
  (target: any, propertyKey: string, descriptor: PropertyDescriptor) => {
    Reflect.defineMetadata('allowedPhases', phases, descriptor.value);
  };

@Injectable()
export class GameTurnGuard implements CanActivate {
  constructor(protected readonly gameStateService: GameStateService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const ctx = context.getArgByIndex<{
      req?: { user?: { id?: string } };
    }>(2);

    const userId = ctx?.req?.user?.id;
    if (!userId) {
      return false;
    }

    // Получаем gameId из аргументов мутации
    const args = context.getArgByIndex(1);
    const input = args?.input || args;

    const gameId = input?.gameId || args?.gameId;
    if (!gameId) {
      return false;
    }

    // Загружаем состояние игры
    const state = await this.gameStateService.loadState(gameId);

    // Проверяем фазу
    const allowedPhases = this.getAllowedPhases(context);
    if (allowedPhases.length > 0 && !allowedPhases.includes(state.phase)) {
      throw new BadRequestException(
        `Invalid phase. Current: ${state.phase}, Required: ${allowedPhases.join(' or ')}`,
      );
    }

    // Проверяем, что сейчас ход игрока
    if (state.currentTurnPlayerId !== userId) {
      throw new BadRequestException(`Not your turn. Current player: ${state.currentTurnPlayerId}`);
    }

    return true;
  }

  /**
   * Получить разрешённые фазы из метаданных или использовать дефолтные
   */
  protected getAllowedPhases(context: ExecutionContext): GamePhase[] {
    const handler = context.getHandler();
    const metadata = Reflect.getMetadata('allowedPhases', handler);

    if (metadata && Array.isArray(metadata)) {
      return metadata as GamePhase[];
    }

    return [];
  }
}

/**
 * Упрощённые версии guard с предустановленными фазами
 */

/**
 * @deprecated Экономика «2 действия за ход»: атака разрешена из любой
 * action-фазы — используйте ActionPhaseGuard. Класс оставлен (зарегистрирован
 * в games.module), не удалять без чистки модуля.
 */
@Injectable()
export class AttackPhaseGuard extends GameTurnGuard {
  constructor(gameStateService: GameStateService) {
    super(gameStateService);
  }

  protected getAllowedPhases(): GamePhase[] {
    return [GamePhase.ACTION_ATTACK];
  }
}

/**
 * @deprecated Экономика «2 действия за ход»: манёвр разрешён из любой
 * action-фазы — используйте ActionPhaseGuard. Класс оставлен (зарегистрирован
 * в games.module), не удалять без чистки модуля.
 */
@Injectable()
export class ManeuverPhaseGuard extends GameTurnGuard {
  constructor(gameStateService: GameStateService) {
    super(gameStateService);
  }

  protected getAllowedPhases(): GamePhase[] {
    return [GamePhase.ACTION_MANEUVER];
  }
}

/**
 * Guard для действий, доступных в любой action-фазе хода:
 * maneuver/moveFighter/attack/endTurn/pass/toggleDoor (экономика «2 действия
 * за ход» — порядок действий свободный). ACTION_ATTACK остаётся валидной
 * legacy-фазой для idle-состояний, сохранённых до фикса.
 */
@Injectable()
export class ActionPhaseGuard extends GameTurnGuard {
  constructor(gameStateService: GameStateService) {
    super(gameStateService);
  }

  protected getAllowedPhases(): GamePhase[] {
    return [GamePhase.ACTION_MANEUVER, GamePhase.ACTION_ATTACK];
  }
}

@Injectable()
export class CombatPhaseGuard extends GameTurnGuard {
  constructor(gameStateService: GameStateService) {
    super(gameStateService);
  }

  protected getAllowedPhases(): GamePhase[] {
    return [GamePhase.COMBAT, GamePhase.COMBAT_RESOLVE];
  }
}

/**
 * Guard для фазы атаки (после объявления атаки)
 * Используется только для playDefense - защита может быть сыграна
 * только защищающимся игроком
 */
@Injectable()
export class DefensePlayGuard extends GameTurnGuard {
  constructor(gameStateService: GameStateService) {
    super(gameStateService);
  }

  protected getAllowedPhases(): GamePhase[] {
    return [GamePhase.COMBAT];
  }

  // Переопределяем canActivate для проверки защищающегося игрока
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const ctx = context.getArgByIndex<{
      req?: { user?: { id?: string } };
    }>(2);

    const userId = ctx?.req?.user?.id;
    if (!userId) {
      return false;
    }

    // Получаем gameId из аргументов мутации
    const args = context.getArgByIndex(1);
    const input = args?.input || args;

    const gameId = input?.gameId || args?.gameId;
    if (!gameId) {
      return false;
    }

    // Загружаем состояние игры
    const state = await this.gameStateService.loadState(gameId);

    // Проверяем фазу
    if (state.phase !== GamePhase.COMBAT) {
      throw new BadRequestException(
        `Invalid phase for defense. Current: ${state.phase}, Required: COMBAT`,
      );
    }

    // Проверяем, что пользователь - защищающийся игрок (не атакующий)
    const combatInfo = state.metadata.combatInfo;
    if (!combatInfo) {
      throw new BadRequestException('No combat in progress');
    }

    if (combatInfo.attackerId && combatInfo.defenderId) {
      // Находим владельца атакующего бойца
      const attacker = state.fighters.find((f) => f.id === combatInfo.attackerId);
      if (attacker && attacker.ownerId === userId) {
        throw new BadRequestException('Attacker cannot play defense');
      }

      // Проверяем, что userId - защищающийся
      if (combatInfo.defenderId !== userId) {
        throw new BadRequestException('Only defender can play defense');
      }
    }

    return true;
  }
}

/**
 * Guard для разрешения боя
 * Доступен как атакующему, так и защищающемуся после истечения таймаута
 */
@Injectable()
export class CombatResolveGuard extends GameTurnGuard {
  constructor(gameStateService: GameStateService) {
    super(gameStateService);
  }

  protected getAllowedPhases(): GamePhase[] {
    return [GamePhase.COMBAT, GamePhase.COMBAT_RESOLVE];
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const ctx = context.getArgByIndex<{
      req?: { user?: { id?: string } };
    }>(2);

    const userId = ctx?.req?.user?.id;
    if (!userId) {
      return false;
    }

    // Получаем gameId из аргументов мутации
    const args = context.getArgByIndex(1);
    const input = args?.input || args;

    const gameId = input?.gameId || args?.gameId;
    if (!gameId) {
      return false;
    }

    // Загружаем состояние игры
    const state = await this.gameStateService.loadState(gameId);

    // Проверяем фазу
    const allowedPhases = [GamePhase.COMBAT, GamePhase.COMBAT_RESOLVE];
    if (!allowedPhases.includes(state.phase)) {
      throw new BadRequestException(
        `Invalid phase for combat resolve. Current: ${state.phase}`,
      );
    }

    const combatInfo = state.metadata.combatInfo;
    if (!combatInfo) {
      throw new BadRequestException('No combat in progress');
    }

    // Проверяем, что пользователь - участник боя
    const attacker = state.fighters.find((f) => f.id === combatInfo.attackerId);
    const isAttacker = attacker?.ownerId === userId;
    const isDefender = combatInfo.defenderId === userId;

    if (!isAttacker && !isDefender) {
      throw new BadRequestException('Only combat participants can resolve combat');
    }

    return true;
  }
}
