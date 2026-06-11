/**
 * Game Subscription Resolver (Enhanced)
 *
 * GraphQL подписки для real-time обновлений игры.
 * Поддерживает:
 * - since параметр для реконнекта
 * - Специфичные события (attackInitiated, defensePlayed, combatResolved)
 * - Фильтрация приватных данных для каждого подписчика
 */

import { Resolver, Args, Subscription } from '@nestjs/graphql';
import { ForbiddenException } from '@nestjs/common';
import { Observable } from 'rxjs';
import { GameSubscriptionService, GameUpdateEvent } from '../game-subscription.service';
import { GameStateService, GameState } from '../game-state.service';
import {
  GameEvent,
  TurnState,
  GameEventType,
  GameState as GameStateGQL,
} from '../dto/gameplay.dto';
import { GamePhase } from '../dto';

/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-argument */
/* eslint-disable @typescript-eslint/no-unsafe-assignment */

/**
 * Состояние игры для публикации в подписках
 */
interface GameEventPayload {
  gameId: string;
  sequenceNumber: number;
  timestamp: number;
  eventType: GameEventType;
  payload: any;
}

const resolveGameStateFn =
  (gameStateService: GameStateService, getUserIdFn: (context: any) => string) =>
  (value: GameEventPayload | null, args: any, context: any): GameStateGQL | null => {
    if (!value) return null;

    // Проверяем since параметр
    if (args?.since !== undefined && value.sequenceNumber <= args.since) {
      return null;
    }

    const userId = getUserIdFn(context);
    const filteredState = gameStateService.filterPrivateData(value.payload, userId);

    return {
      gameId: value.gameId,
      sequenceNumber: value.sequenceNumber,
      phase: filteredState.phase,
      turnCount: filteredState.turnCount,
      currentTurnPlayerId: filteredState.currentTurnPlayerId,
      players: JSON.stringify(filteredState.players),
      fighters: JSON.stringify(filteredState.fighters),
      handZones: JSON.stringify(filteredState.handZones),
      boardState: JSON.stringify(filteredState.boardState),
      metadata: JSON.stringify(filteredState.metadata),
    };
  };

const resolveGameEventFn =
  () =>
  (value: GameEventPayload | null): GameEvent => {
    if (!value) {
      return {
        type: GameEventType.FIGHTER_MOVED,
        gameId: '',
        sequenceNumber: 0,
        timestamp: new Date(),
        payload: null,
      };
    }

    return {
      type: value.eventType,
      gameId: value.gameId,
      sequenceNumber: value.sequenceNumber,
      timestamp: new Date(value.timestamp),
      payload: value.payload,
    };
  };

const resolveTurnStateFn =
  () =>
  (value: GameEventPayload | null): TurnState => {
    if (!value) {
      return {
        playerId: '',
        turnCount: 0,
        phase: GamePhase.SETUP,
      };
    }

    const state = value.payload as GameState;

    return {
      playerId: state.currentTurnPlayerId || '',
      turnCount: state.turnCount,
      phase: state.phase,
    };
  };

@Resolver(() => GameStateGQL)
export class GameSubscriptionResolver {
  private resolveGameState!: (
    value: GameEventPayload | null,
    args: any,
    context: any,
  ) => GameStateGQL | null;
  private resolveGameEvent!: (value: GameEventPayload | null) => GameEvent;
  private resolveTurnState!: (value: GameEventPayload | null) => TurnState;

  constructor(
    private readonly subscriptionService: GameSubscriptionService,
    private readonly gameStateService: GameStateService,
  ) {
    this.resolveGameState = resolveGameStateFn(this.gameStateService, (context) =>
      this.getUserId(context),
    );

    this.resolveGameEvent = resolveGameEventFn();

    this.resolveTurnState = resolveTurnStateFn();
  }

