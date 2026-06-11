// ============================================================
// USE GAME ACTIONS - React hook для игровых действий
// ============================================================

import { useCallback, useMemo } from 'react';
import { ApolloClient } from '@apollo/client';
import * as gql from '@/gql';
import type { Position } from '@/core/models/types';

// ------------------------------------------------------------
// Типы для действий
// ------------------------------------------------------------

/**
 * Результат выполнения действия
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
 * Параметры для манёвра
 */
export interface ManeuverParams {
  fighterId: string;
  cardId: string;
  path: Position[];
}

/**
 * Параметры для атаки
 */
export interface AttackParams {
  attackerId: string;
  targetId: string;
  cardId: string;
}

/**
 * Параметры для защиты
 */
export interface DefenseParams {
  combatId: string;
  cardId: string;
}

/**
 * Параметры для перемещения бойца
 */
export interface MoveFighterParams {
  fighterId: string;
  x: number;
  y: number;
}

/**
 * Опции хука
 */
export interface UseGameActionsOptions {
  /**
   * Apollo клиент
   */
  client: ApolloClient<object>;

  /**
   * ID игры
   */
  gameId: string | null;

  /**
   * ID текущего игрока
   */
  playerId: string | null;

  /**
   * Включить оптимистичные обновления
   */
  optimisticUpdates?: boolean;

  /**
   * Callback при успехе
   */
  onSuccess?: (action: string, result: ActionResult) => void;

  /**
   * Callback при ошибке
   */
  onError?: (action: string, error: string) => void;
}

/**
 * Возвращаемое значение хука
 */
export interface UseGameActionsReturn {
  // Действия
  maneuver: (params: ManeuverParams) => Promise<ActionResult>;
  moveFighter: (params: MoveFighterParams) => Promise<ActionResult>;
  attack: (params: AttackParams) => Promise<ActionResult>;
  playDefense: (params: DefenseParams) => Promise<ActionResult>;
  resolveCombat: () => Promise<ActionResult>;
  endTurn: () => Promise<ActionResult>;
  pass: () => Promise<ActionResult>;
  toggleDoor: (doorId: string) => Promise<ActionResult>;

  // Состояние
  isPending: boolean;
  lastAction: string | null;
}

// ------------------------------------------------------------
// Helper функции
// ------------------------------------------------------------

/**
 * Выполняет мутацию и возвращает результат
 */
