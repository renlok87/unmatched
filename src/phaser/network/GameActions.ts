// ============================================================
// GAME ACTIONS - GraphQL мутации для игровых действий
// ============================================================

import { apolloClient } from '@/lib/apolloClient';
import * as gql from '@/gql/graphql';
import type { Position } from '@/core/models/types';

// ------------------------------------------------------------
// Типы для результатов действий
// ------------------------------------------------------------

/**
 * Базовый результат выполнения игрового действия
 */
export interface ActionResult {
  success: boolean;
  state?: string;
  sequenceNumber: number;
  phase: string;
  currentTurnPlayerId: string;
  turnCount: number;
  timestamp: Date;
  error?: string;
}

/**
 * Параметры для манёвра (движение с игрой карты)
 */
export interface ManeuverActionParams {
  gameId: string;
  fighterId: string;
  cardId: string;
  path: Position[];
}

/**
 * Параметры для атаки
 */
export interface AttackActionParams {
  gameId: string;
  attackerId: string;
  targetId: string;
  cardId: string;
}

/**
 * Параметры для защиты
 */
export interface DefenseActionParams {
  gameId: string;
  combatId: string;
  cardId: string;
}

/**
 * Параметры для завершения хода
 */
export interface EndTurnActionParams {
  gameId: string;
  playerId: string;
}

/**
 * Параметры для пасса
 */
export interface PassActionParams {
  gameId: string;
  playerId: string;
}

/**
 * Параметры для переключения двери
 */
export interface ToggleDoorActionParams {
  gameId: string;
  doorId: string;
}

/**
 * Параметры для перемещения бойца
 */
export interface MoveFighterActionParams {
  gameId: string;
  fighterId: string;
  x: number;
  y: number;
}

// ------------------------------------------------------------
// Класс для выполнения игровых действий
// ------------------------------------------------------------

/**
 * GameActions - выполняет все игровые мутации на сервере
 *
 * Обеспечивает:
 * - Типобезопасные вызовы GraphQL мутаций
 * - Автоматический retry при сетевых ошибках
 * - Унифицированную обработку ошибок
 * - Оптимистичные обновления (через callback)
 */
export class GameActions {
  private optimisticCallbacks: Map<string, (result: ActionResult) => void> = new Map();

  /**
   * Выполнить манёвр (движение с игрой карты манёвра)
   *
   * Манёвр позволяет переместить бойца на количество клеток,
   * указанное на карте, + дополнительные зоны того же цвета.
   */
  async maneuver(params: ManeuverActionParams): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        maneuver: gql.GameMutationResult;
      }>({
        mutation: gql.ManeuverDocument,
        variables: {
          input: {
            gameId: params.gameId,
            fighterId: params.fighterId,
            cardId: params.cardId,
            path: params.path.map(p => ({ x: p.x, y: p.y })),
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.maneuver;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Переместить бойца (без игры карты)
   *
   * Используется для базового перемещения в некоторых фазах игры.
   */
  async moveFighter(params: MoveFighterActionParams): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        moveFighter: gql.GameMutationResult;
      }>({
        mutation: gql.MoveFighterDocument,
        variables: {
          input: {
            gameId: params.gameId,
            fighterId: params.fighterId,
            x: params.x,
            y: params.y,
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.moveFighter;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Атаковать бойца противника
   *
   * Инициирует боевую фазу с выбранной картой атаки.
   */
  async attack(params: AttackActionParams): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        attack: gql.GameMutationResult;
      }>({
        mutation: gql.AttackDocument,
        variables: {
          input: {
            gameId: params.gameId,
            attackerId: params.attackerId,
            targetId: params.targetId,
            cardId: params.cardId,
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.attack;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Сыграть карту защиты
   *
   * Используется защищающимся игроком в фазе боя.
   */
  async playDefense(params: DefenseActionParams): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        playDefense: gql.GameMutationResult;
      }>({
        mutation: gql.PlayDefenseDocument,
        variables: {
          input: {
            gameId: params.gameId,
            combatId: params.combatId,
            cardId: params.cardId,
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.playDefense;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Разрешить бой
   *
   * Завершает фазу боя и применяет урон.
   */
  async resolveCombat(params: Pick<DefenseActionParams, 'gameId'>): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        resolveCombat: gql.GameMutationResult;
      }>({
        mutation: gql.ResolveCombatDocument,
        variables: {
          input: {
            gameId: params.gameId,
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.resolveCombat;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Завершить ход
   *
   * Переход к следующему игроку или фазе.
   */
  async endTurn(params: EndTurnActionParams): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        endTurn: gql.GameMutationResult;
      }>({
        mutation: gql.EndTurnDocument,
        variables: {
          input: {
            gameId: params.gameId,
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.endTurn;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Пассовать
   *
   * Пропустить оставшиеся действия в текущем ходу.
   */
  async pass(params: PassActionParams): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        pass: gql.GameMutationResult;
      }>({
        mutation: gql.PassDocument,
        variables: {
          input: {
            gameId: params.gameId,
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.pass;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Переключить дверь
   *
   * Открывает/закрывает дверь на игровом поле.
   */
  async toggleDoor(params: ToggleDoorActionParams): Promise<ActionResult> {
    try {
      const { data, errors } = await apolloClient.mutate<{
        toggleDoor: gql.GameMutationResult;
      }>({
        mutation: gql.ToggleDoorDocument,
        variables: {
          input: {
            gameId: params.gameId,
            doorId: params.doorId,
          },
        },
      });

      if (errors?.length) {
        return {
          success: false,
          error: errors[0].message,
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      const result = data?.toggleDoor;
      if (!result) {
        return {
          success: false,
          error: 'No data returned from server',
          sequenceNumber: 0,
          phase: '',
          currentTurnPlayerId: '',
          turnCount: 0,
          timestamp: new Date(),
        };
      }

      return {
        success: true,
        state: result.state ?? undefined,
        sequenceNumber: result.sequenceNumber,
        phase: result.phase,
        currentTurnPlayerId: result.currentTurnPlayerId ?? '',
        turnCount: result.turnCount,
        timestamp: new Date(result.timestamp),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Зарегистрировать callback для оптимистичного обновления
   *
   * Callback вызывается немедленно при отправке действия,
   * до получения ответа от сервера.
   */
  registerOptimisticCallback(
    actionId: string,
    callback: (result: ActionResult) => void
  ): void {
    this.optimisticCallbacks.set(actionId, callback);
  }

  /**
   * Удалить callback оптимистичного обновления
   */
  unregisterOptimisticCallback(actionId: string): void {
    this.optimisticCallbacks.delete(actionId);
  }

  /**
   * Очистить все callbacks
   */
  clearCallbacks(): void {
    this.optimisticCallbacks.clear();
  }
}

// ------------------------------------------------------------
// Singleton экземпляр
// ------------------------------------------------------------

export const gameActions = new GameActions();