  /**
   * Подписка на обновления состояния игры
   * Поддерживает since параметр для реконнекта
   */
  @Subscription(() => GameStateGQL, {
    name: 'gameStateUpdated',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return payload.gameId === variables.gameId;
    },
    resolve: function (this: GameSubscriptionResolver, value: any, args: any, context: any) {
      return this.resolveGameState(value || null, args, context);
    },
  })
  gameStateUpdated(
    @Args('gameId') gameId: string,
    @Args('since', { nullable: true }) since?: number,
    @Args('userId', { nullable: true }) userId?: string,
  ): Observable<GameStateGQL> {
    return this.createGameObservable(gameId, userId || '', since) as any;
  }

  /**
   * Подписка на события атак
   */
  @Subscription(() => GameEvent, {
    name: 'attackInitiated',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return (
        payload.gameId === variables.gameId && payload.eventType === GameEventType.ATTACK_INITIATED
      );
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  attackInitiated(@Args('gameId') gameId: string): Observable<GameEvent> {
    return this.createGameObservable(gameId, '') as any;
  }

  /**
   * Подписка на события защиты
   */
  @Subscription(() => GameEvent, {
    name: 'defensePlayed',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return (
        payload.gameId === variables.gameId && payload.eventType === GameEventType.DEFENSE_PLAYED
      );
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  defensePlayed(@Args('gameId') gameId: string): Observable<GameEvent> {
    return this.createGameObservable(gameId, '') as any;
  }

  /**
   * Подписка на события разрешения боя
   */
  @Subscription(() => GameEvent, {
    name: 'combatResolved',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return (
        payload.gameId === variables.gameId && payload.eventType === GameEventType.COMBAT_RESOLVED
      );
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  combatResolved(@Args('gameId') gameId: string): Observable<GameEvent> {
    return this.createGameObservable(gameId, '') as any;
  }

  /**
   * Подписка на события смены хода
   */
  @Subscription(() => TurnState, {
    name: 'turnChanged',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return (
        payload.gameId === variables.gameId && payload.eventType === GameEventType.TURN_CHANGED
      );
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveTurnState(value || null);
    },
  })
  turnChanged(@Args('gameId') gameId: string): Observable<TurnState> {
    return this.createGameObservable(gameId, '') as any;
  }

  /**
   * Подписка на события присоединения игроков
   */
  @Subscription(() => GameEvent, {
    name: 'playerJoined',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return (
        payload.gameId === variables.gameId && payload.eventType === GameEventType.PLAYER_JOINED
      );
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  playerJoined(@Args('gameId') gameId: string): Observable<GameEvent> {
    return this.createGameObservable(gameId, '') as any;
  }

  /**
   * Подписка на события выхода игроков
   */
  @Subscription(() => GameEvent, {
    name: 'playerLeft',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return payload.gameId === variables.gameId && payload.eventType === GameEventType.PLAYER_LEFT;
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  playerLeft(@Args('gameId') gameId: string): Observable<GameEvent> {
    return this.createGameObservable(gameId, '') as any;
  }

  /**
   * Подписка на события окончания игры
   */
  @Subscription(() => GameEvent, {
    name: 'gameEnded',
    filter: (payload: any, variables: any) => {
      if (!payload || !variables) return false;
      return payload.gameId === variables.gameId && payload.eventType === GameEventType.GAME_ENDED;
    },
    resolve: function (this: GameSubscriptionResolver, value: any) {
      return this.resolveGameEvent(value || null);
    },
  })
  gameEnded(@Args('gameId') gameId: string): Observable<GameEvent> {
    return this.createGameObservable(gameId, '') as any;
  }

  // ============================================
  // Private Helper Methods
  // ============================================

  /**
   * Создать Observable для игровых событий
   */
  private createGameObservable(gameId: string, userId: string, since?: number): Observable<any> {
    return new Observable<GameEventPayload>((subscriber) => {
      // Получаем базовый observable от subscription service
      const baseObservable = this.subscriptionService.subscribeToGame(
        gameId,
        userId,
        (state: GameState) => {
          // Фильтруем приватные данные для пользователя
          return this.gameStateService.filterPrivateData(state, userId);
        },
      );

      // Подписываемся и трансформируем события
      const subscription = baseObservable.subscribe({
        next: (event: GameUpdateEvent) => {
          // Проверяем since параметр
          if (since !== undefined && event.sequenceNumber <= since) {
            return; // Пропускаем устаревшие события
          }

          // Определяем тип события на основе изменений в состоянии
          const eventType = this.determineEventType(event);

          subscriber.next({
            gameId: event.gameId,
            sequenceNumber: event.sequenceNumber,
            timestamp: event.timestamp,
            eventType,
            payload: event.gameState,
          });
        },
        error: (err) => subscriber.error(err),
        complete: () => subscriber.complete(),
      });

      // Cleanup при отписке
      return () => {
        subscription.unsubscribe();
      };
    });
  }

  /**
   * Определить тип события на основе изменений в состоянии
   */
  private determineEventType(event: GameUpdateEvent): GameEventType {
    const { gameState } = event;
    if (!gameState) {
      return GameEventType.FIGHTER_MOVED;
    }

    const phase = gameState.phase;

    // Определяем тип события по фазе и другим признакам
    switch (phase) {
      case GamePhase.COMBAT:
        return GameEventType.ATTACK_INITIATED;
      case GamePhase.COMBAT_RESOLVE:
        return GameEventType.COMBAT_RESOLVED;
      case GamePhase.TURN_START:
        return GameEventType.TURN_CHANGED;
      case GamePhase.TURN_END:
        return GameEventType.TURN_ENDED;
      default:
        return GameEventType.FIGHTER_MOVED;
    }
  }

  /**
   * Получить userId из контекста
   */
  private getUserId(context: any): string {
    const userId = context?.req?.user?.id || context?.user?.id;

    if (!userId) {
      throw new ForbiddenException('User not authenticated');
    }

    return userId;
  }
}