async function executeMutation<T>(
  client: ApolloClient<object>,
  mutation: any,
  variables: Record<string, unknown>
): Promise<ActionResult> {
  try {
    const { data, errors } = await client.mutate<T>({
      mutation,
      variables,
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

    const result = data as any;
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

    // Извлекаем результат из разных полей
    const mutationResult = Object.values(result)[0] as gql.GameMutationResult;

    return {
      success: true,
      state: mutationResult.state ?? undefined,
      sequenceNumber: mutationResult.sequenceNumber,
      phase: mutationResult.phase,
      currentTurnPlayerId: mutationResult.currentTurnPlayerId ?? '',
      turnCount: mutationResult.turnCount,
      timestamp: new Date(mutationResult.timestamp),
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

// ------------------------------------------------------------
// Hook implementation
// ------------------------------------------------------------

/**
 * useGameActions - хук для выполнения игровых действий
 *
 * Функционал:
 * - Все игровые мутации (maneuver, attack, defense, etc.)
 * - Оптимистичные обновления
 * - Обработка ошибок
 * - Отслеживание pending состояния
 *
 * @example
 * ```tsx
 * const { maneuver, attack, endTurn, isPending } = useGameActions({
 *   client: apolloClient,
 *   gameId: currentGame?.id,
 *   playerId: currentUser?.id,
 * });
 *
 * // Выполнить действие
 * const result = await attack({
 *   attackerId: 'hero-1',
 *   targetId: 'enemy-1',
 *   cardId: 'punch-1',
 * });
 * ```
 */
export function useGameActions(
  options: UseGameActionsOptions
): UseGameActionsReturn {
  const { client, gameId, playerId, optimisticUpdates = false, onSuccess, onError } = options;

  // Отслеживаем последнее действие
  const state = useMemo(() => ({
    isPending: false,
    lastAction: null as string | null,
  }), []);

  /**
   * Выполнить манёвр
   */
  const maneuver = useCallback(async (params: ManeuverParams): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'maneuver';

    try {
      const result = await executeMutation<{ maneuver: gql.GameMutationResult }>(
        client,
        gql.ManeuverDocument,
        {
          input: {
            gameId,
            fighterId: params.fighterId,
            cardId: params.cardId,
            path: params.path.map(p => ({ x: p.x, y: p.y })),
          },
        }
      );

      if (result.success) {
        onSuccess?.('maneuver', result);
      } else {
        onError?.('maneuver', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  /**
   * Переместить бойца
   */
  const moveFighter = useCallback(async (params: MoveFighterParams): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'moveFighter';

    try {
      const result = await executeMutation<{ moveFighter: gql.GameMutationResult }>(
        client,
        gql.MoveFighterDocument,
        {
          input: {
            gameId,
            fighterId: params.fighterId,
            x: params.x,
            y: params.y,
          },
        }
      );

      if (result.success) {
        onSuccess?.('moveFighter', result);
      } else {
        onError?.('moveFighter', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  /**
   * Атаковать
   */
  const attack = useCallback(async (params: AttackParams): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'attack';

    try {
      const result = await executeMutation<{ attack: gql.GameMutationResult }>(
        client,
        gql.AttackDocument,
        {
          input: {
            gameId,
            attackerId: params.attackerId,
            targetId: params.targetId,
            cardId: params.cardId,
          },
        }
      );

      if (result.success) {
        onSuccess?.('attack', result);
      } else {
        onError?.('attack', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  /**
   * Сыграть защиту
   */
  const playDefense = useCallback(async (params: DefenseParams): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'playDefense';

    try {
      const result = await executeMutation<{ playDefense: gql.GameMutationResult }>(
        client,
        gql.PlayDefenseDocument,
        {
          input: {
            gameId,
            combatId: params.combatId,
            cardId: params.cardId,
          },
        }
      );

      if (result.success) {
        onSuccess?.('playDefense', result);
      } else {
        onError?.('playDefense', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  /**
   * Разрешить бой
   */
  const resolveCombat = useCallback(async (): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'resolveCombat';

    try {
      const result = await executeMutation<{ resolveCombat: gql.GameMutationResult }>(
        client,
        gql.ResolveCombatDocument,
        {
          input: { gameId },
        }
      );

      if (result.success) {
        onSuccess?.('resolveCombat', result);
      } else {
        onError?.('resolveCombat', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  /**
   * Завершить ход
   */
  const endTurn = useCallback(async (): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'endTurn';

    try {
      const result = await executeMutation<{ endTurn: gql.GameMutationResult }>(
        client,
        gql.EndTurnDocument,
        {
          input: { gameId },
        }
      );

      if (result.success) {
        onSuccess?.('endTurn', result);
      } else {
        onError?.('endTurn', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  /**
   * Пассовать
   */
  const pass = useCallback(async (): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'pass';

    try {
      const result = await executeMutation<{ pass: gql.GameMutationResult }>(
        client,
        gql.PassDocument,
        {
          input: { gameId },
        }
      );

      if (result.success) {
        onSuccess?.('pass', result);
      } else {
        onError?.('pass', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  /**
   * Переключить дверь
   */
  const toggleDoor = useCallback(async (doorId: string): Promise<ActionResult> => {
    if (!gameId) {
      return {
        success: false,
        error: 'Нет активной игры',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    state.isPending = true;
    state.lastAction = 'toggleDoor';

    try {
      const result = await executeMutation<{ toggleDoor: gql.GameMutationResult }>(
        client,
        gql.ToggleDoorDocument,
        {
          input: { gameId, doorId },
        }
      );

      if (result.success) {
        onSuccess?.('toggleDoor', result);
      } else {
        onError?.('toggleDoor', result.error ?? 'Неизвестная ошибка');
      }

      return result;
    } finally {
      state.isPending = false;
    }
  }, [gameId, client, onSuccess, onError]);

  return {
    maneuver,
    moveFighter,
    attack,
    playDefense,
    resolveCombat,
    endTurn,
    pass,
    toggleDoor,
    isPending: state.isPending,
    lastAction: state.lastAction,
  };
}
